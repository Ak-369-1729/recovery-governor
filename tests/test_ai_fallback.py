import pytest
from app.models.enums import FailureType, ActionType, AIMode
from app.models.schemas import AIDiagnosisOutput
from app.engine.fallback import DeterministicFallbackEngine
from app.engine.diagnosis import AIDiagnosisEngine

def test_fallback_engine_all_failure_types():
    failures = list(FailureType)
    for f in failures:
        payment = {
            "payment_id": "pay_test_f",
            "amount": 1500.0,
            "failure_type": f.value,
            "payment_method": "UPI",
            "retry_count": 0,
            "risk_tier": "LOW",
            "channel": "MOBILE_APP"
        }
        res = DeterministicFallbackEngine.diagnose(payment)
        assert isinstance(res, AIDiagnosisOutput)
        assert res.confidence > 0.0
        assert len(res.candidate_actions) > 0
        assert isinstance(res.candidate_actions[0].action, ActionType)

def test_ai_diagnosis_graceful_fallback_without_key(monkeypatch):
    from app.config import settings
    # Ensure no Gemini key
    monkeypatch.setattr(settings, "gemini_api_key", "")
    
    payment = {
        "payment_id": "pay_test_no_key",
        "amount": 2000.0,
        "failure_type": FailureType.TEMPORARY_ISSUER_FAILURE.value,
        "payment_method": "UPI"
    }
    diagnosis, mode = AIDiagnosisEngine.diagnose(payment)
    assert mode == AIMode.DETERMINISTIC_FALLBACK
    assert isinstance(diagnosis, AIDiagnosisOutput)
    assert diagnosis.confidence >= 0.50
