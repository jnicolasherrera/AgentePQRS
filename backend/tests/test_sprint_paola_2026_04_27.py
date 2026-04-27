"""
Tests del sprint Paola 2026-04-27 — 4 fixes producción ARC.

Cobertura:
- P1: upload límite 25 MB.
- P2: PUT /borrador skipea audit cuando texto idéntico.
- P3: SMTP fallback genera MIME multipart/related con firma inline (CID).
- P4: generar_borrador_con_ia retorna texto sin AVISO_GENERICA.

Mocks: asyncpg.Connection, smtplib.SMTP_SSL, anthropic.AsyncAnthropic.
Sin DB real, sin red. Stubbea app.services.storage_engine antes de cualquier
import de routes (DT-29: el módulo conecta a MinIO en import time).
"""
from __future__ import annotations

import sys
import uuid
from email import message_from_string
from unittest.mock import AsyncMock, MagicMock, patch

# Stub storage_engine ANTES de importar casos.py (DT-29).
_storage_stub = MagicMock()
_storage_stub.upload_file = AsyncMock(return_value="reply/stub/file.pdf")
_storage_stub.download_file = MagicMock(return_value=b"")
_storage_stub.get_download_url = MagicMock(return_value="https://stub")
_storage_stub.client = MagicMock()
_storage_stub.BUCKET_NAME = "stub"
sys.modules["app.services.storage_engine"] = _storage_stub

import pytest
from fastapi import HTTPException


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")
USUARIO = uuid.UUID("11111111-1111-1111-1111-111111111111")
CASO = uuid.UUID("22222222-2222-2222-2222-222222222222")


# ─────────────────────────────────────────────────────────────────────────────
# P1 — Upload límite 25 MB
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p1_upload_24mb_passes_size_check():
    """Archivo de 24 MB pasa el check de tamaño y llega al INSERT."""
    from app.api.routes.casos import upload_reply_adjunto

    fake_file = MagicMock()
    fake_file.read = AsyncMock(return_value=b"x" * (24 * 1024 * 1024))
    fake_file.filename = "respuesta.pdf"
    fake_file.content_type = "application/pdf"

    fake_user = MagicMock(usuario_id=str(USUARIO), tenant_uuid=str(TENANT))
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"id": CASO, "cliente_id": TENANT})
    fake_conn.execute = AsyncMock()

    result = await upload_reply_adjunto(
        caso_id=str(CASO), file=fake_file,
        current_user=fake_user, conn=fake_conn,
    )

    assert result["nombre"] == "respuesta.pdf"
    assert result["tamano"] == 24 * 1024 * 1024
    fake_conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_p1_upload_26mb_rejects_with_400():
    """Archivo de 26 MB es rechazado con HTTP 400 antes del INSERT."""
    from app.api.routes.casos import upload_reply_adjunto

    fake_file = MagicMock()
    fake_file.read = AsyncMock(return_value=b"x" * (26 * 1024 * 1024))
    fake_file.filename = "demasiado.pdf"
    fake_file.content_type = "application/pdf"

    fake_user = MagicMock(usuario_id=str(USUARIO), tenant_uuid=str(TENANT))
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"id": CASO, "cliente_id": TENANT})

    with pytest.raises(HTTPException) as exc:
        await upload_reply_adjunto(
            caso_id=str(CASO), file=fake_file,
            current_user=fake_user, conn=fake_conn,
        )

    assert exc.value.status_code == 400
    assert "25" in exc.value.detail


# ─────────────────────────────────────────────────────────────────────────────
# P2 — PUT /borrador skipea audit cuando texto unchanged
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_put_borrador_unchanged_skips_audit():
    """Si el texto nuevo == texto actual, NO se inserta en audit_log_respuestas."""
    from app.api.routes.casos import editar_borrador, BorradorUpdateRequest

    texto_actual = "Borrador original sin cambios."
    fake_user = MagicMock(usuario_id=str(USUARIO))
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={
        "id": CASO, "cliente_id": TENANT, "tipo_caso": "PETICION",
        "borrador_respuesta": texto_actual,
    })
    fake_conn.execute = AsyncMock()

    body = BorradorUpdateRequest(texto=texto_actual)
    result = await editar_borrador(
        caso_id=str(CASO), body=body,
        current_user=fake_user, conn=fake_conn,
    )

    assert result == {"ok": True, "unchanged": True}
    fake_conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_p2_put_borrador_changed_inserts_audit():
    """Si el texto nuevo != texto actual, sí se hace UPDATE + audit + feedback."""
    from app.api.routes.casos import editar_borrador, BorradorUpdateRequest

    fake_user = MagicMock(usuario_id=str(USUARIO))
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={
        "id": CASO, "cliente_id": TENANT, "tipo_caso": "PETICION",
        "borrador_respuesta": "Borrador original.",
    })
    fake_conn.execute = AsyncMock()

    body = BorradorUpdateRequest(texto="Borrador editado por abogado.")
    result = await editar_borrador(
        caso_id=str(CASO), body=body,
        current_user=fake_user, conn=fake_conn,
    )

    assert result == {"ok": True}
    queries = [str(call.args[0]) for call in fake_conn.execute.await_args_list]
    assert any("UPDATE pqrs_casos" in q for q in queries), "falta el UPDATE"
    assert any("audit_log_respuestas" in q and "BORRADOR_EDITADO" in q for q in queries), "falta audit"
    assert any("borrador_feedback" in q for q in queries), "falta feedback"


