# backend/scripts/

Utilidades ad-hoc de administración/diagnóstico del backend (reorganizadas 2026-05-21).
NO son parte del runtime — los entrypoints de los workers siguen en `backend/`
(`master_worker_outlook.py`, `demo_worker.py`, `healthcheck_worker.py`).

Correr desde `backend/` para que resuelvan `import app.*`, ej:
`docker exec pqrs_v2_backend python scripts/list_users.py`
