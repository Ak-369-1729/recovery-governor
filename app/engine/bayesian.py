import math
from typing import Tuple, Dict, Any, Optional
from app.models.enums import FailureType, ActionType, Channel
from app.models.repositories import get_bayesian_record, upsert_bayesian_record, get_all_bayesian_records

# Curated domain-informed priors (alpha, beta) for common failure-action-channel triples
# alpha / (alpha + beta) = prior expected recovery rate
DEFAULT_PRIORS: Dict[str, Tuple[float, float]] = {
    # Temporary issuer failure (30-min recovery window is the optimal immediate resolution window)
    f"{FailureType.TEMPORARY_ISSUER_FAILURE.value}::{ActionType.RETRY_30_MIN.value}": (14.0, 6.0),   # 70% optimal window
    f"{FailureType.TEMPORARY_ISSUER_FAILURE.value}::{ActionType.RETRY_2_HOURS.value}": (12.0, 8.0),  # 60%
    f"{FailureType.TEMPORARY_ISSUER_FAILURE.value}::{ActionType.RETRY_NOW.value}": (7.0, 13.0),      # 35% - issuer still down
    f"{FailureType.TEMPORARY_ISSUER_FAILURE.value}::{ActionType.SEND_PAYMENT_LINK.value}": (9.0, 11.0), # 45%
    
    # Network timeout
    f"{FailureType.NETWORK_TIMEOUT.value}::{ActionType.RETRY_NOW.value}": (11.0, 9.0),      # 55%
    f"{FailureType.NETWORK_TIMEOUT.value}::{ActionType.RETRY_30_MIN.value}": (13.0, 7.0),   # 65%
    
    # Bank server unavailable
    f"{FailureType.BANK_SERVER_UNAVAILABLE.value}::{ActionType.RETRY_2_HOURS.value}": (13.0, 7.0),  # 65%
    f"{FailureType.BANK_SERVER_UNAVAILABLE.value}::{ActionType.RETRY_NOW.value}": (4.0, 16.0),      # 20%
    
    # Insufficient funds
    f"{FailureType.INSUFFICIENT_FUNDS.value}::{ActionType.RETRY_NEXT_DAY.value}": (9.0, 11.0),       # 45%
    f"{FailureType.INSUFFICIENT_FUNDS.value}::{ActionType.SEND_REMINDER.value}": (8.0, 12.0),         # 40%
    f"{FailureType.INSUFFICIENT_FUNDS.value}::{ActionType.SEND_PAYMENT_LINK.value}": (10.0, 10.0),    # 50%
    f"{FailureType.INSUFFICIENT_FUNDS.value}::{ActionType.RETRY_NOW.value}": (3.0, 17.0),            # 15%
    
    # Card expired
    f"{FailureType.CARD_EXPIRED.value}::{ActionType.REQUEST_CUSTOMER_ACTION.value}": (14.0, 6.0),    # 70%
    f"{FailureType.CARD_EXPIRED.value}::{ActionType.SEND_PAYMENT_LINK.value}": (13.0, 7.0),          # 65%
    f"{FailureType.CARD_EXPIRED.value}::{ActionType.RETRY_NOW.value}": (0.5, 99.5),                  # <1%
    
    # Authentication required
    f"{FailureType.AUTHENTICATION_REQUIRED.value}::{ActionType.SEND_PAYMENT_LINK.value}": (14.0, 6.0), # 70%
    f"{FailureType.AUTHENTICATION_REQUIRED.value}::{ActionType.RETRY_NOW.value}": (2.0, 18.0),        # 10%
    
    # Hard declines (permanent - mathematically close to zero)
    f"{FailureType.CARD_LOST_STOLEN.value}::{ActionType.RETRY_NOW.value}": (0.1, 99.9),
    f"{FailureType.MANDATE_REVOKED.value}::{ActionType.RETRY_NOW.value}": (0.1, 99.9),
    f"{FailureType.ACCOUNT_CLOSED.value}::{ActionType.RETRY_NOW.value}": (0.1, 99.9),
    f"{FailureType.PERMANENT_DECLINE.value}::{ActionType.RETRY_NOW.value}": (0.1, 99.9),
}

