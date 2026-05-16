"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tabs, TabsList, TabsTrigger, TabsContent,
} from "@/components/ui/tabs";
import {
  DollarSign, AlertTriangle, ArrowUpDown,
  RefreshCw, Wallet, Receipt, PieChart, Settings2,
  RotateCcw, ChevronDown, ChevronUp, Clock, Zap,
  CircleDot, BarChart3, TrendingUp, TrendingDown,
  Minus, Activity, CalendarDays, Timer, Lightbulb,
  ShieldAlert, ArrowRight, Gauge, WifiOff,
} from "lucide-react";
import { useHealth, useModelBudgets, useModelTransactions, useSpendingSummary, useCostAlerts } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { HelpTip } from "@/components/common/HelpTip";
import { CostAlertsSection } from "./alerts-section";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

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

interface Transaction {
  id: string;
  model_id: string;
  provider: string;
  amount: number;
  tokens_in: number;
  tokens_out: number;
  task_type: string;
  timestamp: number | string;
}

interface SpendingSummary {
  total_budget: number;
  total_spent: number;
  total_remaining: number;
  by_model: { model_id: string; spent: number }[];
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function fmtUSD(n: unknown) {
  const value = toNumber(n);
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

function fmtTokens(n: unknown) {
  const value = toNumber(n);
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

function fmtTimestamp(ts: number | string): string {
  const numericTs = typeof ts === "number" ? ts : Number(ts);
  const d = Number.isFinite(numericTs)
    ? new Date(numericTs < 10_000_000_000 ? numericTs * 1000 : numericTs)
    : new Date(ts);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60_000) return "przed chwilą";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m temu`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h temu`;
  return d.toLocaleDateString();
}

function budgetPct(spent: number, limit: number) {
  return limit > 0 ? Math.min((spent / limit) * 100, 100) : 0;
}

function normalizeBudgetEntry(raw: any): BudgetEntry {
  const dailyLimit = toNumber(raw?.daily_limit);
  const monthlyLimit = toNumber(raw?.monthly_limit);
  const limit = toNumber(raw?.budget_limit, dailyLimit || monthlyLimit);
  const spent = toNumber(raw?.spent, toNumber(raw?.spent_today, toNumber(raw?.spent_this_month)));
  return {
    model_id: String(raw?.model_id || "unknown-model"),
    provider: String(raw?.provider || raw?.runtime_provider || "unknown"),
    budget_limit: limit,
    spent,
    remaining: toNumber(raw?.remaining, Math.max(limit - spent, 0)),
    status: String(raw?.status || (limit > 0 && spent >= limit ? "exhausted" : "healthy")),
    fallback_model_id: String(raw?.fallback_model_id || ""),
    pct_used: toNumber(raw?.pct_used, limit > 0 ? spent / limit : 0),
  };
}

function normalizeTransaction(raw: any): Transaction {
  const tokens = toNumber(raw?.tokens);
  return {
    id: String(raw?.id || raw?.usage_id || raw?.transaction_id || ""),
    model_id: String(raw?.model_id || "unknown-model"),
    provider: String(raw?.provider || "unknown"),
    amount: toNumber(raw?.amount, toNumber(raw?.cost)),
    tokens_in: toNumber(raw?.tokens_in, toNumber(raw?.prompt_tokens, tokens)),
    tokens_out: toNumber(raw?.tokens_out, toNumber(raw?.completion_tokens)),
    task_type: String(raw?.task_type || raw?.operation || "model_usage"),
    timestamp: raw?.timestamp || raw?.created_at || Date.now(),
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

function barColor(pct: number) {
  if (pct >= 90) return "bg-sylion-red";
  if (pct >= 80) return "bg-sylion-amber";
  return "bg-sylion-green";
}

function pctColor(pct: number) {
  if (pct >= 90) return "text-sylion-red";
  if (pct >= 80) return "text-sylion-amber";
  return "text-sylion-green";
}

const TASK_COLORS: Record<string, string> = {
  code_generation: "bg-blue-500/15 text-blue-400",
  analysis: "bg-purple-500/15 text-purple-400",
  evaluation: "bg-sylion-green/15 text-sylion-green",
  routing: "bg-sylion-amber/15 text-sylion-amber",
  synthesis: "bg-cyan-500/15 text-cyan-400",
  planning: "bg-orange-500/15 text-orange-400",
  completion: "bg-sylion-blue/15 text-sylion-blue",
  embedding: "bg-pink-500/15 text-pink-400",
  chat: "bg-emerald-500/15 text-emerald-400",
};

const BAR_COLORS = [
  "bg-sylion-blue", "bg-sylion-green", "bg-sylion-amber",
  "bg-cyan-400", "bg-purple-400", "bg-pink-400",
  "bg-emerald-400", "bg-orange-400",
];

/* ------------------------------------------------------------------ */
/*  Circular Gauge                                                     */
/* ------------------------------------------------------------------ */

function CircularGauge({ pct, size = 140, strokeWidth = 10 }: { pct: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const color = pct >= 90 ? "#ef4444" : pct >= 80 ? "#f59e0b" : "#22c55e";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(148,163,184,0.08)" strokeWidth={strokeWidth} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-2xl font-bold", pctColor(pct))}>{pct.toFixed(1)}%</span>
        <span className="text-[9px] text-muted-foreground uppercase tracking-wider mt-0.5">wykorzystano</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Budget Edit Row (inline)                                           */
/* ------------------------------------------------------------------ */

function BudgetEditRow({
  entry,
  onSave,
  onCancel,
}: {
  entry: BudgetEntry;
  onSave: (modelId: string, limit: number, provider: string, fallback: string) => void;
  onCancel: () => void;
}) {
  const [limit, setLimit] = useState(String(entry.budget_limit));
  const [fallback, setFallback] = useState(entry.fallback_model_id ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await onSave(entry.model_id, parseFloat(limit) || 0, entry.provider, fallback);
    } finally {
      setSaving(false);
    }
  }, [entry.model_id, entry.provider, limit, fallback, onSave]);

  return (
    <motion.tr
      initial={{ opacity: 0, backgroundColor: "rgba(148,163,184,0.04)" }}
      animate={{ opacity: 1 }}
      className="border-b last:border-0"
      style={{ borderColor: "rgba(148,163,184,0.04)" }}
    >
      <td className="px-4 py-3 font-medium text-foreground" colSpan={7}>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] text-muted-foreground">Limit $</span>
          <input
            type="number"
            step="0.01"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            className="w-28 rounded-md border bg-transparent px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            style={{ borderColor: "rgba(148,163,184,0.15)" }}
          />
          <span className="text-[11px] text-muted-foreground">Awaryjny</span>
          <input
            type="text"
            value={fallback}
            onChange={(e) => setFallback(e.target.value)}
            placeholder="brak"
            className="w-40 rounded-md border bg-transparent px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            style={{ borderColor: "rgba(148,163,184,0.15)" }}
          />
          <Button size="xs" onClick={handleSave} disabled={saving}>
            {saving ? "Zapisywanie..." : "Zapisz"}
          </Button>
          <Button size="xs" variant="ghost" onClick={onCancel}>
            Anuluj
          </Button>
        </div>
      </td>
    </motion.tr>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function CostsPage() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  const { data: budgetsData, refresh: refreshBudgets } = useModelBudgets();
  const { data: txData, refresh: refreshTx } = useModelTransactions(undefined, 50);
  const { data: summaryData, refresh: refreshSummary } = useSpendingSummary();
  const { data: alertsData } = useCostAlerts();

  const budgets: BudgetEntry[] = useMemo(() => (budgetsData?.budgets ?? []).map(normalizeBudgetEntry), [budgetsData]);
  const transactions: Transaction[] = useMemo(() => (txData?.transactions ?? []).map(normalizeTransaction), [txData]);
  const summary: SpendingSummary = useMemo(() => normalizeSummary(summaryData, budgets), [summaryData, budgets]);

  const [editingModel, setEditingModel] = useState<string | null>(null);
  const [sortField, setSortField] = useState<"spent" | "model_id" | "pct">("spent");
  const [sortAsc, setSortAsc] = useState(false);
  const [txFilter, setTxFilter] = useState<string>("all");

  // Auto-refresh every 10s
  useEffect(() => {
    const id = setInterval(() => {
      if (backendLive) {
        refreshBudgets();
        refreshTx();
        refreshSummary();
      }
    }, 10_000);
    return () => clearInterval(id);
  }, [backendLive, refreshBudgets, refreshTx, refreshSummary]);

  const totalBudget = summary?.total_budget || budgets.reduce((s, b) => s + (b.budget_limit || 0), 0);
  const totalSpent = summary?.total_spent || budgets.reduce((s, b) => s + (b.spent || 0), 0);
  const totalRemaining = summary?.total_remaining || Math.max(totalBudget - totalSpent, 0);
  const totalPct = budgetPct(totalSpent, totalBudget);

  const alertCount = (alertsData?.alerts ?? []).length;
  const activeModels = budgets.length || transactions.reduce((acc, tx) => {
    if (!acc.has(tx.model_id)) acc.add(tx.model_id);
    return acc;
  }, new Set<string>()).size || 0;

  // Days in current month
  const now = new Date();
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const dayOfMonth = now.getDate();
  const dailyAvg = dayOfMonth > 0 ? totalSpent / dayOfMonth : 0;

  // Sorted budgets
  const sortedBudgets = useMemo(() => {
    const copy = [...budgets];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortField === "spent") cmp = (a.spent || 0) - (b.spent || 0);
      else if (sortField === "model_id") cmp = (a.model_id || "").localeCompare(b.model_id || "");
      else if (sortField === "pct") cmp = budgetPct(a.spent, a.budget_limit) - budgetPct(b.spent, b.budget_limit);
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [budgets, sortField, sortAsc]);

  // Per-model analytics derived from transactions
  const modelAnalytics = useMemo(() => {
    const map = new Map<string, {
      model_id: string;
      totalCost: number;
      requestCount: number;
      promptTokens: number;
      completionTokens: number;
      lastTimestamp: number;
    }>();
    for (const tx of transactions) {
      const existing = map.get(tx.model_id) || {
        model_id: tx.model_id,
        totalCost: 0,
        requestCount: 0,
        promptTokens: 0,
        completionTokens: 0,
        lastTimestamp: 0,
      };
      existing.totalCost += tx.amount || 0;
      existing.requestCount += 1;
      existing.promptTokens += tx.tokens_in || 0;
      existing.completionTokens += tx.tokens_out || 0;
      const t = typeof tx.timestamp === "number" ? tx.timestamp : new Date(tx.timestamp).getTime();
      if (t > existing.lastTimestamp) existing.lastTimestamp = t;
      map.set(tx.model_id, existing);
    }
    return Array.from(map.values()).sort((a, b) => b.totalCost - a.totalCost);
  }, [transactions]);

  // Filtered transactions
  const filteredTransactions = useMemo(() => {
    if (txFilter === "all") return transactions;
    return transactions.filter((tx) => tx.model_id === txFilter);
  }, [transactions, txFilter]);

  const txTotalAmount = filteredTransactions.reduce((s, tx) => s + (tx.amount || 0), 0);
  const txTotalTokens = filteredTransactions.reduce((s, tx) => s + (tx.tokens_in || 0) + (tx.tokens_out || 0), 0);

  // Predictions
  const predictedEOM = dailyAvg * daysInMonth;
  const daysUntilExhaustion = dailyAvg > 0 ? Math.floor(totalRemaining / dailyAvg) : Infinity;
  const recommendedDaily = totalBudget > 0 ? (totalBudget - totalSpent) / Math.max(daysInMonth - dayOfMonth, 1) : 0;

  const optimizationSuggestions = useMemo(() => {
    const suggestions: { icon: React.ElementType; text: string; severity: "info" | "warning" | "critical" }[] = [];
    if (totalPct > 80 && dayOfMonth < daysInMonth - 3) {
      suggestions.push({ icon: AlertTriangle, text: `Budget is ${totalPct.toFixed(0)}% consumed with ${daysInMonth - dayOfMonth} days remaining. Consider reducing high-cost model usage.`, severity: "critical" });
    }
    const topModel = modelAnalytics[0];
    if (topModel && modelAnalytics.length > 1) {
      const topShare = totalSpent > 0 ? (topModel.totalCost / totalSpent) * 100 : 0;
      if (topShare > 60) {
        suggestions.push({ icon: PieChart, text: `${topModel.model_id} accounts for ${topShare.toFixed(0)}% of total spend. Consider load-balancing to cheaper models for routine tasks.`, severity: "warning" });
      }
    }
    if (dailyAvg > recommendedDaily * 1.5 && recommendedDaily > 0) {
      suggestions.push({ icon: TrendingDown, text: `Daily average (${fmtUSD(dailyAvg)}) exceeds recommended rate (${fmtUSD(recommendedDaily)}). Cut spending by ${(((dailyAvg - recommendedDaily) / dailyAvg) * 100).toFixed(0)}% to stay on budget.`, severity: "warning" });
    }
    for (const b of budgets) {
      const p = budgetPct(b.spent, b.budget_limit);
      if (p >= 95) {
        suggestions.push({ icon: ShieldAlert, text: `${b.model_id} is at ${p.toFixed(0)}% budget. Fallback model (${b.fallback_model_id || "none"}) will activate soon.`, severity: "critical" });
      }
    }
    if (suggestions.length === 0) {
      suggestions.push({ icon: Lightbulb, text: "Spending is within normal parameters. No optimization actions required at this time.", severity: "info" });
    }
    return suggestions;
  }, [totalPct, dayOfMonth, daysInMonth, modelAnalytics, dailyAvg, recommendedDaily, budgets, totalSpent]);

  const handleSaveBudget = useCallback(async (modelId: string, limit: number, provider: string, fallback: string) => {
    await api.configureModelBudget(modelId, limit, provider, fallback);
    setEditingModel(null);
    refreshBudgets();
    refreshSummary();
  }, [refreshBudgets, refreshSummary]);

  const handleResetBudget = useCallback(async (modelId: string) => {
    await api.resetModelBudget(modelId);
    refreshBudgets();
    refreshSummary();
  }, [refreshBudgets, refreshSummary]);

  const toggleSort = useCallback((field: "spent" | "model_id" | "pct") => {
    if (sortField === field) setSortAsc((a) => !a);
    else { setSortField(field); setSortAsc(false); }
  }, [sortField]);

  const handleRefreshAll = useCallback(() => {
    refreshBudgets();
    refreshTx();
    refreshSummary();
  }, [refreshBudgets, refreshTx, refreshSummary]);

  const isExhausted = (entry: BudgetEntry) => {
    const pct = budgetPct(entry.spent, entry.budget_limit);
    return entry.status === "exhausted" || pct >= 100;
  };

  const isNearLimit = (entry: BudgetEntry) => {
    const pct = budgetPct(entry.spent, entry.budget_limit);
    return pct >= 80 && pct < 100;
  };

  // Get unique model IDs from transactions for filter
  const txModelIds = useMemo(() => {
    const ids = new Set<string>();
    for (const tx of transactions) ids.add(tx.model_id);
    return Array.from(ids).sort();
  }, [transactions]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-sylion-green/10 flex items-center justify-center">
            <DollarSign className="w-5 h-5 text-sylion-green" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Koszty
              <HelpTip text="Total spending dashboard — koszt LLM + storage + compute + bandwidth, breakdown per-projekt/per-model. Eksport CSV; thresholdy z alertami." />
            </h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Monitorowanie budżetu i analityka wydatków</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="xs" variant="ghost" onClick={handleRefreshAll}>
            <RefreshCw className="w-3 h-3" />
            Odśwież
          </Button>
          <Badge className={cn(
            "text-[9px] px-2 py-0.5 border",
            backendLive ? "bg-sylion-green/10 text-sylion-green border-sylion-green/30" : "bg-sylion-red/10 text-sylion-red border-sylion-red/30"
          )}>
            {backendLive ? "NA ŻYWO" : (<><WifiOff className="w-2.5 h-2.5 mr-1 inline" />OFFLINE</>)}
          </Badge>
        </div>
      </motion.div>

      {/* Offline message */}
      {!backendLive && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="rounded-xl border border-sylion-red/20 p-8 flex flex-col items-center justify-center" style={{ background: "rgba(15,22,41,0.95)" }}>
            <WifiOff className="w-10 h-10 text-sylion-red/60 mb-3" />
            <p className="text-sm text-sylion-red/80 font-medium">Backend niedostępny</p>
            <p className="text-[11px] text-muted-foreground mt-1">Uruchom backend: <code className="text-primary">scripts/start-server.bat</code></p>
          </div>
        </motion.div>
      )}

      {/* ---- Content (only when backend is live) ---- */}
      {backendLive && <div>

      {/* ---- Stats Row (4 cards) ---- */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: "Łączne wydatki",
            sublabel: "W tym miesiącu",
            value: fmtUSD(totalSpent),
            icon: DollarSign,
            color: "text-sylion-amber",
            detail: `${totalPct.toFixed(1)}% z ${fmtUSD(totalBudget)}`,
          },
          {
            label: "Pozostały budżet",
            sublabel: `${(100 - totalPct).toFixed(1)}% pozostało`,
            value: fmtUSD(totalRemaining),
            icon: Wallet,
            color: totalRemaining > totalBudget * 0.2 ? "text-sylion-green" : totalRemaining > 0 ? "text-sylion-amber" : "text-sylion-red",
            detail: totalBudget > 0 ? undefined : undefined,
            hasBar: true,
          },
          {
            label: "Aktywne modele",
            sublabel: "Z budżetem",
            value: activeModels,
            icon: Activity,
            color: "text-sylion-blue",
            detail: `${budgets.filter(b => !isExhausted(b)).length} aktywnych`,
          },
          {
            label: "Średnia dzienna",
            sublabel: `Dzień ${dayOfMonth}/${daysInMonth}`,
            value: fmtUSD(dailyAvg),
            icon: CalendarDays,
            color: "text-sylion-blue",
            detail: recommendedDaily > 0 ? `Zal.: ${fmtUSD(recommendedDaily)}/dzień` : undefined,
          },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Card size="sm" className="bg-[#0f1629]" style={{ border: "1px solid rgba(148,163,184,0.06)" }}>
              <CardHeader className="pb-0">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                    {s.label}
                    <HelpTip text={
                      s.label === "Łączne wydatki" ? "Suma kosztów (USD) wszystkich modeli w bieżącym miesiącu."
                      : s.label === "Pozostały budżet" ? "Kwota dostępna do końca miesiąca przy bieżących limitach."
                      : s.label === "Aktywne modele" ? "Liczba modeli z aktywnym budżetem (poniżej limitu)."
                      : "Średnie wydatki na dzień obliczone narastająco od początku miesiąca."
                    } />
                  </p>
                  <s.icon className={cn("w-4 h-4", s.color)} />
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-bold text-foreground">{s.value}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{s.sublabel}</p>
                {s.hasBar && totalBudget > 0 && (
                  <div className="mt-2 h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${100 - totalPct}%` }}
                      transition={{ duration: 0.8, ease: "easeOut" }}
                      className={cn("h-full rounded-full", barColor(100 - totalPct))}
                    />
                  </div>
                )}
                {s.detail && <p className="text-[9px] text-muted-foreground/70 mt-1">{s.detail}</p>}
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* ---- Tabs ---- */}
      <Tabs defaultValue="budget">
        <HelpTip text="Przegląd budżetu: limity i wykorzystanie per model. Transakcje: pojedyncze wywołania LLM. Analityka: agregaty per-model. Prognozy: koniec miesiąca, dni do wyczerpania, sugestie optymalizacji." />
        <TabsList>
          <TabsTrigger value="budget">
            <Gauge className="w-3.5 h-3.5" />
            Przegląd budżetu
          </TabsTrigger>
          <TabsTrigger value="transactions">
            <Receipt className="w-3.5 h-3.5" />
            Transakcje
          </TabsTrigger>
          <TabsTrigger value="analytics">
            <BarChart3 className="w-3.5 h-3.5" />
            Analityka modeli
          </TabsTrigger>
          <TabsTrigger value="predictions">
            <TrendingUp className="w-3.5 h-3.5" />
            Prognozy
          </TabsTrigger>
        </TabsList>

        {/* ============================================================ */}
        {/*  Tab 1: Budget Overview                                      */}
        {/* ============================================================ */}
        <TabsContent value="budget">
          <div className="grid grid-cols-12 gap-4">
            {/* Left: circular gauge + budget alerts */}
            <div className="col-span-4 space-y-4">
              {/* Circular gauge */}
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4 }}
                className="rounded-xl border p-5 flex flex-col items-center"
                style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
              >
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-4">Łączne wykorzystanie budżetu</p>
                <CircularGauge pct={totalPct} />
                <div className="flex items-center gap-6 mt-4 text-[10px]">
                  <div className="text-center">
                    <p className="text-muted-foreground">Wydano</p>
                    <p className="font-semibold text-foreground">{fmtUSD(totalSpent)}</p>
                  </div>
                  <div className="w-px h-8 bg-white/5" />
                  <div className="text-center">
                    <p className="text-muted-foreground">Budżet</p>
                    <p className="font-semibold text-foreground">{fmtUSD(totalBudget)}</p>
                  </div>
                  <div className="w-px h-8 bg-white/5" />
                  <div className="text-center">
                    <p className="text-muted-foreground">Pozostało</p>
                    <p className={cn("font-semibold", totalRemaining > 0 ? "text-sylion-green" : "text-sylion-red")}>{fmtUSD(totalRemaining)}</p>
                  </div>
                </div>
              </motion.div>

