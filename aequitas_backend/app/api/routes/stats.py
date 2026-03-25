import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List

from app.core.db import get_db_connection
from app.core.security import get_current_user, UserInToken

router = APIRouter()
logger = logging.getLogger("STATS")

@router.get("/dashboard")
async def get_dashboard_stats(
    cliente_id: Optional[str] = None,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
) -> Dict[str, Any]:
    es_super = current_user.role == 'super_admin'
    es_abogado = current_user.role == 'analista'

    # Determinar el tenant a filtrar
    if es_super and cliente_id:
        target_tenant = cliente_id
    elif not es_super:
        target_tenant = str(current_user.tenant_uuid)
    else:
        target_tenant = None  # super_admin sin filtro: ve todo

    filtro_tenant = f"AND cliente_id = '{target_tenant}'" if target_tenant else ""
    filtro_abogado = f"AND asignado_a = '{current_user.usuario_id}'" if es_abogado else ""
    w = f"WHERE 1=1 {filtro_tenant} {filtro_abogado}"

    total_casos    = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w}")
    total_criticos = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND nivel_prioridad IN ('ALTA', 'CRITICA')")
    abiertos       = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND estado = 'ABIERTO'")
    en_proceso     = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND estado = 'EN_PROCESO'")
    contestados    = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND estado = 'CONTESTADO'")
    cerrados       = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND estado = 'CERRADO'")
    casos_hoy      = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND fecha_recibido >= CURRENT_DATE")
    casos_semana   = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND fecha_recibido >= CURRENT_DATE - INTERVAL '7 days'")
    vencidos       = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND fecha_vencimiento < NOW() AND estado != 'CERRADO'")
    asignados      = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND asignado_a IS NOT NULL")
    con_acuse      = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND acuse_enviado = TRUE")
    respondidos    = await conn.fetchval(f"SELECT COUNT(*) FROM pqrs_casos {w} AND estado IN ('CONTESTADO', 'CERRADO')")

    estados_records = await conn.fetch(f"SELECT estado, COUNT(*) as count FROM pqrs_casos {w} GROUP BY estado")
    distribucion_estados = {r['estado']: r['count'] for r in estados_records}

    tipos_records = await conn.fetch(f"SELECT tipo_caso, COUNT(*) as count FROM pqrs_casos {w} GROUP BY tipo_caso")
    distribucion_tipos = {r['tipo_caso'] if r['tipo_caso'] else 'SIN TIPO': r['count'] for r in tipos_records}

    ultimos_records = await conn.fetch(f"""
        SELECT c.id, c.email_origen, c.asunto, c.nivel_prioridad, c.estado,
               c.fecha_recibido, c.tipo_caso, c.fecha_vencimiento,
               c.cliente_id, t.nombre AS cliente_nombre
        FROM pqrs_casos c
        LEFT JOIN clientes_tenant t ON t.id = c.cliente_id
        {w}
        ORDER BY c.fecha_recibido DESC LIMIT 50
    """)
    ultimos_casos = [
        {
            "id": str(r["id"]),
            "email": r["email_origen"],
            "asunto": r["asunto"],
            "prioridad": r["nivel_prioridad"],
            "estado": r["estado"],
            "tipo": r["tipo_caso"],
            "fecha": r["fecha_recibido"].isoformat() if r["fecha_recibido"] else None,
            "vencimiento": r["fecha_vencimiento"].isoformat() if r["fecha_vencimiento"] else None,
            "cliente_id": str(r["cliente_id"]) if r["cliente_id"] else None,
            "cliente_nombre": r["cliente_nombre"]
        }
        for r in ultimos_records
    ]

    porcentaje_efectividad = round((cerrados / total_casos * 100), 1) if total_casos > 0 else 0

    return {
        "kpis": {
            "total_casos": total_casos,
            "casos_criticos": total_criticos,
            "porcentaje_resueltos": porcentaje_efectividad,
            "abiertos": abiertos,
            "en_proceso": en_proceso,
            "contestados": contestados,
            "cerrados": cerrados,
            "casos_hoy": casos_hoy,
            "casos_semana": casos_semana,
            "vencidos": vencidos
        },
        "trazabilidad": {
            "recibidos":   total_casos,
            "asignados":   asignados,
            "con_acuse":   con_acuse,
            "respondidos": respondidos,
        },
        "distribucion": distribucion_estados,
        "distribucion_tipo": distribucion_tipos,
        "ultimos_casos": ultimos_casos
    }


