"""Tests del flow ATENCION_CLIENTE (sprint FlexFintech 2026-05-27, bloque 3).

Mockea asyncpg + redis + provider Outlook/Zoho — no toca recursos externos.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import del worker — tiene side-effects de imports de app.* en /app PYTHONPATH.
# Pero como la función es independiente, solo importamos eso.
import sys
sys.path.insert(0, "/app")
from master_worker_outlook import procesar_atencion_cliente


TENANT_FF = uuid.UUID("f7e8d9c0-b1a2-3456-7890-123456abcdef")


def _mock_conn(insert_returns=None):
    """asyncpg.Connection mock."""
    c = MagicMock()
    c.execute = AsyncMock(return_value="OK")
    c.fetch = AsyncMock(return_value=[])  # no agentes por default
    c.fetchval = AsyncMock(return_value=insert_returns)
    return c


def _mock_redis(rr_idx=1):
    r = MagicMock()
    r.incr = AsyncMock(return_value=rr_idx)
    r.publish = AsyncMock(return_value=1)
    return r


def _em(subject="Test", body="cuerpo", sender="test@x.com", msg_id="msg-001"):
    prov_obj = MagicMock()
    prov_obj.mark_as_read = MagicMock(return_value=None)
    return {
        "id": msg_id,
        "subject": subject,
        "body": body,
        "sender": sender,
        "email_buzon": "clientes@flexfintech.com",
        "prov_obj": prov_obj,
        "attachments": [],
    }


def _buzon():
    return {"tipo_workflow": "PQRS", "cliente_nombre": "FlexFintech"}


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

class TestProcesarAtencionCliente:
    @pytest.mark.asyncio
    async def test_insert_con_tipo_workflow_atencion_cliente(self):
        nuevo_id = uuid.uuid4()
        conn = _mock_conn(insert_returns=nuevo_id)
        r = _mock_redis()
        em = _em(subject="Solicito paz y salvo", body="Necesito mi certificado")

        with patch("master_worker_outlook.generar_borrador_para_caso", new=AsyncMock()):
            db_id = await procesar_atencion_cliente(
                conn, r, em, TENANT_FF, _buzon(),
                datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc), "OUTLOOK",
            )

        assert db_id == nuevo_id

        # INSERT SQL contiene tipo_workflow='ATENCION_CLIENTE'
        insert_call = conn.fetchval.call_args
        sql = insert_call.args[0]
        assert "'ATENCION_CLIENTE'" in sql
        assert "tipo_workflow" in sql
        assert "problematica_detectada" in sql

    @pytest.mark.asyncio
    async def test_publica_sse_con_tipo_atencion_cliente(self):
        nuevo_id = uuid.uuid4()
        conn = _mock_conn(insert_returns=nuevo_id)
        r = _mock_redis()
        em = _em(subject="Paz y salvo", body="Comprobante")

        with patch("master_worker_outlook.generar_borrador_para_caso", new=AsyncMock()):
            await procesar_atencion_cliente(
                conn, r, em, TENANT_FF, _buzon(),
                datetime(2026, 5, 27, tzinfo=timezone.utc), "OUTLOOK",
            )

        # publish llamado con tipo='ATENCION_CLIENTE'
        publish_call = r.publish.call_args
        canal = publish_call.args[0]
        payload = json.loads(publish_call.args[1])
        assert canal == "pqrs_stream_v2"
        assert payload["tipo"] == "ATENCION_CLIENTE"
        assert payload["prioridad"] == "NORMAL"

    @pytest.mark.asyncio
    async def test_email_ya_procesado_devuelve_none_sin_publish(self):
        """ON CONFLICT devuelve None → no debe publicar SSE ni mark_as_read."""
        conn = _mock_conn(insert_returns=None)
        r = _mock_redis()
        em = _em()

        with patch("master_worker_outlook.generar_borrador_para_caso", new=AsyncMock()) as mock_borr:
            db_id = await procesar_atencion_cliente(
                conn, r, em, TENANT_FF, _buzon(),
                datetime(2026, 5, 27, tzinfo=timezone.utc), "OUTLOOK",
            )

        assert db_id is None
        r.publish.assert_not_called()
        mock_borr.assert_not_called()
        em["prov_obj"].mark_as_read.assert_not_called()

    @pytest.mark.asyncio
    async def test_round_robin_asigna_admin_si_no_hay_analistas(self):
        """FlexFintech tiene solo admins (Mica, Paula). Round-robin debe
        incluir rol='admin' además de analista/abogado."""
        admin1, admin2 = uuid.uuid4(), uuid.uuid4()
        nuevo_id = uuid.uuid4()
        conn = _mock_conn(insert_returns=nuevo_id)
        conn.fetch = AsyncMock(return_value=[{"id": admin1}, {"id": admin2}])
        r = _mock_redis(rr_idx=1)  # idx 0 → admin1

        with patch("master_worker_outlook.generar_borrador_para_caso", new=AsyncMock()):
            await procesar_atencion_cliente(
                conn, r, _em(), TENANT_FF, _buzon(),
                datetime(2026, 5, 27, tzinfo=timezone.utc), "OUTLOOK",
            )

        # Query de agentes incluye rol='admin'
        fetch_sql = conn.fetch.call_args.args[0]
        assert "'admin'" in fetch_sql
        assert "'analista'" in fetch_sql
        assert "'abogado'" in fetch_sql

        # Round-robin key específico de AC (separado del de PQRS)
        r.incr.assert_called_once_with(f"rr_ac:{TENANT_FF}")

        # asignado_a = admin1 (idx=0)
        insert_args = conn.fetchval.call_args.args[1:]
        # posición de asignado_a depende del orden — buscamos uuid de admin1
        assert admin1 in insert_args

    @pytest.mark.asyncio
    async def test_genera_borrador_con_tipo_workflow_atencion_cliente(self):
        nuevo_id = uuid.uuid4()
        conn = _mock_conn(insert_returns=nuevo_id)
        r = _mock_redis()
        em = _em(subject="Adjunto comprobante", body="Para que actualicen")

        with patch("master_worker_outlook.generar_borrador_para_caso", new=AsyncMock()) as mock_borr:
            await procesar_atencion_cliente(
                conn, r, em, TENANT_FF, _buzon(),
                datetime(2026, 5, 27, tzinfo=timezone.utc), "OUTLOOK",
            )

        kwargs = mock_borr.call_args.kwargs
        assert kwargs["tipo_workflow"] == "ATENCION_CLIENTE"
        assert kwargs["tipo_caso"] is None
        assert kwargs["email_origen"] == "test@x.com"

    @pytest.mark.asyncio
    async def test_borrador_falla_no_propaga(self):
        """Si generar_borrador_para_caso lanza, el flow sigue (no rompe worker)."""
        nuevo_id = uuid.uuid4()
        conn = _mock_conn(insert_returns=nuevo_id)
        r = _mock_redis()
        em = _em()

        with patch("master_worker_outlook.generar_borrador_para_caso",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            db_id = await procesar_atencion_cliente(
                conn, r, em, TENANT_FF, _buzon(),
                datetime(2026, 5, 27, tzinfo=timezone.utc), "OUTLOOK",
            )

        # Igual completó: db_id devuelto, SSE publicado, mark_as_read llamado
        assert db_id == nuevo_id
        r.publish.assert_called_once()
        em["prov_obj"].mark_as_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_as_read_outlook_vs_zoho(self):
        nuevo_id = uuid.uuid4()
        conn = _mock_conn(insert_returns=nuevo_id)
        r = _mock_redis()
        em = _em(msg_id="msg-zoho")

        with patch("master_worker_outlook.generar_borrador_para_caso", new=AsyncMock()):
            await procesar_atencion_cliente(
                conn, r, em, TENANT_FF, _buzon(),
                datetime(2026, 5, 27, tzinfo=timezone.utc), "ZOHO",
            )

        # ZOHO: mark_as_read(msg_id) — 1 argumento
        em["prov_obj"].mark_as_read.assert_called_once_with("msg-zoho")
