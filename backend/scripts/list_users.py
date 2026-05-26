import asyncio
import asyncpg

async def list_users():
    conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@localhost:5433/pqrs_v2')
    rows = await conn.fetch('SELECT email, rol FROM usuarios')
    for r in rows:
        print(f"Email: {r['email']} - Rol: {r['rol']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(list_users())
