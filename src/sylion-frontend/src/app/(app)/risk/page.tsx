"use client";

import { useMemo } from "react";
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
import { useHealth, useRiskScores, useChangeProposals } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Shield,
  WifiOff,
  RefreshCw,
  AlertTriangle,
  Activity,
  FileText,
  TrendingUp,
  ChevronRight,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface RiskScore {
  target_id: string;
  target_type: string;
  composite_score: number;
  risk_level: string;
  contributing_factors?: string[];
  module_id?: string;
  assessed_at?: number;
}

interface ChangeProposal {
  proposal_id: string;
  title: string;
  status: string;
  risk_impact?: string;
  submitted_at?: number;
  description?: string;
}

/* ============================================================
   Risk level styling
   ============================================================ */

const riskLevelStyles: Record<string, { badge: string; dot: string; text: string }> = {
  critical: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    dot: "bg-sylion-red",
    text: "text-sylion-red",
  },
  high: {
    badge: "border-orange-400/30 text-orange-400 bg-orange-400/5",
    dot: "bg-orange-400",
    text: "text-orange-400",
  },
  medium: {
    badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
    dot: "bg-sylion-amber",
    text: "text-sylion-amber",
  },
  low: {
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    dot: "bg-sylion-green",
    text: "text-sylion-green",
  },
};

const proposalStatusStyles: Record<string, { badge: string; dot: string }> = {
  draft: {
    badge: "border-slate-400/30 text-slate-400 bg-slate-400/5",
    dot: "bg-slate-400",
  },
  review: {
    badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    dot: "bg-sylion-blue",
  },
  approved: {
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    dot: "bg-sylion-green",
  },
  rejected: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    dot: "bg-sylion-red",
  },
};

/* ============================================================
   Helpers
   ============================================================ */

