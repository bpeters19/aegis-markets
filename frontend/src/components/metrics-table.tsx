import type { CurveMetrics } from "@/lib/api";
import { num, pct } from "@/lib/format";

const ROWS: [string, (m: CurveMetrics) => string][] = [
  ["Total return", (m) => pct(m.total_return)],
  ["CAGR", (m) => pct(m.cagr)],
  ["Volatility (annualized)", (m) => pct(m.volatility, false)],
  ["Sharpe ratio", (m) => num(m.sharpe)],
  ["Sortino ratio", (m) => num(m.sortino)],
  ["Calmar ratio", (m) => num(m.calmar)],
  ["Max drawdown", (m) => pct(m.max_drawdown)],
  ["Drawdown length", (m) => `${m.drawdown_days} days`],
];

type Props = {
  strategy: CurveMetrics;
  benchmark: CurveMetrics | null | undefined;
  benchmarkName: string;
};

export default function MetricsTable({ strategy, benchmark, benchmarkName }: Props) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-slate-400">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Metric</th>
            <th className="px-4 py-2 text-right font-medium">Strategy</th>
            <th className="px-4 py-2 text-right font-medium">{benchmarkName} buy and hold</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map(([label, format]) => (
            <tr key={label} className="border-t border-slate-800">
              <td className="px-4 py-2 text-slate-300">{label}</td>
              <td className="px-4 py-2 text-right font-mono tabular-nums">{format(strategy)}</td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-slate-400">
                {benchmark ? format(benchmark) : "n/a"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
