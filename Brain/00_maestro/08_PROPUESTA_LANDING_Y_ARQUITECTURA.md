---
tags:
  - brain/maestro
---

# Propuesta Landing y Arquitectura -- FlexPQR

## Landing Page (flexpqr.com)

### Estado Actual
- Directorio: `pqrs-landing/`
- Framework: Next.js con TypeScript
- Despliegue: Vercel
- Proposito: Sitio publico comercial con boton Login hacia app.flexpqr.com

### Arquitectura de DNS y Routing

```
flexpqr.com         -> Vercel (landing page publica)
www.flexpqr.com     -> Vercel (redirect)
app.flexpqr.com     -> VPS (Nginx -> frontend_v2:3000 + backend_v2:8000)
```

### Nginx Routing (app.flexpqr.com)

| Path                    | Destino                            | Notas                     |
|-------------------------|------------------------------------|---------------------------|
| /api/v2/stream/         | backend_v2:8000                    | SSE, buffering off        |
| /api/                   | backend_v2:8000                    | API REST, timeout 120s    |
| /                       | frontend_v2:3000                   | Dashboard Next.js         |

### Security Headers (Nginx)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=63072000; includeSubDomains`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

### Vision de Diseno
- Estetica "Premium/Glassmorphism" con animaciones dinamicas
- Modo oscuro reactivo
- Herramientas planificadas: Google Stitch (IA Text-to-UI), Magic UI MCP, Figma MCP
