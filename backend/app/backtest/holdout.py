"""Locked holdout: research runs may not touch data on or after the lock date unless explicitly
unlocked with a reason. Every unlock is appended to docs/research/holdout-log.md."""
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

LOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "research" / "holdout-log.md"


class HoldoutLockedError(RuntimeError):
    pass


def check_period(end: datetime, unlock: bool = False, reason: str | None = None, command: str = "") -> None:
    """end is exclusive, so a period ending exactly on the lock date never touches locked data."""
    lock = get_settings().research_lock_date
    if end.date() <= lock:
        return
    if not unlock:
        raise HoldoutLockedError(
            f"This run reaches {end.date()}, past the research lock date {lock}. That period is reserved "
            f"for the final test. Use --unlock-holdout --reason \"...\" to run it anyway; the unlock is logged."
        )
    if not reason or not reason.strip():
        raise HoldoutLockedError("Unlocking the holdout requires a --reason.")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(f"- {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC | {command} | {reason.strip()}\n")
