"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BackendErrorBanner } from "@/components/advisor/BackendErrorBanner";
import { useMonitoringSnapshot } from "@/lib/hooks/advisor";
import { useAdvisorFeed } from "@/lib/hooks/advisor";
import { useProjectLifecycle } from "@/lib/hooks/advisor";
import { useAdvisorMode } from "@/components/layout/useAdvisorMode";
import { cn } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CircleDollarSign,
  FolderKanban,
  RefreshCcw,
  Server,
  TrendingUp,
  LayoutDashboard,
  Terminal,
} from "lucide-react";
import { ProjectsMatrix } from "./_components/ProjectsMatrix";
import { RecommendationThroughput } from "./_components/RecommendationThroughput";
import { CostVsBudget } from "./_components/CostVsBudget";
import { CouncilActivityHeatmap } from "./_components/CouncilActivityHeatmap";
import { SubscriptionAdvisorBanner } from "./_components/SubscriptionAdvisorBanner";
import { AlertsBanner } from "./_components/AlertsBanner";
import { CockpitHero } from "@/components/dashboard/CockpitHero";
import { CockpitDecisionSection } from "@/components/dashboard/CockpitDecisionSection";
import { CockpitLifecycleStrip } from "@/components/dashboard/CockpitLifecycleStrip";
import { CockpitAgentFlow } from "@/components/dashboard/CockpitAgentFlow";
import { CockpitConfigStats } from "@/components/dashboard/CockpitConfigStats";
import { CockpitFAQWidget } from "@/components/dashboard/CockpitFAQWidget";
import { api } from "@/lib/api/client";

type RuntimeChecklistItem = {
  id: string;
  label: string;
  status: string;
};

type RuntimeW18Command = {
  id?: string;
  command?: string;
  source?: string;
  status?: string;
};

type RuntimeCapabilitiesData = {
  active_project_id?: string | null;
  checklist?: RuntimeChecklistItem[];
  capabilities?: {
    runtime_ready?: boolean;
    missing?: string[];
    session_backend?: {
      id?: string;
      label?: string;
    };
    docker_runtime?: {
      state?: string;
    };
  };
  live_spawn?: {
    running?: number;
    total?: number;
  };
  runtime_configuration?: {
    topology?: string;
    local_workers?: number;
    vps_workers?: number;
    environments?: number;
    max_parallel_workers?: number;
    max_monthly_vps_eur?: number;
    provisioning_state?: string;
  };
  w18_recent?: RuntimeW18Command[];
};

type RuntimeTruthData = {
  status?: "ok" | "warning" | "blocked" | string;
  checked_at?: number;
  api?: {
    pid?: number;
    port?: number;
    url?: string;
    cwd?: string;
    python?: string;
    platform?: string;
  };
  frontend?: {
    expected_url?: string;
    port_open?: boolean;
  };
  database?: {
    mode?: string;
    candidates?: string[];
  };
  git?: {
    root?: string;
    branch?: string;
    commit?: string;
    dirty?: boolean;
    dirty_entries?: number;
  };
  ports?: Array<{ port: number; label: string; open: boolean }>;
  warnings?: string[];
  blockers?: string[];
};