@router.get("/rendimiento")
async def get_rendimiento(
    periodo: str = "semana",
    cliente_id: Optional[str] = None,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
) -> Dict[str, Any]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")

    es_super = current_user.role == 'super_admin'
    if es_super and cliente_id:
        target_tenant = cliente_id
    elif es_super:
        target_tenant = None  # super_admin sin filtro: todos los tenants
    else:
        target_tenant = str(current_user.tenant_uuid)

    intervalos = {"dia": "1 day", "semana": "7 days", "mes": "30 days"}
    intervalo = intervalos.get(periodo, "7 days")

    if target_tenant is None:
        rows = await conn.fetch(f"""
            SELECT
                u.id, u.nombre, u.email,
                t.nombre AS cliente_nombre,
                COUNT(c.id) FILTER (WHERE c.fecha_asignacion >= NOW() - INTERVAL '{intervalo}') AS asignados_periodo,
                COUNT(c.id) AS asignados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO') AS cerrados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO' AND c.fecha_asignacion >= NOW() - INTERVAL '{intervalo}') AS cerrados_periodo,
                COUNT(c.id) FILTER (WHERE c.fecha_vencimiento < NOW() AND c.estado != 'CERRADO') AS vencidos,
                COUNT(c.id) FILTER (WHERE c.nivel_prioridad IN ('ALTA','CRITICA')) AS criticos,
                ROUND(AVG(EXTRACT(EPOCH FROM (c.updated_at - c.fecha_asignacion)) / 3600)::numeric, 1) AS avg_horas_resolucion
            FROM usuarios u
            LEFT JOIN pqrs_casos c ON c.asignado_a = u.id
            LEFT JOIN clientes_tenant t ON t.id = u.cliente_id
            WHERE u.rol IN ('analista', 'abogado')
            GROUP BY u.id, u.nombre, u.email, t.nombre
            ORDER BY asignados_total DESC
        """)
    else:
        rows = await conn.fetch(f"""
            SELECT
                u.id, u.nombre, u.email,
                NULL::text AS cliente_nombre,
                COUNT(c.id) FILTER (WHERE c.fecha_asignacion >= NOW() - INTERVAL '{intervalo}') AS asignados_periodo,
                COUNT(c.id) AS asignados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO') AS cerrados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO' AND c.fecha_asignacion >= NOW() - INTERVAL '{intervalo}') AS cerrados_periodo,
                COUNT(c.id) FILTER (WHERE c.fecha_vencimiento < NOW() AND c.estado != 'CERRADO') AS vencidos,
                COUNT(c.id) FILTER (WHERE c.nivel_prioridad IN ('ALTA','CRITICA')) AS criticos,
                ROUND(AVG(EXTRACT(EPOCH FROM (c.updated_at - c.fecha_asignacion)) / 3600)::numeric, 1) AS avg_horas_resolucion
            FROM usuarios u
            LEFT JOIN pqrs_casos c ON c.asignado_a = u.id
            WHERE u.cliente_id = $1::uuid AND u.rol IN ('analista', 'abogado')
            GROUP BY u.id, u.nombre, u.email
            ORDER BY asignados_total DESC
        """, target_tenant)

    abogados = [
        {
            "id": str(r["id"]),
            "nombre": r["nombre"],
            "email": r["email"],
            "cliente_nombre": r["cliente_nombre"],
            "asignados_periodo": r["asignados_periodo"] or 0,
            "asignados_total": r["asignados_total"] or 0,
            "cerrados_total": r["cerrados_total"] or 0,
            "cerrados_periodo": r["cerrados_periodo"] or 0,
            "vencidos": r["vencidos"] or 0,
            "criticos": r["criticos"] or 0,
            "tasa_resolucion": round((r["cerrados_total"] / r["asignados_total"] * 100), 1) if r["asignados_total"] else 0,
            "avg_horas_resolucion": float(r["avg_horas_resolucion"]) if r["avg_horas_resolucion"] else None
        }
        for r in rows
    ]

    return {"periodo": periodo, "abogados": abogados}


