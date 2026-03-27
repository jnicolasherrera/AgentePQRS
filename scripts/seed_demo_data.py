"""
Seed de datos demo para FlexPQR — Dashboard comercial.
Ejecutar: docker exec pqrs_v2_backend python3 /app/scripts/seed_demo_data.py
o desde el host: python3 scripts/seed_demo_data.py

Idempotente: ON CONFLICT DO NOTHING para usuarios,
verifica existencia por (email_origen, asunto) para casos.
"""
import asyncio
import asyncpg
import bcrypt
import uuid
import os
import json
from datetime import datetime, timezone, timedelta

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    os.environ.get("WORKER_DB_URL", "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2"),
)

DEMO_TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")

# ── Usuarios demo ────────────────────────────────────────────────────────────

def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

DEMO_PASSWORD = hash_pw("Demo2026!")

USERS = [
    {"id": "aaaa0001-0001-0001-0001-000000000001", "nombre": "Laura Martínez",    "email": "laura.martinez@demo.flexpqr.com",    "rol": "analista"},
    {"id": "aaaa0002-0002-0002-0002-000000000002", "nombre": "Carlos Ospina",      "email": "carlos.ospina@demo.flexpqr.com",      "rol": "analista"},
    {"id": "aaaa0003-0003-0003-0003-000000000003", "nombre": "Valentina Torres",   "email": "valentina.torres@demo.flexpqr.com",   "rol": "analista"},
    {"id": "aaaa0004-0004-0004-0004-000000000004", "nombre": "Andrés Molina",      "email": "andres.molina@demo.flexpqr.com",      "rol": "analista"},
    {"id": "aaaa0005-0005-0005-0005-000000000005", "nombre": "Sandra Ríos",        "email": "sandra.rios@demo.flexpqr.com",        "rol": "coordinador"},
]

ANALYST_IDS = [uuid.UUID(u["id"]) for u in USERS if u["rol"] == "analista"]

# ── Casos demo ───────────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc)

def ago(days: int) -> datetime:
    return NOW - timedelta(days=days)

def venc(fecha_recibido: datetime, dias_habiles: int) -> datetime:
    return fecha_recibido + timedelta(days=dias_habiles)

