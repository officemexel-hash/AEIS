"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useHealth, useHealingRules, useHealingActions } from "@/lib/api/hooks";
import { cn, fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  RefreshCw,
  WifiOff,
  ShieldCheck,
  Activity,
  Zap,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Timer,
  ListChecks,
  Wrench,
  Users,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface HealingRule {
  rule_id: string;
  name: string;
  trigger_condition: string;
  action_type: string;
  enabled: boolean;
  cooldown_seconds: number;
  description?: string;
  created_at?: string | number;
}

interface HealingAction {
  action_id: string;
  rule_name: string;
  rule_id?: string;
  triggered_at: string | number;
  status: "success" | "failed" | "in_progress";
  result_summary?: string;
  duration_ms?: number;
}

/* ============================================================
   Status badge style map
   ============================================================ */

const actionStatusStyles: Record<string, { badge: string; icon: React.ElementType }> = {
  success: {
    badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
    icon: CheckCircle2,
  },
  failed: {
    badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
    icon: XCircle,
  },
  in_progress: {
    badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
    icon: Loader2,
  },
};

/* ============================================================
   Helper: format cooldown
   ============================================================ */

function formatCooldown(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
}

/* ============================================================
   Helper: format triggered_at timestamp
   ============================================================ */

function formatTriggerTime(ts: string | number): string {
  if (!ts) return "---";
  if (typeof ts === "number" && ts > 1e12) return fmtDateTime(new Date(ts));
  return fmtDateTime(ts);
}

/* ============================================================
   Page Component
   ============================================================ */

export default function HealingPage() {
  /* ---------- Hook-driven data ---------- */
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const { data: rulesData, refresh: refreshRules } = useHealingRules();
  const { data: actionsData, refresh: refreshActions } = useHealingActions(50);
  const backendLive = (healthRaw as any).status === "ok";

  const rules: HealingRule[] = (rulesData as any).rules ?? [];
  const actions: HealingAction[] = (actionsData as any).actions ?? [];

  /* ---------- Derived stats ---------- */
  const activeRules = useMemo(
    () => rules.filter((r) => r.enabled),
    [rules],
  );

  const successCount = useMemo(
    () => actions.filter((a) => a.status === "success").length,
    [actions],
  );

  const failedCount = useMemo(
    () => actions.filter((a) => a.status === "failed").length,
    [actions],
  );

  const inProgressCount = useMemo(
    () => actions.filter((a) => a.status === "in_progress").length,
    [actions],
  );

  const successRate = useMemo(() => {
    const total = successCount + failedCount;
    if (total === 0) return 0;
    return Math.round((successCount / total) * 100);
  }, [successCount, failedCount]);

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
              Auto-naprawa
              <HelpTip text="Orkiestrator samonapraw — automatyczne wykrywanie incydentów i ich łagodzenie. Reguły mają warunek wyzwalający, akcję, cooldown i flagę enabled. Ścieżka audytu w sekcji niżej." />
            </h1>
            <p className="text-sm text-muted-foreground">Automatyczna odpowiedź na incydenty i odzyskiwanie</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Reguły auto-naprawy wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => fetchHealth()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Stats cards config ---------- */
  const statsCards = [
    {
      label: "Aktywne reguły",
      tipText: "Reguły z włączoną flagą enabled — gotowe do uruchomienia po wystąpieniu warunku.",
      value: activeRules.length,
      icon: ListChecks,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Łącznie akcji",
      tipText: "Suma wszystkich uruchomień akcji naprawczych w całej historii.",
      value: actions.length,
      icon: Activity,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Wskaźnik sukcesu",
      tipText: "Procent akcji zakończonych sukcesem względem zakończonych nieudanie. <80% wymaga przeglądu reguł.",
      value: `${successRate}%`,
      icon: successRate >= 80 ? CheckCircle2 : successRate >= 50 ? Activity : XCircle,
      color: successRate >= 80 ? "text-sylion-green" : successRate >= 50 ? "text-sylion-amber" : "text-sylion-red",
      bgColor: successRate >= 80 ? "bg-sylion-green/10" : successRate >= 50 ? "bg-sylion-amber/10" : "bg-sylion-red/10",
    },
    {
      label: "W toku",
      tipText: "Liczba akcji aktualnie wykonywanych przez orkiestrator.",
      value: inProgressCount,
      icon: Users,
      color: "text-purple-400",
      bgColor: "bg-purple-400/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-green/10 border border-sylion-green/20 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-sylion-green" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Auto-naprawa
              <HelpTip text="Orkiestrator samonapraw — automatyczne wykrywanie incydentów i ich łagodzenie. Reguły mają warunek wyzwalający, akcję, cooldown i flagę enabled. Ścieżka audytu w sekcji niżej." />
            </h1>
            <p className="text-sm text-muted-foreground">Automatyczna odpowiedź na incydenty i odzyskiwanie</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green bg-sylion-green/5 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-sylion-green animate-pulse" />
            LIVE
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { refreshRules(); refreshActions(); }}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== STATS ROW (4 cards) ====== */}
      <div className="grid grid-cols-4 gap-3">
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

      {/* ====== HEALING RULES TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wrench className="w-4 h-4 text-sylion-green" />
              <h3 className="text-xs font-semibold">
                Reguły naprawcze
                <HelpTip text="Definicje warunków wyzwalających i akcji naprawczych. Każda reguła ma cooldown blokujący zbyt częste odpalanie." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {rules.length} łącznie
              </Badge>
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="border-border/20 hover:bg-transparent">
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">ID reguły</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">Nazwa</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">Warunek wyzwalający</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">Typ akcji</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider text-center">Włączona<HelpTip text="Reguła musi być włączona, aby system uruchomił akcję po wystąpieniu warunku." /></TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider text-right">Cooldown<HelpTip text="Minimalny czas między kolejnymi odpaleniami tej samej reguły. Zapobiega zapętleniu." /></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                    <ListChecks className="w-6 h-6 mx-auto mb-2 opacity-30" />
                    <p className="text-xs">Brak skonfigurowanych reguł naprawczych</p>
                  </TableCell>
                </TableRow>
              )}
              {rules.map((rule) => (
                <TableRow key={rule.rule_id} className="border-border/10 hover:bg-muted/10">
                  <TableCell className="text-[11px] font-mono text-muted-foreground">
                    {rule.rule_id.length > 12 ? rule.rule_id.slice(0, 12) + "..." : rule.rule_id}
                  </TableCell>
                  <TableCell className="text-[11px] font-medium text-foreground">
                    {rule.name}
                  </TableCell>
                  <TableCell className="text-[11px] text-muted-foreground max-w-[200px]">
                    <span className="truncate block">{rule.trigger_condition}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[9px] border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5">
                      {rule.action_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <Switch checked={rule.enabled} disabled />
                  </TableCell>
                  <TableCell className="text-[11px] text-muted-foreground text-right font-mono">
                    <span className="flex items-center justify-end gap-1">
                      <Timer className="w-3 h-3 text-muted-foreground/50" />
                      {formatCooldown(rule.cooldown_seconds)}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </motion.div>

      {/* ====== RECENT HEALING ACTIONS TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.3 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">
                Ostatnie akcje naprawcze
                <HelpTip text="Wykonania akcji naprawczych — kto, kiedy, z jakim skutkiem, czas trwania. Stanowi ścieżkę audytu samonapraw." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {actions.length} ostatnich
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              {successCount > 0 && (
                <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green bg-sylion-green/5">
                  {successCount} Sukces
                </Badge>
              )}
              {failedCount > 0 && (
                <Badge variant="outline" className="text-[9px] border-sylion-red/30 text-sylion-red bg-sylion-red/5">
                  {failedCount} Nieudane
                </Badge>
              )}
              {inProgressCount > 0 && (
                <Badge variant="outline" className="text-[9px] border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5">
                  {inProgressCount} Działa
                </Badge>
              )}
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="border-border/20 hover:bg-transparent">
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">ID akcji</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">Nazwa reguły</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">Wyzwolono</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider text-center">Status</TableHead>
                <TableHead className="text-[10px] text-muted-foreground uppercase tracking-wider">Podsumowanie wyniku</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {actions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-12 text-muted-foreground">
                    <Activity className="w-6 h-6 mx-auto mb-2 opacity-30" />
                    <p className="text-xs">Brak zarejestrowanych akcji naprawczych</p>
                  </TableCell>
                </TableRow>
              )}
              {actions.map((action) => {
                const styles = actionStatusStyles[action.status] ?? actionStatusStyles.in_progress;
                const StatusIcon = styles.icon;

                return (
                  <TableRow key={action.action_id} className="border-border/10 hover:bg-muted/10">
                    <TableCell className="text-[11px] font-mono text-muted-foreground">
                      {action.action_id.length > 12 ? action.action_id.slice(0, 12) + "..." : action.action_id}
                    </TableCell>
                    <TableCell className="text-[11px] font-medium text-foreground">
                      {action.rule_name}
                    </TableCell>
                    <TableCell className="text-[11px] text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-muted-foreground/50" />
                        {formatTriggerTime(action.triggered_at)}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className={cn("text-[9px] inline-flex items-center gap-1", styles.badge)}>
                        <StatusIcon className={cn("w-3 h-3", action.status === "in_progress" && "animate-spin")} />
                        {action.status === "in_progress" ? "W TOKU" : action.status === "success" ? "SUKCES" : "NIEUDANE"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-[11px] text-muted-foreground max-w-[300px]">
                      <span className="truncate block">{action.result_summary || "---"}</span>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      </motion.div>

      {/* ====== LIVE INDICATOR ====== */}
      <div className="flex items-center justify-center gap-2 mt-2 text-[10px] text-muted-foreground">
        <span className="w-1.5 h-1.5 rounded-full bg-sylion-green animate-pulse" />
        <span>Auto-odświeżanie co 15 sekund</span>
      </div>
    </div>
  );
}
