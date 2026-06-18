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
    periodo: str = "semana",
    cliente_id: Optional[str] = None,
    workflow: Optional[str] = None,  # PQRS | ATENCION_CLIENTE | None=ambos (sprint FF bloque 7)
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
) -> Dict[str, Any]:
    es_super = current_user.role == 'super_admin'
    es_abogado = current_user.role in ('analista', 'abogado')

    if workflow is not None and workflow not in ("PQRS", "ATENCION_CLIENTE"):
        raise HTTPException(status_code=400, detail="workflow inválido")

    # Período del dashboard: aplica al WHERE base => TODO se filtra por el rango
    # (activos creados en el período, vencidos del período, ingresos del período…).
    # `por_vencer` sigue siendo prospectivo (vence ≤48h) pero contado sobre casos
    # del período. Mismo contrato que /rendimiento/tendencia.
    intervalos = {"dia": 1, "semana": 7, "mes": 30}
    dias = intervalos.get(periodo, 7)

    # Determinar el tenant a filtrar
    if es_super and cliente_id:
        target_tenant = cliente_id
    elif not es_super:
        target_tenant = str(current_user.tenant_uuid)
    else:
        target_tenant = None  # super_admin sin filtro: ve todo

    params = []
    filtros = [f"fecha_recibido >= CURRENT_DATE - INTERVAL '{dias} days'"]
    if target_tenant:
        params.append(uuid.UUID(target_tenant))
        filtros.append(f"cliente_id = ${len(params)}::uuid")
    if es_abogado:
        params.append(uuid.UUID(current_user.usuario_id))
        filtros.append(f"asignado_a = ${len(params)}::uuid")
    if workflow:
        params.append(workflow)
        filtros.append(f"tipo_workflow = ${len(params)}")
    w = "WHERE " + " AND ".join(filtros)

    # KPIs en una sola query con COUNT(*) FILTER (1 RTT vs 14)
    # Incluye breakdown PQR/TUTELA y pulso de tutelas (SLA propio, 10 días).
    kpi = await conn.fetchrow(f"""
        SELECT
          COUNT(*) AS total_casos,
          COUNT(*) FILTER (WHERE nivel_prioridad IN ('ALTA','CRITICA')) AS total_criticos,
          COUNT(*) FILTER (WHERE estado='ABIERTO')                       AS abiertos,
          COUNT(*) FILTER (WHERE estado='EN_PROCESO')                    AS en_proceso,
          COUNT(*) FILTER (WHERE estado='CONTESTADO')                    AS contestados,
          COUNT(*) FILTER (WHERE estado='CERRADO')                       AS cerrados,
          COUNT(*) FILTER (WHERE estado IN ('ABIERTO','EN_PROCESO'))     AS activos,
          COUNT(*) FILTER (WHERE fecha_recibido >= CURRENT_DATE)         AS casos_hoy,
          COUNT(*)                                                       AS casos_periodo,
          COUNT(*) FILTER (WHERE fecha_vencimiento < NOW() AND estado != 'CERRADO') AS vencidos,
          COUNT(*) FILTER (WHERE fecha_vencimiento >= NOW()
                            AND fecha_vencimiento <= NOW() + INTERVAL '48 hours'
                            AND estado != 'CERRADO')                     AS por_vencer,
          COUNT(*) FILTER (WHERE asignado_a IS NOT NULL)                 AS asignados,
          COUNT(*) FILTER (WHERE acuse_enviado = TRUE)                   AS con_acuse,
          COUNT(*) FILTER (WHERE estado IN ('CONTESTADO','CERRADO'))     AS respondidos,
          -- Breakdown PQR vs Tutela del período (WHERE base ya filtró fecha_recibido)
          COUNT(*) FILTER (WHERE tipo_caso IN ('PETICION','QUEJA','RECLAMO','SOLICITUD','SUGERENCIA')) AS ingresos_pqr,
          COUNT(*) FILTER (WHERE tipo_caso = 'TUTELA')                   AS ingresos_tutela,
          -- Pulso TUTELAS (SLA legal 10 días, tracking separado)
          COUNT(*) FILTER (WHERE tipo_caso='TUTELA' AND estado IN ('ABIERTO','EN_PROCESO')) AS tutelas_activas,
          COUNT(*) FILTER (WHERE tipo_caso='TUTELA' AND fecha_vencimiento < NOW() AND estado != 'CERRADO') AS tutelas_vencidas,
          COUNT(*) FILTER (WHERE tipo_caso='TUTELA' AND fecha_vencimiento >= NOW()
                            AND fecha_vencimiento <= NOW() + INTERVAL '48 hours'
                            AND estado != 'CERRADO') AS tutelas_por_vencer,
          COUNT(*) FILTER (WHERE tipo_caso='TUTELA')                     AS tutelas_total,
          -- Tutelas escaladas de PQR previo (poblado por master_worker al ingestar)
          COUNT(*) FILTER (WHERE tipo_caso='TUTELA'
                            AND COALESCE(array_length(pqr_origenes, 1), 0) > 0) AS tutelas_escaladas
        FROM pqrs_casos {w}
    """, *params)
    total_casos        = kpi['total_casos']
    total_criticos     = kpi['total_criticos']
    abiertos           = kpi['abiertos']
    en_proceso         = kpi['en_proceso']
    contestados        = kpi['contestados']
    cerrados           = kpi['cerrados']
    activos            = kpi['activos']
    casos_hoy          = kpi['casos_hoy']
    casos_periodo      = kpi['casos_periodo']
    vencidos           = kpi['vencidos']
    por_vencer         = kpi['por_vencer']
    asignados          = kpi['asignados']
    con_acuse          = kpi['con_acuse']
    respondidos        = kpi['respondidos']
    ingresos_pqr       = kpi['ingresos_pqr']
    ingresos_tutela    = kpi['ingresos_tutela']
    tutelas_activas    = kpi['tutelas_activas']
    tutelas_vencidas   = kpi['tutelas_vencidas']
    tutelas_por_vencer = kpi['tutelas_por_vencer']
    tutelas_total      = kpi['tutelas_total']
    tutelas_escaladas  = kpi['tutelas_escaladas']

    estados_records = await conn.fetch(f"SELECT estado, COUNT(*) as count FROM pqrs_casos {w} GROUP BY estado", *params)
    distribucion_estados = {r['estado']: r['count'] for r in estados_records}

    tipos_records = await conn.fetch(f"SELECT tipo_caso, COUNT(*) as count FROM pqrs_casos {w} GROUP BY tipo_caso", *params)
    distribucion_tipos = {r['tipo_caso'] if r['tipo_caso'] else 'SIN TIPO': r['count'] for r in tipos_records}

    ultimos_records = await conn.fetch(f"""
        SELECT c.id, c.email_origen, c.asunto, c.nivel_prioridad, c.estado,
               c.fecha_recibido, c.tipo_caso, c.fecha_vencimiento,
               c.cliente_id, t.nombre AS cliente_nombre
        FROM pqrs_casos c
        LEFT JOIN clientes_tenant t ON t.id = c.cliente_id
        {w}
        ORDER BY c.fecha_recibido DESC LIMIT 10
    """, *params)
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

    tasa_escalamiento = round((tutelas_escaladas / tutelas_total * 100), 1) if tutelas_total > 0 else 0

    # ─── Sprint FF bloque 7: workflow_breakdown (solo si el tenant tiene AC) ───
    # Detecta si el tenant del dashboard usa workflow ATENCION_CLIENTE para
    # decidir si calcular el bloque. Cero costo extra para Recovery/Demo.
    workflow_breakdown = None
    detect_tenant = target_tenant  # str UUID o None
    tiene_ac = False
    if detect_tenant:
        tiene_ac = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM config_buzones "
            "WHERE cliente_id = $1::uuid AND tipo_workflow = 'ATENCION_CLIENTE' "
            "AND is_active = TRUE)",
            uuid.UUID(detect_tenant),
        )
    elif es_super:
        # super_admin sin cliente_id => mostramos breakdown si hay ALGÚN tenant con AC
        tiene_ac = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM config_buzones "
            "WHERE tipo_workflow = 'ATENCION_CLIENTE' AND is_active = TRUE)"
        )

    if tiene_ac:
        # Counts por workflow del período. Reutiliza el WHERE base del dashboard
        # excepto el filtro de workflow (queremos ver ambos breakdown).
        bd_params = []
        bd_filtros = [f"fecha_recibido >= CURRENT_DATE - INTERVAL '{dias} days'"]
        if target_tenant:
            bd_params.append(uuid.UUID(target_tenant))
            bd_filtros.append(f"cliente_id = ${len(bd_params)}::uuid")
        if es_abogado:
            bd_params.append(uuid.UUID(current_user.usuario_id))
            bd_filtros.append(f"asignado_a = ${len(bd_params)}::uuid")
        bd_w = "WHERE " + " AND ".join(bd_filtros)

        bd = await conn.fetchrow(f"""
            SELECT
              COUNT(*) FILTER (WHERE tipo_workflow = 'PQRS')              AS pqrs_count,
              COUNT(*) FILTER (WHERE tipo_workflow = 'ATENCION_CLIENTE')  AS ac_count
            FROM pqrs_casos {bd_w}
        """, *bd_params)

        # Top 5 plantillas más usadas en el período (vía audit_log PLANTILLA_APLICADA)
        top_plantillas = await conn.fetch(
            """SELECT pr.problematica, COUNT(*) AS usos
               FROM audit_log_respuestas a
               JOIN pqrs_casos c ON c.id = a.caso_id
               JOIN plantillas_respuesta pr
                 ON (a.metadata->>'plantilla_id')::uuid = pr.id
               WHERE a.accion = 'PLANTILLA_APLICADA'
                 AND a.created_at >= CURRENT_DATE - make_interval(days => $1)
                 AND ($2::uuid IS NULL OR c.cliente_id = $2::uuid)
               GROUP BY pr.problematica
               ORDER BY usos DESC LIMIT 5""",
            dias,
            uuid.UUID(target_tenant) if target_tenant else None,
        )

        # % de casos AC del período que tienen problematica_detectada con plantilla matching
        # (proxy de "match exacto" vs "fallback IA"). Si problematica_detectada está poblada
        # y existe una plantilla con misma `problematica`, contó como match.
        match_stats = await conn.fetchrow(f"""
            SELECT
              COUNT(*) FILTER (WHERE c.problematica_detectada IS NOT NULL
                               AND EXISTS(SELECT 1 FROM plantillas_respuesta pr
                                          WHERE pr.cliente_id = c.cliente_id
                                          AND pr.problematica = c.problematica_detectada
                                          AND pr.is_active = TRUE)) AS con_match,
              COUNT(*) AS total_ac
            FROM pqrs_casos c
            WHERE c.tipo_workflow = 'ATENCION_CLIENTE'
              AND c.fecha_recibido >= CURRENT_DATE - INTERVAL '{dias} days'
              {("AND c.cliente_id = $1::uuid" if target_tenant else "")}
        """, *([uuid.UUID(target_tenant)] if target_tenant else []))

        pct_match = 0
        if match_stats and match_stats["total_ac"] > 0:
            pct_match = round(match_stats["con_match"] / match_stats["total_ac"] * 100, 1)

        workflow_breakdown = {
            "pqrs_count": bd["pqrs_count"] or 0,
            "ac_count":   bd["ac_count"]   or 0,
            "plantillas_top5": [
                {"problematica": r["problematica"], "usos": r["usos"]}
                for r in top_plantillas
            ],
            "pct_match_exacto": pct_match,
        }

    return {
        "periodo": periodo,
        "dias": dias,
        "workflow_breakdown": workflow_breakdown,
        "kpis": {
            "total_casos": total_casos,
            "casos_criticos": total_criticos,
            "porcentaje_resueltos": porcentaje_efectividad,
            "abiertos": abiertos,
            "en_proceso": en_proceso,
            "contestados": contestados,
            "cerrados": cerrados,
            "casos_hoy": casos_hoy,
            "casos_periodo": casos_periodo,
            "casos_semana": casos_periodo,  # legacy: clientes viejos esperan casos_semana
            "vencidos": vencidos,
            "por_vencer": por_vencer,
            "activos": activos
        },
        "ingresos_periodo": {
            "pqr": ingresos_pqr,
            "tutela": ingresos_tutela,
            "total": ingresos_pqr + ingresos_tutela,
        },
        # legacy alias: clientes que aún leen ingresos_semana
        "ingresos_semana": {
            "pqr": ingresos_pqr,
            "tutela": ingresos_tutela,
            "total": ingresos_pqr + ingresos_tutela,
        },
        "tutelas": {
            "activas": tutelas_activas,
            "vencidas": tutelas_vencidas,
            "por_vencer": tutelas_por_vencer,
            "total": tutelas_total,
            "escaladas_de_pqr": tutelas_escaladas,
            "tasa_escalamiento": tasa_escalamiento,
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

    intervalos = {"dia": 1, "semana": 7, "mes": 30}
    dias = intervalos.get(periodo, 7)

    # Subqueries de eficiencia (idénticas en ambas ramas). Calculadas por usuario.
    # NOTA: usan ventana del período ($1 = dias) para borradores; PQRs gestionados
    # y escalamiento se miden sobre la historia completa del abogado.
    efic_subq = """
      (SELECT COUNT(*) FROM audit_log_respuestas a
        WHERE a.usuario_id = u.id AND a.accion='BORRADOR_GENERADO'
          AND a.created_at >= NOW() - make_interval(days => $1)) AS borradores_generados,
      (SELECT COUNT(*) FROM audit_log_respuestas a
        WHERE a.usuario_id = u.id AND a.accion='BORRADOR_EDITADO'
          AND a.created_at >= NOW() - make_interval(days => $1)) AS borradores_editados,
      (SELECT COUNT(*) FROM audit_log_respuestas a
        WHERE a.usuario_id = u.id AND a.accion='ENVIADO_LOTE'
          AND a.created_at >= NOW() - make_interval(days => $1)) AS borradores_enviados,
      (SELECT ROUND(AVG(similarity_score)::numeric, 3) FROM borrador_feedback bf
        WHERE bf.usuario_id = u.id
          AND bf.created_at >= NOW() - make_interval(days => $1)) AS similarity_avg,
      (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (e.created_at - g.created_at))/60)::numeric, 1)
         FROM audit_log_respuestas g
         JOIN audit_log_respuestas e ON e.caso_id = g.caso_id AND e.accion='ENVIADO_LOTE'
        WHERE g.accion='BORRADOR_GENERADO' AND g.usuario_id = u.id
          AND g.created_at >= NOW() - make_interval(days => $1)) AS review_time_avg_min,
      -- PQRs gestionados (respondidos) por este abogado (toda la historia)
      (SELECT COUNT(*) FROM pqrs_casos pq
        WHERE pq.asignado_a = u.id AND pq.tipo_caso != 'TUTELA'
          AND pq.estado IN ('CERRADO','CONTESTADO')) AS pqrs_gestionados,
      -- De esos PQRs, cuántos figuran como origen de alguna tutela posterior
      (SELECT COUNT(DISTINCT pq.id) FROM pqrs_casos pq
         JOIN pqrs_casos t ON pq.id = ANY(t.pqr_origenes)
        WHERE pq.asignado_a = u.id AND pq.tipo_caso != 'TUTELA'
          AND t.tipo_caso = 'TUTELA') AS pqrs_escalaron
    """

    if target_tenant is None:
        rows = await conn.fetch(f"""
            SELECT
                u.id, u.nombre, u.email,
                t.nombre AS cliente_nombre,
                COUNT(c.id) FILTER (WHERE c.fecha_asignacion >= NOW() - make_interval(days => $1)) AS asignados_periodo,
                COUNT(c.id) AS asignados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO') AS cerrados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO' AND c.fecha_asignacion >= NOW() - make_interval(days => $1)) AS cerrados_periodo,
                COUNT(c.id) FILTER (WHERE c.fecha_vencimiento < NOW() AND c.estado != 'CERRADO') AS vencidos,
                COUNT(c.id) FILTER (WHERE c.nivel_prioridad IN ('ALTA','CRITICA')) AS criticos,
                ROUND(AVG(EXTRACT(EPOCH FROM (c.updated_at - c.fecha_asignacion)) / 3600)::numeric, 1) AS avg_horas_resolucion,
                {efic_subq}
            FROM usuarios u
            LEFT JOIN pqrs_casos c ON c.asignado_a = u.id
            LEFT JOIN clientes_tenant t ON t.id = u.cliente_id
            WHERE u.rol IN ('analista', 'abogado')
            GROUP BY u.id, u.nombre, u.email, t.nombre
            ORDER BY asignados_total DESC
        """, dias)
    else:
        rows = await conn.fetch(f"""
            SELECT
                u.id, u.nombre, u.email,
                NULL::text AS cliente_nombre,
                COUNT(c.id) FILTER (WHERE c.fecha_asignacion >= NOW() - make_interval(days => $1)) AS asignados_periodo,
                COUNT(c.id) AS asignados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO') AS cerrados_total,
                COUNT(c.id) FILTER (WHERE c.estado = 'CERRADO' AND c.fecha_asignacion >= NOW() - make_interval(days => $1)) AS cerrados_periodo,
                COUNT(c.id) FILTER (WHERE c.fecha_vencimiento < NOW() AND c.estado != 'CERRADO') AS vencidos,
                COUNT(c.id) FILTER (WHERE c.nivel_prioridad IN ('ALTA','CRITICA')) AS criticos,
                ROUND(AVG(EXTRACT(EPOCH FROM (c.updated_at - c.fecha_asignacion)) / 3600)::numeric, 1) AS avg_horas_resolucion,
                {efic_subq}
            FROM usuarios u
            LEFT JOIN pqrs_casos c ON c.asignado_a = u.id
            WHERE u.cliente_id = $2::uuid AND u.rol IN ('analista', 'abogado')
            GROUP BY u.id, u.nombre, u.email
            ORDER BY asignados_total DESC
        """, dias, target_tenant)

    abogados = []
    for r in rows:
        bg = r["borradores_generados"] or 0
        be = r["borradores_editados"] or 0
        pq_gest = r["pqrs_gestionados"] or 0
        pq_esc = r["pqrs_escalaron"] or 0
        abogados.append({
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
            "avg_horas_resolucion": float(r["avg_horas_resolucion"]) if r["avg_horas_resolucion"] else None,
            # === Eficiencia (Fase 1+2) ===
            "borradores_generados": bg,
            "borradores_editados": be,
            "borradores_enviados": r["borradores_enviados"] or 0,
            "ratio_edicion": round(be / bg * 100, 1) if bg else 0,
            "similarity_avg": float(r["similarity_avg"]) if r["similarity_avg"] is not None else None,
            "review_time_avg_min": float(r["review_time_avg_min"]) if r["review_time_avg_min"] is not None else None,
            "pqrs_gestionados": pq_gest,
            "pqrs_escalaron_a_tutela": pq_esc,
            "tutelas_evitadas": max(pq_gest - pq_esc, 0),
            "tasa_prevencion": round((pq_gest - pq_esc) / pq_gest * 100, 1) if pq_gest else 0,
        })

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
    intervalos = {"dia": 1, "semana": 7, "mes": 30}
    dias = intervalos.get(periodo, 7)

    if es_super and not cliente_id:
        rows = await conn.fetch("""
            SELECT tipo_caso, COUNT(*) AS total FROM pqrs_casos
            WHERE fecha_recibido >= NOW() - make_interval(days => $1)
            GROUP BY tipo_caso ORDER BY total DESC
        """, dias)
    else:
        tid = uuid.UUID(cliente_id) if (es_super and cliente_id) else uuid.UUID(current_user.tenant_uuid)
        rows = await conn.fetch("""
            SELECT tipo_caso, COUNT(*) AS total FROM pqrs_casos
            WHERE cliente_id = $1 AND fecha_recibido >= NOW() - make_interval(days => $2)
            GROUP BY tipo_caso ORDER BY total DESC
        """, tid, dias)
    return [{"tipo": r["tipo_caso"], "total": r["total"]} for r in rows]


@router.get("/rendimiento/tendencia")
async def rendimiento_tendencia(
    periodo: str = "semana",
    cliente_id: Optional[str] = None,
    workflow: Optional[str] = None,  # PQRS | ATENCION_CLIENTE | None=ambos (sprint FF bloque 7)
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
):
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403)
    if workflow is not None and workflow not in ("PQRS", "ATENCION_CLIENTE"):
        raise HTTPException(status_code=400, detail="workflow inválido")

    es_super = current_user.role == "super_admin"
    intervalos = {"dia": 1, "semana": 7, "mes": 30}
    dias = intervalos.get(periodo, 7)

    # Refactor sprint FF bloque 7: query unificada con WHERE dinámico (de 6 a 3 RTT)
    filtros_base = ["1=1"]
    params: list = [dias]  # $1 fijo siempre
    idx = 2
    if not (es_super and not cliente_id):
        tid = uuid.UUID(cliente_id) if (es_super and cliente_id) else uuid.UUID(current_user.tenant_uuid)
        filtros_base.append(f"cliente_id = ${idx}::uuid")
        params.append(tid)
        idx += 1
    if workflow:
        filtros_base.append(f"tipo_workflow = ${idx}")
        params.append(workflow)
        idx += 1
    base_w = " AND ".join(filtros_base)

    rec = await conn.fetch(f"""
        SELECT DATE(fecha_recibido AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
        FROM pqrs_casos
        WHERE {base_w} AND fecha_recibido >= NOW() - make_interval(days => $1)
        GROUP BY d ORDER BY d
    """, *params)
    cer = await conn.fetch(f"""
        SELECT DATE(enviado_at AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
        FROM pqrs_casos
        WHERE {base_w} AND enviado_at IS NOT NULL
              AND enviado_at >= NOW() - make_interval(days => $1)
        GROUP BY d ORDER BY d
    """, *params)
    tut = await conn.fetch(f"""
        SELECT DATE(fecha_recibido AT TIME ZONE 'America/Bogota') AS d, COUNT(*) AS n
        FROM pqrs_casos
        WHERE {base_w} AND tipo_caso = 'TUTELA'
              AND fecha_recibido >= NOW() - make_interval(days => $1)
        GROUP BY d ORDER BY d
    """, *params)

    recibidos = {str(r["d"]): r["n"] for r in rec}
    cerrados  = {str(r["d"]): r["n"] for r in cer}
    tutelas   = {str(r["d"]): r["n"] for r in tut}
    all_dates = sorted(set(recibidos) | set(cerrados) | set(tutelas))
    return [{"fecha": d, "recibidos": recibidos.get(d, 0), "cerrados": cerrados.get(d, 0), "tutelas": tutelas.get(d, 0)} for d in all_dates]


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

    intervalos = {"dia": 1, "semana": 7, "mes": 30}
    dias = intervalos.get(periodo, 7)

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
          AND c.fecha_asignacion >= NOW() - make_interval(days => $2)
        ORDER BY c.fecha_asignacion DESC
        LIMIT 100
    """, uuid.UUID(abogado_id), dias)

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
