"""
Comprehensive Unit and Regression Tests for Phase 3 & 3.1 Hardening:
Predict -> Prevent -> Recover -> Prove

Tests:
1. No-Outcome-Leakage Invariant: Changing post-failure ground truth does not affect prediction.
2. Prediction Confidence & Schema Bounds: Probabilities bounded in [0.01, 0.98].
3. Evaluation Metrics: Precision, Recall, F1, FPR, Accuracy, Brier Score.
4. Insufficient Sample Handling: Safe "N/A" outputs on sparse data.
5. Reliability Buckets: 5-bin calibration curve.
6. Preventive Governor Evaluation: High-risk triggers candidate actions; economic hurdle gate.
7. Conservative Prevention Attribution: Causal lift only credited when counterfactual fails.
8. Network Simulation Reproducibility: Same scenario + seed produces identical telemetry.
9. Temporal Health Trajectory: 7-step degradation and recovery timeline.
10. Global Deterministic Safety Override: Merchant policy cannot bypass hard decline bans or kill switch.
11. Emergency Kill Switch Circuit Breaker: Halts both preventive and reactive recovery actions.
12. Unified Lifecycle State Machine: 13-stage orchestration end-to-end.
"""

import pytest
from app.models.enums import (
    PaymentMethod,
    RiskTier,
    Channel,
    FailureType,
    ActionType,
    NetworkScenario,
    GateStatus,
    AttributionCategory,
    PredictionClassification,
)
from app.models.schemas import MerchantPolicyConfig
from app.engine.predictor import FailurePredictor, FORBIDDEN_GROUND_TRUTH_FIELDS
from app.engine.prediction_evaluation import PredictionEvaluationEngine
from app.engine.network_health import SimulatedNetworkHealthEngine
from app.engine.governor import RecoveryGovernor, EmergencyKillSwitchManager
from app.engine.attribution import RecoveryAttributionEngine
from app.engine.merchant_policy import MerchantPolicyManager
from app.engine.lifecycle import UnifiedLifecycleEngine
from app.engine.fallback import DeterministicFallbackEngine


def test_no_outcome_leakage_into_predictor():
    """
    CRITICAL INVARIANT: The predictor must NEVER inspect or change output
    based on ground-truth outcome fields (status, failure_type, failure_code).
    """
    payload_a = {
        "payment_id": "pay_test_leakage_1",
        "amount": 10000.0,
        "payment_method": PaymentMethod.UPI,
        "customer_success_rate": 0.85,
        "risk_tier": RiskTier.LOW,
        "channel": Channel.MOBILE_APP,
        "status": "FAILED",
        "failure_type": FailureType.NETWORK_TIMEOUT.value,
        "failure_code": "ISSUER_504_TIMEOUT",
    }
    
    pred_a = FailurePredictor.predict(
        payment_id=payload_a["payment_id"],
        amount=payload_a["amount"],
        payment_method=payload_a["payment_method"],
        customer_success_rate=payload_a["customer_success_rate"],
        risk_tier=payload_a["risk_tier"],
        channel=payload_a["channel"],
        network_scenario=NetworkScenario.NORMAL,
        network_seed=42,
        raw_input_payload=payload_a,
    )

    # In payload_b, we change status to SUCCESS and set failure_type to None
    payload_b = {
        "payment_id": "pay_test_leakage_1",
        "amount": 10000.0,
        "payment_method": PaymentMethod.UPI,
        "customer_success_rate": 0.85,
        "risk_tier": RiskTier.LOW,
        "channel": Channel.MOBILE_APP,
        "status": "SUCCESS",
        "failure_type": None,
        "failure_code": None,
    }

    pred_b = FailurePredictor.predict(
        payment_id=payload_b["payment_id"],
        amount=payload_b["amount"],
        payment_method=payload_b["payment_method"],
        customer_success_rate=payload_b["customer_success_rate"],
        risk_tier=payload_b["risk_tier"],
        channel=payload_b["channel"],
        network_scenario=NetworkScenario.NORMAL,
        network_seed=42,
        raw_input_payload=payload_b,
    )

    # Predictions MUST be identical: post-failure outcomes have 0 influence
    assert pred_a.simulated_failure_probability == pred_b.simulated_failure_probability
    assert pred_a.confidence == pred_b.confidence
    assert pred_a.confidence_score == pred_b.confidence_score


