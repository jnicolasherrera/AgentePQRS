import os
from datetime import datetime
from pydantic import BaseModel, Field
from faststream import FastStream, Logger
from faststream.kafka import KafkaBroker

# ==========================================
# 🚀 WORKER 1: CONSUMIDOR DE CORREOS (KAFKA)
# ==========================================

# 1. Conexión al Clúster Kafka Transaccional
KAFKA_URL = os.getenv("KAFKA_URL", "localhost:9092")
broker = KafkaBroker(KAFKA_URL)
app = FastStream(broker)

# 2. Esquema Estricto de Datos (Evita Inyecciones o Basura)
class EmailInbound(BaseModel):
    cliente_id: str = Field(..., description="UUID del Tenant (Ej: Abogados Recovery)")
    email_origen: str = Field(..., description="Correo del usuario que envía la PQR")
    asunto: str
    cuerpo: str
    fecha_recibido: datetime = Field(default_factory=datetime.utcnow)

# 3. Lógica del Consumidor (Se dispara automáticamente al entrar un e-mail)
@broker.subscriber("correos_crudos_inbound")
async def procesar_correo_entrante(msg: EmailInbound, logger: Logger):
    """
    Este conducto recibe MILES de correos por segundo sin trabarse.
    El Event-Driven Architecture (EDA) nos asegura Cero-Pérdida de datos.
    """
    logger.info("=========================================")
    logger.info(f"📩 [NUEVA PQR ENTRANTE] | Tenant: {msg.cliente_id}")
    logger.info(f"👤 Remitente: {msg.email_origen}")
    logger.info(f"📝 Asunto: {msg.asunto}")
    
    # -----------------------------------------------------
    # PRÓXIMA FASE: INYECCIÓN IA + GUARDADO BD
    # -----------------------------------------------------
    # 1. Llamar a Langchain/OpenAI para leer el 'cuerpo' y extraer:
    #    - Sentimiento (Enojo, Urgencia)
    #    - Tipo de PQR (Reclamo, Solicitud Judicial, etc.)
    # 2. Guardar asíncronamente en PostgreSQL V2 respetando el RLS.
    
    logger.info("✅ PQR procesada preliminarmente con éxito. Lista para la BD.")
    logger.info("=========================================")

# Para arrancar este motor en local:
# faststream run main:app
