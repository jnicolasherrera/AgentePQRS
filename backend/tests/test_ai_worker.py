"""
test_ai_worker.py — Sprint 4 QA: Worker AI Consumer
Batería de 7 tests: retry exponencial, DLQ y happy path.
asyncio_mode = auto en pytest.ini — no requiere @pytest.mark.asyncio.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, call

import anthropic
import pytest

from app.services.ai_classifier import (
    ClassificationResult,
    PoisonPillError,
    classify_email_event,
    MAX_RETRIES,
    RETRY_BASE_SECONDS,
)
from worker_ai_consumer import _process_message, _send_to_dlq


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _make_rate_limit_error() -> anthropic.RateLimitError:
    return anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(),
        body={},
    )


def _mock_resultado_hibrido() -> SimpleNamespace:
    """Simula el objeto que retorna clasificar_hibrido() de ai_engine.py."""
    return SimpleNamespace(
        tipo=SimpleNamespace(value="PETICION"),
        cedula=None,
        nombre_cliente=None,
        es_juzgado=False,
        confianza=0.9,
    )


def _make_kafka_msg(tenant_id: str = "tenant_abc", correlation_id: str = "corr-001"):
    payload = {
        "subject": "Petición de prueba",
        "body": "Cuerpo de la petición",
        "sender": "usuario@test.com",
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
    }
    msg = MagicMock()
    msg.value = json.dumps(payload).encode("utf-8")
    return msg


def _make_classification_result() -> ClassificationResult:
    return ClassificationResult(
        tipo_caso="PETICION",
        prioridad="MEDIA",
        plazo_dias=15,
        cedula=None,
        nombre_cliente=None,
        es_juzgado=False,
        confianza=0.9,
        borrador=None,
    )


# ── Bloque A: classify_email_event ──────────────────────────────────────────────

class TestClassifyEmailEvent:

    async def test_classify_success_on_first_attempt(self):
        """Clasificación exitosa en el primer intento — sin sleeps."""
        with patch(
            "app.services.ai_classifier.clasificar_hibrido",
            new=AsyncMock(return_value=_mock_resultado_hibrido()),
        ):
            result = await classify_email_event(
                {"subject": "Petición", "body": "...", "sender": "a@b.com"}
            )

        assert isinstance(result, ClassificationResult)
        assert result.tipo_caso == "PETICION"
        assert result.prioridad == "MEDIA"

    async def test_classify_retries_on_rate_limit_then_succeeds(self):
        """2 RateLimitError → éxito en el intento 3. Sleep con backoff 2s, 4s."""
        rate_err = _make_rate_limit_error()
        mock_hibrido = AsyncMock(
            side_effect=[rate_err, rate_err, _mock_resultado_hibrido()]
        )
        with (
            patch("app.services.ai_classifier.clasificar_hibrido", new=mock_hibrido),
            patch("app.services.ai_classifier.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            result = await classify_email_event(
                {"subject": "Petición", "body": "...", "sender": "a@b.com"}
            )

        assert isinstance(result, ClassificationResult)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(2.0), call(4.0)])

    async def test_classify_raises_poison_pill_after_max_retries(self):
        """MAX_RETRIES=5 RateLimitErrors consecutivos → PoisonPillError. Sleep llamado 4 veces."""
        mock_hibrido = AsyncMock(side_effect=[_make_rate_limit_error()] * MAX_RETRIES)
        with (
            patch("app.services.ai_classifier.clasificar_hibrido", new=mock_hibrido),
            patch("app.services.ai_classifier.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            with pytest.raises(PoisonPillError):
                await classify_email_event(
                    {"subject": "Petición", "body": "...", "sender": "a@b.com"}
                )

        # El sleep se llama en los intentos 0..3; el intento 4 lanza PoisonPillError sin sleep
        assert mock_sleep.call_count == MAX_RETRIES - 1

    async def test_classify_adjunto_uri_enriquece_cuerpo(self):
        """Si hay adjunto_s3_uri, el contenido descargado se añade al cuerpo."""
        mock_hibrido = AsyncMock(return_value=_mock_resultado_hibrido())
        with (
            patch(
                "app.services.ai_classifier._descargar_adjunto",
                new=AsyncMock(return_value=b"contenido del adjunto"),
            ),
            patch("app.services.ai_classifier.clasificar_hibrido", new=mock_hibrido),
        ):
            await classify_email_event({
                "subject": "Test",
                "body": "cuerpo base",
                "sender": "x@y.com",
                "adjunto_s3_uri": "tenant/test.txt",
            })

        cuerpo_enviado = mock_hibrido.call_args.args[1]
        assert "[ADJUNTO]: contenido" in cuerpo_enviado


# ── Bloque B: _process_message ─────────────────────────────────────────────────

class TestProcessMessage:

    async def test_process_message_happy_path(self):
        """Flujo completo: clasificación OK → insert DB → Redis publish en canal correcto."""
        msg = _make_kafka_msg(tenant_id="tenant_xyz", correlation_id="corr-happy")
        pool = AsyncMock()
        r = AsyncMock()
        producer = AsyncMock()

        with (
            patch(
                "worker_ai_consumer.classify_email_event",
                new=AsyncMock(return_value=_make_classification_result()),
            ),
            patch(
                "worker_ai_consumer.insert_pqrs_caso",
                new=AsyncMock(return_value="caso-uuid-123"),
            ) as mock_insert,
        ):
            await _process_message(msg, pool, r, producer)

        mock_insert.assert_called_once()
        r.publish.assert_called_once()
        assert r.publish.call_args.args[0] == "pqrs.events.tenant_xyz"

    async def test_process_message_sends_to_dlq_on_poison_pill(self):
        """PoisonPillError → DLQ llamada, excepción capturada sin propagar."""
        msg = _make_kafka_msg()
        pool = AsyncMock()
        r = AsyncMock()
        producer = AsyncMock()

        with (
            patch(
                "worker_ai_consumer.classify_email_event",
                new=AsyncMock(side_effect=PoisonPillError("test error")),
            ),
            patch("worker_ai_consumer._send_to_dlq", new=AsyncMock()) as mock_dlq,
        ):
            await _process_message(msg, pool, r, producer)  # no debe lanzar

        mock_dlq.assert_called_once()

    async def test_send_to_dlq_formats_event_correctly(self):
        """_send_to_dlq publica al topic dead_letter con correlation_id y failure_reason."""
        producer_mock = AsyncMock()

        await _send_to_dlq(
            producer_mock,
            b'{"test": "data"}',
            "corr-123",
            "Test error",
        )

        producer_mock.send_and_wait.assert_called_once()
        assert producer_mock.send_and_wait.call_args.args[0] == "pqrs.events.dead_letter"

        value_bytes = producer_mock.send_and_wait.call_args.kwargs["value"]
        dlq_payload = json.loads(value_bytes.decode("utf-8"))
        assert dlq_payload["correlation_id"] == "corr-123"
        assert dlq_payload["failure_reason"] == "Test error"
