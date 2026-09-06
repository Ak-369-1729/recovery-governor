"""
Merchant Policy Configuration Layer.

Allows merchants to customize business preferences for preventive interventions:
- Enable/disable preventive suggestions
- Friction cost thresholds
- Prohibited action lists

ARCHITECTURAL SAFETY INVARIANT:
Merchant policy preferences NEVER override global deterministic safety gates.
If a merchant attempts to bypass cooling-off rules, retry caps, or kill-switch,
the Governor strictly enforces global safety invariants.
"""

from typing import Dict, Optional, List
from app.models.enums import ActionType, PaymentMethod
from app.models.schemas import MerchantPolicyConfig

class MerchantPolicyManager:
    """In-memory and persistent store for merchant recovery/prevention policies."""

    _policies: Dict[str, MerchantPolicyConfig] = {
        "mer_default": MerchantPolicyConfig(
            merchant_id="mer_default",
            allow_prevention=True,
            max_prevention_friction=25.0,
            prohibited_preventive_actions=[],
            preferred_payment_methods=[PaymentMethod.UPI, PaymentMethod.CARD],
            max_daily_preventions=100,
            override_global_safety=False,
        ),
        "mer_demo_razorpay": MerchantPolicyConfig(
            merchant_id="mer_demo_razorpay",
            allow_prevention=True,
            max_prevention_friction=30.0,
            prohibited_preventive_actions=[],
            preferred_payment_methods=[PaymentMethod.UPI, PaymentMethod.CARD],
            max_daily_preventions=250,
            override_global_safety=False,
        ),
        "mer_conservative": MerchantPolicyConfig(
            merchant_id="mer_conservative",
            allow_prevention=True,
            max_prevention_friction=5.0,  # Zero customer friction preferred
            prohibited_preventive_actions=[ActionType.CUSTOMER_NOTIFICATION, ActionType.SEND_PAYMENT_LINK],
            preferred_payment_methods=[PaymentMethod.UPI],
            max_daily_preventions=10,
            override_global_safety=False,
        ),
        "mer_high_volume": MerchantPolicyConfig(
            merchant_id="mer_high_volume",
            allow_prevention=True,
            max_prevention_friction=40.0,
            prohibited_preventive_actions=[],
            preferred_payment_methods=[PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING],
            max_daily_preventions=1000,
            override_global_safety=False,
        ),
    }

    @classmethod
    def get_policy(cls, merchant_id: str) -> MerchantPolicyConfig:
        """Retrieves merchant policy or falls back to default."""
        return cls._policies.get(
            merchant_id,
            MerchantPolicyConfig(
                merchant_id=merchant_id,
                allow_prevention=True,
                max_prevention_friction=25.0,
                prohibited_preventive_actions=[],
                preferred_payment_methods=[PaymentMethod.UPI, PaymentMethod.CARD],
                max_daily_preventions=100,
                override_global_safety=False,
            )
        )

    @classmethod
    def update_policy(cls, config: MerchantPolicyConfig) -> MerchantPolicyConfig:
        """
        Updates merchant policy.
        Enforces that override_global_safety cannot disable safety invariants.
        """
        if config.override_global_safety:
            # Explicitly force to False or flag as ignored
            config.override_global_safety = False
        cls._policies[config.merchant_id] = config
        return config

    @classmethod
    def list_policies(cls) -> List[MerchantPolicyConfig]:
        """Returns all configured merchant policies."""
        return list(cls._policies.values())
