import hashlib
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

from app.services.clasificador import (
    clasificar_texto, ResultadoClasificacion,
    extraer_cedula, extraer_nombre, extraer_radicado, es_remitente_juzgado,
)
from app.services.scoring_engine import score_and_classify
from app.enums import TipoCaso, Prioridad
from app.core.config import settings, PRIORIDADES, PLAZOS_DIAS_HABILES

UMBRAL_CONFIANZA = 0.70

CLASSIFICATION_TOOL = {
    "name": "clasificar_pqr",
    "description": "Clasifica un email PQR colombiano en su tipo legal correcto.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tipo": {
                "type": "string",
                "enum": ["TUTELA", "PETICION", "QUEJA", "RECLAMO", "SOLICITUD", "FELICITACION", "NO_PQR"],
            },
            "confianza": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confianza de 0.0 a 1.0 en la clasificación.",
            },
            "razonamiento": {
                "type": "string",
                "description": "Breve justificación de la clasificación.",
            },
        },
        "required": ["tipo", "confianza", "razonamiento"],
    },
}

SYSTEM_PROMPT_CLASIFICADOR = """Eres un experto en derecho colombiano especializado en clasificar PQRS (Peticiones, Quejas, Reclamos, Solicitudes) y Tutelas.

Tipos válidos:
- TUTELA: Acción constitucional para proteger derechos fundamentales. Plazo 48h. EN CASO DE DUDA, ELIGE TUTELA.
- PETICION: Derecho de petición (Art. 23 Constitución, Ley 1755). Solicitudes de información, certificados, copias.
- QUEJA: Inconformidad con un servicio o atención. Expresión de disgusto o mala experiencia.
- RECLAMO: Exigencia de corrección por cobros indebidos, errores en facturación, devoluciones.
- SOLICITUD: Petición general que no encaja en las anteriores. Solicitudes de gestión, trámites.
- FELICITACION: Agradecimiento o reconocimiento positivo.
- NO_PQR: No es una PQRS (spam, publicidad, emails internos).

Señales contextuales:
- Dominios judiciales (@ramajudicial.gov.co, @cendoj.ramajudicial.gov.co) sugieren TUTELA.
- "48 horas" en contexto legal sugiere TUTELA.
- "habeas data" sugiere PETICION (Ley 1266 de 2008).
- Usa el tool clasificar_pqr para responder."""

# IDs de Clientes Especiales
TENANT_RECOVERY = "effca814-b0b5-4329-96be-186c0333ad4b"

