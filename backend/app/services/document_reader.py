"""
Extractor multi-formato para adjuntos de emails entrantes.

Sprint FF 2026-05-27 — F1: lectura de texto extraíble (sin OCR / visión).

Función pública: `extract_text(content_bytes, filename, content_type) -> str`.
Devuelve el texto del adjunto (truncado a MAX_CHARS_POR_ADJUNTO) o "" si
no se puede leer (formato no soportado / PDF escaneado / error).

Soportados en F1:
- PDF con texto (pdfplumber)
- DOCX (python-docx)
- XLSX (openpyxl)
- TXT / CSV / HTML / Markdown / JSON (decode UTF-8 con fallback latin-1)

NO soportados aún (F2 — Claude visión):
- PDF escaneado (sin texto extraíble)
- Imágenes JPG / PNG / TIFF / etc.

Filosofía: best-effort + log warn ante cualquier falla. NUNCA debe
romper el flow de generación de borrador.
"""

from __future__ import annotations

import io
import logging
from typing import Iterable

logger = logging.getLogger(__name__)

# Límites duros para evitar prompts gigantes
MAX_CHARS_POR_ADJUNTO = 3000
MAX_CHARS_TOTAL = 8000
MAX_ADJUNTOS = 5


# ──────────────────────────────────────────────────────────────────────────
# Extractores por formato
# ──────────────────────────────────────────────────────────────────────────

def _extract_pdf(content: bytes) -> str:
    """PDF con texto. PDFs escaneados → string vacío (F2 con visión)."""
    try:
        import pdfplumber
        out: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:20]:  # cap 20 páginas
                txt = page.extract_text() or ""
                if txt.strip():
                    out.append(txt)
        result = "\n\n".join(out).strip()
        return result
    except Exception as e:
        logger.warning("PDF extract falló: %s", e)
        return ""


def _extract_docx(content: bytes) -> str:
    """Microsoft Word (.docx)."""
    try:
        import docx as _docx
        d = _docx.Document(io.BytesIO(content))
        partes: list[str] = []
        # Párrafos
        for p in d.paragraphs:
            if p.text.strip():
                partes.append(p.text)
        # Tablas (case típico: tutela con datos en tabla)
        for tabla in d.tables:
            for row in tabla.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    partes.append(" | ".join(cells))
        return "\n".join(partes).strip()
    except Exception as e:
        logger.warning("DOCX extract falló: %s", e)
        return ""


def _extract_xlsx(content: bytes) -> str:
    """Excel (.xlsx). Solo primera hoja, primeras 200 filas."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        ws = wb.active
        partes: list[str] = [f"Hoja: {ws.title}"]
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 200:
                break
            cells = [str(v) for v in row if v is not None]
            if cells:
                partes.append(" | ".join(cells))
        return "\n".join(partes).strip()
    except Exception as e:
        logger.warning("XLSX extract falló: %s", e)
        return ""


def _extract_text_plain(content: bytes) -> str:
    """TXT / CSV / HTML / MD / JSON — best-effort decode."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    logger.warning("text plain: no decodificable")
    return ""


# ──────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────

def _detectar_formato(filename: str, content_type: str) -> str:
    """Devuelve 'pdf' | 'docx' | 'xlsx' | 'text' | 'unsupported'."""
    fn = (filename or "").lower()
    ct = (content_type or "").lower()

    if fn.endswith(".pdf") or "pdf" in ct:
        return "pdf"
    if fn.endswith(".docx") or "wordprocessingml" in ct:
        return "docx"
    if fn.endswith(".xlsx") or "spreadsheetml" in ct:
        return "xlsx"
    if any(fn.endswith(ext) for ext in (".txt", ".csv", ".html", ".htm",
                                          ".md", ".json", ".log", ".xml")):
        return "text"
    if ct.startswith("text/"):
        return "text"
    # Imágenes y .doc legacy → no soportado en F1
    return "unsupported"


def extract_text(
    content: bytes,
    filename: str = "",
    content_type: str = "",
    max_chars: int = MAX_CHARS_POR_ADJUNTO,
) -> str:
    """Extrae texto de un adjunto. Devuelve "" si no se puede leer.

    NUNCA levanta excepciones — best-effort con log warn ante errores.
    """
    if not content:
        return ""

    fmt = _detectar_formato(filename, content_type)
    if fmt == "pdf":
        text = _extract_pdf(content)
    elif fmt == "docx":
        text = _extract_docx(content)
    elif fmt == "xlsx":
        text = _extract_xlsx(content)
    elif fmt == "text":
        text = _extract_text_plain(content)
    else:
        logger.info("formato no soportado en F1: %s / %s", filename, content_type)
        return ""

    # Truncar y limpiar
    text = (text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars] + " [...truncado]"
    return text


def extract_from_adjuntos(
    adjuntos: Iterable[dict],
    max_adjuntos: int = MAX_ADJUNTOS,
    max_chars_total: int = MAX_CHARS_TOTAL,
) -> str:
    """Procesa una lista de adjuntos y devuelve un bloque de texto listo
    para inyectar al user_prompt de Claude.

    Cada adjunto debe ser un dict con:
      - nombre / nombre_archivo: str
      - content / content_bytes: bytes
      - content_type: str (opcional)

    Devuelve string vacío si ninguno tiene texto extraíble.

    Formato del output:
    --- ADJUNTO 1: nombre.pdf ---
    <texto extraído>

    --- ADJUNTO 2: doc.docx ---
    <texto extraído>
    """
    if not adjuntos:
        return ""

    bloques: list[str] = []
    chars_total = 0

    for i, adj in enumerate(adjuntos):
        if i >= max_adjuntos:
            bloques.append(f"--- {len(list(adjuntos)) - max_adjuntos} adjuntos adicionales omitidos ---")
            break

        nombre = (adj.get("nombre") or adj.get("nombre_archivo") or f"adjunto_{i+1}").strip()
        content = adj.get("content") or adj.get("content_bytes") or b""
        ctype = adj.get("content_type") or ""

        if not content:
            continue

        chars_restantes = max(0, max_chars_total - chars_total)
        if chars_restantes < 200:  # no vale la pena
            break

        texto = extract_text(
            content, nombre, ctype,
            max_chars=min(MAX_CHARS_POR_ADJUNTO, chars_restantes),
        )
        if not texto:
            continue

        bloques.append(f"--- ADJUNTO {i+1}: {nombre} ---\n{texto}")
        chars_total += len(texto)

    return "\n\n".join(bloques)
