"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useHealth, useModelBudgets, useSpendingSummary, useCostAlerts } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Wallet,
  RefreshCw,
  WifiOff,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  BarChart3,
  CreditCard,
  Gauge,
  CalendarDays,
  ArrowUpRight,
  Plus,
  Loader2,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface BudgetEntry {
  model_id: string;
  provider: string;
  budget_limit: number;
  spent: number;
  remaining: number;
  status: string;
  fallback_model_id: string;
  pct_used?: number;
}

interface SpendingSummary {
  total_budget: number;
  total_spent: number;
  total_remaining: number;
  by_model: { model_id: string; spent: number }[];
}

/* ============================================================
   Helpers
   ============================================================ */

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function fmtUSD(n: unknown): string {
  const value = toNumber(n);
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

function normalizeBudgetEntry(raw: any): BudgetEntry {
  const dailyLimit = toNumber(raw?.daily_limit);
  const monthlyLimit = toNumber(raw?.monthly_limit);
  const limit = toNumber(raw?.budget_limit, dailyLimit || monthlyLimit);
  const spent = toNumber(raw?.spent, toNumber(raw?.spent_today, toNumber(raw?.spent_this_month)));
  const remaining = toNumber(raw?.remaining, Math.max(limit - spent, 0));
  const ratio = limit > 0 ? spent / limit : 0;
  const status = String(
    raw?.status
      || (limit <= 0 ? "unlimited" : ratio >= 1 ? "over_budget" : ratio >= 0.8 ? "warning" : "healthy")
  );
  return {
    model_id: String(raw?.model_id || "unknown-model"),
    provider: String(raw?.provider || raw?.runtime_provider || "unknown"),
    budget_limit: limit,
    spent,
    remaining,
    status,
    fallback_model_id: String(raw?.fallback_model_id || ""),
    pct_used: toNumber(raw?.pct_used, ratio),
  };
}

function normalizeSummary(raw: any, budgets: BudgetEntry[]): SpendingSummary {
  const totalBudget = toNumber(raw?.total_budget, toNumber(raw?.total_daily_limit, budgets.reduce((sum, item) => sum + item.budget_limit, 0)));
  const totalSpent = toNumber(raw?.total_spent, toNumber(raw?.total_spent_daily, budgets.reduce((sum, item) => sum + item.spent, 0)));
  return {
    total_budget: totalBudget,
    total_spent: totalSpent,
    total_remaining: toNumber(raw?.total_remaining, Math.max(totalBudget - totalSpent, 0)),
    by_model: Array.isArray(raw?.by_model) ? raw.by_model : Array.isArray(raw?.models) ? raw.models : [],
  };
}

/*
function fmtUSD(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
}
*/

function budgetStatusColor(status: string): string {
  switch (status) {
    case "healthy":
    case "under_budget":
      return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
    case "warning":
    case "approaching":
      return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
    case "exceeded":
    case "over_budget":
      return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
    default:
      return "border-border/50 text-muted-foreground";
  }
}

function budgetBarColor(pct: number): string {
  if (pct < 0.7) return "bg-sylion-green";
  if (pct < 0.9) return "bg-sylion-amber";
  return "bg-sylion-red";
}

/* ============================================================
   Page Component
   ============================================================ */

export default function BudgetPage() {
  const { data: healthRaw, loading: healthLoading, refresh: refreshHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: budgetRaw, loading: budgetLoading, refresh: refreshBudgets } = useModelBudgets();
  const { data: summaryRaw, loading: summaryLoading, refresh: refreshSummary } = useSpendingSummary();
  const { data: alertsRaw, loading: alertsLoading, refresh: refreshAlerts } = useCostAlerts();

  const loading = healthLoading || budgetLoading || summaryLoading || alertsLoading;

  const budgets: BudgetEntry[] = ((budgetRaw as any).budgets || []).map(normalizeBudgetEntry);
  const summary: SpendingSummary = normalizeSummary(summaryRaw as any, budgets);
  const alerts: any[] = (alertsRaw as any).alerts || [];

  const [activeTab, setActiveTab] = useState("budgets");

  // F-bug-budget: page was view-only — user couldn't add or edit a model
  // budget. Now we expose an "Add budget" modal that posts to
  // /api/v1/model-budget/budgets via api.setModelBudgetFull.
  const [showAddBudget, setShowAddBudget] = useState(false);
  const [newModelId, setNewModelId] = useState("");
  const [newDailyLimit, setNewDailyLimit] = useState("10");
  const [newMonthlyLimit, setNewMonthlyLimit] = useState("200");
  const [newAlertPct, setNewAlertPct] = useState("80");
  const [submittingBudget, setSubmittingBudget] = useState(false);
  const [budgetError, setBudgetError] = useState<string | null>(null);

  /* ---------- Derived ---------- */
  const alertCount = useMemo(() => alerts.filter((a) => !a.acknowledged).length, [alerts]);

  const handleSubmitBudget = async () => {
    setBudgetError(null);
    if (!newModelId.trim()) {
      setBudgetError("Podaj identyfikator modelu (np. claude-haiku-4-5)");
      return;
    }
    const daily = Number(newDailyLimit);
    const monthly = Number(newMonthlyLimit);
    const alertPct = Number(newAlertPct);
    if (!Number.isFinite(daily) || daily < 0) {
      setBudgetError("Limit dzienny musi byc liczba >= 0");
      return;
    }
    if (!Number.isFinite(monthly) || monthly < 0) {
      setBudgetError("Limit miesieczny musi byc liczba >= 0");
      return;
    }
    setSubmittingBudget(true);
    try {
      await api.setModelBudgetFull(newModelId.trim(), daily, monthly, alertPct);
      setShowAddBudget(false);
      setNewModelId("");
      setNewDailyLimit("10");
      setNewMonthlyLimit("200");
      setNewAlertPct("80");
      refreshBudgets();
      refreshSummary();
    } catch (err) {
      setBudgetError(err instanceof Error ? err.message : "Błąd zapisu budżetu");
    } finally {
      setSubmittingBudget(false);
    }
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
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
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
            <Wallet className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Budżet modeli</h1>
            <p className="text-sm text-muted-foreground">Limity wydatków i śledzenie kosztów</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane budżetu wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { refreshHealth(); refreshBudgets(); refreshSummary(); refreshAlerts(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  const refresh = () => { refreshBudgets(); refreshSummary(); refreshAlerts(); refreshHealth(); };

  /* ---------- Stats ---------- */
  const stats = [
    {
      label: "Śledzone modele",
      value: budgets.length,
      icon: BarChart3,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Wydano dzisiaj",
      value: summary.total_spent > 0 ? fmtUSD(summary.total_spent) : "--",
      icon: CreditCard,
      color: "text-sylion-amber",
      bgColor: "bg-sylion-amber/10",
    },
    {
      label: "Wydano w tym miesiącu",
      value: summary.total_budget > 0 ? fmtUSD(summary.total_spent) : "--",
      icon: CalendarDays,
      color: "text-purple-400",
      bgColor: "bg-purple-400/10",
    },
    {
      label: "Alerty budżetowe",
      value: alertCount,
      icon: AlertTriangle,
      color: alertCount > 0 ? "text-sylion-red" : "text-sylion-green",
      bgColor: alertCount > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-amber/10 border border-sylion-amber/20 flex items-center justify-center">
            <Wallet className="w-4 h-4 text-sylion-amber" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center gap-2">
              Budżet modeli
              <HelpTip text="Dzienne i miesięczne limity wydatków per-model (USD). Gdy model przekroczy próg alertu (default 80%) — pojawia się alert; gdy przekroczy 100% — system automatycznie przełącza na model awaryjny (fallback). Konfiguracja per-model: limit dzienny + miesięczny + próg alertu." />
            </h1>
            <p className="text-sm text-muted-foreground">Limity wydatków i śledzenie kosztów</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10"
            onClick={() => setShowAddBudget(true)}
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Dodaj budżet
          </Button>
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* F-bug-budget: add-budget modal */}
      {showAddBudget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <Card className="max-w-md w-full mx-4 p-5 border border-sylion-blue/30 bg-card space-y-4">
            <div className="flex items-center gap-2">
              <Plus className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-sm font-semibold text-sylion-blue">Dodaj budżet modelu</h3>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                  ID modelu
                  <HelpTip text="Identyfikator modelu LLM (np. 'claude-haiku-4-5', 'gpt-4o-mini', 'qwen2.5:7b'). Musi być dokładnie tym samym ID który widnieje w hierarchii modeli — używaj zakładki AI Models do podglądu." />
                </label>
                <input
                  type="text"
                  value={newModelId}
                  onChange={(e) => setNewModelId(e.target.value)}
                  placeholder="np. claude-haiku-4-5"
                  disabled={submittingBudget}
                  className="w-full rounded-md border border-border/50 bg-background/60 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-sylion-blue/50"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                    Limit dzienny (USD)
                    <HelpTip text="Maksymalna kwota w USD jaką ten model może wydać w jednym dniu. Po przekroczeniu — wstrzymanie wywołań do następnego dnia LUB automatyczny fallback na inny model. Default $10 to bezpieczny start." />
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={newDailyLimit}
                    onChange={(e) => setNewDailyLimit(e.target.value)}
                    disabled={submittingBudget}
                    className="w-full rounded-md border border-border/50 bg-background/60 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-sylion-blue/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                    Limit miesięczny (USD)
                    <HelpTip text="Twardy limit wydatków na ten model w jednym miesiącu kalendarzowym. Łapie scenariusze gdzie 30 dni z 50% limitu dziennego sumuje się do astronomicznych kwot. Default $200 = ~$6.5/dzień średnio." />
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={newMonthlyLimit}
                    onChange={(e) => setNewMonthlyLimit(e.target.value)}
                    disabled={submittingBudget}
                    className="w-full rounded-md border border-border/50 bg-background/60 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-sylion-blue/50"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                  Próg alertu (%)
                  <HelpTip text="Procent limitu (dziennego lub miesięcznego) po którym system wysyła alert (do dashboardu + Notifications) ale jeszcze NIE blokuje. Default 80% daje 20% bufora na zareagowanie. Niższy próg = wcześniejsze ostrzeżenie." />
                </label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={5}
                  value={newAlertPct}
                  onChange={(e) => setNewAlertPct(e.target.value)}
                  disabled={submittingBudget}
                  className="w-full rounded-md border border-border/50 bg-background/60 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-sylion-blue/50"
                />
              </div>
              {budgetError && (
                <p className="text-xs text-sylion-red bg-sylion-red/10 border border-sylion-red/20 rounded px-3 py-2">
                  {budgetError}
                </p>
              )}
            </div>

            <div className="flex gap-2 justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddBudget(false)}
                disabled={submittingBudget}
              >
                Anuluj
              </Button>
              <Button
                size="sm"
                className="bg-sylion-blue/20 text-sylion-blue hover:bg-sylion-blue/30 border border-sylion-blue/40"
                onClick={handleSubmitBudget}
                disabled={submittingBudget}
              >
                {submittingBudget && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
                Zapisz budżet
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* ====== STATS ROW ====== */}
      <div className="grid grid-cols-4 gap-3">
        {stats.map((stat) => {
          const SIcon = stat.icon;
          return (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{stat.label}</p>
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
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-muted/20">
          <TabsTrigger value="budgets" className="text-xs">
            <BarChart3 className="w-3.5 h-3.5 mr-1.5" />
            Budżety modeli
          </TabsTrigger>
          <TabsTrigger value="alerts" className="text-xs">
            <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
            Alerty
            {alertCount > 0 && (
              <Badge variant="outline" className="ml-1.5 text-[9px] border-sylion-red/30 text-sylion-red bg-sylion-red/5 h-4">
                {alertCount}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ===== TAB 1: MODEL BUDGETS ===== */}
        <TabsContent value="budgets" className="mt-4">
          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-3 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-xs font-medium text-muted-foreground">Alokacje budżetu modeli</h3>
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                {budgets.length} modeli
              </span>
            </div>
            {budgets.length === 0 ? (
              <div className="p-8 text-center">
                <BarChart3 className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">Brak skonfigurowanych budżetów modeli. Dane są ładowane z backendu.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/20">
                {budgets.map((b) => {
                  const pct = b.budget_limit > 0 ? (b.spent / b.budget_limit) : 0;
                  const clampedPct = Math.min(pct, 1);
                  return (
                    <div key={b.model_id} className="px-4 py-3 hover:bg-muted/20 transition-colors">
                      <div className="flex items-center gap-3 mb-2">
                        <div className={cn(
                          "w-7 h-7 rounded-md flex items-center justify-center shrink-0",
                          pct < 0.7 ? "bg-sylion-green/10" : pct < 0.9 ? "bg-sylion-amber/10" : "bg-sylion-red/10"
                        )}>
                          <Gauge className={cn("w-3.5 h-3.5", pct < 0.7 ? "text-sylion-green" : pct < 0.9 ? "text-sylion-amber" : "text-sylion-red")} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{b.model_id}</p>
                          <p className="text-[10px] text-muted-foreground">{b.provider}</p>
                        </div>
                        <Badge variant="outline" className={cn("text-[9px] shrink-0", budgetStatusColor(b.status))}>
                          {b.status.toUpperCase()}
                        </Badge>
                      </div>

                      {/* Daily progress bar */}
                      <div className="flex items-center gap-3 ml-10">
                        <div className="flex-1">
                          <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
                            <span>Dziennie: {fmtUSD(b.spent)} / {fmtUSD(b.budget_limit)}</span>
                            <span className="font-mono">{(clampedPct * 100).toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted/30 overflow-hidden">
                            <motion.div
                              className={cn("h-full rounded-full", budgetBarColor(clampedPct))}
                              initial={{ width: 0 }}
                              animate={{ width: `${clampedPct * 100}%` }}
                              transition={{ duration: 0.8 }}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Remaining info */}
                      <div className="flex items-center gap-4 ml-10 mt-1.5 text-[10px] text-muted-foreground">
                        <span>Pozostało: <span className="font-mono text-foreground">{fmtUSD(b.remaining)}</span></span>
                        {b.fallback_model_id && (
                          <span>Awaryjny: <span className="font-mono text-foreground">{b.fallback_model_id}</span></span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ===== TAB 2: ALERTS ===== */}
        <TabsContent value="alerts" className="mt-4">
          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-3 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-xs font-medium text-muted-foreground">Alerty budżetowe</h3>
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                {alerts.length} łącznie
              </span>
            </div>
            {alerts.length === 0 ? (
              <div className="p-8 text-center">
                <CheckCircle2 className="w-6 h-6 text-sylion-green mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">Brak alertów budżetowych. Wszystkie modele w limitach wydatków.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/20">
                {alerts.map((alert, idx) => (
                  <div key={alert.id || idx} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
                    <div className={cn(
                      "w-7 h-7 rounded-md flex items-center justify-center shrink-0",
                      alert.severity === "critical" ? "bg-sylion-red/10" : "bg-sylion-amber/10"
                    )}>
                      {alert.severity === "critical" ? (
                        <XCircle className="w-3.5 h-3.5 text-sylion-red" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5 text-sylion-amber" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{alert.message || alert.title || `Alert #${idx + 1}`}</p>
                      <p className="text-[10px] text-muted-foreground">{alert.model_id || "System"}</p>
                    </div>
                    {alert.acknowledged ? (
                      <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground shrink-0">
                        POTWIERDZONO
                      </Badge>
                    ) : (
                      <Badge variant="outline" className={cn("text-[9px] shrink-0", budgetStatusColor(alert.severity === "critical" ? "exceeded" : "warning"))}>
                        AKTYWNY
                      </Badge>
                    )}
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0 w-24 text-right">
                      <Clock className="w-2.5 h-2.5" />
                      {alert.timestamp ? new Date(alert.timestamp).toLocaleDateString() : "--"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
