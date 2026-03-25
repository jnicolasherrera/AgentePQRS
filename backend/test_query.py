import asyncpg
import asyncio
import sys

async def main():
    conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@127.0.0.1:5433/pqrs_v2')
    caso_id = '2820b875-c63a-4923-a54a-11b4ce9533da'
    record = await conn.fetchrow('''SELECT id, cliente_id, email_origen, asunto, estado, nivel_prioridad, fecha_recibido FROM pqrs_casos WHERE id = $1''', caso_id)
    print("Direct string parameter:", record)
    
    import uuid
    caso_uuid = uuid.UUID(caso_id)
    try:
        record2 = await conn.fetchrow('''SELECT id, cliente_id, email_origen, asunto, estado, nivel_prioridad, fecha_recibido FROM pqrs_casos WHERE id = $1''', caso_uuid)
        print("UUID object parameter:", record2)
    except Exception as e:
        print("UUID object parameter failed:", e)

    await conn.close()

asyncio.run(main())
