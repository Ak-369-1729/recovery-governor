import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from app.models.enums import FailureType, PaymentMethod, Channel, RiskTier
from app.models.repositories import insert_payments_batch, count_payments

SYNTHETIC_DATASET_SIZE = 5000
RANDOM_SEED = 42

FAILURE_CODES: Dict[FailureType, List[str]] = {
    FailureType.TEMPORARY_ISSUER_FAILURE: ["ISSUER_DOWN_503", "SWITCH_TIMEOUT_91", "NPCI_UP_DEGRADED"],
    FailureType.NETWORK_TIMEOUT: ["GATEWAY_SOCKET_TIMEOUT", "TCP_CONN_RESET", "HTTP_504_TIMEOUT"],
    FailureType.BANK_SERVER_UNAVAILABLE: ["BANK_HOST_UNREACHABLE", "CORE_BANKING_MAINTENANCE", "CBS_DOWN"],
    FailureType.INSUFFICIENT_FUNDS: ["INSUFFICIENT_BALANCE_51", "LIMIT_EXCEEDED", "LOW_WALLET_BALANCE"],
    FailureType.CARD_EXPIRED: ["CARD_EXPIRED_54", "INVALID_EXPIRY_DATE"],
    FailureType.CARD_LOST_STOLEN: ["CARD_STOLEN_43", "CARD_LOST_41", "HOTLISTED_CARD"],
    FailureType.MANDATE_REVOKED: ["CUSTOMER_CANCELLED_MANDATE", "AUTO_DEBIT_REVOKED"],
    FailureType.ACCOUNT_CLOSED: ["ACCOUNT_DORMANT_CLOSED", "BENEFICIARY_CLOSED"],
    FailureType.PERMANENT_DECLINE: ["SUSPECTED_FRAUD_59", "DO_NOT_HONOR_05", "RESTRICTED_CARD"],
    FailureType.AUTHENTICATION_REQUIRED: ["OTP_TIMEOUT_3DS", "CHALLENGE_ABANDONED", "BIOMETRIC_FAIL"],
    FailureType.UNKNOWN_FAILURE: ["UNKNOWN_GATEWAY_ERROR", "UNSPECIFIED_FAILURE_96"]
}

