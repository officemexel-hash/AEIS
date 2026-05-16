"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  useSkills,
  useSkillExecutions,
  useDemandSignals,
  useHealth,
} from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  Cpu,
  Loader2,
  RotateCw,
  Signal,
  Layers,
  WifiOff,
  Plus,
  Filter,
  Play,
  BarChart3,
} from "lucide-react";
import type { SkillLifecycle } from "@/lib/types";

/* ============================================================
   Constants & Helpers
   ============================================================ */

const LIFECYCLE_STAGES: SkillLifecycle[] = [
  "DRAFT",
  "TESTING",
  "PUBLISHED",
  "DEPRECATED",
];

const LIFECYCLE_META: Record<
  SkillLifecycle,
  { color: string; bg: string; border: string; label: string }
> = {
  DRAFT: {
    color: "text-muted-foreground",
    bg: "bg-secondary/50",
    border: "border-border",
    label: "Szkic",
  },
  TESTING: {
    color: "text-sylion-amber",
    bg: "bg-sylion-amber/10",
    border: "border-sylion-amber/20",
    label: "Testy",
  },
  PUBLISHED: {
    color: "text-sylion-green",
    bg: "bg-sylion-green/10",
    border: "border-sylion-green/20",
    label: "Opublikowana",
  },
  DEPRECATED: {
    color: "text-sylion-red",
    bg: "bg-sylion-red/10",
    border: "border-sylion-red/20",
    label: "Wycofywana",
  },
};

const EXEC_STATUS_META: Record<
  string,
  { color: string; bg: string; border: string; icon: React.ElementType }
> = {
  completed: {
    color: "text-sylion-green",
    bg: "bg-sylion-green/10",
    border: "border-sylion-green/20",
    icon: CheckCircle2,
  },
  failed: {
    color: "text-sylion-red",
    bg: "bg-sylion-red/10",
    border: "border-sylion-red/20",
    icon: XCircle,
  },
  pending: {
    color: "text-sylion-amber",
    bg: "bg-sylion-amber/10",
    border: "border-sylion-amber/20",
    icon: Clock,
  },
  running: {
    color: "text-sylion-blue",
    bg: "bg-sylion-blue/10",
    border: "border-sylion-blue/20",
    icon: Loader2,
  },
};

const DOMAIN_COLORS: Record<string, string> = {
  security: "bg-sylion-red/15 text-sylion-red border-sylion-red/20",
  efficiency: "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20",
  governance: "bg-purple-500/15 text-purple-400 border-purple-500/20",
  architecture: "bg-sylion-blue/15 text-sylion-blue border-sylion-blue/20",
  aeis: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  core: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
  cognitive: "bg-pink-500/15 text-pink-400 border-pink-500/20",
  execution: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  quality: "bg-violet-500/15 text-violet-400 border-violet-500/20",
  memory: "bg-teal-500/15 text-teal-400 border-teal-500/20",
  rebuild: "bg-lime-500/15 text-lime-400 border-lime-500/20",
};

function getDomainBadge(domain: string): string {
  return (
    DOMAIN_COLORS[domain] ??
    "bg-secondary/50 text-muted-foreground border-border"
  );
}

const URGENCY_COLORS: Record<string, string> = {
  critical: "text-sylion-red border-sylion-red/30 bg-sylion-red/10",
  high: "text-sylion-amber border-sylion-amber/30 bg-sylion-amber/10",
  medium: "text-sylion-blue border-sylion-blue/30 bg-sylion-blue/10",
  low: "text-muted-foreground border-border bg-secondary/30",
};

const URGENCY_BAR: Record<string, string> = {
  critical: "bg-sylion-red",
  high: "bg-sylion-amber",
  medium: "bg-sylion-blue",
  low: "bg-muted-foreground/40",
};

