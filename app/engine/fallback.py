from typing import Dict, Any, List
from app.models.enums import FailureType, ActionType
from app.models.schemas import AIDiagnosisOutput, CandidateActionProposal

class DeterministicFallbackEngine:
    """
    Expert rule-based fallback diagnosis engine.
    Produces high-fidelity, structured diagnosis and candidate actions
    when Gemini AI is unavailable, unconfigured, or timed out.
    """

    @classmethod
    def diagnose(cls, payment: Dict[str, Any]) -> AIDiagnosisOutput:
        failure_type_raw = payment.get("failure_type", "UNKNOWN_FAILURE")
        try:
            failure_type = FailureType(failure_type_raw)
        except ValueError:
            failure_type = FailureType.UNKNOWN_FAILURE

        amount = float(payment.get("amount", 0.0))
        method = payment.get("payment_method", "CARD")
        retry_count = int(payment.get("retry_count", 0))
        risk_tier = payment.get("risk_tier", "LOW")

        risk_flags: List[str] = []
        if risk_tier == "HIGH":
            risk_flags.append("HIGH_RISK_CUSTOMER_PROFILE")
        if amount > 10000.0:
            risk_flags.append("HIGH_TICKET_TRANSACTION")
        if retry_count >= 2:
            risk_flags.append("REPEATED_PRIOR_FAILURES")

        if failure_type == FailureType.TEMPORARY_ISSUER_FAILURE:
            return AIDiagnosisOutput(
                diagnosis="Transient failure at issuer switch or core banking system. Immediate retry has high collision probability.",
                confidence=0.88,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.RETRY_30_MIN,
                        reason="Historical recovery jumps from 35% to 65% when allowing a 30-minute issuer recovery window."
                    ),
                    CandidateActionProposal(
                        action=ActionType.RETRY_2_HOURS,
                        reason="Secondary window provides clearing stability if switch restart takes >1 hour."
                    ),
                    CandidateActionProposal(
                        action=ActionType.SEND_PAYMENT_LINK,
                        reason="Alternate payment rail bypasses current issuer outage."
                    )
                ],
                risk_flags=risk_flags
            )

        elif failure_type == FailureType.NETWORK_TIMEOUT:
            return AIDiagnosisOutput(
                diagnosis="Network packet drop or gateway socket timeout during handoff. Transaction state was not committed.",
                confidence=0.84,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.RETRY_NOW,
                        reason="Network glitches are often instantaneous; immediate retry captures high natural recovery."
                    ),
                    CandidateActionProposal(
                        action=ActionType.RETRY_30_MIN,
                        reason="Fallback if local infrastructure routing remains degraded."
                    )
                ],
                risk_flags=risk_flags
            )

        elif failure_type == FailureType.BANK_SERVER_UNAVAILABLE:
            return AIDiagnosisOutput(
                diagnosis="Bank node offline or returning 503 HTTP gateway timeout. Core banking maintenance likely.",
                confidence=0.86,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.RETRY_2_HOURS,
                        reason="Allows sufficient window for bank maintenance window to conclude."
                    ),
                    CandidateActionProposal(
                        action=ActionType.SEND_PAYMENT_LINK,
                        reason="Allows customer to select an alternate bank or payment method."
                    )
                ],
                risk_flags=risk_flags
            )

        elif failure_type == FailureType.INSUFFICIENT_FUNDS:
            return AIDiagnosisOutput(
                diagnosis="Customer account has insufficient funds to clear transaction. Retrying immediately wastes auth fees.",
                confidence=0.90,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.RETRY_NEXT_DAY,
                        reason="Next-day retry aligns with bank balance replenishments and salary cycles."
                    ),
                    CandidateActionProposal(
                        action=ActionType.SEND_REMINDER,
                        reason="Gentle prompt alerts customer to top-up funds without causing chargeback friction."
                    ),
                    CandidateActionProposal(
                        action=ActionType.SEND_PAYMENT_LINK,
                        reason="Allows customer to settle using credit card or secondary account."
                    )
                ],
                risk_flags=risk_flags
            )

        elif failure_type == FailureType.CARD_EXPIRED:
            return AIDiagnosisOutput(
                diagnosis="Stored payment card instrument has reached its expiration date. Retries will fail 100% of the time.",
                confidence=0.96,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.REQUEST_CUSTOMER_ACTION,
                        reason="Direct prompt to update card details or select fresh payment instrument."
                    ),
                    CandidateActionProposal(
                        action=ActionType.SEND_PAYMENT_LINK,
                        reason="Dynamic link enabling one-click update and payment completion."
                    )
                ],
                risk_flags=risk_flags + ["CARD_INSTRUMENT_INVALID"]
            )

        elif failure_type == FailureType.AUTHENTICATION_REQUIRED:
            return AIDiagnosisOutput(
                diagnosis="Issuer 3DS OTP step-up required or biometric challenge was abandoned by user.",
                confidence=0.85,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.SEND_PAYMENT_LINK,
                        reason="Fresh checkout session allows customer to complete 3DS authentication securely."
                    ),
                    CandidateActionProposal(
                        action=ActionType.SEND_REMINDER,
                        reason="Reminds customer that payment requires authorization."
                    )
                ],
                risk_flags=risk_flags
            )

        elif FailureType.is_hard_decline(failure_type):
            risk_flags.append("PERMANENT_DECLINE_DETECTED")
            return AIDiagnosisOutput(
                diagnosis=f"Permanent hard decline: {failure_type.value}. Card stolen/mandate revoked/account closed.",
                confidence=0.98,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.STOP,
                        reason="Hard decline requires absolute termination of retries to prevent card scheme fines."
                    ),
                    CandidateActionProposal(
                        action=ActionType.NO_ACTION,
                        reason="Zero-cost non-intervention protects merchant standing."
                    )
                ],
                risk_flags=risk_flags
            )

        else:
            return AIDiagnosisOutput(
                diagnosis="Uncategorized payment failure. Conservative review recommended.",
                confidence=0.60,
                candidate_actions=[
                    CandidateActionProposal(
                        action=ActionType.RETRY_30_MIN,
                        reason="Default conservative retry window."
                    ),
                    CandidateActionProposal(
                        action=ActionType.NO_ACTION,
                        reason="Avoid speculative retry costs when failure etiology is unknown."
                    )
                ],
                risk_flags=risk_flags
            )
