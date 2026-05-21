import asyncio
import json
import datetime
import asyncpg
import redis.asyncio as redis
import os

# URLs para ejecución interna de Docker
DATABASE_URL = "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2"
REDIS_URL = "redis://redis_v2:6379"
TENANT_FLEXFINTECH = "a1b2c3d4-e5f6-7890-1234-56789abcdef0"

from app.services.clasificador import clasificar_texto
import pandas as pd

async def test_classification_flow(remitente, asunto, cuerpo):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        r = redis.from_url(REDIS_URL, decode_responses=True)
        
        print(f"\n--- INICIANDO PRUEBA DE CLASIFICACIÓN V1 EN ARQUITECTURA V2 ---")
        print(f"📧 Remitente: {remitente}")
        print(f"📝 Asunto: {asunto}")
        
        # 1. EJECUTAR EL CEREBRO MIGRADO
        resultado = clasificar_texto(asunto, cuerpo, remitente)
        
        print(f"\n🔍 RESULTADO DE LA IA:")
        print(f"   - Tipo Detectado: {resultado.tipo.value}")
        print(f"   - Prioridad Sugerida: {resultado.prioridad.value}")
        print(f"   - Plazo Legal: {resultado.plazo_dias} días hábiles")
        print(f"   - Cédula Extraída: {resultado.cedula or 'No detectada'}")
        print(f"   - Radicado: {resultado.radicado or 'No detectado'}")
        print(f"   - Confianza: {resultado.confianza * 100}%")
        
        # 2. CALCULAR VENCIMIENTO REAL
        ahora = datetime.datetime.now()
        vencimiento = (pd.Timestamp(ahora) + pd.offsets.CustomBusinessDay(n=resultado.plazo_dias)).to_pydatetime()
        
        # 3. INYECTAR EN LA BASE DE DATOS TRANSACCIONAL
        query_insert = """
        INSERT INTO pqrs_casos (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, tipo_caso, fecha_vencimiento)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        """
        
        db_id = await conn.fetchval(
            query_insert, 
            TENANT_FLEXFINTECH, 
            remitente, 
            asunto, 
            cuerpo[:1000], 
            'ABIERTO', 
            resultado.prioridad.value, 
            ahora, 
            resultado.tipo.value, 
            vencimiento
        )
        
        # 4. DISPARAR EVENTO EN TIEMPO REAL (SSE)
        notificacion = {
            "id": str(db_id),
            "subject": asunto,
            "client": remitente,
            "severity": resultado.prioridad.value,
            "status": "Abierto",
            "source": "Prueba de Fuego V1-V2",
            "date": ahora.strftime("%d/%m/%Y %H:%M"),
            "tipo": resultado.tipo.value,
            "vencimiento": vencimiento.isoformat(),
            "confianza": resultado.confianza,
            "es_juzgado": resultado.es_juzgado
        }
        
        await r.publish("pqrs_stream_v2", json.dumps(notificacion))
        print(f"\n✅ CASO CREADO EXITOSAMENTE: {db_id}")
        print(f"🚀 Notificación enviada al Dashboard en tiempo real.")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error en la prueba: {e}")

if __name__ == "__main__":
    # CASO DE PRUEBA: UNA TUTELA JUDICIAL
    remitente_test = "juzgado05@ramajudicial.gov.co"
    asunto_test = "NOTIFICACIÓN JUDICIAL - ACCIÓN DE TUTELA - RAD: 2024-00150"
    cuerpo_test = """
    Señores FLEXFINTECH,
    El Juzgado 5 admite Acción de Tutela del ciudadano PEDRO PEREZ con CC 1020304050 
    por presunta vulneración al derecho de Habeas Data. Se ordena dar respuesta en 48 horas.
    Radicado del proceso: 2024-00150.
    """
    
    asyncio.run(test_classification_flow(remitente_test, asunto_test, cuerpo_test))
