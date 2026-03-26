# Hoja de Ruta Paso a Paso -- FlexPQR

## Historial de Implementacion

### Sprint 0: Fundacion (Feb 2026)
- [x] Esquema PostgreSQL V2 con RLS multi-tenant
- [x] Backend FastAPI con asyncpg
- [x] Frontend Next.js 14 con Zustand auth
- [x] Docker Compose con 9 servicios
- [x] Nginx reverse proxy con SSL

### Sprint 1: Motor de Ingesta (Feb 2026)
- [x] Worker Outlook multi-buzon (`master_worker_outlook.py`)
- [x] Integracion Zoho Mail (lectura + envio)
- [x] Clasificador de keywords con scoring ponderado
- [x] SLA legal colombiano con festivos
- [x] SSE via Redis PubSub

### Sprint 2: El Cerebro (Feb-Mar 2026)
- [x] Kafka producer/consumer con DLQ
- [x] AI Classifier con retry exponencial
- [x] Clasificacion hibrida (keywords + Claude Haiku)
- [x] db_inserter con round-robin de analistas
- [x] Claim Check Pattern para adjuntos
- [x] Webhooks Microsoft Graph + Google Workspace

### Sprint 3: Respuestas Inteligentes (Mar 2026)
- [x] Plantilla engine con deteccion de problematicas
- [x] Borradores IA con prompts legales por tipo
- [x] Aprobacion por lote con confirmacion de password
- [x] Envio via Zoho Mail con adjuntos
- [x] Acuse de recibo HTML automatico
- [x] Audit log de respuestas

### Sprint 4: Dashboard Avanzado (Mar 2026)
- [x] Estadisticas KPIs por tenant
- [x] Rendimiento por abogado (asignados, cerrados, vencidos)
- [x] Tendencia recibidos vs cerrados
- [x] Historial de enviados
- [x] Metricas de respuestas
- [x] Re-autenticacion inline con retry de requests

## Proximos Pasos (Sin Implementar)

### Sprint 5: Produccion Hardening
- [ ] Kubernetes manifiestos + KEDA autoscaling
- [ ] WAF / Cloudflare
- [ ] Backup automatizado de PostgreSQL
- [ ] Monitoring (Grafana + Prometheus)
- [ ] Health checks endpoint detallado

### Sprint 6: Billing
- [ ] Stripe/Wompi integracion
- [ ] Quotas por tenant
- [ ] Facturacion automatica por volumen

### Sprint 7: Analytics
- [ ] Snowflake ETL nocturno
- [ ] Dashboards OLAP separados
- [ ] Prediccion de volumen con ML

### Sprint 8: Frontend Performance
- [ ] TanStack Query para cache client-side
- [ ] Virtualizacion de tablas (react-virtual)
- [ ] Kanban board interactivo


## Referencias

- [[00_DIRECTIVAS_CLAUDE_CODE]]
- [[01_ARQUITECTURA_MAESTRA]]
- [[14_CONFIRMACION_TECNICA_SPRINT_0]]
- [[13_EQUIPOS_DE_AGENTES_Y_ORQUESTACION]]
