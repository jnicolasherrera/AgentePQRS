# Deudas técnicas registradas

## Motor SLA sectorial — deploy pendiente

**Estado:** dormido en `main` desde 2026-04-13
**Commits involucrados:**
- `c26bcee` — feat(sla): motor SLA sectorial — régimen FINANCIERO 8 días SFC
- `0713f74` — fix(sla): agregar tabla `festivos_colombia` 2026 a migración 14

### Por qué está dormido

La migración `aequitas_infrastructure/database/14_regimen_sectorial.sql` (169 líneas) **nunca corrió** contra la DB de producción `pqrs_v2`. El código en main hace queries a estructuras que no existen:

| Objeto | Tipo | Dónde se usa |
|---|---|---|
| `festivos_colombia` | tabla | `backend/app/core/models.py:259` (clase ORM huérfana, sin queries) |
| `sla_regimen_config` | tabla | `backend/app/api/routes/admin.py:487` |
| `clientes_tenant.regimen_sla` | columna | `backend/app/api/routes/admin.py:437, 462, 481` |

Ninguna existe en `pqrs_v2` hoy (verificado 2026-04-13 via `information_schema`).

> **Nota de inconsistencia documental — RESUELTA 2026-04-23**: La versión previa de este texto decía: "SPRINT_SLA_SECTORIAL.md dice que el sprint se aplicó a 'Staging 18.228.54.9' el 8-abril, pero esa IP es producción. Resolver en sesión dedicada". La sesión dedicada ocurrió el 2026-04-23 dentro del sprint Tutelas (ver `Brain/sprints/SPRINT_TUTELAS_S123_ANALISIS_DRIFT.md`). Resultado: 18.228.54.9 es prod y **la migración 14 nunca corrió ahí** (verificado con `to_regclass('festivos_colombia')=f`, SP ausente, trigger ausente). `SPRINT_SLA_SECTORIAL.md` fue corregido en el mismo sprint. La deuda principal (aplicar 14 a prod) sigue viva; ver "Plan de deploy futuro" más abajo.

### Endpoints afectados (en disco, NO en runtime)

4 rutas nuevas en `backend/app/api/routes/admin.py` (+227 líneas respecto al runtime actual `97f239e`):

- `GET /admin/regimen-sla/{cliente_id}` → línea ~430
- `POST /admin/regimen-sla/{cliente_id}` → línea ~444
- Otros 2 endpoints auxiliares de config

**Estado protegido**: los containers `pqrs_v2_backend` corriendo hoy están en commit `97f239e` que NO tiene estas rutas. Los endpoints existen solo en disco. Rebuildear `backend` sin aplicar migración primero → `500 column "regimen_sla" does not exist` al primer click.

### Plan de deploy futuro (cuando se aborde)

Orden obligatorio:

1. **Leer migración 14 completa** (169 líneas) y validar que no tiene `DROP`, `TRUNCATE`, `UPDATE` masivo, ni `FOREIGN KEY` contra tablas grandes.
2. **Backup DB pre-deploy** (`docker exec pqrs_v2_db pg_dump -F c`).
3. **Aplicar migración 14 contra `pqrs_v2`** manualmente:
   ```bash
   docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 < aequitas_infrastructure/database/14_regimen_sectorial.sql
   ```
4. **Verificar que las 2 tablas y la columna nueva existen**:
   ```sql
   SELECT count(*) FROM festivos_colombia;
   SELECT count(*) FROM sla_regimen_config;
   SELECT column_name FROM information_schema.columns WHERE table_name='clientes_tenant' AND column_name='regimen_sla';
   ```
5. **Smoke test de queries directas** de `admin.py` contra la DB real.
6. **Recién entonces rebuild de `pqrs_v2_backend`** con `docker compose up -d --no-deps --build backend`.
7. **Smoke test funcional** de los endpoints admin vía curl con JWT de super_admin.
8. **Comunicar a Paola (Recovery)** que hay tab nuevo de "Régimen SLA" disponible en admin.
9. **Ideal**: correr todo el ciclo primero en staging EC2 (`15.229.114.148`) con datos clonados de Recovery.

### Complejidad

**Medio-alta.** No es urgente — hoy nadie usa la feature. El bloqueo principal es validar que el SQL no tiene sorpresas (lo único que leí confirmado es la sección de `festivos_colombia` del commit `0713f74`, líneas 7-36). El resto del archivo (líneas 38-168) requiere lectura previa.

### Referencia cruzada

- Análisis forense completo del drift: ver `Brain/CHANGELOG.md` entrada `2026-04-13 (deploy nocturno)`.
- Regla anti-drift que previno este deploy en caliente: `Brain/00_DIRECTIVAS_CLAUDE_CODE.md` sección 3.5.
- Bug separado pendiente: visualización de `borrador_respuesta` en frontend pestaña Casos (tipo TS `Caso` no declara el campo).

---

## 2026-04-14 — Deudas descubiertas durante fix FirmaModal

