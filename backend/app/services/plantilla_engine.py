import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.services.rag_engine import (
    buscar_docs_similares,
    formatear_contexto_para_prompt,
)
from app.services.ab_test_engine import (
    persistir_variant,
    registrar_shadow_para_caso,
)

logger = logging.getLogger("PLANTILLA_ENGINE")

AVISO_GENERICA = (
    "\n\n---\n"
    "NOTA: Esta respuesta fue generada automáticamente por inteligencia artificial "
    "como borrador inicial. En producción, las respuestas se estandarizan y personalizan "
    "según los procedimientos y plantillas aprobadas por cada cliente.\n"
    "Por favor revise y ajuste antes de enviar."
)

_PROMPTS_TIPO = {
    "TUTELA": (
        "Eres un abogado colombiano experto en acciones de tutela. "
        "Redacta una respuesta formal a la tutela descrita, en nombre de la entidad demandada. "
        "Cita el Decreto 2591 de 1991 y recuerda que el plazo legal para responder es de 48 horas. "
        "Sé conciso, formal y técnico. Usa lenguaje jurídico colombiano."
    ),
    "PETICION": (
        "Eres un abogado colombiano experto en derechos de petición. "
        "Redacta una respuesta formal al derecho de petición descrito, citando el artículo 23 "
        "de la Constitución Política y la Ley 1755 de 2015. "
        "El plazo legal es de 15 días hábiles. Usa lenguaje formal y respetuoso."
    ),
    "QUEJA": (
        "Eres un abogado colombiano especialista en protección al consumidor financiero. "
        "Redacta una respuesta formal a la queja descrita, en cumplimiento de la normativa "
        "de la Superintendencia Financiera de Colombia. "
        "El plazo es de 8 días hábiles según la SFC. Sé empático pero formal."
    ),
    "RECLAMO": (
        "Eres un abogado colombiano especialista en protección al consumidor financiero. "
        "Redacta una respuesta formal al reclamo descrito, cumpliendo la normativa de la "
        "Superintendencia Financiera de Colombia (Circular Básica Jurídica). "
        "El plazo es de 8 días hábiles. Sé formal, empático y propositivo."
    ),
    "SOLICITUD": (
        "Eres un abogado colombiano. Redacta una respuesta formal y cordial a la solicitud "
        "descrita, indicando que fue radicada y será atendida dentro de los 15 días hábiles. "
        "Usa lenguaje formal colombiano."
    ),
}


