"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { Scale, RefreshCw, Loader2, Play, CheckCircle2, XCircle } from "lucide-react";

const D_LEVELS = ["D0", "D1", "D2", "D3", "D4", "D5"];

export default function CouncilRulesPage() {
  const [rules, setRules] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [simVotes, setSimVotes] = useState<{ rank: number; vote: string }[]>([
    { rank: 5, vote: "for" }, { rank: 4, vote: "for" }, { rank: 3, vote: "against" },
  ]);
  const [simResult, setSimResult] = useState<any>(null);
  const [simLoading, setSimLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRules(await orchestrationApi.getCouncilRules());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!rules) return;
    setSaving(true);
    try {
      const data = await orchestrationApi.updateCouncilRules(rules);
      setRules(data);
    } finally {
      setSaving(false);
    }
  };

  const handleSimulate = async () => {
    setSimLoading(true);
    try {
      const result = await orchestrationApi.simulateCouncilVote(
        simVotes as { rank: number; vote: "for" | "against" | "abstain" }[]
      );
      setSimResult(result);
    } finally {
      setSimLoading(false);
    }
  };

  const updateWeight = (rank: number, weight: number) => {
    setRules((prev: any) => ({
      ...prev,
      rank_weights: prev.rank_weights.map((w: any) =>
        w.rank === rank ? { ...w, weight } : w
      ),
    }));
  };

  const updateSentinel = (d_level: string, field: "cost_required" | "security_required", val: boolean) => {
    setRules((prev: any) => ({
      ...prev,
      sentinel_requirements: prev.sentinel_requirements.map((s: any) =>
        s.d_level === d_level ? { ...s, [field]: val } : s
      ),
    }));
  };

  const addSimVote = () => setSimVotes(v => [...v, { rank: 3, vote: "abstain" }]);
  const removeSimVote = (i: number) => setSimVotes(v => v.filter((_, idx) => idx !== i));
  const updateSimVote = (i: number, field: string, val: any) =>
    setSimVotes(v => v.map((vote, idx) => idx === i ? { ...vote, [field]: val } : vote));

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
            <div className="w-8 h-8 rounded-lg bg-accent-amber-dim flex items-center justify-center">
              <Scale className="w-4 h-4 text-sylion-amber" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Reguły Rady</h1>
              <p className="text-[11px] text-muted-foreground">Wagi rang, bramka krytyka, kworum, wartownicy</p>
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

      {rules && (
        <div className="grid grid-cols-2 gap-4">
          {/* Rank Weights */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Wagi rang
                <HelpTip text="Mnożniki wpływu głosów w consensus. R5 Architect ma największą wagę (decyduje o kierunku), R1 Associate najmniejszą (świeża perspektywa, ale mało doświadczenia). Przy R5=2.0 a R1=0.3 jeden Architect przeważy nad trzema Associates. Domyślne wagi (1.5/1.3/1.1/0.9/0.7) dają zbalansowany ośrodek decyzyjny." />
              </p>
              <div className="space-y-3">
                {rules.rank_weights.map((w: any) => (
                  <div key={w.rank} className="flex items-center gap-3">
                    <div className="w-16 shrink-0">
                      <Badge variant="outline" className="text-[9px] border-sylion-blue/30 text-sylion-blue w-full justify-center">
                        R{w.rank} {w.label}
                      </Badge>
                    </div>
                    <input type="range" min={0.1} max={2.0} step={0.1} value={w.weight}
                      onChange={e => updateWeight(w.rank, parseFloat(e.target.value))}
                      className="flex-1 accent-sylion-blue"
                    />
                    <span className="text-[11px] font-mono text-sylion-blue w-8 text-right">{w.weight.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>

          {/* Critic Gate + Quorum */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Bramka krytyka i kworum
                <HelpTip text="Bramka krytyka = niezależny przegląd argumentów PRZED zatwierdzeniem decyzji. Kworum = minimalna liczba uczestników aby decyzja była ważna (jak w prawdziwej radzie nadzorczej). Te dwa mechanizmy razem chronią przed: (a) jednomyślnymi błędami zespołu, (b) decyzjami w niepełnym składzie." />
              </p>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px]">
                    Bramka krytyka
                    <HelpTip text="Gdy włączona — przed zatwierdzeniem każdej decyzji rady, niezależny model-krytyk ocenia argumenty. Jeśli pewność krytyka < próg, decyzja wraca do dyskusji. To dodatkowy 'devil's advocate', kosztuje 1 dodatkowy call do LLM ale eliminuje groupthink." /></span>
                  <button
                    onClick={() => setRules((r: any) => ({ ...r, critic_gate_enabled: !r.critic_gate_enabled }))}
                    className={cn("text-[9px] px-2 py-1 rounded transition-colors",
                      rules.critic_gate_enabled ? "bg-sylion-green/15 text-sylion-green" : "bg-muted/50 text-muted-foreground"
                    )}
                  >{rules.critic_gate_enabled ? "WŁĄCZONA" : "WYŁĄCZONA"}</button>
                </div>
                {rules.critic_gate_enabled && (
                  <div>
                    <label className="text-[10px] text-muted-foreground">
                      Próg krytyka: {rules.critic_gate_threshold.toFixed(2)}
                      <HelpTip text="Minimalna pewność krytyka (0.1-1.0) aby przepuścić decyzję dalej. 0.5 = 'krytyk musi być neutralnie zgodny', 0.8 = 'krytyk musi być silnie zgodny'. Wyższy próg = ostrzejsza brama, więcej decyzji wraca do rady. Domyślnie 0.65." />
                    </label>
                    <input type="range" min={0.1} max={1.0} step={0.05} value={rules.critic_gate_threshold}
                      onChange={e => setRules((r: any) => ({ ...r, critic_gate_threshold: parseFloat(e.target.value) }))}
                      className="w-full accent-sylion-amber mt-1"
                    />
                  </div>
                )}
                <div>
                  <label className="text-[10px] text-muted-foreground">
                    Min kworum: {rules.quorum_min}
                    <HelpTip text="Minimalna liczba członków rady (1-9) potrzebna by decyzja była ważna. Przy 9 ról ogółem: 3 = niska bariera (3/9=33%), 5 = większość (56%), 7 = supermajority. Pomysł: niskie kworum dla D0-D2 (drobne decyzję), wysokie dla D4-D5 (architektura, security)." />
                  </label>
                  <div className="mt-1 flex items-center gap-2">
                    <input type="range" min={1} max={9} step={1} value={rules.quorum_min}
                      onChange={e => setRules((r: any) => ({ ...r, quorum_min: parseInt(e.target.value) }))}
                      className="flex-1 accent-sylion-blue"
                    />
                    <input
                      aria-label="Minimalne kworum"
                      type="number"
                      min={1}
                      max={9}
                      step={1}
                      value={rules.quorum_min}
                      onChange={e => {
                        const value = Math.min(9, Math.max(1, parseInt(e.target.value) || 1));
                        setRules((r: any) => ({ ...r, quorum_min: value }));
                      }}
                      className="h-7 w-14 rounded border border-border bg-background px-2 text-right text-[11px]"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground">
                    Typ kworum
                    <HelpTip text="Większość = >50% głosów ZA spośród oddanych. Absolutna = >50% wszystkich uprawnionych członków (nieobecność = NIE). Super-większość = ≥66% — używana przy decyzjach wysokiego ryzyka (D4+, security, architektura). Domyślnie: większość." />
                  </label>
                  <select className="mt-1 w-full px-2 py-1 rounded bg-background border border-border text-[11px]"
                    value={rules.quorum_type}
                    onChange={e => setRules((r: any) => ({ ...r, quorum_type: e.target.value }))}
                  >
                    <option value="majority">Większość</option>
                    <option value="absolute">Absolutna</option>
                    <option value="supermajority">Super-większość</option>
                  </select>
                </div>
              </div>
            </Card>
          </motion.div>

          {/* Sentinel Requirements */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Wymagania wartowników
                <HelpTip text="Wartownicy (Sentinels) to wyspecjalizowane gates BLOKUJĄCE decyzję rady. Cost Sentinel = czuwa nad budżetem (zatrzymuje przy przekroczeniu limitów $/token). Security Sentinel = czuwa nad bezpieczeństwem (PII, secrets, supply-chain). Tabela mówi: dla jakich poziomów decyzji (D0-D5) który wartownik MUSI dać zielone światło. D0 = drobne, D5 = krytyczne dla biznesu." />
              </p>
              <div className="overflow-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b border-[rgba(148,163,184,0.08)]">
                      <th className="text-left py-1 text-muted-foreground font-medium">Poziom D</th>
                      <th className="text-center py-1 text-muted-foreground font-medium">Cost Sentinel</th>
                      <th className="text-center py-1 text-muted-foreground font-medium">Security Sentinel</th>
                    </tr>
                  </thead>
                  <tbody>
                    {D_LEVELS.map(dl => {
                      const s = rules.sentinel_requirements.find((x: any) => x.d_level === dl);
                      return (
                        <tr key={dl} className="border-b border-[rgba(148,163,184,0.06)]">
                          <td className="py-1.5 font-mono">{dl}</td>
                          <td className="text-center py-1.5">
                            {s ? (
                              <button onClick={() => updateSentinel(dl, "cost_required", !s.cost_required)}
                                className={cn("text-[8px] px-1.5 py-0.5 rounded",
                                  s.cost_required ? "bg-sylion-green/15 text-sylion-green" : "bg-muted/50 text-muted-foreground"
                                )}
                              >{s.cost_required ? "Wymagany" : "Opcjonalny"}</button>
                            ) : <span className="text-muted-foreground">—</span>}
                          </td>
                          <td className="text-center py-1.5">
                            {s ? (
                              <button onClick={() => updateSentinel(dl, "security_required", !s.security_required)}
                                className={cn("text-[8px] px-1.5 py-0.5 rounded",
                                  s.security_required ? "bg-sylion-red/15 text-sylion-red" : "bg-muted/50 text-muted-foreground"
                                )}
                              >{s.security_required ? "Wymagany" : "Opcjonalny"}</button>
                            ) : <span className="text-muted-foreground">—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </motion.div>

          {/* Vote Simulator */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Symulator głosowania
                <HelpTip text="Wpisujesz kto jak głosuje (ranga + za/przeciw/wstrzymanie) — system policzy ważone głosy używając aktualnych wag rang i powie czy decyzja przeszłaby. Idealne do walidacji: 'czy 2 Architects + 1 Senior wystarczą do zablokowania 5 Associates?'. Nie dotyka rzeczywistych projektów, czysto teoretyczna piaskownica." />
              </p>
              <div className="space-y-2 mb-3">
                {simVotes.map((v, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <select className="px-2 py-1 rounded bg-background border border-border text-[10px]"
                      value={v.rank} onChange={e => updateSimVote(i, "rank", parseInt(e.target.value))}>
                      {[1,2,3,4,5].map(r => <option key={r} value={r}>Ranga {r}</option>)}
                    </select>
                    <select className="px-2 py-1 rounded bg-background border border-border text-[10px]"
                      value={v.vote} onChange={e => updateSimVote(i, "vote", e.target.value)}>
                      <option value="for">Za</option>
                      <option value="against">Przeciw</option>
                      <option value="abstain">Wstrzymanie</option>
                    </select>
                    <button onClick={() => removeSimVote(i)} className="text-muted-foreground hover:text-sylion-red text-xs">✕</button>
                  </div>
                ))}
                <Button variant="ghost" size="sm" className="h-6 text-[10px] text-sylion-blue" onClick={addSimVote}>
                  + Dodaj głos
                </Button>
              </div>
              <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10 w-full"
                onClick={handleSimulate} disabled={simLoading}>
                {simLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
                Symuluj wynik
              </Button>
              {simResult && (
                <div className={cn("mt-3 p-3 rounded-md",
                  simResult.outcome === "approved" ? "bg-sylion-green/10 border border-sylion-green/20" : "bg-sylion-red/10 border border-sylion-red/20"
                )}>
                  <div className="flex items-center gap-2 mb-1">
                    {simResult.outcome === "approved"
                      ? <CheckCircle2 className="w-4 h-4 text-sylion-green" />
                      : <XCircle className="w-4 h-4 text-sylion-red" />}
                    <span className={cn("text-xs font-semibold", simResult.outcome === "approved" ? "text-sylion-green" : "text-sylion-red")}>
                      {simResult.outcome === "approved" ? "ZATWIERDZONE" : "ODRZUCONE"}
                    </span>
                  </div>
                  <div className="text-[10px] text-muted-foreground space-y-0.5">
                    <p>Kworum: {simResult.quorum_met ? "Spełnione" : "Niespełnione"} ({simResult.participating}/{simResult.quorum_min})</p>
                    <p>Waga Za: {simResult.for_weight?.toFixed(2)} | Przeciw: {simResult.against_weight?.toFixed(2)}</p>
                  </div>
                </div>
              )}
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
