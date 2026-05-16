"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth, useSlaPolicies } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Shield,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  WifiOff,
  Clock,
  Activity,
  Gauge,
  ListChecks,
  TrendingUp,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface SlaPolicy {
  policy_id: string;
  name: string;
  target_metric: string;
  threshold: number;
  current_value: number;
  status: "compliant" | "breached" | "at-risk";
  last_checked: number | string;
}

/* ============================================================
   Helpers
   ============================================================ */

function formatLastChecked(ts: number | string): string {
  if (!ts) return "---";
  const ms = typeof ts === "number" ? (ts > 1e12 ? ts : ts * 1000) : new Date(ts).getTime();
  const diff = Date.now() - ms;
  if (diff < 60000) return `${Math.floor(diff / 1000)}s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h temu`;
  return `${Math.floor(diff / 86400000)}d temu`;
}

function formatThreshold(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

/* ============================================================
   Status style maps
   ============================================================ */

const statusConfig: Record<
  string,
  { label: string; badge: string; icon: React.ElementType; text: string; dotBg: string }
> = {
  compliant: {
    label: "ZGODNE",
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    icon: CheckCircle2,
    text: "text-sylion-green",
    dotBg: "bg-sylion-green",
  },
  breached: {
    label: "NARUSZONE",
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    icon: XCircle,
    text: "text-sylion-red",
    dotBg: "bg-sylion-red",
  },
  "at-risk": {
    label: "ZAGROZONE",
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    icon: AlertTriangle,
    text: "text-sylion-amber",
    dotBg: "bg-sylion-amber",
  },
};

/* ============================================================
   Page Component
   ============================================================ */

export default function SlaPage() {
  /* ---------- Hook-driven data ---------- */
  const { data: healthRaw, refresh: fetchHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: slaData, refresh: fetchSla } = useSlaPolicies();
  const policies = (slaData as { policies: SlaPolicy[] }).policies ?? [];

  /* ---------- Derived counts ---------- */
  const counts = useMemo(() => {
    const total = policies.length;
    const compliant = policies.filter((p) => p.status === "compliant").length;
    const breached = policies.filter((p) => p.status === "breached").length;
    const atRisk = policies.filter((p) => p.status === "at-risk").length;
    return { total, compliant, breached, atRisk };
  }, [policies]);

  /* ---------- Compliance rate ---------- */
  const complianceRate = useMemo(() => {
    if (counts.total === 0) return 0;
    return Math.round((counts.compliant / counts.total) * 100);
  }, [counts]);

  /* ---------- Summary cards data ---------- */
  const summaryCards = [
    {
      label: "Łącznie polityk",
      tip: "Liczba zdefiniowanych polityk SLA — każda monitoruje konkretną metrykę vs próg.",
      value: counts.total,
      icon: ListChecks,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Zgodne",
      tip: "Polityki, których metryka mieści się w progu — system działa zgodnie z umową.",
      value: counts.compliant,
      icon: CheckCircle2,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Naruszone",
      tip: "Polityki przekroczone — wymagana eskalacja zgodnie z procedurą incydentów.",
      value: counts.breached,
      icon: XCircle,
      color: "text-sylion-red",
      bgColor: "bg-sylion-red/10",
    },
    {
      label: "Zagrożone",
      tip: "Polityki blisko progu (>80% wykorzystania). Sygnał ostrzegawczy — działaj proaktywnie.",
      value: counts.atRisk,
      icon: AlertTriangle,
      color: "text-sylion-amber",
      bgColor: "bg-sylion-amber/10",
    },
  ];

  /* ---------- Refresh handler ---------- */
  const handleRefresh = () => {
    fetchHealth();
    fetchSla();
  };

  /* ---------- Loading skeleton ---------- */
  if (!(healthRaw as any).status) {
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
            <Shield className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Monitor SLA
              <HelpTip text="Service Level Agreement — śledzenie zgodności metryk z umownymi progami. Naruszone SLA = automatyczna eskalacja + alert do operatora; zagrożone = sygnał wczesnego ostrzeżenia." />
            </h1>
            <p className="text-sm text-muted-foreground">Śledzenie zgodności umów SLA</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane polityk SLA i status zgodności wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Main content ---------- */
  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Monitor SLA
              <HelpTip text="Service Level Agreement — śledzenie zgodności metryk z umownymi progami. Naruszone SLA = automatyczna eskalacja + alert do operatora; zagrożone = sygnał wczesnego ostrzeżenia." />
            </h1>
            <p className="text-sm text-muted-foreground">Śledzenie zgodności umów SLA</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Compliance rate badge */}
          <Badge
            variant="outline"
            className={cn(
              "text-[10px] flex items-center gap-1.5",
              complianceRate >= 90
                ? "border-sylion-green/30 text-sylion-green bg-sylion-green/5"
                : complianceRate >= 70
                  ? "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5"
                  : "border-sylion-red/30 text-sylion-red bg-sylion-red/5"
            )}
          >
            <Activity className="w-3 h-3" />
            {complianceRate}% ZGODNE
          </Badge>

          {/* Refresh button */}
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS (4 columns) ====== */}
      <div className="grid grid-cols-4 gap-3">
        {summaryCards.map((stat, i) => {
          const SIcon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
            >
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                      {stat.label}
                      <HelpTip text={stat.tip} />
                    </p>
                    <p className={cn("text-xl font-semibold mt-1 font-mono", stat.color)}>
                      {stat.value}
                    </p>
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

      {/* ====== COMPLIANCE TREND AREA ====== */}
      <Card className="p-4 bg-[#0f1629] border-sylion-border">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-sylion-blue" />
          <h3 className="text-xs font-semibold">
            Trend zgodności
            <HelpTip text="Procentowy podział polityk wg statusu. Zielony = OK; amber = zagrożone; czerwony = naruszone. Cel: >90% zgodnych długoterminowo." />
          </h3>
          <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground ml-auto">
            <Clock className="w-2.5 h-2.5 mr-1" />
            Live
          </Badge>
        </div>
        <div className="flex items-center gap-4 text-[11px]">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sylion-green" />
            <span className="text-muted-foreground">Zgodne:</span>
            <span className="font-mono text-sylion-green">{counts.compliant}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sylion-red" />
            <span className="text-muted-foreground">Naruszone:</span>
            <span className="font-mono text-sylion-red">{counts.breached}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sylion-amber" />
            <span className="text-muted-foreground">Zagrożone:</span>
            <span className="font-mono text-sylion-amber">{counts.atRisk}</span>
          </div>
          <div className="ml-auto text-muted-foreground">
            Łącznie: <span className={cn(
              "font-semibold font-mono",
              complianceRate >= 90 ? "text-sylion-green" : complianceRate >= 70 ? "text-sylion-amber" : "text-sylion-red"
            )}>
              {complianceRate}%
            </span>
          </div>
        </div>
        {/* Text-based trend bar */}
        <div className="mt-3 h-2.5 rounded-full bg-muted/30 overflow-hidden flex">
          {counts.total > 0 && (
            <>
              <div
                className="h-full bg-sylion-green transition-all duration-500"
                style={{ width: `${(counts.compliant / counts.total) * 100}%` }}
              />
              <div
                className="h-full bg-sylion-amber transition-all duration-500"
                style={{ width: `${(counts.atRisk / counts.total) * 100}%` }}
              />
              <div
                className="h-full bg-sylion-red transition-all duration-500"
                style={{ width: `${(counts.breached / counts.total) * 100}%` }}
              />
            </>
          )}
        </div>
      </Card>

      {/* ====== SLA POLICY TABLE ====== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gauge className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-xs font-medium text-muted-foreground">
              Polityki SLA
              <HelpTip text="Każda polityka definiuje metrykę docelową, próg i okno czasowe. Kliknij wiersz, aby zobaczyć historię — wszystkie polityki muszą być monitorowane co 1-15 min." />
            </h3>
          </div>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            {policies.length} polityk
          </span>
        </div>

        {/* Table header */}
        <div className="grid grid-cols-12 gap-2 px-4 py-2.5 text-[10px] text-muted-foreground uppercase tracking-wider border-b border-border/20 bg-muted/[0.03]">
          <div className="col-span-3">Nazwa polityki</div>
          <div className="col-span-2">Metryka docelowa</div>
          <div className="col-span-1 text-right">Próg</div>
          <div className="col-span-1 text-right">Bieżące</div>
          <div className="col-span-2 text-center">Status</div>
          <div className="col-span-3 text-right">Ostatnia kontrola</div>
        </div>

        {/* Table body */}
        {policies.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Shield className="w-6 h-6 mb-2 opacity-30" />
            <p className="text-xs">Brak zdefiniowanych polityk SLA</p>
            <p className="text-[10px] mt-1 opacity-60">Polityki pojawią się tutaj po konfiguracji w backendzie</p>
          </div>
        )}

        <div className="divide-y divide-border/20">
          {policies.map((policy, idx) => {
            const cfg = statusConfig[policy.status] ?? statusConfig.compliant;
            const StatusIcon = cfg.icon;

            return (
              <motion.div
                key={policy.policy_id ?? idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: idx * 0.02 }}
                className={cn(
                  "grid grid-cols-12 gap-2 px-4 py-3 items-center text-xs transition-colors hover:bg-muted/20",
                  policy.status === "breached" && "bg-sylion-red/[0.02]",
                  policy.status === "at-risk" && "bg-sylion-amber/[0.02]"
                )}
              >
                {/* Policy Name */}
                <div className="col-span-3 flex items-center gap-2 min-w-0">
                  <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", cfg.dotBg)} />
                  <span className="font-medium truncate">{policy.name || policy.policy_id}</span>
                </div>

                {/* Target Metric */}
                <div className="col-span-2 text-muted-foreground truncate">
                  {policy.target_metric || "---"}
                </div>

                {/* Threshold */}
                <div className="col-span-1 text-right font-mono text-muted-foreground">
                  {formatThreshold(policy.threshold)}
                </div>

                {/* Current Value */}
                <div className={cn(
                  "col-span-1 text-right font-mono",
                  policy.status === "compliant"
                    ? "text-sylion-green"
                    : policy.status === "breached"
                      ? "text-sylion-red"
                      : "text-sylion-amber"
                )}>
                  {policy.current_value != null ? formatThreshold(policy.current_value) : "---"}
                </div>

                {/* Status Badge */}
                <div className="col-span-2 flex justify-center">
                  <Badge
                    variant="outline"
                    className={cn("text-[9px] flex items-center gap-1", cfg.badge)}
                  >
                    <StatusIcon className="w-3 h-3" />
                    {cfg.label}
                  </Badge>
                </div>

                {/* Last Checked */}
                <div className="col-span-3 text-right text-muted-foreground flex items-center justify-end gap-1">
                  <Clock className="w-2.5 h-2.5 shrink-0" />
                  <span>{formatLastChecked(policy.last_checked)}</span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
