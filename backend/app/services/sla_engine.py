"""
sla_engine.py — Motor Python de SLA para tutelas.

Coexiste con el SP `calcular_fecha_vencimiento` de PostgreSQL (migración 14):
- El SP hace el cálculo DEFAULT basado en `sla_regimen_config` (régimen por tenant + tipo_caso).
- Este motor se invoca SOLO para TUTELA cuando tenemos metadata_especifica
  del extractor (plazo_informe_horas + plazo_tipo).

Las 3 funciones públicas viven en el pipeline (`pipeline.py`):
- `calcular_vencimiento_tutela`: dispatcher sobre plazo_tipo.
- `sumar_horas_habiles`: jornada 8-12 / 13-17 UTC, excluye fines de semana + festivos.
- `calcular_vencimiento_medida_provisional`: plazo CALENDARIO desde `fecha_auto` si
  la metadata trae medidas provisionales.

Defaults defensivos:
- plazo_tipo desconocido → trata como HABILES + logger.warning.
- plazo_horas ≤ 0 → 48h HABILES + warning.
- horas = 0 → retorna inicio sin cálculo.
- metadata sin plazo → 48h HABILES + warning.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import asyncpg

logger = logging.getLogger("SLA_ENGINE")

# Jornada hábil (UTC). 8 horas hábiles por día. Bloques: 08-12 y 13-17.
_JORNADA_MANANA_INICIO = time(8, 0, 0)
_JORNADA_MANANA_FIN = time(12, 0, 0)
_JORNADA_TARDE_INICIO = time(13, 0, 0)
_JORNADA_TARDE_FIN = time(17, 0, 0)
_HORAS_POR_DIA_HABIL = 8

# Fallback mínimo de festivos fijos 2026 (cuando no hay conn disponible en tests).
_FESTIVOS_FALLBACK_FIJOS: frozenset[date] = frozenset({
    date(2026, 1, 1),   # Año Nuevo
    date(2026, 5, 1),   # Día del Trabajo
    date(2026, 7, 20),  # Independencia
    date(2026, 8, 7),   # Batalla de Boyacá
    date(2026, 12, 8),  # Inmaculada Concepción
    date(2026, 12, 25), # Navidad
})


# ─────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────

def _ensure_utc(dt: datetime) -> datetime:
    """Datetime timezone-aware en UTC. Si viene naive, se asume UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _obtener_festivos(anio: int, conn: Optional[asyncpg.Connection]) -> frozenset[date]:
    """
    Festivos de `festivos_colombia` para el año dado.
    Si conn es None retorna el fallback mínimo (tests).
    """
    if conn is None:
        return _festivos_fallback(anio)

    try:
        rows = await conn.fetch(
            "SELECT fecha FROM festivos_colombia "
            "WHERE fecha >= $1 AND fecha < $2",
            date(anio, 1, 1),
            date(anio + 1, 1, 1),
        )
        return frozenset(row["fecha"] for row in rows)
    except Exception:
        logger.exception("Fallo consultando festivos_colombia, uso fallback (año=%s)", anio)
        return _festivos_fallback(anio)


def _festivos_fallback(anio: int) -> frozenset[date]:
    """Festivos fijos del año (sin puentes móviles). Solo para tests sin conn."""
    if anio == 2026:
        return _FESTIVOS_FALLBACK_FIJOS
    # Para otros años, devolvemos los festivos fijos trasladados al año solicitado.
    return frozenset(d.replace(year=anio) for d in _FESTIVOS_FALLBACK_FIJOS)


def _es_dia_habil(dia: date, festivos: frozenset[date]) -> bool:
    # weekday: lunes=0, domingo=6.
    if dia.weekday() >= 5:
        return False
    return dia not in festivos


