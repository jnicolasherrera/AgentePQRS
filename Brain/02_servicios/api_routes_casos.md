# API Routes: Casos

## Archivo
`backend/app/api/routes/casos.py`

## Prefijo
`/api/v2/casos`

## Descripcion
CRUD principal de casos PQRS. Incluye gestion de borradores, adjuntos de respuesta, aprobacion por lote con envio via Zoho/Gmail, historial de enviados y metricas de respuestas.

## Endpoints

### GET /borrador/pendientes
- **Funcion:** Lista hasta 100 casos con borrador_estado='PENDIENTE' ordenados por fecha
- **Retorna:** id, email_origen, asunto, tipo, prioridad, fecha, borrador_respuesta, problematica

### GET /enviados/historial
- **Acceso:** admin, super_admin, analista (solo sus envios)
- **Funcion:** Historial de respuestas enviadas via audit_log_respuestas
- **Parametros:** cliente_id (super_admin)

### GET /metricas/respuestas
- **Acceso:** Solo admin / super_admin
- **Funcion:** Metricas de respuestas: respondidos_hoy, respondidos_semana, tiempo_promedio_horas, tasa_cobertura_plantilla, por_abogado

### GET /{caso_id}
- **Funcion:** Detalle completo de un caso con comentarios y adjuntos
- **Retorna:** Datos del caso, timeline de comentarios, lista de archivos con URLs de descarga

### GET /{caso_id}/adjuntos/{adjunto_id}/download
- **Funcion:** Descarga un adjunto desde MinIO via streaming
- **Retorna:** StreamingResponse con el archivo

### PATCH /{caso_id}
- **Funcion:** Actualiza estado y/o prioridad de un caso
- **Body:** `{ "estado": "...", "prioridad": "..." }`

### PUT /{caso_id}/borrador
- **Funcion:** Edita el texto del borrador de respuesta
- **Efecto adicional:** Si el texto difiere del original IA, calcula similarity_score y lo registra en borrador_feedback

### POST /{caso_id}/rechazar-borrador
- **Funcion:** Marca el borrador como RECHAZADO y registra en audit_log

### POST /{caso_id}/reply-adjuntos
- **Funcion:** Sube un archivo adjunto para la respuesta (max 10MB)
- **Storage:** MinIO en `reply/{caso_id}/`
- **Flag:** `es_reply=TRUE` en pqrs_adjuntos

### DELETE /{caso_id}/reply-adjuntos/{adjunto_id}
- **Funcion:** Elimina un adjunto de reply

### POST /aprobar-lote
- **Funcion:** Aprueba y envia hasta 10 borradores en un lote
- **Seguridad:** Requiere password del usuario como confirmacion
- **Envio:** Via Zoho Mail API (preferido) o Gmail SMTP (fallback)
- **Adjuntos:** Descarga adjuntos de reply desde MinIO e incluye en el email
- **Auditoria:** Registra ENVIADO_LOTE con lote_id, IP origen, email destino
- **Efecto:** Actualiza borrador_estado='ENVIADO', estado='CERRADO'
