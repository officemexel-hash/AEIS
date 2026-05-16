"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { Users, RefreshCw, Loader2, Plus, Play } from "lucide-react";

const LIFETIME_COLORS: Record<string, string> = {
  ephemeral: "border-sylion-blue/30 text-sylion-blue",
  persistent: "border-sylion-green/30 text-sylion-green",
};

const AGENT_TYPES = ["claude", "codex", "kimi", "z_ai"];

function sampleEventLabelFromPattern(pattern?: string) {
  if (!pattern?.trim()) return "[advisor][claude][engine] dashboard runtime check";
  const literalPrefix = pattern
    .trim()
    .replace(/^\^/, "")
    .replace(/\$$/, "")
    .replace(/\\\[/g, "[")
    .replace(/\\\]/g, "]")
    .replace(/\\\(/g, "(")
    .replace(/\\\)/g, ")")
    .replace(/\\-/g, "-")
    .replace(/\.\*$/, "")
    .replace(/\.\+$/, "");
  if (!literalPrefix || /[\\^$|?*+(){}]/.test(literalPrefix)) {
    return "[advisor][claude][engine] dashboard runtime check";
  }
  return `${literalPrefix} dashboard runtime check`;
}

export default function TeamFormationPage() {
  const [data, setData] = useState<{ rules: any[]; active_teams: any[] }>({ rules: [], active_teams: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newRule, setNewRule] = useState({
    trigger_pattern: "",
    agent_types: ["claude", "z_ai"],
    lifetime: "ephemeral",
    action: "spawn_audit_team",
    enabled: true,
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await orchestrationApi.getTeamFormationRules());
    } finally {
      setLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  const handleToggleRule = async (ruleId: string, enabled: boolean) => {
    const updated = data.rules.map(r => r.rule_id === ruleId ? { ...r, enabled } : r);
    setSaving(true);
    try {
      const res = await orchestrationApi.updateTeamFormationRules(updated);
      setData(prev => ({ ...prev, rules: res.rules }));
    } finally {
      setSaving(false);
    }
  };

  const handleAddRule = async () => {
    if (!newRule.trigger_pattern.trim()) return;
    setSaving(true);
    try {
      const rule = await orchestrationApi.addTeamFormationRule(newRule);
      setData(prev => ({ ...prev, rules: [...prev.rules, rule] }));
      setShowAdd(false);
      setNewRule({ trigger_pattern: "", agent_types: ["claude", "z_ai"], lifetime: "ephemeral", action: "spawn_audit_team", enabled: true });
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerRuntimeCheck = async () => {
    setTriggering(true);
    setTriggerResult(null);
    try {
      const enabledRule = data.rules.find((rule: any) => rule.enabled);
      const result = await orchestrationApi.triggerTeamFormation({
        event_label: sampleEventLabelFromPattern(enabledRule?.trigger_pattern),
        task: "Operator dashboard runtime check: utwórz zespół z aktywnej reguły i pokaż go w panelu.",
      });
      setTriggerResult(`Utworzono zespoły: ${result.created_teams?.length ?? 0}`);
      await load();
    } catch (err) {
      setTriggerResult(err instanceof Error ? err.message : "Błąd testu runtime");
    } finally {
      setTriggering(false);
    }
  };

  const toggleAgentType = (agent: string) => {
    setNewRule(prev => ({
      ...prev,
      agent_types: prev.agent_types.includes(agent)
        ? prev.agent_types.filter(a => a !== agent)
        : [...prev.agent_types, agent],
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
              <Users className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Formowanie Zespołów</h1>
              <p className="text-[11px] text-muted-foreground">Reguły automatycznego tworzenia zespołów agentów</p>
            </div>
          </div>
          <div className="flex gap-2">
            {triggerResult ? <span className="self-center text-[10px] text-sylion-green">{triggerResult}</span> : null}
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
              onClick={handleTriggerRuntimeCheck} disabled={triggering}>
              {triggering ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
              Testuj reguły
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load}><RefreshCw className="w-3 h-3 mr-1" />Odśwież</Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10"
              onClick={() => setShowAdd(v => !v)}>
              <Plus className="w-3 h-3 mr-1" />Nowa reguła
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Add rule form */}
      <AnimatePresence>
        {showAdd && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
            <Card className="p-4 border-sylion-blue/20 bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-sylion-blue uppercase tracking-wider mb-3">
                Nowa reguła
                <HelpTip text="Definicja: jakie zdarzenia (np. commit pasujący do regex) automatycznie tworzą zespół agentów. Po zapisie reguła działa od razu — przy każdym pasującym commicie powstanie nowy team. Pomyśl o tym jak o trigger → spawn agents." />
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] text-muted-foreground">
                    Wzorzec commit (regex)
                    <HelpTip text="Regex matchowany na message commita lub branch nazwie. Przykład: '^\\[advisor\\]\\[claude\\]' = każdy commit zaczynający się od [advisor][claude] tworzy team. Używaj '^' i '$' aby ograniczyć dopasowania. Zły regex = reguła nigdy nie wystrzeli." />
                  </label>
                  <input type="text" placeholder="^\[advisor\]\[claude\]"
                    className="mt-1 w-full px-2 py-1 rounded bg-background border border-border text-[11px] font-mono focus:outline-none focus:border-sylion-blue"
                    value={newRule.trigger_pattern}
                    onChange={e => setNewRule(r => ({ ...r, trigger_pattern: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground">
                    Typy agentów
                    <HelpTip text="Którzy agenci wejdą do zespołu (multi-select). Claude = reasoning/architektura, Codex = bulk coding, Kimi = lokalny tani LLM, z_ai = independent reviewer. Mix 2-3 daje najlepszy balans między różnorodnością opinii a kosztem." />
                  </label>
                  <div className="flex items-center gap-2 mt-1">
                    {AGENT_TYPES.map(a => (
                      <button key={a} onClick={() => toggleAgentType(a)}
                        className={cn("text-[9px] px-2 py-1 rounded border transition-colors",
                          newRule.agent_types.includes(a)
                            ? "border-sylion-blue/30 text-sylion-blue bg-accent-blue-dim"
                            : "border-[rgba(148,163,184,0.08)] text-muted-foreground"
                        )}>
                        {a}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div>
                    <label className="text-[10px] text-muted-foreground">
                      Czas życia
                      <HelpTip text="Jednorazowy = team zniknie po zakończeniu zadania (lekki, ad-hoc). Stały = team żyje przez całą sesję, zachowuje pamięć między zadaniami (cięższy, ale uczy się kontekstu projektu). Stałe = lepsze do długich projektów, jednorazowe = do incident response." />
                    </label>
                    <select className="mt-1 px-2 py-1 rounded bg-background border border-border text-[11px]"
                      value={newRule.lifetime} onChange={e => setNewRule(r => ({ ...r, lifetime: e.target.value }))}>
                      <option value="ephemeral">Jednorazowy</option>
                      <option value="persistent">Stały</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2 mt-4">
                    <Button variant="ghost" size="sm" className="h-7 text-[10px] text-muted-foreground" onClick={() => setShowAdd(false)}>Anuluj</Button>
                    <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                      onClick={handleAddRule} disabled={saving || !newRule.trigger_pattern.trim()}>
                      {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : null}Dodaj
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rules list */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] overflow-hidden">
          <div className="p-3 border-b border-[rgba(148,163,184,0.08)]">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              Reguły ({data.rules.length})
              <HelpTip text="Lista wszystkich reguł formowania zespołów. Aktywne reguły działają natychmiast przy pasującym evencie. Wyłączenie reguły zatrzymuje nowe spawny ale NIE niszczy już istniejących teamów (zobacz 'Aktywne zespoły' niżej)." />
            </p>
          </div>
          <div className="divide-y divide-[rgba(148,163,184,0.06)]">
            {data.rules.map(rule => (
              <div key={rule.rule_id} className="px-4 py-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <code className="text-[10px] font-mono text-sylion-blue bg-accent-blue-dim px-1.5 py-0.5 rounded">{rule.trigger_pattern}</code>
                    <Badge variant="outline" className={cn("text-[8px]", LIFETIME_COLORS[rule.lifetime] ?? "")}>{rule.lifetime}</Badge>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {rule.agent_types.map((a: string) => (
                      <span key={a} className="text-[9px] px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">{a}</span>
                    ))}
                    <span className="text-[9px] text-muted-foreground">→ {rule.action}</span>
                  </div>
                </div>
                <button
                  onClick={() => handleToggleRule(rule.rule_id, !rule.enabled)}
                  className={cn("text-[9px] px-2 py-1 rounded transition-colors shrink-0",
                    rule.enabled ? "bg-sylion-green/15 text-sylion-green" : "bg-muted/50 text-muted-foreground"
                  )}
                >
                  {rule.enabled ? "Aktywna" : "Wyłączona"}
                </button>
              </div>
            ))}
            {data.rules.length === 0 && (
              <div className="p-6 text-center text-[11px] text-muted-foreground">Brak reguł. Dodaj pierwszą regułę.</div>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Active Teams */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
        <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Aktywne zespoły ({data.active_teams.length})
            <HelpTip text="Aktualnie żyjące teamy (spawnowane przez reguły lub ręcznie). Pokazuje skład agentów + bieżące zadanie. Read-only — do zatrzymania teamu wyłącz odpowiednią regułę i odczekaj aż zadanie się zakończy." />
          </p>
          {data.active_teams.length === 0 ? (
            <p className="text-[11px] text-muted-foreground text-center py-3">Brak aktywnych zespołów</p>
          ) : (
            <div className="space-y-2">
              {data.active_teams.map(team => (
                <div key={team.team_id} className="flex items-center gap-3 p-2 rounded bg-muted/20">
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      {team.agent_types.map((a: string) => (
                        <span key={a} className="text-[9px] px-1.5 py-0.5 rounded bg-accent-blue-dim text-sylion-blue">{a}</span>
                      ))}
                    </div>
                    {team.current_task && <p className="text-[10px] text-muted-foreground mt-0.5">{team.current_task}</p>}
                  </div>
                  <Badge variant="outline" className="text-[8px] border-sylion-amber/30 text-sylion-amber">{team.lifetime}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
