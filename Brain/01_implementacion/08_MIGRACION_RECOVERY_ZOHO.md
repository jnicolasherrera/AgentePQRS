---
tags:
  - brain/implementacion
---

# Migracion Recovery y Zoho

## Tenant Abogados Recovery

UUID: `effca814-b0b5-4329-96be-186c0333ad4b`

Este es un tenant clave que usa Zoho Mail como proveedor de email y tiene plantillas legales especializadas para cobranza financiera en Colombia.

## Plantillas Especializadas de Recovery

El `ai_engine.py` contiene plantillas hardcodeadas (PLANTILLAS_RECOVERY) para este tenant:

| Problematica                      | Keywords de Deteccion                           |
|-----------------------------------|-------------------------------------------------|
| DEBITOS AUTOMATICOS               | debito, automatico, cobro, banco, convenio      |
| PAZ Y SALVO RAPICREDIT            | paz y salvo, rapicredit, certificado, deuda      |
| SUPLANTACION RAPICREDIT           | suplantacion, fiscalia, delito, estafa, identidad|
| ELIMINACION EN CENTRALES          | centrales, riesgo, datacredito, reporte, eliminar|
| PAZ Y SALVO FINDORSE              | findorse, paz y salvo, soporte                   |

## Flujo de Procesamiento Recovery

1. Worker lee emails del buzon Zoho configurado en `config_buzones`
2. Si el tenant es TENANT_RECOVERY, `redactar_borrador_legal()` busca en PLANTILLAS_RECOVERY
3. Match por problematica en asunto+cuerpo (case insensitive)
4. Si hay match, personaliza la plantilla con nombre del cliente
5. Si no hay match, genera borrador generico con formato legal

## Zoho Mail API

El servicio `ZohoServiceV2` maneja:
- **OAuth2 refresh:** Token auto-renovable con backoff de 90s ante rate limits
- **Lectura:** Fetch de emails no leidos, detalle de mensaje, lista/descarga de adjuntos
- **Envio:** Respuestas con HTML + firma + adjuntos (multipart/form-data)
- **Acuse:** Email HTML con radicado, tipo, fecha limite al ciudadano

## Seed de Plantillas

```bash
# Cargar plantillas en la tabla plantillas_respuesta
python 09_seed_plantillas_recovery.py
```

Esto inserta las plantillas como registros en la tabla `plantillas_respuesta`, permitiendo que el `plantilla_engine.py` las detecte via la funcion `obtener_plantilla()`.


## Referencias

- [[07_MIGRACION_Y_MODO_GOD]]
- [[service_zoho_engine]]
- [[09_ONBOARDING_FLEXFINTECH]]
