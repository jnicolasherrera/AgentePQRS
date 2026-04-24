from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import re
from typing import Optional


# ─────────────────────────────────────────────────────────────
# Semáforo SLA (sprint Tutelas)
# ─────────────────────────────────────────────────────────────
# Mapa polimórfico por tipo_caso. Valores en % de tiempo restante vs plazo total.
# La regla NARANJA solo aplica a TUTELA; PQRS_DEFAULT salta de AMARILLO directo
# a ROJO. NEGRO marca vencido sin respuesta (solo si negro_si_vencido=True; la
# UI puede usarlo para destacar tutelas vencidas en rojo intenso).
SEMAFORO_CONFIG: dict[str, dict[str, object]] = {
    "PQRS_DEFAULT": {
        "verde_hasta_pct": 50.0,
        "amarillo_hasta_pct": 20.0,
        "naranja_hasta_pct": None,       # PQRS no usa NARANJA.
        "rojo_hasta_pct": 0.0,
        "negro_si_vencido": False,
        "escalar_representante_legal_en_rojo": False,
    },
    "TUTELA": {
        "verde_hasta_pct": 50.0,
        "amarillo_hasta_pct": 25.0,
        "naranja_hasta_pct": 10.0,
        "rojo_hasta_pct": 0.0,
        "negro_si_vencido": True,
        "escalar_representante_legal_en_rojo": True,
    },
}


def calcular_semaforo(
    tipo_caso: str,
    fecha_creacion: datetime,
    fecha_vencimiento: datetime,
    ahora: Optional[datetime] = None,
) -> str:
    """
    Calcula el color de semáforo según el % de tiempo restante relativo al plazo total.

    - Lee SEMAFORO_CONFIG[tipo_caso], con fallback a "PQRS_DEFAULT".
    - Si ya se venció y `negro_si_vencido` → "NEGRO"; si no → "ROJO".
    - Para tutelas, aplica NARANJA entre rojo_hasta_pct y naranja_hasta_pct.

    Todos los datetimes se normalizan a UTC.
    """
    config = SEMAFORO_CONFIG.get(tipo_caso, SEMAFORO_CONFIG["PQRS_DEFAULT"])

    if ahora is None:
        ahora = datetime.now(timezone.utc)

    # Normalización a UTC (asume UTC si naive).
    def _utc(d: datetime) -> datetime:
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

    ahora_utc = _utc(ahora)
    creacion_utc = _utc(fecha_creacion)
    vencimiento_utc = _utc(fecha_vencimiento)

    tiempo_total = (vencimiento_utc - creacion_utc).total_seconds()
    if tiempo_total <= 0:
        return "NEGRO" if config["negro_si_vencido"] else "ROJO"

    tiempo_restante = (vencimiento_utc - ahora_utc).total_seconds()

    if tiempo_restante <= 0:
        return "NEGRO" if config["negro_si_vencido"] else "ROJO"

    pct_restante = (tiempo_restante / tiempo_total) * 100

    if pct_restante >= float(config["verde_hasta_pct"]):
        return "VERDE"
    if pct_restante >= float(config["amarillo_hasta_pct"]):
        return "AMARILLO"
    naranja_hasta = config.get("naranja_hasta_pct")
    if naranja_hasta is not None and pct_restante >= float(naranja_hasta):
        return "NARANJA"
    # entre 0 y el threshold restante → ROJO.
    return "ROJO"


@dataclass(frozen=True)
class ScoringRule:
    pattern: str
    weight: float
    category: str
    zone: str