# ─────────────────────────────────────────────────────────────────────────────
# P3 — SMTP fallback con CID multipart/related
# ─────────────────────────────────────────────────────────────────────────────

def test_p3_smtp_fallback_genera_multipart_related_con_cid(monkeypatch):
    """SMTP fallback genera MIME multipart/related con firma como inline CID."""
    from app.api.routes.casos import _send_via_smtp_fallback, _firma_bytes, _FIRMA_CID

    if _firma_bytes() is None:
        pytest.skip("firma_correo.jpeg no disponible en este entorno")

    monkeypatch.setenv("SMTP_FALLBACK_USER", "test@flexpqr.dev")
    monkeypatch.setenv("SMTP_FALLBACK_PASS", "stub")

    captured = {}
    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, u, p): captured["login"] = (u, p)
        def sendmail(self, frm, to, msg_str):
            captured["msg"] = msg_str
            captured["from"] = frm
            captured["to"] = to

    with patch("app.api.routes.casos.smtplib.SMTP_SSL", FakeSMTP):
        ok = _send_via_smtp_fallback("dest@example.com", "Asunto", "Cuerpo de prueba")

    assert ok is True
    raw = captured["msg"]
    msg = message_from_string(raw)
    assert msg.get_content_type() == "multipart/related"

    parts = list(msg.walk())
    cids = [p.get("Content-ID", "") for p in parts if p.get_content_type().startswith("image/")]
    assert any(_FIRMA_CID in cid for cid in cids), f"Content-ID con {_FIRMA_CID} no encontrado en {cids}"

    html_parts = [p for p in parts if p.get_content_type() == "text/html"]
    assert html_parts, "no hay parte text/html"
    html_payload = html_parts[0].get_payload(decode=True).decode("utf-8")
    assert f'cid:{_FIRMA_CID}' in html_payload, "HTML no referencia cid:firma_arc"


def test_p3_smtp_fallback_sin_firma_usa_alternative(monkeypatch, tmp_path):
    """Si firma_correo.jpeg no existe, fallback usa multipart/alternative (no related)."""
    from app.api.routes import casos as casos_module

    monkeypatch.setenv("SMTP_FALLBACK_USER", "test@flexpqr.dev")
    monkeypatch.setenv("SMTP_FALLBACK_PASS", "stub")
    monkeypatch.setattr(casos_module, "_firma_bytes", lambda: None)

    captured = {}
    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, u, p): pass
        def sendmail(self, frm, to, msg_str): captured["msg"] = msg_str

    with patch("app.api.routes.casos.smtplib.SMTP_SSL", FakeSMTP):
        ok = casos_module._send_via_smtp_fallback("d@x.com", "S", "B")

    assert ok is True
    msg = message_from_string(captured["msg"])
    assert msg.get_content_type() == "multipart/alternative"


# ─────────────────────────────────────────────────────────────────────────────
# P4 — generar_borrador_con_ia sin AVISO_GENERICA
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p4_borrador_ia_sin_aviso_generica(monkeypatch):
    """generar_borrador_con_ia retorna SOLO el texto de Claude, sin disclaimer."""
    from app.services import plantilla_engine

    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub-key")

    texto_claude = "Cordial saludo, su petición fue radicada bajo el número PQRS-2026-001."

    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=texto_claude)]
    fake_messages = MagicMock(create=AsyncMock(return_value=fake_resp))
    fake_client = MagicMock(messages=fake_messages)

    with patch("anthropic.AsyncAnthropic", return_value=fake_client):
        result = await plantilla_engine.generar_borrador_con_ia(
            asunto="Solicitud paz y salvo",
            cuerpo="Solicito certificado.",
            tipo_caso="PETICION",
            nombre_cliente="Juan Pérez",
        )

    assert result == texto_claude
    assert "inteligencia artificial" not in result.lower()
    assert "generada automáticamente" not in result.lower()
    assert plantilla_engine.AVISO_GENERICA not in result
