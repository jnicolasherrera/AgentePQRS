---
tags:
  - brain/maestro
---

# Manifiesto de Entrega Senior -- FlexPQR

## Criterios de Aceptacion para Cualquier Feature

### 1. Seguridad
- [ ] No introduce secretos en codigo fuente
- [ ] Queries pasan por RLS (usa `get_db_connection` con JWT)
- [ ] Inputs validados con Pydantic
- [ ] Endpoints sensibles tienen rate limiting

### 2. Multi-tenancy
- [ ] Toda nueva tabla tiene `cliente_id` con FK a `clientes_tenant`
- [ ] RLS habilitado y politica creada para la nueva tabla
- [ ] Super admin bypass via `app.is_superuser`
- [ ] Worker usa `aequitas_worker` (BYPASSRLS) si necesita cross-tenant

### 3. Resiliencia
- [ ] Errores no crashean el servicio completo
- [ ] Operaciones externas (API calls) tienen timeout y retry
- [ ] Mensajes Kafka irrecuperables van a DLQ
- [ ] Logs con correlation_id para trazabilidad

### 4. Rendimiento
- [ ] Queries SQL tienen indices apropiados
- [ ] No se hacen N+1 queries (usar JOINs o batch)
- [ ] Paginacion en listados (LIMIT/OFFSET)
- [ ] Adjuntos grandes no viajan en Kafka (Claim Check Pattern)

### 5. Auditoria Legal
- [ ] Cambios de estado registrados en `logs_auditoria` o `audit_log_respuestas`
- [ ] Acciones criticas (envio de respuesta) requieren confirmacion de password
- [ ] IP de origen registrada en acciones de envio

### 6. Testing
- [ ] Casos de prueba cubren el happy path
- [ ] Casos de prueba cubren autorizacion (403 para roles no permitidos)
- [ ] Casos de prueba cubren aislamiento de tenant
