# 🔐 Hardening AWS — Sprint Abril 2026 (15-16 abril)

> **Contexto**: cierre del sprint de hardening iniciado tras la auditoría de Dante Anelli (14-abril). Objetivo inmediato: postura mínima defendible en AWS antes de continuar conversaciones con Bancolombia. Este documento es **forensic**: registra exactamente qué se hizo, qué problemas aparecieron, cómo se resolvieron y qué quedó pendiente como deuda técnica.
>
> **Estado al cierre (16-abril-2026)**: Quick Wins 1-4 completados. Deudas técnicas para Bancolombia registradas en `DEUDAS_PENDIENTES.md`.

---

## 📋 Identificación de la cuenta

| Dato | Valor |
|---|---|
| AWS Account | `336457597619` |
| Organización | Flexfintech S.A.S. |
| Región primaria | `sa-east-1` (São Paulo) |
| EC2 producción | `18.228.54.9` (t3.large, instance `i-08513f12ecd61947f`) |
| EC2 staging | `15.229.114.148` (t3.small, instance `i-051ace2a46910c789`) |

---

## ✅ Quick Wins completados

### QW1 — MFA en root AWS

**Estado al cierre**: ✅ Configurado (Authapp, marzo 2026). Confirmado.

**Postura correcta verificada**:
- Root tiene **cero access keys activas**. Nunca se crearon access keys para root.
- MFA virtual vinculado a Authapp del teléfono de Nico.

**Regla permanente**: nunca generar access keys para la cuenta root. Todo acceso programático debe pasar por usuarios IAM con scoped permissions.

---

### QW2 — IAM user separado para deploys

**Estado al cierre**: ✅ Creado y configurado.

**Identidad creada**:
```
User:     flexpqr-deploy
ARN:      arn:aws:iam::336457597619:user/flexpqr-deploy
Tags:     Project=FlexPQR, Env=Production
```

**Policies attached** (AWS-managed, primera pasada — ver deuda técnica DT-3):
- `AmazonEC2FullAccess`
- `AmazonS3FullAccess`
- `CloudWatchFullAccess`

**Policies NO attached (por diseño, least privilege estricto)**:
- Sin permisos IAM (no puede crear/modificar usuarios ni policies)
- Sin permisos CloudTrail write (no puede desactivar el trail ni borrar logs)
- Sin permisos de gestión de cuenta (billing, organizations)

**Configuración CLI**:
```bash
aws configure --profile flexpqr-deploy
# Región: sa-east-1
# Output: json
aws sts get-caller-identity --profile flexpqr-deploy
# → confirma ARN arn:aws:iam::336457597619:user/flexpqr-deploy
```

**Regla operacional**: toda gestión de IAM/CloudTrail/policies de cuenta se hace desde consola web con la sesión root (con MFA). El CLI con profile `flexpqr-deploy` se usa solo para operaciones EC2/S3/CloudWatch.

---

### QW3 — CloudTrail multi-región a S3

**Estado al cierre**: ✅ Creado, validación SHA-256 activa, logs llegando al bucket correcto cada ~5 minutos.

**Bucket S3 dedicado**:
```
Nombre:       flexpqr-cloudtrail-logs
Región:       sa-east-1
```

Configuración del bucket:
- Public access bloqueado (4 flags activas)
- Versionado: habilitado
- Lifecycle:
  - Transición a Glacier a los **90 días**
  - Expiración a los **2555 días (7 años)**
- Bucket policy con condición `AWS:SourceArn` apuntando al ARN exacto del trail (previene confused-deputy attack)

**Trail creado**:
```
Nombre:              flexpqr-trail
ARN:                 arn:aws:cloudtrail:sa-east-1:336457597619:trail/flexpqr-trail
Multi-región:        Sí
Log file validation: Habilitado (SHA-256 digest cada hora)
Management events:   Read + Write
Data events:         No habilitados (no aplican aún)
SSE-KMS:             No habilitado (ver deuda técnica DT-1)
```