# Diccionario de Inteligencia Legal para Abogados Recovery (Option B)
# Estas plantillas son inmutables y basadas en la normativa colombiana actual (Ley 2157 de 2021)
PLANTILLAS_RECOVERY = [
    {
        "PROBLEMATICA": "DEBITOS AUTOMATICOS",
        "KEYWORDS": ["DEBITO", "AUTOMATICO", "COBRO", "BANCO", "CONVENIO"],
        "R": "Buenas tardes Sr (a)\n\nEsperamos que se encuentre bien\n\nABOGADOS RECOVERY OF CREDITS S.A.S.  respetuosamente se dirijo a usted con el fin de dar respuesta a la petición que invoca la ley hábeas data, los artículos 15, 21, 23 y 29 de la Constitución Política, la Ley 1266 de 2008, y la ley 2157 de 2021. \n\nUna vez revisado en nuestro sistema la información del solicitante, se indica que ABOGADOS RECOVERY OF CREDITS S.A.S, cuenta con contrato de prestación de servicios de cobranza con RAPICREDIT. Se indica con relación al hecho manifestado, que los débitos automáticos fueron aceptados desde el momento de la adquisición del crédito de conformidad con el contrato y los términos y condiciones por usted aceptados.\n\nSi desea solicitar alguna devolución debe realizarlo directamente a ayuda@rapicredit.com; teléfono de Servicio al cliente: 60 (1) 3902670.\n\nCordialmente,"
    },
    {
        "PROBLEMATICA": "PAZ Y SALVO RAPICREDIT",
        "KEYWORDS": ["PAZ Y SALVO", "SALVO", "RAPICREDIT", "CERTIFICADO", "DEUDA"],
        "R": "Cordial saludo,\n\nABOGADOS RECOVERY OF CREDITS S.A.S le informa que somos encargados de la gestión de cobranza conforme a la información suministrada directamente por el acreedor RAPICREDIT. Por consiguiente, cualquier asunto relacionado con desembolsos, actualización de mora u otros aspectos que no estén bajo nuestra jurisdicción deben ser gestionados directamente por el acreedor.\n\nPara solicitud de PAZ Y SALVO ó DEVOLUCIÓN, debe ponerse en contacto con ayuda@rapicredit.com; Teléfono de Servicio al cliente: 60 (1) 3902670.\n\nCordialmente,"
    },
    {
        "PROBLEMATICA": "SUPLANTACION RAPICREDIT",
        "KEYWORDS": ["SUPLANTACION", "FISCALIA", "DELITO", "ESTAFA", "IDENTIDAD"],
        "R": "Muy buenas tardes,\n\nEntendemos la difícil situación por la que está atravesando. Nos permitimos informarle que, de acuerdo con la Ley 2157 de 2021, artículo 7, en los casos donde el titular de la información alegue ser víctima del delito de falsedad personal, deberá presentar una petición de corrección directamente ante la fuente (RAPICREDIT), adjuntando los soportes correspondientes.\n\nUna vez recibida la solicitud, la fuente tiene un plazo de diez (10) días para cotejar los documentos. Dado que la denuncia ya fue interpuesta ante la Fiscalía, será esta autoridad la encargada de pronunciarse. Mientras tanto, legalmente la obligación continúa siendo exigible.\n\nCordialmente,"
    },
    {
        "PROBLEMATICA": "ELIMINACION EN CENTRALES (PAZ Y SALVO)",
        "KEYWORDS": ["CENTRALES", "RIESGO", "DATACREDITO", "REPORTE", "ELIMINAR"],
        "R": "Cordial saludo.\n\nEn atención a su solicitud, le informamos que en nuestro sistema la obligación registrada se encuentra al día. Le confirmamos que el proceso de actualización y eliminación del reporte en las centrales de riesgo ya ha sido gestionado. No obstante, considere que la actualización efectiva depende de los ciclos de procesamiento de las entidades de información crediticia (Datacrédito/TransUnion).\n\nCordialmente,"
    },
    {
        "PROBLEMATICA": "PAZ Y SALVO FINDORSE",
        "KEYWORDS": ["FINDORSE", "PAZ Y SALVO", "SOPORTE"],
        "R": "Buenas tardes,\n\nABOGADOS RECOVERY OF CREDITS S.A.S le informa que la gestión de cobranza se realiza conforme a la información de FINDORSE. Cualquier asunto de actualización de mora debe ser gestionado directamente por el acreedor.\n\nPara solicitud de PAZ Y SALVO, debe ingresar a la página https://www.findorse.co/ \n\nCordialmente,"
    }
]

def _merge_confidence(
    kw_tipo: str, kw_conf: float,
    cl_tipo: str, cl_conf: float,
) -> tuple[str, float]:
    if kw_tipo == cl_tipo:
        return (kw_tipo, min(kw_conf + 0.08, 0.99))
    if cl_conf >= 0.70:
        return (cl_tipo, cl_conf)
    return (cl_tipo, max(cl_conf, 0.50))


async def _log_feedback(
    email_text: str,
    kw_tipo: str, kw_conf: float,
    cl_tipo: str, cl_conf: float,
    razonamiento: str,
) -> None:
    try:
        from app.core.db import get_raw_pool
        pool = get_raw_pool()
        if not pool:
            return
        email_hash = hashlib.sha256(email_text[:500].encode()).hexdigest()[:32]
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO clasificacion_feedback
                   (email_hash, keyword_tipo, keyword_confianza,
                    claude_tipo, claude_confianza, claude_razonamiento)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                email_hash, kw_tipo, kw_conf, cl_tipo, cl_conf, razonamiento[:500],
            )
    except Exception as e:
        logger.debug(f"Feedback log skipped: {e}")


