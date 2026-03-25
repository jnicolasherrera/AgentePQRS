import asyncio
import asyncpg

async def get_clients():
    conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@localhost:5433/pqrs_v2')
    rows = await conn.fetch('SELECT id, nombre FROM clientes_tenant')
    for r in rows:
        print(f"ID: {r['id']} - Name: {r['nombre']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(get_clients())
