import type { BacktestResponse } from "./api";

type Curve = BacktestResponse["equity_curve"];

export type ComparisonPoint = { date: string; strategy: number; benchmark: number | null };
export type ExposurePoint = { date: string; exposure: number };

/** Equity as a return from the starting value, for strategy and benchmark. */
export function toReturns(curve: Curve, startingValue: number): ComparisonPoint[] {
  return curve.map((p) => ({
    date: p.date,
    strategy: Number(p.equity) / startingValue - 1,
    benchmark: p.benchmark == null ? null : Number(p.benchmark) / startingValue - 1,
  }));
}

/** Distance below the running peak; same definition the backend uses for max drawdown. */
export function drawdowns(values: (number | null)[]): (number | null)[] {
  let peak = -Infinity;
  return values.map((value) => {
    if (value == null) return null;
    peak = Math.max(peak, value);
    return value / peak - 1;
  });
}

export function toDrawdowns(curve: Curve): ComparisonPoint[] {
  const strategy = drawdowns(curve.map((p) => Number(p.equity)));
  const benchmark = drawdowns(curve.map((p) => (p.benchmark == null ? null : Number(p.benchmark))));
  return curve.map((p, i) => ({ date: p.date, strategy: strategy[i] ?? 0, benchmark: benchmark[i] }));
}

export function toExposure(curve: Curve): ExposurePoint[] {
  return curve.map((p) => ({ date: p.date, exposure: p.exposure }));
}
