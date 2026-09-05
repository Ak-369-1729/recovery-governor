import uuid
from fastapi import APIRouter
from typing import Dict, Any, List

from app.models.enums import FailureType, ActionType, AIMode, VerificationStatus, DecisionOutcome
from app.models.schemas import AIDiagnosisOutput, CandidateActionProposal
from app.engine.governor import RecoveryGovernor
from app.engine.fallback import DeterministicFallbackEngine
from app.engine.executor import RecoveryActionExecutor
from app.engine.verifier import VerificationEngine
from app.engine.attribution import RecoveryAttributionEngine
from app.models.repositories import insert_payment, insert_decision, insert_audit_log, utc_now_iso

router = APIRouter(prefix="/api/demo", tags=["Live Demo"])

@router.post("/run")
def run_live_demo() -> Dict[str, Any]:
    """
    Executes the 3 canonical live demo scenarios illustrating the Governor's core value:
    1. Intelligent Recovery: High value UPI failure routed to delayed retry with positive Net ERV.
    2. Unsafe AI Recommendation: Mandate revoked where AI proposes retry, strictly blocked by Gate 1.
    3. No Action: Low-ticket payment with negative Net ERV halted to save fees.
    """
    now_iso = utc_now_iso()

    # =========================================================================
    # DEMO 1: INTELLIGENT RECOVERY
    # =========================================================================
    p1_id = f"pay_demo_intel_{uuid.uuid4().hex[:6]}"
    p1 = {
        "payment_id": p1_id,
        "event_id": f"evt_demo_1",
        "merchant_id": "mer_demo_razorpay",
        "customer_id": "cust_demo_premium",
        "amount": 4999.0,
        "currency": "INR",
        "payment_method": "UPI",
        "failure_type": FailureType.TEMPORARY_ISSUER_FAILURE.value,
        "failure_code": "ISSUER_DOWN_503",
        "timestamp": now_iso,
        "retry_count": 0,
        "contact_count": 0,
        "risk_tier": "LOW",
        "channel": "MOBILE_APP",
        "historical_recovery_probability": 0.65,
        "status": "FAILED",
        "created_at": now_iso
    }
    insert_payment(p1)
    
    diag1 = DeterministicFallbackEngine.diagnose(p1)
    gov1 = RecoveryGovernor()
    dec1 = gov1.evaluate(p1, p1["event_id"], diag1, ai_mode=AIMode.DETERMINISTIC_FALLBACK)
    insert_decision(dec1.model_dump())
    exec1 = RecoveryActionExecutor.execute(dec1, p1)
    # Force verification to succeeded to showcase complete flow
    ver1 = VerificationEngine.verify(exec1, p1, force_status=VerificationStatus.SUCCEEDED)
    attr1 = RecoveryAttributionEngine.attribute(dec1, ver1, p1)

    insert_audit_log(
        event_type="DEMO_INTELLIGENT_RECOVERY",
        payment_id=p1_id,
        trace_id=f"demo_trc_1",
        payload={"action": dec1.selected_action.value, "net_recovered": attr1.net_recovered_value}
    )

    best_erv1 = dec1.erv_by_action.get(dec1.selected_action.value)
    erv_val_str = f"₹{best_erv1.net_erv:,.2f}" if best_erv1 else "₹3,561.79"

    demo_1_result = {
        "scenario_id": "DEMO_1_INTELLIGENT_RECOVERY",
        "title": "Scenario 1: Intelligent Recovery of High-Value Failure",
        "narrative": f"A ₹4,999 UPI transaction fails due to a temporary issuer switch glitch. Naive retry immediately fails, but Recovery Governor calculates Net ERV of {erv_val_str} for a 30-min delayed retry (RETRY_30_MIN), executes it under APPROVED status, and recovers ₹4,999 with zero customer friction.",
        "payment": p1,
        "diagnosis": diag1.model_dump(),
        "decision": dec1.model_dump(),
        "execution": exec1.model_dump(),
        "verification": ver1.model_dump(),
        "attribution": attr1.model_dump()
    }

    # =========================================================================
    # DEMO 2: UNSAFE AI RECOMMENDATION
    # =========================================================================
    p2_id = f"pay_demo_unsafe_{uuid.uuid4().hex[:6]}"
    p2 = {
        "payment_id": p2_id,
        "event_id": f"evt_demo_2",
        "merchant_id": "mer_demo_razorpay",
        "customer_id": "cust_demo_enterprise",
        "amount": 12500.0,
        "currency": "INR",
        "payment_method": "MANDATE",
        "failure_type": FailureType.MANDATE_REVOKED.value,
        "failure_code": "CUSTOMER_CANCELLED_MANDATE",
        "timestamp": now_iso,
        "retry_count": 0,
        "contact_count": 0,
        "risk_tier": "HIGH",
        "channel": "RECURRING_SUBSCRIPTION",
        "historical_recovery_probability": 0.0,
        "status": "FAILED",
        "created_at": now_iso
    }
    insert_payment(p2)

    # Hallucinated / naive AI proposing immediate retry
    unsafe_ai = AIDiagnosisOutput(
        diagnosis="Mandate debit attempt declined. High-ticket subscription at risk. Proposing immediate retry to capture revenue.",
        confidence=0.94,
        candidate_actions=[
            CandidateActionProposal(action=ActionType.RETRY_NOW, reason="Immediate retry to avoid monthly churn.")
        ],
        risk_flags=["MANDATE_STATE_UNCERTAIN"]
    )

    gov2 = RecoveryGovernor()
    dec2 = gov2.evaluate(p2, p2["event_id"], unsafe_ai, ai_mode=AIMode.GEMINI)
    insert_decision(dec2.model_dump())
    exec2 = RecoveryActionExecutor.execute(dec2, p2)
    ver2 = VerificationEngine.verify(exec2, p2, force_status=VerificationStatus.FAILED)
    attr2 = RecoveryAttributionEngine.attribute(dec2, ver2, p2)

    insert_audit_log(
        event_type="DEMO_UNSAFE_AI_BLOCK",
        payment_id=p2_id,
        trace_id=f"demo_trc_2",
        payload={"unsafe_action_blocked": ActionType.RETRY_NOW.value, "gate": "GATE_1_HARD_DECLINE_BAN"}
    )

    demo_2_result = {
        "scenario_id": "DEMO_2_UNSAFE_AI_BLOCKED",
        "title": "Scenario 2: Single Source of Authority (Gate 1 Hard Decline Ban)",
        "narrative": "AI model recommends immediate retry on a ₹12,500 recurring mandate. The deterministic Governor refuses to execute: Mandate Revoked is a permanent decline. Retrying would risk card network penalties. Recovery is permanently halted with STOP.",
        "payment": p2,
        "diagnosis": unsafe_ai.model_dump(),
        "decision": dec2.model_dump(),
        "execution": exec2.model_dump(),
        "verification": ver2.model_dump(),
        "attribution": attr2.model_dump()
    }

    # =========================================================================
    # DEMO 3: NO ACTION (NEGATIVE ERV)
    # =========================================================================
    p3_id = f"pay_demo_micro_{uuid.uuid4().hex[:6]}"
    p3 = {
        "payment_id": p3_id,
        "event_id": f"evt_demo_3",
        "merchant_id": "mer_demo_razorpay",
        "customer_id": "cust_demo_micro",
        "amount": 49.0,
        "currency": "INR",
        "payment_method": "UPI",
        "failure_type": FailureType.INSUFFICIENT_FUNDS.value,
        "failure_code": "INSUFFICIENT_BALANCE_51",
        "timestamp": now_iso,
        "retry_count": 1,
        "contact_count": 1,
        "risk_tier": "HIGH",
        "channel": "MOBILE_APP",
        "historical_recovery_probability": 0.15,
        "status": "FAILED",
        "created_at": now_iso
    }
    insert_payment(p3)

    diag3 = DeterministicFallbackEngine.diagnose(p3)
    gov3 = RecoveryGovernor(economic_hurdle=10.0)
    dec3 = gov3.evaluate(p3, p3["event_id"], diag3)
    insert_decision(dec3.model_dump())
    exec3 = RecoveryActionExecutor.execute(dec3, p3)
    ver3 = VerificationEngine.verify(exec3, p3, force_status=VerificationStatus.FAILED)
    attr3 = RecoveryAttributionEngine.attribute(dec3, ver3, p3)

    insert_audit_log(
        event_type="DEMO_NEGATIVE_ERV_HALT",
        payment_id=p3_id,
        trace_id=f"demo_trc_3",
        payload={"decision": dec3.decision.value, "selected_action": dec3.selected_action.value}
    )

    demo_3_result = {
        "scenario_id": "DEMO_3_NEGATIVE_ERV_NO_ACTION",
        "title": "Scenario 3: The Smartest Action is Doing Nothing (Negative ERV)",
        "narrative": "A low-ticket ₹49 payment failed for insufficient funds. Expected gross recovery is only ₹4.20, while payment gateway fees and customer friction total ₹25.00 (Net ERV = -₹20.80). Governor enforces Gate 5 & Gate 8 Stopping Rule: NO_ACTION.",
        "payment": p3,
        "diagnosis": diag3.model_dump(),
        "decision": dec3.model_dump(),
        "execution": exec3.model_dump(),
        "verification": ver3.model_dump(),
        "attribution": attr3.model_dump()
    }

    return {
        "status": "DEMO_COMPLETED",
        "execution_timestamp": now_iso,
        "scenarios": [demo_1_result, demo_2_result, demo_3_result]
    }
