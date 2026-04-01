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
