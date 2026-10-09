"""Official hypothesis evaluation: python -m app.research.evaluate H1"""
import argparse
from datetime import timedelta

from app.backtest.holdout import HoldoutLockedError, check_period
from app.backtest.run import load
from app.research.config import config_hash
from app.research.evaluation import at, evaluate_development
from app.research.fingerprint import REPO_ROOT, data_hash, git_commit, holdout_unlocks, registered_config_hash
from app.research.hypotheses.h1 import H1
from app.research.report import to_json, to_markdown

HYPOTHESES = {"H1": H1}
RESULTS_DIR = REPO_ROOT / "docs" / "research" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official development evaluation of a hypothesis")
    parser.add_argument("hypothesis", choices=HYPOTHESES)
    parser.add_argument("--allow-dirty", action="store_true", help="allow uncommitted changes (marks the result +dirty)")
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
    if commit.endswith("+dirty") and not args.allow_dirty:
        raise SystemExit(
            "There are uncommitted changes. Commit first so the result is tied to exact code, "
            "or pass --allow-dirty for a non-official run."
        )

    try:
        check_period(at(config.development.end))
    except HoldoutLockedError as exc:
        raise SystemExit(str(exc))

    series = load(list(config.universe), at(config.development.start) - timedelta(days=400), at(config.development.end))
    fingerprints = {
        "commit": commit,
        "data_hash": data_hash(series),
        "config_hash": current,
        "registered_config_hash": registered,
        "holdout_unlocks": holdout_unlocks(),
    }
    result = evaluate_development(config, series, fingerprints)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = RESULTS_DIR / f"{config.id}-development"
    markdown = to_markdown(result)
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")
    stem.with_suffix(".json").write_text(to_json(result), encoding="utf-8")
    print("\n" + markdown)
    print(f"Saved {stem.with_suffix('.md').relative_to(REPO_ROOT)} and {stem.with_suffix('.json').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
