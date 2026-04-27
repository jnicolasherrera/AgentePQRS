---
tags:
  - brain/maestro
---

# Arquitectura Maestra -- FlexPQR V2

## Vision General

FlexPQR V2 es un sistema enterprise para procesamiento masivo de PQRS (>1M/mes), construido sobre una arquitectura Event-Driven con clasificacion hibrida de IA y multitenancy estricto a nivel de base de datos.

## 7 Pilares Fundamentales

### 1. Backend (Motor Transaccional & Ingesta)
- **Framework:** FastAPI asincrono con asyncpg (no ORM para queries criticas)
- **Patron:** Monolito modular con routers separados por dominio
- **Rate Limiting:** SlowAPI (10 req/min en login)
- **CORS:** Configurado para localhost:3000, localhost:3002, app.flexpqr.com
- **Lifespan:** Inicializa pool de PostgreSQL y producer Kafka al arrancar

### 2. Base de Datos (PostgreSQL 15 + RLS)
- **OLTP puro:** Toda la operativa transaccional vive en PostgreSQL
- **RLS nativo:** Politicas `tenant_isolation_*` en todas las tablas criticas
- **Variables de sesion:** `app.current_tenant_id`, `app.current_user_id`, `app.current_role`, `app.is_superuser`
- **Worker especial:** `aequitas_worker` con BYPASSRLS para inserciones desde Kafka consumers
- **Triggers:** `fn_set_fecha_vencimiento()` calcula SLA automaticamente, `fn_audit_pqrs_casos()` registra en logs_auditoria

### 3. Frontend (Next.js 14)
- **Framework:** Next.js 14 con App Router + TypeScript
- **Estado:** Zustand con persistencia en localStorage (`pqrs-v2-auth`)
- **HTTP:** Axios con interceptors para JWT automatico y re-autenticacion inline
- **Streaming:** SSE via Redis PubSub para notificaciones en tiempo real
- **Auth:** Modal de re-autenticacion cuando el token expira (SessionGuardProvider)

### 4. Message Broker (Apache Kafka)
- **Topic principal:** `pqrs.raw.emails` -- emails crudos para clasificar
- **Dead Letter Queue:** `pqrs.events.dead_letter` -- mensajes irrecuperables
- **Consumer Group:** `aequitas_classifier_group`
- **Garantias:** acks=all, idempotence=true, compresion gzip
- **Particionado:** Por tenant_id (key) para orden por cliente

### 5. Clasificacion IA (Hibrida)
- **Capa 1 -- Keywords:** scoring_engine.py con reglas ponderadas por zona (subject/body/any) + senales contextuales (dominio judicial, "48 horas", habeas data)
- **Capa 2 -- Claude Haiku:** Solo si confianza < 0.70. Usa tool_use para clasificacion estructurada
- **Merge:** Si ambas capas coinciden, boost +0.08. Si Claude tiene >= 0.70, prevalece
- **Retry:** Exponencial ante RateLimitError (2s, 4s, 8s, 16s, 32s). Despues de 5 intentos -> PoisonPillError -> DLQ

### 6. Storage (MinIO)
- **Bucket:** `pqrs-vault`
- **Claim Check Pattern:** Adjuntos > 1MB se suben a MinIO y solo la URI viaja en Kafka
- **URLs temporales:** Presigned URLs con 2h de expiracion
- **Backup:** SharePoint via Microsoft Graph API como storage secundario

### 7. Infraestructura
- **Orquestacion:** Docker Compose (9 servicios)
- **Proxy reverso:** Nginx con SSL/TLS, security headers (HSTS, X-Frame-Options DENY)
- **SSE dedicado:** Nginx con `proxy_buffering off` y `proxy_read_timeout 3600s`
- **Dominio:** app.flexpqr.com (dashboard), flexpqr.com (landing en Vercel)

## Flujo Principal de Datos

```
Email (Outlook/Zoho) -> Webhook/Worker -> Kafka (pqrs.raw.emails)
  -> AI Consumer -> classify_email_event() -> insert_pqrs_caso()
  -> Redis PubSub (pqrs.events.{tenant_id})
  -> Frontend SSE (/api/v2/stream/listen)
```

## Servicios Docker Compose

