from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import hashlib

from app.config import settings
from app.models.enums import (
    FailureType,
    ActionType,
    Channel,
    RiskTier,
    AIMode,
    GateStatus,
    DecisionOutcome,
    GovernorOperatingMode,
)
from app.models.schemas import (
    PolicyGateCheck,
    GovernorDecision,
    AIDiagnosisOutput,
    ERVCalculation,
)
from app.engine.erv import ERVEngine
from app.models.repositories import get_execution_by_idempotency, utc_now_iso

class EmergencyKillSwitchManager:
    """
    Emergency Kill Switch: Global hardware-level circuit breaker.
    When active, all automated recovery interventions are blocked and exposure prevented is tracked.
    """
    _is_active: bool = False
    _activated_at: Optional[str] = None
    _actions_blocked: int = 0
    _potential_exposure_prevented: float = 0.0
    _last_audit_id: Optional[str] = None

    @classmethod
    def is_active(cls) -> bool:
        return cls._is_active

    @classmethod
    def activate(cls, audit_id: Optional[str] = None) -> None:
        cls._is_active = True
        cls._activated_at = utc_now_iso()
        if audit_id:
            cls._last_audit_id = audit_id

    @classmethod
    def reset(cls) -> None:
        cls._is_active = False
        cls._activated_at = None
        cls._actions_blocked = 0
        cls._potential_exposure_prevented = 0.0
        cls._last_audit_id = None

    @classmethod
    def record_blocked(cls, amount: float) -> None:
        cls._actions_blocked += 1
        cls._potential_exposure_prevented += max(0.0, float(amount))

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "is_active": cls._is_active,
            "activated_at": cls._activated_at,
            "actions_blocked": cls._actions_blocked,
            "potential_exposure_prevented": round(cls._potential_exposure_prevented, 2),
            "last_audit_id": cls._last_audit_id,
        }

