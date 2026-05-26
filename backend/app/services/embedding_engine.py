"""
Wrapper async sobre Voyage AI para embeddings del KB de RAG (Fase 2).

Diseño:
- Async (compatible con FastAPI / asyncpg).
- Retry exponencial ante errores transitorios + rate-limit.
- Tipado de errores: el caller distingue auth vs rate-limit vs transient.
- Cada llamada devuelve (vectors, total_tokens) — el caller persiste el costo
  en `kb_ingestion_log`.
- `input_type` correcto ('document' vs 'query') — Voyage mejora retrieval
  cuando se distingue.

Modelo por defecto: voyage-multilingual-2 (1024d, optimizado multilingüe).
Coincide con la dimensionalidad de la columna `respuestas_kb.embedding`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Literal, Sequence

import voyageai

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Errores tipados
# --------------------------------------------------------------------------- #

class EmbeddingError(Exception):
    """Error base del embedding engine."""


class EmbeddingAuthError(EmbeddingError):
    """API key inválida o sin permisos. NO reintentar — escalar."""


class EmbeddingRateLimitError(EmbeddingError):
    """Rate limit alcanzado. Reintentar con backoff exponencial."""


class EmbeddingTransientError(EmbeddingError):
    """Error transitorio (red, 5xx). Reintentar."""


# --------------------------------------------------------------------------- #
# Resultado de cada llamada
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    total_tokens: int
    model: str


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

DEFAULT_MODEL = "voyage-multilingual-2"
DEFAULT_DIM = 1024  # matchea respuestas_kb.embedding vector(1024)

# Voyage hard limits (free tier): 60 req/min, 1M tokens/min, 1000 inputs por batch.
# El SDK ya valida el batch_size por modelo; nosotros chunkeamos defensivamente.
MAX_BATCH_SIZE = 128
MAX_RETRIES = 5
RETRY_BASE_SECONDS = 1.5  # 1.5s, 3s, 6s, 12s, 24s


class EmbeddingEngine:
    """Servicio async para generar embeddings vía Voyage AI."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        key = api_key or os.environ.get("VOYAGE_API_KEY")
        if not key:
            raise EmbeddingAuthError(
                "VOYAGE_API_KEY no está configurada en el entorno"
            )
        self._client = voyageai.AsyncClient(api_key=key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def embed_texts(
        self,
        textos: Sequence[str],
        input_type: Literal["document", "query"] = "document",
    ) -> EmbeddingResult:
        """Embedea una lista de textos. Chunkea automáticamente si excede el batch.

        Args:
            textos: secuencia de strings (cada uno es un doc o una query).
            input_type:
                - 'document' al ingerir contenido al KB.
                - 'query'    al embedear el email entrante para retrieval.
                Voyage usa esto para optimizar la representación según el rol.

        Returns:
            EmbeddingResult con vectores en el mismo orden que ``textos``
            + tokens totales consumidos + nombre del modelo.

        Raises:
            EmbeddingAuthError: API key inválida.
            EmbeddingRateLimitError: tras ``MAX_RETRIES`` con backoff.
            EmbeddingTransientError: error de red o servidor persistente.
            EmbeddingError: cualquier otro error.
        """
        if not textos:
            return EmbeddingResult(vectors=[], total_tokens=0, model=self._model)

        # Sanitizar: Voyage rechaza strings vacíos o solo whitespace.
        textos_limpios = [t.strip() for t in textos]
        if any(not t for t in textos_limpios):
            indices = [i for i, t in enumerate(textos_limpios) if not t]
            raise EmbeddingError(
                f"Textos vacíos en posiciones {indices} — limpiar antes de embedear"
            )

        all_vectors: list[list[float]] = []
        total_tokens = 0

        for i in range(0, len(textos_limpios), MAX_BATCH_SIZE):
            batch = textos_limpios[i : i + MAX_BATCH_SIZE]
            result = await self._embed_batch_with_retry(batch, input_type)
            all_vectors.extend(result.embeddings)
            total_tokens += result.total_tokens

        return EmbeddingResult(
            vectors=all_vectors,
            total_tokens=total_tokens,
            model=self._model,
        )

    async def _embed_batch_with_retry(
        self,
        batch: list[str],
        input_type: str,
    ):
        """Embedea UN batch (≤ MAX_BATCH_SIZE) con retry exponencial."""
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._client.embed(
                    texts=batch,
                    model=self._model,
                    input_type=input_type,
                )
            except Exception as exc:
                last_exc = exc
                kind = _classify_exception(exc)

                if kind == "auth":
                    # No tiene sentido reintentar auth — escalar.
                    raise EmbeddingAuthError(
                        f"Voyage rechazó la API key: {exc}"
                    ) from exc

                if attempt == MAX_RETRIES - 1:
                    # Última oportunidad agotada.
                    break

                wait = RETRY_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "embedding_engine: %s en intento %d/%d, retry en %.1fs (%s)",
                    kind, attempt + 1, MAX_RETRIES, wait, exc,
                )
                await asyncio.sleep(wait)

        # agotó reintentos
        kind = _classify_exception(last_exc) if last_exc else "transient"
        if kind == "rate_limit":
            raise EmbeddingRateLimitError(
                f"Rate limit tras {MAX_RETRIES} reintentos"
            ) from last_exc
        raise EmbeddingTransientError(
            f"Error persistente tras {MAX_RETRIES} reintentos: {last_exc}"
        ) from last_exc


def _classify_exception(exc: Exception | None) -> str:
    """Clasifica una excepción de voyageai para decidir cómo reintentar.

    bug_005 (review remoto): el substring "limit" desnudo matcheaba
    errores de validación no reintentables como "token limit exceeded" /
    "context length limit" / "max input length" como rate_limit, gastando
    ~47s en 5 retries inútiles antes de levantar EmbeddingRateLimitError
    con un mensaje engañoso. Ahora exigimos conjunciones claras
    ("rate limit", "too many requests") o el código 429 explícito.
    """
    if exc is None:
        return "unknown"
    msg = str(exc).lower()
    if "unauthorized" in msg or "invalid api" in msg or "401" in msg or "403" in msg:
        return "auth"
    if "rate limit" in msg or "too many requests" in msg or "429" in msg:
        return "rate_limit"
    return "transient"
