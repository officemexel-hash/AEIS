"use client";

import React, { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Settings,
  Key,
  Boxes,
  Users,
  Plus,
  Loader2,
  Trash2,
  WifiOff,
  ArrowUpDown,
  AlertTriangle,
  Layers,
  Wrench,
} from "lucide-react";

export default function SettingsPage() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  if (!backendLive) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh]">
        <WifiOff className="w-8 h-8 text-sylion-red/50 mb-3" />
        <p className="text-sm text-muted-foreground">Backend nieosięgalny</p>
        <p className="text-[10px] text-muted-foreground mt-1">
          Start: <code className="text-primary">python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010</code>
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
          <Settings className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Ustawienia
            <HelpTip text="Centrum konfiguracji platformy: klucze API providerów, hierarchia modeli (thinking/working) oraz sklad rady. Zmiany sa audytowane; modyfikacje hierarchii i rady sa traktowane jako D3+." />
          </h1>
          <p className="text-sm text-muted-foreground">Klucze API, hierarchia modeli, konfiguracja rady</p>
        </div>
      </div>

      <Tabs defaultValue="keys">
        <div className="flex items-center gap-2">
          <TabsList className="bg-muted/20">
            <TabsTrigger value="keys" className="text-xs">
              <Key className="w-3.5 h-3.5 mr-1.5" /> Klucze API
            </TabsTrigger>
            <TabsTrigger value="hierarchy" className="text-xs">
              <Boxes className="w-3.5 h-3.5 mr-1.5" /> Hierarchia modeli
            </TabsTrigger>
            <TabsTrigger value="council" className="text-xs">
              <Users className="w-3.5 h-3.5 mr-1.5" /> Czlonkowie rady
            </TabsTrigger>
          </TabsList>
          <HelpTip text="Trzy zak?adki: Klucze API (sekrety providerów z bud?etami dziennymi/tygodniowymi/30d), Hierarchia (routing thinking vs working z fallback chain), Rada (role i wagi głosow). Wymagaja uprawnien architect/owner." />
        </div>

        <TabsContent value="keys" className="mt-4">
          <APIKeysTab />
        </TabsContent>
        <TabsContent value="hierarchy" className="mt-4">
          <HierarchyTab />
        </TabsContent>
        <TabsContent value="council" className="mt-4">
          <CouncilTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   API Keys Tab — free-form provider input
   ═══════════════════════════════════════════════════════════════════════════ */

const KNOWN_PROVIDERS = ["anthropic", "openai", "ollama", "google", "mistral", "cohere", "deepseek", "groq", "together", "localai"];

