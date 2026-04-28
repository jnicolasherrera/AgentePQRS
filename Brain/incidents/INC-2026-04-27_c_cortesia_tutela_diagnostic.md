# Diagnóstico INC-2026-04-27_c — "Cortesía a tutelas" (DT-40)

## Contexto

Reporte de Paola Lombana (ARC) durante validación post-deploy del sprint Paola: **"se está enviando correo de cortesía al peticionante de tutelas, no debería"**.

Hipótesis inicial: regresión post incidente master_worker (DT-32). El filtro `!= "TUTELA"` en `master_worker_outlook.py:258` puede haber sido removido por un commit reciente, o el comportamiento cambió tras el restart del worker.

## Verificación V1-V5 (read-only, 2026-04-28 madrugada UTC)

### V1 — `ai_engine.py` main vs develop
**Sin cambios.** El clasificador `clasificar_hibrido` con su flujo Claude Haiku → `_merge_confidence` es idéntico en ambas branches. `git log main..origin/develop -- backend/app/services/ai_engine.py` retorna **vacío**.

### V2 — Commits del sprint Tutelas tocando `master_worker_outlook.py`
Solo 1 commit: `bba7f67 refactor(workers): 3 workers invocan pipeline unificado`. Preserva el filtro intacto:
```python
if str(c_id) == TENANT_ABOGADOS_RECOVERY and resultado.tipo.value != "TUTELA":
    enviado = zoho_prov.send_acuse_recibo(...)
```

### V3 — Pipeline + tutela_extractor desde develop
```python
# pipeline.py
async def process_classified_event(clasificacion: ClassificationResult, ...):
    tipo_caso = clasificacion.tipo_caso  # ← asume clasificación correcta
    if tipo_caso == "TUTELA":
        metadata = enrich_by_tipo(...)  # extractor solo para TUTELA
```

`tutela_extractor.py` (343 líneas) extrae metadata estructurada de oficios judiciales **solo si caso ya viene como TUTELA**. NO hay re-clasificación ni override. `scoring_engine.py` solo agrega `SEMAFORO_CONFIG` (semáforo polimórfico VERDE/AMARILLO/NARANJA/ROJO/NEGRO), sin tocar keywords ni reglas de scoring de tipo.

### V4 — Histórico del filtro `!= TUTELA`
Commit `a5ae728 feat(bandeja): eliminar correos desde bandeja + no acuse en tutelas` — **2026-04-08 15:13 UTC**. Filtro vivo desde hace casi 3 semanas, nunca removido.

### V5 — Datos prod ARC

**Acuse vs tipo_caso (histórico completo):**

| tipo_caso | acuse_enviado | count |
|---|---|---|
| TUTELA | FALSE | 28 |
| TUTELA | TRUE | **4** (todas pre-`a5ae728`) |
| PETICION | TRUE | 55 |
| PETICION | FALSE | 24 |
| QUEJA | TRUE | 1 |
| RECLAMO | TRUE | 11 |
| SOLICITUD | TRUE | 26 |
| SOLICITUD | FALSE | 17 |

Las 4 tutelas con `acuse_enviado=TRUE`:
- 2026-03-27 20:31 — `Notificación Auto Apertura - Tutela 2026-00375`
- 2026-04-06 17:53 — `TUTELA I INSTANCIA 2026-00118 -AVOCAMIENTO-`
- 2026-04-06 19:57 — `Reenviar: NOTIFICACION AUTO REQUIERE - INCIDENTE DESACATO`
- 2026-04-07 03:07 — `Fwd: Reenviar: TUTELA I INSTANCIA 2026-00118 -AVOCAMIENTO-`

**Todas anteriores al filtro `a5ae728` del 8-abril 15:13 UTC.** Desde entonces, **0 tutelas con acuse**.

**Búsqueda de tutelas mal-clasificadas como otro tipo recibiendo acuse:**

Query: `tipo_caso != 'TUTELA' AND acuse_enviado = TRUE AND asunto matchea ['TUTELA I INSTANCIA','accion de tutela','avocamiento','notificación auto','admisión tutela','admision tutela']`

→ **0 resultados.**

Búsqueda más laxa (asunto menciona "fallo de tutela"): 3 resultados, pero todos son **peticiones legítimas post-fallo** (solicitud supresión datos a Superindustria que mencionan el fallo previo en el asunto). No son falsos negativos del clasificador.

## Conclusión empírica

**Hipótesis "Claude Haiku reclasifica TUTELA→PETICION causando cortesía" → SIN evidencia.**

- Filtro `!= TUTELA` activo y funcional desde 2026-04-08.
- 0 tutelas reciben acuse desde esa fecha.
- 0 casos con asunto fuerte de tutela clasificados como otro tipo recibiendo acuse.
- El sprint Tutelas no toca clasificación, solo enriquece post-clasificación.

## Hipótesis alternativas (pendientes confirmación con Paola)

A. **Memoria desactualizada**: Paola recuerda comportamiento pre-`a5ae728` (antes de 8-abril) y reportó la regresión hoy basándose en memoria, no en evidencia reciente.

B. **Confusión con otro flujo**: el correo "cortesía" que vio Paola NO es `send_acuse_recibo` sino el correo de **respuesta del abogado** vía `aprobar-lote`. Ese SÍ debe llegar al peticionante de tutela porque es la respuesta legal al juzgado. Pero ese no es "cortesía", es la respuesta firme.

C. **Flujo no detectado**: existe algún path desconocido (otro worker, manual via UI, integración externa) que no estamos viendo.

## DT-40 reclasificada

**Estado**: pendiente confirmación con caso real de Paola.

**Bloqueante para fix**: necesitamos message-id, asunto exacto, fecha del envío, caso_id si lo tiene. Sin esa info, fixear sería especular sobre datos que no existen.

**Plan al recibir info**:
1. Buscar el caso en DB: `SELECT id, tipo_caso, acuse_enviado, asunto, fecha_recibido, created_at FROM pqrs_casos WHERE id='...' OR asunto='...'`.
2. Validar cuál de hipótesis A/B/C aplica.
3. Decidir fix basado en evidencia.

**NO se aplicó fix técnico hoy** (28-abril). Sprint dedicado cuando llegue caso específico de Paola.

## Riesgo residual hasta confirmación

Si la hipótesis alternativa C es real y existe un path que envía cortesía a peticionantes de tutela, el caso seguiría ocurriendo. Mitigación operativa: Paola pausando aprobaciones de tutelas como workaround temporal hasta confirmación.

## Lecciones del diagnóstico

1. **Validar hipótesis con datos antes de fixear**. La hipótesis "Claude reclasifica" parecía elegante por los logs visibles (`Claude corrigió: TUTELA→PETICION` ~30 veces/24h), pero los datos en DB no respaldaban el patrón.
2. **Sprint Tutelas y este bug son ortogonales**. Sprint Tutelas mejora post-clasificación; el bug presunto es de clasificación. Deployar sprint Tutelas no habría resuelto nada.
3. **Diagnóstico read-only ahorra deploys innecesarios**. 1 hora de queries valió por evitar deploy especulativo a prod.

## Referencia cruzada

- DT-40 (este doc) — pendiente caso Paola.
- DT-32 (incidente master_worker) — bridge cron mitigando hasta sprint dedicado.
- DT-39 (próximo) — bridge cron false-positives en madrugada CO. Ver `Brain/DEUDAS_PENDIENTES.md`.
- Sprint Paola: `Brain/sprints/SPRINT_BUGS_PAOLA_2026-04-27.md`.
- Sprint Tutelas (no deployado prod): `Brain/sprints/SPRINT_TUTELAS_S123_*` (en develop).
