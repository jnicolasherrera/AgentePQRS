import asyncio
import json
import random
import redis.asyncio as redis
from datetime import datetime

REDIS_URL = "redis://localhost:6379"

async def mock_kafka_to_redis_worker():
    print("⏳ Iniciando Simulador Worker de Kafka => Redis")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    
    count = 1
    while True:
        await asyncio.sleep(random.randint(3, 8)) # PQR aleatoria cada 3-8 segs
        
        new_pqr = {
            "id": f"PQR-KAFKA-{count:04d}",
            "subject": f"Reporte automático vía Kafka/Webhook #{count}",
            "client": f"Humano Anónimo {random.randint(100,999)}",
            "severity": random.choice(["Alta", "Baja", "Crítica"]),
            "status": "Abierto",
            "source": random.choice(["Kafka (Email)", "Kafka (App)", "Kafka (Social)"]),
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        
        # Publicamos en el canal (PubSub puente)
        await r.publish("pqrs_stream_v2", json.dumps(new_pqr))
        print(f"🚀 [KAFKA->REDIS] Inyectada nueva PQR viva en el Stream: {new_pqr['id']}")
        count += 1

if __name__ == "__main__":
    try:
        asyncio.run(mock_kafka_to_redis_worker())
    except KeyboardInterrupt:
        print("Apagando...")
