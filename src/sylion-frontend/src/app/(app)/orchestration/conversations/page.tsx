"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { MessageSquare, RefreshCw, Loader2, Check, Play } from "lucide-react";

const MODELS = [
  "claude-haiku-4-5-20251001",
  "claude-sonnet-4-6",
  "claude-opus-4-7",
  "gpt-4o-mini",
  "gpt-4o",
];

export default function InterModelConversationsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // F-bug-J9: auto-save state — user reported toggle reverted after leaving.
  // We now debounce-persist any change so "leave + come back" preserves state.
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);
  const skipNextAutosaveRef = useRef<boolean>(true); // skip after initial load

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // mark next state-set as "from server" so the autosave effect doesn't
      // fire and immediately re-send the value back.
      skipNextAutosaveRef.current = true;
      setSettings(await orchestrationApi.getInterModelConversation());
    } finally {
      setLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  // Auto-save debounced 400ms after last user change. Means: toggle clicks,
  // slider drags and dropdown changes all persist without an explicit
  // "Zapisz" click. The button is still there as an instant-save fallback.
  useEffect(() => {
    if (!settings) return;
    if (skipNextAutosaveRef.current) {
      skipNextAutosaveRef.current = false;
      return;
    }
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current);
    }
    debounceRef.current = window.setTimeout(async () => {
      setSaving(true);
      setSaveError(null);
      try {
        const data = await orchestrationApi.updateInterModelConversation(settings);
        // Use ref so we don't re-trigger the autosave effect after server echo.
        skipNextAutosaveRef.current = true;
        setSettings(data);
        setSavedAt(Date.now());
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : "Błąd autosave");
      } finally {
        setSaving(false);
      }
    }, 400);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [settings]);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaveError(null);
    try {
      const data = await orchestrationApi.updateInterModelConversation(settings);
      skipNextAutosaveRef.current = true;
      setSettings(data);
      setSavedAt(Date.now());
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Błąd zapisu");
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerConversation = async () => {
    if (!settings) return;
    setTriggering(true);
    setTriggerResult(null);
    try {
      if (!settings.enabled) {
        const enabled = await orchestrationApi.updateInterModelConversation({ ...settings, enabled: true });
        skipNextAutosaveRef.current = true;
        setSettings(enabled);
      }
      const record = await orchestrationApi.triggerInterModelConversation({
        topic: "Operator dashboard runtime check: rozmowa modeli o meta-orchestracji, guardach, kosztach i pamięci.",
      });
      setTriggerResult(`Rozmowa zakończona: ${record.turns} tur`);
      skipNextAutosaveRef.current = true;
      setSettings(await orchestrationApi.getInterModelConversation());
    } catch (err) {
      setTriggerResult(err instanceof Error ? err.message : "Błąd rozmowy runtime");
    } finally {
      setTriggering(false);
    }
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
              <MessageSquare className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Rozmowy Modeli (J9)</h1>
              <p className="text-[11px] text-muted-foreground">Agent-to-agent discussion, arbitraż, log konwersacji</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Autosave indicator (F-bug-J9) */}
            {saving ? (
              <span className="text-[10px] text-muted-foreground inline-flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                Zapisuję…
              </span>
            ) : saveError ? (
              <span className="text-[10px] text-sylion-red">{saveError}</span>
            ) : savedAt ? (
              <span className="text-[10px] text-sylion-green inline-flex items-center gap-1">
                <Check className="w-3 h-3" />
                Zapisano
              </span>
            ) : null}
            {triggerResult ? <span className="text-[10px] text-sylion-green">{triggerResult}</span> : null}
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10"
              onClick={handleTriggerConversation} disabled={triggering || saving}>
              {triggering ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
              Uruchom rozmowę
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load}><RefreshCw className="w-3 h-3 mr-1" />Odśwież</Button>
            <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
              onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : null}Zapisz
            </Button>
          </div>
        </div>
      </motion.div>

      {settings && (
        <div className="grid grid-cols-2 gap-4">
          {/* Main Settings */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                Ustawienia
                <HelpTip text="Globalne parametry rozmów agent-do-agent. Wyłączone = agenci pracują w izolacji (szybciej, taniej). Włączone = agenci konsultują się przed kluczowymi decyzjami (wolniej, drożej, ale wyższa jakość przy złożonej logice)." />
              </p>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[11px] font-medium">
                      Rozmowy agent-do-agent
                      <HelpTip text="Master switch. Włącza możliwość bezpośredniej rozmowy między dwoma agentami (np. Codex pyta Claude o opinię). Każda rozmowa = dodatkowe LLM calle = wyższy koszt, ale lepsza jakość przy decyzjach D2+. Domyślnie WŁĄCZONE dla prod, wyłączone dla MVP/dev." />
                    </p>
                    <p className="text-[10px] text-muted-foreground">Umożliwia agentom konsultacje przed implementacją</p>
                  </div>
                  <button
                    onClick={() => setSettings((s: any) => ({ ...s, enabled: !s.enabled }))}
                    className={cn(
                      "text-[9px] px-3 py-1.5 rounded border transition-colors",
                      settings.enabled
                        ? "border-sylion-green/30 text-sylion-green bg-sylion-green/10"
                        : "border-[rgba(148,163,184,0.08)] text-muted-foreground"
                    )}
                  >
                    {settings.enabled ? "WŁĄCZONE" : "WYŁĄCZONE"}
                  </button>
                </div>

                {settings.enabled && (
                  <>
                    <div>
                      <label className="text-[10px] text-muted-foreground">
                        Głębokość dyskusji (max tury): {settings.max_turns}
                        <HelpTip text="Maksymalna liczba wymian zdań A↔B w jednej rozmowie. 3-4 = krótka konsultacja, 6-8 = poważna dyskusja, 10 = dogłębna debata. Wyższe = lepsza jakość ale mnoży koszt LLM (tury × 2 calle). Sweet spot: 5 dla większości decyzji." />
                      </label>
                      <input type="range" min={1} max={10} step={1} value={settings.max_turns}
                        onChange={e => setSettings((s: any) => ({ ...s, max_turns: parseInt(e.target.value) }))}
                        className="w-full accent-sylion-blue mt-1"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] text-muted-foreground">
                        Model arbiter (przy sporach)
                        <HelpTip text="Trzeci model który rozstrzyga gdy A i B nie mogą się dogadać po max turach. Zalecany Opus (najlepszy reasoning, ale drogi) lub Sonnet (kompromis). 'Brak arbitra' = przy sporze decyzja eskaluje do human gate (bezpieczniej, ale wolniej)." />
                      </label>
                      <select className="mt-1 w-full px-2 py-1 rounded bg-background border border-border text-[11px]"
                        value={settings.arbiter_model_id ?? ""}
                        onChange={e => setSettings((s: any) => ({ ...s, arbiter_model_id: e.target.value || null }))}
                      >
                        <option value="">Brak arbitra</option>
                        {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-[11px]">
                          Głosowanie przy sporach
                          <HelpTip text="Gdy A i B się nie zgadzają, system pyta TRZECIEGO niezależnego agenta o głos rozstrzygający (zamiast arbitra-modela). Tańsze niż używanie Opus jako arbiter, ale ryzyko że trzeci agent też nie zna kontekstu. Wyłączone = od razu eskalacja do arbitra/human." />
                        </p>
                        <p className="text-[10px] text-muted-foreground">Trzeci agent arbitruje przy niezgodności 2 agentów</p>
                      </div>
                      <button
                        onClick={() => setSettings((s: any) => ({ ...s, disagreement_voting: !s.disagreement_voting }))}
                        className={cn("text-[9px] px-2 py-1 rounded transition-colors",
                          settings.disagreement_voting ? "bg-sylion-blue/15 text-sylion-blue" : "bg-muted/50 text-muted-foreground"
                        )}
                      >
                        {settings.disagreement_voting ? "Włączone" : "Wyłączone"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </Card>
          </motion.div>

          {/* Recent Conversations */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Ostatnie konwersacje ({settings.recent_conversations?.length ?? 0})
                <HelpTip text="Read-only log ostatnich rozmów A↔B. Pokazuje skład pary, temat i liczbę tur. Używaj do triage: rozmowy z max turami osiąganymi notorycznie = sygnał że agenci nie potrafią się dogadać i potrzeba ostrzejszego arbitra." />
              </p>
              {!settings.recent_conversations || settings.recent_conversations.length === 0 ? (
                <div className="text-center py-8">
                  <MessageSquare className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-[11px] text-muted-foreground">Brak zarejestrowanych konwersacji</p>
                  <p className="text-[10px] text-muted-foreground/70 mt-1">
                    {settings.enabled ? "Konwersacje pojawią się po aktywacji agentów" : "Włącz rozmowy modeli, aby zarejestrować historię"}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {settings.recent_conversations.map((conv: any, i: number) => (
                    <div key={i} className="p-2 rounded bg-muted/20 text-[10px]">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-[8px] border-sylion-blue/30 text-sylion-blue">{conv.agent_a}</Badge>
                        <span className="text-muted-foreground">↔</span>
                        <Badge variant="outline" className="text-[8px] border-violet-400/30 text-violet-400">{conv.agent_b}</Badge>
                        <span className="text-muted-foreground ml-auto">{conv.turns} tur</span>
                      </div>
                      <p className="text-muted-foreground truncate">{conv.topic ?? "Brak tematu"}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </motion.div>

          {/* Info card */}
          {!settings.enabled && (
            <motion.div className="col-span-2" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Jak działają rozmowy modeli?</p>
                <div className="grid grid-cols-3 gap-4 text-[11px] text-muted-foreground">
                  <div>
                    <p className="font-medium text-foreground mb-1">Konsultacje</p>
                    <p>Codex może zapytać Kimi o opinię przed implementacją skomplikowanej logiki</p>
                  </div>
                  <div>
                    <p className="font-medium text-foreground mb-1">Arbitraż</p>
                    <p>Gdy 2 agenty się nie zgadzają, arbiter (np. Claude Opus) podejmuje decyzję</p>
                  </div>
                  <div>
                    <p className="font-medium text-foreground mb-1">Głębokość</p>
                    <p>Max tury ograniczają czas trwania dyskusji, zapobiegając nieskończonym pętlom</p>
                  </div>
                </div>
              </Card>
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}
