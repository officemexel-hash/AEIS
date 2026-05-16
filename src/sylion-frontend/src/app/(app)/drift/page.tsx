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
import { useHealth, useApi, useConfigDrifts } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  RefreshCw,
  WifiOff,
  Search,
  ArrowUpDown,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Activity,
  FileWarning,
  ScanSearch,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface ConfigDriftEntry {
  drift_id?: string;
  id?: string;
  config_key: string;
  expected_value: string;
  actual_value: string;
  severity: "critical" | "high" | "medium" | "low";
  detected_at: number | string;
  status: "active" | "resolved" | "ignored";
  module_id?: string;
  description?: string;
}

/* ============================================================
   Severity styles
   ============================================================ */

const severityStyles: Record<string, { badge: string; icon: React.ElementType }> = {
  critical: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    icon: ShieldAlert,
  },
  high: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    icon: AlertTriangle,
  },
  medium: {
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    icon: AlertTriangle,
  },
  low: {
    badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    icon: Activity,
  },
};

const statusBadgeStyles: Record<string, string> = {
  active: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
  resolved: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
  ignored: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
};

/* ============================================================
   Helpers
   ============================================================ */

function formatDetectedAt(ts: number | string): string {
  if (!ts) return "---";
  const date = typeof ts === "number" ? (ts > 1e12 ? new Date(ts) : new Date(ts * 1000)) : new Date(ts);
  if (isNaN(date.getTime())) return "---";
  return date.toLocaleString();
}

/* ============================================================
   Page Component
   ============================================================ */

