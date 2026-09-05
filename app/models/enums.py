from enum import Enum
from typing import Dict, Any

class FailureType(str, Enum):
    TEMPORARY_ISSUER_FAILURE = "TEMPORARY_ISSUER_FAILURE"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    BANK_SERVER_UNAVAILABLE = "BANK_SERVER_UNAVAILABLE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    CARD_EXPIRED = "CARD_EXPIRED"
    CARD_LOST_STOLEN = "CARD_LOST_STOLEN"
    MANDATE_REVOKED = "MANDATE_REVOKED"
    ACCOUNT_CLOSED = "ACCOUNT_CLOSED"
    PERMANENT_DECLINE = "PERMANENT_DECLINE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

    @classmethod
    def is_hard_decline(cls, failure: "FailureType") -> bool:
        return failure in {
            cls.CARD_LOST_STOLEN,
            cls.MANDATE_REVOKED,
            cls.ACCOUNT_CLOSED,
            cls.PERMANENT_DECLINE,
        }

class ActionType(str, Enum):
    RETRY_NOW = "RETRY_NOW"
    RETRY_30_MIN = "RETRY_30_MIN"
    RETRY_2_HOURS = "RETRY_2_HOURS"
    RETRY_NEXT_DAY = "RETRY_NEXT_DAY"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    SEND_REMINDER = "SEND_REMINDER"
    REQUEST_CUSTOMER_ACTION = "REQUEST_CUSTOMER_ACTION"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    NO_ACTION = "NO_ACTION"
    STOP = "STOP"

    @classmethod
    def is_retry(cls, action: "ActionType") -> bool:
        return action in {
            cls.RETRY_NOW,
            cls.RETRY_30_MIN,
            cls.RETRY_2_HOURS,
            cls.RETRY_NEXT_DAY,
        }

    @classmethod
    def requires_customer_contact(cls, action: "ActionType") -> bool:
        return action in {
            cls.SEND_PAYMENT_LINK,
            cls.SEND_REMINDER,
            cls.REQUEST_CUSTOMER_ACTION,
        }

class PaymentMethod(str, Enum):
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    MANDATE = "MANDATE"
    WALLET = "WALLET"

class Channel(str, Enum):
    MOBILE_APP = "MOBILE_APP"
    WEB_CHECKOUT = "WEB_CHECKOUT"
    RECURRING_SUBSCRIPTION = "RECURRING_SUBSCRIPTION"

class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class AIMode(str, Enum):
    GEMINI = "GEMINI"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"

class GateStatus(str, Enum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    SUPPRESSED = "SUPPRESSED"

class DecisionOutcome(str, Enum):
    EXECUTE = "EXECUTE"
    SUPPRESS = "SUPPRESS"
    NO_ACTION = "NO_ACTION"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    STOP = "STOP"

class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    SUPPRESSED = "SUPPRESSED"
    FAILED = "FAILED"

class VerificationStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"

class AttributionCategory(str, Enum):
    ATTRIBUTED_RECOVERY = "ATTRIBUTED_RECOVERY"
    NATURAL_RECOVERY = "NATURAL_RECOVERY"
    UNKNOWN = "UNKNOWN"
    FAILED_RECOVERY = "FAILED_RECOVERY"

class BenchmarkCohort(str, Enum):
    CONTROL = "CONTROL"
    BASELINE = "BASELINE"
    GOVERNOR = "GOVERNOR"

# Action Catalog metadata with financial cost parameters (in INR)
ACTION_CATALOG: Dict[ActionType, Dict[str, Any]] = {
    ActionType.RETRY_NOW: {
        "delay_minutes": 0,
        "intervention_cost": 5.0,     # Payment gateway processing / auth attempt fee
        "risk_cost": 10.0,            # Issuer rate limiting / chargeback risk penalty
        "friction_cost": 0.0,         # Zero customer friction (invisible retry)
        "requires_customer_action": False,
        "requires_human_approval": False,
        "description": "Immediate automated retry via original payment rail",
    },
    ActionType.RETRY_30_MIN: {
        "delay_minutes": 30,
        "intervention_cost": 5.0,
        "risk_cost": 4.0,             # Lower risk cost after initial issuer cool-off
        "friction_cost": 0.0,
        "requires_customer_action": False,
        "requires_human_approval": False,
        "description": "Scheduled retry after 30-minute issuer recovery window",
    },
    ActionType.RETRY_2_HOURS: {
        "delay_minutes": 120,
        "intervention_cost": 5.0,
        "risk_cost": 4.0,
        "friction_cost": 0.0,
        "requires_customer_action": False,
        "requires_human_approval": False,
        "description": "Scheduled retry after 2-hour banking clearing window",
    },
    ActionType.RETRY_NEXT_DAY: {
        "delay_minutes": 1440,
        "intervention_cost": 5.0,
        "risk_cost": 3.0,
        "friction_cost": 0.0,
        "requires_customer_action": False,
        "requires_human_approval": False,
        "description": "Scheduled retry next business morning (e.g. balance top-up / salary cycle)",
    },
    ActionType.SEND_PAYMENT_LINK: {
        "delay_minutes": 0,
        "intervention_cost": 3.0,     # SMS/WhatsApp notification dispatch cost
        "risk_cost": 2.0,             # Minimal risk
        "friction_cost": 25.0,        # Moderate customer friction (requires manual action)
        "requires_customer_action": True,
        "requires_human_approval": False,
        "description": "Generate multi-rail dynamic payment link sent to customer",
    },
    ActionType.SEND_REMINDER: {
        "delay_minutes": 60,
        "intervention_cost": 2.0,
        "risk_cost": 1.0,
        "friction_cost": 15.0,
        "requires_customer_action": True,
        "requires_human_approval": False,
        "description": "Gentle SMS / Push reminder for pending invoice",
    },
    ActionType.REQUEST_CUSTOMER_ACTION: {
        "delay_minutes": 0,
        "intervention_cost": 4.0,
        "risk_cost": 2.0,
        "friction_cost": 35.0,        # Higher friction (requesting mandate re-authorization or new card)
        "requires_customer_action": True,
        "requires_human_approval": False,
        "description": "Request customer update payment method or re-authorize mandate",
    },
    ActionType.HUMAN_ESCALATION: {
        "delay_minutes": 0,
        "intervention_cost": 150.0,   # Human ops team review cost
        "risk_cost": 0.0,
        "friction_cost": 10.0,
        "requires_customer_action": False,
        "requires_human_approval": True,
        "description": "Escalate to high-value manual recovery & account manager review",
    },
    ActionType.NO_ACTION: {
        "delay_minutes": 0,
        "intervention_cost": 0.0,
        "risk_cost": 0.0,
        "friction_cost": 0.0,
        "requires_customer_action": False,
        "requires_human_approval": False,
        "description": "Do not intervene. Allow natural recovery or avoid negative ERV",
    },
    ActionType.STOP: {
        "delay_minutes": 0,
        "intervention_cost": 0.0,
        "risk_cost": 0.0,
        "friction_cost": 0.0,
        "requires_customer_action": False,
        "requires_human_approval": False,
        "description": "Permanently cease recovery attempts (hard decline or caps exhausted)",
    },
}
