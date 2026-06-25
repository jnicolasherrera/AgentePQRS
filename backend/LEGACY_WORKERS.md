# Workers legacy (Fase 3 — 2026-06-25)

Estos `worker_*.py` **NO son entrypoints vivos**
(no aparecen en `docker-compose*.yml` ni en cron de prod, verificado 2026-05-21):

## Archivados en `backend/archive/` (Fase 3 — 2026-06-25)

- `worker_outlook.py` — worker Outlook V1 (reemplazado por `master_worker_outlook.py`). Movido a `backend/archive/`.
- `worker_outlook_cliente2.py` — variante multi-cliente V1. Movido a `backend/archive/`.

## Pendientes (no se mueven aún)

- `worker_ai_consumer.py` — consumidor Kafka del `ai-worker` (servicio comentado en compose). **No se mueve porque `backend/tests/test_ai_worker.py` lo importa directamente.**
