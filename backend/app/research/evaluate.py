"""Official hypothesis evaluation.

    python -m app.research.evaluate H1                                  development phase
    python -m app.research.evaluate H1 --phase locked --reason "..."    one-time locked-period run
"""
import argparse
import json
from datetime import date, timedelta

from app.backtest.holdout import HoldoutLockedError, check_period
from app.backtest.run import load
from app.research.config import config_hash
from app.research.evaluation import at, evaluate_development, evaluate_locked
from app.research.fingerprint import REPO_ROOT, data_hash, git_commit, holdout_unlocks, registered_config_hash
from app.research.hypotheses.h1 import H1
from app.research.report import to_json, to_markdown

HYPOTHESES = {"H1": H1}
RESULTS_DIR = REPO_ROOT / "docs" / "research" / "results"
FAR_FUTURE = date(2100, 1, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official evaluation of a pre-registered hypothesis")
    parser.add_argument("hypothesis", choices=HYPOTHESES)
    parser.add_argument("--phase", choices=["development", "locked"], default="development")
    parser.add_argument("--reason", help="required for the locked phase; written to the holdout log")
    parser.add_argument("--allow-dirty", action="store_true", help="development only: allow uncommitted changes")
    args = parser.parse_args()
    config = HYPOTHESES[args.hypothesis]

    registered = registered_config_hash(config.id)
    current = config_hash(config)
    if registered is None:
        raise SystemExit(f"No pre-registered config hash found for {config.id} in hypotheses.md.")
    if registered != current:
        raise SystemExit(
            f"Config hash {current} does not match the pre-registered {registered}. "
            f"The configuration changed after pre-registration."
        )

    commit = git_commit()
    if commit.endswith("+dirty") and (args.phase == "locked" or not args.allow_dirty):
        raise SystemExit(
            "There are uncommitted changes. Commit first so the result is tied to exact code."
            + ("" if args.phase == "locked" else " (Or pass --allow-dirty for a non-official run.)")
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = RESULTS_DIR / f"{config.id}-{args.phase}"

    if args.phase == "development":
        try:
            check_period(at(config.development.end))
        except HoldoutLockedError as exc:
            raise SystemExit(str(exc))
        series = load(list(config.universe), at(config.development.start) - timedelta(days=400), at(config.development.end))
        fingerprints = {
            "commit": commit, "data_hash": data_hash(series), "config_hash": current,
            "registered_config_hash": registered, "holdout_unlocks": holdout_unlocks(),
        }
        result = evaluate_development(config, series, fingerprints)
    else:
        development = RESULTS_DIR / f"{config.id}-development.json"
        if not development.exists() or not json.loads(development.read_text(encoding="utf-8"))["passed"]:
            raise SystemExit(f"{config.id} must pass its development evaluation before the locked run.")
        if stem.with_suffix(".json").exists():
            raise SystemExit(f"{config.id} already has a locked result. The locked run happens once and is final.")
        if not args.reason or not args.reason.strip():
            raise SystemExit("The locked run requires --reason, which is written to the holdout log.")

        series = load(list(config.universe), at(config.holdout.start) - timedelta(days=400), at(FAR_FUTURE))
        end = max(b.ts.date() for b in series[config.benchmark]) + timedelta(days=1)
        check_period(at(end), unlock=True, reason=args.reason, command=f"evaluate {config.id} locked")
        fingerprints = {
            "commit": commit, "data_hash": data_hash(series), "config_hash": current,
            "registered_config_hash": registered, "holdout_unlocks": holdout_unlocks(),
        }
        result = evaluate_locked(config, series, fingerprints, end)

    markdown = to_markdown(result)
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")
    stem.with_suffix(".json").write_text(to_json(result), encoding="utf-8")
    print("\n" + markdown)
    print(f"Saved {stem.with_suffix('.md').relative_to(REPO_ROOT)} and {stem.with_suffix('.json').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
