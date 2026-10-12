from collections.abc import Sequence
from decimal import Decimal


def wilder_rsi(closes: Sequence[Decimal | float], period: int) -> float | None:
    """Wilder's RSI over the whole sequence: seeded with a simple average of the first `period`
    changes, then smoothed recursively. Computing over a fixed-length window keeps it deterministic."""
    if period < 1:
        raise ValueError("period must be at least 1")
    if len(closes) < period + 1:
        return None
    changes = [float(b) - float(a) for a, b in zip(closes, closes[1:])]
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)
