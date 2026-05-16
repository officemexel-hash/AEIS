"use client";

import { CheckCircle2, DollarSign, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { SmartDefault } from "./SmartDefault";
import { type SubscriptionEntry, SUGGESTED_PLANS } from "./_lib/subscriptions";

export type { SubscriptionEntry };

export interface BudgetCeilings {
  low: number;
  medium: number;
  high: number;
  critical: number;
}

export interface Step3Values {
  cost_ceilings?: BudgetCeilings;
  subscriptions?: SubscriptionEntry[];
}

export const DEFAULT_CEILINGS: BudgetCeilings = {
  low: 0.1,
  medium: 0.4,
  high: 1.6,
  critical: 6.0,
};

const ROWS: Array<{
  key: keyof BudgetCeilings;
  label: string;
  hint: string;
  color: string;
}> = [
  { key: "low", label: "Niskie ryzyko", hint: "Rutynowe decyzję, tanie modele.", color: "text-sylion-green" },
  { key: "medium", label: "Średnie ryzyko", hint: "Domyślna codzienna praca.", color: "text-sylion-amber" },
  { key: "high", label: "Wysokie ryzyko", hint: "Zmiany dotykające produkcji.", color: "text-orange-400" },
  { key: "critical", label: "Krytyczne ryzyko", hint: "Wielu sędziów + przegląd Rady.", color: "text-sylion-red" },
];

// ── Subscription row ──────────────────────────────────────────────────────────

function SubscriptionRow({
  sub,
  onRemove,
  onUpdate,
}: {
  sub: SubscriptionEntry;
  onRemove: () => void;
  onUpdate: (patch: Partial<SubscriptionEntry>) => void;
}) {
  const planDef = SUGGESTED_PLANS.find((p) => p.id === sub.plan_id);
  const displayLabel = planDef?.label ?? sub.plan_id;

  return (
    <div className="flex items-start gap-2 rounded-md border border-border bg-muted/10 px-3 py-2.5">
      <div className="flex-1 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{displayLabel}</span>
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              ${sub.monthly_fee_usd}/mo
            </span>
          </div>
          <button
            type="button"
            onClick={onRemove}
            className="rounded p-0.5 text-muted-foreground transition hover:text-destructive"
            aria-label="Usuń subskrypcję"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {sub.monthly_quota_tokens !== undefined && (
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              Tokeny/mies.:
              <input
                type="number"
                min={0}
                step={100_000}
                value={sub.monthly_quota_tokens}
                onChange={(e) => onUpdate({ monthly_quota_tokens: parseFloat(e.target.value) || 0 })}
                className="w-28 rounded-md border border-border bg-background px-2 py-0.5 text-right text-xs font-mono outline-none focus:border-sylion-blue/60"
              />
            </label>
          )}
          {sub.monthly_quota_usd !== undefined && (
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              Kredyty ($):
              <input
                type="number"
                min={0}
                step={5}
                value={sub.monthly_quota_usd}
                onChange={(e) => onUpdate({ monthly_quota_usd: parseFloat(e.target.value) || 0 })}
                className="w-20 rounded-md border border-border bg-background px-2 py-0.5 text-right text-xs font-mono outline-none focus:border-sylion-blue/60"
              />
            </label>
          )}
          <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            Reset dnia:
            <input
              type="number"
              min={1}
              max={28}
              value={sub.reset_day_of_month}
              onChange={(e) =>
                onUpdate({ reset_day_of_month: Math.min(28, Math.max(1, parseInt(e.target.value) || 1)) })
              }
              className="w-14 rounded-md border border-border bg-background px-2 py-0.5 text-right text-xs font-mono outline-none focus:border-sylion-blue/60"
            />
          </label>
        </div>

        {sub.models_covered.length > 0 && (
          <p className="text-[11px] text-muted-foreground">
            Modele: {sub.models_covered.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Step3Budget ───────────────────────────────────────────────────────────────

interface Step3Context {
  apiKeys?: Array<{ provider: string; key: string }>;
}

interface Props {
  values: Step3Values;
  context?: Step3Context;
  onChange: (patch: Step3Values) => void;
}

// F-028: explain which suggested plans actually map to API access vs. just
// the consumer web-UI subscription. SYLION calls APIs, so a ChatGPT Plus
// (web-only) sub does NOT help SYLION even if the user is paying for it.
// Same for Gemini Advanced. Only Anthropic Pro/Max bundles some API credits;
// OpenRouter prepaid is straight API credit.
const PLAN_API_RELEVANCE: Record<string, "api" | "web_only" | "credit_pool"> = {
  "claude-pro": "api",
  "claude-max": "api",
  "chatgpt-plus": "web_only",
  "openrouter-credits": "credit_pool",
  "gemini-advanced": "web_only",
  custom: "api",
};

function parseDecimalInput(value: string): number {
  const normalized = value.trim().replace(",", ".");
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function Step3Budget({ values, context, onChange }: Props) {
  const ceilings = values.cost_ceilings ?? DEFAULT_CEILINGS;
  const subs = values.subscriptions ?? [];
  const apiKeys = context?.apiKeys ?? [];
  const hasApiKeyFor = (provider: string) =>
    apiKeys.some(
      (k) => (k.provider || "").trim().toLowerCase() === provider && (k.key || "").trim().length >= 10,
    );

  const isDefault =
    ceilings.low === DEFAULT_CEILINGS.low &&
    ceilings.medium === DEFAULT_CEILINGS.medium &&
    ceilings.high === DEFAULT_CEILINGS.high &&
    ceilings.critical === DEFAULT_CEILINGS.critical;

  const updateCeiling = (k: keyof BudgetCeilings, v: number) => {
    onChange({ ...values, cost_ceilings: { ...ceilings, [k]: Number.isFinite(v) ? v : 0 } });
  };

  const addSubFromPlan = (plan: (typeof SUGGESTED_PLANS)[number]) => {
    const nextOrdinal =
      1 +
      subs.reduce((max, sub) => {
        const match = sub.id.match(new RegExp(`^${plan.id}-(\\d+)$`));
        return Math.max(max, match ? Number(match[1]) || 0 : 0);
      }, 0);
    const entry: SubscriptionEntry = {
      id: `${plan.id}-${nextOrdinal}`,
      provider: plan.provider,
      plan_id: plan.id,
      monthly_fee_usd: plan.monthly_fee_usd,
      monthly_quota_tokens: plan.id === "custom" ? 0 : plan.quota_tokens,
      monthly_quota_usd: plan.quota_usd,
      models_covered: [...plan.models],
      reset_day_of_month: 1,
    };
    onChange({ ...values, subscriptions: [...subs, entry] });
  };

  const removeSub = (id: string) => {
    onChange({ ...values, subscriptions: subs.filter((s) => s.id !== id) });
  };

  const updateSub = (id: string, patch: Partial<SubscriptionEntry>) => {
    onChange({
      ...values,
      subscriptions: subs.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  };

  const sonnetSub = subs.find((s) => s.models_covered.includes("claude-sonnet-4-6"));
  const exampleCapUsd = ceilings.medium;

  return (
    <div className="space-y-6">
      {/* Section 1: Subskrypcje */}
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Aktywne subskrypcje (opcjonalne)</h2>
          <p className="text-xs text-muted-foreground">
            SYLION priorytetyzuje wykorzystanie subskrypcji — najpierw używa quota subskrypcji,
            a dopiero gdy się wyczerpie, przechodzi na pay-as-you-go w ramach budżetów poniżej.
          </p>
        </div>

        {subs.length === 0 ? (
          <p className="rounded-md border border-dashed border-border py-4 text-center text-xs text-muted-foreground">
            Brak subskrypcji. Możesz dodać teraz lub później (Ustawienia → Subskrypcje).
          </p>
        ) : (
          <div className="space-y-2">
            {subs.map((s) => (
              <SubscriptionRow
                key={s.id}
                sub={s}
                onRemove={() => removeSub(s.id)}
                onUpdate={(p) => updateSub(s.id, p)}
              />
            ))}
          </div>
        )}

        {/* Suggested plans grid */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Sugerowane plany — kliknij aby dodać
          </p>
          {/* F-028: explain why some "subscriptions" don't help SYLION */}
          <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-[11px] text-muted-foreground">
            <strong className="text-amber-300">Uwaga:</strong> SYLION wywołuje{" "}
            <strong>API</strong>, nie webowy chat. Subskrypcje konsumenckie typu{" "}
            <em>ChatGPT Plus</em> czy <em>Gemini Advanced</em> dają dostęp tylko do strony web —
            <strong className="text-destructive"> nie pomagają SYLION</strong> jeśli już masz klucz
            API danego providera. Tylko Claude Pro/Max (zawierają kredyty API) i kredyty
            przedpłacone OpenRouter mają sens jako uzupełnienie kluczy.
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {SUGGESTED_PLANS.filter((p) => p.id !== "custom").map((plan) => {
              const isAdded = subs.some((s) => s.plan_id === plan.id);
              const relevance = PLAN_API_RELEVANCE[plan.id] ?? "api";
              const userHasKey = hasApiKeyFor(plan.provider);
              const irrelevant = relevance === "web_only" && userHasKey;
              return (
                <button
                  key={plan.id}
                  type="button"
                  disabled={isAdded || irrelevant}
                  onClick={() => addSubFromPlan(plan)}
                  className={cn(
                    "flex items-start justify-between gap-2 rounded-md border p-3 text-left text-xs transition",
                    isAdded
                      ? "cursor-default border-emerald-500/40 bg-emerald-500/5"
                      : irrelevant
                        ? "cursor-not-allowed border-border/30 opacity-50"
                        : "border-border hover:border-sylion-blue/50",
                  )}
                  title={
                    irrelevant
                      ? `Masz już klucz API ${plan.provider}. ${plan.label} to subskrypcja webowa (chat.openai.com / gemini.google.com) — nie odblokowuje API.`
                      : undefined
                  }
                  data-testid={`step3-plan-${plan.id}`}
                  data-relevance={relevance}
                  data-user-has-key={userHasKey || undefined}
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold">{plan.label}</span>
                      <span className="text-muted-foreground">${plan.monthly_fee_usd}/mo</span>
                      {relevance === "web_only" ? (
                        <span className="rounded bg-amber-500/15 px-1 py-0.5 text-[9px] uppercase tracking-wide text-amber-300">
                          tylko web
                        </span>
                      ) : relevance === "credit_pool" ? (
                        <span className="rounded bg-sylion-blue/15 px-1 py-0.5 text-[9px] uppercase tracking-wide text-sylion-blue">
                          kredyty API
                        </span>
                      ) : (
                        <span className="rounded bg-emerald-500/15 px-1 py-0.5 text-[9px] uppercase tracking-wide text-emerald-300">
                          API + web
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground">{plan.description}</p>
                    {irrelevant ? (
                      <p className="text-[10px] text-amber-300/80">
                        Masz klucz API {plan.provider} — ten plan nie doda dostępu API.
                      </p>
                    ) : null}
                  </div>
                  {isAdded ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  ) : (
                    <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => addSubFromPlan(SUGGESTED_PLANS.find((p) => p.id === "custom")!)}
            className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:border-sylion-blue/60 hover:text-foreground"
          >
            <Plus className="h-3.5 w-3.5" /> Inny plan (własny)
          </button>
        </div>
      </section>

      <hr className="border-border" />

      {/* Section 2: Budget caps */}
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Limity per ryzyko (PAYG safety cap)</h2>
          <p className="text-xs text-muted-foreground">
            Maksymalny koszt jednego wywołania pay-as-you-go (gdy subskrypcja wyczerpana lub model nie pokryty).
            Advisor odrzuci plan modelu który przekracza ten pułap.
          </p>
        </div>

        <div className="space-y-3" data-testid="step3-ceilings">
          {ROWS.map((r) => (
            <div
              key={r.key}
              className="flex items-center gap-3 rounded-md border border-border bg-muted/10 px-3 py-2.5"
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-md bg-card ${r.color}`}>
                <DollarSign className="h-4 w-4" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">{r.label}</p>
                <p className="text-[11px] text-muted-foreground">{r.hint}</p>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground">$</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={ceilings[r.key]}
                  onChange={(e) => updateCeiling(r.key, parseDecimalInput(e.target.value))}
                  className="w-24 rounded-md border border-border bg-background px-2 py-1 text-right text-sm font-mono outline-none focus:border-sylion-blue/60"
                  data-testid={`step3-${r.key}`}
                />
              </div>
            </div>
          ))}
        </div>

        {!isDefault ? (
          <SmartDefault
            label="Reset do rekomendowanych limitów (0.10 / 0.40 / 1.60 / 6.00)"
            rationale="Te limity utrzymują przewidywalne miesięczne spalanie budżetu, ale nadal pozwalają użyć Sonnet/GPT-5 na krytycznych ścieżkach."
            onApply={() => onChange({ ...values, cost_ceilings: { ...DEFAULT_CEILINGS } })}
          />
        ) : null}
      </section>

      {/* Waterfall visualization */}
      <div className="rounded-md border border-sylion-blue/30 bg-sylion-blue/5 p-3">
        <p className="text-xs font-semibold text-sylion-blue">Przykład waterfall:</p>
        <ol className="mt-2 space-y-1 text-[11px] text-muted-foreground">
          <li>
            1. Wywołanie Claude Sonnet →{" "}
            {sonnetSub ? (
              <>
                masz <code className="rounded bg-muted px-1 py-0.5">{sonnetSub.plan_id}</code> z{" "}
                {sonnetSub.monthly_quota_tokens?.toLocaleString() ?? "0"} tokenów quota
              </>
            ) : (
              "brak subskrypcji pokrywającej ten model"
            )}
          </li>
          <li>2. Quota dostępna → koszt $0 (subskrypcja)</li>
          <li>3. Quota wyczerpana → fallback do API key Anthropic, koszt ~$0.003 per 1k input tokens</li>
          <li>
            4. Estimated cost &gt; <strong>${exampleCapUsd}</strong> (medium risk cap) → advisor odmawia,
            sugeruje tańszy worker
          </li>
        </ol>
      </div>
    </div>
  );
}
