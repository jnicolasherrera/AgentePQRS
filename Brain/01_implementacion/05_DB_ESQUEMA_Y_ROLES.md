# Base de Datos: Esquema y Roles

## Archivos de Migracion

| Archivo                          | Contenido                                          |
|----------------------------------|-----------------------------------------------------|
| 01_schema_v2.sql                 | Tablas base: clientes_tenant, usuarios, pqrs_casos  |
| 02_rls_security_v2.sql           | Politicas RLS iniciales                             |
| 03_advanced_features_v2.sql      | pqrs_adjuntos, pqrs_comentarios + RLS               |
| 04_multi_tenant_config_v2.sql    | config_buzones + super_admin bypass + seeds          |
| 05_multi_provider_buzones.sql    | Multi-proveedor (Outlook/Zoho)                      |
| 08_plantillas_schema.sql         | plantillas_respuesta                                |

## Tablas Principales

### clientes_tenant
Tabla raiz de multitenancy. Todo tenant tiene un UUID unico.
- Campos: id, nombre, dominio, is_active, created_at

### usuarios
Usuarios ligados a un tenant via cliente_id.
- Roles validos: admin, coordinador, analista, auditor, super_admin, bot
- Campo `debe_cambiar_password` para forzar cambio en primer login

### pqrs_casos
Tabla transaccional principal de casos PQRS.
- Estados: ABIERTO, EN_PROCESO, CONTESTADO, CERRADO
- Semaforo SLA: VERDE, AMARILLO, ROJO
- Borrador estados: SIN_PLANTILLA, PENDIENTE, RECHAZADO, ENVIADO
- correlation_id para trazabilidad end-to-end desde Kafka

### pqrs_adjuntos
Archivos adjuntos almacenados en MinIO.
- Campo `es_reply` para distinguir adjuntos del email original vs adjuntos de respuesta

### pqrs_comentarios
Timeline de eventos del caso.
- tipo_evento: COMENTARIO, CAMBIO_ESTADO, IA_DRAFT, etc.

### config_buzones
Configuracion dinamica de buzones de email por tenant.
- Soporta OUTLOOK y ZOHO como proveedores

### plantillas_respuesta
Plantillas de respuesta por problematica y tenant.
- Campo `keywords` (ARRAY[TEXT]) para matching
- Campo `problematica` para mapeo con deteccion automatica

### audit_log_respuestas
Log inmutable de acciones sobre respuestas (BORRADOR_GENERADO, BORRADOR_EDITADO, ENVIADO_LOTE, RECHAZADO).

### logs_auditoria
Audit trail general con delta_antes/delta_despues en JSONB.

### festivos_colombia
Tabla de dias festivos para calculo de plazos en dias habiles.

## Roles de Base de Datos

| Rol              | Descripcion                                     |
|------------------|--------------------------------------------------|
| pqrs_admin       | Owner de la base de datos, usado por el backend  |
| aequitas_worker  | Rol con BYPASSRLS, usado por workers Kafka       |

## Politicas RLS

Todas las tablas con `cliente_id` tienen politica:
```sql
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID
    OR current_setting('app.is_superuser', true) = 'true'
)
```

El backend inyecta las variables via `set_config()` antes de cada query. El worker usa `aequitas_worker` que bypasea RLS nativamente.
