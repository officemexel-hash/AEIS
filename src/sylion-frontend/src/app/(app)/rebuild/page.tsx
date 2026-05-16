"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { useHealth, useRebuildPlans, useLPW, useCutoverPlans, useModules } from "@/lib/api/hooks";
import type {
  KPI,
  ModuleLifecycle,
  CFTRun,
  LPWCheckpoint,
  RebuildPlanStep,
} from "@/lib/types";
import {
  RefreshCw,
  ShieldCheck,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  Save,
  ArrowRight,
  ArrowLeftRight,
  GitBranch,
  Layers,
  RotateCcw,
  Activity,
  Box,
  FileCheck,
  Hash,
  ChevronDown,
  ChevronUp,
  Zap,
  Timer,
  CircleDot,
  Package,
} from "lucide-react";

/* ------------------------------------------------------------------
   LIFECYCLE STAGE CONFIG
   ------------------------------------------------------------------ */

const LIFECYCLE_STAGES: ModuleLifecycle[] = [
  "draft",
  "build",
  "validate",
  "shadow",
  "dual",
  "cutover",
  "stable",
  "deprecated",
];

const stageLabels: Record<ModuleLifecycle, string> = {
  draft: "Draft",
  build: "Build",
  validate: "Validate",
  shadow: "Shadow",
  dual: "Dual Run",
  cutover: "Cutover",
  stable: "Stable",
  deprecated: "Deprecated",
};

const stageColor: Record<ModuleLifecycle, string> = {
  draft: "border-muted-foreground/20 bg-muted-foreground/5",
  build: "border-sylion-amber/25 bg-sylion-amber/5",
  validate: "border-sylion-blue/25 bg-sylion-blue/5",
  shadow: "border-purple-400/25 bg-purple-400/5",
  dual: "border-sylion-amber/25 bg-sylion-amber/5",
  cutover: "border-orange-400/25 bg-orange-400/5",
  stable: "border-sylion-green/25 bg-sylion-green/5",
  deprecated: "border-sylion-red/25 bg-sylion-red/5",
};

const stageDotColor: Record<ModuleLifecycle, string> = {
  draft: "bg-muted-foreground",
  build: "bg-sylion-amber",
  validate: "bg-sylion-blue",
  shadow: "bg-purple-400",
  dual: "bg-sylion-amber",
  cutover: "bg-orange-400",
  stable: "bg-sylion-green",
  deprecated: "bg-sylion-red",
};

const stageTextColor: Record<ModuleLifecycle, string> = {
  draft: "text-muted-foreground",
  build: "text-sylion-amber",
  validate: "text-sylion-blue",
  shadow: "text-purple-400",
  dual: "text-sylion-amber",
  cutover: "text-orange-400",
  stable: "text-sylion-green",
  deprecated: "text-sylion-red",
};

/* ------------------------------------------------------------------
   TYPES (backend-shape mirrors for this view)
   ------------------------------------------------------------------ */

interface Bundle {
  id: string;
  modules: string[];
  state: "BUILDING" | "TESTING" | "PASSED" | "FAILED";
  validationResults: { module: string; passed: boolean; score: number }[];
}

interface CutoverItem {
  moduleId: string;
  currentStage: ModuleLifecycle;
  targetStage: ModuleLifecycle;
  validationStatus: "passed" | "pending" | "failed";
  lpwStatus: "ready" | "pending" | "captured";
  rollbackReady: boolean;
}

interface ShadowComparison {
  moduleId: string;
  metrics: Record<string, { shadow: number; live: number; unit: string }>;
  healthShadow: string;
  healthLive: string;
  perfDelta: string;
}

interface RollbackEvent {
  id: string;
  timestamp: string;
  module: string;
  reason: string;
  evidenceRef: string;
  result: "success" | "partial" | "failed";
}

/* ------------------------------------------------------------------
   STATUS HELPERS
   ------------------------------------------------------------------ */

const stepStatusIcon: Record<string, React.ElementType> = {
  completed: CheckCircle2,
  in_progress: RefreshCw,
  ready: Clock,
  blocked: AlertTriangle,
};

const stepStatusColor: Record<string, string> = {
  completed: "text-sylion-green",
  in_progress: "text-primary",
  ready: "text-muted-foreground",
  blocked: "text-sylion-red",
};

const stepStatusBg: Record<string, string> = {
  completed: "border-sylion-green/20 bg-sylion-green/3",
  in_progress: "border-primary/20 bg-primary/5",
  ready: "border-border/30 bg-muted/10",
  blocked: "border-sylion-red/20 bg-sylion-red/3",
};

