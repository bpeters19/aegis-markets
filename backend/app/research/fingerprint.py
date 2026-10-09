"""Content fingerprints that tie a research result to exact code, data and configuration."""
import hashlib
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.backtest import holdout
from app.market_data.domain import Bar

REPO_ROOT = Path(__file__).resolve().parents[3]
HYPOTHESES_PATH = REPO_ROOT / "docs" / "research" / "hypotheses.md"


def git_commit() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()

    head = git("rev-parse", "--short=12", "HEAD")
    return head + ("+dirty" if git("status", "--porcelain") else "")


def data_hash(series: Mapping[str, Sequence[Bar]]) -> str:
    """Hash of every bar's content. Changes if any price is corrected or re-adjusted."""
    digest = hashlib.sha256()
    for symbol in sorted(series):
        for bar in series[symbol]:
            line = f"{symbol},{bar.ts.isoformat()},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}\n"
            digest.update(line.encode())
    return digest.hexdigest()[:12]


def registered_config_hash(hypothesis_id: str, path: Path = HYPOTHESES_PATH) -> str | None:
    text = path.read_text(encoding="utf-8")
    section = re.search(rf"### {re.escape(hypothesis_id)}:.*?(?=\n### |\Z)", text, re.S)
    if section is None:
        return None
    found = re.search(r"Config hash at pre-registration:\*\* `([0-9a-f]{12})`", section.group(0))
    return found.group(1) if found else None


def holdout_unlocks(path: Path | None = None) -> int:
    path = path or holdout.LOG_PATH
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- "))
