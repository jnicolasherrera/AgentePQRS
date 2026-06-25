# A3/A4 — Filtro de cartera (`asignado_a`) en detalle y edición de caso

**Fecha:** 2026-06-25
**Hallazgos auditoría:** 3.B2 (ALTO, `get_caso_detalle`) + 3.B3 (ALTO, `update_caso`)
**Tipo:** Fuga intra-tenant entre carteras + escalada de privilegios (NO cross-tenant)

## Problema (verificado en código de PROD)

El modelo de negocio es "cada abogado ve lo suyo": un `abogado`/`analista` solo debe
ver/operar los casos de **su** cartera (`pqrs_casos.asignado_a = su user_id`). Ese filtro
se aplica correctamente en Bandeja (`admin.py`), Enviados (`casos.py` historial) y Dashboard
(`stats.py`), pero **falta** en dos endpoints:

- **A3 — `get_caso_detalle` (`casos.py` ~L323-339):** el WHERE es `c.id=$1 AND ($2 OR c.cliente_id=$3)`
  → filtra solo por tenant, NO por `asignado_a`. Un abogado puede leer el detalle completo
  (cuerpo, cédula/`documento_peticionante`, borrador, comentarios, adjuntos-metadata) de
  **cualquier** caso de su tenant, incluida la cartera de otros abogados.

- **A4 — `update_caso` (PATCH, `casos.py` ~L491-518):** **no valida rol al inicio** y el UPDATE
  scoping es `($idx OR cliente_id=$idx)` (solo tenant). Cualquier rol autenticado —incluido
  `abogado`— puede cambiar `estado`/`prioridad` y **reasignar `asignado_a`** de cualquier caso
  del tenant → un abogado puede robarse/soltar casos de otras carteras.

### Por qué RLS NO lo cubre (re-chequeo solicitado, jun 2026)
RLS aísla por `cliente_id` (tenant). Los 7 abogados de Abogados Recovery comparten el mismo
`cliente_id` → para RLS son el MISMO inquilino. La fuga A3/A4 es **entre carteras del mismo
tenant** (eje `asignado_a`), que RLS no toca. Confirmado empíricamente: Recovery tiene 7 abogados
activos con carteras de ~260-378 casos c/u; hoy cada uno puede ver/editar los ~1.770 casos de
los otros. **No se ahorra trabajo vía RLS: hay que filtrar en la query.**

## Decisión de política (confirmada con el usuario)

| Acción | abogado / analista | admin / coordinador / super_admin / auditor |
|---|---|---|
| Ver detalle de caso (A3) | solo su cartera (`asignado_a = self`) | todo el tenant |
| Cambiar estado / prioridad (A4) | solo en SUS casos | cualquier caso del tenant |
| Reasignar `asignado_a` (A4) | **PROHIBIDO (403)** | permitido |

`super_admin` bypassa el scope de tenant (opera cualquier tenant), como ya hace el resto del código.

## Roles que "ven todo" (patrón canónico ya en el repo)
`ROLES_VEN_TODO = {"admin", "coordinador", "super_admin", "auditor"}` (idéntico a `casos.py` historial L227).
`abogado`/`analista` quedan fuera → se les aplica el filtro de cartera.

## Cambios por capa

### Backend — `backend/app/api/routes/casos.py` (ÚNICO archivo)

**A3 `get_caso_detalle`:** agregar al WHERE el filtro de cartera con bypass por rol:
```
WHERE c.id = $1 AND ($2 OR c.cliente_id = $3) AND ($4 OR c.asignado_a = $5)
```
- `$4 = current_user.role in ROLES_VEN_TODO` (bypass de cartera)
- `$5 = uuid.UUID(current_user.usuario_id)`
Resultado: abogado pide caso ajeno → 0 filas → 404 (no filtra existencia/contenido).

**A4 `update_caso`:**
1. **Guard de reasignación:** si `"asignado_a" in payload` y `current_user.role not in ROLES_VEN_TODO`
   → `403 "No autorizado para reasignar casos"`. (Solo admin/coordinador reasignan.)
2. **Scope de cartera en el UPDATE:** agregar `AND ($N OR asignado_a = $M)` al WHERE, con
   `$N = role in ROLES_VEN_TODO`, `$M = usuario_id`. Así un abogado solo puede modificar SUS casos;
   intentar editar uno ajeno → 0 filas → 404.

### DB / Frontend
Sin cambios. (El frontend ya oculta controles admin para abogado; esto es defensa de backend.)

## Riesgos y mitigaciones
- **Riesgo:** romper el acceso legítimo de admin/coordinador → mitigado: `ROLES_VEN_TODO` bypassa.
- **Riesgo:** un abogado deja de ver SUS propios casos (regresión) → cubierto por test de cartera propia.
- **Riesgo:** `usuario_id` del token no castea a UUID → ya se usa así en historial (L248), patrón probado.
- **Rollback:** revertir `casos.py` al `.bak` (deploy quirúrgico de 1 archivo).

## Estrategia de validación
1. **Staging** (alineado con prod, 2 abogados + 1 admin sembrados, casos en 2 carteras):
   - Abogado A pide detalle de caso de abogado B → 404 ✅ (antes: 200 con datos).
   - Abogado A pide SU caso → 200 ✅ (no regresión).
   - Admin pide cualquier caso → 200 ✅.
   - Abogado A intenta PATCH estado de caso de B → 404; de SU caso → 200.
   - Abogado A intenta reasignar (cualquier caso) → 403.
   - Admin reasigna → 200.
2. **Prod:** mismas pruebas con datos reales (Recovery: 2 abogados reales), luego HTTP 200 backend.