const bundleStateBg: Record<string, string> = {
  BUILDING: "border-sylion-amber/25 bg-sylion-amber/5",
  TESTING: "border-sylion-blue/25 bg-sylion-blue/5",
  PASSED: "border-sylion-green/25 bg-sylion-green/5",
  FAILED: "border-sylion-red/25 bg-sylion-red/5",
};

const bundleStateBadge: Record<string, string> = {
  BUILDING: "border-sylion-amber/30 text-sylion-amber",
  TESTING: "border-sylion-blue/30 text-sylion-blue",
  PASSED: "border-sylion-green/30 text-sylion-green",
  FAILED: "border-sylion-red/30 text-sylion-red",
};

const validationBadge: Record<string, string> = {
  passed: "border-sylion-green/30 text-sylion-green",
  pending: "border-sylion-amber/30 text-sylion-amber",
  failed: "border-sylion-red/30 text-sylion-red",
};

const lpwBadge: Record<string, string> = {
  ready: "border-sylion-green/30 text-sylion-green",
  pending: "border-sylion-amber/30 text-sylion-amber",
  captured: "border-sylion-blue/30 text-sylion-blue",
};

const rollbackResultColor: Record<string, string> = {
  success: "text-sylion-green",
  partial: "text-sylion-amber",
  failed: "text-sylion-red",
};

const rollbackResultBadge: Record<string, string> = {
  success: "border-sylion-green/30 text-sylion-green",
  partial: "border-sylion-amber/30 text-sylion-amber",
  failed: "border-sylion-red/30 text-sylion-red",
};

const metricLabel: Record<string, string> = {
  latency_p50: "Latency P50",
  latency_p99: "Latency P99",
  throughput: "Throughput",
  failure_rate: "Failure Rate",
  error_rate: "Failure Rate",
  memory_mb: "Memory",
  cpu_pct: "CPU",
};

/* ------------------------------------------------------------------
   PAGE
   ------------------------------------------------------------------ */

