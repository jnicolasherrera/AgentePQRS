import asyncio
import asyncpg
import os
from datetime import datetime, timezone

STAGING_DB_URL = os.environ.get(
    "STAGING_DB_URL",
    "postgresql://pqrs_admin:pg_password@localhost:5432/pqrs_v2"
)
PASS = "PASS"
FAIL = "FAIL"
TENANT_DEMO = "11111111-1111-1111-1111-111111111111"

async def main():
    conn = await asyncpg.connect(STAGING_DB_URL)
    print("\n" + "="*60)
    print("TEST: Motor SLA Sectorial — Migracion 14")
    print("="*60)

    # Test 1: tabla existe y tiene datos
    count = await conn.fetchval("SELECT COUNT(*) FROM sla_regimen_config")
    ok = count >= 16
    print(f"\nTest 1 — sla_regimen_config poblada: {PASS if ok else FAIL}")
    print(f"  Registros: {count} (esperado >= 16)")

    # Test 2: FINANCIERO + QUEJA = 8 dias
    dias = await conn.fetchval(
        "SELECT dias_habiles FROM sla_regimen_config WHERE regimen='FINANCIERO' AND tipo_caso='QUEJA'"
    )
    ok = dias == 8
    print(f"\nTest 2 — FINANCIERO/QUEJA = 8 dias: {PASS if ok else FAIL}")
    print(f"  Dias: {dias} (esperado: 8)")

    # Test 3: GENERAL + QUEJA = 15 dias
    dias = await conn.fetchval(
        "SELECT dias_habiles FROM sla_regimen_config WHERE regimen='GENERAL' AND tipo_caso='QUEJA'"
    )
    ok = dias == 15
    print(f"\nTest 3 — GENERAL/QUEJA = 15 dias: {PASS if ok else FAIL}")
    print(f"  Dias: {dias} (esperado: 15)")

    # Test 4: columna regimen_sla existe
    col = await conn.fetchval(
        "SELECT column_name FROM information_schema.columns WHERE table_name='clientes_tenant' AND column_name='regimen_sla'"
    )
    ok = col is not None
    print(f"\nTest 4 — Columna regimen_sla en clientes_tenant: {PASS if ok else FAIL}")

    # Test 5: calculo GENERAL/QUEJA desde 8-abril-2026
    await conn.execute("UPDATE clientes_tenant SET regimen_sla='GENERAL' WHERE id=$1", TENANT_DEMO)
    fecha_test = datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc)
    venc_general = await conn.fetchval(
        "SELECT calcular_fecha_vencimiento($1, $2, 'QUEJA')", fecha_test, TENANT_DEMO
    )
    dias_cal = (venc_general.date() - fecha_test.date()).days
    ok = 18 <= dias_cal <= 25
    print(f"\nTest 5 — Calculo GENERAL/QUEJA: {PASS if ok else FAIL}")
    print(f"  Vence: {venc_general.date()} ({dias_cal} dias calendario)")

    # Test 6: calculo FINANCIERO/QUEJA — debe vencer antes
    await conn.execute("UPDATE clientes_tenant SET regimen_sla='FINANCIERO' WHERE id=$1", TENANT_DEMO)
    venc_fin = await conn.fetchval(
        "SELECT calcular_fecha_vencimiento($1, $2, 'QUEJA')", fecha_test, TENANT_DEMO
    )
    dias_cal_fin = (venc_fin.date() - fecha_test.date()).days
    ok = 8 <= dias_cal_fin <= 14
    print(f"\nTest 6 — Calculo FINANCIERO/QUEJA: {PASS if ok else FAIL}")
    print(f"  Vence: {venc_fin.date()} ({dias_cal_fin} dias calendario)")

    diferencia = (venc_general.date() - venc_fin.date()).days
    print(f"\n  > Diferencia GENERAL vs FINANCIERO: {diferencia} dias menos para banco")
    print(f"    GENERAL vence:    {venc_general.date()}")
    print(f"    FINANCIERO vence: {venc_fin.date()}")

    # Test 7: TUTELA es igual en ambos regimenes (siempre 2 dias)
    await conn.execute("UPDATE clientes_tenant SET regimen_sla='FINANCIERO' WHERE id=$1", TENANT_DEMO)
    venc_t = await conn.fetchval(
        "SELECT calcular_fecha_vencimiento($1, $2, 'TUTELA')", fecha_test, TENANT_DEMO
    )
    dias_t = (venc_t.date() - fecha_test.date()).days
    ok = 2 <= dias_t <= 5
    print(f"\nTest 7 — TUTELA siempre 2 dias habiles: {PASS if ok else FAIL}")
    print(f"  Vence: {venc_t.date()} ({dias_t} dias calendario)")

    # Restaurar tenant demo a GENERAL
    await conn.execute("UPDATE clientes_tenant SET regimen_sla='GENERAL' WHERE id=$1", TENANT_DEMO)

    print("\n" + "="*60)
    print("FIN — tenant demo restaurado a GENERAL")
    print("="*60 + "\n")
    await conn.close()

asyncio.run(main())