### Bug UX del FirmaModal (no bloqueante)

**Severidad**: Baja (cosmético)
**Archivo**: `frontend/src/components/ui/firma-modal.tsx`
**Líneas**: 33-40

**Descripción**: Después de confirmar el envío, el modal se cierra pero la notificación flotante no aparece visiblemente (o aparece por menos de 1 segundo). Además, el código siempre dispara `tipo='exito'` aunque `res.data.enviados` sea 0, lo cual produce notificaciones verdes engañosas del tipo *"0 respuesta(s) enviada(s) correctamente"* cuando en realidad el envío falló.

**Fix propuesto**:

```typescript
if (res.data.enviados === 0 && res.data.errores.length > 0) {
  setNotifEnvio({
    tipo: 'error',
    mensaje: `Envío falló: ${res.data.errores[0].motivo}`
  });
} else {
  setNotifEnvio({
    tipo: 'exito',
    mensaje: `${res.data.enviados} respuesta(s) enviada(s) correctamente`
  });
}
```

**Cómo verificar**: después del fix, hacer smoke test desactivando `DEMO_GMAIL_USER` del backend y confirmar que aparece notificación roja con error específico.

---

### Kafka containers Exited hace 5+ días

**Severidad**: Media (investigar por qué nadie se dio cuenta)

**Evidencia**:
```bash
docker ps -a | grep kafka
pqrs_staging_kafka  Exited (1) 5 days ago
pqrs_v2_kafka       Exited (1) 5 days ago
```

El backend tiene manejo gracioso: intenta 5 veces conectarse a Kafka al arrancar, loguea `"Kafka no disponible — API arranca sin producer"`, y sigue funcionando. Los `GET`/`POST` de `/api/v2/*` se atienden normalmente porque el flujo principal (auth, casos, stats, SSE via Redis) no depende de Kafka.

Kafka se usaba (presumiblemente) para publicar eventos secundarios a un event bus. Sin Kafka, esos eventos no se publican, pero no rompen el flujo principal.

**Acción pendiente**:

1. Investigar qué consumidores dependen de los eventos Kafka.
2. Decidir si reactivar Kafka o si el event bus es deuda técnica a deprecar.
3. Ajustar monitoreo para detectar cuando containers críticos quedan `Exited`.

---

## 2026-04-15/16 — Deudas hardening AWS

Generadas durante el sprint de hardening AWS documentado en `fixes/HARDENING_AWS_ABRIL_2026.md`. Todas son para el camino a Bancolombia; ninguna bloquea operación actual.

### DT-1 — SSE-KMS en CloudTrail (CMK dedicada)

**Severidad**: Media (compliance bancaria).
**Estado actual**: CloudTrail `flexpqr-trail` usa cifrado SSE-S3 (AES-256 gestionado por AWS) en los logs del bucket `flexpqr-cloudtrail-logs`. Funciona y cumple el mínimo, pero no da control granular sobre quién puede descifrar los logs.
**Gap**: auditores bancarios típicamente piden SSE-KMS con CMK dedicada (Customer Managed Key) para que la propia organización controle la key y su rotación, y el log de uso de la key quede también en CloudTrail. Habilita separación de funciones (quien opera EC2 ≠ quien descifra logs de auditoría).
**Plan**: crear CMK `flexpqr/cloudtrail` en KMS → policy de la CMK que permita a CloudTrail cifrar y solo a auditor + root descifrar → editar trail para usar SSE-KMS con esta CMK → verificar que los logs siguientes están cifrados con la CMK.
**Esfuerzo**: ~30 minutos.
**Responsable**: Nico.
**Trigger**: antes de primera auditoría formal de Bancolombia o cuando se active.

---

### DT-2 — GuardDuty multi-región

**Severidad**: Media.
**Estado actual**: GuardDuty activo solo en `sa-east-1` (trial 30 días).
**Gap**: una cuenta AWS comprometida no necesariamente opera desde la región donde están los workloads. Un atacante que roba credenciales puede lanzar instancias en `us-east-1` sin que GuardDuty de `sa-east-1` lo vea. La best practice es GuardDuty en todas las regiones donde la cuenta puede operar.
**Plan**: activar GuardDuty en `us-east-1`, `us-west-2`, `eu-west-1`, `ap-southeast-1` (mínimo), idealmente todas las regiones. Configurar una región como "administrador delegado" para centralizar findings.
**Esfuerzo**: ~10 minutos por región (consola web).
**Responsable**: Nico.
**Trigger**: antes del fin del trial de 30 días en `sa-east-1` para consolidar decisión de si continuar pagando.

---

### DT-3 — Migrar `*FullAccess` a policies custom mínimas

