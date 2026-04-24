"""
enrichers/ — dispatcher polimórfico por tipo_caso.

Cada enricher especializado (hoy sólo `tutela_extractor`) se auto-registra
en `ENRICHERS` al importarse. El pipeline invoca `enrich_by_tipo` después
de la clasificación para obtener `metadata_especifica` según el tipo.

Si un `tipo_caso` no tiene enricher registrado, devuelve `{}` (no falla).
Si el enricher lanza excepción, se captura y devuelve un dict con
`_enrichment_failed=True` + el error, para que el pipeline pueda decidir
qué hacer (típicamente: seguir sin metadata y dejar que el trigger DB
calcule fecha_vencimiento).
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger("ENRICHERS")

# Firma del enricher: async callable que recibe (event, clasificacion) y
# retorna el dict metadata_especifica. Los enrichers pueden consultar DB
# usando la sesión asyncpg que ya está abierta en el pipeline.
Enricher = Callable[[dict, Any], Awaitable[dict[str, Any]]]

ENRICHERS: dict[str, Enricher] = {}


async def enrich_by_tipo(tipo_caso: str, event: dict, clasificacion: Any) -> dict[str, Any]:
    """
    Despacha al enricher correspondiente al `tipo_caso`.
    Retorna `{}` si no hay enricher registrado.
    Retorna `{"_enrichment_failed": True, "_error": ...}` si el enricher lanza.
    """
    enricher = ENRICHERS.get(tipo_caso)
    if enricher is None:
        return {}

    try:
        return await enricher(event, clasificacion)
    except Exception as e:
        logger.exception("enricher de %s lanzó excepción", tipo_caso)
        return {"_enrichment_failed": True, "_error": str(e)}


# Auto-registro de enrichers disponibles. El import provoca el side-effect
# `ENRICHERS["TUTELA"] = enrich_tutela`.
from . import tutela_extractor  # noqa: F401,E402
