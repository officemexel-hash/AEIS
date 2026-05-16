import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { DecisionClass, ModuleLifecycle } from "@/lib/types";

/* ============================================================
   cn() — Merge Tailwind classes safely
   ============================================================ */

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/* ============================================================
   formatNumber — Compact human-readable numbers
   ============================================================ */

export function formatNumber(n: number): string {
  if (n >= 1_000_000_000) {
    return `${(n / 1_000_000_000).toFixed(1).replace(/\.0$/, "")}B`;
  }
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  }
  return n.toString();
}

/* ============================================================
   getLifecycleColor — Color per module lifecycle stage
   ============================================================ */

export function getLifecycleColor(stage: ModuleLifecycle): string {
  const map: Record<ModuleLifecycle, string> = {
    draft: "text-muted-foreground",
    build: "text-sylion-amber",
    validate: "text-sylion-blue",
    shadow: "text-purple-400",
    dual: "text-sylion-amber",
    cutover: "text-orange-400",
    stable: "text-sylion-green",
    deprecated: "text-sylion-red",
  };
  return map[stage] ?? "text-muted-foreground";
}

/* ============================================================
   getLifecycleBgColor — Background variant per module lifecycle
   ============================================================ */

export function getLifecycleBgColor(stage: ModuleLifecycle): string {
  const map: Record<ModuleLifecycle, string> = {
    draft: "bg-muted/50 text-muted-foreground",
    build: "bg-accent-amber-dim text-sylion-amber",
    validate: "bg-accent-blue-dim text-sylion-blue",
    shadow: "bg-purple-500/15 text-purple-400",
    dual: "bg-accent-amber-dim text-sylion-amber",
    cutover: "bg-orange-500/15 text-orange-400",
    stable: "bg-sylion-green/15 text-sylion-green",
    deprecated: "bg-sylion-red/15 text-sylion-red",
  };
  return map[stage] ?? "bg-muted/50 text-muted-foreground";
}

/* ============================================================
   getDecisionClassColor — Color per D0–D5
   ============================================================ */

export function getDecisionClassColor(d: DecisionClass): string {
  const map: Record<DecisionClass, string> = {
    D0: "text-sylion-green",
    D1: "text-sylion-blue",
    D2: "text-cyan-400",
    D3: "text-sylion-amber",
    D4: "text-orange-400",
    D5: "text-sylion-red",
  };
  return map[d] ?? "text-muted-foreground";
}

/* ============================================================
   getDecisionClassBgColor — Background variant per D0–D5
   ============================================================ */

export function getDecisionClassBgColor(d: DecisionClass): string {
  const map: Record<DecisionClass, string> = {
    D0: "bg-sylion-green/15 text-sylion-green",
    D1: "bg-accent-blue-dim text-sylion-blue",
    D2: "bg-cyan-500/15 text-cyan-400",
    D3: "bg-accent-amber-dim text-sylion-amber",
    D4: "bg-orange-500/15 text-orange-400",
    D5: "bg-sylion-red/15 text-sylion-red",
  };
  return map[d] ?? "bg-muted/50 text-muted-foreground";
}

/* ============================================================
   getRiskColor — Green / Amber / Red by risk level
   ============================================================ */

export function getRiskColor(
  risk: "none" | "low" | "medium" | "high" | "critical",
): string {
  const map: Record<string, string> = {
    none: "text-sylion-green",
    low: "text-sylion-green",
    medium: "text-sylion-amber",
    high: "text-orange-400",
    critical: "text-sylion-red",
  };
  return map[risk] ?? "text-muted-foreground";
}

export function getRiskBgColor(
  risk: "none" | "low" | "medium" | "high" | "critical",
): string {
  const map: Record<string, string> = {
    none: "bg-sylion-green/15 text-sylion-green",
    low: "bg-sylion-green/15 text-sylion-green",
    medium: "bg-accent-amber-dim text-sylion-amber",
    high: "bg-orange-500/15 text-orange-400",
    critical: "bg-sylion-red/15 text-sylion-red",
  };
  return map[risk] ?? "bg-muted/50 text-muted-foreground";
}

/* ============================================================
   getReadinessColor — Gradient based on 0–100 score
   ============================================================ */

export function getReadinessColor(score: number): string {
  if (score >= 90) return "text-sylion-green";
  if (score >= 75) return "text-emerald-400";
  if (score >= 60) return "text-sylion-blue";
  if (score >= 40) return "text-sylion-amber";
  if (score >= 20) return "text-orange-400";
  return "text-sylion-red";
}

export function getReadinessBgColor(score: number): string {
  if (score >= 90) return "bg-sylion-green/15 text-sylion-green";
  if (score >= 75) return "bg-emerald-500/15 text-emerald-400";
  if (score >= 60) return "bg-accent-blue-dim text-sylion-blue";
  if (score >= 40) return "bg-accent-amber-dim text-sylion-amber";
  if (score >= 20) return "bg-orange-500/15 text-orange-400";
  return "bg-sylion-red/15 text-sylion-red";
}

/* ============================================================
   getStatusColor — Agent / module status badge
   ============================================================ */

export function getStatusColor(
  status: "idle" | "active" | "busy" | "error" | "healthy" | "degraded" | "unhealthy" | "unknown",
): string {
  const map: Record<string, string> = {
    idle: "text-muted-foreground",
    active: "text-sylion-green",
    busy: "text-sylion-amber",
    error: "text-sylion-red",
    healthy: "text-sylion-green",
    degraded: "text-sylion-amber",
    unhealthy: "text-sylion-red",
    unknown: "text-muted-foreground",
  };
  return map[status] ?? "text-muted-foreground";
}