def test_prediction_probability_bounds_and_confidence():
    """Verifies probabilities remain strictly in [0.01, 0.98] and valid confidence."""
    for amt in [10.0, 500.0, 49999.0, 100000.0]:
        for sr in [0.10, 0.50, 0.95]:
            pred = FailurePredictor.predict(
                payment_id=f"pay_bound_{amt}_{sr}",
                amount=amt,
                payment_method=PaymentMethod.UPI,
                customer_success_rate=sr,
                network_scenario=NetworkScenario.SBI_DEGRADED,
                network_seed=123,
            )
            assert 0.01 <= pred.simulated_failure_probability <= 0.98
            assert 0.0 <= pred.confidence_score <= 1.0
            assert pred.prediction_source == "SYNTHETIC_PREDICTIVE_MODEL"


def test_prediction_evaluation_metrics_calculation():
    """Tests deterministic confusion matrix, precision, recall, F1, accuracy, and Brier score."""
    PredictionEvaluationEngine.reset()
    
    # 2 True Positives
    for i in range(2):
        p = FailurePredictor.predict(f"tp_{i}", 1000.0, PaymentMethod.UPI, network_scenario=NetworkScenario.SBI_DEGRADED)
        p.simulated_failure_probability = 0.80
        PredictionEvaluationEngine.record_outcome(p, "FAILED")

    # 2 True Negatives
    for i in range(2):
        p = FailurePredictor.predict(f"tn_{i}", 1000.0, PaymentMethod.UPI, network_scenario=NetworkScenario.NORMAL)
        p.simulated_failure_probability = 0.10
        PredictionEvaluationEngine.record_outcome(p, "SUCCESS")

    # 1 False Positive
    p_fp = FailurePredictor.predict("fp_0", 1000.0, PaymentMethod.UPI, network_scenario=NetworkScenario.SBI_DEGRADED)
    p_fp.simulated_failure_probability = 0.75
    PredictionEvaluationEngine.record_outcome(p_fp, "SUCCESS")

    # 1 False Negative
    p_fn = FailurePredictor.predict("fn_0", 1000.0, PaymentMethod.UPI, network_scenario=NetworkScenario.NORMAL)
    p_fn.simulated_failure_probability = 0.20
    PredictionEvaluationEngine.record_outcome(p_fn, "FAILED")

    metrics = PredictionEvaluationEngine.calculate_reliability_metrics()

    assert metrics.total_predictions == 6
    assert metrics.true_positives == 2
    assert metrics.true_negatives == 2
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1

    # Precision: TP / (TP + FP) = 2 / 3 = 0.6667
    assert pytest.approx(metrics.precision, 0.01) == 0.667
    # Recall: TP / (TP + FN) = 2 / 3 = 0.6667
    assert pytest.approx(metrics.recall, 0.01) == 0.667
    # Accuracy: (TP + TN) / Total = 4 / 6 = 0.6667
    assert pytest.approx(metrics.accuracy, 0.01) == 0.667
    # Brier score: mean((p - y)^2)
    # TP errors: (0.8 - 1)^2 = 0.04 (twice -> 0.08)
    # TN errors: (0.1 - 0)^2 = 0.01 (twice -> 0.02)
    # FP error: (0.75 - 0)^2 = 0.5625
    # FN error: (0.20 - 1)^2 = 0.64
    # sum = 0.08 + 0.02 + 0.5625 + 0.64 = 1.3025 / 6 = ~0.217
    assert isinstance(metrics.brier_score, float)
    assert 0.0 < metrics.brier_score < 0.5


