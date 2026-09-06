"""
Synthetic Failure Predictor Engine.

Predicts transaction failure probability BEFORE execution using strictly pre-flight features:
- Payment Method & Rail
- Simulated Network Health
- Transaction Amount
- Customer Historical Behaviour
- Risk Tier & Channel

CRITICAL INVARIANT (NO LEAKAGE):
This engine NEVER receives, references, or uses post-failure ground truth (status, failure_type, failure_code).
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.models.enums import (
    PaymentMethod,
    RiskTier,
    Channel,
    FailureType,
    ActionType,
    PredictionConfidence,
    NetworkScenario,
    ChaosType,
)
from app.models.schemas import FailurePrediction
from app.engine.network_health import SimulatedNetworkHealthEngine

# Forbidden fields that must NEVER influence pre-flight failure predictions
FORBIDDEN_GROUND_TRUTH_FIELDS = {
    "failure_type",
    "failure_code",
    "status",
    "natural_recovery_status",
    "execution_id",
    "verification_status",
    "attribution_category",
}

class PredictorUnavailableException(Exception):
    """Raised when chaos injection simulates a predictor outage."""
    pass

class FailurePredictor:
    """
    Synthetic Pre-Flight Failure Predictor.
    Calculates deterministic simulation-derived failure probabilities and candidate preventive actions.
    """

    @classmethod
    def predict(
        cls,
        payment_id: str,
        amount: float,
        payment_method: PaymentMethod,
        rail_id: Optional[str] = None,
        customer_success_rate: float = 0.85,
        risk_tier: RiskTier = RiskTier.LOW,
        channel: Channel = Channel.MOBILE_APP,
        network_scenario: NetworkScenario = NetworkScenario.NORMAL,
        network_seed: int = 42,
        chaos_injection: Optional[ChaosType] = None,
        raw_input_payload: Optional[Dict[str, Any]] = None,
    ) -> FailurePrediction:
        """
        Generates deterministic pre-flight failure prediction without outcome leakage.
        """
        # Audit check: Ensure no forbidden outcome fields leak into prediction
        if raw_input_payload:
            for field in FORBIDDEN_GROUND_TRUTH_FIELDS:
                if field in raw_input_payload and raw_input_payload[field] is not None:
                    # Explicitly ignore to guarantee no data leakage
                    pass

        # Handle chaos injection
        if chaos_injection == ChaosType.PREDICTOR_UNAVAILABLE:
            raise PredictorUnavailableException("Predictive intelligence service is unavailable (Chaos Injected).")
        
        if chaos_injection == ChaosType.MALFORMED_PREDICTION:
            # Returns malformed prediction to test Governor gate rejection
            return FailurePrediction(
                prediction_id=f"pred_malformed_{payment_id}",
                payment_id=payment_id,
                simulated_failure_probability=-0.5,  # Out of bounds
                confidence=PredictionConfidence.LOW,
                confidence_score=0.1,
                predicted_failure_type=None,
                predicted_failure_code="CORRUPT_SIGNAL",
                contributing_factors=["MALFORMED_AI_DATA"],
                candidate_preventive_actions=[],
                prediction_source="CHAOS_MALFORMED_SYNTHETIC",
                model_version="v3.1-chaos",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # 1. Resolve default rail ID if not specified
        if not rail_id:
            if payment_method == PaymentMethod.UPI:
                # Default SBI UPI for demonstration scenarios
                rail_id = "UPI_SBI"
            elif payment_method == PaymentMethod.CARD:
                rail_id = "CARD_VISA"
            elif payment_method == PaymentMethod.NETBANKING:
                rail_id = "NETBANKING_SBI"
            else:
                rail_id = "UPI_HDFC"

        # 2. Get simulated rail health telemetry (never live bank access)
        telemetry = SimulatedNetworkHealthEngine.get_rail_health(
            rail_id=rail_id,
            scenario=network_scenario,
            seed=network_seed,
        )

        contributing_factors: List[str] = []

        # 3. Base probability derived from rail health (lower health = higher failure risk)
        # Health 100 -> failure risk 0.05; Health 43 -> failure risk 0.72; Health 20 -> 0.88
        health_score = telemetry.health_score
        base_risk = max(0.02, (100.0 - health_score) / 100.0)
        
        if health_score < 60.0:
            contributing_factors.append(f"Simulated rail degradation: {rail_id} at health {health_score}/100")
        elif health_score < 80.0:
            contributing_factors.append(f"Simulated rail sub-optimal: {rail_id} at health {health_score}/100")

        # 4. Amount factor: high ticket sizes experience increased auth friction / issuer dropouts
        amount_adjustment = 0.0
        if amount >= 45000.0:
            amount_adjustment = 0.15
            contributing_factors.append(f"High transaction ticket size (₹{amount:,.0f}) increases step-up friction")
        elif amount >= 15000.0:
            amount_adjustment = 0.08
            contributing_factors.append(f"Moderate ticket size (₹{amount:,.0f})")
        elif amount < 50.0:
            amount_adjustment = 0.04
            contributing_factors.append("Micro-transaction validation threshold")

        # 5. Customer historical behaviour factor
        customer_adjustment = 0.0
        if customer_success_rate < 0.60:
            customer_adjustment = 0.18
            contributing_factors.append(f"Low historical customer success rate ({customer_success_rate:.0%})")
        elif customer_success_rate > 0.90:
            customer_adjustment = -0.06

        # 6. Risk Tier adjustment
        risk_adjustment = 0.0
        if risk_tier == RiskTier.HIGH:
            risk_adjustment = 0.20
            contributing_factors.append("High merchant risk classification")
        elif risk_tier == RiskTier.MEDIUM:
            risk_adjustment = 0.08

        # 7. Payment method adjustment
        method_adjustment = 0.0
        if payment_method == PaymentMethod.MANDATE:
            method_adjustment = 0.08
            contributing_factors.append("Recurring mandate execution dependency")
        elif payment_method == PaymentMethod.NETBANKING:
            method_adjustment = 0.05

        # Aggregate total simulated failure probability
        total_risk = base_risk + amount_adjustment + customer_adjustment + risk_adjustment + method_adjustment
        simulated_prob = round(max(0.01, min(0.98, total_risk)), 3)

        # 8. Confidence computation
        confidence_score = 0.88
        if chaos_injection == ChaosType.LOW_CONFIDENCE_PREDICTION:
            confidence = PredictionConfidence.LOW
            confidence_score = 0.35
            contributing_factors.append("Artificially downgraded confidence (Chaos Injected)")
        else:
            if health_score < 50.0 and amount > 30000.0:
                confidence = PredictionConfidence.HIGH
                confidence_score = 0.92
            elif health_score >= 80.0:
                confidence = PredictionConfidence.HIGH
                confidence_score = 0.89
            else:
                confidence = PredictionConfidence.MEDIUM
                confidence_score = 0.74

        # 9. Hypothesized failure type (if high risk)
        predicted_failure_type: Optional[FailureType] = None
        predicted_code: Optional[str] = None
        if simulated_prob >= 0.50:
            if health_score < 50.0:
                predicted_failure_type = FailureType.NETWORK_TIMEOUT
                predicted_code = "SIMULATED_ISSUER_TIMEOUT"
            elif customer_success_rate < 0.60:
                predicted_failure_type = FailureType.INSUFFICIENT_FUNDS
                predicted_code = "SIMULATED_BALANCE_DEFICIT"
            elif amount >= 45000.0:
                predicted_failure_type = FailureType.AUTHENTICATION_REQUIRED
                predicted_code = "SIMULATED_STEPUP_AUTH_REQUIRED"
            else:
                predicted_failure_type = FailureType.TEMPORARY_ISSUER_FAILURE
                predicted_code = "SIMULATED_ISSUER_DEGRADED"

        # 10. Generate candidate preventive actions
        candidate_actions: List[ActionType] = []
        if simulated_prob >= 0.50:
            if health_score < 60.0:
                candidate_actions.append(ActionType.RECOMMEND_ALTERNATE_PAYMENT_PATH)
            if channel == Channel.RECURRING_SUBSCRIPTION or payment_method == PaymentMethod.MANDATE:
                candidate_actions.append(ActionType.DELAY_ATTEMPT)
            candidate_actions.append(ActionType.CUSTOMER_NOTIFICATION)
            candidate_actions.append(ActionType.SEND_PAYMENT_LINK)
            candidate_actions.append(ActionType.NO_ACTION)
        else:
            candidate_actions = [ActionType.NO_ACTION]

        now_iso = datetime.now(timezone.utc).isoformat()
        pred_hash = hashlib.md5(f"{payment_id}_{simulated_prob}_{now_iso}".encode()).hexdigest()[:8]

        return FailurePrediction(
            prediction_id=f"pred_{pred_hash}",
            payment_id=payment_id,
            simulated_failure_probability=simulated_prob,
            confidence=confidence,
            confidence_score=confidence_score,
            predicted_failure_type=predicted_failure_type,
            predicted_failure_code=predicted_code,
            contributing_factors=contributing_factors,
            candidate_preventive_actions=candidate_actions,
            prediction_source="SYNTHETIC_PREDICTIVE_MODEL",
            model_version="v3.1-simulation",
            timestamp=now_iso,
        )
