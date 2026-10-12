"""Comparing a paper account's recorded days with a fresh replay. A recorded day is never rewritten:
any difference is reported as drift and the runner stops."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class DayState:
    day: date
    equity: Decimal
    positions: dict[str, int]


def find_drift(recorded: Sequence[DayState], recomputed: Sequence[DayState]) -> list[tuple[date, str]]:
    replayed = {d.day: d for d in recomputed}
    issues: list[tuple[date, str]] = []
    for old in recorded:
        new = replayed.get(old.day)
        if new is None:
            issues.append((old.day, "recorded day is missing from the replay"))
            continue
        if abs(new.equity - old.equity) > TOLERANCE:
            issues.append((old.day, f"equity recorded {old.equity}, replay gives {new.equity}"))
        if new.positions != old.positions:
            issues.append((old.day, f"positions recorded {old.positions}, replay gives {new.positions}"))
    return issues


def unrecorded_days(recorded: Sequence[DayState], recomputed: Sequence[DayState]) -> list[DayState]:
    last = max((d.day for d in recorded), default=None)
    return [d for d in recomputed if last is None or d.day > last]