def generate_synthetic_payments(count: int = SYNTHETIC_DATASET_SIZE, seed: int = RANDOM_SEED) -> List[Dict[str, Any]]:
    """
    Generates reproducible synthetic failed-payment events.
    Label: Synthetic evaluation data — no real customer or payment data.
    """
    rng = random.Random(seed)
    payments: List[Dict[str, Any]] = []
    
    # Failure taxonomy probability weights (realistic enterprise fintech traffic)
    failure_weights = [
        (FailureType.TEMPORARY_ISSUER_FAILURE, 0.25),
        (FailureType.NETWORK_TIMEOUT, 0.20),
        (FailureType.INSUFFICIENT_FUNDS, 0.20),
        (FailureType.BANK_SERVER_UNAVAILABLE, 0.10),
        (FailureType.AUTHENTICATION_REQUIRED, 0.08),
        (FailureType.CARD_EXPIRED, 0.06),
        (FailureType.CARD_LOST_STOLEN, 0.03),
        (FailureType.MANDATE_REVOKED, 0.03),
        (FailureType.ACCOUNT_CLOSED, 0.02),
        (FailureType.PERMANENT_DECLINE, 0.01),
        (FailureType.UNKNOWN_FAILURE, 0.02),
    ]
    failure_choices, failure_probs = zip(*failure_weights)

    methods = [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.MANDATE]
    method_probs = [0.55, 0.25, 0.12, 0.08]

    channels = [Channel.MOBILE_APP, Channel.WEB_CHECKOUT, Channel.RECURRING_SUBSCRIPTION]
    channel_probs = [0.65, 0.25, 0.10]

    risk_tiers = [RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH]
    risk_probs = [0.75, 0.18, 0.07]

    base_time = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(1, count + 1):
        payment_id = f"pay_syn_{i:05d}"
        event_id = f"evt_syn_{i:05d}"
        merchant_id = f"mer_syn_{(i % 120) + 1:03d}"
        customer_id = f"cust_syn_{(i % 850) + 1:04d}"

        # Payment Amount: Lognormal distribution spanning micro to high ticket
        # Median ~ ₹1,800, 90th percentile ~ ₹8,500
        raw_amt = rng.lognormvariate(7.4, 0.85)
        amount = round(min(99999.0, max(49.0, raw_amt)), 2)

        failure_type: FailureType = rng.choices(failure_choices, weights=failure_probs, k=1)[0]
        method: PaymentMethod = rng.choices(methods, weights=method_probs, k=1)[0]
        channel: Channel = rng.choices(channels, weights=channel_probs, k=1)[0]
        risk_tier: RiskTier = rng.choices(risk_tiers, weights=risk_probs, k=1)[0]
        
        # Hard decline adjustments
        if FailureType.is_hard_decline(failure_type):
            if failure_type == FailureType.MANDATE_REVOKED:
                method = PaymentMethod.MANDATE
                channel = Channel.RECURRING_SUBSCRIPTION
            elif failure_type in {FailureType.CARD_LOST_STOLEN, FailureType.CARD_EXPIRED}:
                method = PaymentMethod.CARD

        codes = FAILURE_CODES.get(failure_type, ["GENERIC_FAIL"])
        failure_code = rng.choice(codes)

        # Event Timestamp within past 30 days
        offset_minutes = rng.randint(0, 30 * 24 * 60)
        event_time = base_time + timedelta(minutes=offset_minutes)
        event_time_str = event_time.isoformat()

        # Prior attempts
        retry_count = rng.choices([0, 1, 2, 3], weights=[0.60, 0.25, 0.10, 0.05], k=1)[0]
        contact_count = rng.choices([0, 1, 2], weights=[0.75, 0.20, 0.05], k=1)[0]
        last_retry_at = None
        if retry_count > 0:
            last_retry_at = (event_time - timedelta(minutes=rng.randint(5, 120))).isoformat()

        # Merchant policy profile
        merchant_policy = {
            "max_retries": 3,
            "cooldown_minutes": 15,
            "customer_contact_cap": 2,
            "economic_hurdle": 10.0,
        }

        # Ground truth recovery probability (for synthetic benchmarking)
        if FailureType.is_hard_decline(failure_type):
            base_recovery_p = 0.0
            natural_recovery = None
        elif failure_type == FailureType.NETWORK_TIMEOUT:
            base_recovery_p = 0.65
            # Natural recovery: 12% of network timeouts naturally self-resolve if customer tries again
            natural_recovery = "NATURAL_RECOVERY_CONTROL" if rng.random() < 0.12 else None
        elif failure_type == FailureType.TEMPORARY_ISSUER_FAILURE:
            base_recovery_p = 0.58
            natural_recovery = "NATURAL_RECOVERY_CONTROL" if rng.random() < 0.08 else None
        elif failure_type == FailureType.INSUFFICIENT_FUNDS:
            base_recovery_p = 0.42
            natural_recovery = "NATURAL_RECOVERY_CONTROL" if rng.random() < 0.05 else None
        elif failure_type == FailureType.CARD_EXPIRED:
            base_recovery_p = 0.60
            natural_recovery = None
        elif failure_type == FailureType.AUTHENTICATION_REQUIRED:
            base_recovery_p = 0.68
            natural_recovery = "NATURAL_RECOVERY_CONTROL" if rng.random() < 0.10 else None
        else:
            base_recovery_p = 0.35
            natural_recovery = None

        payment = {
            "payment_id": payment_id,
            "event_id": event_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "amount": amount,
            "currency": "INR",
            "payment_method": method.value,
            "failure_type": failure_type.value,
            "failure_code": failure_code,
            "timestamp": event_time_str,
            "retry_count": retry_count,
            "last_retry_at": last_retry_at,
            "contact_count": contact_count,
            "merchant_policy": merchant_policy,
            "risk_tier": risk_tier.value,
            "channel": channel.value,
            "historical_recovery_probability": round(base_recovery_p, 3),
            "status": "FAILED",
            "natural_recovery_status": natural_recovery,
            "created_at": event_time_str
        }
        payments.append(payment)

    return payments

def ensure_synthetic_data_seeded(target_count: int = SYNTHETIC_DATASET_SIZE) -> int:
    """Checks existing payment count in SQLite. If less than target, generates and batch inserts."""
    current_count = count_payments()
    if current_count >= target_count:
        return current_count

    needed = target_count - current_count
    payments = generate_synthetic_payments(count=target_count, seed=RANDOM_SEED)
    insert_payments_batch(payments)
    return count_payments()
