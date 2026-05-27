"""
Seed de plantillas Abogados Recovery a `plantillas_respuesta`.

Migra las 5 plantillas que vivían hardcoded en
``app/services/ai_engine.py:PLANTILLAS_RECOVERY`` al KB de la DB para que:

- Se ingesten a ``respuestas_kb`` por ``kb_backfill`` (retrieval RAG).
- Sean editables sin redeploy (el operario las puede ajustar desde el admin).
- Pasen por la misma maquinaria que FlexFintech (``detectar_problematica_dinamica``).

Idempotente por (cliente_id, problematica): re-ejecutar es seguro.

Uso (dentro del container backend):
    python -m scripts.seed_plantillas_recovery
    python -m scripts.seed_plantillas_recovery --dry-run

Sprint FF cierre-de-loop 2026-05-27 — paridad Recovery/FlexFintech.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_plantillas_recovery")

# tenant_id Abogados Recovery — sincronizado con app.constants
TENANT_RECOVERY = "effca814-b0b5-4329-96be-186c0333ad4b"

# Plantillas migradas literal desde ai_engine.PLANTILLAS_RECOVERY (Option B).
# Inmutables por normativa (Ley 2157 de 2021, Ley 1266 de 2008).
# `tipo_workflow='PQRS'` porque Recovery NO usa universo ATENCION_CLIENTE.
PLANTILLAS = [
    {
        "slug": "DEBITOS_AUTOMATICOS",
        "contexto": "Cliente reclama por débitos automáticos no autorizados — convenio Rapicredit",
        "keywords": ["debito", "débito", "automatico", "automático",
                     "cobro", "banco", "convenio"],
        "cuerpo": (
            "Buenas tardes Sr (a)\n\n"
            "Esperamos que se encuentre bien\n\n"
            "ABOGADOS RECOVERY OF CREDITS S.A.S.  respetuosamente se dirijo a "
            "usted con el fin de dar respuesta a la petición que invoca la ley "
            "hábeas data, los artículos 15, 21, 23 y 29 de la Constitución "
            "Política, la Ley 1266 de 2008, y la ley 2157 de 2021. \n\n"
            "Una vez revisado en nuestro sistema la información del solicitante, "
            "se indica que ABOGADOS RECOVERY OF CREDITS S.A.S, cuenta con "
            "contrato de prestación de servicios de cobranza con RAPICREDIT. "
            "Se indica con relación al hecho manifestado, que los débitos "
            "automáticos fueron aceptados desde el momento de la adquisición "
            "del crédito de conformidad con el contrato y los términos y "
            "condiciones por usted aceptados.\n\n"
            "Si desea solicitar alguna devolución debe realizarlo directamente "
            "a ayuda@rapicredit.com; teléfono de Servicio al cliente: "
            "60 (1) 3902670.\n\nCordialmente,"
        ),
    },
    {
        "slug": "PAZ_Y_SALVO_RAPICREDIT",
        "contexto": "Solicitud de paz y salvo / certificado de cancelación — acreedor Rapicredit",
        "keywords": ["paz y salvo", "rapicredit", "certificado", "salvo"],
        "cuerpo": (
            "Cordial saludo,\n\n"
            "ABOGADOS RECOVERY OF CREDITS S.A.S le informa que somos "
            "encargados de la gestión de cobranza conforme a la información "
            "suministrada directamente por el acreedor RAPICREDIT. Por "
            "consiguiente, cualquier asunto relacionado con desembolsos, "
            "actualización de mora u otros aspectos que no estén bajo nuestra "
            "jurisdicción deben ser gestionados directamente por el acreedor.\n\n"
            "Para solicitud de PAZ Y SALVO ó DEVOLUCIÓN, debe ponerse en "
            "contacto con ayuda@rapicredit.com; Teléfono de Servicio al "
            "cliente: 60 (1) 3902670.\n\nCordialmente,"
        ),
    },
    {
        "slug": "SUPLANTACION_RAPICREDIT",
        "contexto": "Cliente alega suplantación / falsedad personal — denuncia ante Fiscalía",
        "keywords": ["suplantacion", "suplantación", "fiscalia", "fiscalía",
                     "delito", "estafa", "identidad", "falsedad personal"],
        "cuerpo": (
            "Muy buenas tardes,\n\n"
            "Entendemos la difícil situación por la que está atravesando. Nos "
            "permitimos informarle que, de acuerdo con la Ley 2157 de 2021, "
            "artículo 7, en los casos donde el titular de la información "
            "alegue ser víctima del delito de falsedad personal, deberá "
            "presentar una petición de corrección directamente ante la fuente "
            "(RAPICREDIT), adjuntando los soportes correspondientes.\n\n"
            "Una vez recibida la solicitud, la fuente tiene un plazo de diez "
            "(10) días para cotejar los documentos. Dado que la denuncia ya "
            "fue interpuesta ante la Fiscalía, será esta autoridad la "
            "encargada de pronunciarse. Mientras tanto, legalmente la "
            "obligación continúa siendo exigible.\n\nCordialmente,"
        ),
    },
    {
        "slug": "ELIMINACION_CENTRALES_RIESGO",
        "contexto": "Solicitud de eliminación o actualización del reporte en centrales de riesgo (Datacrédito / TransUnion)",
        "keywords": ["centrales", "central de riesgo", "centrales de riesgo",
                     "datacredito", "datacrédito", "transunion", "reporte",
                     "eliminar reporte", "eliminacion", "eliminación"],
        "cuerpo": (
            "Cordial saludo.\n\n"
            "En atención a su solicitud, le informamos que en nuestro sistema "
            "la obligación registrada se encuentra al día. Le confirmamos que "
            "el proceso de actualización y eliminación del reporte en las "
            "centrales de riesgo ya ha sido gestionado. No obstante, considere "
            "que la actualización efectiva depende de los ciclos de "
            "procesamiento de las entidades de información crediticia "
            "(Datacrédito/TransUnion).\n\nCordialmente,"
        ),
    },
    {
        "slug": "PAZ_Y_SALVO_FINDORSE",
        "contexto": "Solicitud de paz y salvo — acreedor Findorse",
        "keywords": ["findorse", "paz y salvo findorse"],
        "cuerpo": (
            "Buenas tardes,\n\n"
            "ABOGADOS RECOVERY OF CREDITS S.A.S le informa que la gestión de "
            "cobranza se realiza conforme a la información de FINDORSE. "
            "Cualquier asunto de actualización de mora debe ser gestionado "
            "directamente por el acreedor.\n\n"
            "Para solicitud de PAZ Y SALVO, debe ingresar a la página "
            "https://www.findorse.co/ \n\nCordialmente,"
        ),
    },
]


async def upsert(conn: asyncpg.Connection, dry_run: bool) -> dict:
    """UPSERT por (cliente_id, problematica). Devuelve contadores."""
    contadores = {"insertados": 0, "actualizados": 0}

    for p in PLANTILLAS:
        if dry_run:
            logger.info("  DRY %s (chars=%d, kw=%d)",
                        p["slug"], len(p["cuerpo"]), len(p["keywords"]))
            continue

        existe = await conn.fetchval(
            "SELECT 1 FROM plantillas_respuesta "
            "WHERE cliente_id = $1::uuid AND problematica = $2",
            TENANT_RECOVERY, p["slug"],
        )
        if existe:
            await conn.execute(
                """UPDATE plantillas_respuesta
                   SET cuerpo = $1, contexto = $2, keywords = $3,
                       tipo_workflow = 'PQRS', is_active = TRUE
                   WHERE cliente_id = $4::uuid AND problematica = $5""",
                p["cuerpo"], p["contexto"], p["keywords"],
                TENANT_RECOVERY, p["slug"],
            )
            contadores["actualizados"] += 1
            logger.info("  ↻ UPDATE %s", p["slug"])
        else:
            await conn.execute(
                """INSERT INTO plantillas_respuesta
                      (cliente_id, problematica, contexto, cuerpo, keywords,
                       tipo_workflow, is_active)
                   VALUES ($1::uuid, $2, $3, $4, $5, 'PQRS', TRUE)""",
                TENANT_RECOVERY, p["slug"], p["contexto"], p["cuerpo"],
                p["keywords"],
            )
            contadores["insertados"] += 1
            logger.info("  + INSERT %s", p["slug"])

    return contadores


async def main_async(args: argparse.Namespace) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL no configurada")
        return 2

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute("SET app.is_superuser = 'true'")
        cont = await upsert(conn, args.dry_run)
        logger.info(
            "Hecho. insertados=%d actualizados=%d (dry_run=%s)",
            cont["insertados"], cont["actualizados"], args.dry_run,
        )
    finally:
        await conn.close()
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Solo loguea lo que haría, no escribe a la DB.")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async(parse_args())))