**Severidad**: Alta (least privilege).
**Estado actual**: `flexpqr-deploy` tiene `AmazonEC2FullAccess`, `AmazonS3FullAccess`, `CloudWatchFullAccess`. Funciona pero viola least privilege — el user puede, por ejemplo, eliminar la EC2 de producción o cualquier bucket S3 de la cuenta.
**Gap**: auditores bancarios miran directamente las policies attached a los users de producción. `*FullAccess` es señal de alerta roja.
**Plan**: identificar las operaciones exactas que el user necesita (ssh via SSM Session Manager, subir/bajar archivos a buckets específicos, leer métricas CloudWatch, restart de instancias). Escribir 3 policies custom con solo esas acciones, scoped a los ARNs específicos (instance ARN, bucket ARNs, log group ARNs). Attach las custom, detach las `*FullAccess`.
**Esfuerzo**: ~1 hora (incluye testing de que nada se rompe).
**Responsable**: Nico.
**Trigger**: antes de due diligence técnico de Bancolombia.

---

### DT-4 — AWS IAM Identity Center cuando sumen Dante/Martín

**Severidad**: Media-alta (compliance + segregación de funciones).
**Estado actual**: acceso AWS solo por Nico (root + `flexpqr-deploy`). Dante y Martín no tienen acceso formal a la consola AWS.
**Gap**: compartir credenciales root es anti-patrón. Crear IAM users individuales funciona pero dificulta rotación y desactivación. Identity Center (antes AWS SSO) resuelve esto con login federado + asignación de permisos por grupo.
**Plan**: crear directorio Identity Center → crear grupos (`Admins`, `Developers`, `ReadOnly`) → asignar permission sets a cada grupo → invitar a Dante y Martín con acceso a los grupos correspondientes. Cuando salga alguien del equipo, se borra de Identity Center y queda sin acceso a AWS automáticamente.
**Esfuerzo**: ~45 minutos.
**Responsable**: Nico.
**Trigger**: cuando Dante o Martín necesiten acceso directo a AWS (por ahora no lo necesitan).

---

### DT-5 — Rotación automática de access keys

**Severidad**: Media (best practice).
**Estado actual**: Access Key de `flexpqr-deploy` generada el 15-abril-2026, sin fecha de rotación planificada.
**Gap**: AWS recomienda rotar access keys cada 90 días máximo. Muchos frameworks de compliance (incluyendo los que auditan los bancos colombianos) lo exigen.
**Plan**: script trimestral (cron en EC2 o GitHub Actions) que:
  1. Crea una Access Key nueva para `flexpqr-deploy`.
  2. Actualiza el secret en el orquestador de secretos (cuando exista; por ahora, manualmente en `~/.aws/credentials` de la máquina de Nico).
  3. Espera 24 horas para asegurar que nadie usa la vieja.
  4. Elimina la Access Key vieja.
**Esfuerzo**: ~2 horas (implementar + probar).
**Responsable**: Nico.
**Trigger**: antes de la primera rotación manual (objetivo: mediados de julio 2026 para mantener ciclo trimestral).

---

### DT-6 — Retención CloudTrail 10 años (solo si Bancolombia lo pide)

**Severidad**: Depende del cliente.
**Estado actual**: lifecycle del bucket `flexpqr-cloudtrail-logs` con expiración a los 2555 días (7 años), alineado con normativa SARLAFT general.
**Gap**: algunos bancos exigen 10 años de retención para todos los audit logs relacionados con procesamiento de información de clientes bancarios.
**Plan**: si Bancolombia u otro cliente bancario lo exige en el contrato → ajustar lifecycle del bucket de 2555 días a 3650 días. Evaluar costo Glacier a 10 años (muy bajo pero no cero). Documentar en el contrato.
**Esfuerzo**: ~5 minutos (1 edit en lifecycle policy).
**Responsable**: Nico.
**Trigger**: cláusula contractual con Bancolombia o equivalente.

---

### DT-7 — Push commit Brain `0307fa1` al remoto

**Severidad**: Baja-media (resiliencia documental).
**Estado actual**: commit `0307fa1` del Brain está en la branch `develop` local, sin push al remoto desde el 14-abril. La auditoría de Dante y el sprint de hardening viven solo en la máquina de Nico.
**Gap**: si la máquina de Nico se rompe mañana, se pierden ~3 días de memoria operacional del proyecto. Riesgo bus-factor sobre documentación, no solo sobre infraestructura.
**Plan**: `cd /mnt/f/proyectos/AgentePQRS && git checkout develop && git push origin develop`. Verificar que aparece en GitHub. Considerar merge a main si el Brain ya es oficial.
**Esfuerzo**: ~2 minutos.
**Responsable**: Nico (cuando termine el sprint actual sin riesgos).
**Trigger**: fin de sesión del 16-abril-2026.

---

### DT-8 — Guardrail `docker-compose.yml` prod vs local

