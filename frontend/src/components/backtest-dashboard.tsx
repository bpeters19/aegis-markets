"use client";

import { useEffect, useState, type ReactNode } from "react";

import { api, ApiError, type BacktestResponse, type SymbolInfo } from "@/lib/api";
import { money, num, pct } from "@/lib/format";
import { toDrawdowns, toExposure, toReturns } from "@/lib/chart-data";
import { ChartCard, DrawdownChart, ExposureChart, ReturnChart } from "./charts";
import MetricsTable from "./metrics-table";
import TradeTable from "./trade-table";

const DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMD", "TSLA", "SPY", "QQQ", "META", "AMZN", "GOOGL"];
const inputClass =
  "w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function Results({ result }: { result: BacktestResponse }) {
  const s = result.strategy;
  const b = result.benchmark;
  const t = result.trade_summary;
  const benchmarkName = result.params.benchmark ?? "SPY";
  const cards: [string, string, string][] = [
    ["Total return", pct(s.total_return), b ? `${benchmarkName} ${pct(b.total_return)}` : ""],
    ["Sharpe ratio", num(s.sharpe), b ? `${benchmarkName} ${num(b.sharpe)}` : ""],
    ["Max drawdown", pct(s.max_drawdown), b ? `${benchmarkName} ${pct(b.max_drawdown)}` : ""],
    ["Closed trades", String(t.count), `win rate ${pct(t.win_rate, false)}`],
  ];

  return (
    <section className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map(([label, value, sub]) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
            <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">{value}</p>
            <p className="mt-1 text-xs text-slate-500">{sub}</p>
          </div>
        ))}
      </div>

      <ReturnChart data={toReturns(result.equity_curve, Number(result.starting_value))} benchmarkName={benchmarkName} />
      <div className="grid gap-6 lg:grid-cols-2">
        <DrawdownChart data={toDrawdowns(result.equity_curve)} benchmarkName={benchmarkName} />
        <ExposureChart data={toExposure(result.equity_curve)} />
      </div>

      <MetricsTable strategy={s} benchmark={b} benchmarkName={benchmarkName} />

      <div className="grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-sm sm:grid-cols-3">
        <p>Average win <span className="font-mono">{money(t.avg_win)}</span></p>
        <p>Average loss <span className="font-mono">{money(t.avg_loss)}</span></p>
        <p>Profit factor <span className="font-mono">{num(t.profit_factor)}</span></p>
        <p>Beta to {benchmarkName} <span className="font-mono">{num(result.relative.beta)}</span></p>
        <p>Alpha (annualized) <span className="font-mono">{pct(result.relative.alpha)}</span></p>
        <p>Best trade share of profit <span className="font-mono">{pct(t.best_trade_share, false)}</span></p>
      </div>

      <ChartCard title="Closed trades" subtitle="Click a column to sort">
        <TradeTable trades={result.trades} />
      </ChartCard>

      <p className="text-xs text-slate-500">
        Run {result.run_id} | {result.trading_days} trading days | signals {result.counts.signals ?? 0}, approved{" "}
        {result.counts.approved ?? 0}, rejected {result.counts.rejected ?? 0} | idle cash earns{" "}
        {pct(Number(result.params.cash_rate ?? 0.02), false)}. Results on hand-picked symbols are in-sample
        diagnostics, not evidence of an edge.
      </p>
    </section>
  );
}

export default function BacktestDashboard() {
  const [available, setAvailable] = useState<SymbolInfo[]>([]);
  const [selected, setSelected] = useState<string[]>(DEFAULT_SYMBOLS);
  const [start, setStart] = useState("2025-01-01");
  const [end, setEnd] = useState("2026-01-01");
  const [fast, setFast] = useState(10);
  const [slow, setSlow] = useState(30);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .symbols()
      .then(setAvailable)
      .catch((e: Error) => setError(`Could not reach the API: ${e.message}`));
  }, []);

  function toggle(symbol: string) {
    setSelected((current) =>
      current.includes(symbol) ? current.filter((s) => s !== symbol) : [...current, symbol],
    );
  }

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.runBacktest({ symbols: selected, start, end, fast, slow, capital: 100000, cash_rate: 0.02, benchmark: "SPY" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Backtest</h2>

        <div className="mt-4 flex flex-wrap gap-2">
          {available.map((s) => (
            <button
              key={s.symbol}
              type="button"
              onClick={() => toggle(s.symbol)}
              title={`${s.bars} bars, ${s.first.slice(0, 10)} to ${s.last.slice(0, 10)}`}
              className={`rounded-md border px-3 py-1 font-mono text-sm ${
                selected.includes(s.symbol)
                  ? "border-emerald-500 bg-emerald-500/10 text-emerald-300"
                  : "border-slate-700 text-slate-400 hover:border-slate-500"
              }`}
            >
              {s.symbol}
            </button>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Field label="Start">
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputClass} />
          </Field>
          <Field label="End">
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={inputClass} />
          </Field>
          <Field label="Fast SMA">
            <input type="number" min={1} value={fast} onChange={(e) => setFast(Number(e.target.value))} className={inputClass} />
          </Field>
          <Field label="Slow SMA">
            <input type="number" min={2} value={slow} onChange={(e) => setSlow(Number(e.target.value))} className={inputClass} />
          </Field>
        </div>

        <button
          type="button"
          onClick={run}
          disabled={loading || selected.length === 0}
          className="mt-6 rounded-md bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Running..." : "Run backtest"}
        </button>
        {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
      </section>

      {result && <Results result={result} />}
    </div>
  );
}
