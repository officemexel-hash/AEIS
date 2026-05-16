"use client";

import { useState, useMemo, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { cn, fmtNum } from "@/lib/utils";
import {
  useHealth,
  usePerfBudgets,
  useOverBudget,
  useConfigDrift,
  useCircuits,
  useCodeBloat,
  useModelLeaderboard,
  useModelSummaries,
} from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import {
  Gauge,
  ShieldCheck,
  AlertTriangle,
  Activity,
  CheckCircle2,
  XCircle,
  Minus,
  ArrowUpRight,
  Trophy,
  TrendingUp,
} from "lucide-react";
import { motion } from "framer-motion";
import { HelpTip } from "@/components/common/HelpTip";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type CircuitState = "closed" | "open" | "half-open";
type BudgetStatus = "within" | "warning" | "over";
type DriftSeverity = "none" | "low" | "medium" | "high" | "critical";

interface Circuit {
  name: string;
  state: CircuitState;
  failures: number;
  threshold: number;
  last_trip: string | null;
}

interface Budget {
  module_id: string;
  module_name: string;
  class: string;
  status: BudgetStatus;
  actual_lines: number;
  max_lines: number;
  actual_response_ms: number;
  max_response_ms: number;
  actual_memory_mb: number;
  max_memory_mb: number;
}

interface DriftEntry {
  module: string;
  expected: string;
  actual: string;
  drift_type: string;
  severity: DriftSeverity;
}

interface BloatModule {
  module: string;
  loc: number;
  budget_loc: number;
  complexity: number;
  unused_exports: number;
  duplication_pct: number;
}

/* ------------------------------------------------------------------ */
/*  All data sourced from backend API                                  */
/* ------------------------------------------------------------------ */

/* ---- Leaderboard types ---- */

type MetricType = "quality_score" | "response_time" | "error_rate" | "token_efficiency";

interface LeaderboardEntry {
  model_id: string;
  model_name: string;
  avg_quality_score: number;
  avg_response_time: number;
  request_count: number;
  best_task_type: string;
  worst_task_type: string;
  rank: number;
}

interface TrendPoint {
  timestamp: number;
  value: number;
}

const METRIC_OPTIONS: { value: MetricType; label: string }[] = [
  { value: "quality_score", label: "Wynik jakości" },
  { value: "response_time", label: "Czas odpowiedzi" },
  { value: "error_rate", label: "Wskaźnik błędów" },
  { value: "token_efficiency", label: "Efektywność tokenów" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CARD_STYLE = { backgroundColor: "#0f1629", borderColor: "rgba(148,163,184,0.08)" };

function circuitStateConfig(state: CircuitState) {
  switch (state) {
    case "closed":
      return {
        label: "ZAMKNIĘTY",
        color: "text-sylion-green",
        border: "border-sylion-green/30",
        bg: "bg-sylion-green/5 border-sylion-green/15",
        dot: "bg-sylion-green",
        badge: "border-sylion-green/30 text-sylion-green",
      };
    case "open":
      return {
        label: "OTWARTY",
        color: "text-sylion-red",
        border: "border-sylion-red/30",
        bg: "bg-sylion-red/5 border-sylion-red/20",
        dot: "bg-sylion-red",
        badge: "border-sylion-red/30 text-sylion-red",
      };
    case "half-open":
      return {
        label: "POŁ-OTWARTY",
        color: "text-sylion-amber",
        border: "border-sylion-amber/30",
        bg: "bg-sylion-amber/5 border-sylion-amber/20",
        dot: "bg-sylion-amber",
        badge: "border-sylion-amber/30 text-sylion-amber",
      };
  }
}

function budgetStatusConfig(status: BudgetStatus) {
  switch (status) {
    case "within":
      return { color: "text-sylion-green", badge: "border-sylion-green/30 text-sylion-green", bg: "bg-sylion-green", icon: CheckCircle2 };
    case "warning":
      return { color: "text-sylion-amber", badge: "border-sylion-amber/30 text-sylion-amber", bg: "bg-sylion-amber", icon: AlertTriangle };
    case "over":
      return { color: "text-sylion-red", badge: "border-sylion-red/30 text-sylion-red", bg: "bg-sylion-red", icon: XCircle };
  }
}

function driftSeverityConfig(severity: DriftSeverity) {
  switch (severity) {
    case "none":
      return { color: "text-sylion-green", badge: "border-sylion-green/30 text-sylion-green" };
    case "low":
      return { color: "text-sylion-blue", badge: "border-sylion-blue/30 text-sylion-blue" };
    case "medium":
      return { color: "text-sylion-amber", badge: "border-sylion-amber/30 text-sylion-amber" };
    case "high":
      return { color: "text-orange-400", badge: "border-orange-400/30 text-orange-400" };
    case "critical":
      return { color: "text-sylion-red", badge: "border-sylion-red/30 text-sylion-red" };
  }
}

function budgetUtil(b: Budget): number {
  const linePct = b.actual_lines / (b.max_lines || 1);
  const respPct = b.actual_response_ms / (b.max_response_ms || 1);
  const memPct = b.actual_memory_mb / (b.max_memory_mb || 1);
  return Math.round(Math.max(linePct, respPct, memPct) * 100);
}

/* ------------------------------------------------------------------ */
/*  Stat Card                                                          */
/* ------------------------------------------------------------------ */

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accentColor,
  index = 0,
  tip,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accentColor: string;
  index?: number;
  tip?: string;
}) {
  const bgMap: Record<string, string> = {
    green: "rgba(34,197,94,0.10)",
    amber: "rgba(245,158,11,0.10)",
    red: "rgba(239,68,68,0.10)",
    blue: "rgba(47,107,255,0.10)",
  };
  const iconColorMap: Record<string, string> = {
    green: "text-sylion-green",
    amber: "text-sylion-amber",
    red: "text-sylion-red",
    blue: "text-sylion-blue",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06 }}
      className="group relative overflow-hidden rounded-xl border transition-all duration-300 hover:scale-[1.015]"
      style={{
        background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.08)",
      }}
    >
      <div
        className="absolute top-0 left-[10%] right-[10%] h-px opacity-60"
        style={{
          background: `linear-gradient(90deg, transparent, ${bgMap[accentColor]?.replace("0.10", "0.5") ?? "transparent"}, transparent)`,
        }}
      />
      <div className="p-4 pb-3">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            {label}
            {tip && <HelpTip text={tip} />}
          </p>
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: bgMap[accentColor] ?? "rgba(148,163,184,0.10)" }}
          >
            <Icon className={cn("w-4 h-4", iconColorMap[accentColor] ?? "text-muted-foreground")} />
          </div>
        </div>
        <p className="text-3xl font-bold tracking-tight text-foreground mb-0.5">{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
      </div>
      <div
        className="h-[2px] mx-3 rounded-full opacity-50"
        style={{ background: "linear-gradient(90deg, transparent, currentColor, transparent)" }}
      />
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function PerformancePage() {
  const { data: apiHealth } = useHealth();
  const { data: budgetsData } = usePerfBudgets();
  const { data: overBudgetData } = useOverBudget();
  const { data: configDriftData } = useConfigDrift();
  const { data: circuitsData } = useCircuits();
  const { data: codeBloatData } = useCodeBloat();
  const backendLive = apiHealth.status === "ok";

  /* ---- Leaderboard state ---- */
  const [metricType, setMetricType] = useState<MetricType>("quality_score");
  const { data: leaderboardData } = useModelLeaderboard(metricType);
  const { data: summariesData } = useModelSummaries();
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [trendData, setTrendData] = useState<TrendPoint[]>([]);
  const [modelAnomalies, setModelAnomalies] = useState<Record<string, boolean>>({});

  const [activeTab, setActiveTab] = useState("circuits");

  /* ---- Data merge: live API ---- */

  const circuits: Circuit[] = useMemo(() => {
    const raw = circuitsData.circuits ?? [];
    if (raw.length > 0) {
      return raw.map((c: any) => ({
        name: c.name ?? c.circuit_name ?? "",
        state: (c.state ?? "closed") as CircuitState,
        failures: c.failures ?? c.failure_count ?? 0,
        threshold: c.threshold ?? 5,
        last_trip: c.last_trip ?? c.last_trip_at ?? null,
      }));
    }
    return [] as Circuit[];
  }, [circuitsData]);

  const budgets: Budget[] = useMemo(() => {
    const raw = budgetsData.budgets ?? [];
    if (raw.length > 0) {
      return raw.map((b: any) => ({
        module_id: b.module_id ?? b.id ?? "",
        module_name: b.module_name ?? b.name ?? "",
        class: b.class ?? "A",
        status: (b.status ?? "within") as BudgetStatus,
        actual_lines: b.actual_lines ?? 0,
        max_lines: b.max_lines ?? 0,
        actual_response_ms: b.actual_response_ms ?? 0,
        max_response_ms: b.max_response_ms ?? 0,
        actual_memory_mb: b.actual_memory_mb ?? 0,
        max_memory_mb: b.max_memory_mb ?? 0,
      }));
    }
    return [] as Budget[];
  }, [budgetsData]);

  const drift: DriftEntry[] = useMemo(() => {
    const raw = configDriftData.drift ?? [];
    if (raw.length > 0) {
      return raw.map((d: any) => ({
        module: d.module ?? d.module_name ?? "",
        expected: d.expected ?? d.expected_version ?? "",
        actual: d.actual ?? d.actual_version ?? "",
        drift_type: d.drift_type ?? "none",
        severity: (d.severity ?? "none") as DriftSeverity,
      }));
    }
    return [] as DriftEntry[];
  }, [configDriftData]);

  const bloat: BloatModule[] = useMemo(() => {
    const raw = codeBloatData.modules ?? [];
    if (raw.length > 0) {
      return raw.map((m: any) => ({
        module: m.module ?? m.module_name ?? "",
        loc: m.loc ?? m.lines ?? 0,
        budget_loc: m.budget_loc ?? m.budget_lines ?? 0,
        complexity: m.complexity ?? 0,
        unused_exports: m.unused_exports ?? 0,
        duplication_pct: m.duplication_pct ?? 0,
      }));
    }
    return [] as BloatModule[];
  }, [codeBloatData]);

  /* ---- Derived stats ---- */

  const circuitsHealthy = useMemo(
    () => circuits.filter((c) => c.state === "closed").length,
    [circuits]
  );

  const budgetCompliance = useMemo(() => {
    if (budgets.length === 0) return -1;
    const within = budgets.filter((b) => b.status === "within").length;
    return Math.round((within / budgets.length) * 100);
  }, [budgets]);

  const driftAlertCount = useMemo(
    () => drift.filter((d) => d.drift_type !== "none").length,
    [drift]
  );

  const bloatScore = useMemo(() => {
    if (bloat.length === 0) return 0;
    const totalOver = bloat.filter((m) => m.loc > m.budget_loc).length;
    return Math.round(((bloat.length - totalOver) / bloat.length) * 100);
  }, [bloat]);

  const maxBloatLoc = useMemo(
    () => Math.max(...bloat.map((m) => m.loc), 1),
    [bloat]
  );

  const overBudgetModules = useMemo(
    () => budgets.filter((b) => b.status === "over" || b.status === "warning"),
    [budgets]
  );

  /* ---- Leaderboard data merge ---- */
  const leaderboard: LeaderboardEntry[] = useMemo(() => {
    const raw = leaderboardData.leaderboard ?? [];
    if (raw.length > 0) {
      return raw.map((e: any, i: number) => ({
        model_id: e.model_id ?? e.id ?? "",
        model_name: e.model_name ?? e.name ?? e.model_id ?? "",
        avg_quality_score: e.avg_quality_score ?? e.quality_score ?? 0,
        avg_response_time: e.avg_response_time ?? e.response_time ?? 0,
        request_count: e.request_count ?? e.total_requests ?? 0,
        best_task_type: e.best_task_type ?? e.best_task ?? "",
        worst_task_type: e.worst_task_type ?? e.worst_task ?? "",
        rank: e.rank ?? i + 1,
      }));
    }
    return [] as LeaderboardEntry[];
  }, [leaderboardData]);

  /* ---- Model summaries for Budgets tab ---- */
  const modelSummaries = useMemo(() => {
    const raw = summariesData.summaries ?? [];
    if (raw.length === 0) return new Map<string, { avg_response_time: number; avg_quality_score: number }>();
    const map = new Map<string, { avg_response_time: number; avg_quality_score: number }>();
    for (const s of raw) {
      const id = s.model_id ?? s.id ?? "";
      if (id) map.set(id, { avg_response_time: s.avg_response_time ?? 0, avg_quality_score: s.avg_quality_score ?? 0 });
    }
    return map;
  }, [summariesData]);

  /* ---- Trend fetch on model select ---- */
  useEffect(() => {
    if (!selectedModelId) { setTrendData([]); return; }
    let cancelled = false;
    const fetchTrend = async () => {
      try {
        const res = await api.getModelTrend(selectedModelId, metricType, 24);
        if (!cancelled && res.trend?.length) {
          setTrendData(res.trend.map((p: any) => ({ timestamp: p.timestamp ?? p.time ?? 0, value: p.value ?? 0 })));
        } else if (!cancelled) {
          setTrendData([]);
        }
      } catch {
        if (!cancelled) setTrendData([]);
      }
    };
    fetchTrend();
    return () => { cancelled = true; };
  }, [selectedModelId, metricType]);

  /* ---- Anomaly detection for leaderboard models ---- */
  useEffect(() => {
    if (!backendLive || leaderboard.length === 0) return;
    let cancelled = false;
    const checkAnomalies = async () => {
      const result: Record<string, boolean> = {};
      await Promise.all(leaderboard.map(async (entry) => {
        try {
          const res = await api.detectAnomalies(entry.model_id);
          if (!cancelled) result[entry.model_id] = (res.anomalies?.length ?? 0) > 0;
        } catch { /* no anomaly info */ }
      }));
      if (!cancelled) setModelAnomalies(result);
    };
    checkAnomalies();
    return () => { cancelled = true; };
  }, [backendLive, leaderboard]);

  /* ---- Render ---- */

  return (
    <div className="space-y-5">
      {/* ---- Header ---- */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(47,107,255,0.10)", boxShadow: "0 0 16px rgba(47,107,255,0.25)" }}
          >
            <Gauge className="w-5 h-5 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Wydajność
              <HelpTip text="Centralny dashboard wydajności: przerywacze obwodów, budżety modułów, dryf konfiguracji, code bloat i leaderboard modeli. Czerwony badge = przekroczenia wymagające reakcji." />
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Przerywacze obwodów, budżety, dryf i code bloat
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={cn(
            "text-[10px]",
            overBudgetModules.length > 0 ? "border-sylion-amber/30 text-sylion-amber" : "border-sylion-green/30 text-sylion-green"
          )}>
            <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", overBudgetModules.length > 0 ? "bg-sylion-amber" : "bg-sylion-green")} />
            {overBudgetModules.length} przekroczeń budżetu
          </Badge>
          <Badge variant="outline" className={cn(
            "text-[10px]",
            backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red"
          )}>
            <span className={cn(
              "w-1.5 h-1.5 rounded-full mr-1.5",
              backendLive ? "bg-sylion-green animate-pulse" : "bg-sylion-red"
            )} />
            {backendLive ? "NA ŻYWO" : "OFFLINE"}
          </Badge>
        </div>
      </div>

      {/* ---- Backend Offline Warning ---- */}
      {!backendLive && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-sylion-red/[0.06] border border-sylion-red/15">
          <AlertTriangle className="w-3.5 h-3.5 text-sylion-red shrink-0" />
          <p className="text-[11px] text-sylion-red">Backend niedostępny — brak danych wydajności. Uruchom serwer backendu, aby się połączyć.</p>
        </div>
      )}

      {/* ---- Stats row ---- */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Sprawne przerywacze"
          tip="Liczba przerywaczy obwodów w stanie ZAMKNIĘTYM (sprawne). N/M = N sprawnych z M wszystkich. <100% wymaga sprawdźenia trippów."
          value={circuits.length > 0 ? `${circuitsHealthy}/${circuits.length}` : "---"}
          sub={circuits.length > 0 ? (circuitsHealthy === circuits.length ? "Wszystkie zamknięte" : `${circuits.length - circuitsHealthy} otwartych`) : "Brak danych"}
          icon={ShieldCheck}
          accentColor={circuits.length === 0 ? "blue" : circuitsHealthy === circuits.length ? "green" : "amber"}
          index={0}
        />
        <StatCard
          label="Zgodność z budżetem"
          tip="Procent modułów mieszczących się w limitach LOC/RAM/response_ms. >80% = zdrowy; 60-80% = monitoruj; <60% = wymaga refaktoringu."
          value={budgetCompliance >= 0 ? `${budgetCompliance}%` : "---"}
          sub={budgets.length > 0 ? `${budgets.filter((b) => b.status === "over").length} modułów po przekroczeniu` : "Brak danych"}
          icon={Gauge}
          accentColor={budgetCompliance < 0 ? "blue" : budgetCompliance >= 80 ? "green" : budgetCompliance >= 60 ? "amber" : "red"}
          index={1}
        />
        <StatCard
          label="Alerty dryfu"
          tip="Liczba modułów z dryfem konfiguracji (wersja oczekiwana ≠ rzeczywista). >0 wymaga sprawdźenia spójności."
          value={drift.length > 0 ? driftAlertCount : "---"}
          sub={drift.length > 0 ? `${drift.length} śledzonych modułów` : "Brak danych"}
          icon={AlertTriangle}
          accentColor={drift.length === 0 ? "blue" : driftAlertCount === 0 ? "green" : driftAlertCount <= 2 ? "amber" : "red"}
          index={2}
        />
        <StatCard
          label="Wynik code bloat"
          tip="Procent modułów mieszczących się w budżecie LOC. <80% = znaczne nadmiarowe linie; warto rozbić moduł lub usunąć dead code."
          value={bloat.length > 0 ? `${bloatScore}%` : "---"}
          sub={bloat.length === 0 ? "Brak danych" : bloatScore >= 80 ? "Czysty kod" : bloatScore >= 60 ? "Lekki nadmiar" : "Znaczny nadmiar"}
          icon={Activity}
          accentColor={bloatScore >= 80 ? "green" : bloatScore >= 60 ? "amber" : "red"}
          index={3}
        />
      </div>

      {/* ---- Tabs ---- */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex items-center gap-2">
          <TabsList>
            <TabsTrigger value="circuits">
              <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
              Przerywacze
            </TabsTrigger>
            <TabsTrigger value="budgets">
              <Gauge className="w-3.5 h-3.5 mr-1.5" />
              Budżety
            </TabsTrigger>
            <TabsTrigger value="drift">
              <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
              Dryf
            </TabsTrigger>
            <TabsTrigger value="bloat">
              <Activity className="w-3.5 h-3.5 mr-1.5" />
              Code bloat
            </TabsTrigger>
            <TabsTrigger value="leaderboard">
              <Trophy className="w-3.5 h-3.5 mr-1.5" />
              Ranking
            </TabsTrigger>
          </TabsList>
          <HelpTip text="Pięć perspektyw: Przerywacze (fault tolerance), Budżety (limity zasobów per moduł), Dryf (różnice konfiguracji), Code bloat (nadmiar linii), Ranking modeli LLM." />
        </div>

        {/* ============================================================ */}
        {/*  CIRCUITS TAB                                                 */}
        {/* ============================================================ */}
        <TabsContent value="circuits">
          <Card className="p-5" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">
                  Przerywacze obwodów
                  <HelpTip text="Mechanizm fault-tolerance — gdy moduł zewnętrzny (LLM/DB) wielokrotnie zawodzi, przerywacz przechodzi w OTWARTY i blokuje kolejne wywołania na recovery_timeout. Stan POŁ-OTWARTY = test czy serwis wrócił." />
                </h3>
                <Badge variant="secondary" className="text-[9px] h-4">
                  {circuits.length} obwodów
                </Badge>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-green" /> Zamknięty</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-amber" /> Poł-otwarty</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-red" /> Otwarty</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {circuits.map((c, i) => {
                const cfg = circuitStateConfig(c.state);
                const failurePct = Math.min((c.failures / (c.threshold || 1)) * 100, 100);
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.05 }}
                    className={cn("rounded-lg border p-4", cfg.bg)}
                  >
                    {/* Name + state badge */}
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-medium truncate pr-2">{c.name}</span>
                      <Badge variant="outline" className={cn("text-[8px] h-4 shrink-0", cfg.badge)}>
                        <span className={cn("w-1.5 h-1.5 rounded-full mr-1", cfg.dot)} />
                        {cfg.label}
                      </Badge>
                    </div>

                    {/* State indicator bar */}
                    <div className="mb-3">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] text-muted-foreground">Liczba awarii</span>
                        <span className="text-[10px] font-medium ml-auto">
                          <span className={cn(c.failures >= c.threshold ? "text-sylion-red font-semibold" : c.failures >= c.threshold * 0.5 ? "text-sylion-amber" : "text-foreground")}>
                            {c.failures}
                          </span>
                          <span className="text-muted-foreground">/{c.threshold}</span>
                        </span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-secondary">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-500",
                            c.failures >= c.threshold ? "bg-sylion-red" :
                            c.failures >= c.threshold * 0.5 ? "bg-sylion-amber" :
                            "bg-sylion-green"
                          )}
                          style={{ width: `${failurePct}%` }}
                        />
                      </div>
                    </div>

                    {/* Last trip time */}
                    <div className="text-[10px] text-muted-foreground">
                      {c.last_trip ? (
                        <span>Ostatni trip: {new Date(c.last_trip).toLocaleString()}</span>
                      ) : (
                        <span className="text-sylion-green/70">Brak zarejestrowanych trippów</span>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </TabsContent>

        {/* ============================================================ */}
        {/*  BUDGETS TAB                                                  */}
        {/* ============================================================ */}
        <TabsContent value="budgets">
          <Card className="p-5" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">
                  Budżety wydajności
                  <HelpTip text="Każdy moduł ma klasę (A/B/C) z limitami LOC, czasu odpowiedzi i RAM. Przekroczenie = ostrzeżenie w dashboardzie i blokada promotion. Cel: 100% within budget." />
                </h3>
                <Badge variant="secondary" className="text-[9px] h-4">
                  {budgets.length} modułów
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green">
                  {budgets.filter((b) => b.status === "within").length} w limicie
                </Badge>
                <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber">
                  {budgets.filter((b) => b.status === "warning").length} ostrzeżenie
                </Badge>
                <Badge variant="outline" className="text-[9px] border-sylion-red/30 text-sylion-red">
                  {budgets.filter((b) => b.status === "over").length} przekroczenie
                </Badge>
              </div>
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px]">Moduł</TableHead>
                  <TableHead className="text-[11px]">Klasa</TableHead>
                  <TableHead className="text-[11px] text-right">LOC</TableHead>
                  <TableHead className="text-[11px] text-right">Budżet</TableHead>
                  <TableHead className="text-[11px] text-right">Odpowiedź</TableHead>
                  <TableHead className="text-[11px] text-right">Limit odp.</TableHead>
                  <TableHead className="text-[11px] text-right">Pamięć</TableHead>
                  <TableHead className="text-[11px] text-right">Limit pam.</TableHead>
                  <TableHead className="text-[11px] text-right">Wykorzystanie</TableHead>
                  <TableHead className="text-[11px] text-center">Wydajność</TableHead>
                  <TableHead className="text-[11px] text-center">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {budgets.map((b) => {
                  const cfg = budgetStatusConfig(b.status);
                  const util = budgetUtil(b);
                  const StatusIcon = cfg.icon;
                  const perfData = modelSummaries.get(b.module_id);
                  return (
                    <TableRow key={b.module_id}>
                      <TableCell className="font-mono text-xs">{b.module_name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[9px] h-4 font-mono">{b.class}</Badge>
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        <span className={cn(b.actual_lines > b.max_lines && "text-sylion-red font-medium")}>
                          {fmtNum(b.actual_lines)}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">{fmtNum(b.max_lines)}</TableCell>
                      <TableCell className="text-right text-xs">
                        <span className={cn(b.actual_response_ms > b.max_response_ms && "text-sylion-red font-medium")}>
                          {b.actual_response_ms}ms
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">{b.max_response_ms}ms</TableCell>
                      <TableCell className="text-right text-xs">
                        <span className={cn(b.actual_memory_mb > b.max_memory_mb && "text-sylion-red font-medium")}>
                          {b.actual_memory_mb}MB
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">{b.max_memory_mb}MB</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center gap-2 justify-end">
                          <div className="w-16 h-1.5 rounded-full bg-secondary">
                            <div
                              className={cn("h-full rounded-full", cfg.bg)}
                              style={{ width: `${Math.min(util, 100)}%` }}
                            />
                          </div>
                          <span className={cn("text-[10px] font-medium w-8 text-right", cfg.color)}>
                            {util}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        {perfData ? (
                          <div className="flex flex-col items-center gap-0.5">
                            <span className="text-[10px] text-foreground">{perfData.avg_response_time}ms</span>
                            <span className={cn(
                              "text-[10px] font-medium",
                              perfData.avg_quality_score >= 0.9 ? "text-sylion-green" :
                              perfData.avg_quality_score >= 0.7 ? "text-sylion-amber" : "text-sylion-red"
                            )}>
                              {(perfData.avg_quality_score * 100).toFixed(0)}% jakości
                            </span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">--</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={cn("text-[8px] h-4", cfg.badge)}>
                          <StatusIcon className="w-3 h-3 mr-0.5" />
                          {b.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ============================================================ */}
        {/*  DRIFT TAB                                                    */}
        {/* ============================================================ */}
        <TabsContent value="drift">
          <Card className="p-5" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-sylion-amber" />
                <h3 className="text-sm font-semibold">
                  Dryf konfiguracji
                  <HelpTip text="Porównanie wersji oczekiwanej (manifest/lockfile) z rzeczywistą wersją w runtime. Dryf = potencjalne problemy bezpieczeństwa lub zgodności." />
                </h3>
                <Badge variant="secondary" className="text-[9px] h-4">
                  {driftAlertCount} dryfów / {drift.length} łącznie
                </Badge>
              </div>
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px]">Moduł</TableHead>
                  <TableHead className="text-[11px]">Oczekiwana</TableHead>
                  <TableHead className="text-[11px]">Rzeczywista</TableHead>
                  <TableHead className="text-[11px]">Delta</TableHead>
                  <TableHead className="text-[11px]">Typ dryfu</TableHead>
                  <TableHead className="text-[11px] text-center">Poziom</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drift.map((d, i) => {
                  const severityCfg = driftSeverityConfig(d.severity);
                  const hasDrift = d.drift_type !== "none";
                  return (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs">{d.module}</TableCell>
                      <TableCell className="text-xs text-muted-foreground font-mono">{d.expected}</TableCell>
                      <TableCell className={cn("text-xs font-mono", hasDrift ? severityCfg.color : "text-muted-foreground")}>
                        {d.actual}
                      </TableCell>
                      <TableCell className="text-xs">
                        {hasDrift ? (
                          <span className={cn("flex items-center gap-1", severityCfg.color)}>
                            <ArrowUpRight className="w-3 h-3" />
                            dryf
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-sylion-green">
                            <Minus className="w-3 h-3" />
                            zgodne
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn(
                          "text-[8px] h-4",
                          d.drift_type === "none"
                            ? "border-sylion-green/30 text-sylion-green"
                            : "border-sylion-amber/30 text-sylion-amber"
                        )}>
                          {d.drift_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={cn("text-[8px] h-4", severityCfg.badge)}>
                          {d.severity}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ============================================================ */}
        {/*  CODE BLOAT TAB                                               */}
        {/* ============================================================ */}
        <TabsContent value="bloat">
          <Card className="p-5" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">
                  Code bloat
                  <HelpTip text="Wskaźniki nadmiarowych linii kodu, złożoności cyklomatycznej, nieużywanych eksportów i duplikacji. Powyżej budżetu LOC = sygnał do refaktoringu lub podzielenia modułu." />
                </h3>
                <Badge variant="secondary" className="text-[9px] h-4">
                  {bloat.length} modułów
                </Badge>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-sylion-blue" /> W limicie
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-sylion-red" /> Po przekroczeniu
                </span>
              </div>
            </div>

            <div className="space-y-2">
              {bloat.map((m, i) => {
                const isOver = m.loc > m.budget_loc;
                const widthPct = Math.round((m.loc / maxBloatLoc) * 100);
                const budgetPct = Math.round((m.budget_loc / maxBloatLoc) * 100);
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25, delay: i * 0.03 }}
                    className={cn(
                      "rounded-lg border p-3",
                      isOver ? "bg-sylion-red/5 border-sylion-red/15" : "bg-transparent border-transparent"
                    )}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-medium">{m.module}</span>
                        {isOver && (
                          <Badge variant="outline" className="text-[8px] h-3.5 border-sylion-red/30 text-sylion-red">
                            NADMIAR
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-[10px]">
                        <span className="text-muted-foreground">
                          Złożoność: <span className={cn("font-medium", m.complexity > 200 ? "text-sylion-amber" : "text-foreground")}>{m.complexity}</span>
                        </span>
                        <span className="text-muted-foreground">
                          Nieużywane: <span className={cn("font-medium", m.unused_exports > 10 ? "text-sylion-amber" : "text-foreground")}>{m.unused_exports}</span>
                        </span>
                        <span className="text-muted-foreground">
                          Dup.: <span className={cn("font-medium", m.duplication_pct > 5 ? "text-sylion-amber" : "text-foreground")}>{m.duplication_pct}%</span>
                        </span>
                        <span className={cn("font-medium text-xs", isOver ? "text-sylion-red" : "text-foreground")}>
                          {fmtNum(m.loc)} <span className="text-muted-foreground font-normal">/ {fmtNum(m.budget_loc)} LOC</span>
                        </span>
                      </div>
                    </div>
                    {/* Size bar */}
                    <div className="relative w-full h-2 rounded-full bg-secondary">
                      {/* Budget marker */}
                      <div
                        className="absolute top-0 h-full border-r border-dashed border-muted-foreground/40"
                        style={{ left: `${budgetPct}%` }}
                      />
                      {/* Actual bar */}
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-500",
                          isOver ? "bg-sylion-red" : "bg-sylion-blue"
                        )}
                        style={{ width: `${Math.min(widthPct, 100)}%` }}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </TabsContent>

        {/* ============================================================ */}
        {/*  MODEL LEADERBOARD TAB                                        */}
        {/* ============================================================ */}
        <TabsContent value="leaderboard">
          <div className="space-y-4">
            {/* Leaderboard table */}
            <Card className="p-5" style={CARD_STYLE}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Trophy className="w-4 h-4 text-sylion-amber" />
                  <h3 className="text-sm font-semibold">
                    Ranking modeli
                    <HelpTip text="Porównanie wszystkich modeli LLM po wybranej metryce. Pierwsze 3 miejsca = preferowane do nowych zadań; czerwona kropka = wykryta anomalia." />
                  </h3>
                  <Badge variant="secondary" className="text-[9px] h-4">
                    {leaderboard.length} modeli
                  </Badge>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-muted-foreground">
                    Metryka
                    <HelpTip text="Wybór kryterium rankingu — quality score (jakość odpowiedzi), response time (latencja), error rate (% nieudanych) lub token efficiency (koszt vs jakość)." />
                  </span>
                  <select
                    value={metricType}
                    onChange={(e) => setMetricType(e.target.value as MetricType)}
                    className="h-7 rounded-md border border-border bg-background px-2 text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    {METRIC_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-green" /> Normalny</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-red" /> Anomalia</span>
                  </div>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-[11px] w-12 text-center">Pozycja</TableHead>
                    <TableHead className="text-[11px]">Model</TableHead>
                    <TableHead className="text-[11px]">Wynik jakości</TableHead>
                    <TableHead className="text-[11px] text-right">Śr. czas odp.</TableHead>
                    <TableHead className="text-[11px] text-right">Żądania</TableHead>
                    <TableHead className="text-[11px]">Najlepsze zada?ie</TableHead>
                    <TableHead className="text-[11px]">Najgorsze zada?ie</TableHead>
                    <TableHead className="text-[11px] text-center">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leaderboard.map((entry) => {
                    const isSelected = selectedModelId === entry.model_id;
                    const hasAnomaly = modelAnomalies[entry.model_id] ?? false;
                    const qualityPct = Math.round(entry.avg_quality_score * 100);
                    return (
                      <TableRow
                        key={entry.model_id}
                        className={cn(
                          "cursor-pointer transition-colors",
                          isSelected && "bg-sylion-blue/5"
                        )}
                        onClick={() => setSelectedModelId(isSelected ? null : entry.model_id)}
                      >
                        <TableCell className="text-center">
                          <span className={cn(
                            "inline-flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold",
                            entry.rank === 1 ? "bg-yellow-500/15 text-yellow-400" :
                            entry.rank === 2 ? "bg-gray-400/15 text-gray-300" :
                            entry.rank === 3 ? "bg-orange-500/15 text-orange-400" :
                            "bg-secondary text-muted-foreground"
                          )}>
                            {entry.rank}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-xs">{entry.model_name}</span>
                            {hasAnomaly && (
                              <span className="w-2 h-2 rounded-full bg-sylion-red animate-pulse" title="Wykryto anomalię" />
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-1.5 rounded-full bg-secondary">
                              <div
                                className={cn(
                                  "h-full rounded-full",
                                  qualityPct >= 90 ? "bg-sylion-green" :
                                  qualityPct >= 70 ? "bg-sylion-amber" : "bg-sylion-red"
                                )}
                                style={{ width: `${qualityPct}%` }}
                              />
                            </div>
                            <span className={cn(
                              "text-[10px] font-medium w-8 text-right",
                              qualityPct >= 90 ? "text-sylion-green" :
                              qualityPct >= 70 ? "text-sylion-amber" : "text-sylion-red"
                            )}>
                              {qualityPct}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right text-xs">
                          <span className={cn(
                            entry.avg_response_time < 1000 ? "text-sylion-green" :
                            entry.avg_response_time < 1500 ? "text-sylion-amber" : "text-sylion-red"
                          )}>
                            {entry.avg_response_time}ms
                          </span>
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground">
                          {fmtNum(entry.request_count)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[8px] h-4 border-sylion-green/30 text-sylion-green">
                            {entry.best_task_type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[8px] h-4 border-sylion-red/30 text-sylion-red">
                            {entry.worst_task_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-center">
                          {isSelected ? (
                            <Badge variant="outline" className="text-[8px] h-4 border-sylion-blue/30 text-sylion-blue">
                              <TrendingUp className="w-3 h-3 mr-0.5" />
                              podgląd
                            </Badge>
                          ) : (
                            <span className="text-[10px] text-muted-foreground">kliknij, aby zobaczyć</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </Card>

            {/* Trend chart for selected model */}
            {selectedModelId && trendData.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Card className="p-5" style={CARD_STYLE}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-sylion-blue" />
                      <h3 className="text-sm font-semibold">
                        {leaderboard.find((e) => e.model_id === selectedModelId)?.model_name ?? selectedModelId}
                        <HelpTip text="Sparkline z 24-godzinnym trendem wybranej metryki dla wybranego modelu. Pomocny do wyłapania regresji jakości lub dryfu wydajności." />
                      </h3>
                      <Badge variant="outline" className="text-[8px] h-4 border-sylion-blue/30 text-sylion-blue">
                        Trend 24h
                      </Badge>
                      <Badge variant="outline" className="text-[8px] h-4 border-border text-muted-foreground">
                        {METRIC_OPTIONS.find((o) => o.value === metricType)?.label}
                      </Badge>
                    </div>
                    <button
                      onClick={() => setSelectedModelId(null)}
                      className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Zamknij
                    </button>
                  </div>

                  {/* SVG sparkline chart */}
                  <div className="w-full h-40 relative">
                    {(() => {
                      const values = trendData.map((p) => p.value);
                      const minVal = Math.min(...values);
                      const maxVal = Math.max(...values);
                      const range = maxVal - minVal || 1;
                      const w = 800;
                      const h = 140;
                      const padding = 4;

                      const points = trendData.map((p, i) => {
                        const x = padding + (i / (trendData.length - 1)) * (w - padding * 2);
                        const y = h - padding - ((p.value - minVal) / range) * (h - padding * 2);
                        return { x, y, ...p };
                      });

                      const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
                      const areaPath = `${linePath} L ${points[points.length - 1].x} ${h} L ${points[0].x} ${h} Z`;

                      return (
                        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full" preserveAspectRatio="none">
                          {/* Grid lines */}
                          {[0.25, 0.5, 0.75].map((frac) => (
                            <line
                              key={frac}
                              x1={padding}
                              y1={h * frac}
                              x2={w - padding}
                              y2={h * frac}
                              stroke="rgba(148,163,184,0.08)"
                              strokeDasharray="4 4"
                            />
                          ))}
                          {/* Area fill */}
                          <path d={areaPath} fill="url(#leaderboardGradient)" opacity="0.3" />
                          {/* Line */}
                          <path d={linePath} fill="none" stroke="rgba(47,107,255,0.8)" strokeWidth="2" />
                          {/* Points */}
                          {points.map((p, i) => (
                            <circle
                              key={i}
                              cx={p.x}
                              cy={p.y}
                              r="3"
                              fill="rgba(47,107,255,0.9)"
                              stroke="#0f1629"
                              strokeWidth="2"
                            />
                          ))}
                          {/* Gradient definition */}
                          <defs>
                            <linearGradient id="leaderboardGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="rgba(47,107,255,0.4)" />
                              <stop offset="100%" stopColor="rgba(47,107,255,0)" />
                            </linearGradient>
                          </defs>
                        </svg>
                      );
                    })()}
                    {/* Axis labels */}
                    <div className="flex justify-between mt-1 px-1">
                      <span className="text-[9px] text-muted-foreground">
                        {trendData[0] ? new Date(trendData[0].timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                      </span>
                      <span className="text-[9px] text-muted-foreground">
                        {trendData[trendData.length - 1] ? new Date(trendData[trendData.length - 1].timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                      </span>
                    </div>
                    {/* Min/max labels */}
                    <div className="absolute top-0 right-0 flex flex-col items-end gap-0.5">
                      <span className="text-[9px] text-sylion-blue font-medium">
                        Maks.: {trendData.length ? trendData.reduce((a, b) => a.value > b.value ? a : b).value.toFixed(3) : "--"}
                      </span>
                      <span className="text-[9px] text-muted-foreground">
                        Min.: {trendData.length ? trendData.reduce((a, b) => a.value < b.value ? a : b).value.toFixed(3) : "--"}
                      </span>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
