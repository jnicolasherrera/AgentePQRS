---
tags:
  - brain/worker
---

# Worker: DB Inserter

## Archivo
`backend/app/services/db_inserter.py`

## Descripcion
Persiste el resultado de clasificacion IA en pqrs_casos. Usa el rol `aequitas_worker` (BYPASSRLS) y no depende del pool ni del JWT del backend FastAPI.

## Funcion Principal: insert_pqrs_caso(event, result, pool)

### Flujo
1. Extrae tenant_id y correlation_id del evento
2. Extrae asunto (max 500 chars), cuerpo (max 10000 chars), email_origen (max 255 chars)
3. Parsea fecha_recibido del evento (o usa NOW() UTC)
4. **Round Robin:** Asigna al analista con menor carga
5. Inserta en pqrs_casos con estado='ABIERTO'
6. Retorna UUID del caso insertado

### Campos Insertados
- cliente_id, correlation_id, tipo_caso, asunto, cuerpo, email_origen
- estado='ABIERTO', nivel_prioridad, asignado_a
- borrador_respuesta, borrador_estado, fecha_recibido

### Triggers Automaticos (PostgreSQL)
- `fn_set_fecha_vencimiento()` -- Calcula fecha_vencimiento basado en tipo_caso y festivos
- `fn_audit_pqrs_casos()` -- Registra la insercion en logs_auditoria

## Round Robin de Analistas

`_round_robin_analista(conn, tenant_id)`:
```sql
SELECT u.id FROM usuarios u
WHERE u.cliente_id = $1
  AND u.rol = 'analista'
  AND u.is_active = TRUE
ORDER BY (
    SELECT COUNT(*) FROM pqrs_casos p
    WHERE p.asignado_a = u.id AND p.estado = 'ABIERTO'
) ASC,
u.created_at ASC
LIMIT 1
```
- Asigna al analista con menos casos ABIERTOS
- En caso de empate, prefiere al mas antiguo (created_at ASC)
- Retorna None si no hay analistas activos

## Parse de Fecha

`_parse_fecha(raw)`:
- Si es datetime: asegura timezone UTC
- Si es string: intenta parsear con pandas
- Si falla: usa `datetime.now(UTC)`

## Nota sobre Trazabilidad
El `correlation_id` generado en el webhook/ingesta se preserva en la insercion, permitiendo trazabilidad end-to-end desde la recepcion hasta la notificacion SSE.


## Referencias

- [[worker_kafka_consumer]]
- [[backend_core]]
- [[10_rbac_rls_roles]]