**Verificación end-to-end ejecutada**:
1. Llegada de logs al bucket confirmada (archivos `.json.gz` cada ~5 minutos).
2. Digest files `.json.gz` con SHA-256 llegando cada hora (validación anti-tampering).
3. Consulta de eventos desde consola CloudTrail → eventos de sesión root y `flexpqr-deploy` visibles.

---

### QW4 — GuardDuty

**Estado al cierre**: ✅ Activo en `sa-east-1`, trial 30 días.

**Configuración aplicada**:
- Región: `sa-east-1` únicamente (ver deuda técnica DT-2 para multi-región)
- Runtime Monitoring: **No activado** (no necesario para Docker Compose sobre EC2 — GuardDuty Runtime está orientado a EKS/ECS/EC2 con agent)
- Detectors habilitados: default set (análisis de CloudTrail, VPC Flow Logs, DNS logs)

**Próximos pasos automáticos**: GuardDuty empieza a emitir findings cuando detecta anomalías (accesos desde geografías inusuales, comunicación con IPs conocidas maliciosas, escalamiento de privilegios sospechoso, etc.).

---

## 🚨 Problemas encontrados durante el sprint y cómo se resolvieron

### Problema 1 — Variables de entorno AWS_* pisando el `--profile`

**Síntoma**: `aws sts get-caller-identity --profile flexpqr-deploy` retornaba la identidad de la cuenta equivocada o fallaba con credenciales inválidas, incluso después de `aws configure --profile flexpqr-deploy` ejecutado correctamente.

**Causa raíz**: el shell de WSL tenía variables de entorno viejas (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) de sesiones previas. Según el orden de precedencia del AWS CLI, **las env vars ganan al `--profile`**.

**Fix aplicado**:
```bash
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN
unset AWS_DEFAULT_REGION
unset AWS_PROFILE
aws sts get-caller-identity --profile flexpqr-deploy  # ahora sí
```

**Lección permanente**: antes de debuggear cualquier problema de credenciales AWS, correr `env | grep AWS_` y limpiar con `unset` lo que sobre.

---

### Problema 2 — Access Key ID y Secret idénticos (copy-paste error)

**Síntoma**: al configurar el profile, el CLI aceptaba los valores pero después fallaba con `InvalidClientTokenId`.

**Causa raíz**: durante el copy-paste de la Access Key generada en la consola AWS, se copió el mismo string en ambos campos (ID y Secret).

**Fix aplicado**: regenerar la Access Key en consola (deshabilitar la anterior), copiar ID y Secret por separado con atención, y repetir `aws configure --profile flexpqr-deploy`.

**Lección permanente**: después de `aws configure`, siempre verificar con `aws sts get-caller-identity --profile <nombre>` antes de continuar. Si falla ahí, el problema es de credenciales, no de permisos.

---

### Problema 3 — Credenciales de consola confundidas con Access Keys

**Síntoma**: se intentó configurar el profile `flexpqr-deploy` con el email y password de login a la consola AWS.

**Causa raíz**: confusión conceptual entre:
- **Credenciales de consola** (email + password + MFA): para acceder al panel web `console.aws.amazon.com`.
- **Access Keys** (Access Key ID + Secret Access Key): para acceder al API vía CLI/SDK.

**Son dos cosas completamente distintas**. Un IAM user puede tener ambas, solo una, o ninguna — se gestionan por separado en la pestaña "Security credentials" del user.

**Lección permanente**:
- Consola web → email + password + MFA.
- CLI/SDK → Access Key ID (empieza con `AKIA...`) + Secret Access Key (string largo random).
- Si el string que te da AWS empieza con `AKIA` es una Access Key ID; si es un email no lo es.

---

### Problema 4 — AWS creó un bucket CloudTrail auto-generado

**Síntoma**: durante la creación del trail vía consola, AWS creó automáticamente el bucket `aws-cloudtrail-logs-336457597619-711f0891` en lugar de usar el bucket `flexpqr-cloudtrail-logs` que ya habíamos creado manualmente.

