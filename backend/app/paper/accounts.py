"""Paper accounts: python -m app.paper.accounts create --name h1-shakedown --hypothesis H1 --purpose "..."
                       python -m app.paper.accounts list"""
import argparse
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.paper.models import PaperAccount
from app.research.config import HypothesisConfig, config_hash
from app.research.hypotheses.h1 import H1
from app.research.hypotheses.h3 import H3

STRATEGY_HYPOTHESES: dict[str, HypothesisConfig] = {"H1": H1, "H3": H3}


def create_account(
    session: Session, name: str, hypothesis_id: str, capital: Decimal, purpose: str, start: date | None = None
) -> PaperAccount:
    if hypothesis_id not in STRATEGY_HYPOTHESES:
        raise ValueError(f"{hypothesis_id} cannot be paper traded yet (supported: {', '.join(STRATEGY_HYPOTHESES)})")
    if not purpose.strip():
        raise ValueError("every paper account needs a stated purpose")
    account = PaperAccount(
        name=name,
        hypothesis_id=hypothesis_id,
        config_hash=config_hash(STRATEGY_HYPOTHESES[hypothesis_id]),
        start_date=start or date.today(),
        capital=capital,
        purpose=purpose.strip(),
    )
    session.add(account)
    session.flush()
    return account


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage paper-trading accounts")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--hypothesis", required=True, choices=STRATEGY_HYPOTHESES)
    create.add_argument("--capital", type=Decimal, default=Decimal("100000"))
    create.add_argument("--purpose", required=True)
    sub.add_parser("list")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        if args.command == "create":
            account = create_account(session, args.name, args.hypothesis, args.capital, args.purpose)
            session.commit()
            print(f"Created {account.name}: {account.hypothesis_id} (config {account.config_hash}), "
                  f"${account.capital:,.2f}, starting {account.start_date}")
        else:
            for a in session.scalars(select(PaperAccount).order_by(PaperAccount.id)):
                print(f"{a.name:<16} {a.hypothesis_id:<4} config {a.config_hash}  since {a.start_date}  "
                      f"${a.capital:,.2f}  {a.purpose}")


if __name__ == "__main__":
    main()