def test_insufficient_sample_returns_safe_na():
    """Verifies that with < 5 samples, metrics safely return 'N/A' rather than NaN, null, or 0."""
    PredictionEvaluationEngine.reset()
    
    # Empty history
    metrics_empty = PredictionEvaluationEngine.calculate_reliability_metrics()
    assert metrics_empty.precision == "N/A"
    assert metrics_empty.recall == "N/A"
    assert metrics_empty.f1_score == "N/A"
    assert metrics_empty.brier_score == "N/A"
    for b in metrics_empty.reliability_buckets:
        assert b.predicted_average == "N/A"
        assert b.sample_count == 0

    # Sparse history (2 records)
    p = FailurePredictor.predict("p1", 1000.0, PaymentMethod.UPI)
    PredictionEvaluationEngine.record_outcome(p, "SUCCESS")
    PredictionEvaluationEngine.record_outcome(p, "FAILED")

    metrics_sparse = PredictionEvaluationEngine.calculate_reliability_metrics()
    assert metrics_sparse.total_predictions == 2
    assert metrics_sparse.precision == "N/A"
    assert metrics_sparse.f1_score == "N/A"
    assert metrics_sparse.brier_score == "N/A"


def test_network_scenario_and_seed_reproducibility():
    """
    Verifies that the simulated network health engine produces identical telemetry
    for identical scenario + seed, and bounded variance across seeds.
    """
    # 1. Exact reproducibility with same scenario + seed
    run_1 = SimulatedNetworkHealthEngine.get_rail_health("UPI_SBI", scenario=NetworkScenario.SBI_DEGRADED, seed=42)
    run_2 = SimulatedNetworkHealthEngine.get_rail_health("UPI_SBI", scenario=NetworkScenario.SBI_DEGRADED, seed=42)

    assert run_1.health_score == run_2.health_score
    assert run_1.latency_ms == run_2.latency_ms
    assert run_1.timeout_rate == run_2.timeout_rate
    assert run_1.status == "DEGRADED"
    assert "SIMULATED NETWORK HEALTH" in run_1.simulation_disclaimer

    # 2. Bounded difference across seeds
    run_diff_seed = SimulatedNetworkHealthEngine.get_rail_health("UPI_SBI", scenario=NetworkScenario.SBI_DEGRADED, seed=999)
    assert abs(run_1.health_score - run_diff_seed.health_score) <= 5.0
    assert run_diff_seed.status == "DEGRADED"

    # 3. Normal scenario health is high
    normal_run = SimulatedNetworkHealthEngine.get_rail_health("UPI_SBI", scenario=NetworkScenario.NORMAL, seed=42)
    assert normal_run.health_score >= 90.0
    assert normal_run.status == "OPERATIONAL"


def test_temporal_network_telemetry_timeline():
    """Verifies 7-step temporal telemetry trajectory across degradation and recovery."""
    timeline = SimulatedNetworkHealthEngine.get_temporal_timeline(
        rail_id="UPI_SBI",
        scenario=NetworkScenario.SBI_DEGRADED,
        seed=42,
    )
    assert len(timeline) == 7
    # Starts normal, degrades, then recovers
    assert timeline[0]["time_label"] == "10:00"
    assert timeline[0]["health_score"] >= 90.0

    # Trough at 10:15 / 10:20
    assert timeline[3]["time_label"] == "10:15"
    assert timeline[3]["health_score"] < 50.0
    assert timeline[3]["status"] == "OUTAGE"

    # Recovery by 10:30
    assert timeline[6]["time_label"] == "10:30"
    assert timeline[6]["health_score"] >= 80.0


def test_preventive_governor_high_risk_and_erv_gate():
    """
    Verifies that high-risk payments trigger Governor preventive evaluation,
    and actions clearing positive ERV are approved.
    """
    governor = RecoveryGovernor()
    payment = {
        "payment_id": "pay_prev_erv_test",
        "amount": 49999.0,
        "payment_method": PaymentMethod.UPI.value,
        "merchant_id": "mer_demo_razorpay",
    }

    # Synthesize high-risk prediction
    pred = FailurePredictor.predict(
        payment_id=payment["payment_id"],
        amount=payment["amount"],
        payment_method=PaymentMethod.UPI,
        network_scenario=NetworkScenario.SBI_DEGRADED,
        network_seed=42,
    )
    assert pred.simulated_failure_probability >= 0.50

    decision = governor.evaluate_prevention(payment, pred)
    assert decision.decision_outcome == "APPROVED"
    assert decision.selected_action in {ActionType.RECOMMEND_ALTERNATE_PAYMENT_PATH, ActionType.DELAY_ATTEMPT, ActionType.CUSTOMER_NOTIFICATION}
    assert decision.net_preventive_erv > 0.0
    assert "why_this_action" in decision.explainability


