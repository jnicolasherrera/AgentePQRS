---
tags:
  - brain/frontend
---

# Frontend: Contexto y SSE

## Arquitectura de Estado

### Zustand Auth Store
- **Archivo:** `frontend/src/store/authStore.ts`
- **Store:** `useAuthStore` con middleware `persist` (localStorage key: `pqrs-v2-auth`)
- **Estado:** token, user (AuthUser), isAuthenticated
- **Acciones:** setAuth, clearAuth, login, logout
- **AuthUser:** id, email, nombre, rol, tenant_uuid, cliente_nombre, debe_cambiar_password

### Axios Instance
- **Archivo:** `frontend/src/lib/api.ts`
- **Base URL:** `${NEXT_PUBLIC_API_URL}/api/v2`
- **Request interceptor:** Lee token de localStorage y agrega `Authorization: Bearer` header
- **Response interceptor:** En 401, dispara `FLEXPQR_SESSION_EXPIRED` custom event (no redirige)

## SSE (Server-Sent Events)

### Conexion
```
GET /api/v2/stream/listen?token={jwt_token}
```
El token se pasa como query parameter porque EventSource no soporta headers custom.

### Eventos Recibidos
- `new_pqr` -- Nuevo caso clasificado e insertado en DB
- `ping` -- Keepalive cada 30 segundos

### Filtrado por Rol
- **super_admin:** Recibe eventos de todos los tenants
- **admin:** Recibe eventos de su tenant
- **analista:** Recibe solo eventos de casos asignados a el

## Re-Autenticacion Inline

### Flujo
1. Request falla con 401
2. Axios interceptor dispara `FLEXPQR_SESSION_EXPIRED` con el `originalRequest`
3. `useSessionGuard` hook escucha el evento
4. `SessionGuardProvider` muestra `ReAuthModal`
5. Usuario ingresa password
6. Si es exitoso, dispara `FLEXPQR_REAUTH_SUCCESS` con `newToken`
7. `useSessionGuard` reintenta requests pendientes con el nuevo token

### Componentes Involucrados
- **SessionGuardProvider** (`frontend/src/components/ui/SessionGuardProvider.tsx`) -- Wrapper en layout raiz
- **ReAuthModal** (`frontend/src/components/ui/ReAuthModal.tsx`) -- Modal overlay con form de password
- **useSessionGuard** (`frontend/src/hooks/useSessionGuard.ts`) -- Hook que gestiona la cola de requests

### Seguridad del Modal
- 3 intentos maximos antes de logout forzado
- Email prefillado (read-only) del usuario actual
- Toggle de visibilidad de password
- Boton de "Cerrar sesion" como alternativa


## Referencias

- [[api_routes_stream]]
- [[frontend_ui_kanban]]
- [[frontend_tablas_interactivas]]
