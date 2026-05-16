"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth, useCircuitBreakers } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Zap,
  RefreshCw,
  WifiOff,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Activity,
  Server,
  BarChart3,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface CircuitBreaker {
  breaker_id: string;
  name: string;
  state: "closed" | "open" | "half_open";
  failure_count: number;
  failure_threshold: number;
  recovery_timeout_ms: number;
  last_event: string;
  last_event_time?: number;
  target?: string;
}

/* ============================================================
   Helpers
   ============================================================ */

function stateStyles(state: string): { badge: string; dot: string; text: string; iconBg: string } {
  switch (state) {
    case "closed":
      return {
        dot: "bg-sylion-green",
        badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
        text: "text-sylion-green",
        iconBg: "bg-sylion-green/10",
      };
    case "open":
      return {
        dot: "bg-sylion-red",
        badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
        text: "text-sylion-red",
        iconBg: "bg-sylion-red/10",
      };
    case "half_open":
      return {
        dot: "bg-sylion-amber",
        badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
        text: "text-sylion-amber",
        iconBg: "bg-sylion-amber/10",
      };
    default:
      return {
        dot: "bg-muted-foreground",
        badge: "border-muted-foreground/30 text-muted-foreground bg-muted-foreground/5",
        text: "text-muted-foreground",
        iconBg: "bg-muted-foreground/10",
      };
  }
}

function stateIcon(state: string): React.ElementType {
  switch (state) {
    case "closed":
      return CheckCircle2;
    case "open":
      return AlertTriangle;
    case "half_open":
      return Clock;
    default:
      return Shield;
  }
}

