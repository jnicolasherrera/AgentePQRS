"""Tests del extractor multi-formato (sprint FF F1 adjuntos)."""

from __future__ import annotations

import io
import zipfile

import pytest

from unittest.mock import MagicMock, patch

from app.services.document_reader import (
    MAX_CHARS_POR_ADJUNTO,
    extract_from_adjuntos,
    extract_text,
    _detectar_formato,
    _extract_with_vision,
    _image_media_type,
)


# ──────────────────────────────────────────────────────────────────────────
# Generadores de docs sintéticos (sin dependencias adicionales)
# ──────────────────────────────────────────────────────────────────────────

def _make_pdf_simple(texto: str) -> bytes:
    """PDF text-based mínimo (1 página)."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for linea in texto.split("\n"):
        c.drawString(50, y, linea[:80])
        y -= 20
        if y < 50:
            c.showPage()
            y = 800
    c.save()
    return buf.getvalue()


def _make_docx_simple(parrafos: list[str]) -> bytes:
    import docx as _docx
    d = _docx.Document()
    for p in parrafos:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _make_xlsx_simple(rows: list[list]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────
# Detector de formato
# ──────────────────────────────────────────────────────────────────────────

class TestDetectarFormato:
    @pytest.mark.parametrize("filename,ct,expected", [
        ("doc.pdf", "", "pdf"),
        ("DOC.PDF", "", "pdf"),
        ("x", "application/pdf", "pdf"),
        ("contrato.docx", "", "docx"),
        ("data.xlsx", "", "xlsx"),
        ("notas.txt", "", "text"),
        ("export.csv", "", "text"),
        ("page.html", "", "text"),
        ("notes.md", "", "text"),
        ("x", "text/plain", "text"),
        # F2: imágenes y PDFs escaneados ahora van por visión
        ("foto.jpg", "image/jpeg", "image"),
        ("escaneo.PNG", "", "image"),
        ("foto.webp", "", "image"),
        ("x", "image/png", "image"),
        ("doc.doc", "", "unsupported"),  # .doc legacy aún no soportado
        ("scan.tiff", "image/tiff", "unsupported"),  # TIFF no es image/* soportado por Anthropic
    ])
    def test_detecta(self, filename, ct, expected):
        assert _detectar_formato(filename, ct) == expected


# ──────────────────────────────────────────────────────────────────────────
# Extractores
# ──────────────────────────────────────────────────────────────────────────

class TestExtractPDF:
    def test_pdf_con_texto(self):
        # enable_vision=False: testeamos pdfplumber puro (sin caer a Claude)
        pdf = _make_pdf_simple(
            "PROCESO 2026-001\nJuzgado 5 Civil\nTutela contra FlexFintech\n"
            + "Texto adicional para superar el umbral de 100 chars del fallback vision.\n"
            * 3
        )
        text = extract_text(pdf, "tutela.pdf", enable_vision=False)
        assert "PROCESO 2026-001" in text
        assert "Juzgado 5" in text
        assert "FlexFintech" in text

    def test_pdf_corrupto_devuelve_vacio(self):
        assert extract_text(b"no es un pdf", "x.pdf", enable_vision=False) == ""

    def test_pdf_vacio_devuelve_vacio(self):
        assert extract_text(b"", "x.pdf", enable_vision=False) == ""


class TestExtractDOCX:
    def test_docx_con_parrafos(self):
        docx = _make_docx_simple([
            "Notificación judicial",
            "Estimados señores FlexFintech S.A.S.",
            "Por medio de la presente solicito...",
        ])
        text = extract_text(docx, "carta.docx")
        assert "Notificación judicial" in text
        assert "FlexFintech S.A.S." in text
        assert "solicito" in text

    def test_docx_corrupto_devuelve_vacio(self):
        assert extract_text(b"no docx", "x.docx") == ""


class TestExtractXLSX:
    def test_xlsx_lee_celdas(self):
        xlsx = _make_xlsx_simple([
            ["Cliente", "Cédula", "Saldo"],
            ["Juan Perez", "1007403296", 1500000],
            ["María Gomez", "98765432", 250000],
        ])
        text = extract_text(xlsx, "datos.xlsx")
        assert "Cliente" in text
        assert "Juan Perez" in text
        assert "1007403296" in text


class TestExtractTextPlain:
    def test_utf8(self):
        text = "Solicitud paz y salvo — número 1.007.403.296"
        assert extract_text(text.encode("utf-8"), "nota.txt") == text

    def test_latin1_fallback(self):
        text = "señor con acentúación"
        assert text in extract_text(text.encode("latin-1"), "nota.txt")

    def test_csv_extension(self):
        text = "a,b,c\n1,2,3"
        assert extract_text(text.encode(), "data.csv") == text


# ──────────────────────────────────────────────────────────────────────────
# Truncado
# ──────────────────────────────────────────────────────────────────────────

class TestTruncado:
    def test_max_chars_default(self):
        # Texto plano con tamaño predecible (PDF generado no garantiza
        # extraer todos los chars, depende de fuente/layout).
        large = ("lorem ipsum dolor sit amet " * 500).encode()  # ~13K chars
        text = extract_text(large, "x.txt")
        assert len(text) <= MAX_CHARS_POR_ADJUNTO + 30
        assert "[...truncado]" in text

    def test_max_chars_custom(self):
        text = extract_text(b"hello world " * 100, "x.txt", max_chars=50)
        assert len(text) <= 50 + 30


# ──────────────────────────────────────────────────────────────────────────
# extract_from_adjuntos (API principal)
# ──────────────────────────────────────────────────────────────────────────

class TestExtractFromAdjuntos:
    def test_vacio(self):
        assert extract_from_adjuntos([]) == ""

    def test_un_adjunto_pdf(self):
        # PDF con texto suficiente para que NO caiga a vision
        adj = [{
            "nombre_archivo": "tutela.pdf",
            "content_bytes": _make_pdf_simple(
                "ACCION DE TUTELA PROCESO 555\n" * 10
            ),
            "content_type": "application/pdf",
        }]
        # extract_from_adjuntos llama extract_text con default enable_vision=True,
        # pero como el texto extraído va a ser > 100 chars, no cae a vision.
        bloque = extract_from_adjuntos(adj)
        assert "--- ADJUNTO 1: tutela.pdf ---" in bloque
        assert "ACCION DE TUTELA" in bloque or "ACCIÓN DE TUTELA" in bloque

    def test_multiples_formatos(self):
        adj = [
            {"nombre_archivo": "carta.docx",
             "content_bytes": _make_docx_simple(["Saludo cordial", "Adjunto comprobante"])},
            {"nombre_archivo": "nota.txt",
             "content_bytes": b"texto plano simple"},
        ]
        bloque = extract_from_adjuntos(adj)
        assert "ADJUNTO 1: carta.docx" in bloque
        assert "Saludo cordial" in bloque
        assert "ADJUNTO 2: nota.txt" in bloque
        assert "texto plano simple" in bloque

    def test_skip_imagenes(self):
        """Imágenes en F1 → string vacío, no se agregan al bloque."""
        adj = [
            {"nombre_archivo": "foto.jpg", "content_bytes": b"\xff\xd8\xff\xe0fake",
             "content_type": "image/jpeg"},
            {"nombre_archivo": "ok.txt", "content_bytes": b"texto"},
        ]
        bloque = extract_from_adjuntos(adj)
        assert "foto.jpg" not in bloque  # skip
        assert "ok.txt" in bloque

    def test_limita_a_max_adjuntos(self):
        adj = [
            {"nombre_archivo": f"a{i}.txt", "content_bytes": f"text {i}".encode()}
            for i in range(10)
        ]
        bloque = extract_from_adjuntos(adj, max_adjuntos=3)
        assert "a0.txt" in bloque
        assert "a2.txt" in bloque
        assert "a3.txt" not in bloque  # cortado

    def test_limita_chars_total(self):
        adj = [
            {"nombre_archivo": "a.txt", "content_bytes": ("x" * 5000).encode()},
            {"nombre_archivo": "b.txt", "content_bytes": ("y" * 5000).encode()},
        ]
        bloque = extract_from_adjuntos(adj, max_chars_total=3000)
        # No debería pasar mucho de 3000 (más algunos chars de markers)
        assert len(bloque) <= 4500


# ──────────────────────────────────────────────────────────────────────────
# F2 — Claude visión (mockean Anthropic)
# ──────────────────────────────────────────────────────────────────────────

def _mock_anthropic_response(text: str):
    """Construye un mock de anthropic.Anthropic().messages.create()."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    client = MagicMock()
    client.messages.create = MagicMock(return_value=resp)
    return client


