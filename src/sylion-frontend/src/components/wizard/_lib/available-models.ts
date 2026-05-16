import type { ApiKeyEntry, LocalModelEntry } from "../Step2Providers";

export interface AvailableModel {
  id: string;
  name: string;
  provider: string;
  type: "cloud" | "local";
  cost_tier: "premium" | "standard" | "cheap" | "free";
}

export interface ModelInventory {
  models: AvailableModel[];
  cloud_count: number;
  local_count: number;
  unique_providers: string[];
  can_dual_judge: boolean;
  recommended_max_council: number;
}

const PROVIDER_DEFAULTS: Record<string, { models: string[]; cost_tier: AvailableModel["cost_tier"] }> = {
  anthropic: { models: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"], cost_tier: "premium" },
  openai: { models: ["gpt-5", "gpt-4.1-mini"], cost_tier: "premium" },
  perplexity: { models: ["sonar", "sonar-pro"], cost_tier: "standard" },
  google: { models: ["gemini-2.5-pro", "gemini-2.5-flash"], cost_tier: "standard" },
  zai: { models: ["glm-4-plus"], cost_tier: "standard" },
  openrouter: { models: ["openrouter/auto"], cost_tier: "standard" },
  moonshot: { models: ["moonshot-v1-8k"], cost_tier: "standard" },
  deepseek: { models: ["deepseek-chat"], cost_tier: "cheap" },
  mistral: { models: ["mistral-large-latest"], cost_tier: "standard" },
  xai: { models: ["grok-4"], cost_tier: "premium" },
  groq: { models: ["llama-3.3-70b-versatile"], cost_tier: "cheap" },
  cohere: { models: ["command-r-plus"], cost_tier: "standard" },
  fireworks: { models: ["accounts/fireworks/models/llama-v3p3-70b-instruct"], cost_tier: "cheap" },
  together: { models: ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"], cost_tier: "cheap" },
};

export function deriveInventory(
  apiKeys: ApiKeyEntry[],
  localModels: LocalModelEntry[],
): ModelInventory {
  const models: AvailableModel[] = [];

  for (const k of apiKeys) {
    if (!k.provider || !k.key) continue;
    if (k.validation_status === "error" || k.validation_status === "testing") continue;
    const def = PROVIDER_DEFAULTS[k.provider];
    if (!def) continue;
    for (const m of def.models) {
      models.push({ id: m, name: m, provider: k.provider, type: "cloud", cost_tier: def.cost_tier });
    }
  }

  for (const m of localModels) {
    if (m.status !== "installed") continue;
    models.push({ id: m.name, name: m.name, provider: "ollama", type: "local", cost_tier: "free" });
  }

  const uniqueProviders = Array.from(new Set(models.map((m) => m.provider)));

  return {
    models,
    cloud_count: models.filter((m) => m.type === "cloud").length,
    local_count: models.filter((m) => m.type === "local").length,
    unique_providers: uniqueProviders,
    can_dual_judge: uniqueProviders.length >= 2,
    recommended_max_council: Math.min(11, Math.max(1, models.length)),
  };
}

export function suggestModelForRisk(
  risk: "low" | "medium" | "high" | "critical",
  inventory: ModelInventory,
): string | null {
  if (inventory.models.length === 0) return null;
  const local = inventory.models.filter((m) => m.type === "local");
  const cloud = inventory.models.filter((m) => m.type === "cloud");
  const premium = cloud.filter((m) => m.cost_tier === "premium");

  switch (risk) {
    case "low":
      return (
        local[0]?.name ??
        cloud.find((m) => m.cost_tier === "cheap")?.name ??
        cloud[0]?.name ??
        null
      );
    case "medium":
      return (
        local.find((m) => m.name.includes("72b") || m.name.includes("9b"))?.name ??
        cloud.find((m) => m.cost_tier === "standard")?.name ??
        cloud[0]?.name ??
        null
      );
    case "high":
      return premium[0]?.name ?? cloud[0]?.name ?? local[0]?.name ?? null;
    case "critical": {
      if (inventory.can_dual_judge) {
        const preferred = premium.length > 0 ? premium : cloud;
        for (const first of preferred) {
          const second =
            premium.find((m) => m.provider !== first.provider) ??
            cloud.find((m) => m.provider !== first.provider) ??
            inventory.models.find((m) => m.provider !== first.provider);
          if (second) {
            return `${first.id}+${second.id}`;
          }
        }
      }
      return premium[0]?.name ?? cloud[0]?.name ?? local[0]?.name ?? null;
    }
  }
}