export default function RebuildPage() {
  const { data: health } = useHealth();
  const { data: rebuildPlansData } = useRebuildPlans();
  const { data: lpwData } = useLPW();
  const { data: cutoverData } = useCutoverPlans();
  const { data: modulesData } = useModules();
  const [mounted, setMounted] = useState(false);
  const [expandedBundle, setExpandedBundle] = useState<string | null>("BND-002");
  const [selectedShadow, setSelectedShadow] = useState(true);

  useEffect(() => {
    setMounted(true);
  }, []);

  const backendLive = health.status === "ok";

  // Backend-only: modules list (prefers /modules, falls back to /rebuild/plans if the former is empty).
  const modules = useMemo(() => {
    if (!backendLive) return [];
    if ((modulesData?.modules ?? []).length > 0) {
      return (modulesData?.modules ?? []).map((m: any) => ({
        id: m.module_id ?? m.id ?? "",
        name: m.module_id ?? m.name ?? "",
        kind: m.module_kind ?? m.kind ?? m.class ?? "A",
        lifecycle: (m.lifecycle ?? m.stage ?? "draft") as ModuleLifecycle,
        contract_state: m.contract_state ?? "draft",
        risk: m.risk ?? "low",
      }));
    }
    if ((rebuildPlansData?.plans ?? []).length > 0) {
      return (rebuildPlansData?.plans ?? []).map((p: any) => ({
        id: p.plan_id ?? p.id ?? "",
        name: p.module_id ?? p.name ?? "",
        kind: p.module_kind ?? p.kind ?? "A",
        lifecycle: (p.lifecycle ?? p.stage ?? "draft") as ModuleLifecycle,
        contract_state: p.contract_state ?? "draft",
        risk: p.risk ?? "low",
      }));
    }
    return [];
  }, [backendLive, modulesData, rebuildPlansData]);

  const displayLPW: LPWCheckpoint[] = useMemo(() => {
    if (!backendLive) return [];
    return (lpwData?.entries ?? []).map((e: any) => ({
      id: e.id ?? e.checkpoint_id ?? "",
      hash: e.hash ?? e.golden_hash ?? "",
      valid: e.valid ?? true,
      module_count: e.module_count ?? 0,
      fidelity_score: e.fidelity_score ?? 0.95,
      created_at: e.created_at ?? e.timestamp ?? new Date().toISOString(),
    }));
  }, [backendLive, lpwData]);

  const displayCutoverQueue: CutoverItem[] = useMemo(() => {
    if (!backendLive) return [];
    return (cutoverData?.plans ?? []).map((p: any) => ({
      moduleId: p.module_id ?? p.moduleId ?? "",
      currentStage: (p.current_stage ?? p.currentStage ?? "validate") as ModuleLifecycle,
      targetStage: (p.target_stage ?? p.targetStage ?? "shadow") as ModuleLifecycle,
      validationStatus: p.validation_status ?? p.validationStatus ?? "pending",
      lpwStatus: p.lpw_status ?? p.lpwStatus ?? "pending",
      rollbackReady: p.rollback_ready ?? p.rollbackReady ?? false,
    }));
  }, [backendLive, cutoverData]);

  const displayRebuildSteps: RebuildPlanStep[] = useMemo(() => {
    if (!backendLive) return [];
    return (rebuildPlansData?.plans ?? []).map((p: any, idx: number) => ({
      seq: p.seq ?? idx + 1,
      module_name: p.module_id ?? p.module_name ?? p.name ?? "",
      package: p.package ?? p.module_id?.split(".")[0] ?? "",
      contract_version: p.contract_version ?? "1.0.0",
      dependencies: p.dependencies ?? [],
      status: p.status ?? "ready",
    }));
  }, [backendLive, rebuildPlansData]);

  const displayBundles: Bundle[] = useMemo(() => {
    if (!backendLive) return [];
    return (rebuildPlansData?.plans ?? [])
      .filter((p: any) => p.bundle_id || p.modules)
      .map((p: any) => ({
        id: p.bundle_id ?? p.plan_id ?? p.id ?? "",
        modules: p.modules ?? [p.module_id ?? p.module_name ?? ""].filter(Boolean),
        state: p.state ?? p.bundle_state ?? "BUILDING",
        validationResults: p.validation_results ?? p.modules?.map((m: string) => ({ module: m, passed: false, score: 0 })) ?? [],
      }));
  }, [backendLive, rebuildPlansData]);

  const displayCFTHistory: CFTRun[] = useMemo(() => {
    if (!backendLive) return [];
    return (lpwData?.entries ?? []).map((e: any, idx: number) => ({
      id: e.cft_run_id ?? e.id ?? `cft-${String(idx + 1).padStart(3, "0")}`,
      fidelity_score: e.fidelity_score ?? 0.95,
      timestamp: e.created_at ?? e.timestamp ?? new Date().toISOString(),
      passed: (e.fidelity_score ?? 0.95) >= 0.95,
      modules_tested: e.module_count ?? 0,
      duration_ms: e.duration_ms ?? 0,
    }));
  }, [backendLive, lpwData]);

  const displayStats = useMemo(() => {
    const latestLPW = displayLPW[0];
    return {
      cft_fidelity_score: latestLPW?.fidelity_score ?? 0,
      rebuild_history_count: displayCFTHistory.length,
      last_cft_run: displayCFTHistory[0]?.timestamp ?? null,
      modules_tracked: modules.length,
    };
  }, [displayLPW, displayCFTHistory, modules]);

  // Shadow comparison is null unless backend returns a plan that actually carries
  // shadow_metrics — empty state handled in the render.
  const displayShadowComparison: ShadowComparison | null = useMemo(() => {
    if (!backendLive) return null;
    const plans = cutoverData?.plans ?? [];
    const shadowPlan = plans.find(
      (p: any) => p.shadow_metrics || p.current_stage === "shadow" || p.metrics,
    );
    if (!shadowPlan) return null;
    const metrics = shadowPlan.shadow_metrics ?? shadowPlan.metrics ?? {};
    return {
      moduleId: shadowPlan.module_id ?? shadowPlan.moduleId ?? "unknown",
      metrics: Object.fromEntries(
        Object.entries(metrics)
          .filter(([k]) => k !== "health_shadow" && k !== "health_live" && k !== "perf_delta")
          .map(([k, v]: [string, any]) => [
            k,
            { shadow: v.shadow ?? v.new ?? 0, live: v.live ?? v.old ?? 0, unit: v.unit ?? "" },
          ]),
      ),
      healthShadow: metrics.health_shadow ?? metrics.healthShadow ?? "unknown",
      healthLive: metrics.health_live ?? metrics.healthLive ?? "unknown",
      perfDelta: metrics.perf_delta ?? metrics.perfDelta ?? "+0%",
    };
  }, [backendLive, cutoverData]);

  const displayRollbackHistory: RollbackEvent[] = useMemo(() => {
    if (!backendLive) return [];
    return (lpwData?.entries ?? [])
      .filter((e: any) => e.type === "rollback" || e.action === "rollback" || e.rollback)
      .map((e: any, idx: number) => ({
        id: e.id ?? `rb-${String(idx + 1).padStart(3, "0")}`,
        timestamp: e.created_at ?? e.timestamp ?? new Date().toISOString(),
        module: e.module_id ?? e.module ?? "",
        reason: e.reason ?? e.description ?? "",
        evidenceRef: e.evidence_ref ?? e.evidenceRef ?? `spine.seq#${e.seq ?? idx}`,
        result: e.result ?? "success",
      }));
  }, [backendLive, lpwData]);

  // Group modules by lifecycle stage
  const modulesByStage = LIFECYCLE_STAGES.reduce(
    (acc, stage) => {
      acc[stage] = modules.filter((m) => m.lifecycle === stage);
      return acc;
    },
    {} as Record<ModuleLifecycle, any[]>,
  );

  const activeRebuilds = displayRebuildSteps.filter(
    (s) => s.status === "in_progress",
  ).length;
  const pendingCutovers = displayCutoverQueue.filter(
    (c) => c.validationStatus === "pending" || c.validationStatus === "passed",
  ).length;
  const rollbackReady = displayCutoverQueue.filter((c) => c.rollbackReady).length;

  const fidelityScore = displayStats.cft_fidelity_score;

  const kpis: KPI[] = [
    {
      label: "Active Rebuilds",
      value: activeRebuilds,
      change: 1,
      trend: "up",
      icon: "RefreshCw",
    },
    {
      label: "Pending Cutovers",
      value: pendingCutovers,
      change: 2,
      trend: "up",
      icon: "ArrowRight",
    },
    {
      label: "Rollback Ready",
      value: rollbackReady,
      change: 0,
      trend: "stable",
      icon: "RotateCcw",
    },
    {
      label: "CFT Fidelity",
      value: `${(fidelityScore * 100).toFixed(1)}%`,
      change: 2,
      trend: "up",
      icon: "ShieldCheck",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Backend not reachable banner */}
      {!backendLive && (
        <div className="rounded-lg border border-sylion-amber/30 bg-sylion-amber/5 px-4 py-3 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-sylion-amber shrink-0" />
          <div>
            <p className="text-sm font-medium text-sylion-amber">Backend not reachable</p>
            <p className="text-xs text-muted-foreground">
              No live data available. Start the backend to populate this view.
            </p>
          </div>
        </div>
      )}
      {/* ============================================================
          SECTION 1: HEADER
          ============================================================ */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <GitBranch className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Rebuild &amp; Cutover
            </h1>
            <p className="text-sm text-muted-foreground">
              Module lifecycle transitions
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={cn(
              "text-[10px]",
              backendLive
                ? "border-sylion-green/30 text-sylion-green"
                : "border-border text-muted-foreground",
            )}
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full mr-1.5",
                backendLive ? "bg-sylion-green" : "bg-muted-foreground",
              )}
            />
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
          <Badge
            variant="outline"
            className={cn(
              "text-[10px] h-6",
              fidelityScore > 0.95
                ? "border-sylion-green/30 text-sylion-green"
                : "border-sylion-amber/30 text-sylion-amber",
            )}
          >
            <ShieldCheck className="w-3 h-3 mr-1" />
            Fidelity {(fidelityScore * 100).toFixed(1)}%
          </Badge>
          <button
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
            onClick={() => {}}
          >
            <Play className="w-3.5 h-3.5" />
            Run CFT
          </button>
          <button
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-border text-foreground text-xs font-medium hover:bg-accent transition-colors"
            onClick={() => {}}
          >
            <Save className="w-3.5 h-3.5" />
            LPW Checkpoint
          </button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-3">
        {kpis.map((kpi) => (
          <MetricCard key={kpi.label} kpi={kpi} />
        ))}
      </div>

      {/* ============================================================
          SECTION 2: MODULE LIFECYCLE GRID (Kanban)
          ============================================================ */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold">Module Lifecycle Grid</h2>
          <Badge variant="secondary" className="text-[10px]">
            {modules.length} modules
          </Badge>
        </div>
        <div className="grid grid-cols-8 gap-2">
          {LIFECYCLE_STAGES.map((stage) => (
            <div key={stage} className="space-y-2">
              {/* Column header */}
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2 py-1.5 rounded-md border text-[10px] font-semibold uppercase tracking-wider",
                  stageColor[stage],
                  stageTextColor[stage],
                )}
              >
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full shrink-0",
                    stageDotColor[stage],
                  )}
                />
                {stageLabels[stage]}
                <span className="ml-auto text-muted-foreground font-normal">
                  {modulesByStage[stage].length}
                </span>
              </div>
              {/* Module cards in this column */}
              <div className="space-y-1.5 min-h-[60px]">
                {modulesByStage[stage].map((mod) => (
                  <motion.div
                    key={mod.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={cn(
                      "p-2 rounded-md border text-xs transition-colors hover:border-primary/20 cursor-default",
                      stageColor[stage],
                    )}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <span
                        className={cn(
                          "inline-flex items-center justify-center w-4 h-4 rounded text-[8px] font-bold bg-muted/30",
                          stageTextColor[stage],
                        )}
                      >
                        {mod.kind}
                      </span>
                      <span
                        className={cn(
                          "font-medium truncate",
                          stageTextColor[stage],
                        )}
                      >
                        {mod.name.split(".").pop()}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[8px] h-3.5",
                          mod.contract_state === "frozen"
                            ? "border-sylion-green/30 text-sylion-green"
                            : mod.contract_state === "draft"
                              ? "border-sylion-amber/30 text-sylion-amber"
                              : "border-sylion-red/30 text-sylion-red",
                        )}
                      >
                        {mod.contract_state}
                      </Badge>
                      {mod.risk !== "low" && (
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[8px] h-3.5",
                            mod.risk === "medium"
                              ? "border-sylion-amber/30 text-sylion-amber"
                              : "border-sylion-red/30 text-sylion-red",
                          )}
                        >
                          {mod.risk}
                        </Badge>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ============================================================
          SECTION 3: BUNDLE STATUS
          ============================================================ */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Package className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold">Bundle Status</h2>
          <Badge variant="secondary" className="text-[10px]">
            {displayBundles.length} bundles
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {displayBundles.map((bundle) => {
            const isExpanded = expandedBundle === bundle.id;
            const Icon = isExpanded ? ChevronUp : ChevronDown;
            return (
              <Card
                key={bundle.id}
                className={cn(
                  "p-4 border transition-all card-hover",
                  bundleStateBg[bundle.state],
                )}
              >
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() =>
                    setExpandedBundle(isExpanded ? null : bundle.id)
                  }
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className="text-[9px] h-5 font-mono"
                    >
                      {bundle.id}
                    </Badge>
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[9px] h-5",
                        bundleStateBadge[bundle.state],
                      )}
                    >
                      {bundle.state}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {bundle.modules.length} modules
                    </span>
                  </div>
                  <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
                {/* Module pills */}
                <div className="flex flex-wrap gap-1 mt-2">
                  {bundle.modules.map((mod) => (
                    <span
                      key={mod}
                      className="text-[9px] px-1.5 py-0.5 rounded bg-muted/40 text-muted-foreground font-mono"
                    >
                      {mod.split(".").pop()}
                    </span>
                  ))}
                </div>
                {/* Expanded validation results */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-3 pt-3 border-t border-border/30 space-y-1.5">
                        <div className="grid grid-cols-[1fr_auto_auto] gap-2 text-[9px] text-muted-foreground uppercase tracking-wider px-1 pb-1">
                          <span>Module</span>
                          <span className="w-12 text-right">Score</span>
                          <span className="w-14 text-right">Result</span>
                        </div>
                        {bundle.validationResults.map((vr) => (
                          <div
                            key={vr.module}
                            className="grid grid-cols-[1fr_auto_auto] gap-2 items-center px-1 py-1.5 rounded hover:bg-muted/20 text-xs"
                          >
                            <span className="font-mono text-[11px] truncate">
                              {vr.module.split(".").pop()}
                            </span>
                            <span
                              className={cn(
                                "w-12 text-right font-semibold",
                                vr.score >= 0.95
                                  ? "text-sylion-green"
                                  : vr.score >= 0.85
                                    ? "text-sylion-amber"
                                    : vr.score > 0
                                      ? "text-sylion-red"
                                      : "text-muted-foreground",
                              )}
                            >
                              {vr.score > 0
                                ? `${(vr.score * 100).toFixed(0)}%`
                                : "--"}
                            </span>
                            {vr.passed ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-sylion-green justify-self-end" />
                            ) : (
                              <XCircle className="w-3.5 h-3.5 text-sylion-red justify-self-end" />
                            )}
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Card>
            );
          })}
        </div>
      </div>

      {/* ============================================================
          SECTION 4: CUTOVER QUEUE
          ============================================================ */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <ArrowRight className="w-4 h-4 text-orange-400" />
          <h2 className="text-sm font-semibold">Cutover Queue</h2>
          <Badge variant="secondary" className="text-[10px]">
            {displayCutoverQueue.length} pending
          </Badge>
        </div>
        <div className="rounded-lg border border-sylion-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/40 border-b border-sylion-border">
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  Module
                </th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  Current
                </th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  Target
                </th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  Validation
                </th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  LPW Status
                </th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  Rollback
                </th>
              </tr>
            </thead>
            <tbody>
              {displayCutoverQueue.map((item) => (
                <tr
                  key={item.moduleId}
                  className="border-b border-sylion-border/50 hover:bg-muted/20 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs">
                    {item.moduleId}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[9px] h-5",
                        stageTextColor[item.currentStage],
                      )}
                    >
                      {stageLabels[item.currentStage]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <ArrowRight className="w-3 h-3 text-muted-foreground" />
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[9px] h-5",
                          stageTextColor[item.targetStage],
                        )}
                      >
                        {stageLabels[item.targetStage]}
                      </Badge>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[9px] h-5",
                        validationBadge[item.validationStatus],
                      )}
                    >
                      {item.validationStatus === "passed" && (
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                      )}
                      {item.validationStatus === "failed" && (
                        <XCircle className="w-3 h-3 mr-1" />
                      )}
                      {item.validationStatus === "pending" && (
                        <Clock className="w-3 h-3 mr-1" />
                      )}
                      {item.validationStatus}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[9px] h-5",
                        lpwBadge[item.lpwStatus],
                      )}
                    >
                      {item.lpwStatus}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {item.rollbackReady ? (
                      <CheckCircle2 className="w-4 h-4 text-sylion-green" />
                    ) : (
                      <XCircle className="w-4 h-4 text-sylion-red/50" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ============================================================
          SECTION 5: SHADOW COMPARISON
          ============================================================ */}
      {displayShadowComparison ? (
      <div>
        <div className="flex items-center gap-2 mb-3">
          <ArrowLeftRight className="w-4 h-4 text-purple-400" />
          <h2 className="text-sm font-semibold">Shadow Comparison</h2>
          <Badge
            variant="outline"
            className="text-[9px] h-5 border-purple-400/30 text-purple-400"
          >
            {displayShadowComparison.moduleId}
          </Badge>
          <Badge
            variant="outline"
            className={cn(
              "text-[9px] h-5 ml-2",
              displayShadowComparison.perfDelta.startsWith("+")
                ? "border-sylion-green/30 text-sylion-green"
                : "border-sylion-red/30 text-sylion-red",
            )}
          >
            <Zap className="w-3 h-3 mr-1" />
            {displayShadowComparison.perfDelta}
          </Badge>
        </div>
        <Card className="p-4 bg-card border-sylion-border">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 text-xs">
            {/* Header row */}
            <div />
            <div className="w-28 text-center">
              <Badge
                variant="outline"
                className="text-[9px] h-5 border-purple-400/30 text-purple-400"
              >
                Shadow
              </Badge>
            </div>
            <div className="w-28 text-center">
              <Badge
                variant="outline"
                className="text-[9px] h-5 border-sylion-blue/30 text-sylion-blue"
              >
                Live
              </Badge>
            </div>
            <div className="w-24 text-center">
              <span className="text-[10px] text-muted-foreground uppercase">
                Delta
              </span>
            </div>
            {/* Metric rows */}
            {Object.entries(displayShadowComparison.metrics).map(
              ([key, val]: [string, any]) => {
                const delta =
                  val.live !== 0
                    ? (((val.shadow - val.live) / val.live) * 100).toFixed(1)
                    : "0";
                const isPositive = Number(delta) > 0;
                return (
                  <div
                    key={key}
                    className="contents"
                  >
                    <div className="flex items-center gap-2 py-2 border-b border-border/20">
                      <span className="text-muted-foreground text-[11px]">
                        {metricLabel[key] ?? key.replace(/_/g, " ")}
                      </span>
                      <span className="text-[9px] text-muted-foreground">
                        ({val.unit})
                      </span>
                    </div>
                    <div className="py-2 text-center border-b border-border/20">
                      <span className="font-mono text-[12px] font-medium">
                        {val.shadow}
                      </span>
                    </div>
                    <div className="py-2 text-center border-b border-border/20">
                      <span className="font-mono text-[12px] font-medium">
                        {val.live}
                      </span>
                    </div>
                    <div className="py-2 text-center border-b border-border/20">
                      <span
                        className={cn(
                          "font-mono text-[11px] font-medium",
                          isPositive
                            ? "text-sylion-green"
                            : Number(delta) < 0
                              ? "text-sylion-red"
                              : "text-muted-foreground",
                        )}
                      >
                        {isPositive ? "+" : ""}
                        {delta}%
                      </span>
                    </div>
                  </div>
                );
              },
            )}
            {/* Health row */}
            <div className="flex items-center gap-2 py-2">
              <span className="text-muted-foreground text-[11px]">
                Health Status
              </span>
            </div>
            <div className="py-2 text-center">
              <Badge
                variant="outline"
                className="text-[9px] h-5 border-sylion-green/30 text-sylion-green"
              >
                {displayShadowComparison.healthShadow}
              </Badge>
            </div>
            <div className="py-2 text-center">
              <Badge
                variant="outline"
                className="text-[9px] h-5 border-sylion-amber/30 text-sylion-amber"
              >
                {displayShadowComparison.healthLive}
              </Badge>
            </div>
            <div className="py-2 text-center">
              <span className="text-[10px] text-sylion-green font-medium">
                Improved
              </span>
            </div>
          </div>
        </Card>
      </div>
      ) : null}

      {/* ============================================================
          SECTION 6: ROLLBACK HISTORY
          ============================================================ */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <RotateCcw className="w-4 h-4 text-sylion-red" />
          <h2 className="text-sm font-semibold">Rollback History</h2>
          <Badge variant="secondary" className="text-[10px]">
            {displayRollbackHistory.length} events
          </Badge>
        </div>
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-[18px] top-3 bottom-3 w-px bg-border/40" />
          <div className="space-y-3">
            {displayRollbackHistory.map((event, idx) => {
              const RIcon =
                event.result === "success"
                  ? CheckCircle2
                  : event.result === "partial"
                    ? AlertTriangle
                    : XCircle;
              return (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2, delay: idx * 0.05 }}
                  className="relative flex items-start gap-4 pl-1"
                >
                  {/* Timeline dot */}
                  <div className="relative z-10 mt-1">
                    <RIcon
                      className={cn(
                        "w-4 h-4",
                        rollbackResultColor[event.result],
                      )}
                    />
                  </div>
                  {/* Content */}
                  <Card className="flex-1 p-3 bg-card border-sylion-border card-hover">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="text-[9px] h-4 font-mono"
                        >
                          {event.id}
                        </Badge>
                        <span className="text-xs font-medium font-mono">
                          {event.module}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="text-[8px] h-4"
                        >
                          <Hash className="w-2.5 h-2.5 mr-0.5" />
                          {event.evidenceRef}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[8px] h-4 capitalize",
                            rollbackResultBadge[event.result],
                          )}
                        >
                          {event.result}
                        </Badge>
                      </div>
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      {event.reason}
                    </p>
                    {mounted && (
                      <p className="text-[9px] text-muted-foreground mt-1">
                        {new Date(event.timestamp).toLocaleString()}
                      </p>
                    )}
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ============================================================
          SECTION 7: CFT RESULTS
          ============================================================ */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <FileCheck className="w-4 h-4 text-sylion-green" />
          <h2 className="text-sm font-semibold">CFT Results</h2>
          <Badge variant="secondary" className="text-[10px]">
            {displayCFTHistory.length} runs
          </Badge>
        </div>
        <div className="grid grid-cols-12 gap-4">
          {/* CFT History Table — 7 cols */}
          <Card className="col-span-7 p-4 bg-card border-sylion-border">
            <div className="rounded-lg border border-border/30 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/40 border-b border-border/30">
                    <th className="text-left px-3 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-medium">
                      Run
                    </th>
                    <th className="text-left px-3 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-medium">
                      Fidelity
                    </th>
                    <th className="text-left px-3 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-medium">
                      Modules
                    </th>
                    <th className="text-left px-3 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-medium">
                      Duration
                    </th>
                    <th className="text-left px-3 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-medium">
                      Pass Rate
                    </th>
                    <th className="text-left px-3 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-medium">
                      Result
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayCFTHistory.map((run) => (
                    <tr
                      key={run.id}
                      className={cn(
                        "border-b border-border/20 transition-colors",
                        run.passed
                          ? "hover:bg-muted/20"
                          : "bg-sylion-red/3 hover:bg-sylion-red/5",
                      )}
                    >
                      <td className="px-3 py-2.5 font-mono text-xs">
                        {run.id}
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className={cn(
                            "text-xs font-semibold",
                            run.fidelity_score >= 0.95
                              ? "text-sylion-green"
                              : run.fidelity_score >= 0.90
                                ? "text-sylion-amber"
                                : "text-sylion-red",
                          )}
                        >
                          {(run.fidelity_score * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">
                        {run.modules_tested}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">
                        {(run.duration_ms / 1000).toFixed(1)}s
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-secondary">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                run.fidelity_score >= 0.95
                                  ? "bg-sylion-green"
                                  : run.fidelity_score >= 0.90
                                    ? "bg-sylion-amber"
                                    : "bg-sylion-red",
                              )}
                              style={{
                                width: `${run.fidelity_score * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        {run.passed ? (
                          <CheckCircle2 className="w-4 h-4 text-sylion-green" />
                        ) : (
                          <XCircle className="w-4 h-4 text-sylion-red" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* LPW + Golden Hash — 5 cols */}
          <Card className="col-span-5 p-4 bg-card border-sylion-border">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">LPW Checkpoints</h3>
              <Badge variant="secondary" className="text-[10px]">
                {displayLPW.length}
              </Badge>
            </div>
            <div className="space-y-2">
              {displayLPW.map((cp) => (
                <div
                  key={cp.id}
                  className={cn(
                    "p-2.5 rounded-md border transition-colors",
                    cp.valid
                      ? "border-border/30 hover:bg-muted/20"
                      : "border-sylion-red/20 bg-sylion-red/3",
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge
                      variant="outline"
                      className="text-[9px] h-4 font-mono"
                    >
                      {cp.id}
                    </Badge>
                    {cp.valid ? (
                      <CheckCircle2 className="w-3 h-3 text-sylion-green shrink-0" />
                    ) : (
                      <XCircle className="w-3 h-3 text-sylion-red shrink-0" />
                    )}
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[8px] h-4 shrink-0",
                        cp.valid
                          ? "border-sylion-green/30 text-sylion-green"
                          : "border-sylion-red/30 text-sylion-red",
                      )}
                    >
                      {cp.valid ? "valid" : "invalid"}
                    </Badge>
                  </div>
                  {/* Golden vs Actual hash */}
                  <div className="space-y-0.5 mt-1.5">
                    <div className="flex items-center gap-1.5 text-[9px]">
                      <span className="text-muted-foreground w-12 shrink-0">
                        Golden:
                      </span>
                      <span className="font-mono text-muted-foreground truncate">
                        {cp.hash.slice(0, 20)}...
                        {cp.hash.slice(-8)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[9px]">
                      <span className="text-muted-foreground w-12 shrink-0">
                        Actual:
                      </span>
                      <span
                        className={cn(
                          "font-mono truncate",
                          cp.valid
                            ? "text-sylion-green"
                            : "text-sylion-red",
                        )}
                      >
                        {cp.valid
                          ? `${cp.hash.slice(0, 20)}...${cp.hash.slice(-8)}`
                          : "a4f8e2c1...5b1a7"}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-1.5 text-[10px]">
                    <span className="text-muted-foreground">
                      {cp.module_count} modules
                    </span>
                    <span
                      className={cn(
                        "font-medium",
                        cp.fidelity_score > 0.95
                          ? "text-sylion-green"
                          : "text-sylion-amber",
                      )}
                    >
                      {(cp.fidelity_score * 100).toFixed(1)}%
                    </span>
                    {mounted && (
                      <span className="text-muted-foreground">
                        {new Date(cp.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Fidelity Score Breakdown */}
            <div className="mt-4 pt-3 border-t border-border/30">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                Latest CFT Fidelity Breakdown
              </p>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded-md bg-sylion-green/5 border border-sylion-green/15">
                  <p className="text-lg font-semibold text-sylion-green">
                    {(fidelityScore * 100).toFixed(1)}%
                  </p>
                  <p className="text-[9px] text-muted-foreground">
                    Overall Score
                  </p>
                </div>
                <div className="p-2 rounded-md bg-muted/30 border border-border/30">
                  <p className="text-lg font-semibold">
                    {displayStats.modules_tracked}
                  </p>
                  <p className="text-[9px] text-muted-foreground">
                    Modules Tested
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
