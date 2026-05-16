"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";
import { orchestrationApi } from "@/lib/api/orchestration";
import { cn } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle2,
  Cloud,
  Download,
  Gauge,
  KeyRound,
  Loader2,
  Network,
  Plus,
  RefreshCw,
  Server,
  Shield,
  Sliders,
  Trash2,
  Users,
  XCircle,
} from "lucide-react";

type LoadState = {
  health: any;
  providers: any[];
  apiKeys: any[];
  registeredModels: any[];
  registryStats: any;
  hierarchies: any[];
  councilMembers: any[];
  ollama: any;
  budgets: any[];
  routing: any;
  providerCatalog: any;
};

const emptyState: LoadState = {
  health: null,
  providers: [],
  apiKeys: [],
  registeredModels: [],
  registryStats: {},
  hierarchies: [],
  councilMembers: [],
  ollama: { available: false, models: [], error: "", base_url: "http://localhost:11434" },
  budgets: [],
  routing: null,
  providerCatalog: null,
};

const REC_TYPE_LABELS: Record<string, string> = {
  cost_optimization: "Optymalizacja kosztów",
  scaling: "Skalowanie",
  security: "Bezpieczeństwo",
  subscription: "Subskrypcje",
  architecture: "Architektura",
  funding: "Finansowanie",
  onboarding: "Onboarding",
  maintenance: "Utrzymanie",
  critical_decision: "Decyzja krytyczna",
  draft_ui: "Szkic UI",
  audit_review: "Przegląd audytu",
  code_review: "Przegląd kodu",
};

const providerOptions = [
  "openai",
  "anthropic",
  "perplexity",
  "google",
  "zai",
  "openrouter",
  "moonshot",
  "deepseek",
  "xai",
  "mistral",
  "groq",
  "cohere",
  "fireworks",
  "together",
  "ollama",
  "lmstudio",
  "vllm",
  "llamacpp",
  "localai",
];

const recommendedLocalModels = ["qwen3-coder:30b", "gpt-oss:20b", "deepseek-r1:14b", "nomic-embed-text"];
const inputClass = "w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-primary/30";

function getSettled<T, F>(result: PromiseSettledResult<T>, fallback: F): T | F {
  return result.status === "fulfilled" ? result.value : fallback;
}

function withControlPlaneTimeout<T>(promise: Promise<T>, label: string, timeoutMs = 8_000): Promise<T> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      reject(new Error(`${label} timeout after ${timeoutMs}ms`));
    }, timeoutMs);

    promise
      .then((value) => resolve(value))
      .catch((error) => reject(error))
      .finally(() => window.clearTimeout(timeout));
  });
}

