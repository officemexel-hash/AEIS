"use client";

import { Eye, EyeOff, Server, Trash2, Plus, HardDrive, Download, Cpu, CheckCircle2, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export type ApiKeyValidationStatus = "idle" | "testing" | "ok" | "error";

export interface ApiKeyEntry {
  id: string;
  provider: string;
  key: string;
  key_masked?: boolean;
  validation_status?: ApiKeyValidationStatus;
  validation_info?: {
    plan_inferred?: string;
    models_count?: number;
    rate_limits?: Record<string, string>;
    balance_usd?: number;
    credit_limit_usd?: number;
    sample_models?: string[];
  };
}

export interface HostingEntry {
  id: string;
  provider: string;
  fields: Record<string, string>;
}

type HostingValidationStatus = "idle" | "testing" | "ok" | "error";

export type LocalModelStatus = "not_installed" | "downloading" | "installed" | "error";

export interface LocalModelEntry {
  id: string;
  name: string;
  status: LocalModelStatus;
  error?: string;
}

export interface Step2Values {
  api_keys?: ApiKeyEntry[];
  hosting_providers?: HostingEntry[];
  local_models?: LocalModelEntry[];
}

const SUGGESTED_OLLAMA_MODELS: Array<{ name: string; size: string; description: string }> = [
  { name: "qwen2.5:7b-instruct", size: "4.7 GB", description: "Szybki uniwersalny — kod, rozmowa i rozumowanie" },
  { name: "qwen2.5:72b-instruct", size: "47 GB", description: "Najmocniejszy lokalny — wymaga 64+ GB RAM" },
  { name: "llama3.2:3b", size: "2.0 GB", description: "Najlżejszy — szybkie odpowiedzi, słabsze rozumowanie" },
  { name: "mistral:7b", size: "4.4 GB", description: "Dobry balans szybkości i jakości" },
  { name: "gemma2:9b", size: "5.4 GB", description: "Google — silne rozumowanie, wielojęzyczny" },
  { name: "phi3:mini", size: "2.3 GB", description: "Microsoft — mały, ale skuteczny w kodzie" },
  { name: "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M", size: "6.7 GB", description: "Polski model domenowy — granty, urzędy, regulaminy" },
  { name: "PRIHLOP/PLLuM:12B-chat-Q8_0", size: "~12-13 GB", description: "Polski model publiczny — administracja i język formalny" },
];

// F-026: full provider catalogue. Hint copy after each label tells the operator
// when to bother adding the key. Native = direct provider; OAI-compat = uses
// OpenAI client + custom base_url; aggregator = single key for many models.
const AI_PROVIDERS: Array<{
  id: string;
  label: string;
  placeholder: string;
  hint?: string;
}> = [
  { id: "anthropic", label: "Anthropic (Claude)", placeholder: "sk-ant-…", hint: "Bezpośredni provider — Claude Sonnet/Opus/Haiku" },
  { id: "openai", label: "OpenAI", placeholder: "sk-proj-… / sk-…", hint: "Bezpośredni provider — GPT-4o, o1, o3, GPT-5" },
  { id: "openrouter", label: "OpenRouter", placeholder: "sk-or-…", hint: "Agregator — ~100 modeli z jednym kluczem" },
  { id: "google", label: "Google AI (Gemini)", placeholder: "AIza…", hint: "Bezpośredni provider — Gemini 2.5 Pro / Flash" },
  { id: "perplexity", label: "Perplexity", placeholder: "pplx-…", hint: "Wyszukiwanie z citations — Sonar models" },
  { id: "zai", label: "z.ai (GLM)", placeholder: "…", hint: "Bezpośredni provider — GLM-4 Plus, kodowanie + rozumowanie" },
  { id: "moonshot", label: "Moonshot (Kimi)", placeholder: "sk-…", hint: "Bezpośredni provider — Kimi K2, długi kontekst" },
  { id: "deepseek", label: "DeepSeek", placeholder: "sk-…", hint: "Zgodny z OpenAI — R1 reasoning, V3 chat" },
  { id: "xai", label: "xAI / Grok", placeholder: "xai-…", hint: "Bezpośredni provider — Grok 4, integracja X realtime" },
  { id: "mistral", label: "Mistral AI", placeholder: "…", hint: "Bezpośredni provider — Mistral Large, Codestral" },
  { id: "groq", label: "Groq", placeholder: "gsk_…", hint: "Zgodny z OpenAI — szybka inferencja Llama/Qwen" },
  { id: "cohere", label: "Cohere", placeholder: "…", hint: "Bezpośredni provider — Command R+, RAG" },
  { id: "fireworks", label: "Fireworks AI", placeholder: "fw-…", hint: "Zgodny z OpenAI — hosting modeli open-source" },
  { id: "together", label: "Together AI", placeholder: "…", hint: "Zgodny z OpenAI — agregator open-source" },
  { id: "ollama", label: "Ollama (lokalny)", placeholder: "http://localhost:11434", hint: "Lokalny — żaden klucz nie jest potrzebny" },
];

type HostingFieldDef = { id: string; label: string; placeholder: string; secret?: boolean };
type HostingProviderDef = { id: string; label: string; fields: HostingFieldDef[] };

const HOSTING_PROVIDERS: HostingProviderDef[] = [
  {
    id: "cloudflare",
    label: "Cloudflare",
    fields: [
      { id: "token", label: "API Token", placeholder: "…", secret: true },
      { id: "account_id", label: "Account ID", placeholder: "…" },
    ],
  },
  {
    id: "aws",
    label: "AWS",
    fields: [
      { id: "access_key", label: "Access Key ID", placeholder: "AKIA…", secret: true },
      { id: "secret_key", label: "Secret Access Key", placeholder: "…", secret: true },
      { id: "region", label: "Region", placeholder: "us-east-1" },
    ],
  },
  {
    id: "vercel",
    label: "Vercel",
    fields: [
      { id: "token", label: "Token", placeholder: "…", secret: true },
      { id: "team_id", label: "Team ID", placeholder: "team_…" },
    ],
  },
  {
    id: "render",
    label: "Render",
    fields: [{ id: "api_key", label: "API Key", placeholder: "…", secret: true }],
  },
  {
    id: "flyio",
    label: "Fly.io",
    fields: [{ id: "token", label: "Token", placeholder: "FlyV1 …", secret: true }],
  },
  {
    id: "railway",
    label: "Railway",
    fields: [{ id: "api_key", label: "API Key", placeholder: "…", secret: true }],
  },
  {
    id: "digitalocean",
    label: "DigitalOcean",
    fields: [{ id: "token", label: "Personal Access Token", placeholder: "dop_v1_…", secret: true }],
  },
  // F-022: Hetzner + OVH — dwa najpopularniejsze europejskie VPS providery,
  // wcześniej brakowali na liście. Hetzner Cloud używa API tokenu z konsoli;
  // OVH (Public Cloud / VPS) wymaga app key + app secret + consumer key
  // (OAuth-style) — pełen 3-fields setup.
  {
    id: "hetzner",
    label: "Hetzner Cloud",
    fields: [
      { id: "token", label: "API Token", placeholder: "…", secret: true },
      { id: "project", label: "Project (opcjonalne)", placeholder: "default" },
    ],
  },
  {
    id: "ovh",
    label: "OVHcloud",
    fields: [
      { id: "endpoint", label: "Endpoint", placeholder: "ovh-eu" },
      { id: "application_key", label: "Application Key", placeholder: "…", secret: true },
      { id: "application_secret", label: "Application Secret", placeholder: "…", secret: true },
      { id: "consumer_key", label: "Consumer Key", placeholder: "…", secret: true },
    ],
  },
  {
    id: "custom",
    label: "Inny dostawca",
    fields: [
      { id: "name", label: "Nazwa", placeholder: "…" },
      { id: "token", label: "Token / klucz", placeholder: "…", secret: true },
      { id: "endpoint", label: "Endpoint (opcjonalne)", placeholder: "https://…" },
    ],
  },
];

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function isMaskedSecret(value: string | undefined, keyMasked?: boolean): boolean {
  const trimmed = value?.trim() ?? "";
  return Boolean(keyMasked) || trimmed === "***" || trimmed.includes("...") || trimmed.includes("…");
}

interface Props {
  values: Step2Values;
  onChange: (patch: Step2Values) => void;
}

export function Step2Providers({ values, onChange }: Props) {
  const [keys, setKeys] = useState<ApiKeyEntry[]>(() => values.api_keys ?? []);
  const [hosting, setHosting] = useState<HostingEntry[]>(() => values.hosting_providers ?? []);
  const [localModels, setLocalModels] = useState<LocalModelEntry[]>(() => values.local_models ?? []);
  const [customModelName, setCustomModelName] = useState("");
  const [revealKey, setRevealKey] = useState<Record<string, boolean>>({});
  const [revealHosting, setRevealHosting] = useState<Record<string, boolean>>({});
  // F-018: surface Ollama models present on disk so user can mark them as
  // installed without forcing a re-pull. Source of truth =
  // GET /api/v1/ai-providers/local-models/installed proxied to ollama /api/tags.
  const [installedOnDisk, setInstalledOnDisk] = useState<Array<{ name: string; size_gb: number }>>([]);
  const [installedReachable, setInstalledReachable] = useState<boolean>(false);

  // Local models handlers
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
  const isModelInList = (name: string) => localModels.some((m) => m.name === name);

  // F-018: fetch already-installed Ollama models on mount and reconcile state.
  // F-019b: never call parent onChange() from inside a setState callback —
  // React surfaces "Cannot update a component while rendering a different
  // component" because the setter runs during render. We compute the next
  // value imperatively against the latest snapshot, then setState + onChange
  // outside any React-managed callback.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/v1/ai-providers/local-models/installed`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        const models: Array<{ name: string; size_gb: number }> = data?.models ?? [];
        setInstalledOnDisk(models);
        setInstalledReachable(Boolean(data?.ollama_reachable));
        // Reconcile against the current value in state ref via setState callback
        // for THE READ ONLY, then schedule the update via a microtask so that
        // parent onChange runs after this render commits, not during it.
        const current = localModels;
        const byName = new Map(current.map((m) => [m.name, m] as const));
        const installedNames = new Set(models.map((m) => m.name));
        let mutated = false;
        for (const existing of current) {
          if (existing.status === "installed" && !installedNames.has(existing.name)) {
            let patch: Partial<LocalModelEntry> = {
              status: "error",
              error: "Model oznaczony jako zainstalowany, ale nie występuje w Ollama /installed.",
            };
            try {
              const statusRes = await fetch(
                `${apiBase}/api/v1/ai-providers/local-models/pull-status/${encodeURIComponent(existing.name)}`,
              );
              if (statusRes.ok) {
                const status = await statusRes.json();
                if (status?.status === "pulling") {
                  patch = { status: "downloading", error: undefined };
                } else if (status?.status === "error") {
                  patch = { status: "error", error: String(status?.error ?? "Ollama pull failed") };
                }
              }
            } catch {
              // leave the explicit not-on-disk error
            }
            byName.set(existing.name, { ...existing, ...patch });
            mutated = true;
          }
        }
        for (const m of models) {
          const existing = byName.get(m.name);
          if (!existing) {
            byName.set(m.name, { id: newId(), name: m.name, status: "installed" });
            mutated = true;
          } else if (existing.status !== "installed") {
            byName.set(m.name, { ...existing, status: "installed", error: undefined });
            mutated = true;
          }
        }
        if (!mutated) return;
        const updated = Array.from(byName.values());
        setLocalModels(updated);
        // Defer parent state update to avoid "setState during render" warning.
        queueMicrotask(() => {
          if (!cancelled) onChange({ local_models: updated });
        });
      } catch {
        // backend offline or endpoint missing — keep static suggestions only
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  const updateModel = (id: string, patch: Partial<LocalModelEntry>) => {
    setLocalModels((prev) => {
      const updated = prev.map((m) => (m.id === id ? { ...m, ...patch } : m));
      queueMicrotask(() => onChange({ local_models: updated }));
      return updated;
    });
  };

  const removeModel = (id: string) => {
    const updated = localModels.filter((m) => m.id !== id);
    setLocalModels(updated);
    onChange({ local_models: updated });
  };

  // F-020: real model pull. The backend returns immediately and exposes
  // progress through /pull-status/{model}. Do not mark a model installed until
  // Ollama reports completion and /installed confirms it exists on disk.
  const pullModel = async (name: string) => {
    const existing = localModels.find((m) => m.name === name);
    if (existing && existing.status !== "error") return;
    const id = existing?.id ?? newId();
    if (existing) {
      updateModel(id, { status: "downloading", error: undefined });
    } else {
      const entry: LocalModelEntry = { id, name, status: "downloading" };
      const updated = [...localModels, entry];
      setLocalModels(updated);
      onChange({ local_models: updated });
    }

    const refreshInstalled = async (): Promise<boolean> => {
      try {
        const r = await fetch(`${apiBase}/api/v1/ai-providers/local-models/installed`);
        if (!r.ok) return false;
        const j = await r.json();
        const models: Array<{ name: string }> = j?.models ?? [];
        const present = models.some((m) => m.name === name);
        setInstalledOnDisk(j?.models ?? []);
        if (present) {
          updateModel(id, { status: "installed" });
          return true;
        }
      } catch {
        // ignore transient errors
      }
      return false;
    };

    try {
      const res = await fetch(`${apiBase}/api/v1/ai-providers/local-models/pull`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: name, stream: false }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        updateModel(id, {
          status: "error",
          error: `HTTP ${res.status}${body ? `: ${body.slice(0, 100)}` : ""}`,
        });
        return;
      }
      const start = await res.json().catch(() => ({}));
      if (start?.status === "error") {
        updateModel(id, { status: "error", error: String(start?.error ?? "Ollama pull failed") });
        return;
      }

      const statusUrl = `${apiBase}/api/v1/ai-providers/local-models/pull-status/${encodeURIComponent(name)}`;
      for (;;) {
        const statusRes = await fetch(statusUrl);
        if (statusRes.ok) {
          const status = await statusRes.json();
          if (status?.status === "error") {
            updateModel(id, { status: "error", error: String(status?.error ?? "Ollama pull failed") });
            return;
          }
          if (status?.status === "completed") {
            if (await refreshInstalled()) return;
            updateModel(id, {
              status: "error",
              error: "Ollama reported completion, but model is not present in /installed.",
            });
            return;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    } catch (err) {
      updateModel(id, { status: "error", error: err instanceof Error ? err.message : "Błąd sieci" });
    }
  };

  const pullCustomModel = () => {
    const name = customModelName.trim();
    if (!name || isModelInList(name)) return;
    void pullModel(name);
    setCustomModelName("");
  };

  // F-021/F-023: per-key validation status (idle | testing | ok | error) +
  // enrichment data (plan tier, accessible models, rate limits) so onboarding
  // can show "Plan: build_tier · 12 models · 4000 req/min" instead of just OK.
  interface KeyValidationState {
    status: "idle" | "testing" | "ok" | "error";
    message?: string;
    preview?: string;
    info?: {
      plan_inferred?: string;
      models_count?: number;
      rate_limits?: Record<string, string>;
      balance_usd?: number;
      credit_limit_usd?: number;
      sample_models?: string[];
    };
  }
  const [keyValidation, setKeyValidation] = useState<Record<string, KeyValidationState>>({});

  interface HostingValidationState {
    status: HostingValidationStatus;
    message?: string;
    account_label?: string;
  }
  const [hostingValidation, setHostingValidation] = useState<Record<string, HostingValidationState>>({});

  // Debounced validator — pings backend `/api/v1/ai-providers/test/{provider}`
  // with the typed key in body (F-023) to confirm it's real, then fetches
  // /key-info for enrichment.
  useEffect(() => {
    const timers: Array<ReturnType<typeof setTimeout>> = [];
    for (const k of keys) {
      const provider = k.provider?.trim().toLowerCase();
      const key = k.key?.trim();
      if (isMaskedSecret(key, k.key_masked)) {
        setKeyValidation((prev) => ({
          ...prev,
          [k.id]: {
            status: k.validation_status === "ok" ? "ok" : "idle",
            message: "Klucz jest zapisany w backendzie i ukryty w UI.",
            info: k.validation_info,
          },
        }));
        continue;
      }
      if (!provider || !key || key.length < 10) {
        setKeyValidation((prev) => {
          if (prev[k.id]?.status === "idle" && !prev[k.id]?.message) return prev;
          return { ...prev, [k.id]: { status: "idle" } };
        });
        persistKeyValidation(k.id, "idle");
        continue;
      }
      const t = setTimeout(async () => {
        setKeyValidation((prev) => ({ ...prev, [k.id]: { status: "testing" } }));
        try {
          const res = await fetch(`${apiBase}/api/v1/ai-providers/test/${provider}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: "ping", max_tokens: 8, api_key: key }),
          });
          if (!res.ok) {
            const body = await res.text().catch(() => "");
            setKeyValidation((prev) => ({
              ...prev,
              [k.id]: { status: "error", message: `HTTP ${res.status}${body ? `: ${body.slice(0, 80)}` : ""}` },
            }));
            persistKeyValidation(k.id, "error");
            return;
          }
          const data = await res.json();
          // After successful validation, fetch enriched key info (best-effort).
          let info: KeyValidationState["info"] = undefined;
          try {
            const ir = await fetch(`${apiBase}/api/v1/ai-providers/key-info/${provider}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ api_key: key }),
            });
            if (ir.ok) {
              const ij = await ir.json();
              info = {
                plan_inferred: ij?.plan_inferred,
                models_count: Array.isArray(ij?.accessible_models) ? ij.accessible_models.length : undefined,
                rate_limits: ij?.rate_limits,
                balance_usd: ij?.balance_usd,
                credit_limit_usd: ij?.credit_limit_usd,
                sample_models: Array.isArray(ij?.accessible_models)
                  ? (ij.accessible_models as Array<{ id?: string }>)
                      .map((m) => m?.id ?? "")
                      .filter(Boolean)
                      .slice(0, 5)
                  : undefined,
              };
            }
          } catch {
            // info is optional
          }
          setKeyValidation((prev) => ({
            ...prev,
            [k.id]: {
              status: "ok",
              preview: data?.response?.text ? String(data.response.text).slice(0, 40) : "OK",
              info,
            },
          }));
          persistKeyValidation(k.id, "ok", info);
        } catch (err) {
          setKeyValidation((prev) => ({
            ...prev,
            [k.id]: {
              status: "error",
              message: err instanceof Error ? err.message : "Błąd sieci (backend offline?)",
            },
          }));
        }
      }, 800);
      timers.push(t);
    }
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(keys.map((k) => ({ id: k.id, p: k.provider, k: k.key }))), apiBase]);

  // API key handlers
  const addKey = () => {
    const updated = [...keys, { id: newId(), provider: "", key: "" }];
    setKeys(updated);
    onChange({ api_keys: updated });
  };
  const removeKey = (id: string) => {
    const updated = keys.filter((r) => r.id !== id);
    setKeys(updated);
    onChange({ api_keys: updated });
    setKeyValidation((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };
  const updateKey = (id: string, patch: Partial<ApiKeyEntry>) => {
    const updated = keys.map((r) => (r.id === id ? { ...r, ...patch } : r));
    setKeys(updated);
    onChange({ api_keys: updated });
  };

  const persistKeyValidation = (
    id: string,
    status: ApiKeyValidationStatus,
    info?: ApiKeyEntry["validation_info"],
  ) => {
    setKeys((prev) => {
      const updated = prev.map((r) =>
        r.id === id ? { ...r, validation_status: status, validation_info: info } : r,
      );
      queueMicrotask(() => onChange({ api_keys: updated }));
      return updated;
    });
  };

  // Hosting handlers
  const addHosting = () => {
    const updated = [...hosting, { id: newId(), provider: "", fields: {} }];
    setHosting(updated);
    onChange({ hosting_providers: updated });
  };
  const removeHosting = (id: string) => {
    const updated = hosting.filter((r) => r.id !== id);
    setHosting(updated);
    onChange({ hosting_providers: updated });
  };
  const updateHostingProvider = (id: string, provider: string) => {
    const updated = hosting.map((r) => (r.id === id ? { ...r, provider, fields: {} } : r));
    setHosting(updated);
    onChange({ hosting_providers: updated });
  };
  const updateHostingField = (id: string, field: string, value: string) => {
    const updated = hosting.map((r) =>
      r.id === id ? { ...r, fields: { ...r.fields, [field]: value } } : r,
    );
    setHosting(updated);
    onChange({ hosting_providers: updated });
  };

  useEffect(() => {
    const timers: Array<ReturnType<typeof setTimeout>> = [];
    for (const row of hosting) {
      const provider = row.provider?.trim().toLowerCase();
      const hasAnyField = Object.values(row.fields ?? {}).some((value) => value.trim().length > 0);
      if (!provider || !hasAnyField) {
        setHostingValidation((prev) => ({ ...prev, [row.id]: { status: "idle" } }));
        continue;
      }

      const timer = setTimeout(async () => {
        setHostingValidation((prev) => ({ ...prev, [row.id]: { status: "testing" } }));
        try {
          const res = await fetch(`${apiBase}/api/v1/ai-providers/hosting/test/${provider}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fields: row.fields ?? {} }),
          });
          if (!res.ok) {
            const body = await res.text().catch(() => "");
            setHostingValidation((prev) => ({
              ...prev,
              [row.id]: { status: "error", message: `HTTP ${res.status}${body ? `: ${body.slice(0, 120)}` : ""}` },
            }));
            return;
          }
          const data = await res.json();
          setHostingValidation((prev) => ({
            ...prev,
            [row.id]: data?.ok
              ? {
                  status: "ok",
                  message: data?.message ?? "Połączenie działa",
                  account_label: data?.account_label,
                }
              : {
                  status: "error",
                  message: data?.error ?? data?.message ?? "Nie udało się zweryfikować dostawcy hostingu",
                },
          }));
        } catch (err) {
          setHostingValidation((prev) => ({
            ...prev,
            [row.id]: {
              status: "error",
              message: err instanceof Error ? err.message : "Błąd sieci (backend offline?)",
            },
          }));
        }
      }, 700);
      timers.push(timer);
    }
    return () => {
      timers.forEach(clearTimeout);
    };
  }, [apiBase, hosting]);

  return (
    <div className="space-y-8">
      <div className="rounded-md border border-border bg-muted/10 p-3 text-xs text-muted-foreground">
        <Server className="mr-1 inline h-3 w-3" />
        Klucze przechowywane są lokalnie w przeglądarce podczas konfiguracji. Trafiają do bezpiecznego magazynu dopiero po zakończeniu instalacji.
      </div>

      {/* API Keys */}
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Klucze API modeli językowych</h2>
          <p className="text-xs text-muted-foreground">
            Dodaj klucze do providerów, których chcesz używać. Ten krok jest opcjonalny.
          </p>
        </div>

        {keys.length === 0 ? (
          <p className="rounded-md border border-dashed border-border py-4 text-center text-xs text-muted-foreground">
            Brak kluczy. Kliknij przycisk poniżej, aby dodać.
          </p>
        ) : (
          <div className="space-y-3">
            {keys.map((row) => {
              const providerDef = AI_PROVIDERS.find((p) => p.id === row.provider);
              const isRevealed = revealKey[row.id] === true;
              const validation = keyValidation[row.id];
              return (
                <div
                  key={row.id}
                  className={cn(
                    "flex flex-col gap-2 rounded-md border p-3 transition",
                    validation?.status === "ok" && "border-emerald-500/40 bg-emerald-500/5",
                    validation?.status === "error" && "border-destructive/40 bg-destructive/5",
                    validation?.status === "testing" && "border-sylion-blue/40 bg-sylion-blue/5",
                    !validation || validation.status === "idle"
                      ? "border-border"
                      : "",
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex flex-1 flex-col gap-2 sm:flex-row">
                      <select
                        value={row.provider}
                        onChange={(e) => updateKey(row.id, { provider: e.target.value, key: "" })}
                        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:border-sylion-blue/60 sm:w-48"
                        data-testid={`step2-provider-${row.id}`}
                      >
                        <option value="">— wybierz provider —</option>
                        {AI_PROVIDERS.map((p) => (
                          <option key={p.id} value={p.id} title={p.hint}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                      <div className="relative flex-1">
                        {providerDef?.hint ? (
                          <p className="absolute -top-4 right-0 text-[10px] text-muted-foreground/70">
                            {providerDef.hint}
                          </p>
                        ) : null}
                        <input
                          type={isRevealed ? "text" : "password"}
                          value={row.key}
                          onChange={(e) =>
                            updateKey(row.id, {
                              key: e.target.value,
                              key_masked: false,
                              validation_status: "idle",
                              validation_info: undefined,
                            })
                          }
                          placeholder={providerDef?.placeholder ?? "klucz / URL"}
                          className="w-full rounded-md border border-border bg-background px-3 py-1.5 pr-10 font-mono text-sm outline-none transition focus:border-sylion-blue/60"
                          data-testid={`step2-key-${row.id}`}
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setRevealKey((r) => ({ ...r, [row.id]: !r[row.id] }))
                          }
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          aria-label={isRevealed ? "Ukryj klucz" : "Pokaż klucz"}
                        >
                          {isRevealed ? (
                            <EyeOff className="h-3.5 w-3.5" />
                          ) : (
                            <Eye className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeKey(row.id)}
                      className="mt-1 text-muted-foreground hover:text-destructive"
                      aria-label="Usuń klucz"
                      data-testid={`step2-remove-${row.id}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  {/* F-021: validation badge — gives operator immediate feedback whether the key actually works. */}
                  {validation && validation.status !== "idle" ? (
                    <div
                      className="flex items-center gap-1.5 text-[11px]"
                      data-testid={`step2-validation-${row.id}`}
                      data-validation-status={validation.status}
                    >
                      {validation.status === "testing" ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin text-sylion-blue" />
                          <span className="text-sylion-blue/80">SprawdŹam klucz…</span>
                        </>
                      ) : validation.status === "ok" ? (
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-1.5">
                            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                            <span className="text-emerald-300">
                              Klucz działa ✓ {validation.preview ? `(${validation.preview})` : ""}
                            </span>
                          </div>
                          {validation.info ? (
                            <div className="ml-4 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-emerald-200/80">
                              {validation.info.plan_inferred && validation.info.plan_inferred !== "unknown" ? (
                                <span>Plan: <span className="font-mono">{validation.info.plan_inferred}</span></span>
                              ) : null}
                              {validation.info.models_count !== undefined ? (
                                <span>{validation.info.models_count} modeli</span>
                              ) : null}
                              {validation.info.rate_limits?.["requests-limit"] ? (
                                <span>Limit: {validation.info.rate_limits["requests-limit"]} req/min</span>
                              ) : null}
                              {validation.info.balance_usd !== undefined ? (
                                <span>Saldo: ${Number(validation.info.balance_usd).toFixed(2)}{validation.info.credit_limit_usd ? ` / $${Number(validation.info.credit_limit_usd).toFixed(2)}` : ""}</span>
                              ) : null}
                              {validation.info.sample_models?.length ? (
                                <span className="text-[10px] opacity-70" title={validation.info.sample_models.join(", ")}>
                                  {validation.info.sample_models.slice(0, 3).join(", ")}{(validation.info.models_count ?? 0) > 3 ? "…" : ""}
                                </span>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      ) : (
                        <>
                          <span className="text-destructive">⚠</span>
                          <span className="text-destructive/90">
                            Klucz nie działa: {validation.message ?? "nieznany błąd"}
                          </span>
                        </>
                      )}
                    </div>
                  ) : row.provider && row.key && row.key.trim().length > 0 && row.key.trim().length < 10 ? (
                    <div className="text-[11px] text-amber-300/80">
                      Klucz wygląda na za krótki — poczekaj aż wkleisz całość…
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}

        <button
          type="button"
          onClick={addKey}
          className="flex items-center gap-1.5 rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground transition hover:border-sylion-blue/60 hover:text-foreground"
          data-testid="step2-add-key"
        >
          <Plus className="h-3.5 w-3.5" />
          Dodaj kolejny klucz API
        </button>
      </section>

      <hr className="border-border" />

      {/* Local Ollama models */}
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Modele lokalne (Ollama)</h2>
          <p className="text-xs text-muted-foreground">
            Pobierz modele lokalne — nie wymagają API keys, działają offline. Wybierz z sugerowanych lub wpisz własną nazwę.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {SUGGESTED_OLLAMA_MODELS.map((model) => {
            const existing = localModels.find((m) => m.name === model.name);
            const status = existing?.status;
            const isPending = status === "downloading";
            const isInstalled = status === "installed";
            const isError = status === "error";
            return (
              <div
                key={model.name}
                className={cn(
                  "flex items-start justify-between gap-2 rounded-md border p-3 text-xs transition",
                  isInstalled
                    ? "border-emerald-500/40 bg-emerald-500/5"
                    : isError
                      ? "border-destructive/40 bg-destructive/5"
                      : "border-border hover:border-sylion-blue/50",
                )}
              >
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="font-mono font-semibold">{model.name}</span>
                    <span className="text-[10px] text-muted-foreground">· {model.size}</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground">{model.description}</p>
                  {isError && existing?.error ? (
                    <p className="text-[10px] text-destructive">Błąd: {existing.error}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => pullModel(model.name)}
                  disabled={isPending || isInstalled}
                  className={cn(
                    "flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold transition",
                    isInstalled
                      ? "cursor-default bg-emerald-500/15 text-emerald-300"
                      : isPending
                        ? "cursor-not-allowed bg-sylion-blue/20 text-sylion-blue"
                        : "border border-border text-foreground hover:bg-sylion-blue/15 hover:text-sylion-blue",
                  )}
                  data-testid={`step2-pull-model-${model.name}`}
                >
                  {isInstalled ? (
                    <>
                      <CheckCircle2 className="h-3 w-3" /> Zainstalowany
                    </>
                  ) : isPending ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" /> Pobieranie…
                    </>
                  ) : (
                    <>
                      <Download className="h-3 w-3" /> Pobierz
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Custom model */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={customModelName}
            onChange={(e) => setCustomModelName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                pullCustomModel();
              }
            }}
            placeholder="Inny model (np. codellama:13b, deepseek-coder:6.7b)"
            className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono outline-none transition focus:border-sylion-blue/60"
            data-testid="step2-custom-model"
          />
          <button
            type="button"
            onClick={pullCustomModel}
            disabled={!customModelName.trim() || isModelInList(customModelName.trim())}
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:border-sylion-blue/60 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="step2-pull-custom"
          >
            <Download className="h-3.5 w-3.5" />
            Pobierz
          </button>
        </div>

        {/* Active downloads + manual entries */}
        {localModels.length > 0 ? (
          <div className="space-y-1.5 rounded-md border border-border bg-card/40 p-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Twoje lokalne modele ({localModels.length})
            </p>
            <ul className="space-y-1">
              {localModels.map((m) => (
                <li
                  key={m.id}
                  className="flex items-center justify-between gap-2 text-xs"
                  data-testid={`step2-local-model-${m.id}`}
                >
                  <span className="flex items-center gap-1.5">
                    {m.status === "downloading" ? (
                      <Loader2 className="h-3 w-3 animate-spin text-sylion-blue" />
                    ) : m.status === "installed" ? (
                      <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                    ) : m.status === "error" ? (
                      <span className="h-3 w-3 rounded-full bg-destructive" />
                    ) : (
                      <Cpu className="h-3 w-3 text-muted-foreground" />
                    )}
                    <span className="font-mono">{m.name}</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => removeModel(m.id)}
                    className="text-muted-foreground hover:text-destructive"
                    aria-label="Usuń model z listy"
                    data-testid={`step2-remove-model-${m.id}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <hr className="border-border" />

      {/* Hosting providers */}
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Dostawcy hostingu (opcjonalne)</h2>
          <p className="text-xs text-muted-foreground">
            Połącz konta Cloudflare, AWS, Vercel, Render, ... abyśmy mogli proponować ich w deploymencie.
          </p>
        </div>

        {hosting.length === 0 ? (
          <p className="rounded-md border border-dashed border-border py-4 text-center text-xs text-muted-foreground">
            Brak dostawców hostingu. Możesz je dodać teraz lub później.
          </p>
        ) : (
          <div className="space-y-4">
            {hosting.map((row) => {
              const def = HOSTING_PROVIDERS.find((p) => p.id === row.provider);
              return (
                <div key={row.id} className="space-y-3 rounded-md border border-border p-3">
                  <div className="flex items-center gap-2">
                    <select
                      value={row.provider}
                      onChange={(e) => updateHostingProvider(row.id, e.target.value)}
                      className="flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:border-sylion-blue/60"
                      data-testid={`step2-hosting-provider-${row.id}`}
                    >
                      <option value="">— wybierz dostawcę —</option>
                      {HOSTING_PROVIDERS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => removeHosting(row.id)}
                      className="text-muted-foreground hover:text-destructive"
                      aria-label="Usuń dostawcę"
                      data-testid={`step2-remove-hosting-${row.id}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  {def
                    ? def.fields.map((field) => {
                        const revealId = `${row.id}-${field.id}`;
                        const isRevealed = revealHosting[revealId] === true;
                        return (
                          <div key={field.id} className="space-y-1">
                            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              {field.label}
                            </label>
                            <div className="relative">
                              <input
                                type={field.secret && !isRevealed ? "password" : "text"}
                                value={row.fields[field.id] ?? ""}
                                onChange={(e) =>
                                  updateHostingField(row.id, field.id, e.target.value)
                                }
                                placeholder={field.placeholder}
                                className={cn(
                                  "w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none transition focus:border-sylion-blue/60",
                                  field.secret && "pr-10 font-mono",
                                )}
                                data-testid={`step2-hosting-${row.id}-${field.id}`}
                              />
                              {field.secret ? (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setRevealHosting((r) => ({
                                      ...r,
                                      [revealId]: !r[revealId],
                                    }))
                                  }
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                  aria-label={isRevealed ? "Ukryj" : "Pokaż"}
                                >
                                  {isRevealed ? (
                                    <EyeOff className="h-3.5 w-3.5" />
                                  ) : (
                                    <Eye className="h-3.5 w-3.5" />
                                  )}
                                </button>
                              ) : null}
                            </div>
                          </div>
                        );
                      })
                    : null}

                  {hostingValidation[row.id]?.status && hostingValidation[row.id]?.status !== "idle" ? (
                    <div
                      className="flex items-center gap-1.5 text-[11px]"
                      data-testid={`step2-hosting-validation-${row.id}`}
                      data-validation-status={hostingValidation[row.id].status}
                    >
                      {hostingValidation[row.id].status === "testing" ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin text-sylion-blue" />
                          <span className="text-sylion-blue/80">SprawdŹam dostawcę hostingu…</span>
                        </>
                      ) : hostingValidation[row.id].status === "ok" ? (
                        <>
                          <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                          <span className="text-emerald-300">
                            Hosting działa ✓ {hostingValidation[row.id].account_label ? `(${hostingValidation[row.id].account_label})` : ""}
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="text-destructive">⚠</span>
                          <span className="text-destructive/90">
                            Hosting nie działa: {hostingValidation[row.id].message ?? "nieznany błąd"}
                          </span>
                        </>
                      )}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}

        <button
          type="button"
          onClick={addHosting}
          className="flex items-center gap-1.5 rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground transition hover:border-sylion-blue/60 hover:text-foreground"
          data-testid="step2-add-hosting"
        >
          <HardDrive className="h-3.5 w-3.5" />
          Dodaj dostawcę hostingu
        </button>
      </section>
    </div>
  );
}
