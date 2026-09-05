from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from app.models.enums import (
    FailureType,
    ActionType,
    PaymentMethod,
    Channel,
    RiskTier,
    AIMode,
    GateStatus,
    DecisionOutcome,
    ExecutionStatus,
    VerificationStatus,
    AttributionCategory,
    BenchmarkCohort,
    GovernorOperatingMode,
    AutonomyLevel,
    StrategyType,
    ChaosType,
)

# AI Diagnosis Schemas
class CandidateActionProposal(BaseModel):
    action: ActionType
    reason: str

class AIDiagnosisOutput(BaseModel):
    diagnosis: str
    confidence: float = Field(ge=0.0, le=1.0)
    candidate_actions: List[CandidateActionProposal]
    risk_flags: List[str] = Field(default_factory=list)

# ERV Schemas
class ERVCalculation(BaseModel):
    action: ActionType
    recovery_probability: float = Field(ge=0.0, le=1.0)
    payment_amount: float
    gross_expected_recovery: float
    intervention_cost: float
    risk_cost: float
    friction_cost: float
    net_erv: float
    is_economically_viable: bool
    formula_breakdown: str

# Policy Check Schema
class PolicyGateCheck(BaseModel):
    gate_name: str
    status: GateStatus
    reason: str
    details: Optional[Dict[str, Any]] = None

# Governor Decision Schema
class GovernorDecision(BaseModel):
    decision_id: str
    payment_id: str
    event_id: str
    ai_diagnosis: str
    ai_confidence: float
    ai_mode: AIMode
    candidate_actions: List[ActionType]
    erv_by_action: Dict[str, ERVCalculation]
    policy_checks: List[PolicyGateCheck]
    blocked_actions: List[str]
    selected_action: ActionType
    decision: DecisionOutcome
    decision_outcome: str = "APPROVED"
    operating_mode: GovernorOperatingMode = GovernorOperatingMode.GOVERNED
    reason: str
    confidence: float
    governor_version: str = "1.0.0"
    timestamp: str

# Payment Event Schema
class PaymentEvent(BaseModel):
    payment_id: str
    event_id: str
    merchant_id: str
    customer_id: str
    amount: float
    currency: str = "INR"
    payment_method: PaymentMethod
    failure_type: FailureType
    failure_code: str
    timestamp: str
    retry_count: int = 0
    last_retry_at: Optional[str] = None
    contact_count: int = 0
    merchant_policy: Dict[str, Any] = Field(default_factory=dict)
    risk_tier: RiskTier = RiskTier.LOW
    channel: Channel = Channel.MOBILE_APP
    historical_recovery_probability: float = 0.5
    status: str = "FAILED"
    natural_recovery_status: Optional[str] = None
    created_at: Optional[str] = None

# Execution & Verification Schemas
class ExecutionResult(BaseModel):
    execution_id: str
    decision_id: str
    payment_id: str
    action: ActionType
    adapter_type: str
    status: ExecutionStatus
    response_payload: Dict[str, Any]
    idempotency_key: str
    timestamp: str

class VerificationResult(BaseModel):
    verification_id: str
    execution_id: str
    payment_id: str
    status: VerificationStatus
    evidence: Dict[str, Any]
    verified_at: str

class AttributionResult(BaseModel):
    attribution_id: str
    payment_id: str
    category: AttributionCategory
    counterfactual_method: str
    recovered_amount: float
    net_recovered_value: float
    cost_breakdown: Dict[str, float]
    timestamp: str

# Audit Log Schema
class AuditRecord(BaseModel):
    log_id: str
    event_type: str
    payment_id: str
    trace_id: str
    payload: Dict[str, Any]
    prev_hash: str
    hash: str
    timestamp: str

# Benchmark & Metrics
class BenchmarkMetrics(BaseModel):
    cohort: BenchmarkCohort
    sample_size: int
    gross_failed_volume: float
    gross_recovered: float
    recovery_rate: float
    attributed_recovery: float
    natural_recovery: float
    incremental_recovery_vs_control: float
    incremental_recovery_vs_baseline: float
    intervention_count: int
    total_intervention_cost: float
    total_risk_cost: float
    total_friction_cost: float
    net_recovery_value: float
    unsafe_actions_blocked: int
    duplicate_actions_suppressed: int

class DashboardMetrics(BaseModel):
    revenue_at_risk: float
    incrementally_recovered: float
    recovery_rate: float
    recovery_lift_vs_baseline: float
    intervention_rate: float
    total_intervention_cost: float
    net_recovery_value: float
    unsafe_actions_blocked: int
    human_escalations: int
    average_time_to_recovery_minutes: float
    total_payments_analyzed: int
    gemini_diagnoses_count: int
    fallback_diagnoses_count: int

# =============================================================================
# PHASE-2 SCHEMAS: SANDBOX, WHAT-IF, ARENA, READINESS, AUTONOMY, KILL SWITCH
# =============================================================================

class WhatIfActionEvaluation(BaseModel):
    action: ActionType
    action_label: str
    description: str
    recovery_probability: float = Field(ge=0.0, le=1.0)
    expected_gross_recovery: float
    intervention_cost: float
    friction_cost: float
    risk_cost: float
    net_erv: float
    is_viable: bool
    governor_eligible: bool
    gate_block_reasons: List[str] = Field(default_factory=list)
    confidence: float
    is_governor_choice: bool = False

