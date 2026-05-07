# Directivas Claude Code — FlexPQR / AgentePQRS

## 1. PROYECTO
- Nombre: FlexPQR (AgentePQRS)
- Stack: FastAPI backend, React frontend, PostgreSQL (Supabase), Redis, Kafka, Docker
- Repo: /mnt/f/proyectos/AgentePQRS

## 2. INFRAESTRUCTURA

### Servidores

| Entorno | IP | Tipo | Usuario SSH | Clave |
|---------|-----|------|-------------|-------|
| **Producción** | `18.228.54.9` | t3.large | ubuntu | `~/.ssh/flexpqr-prod` (WSL) |
| **Staging** | `15.229.114.148` | t3.small | ubuntu | `~/.ssh/flexpqr-staging` (WSL) |

### Conexión SSH

```bash
# Producción
ssh -i ~/.ssh/flexpqr-prod ubuntu@18.228.54.9

# Staging
ssh -i ~/.ssh/flexpqr-staging ubuntu@15.229.114.148
```

> Máquina de desarrollo reformateada el 01/04/2026.
> Claves ED25519 regeneradas y almacenadas en WSL (~/.ssh/).
> Claves anteriores (.pem) ya no existen.

## 3. HALLAZGOS Y ACCIONES

### 01/04/2026 — Stack staging apagado en producción
- Se detectaron 5 contenedores `pqrs_staging_*` corriendo en el servidor de producción (18.228.54.9)
- Contenedores apagados (`docker stop`, no eliminados): frontend, backend, redis, db, minio
- **Staging real vive exclusivamente en 15.229.114.148**
- El directorio `~/PQRS_V2_STAGING/` permanece en prod pero sus contenedores están detenidos

## 4. REGLAS ANTI-502 NGINX

1. Nginx cachea IPs internas al arrancar.
2. Si hay 502: `docker compose restart nginx_ssl` (fix inmediato).
3. Fix permanente: `resolver 127.0.0.11 valid=30s` + variables `$upstream_*`.
4. El `nginx.conf` actual ya tiene el fix permanente aplicado.

## 5. REGLA ROL ABOGADO (LEGACY)

El tenant arcsas.com.co usa `rol='abogado'` en lugar de `rol='analista'`.
**TODA** query que filtre por rol de operador **DEBE** incluir ambos:

```sql
AND u.rol IN ('analista', 'abogado')
```

**Nunca** usar: `AND u.rol = 'analista'` solo.

Aplica a: round-robin, RLS policies, filtros de bandeja, enviados, cualquier query de asignación.

## 6. REGLA MULTI-AGENTE OBLIGATORIA

TODO prompt de Claude Code con más de un componente DEBE:
1. Declarar el plan de agentes al inicio (nombrarlos)
2. Usar Task() para ejecutar agentes en paralelo
3. El agente de infra/deploy espera siempre al resto

Estructura mínima:
- Agente DB: migraciones y cambios de esquema
- Agente Backend: endpoints y lógica de negocio
- Agente Frontend: componentes y UI
- Agente QA: scripts de verificación
- Agente Infra: deploy (siempre último)

## 7. STAGING (actualizado 8-abril-2026)

| Campo | Valor |
|-------|-------|
| IP | 15.229.114.148 |
| Tipo | t3.small, sa-east-1 |
| Acceso | `ssh -i ~/.ssh/flexpqr-staging ubuntu@15.229.114.148` |
| URL | https://15.229.114.148 (cert self-signed — aceptar warning) |
| SSL | Certificados self-signed generados 8-abril-2026 |

Usuarios de prueba staging:
- `demo@sistemapqrs.co` / `demo1234` (admin)
- `admin@flexfintech.com` / `superpassword123` (admin)

> NOTA: No tiene dominio propio — solo acceso por IP.
> Si nginx crashea: verificar que existan los 3 pares de cert/key en nginx/certs/.


---

## Comportamiento exclusivo del demo_worker

El `demo_worker.py` implementa un flujo de **auto-envío de respuesta IA** que es exclusivo del tenant demo y NO debe replicarse a otros tenants sin pasar por aprobación humana.

### Flujo demo (4 pasos)
1. Ingesta del email vía Gmail IMAP (`fetch_unread_gmail`)
2. Acuse de recibo vía Gmail SMTP (`send_acuse_demo`)
3. Generación del borrador IA (`generar_borrador_para_caso`)
4. **Auto-envío del borrador** vía Gmail SMTP (`send_respuesta_ia_demo`) → marca caso como `CERRADO`/`ENVIADO`

