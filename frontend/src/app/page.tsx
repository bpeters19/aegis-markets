import BacktestDashboard from "@/components/backtest-dashboard";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Aegis Markets</h1>
          <p className="mt-1 text-sm text-slate-400">
            Event-driven backtesting: strategy, risk, order management, execution and portfolio accounting.
          </p>
        </header>
        <BacktestDashboard />
      </div>
    </main>
  );
}