**Severidad**: Alta (riesgo de reabrir los 9 puertos cerrados por Dante).
**Estado actual**: el compose de producción tiene todos los puertos críticos bindeados a `127.0.0.1` (fruto del hardening del 14-abril) y env vars Gmail específicas. El compose local los expone a `0.0.0.0` y no tiene esas env vars. No hay nada que impida copiar local sobre prod y borrar silenciosamente el hardening.
**Gap**: un `scp docker-compose.yml server:~/PQRS_V2/` apurado un día cualquiera borra 2 horas de trabajo de seguridad sin aviso. Ni un lint, ni un hook, ni un log lo detecta.
**Plan**:
  1. **Corto plazo (~15 min)**: crear `README.DEPLOY.md` en la raíz del repo con el diff esperado documentado y la regla "NO sincronizar compose entre entornos sin diff aprobado".
  2. **Mediano plazo (~2 horas)**: script `deploy/verify_compose_diff.sh` que lee compose local y el de prod (via SSH), aborta si detecta líneas con puertos que no empiezan por `127.0.0.1:` o env vars de prod que faltan en local, imprime diff legible, y exige confirmación `yes` explícita antes de continuar.
  3. **Largo plazo**: mover todo deploy a GitHub Actions con estado declarativo, no file sync.
**Esfuerzo**: corto plazo 15 min, mediano 2 h.
**Responsable**: Nico.
**Trigger**: próximo deploy que toque docker-compose.yml (hacer el README antes de cualquier edit).

---

### Credenciales a rotar (expuestas durante sesión)

Durante la sesión de hardening aparecieron logs mostrando credenciales activas. No son deudas estructurales sino tareas específicas de rotación:

| Credencial | Servicio | Prioridad |
|---|---|---|
| App Password Gmail `democlasificador@gmail.com` | SMTP demo | Alta |
| Password Redis de `pqrs_v2_redis` | Cache/SSE | Alta |
| Credenciales MinIO `adminminio/adminpassword` | Object storage | Media (ya eran conocidas) |

Patrón de rotación sin downtime documentado en `fixes/HARDENING_AWS_ABRIL_2026.md`.

---

## 2026-04-23 — Deudas descubiertas durante sprint Tutelas S1+S2+S3

### DT-19 — Drift detection periódico staging vs prod vs repo

**Origen:** sesión del 2026-04-23 detectó drift severo entre 3 fuentes (prod 18.228, staging 15.229, SQLs del repo). Ver `Brain/sprints/SPRINT_TUTELAS_S123_BLOQUEANTE_DRIFT_REPO.md`.

**Severidad:** Media — no bloqueante mientras nadie deploye, pero se van acumulando cambios silenciosos cada vez que alguien toca prod directo.

**Propuesta:** cron semestral (o por sprint relevante) que:
1. Ejecuta `pg_dump --schema-only` contra prod y staging.
2. Compara con el baseline vigente en `migrations/baseline/`.
3. Alerta por Slack/email si detecta divergencias, con diff resumido.

**Baseline de referencia:** `migrations/baseline/prod_schema_20260423_1600.sql` (SHA256 `3d0bc89fd69b35819842f3e0db9eacf587cc4935cfce9bf031af339a17c14044`).

**Responsable propuesto:** Nico + agente de mantenimiento.

---

### DT-20 — Rotación de credenciales productivas ARC expuestas en repo

**Origen:** `05_multi_provider_buzones.sql` (y su copia histórica en main) contiene hard-coded los siguientes secretos productivos de ARC (`effca814-...`):

| Secreto | Dónde |
|---|---|
| `azure_client_id` | línea 29 |
| `azure_client_secret` | línea 30 |
| `zoho_refresh_token` | línea 31 |
| `zoho_account_id` | línea 32 |

Adicionalmente, UUIDs productivos de FlexFintech y Cliente2 en `04_multi_tenant_config_v2.sql`.

**Severidad:** Alta por cumplimiento. Baja por superficie real (repo privado, 1 owner). Nico decidió: **no bloquea el sprint Tutelas; ventana de 7 días para rotar.**

**Plan:**
1. Rotar en Zoho el refresh_token (`1000.1b69662a184a373bc3171bb906733499...`).
2. Rotar en Azure Portal el client_secret (`568f75dac62845e5d8e4caff0deef488c2896803cd`).
3. Actualizar `.env` de prod con nuevos valores.
4. Verificar que buzón ARC sigue sincronizando con las nuevas credenciales.
5. **Rotar también `ANTHROPIC_API_KEY` de staging** (`.env` del server `flexpqr-staging` quedó inválido durante smoke E2E — devolvió 401). Sustituir por una nueva.
6. **Revocar la key ad-hoc** que Nico generó para los smokes #2 y #3 del sprint Tutelas (ya cumplió su propósito).
7. Una vez confirmada rotación, avanzar a DT-21 (purga historia git).

**Deadline:** **2026-04-30** (3 días desde 2026-04-27).

**Deadline:** 2026-04-30 (7 días desde 2026-04-23).

**Responsable:** Nico.

---

### DT-21 — Purga de credenciales en historia git (`filter-repo`)

**Depende de:** DT-20 completada.