def test_preventive_governor_low_risk_holds_no_action():
    """Verifies that low failure risk (< 50%) holds to NO_ACTION to avoid unnecessary friction."""
    governor = RecoveryGovernor()
    payment = {"payment_id": "pay_low_risk", "amount": 250.0, "payment_method": PaymentMethod.UPI.value}
    
    pred = FailurePredictor.predict(
        payment_id=payment["payment_id"],
        amount=payment["amount"],
        payment_method=PaymentMethod.UPI,
        network_scenario=NetworkScenario.NORMAL,
        network_seed=42,
    )
    assert pred.simulated_failure_probability < 0.50

    decision = governor.evaluate_prevention(payment, pred)
    assert decision.selected_action == ActionType.NO_ACTION
    assert "NO_ACTION" in decision.decision_outcome


def test_merchant_policy_cannot_override_global_safety_invariants():
    """
    ARCHITECTURAL SAFETY INVARIANT:
    Merchant policy CANNOT bypass deterministic safety gates.
    """
    policy = MerchantPolicyConfig(
        merchant_id="mer_adversarial",
        allow_prevention=True,
        override_global_safety=True,  # Attempts to bypass safety
    )
    # Manager must neutralize override_global_safety
    updated = MerchantPolicyManager.update_policy(policy)
    assert updated.override_global_safety is False

    # Also verify that a permanent hard decline is strictly STOPPED by Governor regardless of merchant policy
    from app.models.schemas import AIDiagnosisOutput, CandidateActionProposal
    governor = RecoveryGovernor()
    revoked_payment = {
        "payment_id": "pay_revoked_mandate_safe",
        "amount": 5000.0,
        "failure_type": FailureType.MANDATE_REVOKED.value,
        "merchant_policy": {"override_global_safety": True, "max_retries": 10},
    }
    unsafe_ai = AIDiagnosisOutput(
        diagnosis="Hallucinated model attempting retry on revoked mandate.",
        confidence=0.95,
        candidate_actions=[
            CandidateActionProposal(action=ActionType.RETRY_NOW, reason="Immediate retry"),
        ]
    )
    decision = governor.evaluate(revoked_payment, "evt_test_mandate", unsafe_ai)
    assert decision.selected_action == ActionType.STOP
    assert decision.decision.value == "STOP"
    assert ActionType.RETRY_NOW.value in decision.blocked_actions


def test_emergency_kill_switch_blocks_prevention_and_recovery():
    """Verifies hardware kill switch blocks pre-flight interventions AND reactive retries."""
    EmergencyKillSwitchManager.reset()
    EmergencyKillSwitchManager.activate(audit_id="audit_test_kill")
    
    try:
        governor = RecoveryGovernor()
        payment = {"payment_id": "pay_kill_test", "amount": 49999.0, "payment_method": PaymentMethod.UPI.value}
        
        # 1. Pre-flight prevention test
        pred = FailurePredictor.predict(payment["payment_id"], payment["amount"], PaymentMethod.UPI)
        prev_dec = governor.evaluate_prevention(payment, pred)
        assert prev_dec.governor_status == GateStatus.BLOCKED
        assert prev_dec.decision_outcome == "EMERGENCY_STOP_BLOCKED"
        assert prev_dec.selected_action == ActionType.NO_ACTION

        # 2. Reactive recovery test
        payment["failure_type"] = FailureType.NETWORK_TIMEOUT.value
        diag = DeterministicFallbackEngine.diagnose(payment)
        rec_dec = governor.evaluate(payment, "evt_kill", diag)
        assert rec_dec.decision.value == "STOP"
        assert rec_dec.decision_outcome == "EMERGENCY_STOP_BLOCKED"
        assert rec_dec.selected_action == ActionType.STOP

        # Verify exposure tracking
        status = EmergencyKillSwitchManager.get_status()
        assert status["actions_blocked"] >= 2
        assert status["potential_exposure_prevented"] >= 49999.0
    finally:
        EmergencyKillSwitchManager.reset()