**Causa raíz**: el wizard de CloudTrail en la consola tiene por defecto la opción "Create a new S3 bucket" seleccionada. Hay que scrollear y cambiar explícitamente a "Use existing S3 bucket".

**Fix aplicado**:
1. Editar el trail recién creado y apuntarlo al bucket correcto (`flexpqr-cloudtrail-logs`).
2. Activar manualmente "Log file validation" en la edición (también estaba desactivada por default).
3. Eliminar el bucket auto-generado (estaba vacío, seguro borrarlo).
4. Verificar que los logs siguientes aparecen en el bucket correcto.

**Lección permanente**: en cualquier wizard de AWS que cree recursos, leer cada default antes de clickear "Create". Los defaults del wizard CloudTrail no son los que queremos:
- Crea bucket nuevo → queremos usar uno existente.
- Log file validation OFF → queremos ON.
- SSE-S3 → queremos SSE-KMS (pendiente, ver DT-1).

---

### Problema 5 — API de S3 lifecycle exige `ID` con mayúsculas

**Síntoma**: al intentar aplicar la policy de lifecycle del bucket via CLI, fallaba con `MalformedXML: Missing required field: ID`.

**Causa raíz**: el JSON del lifecycle usa `"Id"` en minúsculas por convención de AWS, pero la API específica de S3 lifecycle exige `"ID"` en mayúsculas. Es inconsistencia de la API dentro del mismo AWS.

**Fix aplicado**: cambiar `"Id"` a `"ID"` en el JSON del lifecycle policy y reintentar.

**Lección permanente**: si un comando AWS CLI falla con `MalformedXML` o `Missing required field`, revisar casing del JSON antes de asumir otros problemas.

---

## 🔑 Credenciales expuestas durante esta sesión — ROTAR

Durante la sesión de hardening aparecieron logs que mostraron credenciales activas de servicios en producción. **Hay que rotarlas como tarea pendiente**. Registradas también en `DEUDAS_PENDIENTES.md` bajo "Deudas hardening AWS abril 2026".

| Credencial | Servicio | Acción requerida |
|---|---|---|
| App Password Gmail de `democlasificador@gmail.com` | Gmail SMTP para demo tenant | Revocar en Google Account → generar nueva → actualizar `DEMO_GMAIL_PASSWORD` en docker-compose.yml de producción |
| Password Redis del container `pqrs_v2_redis` | Cache de sesiones y SSE | Cambiar en `REDIS_PASSWORD` env var → recreate container + backend → validar que SSE sigue funcionando |
| Credenciales MinIO (`adminminio/adminpassword`) | Object storage de adjuntos | Rotar a credenciales random largas → actualizar `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` + backend → validar que los uploads siguen funcionando |

**Patrón de rotación seguro** (sin downtime):
1. Generar credencial nueva en un gestor de secretos (o random con `openssl rand -base64 32`).
2. Actualizar docker-compose.yml con la nueva credencial.
3. `docker compose up -d --no-deps <servicio_dueño>` (ej. redis).
4. `docker compose up -d --no-deps <servicios_que_consumen>` (ej. backend_v2, master_worker_v2, demo_worker_v2).
5. Smoke test funcional.
6. Si hay problema → rollback del compose y recreate. Si no → confirmar rotación en `CHANGELOG.md`.

---

## ⚠️ Hallazgo CRÍTICO — Divergencia `docker-compose.yml` local vs producción

Durante la revisión del compose de producción se identificaron diferencias **importantes** respecto al compose local. **Nunca copiar el compose local a producción sin diff previo** — reabre los 9 puertos cerrados por Dante el 14-abril.

### Tabla comparativa

| Servicio | Compose local | Compose producción |
|---|---|---|
| Postgres | `"5434:5432"` (abierto) | `"127.0.0.1:5434:5432"` (bind local only) |
| Redis | `"6381:6379"` (abierto) | `"127.0.0.1:6381:6379"` |
| Backend v2 | `"8001:8000"` (abierto) | `"127.0.0.1:8001:8000"` |
| Frontend v2 | `"3002:3000"` (abierto) | `"127.0.0.1:3002:3000"` |
| `DEMO_GMAIL_USER` | No presente | `democlasificador@gmail.com` |
| `DEMO_GMAIL_PASSWORD` | No presente | `${DEMO_GMAIL_PASSWORD:-}` |
| `DEMO_RESET_MINUTES` | `30` | `1440` |