function formatTimestamp(ts: number | undefined): string {
  if (!ts) return "---";
  const date = typeof ts === "number" && ts > 1e12 ? new Date(ts) : new Date(ts);
  return date.toLocaleDateString("pl-PL", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRiskStyles(level: string) {
  const normalized = (level || "low").toLowerCase();
  return riskLevelStyles[normalized] || riskLevelStyles.low;
}

function getProposalStatusStyles(status: string) {
  const normalized = (status || "draft").toLowerCase();
  return proposalStatusStyles[normalized] || proposalStatusStyles.draft;
}

/* ============================================================
   Page Component
   ============================================================ */

export default function RiskPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const healthData = healthRaw as { status: string; version: string; modules: number; endpoints: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const { data: riskData, refresh: refreshRisk } = useRiskScores();
  const { data: proposalsData, refresh: refreshProposals } = useChangeProposals();

  const scores: RiskScore[] = (riskData as any).scores ?? [];
  const proposals: ChangeProposal[] = (proposalsData as any).proposals ?? [];

  /* ---------- Derived stats ---------- */
  const avgRiskScore = useMemo(() => {
    if (scores.length === 0) return 0;
    const total = scores.reduce((sum, s) => sum + (s.composite_score ?? 0), 0);
    return Math.round(total / scores.length);
  }, [scores]);

  const highRiskCount = useMemo(() => {
    return scores.filter((s) => {
      const level = (s.risk_level || "").toLowerCase();
      return level === "critical" || level === "high";
    }).length;
  }, [scores]);

  const openProposalCount = useMemo(() => {
    return proposals.filter((p) => {
      const status = (p.status || "").toLowerCase();
      return status === "draft" || status === "review";
    }).length;
  }, [proposals]);

  const handleRefreshAll = () => {
    fetchHealth();
    refreshRisk();
    refreshProposals();
  };

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
            <Shield className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Ryzyko
              <HelpTip text="Ocena ryzyka modułów, decyzji i propozycji zmian. Wartości > 70 = krytyczne; wymagana eskalacja do human-gate. Kontrybutory pokazują, co podnosi score." />
            </h1>
            <p className="text-sm text-muted-foreground">Ocena ryzyka i zarządzanie zmianami</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Wyniki ryzyka, propozycje zmian i dane oceny wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
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
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Ryzyko
              <HelpTip text="Ocena ryzyka modułów, decyzji i propozycji zmian. Wartości > 70 = krytyczne; wymagana eskalacja do human-gate. Kontrybutory pokazują, co podnosi score." />
            </h1>
            <p className="text-sm text-muted-foreground">Ocena ryzyka i zarządzanie zmianami</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS (3) ====== */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            label: "Średnie ryzyko",
            tip: "Średnia arytmetyczna ze wszystkich ocenionych targetów. >70 = krytyczne; 40-70 = umiarkowane; <40 = niskie.",
            value: scores.length > 0 ? avgRiskScore : "---",
            icon: TrendingUp,
            color: avgRiskScore >= 70 ? "text-sylion-red" : avgRiskScore >= 40 ? "text-sylion-amber" : "text-sylion-green",
            bgColor: avgRiskScore >= 70 ? "bg-sylion-red/10" : avgRiskScore >= 40 ? "bg-sylion-amber/10" : "bg-sylion-green/10",
          },
          {
            label: "Pozycje wysokiego ryzyka",
            tip: "Liczba targetów z poziomem critical lub high. Każdy z nich powinien mieć aktywny mitigation plan.",
            value: highRiskCount,
            icon: AlertTriangle,
            color: highRiskCount > 0 ? "text-sylion-red" : "text-sylion-green",
            bgColor: highRiskCount > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
          },
          {
            label: "Otwarte propozycje",
            tip: "Propozycje zmian w stanie draft/review oczekujące na decyzję rady lub human-gate.",
            value: openProposalCount,
            icon: FileText,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
          },
        ].map((stat, i) => {
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

      {/* ====== RISK SCORES TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.15 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-sylion-red" />
              <h3 className="text-xs font-semibold">
                Wyniki ryzyka
                <HelpTip text="Oceny ryzyka per-target z czynnikami przyczyniającymi się. Składnik composite jest sumą ważoną z czynników security/cost/availability." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {scores.length} pozycji
              </Badge>
            </div>
          </div>

          {scores.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Shield className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-xs">Brak dostępnych ocen ryzyka</p>
              <p className="text-[10px] mt-1 opacity-60">Oceny pojawią się tutaj po obliczeniu przez backend</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border/20 hover:bg-transparent">
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">ID celu</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Typ celu</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Wynik łączny</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Poziom ryzyka</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Czynniki przyczyniające się</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scores.map((score, idx) => {
                  const styles = getRiskStyles(score.risk_level);
                  return (
                    <TableRow key={score.target_id ?? idx} className="border-border/10 hover:bg-muted/10">
                      <TableCell className="text-xs font-mono">{score.target_id}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{score.target_type}</TableCell>
                      <TableCell className="text-xs">
                        <div className="flex items-center gap-2">
                          <span className={cn("font-mono font-semibold", styles.text)}>
                            {score.composite_score ?? 0}
                          </span>
                          <div className="w-16 h-1.5 rounded-full bg-muted/30 overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all duration-500",
                                styles.dot
                              )}
                              style={{ width: `${Math.min(100, score.composite_score ?? 0)}%` }}
                            />
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("text-[9px]", styles.badge)}>
                          <span className={cn("w-1.5 h-1.5 rounded-full mr-1", styles.dot)} />
                          {(score.risk_level || "low").toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[250px]">
                        {score.contributing_factors && score.contributing_factors.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {score.contributing_factors.slice(0, 3).map((factor, fi) => (
                              <Badge
                                key={fi}
                                variant="outline"
                                className="text-[8px] border-border/40 text-muted-foreground"
                              >
                                {factor}
                              </Badge>
                            ))}
                            {score.contributing_factors.length > 3 && (
                              <Badge
                                variant="outline"
                                className="text-[8px] border-border/40 text-muted-foreground"
                              >
                                +{score.contributing_factors.length - 3}
                              </Badge>
                            )}
                          </div>
                        ) : (
                          <span className="opacity-50">---</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Card>
      </motion.div>

      {/* ====== CHANGE PROPOSALS TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.25 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">
                Propozycje zmian
                <HelpTip text="Lista wniosków o zmianę konfiguracji/architektury z oszacowanym wpływem na ryzyko. Każda przechodzi przez bramki D0-D5 zanim zostanie wdrożona." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {proposals.length} propozycji
              </Badge>
            </div>
          </div>

          {proposals.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <FileText className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-xs">Brak dostępnych propozycji zmian</p>
              <p className="text-[10px] mt-1 opacity-60">Propozycje pojawią się tutaj po przesłaniu przez proces governance</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border/20 hover:bg-transparent">
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">ID propozycji</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Tytuł</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Status</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Wpływ ryzyka</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Złożono</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {proposals.map((proposal, idx) => {
                  const statusStyles = getProposalStatusStyles(proposal.status);
                  const riskStyles = getRiskStyles(proposal.risk_impact || "low");
                  return (
                    <TableRow key={proposal.proposal_id ?? idx} className="border-border/10 hover:bg-muted/10">
                      <TableCell className="text-xs font-mono">{proposal.proposal_id}</TableCell>
                      <TableCell className="text-xs">
                        <div className="flex items-center gap-1.5 max-w-[300px]">
                          <ChevronRight className="w-3 h-3 text-muted-foreground/40 shrink-0" />
                          <span className="truncate">{proposal.title}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("text-[9px]", statusStyles.badge)}>
                          <span className={cn("w-1.5 h-1.5 rounded-full mr-1", statusStyles.dot)} />
                          {(proposal.status || "draft").toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {proposal.risk_impact ? (
                          <Badge variant="outline" className={cn("text-[9px]", riskStyles.badge)}>
                            <span className={cn("w-1.5 h-1.5 rounded-full mr-1", riskStyles.dot)} />
                            {proposal.risk_impact.toUpperCase()}
                          </Badge>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/50">---</span>
                        )}
                      </TableCell>
                      <TableCell className="text-[11px] text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <Activity className="w-3 h-3 text-muted-foreground/40" />
                          {formatTimestamp(proposal.submitted_at)}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
