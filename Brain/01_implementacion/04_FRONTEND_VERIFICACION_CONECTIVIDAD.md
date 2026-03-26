# Frontend: Verificacion de Conectividad

## URL de Acceso

- **Desarrollo local:** http://localhost:3002
- **Produccion:** https://app.flexpqr.com

## Variable de Entorno Critica

```
NEXT_PUBLIC_API_URL=https://app.flexpqr.com
```

Esta variable se compila en build-time dentro del Dockerfile del frontend. Todos los requests API van a `${NEXT_PUBLIC_API_URL}/api/v2`.

## Flujo de Autenticacion

1. Usuario ingresa email/password en `/login`
2. `POST /api/v2/auth/login` retorna `access_token` + `user` object
3. Token se guarda en Zustand store con persistencia localStorage (`pqrs-v2-auth`)
4. Axios interceptor auto-adjunta `Authorization: Bearer {token}` en cada request

## Re-Autenticacion Inline

Cuando el token expira (default 480 min = 8 horas):

1. Backend responde 401
2. Axios interceptor dispara evento `FLEXPQR_SESSION_EXPIRED`
3. `SessionGuardProvider` captura el evento y muestra `ReAuthModal`
4. Usuario ingresa su password (email prefillado)
5. Si es correcto: nuevo token se guarda, requests pendientes se reintentan
6. Si falla 3 veces: logout forzado, redirect a `/login`

## SSE (Server-Sent Events)

```
GET /api/v2/stream/listen?token={jwt}
```

- Token se pasa como query param (no header, porque SSE no soporta headers custom)
- Canal Redis: `pqrs.events.{tenant_id}`
- super_admin se suscribe con pattern `pqrs.events.*`
- analista solo recibe casos asignados a el (`asignado_a` == usuario_id)
- Keepalive ping cada 30s para evitar que proxies cierren la conexion

## Estructura del Layout

```
RootLayout (layout.tsx)
  -> SessionGuardProvider (wrapper global)
    -> {children} (paginas)
    -> ReAuthModal (condicional si sesion expiro)
```
