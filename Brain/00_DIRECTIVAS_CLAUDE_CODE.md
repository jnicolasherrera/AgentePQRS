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
