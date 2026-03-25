import pytest
from app.services.scoring_engine import (
    score_email, apply_context_signals, compute_confidence, score_and_classify
)


class TestWordBoundaries:
    def test_reclamatorio_does_not_match_reclamo(self):
        scores = score_email("Asunto reclamatorio", "")
        assert scores.get("RECLAMO", 0) == 0

    def test_exact_reclamo_matches(self):
        scores = score_email("Reclamo por cobro indebido", "")
        assert scores.get("RECLAMO", 0) > 0

    def test_competicion_does_not_match_peticion(self):
        scores = score_email("Competicion deportiva", "")
        assert scores.get("PETICION", 0) == 0

    def test_exact_peticion_matches(self):
        scores = score_email("Petición formal", "")
        assert scores.get("PETICION", 0) > 0

    def test_prejuzgado_does_not_match_juzgado(self):
        scores = score_email("", "Fue prejuzgado por la sociedad")
        assert scores.get("TUTELA", 0) == 0


class TestWeightedScoring:
    def test_accion_tutela_high_weight(self):
        scores = score_email("Acción de tutela", "")
        assert scores.get("TUTELA", 0) >= 6.0

    def test_juez_low_weight(self):
        scores = score_email("", "El juez dijo algo")
        assert scores.get("TUTELA", 0) <= 2.0

    def test_derecho_peticion_high_weight(self):
        scores = score_email("Derecho de petición", "")
        assert scores.get("PETICION", 0) >= 6.0

    def test_subject_multiplier(self):
        score_subject = score_email("tutela", "")
        score_body = score_email("", "tutela")
        assert score_subject.get("TUTELA", 0) > score_body.get("TUTELA", 0)

    def test_solicitud_not_overwhelmed_by_tutela(self):
        scores = score_email("Solicitud formal de documentos", "Necesito que me envíen la certificación")
        assert scores.get("SOLICITUD", 0) > 0


class TestZoneAwareness:
    def test_queja_in_subject_higher_than_body(self):
        s1 = score_email("Queja por mal servicio", "")
        s2 = score_email("", "Queja por mal servicio")
        assert s1.get("QUEJA", 0) > s2.get("QUEJA", 0)

    def test_informacion_only_in_body(self):
        s1 = score_email("Información general", "")
        s2 = score_email("", "Necesito información")
        assert s2.get("PETICION", 0) > 0


class TestContextSignals:
    def test_court_sender_with_tutela_keyword(self):
        base = score_email("Tutela contra empresa", "")
        boosted = apply_context_signals(base, "Tutela contra empresa", "", "notificaciones@ramajudicial.gov.co")
        assert boosted.get("TUTELA", 0) > base.get("TUTELA", 0)
        boost_diff = boosted.get("TUTELA", 0) - base.get("TUTELA", 0)
        assert boost_diff == pytest.approx(4.0, abs=0.5)

    def test_court_sender_without_tutela_keyword(self):
        base = score_email("Circular informativa", "")
        boosted = apply_context_signals(base, "Circular informativa", "", "secretaria@ramajudicial.gov.co")
        boost_diff = boosted.get("TUTELA", 0) - base.get("TUTELA", 0)
        assert boost_diff == pytest.approx(1.0, abs=0.5)

    def test_urgente_in_subject_boosts_tutela(self):
        base = {"TUTELA": 2.0}
        boosted = apply_context_signals(base, "URGENTE: caso pendiente", "", "user@test.com")
        assert boosted.get("TUTELA", 0) > base.get("TUTELA", 0)

    def test_does_not_mutate_input(self):
        original = {"TUTELA": 5.0, "PETICION": 3.0}
        original_copy = dict(original)
        apply_context_signals(original, "urgente", "", "test@ramajudicial.gov.co")
        assert original == original_copy


class TestConfidence:
    def test_no_scores_returns_peticion(self):
        tipo, conf = compute_confidence({})
        assert tipo == "PETICION"
        assert conf == 0.30

    def test_all_zero_returns_peticion(self):
        tipo, conf = compute_confidence({"TUTELA": 0, "PETICION": 0})
        assert tipo == "PETICION"
        assert conf == 0.30

    def test_high_score_high_margin(self):
        tipo, conf = compute_confidence({"TUTELA": 12.0, "PETICION": 2.0})
        assert tipo == "TUTELA"
        assert conf >= 0.95

    def test_medium_score_medium_margin(self):
        tipo, conf = compute_confidence({"PETICION": 7.0, "SOLICITUD": 2.0})
        assert tipo == "PETICION"
        assert conf >= 0.85

    def test_low_score_returns_low_confidence(self):
        tipo, conf = compute_confidence({"SOLICITUD": 1.5})
        assert tipo == "SOLICITUD"
        assert conf <= 0.60

    def test_close_scores_lower_confidence(self):
        tipo, conf = compute_confidence({"TUTELA": 5.0, "PETICION": 4.5})
        assert conf < 0.85


class TestEndToEnd:
    def test_clear_tutela_email(self):
        tipo, conf, _ = score_and_classify(
            "Acción de tutela - Derechos fundamentales",
            "Se interpone acción de tutela por vulneración de derechos fundamentales decreto 2591",
            "notificaciones@ramajudicial.gov.co"
        )
        assert tipo == "TUTELA"
        assert conf >= 0.92

    def test_clear_peticion_email(self):
        tipo, conf, _ = score_and_classify(
            "Derecho de petición - Solicitud de información",
            "En ejercicio del derecho de petición consagrado en la ley 1755",
            "ciudadano@gmail.com"
        )
        assert tipo == "PETICION"
        assert conf >= 0.85

    def test_clear_queja_email(self):
        tipo, conf, _ = score_and_classify(
            "Queja formal por mal servicio",
            "Presento queja por la inconformidad con el servicio deficiente recibido",
            "usuario@hotmail.com"
        )
        assert tipo == "QUEJA"
        assert conf >= 0.72

    def test_clear_reclamo_email(self):
        tipo, conf, _ = score_and_classify(
            "Reclamo por cobro indebido",
            "Solicito devolución por un cargo no reconocido en mi factura",
            "cliente@outlook.com"
        )
        assert tipo == "RECLAMO"
        assert conf >= 0.85

    def test_no_keywords_defaults_to_peticion(self):
        tipo, conf, _ = score_and_classify(
            "Hola buenos días",
            "Le escribo para saludarlo",
            "alguien@gmail.com"
        )
        assert tipo == "PETICION"
        assert conf == 0.30

    def test_accent_variants_both_match(self):
        t1, _, _ = score_and_classify("Acción de tutela", "", "")
        t2, _, _ = score_and_classify("Accion de tutela", "", "")
        assert t1 == "TUTELA"
        assert t2 == "TUTELA"