function formatRecoveryTimeout(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}min ${Math.floor((ms % 60000) / 1000)}s`;
}

function formatEventTime(ts?: number): string {
  if (!ts) return "---";
  const diff = Date.now() - ts;
  if (diff < 5000) return "przed chwilą";
  if (diff < 60000) return `${Math.floor(diff / 1000)}s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}min temu`;
  return `${Math.floor(diff / 3600000)}h temu`;
}

/* ============================================================
   Page Component
   ============================================================ */

export default function CircuitsPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const { data: breakersData, refresh: refreshBreakers } = useCircuitBreakers();

  const healthData = healthRaw as { status: string; version?: string; modules?: number; endpoints?: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const breakers: CircuitBreaker[] = breakersData.breakers ?? [];

  const refreshAll = () => {
    refreshHealth();
    refreshBreakers();
  };

  /* ---------- Derived: summary stats ---------- */
  const totalCount = breakers.length;
  const closedCount = useMemo(() => breakers.filter((b) => b.state === "closed").length, [breakers]);
  const openCount = useMemo(() => breakers.filter((b) => b.state === "open").length, [breakers]);
  const halfOpenCount = useMemo(() => breakers.filter((b) => b.state === "half_open").length, [breakers]);

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
            <Zap className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Przerywacze obwodów
              <HelpTip text="Mechanizm fault-tolerance — gdy zewnętrzny serwis (LLM/DB/API) wielokrotnie zawodzi, przerywacz przechodzi w OTWARTY i blokuje kolejne wywołania na recovery_timeout. Stan POŁ-OTWARTY = test czy serwis wrócił. Domyślny próg 5 błędów / 30 s." />
            </h1>
            <p className="text-sm text-muted-foreground">Monitoring odporności i fault-tolerance</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane przerywaczy obwodów wymagają działającego backendu.
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
      label: "Łącznie przerywaczy",
      tip: "Liczba zarejestrowanych przerywaczy obwodów (jeden per zewnętrzny serwis lub krytyczna integracja).",
      value: totalCount,
      icon: Shield,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Zamknięte (sprawne)",
      tip: "Przerywacze w stanie zamkniętym — wszystkie wywołania przechodzą normalnie. Stan docelowy.",
      value: closedCount,
      icon: CheckCircle2,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Otwarte (zerwane)",
      tip: "Przerywacze otwarte po przekroczeniu progu błędów. Wywołania są blokowane do końca recovery_timeout, potem przejście w POŁ-OTWARTY.",
      value: openCount,
      icon: AlertTriangle,
      color: openCount > 0 ? "text-sylion-red" : "text-sylion-green",
      bgColor: openCount > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
    },
    {
      label: "Poł-otwarte (testują)",
      tip: "Przerywacze testujące czy serwis wrócił do sprawności. Jeden sukces = ZAMKNIĘTY; jeden błąd = ponownie OTWARTY.",
      value: halfOpenCount,
      icon: Clock,
      color: halfOpenCount > 0 ? "text-sylion-amber" : "text-muted-foreground",
      bgColor: halfOpenCount > 0 ? "bg-sylion-amber/10" : "bg-muted-foreground/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-9 h-9 rounded-lg flex items-center justify-center border",
            openCount > 0 ? "bg-sylion-red/10 border-sylion-red/20" : "bg-sylion-green/10 border-sylion-green/20"
          )}>
            <Zap className={cn("w-4 h-4", openCount > 0 ? "text-sylion-red" : "text-sylion-green")} />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Przerywacze obwodów
              <HelpTip text="Mechanizm fault-tolerance — gdy zewnętrzny serwis (LLM/DB/API) wielokrotnie zawodzi, przerywacz przechodzi w OTWARTY i blokuje kolejne wywołania na recovery_timeout. Stan POŁ-OTWARTY = test czy serwis wrócił. Domyślny próg 5 błędów / 30 s." />
            </h1>
            <p className="text-sm text-muted-foreground">Monitoring odporności i fault-tolerance</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className={cn(
            "text-[10px] flex items-center gap-1.5",
            openCount > 0
              ? "border-sylion-red/30 text-sylion-red bg-sylion-red/5"
              : "border-sylion-green/30 text-sylion-green bg-sylion-green/5"
          )}>
            <span className={cn(
              "w-1.5 h-1.5 rounded-full animate-pulse",
              openCount > 0 ? "bg-sylion-red" : "bg-sylion-green"
            )} />
            {openCount > 0 ? `${openCount} ZERWANYCH` : "WSZYSTKO OK"}
          </Badge>

          <Button variant="outline" size="sm" onClick={refreshAll}>
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

      {/* ====== BREAKERS TABLE ====== */}
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
                Przerywacze obwodów
                <HelpTip text="Lista wszystkich przerywaczy z aktualnym stanem, licznikiem awarii (vs próg) i czasem do recovery. Otwarte podświetlone na czerwono — wymagają interwencji lub czekają na recovery_timeout." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {totalCount} przerywaczy
              </Badge>
            </div>
          </div>

          {breakers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Shield className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">Brak zarejestrowanych przerywaczy obwodów</p>
              <p className="text-[10px] mt-1 opacity-60">Przerywacze pojawią się tutaj gdy moduły je zarejestrują</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Nazwa</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Stan</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Awarie</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Recovery</th>
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Ostatnie zdarze?ie</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/10">
                  {breakers
                    .sort((a, b) => {
                      const order = { open: 0, half_open: 1, closed: 2 };
                      return (order[a.state] ?? 2) - (order[b.state] ?? 2);
                    })
                    .map((breaker, idx) => {
                      const styles = stateStyles(breaker.state);
                      const SIcon = stateIcon(breaker.state);

                      return (
                        <motion.tr
                          key={breaker.breaker_id ?? idx}
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.2, delay: 0.25 + idx * 0.03 }}
                          className={cn(
                            "hover:bg-muted/10 transition-colors",
                            breaker.state === "open" && "bg-sylion-red/[0.02]",
                            breaker.state === "half_open" && "bg-sylion-amber/[0.02]"
                          )}
                        >
                          {/* Name */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className={cn("w-6 h-6 rounded-md flex items-center justify-center", styles.iconBg)}>
                                <SIcon className={cn("w-3 h-3", styles.text)} />
                              </div>
                              <div>
                                <span className="text-xs font-medium text-foreground">{breaker.name ?? breaker.breaker_id}</span>
                                {breaker.target && (
                                  <p className="text-[10px] text-muted-foreground">{breaker.target}</p>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* State badge */}
                          <td className="px-4 py-3 text-center">
                            <Badge variant="outline" className={cn("text-[9px] uppercase font-semibold", styles.badge)}>
                              <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", styles.dot)} />
                              {breaker.state.replace("_", " ")}
                            </Badge>
                          </td>

                          {/* Failure count */}
                          <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              {breaker.failure_count >= breaker.failure_threshold && (
                                <AlertTriangle className="w-3 h-3 text-sylion-red" />
                              )}
                              <span className={cn(
                                "font-mono",
                                breaker.failure_count >= breaker.failure_threshold ? "text-sylion-red" : "text-muted-foreground"
                              )}>
                                {breaker.failure_count}/{breaker.failure_threshold}
                              </span>
                            </div>
                          </td>

                          {/* Recovery timeout */}
                          <td className="px-4 py-3 text-center">
                            <span className="font-mono text-muted-foreground">
                              {formatRecoveryTimeout(breaker.recovery_timeout_ms)}
                            </span>
                          </td>

                          {/* Last event */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <Activity className="w-3 h-3 text-muted-foreground" />
                              <span className="text-muted-foreground truncate max-w-[200px]">
                                {breaker.last_event || "---"}
                              </span>
                              {breaker.last_event_time && (
                                <span className="text-[10px] text-muted-foreground shrink-0">
                                  {formatEventTime(breaker.last_event_time)}
                                </span>
                              )}
                            </div>
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
    </div>
  );
}
