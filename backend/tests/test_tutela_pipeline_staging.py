"""
Smoke E2E staging — Agente 3 sprint Tutelas.

Construye un evento sintético (estructura Outlook/Gmail), lo pasa por
`pipeline.process_classified_event` contra la DB real de staging, y
verifica:
 1. Caso insertado con asunto "[SMOKE_TEST_AGENTE3] ...".
 2. metadata_especifica poblada (si el extractor corrió).
 3. fecha_vencimiento calculada (trigger o sla_engine Python).

Uso:
    pytest backend/tests/test_tutela_pipeline_staging.py -v -s

Requisitos:
 - DATABASE_URL apuntando a staging (ej. configurado en .env o env var).
 - ANTHROPIC_API_KEY si se quiere ejercitar Claude real (1 call).
   Sin la key, el extractor usa su fallback defensivo y el pipeline sigue.
 - Nico autoriza máximo 1-3 calls reales al API de Claude desde acá.

El test NO hace ROLLBACK para dejar el caso disponible al Agente 4.
Identificación para cleanup posterior: asunto con marker `[SMOKE_TEST_AGENTE3]`
y external_msg_id = `SMOKE_AGENTE3_{uuid}`.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from app.services.ai_classifier import ClassificationResult
from app.services.pipeline import process_classified_event


# Staging DB — usa la connection string que tiene el container backend local o .env.
STAGING_DB_URL = os.environ.get(
    "STAGING_DB_URL",
    "postgresql://pqrs_admin:pg_password@15.229.114.148:5434/pqrs_v2",
)

# UUIDs del seed sintético (migración 99).
ARC_STAGING = uuid.UUID("00000000-0001-0001-0001-000000000001")

SMOKE_MARKER = "[SMOKE_TEST_AGENTE3]"


def _synthetic_tutela_body() -> str:
    """Cuerpo mínimo de una tutela sintética con marker del fixture."""
    return (
        "SYNTHETIC_FIXTURE_V1\n\n"
        "Señor Juez, me dirijo a usted para notificar la siguiente acción de tutela.\n"
        "Expediente: 11001-9999-888-2026-00999-00.\n"
        "Término para rendir informe: dos (2) días hábiles.\n"
        "Accionante: peticionario sintético para smoke test — documento 1012345678.\n"
        "Derechos invocados: derecho de petición.\n"
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("RUN_STAGING_SMOKE") != "1",
    reason="Set RUN_STAGING_SMOKE=1 to enable. Requires network access to staging DB.",
)
async def test_smoke_pipeline_tutela_staging():
    corr_id = uuid.uuid4()
    event = {
        "tenant_id": str(ARC_STAGING),
        "correlation_id": str(corr_id),
        "subject": f"{SMOKE_MARKER} Tutela sintética Agente 3 {corr_id}",
        "body": _synthetic_tutela_body(),
        "sender": f"juzgado-smoke-{corr_id}@fixture.invalid",
        "date": datetime.now(timezone.utc).isoformat(),
        "external_msg_id": f"SMOKE_AGENTE3_{corr_id}",
    }
    clasif = ClassificationResult(
        tipo_caso="TUTELA",
        prioridad="ALTA",
        plazo_dias=2,
        cedula=None,
        nombre_cliente=None,
        es_juzgado=True,
        confianza=0.95,
        borrador=None,
    )

    pool = await asyncpg.create_pool(STAGING_DB_URL, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            caso_id = await process_classified_event(
                clasif, event, ARC_STAGING, conn, pool,
            )

            # Verificar el caso en DB.
            row = await conn.fetchrow(
                """
                SELECT id, tipo_caso, asunto, fecha_vencimiento, metadata_especifica,
                       external_msg_id
                FROM pqrs_casos
                WHERE id = $1
                """,
                caso_id,
            )
            assert row is not None, "El caso no aparece en DB"
            assert row["tipo_caso"] == "TUTELA"
            assert SMOKE_MARKER in row["asunto"]
            assert row["external_msg_id"] == event["external_msg_id"]
            # fecha_vencimiento debe estar calculada (por trigger o pipeline).
            assert row["fecha_vencimiento"] is not None, "fecha_vencimiento quedó NULL"
            # metadata_especifica: puede ser {} si no hay API key o extractor falló,
            # o dict con keys si corrió Claude. Ambos son válidos para smoke.
            assert row["metadata_especifica"] is not None

            print(f"\n[SMOKE OK] caso_id={caso_id}")
            print(f"           tipo={row['tipo_caso']}")
            print(f"           fecha_vencimiento={row['fecha_vencimiento']}")
            print(f"           metadata_especifica={row['metadata_especifica']}")
    finally:
        await pool.close()


if __name__ == "__main__":
    # Permite correr manualmente: python tests/test_tutela_pipeline_staging.py
    os.environ["RUN_STAGING_SMOKE"] = "1"
    asyncio.run(test_smoke_pipeline_tutela_staging())
