"""Tests de visibilidad por rol en GET /casos/enviados/historial.

Contexto (2026-06-18): el tenant Abogados Recovery / ARC SAS provisiona a su
equipo con rol `abogado`. La regla previa (commit 8adcaca) restringía a todo
rol fuera de ROLES_VEN_TODO a ver SOLO sus propios envíos. Pedido del cliente:
los abogados deben ver el Enviados completo de su tenant. Fix: `abogado` pasa a
ROLES_VEN_TODO; `analista` (solo Demo) sigue restringido.

Tests unitarios: mockean conn + current_user. No tocan DB. Se asertan los
filtros SQL que arma el endpoint, capturando la query pasada a conn.fetch.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.api.routes.casos import historial_enviados
from app.core.security import UserInToken


TENANT = "effca814-b0b5-4329-96be-186c0333ad4b"  # Abogados Recovery
USUARIO_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"


def _user(rol):
    return UserInToken(
        usuario_id=USUARIO_ID,
        email="jpalacio@arcsas.com.co",
        role=rol,
        tenant_uuid=TENANT,
    )


def _conn():
    c = AsyncMock()
    c.fetch = AsyncMock(return_value=[])
    return c


async def _query_de(rol):
    """Ejecuta el endpoint y devuelve (query_sql, params) pasados a conn.fetch."""
    conn = _conn()
    await historial_enviados(current_user=_user(rol), conn=conn)
    args, _ = conn.fetch.call_args
    return args[0], args[1:]


@pytest.mark.asyncio
async def test_abogado_ve_todo_el_tenant_no_filtra_por_usuario():
    query, params = await _query_de("abogado")
    # Sigue aislado por tenant...
    assert "c.cliente_id = $1::uuid" in query
    # ...pero NO se restringe a su propio usuario_id (el JOIN usa a.usuario_id,
    # lo que NO debe aparecer es el FILTRO `a.usuario_id = $...`).
    assert "a.usuario_id = $" not in query
    assert uuid.UUID(USUARIO_ID) not in params


@pytest.mark.asyncio
async def test_analista_sigue_restringido_a_lo_propio():
    query, params = await _query_de("analista")
    assert "c.cliente_id = $1::uuid" in query
    assert "a.usuario_id = $2::uuid" in query
    assert uuid.UUID(USUARIO_ID) in params


@pytest.mark.asyncio
async def test_admin_ve_todo_el_tenant():
    query, _ = await _query_de("admin")
    assert "c.cliente_id = $1::uuid" in query
    assert "a.usuario_id = $" not in query
