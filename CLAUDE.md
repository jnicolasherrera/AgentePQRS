# AgentePQRS / FlexPQR (PQRS V2)

Sistema multi-tenant de gestión de PQRS (Peticiones/Quejas/Reclamos/Sugerencias) para clientes en Colombia. Clasifica correos entrantes, arma seguimientos y responde por tenant.

> Para procedimientos operativos detallados, usar primero la skill `agentepqrs-flexpqr`.

## Stack
- **Backend:** FastAPI (`backend/app/`), servicio compose `backend_v2`.
- **Workers:** `master_worker_outlook.py` (orquestador), worker `inbound_email`. En prod el master es `master_worker_v2`.
- **DB:** PostgreSQL (`postgres_v2`), con **RLS activo**. El user `pqrs_admin` **bypassa RLS** — usarlo con cuidado en queries de inspección.
- **Infra compose:** postgres_v2, redis_v2, zookeeper_v2, kafka_v2.
- **Inbound:** Microsoft Graph (envío FF) + Outlook. `inbound_outlook_v2.py` en raíz.
- **Schema:** archivos `0X_*.sql` en raíz (schema, RLS, multi-tenant, buzones, plantillas).

## Multi-tenant
- Tabla de clientes = **`clientes_tenant`** (NO `tenants`).
- Firma por tenant: FF usa firma de texto, Recovery usa imagen. (fix en rama `fix/firma-por-tenant`).

## Entornos
- **PROD = OTRA máquina** (VPS São Paulo), distinta de este VPS de Hermes. Acceso por clave SSH ya autorizada (NO SSM). Detalle en skill.
- **Disco prod chico (~29GB, ~84% usado)** → cuidado con VACUUM full / dumps grandes.
- Local: `~/proyectos/AgentePQRS` en el VPS Hermes (este).

## Regla de oro de desarrollo
**TODO cambio de código lo hace Claude Code CLI, no la API.** Auth OAuth con la suscripción Claude Max (sin ANTHROPIC_API_KEY).

## Pitfalls conocidos
- Loop infinito de seguimientos → ya fix en prod (PR #20/#21).
- RLS: si una query "no devuelve nada", confirmar si el rol tiene bypass o está filtrado por tenant.
- No correr migraciones destructivas sin backup por el disco chico.

## Remoto
`git@github.com:jnicolasherrera/AgentePQRS.git` (SSH, NO tokens HTTPS).
