import pytest
from app.engine.bayesian import BayesianRecoveryModel
from app.models.enums import FailureType, ActionType, Channel
from app.models.database import init_db, get_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    BayesianRecoveryModel._POSTERIOR_CACHE.clear()
    with get_db() as conn:
        conn.execute("DELETE FROM bayesian_priors")

def test_bayesian_prior_initialization():
    post = BayesianRecoveryModel.get_posterior(
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE.value,
        action=ActionType.RETRY_30_MIN.value,
        channel=Channel.MOBILE_APP.value
    )
    # Prior is 14 / (14 + 6) = 0.70
    assert post["prior_alpha"] == 14.0
    assert post["prior_beta"] == 6.0
    assert post["posterior_mean"] == 0.70
    assert post["credible_interval_95"][0] < 0.70 < post["credible_interval_95"][1]

def test_bayesian_conjugate_update_success_and_failure():
    import uuid
    rand_suffix = uuid.uuid4().hex[:6]
    ft = f"TEST_FAILURE_{rand_suffix}"
    act = f"TEST_ACTION_{rand_suffix}"
    chan = "TEST_CHANNEL"

    # Initial state
    init_p = BayesianRecoveryModel.get_posterior(ft, act, chan)
    initial_mean = init_p["posterior_mean"]

    # Record 10 consecutive successes
    for _ in range(10):
        BayesianRecoveryModel.update_outcome(ft, act, chan, succeeded=True)

    post_success = BayesianRecoveryModel.get_posterior(ft, act, chan)
    assert post_success["successes"] == 10
    assert post_success["posterior_mean"] > initial_mean

    # Record 10 consecutive failures
    for _ in range(10):
        BayesianRecoveryModel.update_outcome(ft, act, chan, succeeded=False)

    post_both = BayesianRecoveryModel.get_posterior(ft, act, chan)
    assert post_both["successes"] == 10
    assert post_both["failures"] == 10
    # Uncertainty (variance) should decrease with 20 data points compared to uninformative prior
    assert post_both["posterior_variance"] < init_p["posterior_variance"]
