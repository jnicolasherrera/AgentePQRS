# Brain Changelog

## 2026-04-16 — Hardening AWS sprint cierre (QW3 CloudTrail + QW4 GuardDuty)

### Contexto
Continuación del sprint de hardening iniciado el 14-abril tras la auditoría de Dante Anelli. Objetivo del día: completar los Quick Wins 3 y 4 del plan AWS para alcanzar postura mínima defendible antes de próximas conversaciones con Bancolombia.

### QW3 — CloudTrail multi-región a S3 ✅

Bucket S3 dedicado creado con public access bloqueado, versionado activo, lifecycle (Glacier 90d, expiración 2555d), y bucket policy con condición `AWS:SourceArn` (anti confused-deputy):

```
Bucket: flexpqr-cloudtrail-logs
Región: sa-east-1
```

Trail creado con validación SHA-256 activa:

```
Nombre: flexpqr-trail
ARN:    arn:aws:cloudtrail:sa-east-1:336457597619:trail/flexpqr-trail
Multi-región: Sí
Log file validation: Habilitado
Management events: Read + Write
SSE-KMS: No habilitado (deuda DT-1)
```

Verificación end-to-end: logs llegando al bucket cada ~5 minutos, digest files SHA-256 cada hora, consultas desde consola CloudTrail funcionando.

### Incidente durante la creación del trail

La consola AWS creó por default un bucket auto-generado (`aws-cloudtrail-logs-336457597619-711f0891`) en lugar de usar el bucket `flexpqr-cloudtrail-logs` preexistente. Se editó el trail para apuntarlo al bucket correcto, se activó manualmente Log file validation (también off por default), se eliminó el bucket auto-creado. Lección: en wizards AWS, leer cada default antes de clickear Create.

### QW4 — GuardDuty ✅

Activado en `sa-east-1` desde consola web, trial 30 días gratis. Runtime Monitoring no activado (no aplica a Docker Compose sobre EC2; GuardDuty Runtime está orientado a EKS/ECS con agent).

### Decisión de permisos

`flexpqr-deploy` mantiene least privilege estricto: sin permisos IAM, sin CloudTrail write. La gestión de IAM/CloudTrail/policies de cuenta se hace desde consola web con sesión root (con MFA). El CLI con profile `flexpqr-deploy` se usa solo para operaciones EC2/S3/CloudWatch.

### Deudas registradas al cierre

- DT-1: SSE-KMS en CloudTrail (CMK dedicada)
- DT-2: GuardDuty multi-región (us-east-1, us-west-2, eu-west-1, ap-southeast-1)
- DT-3: Migrar `*FullAccess` a policies custom mínimas
- DT-4: AWS IAM Identity Center cuando sumen Dante/Martín
- DT-5: Rotación automática de access keys (cron + script trimestral)
- DT-6: Retención CloudTrail 10 años si Bancolombia lo pide (ajustar 2555d → 3650d)
- DT-7: Push commit Brain `0307fa1` al remoto (pendiente desde el 14-abril)
- DT-8: Guardrail docker-compose prod vs local (script de diff pre-deploy)

Ver `DEUDAS_PENDIENTES.md` sección "2026-04-15/16 — Deudas hardening AWS" y documento detallado `fixes/HARDENING_AWS_ABRIL_2026.md`.

### Credenciales expuestas durante la sesión — rotar

- App Password Gmail de `democlasificador@gmail.com` (revocar + regenerar)
- Password Redis de `pqrs_v2_redis` (rotar)
- Credenciales MinIO `adminminio/adminpassword` (rotar aunque ya eran conocidas)

### Hallazgo colateral: divergencia `docker-compose.yml` local vs prod

Se detectaron diferencias importantes entre el compose local y el de producción. El de producción tiene todos los puertos críticos bindeados a `127.0.0.1` (fruto del trabajo de Dante del 14-abril), mientras que el local los expone a `0.0.0.0`. Además, el de producción tiene env vars Gmail (`DEMO_GMAIL_USER`, `DEMO_GMAIL_PASSWORD`) y `DEMO_RESET_MINUTES=1440` que el local no tiene.

**Regla inmutable**: nunca copiar el compose local a producción sin diff previo aprobado. Reabriría los 9 puertos cerrados y borraría env vars que se agregaron para fixes específicos.

---

## 2026-04-15 — Hardening AWS sprint inicio (QW1 MFA + QW2 IAM user)

### Contexto
Continuación del sprint iniciado por Dante Anelli (14-abril: 13 puntos de auditoría, 9 puertos cerrados a 127.0.0.1). Objetivo: alcanzar postura mínima defendible en AWS.

### QW1 — MFA en root AWS ✅
Ya estaba configurado (Authapp, marzo 2026). Confirmado: root con cero access keys activas. Postura correcta verificada.

### QW2 — IAM user separado para deploys ✅

Usuario creado:
```
Nombre: flexpqr-deploy
ARN:    arn:aws:iam::336457597619:user/flexpqr-deploy
Tags:   Project=FlexPQR, Env=Production
```

Policies attached (primera pasada, deuda técnica DT-3 para migrar a custom):
- AmazonEC2FullAccess
- AmazonS3FullAccess
- CloudWatchFullAccess

Access Key generada para CLI, profile configurado con `aws configure --profile flexpqr-deploy` (región `sa-east-1`). Verificado con `aws sts get-caller-identity`.

### Problemas encontrados y resueltos

1. **Variables de entorno AWS_* viejas pisaban el `--profile`**: el shell de WSL tenía `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` de sesiones previas; las env vars ganan al `--profile` en la precedencia del AWS CLI. Fix: `unset AWS_*` antes de usar el profile.

2. **Access Key ID y Secret eran el mismo string**: error de copy-paste al configurar el profile. Fix: regenerar la Access Key en consola, copiar ID y Secret por separado, repetir `aws configure`.

3. **Credenciales de consola (email+password) confundidas con Access Keys**: conceptualmente son dos cosas distintas. Consola web → email+password+MFA. CLI/SDK → Access Key ID (empieza con `AKIA`) + Secret. Aclarado.

### Lecciones técnicas permanentes

- Nunca crear access keys para root. Todo acceso programático vía IAM users con scoped permissions.
- Antes de debuggear credenciales AWS, correr `env | grep AWS_` y limpiar con `unset`.
- Después de `aws configure`, siempre verificar con `aws sts get-caller-identity --profile <nombre>`.
- `AKIA...` = Access Key ID. Un email no lo es.

Ver documento detallado: `fixes/HARDENING_AWS_ABRIL_2026.md`.

---

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
