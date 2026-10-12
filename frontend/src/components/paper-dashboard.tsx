"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { api, ApiError, type PaperAccountDetail, type PaperAccountSummary } from "@/lib/api";
import { money, pct } from "@/lib/format";
import { asItems, describeItem, equitySeries } from "@/lib/paper";
import { ChartCard } from "./charts";

const pctTip = (v: unknown) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : "n/a");

function ItemList({ items, empty }: { items: Record<string, unknown>[]; empty: string }) {
  const list = asItems(items);
  if (list.length === 0) return <p className="text-sm text-slate-400">{empty}</p>;
  return (
    <ul className="space-y-1 font-mono text-sm">
      {list.map((item, i) => (
        <li key={i}>{describeItem(item)}</li>
      ))}
    </ul>
  );
}

function AccountDetail({ detail }: { detail: PaperAccountDetail }) {
  const days = detail.days;
  if (days.length === 0) {
    return (
      <ChartCard title={detail.name} subtitle={detail.purpose}>
        <p className="text-sm text-slate-400">
          No days recorded yet. The daily runner records a trading day after 6 PM New York time.
        </p>
      </ChartCard>
    );
  }

  const capital = Number(detail.capital);
  const latest = days[days.length - 1];
  const positions = Object.entries(latest.positions);
  const ledger = days
    .map((d, i) => ({ d, change: Number(d.equity) - (i > 0 ? Number(days[i - 1].equity) : capital) }))
    .reverse()
    .slice(0, 20);

  return (
    <section className="space-y-6">
      <ChartCard title="Return since start" subtitle={`${detail.name} | ${detail.hypothesis_id} | since ${detail.start_date}`}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={equitySeries(days, capital)}>
            <CartesianGrid stroke="#1e293b" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 12 }} minTickGap={70} />
            <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} tick={{ fill: "#94a3b8", fontSize: 12 }} width={56} />
            <Tooltip
              formatter={(v) => pctTip(v)}
              contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            <ReferenceLine y={0} stroke="#475569" />
            <Line name="Return" dataKey="ret" stroke="#34d399" strokeWidth={2} dot={days.length < 30} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid gap-6 lg:grid-cols-3">
        <ChartCard title="Positions" subtitle={`as of ${latest.day}`}>
          {positions.length === 0 ? (
            <p className="text-sm text-slate-400">No open positions.</p>
          ) : (
            <ul className="space-y-1 font-mono text-sm">
              {positions.map(([symbol, quantity]) => (
                <li key={symbol} className="flex justify-between">
                  <span>{symbol}</span>
                  <span className="tabular-nums">{quantity}</span>
                </li>
              ))}
            </ul>
          )}
        </ChartCard>
        <ChartCard title="Fills" subtitle={`on ${latest.day}`}>
          <ItemList items={latest.fills} empty="No fills." />
        </ChartCard>
        <ChartCard title="Orders for the next session" subtitle={`placed after the ${latest.day} close`}>
          <ItemList items={latest.working_orders} empty="No orders queued." />
        </ChartCard>
      </div>

      <ChartCard title="Ledger" subtitle="Append-only daily record, newest first">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Day</th>
                <th className="px-3 py-2 text-right font-medium">Equity</th>
                <th className="px-3 py-2 text-right font-medium">Change</th>
                <th className="px-3 py-2 text-right font-medium">Exposure</th>
                <th className="px-3 py-2 text-right font-medium">Fills</th>
                <th className="px-3 py-2 text-left font-medium">Code</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map(({ d, change }) => (
                <tr key={d.day} className="border-t border-slate-800">
                  <td className="px-3 py-2 font-mono">{d.day}</td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{money(d.equity)}</td>
                  <td className={`px-3 py-2 text-right font-mono tabular-nums ${change >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {money(change)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{pct(d.exposure, false)}</td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{d.fills.length}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{d.code_commit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </section>
  );
}

export default function PaperDashboard() {
  const [accounts, setAccounts] = useState<PaperAccountSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<PaperAccountDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .paperAccounts()
      .then((list) => {
        setAccounts(list);
        if (list.length > 0) setSelected(list[0].name);
      })
      .catch((e: Error) => setError(`Could not reach the API: ${e.message}`));
  }, []);

  useEffect(() => {
    if (!selected) return;
    api
      .paperAccount(selected)
      .then(setDetail)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [selected]);

  return (
    <div className="space-y-8">
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        {accounts.map((a) => (
          <button
            key={a.name}
            type="button"
            onClick={() => setSelected(a.name)}
            className={`rounded-xl border p-4 text-left ${
              a.name === selected ? "border-emerald-500 bg-emerald-500/5" : "border-slate-800 bg-slate-900/60 hover:border-slate-600"
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono font-semibold">{a.name}</span>
              <span className="text-xs text-slate-500">{a.hypothesis_id} | config {a.config_hash}</span>
            </div>
            <p className="mt-2 font-mono text-xl tabular-nums">{money(a.latest_equity ?? a.capital)}</p>
            <p className="text-xs text-slate-400">
              {a.return_since_start == null
                ? "no days recorded yet"
                : `${pct(a.return_since_start)} since ${a.start_date} | ${a.days_recorded} days`}
            </p>
            <p className="mt-2 text-xs text-slate-500">{a.purpose}</p>
          </button>
        ))}
      </div>
      {detail && <AccountDetail detail={detail} />}
    </div>
  );
}