CASES = [
    # ── TUTELAS ──
    {
        "email_origen": "ciudadano1@gmail.com",
        "asunto": "Acción de tutela - Derecho fundamental a la salud y mínimo vital",
        "cuerpo": "Me dirijo a ustedes para interponer acción de tutela contra su entidad por vulneración de mi derecho fundamental al mínimo vital. Llevan 3 meses sin desembolsar mi crédito aprobado y mi familia no tiene con qué pagar los servicios básicos. Adjunto documentos que prueban la aprobación.",
        "tipo_caso": "TUTELA", "estado": "ABIERTO", "nivel_prioridad": "CRITICA",
        "fecha_recibido": ago(12), "fecha_vencimiento": venc(ago(12), 2),
        "analista_idx": 0, "borrador": None,
    },
    {
        "email_origen": "hernandez.mario@hotmail.com",
        "asunto": "Tutela por vulneración derecho petición - Sin respuesta hace 20 días",
        "cuerpo": "Presento tutela por cuanto esta entidad no ha dado respuesta a mi derecho de petición radicado el 5 de febrero. Han pasado más de 15 días hábiles sin respuesta alguna, vulnerando mis derechos fundamentales.",
        "tipo_caso": "TUTELA", "estado": "EN_PROCESO", "nivel_prioridad": "CRITICA",
        "fecha_recibido": ago(11), "fecha_vencimiento": venc(ago(11), 2),
        "analista_idx": 1,
        "borrador": """Bogotá D.C.

Señor
MARIO HERNÁNDEZ
Correo electrónico: hernandez.mario@hotmail.com

Asunto: Respuesta a Acción de Tutela — Vulneración derecho de petición

Cordial saludo,

En atención a la acción de tutela interpuesta por usted, en la cual manifiesta no haber recibido respuesta a su derecho de petición, nos permitimos informar lo siguiente:

RECONOCIMIENTO: Verificados nuestros registros, evidenciamos que efectivamente su derecho de petición no fue respondido dentro del término legal de 15 días hábiles, lo cual constituye una vulneración a su derecho fundamental.

ACCIONES CORRECTIVAS:
1. Se ha dado respuesta inmediata a su derecho de petición original (anexa a esta comunicación).
2. Se ha iniciado proceso disciplinario interno para determinar las causas del incumplimiento.
3. Se implementarán alertas automáticas para evitar futuros vencimientos.

Ofrecemos nuestras más sinceras disculpas por los inconvenientes causados.

Cordialmente,
Área Jurídica
Demo FlexPQR""",
    },
    {
        "email_origen": "pilar.gonzalez@gmail.com",
        "asunto": "Acción de tutela - Derecho de petición sobre certificado de paz y salvo",
        "cuerpo": "Solicito amparo de mi derecho fundamental de petición. Requiero con urgencia certificado de paz y salvo para proceso de vivienda VIS pero su entidad no ha respondido en 10 días hábiles.",
        "tipo_caso": "TUTELA", "estado": "CONTESTADO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(8), "fecha_vencimiento": venc(ago(8), 2),
        "analista_idx": 2, "borrador": "APROBADO",
    },
    # ── PETICIONES ──
    {
        "email_origen": "rodrigo.pena@empresa.com.co",
        "asunto": "Derecho de petición - Solicitud extracto cuenta corriente últimos 12 meses",
        "cuerpo": "De manera respetuosa me dirijo a ustedes para solicitar extractos de mi cuenta corriente No. 4521-8834 correspondientes a los últimos 12 meses, necesarios para declaración de renta.",
        "tipo_caso": "PETICION", "estado": "ABIERTO", "nivel_prioridad": "NORMAL",
        "fecha_recibido": ago(3), "fecha_vencimiento": venc(ago(3), 15),
        "analista_idx": 3, "borrador": None,
    },
    {
        "email_origen": "amparo.vargas@gmail.com",
        "asunto": "Derecho de petición - Información sobre modificación unilateral de tasa",
        "cuerpo": "Solicito información detallada sobre el incremento de la tasa de interés de mi crédito de consumo del 18% al 24% EA sin previo aviso, lo cual considero contrario a las condiciones inicialmente pactadas.",
        "tipo_caso": "PETICION", "estado": "EN_PROCESO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(5), "fecha_vencimiento": venc(ago(5), 15),
        "analista_idx": 0,
        "borrador": """Bogotá D.C.

Señora
AMPARO VARGAS
Correo electrónico: amparo.vargas@gmail.com

Asunto: Respuesta a Derecho de Petición — Modificación de tasa de interés

Cordial saludo,

Damos respuesta formal a su derecho de petición en el cual solicita información sobre la modificación de la tasa de interés de su crédito de consumo.

RECONOCIMIENTO: Hemos recibido y registrado debidamente su solicitud. Identificamos que su crédito de consumo presentó un ajuste en la tasa de interés del 18% al 24% EA.

FUNDAMENTO LEGAL: De conformidad con el Estatuto Orgánico del Sistema Financiero y las circulares de la Superintendencia Financiera de Colombia, las entidades financieras deben informar con al menos 30 días de antelación cualquier modificación en las condiciones del crédito.

RESPUESTA: Verificada su cuenta, encontramos que el ajuste de tasa se realizó conforme a la cláusula 8.3 del contrato de crédito suscrito, la cual permite revisiones periódicas atadas al IBR. No obstante, procedemos a verificar si se cumplió con el deber de notificación previa.

En caso de encontrar alguna irregularidad en el proceso de notificación, procederemos con el ajuste correspondiente y la compensación a que haya lugar.

Cordialmente,
Área de Atención al Cliente
Demo FlexPQR""",
    },
    {
        "email_origen": "familia.torres@gmail.com",
        "asunto": "Petición - Certificado de tradición y libertad crédito hipotecario",
        "cuerpo": "Solicito certificado de tradición y libertad del inmueble dado en garantía hipotecaria, requiero para proceso notarial de compraventa.",
        "tipo_caso": "PETICION", "estado": "CERRADO", "nivel_prioridad": "NORMAL",
        "fecha_recibido": ago(15), "fecha_vencimiento": venc(ago(15), 15),
        "analista_idx": 1, "borrador": "APROBADO",
    },
    {
        "email_origen": "nelson.suarez@hotmail.com",
        "asunto": "Derecho de petición - Reliquidación crédito por pago en exceso",
        "cuerpo": "Solicito reliquidación de mi crédito personal No. 88234 por cuanto realicé abono extraordinario de $5.000.000 en enero y no se ve reflejado en la reducción de cuotas restantes.",
        "tipo_caso": "PETICION", "estado": "CONTESTADO", "nivel_prioridad": "NORMAL",
        "fecha_recibido": ago(10), "fecha_vencimiento": venc(ago(10), 15),
        "analista_idx": 2, "borrador": "APROBADO",
    },
    {
        "email_origen": "diana.castro@gmail.com",
        "asunto": "Derecho de petición - Bloqueo injustificado cuenta de ahorros",
        "cuerpo": "Mi cuenta de ahorros No. 7823-4421 fue bloqueada hace 18 días sin ninguna notificación previa. Tengo mi nómina depositada ahí y no puedo acceder a mis recursos. Solicito explicación inmediata y desbloqueo urgente.",
        "tipo_caso": "PETICION", "estado": "ABIERTO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(16), "fecha_vencimiento": venc(ago(16), 15),
        "analista_idx": 3, "borrador": None,
    },
    # ── QUEJAS ──
    {
        "email_origen": "juan.medina.co@gmail.com",
        "asunto": "Queja formal - Cobro de cuota de manejo no autorizada tarjeta crédito",
        "cuerpo": "Presento queja formal por cobro de cuota de manejo de $28.500 en mi tarjeta de crédito Visa Gold. Al momento de la vinculación se me informó que dicha cuota estaba exonerada por el tipo de cuenta. Exijo reversión inmediata.",
        "tipo_caso": "QUEJA", "estado": "ABIERTO", "nivel_prioridad": "NORMAL",
        "fecha_recibido": ago(2), "fecha_vencimiento": venc(ago(2), 8),
        "analista_idx": 0, "borrador": None,
    },
    {
        "email_origen": "beatriz.londono@gmail.com",
        "asunto": "Queja - Mal servicio sucursal Chapinero, tiempo de espera 3 horas",
        "cuerpo": "El día 15 de marzo visité la sucursal Chapinero y tuve que esperar 3 horas para ser atendida. El personal fue descortés y no resolvió mi solicitud. Esto afecta mi confianza en la entidad.",
        "tipo_caso": "QUEJA", "estado": "EN_PROCESO", "nivel_prioridad": "NORMAL",
        "fecha_recibido": ago(7), "fecha_vencimiento": venc(ago(7), 8),
        "analista_idx": 1,
        "borrador": """Bogotá D.C.

Señora
BEATRIZ LONDOÑO
Correo electrónico: beatriz.londono@gmail.com

Asunto: Respuesta a Queja — Servicio en sucursal Chapinero

Cordial saludo,

Hemos recibido su queja respecto al servicio prestado en nuestra sucursal Chapinero y lamentamos profundamente la experiencia que tuvo.

ACCIONES TOMADAS:
1. Se revisaron las cámaras y registros del día indicado, confirmando tiempos de espera superiores a los estándares de servicio.
2. Se realizó retroalimentación al equipo de la sucursal sobre protocolos de atención.
3. Se ha reforzado el personal en horarios de alta demanda.

Valoramos su confianza y nos comprometemos a mejorar continuamente la calidad de nuestro servicio.

Cordialmente,
Dirección de Servicio al Cliente
Demo FlexPQR""",
    },
    {
        "email_origen": "patricia.mora@empresa.com",
        "asunto": "Queja - Débito automático no autorizado servicio seguro vida",
        "cuerpo": "Desde hace 4 meses aparece un débito mensual de $45.000 por concepto de seguro de vida que nunca autoricé. Solicito cancelación inmediata y reembolso de los valores cobrados indebidamente.",
        "tipo_caso": "QUEJA", "estado": "CONTESTADO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(12), "fecha_vencimiento": venc(ago(12), 8),
        "analista_idx": 2, "borrador": "APROBADO",
    },
    {
        "email_origen": "camilo.reyes@gmail.com",
        "asunto": "Queja - Error en reporte central de riesgo afecta solicitud vivienda",
        "cuerpo": "Aparezco reportado en DataCrédito con una deuda de $1.200.000 que ya fue pagada hace 6 meses. Este reporte erróneo me impidió acceder a crédito de vivienda. Adjunto paz y salvo.",
        "tipo_caso": "QUEJA", "estado": "CERRADO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(20), "fecha_vencimiento": venc(ago(20), 8),
        "analista_idx": 3, "borrador": "APROBADO",
    },
    # ── RECLAMOS ──
    {
        "email_origen": "exportaciones.villa@gmail.com",
        "asunto": "Reclamo - Transferencia internacional no acreditada USD 2.500",
        "cuerpo": "El 10 de marzo realicé transferencia internacional por USD 2.500 hacia cuenta en España. A la fecha el beneficiario no ha recibido los fondos y su banco indica que nunca llegaron. Solicito investigación y devolución.",
        "tipo_caso": "RECLAMO", "estado": "ABIERTO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(4), "fecha_vencimiento": venc(ago(4), 15),
        "analista_idx": 0, "borrador": None,
    },
    {
        "email_origen": "lucia.herrera.bog@gmail.com",
        "asunto": "Reclamo - Doble cobro cuota crédito mes de febrero",
        "cuerpo": "En el mes de febrero se realizaron DOS débitos de $850.000 correspondientes a mi crédito de vehículo. El extracto muestra claramente el doble cobro los días 5 y 7 de febrero. Solicito reembolso del valor cobrado en exceso más intereses.",
        "tipo_caso": "RECLAMO", "estado": "EN_PROCESO", "nivel_prioridad": "ALTA",
        "fecha_recibido": ago(6), "fecha_vencimiento": venc(ago(6), 15),
        "analista_idx": 1,
        "borrador": """Bogotá D.C.

Señora
LUCÍA HERRERA
Correo electrónico: lucia.herrera.bog@gmail.com

Asunto: Respuesta a Reclamo — Doble cobro cuota crédito vehículo

Cordial saludo,

Acusamos recibo de su reclamo en el que reporta un doble débito por $850.000 en su crédito de vehículo durante el mes de febrero.

VERIFICACIÓN: Revisados los movimientos de su cuenta, confirmamos que efectivamente se realizaron dos débitos los días 5 y 7 de febrero por el mismo concepto, lo cual constituye un cobro indebido.

SOLUCIÓN: Hemos procedido a realizar la reversión del cobro duplicado por valor de $850.000. Adicionalmente, se abonarán los intereses correspondientes calculados a la tasa de mora vigente por los días transcurridos.

El reembolso se verá reflejado en su cuenta dentro de los próximos 3 días hábiles.

Cordialmente,
Área de Reclamos
Demo FlexPQR""",
    },
    {
        "email_origen": "mauricio.jimenez@hotmail.com",
        "asunto": "Reclamo - Seguro deudores cobrado sin autorización en crédito libre inversión",
        "cuerpo": "Al desembolso de mi crédito de libre inversión por $15.000.000 se descontaron $890.000 por concepto de seguro deudores sin que yo lo autorizara expresamente. Solicito reembolso inmediato.",
        "tipo_caso": "RECLAMO", "estado": "CONTESTADO", "nivel_prioridad": "NORMAL",
        "fecha_recibido": ago(9), "fecha_vencimiento": venc(ago(9), 15),
        "analista_idx": 2, "borrador": "APROBADO",
    },
    # ── SOLICITUD ──
    {
        "email_origen": "roberto.pardo@gmail.com",
        "asunto": "Solicitud refinanciación crédito - Dificultades económicas",
        "cuerpo": "Solicito refinanciación de mi crédito personal No. 55821 por dificultades económicas. Puedo continuar pagando pero necesito reducir la cuota mensual de $1.200.000 a aproximadamente $800.000 ampliando el plazo.",
        "tipo_caso": "SOLICITUD", "estado": "EN_PROCESO", "nivel_prioridad": "MEDIA",
        "fecha_recibido": ago(5), "fecha_vencimiento": venc(ago(5), 10),
        "analista_idx": 3,
        "borrador": """Bogotá D.C.

Señor
ROBERTO PARDO
Correo electrónico: roberto.pardo@gmail.com

Asunto: Respuesta a Solicitud de Refinanciación — Crédito Personal No. 55821

Cordial saludo,

En atención a su solicitud de refinanciación, le informamos que hemos evaluado su caso y tenemos las siguientes opciones disponibles:

OPCIÓN A: Ampliación de plazo de 36 a 60 meses. Cuota estimada: $780.000/mes.
OPCIÓN B: Período de gracia de 3 meses con extensión de plazo a 48 meses. Cuota estimada: $850.000/mes.

Para formalizar cualquiera de las opciones, requerimos:
1. Certificación laboral vigente
2. Últimos 3 desprendibles de nómina
3. Declaración de renta (si aplica)

Quedamos atentos a su decisión.

Cordialmente,
Área de Cartera
Demo FlexPQR""",
    },
    # ── SUGERENCIAS ──
    {
        "email_origen": "tech.usuario@gmail.com",
        "asunto": "Sugerencia - Implementar pagos PSE desde app móvil",
        "cuerpo": "Sugiero habilitar la opción de pago de créditos mediante PSE directamente desde la aplicación móvil. Actualmente solo está disponible en la web y muchos clientes usamos exclusivamente el celular.",
        "tipo_caso": "SOLICITUD", "estado": "ABIERTO", "nivel_prioridad": "BAJA",
        "fecha_recibido": ago(1), "fecha_vencimiento": venc(ago(1), 10),
        "analista_idx": 0, "borrador": None,
    },
    {
        "email_origen": "ximena.cardona@gmail.com",
        "asunto": "Sugerencia - Ampliar horario atención telefónica hasta las 8pm",
        "cuerpo": "Propongo ampliar el horario de atención de la línea telefónica hasta las 8:00 pm. Muchos clientes trabajamos en horario de oficina y es difícil llamar antes de las 6:00 pm.",
        "tipo_caso": "SOLICITUD", "estado": "CERRADO", "nivel_prioridad": "BAJA",
        "fecha_recibido": ago(18), "fecha_vencimiento": venc(ago(18), 10),
        "analista_idx": 1, "borrador": "APROBADO",
    },
]


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    print(f"Conectado a: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")

    # ── 1. Usuarios ──────────────────────────────────────────────────────────
    users_created = 0
    for u in USERS:
        result = await conn.execute(
            """INSERT INTO usuarios (id, cliente_id, email, password_hash, nombre, rol, is_active, debe_cambiar_password)
               VALUES ($1, $2, $3, $4, $5, $6, TRUE, FALSE)
               ON CONFLICT (email) DO NOTHING""",
            uuid.UUID(u["id"]), DEMO_TENANT, u["email"], DEMO_PASSWORD, u["nombre"], u["rol"],
        )
        if "INSERT" in result and result != "INSERT 0 0":
            users_created += 1
            print(f"  + Usuario: {u['nombre']} ({u['rol']})")
        else:
            print(f"  = Usuario existente: {u['nombre']}")

    # ── 2. Casos ─────────────────────────────────────────────────────────────
    cases_created = 0
    audit_created = 0
    stats = {"tipo": {}, "estado": {}}
    admin_id = uuid.UUID("22222222-2222-2222-2222-222222222222")  # Demo FlexPQR admin
    # Buscar el admin real
    admin_row = await conn.fetchrow(
        "SELECT id FROM usuarios WHERE cliente_id = $1 AND rol = 'admin' AND email = 'demo@flexpqr.co'",
        DEMO_TENANT,
    )
    if admin_row:
        admin_id = admin_row["id"]

    for i, c in enumerate(CASES):
        # Idempotencia: verificar si ya existe
        exists = await conn.fetchval(
            "SELECT id FROM pqrs_casos WHERE cliente_id = $1 AND email_origen = $2 AND asunto = $3",
            DEMO_TENANT, c["email_origen"], c["asunto"],
        )
        if exists:
            print(f"  = Caso existente: {c['asunto'][:50]}...")
            continue

        caso_id = uuid.uuid4()
        analista_id = ANALYST_IDS[c["analista_idx"] % len(ANALYST_IDS)]
        fecha_rec = c["fecha_recibido"]
        radicado = f"PQRS-{fecha_rec.year}-{str(caso_id)[:8].upper()}"

        # Calcular fechas para casos contestados/cerrados
        enviado_at = None
        aprobado_at = None
        borrador_estado = None
        borrador_text = None

        if c["estado"] in ("CONTESTADO", "CERRADO"):
            dias_resp = 3 if c["tipo_caso"] == "TUTELA" else 5
            enviado_at = fecha_rec + timedelta(days=dias_resp)
            aprobado_at = enviado_at - timedelta(minutes=30)
            borrador_estado = "ENVIADO"
            borrador_text = f"Respuesta formal enviada al ciudadano. Caso {radicado} atendido dentro del plazo legal."
        elif c.get("borrador") and c["borrador"] != "APROBADO":
            borrador_estado = "PENDIENTE"
            borrador_text = c["borrador"]
        elif c["estado"] == "EN_PROCESO" and not c.get("borrador"):
            borrador_estado = None

        await conn.execute(
            """INSERT INTO pqrs_casos
               (id, cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad,
                fecha_recibido, tipo_caso, fecha_vencimiento, numero_radicado,
                asignado_a, fecha_asignacion, acuse_enviado, es_pqrs,
                borrador_respuesta, borrador_estado, enviado_at, aprobado_at, aprobado_por)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,TRUE,TRUE,$14,$15,$16,$17,$18)""",
            caso_id, DEMO_TENANT, c["email_origen"], c["asunto"], c["cuerpo"],
            c["estado"], c["nivel_prioridad"], fecha_rec, c["tipo_caso"],
            c["fecha_vencimiento"], radicado, analista_id,
            fecha_rec + timedelta(hours=1),
            borrador_text, borrador_estado, enviado_at, aprobado_at,
            admin_id if aprobado_at else None,
        )
        cases_created += 1
        stats["tipo"][c["tipo_caso"]] = stats["tipo"].get(c["tipo_caso"], 0) + 1
        stats["estado"][c["estado"]] = stats["estado"].get(c["estado"], 0) + 1

        # ── Audit log ────────────────────────────────────────────────────────
        eventos = [("ASIGNADO", fecha_rec + timedelta(hours=1))]
        if borrador_estado in ("PENDIENTE", "ENVIADO"):
            eventos.append(("BORRADOR_GENERADO", fecha_rec + timedelta(hours=2)))
        if c["estado"] in ("CONTESTADO", "CERRADO") and enviado_at:
            eventos.append(("ENVIADO_LOTE", enviado_at))
        if c["estado"] == "CERRADO" and enviado_at:
            eventos.append(("CERRADO", enviado_at + timedelta(hours=1)))

        for accion, ts in eventos:
            await conn.execute(
                """INSERT INTO audit_log_respuestas (id, caso_id, usuario_id, accion, created_at, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                uuid.uuid4(), caso_id,
                admin_id if accion == "ENVIADO_LOTE" else analista_id,
                accion, ts, json.dumps({"seed": True}),
            )
            audit_created += 1

        print(f"  + [{c['tipo_caso']:10}] [{c['estado']:12}] {c['asunto'][:55]}...")

    await conn.close()

    # ── Resumen ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SEED DEMO COMPLETADO")
    print(f"{'='*60}")
    print(f"  Usuarios creados:  {users_created}/{len(USERS)}")
    print(f"  Casos insertados:  {cases_created}/{len(CASES)}")
    print(f"  Audit log entries: {audit_created}")
    print(f"\n  Por tipo:")
    for t, n in sorted(stats.get("tipo", {}).items()):
        print(f"    {t:12} {n}")
    print(f"\n  Por estado:")
    for e, n in sorted(stats.get("estado", {}).items()):
        print(f"    {e:12} {n}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
