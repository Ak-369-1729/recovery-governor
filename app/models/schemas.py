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