class TestImageMediaType:
    @pytest.mark.parametrize("filename,ct,expected", [
        ("x.jpg", "", "image/jpeg"),
        ("x.JPEG", "", "image/jpeg"),
        ("x.png", "", "image/png"),
        ("x.gif", "", "image/gif"),
        ("x.webp", "", "image/webp"),
        ("x", "image/png", "image/png"),
        ("x.tiff", "image/tiff", "image/jpeg"),  # tiff no soportado → fallback
        ("desconocido", "", "image/jpeg"),       # fallback default
    ])
    def test_media_type(self, filename, ct, expected):
        assert _image_media_type(filename, ct) == expected


class TestVisionExtract:
    def test_imagen_jpg_llama_visión(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        fake_client = _mock_anthropic_response(
            "Cédula: 1007403296\nNombre: Juan Pérez"
        )
        with patch("anthropic.Anthropic", return_value=fake_client):
            txt = extract_text(b"\xff\xd8\xff\xe0fakejpegcontent",
                               "cedula.jpg", "image/jpeg")
        assert "1007403296" in txt
        assert "Juan Pérez" in txt
        # Verifica que se llamó con el bloque image
        call_kwargs = fake_client.messages.create.call_args.kwargs
        content_blocks = call_kwargs["messages"][0]["content"]
        assert content_blocks[0]["type"] == "image"
        assert content_blocks[0]["source"]["media_type"] == "image/jpeg"

    def test_pdf_escaneado_cae_a_vision(self, monkeypatch):
        """PDF sin texto extraíble → cae a Claude visión."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        fake_client = _mock_anthropic_response(
            "JUZGADO 5 CIVIL\nPROCESO 2026-001"
        )
        # PDF "vacío" (sin texto extraíble por pdfplumber)
        with patch("anthropic.Anthropic", return_value=fake_client):
            with patch("app.services.document_reader._extract_pdf", return_value=""):
                txt = extract_text(b"%PDF-fake", "scan.pdf", "application/pdf")
        assert "JUZGADO 5" in txt
        # Verifica bloque document (PDF)
        content_blocks = fake_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert content_blocks[0]["type"] == "document"
        assert content_blocks[0]["source"]["media_type"] == "application/pdf"

    def test_pdf_con_texto_NO_llama_vision(self, monkeypatch):
        """PDF text-based con texto suficiente → NO llama vision (ahorra costo)."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        fake_client = _mock_anthropic_response("from_vision")
        # Mock que _extract_pdf devuelve texto suficiente
        with patch("anthropic.Anthropic", return_value=fake_client):
            with patch("app.services.document_reader._extract_pdf",
                       return_value="Texto extraído del PDF " * 20):
                txt = extract_text(b"%PDF", "doc.pdf", "application/pdf")
        assert "Texto extraído" in txt
        assert "from_vision" not in txt
        fake_client.messages.create.assert_not_called()

    def test_vision_disabled_skipea_imagen(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        fake_client = _mock_anthropic_response("x")
        with patch("anthropic.Anthropic", return_value=fake_client):
            txt = extract_text(b"\xff\xd8fake", "foto.jpg", "image/jpeg",
                               enable_vision=False)
        assert txt == ""
        fake_client.messages.create.assert_not_called()

    def test_sin_api_key_devuelve_vacio(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        txt = _extract_with_vision(b"fake", "x.jpg", "image/jpeg", es_pdf=False)
        assert txt == ""

    def test_archivo_muy_grande_skipea(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        big = b"x" * (6 * 1024 * 1024)  # 6 MB > 5 MB limit
        fake_client = _mock_anthropic_response("x")
        with patch("anthropic.Anthropic", return_value=fake_client):
            txt = _extract_with_vision(big, "big.jpg", "image/jpeg", es_pdf=False)
        assert txt == ""
        fake_client.messages.create.assert_not_called()

    def test_anthropic_falla_devuelve_vacio(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        fake_client = MagicMock()
        fake_client.messages.create = MagicMock(side_effect=RuntimeError("API down"))
        with patch("anthropic.Anthropic", return_value=fake_client):
            txt = _extract_with_vision(b"fake", "x.jpg", "image/jpeg", es_pdf=False)
        assert txt == ""  # log warn + sigue
