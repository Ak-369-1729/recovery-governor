from typing import Dict, Any, Optional
from app.models.enums import ActionType, FailureType, Channel, RiskTier, ACTION_CATALOG
from app.models.schemas import ERVCalculation
from app.engine.bayesian import BayesianRecoveryModel

class ERVEngine:
    """
    Calculates the Net Expected Recovery Value (ERV) for candidate actions:
    Net ERV = P(recovery | action, context) * payment_amount - intervention_cost - risk_cost - friction_cost
    """

    @classmethod
    def calculate(
        cls,
        action: ActionType,
        payment_amount: float,
        failure_type: FailureType,
        channel: Optional[Channel] = None,
        retry_count: int = 0,
        risk_tier: RiskTier = RiskTier.LOW,
        hurdle: float = 10.0,
        custom_base_probability: Optional[float] = None
    ) -> ERVCalculation:
        # 1. Base recovery probability from Bayesian model or override
        if custom_base_probability is not None:
            base_prob = custom_base_probability
        else:
            posterior = BayesianRecoveryModel.get_posterior(
                failure_type=failure_type.value,
                action=action.value,
                channel=channel.value if channel else None
            )
            base_prob = posterior["posterior_mean"]

        # 2. Contextual Modulation
        # Retry decay: subsequent retries have diminishing returns
        # e.g., attempt 1 = 100% of base, attempt 2 = 75%, attempt 3 = 50%
        decay_factor = max(0.05, 1.0 - (0.25 * retry_count))
        
        # Risk tier adjustment
        risk_modifier = 1.0
        if risk_tier == RiskTier.MEDIUM:
            risk_modifier = 0.90
        elif risk_tier == RiskTier.HIGH:
            risk_modifier = 0.70

        # Hard declines have zero effective recovery via retry
        if FailureType.is_hard_decline(failure_type) and ActionType.is_retry(action):
            adjusted_prob = 0.0
        elif action in {ActionType.NO_ACTION, ActionType.STOP}:
            # No intervention means 0 gross incremental recovery through governor
            adjusted_prob = 0.0
        else:
            adjusted_prob = max(0.0, min(0.98, base_prob * decay_factor * risk_modifier))

        # 3. Action cost parameters from catalog
        meta = ACTION_CATALOG.get(action, {
            "intervention_cost": 0.0,
            "risk_cost": 0.0,
            "friction_cost": 0.0,
        })
        
        intervention_cost = float(meta["intervention_cost"])
        risk_cost = float(meta["risk_cost"])
        friction_cost = float(meta["friction_cost"])

        # Special risk tier penalty addition to risk cost
        if risk_tier == RiskTier.HIGH:
            risk_cost *= 2.0

        # 4. Financial Calculations
        gross_recovery = round(adjusted_prob * payment_amount, 2)
        total_cost = intervention_cost + risk_cost + friction_cost
        net_erv = round(gross_recovery - total_cost, 2)

        # 5. Economic viability hurdle
        is_viable = (net_erv > 0.0) and (net_erv >= hurdle)
        
        if action in {ActionType.NO_ACTION, ActionType.STOP}:
            formula = f"No action taken. Cost = ₹0.00, Gross = ₹0.00, Net ERV = ₹0.00"
            is_viable = True  # Always economically viable to do nothing
        else:
            formula = (
                f"Net ERV = ({adjusted_prob:.3f} × ₹{payment_amount:,.2f}) "
                f"- ₹{intervention_cost:.2f} (intervention) "
                f"- ₹{risk_cost:.2f} (risk) "
                f"- ₹{friction_cost:.2f} (friction) "
                f"= ₹{net_erv:,.2f}"
            )

        return ERVCalculation(
            action=action,
            recovery_probability=round(adjusted_prob, 4),
            payment_amount=round(payment_amount, 2),
            gross_expected_recovery=gross_recovery,
            intervention_cost=intervention_cost,
            risk_cost=risk_cost,
            friction_cost=friction_cost,
            net_erv=net_erv,
            is_economically_viable=is_viable,
            formula_breakdown=formula
        )

    @classmethod
    def evaluate_all(
        cls,
        candidate_actions: list[ActionType],
        payment_amount: float,
        failure_type: FailureType,
        channel: Optional[Channel] = None,
        retry_count: int = 0,
        risk_tier: RiskTier = RiskTier.LOW,
        hurdle: float = 10.0
    ) -> Dict[str, ERVCalculation]:
        results: Dict[str, ERVCalculation] = {}
        for action in candidate_actions:
            results[action.value] = cls.calculate(
                action=action,
                payment_amount=payment_amount,
                failure_type=failure_type,
                channel=channel,
                retry_count=retry_count,
                risk_tier=risk_tier,
                hurdle=hurdle
            )
        return results
