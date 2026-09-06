"""
API Routes for Pre-Flight Prediction, Evaluation, Reliability, and Prevention Economics.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.enums import PaymentMethod, RiskTier, Channel, NetworkScenario, ChaosType, FailureType
from app.models.schemas import (
    FailurePrediction,
    PreventiveGovernorDecision,
    PredictionReliabilityMetrics,
    PreventionEconomicsMetrics,
    PredictionOutcomeEvaluation,
)
from app.engine.predictor import FailurePredictor, PredictorUnavailableException
from app.engine.governor import RecoveryGovernor
from app.engine.prediction_evaluation import PredictionEvaluationEngine
from app.engine.merchant_policy import MerchantPolicyManager

router = APIRouter(prefix="/api", tags=["Prediction & Prevention"])

class PredictRequest(BaseModel):
    payment_id: Optional[str] = None
    amount: float = 4999.0
    payment_method: PaymentMethod = PaymentMethod.UPI
    rail_id: Optional[str] = "UPI_SBI"
    customer_success_rate: float = 0.85
    risk_tier: RiskTier = RiskTier.LOW
    channel: Channel = Channel.MOBILE_APP
    network_scenario: NetworkScenario = NetworkScenario.SBI_DEGRADED
    network_seed: int = 42
    chaos_injection: Optional[ChaosType] = None

class PreventionEvaluateRequest(BaseModel):
    payment: Dict[str, Any]
    prediction: FailurePrediction
    merchant_id: Optional[str] = "mer_default"

class OutcomeFeedbackRequest(BaseModel):
    prediction: FailurePrediction
    actual_status: str  # "SUCCESS" or "FAILED"
    actual_failure_type: Optional[FailureType] = None

@router.post("/prediction/predict", response_model=FailurePrediction)
def predict_failure(req: PredictRequest):
    """Generates synthetic pre-flight failure risk prediction without outcome leakage."""
    try:
        pid = req.payment_id or f"pay_pred_{int(req.amount)}"
        return FailurePredictor.predict(
            payment_id=pid,
            amount=req.amount,
            payment_method=req.payment_method,
            rail_id=req.rail_id,
            customer_success_rate=req.customer_success_rate,
            risk_tier=req.risk_tier,
            channel=req.channel,
            network_scenario=req.network_scenario,
            network_seed=req.network_seed,
            chaos_injection=req.chaos_injection,
        )
    except PredictorUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/prediction/evaluate", response_model=PreventiveGovernorDecision)
def evaluate_prevention(req: PreventionEvaluateRequest):
    """Evaluates preventive candidate actions through Deterministic Governor gates."""
    governor = RecoveryGovernor()
    policy = MerchantPolicyManager.get_policy(req.merchant_id or "mer_default")
    return governor.evaluate_prevention(
        payment=req.payment,
        prediction=req.prediction,
        merchant_policy=policy,
    )

@router.get("/prediction/reliability", response_model=PredictionReliabilityMetrics)
@router.get("/prediction/metrics", response_model=PredictionReliabilityMetrics)
def get_prediction_reliability():
    """Returns empirical prediction reliability metrics (Precision, Recall, F1, Brier score, 5-bin curve)."""
    return PredictionEvaluationEngine.calculate_reliability_metrics()

@router.post("/prediction/outcome", response_model=PredictionOutcomeEvaluation)
def record_outcome_feedback(req: OutcomeFeedbackRequest):
    """Feeds realized payment outcome back into prediction evaluation loop."""
    return PredictionEvaluationEngine.record_outcome(
        prediction=req.prediction,
        actual_status=req.actual_status,
        actual_failure_type=req.actual_failure_type,
    )

@router.get("/prediction/history")
def get_prediction_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns recent prediction vs outcome evaluation pairs."""
    return PredictionEvaluationEngine.get_history(limit=limit)

@router.get("/prevention/economics", response_model=PreventionEconomicsMetrics)
def get_prevention_economics():
    """Returns comprehensive economics metrics for predictive prevention system."""
    return PredictionEvaluationEngine.calculate_prevention_economics()