function parseConfig(value: unknown): Record<string, any> {
  if (!value || typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function providerClass(provider: string) {
  if (provider === "ollama" || provider === "localai") return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
  if (provider === "anthropic" || provider === "zai") return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
  return "border-primary/30 text-primary bg-primary/5";
}

function fmtBytes(value: number) {
  if (!value) return "";
  if (value > 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
  if (value > 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${value} B`;
}

function fmtUSD(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return `$${Number(value || 0).toFixed(2)}`;
}

function pct(spent: number, limit: number) {
  if (!limit || limit <= 0) return 0;
  return Math.min(100, Math.round((spent / limit) * 100));
}

const councilRankOrder: Record<string, number> = {
  primary: 1,
  senior_specialist: 2,
  support: 3,
  review_only: 4,
  validation_only: 5,
};

function buildCouncilHierarchyPreview(members: any[]) {
  const ordered = [...members].sort((a, b) => (
    (councilRankOrder[a.rank || "primary"] ?? 9) - (councilRankOrder[b.rank || "primary"] ?? 9)
    || Number(a.priority || 0) - Number(b.priority || 0)
    || Number(b.voting_weight || 1) - Number(a.voting_weight || 1)
    || String(a.member_id || "").localeCompare(String(b.member_id || ""))
  ));
  const totalWeight = ordered.reduce((sum, item) => sum + Math.max(0, Number(item.voting_weight || 0)), 0) || 1;
  return ordered.map((item, index) => ({
    level: index + 1,
    label: `R${index + 1}`,
    member_id: item.member_id,
    model_id: item.model_id,
    role: item.role,
    rank: item.rank || "primary",
    voting_weight: Number(item.voting_weight || 1),
    influence_percent: Math.round((Number(item.voting_weight || 1) / totalWeight) * 1000) / 10,
  }));
}

export default function AIModelsPage() {
  const [data, setData] = useState<LoadState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionStatus, setActionStatus] = useState("");
  const [testingProvider, setTestingProvider] = useState("");
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const [routingCells, setRoutingCells] = useState<any[]>([]);
  const [routingSaving, setRoutingSaving] = useState(false);
  const [ollamaPullModel, setOllamaPullModel] = useState("");
  const [ollamaPulling, setOllamaPulling] = useState(false);
  const [catalogView, setCatalogView] = useState<"provider" | "model" | "capability">("provider");
  const [catalogGoal, setCatalogGoal] = useState("mixed");

  const refresh = async (goalOverride = catalogGoal) => {
    setLoading(true);
    setError("");
    const [
      health,
      providers,
      keys,
      models,
      stats,
      hierarchies,
      members,
      ollama,
      budgets,
      routing,
      providerCatalog,
    ] = await Promise.allSettled([
      withControlPlaneTimeout(api.health(), "health", 5_000),
      withControlPlaneTimeout(api.listAIProviders(), "ai-providers", 8_000),
      withControlPlaneTimeout(api.listAPIKeys(), "api-keys", 8_000),
      withControlPlaneTimeout(api.listRegisteredModels(), "model-registry", 8_000),
      withControlPlaneTimeout(api.getModelRegistryStats(), "model-registry-stats", 8_000),
      withControlPlaneTimeout(api.listHierarchies(), "hierarchies", 8_000),
      withControlPlaneTimeout(api.listCouncilMemberConfigs(), "council-members", 8_000),
      withControlPlaneTimeout(api.listOllamaModels(), "ollama-models", 8_000),
      withControlPlaneTimeout(api.getModelBudgets(), "model-budgets", 8_000),
      withControlPlaneTimeout(orchestrationApi.getLLMRouting(), "llm-routing", 8_000),
      withControlPlaneTimeout(api.getProviderCatalog(goalOverride), "provider-catalog", 8_000),
    ]);

    setData({
      health: getSettled(health, null),
      providers: getSettled(providers, { providers: [] }).providers || [],
      apiKeys: getSettled(keys, { keys: [] }).keys || [],
      registeredModels: getSettled(models, { models: [] }).models || [],
      registryStats: getSettled(stats, {}),
      hierarchies: getSettled(hierarchies, { hierarchies: [] }).hierarchies || [],
      councilMembers: getSettled(members, { members: [] }).members || [],
      ollama: getSettled(ollama, emptyState.ollama),
      budgets: getSettled(budgets, { budgets: [] }).budgets || [],
      routing: getSettled(routing, null),
      providerCatalog: getSettled(providerCatalog, null),
    });

    const failed = [health, providers, keys, models, stats, hierarchies, members, ollama, budgets, providerCatalog]
      .filter((item) => item.status === "rejected").length;
    if (failed > 0) setError(`${failed} żądań control-plane nie powiodło się. Panel pokazuje częściowe dane.`);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (data.routing?.cells) setRoutingCells(data.routing.cells);
  }, [data.routing]);

  const testProvider = async (provider: string, model?: string) => {
    setTestingProvider(provider);
    setTestResults((prev) => ({ ...prev, [provider]: "Testuję..." }));
    try {
      const result = await api.testAIProvider(provider, { prompt: "Return exactly OK.", model, max_tokens: 4 });
      const text = result?.response?.text || "OK";
      setTestResults((prev) => ({
        ...prev,
        [provider]: `PASS ${result.latency_ms ?? 0}ms: ${String(text).slice(0, 120)}`,
      }));
    } catch (err: any) {
      setTestResults((prev) => ({ ...prev, [provider]: `FAIL: ${err.message}` }));
    } finally {
      setTestingProvider("");
    }
  };

  const backendLive = data.health?.status === "ok";
  const localModelNames = new Set((data.ollama?.models || []).map((item: any) => item.name));
  const registryIds = new Set(data.registeredModels.map((item) => item.model_id));
  const activeKeyProviders = new Set(data.apiKeys.filter((key) => key.is_active).map((key) => key.provider));
  const budgetByModel = new Map(data.budgets.map((budget) => [budget.model_id, budget]));
  const activeHierarchy = data.hierarchies.find((hierarchy) => hierarchy.is_active);
  const defaultHierarchyLevels = activeHierarchy?.levels?.length
    ? activeHierarchy.levels
    : buildCouncilHierarchyPreview(data.councilMembers);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Brain className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight inline-flex items-center">
              Modele AI — Centrum Sterowania
              <HelpTip text="Centralne miejsce zarządzania wszystkimi modelami LLM AEIS: rejestr modeli, klucze API, role/rangi rady, wagi głosowania, budżety per-model i testy runtime. Każdy produkcyjny przepływ pracy AEIS musi przejść przez ten panel zanim rada modeli zacznie pracować." />
            </h1>
            <p className="text-sm text-muted-foreground">
              Modele lokalne i zewnętrzne, klucze API, rangi rady, wagi głosowania, budżety, testy runtime.
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refresh()} disabled={loading}>
          {loading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
          Odśwież
        </Button>
      </div>

      {error && (
        <Card className="p-3 bg-sylion-amber/5 border-sylion-amber/20 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-sylion-amber" />
          <p className="text-xs text-sylion-amber">{error}</p>
        </Card>
      )}

      {actionStatus && (
        <Card className="p-3 bg-primary/5 border-primary/20 flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          <p className="text-xs text-primary">{actionStatus}</p>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <MetricCard
          label="Backend"
          help="Status połączenia z backendem AEIS (FastAPI control-plane). Online = wszystkie endpointy odpowiadają i panel pokazuje dane na żywo; Offline = panel wyświetla puste lub przeterminowane dane do czasu przywrócenia łączności."
          value={backendLive ? "Online" : "Offline"}
          tone={backendLive ? "green" : "red"}
          icon={Activity}
        />
        <MetricCard
          label="Zarejestrowane modele"
          help="Liczba modeli LLM zarejestrowanych w rejestrze AEIS (z rolą + rangą + wagą głosowania). Pusty rejestr = rada nie może działać; konieczne dodanie min. 3 modeli (R5 Architect + R3 Senior + R1 Associate)."
          value={String(data.registeredModels.length)}
          tone="primary"
          icon={Brain}
        />
        <MetricCard
          label="Aktywni dostawcy API"
          help="Liczba dostawców LLM z aktywnym kluczem API w KeyVault (Anthropic, OpenAI, Perplexity, Google, ZAI, Mistral...). Dostawca bez aktywnego klucza nie może być wybrany przez routera ani radę. Konfiguracja w zakładce 'Dostawcy i klucze'."
          value={String(activeKeyProviders.size)}
          tone="amber"
          icon={KeyRound}
        />
        <MetricCard
          label="Lokalna Ollama"
          help="Status lokalnego runtime Ollama (offline/online + lista zainstalowanych modeli). Online umożliwia całkowicie offline-prywatne wnioskowanie; offline = system spadnie na cloudowych dostawców."
          value={data.ollama?.available ? `${data.ollama.models?.length || 0} modeli` : "Offline"}
          tone={data.ollama?.available ? "green" : "red"}
          icon={Server}
        />
      </div>

      <Tabs defaultValue="catalog" className="space-y-4">
        <TabsList className="bg-muted/20 flex flex-wrap h-auto">
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="overview" className="text-xs">
              Przegląd
            </TabsTrigger>
            <HelpTip text="Zbiorcze KPI: gotowość dostawców LLM + powiązania rady (członkowie, hierarchie, wpisy budżetowe, migawki rejestru). Pierwsze miejsce do sprawdźenia stanu całego control-plane." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="catalog" className="text-xs">
              Katalog providerów
            </TabsTrigger>
            <HelpTip text="Faza 2: trzy widoki katalogu provider -> endpoint -> model, model-first i capability-first, z gap detection, acquisition advisor, local install suggestions oraz acceptance test." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="providers" className="text-xs">
              Dostawcy i klucze
            </TabsTrigger>
            <HelpTip text="Lista wszystkich obsługiwanych dostawców LLM + zarządzanie kluczami API w KeyVault. Tu dodajesz/aktywujesz klucz produkcyjny zanim model będzie mógł być zarejestrowany." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="registry" className="text-xs">
              Rejestr modeli
            </TabsTrigger>
            <HelpTip text="Centralny rejestr modeli LLM: model_id, provider, rola, ranga, waga głosowania, runtime, fallback. Bez wpisu w tym rejestrze model nie istnieje dla rady ani routera." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="budget-access" className="text-xs">
              Budżet i dostęp
            </TabsTrigger>
            <HelpTip text="Per-model widok: dzienny/miesięczny budżet USD, profil językowy, głębokość intelligence, polityka access (full/limited/gated/read_only) i polityka Human Gate. Domyślnie 'gated' z 'ask_for_risky_changes'." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="council" className="text-xs">
              Rada modeli
            </TabsTrigger>
            <HelpTip text="Konfiguracja członków rady: model_id, rola (planner/architect/critic/verifier...), ranga (R1-R5 + senior_specialist) i waga głosowania. Bez 3+ członków rada nie może debatować." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="ollama" className="text-xs">
              Lokalne Ollama
            </TabsTrigger>
            <HelpTip text="Lokalny runtime Ollama: lista zainstalowanych modeli, pobieranie nowych, rejestracja jako lokalny worker w radzie. Modele lokalne dają zerowy koszt inference + pełną prywatność danych." />
          </span>
          <span role="presentation" className="inline-flex items-center gap-1">
            <TabsTrigger value="routing-defaults" className="text-xs">
              Preferencje domyślne
            </TabsTrigger>
            <HelpTip text="Matryca routingu: domyślny model per typ zadania (security, cost, architecture...) × poziom ryzyka (low/medium/high/critical). Zapisuje preset wykorzystywany przez LLM Judge przy automatycznym wyborze modelu." />
          </span>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Card className="p-4 bg-card border-sylion-border">
              <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Cloud className="w-4 h-4 text-primary" /> Gotowość dostawców
                <HelpTip text="Lista wszystkich obsługiwanych dostawców LLM z statusem klucza API. 'GOTOWY' = klucz aktywny i przetestówany; 'BRAK KLUCZA' = wymaga konfiguracji w zakładce 'Dostawcy i klucze'." />
                </h2>
              <div className="space-y-2">
                {data.providers.map((provider) => (
                  <ProviderRow
                    key={provider.provider}
                    provider={provider}
                    storedActive={activeKeyProviders.has(provider.provider)}
                    testing={testingProvider === provider.provider}
                    testResult={testResults[provider.provider]}
                    onTest={() => testProvider(provider.provider, provider.default_model)}
                  />
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-card border-sylion-border">
              <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4 text-sylion-amber" /> Powiązania rady
                <HelpTip text="Liczniki obiektów rady: członkowie (modele z przypisaną rolą), hierarchie (struktury R1-R5), wpisy budżetowe (limity per-model), migawki rejestru (audit trail zmian)." />
              </h2>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <StatusBlock
                  label="Członkowie rady"
                  value={data.councilMembers.length}
                  help="Liczba modeli skonfigurowanych jako członkowie rady (z rolą + rangą + wagą głosu). Minimum 3 członków wymagane dla pełnej debaty (R5 Architect + R3 Senior + R1 Associate)."
                />
                <StatusBlock
                  label="Hierarchie"
                  value={data.hierarchies.length}
                  help="Liczba zdefiniowanych hierarchii rady — struktur R1-R5 określających kto może blokować, eskalować i podpisywać decyzję. Tylko jedna hierarchia jest aktywna naraz."
                />
                <StatusBlock
                  label="Wpisy budżetów"
                  value={data.budgets.length}
                  help="Liczba zdefiniowanych budżetów per-model w rejestrze. Każdy budżet zawiera limit dzienny/miesięczny + próg alertu. Bez wpisów — modele mogą wydawać bez ograniczeń."
                />
                <StatusBlock
                  label="Migawki rejestru"
                  value={data.registryStats?.total_performance_snapshots || 0}
                  help="Suma snapshotów performance zapisanych w rejestrze (latency, cost, jakość odpowiedzi, success rate). Stanowi audit trail dla decyzji D3+ i pomaga w analizie cost optymalizacji."
                />
              </div>
              <div className="mt-4 rounded-lg border border-sylion-border p-3 bg-secondary/10">
                <p className="text-xs text-muted-foreground">
                  Produkcyjne AEIS musi używać tego rejestru przed pracą rady: rola modelu, ranga, waga głosowania,
                  dostępność klucza, runtime lokalny/zewnętrzny, budżet i polityka Human Gate muszą być widoczne dla operatora.
                </p>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="catalog">
          <ProviderCatalogPanel
            catalog={data.providerCatalog}
            view={catalogView}
            goal={catalogGoal}
            loading={loading}
            onViewChange={setCatalogView}
            onGoalChange={async (nextGoal) => {
              setCatalogGoal(nextGoal);
              await refresh(nextGoal);
            }}
            onRefreshLocal={async () => {
              await api.refreshProviderCatalogLocal();
              setActionStatus("Lokalne runtime providerów zostaćy przeskanowane ponownie.");
              await refresh();
            }}
          />
        </TabsContent>

        <TabsContent value="providers">
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-4">
            <Card className="p-4 bg-card border-sylion-border">
              <h2 className="text-sm font-semibold mb-3 inline-flex items-center">
                Dostawcy zewnętrzni i lokalni
                <HelpTip text="Lista wszystkich obsługiwanych dostawców LLM (cloud + lokalni). Zawiera default model, env var dla klucza i status gotowości. Klikaj 'Test' aby sprawdźić, czy klucz faktycznie działa." />
              </h2>
              <div className="space-y-2">
                {data.providers.map((provider) => (
                  <ProviderRow
                    key={provider.provider}
                    provider={provider}
                    storedActive={activeKeyProviders.has(provider.provider)}
                    testing={testingProvider === provider.provider}
                    testResult={testResults[provider.provider]}
                    onTest={() => testProvider(provider.provider, provider.default_model)}
                  />
                ))}
              </div>
            </Card>
            <KeyForm
              onSaved={async () => {
                setActionStatus("Klucz API zapisany w KeyVault. Wartość surowa nie jest zwracana do UI.");
                await refresh();
              }}
            />
          </div>

          <Card className="p-4 bg-card border-sylion-border mt-4">
            <h2 className="text-sm font-semibold mb-3 inline-flex items-center">
              Wpisy w KeyVault
              <HelpTip text="Wszystkie klucze API zapisane w bezpiecznym KeyVault backendu (zaszyfrowane na dysku). UI pokazuje tylko zamaskowany podgląd. Można aktywować/dezaktywować klucz bez usuwania go." />
            </h2>
            {data.apiKeys.length === 0 ? (
              <EmptyState text="Brak kluczy API w KeyVault. Klucze ze zmiennych środowiskowych mogą być nadal dostępne." />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                {data.apiKeys.map((key) => (
                  <div key={key.key_id} className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant="outline" className={cn("text-[9px]", providerClass(key.provider))}>{key.provider}</Badge>
                      <Badge variant="outline" className={cn("text-[9px]", key.is_active ? "border-sylion-green/30 text-sylion-green" : "border-muted-foreground/30 text-muted-foreground")}>
                        {key.is_active ? "AKTYWNY" : "NIEAKTYWNY"}
                      </Badge>
                    </div>
                    <p className="text-xs font-medium mt-2">{key.display_name || key.key_id}</p>
                    <p className="text-[10px] font-mono text-muted-foreground mt-1">{key.masked_key}</p>
                    {!key.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-[10px] mt-2 px-2"
                        onClick={async () => {
                          await api.activateAPIKey(key.key_id);
                          setActionStatus(`Aktywowano klucz API dostawcy ${key.provider}.`);
                          await refresh();
                        }}
                      >
                        <CheckCircle2 className="w-3 h-3 mr-1" /> Aktywuj
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="registry">
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_430px] gap-4">
            <Card className="p-4 bg-card border-sylion-border">
              <h2 className="text-sm font-semibold mb-3 inline-flex items-center">
                Zarejestrowane modele
                <HelpTip text="Lista modeli LLM aktywnych w rejestrze AEIS (tabela `registered_models`, is_active=1). Każdy wpis ma model_id, providera i config_json z rolą/rangą/wagą głosu. Tylko modele z tej listy mogą trafić do rady i routera." />
              </h2>
              {data.registeredModels.length === 0 ? (
                <EmptyState text={
                  data.ollama?.available && (data.ollama?.models || []).length > 0
                    ? `Brak zarejestrowanych modeli w rejestrze AEIS, choć backend i Ollama są online (${data.ollama.models.length} lokalnych modeli wykrytych). Endpoint /api/v1/model-registry/models zwraca pustą listę — modele Ollama nie są automatycznie rejestrowane. Przejdź do zakładki "Lokalne Ollama" i kliknij "Register" przy wybranym modelu, albo dodaj model zewnętrzny formularzem po prawej.`
                    : `Brak zarejestrowanych modeli. Zarejestruj pierwszy formularzem po prawej, albo uruchom auto-discovery z zakładki "Lokalne Ollama" jeśli runtime Ollama jest aktywny.`
                } />
              ) : (
                <div className="space-y-2">
                  {data.registeredModels.map((model) => {
                    const cfg = parseConfig(model.config_json);
                    return (
                      <div key={model.model_id} className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-semibold truncate">{model.display_name || model.model_id}</p>
                              <Badge variant="outline" className={cn("text-[9px]", providerClass(model.provider))}>{model.provider}</Badge>
                              {cfg.rank && <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">rank: {cfg.rank}</Badge>}
                              {cfg.role && <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber">{cfg.role}</Badge>}
                            </div>
                            <p className="text-[10px] font-mono text-muted-foreground mt-1">{model.model_id}</p>
                            <div className="flex flex-wrap gap-2 mt-2 text-[10px] text-muted-foreground">
                              {cfg.voting_weight && <span>weight {cfg.voting_weight}</span>}
                              {cfg.context_window && <span>context {cfg.context_window}</span>}
                              {cfg.runtime_type && <span>{cfg.runtime_type}</span>}
                              {cfg.fallback_model_id && <span>fallback {cfg.fallback_model_id}</span>}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-[10px] text-sylion-red/70"
                            onClick={async () => {
                              await api.deregisterModel(model.model_id);
                              setActionStatus(`Model ${model.model_id} został usunięty z rejestru.`);
                              await refresh();
                            }}
                          >
                            <Trash2 className="w-3 h-3 mr-1" /> Usuń
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
            <ModelForm
              onSaved={async () => {
                setActionStatus("Model zarejestrowany z metadanymi rola/ranga/waga.");
                await refresh();
              }}
            />
          </div>
        </TabsContent>

        <TabsContent value="budget-access">
          <Card className="p-4 bg-card border-sylion-border">
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <Gauge className="w-4 h-4 text-sylion-amber" /> Budżety modeli i polityki dostępu
                  <HelpTip text="Per-model widok kosztów (dzienny/miesięczny limit USD), profilu językowego, głębokości intelligence, polityki access (full/limited/gated/read_only) i polityki Human Gate. Kluczowe dla cost-control i compliance." />
                </h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Jeden operatorski widok kosztów, języka, głębokości intelligence, dostępu runtime i wymagań Human Gate per model.
                </p>
              </div>
              <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">
                {data.registeredModels.length} skonfigurowanych
              </Badge>
            </div>

            {data.registeredModels.length === 0 ? (
              <EmptyState text="Brak zarejestrowanych modeli. Najpierw zarejestruj modele w zakładce 'Rejestr modeli' aby skonfigurować budżet i polityki dostępu." />
            ) : (
              <div className="space-y-3">
                {data.registeredModels.map((model) => {
                  const cfg = parseConfig(model.config_json);
                  const budget = budgetByModel.get(model.model_id) || {};
                  const dailyPct = pct(Number(budget.spent_today || 0), Number(budget.daily_limit || 0));
                  const monthlyPct = pct(Number(budget.spent_this_month || 0), Number(budget.monthly_limit || 0));
                  const access = cfg.access_level || "gated";
                  const approval = cfg.approval_policy || "ask_for_risky_changes";
                  return (
                    <div key={model.model_id} className="rounded-xl border border-sylion-border bg-secondary/10 p-4">
                      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-sm font-semibold">{model.display_name || model.model_id}</p>
                            <Badge variant="outline" className={cn("text-[9px]", providerClass(model.provider))}>{model.provider}</Badge>
                            <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">{cfg.intelligence_depth || "balanced"}</Badge>
                            <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green">{cfg.language_profile || "multilingual"}</Badge>
                            <Badge variant="outline" className={cn("text-[9px]", access === "full" ? "border-sylion-red/30 text-sylion-red" : access === "limited" ? "border-sylion-amber/30 text-sylion-amber" : "border-primary/30 text-primary")}>
                              access: {access}
                            </Badge>
                          </div>
                          <p className="text-[10px] font-mono text-muted-foreground mt-1">{model.model_id}</p>
                          <p className="text-[10px] text-muted-foreground mt-2">
                            Polityka zatwierdzania: <span className="text-foreground">{approval}</span>
                          </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3 min-w-[280px]">
                          <BudgetMini label="Dzienny" spent={Number(budget.spent_today || 0)} limit={Number(budget.daily_limit || 0)} percent={dailyPct} />
                          <BudgetMini label="Miesięczny" spent={Number(budget.spent_this_month || 0)} limit={Number(budget.monthly_limit || 0)} percent={monthlyPct} />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-[10px]">
                        <StatusPill label="Rola" value={cfg.role || "unset"} />
                        <StatusPill label="Ranga" value={cfg.rank || "unset"} />
                        <StatusPill label="Waga głosu" value={String(cfg.voting_weight ?? 1)} />
                        <StatusPill label="Koszt / 1K" value={cfg.cost_per_1k_tokens_usd ? `$${cfg.cost_per_1k_tokens_usd}` : "$0"} />
                        <StatusPill label="Fallback" value={cfg.fallback_model_id || "none"} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="council">
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_430px] gap-4">
            <Card className="p-4 bg-card border-sylion-border">
              <div className="flex items-start justify-between gap-3 mb-3">
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <Users className="w-4 h-4 text-sylion-amber" /> Członkowie rady
                  <HelpTip text="Aktywni członkowie rady modeli z przypisaną rolą (planner/architect/critic/...), rangą (R1-R5) i wagą głosowania. Bez 3+ członków rada nie może debatować — AEIS nie udowodni ranged model deliberation." />
                </h2>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs"
                  onClick={async () => {
                    const result = await api.autoArrangeModelCouncil({ force: false, max_members: 7 });
                    setActionStatus(`Rada ułożona automatycznie: ${result.summary?.member_count || 0} członków, ${result.summary?.configured_count || 0} nowych.`);
                    await refresh();
                  }}
                >
                  <Sliders className="w-3.5 h-3.5 mr-1.5" /> Ułóż automatycznie
                </Button>
              </div>
              {data.councilMembers.length === 0 ? (
                <EmptyState text="Brak skonfigurowanych członków rady. AEIS nie może na razie udowodnić ranged model deliberation." />
              ) : (
                <div className="space-y-2">
                  {data.councilMembers.map((member) => (
                    <CouncilMemberCard
                      key={member.member_id}
                      member={member}
                      models={data.registeredModels}
                      onSaved={async () => {
                        setActionStatus(`Zaktualizowano wpływ członka ${member.member_id}.`);
                        await refresh();
                      }}
                    />
                  ))}
                </div>
              )}
            </Card>
            <CouncilForm
              models={data.registeredModels}
              onSaved={async () => {
                setActionStatus("Członek rady skonfigurowany z rangą i wagą głosowania.");
                await refresh();
              }}
            />
          </div>

          <Card className="p-4 bg-card border-sylion-border mt-4">
            <div className="flex items-start justify-between gap-3 mb-3">
              <h2 className="text-sm font-semibold inline-flex items-center">
                Hierarchie modeli
                <HelpTip text="Zdefiniowane hierarchie rady (struktury R1-R5) określające kto może blokować, eskalować i podpisywać decyzję D3+. Panel pokazuje aktywną hierarchię albo domyślny układ wynikający z rang, priorytetów i wag aktualnych członków." />
              </h2>
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                disabled={data.councilMembers.length === 0}
                onClick={async () => {
                  const result = await api.rebuildModelCouncilHierarchy();
                  setActionStatus(`Hierarchia przebudowana: ${(result.hierarchy?.levels || []).length} poziomów.`);
                  await refresh();
                }}
              >
                <Sliders className="w-3.5 h-3.5 mr-1.5" /> Przebuduj z członków
              </Button>
            </div>
            {defaultHierarchyLevels.length === 0 ? (
              <EmptyState text="Brak skonfigurowanej hierarchii. Dodaj członków rady albo użyj automatycznego ułożenia." />
            ) : (
              <div className="space-y-2">
                <div className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold">{activeHierarchy?.name || "Domyślna hierarchia z aktualnych członków"}</p>
                    <Badge variant="outline" className={cn("text-[9px]", activeHierarchy ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
                      {activeHierarchy ? "AKTYWNA" : "PREVIEW"}
                    </Badge>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1">{defaultHierarchyLevels.length} poziomów routingu według rangi, priorytetu i wagi wpływu</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2 mt-3">
                    {defaultHierarchyLevels.map((level: any) => (
                      <div key={`${level.member_id || level.model_id}-${level.level}`} className="rounded-lg border border-sylion-border bg-card/40 p-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-semibold">{level.label || `R${level.level}`}</span>
                          <Badge variant="outline" className="text-[8px] border-sylion-green/30 text-sylion-green">
                            {level.influence_percent ?? 0}%
                          </Badge>
                        </div>
                        <p className="text-[9px] font-mono text-muted-foreground mt-1 truncate">{level.model_id}</p>
                        <p className="text-[9px] text-muted-foreground">{level.role} | {level.rank} | w {level.voting_weight}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {data.hierarchies.filter((hierarchy) => !hierarchy.is_active).map((hierarchy) => (
                  <div key={hierarchy.hierarchy_id} className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold">{hierarchy.name}</p>
                      <Badge variant="outline" className="text-[9px] border-muted-foreground/30 text-muted-foreground">WERSJA</Badge>
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1">{(hierarchy.levels || []).length} poziomów historycznych</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="ollama">
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
            <Card className="p-4 bg-card border-sylion-border">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <h2 className="text-sm font-semibold flex items-center gap-2">
                    <Server className="w-4 h-4 text-sylion-green" /> Lokalny runtime Ollama
                    <HelpTip text="Endpoint i status lokalnego serwera Ollama (domyślnie http://localhost:11434). DOSTĘPNY = backend wykrył runtime; OFFLINE = uruchom 'ollama serve' lokalnie. Modele lokalne pozwalają na zerowy koszt + pełną prywatność." />
                  </h2>
                  <p className="text-xs text-muted-foreground mt-1">{data.ollama?.base_url || "http://localhost:11434"}</p>
                </div>
                <Badge variant="outline" className={cn("text-[9px]", data.ollama?.available ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                  {data.ollama?.available ? "DOSTĘPNY" : "OFFLINE"}
                </Badge>
              </div>

              {!data.ollama?.available && (
                <Card className="p-3 bg-sylion-red/5 border-sylion-red/20 mb-4">
                  <p className="text-xs text-sylion-red">Ollama nie odpowiada. Uruchom serwer lokalnie i wykonaj `ollama list` aby sprawdźić zainstalowane modele.</p>
                  {data.ollama?.error && <p className="text-[10px] text-muted-foreground mt-2">{data.ollama.error}</p>}
                </Card>
              )}

              {(data.ollama?.models || []).length === 0 ? (
                <EmptyState text="Nie wykryto lokalnych modeli Ollama." />
              ) : (
                <div className="space-y-2">
                  {data.ollama.models.map((model: any) => (
                    <div key={model.name} className="rounded-lg border border-sylion-border p-3 bg-secondary/10 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold font-mono">{model.name}</p>
                        <p className="text-[10px] text-muted-foreground">{fmtBytes(model.size)} {model.details?.parameter_size ? `| ${model.details.parameter_size}` : ""}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" className="h-7 text-[10px]" onClick={() => testProvider("ollama", model.name)} disabled={testingProvider === "ollama"}>
                          {testingProvider === "ollama" ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle2 className="w-3 h-3 mr-1" />}
                          Test
                        </Button>
                        {!registryIds.has(model.name) && (
                          <Button
                            size="sm"
                            className="h-7 text-[10px]"
                            onClick={async () => {
                              await api.registerModel({
                                model_id: model.name,
                                provider: "ollama",
                                display_name: model.name,
                                config_json: JSON.stringify({
                                  runtime_type: "local",
                                  role: "local_worker",
                                  rank: "support",
                                  voting_weight: 0.7,
                                  base_url: data.ollama?.base_url,
                                }),
                              });
                              setActionStatus(`Model lokalny ${model.name} zarejestrowany.`);
                              await refresh();
                            }}
                          >
                            <Plus className="w-3 h-3 mr-1" /> Zarejestruj
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {testResults.ollama && <p className="text-[10px] text-muted-foreground mt-3">{testResults.ollama}</p>}
            </Card>

            <div className="space-y-4">
              <Card className="p-4 bg-card border-sylion-border">
                <h2 className="text-sm font-semibold mb-3 inline-flex items-center">
                  Zalecany lokalny council
                  <HelpTip text="Rekomendowany zestaw modeli Ollama do prywatnego, offline-friendly council: qwen3-coder do kodu, gpt-oss do dyskusji, deepseek-r1 do reasoning, nomic-embed-text do embedingów. Pozwala uruchomić AEIS bez kluczy zewnętrznych." />
                </h2>
                <div className="space-y-2">
                  {recommendedLocalModels.map((name) => (
                    <div key={name} className="flex items-center justify-between rounded-lg border border-sylion-border p-2 bg-secondary/10">
                      <span className="text-[11px] font-mono">{name}</span>
                      {localModelNames.has(name) ? (
                        <CheckCircle2 className="w-4 h-4 text-sylion-green" />
                      ) : (
                        <XCircle className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-muted-foreground mt-3">
                  Lokalne modele uczą się przez pamięć AEIS, historię ocen, użycie skills i opcjonalne kolejki LoRA/fine-tuning. Sam inference nie trenuje modelu.
                </p>
              </Card>

              <Card className="p-4 bg-card border-sylion-border">
                <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Download className="w-4 h-4 text-primary" /> Pobierz nowy model
                  <HelpTip text="Wysyła zada?ie 'ollama pull' przez backend do lokalnego runtime. Pobiera wagi modelu (od kilkuset MB do 100+ GB). Po zakończeniu pobierania modelu pojawi się on na liście Ollama models i będzie można go zarejestrować w radzie." />
                </h2>
                <div className="space-y-3">
                  <Field label="Nazwa modelu" help="Identyfikator modelu w stylu Ollama, np. 'qwen3-coder:30b' lub 'llama3.2:3b'. Pełna lista: https://ollama.com/library">
                    <input
                      value={ollamaPullModel}
                      onChange={(e) => setOllamaPullModel(e.target.value)}
                      placeholder="np. qwen3-coder:30b"
                      className={`${inputClass} font-mono`}
                    />
                  </Field>
                  <p className="text-[10px] text-muted-foreground">
                    Wyślij zada?ie ściągnięcia modelu przez backend. Wymaga działającego Ollama na serwerze.
                  </p>
                  <Button
                    size="sm"
                    className="w-full"
                    onClick={async () => {
                      if (!ollamaPullModel.trim()) return;
                      setOllamaPulling(true);
                      try {
                        await api.pullOllamaModel(ollamaPullModel.trim());
                        setActionStatus(`Zadanie pobierania modelu "${ollamaPullModel}" wysłane do backendu.`);
                        setOllamaPullModel("");
                      } catch (err: any) {
                        setActionStatus(`Błąd pobierania: ${err.message}`);
                      } finally {
                        setOllamaPulling(false);
                      }
                    }}
                    disabled={ollamaPulling || !ollamaPullModel.trim()}
                  >
                    {ollamaPulling ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Download className="w-3.5 h-3.5 mr-1.5" />}
                    Pobierz model
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="routing-defaults">
          <RoutingDefaultsTab
            cells={routingCells}
            registeredModels={data.registeredModels}
            preset={data.routing?.preset ?? "balanced"}
            saving={routingSaving}
            onCellChange={(recType, risk, modelId) => {
              setRoutingCells((prev) =>
                prev.map((c) =>
                  c.recommendation_type === recType && c.risk_level === risk
                    ? { ...c, model_id: modelId, is_default: false }
                    : c
                )
              );
            }}
            onSave={async () => {
              setRoutingSaving(true);
              try {
                const updated = await orchestrationApi.updateLLMRouting(
                  routingCells,
                  data.routing?.preset ?? "balanced"
                );
                setRoutingCells(updated.cells ?? routingCells);
                setActionStatus("Preferencje routingu zapisane.");
              } catch (err: any) {
                setActionStatus(`Błąd zapisu routingu: ${err.message}`);
              } finally {
                setRoutingSaving(false);
              }
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MetricCard({ label, value, tone, icon: Icon, help }: { label: string; value: string; tone: "green" | "red" | "amber" | "primary"; icon: any; help?: string }) {
  const toneClass = {
    green: "text-sylion-green bg-sylion-green/10 border-sylion-green/20",
    red: "text-sylion-red bg-sylion-red/10 border-sylion-red/20",
    amber: "text-sylion-amber bg-sylion-amber/10 border-sylion-amber/20",
    primary: "text-primary bg-primary/10 border-primary/20",
  }[tone];

  return (
    <Card className="p-4 bg-card border-sylion-border">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center">
            {label}
            {help && <HelpTip text={help} />}
          </p>
          <p className="text-lg font-semibold mt-1">{value}</p>
        </div>
        <div className={cn("w-8 h-8 rounded-lg border flex items-center justify-center", toneClass)}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
    </Card>
  );
}

function ProviderRow({ provider, storedActive, testing, testResult, onTest }: {
  provider: any;
  storedActive: boolean;
  testing: boolean;
  testResult?: string;
  onTest: () => void;
}) {
  const isLocal = provider.locality === "local";
  const ready = isLocal ? Boolean(provider.runtime_reachable ?? provider.ready) : Boolean(provider.key_available);
  const testable = isLocal || Boolean(provider.key_available);
  const statusLabel = ready ? "GOTOWY" : isLocal ? "RUNTIME OFFLINE" : "BRAK KLUCZA";
  return (
    <div className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={cn("text-[9px]", providerClass(provider.provider))}>{provider.provider}</Badge>
            <Badge variant="outline" className={cn("text-[9px]", ready ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
              {statusLabel}
            </Badge>
            {storedActive && <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">KEYVAULT AKTYWNY</Badge>}
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">
            default {provider.default_model || "-"} {provider.env_var ? `| env ${provider.env_var}` : "| lokalny runtime"}
          </p>
          {provider.key_preview && <p className="text-[10px] font-mono text-muted-foreground">{provider.key_preview}</p>}
          {provider.base_url && <p className="text-[10px] font-mono text-muted-foreground">{provider.base_url}</p>}
        </div>
        <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={onTest} disabled={testing || !testable}>
          {testing ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle2 className="w-3 h-3 mr-1" />}
          Test
        </Button>
      </div>
      {testResult && <p className="text-[10px] text-muted-foreground mt-2 break-words">{testResult}</p>}
    </div>
  );
}

function StatusBlock({ label, value, help }: { label: string; value: number; help?: string }) {
  return (
    <div className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center">
        {label}
        {help && <HelpTip text={help} />}
      </p>
      <p className="text-lg font-mono font-semibold mt-1">{value}</p>
    </div>
  );
}

function BudgetMini({ label, spent, limit, percent }: { label: string; spent: number; limit: number; percent: number }) {
  const color = percent >= 90 ? "bg-sylion-red" : percent >= 70 ? "bg-sylion-amber" : "bg-sylion-green";
  return (
    <div className="rounded-lg border border-sylion-border bg-card/40 p-2">
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">{limit > 0 ? `${percent}%` : "bez limitu"}</span>
      </div>
      <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden mt-1.5">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${limit > 0 ? percent : 0}%` }} />
      </div>
      <p className="text-[10px] text-muted-foreground mt-1">
        {fmtUSD(spent)} / {limit > 0 ? fmtUSD(limit) : "brak limitu"}
      </p>
    </div>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-sylion-border bg-card/40 px-2 py-1.5">
      <span className="text-muted-foreground">{label}: </span>
      <span className="text-foreground font-mono">{value}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="p-8 text-center">
      <AlertTriangle className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
      <p className="text-xs text-muted-foreground">{text}</p>
    </div>
  );
}

function ProviderCatalogPanel({
  catalog,
  view,
  goal,
  loading,
  onViewChange,
  onGoalChange,
  onRefreshLocal,
}: {
  catalog: any;
  view: "provider" | "model" | "capability";
  goal: string;
  loading: boolean;
  onViewChange: (view: "provider" | "model" | "capability") => void;
  onGoalChange: (goal: string) => Promise<void>;
  onRefreshLocal: () => Promise<void>;
}) {
  if (!catalog) {
    return (
      <Card className="p-6 bg-card border-sylion-border">
        <EmptyState text={loading ? "Ładowanie katalogu providerów..." : "Backend nie zwróci? snapshotu Provider Catalog."} />
      </Card>
    );
  }

  const providers = catalog.providers || [];
  const models = catalog.models || [];
  const configuredModels = models.filter((model: any) => model.configured);
  const matrix = catalog.capability_matrix || [];
  const acceptance = catalog.acceptance || {};
  const covered = matrix.filter((row: any) => row.model_count > 0).length;
  const coveragePct = matrix.length ? Math.round((covered / matrix.length) * 100) : 0;
  const configuredProviders = providers.filter((provider: any) => provider.configured).length;
  const hardBlocks = acceptance.hard_blocks?.length || 0;
  const warnings = acceptance.soft_warnings?.length || 0;
  const goalOptions = [
    { value: "mixed", label: "Mixed / explore" },
    { value: "public_products", label: "Public products" },
    { value: "cybersecurity", label: "Cybersecurity" },
    { value: "research", label: "Research" },
    { value: "apps_internal", label: "Apps internal" },
  ];

  const statusClass = (status: string) => {
    if (status === "healthy") return "border-sylion-green/30 text-sylion-green";
    if (status === "degraded" || status === "quota_risk") return "border-sylion-amber/30 text-sylion-amber";
    if (status === "unavailable") return "border-sylion-red/30 text-sylion-red";
    return "border-muted-foreground/30 text-muted-foreground";
  };

  const viewButton = (key: "provider" | "model" | "capability", label: string, icon: ReactNode) => (
    <Button
      key={key}
      type="button"
      variant={view === key ? "default" : "outline"}
      size="sm"
      className="h-8 text-xs"
      onClick={() => onViewChange(key)}
    >
      {icon}
      {label}
    </Button>
  );

  return (
    <div className="space-y-4">
      <Card className="p-4 bg-card border-sylion-border">
        <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Cloud className="w-4 h-4 text-primary" /> Provider Catalog - Faza 2
              <HelpTip text="Żywy katalog providerów: provider -> endpoint -> model, capability matrix, gap detection, local suggestions, cost/priority chains, health/quota oraz acceptance test fazy 2." />
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Snapshot runtime z backendu: {configuredProviders} providerów aktywnych, {configuredModels.length} modeli skonfigurowanych, pokrycie {coveragePct}%.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={goal}
              onChange={(event) => void onGoalChange(event.target.value)}
              className="bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 h-8 text-xs focus:outline-none focus:border-primary/30"
            >
              {goalOptions.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => void onRefreshLocal()}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Re-scan local
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          <StatusBlock label="Providerzy aktywni" value={configuredProviders} />
          <StatusBlock label="Modele aktywne" value={configuredModels.length} />
          <StatusBlock label="Capabilities" value={covered} />
          <StatusBlock label="Hard blocks" value={hardBlocks} />
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {viewButton("provider", "Provider-first", <Cloud className="w-3.5 h-3.5 mr-1.5" />)}
          {viewButton("model", "Model-first", <Brain className="w-3.5 h-3.5 mr-1.5" />)}
          {viewButton("capability", "Capability-first", <Sliders className="w-3.5 h-3.5 mr-1.5" />)}
        </div>
      </Card>

      {view === "provider" && (
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
          <div className="space-y-3">
            {providers.map((provider: any) => {
              const activeModels = (provider.models || []).filter((model: any) => model.configured);
              const catalogModels = provider.models || [];
              return (
                <Card key={provider.provider} className="p-4 bg-card border-sylion-border">
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className={cn("text-[9px]", providerClass(provider.provider))}>{provider.display_name || provider.provider}</Badge>
                        <Badge variant="outline" className={cn("text-[9px]", statusClass(provider.health_level))}>{provider.health_level}</Badge>
                        <Badge variant="outline" className="text-[9px] border-muted-foreground/30 text-muted-foreground">{provider.kind}</Badge>
                      </div>
                      <p className="text-[10px] font-mono text-muted-foreground mt-2 break-all">{provider.default_endpoint || "endpoint do skonfigurowania"}</p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        {activeModels.length} aktywnych modeli / {catalogModels.length} w katalogu
                        {provider.latency_ms ? ` | ${provider.latency_ms}ms` : ""}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-muted-foreground">Quota</p>
                      <p className="text-xs font-mono">{provider.quota_status || "unknown"}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2 mt-3">
                    {catalogModels.slice(0, 9).map((model: any) => (
                      <div key={`${provider.provider}-${model.model_id}-${model.source}`} className="rounded-lg border border-sylion-border bg-secondary/10 p-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-[11px] font-mono truncate">{model.model_id}</p>
                          <Badge variant="outline" className={cn("text-[8px]", statusClass(model.status))}>
                            {model.configured ? "active" : "slot"}
                          </Badge>
                        </div>
                        <p className="text-[9px] text-muted-foreground mt-1">
                          {(Object.keys(model.capabilities || {}).slice(0, 3)).join(", ") || "capability TBD"}
                        </p>
                      </div>
                    ))}
                  </div>
                </Card>
              );
            })}
          </div>

          <div className="space-y-4">
            <Card className="p-4 bg-card border-sylion-border">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" /> Acceptance
              </h3>
              <div className="mt-3 space-y-2">
                {(acceptance.checks || []).map((check: any) => (
                  <div key={check.id} className="flex items-start justify-between gap-3 rounded-lg border border-sylion-border bg-secondary/10 p-2">
                    <div>
                      <p className="text-[11px] font-medium">{check.label}</p>
                      <p className="text-[9px] text-muted-foreground">{check.evidence}</p>
                    </div>
                    <Badge variant="outline" className={cn("text-[8px]", check.status === "pass" ? "border-sylion-green/30 text-sylion-green" : check.status === "warn" ? "border-sylion-amber/30 text-sylion-amber" : "border-sylion-red/30 text-sylion-red")}>
                      {check.status}
                    </Badge>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground mt-3">
                Wynik: {acceptance.score?.passed || 0}/{acceptance.score?.total || 0}; ostrze?enia: {warnings}; hard blocks: {hardBlocks}.
              </p>
            </Card>

            <Card className="p-4 bg-card border-sylion-border">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Shield className="w-4 h-4 text-sylion-amber" /> Health levels
              </h3>
              <div className="flex flex-wrap gap-2 mt-3">
                {(catalog.health_levels || []).map((level: string) => (
                  <Badge key={level} variant="outline" className={cn("text-[9px]", statusClass(level))}>{level}</Badge>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground mt-3">
                Progi quota: warn {catalog.quota_thresholds?.warn_pct ?? 75}%, soft {catalog.quota_thresholds?.soft_limit_pct ?? 90}%, hard {catalog.quota_thresholds?.hard_limit_pct ?? 100}%.
              </p>
            </Card>
          </div>
        </div>
      )}

      {view === "model" && (
        <Card className="p-4 bg-card border-sylion-border">
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-sylion-border">
                  <th className="text-left px-3 py-2">Model</th>
                  <th className="text-left px-3 py-2">Provider</th>
                  <th className="text-left px-3 py-2">Typ</th>
                  <th className="text-left px-3 py-2">Koszt in / 1M</th>
                  <th className="text-left px-3 py-2">Status</th>
                  <th className="text-left px-3 py-2">Capabilities</th>
                </tr>
              </thead>
              <tbody>
                {models.map((model: any) => (
                  <tr key={`${model.provider}-${model.endpoint}-${model.model_id}-${model.source}`} className="border-b border-sylion-border/40 hover:bg-muted/5">
                    <td className="px-3 py-2 font-mono max-w-[260px] truncate">{model.model_id}</td>
                    <td className="px-3 py-2"><Badge variant="outline" className={cn("text-[9px]", providerClass(model.provider))}>{model.provider}</Badge></td>
                    <td className="px-3 py-2">{model.kind}</td>
                    <td className="px-3 py-2 font-mono">{model.cost_input_per_1m ? `$${model.cost_input_per_1m}` : "$0"}</td>
                    <td className="px-3 py-2"><Badge variant="outline" className={cn("text-[9px]", statusClass(model.status))}>{model.configured ? model.status : "not configured"}</Badge></td>
                    <td className="px-3 py-2 text-muted-foreground">{Object.keys(model.capabilities || {}).slice(0, 5).join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {view === "capability" && (
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4">
          <Card className="p-4 bg-card border-sylion-border">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary" /> Capability matrix
            </h3>
            <div className="space-y-2">
              {matrix.map((row: any) => (
                <div key={row.id} className="rounded-lg border border-sylion-border bg-secondary/10 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold">{row.label}</p>
                      <p className="text-[10px] text-muted-foreground">{row.model_count} modeli | {row.single_point_of_failure ? "single point of failure" : row.gap ? "gap" : "covered"}</p>
                    </div>
                    <Badge variant="outline" className={cn("text-[9px]", row.gap ? "border-sylion-red/30 text-sylion-red" : row.single_point_of_failure ? "border-sylion-amber/30 text-sylion-amber" : "border-sylion-green/30 text-sylion-green")}>
                      {row.gap ? "GAP" : row.single_point_of_failure ? "THIN" : "OK"}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {(row.models || []).slice(0, 6).map((model: any) => (
                      <Badge key={`${row.id}-${model.provider}-${model.model_id}`} variant="outline" className="text-[9px] border-muted-foreground/30 text-muted-foreground">
                        {model.model_id} ({model.score})
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <div className="space-y-4">
            <Card className="p-4 bg-card border-sylion-border">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Plus className="w-4 h-4 text-sylion-amber" /> Acquisition advisor
              </h3>
              <div className="space-y-2 mt-3">
                {(catalog.acquisition_advisor || []).slice(0, 6).map((item: any) => (
                  <div key={item.provider} className="rounded-lg border border-sylion-border bg-secondary/10 p-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] font-medium">{item.display_name}</p>
                      <Badge variant="outline" className="text-[8px] border-primary/30 text-primary">{item.action}</Badge>
                    </div>
                    <p className="text-[9px] text-muted-foreground mt-1">Covers: {(item.covers || []).join(", ")}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-card border-sylion-border">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Server className="w-4 h-4 text-sylion-green" /> Lokalne sugestie
              </h3>
              <div className="space-y-2 mt-3">
                {(catalog.local_install_suggestions || []).map((item: any) => (
                  <div key={`${item.capability}-${item.title}`} className="rounded-lg border border-sylion-border bg-secondary/10 p-2">
                    <p className="text-[11px] font-medium">{item.title}</p>
                    <p className="text-[9px] text-muted-foreground mt-1">{item.recommended_when}</p>
                    <p className="text-[9px] font-mono text-muted-foreground mt-1">{item.install_hint}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-card border-sylion-border">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Network className="w-4 h-4 text-primary" /> Priority chains
              </h3>
              <div className="space-y-2 mt-3 max-h-[360px] overflow-y-auto pr-1">
                {(catalog.priority_chains || []).map((chain: any) => (
                  <div key={chain.capability} className="rounded-lg border border-sylion-border bg-secondary/10 p-2">
                    <p className="text-[11px] font-medium">{chain.capability}</p>
                    <p className="text-[9px] text-muted-foreground mt-1">
                      {(chain.chain || []).map((item: any) => item.model_id).join(" -> ") || chain.exhaustion_behavior}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function KeyForm({ onSaved }: { onSaved: () => Promise<void> }) {
  const [provider, setProvider] = useState("openai");
  const [displayName, setDisplayName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!provider.trim() || !apiKey.trim()) return;
    setSaving(true);
    try {
      const saved = await api.storeAPIKey(provider.trim().toLowerCase(), apiKey.trim(), displayName || `${provider} key`, {
        source: "ai-models-panel",
      });
      const keyId = (saved as any).key_id || (saved as any).entry_id;
      if (keyId) await api.activateAPIKey(keyId);
      setApiKey("");
      setDisplayName("");
      await onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-4 bg-card border-sylion-border">
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <KeyRound className="w-4 h-4 text-primary" /> Dodaj klucz API
        <HelpTip text="Formularz zapisu klucza API w bezpiecznym KeyVault backendu. Surowy klucz nigdy nie wraca do UI — panel pokazuje tylko zamaskowany podgląd. Po zapisie klucz aktywuje dostawcę dla rady i routera." />
      </h2>
      <div className="space-y-3">
        <Field label="Dostawca" help="Wybierz dostawcę LLM dla KeyVault. Lista jest wyrównana z backendowym katalogiem: OpenAI, Anthropic, Google, Perplexity, Z.ai, OpenRouter, Kimi/Moonshot, DeepSeek, xAI, Mistral, Groq, Cohere, Fireworks, Together oraz lokalne runtime'y.">
          <select value={provider} onChange={(event) => setProvider(event.target.value)} className={inputClass}>
            {providerOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Nazwa wyświetlana" help="Czytelna etykieta klucza (np. 'Production OpenAI', 'Dev Anthropic'). Pomaga rozróżniać wiele kluczy tego samego dostawcy w KeyVault.">
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Production OpenAI" className={inputClass} />
        </Field>
        <Field label="Klucz API" help="Wartość klucza API od dostawcy (np. sk-ant-... dla Anthropic). Jest natychmiast szyfrowana przy zapisie i nigdy nie wraca do UI w formie surowej. Wymagane.">
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="wartość klucza jest szyfrowana w spoczynku" className={`${inputClass} font-mono`} />
        </Field>
        <p className="text-[10px] text-muted-foreground">Surowy klucz jest wysyłany tylko do backendu KeyVault. Panel pokazuje wyłącznie zamaskowane podglądy.</p>
        <Button size="sm" onClick={save} disabled={saving || !apiKey.trim()}>
          {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
          Zapisz klucz
        </Button>
      </div>
    </Card>
  );
}

function ModelForm({ onSaved }: { onSaved: () => Promise<void> }) {
  const [provider, setProvider] = useState("openai");
  const [modelId, setModelId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("planner");
  const [rank, setRank] = useState("primary");
  const [weight, setWeight] = useState("1.0");
  const [contextWindow, setContextWindow] = useState("");
  const [capabilities, setCapabilities] = useState("planning, reasoning");
  const [dailyBudget, setDailyBudget] = useState("");
  const [monthlyBudget, setMonthlyBudget] = useState("");
  const [costPer1k, setCostPer1k] = useState("");
  const [fallback, setFallback] = useState("");
  const [languageProfile, setLanguageProfile] = useState("multilingual");
  const [intelligenceDepth, setIntelligenceDepth] = useState("balanced");
  const [accessLevel, setAccessLevel] = useState("gated");
  const [approvalPolicy, setApprovalPolicy] = useState("ask_for_risky_changes");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!provider.trim() || !modelId.trim()) return;
    setSaving(true);
    try {
      const config = {
        runtime_type: provider === "ollama" || provider === "localai" ? "local" : "external",
        role,
        rank,
        voting_weight: Number(weight) || 1,
        context_window: contextWindow ? Number(contextWindow) : undefined,
        language_profile: languageProfile,
        intelligence_depth: intelligenceDepth,
        access_level: accessLevel,
        approval_policy: approvalPolicy,
        cost_per_1k_tokens_usd: costPer1k ? Number(costPer1k) : undefined,
        fallback_model_id: fallback || undefined,
      };
      await api.registerModel({
        model_id: modelId.trim(),
        provider: provider.trim().toLowerCase(),
        display_name: displayName || modelId.trim(),
        config_json: JSON.stringify(config),
      });
      for (const capability of capabilities.split(",").map((item) => item.trim()).filter(Boolean)) {
        await api.addModelCapability(modelId.trim(), capability, { source: "ai-models-panel" }).catch(() => null);
      }
      if (Number(dailyBudget) > 0 || Number(monthlyBudget) > 0) {
        await api.setModelBudgetFull(
          modelId.trim(),
          Number(dailyBudget) || 0,
          Number(monthlyBudget) || 0,
          80,
        ).catch(() => null);
      }
      setModelId("");
      setDisplayName("");
      setCostPer1k("");
      await onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-4 bg-card border-sylion-border">
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Brain className="w-4 h-4 text-primary" /> Zarejestruj model
        <HelpTip text="Pełny formularz rejestracji modelu LLM w rejestrze AEIS. Określa providera, model_id, rolę w radzie, rangę, wagę głosu, budżet i polityki dostępu. Wszystkie pola łącznie z config_json są zapisywane w SQLite (registered_models)." />
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Dostawca" help="Provider modelu — decyduje, którego klienta API backend użyje przy inference. Dla 'ollama' i 'localai' runtime_type zostanie ustawiony na 'local' (zerowy koszt, prywatność).">
          <select value={provider} onChange={(event) => setProvider(event.target.value)} className={inputClass}>
            {providerOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Model ID" help="Dokładny identyfikator modelu (np. 'gpt-4o-mini', 'claude-haiku-4-5', 'qwen3-coder:30b'). Musi pasować do tego, co provider/runtime akceptuje. Identyfikator służy jako klucz primary w rejestrze.">
          <input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="gpt-4o-mini lub qwen3-coder:30b" className={`${inputClass} font-mono`} />
        </Field>
        <Field label="Nazwa wyświetlana" help="Czytelna etykieta modelu w UI (np. 'Planner primary', 'Cost-Sentinel-Haiku'). Domyślnie używana jest wartość Model ID jeśli pozostawisz puste.">
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Planner primary" className={inputClass} />
        </Field>
        <Field label="Rola" help="Funkcja modelu w radzie: planner planuje pracę, architect projektuje rozwiązania, executor wykonuje zadania, critic kwestionuje, verifier weryfikuje wyniki, sentinele pilnują kosztów/bezpieczeństwa.">
          <select value={role} onChange={(event) => setRole(event.target.value)} className={inputClass}>
            {["planner", "architect", "executor", "critic", "verifier", "governance", "cost_sentinel", "security_sentinel", "funding_specialist"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Ranga" help="Hierarchia w radzie: primary = pełnoprawny członek z głosem decydującym; senior_specialist = ekspert dziedzinowy; support = głos pomocniczy; review_only/validation_only = tylko do oceny; local_worker = lokalny model wsparcia.">
          <select value={rank} onChange={(event) => setRank(event.target.value)} className={inputClass}>
            {["primary", "senior_specialist", "support", "review_only", "validation_only", "local_worker"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Waga głosowania" help="Mnożnik głosu modelu w decyzjach rady. 1.0 = głos standardowy; >1.0 dla expertów (np. 1.5 dla R5 Architect); <1.0 dla wsparcia (np. 0.7 dla local_worker). Suma wag musi pozwalać na większość kwalifikowaną.">
          <input value={weight} onChange={(event) => setWeight(event.target.value)} type="number" step="0.1" min="0" className={inputClass} />
        </Field>
        <Field label="Okno kontekstu" help="Maksymalny rozmiar promptu w tokenach (input + output). Przekroczenie powoduje obcięcie historii. Typowe wartości: 8K dla starych modeli, 128K dla GPT-4o, 200K dla Claude, 1M dla Gemini Pro.">
          <input value={contextWindow} onChange={(event) => setContextWindow(event.target.value)} type="number" placeholder="128000" className={inputClass} />
        </Field>
        <Field label="Budżet dzienny USD" help="Twardy limit dziennych wydatków na ten model. Po przekroczeniu router automatycznie spadnie na fallback. Wartość 0 lub puste = bez limitu (uwaga na koszty!).">
          <input value={dailyBudget} onChange={(event) => setDailyBudget(event.target.value)} type="number" step="0.01" placeholder="5.00" className={inputClass} />
        </Field>
        <Field label="Budżet miesięczny USD" help="Twardy limit miesięcznych wydatków na ten model (kalendarzowy reset 1. dnia miesiąca). 80% triggeruje alert; 100% przełącza na fallback. Wartość 0 lub puste = bez limitu.">
          <input value={monthlyBudget} onChange={(event) => setMonthlyBudget(event.target.value)} type="number" step="0.01" placeholder="100.00" className={inputClass} />
        </Field>
        <Field label="Koszt na 1K tokenów USD" help="Średni koszt 1000 tokenów (mix input/output) — wykorzystywany do estymacji kosztów przed wywołaniem i raportowania. Sprawdź pricing.json dostawcy. Przykład: GPT-4o-mini ~$0.0002, Claude Sonnet ~$0.006.">
          <input value={costPer1k} onChange={(event) => setCostPer1k(event.target.value)} type="number" step="0.0001" placeholder="0.0020" className={inputClass} />
        </Field>
        <Field label="Profil językowy" help="Preferencje językowe modelu: multilingual = uniwersalny; polish_primary = optymalizacja dla polskich tekstów; code_heavy = lepszy w kodzie; documentation = bardziej formalny; funding_formal = język wniosków grantowych.">
          <select value={languageProfile} onChange={(event) => setLanguageProfile(event.target.value)} className={inputClass}>
            {["multilingual", "polish_primary", "english_primary", "code_heavy", "documentation", "funding_formal"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Głębokość intelligence" help="Profil performance: fast = niska latencja (Haiku); balanced = standard (Sonnet); deep = większy reasoning; research = wieloetapowe analizy; council_grade = premium (Opus) do decyzji D3+.">
          <select value={intelligenceDepth} onChange={(event) => setIntelligenceDepth(event.target.value)} className={inputClass}>
            {["fast", "balanced", "deep", "research", "council_grade"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Poziom dostępu" help="Co model może w systemie: full = pełny dostęp (z gate); limited = ograniczone akcje; gated = wymaga Human Gate dla większości operacji (DOMYŚLNIE!); read_only = tylko odczyt; review_only = tylko ocena; no_external_actions = brak akcji zewnętrznych.">
          <select value={accessLevel} onChange={(event) => setAccessLevel(event.target.value)} className={inputClass}>
            {["full", "limited", "gated", "read_only", "review_only", "no_external_actions"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Polityka zatwierdzania" help="Kiedy model wymaga zgody operatora (Human Gate): auto_low_risk_only = tylko zadania low-risk auto; ask_for_risky_changes = pyta o ryzykowne (DOMYŚLNIE); ask_for_code_changes = każda zmiana kodu; always_human_gate = każda akcja wymaga zgody.">
          <select value={approvalPolicy} onChange={(event) => setApprovalPolicy(event.target.value)} className={inputClass}>
            {[
              "auto_low_risk_only",
              "ask_for_risky_changes",
              "ask_for_code_changes",
              "ask_for_architecture_changes",
              "ask_for_external_actions",
              "always_human_gate",
            ].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Model fallback" help="Model_id zapasowego LLM uruchamianego, gdy ten zawiedzie (rate limit, błąd, brak budżetu). Powinien być tańszy/lokalny (np. fallback z Opus na Sonnet, z Sonnet na Haiku, z cloud na Ollama).">
          <input value={fallback} onChange={(event) => setFallback(event.target.value)} placeholder="lokalny lub tańszy fallback" className={`${inputClass} font-mono`} />
        </Field>
        <Field label="Kompetencje" help="Lista możliwości modelu rozdzielonych przecinkami (np. 'planning, coding, review'). Router używa ich do dopasowania modelu do typu zadania. Każda kompetencja zostanie zapisana jako osobny wpis w model_capabilities.">
          <input value={capabilities} onChange={(event) => setCapabilities(event.target.value)} placeholder="planning, coding, review" className={inputClass} />
        </Field>
      </div>
      <Button size="sm" className="mt-3" onClick={save} disabled={saving || !modelId.trim()}>
        {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
        Zarejestruj model
      </Button>
    </Card>
  );
}

function CouncilMemberCard({ member, models, onSaved }: { member: any; models: any[]; onSaved: () => Promise<void> }) {
  const [modelId, setModelId] = useState(member.model_id || "");
  const [role, setRole] = useState(member.role || "critic");
  const [rank, setRank] = useState(member.rank || "primary");
  const [weight, setWeight] = useState(String(member.voting_weight ?? 1));
  const [priority, setPriority] = useState(String(member.priority ?? 0));
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.configureCouncilMember(member.member_id, modelId, role, Number(priority) || 0, member.system_prompt || undefined, {
        rank,
        voting_weight: Number(weight) || 1,
        specialization: member.specialization || "",
        max_tokens: Number(member.max_tokens) || 0,
      });
      await api.rebuildModelCouncilHierarchy().catch(() => null);
      await onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold">{member.member_id}</p>
          <p className="text-[10px] font-mono text-muted-foreground break-all">{member.model_id}</p>
          {member.specialization && <p className="text-[10px] text-muted-foreground mt-2">Specjalizacja: {member.specialization}</p>}
        </div>
        <div className="flex gap-2 flex-wrap lg:justify-end">
          <Badge variant="outline" className="text-[9px] border-primary/30 text-primary">{role}</Badge>
          <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber">{rank}</Badge>
          <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green">w {weight}</Badge>
          <Badge variant="outline" className="text-[9px] border-muted-foreground/30 text-muted-foreground">P{priority}</Badge>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mt-3">
        <select value={modelId} onChange={(event) => setModelId(event.target.value)} className={`${inputClass} md:col-span-2`}>
          {models.map((model) => <option key={model.model_id} value={model.model_id}>{model.model_id}</option>)}
          {modelId && !models.some((model) => model.model_id === modelId) && <option value={modelId}>{modelId}</option>}
        </select>
        <select value={role} onChange={(event) => setRole(event.target.value)} className={inputClass}>
          {["planner", "architect", "executor", "critic", "verifier", "governance", "cost_sentinel", "security_sentinel", "local_verifier"].map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select value={rank} onChange={(event) => setRank(event.target.value)} className={inputClass}>
          {["primary", "senior_specialist", "support", "review_only", "validation_only"].map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <input value={priority} onChange={(event) => setPriority(event.target.value)} type="number" className={inputClass} />
      </div>
      <div className="grid grid-cols-[1fr_76px_auto] gap-2 items-center mt-3">
        <input value={weight} onChange={(event) => setWeight(event.target.value)} type="range" min="0" max="2" step="0.1" className="w-full" />
        <input value={weight} onChange={(event) => setWeight(event.target.value)} type="number" min="0" max="2" step="0.1" className={inputClass} />
        <Button size="sm" variant="outline" className="h-8 text-xs" onClick={save} disabled={saving || !modelId}>
          {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle2 className="w-3 h-3 mr-1" />}
          Zapisz
        </Button>
      </div>
    </div>
  );
}

function CouncilForm({ models, onSaved }: { models: any[]; onSaved: () => Promise<void> }) {
  const [memberId, setMemberId] = useState("");
  const [modelId, setModelId] = useState("");
  const [role, setRole] = useState("critic");
  const [rank, setRank] = useState("primary");
  const [weight, setWeight] = useState("1.0");
  const [priority, setPriority] = useState("1");
  const [specialization, setSpecialization] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    const chosenModel = modelId.trim();
    if (!chosenModel) return;
    setSaving(true);
    try {
      await api.configureCouncilMember(memberId || `${role}-${chosenModel}`, chosenModel, role, Number(priority) || 0, undefined, {
        rank,
        voting_weight: Number(weight) || 1,
        specialization,
        max_tokens: Number(maxTokens) || 0,
      });
      setMemberId("");
      setModelId("");
      await onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-4 bg-card border-sylion-border">
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Users className="w-4 h-4 text-sylion-amber" /> Dodaj członka rady
        <HelpTip text="Konfiguruje model jako członka rady z określoną rolą, rangą i wagą głosu. Model musi być wcześniej zarejestrowany w 'Rejestrze modeli'. Bez 3+ członków rada nie może debatować D3+." />
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Identyfikator członka" help="Unikalny ID członka rady (np. 'security-critic', 'planner-primary'). Jeśli puste, system wygeneruje '${role}-${model_id}'.">
          <input value={memberId} onChange={(event) => setMemberId(event.target.value)} placeholder="security-critic" className={inputClass} />
        </Field>
        <Field label="Model" help="Wybierz model z rejestru AEIS, który będzie pełnił tę rolę w radzie. Lista zawiera wszystkie modele zarejestrowane w 'Rejestr modeli'. Wymagane.">
          <select value={modelId} onChange={(event) => setModelId(event.target.value)} className={inputClass}>
            <option value="">Wybierz model...</option>
            {models.map((model) => <option key={model.model_id} value={model.model_id}>{model.model_id}</option>)}
          </select>
        </Field>
        <Field label="Rola" help="Funkcja w radzie: planner = planowanie pracy; architect = projektowanie; executor = wykonanie; critic = krytyka rozwiązań; verifier = weryfikacja; sentinele = pilnowanie kosztów/bezpieczeństwa.">
          <select value={role} onChange={(event) => setRole(event.target.value)} className={inputClass}>
            {["planner", "architect", "executor", "critic", "verifier", "governance", "cost_sentinel", "security_sentinel"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Ranga" help="Pozycja w hierarchii: primary = pełen głos (zalecany dla R3-R5); senior_specialist = ekspert dziedzinowy; support = głos pomocniczy; review_only/validation_only = tylko ocena bez prawa głosu.">
          <select value={rank} onChange={(event) => setRank(event.target.value)} className={inputClass}>
            {["primary", "senior_specialist", "support", "review_only", "validation_only"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Waga głosowania" help="Mnożnik głosu w decyzjach rady. 1.0 = standard, >1.0 dla expertów (np. 1.5 dla Architect), <1.0 dla wsparcia. Suma wag aktywnych członków musi pozwalać na większość kwalifikowaną (zwykle 2/3).">
          <input value={weight} onChange={(event) => setWeight(event.target.value)} type="number" step="0.1" min="0" className={inputClass} />
        </Field>
        <Field label="Priorytet" help="Kolejność wezwania członka do debaty (niższa liczba = wcześniej). 1 = pierwszy w kolejce, 99 = ostatni. Pomaga w sterowaniu kolejnością wypowiedzi w deliberacji.">
          <input value={priority} onChange={(event) => setPriority(event.target.value)} type="number" className={inputClass} />
        </Field>
        <Field label="Specjalizacja" help="Tagi specjalizacji członka rozdzielone przecinkami (np. 'security, cost, funding'). Router używa do dopasowania członka do typu sprawy. Pomaga, gdy mamy wielu critic-ów o różnych obszarach.">
          <input value={specialization} onChange={(event) => setSpecialization(event.target.value)} placeholder="security, cost, funding" className={inputClass} />
        </Field>
        <Field label="Maksimum tokenów" help="Limit tokenów dla pojedynczej wypowiedzi tego członka. Zapobiega 'pożeraniu kontekstu' przez gadatliwe modele. Typowe wartości: 2048 dla critic-a, 4096 dla architect-a, 8192 dla planner-a.">
          <input value={maxTokens} onChange={(event) => setMaxTokens(event.target.value)} type="number" placeholder="4096" className={inputClass} />
        </Field>
      </div>
      <Button size="sm" className="mt-3" onClick={save} disabled={saving || !modelId.trim()}>
        {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
        Zapisz członka rady
      </Button>
    </Card>
  );
}

function RoutingDefaultsTab({
  cells,
  registeredModels,
  preset,
  saving,
  onCellChange,
  onSave,
}: {
  cells: any[];
  registeredModels: any[];
  preset: string;
  saving: boolean;
  onCellChange: (recType: string, risk: string, modelId: string) => void;
  onSave: () => Promise<void>;
}) {
  const RISK_DISPLAY = [
    { key: "low", label: "Niskie ryzyko", desc: "Szkice, dry-run, tanie zadania" },
    { key: "medium", label: "Średnie ryzyko", desc: "Normalny flow, dokumentacja" },
    { key: "high", label: "Wysokie ryzyko", desc: "Produkcja, architektura" },
    { key: "critical", label: "Krytyczne", desc: "Decyzje D3+, council vote" },
  ];

  const recTypes = Array.from(new Set(cells.map((c) => c.recommendation_type)));
  const availableModels = registeredModels.length > 0
    ? registeredModels.map((m) => m.model_id)
    : ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"];

  const getModel = (recType: string, risk: string) =>
    cells.find((c) => c.recommendation_type === recType && c.risk_level === risk)?.model_id ?? "";

  if (cells.length === 0) {
    return (
      <Card className="p-8 border-sylion-border bg-card text-center">
        <Network className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
        <p className="text-xs text-muted-foreground">
          Brak danych matrycy routingu. Sprawdź połączenie z backendem lub odśwież panel.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4 border-sylion-border bg-card">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary" /> Preferencje domyślne routingu
              <HelpTip text="Matryca decyzyjna: typ zadania (security, cost, architecture, ...) × poziom ryzyka (low/medium/high/critical) → wybrany model. Wartości tu zapisane stają się domyślnym wyborem LLM Judge gdy router nie ma jednoznacznego sygnału." />
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Domyślny model per typ zadania × poziom ryzyka. Zapis aktualizuje matryca LLM Judge.
              Obecny preset: <span className="font-mono text-foreground">{preset}</span>
            </p>
          </div>
          <Button size="sm" onClick={onSave} disabled={saving}>
            {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
            Zapisz preferencje
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-sylion-border">
                <th className="text-left px-3 py-2 text-muted-foreground font-medium w-48">Typ zadania</th>
                {RISK_DISPLAY.map((r) => (
                  <th key={r.key} className="px-3 py-2 text-center min-w-[160px]">
                    <div>
                      <Badge variant="outline" className="text-[9px] mb-0.5">{r.label}</Badge>
                      <p className="text-[9px] text-muted-foreground font-normal">{r.desc}</p>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recTypes.map((recType) => (
                <tr key={recType} className="border-b border-sylion-border/40 hover:bg-muted/5">
                  <td className="px-3 py-2">
                    <div>
                      <span className="text-foreground font-medium">
                        {REC_TYPE_LABELS[recType] || recType}
                      </span>
                      <span className="block font-mono text-[9px] text-muted-foreground">{recType}</span>
                    </div>
                  </td>
                  {RISK_DISPLAY.map((r) => {
                    const modelId = getModel(recType, r.key);
                    return (
                      <td key={r.key} className="px-2 py-1.5">
                        <select
                          value={modelId}
                          onChange={(e) => onCellChange(recType, r.key, e.target.value)}
                          className={`${inputClass} font-mono text-[10px]`}
                        >
                          {availableModels.map((m) => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                          {modelId && !availableModels.includes(modelId) && (
                            <option value={modelId}>{modelId}</option>
                          )}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-4 border-sylion-border bg-card">
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-sylion-amber" /> Szybkie ustawieńie per typ decyzji
          <HelpTip text="Skrót do trzech najczęściej zmienianych komórek matrycy: krytyczna decyzja security (zalecany Opus), szkic UI low-risk (zalecany Haiku — tani), high-risk architecture review (zalecany Sonnet — krytyk). Pomaga skonfigurować router w 30 sekund." />
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { key: "security", risk: "critical", label: "Decyzja krytyczna", hint: "Wybierz model premium (Opus)" },
            { key: "cost_optimization", risk: "low", label: "Szkic / draft UI", hint: "Wybierz tani model (Haiku)" },
            { key: "architecture", risk: "high", label: "Przegląd audytu", hint: "Wybierz model krytyka (Sonnet)" },
          ].map(({ key, risk, label, hint }) => {
            const modelId = getModel(key, risk);
            return (
              <div key={key} className="rounded-lg border border-sylion-border p-3 bg-secondary/10">
                <p className="text-xs font-semibold mb-0.5">{label}</p>
                <p className="text-[10px] text-muted-foreground mb-2">{hint}</p>
                <select
                  value={modelId}
                  onChange={(e) => onCellChange(key, risk, e.target.value)}
                  className={`${inputClass} font-mono text-[10px]`}
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  {modelId && !availableModels.includes(modelId) && (
                    <option value={modelId}>{modelId}</option>
                  )}
                </select>
                <p className="text-[9px] font-mono text-muted-foreground mt-1.5">
                  {REC_TYPE_LABELS[key] || key} × {risk}
                </p>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

function Field({ label, children, help }: { label: string; children: ReactNode; help?: string }) {
  return (
    <label className="block">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 inline-flex items-center">
        {label}
        {help && <HelpTip text={help} />}
      </span>
      {children}
    </label>
  );
}
