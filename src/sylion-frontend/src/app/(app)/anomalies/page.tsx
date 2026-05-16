"use client";

import { useState, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useHealth, useAnomalies, useMetricSummary } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  AlertTriangle,
  Activity,
  RefreshCw,
  WifiOff,
  ShieldAlert,
  BarChart3,
  Clock,
  TrendingUp,
  Eye,
  CheckCircle2,
  XCircle,
  Info,
  Search,
  ArrowUpDown,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Anomaly {
  id: string;
  metric_name: string;
  detected_value: number;
  expected_min?: number;
  expected_max?: number;
  severity: "critical" | "warning" | "info";
  status: "active" | "resolved" | "acknowledged";
  timestamp: number | string;
  description?: string;
}

interface Baseline {
  metric_name: string;
  mean: number;
  std_dev: number;
  min: number;
  max: number;
  sample_count: number;
  last_updated: number | string;
}

/* ============================================================
   Helpers
   ============================================================ */

function fmtTimestamp(ts: number | string): string {
  if (!ts) return "---";
  try {
    const d = typeof ts === "number" ? (ts > 1e12 ? new Date(ts) : new Date(ts * 1000)) : new Date(ts);
    return d.toLocaleString();
  } catch {
    return String(ts);
  }
}

/* ============================================================
   Severity badge config
   ============================================================ */

const severityConfig: Record<string, { color: string; borderCls: string; icon: React.ElementType }> = {
  critical: {
    color: "text-sylion-red",
    borderCls: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    icon: XCircle,
  },
  warning: {
    color: "text-sylion-amber",
    borderCls: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    icon: AlertTriangle,
  },
  info: {
    color: "text-sylion-blue",
    borderCls: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    icon: Info,
  },
};

const statusConfig: Record<string, { borderCls: string; icon: React.ElementType }> = {
  active: {
    borderCls: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    icon: AlertTriangle,
  },
  acknowledged: {
    borderCls: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    icon: Eye,
  },
  resolved: {
    borderCls: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    icon: CheckCircle2,
  },
};

/* ============================================================
   Page Component
   ============================================================ */

