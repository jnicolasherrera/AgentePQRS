# INC-2026-06-25 — Loop infinito de seguimientos: 775k comentarios duplicados

## Severidad
ALTA. Loop infinito en producción inflando la DB sin control (afectaba ARC + FlexFintech).
Descubierto durante el test de envío de Micaela (caso `f03640cb`).

## Síntoma observado
- Caso de prueba de Micaela figuraba "Resuelto" pero con seguimientos del ciudadano sin atender.
- El panel "CORREO RECIBIDO" se veía vacío (el correo original venía sin cuerpo — eso NO era bug).
- Al investigar: `pqrs_comentarios` tenía **776.021** filas `SEGUIMIENTO_CIUDADANO` sobre solo **673 únicos**.
  Un caso con 17.154 duplicados del mismo correo. Tabla = 1 GB.

## Causa raíz
`backend/master_worker_outlook.py`, loop principal (~línea 467):
```python
if await _registrar_seguimiento(conn, em, c_id):
    continue   # ← saltaba SIN marcar el correo como leído
```
`fetch_emails` filtra `?$filter=isRead eq false`. Como el seguimiento nunca se marcaba leído,
el worker lo traía y reprocesaba en CADA ciclo (~30s) → INSERT de comentario duplicado infinito.
El path de spam (`procesar_atencion_cliente`) SÍ hacía `mark_as_read`; el de seguimiento no.

## Fix (PR #21, rama `fix/seguimiento-loop-infinito`)
1. **Loop:** `mark_as_read` del seguimiento ANTES del `continue` (OUTLOOK: `(email_buzon, id)`; ZOHO: `(id)`), en try/except con warning. Corta el reproceso de raíz.
2. **`_registrar_seguimiento`:** idempotencia — `SELECT 1 ... WHERE caso_id=$1 AND comentario=$2` antes del INSERT (defensa en profundidad). Reapertura a `EN_PROCESO` se mantiene, es idempotente.

## Deploy (quirúrgico, regla de oro)
- Backup: `backend/master_worker_outlook.py.bak.20260625`.
- ⚠️ PROD va detrás de main para este archivo (le faltan funciones como `_download_attachments_inline`). NO se copió el archivo de main: se descargó el de prod, se le aplicaron SOLO los 2 parches, y se re-subió. Diff verificado = exactamente los 2 bloques.
- `docker compose build master_worker_v2 && up -d`. Worker sano.
- Validado: conteo dejó de crecer (776015→776021 en 90s = solo seguimientos nuevos legítimos), 0 reprocesos en logs, caso Micaela no acumula más.

## Limpieza de datos
- Backup dedup previo: tabla `pqrs_comentarios_bak_20260625` (673 filas, los únicos).
- DELETE por lotes de 50k conservando el más antiguo por `(caso_id, comentario)`: 776.021 → **673**.
- `VACUUM FULL pqrs_comentarios`: 1016 MB → **984 kB**. Disco 86% → 84%.
- Caso Micaela `f03640cb` reabierto a `EN_PROCESO` (tenía 2 seguimientos reales sin atender).

## Pendientes / seguimiento
- Mergear PR #21 a main.
- Borrar `pqrs_comentarios_bak_20260625` cuando se confirme que todo quedó OK (libera ~900kB, no urge).
- Considerar índice único parcial en `pqrs_comentarios(caso_id, md5(comentario))` para blindar a nivel DB (a futuro).
- El disco de prod está al 84% (29 GB total) — vigilar, hay otras tablas/WAL que podrían necesitar VACUUM.
