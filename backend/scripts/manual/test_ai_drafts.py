import asyncio
from app.services.ai_engine import redactar_borrador_legal

async def test_draft():
    # Caso 1: Abogados Recovery - Paz y Salvo
    caso_recovery = {
        "cliente_id": "effca814-b0b5-4329-96be-186c0333ad4b",
        "asunto": "Solicitud de PAZ Y SALVO mi deuda",
        "cuerpo": "Hola, necesito mi paz y salvo de la deuda con Rapicredit.",
        "tipo_caso": "DERECHO_PETICION"
    }
    
    draft = await redactar_borrador_legal(caso_recovery)
    print("\n--- TEST ABOGADOS RECOVERY (PAZ Y SALVO) ---")
    print(draft)
    
    # Caso 2: Abogados Recovery - Débito
    caso_debito = {
        "cliente_id": "effca814-b0b5-4329-96be-186c0333ad4b",
        "asunto": "Reclamo por DEBITOS AUTOMATICOS no autorizados",
        "cuerpo": "Me hicieron un descuento sin permiso.",
        "tipo_caso": "DERECHO_PETICION"
    }
    
    draft_debito = await redactar_borrador_legal(caso_debito)
    print("\n--- TEST ABOGADOS RECOVERY (DEBITOS) ---")
    print(draft_debito)

    # Caso 3: EmpresaDemo (Default)
    caso_agente = {
        "cliente_id": "f7e8d9c0-b1a2-3456-7890-123456abcdef",
        "asunto": "Consulta General",
        "cuerpo": "Quiero saber el estado de mi solicitud.",
        "tipo_caso": "DERECHO_PETICION"
    }
    
    draft_agente = await redactar_borrador_legal(caso_flex)
    print("\n--- TEST FLEXFINTECH (DEFAULT) ---")
    print(draft_flex)

if __name__ == "__main__":
    asyncio.run(test_draft())
