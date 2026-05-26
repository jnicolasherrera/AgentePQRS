import asyncio
import asyncpg
import bcrypt

async def cleanup_database():
    try:
        conn = await asyncpg.connect('postgresql://pqrs_admin:pg_password@localhost:5434/pqrs_v2')
        
        # 1. Definir los IDs de los Tenants que se quedan
        FLEX_ID = 'f7e8d9c0-b1a2-3456-7890-123456abcdef'
        RECOVERY_ID = 'effca814-b0b5-4329-96be-186c0333ad4b'
        
        print("Iniciando Limpieza Maestro de Usuarios y Clientes...")

        # 2. Borrar todos los usuarios y clientes excepto los requeridos
        # Primero usuarios que no esten en la lista blanca
        whitelist_emails = [
            'nicolas.herrera@empresademo.com',
            'micaela@empresademo.co',
            'paula.tolaba@empresademo.co',
            'Abogadojunior5@abogadosrecovery.com'
        ]
        
        await conn.execute("DELETE FROM usuarios WHERE email NOT IN ($1, $2, $3, $4)", *whitelist_emails)
        await conn.execute("DELETE FROM clientes_tenant WHERE id NOT IN ($1, $2)", FLEX_ID, RECOVERY_ID)
        
        # 3. Asegurar que los Tenants tengan los nombres correctos
        await conn.execute("UPDATE clientes_tenant SET nombre = 'EmpresaDemo', dominio = 'empresademo.co' WHERE id = $1", FLEX_ID)
        await conn.execute("UPDATE clientes_tenant SET nombre = 'Abogados Recovery', dominio = 'abogadosrecovery.com' WHERE id = $1", RECOVERY_ID)

        # 4. Configurar/Actualizar usuarios específicos
        password_default = 'Armando2026!'
        hash_pw = bcrypt.hashpw(password_default.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # (cliente_id, nombre, email, rol, debe_cambiar_password)
        users_to_ensure = [
            (FLEX_ID, 'Nicolas Herrera', 'nicolas.herrera@empresademo.com', 'super_admin', False),
            (FLEX_ID, 'Micaela Guerra', 'micaela@empresademo.co', 'admin', True),
            (FLEX_ID, 'Paula Tolaba', 'paula.tolaba@empresademo.co', 'admin', True),
            (RECOVERY_ID, 'Admin Recovery', 'admin@abogadosrecovery.com', 'admin', True),
            (RECOVERY_ID, 'Analista Junior 5', 'Abogadojunior5@abogadosrecovery.com', 'analista', True)
        ]

        for cid, name, email, role, force_change in users_to_ensure:
            await conn.execute("""
                INSERT INTO usuarios (cliente_id, nombre, email, rol, password_hash, debe_cambiar_password)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (email) DO UPDATE SET
                    cliente_id = EXCLUDED.cliente_id,
                    nombre = EXCLUDED.nombre,
                    rol = EXCLUDED.rol,
                    password_hash = EXCLUDED.password_hash,
                    debe_cambiar_password = EXCLUDED.debe_cambiar_password
            """, cid, name, email, role, hash_pw, force_change)

        print("--- LIMPIEZA COMPLETADA ---")
        
        # 5. Mostrar resultado final
        rows = await conn.fetch("""
            SELECT c.nombre as cliente, u.nombre, u.email, u.rol, u.debe_cambiar_password
            FROM usuarios u 
            JOIN clientes_tenant c ON u.cliente_id = c.id 
            ORDER BY cliente, u.rol
        """)
        
        print(f"\n{'CLIENTE':<20} | {'NOMBRE':<20} | {'EMAIL':<35} | {'ROL':<12} | {'CHANGE PWD'}")
        print("-" * 110)
        for r in rows:
             print(f"{r['cliente']:<20} | {r['nombre']:<20} | {r['email']:<35} | {r['rol']:<12} | {r['debe_cambiar_password']}")

        print("\nNOTA: La contraseña para todos los usuarios (excepto Nicolas si ya la tenia) se ha reseteado a: Armando2026!")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_database())