### Por qué importa

Los 9 puertos cerrados el 14-abril (auditoría de Dante) son uno de los hallazgos más visibles del hardening. Si alguien hace `scp docker-compose.yml server:~/PQRS_V2/` sin revisar el diff, **los puertos se reabren silenciosamente en el próximo `docker compose up`** y el servidor queda expuesto a escaneos externos directos a Postgres/Redis/Backend.

### Guardrail propuesto (ver deuda DT-8 en `DEUDAS_PENDIENTES.md`)

Script `deploy/verify_compose_diff.sh` que:
1. Lee `docker-compose.yml` local y el de producción (via SSH).
2. Aborta el deploy si detecta:
   - Líneas con puertos que no empiezan por `127.0.0.1:`.
   - Env vars de producción que faltan en local (indicaría overwrite destructivo).
3. Imprime el diff legible y exige confirmación `yes` explícita antes de continuar.

Como workaround inmediato: `README.DEPLOY.md` en la raíz del repo con el diff esperado documentado y la regla "NO sincronizar compose entre entornos sin diff aprobado".

---

## 📊 Postura de seguridad AWS al cierre del sprint

| Control | Antes (14-abril) | Después (16-abril) |
|---|---|---|
| MFA en root | ✅ | ✅ (sin cambio) |
| Access keys en root | ✅ cero | ✅ cero (sin cambio) |
| IAM user separado para deploys | ❌ | ✅ `flexpqr-deploy` |
| CloudTrail | ❌ | ✅ multi-región, SHA-256, 7 años retención |
| GuardDuty | ❌ | ✅ `sa-east-1` (trial 30 días) |
| Alertamiento sobre findings | ❌ | ❌ (deuda) |
| SSE-KMS en CloudTrail | ❌ | ❌ (deuda DT-1) |
| GuardDuty multi-región | ❌ | ❌ (deuda DT-2) |
| Policies least-privilege custom | ❌ (usa `*FullAccess`) | ❌ (deuda DT-3) |
| Secrets manager en lugar de `.env` | ❌ | ❌ (deuda pre-existente, Punto 10 Banco Popular) |
| Bus factor >1 | ❌ | ❌ (deuda crítica, Punto 10 Banco Popular) |

**Lectura comercial**: pasamos de "cuenta AWS sin ningún control documentado" a "postura mínima defendible". **No es suficiente para cerrar con Bancolombia**, pero sí para sostener una conversación técnica sin bochornos. El camino a Bancolombia sigue requiriendo cerrar los 8 blockers críticos del Punto-por-Punto del `BANCO_POPULAR_ANALISIS_SEGURIDAD.md` (SSO, SIEM, secrets manager, segundo operador, etc.).

---

## 🔗 Referencias cruzadas

- Auditoría de seguridad original: `BANCO_POPULAR_ANALISIS_SEGURIDAD.md` (Punto 4 IAM, Punto 7 Conectividad, Punto 8 Logs, Punto 10 SDLC).
- Deudas técnicas registradas: `DEUDAS_PENDIENTES.md` sección "2026-04-15/16 — Deudas hardening AWS".
- Entrada histórica de cambios: `CHANGELOG.md` entradas 2026-04-15 y 2026-04-16.
- Decisión Compose vs K8s (implica decisiones de orquestador de secretos): `DECISION_COMPOSE_VS_K8S.md`.
- Monitoreo CloudWatch preexistente: `infra/cloudwatch_monitoring.md`.
- Commit Brain del cierre del sprint: `0307fa1` en `develop` (pendiente de push al remoto).

---

**Última actualización**: 2026-04-16
**Próxima revisión**: cuando se aborde alguna de las deudas DT-1 a DT-8, o cuando un auditor externo pida evidencia del trail.
