# Fix: Zoho Rate-Limiting — Exponential Backoff

**Fecha:** 01/04/2026
**Archivo:** `backend/app/services/zoho_engine.py`
**Severidad:** ALTA — buzón pqrs@arcsas.com.co inoperante

## Problema

El master_worker crea una nueva instancia de `ZohoServiceV2` en cada ciclo de polling (~15s).
El token cache era por instancia → se perdía cada ciclo → cada ciclo forzaba un refresh de token OAuth.
Zoho rate-limitea tras demasiados requests consecutivos.
El backoff era fijo en 90s, insuficiente para que Zoho levante el rate-limit.

**Resultado:** Bucle infinito de rate-limit → wait 90s → rate-limit → buzón nunca se procesa.

## Causa raíz (4 problemas compuestos)

1. **Token cache per-instance:** `_access_token` y `_token_expiry` se inicializaban en `__init__`, se perdían al crear nueva instancia cada ciclo
2. **Backoff class-level pero token instance-level:** Inconsistencia — el backoff sobrevivía entre instancias, el token no
3. **Backoff fijo 90s:** Zoho necesita más tiempo para levantar el rate-limit
4. **Múltiples API calls por ciclo:** Cada email genera: token refresh + folders + messages + detail + attachments = 5+ requests

## Solución implementada

### 1. Token cache a nivel de clase
- `_token_cache` es ahora un `dict` class-level keyed por `refresh_token`
- Sobrevive entre instancias — un token válido (~59 min) se reutiliza en todos los ciclos

### 2. Exponential backoff
- Contador de fallos consecutivos por refresh_token (`_consecutive_failures`)
- Backoff escalonado:
  | Fallo # | Espera |
  |---------|--------|
  | 1 | 90s |
  | 2 | 180s (3 min) |
  | 3 | 600s (10 min) |
  | 4+ | 1800s (30 min) + log CRITICAL |
- Reset automático tras conexión exitosa

### 3. Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ZOHO_MAX_RETRIES` | 4 | Número de fallos antes de log CRITICAL |
| `ZOHO_BACKOFF_BASE_SECONDS` | 90 | Base en segundos para el cálculo de backoff |

### 4. Logging mejorado
- Cada intento logea: `intento N/MAX, backoff Xs`
- Nivel CRITICAL cuando se alcanza MAX_RETRIES
- Segundos restantes de backoff en el mensaje de error

## Impacto esperado

- El token se cachea ~59 min → elimina ~99% de requests innecesarios de token refresh
- Si ocurre rate-limit, el backoff exponencial da tiempo suficiente a Zoho
- El log CRITICAL alerta si un buzón está persistentemente bloqueado
