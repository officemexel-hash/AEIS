"use client";

import { useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Heart,
  RefreshCw,
  AlertTriangle,
  Activity,
  Clock,
  Server,
  Database,
  Shield,
  CheckCircle2,
  XCircle,
  Zap,
  Layers,
  Cpu,
  HardDrive,
  Radio,
  WifiOff,
  Timer,
  Eye,
  Brain,
  Lock,
  MonitorSmartphone,
  ChevronDown,
  ChevronUp,
  Search,
  SortAsc,
  SortDesc,
  Play,
  Gauge,
  MemoryStick,
  ArrowUpRight,
  Globe,
  GitBranch,
  Terminal,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface HealthCheck {
  name: string;
  status: "pass" | "fail" | "warn";
  duration_ms: number;
  message: string;
  category?: string;
}

interface HealthModule {
  module_id: string;
  lifecycle: string;
  last_heartbeat: number;
  health: "healthy" | "unhealthy" | "stale";
  category: string;
}

interface DiagnosticInfo {
  python_version: string;
  os_info: string;
  uptime_seconds: number;
  memory_usage_mb: number;
  memory_total_mb: number;
  db_size_mb: number;
  db_tables: number;
  db_connections: number;
  eventbus_published: number;
  eventbus_subscribers: number;
  avg_response_ms: number;
  requests_per_minute: number;
}

interface HealthData {
  status: string;
  version: string;
  modules: number;
  endpoints: number;
  db_mode?: string;
  checks?: HealthCheck[];
  registered_modules?: HealthModule[];
  diagnostics?: DiagnosticInfo;
}

/* ============================================================
   Backend-only empty states
   ============================================================ */

const EMPTY_DIAGNOSTICS: DiagnosticInfo = {
  python_version: "",
  os_info: "",
  uptime_seconds: 0,
  memory_usage_mb: 0,
  memory_total_mb: 0,
  db_size_mb: 0,
  db_tables: 0,
  db_connections: 0,
  eventbus_published: 0,
  eventbus_subscribers: 0,
  avg_response_ms: 0,
  requests_per_minute: 0,
};

/* ============================================================
   Helpers
   ============================================================ */

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 24) return `${Math.floor(h / 24)}d ${h % 24}h ${m}m`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatHeartbeat(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 5000) return "just now";
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  return `${Math.floor(diff / 3600000)}h ago`;
}

/* ============================================================
   Status style maps
   ============================================================ */

const statusStyles: Record<string, { dot: string; badge: string; text: string; iconBg: string }> = {
  pass: {
    dot: "bg-sylion-green",
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    text: "text-sylion-green",
    iconBg: "bg-sylion-green/10",
  },
  warn: {
    dot: "bg-sylion-amber",
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    text: "text-sylion-amber",
    iconBg: "bg-sylion-amber/10",
  },
  fail: {
    dot: "bg-sylion-red",
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    text: "text-sylion-red",
    iconBg: "bg-sylion-red/10",
  },
  healthy: {
    dot: "bg-sylion-green",
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    text: "text-sylion-green",
    iconBg: "bg-sylion-green/10",
  },
  unhealthy: {
    dot: "bg-sylion-red",
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    text: "text-sylion-red",
    iconBg: "bg-sylion-red/10",
  },
  stale: {
    dot: "bg-sylion-amber",
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    text: "text-sylion-amber",
    iconBg: "bg-sylion-amber/10",
  },
};

const categoryIcons: Record<string, React.ElementType> = {
  Core: Server,
  Governance: Shield,
  Security: Lock,
  Cognitive: Brain,
  Execution: Zap,
  AEIS: Eye,
  Memory: HardDrive,
  Quality: CheckCircle2,
  Efficiency: Timer,
  Surface: MonitorSmartphone,
};

/* ============================================================
   PulseIndicator
   ============================================================ */

function PulseIndicator({ active, color }: { active: boolean; color: "green" | "amber" | "red" }) {
  const colors = { green: "bg-sylion-green", amber: "bg-sylion-amber", red: "bg-sylion-red" };
  const rings = { green: "ring-sylion-green/30", amber: "ring-sylion-amber/30", red: "ring-sylion-red/30" };
  return (
    <span className="relative flex h-3 w-3">
      {active && (
        <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", colors[color])} />
      )}
      <span className={cn("relative inline-flex rounded-full h-3 w-3", colors[color], active && `ring-4 ${rings[color]}`)} />
    </span>
  );
}

