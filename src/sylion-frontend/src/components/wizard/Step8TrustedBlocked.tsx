"use client";

import { Ban, ShieldCheck, Info, Plus, X } from "lucide-react";
import { useMemo } from "react";
import type { ApiKeyEntry, LocalModelEntry } from "./Step2Providers";
import { cn } from "@/lib/utils";

export const PROVIDERS: Array<{ id: string; label: string; tier: "core" | "extended" }> = [
  { id: "anthropic", label: "Anthropic", tier: "core" },
  { id: "openai", label: "OpenAI", tier: "core" },
  { id: "perplexity", label: "Perplexity", tier: "core" },
  { id: "zai", label: "z.ai (GLM)", tier: "core" },
  { id: "google", label: "Google AI", tier: "core" },
  { id: "ollama", label: "Ollama (lokalna)", tier: "core" },
  { id: "moonshot", label: "Moonshot (Kimi)", tier: "extended" },
  { id: "xai", label: "xAI (Grok)", tier: "extended" },
  { id: "openrouter", label: "OpenRouter", tier: "extended" },
  { id: "deepseek", label: "DeepSeek", tier: "extended" },
  { id: "mistral", label: "Mistral AI", tier: "extended" },
  { id: "groq", label: "Groq", tier: "extended" },
  { id: "cohere", label: "Cohere", tier: "extended" },
  { id: "fireworks", label: "Fireworks AI", tier: "extended" },
  { id: "together", label: "Together AI", tier: "extended" },
];

export interface Step8Values {
  trusted_providers?: string[];
  blocked_providers?: string[];
  // F-024: providers that are auto-trusted because user added an API key in
  // Step 2 or has Ollama running. Stored separately from `trusted_providers`
  // (which are EXPLICIT manual additions on top of auto-trust).
  auto_trusted_providers?: string[];
}

interface Step8Context {
  apiKeys?: ApiKeyEntry[];
  localModels?: LocalModelEntry[];
}

interface Props {
  values: Step8Values;
  context?: Step8Context;
  onChange: (patch: Step8Values) => void;
}

