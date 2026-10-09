from datetime import date

import pytest

from app.backtest.metrics import CurveStats, Drawdown
from app.research.config import Criteria
from app.research.evaluation import EvaluationResult, SubperiodResult, judge
from app.research.fingerprint import data_hash, holdout_unlocks, registered_config_hash
from app.research.report import to_markdown
from tests.factories import make_bar, series

C = Criteria()
ROBUST = {"3-month": 0.2, "6-month": 0.3}
GOOD_SUBPERIODS = [0.5, 0.1, -0.2]


def stats(sharpe, drawdown=-0.10):
    return CurveStats(0.1, 0.05, 0.1, sharpe, None, Drawdown(drawdown, None, None, None, 0), None)


def test_passes_on_higher_sharpe_when_robust():
    _, passed = judge(C, stats(0.6), stats(0.4, -0.5), 0.5, ROBUST, GOOD_SUBPERIODS, 0.10)
    assert passed


def test_fails_when_one_trade_carries_the_profit():
    _, passed = judge(C, stats(0.6), stats(0.4, -0.5), 0.5, ROBUST, GOOD_SUBPERIODS, 0.40)
    assert not passed


def test_fails_when_a_robustness_variant_is_negative():
    _, passed = judge(C, stats(0.6), stats(0.4, -0.5), 0.5, {"3-month": -0.1, "6-month": 0.3}, GOOD_SUBPERIODS, 0.10)
    assert not passed


def test_passes_on_similar_sharpe_with_much_smaller_drawdown():
    results, passed = judge(C, stats(0.35, -0.20), stats(0.40, -0.50), 0.5, ROBUST, GOOD_SUBPERIODS, 0.10)
    assert [r.passed for r in results if r.group == "return"] == [False, True, False]
    assert passed


def test_passes_on_low_correlation_with_decent_sharpe():
    results, passed = judge(C, stats(0.55, -0.40), stats(0.90, -0.50), 0.2, ROBUST, GOOD_SUBPERIODS, 0.10)
    assert [r.passed for r in results if r.group == "return"] == [False, False, True]
    assert passed


def test_needs_enough_positive_subperiods():
    _, passed = judge(C, stats(0.6), stats(0.4, -0.5), 0.5, ROBUST, [0.5, -0.1, -0.2], 0.10)
    assert not passed


def test_missing_sharpe_never_passes():
    _, passed = judge(C, stats(None), stats(0.4, -0.5), 0.1, ROBUST, GOOD_SUBPERIODS, 0.10)
    assert not passed


def test_data_hash_changes_when_any_price_changes():
    original = {"TEST": series([10, 11, 12])}
    same = {"TEST": series([10, 11, 12])}
    corrected = {"TEST": series([10, 11, 12])[:2] + [make_bar(12.5, day=2)]}
    assert data_hash(original) == data_hash(same)
    assert data_hash(original) != data_hash(corrected)


def test_registered_hash_is_read_from_the_right_hypothesis(tmp_path):
    doc = tmp_path / "hypotheses.md"
    doc.write_text(
        "### H1: First\n- **Config hash at pre-registration:** `aaaaaaaaaaaa` (x)\n\n"
        "### H2: Second\n- **Config hash at pre-registration:** `bbbbbbbbbbbb` (x)\n",
        encoding="utf-8",
    )
    assert registered_config_hash("H1", doc) == "aaaaaaaaaaaa"
    assert registered_config_hash("H2", doc) == "bbbbbbbbbbbb"
    assert registered_config_hash("H3", doc) is None


def test_holdout_unlocks_are_counted_from_the_log(tmp_path):
    log = tmp_path / "holdout-log.md"
    assert holdout_unlocks(log) == 0
    log.write_text("- 2026-10-09 | holdout | final test of H1\n", encoding="utf-8")
    assert holdout_unlocks(log) == 1


def test_report_shows_the_mechanical_decision():
    criteria, passed = judge(C, stats(0.2), stats(0.4, -0.5), 0.5, ROBUST, GOOD_SUBPERIODS, 0.10)
    result = EvaluationResult(
        hypothesis_id="H1", title="t", phase="development", generated_at="now", commit="abc",
        data_hash="d", config_hash="c", registered_config_hash="c", holdout_unlocks=0,
        run_ids={"12-month": "r1"}, period_start=date(2008, 1, 1), period_end=date(2023, 1, 1),
        universe=("SPY",), benchmark_name="SPY", cash_rate=0.02, strategy=stats(0.2),
        benchmark=stats(0.4, -0.5), correlation=0.5, average_exposure=0.4, closed_trades=10,
        robustness=ROBUST, subperiods=[SubperiodResult("2008-2012", 0.5, -0.3)],
        best_trade_share=0.10, top5_trade_share=0.30, criteria=criteria, passed=passed,
    )
    markdown = to_markdown(result)
    assert "- **Decision:** FAIL" in markdown
    assert "| 2008-2012 | 0.50 | -0.30 |" in markdown
