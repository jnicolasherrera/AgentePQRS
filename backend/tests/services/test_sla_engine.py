"""Tests unitarios de sla_engine (sprint Tutelas)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.sla_engine import (
    calcular_vencimiento_medida_provisional,
    calcular_vencimiento_tutela,
    sumar_horas_habiles,
)


@pytest.fixture
def no_conn():
    """Fallback de festivos fijos 2026 (sin conn)."""
    return None


# ── sumar_horas_habiles ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sumar_48h_habiles_desde_lunes_9am_martes_mitad(no_conn):
    # Lunes 2026-04-20 9:00 UTC + 48h hábiles.
    # 8h/día hábil → 48h = 6 días hábiles. Lunes→martes(1), mié(2), jue(3), vie(4), lun(5), mar(6).
    # Pero las 9:00 no es inicio de jornada (08:00); hay 7h restantes del lunes (9-12 + 13-17 = 3+4 = 7).
    # Tras 7h estamos a final lunes 17:00. Quedan 41h = 5 días de 8h + 1h = resto fin martes 17h + 1h miércoles 09:00.
    # Entonces: +48h hábiles desde lunes 9:00 → martes siguiente semana? No.
    # Recalculemos: 48h / 8h-día = 6 días hábiles. Empezamos desde lunes 9:00 (dentro de jornada, 7h disponibles).
    # Necesitamos sumar 48h. Después de 7h estamos en lunes 17:00 (fin jornada); queda 41h.
    # Día hábil siguiente (martes 08:00) + 8h = martes 17:00; restan 33h.
    # Miércoles +8h=17:00, quedan 25h. Jueves +8h=17:00, quedan 17h. Viernes +8h=17:00, quedan 9h.
    # Lunes +8h=17:00, quedan 1h. Martes +1h = martes 09:00 de la semana siguiente.
    # Lunes 20-abr + 7 días hábiles y 1h → martes 28-abr 09:00.
    inicio = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    resultado = await sumar_horas_habiles(inicio, 48, None, no_conn)
    assert resultado == datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_sumar_48h_habiles_desde_viernes_9am_cae_martes(no_conn):
    # Viernes 2026-04-24 9:00 + 48h hábiles. Mismo conteo: 6 días hábiles.
    # vie 9:00 (7h hasta 17:00), lun(+8h), mar(+8h), mié(+8h), jue(+8h), vie(+8h=17:00 quedan 1h), lun+1h=lun 09:00.
    # No hay festivos en el rango 24-abr a 4-may (el 1-may cae viernes, es festivo → se salta).
    # vie 24 9:00 +7h = vie 17:00 (quedan 41h).
    # lun 27 +8h = lun 17:00 (33h).
    # mar 28 +8h (25h).
    # mié 29 +8h (17h).
    # jue 30 +8h (9h).
    # vie 1-may = FESTIVO → salta.
    # lun 4 +8h = lun 17:00 (1h).
    # mar 5 +1h = mar 09:00.
    inicio = datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc)
    resultado = await sumar_horas_habiles(inicio, 48, None, no_conn)
    assert resultado == datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_sumar_habiles_salta_festivo_1mayo(no_conn):
    # Jueves 2026-04-30 10:00 + 16h hábiles = 2 días hábiles.
    # jue 30 10:00 (2h hasta 12 + 4h tarde = 6h hasta 17:00) → jue 17:00, quedan 10h.
    # vie 1-may festivo → salta.
    # lun 4-may +8h (mañana 4 + tarde 4) = lun 17:00, quedan 2h.
    # mar 5 +2h = mar 10:00.
    inicio = datetime(2026, 4, 30, 10, 0, tzinfo=timezone.utc)
    resultado = await sumar_horas_habiles(inicio, 16, None, no_conn)
    assert resultado == datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_sumar_0_horas_retorna_inicio(no_conn):
    inicio = datetime(2026, 4, 23, 15, 30, tzinfo=timezone.utc)
    resultado = await sumar_horas_habiles(inicio, 0, None, no_conn)
    assert resultado == inicio


@pytest.mark.asyncio
async def test_sumar_horas_negativas_raises(no_conn):
    inicio = datetime(2026, 4, 23, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        await sumar_horas_habiles(inicio, -1, None, no_conn)


@pytest.mark.asyncio
async def test_inicio_fin_de_semana_se_ajusta_al_lunes(no_conn):
    # Sábado 2026-04-25 10:00 + 8h hábiles = 1 día hábil.
    # Se ajusta al siguiente lunes 08:00. +8h = lunes 17:00.
    inicio = datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)
    resultado = await sumar_horas_habiles(inicio, 8, None, no_conn)
    assert resultado == datetime(2026, 4, 27, 17, 0, tzinfo=timezone.utc)


# ── calcular_vencimiento_tutela ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tutela_calendario_24h_sabado_domingo(no_conn):
    # Sábado 2026-04-25 10:00 + 24h CALENDARIO = domingo 10:00.
    inicio = datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)
    metadata = {"plazo_informe_horas": 24, "plazo_tipo": "CALENDARIO"}
    resultado = await calcular_vencimiento_tutela(inicio, metadata, None, no_conn)
    assert resultado == datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_tutela_habiles_default_48h_si_metadata_vacia(no_conn):
    # Sin plazo → default 48h HABILES + warn.
    inicio = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    resultado = await calcular_vencimiento_tutela(inicio, None, None, no_conn)
    # Mismo resultado que test de 48h hábiles desde lunes 9am.
    assert resultado == datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_tutela_plazo_tipo_desconocido_trata_como_habiles(no_conn, caplog):
    inicio = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    metadata = {"plazo_informe_horas": 48, "plazo_tipo": "RARO"}
    resultado = await calcular_vencimiento_tutela(inicio, metadata, None, no_conn)
    assert resultado == datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_tutela_horas_cero_retorna_inicio(no_conn):
    inicio = datetime(2026, 4, 23, 10, 0, tzinfo=timezone.utc)
    metadata = {"plazo_informe_horas": 0, "plazo_tipo": "CALENDARIO"}
    resultado = await calcular_vencimiento_tutela(inicio, metadata, None, no_conn)
    assert resultado == inicio


@pytest.mark.asyncio
async def test_tutela_horas_negativas_usa_default(no_conn):
    inicio = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    metadata = {"plazo_informe_horas": -5, "plazo_tipo": "HABILES"}
    resultado = await calcular_vencimiento_tutela(inicio, metadata, None, no_conn)
    # Se trata como 48h HABILES.
    assert resultado == datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_tutela_horas_no_numericas_usa_default(no_conn):
    inicio = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    metadata = {"plazo_informe_horas": "diez", "plazo_tipo": "HABILES"}
    resultado = await calcular_vencimiento_tutela(inicio, metadata, None, no_conn)
    assert resultado == datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)


# ── medida provisional ──────────────────────────────────────────────

def test_medida_provisional_calendario_12h():
    metadata = {
        "medidas_provisionales": [
            {"plazo_horas": 12, "fecha_auto": "2026-04-23T10:00:00+00:00"},
        ]
    }
    resultado = calcular_vencimiento_medida_provisional(metadata)
    assert resultado == datetime(2026, 4, 23, 22, 0, tzinfo=timezone.utc)


def test_medida_provisional_sin_metadata_retorna_none():
    assert calcular_vencimiento_medida_provisional(None) is None
    assert calcular_vencimiento_medida_provisional({}) is None
    assert calcular_vencimiento_medida_provisional({"medidas_provisionales": []}) is None


def test_medida_provisional_plazo_cero_retorna_none():
    metadata = {
        "medidas_provisionales": [
            {"plazo_horas": 0, "fecha_auto": "2026-04-23T10:00:00+00:00"},
        ]
    }
    assert calcular_vencimiento_medida_provisional(metadata) is None


# ── festivos con conn real simulada ─────────────────────────────────

@pytest.mark.asyncio
async def test_obtener_festivos_usa_conn_cuando_disponible():
    """El engine consulta festivos_colombia cuando hay conn."""
    mock_conn = AsyncMock()
    # Simula la tabla completa con solo 1 festivo: miércoles 2026-04-22.
    mock_conn.fetch = AsyncMock(return_value=[{"fecha": datetime(2026, 4, 22).date()}])

    # lunes 20-abr 9:00 + 16h (2 días hábiles). Sin festivos cae martes 17h + 1h = no llega.
    # 16h: lun 9→17 (7h), mar (9h → 8h) mar 17:00 restan 1h → mié+1h=mié 09:00.
    # CON festivo miércoles: mar 17:00 restan 1h, mié es festivo → salta, jue +1h = jue 09:00.
    inicio = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    resultado = await sumar_horas_habiles(inicio, 16, None, mock_conn)
    assert resultado == datetime(2026, 4, 23, 9, 0, tzinfo=timezone.utc)
