"use client";

import { useMemo } from "react";
import { AlertTriangle, Cloud, Cpu, Download, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { deriveInventory, suggestModelForRisk } from "./_lib/available-models";
import type { ApiKeyEntry, LocalModelEntry } from "./Step2Providers";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface JudgeRouting {
  low: string;
  medium: string;
  high: string;
  critical: string;
}

export interface Step6Values {
  council_size?: number;
  llm_judge_routing?: JudgeRouting;
}

export const DEFAULT_ROUTING: JudgeRouting = {
  low: "qwen2.5:7b-instruct",
  medium: "qwen2.5:72b-instruct",
  high: "claude-sonnet-4-6",
  critical: "claude-sonnet-4-6+gpt-5",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "niskie",
  medium: "średnie",
  high: "wysokie",
  critical: "krytyczne",
};

interface Props {
  values: Step6Values;
  onChange: (patch: Step6Values) => void;
  apiKeys: ApiKeyEntry[];
  localModels: LocalModelEntry[];
  onJumpToStep2?: () => void;
}

export function Step6Council({ values, onChange, apiKeys, localModels, onJumpToStep2 }: Props) {
  const inventory = useMemo(() => deriveInventory(apiKeys, localModels), [apiKeys, localModels]);

  const maxCouncil = inventory.recommended_max_council;
  const councilSize = values.council_size ?? Math.min(5, maxCouncil);
  const cappedSize = Math.min(councilSize, maxCouncil);

  const routing: JudgeRouting = values.llm_judge_routing ?? {
    low: suggestModelForRisk("low", inventory) ?? "",
    medium: suggestModelForRisk("medium", inventory) ?? "",
    high: suggestModelForRisk("high", inventory) ?? "",
    critical: suggestModelForRisk("critical", inventory) ?? "",
  };

  const showWarning = inventory.models.length < 2;
  const cantDualJudge = !inventory.can_dual_judge;
  const setCouncilSize = (next: number) => {
    const safe = Math.max(1, Math.min(maxCouncil, Number.isFinite(next) ? next : cappedSize));
    onChange({ council_size: safe });
  };

  return (
    <div className="space-y-5">
      {showWarning ? (
        <div className="flex gap-3 rounded-md border border-amber-500/50 bg-amber-500/10 p-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
          <div className="flex-1 space-y-1.5">
            <p className="text-sm font-semibold text-amber-200">
              Wymagane minimum 2 modele dla działania Rady
            </p>
            <p className="text-xs text-amber-200/80">
              Masz teraz {inventory.models.length}{" "}
              {inventory.models.length === 1 ? "model" : "modele"} ({inventory.cloud_count} chmurowych,{" "}
              {inventory.local_count} lokalnych). Pojedynczy model to jeden sędzia — Rada nie ma
              różnorodności perspektyw i degeneruje.
            </p>
            <p className="text-xs text-amber-200/80">
              Rekomendacja: pobierz minimum 2 modele lokalne (np.{" "}
              <code className="rounded bg-amber-500/20 px-1">qwen2.5:7b-instruct</code> +{" "}
              <code className="rounded bg-amber-500/20 px-1">mistral:7b</code>) aby Rada działała
              offline bez kosztów.
            </p>
            {onJumpToStep2 ? (
              <button
                type="button"
                onClick={onJumpToStep2}
                className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-amber-200 underline-offset-2 hover:underline"
              >
                <Download className="h-3 w-3" />
                Wróć do kroku 2 i dodaj modele
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 rounded-md border border-border bg-card/40 p-3 text-xs">
        <span className="flex items-center gap-1">
          <Cloud className="h-3.5 w-3.5 text-sylion-blue" />
          {inventory.cloud_count} chmurowych
          {inventory.unique_providers.filter((p) => p !== "ollama").length > 0
            ? " · " + inventory.unique_providers.filter((p) => p !== "ollama").join(", ")
            : ""}
        </span>
        <span className="text-muted-foreground">·</span>
        <span className="flex items-center gap-1">
          <Cpu className="h-3.5 w-3.5 text-emerald-400" />
          {inventory.local_count} lokalnych
        </span>
        <span className="text-muted-foreground">·</span>
        <span>{inventory.models.length} modeli łącznie</span>
        <span className="text-muted-foreground">·</span>
        <span
          className={cn(
            "font-semibold",
            inventory.can_dual_judge ? "text-emerald-400" : "text-amber-400",
          )}
        >
          {inventory.can_dual_judge ? "Podwójny sędzia możliwy" : "Podwójny sędzia wymaga 2+ providerów"}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Rozmiar Rady (1 — {maxCouncil} dostępnych)
          </label>
          <span className="flex items-center gap-1 text-sm font-mono">
            <Users className="h-3.5 w-3.5 text-sylion-blue" />
            <span className="font-semibold">{cappedSize}</span>
          </span>
        </div>
        <input
          type="range"
          min={1}
          max={maxCouncil}
          step={1}
          value={cappedSize}
          onChange={(e) => setCouncilSize(parseInt(e.target.value, 10))}
          className="w-full accent-sylion-blue"
          data-testid="step6-council-size"
          aria-label="Rozmiar Rady"
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCouncilSize(cappedSize - 1)}
            disabled={cappedSize <= 1}
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted/30 disabled:cursor-not-allowed disabled:opacity-40"
            data-testid="step6-council-size-dec"
          >
            -
          </button>
          <input
            type="number"
            min={1}
            max={maxCouncil}
            value={cappedSize}
            onChange={(e) => setCouncilSize(parseInt(e.target.value, 10))}
            className="w-20 rounded-md border border-border bg-background px-2 py-1 text-center text-xs font-mono outline-none focus:border-sylion-blue/60"
            data-testid="step6-council-size-number"
            aria-label="Rozmiar Rady - wartość liczbowa"
          />
          <button
            type="button"
            onClick={() => setCouncilSize(cappedSize + 1)}
            disabled={cappedSize >= maxCouncil}
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted/30 disabled:cursor-not-allowed disabled:opacity-40"
            data-testid="step6-council-size-inc"
          >
            +
          </button>
          <span className="text-[11px] text-muted-foreground">
            precyzyjne sterowanie, gdy range slider jest niewygodny w audycie lub na touchpadzie
          </span>
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>1 — solo</span>
          <span>{Math.max(1, Math.ceil(maxCouncil / 2))} — rekomendowany</span>
          <span>{maxCouncil} — pełna Rada</span>
        </div>
        {councilSize > maxCouncil ? (
          <p className="text-xs text-amber-400">
            Wybrano {councilSize}, ale dostępnych jest tylko {maxCouncil} modeli — używamy {maxCouncil}.
          </p>
        ) : null}
      </div>

      <div className="space-y-3 border-t border-border pt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Model sędziowski per ryzyko
        </p>
        {(["low", "medium", "high", "critical"] as const).map((risk) => {
          const isCritical = risk === "critical";
          return (
            <div key={risk} className="grid grid-cols-[80px_1fr] items-center gap-3">
              <span
                className={cn(
                  "text-xs font-bold uppercase",
                  risk === "low" && "text-emerald-400",
                  risk === "medium" && "text-amber-400",
                  risk === "high" && "text-orange-400",
                  risk === "critical" && "text-destructive",
                )}
              >
                {RISK_LABELS[risk]}
              </span>
              <select
                value={routing[risk]}
                onChange={(e) =>
                  onChange({ llm_judge_routing: { ...routing, [risk]: e.target.value } })
                }
                className="rounded-md border border-border bg-background px-3 py-2 text-xs font-mono outline-none focus:border-sylion-blue/60"
                data-testid={`step6-routing-${risk}`}
              >
                <option value="">— wybierz model —</option>
                {inventory.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.type === "local" ? "lokalny" : m.provider})
                  </option>
                ))}
                {isCritical && inventory.can_dual_judge ? (
                  <optgroup label="Podwójny sędzia (2 modele równocześnie)">
                    {inventory.models.flatMap((a, ai) =>
                      inventory.models
                        .slice(ai + 1)
                        .filter((b) => b.provider !== a.provider)
                        .map((b) => (
                          <option key={`${a.id}+${b.id}`} value={`${a.id}+${b.id}`}>
                            {a.name} + {b.name} (podwójnie)
                          </option>
                        )),
                    )}
                  </optgroup>
                ) : null}
              </select>
            </div>
          );
        })}
        {cantDualJudge ? (
          <p className="text-xs text-amber-400">
            Krytyczne ryzyko = podwójny sędzia wymaga minimum 2 różnych providerów. Aktualnie używamy
            pojedynczego sędziego.
          </p>
        ) : null}
      </div>
    </div>
  );
}