class RecoveryGovernor:
    """
    Deterministic Recovery Governor: Single Source of Financial Authority.
    Evaluates 8 deterministic safety gates before authorizing any financial recovery action.
    AI proposes. Deterministic code decides.
    """

    def __init__(
        self,
        max_retries: Optional[int] = None,
        cooldown_minutes: Optional[int] = None,
        customer_contact_cap: Optional[int] = None,
        economic_hurdle: Optional[float] = None,
        confidence_threshold: Optional[float] = None,
    ):
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.cooldown_minutes = cooldown_minutes if cooldown_minutes is not None else settings.cooldown_minutes
        self.customer_contact_cap = customer_contact_cap if customer_contact_cap is not None else settings.customer_contact_cap
        self.economic_hurdle = economic_hurdle if economic_hurdle is not None else settings.economic_hurdle
        self.confidence_threshold = confidence_threshold if confidence_threshold is not None else settings.ai_confidence_threshold
        self.version = "1.0.0"

    def evaluate(
        self,
        payment: Dict[str, Any],
        event_id: str,
        ai_diagnosis: AIDiagnosisOutput,
        ai_mode: AIMode = AIMode.DETERMINISTIC_FALLBACK,
        force_action: Optional[ActionType] = None,
        operating_mode: GovernorOperatingMode = GovernorOperatingMode.GOVERNED,
    ) -> GovernorDecision:
        payment_id = payment["payment_id"]
        amount = float(payment["amount"])
        failure_type = FailureType(payment["failure_type"]) if isinstance(payment["failure_type"], str) else payment["failure_type"]
        retry_count = int(payment.get("retry_count", 0))
        contact_count = int(payment.get("contact_count", 0))
        last_retry_at_str = payment.get("last_retry_at")
        risk_tier = RiskTier(payment.get("risk_tier", "LOW"))
        channel = Channel(payment.get("channel", "MOBILE_APP"))
        
        # Override merchant policy if present
        policy = payment.get("merchant_policy", {}) or {}
        max_retries = policy.get("max_retries", self.max_retries)
        cooldown_minutes = policy.get("cooldown_minutes", self.cooldown_minutes)
        contact_cap = policy.get("customer_contact_cap", self.customer_contact_cap)
        hurdle = policy.get("economic_hurdle", self.economic_hurdle)

        # --- PRE-GATE: GLOBAL EMERGENCY KILL SWITCH ---
        if EmergencyKillSwitchManager.is_active():
            EmergencyKillSwitchManager.record_blocked(amount)
            now_iso = utc_now_iso()
            decision_id = f"dec_{hashlib.sha256(f'{payment_id}_{now_iso}_{event_id}'.encode()).hexdigest()[:16]}"
            kill_gate = PolicyGateCheck(
                gate_name="GATE_0_EMERGENCY_KILL_SWITCH",
                status=GateStatus.BLOCKED,
                reason="EMERGENCY_STOP_ENGAGED: All automated payment recovery interventions are globally halted.",
                details=EmergencyKillSwitchManager.get_status()
            )
            candidates_list = [force_action] if force_action else [p.action for p in ai_diagnosis.candidate_actions]
            if ActionType.NO_ACTION not in candidates_list:
                candidates_list.append(ActionType.NO_ACTION)
            erv_map = {}
            for act in candidates_list:
                erv_map[act.value] = ERVEngine.calculate(
                    action=act,
                    payment_amount=amount,
                    failure_type=failure_type,
                    channel=channel,
                    retry_count=retry_count,
                    risk_tier=risk_tier,
                    hurdle=hurdle
                )
            return GovernorDecision(
                decision_id=decision_id,
                payment_id=payment_id,
                event_id=event_id,
                ai_diagnosis=ai_diagnosis.diagnosis,
                ai_confidence=ai_diagnosis.confidence,
                ai_mode=ai_mode,
                candidate_actions=candidates_list,
                erv_by_action=erv_map,
                policy_checks=[kill_gate],
                blocked_actions=[a.value for a in candidates_list],
                selected_action=ActionType.STOP,
                decision=DecisionOutcome.STOP,
                decision_outcome="EMERGENCY_STOP_BLOCKED",
                operating_mode=operating_mode,
                reason="All recovery actions halted by global Emergency Kill Switch.",
                confidence=ai_diagnosis.confidence,
                governor_version=self.version,
                timestamp=now_iso
            )

        # 1. Candidate Actions from AI + Fallback candidates
        if force_action:
            candidates = [force_action]
        else:
            candidates = [p.action for p in ai_diagnosis.candidate_actions]
        
        # Ensure NO_ACTION is always an available candidate
        if ActionType.NO_ACTION not in candidates:
            candidates.append(ActionType.NO_ACTION)

        # 2. Compute ERV for each candidate action
        erv_map: Dict[str, ERVCalculation] = {}
        for act in candidates:
            erv_map[act.value] = ERVEngine.calculate(
                action=act,
                payment_amount=amount,
                failure_type=failure_type,
                channel=channel,
                retry_count=retry_count,
                risk_tier=risk_tier,
                hurdle=hurdle
            )

        # 3. Deterministic Policy Gate Evaluation
        policy_checks: List[PolicyGateCheck] = []
        blocked_actions: List[str] = []
        
        # --- GATE 1: HARD DECLINE BAN ---
        is_hard_decline = FailureType.is_hard_decline(failure_type)
        if is_hard_decline:
            for act in candidates:
                if ActionType.is_retry(act):
                    blocked_actions.append(act.value)
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_1_HARD_DECLINE_BAN",
                status=GateStatus.BLOCKED if any(ActionType.is_retry(a) for a in candidates) else GateStatus.PASSED,
                reason=f"Failure type {failure_type.value} is a permanent hard decline. All automated retries strictly prohibited.",
                details={"failure_type": failure_type.value, "is_hard_decline": True}
            ))
        else:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_1_HARD_DECLINE_BAN",
                status=GateStatus.PASSED,
                reason=f"Failure type {failure_type.value} is not a permanent hard decline.",
                details={"failure_type": failure_type.value, "is_hard_decline": False}
            ))

        # --- GATE 2: RETRY CAP ---
        retry_cap_exceeded = retry_count >= max_retries
        if retry_cap_exceeded:
            for act in candidates:
                if ActionType.is_retry(act) and act.value not in blocked_actions:
                    blocked_actions.append(act.value)
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_2_RETRY_CAP",
                status=GateStatus.BLOCKED,
                reason=f"Payment retry limit reached ({retry_count} >= max {max_retries}). Retries prohibited.",
                details={"retry_count": retry_count, "max_retries": max_retries}
            ))
        else:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_2_RETRY_CAP",
                status=GateStatus.PASSED,
                reason=f"Retry count ({retry_count}) is within limit ({max_retries}).",
                details={"retry_count": retry_count, "max_retries": max_retries}
            ))

        # --- GATE 3: COOLDOWN ---
        in_cooldown = False
        remaining_seconds = 0
        if last_retry_at_str:
            try:
                last_retry_at = datetime.fromisoformat(last_retry_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                diff = (now - last_retry_at).total_seconds()
                cooldown_sec = cooldown_minutes * 60
                if diff < cooldown_sec:
                    in_cooldown = True
                    remaining_seconds = int(cooldown_sec - diff)
            except Exception:
                pass

        if in_cooldown:
            if ActionType.RETRY_NOW.value not in blocked_actions and ActionType.RETRY_NOW in candidates:
                blocked_actions.append(ActionType.RETRY_NOW.value)
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_3_COOLDOWN",
                status=GateStatus.BLOCKED,
                reason=f"Cooldown period active ({remaining_seconds}s remaining of {cooldown_minutes}m). Immediate retry blocked.",
                details={"cooldown_minutes": cooldown_minutes, "remaining_seconds": remaining_seconds}
            ))
        else:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_3_COOLDOWN",
                status=GateStatus.PASSED,
                reason=f"No active cooldown restriction ({cooldown_minutes}m required).",
                details={"cooldown_minutes": cooldown_minutes}
            ))

        # --- GATE 4: CUSTOMER CONTACT CAP ---
        contact_cap_exceeded = contact_count >= contact_cap
        if contact_cap_exceeded:
            for act in candidates:
                if ActionType.requires_customer_contact(act) and act.value not in blocked_actions:
                    blocked_actions.append(act.value)
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_4_CUSTOMER_CONTACT_CAP",
                status=GateStatus.BLOCKED,
                reason=f"Customer contact cap reached ({contact_count} >= max {contact_cap}). Outbound customer messages blocked to prevent churn.",
                details={"contact_count": contact_count, "max_contacts": contact_cap}
            ))
        else:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_4_CUSTOMER_CONTACT_CAP",
                status=GateStatus.PASSED,
                reason=f"Customer contact count ({contact_count}) is below limit ({contact_cap}).",
                details={"contact_count": contact_count, "max_contacts": contact_cap}
            ))

        # --- GATE 5: ECONOMIC HURDLE ---
        # Any candidate action that has negative ERV or fails the hurdle threshold is blocked
        for act in candidates:
            if act in {ActionType.NO_ACTION, ActionType.STOP}:
                continue
            calc = erv_map.get(act.value)
            if calc and (calc.net_erv <= 0 or calc.net_erv < hurdle):
                if act.value not in blocked_actions:
                    blocked_actions.append(act.value)

        has_economically_viable = any(
            act.value not in blocked_actions and erv_map[act.value].net_erv >= hurdle
            for act in candidates if act not in {ActionType.NO_ACTION, ActionType.STOP}
        )
        
        policy_checks.append(PolicyGateCheck(
            gate_name="GATE_5_ECONOMIC_HURDLE",
            status=GateStatus.PASSED if has_economically_viable else GateStatus.BLOCKED,
            reason=(
                f"At least one candidate action exceeds economic hurdle of ₹{hurdle:.2f}."
                if has_economically_viable else
                f"No candidate action achieves positive net ERV meeting economic hurdle of ₹{hurdle:.2f}."
            ),
            details={"hurdle": hurdle, "has_viable_action": has_economically_viable}
        ))

        # --- GATE 6: IDEMPOTENCY ---
        idempotency_key = f"idem_{payment_id}_{event_id}"
        existing_execution = get_execution_by_idempotency(idempotency_key)
        
        is_duplicate = bool(existing_execution)
        if is_duplicate:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_6_IDEMPOTENCY",
                status=GateStatus.SUPPRESSED,
                reason=f"Duplicate event detected for key {idempotency_key}. Action suppressed to prevent duplicate charges.",
                details={"idempotency_key": idempotency_key, "existing_execution_id": existing_execution["execution_id"]}
            ))
        else:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_6_IDEMPOTENCY",
                status=GateStatus.PASSED,
                reason="Idempotency check passed. No prior execution for this event key.",
                details={"idempotency_key": idempotency_key}
            ))

        # --- GATE 7: CONFIDENCE THRESHOLD ---
        low_confidence = ai_diagnosis.confidence < self.confidence_threshold
        if low_confidence:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_7_CONFIDENCE_THRESHOLD",
                status=GateStatus.BLOCKED,
                reason=f"AI diagnosis confidence ({ai_diagnosis.confidence:.2f}) is below safety threshold ({self.confidence_threshold:.2f}).",
                details={"confidence": ai_diagnosis.confidence, "threshold": self.confidence_threshold}
            ))
        else:
            policy_checks.append(PolicyGateCheck(
                gate_name="GATE_7_CONFIDENCE_THRESHOLD",
                status=GateStatus.PASSED,
                reason=f"AI diagnosis confidence ({ai_diagnosis.confidence:.2f}) satisfies safety threshold ({self.confidence_threshold:.2f}).",
                details={"confidence": ai_diagnosis.confidence, "threshold": self.confidence_threshold}
            ))

        # --- GATE 8: STOPPING RULE ---
        # Deduce final selected action and decision outcome
        viable_actions = [
            act for act in candidates
            if act.value not in blocked_actions and act not in {ActionType.NO_ACTION, ActionType.STOP}
        ]

        # Sort viable actions by Net ERV descending
        viable_actions.sort(key=lambda a: erv_map[a.value].net_erv, reverse=True)

        selected_action: ActionType
        decision: DecisionOutcome
        final_reason: str

        if is_duplicate:
            selected_action = ActionType.NO_ACTION
            decision = DecisionOutcome.SUPPRESS
            final_reason = f"Action suppressed by Gate 6 (Idempotency) to avoid duplicate financial execution."
            
        elif is_hard_decline and not viable_actions:
            selected_action = ActionType.STOP
            decision = DecisionOutcome.STOP
            final_reason = f"Recovery permanently halted by Gate 1 (Hard Decline Ban). Failure {failure_type.value} cannot be retried."
            
        elif retry_cap_exceeded and not viable_actions:
            selected_action = ActionType.STOP
            decision = DecisionOutcome.STOP
            final_reason = f"Recovery ceased by Gate 2 (Retry Cap). Maximum retry attempts reached ({retry_count}/{max_retries})."
            
        elif low_confidence:
            if amount >= 2000.0:
                selected_action = ActionType.HUMAN_ESCALATION
                decision = DecisionOutcome.HUMAN_ESCALATION
                final_reason = f"Gate 7 flagged low confidence ({ai_diagnosis.confidence:.2f}) on high-value transaction (₹{amount:,.2f}). Escalated to manual review."
            else:
                selected_action = ActionType.NO_ACTION
                decision = DecisionOutcome.NO_ACTION
                final_reason = f"Gate 7 flagged low confidence ({ai_diagnosis.confidence:.2f}). Conservative policy: NO_ACTION."

        elif viable_actions:
            best_action = viable_actions[0]
            selected_action = best_action
            decision = DecisionOutcome.EXECUTE
            best_erv = erv_map[best_action.value]
            final_reason = (
                f"Authorized {best_action.value}. Passed all safety gates with highest Net ERV (₹{best_erv.net_erv:,.2f}, "
                f"recovery prob {best_erv.recovery_probability:.1%})."
            )
        else:
            selected_action = ActionType.NO_ACTION
            decision = DecisionOutcome.NO_ACTION
            final_reason = "No candidate actions satisfied economic hurdle and safety gates. Smartest recovery action is doing nothing."

        policy_checks.append(PolicyGateCheck(
            gate_name="GATE_8_STOPPING_RULE",
            status=GateStatus.PASSED,
            reason=final_reason,
            details={"selected_action": selected_action.value, "decision": decision.value}
        ))

        now_iso = utc_now_iso()
        decision_id = f"dec_{hashlib.sha256(f'{payment_id}_{now_iso}_{event_id}'.encode()).hexdigest()[:16]}"
        outcome_str = "APPROVED" if decision == DecisionOutcome.EXECUTE else decision.value
        if operating_mode == GovernorOperatingMode.SHADOW and decision == DecisionOutcome.EXECUTE:
            outcome_str = "SHADOW_APPROVED"
            final_reason = f"SHADOW MODE: Action {selected_action.value} evaluated & approved by Governor gates, but execution withheld in Shadow observation mode."

        return GovernorDecision(
            decision_id=decision_id,
            payment_id=payment_id,
            event_id=event_id,
            ai_diagnosis=ai_diagnosis.diagnosis,
            ai_confidence=ai_diagnosis.confidence,
            ai_mode=ai_mode,
            candidate_actions=candidates,
            erv_by_action=erv_map,
            policy_checks=policy_checks,
            blocked_actions=list(set(blocked_actions)),
            selected_action=selected_action,
            decision=decision,
            decision_outcome=outcome_str,
            operating_mode=operating_mode,
            reason=final_reason,
            confidence=ai_diagnosis.confidence,
            governor_version=self.version,
            timestamp=now_iso
        )
