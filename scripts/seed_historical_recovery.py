"""Migra casos históricos de Abogados Recovery desde Excel V1 a PostgreSQL V2.

Hojas procesadas: Reclamos, Mails, CONSOLIDADO SANTANDER, CONSOLIDADO BOGOTA.
Asigna round-robin a los abogados del tenant y marca con [HISTÓRICO].
Idempotente por external_msg_id.
"""
import pandas as pd
import asyncpg
import asyncio
import uuid
import os
import hashlib
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.environ.get(
    "WORKER_DB_URL",
    "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2",
)
EXCEL_PATH = os.environ.get(
    "EXCEL_PATH",
    "E:\\COLOMBIA\\PQRS_V2\\Consolidado Reclamos.xlsx",
)
RECOVERY_TENANT = uuid.UUID("effca814-b0b5-4329-96be-186c0333ad4b")

TIPO_MAP = {
    "BAJA DE BURO": "RECLAMO",
    "CANCELADO": "RECLAMO",
    "DESCONOCIMIENTO": "RECLAMO",
    "FRAUDE": "RECLAMO",
    "RECLAMO": "RECLAMO",
    "PAZ Y SALVO": "SOLICITUD",
    "LIBRE DEUDA": "SOLICITUD",
    "SUPLANTACION": "QUEJA",
    "SUPLANTACIÓN": "QUEJA",
}

ESTADO_MAP = {
    "CERRADO": "CERRADO",
    "PROCESO": "EN_PROGRESO",
    "REVISION": "EN_PROGRESO",
    "REVISIÓN": "EN_PROGRESO",
    "RECLAMO": "ABIERTO",
}

PLAZOS_DIAS = {
    "TUTELA": 2,
    "RECLAMO": 15,
    "QUEJA": 8,
    "SOLICITUD": 15,
    "PETICION": 15,
}


def clean(val):
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()


