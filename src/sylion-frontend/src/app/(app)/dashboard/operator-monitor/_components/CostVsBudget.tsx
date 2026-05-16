"use client";

/**
 * CostVsBudget — global progress bar plus per-project bar chart.
 *
 * Pulls from `monitoring_snapshot.cost_vs_budget`. The per-project breakdown
 * uses recharts horizontal bars (so labels read left-to-right). The global
 * progress bar is the simple Tailwind div pattern used elsewhere in the
 * console — keeping fewer surface dependencies.
 */

import { motion } from "framer-motion";
import { Coins, Wallet } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface PerProjectSpend {
  spend: number;
  budget: number;
}

export interface CostSnapshot {
  spend_usd: number;
  budget_usd: number;
  per_project: Record<string, PerProjectSpend>;
}

export interface ProjectMeta {
  project_id: string;
  project_name: string;
}

interface Props {
  cost: CostSnapshot;
  projects: ProjectMeta[];
}

function pickTone(pct: number): string {
  if (pct >= 1) return "#EF4444";
  if (pct >= 0.85) return "#F59E0B";
  if (pct >= 0.6) return "#3B82F6";
  return "#17C964";
}

function pickToneClass(pct: number): string {
  if (pct >= 1) return "bg-sylion-red";
  if (pct >= 0.85) return "bg-sylion-amber";
  if (pct >= 0.6) return "bg-sylion-blue";
  return "bg-sylion-green";
}

export function CostVsBudget({ cost, projects }: Props) {
  const globalPct = cost.budget_usd > 0 ? cost.spend_usd / cost.budget_usd : 0;
  const remaining = Math.max(0, cost.budget_usd - cost.spend_usd);
  const tone = pickTone(globalPct);
  const toneClass = pickToneClass(globalPct);

  const projectMap = Object.fromEntries(projects.map((p) => [p.project_id, p.project_name]));
  const rows = Object.entries(cost.per_project).map(([projectId, val]) => {
    const pct = val.budget > 0 ? val.spend / val.budget : 0;
    return {
      project_id: projectId,
      name: projectMap[projectId] ?? projectId,
      spend: Number(val.spend.toFixed(2)),
      budget: Number(val.budget.toFixed(2)),
      pct,
      tone: pickTone(pct),
    };
  });
  rows.sort((a, b) => b.pct - a.pct);

  return (
    <Card className="bg-[#0f1629] ring-1 ring-[rgba(148,163,184,0.08)]" data-testid="cost-vs-budget">
      <header className="flex items-start justify-between px-4 pt-1 pb-2">
        <div className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-sylion-blue" />
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Cost vs budget</h2>
            <p className="text-[10px] text-muted-foreground">Monthly spend across all projects</p>
          </div>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            globalPct >= 0.85
              ? "border-sylion-amber/30 text-sylion-amber"
              : "border-sylion-green/30 text-sylion-green",
          )}
        >
          {(globalPct * 100).toFixed(0)}% used
        </Badge>
      </header>

      <div className="px-4 pb-2">
        <div className="mb-2 flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground">
            ${cost.spend_usd.toFixed(2)} of ${cost.budget_usd.toFixed(2)}
          </span>
          <span className="font-mono text-muted-foreground">${remaining.toFixed(2)} left</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-secondary/30" data-testid="global-progress">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(100, globalPct * 100)}%` }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className={cn("h-full rounded-full", toneClass)}
            style={{ background: tone }}
          />
        </div>
      </div>

      <div className="px-2 pb-3" data-testid="per-project-chart">
        {rows.length === 0 ? (
          <div className="px-4 py-6 text-center text-[11px] text-muted-foreground">
            No spend recorded yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(140, rows.length * 42)}>
            <BarChart data={rows} layout="vertical" margin={{ top: 5, right: 16, bottom: 5, left: 8 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.06)" horizontal={false} />
              <XAxis
                type="number"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "rgba(148,163,184,0.45)", fontSize: 10 }}
              />
              <YAxis
                type="category"
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "rgba(226,232,240,0.85)", fontSize: 11 }}
                width={140}
              />
              <Tooltip content={<CostTooltip />} />
              <Legend wrapperStyle={{ fontSize: 10, paddingTop: 4 }} iconType="circle" />
              <Bar dataKey="budget" name="Budget" fill="rgba(148,163,184,0.20)" radius={[3, 3, 3, 3]} />
              <Bar dataKey="spend" name="Spend" radius={[3, 3, 3, 3]}>
                {rows.map((row) => (
                  <Cell key={row.project_id} fill={row.tone} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 border-t border-[rgba(148,163,184,0.06)] px-4 py-3">
        <Stat label="Spend" value={`$${cost.spend_usd.toFixed(2)}`} accent="text-sylion-amber" icon={<Coins className="h-3 w-3" />} />
        <Stat label="Budget" value={`$${cost.budget_usd.toFixed(2)}`} accent="text-sylion-blue" icon={<Wallet className="h-3 w-3" />} />
        <Stat
          label="Projects"
          value={rows.length.toString()}
          accent="text-foreground"
        />
      </div>
    </Card>
  );
}

function Stat({ label, value, accent, icon }: { label: string; value: string; accent: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-[rgba(20,27,45,0.6)] p-2">
      <div className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className={cn("mt-0.5 text-base font-semibold tabular-nums", accent)}>{value}</p>
    </div>
  );
}

interface CostTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; payload: { name: string; pct: number; spend: number; budget: number } }>;
}

function CostTooltip({ active, payload }: CostTooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div
      className="rounded-md border px-2.5 py-1.5 text-xs shadow-lg"
      style={{ background: "rgba(20,27,45,0.95)", borderColor: "rgba(148,163,184,0.15)", backdropFilter: "blur(8px)" }}
    >
      <p className="font-medium">{row.name}</p>
      <p className="text-[10px] text-muted-foreground">
        ${row.spend.toFixed(2)} / ${row.budget.toFixed(2)}
      </p>
      <p className={cn("text-[10px] font-mono", row.pct >= 0.85 ? "text-sylion-amber" : "text-muted-foreground")}>
        {(row.pct * 100).toFixed(0)}% used
      </p>
    </div>
  );
}
