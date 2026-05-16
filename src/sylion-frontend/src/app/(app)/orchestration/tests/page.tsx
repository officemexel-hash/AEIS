"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { TestTube, RefreshCw, Loader2, Play, CheckCircle2, XCircle, Clock, SkipForward, Filter } from "lucide-react";

const STATUS_CONFIG: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
  pass:       { color: "text-sylion-green border-sylion-green/30", icon: CheckCircle2, label: "Zdany" },
  fail:       { color: "text-sylion-red border-sylion-red/30",     icon: XCircle,      label: "Błąd" },
  skip:       { color: "text-sylion-amber border-sylion-amber/30", icon: SkipForward,  label: "Pominięty" },
  never_run:  { color: "text-muted-foreground border-muted-foreground/20", icon: Clock, label: "Nie uruchomiony" },
  running:    { color: "text-sylion-blue border-sylion-blue/30",   icon: Loader2,      label: "Trwa" },
};

const TYPE_COLORS: Record<string, string> = {
  golden: "border-sylion-amber/30 text-sylion-amber",
  integration: "border-sylion-blue/30 text-sylion-blue",
  e2e: "border-violet-400/30 text-violet-400",
  sim: "border-cyan-400/30 text-cyan-400",
};

export default function TestCatalogPage() {
  const [tests, setTests] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [moduleFilter, setModuleFilter] = useState<string>("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [tData, rData] = await Promise.all([
        orchestrationApi.getTestCatalog(),
        orchestrationApi.getTestCatalogRuns(10),
      ]);
      setTests(tData.tests ?? []);
      setRuns(rData.runs ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRunTest = async (test_id?: string, suite?: string) => {
    const key = test_id ?? suite ?? "all";
    setTriggering(key);
    try {
      await orchestrationApi.triggerTestRun({ test_id, suite });
      await load();
    } finally {
      setTriggering(null);
    }
  };

  const modules = Array.from(new Set(tests.map((t) => t.module)));
  const types = Array.from(new Set(tests.map((t) => t.test_type)));
  const statuses = ["all", "pass", "fail", "skip", "never_run"];

  const filtered = tests.filter(t =>
    (statusFilter === "all" || t.status === statusFilter) &&
    (typeFilter === "all" || t.test_type === typeFilter) &&
    (moduleFilter === "all" || t.module === moduleFilter)
  );

  const countByStatus = (s: string) => tests.filter(t => t.status === s).length;

  return (
    <div className="space-y-5">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent-blue-dim flex items-center justify-center">
              <TestTube className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Katalog Testów</h1>
              <p className="text-[11px] text-muted-foreground">Przeglądarka testów i uruchamianie on-demand</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load}><RefreshCw className="w-3 h-3 mr-1" />Odśwież</Button>
            <Button variant="outline" size="sm"
              className="h-7 text-[10px] border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
              onClick={() => handleRunTest(undefined, "golden")} disabled={!!triggering}>
              {triggering === "golden" ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
              Uruchom golden
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.04 }}>
        <div className="grid grid-cols-4 gap-3">
          {["pass", "fail", "skip", "never_run"].map(s => {
            const cfg = STATUS_CONFIG[s];
            const Icon = cfg.icon;
            return (
              <Card key={s} className="p-3 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
                <div className="flex items-center gap-2">
                  <Icon className={cn("w-4 h-4", cfg.color.split(" ")[0])} />
                  <div>
                    <p className="text-lg font-bold">{countByStatus(s)}</p>
                    <p className="text-[9px] text-muted-foreground">{cfg.label}</p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }}>
        <Card className="p-3 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-1.5">
              <Filter className="w-3 h-3 text-muted-foreground" />
              <span className="text-[10px] text-muted-foreground">
                Status:
                <HelpTip text="Filtruj testy po wyniku ostatniego uruchomienia. 'fail' = priorytet do napraw, 'never_run' = trzeba uruchomić aby uzyskać sygnał, 'skip' = pominięte (np. brak dependency). Pomaga skupić uwagę na czerwonym." />
              </span>
              {statuses.map(s => (
                <button key={s} onClick={() => setStatusFilter(s)}
                  className={cn("text-[9px] px-1.5 py-0.5 rounded transition-colors",
                    statusFilter === s ? "bg-accent-blue-dim text-sylion-blue" : "text-muted-foreground hover:text-foreground"
                  )}>
                  {s === "all" ? "Wszystkie" : STATUS_CONFIG[s]?.label ?? s}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">
                Typ:
                <HelpTip text="Filtruj po kategorii testu. golden = stałe scenariusze referencyjne (regresja). integration = testy między modułami. e2e = pełny scenariusz user journey. sim = symulacje obciążenia/awarii. Każdy typ ma inny czas wykonania i koszt." />
              </span>
              {["all", ...types].map(t => (
                <button key={t} onClick={() => setTypeFilter(t)}
                  className={cn("text-[9px] px-1.5 py-0.5 rounded transition-colors",
                    typeFilter === t ? "bg-accent-blue-dim text-sylion-blue" : "text-muted-foreground hover:text-foreground"
                  )}>
                  {t === "all" ? "Wszystkie" : t}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">
                Moduł:
                <HelpTip text="Filtruj testy po module którego dotyczą (np. council, advisor, fixer). Przydatne podczas debugowania konkretnego subsystemu — pokazuje TYLKO testy dotykające danego kodu." />
              </span>
              <select className="text-[9px] px-1.5 py-0.5 rounded bg-background border border-border focus:outline-none"
                value={moduleFilter} onChange={e => setModuleFilter(e.target.value)}>
                <option value="all">Wszystkie</option>
                {modules.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Test list */}
      {loading ? (
        <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
          <Loader2 className="w-5 h-5 animate-spin mx-auto text-sylion-blue" />
        </Card>
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
          <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] overflow-hidden">
            <div className="divide-y divide-[rgba(148,163,184,0.06)]">
              {filtered.map(test => {
                const cfg = STATUS_CONFIG[test.status] ?? STATUS_CONFIG.never_run;
                const Icon = cfg.icon;
                return (
                  <div key={test.test_id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-muted/10">
                    <Icon className={cn("w-3.5 h-3.5 shrink-0", cfg.color.split(" ")[0], test.status === "running" && "animate-spin")} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-mono">{test.name}</span>
                        <Badge variant="outline" className={cn("text-[8px]", TYPE_COLORS[test.test_type] ?? "")}>{test.test_type}</Badge>
                        <Badge variant="outline" className="text-[8px] text-muted-foreground border-muted-foreground/20">{test.module}</Badge>
                      </div>
                      {test.last_run_at && (
                        <p className="text-[9px] text-muted-foreground mt-0.5">Ostatni: {test.last_run_at}</p>
                      )}
                    </div>
                    <Button variant="ghost" size="sm" className="h-6 text-[9px] text-sylion-blue hover:bg-sylion-blue/10 shrink-0"
                      onClick={() => handleRunTest(test.test_id)} disabled={triggering === test.test_id}>
                      {triggering === test.test_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
                      Uruchom
                    </Button>
                  </div>
                );
              })}
              {filtered.length === 0 && (
                <div className="p-6 text-center text-muted-foreground text-sm">Brak testów pasujących do filtrów</div>
              )}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Recent runs */}
      {runs.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Ostatnie uruchomienia
              <HelpTip text="Historia 10 ostatnich runów testów (zarówno suite jak pojedyncze test_id). Pokazuje czy CI/manual triggers działały i jak długo trwały. Read-only — używaj do triage: częste 'fail' w danym module = sygnał do uważnego review tego subsystemu." />
            </p>
            <div className="space-y-1.5">
              {runs.map(run => (
                <div key={run.run_id} className="flex items-center gap-2 text-[10px]">
                  <Badge variant="outline" className={cn("text-[8px] shrink-0",
                    run.status === "pass" ? "border-sylion-green/30 text-sylion-green" :
                    run.status === "fail" ? "border-sylion-red/30 text-sylion-red" :
                    run.status === "running" ? "border-sylion-blue/30 text-sylion-blue" :
                    "border-muted-foreground/20 text-muted-foreground"
                  )}>
                    {run.status}
                  </Badge>
                  <span className="font-mono text-muted-foreground truncate">{run.suite ?? run.test_id ?? "manual"}</span>
                  <span className="text-muted-foreground shrink-0">{run.triggered_at}</span>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
