"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { useApi } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  ShieldCheck,
  RefreshCw,
  WifiOff,
  AlertTriangle,
  XCircle,
  Info,
  Activity,
  FileSearch,
  CheckCircle2,
  Bug,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Finding {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  module: string;
  status: "open" | "acknowledged" | "remediated" | "false_positive";
  recommendation: string;
  detected_at?: number;
}

interface Scan {
  id: string;
  status: string;
  started_at?: number;
  completed_at?: number;
}

interface FindingsData {
  findings: Finding[];
}

interface ScansData {
  scans: Scan[];
}

/* ============================================================
   Helpers
   ============================================================ */

const severityStyles: Record<string, { badge: string; text: string; iconBg: string }> = {
  critical: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    text: "text-sylion-red",
    iconBg: "bg-sylion-red/10",
  },
  high: {
    badge: "border-orange-400/30 text-orange-400 bg-orange-400/5",
    text: "text-orange-400",
    iconBg: "bg-orange-400/10",
  },
  medium: {
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    text: "text-sylion-amber",
    iconBg: "bg-sylion-amber/10",
  },
  low: {
    badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    text: "text-sylion-blue",
    iconBg: "bg-sylion-blue/10",
  },
  info: {
    badge: "border-muted-foreground/30 text-muted-foreground bg-muted/20",
    text: "text-muted-foreground",
    iconBg: "bg-muted/20",
  },
};

const statusBadgeStyles: Record<string, string> = {
  open: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
  acknowledged: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
  remediated: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
  false_positive: "border-muted-foreground/30 text-muted-foreground bg-muted/20",
};

function severityIcon(severity: string): React.ElementType {
  switch (severity) {
    case "critical": return XCircle;
    case "high": return AlertTriangle;
    case "medium": return AlertTriangle;
    case "low": return Info;
    default: return Bug;
  }
}

/* ============================================================
   Page Component
   ============================================================ */

