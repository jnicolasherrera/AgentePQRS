"""Tests del clasificador workflow PQRS vs ATENCION_CLIENTE (FlexFintech)."""

from __future__ import annotations

import pytest

from app.services.workflow_classifier import clasificar_workflow


class TestDomainsJudiciales:
    """Cualquier sender judicial → PQRS, sin importar contenido."""

    @pytest.mark.parametrize("sender", [
        "juzgado05civil@ramajudicial.gov.co",
        "secretaria@cendoj.ramajudicial.gov.co",
        "notif@juzgado12.gov",
        "tribunal-sup@tribunal.gov.co",
    ])
    def test_sender_judicial_siempre_pqrs(self, sender):
        # Texto sin keywords legales — igual debe ir a PQRS
        assert clasificar_workflow(
            asunto="Solicito paz y salvo",  # keyword AC fuerte
            cuerpo="Necesito mi certificado de cancelación",  # otra AC
            sender=sender,
        ) == "PQRS"


class TestPqrsKeywords:
    """Keywords legales explícitas → PQRS."""

    @pytest.mark.parametrize("asunto,cuerpo", [
        ("Acción de tutela urgente", "Vulneración de derecho fundamental"),
        ("Derecho de petición", "Solicito información sobre mi caso"),
        ("Habeas data", "Quiero ejercer mis derechos"),
        ("Reclamo formal Superintendencia Financiera", ""),
        ("", "Decreto 2591 de 1991 aplicable a mi caso"),
        ("Queja formal por incumplimiento", "Ley 1755 de 2015"),
    ])
    def test_pqrs_fuerte(self, asunto, cuerpo):
        assert clasificar_workflow(asunto, cuerpo) == "PQRS"


class TestAtencionClienteKeywords:
    """Keywords operativas explícitas → ATENCION_CLIENTE."""

    @pytest.mark.parametrize("asunto,cuerpo", [
        ("Solicito paz y salvo", "Por favor enviarme el certificado de cancelación"),
        ("Adjunto comprobante de pago", "Para que actualicen mi obligación"),
        ("Mi obligación cancelada", "Necesito el libre de deuda"),
        ("", "Necesito mi paz y salvo de Rapicredit"),
        ("Estado de mi obligación", ""),
    ])
    def test_ac_fuerte(self, asunto, cuerpo):
        assert clasificar_workflow(asunto, cuerpo) == "ATENCION_CLIENTE"


class TestEmpateYAmbiguedad:
    """Cuando matchean ambas → PQRS gana (conservador legal)."""

    def test_empate_gana_pqrs(self):
        # Empate exacto: 1 fuerte PQRS vs 1 fuerte AC, ningún tie-breaker.
        # Score: PQRS = +2 (acción de tutela) + 1 (tutela medio) = 3
        #        AC   = +2 (paz y salvo) = 2
        # Hmm — la presencia de "tutela" como keyword media siempre desempata
        # naturalmente a favor de PQRS. Probemos un caso de empate real con
        # texto que no tenga keywords medias inflacionarias.
        # PQRS solo "habeas data" (fuerte +2), AC solo "comprobante de pago" (fuerte +2)
        assert clasificar_workflow(
            asunto="Habeas data + comprobante de pago",
            cuerpo="",
        ) == "PQRS"  # empate exacto → conservador

    def test_ac_gana_si_supera_pqrs(self):
        # 2 AC fuertes vs 1 PQRS fuerte → AC gana
        assert clasificar_workflow(
            asunto="Acción de tutela por mi paz y salvo",
            cuerpo="No me entregan el certificado de cancelación",
        ) == "ATENCION_CLIENTE"

    def test_keywords_medias_solo_pqrs(self):
        # Sólo "queja" (media PQRS), nada de AC
        assert clasificar_workflow(
            asunto="Tengo una queja",
            cuerpo="No me atendieron bien",
        ) == "PQRS"

    def test_keywords_medias_solo_ac(self):
        # Sólo "comprobante" + "consulta" (medias AC), nada de PQRS
        assert clasificar_workflow(
            asunto="Adjunto comprobante",
            cuerpo="Una consulta sobre mi saldo",
        ) == "ATENCION_CLIENTE"


class TestDefaultFallback:
    """Texto sin keywords identificables → cae al default_workflow."""

    def test_sin_keywords_default_pqrs(self):
        # Default = PQRS (conservador)
        assert clasificar_workflow(
            asunto="Hola",
            cuerpo="Quería contactarme con ustedes.",
        ) == "PQRS"

    def test_sin_keywords_default_override_ac(self):
        # Si el buzón configurado es ATENCION_CLIENTE, fallback va por ahí
        assert clasificar_workflow(
            asunto="Hola",
            cuerpo="Quería contactarme",
            default_workflow="ATENCION_CLIENTE",
        ) == "ATENCION_CLIENTE"

    def test_inputs_vacios_default(self):
        assert clasificar_workflow("", "", "") == "PQRS"  # default
        assert clasificar_workflow("", "", "", default_workflow="ATENCION_CLIENTE") == "ATENCION_CLIENTE"


class TestEscenariosReales:
    """Samples reales del buzón clientes@flexfintech.com — vistos en el recon."""

    def test_solicitud_paz_y_salvo_real(self):
        # Lo vimos en 03. Flex Colombia: "CO - Re: Solicitud de paz y Salvo"
        assert clasificar_workflow(
            asunto="CO - Re: Solicitud de paz y Salvo",
            cuerpo="Buenas tardes, necesito mi paz y salvo de la deuda cancelada hace 3 meses.",
            sender="bautistaedinson9@gmail.com",
        ) == "ATENCION_CLIENTE"

    def test_derecho_peticion_real(self):
        # Otro caso real: "CO - Derecho de petición rayner lizcano"
        assert clasificar_workflow(
            asunto="CO - Derecho de petición rayner lizcano",
            cuerpo="En ejercicio del derecho de petición consagrado en el art. 23...",
            sender="alizcano28@gmail.com",
        ) == "PQRS"

    def test_tutela_de_juzgado_real(self):
        # Notificación judicial — debe ir a PQRS por dominio
        assert clasificar_workflow(
            asunto="Notificación acción de tutela",
            cuerpo="Adjunto auto de admisión",
            sender="juzgado05civil@ramajudicial.gov.co",
        ) == "PQRS"
