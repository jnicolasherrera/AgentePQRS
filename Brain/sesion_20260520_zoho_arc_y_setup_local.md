# Sesión 2026-05-20 — Setup local + Zoho ARC pendiente

## Lo que se hizo

### Setup local de AgentePQRS (10/10 servicios up)
- Repo traído desde `/mnt/win-f/proyectos/AgentePQRS` → `~/proyectos/AgentePQRS`.
- `.env` real de prod copiado desde `ubuntu@18.228.54.9:/home/ubuntu/PQRS_V2/.env` (drop-in compose-internal).
- `docker-compose.override.yml` (gitignored) bumpea Confluent 7.3.0 → 7.5.3 (esquiva bug JDK-8253702 / cgroupv2).
- Certs SSL self-signed regenerados (los originales no tenían `.key`); originales preservados como `.crt.orig`.
- Schema + roles de prod aplicados al postgres local, password de `aequitas_worker` matched al `.env`.
- Seed demo cargado: tenant `11111111-1111-1111-1111-111111111111`, 6 usuarios, 18 casos. Super_admin local: `admin@flexpqr.local` / `Admin2026!`.

### Diff staging vs prod (read-only)
- **Schema staging = prod**, sin migraciones funcionales pendientes (solo `99_seed_staging.sql` por diseño).
- **Tenants prod**: Abogados Recovery, Demo FlexPQR, FlexFintech.
- **Tenants staging**: 2 fakes (ARC + Demo). No hay fake de FlexFintech en staging.
- Mapeo: "arcsas" = Abogados Recovery (`abogadosrecovery.com`) · "Flex" = FlexFintech.

### Review git
- `release/tutelas-2026-05-07` corre en prod pero NO está mergeada a `main` (72 commits ahead). Deuda documental.
- Commit `d757ffa` en prod ("drift productivo no-commiteado abr-2026") solo existe en el server.
- DEUDAS_PENDIENTES.md desactualizado — dice que el Motor SLA Sectorial sigue pendiente, pero **ya está aplicado en prod** (mig 14 + columnas + tablas).

### Tutelas (sprint 11/5)
- Migraciones 14, 18-22 aplicadas en prod (confirmado el 20/5).
- `tutelas_view` (matview) con 251 filas. 269 casos TUTELA en prod.
- **D3 (build + force-recreate del backend/frontend con el código sprint Tutelas) NUNCA SE HIZO**. Imágenes backend/frontend en prod tienen 6 semanas.
- Bridge cron pausado el 11/5 sigue pausado el 20/5 — correcto, mientras Zoho esté roto.

## ✅ RESUELTO 2026-05-21 — Token Zoho ARC

**Ingesta restaurada.** Se generó un Self Client nuevo en Zoho
(`1000.TKA5AEC...`) y se canjeó un code por refresh_token con **scopes completos**:
`VirtualOffice.messages.READ,messages.CREATE,messages.UPDATE,folders.READ,accounts.READ`.
Se actualizaron `azure_client_id` / `azure_client_secret` / `zoho_refresh_token`
en `config_buzones` (ARC) y se reinició `master_worker_v2`. Worker procesando sin
errores, 5 casos ARC en 24h, último caso 2026-05-21 14:19 (antes 2026-05-08).

Nota: el primer token se generó solo con scopes READ → daba `INVALID_OAUTHSCOPE`
en `send_reply` (POST /messages) y `markAsRead`. El markAsRead es crítico porque
el fetch filtra `status:unread` — sin marcar leído, re-lee la cola. Por eso se
regeneró con CREATE+UPDATE.

**Pendiente:** rotar el client_secret Zoho que se vio en chat (`568f75dac...`).
Los `self_client*.json` se shredearon del repo y se agregaron a `.gitignore`.

### Histórico del incidente (resuelto)

ARC estuvo **13 días sin ingerir un solo caso** (2026-05-08 → 2026-05-21).

Causa raíz real (no era rate-limit como decía el log): el `refresh_token` en
`config_buzones.zoho_refresh_token` para `pqrs@arcsas.com.co` **está revocado o
expirado**. El worker pide token → Zoho responde sin `access_token` → `KeyError`
→ reintenta → eventualmente Zoho rate-limitea el endpoint de auth.

El user creó un **Self Client nuevo** en `api-console.zoho.com` con:
- client_id prefix: `1000.TKA5AEC...`
- client_secret prefix: `568f75dac...`

Pasos pendientes (todos requieren que el user genere un code FRESCO en la consola):

1. User: Generate Code → Create → Download JSON. JSON va a `~/Descargas/` o `~/proyectos/AgentePQRS/` como `self_client (N).json`.
2. Script listo en `/tmp/zoho_finish.sh` (se borró al cerrar — recrearlo si hace falta) que:
   - Lee `client_id`, `client_secret`, `code` del JSON más reciente.
   - Canjea code → refresh_token en `accounts.zoho.com/oauth/v2/token` (US region — confirmado).
   - UPDATE `config_buzones` SET `azure_client_id`, `azure_client_secret`, `zoho_refresh_token` WHERE `email_buzon = 'pqrs@arcsas.com.co'`.
   - Restart `master_worker_v2` en prod.
   - Verifica logs y count de casos ARC.
3. Confirmar que entra ingesta (esperar 1-2 min después del restart, ver primer caso nuevo).
4. Re-habilitar el bridge cron en prod (descomentar la línea `# PAUSED ...`).
5. Ejecutar D3: build + force-recreate del backend/frontend con sprint Tutelas.

## Después de Zoho destrabado

### Cambios de tenants en prod (las 3 tareas originales del user)
- **ARCSAS** → cambiar `regimen_sla` de `'GENERAL'` a `'FINANCIERO'` (la infra ya está, es solo UPDATE).
- **FlexFintech** → cambios concretos pendientes de definir.
- **Cliente nuevo** → datos pendientes de definir (nombre, dominio, régimen, buzón).

### Deudas técnicas anotadas hoy
- Renombrar columnas `azure_client_id`/`azure_client_secret` → algo neutral (`provider_client_id`/`_secret`) o crear `zoho_*` aparte. Hoy reutilizan las azure_* para Zoho — confunde.
- Rotar el `client_secret` Zoho que se vio en este chat (`568f75dac...`).
- Actualizar `DEUDAS_PENDIENTES.md` (SLA sectorial ya no es deuda).

## Notas operativas

- Stack local: 10/10 services up, fue restaurado el 20/5 16:30 — sigue corriendo (Up 2h al cierre).
- Para liberar RAM hasta mañana: `cd ~/proyectos/AgentePQRS && docker compose stop`.
- Para retomar: `docker compose up -d` (volúmenes persisten, mismos datos).
- Paola Lombana (ARC) ya está al tanto del bloqueo de Zoho.