function RuntimeTruthCard({
  truth,
  error,
  onRefresh,
}: {
  truth: RuntimeTruthData | null;
  error: string | null;
  onRefresh: () => Promise<void> | void;
}) {
  const status = truth?.status ?? "loading";
  const statusClass =
    status === "ok"
      ? "border-[#40d987]/40 text-[#40d987]"
      : status === "blocked"
        ? "border-[#ff5f7a]/40 text-[#ff5f7a]"
        : "border-[#f6c177]/40 text-[#f6c177]";
  const ports = Array.isArray(truth?.ports) ? truth.ports : [];
  const warnings = Array.isArray(truth?.warnings) ? truth.warnings : [];
  const blockers = Array.isArray(truth?.blockers) ? truth.blockers : [];
  const dbCandidates = Array.isArray(truth?.database?.candidates) ? truth.database.candidates : [];

  return (
    <Card className="bg-[rgba(20,27,45,0.78)] p-4 ring-1 ring-[rgba(148,163,184,0.1)]" data-testid="runtime-truth-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#75a7ff]/10 ring-1 ring-[#75a7ff]/20">
            <Server className="h-4 w-4 text-[#75a7ff]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Runtime Truth</h3>
            <p className="mt-1 text-[11px] text-slate-500">
              Faktyczny backend, frontend, porty, baza i worktree używane przez ten dashboard.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={cn("text-[10px]", statusClass)}>
            {status === "loading" ? "sprawdźam" : status}
          </Badge>
          <button
            type="button"
            onClick={() => void onRefresh()}
            className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] text-slate-300 hover:border-[#75a7ff]/40 hover:text-[#75a7ff]"
          >
            Odśwież
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-3 rounded border border-[#ff5f7a]/25 bg-[#ff5f7a]/10 px-3 py-2 text-[11px] text-[#ff5f7a]">
          {error}
        </p>
      ) : null}

      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        <RuntimeFact label="API" value={`${truth?.api?.url ?? "-"} pid=${truth?.api?.pid ?? "-"}`} />
        <RuntimeFact label="Frontend" value={`${truth?.frontend?.expected_url ?? "-"} ${truth?.frontend?.port_open ? "open" : "closed"}`} />
        <RuntimeFact label="Baza" value={truth?.database?.mode ?? "-"} />
        <RuntimeFact label="Git" value={`${truth?.git?.branch ?? "-"} @ ${truth?.git?.commit ?? "-"}${truth?.git?.dirty ? " dirty" : ""}`} />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Porty lokalne</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ports.map((port) => (
              <span
                key={port.port}
                className={cn(
                  "rounded border px-2 py-1 text-[10px]",
                  port.open
                    ? "border-[#40d987]/25 bg-[#40d987]/10 text-[#40d987]"
                    : "border-white/10 bg-black/20 text-slate-500",
                )}
              >
                {port.port} {port.label}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Blokady i ostrze?enia</p>
          <div className="mt-2 space-y-1">
            {[...blockers.map((item) => `BLOCKER: ${item}`), ...warnings.map((item) => `WARN: ${item}`)].length === 0 ? (
              <p className="text-[11px] text-[#40d987]">Brak blokad runtime.</p>
            ) : (
              [...blockers.map((item) => `BLOCKER: ${item}`), ...warnings.map((item) => `WARN: ${item}`)].map((item) => (
                <p key={item} className="font-mono text-[10px] text-[#f6c177]">{item}</p>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Sciezki runtime</p>
        <p className="mt-1 break-all font-mono text-[10px] text-slate-400">cwd: {truth?.api?.cwd ?? "-"}</p>
        <p className="mt-1 break-all font-mono text-[10px] text-slate-500">
          db: {dbCandidates.length > 0 ? dbCandidates.slice(0, 3).join(" | ") : "brak wykrytego pliku lokalnego"}
        </p>
      </div>
    </Card>
  );
}

function RuntimeFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 break-all font-mono text-[10px] text-slate-300">{value}</p>
    </div>
  );
}

function RuntimeUpgradeStatusCard({
  data,
  projectId,
  onRefresh,
}: {
  data: RuntimeCapabilitiesData | null;
  projectId: string | null;
  onRefresh: () => Promise<void> | void;
}) {
  const [runtimeAction, setRuntimeAction] = useState<"start" | "stop" | "save" | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [runtimeForm, setRuntimeForm] = useState({
    topology: "local-first",
    local_workers: 2,
    vps_workers: 0,
    environments: 2,
    max_parallel_workers: 2,
    max_monthly_vps_eur: 0,
  });
  const checklist: RuntimeChecklistItem[] = Array.isArray(data?.checklist) ? data.checklist : [];
  const missing: string[] = Array.isArray(data?.capabilities?.missing) ? data.capabilities.missing : [];
  const sessionBackend = data?.capabilities?.session_backend;
  const dockerRuntime = data?.capabilities?.docker_runtime;
  const liveSpawn = data?.live_spawn;
  const runtimeConfig = useMemo(() => data?.runtime_configuration ?? {}, [data?.runtime_configuration]);
  const w18Recent: RuntimeW18Command[] = Array.isArray(data?.w18_recent) ? data.w18_recent : [];
  const effectiveProjectId = data?.active_project_id ?? projectId;
  const runningWorkers = Number(liveSpawn?.running ?? 0);
  const totalWorkers = Number(liveSpawn?.total ?? 0);
  const plannedWorkers = runtimeForm.local_workers + runtimeForm.vps_workers;
  const smokeTotalWorkers = runningWorkers > 0 ? totalWorkers || plannedWorkers : plannedWorkers;
  const hasRuntimeData = Boolean(data?.capabilities);
  const ready = hasRuntimeData && Boolean(data?.capabilities?.runtime_ready);
  const statusLabels: Record<string, string> = {
    ready: "gotowe",
    blocked: "blokada",
    planned: "planowane",
  };
  const missingLabels: Record<string, string> = {
    persistent_session_backend: "backend trwałych sesji",
    docker_daemon: "Docker Desktop / daemon",
    git: "Git",
  };

  useEffect(() => {
    if (!runtimeConfig || Object.keys(runtimeConfig).length === 0) return;
    const nextRuntimeForm = {
      topology: String(runtimeConfig.topology ?? "local-first"),
      local_workers: Number(runtimeConfig.local_workers ?? 2),
      vps_workers: Number(runtimeConfig.vps_workers ?? 0),
      environments: Number(runtimeConfig.environments ?? 2),
      max_parallel_workers: Number(runtimeConfig.max_parallel_workers ?? 2),
      max_monthly_vps_eur: Number(runtimeConfig.max_monthly_vps_eur ?? 0),
    };
    const timer = window.setTimeout(() => setRuntimeForm(nextRuntimeForm), 0);
    return () => window.clearTimeout(timer);
  }, [effectiveProjectId, runtimeConfig]);

  const setRuntimeNumber = (field: keyof typeof runtimeForm, value: string, min: number, max: number) => {
    const parsed = Number(value);
    const safe = Number.isFinite(parsed) ? Math.min(max, Math.max(min, Math.round(parsed))) : min;
    setRuntimeForm((current) => ({ ...current, [field]: safe }));
  };

  const saveRuntimeConfig = async () => {
    if (!effectiveProjectId || runtimeAction) return;
    const totalWorkers = runtimeForm.local_workers + runtimeForm.vps_workers;
    if (runtimeForm.max_parallel_workers < totalWorkers) {
      setRuntimeError("Limit r?wnoległosci musi byc co najmniej równy liczbie workerów lokalnych i VPS.");
      return;
    }
    setRuntimeAction("save");
    setRuntimeError(null);
    try {
      await api.updateExecutionRuntimeConfiguration(effectiveProjectId, {
        approved: true,
        operator_id: "operator",
        notes: "Konfiguracja runtime z dashboardu operatora",
        topology: runtimeForm.topology,
        local_workers: runtimeForm.local_workers,
        vps_workers: runtimeForm.vps_workers,
        environments: runtimeForm.environments,
        max_parallel_workers: runtimeForm.max_parallel_workers,
        max_monthly_vps_eur: runtimeForm.max_monthly_vps_eur,
        allow_paid_vps: false,
        apply_to_next_build: true,
      });
      await onRefresh();
    } catch (error) {
      setRuntimeError(error instanceof Error ? error.message : "Nie udało się zapisać konfiguracji runtime.");
    } finally {
      setRuntimeAction(null);
    }
  };

  const runSmokeWorkers = async () => {
    if (!effectiveProjectId || !ready || runtimeAction) return;
    setRuntimeAction("start");
    setRuntimeError(null);
    try {
      await api.liveSpawnExecutionWorkers(effectiveProjectId, {
        approved: true,
        operator_id: "operator",
        workers_limit: Math.min(8, Math.max(1, runtimeForm.local_workers + runtimeForm.vps_workers)),
        duration_seconds: 120,
        mode: "dashboard_smoke",
        allow_docker_run: false,
      });
      await onRefresh();
    } catch (error) {
      setRuntimeError(error instanceof Error ? error.message : "Nie udało się uruchomi? workerów smoke.");
    } finally {
      setRuntimeAction(null);
    }
  };

  const stopSmokeWorkers = async () => {
    if (!effectiveProjectId || runtimeAction) return;
    setRuntimeAction("stop");
    setRuntimeError(null);
    try {
      await api.stopExecutionLiveWorkers(effectiveProjectId, {
        approved: true,
        operator_id: "operator",
        notes: "Dashboard smoke stop",
      });
      await onRefresh();
    } catch (error) {
      setRuntimeError(error instanceof Error ? error.message : "Nie udało się zatrzyma? workerów smoke.");
    } finally {
      setRuntimeAction(null);
    }
  };

  return (
    <Card className="bg-[rgba(20,27,45,0.72)] p-4 ring-1 ring-[rgba(148,163,184,0.08)]" data-testid="runtime-upgrade-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">A1/A2/A3 + Profile 6 na Windows</h3>
          <p className="mt-1 text-[11px] text-slate-500">
            Trwałe sesje workerów, worktrees, Docker, Burst Mode, Build Critic i Prompt Splitting.
          </p>
          {sessionBackend?.label ? (
            <p className="mt-1 text-[11px] text-slate-400">
              Backend sesji: {sessionBackend.label}. Docker: {dockerRuntime?.state ?? "nie sprawdźono"}.
            </p>
          ) : null}
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            ready ? "border-[#40d987]/40 text-[#40d987]" : "border-[#f6c177]/40 text-[#f6c177]",
          )}
        >
          {!hasRuntimeData ? "sprawdźam runtime" : ready ? "runtime gotowy" : "wymaga runtime"}
        </Badge>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {checklist.map((item) => (
          <div key={item.id} className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-medium text-slate-300">{item.label}</span>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10px]",
                  item.status === "ready"
                    ? "bg-[#40d987]/10 text-[#40d987]"
                    : item.status === "blocked"
                      ? "bg-[#ff5f7a]/10 text-[#ff5f7a]"
                      : "bg-[#75a7ff]/10 text-[#75a7ff]",
                )}
              >
                {statusLabels[item.status] ?? item.status}
              </span>
            </div>
          </div>
        ))}
      </div>
      {hasRuntimeData ? (
        <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-3" data-testid="runtime-config-panel">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-[11px] font-medium text-slate-300">Konfiguracja runtime i środowisk</p>
              <p className="text-[10px] text-slate-500">
                Ustawia plan workerów, VPS i liczb? środowisk. Nie provisionuje Hetznera i nie generuje kosztu.
              </p>
            </div>
            <Badge variant="outline" className="border-[#75a7ff]/30 text-[10px] text-[#75a7ff]">
              {runtimeConfig?.provisioning_state ?? "plan lokalny"}
            </Badge>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
            <label className="space-y-1 text-[10px] text-slate-500">
              Topologia
              <select
                value={runtimeForm.topology}
                onChange={(event) => setRuntimeForm((current) => ({ ...current, topology: event.target.value }))}
                className="h-8 w-full rounded-md border border-white/10 bg-[#101827] px-2 text-[11px] text-slate-200 outline-none"
                data-testid="runtime-topology-select"
              >
                <option value="local-only">local-only</option>
                <option value="local-first">local-first</option>
                <option value="local-plus-vps">local + VPS</option>
                <option value="hybrid">hybrydowo</option>
              </select>
            </label>
            <label className="space-y-1 text-[10px] text-slate-500">
              Workery lokalne
              <input
                type="number"
                min={1}
                max={60}
                value={runtimeForm.local_workers}
                onChange={(event) => setRuntimeNumber("local_workers", event.target.value, 1, 60)}
                className="h-8 w-full rounded-md border border-white/10 bg-[#101827] px-2 text-[11px] text-slate-200 outline-none"
                data-testid="runtime-local-workers"
              />
            </label>
            <label className="space-y-1 text-[10px] text-slate-500">
              VPS planowane
              <input
                type="number"
                min={0}
                max={60}
                value={runtimeForm.vps_workers}
                onChange={(event) => setRuntimeNumber("vps_workers", event.target.value, 0, 60)}
                className="h-8 w-full rounded-md border border-white/10 bg-[#101827] px-2 text-[11px] text-slate-200 outline-none"
                data-testid="runtime-vps-workers"
              />
            </label>
            <label className="space-y-1 text-[10px] text-slate-500">
              środowiska
              <input
                type="number"
                min={1}
                max={8}
                value={runtimeForm.environments}
                onChange={(event) => setRuntimeNumber("environments", event.target.value, 1, 8)}
                className="h-8 w-full rounded-md border border-white/10 bg-[#101827] px-2 text-[11px] text-slate-200 outline-none"
                data-testid="runtime-environments"
              />
            </label>
            <label className="space-y-1 text-[10px] text-slate-500">
              Max r?wnolegle
              <input
                type="number"
                min={1}
                max={60}
                value={runtimeForm.max_parallel_workers}
                onChange={(event) => setRuntimeNumber("max_parallel_workers", event.target.value, 1, 60)}
                className="h-8 w-full rounded-md border border-white/10 bg-[#101827] px-2 text-[11px] text-slate-200 outline-none"
                data-testid="runtime-max-parallel"
              />
            </label>
            <label className="space-y-1 text-[10px] text-slate-500">
              Limit VPS EUR/m
              <input
                type="number"
                min={0}
                max={500}
                value={runtimeForm.max_monthly_vps_eur}
                onChange={(event) => setRuntimeNumber("max_monthly_vps_eur", event.target.value, 0, 500)}
                className="h-8 w-full rounded-md border border-white/10 bg-[#101827] px-2 text-[11px] text-slate-200 outline-none"
                data-testid="runtime-vps-budget"
              />
            </label>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] text-slate-500">
              Razem workerów: {runtimeForm.local_workers + runtimeForm.vps_workers}. Świeże potwierdzenie operatora nadal wymagane przed kosztem lub provisioningiem.
            </p>
            <button
              type="button"
              onClick={saveRuntimeConfig}
              disabled={!effectiveProjectId || runtimeAction !== null}
              className="rounded-md border border-[#75a7ff]/30 bg-[#75a7ff]/10 px-2.5 py-1 text-[10px] font-medium text-[#75a7ff] disabled:cursor-not-allowed disabled:opacity-40"
              data-testid="runtime-config-save"
            >
              {runtimeAction === "save" ? "Zapisuje..." : "Zastosuj runtime"}
            </button>
          </div>
        </div>
      ) : null}
      {hasRuntimeData ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
          <div>
            <p className="text-[11px] font-medium text-slate-300">Test workerów na żywo</p>
            <p className="text-[10px] text-slate-500">
              Uruchomione: {runningWorkers}/{smokeTotalWorkers}. Bez Docker run, bez Hetznera, bez kosztu zewnętrznego.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={runSmokeWorkers}
              disabled={!ready || !effectiveProjectId || runningWorkers > 0 || runtimeAction !== null}
              className="rounded-md border border-[#40d987]/30 bg-[#40d987]/10 px-2.5 py-1 text-[10px] font-medium text-[#40d987] disabled:cursor-not-allowed disabled:opacity-40"
              data-testid="runtime-live-spawn-start"
            >
              {runtimeAction === "start" ? "Uruchamiam..." : "Uruchom smoke"}
            </button>
            <button
              type="button"
              onClick={stopSmokeWorkers}
              disabled={!effectiveProjectId || runningWorkers === 0 || runtimeAction !== null}
              className="rounded-md border border-[#ff5f7a]/30 bg-[#ff5f7a]/10 px-2.5 py-1 text-[10px] font-medium text-[#ff5f7a] disabled:cursor-not-allowed disabled:opacity-40"
              data-testid="runtime-live-spawn-stop"
            >
              {runtimeAction === "stop" ? "Zatrzymuję..." : "Zatrzymaj"}
            </button>
          </div>
        </div>
      ) : null}
      {!hasRuntimeData ? (
        <p className="mt-3 text-[11px] text-[#75a7ff]">
          SprawdŹam lokalny runtime Windows i Docker daemon.
        </p>
      ) : missing.length > 0 ? (
        <p className="mt-3 text-[11px] text-[#f6c177]">
          Brakuje: {missing.map((item: string) => missingLabels[item] ?? item).join(", ")}. Live spawn zostaje zablokowany do decyzji operatora.
        </p>
      ) : (
        <p className="mt-3 text-[11px] text-[#40d987]">
          Runtime jest gotowy do bramki operatora; realny spawn nadal wymaga osobnego uruchomienia akcji.
        </p>
      )}
      {w18Recent.length > 0 ? (
        <div className="mt-3 rounded-lg border border-white/10 bg-black/20 px-3 py-2" data-testid="runtime-w18-recent">
          <p className="text-[11px] font-medium text-slate-300">Ostatnie komendy W18 z dashboardu</p>
          <div className="mt-2 space-y-1">
            {w18Recent.slice(-8).map((item) => (
              <div key={item.id ?? item.command} className="rounded border border-white/5 bg-white/[0.02] px-2 py-1">
                <p className="font-mono text-[10px] text-[#40d987]">{item.command}</p>
                <p className="text-[9px] text-slate-500">{item.source ?? "dashboard"} · {item.status ?? "accepted"}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {runtimeError ? <p className="mt-2 text-[11px] text-[#ff5f7a]">{runtimeError}</p> : null}
    </Card>
  );
}

export default function OperatorMonitoringDashboardPage() {
  const { snapshot, source: monSource, loading, refresh } = useMonitoringSnapshot(30_000);
  const { data: cards, source: cardSource, refresh: refreshCards } = useAdvisorFeed({ refreshMs: 8000 });
  const { mode, toggle } = useAdvisorMode();
  const [tab, setTab] = useState<string>("overview");
  const [runtimeCaps, setRuntimeCaps] = useState<RuntimeCapabilitiesData | null>(null);
  const [runtimeTruth, setRuntimeTruth] = useState<RuntimeTruthData | null>(null);
  const [runtimeTruthError, setRuntimeTruthError] = useState<string | null>(null);

  const runtimeActiveProjectId = runtimeCaps?.active_project_id ?? null;
  const featuredProjectId = snapshot.projects[0]?.project_id ?? runtimeActiveProjectId ?? null;
  const { lifecycle } = useProjectLifecycle(featuredProjectId);

  const stats = useMemo(() => {
    const projectCount = snapshot.projects.length;
    const effectiveProjectCount = projectCount || (runtimeActiveProjectId ? 1 : 0);
    const totalActiveCards = snapshot.projects.reduce((acc, p) => acc + p.active_cards, 0);
    const avgAcceptRate =
      projectCount > 0
        ? snapshot.projects.reduce((acc, p) => acc + p.accept_rate, 0) / projectCount
        : 0;
    const criticalAlerts = snapshot.alerts.filter((a) => a.severity === "critical").length;
    const usedPct =
      snapshot.cost_vs_budget.budget_usd > 0
        ? snapshot.cost_vs_budget.spend_usd / snapshot.cost_vs_budget.budget_usd
        : 0;
    return { projectCount: effectiveProjectCount, totalActiveCards, avgAcceptRate, criticalAlerts, usedPct };
  }, [snapshot, runtimeActiveProjectId]);

  const refreshRuntimeCaps = useCallback(async () => {
    try {
      setRuntimeCaps(await api.getExecutionRuntimeCapabilities());
    } catch {
      setRuntimeCaps(null);
    }
  }, []);

  const refreshRuntimeTruth = useCallback(async () => {
    try {
      setRuntimeTruthError(null);
      setRuntimeTruth(await api.getRuntimeTruth());
    } catch (error) {
      setRuntimeTruth(null);
      setRuntimeTruthError(error instanceof Error ? error.message : "Nie udało się pobrać Runtime Truth.");
    }
  }, []);

  const handleRefresh = useCallback(() => {
    refresh();
    refreshCards();
    void refreshRuntimeCaps();
    void refreshRuntimeTruth();
  }, [refresh, refreshCards, refreshRuntimeCaps, refreshRuntimeTruth]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshRuntimeCaps();
      void refreshRuntimeTruth();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshRuntimeCaps, refreshRuntimeTruth]);

  return (
    <div className="space-y-5" data-testid="operator-monitor-page">
      {/* Naglowek strony + przelacznik trybu */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/10 ring-1 ring-cyan-400/20">
              <Activity className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                {mode === "operator" ? "Kokpit operatora AEIS" : "Monitor operatora"}
              </h1>
              <p className="text-sm text-muted-foreground">
                {mode === "operator"
                  ? "Centrum prowadzenia projektów AI: decyzję, cykl ?ycia, modele i koszty"
                  : "Przegląd wielu projektów: przepustowość, koszt i aktywność Rady"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggle}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-white/20 hover:text-white"
            >
              {mode === "operator" ? (
                <>
                  <Terminal className="h-3.5 w-3.5" />
                  Tryb techniczny
                </>
              ) : (
                <>
                  <LayoutDashboard className="h-3.5 w-3.5" />
                  Tryb operatora
                </>
              )}
            </button>
            <Badge variant="outline" className="border-sylion-blue/30 text-[10px] text-sylion-blue">
              odświeżanie co 30 s
            </Badge>
            <button
              type="button"
              onClick={handleRefresh}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border border-[rgba(148,163,184,0.15)] bg-[rgba(20,27,45,0.6)] px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-sylion-blue/40 hover:text-sylion-blue",
                loading && "animate-pulse",
              )}
              aria-label="Odśwież snapshot"
            >
              <RefreshCcw className={cn("h-3 w-3", loading && "animate-spin")} />
              Odśwież
            </button>
          </div>
        </div>
      </motion.div>

      <BackendErrorBanner source={monSource} />

      {/* KPI strip — wspolne dla obu trybow */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.05 }}
        className="grid grid-cols-2 gap-3 lg:grid-cols-4"
        data-testid="headline-stats"
      >
        <KpiCard
          label="Aktywne projekty"
          value={stats.projectCount.toString()}
          accent="text-[#75a7ff]"
          icon={<FolderKanban className="h-4 w-4 text-[#75a7ff]" />}
        />
        <KpiCard
          label="Aktywne karty"
          value={(cards.length || stats.totalActiveCards).toString()}
          accent="text-[#f6c177]"
          icon={<TrendingUp className="h-4 w-4 text-[#f6c177]" />}
        />
        <KpiCard
          label="Sred. akceptacja"
          value={`${(stats.avgAcceptRate * 100).toFixed(0)}%`}
          accent="text-[#40d987]"
          icon={<CheckCircle2 className="h-4 w-4 text-[#40d987]" />}
        />
        <KpiCard
          label="Budzet wykorzystany"
          value={`${(stats.usedPct * 100).toFixed(0)}%`}
          accent={
            stats.usedPct >= 1
              ? "text-[#ff5f7a]"
              : stats.usedPct >= 0.85
                ? "text-[#f6c177]"
                : "text-[#75a7ff]"
          }
          icon={<CircleDollarSign className="h-4 w-4 text-[#f6c177]" />}
          accessory={
            stats.criticalAlerts > 0 ? (
              <span className="inline-flex items-center gap-1 text-[10px] text-[#ff5f7a]">
                <AlertTriangle className="h-3 w-3" />
                {stats.criticalAlerts} krytycznych
              </span>
            ) : null
          }
        />
      </motion.div>

      {/* Tryb operatora — Cockpit */}
      {mode === "operator" ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35 }}
          className="space-y-5"
        >
          {/* Banner subskrypcji (jesli sa rekomendacje) */}
          <SubscriptionAdvisorBanner recommendations={snapshot.subscription_recommendations } />

          {/* Hero: cockpit intro + dymek advisora */}
          <CockpitHero cards={cards} />

          {/* Sekcja decyzji */}
          <CockpitDecisionSection
            cards={cards}
            source={cardSource}
            onActionComplete={handleRefresh}
          />

          {/* Lifecycle wybranego projektu */}
          {lifecycle ? (
            <CockpitLifecycleStrip
              lifecycle={lifecycle}
              projectName={snapshot.projects[0]?.project_name}
              currentPhase={
                lifecycle.phases.filter((p) => p.status === "approved").length
              }
            />
          ) : null}

          {/* Przepływ agentów */}
          <CockpitAgentFlow />

          <RuntimeTruthCard truth={runtimeTruth} error={runtimeTruthError} onRefresh={refreshRuntimeTruth} />

          <RuntimeUpgradeStatusCard data={runtimeCaps} projectId={featuredProjectId} onRefresh={refreshRuntimeCaps} />

          {/* Dolna siatka: testy + Council */}
          <div className="grid gap-4 lg:grid-cols-2">
            <TestsStatusCard alerts={snapshot.alerts} />
            <CouncilSnapshotCard />
          </div>

          {/* Statystyki konfiguracji */}
          <CockpitConfigStats projectCount={stats.projectCount} />

          {/* FAQ */}
          <CockpitFAQWidget />
        </motion.div>
      ) : (
        /* Tryb techniczny — oryginalny widok z zakladkami */
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          <SubscriptionAdvisorBanner recommendations={snapshot.subscription_recommendations } />

          <Tabs value={tab} onValueChange={setTab} className="mt-4">
            <TabsList variant="line">
              <TabsTrigger value="overview">Przegląd</TabsTrigger>
              <TabsTrigger value="cost">Koszt i bud?et</TabsTrigger>
              <TabsTrigger value="activity">Aktywnosc Council</TabsTrigger>
              <TabsTrigger value="alerts">
                Alerty
                {snapshot.alerts.length > 0 ? (
                  <span className="ml-1 rounded bg-[#ff5f7a]/20 px-1 text-[9px] font-bold text-[#ff5f7a]">
                    {snapshot.alerts.length}
                  </span>
                ) : null}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <div className="space-y-4">
                <ProjectsMatrix
                  projects={snapshot.projects}
                  throughput={snapshot.throughput}
                  onSelectProject={(id) => {
                    if (typeof window !== "undefined") {
                      window.location.href = `/projects/${encodeURIComponent(id)}/lifecycle`;
                    }
                  }}
                />
                <div className="grid gap-4 lg:grid-cols-2">
                  <RecommendationThroughput data={snapshot.throughput} />
                  <AlertsBanner alerts={snapshot.alerts} />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="cost">
              <CostVsBudget cost={snapshot.cost_vs_budget} projects={snapshot.projects} />
            </TabsContent>

            <TabsContent value="activity">
              <div className="space-y-4">
                <CouncilActivityHeatmap data={snapshot.council_activity} />
                <RecommendationThroughput data={snapshot.throughput} />
              </div>
            </TabsContent>

            <TabsContent value="alerts">
              <AlertsBanner alerts={snapshot.alerts} />
            </TabsContent>
          </Tabs>

          <Card className="mt-4 bg-[rgba(20,27,45,0.6)] ring-1 ring-[rgba(148,163,184,0.06)]">
            <div className="flex items-center justify-between gap-3 px-4 py-2">
              <div>
                <p className="text-sm font-medium">Potrzebujesz glebszej analizy projektu?</p>
                <p className="text-[11px] text-muted-foreground">
                  Otworz dashboard lifecycle, aby sprawdźi? wszystkie 16 hookow Advisora.
                </p>
              </div>
              <a
                href="/dashboard"
                className="inline-flex items-center gap-1.5 rounded-md border border-sylion-blue/30 bg-sylion-blue/10 px-3 py-1.5 text-[11px] font-medium text-sylion-blue transition-colors hover:bg-sylion-blue/15"
                data-testid="link-lifecycle-dashboard"
              >
                Dashboard lifecycle
                <ArrowUpRight className="h-3 w-3" />
              </a>
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}

