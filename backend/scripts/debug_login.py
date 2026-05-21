import asyncio
import asyncpg
from bcrypt import checkpw

async def verify():
    try:
        conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@localhost:5433/pqrs_v2')
        email = 'nicolas.herrera@empresademo.com'
        password = 'Armando1121$$!!'
        
        row = await conn.fetchrow('SELECT password_hash, rol FROM usuarios WHERE email = $1', email)
        
        if row:
            print(f"Usuario encontrado: {email}")
            print(f"Rol: {row['rol']}")
            print(f"Hash en BD: {row['password_hash']}")
            
            is_match = checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8'))
            print(f"¿Password coincide?: {is_match}")
        else:
            print(f"Usuario {email} NO encontrado en la base de datos.")
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
