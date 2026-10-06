"use client";

import type { ReactNode } from "react";
import {
  Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import type { ComparisonPoint, ExposurePoint } from "@/lib/chart-data";

const STRATEGY = "#34d399";
const BENCHMARK = "#94a3b8";
const GRID = "#1e293b";
const AXIS = { fill: "#94a3b8", fontSize: 12 };
const TOOLTIP_STYLE = { backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: 8 };

const pctTick = (v: number) => `${(v * 100).toFixed(0)}%`;
const pctTip = (v: unknown) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : "n/a");
const dateTick = (d: string) => d;

export function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </div>
  );
}

type ComparisonProps = { data: ComparisonPoint[]; benchmarkName: string };

export function ReturnChart({ data, benchmarkName }: ComparisonProps) {
  return (
    <ChartCard title="Return" subtitle={`Strategy vs ${benchmarkName} buy and hold, from the same starting value`}>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={dateTick} tick={AXIS} minTickGap={70} />
          <YAxis tickFormatter={pctTick} tick={AXIS} width={48} />
          <Tooltip formatter={(v) => pctTip(v)} contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#e2e8f0" }} />
          <Legend />
          <ReferenceLine y={0} stroke="#475569" />
          <Line name="Strategy" dataKey="strategy" stroke={STRATEGY} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line name={benchmarkName} dataKey="benchmark" stroke={BENCHMARK} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function DrawdownChart({ data, benchmarkName }: ComparisonProps) {
  return (
    <ChartCard title="Drawdown" subtitle="Distance below the previous peak">
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={dateTick} tick={AXIS} minTickGap={70} />
          <YAxis tickFormatter={pctTick} tick={AXIS} width={48} domain={["dataMin", 0]} />
          <Tooltip formatter={(v) => pctTip(v)} contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#e2e8f0" }} />
          <Legend />
          <Area name={benchmarkName} dataKey="benchmark" stroke={BENCHMARK} fill={BENCHMARK} fillOpacity={0.15} isAnimationActive={false} />
          <Area name="Strategy" dataKey="strategy" stroke={STRATEGY} fill={STRATEGY} fillOpacity={0.3} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function ExposureChart({ data }: { data: ExposurePoint[] }) {
  return (
    <ChartCard title="Exposure" subtitle="Share of equity invested at each close">
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={dateTick} tick={AXIS} minTickGap={70} />
          <YAxis tickFormatter={pctTick} tick={AXIS} width={48} domain={[0, 1]} />
          <Tooltip formatter={(v) => pctTip(v)} contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#e2e8f0" }} />
          <Area name="Exposure" dataKey="exposure" stroke={STRATEGY} fill={STRATEGY} fillOpacity={0.25} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