SCORING_RULES: tuple[ScoringRule, ...] = (
    # TUTELA
    ScoringRule(r"acci[oó]n de tutela", 6.0, "TUTELA", "any"),
    ScoringRule(r"decreto 2591", 5.0, "TUTELA", "any"),
    ScoringRule(r"auto admisorio", 5.0, "TUTELA", "any"),
    ScoringRule(r"amparo constitucional", 4.0, "TUTELA", "any"),
    ScoringRule(r"derechos fundamentales", 3.0, "TUTELA", "any"),
    ScoringRule(r"notificaci[oó]n judicial", 3.0, "TUTELA", "any"),
    ScoringRule(r"providencia", 2.0, "TUTELA", "any"),
    ScoringRule(r"impugnaci[oó]n", 2.0, "TUTELA", "any"),
    ScoringRule(r"sentencia", 1.5, "TUTELA", "any"),
    ScoringRule(r"fallo", 1.5, "TUTELA", "any"),
    ScoringRule(r"demandante", 1.5, "TUTELA", "any"),
    ScoringRule(r"demandado", 1.5, "TUTELA", "any"),
    ScoringRule(r"juzgado", 1.0, "TUTELA", "any"),
    ScoringRule(r"tribunal", 1.0, "TUTELA", "any"),
    ScoringRule(r"magistrado", 1.0, "TUTELA", "any"),
    ScoringRule(r"juez", 1.0, "TUTELA", "any"),
    ScoringRule(r"amparo", 1.0, "TUTELA", "any"),
    ScoringRule(r"tutela", 3.0, "TUTELA", "subject"),
    ScoringRule(r"tutela", 2.0, "TUTELA", "body"),
    # PETICION
    ScoringRule(r"derecho de petici[oó]n", 6.0, "PETICION", "any"),
    ScoringRule(r"ley 1755", 5.0, "PETICION", "any"),
    ScoringRule(r"art[ií]culo 23", 4.0, "PETICION", "any"),
    ScoringRule(r"solicito informaci[oó]n", 3.0, "PETICION", "any"),
    ScoringRule(r"certificaci[oó]n", 2.0, "PETICION", "any"),
    ScoringRule(r"constancia", 2.0, "PETICION", "any"),
    ScoringRule(r"requiero", 1.5, "PETICION", "any"),
    ScoringRule(r"petici[oó]n", 2.5, "PETICION", "subject"),
    ScoringRule(r"petici[oó]n", 1.0, "PETICION", "body"),
    ScoringRule(r"copia", 1.0, "PETICION", "any"),
    ScoringRule(r"informaci[oó]n", 0.5, "PETICION", "body"),
    # QUEJA
    ScoringRule(r"queja formal", 5.0, "QUEJA", "any"),
    ScoringRule(r"queja", 3.0, "QUEJA", "subject"),
    ScoringRule(r"queja", 1.5, "QUEJA", "body"),
    ScoringRule(r"inconformidad", 3.0, "QUEJA", "any"),
    ScoringRule(r"mal servicio", 3.0, "QUEJA", "any"),
    ScoringRule(r"insatisfecho", 2.0, "QUEJA", "any"),
    ScoringRule(r"deficiente", 2.0, "QUEJA", "any"),
    ScoringRule(r"denuncia", 2.0, "QUEJA", "any"),
    ScoringRule(r"disgusto", 1.5, "QUEJA", "any"),
    ScoringRule(r"reclamaci[oó]n formal", 2.0, "QUEJA", "any"),
    # RECLAMO
    ScoringRule(r"reclamo", 3.0, "RECLAMO", "subject"),
    ScoringRule(r"reclamo", 1.5, "RECLAMO", "body"),
    ScoringRule(r"cobro indebido", 5.0, "RECLAMO", "any"),
    ScoringRule(r"cargo no reconocido", 5.0, "RECLAMO", "any"),
    ScoringRule(r"error en factura", 4.0, "RECLAMO", "any"),
    ScoringRule(r"devoluci[oó]n", 3.0, "RECLAMO", "any"),
    ScoringRule(r"reembolso", 3.0, "RECLAMO", "any"),
    ScoringRule(r"compensaci[oó]n", 2.0, "RECLAMO", "any"),
    # SOLICITUD
    ScoringRule(r"solicitud formal", 4.0, "SOLICITUD", "any"),
    ScoringRule(r"solicitud", 2.5, "SOLICITUD", "subject"),
    ScoringRule(r"solicitud", 1.0, "SOLICITUD", "body"),
    ScoringRule(r"necesito que", 2.0, "SOLICITUD", "any"),
    ScoringRule(r"agradecer[eé]", 1.5, "SOLICITUD", "any"),
    ScoringRule(r"necesito", 1.0, "SOLICITUD", "body"),
    ScoringRule(r"pido", 1.0, "SOLICITUD", "body"),
    # FELICITACION
    ScoringRule(r"felicitaci[oó]n", 5.0, "FELICITACION", "any"),
    ScoringRule(r"excelente servicio", 4.0, "FELICITACION", "any"),
    ScoringRule(r"buen trabajo", 3.0, "FELICITACION", "any"),
    ScoringRule(r"agradecimiento", 3.0, "FELICITACION", "any"),
    ScoringRule(r"reconocimiento", 2.0, "FELICITACION", "any"),
    ScoringRule(r"gracias", 1.0, "FELICITACION", "body"),
)