export default function AnomaliesPage() {
  /* ---------- Hook-driven data ---------- */
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const healthData = healthRaw as { status: string; version: string };
  const backendLive = healthData.status === "ok";

  const { data: anomaliesData, refresh: fetchAnomalies } = useAnomalies();
  const anomalies = (anomaliesData as { anomalies: Anomaly[] }).anomalies ?? [];

  /* ---------- Local state ---------- */
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [sortField, setSortField] = useState<"timestamp" | "severity">("timestamp");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selectedMetric, setSelectedMetric] = useState<string>("");

  /* ---------- Metric baseline (fetched on demand) ---------- */
  const { data: metricSummary } = useMetricSummary(selectedMetric);
  const baseline = (metricSummary ?? {}) as Baseline;

  /* ---------- Derived: summary stats ---------- */
  const totalAnomalies = anomalies.length;
  const activeAnomalies = anomalies.filter((a) => a.status === "active").length;
  const criticalAnomalies = anomalies.filter((a) => a.severity === "critical" && a.status === "active").length;

  const uniqueMetrics = useMemo(() => {
    const set = new Set<string>();
    anomalies.forEach((a) => set.add(a.metric_name));
    return Array.from(set).sort();
  }, [anomalies]);

  const baselinesTracked = uniqueMetrics.length;

  /* ---------- Derived: filtered + sorted anomalies ---------- */
  const filteredAnomalies = useMemo(() => {
    let list = [...anomalies];
    if (statusFilter !== "all") list = list.filter((a) => a.status === statusFilter);
    if (severityFilter !== "all") list = list.filter((a) => a.severity === severityFilter);

    const severityOrder = { critical: 0, warning: 1, info: 2 };
    list.sort((a, b) => {
      let cmp = 0;
      if (sortField === "timestamp") {
        const ta = typeof a.timestamp === "number" ? a.timestamp : new Date(a.timestamp).getTime();
        const tb = typeof b.timestamp === "number" ? b.timestamp : new Date(b.timestamp).getTime();
        cmp = ta - tb;
      } else {
        cmp = (severityOrder[a.severity] ?? 2) - (severityOrder[b.severity] ?? 2);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [anomalies, statusFilter, severityFilter, sortField, sortDir]);

  /* ---------- Toggle sort ---------- */
  const toggleSort = useCallback((field: "timestamp" | "severity") => {
    if (sortField === field) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortField(field); setSortDir("desc"); }
  }, [sortField]);

  /* ---------- Refresh all ---------- */
  const refreshAll = useCallback(() => {
    fetchHealth();
    fetchAnomalies();
  }, [fetchHealth, fetchAnomalies]);

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-44 bg-muted animate-pulse rounded" />
            <div className="h-4 w-56 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
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
            <ShieldAlert className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Anomalie
              <HelpTip text="Wykrywanie nietypowych wzorców w wywołaniach (anomalous prompts, suspicious responses, cost spikes). Łapie próby exfiltracji, prompt injection, sudden cost overruns." />
            </h1>
            <p className="text-sm text-muted-foreground">Baseline'y metryk i śledzenie anomalii</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane wykrywania anomalii wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => refreshAll()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Live content ---------- */
  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-amber/10 border border-sylion-amber/20 flex items-center justify-center">
            <ShieldAlert className="w-4 h-4 text-sylion-amber" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Anomalie
              <HelpTip text="Wykrywanie nietypowych wzorców w wywołaniach (anomalous prompts, suspicious responses, cost spikes). Łapie próby exfiltracji, prompt injection, sudden cost overruns." />
            </h1>
            <p className="text-sm text-muted-foreground">Baseline'y metryk i śledzenie anomalii</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {criticalAnomalies > 0 && (
            <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red bg-sylion-red/5 flex items-center gap-1.5">
              <XCircle className="w-3 h-3" />
              {criticalAnomalies} krytyczne
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={() => refreshAll()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS ====== */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            label: "Łącznie anomalii",
            tip: "Wszystkie wykryte odchylenia od baseline'u — niezależnie od statusu.",
            value: totalAnomalies,
            icon: Activity,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
          },
          {
            label: "Aktywne anomalie",
            tip: "Anomalie wymagające reakcji (status active). Powyżej 0 sprawdź szczegóły i potwierdź lub wycisz.",
            value: activeAnomalies,
            icon: AlertTriangle,
            color: activeAnomalies > 0 ? "text-sylion-red" : "text-sylion-green",
            bgColor: activeAnomalies > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
          },
          {
            label: "Śledzone baseline'y",
            tip: "Liczba metryk z aktywnym profilem oczekiwanych wartości. Baseline = mean ± std_dev z N ostatnich próbek.",
            value: baselinesTracked,
            icon: BarChart3,
            color: "text-sylion-amber",
            bgColor: "bg-sylion-amber/10",
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
      <Tabs defaultValue="anomalies">
        <div className="flex items-center gap-2">
          <TabsList className="bg-muted/20">
            <TabsTrigger value="anomalies" className="text-xs">
              <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
              Lista anomalii
            </TabsTrigger>
            <TabsTrigger value="baselines" className="text-xs">
              <BarChart3 className="w-3.5 h-3.5 mr-1.5" />
              Baseline'y metryk
            </TabsTrigger>
          </TabsList>
          <HelpTip text="Lista anomalii = wszystkie wykryte zdarze?ia z filtrowaniem po statusie/poziomie. Baseline'y metryk = statystyki referencyjne (mean, std, min, max) dla wybranej metryki." />
        </div>

        {/* ===== TAB 1: ANOMALY LIST ===== */}
        <TabsContent value="anomalies" className="mt-4">
          <div className="space-y-4">
            {/* Filter bar */}
            <div className="flex items-center gap-3">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Filtry
                <HelpTip text="Filtry kombinowane: status (active/acknowledged/resolved) i poziom (critical/warning/info). Łączą się przez AND." />
              </span>
              <div className="flex items-center gap-1">
                {(["all", "active", "acknowledged", "resolved"] as const).map((f) => {
                  const labelMap = { all: "Wszystkie statusy", active: "Aktywne", acknowledged: "Potwierdzone", resolved: "Rozwiązane" };
                  return (
                  <Button
                    key={f}
                    variant={statusFilter === f ? "default" : "outline"}
                    size="sm"
                    className="text-[10px] h-7"
                    onClick={() => setStatusFilter(f)}
                  >
                    {labelMap[f]}
                    {f !== "all" && (
                      <span className="ml-1.5 text-muted-foreground">
                        ({anomalies.filter((a) => a.status === f).length})
                      </span>
                    )}
                  </Button>
                  );
                })}
              </div>

              <div className="w-px h-5 bg-border/30" />

              <div className="flex items-center gap-1">
                {(["all", "critical", "warning", "info"] as const).map((s) => {
                  const labelMap = { all: "Wszystkie poziomy", critical: "Krytyczne", warning: "Ostrzeżenia", info: "Informacyjne" };
                  return (
                  <Button
                    key={s}
                    variant={severityFilter === s ? "default" : "outline"}
                    size="sm"
                    className="text-[10px] h-7"
                    onClick={() => setSeverityFilter(s)}
                  >
                    {labelMap[s]}
                  </Button>
                  );
                })}
              </div>

              <div className="flex-1" />

              <span className="text-[10px] text-muted-foreground">
                {filteredAnomalies.length} {filteredAnomalies.length === 1 ? "wynik" : "wyników"}
              </span>
            </div>

            {/* Anomaly table */}
            <Card className="bg-[#0f1629] border-sylion-border">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/30 hover:bg-transparent">
                    <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Nazwa metryki
                    </TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Wartość wykryta
                    </TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Zakres oczekiwany
                    </TableHead>
                    <TableHead
                      className="text-[10px] uppercase tracking-wider text-muted-foreground cursor-pointer select-none"
                      onClick={() => toggleSort("severity")}
                    >
                      <div className="flex items-center gap-1">
                        Poziom
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="text-[10px] uppercase tracking-wider text-muted-foreground cursor-pointer select-none"
                      onClick={() => toggleSort("timestamp")}
                    >
                      <div className="flex items-center gap-1">
                        Znacznik czasu
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </TableHead>
                    <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Status
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAnomalies.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="h-32 text-center">
                        <div className="flex flex-col items-center justify-center text-muted-foreground">
                          <Search className="w-6 h-6 mb-2 opacity-30" />
                          <p className="text-xs">Nie wykryto anomalii</p>
                          <p className="text-[10px] mt-1 opacity-60">Wszystkie metryki mieszczą się w oczekiwanych zakresach</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                  {filteredAnomalies.map((anomaly, idx) => {
                    const sevCfg = severityConfig[anomaly.severity] ?? severityConfig.info;
                    const statCfg = statusConfig[anomaly.status] ?? statusConfig.active;
                    const SevIcon = sevCfg.icon;
                    const StatIcon = statCfg.icon;

                    return (
                      <motion.tr
                        key={anomaly.id ?? idx}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.15, delay: idx * 0.02 }}
                        className="border-b border-border/20 hover:bg-muted/10 transition-colors"
                      >
                        <TableCell className="text-xs font-medium">
                          <div className="flex items-center gap-2">
                            <Activity className="w-3 h-3 text-muted-foreground shrink-0" />
                            <span>{anomaly.metric_name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-xs font-mono">
                          {anomaly.detected_value != null ? String(anomaly.detected_value) : "---"}
                        </TableCell>
                        <TableCell className="text-xs font-mono text-muted-foreground">
                          {anomaly.expected_min != null && anomaly.expected_max != null
                            ? `${anomaly.expected_min} - ${anomaly.expected_max}`
                            : "---"}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={cn("text-[9px]", sevCfg.borderCls)}>
                            <SevIcon className="w-2.5 h-2.5 mr-1" />
                            {anomaly.severity.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-[10px] text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Clock className="w-2.5 h-2.5 shrink-0" />
                            {fmtTimestamp(anomaly.timestamp)}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={cn("text-[9px]", statCfg.borderCls)}>
                            <StatIcon className="w-2.5 h-2.5 mr-1" />
                            {anomaly.status.toUpperCase()}
                          </Badge>
                        </TableCell>
                      </motion.tr>
                    );
                  })}
                </TableBody>
              </Table>
            </Card>
          </div>
        </TabsContent>

        {/* ===== TAB 2: METRIC BASELINE VIEWER ===== */}
        <TabsContent value="baselines" className="mt-4">
          <div className="space-y-4">
            {/* Metric selector */}
            <Card className="p-4 bg-[#0f1629] border-sylion-border">
              <div className="flex items-center gap-3">
                <BarChart3 className="w-4 h-4 text-sylion-amber shrink-0" />
                <span className="text-xs font-medium">
                  Wybierz metrykę
                  <HelpTip text="Wybierz metrykę z listy dostępnych baseline'ów. Pokazane zostaną statystyki referencyjne i zakres normalny." />
                </span>
                <select
                  value={selectedMetric}
                  onChange={(e) => setSelectedMetric(e.target.value)}
                  className="flex-1 h-8 px-3 rounded-md text-[11px] bg-[#0a0f1e] border border-white/[0.06] text-foreground focus:outline-none focus:border-sylion-blue/40 focus:ring-1 focus:ring-sylion-blue/20 transition-colors"
                >
                  <option value="">-- Wybierz metrykę --</option>
                  {uniqueMetrics.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </Card>

            {/* Baseline stats */}
            {selectedMetric && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
                <Card className="p-5 bg-[#0f1629] border-sylion-border">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-sylion-blue" />
                    <h3 className="text-sm font-semibold">
                      Baseline dla: {selectedMetric}
                      <HelpTip text="Statystyki referencyjne metryki — mean ± std_dev definiują zakres 'normalny'. Próba poza tym zakresem = potencjalna anomalia." />
                    </h3>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { label: "Średnia", value: baseline.mean != null ? String(baseline.mean) : "---" },
                      { label: "Odchylenie standardowe", value: baseline.std_dev != null ? String(baseline.std_dev) : "---" },
                      { label: "Minimum", value: baseline.min != null ? String(baseline.min) : "---" },
                      { label: "Maksimum", value: baseline.max != null ? String(baseline.max) : "---" },
                      { label: "Liczba próbek", value: baseline.sample_count != null ? String(baseline.sample_count) : "---" },
                      { label: "Ostatnia aktualizacja", value: fmtTimestamp(baseline.last_updated) },
                    ].map((item) => (
                      <div key={item.label} className="flex items-center justify-between text-[11px] px-3 py-2 rounded-lg bg-white/[0.02]">
                        <span className="text-muted-foreground">{item.label}</span>
                        <span className="font-mono text-foreground">{item.value}</span>
                      </div>
                    ))}
                  </div>

                  {/* Visual range bar */}
                  {baseline.min != null && baseline.max != null && (
                    <div className="mt-4 pt-4 border-t border-border/30">
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
                        <span>Zakres</span>
                        <span className="font-mono">{baseline.min} - {baseline.max}</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted/30 overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-sylion-blue"
                          initial={{ width: 0 }}
                          animate={{ width: "100%" }}
                          transition={{ duration: 0.6 }}
                        />
                      </div>
                      {baseline.mean != null && (
                        <div className="relative mt-1">
                          <div
                            className="absolute top-0 h-4 w-px bg-sylion-amber"
                            style={{
                              left: baseline.max > baseline.min
                                ? `${Math.min(100, Math.max(0, ((baseline.mean - baseline.min) / (baseline.max - baseline.min)) * 100))}%`
                                : "50%",
                            }}
                          />
                          <span
                            className="absolute top-5 text-[9px] text-sylion-amber font-mono -translate-x-1/2"
                            style={{
                              left: baseline.max > baseline.min
                                ? `${Math.min(100, Math.max(0, ((baseline.mean - baseline.min) / (baseline.max - baseline.min)) * 100))}%`
                                : "50%",
                            }}
                          >
                            średnia: {baseline.mean}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              </motion.div>
            )}

            {!selectedMetric && (
              <Card className="p-12 bg-[#0f1629] border-sylion-border flex flex-col items-center justify-center text-center">
                <BarChart3 className="w-8 h-8 text-muted-foreground/30 mb-3" />
                <p className="text-xs text-muted-foreground">Wybierz metrykę powyżej, aby zobaczyć jej statystyki baseline'u</p>
                <p className="text-[10px] text-muted-foreground/50 mt-1">
                  Dostępne metryki: {baselinesTracked}
                </p>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
