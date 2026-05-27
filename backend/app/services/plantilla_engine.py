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
from app.services.document_reader import extract_from_adjuntos

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
    # Sprint FF 2026-05-27: prompt dedicado para consultas operativas
    # de atención al cliente (no legal). Tono cordial, sin lenguaje jurídico,
    # foco en próximos pasos prácticos.
    "ATENCION_CLIENTE": (
        "Eres agente de atención al cliente de FlexFintech (entidad financiera colombiana). "
        "Recibiste una consulta operativa de un cliente. Redacta una respuesta cordial, "
        "clara y profesional, sin usar lenguaje legal complicado. "
        "Explica los próximos pasos concretos que el cliente debe seguir o lo que vas a "
        "hacer por él. Si necesitás información adicional (cédula, comprobante, etc.) "
        "pedíselo amablemente. Cerrá ofreciendo seguir disponible para cualquier duda. "
        "Máximo 250 palabras."
    ),
}


async def generar_borrador_con_ia(
    asunto: str,
    cuerpo: str,
    tipo_caso: Optional[str],
    nombre_cliente: Optional[str],
    *,
    conn: Optional[asyncpg.Connection] = None,
    tenant_id: Optional[str] = None,
    tipo_workflow: str = "PQRS",
    contexto_adjuntos: Optional[str] = None,
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

        # Selección de system prompt:
        # - ATENCION_CLIENTE → prompt operativo (no legal).
        # - Legacy PQRS: usa el de tipo_caso (TUTELA/PETICION/QUEJA/RECLAMO/SOLICITUD).
        # - Fallback: SOLICITUD (lo más genérico legal).
        if tipo_workflow == "ATENCION_CLIENTE":
            system = _PROMPTS_TIPO["ATENCION_CLIENTE"]
            instrucciones_finales = (
                "La respuesta debe tener: saludo cordial al cliente, "
                "reconocimiento de su consulta, pasos concretos a seguir o "
                "qué vamos a hacer por él, pedido de info adicional si hace "
                "falta (cédula/comprobante), cierre amable. Máximo 250 palabras."
            )
        else:
            system = _PROMPTS_TIPO.get(tipo_caso, _PROMPTS_TIPO["SOLICITUD"])
            instrucciones_finales = (
                "La respuesta debe tener: saludo formal, reconocimiento del caso, "
                "fundamento legal aplicable, plazo de respuesta definitiva y despedida. "
                "Máximo 300 palabras."
            )

        # Inyectar el contexto RAG entre el asunto y el cuerpo si existe.
        bloque_contexto = (
            f"\n{contexto_rag}\n"
            "Usa el contexto anterior como guía de tono, normativa precisa y "
            "estructura. NO copies literal; redacta una respuesta nueva adaptada "
            "al caso específico.\n\n"
        ) if contexto_rag else ""

        # Sprint FF F1 2026-05-27: inyectar texto extraído de adjuntos si existe.
        # Claude considera el contenido de los PDFs/DOCX al armar el borrador.
        bloque_adjuntos = (
            f"\n\nDOCUMENTOS ADJUNTOS AL CORREO:\n{contexto_adjuntos}\n\n"
            "Usa la información de los adjuntos para personalizar la respuesta "
            "(menciona el proceso, número, fecha o detalles relevantes si aplica).\n"
        ) if contexto_adjuntos else ""

        user_msg = (
            f"Redacta la respuesta {saludo} al siguiente caso:\n\n"
            f"Asunto: {asunto}\n\n"
            f"Contenido del correo:\n{cuerpo[:1500]}\n"
            f"{bloque_adjuntos}"
            f"{bloque_contexto}"
            f"{instrucciones_finales}"
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
    """Detector estático (legacy): solo usa _DETECTION_RULES hardcoded.

    Mantenido para callers sin acceso a DB. Para detección que también
    matchea las plantillas dinámicas seedeadas (las 49 del Excel FF),
    usar `detectar_problematica_dinamica`.
    """
    texto = (asunto + " " + cuerpo[:1000]).lower()

    for slug, kw_base, kw_required in _DETECTION_RULES:
        if kw_required and not any(k in texto for k in kw_required):
            continue
        if any(k in texto for k in kw_base):
            return slug
    return None


async def _leer_adjuntos_para_contexto(conn, caso_id: str) -> Optional[str]:
    """Lee adjuntos ORIGINALES (es_reply=FALSE) del caso desde MinIO,
    extrae texto y devuelve un bloque listo para inyectar al prompt.

    Best-effort: si falla, log warn + devuelve None (sigue sin contexto).
    Sprint FF F1 2026-05-27.
    """
    try:
        from app.services.storage_engine import download_file
        rows = await conn.fetch(
            "SELECT nombre_archivo, storage_path, content_type "
            "FROM pqrs_adjuntos WHERE caso_id = $1::uuid AND es_reply = FALSE "
            "ORDER BY created_at ASC",
            uuid.UUID(caso_id),
        )
        if not rows:
            return None
        adjuntos = []
        for r in rows:
            content = download_file(r["storage_path"])
            if content:
                adjuntos.append({
                    "nombre_archivo": r["nombre_archivo"],
                    "content_bytes": content,
                    "content_type": r["content_type"] or "",
                })
        if not adjuntos:
            return None
        bloque = extract_from_adjuntos(adjuntos)
        return bloque if bloque else None
    except Exception as e:
        logger.warning("leer adjuntos para contexto falló: %s", e)
        return None


async def detectar_problematica_dinamica(
    conn: asyncpg.Connection,
    tenant_id: str,
    asunto: str,
    cuerpo: str,
    *,
    tipo_workflow: str = "PQRS",
) -> Optional[str]:
    """Detector híbrido (sprint FF bloque post-review ultrareview #11 — bug_016).

    Combina:
    1. `_DETECTION_RULES` hardcoded (8 reglas legacy Recovery).
    2. **Plantillas DB**: query a `plantillas_respuesta` filtrando por
       (cliente_id, tipo_workflow, is_active=TRUE, keywords no vacías) y
       matcheando cada keyword en el texto.

    Si ambas matchean, gana la hardcoded (más específica con
    `kw_required`). Si solo matchea DB, devuelve el slug DB.
    """
    # 1) Hardcoded primero (preserva semántica Recovery actual).
    slug_hc = detectar_problematica(asunto, cuerpo)
    if slug_hc:
        return slug_hc

    # 2) Plantillas DB con keywords.
    try:
        rows = await conn.fetch(
            """SELECT problematica, keywords FROM plantillas_respuesta
               WHERE cliente_id = $1::uuid
                 AND tipo_workflow = $2
                 AND is_active = TRUE
                 AND keywords IS NOT NULL
                 AND array_length(keywords, 1) > 0""",
            uuid.UUID(tenant_id), tipo_workflow,
        )
    except Exception as e:
        logger.warning("detectar_problematica_dinamica: query falló (%s)", e)
        return None

    if not rows:
        return None

    texto = (asunto + " " + (cuerpo or "")[:1000]).lower()
    for r in rows:
        for kw in (r["keywords"] or []):
            if kw and kw.lower() in texto:
                return r["problematica"]
    return None


async def obtener_plantilla(
    conn: asyncpg.Connection,
    tenant_id: str,
    problematica: str,
    *,
    tipo_workflow: str = "PQRS",
) -> Optional[dict]:
    """Busca la plantilla activa para el tenant + problemática + workflow.

    ``tipo_workflow`` separa plantillas legales (PQRS) de operativas
    (ATENCION_CLIENTE). Default 'PQRS' para mantener backward-compat con
    callers viejos. Sprint FlexFintech 2026-05-27.
    """
    row = await conn.fetchrow(
        """SELECT id, cuerpo, contexto FROM plantillas_respuesta
           WHERE cliente_id = $1 AND problematica = $2 AND is_active = TRUE
             AND tipo_workflow = $3
           LIMIT 1""",
        uuid.UUID(tenant_id), problematica, tipo_workflow,
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
    *,
    tipo_workflow: str = "PQRS",
    adjuntos_inline: Optional[list] = None,
) -> dict:
    """
    Detecta problemática, obtiene plantilla, personaliza borrador y actualiza pqrs_casos.
    Si no hay plantilla específica, intenta fallback genérico por tipo_caso.

    ``tipo_workflow`` (PQRS | ATENCION_CLIENTE) filtra plantillas para que no
    se mezclen las legales con las operativas. Default 'PQRS' = backward-compat.

    Retorna dict con borrador_respuesta, borrador_estado, problematica_detectada.
    """
    # bug_016 fix: usar el detector dinámico que matchea también las
    # 49 plantillas DB seedeadas para FlexFintech (no solo las 8 hardcoded).
    problematica = await detectar_problematica_dinamica(
        conn, tenant_id, asunto, cuerpo, tipo_workflow=tipo_workflow,
    )
    plantilla    = await obtener_plantilla(
        conn, tenant_id, problematica, tipo_workflow=tipo_workflow,
    ) if problematica else None

    if not plantilla and tipo_caso:
        slug_generico = f"GENERICO_{tipo_caso.upper()}"
        plantilla = await obtener_plantilla(
            conn, tenant_id, slug_generico, tipo_workflow=tipo_workflow,
        )

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
        # Fallback: Claude SIEMPRE genera borrador, aunque no haya plantilla
        # ni tipo_caso. Para ATENCION_CLIENTE usa prompt operativo dedicado;
        # para PQRS sin tipo_caso clasificado, cae a SOLICITUD genérico.
        # (Fix 2026-05-27: antes solo llamaba si tipo_caso truthy → casos AC
        # con problemática Recovery quedaban SIN_PLANTILLA + sin respuesta.)

        # Sprint FF F1: inyectar texto de adjuntos al prompt.
        # Prioridad: si el caller pasó adjuntos_inline (worker en runtime que
        # ya los descargó), extraer de ahí. Si no, leer de pqrs_adjuntos
        # (caso re-generación / batch sobre casos existentes).
        if adjuntos_inline:
            contexto_adjuntos = extract_from_adjuntos(adjuntos_inline) or None
        else:
            contexto_adjuntos = await _leer_adjuntos_para_contexto(conn, caso_id)

        borrador = await generar_borrador_con_ia(
            asunto, cuerpo, tipo_caso, nombre_cliente,
            conn=conn, tenant_id=tenant_id,
            tipo_workflow=tipo_workflow,
            contexto_adjuntos=contexto_adjuntos,
        )
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
