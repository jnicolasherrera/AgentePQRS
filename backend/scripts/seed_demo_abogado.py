"""Seed: abogado ficticio + casos históricos para demo de rendimiento."""
import asyncio, asyncpg, bcrypt, uuid, os
from datetime import datetime, timezone, timedelta

DEMO_TENANT = "11111111-1111-1111-1111-111111111111"
ABOGADO_ID  = "33333333-3333-3333-3333-333333333333"
ABOGADO_EMAIL = "maria.fernandez@flexpqr.co"
ABOGADO_NOMBRE = "Dra. María Fernández"
ABOGADO_PASS = "Demo2026!"

DB_URL = os.environ.get("WORKER_DB_URL", "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2")

SEED_CASOS = [
    {"tipo": "TUTELA",    "prio": "CRITICA", "estado": "CERRADO",     "dias_atras": 1,  "asunto": "Tutela - Derecho fundamental a la salud - EPS Sanitas", "email": "juzgado3@ramajudicial.gov.co"},
    {"tipo": "TUTELA",    "prio": "CRITICA", "estado": "CONTESTADO",  "dias_atras": 0,  "asunto": "Tutela - Acceso a medicamentos esenciales POS", "email": "juzgado7@ramajudicial.gov.co"},
    {"tipo": "QUEJA",     "prio": "ALTA",    "estado": "CERRADO",     "dias_atras": 3,  "asunto": "Queja por cobro indebido de comisión bancaria", "email": "carlos.gomez@gmail.com"},
    {"tipo": "QUEJA",     "prio": "ALTA",    "estado": "CERRADO",     "dias_atras": 5,  "asunto": "Queja servicio al cliente deficiente sucursal Norte", "email": "ana.martinez@hotmail.com"},
    {"tipo": "RECLAMO",   "prio": "ALTA",    "estado": "EN_PROCESO",  "dias_atras": 1,  "asunto": "Reclamo por débito no autorizado cuenta ahorros", "email": "pedro.lopez@yahoo.com"},
    {"tipo": "RECLAMO",   "prio": "MEDIA",   "estado": "CERRADO",     "dias_atras": 6,  "asunto": "Reclamo error en extracto bancario febrero 2026", "email": "lucia.vargas@outlook.com"},
    {"tipo": "PETICION",  "prio": "MEDIA",   "estado": "CERRADO",     "dias_atras": 4,  "asunto": "Petición certificado de deuda al día crédito hipotecario", "email": "jorge.ramirez@gmail.com"},
    {"tipo": "PETICION",  "prio": "MEDIA",   "estado": "CONTESTADO",  "dias_atras": 2,  "asunto": "Petición paz y salvo obligaciones financieras", "email": "maria.castillo@gmail.com"},
    {"tipo": "SOLICITUD", "prio": "BAJA",    "estado": "CERRADO",     "dias_atras": 7,  "asunto": "Solicitud cambio de plan de tarjeta de crédito", "email": "andres.rojas@gmail.com"},
    {"tipo": "SOLICITUD", "prio": "BAJA",    "estado": "CERRADO",     "dias_atras": 2,  "asunto": "Solicitud actualización datos personales sistema", "email": "diana.herrera@hotmail.com"},
    {"tipo": "TUTELA",    "prio": "CRITICA", "estado": "CERRADO",     "dias_atras": 8,  "asunto": "Tutela - Habeas Data rectificación reporte Datacrédito", "email": "juzgado12@ramajudicial.gov.co"},
    {"tipo": "QUEJA",     "prio": "ALTA",    "estado": "ABIERTO",     "dias_atras": 0,  "asunto": "Queja demora excesiva en desembolso crédito libre inversión", "email": "santiago.mora@gmail.com"},
    {"tipo": "RECLAMO",   "prio": "ALTA",    "estado": "CERRADO",     "dias_atras": 4,  "asunto": "Reclamo cargo no reconocido tarjeta Visa terminación 4521", "email": "valentina.rios@outlook.com"},
    {"tipo": "PETICION",  "prio": "MEDIA",   "estado": "CERRADO",     "dias_atras": 10, "asunto": "Petición copia contrato apertura cuenta corriente", "email": "felipe.torres@yahoo.com"},
    {"tipo": "TUTELA",    "prio": "CRITICA", "estado": "CONTESTADO",  "dias_atras": 1,  "asunto": "Tutela - Mínimo vital pensión alimentaria retenida", "email": "juzgado5@ramajudicial.gov.co"},
]

PLAZOS = {"TUTELA": 2, "QUEJA": 15, "RECLAMO": 15, "PETICION": 15, "SOLICITUD": 10}


async def main():
    conn = await asyncpg.connect(DB_URL)

    pw_hash = bcrypt.hashpw(ABOGADO_PASS.encode(), bcrypt.gensalt()).decode()

    await conn.execute("""
        INSERT INTO usuarios (id, cliente_id, email, password_hash, nombre, rol, is_active)
        VALUES ($1, $2::uuid, $3, $4, $5, 'analista', TRUE)
        ON CONFLICT (email) DO UPDATE SET nombre = EXCLUDED.nombre, password_hash = EXCLUDED.password_hash, rol = 'analista'
    """, uuid.UUID(ABOGADO_ID), uuid.UUID(DEMO_TENANT), ABOGADO_EMAIL, pw_hash, ABOGADO_NOMBRE)
    print(f"Abogado creado/actualizado: {ABOGADO_NOMBRE} ({ABOGADO_EMAIL})")

    now = datetime.now(timezone.utc)
    created = 0

    for caso in SEED_CASOS:
        fecha_recibido = now - timedelta(days=caso["dias_atras"], hours=2)
        fecha_asignacion = fecha_recibido + timedelta(minutes=5)
        fecha_vencimiento = fecha_recibido + timedelta(days=PLAZOS[caso["tipo"]])

        updated_at = fecha_asignacion + timedelta(hours=caso["dias_atras"] * 3 + 1)
        if caso["estado"] in ("CERRADO", "CONTESTADO"):
            updated_at = fecha_asignacion + timedelta(hours=max(caso["dias_atras"], 1) * 2)

        radicado = f"PQRS-2026-DEMO{created:04d}"

        caso_id = await conn.fetchval("""
            INSERT INTO pqrs_casos (
                cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad,
                fecha_recibido, tipo_caso, fecha_vencimiento, asignado_a,
                fecha_asignacion, updated_at, numero_radicado, acuse_enviado,
                borrador_estado, created_at, es_pqrs
            ) VALUES (
                $1::uuid, $2, $3, $4, $5, $6,
                $7, $8, $9, $10::uuid,
                $11, $12, $13, TRUE,
                'PENDIENTE', $7, TRUE
            )
            ON CONFLICT DO NOTHING
            RETURNING id
        """,
            uuid.UUID(DEMO_TENANT), caso["email"], caso["asunto"],
            f"Contenido de prueba para {caso['asunto']}.",
            caso["estado"], caso["prio"],
            fecha_recibido, caso["tipo"], fecha_vencimiento,
            uuid.UUID(ABOGADO_ID),
            fecha_asignacion, updated_at, radicado,
        )

        if caso_id:
            created += 1
            print(f"  Caso {radicado}: {caso['tipo']} | {caso['estado']} | {caso['prio']}")

    print(f"\nTotal: {created} casos seed creados")
    await conn.close()

asyncio.run(main())
