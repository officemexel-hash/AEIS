export interface SubscriptionEntry {
  id: string;
  provider: string;
  plan_id: string;
  monthly_fee_usd: number;
  monthly_quota_tokens?: number;
  monthly_quota_usd?: number;
  models_covered: string[];
  reset_day_of_month: number;
}

export const SUGGESTED_PLANS: Array<{
  id: string;
  provider: string;
  label: string;
  monthly_fee_usd: number;
  quota_tokens?: number;
  quota_usd?: number;
  models: string[];
  description: string;
}> = [
  {
    id: "claude-pro",
    provider: "anthropic",
    label: "Claude Pro",
    monthly_fee_usd: 20,
    quota_tokens: 5_000_000,
    models: ["claude-sonnet-4-6", "claude-haiku-4-5"],
    description: "5 mln tokenów/mies. dla Sonnet + Haiku",
  },
  {
    id: "claude-max",
    provider: "anthropic",
    label: "Claude Max",
    monthly_fee_usd: 100,
    quota_tokens: 30_000_000,
    models: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
    description: "30 mln tokenów/mies. + dostęp do Opus",
  },
  {
    id: "chatgpt-plus",
    provider: "openai",
    label: "ChatGPT Plus",
    monthly_fee_usd: 20,
    quota_tokens: 5_000_000,
    models: ["gpt-5", "gpt-4.1-mini"],
    description: "5 mln tokenów/mies. + szybciej + GPT-5",
  },
  {
    id: "openrouter-credits",
    provider: "openrouter",
    label: "OpenRouter - kredyty przedpłacone",
    monthly_fee_usd: 25,
    quota_usd: 25,
    models: ["openrouter/auto"],
    description: "$25 przedpłaty → routing przez 100+ modeli",
  },
  {
    id: "gemini-advanced",
    provider: "google",
    label: "Gemini Advanced",
    monthly_fee_usd: 20,
    quota_tokens: 10_000_000,
    models: ["gemini-2.5-pro", "gemini-2.5-flash"],
    description: "Dostęp do Gemini 2.5 Pro",
  },
  {
    id: "custom",
    provider: "custom",
    label: "Inny plan (własny)",
    monthly_fee_usd: 0,
    models: [],
    description: "Wpisz ręcznie własny plan i quota",
  },
];
