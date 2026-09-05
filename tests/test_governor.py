import pytest
from app.models.enums import FailureType, ActionType, GateStatus, DecisionOutcome, AIMode
from app.models.schemas import AIDiagnosisOutput, CandidateActionProposal
from app.engine.governor import RecoveryGovernor

@pytest.fixture
def base_payment():
    return {
        "payment_id": "pay_test_001",
        "amount": 2500.0,
        "currency": "INR",
        "payment_method": "UPI",
        "failure_type": FailureType.TEMPORARY_ISSUER_FAILURE.value,
        "failure_code": "ISSUER_DOWN_503",
        "retry_count": 0,
        "contact_count": 0,
        "risk_tier": "LOW",
        "channel": "MOBILE_APP",
        "historical_recovery_probability": 0.60
    }

@pytest.fixture
def mock_diagnosis():
    return AIDiagnosisOutput(
        diagnosis="Temporary issuer switch outage.",
        confidence=0.85,
        candidate_actions=[
            CandidateActionProposal(action=ActionType.RETRY_30_MIN, reason="Issuer recovery window"),
            CandidateActionProposal(action=ActionType.RETRY_NOW, reason="Immediate try"),
            CandidateActionProposal(action=ActionType.SEND_PAYMENT_LINK, reason="Alternative channel")
        ],
        risk_flags=[]
    )

def test_gate_1_hard_decline_ban_blocks_retries(base_payment):
    # Test all 4 hard declines
    hard_declines = [
        FailureType.CARD_LOST_STOLEN,
        FailureType.MANDATE_REVOKED,
        FailureType.ACCOUNT_CLOSED,
        FailureType.PERMANENT_DECLINE
    ]
    governor = RecoveryGovernor()

    for hd in hard_declines:
        payment = dict(base_payment)
        payment["failure_type"] = hd.value
        
        # AI recklessly recommends retry
        ai_output = AIDiagnosisOutput(
            diagnosis="Hard decline present.",
            confidence=0.90,
            candidate_actions=[
                CandidateActionProposal(action=ActionType.RETRY_NOW, reason="Reckless retry")
            ]
        )
        decision = governor.evaluate(payment, "evt_test_hd", ai_output)
        
        assert ActionType.RETRY_NOW.value in decision.blocked_actions
        assert decision.decision == DecisionOutcome.STOP
        # Gate 1 check should be blocked
        g1 = next(g for g in decision.policy_checks if g.gate_name == "GATE_1_HARD_DECLINE_BAN")
        assert g1.status == GateStatus.BLOCKED

def test_gate_2_retry_cap(base_payment, mock_diagnosis):
    payment = dict(base_payment)
    payment["retry_count"] = 3  # Cap is 3
    
    governor = RecoveryGovernor(max_retries=3)
    decision = governor.evaluate(payment, "evt_test_cap", mock_diagnosis)
    
    assert ActionType.RETRY_30_MIN.value in decision.blocked_actions
    assert ActionType.RETRY_NOW.value in decision.blocked_actions
    g2 = next(g for g in decision.policy_checks if g.gate_name == "GATE_2_RETRY_CAP")
    assert g2.status == GateStatus.BLOCKED

def test_gate_3_cooldown(base_payment, mock_diagnosis):
    from datetime import datetime, timezone, timedelta
    payment = dict(base_payment)
    # Retried 2 minutes ago (cooldown is 15 minutes)
    payment["last_retry_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    payment["retry_count"] = 1

    governor = RecoveryGovernor(cooldown_minutes=15)
    decision = governor.evaluate(payment, "evt_test_cd", mock_diagnosis)

    assert ActionType.RETRY_NOW.value in decision.blocked_actions
    g3 = next(g for g in decision.policy_checks if g.gate_name == "GATE_3_COOLDOWN")
    assert g3.status == GateStatus.BLOCKED

def test_gate_4_customer_contact_cap(base_payment):
    payment = dict(base_payment)
    payment["contact_count"] = 2  # Cap is 2

    ai_output = AIDiagnosisOutput(
        diagnosis="Auth required",
        confidence=0.88,
        candidate_actions=[
            CandidateActionProposal(action=ActionType.SEND_PAYMENT_LINK, reason="Contact customer"),
            CandidateActionProposal(action=ActionType.SEND_REMINDER, reason="Remind customer")
        ]
    )

    governor = RecoveryGovernor(customer_contact_cap=2)
    decision = governor.evaluate(payment, "evt_test_contact", ai_output)

    assert ActionType.SEND_PAYMENT_LINK.value in decision.blocked_actions
    assert ActionType.SEND_REMINDER.value in decision.blocked_actions
    g4 = next(g for g in decision.policy_checks if g.gate_name == "GATE_4_CUSTOMER_CONTACT_CAP")
    assert g4.status == GateStatus.BLOCKED

def test_gate_5_economic_hurdle_and_stopping_rule(base_payment):
    payment = dict(base_payment)
    payment["amount"] = 30.0  # Very small payment
    payment["failure_type"] = FailureType.INSUFFICIENT_FUNDS.value

    ai_output = AIDiagnosisOutput(
        diagnosis="Insufficient funds",
        confidence=0.85,
        candidate_actions=[
            CandidateActionProposal(action=ActionType.SEND_PAYMENT_LINK, reason="Link")
        ]
    )

    governor = RecoveryGovernor(economic_hurdle=10.0)
    decision = governor.evaluate(payment, "evt_test_hurdle", ai_output)

    # Intervention fee ₹3 + friction ₹25 = ₹28 cost on ₹30 payment. Net ERV < 10 hurdle.
    assert decision.decision == DecisionOutcome.NO_ACTION
    assert decision.selected_action == ActionType.NO_ACTION

def test_gate_7_confidence_threshold_escalation(base_payment):
    payment = dict(base_payment)
    payment["amount"] = 5000.0  # High value

    # AI is very uncertain
    ai_output = AIDiagnosisOutput(
        diagnosis="Ambiguous error",
        confidence=0.30,  # Below threshold 0.50
        candidate_actions=[
            CandidateActionProposal(action=ActionType.RETRY_NOW, reason="Try blindly")
        ]
    )

    governor = RecoveryGovernor(confidence_threshold=0.50)
    decision = governor.evaluate(payment, "evt_test_conf", ai_output)

    assert decision.decision == DecisionOutcome.HUMAN_ESCALATION
    assert decision.selected_action == ActionType.HUMAN_ESCALATION
    g7 = next(g for g in decision.policy_checks if g.gate_name == "GATE_7_CONFIDENCE_THRESHOLD")
    assert g7.status == GateStatus.BLOCKED
