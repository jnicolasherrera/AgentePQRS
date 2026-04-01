# Fix: Flujo debe_cambiar_password en Login

**Fecha:** 01/04/2026
**Archivos modificados:**
- `frontend/src/components/ui/ForceChangePasswordModal.tsx` (nuevo)
- `frontend/src/components/ui/SessionGuardProvider.tsx` (modificado)

**Severidad:** ALTA — ningún usuario de Abogados Recovery podía cambiar su password temporal

## Problema

Todos los usuarios de Abogados Recovery tenían `debe_cambiar_password = true` desde su creación (Mar 4-6, 2026). El backend retornaba correctamente el flag en la respuesta de login, pero:

1. El frontend almacenaba el flag pero **nunca actuaba sobre él**
2. No existía componente de cambio de password forzado
3. Los usuarios nunca fueron redirigidos a cambiar su password temporal

## Causa raíz

- **Backend:** Correcto — retorna 200 + token + `debe_cambiar_password: true`
- **Backend:** Endpoint `POST /auth/change-password` existía y funcionaba
- **Frontend:** `authStore.ts` almacenaba `debe_cambiar_password` pero ningún componente lo leía
- **Frontend:** No existía modal ni página de cambio de password forzado

## Solución

### ForceChangePasswordModal.tsx (nuevo)
- Modal bloqueante que aparece cuando `debe_cambiar_password = true`
- Sigue el mismo patrón visual que `ReAuthModal.tsx`
- Validación: mínimo 8 caracteres + confirmación de password
- Llama a `POST /auth/change-password` con el token existente
- Al completar, actualiza el estado local (`debe_cambiar_password = false`)

### SessionGuardProvider.tsx (modificado)
- Ahora importa `useAuthStore` y `ForceChangePasswordModal`
- Detecta `isAuthenticated && user.debe_cambiar_password === true`
- Muestra `ForceChangePasswordModal` como overlay bloqueante
- El modal desaparece automáticamente al cambiar el password (estado reactivo)

## Notas
- El backend NO fue modificado — ya funcionaba correctamente
- No se modificaron passwords en DB
- No se tocaron usuarios ni tenant de Abogados Recovery
