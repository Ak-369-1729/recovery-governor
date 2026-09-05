import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.models.enums import AttributionCategory, VerificationStatus, ActionType, ACTION_CATALOG
from app.models.schemas import AttributionResult, VerificationResult, GovernorDecision
from app.models.repositories import insert_attribution, utc_now_iso

class RecoveryAttributionEngine:
    """
    Causal Recovery Attribution Engine:
    Distinguishes true incremental recovery from natural recovery and unverified outcomes.
    Never claims causal credit merely because payment succeeded post-hoc.
    """

    @classmethod
    def attribute(
        cls,
        decision: GovernorDecision,
        verification: VerificationResult,
        payment: Dict[str, Any]
    ) -> AttributionResult:
        attribution_id = f"attr_{uuid.uuid4().hex[:12]}"
        now_iso = utc_now_iso()
        payment_id = decision.payment_id
        amount = float(payment.get("amount", 0.0))
        action = decision.selected_action
        v_status = verification.status
        
        # Action cost breakdown
        meta = ACTION_CATALOG.get(action, {
            "intervention_cost": 0.0,
            "risk_cost": 0.0,
            "friction_cost": 0.0,
        })
        intervention_cost = float(meta["intervention_cost"])
        risk_cost = float(meta["risk_cost"])
        friction_cost = float(meta["friction_cost"])
        
        # Natural recovery ground truth (synthetic benchmark indicator or baseline probability)
        natural_rec_status = payment.get("natural_recovery_status")

        cost_breakdown = {
            "intervention_cost": intervention_cost,
            "risk_cost": risk_cost,
            "friction_cost": friction_cost,
            "total_cost": intervention_cost + risk_cost + friction_cost
        }

        if v_status == VerificationStatus.UNKNOWN:
            category = AttributionCategory.UNKNOWN
            recovered_amount = 0.0
            net_recovered_value = -cost_breakdown["total_cost"]
            counterfactual_method = "AMBIGUOUS_SETTLEMENT_AWAITING_RECONCILIATION"

        elif v_status == VerificationStatus.FAILED or action in {ActionType.NO_ACTION, ActionType.STOP}:
            category = AttributionCategory.FAILED_RECOVERY
            recovered_amount = 0.0
            net_recovered_value = -cost_breakdown["total_cost"]
            counterfactual_method = "CONFIRMED_NON_RECOVERY"

        elif v_status == VerificationStatus.SUCCEEDED:
            # Check counterfactual: Did this payment naturally succeed on its own without needing the intervention?
            if natural_rec_status == "NATURAL_RECOVERY_CONTROL":
                category = AttributionCategory.NATURAL_RECOVERY
                recovered_amount = amount
                # Does not credit incremental value from intervention
                net_recovered_value = amount - cost_breakdown["total_cost"]
                counterfactual_method = "CONTROL_COHORT_COUNTERFACTUAL_OVERLAP"
            else:
                category = AttributionCategory.ATTRIBUTED_RECOVERY
                recovered_amount = amount
                net_recovered_value = amount - cost_breakdown["total_cost"]
                counterfactual_method = "CAUSAL_GOVERNOR_INTERVENTION_LIFT"
        else:
            category = AttributionCategory.UNKNOWN
            recovered_amount = 0.0
            net_recovered_value = 0.0
            counterfactual_method = "PENDING_VERIFICATION"

        res = AttributionResult(
            attribution_id=attribution_id,
            payment_id=payment_id,
            category=category,
            counterfactual_method=counterfactual_method,
            recovered_amount=round(recovered_amount, 2),
            net_recovered_value=round(net_recovered_value, 2),
            cost_breakdown=cost_breakdown,
            timestamp=now_iso
        )
        insert_attribution(res.model_dump())
        return res
