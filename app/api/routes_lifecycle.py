"""
API Routes for Unified Payment Lifecycle Orchestration (Predict -> Prevent -> Recover -> Prove).
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.models.enums import PaymentMethod, RiskTier, Channel, NetworkScenario, ChaosType, GovernorOperatingMode
from app.models.schemas import UnifiedLifecycleTrace
from app.engine.lifecycle import UnifiedLifecycleEngine

router = APIRouter(prefix="/api/lifecycle", tags=["Payment Lifecycle"])

class LifecycleSimulateRequest(BaseModel):
    payment_id: Optional[str] = None
    amount: float = 49999.0
    payment_method: PaymentMethod = PaymentMethod.UPI
    rail_id: Optional[str] = "UPI_SBI"
    customer_success_rate: float = 0.85
    risk_tier: RiskTier = RiskTier.LOW
    channel: Channel = Channel.MOBILE_APP
    network_scenario: NetworkScenario = NetworkScenario.SBI_DEGRADED
    network_seed: int = 42
    chaos_injection: Optional[ChaosType] = None
    operating_mode: GovernorOperatingMode = GovernorOperatingMode.GOVERNED

@router.post("/simulate", response_model=UnifiedLifecycleTrace)
def simulate_payment_lifecycle(req: LifecycleSimulateRequest):
    """
    Executes full 13-stage deterministic payment lifecycle:
    Pre-flight Prediction -> Preventive Evaluation -> Dispatched Attempt -> Realization -> Reactive Recovery -> Verification & Attribution.
    """
    pid = req.payment_id or f"pay_life_{int(req.amount)}"
    payment = {
        "payment_id": pid,
        "amount": req.amount,
        "payment_method": req.payment_method.value,
        "rail_id": req.rail_id,
        "customer_success_rate": req.customer_success_rate,
        "risk_tier": req.risk_tier.value,
        "channel": req.channel.value,
    }
    return UnifiedLifecycleEngine.simulate_lifecycle(
        payment=payment,
        scenario=req.network_scenario,
        seed=req.network_seed,
        chaos_injection=req.chaos_injection,
        operating_mode=req.operating_mode,
    )