export default function SecurityScanPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: findingsData, refresh: refreshFindings } = useApi(
    () => api.listSecurityFindings() as Promise<FindingsData>,
    { findings: [] } as FindingsData,
    15000
  );

  const { data: scansData } = useApi(
    () => api.listSecurityScans() as Promise<ScansData>,
    { scans: [] } as ScansData,
    15000
  );

  const findings = findingsData.findings || [];
  const scans = scansData.scans || [];

  /* ---------- Derived stats ---------- */
  const openFindings = useMemo(
    () => findings.filter((f) => f.status === "open").length,
    [findings]
  );
  const criticalCount = useMemo(
    () => findings.filter((f) => f.severity === "critical" || f.severity === "high").length,
    [findings]
  );
  const completedScans = useMemo(
    () => scans.filter((s) => s.status === "completed" || s.status === "done").length,
    [scans]
  );

  /* ---------- Summary cards ---------- */
  const summaryCards = [
    {
      label: "Otwarte wyniki",
      tip: "Liczba podatności w stanie open. >0 = wymagana reakcja zgodnie z severity (krytyczne w 24h, wysokie w 7 dni).",
      value: openFindings,
      icon: FileSearch,
      color: openFindings > 0 ? "text-sylion-red" : "text-sylion-green",
      bgColor: openFindings > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
    },
    {
      label: "Krytyczne / Wysokie",
      tip: "Suma podatności o severity critical+high. Każda blokuje promotion do produkcji aż do remediacji lub udokumentowania jako false positive.",
      value: criticalCount,
      icon: XCircle,
      color: criticalCount > 0 ? "text-orange-400" : "text-sylion-green",
      bgColor: criticalCount > 0 ? "bg-orange-400/10" : "bg-sylion-green/10",
    },
    {
      label: "Ukończone skany",
      tip: "Liczba zakończonych przebiegów skanu. Trend rosnący = aktywny monitoring; brak nowych skanów = sprawdź harmonogram.",
      value: completedScans,
      icon: CheckCircle2,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
  ];

  /* ---------- Sorted findings: critical first ---------- */
  const sortedFindings = useMemo(() => {
    const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    const statusOrder: Record<string, number> = { open: 0, acknowledged: 1, remediated: 2, false_positive: 3 };
    return [...findings].sort((a, b) => {
      const sevDiff = (severityOrder[a.severity] ?? 5) - (severityOrder[b.severity] ?? 5);
      if (sevDiff !== 0) return sevDiff;
      return (statusOrder[a.status] ?? 3) - (statusOrder[b.status] ?? 3);
    });
  }, [findings]);

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
            <ShieldCheck className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Skanowanie bezpieczeństwa
              <HelpTip text="Centrum audytu podatności — SAST/SCA/secrets-scan/CVE. Wyniki są klasyfikowane wg severity (critical-info) i mają jasną rekomendację remediacji. Krytyczne blokują deploy." />
            </h1>
            <p className="text-sm text-muted-foreground">Wyniki podatności i skanowania</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane audytu bezpieczeństwa wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { fetchHealth(); refreshFindings(); }}>
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
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Skanowanie bezpieczeństwa
              <HelpTip text="Centrum audytu podatności — SAST/SCA/secrets-scan/CVE. Wyniki są klasyfikowane wg severity (critical-info) i mają jasną rekomendację remediacji. Krytyczne blokują deploy." />
            </h1>
            <p className="text-sm text-muted-foreground">Wyniki podatności i skanowania</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refreshFindings()}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Odśwież
        </Button>
      </div>

      {/* ====== SUMMARY CARDS ====== */}
      <div className="grid grid-cols-3 gap-3">
        {summaryCards.map((stat) => {
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

      {/* ====== FINDINGS TABLE ====== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-xs font-medium text-muted-foreground">
              Wyniki bezpieczeństwa
              <HelpTip text="Wszystkie wykryte podatności i naruszenia — z modułem, severity, statusem (open/acknowledged/remediated/false_positive) i rekomendacją działania." />
            </h3>
          </div>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            Sortowane według priorytetu
          </span>
        </div>
        <div className="divide-y divide-border/20">
          {sortedFindings.map((finding, idx) => {
            const sevStyles = severityStyles[finding.severity] || severityStyles.info;
            const statBadge = statusBadgeStyles[finding.status] || "border-border/50 text-muted-foreground bg-muted/20";
            const SevIcon = severityIcon(finding.severity);
            return (
              <motion.div
                key={finding.id || idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.03, duration: 0.2 }}
                className="px-4 py-3 hover:bg-muted/20 transition-colors"
              >
                <div className="flex items-center gap-3">
                  {/* Severity icon */}
                  <div className={cn("w-6 h-6 rounded-md flex items-center justify-center shrink-0", sevStyles.iconBg)}>
                    <SevIcon className={cn("w-3 h-3", sevStyles.text)} />
                  </div>

                  {/* Title */}
                  <span className="text-xs font-medium flex-1 min-w-0 truncate">{finding.title}</span>

                  {/* Severity badge */}
                  <Badge variant="outline" className={cn("text-[9px] shrink-0", sevStyles.badge)}>
                    {finding.severity.toUpperCase()}
                  </Badge>

                  {/* Module */}
                  <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground shrink-0">
                    {finding.module}
                  </Badge>

                  {/* Status badge */}
                  <Badge variant="outline" className={cn("text-[9px] shrink-0", statBadge)}>
                    {finding.status.replace("_", " ").toUpperCase()}
                  </Badge>
                </div>

                {/* Recommendation */}
                {finding.recommendation && (
                  <p className="text-[10px] text-muted-foreground mt-1.5 pl-9 truncate">
                    {finding.recommendation}
                  </p>
                )}
              </motion.div>
            );
          })}

          {findings.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ShieldCheck className="w-6 h-6 text-sylion-green mb-2" />
              <p className="text-xs text-muted-foreground">Brak wyników bezpieczeństwa</p>
              <p className="text-[10px] text-muted-foreground mt-1">Wszystko w porządku — nie wykryto podatności</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
