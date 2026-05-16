"use client";

import { useState, useCallback, useMemo } from "react";
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
import { useAuditEvents, useAuditSummary, useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Shield,
  WifiOff,
  RefreshCw,
  Activity,
  FileCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Lock,
  Search,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface AuditEvent {
  event_id?: string;
  entry_id?: string;
  timestamp?: number;
  event_type?: string;
  source?: string;
  actor?: string;
  action?: string;
  severity?: string;
  outcome?: string;
  resource?: string;
  details?: string;
  metadata?: Record<string, unknown>;
  hash?: string;
}

/* ============================================================
   Severity styling
   ============================================================ */

const severityStyles: Record<string, { badge: string; dot: string; text: string }> = {
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
  info: {
    badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    dot: "bg-sylion-blue",
    text: "text-sylion-blue",
  },
};

/* ============================================================
   Helpers
   ============================================================ */

function formatTimestamp(ts: number | undefined): string {
  if (!ts) return "---";
  const date = typeof ts === "number" && ts < 1e12 ? new Date(ts * 1000) : new Date(ts);
  return date.toLocaleDateString("pl-PL", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getSeverityStyles(severity: string) {
  const normalized = (severity || "info").toLowerCase();
  return severityStyles[normalized] || severityStyles.info;
}

function eventSeverity(event: AuditEvent): string {
  const explicit = String(event.severity || event.metadata?.severity || "");
  if (explicit) return explicit;
  if (event.outcome === "failure" || event.outcome === "error") return "high";
  if (event.outcome === "denied") return "medium";
  return "info";
}

/* ============================================================
   Page Component
   ============================================================ */

export default function AuditPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const healthData = healthRaw as { status: string; version: string; modules: number; endpoints: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const { data: auditData, refresh: refreshAudit } = useAuditEvents({ limit: 100 });
  const { data: summaryData, refresh: refreshSummary } = useAuditSummary();

  const events: AuditEvent[] = (auditData as any).events ?? [];
  const auditSummary = summaryData as any;

  /* ---------- Chain verification state ---------- */
  const [verifying, setVerifying] = useState(false);
  const [tamperChecking, setTamperChecking] = useState(false);
  const [chainStatus, setChainStatus] = useState<"idle" | "valid" | "invalid">("idle");
  const [tamperStatus, setTamperStatus] = useState<"idle" | "clean" | "detected">("idle");

  /* ---------- Derived stats ---------- */
  const chainIntegrityLabel = useMemo(() => {
    if (chainStatus === "valid") return "VALID";
    if (chainStatus === "invalid") return "INVALID";
    return "UNKNOWN";
  }, [chainStatus]);

  const chainIntegrityColor = useMemo(() => {
    if (chainStatus === "valid") return "text-sylion-green";
    if (chainStatus === "invalid") return "text-sylion-red";
    return "text-muted-foreground";
  }, [chainStatus]);

  const handleRefreshAll = () => {
    fetchHealth();
    refreshAudit();
    refreshSummary();
  };

  /* ---------- Verify chain ---------- */
  const handleVerifyChain = useCallback(() => {
    setVerifying(true);
    api.getAuditIntegrity()
      .then((result: any) => {
        setChainStatus(result.valid === true ? "valid" : "invalid");
      })
      .catch(() => {
        setChainStatus("invalid");
      })
      .finally(() => {
        setVerifying(false);
      });
  }, []);

  /* ---------- Tamper check ---------- */
  const handleTamperCheck = useCallback(() => {
    setTamperChecking(true);
    api.getAuditIntegrity()
      .then((result: any) => {
        setTamperStatus(result.valid === true && (result.tampered_count || 0) === 0 ? "clean" : "detected");
      })
      .catch(() => {
        setTamperStatus("detected");
      })
      .finally(() => {
        setTamperChecking(false);
      });
  }, []);

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
        <div className="grid grid-cols-2 gap-3">
          {[1, 2].map((i) => (
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
              Zintegrowany dziennik audytu
              <HelpTip text="Append-only ścieżka audytu wszystkich zdarzeń zarządczych, projektowych i rady. Hash-chained — każdy wpis powiązany z poprzednim. Eksport CSV/JSON; weryfikacja integralności łańcucha." />
            </h1>
            <p className="text-sm text-muted-foreground">Widoczny dla operatora łańcuch dowodów zarządczych, projektowych i rady</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane ścieżki audytu, weryfikacja łańcucha i wykrywanie manipulacji wymagają działającego backendu.
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
          <div className="w-9 h-9 rounded-lg bg-sylion-green/10 border border-sylion-green/20 flex items-center justify-center">
            <Lock className="w-4 h-4 text-sylion-green" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Zintegrowany dziennik audytu
              <HelpTip text="Append-only ścieżka audytu wszystkich zdarzeń zarządczych, projektowych i rady. Hash-chained — każdy wpis powiązany z poprzednim. Eksport CSV/JSON; weryfikacja integralności łańcucha." />
            </h1>
            <p className="text-sm text-muted-foreground">Widoczny dla operatora łańcuch dowodów zarządczych, projektowych i rady</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== SUMMARY CARDS (2) ====== */}
      <div className="grid grid-cols-2 gap-3">
        {[
          {
            label: "Łącznie zdarzeń",
            value: auditSummary?.total_entries ?? events.length,
            tipText: "Liczba wszystkich wpisów w dzienniku audytu od początku łańcucha.",
            icon: Activity,
            color: "text-sylion-blue",
            bgColor: "bg-sylion-blue/10",
          },
          {
            label: "Integralność łańcucha",
            tipText: "Status weryfikacji łańcucha hashy. VALID = brak manipulacji; INVALID = złamany hash.",
            value: chainIntegrityLabel,
            icon: chainStatus === "valid" ? CheckCircle2 : chainStatus === "invalid" ? XCircle : FileCheck,
            color: chainIntegrityColor,
            bgColor: chainStatus === "valid" ? "bg-sylion-green/10" : chainStatus === "invalid" ? "bg-sylion-red/10" : "bg-muted/20",
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
                      {(stat as any).tipText && <HelpTip text={(stat as any).tipText} />}
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

      {/* ====== CHAIN VERIFICATION ACTIONS ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-sylion-green" />
              <h3 className="text-xs font-semibold">
                Weryfikacja łańcucha
                <HelpTip text="Sprawdź spójność łańcucha audytu. Weryfikuj liczy hashe, Kontrola manipulacji wykrywa modyfikacje." />
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleVerifyChain}
                disabled={verifying}
              >
                {verifying ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                )}
                {verifying ? "Weryfikacja..." : "Weryfikuj łańcuch"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTamperCheck}
                disabled={tamperChecking}
              >
                {tamperChecking ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Shield className="w-3.5 h-3.5 mr-1.5" />
                )}
                {tamperChecking ? "SprawdŹanie..." : "Kontrola manipulacji"}
              </Button>
              {tamperStatus === "clean" && (
                <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green bg-sylion-green/5">
                  <CheckCircle2 className="w-2.5 h-2.5 mr-1" />
                  BRAK MANIPULACJI
                </Badge>
              )}
              {tamperStatus === "detected" && (
                <Badge variant="outline" className="text-[9px] border-sylion-red/30 text-sylion-red bg-sylion-red/5">
                  <AlertTriangle className="w-2.5 h-2.5 mr-1" />
                  WYKRYTO MANIPULACJĘ
                </Badge>
              )}
            </div>
          </div>
        </Card>
      </motion.div>

      {/* ====== EVENTS TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-sylion-green" />
              <h3 className="text-xs font-semibold">
                Zdarzenia audytu
                <HelpTip text="Strumień zdarzeń audytu w kolejności chronologicznej. Każde zdarze?ie ma typ, aktora, akcję i wagę." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {events.length} zdarzeń
              </Badge>
            </div>
          </div>

          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Search className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-xs">Brak zdarzeń audytu</p>
              <p className="text-[10px] mt-1 opacity-60">Zdarzenia będą się tu pojawiać w miarę rejestrowania akcji zarządczych i projektowych</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border/20 hover:bg-transparent">
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Czas</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Typ zdarze?ia</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Aktor</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Akcja</TableHead>
                  <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground">Waga</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event, idx) => {
                  const severity = eventSeverity(event);
                  const styles = getSeverityStyles(severity);
                  return (
                    <TableRow key={event.entry_id ?? event.event_id ?? idx} className="border-border/10 hover:bg-muted/10">
                      <TableCell className="text-[11px] text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <Activity className="w-3 h-3 text-muted-foreground/40" />
                          {formatTimestamp(event.timestamp)}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono">
                        {event.event_type || event.source || "---"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {event.actor || "---"}
                      </TableCell>
                      <TableCell className="text-xs max-w-[250px]">
                        <span className="truncate block">{event.action || "---"}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("text-[9px]", styles.badge)}>
                          <span className={cn("w-1.5 h-1.5 rounded-full mr-1", styles.dot)} />
                          {severity.toUpperCase()}
                        </Badge>
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
