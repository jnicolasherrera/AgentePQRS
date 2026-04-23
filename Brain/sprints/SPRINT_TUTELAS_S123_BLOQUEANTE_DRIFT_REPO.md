# Bloqueante FASE A — Drift repo ↔ prod ↔ 14 sectorial

**Fecha:** 2026-04-23
**Estado:** STOP. Se detienen A.1–A.9 de la reconstrucción. No se ha tocado staging ni el repo.
**Regla que dispara la pausa:** "Si durante FASE A encontrás que alguna de las 01-14 falla contra staging limpio: STOP y reportá."

Este documento compila los 3 bloqueantes detectados al preparar la FASE A. La reconstrucción tal como está especificada en Opción 1b **no puede ejecutarse** con las SQLs actuales del repo.

---

## Inventario confirmado de SQLs en el repo

`find` exhaustivo detectó solo 7 SQLs, coincidiendo con lo que el prompt original esperaba:

```
01_schema_v2.sql                                         raíz
02_rls_security_v2.sql                                   raíz
03_advanced_features_v2.sql                              raíz
04_multi_tenant_config_v2.sql                            raíz
05_multi_provider_buzones.sql                            raíz
08_plantillas_schema.sql                                 raíz
aequitas_infrastructure/database/14_regimen_sectorial.sql
```

No existen 06, 07, 09, 10, 11, 12, 13 en ningún directorio del repo.

## Bloqueante 1 — Drift repo ↔ prod: ~14 columnas de `pqrs_casos` no vienen de ningún SQL

Prod 18.228 tiene 30 columnas en `pqrs_casos`. Las 7 SQLs del repo crean solo estas 16:

| Columna | Fuente en repo |
|---|---|
| id, cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, created_at | 01_schema_v2.sql |
| borrador_respuesta, borrador_estado, problematica_detectada, plantilla_id, aprobado_por, aprobado_at, enviado_at | 08_plantillas_schema.sql |

Las 14 columnas restantes existen en prod pero **no las crea ninguna SQL del repo**:

```
fecha_vencimiento, tipo_caso, external_msg_id, asignado_a, fecha_asignacion,
updated_at, alerta_2h_enviada, acuse_enviado, numero_radicado, es_pqrs,
reply_adjunto_ids, texto_respuesta_final, borrador_ia_original, edit_ratio
```

**Implicación:** aplicar 01-14 contra staging limpio produce un schema de `pqrs_casos` **con solo 16 columnas**, que no refleja prod y que hará fallar cualquier pipeline que asuma la presencia de `tipo_caso`, `fecha_vencimiento`, `numero_radicado`, etc.

**Conclusión:** prod fue construido ejecutando SQLs que no están versionadas. Hay migraciones fantasma (presumiblemente 06, 07, 09-13, y posiblemente otras no numeradas) que corrieron directo contra prod en su momento y nunca se subieron al repo.

## Bloqueante 2 — La migración 14 depende de columnas que no existen en el repo

La 14 (`14_regimen_sectorial.sql`) crea el trigger `fn_set_fecha_vencimiento()`:

```sql
NEW.fecha_vencimiento := calcular_fecha_vencimiento(
  NEW.fecha_recibido, NEW.cliente_id, NEW.tipo_caso
);
NEW.semaforo_sla := 'VERDE';
```

Referencias requeridas en `pqrs_casos`:
- `fecha_vencimiento` ← **no la crea ninguna SQL del repo**.
- `tipo_caso` ← **no la crea ninguna SQL del repo**.
- `semaforo_sla` ← **no la crea ninguna SQL del repo Y tampoco existe en prod**.

Aplicar la 14 contra staging limpio con solo 01-08 previas **romperá el trigger en el primer INSERT** (ERROR: column "tipo_caso" does not exist / column "semaforo_sla" does not exist).

Nota adicional: `semaforo_sla` tampoco existe en prod hoy (verificado en diagnóstico read-only, sección 2 de `SPRINT_TUTELAS_S123_DIAG_PROD_READONLY.md`). El código del trigger asume una columna que **ningún ambiente tiene**. Si algún día se aplica la 14 a prod tal como está, el primer INSERT en `pqrs_casos` revienta.

## Bloqueante 3 — Las 04 y 05 contienen UUIDs productivos y secretos de Zoho

### 04_multi_tenant_config_v2.sql líneas 62-76

```sql
INSERT INTO config_buzones (cliente_id, email_buzon, azure_folder_id) VALUES
  ('a1b2c3d4-e5f6-7890-1234-56789abcdef0', 'clientes@flexfintech.com', '...');
INSERT INTO config_buzones (cliente_id, email_buzon, azure_folder_id) VALUES
  ('d1cf5e93-4121-4124-abf7-0f8dc1b070a9', 'clientes@cliente2.com', '...');
```

Esos `cliente_id` son UUIDs productivos de FlexFintech y Cliente2. No existen en staging limpio → `INSERT` falla por FK violation contra `clientes_tenant(id)`.

Además, si luego el seed 99 crea los mismos UUIDs como "sintéticos", estaríamos mezclando datos reales con sintéticos y perdiendo el guardrail anti-PII.

### 05_multi_provider_buzones.sql líneas 15-33

