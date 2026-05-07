#!/bin/bash
# Mitigación bridge — INC-2026-04-27 master_worker pool dead.
# Verifica si master_worker está ingestando casos. Si no, auto-restart.
# Reemplazar cuando DT-32 (reconnect logic) + DT-33 (healthcheck) + DT-34 (alerting)
# estén implementados como fix de fondo.
#
# Cron sugerido: 0 * * * * /home/ubuntu/check_ingestion.sh
# Log: /home/ubuntu/logs/check_ingestion.log

set -uo pipefail

THRESHOLD_HOURS="${THRESHOLD_HOURS:-4}"
CLIENTE_ID="${CLIENTE_ID:-effca814-b0b5-4329-96be-186c0333ad4b}"
LOG_FILE="${LOG_FILE:-/home/ubuntu/logs/check_ingestion.log}"
WORKER_CONTAINER="${WORKER_CONTAINER:-pqrs_v2_master_worker}"
DB_CONTAINER="${DB_CONTAINER:-pqrs_v2_db}"

mkdir -p "$(dirname "$LOG_FILE")"

TS() { date -u +%Y-%m-%dT%H:%M:%SZ; }

DB_CHECK=$(docker exec "$DB_CONTAINER" psql -U pqrs_admin -d pqrs_v2 -tAc "SELECT 1" 2>&1)
if [ "$DB_CHECK" != "1" ]; then
    echo "[$(TS)] ERROR: DB $DB_CONTAINER no responde: $DB_CHECK" >> "$LOG_FILE"
    exit 1
fi

LATEST_CASE=$(docker exec "$DB_CONTAINER" psql -U pqrs_admin -d pqrs_v2 -tAc \
    "SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - MAX(fecha_recibido)))/3600, -1)
     FROM pqrs_casos
     WHERE cliente_id = '$CLIENTE_ID'" 2>/dev/null)

HOURS_AGO=${LATEST_CASE%.*}

if [ "$HOURS_AGO" = "-1" ]; then
    echo "[$(TS)] INFO: cliente_id=$CLIENTE_ID sin casos (esperado en staging recién provisto)" >> "$LOG_FILE"
    exit 0
fi

if [ "$HOURS_AGO" -gt "$THRESHOLD_HOURS" ]; then
    echo "[$(TS)] ALERTA: cliente=$CLIENTE_ID sin casos nuevos hace ${HOURS_AGO}h (umbral=${THRESHOLD_HOURS}h)" >> "$LOG_FILE"
    docker restart "$WORKER_CONTAINER" >> "$LOG_FILE" 2>&1
    echo "[$(TS)] Restart $WORKER_CONTAINER aplicado automáticamente" >> "$LOG_FILE"
fi