async def generar_borrador_con_ia(
    asunto: str,
    cuerpo: str,
    tipo_caso: str,
    nombre_cliente: Optional[str],
    *,
    conn: Optional[asyncpg.Connection] = None,
    tenant_id: Optional[str] = None,
) -> Optional[str]:
    """Genera borrador con Claude Haiku cuando no hay plantilla disponible.

    Si ``conn`` y ``tenant_id`` están presentes Y ``VOYAGE_API_KEY`` configurada,
    se hace retrieval del KB (Fase 3 RAG) e inyecta los docs relevantes como
    contexto few-shot en el user prompt. Si el RAG falla, degrada silencioso
    sin romper el flujo (igual que como funciona hoy sin RAG).

    Devuelve adicionalmente el contexto usado en el atributo ``_rag_docs`` del
    string (vía dict-wrapper si fuera necesario en versiones futuras; hoy solo
    se loggean en el caller).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    # ── RAG retrieval (degrada elegante si falla) ────────────────────────────
    contexto_rag = ""
    docs_rag: list[dict] = []
    if conn is not None and tenant_id and os.environ.get("VOYAGE_API_KEY"):
        try:
            docs_rag = await buscar_docs_similares(
                conn, tenant_id, asunto, cuerpo, tipo_caso=tipo_caso,
            )
            if docs_rag:
                contexto_rag = formatear_contexto_para_prompt(docs_rag)
        except Exception as exc:  # noqa: BLE001 — RAG nunca debe romper el flow
            logger.warning("RAG retrieval falló — sigo sin contexto (%s)", exc)
            docs_rag = []

    # Guardamos los docs usados como atributo del module-level state para que
    # el caller los pueda loggear en audit_log_respuestas. Es feo pero menos
    # invasivo que cambiar el contrato de retorno.
    generar_borrador_con_ia._last_rag_docs = docs_rag  # type: ignore[attr-defined]

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        saludo = f"dirigida a {nombre_cliente}" if nombre_cliente else ""
        system = _PROMPTS_TIPO.get(tipo_caso, _PROMPTS_TIPO["SOLICITUD"])

        # Inyectar el contexto RAG entre el asunto y el cuerpo si existe.
        bloque_contexto = (
            f"\n{contexto_rag}\n"
            "Usa el contexto anterior como guía de tono, normativa precisa y "
            "estructura. NO copies literal; redacta una respuesta nueva adaptada "
            "al caso específico.\n\n"
        ) if contexto_rag else ""

        user_msg = (
            f"Redacta la respuesta {saludo} al siguiente caso:\n\n"
            f"Asunto: {asunto}\n\n"
            f"Contenido del correo:\n{cuerpo[:1500]}\n"
            f"{bloque_contexto}"
            "La respuesta debe tener: saludo formal, reconocimiento del caso, "
            "fundamento legal aplicable, plazo de respuesta definitiva y despedida. "
            "Máximo 300 palabras."
        )
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": user_msg}],
            system=system,
        )
        texto = resp.content[0].text.strip()
        return texto
    except Exception as e:
        logger.warning(f"IA borrador fallido: {e}")
        return None

# ---------------------------------------------------------------------------
# Mapeo problemática → keywords de detección (orden importa: más específico primero)
# ---------------------------------------------------------------------------
_DETECTION_RULES = [
    ("SUPLANTACION_RAPICREDIT",       ["suplantación", "suplantacion", "robo de identidad", "no reconozco", "fraude"],
                                       ["rapicredit"]),
    ("PAZ_Y_SALVO_RAPICREDIT",        ["paz y salvo", "certificado de paz", "libre de deuda", "obligación cancelada"],
                                       ["rapicredit"]),
    ("SUPLANTACION_GENERAL",          ["suplantación", "suplantacion", "robo de identidad", "no reconozco", "fraude",
                                        "falsedad personal", "crédito que no solicité"], []),
    ("PAZ_Y_SALVO_FINDORSE",          ["paz y salvo", "certificado de paz", "libre de deuda"],
                                       ["findorse"]),
    ("DEBITOS_AUTOMATICOS",           ["débito automático", "debito automatico", "cobro automático",
                                        "cargo automático", "débito no autorizado", "débito recurrente",
                                        "debitan", "cobro recurrente"], []),
    ("ELIMINACION_CENTRALES_PAZ_SALVO", ["centrales de riesgo", "datacrédito", "datacredito",
                                          "eliminar reporte", "reportado negativamente"],
                                          ["paz y salvo"]),
    ("ELIMINACION_CENTRALES_PROPIA",  ["centrales de riesgo", "datacrédito", "datacredito",
                                        "eliminar reporte", "actualización", "actualizar estado"], []),
    ("SIN_IDENTIFICACION",            ["sin cédula", "sin cedula", "sin identificación",
                                        "no aporta datos"], []),
]


def detectar_problematica(asunto: str, cuerpo: str) -> Optional[str]:
    """Retorna el slug de la problemática más probable, o None si no hay match."""
    texto = (asunto + " " + cuerpo[:1000]).lower()

    for slug, kw_base, kw_required in _DETECTION_RULES:
        if kw_required and not any(k in texto for k in kw_required):
            continue
        if any(k in texto for k in kw_base):
            return slug
    return None


async def obtener_plantilla(conn: asyncpg.Connection, tenant_id: str, problematica: str) -> Optional[dict]:
    """Busca la plantilla activa para el tenant y problemática dados."""
    row = await conn.fetchrow(
        """SELECT id, cuerpo, contexto FROM plantillas_respuesta
           WHERE cliente_id = $1 AND problematica = $2 AND is_active = TRUE
           LIMIT 1""",
        uuid.UUID(tenant_id), problematica,
    )
    return dict(row) if row else None


def personalizar_borrador(
    cuerpo_plantilla: str,
    nombre_cliente: Optional[str],
    cedula: Optional[str],
    radicado: Optional[str] = None,
    email_origen: Optional[str] = None,
    tipo_caso: Optional[str] = None,
    fecha_vencimiento: Optional[str] = None,
) -> str:
    """Sustituye variables reales en la plantilla: nombre, cédula, radicado, etc."""
    if nombre_cliente:
        cuerpo_plantilla = cuerpo_plantilla.replace(
            "Buenas tardes Sr (a)", f"Buenas tardes Sr(a) {nombre_cliente}"
        ).replace(
            "Buenas tardes\nEsperamos", f"Buenas tardes {nombre_cliente},\nEsperamos"
        ).replace(
            "Cordial saludo,", f"Cordial saludo {nombre_cliente},"
        ).replace(
            "Muy buenas tardes,", f"Muy buenas tardes {nombre_cliente},"
        ).replace(
            "Sr(a)", f"Sr(a) {nombre_cliente}"
        )
    import re
    vars_map = {
        "nombre": nombre_cliente or "",
        "cedula": cedula or "",
        "radicado": radicado or "",
        "email": email_origen or "",
        "tipo": tipo_caso or "",
        "fecha_vencimiento": fecha_vencimiento or "",
    }
    for key, val in vars_map.items():
        if val:
            cuerpo_plantilla = re.sub(
                r"\{\{\s*" + key + r"\s*\}\}",
                val, cuerpo_plantilla, flags=re.IGNORECASE,
            )
            cuerpo_plantilla = re.sub(
                r"\{\s*" + key + r"\s*\}",
                val, cuerpo_plantilla, flags=re.IGNORECASE,
            )
    return cuerpo_plantilla


async def generar_borrador_para_caso(
    conn: asyncpg.Connection,
    tenant_id: str,
    caso_id: str,
    asunto: str,
    cuerpo: str,
    nombre_cliente: Optional[str] = None,
    cedula: Optional[str] = None,
    tipo_caso: Optional[str] = None,
    radicado: Optional[str] = None,
    email_origen: Optional[str] = None,
    fecha_vencimiento: Optional[str] = None,
) -> dict:
    """
    Detecta problemática, obtiene plantilla, personaliza borrador y actualiza pqrs_casos.
    Si no hay plantilla específica, intenta fallback genérico por tipo_caso.
    Retorna dict con borrador_respuesta, borrador_estado, problematica_detectada.
    """
    problematica = detectar_problematica(asunto, cuerpo)
    plantilla    = await obtener_plantilla(conn, tenant_id, problematica) if problematica else None

    if not plantilla and tipo_caso:
        slug_generico = f"GENERICO_{tipo_caso.upper()}"
        plantilla = await obtener_plantilla(conn, tenant_id, slug_generico)

    rag_docs_usados: list[dict] = []
    if plantilla:
        borrador = personalizar_borrador(
            plantilla["cuerpo"], nombre_cliente, cedula,
            radicado=radicado, email_origen=email_origen,
            tipo_caso=tipo_caso, fecha_vencimiento=fecha_vencimiento,
        )
        estado   = "PENDIENTE"
        pid      = plantilla["id"]
    else:
        # Fallback: Claude genera un borrador legal genérico, ahora con RAG.
        borrador = await generar_borrador_con_ia(
            asunto, cuerpo, tipo_caso or "SOLICITUD", nombre_cliente,
            conn=conn, tenant_id=tenant_id,
        ) if tipo_caso else None
        estado   = "PENDIENTE" if borrador else "SIN_PLANTILLA"
        pid      = None
        rag_docs_usados = getattr(generar_borrador_con_ia, "_last_rag_docs", []) or []

        # ── Fase 4 A/B shadow mode ────────────────────────────────────────
        # Persistimos la variant oficial (with_rag) + lanzamos shadow no_rag
        # para comparación posterior. Ambas son fire-and-degrade: si
        # cualquiera falla, log warn y el flow sigue normal.
        if borrador and tipo_caso:
            await persistir_variant(
                conn, caso_id, tenant_id, "with_rag", borrador,
                rag_docs=[
                    {"source_type": d["source_type"],
                     "source_id":   d["source_id"],
                     "sim_score":   round(float(d["sim_score"]), 4)}
                    for d in rag_docs_usados
                ],
                tipo_caso=tipo_caso,
                modelo="claude-haiku-4-5-20251001",
            )
            # Shadow inline (~3-5s extra). NO usamos create_task para evitar
            # leaks de tasks no-awaited en el worker batch.
            await registrar_shadow_para_caso(
                conn, caso_id, tenant_id, asunto, cuerpo,
                tipo_caso, nombre_cliente,
            )

    await conn.execute(
        """UPDATE pqrs_casos
           SET borrador_respuesta     = $1,
               borrador_estado        = $2,
               problematica_detectada = $3,
               plantilla_id           = $4
           WHERE id = $5""",
        borrador, estado, problematica, pid, uuid.UUID(caso_id),
    )

    metadata = {
        "problematica": problematica,
        "tiene_plantilla": plantilla is not None,
        "rag_docs": [
            {"source_type": d["source_type"],
             "source_id":   d["source_id"],
             "sim_score":   round(float(d["sim_score"]), 4)}
            for d in rag_docs_usados
        ],
    }
    await conn.execute(
        """INSERT INTO audit_log_respuestas (caso_id, accion, metadata)
           VALUES ($1, 'BORRADOR_GENERADO', $2)""",
        uuid.UUID(caso_id),
        json.dumps(metadata),
    )

    logger.info(
        f"Borrador [{estado}] para caso {caso_id} | "
        f"problematica={problematica} | rag_docs={len(rag_docs_usados)}"
    )
    return {
        "borrador_respuesta":     borrador,
        "borrador_estado":        estado,
        "problematica_detectada": problematica,
        "rag_docs_usados":        len(rag_docs_usados),
    }
