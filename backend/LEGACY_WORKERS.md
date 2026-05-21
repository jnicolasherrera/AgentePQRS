# Workers legacy (revisar para deprecar — Fase 3)

Estos `worker_*.py` siguen en `backend/` pero **NO son entrypoints vivos**
(no aparecen en `docker-compose*.yml` ni en cron de prod, verificado 2026-05-21):

- `worker_outlook.py` — worker Outlook V1 (reemplazado por `master_worker_outlook.py`)
- `worker_outlook_cliente2.py` — variante multi-cliente V1
- `worker_ai_consumer.py` — consumidor Kafka del `ai-worker` (servicio comentado en compose)

Decidir en Fase 3: borrar, o mover a `archive/` si valen como referencia histórica.
No se tocaron en Fase 1 por las dudas (podrían tener lógica reutilizable).