### Por qué es exclusivo
- Recovery y demás tenants productivos están sujetos a SLAs regulatorios (Ley 1755/2015, SFC) que exigen aprobación humana antes de enviar respuestas legales.
- El auto-envío demo existe únicamente para mostrar el ciclo end-to-end completo en demos comerciales sin requerir un humano aprobando en tiempo real.
- Está protegido por el hecho de que únicamente corre en el contenedor `demo_worker` (tenant `DEMO_TENANT_ID = 11111111-1111-1111-1111-111111111111`). `master_worker_outlook.py` no tiene este path.

### Auditoría
Cada envío auto se registra en `audit_log_respuestas` con `accion='ENVIADO_AUTO_DEMO'` y `metadata.auto_aprobado_por='demo_worker'` para trazabilidad. `aprobado_por` queda en NULL (no hay usuario humano).

### ⚠️ Regla
NUNCA copiar este patrón a `master_worker_outlook.py` ni a ningún flujo de tenant productivo sin pasar por aprobación regulatoria explícita.


---

## 3.5 Regla anti-drift de branches

Antes de cualquier PR `develop → main` (incluso si es para un fix urgente), ejecutar:

```bash
git fetch origin
git log staging..develop --oneline
git diff staging..develop --stat
```

Esto muestra qué otros commits van a viajar de polizón en el merge. Si hay más de 1-2 commits relacionados al fix, **STOP** y evaluar:

1. ¿Todos esos commits deberían ir a producción ahora?
2. ¿Alguno depende de migraciones de DB no aplicadas?
3. ¿Alguno introduce features grandes sin testing en staging?

Si la respuesta a 2 o 3 es sí → **NO mergear develop→main**. Crear branch `hotfix/descripcion` desde el commit del runtime actual de prod (ver `git log` en server EC2), cherry-pickear solo el fix, abrir PR aislado a main.

### Verificación adicional antes del rebuild de cualquier container

Aunque el cherry-pick esté aislado, al rebuildar un container el Dockerfile copia **todo el contexto** del disco del server, que puede incluir archivos de otros commits no relacionados. Antes del rebuild, verificar imports transitivos del servicio a rebuildar contra la lista de archivos que cambiaron entre el runtime actual y el commit en disco:

```bash
# Módulos cambiados en el área crítica
git diff <runtime_commit>..<disco_commit> --stat -- backend/app/core/ backend/app/services/

# Imports directos del servicio (ej. master_worker_outlook.py)
grep -nE "^(from|import) app\." backend/<servicio>.py

# Cruce: si algún módulo importado aparece en la lista de cambiados, revisar el diff completo
git diff <runtime_commit>..<disco_commit> -- backend/app/services/<modulo>.py
```

Si hay intersección, leer el diff y validar: (a) APIs compatibles, (b) cambios aditivos/defensivos, (c) sin nuevos imports o símbolos removidos, (d) env vars nuevas con defaults seguros.

### Aprendizaje histórico

El **2026-04-13** esta regla se usó por primera vez. El contexto:

1. En la mañana mergeamos `develop → main` (PR #3) para desplegar un fix del `demo_worker`. El merge arrastró 4 commits de polizón, incluyendo el motor SLA sectorial completo (+227 líneas de endpoints admin en `admin.py`) que dependía de una migración de DB (`14_regimen_sectorial.sql`) que **nunca corrió** contra `pqrs_v2`. La tabla `festivos_colombia`, la tabla `sla_regimen_config` y la columna `clientes_tenant.regimen_sla` no existen en producción.

2. Rebuildar `backend` con ese código habría expuesto 4 endpoints admin que fallan con `500 column "regimen_sla" does not exist` al primer click.

3. Por la tarde, cuando se necesitó desplegar un segundo fix (`453e5ae` round-robin rol abogado), se creó el branch `hotfix/round-robin-abogado` desde `97f239e` (el runtime real de los containers, no el disco), se cherry-pickeó solo el fix, se mergeó a main via PR #4 y se rebuildó exclusivamente `master_worker_v2`. El backend quedó intacto con código viejo + endpoints admin sin exponer.

4. Durante la validación previa al rebuild se descubrió que el pull no traía cambios de archivo netos (el contenido del fix ya estaba en `c0dab9d` desde el pull del deploy matutino). Esto reveló la necesidad de validar imports transitivos del servicio a rebuildar contra el diff `runtime..disco`, no solo contra el commit del hotfix.

Ver `Brain/CHANGELOG.md` entrada de esa fecha y `Brain/DEUDAS_PENDIENTES.md` para el plan de deploy futuro del motor SLA sectorial.
