---
tags:
  - brain/service
---

# Service: Plantilla Engine

## Archivo
`backend/app/services/plantilla_engine.py`

## Descripcion
Motor de plantillas para generar borradores de respuesta. Detecta la problematica del caso, busca una plantilla en la BD, la personaliza con datos del caso, y como fallback genera un borrador con Claude Haiku.

## Funcion Principal: generar_borrador_para_caso(conn, tenant_id, caso_id, ...)

### Flujo
1. `detectar_problematica(asunto, cuerpo)` -- Identifica la problematica especifica
2. `obtener_plantilla(conn, tenant_id, problematica)` -- Busca plantilla activa en la BD
3. Si no hay plantilla especifica, intenta `GENERICO_{tipo_caso}` como fallback
4. Si hay plantilla: `personalizar_borrador()` con variables del caso
5. Si no hay plantilla: `generar_borrador_con_ia()` con Claude Haiku
6. Actualiza pqrs_casos con borrador, estado, problematica, plantilla_id
7. Registra en audit_log_respuestas

## Deteccion de Problematicas

Reglas ordenadas por especificidad (primera en matchear gana):

| Slug                         | Keywords Base                           | Keywords Requeridos |
|------------------------------|-----------------------------------------|---------------------|
| SUPLANTACION_RAPICREDIT      | suplantacion, robo identidad, fraude    | rapicredit          |
| PAZ_Y_SALVO_RAPICREDIT       | paz y salvo, certificado de paz         | rapicredit          |
| SUPLANTACION_GENERAL         | suplantacion, robo identidad, fraude    | (ninguno)           |
| PAZ_Y_SALVO_FINDORSE         | paz y salvo, libre de deuda             | findorse            |
| DEBITOS_AUTOMATICOS          | debito automatico, cobro automatico     | (ninguno)           |
| ELIMINACION_CENTRALES_PAZ    | centrales de riesgo, datacredito        | paz y salvo         |
| ELIMINACION_CENTRALES_PROPIA | centrales de riesgo, datacredito        | (ninguno)           |
| SIN_IDENTIFICACION           | sin cedula, sin identificacion          | (ninguno)           |

## Personalizacion de Borrador

`personalizar_borrador()` reemplaza:
- Saludos genericos por nombre del cliente
- Variables con doble llave: `{{nombre}}`, `{{cedula}}`, `{{radicado}}`, `{{email}}`, `{{tipo}}`, `{{fecha_vencimiento}}`

## Generacion con IA (Fallback)

`generar_borrador_con_ia()` usa Claude Haiku con prompts especializados por tipo:
- TUTELA: Experto en acciones de tutela, cita Decreto 2591 de 1991
- PETICION: Experto en derechos de peticion, cita Art. 23 Constitucion
- QUEJA: Especialista en proteccion al consumidor financiero (SFC)
- RECLAMO: Similar a QUEJA con enfoque en cobros indebidos
- SOLICITUD: Respuesta formal generica

Todos los borradores IA incluyen un aviso: "Esta respuesta fue generada automaticamente por inteligencia artificial".
