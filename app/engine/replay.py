import uuid
from typing import Dict, Any, Optional

from app.models.enums import AIMode
from app.models.repositories import (
    get_payment,
    get_latest_decision_for_payment,
    get_latest_execution_for_payment,
    get_latest_verification_for_payment,
    get_latest_attribution_for_payment,
    insert_decision,
    insert_audit_log,
)
from app.engine.diagnosis import AIDiagnosisEngine
from app.engine.governor import RecoveryGovernor
from app.engine.executor import RecoveryActionExecutor
from app.engine.verifier import VerificationEngine
from app.engine.attribution import RecoveryAttributionEngine

class DecisionReplayEngine:
    """
    Decision Replay Engine:
    Reconstructs the complete chronological, auditable chain of reasoning
    for any payment event. Answers: 'Why did Recovery Governor make this decision?'
    """

    @classmethod
    def get_or_create_replay(cls, payment_id: str) -> Dict[str, Any]:
        payment = get_payment(payment_id)
        if not payment:
            raise ValueError(f"Payment with ID {payment_id} not found.")

        decision_data = get_latest_decision_for_payment(payment_id)
        if decision_data:
            decision_data["decision_outcome"] = decision_data.get("decision_outcome") or decision_data.get("decision")
            decision_data["decision"] = decision_data.get("decision") or decision_data.get("decision_outcome")
        execution_data = get_latest_execution_for_payment(payment_id)
        verification_data = get_latest_verification_for_payment(payment_id)
        attribution_data = get_latest_attribution_for_payment(payment_id)

        # If this payment was not evaluated yet, run it through the live pipeline now
        if not decision_data:
            ai_diagnosis, ai_mode = AIDiagnosisEngine.diagnose(payment)
            governor = RecoveryGovernor()
            event_id = payment.get("event_id") or f"evt_{uuid.uuid4().hex[:8]}"
            
            decision = governor.evaluate(
                payment=payment,
                event_id=event_id,
                ai_diagnosis=ai_diagnosis,
                ai_mode=ai_mode
            )
            insert_decision(decision.model_dump())
            decision_data = decision.model_dump()
            decision_data["decision_outcome"] = decision_data.get("decision_outcome") or decision_data.get("decision")

            # Execute
            execution = RecoveryActionExecutor.execute(decision, payment)
            execution_data = execution.model_dump()

            # Verify
            verification = VerificationEngine.verify(execution, payment)
            verification_data = verification.model_dump()

            # Attribute
            attribution = RecoveryAttributionEngine.attribute(decision, verification, payment)
            attribution_data = attribution.model_dump()

            # Audit
            insert_audit_log(
                event_type="PAYMENT_DECISION_EVALUATED",
                payment_id=payment_id,
                trace_id=f"trc_{decision.decision_id}",
                payload={
                    "decision_id": decision.decision_id,
                    "selected_action": decision.selected_action.value,
                    "decision": decision.decision.value,
                    "verification_status": verification.status.value,
                    "attribution_category": attribution.category.value
                }
            )

        # Reconstruct step-by-step pipeline trace
        trace_steps = [
            {
                "step_number": 1,
                "stage": "PAYMENT_EVENT",
                "title": "Payment Failure Event Received",
                "timestamp": payment.get("timestamp"),
                "status": "COMPLETED",
                "summary": f"Failed {payment.get('payment_method')} payment of ₹{payment.get('amount'):,.2f} ({payment.get('failure_type')})",
                "data": {
                    "payment_id": payment["payment_id"],
                    "amount": payment["amount"],
                    "currency": payment.get("currency", "INR"),
                    "payment_method": payment["payment_method"],
                    "failure_type": payment["failure_type"],
                    "failure_code": payment["failure_code"],
                    "channel": payment.get("channel", "MOBILE_APP"),
                    "timestamp": payment["timestamp"]
                }
            },
            {
                "step_number": 2,
                "stage": "CONTEXT_ENGINE",
                "title": "Payment Context & Customer Profile Assembled",
                "timestamp": payment.get("timestamp"),
                "status": "COMPLETED",
                "summary": f"Retry attempts: {payment.get('retry_count', 0)}, Risk Tier: {payment.get('risk_tier', 'LOW')}, Contacts: {payment.get('contact_count', 0)}",
                "data": {
                    "retry_count": payment.get("retry_count", 0),
                    "last_retry_at": payment.get("last_retry_at"),
                    "contact_count": payment.get("contact_count", 0),
                    "risk_tier": payment.get("risk_tier", "LOW"),
                    "merchant_policy": payment.get("merchant_policy", {})
                }
            },
            {
                "step_number": 3,
                "stage": "AI_DIAGNOSIS",
                "title": f"AI Failure Etiology Diagnosis ({decision_data.get('ai_mode', 'FALLBACK')})",
                "timestamp": decision_data.get("timestamp"),
                "status": "COMPLETED",
                "summary": decision_data.get("ai_diagnosis"),
                "data": {
                    "diagnosis": decision_data.get("ai_diagnosis"),
                    "confidence": decision_data.get("ai_confidence"),
                    "ai_mode": decision_data.get("ai_mode"),
                    "candidate_proposals": decision_data.get("candidate_actions")
                }
            },
            {
                "step_number": 4,
                "stage": "ERV_CALCULATION",
                "title": "Expected Recovery Value (ERV) Mathematical Calculation",
                "timestamp": decision_data.get("timestamp"),
                "status": "COMPLETED",
                "summary": f"Computed Net ERV for {len(decision_data.get('erv_by_action', {}))} candidate actions factoring gateway fees, risk, and customer friction.",
                "data": decision_data.get("erv_by_action", {})
            },
            {
                "step_number": 5,
                "stage": "GOVERNOR_POLICY",
                "title": "Deterministic Safety Gate Evaluation (8 Gates)",
                "timestamp": decision_data.get("timestamp"),
                "status": "COMPLETED",
                "summary": f"Selected {decision_data.get('selected_action')} with decision {decision_data.get('decision_outcome')}. Blocked: {len(decision_data.get('blocked_actions', []))} actions.",
                "data": {
                    "policy_checks": decision_data.get("policy_checks", []),
                    "blocked_actions": decision_data.get("blocked_actions", []),
                    "selected_action": decision_data.get("selected_action"),
                    "decision_outcome": decision_data.get("decision_outcome"),
                    "governor_reason": decision_data.get("reason"),
                    "governor_version": decision_data.get("governor_version", "1.0.0")
                }
            },
            {
                "step_number": 6,
                "stage": "EXECUTION",
                "title": "Recovery Action Execution via Adapter",
                "timestamp": execution_data.get("timestamp") if execution_data else None,
                "status": "COMPLETED" if execution_data else "PENDING",
                "summary": f"Action {execution_data.get('action') if execution_data else 'None'} dispatched via {execution_data.get('adapter_type') if execution_data else 'None'}.",
                "data": execution_data or {}
            },
            {
                "step_number": 7,
                "stage": "VERIFICATION",
                "title": "Financial Settlement Verification",
                "timestamp": verification_data.get("verified_at") if verification_data else None,
                "status": "COMPLETED" if verification_data else "PENDING",
                "summary": f"Verification status: {verification_data.get('status') if verification_data else 'UNKNOWN'}.",
                "data": verification_data or {}
            },
            {
                "step_number": 8,
                "stage": "ATTRIBUTION",
                "title": "Causal Revenue Attribution & Net Impact",
                "timestamp": attribution_data.get("timestamp") if attribution_data else None,
                "status": "COMPLETED" if attribution_data else "PENDING",
                "summary": f"Classified as {attribution_data.get('category') if attribution_data else 'UNKNOWN'}. Net recovered: ₹{attribution_data.get('net_recovered_value', 0):,.2f}.",
                "data": attribution_data or {}
            }
        ]

        return {
            "payment_id": payment_id,
            "payment": payment,
            "decision": decision_data,
            "execution": execution_data,
            "verification": verification_data,
            "attribution": attribution_data,
            "trace_steps": trace_steps
        }
