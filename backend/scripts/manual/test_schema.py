import asyncpg
import asyncio

async def main():
    conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@127.0.0.1:5433/pqrs_v2')
    res = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'pqrs_casos'")
    for r in res:
        print(f"{r['column_name']} ({r['data_type']})")
    await conn.close()

asyncio.run(main())