| Servicio           | Puerto Host | Descripcion                              |
|--------------------|-------------|------------------------------------------|
| postgres_v2        | 5434        | PostgreSQL 15 con RLS                    |
| redis_v2           | 6381        | Redis 7 (cache, PubSub, dedup)           |
| zookeeper_v2       | 2182        | ZooKeeper para Kafka                     |
| kafka_v2           | 9093        | Apache Kafka (Confluent 7.3)             |
| minio_v2           | 9020/9021   | MinIO (API/Console)                      |
| backend_v2         | 8001        | FastAPI                                  |
| master_worker_v2   | --          | Worker Outlook (polling multi-buzon)     |
| demo_worker_v2     | --          | Worker demo con reset periodico          |
| frontend_v2        | 3002        | Next.js 14                               |
| nginx_ssl          | 80/443      | Reverse proxy + SSL                      |


## Polimorfismo por `tipo_caso` (sprint Tutelas, 2026-04)

El sistema procesa 5 tipos canónicos: `PETICION`, `QUEJA`, `RECLAMO`, `SUGERENCIA`, `SOLICITUD`, `TUTELA` (la tutela tiene su propio tratamiento). Antes del sprint, los 3 workers tenían lógica duplicada de INSERT + cálculo de fecha + asignación. Tras el sprint, todos convergen en un único pipeline polimórfico:

```
worker → classify → pipeline.process_classified_event:
                       1. enrich_by_tipo (dispatcher polimórfico)
                       2. SLA Python (solo TUTELA con metadata) o trigger DB (default)
                       3. db_inserter.insert_pqrs_caso
                       4. vinculacion best-effort (solo TUTELA con doc_hash)
```

**Decisión B2 — SLA coexistencia.** El SP `calcular_fecha_vencimiento` (mig 14, régimen sectorial) sigue siendo el cálculo default vía trigger. Para TUTELA con `metadata.plazo_informe_horas` extraído por Claude, el `sla_engine` Python lo precalcula y el trigger respeta el valor entrante. Defense-in-depth en el trigger híbrido `fn_set_fecha_vencimiento` (3 capas: respeta valor entrante → CALENDARIO calcula `fecha_recibido + N hours` → fallback al SP sectorial).

**Decisión W3 — Pipeline unificador + auto-registro de enrichers.** `enrichers/__init__.py` mantiene `ENRICHERS: dict[str, Enricher]`. Cada enricher se auto-registra al importarse (`ENRICHERS["TUTELA"] = enrich_tutela`). `enrich_by_tipo(tipo_caso, event, clasif)` despacha al enricher correspondiente o devuelve `{}` si no hay registro. Si el enricher lanza, retorna `{"_enrichment_failed": True}` y el pipeline sigue.

**Cómo agregar un nuevo enricher (ej. SALUD):**
1. Crear `backend/app/services/enrichers/salud_extractor.py` con función `enrich_salud(event, clasif)`.
2. Al final del módulo: `ENRICHERS["SALUD"] = enrich_salud`.
3. Agregar `from . import salud_extractor` en `enrichers/__init__.py`.
4. Definir el schema (estructura de `metadata_especifica` para SALUD) en el docstring.
5. Si requiere SLA Python específico, extender `sla_engine.calcular_vencimiento_<tipo>`. Si no, el trigger DB con SP sectorial cubre.

**`metadata_especifica` JSONB polimórfico.** Cada `tipo_caso` define su propio shape dentro del campo. Ejemplo TUTELA documentado en [[SPRINT_TUTELAS_S123]]. El INSERT siempre lo trata como `jsonb` opaco — la lógica de schema vive en los enrichers.

**Vista materializada `tutelas_view` polimórfica.** Expone los campos de `metadata_especifica` como columnas planas para que frontend/BI no tengan que parsear JSONB. ⚠️ NO hereda RLS — los consumidores filtran por `cliente_id` explícito. Ver mig 21 + [[RUNBOOK_TUTELAS]].

## Referencias

- [[00_DIRECTIVAS_CLAUDE_CODE]]
- [[02_ESTANDARES_CODING]]
- [[backend_core]]
- [[SPRINT_TUTELAS_S123]] — sprint de habilitación del polimorfismo.
- [[frontend_context_sse]]
- [[infra_docker_kafka_cluster]]
- [[service_ai_classifier]]
