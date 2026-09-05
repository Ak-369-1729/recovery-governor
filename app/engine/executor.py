import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.config import settings
from app.models.enums import ActionType, ExecutionStatus, DecisionOutcome
from app.models.schemas import GovernorDecision, ExecutionResult
from app.models.repositories import insert_execution, get_execution_by_idempotency, utc_now_iso

class RecoveryActionExecutor:
    """
    Action Execution Layer: Dispatches Governor decisions to execution adapters.
    Supports SimulationAdapter and RazorpayAdapter (test mode).
    """

    @classmethod
    def execute(
        cls,
        decision: GovernorDecision,
        payment: Dict[str, Any],
        adapter_override: Optional[str] = None
    ) -> ExecutionResult:
        action = decision.selected_action
        payment_id = decision.payment_id
        decision_id = decision.decision_id
        now_iso = utc_now_iso()
        
        # Build strict idempotency key
        idempotency_key = f"idem_{payment_id}_{decision.event_id}"

        # If decision is SUPPRESS, record suppressed execution
        if decision.decision == DecisionOutcome.SUPPRESS:
            execution_id = f"exec_sup_{uuid.uuid4().hex[:12]}"
            res = ExecutionResult(
                execution_id=execution_id,
                decision_id=decision_id,
                payment_id=payment_id,
                action=action,
                adapter_type="SIMULATION",
                status=ExecutionStatus.SUPPRESSED,
                response_payload={"message": "Execution suppressed by Governor Gate 6 (Idempotency)"},
                idempotency_key=idempotency_key,
                timestamp=now_iso
            )
            insert_execution(res.model_dump())
            return res

        # If NO_ACTION or STOP, record non-action execution
        if decision.decision in {DecisionOutcome.NO_ACTION, DecisionOutcome.STOP}:
            execution_id = f"exec_noop_{uuid.uuid4().hex[:12]}"
            res = ExecutionResult(
                execution_id=execution_id,
                decision_id=decision_id,
                payment_id=payment_id,
                action=action,
                adapter_type="SIMULATION",
                status=ExecutionStatus.EXECUTED,
                response_payload={"message": f"Governor instructed {decision.decision.value}: no financial rails invoked."},
                idempotency_key=idempotency_key,
                timestamp=now_iso
            )
            insert_execution(res.model_dump())
            return res

        # Choose adapter: Razorpay test mode or Simulation
        use_razorpay = (adapter_override == "RAZORPAY" or settings.has_razorpay) and adapter_override != "SIMULATION"

        if use_razorpay:
            return cls._execute_razorpay(decision, payment, idempotency_key, now_iso)
        else:
            return cls._execute_simulation(decision, payment, idempotency_key, now_iso)

    @classmethod
    def _execute_simulation(
        cls,
        decision: GovernorDecision,
        payment: Dict[str, Any],
        idempotency_key: str,
        timestamp: str
    ) -> ExecutionResult:
        execution_id = f"exec_sim_{uuid.uuid4().hex[:12]}"
        action = decision.selected_action
        amount = payment.get("amount", 0.0)
        
        payload: Dict[str, Any] = {
            "mode": "SIMULATION",
            "action": action.value,
            "target_rail": payment.get("payment_method", "UPI"),
            "authorized_by_governor": True,
            "governor_version": decision.governor_version,
            "simulated_trace_id": f"sim_trace_{uuid.uuid4().hex[:16]}",
        }

        if action in {ActionType.RETRY_NOW, ActionType.RETRY_30_MIN, ActionType.RETRY_2_HOURS, ActionType.RETRY_NEXT_DAY}:
            payload["gateway_command"] = "PAYMENT_REATTEMPT"
            payload["scheduled_delay_minutes"] = 0 if action == ActionType.RETRY_NOW else (30 if action == ActionType.RETRY_30_MIN else 120)
            payload["queue_status"] = "DISPATCHED" if action == ActionType.RETRY_NOW else "SCHEDULED"

        elif action == ActionType.SEND_PAYMENT_LINK:
            payload["payment_link_id"] = f"plink_sim_{uuid.uuid4().hex[:14]}"
            payload["short_url"] = f"https://rzp.io/i/sim_{payment['payment_id'][-6:]}"
            payload["status"] = "ISSUED"
            payload["amount"] = amount

        elif action in {ActionType.SEND_REMINDER, ActionType.REQUEST_CUSTOMER_ACTION}:
            payload["notification_channel"] = "WHATSAPP_SMS"
            payload["dispatch_status"] = "DELIVERED"

        elif action == ActionType.HUMAN_ESCALATION:
            payload["ticket_id"] = f"TICK_ESC_{uuid.uuid4().hex[:8].upper()}"
            payload["assigned_queue"] = "HIGH_VALUE_RECOVERY_OPS"
            payload["priority"] = "P1"

        res = ExecutionResult(
            execution_id=execution_id,
            decision_id=decision.decision_id,
            payment_id=decision.payment_id,
            action=action,
            adapter_type="SIMULATION",
            status=ExecutionStatus.EXECUTED,
            response_payload=payload,
            idempotency_key=idempotency_key,
            timestamp=timestamp
        )
        insert_execution(res.model_dump())
        return res

    @classmethod
    def _execute_razorpay(
        cls,
        decision: GovernorDecision,
        payment: Dict[str, Any],
        idempotency_key: str,
        timestamp: str
    ) -> ExecutionResult:
        execution_id = f"exec_rzp_{uuid.uuid4().hex[:12]}"
        action = decision.selected_action
        
        # Test mode Razorpay integration
        try:
            import requests
            auth = (settings.razorpay_key_id, settings.razorpay_key_secret)
            amount_paise = int(float(payment.get("amount", 0.0)) * 100)

            if action == ActionType.SEND_PAYMENT_LINK:
                resp = requests.post(
                    "https://api.razorpay.com/v1/payment_links",
                    auth=auth,
                    json={
                        "amount": amount_paise,
                        "currency": "INR",
                        "accept_partial": False,
                        "description": f"Recovery for failed payment {payment['payment_id']}",
                        "customer": {
                            "name": f"Customer {payment['customer_id']}",
                            "contact": "+919999999999",
                            "email": "customer@example.synthetic"
                        },
                        "notify": {"sms": True, "email": True},
                        "reminder_enable": True,
                        "reference_id": payment['payment_id']
                    },
                    timeout=5.0
                )
                payload = resp.json()
            else:
                payload = {
                    "mode": "RAZORPAY_TEST_API",
                    "note": f"Action {action.value} recorded in Razorpay test mode tracking",
                    "payment_id": payment['payment_id']
                }

            res = ExecutionResult(
                execution_id=execution_id,
                decision_id=decision.decision_id,
                payment_id=decision.payment_id,
                action=action,
                adapter_type="RAZORPAY_TEST_MODE",
                status=ExecutionStatus.EXECUTED,
                response_payload=payload,
                idempotency_key=idempotency_key,
                timestamp=timestamp
            )
        except Exception as e:
            # Fallback to simulation execution if test api network error occurs
            return cls._execute_simulation(decision, payment, idempotency_key, timestamp)

        insert_execution(res.model_dump())
        return res
