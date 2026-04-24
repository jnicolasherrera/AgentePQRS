"""Tests del semáforo polimórfico extendido al scoring_engine (sprint Tutelas)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.scoring_engine import SEMAFORO_CONFIG, calcular_semaforo


# Helper: construir fechas relativas a un "ahora" fijo.
AHORA = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)


def _caso(creado_hace_horas: float, vence_en_horas: float) -> tuple[datetime, datetime]:
    return (
        AHORA - timedelta(hours=creado_hace_horas),
        AHORA + timedelta(hours=vence_en_horas),
    )


# ── TUTELA — 5 colores ──────────────────────────────────────────────

def test_tutela_verde_cuando_resta_mas_de_50pct():
    # Plazo total 48h, creado hace 10h, restan 38h → 38/48 ≈ 79% > 50% → VERDE.
    creacion, vencimiento = _caso(10, 38)
    assert calcular_semaforo("TUTELA", creacion, vencimiento, AHORA) == "VERDE"


def test_tutela_amarillo_entre_25_y_50():
    # Plazo 40h, creado hace 30h, restan 10h → 10/40 = 25% → AMARILLO (en el borde inferior).
    creacion, vencimiento = _caso(30, 10)
    assert calcular_semaforo("TUTELA", creacion, vencimiento, AHORA) == "AMARILLO"


def test_tutela_naranja_entre_10_y_25():
    # Plazo 40h, creado hace 34h, restan 6h → 6/40 = 15% → NARANJA.
    creacion, vencimiento = _caso(34, 6)
    assert calcular_semaforo("TUTELA", creacion, vencimiento, AHORA) == "NARANJA"


def test_tutela_rojo_debajo_de_10pct_no_vencido():
    # Plazo 50h, creado hace 48h, restan 2h → 2/50 = 4% → ROJO.
    creacion, vencimiento = _caso(48, 2)
    assert calcular_semaforo("TUTELA", creacion, vencimiento, AHORA) == "ROJO"


def test_tutela_negro_cuando_vencido():
    # Plazo 24h, creado hace 30h, ya venció 6h → NEGRO.
    creacion, vencimiento = _caso(30, -6)
    assert calcular_semaforo("TUTELA", creacion, vencimiento, AHORA) == "NEGRO"


# ── PQRS_DEFAULT — sin NARANJA, sin NEGRO ────────────────────────────

def test_pqrs_default_nunca_naranja():
    # Plazo 40h, creado hace 34h, restan 6h → 15%. En tutela sería NARANJA;
    # en PQRS debería saltar directo a ROJO.
    creacion, vencimiento = _caso(34, 6)
    assert calcular_semaforo("PETICION", creacion, vencimiento, AHORA) == "ROJO"


def test_pqrs_vencido_es_rojo_no_negro():
    creacion, vencimiento = _caso(30, -6)
    # PETICION no está en SEMAFORO_CONFIG → usa PQRS_DEFAULT.
    assert calcular_semaforo("PETICION", creacion, vencimiento, AHORA) == "ROJO"
    assert calcular_semaforo("QUEJA", creacion, vencimiento, AHORA) == "ROJO"


def test_pqrs_verde_cuando_mucho_tiempo_restante():
    creacion, vencimiento = _caso(2, 100)  # 2h creado, restan 100h → mucho tiempo.
    assert calcular_semaforo("RECLAMO", creacion, vencimiento, AHORA) == "VERDE"


def test_pqrs_amarillo_entre_20_y_50():
    # 40h plazo, creado hace 30h, restan 10h → 25% → AMARILLO.
    creacion, vencimiento = _caso(30, 10)
    assert calcular_semaforo("RECLAMO", creacion, vencimiento, AHORA) == "AMARILLO"


# ── Config integrity ────────────────────────────────────────────────

def test_config_default_tiene_todas_claves():
    cfg = SEMAFORO_CONFIG["PQRS_DEFAULT"]
    for key in ("verde_hasta_pct", "amarillo_hasta_pct", "rojo_hasta_pct",
                "negro_si_vencido", "escalar_representante_legal_en_rojo"):
        assert key in cfg


def test_config_tutela_tiene_naranja():
    assert SEMAFORO_CONFIG["TUTELA"]["naranja_hasta_pct"] is not None
    assert SEMAFORO_CONFIG["TUTELA"]["negro_si_vencido"] is True
    assert SEMAFORO_CONFIG["TUTELA"]["escalar_representante_legal_en_rojo"] is True


def test_tipo_desconocido_usa_pqrs_default():
    creacion, vencimiento = _caso(30, -6)
    # "INVENTADO" no existe → cae a PQRS_DEFAULT, por ende ROJO (no NEGRO).
    assert calcular_semaforo("INVENTADO", creacion, vencimiento, AHORA) == "ROJO"
