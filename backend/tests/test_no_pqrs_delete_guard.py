"""Guard del borrado No PQRS: un caso movido a ATENCION_CLIENTE queda con
es_pqrs=False (señal de aprendizaje) pero NO debe ser borrable desde el flujo
de descarte. Solo se borran casos tipo_workflow='PQRS'.

Unitario: mockea conn + current_user. No toca DB.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes.admin import eliminar_caso_no_pqrs
from app.core.security import UserInToken

TENANT_FF = "f7e8d9c0-b1a2-3456-7890-123456abcdef"
CASO_ID = "11111111-2222-3333-4444-555555555555"


def _user(rol="admin"):
    return UserInToken(usuario_id="66666666-7777-8888-9999-aaaaaaaaaaaa",
                       email="a@b.com", role=rol, tenant_uuid=TENANT_FF)


def _conn(es_pqrs, tipo_workflow):
    c = MagicMock()
    c.fetchrow = AsyncMock(return_value={
        "id": uuid.UUID(CASO_ID),
        "es_pqrs": es_pqrs,
        "tipo_workflow": tipo_workflow,
        "cliente_id": uuid.UUID(TENANT_FF),
    })
    c.execute = AsyncMock(return_value="OK")
    return c


@pytest.mark.asyncio
async def test_caso_ac_no_es_borrable():
    """es_pqrs=False pero tipo_workflow=ATENCION_CLIENTE → 400 (protegido)."""
    with pytest.raises(HTTPException) as ei:
        await eliminar_caso_no_pqrs(CASO_ID, _user(), _conn(es_pqrs=False, tipo_workflow="ATENCION_CLIENTE"))
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_caso_pqrs_no_pqr_si_es_borrable():
    """es_pqrs=False y tipo_workflow=PQRS → se borra OK."""
    conn = _conn(es_pqrs=False, tipo_workflow="PQRS")
    r = await eliminar_caso_no_pqrs(CASO_ID, _user(), conn)
    assert r["ok"] is True
    assert r["deleted"] == CASO_ID