async def clasificar_hibrido(asunto: str, cuerpo: str = "", remitente: str = "") -> ResultadoClasificacion:
    resultado = clasificar_texto(asunto, cuerpo, remitente)
    if resultado.confianza >= UMBRAL_CONFIANZA or not settings.anthropic_api_key:
        return resultado

    kw_tipo = resultado.tipo.value
    kw_conf = resultado.confianza

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        _, _, scores = score_and_classify(asunto, cuerpo, remitente)
        scores_txt = ", ".join(f"{k}: {v:.1f}" for k, v in sorted(scores.items(), key=lambda x: -x[1]) if v > 0)

        user_prompt = (
            f"Clasifica este email PQR colombiano.\n\n"
            f"Asunto: {asunto}\n"
            f"Cuerpo (primeros 500 chars): {cuerpo[:500]}\n"
            f"Remitente: {remitente}\n\n"
            f"Puntajes del análisis de keywords: [{scores_txt or 'sin coincidencias'}]\n"
            f"Clasificación de keywords: {kw_tipo} (confianza {kw_conf:.2f})\n\n"
            "Confirma o corrige la clasificación usando el tool clasificar_pqr."
        )

        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=SYSTEM_PROMPT_CLASIFICADOR,
            tools=[CLASSIFICATION_TOOL],
            tool_choice={"type": "tool", "name": "clasificar_pqr"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        tool_block = next((b for b in msg.content if b.type == "tool_use"), None)
        if not tool_block:
            logger.warning("Claude no usó tool_use, fallback a keywords")
            return resultado

        cl_tipo = tool_block.input.get("tipo", kw_tipo).upper()
        cl_conf = float(tool_block.input.get("confianza", 0.70))
        razonamiento = tool_block.input.get("razonamiento", "")

        if cl_tipo == "NO_PQR":
            cl_tipo = kw_tipo
            cl_conf = max(kw_conf, 0.50)

        final_tipo_str, final_conf = _merge_confidence(kw_tipo, kw_conf, cl_tipo, cl_conf)

        if kw_tipo != cl_tipo:
            logger.info(f"Claude corrigió: {kw_tipo}→{cl_tipo} ({razonamiento[:80]})")
            await _log_feedback(f"{asunto} {cuerpo}", kw_tipo, kw_conf, cl_tipo, cl_conf, razonamiento)

        tipo = TipoCaso(final_tipo_str)
        return ResultadoClasificacion(
            tipo=tipo,
            prioridad=Prioridad(PRIORIDADES.get(tipo.value, "MEDIA")),
            plazo_dias=PLAZOS_DIAS_HABILES.get(tipo.value, 15),
            radicado=resultado.radicado,
            cedula=resultado.cedula,
            nombre_cliente=resultado.nombre_cliente,
            es_juzgado=resultado.es_juzgado,
            confianza=round(final_conf, 2),
        )
    except Exception as e:
        logger.warning(f"Claude API falló en clasificar_hibrido: {e}, usando keywords")
        return resultado


async def analizar_pqr_documento(asunto: str, cuerpo_texto: str, remitente: str = "") -> Dict[str, Any]:
    """
    Clasifica la PQR — keywords primero, Claude si confianza baja.
    """
    resultado = await clasificar_hibrido(asunto, cuerpo_texto, remitente)

    return {
        "tipo_identificado": resultado.tipo.value,
        "prioridad_sugerida": resultado.prioridad.value,
        "plazo_dias_estimado": resultado.plazo_dias,
        "cedula_extraida": resultado.cedula or "No identificada",
        "radicado_detectado": resultado.radicado or "N/A",
        "nombre_cliente": resultado.nombre_cliente or "Desconocido",
        "confianza_clasificacion": resultado.confianza,
        "es_juzgado": resultado.es_juzgado
    }

async def redactar_borrador_legal(datos_caso: dict) -> str:
    cliente_id = str(datos_caso.get("cliente_id", ""))
    asunto_raw = datos_caso.get("asunto", "")
    cuerpo_raw = datos_caso.get("cuerpo", "")
    email_origen = datos_caso.get("email_origen", "")

    texto_completo = f"{asunto_raw} {cuerpo_raw}"
    cedula = extraer_cedula(texto_completo) or ""
    nombre = extraer_nombre(texto_completo) or email_origen.split("@")[0].replace(".", " ").title()
    radicado = datos_caso.get("numero_radicado") or extraer_radicado(texto_completo) or ""

    asunto = asunto_raw.upper()
    cuerpo = cuerpo_raw.upper()
    mensaje_completo = f"{asunto} {cuerpo}"

    if cliente_id == TENANT_RECOVERY:
        mejor_match = None

        for p in PLANTILLAS_RECOVERY:
            problema = p.get("PROBLEMATICA", "").upper()
            keywords = p.get("KEYWORDS", [])

            if problema and (problema in mensaje_completo):
                mejor_match = p
                break

            if any(k.upper() in mensaje_completo for k in keywords if len(k) > 3):
                mejor_match = p

        if mejor_match:
            respuesta = mejor_match.get("R", "")
            respuesta = respuesta.replace("Sr (a)", f"Sr(a) {nombre}")
            respuesta = respuesta.replace("Cordial saludo,", f"Cordial saludo {nombre},")
            respuesta = respuesta.replace("Muy buenas tardes,", f"Muy buenas tardes {nombre},")
            return respuesta

    tipo = datos_caso.get("tipo_caso", "DERECHO_PETICION")
    cedula_display = cedula if cedula else "[pendiente verificación]"
    radicado_display = radicado if radicado else "[por asignar]"

    if tipo == "TUTELA":
        juzgado_info = ""
        if es_remitente_juzgado(email_origen):
            juzgado_info = f"JUZGADO remitente: {email_origen}"

        plantilla = f"""Señor(a) Juez,
JUZGADO DE CONOCIMIENTO
{juzgado_info}

Ref: Respuesta a Acción de Tutela — Radicado {radicado_display}
Accionante: {nombre} — C.C. {cedula_display}
Accionado: FLEXFINTECH

Respetado Juez,

En atención a la Acción de Tutela de la referencia, notificada a nuestra entidad en la fecha correspondiente, nos permitimos dar contestación a la misma dentro del término legal (2 días hábiles), en los siguientes términos:

Sobre los Hechos:
El accionante manifiesta en su escrito inicial: "{asunto_raw[:80]}". Al respecto, FLEXFINTECH aclara que los procedimientos de cobranza o reporte en centrales de riesgo se realizaron bajo estricto apego a la Ley 1266 de 2008 (Habeas Data).

Se adjuntan los siguientes soportes para desvirtuar la vulneración de derechos:
1. ...
2. ...

Solicitamos muy respetuosamente denegar las pretensiones de la acción de tutela.

Atentamente,
Departamento Legal
FLEXFINTECH"""
    else:
        plantilla = f"""Señor(a) {nombre},

Ref: Respuesta a Derecho de Petición — Radicado {radicado_display}
C.C. {cedula_display}
Asunto: {asunto_raw}

Cordiales saludos.

En atención a su derecho de petición radicado en nuestros sistemas, donde nos solicita aclaraciones sobre su obligación, le informamos lo siguiente:

Procedemos a emitir y adjuntar a la presente comunicación los históricos de pago y/o paz y salvos correspondientes a su solicitud. Nuestros reportes a centrales de riesgo (Datacrédito, TransUnion) se encuentran debidamente actualizados.

Si necesita mayor información, no dude en contactarnos a nuestros canales oficiales.

Atentamente,
Atención al Cliente
FLEXFINTECH"""
    return plantilla.strip()