@router.get("/rendimiento/tipos")
async def rendimiento_tipos(
    periodo: str = "semana",
    cliente_id: Optional[str] = None,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
):
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403)
    es_super = current_user.role == "super_admin"
    intervalos = {"dia": "1 day", "semana": "7 days", "mes": "30 days"}
    intervalo = intervalos.get(periodo, "7 days")

    if es_super and not cliente_id:
        rows = await conn.fetch(f"""
            SELECT tipo_caso, COUNT(*) AS total FROM pqrs_casos
            WHERE fecha_recibido >= NOW() - INTERVAL '{intervalo}'
            GROUP BY tipo_caso ORDER BY total DESC
        """)
    else:
        tid = uuid.UUID(cliente_id) if (es_super and cliente_id) else uuid.UUID(current_user.tenant_uuid)
        rows = await conn.fetch(f"""
            SELECT tipo_caso, COUNT(*) AS total FROM pqrs_casos
            WHERE cliente_id = $1 AND fecha_recibido >= NOW() - INTERVAL '{intervalo}'
            GROUP BY tipo_caso ORDER BY total DESC
        """, tid)
    return [{"tipo": r["tipo_caso"], "total": r["total"]} for r in rows]


@router.get("/rendimiento/tendencia")
async def rendimiento_tendencia(
    periodo: str = "semana",
    cliente_id: Optional[str] = None,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
):
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403)
    es_super = current_user.role == "super_admin"
    intervalos = {"dia": "1 day", "semana": "7 days", "mes": "30 days"}
    intervalo = intervalos.get(periodo, "7 days")

    if es_super and not cliente_id:
        rec = await conn.fetch(f"""
            SELECT DATE(fecha_recibido AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
            FROM pqrs_casos WHERE fecha_recibido >= NOW() - INTERVAL '{intervalo}'
            GROUP BY d ORDER BY d
        """)
        cer = await conn.fetch(f"""
            SELECT DATE(enviado_at AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
            FROM pqrs_casos WHERE enviado_at IS NOT NULL AND enviado_at >= NOW() - INTERVAL '{intervalo}'
            GROUP BY d ORDER BY d
        """)
    else:
        tid = uuid.UUID(cliente_id) if (es_super and cliente_id) else uuid.UUID(current_user.tenant_uuid)
        rec = await conn.fetch(f"""
            SELECT DATE(fecha_recibido AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
            FROM pqrs_casos WHERE cliente_id = $1 AND fecha_recibido >= NOW() - INTERVAL '{intervalo}'
            GROUP BY d ORDER BY d
        """, tid)
        cer = await conn.fetch(f"""
            SELECT DATE(enviado_at AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
            FROM pqrs_casos WHERE cliente_id = $1 AND enviado_at IS NOT NULL AND enviado_at >= NOW() - INTERVAL '{intervalo}'
            GROUP BY d ORDER BY d
        """, tid)

    recibidos = {str(r["d"]): r["n"] for r in rec}
    cerrados  = {str(r["d"]): r["n"] for r in cer}
    all_dates = sorted(set(recibidos) | set(cerrados))
    return [{"fecha": d, "recibidos": recibidos.get(d, 0), "cerrados": cerrados.get(d, 0)} for d in all_dates]


