import asyncio
import asyncpg
import bcrypt

async def seed_user():
    print("Iniciando seed de base de datos...")
    conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2')
    
    pwd_bytes = 'superpassword123'.encode('utf-8')
    salt = bcrypt.gensalt()
    hash_pw = bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')
    
    query_tenant = """
    INSERT INTO clientes_tenant (id, nombre, dominio) 
    VALUES ('a1b2c3d4-e5f6-7890-1234-56789abcdef0', 'Organizacion Default V2', 'oficina.local')
    ON CONFLICT (dominio) DO NOTHING
    """
    await conn.execute(query_tenant)

    # Insertar el que usas en la captura para que entres directo
    query_user_agente = """
    INSERT INTO usuarios (id, cliente_id, nombre, email, rol, password_hash) 
    VALUES ('c3d4e5f6-a7b8-9012-3456-7890abcdef02', 'a1b2c3d4-e5f6-7890-1234-56789abcdef0', 'Admin Flex', 'admin@empresademo.com', 'admin_ti', $1) 
    ON CONFLICT (email) DO UPDATE SET password_hash = $1
    """
    await conn.execute(query_user_flex, hash_pw)
    
    print(f"Usuarios actualizados. Password para todos: 'superpassword123'")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_user())