class WhatIfComparisonResponse(BaseModel):
    scenario_id: str
    payment_amount: float
    total_candidate_actions_evaluated: int  # Dynamic count from ActionType
    evaluations: List[WhatIfActionEvaluation]
    governor_selected_action: ActionType
    governor_selected_net_erv: float
    selection_rationale: str

class SandboxScenarioRequest(BaseModel):
    scenario_id: Optional[str] = None
    amount: float = 4999.0
    currency: str = "INR"
    payment_method: PaymentMethod = PaymentMethod.UPI
    failure_type: FailureType = FailureType.TEMPORARY_ISSUER_FAILURE
    failure_code: str = "ISSUER_504_TIMEOUT"
    retry_count: int = 0
    time_since_failure_minutes: int = 5
    customer_ltv: float = 15000.0
    customer_success_rate: float = 0.85
    customer_contact_count: int = 0
    preferred_channel: str = "WHATSAPP"
    risk_tier: RiskTier = RiskTier.LOW
    channel: Channel = Channel.MOBILE_APP
    operating_mode: GovernorOperatingMode = GovernorOperatingMode.GOVERNED
    chaos_injection: Optional[ChaosType] = None
    policy_overrides: Dict[str, Any] = Field(default_factory=dict)

class StrategyResultItem(BaseModel):
    strategy: StrategyType
    strategy_label: str
    sample_size: int
    failed_payment_value: float
    recovered_value: float
    recovery_rate: float
    incremental_recovery: float
    intervention_count: int
    intervention_rate: float
    intervention_cost: float
    friction_cost: float
    risk_cost: float
    net_recovery: float
    recovery_lift: float
    unsafe_actions_prevented: int
    average_time_to_recovery_minutes: float
    attribution_breakdown: Dict[str, int] = Field(default_factory=dict)

class StrategyArenaRequest(BaseModel):
    population_size: int = 500
    seed: int = 42
    strategies: List[StrategyType] = Field(default_factory=lambda: list(StrategyType))
    policy_overrides: Dict[str, Any] = Field(default_factory=dict)

class PortfolioSimulationResponse(BaseModel):
    simulation_id: str
    population_size: int
    seed: int
    results: Dict[str, StrategyResultItem]
    sensitivity_summary: Optional[Dict[str, Any]] = None
    execution_time_ms: float

class RecoveryAIReadinessBreakdown(BaseModel):
    safety_score: float = Field(ge=0.0, le=30.0)
    safety_max: float = 30.0
    safety_notes: str
    economic_efficiency_score: float = Field(ge=0.0, le=25.0)
    economic_efficiency_max: float = 25.0
    economic_efficiency_notes: str
    fallback_reliability_score: float = Field(ge=0.0, le=15.0)
    fallback_reliability_max: float = 15.0
    fallback_reliability_notes: str
    accuracy_calibration_score: float = Field(ge=0.0, le=15.0)
    accuracy_calibration_max: float = 15.0
    accuracy_calibration_notes: str
    verification_attribution_score: float = Field(ge=0.0, le=15.0)
    verification_attribution_max: float = 15.0
    verification_attribution_notes: str
    total_score: float = Field(ge=0.0, le=100.0)
    methodology_doc: str

class AutonomyStatusResponse(BaseModel):
    current_level: AutonomyLevel
    level_name: str
    readiness_score: float
    readiness_breakdown: RecoveryAIReadinessBreakdown
    safety_rate: float
    recovery_lift: float
    unsafe_action_rate: float
    fallback_success_rate: float
    critical_violations_count: int
    is_eligible_for_promotion: bool
    promotion_target_level: Optional[AutonomyLevel] = None
    eligibility_criteria: Dict[str, Dict[str, Any]]
    architectural_invariant: str = (
        "AI proposes. Deterministic Governor decides. Direct financial execution by AI is permanently prohibited at all autonomy levels."
    )

class CounterfactualPath(BaseModel):
    path_id: str
    label: str
    strategy: str
    is_counterfactual: bool = True
    action_taken: ActionType
    expected_outcome: str
    financial_outcome_inr: float
    net_value_inr: float
    attribution_category: AttributionCategory
    governor_status: str
    causal_disclaimer: str = (
        "SIMULATED COUNTERFACTUAL: Preserves counterfactual bounds; causality is not asserted without controlled randomized assignment."
    )

class DecisionReplayTrace(BaseModel):
    payment_id: str
    event_id: str
    scenario_narrative: str
    ai_diagnosis: Dict[str, Any]
    candidate_actions: List[str]
    what_if_comparison: List[Dict[str, Any]]
    erv_summary: Dict[str, Any]
    governor_gates: List[Dict[str, Any]]
    chaos_state: Optional[Dict[str, Any]] = None
    operating_mode: GovernorOperatingMode = GovernorOperatingMode.GOVERNED
    final_decision: Dict[str, Any]
    execution: Dict[str, Any]
    verification: Dict[str, Any]
    attribution: Dict[str, Any]
    learning_update: Dict[str, Any]
    actual_path: CounterfactualPath
    counterfactual_paths: List[CounterfactualPath]

class EmergencyStopStatus(BaseModel):
    is_active: bool
    activated_at: Optional[str] = None
    actions_blocked: int = 0
    potential_exposure_prevented: float = 0.0
    last_audit_id: Optional[str] = None
