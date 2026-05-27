"""Tests del endpoint PATCH /casos/{id}/destinatario y del enviar-lote
con override (sprint FlexFintech 2026-05-27, bloque 5).

Tests unitarios: mockean conn + current_user. No tocan DB ni SMTP.
"""

from __future__ import annotations

import json
import re
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.routes.casos import (
    DestinatarioOverrideRequest,
    _EMAIL_OVERRIDE_RE,
    editar_destinatario,
)
from app.core.security import UserInToken


TENANT_FF = "f7e8d9c0-b1a2-3456-7890-123456abcdef"
CASO_ID = "11111111-2222-3333-4444-555555555555"
USUARIO_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"


def _user(rol="admin", tenant=TENANT_FF):
    return UserInToken(
        usuario_id=USUARIO_ID,
        email="mica@flexfintech.com",
        role=rol,
        tenant_uuid=tenant,
    )


def _conn(caso_existe=True, email_actual_override=None):
    c = MagicMock()
    if caso_existe:
        c.fetchrow = AsyncMock(return_value={
            "id": uuid.UUID(CASO_ID),
            "cliente_id": uuid.UUID(TENANT_FF),
            "email_origen": "cliente@gmail.com",
            "email_respuesta_override": email_actual_override,
        })
    else:
        c.fetchrow = AsyncMock(return_value=None)
    c.execute = AsyncMock(return_value="OK")
    return c


def _request(host="1.2.3.4"):
    req = MagicMock()
    req.client = MagicMock(host=host)
    return req


# --------------------------------------------------------------------------- #
# Validación de email
# --------------------------------------------------------------------------- #

class TestEmailValidation:
    @pytest.mark.parametrize("email,ok", [
        ("user@example.com",              True),
        ("juan.perez+tag@gmail.com",      True),
        ("nuevomail@otro-dominio.co",     True),
        ("UPPER@DOMAIN.COM",              True),    # se normaliza a lower
        ("notanemail",                    False),
        ("@nodomain.com",                 False),
        ("nouser@",                       False),
        ("nodot@x",                       False),
        ("",                              False),  # vacío != null (lo trata como "quitar")
        ("a a@b.com",                     False),
    ])
    def test_regex(self, email, ok):
        # Validación interna del regex (sin normalizar)
        if email.strip().lower():
            assert bool(_EMAIL_OVERRIDE_RE.match(email.strip().lower())) == ok


# --------------------------------------------------------------------------- #
# Permisos
# --------------------------------------------------------------------------- #

class TestPermisos:
    @pytest.mark.asyncio
    async def test_analista_403(self):
        from fastapi import HTTPException
        body = DestinatarioOverrideRequest(email="nuevo@x.com")
        with pytest.raises(HTTPException) as ei:
            await editar_destinatario(CASO_ID, body, _request(), _user(rol="analista"), _conn())
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_abogado_403(self):
        from fastapi import HTTPException
        body = DestinatarioOverrideRequest(email="nuevo@x.com")
        with pytest.raises(HTTPException) as ei:
            await editar_destinatario(CASO_ID, body, _request(), _user(rol="abogado"), _conn())
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_OK(self):
        body = DestinatarioOverrideRequest(email="nuevo@x.com")
        r = await editar_destinatario(CASO_ID, body, _request(), _user(rol="admin"), _conn())
        assert r["status"] == "ok"

    @pytest.mark.asyncio
    async def test_super_admin_OK(self):
        body = DestinatarioOverrideRequest(email="nuevo@x.com")
        r = await editar_destinatario(CASO_ID, body, _request(), _user(rol="super_admin"), _conn())
        assert r["status"] == "ok"


# --------------------------------------------------------------------------- #
# Casos de uso
# --------------------------------------------------------------------------- #

