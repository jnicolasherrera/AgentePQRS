#!/bin/bash
# check_ingestion v3 — DT-34 alerting via email multi-tenant
# Lee credenciales SMTP del tenant desde SSM y envía alertas a Nico.

set -e

# Config
TENANT_KEY=${TENANT_KEY:-arc}
CLIENTE_ID=${CLIENTE_ID:-effca814-b0b5-4329-96be-186c0333ad4b}
THRESHOLD_HOURS=${THRESHOLD_HOURS:-2}
MAX_HOURS_BEFORE_RESTART=${MAX_HOURS_BEFORE_RESTART:-4}
AWS_REGION=${AWS_REGION:-sa-east-1}
LOG_FILE=${LOG_FILE:-/home/ubuntu/logs/check_ingestion.log}
STATE_FILE=${STATE_FILE:-/home/ubuntu/.check_ingestion_state_${TENANT_KEY}}

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$TENANT_KEY] $1" >> "$LOG_FILE"
}

# Leer config SMTP del tenant desde SSM
ssm_get() {
    aws ssm get-parameter \
        --name "/flexpqr/alerts/${TENANT_KEY}/$1" \
        --with-decryption \
        --region "$AWS_REGION" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null
}

send_email() {
    local subject="$1"
    local body="$2"

    # Cargar config tenant
    local smtp_user smtp_password smtp_host destinatario
    smtp_user=$(ssm_get smtp_user)
    smtp_password=$(ssm_get smtp_password)
    smtp_host=$(ssm_get smtp_host)
    destinatario=$(ssm_get destinatario)

    if [ -z "$smtp_user" ] || [ -z "$smtp_password" ] || [ -z "$smtp_host" ] || [ -z "$destinatario" ]; then
        log "ERROR: faltan parametros SSM para tenant ${TENANT_KEY}"
        return 1
    fi

    # Build mail file
    local mail_file
    mail_file=$(mktemp)
    cat > "$mail_file" << MAIL_END
From: $smtp_user
To: $destinatario
Subject: $subject
Content-Type: text/plain; charset=UTF-8

$body
MAIL_END

    # Send via curl SMTP (sanitiza errores antes de loguear)
    local result
    result=$(curl --silent --show-error \
        --url "smtps://${smtp_host}:465" \
        --ssl-reqd \
        --mail-from "$smtp_user" \
        --mail-rcpt "$destinatario" \
        --user "${smtp_user}:${smtp_password}" \
        --upload-file "$mail_file" 2>&1)

    local exit_code=$?

    # Cleanup
    rm -f "$mail_file"
    # Sanitizar password del result antes de log
    local sanitized=$(echo "$result" | sed "s|${smtp_password}|***REDACTED***|g")
    unset smtp_password

    if [ $exit_code -ne 0 ]; then
        log "ERROR envio email: $sanitized"
        return 1
    fi

    log "Email enviado: $subject"
    return 0
}

# 1. Verificar DB sana
DB_CHECK=$(docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -tAc "SELECT 1" 2>&1 || echo "FAIL")
if [ "$DB_CHECK" != "1" ]; then
    log "CRITICAL: DB no responde. Output: $DB_CHECK"
    exit 1
fi

# 2. Calcular hace cuanto fue el ultimo caso
LATEST_HOURS=$(docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -tAc \
    "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(fecha_recibido)))/3600
     FROM pqrs_casos
     WHERE cliente_id = '$CLIENTE_ID'" 2>/dev/null || echo "999")

HOURS_INT=${LATEST_HOURS%.*}

# 3. Decidir accion
if [ "$HOURS_INT" -lt "$THRESHOLD_HOURS" ]; then
    echo "OK" > "$STATE_FILE"
    exit 0
elif [ "$HOURS_INT" -lt "$MAX_HOURS_BEFORE_RESTART" ]; then
    LAST_STATE=$(cat "$STATE_FILE" 2>/dev/null || echo "OK")
    if [ "$LAST_STATE" != "WARNING" ]; then
        log "WARNING: cliente=$CLIENTE_ID sin casos hace ${HOURS_INT}h"
        send_email \
            "[FlexPQR][${TENANT_KEY^^}] WARNING ingestion delayed" \
            "Tenant: ${TENANT_KEY}
Cliente ID: $CLIENTE_ID
Sin casos hace: ${HOURS_INT}h
Threshold: ${THRESHOLD_HOURS}h
Servidor: $(hostname)
Hora: $(date)
Estado: WARNING (sin restart aun)
Auto-restart si supera ${MAX_HOURS_BEFORE_RESTART}h.

Investigar:
- ssh flexpqr-prod
- docker logs pqrs_v2_master_worker --tail 50
- ver bridge cron logs en /home/ubuntu/logs/check_ingestion.log"
        echo "WARNING" > "$STATE_FILE"
    fi
else
    log "CRITICAL: cliente=$CLIENTE_ID sin casos hace ${HOURS_INT}h - restart aplicado"
    docker restart pqrs_v2_master_worker >> "$LOG_FILE" 2>&1
    send_email \
        "[FlexPQR][${TENANT_KEY^^}] CRITICAL master_worker restarted" \
        "Tenant: ${TENANT_KEY}
Cliente ID: $CLIENTE_ID
Sin casos hace: ${HOURS_INT}h
Threshold critico: ${MAX_HOURS_BEFORE_RESTART}h
Accion: docker restart pqrs_v2_master_worker
Hora: $(date)

Esto NO deberia ocurrir si DT-32 (reconnect) y DT-33 (healthcheck)
funcionan. Si llega esta alerta, investigar fallo de esas capas."
    echo "CRITICAL" > "$STATE_FILE"
fi

exit 0
