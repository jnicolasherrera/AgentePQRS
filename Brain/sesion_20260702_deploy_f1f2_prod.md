# Sesión 2026-07-02 — Deploy F1/F2 + main@59e23a7 a PROD (deuda de deploy #1 cerrada)

## Resumen ejecutivo

Prod (`18.228.54.9`) actualizado de imágenes del 25/06 (commit `cdff3e6` + drift) a **`main@59e23a7`** en la ventana de mantenimiento (18:00 ART). Entra al runtime TODO lo que faltaba: **F1+F2 (lectura de adjuntos para borradores)**, RAG cierre-de-loop completo (PR #17), `/health` (DT-25, PR #18), reclasificación workflow PQRS↔AC (PR #19), fixes de auditoría A1–A7 y RBAC operador v2.

**Validación E2E real inmediata**: minutos después del swap, el master_worker procesó derechos de petición reales de ARC con adjuntos — `📎 1 adjuntos descargados para contexto borrador`, `Borrador [PENDIENTE] ... rag_docs=3`. La feature por la que se hizo el deploy quedó verificada con casos reales, no sintéticos.

## Contexto (preflight 15:40–15:55 ART)

- El diagnóstico del mediodía (demo en vivo) mostró que prod NO leía adjuntos: la imagen corriendo era del 25/06, buildeada desde `cdff3e6` — commit que NO contiene F1/F2 (PR #16 se mergeó antes que #17).
- El repo del server tenía drift sin commitear del 25/06 (firma_engine, outlook_send_engine, etc.) — verificado archivo por archivo que TODO estaba ya en main (idéntico o evolucionado por las PRs #20–#28 de Hermes). Nada que preservar salvo `docker-compose.yml`, `.env` y `nginx/certs/`.
- DB: solo faltaba la migración 14 (régimen SLA sectorial). pgvector, migs 15–19 y policies C2 ya estaban.
- `package.json` sin cambios → frontend por reuse (`npm run build` en container, regla inmutable de prod).
- Compose prod ya tenía `VOYAGE_API_KEY` y `WORKER_DB_URL`.

## Ejecución (18:00–18:15 ART)

1. Backups: dump DB 8.4 MB + compose + `.env` en `/home/ubuntu/backups/*20260702*`; imágenes taggeadas `pre-upgrade-20260702`; tag git `pre-f1f2-prod-20260702` (= `cdff3e6`).
2. Migración 14 aplicada (regimen_sla + festivos_colombia + sla_regimen_config + trigger fecha_vencimiento). Verificada: 22 festivos, 24 configs.
3. Git: drift stasheado (`prod-drift-pre-f1f2-20260702`), pull ff a `59e23a7`, compose restaurado del backup, certs del stash.
4. Build backend_v2 + master_worker_v2 + demo_worker_v2 (~3 min) y swap con `up -d --no-deps`. Frontend: `npm run build` en container + restart `frontend_v2 nginx_ssl`.
5. Verificación runtime: `document_reader` + `_leer_adjuntos_para_contexto` importan en el container nuevo.

## Incidentes durante el corte (ambos resueltos en ~15 min)

### 1. `permission denied for table sla_regimen_config` (master_worker, buzón ARC)
Mismo patrón que staging 2026-06-01 (DT-43): el `GRANT ALL ON ALL TABLES` histórico es one-shot y no cubre las tablas nuevas de la mig 14. El trigger de `fecha_vencimiento` (SECURITY INVOKER) lee esas tablas al insertar casos → el worker explotaba. **Fix**: `GRANT SELECT ON sla_regimen_config, festivos_colombia TO aequitas_worker`.

### 2. `value too long for type character varying(500)` (buzón ARC en loop)
Un derecho de petición real con asunto >500 chars (cadena de forwards) bloqueaba el buzón en head-of-line (reintento por ciclo, ~60 s). `pqrs_casos.asunto` era `varchar(500)` y `tutelas_view` (materialized) dependía de la columna. **Fix**: `storage_path` → TEXT directo; `asunto` → TEXT con drop/recreate transaccional de `tutelas_view` (867 filas, 3 índices recreados idénticos). Ambos fixes versionados en la **migración 20** (`aequitas_infrastructure/database/20_asunto_text_y_grants_worker.sql`, idempotente — pendiente aplicar en staging).

Post-fix: los 2 emails trabados se inyectaron (`13f44340`, `6c3b3194` con `john.docx`) y 3+ ciclos limpios.

## Smoke final (18:15 ART)

- `/health` → `{"status":"ok","db":"up"}` (loopback; nginx NO lo proxya — para uptime-probe externo falta un `location /health` en nginx, anotado en DT-25).
- Login (`/api/v2/auth/login`) → 401 con creds dummy (vivo vía nginx). `/` y `/login` → 200.
- `/docs` Swagger quedó accesible SOLO en loopback (`/api/v2/docs` público da 404) — mejora de seguridad, no regresión.
- backend/master_worker/demo_worker sin errores; workers healthy; ingesta ARC drenando backlog.
- Disco: 85% → 93% (build) → 89% post-prune. **Recuperable**: borrar tags `pre-upgrade-20260702` (~2 GB) cuando se confirme estabilidad (unos días).

## Rollback disponible

- Imágenes: `pqrs_v2-{backend_v2,master_worker_v2,demo_worker_v2}:pre-upgrade-20260702`.
- Git: tag `pre-f1f2-prod-20260702`; drift en stash `prod-drift-pre-f1f2-20260702`.
- DB: `/home/ubuntu/backups/pqrs_v2_pre_upgrade_20260702.dump.gz` (migs 14 y 20 son aditivas, no requieren revert).

## Notas operativas

- **demo_worker**: había sido apagado a propósito el 25/06 (zombie congelado desde el 29/05, hallazgo auditoría). Hoy se revivió al mediodía para la demo en vivo de Nico y FUNCIONÓ (ingirió el caso `c5098ce5` con PDF). Con el rebuild de hoy corre código main. **La idea de borrarlo del compose queda revertida: se usa para demos comerciales.** Le falta healthcheck real (DT-33).
- El caso demo `c5098ce5` (mediodía) se respondió con un workaround fuera de pipeline; con F1/F2 en prod el workaround ya no hace falta.
- Kafka/zookeeper vestigiales intactos (no se usó `up -d` sin `--no-deps`).

## Pendientes derivados

1. Aplicar migración 20 en **staging** (asunto/storage_path TEXT + grants).
2. `location /health` en nginx prod para monitoreo externo (cierra DT-25 al 100%).
3. Borrar tags/imágenes `pre-upgrade-20260702` en ~1 semana (recupera ~2 GB de disco).
4. DT-43 sigue: considerar `ALTER DEFAULT PRIVILEGES ... GRANT SELECT TO aequitas_worker` (decisión de seguridad, no tomada unilateralmente).
5. Truncado cosmético de asuntos kilométricos en la UI (opcional).
