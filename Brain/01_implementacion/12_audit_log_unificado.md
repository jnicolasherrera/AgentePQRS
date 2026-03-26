---
tags:
  - brain/implementacion
---

# Audit Log Unificado -- FlexPQR

## Tablas de Auditoria

### 1. logs_auditoria (General)

Audit trail general para cambios en cualquier tabla. Trigger automatico `fn_audit_pqrs_casos` lo alimenta.

```sql
CREATE TABLE logs_auditoria (
    id UUID PRIMARY KEY,
    correlation_id UUID,        -- Trazabilidad end-to-end
    tabla_afectada VARCHAR(50), -- Nombre de la tabla
    registro_id UUID,           -- ID del registro afectado
    usuario_id UUID,            -- Quien hizo el cambio
    cliente_id UUID,            -- Tenant
    accion VARCHAR(30),         -- INSERT, UPDATE, DELETE, VIEW
    delta_antes JSONB,          -- Estado anterior
    delta_despues JSONB,        -- Estado posterior
    ip_origen INET,             -- IP del usuario
    created_at TIMESTAMPTZ
);
```

### 2. audit_log_respuestas (Respuestas Especifico)

Log de acciones sobre borradores y envios de respuestas.

```sql
CREATE TABLE audit_log_respuestas (
    id UUID PRIMARY KEY,
    caso_id UUID,         -- Caso asociado
    usuario_id UUID,      -- Quien realizo la accion
    accion VARCHAR(30),   -- BORRADOR_GENERADO, BORRADOR_EDITADO, ENVIADO_LOTE, RECHAZADO
    lote_id UUID,         -- ID del lote de envio (si aplica)
    ip_origen INET,       -- IP del origen
    metadata JSONB,       -- Datos adicionales
    created_at TIMESTAMPTZ
);
```

### 3. clasificacion_feedback (IA Feedback)

Registra divergencias entre clasificacion por keywords y por Claude.

### 4. pqrs_clasificacion_feedback (Admin Feedback)

Registra correcciones manuales de clasificacion por administradores.

### 5. borrador_feedback (Edicion de Borradores)

Registra cuanto edita un abogado el borrador generado por IA.

## Acciones Auditadas

| Accion            | Tabla                   | Trigger/Manual |
|-------------------|-------------------------|----------------|
| INSERT caso       | logs_auditoria          | Trigger        |
| UPDATE caso       | logs_auditoria          | Trigger        |
| BORRADOR_GENERADO | audit_log_respuestas    | Manual         |
| BORRADOR_EDITADO  | audit_log_respuestas    | Manual         |
| ENVIADO_LOTE      | audit_log_respuestas    | Manual         |
| RECHAZADO         | audit_log_respuestas    | Manual         |

## Trazabilidad End-to-End

Cada caso tiene un `correlation_id` que se genera en el webhook/ingesta y viaja por todo el pipeline:

```
Webhook -> correlation_id generado
  -> Kafka message -> correlation_id preservado
  -> AI Consumer -> correlation_id preservado
  -> INSERT pqrs_casos -> correlation_id guardado
  -> Redis notification -> correlation_id incluido
  -> logs_auditoria -> correlation_id registrado
```