def _siguiente_inicio_jornada(desde: datetime, festivos: frozenset[date]) -> datetime:
    """Mueve `desde` al inicio de la próxima ventana hábil (08:00 de día hábil)."""
    cursor = desde
    # Si cae fuera de jornada, empuja al siguiente momento hábil.
    while True:
        dia = cursor.date()
        hora = cursor.time()
        if not _es_dia_habil(dia, festivos):
            cursor = datetime.combine(dia + timedelta(days=1), _JORNADA_MANANA_INICIO, tzinfo=timezone.utc)
            continue
        if hora < _JORNADA_MANANA_INICIO:
            return datetime.combine(dia, _JORNADA_MANANA_INICIO, tzinfo=timezone.utc)
        if _JORNADA_MANANA_FIN <= hora < _JORNADA_TARDE_INICIO:
            return datetime.combine(dia, _JORNADA_TARDE_INICIO, tzinfo=timezone.utc)
        if hora >= _JORNADA_TARDE_FIN:
            cursor = datetime.combine(dia + timedelta(days=1), _JORNADA_MANANA_INICIO, tzinfo=timezone.utc)
            continue
        # Dentro de jornada hábil → usa el momento tal cual.
        return cursor


def _minutos_restantes_bloque(dt: datetime) -> tuple[int, datetime]:
    """
    Minutos hábiles que quedan desde `dt` hasta el fin del bloque actual
    (mañana 12:00 o tarde 17:00). Retorna (minutos, fin_del_bloque).
    Si dt no está en jornada, retorna (0, dt).
    """
    hora = dt.time()
    if _JORNADA_MANANA_INICIO <= hora < _JORNADA_MANANA_FIN:
        fin = datetime.combine(dt.date(), _JORNADA_MANANA_FIN, tzinfo=dt.tzinfo)
        return (int((fin - dt).total_seconds() // 60), fin)
    if _JORNADA_TARDE_INICIO <= hora < _JORNADA_TARDE_FIN:
        fin = datetime.combine(dt.date(), _JORNADA_TARDE_FIN, tzinfo=dt.tzinfo)
        return (int((fin - dt).total_seconds() // 60), fin)
    return (0, dt)


# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────

async def sumar_horas_habiles(
    inicio: datetime,
    horas: int,
    cliente_id: Optional[uuid.UUID],
    conn: Optional[asyncpg.Connection],
) -> datetime:
    """
    Suma `horas` hábiles a `inicio` respetando:
    - jornada 08:00-12:00 + 13:00-17:00 UTC (8 h hábiles/día),
    - fines de semana excluidos,
    - festivos de `festivos_colombia` excluidos.

    Si el inicio cae fuera de jornada (fin de semana, festivo, antes/después de
    horario o durante almuerzo), se ajusta al siguiente momento hábil antes de
    empezar a sumar.
    """
    if horas == 0:
        return _ensure_utc(inicio)

    if horas < 0:
        raise ValueError(f"horas hábiles no puede ser negativo: {horas}")

    inicio_utc = _ensure_utc(inicio)
    festivos = await _obtener_festivos(inicio_utc.year, conn)
    # Si la suma cruza año, hacemos union con el próximo (barato).
    if horas > 24 * 8 * 30:  # heurística conservadora: si son muchas horas, incluir año siguiente
        festivos = festivos | await _obtener_festivos(inicio_utc.year + 1, conn)

    cursor = _siguiente_inicio_jornada(inicio_utc, festivos)
    minutos_restantes = horas * 60

    while minutos_restantes > 0:
        disponibles, fin_bloque = _minutos_restantes_bloque(cursor)
        if disponibles == 0:
            # No debería pasar post-ajuste; defense.
            cursor = _siguiente_inicio_jornada(
                datetime.combine(cursor.date() + timedelta(days=1), _JORNADA_MANANA_INICIO, tzinfo=timezone.utc),
                festivos,
            )
            continue

        if minutos_restantes <= disponibles:
            return cursor + timedelta(minutes=minutos_restantes)

        minutos_restantes -= disponibles
        # Avanza al inicio del siguiente bloque (tarde del mismo día o mañana siguiente hábil).
        cursor = _siguiente_inicio_jornada(fin_bloque, festivos)

    return cursor


async def calcular_vencimiento_tutela(
    fecha_inicio: datetime,
    metadata: Optional[dict],
    cliente_id: Optional[uuid.UUID],
    conn: Optional[asyncpg.Connection],
) -> datetime:
    """
    Calcula fecha_vencimiento para una tutela a partir de `metadata.plazo_informe_horas`
    y `metadata.plazo_tipo`.

    Defaults si metadata inconsistente:
    - sin plazo → 48h HABILES + warn.
    - plazo_tipo desconocido → HABILES + warn.
    - plazo_horas ≤ 0 → 48h HABILES + warn.
    - plazo_horas = 0 → retorna fecha_inicio (sin añadir tiempo).
    """
    meta = metadata or {}
    plazo_horas_raw = meta.get("plazo_informe_horas")
    plazo_tipo = meta.get("plazo_tipo")

    # Normalización de horas.
    plazo_horas: Optional[int]
    try:
        plazo_horas = int(plazo_horas_raw) if plazo_horas_raw is not None else None
    except (TypeError, ValueError):
        logger.warning("plazo_informe_horas no numérico (%r) → usando 48h HABILES", plazo_horas_raw)
        plazo_horas = None

    if plazo_horas is None:
        logger.warning("Metadata tutela sin plazo_informe_horas → usando 48h HABILES por defecto")
        plazo_horas = 48
        plazo_tipo = plazo_tipo or "HABILES"

    if plazo_horas < 0:
        logger.warning("plazo_informe_horas negativo (%d) → usando 48h HABILES", plazo_horas)
        plazo_horas = 48
        plazo_tipo = "HABILES"

    if plazo_horas == 0:
        return _ensure_utc(fecha_inicio)

    if plazo_tipo not in ("HABILES", "CALENDARIO"):
        logger.warning("plazo_tipo desconocido (%r) → tratando como HABILES", plazo_tipo)
        plazo_tipo = "HABILES"

    if plazo_tipo == "CALENDARIO":
        return _ensure_utc(fecha_inicio) + timedelta(hours=plazo_horas)

    # HABILES
    return await sumar_horas_habiles(fecha_inicio, plazo_horas, cliente_id, conn)


def calcular_vencimiento_medida_provisional(metadata: Optional[dict]) -> Optional[datetime]:
    """
    Retorna fecha de vencimiento de la medida provisional (plazo CALENDARIO) si la metadata
    la trae, o None en caso contrario.

    Espera estructura:
        metadata["medidas_provisionales"] = [
            {"plazo_horas": 24, "fecha_auto": "2026-04-23T10:00:00+00:00", ...},
            ...
        ]

    Solo considera la primera medida. Si falta `fecha_auto` o `plazo_horas`, retorna None.
    """
    if not metadata:
        return None

    medidas = metadata.get("medidas_provisionales")
    if not medidas or not isinstance(medidas, list):
        return None

    primera = medidas[0] if isinstance(medidas[0], dict) else None
    if not primera:
        return None

    plazo_horas_raw = primera.get("plazo_horas")
    fecha_auto_raw = primera.get("fecha_auto")

    if plazo_horas_raw is None or fecha_auto_raw is None:
        return None

    try:
        plazo_horas = int(plazo_horas_raw)
    except (TypeError, ValueError):
        logger.warning("medida_provisional.plazo_horas no numérico (%r)", plazo_horas_raw)
        return None

    if plazo_horas <= 0:
        return None

    fecha_auto: datetime
    if isinstance(fecha_auto_raw, datetime):
        fecha_auto = fecha_auto_raw
    else:
        try:
            fecha_auto = datetime.fromisoformat(str(fecha_auto_raw).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("medida_provisional.fecha_auto no parseable (%r)", fecha_auto_raw)
            return None

    return _ensure_utc(fecha_auto) + timedelta(hours=plazo_horas)