/* ============================================================
   HealthScoreRing — circular progress indicator
   ============================================================ */

function HealthScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 90 ? "stroke-sylion-green" : score >= 70 ? "stroke-sylion-amber" : "stroke-sylion-red";
  const textColor = score >= 90 ? "text-sylion-green" : score >= 70 ? "text-sylion-amber" : "text-sylion-red";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={strokeWidth} className="text-muted/30" />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke="currentColor" strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn(color, "transition-all duration-700")}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className={cn("text-lg font-bold font-mono", textColor)}>{score}%</span>
      </div>
    </div>
  );
}

/* ============================================================
   Page Component
   ============================================================ */

export default function HealthPage() {
  /* ---------- Hook-driven data ---------- */
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const healthData = healthRaw as HealthData;
  const backendLive = healthData.status === "ok";

  // Health checks tab
  const [expandedCheckOverrides, setExpandedCheckOverrides] = useState<Set<string>>(new Set());
  const [runningChecks, setRunningChecks] = useState(false);

  // Module status tab
  const [moduleFilter, setModuleFilter] = useState<string>("all");
  const [moduleSort, setModuleSort] = useState<"name" | "status" | "heartbeat">("name");
  const [moduleSortDir, setModuleSortDir] = useState<"asc" | "desc">("asc");
  const [selectedModule, setSelectedModule] = useState<HealthModule | null>(null);

  /* ---------- Determine overall system status ---------- */
  const systemStatus: "healthy" | "degraded" | "unhealthy" = useMemo(() => {
    if (!backendLive) return "unhealthy";
    const checks = healthData.checks || [];
    if (checks.length === 0) return "healthy";
    const fails = checks.filter((c) => c.status === "fail").length;
    const warns = checks.filter((c) => c.status === "warn").length;
    if (fails > 0) return "unhealthy";
    if (warns > 0) return "degraded";
    return "healthy";
  }, [healthData, backendLive]);

  /* ---------- Auto-expand failed/warn checks ---------- */
  const autoExpandedChecks = useMemo(() => {
    const checks = healthData.checks || [];
    return new Set(
      checks.filter((c) => c.status === "fail" || c.status === "warn").map((c) => c.name)
    );
  }, [healthData.checks]);

  /* ---------- Derived: checks ---------- */
  const checks = healthData.checks || [];
  const passCount = checks.filter((c) => c.status === "pass").length;
  const warnCount = checks.filter((c) => c.status === "warn").length;
  const failCount = checks.filter((c) => c.status === "fail").length;
  const healthScore = checks.length > 0 ? Math.round((passCount / checks.length) * 100) : 100;

  /* ---------- Derived: modules ---------- */
  const allModules = healthData.registered_modules || [];
  const filteredModules = useMemo(() => {
    let list = [...allModules];
    if (moduleFilter !== "all") list = list.filter((m) => m.health === moduleFilter);
    list.sort((a, b) => {
      let cmp = 0;
      if (moduleSort === "name") cmp = a.module_id.localeCompare(b.module_id);
      else if (moduleSort === "status") {
        const order = { unhealthy: 0, stale: 1, healthy: 2 };
        cmp = (order[a.health] ?? 2) - (order[b.health] ?? 2);
      } else if (moduleSort === "heartbeat") cmp = a.last_heartbeat - b.last_heartbeat;
      return moduleSortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [allModules, moduleFilter, moduleSort, moduleSortDir]);

  /* ---------- Derived: diagnostics ---------- */
  const diag = healthData.diagnostics || EMPTY_DIAGNOSTICS;

  /* ---------- Toggle check expansion ---------- */
  const toggleCheck = useCallback((name: string) => {
    setExpandedCheckOverrides((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const isCheckExpanded = useCallback((name: string) => {
    return expandedCheckOverrides.has(name)
      ? !autoExpandedChecks.has(name)
      : autoExpandedChecks.has(name);
  }, [autoExpandedChecks, expandedCheckOverrides]);

  /* ---------- Run All Checks simulation ---------- */
  const runAllChecks = useCallback(() => {
    setRunningChecks(true);
    setTimeout(() => {
      setRunningChecks(false);
      fetchHealth();
    }, 1500);
  }, [fetchHealth]);

  /* ---------- Toggle sort ---------- */
  const toggleSort = useCallback((field: "name" | "status" | "heartbeat") => {
    if (moduleSort === field) setModuleSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setModuleSort(field); setModuleSortDir("asc"); }
  }, [moduleSort]);

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-36 bg-muted animate-pulse rounded" />
            <div className="h-4 w-52 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-8 w-64 bg-muted animate-pulse rounded-lg" />
        <div className="h-64 bg-muted animate-pulse rounded-lg" />
      </div>
    );
  }

  /* ---------- Backend unreachable ---------- */
  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <Heart className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Zdrowie systemu
              <HelpTip text="Stan zdrowia wszystkich modułów AEIS. Zielony = sprawny; amber = degradacja (np. wolny PG, brakujący embedding model); czerwony = krytyczne (storage pełny, db down). Klikając w moduł — szczegóły ostatnich kontroli." />
            </h1>
            <p className="text-sm text-muted-foreground">Monitoring i diagnostyka na żywo</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane o zdrowiu, statusie modułów i diagnostyce wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => fetchHealth()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Status badge for header ---------- */
  const statusBadge = (() => {
    if (systemStatus === "healthy") return { label: "SPRAWNY", color: "green" as const, borderCls: "border-sylion-green/30 text-sylion-green bg-sylion-green/5" };
    if (systemStatus === "degraded") return { label: "POGORSZONY", color: "amber" as const, borderCls: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5" };
    return { label: "KRYTYCZNY", color: "red" as const, borderCls: "border-sylion-red/30 text-sylion-red bg-sylion-red/5" };
  })();

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center border", systemStatus === "healthy" ? "bg-sylion-green/10 border-sylion-green/20" : systemStatus === "degraded" ? "bg-sylion-amber/10 border-sylion-amber/20" : "bg-sylion-red/10 border-sylion-red/20")}>
            <Heart className={cn("w-4 h-4", systemStatus === "healthy" ? "text-sylion-green" : systemStatus === "degraded" ? "text-sylion-amber" : "text-sylion-red")} />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Zdrowie systemu
              <HelpTip text="Stan zdrowia wszystkich modułów AEIS. Zielony = sprawny; amber = degradacja (np. wolny PG, brakujący embedding model); czerwony = krytyczne (storage pełny, db down). Klikając w moduł — szczegóły ostatnich kontroli." />
            </h1>
            <p className="text-sm text-muted-foreground">Monitoring i diagnostyka na żywo</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Status badge */}
          <Badge variant="outline" className={cn("text-[10px] flex items-center gap-1.5", statusBadge.borderCls)}>
            <PulseIndicator active={true} color={statusBadge.color} />
            {statusBadge.label}
          </Badge>

          {/* Refresh button */}
          <Button variant="outline" size="sm" onClick={() => fetchHealth()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== STATS ROW (4 cards) ====== */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: "Status ogólny",
            tip: "Zagregowany stan systemu. Sprawny = wszystkie kontrole pass; Pogorszony = ostrzeżenia obecne; Krytyczny = co najmniej jedna kontrola nie powiodła się.",
            value: systemStatus === "healthy" ? "Sprawny" : systemStatus === "degraded" ? "Pogorszony" : "Krytyczny",
            icon: systemStatus === "healthy" ? CheckCircle2 : systemStatus === "degraded" ? AlertTriangle : XCircle,
            color: systemStatus === "healthy" ? "text-sylion-green" : systemStatus === "degraded" ? "text-sylion-amber" : "text-sylion-red",
            bgColor: systemStatus === "healthy" ? "bg-sylion-green/10" : systemStatus === "degraded" ? "bg-sylion-amber/10" : "bg-sylion-red/10",
          },
          {
            label: "Załadowane moduły",
            tip: "Liczba modułów AEIS zarejestrowanych w jądrze. Powinna odpowiadać liczbie z manifestu — różnica oznacza brakujące/uszkodzone moduły.",
            value: healthData.modules || 0,
            icon: Layers,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
          },
          {
            label: "Dostępne punkty końcowe",
            tip: "Liczba aktywnych endpointów REST/RPC. Każdy moduł publikuje własne — spadek może wskazywać na problem z bootstrapem.",
            value: healthData.endpoints || 0,
            icon: Server,
            color: "text-sylion-amber",
            bgColor: "bg-sylion-amber/10",
          },
          {
            label: "Tryb bazy danych",
            tip: "Aktualnie używany silnik (sqlite/postgres). Dla produkcji zalecane PostgreSQL; SQLite OK na dev/test.",
            value: healthData.db_mode || "--",
            icon: Database,
            color: "text-purple-400",
            bgColor: "bg-purple-400/10",
          },
        ].map((stat) => {
          const SIcon = stat.icon;
          return (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                      {stat.label}
                      <HelpTip text={stat.tip} />
                    </p>
                    <p className={cn("text-xl font-semibold mt-1 font-mono", stat.color)}>{stat.value}</p>
                  </div>
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", stat.bgColor)}>
                    <SIcon className={cn("w-4 h-4", stat.color)} />
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* ====== MAIN TABS ====== */}
      <Tabs defaultValue="checks">
        <div className="flex items-center gap-2">
          <TabsList className="bg-muted/20">
            <TabsTrigger value="checks" className="text-xs">
              <Activity className="w-3.5 h-3.5 mr-1.5" />
              Kontrole zdrowia
            </TabsTrigger>
            <TabsTrigger value="modules" className="text-xs">
              <Layers className="w-3.5 h-3.5 mr-1.5" />
              Status modułów
            </TabsTrigger>
            <TabsTrigger value="diagnostics" className="text-xs">
              <Gauge className="w-3.5 h-3.5 mr-1.5" />
              Diagnostyka
            </TabsTrigger>
          </TabsList>
          <HelpTip text="Trzy widoki: Kontrole zdrowia (lista pass/warn/fail z szczegółami), Status modułów (siatka modułów z heartbeatem) oraz Diagnostyka (CPU, RAM, EventBus). Domyślnie odświeżane co 15 s." />
        </div>

        {/* ===== TAB 1: HEALTH CHECKS ===== */}
        <TabsContent value="checks" className="mt-4">
          <div className="space-y-4">
            {/* Summary bar */}
            <div className="flex items-center gap-4">
              <Card className="p-4 bg-[#0f1629] border-sylion-border flex items-center gap-4 flex-1">
                <HealthScoreRing score={healthScore} size={64} />
                <div className="flex-1">
                  <p className="text-sm font-medium">
                    Wynik zdrowia
                    <HelpTip text="Procentowy udział kontroli pass do wszystkich. 100% = idealnie; <90% wymaga uwagi; <70% — interwencja." />
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {passCount} pass, {warnCount} warn, {failCount} fail — łącznie {checks.length} kontroli
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {failCount > 0 && (
                    <Badge variant="outline" className="text-[9px] border-sylion-red/30 text-sylion-red bg-sylion-red/5">
                      {failCount} nieudane
                    </Badge>
                  )}
                  {warnCount > 0 && (
                    <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5">
                      {warnCount} ostrzeżeń
                    </Badge>
                  )}
                  <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green bg-sylion-green/5">
                    {passCount} pomyślnych
                  </Badge>
                </div>
              </Card>
              <Button
                variant="outline"
                size="sm"
                onClick={runAllChecks}
                disabled={runningChecks}
                className="shrink-0"
              >
                {runningChecks ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                )}
                {runningChecks ? "Trwa..." : "Uruchom wszystkie kontrole"}
              </Button>
            </div>

            {/* Checks list */}
            <Card className="bg-[#0f1629] border-sylion-border">
              <div className="p-3 border-b border-border/30 flex items-center justify-between">
                <h3 className="text-xs font-medium text-muted-foreground">
                  Pojedyncze kontrole
                  <HelpTip text="Każda pozycja to niezależny check zarejestrowany przez moduł. Kliknij wiersz, aby rozwinąć szczegóły i sugestię naprawy." />
                </h3>
                <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                  Posortowane wg statusu (najpierw błędy)
                </span>
              </div>
              <div className="divide-y divide-border/20">
                {[...checks]
                  .sort((a, b) => {
                    const order = { fail: 0, warn: 1, pass: 2 };
                    return (order[a.status] ?? 2) - (order[b.status] ?? 2);
                  })
                  .map((check) => {
                    const styles = statusStyles[check.status] || statusStyles.pass;
                    const isExpanded = isCheckExpanded(check.name);
                    const CIcon = categoryIcons[check.category || ""] || Activity;

                    return (
                      <motion.div
                        key={check.name}
                        initial={false}
                        animate={{ opacity: 1 }}
                        className={cn(
                          "transition-colors",
                          check.status === "fail" && "bg-sylion-red/[0.02]",
                          check.status === "warn" && "bg-sylion-amber/[0.02]"
                        )}
                      >
                        <button
                          type="button"
                          className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
                          onClick={() => toggleCheck(check.name)}
                        >
                          {/* Status icon */}
                          {check.status === "pass" ? (
                            <CheckCircle2 className={cn("w-4 h-4 shrink-0", styles.text)} />
                          ) : check.status === "warn" ? (
                            <AlertTriangle className={cn("w-4 h-4 shrink-0", styles.text)} />
                          ) : (
                            <XCircle className={cn("w-4 h-4 shrink-0", styles.text)} />
                          )}

                          {/* Check name */}
                          <span className="text-xs font-medium flex-1">{check.name}</span>

                          {/* Category badge */}
                          {check.category && (
                            <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground shrink-0">
                              <CIcon className="w-2.5 h-2.5 mr-1" />
                              {check.category}
                            </Badge>
                          )}

                          {/* Status badge */}
                          <Badge variant="outline" className={cn("text-[9px] shrink-0", styles.badge)}>
                            {check.status.toUpperCase()}
                          </Badge>

                          {/* Duration */}
                          <span className={cn(
                            "text-[10px] font-mono w-16 text-right shrink-0",
                            check.duration_ms < 10 ? "text-sylion-green" : check.duration_ms < 50 ? "text-sylion-amber" : "text-sylion-red"
                          )}>
                            {check.duration_ms}ms
                          </span>

                          {/* Expand arrow */}
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          )}
                        </button>

                        {/* Expanded details */}
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden"
                            >
                              <div className={cn(
                                "px-4 pb-3 pl-11 text-xs space-y-1",
                                check.status === "fail" ? "text-sylion-red/80" : check.status === "warn" ? "text-sylion-amber/80" : "text-muted-foreground"
                              )}>
                                <p>{check.message}</p>
                                {check.status === "fail" && (
                                  <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
                                    <AlertTriangle className="w-3 h-3 text-sylion-amber" />
                                    <span>Sprawdź logi lub zrestartuj moduł, aby rozwiązać ten problem.</span>
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })}
              </div>
            </Card>
          </div>
        </TabsContent>

        {/* ===== TAB 2: MODULE STATUS ===== */}
        <TabsContent value="modules" className="mt-4">
          <div className="space-y-4">
            {/* Filter + sort bar */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                {(["all", "healthy", "unhealthy", "stale"] as const).map((f) => {
                  const labelMap = { all: "Wszystkie", healthy: "Sprawne", unhealthy: "Niesprawne", stale: "Nieaktualne" };
                  return (
                  <Button
                    key={f}
                    variant={moduleFilter === f ? "default" : "outline"}
                    size="sm"
                    className="text-[10px] h-7"
                    onClick={() => setModuleFilter(f)}
                  >
                    {labelMap[f]}
                    {f !== "all" && (
                      <span className="ml-1.5 text-muted-foreground">
                        ({allModules.filter((m) => m.health === f).length})
                      </span>
                    )}
                  </Button>
                  );
                })}
              </div>

              <div className="flex-1" />

              {/* Sort controls */}
              <div className="flex items-center gap-1">
                {(["name", "status", "heartbeat"] as const).map((field) => {
                  const labelMap = { name: "Nazwa", status: "Status", heartbeat: "Ostatni puls" };
                  return (
                  <Button
                    key={field}
                    variant={moduleSort === field ? "default" : "outline"}
                    size="sm"
                    className="text-[10px] h-7"
                    onClick={() => toggleSort(field)}
                  >
                    {labelMap[field]}
                    {moduleSort === field && (
                      moduleSortDir === "asc" ? <SortAsc className="w-3 h-3 ml-1" /> : <SortDesc className="w-3 h-3 ml-1" />
                    )}
                  </Button>
                  );
                })}
              </div>
            </div>

            {/* Module grid */}
            <div className="grid grid-cols-3 gap-3">
              {filteredModules.map((mod, idx) => {
                const styles = statusStyles[mod.health] || statusStyles.healthy;
                const CIcon = categoryIcons[mod.category] || Server;
                const isSelected = selectedModule?.module_id === mod.module_id;

                return (
                  <motion.div
                    key={mod.module_id}
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: idx * 0.02, duration: 0.2 }}
                  >
                    <Card
                      className={cn(
                        "p-3.5 transition-all cursor-pointer card-hover",
                        "bg-[#0f1629] border-sylion-border",
                        isSelected && "ring-1 ring-primary/50",
                        mod.health === "unhealthy" && "border-sylion-red/20",
                        mod.health === "stale" && "border-sylion-amber/20"
                      )}
                      onClick={() => setSelectedModule(isSelected ? null : mod)}
                    >
                      <div className="flex items-center gap-2.5 mb-2">
                        <div className={cn("w-7 h-7 rounded-md flex items-center justify-center", styles.iconBg)}>
                          <CIcon className={cn("w-3.5 h-3.5", styles.text)} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{mod.module_id}</p>
                          <p className="text-[10px] text-muted-foreground">{mod.category}</p>
                        </div>
                        <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", styles.dot, mod.health === "stale" && "animate-pulse")} />
                      </div>

                      <div className="flex items-center justify-between text-[10px]">
                        <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                          {mod.lifecycle}
                        </Badge>
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {formatHeartbeat(mod.last_heartbeat)}
                        </span>
                      </div>

                      {/* Expanded detail */}
                      <AnimatePresence>
                        {isSelected && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="mt-3 pt-3 border-t border-border/30 space-y-2 text-[10px] text-muted-foreground">
                              <div className="flex justify-between">
                                <span>ID modułu</span>
                                <span className="font-mono text-foreground">{mod.module_id}</span>
                              </div>
                              <div className="flex justify-between">
                                <span>Cykl życia</span>
                                <Badge variant="outline" className="text-[9px] h-4 border-border/50">{mod.lifecycle}</Badge>
                              </div>
                              <div className="flex justify-between">
                                <span>Stan</span>
                                <Badge variant="outline" className={cn("text-[9px] h-4", styles.badge)}>{mod.health}</Badge>
                              </div>
                              <div className="flex justify-between">
                                <span>Ostatni puls</span>
                                <span className="font-mono text-foreground">{new Date(mod.last_heartbeat).toLocaleTimeString()}</span>
                              </div>
                              <div className="flex justify-between">
                                <span>Kategoria</span>
                                <span className="text-foreground">{mod.category}</span>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </Card>
                  </motion.div>
                );
              })}
            </div>

            {filteredModules.length === 0 && (
              <div className="text-center py-12">
                <Search className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">Żaden moduł nie spełnia bieżącego filtra</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ===== TAB 3: DIAGNOSTICS ===== */}
        <TabsContent value="diagnostics" className="mt-4">
          <div className="grid grid-cols-2 gap-4">
            {/* System Info */}
            <Card className="p-4 bg-[#0f1629] border-sylion-border">
              <div className="flex items-center gap-2 mb-3">
                <Cpu className="w-4 h-4 text-sylion-blue" />
                <h3 className="text-xs font-semibold">
                  Informacje o systemie
                  <HelpTip text="Podstawowe metadane runtime'u: wersja Pythona, OS, czas działania procesu, wersja SYLION. Pomocne przy raportowaniu bugów." />
                </h3>
              </div>
              <div className="space-y-2.5">
                {[
                  { label: "Wersja Pythona", value: diag.python_version, icon: Terminal },
                  { label: "System operacyjny", value: diag.os_info, icon: Globe },
                  { label: "Czas działania", value: formatUptime(diag.uptime_seconds), icon: Clock },
                  { label: "Wersja SYLION", value: healthData.version || "--", icon: GitBranch },
                ].map((item) => {
                  const IIcon = item.icon;
                  return (
                    <div key={item.label} className="flex items-center justify-between text-[11px]">
                      <span className="text-muted-foreground flex items-center gap-1.5">
                        <IIcon className="w-3 h-3" />
                        {item.label}
                      </span>
                      <span className="font-mono text-foreground">{item.value}</span>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Memory Usage */}
            <Card className="p-4 bg-[#0f1629] border-sylion-border">
              <div className="flex items-center gap-2 mb-3">
                <MemoryStick className="w-4 h-4 text-purple-400" />
                <h3 className="text-xs font-semibold">
                  Zużycie pamięci
                  <HelpTip text="Ile RAM-u zajmuje proces SYLION + wielkość bazy danych i połączeń. Czerwony pasek = >90% zajętości; rozważ restart lub zwiększenie limitu." />
                </h3>
              </div>
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between text-[11px] mb-1">
                    <span className="text-muted-foreground">RAM</span>
                    <span className="font-mono text-foreground">
                      {diag.memory_usage_mb} / {diag.memory_total_mb} MB
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted/30 overflow-hidden">
                    <motion.div
                      className={cn(
                        "h-full rounded-full transition-all",
                        (diag.memory_usage_mb / diag.memory_total_mb) < 0.7 ? "bg-sylion-green" : (diag.memory_usage_mb / diag.memory_total_mb) < 0.9 ? "bg-sylion-amber" : "bg-sylion-red"
                      )}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, (diag.memory_usage_mb / diag.memory_total_mb) * 100)}%` }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {((diag.memory_usage_mb / diag.memory_total_mb) * 100).toFixed(1)}% wykorzystania
                  </p>
                </div>

                <div className="pt-2 border-t border-border/30 space-y-2.5">
                  {[
                    { label: "Rozmiar DB", value: `${diag.db_size_mb} MB`, icon: Database },
                    { label: "Tabele DB", value: String(diag.db_tables), icon: HardDrive },
                    { label: "Połączenia DB", value: String(diag.db_connections), icon: ArrowUpRight },
                  ].map((item) => {
                    const IIcon = item.icon;
                    return (
                      <div key={item.label} className="flex items-center justify-between text-[11px]">
                        <span className="text-muted-foreground flex items-center gap-1.5">
                          <IIcon className="w-3 h-3" />
                          {item.label}
                        </span>
                        <span className="font-mono text-foreground">{item.value}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>

            {/* EventBus Stats */}
            <Card className="p-4 bg-[#0f1629] border-sylion-border">
              <div className="flex items-center gap-2 mb-3">
                <Radio className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-semibold">
                  Statystyki EventBus
                  <HelpTip text="Ruch w wewnętrznej szynie zdarzeń. Wzrost subskrybentów = więcej modułów; spadek publikacji = możliwa awaria producenta." />
                </h3>
              </div>
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Opublikowane zdarze?ia</span>
                  <span className="font-mono text-sylion-green">{diag.eventbus_published.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Aktywni subskrybenci</span>
                  <span className="font-mono text-sylion-blue">{diag.eventbus_subscribers}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Tryb zdarzeń</span>
                  <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                    {(healthData as any).event_mode || "in-process"}
                  </Badge>
                </div>
              </div>
            </Card>

            {/* Performance */}
            <Card className="p-4 bg-[#0f1629] border-sylion-border">
              <div className="flex items-center gap-2 mb-3">
                <Gauge className="w-4 h-4 text-sylion-amber" />
                <h3 className="text-xs font-semibold">
                  Wydajność
                  <HelpTip text="Średni czas odpowiedzi (p50) i przepustowość RPM. Czerwony >200 ms = pogorszenie; zalecane sprawdźenie obciążenia DB i cache." />
                </h3>
              </div>
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between text-[11px] mb-1">
                    <span className="text-muted-foreground">Średni czas odpowiedzi</span>
                    <span className={cn(
                      "font-mono",
                      diag.avg_response_ms < 50 ? "text-sylion-green" : diag.avg_response_ms < 200 ? "text-sylion-amber" : "text-sylion-red"
                    )}>
                      {diag.avg_response_ms}ms
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted/30 overflow-hidden">
                    <motion.div
                      className={cn(
                        "h-full rounded-full",
                        diag.avg_response_ms < 50 ? "bg-sylion-green" : diag.avg_response_ms < 200 ? "bg-sylion-amber" : "bg-sylion-red"
                      )}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, (diag.avg_response_ms / 500) * 100)}%` }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                </div>

                <div className="pt-2 border-t border-border/30 space-y-2.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Activity className="w-3 h-3" />
                      Żądania / minutę
                    </span>
                    <span className="font-mono text-foreground">{diag.requests_per_minute}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Layers className="w-3 h-3" />
                      Łącznie modułów
                    </span>
                    <span className="font-mono text-foreground">{healthData.modules || 0}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Server className="w-3 h-3" />
                      Łącznie endpointów
                    </span>
                    <span className="font-mono text-foreground">{healthData.endpoints || 0}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Database className="w-3 h-3" />
                      Tryb DB
                    </span>
                    <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                      {healthData.db_mode || "--"}
                    </Badge>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Live indicator */}
          <div className="flex items-center justify-center gap-2 mt-4 text-[10px] text-muted-foreground">
            <PulseIndicator active={true} color={systemStatus === "healthy" ? "green" : systemStatus === "degraded" ? "amber" : "red"} />
            <span>Auto-odświeżanie co 15 sekund</span>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