def parse_date(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    try:
        dt = pd.to_datetime(val, dayfirst=True).to_pydatetime()
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def map_tipo(raw):
    s = clean(raw).upper()
    for key, val in TIPO_MAP.items():
        if key in s:
            return val
    return "PETICION"


def map_estado(raw):
    s = clean(raw).upper()
    for key, val in ESTADO_MAP.items():
        if key in s:
            return val
    return "ABIERTO"


def map_prioridad(alerta):
    s = clean(alerta).upper()
    if "CRÍTICO" in s or "CRITICO" in s or "DEFCON" in s:
        return "ALTA"
    if "DEMORADO" in s or "ATENCION" in s:
        return "MEDIA"
    return "NORMAL"


def make_external_id(sheet, row_data):
    raw = f"{sheet}:{row_data}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def get_abogados(conn):
    await conn.execute(f"SET app.current_tenant_id = '{RECOVERY_TENANT}'")
    await conn.execute("SET app.is_superuser = 'true'")
    rows = await conn.fetch(
        "SELECT id, nombre, email FROM usuarios "
        "WHERE cliente_id = $1 AND rol IN ('abogado', 'analista') "
        "ORDER BY email",
        RECOVERY_TENANT,
    )
    return [r["id"] for r in rows]


async def insert_caso(conn, caso):
    return await conn.fetchval("""
        INSERT INTO pqrs_casos (
            cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad,
            fecha_recibido, created_at, tipo_caso, fecha_vencimiento,
            asignado_a, fecha_asignacion, enviado_at, external_msg_id,
            numero_radicado, acuse_enviado
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
        )
        ON CONFLICT (cliente_id, external_msg_id)
            WHERE external_msg_id IS NOT NULL DO NOTHING
        RETURNING id
    """,
        caso["cliente_id"], caso["email_origen"], caso["asunto"], caso["cuerpo"],
        caso["estado"], caso["nivel_prioridad"], caso["fecha_recibido"],
        caso["created_at"], caso["tipo_caso"], caso["fecha_vencimiento"],
        caso["asignado_a"], caso["fecha_asignacion"], caso["enviado_at"],
        caso["external_msg_id"], caso["numero_radicado"], True,
    )


def process_reclamos(df, abogados):
    casos = []
    rr = 0
    for _, row in df.iterrows():
        doc = clean(row.get("DNI/CEDULA CLIENTE", ""))
        nombre = clean(row.get("APELLIDO Y NOMBRE", ""))
        tipo_raw = clean(row.get("TIPO DE RECLAMO", "RECLAMO"))
        fecha_rec = parse_date(row.get("FECHA RECLAMO")) or parse_date(row.get("FECHA CARGA"))
        if not fecha_rec:
            continue
        estado = map_estado(row.get("AVANCE RECLAMO", "CERRADO"))
        tipo = map_tipo(tipo_raw)
        prioridad = map_prioridad(row.get("ALERTA", ""))
        comentario = clean(row.get("COMENTARIO INTERNO", ""))
        contacto = clean(row.get("DATO CONTACTO", ""))
        ultima_act = parse_date(row.get("ÚLTIMA ACTUALIZACIÓN") or row.get("ULTIMA ACTUALIZACION"))
        email = f"doc_{doc}@historico.recovery.co" if doc else f"anon_{uuid.uuid4().hex[:6]}@historico.recovery.co"
        ext_id = make_external_id("reclamos", f"{doc}:{fecha_rec}:{tipo_raw}")
        radicado = f"REC-{fecha_rec.year}-{ext_id[:8].upper()}"
        fecha_asig = fecha_rec + timedelta(days=1)
        fecha_venc = fecha_rec + timedelta(days=PLAZOS_DIAS.get(tipo, 15))
        enviado_at = ultima_act if estado == "CERRADO" and ultima_act else None

        casos.append({
            "cliente_id": RECOVERY_TENANT,
            "email_origen": email,
            "asunto": f"[HISTÓRICO] {tipo_raw} - {nombre} - Doc:{doc}",
            "cuerpo": f"Migrado de V1.\nTipo: {tipo_raw}\nContacto: {contacto}\n---\n{comentario}",
            "estado": estado,
            "nivel_prioridad": prioridad,
            "fecha_recibido": fecha_rec,
            "created_at": fecha_rec,
            "tipo_caso": tipo,
            "fecha_vencimiento": fecha_venc,
            "asignado_a": abogados[rr % len(abogados)],
            "fecha_asignacion": fecha_asig,
            "enviado_at": enviado_at,
            "external_msg_id": ext_id,
            "numero_radicado": radicado,
        })
        rr += 1
    return casos


def process_mails(df, abogados, start_rr=0):
    casos = []
    rr = start_rr
    for _, row in df.iterrows():
        doc = clean(row.get("DOCUMENTO", ""))
        nombre = clean(row.get("NOMBRE", ""))
        mail = clean(row.get("MAIL", ""))
        tipo_raw = clean(row.get("TIPO DE RECLAMO", "CONSULTA"))
        fecha_rec = parse_date(row.get("FECHA DE INGRESO")) or parse_date(row.get("FECHA DE CARGA"))
        if not fecha_rec:
            continue
        estado = map_estado(row.get("ESTADO", "CERRADO"))
        tipo = map_tipo(tipo_raw)
        prioridad = map_prioridad(row.get("ALERTA", ""))
        comentario = clean(row.get("COMENTARIO INTERNO - GESTION", ""))
        ultima_act = parse_date(row.get("ULTIMA ACTUALIZACION"))
        email = mail if "@" in mail else (f"doc_{doc}@historico.recovery.co" if doc else f"anon_{uuid.uuid4().hex[:6]}@historico.recovery.co")
        ext_id = make_external_id("mails", f"{doc}:{mail}:{fecha_rec}:{tipo_raw}")
        radicado = f"MAIL-{fecha_rec.year}-{ext_id[:8].upper()}"
        fecha_asig = fecha_rec + timedelta(days=1)
        fecha_venc = fecha_rec + timedelta(days=PLAZOS_DIAS.get(tipo, 15))
        enviado_at = ultima_act if estado == "CERRADO" and ultima_act else None

        casos.append({
            "cliente_id": RECOVERY_TENANT,
            "email_origen": email,
            "asunto": f"[HISTÓRICO] {tipo_raw} - {nombre} - Doc:{doc}",
            "cuerpo": f"Migrado de V1.\nCanal: Email\nDoc: {doc}\n---\n{comentario}",
            "estado": estado,
            "nivel_prioridad": prioridad,
            "fecha_recibido": fecha_rec,
            "created_at": fecha_rec,
            "tipo_caso": tipo,
            "fecha_vencimiento": fecha_venc,
            "asignado_a": abogados[rr % len(abogados)],
            "fecha_asignacion": fecha_asig,
            "enviado_at": enviado_at,
            "external_msg_id": ext_id,
            "numero_radicado": radicado,
        })
        rr += 1
    return casos, rr


def process_consolidado(df, abogados, sheet_tag, start_rr=0):
    casos = []
    rr = start_rr
    for _, row in df.iterrows():
        doc_raw = row.get("DOCUMENTO", "")
        if pd.isna(doc_raw):
            continue
        doc = str(int(float(doc_raw))) if isinstance(doc_raw, (int, float)) else clean(doc_raw)
        nombre = clean(row.get("NOMBRE", ""))
        mail = clean(row.get("MAIL", ""))
        tipo_raw = clean(row.get("TIPO DE RECLAMO", "RECLAMO"))
        fecha_rec = parse_date(row.get("FECHA DE INGRESO")) or parse_date(row.get("FECHA DE CARGA"))
        if not fecha_rec:
            continue
        estado = map_estado(row.get("ESTADO", "CERRADO"))
        tipo = map_tipo(tipo_raw)
        prioridad = map_prioridad(row.get("ALERTA", ""))
        comentario = clean(row.get("COMENTARIO INTERNO - GESTION", ""))
        ultima_act = parse_date(row.get("ULTIMA ACTUALIZACION"))
        email = mail if "@" in mail else f"doc_{doc}@historico.recovery.co"
        ext_id = make_external_id(sheet_tag, f"{doc}:{fecha_rec}:{tipo_raw}")
        radicado = f"CON-{fecha_rec.year}-{ext_id[:8].upper()}"
        fecha_asig = fecha_rec + timedelta(days=1)
        fecha_venc = fecha_rec + timedelta(days=PLAZOS_DIAS.get(tipo, 15))
        enviado_at = ultima_act if estado == "CERRADO" and ultima_act else None

        casos.append({
            "cliente_id": RECOVERY_TENANT,
            "email_origen": email,
            "asunto": f"[HISTÓRICO {sheet_tag}] {tipo_raw} - {nombre} - Doc:{doc}",
            "cuerpo": f"Migrado de V1 ({sheet_tag}).\nDoc: {doc}\n---\n{comentario}",
            "estado": estado,
            "nivel_prioridad": prioridad,
            "fecha_recibido": fecha_rec,
            "created_at": fecha_rec,
            "tipo_caso": tipo,
            "fecha_vencimiento": fecha_venc,
            "asignado_a": abogados[rr % len(abogados)],
            "fecha_asignacion": fecha_asig,
            "enviado_at": enviado_at,
            "external_msg_id": ext_id,
            "numero_radicado": radicado,
        })
        rr += 1
    return casos, rr


async def main():
    print(f"[START] Migración histórica Recovery → V2")
    print(f"  Excel: {EXCEL_PATH}")
    print(f"  DB: {DATABASE_URL}")

    conn = await asyncpg.connect(DATABASE_URL)
    abogados = await get_abogados(conn)
    print(f"  Abogados Recovery: {len(abogados)}")
    if not abogados:
        print("ERROR: No se encontraron abogados en el tenant Recovery")
        await conn.close()
        return

    xls = pd.ExcelFile(EXCEL_PATH)
    all_casos = []
    rr = 0

    if "Reclamos" in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name="Reclamos")
        casos = process_reclamos(df, abogados)
        all_casos.extend(casos)
        rr = len(casos)
        print(f"  Reclamos: {len(casos)} casos preparados")

    if "Mails" in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name="Mails")
        casos, rr = process_mails(df, abogados, rr)
        all_casos.extend(casos)
        print(f"  Mails: {len(casos)} casos preparados")

    if "CONSOLIDADO SANTANDER" in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name="CONSOLIDADO SANTANDER")
        casos, rr = process_consolidado(df, abogados, "STDER", rr)
        all_casos.extend(casos)
        print(f"  Consolidado Santander: {len(casos)} casos preparados")

    if "CONSOLIDADO BOGOTA" in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name="CONSOLIDADO BOGOTA")
        casos, rr = process_consolidado(df, abogados, "BOG", rr)
        all_casos.extend(casos)
        print(f"  Consolidado Bogota: {len(casos)} casos preparados")

    print(f"\n  TOTAL: {len(all_casos)} casos a migrar")

    inserted = 0
    skipped = 0
    errors = 0
    for caso in all_casos:
        try:
            result = await insert_caso(conn, caso)
            if result:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {e}")

    print(f"\n[DONE] Insertados: {inserted} | Duplicados: {skipped} | Errores: {errors}")

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM pqrs_casos WHERE cliente_id = $1", RECOVERY_TENANT
    )
    cerrados = await conn.fetchval(
        "SELECT COUNT(*) FROM pqrs_casos WHERE cliente_id = $1 AND estado = 'CERRADO'", RECOVERY_TENANT
    )
    print(f"  Total casos Recovery: {total} (cerrados: {cerrados})")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
