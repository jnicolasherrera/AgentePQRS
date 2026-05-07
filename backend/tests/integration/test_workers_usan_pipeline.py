"""
Tests integración: los 3 workers (worker_ai_consumer, master_worker_outlook,
demo_worker) ahora invocan `pipeline.process_classified_event` en lugar de
hacer INSERT directo. Verifica la integración leyendo los archivos como texto
(evita imports pesados como pandas/aiokafka que no están en todo entorno).
"""
from __future__ import annotations

import inspect
from pathlib import Path

from app.services import pipeline


_BACKEND = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    return (_BACKEND / name).read_text(encoding="utf-8")


def test_pipeline_process_classified_event_existe():
    """Sanity: el contrato existe."""
    assert callable(pipeline.process_classified_event)
    sig = inspect.signature(pipeline.process_classified_event)
    params = list(sig.parameters.keys())
    assert params[:3] == ["clasificacion", "event", "cliente_id"]


def test_worker_ai_consumer_importa_pipeline():
    src = _read("worker_ai_consumer.py")
    assert "from app.services.pipeline import process_classified_event" in src
    assert "process_classified_event(" in src
    # No debería llamar directo a insert_pqrs_caso (la integración lo reemplazó).
    assert "from app.services.db_inserter import insert_pqrs_caso" not in src


def test_master_worker_importa_pipeline():
    src = _read("master_worker_outlook.py")
    assert "from app.services.pipeline import process_classified_event" in src
    assert "process_classified_event(" in src
    assert "from app.services.ai_classifier import ClassificationResult" in src


def test_demo_worker_importa_pipeline():
    src = _read("demo_worker.py")
    assert "from app.services.pipeline import process_classified_event" in src
    assert "process_classified_event(" in src
    assert "from app.services.ai_classifier import ClassificationResult" in src


def test_master_worker_preserva_post_insert_logic():
    """El refactor mantuvo la lógica de acuse + radicado + borrador."""
    src = _read("master_worker_outlook.py")
    assert "send_acuse_recibo" in src
    assert "generar_borrador_para_caso" in src


def test_demo_worker_preserva_post_insert_logic():
    """Demo worker mantiene generación de radicado y asignación de abogado."""
    src = _read("demo_worker.py")
    assert "save_adjuntos" in src or "adjuntos" in src
    assert "DEMO_ABOGADO_ID" in src


def test_master_y_demo_tienen_pool_minimo():
    """Ambos workers crean pool asyncpg para usar el pipeline."""
    src_master = _read("master_worker_outlook.py")
    src_demo = _read("demo_worker.py")
    assert "create_pool" in src_master
    assert "create_pool" in src_demo


def test_workers_preservan_dedup_external_msg_id():
    """Ambos workers tienen pre-check de dedup por external_msg_id."""
    src_master = _read("master_worker_outlook.py")
    src_demo = _read("demo_worker.py")
    assert "external_msg_id" in src_master
    assert "external_msg_id" in src_demo
