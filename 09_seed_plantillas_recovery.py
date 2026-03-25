"""
Importa plantillas desde PLANTILLAS_v2.xlsx a la tabla plantillas_respuesta.
Uso: python 09_seed_plantillas_recovery.py [TENANT_ID]
     Si no se pasa TENANT_ID, busca el tenant por nombre 'Recovery' en la BD.
"""
import asyncio
import asyncpg
import openpyxl
import sys
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://pqrs_admin:pg_password@localhost:5434/pqrs_v2")
EXCEL_PATH   = os.environ.get("EXCEL_PATH", os.path.join(os.path.dirname(__file__), "../docs/07_Otros/PLANTILLAS_v2.xlsx"))

# Mapeo nombre Excel → slug normalizado + keywords para detección
PROBLEMATICA_META = {
    "DEBITOS AUTOMATICOS": {
        "slug": "DEBITOS_AUTOMATICOS",
        "keywords": ["débito automático", "debito automatico", "cobro automático", "cargo automático",
                     "débito no autorizado", "debito no autorizado", "debitan", "débito recurrente"],
    },
    "PAZ Y SALVO RAPICREDIT": {
        "slug": "PAZ_Y_SALVO_RAPICREDIT",
        "keywords": ["paz y salvo", "rapicredit", "certificado de paz", "libre de deuda",
                     "deuda cancelada", "saldo cero", "obligación cancelada"],
    },
    "SUPLANTACION RAPICREDIT": {
        "slug": "SUPLANTACION_RAPICREDIT",
        "keywords": ["suplantación", "suplantacion", "robo de identidad", "no reconozco",
                     "fraude", "rapicredit", "crédito que no solicité"],
    },
    "DELITO DE SUPLANTACION CLIENTES GENERALES": {
        "slug": "SUPLANTACION_GENERAL",
        "keywords": ["suplantación", "suplantacion", "robo de identidad", "no reconozco",
                     "fraude", "falsedad personal", "crédito que no solicité"],
    },
    "ELIMINACION EN CENTRALES": {
        "slug": "ELIMINACION_CENTRALES_PAZ_SALVO",
        "keywords": ["centrales de riesgo", "datacrédito", "datacredito", "eliminar reporte",
                     "eliminación", "eliminar historial", "reportado negativamente", "paz y salvo"],
    },
    "PAZ Y SALVO FINDORSE": {
        "slug": "PAZ_Y_SALVO_FINDORSE",
        "keywords": ["paz y salvo", "findorse", "certificado", "libre de deuda"],
    },
    "ELIMINACION EN CENTRALES ": {  # con espacio trailing del Excel
        "slug": "ELIMINACION_CENTRALES_PROPIA",
        "keywords": ["centrales de riesgo", "datacrédito", "datacredito", "actualización",
                     "actualizacion", "actualizar estado", "eliminar reporte"],
    },
}
SIN_IDENTIFICACION_KEYWORDS = ["sin cédula", "sin cedula", "sin identificación", "no aporta datos"]


async def run(tenant_id: str | None):
    conn = await asyncpg.connect(DATABASE_URL)

    if not tenant_id:
        row = await conn.fetchrow(
            "SELECT id FROM clientes_tenant WHERE nombre ILIKE '%recovery%' LIMIT 1"
        )
        if not row:
            print("ERROR: no se encontró tenant 'Recovery'. Pasá el UUID como argumento.")
            await conn.close()
            return
        tenant_id = str(row["id"])

    print(f"Tenant: {tenant_id}")

    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True)
    ws = wb["Hoja 1"]
    rows = list(ws.iter_rows(values_only=True))[1:]  # skip header

    inserted = 0
    for row in rows:
        contexto, problematica_raw, cuerpo = row[0], row[1], row[2]
        if not cuerpo:
            continue

        if problematica_raw:
            meta = PROBLEMATICA_META.get(problematica_raw.strip())
            if meta:
                slug     = meta["slug"]
                keywords = meta["keywords"]
            else:
                slug     = problematica_raw.strip().upper().replace(" ", "_")
                keywords = []
        else:
            # Fila sin nombre = SIN_IDENTIFICACION
            slug     = "SIN_IDENTIFICACION"
            keywords = SIN_IDENTIFICACION_KEYWORDS

        await conn.execute(
            """INSERT INTO plantillas_respuesta
                   (cliente_id, problematica, contexto, cuerpo, keywords)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT DO NOTHING""",
            tenant_id, slug, contexto, cuerpo.strip(), keywords,
        )
        inserted += 1
        print(f"  ✓ {slug}")

    await conn.close()
    print(f"\nTotal insertadas: {inserted}")


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run(tid))
