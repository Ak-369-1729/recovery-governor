import pytest
from app.models.enums import (
    FailureType,
    ActionType,
    PaymentMethod,
    Channel,
    RiskTier,
    GovernorOperatingMode,
    AutonomyLevel,
    StrategyType,
    ChaosType,
    ExecutionStatus,
    DecisionOutcome,
    AttributionCategory,
)
from app.models.schemas import (
    SandboxScenarioRequest,
    StrategyArenaRequest,
)
from app.engine.sandbox import (
    WhatIfEngine,
    RecoveryAIReadinessEngine,
    AutonomyGateEngine,
    PortfolioSimulationEngine,
    CounterfactualReplayEngine,
    SandboxPipelineRunner,
)
from app.engine.governor import RecoveryGovernor, EmergencyKillSwitchManager

# =============================================================================
# PATCH 1: DYNAMIC ACTION CATALOG WHAT-IF TESTS
# =============================================================================

def test_dynamic_action_catalog_what_if():
    """
    Verifies Patch 1: What-If evaluates every candidate action dynamically
    without hardcoding any count or static action list.
    """
    payment = {
        "payment_id": "pay_test_whatif_001",
        "amount": 4999.0,
        "currency": "INR",
        "payment_method": "UPI",
        "failure_type": FailureType.TEMPORARY_ISSUER_FAILURE.value,
        "channel": "MOBILE_APP",
        "risk_tier": "LOW",
        "retry_count": 0,
    }

    resp = WhatIfEngine.evaluate_all_actions(payment, hurdle=10.0)

    # Expected count is dynamic: all ActionType except STOP
    expected_count = len([a for a in ActionType if a != ActionType.STOP])
    assert resp.total_candidate_actions_evaluated == expected_count
    assert len(resp.evaluations) == expected_count

    # Verify every evaluated action is an ActionType
    evaluated_actions = {e.action for e in resp.evaluations}
    assert ActionType.RETRY_NOW in evaluated_actions
    assert ActionType.RETRY_30_MIN in evaluated_actions
    assert ActionType.RETRY_2_HOURS in evaluated_actions
    assert ActionType.NO_ACTION in evaluated_actions

    # Verify Governor selected action is marked and viable
    selected = [e for e in resp.evaluations if e.is_governor_choice]
    assert len(selected) == 1
    assert selected[0].action == resp.governor_selected_action
    assert selected[0].governor_eligible is True
    assert selected[0].net_erv > 0


# =============================================================================
# PATCH 2: RECOVERY AI READINESS SCORE TESTS
# =============================================================================

def test_recovery_ai_readiness_score_calculation():
    """
    Verifies Patch 2: Deterministic 0-100 score measuring recovery reliability
    across 5 distinct dimensions.
    """
    # Ideal run: 100% safety, 71% lift, 100% fallback, 88% calibration, 94% attribution
    scorecard = RecoveryAIReadinessEngine.calculate_readiness(
        safety_rate=1.0,
        critical_violations=0,
        empirical_lift_vs_baseline=0.71,
        fallback_success_rate=1.0,
        brier_calibration=0.88,
        attribution_verification_rate=0.94,
    )

    assert 0.0 <= scorecard.total_score <= 100.0
    assert scorecard.safety_score == 30.0
    assert scorecard.economic_efficiency_score > 20.0
    assert scorecard.fallback_reliability_score == 15.0
    assert scorecard.accuracy_calibration_score > 12.0
    assert scorecard.verification_attribution_score > 13.0
    assert scorecard.total_score >= 90.0

    # Penalized run: critical violation deducts 15 pts
    penalized = RecoveryAIReadinessEngine.calculate_readiness(
        safety_rate=0.95,
        critical_violations=1,
    )
    assert penalized.safety_score <= 15.0
    assert penalized.total_score < scorecard.total_score


# =============================================================================
# PATCH 3: CONSTRAINED AUTONOMY TESTS
# =============================================================================

def test_constrained_autonomy_invariant():
    """
    Verifies Patch 3: Level 4 is explicitly CONSTRAINED AUTONOMOUS.
    Governor remains the single authority and AI cannot directly execute.
    """
    status = AutonomyGateEngine.get_status()

    assert AutonomyLevel.LEVEL_4_CONSTRAINED_AUTONOMOUS.value == "LEVEL_4_CONSTRAINED_AUTONOMOUS"
    assert "CONSTRAINED AUTONOMOUS" in status.architectural_invariant
    assert "Direct financial execution by AI is permanently prohibited" in status.architectural_invariant

    # Verify criteria exists and is deterministic
    assert "safety_rate" in status.eligibility_criteria
    assert "decision_accuracy" in status.eligibility_criteria
    assert "critical_violations" in status.eligibility_criteria
    assert status.critical_violations_count == 0


# =============================================================================
# PATCH 4: PORTFOLIO SIMULATION TESTS
# =============================================================================

def test_portfolio_simulation_reproducibility():
    """
    Verifies Patch 4: Mode B portfolio simulation on scalable synthetic populations
    produces identical deterministic results with the same seed.
    """
    sim1 = PortfolioSimulationEngine.run_simulation(population_size=100, seed=42)
    sim2 = PortfolioSimulationEngine.run_simulation(population_size=100, seed=42)

    # Identical seed -> identical output
    for strat in [StrategyType.CONTROL.value, StrategyType.NAIVE_BASELINE.value, StrategyType.GOVERNOR.value]:
        assert sim1.results[strat].recovered_value == sim2.results[strat].recovered_value
        assert sim1.results[strat].net_recovery == sim2.results[strat].net_recovery
        assert sim1.results[strat].recovery_rate == sim2.results[strat].recovery_rate

    # Governor should have superior net recovery and prevent unsafe actions
    gov = sim1.results[StrategyType.GOVERNOR.value]
    base = sim1.results[StrategyType.NAIVE_BASELINE.value]
    assert gov.net_recovery > base.net_recovery
    assert gov.unsafe_actions_prevented > 0


