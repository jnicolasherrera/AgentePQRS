# Columnas Faltantes y Evoluciones de Esquema

## Columnas Agregadas Post-Migracion Inicial

Las siguientes columnas existen en los modelos ORM (`backend/app/core/models.py`) pero pueden requerir migraciones adicionales si no estan en la BD:

### pqrs_casos
| Columna              | Tipo          | Descripcion                              |
|----------------------|---------------|------------------------------------------|
| tipo_caso            | VARCHAR(50)   | Clasificacion: TUTELA, PETICION, etc.    |
| fecha_vencimiento    | TIMESTAMPTZ   | Calculada por trigger de SLA             |
| borrador_respuesta   | TEXT          | Texto del borrador generado por IA       |
| borrador_estado      | VARCHAR(20)   | SIN_PLANTILLA, PENDIENTE, ENVIADO, etc.  |
| problematica_detectada | VARCHAR(100)| Slug de la problematica detectada        |
| plantilla_id         | UUID          | FK a plantillas_respuesta                |
| aprobado_por         | UUID          | FK a usuarios (quien aprobo el envio)    |
| aprobado_at          | TIMESTAMPTZ   | Fecha de aprobacion                      |
| enviado_at           | TIMESTAMPTZ   | Fecha de envio del email de respuesta    |
| alerta_2h_enviada    | BOOLEAN       | Flag para alerta de 2h (tutelas)         |
| acuse_enviado        | BOOLEAN       | Flag de acuse de recibo enviado          |
| numero_radicado      | VARCHAR(30)   | Numero de radicado unico                 |
| correlation_id       | UUID          | Trazabilidad desde Kafka                 |
| asignado_a           | UUID          | FK a usuarios (analista asignado)        |
| semaforo_sla         | VARCHAR(10)   | VERDE, AMARILLO, ROJO                    |
| es_pqrs              | BOOLEAN       | Marcado por admin como PQRS o no         |
| fecha_asignacion     | TIMESTAMPTZ   | Cuando se asigno a un analista           |

### pqrs_adjuntos
| Columna   | Tipo    | Descripcion                              |
|-----------|---------|------------------------------------------|
| es_reply  | BOOLEAN | Distingue adjuntos originales vs reply   |

### usuarios
| Columna              | Tipo    | Descripcion                              |
|----------------------|---------|------------------------------------------|
| debe_cambiar_password| BOOLEAN | Forzar cambio en primer login            |

### config_buzones
| Columna              | Tipo         | Descripcion                             |
|----------------------|--------------|-----------------------------------------|
| proveedor            | VARCHAR(50)  | OUTLOOK o ZOHO                          |
| zoho_refresh_token   | TEXT         | Token de refresco para Zoho             |
| zoho_account_id      | VARCHAR(255) | ID de cuenta Zoho                       |

## Tablas Adicionales Referenciadas en Codigo

Estas tablas se mencionan en el codigo pero pueden no tener migracion SQL formal:

- `clasificacion_feedback` -- Feedback de divergencia keywords vs Claude
- `pqrs_clasificacion_feedback` -- Feedback manual de admin
- `borrador_feedback` -- Feedback de edicion de borradores

Si no existen en la BD, los inserts fallan silenciosamente (try/except en el codigo).
