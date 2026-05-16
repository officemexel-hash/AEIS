"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";
import { Card } from "@/components/ui/card";
import type { ProjectLifecycleState, ProjectLifecyclePhase } from "@/lib/api/advisor";

interface Props {
  lifecycle: ProjectLifecycleState;
  onPhaseClick?: (hookId: string) => void;
  selected?: string;
}

const STATUS_COLOR: Record<ProjectLifecyclePhase["status"], string> = {
  approved: "var(--color-sylion-green, #10b981)",
  in_progress: "var(--color-sylion-blue, #3b82f6)",
  pending: "var(--color-muted-foreground, #94a3b8)",
  blocked: "var(--color-sylion-red, #ef4444)",
};

const STATUS_WEIGHT: Record<ProjectLifecyclePhase["status"], number> = {
  approved: 4,
  in_progress: 3,
  blocked: 2,
  pending: 1,
};

export function LifecycleFlowChart({ lifecycle, onPhaseClick, selected }: Props) {
  const data = useMemo(
    () =>
      lifecycle.phases.map((phase) => ({
        hook_id: phase.hook_id,
        weight: STATUS_WEIGHT[phase.status],
        status: phase.status,
        cards: phase.cards?.length ?? 0,
      })),
    [lifecycle.phases],
  );

  return (
    <Card className="bg-card p-3" data-testid="lifecycle-flow-chart">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Przeplyw faz</h3>
        <p className="text-[10px] text-muted-foreground">
          wysokosc zalezy od statusu: zatwierdzone, w toku, zablokowane, oczekuje
        </p>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
          <XAxis
            dataKey="hook_id"
            tick={{ fontSize: 9, fill: "rgba(148,163,184,0.6)" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis hide domain={[0, 4]} />
          <Tooltip
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
            contentStyle={{
              background: "rgba(15,22,41,0.95)",
              border: "1px solid rgba(148,163,184,0.15)",
              borderRadius: 8,
              fontSize: 11,
              padding: 8,
            }}
            formatter={(_value, _name, item) => {
              const payload = (item && (item as { payload?: { status: string; cards: number } }).payload) || null;
              return [`${statusLabel(payload?.status ?? "?")} · ${payload?.cards ?? 0} kart`, "faza"];
            }}
            labelFormatter={(label) => `Hook ${String(label ?? "")}`}
          />
          <Bar
            dataKey="weight"
            radius={[3, 3, 0, 0]}
            onClick={(barData) => {
              const hookId = (barData as unknown as { hook_id?: string })?.hook_id;
              if (hookId) onPhaseClick?.(hookId);
            }}
          >
            {data.map((entry) => (
              <Cell
                key={entry.hook_id}
                fill={STATUS_COLOR[entry.status]}
                fillOpacity={selected && selected !== entry.hook_id ? 0.45 : 0.95}
                stroke={selected === entry.hook_id ? "rgba(59,130,246,0.9)" : "transparent"}
                strokeWidth={selected === entry.hook_id ? 1.5 : 0}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function statusLabel(status: string): string {
  if (status === "approved") return "zatwierdzone";
  if (status === "in_progress") return "w toku";
  if (status === "blocked") return "zablokowane";
  if (status === "pending") return "oczekuje";
  return status;
}