              {/* Budget alerts summary */}
              <div
                className="rounded-xl border p-4"
                style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
              >
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-3">Podsumowanie budżetów</p>
                <div className="space-y-2">
                  {[
                    { label: "Poniżej limitu", count: budgets.filter(b => budgetPct(b.spent, b.budget_limit) < 80).length, color: "text-sylion-green", bg: "bg-sylion-green/10" },
                    { label: "Blisko limitu", count: budgets.filter(b => { const p = budgetPct(b.spent, b.budget_limit); return p >= 80 && p < 100; }).length, color: "text-sylion-amber", bg: "bg-sylion-amber/10" },
                    { label: "Powyżej limitu", count: budgets.filter(b => budgetPct(b.spent, b.budget_limit) >= 100).length, color: "text-sylion-red", bg: "bg-sylion-red/10" },
                  ].map(s => (
                    <div key={s.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={cn("w-2 h-2 rounded-full", s.bg)} />
                        <span className={cn("text-[11px]", s.color)}>{s.label}</span>
                      </div>
                      <span className="text-[11px] font-semibold text-foreground">{s.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: per-model budget cards */}
            <div className="col-span-8 space-y-3">
              {sortedBudgets.length === 0 ? (
                <EmptyState message="Połącz się z backendem aby zobaczyć budżety modeli" />
              ) : (
                sortedBudgets.map((entry, i) => {
                  const pct = budgetPct(entry.spent, entry.budget_limit);
                  const exhausted = isExhausted(entry);
                  const nearLimit = isNearLimit(entry);
                  // Estimated daily/weekly/monthly values derived from recorded spend.
                  const dailyBudget = entry.budget_limit / daysInMonth;
                  const weeklyBudget = entry.budget_limit / (daysInMonth / 7);
                  const dailySpent = entry.spent / Math.max(dayOfMonth, 1);
                  const weeklySpent = dailySpent * 7;

                  // Find last transaction time for this model
                  const lastTx = transactions.find(tx => tx.model_id === entry.model_id);

                  return (
                    <motion.div
                      key={entry.model_id}
                      initial={{ opacity: 0, x: 12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.04 }}
                      className="rounded-xl border p-4"
                      style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold",
                            BAR_COLORS[i % BAR_COLORS.length].replace("bg-", "bg-"),
                          )} style={{ backgroundColor: `${["#3b82f6", "#22c55e", "#f59e0b", "#22d3ee", "#a855f7", "#ec4899", "#34d399", "#f97316"][i % 8]}20`, color: ["#3b82f6", "#22c55e", "#f59e0b", "#22d3ee", "#a855f7", "#ec4899", "#34d399", "#f97316"][i % 8] }}>
                            {(entry.model_id || "?").charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-[12px] font-semibold text-foreground">{entry.model_id}</p>
                            <p className="text-[10px] text-muted-foreground capitalize">{entry.provider}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {lastTx && (
                            <span className="text-[9px] text-muted-foreground flex items-center gap-1">
                              <Clock className="w-2.5 h-2.5" />
                              {fmtTimestamp(lastTx.timestamp)}
                            </span>
                          )}
                          {exhausted ? (
                            <Badge className="text-[8px] px-1.5 py-0 bg-sylion-red/15 text-sylion-red border-sylion-red/30 border">Powyżej limitu</Badge>
                          ) : nearLimit ? (
                            <Badge className="text-[8px] px-1.5 py-0 bg-sylion-amber/15 text-sylion-amber border-sylion-amber/30 border flex items-center gap-0.5">
                              <AlertTriangle className="w-2.5 h-2.5" />
                              Blisko limitu
                            </Badge>
                          ) : (
                            <Badge className="text-[8px] px-1.5 py-0 bg-sylion-green/15 text-sylion-green border-sylion-green/30 border">Poniżej limitu</Badge>
                          )}
                        </div>
                      </div>

                      {/* Daily / Weekly / Monthly bars */}
                      <div className="grid grid-cols-3 gap-3 mb-3">
                        {[
                          { label: "Dziennie", spent: dailySpent, budget: dailyBudget },
                          { label: "Tygodniowo", spent: weeklySpent, budget: weeklyBudget },
                          { label: "Miesięcznie", spent: entry.spent, budget: entry.budget_limit },
                        ].map(period => {
                          const ppct = budgetPct(period.spent, period.budget);
                          return (
                            <div key={period.label}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[9px] text-muted-foreground">{period.label}</span>
                                <span className={cn("text-[9px] font-medium", pctColor(ppct))}>{ppct.toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${ppct}%` }}
                                  transition={{ duration: 0.6, ease: "easeOut", delay: i * 0.04 }}
                                  className={cn("h-full rounded-full", barColor(ppct))}
                                />
                              </div>
                              <div className="flex justify-between mt-0.5">
                                <span className="text-[8px] text-muted-foreground">{fmtUSD(period.spent)}</span>
                                <span className="text-[8px] text-muted-foreground">{fmtUSD(period.budget)}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Spent vs remaining summary */}
                      <div className="flex items-center gap-4 text-[10px]">
                        <span className="text-muted-foreground">Wydano: <span className="font-medium text-foreground">{fmtUSD(entry.spent)}</span></span>
                        <span className="text-muted-foreground">Pozostało: <span className={cn("font-medium", entry.remaining >= 0 ? "text-foreground" : "text-sylion-red")}>{fmtUSD(entry.remaining)}</span></span>
                        {entry.fallback_model_id && <span className="text-muted-foreground">Awaryjny: <span className="text-foreground">{entry.fallback_model_id}</span></span>}
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>
          </div>

          {/* Budget Alerts Section */}
          <div className="mt-5">
            <CostAlertsSection />
          </div>
        </TabsContent>

        {/* ============================================================ */}
        {/*  Tab 2: Transactions                                         */}
        {/* ============================================================ */}
        <TabsContent value="transactions">
          {!backendLive && transactions.length === 0 ? (
            <EmptyState message="Połącz się z backendem aby zobaczyć transakcje" />
          ) : (
            <div className="rounded-xl border overflow-hidden" style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}>
              {/* Filter bar */}
              <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Ostatnie transakcje</span>
                  <span className="text-[9px] text-muted-foreground bg-white/5 px-1.5 py-0.5 rounded">{filteredTransactions.length} rekordów</span>
                  <span className="text-[9px] text-sylion-green flex items-center gap-0.5">
                    <RefreshCw className="w-2.5 h-2.5 animate-spin" style={{ animationDuration: "3s" }} />
                    Auto-odświeżanie
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] text-muted-foreground">Filtr:</span>
                  <select
                    value={txFilter}
                    onChange={(e) => setTxFilter(e.target.value)}
                    className="rounded-md border bg-transparent px-2 py-0.5 text-[10px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    style={{ borderColor: "rgba(148,163,184,0.15)" }}
                  >
                    <option value="all">Wszystkie modele</option>
                    {txModelIds.map(id => (
                      <option key={id} value={id}>{id}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="max-h-[420px] overflow-y-auto">
                <table className="w-full text-[11px]">
                  <thead className="sticky top-0" style={{ background: "rgba(15,22,41,0.98)" }}>
                    <tr className="text-muted-foreground text-[10px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                      <th className="text-left px-4 py-2">Model</th>
                      <th className="text-left px-4 py-2">Typ</th>
                      <th className="text-right px-4 py-2">Tokeny wejściowe</th>
                      <th className="text-right px-4 py-2">Tokeny wyjściowe</th>
                      <th className="text-right px-4 py-2">Koszt</th>
                      <th className="text-right px-4 py-2">Czas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTransactions.map((tx, i) => (
                      <motion.tr
                        key={tx.id ?? i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.015 }}
                        className="border-b last:border-0 hover:bg-white/[0.02] transition-colors"
                        style={{ borderColor: "rgba(148,163,184,0.03)" }}
                      >
                        <td className="px-4 py-2 font-medium text-foreground">{tx.model_id}</td>
                        <td className="px-4 py-2">
                          <Badge className={cn("text-[8px] px-1.5 py-0 border-0", TASK_COLORS[tx.task_type] || "bg-white/5 text-muted-foreground")}>
                            {tx.task_type}
                          </Badge>
                        </td>
                        <td className="px-4 py-2 text-right text-muted-foreground">{fmtTokens(tx.tokens_in)}</td>
                        <td className="px-4 py-2 text-right text-muted-foreground">{fmtTokens(tx.tokens_out)}</td>
                        <td className="px-4 py-2 text-right font-medium text-sylion-amber">{fmtUSD(tx.amount)}</td>
                        <td className="px-4 py-2 text-right text-muted-foreground flex items-center justify-end gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {fmtTimestamp(tx.timestamp)}
                        </td>
                      </motion.tr>
                    ))}
                    {filteredTransactions.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground text-xs">
                          Brak zarejestrowanych transakcji
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {/* Sum totals footer */}
              <div className="px-4 py-3 border-t flex items-center justify-between" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                <div className="flex items-center gap-4 text-[10px]">
                  <span className="text-muted-foreground">Łączny koszt: <span className="font-semibold text-sylion-amber">{fmtUSD(txTotalAmount)}</span></span>
                  <span className="text-muted-foreground">Łączne tokeny: <span className="font-semibold text-foreground">{fmtTokens(txTotalTokens)}</span></span>
                  <span className="text-muted-foreground">Transakcje: <span className="font-semibold text-foreground">{filteredTransactions.length}</span></span>
                </div>
                <span className="text-[9px] text-muted-foreground">
                  Śr. na transakcję: {filteredTransactions.length > 0 ? fmtUSD(txTotalAmount / filteredTransactions.length) : "$0.00"}
                </span>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ============================================================ */}
        {/*  Tab 3: Per-Model Analytics                                  */}
        {/* ============================================================ */}
        <TabsContent value="analytics">
          {modelAnalytics.length === 0 ? (
            <EmptyState message="Połącz się z backendem aby zobaczyć analitykę modeli" />
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {modelAnalytics.map((model, i) => {
                const budget = budgets.find(b => b.model_id === model.model_id);
                const pct = budget ? budgetPct(budget.spent, budget.budget_limit) : 0;
                const avgCost = model.requestCount > 0 ? model.totalCost / model.requestCount : 0;
                const totalTokens = model.promptTokens + model.completionTokens;

                // Determine trend (compare first half vs second half of transactions)
                const modelTxs = transactions.filter(tx => tx.model_id === model.model_id);
                const halfIdx = Math.floor(modelTxs.length / 2);
                const firstHalfCost = modelTxs.slice(0, halfIdx).reduce((s, tx) => s + (tx.amount || 0), 0);
                const secondHalfCost = modelTxs.slice(halfIdx).reduce((s, tx) => s + (tx.amount || 0), 0);
                const trend = secondHalfCost > firstHalfCost * 1.1 ? "up" : secondHalfCost < firstHalfCost * 0.9 ? "down" : "stable";

                return (
                  <motion.div
                    key={model.model_id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="rounded-xl border p-4"
                    style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold"
                          style={{
                            backgroundColor: `${["#3b82f6", "#22c55e", "#f59e0b", "#22d3ee", "#a855f7", "#ec4899", "#34d399", "#f97316"][i % 8]}20`,
                            color: ["#3b82f6", "#22c55e", "#f59e0b", "#22d3ee", "#a855f7", "#ec4899", "#34d399", "#f97316"][i % 8],
                          }}
                        >
                          {(model.model_id || "?").charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="text-[12px] font-semibold text-foreground">{model.model_id}</p>
                          {budget && <p className="text-[9px] text-muted-foreground capitalize">{budget.provider}</p>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {trend === "up" && <TrendingUp className="w-3.5 h-3.5 text-sylion-red" />}
                        {trend === "down" && <TrendingDown className="w-3.5 h-3.5 text-sylion-green" />}
                        {trend === "stable" && <Minus className="w-3.5 h-3.5 text-muted-foreground" />}
                        <span className={cn(
                          "text-[9px] font-medium",
                          trend === "up" ? "text-sylion-red" : trend === "down" ? "text-sylion-green" : "text-muted-foreground"
                        )}>
                          {trend === "up" ? "Rośnie" : trend === "down" ? "Maleje" : "Stabilny"}
                        </span>
                      </div>
                    </div>

                    {/* KPIs */}
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="rounded-lg bg-white/[0.02] p-2.5">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Łączny koszt</p>
                        <p className="text-[14px] font-bold text-foreground mt-0.5">{fmtUSD(model.totalCost)}</p>
                      </div>
                      <div className="rounded-lg bg-white/[0.02] p-2.5">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Żądania</p>
                        <p className="text-[14px] font-bold text-foreground mt-0.5">{model.requestCount}</p>
                      </div>
                      <div className="rounded-lg bg-white/[0.02] p-2.5">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Śr. koszt</p>
                        <p className="text-[14px] font-bold text-foreground mt-0.5">{fmtUSD(avgCost)}</p>
                      </div>
                    </div>

                    {/* Token breakdown */}
                    <div className="mb-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] text-muted-foreground">Zużycie tokenów</span>
                        <span className="text-[9px] text-muted-foreground">{fmtTokens(totalTokens)} łącznie</span>
                      </div>
                      <div className="h-2 rounded-full bg-white/5 overflow-hidden flex">
                        {totalTokens > 0 && (
                          <>
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${(model.promptTokens / totalTokens) * 100}%` }}
                              transition={{ duration: 0.6, ease: "easeOut", delay: i * 0.05 }}
                              className="h-full bg-sylion-blue"
                            />
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${(model.completionTokens / totalTokens) * 100}%` }}
                              transition={{ duration: 0.6, ease: "easeOut", delay: i * 0.05 }}
                              className="h-full bg-sylion-green"
                            />
                          </>
                        )}
                      </div>
                      <div className="flex items-center gap-4 mt-1">
                        <span className="flex items-center gap-1 text-[9px] text-muted-foreground">
                          <div className="w-2 h-2 rounded-sm bg-sylion-blue" /> Monit: {fmtTokens(model.promptTokens)}
                        </span>
                        <span className="flex items-center gap-1 text-[9px] text-muted-foreground">
                          <div className="w-2 h-2 rounded-sm bg-sylion-green" /> Odpowiedź: {fmtTokens(model.completionTokens)}
                        </span>
                      </div>
                    </div>

                    {/* Budget utilization */}
                    {budget && (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] text-muted-foreground">Wykorzystanie budżetu</span>
                          <span className={cn("text-[10px] font-semibold", pctColor(pct))}>{pct.toFixed(1)}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.6, ease: "easeOut", delay: i * 0.05 }}
                            className={cn("h-full rounded-full", barColor(pct))}
                          />
                        </div>
                        <div className="flex justify-between mt-0.5">
                          <span className="text-[8px] text-muted-foreground">{fmtUSD(budget.spent)} wydano</span>
                          <span className="text-[8px] text-muted-foreground">{fmtUSD(budget.budget_limit)} limit</span>
                        </div>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* ============================================================ */}
        {/*  Tab 4: Predictions                                          */}
        {/* ============================================================ */}
        <TabsContent value="predictions">
          <div className="grid grid-cols-3 gap-4 mb-5">
            {[
              {
                label: "Prognoza na koniec miesiąca",
                value: fmtUSD(predictedEOM),
                icon: CalendarDays,
                color: predictedEOM > totalBudget ? "text-sylion-red" : "text-sylion-green",
                detail: predictedEOM > totalBudget
                  ? `${fmtUSD(predictedEOM - totalBudget)} ponad budżet`
                  : `${fmtUSD(totalBudget - predictedEOM)} poniżej budżetu`,
              },
              {
                label: "Dni do wyczerpania",
                value: daysUntilExhaustion === Infinity ? "N/D" : `${daysUntilExhaustion}d`,
                icon: Timer,
                color: daysUntilExhaustion < 7 ? "text-sylion-red" : daysUntilExhaustion < 14 ? "text-sylion-amber" : "text-sylion-green",
                detail: daysUntilExhaustion === Infinity ? "Budżet nie jest zagrożony" : `przy obecnym dziennym tempie (${fmtUSD(dailyAvg)}/dzień)`,
              },
              {
                label: "Zalecany dzienny limit",
                value: fmtUSD(recommendedDaily),
                icon: Gauge,
                color: dailyAvg > recommendedDaily ? "text-sylion-amber" : "text-sylion-green",
                detail: `aby pozostać w budżecie ${fmtUSD(totalBudget)}`,
              },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
              >
                <Card size="sm" className="bg-[#0f1629]" style={{ border: "1px solid rgba(148,163,184,0.06)" }}>
                  <CardHeader className="pb-0">
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{s.label}</p>
                      <s.icon className={cn("w-4 h-4", s.color)} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className={cn("text-2xl font-bold", s.color)}>{s.value}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{s.detail}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          {/* Budget trajectory */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-xl border p-5 mb-5"
            style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
          >
            <div className="flex items-center justify-between mb-4">
              <p className="text-[12px] font-semibold text-foreground">Trajektoria budżetu</p>
              <span className="text-[9px] text-muted-foreground">Dzień {dayOfMonth} z {daysInMonth}</span>
            </div>
            {/* Simple bar-based trajectory visualization */}
            <div className="flex items-end gap-1 h-24">
              {Array.from({ length: daysInMonth }, (_, d) => {
                const projectedSpend = dailyAvg * (d + 1);
                const projectedPct = totalBudget > 0 ? Math.min((projectedSpend / totalBudget) * 100, 100) : 0;
                const isCurrentDay = d + 1 === dayOfMonth;
                const isPast = d + 1 <= dayOfMonth;
                const isOverBudget = projectedPct >= 100;
                return (
                  <div
                    key={d}
                    className="flex-1 rounded-t relative group"
                    style={{
                      height: `${Math.max(projectedPct, 2)}%`,
                      backgroundColor: isOverBudget
                        ? "rgba(239,68,68,0.5)"
                        : isPast
                          ? isCurrentDay
                            ? "rgba(59,130,246,0.7)"
                            : "rgba(34,197,94,0.3)"
                          : "rgba(148,163,184,0.1)",
                      border: isCurrentDay ? "1px solid rgba(59,130,246,0.8)" : "none",
                    }}
                  >
                    {isCurrentDay && (
                      <div className="absolute -top-5 left-1/2 -translate-x-1/2 text-[8px] text-sylion-blue whitespace-nowrap">Dziś</div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between mt-1.5 text-[8px] text-muted-foreground">
              <span>Dzień 1</span>
              <span>Dzień {daysInMonth}</span>
            </div>
            {/* Budget line indicator */}
            <div className="relative h-4 mt-1">
              {totalBudget > 0 && (
                <div
                  className="absolute border-t border-dashed border-sylion-red/40 w-full"
                  style={{ top: `${100 - 100}%` }}
                >
                  <span className="absolute right-0 -top-3 text-[8px] text-sylion-red/60">Limit budżetu</span>
                </div>
              )}
            </div>
          </motion.div>

          {/* Optimization suggestions */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="rounded-xl border p-5"
            style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Lightbulb className="w-4 h-4 text-sylion-amber" />
              <p className="text-[12px] font-semibold text-foreground">Sugestie optymalizacji kosztów</p>
            </div>
            <div className="space-y-3">
              {optimizationSuggestions.map((s, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className={cn(
                    "flex items-start gap-3 p-3 rounded-lg border",
                    s.severity === "critical" ? "bg-sylion-red/5 border-sylion-red/20" :
                    s.severity === "warning" ? "bg-sylion-amber/5 border-sylion-amber/20" :
                    "bg-sylion-green/5 border-sylion-green/20"
                  )}
                >
                  <div className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center shrink-0",
                    s.severity === "critical" ? "bg-sylion-red/10" :
                    s.severity === "warning" ? "bg-sylion-amber/10" :
                    "bg-sylion-green/10"
                  )}>
                    <s.icon className={cn(
                      "w-3.5 h-3.5",
                      s.severity === "critical" ? "text-sylion-red" :
                      s.severity === "warning" ? "text-sylion-amber" :
                      "text-sylion-green"
                    )} />
                  </div>
                  <div>
                    <Badge className={cn(
                      "text-[8px] px-1.5 py-0 border mb-1",
                      s.severity === "critical" ? "bg-sylion-red/10 text-sylion-red border-sylion-red/30" :
                      s.severity === "warning" ? "bg-sylion-amber/10 text-sylion-amber border-sylion-amber/30" :
                      "bg-sylion-green/10 text-sylion-green border-sylion-green/30"
                    )}>
                      {s.severity.toUpperCase()}
                    </Badge>
                    <p className="text-[11px] text-foreground leading-relaxed">{s.text}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </TabsContent>
      </Tabs>

      {/* ---- Budget Configuration (accessible from budget tab) ---- */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}
      >
        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Settings2 className="w-3.5 h-3.5" />
            Konfiguracja budżetu
          </span>
          <span className="text-[9px] text-muted-foreground">Kliknij edytuj, aby zmienić limity budżetu na model</span>
        </div>
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-muted-foreground text-[10px] uppercase tracking-wider border-b" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
              <th className="text-left px-4 py-2.5 cursor-pointer select-none" onClick={() => toggleSort("model_id")}>
                <span className="inline-flex items-center gap-1">Model {sortField === "model_id" ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-30" />}</span>
              </th>
              <th className="text-left px-4 py-2.5">Dostawca</th>
              <th className="text-right px-4 py-2.5">Aktualny limit</th>
              <th className="text-right px-4 py-2.5 cursor-pointer select-none" onClick={() => toggleSort("spent")}>
                <span className="inline-flex items-center gap-1">Wydano {sortField === "spent" ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-30" />}</span>
              </th>
              <th className="text-center px-4 py-2.5">Użycie</th>
              <th className="text-left px-4 py-2.5">Awaryjny</th>
              <th className="text-right px-4 py-2.5">Akcje</th>
            </tr>
          </thead>
          <tbody>
            {budgets.map((entry, i) => {
              if (editingModel === entry.model_id) {
                return (
                  <BudgetEditRow
                    key={entry.model_id}
                    entry={entry}
                    onSave={handleSaveBudget}
                    onCancel={() => setEditingModel(null)}
                  />
                );
              }
              const pct = budgetPct(entry.spent, entry.budget_limit);
              return (
                <motion.tr
                  key={entry.model_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  className="border-b last:border-0 hover:bg-white/[0.02] transition-colors"
                  style={{ borderColor: "rgba(148,163,184,0.04)" }}
                >
                  <td className="px-4 py-2.5 font-medium text-foreground">{entry.model_id}</td>
                  <td className="px-4 py-2.5 text-muted-foreground capitalize">{entry.provider}</td>
                  <td className={cn("px-4 py-2.5 text-right font-medium", pctColor(pct))}>{fmtUSD(entry.budget_limit)}</td>
                  <td className="px-4 py-2.5 text-right text-foreground">{fmtUSD(entry.spent)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 rounded-full bg-white/5">
                        <div className={cn("h-full rounded-full transition-all", barColor(pct))} style={{ width: `${Math.min(pct, 100)}%` }} />
                      </div>
                      <span className={cn("text-[10px] w-10 text-right", pctColor(pct))}>{pct.toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-[10px] text-muted-foreground">{entry.fallback_model_id || "none"}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button size="icon-xs" variant="ghost" onClick={() => setEditingModel(entry.model_id)}>
                        <Settings2 className="w-3 h-3" />
                      </Button>
                      <Button size="icon-xs" variant="ghost" onClick={() => handleResetBudget(entry.model_id)}>
                        <RotateCcw className="w-3 h-3" />
                      </Button>
                    </div>
                  </td>
                </motion.tr>
              );
            })}
            {budgets.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground text-xs">
                  Brak budżetów do skonfigurowania
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      </div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Empty State                                                        */
/* ------------------------------------------------------------------ */

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border p-8 flex flex-col items-center justify-center" style={{ background: "rgba(15,22,41,0.95)", borderColor: "rgba(148,163,184,0.06)" }}>
      <Zap className="w-8 h-8 text-muted-foreground/20 mb-3" />
      <p className="text-xs text-muted-foreground">{message}</p>
    </div>
  );
}