function APIKeysTab() {
  const [keys, setKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [provider, setProvider] = useState("");
  const [customProvider, setCustomProvider] = useState("");
  const [keyName, setKeyName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [budgetDaily, setBudgetDaily] = useState("");
  const [budgetWeekly, setBudgetWeekly] = useState("");
  const [budgetMonthly, setBudgetMonthly] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listAPIKeys().then((d) => { setKeys(d.keys ?? []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    const prov = provider === "custom" ? customProvider.trim() : provider;
    if (!prov || !apiKey.trim()) return;
    setSaving(true);
    try {
      const metadata: Record<string, unknown> = {};
      if (parseFloat(budgetDaily) > 0) metadata.budget_daily = parseFloat(budgetDaily);
      if (parseFloat(budgetWeekly) > 0) metadata.budget_weekly = parseFloat(budgetWeekly);
      if (parseFloat(budgetMonthly) > 0) metadata.budget_monthly = parseFloat(budgetMonthly);
      await api.storeAPIKey(prov, apiKey, keyName || prov, Object.keys(metadata).length > 0 ? metadata : undefined);
      const d = await api.listAPIKeys();
      setKeys(d.keys ?? []);
      setShowAdd(false);
      setApiKey("");
      setKeyName("");
      setProvider("");
      setCustomProvider("");
      setBudgetDaily("");
      setBudgetWeekly("");
      setBudgetMonthly("");
    } catch {}
    setSaving(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{keys.length} skonfigurowanych kluczy API</p>
        <Button size="sm" onClick={() => setShowAdd(!showAdd)}>
          <Plus className="w-3.5 h-3.5 mr-1" /> Dodaj klucz
        </Button>
      </div>

      {showAdd && (
        <Card className="p-4 bg-card border-sylion-border space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Provider
                <HelpTip text="Dostawca LLM (np. anthropic, openai, ollama). Okresla format klucza i endpointy. Lokalne modele (ollama, localai) nie wymagaj? klucza, ale wymagaj? URL bazowego." />
              </label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)}
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30">
                <option value="">Wybierz dostawce...</option>
                {KNOWN_PROVIDERS.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
                <option value="custom">Inny (wlasny)...</option>
              </select>
            </div>
            {provider === "custom" && (
              <div>
                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                  Wlasny dostawca
                  <HelpTip text="Identyfikator dostawcy spoza listy znanych. U?ywany jako klucz w routingu i logach. Format: lowercase, bez spacji." />
                </label>
                <input value={customProvider} onChange={(e) => setCustomProvider(e.target.value)} placeholder="moj-provider"
                  className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
              </div>
            )}
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Nazwa klucza
                <HelpTip text="Etykieta opisujaca klucz w UI i audycie. Pomocna gdy masz kilka kluczy tego samego providera (np. dev/prod, projekt-A/projekt-B)." />
              </label>
              <input value={keyName} onChange={(e) => setKeyName(e.target.value)} placeholder="Moj klucz API"
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Klucz API
                <HelpTip text="Sekret providera. Zapisywany w vault zaszyfrowany; nigdy nie pokazywany w czystej postaci po zapisie. Operator widzi tylko maskowana forme (np. sk-...abcd)." />
              </label>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..."
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:border-primary/30" />
            </div>
          </div>
          {/* Budget limits — daily / weekly / 30-day */}
          <div className="border-t border-[rgba(148,163,184,0.06)] pt-3 space-y-2">
            <p className="text-[10px] font-medium text-foreground">
              Limity budżetu (USD, opcjonalne)
              <HelpTip text="Trzy okresy: dzienny, tygodniowy, 30-dniowy. Po przekroczeniu progu model zostaje zatrzymany na ten okres, a routing przelacza sie na fallback chain — praca trwa bez przerwy." />
            </p>
            <p className="text-[9px] text-muted-foreground">Po osiagnieciu limitu model jest dezaktywowany dla danego okresu, a routing przelacza sie na fallback — praca trwa bez przerwy.</p>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-[9px] text-muted-foreground mb-0.5 flex items-center gap-1">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-sylion-green" /> Dzienny
                  <HelpTip text="Limit USD na dobe (UTC). Reset o polnocy. Najczesciej najnizszy z trzech okresow — chroni przed nieoczekiwanym przepaleniem w jeden dzien." />
                </label>
                <input value={budgetDaily} onChange={(e) => setBudgetDaily(e.target.value)} placeholder="1.00" type="number" step="0.01"
                  className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-[11px] focus:outline-none focus:border-primary/30" />
              </div>
              <div>
                <label className="text-[9px] text-muted-foreground mb-0.5 flex items-center gap-1">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-sylion-amber" /> Tygodniowy
                  <HelpTip text="Limit USD na 7 dni kroczących. Wykrywa serie drogich uruchomień, które mieszcz? się w dziennym limicie, ale narastają w tygodniu." />
                </label>
                <input value={budgetWeekly} onChange={(e) => setBudgetWeekly(e.target.value)} placeholder="5.00" type="number" step="0.01"
                  className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-[11px] focus:outline-none focus:border-primary/30" />
              </div>
              <div>
                <label className="text-[9px] text-muted-foreground mb-0.5 flex items-center gap-1">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary" /> 30-dniowy
                  <HelpTip text="Limit USD na 30 dni kroczących — twardy sufit miesieczny. Najczesciej powiazany z faktycznym billingiem providera." />
                </label>
                <input value={budgetMonthly} onChange={(e) => setBudgetMonthly(e.target.value)} placeholder="20.00" type="number" step="0.01"
                  className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-[11px] focus:outline-none focus:border-primary/30" />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>Anuluj</Button>
            <Button size="sm" onClick={handleSave} disabled={saving || !apiKey.trim() || (!provider || (provider === "custom" && !customProvider.trim()))}>
              {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Key className="w-3.5 h-3.5 mr-1" />}
              Zapisz klucz
            </Button>
          </div>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 text-muted-foreground animate-spin" /></div>
      ) : keys.length === 0 ? (
        <Card className="p-8 bg-card border-sylion-border text-center">
          <Key className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
          <p className="text-xs text-muted-foreground">Nie skonfigurowano jeszcze zadnych kluczy API</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <Card key={k.key_id} className="p-3 bg-card border-sylion-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant="outline" className={cn("text-[9px]",
                  k.provider === "anthropic" ? "border-sylion-amber/30 text-sylion-amber" :
                  k.provider === "openai" ? "border-sylion-green/30 text-sylion-green" :
                  "border-primary/30 text-primary"
                )}>{k.provider}</Badge>
                <span className="text-xs font-medium">{k.display_name || k.masked_key}</span>
                <Badge variant="outline" className={cn("text-[8px]",
                  k.is_active ? "border-sylion-green/30 text-sylion-green" : "border-muted-foreground/30 text-muted-foreground"
                )}>{k.is_active ? "Aktywny" : "Nieaktywny"}</Badge>
                {/* Budget badges from metadata */}
                {k.metadata?.budget_daily > 0 && (
                  <Badge variant="outline" className="text-[8px] border-sylion-green/20 text-sylion-green">
                    ${k.metadata.budget_daily}/day
                  </Badge>
                )}
                {k.metadata?.budget_weekly > 0 && (
                  <Badge variant="outline" className="text-[8px] border-sylion-amber/20 text-sylion-amber">
                    ${k.metadata.budget_weekly}/wk
                  </Badge>
                )}
                {k.metadata?.budget_monthly > 0 && (
                  <Badge variant="outline" className="text-[8px] border-primary/20 text-primary">
                    ${k.metadata.budget_monthly}/30d
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" className="h-7 text-[10px]" onClick={async () => {
                  try { const res = await api.validateAPIKey(k.key_id); alert(res.valid ? `Klucz prawidlowy: ${k.key_id}` : `Nieprawidlowy: ${res.details ?? "nieznany"}`); } catch (e: any) { alert(`Walidacja nie powiodla sie: ${e.message}`); }
                }}>
                  Waliduj
                </Button>
                <Button variant="ghost" size="sm" className="h-7 text-[10px]" onClick={async () => {
                  try { await api.activateAPIKey(k.key_id); const d = await api.listAPIKeys(); setKeys(d.keys ?? []); } catch {}
                }}>
                  {k.is_active ? "Dezaktywuj" : "Aktywuj"}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Model Hierarchy Tab — thinking layer + working layer + budget fallback
   ═══════════════════════════════════════════════════════════════════════════ */

interface HierarchyLevel {
  model_id: string;
  layer: "thinking" | "working" | "both";
  priority: number;
  task_types: string[];
  budget_daily: string;
  budget_weekly: string;
  budget_monthly: string;
  fallback_chain: string;
  max_concurrent: string;
  temperature: string;
}

function HierarchyTab() {
  const [hierarchies, setHierarchies] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [hierName, setHierName] = useState("");
  const [levels, setLevels] = useState<HierarchyLevel[]>([
    { model_id: "", layer: "thinking", priority: 1, task_types: ["analysis", "planning"], budget_daily: "", budget_weekly: "", budget_monthly: "", fallback_chain: "", max_concurrent: "", temperature: "" },
  ]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listHierarchies().then((d) => setHierarchies(d.hierarchies ?? [])).catch(() => {});
  }, []);

  const addLevel = () => {
    setLevels([...levels, {
      model_id: "", layer: "both", priority: levels.length + 1, task_types: [],
      budget_daily: "", budget_weekly: "", budget_monthly: "", fallback_chain: "", max_concurrent: "", temperature: "",
    }]);
  };

  const removeLevel = (idx: number) => {
    setLevels(levels.filter((_, i) => i !== idx));
  };

  const updateLevel = (idx: number, field: keyof HierarchyLevel, value: any) => {
    const updated = [...levels];
    updated[idx] = { ...updated[idx], [field]: value };
    setLevels(updated);
  };

  const handleCreate = async () => {
    if (!hierName.trim() || levels.length === 0 || saving) return;
    setSaving(true);
    try {
      const apiLevels = levels.map((l) => ({
        model_id: l.model_id, layer: l.layer, priority: l.priority, task_types: l.task_types,
        budget_daily: l.budget_daily, budget_weekly: l.budget_weekly, budget_monthly: l.budget_monthly,
        fallback_chain: l.fallback_chain, max_concurrent: l.max_concurrent, temperature: l.temperature,
      }));
      await api.saveHierarchy(hierName, apiLevels);
      const d = await api.listHierarchies();
      setHierarchies(d.hierarchies ?? []);
      setShowCreate(false);
      setHierName("");
      setLevels([{ model_id: "", layer: "thinking", priority: 1, task_types: ["analysis", "planning"], budget_daily: "", budget_weekly: "", budget_monthly: "", fallback_chain: "", max_concurrent: "", temperature: "" }]);
    } catch {}
    setSaving(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Definiuj routing modeli: warstwy thinking vs working, fallback chain i obsluga wyczerpania budżetu
        </p>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="w-3.5 h-3.5 mr-1" /> Nowa hierarchia
        </Button>
      </div>

      {/* Explanation */}
      <Card className="p-3 bg-primary/5 border-primary/10">
        <div className="flex items-start gap-2">
          <Layers className="w-4 h-4 text-primary shrink-0 mt-0.5" />
          <div className="text-[10px] text-muted-foreground space-y-1">
            <p><span className="text-primary font-medium">Warstwa Thinking</span> — analiza, planowanie, code review, naradzie rady</p>
            <p><span className="text-sylion-amber font-medium">Warstwa Working</span> — generowanie kodu, wykonanie, testy, deployment</p>
            <p><span className="text-sylion-green font-medium">Fallback Chain</span> — lista modeli (rozdzielona przecinkami) probowana, gdy bie??cy wyczerpal bud?et lub padnie. Praca trwa bez przerwy.</p>
            <p><span className="text-sylion-red font-medium">Wyczerpanie budżetu</span> — gdy zostanie osiagniety jakikolwiek limit okresowy (dzienny/tygodniowy/30-dniowy), model zostaje dezaktywowany na ten okres, a fallback chain przejmuje routing</p>
          </div>
        </div>
      </Card>

      {/* Create form */}
      {showCreate && (
        <Card className="p-4 bg-card border-sylion-border space-y-4">
          <div className="grid grid-cols-1 gap-3">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Nazwa hierarchii
                <HelpTip text="Nazwa identyfikuje hierarchie w routerze i logach. Mozesz miec wiele hierarchii (np. dev/prod, projekt-A/projekt-B); domyslna oznaczona jest jako Default." />
              </label>
              <input value={hierName} onChange={(e) => setHierName(e.target.value)} placeholder="Routing produkcyjny"
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
          </div>

          {/* Level rows */}
          <div className="space-y-3">
            <p className="text-[10px] font-medium text-foreground">
              Poziomy (wy?szy priorytet = preferowany)
              <HelpTip text="Każdy poziom to wpis routingowy (model + warstwa + priorytet). Router próbuje od najwyższego priorytetu w dol; jesli jeden padnie lub wyczerpie bud?et, fallback przekazuje sterowanie nizszym poziomom." />
            </p>
            {levels.map((lvl, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-secondary/10 border border-[rgba(148,163,184,0.06)] space-y-2">
                {/* Row 1: Model + Layer + Priority */}
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 block">
                      Model ID
                      <HelpTip text="Pełny identyfikator modelu providera (np. claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5-20251001, gpt-5, gpt-5-mini, qwen2.5:72b-instruct). Musi pasowac do formatu providera — sprawdźane przy walidacji." />
                    </label>
                    <input value={lvl.model_id} onChange={(e) => updateLevel(idx, "model_id", e.target.value)}
                      placeholder="claude-sonnet-4-20250514"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] font-mono focus:outline-none focus:border-primary/30" />
                  </div>
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 block">
                      Warstwa
                      <HelpTip text="Thinking — analiza/planowanie/review (drogie, dokładne). Working — generowanie/wykonanie/testy (szybsze, tańsze). Both — model używany w obu trybach." />
                    </label>
                    <select value={lvl.layer} onChange={(e) => updateLevel(idx, "layer", e.target.value)}
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30">
                      <option value="thinking">Thinking</option>
                      <option value="working">Working</option>
                      <option value="both">Both</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 block">
                      Priorytet
                      <HelpTip text="Liczba ca?kowita >= 1. Wy?sza wartość = wy?szy priorytet w routingu. W tej samej warstwie router próbuje od najwyższego do najni?szego priorytetu." />
                    </label>
                    <input type="number" value={lvl.priority} onChange={(e) => updateLevel(idx, "priority", parseInt(e.target.value) || 1)} min={1}
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30" />
                  </div>
                </div>
                {/* Row 2: Budget periods */}
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-sylion-green" /> Budzet dzienny ($)
                      <HelpTip text="Limit USD na 24h dla tego poziomu. Po przekroczeniu poziom dezaktywowany na resztę doby; fallback chain przejmuje routing." />
                    </label>
                    <input value={lvl.budget_daily} onChange={(e) => updateLevel(idx, "budget_daily", e.target.value)} placeholder="1.00"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30" />
                  </div>
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-sylion-amber" /> Budzet tygodniowy ($)
                      <HelpTip text="Limit USD na 7 dni kroczących. Wykrywa serie drogich uruchomień, które mieszcz? się w dziennym limicie, ale narastają w tygodniu." />
                    </label>
                    <input value={lvl.budget_weekly} onChange={(e) => updateLevel(idx, "budget_weekly", e.target.value)} placeholder="5.00"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30" />
                  </div>
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary" /> Budzet 30-dniowy ($)
                      <HelpTip text="Limit USD na 30 dni kroczących — twardy sufit miesieczny. Najczesciej dopasowany do faktycznego billingu providera." />
                    </label>
                    <input value={lvl.budget_monthly} onChange={(e) => updateLevel(idx, "budget_monthly", e.target.value)} placeholder="20.00"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30" />
                  </div>
                </div>
                {/* Row 3: Fallback chain + concurrency + temperature */}
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 block">
                      Fallback Chain (rozdzielone przecinkami)
                      <HelpTip text="Lista model_id probowana po kolei, gdy bie??cy poziom padnie lub wyczerpie bud?et. Pierwsza pasujaca dostepna pozycja przejmuje routing — praca trwa bez przerwy." />
                    </label>
                    <input value={lvl.fallback_chain} onChange={(e) => updateLevel(idx, "fallback_chain", e.target.value)}
                      placeholder="gpt-4o-mini, llama3"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] font-mono focus:outline-none focus:border-primary/30" />
                  </div>
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 block">
                      Max r?wnoleglych
                      <HelpTip text="Maksymalna liczba rownoczesnych zapytan do tego modelu. Chroni przed rate-limitem providera. Domyslnie 5." />
                    </label>
                    <input value={lvl.max_concurrent} onChange={(e) => updateLevel(idx, "max_concurrent", e.target.value)} placeholder="5"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30" />
                  </div>
                  <div>
                    <label className="text-[8px] text-muted-foreground mb-0.5 block">
                      Temperature
                      <HelpTip text="Parametr losowosci modelu (0.0-2.0). Niskie wartośći (0.0-0.3) — deterministyczne, dla testów/walidacji. Wysokie (0.7-1.0) — kreatywne, dla brainstormingu." />
                    </label>
                    <input value={lvl.temperature} onChange={(e) => updateLevel(idx, "temperature", e.target.value)} placeholder="0.7"
                      className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2 py-1.5 text-[10px] focus:outline-none focus:border-primary/30" />
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button variant="ghost" size="sm" className="h-6 text-[9px] text-sylion-red/60 hover:text-sylion-red"
                    onClick={() => removeLevel(idx)} disabled={levels.length <= 1}>
                    <Trash2 className="w-3 h-3 mr-1" /> Usun
                  </Button>
                </div>
              </div>
            ))}
            <Button variant="ghost" size="sm" className="text-[10px] gap-1" onClick={addLevel}>
              <Plus className="w-3 h-3" /> Dodaj poziom
            </Button>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setShowCreate(false)}>Anuluj</Button>
            <Button size="sm" onClick={handleCreate} disabled={saving || !hierName.trim()}>
              {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Boxes className="w-3.5 h-3.5 mr-1" />}
              Utworz hierarchie
            </Button>
          </div>
        </Card>
      )}

      {/* Existing hierarchies */}
      {hierarchies.length === 0 && !showCreate ? (
        <Card className="p-8 bg-card border-sylion-border text-center">
          <Boxes className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
          <p className="text-xs text-muted-foreground">Brak skonfigurowanych hierarchii</p>
          <p className="text-[10px] text-muted-foreground mt-1">Dodaj hierarchie aby zdefiniowac routing modeli z fallback chain i okresami bud?etowymi</p>
        </Card>
      ) : (
        hierarchies.map((h) => (
          <Card key={h.hierarchy_id} className="p-3 bg-card border-sylion-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium">{h.name}</span>
              {h.is_active && <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">Domyślna</Badge>}
            </div>
            {(h.levels || []).map((lvl: any, i: number) => (
              <div key={i} className="flex items-center gap-2 py-1 text-[10px] flex-wrap">
                <Badge variant="outline" className={cn("text-[8px] h-4",
                  lvl.layer === "thinking" ? "border-primary/30 text-primary" :
                  lvl.layer === "working" ? "border-sylion-amber/30 text-sylion-amber" :
                  "border-sylion-green/30 text-sylion-green"
                )}>
                  {lvl.layer === "thinking" ? <Layers className="w-2.5 h-2.5 mr-0.5" /> : <Wrench className="w-2.5 h-2.5 mr-0.5" />}
                  {lvl.layer || "both"}
                </Badge>
                <span className="font-mono text-muted-foreground">{lvl.model_id}</span>
                <span className="text-muted-foreground">P{lvl.priority}</span>
                {lvl.budget_daily && <Badge variant="outline" className="text-[7px] h-3.5 border-sylion-green/20 text-sylion-green">${lvl.budget_daily}/d</Badge>}
                {lvl.budget_weekly && <Badge variant="outline" className="text-[7px] h-3.5 border-sylion-amber/20 text-sylion-amber">${lvl.budget_weekly}/w</Badge>}
                {lvl.budget_monthly && <Badge variant="outline" className="text-[7px] h-3.5 border-primary/20 text-primary">${lvl.budget_monthly}/30d</Badge>}
                {lvl.fallback_chain && <span className="text-[8px] text-sylion-green/70">fallback: {lvl.fallback_chain}</span>}
              </div>
            ))}
          </Card>
        ))
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Council Members Tab — advanced configuration
   ═══════════════════════════════════════════════════════════════════════════ */

function CouncilTab() {
  const [members, setMembers] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [modelId, setModelId] = useState("");
  const [memberName, setMemberName] = useState("");
  const [role, setRole] = useState("analyst");
  const [priority, setPriority] = useState(0);
  const [votingWeight, setVotingWeight] = useState(1);
  const [specialization, setSpecialization] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [maxTokens, setMaxTokens] = useState("");

  useEffect(() => {
    api.listCouncilMemberConfigs().then((d) => setMembers(d.members ?? [])).catch(() => {});
  }, []);

  const handleAdd = async () => {
    if (!modelId.trim()) return;
    try {
      await api.configureCouncilMember(memberName || modelId, modelId, role, priority, systemPrompt || undefined);
      const d = await api.listCouncilMemberConfigs();
      setMembers(d.members ?? []);
      setShowAdd(false);
      setModelId("");
      setMemberName("");
      setRole("analyst");
      setPriority(0);
      setVotingWeight(1);
      setSpecialization("");
      setSystemPrompt("");
      setMaxTokens("");
    } catch {}
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{members.length} czlonkow rady</p>
        <Button size="sm" onClick={() => setShowAdd(!showAdd)}>
          <Plus className="w-3.5 h-3.5 mr-1" /> Dodaj członka
        </Button>
      </div>

      {/* Explanation */}
      <Card className="p-3 bg-sylion-amber/5 border-sylion-amber/10">
        <div className="flex items-start gap-2">
          <Users className="w-4 h-4 text-sylion-amber shrink-0 mt-0.5" />
          <div className="text-[10px] text-muted-foreground space-y-1">
            <p><span className="text-sylion-amber font-medium">Role</span> — Analityk: bada dane, Krytyk: kwestionuje zalozenia, Syntezator: laczy perspektywy, Moderator: prowadzi dyskusje, Architekt: projektuje rozwiazania, Reviewer: bramki jako?ciowe</p>
            <p><span className="text-primary font-medium">Waga głosu</span> — jak mocno werdykt tego członka liczy sie w skonsolidowanej decyzji rady</p>
            <p><span className="text-sylion-green font-medium">Specjalizacja</span> — domena np. bezpieczenstwo, wydajnosc, UX, architektura</p>
          </div>
        </div>
      </Card>

      {showAdd && (
        <Card className="p-4 bg-card border-sylion-border space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Model ID
                <HelpTip text="Identyfikator modelu providera, który będzie pełnił role członka rady. Różnorodne modele w jednej radzie dają lepsze pokrycie blind spotow." />
              </label>
              <input value={modelId} onChange={(e) => setModelId(e.target.value)} placeholder="np. claude-opus-4-7, claude-sonnet-4-6, gpt-5, gpt-5-mini, qwen2.5:72b-instruct, ollama-bielik..."
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:border-primary/30" />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Nazwa członka
                <HelpTip text="Krótka etykieta widoczna w naradzie i logach (np. 'Analityk Claude', 'Krytyk GPT-4o'). Pomaga rozróżnić, który model grał daną rolę." />
              </label>
              <input value={memberName} onChange={(e) => setMemberName(e.target.value)} placeholder="np. Analityk Claude"
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Rola
                <HelpTip text="Funkcja w naradzie: Analityk analizuje dane, Krytyk kwestionuje, Syntezator laczy, Moderator prowadzi, Architekt projektuje, Reviewer waliduje. Wpływa na system prompt." />
              </label>
              <select value={role} onChange={(e) => setRole(e.target.value)}
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30">
                <option value="analyst">Analityk</option>
                <option value="critic">Krytyk</option>
                <option value="synthesizer">Syntezator</option>
                <option value="moderator">Moderator</option>
                <option value="architect">Architekt</option>
                <option value="reviewer">Reviewer</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Priorytet
                <HelpTip text="Kolejnosc wypowiedzi w naradzie. Wyzszy priorytet = wczesniejsza wypowiedz, co wp?ywa na 'pierwszego mowce' w syntezie. Domyslnie 0." />
              </label>
              <input type="number" value={priority} onChange={(e) => setPriority(parseInt(e.target.value) || 0)} min={0}
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Waga głosu
                <HelpTip text="Wspolczynnik (0.1 - 5.0) z jakim głos członka liczy sie w finalnym konsensusie. Senior Architect moze miec 2.0, podczas gdy Reviewer 1.0. Domyslnie 1.0." />
              </label>
              <input type="number" value={votingWeight} onChange={(e) => setVotingWeight(parseFloat(e.target.value) || 1)} min={0.1} step={0.1}
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Specjalizacja
                <HelpTip text="Domena ekspertyzy (np. security, performance, UX, architecture, compliance). Wstrzykiwana do system prompta — wzmacnia reakcje krytyczne na pytania w tej domenie." />
              </label>
              <input value={specialization} onChange={(e) => setSpecialization(e.target.value)} placeholder="bezpieczenstwo, wydajnosc, UX..."
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
                Max tokenow
                <HelpTip text="Limit tokenow odpowiedzi tego członka. Niski limit (1024) wymusza zwiezlosc, wysoki (8192) pozwala na rozbudowane analizy. Domyslnie 4096." />
              </label>
              <input value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} placeholder="4096"
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30" />
            </div>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">
              Wlasny system prompt (opcjonalny)
              <HelpTip text="Dodatkowe instrukcje doklejone do bazowego promptu roli. Uzyteczne gdy chcesz wzmocnic okreslone zachowanie (np. 'zawsze pytaj o impact na produkcje')." />
            </label>
            <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={2}
              placeholder="Dodatkowe instrukcje dla tego członka rady..."
              className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30 resize-none" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>Anuluj</Button>
            <Button size="sm" onClick={handleAdd} disabled={!modelId.trim()}>Dodaj</Button>
          </div>
        </Card>
      )}

      {members.length === 0 ? (
        <Card className="p-8 bg-card border-sylion-border text-center">
          <Users className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
          <p className="text-xs text-muted-foreground">Brak skonfigurowanych czlonkow rady</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {members.map((m) => (
            <Card key={m.member_id} className="p-3 bg-card border-sylion-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-medium">{m.member_id}</span>
                  <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">{m.role}</Badge>
                  <span className="text-[9px] text-muted-foreground font-mono">{m.model_id}</span>
                  <span className="text-[8px] text-muted-foreground">P{m.priority}</span>
                </div>
                <Badge variant="outline" className={cn("text-[8px] border-sylion-green/30 text-sylion-green")}>
                  Skonfigurowany
                </Badge>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
