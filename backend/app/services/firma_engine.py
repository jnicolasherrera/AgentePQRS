"""Firma de correo por tenant.

Sprint firma-por-tenant 2026-06-25.
Antes la firma era una imagen única global (`static/firma_correo.jpeg`, firma de
Abogados Recovery / ARC Sas) aplicada a TODOS los envíos → los correos de
FlexFintech salían con la firma de Recovery, lo cual es incorrecto.

Ahora la firma se resuelve por tenant:
- **FlexFintech** (`f7e8d9c0-...`): firma de TEXTO, sin imagen.
- **Resto** (Recovery/ARC, etc.): la imagen institucional actual (sin cambios).

La firma puede entregarse de dos maneras según el canal de envío:
- `firma_html_cid()`  → referencia `cid:firma_arc` (para MIME inline / Graph attachment).
- `firma_html_datauri()` → imagen embebida como data: URI (para Zoho API).
Ambas devuelven solo el bloque de firma (texto plano para FF, imagen para el resto).
"""

import base64
import os
from typing import Optional

_FIRMA_CID = "firma_arc"
TENANT_FLEXFINTECH = "f7e8d9c0-b1a2-3456-7890-123456abcdef"

# Firma de texto para FlexFintech (sin imagen).
_FIRMA_TEXTO_FLEXFINTECH = (
    "<br><br>"
    "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.4'>"
    "Saludos Cordiales<br>"
    "<strong>Flexfintech</strong>"
    "</div>"
)


def _firma_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "static", "firma_correo.jpeg")


def firma_bytes() -> Optional[bytes]:
    """Bytes de la imagen de firma institucional (Recovery/ARC). None si no existe."""
    try:
        with open(_firma_path(), "rb") as f:
            return f.read()
    except Exception:
        return None


def _es_flexfintech(email_buzon: Optional[str], tenant_id: Optional[str]) -> bool:
    if tenant_id and str(tenant_id).lower() == TENANT_FLEXFINTECH:
        return True
    if email_buzon and "flexfintech.com" in email_buzon.lower():
        return True
    return False


def usa_imagen(email_buzon: Optional[str] = None, tenant_id: Optional[str] = None) -> bool:
    """True si este tenant firma con imagen (Recovery/ARC). False para FlexFintech (texto)."""
    if _es_flexfintech(email_buzon, tenant_id):
        return False
    return firma_bytes() is not None


def firma_html_cid(email_buzon: Optional[str] = None, tenant_id: Optional[str] = None) -> str:
    """Bloque de firma para MIME inline / Graph (imagen referenciada por CID).

    FlexFintech → firma de texto. Resto → <img src="cid:firma_arc">.
    """
    if _es_flexfintech(email_buzon, tenant_id):
        return _FIRMA_TEXTO_FLEXFINTECH
    if firma_bytes() is None:
        return ""
    return f'<br><img src="cid:{_FIRMA_CID}" style="max-width:560px;display:block;" alt="Firma" />'


def firma_html_datauri(email_buzon: Optional[str] = None, tenant_id: Optional[str] = None) -> str:
    """Bloque de firma con imagen embebida como data: URI (para Zoho API).

    FlexFintech → firma de texto. Resto → imagen base64 inline.
    """
    if _es_flexfintech(email_buzon, tenant_id):
        return _FIRMA_TEXTO_FLEXFINTECH
    data = firma_bytes()
    if data is None:
        return ""
    b64 = base64.b64encode(data).decode()
    return f'<br><img src="data:image/jpeg;base64,{b64}" style="max-width:560px;display:block;" alt="Firma" />'
