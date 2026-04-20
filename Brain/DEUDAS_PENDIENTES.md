# Deudas técnicas registradas

## Motor SLA sectorial — deploy pendiente

**Estado:** dormido en `main` desde 2026-04-13
**Commits involucrados:**
- `c26bcee` — feat(sla): motor SLA sectorial — régimen FINANCIERO 8 días SFC
- `0713f74` — fix(sla): agregar tabla `festivos_colombia` 2026 a migración 14

### Por qué está dormido

La migración `aequitas_infrastructure/database/14_regimen_sectorial.sql` (169 líneas) **nunca corrió** contra la DB de producción `pqrs_v2`. El código en main hace queries a estructuras que no existen:

| Objeto | Tipo | Dónde se usa |
|---|---|---|
| `festivos_colombia` | tabla | `backend/app/core/models.py:259` (clase ORM huérfana, sin queries) |
| `sla_regimen_config` | tabla | `backend/app/api/routes/admin.py:487` |
| `clientes_tenant.regimen_sla` | columna | `backend/app/api/routes/admin.py:437, 462, 481` |

Ninguna existe en `pqrs_v2` hoy (verificado 2026-04-13 via `information_schema`).

> **Nota de inconsistencia documental (16-abril-2026)**: `sprints/SPRINT_SLA_SECTORIAL.md` dice que el sprint se aplicó a "Staging 18.228.54.9" el 8-abril, pero esa IP es **producción**, no staging (staging real es `15.229.114.148`). Resolver en sesión dedicada: o el sprint se aplicó a staging `15.229.114.148` y el documento tiene un typo, o el sprint sí se aplicó a prod `18.228.54.9` y entonces el estado de esta deuda está mal descrito. Verificar con `information_schema` cuál es el estado real hoy antes de cualquier deploy.

### Endpoints afectados (en disco, NO en runtime)

4 rutas nuevas en `backend/app/api/routes/admin.py` (+227 líneas respecto al runtime actual `97f239e`):

- `GET /admin/regimen-sla/{cliente_id}` → línea ~430
- `POST /admin/regimen-sla/{cliente_id}` → línea ~444
- Otros 2 endpoints auxiliares de config

**Estado protegido**: los containers `pqrs_v2_backend` corriendo hoy están en commit `97f239e` que NO tiene estas rutas. Los endpoints existen solo en disco. Rebuildear `backend` sin aplicar migración primero → `500 column "regimen_sla" does not exist` al primer click.

### Plan de deploy futuro (cuando se aborde)

Orden obligatorio:

1. **Leer migración 14 completa** (169 líneas) y validar que no tiene `DROP`, `TRUNCATE`, `UPDATE` masivo, ni `FOREIGN KEY` contra tablas grandes.
2. **Backup DB pre-deploy** (`docker exec pqrs_v2_db pg_dump -F c`).
3. **Aplicar migración 14 contra `pqrs_v2`** manualmente:
   ```bash
   docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 < aequitas_infrastructure/database/14_regimen_sectorial.sql
   ```
4. **Verificar que las 2 tablas y la columna nueva existen**:
   ```sql
   SELECT count(*) FROM festivos_colombia;
   SELECT count(*) FROM sla_regimen_config;
   SELECT column_name FROM information_schema.columns WHERE table_name='clientes_tenant' AND column_name='regimen_sla';
   ```
5. **Smoke test de queries directas** de `admin.py` contra la DB real.
6. **Recién entonces rebuild de `pqrs_v2_backend`** con `docker compose up -d --no-deps --build backend`.
7. **Smoke test funcional** de los endpoints admin vía curl con JWT de super_admin.
8. **Comunicar a Paola (Recovery)** que hay tab nuevo de "Régimen SLA" disponible en admin.
9. **Ideal**: correr todo el ciclo primero en staging EC2 (`15.229.114.148`) con datos clonados de Recovery.

### Complejidad

**Medio-alta.** No es urgente — hoy nadie usa la feature. El bloqueo principal es validar que el SQL no tiene sorpresas (lo único que leí confirmado es la sección de `festivos_colombia` del commit `0713f74`, líneas 7-36). El resto del archivo (líneas 38-168) requiere lectura previa.

