# 📋 TABLERO ACTUAL — FlexPQR

**Última actualización**: 2026-04-14 (post-fix FirmaModal demo tenant)

## Contexto

- Demo Banco Popular del 14-abril: **aplazada**
- Reunión emergente con Banco W: **en curso, Nico en standby técnico**
- Próxima demo confirmada: esta semana, sin fecha cerrada

## Fix aplicado hoy ✅

- **A2**: env vars `DEMO_GMAIL_USER`/`DEMO_GMAIL_PASSWORD` en `backend_v2` (arregla bug del FirmaModal en demo tenant)
- **A4**: `DEMO_RESET_MINUTES` de 30 a 1440 (evita borrado de casos durante demos)
- **A3**: Validación funcional exitosa con caso `1445ae6e` (Tutela Mario Hernández)

## Tareas abiertas

### 🟡 Importantes (próxima sesión)

| ID | Tarea | Estado |
|----|-------|--------|
| B1 | Investigar trabajo pendiente en staging para Bancolombia | Pendiente de investigación |
| C1 | Cross-tenant leak en `/casos/borrador/pendientes` | Hotfix aislado pendiente |
| C2 | SSE canal equivocado en demo_worker (`pqrs_stream_v2` vs `pqrs.events.*`) | Fix de 6 líneas pendiente |

### 🟢 Deudas técnicas (sprint aparte)

| ID | Tarea | Notas |
|----|-------|-------|
| D1 | Motor SLA sectorial dormido en main | Requiere migración 14 + deploy coordinado |
| D2 | Drift staging vs main (5+ días) | Fast-forward cuando haya ventana |
| D3 | Clase ORM `FestivosColombia` huérfana | Eliminar o aplicar migración |
| D4 | `ORDER BY ASC` estanca borradores nuevos en `/casos/borrador/pendientes` | 1 línea de fix |
| D5 | Seed del demo tenant con casos viejos (27/3) | Diseñar refresh periódico |
| D6 | Bug UX FirmaModal (notificación verde engañosa) | Fix en 5 líneas |
| D7 | Kafka containers `Exited` hace 5+ días | Investigar impacto y decidir |

### ⚪ Procesos

| ID | Tarea | Estado |
|----|-------|--------|
| P1 | Guión de demo estándar para Martín | Pendiente de documentar |
| P2 | Regla anti-drift de branches | ✅ Aplicada ayer (ver `00_DIRECTIVAS_CLAUDE_CODE.md` §3.5) |

## Convenciones de deploy aprendidas

1. **Patrón de fix aislado sin rebuild**: edit compose + `docker compose up -d --no-deps <servicio>`
2. **Siempre backup** del compose antes de editar (`cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M)`)
3. **Verificación YAML** con `docker compose config --quiet` antes de recreate
4. **Checkpoints de pausa** entre paso y paso en deploys a prod
5. **Monitores background** con `nohup + disown` + launcher en archivo para debug en vivo sin infierno de escaping SSH→bash→bash
