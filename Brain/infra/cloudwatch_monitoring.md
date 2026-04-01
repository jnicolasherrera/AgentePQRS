# CloudWatch Monitoring — FlexPQR

**Setup date**: 01/04/2026

---

## Dashboard

**URL**: https://sa-east-1.console.aws.amazon.com/cloudwatch/home?region=sa-east-1#dashboards:name=FlexPQR-Monitor

**Region**: sa-east-1

**Paneles**:
- CPU Idle, RAM Usada, Disco Usado — Produccion
- CPU Idle, RAM Usada, Disco Usado — Staging
- Contenedores Up/Down — Produccion (7 contenedores)
- Contenedores Up/Down — Staging (7 contenedores)

---

## Namespaces

| Entorno | Namespace | Instance ID |
|---------|-----------|-------------|
| Produccion | `FlexPQR/Prod` | `i-08513f12ecd61947f` |
| Staging | `FlexPQR/Staging` | `i-051ace2a46910c789` |

---

## CloudWatch Agent

**Instalacion**: `/opt/aws/amazon-cloudwatch-agent/`
**Config**: `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`
**Service**: `amazon-cloudwatch-agent.service` (enabled, auto-start)

**Metricas del agente** (intervalo 60s):
- `cpu_usage_idle` — % CPU libre (100 = idle total)
- `mem_used_percent` — % RAM usada
- `disk_used_percent` — % disco usado en /

**Comandos utiles**:
```bash
# Ver status
sudo systemctl status amazon-cloudwatch-agent

# Reiniciar con nueva config
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

# Ver logs del agente
sudo tail -f /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
```

---

## Script Docker Monitor

**Ubicacion**: `/home/ubuntu/monitor_docker.sh`
**Cron**: `*/5 * * * *` (cada 5 minutos)
**Log**: `/var/log/monitor_docker.log`

**Metricas custom** (1 = up, 0 = down):
- `ContainerUp_pqrs_v2_backend`
- `ContainerUp_pqrs_v2_db`
- `ContainerUp_pqrs_v2_redis`
- `ContainerUp_pqrs_v2_frontend`
- `ContainerUp_pqrs_v2_nginx`
- `ContainerUp_pqrs_v2_master_worker`
- `ContainerUp_pqrs_v2_minio`

---

## IAM

**Role**: `flexpqr-ec2-s3-backup` (attached a ambos EC2)
**Policies**:
- `CloudWatchAgentServerPolicy` — para enviar metricas
- `CloudWatchFullAccess` — para dashboards y queries
- S3 policies existentes (backup)

---

## Agregar nuevas metricas

### Agregar metrica de sistema al CW Agent
1. Editar `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`
2. Agregar bajo `metrics_collected` (ver [docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html))
3. Reiniciar agente con `fetch-config -s`

### Agregar contenedor al monitor
1. Editar `/home/ubuntu/monitor_docker.sh`
2. Agregar nombre del contenedor al array `CONTAINERS`

### Agregar widget al dashboard
1. Desde AWS Console: CloudWatch > Dashboards > FlexPQR-Monitor > Edit
2. Add widget > seleccionar tipo y metrica
