import asyncio
import json
import datetime
import uuid
import asyncpg
import redis.asyncio as redis

DATABASE_URL = "postgresql://pqrs_admin:pg_password@127.0.0.1:5433/pqrs_v2"
REDIS_URL = "redis://localhost:6379"
TENANT_FLEXFINTECH = "a1b2c3d4-e5f6-7890-1234-56789abcdef0"

async def dispatch_demo_case(tipo="TUTELA", id_doc="1143246256"):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        r = redis.from_url(REDIS_URL, decode_responses=True)
        
        # 1. Definir Data Fake según el tipo
        ahora = datetime.datetime.now()
        
        if tipo == "TUTELA":
            email = "JUZGADO01CIVIL@RAMAJUDICIAL.GOV.CO"
            asunto = f"ACCION DE TUTELA - Doc: {id_doc} - URGENTE"
            cuerpo = "El presente juzgado notifica la acción de tutela interpuesta por el titular para obtener respuesta inmediata a derecho de petición no atendido. Plazo de 48 hrs."
            prioridad = "CRITICA"
            vencimiento = ahora + datetime.timedelta(days=2)
            c_cliente = "Juzgado 01"
        else: # DERECHO DE PETICION
            email = "cliente.molesto@gmail.com"
            asunto = f"DERECHO DE PETICION - SOLICITUD DE HISTORIAL PAGOS - Doc: {id_doc}"
            cuerpo = "Por medio de la presente, solicito en el marco del derecho de petición, copia de mi historial de pagos y soporte de cesión dado que requiero validar reportes en centrales."
            prioridad = "NORMAL"
            vencimiento = ahora + datetime.timedelta(days=15)
            c_cliente = email
            
        print(f"🪄 Generando Caso Simulado: {tipo} ({id_doc})")
        
        # 2. Inserción en Postgres
        query_insert = """
        INSERT INTO pqrs_casos (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, tipo_caso, fecha_vencimiento)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        """
        
        db_id = await conn.fetchval(
            query_insert, TENANT_FLEXFINTECH, email, asunto, cuerpo, 'ABIERTO', prioridad, ahora, tipo, vencimiento
        )
        
        # 3. Notificación a Redis (SSE para Frontend)
        notificacion_redis = {
            "id": str(db_id),
            "subject": asunto,
            "client": c_cliente,
            "severity": prioridad,
            "status": "Abierto",
            "source": "TUTELA - Juzgado" if tipo == "TUTELA" else "PQR - Flexfintech",
            "date": ahora.strftime("%d/%m/%Y %H:%M"),
            "tipo": tipo,
            "vencimiento": vencimiento.isoformat()
        }
        
        await r.publish("pqrs_stream_v2", json.dumps(notificacion_redis))
        
        print(f"✅ ¡BUM! Inyectado en BD y disparado evento SSE al Tablero.")
        
        await conn.close()
        
    except Exception as e:
        print(f"Error (Docker posiblemente apagado?): {e}")

if __name__ == "__main__":
    print("---------------------------------------")
    print("SIMULADOR EN VIVO PARA DEMO FLEXFINTECH")
    print("---------------------------------------")
    print("1: Disparar TUTELA JUDICIAL")
    print("2: Disparar DERECHO DE PETICIÓN")
    print("---------------------------------------")
    opcion = input("Elige la demo a ejecutar (1/2): ")
    
    if opcion == "1":
        asyncio.run(dispatch_demo_case("TUTELA", "1143246256"))
    elif opcion == "2":
        asyncio.run(dispatch_demo_case("DERECHO_PETICION", "1110531761"))
    else:
        print("Opción inválida.")
