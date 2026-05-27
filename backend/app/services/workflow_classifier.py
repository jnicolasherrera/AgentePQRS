"""
Clasificador binario PQRS vs ATENCION_CLIENTE (sprint FlexFintech 2026-05-27).

Diseño:
- Un solo buzón Outlook recibe TODO mezclado (PQRS legales + consultas
  operativas de atención al cliente).
- Esta función decide a qué workflow va cada mail entrante.
- Heurística keywords-only (zero cost, sub-ms). Si keywords no decide,
  cae al `default_workflow` que viene del `config_buzones.tipo_workflow`
  (típicamente 'PQRS' — conservador legal).
- A futuro podríamos sumar una capa Claude tool_use cuando la confianza
  sea baja, igual que `clasificar_hibrido` hace para tipo_caso.

Reglas:
- DOMINIO JUDICIAL (@ramajudicial, @cendoj...) → siempre PQRS (no se
  arriesga a tratar una notificación judicial como atención al cliente).
- Keywords legales explícitas (tutela, derecho de petición, queja
  formal, …) → PQRS.
- Keywords operativas explícitas (paz y salvo, comprobante, libre de
  deuda, …) → ATENCION_CLIENTE.
- Si MATCHEAN AMBAS → PQRS (conservador — preferimos sobre-procesar
  como legal antes que sub-procesar).
- Si NO matchea ninguna → default_workflow del buzón.
"""

from __future__ import annotations

import re
from typing import Literal

Workflow = Literal["PQRS", "ATENCION_CLIENTE"]


# ── Señales de PQRS legal (orden importa: más específico primero) ─────────
_PQRS_DOMAINS_JUDICIALES = (
    "@ramajudicial.gov.co",
    "@cendoj.ramajudicial.gov.co",
    "@jurisdiccion",
    "@juzgado",
    "@tribunal",
    "@consejodeestado",
    "@cortesuprema",
)

# Frases legales explícitas — alta confianza PQRS
_PQRS_KEYWORDS_FUERTES = (
    "acción de tutela",
    "accion de tutela",
    "derecho de petición",
    "derecho de peticion",
    "habeas data",
    "hábeas data",
    "queja formal",
    "reclamo formal",
    "superintendencia financiera",
    "supersolidaria",
    "superservicios",
    "vulneración derecho fundamental",
    "vulneracion derecho fundamental",
    "decreto 2591",
    "ley 1755",
    "ley 1266",
    "circular básica jurídica",
    "circular basica juridica",
)

# Frases medias — necesitan otra señal para confirmar PQRS
_PQRS_KEYWORDS_MEDIAS = (
    "tutela",
    "petición",
    "peticion",
    "queja",
    "reclamo",
    "denuncia",
    "fundamental",
    "constitucional",
)


# ── Señales de ATENCION_CLIENTE (operativo, no legal) ────────────────────
_AC_KEYWORDS_FUERTES = (
    "paz y salvo",
    "paz_y_salvo",
    "certificado de cancelación",
    "certificado de cancelacion",
    "libre de deuda",
    "obligación cancelada",
    "obligacion cancelada",
    "comprobante de pago",
    "adjunto comprobante",
    "adjunto el comprobante",
    "enviar paz y salvo",
    "necesito mi paz y salvo",
    "solicito paz y salvo",
    "saldo de mi obligación",
    "estado de mi obligación",
    "estado de cuenta",
    "estado de la deuda",
)

_AC_KEYWORDS_MEDIAS = (
    "comprobante",
    "consulta",
    "información",
    "informacion",
    "duda",
    "ayuda",
    "saldo",
    "facturación",
    "facturacion",
)


# ── API pública ──────────────────────────────────────────────────────────

def clasificar_workflow(
    asunto: str,
    cuerpo: str,
    sender: str = "",
    *,
    default_workflow: Workflow = "PQRS",
) -> Workflow:
    """Devuelve 'PQRS' o 'ATENCION_CLIENTE' según contenido del mail.

    Args:
        asunto, cuerpo: texto del email.
        sender: email del remitente (para detectar dominios judiciales).
        default_workflow: fallback cuando keywords no deciden.
            Default 'PQRS' = conservador. El caller (worker) suele pasar
            `config_buzones.tipo_workflow` para alinearse con el buzón.

    Returns:
        'PQRS' o 'ATENCION_CLIENTE'.
    """
    sender_l = (sender or "").lower()
    if any(d in sender_l for d in _PQRS_DOMAINS_JUDICIALES):
        return "PQRS"  # judicial siempre PQRS, sin ambigüedad

    texto = f"{asunto or ''} {(cuerpo or '')[:1500]}".lower()

    # Fuertes: +2 cada una
    fuertes_pqrs = sum(1 for k in _PQRS_KEYWORDS_FUERTES if k in texto)
    fuertes_ac   = sum(1 for k in _AC_KEYWORDS_FUERTES   if k in texto)
    score_pqrs   = 2 * fuertes_pqrs
    score_ac     = 2 * fuertes_ac

    # Medias: solo si NO hubo fuertes del mismo lado (evita doble conteo
    # de palabras que están contenidas en las fuertes, p.ej. "comprobante"
    # vs "comprobante de pago"). Las medias agregan señal solo cuando la
    # fuerte no detectó nada explícito.
    if fuertes_pqrs == 0:
        score_pqrs += sum(1 for k in _PQRS_KEYWORDS_MEDIAS if k in texto)
    if fuertes_ac == 0:
        score_ac   += sum(1 for k in _AC_KEYWORDS_MEDIAS   if k in texto)

    # Decisión
    if score_pqrs == 0 and score_ac == 0:
        return default_workflow  # nada matcheó — caer al default del buzón
    if score_pqrs >= score_ac:
        return "PQRS"             # empate o pqrs gana = PQRS (conservador legal)
    return "ATENCION_CLIENTE"
