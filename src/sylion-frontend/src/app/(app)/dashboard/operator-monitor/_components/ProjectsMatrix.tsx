"use client";

/**
 * ProjectsMatrix — projects (rows) × phases (columns) grid.
 *
 * Each cell shows current phase status, active card count for the project's
 * active phase, and a small accept-rate sparkline. The 16 lifecycle hooks
 * (H01..H16) are used as the column basis to align with the engine taxonomy.
 *
 * Pure presentational — receives the monitoring snapshot's `projects` slice and
 * an optional throughput series so we can synthesise a sparkline trend.
 */

import { motion } from "framer-motion";
import { Activity, ArrowRight, FolderKanban, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const HOOKS: { id: string; label: string }[] = [
  { id: "H01", label: "Model" },
  { id: "H02", label: "Dostawca" },
  { id: "H03", label: "Budżet" },
  { id: "H04", label: "Pomysł" },
  { id: "H05", label: "Model SoT" },
  { id: "H06", label: "Rada" },
  { id: "H07", label: "Autonomia" },
  { id: "H08", label: "Szkic SoT" },
  { id: "H09", label: "Master" },
  { id: "H10", label: "Topologia" },
  { id: "H11", label: "VPS" },
  { id: "H12", label: "Skille" },
  { id: "H13", label: "Wdrożenie" },
  { id: "H14", label: "Test" },
  { id: "H15", label: "HG" },
  { id: "H16", label: "Finał" },
];

export interface MatrixProject {
  project_id: string;
  project_name: string;
  project_type: string;
  project_domain: string;
  active_phase: string; // e.g. "H08 — SoT drafting"
  active_cards: number;
  accept_rate: number;
  spend_usd_month: number;
  budget_usd_month: number;
}

export interface MatrixThroughputPoint {
  ts: number;
  emitted: number;
  accepted: number;
  rejected: number;
}

interface Props {
  projects: MatrixProject[];
  throughput: MatrixThroughputPoint[];
  onSelectProject?: (projectId: string) => void;
}

export function ProjectsMatrix({ projects, throughput, onSelectProject }: Props) {
  const trend = buildAcceptTrend(throughput);
  return (
    <Card className="bg-[#0f1629] ring-1 ring-[rgba(148,163,184,0.08)]" data-testid="projects-matrix">
      <header className="flex items-center justify-between px-4 pt-1 pb-2">
        <div className="flex items-center gap-2">
          <FolderKanban className="h-4 w-4 text-sylion-blue" />
          <h2 className="text-sm font-semibold tracking-tight">Macierz projektów</h2>
        </div>
        <Badge variant="outline" className="text-[10px] border-sylion-blue/30 text-sylion-blue">
          {projects.length} projektów · 16 faz
        </Badge>
      </header>
      <div className="overflow-x-auto px-2 pb-3">
        <table className="min-w-full border-separate border-spacing-x-1 border-spacing-y-1">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-[#0f1629] px-3 py-1.5 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Projekt
              </th>
              {HOOKS.map((h) => (
                <th
                  key={h.id}
                  className="px-1.5 py-1.5 text-center text-[9px] font-mono text-muted-foreground"
                  title={h.label}
                >
                  <div className="flex flex-col items-center gap-0.5">
                    <span className="font-semibold">{h.id}</span>
                    <span className="hidden text-[8px] uppercase tracking-wider opacity-60 lg:block">{h.label}</span>
                  </div>
                </th>
              ))}
              <th className="px-2 py-1.5 text-right text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Trend
              </th>
            </tr>
          </thead>
          <tbody>
            {projects.length === 0 ? (
              <tr>
                <td colSpan={HOOKS.length + 2} className="px-3 py-6 text-center text-xs text-muted-foreground">
                  Brak aktywnych projektów.
                </td>
              </tr>
            ) : null}
            {projects.map((p, idx) => {
              const activeIdx = HOOKS.findIndex((h) => p.active_phase.startsWith(h.id));
              return (
                <motion.tr
                  key={p.project_id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="cursor-pointer transition-colors hover:bg-[rgba(148,163,184,0.04)]"
                  onClick={() => onSelectProject?.(p.project_id)}
                  data-testid={`matrix-row-${p.project_id}`}
                >
                  <th className="sticky left-0 z-10 bg-[#0f1629] px-3 py-2 text-left text-xs">
                    <div className="flex flex-col">
                      <span className="font-medium text-foreground">{p.project_name}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {p.project_type} · {p.project_domain}
                      </span>
                      <span className="mt-0.5 inline-flex items-center gap-1 text-[10px] text-sylion-blue">
                        {p.active_phase}
                        <ArrowRight className="h-2.5 w-2.5" />
                      </span>
                    </div>
                  </th>
                  {HOOKS.map((h, i) => {
                    const isActive = i === activeIdx;
                    const isPast = i < activeIdx;
                    return (
                      <td
                        key={h.id}
                        className={cn(
                          "h-9 min-w-[44px] rounded-sm border px-1 py-1 text-center align-middle text-[10px]",
                          isActive
                            ? "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue"
                            : isPast
                              ? "border-sylion-green/20 bg-sylion-green/5 text-sylion-green"
                              : "border-[rgba(148,163,184,0.08)] bg-[rgba(20,27,45,0.6)] text-muted-foreground/60",
                        )}
                        data-testid={`matrix-cell-${p.project_id}-${h.id}`}
                      >
                        {isActive ? (
                          <div className="flex flex-col items-center gap-0.5">
                            <Activity className="h-3 w-3" />
                            <span className="font-mono text-[9px] font-semibold">{p.active_cards}</span>
                          </div>
                        ) : isPast ? (
                          <span className="text-sylion-green">●</span>
                        ) : (
                          <span className="opacity-30">–</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-2 py-2 text-right">
                    <Sparkline values={trend} acceptRate={p.accept_rate} />
                    <p className="mt-0.5 text-[10px] font-mono text-muted-foreground">
                      {(p.accept_rate * 100).toFixed(0)}%
                    </p>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {projects.some((p) => p.spend_usd_month > p.budget_usd_month * 0.85) ? (
        <div className="mx-3 mb-3 flex items-center gap-2 rounded-md border border-sylion-amber/30 bg-sylion-amber/5 px-2 py-1.5 text-[10px] text-sylion-amber">
          <ShieldAlert className="h-3 w-3" />
          Co najmniej jeden projekt przekroczył 85% miesięcznego budżetu - szczegóły są w panelu kosztu względem budżetu.
        </div>
      ) : null}
    </Card>
  );
}

function Sparkline({ values, acceptRate }: { values: number[]; acceptRate: number }) {
  if (!values.length) {
    return <div className="h-5 w-20 rounded bg-secondary/20" />;
  }
  const max = Math.max(1, ...values);
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100;
      const y = 100 - (v / max) * 100;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const tone =
    acceptRate >= 0.8
      ? "stroke-sylion-green"
      : acceptRate >= 0.6
        ? "stroke-sylion-blue"
        : acceptRate >= 0.4
          ? "stroke-sylion-amber"
          : "stroke-sylion-red";
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="ml-auto h-5 w-20">
      <polyline fill="none" strokeWidth="3" className={tone} points={points} />
    </svg>
  );
}

function buildAcceptTrend(points: MatrixThroughputPoint[]): number[] {
  if (!points.length) return [];
  return points.map((p) => {
    const total = p.emitted || 1;
    return Math.max(0, Math.min(1, p.accepted / total));
  });
}
