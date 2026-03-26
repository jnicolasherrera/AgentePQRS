---
tags:
  - brain/implementacion
---

# Landing Page y Alineacion de Marca

## Directorio

`pqrs-landing/` -- Proyecto Next.js independiente para la landing page publica.

## Stack

- **Framework:** Next.js con TypeScript
- **Estilos:** Tailwind CSS + PostCSS
- **Despliegue:** Vercel
- **Dominio:** flexpqr.com

## Relacion con el Dashboard

| Componente | Dominio            | Infraestructura |
|------------|--------------------|-----------------|
| Landing    | flexpqr.com        | Vercel          |
| Dashboard  | app.flexpqr.com    | VPS + Nginx     |

La landing tiene un boton "Login" / "Iniciar Sesion" que redirige a `app.flexpqr.com`.

## Nginx Fallback

Si el DNS de `flexpqr.com` llega al VPS en lugar de Vercel, Nginx redirige:
```
server {
    listen 443 ssl;
    server_name flexpqr.com www.flexpqr.com;
    return 301 https://flexpqr.com$request_uri;
}
```

## Archivos de la Landing

```
pqrs-landing/
  src/              # Codigo fuente
  public/           # Assets estaticos
  Dockerfile        # Para despliegue containerizado (alternativo)
  next.config.ts
  package.json
  postcss.config.mjs
  tsconfig.json
```
