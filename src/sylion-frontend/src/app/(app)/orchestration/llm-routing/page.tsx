"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { api } from "@/lib/api/client";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Network,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Loader2,
  WifiOff,
  Zap,
  Eye,
  EyeOff,
  Copy,
  Filter,
  ExternalLink,
  ChevronRight,
  Check,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DOMAINS = [
  { key: "all", label: "Wszystkie" },
  { key: "fintech", label: "Fintech", types: ["cost_optimization", "security", "subscription", "funding", "architecture"] },
  { key: "healthcare", label: "Healthcare", types: ["security", "scaling", "architecture", "maintenance", "onboarding"] },
  { key: "ecommerce", label: "E-Commerce", types: ["cost_optimization", "scaling", "subscription", "architecture", "maintenance"] },
  { key: "saas", label: "B2B SaaS", types: ["cost_optimization", "architecture", "subscription", "onboarding", "maintenance"] },
  { key: "marketplace", label: "Marketplace", types: ["scaling", "architecture", "subscription", "cost_optimization"] },
  { key: "gaming", label: "Gaming", types: ["scaling", "architecture", "cost_optimization", "maintenance"] },
  { key: "iot", label: "IoT", types: ["scaling", "security", "architecture", "maintenance"] },
  { key: "media", label: "Media", types: ["scaling", "cost_optimization", "architecture", "maintenance"] },
  { key: "legal", label: "Legal / RegTech", types: ["security", "architecture", "onboarding", "maintenance"] },
  { key: "education", label: "EdTech", types: ["onboarding", "cost_optimization", "architecture", "subscription"] },
  { key: "government", label: "Gov / Publiczny", types: ["security", "architecture", "maintenance", "onboarding"] },
  { key: "ngo", label: "NGO / Non-profit", types: ["cost_optimization", "funding", "onboarding"] },
  { key: "startup", label: "Startup", types: ["cost_optimization", "funding", "architecture", "scaling", "onboarding"] },
  { key: "enterprise", label: "Enterprise", types: ["security", "architecture", "maintenance", "scaling", "cost_optimization"] },
];

const RISK_LEVELS = ["low", "medium", "high", "critical"];

const RISK_META: Record<string, { label: string; color: string }> = {
  low: { label: "Niskie", color: "text-sylion-green border-sylion-green/30" },
  medium: { label: "Srednie", color: "text-sylion-amber border-sylion-amber/30" },
  high: { label: "Wysokie", color: "text-orange-400 border-orange-400/30" },
  critical: { label: "Krytyczne", color: "text-sylion-red border-sylion-red/30" },
};

const REC_TYPE_LABELS: Record<string, string> = {
  cost_optimization: "Optymalizacja kosztow",
  scaling: "Skalowanie",
  security: "Bezpieczenstwo",
  subscription: "Subskrypcje",
  architecture: "Architektura",
  funding: "Finansowanie",
  onboarding: "Onboarding",
  maintenance: "Utrzymanie",
};

const PRESETS: { key: "cost-saving" | "balanced" | "aggressive"; label: string; desc: string }[] = [
  { key: "cost-saving", label: "Oszczedny", desc: "Haiku dla wszystkich" },
  { key: "balanced", label: "Zbalansowany", desc: "Domyslny mix" },
  { key: "aggressive", label: "Agresywny", desc: "Opus dla wszystkich" },
];