# =============================================================================
# PATCH 5: COUNTERFACTUAL REPLAY TESTS
# =============================================================================

def test_counterfactual_replay_generation():
    """
    Verifies Patch 5: Decision Replay generates both the actual path
    and simulated counterfactual trajectories (Control, Baseline, Alternative).
    """
    req = SandboxScenarioRequest(
        amount=4999.0,
        payment_method=PaymentMethod.UPI,
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE,
    )
    run_res = SandboxPipelineRunner.run_scenario(req)

    trace = run_res["counterfactual_replay"]
    assert trace["actual_path"]["is_counterfactual"] is False
    assert trace["actual_path"]["strategy"] == "GOVERNOR"

    # Verify counterfactual paths exist and are clearly disclaimed
    cfs = trace["counterfactual_paths"]
    assert len(cfs) == 3
    strategies = {c["strategy"] for c in cfs}
    assert "CONTROL" in strategies
    assert "NAIVE_BASELINE" in strategies
    assert "ALTERNATIVE_POLICY" in strategies

    for c in cfs:
        assert c["is_counterfactual"] is True
        assert "SIMULATED COUNTERFACTUAL" in c["causal_disclaimer"]


# =============================================================================
# SANDBOX PRESETS & SAFETY TESTS
# =============================================================================

def test_preset_b_permanent_decline_strictly_blocked():
    """
    Preset B: Mandate revoked must be strictly stopped by Gate 1 Hard Decline Ban.
    """
    req = SandboxScenarioRequest(
        amount=12500.0,
        payment_method=PaymentMethod.MANDATE,
        failure_type=FailureType.MANDATE_REVOKED,
    )
    res = SandboxPipelineRunner.run_scenario(req)

    gov_dec = res["governor_decision"]
    assert gov_dec["decision"] == DecisionOutcome.STOP.value
    assert gov_dec["selected_action"] == ActionType.STOP.value
    # Retries must be in blocked actions
    assert ActionType.RETRY_NOW.value in gov_dec["blocked_actions"]


def test_preset_c_negative_economics_halts_action():
    """
    Preset C: Low-ticket payment with negative Net ERV halts with NO_ACTION.
    """
    req = SandboxScenarioRequest(
        amount=49.0,
        payment_method=PaymentMethod.UPI,
        failure_type=FailureType.INSUFFICIENT_FUNDS,
    )
    res = SandboxPipelineRunner.run_scenario(req)

    gov_dec = res["governor_decision"]
    assert gov_dec["decision"] == DecisionOutcome.NO_ACTION.value
    assert gov_dec["selected_action"] == ActionType.NO_ACTION.value


def test_shadow_mode_withholds_execution():
    """
    Shadow Mode: Decision evaluated and approved by Governor,
    but actual execution is SUPPRESSED / withheld.
    """
    req = SandboxScenarioRequest(
        amount=4999.0,
        payment_method=PaymentMethod.UPI,
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE,
        operating_mode=GovernorOperatingMode.SHADOW,
    )
    res = SandboxPipelineRunner.run_scenario(req)

    gov_dec = res["governor_decision"]
    assert gov_dec["decision_outcome"] == "SHADOW_APPROVED"
    assert "SHADOW MODE" in gov_dec["reason"]

    exec_res = res["execution"]
    assert exec_res["adapter_type"] == "SHADOW_MODE"
    assert exec_res["status"] == ExecutionStatus.SUPPRESSED.value
    assert "BLOCKED — SHADOW MODE" in exec_res["response_payload"]["message"]


def test_emergency_kill_switch_intercepts_all():
    """
    Emergency Stop: When engaged, pre-gate 0 immediately halts all interventions.
    """
    EmergencyKillSwitchManager.reset()
    EmergencyKillSwitchManager.activate()

    assert EmergencyKillSwitchManager.is_active() is True

    req = SandboxScenarioRequest(
        amount=5000.0,
        payment_method=PaymentMethod.UPI,
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE,
    )
    res = SandboxPipelineRunner.run_scenario(req)

    gov_dec = res["governor_decision"]
    assert gov_dec["decision"] == DecisionOutcome.STOP.value
    assert gov_dec["decision_outcome"] == "EMERGENCY_STOP_BLOCKED"
    assert "Emergency Kill Switch" in gov_dec["reason"]

    # Verify exposure tracked
    status = EmergencyKillSwitchManager.get_status()
    assert status["actions_blocked"] >= 1
    assert status["potential_exposure_prevented"] >= 5000.0

    # Reset
    EmergencyKillSwitchManager.reset()
    assert EmergencyKillSwitchManager.is_active() is False


def test_chaos_injection_gemini_outage_fallback():
    """
    Chaos: Simulated Gemini outage triggers deterministic fallback with zero financial loss.
    """
    req = SandboxScenarioRequest(
        amount=4999.0,
        payment_method=PaymentMethod.UPI,
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE,
        chaos_injection=ChaosType.GEMINI_OUTAGE,
    )
    res = SandboxPipelineRunner.run_scenario(req)

    assert res["chaos_state"]["injected"] is True
    assert res["chaos_state"]["fallback_triggered"] is True
    assert res["chaos_state"]["financial_exposure"] == 0.0
    assert res["governor_decision"]["decision"] == DecisionOutcome.EXECUTE.value