**Origen:** Las credenciales expuestas en `05_multi_provider_buzones.sql` (rotadas en DT-20) siguen vivas en la historia git de los commits que introdujeron ese archivo. Aunque el repo sea privado, si alguna vez pasa a público o es forkeado, quedan indexables.

**Severidad:** Media una vez rotadas las credenciales (son válidas como trazabilidad de incidente, no como keys activas). Alta si DT-20 no se completa primero.

**Plan:**
1. Confirmar que DT-20 terminó (credenciales rotadas, sistema verificado).
2. Usar `git filter-repo --replace-text` para reemplazar los 4 secretos específicos por `REDACTED_2026_04_23`.
3. Force-push coordinado con Nico (único colaborador) sobre `main` y `develop`.
4. Todos los clones locales de Nico deben re-clonarse. Ningún tercero debe tener clones.
5. Rotar deploy keys de GitHub si existen.

**Deadline:** dentro de 14 días desde fin de DT-20.

**Responsable:** Nico.

---

### DT-25 — Backend no expone `/health` (ni staging ni posiblemente prod)

**Origen:** verificación de restart del backend_v2 en staging (2026-04-23). `GET /health` → 404. La ruta canónica actual es `GET /` → `{"status":"ok","message":"FlexPQR API está VIVO."}`.

**Severidad:** Baja. No bloqueante, pero afecta convenciones de monitoring externo (Cloudwatch, uptime probes, etc.).

**Plan:**
1. Verificar si el mismo 404 ocurre en prod (curl `http://18.228.54.9:8001/health` cuando se autorice).
2. Si ambos ambientes comparten el gap, agregar endpoint `/health` al backend FastAPI con response `{"status":"ok"}` + chequeo básico de DB (SELECT 1).
3. **Impacto inmediato en sprint:** los smoke tests del Agente 4 deben usar `GET /` (o endpoint conocido con DB-touch como `/api/v2/casos`), no `/health`.

**Responsable:** Agente 2 (backend) o Agente 6 (infra) en Sesión 3; queda como tarea paralela sin bloquear el sprint.

---

### DT-26 — Kafka no existe como container en staging

**Origen:** `docker compose ps` en staging no lista ningún container Kafka. Backend loggea "Kafka no disponible — API arranca sin producer" al boot.

**Severidad:** Media. No rompe runtime del backend (arranca en modo degradado). Rompe tests E2E que dependan del pipeline completo worker_ai_consumer → Kafka → consumer.

**Impacto en sprint Tutelas:**
- Agente 3 (AI/Worker) debe producir eventos al pipeline. Si esos eventos usan Kafka, no se puede probar E2E contra staging.
- Agente 4 (QA) debe mockear la capa Kafka o usar in-memory producer/consumer fixture.

**Plan:**
1. Decidir: ¿agregar Kafka como container al `docker-compose.yml` de staging o mockearlo con in-memory?
2. Si se mockea: documentar el fixture en tests del Agente 3 + Agente 4.
3. Si se agrega: ventana de infra + pruebas pre-sprint.

**Mitigación aplicada 2026-04-24:** `ai-worker` stopped en staging + servicio ausente del yml (bloque comentado en `docker-compose.yml` con la definición previa como docs). Previene auto-restart del consumer y futura acumulación de logs. Reactivar junto con despliegue de Kafka en staging. Causa raíz del incidente DT-28.

**Responsable:** Nico + Agente 3/4 al llegar a Sesión 2/3.

---

### DT-27 — SQLs legacy en raíz del repo subsumidas por el baseline

**Origen:** `01_schema_v2.sql ... 08_plantillas_schema.sql` siguen en la raíz del repo. Fueron las SQLs históricas antes de la 14. El baseline `migrations/00_baseline_schema.sql` (pg_dump schema-only de prod) las subsume completamente y además corrige gaps (agrega columnas productivas que las legacy no cubrían).

**Severidad:** Baja. No rompe nada — `migrate.sh` no las toca (lee solo `migrations/`). Pero confunden: un lector nuevo puede creer que son el pipeline activo.

**Plan (housekeeping, no bloqueante):**
1. `git mv` de las 6 SQLs a `migrations/legacy/`.
2. README corto en `migrations/legacy/README.md` explicando que son el historial antes del baseline y que no deben aplicarse.
3. Un commit `chore(migrations): archivar SQLs legacy bajo migrations/legacy/`.

**Responsable:** puede hacerse en cualquier sprint como tarea puntual. No bloquea tutelas.

---

### DT-28 — Staging al 100% de disco — RESUELTA 2026-04-24

**Origen:** `df -h /` en staging reportaba 19/19 GB (100%) bloqueando `docker exec` y `scp` nuevos. Detectado durante Agente 2 del sprint Tutelas al intentar correr tests en el container.

