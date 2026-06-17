"""Tests del endpoint PATCH /admin/casos/{id}/workflow (reclasificación PQRS⇄AC).

Unitarios: mockean conn + current_user. No tocan DB. Espejo de
test_destinatario_override.py.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes.admin import ReclasificarWorkflowRequest, reclasificar_workflow
from app.core.security import UserInToken

TENANT_FF = "f7e8d9c0-b1a2-3456-7890-123456abcdef"
CASO_ID = "11111111-2222-3333-4444-555555555555"
USUARIO_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"


def _user(rol="admin", tenant=TENANT_FF):
    return UserInToken(usuario_id=USUARIO_ID, email="mica@flexfintech.com",
                       role=rol, tenant_uuid=tenant)


def _conn(caso_existe=True, tipo_actual="PQRS", tiene_ac=True):
    c = MagicMock()
    wf = [{"tipo_workflow": "PQRS"}]
    if tiene_ac:
        wf.append({"tipo_workflow": "ATENCION_CLIENTE"})
    c.fetch = AsyncMock(return_value=wf)
    if caso_existe:
        c.fetchrow = AsyncMock(return_value={
            "id": uuid.UUID(CASO_ID),
            "tipo_workflow": tipo_actual,
            "tipo_caso": "RECLAMO",
            "cliente_id": uuid.UUID(TENANT_FF),
        })
    else:
        c.fetchrow = AsyncMock(return_value=None)
    c.execute = AsyncMock(return_value="OK")
    return c


class TestPermisos:
    @pytest.mark.asyncio
    async def test_analista_403(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(rol="analista"), _conn())
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tenant_sin_ac_403(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(), _conn(tiene_ac=False))
        assert ei.value.status_code == 403


class TestValidacion:
    @pytest.mark.asyncio
    async def test_workflow_invalido_400(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="BANANA")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(), _conn())
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_caso_no_encontrado_404(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(), _conn(caso_existe=False))
        assert ei.value.status_code == 404


class TestReclasificacion:
    @pytest.mark.asyncio
    async def test_pqr_a_ac(self):
        conn = _conn(tipo_actual="PQRS")
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        r = await reclasificar_workflow(CASO_ID, body, _user(), conn)
        assert r["ok"] is True
        assert r["tipo_workflow"] == "ATENCION_CLIENTE"
        upd = conn.execute.call_args_list[0]
        assert "UPDATE pqrs_casos" in upd.args[0]
        assert upd.args[1] == "ATENCION_CLIENTE"
        assert upd.args[2] is False
        audit = conn.execute.call_args_list[2]
        assert "WORKFLOW_RECLASIFICADO" in audit.args[0]
        meta = json.loads(audit.args[3])
        assert meta == {"anterior": "PQRS", "nuevo": "ATENCION_CLIENTE"}

    @pytest.mark.asyncio
    async def test_ac_a_pqr(self):
        conn = _conn(tipo_actual="ATENCION_CLIENTE")
        body = ReclasificarWorkflowRequest(tipo_workflow="PQRS")
        r = await reclasificar_workflow(CASO_ID, body, _user(), conn)
        assert r["tipo_workflow"] == "PQRS"
        upd = conn.execute.call_args_list[0]
        assert upd.args[1] == "PQRS"
        assert upd.args[2] is True
