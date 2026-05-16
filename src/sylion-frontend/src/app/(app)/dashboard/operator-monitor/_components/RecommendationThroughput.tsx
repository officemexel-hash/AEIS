"use client";

/**
 * RecommendationThroughput — area chart of emitted vs accepted vs rejected.
 *
 * Renders the engine event taxonomy (07_event_taxonomy.md §4.3):
 *   - aeis.advisor.engine.recommendation_emitted (orange line)
 *   - history.action_recorded (action=accept) (green line)
 *   - history.action_recorded (action=reject) (red line)
 *
 * The hook delivers a 14-day rolling series. We visualise it as overlapping
 * areas so trend reading is more important than absolute pixel accuracy.
 */

import { motion } from "framer-motion";
import { Activity, TrendingUp, TrendingDown } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, fmtDate } from "@/lib/utils";

export interface ThroughputPoint {
  ts: number; // unix seconds
  emitted: number;
  accepted: number;
  rejected: number;
}

interface Props {
  data: ThroughputPoint[];
}

export function RecommendationThroughput({ data }: Props) {
  const series = data.map((p) => ({
    date: fmtDate(p.ts * 1000).slice(5),
    emitted: p.emitted,
    accepted: p.accepted,
    rejected: p.rejected,
  }));

  const totalEmitted = data.reduce((a, p) => a + p.emitted, 0);
  const totalAccepted = data.reduce((a, p) => a + p.accepted, 0);
  const totalRejected = data.reduce((a, p) => a + p.rejected, 0);
  const acceptRate = totalEmitted > 0 ? totalAccepted / totalEmitted : 0;
  const rejectRate = totalEmitted > 0 ? totalRejected / totalEmitted : 0;

  const last = data[data.length - 1];
  const prev = data[data.length - 2];
  const lastEmitted = last?.emitted ?? 0;
  const trendPct = prev && prev.emitted
    ? ((lastEmitted - prev.emitted) / Math.max(1, prev.emitted)) * 100
    : 0;
  const TrendIcon = trendPct >= 0 ? TrendingUp : TrendingDown;
  const trendColor = trendPct >= 0 ? "text-sylion-green" : "text-sylion-amber";

  return (
    <Card
      className="bg-[#0f1629] ring-1 ring-[rgba(148,163,184,0.08)]"
      data-testid="recommendation-throughput"
    >
      <header className="flex items-start justify-between px-4 pt-1 pb-2">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-sylion-blue" />
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Recommendation throughput</h2>
            <p className="text-[10px] text-muted-foreground">
              14-day window · emitted vs accepted vs rejected
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <TrendIcon className={cn("h-3.5 w-3.5", trendColor)} />
          <span className={cn("text-[11px] font-medium", trendColor)}>
            {trendPct >= 0 ? "+" : ""}
            {trendPct.toFixed(0)}%
          </span>
        </div>
      </header>

      <div className="px-2" data-testid="throughput-chart">
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={series} margin={{ top: 5, right: 12, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="advisorEmitted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(245,158,11,0.32)" />
                <stop offset="95%" stopColor="rgba(245,158,11,0.02)" />
              </linearGradient>
              <linearGradient id="advisorAccepted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(23,201,100,0.30)" />
                <stop offset="95%" stopColor="rgba(23,201,100,0.02)" />
              </linearGradient>
              <linearGradient id="advisorRejected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(239,68,68,0.28)" />
                <stop offset="95%" stopColor="rgba(239,68,68,0.02)" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" vertical={false} />
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "rgba(148,163,184,0.45)", fontSize: 10 }}
              minTickGap={20}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "rgba(148,163,184,0.45)", fontSize: 10 }}
              width={32}
            />
            <Tooltip content={<ThroughputTooltip />} />
            <Legend
              iconType="circle"
              wrapperStyle={{ fontSize: 10, paddingTop: 6 }}
            />
            <Area
              type="monotone"
              dataKey="emitted"
              name="Emitted"
              stroke="rgba(245,158,11,0.85)"
              strokeWidth={2}
              fill="url(#advisorEmitted)"
              dot={false}
              activeDot={{ r: 4, fill: "#F59E0B", stroke: "#0f1629", strokeWidth: 2 }}
            />
            <Area
              type="monotone"
              dataKey="accepted"
              name="Accepted"
              stroke="rgba(23,201,100,0.85)"
              strokeWidth={2}
              fill="url(#advisorAccepted)"
              dot={false}
              activeDot={{ r: 4, fill: "#17C964", stroke: "#0f1629", strokeWidth: 2 }}
            />
            <Area
              type="monotone"
              dataKey="rejected"
              name="Rejected"
              stroke="rgba(239,68,68,0.85)"
              strokeWidth={2}
              fill="url(#advisorRejected)"
              dot={false}
              activeDot={{ r: 4, fill: "#EF4444", stroke: "#0f1629", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-2 px-4 pb-3 pt-2 border-t border-[rgba(148,163,184,0.06)]">
        <Stat label="Emitted (14d)" value={totalEmitted.toString()} accent="text-amber-400" />
        <Stat
          label="Accept rate"
          value={`${(acceptRate * 100).toFixed(0)}%`}
          accent="text-sylion-green"
        />
        <Stat
          label="Reject rate"
          value={`${(rejectRate * 100).toFixed(0)}%`}
          accent="text-sylion-red"
        />
      </div>
    </Card>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-[rgba(20,27,45,0.6)] p-2"
    >
      <p className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-semibold tabular-nums", accent)}>{value}</p>
    </motion.div>
  );
}

interface ChartTooltipProps {
  active?: boolean;
  label?: string;
  payload?: Array<{ name: string; value: number; color: string }>;
}

function ThroughputTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-md border px-2.5 py-1.5 text-xs shadow-lg"
      style={{ background: "rgba(20,27,45,0.95)", borderColor: "rgba(148,163,184,0.15)", backdropFilter: "blur(8px)" }}
    >
      <p className="text-[10px] text-muted-foreground">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="mt-0.5 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: entry.color }} />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-mono font-medium tabular-nums">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export const __test_helpers = {
  buildSeries(data: ThroughputPoint[]) {
    return data.map((p) => ({
      date: fmtDate(p.ts * 1000).slice(5),
      emitted: p.emitted,
      accepted: p.accepted,
      rejected: p.rejected,
    }));
  },
};
