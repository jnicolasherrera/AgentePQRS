import asyncio
import asyncpg
import bcrypt

async def create_superuser():
    print("Creando Superusuario V2...")
    # Cambia el puerto si es necesario (el docker-compose suele usar 5433 para evitar conflictos)
    try:
        conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@localhost:5433/pqrs_v2')
        
        # Hash para 'Armando2026!'
        pwd = 'Armando2026!'.encode('utf-8')
        hash_pw = bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8')
        
        # Asegurarnos de usar un cliente_id válido (usaremos el de Flexfintech como base)
        tenant_id = 'f7e8d9c0-b1a2-3456-7890-123456abcdef'
        
        query = """
        INSERT INTO usuarios (cliente_id, nombre, email, rol, password_hash) 
        VALUES ($1, $2, $3, $4, $5) 
        ON CONFLICT (email) DO UPDATE SET 
            rol = EXCLUDED.rol, 
            password_hash = EXCLUDED.password_hash,
            nombre = EXCLUDED.nombre
        """
        
        await conn.execute(query, tenant_id, 'Nicolas Herrera', 'nicolas.herrera@flexfintech.com', 'super_admin', hash_pw)
        print("\n--- Superusuario Creado / Actualizado ---")
        print(f"Email: nicolas.herrera@flexfintech.com")
        print(f"Password: Armando2026!")
        print(f"Rol: super_admin")
        
        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(create_superuser())