### Referencia cruzada

- Análisis forense completo del drift: ver `Brain/CHANGELOG.md` entrada `2026-04-13 (deploy nocturno)`.
- Regla anti-drift que previno este deploy en caliente: `Brain/00_DIRECTIVAS_CLAUDE_CODE.md` sección 3.5.
- Bug separado pendiente: visualización de `borrador_respuesta` en frontend pestaña Casos (tipo TS `Caso` no declara el campo).

---

## 2026-04-14 — Deudas descubiertas durante fix FirmaModal

### Bug UX del FirmaModal (no bloqueante)

**Severidad**: Baja (cosmético)
**Archivo**: `frontend/src/components/ui/firma-modal.tsx`
**Líneas**: 33-40

**Descripción**: Después de confirmar el envío, el modal se cierra pero la notificación flotante no aparece visiblemente (o aparece por menos de 1 segundo). Además, el código siempre dispara `tipo='exito'` aunque `res.data.enviados` sea 0, lo cual produce notificaciones verdes engañosas del tipo *"0 respuesta(s) enviada(s) correctamente"* cuando en realidad el envío falló.

**Fix propuesto**:

```typescript
if (res.data.enviados === 0 && res.data.errores.length > 0) {
  setNotifEnvio({
    tipo: 'error',
    mensaje: `Envío falló: ${res.data.errores[0].motivo}`
  });
} else {
  setNotifEnvio({
    tipo: 'exito',
    mensaje: `${res.data.enviados} respuesta(s) enviada(s) correctamente`
  });
}
```

**Cómo verificar**: después del fix, hacer smoke test desactivando `DEMO_GMAIL_USER` del backend y confirmar que aparece notificación roja con error específico.

---

### Kafka containers Exited hace 5+ días

**Severidad**: Media (investigar por qué nadie se dio cuenta)

**Evidencia**:
```bash
docker ps -a | grep kafka
pqrs_staging_kafka  Exited (1) 5 days ago
pqrs_v2_kafka       Exited (1) 5 days ago
```

El backend tiene manejo gracioso: intenta 5 veces conectarse a Kafka al arrancar, loguea `"Kafka no disponible — API arranca sin producer"`, y sigue funcionando. Los `GET`/`POST` de `/api/v2/*` se atienden normalmente porque el flujo principal (auth, casos, stats, SSE via Redis) no depende de Kafka.

Kafka se usaba (presumiblemente) para publicar eventos secundarios a un event bus. Sin Kafka, esos eventos no se publican, pero no rompen el flujo principal.

**Acción pendiente**:

1. Investigar qué consumidores dependen de los eventos Kafka.
2. Decidir si reactivar Kafka o si el event bus es deuda técnica a deprecar.
3. Ajustar monitoreo para detectar cuando containers críticos quedan `Exited`.

---

## 2026-04-15/16 — Deudas hardening AWS

Generadas durante el sprint de hardening AWS documentado en `fixes/HARDENING_AWS_ABRIL_2026.md`. Todas son para el camino a Bancolombia; ninguna bloquea operación actual.

### DT-1 — SSE-KMS en CloudTrail (CMK dedicada)

**Severidad**: Media (compliance bancaria).
**Estado actual**: CloudTrail `flexpqr-trail` usa cifrado SSE-S3 (AES-256 gestionado por AWS) en los logs del bucket `flexpqr-cloudtrail-logs`. Funciona y cumple el mínimo, pero no da control granular sobre quién puede descifrar los logs.
**Gap**: auditores bancarios típicamente piden SSE-KMS con CMK dedicada (Customer Managed Key) para que la propia organización controle la key y su rotación, y el log de uso de la key quede también en CloudTrail. Habilita separación de funciones (quien opera EC2 ≠ quien descifra logs de auditoría).
**Plan**: crear CMK `flexpqr/cloudtrail` en KMS → policy de la CMK que permita a CloudTrail cifrar y solo a auditor + root descifrar → editar trail para usar SSE-KMS con esta CMK → verificar que los logs siguientes están cifrados con la CMK.
**Esfuerzo**: ~30 minutos.
**Responsable**: Nico.
**Trigger**: antes de primera auditoría formal de Bancolombia o cuando se active.

