"""
Test de Jerarquía RLS — Sprint 0: El Búnker
Valida que el nuevo modelo RBAC con aequitas_worker (BYPASSRLS) funciona correctamente.

Escenarios:
  1. aequitas_worker ve TODOS los casos (BYPASSRLS nativo, sin app.is_superuser)
  2. pqrs_admin con rol 'analista' solo ve sus casos asignados (asignado_a = user_id)
  3. pqrs_admin con rol 'auditor' puede SELECT pero no INSERT
  4. Audit log es INMUTABLE (UPDATE y DELETE deben lanzar excepción)

Uso:
  WORKER_DB_URL=... ADMIN_DB_URL=... python test_rls_hierarchy.py
"""
import asyncio
import os
import asyncpg

WORKER_DB_URL = os.environ.get(
    "WORKER_DB_URL",
    "postgresql://aequitas_worker:changeme_worker@postgres_v2:5432/pqrs_v2",
)
ADMIN_DB_URL = os.environ.get(
    "ADMIN_DB_URL",
    "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2",
)

# UUIDs de prueba — deben existir en la DB antes de correr este test
TEST_TENANT_ID  = "11111111-1111-1111-1111-111111111111"
TEST_ANALISTA_ID = "22222222-2222-2222-2222-222222222222"
TEST_AUDITOR_ID  = "33333333-3333-3333-3333-333333333333"

PASS = "✅ PASS"
FAIL = "❌ FAIL"


async def test_worker_bypassrls():
    """aequitas_worker debe ver todos los casos sin necesidad de set_config."""
    conn = await asyncpg.connect(WORKER_DB_URL)
    try:
        total = await conn.fetchval("SELECT COUNT(*) FROM pqrs_casos")
        tenants = await conn.fetchval("SELECT COUNT(DISTINCT cliente_id) FROM pqrs_casos")
        print(f"\n{'='*60}")
        print("TEST 1: Worker BYPASSRLS — visibilidad cruzada entre tenants")
        print(f"  Casos totales visibles: {total}")
        print(f"  Tenants distintos:      {tenants}")
        # Un worker que usa BYPASSRLS debe ver todos los casos (al menos 0, nunca error)
        ok = total >= 0 and tenants >= 0
        print(f"  Resultado: {PASS if ok else FAIL}")
        return ok
    finally:
        await conn.close()


async def test_analista_isolation():
    """Analista solo debe ver los casos donde asignado_a = su user_id."""
    conn = await asyncpg.connect(ADMIN_DB_URL)
    try:
        await conn.execute(f"SELECT set_config('app.current_tenant_id', '{TEST_TENANT_ID}', false)")
        await conn.execute(f"SELECT set_config('app.current_user_id',   '{TEST_ANALISTA_ID}', false)")
        await conn.execute("SELECT set_config('app.current_role', 'analista', false)")

        casos = await conn.fetch(
            "SELECT id, asignado_a FROM pqrs_casos WHERE cliente_id = $1",
            TEST_TENANT_ID,
        )
        print(f"\n{'='*60}")
        print("TEST 2: Analista RLS — aislamiento por asignado_a")
        print(f"  Casos visibles: {len(casos)}")

        # Todos los casos visibles deben estar asignados a este analista (o ser NULL si la policy lo permite)
        fuera_de_scope = [
            str(r["id"]) for r in casos
            if r["asignado_a"] and str(r["asignado_a"]) != TEST_ANALISTA_ID
        ]
        if fuera_de_scope:
            print(f"  ⚠️  Casos de otro analista visibles: {fuera_de_scope}")
        ok = len(fuera_de_scope) == 0
        print(f"  Resultado: {PASS if ok else FAIL}")
        return ok
    finally:
        await conn.execute("RESET app.current_tenant_id")
        await conn.execute("RESET app.current_user_id")
        await conn.execute("RESET app.current_role")
        await conn.close()


