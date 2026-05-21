import asyncio
import asyncpg
import bcrypt

async def seed_flexfintech():
    print("Iniciando seed de clientes Flexfintech...")
    conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@127.0.0.1:5433/pqrs_v2')
    
    pwd_bytes = 'flex2026!'.encode('utf-8')
    salt = bcrypt.gensalt()
    hash_pw = bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')
    
    tenant_flex = 'f7e8d9c0-b1a2-3456-7890-123456abcdef'
    
    query_tenant = """
    INSERT INTO clientes_tenant (id, nombre, dominio) 
    VALUES ($1, 'Flexfintech Colombia', 'flexfintech.co')
    ON CONFLICT (dominio) DO NOTHING
    """
    await conn.execute(query_tenant, tenant_flex)

    query_user = """
    INSERT INTO usuarios (cliente_id, nombre, email, rol, password_hash) 
    VALUES ($1, $2, $3, 'agente', $4) 
    ON CONFLICT (email) DO UPDATE SET password_hash = $4
    """
    
    await conn.execute(query_user, tenant_flex, 'Micaela', 'micaela@flexfintech.co', hash_pw)
    await conn.execute(query_user, tenant_flex, 'Paula', 'paula@flexfintech.co', hash_pw)
    print("Usuarios Micaela y Paula (Flexfintech) insertados con exito.")
    
    # Agregar correo origen maestro como cliente en la BD o tenant
    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_flexfintech())
