"use client";

import { useMemo, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth, useGovernanceGates, useHumanGateRequests } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Shield,
  RefreshCw,
  WifiOff,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Eye,
  ThumbsUp,
  ThumbsDown,
  UserCheck,
  BarChart3,
  Layers,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface GovernanceGate {
  gate_id: string;
  name: string;
  type: string;
  scope: string;
  criteria: string;
  description?: string;
  status?: string;
  pass_rate?: number;
}

interface HumanGateRequest {
  request_id: string;
  gate_id: string;
  gate_name?: string;
  title: string;
  description?: string;
  status: "pending" | "approved" | "rejected" | "needs_info";
  requested_by?: string;
  requested_at?: number;
  context?: string;
}

/* ============================================================
   Helpers
   ============================================================ */

function gateTypeBadge(type: string): { badge: string; icon: React.ElementType } {
  switch (type) {
    case "human":
      return { badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5", icon: UserCheck };
    case "automated":
      return { badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5", icon: CheckCircle2 };
    case "hybrid":
      return { badge: "border-purple-400/30 text-purple-400 bg-purple-400/5", icon: Eye };
    default:
      return { badge: "border-muted-foreground/30 text-muted-foreground bg-muted-foreground/5", icon: Shield };
  }
}

function formatRequestedAt(ts?: number): string {
  if (!ts) return "---";
  const diff = Date.now() - ts;
  if (diff < 5000) return "przed chwilą";
  if (diff < 60000) return `${Math.floor(diff / 1000)}s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h temu`;
  return `${Math.floor(diff / 86400000)}d temu`;
}

/* ============================================================
   Page Component
   ============================================================ */

export default function GatesPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const { data: gatesData, refresh: refreshGates } = useGovernanceGates();
  const { data: requestsData, refresh: refreshRequests } = useHumanGateRequests();

  const healthData = healthRaw as { status: string; version?: string; modules?: number; endpoints?: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const gates: GovernanceGate[] = useMemo(() => gatesData.gates ?? [], [gatesData.gates]);
  const requests: HumanGateRequest[] = useMemo(() => requestsData.requests ?? [], [requestsData.requests]);

  const [actioningId, setActioningId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refreshAll = () => {
    refreshHealth();
    refreshGates();
    refreshRequests();
  };

  /* ---------- Derived: summary stats ---------- */
  const totalGates = gates.length;
  const avgPassRate = useMemo(() => {
    const withRate = gates.filter((g) => g.pass_rate !== undefined && g.pass_rate !== null);
    if (withRate.length === 0) return 0;
    const sum = withRate.reduce((acc, g) => acc + (g.pass_rate ?? 0), 0);
    return Math.round(sum / withRate.length);
  }, [gates]);
  const pendingReviews = useMemo(() => requests.filter((r) => r.status === "pending").length, [requests]);

  /* ---------- Action handlers ---------- */
  const handleReview = useCallback(async (
    requestId: string,
    decision: "approved" | "rejected" | "needs_info",
  ) => {
    setActioningId(requestId);
    setActionError(null);
    try {
      await api.submitHumanReview(requestId, {
        decision,
        reviewer: "operator-dashboard",
        rationale:
          decision === "needs_info"
            ? "Operator wymaga doprecyzowania przed zatwierdzeniem HumanGate."
            : `Operator dashboard: ${decision}`,
      });
      refreshRequests();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się zapisać decyzji HumanGate");
    } finally {
      setActioningId(null);
    }
  }, [refreshRequests]);

  const handleApprove = useCallback((requestId: string) => handleReview(requestId, "approved"), [handleReview]);
  const handleNeedsInfo = useCallback((requestId: string) => handleReview(requestId, "needs_info"), [handleReview]);
  const handleReject = useCallback((requestId: string) => handleReview(requestId, "rejected"), [handleReview]);

  /* ---------- Loading skeleton ---------- */
  const loading = healthRaw.status === "unknown";

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
              Bramki decyzyjne
              <HelpTip text="Bramki decyzyjne D0-D5 — punkty audytu w lifecycle decyzji rady. Każda bramka = obowiązkowy wartownik (cost, security) + opcjonalny human-gate. Bramka NIE PUSZCZA = decyzja blokowana." />
            </h1>
            <p className="text-sm text-muted-foreground">Punkty kontrolne decyzji i przepływ przeglądu ludzkiego</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane bramek governance wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Stats cards ---------- */
  const statsCards = [
    {
      label: "Łącznie bramek",
      tip: "Liczba zarejestrowanych bramek decyzyjnych. Każda blokuje określoną klasę decyzji (D0-D5) do czasu spełnienia kryteriów.",
      value: totalGates,
      icon: Layers,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Średnia zdawalność",
      tip: "Procent decyzji, które przeszły przez bramki bez interwencji. <90% = sprawdź konfigurację kryteriów.",
      value: `${avgPassRate}%`,
      icon: avgPassRate >= 90 ? CheckCircle2 : avgPassRate >= 70 ? AlertTriangle : XCircle,
      color: avgPassRate >= 90 ? "text-sylion-green" : avgPassRate >= 70 ? "text-sylion-amber" : "text-sylion-red",
      bgColor: avgPassRate >= 90 ? "bg-sylion-green/10" : avgPassRate >= 70 ? "bg-sylion-amber/10" : "bg-sylion-red/10",
    },
    {
      label: "Oczekujące przeglądy",
      tip: "Wnioski human-gate czekające na decyzję operatora. Każdy blokuje pipeline — rozpatrz w priorytecie.",
      value: pendingReviews,
      icon: Clock,
      color: pendingReviews > 0 ? "text-sylion-amber" : "text-sylion-green",
      bgColor: pendingReviews > 0 ? "bg-sylion-amber/10" : "bg-sylion-green/10",
    },
  ];

  /* ---------- Pending requests for the human gate section ---------- */
  const pendingRequests = requests.filter((r) => r.status === "pending");

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
              Bramki decyzyjne
              <HelpTip text="Bramki decyzyjne D0-D5 — punkty audytu w lifecycle decyzji rady. Każda bramka = obowiązkowy wartownik (cost, security) + opcjonalny human-gate. Bramka NIE PUSZCZA = decyzja blokowana." />
            </h1>
            <p className="text-sm text-muted-foreground">Punkty kontrolne decyzji i przepływ przeglądu ludzkiego</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {pendingReviews > 0 && (
            <Badge variant="outline" className="text-[10px] flex items-center gap-1.5 border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5">
              <span className="w-1.5 h-1.5 rounded-full bg-sylion-amber animate-pulse" />
              {pendingReviews} OCZEKUJE
            </Badge>
          )}

          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== STATS ROW (3 cards) ====== */}
      <div className="grid grid-cols-3 gap-3">
        {statsCards.map((stat, i) => {
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

      {/* ====== GATES TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.2 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">
                Bramki governance
                <HelpTip text="Wszystkie zarejestrowane bramki — typ (human/automated/hybrid), zakres (jaką klasę decyzji obsługują) oraz kryterium pass/fail." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {totalGates} bramek
              </Badge>
            </div>
          </div>

          {gates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Shield className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">Brak skonfigurowanych bramek governance</p>
              <p className="text-[10px] mt-1 opacity-60">Zarejestruj bramki przez Governance API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Nazwa</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Typ</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Zakres</th>
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Kryterium</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/10">
                  {gates
                    .sort((a, b) => (a.name ?? "").localeCompare(b.name ?? ""))
                    .map((gate, idx) => {
                      const typeInfo = gateTypeBadge(gate.type);
                      const TIcon = typeInfo.icon;

                      return (
                        <motion.tr
                          key={gate.gate_id ?? idx}
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.2, delay: 0.25 + idx * 0.03 }}
                          className="hover:bg-muted/10 transition-colors"
                        >
                          {/* Name */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-6 h-6 rounded-md flex items-center justify-center bg-sylion-blue/10">
                                <Shield className="w-3 h-3 text-sylion-blue" />
                              </div>
                              <div>
                                <span className="text-xs font-medium text-foreground">{gate.name ?? gate.gate_id}</span>
                                {gate.description && (
                                  <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">{gate.description}</p>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Type */}
                          <td className="px-4 py-3 text-center">
                            <Badge variant="outline" className={cn("text-[9px] uppercase font-semibold", typeInfo.badge)}>
                              <TIcon className="w-2.5 h-2.5 mr-1" />
                              {gate.type || "---"}
                            </Badge>
                          </td>

                          {/* Scope */}
                          <td className="px-4 py-3 text-center">
                            <span className="font-mono text-muted-foreground">{gate.scope || "---"}</span>
                          </td>

                          {/* Criteria */}
                          <td className="px-4 py-3">
                            <span className="text-muted-foreground truncate max-w-[300px] block">
                              {gate.criteria || "---"}
                            </span>
                          </td>
                        </motion.tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </motion.div>

      {/* ====== HUMAN GATE REQUESTS ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.35 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-sylion-amber" />
              <h3 className="text-xs font-semibold">
                Wnioski human-gate
                <HelpTip text="Wnioski wymagające decyzji człowieka — najczęściej dla decyzji D3+ (krytyczne). Każdy ma kontekst, gate_id i wnioskodawcę. Akceptuj/Odrzuć wpisuje się do audit-log." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {pendingRequests.length} oczekuje
              </Badge>
            </div>
          </div>

          {actionError && (
            <div className="mx-4 mt-3 rounded-md border border-sylion-red/30 bg-sylion-red/10 px-3 py-2 text-xs text-sylion-red">
              {actionError}
            </div>
          )}

          {pendingRequests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <CheckCircle2 className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">Brak oczekujących przeglądów</p>
              <p className="text-[10px] mt-1 opacity-60">Wszystkie wnioski human-gate zostały przetworzone</p>
            </div>
          ) : (
            <div className="divide-y divide-border/10">
              {pendingRequests.map((req, idx) => {
                const isActioning = actioningId === req.request_id;

                return (
                  <motion.div
                    key={req.request_id ?? idx}
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: 0.4 + idx * 0.04 }}
                    className="flex items-start gap-3 px-4 py-3 hover:bg-muted/10 transition-colors bg-sylion-amber/[0.02]"
                  >
                    {/* Status dot */}
                    <div className="w-6 h-6 rounded-md flex items-center justify-center bg-sylion-amber/10 shrink-0 mt-0.5">
                      <Clock className="w-3 h-3 text-sylion-amber" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-medium text-foreground truncate">{req.title || req.request_id}</p>
                        <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5 shrink-0 uppercase">
                          oczekuje
                        </Badge>
                      </div>
                      {req.description && (
                        <p className="text-[10px] text-muted-foreground mt-0.5">{req.description}</p>
                      )}
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
                        {req.gate_name && (
                          <span className="flex items-center gap-1">
                            <Shield className="w-2.5 h-2.5" />
                            {req.gate_name}
                          </span>
                        )}
                        {req.requested_by && (
                          <span>od {req.requested_by}</span>
                        )}
                        <span>{formatRequestedAt(req.requested_at)}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-[10px] h-7 border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                        disabled={isActioning}
                        onClick={() => handleApprove(req.request_id)}
                      >
                        <ThumbsUp className="w-3 h-3 mr-1" />
                        Zatwierdź
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-[10px] h-7 border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
                        disabled={isActioning}
                        onClick={() => handleNeedsInfo(req.request_id)}
                      >
                        <AlertTriangle className="w-3 h-3 mr-1" />
                        Potrzebne info
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-[10px] h-7 border-sylion-red/30 text-sylion-red hover:bg-sylion-red/10"
                        disabled={isActioning}
                        onClick={() => handleReject(req.request_id)}
                      >
                        <ThumbsDown className="w-3 h-3 mr-1" />
                        Odrzuć
                      </Button>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
