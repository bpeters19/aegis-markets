"use client";

import { useMemo, useState } from "react";

import type { BacktestResponse } from "@/lib/api";
import { money } from "@/lib/format";

type Trade = BacktestResponse["trades"][number];
type Column = {
  key: string;
  label: string;
  value: (t: Trade) => number | string;
  render: (t: Trade) => string;
  numeric?: boolean;
};

const holdingDays = (t: Trade) => Math.round((Date.parse(t.closed_at) - Date.parse(t.opened_at)) / 86_400_000);

const COLUMNS: Column[] = [
  { key: "symbol", label: "Symbol", value: (t) => t.symbol, render: (t) => t.symbol },
  { key: "opened", label: "Opened", value: (t) => t.opened_at, render: (t) => t.opened_at.slice(0, 10) },
  { key: "closed", label: "Closed", value: (t) => t.closed_at, render: (t) => t.closed_at.slice(0, 10) },
  { key: "days", label: "Days", value: holdingDays, render: (t) => String(holdingDays(t)), numeric: true },
  { key: "qty", label: "Qty", value: (t) => t.quantity, render: (t) => String(t.quantity), numeric: true },
  { key: "entry", label: "Entry", value: (t) => Number(t.avg_entry), render: (t) => Number(t.avg_entry).toFixed(2), numeric: true },
  { key: "exit", label: "Exit", value: (t) => Number(t.avg_exit), render: (t) => Number(t.avg_exit).toFixed(2), numeric: true },
  { key: "pnl", label: "Net P&L", value: (t) => Number(t.net_pnl), render: (t) => money(t.net_pnl), numeric: true },
  { key: "reason", label: "Exit reason", value: (t) => t.exit_reason, render: (t) => t.exit_reason.replaceAll("_", " ") },
];

export default function TradeTable({ trades }: { trades: Trade[] }) {
  const [sortKey, setSortKey] = useState("opened");
  const [descending, setDescending] = useState(false);

  const sorted = useMemo(() => {
    const column = COLUMNS.find((c) => c.key === sortKey) ?? COLUMNS[1];
    return [...trades].sort((a, b) => {
      const x = column.value(a);
      const y = column.value(b);
      const order = x < y ? -1 : x > y ? 1 : 0;
      return descending ? -order : order;
    });
  }, [trades, sortKey, descending]);

  function sortBy(key: string) {
    if (key === sortKey) {
      setDescending((d) => !d);
    } else {
      setSortKey(key);
      setDescending(false);
    }
  }

  if (trades.length === 0) {
    return <p className="text-sm text-slate-400">No closed trades in this period.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-slate-400">
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} className={`px-3 py-2 font-medium ${c.numeric ? "text-right" : "text-left"}`}>
                <button type="button" onClick={() => sortBy(c.key)} className="hover:text-slate-200">
                  {c.label}
                  {c.key === sortKey ? (descending ? " v" : " ^") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((t) => {
            const pnl = Number(t.net_pnl);
            return (
              <tr key={`${t.symbol}-${t.opened_at}`} className="border-t border-slate-800">
                {COLUMNS.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3 py-2 ${c.numeric ? "text-right font-mono tabular-nums" : ""} ${
                      c.key === "pnl" ? (pnl > 0 ? "text-emerald-400" : "text-red-400") : ""
                    }`}
                  >
                    {c.render(t)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
