"""Generates a reproducible random order stream for differential tests and benchmarks.

Format, one operation per line (prices are integer ticks):
    L,<id>,<B|S>,<price>,<qty>   limit order
    M,<id>,<B|S>,<qty>           market order
    C,<id>                       cancel
"""
import argparse
import random
from pathlib import Path


def generate(count: int, seed: int, mid: int = 10_000) -> list[str]:
    rng = random.Random(seed)
    next_id = 1
    submitted: list[int] = []  # limit order ids that may still be resting
    lines: list[str] = []
    for _ in range(count):
        roll = rng.random()
        if roll < 0.35 and submitted:
            i = rng.randrange(len(submitted))
            submitted[i], submitted[-1] = submitted[-1], submitted[i]
            lines.append(f"C,{submitted.pop()}")
            continue
        side = "B" if rng.random() < 0.5 else "S"
        qty = rng.randint(1, 100)
        if roll < 0.40:
            lines.append(f"M,{next_id},{side},{qty}")
        else:
            mid = max(100, mid + rng.choice((-1, 0, 1)))
            offset = rng.randint(-5, 20)  # most orders rest away from the touch; negative offsets cross
            price = max(1, mid - offset if side == "B" else mid + offset)
            lines.append(f"L,{next_id},{side},{price},{qty}")
            submitted.append(next_id)
        next_id += 1
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    lines = generate(args.count, args.seed)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    print(f"Wrote {len(lines):,} operations to {args.out}")


if __name__ == "__main__":
    main()