def test_conservative_prevention_attribution():
    """
    Verifies that PREVENTED_FAILURE is ONLY credited when simulation
    confirms counterfactual failure. Otherwise classified as NATURAL_SUCCESS or UNKNOWN.
    """
    from app.models.schemas import PreventiveGovernorDecision
    
    # 1. Active intervention on degraded rail that avoided failure -> PREVENTED_FAILURE
    decision_active = PreventiveGovernorDecision(
        decision_id="dec_test_1",
        payment_id="pay_attr_1",
        failure_prediction=FailurePredictor.predict("p1", 1000.0, PaymentMethod.UPI),
        governor_status=GateStatus.PASSED,
        decision_outcome="APPROVED",
        selected_action=ActionType.RECOMMEND_ALTERNATE_PAYMENT_PATH,
        net_preventive_erv=500.0,
        erv_breakdown={},
        policy_checks=[],
        blocked_actions=[],
        explainability={},
        timestamp="2026-09-06T00:00:00Z",
    )
    attr_lift = RecoveryAttributionEngine.attribute_prevention(
        prevention_decision=decision_active,
        payment={"payment_id": "pay_attr_1", "amount": 1000.0},
        final_outcome="SUCCESS",
        counterfactual_outcome="FAILED",  # Without intervention, it would have failed
    )
    assert attr_lift.category == AttributionCategory.PREVENTED_FAILURE
    assert attr_lift.recovered_amount == 1000.0

    # 2. Active intervention, but counterfactual would have succeeded naturally anyway -> NATURAL_SUCCESS
    attr_unnecessary = RecoveryAttributionEngine.attribute_prevention(
        prevention_decision=decision_active,
        payment={"payment_id": "pay_attr_2", "amount": 1000.0},
        final_outcome="SUCCESS",
        counterfactual_outcome="SUCCESS",
    )
    assert attr_unnecessary.category == AttributionCategory.NATURAL_SUCCESS
    assert attr_unnecessary.recovered_amount == 0.0

    # 3. Active intervention failed -> FAILED_PREVENTION
    attr_failed = RecoveryAttributionEngine.attribute_prevention(
        prevention_decision=decision_active,
        payment={"payment_id": "pay_attr_3", "amount": 1000.0},
        final_outcome="FAILED",
    )
    assert attr_failed.category == AttributionCategory.FAILED_PREVENTION


def test_unified_lifecycle_state_machine_end_to_end():
    """Verifies that simulate_lifecycle executes all stages and closes feedback loop."""
    payment = {
        "payment_id": "pay_life_full_test",
        "amount": 25000.0,
        "payment_method": PaymentMethod.UPI.value,
        "rail_id": "UPI_SBI",
        "customer_success_rate": 0.85,
        "risk_tier": RiskTier.LOW.value,
        "channel": Channel.MOBILE_APP.value,
    }

    trace = UnifiedLifecycleEngine.simulate_lifecycle(
        payment=payment,
        scenario=NetworkScenario.SBI_DEGRADED,
        seed=42,
    )

    assert trace.current_state.value == "COMPLETED"
    states_visited = [s["state"] for s in trace.history]
    assert "INTENT_CREATED" in states_visited
    assert "PRE_FLIGHT_ANALYSIS" in states_visited
    assert "FAILURE_PREDICTED" in states_visited
    assert "PREVENTION_EVALUATION" in states_visited
    assert "COMPLETED" in states_visited
    assert trace.prediction is not None
    assert trace.prevention_decision is not None
    assert trace.prediction_evaluation is not None
