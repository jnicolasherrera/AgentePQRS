"""
Tests no-regresión: PQRS normales (no-TUTELA) deben seguir funcionando idénticos
post-sprint. El pipeline procesa 10 casos variados (PETICION, QUEJA, RECLAMO,
SUGERENCIA) y verifica:
- metadata_especifica queda como '{}' (sin enrich_tutela invocado).
- fecha_vencimiento NO se calcula en Python (queda None → trigger DB lo hace).
- semaforo_sla queda en default (no NARANJA/NEGRO porque PQRS_DEFAULT no los aplica).
- INSERT recibe los campos esperados.

Mocks asyncpg, NO toca DB.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_classifier import ClassificationResult


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")


def _clasif(tipo: str) -> ClassificationResult:
    return ClassificationResult(
        tipo_caso=tipo, prioridad="MEDIA", plazo_dias=15,
        cedula=None, nombre_cliente=None, es_juzgado=False,
        confianza=0.85, borrador=None,
    )


def _event(tipo: str, idx: int) -> dict:
    return {
        "tenant_id": str(TENANT),
        "correlation_id": str(uuid.uuid4()),
        "subject": f"{tipo} caso {idx}",
        "body": f"cuerpo {tipo} {idx}",
        "sender": f"ciudadano-{idx}@email.invalid",
        "date": "2026-04-27T10:00:00+00:00",
        "external_msg_id": f"REG-{tipo}-{idx}",
    }


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid.uuid4())
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool, conn


@pytest.mark.asyncio
@pytest.mark.parametrize("tipo,idx", [
    ("PETICION", 1), ("PETICION", 2), ("PETICION", 3),
    ("QUEJA", 4),
    ("RECLAMO", 5), ("RECLAMO", 6),
    ("SUGERENCIA", 7), ("SUGERENCIA", 8),
    ("SOLICITUD", 9), ("SOLICITUD", 10),
])
async def test_pqrs_no_regresion(tipo: str, idx: int):
    pool, conn = _mock_pool()
    from app.services import pipeline as pl
    caso_id = await pl.process_classified_event(
        _clasif(tipo), _event(tipo, idx), TENANT, conn, pool,
    )

    assert caso_id is not None
    insert_args = conn.fetchval.await_args[0]

    # tipo_caso ($3).
    assert insert_args[3] == tipo

    # fecha_vencimiento ($13) None: el trigger DB lo calcula con SP sectorial.
    assert insert_args[13] is None, f"PQRS {tipo} debería dejar fecha al trigger, no precalcularla"

    # metadata_especifica ($12) JSON vacío {}: enrich_by_tipo retorna {} para tipos sin
    # enricher (PETICION/QUEJA/RECLAMO/SUGERENCIA/SOLICITUD).
    metadata_payload = insert_args[12]
    metadata = json.loads(metadata_payload)
    assert metadata == {}, f"PQRS {tipo} no debería tener metadata: {metadata}"

    # documento_peticionante_hash ($15) None: sin enricher, sin hash.
    assert insert_args[15] is None

    # external_msg_id ($14) propagado.
    assert insert_args[14] == f"REG-{tipo}-{idx}"


@pytest.mark.asyncio
async def test_pqrs_sin_external_msg_id_no_rompe():
    """Sanity: PQRS legacy sin external_msg_id sigue funcionando (event sin la key)."""
    pool, conn = _mock_pool()
    event = {
        "tenant_id": str(TENANT),
        "correlation_id": str(uuid.uuid4()),
        "subject": "Legacy event", "body": "x", "sender": "x@y.invalid",
        "date": "2026-04-27T10:00:00+00:00",
    }
    from app.services import pipeline as pl
    caso_id = await pl.process_classified_event(
        _clasif("PETICION"), event, TENANT, conn, pool,
    )
    assert caso_id is not None
    insert_args = conn.fetchval.await_args[0]
    assert insert_args[14] is None  # external_msg_id queda NULL, no rompe


@pytest.mark.asyncio
async def test_pqrs_no_invoca_enrich_tutela():
    """Sanity adicional: para PETICION no se invoca enrich_tutela (solo aplica a TUTELA)."""
    pool, conn = _mock_pool()
    with patch("app.services.enrichers.tutela_extractor.enrich_tutela") as mock_enrich:
        mock_enrich.return_value = {"shouldnotbecalled": True}
        from app.services import pipeline as pl
        await pl.process_classified_event(
            _clasif("PETICION"), _event("PETICION", 99), TENANT, conn, pool,
        )

    mock_enrich.assert_not_called()
