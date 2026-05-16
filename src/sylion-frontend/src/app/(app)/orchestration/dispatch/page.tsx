"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { Cpu, RefreshCw, Loader2, DollarSign } from "lucide-react";

const STAGE_LABELS: Record<string, string> = {
  architectural: "Architektura",
  production: "Produkcja",
  testing: "Testowanie",
  docs: "Dokumentacja",
};

const AGENT_COLORS: Record<string, string> = {
  claude: "bg-sylion-blue",
  codex: "bg-cyan-400",
  kimi: "bg-violet-400",
};

export default function DispatchConfigPage() {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setConfig(await orchestrationApi.getDispatchConfig());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const data = await orchestrationApi.updateDispatchConfig(config);
      setConfig(data);
    } finally {
      setSaving(false);
    }
  };

  const updateRatio = (stage_type: string, agent: "claude_ratio" | "codex_ratio" | "kimi_ratio", val: number) => {
    setConfig((prev: any) => ({
      ...prev,
      stage_allocation_rules: prev.stage_allocation_rules.map((r: any) =>
        r.stage_type === stage_type ? { ...r, [agent]: val } : r
      ),
    }));
  };

  const setParallelismMode = (mode: "wide" | "capped") => {
    setConfig((prev: any) => ({
      ...prev,
      parallelism_mode: mode,
      max_simultaneous: mode === "capped" ? (prev.max_simultaneous ?? 8) : prev.max_simultaneous,
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
            <div className="w-8 h-8 rounded-lg bg-accent-blue-dim flex items-center justify-center">
              <Cpu className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Dispatch Agentów</h1>
              <p className="text-[11px] text-muted-foreground">Równoległość, alokacja, pułapy kosztów</p>
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

      {config && (
        <div className="space-y-4">
          {/* Mode + Parallelism */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                    Tryb równoległości
                    <HelpTip text="Szerokie = system uruchamia tyle agentów ile zadań w kolejce (najszybsze, ale niekontrolowany koszt). Ograniczone = sztywny limit max równoległych jobs (przewidywalny koszt, dłuższe oczekiwanie). Dla MVP: ograniczone z capem 5-10. Dla burst processing: szerokie." />
                  </p>
                  <div className="flex gap-2">
                    {["wide", "capped"].map(mode => (
                      <button key={mode}
                        onClick={() => setParallelismMode(mode as "wide" | "capped")}
                        className={cn("text-[10px] px-3 py-1.5 rounded border transition-colors",
                          config.parallelism_mode === mode
                            ? "border-sylion-blue/40 text-sylion-blue bg-accent-blue-dim"
                            : "border-[rgba(148,163,184,0.08)] text-muted-foreground hover:border-muted-foreground/30"
                        )}
                      >
                        {mode === "wide" ? "Szerokie (∞)" : "Ograniczone"}
                      </button>
                    ))}
                  </div>
                </div>
                {config.parallelism_mode === "capped" && (
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                      Max równoległych: {config.max_simultaneous ?? 8}
                      <HelpTip text="Twardy limit liczby agentów pracujących w tym samym czasie (3-20). Niski (3-5) = szeregowanie zadań, mała chmura kosztów. Wysoki (15-20) = burst speed, ale może wyczerpać limit API providera. Sweet spot: 8-10 dla średniego pipeline." />
                    </p>
                    <input type="range" min={3} max={20} step={1} value={config.max_simultaneous ?? 8}
                      onChange={e => setConfig((c: any) => ({ ...c, max_simultaneous: parseInt(e.target.value) }))}
                      className="w-full accent-sylion-blue"
                    />
                  </div>
                )}
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                    Pułap kosztów (USD/h)
                    <HelpTip text="Maksymalny wydatek na LLM API w ciągu godziny. Po przekroczeniu cost-sentinel zatrzymuje dispatch nowych zadań. Pusty = brak limitu (NIE zalecane). Typowo: 5-10$/h dla dev, 20-50$/h dla prod. Twarda barierka kosztowa." />
                  </p>
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-3 h-3 text-sylion-amber" />
                    <input
                      type="number"
                      min={0} step={0.5}
                      placeholder="Brak limitu"
                      className="flex-1 px-2 py-1 rounded bg-background border border-border text-[11px] focus:outline-none focus:border-sylion-blue"
                      value={config.cost_ceiling_usd_per_hour ?? ""}
                      onChange={e => setConfig((c: any) => ({
                        ...c,
                        cost_ceiling_usd_per_hour: e.target.value ? parseFloat(e.target.value) : null,
                      }))}
                    />
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>

          {/* Stage Allocation */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Alokacja agentów per etap
                <HelpTip text="Jak rozkłada się obciążenie między agentów (Claude/Codex/Kimi) na każdym etapie pipeline. Suma proporcji per etap = 1.0. Przykład: Architektura → Claude 0.7 + Codex 0.3 (Claude lepiej rozumie design). Etap Produkcja → Codex 0.6 + Claude 0.4 (Codex szybszy w bulk codingu)." />
              </p>
              <div className="space-y-4">
                {config.stage_allocation_rules.map((rule: any) => {
                  const total = rule.claude_ratio + rule.codex_ratio + rule.kimi_ratio;
                  const pcts = {
                    claude: total > 0 ? (rule.claude_ratio / total) * 100 : 0,
                    codex: total > 0 ? (rule.codex_ratio / total) * 100 : 0,
                    kimi: total > 0 ? (rule.kimi_ratio / total) * 100 : 0,
                  };
                  return (
                    <div key={rule.stage_type}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-medium">{STAGE_LABELS[rule.stage_type] ?? rule.stage_type}</span>
                        <div className="flex items-center gap-2 text-[9px]">
                          {Object.entries(pcts).map(([agent, pct]) => (
                            <span key={agent} className="flex items-center gap-1">
                              <span className={cn("w-2 h-2 rounded-full", AGENT_COLORS[agent])} />
                              {agent}: {pct.toFixed(0)}%
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="h-4 rounded-full overflow-hidden flex">
                        <div className="bg-sylion-blue transition-all" style={{ width: `${pcts.claude}%` }} />
                        <div className="bg-cyan-400 transition-all" style={{ width: `${pcts.codex}%` }} />
                        <div className="bg-violet-400 transition-all" style={{ width: `${pcts.kimi}%` }} />
                      </div>
                      <div className="grid grid-cols-3 gap-2 mt-1.5">
                        {[
                          { key: "claude_ratio" as const, label: "Claude", color: "accent-sylion-blue" },
                          { key: "codex_ratio" as const, label: "Codex", color: "accent-cyan-400" },
                          { key: "kimi_ratio" as const, label: "Kimi", color: "accent-violet-400" },
                        ].map(({ key, label }) => (
                          <div key={key}>
                            <label className="text-[9px] text-muted-foreground">
                              {label}: {rule[key].toFixed(1)}
                              <HelpTip text={`Proporcja zadań tego etapu trafiająca do agenta ${label} (0.0-1.0). Suma wszystkich agentów per etap powinna wynosić 1.0 — system normalizuje automatycznie. 0.0 = ten agent NIE pracuje na tym etapie.`} />
                            </label>
                            <input type="range" min={0} max={1} step={0.1} value={rule[key]}
                              onChange={e => updateRatio(rule.stage_type, key, parseFloat(e.target.value))}
                              className="w-full"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </motion.div>

          {/* Sub-agent permissions */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Uprawnienia sub-agentów
                <HelpTip text="Czy główny agent może spawnować sub-agentów tego typu (np. Claude może uruchomić Kimi do rozwiązania osobnego pod-zadania). Zablokowane = ten typ NIE może być sub-agentem nikogo. Używaj do izolacji — np. zablokuj 'kimi' jeśli nie ufasz lokalnemu modelowi w sub-roli." />
              </p>
              <div className="flex items-center gap-3 flex-wrap">
                {Object.entries(config.sub_agent_permission_by_type).map(([agent, allowed]) => (
                  <button
                    key={agent}
                    onClick={() => setConfig((c: any) => ({
                      ...c,
                      sub_agent_permission_by_type: { ...c.sub_agent_permission_by_type, [agent]: !allowed },
                    }))}
                    className={cn(
                      "flex items-center gap-1.5 text-[10px] px-3 py-1.5 rounded border transition-colors",
                      allowed
                        ? "border-sylion-green/30 text-sylion-green bg-sylion-green/10"
                        : "border-[rgba(148,163,184,0.08)] text-muted-foreground"
                    )}
                  >
                    <span className={cn("w-1.5 h-1.5 rounded-full", allowed ? "bg-sylion-green" : "bg-muted-foreground")} />
                    {agent}: {allowed ? "dozwolony" : "zablokowany"}
                  </button>
                ))}
              </div>
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