---

### DT-2 — GuardDuty multi-región

**Severidad**: Media.
**Estado actual**: GuardDuty activo solo en `sa-east-1` (trial 30 días).
**Gap**: una cuenta AWS comprometida no necesariamente opera desde la región donde están los workloads. Un atacante que roba credenciales puede lanzar instancias en `us-east-1` sin que GuardDuty de `sa-east-1` lo vea. La best practice es GuardDuty en todas las regiones donde la cuenta puede operar.
**Plan**: activar GuardDuty en `us-east-1`, `us-west-2`, `eu-west-1`, `ap-southeast-1` (mínimo), idealmente todas las regiones. Configurar una región como "administrador delegado" para centralizar findings.
**Esfuerzo**: ~10 minutos por región (consola web).
**Responsable**: Nico.
**Trigger**: antes del fin del trial de 30 días en `sa-east-1` para consolidar decisión de si continuar pagando.

---

### DT-3 — Migrar `*FullAccess` a policies custom mínimas

**Severidad**: Alta (least privilege).
**Estado actual**: `flexpqr-deploy` tiene `AmazonEC2FullAccess`, `AmazonS3FullAccess`, `CloudWatchFullAccess`. Funciona pero viola least privilege — el user puede, por ejemplo, eliminar la EC2 de producción o cualquier bucket S3 de la cuenta.
**Gap**: auditores bancarios miran directamente las policies attached a los users de producción. `*FullAccess` es señal de alerta roja.
**Plan**: identificar las operaciones exactas que el user necesita (ssh via SSM Session Manager, subir/bajar archivos a buckets específicos, leer métricas CloudWatch, restart de instancias). Escribir 3 policies custom con solo esas acciones, scoped a los ARNs específicos (instance ARN, bucket ARNs, log group ARNs). Attach las custom, detach las `*FullAccess`.
**Esfuerzo**: ~1 hora (incluye testing de que nada se rompe).
**Responsable**: Nico.
**Trigger**: antes de due diligence técnico de Bancolombia.

---

### DT-4 — AWS IAM Identity Center cuando sumen Dante/Martín

**Severidad**: Media-alta (compliance + segregación de funciones).
**Estado actual**: acceso AWS solo por Nico (root + `flexpqr-deploy`). Dante y Martín no tienen acceso formal a la consola AWS.
**Gap**: compartir credenciales root es anti-patrón. Crear IAM users individuales funciona pero dificulta rotación y desactivación. Identity Center (antes AWS SSO) resuelve esto con login federado + asignación de permisos por grupo.
**Plan**: crear directorio Identity Center → crear grupos (`Admins`, `Developers`, `ReadOnly`) → asignar permission sets a cada grupo → invitar a Dante y Martín con acceso a los grupos correspondientes. Cuando salga alguien del equipo, se borra de Identity Center y queda sin acceso a AWS automáticamente.
**Esfuerzo**: ~45 minutos.
**Responsable**: Nico.
**Trigger**: cuando Dante o Martín necesiten acceso directo a AWS (por ahora no lo necesitan).

---

### DT-5 — Rotación automática de access keys

**Severidad**: Media (best practice).
**Estado actual**: Access Key de `flexpqr-deploy` generada el 15-abril-2026, sin fecha de rotación planificada.
**Gap**: AWS recomienda rotar access keys cada 90 días máximo. Muchos frameworks de compliance (incluyendo los que auditan los bancos colombianos) lo exigen.
**Plan**: script trimestral (cron en EC2 o GitHub Actions) que:
  1. Crea una Access Key nueva para `flexpqr-deploy`.
  2. Actualiza el secret en el orquestador de secretos (cuando exista; por ahora, manualmente en `~/.aws/credentials` de la máquina de Nico).
  3. Espera 24 horas para asegurar que nadie usa la vieja.
  4. Elimina la Access Key vieja.
