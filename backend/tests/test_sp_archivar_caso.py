"""Tests del archivado SharePoint post-envío (sprint FlexFintech 2026-05-27, bloque 6).

Mockean requests.put + msal token. No tocan Graph API real.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sharepoint_engine import SharePointEngineV2


def _engine_con_token():
    e = SharePointEngineV2(
        client_id="cid", client_secret="cs", tenant_id="tid",
        site_id="site1", base_folder="01. RECOVERY/01. DOC",
    )
    # Saltar la auth real
    e._access_token = "fake-token"
    e._token_expiry = datetime(2099, 1, 1)
    e._drive_id = "drive1"
    return e


# --------------------------------------------------------------------------- #
# archivar_caso
# --------------------------------------------------------------------------- #

class TestArchivarCaso:
    @pytest.mark.asyncio
    async def test_cedula_vacia_devuelve_none_sin_uploads(self):
        e = _engine_con_token()
        with patch("requests.put") as mock_put:
            res = await e.archivar_caso(
                cedula="", fecha=datetime(2026, 5, 27),
                mail_original_html=b"<html></html>",
                respuesta_html=b"<html></html>",
            )
        assert res is None
        mock_put.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_3_archivos(self):
        e = _engine_con_token()
        resp_ok = MagicMock(status_code=201)
        with patch("requests.put", return_value=resp_ok) as mock_put:
            res = await e.archivar_caso(
                cedula="1007403296",
                fecha=datetime(2026, 5, 27, 14, 30),
                mail_original_html=b"<html>mail</html>",
                respuesta_html=b"<html>resp</html>",
                adjuntos=[{"nombre_archivo": "doc.pdf",
                           "content_bytes": b"%PDF-1.7",
                           "content_type": "application/pdf"}],
            )

        assert res == "01. RECOVERY/01. DOC/1007403296_2026-05-27"
        assert mock_put.call_count == 3  # mail + respuesta + 1 adjunto

        # Verificar paths
        urls = [c.args[0] for c in mock_put.call_args_list]
        assert any("1007403296_2026-05-27/mail_original.html" in u for u in urls)
        assert any("1007403296_2026-05-27/respuesta.html" in u for u in urls)
        assert any("1007403296_2026-05-27/doc.pdf" in u for u in urls)

    @pytest.mark.asyncio
    async def test_adjunto_vacio_skipea(self):
        e = _engine_con_token()
        resp_ok = MagicMock(status_code=201)
        with patch("requests.put", return_value=resp_ok) as mock_put:
            await e.archivar_caso(
                cedula="999",
                fecha=datetime(2026, 5, 27),
                mail_original_html=b"m",
                respuesta_html=b"r",
                adjuntos=[
                    {"nombre_archivo": "vacio.pdf", "content_bytes": b"", "content_type": "x"},
                    {"nombre_archivo": "ok.pdf", "content_bytes": b"data", "content_type": "x"},
                ],
            )
        # mail + respuesta + 1 adjunto válido (el vacío skipea)
        assert mock_put.call_count == 3

    @pytest.mark.asyncio
    async def test_put_falla_no_propaga(self):
        """Si una PUT falla, archivar_caso sigue (best-effort)."""
        e = _engine_con_token()
        resp_fail = MagicMock(status_code=500, text="server error")
        with patch("requests.put", return_value=resp_fail):
            # No debe levantar excepción
            res = await e.archivar_caso(
                cedula="999",
                fecha=datetime(2026, 5, 27),
                mail_original_html=b"m",
                respuesta_html=b"r",
            )
        # Igual devuelve la carpeta esperada (best-effort)
        assert res == "01. RECOVERY/01. DOC/999_2026-05-27"

    @pytest.mark.asyncio
    async def test_fecha_como_string(self):
        """Soporta fecha como string ISO."""
        e = _engine_con_token()
        resp_ok = MagicMock(status_code=201)
        with patch("requests.put", return_value=resp_ok) as mock_put:
            res = await e.archivar_caso(
                cedula="500",
                fecha="2026-05-27T10:00:00",
                mail_original_html=b"m",
                respuesta_html=b"r",
            )
        assert res == "01. RECOVERY/01. DOC/500_2026-05-27"

    @pytest.mark.asyncio
    async def test_content_type_correcto_en_uploads(self):
        e = _engine_con_token()
        resp_ok = MagicMock(status_code=201)
        with patch("requests.put", return_value=resp_ok) as mock_put:
            await e.archivar_caso(
                cedula="1",
                fecha=datetime(2026, 5, 27),
                mail_original_html=b"<html>",
                respuesta_html=b"<html>",
                adjuntos=[{"nombre_archivo": "x.pdf",
                           "content_bytes": b"d",
                           "content_type": "application/pdf"}],
            )
        # 3 calls; verificar content-type de cada uno
        cts = [c.kwargs["headers"]["Content-Type"] for c in mock_put.call_args_list]
        assert cts[0] == "text/html; charset=utf-8"  # mail
        assert cts[1] == "text/html; charset=utf-8"  # respuesta
        assert cts[2] == "application/pdf"            # adjunto

    @pytest.mark.asyncio
    async def test_path_encoding_espacios(self):
        """Los espacios del base_folder se URL-encodean correctamente."""
        e = _engine_con_token()  # base_folder tiene espacios
        resp_ok = MagicMock(status_code=201)
        with patch("requests.put", return_value=resp_ok) as mock_put:
            await e.archivar_caso(
                cedula="42",
                fecha=datetime(2026, 5, 27),
                mail_original_html=b"m",
                respuesta_html=b"r",
            )
        url0 = mock_put.call_args_list[0].args[0]
        # No deben quedar espacios literales en la URL
        assert " " not in url0
        # Debe contener el cedula_fecha encoded
        assert "42_2026-05-27" in url0
