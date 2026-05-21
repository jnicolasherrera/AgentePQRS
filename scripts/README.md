# scripts/

Scripts auxiliares y de operación (reorganizados en Fase 1 de limpieza, 2026-05-21).
Antes estaban sueltos en la raíz del repo y en `backend/`.

- `db/` — seeds y carga de datos (`seed_*.py`, `create_admin.py`, `demo_simulate_email.py`)
- `analysis/` — scripts de análisis one-off (`analyze_*.py`)
- `onboarding/` — setup de máquina (`deploy_ubuntu.sh`)
- `testing/` — pruebas ad-hoc contra entornos remotos (`test_remote_v2.py`)

Scripts de mantenimiento del backend (que importan `app.*`) viven en `backend/scripts/`.