// ─── KPI card ────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  accent,
  icon,
  accessory,
}: {
  label: string;
  value: string;
  accent: string;
  icon: React.ReactNode;
  accessory?: React.ReactNode;
}) {
  return (
    <Card className="relative overflow-hidden bg-[#0f1629] ring-1 ring-[rgba(148,163,184,0.08)]">
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <p className={cn("text-2xl font-semibold tabular-nums", accent)}>{value}</p>
          {accessory ? <div className="mt-1">{accessory}</div> : null}
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(20,27,45,0.7)] ring-1 ring-[rgba(148,163,184,0.08)]">
          {icon}
        </div>
      </div>
    </Card>
  );
}

// ─── Testy i fixer ───────────────────────────────────────────────────────────

const TEST_ROWS = [
  { layer: "Security", status: "failed", next: "Fixer Team + sentinel retry", cls: "text-[#ff5f7a]" },
  { layer: "Golden", status: "passed", next: "bez akcji", cls: "text-[#40d987]" },
  { layer: "Symulacja głosowania", status: "passed", next: "bez akcji", cls: "text-[#40d987]" },
  { layer: "Lancuch audytu", status: "verified", next: "bez akcji", cls: "text-[#40d987]" },
];

function TestsStatusCard({ alerts }: { alerts: Array<{ id: string; severity: string; title: string }> }) {
  return (
    <div
      className="rounded-2xl border border-white/10 p-5"
      style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
    >
      <h3 className="mb-1 text-base font-bold text-white">Testy i fixer flow</h3>
      <p className="mb-4 text-[11px] text-slate-500">
        Nie wystarczy ładny status — operator widzi błędy, owner?w i plan poprawek.
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-slate-500">
            <th className="pb-2 text-left font-medium">Warstwa</th>
            <th className="pb-2 text-left font-medium">Status</th>
            <th className="pb-2 text-left font-medium">Co dalej</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.05]">
          {TEST_ROWS.map((r) => (
            <tr key={r.layer}>
              <td className="py-2 text-slate-200">{r.layer}</td>
              <td className={cn("py-2 font-mono text-[11px]", r.cls)}>{r.status}</td>
              <td className="py-2 text-[11px] text-slate-400">{r.next}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {alerts.length > 0 ? (
        <div className="mt-3 text-[11px] text-[#ff5f7a]">
          {alerts.length} aktywny{alerts.length > 1 ? "ch" : ""} alert
          {alerts.length > 1 ? "ow" : ""} — sprawdź alerty.
        </div>
      ) : null}
    </div>
  );
}

// ─── Council snapshot ────────────────────────────────────────────────────────

const COUNCIL_ROWS = [
  { role: "planner.primary", verdict: "accept", weight: "1.00", cls: "text-[#40d987]" },
  { role: "critic.primary", verdict: "accept + signed", weight: "1.00", cls: "text-[#40d987]" },
  { role: "cost_sentinel.support", verdict: "accept", weight: "0.35", cls: "text-[#40d987]" },
  { role: "security_sentinel.support", verdict: "reject", weight: "0.35", cls: "text-[#ff5f7a]" },
];

function CouncilSnapshotCard() {
  return (
    <div
      className="rounded-2xl border border-white/10 p-5"
      style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
    >
      <h3 className="mb-1 text-base font-bold text-white">Snapshot Council</h3>
      <p className="mb-4 text-[11px] text-slate-500">
        Wagi, bramka critic i sentinels widoczne operatorowi.
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-slate-500">
            <th className="pb-2 text-left font-medium">Rola</th>
            <th className="pb-2 text-left font-medium">Verdict</th>
            <th className="pb-2 text-left font-medium">Waga</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.05]">
          {COUNCIL_ROWS.map((r) => (
            <tr key={r.role}>
              <td className="py-2 font-mono text-[11px] text-slate-300">{r.role}</td>
              <td className={cn("py-2 text-[11px]", r.cls)}>{r.verdict}</td>
              <td className="py-2 font-mono text-[11px] text-slate-400">{r.weight}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3">
        <a href="/decisions" className="text-[11px] text-[#75a7ff] hover:underline">
          Pe?na historia głosowan Council →
        </a>
      </div>
    </div>
  );
}
