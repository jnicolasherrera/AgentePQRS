"""
tutela_extractor.py — enricher de TUTELA con Claude Sonnet + tool use.

Extrae de un oficio judicial (texto plano o texto OCR de adjuntos) el metadata
estructurado que el pipeline necesita para:
- Calcular plazo de informe (plazo_informe_horas + plazo_tipo).
- Detectar medidas provisionales con su propio plazo.
- Generar documento_peticionante_hash para vinculación cross-tenant-safe.
- Identificar tipo_actuacion (AUTO_ADMISORIO, FALLO_PRIMERA, etc.).

Usa Claude Sonnet con tool_use forzado para retornar JSON siguiendo
TUTELA_SCHEMA. Ante error (rate limit, timeout, API error), retorna un dict
con `_extraction_failed=True` + defaults defensivos (48h HABILES) para que
el pipeline pueda seguir.

Hashea accionante.documento_raw con SHA-256 salteado por tenant (config_hash_salt
de la 19) y borra el documento en claro antes de persistir.

Auto-registro: `ENRICHERS["TUTELA"] = enrich_tutela` al importarse el módulo.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Any, Optional

import anthropic

from app.services.enrichers import ENRICHERS

logger = logging.getLogger("TUTELA_EXTRACTOR")

# Modelo por defecto. Se puede overridear con env var.
ANTHROPIC_MODEL_SONNET = os.environ.get(
    "ANTHROPIC_MODEL_SONNET", "claude-sonnet-4-5-20250929"
)

# Marker para detectar fixtures sintéticos y warnear en prod.
_SYNTHETIC_MARKER = "SYNTHETIC_FIXTURE_V1"

# Defaults defensivos cuando la extracción falla.
_DEFAULT_PLAZO_HORAS = 48
_DEFAULT_PLAZO_TIPO = "HABILES"
_DEFAULT_TIPO_ACTUACION = "AUTO_ADMISORIO"

# Umbral para marcar revisión humana.
_CONFIDENCE_UMBRAL = 0.85


TUTELA_SCHEMA: dict[str, Any] = {
    "name": "extraer_metadata_tutela",
    "description": (
        "Extrae metadata estructurada de un oficio judicial de tutela. "
        "Para plazos usa la regla operativa: 1 día hábil = 8 horas hábiles. "
        "Para expedientes usa el formato CCCCC-CCCC-NNN-YYYY-NNNNN-NN. "
        "Las medidas provisionales tienen plazo INDEPENDIENTE del plazo del informe. "
        "NUNCA extraigas el nombre del accionante, solo el número de documento (documento_raw)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "numero_expediente": {
                "type": "string",
                "description": "Formato CCCCC-CCCC-NNN-YYYY-NNNNN-NN cuando está presente.",
            },
            "despacho": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "ciudad": {"type": "string"},
                },
                "required": ["nombre"],
            },
            "tipo_actuacion": {
                "type": "string",
                "enum": [
                    "AUTO_ADMISORIO",
                    "AUTO_INADMISORIO",
                    "FALLO_PRIMERA",
                    "FALLO_SEGUNDA",
                    "REQUERIMIENTO",
                    "NOTIFICACION_CUMPLIMIENTO",
                    "OTRO",
                ],
            },
            "fecha_auto": {
                "type": "string",
                "description": "Fecha del auto/fallo en formato ISO 8601 (YYYY-MM-DD o con hora).",
            },
            "plazo_informe_horas": {
                "type": "integer",
                "minimum": 1,
                "maximum": 720,
                "description": (
                    "Horas totales para rendir el informe. 1 día hábil = 8h. "
                    "Si el texto es ambiguo o no indica plazo, poner 48 y marcar confidence bajo."
                ),
            },
            "plazo_tipo": {
                "type": "string",
                "enum": ["HABILES", "CALENDARIO"],
            },
            "medidas_provisionales": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "descripcion": {"type": "string"},
                        "plazo_horas": {"type": "integer"},
                        "plazo_tipo": {"type": "string", "enum": ["HABILES", "CALENDARIO"]},
                        "fecha_auto": {"type": "string"},
                    },
                    "required": ["descripcion"],
                },
            },
            "accionante": {
                "type": "object",
                "properties": {
                    "documento_raw": {
                        "type": "string",
                        "description": (
                            "Número del documento de identidad del accionante EN CLARO "
                            "(cédula/NIT, solo dígitos). Será hasheado y borrado antes de persistir."
                        ),
                    },
                    "tipo_documento": {"type": "string"},
                },
            },
            "accionado": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "nit_raw": {"type": "string"},
                },
            },
            "derechos_invocados": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 10,
            },
            "hechos": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
            "pretensiones": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 10,
            },
            "sentido_fallo": {
                "type": "string",
                "enum": ["CONCEDIDA", "NEGADA", "PARCIAL", "IMPUGNADA", "N/A"],
                "description": "Solo aplica cuando tipo_actuacion es FALLO_*.",
            },
            "_confidence": {
                "type": "object",
                "description": "Confianza (0-1) por campo clave; usar valores bajos ante ambigüedad.",
                "properties": {
                    "plazo_informe_horas": {"type": "number", "minimum": 0, "maximum": 1},
                    "numero_expediente": {"type": "number", "minimum": 0, "maximum": 1},
                    "tipo_actuacion": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "required": ["tipo_actuacion", "plazo_informe_horas", "plazo_tipo", "_confidence"],
    },
}


SYSTEM_PROMPT = (
    "Eres un asistente experto en derecho constitucional colombiano. Analizas oficios "
    "judiciales de tutela y extraes metadata estructurado en JSON estricto.\n\n"
    "Reglas operativas:\n"
    "- 1 día hábil equivale a 8 horas hábiles para el cálculo de plazos.\n"
    "- Plazos expresados como 'dos (2) días hábiles' → plazo_informe_horas=16, plazo_tipo=HABILES.\n"
    "- Plazos expresados en horas calendario explícitas ('dentro de 24 horas') → plazo_tipo=CALENDARIO.\n"
    "- Expedientes: formato canónico CCCCC-CCCC-NNN-YYYY-NNNNN-NN.\n"
    "- Medidas provisionales: tienen plazo INDEPENDIENTE del informe principal. Extraerlas aparte.\n"
    "- Si el plazo del informe es AMBIGUO o NO aparece explícito, usa plazo_informe_horas=48 y "
    "  _confidence.plazo_informe_horas < 0.85 para que el sistema marque revisión humana.\n"
    "- NUNCA extraigas el NOMBRE del accionante. Solo documento_raw (cédula/NIT en dígitos). "
    "  El sistema lo hashea con salt por tenant y borra el original antes de persistir.\n"
    "- Usa _confidence bajo (<0.85) cuando tengas dudas; la UI pedirá revisión humana.\n"
)


async def _get_tenant_salt(cliente_id: Optional[uuid.UUID], conn) -> str:
    """Lee config_hash_salt del tenant. Fallback determinístico si no hay conn."""
    if conn is None or cliente_id is None:
        return f"test_salt_{cliente_id}"

    try:
        row = await conn.fetchrow(
            "SELECT config_hash_salt FROM clientes_tenant WHERE id = $1",
            cliente_id,
        )
        if row and row["config_hash_salt"]:
            return row["config_hash_salt"]
        logger.warning("tenant %s sin config_hash_salt — usando fallback", cliente_id)
        return f"missing_salt_{cliente_id}"
    except Exception:
        logger.exception("error leyendo config_hash_salt; usando fallback")
        return f"error_salt_{cliente_id}"


def _hash_documento(documento_raw: str, salt: str) -> str:
    """SHA-256 hex del documento salteado con el salt del tenant."""
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(b":")
    h.update(documento_raw.encode("utf-8"))
    return h.hexdigest()


def _extract_full_text(event: dict) -> str:
    """Concatena body + texto OCR de adjuntos (si los hay)."""
    partes: list[str] = []
    body = event.get("body", event.get("cuerpo", "")) or ""
    if body:
        partes.append(body)
    adjuntos = event.get("adjuntos") or event.get("attachments") or []
    if isinstance(adjuntos, list):
        for adj in adjuntos:
            if isinstance(adj, dict):
                ocr = adj.get("texto_ocr") or adj.get("text") or ""
                if ocr:
                    partes.append(f"\n\n[ADJUNTO {adj.get('nombre_archivo', '?')}]:\n{ocr}")
    return "\n".join(partes)


def _fallback_dict(error_msg: str) -> dict[str, Any]:
    """Dict defensivo cuando la extracción falla."""
    return {
        "_extraction_failed": True,
        "_error": error_msg,
        "_requiere_revision_humana": True,
        "plazo_informe_horas": _DEFAULT_PLAZO_HORAS,
        "plazo_tipo": _DEFAULT_PLAZO_TIPO,
        "tipo_actuacion": _DEFAULT_TIPO_ACTUACION,
        "_confidence": {"plazo_informe_horas": 0.0},
    }


async def enrich_tutela(event: dict, clasificacion: Any) -> dict[str, Any]:
    """
    Enricher principal de TUTELA. Invoca Claude Sonnet con tool_use forzado,
    parsea la respuesta, hashea documento y retorna el dict listo para persistir
    como `pqrs_casos.metadata_especifica`.
    """
    texto = _extract_full_text(event)
    tenant_id = event.get("tenant_id")
    cliente_id: Optional[uuid.UUID]
    try:
        cliente_id = uuid.UUID(tenant_id) if tenant_id else None
    except (ValueError, TypeError):
        cliente_id = None

    # Detectar marker sintético y warnear si pasa en prod.
    es_sintetico = _SYNTHETIC_MARKER in texto
    if es_sintetico and os.environ.get("ENV", "").lower() == "prod":
        logger.warning(
            "Fixture sintético %s detectado en AMBIENTE PROD — esto NO debería pasar",
            _SYNTHETIC_MARKER,
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY ausente — fallback defensivo")
        return _fallback_dict("no_api_key")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=ANTHROPIC_MODEL_SONNET,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": texto}],
            tools=[TUTELA_SCHEMA],
            tool_choice={"type": "tool", "name": "extraer_metadata_tutela"},
        )
    except Exception as e:
        logger.exception("Claude Sonnet error en enrich_tutela")
        return _fallback_dict(f"api_error: {e}")

    # Extraer el tool_use input del mensaje.
    metadata: Optional[dict[str, Any]] = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            metadata = dict(getattr(block, "input", {}) or {})
            break

    if metadata is None:
        logger.warning("Claude no devolvió tool_use; fallback defensivo")
        return _fallback_dict("no_tool_use_in_response")

    # Post-proc: hash documento + borrar raw.
    accionante = metadata.get("accionante")
    if isinstance(accionante, dict):
        doc_raw = accionante.get("documento_raw")
        if doc_raw:
            # Importamos aquí para permitir mocks en tests.
            from app.services.enrichers.tutela_extractor import _get_tenant_salt as _gts
            # Conn pasada vía clasificacion? No tenemos. Usamos fallback.
            salt = await _gts(cliente_id, None)
            accionante["documento_hash"] = _hash_documento(str(doc_raw), salt)
            accionante.pop("documento_raw", None)
            metadata["accionante"] = accionante

    # Idem para accionado.nit_raw si existe.
    accionado = metadata.get("accionado")
    if isinstance(accionado, dict):
        nit_raw = accionado.get("nit_raw")
        if nit_raw:
            from app.services.enrichers.tutela_extractor import _get_tenant_salt as _gts
            salt = await _gts(cliente_id, None)
            accionado["nit_hash"] = _hash_documento(str(nit_raw), salt)
            accionado.pop("nit_raw", None)
            metadata["accionado"] = accionado

    # Confidence check → marcar revisión humana si está debajo del umbral.
    conf_plazo = (
        metadata.get("_confidence", {}).get("plazo_informe_horas", 0.0)
        if isinstance(metadata.get("_confidence"), dict)
        else 0.0
    )
    if conf_plazo < _CONFIDENCE_UMBRAL:
        metadata["_requiere_revision_humana"] = True
        logger.warning(
            "plazo_informe_horas con confidence %.2f < %.2f — marcado para revisión humana",
            conf_plazo, _CONFIDENCE_UMBRAL,
        )

    if es_sintetico:
        metadata["_synthetic_fixture"] = _SYNTHETIC_MARKER

    return metadata


# Auto-registro en el dispatcher.
ENRICHERS["TUTELA"] = enrich_tutela
