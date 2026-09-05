import pytest
from app.models.enums import VerificationStatus, AttributionCategory, ActionType, FailureType
from app.models.schemas import ExecutionResult, GovernorDecision, AIDiagnosisOutput, CandidateActionProposal
from app.engine.verifier import VerificationEngine
from app.engine.attribution import RecoveryAttributionEngine
from app.engine.governor import RecoveryGovernor
from app.models.database import init_db

@pytest.fixture(autouse=True)
def setup():
    init_db()

def test_verification_unknown_safety_handling():
    # Force verification state to UNKNOWN
    mock_exec = ExecutionResult(
        execution_id="exec_test_unk",
        decision_id="dec_test_unk",
        payment_id="pay_test_unk",
        action=ActionType.RETRY_NOW,
        adapter_type="SIMULATION",
        status="EXECUTED",
        response_payload={},
        idempotency_key="idem_test_unk",
        timestamp="2026-09-01T12:00:00Z"
    )
    payment = {
        "payment_id": "pay_test_unk",
        "amount": 1000.0,
        "failure_type": FailureType.NETWORK_TIMEOUT.value,
        "channel": "MOBILE_APP"
    }

    v_res = VerificationEngine.verify(mock_exec, payment, force_status=VerificationStatus.UNKNOWN)
    assert v_res.status == VerificationStatus.UNKNOWN
    # Crucial safety rule: UNKNOWN is never treated as SUCCEEDED or FAILED

def test_attribution_natural_vs_attributed_recovery():
    diag = AIDiagnosisOutput(
        diagnosis="Timeout",
        confidence=0.85,
        candidate_actions=[CandidateActionProposal(action=ActionType.RETRY_NOW, reason="Retry")]
    )
    gov = RecoveryGovernor()

    # Case 1: Attributed recovery (not naturally recovering)
    p1 = {
        "payment_id": "pay_attr_1",
        "amount": 3000.0,
        "currency": "INR",
        "payment_method": "UPI",
        "failure_type": FailureType.NETWORK_TIMEOUT.value,
        "natural_recovery_status": None
    }
    dec1 = gov.evaluate(p1, "evt_p1", diag)
    exec1 = ExecutionResult(
        execution_id="e1", decision_id=dec1.decision_id, payment_id=p1["payment_id"],
        action=ActionType.RETRY_NOW, adapter_type="SIMULATION", status="EXECUTED",
        response_payload={}, idempotency_key="i1", timestamp="2026-09-01T12:00:00Z"
    )
    ver1 = VerificationEngine.verify(exec1, p1, force_status=VerificationStatus.SUCCEEDED)
    attr1 = RecoveryAttributionEngine.attribute(dec1, ver1, p1)

    assert attr1.category == AttributionCategory.ATTRIBUTED_RECOVERY
    assert attr1.recovered_amount == 3000.0
    # Net recovery = 3000 - 15 (intervention 5 + risk 10 + friction 0) = 2985.0
    assert attr1.net_recovered_value == 2985.0

    # Case 2: Natural recovery (payment would have self-healed in control cohort)
    p2 = dict(p1, payment_id="pay_attr_2", natural_recovery_status="NATURAL_RECOVERY_CONTROL")
    dec2 = gov.evaluate(p2, "evt_p2", diag)
    exec2 = ExecutionResult(
        execution_id="e2", decision_id=dec2.decision_id, payment_id=p2["payment_id"],
        action=ActionType.RETRY_NOW, adapter_type="SIMULATION", status="EXECUTED",
        response_payload={}, idempotency_key="i2", timestamp="2026-09-01T12:00:00Z"
    )
    ver2 = VerificationEngine.verify(exec2, p2, force_status=VerificationStatus.SUCCEEDED)
    attr2 = RecoveryAttributionEngine.attribute(dec2, ver2, p2)

    assert attr2.category == AttributionCategory.NATURAL_RECOVERY
    assert attr2.counterfactual_method == "CONTROL_COHORT_COUNTERFACTUAL_OVERLAP"
