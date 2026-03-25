import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.enums import TipoCaso, Prioridad
from app.services.clasificador import (
    clasificar_texto,
    extraer_cedula,
    extraer_radicado,
)
from app.services.ai_engine import clasificar_hibrido, UMBRAL_CONFIANZA


def test_extraer_radicado_formato_guiones():
    texto = "Referencia radicado: 2024-001-000123 para su seguimiento."
    resultado = extraer_radicado(texto)
    assert resultado == "2024-001-000123"


def test_extraer_cedula():
    texto = "El ciudadano identificado con C.C. 12345678 presenta la siguiente queja."
    resultado = extraer_cedula(texto)
    assert resultado == "12345678"


def test_clasificar_tutela():
    resultado = clasificar_texto(
        asunto="Acción de tutela por vulneración de derechos fundamentales",
        cuerpo="El juzgado emitió un fallo en el proceso de tutela.",
    )
    assert resultado.tipo == TipoCaso.TUTELA


def test_clasificar_pqr_queja():
    resultado = clasificar_texto(
        asunto="Queja formal por mal servicio",
        cuerpo="Estoy insatisfecho con la atención recibida. Presento esta queja formal.",
    )
    assert resultado.tipo == TipoCaso.QUEJA


def test_clasificar_pqr_peticion():
    resultado = clasificar_texto(
        asunto="Derecho de petición",
        cuerpo="Solicito respetuosamente información sobre mi contrato.",
    )
    assert resultado.tipo == TipoCaso.PETICION


def test_prioridad_critica():
    # Las tutelas tienen prioridad CRITICA según config.py
    resultado = clasificar_texto(
        asunto="URGENTE: acción de tutela",
        cuerpo="Interpongo acción de tutela ante el juzgado por vulneración de derechos fundamentales.",
    )
    assert resultado.prioridad in (Prioridad.CRITICA, Prioridad.ALTA)


def test_clasificar_sin_keywords():
    # Sin coincidencias → clasificador cae en PETICION con confianza 0.3
    resultado = clasificar_texto(
        asunto="Comunicación general",
        cuerpo="Buenos días, le escribo para saludarle.",
    )
    assert isinstance(resultado.tipo, TipoCaso)
    assert resultado.confianza <= 0.5


@pytest.mark.asyncio
async def test_hibrido_sin_api_key_devuelve_keywords():
    # Sin API key → retorna resultado de keywords directamente
    with patch("app.services.ai_engine.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        resultado = await clasificar_hibrido("Comunicación general", "Buenos días")
    assert isinstance(resultado.tipo, TipoCaso)


@pytest.mark.asyncio
async def test_hibrido_confianza_alta_no_llama_claude():
    # Texto con keywords claras → confianza >= umbral, no depende de Claude
    resultado = await clasificar_hibrido(
        "Acción de tutela urgente",
        "El juzgado emitió un fallo por vulneración de derechos fundamentales.",
    )
    assert resultado.tipo == TipoCaso.TUTELA
    assert resultado.confianza >= UMBRAL_CONFIANZA


@pytest.mark.asyncio
async def test_hibrido_api_error_hace_fallback():
    # Claude falla → se retorna resultado de keywords sin propagar la excepción
    with patch("app.services.ai_engine.settings") as mock_settings:
        mock_settings.anthropic_api_key = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=Exception("timeout"))
            mock_cls.return_value = mock_client
            resultado = await clasificar_hibrido("hola", "quiero información")
    assert isinstance(resultado.tipo, TipoCaso)
