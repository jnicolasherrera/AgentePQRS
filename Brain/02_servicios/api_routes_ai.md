---
tags:
  - brain/api
---

# API Routes: AI (Inteligencia Artificial)

## Archivo
`backend/app/api/routes/ai.py`

## Prefijo
`/api/v2/ai`

## Descripcion
Endpoints para interactuar con el motor de IA. Permite extraer entidades de un caso y generar borradores legales automaticos.

## Endpoints

### GET /extract/{caso_id}
- **Acceso:** Cualquier usuario autenticado
- **Funcion:** Extrae informacion del caso usando clasificacion hibrida (keywords + Claude)
- **Flujo:**
  1. Lee asunto y cuerpo del caso desde pqrs_casos
  2. Llama `analizar_pqr_documento(asunto, cuerpo)`
  3. Retorna tipo identificado, prioridad sugerida, plazo estimado, cedula, radicado, nombre_cliente, confianza, es_juzgado
- **Servicio usado:** `ai_engine.analizar_pqr_documento()`

### POST /draft/{caso_id}
- **Acceso:** Cualquier usuario autenticado
- **Funcion:** Genera un borrador de respuesta legal para el caso
- **Body:** `{ "save": true/false }` (default false)
- **Flujo:**
  1. Lee el caso completo desde pqrs_casos
  2. Llama `redactar_borrador_legal(dict(caso))`
  3. Si `save=true`, actualiza borrador_respuesta y borrador_estado='PENDIENTE' en la BD
  4. Retorna el texto del borrador
- **Servicio usado:** `ai_engine.redactar_borrador_legal()`

## Dependencias
- `app.services.ai_engine` -- Motor de clasificacion hibrida y generacion de borradores
- `app.core.db.get_db_connection` -- Pool asyncpg con contexto RLS
- `app.core.security.get_current_user` -- Validacion JWT


## Referencias

- [[backend_core]]
- [[service_ai_classifier]]
- [[service_clasificador]]
- [[service_scoring_engine]]
