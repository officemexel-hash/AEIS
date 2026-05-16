"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useHealth, useGoldenSetsList } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Award,
  RefreshCw,
  WifiOff,
  CheckCircle2,
  XCircle,
  FlaskConical,
  Layers,
  Activity,
  Server,
  BarChart3,
  Play,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface GoldenSet {
  set_id: string;
  name: string;
  category: string;
  case_count: number;
  last_run?: number;
  pass_rate?: number;
  description?: string;
}

/* ============================================================
   Helpers
   ============================================================ */

function passRateColor(rate: number): string {
  if (rate >= 90) return "text-sylion-green";
  if (rate >= 70) return "text-sylion-amber";
  return "text-sylion-red";
}

function passRateBarColor(rate: number): string {
  if (rate >= 90) return "bg-sylion-green";
  if (rate >= 70) return "bg-sylion-amber";
  return "bg-sylion-red";
}

function formatLastRun(ts?: number): string {
  if (!ts) return "Nigdy";
  const diff = Date.now() - ts;
  if (diff < 5000) return "przed chwilą";
  if (diff < 60000) return `${Math.floor(diff / 1000)}s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h temu`;
  return `${Math.floor(diff / 86400000)}d temu`;
}

/* ============================================================
   Page Component
   ============================================================ */

export default function GoldenTestsPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const { data: setsData, refresh: refreshSets } = useGoldenSetsList();

  const healthData = healthRaw as { status: string; version?: string; modules?: number; endpoints?: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const sets: GoldenSet[] = setsData.sets ?? [];

  const refreshAll = () => {
    refreshHealth();
    refreshSets();
  };

  /* ---------- Derived: summary stats ---------- */
  const totalSets = sets.length;
  const totalCases = useMemo(() => sets.reduce((acc, s) => acc + (s.case_count ?? 0), 0), [sets]);
  const totalRuns = useMemo(() => sets.filter((s) => s.last_run).length, [sets]);

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
            <Award className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Testy złote
              <HelpTip text="Zestawy testów referencyjnych — golden sets — walidujące kontrakty i wykrywające regresje. Każdy zestaw zawiera przypadki testówe i wskaźnik przejścia (pass-rate)." />
            </h1>
            <p className="text-sm text-muted-foreground">Walidacja kontraktów i testy regresyjne</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane testów złotych wymagają działającego backendu.
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
      label: "Łącznie zestawów",
      tipText: "Liczba zarejestrowanych zestawów testów złotych.",
      value: totalSets,
      icon: Layers,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Łącznie przypadków",
      tipText: "Suma wszystkich przypadków testówych we wszystkich zestawach.",
      value: totalCases,
      icon: FlaskConical,
      color: "text-purple-400",
      bgColor: "bg-purple-400/10",
    },
    {
      label: "Łącznie uruchomień",
      tipText: "Liczba zestawów, które miały co najmniej jedno wykonanie testów.",
      value: totalRuns,
      icon: Play,
      color: "text-sylion-amber",
      bgColor: "bg-sylion-amber/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Award className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Testy złote
              <HelpTip text="Zestawy testów referencyjnych — golden sets — walidujące kontrakty i wykrywające regresje. Każdy zestaw zawiera przypadki testówe i wskaźnik przejścia (pass-rate)." />
            </h1>
            <p className="text-sm text-muted-foreground">Walidacja kontraktów i testy regresyjne</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-[10px] flex items-center gap-1.5 border-sylion-green/30 text-sylion-green bg-sylion-green/5">
            <span className="w-1.5 h-1.5 rounded-full bg-sylion-green animate-pulse" />
            LIVE
          </Badge>

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

      {/* ====== GOLDEN SETS TABLE ====== */}
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
                Zestawy złote
                <HelpTip text="Lista wszystkich zestawów testów złotych z liczbą przypadków i wskaźnikiem przejścia." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {totalSets} zestawów
              </Badge>
            </div>
          </div>

          {sets.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Award className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">Brak zarejestrowanych zestawów złotych</p>
              <p className="text-[10px] mt-1 opacity-60">Utwórz zestawy poprzez Quality API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Nazwa</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Kategoria</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Przypadki</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Ostatnie uruchomienie</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Wskaźnik przejścia</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/10">
                  {sets
                    .sort((a, b) => (a.name ?? "").localeCompare(b.name ?? ""))
                    .map((set, idx) => {
                      const rate = set.pass_rate ?? 0;

                      return (
                        <motion.tr
                          key={set.set_id ?? idx}
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.2, delay: 0.25 + idx * 0.03 }}
                          className="hover:bg-muted/10 transition-colors"
                        >
                          {/* Name */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className={cn(
                                "w-6 h-6 rounded-md flex items-center justify-center",
                                rate >= 90 ? "bg-sylion-green/10" : rate >= 70 ? "bg-sylion-amber/10" : "bg-sylion-red/10"
                              )}>
                                {rate >= 90 ? (
                                  <CheckCircle2 className={cn("w-3 h-3", passRateColor(rate))} />
                                ) : rate >= 70 ? (
                                  <Activity className={cn("w-3 h-3", passRateColor(rate))} />
                                ) : (
                                  <XCircle className={cn("w-3 h-3", passRateColor(rate))} />
                                )}
                              </div>
                              <div>
                                <span className="text-xs font-medium text-foreground">{set.name ?? set.set_id}</span>
                                {set.description && (
                                  <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">{set.description}</p>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Category */}
                          <td className="px-4 py-3 text-center">
                            <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                              {set.category || "---"}
                            </Badge>
                          </td>

                          {/* Case count */}
                          <td className="px-4 py-3 text-center">
                            <span className="font-mono text-foreground">{set.case_count ?? 0}</span>
                          </td>

                          {/* Last run */}
                          <td className="px-4 py-3 text-center">
                            <span className="text-muted-foreground">{formatLastRun(set.last_run)}</span>
                          </td>

                          {/* Pass rate */}
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-center gap-2">
                              <div className="w-16">
                                <Progress value={rate} className="h-1.5" />
                              </div>
                              <span className={cn("font-mono w-12 text-right", passRateColor(rate))}>
                                {rate}%
                              </span>
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

      {/* ====== RUNS SECTION ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.35 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Play className="w-4 h-4 text-sylion-amber" />
              <h3 className="text-xs font-semibold">
                Ostatnie uruchomienia
                <HelpTip text="Najnowsze wykonania zestawów testów z wynikami pass-rate." />
              </h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {totalRuns} wykonano
              </Badge>
            </div>
          </div>

          {totalRuns === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Play className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">Brak zarejestrowanych uruchomień</p>
              <p className="text-[10px] mt-1 opacity-60">Wykonaj zestawy testów, aby zobaczyć wyniki</p>
            </div>
          ) : (
            <div className="divide-y divide-border/10">
              {sets
                .filter((s) => s.last_run)
                .sort((a, b) => (b.last_run ?? 0) - (a.last_run ?? 0))
                .slice(0, 10)
                .map((set, idx) => {
                  const rate = set.pass_rate ?? 0;
                  return (
                    <motion.div
                      key={set.set_id ?? idx}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2, delay: 0.4 + idx * 0.04 }}
                      className="flex items-center gap-3 px-4 py-3 hover:bg-muted/10 transition-colors"
                    >
                      <div className={cn(
                        "w-6 h-6 rounded-md flex items-center justify-center shrink-0",
                        rate >= 90 ? "bg-sylion-green/10" : rate >= 70 ? "bg-sylion-amber/10" : "bg-sylion-red/10"
                      )}>
                        {rate >= 90 ? (
                          <CheckCircle2 className={cn("w-3 h-3", passRateColor(rate))} />
                        ) : (
                          <XCircle className={cn("w-3 h-3", passRateColor(rate))} />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{set.name ?? set.set_id}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {set.case_count ?? 0} przypadków | {set.category || "bez kategorii"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={cn("font-mono text-xs", passRateColor(rate))}>{rate}%</span>
                        <span className="text-[10px] text-muted-foreground">{formatLastRun(set.last_run)}</span>
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
