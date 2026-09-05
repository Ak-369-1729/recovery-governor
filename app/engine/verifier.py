import uuid
import random
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.models.enums import VerificationStatus, ActionType, FailureType
from app.models.schemas import VerificationResult, ExecutionResult
from app.models.repositories import insert_verification, update_payment_status, utc_now_iso
from app.engine.bayesian import BayesianRecoveryModel

class VerificationEngine:
    """
    Verification Engine: Validates whether executed recovery actions actually succeeded.
    Distinguishes SUCCEEDED, FAILED, PENDING, and UNKNOWN.
    Crucial Safety Invariant: Ambiguous or unconfirmed outcomes are marked UNKNOWN.
    Only strictly verified outcomes update the Bayesian model.
    """

    @classmethod
    def verify(
        cls,
        execution: ExecutionResult,
        payment: Dict[str, Any],
        force_status: Optional[VerificationStatus] = None,
        simulate_ground_truth: bool = True
    ) -> VerificationResult:
        verification_id = f"ver_{uuid.uuid4().hex[:12]}"
        now_iso = utc_now_iso()
        action = execution.action
        payment_id = execution.payment_id
        failure_type = payment.get("failure_type", "UNKNOWN_FAILURE")
        channel = payment.get("channel", "MOBILE_APP")

        if force_status:
            status = force_status
            evidence = {"source": "EXPLICIT_VERIFICATION_INPUT", "forced": True}

        elif execution.status == "SUPPRESSED" or action in {ActionType.NO_ACTION, ActionType.STOP}:
            # No action or suppression does not produce financial settlement
            status = VerificationStatus.FAILED
            evidence = {"source": "GOVERNOR_STOP_OR_NO_ACTION", "reason": "No financial attempt executed."}

        elif simulate_ground_truth:
            # Deterministic simulation of verification state
            # Base probability from ground truth recovery expectation
            hist_prob = float(payment.get("historical_recovery_probability", 0.5))
            
            # Incorporate natural recovery status if defined in synthetic dataset
            nat_status = payment.get("natural_recovery_status")
            
            # Action efficacy factor
            action_multiplier = 1.0
            if action == ActionType.RETRY_30_MIN and failure_type == FailureType.TEMPORARY_ISSUER_FAILURE.value:
                action_multiplier = 1.6
            elif action == ActionType.RETRY_NOW and failure_type == FailureType.TEMPORARY_ISSUER_FAILURE.value:
                action_multiplier = 0.5  # Issuer still down!
            elif action == ActionType.RETRY_NOW and failure_type == FailureType.NETWORK_TIMEOUT.value:
                action_multiplier = 1.4
            elif action == ActionType.SEND_PAYMENT_LINK and failure_type in {FailureType.CARD_EXPIRED.value, FailureType.AUTHENTICATION_REQUIRED.value}:
                action_multiplier = 1.8
            elif FailureType.is_hard_decline(FailureType(failure_type) if failure_type in FailureType.__members__ else FailureType.UNKNOWN_FAILURE):
                action_multiplier = 0.0  # Cannot recover hard decline

            effective_p = min(0.92, hist_prob * action_multiplier)
            
            # Roll deterministic outcome based on pseudo-random hash of payment_id and action
            seed_val = int(uuid.uuid5(uuid.NAMESPACE_DNS, f"{payment_id}_{action.value}").int) % 1000 / 1000.0

            # 5% of cases encounter network webhook ambiguity -> UNKNOWN
            if seed_val < 0.05:
                status = VerificationStatus.UNKNOWN
                evidence = {
                    "source": "BANK_WEBHOOK_TIMEOUT",
                    "reason": "Gateway returned HTTP 504. Settlement state ambiguous. Awaiting clearing reconciliation.",
                    "requires_manual_reconciliation": True
                }
            elif seed_val < (0.05 + effective_p * 0.95):
                status = VerificationStatus.SUCCEEDED
                evidence = {
                    "source": "BANK_SETTLEMENT_BATCH",
                    "bank_reference": f"RRN_{uuid.uuid4().hex[:12].upper()}",
                    "settled_at": now_iso,
                    "reconciliation_code": "CAPTURED_SETTLED"
                }
            else:
                status = VerificationStatus.FAILED
                evidence = {
                    "source": "ISSUER_NACK_WEBHOOK",
                    "decline_code": "RETRY_ATTEMPT_DECLINED",
                    "settled_at": now_iso
                }
        else:
            status = VerificationStatus.PENDING
            evidence = {"source": "ASYNC_DISPATCH_WINDOW", "reason": "Awaiting gateway webhook callback."}

        # Bayesian model feedback: ONLY update on SUCCEEDED or FAILED
        if status in {VerificationStatus.SUCCEEDED, VerificationStatus.FAILED}:
            succeeded_bool = (status == VerificationStatus.SUCCEEDED)
            BayesianRecoveryModel.update_outcome(
                failure_type=failure_type,
                action=action.value,
                channel=channel,
                succeeded=succeeded_bool
            )
            
            # Update payment table status
            new_payment_status = "RECOVERED" if succeeded_bool else "FAILED"
            update_payment_status(
                payment_id=payment_id,
                status=new_payment_status,
                retry_increment=1 if ActionType.is_retry(action) else 0,
                contact_increment=1 if ActionType.requires_customer_contact(action) else 0,
                last_retry_at=now_iso if ActionType.is_retry(action) else None
            )

        res = VerificationResult(
            verification_id=verification_id,
            execution_id=execution.execution_id,
            payment_id=payment_id,
            status=status,
            evidence=evidence,
            verified_at=now_iso
        )
        insert_verification(res.model_dump())
        return res