class BayesianRecoveryModel:
    """
    Beta-Binomial Conjugate Bayesian Model for Recovery Probabilities.
    Maintains Beta(alpha + successes, beta + failures) per (failure_type, action, channel).
    """

    @staticmethod
    def _make_key(failure_type: str, action: str, channel: Optional[str] = None) -> str:
        # Channel-aware key with fallback to 2-tuple key
        return f"{failure_type}::{action}::{channel or Channel.MOBILE_APP.value}"

    @staticmethod
    def _get_base_priors(failure_type: str, action: str) -> Tuple[float, float]:
        lookup_key = f"{failure_type}::{action}"
        if lookup_key in DEFAULT_PRIORS:
            return DEFAULT_PRIORS[lookup_key]
            
        if FailureType.is_hard_decline(FailureType(failure_type)) if failure_type in FailureType.__members__ else False:
            return (0.1, 99.9)
            
        # Uninformative / weak prior with conservative 30% mean
        return (3.0, 7.0)

    _POSTERIOR_CACHE: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_posterior(cls, failure_type: str, action: str, channel: Optional[str] = None) -> Dict[str, Any]:
        key = cls._make_key(failure_type, action, channel)
        if key in cls._POSTERIOR_CACHE:
            return cls._POSTERIOR_CACHE[key]

        record = get_bayesian_record(key)
        
        if record:
            alpha_0 = record["alpha"]
            beta_0 = record["beta"]
            successes = record["successes"]
            failures = record["failures"]
        else:
            alpha_0, beta_0 = cls._get_base_priors(failure_type, action)
            successes = 0
            failures = 0
            
        alpha_post = alpha_0 + successes
        beta_post = beta_0 + failures
        total = alpha_post + beta_post
        
        mean = alpha_post / total
        variance = (alpha_post * beta_post) / ((total ** 2) * (total + 1))
        std_dev = math.sqrt(variance)
        
        # 95% Credible Interval approximation using normal approximation to beta distribution
        z = 1.96
        ci_lower = max(0.0, mean - z * std_dev)
        ci_upper = min(1.0, mean + z * std_dev)
        
        res = {
            "key": key,
            "failure_type": failure_type,
            "action": action,
            "channel": channel or Channel.MOBILE_APP.value,
            "prior_alpha": alpha_0,
            "prior_beta": beta_0,
            "successes": successes,
            "failures": failures,
            "posterior_alpha": alpha_post,
            "posterior_beta": beta_post,
            "posterior_mean": round(mean, 4),
            "posterior_variance": round(variance, 6),
            "std_dev": round(std_dev, 4),
            "credible_interval_95": (round(ci_lower, 4), round(ci_upper, 4)),
            "sample_weight": successes + failures,
        }
        cls._POSTERIOR_CACHE[key] = res
        return res

    @classmethod
    def update_outcome(cls, failure_type: str, action: str, channel: Optional[str], succeeded: bool):
        """
        Bayesian Conjugate update:
        Posterior ~ Beta(alpha + 1, beta) on success
        Posterior ~ Beta(alpha, beta + 1) on failure
        """
        key = cls._make_key(failure_type, action, channel)
        cls._POSTERIOR_CACHE.pop(key, None)
        record = get_bayesian_record(key)
        
        if record:
            alpha = record["alpha"]
            beta = record["beta"]
            successes = record["successes"] + (1 if succeeded else 0)
            failures = record["failures"] + (0 if succeeded else 1)
        else:
            alpha, beta = cls._get_base_priors(failure_type, action)
            successes = 1 if succeeded else 0
            failures = 0 if succeeded else 1
            
        upsert_bayesian_record(key, alpha, beta, successes, failures)

    @classmethod
    def get_all_models(cls):
        records = get_all_bayesian_records()
        res = []
        for r in records:
            key_parts = r["key"].split("::")
            failure_type = key_parts[0] if len(key_parts) > 0 else "UNKNOWN"
            action = key_parts[1] if len(key_parts) > 1 else "UNKNOWN"
            channel = key_parts[2] if len(key_parts) > 2 else "MOBILE_APP"
            
            alpha_post = r["alpha"] + r["successes"]
            beta_post = r["beta"] + r["failures"]
            total = alpha_post + beta_post
            mean = alpha_post / total
            var = (alpha_post * beta_post) / ((total ** 2) * (total + 1))
            
            res.append({
                "key": r["key"],
                "failure_type": failure_type,
                "action": action,
                "channel": channel,
                "alpha_prior": r["alpha"],
                "beta_prior": r["beta"],
                "successes": r["successes"],
                "failures": r["failures"],
                "posterior_mean": round(mean, 4),
                "std_dev": round(math.sqrt(var), 4),
                "samples": r["successes"] + r["failures"],
                "updated_at": r["updated_at"]
            })
        return res
