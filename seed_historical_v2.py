import pandas as pd
import asyncpg
import asyncio
from datetime import datetime
import uuid

# Conexión local V2 (Usamos el puerto de docker-compose)
DATABASE_URL = "postgresql://pqrs_admin:pg_password@127.0.0.1:5433/pqrs_v2"
EXCEL_PATH = "E:\\COLOMBIA\\PQRS_V2\\Consolidado Reclamos.xlsx"
# Tenant oficial de V2 insertado previamente en seed.py
TENANT_UUID = "a1b2c3d4-e5f6-7890-1234-56789abcdef0"

def clean_string(val):
    if pd.isna(val) or val is None:
        return 'SIN_DATO'
    return str(val).strip()

def map_state(estado_legacy):
    """Mapea los estados de Flexfintech a los estados de V2"""
    est = str(estado_legacy).strip().upper()
    if est in ['CERRADO']:
        return 'CERRADO'
    elif est in ['PROCESO', 'REVISION']:
        return 'EN_PROGRESO'
    else:
        return 'ABIERTO' # Casos raros o nuevos (DEFCON)

def clean_date(val):
    """Limpia las fechas corruptas del Excel y forzar un timestamp PG"""
    if pd.isna(val):
        return datetime.now()
    if isinstance(val, str):
        try:
            # Intento de parseo de strings (Ej: "20/05/2021")
            return pd.to_datetime(val, dayfirst=True).to_pydatetime()
        except:
            return datetime.now()
    elif isinstance(val, datetime):
        return val
    return datetime.now()

async def ingest_historical_data():
    conn = await asyncpg.connect(DATABASE_URL)
    print("[START] Conexion a PostgreSQL V2 Establecida.")
    
    print("Leyendo Excel Maestro (Consolidado Reclamos.xlsx)...")
    xls = pd.ExcelFile(EXCEL_PATH)
    
    df_reclamos = pd.read_excel(xls, sheet_name="Reclamos")
    df_mails = pd.read_excel(xls, sheet_name="Mails")
    print(f"Excel en memoria. Reclamos={len(df_reclamos)} | Mails={len(df_mails)}")
    
    # === 2. INGESTA HOJA: RECLAMOS ===
    print("Iniciando migracion de Reclamos...")
    total_reclamos_insertados = 0
    
    # Query preparador RLS/Inyeccion
    query_insert = """
    INSERT INTO pqrs_casos 
    (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, created_at) 
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    """

    for index, row in df_reclamos.iterrows():
        try:
            # En la hoja reclamos, usualmente no hay Email, pero tenemos Documento o TIPO DE RECLAMO
            email_origen = clean_string(row.get('DNI/CEDULA CLIENTE'))
            email_origen = "doc_" + email_origen + "@offline.cliente.co" if email_origen != 'SIN_DATO' else f"anonimo_{uuid.uuid4().hex[:6]}@offline.co"
            
            tipo_reclamo = clean_string(row.get('TIPO DE RECLAMO', 'RECLAMO GENERAL'))
            asunto = f"[HISTORICO RECLAMO] {tipo_reclamo} - Doc: {clean_string(row.get('DNI/CEDULA CLIENTE'))}"
            
            # Cuerpo: Juntamos contacto y comentario interno
            comentario = clean_string(row.get('COMENTARIO INTERNO'))
            datos_contacto = clean_string(row.get('DATO CONTACTO'))
            cuerpo = f"Data Migrada V1.\nTipologia: {tipo_reclamo}.\nContacto Anterior: {datos_contacto}\n---\nComentarios Historicos:\n{comentario}"
            
            estado = map_state(row.get('AVANCE RECLAMO', 'CERRADO'))
            fecha_recibida = clean_date(row.get('FECHA RECLAMO'))
            
            alerta = clean_string(row.get('ALERTA', 'NORMAL')).upper()
            prioridad = 'ALTA' if 'CRÍTICO' in alerta or 'DEFCON' in alerta else ('MEDIA' if 'DEMORADO' in alerta or 'ATENCION' in alerta else 'NORMAL')

            await conn.execute(
                query_insert, 
                TENANT_UUID, 
                email_origen, 
                asunto, 
                cuerpo, 
                estado, 
                prioridad, 
                fecha_recibida,
                fecha_recibida # created_at historico
            )
            total_reclamos_insertados += 1
        except Exception as e:
            pass # Skipping corruped rows silently
            
    print(f"Hoja Reclamos Completada: Se insertaron {total_reclamos_insertados} casos en base de datos PostgreSQL V2.")

    # === 3. INGESTA HOJA: MAILS ===
    print("Iniciando migración de Mails Transaccionales...")
    total_mails_insertados = 0
    
    for index, row in df_mails.iterrows():
        try:
            # Esta hoja SÍ suele tener email
            raw_email = clean_string(row.get('MAIL'))
            email_origen = raw_email if '@' in raw_email else f"doc_{clean_string(row.get('DOCUMENTO'))}@offline.co"
            if email_origen == 'SIN_DATO@offline.co': email_origen = f"anonimo_mail_{uuid.uuid4().hex[:6]}@offline.co"
            
            tipo = clean_string(row.get('TIPO DE RECLAMO', 'CONSULTA GENERAL'))
            nombre = clean_string(row.get('NOMBRE'))
            asunto = f"[HISTORICO TICKET] {tipo} - {nombre}"
            
            cuerpo = f"Data Migrada V1.\nCanal: EMail/Ticket\n---\nGestion Historica:\n{clean_string(row.get('COMENTARIO INTERNO - GESTION'))}"
            estado = map_state(row.get('ESTADO', 'CERRADO'))
            fecha_recibida = clean_date(row.get('FECHA DE INGRESO'))
            
            alerta = clean_string(row.get('ALERTA', 'NORMAL')).upper()
            prioridad = 'ALTA' if 'CRÍTICO' in alerta or estado == 'DEFCON' or tipo == 'DEFCON' else ('MEDIA' if 'DEMORADO' in alerta else 'NORMAL')

            await conn.execute(
                query_insert, 
                TENANT_UUID, 
                email_origen, 
                asunto, 
                cuerpo, 
                estado, 
                prioridad, 
                fecha_recibida,
                fecha_recibida # created_at historico
            )
            total_mails_insertados += 1
        except Exception as e:
            pass
            
    print(f"Hoja Mails Completada: Se insertaron {total_mails_insertados} tickets en base de datos PostgreSQL V2.")

    print(f"\n[DONE] MIGRACION MASIVA EXITOSA.")
    print(f"TOTAL CASOS MIGRADOS A V2: {total_reclamos_insertados + total_mails_insertados}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(ingest_historical_data())
