import pytest
from app.engine.benchmark import BenchmarkEngine
from app.engine.chaos import ChaosLabEngine
from app.engine.synthetic_data import ensure_synthetic_data_seeded
from app.models.database import init_db

@pytest.fixture(autouse=True)
def setup():
    init_db()

def test_three_way_benchmark_execution():
    # Test with sample size 200 for fast automated testing
    results = BenchmarkEngine.run_benchmark(sample_size=200)

    assert "CONTROL" in results
    assert "BASELINE" in results
    assert "GOVERNOR" in results

    ctrl = results["CONTROL"]
    base = results["BASELINE"]
    gov = results["GOVERNOR"]

    # Invariants
    assert ctrl.sample_size == 200
    assert base.sample_size == 200
    assert gov.sample_size == 200

    # Governor should block all unsafe actions (hard declines)
    assert gov.unsafe_actions_blocked > 0
    assert base.unsafe_actions_blocked == 0

    # Governor net recovery value should exceed baseline net recovery
    assert gov.net_recovery_value > base.net_recovery_value

def test_all_5_chaos_scenarios():
    scenarios = [
        "prohibited_retry",
        "webhook_replay_storm",
        "gemini_outage",
        "negative_erv",
        "retry_cap"
    ]

    for sc in scenarios:
        res = ChaosLabEngine.run_scenario(sc)
        assert res["invariant_passed"] is True, f"Chaos scenario {sc} failed invariant check"
        assert "audit_log_id" in res
