# Incidente INC-2026-04-27 — Master Worker pool asyncpg muerto

## Línea de tiempo

- **2026-04-14 20:48 UTC** — DB Postgres reinició (causa exacta pendiente: posiblemente auto-update Docker, OOM, o reboot EC2). Único evento `starting PostgreSQL 15.17 ... database system is ready to accept connections` en logs de los últimos 14 días.
- **2026-04-14 20:48 → 2026-04-27 16:46 UTC** — Master worker en bucle "connection is closed" sin reconectar pool asyncpg. **~12 días 20 horas de gap total.**
- **2026-04-27 ~10:20 (hora local CO)** — Paola Lombana (ARC) reporta vía WhatsApp que no ve casos nuevos en el aplicativo.
- **2026-04-27 ~16:46 UTC** — `docker restart pqrs_v2_master_worker` aplicado. Fix exitoso.

## Causa raíz

`backend/master_worker_outlook.py` no implementa reconnect logic para el pool asyncpg ni para la conexión principal (`conn = await asyncpg.connect(DATABASE_URL)` en línea 149). Cuando la DB reinició, el pool y `conn` quedaron con sockets cerrados.

El handler de errores del loop principal capturaba la excepción pero solo logueaba `str(e)` ("connection is closed") y reintentaba sobre el mismo handle muerto, sin recrear el pool ni la conexión.

Verificación adicional: `grep -E 'Traceback|asyncpg|Pool|reconnect|InterfaceError|ConnectionDoesNotExistError'` en logs del worker durante el periodo del incidente devolvió **0 matches** — el handler se traga el traceback completo. Diagnóstico ciego.

## Detección

**NO automatizada.** El usuario final (Paola Lombana de Abogados Recovery) detectó por ausencia de casos nuevos en el aplicativo y avisó por WhatsApp. **Gap de detección: ~12 días 20 horas.**

Esto es señal directa de la ausencia de `DT-34` (alerting de baseline `MAX(created_at)` reciente).

## Impacto

- **ARC** (cliente productivo): 0 casos ingresados durante el gap. Total ARC pre-incidente: 135. Post-restart: 141 (+6 casos en primeros 30 min, incluyendo **2 tutelas** con plazo 48h).
- **FlexFintech** (`clientes@flexfintech.com`): misma situación. El worker procesa todos los buzones en el mismo loop, todos quedaron afectados.
- **Demo**: misma situación.
- **Datos**: 0 casos perdidos en DB (no hubo corrupción ni rollback). Pero **RIESGO** de correos no ingresados si Zoho/Outlook los marcó como leídos durante intentos fallidos del worker zombi.

### Detalle del riesgo de correos huérfanos

- Outlook: el worker llama `mark_as_read` (PATCH a Graph API) tras procesar exitosamente. Durante el incidente NO procesó nada, así que en teoría los correos siguen como `isRead=false` y serán traídos por `$filter=isRead eq false` ahora que el worker está sano.
- Zoho: el flujo `get_message_detail` puede marcar como leído al hacer fetch del contenido (comportamiento estándar de la API). Si el worker hizo fetch parcial antes de fallar, esos correos podrían estar marcados como leídos sin caso asociado.
- Empíricamente: el email más viejo procesado en los primeros 30 min post-restart fue del 2026-04-26 (1 día atrás), no de hace 12 días. → indicio de que el inbox NO está re-entregando los 12 días de backlog.

## Mitigación inmediata

```bash
ssh flexpqr-prod "docker restart pqrs_v2_master_worker"
```

→ Reabrió pool asyncpg, procesó backlog visible.

**Validación post-fix:**

| Métrica | Valor |
|---|---|
| Casos ARC ingestados en 30 min | 6 (3 PETICION, 2 TUTELA, 1 SOLICITUD) |
| Errores `connection is closed` post-banner | 0 |
| Adjuntos PDF guardados a SharePoint | OK (incluye autos cautelares y oficios judiciales) |
| Pipeline completo (clasif Claude + dedup + DB insert) | Funcional |

## Auditoría pendiente

**Paola Lombana auditará manualmente** el buzón `pqrs@arcsas.com.co` entre 2026-04-14 y 2026-04-26 para identificar correos huérfanos (recibidos pero no ingestados). Mismo proceso para los buzones FlexFintech (`clientes@flexfintech.com`) y Demo si aplica.

Si encuentra correos huérfanos:
1. Marcar como no leído en Zoho/Outlook (toggle).
2. Esperar al siguiente ciclo del worker (~minutos).
3. Verificar en DB que el caso entró.

## Mitigación BRIDGE aplicada

Cron horario en prod **y** staging que:
1. Calcula `EXTRACT(EPOCH FROM (NOW() - MAX(fecha_recibido)))/3600` para ARC.
2. Si supera 4 horas → loguea alerta y aplica `docker restart pqrs_v2_master_worker` automáticamente.

Ver `scripts/check_ingestion.sh` en este repo y `Brain/DEUDAS_PENDIENTES.md` DT-32, DT-33, DT-34 para fix de fondo.

**El cron es BRIDGE temporal, no fix.** DT-32/33/34 sigue pendiente como sprint.

## Fix de fondo (sprint dedicado próximos 7 días)

Ver:
- DT-32 — Pool asyncpg sin reconnect en `master_worker_outlook.py` (CRÍTICA)
- DT-33 — Healthcheck funcional faltante en workers (ALTA)
- DT-34 — Alerting `MAX(created_at)` reciente faltante (ALTA)
- DT-35 — Dedup check después de Claude API en master_worker (MEDIA, optimización)

## Lecciones aprendidas

1. **Docker "Up" no significa "funcional".** Healthcheck por proceso es insuficiente; necesita validar conectividad real (`SELECT 1` contra DB).
2. **Sin alerting de baseline** (ej: `MAX(created_at)` reciente), un incidente silencioso puede durar semanas sin detección.
3. **Errores en pool DB deben recrear pool, no solo loguear.** Un handler que se traga la excepción y reintenta sobre handle muerto es peor que crashear (al menos crashear levanta `restart: unless-stopped`).
4. **Confiar en notificaciones de usuarios externos como detección es señal de falta de monitoreo proactivo.** Un cliente reportando "no veo casos" es señal tardía. El sistema debió alertar internamente al equipo a las 4-6 horas del primer fallo.
5. **El dedup multi-capa salvó el incidente del backlog**: partial UNIQUE index `(cliente_id, external_msg_id)` + fallback `(cliente_id, email_origen, hora)` + pre-check Python `SELECT 1`. Permitió aplicar restart sin riesgo de duplicar casos. Mantener este diseño.
