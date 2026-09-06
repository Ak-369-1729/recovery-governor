"""
Unified Payment Lifecycle Engine: Predict -> Prevent -> Recover -> Prove.

Orchestrates the complete 13-stage deterministic payment state machine:
1. INTENT_CREATED
2. PRE_FLIGHT_ANALYSIS
3. FAILURE_PREDICTED
4. PREVENTION_EVALUATION
5. PREVENTIVE_ACTION_APPROVED / REJECTED
6. PREVENTIVE_ACTION_EXECUTED
7. ATTEMPT_DISPATCHED
8. PAYMENT_SUCCEEDED / PAYMENT_FAILED
9. RECOVERY_GOVERNOR_ACTIVATED
10. RECOVERY_ACTION_EXECUTED
11. VERIFIED_AND_ATTRIBUTED
12. COMPLETED

Integrates:
- Synthetic Failure Predictor (No outcome leakage)
- Deterministic Governor (Single Financial Authority)
- Simulated Network Health
- Prediction Outcome Evaluation (Feedback loop)
- Conservative Prevention Attribution
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.models.enums import (
    LifecycleState,
    PaymentMethod,
    RiskTier,
    Channel,
    FailureType,
    ActionType,
    NetworkScenario,
    ChaosType,
    AttributionCategory,
    VerificationStatus,
    GovernorOperatingMode,
)
from app.models.schemas import (
    FailurePrediction,
    PreventiveGovernorDecision,
    GovernorDecision,
    ExecutionResult,
    VerificationResult,
    AttributionResult,
    PredictionOutcomeEvaluation,
    UnifiedLifecycleTrace,
)
from app.engine.predictor import FailurePredictor, PredictorUnavailableException
from app.engine.governor import RecoveryGovernor, EmergencyKillSwitchManager
from app.engine.network_health import SimulatedNetworkHealthEngine
from app.engine.prediction_evaluation import PredictionEvaluationEngine
from app.engine.attribution import RecoveryAttributionEngine
from app.engine.fallback import DeterministicFallbackEngine
from app.engine.executor import RecoveryActionExecutor
from app.engine.verifier import VerificationEngine
from app.models.repositories import utc_now_iso

class UnifiedLifecycleEngine:
    """
    Simulates end-to-end payment intent lifecycle across predictive and reactive recovery stages.
    """

    @classmethod
    def simulate_lifecycle(
        cls,
        payment: Dict[str, Any],
        scenario: NetworkScenario = NetworkScenario.SBI_DEGRADED,
        seed: int = 42,
        chaos_injection: Optional[ChaosType] = None,
        operating_mode: GovernorOperatingMode = GovernorOperatingMode.GOVERNED,
    ) -> UnifiedLifecycleTrace:
        start_time = time.perf_counter()
        now_iso = utc_now_iso()

        lifecycle_id = f"life_{uuid.uuid4().hex[:12]}"
        payment_id = payment.get("payment_id", f"pay_{uuid.uuid4().hex[:8]}")
        amount = float(payment.get("amount", 4999.0))
        payment_method = PaymentMethod(payment.get("payment_method", PaymentMethod.UPI))
        rail_id = payment.get("rail_id", "UPI_SBI")
        customer_success_rate = float(payment.get("customer_success_rate", 0.85))
        risk_tier = RiskTier(payment.get("risk_tier", RiskTier.LOW))
        channel = Channel(payment.get("channel", Channel.MOBILE_APP))

        history: List[Dict[str, Any]] = []

        def record_stage(state: LifecycleState, details: Dict[str, Any]) -> None:
            history.append({
                "state": state.value,
                "timestamp": utc_now_iso(),
                "details": details,
            })

        # 1. INTENT_CREATED
        record_stage(LifecycleState.INTENT_CREATED, {
            "payment_id": payment_id,
            "amount": amount,
            "currency": "INR",
            "method": payment_method.value,
            "target_rail": rail_id,
        })

        # 2. PRE_FLIGHT_ANALYSIS
        record_stage(LifecycleState.PRE_FLIGHT_ANALYSIS, {
            "action": "Querying synthetic rail telemetry and evaluating pre-flight risk factors",
            "scenario": scenario.value,
            "seed": seed,
        })

        # Call Predictor (strictly no outcome leakage)
        prediction: Optional[FailurePrediction] = None
        try:
            prediction = FailurePredictor.predict(
                payment_id=payment_id,
                amount=amount,
                payment_method=payment_method,
                rail_id=rail_id,
                customer_success_rate=customer_success_rate,
                risk_tier=risk_tier,
                channel=channel,
                network_scenario=scenario,
                network_seed=seed,
                chaos_injection=chaos_injection,
                raw_input_payload=payment,
            )
        except PredictorUnavailableException as e:
            record_stage(LifecycleState.FAILURE_PREDICTED, {
                "status": "PREDICTOR_UNAVAILABLE",
                "fallback": "Predictor service failed under chaos; defaulting safely to reactive governor.",
                "error": str(e),
            })

        governor = RecoveryGovernor()
        prevention_decision: Optional[PreventiveGovernorDecision] = None
        preventive_executed = False
        preventive_execution_details: Optional[Dict[str, Any]] = None

        activated_kill_for_chaos = False
        if chaos_injection in (ChaosType.KILL_SWITCH_PREVENTIVE, "KILL_SWITCH_PREVENTIVE"):
            EmergencyKillSwitchManager.activate(audit_id=f"chaos_{payment_id}")
            activated_kill_for_chaos = True

        if prediction:
            # 3. FAILURE_PREDICTED
            record_stage(LifecycleState.FAILURE_PREDICTED, {
                "simulated_failure_probability": prediction.simulated_failure_probability,
                "confidence": prediction.confidence.value,
                "confidence_score": prediction.confidence_score,
                "predicted_failure_type": prediction.predicted_failure_type.value if prediction.predicted_failure_type else None,
                "contributing_factors": prediction.contributing_factors,
                "candidate_actions": [a.value for a in prediction.candidate_preventive_actions],
            })

            # 4. PREVENTION_EVALUATION
            record_stage(LifecycleState.PREVENTION_EVALUATION, {
                "action": "Governor evaluating candidate preventive actions against safety gates & ERV hurdle",
                "candidates_count": len(prediction.candidate_preventive_actions),
            })
            prevention_decision = governor.evaluate_prevention(payment=payment, prediction=prediction)
            
            # 5. PREVENTIVE_ACTION_APPROVED / REJECTED
            is_approved = (prevention_decision.decision_outcome == "APPROVED")
            approval_state = LifecycleState.PREVENTIVE_ACTION_APPROVED if is_approved else LifecycleState.PREVENTIVE_ACTION_REJECTED
            record_stage(approval_state, {
                "decision": prevention_decision.decision_outcome,
                "selected_action": prevention_decision.selected_action.value,
                "net_preventive_erv": prevention_decision.net_preventive_erv,
                "why_this_action": prevention_decision.explainability.get("why_this_action"),
            })

            # 6. PREVENTIVE_ACTION_EXECUTED
            if is_approved and prevention_decision.selected_action != ActionType.NO_ACTION:
                preventive_executed = True
                preventive_execution_details = {
                    "action": prevention_decision.selected_action.value,
                    "target_substitute": "UPI_HDFC" if rail_id == "UPI_SBI" else "CARD_VISA",
                    "intervention_cost": 2.0,
                    "status": "EXECUTED",
                }
                record_stage(LifecycleState.PREVENTIVE_ACTION_EXECUTED, preventive_execution_details)

        # 7. ATTEMPT_DISPATCHED
        record_stage(LifecycleState.ATTEMPT_DISPATCHED, {
            "dispatch_rail": preventive_execution_details.get("target_substitute", rail_id) if preventive_executed else rail_id,
            "is_preventive_routed": preventive_executed,
        })

        # 8. PAYMENT REALIZATION (Ground-truth simulation)
        # Determine actual ground-truth outcome based on rail health and intervention
        effective_rail = preventive_execution_details.get("target_substitute", rail_id) if preventive_executed else rail_id
        telemetry = SimulatedNetworkHealthEngine.get_rail_health(effective_rail, scenario=scenario, seed=seed)
        counterfactual_telemetry = SimulatedNetworkHealthEngine.get_rail_health(rail_id, scenario=scenario, seed=seed)

        # Payment succeeds if effective rail health is adequate (>= 50) and customer does not bounce
        payment_succeeded = (telemetry.health_score >= 50.0 and customer_success_rate >= 0.50)
        # Counterfactual: without preventive intervention on original rail
        counterfactual_failed = (counterfactual_telemetry.health_score < 50.0 or customer_success_rate < 0.50)

        payment_outcome_str = "SUCCESS" if payment_succeeded else "FAILED"
        actual_failure_type = FailureType.NETWORK_TIMEOUT if not payment_succeeded else None

        # Record prediction outcome evaluation for feedback loop
        eval_outcome: Optional[PredictionOutcomeEvaluation] = None
        if prediction:
            eval_outcome = PredictionEvaluationEngine.record_outcome(
                prediction=prediction,
                actual_status=payment_outcome_str,
                actual_failure_type=actual_failure_type,
            )

        recovery_decision: Optional[GovernorDecision] = None
        recovery_execution: Optional[ExecutionResult] = None
        verification: Optional[VerificationResult] = None
        attribution: Optional[AttributionResult] = None

        if payment_succeeded:
            # 8a. PAYMENT_SUCCEEDED
            record_stage(LifecycleState.PAYMENT_SUCCEEDED, {
                "outcome": "SUCCESS",
                "rail": effective_rail,
                "rail_health": telemetry.health_score,
            })

            # Attribution for prevention
            if prevention_decision:
                attribution = RecoveryAttributionEngine.attribute_prevention(
                    prevention_decision=prevention_decision,
                    payment=payment,
                    final_outcome="SUCCESS",
                    counterfactual_outcome="FAILED" if counterfactual_failed else "SUCCESS",
                )
                record_stage(LifecycleState.VERIFIED_AND_ATTRIBUTED, {
                    "attribution_category": attribution.category.value,
                    "net_prevented_value": attribution.net_recovered_value,
                    "method": attribution.counterfactual_method,
                })

                # Record prevention economics event
                PredictionEvaluationEngine.record_prevention_event(
                    payment_id=payment_id,
                    amount=amount,
                    is_high_risk=prediction.simulated_failure_probability >= 0.50,
                    preventive_action_proposed=True,
                    governor_approved=preventive_executed,
                    governor_action=prevention_decision.selected_action.value,
                    intervention_cost=2.0 if preventive_executed else 0.0,
                    final_outcome="SUCCESS",
                    prevented_failure=(attribution.category == AttributionCategory.PREVENTED_FAILURE),
                    attribution_category=attribution.category.value,
                )

        else:
            # 8b. PAYMENT_FAILED
            record_stage(LifecycleState.PAYMENT_FAILED, {
                "outcome": "FAILED",
                "failure_type": FailureType.NETWORK_TIMEOUT.value,
                "failure_code": "SIMULATED_ISSUER_504_TIMEOUT",
                "rail": effective_rail,
                "rail_health": telemetry.health_score,
            })

            # 9. RECOVERY_GOVERNOR_ACTIVATED
            record_stage(LifecycleState.RECOVERY_GOVERNOR_ACTIVATED, {
                "trigger": "Payment failed; triggering deterministic reactive recovery gates.",
            })

            # Diagnose via deterministic fallback or Gemini
            diag_output = DeterministicFallbackEngine.diagnose(
                payment={
                    "payment_id": payment_id,
                    "amount": amount,
                    "payment_method": payment_method.value,
                    "failure_type": FailureType.NETWORK_TIMEOUT.value,
                    "retry_count": 0,
                    "risk_tier": risk_tier.value,
                    "channel": channel.value,
                }
            )

            recovery_decision = governor.evaluate(
                payment={
                    "payment_id": payment_id,
                    "amount": amount,
                    "failure_type": FailureType.NETWORK_TIMEOUT,
                    "retry_count": 0,
                    "contact_count": 0,
                    "risk_tier": risk_tier,
                    "channel": channel,
                },
                event_id=f"evt_{payment_id}",
                ai_diagnosis=diag_output,
                operating_mode=operating_mode,
            )

            # 10. RECOVERY_ACTION_EXECUTED
            recovery_execution = RecoveryActionExecutor.execute(
                decision=recovery_decision,
                payment={
                    "payment_id": payment_id,
                    "amount": amount,
                    "failure_type": FailureType.NETWORK_TIMEOUT,
                },
            )
            record_stage(LifecycleState.RECOVERY_ACTION_EXECUTED, {
                "action": recovery_decision.selected_action.value,
                "decision": recovery_decision.decision_outcome,
                "execution_status": recovery_execution.status.value,
            })

            # 11. VERIFIED_AND_ATTRIBUTED
            verification = VerificationEngine.verify(
                execution=recovery_execution,
                payment={
                    "payment_id": payment_id,
                    "amount": amount,
                    "failure_type": FailureType.NETWORK_TIMEOUT,
                },
            )
            attribution = RecoveryAttributionEngine.attribute(
                decision=recovery_decision,
                verification=verification,
                payment={
                    "payment_id": payment_id,
                    "amount": amount,
                    "failure_type": FailureType.NETWORK_TIMEOUT,
                },
            )
            record_stage(LifecycleState.VERIFIED_AND_ATTRIBUTED, {
                "verification_status": verification.status.value,
                "attribution_category": attribution.category.value,
                "net_recovered_value": attribution.net_recovered_value,
            })

            # Record prevention economics failure event
            if prediction:
                PredictionEvaluationEngine.record_prevention_event(
                    payment_id=payment_id,
                    amount=amount,
                    is_high_risk=prediction.simulated_failure_probability >= 0.50,
                    preventive_action_proposed=(prevention_decision is not None),
                    governor_approved=preventive_executed,
                    governor_action=prevention_decision.selected_action.value if prevention_decision else "NO_ACTION",
                    intervention_cost=2.0 if preventive_executed else 0.0,
                    final_outcome="FAILED",
                    prevented_failure=False,
                    attribution_category=attribution.category.value,
                )

        # 12. COMPLETED
        record_stage(LifecycleState.COMPLETED, {
            "status": "LIFECYCLE_RUN_COMPLETED",
            "final_outcome": payment_outcome_str,
            "total_steps": len(history),
        })

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        if activated_kill_for_chaos:
            EmergencyKillSwitchManager.reset()

        return UnifiedLifecycleTrace(
            lifecycle_id=lifecycle_id,
            payment_id=payment_id,
            current_state=LifecycleState.COMPLETED,
            history=history,
            prediction=prediction,
            prevention_decision=prevention_decision,
            preventive_execution=preventive_execution_details,
            payment_outcome=payment_outcome_str,
            recovery_decision=recovery_decision,
            recovery_execution=recovery_execution,
            verification=verification,
            attribution=attribution,
            prediction_evaluation=eval_outcome,
            total_duration_ms=elapsed_ms,
        )
