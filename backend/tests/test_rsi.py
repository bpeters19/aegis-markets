import pytest

from app.indicators.rsi import wilder_rsi


def test_two_step_hand_calculation():
    # changes +1, -0.5: avg gain 0.5, avg loss 0.25 -> RS 2 -> RSI 66.67
    assert wilder_rsi([10, 11, 10.5], 2) == pytest.approx(66.6667, rel=1e-4)
    # next change -0.5: gain (0.5*1 + 0)/2 = 0.25, loss (0.25*1 + 0.5)/2 = 0.375 -> RS 0.667 -> RSI 40
    assert wilder_rsi([10, 11, 10.5, 10], 2) == pytest.approx(40.0)


def test_only_gains_is_100():
    assert wilder_rsi([1, 2, 3, 4], 2) == 100.0


def test_flat_prices_are_neutral():
    assert wilder_rsi([5, 5, 5, 5], 2) == 50.0


def test_not_enough_data():
    assert wilder_rsi([10, 11], 2) is None