const STRENGTH_META: Record<string, { label: string; color: string; bars: number }> = {
  high: { label: "Wysoka", color: "text-sylion-red", bars: 3 },
  medium: { label: "Średnia", color: "text-sylion-amber", bars: 2 },
  low: { label: "Niska", color: "text-sylion-blue", bars: 1 },
};

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "--";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatTimestamp(ts: string | number | null | undefined): string {
  if (!ts) return "--";
  const date = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
  if (isNaN(date.getTime())) return "--";
  const diff = Date.now() - date.getTime();
  if (diff < 0) return "teraz";
  if (diff < 60000) return `${Math.floor(diff / 1000)} s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)} min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} godz. temu`;
  return date.toLocaleDateString("pl-PL", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getTriggerBadge(trigger: string): { label: string; color: string } {
  switch ((trigger ?? "").toLowerCase()) {
    case "manual":
      return { label: "Manualnie", color: "bg-sylion-blue/10 text-sylion-blue border-sylion-blue/20" };
    case "auto":
    case "automatic":
      return { label: "Automat", color: "bg-sylion-green/10 text-sylion-green border-sylion-green/20" };
    case "cascade":
      return { label: "Kaskada", color: "bg-sylion-amber/10 text-sylion-amber border-sylion-amber/20" };
    default:
      return { label: trigger ?? "--", color: "bg-secondary/50 text-muted-foreground border-border" };
  }
}


/* ============================================================
   Sub-components
   ============================================================ */

function StatCard({
  label,
  value,
  icon: Icon,
  accent,
  bgColor,
  sub,
  tipText,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  accent: string;
  bgColor: string;
  sub?: string;
  tipText?: string;
}) {
  const computedTip = tipText ?? (
    label.includes("Zarejestrowane") ? "Umiejętności zarejestrowane w katalogu (we wszystkich etapach cyklu życia)."
    : label.includes("wykonań") ? "Łączna liczba wykonań umiejętności (powodzenie + nieudane)."
    : label.includes("sukcesu") ? "Procent wykonań zakończonych statusem completed względem failed."
    : label.includes("popytu") ? "Sygnały od systemu o brakujących lub niedostatecznych umiejętnościach."
    : undefined
  );
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card className="relative overflow-hidden p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)] transition-all duration-300">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
              {label}
              {computedTip && <HelpTip text={computedTip} />}
            </p>
            <p className={cn("text-2xl font-semibold mt-1", accent)}>
              {value}
            </p>
            {sub && (
              <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>
            )}
          </div>
          <div
            className={cn(
              "w-9 h-9 rounded-lg flex items-center justify-center",
              bgColor
            )}
          >
            <Icon className={cn("w-4 h-4", accent)} />
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[rgba(148,163,184,0.1)] to-transparent" />
      </Card>
    </motion.div>
  );
}

function TabButton({
  label,
  icon: Icon,
  active,
  count,
  onClick,
}: {
  label: string;
  icon: React.ElementType;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg transition-all duration-200",
        active
          ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_12px_rgba(47,107,255,0.08)]"
          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50 border border-transparent"
      )}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
      {count != null && (
        <span
          className={cn(
            "text-[9px] px-1.5 py-0.5 rounded-full",
            active
              ? "bg-primary/20 text-primary"
              : "bg-secondary text-muted-foreground"
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

/* ---- Skills Registry Tab ---- */
function SkillsTab({
  skills,
  filterCategory,
  onFilterChange,
}: {
  skills: any[];
  filterCategory: string;
  onFilterChange: (cat: string) => void;
}) {
  const categories = useMemo(() => {
    const cats = new Set<string>();
    for (const s of skills) {
      cats.add(s.domain ?? s.category ?? "general");
    }
    return Array.from(cats).sort();
  }, [skills]);

  const filtered = useMemo(() => {
    if (!filterCategory || filterCategory === "all") return skills;
    return skills.filter(
      (s) => (s.domain ?? s.category ?? "general") === filterCategory
    );
  }, [skills, filterCategory]);

  if (skills.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Cpu className="w-8 h-8 text-muted-foreground/40 mb-3" />
        <p className="text-xs text-muted-foreground">Brak zarejestrowanych umiejetnosci.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Category filter bar */}
      <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.06)] flex items-center gap-2 flex-wrap">
        <Filter className="w-3 h-3 text-muted-foreground mr-1" />
        <button
          onClick={() => onFilterChange("all")}
          className={cn(
            "px-2.5 py-1 text-[10px] font-medium rounded-full border transition-all",
            filterCategory === "all" || !filterCategory
              ? "bg-primary/10 text-primary border-primary/20"
              : "text-muted-foreground hover:text-foreground border-transparent hover:bg-secondary/50"
          )}
        >
          Wszystkie ({skills.length})
        </button>
        {categories.map((cat) => {
          const count = skills.filter(
            (s) => (s.domain ?? s.category ?? "general") === cat
          ).length;
          return (
            <button
              key={cat}
              onClick={() => onFilterChange(cat)}
              className={cn(
                "px-2.5 py-1 text-[10px] font-medium rounded-full border transition-all",
                filterCategory === cat
                  ? getDomainBadge(cat) + " ring-1 ring-current/20"
                  : "text-muted-foreground hover:text-foreground border-transparent hover:bg-secondary/50"
              )}
            >
              {cat} ({count})
            </button>
          );
        })}
      </div>

      {/* Skill cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 p-4">
        {filtered.map((skill: any, idx: number) => {
          const domain = skill.domain ?? skill.category ?? "general";
          const lifecycle = (
            skill.lifecycle ?? "DRAFT"
          ).toUpperCase() as SkillLifecycle;
          const meta = LIFECYCLE_META[lifecycle] ?? LIFECYCLE_META.DRAFT;
          const execCount =
            skill.execution_count ?? skill.usage_count ?? 0;
          const successRate =
            skill.success_rate ?? skill.successRate ?? 0;
          const lastExec = skill.last_executed ?? skill.lastExecuted;
          const successPct =
            typeof successRate === "number" && successRate <= 1
              ? Math.round(successRate * 100)
              : typeof successRate === "number"
                ? successRate
                : 0;

          return (
            <motion.div
              key={skill.skill_id ?? skill.id ?? idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: idx * 0.03 }}
            >
              <Card className="p-4 bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] hover:border-[rgba(148,163,184,0.12)] transition-all duration-200 group">
                {/* Top: ID + lifecycle */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {skill.skill_id ?? skill.id}
                  </span>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium border",
                      meta.bg,
                      meta.border,
                      meta.color
                    )}
                  >
                    {meta.label}
                  </span>
                </div>

                {/* Name */}
                <h4 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors mb-1">
                  {skill.name}
                </h4>

                {/* Description */}
                {skill.description && (
                  <p className="text-[10px] text-muted-foreground leading-relaxed mb-3 line-clamp-2">
                    {skill.description}
                  </p>
                )}

                {/* Success rate bar */}
                <div className="mb-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                      Success Rate
                    </span>
                    <span
                      className={cn(
                        "text-[11px] font-semibold",
                        successPct >= 90
                          ? "text-sylion-green"
                          : successPct >= 70
                            ? "text-sylion-amber"
                            : "text-sylion-red"
                      )}
                    >
                      {successPct}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-secondary">
                    <motion.div
                      className={cn(
                        "h-full rounded-full",
                        successPct >= 90
                          ? "bg-sylion-green"
                          : successPct >= 70
                            ? "bg-sylion-amber"
                            : "bg-sylion-red"
                      )}
                      initial={{ width: 0 }}
                      animate={{ width: `${successPct}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                </div>

                {/* Bottom: domain badge + exec count + last executed */}
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-[rgba(148,163,184,0.06)]">
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-medium border",
                      getDomainBadge(domain)
                    )}
                  >
                    {domain}
                  </span>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1">
                      <Activity className="w-3 h-3 text-muted-foreground" />
                      <span className="text-[10px] text-muted-foreground">
                        {execCount}
                      </span>
                    </div>
                    {lastExec && (
                      <span className="text-[10px] text-muted-foreground">
                        {formatTimestamp(lastExec)}
                      </span>
                    )}
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

/* ---- Executions Tab ---- */
function ExecutionsTab({
  executions,
  filterStatus,
  onFilterChange,
  onRefresh,
}: {
  executions: any[];
  filterStatus: string;
  onFilterChange: (status: string) => void;
  onRefresh: () => void;
}) {
  const hasRunning = executions.some(
    (e) => (e.status ?? "").toLowerCase() === "running"
  );

  const filtered = useMemo(() => {
    if (!filterStatus || filterStatus === "all") return executions;
    return executions.filter(
      (e) => (e.status ?? "").toLowerCase() === filterStatus
    );
  }, [executions, filterStatus]);

  if (executions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Activity className="w-8 h-8 text-muted-foreground/40 mb-3" />
        <p className="text-xs text-muted-foreground">
          No executions recorded yet.
        </p>
        <p className="text-[10px] text-muted-foreground/60 mt-1">
          Trigger a skill execution to see history here.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Status filter bar */}
      <div className="px-4 py-3 border-b border-[rgba(148,163,184,0.06)] flex items-center gap-2 flex-wrap">
        <Filter className="w-3 h-3 text-muted-foreground mr-1" />
        {["all", "completed", "running", "failed", "pending"].map((status) => {
          const count =
            status === "all"
              ? executions.length
              : executions.filter(
                  (e) => (e.status ?? "").toLowerCase() === status
                ).length;
          if (status !== "all" && count === 0) return null;
          const statusMeta = EXEC_STATUS_META[status];
          return (
            <button
              key={status}
              onClick={() => onFilterChange(status)}
              className={cn(
                "px-2.5 py-1 text-[10px] font-medium rounded-full border transition-all flex items-center gap-1.5",
                filterStatus === status || (!filterStatus && status === "all")
                  ? statusMeta
                    ? `${statusMeta.bg} ${statusMeta.border} ${statusMeta.color}`
                    : "bg-primary/10 text-primary border-primary/20"
                  : "text-muted-foreground hover:text-foreground border-transparent hover:bg-secondary/50"
              )}
            >
              {status === "all"
                ? `Wszystkie (${count})`
                : `${status.charAt(0).toUpperCase() + status.slice(1)} (${count})`}
            </button>
          );
        })}

        {/* Auto-refresh indicator */}
        {hasRunning && (
          <div className="ml-auto flex items-center gap-2">
            <span className="flex items-center gap-1 text-[10px] text-sylion-blue">
              <Loader2 className="w-3 h-3 animate-spin" />
              Auto-odświeżanie 10 s
            </span>
            <button
              onClick={onRefresh}
              className="p-1 rounded hover:bg-secondary/50 transition-colors"
              title="Refresh now"
            >
              <RotateCw className="w-3 h-3 text-muted-foreground" />
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow className="border-b border-[rgba(148,163,184,0.06)] hover:bg-transparent">
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Exec ID
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Skill
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Status
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground text-right">
              Duration
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Trigger
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground text-right">
              Timestamp
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((exec: any, idx: number) => {
            const status = (exec.status ?? "pending").toLowerCase();
            const meta =
              EXEC_STATUS_META[status] ?? EXEC_STATUS_META.pending;
            const StatusIcon =
              status === "running" ? Loader2 : meta.icon;
            const skillId = exec.skill_id ?? exec.skill ?? "--";
            const duration = exec.duration_ms ?? exec.duration ?? null;
            const trigger = exec.trigger ?? "auto";
            const triggerBadge = getTriggerBadge(trigger);

            return (
              <motion.tr
                key={exec.exec_id ?? exec.id ?? idx}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: idx * 0.02 }}
                className="border-b border-[rgba(148,163,184,0.04)] hover:bg-[rgba(47,107,255,0.04)] transition-colors"
              >
                <TableCell>
                  <span className="text-[11px] font-mono text-muted-foreground">
                    {(exec.exec_id ?? exec.id ?? "--").toString().slice(0, 12)}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Cpu className="w-3.5 h-3.5 text-primary shrink-0" />
                    <span className="text-xs font-medium text-foreground">
                      {exec.skill_name ?? skillId}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border",
                      meta.bg,
                      meta.border,
                      meta.color
                    )}
                  >
                    <StatusIcon
                      className={cn(
                        "w-2.5 h-2.5",
                        status === "running" && "animate-spin"
                      )}
                    />
                    {status.charAt(0).toUpperCase() + status.slice(1)}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <span className="text-[11px] font-medium text-foreground tabular-nums">
                    {formatDuration(duration)}
                  </span>
                </TableCell>
                <TableCell>
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border",
                      triggerBadge.color
                    )}
                  >
                    {triggerBadge.label}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <span className="text-[11px] text-muted-foreground">
                    {formatTimestamp(
                      exec.timestamp ?? exec.created_at ?? exec.completed_at
                    )}
                  </span>
                </TableCell>
              </motion.tr>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

/* ---- Demand Signals Tab ---- */
function DemandSignalsTab({ signals }: { signals: any[] }) {
  if (signals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Signal className="w-8 h-8 text-muted-foreground/40 mb-3" />
        <p className="text-xs text-muted-foreground">
          No demand signals detected.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
      {signals.map((sig: any, idx: number) => {
        const signalId = sig.signal_id ?? sig.id ?? `sig-${idx}`;
        const skillName = sig.skill_name ?? sig.skill_id ?? "--";
        const domain = sig.domain ?? "general";
        const strength = (sig.strength ?? sig.priority ?? "medium").toLowerCase();
        const strengthMeta =
          STRENGTH_META[strength] ?? STRENGTH_META.medium;
        const reason = sig.reason ?? sig.description ?? "";
        const priority = sig.priority ?? "P2 — Medium";
        const registered = sig.registered ?? true;

        return (
          <motion.div
            key={signalId}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: idx * 0.04 }}
          >
            <Card className="p-4 bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] hover:border-[rgba(148,163,184,0.12)] transition-all duration-200">
              {/* Header: strength indicator + domain */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {/* Signal strength bars */}
                  <div className="flex items-end gap-0.5">
                    {[1, 2, 3].map((bar) => (
                      <div
                        key={bar}
                        className={cn(
                          "w-1.5 rounded-sm",
                          bar <= strengthMeta.bars
                            ? cn("h-2", strengthMeta.color.replace("text-", "bg-"))
                            : "h-2 bg-muted-foreground/20"
                        )}
                      />
                    ))}
                  </div>
                  <span
                    className={cn(
                      "text-[10px] font-semibold uppercase tracking-wider",
                      strengthMeta.color
                    )}
                  >
                    {strengthMeta.label}
                  </span>
                </div>
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-medium border",
                    getDomainBadge(domain)
                  )}
                >
                  {domain}
                </span>
              </div>

              {/* Skill name */}
              <h4 className="text-sm font-semibold text-foreground mb-2">
                {skillName}
              </h4>

              {/* Reason */}
              {reason && (
                <p className="text-[10px] text-muted-foreground leading-relaxed mb-3">
                  {reason}
                </p>
              )}

              {/* Priority */}
              <div className="flex items-center gap-1.5 mb-3">
                <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                  Priority:
                </span>
                <span className="text-[10px] font-semibold text-foreground">
                  {priority}
                </span>
              </div>

              {/* Bottom: register button + timestamp */}
              <div className="flex items-center justify-between pt-2 border-t border-[rgba(148,163,184,0.06)]">
                {!registered ? (
                  <button className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-all">
                    <Plus className="w-3 h-3" />
                    Zarejestruj skill
                  </button>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-[10px] text-sylion-green">
                    <CheckCircle2 className="w-3 h-3" />
                    Registered
                  </span>
                )}
                <span className="text-[9px] text-muted-foreground">
                  {formatTimestamp(sig.timestamp ?? sig.created_at)}
                </span>
              </div>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}

/* ============================================================
   Main Page Component
   ============================================================ */

type TabKey = "skills" | "executions" | "demand";

export default function SkillsPage() {
  const { data: health } = useHealth();
  const { data: skillsData, refresh: refreshSkills } = useSkills();
  const { data: executionsData, refresh: refreshExecutions } = useSkillExecutions();
  const { data: demandData, refresh: refreshDemand } = useDemandSignals();

  const backendChecking = health?.status === "unknown";
  const backendLive = health?.status === "ok" || backendChecking;

  const [activeTab, setActiveTab] = useState<TabKey>("skills");
  const [filterCategory, setFilterCategory] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [skillName, setSkillName] = useState("Dashboard CRM Skill");
  const [skillDomain, setSkillDomain] = useState("crm");
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [skillPayloadText, setSkillPayloadText] = useState(
    '{\n  "source": "skills_dashboard",\n  "simulation": "manual_aeis_test",\n  "text": "Dashboard skills execution smoke test"\n}',
  );
  const [skillActionStatus, setSkillActionStatus] = useState("");
  const [skillActionBusy, setSkillActionBusy] = useState(false);

  /* Auto-refresh every 10s when running executions exist */
  const runningExecs = useMemo(() => {
    if (!backendLive) return [];
    return (executionsData.executions ?? []).filter(
      (e: any) => (e.status ?? "").toLowerCase() === "running"
    );
  }, [backendLive, executionsData]);

  useEffect(() => {
    if (runningExecs.length === 0) return;
    const interval = setInterval(() => {
      refreshExecutions();
    }, 10000);
    return () => clearInterval(interval);
  }, [runningExecs.length, refreshExecutions]);

  const handleRefresh = useCallback(() => {
    refreshExecutions();
    refreshSkills();
    refreshDemand();
  }, [refreshExecutions, refreshSkills, refreshDemand]);

  const refreshAllSkillsData = useCallback(() => {
    refreshSkills();
    refreshExecutions();
    refreshDemand();
  }, [refreshDemand, refreshExecutions, refreshSkills]);

  /* ---- Normalize data ---- */
  const liveSkills = skillsData.skills ?? [];
  const liveExecutions = executionsData.executions ?? [];
  const liveSignals = demandData.signals ?? [];

  const displaySkills = useMemo(() => {
    if (!backendLive) return [];
    return liveSkills.map((s: any) => ({
      skill_id: s.skill_id ?? s.id,
      name: s.name,
      description: s.description ?? "",
      domain: s.domain ?? s.category ?? "general",
      lifecycle: (s.lifecycle ?? "DRAFT").toUpperCase() as SkillLifecycle,
      execution_count: s.execution_count ?? s.usage_count ?? 0,
      success_rate: s.success_rate ?? 0,
      last_executed: s.last_executed ?? "",
    }));
  }, [backendLive, liveSkills]);

  const displayExecutions = useMemo(() => {
    if (!backendLive) return [];
    return liveExecutions;
  }, [backendLive, liveExecutions]);

  const displaySignals = useMemo(() => {
    if (!backendLive) return [];
    return liveSignals;
  }, [backendLive, liveSignals]);

  /* ---- Derived stats ---- */
  const totalExecutions = displayExecutions.length;
  const completedExecs = displayExecutions.filter(
    (e: any) => (e.status ?? "").toLowerCase() === "completed"
  );
  const failedExecs = displayExecutions.filter(
    (e: any) => (e.status ?? "").toLowerCase() === "failed"
  );
  const successRate =
    totalExecutions > 0
      ? Math.round((completedExecs.length / totalExecutions) * 100)
      : 0;

  const activeSignalCount = displaySignals.filter(
    (s: any) => (s.strength ?? "").toLowerCase() === "high" || (s.strength ?? "").toLowerCase() === "medium"
  ).length;

  const executableSkillId =
    (selectedSkillId && displaySkills.some((skill: any) => skill.skill_id === selectedSkillId)
      ? selectedSkillId
      : displaySkills[0]?.skill_id) ?? "seed_skill_001";

  const runSkillAction = useCallback(
    async (action: "create" | "execute" | "signal" | "analyze" | "lifecycle") => {
      if (!backendLive || skillActionBusy) return;
      setSkillActionBusy(true);
      setSkillActionStatus("");
      try {
        const domain = (skillDomain.trim() || "general").toLowerCase();
        if (action === "lifecycle") {
          const result = await api.runSkillLifecycleLongRunTest({
            project_id: "proj_dashboard_skill_lifecycle",
            domain,
            owner_role: "operator-dashboard",
            cycles: 2,
          });
          setSkillActionStatus(
            `Dlugi test lifecycle skills: ${result.passed ? "zaliczony" : "niezaliczony"} (${(result.skill_ids || []).join(", ")})`,
          );
          setActiveTab("skills");
        } else if (action === "create") {
          const base = skillName.trim() || "Dashboard Skill";
          const skillId = `dashboard_${domain}_${Date.now()}`;
          await api.registerSkill({
            skill_id: skillId,
            name: base,
            domain,
            owner_role: "operator",
            description: `Dashboard-created skill for ${domain} simulation`,
          });
          setSkillActionStatus(`Utworzono skill ${skillId}`);
          setActiveTab("skills");
        } else if (action === "execute") {
          let parsedPayload: Record<string, unknown>;
          try {
            parsedPayload = JSON.parse(skillPayloadText || "{}");
          } catch {
            throw new Error("Payload skill musi byc poprawnym JSON.");
          }
          const result = await api.executeSkill(executableSkillId, {
            source: "skills_dashboard",
            domain,
            ...parsedPayload,
          });
          const executionStatus = String(
            result?.status ?? result?.output_data?.result ?? "",
          ).toLowerCase();
          const executionError = String(
            result?.error ?? result?.output_data?.error ?? "",
          ).trim();
          if (executionStatus === "failed" || executionError) {
            throw new Error(
              `Wykonanie skill ${executableSkillId} nieudane: ${executionError || executionStatus}`,
            );
          }
          setSkillActionStatus(
            `Wykonano skill ${executableSkillId}: ${executionStatus || "completed"}`,
          );
          setActiveTab("executions");
        } else if (action === "signal") {
          await api.recordDemandSignal({
            signal_type: "missing_skill",
            source: "skills_dashboard",
            skill_id: `missing_${domain}_skill`,
            confidence: 0.9,
            details: { domain, reason: "manual_dashboard_test" },
          });
          setSkillActionStatus(`Zapisano sygnał popytu dla domeny ${domain}`);
          setActiveTab("demand");
        } else {
          await api.analyzeDemand();
          setSkillActionStatus("Uruchomiono analizę popytu");
          setActiveTab("demand");
        }
        refreshAllSkillsData();
      } catch (error) {
        setSkillActionStatus(
          error instanceof Error ? error.message : "Nie udało się wykonać akcji skills",
        );
      } finally {
        setSkillActionBusy(false);
      }
    },
    [
      backendLive,
      executableSkillId,
      refreshAllSkillsData,
      skillActionBusy,
      skillDomain,
      skillName,
      skillPayloadText,
    ],
  );

  return (
    <div className="space-y-5">
      {/* ====== BACKEND OFFLINE BANNER ====== */}
      {!backendLive && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Card className="p-4 bg-sylion-red/5 border border-sylion-red/20 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-sylion-red/10">
              <WifiOff className="w-4 h-4 text-sylion-red" />
            </div>
            <div>
              <p className="text-sm font-semibold text-sylion-red">
                Backend niedostępny
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Backend SYLION nie odpowiada. Uruchom backend, aby zobaczyć dane umiejętności na żywo.
              </p>
            </div>
          </Card>
        </motion.div>
      )}

      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Zap className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Umiejętności
              <HelpTip text="Rejestr umiejętności (skills) z cyklem życia DRAFT → TESTING → PUBLISHED → DEPRECATED. Liczone wykonania, success-rate i sygnały popytu (demand signals). Każda skill ma domenę i można ją wykonać manualnie lub automatycznie." />
            </h1>
            <p className="text-sm text-muted-foreground">
              Śledzenie wykonań i sygnały popytu
              {backendLive && (
                <Badge
                  variant="outline"
                  className="ml-2 text-[9px] border-sylion-green/30 text-sylion-green"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5" />
                  NA ŻYWO
                </Badge>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* ====== STATS ROW ====== */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Zarejestrowane umiejętności"
          value={displaySkills.length}
          icon={Layers}
          accent="text-primary"
          bgColor="bg-primary/10"
          sub={`${displaySkills.filter((s: any) => s.lifecycle === "PUBLISHED").length} opublikowanych`}
        />
        <StatCard
          label="Łącznie wykonań"
          value={totalExecutions}
          icon={BarChart3}
          accent="text-sylion-amber"
          bgColor="bg-sylion-amber/10"
          sub={`${completedExecs.length} zakończono, ${failedExecs.length} nieudane`}
        />
        <StatCard
          label="Wskaźnik sukcesu"
          value={`${successRate}%`}
          icon={CheckCircle2}
          accent="text-sylion-green"
          bgColor="bg-sylion-green/10"
          sub={`${completedExecs.length} z ${totalExecutions}`}
        />
        <StatCard
          label="Aktywne sygnały popytu"
          value={activeSignalCount}
          icon={Signal}
          accent="text-sylion-blue"
          bgColor="bg-sylion-blue/10"
          sub={`${displaySignals.length} łącznie sygnałów`}
        />
      </div>

      <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 flex-1">
            <label className="space-y-1">
              <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                Nazwa skill
              </span>
              <input
                value={skillName}
                onChange={(event) => setSkillName(event.target.value)}
                className="w-full rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                Domena
              </span>
              <input
                value={skillDomain}
                onChange={(event) => setSkillDomain(event.target.value)}
                className="w-full rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                Skill do wykonania
              </span>
              <select
                value={executableSkillId}
                onChange={(event) => setSelectedSkillId(event.target.value)}
                className="w-full rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
              >
                {displaySkills.length === 0 ? (
                  <option value="seed_skill_001">seed_skill_001</option>
                ) : (
                  displaySkills.map((skill: any) => (
                    <option key={skill.skill_id} value={skill.skill_id}>
                      {skill.skill_id}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="space-y-1 sm:col-span-2 lg:col-span-1">
              <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                Payload JSON
              </span>
              <textarea
                value={skillPayloadText}
                onChange={(event) => setSkillPayloadText(event.target.value)}
                className="min-h-20 w-full rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 font-mono text-[11px] text-foreground outline-none focus:border-primary/50"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!backendLive || skillActionBusy}
              onClick={() => runSkillAction("create")}
              className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-xs font-medium text-primary disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              Utwórz skill
            </button>
            <button
              type="button"
              disabled={!backendLive || skillActionBusy}
              onClick={() => runSkillAction("execute")}
              className="inline-flex items-center gap-1.5 rounded-md border border-sylion-green/20 bg-sylion-green/10 px-3 py-2 text-xs font-medium text-sylion-green disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              Wykonaj wybrana
            </button>
            <button
              type="button"
              disabled={!backendLive || skillActionBusy}
              onClick={() => runSkillAction("signal")}
              className="inline-flex items-center gap-1.5 rounded-md border border-sylion-amber/20 bg-sylion-amber/10 px-3 py-2 text-xs font-medium text-sylion-amber disabled:opacity-50"
            >
              <Signal className="w-3.5 h-3.5" />
              Zgłoś popyt
            </button>
            <button
              type="button"
              disabled={!backendLive || skillActionBusy}
              onClick={() => runSkillAction("analyze")}
              className="inline-flex items-center gap-1.5 rounded-md border border-[rgba(148,163,184,0.16)] bg-secondary/30 px-3 py-2 text-xs font-medium text-foreground disabled:opacity-50"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Analizuj popyt
            </button>
            <button
              type="button"
              disabled={!backendLive || skillActionBusy}
              onClick={() => runSkillAction("lifecycle")}
              className="inline-flex items-center gap-1.5 rounded-md border border-sylion-blue/20 bg-sylion-blue/10 px-3 py-2 text-xs font-medium text-sylion-blue disabled:opacity-50"
            >
              <Activity className="w-3.5 h-3.5" />
              Dlugi test lifecycle
            </button>
          </div>
        </div>
        {skillActionStatus && (
          <p className="mt-3 text-[11px] text-muted-foreground">{skillActionStatus}</p>
        )}
      </Card>

      {/* ====== TABS ====== */}
      <div className="flex items-center gap-2 border-b border-[rgba(148,163,184,0.06)] pb-0">
        <HelpTip text="Rejestr: katalog wszystkich umiejętności. Log wykonań: historia uruchomień. Sygnały popytu: brakujące umiejętności wykryte przez system." />
        <TabButton
          label="Rejestr umiejętności"
          icon={Cpu}
          active={activeTab === "skills"}
          count={displaySkills.length}
          onClick={() => setActiveTab("skills")}
        />
        <TabButton
          label="Log wykonań"
          icon={Play}
          active={activeTab === "executions"}
          count={totalExecutions}
          onClick={() => setActiveTab("executions")}
        />
        <TabButton
          label="Sygnały popytu"
          icon={Signal}
          active={activeTab === "demand"}
          count={displaySignals.length}
          onClick={() => setActiveTab("demand")}
        />
      </div>

      {/* ====== TAB CONTENT ====== */}
      <AnimatePresence mode="wait">
        {activeTab === "skills" && (
          <motion.div
            key="skills"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
          >
            <Card className="bg-[#0f1629] border border-[rgba(148,163,184,0.08)] overflow-hidden">
              <div className="px-4 pt-4 pb-2 flex items-center justify-between border-b border-[rgba(148,163,184,0.06)]">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-foreground">
                    Rejestr umiejętności
                    <HelpTip text="Katalog wszystkich umiejętności AEIS — z domeną, etapem cyklu życia, statystykami wykonań i success-rate." />
                  </h3>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                  {LIFECYCLE_STAGES.map((stage) => {
                    const meta = LIFECYCLE_META[stage];
                    const count = displaySkills.filter(
                      (s: any) => s.lifecycle === stage
                    ).length;
                    return (
                      <span key={stage} className="flex items-center gap-1">
                        <span className={cn("w-1.5 h-1.5 rounded-full", meta.bg)} />
                        {count} {meta.label}
                      </span>
                    );
                  })}
                </div>
              </div>
              <SkillsTab
                skills={displaySkills}
                filterCategory={filterCategory}
                onFilterChange={setFilterCategory}
              />
            </Card>
          </motion.div>
        )}

        {activeTab === "executions" && (
          <motion.div
            key="executions"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
          >
            <Card className="bg-[#0f1629] border border-[rgba(148,163,184,0.08)] overflow-hidden">
              <div className="px-4 pt-4 pb-2 flex items-center justify-between border-b border-[rgba(148,163,184,0.06)]">
                <div className="flex items-center gap-2">
                  <Play className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-foreground">
                    Log wykonań
                    <HelpTip text="Historia wszystkich wykonań umiejętności wraz ze statusem, czasem trwania i typem wyzwolenia (manual / auto / cascade)." />
                  </h3>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-sylion-green" />
                    {completedExecs.length}
                  </span>
                  <span className="flex items-center gap-1">
                    <XCircle className="w-3 h-3 text-sylion-red" />
                    {failedExecs.length}
                  </span>
                  <span>{totalExecutions} total</span>
                </div>
              </div>
              <ExecutionsTab
                executions={displayExecutions}
                filterStatus={filterStatus}
                onFilterChange={setFilterStatus}
                onRefresh={handleRefresh}
              />
            </Card>
          </motion.div>
        )}

        {activeTab === "demand" && (
          <motion.div
            key="demand"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
          >
            <Card className="bg-[#0f1629] border border-[rgba(148,163,184,0.08)] overflow-hidden">
              <div className="px-4 pt-4 pb-2 flex items-center justify-between border-b border-[rgba(148,163,184,0.06)]">
                <div className="flex items-center gap-2">
                  <Signal className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-foreground">
                    Sygnały popytu
                    <HelpTip text="Identyfikowane przez system braki umiejętności — które warto opracować lub kupić. Każdy sygnał ma siłę (high/medium/low), domenę i priorytet." />
                  </h3>
                </div>
                <span className="text-[10px] text-muted-foreground">
                  {displaySignals.length} sygnałów
                </span>
              </div>
              <DemandSignalsTab signals={displaySignals} />
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
