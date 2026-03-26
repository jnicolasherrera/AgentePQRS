# Equipos de Agentes y Orquestacion -- FlexPQR

## Estrategia Multi-Agente

FlexPQR esta disenado para ser desarrollado y mantenido con asistencia de agentes IA especializados. Cada agente tiene un dominio de responsabilidad claro.

## Agentes por Dominio

### Agente Backend (FastAPI + Workers)
- **Responsabilidad:** Rutas API, servicios de negocio, workers Kafka
- **Skills requeridos:** event-driven-architect, postgres-rls-expert
- **MCPs:** mcp-postgres-v2 para validar queries
- **Archivos clave:** `backend/app/`

### Agente Frontend (Next.js)
- **Responsabilidad:** UI/UX del dashboard, estado global, SSE
- **Skills requeridos:** react-performance-master
- **MCPs:** mcp-context7 para docs de Next.js/React
- **Archivos clave:** `frontend/src/`

### Agente Infra (Docker + Nginx)
- **Responsabilidad:** Docker Compose, Nginx, SSL, despliegue
- **Skills requeridos:** kubernetes-cloud-engineer
- **Archivos clave:** `docker-compose.yml`, `nginx/`, `Dockerfile`s

### Agente IA (Clasificacion + Borradores)
- **Responsabilidad:** Scoring engine, integracion Anthropic, plantillas
- **Skills requeridos:** event-driven-architect (para Kafka consumer)
- **Archivos clave:** `backend/app/services/ai_*.py`, `scoring_engine.py`, `plantilla_engine.py`

### Agente Data (PostgreSQL + Migraciones)
- **Responsabilidad:** Esquema SQL, RLS, indices, triggers
- **Skills requeridos:** postgres-rls-expert
- **MCPs:** mcp-postgres-v2
- **Archivos clave:** `*.sql`, `backend/app/core/models.py`

## Flujo de Orquestacion

1. **Tarea ingresa** al agente principal (coordinador)
2. Coordinador **clasifica el dominio** (backend, frontend, infra, IA, data)
3. Se carga el **Skill relevante** para el dominio
4. Se conectan los **MCPs necesarios** (postgres, context7, github)
5. Agente ejecuta con acceso al Brain/ como contexto persistente
6. Resultado se **valida** contra el Manifiesto de Entrega Senior (10_MANIFIESTO)

## Reglas de Coordinacion

- Un agente no debe modificar archivos fuera de su dominio sin consultar
- Cambios en esquema SQL requieren migracion numerada nueva
- Cambios en docker-compose.yml requieren verificar que todos los servicios arranquen
- Todo feature debe pasar por los criterios del Manifiesto de Entrega
