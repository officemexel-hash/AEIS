"use client";

import { useMemo, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { useApi } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  KeyRound,
  RefreshCw,
  WifiOff,
  Clock,
  EyeOff,
  ShieldCheck,
  Activity,
  Hash,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Secret {
  name: string;
  scope: string;
  last_rotated: number;
  access_count: number;
  created_at?: number;
}

interface SecretsData {
  secrets: Secret[];
}

interface AIProviderRow {
  provider: string;
  default_model: string;
  key_available: boolean;
  ready: boolean;
  locality: string;
  runtime_reachable?: boolean | null;
}

interface ProviderValidation {
  provider: string;
  connection?: {
    ok?: boolean;
    status?: string;
    model?: string;
    latency_ms?: number;
    error?: string;
  };
  key_info?: {
    ok?: boolean;
    status?: string;
    plan_inferred?: string;
    accessible_model_count?: number;
    api_balance_usd?: number | null;
    credit_limit_usd?: number | null;
    error?: string;
    note?: string;
  };
  limits?: {
    subscription_5h?: { status?: string };
    subscription_weekly?: { status?: string };
    api_budget?: Record<string, unknown>;
    rate_limits?: Record<string, string>;
    plan_inferred?: string;
  };
  notes?: string[];
}

interface LocalModelRow {
  name: string;
  size_gb?: number;
  family?: string;
  parameter_size?: string;
  quantization?: string;
  installed?: boolean;
}

interface ProviderCatalogSuggestion {
  capability: string;
  title: string;
  provider: string;
  recommended_when?: string;
  models?: string[];
  install_hint?: string;
}

/* ============================================================
   Helpers
   ============================================================ */

function formatTimestamp(ts: number): string {
  if (!ts) return "--";
  const diff = Date.now() - ts;
  if (diff < 60000) return "przed chwilą";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h temu`;
  return `${Math.floor(diff / 86400000)}d temu`;
}

const scopeBadgeStyles: Record<string, string> = {
  global: "border-purple-400/30 text-purple-400 bg-purple-400/5",
  module: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
  pipeline: "border-cyan-400/30 text-cyan-400 bg-cyan-400/5",
  workspace: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
  system: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
};

function maskName(name: string): string {
  if (name.length <= 4) return "*".repeat(name.length);
  return name.slice(0, 2) + "*".repeat(Math.min(name.length - 4, 8)) + name.slice(-2);
}

function isRecentlyRotated(lastRotated: number): boolean {
  if (!lastRotated) return false;
  return Date.now() - lastRotated < 86400000 * 7;
}

const PROVIDER_SECRET_HINTS = [
  "ChatGPT / OPENAI_API_KEY",
  "Claude / ANTHROPIC_API_KEY",
  "Google / GEMINI_API_KEY",
  "Kimi / MOONSHOT_API_KEY",
  "OpenRouter / OPENROUTER_API_KEY",
  "Perplexity / PERPLEXITY_API_KEY",
  "Z.AI / ZAI_API_KEY",
];

const SECRET_NAME_TO_PROVIDER: Record<string, string> = {
  OPENAI_API_KEY: "openai",
  OPENAI: "openai",
  CHATGPT: "openai",
  ANTHROPIC_API_KEY: "anthropic",
  ANTHROPIC: "anthropic",
  CLAUDE: "anthropic",
  PERPLEXITY_API_KEY: "perplexity",
  PERPLEXITY: "perplexity",
  GOOGLE_API_KEY: "google",
  GEMINI_API_KEY: "google",
  GOOGLE: "google",
  GEMINI: "google",
  ZAI_API_KEY: "zai",
  ZAI: "zai",
  OPENROUTER_API_KEY: "openrouter",
  OPENROUTER: "openrouter",
  OPENROUTE: "openrouter",
  MOONSHOT_API_KEY: "moonshot",
  KIMI_API_KEY: "moonshot",
  KIMI: "moonshot",
  MOONSHOT: "moonshot",
};

function providerFromSecretName(name: string): string | null {
  const canonical = name.trim().toUpperCase();
  if (SECRET_NAME_TO_PROVIDER[canonical]) return SECRET_NAME_TO_PROVIDER[canonical];
  const simplified = canonical.replace(/[^A-Z0-9]/g, "");
  return SECRET_NAME_TO_PROVIDER[simplified] || null;
}

function describeApiBudget(validation?: ProviderValidation | null): string {
  const apiBudget = validation?.limits?.api_budget;
  if (!apiBudget) return "Budzet API: do sprawdźenia";
  if (apiBudget.status === "reported_by_provider") {
    const usage = apiBudget.usage_usd ?? "?";
    const limit = apiBudget.credit_limit_usd ?? "?";
    return `Budzet API: provider raportuje uzycie ${usage} / limit ${limit} USD`;
  }
  if (apiBudget.status === "rate_limit_headers_only") {
    return "Budzet API: dostepne limity rate-limit, brak salda konta";
  }
  return "Budzet API: provider nie udostępnia salda przez API";
}

/* ============================================================
   Page Component
   ============================================================ */

export default function SecretsPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: secretsData, refresh: refreshSecrets } = useApi(
    () => api.listSecrets() as Promise<SecretsData>,
    { secrets: [] } as SecretsData,
    15000
  );
  const { data: providersData, refresh: refreshProviders } = useApi(
    () => api.listAIProviders() as Promise<{ providers: AIProviderRow[] }>,
    { providers: [] },
    30000
  );
  const { data: localModelsData, refresh: refreshLocalModels } = useApi(
    () => api.listInstalledLocalModels() as Promise<{ models: LocalModelRow[]; count: number; ollama_reachable: boolean; ollama_base_url: string }>,
    { models: [], count: 0, ollama_reachable: false, ollama_base_url: "" },
    30000
  );
  const { data: providerCatalogData, refresh: refreshProviderCatalog } = useApi(
    () => api.getProviderCatalog("mixed") as Promise<{ local_install_suggestions?: ProviderCatalogSuggestion[]; acquisition_advisor?: any[]; acceptance?: any }>,
    { local_install_suggestions: [], acquisition_advisor: [], acceptance: null },
    60000
  );

  const secrets = secretsData.secrets || [];

  /* ---------- FE-9.1 add-secret form state ---------- */
  const [form, setForm] = useState({ name: "", scope: "global", value: "" });
  const [busy, setBusy] = useState(false);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [providerChecks, setProviderChecks] = useState<Record<string, ProviderValidation>>({});
  const [lastValidation, setLastValidation] = useState<ProviderValidation | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const handleCreate = useCallback(async () => {
    if (!form.name.trim() || !form.value.trim()) return;
    setBusy(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    setLastValidation(null);
    try {
      const secretName = form.name.trim();
      const response = await api.createSecret({ name: secretName, scope: form.scope, value: form.value });
      const validation = response?.provider_validation as ProviderValidation | null | undefined;
      if (validation?.provider) {
        setProviderChecks((current) => ({ ...current, [validation.provider]: validation }));
        setLastValidation(validation);
      }
      const provider = validation?.provider || providerFromSecretName(secretName);
      const status = validation?.connection?.ok ? "Połączenie z providerem sprawdźone." : provider ? "Sekret dodany; test providera wymaga uwagi." : "Sekret dodany.";
      setSubmitSuccess(`Sekret "${secretName}" zostal dodany. ${status}`);
      setForm({ name: "", scope: "global", value: "" });
      refreshSecrets();
      refreshProviders();
      refreshLocalModels();
      refreshProviderCatalog();
      window.setTimeout(() => setSubmitSuccess(null), 4000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Nieznany błąd zapisu sekretu";
      // Defensive 404 fallback (BE-8 not yet shipped)
      if (msg.includes("404")) {
        setSubmitError("Backend endpoint w przygotowaniu (BE-8). Sprobuj ponownie po wdrozeniu.");
      } else {
        setSubmitError(msg);
      }
    } finally {
      setBusy(false);
    }
  }, [form, refreshLocalModels, refreshProviderCatalog, refreshProviders, refreshSecrets]);

  const handleProviderRetest = useCallback(async (provider: string, model?: string) => {
    setTestingProvider(provider);
    try {
      const [connection, keyInfo] = await Promise.allSettled([
        api.testAIProvider(provider, {
          prompt: "Odpowiedz dokladnie jednym slowem: OK",
          model,
          max_tokens: 8,
        }),
        api.getAIProviderKeyInfo(provider),
      ]);
      const validation: ProviderValidation = {
        provider,
        connection: connection.status === "fulfilled"
          ? { ok: true, status: "connected", model: connection.value?.model, latency_ms: connection.value?.latency_ms }
          : { ok: false, status: "failed", error: connection.reason instanceof Error ? connection.reason.message : String(connection.reason) },
        key_info: keyInfo.status === "fulfilled"
          ? {
              ok: true,
              status: "introspected",
              plan_inferred: keyInfo.value?.plan_inferred,
              accessible_model_count: Array.isArray(keyInfo.value?.accessible_models) ? keyInfo.value.accessible_models.length : undefined,
              api_balance_usd: keyInfo.value?.balance_usd,
              credit_limit_usd: keyInfo.value?.credit_limit_usd,
              note: keyInfo.value?.note,
            }
          : { ok: false, status: "failed", error: keyInfo.reason instanceof Error ? keyInfo.reason.message : String(keyInfo.reason) },
        limits: {
          subscription_5h: { status: "not_exposed_by_provider_api" },
          subscription_weekly: { status: "not_exposed_by_provider_api" },
          api_budget: keyInfo.status === "fulfilled" && provider === "openrouter"
            ? { status: "reported_by_provider", usage_usd: keyInfo.value?.balance_usd, credit_limit_usd: keyInfo.value?.credit_limit_usd }
            : { status: keyInfo.status === "fulfilled" && keyInfo.value?.rate_limits ? "rate_limit_headers_only" : "not_exposed_by_provider_api" },
          rate_limits: keyInfo.status === "fulfilled" ? keyInfo.value?.rate_limits || {} : {},
          plan_inferred: keyInfo.status === "fulfilled" ? keyInfo.value?.plan_inferred : "unknown",
        },
      };
      setProviderChecks((current) => ({ ...current, [provider]: validation }));
      setLastValidation(validation);
    } finally {
      setTestingProvider(null);
      refreshProviders();
    }
  }, [refreshProviders]);

  /* ---------- Derived stats ---------- */
  const recentlyRotated = useMemo(
    () => secrets.filter((s) => isRecentlyRotated(s.last_rotated)).length,
    [secrets]
  );
  const totalAccessCount = useMemo(
    () => secrets.reduce((sum, s) => sum + (s.access_count || 0), 0),
    [secrets]
  );

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-48 bg-muted animate-pulse rounded" />
            <div className="h-4 w-60 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-64 bg-muted animate-pulse rounded-lg" />
      </div>
    );
  }

  /* ---------- Backend unreachable ---------- */
  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <KeyRound className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Sekrety
              <HelpTip text="Vault sekretów (klucze API, hasła, certyfikaty). Maskowanie w UI; pełna wartość widoczna tylko po explicit reveal z audit-log entry. Rotacja zalecana co 90 dni." />
            </h1>
            <p className="text-sm text-muted-foreground">Szyfrowane sekrety i śledzenie rotacji</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane sekretów wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { fetchHealth(); refreshSecrets(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Summary cards ---------- */
  const summaryCards = [
    {
      label: "Łącznie sekretów",
      tip: "Liczba zarejestrowanych sekretów (klucze, hasła, tokeny). Każdy zaszyfrowany at-rest.",
      value: secrets.length,
      icon: KeyRound,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Niedawno rotowane",
      tip: "Sekrety zrotowane w ciągu ostatnich 7 dni. Zalecana rotacja co 90 dni dla zachowania compliance.",
      value: recentlyRotated,
      icon: ShieldCheck,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Liczba dostępów",
      tip: "Łączna liczba odczytów wszystkich sekretów. Skok wartości może wskazywać na nadużycie lub atak.",
      value: totalAccessCount,
      icon: Hash,
      color: "text-sylion-amber",
      bgColor: "bg-sylion-amber/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-amber/10 border border-sylion-amber/20 flex items-center justify-center">
            <KeyRound className="w-4 h-4 text-sylion-amber" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Sekrety
              <HelpTip text="Vault sekretów (klucze API, hasła, certyfikaty). Maskowanie w UI; pełna wartość widoczna tylko po explicit reveal z audit-log entry. Rotacja zalecana co 90 dni." />
            </h1>
            <p className="text-sm text-muted-foreground">Szyfrowane sekrety i śledzenie rotacji</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refreshSecrets()}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Odśwież
        </Button>
      </div>

      {/* ====== FE-9.1 ADD SECRET FORM ====== */}
      <Card className="p-4 bg-[#0f1629] border-sylion-border" data-testid="secrets-add-card">
        <div className="flex items-center gap-2 mb-3">
          <Plus className="w-3.5 h-3.5 text-sylion-amber" />
          <h3 className="text-xs font-medium uppercase tracking-wider">
            Dodaj nowy sekret
            <HelpTip text="Rejestruje nowy sekret w vault. Klucze providerów modeli mozesz wpisywac jako ChatGPT, Claude, Google, Kimi, OpenRouter albo klasycznie jako OPENAI_API_KEY itd. Runtime mirroruje je do KeyVault." />
          </h3>
        </div>
        <div className="mb-3 rounded-md border border-sylion-blue/15 bg-sylion-blue/5 px-3 py-2">
          <p className="text-[11px] text-muted-foreground">
            Klucze modeli wpisane tutaj zasilają runtime AEIS po zapisie. Obsługiwane nazwy:{" "}
            <span className="text-sylion-blue">{PROVIDER_SECRET_HINTS.join(", ")}</span>.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Nazwa
              <HelpTip text="Identyfikator sekretu (np. STRIPE_API_KEY). Bez spacji i znakow specjalnych — A-Z, 0-9, podkreslnik." />
            </label>
            <input
              data-testid="secrets-form-name"
              placeholder="np. ChatGPT albo OPENAI_API_KEY"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
              disabled={busy}
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Zakres
              <HelpTip text="Zakres widocznosci sekretu: global (wszedzie), module (jeden modul), pipeline (jeden pipeline), workspace (caly workspace), system (wewnetrzne)." />
            </label>
            <select
              data-testid="secrets-form-scope"
              value={form.scope}
              onChange={(e) => setForm((f) => ({ ...f, scope: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy}
            >
              <option value="global">global</option>
              <option value="module">module</option>
              <option value="pipeline">pipeline</option>
              <option value="workspace">workspace</option>
              <option value="system">system</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Wartosc
              <HelpTip text="Tajna wartość — szyfrowana at-rest. Nie bedzie widoczna po zapisaniu. Aby zmienic, dodaj nowa wartość i usun stara." />
            </label>
            <input
              data-testid="secrets-form-value"
              type="password"
              placeholder="****"
              value={form.value}
              onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
              disabled={busy}
            />
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 mt-3">
          <Button
            data-testid="secrets-form-submit"
            size="sm"
            onClick={handleCreate}
            disabled={busy || !form.name.trim() || !form.value.trim()}
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
            Dodaj
          </Button>
        </div>
        <AnimatePresence>
          {submitError && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 flex items-start gap-2 rounded-md border border-sylion-red/20 bg-sylion-red/5 p-2 text-xs text-sylion-red"
              data-testid="secrets-form-error"
            >
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5" />
              <span>{submitError}</span>
            </motion.div>
          )}
          {submitSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 flex items-start gap-2 rounded-md border border-sylion-green/20 bg-sylion-green/5 p-2 text-xs text-sylion-green"
              data-testid="secrets-form-success"
            >
              <CheckCircle2 className="w-3.5 h-3.5 mt-0.5" />
              <span>{submitSuccess}</span>
            </motion.div>
          )}
        </AnimatePresence>
        {lastValidation && (
          <div className="mt-3 rounded-md border border-sylion-blue/20 bg-sylion-blue/5 p-3 text-xs" data-testid="secrets-provider-validation">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-sylion-blue">
                  Test providera: {lastValidation.provider}
                </p>
                <p className={cn("mt-1", lastValidation.connection?.ok ? "text-sylion-green" : "text-sylion-red")}>
                  Połączenie: {lastValidation.connection?.ok ? `OK (${lastValidation.connection?.model || "model"}, ${lastValidation.connection?.latency_ms ?? "?"} ms)` : lastValidation.connection?.error || "błąd testu"}
                </p>
                <p className="mt-1 text-muted-foreground">
                  Plan/limity: {lastValidation.key_info?.plan_inferred || "unknown"} · modele: {lastValidation.key_info?.accessible_model_count ?? "?"} · {describeApiBudget(lastValidation)}
                </p>
                <p className="mt-1 text-muted-foreground">
                  Limity 5h/tydzien: provider API zwykle ich nie ujawnia; AEIS musi sledzic uzycie runtime lokalnie.
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleProviderRetest(lastValidation.provider, lastValidation.connection?.model)}
                disabled={testingProvider === lastValidation.provider}
              >
                {testingProvider === lastValidation.provider ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1" />}
                Testuj ponownie
              </Button>
            </div>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Card className="p-4 bg-[#0f1629] border-sylion-border" data-testid="secrets-local-models">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-sylion-green" />
              <h3 className="text-xs font-medium uppercase tracking-wider">
                Modele lokalne
                <HelpTip text="Modele wykryte lokalnie przez Ollama. AEIS powinien używa? ich w pierwszej kolejno?ci tam, gdzie koszt, prywatno?? albo limit API ma znaczenie." />
              </h3>
            </div>
            <Badge variant="outline" className={cn("text-[9px]", localModelsData.ollama_reachable ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
              {localModelsData.ollama_reachable ? "Ollama online" : "Ollama offline"}
            </Badge>
          </div>
          <p className="mb-3 text-[10px] text-muted-foreground truncate">
            {localModelsData.count || 0} modeli · {localModelsData.ollama_base_url || "brak runtime"}
          </p>
          <div className="space-y-2 max-h-72 overflow-auto pr-1">
            {(localModelsData.models || []).map((model) => (
              <div key={model.name} className="rounded-md border border-border/25 bg-muted/10 p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{model.name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {model.family || "model"} · {model.parameter_size || "?"} · {model.quantization || "?"}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-[9px] border-sylion-green/30 text-sylion-green shrink-0">
                    {model.size_gb?.toFixed ? `${model.size_gb.toFixed(1)} GB` : "local"}
                  </Badge>
                </div>
              </div>
            ))}
            {(localModelsData.models || []).length === 0 && (
              <div className="rounded-md border border-dashed border-border/30 p-4 text-center text-xs text-muted-foreground">
                Brak wykrytych modeli lokalnych
              </div>
            )}
          </div>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-sylion-border" data-testid="secrets-model-suggestions">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-sylion-amber" />
              <h3 className="text-xs font-medium uppercase tracking-wider">
                Propozycje kolejnych modeli
                <HelpTip text="Rekomendacje z katalogu providerów: lokalne uzupełnienia, brakujące capability i następne sensowne integracje." />
              </h3>
            </div>
            <Badge variant="outline" className={cn("text-[9px]", providerCatalogData.acceptance?.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {providerCatalogData.acceptance?.accepted ? "katalog OK" : "do uzupełnienia"}
            </Badge>
          </div>
          <div className="space-y-2 max-h-72 overflow-auto pr-1">
            {(providerCatalogData.local_install_suggestions || []).map((suggestion) => (
              <div key={`${suggestion.provider}-${suggestion.capability}-${suggestion.title}`} className="rounded-md border border-border/25 bg-muted/10 p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{suggestion.title}</p>
                    <p className="text-[10px] text-muted-foreground">{suggestion.capability} · {suggestion.provider}</p>
                  </div>
                  <Badge variant="outline" className="text-[9px] border-sylion-amber/30 text-sylion-amber shrink-0">
                    propozycja
                  </Badge>
                </div>
                {suggestion.models?.length ? (
                  <p className="mt-1 text-[10px] text-sylion-blue truncate">{suggestion.models.join(", ")}</p>
                ) : null}
                <p className="mt-1 text-[10px] text-muted-foreground">{suggestion.install_hint || suggestion.recommended_when || "Dodaj provider w katalogu modeli."}</p>
              </div>
            ))}
            {(providerCatalogData.local_install_suggestions || []).length === 0 && (
              <div className="rounded-md border border-dashed border-border/30 p-4 text-center text-xs text-muted-foreground">
                Brak nowych propozycji z katalogu providerów
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card className="p-4 bg-[#0f1629] border-sylion-border" data-testid="secrets-provider-status">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-sylion-blue" />
            <h3 className="text-xs font-medium uppercase tracking-wider">
              Providerzy modeli i test połączenia
              <HelpTip text="Po wpisaniu klucza AEIS wykonuje smoke test providera i próbuje pobrać informacje o planie, modelach, limitach oraz budżecie API. Nie każdy provider udostępnia saldo albo limity subskrypcji przez API." />
            </h3>
          </div>
          <Button variant="outline" size="sm" onClick={() => refreshProviders()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(providersData.providers || []).filter((p) => p.ready || p.key_available).map((provider) => {
            const check = providerChecks[provider.provider];
            const connectionOk = check?.connection?.ok;
            return (
              <div key={provider.provider} className="rounded-md border border-border/30 bg-muted/10 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{provider.provider}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{provider.default_model}</p>
                    <p className={cn("text-[10px] mt-1", provider.ready ? "text-sylion-green" : "text-sylion-amber")}>
                      {provider.locality === "local" ? `runtime: ${provider.runtime_reachable ? "osięgalny" : "niedostępny"}` : provider.ready ? "klucz wykryty" : "brak klucza"}
                    </p>
                    {check && (
                      <p className={cn("text-[10px] mt-1", connectionOk ? "text-sylion-green" : "text-sylion-red")}>
                        test: {connectionOk ? `OK ${check.connection?.latency_ms ?? "?"} ms` : check.connection?.error || "błąd"}
                      </p>
                    )}
                    {check && (
                      <p className="text-[10px] mt-1 text-muted-foreground">
                        {check.key_info?.plan_inferred || "plan unknown"} · modele {check.key_info?.accessible_model_count ?? "?"}
                      </p>
                    )}
                  </div>
                  {provider.ready && provider.locality !== "local" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleProviderRetest(provider.provider, provider.default_model)}
                      disabled={testingProvider === provider.provider}
                    >
                      {testingProvider === provider.provider ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* ====== SUMMARY CARDS ====== */}
      <div className="grid grid-cols-3 gap-3">
        {summaryCards.map((stat) => {
          const SIcon = stat.icon;
          return (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                      {stat.label}
                      <HelpTip text={stat.tip} />
                    </p>
                    <p className={cn("text-xl font-semibold mt-1 font-mono", stat.color)}>{stat.value}</p>
                  </div>
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", stat.bgColor)}>
                    <SIcon className={cn("w-4 h-4", stat.color)} />
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* ====== SECRETS TABLE ====== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-xs font-medium text-muted-foreground">
              Zarejestrowane sekrety
              <HelpTip text="Lista sekretów z metadanymi: zakres, ostatnia rotacja, liczba dostępów. Same wartości NIGDY nie są pokazywane na tej stronie — tylko po explicit reveal z audit." />
            </h3>
          </div>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            Wartości są maskowane
          </span>
        </div>
        <div className="divide-y divide-border/20">
          {secrets.map((secret, idx) => {
            const scopeBadge = scopeBadgeStyles[secret.scope] || "border-border/50 text-muted-foreground bg-muted/20";
            const rotated = isRecentlyRotated(secret.last_rotated);
            return (
              <motion.div
                key={secret.name || idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.03, duration: 0.2 }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors"
              >
                {/* Masked name */}
                <EyeOff className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <span className="text-xs font-medium flex-1 min-w-0 truncate font-mono">
                  {maskName(secret.name)}
                </span>

                {/* Scope badge */}
                <Badge variant="outline" className={cn("text-[9px] shrink-0", scopeBadge)}>
                  {secret.scope}
                </Badge>

                {/* Last rotated */}
                <span className={cn(
                  "text-[10px] flex items-center gap-1 shrink-0 w-28 justify-end",
                  rotated ? "text-sylion-green" : "text-muted-foreground"
                )}>
                  <Clock className="w-2.5 h-2.5" />
                  {formatTimestamp(secret.last_rotated)}
                </span>

                {/* Access count */}
                <span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0 w-20 justify-end font-mono">
                  <Hash className="w-2.5 h-2.5" />
                  {secret.access_count || 0}
                </span>
              </motion.div>
            );
          })}

          {secrets.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Activity className="w-6 h-6 text-muted-foreground mb-2" />
              <p className="text-xs text-muted-foreground">Brak zarejestrowanych sekretów</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