const FALLBACK_MODELS = [
  "claude-haiku-4-5-20251001",
  "claude-sonnet-4-6",
  "claude-opus-4-7",
  "gpt-4o-mini",
  "gpt-4o",
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LLMRoutingPage() {
  const [matrix, setMatrix] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localCells, setLocalCells] = useState<any[]>([]);
  const [savedOk, setSavedOk] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>(FALLBACK_MODELS);
  const [selectedDomain, setSelectedDomain] = useState("all");
  const [bulkModel, setBulkModel] = useState("");
  const [bulkRisk, setBulkRisk] = useState("high");
  const [showPreview, setShowPreview] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [routingResult, modelsResult] = await Promise.allSettled([
        orchestrationApi.getLLMRouting(),
        api.listRegisteredModels(),
      ]);

      if (routingResult.status === "fulfilled") {
        setMatrix(routingResult.value);
        setLocalCells(routingResult.value.cells ?? []);
      } else {
        setError("Błąd połączenia z backendem routingu");
      }

      if (modelsResult.status === "fulfilled") {
        const ids = (modelsResult.value.models ?? []).map((m: any) => m.model_id);
        if (ids.length > 0) setAvailableModels(ids);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  // Derived
  const recTypes = Array.from(new Set(localCells.map((c: any) => c.recommendation_type)));
  const domainObj = DOMAINS.find((d) => d.key === selectedDomain);
  const filteredRecTypes =
    selectedDomain === "all" || !domainObj?.types
      ? recTypes
      : recTypes.filter((rt) => domainObj.types?.includes(rt));

  const isDirty = JSON.stringify(localCells) !== JSON.stringify(matrix?.cells ?? []);

  // Cell helpers
  const getCell = (recType: string, risk: string) =>
    localCells.find((c: any) => c.recommendation_type === recType && c.risk_level === risk);

  const updateCell = (recType: string, risk: string, model_id: string) => {
    setLocalCells((prev) =>
      prev.map((c) =>
        c.recommendation_type === recType && c.risk_level === risk
          ? { ...c, model_id, is_default: false }
          : c
      )
    );
  };

  const toggleCell = (recType: string, risk: string) => {
    setLocalCells((prev) =>
      prev.map((c) =>
        c.recommendation_type === recType && c.risk_level === risk
          ? { ...c, enabled: !c.enabled }
          : c
      )
    );
  };

  // Actions
  const handleSave = async () => {
    setSaving(true);
    setSavedOk(false);
    setSaveStatus(null);
    try {
      const data = await orchestrationApi.updateLLMRouting(localCells, matrix?.preset ?? "balanced");
      setMatrix(data);
      setLocalCells(data.cells ?? []);
      setSavedOk(true);
      setSaveStatus("Zmiany zapisane w backendzie.");
      setTimeout(() => {
        setSavedOk(false);
        setSaveStatus(null);
      }, 3000);
    } catch {
      setError("Zapis nieudany. SprawdŹ połączenie z backendem.");
    } finally {
      setSaving(false);
    }
  };

  const handlePreset = async (preset: "cost-saving" | "balanced" | "aggressive") => {
    setSaving(true);
    setSavedOk(false);
    setSaveStatus(null);
    try {
      const data = await orchestrationApi.applyLLMRoutingPreset(preset);
      setMatrix(data);
      setLocalCells(data.cells ?? []);
      const presetLabel = PRESETS.find((item) => item.key === preset)?.label ?? preset;
      setSavedOk(true);
      setSaveStatus(`Preset "${presetLabel}" zapisany w backendzie. Nie trzeba klikać "Zapisz zmiany".`);
      setTimeout(() => {
        setSavedOk(false);
        setSaveStatus(null);
      }, 4500);
    } catch {
      setError("Błąd zastosowania presetu");
    } finally {
      setSaving(false);
    }
  };

  const handleResetCell = async (recType: string, risk: string) => {
    try {
      const data = await orchestrationApi.resetLLMRoutingCell(recType, risk);
      setMatrix(data);
      setLocalCells(data.cells ?? []);
    } catch { /* ignore */ }
  };

  const handleBulkApply = () => {
    if (!bulkModel) return;
    setLocalCells((prev) =>
      prev.map((c) =>
        c.risk_level === bulkRisk ? { ...c, model_id: bulkModel, is_default: false } : c
      )
    );
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Network className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Matryca routingu LLM</h1>
            <p className="text-sm text-muted-foreground">
              Konfiguracja modelu per typ rekomendacji × poziom ryzyka
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Link href="/audit?source=orchestration">
            <Button variant="ghost" size="sm" className="h-7 text-[10px] gap-1">
              <ExternalLink className="w-3 h-3" />
              Dziennik audytu
            </Button>
          </Link>
          <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load} disabled={loading}>
            <RefreshCw className={cn("w-3 h-3 mr-1", loading && "animate-spin")} />
            Odśwież
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={cn(
              "h-7 text-[10px]",
              isDirty && "border-sylion-green/50 text-sylion-green hover:bg-sylion-green/10",
              savedOk && "border-sylion-green bg-sylion-green/10",
              !isDirty && !savedOk && "opacity-50"
            )}
            onClick={handleSave}
            disabled={saving || (!isDirty && !savedOk)}
          >
            {saving ? (
              <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            ) : savedOk ? (
              <Check className="w-3 h-3 mr-1" />
            ) : null}
            {savedOk ? "Zapisano" : "Zapisz zmiany"}
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Card className="p-3 border-sylion-red/20 bg-sylion-red/5 flex items-center gap-2">
          <WifiOff className="w-4 h-4 text-sylion-red shrink-0" />
          <span className="text-xs text-sylion-red">{error}</span>
          <Button variant="ghost" size="sm" className="ml-auto h-6 text-[10px]" onClick={() => setError(null)}>
            Zamknij
          </Button>
        </Card>
      )}

      {savedOk && saveStatus ? (
        <Card className="p-3 border-sylion-green/20 bg-sylion-green/5 flex items-center gap-2">
          <Check className="w-4 h-4 text-sylion-green shrink-0" />
          <span className="text-xs text-sylion-green">{saveStatus}</span>
        </Card>
      ) : null}

      {/* Presets + Preview toggle */}
      <Card className="p-4 border-sylion-border bg-card">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3 h-3" />
            Presety
            <HelpTip text="Gotowe konfiguracje matrycy routingu. Oszczędny = Haiku wszędzie (najtaniej, ale słabsza jakość przy krytycznych decyzjach). Zbalansowany = mix Haiku/Sonnet/Opus dobrany do ryzyka (default). Agresywny = Opus wszędzie (najwyższa jakość, ale 10-20x droższy). Wybór nadpisuje wszystkie komórki." />
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[10px] text-muted-foreground"
            onClick={() => setShowPreview((v) => !v)}
          >
            {showPreview ? <EyeOff className="w-3 h-3 mr-1" /> : <Eye className="w-3 h-3 mr-1" />}
            {showPreview ? "Ukryj podglad" : "Podglad routingu"}
          </Button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {PRESETS.map((p) => (
            <Button
              key={p.key}
              variant="outline"
              size="sm"
              className={cn(
                "h-7 text-[10px]",
                matrix?.preset === p.key && "border-primary/40 text-primary bg-primary/5"
              )}
              onClick={() => handlePreset(p.key)}
              disabled={saving}
            >
              {p.label}
              <span className="ml-1.5 text-[9px] text-muted-foreground">{p.desc}</span>
            </Button>
          ))}
        </div>
      </Card>

      {/* Preview panel */}
      {showPreview && (
        <Card className="p-4 border-sylion-border bg-card">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Eye className="w-3 h-3" />
            Podglad biezacej matrycy
            <HelpTip text="Read-only podgląd CO POJDZIE do każdej komórki po zapisie. Pokazuje przypisany model dla każdej pary (typ rekomendacji × poziom ryzyka). 'wylaczone' oznacza że dana kombinacja nie wygeneruje rekomendacji w ogóle." />
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="border-b border-sylion-border/40">
                  <th className="text-left px-3 py-1.5 text-muted-foreground font-medium w-44">Typ rekomendacji</th>
                  {RISK_LEVELS.map((r) => (
                    <th key={r} className="px-3 py-1.5 text-center">
                      <Badge variant="outline" className={cn("text-[9px]", RISK_META[r]?.color)}>
                        {RISK_META[r]?.label}
                      </Badge>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recTypes.map((rt) => (
                  <tr key={rt} className="border-b border-sylion-border/20">
                    <td className="px-3 py-1.5 text-muted-foreground font-mono">
                      {REC_TYPE_LABELS[rt] || rt}
                    </td>
                    {RISK_LEVELS.map((risk) => {
                      const cell = getCell(rt, risk);
                      return (
                        <td key={risk} className="px-3 py-1.5 text-center">
                          {cell?.enabled ? (
                            <span className="font-mono text-foreground">{cell.model_id}</span>
                          ) : (
                            <span className="text-muted-foreground/40">wylaczone</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Bulk actions */}
      <Card className="p-4 border-sylion-border bg-card">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Copy className="w-3 h-3" />
            Akcje zbiorcze
            <HelpTip text="Szybkie nadpisanie modelu dla całego rzędu (jeden poziom ryzyka × wszystkie typy rekomendacji). Przykład: 'wszystkie komórki critical = claude-opus-4-7'. Oszczędza przeklikiwania 8 selectów osobno." />
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[10px] text-muted-foreground"
            onClick={() => handlePreset("balanced")}
            disabled={saving}
          >
            <RotateCw className="w-3 h-3 mr-1" />
            Przywroc domyslne
          </Button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-[10px]">
            <span className="text-muted-foreground">
              Dla poziomu:
              <HelpTip text="Poziom ryzyka rekomendacji. Niskie = drobne sugestie, można Haiku. Krytyczne = decyzję wpływające na biznes lub bezpieczeństwo, Opus zalecany." />
            </span>
            <select
              value={bulkRisk}
              onChange={(e) => setBulkRisk(e.target.value)}
              className="px-2 py-1 rounded bg-background border border-border text-[10px] focus:outline-none focus:border-primary/40"
            >
              {RISK_LEVELS.map((r) => (
                <option key={r} value={r}>
                  {RISK_META[r]?.label || r}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5 text-[10px]">
            <span className="text-muted-foreground">
              Zastosuj model:
              <HelpTip text="LLM który zostanie przypisany do wszystkich komórek wybranego poziomu ryzyka. Ostrzeżenie: nadpisuje obecny wybór niezależnie czy był ręczny czy z presetu." />
            </span>
            <select
              value={bulkModel}
              onChange={(e) => setBulkModel(e.target.value)}
              className="px-2 py-1 rounded bg-background border border-border text-[10px] focus:outline-none focus:border-primary/40 min-w-[180px]"
            >
              <option value="">Wybierz model...</option>
              {availableModels.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-[10px]"
            onClick={handleBulkApply}
            disabled={!bulkModel}
          >
            Zastosuj do wszystkich wierszy
          </Button>
        </div>
      </Card>

      {/* Domain filter */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Filter className="w-3 h-3 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
            Filtr domeny projektu
            <HelpTip text="Pokazuje tylko typy rekomendacji które są istotne dla wybranej branży (np. dla Healthcare ukrywamy 'funding'). Nie zmienia konfiguracji — wpływa tylko na widoczność wierszy w tabeli niżej. 'Wszystkie' = pokazuje pełną matrycę." />
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {DOMAINS.map((d) => (
            <button
              key={d.key}
              onClick={() => setSelectedDomain(d.key)}
              className={cn(
                "px-2.5 py-1 text-[10px] rounded-full border transition-colors",
                selectedDomain === d.key
                  ? "border-primary/50 bg-primary/10 text-primary"
                  : "border-sylion-border text-muted-foreground hover:border-primary/30 hover:text-primary/70"
              )}
            >
              {d.label}
            </button>
          ))}
        </div>
        {selectedDomain !== "all" && domainObj?.types && (
          <p className="text-[10px] text-muted-foreground mt-1.5">
            Wyswietlono{" "}
            <span className="text-foreground font-medium">{filteredRecTypes.length}</span> z{" "}
            {recTypes.length} typow rekomendacji dla domeny{" "}
            <span className="text-foreground font-medium">{domainObj.label}</span>
          </p>
        )}
      </div>

      {/* Matrix table */}
      {loading ? (
        <Card className="p-10 bg-card border-sylion-border text-center">
          <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
          <p className="text-xs text-muted-foreground mt-3">Ładowanie matrycy routingu...</p>
        </Card>
      ) : (
        <Card className="border-sylion-border bg-card overflow-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-sylion-border">
                <th className="text-left px-4 py-3 text-muted-foreground font-medium w-52">
                  Typ rekomendacji
                </th>
                {RISK_LEVELS.map((r) => (
                  <th key={r} className="px-3 py-3 text-center min-w-[180px]">
                    <Badge variant="outline" className={cn("text-[9px]", RISK_META[r]?.color)}>
                      {RISK_META[r]?.label}
                    </Badge>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRecTypes.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-10 text-muted-foreground text-xs">
                    Brak danych routingu.{" "}
                    {selectedDomain !== "all"
                      ? "Zadne typy rekomendacji nie pasuja do wybranej domeny."
                      : "Kliknij Odśwież lub sprawdź połączenie z backendem."}
                  </td>
                </tr>
              ) : (
                filteredRecTypes.map((recType: any) => (
                  <tr
                    key={recType}
                    className="border-b border-sylion-border/40 hover:bg-muted/5 transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <div>
                        <span className="text-foreground font-medium">
                          {REC_TYPE_LABELS[recType] || recType}
                        </span>
                        <span className="block font-mono text-[9px] text-muted-foreground mt-0.5">
                          {recType}
                        </span>
                      </div>
                    </td>
                    {RISK_LEVELS.map((risk) => {
                      const cell = getCell(recType, risk);
                      return (
                        <td key={risk} className="px-2.5 py-2 text-center">
                          {cell ? (
                            <div className="flex flex-col items-stretch gap-1">
                              <select
                                className={cn(
                                  "px-2 py-1 rounded bg-background border text-[10px] focus:outline-none focus:border-primary/40 w-full transition-opacity",
                                  !cell.enabled && "opacity-40",
                                  !cell.is_default && cell.enabled && "border-primary/30"
                                )}
                                value={cell.model_id}
                                onChange={(e) => updateCell(recType, risk, e.target.value)}
                                disabled={!cell.enabled}
                              >
                                {availableModels.map((m) => (
                                  <option key={m} value={m}>
                                    {m}
                                  </option>
                                ))}
                                {!availableModels.includes(cell.model_id) && (
                                  <option value={cell.model_id}>{cell.model_id}</option>
                                )}
                              </select>
                              <div className="flex items-center gap-1 justify-center">
                                <button
                                  onClick={() => toggleCell(recType, risk)}
                                  className={cn(
                                    "text-[8px] px-1.5 py-0.5 rounded border transition-colors",
                                    cell.enabled
                                      ? "bg-sylion-green/10 text-sylion-green border-sylion-green/30"
                                      : "bg-muted/20 text-muted-foreground border-muted-foreground/20"
                                  )}
                                >
                                  {cell.enabled ? "Aktywny" : "Wyl"}
                                </button>
                                {!cell.is_default && (
                                  <button
                                    onClick={() => handleResetCell(recType, risk)}
                                    className="text-[8px] text-muted-foreground hover:text-sylion-amber p-0.5 rounded"
                                    title="Resetuj do domyslnego"
                                  >
                                    <RotateCcw className="w-2.5 h-2.5" />
                                  </button>
                                )}
                              </div>
                            </div>
                          ) : (
                            <span className="text-muted-foreground/40 text-[10px]">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-sylion-border/30">
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          {matrix?.updated_at && (
            <span>
              Ostatnia aktualizacja:{" "}
              <span className="text-foreground font-mono">{matrix.updated_at}</span>
            </span>
          )}
          {matrix?.preset && (
            <Badge variant="outline" className="text-[9px]">
              preset: {matrix.preset}
            </Badge>
          )}
          {isDirty && (
            <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber">
              niezapisane zmiany
            </Badge>
          )}
        </div>
        <Link
          href="/audit?source=orchestration"
          className="text-[10px] text-muted-foreground hover:text-primary flex items-center gap-1 transition-colors"
        >
          <ExternalLink className="w-3 h-3" />
          Dziennik audytu routingu
          <ChevronRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}
