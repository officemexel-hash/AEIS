"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { AlertTriangle, Clock, RefreshCw, Loader2, Zap, CheckCircle2 } from "lucide-react";

export default function AuditorCadencePage() {
  const [cadence, setCadence] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [lastTrigger, setLastTrigger] = useState<any>(null);
  const [stopFixRestart, setStopFixRestart] = useState<any>(null);
  const [runningGate, setRunningGate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextCadence, nextGate] = await Promise.all([
        orchestrationApi.getAuditorCadence(),
        orchestrationApi.getStopFixRestartStatus(),
      ]);
      setCadence(nextCadence);
      setStopFixRestart(nextGate);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!cadence) return;
    setSaving(true);
    try {
      const data = await orchestrationApi.updateAuditorCadence(cadence);
      setCadence(data);
    } finally {
      setSaving(false);
    }
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const result = await orchestrationApi.triggerAuditNow();
      setLastTrigger(result);
      await load();
    } finally {
      setTriggering(false);
    }
  };

  const handleRunStopFixRestart = async () => {
    setRunningGate(true);
    try {
      const result = await orchestrationApi.runStopFixRestart({ phase: "manual_dashboard_test", limit: 80 });
      setStopFixRestart({
        status: result.restart_required ? "stopped" : "ready",
        policy: "Stop-Fix-Restart",
        rule: "mock/stub/fake/placeholder/example_only in executable surfaces blocks acceptance",
        restart_scope: "current_phase_from_start",
        mock_stub_gate: result.mock_stub_gate,
        last_run: result,
      });
    } finally {
      setRunningGate(false);
    }
  };

  const toggleDimension = (dim: string) => {
    setCadence((prev: any) => {
      const dims = prev.enabled_dimensions.includes(dim)
        ? prev.enabled_dimensions.filter((d: string) => d !== dim)
        : [...prev.enabled_dimensions, dim];
      return { ...prev, enabled_dimensions: dims };
    });
  };

  if (loading) return (
    <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
      <Loader2 className="w-5 h-5 animate-spin mx-auto text-sylion-blue" />
    </Card>
  );

  const ALL_DIMS = [
    "code_quality", "test_coverage", "security_posture", "cost_efficiency",
    "performance_budget", "api_contract_compliance", "event_schema_validity",
    "preference_drift", "council_health", "escalation_backlog",
    "funding_deadlines", "subscription_roi", "d_level_distribution",
    "hallucination_rate", "evidence_pack_completeness", "agent_error_rate",
  ];

  const freqLabel = (s: number) =>
    s < 60 ? `${s}s` : s < 3600 ? `${Math.round(s/60)}m` : `${Math.round(s/3600)}h`;

  return (
    <div className="space-y-5">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent-blue-dim flex items-center justify-center">
              <Clock className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Rytm Audytora</h1>
              <p className="text-[11px] text-muted-foreground">Częstotliwość ticków, wymiary, harmonogram</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
              onClick={handleTrigger} disabled={triggering}>
              {triggering ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Zap className="w-3 h-3 mr-1" />}
              Audytuj teraz
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load}><RefreshCw className="w-3 h-3 mr-1" />Odśwież</Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
              onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : null}Zapisz
            </Button>
          </div>
        </div>
      </motion.div>

      {lastTrigger && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card className="p-3 border-sylion-green/20 bg-sylion-green/5 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-sylion-green" />
            <span className="text-[11px] text-sylion-green">Audyt uruchomiony: {lastTrigger.audit_id}</span>
            <span className="text-[10px] text-muted-foreground ml-2">{lastTrigger.triggered_at}</span>
          </Card>
        </motion.div>
      )}

      {stopFixRestart && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className={cn(
            "p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]",
            stopFixRestart.status === "stopped" && "border-red-500/25 bg-red-500/5",
          )}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-lg",
                  stopFixRestart.status === "stopped" ? "bg-red-500/10 text-red-400" : "bg-sylion-green/10 text-sylion-green",
                )}>
                  {stopFixRestart.status === "stopped" ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                </div>
                <div>
                  <h2 className="text-sm font-semibold">Stop-Fix-Restart Gate</h2>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Twarda zasada testów AEIS: wykryty syntetyczny fallback, nieaktywny endpoint albo dane przykladowe jako live zatrzymuja symulacje do naprawy i restartu etapu.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={cn(
                  "text-[10px]",
                  stopFixRestart.status === "stopped"
                    ? "border-red-500/30 text-red-400"
                    : "border-sylion-green/30 text-sylion-green",
                )}>
                  {stopFixRestart.status === "stopped" ? "STOP" : "READY"}
                </Badge>
                <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={handleRunStopFixRestart} disabled={runningGate}>
                  {runningGate ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Zap className="w-3 h-3 mr-1" />}
                  Uruchom gate
                </Button>
              </div>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-4">
              <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Findings</p>
                <p className="font-mono text-lg text-white">{stopFixRestart.mock_stub_gate?.findings_count ?? 0}</p>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Blockery</p>
                <p className="font-mono text-lg text-red-400">{stopFixRestart.mock_stub_gate?.blockers_count ?? 0}</p>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Restart scope</p>
                <p className="font-mono text-[10px] text-slate-300">{stopFixRestart.restart_scope}</p>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Polityka</p>
                <p className="font-mono text-[10px] text-slate-300">{stopFixRestart.policy}</p>
              </div>
            </div>
            <div className="mt-3 max-h-64 overflow-y-auto rounded border border-white/10 bg-black/20">
              {(stopFixRestart.mock_stub_gate?.findings ?? []).slice(0, 20).map((finding: any) => (
                <div key={finding.id} className="grid gap-2 border-b border-white/5 px-3 py-2 text-[10px] md:grid-cols-[80px_1fr_64px]">
                  <span className={finding.severity === "BLOCKER" ? "text-red-400" : "text-amber-400"}>{finding.severity}</span>
                  <span className="break-all font-mono text-slate-300">{finding.file}:{finding.line} {finding.snippet}</span>
                  <span className="text-slate-500">{finding.token}</span>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}

      {cadence && (
        <div className="grid grid-cols-2 gap-4">
          {/* Tick Frequency */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Częstotliwość ticków
                <HelpTip text="Co ile audytor sprawdźa zdrowie systemu (wszystkie wymiary niżej). 5 min = standard dla produkcji, 1 min = paranoid (drogie - więcej calli LLM), 30 min = relaxed dla MVP/dev. Częste ticki łapią problemy szybciej, ale obciążają LLM i koszty." />
              </p>
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px]">
                      Interwał: <span className="text-sylion-blue font-mono">{freqLabel(cadence.tick_frequency_seconds)}</span>
                      <HelpTip text="Odstęp czasu między kolejnymi audytami w sekundach. Zakres 30s-1h. Sugerowane: 300s (5min) dla prod, 60s (1min) dla incident response, 1800s (30min) dla MVP." />
                    </span>
                  </div>
                  <input type="range" min={30} max={3600} step={30} value={cadence.tick_frequency_seconds}
                    onChange={e => setCadence((c: any) => ({ ...c, tick_frequency_seconds: parseInt(e.target.value) }))}
                    className="w-full accent-sylion-blue"
                  />
                  <div className="flex justify-between text-[9px] text-muted-foreground">
                    <span>30s</span><span>15m</span><span>30m</span><span>1h</span>
                  </div>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground">
                    Harmonogram audytów fazowych (cron)
                    <HelpTip text="Cron expression dla pełnych audytów fazowych (oprócz cyklu ticków). Format: 'min godz dzień miesiąc dzień_tyg'. Przykłady: '0 0 * * *' = codziennie o północy, '0 */6 * * *' = co 6h. Domyślnie pełny audyt raz dziennie wystarcza." />
                  </label>
                  <input
                    type="text"
                    className="mt-1 w-full px-2 py-1 rounded bg-background border border-border text-[11px] font-mono focus:outline-none focus:border-sylion-blue"
                    value={cadence.phase_boundary_cron}
                    onChange={e => setCadence((c: any) => ({ ...c, phase_boundary_cron: e.target.value }))}
                  />
                </div>
                {cadence.last_audit_at && (
                  <p className="text-[10px] text-muted-foreground">Ostatni audyt: <span className="font-mono">{cadence.last_audit_at}</span></p>
                )}
              </div>
            </Card>
          </motion.div>

          {/* Last 10 Audits */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Ostatnie audyty
                <HelpTip text="Lista 10 ostatnich uruchomień audytora (zarówno automatycznych z ticków jak i manualnych z 'Audytuj teraz'). Status 'triggered' = uruchomiony, 'completed' = zakończony. Read-only — używaj do weryfikacji że scheduler działa." />
              </p>
              {cadence.last_10_audits.length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4">Brak historii audytów</p>
              ) : (
                <div className="space-y-1.5">
                  {cadence.last_10_audits.map((a: any, i: number) => (
                    <div key={a.audit_id || i} className="flex items-center gap-2 py-1 border-b border-[rgba(148,163,184,0.06)] last:border-0">
                      <Badge variant="outline" className={cn("text-[8px] shrink-0",
                        a.status === "triggered" ? "border-sylion-blue/30 text-sylion-blue" : "border-sylion-green/30 text-sylion-green"
                      )}>
                        {a.status}
                      </Badge>
                      <span className="text-[10px] font-mono text-muted-foreground truncate">{a.triggered_at}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </motion.div>

          {/* Dimensions */}
          <motion.div className="col-span-2" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Wymiary audytu ({cadence.enabled_dimensions.length}/{ALL_DIMS.length})
                  <HelpTip text="Które aspekty systemu audytor monitoruje. Więcej włączonych = lepsze pokrycie, ale większy koszt LLM per tick. MVP minimum: code_quality + security_posture + cost_efficiency. Pełna lista pokrywa też hallucination_rate, evidence pack, council health itp." />
                </p>
                <div className="flex gap-1">
                  <button className="text-[9px] text-sylion-blue hover:underline"
                    onClick={() => setCadence((c: any) => ({ ...c, enabled_dimensions: ALL_DIMS }))}>
                    Wszystkie
                  </button>
                  <span className="text-muted-foreground">|</span>
                  <button className="text-[9px] text-muted-foreground hover:underline"
                    onClick={() => setCadence((c: any) => ({ ...c, enabled_dimensions: [] }))}>
                    Żaden
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                {ALL_DIMS.map(dim => {
                  const enabled = cadence.enabled_dimensions.includes(dim);
                  return (
                    <button
                      key={dim}
                      onClick={() => toggleDimension(dim)}
                      className={cn(
                        "text-[9px] px-2 py-1.5 rounded border text-left transition-colors",
                        enabled
                          ? "border-sylion-blue/30 text-sylion-blue bg-accent-blue-dim"
                          : "border-[rgba(148,163,184,0.08)] text-muted-foreground hover:border-muted-foreground/30"
                      )}
                    >
                      {dim.replace(/_/g, " ")}
                    </button>
                  );
                })}
              </div>
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