```sql
INSERT INTO config_buzones (
    cliente_id, email_buzon, proveedor, ..., azure_client_id, azure_client_secret,
    zoho_refresh_token, zoho_account_id
) VALUES (
    'effca814-b0b5-4329-96be-186c0333ad4b', 'pqrs@arcsas.com.co', 'ZOHO', ...,
    '1000.TKA5AEC621AB1NISPL1YEN08VKRHAC',
    '568f75dac62845e5d8e4caff0deef488c2896803cd',
    '1000.1b69662a184a373bc3171bb906733499.1c2be417d333b565605751d1e126fc5c',
    '2429327000000008002'
);
```

Mismo FK-violation issue contra staging limpio.

Y además — **esto es un problema de seguridad separado que debería tratarse como incidente:** hay credenciales productivas de Zoho de ARC versioneadas en git. Si ese repo alguna vez pasó por un fork público, ya están comprometidas. Cualquier deploy futuro contra prod con la 05 tal cual está volvería a escribir esos secretos en la DB. No voy a tocar esto sin autorización explícita — pero lo flagueo.

---

## Cómo se llegó acá (hipótesis de raíz)

1. Entre el 25-feb y abril-2026 varias columnas y tablas se agregaron a prod con SQLs ad-hoc que nunca se versionaron (no pasaron por commit), o se versionaron con nombres distintos que luego se borraron.
2. La 14 se escribió asumiendo que las columnas `tipo_caso`/`fecha_vencimiento`/`semaforo_sla` existían en prod cuando la función/trigger fuesen creados — pero como el deploy a prod nunca ocurrió (verificado en sesión anterior), nadie detectó que `semaforo_sla` no existe en ningún ambiente real.
3. La 14 sí llegó a ejecutarse en staging 15.229 el 8-abril (ahí sí existen las tablas festivos/sla_regimen_config), pero el schema esqueleto de 15.229 tampoco tenía `tipo_caso` ni `fecha_vencimiento` en ese momento, lo que deja el trigger apuntando a columnas ausentes — el mismo estado roto que observamos en el diagnóstico D3 de 15.229.

La consecuencia es que **no existe en ningún lado un conjunto de SQLs capaz de reproducir el schema de prod**. Para reconstruir staging desde cero necesitaríamos, como mínimo, parchear el repo con SQLs nuevas que cierren el gap.

## Opciones (para decisión de Nico)

**Opción X — Reconstruir el historial de migraciones "sintetizando" las faltantes.**
- Crear nuevas SQLs `06_`, `07_`, `09_`, `10_`, `11_`, `12_`, `13_` con los `ALTER TABLE ADD COLUMN IF NOT EXISTS` necesarios para llegar al schema de prod.
- Modificar (o crear variantes staging de) la 04 y 05 para que sus INSERTs sean **condicionales** a la existencia del tenant (`WHERE EXISTS (...)` o `ON CONFLICT DO NOTHING` tras crear tenants fake primero).
- Agregar al repo una `15_fix_semaforo_sla.sql` que cree la columna `semaforo_sla` en `pqrs_casos` **antes** de que la 14 pueda cargar su trigger (o rehacer la 14 para que no la toque).
- Costo: 3-5 h adicionales para escribir y validar. Queda un repo limpio que sí reconstruye prod.
- Riesgo: introducir diferencias sutiles entre las SQLs sintetizadas y lo que prod realmente corrió históricamente. Es el mejor esfuerzo posible sin dump.

**Opción Y — pg_dump schema-only de prod (sin datos) + restaurar en staging.**
- No expone PII (solo schema), pero Nico había descartado cualquier `pg_dump` de prod.
- Diferencia vs 1a original: `--schema-only` omite filas.
- Preguntar si Nico acepta esta variante. Técnicamente no viola Ley 1581 porque no se exporta data personal. Política del proyecto podría seguir diciendo no.
- Costo: 30 min.
- Riesgo: si más adelante queremos diff "repo vs prod" para detectar drift, este dump nos da la baseline exacta que sirve como piedra angular de la tarea DT-19 que ya acordamos agregar.

**Opción Z — Renegociar alcance del sprint Tutelas.**
- Mantener staging 15.229 tal como está (esqueleto) y construir las migraciones 18-21 sobre ese esqueleto reconstituyendo solo lo mínimo indispensable en el momento que las 18-21 lo necesiten.
- Es básicamente volver a la propuesta "seguir en staging mínimo con fixture sintético" que el PROGRESS listó como opción (1).
- Costo: bajo, pero deja el sprint cerrando sin poder correr un smoke E2E realista.

**Opción W — Parar el sprint Tutelas y abrir antes un sprint de "reconciliación de migraciones".**
- Reconocer que el repo está en un estado no ejecutable contra limpio. Primero arreglar el repo (Opción X más a fondo + DT-19 drift detection), después reanudar el Tutelas.
- Costo: 1-2 días. Pero queda el sistema en estado sano.

## Lo que NO hice (para que quede claro que nada se tocó)

- No ejecuté `pg_dump` contra staging ni prod.
- No borré ni moví archivos del repo.
- No corrí `DROP SCHEMA` ni nada contra staging.
- No creé `migrations/` ni `scripts/migrate.sh`.
- No toqué las credenciales productivas expuestas en 05. Solo las mencioné.
- No modifiqué ninguna SQL.

## Información adicional relevante

- Hay una deuda de seguridad no registrada: `05_multi_provider_buzones.sql` contiene secretos productivos de Zoho en claro (`zoho_refresh_token`, `zoho_account_id`, `azure_client_id`, `azure_client_secret`). Merece sprint de remediación propio (rotación + scrub de git history).