**Causa raíz identificada:** container `pqrs_v2-ai-worker-1` (consumer de Kafka) huérfano con `restart: unless-stopped` pero sin definición actual en ningún yml. Estaba en reconnect-loop contra `kafka_v2:29092` (DT-26: Kafka ausente) spameando `aiokafka ERROR Unable connect to node with id 1` a ~10 líneas/segundo. En 3-4 semanas acumuló **6.4 GB** en `/var/lib/docker/containers/<id>/*-json.log`.

**Secuencia de mitigación aplicada (2026-04-24):**

| # | Acción | Recuperado |
|---|---|---|
| 1 | `docker builder prune -af` | 0 B (cache vacío) |
| 2 | `docker container prune -f` (elimina 3 exited: kafka, zookeeper, kafka-init) | 118 KB |
| 3 | `docker image prune -af` (cascada post-prune libera imágenes kafka/zookeeper) | 535 MB |
| 4 | `truncate -s 0` del json.log del ai-worker | **6.4 GB** |
| 5 | `docker update --restart=no` + `docker rm` del container ai-worker | — |
| 6 | `journalctl --vacuum-size=100M` | 410 MB |

**Estado final:** 19 GB → **11 GB usados** (56%). **7.7 GB recuperados**.

**Volúmenes NO tocados:** los 12 volúmenes de Docker quedan intactos; los 7 huérfanos detectados sumaban <1 MB, no valía el riesgo.

**Imágenes activas NO tocadas:** 3.9 GB legítimos (backend, frontend, workers productivos, postgres, redis, minio, nginx).

**Prevención permanente:**
- Definición documental (bloque comentado) de `ai-worker` en `docker-compose.yml` explicando por qué está desactivado y cómo reactivarlo cuando Kafka exista. Ver sección "SERVICIO ai-worker DESACTIVADO EN STAGING HASTA DT-26 RESUELTA".
- `Brain/DEUDAS_PENDIENTES.md#DT-26` actualizada con nota de mitigación cruzada.

**Deuda residual futura:**
- Definir `logging.options.max-size` + `max-file` por default en todos los servicios de `docker-compose.yml` para que ningún container pueda pasar de, p.ej., 500 MB de logs acumulados. Evita recurrencia de este tipo de incidente. No bloqueante del sprint; sugerido como housekeeping del Agente 6 (Infra) en Sesión 3.

---

### DT-29 — `storage_engine` import eager bloquea pytest con conftest global

**Origen:** `backend/tests/conftest.py` importa `app.main`, que importa todas las rutas, que importan `app.services.storage_engine`. Ese módulo intenta conectar MinIO **al importarse** (module-level `client`) con 3 reintentos de 30s cada uno. En env local sin MinIO, esto causa que `pytest` se cuelgue ~90s durante `collect`, volviendo impráctico correr la suite rápida.

**Detectado:** 2026-04-24 durante Agente 3 del sprint Tutelas, al correr tests nuevos.

**Severidad:** Baja en prod/staging (MinIO responde). Molesta en dev/CI local donde no hay MinIO.

**Workaround aplicado:** tests del sprint se ejecutan con `pytest --noconftest`. Los 42 tests del Agente 2 + 16 del Agente 3 = 58 tests verdes corren en <2s con esta flag. Los fixtures del conftest global (`test_client`, `mock_db_connection`, etc.) no son necesarios para tests unitarios de servicios.

**Plan:**
1. Refactorizar `storage_engine.py` para hacer el `client` lazy: conectar al primer uso, no al import.
2. O, alternativamente, añadir un `conftest.py` local en `tests/services/` que mockee `storage_engine.client` antes de cualquier import de `app.main`.
3. Opción de mínimo esfuerzo: documentar en `pytest.ini` un marker `no_storage` y un filtro por default que skipee tests que requieren storage.

**Responsable:** Agente 6 (Infra) en Sesión 3, o housekeeping posterior al sprint.

---

### DT-30 — Reconciliación ORM `models.py` ↔ DB completa pendiente

**Origen:** auditoría sistemática del 2026-04-27 durante el smoke E2E del sprint Tutelas. Comparó las 37 columnas reales de `pqrs_casos` en staging contra `backend/app/core/models.py:PqrsCaso` y contra el INSERT de `backend/app/services/db_inserter.py`. Detalle completo en `Brain/sprints/SPRINT_TUTELAS_S123_SMOKE_E2E.md` sección "Auditoría sistemática drift".

**Severidad:** Media. No bloquea runtime hoy (todo el código usa `asyncpg` directo, no SQLAlchemy ORM). Bloquea cualquier código futuro que decida usar ORM para queries — bugs latentes silenciosos.

**Hallazgos concretos:**

1. **9 columnas en DB no declaradas en ORM** (post mig 14, 18, 19, 22):
   `external_msg_id`, `fecha_asignacion`, `updated_at`, `es_pqrs`, `reply_adjunto_ids`, `texto_respuesta_final`, `borrador_ia_original`, `edit_ratio`, `metadata_especifica`, `tutela_informe_rendido_at`, `tutela_fallo_sentido`, `tutela_riesgo_desacato`, `documento_peticionante_hash` (en realidad son 13).

