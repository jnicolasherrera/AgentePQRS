"""
ai_classifier.py — Sprint 2: El Cerebro
Orquesta la clasificación de eventos de email usando clasificar_hibrido().
Agrega retry exponencial para RateLimitError de Anthropic y Claim Check inverso
(descarga adjuntos de MinIO para enriquecer el texto a clasificar).
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from app.core.config import PLAZOS_DIAS_HABILES, PRIORIDADES
from app.services.ai_engine import clasificar_hibrido
from app.services.storage_engine import download_file

logger = logging.getLogger("AI_CLASSIFIER")

MAX_RETRIES = 5
RETRY_BASE_SECONDS = 2.0  # Backoff exponencial: 2s, 4s, 8s, 16s, 32s

# Límite de bytes de adjunto que se envían al clasificador para evitar context overflow
_ADJUNTO_MAX_BYTES = 3000


class PoisonPillError(Exception):
    """Evento que superó el máximo de reintentos — debe ir a DLQ."""


@dataclass
class ClassificationResult:
    tipo_caso: str          # "TUTELA" | "PETICION" | "QUEJA" | "RECLAMO" | "SOLICITUD"
    prioridad: str          # "CRITICA" | "ALTA" | "MEDIA" | "BAJA"
    plazo_dias: int
    cedula: Optional[str]
    nombre_cliente: Optional[str]
    es_juzgado: bool
    confianza: float
    borrador: Optional[str]


async def classify_email_event(event: dict) -> ClassificationResult:
    """
    Clasifica un evento de email proveniente de Kafka.

    Flujo:
    1. Extrae asunto, cuerpo y remitente del evento (acepta claves en español o inglés).
    2. Claim Check inverso: si el evento trae adjunto_s3_uri, descarga los bytes
       desde MinIO y los añade al cuerpo para enriquecer la clasificación.
    3. Llama clasificar_hibrido() con retry exponencial ante anthropic.RateLimitError.
    4. Si se agotan los reintentos, lanza PoisonPillError para que el consumer
       mueva el mensaje a la Dead Letter Queue.
    """
    asunto = event.get("subject", event.get("asunto", ""))
    cuerpo = event.get("body", event.get("cuerpo", ""))
    remitente = event.get("sender", event.get("email_origen", ""))

    # Claim Check inverso: el adjunto viaja en MinIO, no en el mensaje Kafka
    adjunto_uri = event.get("adjunto_s3_uri")
    if adjunto_uri:
        adjunto_bytes = await _descargar_adjunto(adjunto_uri)
        if adjunto_bytes:
            texto_adjunto = adjunto_bytes[:_ADJUNTO_MAX_BYTES].decode("utf-8", errors="ignore")
            cuerpo = f"{cuerpo} [ADJUNTO]: {texto_adjunto}"

    for attempt in range(MAX_RETRIES):
        try:
            resultado = await clasificar_hibrido(asunto, cuerpo, remitente)
            return ClassificationResult(
                tipo_caso=resultado.tipo.value,
                prioridad=PRIORIDADES.get(resultado.tipo.value, "MEDIA"),
                plazo_dias=PLAZOS_DIAS_HABILES.get(resultado.tipo.value, 15),
                cedula=resultado.cedula,
                nombre_cliente=resultado.nombre_cliente,
                es_juzgado=resultado.es_juzgado,
                confianza=resultado.confianza,
                borrador=None,
            )
        except anthropic.RateLimitError:
            wait = RETRY_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                "RateLimitError Anthropic — intento %d/%d, esperando %.0fs",
                attempt + 1, MAX_RETRIES, wait,
            )
            if attempt == MAX_RETRIES - 1:
                raise PoisonPillError(
                    f"RateLimitError después de {MAX_RETRIES} intentos — evento enviado a DLQ"
                )
            await asyncio.sleep(wait)

    # Rama defensiva: nunca debería alcanzarse con la lógica anterior
    raise PoisonPillError("Clasificación falló sin RateLimitError explícito")


async def _descargar_adjunto(uri: str) -> Optional[bytes]:
    """
    Descarga un adjunto desde MinIO ejecutando el cliente síncrono en un thread pool.
    Devuelve None si falla, sin propagar la excepción (el clasificador continúa sin adjunto).
    """
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, download_file, uri)
    except Exception as exc:
        logger.warning("No se pudo descargar adjunto '%s': %s — continuando sin adjunto", uri, exc)
        return None
