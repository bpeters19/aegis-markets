"""Benchmarks the Python reference book on a stream file, reporting the same figures as aegis_bench."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from reference_book import ReferenceBook, apply, parse  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", required=True)
    args = parser.parse_args()
    ops = parse(Path(args.stream).read_text(encoding="ascii").splitlines())

    book, trades = ReferenceBook(), 0
    start = time.perf_counter()
    for op in ops:
        trades += len(apply(book, op))
    seconds = time.perf_counter() - start

    book, latencies = ReferenceBook(), []
    for op in ops:
        t0 = time.perf_counter_ns()
        apply(book, op)
        latencies.append(time.perf_counter_ns() - t0)
    latencies.sort()
    pct = lambda p: latencies[min(len(latencies) - 1, int(p * len(latencies)))]

    print(f"python reference: {len(ops):,} ops in {seconds:.3f} s = {len(ops) / seconds / 1e6:.2f} M ops/s | "
          f"latency ns p50 {pct(0.50):,} p99 {pct(0.99):,} p99.9 {pct(0.999):,} max {latencies[-1]:,} | "
          f"trades {trades:,}")


if __name__ == "__main__":
    main()
