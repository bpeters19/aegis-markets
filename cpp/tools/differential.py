"""Differential test: the C++ book must produce exactly the same trades and final book as the
Python reference on the same random order stream."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from orderflow import generate  # noqa: E402
from reference_book import replay_lines  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", required=True, help="path to the aegis_replay executable")
    parser.add_argument("--count", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        stream = Path(tmp) / "stream.csv"
        cpp_out = Path(tmp) / "cpp_trades.csv"
        lines = generate(args.count, args.seed)
        stream.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
        subprocess.run([args.replay, str(stream), str(cpp_out)], check=True)
        actual = cpp_out.read_text(encoding="ascii").splitlines()

    expected = replay_lines(lines)
    for i, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            sys.exit(f"MISMATCH at output line {i + 1}:\n  python: {want}\n  c++:    {got}")
    if len(expected) != len(actual):
        sys.exit(f"MISMATCH in length: python {len(expected)} lines, c++ {len(actual)} lines")
    print(f"Differential test passed: {args.count:,} operations (seed {args.seed}), "
          f"{len(expected) - 1:,} identical trades, identical final book: {expected[-1]}")


if __name__ == "__main__":
    main()