_COURT_DOMAINS = (
    "@cendoj.ramajudicial.gov.co",
    "@notificacionesrj.gov.co",
    "@consejodeestado.gov.co",
    "@cortesuprema.gov.co",
    "@corteconstitucional.gov.co",
    "@ramajudicial.gov.co",
    "@fiscalia.gov.co",
    "@procuraduria.gov.co",
)

_COURT_KEYWORDS = ("juzgado", "tribunal", "corte", "judicial", "magistrad")

_TUTELA_KEYWORDS = re.compile(
    r"\b(?:tutela|amparo|decreto\s*2591|acci[oó]n\s+de\s+tutela)\b",
    re.IGNORECASE | re.UNICODE,
)


@lru_cache(maxsize=512)
def _compile_pattern(pattern: str) -> re.Pattern:
    return re.compile(rf"\b{pattern}\b", re.IGNORECASE | re.UNICODE)


def score_email(subject: str, body: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    subject_lower = subject.lower()
    body_lower = body.lower()

    for rule in SCORING_RULES:
        compiled = _compile_pattern(rule.pattern)

        if rule.zone == "subject":
            if compiled.search(subject_lower):
                scores[rule.category] = scores.get(rule.category, 0.0) + rule.weight

        elif rule.zone == "body":
            if compiled.search(body_lower):
                scores[rule.category] = scores.get(rule.category, 0.0) + rule.weight

        elif rule.zone == "any":
            matched_subject = compiled.search(subject_lower)
            if matched_subject:
                scores[rule.category] = scores.get(rule.category, 0.0) + (rule.weight * 1.5)
            elif compiled.search(body_lower):
                scores[rule.category] = scores.get(rule.category, 0.0) + rule.weight

    return scores


def _es_remitente_juzgado(remitente: str) -> bool:
    remitente_lower = remitente.lower()
    for domain in _COURT_DOMAINS:
        if domain in remitente_lower:
            return True
    for keyword in _COURT_KEYWORDS:
        if keyword in remitente_lower:
            return True
    return False


def apply_context_signals(
    scores: dict[str, float], subject: str, body: str, remitente: str
) -> dict[str, float]:
    result = dict(scores)
    subject_lower = subject.lower()
    full_text = f"{subject_lower} {body.lower()}"

    if _es_remitente_juzgado(remitente):
        if _TUTELA_KEYWORDS.search(full_text):
            result["TUTELA"] = result.get("TUTELA", 0.0) + 4.0
        else:
            result["TUTELA"] = result.get("TUTELA", 0.0) + 1.0

    if re.search(r"\b(?:urgente|inmediata)\b", subject_lower, re.UNICODE):
        result["TUTELA"] = result.get("TUTELA", 0.0) + 1.5

    if re.search(r"\b48\s*(?:horas|hrs)\b", full_text, re.UNICODE):
        result["TUTELA"] = result.get("TUTELA", 0.0) + 2.0

    if re.search(r"\bhabeas\s+data\b", full_text, re.UNICODE):
        result["PETICION"] = result.get("PETICION", 0.0) + 2.0

    return result


def compute_confidence(scores: dict[str, float]) -> tuple[str, float]:
    filtered = {k: v for k, v in scores.items() if v > 0}
    if not filtered:
        return ("PETICION", 0.30)

    sorted_cats = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    best_type, best_score = sorted_cats[0]
    second_score = sorted_cats[1][1] if len(sorted_cats) > 1 else 0.0
    margin = best_score - second_score

    if best_score >= 10.0 and margin >= 5.0:
        confidence = 0.97
    elif best_score >= 7.0 and margin >= 3.0:
        confidence = 0.92
    elif best_score >= 5.0 and margin >= 2.0:
        confidence = 0.85
    elif best_score >= 3.0 and margin >= 1.0:
        confidence = 0.72
    elif best_score >= 1.5:
        confidence = 0.55
    else:
        confidence = 0.40

    return (best_type, confidence)


def score_and_classify(
    subject: str, body: str, remitente: str = ""
) -> tuple[str, float, dict[str, float]]:
    raw_scores = score_email(subject, body)
    boosted_scores = apply_context_signals(raw_scores, subject, body, remitente)
    tipo, confianza = compute_confidence(boosted_scores)
    return (tipo, confianza, boosted_scores)
