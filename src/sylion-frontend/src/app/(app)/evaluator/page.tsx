"use client";

import { useState, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useHealth, useApi } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  ClipboardCheck,
  RefreshCw,
  WifiOff,
  CheckCircle2,
  XCircle,
  Clock,
  BarChart3,
  ListChecks,
  FileText,
  Award,
  Target,
  TrendingUp,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Criterion {
  criterion_id: string;
  name: string;
  weight: number;
  description: string;
  category?: string;
}

interface Evaluation {
  evaluation_id: string;
  target: string;
  type: string;
  status: string;
  score: number;
  created_at: number;
  completed_at?: number;
  criteria_results?: { criterion_id: string; score: number; passed: boolean }[];
}

interface EvalData {
  criteria: Criterion[];
  evaluations: Evaluation[];
}

/* ============================================================
   Helpers
   ============================================================ */

function fmtDate(ts: number): string {
  const d = new Date(ts);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return d.toLocaleDateString();
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-sylion-green";
  if (score >= 50) return "text-sylion-amber";
  return "text-sylion-red";
}

function scoreBadge(score: number): string {
  if (score >= 80) return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
  if (score >= 50) return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
  return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
}

function statusBadge(status: string): string {
  switch (status) {
    case "completed":
    case "passed":
      return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
    case "failed":
      return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
    case "in_progress":
    case "running":
      return "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5";
    case "pending":
    case "queued":
      return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
    default:
      return "border-border/50 text-muted-foreground";
  }
}

/* ============================================================
   Page Component
   ============================================================ */

export default function EvaluatorPage() {
  const { data: healthRaw, loading: healthLoading, refresh: refreshHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: evalRaw, loading: evalLoading, refresh: refreshEval } = useApi<EvalData>(
    () => Promise.all([api.listEvaluations()]).then(([evalRes]) => {
      const evaluations = evalRes.evaluations || [];
      return { criteria: [], evaluations } as EvalData;
    }),
    { criteria: [], evaluations: [] }
  );

  const loading = healthLoading || evalLoading;

  const [activeTab, setActiveTab] = useState("criteria");

  const evaluations = (evalRaw as EvalData).evaluations || [];
  const criteria = (evalRaw as EvalData).criteria || [];

  /* ---------- Derived stats ---------- */
  const completedEvals = useMemo(
    () => evaluations.filter((e) => e.status === "completed" || e.status === "passed"),
    [evaluations]
  );

  const avgScore = useMemo(() => {
    const scored = evaluations.filter((e) => e.score > 0);
    if (scored.length === 0) return 0;
    return Math.round(scored.reduce((sum, e) => sum + e.score, 0) / scored.length);
  }, [evaluations]);

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
            <ClipboardCheck className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Ramy ewaluacji</h1>
            <p className="text-sm text-muted-foreground">Criteria and assessment tracking</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend Not Reachable</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            The SYLION backend is not responding. Evaluation data requires a running backend.
          </p>
          <Button variant="outline" size="sm" onClick={() => { refreshHealth(); refreshEval(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Retry Connection
          </Button>
        </Card>
      </div>
    );
  }

  const refresh = () => { refreshEval(); refreshHealth(); };

  /* ---------- Stats cards ---------- */
  const stats = [
    {
      label: "Total Criteria",
      value: criteria.length,
      icon: ListChecks,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Total Evaluations",
      value: evaluations.length,
      icon: FileText,
      color: "text-purple-400",
      bgColor: "bg-purple-400/10",
    },
    {
      label: "Completed",
      value: completedEvals.length,
      icon: CheckCircle2,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Avg Score",
      value: avgScore > 0 ? `${avgScore}%` : "--",
      icon: TrendingUp,
      color: avgScore >= 80 ? "text-sylion-green" : avgScore >= 50 ? "text-sylion-amber" : "text-sylion-red",
      bgColor: avgScore >= 80 ? "bg-sylion-green/10" : avgScore >= 50 ? "bg-sylion-amber/10" : "bg-sylion-red/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-purple-400/10 border border-purple-400/20 flex items-center justify-center">
            <ClipboardCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Ramy ewaluacji</h1>
            <p className="text-sm text-muted-foreground">Criteria and assessment tracking</p>
          </div>
        </div>

        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

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
          <TabsTrigger value="criteria" className="text-xs">
            <ListChecks className="w-3.5 h-3.5 mr-1.5" />
            Criteria
          </TabsTrigger>
          <TabsTrigger value="evaluations" className="text-xs">
            <FileText className="w-3.5 h-3.5 mr-1.5" />
            Evaluations
          </TabsTrigger>
        </TabsList>

        {/* ===== TAB 1: CRITERIA ===== */}
        <TabsContent value="criteria" className="mt-4">
          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-3 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-xs font-medium text-muted-foreground">Evaluation Criteria</h3>
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                {criteria.length} defined
              </span>
            </div>
            {criteria.length === 0 ? (
              <div className="p-8 text-center">
                <ListChecks className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">No criteria defined yet. Criteria are loaded from the backend.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/20">
                {criteria.map((c) => (
                  <div key={c.criterion_id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
                    <div className="w-7 h-7 rounded-md bg-sylion-blue/10 flex items-center justify-center shrink-0">
                      <Target className="w-3.5 h-3.5 text-sylion-blue" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{c.name}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{c.description}</p>
                    </div>
                    {c.category && (
                      <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground shrink-0">
                        {c.category}
                      </Badge>
                    )}
                    <div className="text-right shrink-0">
                      <p className="text-xs font-mono font-medium">{(c.weight * 100).toFixed(0)}%</p>
                      <p className="text-[9px] text-muted-foreground">weight</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ===== TAB 2: EVALUATIONS ===== */}
        <TabsContent value="evaluations" className="mt-4">
          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-3 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-xs font-medium text-muted-foreground">Evaluations</h3>
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
                {evaluations.length} total
              </span>
            </div>
            {evaluations.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">No evaluations recorded yet. Evaluations are loaded from the backend.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/20">
                {evaluations.map((ev) => (
                  <div key={ev.evaluation_id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
                    <div className={cn(
                      "w-7 h-7 rounded-md flex items-center justify-center shrink-0",
                      ev.score >= 80 ? "bg-sylion-green/10" : ev.score >= 50 ? "bg-sylion-amber/10" : "bg-sylion-red/10"
                    )}>
                      <Award className={cn("w-3.5 h-3.5", scoreColor(ev.score))} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{ev.target}</p>
                      <p className="text-[10px] text-muted-foreground">{ev.type}</p>
                    </div>
                    <Badge variant="outline" className={cn("text-[9px] shrink-0", statusBadge(ev.status))}>
                      {ev.status.toUpperCase()}
                    </Badge>
                    {ev.score > 0 ? (
                      <Badge variant="outline" className={cn("text-[9px] shrink-0 font-mono", scoreBadge(ev.score))}>
                        {ev.score}%
                      </Badge>
                    ) : (
                      <span className="text-[10px] text-muted-foreground font-mono w-10 text-right shrink-0">--</span>
                    )}
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0 w-24 text-right">
                      <Clock className="w-2.5 h-2.5" />
                      {fmtDate(ev.created_at)}
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