class TestCasosDeUso:
    @pytest.mark.asyncio
    async def test_set_override_normal(self):
        conn = _conn(email_actual_override=None)
        body = DestinatarioOverrideRequest(email="NUEVO@otro.com")  # uppercase
        r = await editar_destinatario(CASO_ID, body, _request(), _user(), conn)
        assert r["email_destinatario_efectivo"] == "nuevo@otro.com"
        assert r["fue_override"] is True

        # UPDATE pqrs_casos con el email normalizado lowercased
        update_call = conn.execute.call_args_list[0]
        assert "UPDATE pqrs_casos" in update_call.args[0]
        assert update_call.args[1] == "nuevo@otro.com"

        # Audit con metadata correcta
        audit_call = conn.execute.call_args_list[1]
        assert "DESTINATARIO_EDITADO" in audit_call.args[0]
        metadata = json.loads(audit_call.args[4])
        assert metadata["anterior"] == "cliente@gmail.com"
        assert metadata["nuevo"] == "nuevo@otro.com"
        assert metadata["tipo_cambio"] == "SET_OVERRIDE"

    @pytest.mark.asyncio
    async def test_quitar_override_email_null(self):
        conn = _conn(email_actual_override="anterior@x.com")
        body = DestinatarioOverrideRequest(email=None)
        r = await editar_destinatario(CASO_ID, body, _request(), _user(), conn)
        assert r["fue_override"] is False
        assert r["email_destinatario_efectivo"] == "cliente@gmail.com"  # vuelve al origen

        # UPDATE con NULL
        update_call = conn.execute.call_args_list[0]
        assert update_call.args[1] is None

        # Audit registra tipo_cambio=QUITAR_OVERRIDE
        audit_call = conn.execute.call_args_list[1]
        metadata = json.loads(audit_call.args[4])
        assert metadata["tipo_cambio"] == "QUITAR_OVERRIDE"
        assert metadata["anterior"] == "anterior@x.com"
        assert metadata["nuevo"] is None

    @pytest.mark.asyncio
    async def test_quitar_override_email_vacio(self):
        """email='' debe tratarse como quitar override (mismo que None)."""
        conn = _conn(email_actual_override="anterior@x.com")
        body = DestinatarioOverrideRequest(email="")
        r = await editar_destinatario(CASO_ID, body, _request(), _user(), conn)
        assert r["fue_override"] is False

    @pytest.mark.asyncio
    async def test_email_invalido_400(self):
        from fastapi import HTTPException
        body = DestinatarioOverrideRequest(email="no_es_un_email")
        with pytest.raises(HTTPException) as ei:
            await editar_destinatario(CASO_ID, body, _request(), _user(), _conn())
        assert ei.value.status_code == 400
        assert "inválido" in ei.value.detail.lower()

    @pytest.mark.asyncio
    async def test_caso_no_encontrado_404(self):
        from fastapi import HTTPException
        body = DestinatarioOverrideRequest(email="nuevo@x.com")
        with pytest.raises(HTTPException) as ei:
            await editar_destinatario(CASO_ID, body, _request(), _user(), _conn(caso_existe=False))
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_otro_tenant_no_ve_caso(self):
        """admin de tenant X no puede editar caso de tenant Y (scope tenant)."""
        from fastapi import HTTPException
        body = DestinatarioOverrideRequest(email="nuevo@x.com")
        # _conn devuelve None porque la WHERE filtra por cliente_id
        conn = _conn(caso_existe=False)
        otro_tenant = "99999999-9999-9999-9999-999999999999"
        with pytest.raises(HTTPException) as ei:
            await editar_destinatario(CASO_ID, body, _request(),
                                      _user(rol="admin", tenant=otro_tenant), conn)
        assert ei.value.status_code == 404

        # Verifica que el SELECT incluye scope tenant ($2 OR cliente_id = $3)
        sel_args = conn.fetchrow.call_args.args
        assert "cliente_id = $3" in sel_args[0]
        assert sel_args[2] is False  # es_super False para admin común
