"""Tests de la Bandeja unificada GET /admin/casos (listar_casos_admin).

Contexto (2026-06-18): modelo "cada abogado ve lo suyo". admin/super ven todo
el tenant; abogado/analista ven SOLO su cartera (casos con asignado_a = ellos),
ignorando cualquier asignado_a del query. Roles no permitidos → 403.

Tests unitarios: mockean conn + current_user. No tocan DB. Se asertan los
filtros SQL (query de COUNT pasada a conn.fetchval) y los params.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.routes.admin import listar_casos_admin
from app.core.security import UserInToken


TENANT = "effca814-b0b5-4329-96be-186c0333ad4b"
USUARIO_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"
OTRO_USUARIO = "11111111-2222-3333-4444-555555555555"


def _user(rol):
    return UserInToken(usuario_id=USUARIO_ID, email="x@arcsas.com.co", role=rol, tenant_uuid=TENANT)


def _conn():
    c = AsyncMock()
    c.fetchval = AsyncMock(return_value=0)
    c.fetch = AsyncMock(return_value=[])
    return c


async def _count_query(rol, **kw):
    conn = _conn()
    await listar_casos_admin(current_user=_user(rol), conn=conn, **kw)
    args, _ = conn.fetchval.call_args  # SELECT COUNT(*) ... WHERE {where}
    return args[0], args[1:]


@pytest.mark.asyncio
async def test_abogado_ve_solo_su_cartera():
    query, params = await _count_query("abogado")
    assert "c.cliente_id = $1::uuid" in query          # scoped al tenant
    assert "c.asignado_a = $2::uuid" in query           # forzado a su cartera
    assert uuid.UUID(USUARIO_ID) in params


@pytest.mark.asyncio
async def test_abogado_no_puede_espiar_otra_cartera():
    # aunque pase asignado_a=otro, se ignora y se fuerza el propio
    query, params = await _count_query("abogado", asignado_a=OTRO_USUARIO)
    assert uuid.UUID(USUARIO_ID) in params
    assert uuid.UUID(OTRO_USUARIO) not in params


@pytest.mark.asyncio
async def test_analista_tambien_scoped():
    query, params = await _count_query("analista")
    assert "c.asignado_a = $2::uuid" in query
    assert uuid.UUID(USUARIO_ID) in params


@pytest.mark.asyncio
async def test_admin_ve_todo_el_tenant_sin_forzar_asignado():
    query, params = await _count_query("admin")
    assert "c.cliente_id = $1::uuid" in query
    assert uuid.UUID(USUARIO_ID) not in params          # no se fuerza su usuario


@pytest.mark.asyncio
async def test_rol_no_permitido_403():
    with pytest.raises(HTTPException) as exc:
        await _count_query("auditor")
    assert exc.value.status_code == 403
