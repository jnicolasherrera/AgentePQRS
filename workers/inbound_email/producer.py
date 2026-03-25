import asyncio
from datetime import datetime
from faststream.kafka import KafkaBroker

# Este es nuestro "Emulador de Correos" (Simula a Gmail o Outlook enviándonos un email)
async def enviar_correo_falso():
    # Nos conectamos al mismo conducto (Broker) en el puerto 9092
    broker = KafkaBroker("localhost:9092")
    await broker.connect()

    # Simulamos el cuerpo de un correo JSON limpio que respeta nuestro modelo Pydantic
    correo_simulado = {
        "cliente_id": "a1b2c3d4-e5f6-7890-1234-56789abcdef0", # UUID ficticio
        "email_origen": "cliente.furioso@empresa.com",
        "asunto": "URGENTE: Mi pago no se refleja",
        "cuerpo": "Hola, hice una transferencia ayer por $5,000 y en el panel aparece como impaga. ¡Exijo una solución o los demandaré!",
        "fecha_recibido": datetime.utcnow().isoformat()
    }

    print("🚀 Disparando correo hacia Kafka...")
    
    # Lo lanzamos al "tópico" (tubo) que nuestro Worker está escuchando
    await broker.publish(
        message=correo_simulado,
        topic="correos_crudos_inbound"
    )

    print("✅ ¡Correo disparado con éxito a la velocidad de la luz!")
    await broker.close()

if __name__ == "__main__":
    asyncio.run(enviar_correo_falso())