2. **`semaforo_sla` ORM CHECK desactualizado**: declara `IN ('VERDE','AMARILLO','ROJO')`, DB tiene 5 valores tras mig 18 (`+ NARANJA, NEGRO`).

3. **6 columnas declaradas en ORM se llenan post-INSERT** por workflows específicos (`problematica_detectada`, `plantilla_id`, `aprobado_por`, `aprobado_at`, `enviado_at`, `acuse_enviado`, `numero_radicado`). No es bug, es diseño — pero el patrón merece documentación para que un dev nuevo no asuma que el INSERT inicial los popula.

**Mitigación parcial aplicada en sprint Tutelas (2026-04-27):**

- Migración 22: agrega columna `correlation_id` (estaba en ORM e INSERT pero no en DB → DRIFT-B con bug bloqueante).
- Fix `db_inserter`: propaga `external_msg_id` y `documento_peticionante_hash` al INSERT (DRIFT-D con bugs bloqueantes para dedup y vinculación).

**Pendiente para sprint dedicado post-tutelas:**

1. Actualizar `models.py:PqrsCaso` para reflejar las 13 columnas ausentes.
2. Actualizar `semaforo_sla` CHECK del ORM a 5 valores.
3. Documentar en docstring de `PqrsCaso` qué columnas son "INSERT-time" (las populadas por `db_inserter`) vs "post-INSERT" (workflows específicos).
4. Considerar generar `models.py` automáticamente desde `pg_dump --schema-only` para evitar que vuelva a desincronizarse.

**Riesgo si se ignora:** cualquier feature futura que use SQLAlchemy ORM (queries declarativas, alembic migrations, admin UI) verá una vista parcial del schema → bugs latentes.

**Responsable:** sprint dedicado de housekeeping o Agente 5 (Docs) si lo prioriza Nico antes de cerrar Sesión 3.

---

## Deudas pre-sprint Tutelas referenciadas (consolidadas durante Agente 5)

Estas DTs venían de antes del sprint y fueron mencionadas por Nico al cerrar Sesión 3. Se consolidan acá para tener un único índice. Estado verificado al 2026-04-27.

### DT-15 — Bind mounts workers staging :ro

**Estado:** **PENDIENTE**, asignada al Agente 6 de la Sesión 3 actual.

**Descripción:** los workers en staging deben tener `volumes: ./backend:/app:ro` (read-only) en `docker-compose.staging.yml` para que cambios en `.py` se reflejen sin rebuild de imagen, acelerando ciclos de iteración. Modo `:ro` previene escritura accidental desde el container.

**Plan:** Agente 6 ajusta los servicios `master_worker_v2`, `demo_worker_v2`, `backend_v2` en el yml de staging activo. Validar con `touch backend/app/services/sla_engine.py` y verificar que el container ve la nueva mtime.

---

### DT-17 — CHECK semáforo extendido (NARANJA, NEGRO)

**Estado:** **RESUELTA 2026-04-23** — Migración 18 del sprint Tutelas.

`pqrs_casos_semaforo_sla_check` actualizado a 5 valores: `VERDE, AMARILLO, NARANJA, ROJO, NEGRO`. Ver [[SPRINT_TUTELAS_S123_AG1_APLICACION]].

⚠️ **ORM stale:** `models.py:PqrsCaso.__table_args__` aún declara CHECK con 3 valores. No bloqueante (asyncpg directo no usa ORM). Se aborda en DT-30.

---

### DT-18 — Fixtures sintéticos pendientes / oficios reales de Paola

**Estado:** **ACTIVA**.

3 fixtures sintéticos creados en sprint Tutelas (`backend/tests/fixtures/tutelas/01_*.txt`, `02_*.txt`, `03_*.txt`) con marker `SYNTHETIC_FIXTURE_V1` para validar el extractor con confidence alto/bajo/sin-plazo.

**Lo pendiente:** Paola Lombana (ARC) debe compartir 5-10 oficios judiciales reales (PDF) para validar precisión de Claude Sonnet en producción. Plantilla del mensaje en [[SPRINT_TUTELAS_S123]] sección "3 fixtures sintéticos".

**Sin esto:** las métricas de `_confidence` que vemos hoy son contra texto sintético; Claude está legítimamente menos seguro con fixtures que con oficios reales. No es bug del extractor.

**Responsable:** Nico solicita; Paola entrega; agente futuro corre extractor real y reporta precisión.

---

### DT-22 — Backup cifrado de SSH keys + Brain

**Estado:** **ACTIVA**.

**Descripción:** las SSH keys (`~/.ssh/flexpqr-prod`, `~/.ssh/flexpqr-staging`) y el directorio `Brain/` viven solo en la máquina de Nico. Bus-factor de 1.

**Plan:**
1. Backup cifrado con `age` o `gpg` de los archivos sensibles.
2. Copia en al menos 2 ubicaciones (USB físico + cloud encrypted).
3. Documentar el procedimiento de recovery.

