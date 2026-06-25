# AgentePQRS / FlexPQR

Plataforma SaaS **multi-tenant** de gestión de **PQRS** (Peticiones, Quejas, Reclamos, Sugerencias) y **Tutelas** para clientes en Colombia (Flex Fintech SAS). Clasifica correos entrantes con IA, arma seguimientos y genera respuestas por tenant.

> Para procedimientos operativos detallados (deploys, RBAC, infra), ver la documentación en [`docs/`](docs/).

---

## Stack

| Capa | Tecnología | Ubicación |
|------|-----------|-----------|
| **Backend** | FastAPI (monolito modular) | [`backend/`](backend/), [`aequitas_backend/`](aequitas_backend/) |
| **Frontend** | Next.js (React) | [`frontend/`](frontend/) |
| **Base de datos** | PostgreSQL + Row-Level Security (RLS) por tenant | [`db/schema/`](db/schema/) |
| **Workers** | `master_worker_outlook.py` (orquestador de ingesta) | [`backend/`](backend/), [`workers/`](workers/) |
| **Infra** | Docker Compose, Redis, MinIO, nginx | [`docker-compose.yml`](docker-compose.yml) |
| **Ingesta de correo** | Microsoft Graph (Outlook/M365) + Zoho | [`scripts/inbound_outlook_v2.py`](scripts/inbound_outlook_v2.py) |

---

## Estructura del repositorio

```
.
├── backend/              # API FastAPI + workers + servicios
├── aequitas_backend/     # Backend auxiliar
├── frontend/             # App Next.js
├── pqrs-landing/         # Landing page
├── db/
│   └── schema/           # Esquemas SQL versionados (01..08)
├── docs/
│   ├── arquitectura/     # Diseño y arquitectura del sistema
│   ├── setup/            # Guías de configuración (MCP, skills, entorno)
│   ├── agentes/          # Notas de tooling de agentes (MCP servers)
│   └── superpowers/      # Specs y planes (flujo SDD)
│       ├── specs/        #   El "qué": diseño de cada feature
│       └── plans/        #   El "cómo": tareas ejecutables
├── scripts/              # Scripts operativos (init DB, seed, ingesta)
├── nginx/                # Configuración del reverse proxy
├── Brain/                # Bitácoras de sesión, auditorías, deudas técnicas
├── docker-compose.yml            # Stack de producción
├── docker-compose.staging.yml    # Stack de staging
└── CLAUDE.md             # Contexto para el asistente de código
```

---

## Multi-tenant y seguridad

- **Aislamiento por tenant:** Row-Level Security de PostgreSQL. El backend corre como rol `pqrs_backend` (sin BYPASSRLS) → RLS activo y filtrando.
- **Tabla de clientes:** `clientes_tenant` (cada fila = un tenant).
- **Modelo de roles:** `admin` / `super_admin` / `coordinador` / `auditor` ven todo el tenant; `abogado` / `analista` ven solo su cartera (`asignado_a`).
- **Firma por tenant:** resuelta en `backend/app/services/firma_engine.py` (cada cliente firma con su identidad).

---

## Desarrollo y deploy

### Flujo SDD (Spec-Driven Development)
Los cambios grandes/delicados siguen: **dimensionar → spec → plan → implementar → validar**. Specs en [`docs/superpowers/specs/`](docs/superpowers/specs/), planes en [`docs/superpowers/plans/`](docs/superpowers/plans/).

### Entornos
- **Producción** y **staging** corren en VPS independientes (AWS São Paulo).
- El despliegue a producción es **quirúrgico** (archivos puntuales + backup), no `git pull`. Detalle en la documentación de operaciones.

### Inicializar staging
```bash
bash scripts/init_staging_db.sh
```

---

## Documentación

- **Arquitectura:** [`docs/arquitectura/PQRS_V2_ARCHITECTURE.md`](docs/arquitectura/PQRS_V2_ARCHITECTURE.md)
- **Configuración (MCP, skills, entorno):** [`docs/setup/`](docs/setup/)
- **Bitácoras, auditorías y deudas técnicas:** [`Brain/`](Brain/)
