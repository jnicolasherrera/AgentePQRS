"""
Regression check ARC: verifica que el seed sintético del tenant ARC Staging
(`00000000-0001-0001-0001-000000000001`) no fue alterado por las migraciones
18-22 ni por el pipeline.

Es un test que se ejecuta opt-in con RUN_STAGING_REGRESSION=1 contra staging
(via tunnel SSH al port 5434). Sin esa env, se skipea para que el resto de la
suite pueda correr en cualquier entorno.

Validaciones:
- Los 5 casos TUTELA y 20 PQRS sintéticos del seed siguen presentes con sus
  external_msg_id originales (FIXTURE_V1_TUTELA_*, FIXTURE_V1_*).
- Ninguno tiene metadata_especifica modificada inesperadamente (el seed los
  inserta con `{}` por default).
- 4 abogados/analistas ARC siguen con sus 2 capabilities cada uno.
- El conteo de casos no decreció (no se borró nada).
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest


STAGING_DB_URL = os.environ.get(
    "STAGING_DB_URL",
    "postgresql://pqrs_admin:pg_password@localhost:5434/pqrs_v2",
)
ARC_STAGING = uuid.UUID("00000000-0001-0001-0001-000000000001")


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_STAGING_REGRESSION") != "1",
    reason="Set RUN_STAGING_REGRESSION=1 (requires SSH tunnel a staging port 5434).",
)


@pytest.mark.asyncio
async def test_arc_seed_intacto():
    conn = await asyncpg.connect(STAGING_DB_URL)
    try:
        # Casos seed (FIXTURE_V1_*) deben ser >= 25 (5 tutelas + 20 PQRS).
        seed_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pqrs_casos "
            "WHERE cliente_id = $1 AND external_msg_id LIKE 'FIXTURE_V1_%'",
            ARC_STAGING,
        )
        assert seed_count >= 25, f"Solo {seed_count} casos seed restantes (esperaba >=25)"

        # 5 tutelas seed.
        tutelas_seed = await conn.fetchval(
            "SELECT COUNT(*) FROM pqrs_casos "
            "WHERE cliente_id = $1 AND external_msg_id LIKE 'FIXTURE_V1_TUTELA_%'",
            ARC_STAGING,
        )
        assert tutelas_seed == 5, f"Esperaba 5 tutelas seed, hay {tutelas_seed}"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_arc_capabilities_siguen():
    conn = await asyncpg.connect(STAGING_DB_URL)
    try:
        # 4 usuarios x 2 capabilities (CAN_SIGN_DOCUMENT + CAN_APPROVE_RESPONSE) = 8.
        grants = await conn.fetchval(
            "SELECT COUNT(*) FROM user_capabilities "
            "WHERE cliente_id = $1 AND scope = 'TUTELA' AND revoked_at IS NULL",
            ARC_STAGING,
        )
        assert grants == 8, f"Esperaba 8 grants TUTELA en ARC, hay {grants}"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_arc_smoke_case_persiste():
    """El caso del smoke E2E del Agente 3 (asunto [SMOKE_TEST_AGENTE3]...) sigue."""
    conn = await asyncpg.connect(STAGING_DB_URL)
    try:
        smoke_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pqrs_casos WHERE asunto LIKE '[SMOKE_TEST_AGENTE3]%'",
        )
        assert smoke_count >= 1, "El caso smoke del Agente 3 fue removido"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_arc_no_tutela_metadata_vacia():
    """Los PQRS no-tutela del seed ARC tienen metadata_especifica='{}' (sin enricher)."""
    conn = await asyncpg.connect(STAGING_DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT external_msg_id, metadata_especifica::text AS md
            FROM pqrs_casos
            WHERE cliente_id = $1
              AND external_msg_id LIKE 'FIXTURE_V1_%'
              AND tipo_caso != 'TUTELA'
            """,
            ARC_STAGING,
        )
        for r in rows:
            md = r["md"]
            assert md == "{}", f"PQRS {r['external_msg_id']} tiene metadata={md}"
    finally:
        await conn.close()
