import asyncio
import asyncpg

async def list_users_detailed():
    try:
        conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@localhost:5433/pqrs_v2')
        query = """
        SELECT u.email, u.rol, u.nombre, c.nombre as cliente_nombre, u.cliente_id
        FROM usuarios u
        JOIN clientes_tenant c ON u.cliente_id = c.id
        ORDER BY c.nombre, u.rol;
        """
        rows = await conn.fetch(query)
        print(f"{'CLIENTE':<30} | {'NOMBRE':<20} | {'EMAIL':<40} | {'ROL':<15}")
        print("-" * 110)
        for r in rows:
            print(f"{r['cliente_nombre'][:30]:<30} | {r['nombre'][:20]:<20} | {r['email'][:40]:<40} | {r['rol']:<15}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_users_detailed())
