"""Performance metrics. Money is Decimal elsewhere; statistics here are float on purpose."""
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.market_data.domain import Bar
from app.portfolio.engine import ClosedTrade

TRADING_DAYS = 252
Curve = Sequence[tuple[date, Decimal]]


@dataclass(frozen=True)
class Drawdown:
    max_drawdown: float
    peak: date | None
    trough: date | None
    recovered: date | None
    duration_days: int


@dataclass(frozen=True)
class CurveStats:
    total_return: float
    cagr: float | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    drawdown: Drawdown
    calmar: float | None


@dataclass(frozen=True)
class RelativeStats:
    beta: float | None
    correlation: float | None
    alpha: float | None


@dataclass(frozen=True)
class TradeStats:
    count: int
    wins: int
    losses: int
    win_rate: float | None
    avg_win: float | None
    avg_loss: float | None
    payoff_ratio: float | None
    profit_factor: float | None
    expectancy: float | None
    avg_holding_days: float | None
    best_trade_share: float | None


def daily_returns(starting_value: Decimal, curve: Curve) -> list[float]:
    """Close-to-close returns; the first day is measured against the starting value."""
    values = [float(starting_value)] + [float(v) for _, v in curve]
    return [b / a - 1 for a, b in zip(values, values[1:])]


def cagr(start: float, end: float, periods: int) -> float | None:
    if periods <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (TRADING_DAYS / periods) - 1


def annual_volatility(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    return statistics.stdev(returns) * math.sqrt(TRADING_DAYS)


def sharpe(returns: Sequence[float], rf_annual: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - rf_annual / TRADING_DAYS for r in returns]
    sd = statistics.stdev(excess)
    if sd == 0:
        return None
    return statistics.fmean(excess) / sd * math.sqrt(TRADING_DAYS)


def sortino(returns: Sequence[float], rf_annual: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - rf_annual / TRADING_DAYS for r in returns]
    downside = math.sqrt(sum(min(0.0, r) ** 2 for r in excess) / len(excess))
    if downside == 0:
        return None
    return statistics.fmean(excess) / downside * math.sqrt(TRADING_DAYS)


def max_drawdown(curve: Curve) -> Drawdown:
    if not curve:
        return Drawdown(0.0, None, None, None, 0)
    dates = [d for d, _ in curve]
    values = [float(v) for _, v in curve]
    peak_i = 0
    worst = 0.0
    worst_peak_i: int | None = None
    worst_trough_i: int | None = None
    for i, value in enumerate(values):
        if value > values[peak_i]:
            peak_i = i
        dd = value / values[peak_i] - 1
        if dd < worst:
            worst, worst_peak_i, worst_trough_i = dd, peak_i, i
    if worst_peak_i is None or worst_trough_i is None:
        return Drawdown(0.0, None, None, None, 0)

    peak_level = values[worst_peak_i]
    recovered_i = next((i for i in range(worst_trough_i + 1, len(values)) if values[i] >= peak_level), None)
    end_i = recovered_i if recovered_i is not None else len(values) - 1
    return Drawdown(
        max_drawdown=worst,
        peak=dates[worst_peak_i],
        trough=dates[worst_trough_i],
        recovered=dates[recovered_i] if recovered_i is not None else None,
        duration_days=end_i - worst_peak_i,
    )


def summarize(starting_value: Decimal, curve: Curve, rf_annual: float = 0.0) -> CurveStats:
    returns = daily_returns(starting_value, curve)
    start, end = float(starting_value), float(curve[-1][1])
    growth = cagr(start, end, len(returns))
    dd = max_drawdown(curve)
    calmar = growth / abs(dd.max_drawdown) if growth is not None and dd.max_drawdown < 0 else None
    return CurveStats(
        total_return=end / start - 1,
        cagr=growth,
        volatility=annual_volatility(returns),
        sharpe=sharpe(returns, rf_annual),
        sortino=sortino(returns, rf_annual),
        drawdown=dd,
        calmar=calmar,
    )


def relative_stats(strategy: Sequence[float], benchmark: Sequence[float]) -> RelativeStats:
    if len(strategy) != len(benchmark) or len(strategy) < 2:
        return RelativeStats(None, None, None)
    variance = statistics.variance(benchmark)
    if variance == 0:
        return RelativeStats(None, None, None)
    beta = statistics.covariance(strategy, benchmark) / variance
    try:
        correlation = statistics.correlation(strategy, benchmark)
    except statistics.StatisticsError:
        correlation = None
    alpha = (statistics.fmean(strategy) - beta * statistics.fmean(benchmark)) * TRADING_DAYS
    return RelativeStats(beta, correlation, alpha)


def trade_stats(trades: Sequence[ClosedTrade]) -> TradeStats:
    nets = [float(t.net_pnl) for t in trades]
    if not nets:
        return TradeStats(0, 0, 0, None, None, None, None, None, None, None, None)
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    avg_win = statistics.fmean(wins) if wins else None
    avg_loss = statistics.fmean(losses) if losses else None
    total = sum(nets)
    return TradeStats(
        count=len(nets),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(nets),
        avg_win=avg_win,
        avg_loss=avg_loss,
        payoff_ratio=avg_win / abs(avg_loss) if avg_win is not None and avg_loss else None,
        profit_factor=gross_win / gross_loss if gross_loss > 0 else None,
        expectancy=statistics.fmean(nets),
        avg_holding_days=statistics.fmean((t.closed_at - t.opened_at).days for t in trades),
        best_trade_share=max(wins) / total if wins and total > 0 else None,
    )


def buy_and_hold_curve(bars: Sequence[Bar], capital: Decimal, dates: Sequence[date]) -> list[tuple[date, Decimal]]:
    """Benchmark: invest everything at the first bar's open and hold."""
    if not bars:
        return []
    start = bars[0].open
    close_by_day = {bar.ts.date(): bar.close for bar in bars}
    return [(d, capital * close_by_day[d] / start) for d in dates if d in close_by_day]
