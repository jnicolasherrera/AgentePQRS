"""Utilidades compartidas para generación de emails.

Centralizado en Fase 2 (2026-05-21) para evitar duplicación: `_md_to_html`
estaba copiado idéntico en `zoho_engine.py` y `api/routes/casos.py`.
(Las funciones de firma NO se unifican: difieren por diseño — base64 inline
en Zoho vs CID en el fallback SMTP.)
"""
import re


def md_to_html(text: str) -> str:
    """Convierte markdown básico (bold, italic, headers) a HTML."""
    # Headers ## → <h3>, # → <h2>
    text = re.sub(r'^### (.+)$', r'<h4 style="margin:12px 0 4px">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$',  r'<h3 style="margin:14px 0 6px">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$',   r'<h2 style="margin:16px 0 8px">\1</h2>', text, flags=re.MULTILINE)
    # Bold **texto** y __texto__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', text)
    # Italic *texto* y _texto_ (no captura los que ya son bold)
    text = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_\n]+?)_',   r'<em>\1</em>', text)
    # Saltos de línea → <br>
    text = text.replace("\n", "<br>")
    return text