**Responsable:** Nico. No bloqueante de runtime.

---

### DT-23 — Claude Code Pro training opt-out

**Estado:** **MITIGADA con toggle off** (2026-04-XX).

**Descripción:** Anthropic puede usar conversaciones de Claude Code Pro para training. Flag de privacidad togglead-able en la consola.

**Mitigación aplicada:** opt-out activado en cuenta de Nico. Las conversaciones del proyecto no entran al pool de training.

**Pendiente:** revalidar el setting cada 6 meses; Anthropic puede cambiar defaults.

---

### DT-24 — Migrar a API key comercial (vs Pro tier)

**Estado:** **ACTIVA**.

**Descripción:** Claude Code Pro tier tiene rate limits y caps de tokens distintos al API comercial. Para escala productiva con FlexPQR (cuando ARC + FlexFintech + nuevos clientes corran tutelas en simultáneo), conviene migrar a billing API directo.

**Plan:**
1. Crear cuenta de billing API.
2. Migrar `ANTHROPIC_API_KEY` en prod (tras DT-20 rotación).
3. Setear caps de spend en consola.
4. Revisar latencia + rate limit del tier.

**Responsable:** Nico cuando el volumen lo justifique.

---

## DT-31 — Deudas frontend tutelas (descubiertas durante sprint)

**Origen:** el sprint Tutelas habilitó backend + DB completo, pero la UI no se tocó. Las siguientes son features pendientes para que el frontend aproveche el pipeline:

### DT-31.a — UI polimórfica para tutelas

Vista dedicada que consume `tutelas_view` (con filtro `cliente_id` explícito por **DT-30 / RLS no hereda**). Campos a mostrar: expediente, juzgado, accionante (anonimizado, solo hash), plazo restante, semáforo, riesgo de desacato.

### DT-31.b — UI para gestión de capabilities

Tabla `user_capabilities` necesita admin UI para que un super_admin del tenant otorgue/revoque `CAN_SIGN_DOCUMENT` y `CAN_APPROVE_RESPONSE` a abogados/analistas. Hoy se hace SQL directo.

### DT-31.c — Firma digital de informes

Una vez el abogado redacta el informe de respuesta a la tutela, debe firmarse digitalmente antes de enviar al juzgado. Requiere integración con Docusign/equivalente + actualización de `tutela_informe_rendido_at` post-firma.

### DT-31.d — Tracking post-informe

Una tutela cuyo informe ya se rindió pasa a estado de "espera de fallo". UI debe mostrar tutelas en ese estado con `tutela_fallo_sentido = NULL` y permitir registrar fallo cuando llega.

### DT-31.e — Visualización de semáforo NARANJA y NEGRO

El frontend actual asume 3 colores (VERDE/AMARILLO/ROJO). Tras migración 18, el backend reporta NARANJA y NEGRO. La UI debe agregarlos en la leyenda + filtros + ordenamientos.

**Severidad:** todas medias. No bloquean operación (el SQL/API responde correctamente). Bloquean UX.

**Responsable:** sprint frontend dedicado, post-deploy a prod del sprint Tutelas backend.

---

## Estado consolidado post sprint Tutelas (2026-04-27)

| DT | Título | Estado | Deadline / Trigger |
|---|---|---|---|
| DT-1 a DT-7 | Hardening AWS pre-sprint | (ver historial Brain) | varía |
| DT-8 | Guardrail compose | Activa | próximo deploy |
| DT-15 | Bind mounts workers staging | Pendiente | Agente 6 Sesión 3 |
| DT-17 | CHECK semáforo extendido | **RESUELTA** 2026-04-23 | mig 18 |
| DT-18 | Fixtures reales Paola | **ACTIVA** | sin deadline |
| DT-19 | Drift detection semestral | Activa | semestral |
| DT-20 | Rotación creds ARC + Anthropic key | **ACTIVA** | **2026-04-30** |
| DT-21 | Purga git history | Activa | post-DT-20 |
| DT-22 | Backup SSH/Brain cifrado | Activa | sin deadline |
| DT-23 | Claude Code Pro training opt-out | **Mitigada** | revalidar 6m |
| DT-24 | Migrar a API key comercial | Activa | cuando volumen lo amerite |
| DT-25 | Backend `/health` ausente | Activa | Agente 6 Sesión 3 |
| DT-26 | Kafka ausente staging | **Mitigada** (ai-worker stop) | sprint dedicado |
| DT-27 | SQLs legacy en raíz | Activa | housekeeping post-tutelas |
| DT-28 | Disco staging 100% | **RESUELTA** 2026-04-24 | -7.7 GB |
| DT-29 | `storage_engine` import eager | Activa | Agente 6 Sesión 3 |
| DT-30 | Reconciliación ORM↔DB completa | Activa | sprint dedicado |
| DT-31.a-e | Frontend tutelas (UI, capabilities, firma, tracking, semáforo) | Activas | sprint frontend post-deploy |
