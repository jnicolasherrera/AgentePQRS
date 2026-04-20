# 📋 TABLERO ACTUAL — FlexPQR

**Última actualización**: 2026-04-16 (cierre sprint hardening AWS QW3 + QW4)

## Contexto

- **Sprint activo**: Hardening AWS (14-16 abril). QW1-QW4 completados. Ver `fixes/HARDENING_AWS_ABRIL_2026.md`.
- **Objetivo estratégico vigente**: cerrar blockers críticos del análisis Bancolombia (`BANCO_POPULAR_ANALISIS_SEGURIDAD.md`) para sostener conversación técnica enterprise sin bochornos.
- **Demo Banco Popular del 14-abril**: aplazada.
- **Reunión emergente con Banco W**: en curso, Nico en standby técnico.
- **Próxima demo comercial**: sin fecha cerrada.
- **Cliente pilot productivo**: Abogados Recovery S.A.S. (`arcsas.com.co`) — estable.

## ✅ Cerrado recientemente

### Sprint hardening AWS (15-16 abril)

- **QW1**: MFA root AWS confirmado (Authapp, marzo 2026). Cero access keys en root.
- **QW2**: IAM user `flexpqr-deploy` creado con least privilege (sin IAM write, sin CloudTrail write). Access Key configurada en WSL con profile dedicado.
- **QW3**: CloudTrail `flexpqr-trail` multi-región → bucket `flexpqr-cloudtrail-logs` con SHA-256 validation, 7 años retención, bucket policy con condición `AWS:SourceArn`.
- **QW4**: GuardDuty activo en `sa-east-1` (trial 30 días).

### Fix FirmaModal demo tenant (14 abril)

- **A2**: env vars `DEMO_GMAIL_USER`/`DEMO_GMAIL_PASSWORD` en `backend_v2` (arregla bug del FirmaModal en demo tenant).
- **A4**: `DEMO_RESET_MINUTES` de 30 a 1440 (evita borrado de casos durante demos).
- **A3**: Validación funcional exitosa con caso `1445ae6e` (Tutela Mario Hernández).

## 🎯 Tareas abiertas

### 🔴 Alta prioridad (próxima sesión)

| ID | Tarea | Contexto |
|----|-------|----------|
| **H1** | Rotar credenciales expuestas en sesión de hardening | Gmail app password, Redis password, MinIO. Ver `fixes/HARDENING_AWS_ABRIL_2026.md` sección "Credenciales expuestas". |
| **H2** | Push commit Brain `0307fa1` a remoto | Deuda DT-7. Pendiente desde 14-abril. Riesgo bus-factor sobre documentación. |
| **H3** | `README.DEPLOY.md` con regla anti-sync compose prod↔local | Corto plazo de deuda DT-8. Prevenir reapertura accidental de los 9 puertos cerrados. |

### 🟡 Importantes (sesiones futuras)

| ID | Tarea | Contexto |
|----|-------|----------|
| B1 | Investigar trabajo pendiente en staging para Bancolombia | Backlog enterprise: 8 blockers críticos. |
| C1 | Cross-tenant leak en `/casos/borrador/pendientes` | Hotfix aislado pendiente (descubierto en sesión 14-abril). |
| C2 | SSE canal equivocado en demo_worker | Fix de 6 líneas (`pqrs_stream_v2` vs `pqrs.events.*`). |
| DT-3 | Migrar `*FullAccess` a policies custom mínimas | Bancolombia mira esto. ~1 hora. |
| DT-1 | SSE-KMS en CloudTrail (CMK dedicada) | Bancolombia mira esto. ~30 min. |
| DT-2 | GuardDuty multi-región | Antes de fin del trial 30 días. |
| DT-8 (largo) | Script `deploy/verify_compose_diff.sh` | ~2 horas. |

### 🟢 Deudas técnicas de producto (sprint aparte)

| ID | Tarea | Notas |
|----|-------|-------|
| D1 | Motor SLA sectorial dormido en main | Requiere migración 14 + deploy coordinado. Ver `DEUDAS_PENDIENTES.md` primer bloque. ⚠️ **Inconsistencia documental detectada** con `sprints/SPRINT_SLA_SECTORIAL.md` — resolver antes de deploy. |
| D2 | Drift staging vs main (5+ días) | Fast-forward cuando haya ventana. |
| D3 | Clase ORM `FestivosColombia` huérfana | Eliminar o aplicar migración. |
| D4 | `ORDER BY ASC` estanca borradores nuevos en `/casos/borrador/pendientes` | 1 línea de fix. |
| D5 | Seed del demo tenant con casos viejos (27/3) | Diseñar refresh periódico. |
| D6 | Bug UX FirmaModal (notificación verde engañosa) | Fix en 5 líneas (`frontend/src/components/ui/firma-modal.tsx` líneas 33-40). |
| D7 | Kafka containers `Exited` hace 5+ días | Investigar impacto y decidir si reactivar o deprecar. |

### ⚪ Procesos

| ID | Tarea | Estado |
|----|-------|--------|
| P1 | Guión de demo estándar para Martín | Pendiente de documentar. |
| P2 | Regla anti-drift de branches | ✅ Aplicada (ver `00_DIRECTIVAS_CLAUDE_CODE.md` §3.5) |
| P3 | Rotación automática trimestral de access keys | Deuda DT-5. ~2 horas implementación. |
| P4 | AWS IAM Identity Center cuando sumen Dante/Martín | Deuda DT-4. ~45 min cuando se necesite. |

## 🔗 Referencias estratégicas vigentes

- **Roadmap enterprise**: `BANCO_POPULAR_ANALISIS_SEGURIDAD.md` — 13 puntos, 3 caminos (A: SaaS certificado, B: on-prem banco, C: híbrido). El sprint AWS atacó mayoritariamente los Puntos 4 (IAM), 7 (conectividad), 8 (logs).
- **Decisión orquestador**: `DECISION_COMPOSE_VS_K8S.md` — Compose hoy, K8s managed cuando se active Camino A.
- **Manual producto para IT bancario**: `MANUAL_FLEXPQR_INDICE.md` + `CHEAT_SHEET_FLEXPQR_IT_BANCARIO.md` (esqueletos, pendiente de llenar secciones P5/P8 que ahora sí tienen respuesta concreta post-sprint).

## 🛠️ Convenciones de deploy aprendidas

1. **Patrón de fix aislado sin rebuild**: edit compose + `docker compose up -d --no-deps <servicio>`.
2. **Siempre backup** del compose antes de editar (`cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M)`).
3. **Verificación YAML** con `docker compose config --quiet` antes de recreate.
4. **Checkpoints de pausa** entre paso y paso en deploys a prod.
5. **Monitores background** con `nohup + disown` + launcher en archivo para debug en vivo sin infierno de escaping SSH→bash→bash.
6. **Nunca sincronizar compose local → prod sin diff previo aprobado** (regla nueva post-sprint AWS — los puertos críticos en prod están bindeados a `127.0.0.1`).
7. **Antes de debuggear credenciales AWS CLI**: `env | grep AWS_` y `unset` lo que sobre (las env vars ganan al `--profile`).