**Esfuerzo**: ~2 horas (implementar + probar).
**Responsable**: Nico.
**Trigger**: antes de la primera rotación manual (objetivo: mediados de julio 2026 para mantener ciclo trimestral).

---

### DT-6 — Retención CloudTrail 10 años (solo si Bancolombia lo pide)

**Severidad**: Depende del cliente.
**Estado actual**: lifecycle del bucket `flexpqr-cloudtrail-logs` con expiración a los 2555 días (7 años), alineado con normativa SARLAFT general.
**Gap**: algunos bancos exigen 10 años de retención para todos los audit logs relacionados con procesamiento de información de clientes bancarios.
**Plan**: si Bancolombia u otro cliente bancario lo exige en el contrato → ajustar lifecycle del bucket de 2555 días a 3650 días. Evaluar costo Glacier a 10 años (muy bajo pero no cero). Documentar en el contrato.
**Esfuerzo**: ~5 minutos (1 edit en lifecycle policy).
**Responsable**: Nico.
**Trigger**: cláusula contractual con Bancolombia o equivalente.

---

### DT-7 — Push commit Brain `0307fa1` al remoto

**Severidad**: Baja-media (resiliencia documental).
**Estado actual**: commit `0307fa1` del Brain está en la branch `develop` local, sin push al remoto desde el 14-abril. La auditoría de Dante y el sprint de hardening viven solo en la máquina de Nico.
**Gap**: si la máquina de Nico se rompe mañana, se pierden ~3 días de memoria operacional del proyecto. Riesgo bus-factor sobre documentación, no solo sobre infraestructura.
**Plan**: `cd /mnt/f/proyectos/AgentePQRS && git checkout develop && git push origin develop`. Verificar que aparece en GitHub. Considerar merge a main si el Brain ya es oficial.
**Esfuerzo**: ~2 minutos.
**Responsable**: Nico (cuando termine el sprint actual sin riesgos).
**Trigger**: fin de sesión del 16-abril-2026.

---

### DT-8 — Guardrail `docker-compose.yml` prod vs local

**Severidad**: Alta (riesgo de reabrir los 9 puertos cerrados por Dante).
**Estado actual**: el compose de producción tiene todos los puertos críticos bindeados a `127.0.0.1` (fruto del hardening del 14-abril) y env vars Gmail específicas. El compose local los expone a `0.0.0.0` y no tiene esas env vars. No hay nada que impida copiar local sobre prod y borrar silenciosamente el hardening.
**Gap**: un `scp docker-compose.yml server:~/PQRS_V2/` apurado un día cualquiera borra 2 horas de trabajo de seguridad sin aviso. Ni un lint, ni un hook, ni un log lo detecta.
**Plan**:
  1. **Corto plazo (~15 min)**: crear `README.DEPLOY.md` en la raíz del repo con el diff esperado documentado y la regla "NO sincronizar compose entre entornos sin diff aprobado".
  2. **Mediano plazo (~2 horas)**: script `deploy/verify_compose_diff.sh` que lee compose local y el de prod (via SSH), aborta si detecta líneas con puertos que no empiezan por `127.0.0.1:` o env vars de prod que faltan en local, imprime diff legible, y exige confirmación `yes` explícita antes de continuar.
  3. **Largo plazo**: mover todo deploy a GitHub Actions con estado declarativo, no file sync.
**Esfuerzo**: corto plazo 15 min, mediano 2 h.
**Responsable**: Nico.
**Trigger**: próximo deploy que toque docker-compose.yml (hacer el README antes de cualquier edit).

---

### Credenciales a rotar (expuestas durante sesión)

Durante la sesión de hardening aparecieron logs mostrando credenciales activas. No son deudas estructurales sino tareas específicas de rotación:

| Credencial | Servicio | Prioridad |
|---|---|---|
| App Password Gmail `democlasificador@gmail.com` | SMTP demo | Alta |
| Password Redis de `pqrs_v2_redis` | Cache/SSE | Alta |
| Credenciales MinIO `adminminio/adminpassword` | Object storage | Media (ya eran conocidas) |

Patrón de rotación sin downtime documentado en `fixes/HARDENING_AWS_ABRIL_2026.md`.