export function getStatusDotColor(
  status: "idle" | "active" | "busy" | "error" | "healthy" | "degraded" | "unhealthy" | "unknown",
): string {
  const map: Record<string, string> = {
    idle: "bg-muted-foreground",
    active: "bg-sylion-green",
    busy: "bg-sylion-amber",
    error: "bg-sylion-red",
    healthy: "bg-sylion-green",
    degraded: "bg-sylion-amber",
    unhealthy: "bg-sylion-red",
    unknown: "bg-muted-foreground",
  };
  return map[status] ?? "bg-muted-foreground";
}

/* ============================================================
   getSeverityColor — Alert severity badge
   ============================================================ */

export function getSeverityColor(
  severity: "info" | "warning" | "critical",
): string {
  const map: Record<string, string> = {
    info: "text-sylion-blue",
    warning: "text-sylion-amber",
    critical: "text-sylion-red",
  };
  return map[severity] ?? "text-muted-foreground";
}

export function getSeverityBgColor(
  severity: "info" | "warning" | "critical",
): string {
  const map: Record<string, string> = {
    info: "bg-accent-blue-dim text-sylion-blue",
    warning: "bg-accent-amber-dim text-sylion-amber",
    critical: "bg-sylion-red/15 text-sylion-red",
  };
  return map[severity] ?? "bg-muted/50 text-muted-foreground";
}

/* ============================================================
   getTrendIcon & getTrendColor — KPI trend indicators
   ============================================================ */

export function getTrendColor(trend: "up" | "down" | "stable"): string {
  if (trend === "up") return "text-sylion-green";
  if (trend === "down") return "text-sylion-amber";
  return "text-muted-foreground";
}

/* ============================================================
   getModuleClassColor — Color per module class A-O
   ============================================================ */

export function getModuleClassColor(cls: string): string {
  const map: Record<string, string> = {
    A: "text-sylion-blue",
    B: "text-indigo-400",
    C: "text-violet-400",
    D: "text-purple-400",
    E: "text-cyan-400",
    F: "text-sylion-green",
    G: "text-emerald-400",
    H: "text-teal-400",
    I: "text-sylion-amber",
    J: "text-orange-400",
    K: "text-yellow-400",
    L: "text-lime-400",
    M: "text-pink-400",
    N: "text-rose-400",
    O: "text-sky-400",
  };
  return map[cls] ?? "text-muted-foreground";
}

/* ============================================================
   getFidelityColor — 0–1 fidelity score
   ============================================================ */

export function getFidelityColor(fidelity: number): string {
  if (fidelity >= 0.99) return "text-sylion-green";
  if (fidelity >= 0.95) return "text-emerald-400";
  if (fidelity >= 0.90) return "text-sylion-blue";
  if (fidelity >= 0.80) return "text-sylion-amber";
  return "text-sylion-red";
}

/* ============================================================
   getMaturityColor — Idea maturity badge
   ============================================================ */

export function getMaturityColor(maturity: "raw" | "scoped" | "validated" | "promoted"): string {
  const map: Record<string, string> = {
    raw: "text-muted-foreground",
    scoped: "text-sylion-blue",
    validated: "text-sylion-amber",
    promoted: "text-sylion-green",
  };
  return map[maturity] ?? "text-muted-foreground";
}

export function getMaturityBgColor(maturity: "raw" | "scoped" | "validated" | "promoted"): string {
  const map: Record<string, string> = {
    raw: "bg-muted/50 text-muted-foreground",
    scoped: "bg-accent-blue-dim text-sylion-blue",
    validated: "bg-accent-amber-dim text-sylion-amber",
    promoted: "bg-sylion-green/15 text-sylion-green",
  };
  return map[maturity] ?? "bg-muted/50 text-muted-foreground";
}

/* ============================================================
   getSkillLifecycleColor — Skill lifecycle badge
   ============================================================ */

export function getSkillLifecycleColor(lifecycle: "DRAFT" | "TESTING" | "PUBLISHED" | "DEPRECATED"): string {
  const map: Record<string, string> = {
    DRAFT: "text-muted-foreground",
    TESTING: "text-sylion-amber",
    PUBLISHED: "text-sylion-green",
    DEPRECATED: "text-sylion-red",
  };
  return map[lifecycle] ?? "text-muted-foreground";
}

/* ============================================================
   getProgressColor — Progress bar color by percentage
   ============================================================ */

export function getProgressColor(progress: number): string {
  if (progress >= 90) return "bg-sylion-green";
  if (progress >= 70) return "bg-sylion-blue";
  if (progress >= 40) return "bg-sylion-amber";
  return "bg-sylion-red";
}

/* ============================================================
   Hydration-safe formatting (deterministic, no locale deps)
   ============================================================ */

function coerceDate(value: string | number | Date): Date {
  if (value instanceof Date) return value;
  if (typeof value === "number") {
    return new Date(Math.abs(value) < 10_000_000_000 ? value * 1000 : value);
  }
  const numeric = Number(value);
  if (value.trim() !== "" && Number.isFinite(numeric)) {
    return new Date(Math.abs(numeric) < 10_000_000_000 ? numeric * 1000 : numeric);
  }
  return new Date(value);
}

export function fmtDate(iso: string | number | Date): string {
  const d = coerceDate(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function fmtTime(iso: string | number | Date): string {
  const d = coerceDate(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function fmtDateTime(iso: string | number | Date): string {
  return `${fmtDate(iso)} ${fmtTime(iso)}`;
}

export function fmtNum(n: number): string {
  return n.toString();
}