export function Step8TrustedBlocked({ values, context, onChange }: Props) {
  const trusted = values.trusted_providers ?? [];
  const blocked = values.blocked_providers ?? [];
  const apiKeys = context?.apiKeys ?? [];
  const localModels = context?.localModels ?? [];

  // F-024 auto-trust derivation: anything user already configured in earlier
  // steps is implicitly trusted. We don't ask user to confirm again.
  const autoTrusted = useMemo<string[]>(() => {
    const set = new Set<string>();
    for (const k of apiKeys) {
      const provider = (k.provider || "").trim().toLowerCase();
      if (
        provider &&
        k.key &&
        k.key.trim().length >= 10 &&
        k.validation_status !== "error" &&
        k.validation_status !== "testing"
      ) {
        // Map legacy provider ids used by older wizard payloads.
        const aliased = provider === "moonshot_kimi" ? "moonshot" : provider;
        set.add(aliased);
      }
    }
    if (localModels.some((m) => m.status === "installed")) {
      set.add("ollama");
    }
    return Array.from(set);
  }, [apiKeys, localModels]);

  // Pełna lista: auto-trusted + ręcznie dodane przez usera (deduped).
  const effectiveTrusted = useMemo(
    () => Array.from(new Set([...autoTrusted, ...trusted])).filter((id) => !blocked.includes(id)),
    [autoTrusted, trusted, blocked],
  );

  const onAddManualTrust = (id: string) => {
    if (autoTrusted.includes(id) || trusted.includes(id)) return;
    onChange({
      trusted_providers: [...trusted, id],
      blocked_providers: blocked.filter((p) => p !== id),
    });
  };

  const onRemoveManualTrust = (id: string) => {
    onChange({ trusted_providers: trusted.filter((p) => p !== id) });
  };

  const onAddBlock = (id: string) => {
    if (blocked.includes(id)) return;
    onChange({
      blocked_providers: [...blocked, id],
      trusted_providers: trusted.filter((p) => p !== id),
    });
  };

  const onRemoveBlock = (id: string) => {
    onChange({ blocked_providers: blocked.filter((p) => p !== id) });
  };

  // Providery dostępne do RĘCZNEGO dodania jako trusted (czyli: nie auto, nie blocked).
  const addableTrusted = PROVIDERS.filter(
    (p) => !autoTrusted.includes(p.id) && !trusted.includes(p.id) && !blocked.includes(p.id),
  );
  // Providery dostępne do zablokowania (te których jeszcze nie zablokowaliśmy).
  const addableBlocks = PROVIDERS.filter((p) => !blocked.includes(p.id));

  return (
    <div className="space-y-5">
      <div className="rounded-md border border-sylion-blue/30 bg-sylion-blue/5 p-3 text-xs">
        <div className="flex items-start gap-2">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sylion-blue" />
          <div className="space-y-1 text-muted-foreground">
            <p className="font-medium text-sylion-blue/90">
              Ten krok jest opcjonalny — domyślne zachowanie wystarczy w 95% przypadków.
            </p>
            <p>
              <span className="text-emerald-300">Zaufanie</span> jest <em>automatyczne</em> dla
              providerów do których podałeś klucz API w kroku 2 oraz dla Ollamy jeśli wykryto
              zainstalowany model. Ten krok służy tylko do dwóch wyjątkowych przypadków:
            </p>
            <ul className="ml-4 list-disc space-y-0.5">
              <li>
                <span className="text-emerald-300">Dodatkowo zaufaj</span> providerowi do którego
                NIE masz klucza (np. używasz OpenRouter jako routing do OpenAI bez własnego klucza).
              </li>
              <li>
                <span className="text-destructive">Wyklucz</span> providera mimo że masz do niego
                klucz (np. masz klucz OpenAI tylko dla zgodności narzędzi, ale nie chcesz żeby
                SYLION go używał).
              </li>
            </ul>
            <p className="mt-1 italic opacity-80">
              Jeśli nie masz takich wymagań — przejdź dalej, defaults wystarczą.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2" data-testid="step8-providers">
        {/* TRUSTED — auto + manual */}
        <div className="space-y-2">
          <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-sylion-green">
            <ShieldCheck className="h-3.5 w-3.5" />
            Zaufani ({effectiveTrusted.length})
          </h3>
          <div className="space-y-1.5">
            {effectiveTrusted.length === 0 ? (
              <p className="rounded-md border border-dashed border-border py-3 text-center text-[11px] text-muted-foreground">
                Brak zaufanych providerów — dodaj klucz API w kroku 2 lub uruchom Ollamę.
              </p>
            ) : (
              effectiveTrusted.map((id) => {
                const def = PROVIDERS.find((p) => p.id === id);
                const isAuto = autoTrusted.includes(id);
                return (
                  <div
                    key={`t-${id}`}
                    className="flex items-center justify-between rounded-md border border-sylion-green/40 bg-sylion-green/5 px-3 py-1.5 text-xs"
                    data-testid={`step8-trust-${id}`}
                  >
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-3 w-3 text-sylion-green" />
                      <span className="text-sylion-green">{def?.label ?? id}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {def?.tier === "core" ? "rdzeń" : def?.tier === "extended" ? "rozszerzony" : "?"}
                      </span>
                      {isAuto ? (
                        <span className="rounded bg-sylion-green/15 px-1.5 py-0.5 text-[10px] text-sylion-green">
                          auto (klucz/Ollama)
                        </span>
                      ) : (
                        <span className="rounded bg-sylion-blue/15 px-1.5 py-0.5 text-[10px] text-sylion-blue">
                          ręcznie
                        </span>
                      )}
                    </div>
                    {!isAuto ? (
                      <button
                        type="button"
                        onClick={() => onRemoveManualTrust(id)}
                        className="text-muted-foreground hover:text-destructive"
                        aria-label={`Usuń ${def?.label ?? id} z zaufanych`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
          {addableTrusted.length > 0 ? (
            <details className="rounded-md border border-dashed border-border/60 px-3 py-2 text-[11px]">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                <Plus className="mr-1 inline h-3 w-3" />
                Dodaj ręcznie zaufanego providera (zaawansowane)
              </summary>
              <div className="mt-2 space-y-1">
                {addableTrusted.map((p) => (
                  <button
                    key={`add-${p.id}`}
                    type="button"
                    onClick={() => onAddManualTrust(p.id)}
                    className="flex w-full items-center justify-between rounded-md border border-border px-2 py-1 text-[11px] transition hover:border-sylion-green/40 hover:bg-sylion-green/5"
                    data-testid={`step8-trust-add-${p.id}`}
                  >
                    <span>{p.label}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {p.tier === "core" ? "rdzeń" : "rozszerzony"}
                    </span>
                  </button>
                ))}
              </div>
            </details>
          ) : null}
        </div>

        {/* BLOCKED — opt-in only */}
        <div className="space-y-2">
          <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-sylion-red">
            <Ban className="h-3.5 w-3.5" />
            Zablokowani ({blocked.length})
          </h3>
          <div className="space-y-1.5">
            {blocked.length === 0 ? (
              <p className="rounded-md border border-dashed border-border py-3 text-center text-[11px] text-muted-foreground">
                Brak — domyślnie żaden provider nie jest blokowany.
              </p>
            ) : (
              blocked.map((id) => {
                const def = PROVIDERS.find((p) => p.id === id);
                return (
                  <div
                    key={`b-${id}`}
                    className="flex items-center justify-between rounded-md border border-sylion-red/40 bg-sylion-red/5 px-3 py-1.5 text-xs"
                    data-testid={`step8-block-${id}`}
                  >
                    <div className="flex items-center gap-2">
                      <Ban className="h-3 w-3 text-sylion-red" />
                      <span className="text-sylion-red">{def?.label ?? id}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {def?.tier === "core" ? "rdzeń" : def?.tier === "extended" ? "rozszerzony" : "?"}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemoveBlock(id)}
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={`Usuń ${def?.label ?? id} z blokady`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
          {addableBlocks.length > 0 ? (
            <details className="rounded-md border border-dashed border-border/60 px-3 py-2 text-[11px]">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                <Plus className="mr-1 inline h-3 w-3" />
                Zablokuj providera (włączane ręcznie)
              </summary>
              <div className="mt-2 space-y-1">
                {addableBlocks.map((p) => {
                  const isAutoTrusted = autoTrusted.includes(p.id);
                  return (
                    <button
                      key={`block-${p.id}`}
                      type="button"
                      onClick={() => onAddBlock(p.id)}
                      className={cn(
                        "flex w-full items-center justify-between rounded-md border border-border px-2 py-1 text-[11px] transition hover:border-sylion-red/40 hover:bg-sylion-red/5",
                        isAutoTrusted && "border-amber-500/30",
                      )}
                      data-testid={`step8-block-add-${p.id}`}
                      title={
                        isAutoTrusted
                          ? "Mimo że masz klucz API tego providera — zablokujesz go w routingu SYLION."
                          : undefined
                      }
                    >
                      <span>{p.label}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {p.tier === "core" ? "rdzeń" : "rozszerzony"}
                        {isAutoTrusted ? " · masz klucz" : ""}
                      </span>
                    </button>
                  );
                })}
              </div>
            </details>
          ) : null}
        </div>
      </div>
    </div>
  );
}