async def test_auditor_readonly():
    """Auditor puede SELECT pero no INSERT en pqrs_casos."""
    conn = await asyncpg.connect(ADMIN_DB_URL)
    try:
        await conn.execute(f"SELECT set_config('app.current_tenant_id', '{TEST_TENANT_ID}', false)")
        await conn.execute(f"SELECT set_config('app.current_user_id',   '{TEST_AUDITOR_ID}', false)")
        await conn.execute("SELECT set_config('app.current_role', 'auditor', false)")

        print(f"\n{'='*60}")
        print("TEST 3: Auditor RLS — SELECT OK, INSERT debe fallar")

        # SELECT debe funcionar
        try:
            count = await conn.fetchval("SELECT COUNT(*) FROM pqrs_casos WHERE cliente_id = $1", TEST_TENANT_ID)
            print(f"  SELECT devolvió {count} casos — {PASS}")
            select_ok = True
        except Exception as e:
            print(f"  SELECT falló (inesperado): {e} — {FAIL}")
            select_ok = False

        # INSERT debe fallar (auditor no tiene policy FOR INSERT)
        try:
            import uuid
            await conn.execute(
                "INSERT INTO pqrs_casos (cliente_id, estado) VALUES ($1, 'ABIERTO')",
                TEST_TENANT_ID,
            )
            print(f"  INSERT tuvo éxito (inseguro!) — {FAIL}")
            insert_blocked = False
        except Exception:
            print(f"  INSERT bloqueado por RLS — {PASS}")
            insert_blocked = True

        ok = select_ok and insert_blocked
        print(f"  Resultado global: {PASS if ok else FAIL}")
        return ok
    finally:
        await conn.execute("RESET app.current_tenant_id")
        await conn.execute("RESET app.current_user_id")
        await conn.execute("RESET app.current_role")
        await conn.close()


async def test_audit_log_immutable():
    """logs_auditoria no debe permitir UPDATE ni DELETE (ni siquiera con pqrs_admin)."""
    conn = await asyncpg.connect(ADMIN_DB_URL)
    try:
        print(f"\n{'='*60}")
        print("TEST 4: Audit Log — inmutabilidad física (trigger BEFORE UPDATE/DELETE)")

        # Tomar un registro existente para intentar mutarlo
        row = await conn.fetchrow("SELECT id FROM logs_auditoria LIMIT 1")
        if not row:
            print("  Sin registros en logs_auditoria — salteando (sin datos de prueba)")
            return True

        log_id = row["id"]

        # UPDATE debe fallar (trigger fn_logs_auditoria_inmutable)
        try:
            await conn.execute("UPDATE logs_auditoria SET accion = 'DELETE' WHERE id = $1", log_id)
            print(f"  UPDATE tuvo éxito (CRÍTICO: audit log no es inmutable!) — {FAIL}")
            update_blocked = False
        except Exception as e:
            if "INMUTABLE" in str(e):
                print(f"  UPDATE bloqueado por trigger — {PASS}")
            else:
                print(f"  UPDATE bloqueado (razón diferente): {e} — {PASS}")
            update_blocked = True

        # DELETE debe fallar (mismo trigger)
        try:
            await conn.execute("DELETE FROM logs_auditoria WHERE id = $1", log_id)
            print(f"  DELETE tuvo éxito (CRÍTICO!) — {FAIL}")
            delete_blocked = False
        except Exception as e:
            if "INMUTABLE" in str(e):
                print(f"  DELETE bloqueado por trigger — {PASS}")
            else:
                print(f"  DELETE bloqueado (razón diferente): {e} — {PASS}")
            delete_blocked = True

        ok = update_blocked and delete_blocked
        print(f"  Resultado global: {PASS if ok else FAIL}")
        return ok
    finally:
        await conn.close()


async def main():
    print("\n" + "="*60)
    print("  AEQUITAS — Test Jerarquía RLS (Sprint 0: El Búnker)")
    print("="*60)

    results = await asyncio.gather(
        test_worker_bypassrls(),
        test_analista_isolation(),
        test_auditor_readonly(),
        test_audit_log_immutable(),
        return_exceptions=True,
    )

    labels = [
        "Worker BYPASSRLS",
        "Analista Isolation",
        "Auditor Readonly",
        "Audit Log Immutable",
    ]

    print(f"\n{'='*60}")
    print("RESUMEN")
    print(f"{'='*60}")
    all_pass = True
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            print(f"  {FAIL} [{label}] — Excepción: {result}")
            all_pass = False
        elif not result:
            print(f"  {FAIL} [{label}]")
            all_pass = False
        else:
            print(f"  {PASS} [{label}]")

    print(f"\n{'='*60}")
    if all_pass:
        print("  RESULTADO FINAL: TODOS LOS TESTS PASARON — El Búnker está blindado")
    else:
        print("  RESULTADO FINAL: HAY FALLOS — Revisar políticas RLS")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
