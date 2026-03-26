# Branding y Diseno -- FlexPQR

## Identidad Visual

- **Nombre comercial:** FlexPQR
- **Nombre legal/interno:** Aequitas
- **Dominio landing:** flexpqr.com (desplegado en Vercel)
- **Dominio app:** app.flexpqr.com (VPS con Nginx SSL)

## Paleta de Colores

Extraida del frontend y componentes de UI:

| Uso                | Color     | Hex       |
|--------------------|-----------|-----------|
| Primary dark       | Azul navy | #021f59   |
| Primary            | Azul      | #035aa7   |
| Accent             | Purpura   | #9D50FF   |
| TUTELA badge       | Rojo      | #DC2626   |
| PETICION badge     | Azul      | #2563EB   |
| QUEJA badge        | Ambar     | #D97706   |
| RECLAMO badge      | Ambar     | #D97706   |
| SOLICITUD badge    | Verde     | #059669   |
| Default badge      | Gris      | #6B7280   |
| SLA VERDE          | --        | VERDE     |
| SLA AMARILLO       | --        | AMARILLO  |
| SLA ROJO           | --        | ROJO      |

## Tipografia

- **Font principal:** Inter (Google Fonts) -- cargada via Next.js font optimization
- **Acuse de recibo:** Arial, sans-serif (email-safe)

## Componentes de Marca

### Acuse de Recibo (Email HTML)
- Header negro (#0a0a0a) con "SistemaPQRS" en purpura (#9D50FF)
- Badge de tipo con color segun la clasificacion
- Cuadro de radicado con fondo gris claro (#f9fafb)
- Footer informativo en gris

### Modal de Re-autenticacion
- Icono de candado en circulo azul navy (#021f59)
- Borde de tarjeta en primary (#035aa7)
- Boton principal en primary (#035aa7)
- Contador de intentos en ambar

## Arquitectura de Landing

- **Tecnologia:** Next.js (directorio `pqrs-landing/`)
- **Despliegue:** Vercel
- **DNS:** flexpqr.com apunta a Vercel, si llega al VPS Nginx redirige a Vercel


## Referencias

- [[08_PROPUESTA_LANDING_Y_ARQUITECTURA]]
- [[11_LANDING_PAGE_BRAND_ALIGNMENT]]
- [[frontend_ui_kanban]]
