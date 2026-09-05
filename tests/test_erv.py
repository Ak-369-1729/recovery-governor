import pytest
from app.models.enums import ActionType, FailureType, Channel, RiskTier
from app.engine.erv import ERVEngine

def test_erv_calculation_formula():
    amount = 4999.0
    calc = ERVEngine.calculate(
        action=ActionType.RETRY_30_MIN,
        payment_amount=amount,
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE,
        channel=Channel.MOBILE_APP,
        retry_count=0,
        risk_tier=RiskTier.LOW,
        hurdle=10.0,
        custom_base_probability=0.64
    )

    # Gross = 0.64 * 4999 = 3199.36
    assert calc.gross_expected_recovery == 3199.36
    # RETRY_30_MIN: int_cost = 5.0, risk_cost = 4.0, friction_cost = 0.0 -> Total = 9.0
    assert calc.intervention_cost == 5.0
    assert calc.risk_cost == 4.0
    assert calc.friction_cost == 0.0
    # Net ERV = 3199.36 - 9.0 = 3190.36
    assert calc.net_erv == 3190.36
    assert calc.is_economically_viable is True
    assert "Net ERV = (" in calc.formula_breakdown

def test_erv_negative_for_micro_amount():
    calc = ERVEngine.calculate(
        action=ActionType.SEND_PAYMENT_LINK,
        payment_amount=20.0,
        failure_type=FailureType.INSUFFICIENT_FUNDS,
        retry_count=0,
        hurdle=10.0
    )

    # Send payment link: int_cost 3.0, risk_cost 2.0, friction_cost 25.0 -> Total costs = 30.0
    # On 20.0 amount, even 100% recovery would be 20.0 - 30.0 = -10.0
    assert calc.net_erv < 0
    assert calc.is_economically_viable is False

def test_erv_retry_diminishing_returns():
    amt = 1000.0
    calc_0 = ERVEngine.calculate(
        action=ActionType.RETRY_NOW,
        payment_amount=amt,
        failure_type=FailureType.NETWORK_TIMEOUT,
        retry_count=0,
        custom_base_probability=0.60
    )
    calc_1 = ERVEngine.calculate(
        action=ActionType.RETRY_NOW,
        payment_amount=amt,
        failure_type=FailureType.NETWORK_TIMEOUT,
        retry_count=1,
        custom_base_probability=0.60
    )
    calc_2 = ERVEngine.calculate(
        action=ActionType.RETRY_NOW,
        payment_amount=amt,
        failure_type=FailureType.NETWORK_TIMEOUT,
        retry_count=2,
        custom_base_probability=0.60
    )

    assert calc_0.recovery_probability > calc_1.recovery_probability > calc_2.recovery_probability
    assert calc_0.net_erv > calc_1.net_erv > calc_2.net_erv

def test_erv_hard_decline_zero_recovery():
    calc = ERVEngine.calculate(
        action=ActionType.RETRY_NOW,
        payment_amount=5000.0,
        failure_type=FailureType.CARD_LOST_STOLEN,
        retry_count=0
    )
    assert calc.recovery_probability == 0.0
    assert calc.gross_expected_recovery == 0.0
    assert calc.net_erv < 0
    assert calc.is_economically_viable is False

def test_erv_no_action_always_zero_cost():
    calc = ERVEngine.calculate(
        action=ActionType.NO_ACTION,
        payment_amount=1000.0,
        failure_type=FailureType.TEMPORARY_ISSUER_FAILURE
    )
    assert calc.intervention_cost == 0.0
    assert calc.risk_cost == 0.0
    assert calc.friction_cost == 0.0
    assert calc.net_erv == 0.0