@router.get("/rendimiento/{abogado_id}/actividad")
async def rendimiento_actividad(
    abogado_id: str,
    periodo: str = "semana",
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> List[Dict[str, Any]]:
    """Timeline de actividad por abogado: casos con eventos ordenados por fecha."""
    es_admin = current_user.role in ['admin', 'super_admin']
    # Abogado solo puede ver su propia actividad
    if not es_admin and str(current_user.usuario_id) != abogado_id:
        raise HTTPException(status_code=403, detail="Sin permiso")

    intervalos = {"dia": "1 day", "semana": "7 days", "mes": "30 days"}
    intervalo = intervalos.get(periodo, "7 days")

    # Casos asignados al abogado en el período
    casos = await conn.fetch("""
        SELECT
            c.id, c.numero_radicado, c.asunto, c.tipo_caso, c.estado,
            c.nivel_prioridad, c.email_origen,
            c.fecha_recibido, c.fecha_asignacion, c.fecha_vencimiento,
            c.enviado_at, c.borrador_estado,
            CASE WHEN c.enviado_at IS NOT NULL AND c.fecha_asignacion IS NOT NULL
                 THEN ROUND(EXTRACT(EPOCH FROM (c.enviado_at - c.fecha_asignacion)) / 3600.0, 1)
                 ELSE NULL
            END AS horas_resolucion
        FROM pqrs_casos c
        WHERE c.asignado_a = $1::uuid
          AND c.fecha_asignacion >= NOW() - INTERVAL %s
        ORDER BY c.fecha_asignacion DESC
        LIMIT 100
    """ % f"'{intervalo}'", uuid.UUID(abogado_id))

    # Eventos de audit log para cada caso
    caso_ids = [r["id"] for r in casos]
    eventos_map: Dict[str, list] = {str(c["id"]): [] for c in casos}

    if caso_ids:
        eventos = await conn.fetch("""
            SELECT al.caso_id, al.accion, al.created_at, u.nombre AS usuario_nombre
            FROM audit_log_respuestas al
            LEFT JOIN usuarios u ON u.id = al.usuario_id
            WHERE al.caso_id = ANY($1::uuid[])
            ORDER BY al.created_at ASC
        """, caso_ids)
        for ev in eventos:
            cid = str(ev["caso_id"])
            if cid in eventos_map:
                eventos_map[cid].append({
                    "accion": ev["accion"],
                    "fecha": ev["created_at"].isoformat() if ev["created_at"] else None,
                    "usuario": ev["usuario_nombre"],
                })

    result = []
    for c in casos:
        cid = str(c["id"])
        # Construir timeline de eventos del caso
        eventos_caso = []
        if c["fecha_asignacion"]:
            eventos_caso.append({"accion": "ASIGNADO", "fecha": c["fecha_asignacion"].isoformat(), "usuario": None})
        eventos_caso.extend(eventos_map.get(cid, []))
        if c["enviado_at"]:
            eventos_caso.append({"accion": "ENVIADO", "fecha": c["enviado_at"].isoformat(), "usuario": None})

        result.append({
            "id": cid,
            "numero_radicado": c["numero_radicado"],
            "asunto": c["asunto"],
            "tipo_caso": c["tipo_caso"],
            "estado": c["estado"],
            "nivel_prioridad": c["nivel_prioridad"],
            "email_origen": c["email_origen"],
            "fecha_recibido": c["fecha_recibido"].isoformat() if c["fecha_recibido"] else None,
            "fecha_asignacion": c["fecha_asignacion"].isoformat() if c["fecha_asignacion"] else None,
            "fecha_vencimiento": c["fecha_vencimiento"].isoformat() if c["fecha_vencimiento"] else None,
            "enviado_at": c["enviado_at"].isoformat() if c["enviado_at"] else None,
            "horas_resolucion": float(c["horas_resolucion"]) if c["horas_resolucion"] else None,
            "eventos": eventos_caso,
        })
    return result