export default function DriftPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const backendLive = healthRaw.status === "ok";

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [scanning, setScanning] = useState(false);
  const [sortField, setSortField] = useState<"severity" | "detected_at">("detected_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Fetch drift data from the monitoring endpoint
  const { data: driftsData, refresh: refreshDrifts } = useConfigDrifts(
    statusFilter !== "all" ? statusFilter : undefined
  );

  const drifts: ConfigDriftEntry[] = driftsData.drifts ?? [];

  /* ---------- Derived summary ---------- */
  const totalCount = drifts.length;
  const activeCount = drifts.filter((d) => d.status === "active").length;
  const resolvedCount = drifts.filter((d) => d.status === "resolved").length;
  const criticalCount = drifts.filter(
    (d) => d.severity === "critical" || d.severity === "high"
  ).length;

  /* ---------- Sort ---------- */
  const sortedDrifts = useMemo(() => {
    const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    const list = [...drifts];
    list.sort((a, b) => {
      let cmp = 0;
      if (sortField === "severity") {
        cmp = (severityOrder[a.severity] ?? 4) - (severityOrder[b.severity] ?? 4);
      } else {
        const aTs = typeof a.detected_at === "number" ? a.detected_at : new Date(a.detected_at).getTime();
        const bTs = typeof b.detected_at === "number" ? b.detected_at : new Date(b.detected_at).getTime();
        cmp = aTs - bTs;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [drifts, sortField, sortDir]);

  /* ---------- Toggle sort ---------- */
  const toggleSort = useCallback((field: "severity" | "detected_at") => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  }, [sortField]);

  /* ---------- Run scan ---------- */
  const handleRunScan = useCallback(() => {
    setScanning(true);
    api.listConfigDrifts()
      .then(() => refreshDrifts())
      .catch(() => {})
      .finally(() => setScanning(false));
  }, [refreshDrifts]);

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-48 bg-muted animate-pulse rounded" />
            <div className="h-4 w-64 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-8 w-48 bg-muted animate-pulse rounded-lg" />
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
            <FileWarning className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Dryf konfiguracji
              <HelpTip text="Wykrywanie dryfu modeli i konfiguracji — gdy odpowiedzi/parametry zaczynają odbiegać od baseline'u (np. po update modelu providera). Próg domyślnie 5% kosinus-similarity vs golden set; alert + auto-fallback gdy przekroczony." />
            </h1>
            <p className="text-sm text-muted-foreground">Monitoring spójności konfiguracji między modułami</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane o dryfie konfiguracji wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => fetchHealth()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-amber/10 border border-sylion-amber/20 flex items-center justify-center">
            <FileWarning className="w-4 h-4 text-sylion-amber" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Dryf konfiguracji
              <HelpTip text="Wykrywanie dryfu modeli i konfiguracji — gdy odpowiedzi/parametry zaczynają odbiegać od baseline'u (np. po update modelu providera). Próg domyślnie 5% kosinus-similarity vs golden set; alert + auto-fallback gdy przekroczony." />
            </h1>
            <p className="text-sm text-muted-foreground">Monitoring spójności konfiguracji między modułami</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { fetchHealth(); refreshDrifts(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRunScan}
            disabled={scanning}
          >
            {scanning ? (
              <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <ScanSearch className="w-3.5 h-3.5 mr-1.5" />
            )}
            {scanning ? "Skanowanie..." : "Uruchom skan"}
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS (4 cards) ====== */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: "Łącznie dryfów",
            tip: "Łączna liczba odchyleń od oczekiwanego stanu konfiguracji we wszystkich modułach.",
            value: totalCount,
            icon: Activity,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
          },
          {
            label: "Aktywne dryfy",
            tip: "Niezamknięte dryfy wymagające reakcji. >0 = sprawdź szczegóły i podejmij działanie naprawcze lub zignoruj świadomie.",
            value: activeCount,
            icon: AlertTriangle,
            color: activeCount > 0 ? "text-sylion-red" : "text-sylion-green",
            bgColor: activeCount > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
          },
          {
            label: "Rozwiązane dryfy",
            tip: "Dryfy oznaczone jako rozwiązane. Wartość historyczna — pokazuje trend usuwania problemów.",
            value: resolvedCount,
            icon: CheckCircle2,
            color: "text-sylion-green",
            bgColor: "bg-sylion-green/10",
          },
          {
            label: "Krytyczne dryfy",
            tip: "Suma dryfów o poziomie critical i high. Każdy z nich blokuje deploy/auto-promotion.",
            value: criticalCount,
            icon: ShieldAlert,
            color: criticalCount > 0 ? "text-sylion-red" : "text-sylion-green",
            bgColor: criticalCount > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
          },
        ].map((stat) => {
          const SIcon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
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

      {/* ====== FILTER BAR ====== */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
          Filtr statusu
          <HelpTip text="Filtruj dryfy po statusie. Aktywne wymagają reakcji; Zignorowane = świadomie pominięte; Rozwiązane = już naprawione." />
        </span>
        <div className="flex items-center gap-1">
          {(["all", "active", "resolved", "ignored"] as const).map((f) => {
            const labelMap = { all: "Wszystkie", active: "Aktywne", resolved: "Rozwiązane", ignored: "Zignorowane" };
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
                  ({drifts.filter((d) => d.status === f).length})
                </span>
              )}
            </Button>
            );
          })}
        </div>
      </div>

      {/* ====== DRIFT TABLE ====== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <h3 className="text-xs font-medium text-muted-foreground">
            Wykryte dryfy konfiguracji
            <HelpTip text="Tabela wszystkich odchyleń klucz-wartość konfiguracji od oczekiwanego stanu. Sortowalna po poziomie i czasie wykrycia." />
          </h3>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            {sortedDrifts.length} wpisów
          </span>
        </div>

        {sortedDrifts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <CheckCircle2 className="w-8 h-8 mb-3 text-sylion-green/40" />
            <p className="text-sm font-medium">Nie wykryto dryfów konfiguracji</p>
            <p className="text-[10px] mt-1 text-muted-foreground/60">
              Konfiguracja jest spójna we wszystkich modułach
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-border/20 hover:bg-transparent">
                <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Klucz konfiguracji
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Wartość oczekiwana
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Wartość rzeczywista
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
                  onClick={() => toggleSort("detected_at")}
                >
                  <div className="flex items-center gap-1">
                    Wykryto
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Status
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedDrifts.map((drift, idx) => {
                const sevStyle = severityStyles[drift.severity] ?? severityStyles.low;
                const SevIcon = sevStyle.icon;
                const statusStyle = statusBadgeStyles[drift.status] ?? statusBadgeStyles.active;

                return (
                  <motion.tr
                    key={drift.drift_id ?? drift.id ?? idx}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15, delay: idx * 0.02 }}
                    className={cn(
                      "border-border/10 transition-colors hover:bg-muted/20",
                      drift.severity === "critical" && "bg-sylion-red/[0.02]",
                    )}
                  >
                    <TableCell className="text-xs font-mono font-medium">
                      {drift.config_key}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {drift.expected_value}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {drift.actual_value}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn("text-[9px] gap-1", sevStyle.badge)}>
                        <SevIcon className="w-2.5 h-2.5" />
                        {drift.severity.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-[10px] text-muted-foreground font-mono">
                      {formatDetectedAt(drift.detected_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn("text-[9px]", statusStyle)}>
                        {drift.status.toUpperCase()}
                      </Badge>
                    </TableCell>
                  </motion.tr>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
