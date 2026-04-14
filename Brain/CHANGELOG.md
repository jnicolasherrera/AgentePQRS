# Brain Changelog

## 2026-04-14 — Fix FirmaModal demo tenant + DEMO_RESET_MINUTES

### Contexto
En la demo de Banco Popular del 14-abril-2026, Martín intentó mostrar el flujo "editar borrador + confirmar con clave + enviar manualmente". El FirmaModal apareció correctamente y la clave fue aceptada, pero el envío del correo falló silenciosamente. El `POST /aprobar-lote` retornó 200 OK pero con `{enviados: 0, errores: [...]}`.

### Diagnóstico (Fase A1)
Read-only, 100% sin tocar containers. Causa raíz: el container `backend_v2` **no tenía las variables de entorno `DEMO_GMAIL_USER` y `DEMO_GMAIL_PASSWORD`**. Cuando el endpoint `/aprobar-lote` no encuentra `config_buzones` para el demo tenant, cae a `_send_via_gmail()` como fallback. Pero las env vars estaban vacías, así que la función retornaba `False` sin siquiera intentar el SMTP. Sin `logger.error` (en versión `97f239e` del runtime), por eso no aparecía en logs.

### Evidencias del diagnóstico
- `config_buzones` sin fila para demo tenant (0 filas)
- Container `backend_v2` sin ninguna `DEMO_*` env var (verificado con `docker exec ... env | grep`)
- `POST /aprobar-lote` retornó 200 OK en logs (no 401, no 500)
- Cero tracebacks durante la demo
- `audit_log_respuestas` últimas 24h: solo `BORRADOR_GENERADO`, cero `ENVIADO_LOTE`
- `demo_worker` SÍ tenía las env vars y funcionaba correctamente para enviar acuses

### Fix aplicado (A2)
Agregar 2 env vars a la sección `backend_v2 > environment` del `docker-compose.yml` de prod. **Sin rebuild** de imagen — solo recreate del container para que tome las nuevas variables.

```yaml
backend_v2:
  environment:
    # ... env vars existentes ...
    - ACCESS_TOKEN_EXPIRE_MINUTES=480
    - DEMO_GMAIL_USER=democlasificador@gmail.com      # NUEVO
    - DEMO_GMAIL_PASSWORD=${DEMO_GMAIL_PASSWORD:-}    # NUEVO
```

Comando de deploy:
```bash
docker compose up -d --no-deps backend_v2
```

### Fix integrado (A4) — DEMO_RESET_MINUTES
Aprovechando el mismo edit al compose, se subió `DEMO_RESET_MINUTES` de **30 a 1440** minutos en la sección `demo_worker_v2`. Motivo: el reset de 30 minutos estaba borrando casos del demo tenant durante las demos, haciendo desaparecer casos que Martín acababa de crear para mostrar al cliente.

```yaml
demo_worker_v2:
  environment:
    - DEMO_RESET_MINUTES=1440   # antes: 30
```

### Validación funcional (A3)
Nico ejecutó smoke test manual desde frontend (`demo@flexpqr.co`, clave `FlexDemo1`). Abrió caso `1445ae6e` (Tutela por vulneración — Mario Hernández), editó el borrador, clickeó Enviar, confirmó clave en el FirmaModal. **Evidencia triple de éxito**:

1. **Backend log (15:43:08 UTC)**:
   ```
   Email enviado via SMTP fallback → hernandez.mario@hotmail.com
   POST /api/v2/casos/aprobar-lote 200 OK
   ```

2. **`audit_log_respuestas`**:
   ```
   caso_id: 1445ae6e
   accion:  ENVIADO_LOTE
   metadata: {"metodo_envio": "smtp_fallback",
              "email_destino": "hernandez.mario@hotmail.com",
              "lote_size": 1}
   ```

3. **Frontend**: badge de estado del caso pasó a **RESUELTO**

### Efecto lateral sobre Recovery
**Cero**. Recovery usa `zoho.send_reply()` y nunca entra al fallback Gmail. Las env vars agregadas al backend no cambian el flujo de Recovery.

### Deuda descubierta (registrar)
- **Bug UX FirmaModal**: no aparece notificación visual después de confirmar. Código: `frontend/src/components/ui/firma-modal.tsx` líneas 33-40. Siempre dispara `tipo='exito'` aunque `enviados` sea 0. Fix propuesto: condicionar tipo según `res.data.enviados`. No bloqueante.
- **Kafka Exited hace 5+ días**: containers `pqrs_v2_kafka` y `pqrs_staging_kafka` en estado `Exited (1)`. Backend tiene manejo gracioso (arranca sin producer) pero es deuda pre-existente que nadie había notado.

### Patrón de deploy aplicado
Hotfix aislado **sin rebuild**:
1. Edit quirúrgico del `docker-compose.yml` (2 líneas agregadas + 1 modificada)
2. Validación YAML con `docker compose config --quiet`
3. Recreate con `docker compose up -d --no-deps backend_v2 demo_worker_v2`
4. Verificación de env vars en runtime + logs de arranque
5. Uptime del resto del stack preservado (master_worker, frontend, db, redis, kafka, minio, nginx intactos)

Este patrón es la alternativa segura a rebuildar el backend con disco actual (`c0dab9d`), que arrastraría el drift del régimen SLA sectorial (+227 líneas de endpoints sin migración 14 aplicada) y el bug descubierto del cross-tenant leak en `/casos/borrador/pendientes`.

## 2026-04-13 (deploy nocturno — hotfix aislado)
- hotfix(round-robin): incluir rol `'abogado'` en asignación automática Recovery (`master_worker_outlook.py` +1/−1)
- Branch: `hotfix/round-robin-abogado`, basado en `97f239e` (runtime actual de containers prod)
- Cherry-pick de `453e5ae` para evitar arrastrar el motor SLA sectorial dormido en main
- Merge PR #4 → commit `1106f45` en main. Semánticamente inerte en disco (el fix ya estaba en `c0dab9d` desde el pull del demo_worker previo), pero el hotfix dejó la historia auditablemente aislada
- Solo `master_worker_v2` rebuildeado. Backend, frontend, demo_worker, DB intactos (uptime original preservado)
- Validación previa: `zoho_engine.py` (+67/−13, refactor rate-limit aditivo) y `config.py` (JWT TTL 120→480) verificados como seguros para master_worker — APIs compatibles, sin impacto funcional
- Smoke test DB: 6 usuarios con rol `abogado` activos en Abogados Recovery, 0 con rol `analista` → el fix resuelve un problema real (casos Recovery no se asignaban automáticamente antes)
- Backup DB pre-deploy: `~/backups/backup_pre_sync_20260413_1927.dump` (11 MB)
- DEUDA REGISTRADA: motor SLA sectorial (commits `c26bcee`, `0713f74`) sigue dormido en main sin migración 14 aplicada. Ver `Brain/DEUDAS_PENDIENTES.md`

## 2026-04-13
- feat(demo): auto-envío de respuesta IA en demo_worker (exclusivo tenant demo)
- docs: documentado comportamiento exclusivo en `00_DIRECTIVAS_CLAUDE_CODE.md` y nuevo `demo_worker.md`
- bug pendiente: visualización de `borrador_respuesta` en frontend pestaña Casos (ticket aparte)
