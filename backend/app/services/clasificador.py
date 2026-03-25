import re
from dataclasses import dataclass
from app.enums import TipoCaso, Prioridad
from app.core.config import PLAZOS_DIAS_HABILES, PRIORIDADES
from app.services.scoring_engine import score_and_classify, score_email

@dataclass
class ResultadoClasificacion:
    tipo: TipoCaso
    prioridad: Prioridad
    plazo_dias: int
    radicado: str | None
    cedula: str | None
    nombre_cliente: str | None
    es_juzgado: bool
    confianza: float

DOMINIOS_SPAM = [
    "litigando.com", "hablame.co", "hablame.com",
    "noreply@", "no-reply@", "newsletter@", "marketing@",
]

SUBJECTS_SPAM = [
    "generación de demanda", "generacion de demanda", "demanda generada",
    "analista de datos", "análisis de datos", "marketing", "newsletter",
    "publicidad", "oferta comercial", "propuesta comercial",
    "webinar", "capacitación gratuita",
]

def es_spam(sender: str, subject: str) -> bool:
    sender_lower = sender.lower()
    subject_lower = subject.lower()
    return (
        any(d in sender_lower for d in DOMINIOS_SPAM)
        or any(kw in subject_lower for kw in SUBJECTS_SPAM)
    )

DOMINIOS_JUZGADO = [
    "@cendoj.ramajudicial.gov.co", "@notificacionesrj.gov.co",
    "@consejodeestado.gov.co", "@cortesuprema.gov.co",
    "@corteconstitucional.gov.co", "@ramajudicial.gov.co",
    "@fiscalia.gov.co", "@procuraduria.gov.co",
]

_RE_RADICADO = [
    re.compile(r'(\d{2,4}[-/]\d{2,4}[-/]\d{2,8})', re.IGNORECASE),
    re.compile(r'RAD[ICADO]*[:\s]*(\d{10,25})', re.IGNORECASE),
    re.compile(r'No\.\s*(\d{10,25})', re.IGNORECASE),
    re.compile(r'(\d{23})'),
]
_RE_CEDULA = re.compile(r'(?i)(?:c\.c\.|cédula|cedula|cc|nit)[:\s#]*(\d{6,12})')
_RE_NOMBRE = re.compile(r'(?i)(?:señor|señora|sr\.|sra\.|accionante|demandante|cliente)[:\s]*([a-záéíóúñ][a-záéíóúñ\s]{5,50})')

def extraer_radicado(texto: str) -> str | None:
    for patron in _RE_RADICADO:
        match = patron.search(texto)
        if match:
            return match.group(1)
    return None

def extraer_cedula(texto: str) -> str | None:
    match = _RE_CEDULA.search(texto)
    return match.group(1) if match else None

def extraer_nombre(texto: str) -> str | None:
    match = _RE_NOMBRE.search(texto)
    if match:
        nombre = match.group(1).strip()
        return ' '.join(nombre.split())[:100]
    return None

def es_remitente_juzgado(email: str) -> bool:
    email_lower = email.lower()
    if any(d in email_lower for d in DOMINIOS_JUZGADO):
        return True
    return any(p in email_lower for p in ["juzgado", "tribunal", "corte", "judicial", "magistrad"])

def parece_pqrs(subject: str, body: str, sender: str) -> bool:
    if es_spam(sender, subject):
        return False
    if es_remitente_juzgado(sender):
        return True
    scores = score_email(subject, body[:500])
    return any(v > 0 for v in scores.values())

def clasificar_texto(
    asunto: str,
    cuerpo: str = "",
    remitente: str = ""
) -> ResultadoClasificacion:
    texto_completo = f"{asunto} {cuerpo}".strip()
    es_juzgado = es_remitente_juzgado(remitente)

    tipo_str, confianza, _ = score_and_classify(asunto, cuerpo, remitente)

    tipo = TipoCaso(tipo_str)
    prioridad = Prioridad(PRIORIDADES.get(tipo.value, "MEDIA"))
    plazo_dias = PLAZOS_DIAS_HABILES.get(tipo.value, 15)

    return ResultadoClasificacion(
        tipo=tipo,
        prioridad=prioridad,
        plazo_dias=plazo_dias,
        radicado=extraer_radicado(texto_completo),
        cedula=extraer_cedula(texto_completo),
        nombre_cliente=extraer_nombre(texto_completo),
        es_juzgado=es_juzgado,
        confianza=round(confianza, 2),
    )
