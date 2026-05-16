"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { Wrench, RefreshCw, Loader2, ArrowRight, AlertTriangle } from "lucide-react";

const AGENT_COLORS: Record<string, string> = {
  codex: "text-cyan-400 border-cyan-400/30",
  kimi: "text-violet-400 border-violet-400/30",
  claude: "text-sylion-blue border-sylion-blue/30",
  z_ai: "text-sylion-green border-sylion-green/30",
};

export default function FixerProtocolPage() {
  const [protocol, setProtocol] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setProtocol(await orchestrationApi.getFixerProtocol());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!protocol) return;
    setSaving(true);
    try {
      const data = await orchestrationApi.updateFixerProtocol(protocol);
      setProtocol(data);
    } finally {
      setSaving(false);
    }
  };

  const updateRetry = (agent_type: string, retry_limit: number) => {
    setProtocol((prev: any) => ({
      ...prev,
      retry_budgets: prev.retry_budgets.map((b: any) =>
        b.agent_type === agent_type ? { ...b, retry_limit } : b
      ),
    }));
  };

  if (loading) return (
    <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
      <Loader2 className="w-5 h-5 animate-spin mx-auto text-sylion-blue" />
    </Card>
  );

  return (
    <div className="space-y-5">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-sylion-red/15 flex items-center justify-center">
              <Wrench className="w-4 h-4 text-sylion-red" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Protokół Fixera</h1>
              <p className="text-[11px] text-muted-foreground">Budżety retry, ścieżki eskalacji, progi NO-GO</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load}><RefreshCw className="w-3 h-3 mr-1" />Odśwież</Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
              onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : null}Zapisz
            </Button>
          </div>
        </div>
      </motion.div>

      {protocol && (
        <div className="grid grid-cols-2 gap-4">
          {/* Retry Budgets */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Budżety retry per agent
                <HelpTip text="Maksymalna liczba prób ponowienia gdy agent zwróci błąd (timeout, NO-GO, exception). 3 = bezpieczny default. Wyższe = lepsza odporność na przerywane API ale dłuższe oczekiwanie przy realnych awariach. 0 = brak retry (escalate od razu)." />
              </p>
              <div className="space-y-4">
                {protocol.retry_budgets.map((b: any) => (
                  <div key={b.agent_type}>
                    <div className="flex items-center justify-between mb-1">
                      <Badge variant="outline" className={cn("text-[9px]", AGENT_COLORS[b.agent_type] ?? "border-muted-foreground/30 text-muted-foreground")}>
                        {b.agent_type}
                      </Badge>
                      <span className="text-[11px] font-mono text-sylion-blue">{b.retry_limit} retries</span>
                    </div>
                    <input type="range" min={0} max={10} step={1} value={b.retry_limit}
                      onChange={e => updateRetry(b.agent_type, parseInt(e.target.value))}
                      className="w-full accent-sylion-blue"
                    />
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>

          {/* Escalation Path */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Ścieżka eskalacji
                <HelpTip text="Sekwencyjna lista do kogo (lub czego) trafia problem gdy retry agentów nie pomoże. Typowo: blocker → fixer-agent → architect → human-gate. Każdy krok dostaje kontekst poprzedniego. Im dalej w łańcuchu, tym poważniejszy lub kosztowniejszy fix." />
              </p>
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <div className="text-[9px] px-2 py-1 rounded bg-sylion-red/15 text-sylion-red border border-sylion-red/20">blocker</div>
                {protocol.escalation_path.map((step: string, i: number) => (
                  <div key={i} className="flex items-center gap-2">
                    <ArrowRight className="w-3 h-3 text-muted-foreground" />
                    <div className="text-[9px] px-2 py-1 rounded bg-accent-blue-dim text-sylion-blue border border-sylion-blue/20">{step}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-3 pt-3 border-t border-[rgba(148,163,184,0.08)]">
                <div>
                  <label className="text-[10px] text-muted-foreground">
                    Max iteracji NO-GO: {protocol.max_nogo_iterations}
                    <HelpTip text="Ile razy decyzja może wrócić ze statusem NO-GO (auditor odrzuca) zanim system zatrzyma cykl i wymusi human gate. 3 = pozwól na 3 podejścia + 4 = ręczna interwencja. Niższe = szybsza eskalacja do człowieka, wyższe = więcej autonomii dla agentów." />
                  </label>
                  <input type="range" min={1} max={10} step={1} value={protocol.max_nogo_iterations}
                    onChange={e => setProtocol((p: any) => ({ ...p, max_nogo_iterations: parseInt(e.target.value) }))}
                    className="w-full accent-sylion-amber mt-1"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-sylion-red" />
                    <span className="text-[11px]">
                      Auto-revert przy critical security
                      <HelpTip text="Gdy security sentinel wykryje krytyczne naruszenie (PII leak, exposed secret, RCE), system AUTOMATYCZNIE cofa zmiany bez czekania na człowieka. Włączone = bezpieczniej dla danych klientów, ale ryzyko false-positive odrzucenia legitnego commit. Domyślnie WŁĄCZONE." />
                    </span>
                  </div>
                  <button
                    onClick={() => setProtocol((p: any) => ({ ...p, auto_revert_on_critical_security: !p.auto_revert_on_critical_security }))}
                    className={cn("text-[9px] px-2 py-1 rounded transition-colors",
                      protocol.auto_revert_on_critical_security
                        ? "bg-sylion-red/15 text-sylion-red"
                        : "bg-muted/50 text-muted-foreground"
                    )}
                  >
                    {protocol.auto_revert_on_critical_security ? "WŁĄCZONY" : "WYŁĄCZONY"}
                  </button>
                </div>
              </div>
            </Card>
          </motion.div>

          {/* Escalation Simulation */}
          <motion.div className="col-span-2" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Symulacja eskalacji
                <HelpTip text="Wizualizacja: przy fikcyjnym blokerze pokazuje krok-po-kroku gdzie pójdzie problem przy aktualnych ustawieńiach (retry budgets + ścieżka eskalacji). Read-only — pomaga zweryfikować że konfiguracja ma sens przed zapisem." />
              </p>
              <div className="flex items-center gap-3 overflow-x-auto pb-1">
                <div className="shrink-0 px-3 py-2 rounded bg-sylion-red/15 border border-sylion-red/20 text-center">
                  <p className="text-[9px] text-sylion-red font-semibold">BLOKER</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Wykryto problem</p>
                </div>
                {protocol.retry_budgets.slice(0, 1).map((b: any) => (
                  <div key={b.agent_type} className="flex items-center gap-2">
                    <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
                    <div className="shrink-0 px-3 py-2 rounded bg-accent-blue-dim border border-sylion-blue/20 text-center">
                      <p className="text-[9px] text-sylion-blue font-semibold">{b.agent_type.toUpperCase()}</p>
                      <p className="text-[10px] text-muted-foreground">{b.retry_limit}× retry</p>
                    </div>
                  </div>
                ))}
                {protocol.escalation_path.map((step: string, i: number) => (
                  <div key={i} className="flex items-center gap-2">
                    <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
                    <div className="shrink-0 px-3 py-2 rounded bg-muted/30 border border-muted-foreground/20 text-center">
                      <p className="text-[9px] text-foreground font-semibold">{step}</p>
                      <p className="text-[10px] text-muted-foreground">Przejęcie kontroli</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
