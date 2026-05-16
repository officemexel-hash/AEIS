"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { HelpTip } from "@/components/common/HelpTip";
import {
  ArrowLeft,
  RefreshCw,
  Loader2,
  Scale,
  Wallet,
  Sparkles,
  Bot,
  Settings2,
  Sliders,
  Activity,
  ShieldCheck,
  CheckCircle2,
  ShieldAlert,
} from "lucide-react";

type CouncilMember = {
  member_id?: string;
  council_member_id?: string;
  member_role?: string;
  role?: string;
  rank?: string;
  model_id?: string;
  provider?: string;
  preferred_models?: string[];
  reasoning_effort?: string;
  config?: {
    rank?: string;
    preferred_models?: string[];
    responsibility?: string;
    reasoning_effort?: string;
    thinking_depth?: string;
    required_signature?: boolean;
  };
  weight?: number;
  voting_weight?: number;
  active?: boolean;
};

type CouncilState = {
  enabled?: boolean;
  plan?: {
    enabled?: boolean;
    members?: CouncilMember[];
    active_size?: number;
    suggested_size?: number;
  };
  members?: CouncilMember[];
  rank_weights?: Record<string, number>;
  critic_gate_enabled?: boolean;
  quorum_min?: number;
};

type BudgetState = {
  cap_usd?: number;
  spent_usd?: number;
  hard_stop?: boolean;
  soft_warn_usd?: number;
  per_provider_cap?: Record<string, number>;
};

type AutonomyState = {
  level?: string;
  enabled?: boolean;
  approval_required?: boolean;
};

type CouncilSuggestion = {
  plan?: {
    members?: CouncilMember[];
    quorum_policy?: Record<string, unknown>;
    suggestion_stage?: string;
    requires_model_probe?: boolean;
    confidence_basis?: string[];
    model_probe?: {
      completed?: boolean;
      note?: string;
    };
  };
  recommended_models?: Array<{
    role?: string;
    rank?: string;
    provider?: string;
    model_id?: string;
    rationale?: string;
  }>;
  rationale?: string;
  suggestion_stage?: string;
  requires_model_probe?: boolean;
  confidence_basis?: string[];
  model_probe?: {
    completed?: boolean;
    note?: string;
  };
};

type SuggestedCouncilItem = {
  role?: string;
  rank?: string;
  provider?: string;
  model_id?: string;
  preferred_models?: string[];
};

type ModelReadinessState = {
  status: "unchecked" | "checking" | "ready" | "limited" | "error";
  activeProviders: string[];
  registeredModels: string[];
  projectCandidateModels: string[];
  checkedAt?: string;
  message?: string;
};

type ProjectState = {
  title?: string;
  project_kind?: string;
  canon_frozen_at?: number | null;
  masterplan_frozen_at?: number | null;
  build_authorized_at?: number | null;
  masterplan?: string;
  modules?: Array<{
    module_id?: string;
    name?: string;
    status?: string;
    spec?: Record<string, unknown>;
  }>;
  worker_plan?: {
    modules?: string[];
    roles?: string[];
  };
  execution_plan?: {
    model_assignments?: ExecutionModelAssignment[];
    model_assignment_source?: string;
    model_assignment_updated_at?: number;
  };
  approvals?: {
    build_pending_ticket_id?: string;
  };
  events?: Array<{
    event_type?: string;
    emitted_at?: number;
    payload?: {
      status?: string;
      decision_class?: string;
      gate_type?: string;
      risk_flags?: string[] | string;
      ticket_id?: string;
      ratio?: number;
      council_session_id?: string;
      consensus?: CouncilDeliberationResult["consensus"] & {
        by_model?: Array<{
          model_id?: string;
          verdict?: string;
          weight?: number;
        }>;
      };
    };
  }>;
};

type ModelCatalogItem = {
  model_id: string;
  display_name: string;
  provider: string;
  source: "registry" | "ollama" | "openrouter" | "static";
  locality?: "local" | "cloud";
  context_length?: number;
  parameter_size?: string;
  family?: string;
  pricing?: Record<string, unknown>;
};

type ExecutionModelAssignment = {
  module_id: string;
  module_name: string;
  worker_model_id: string;
  worker_provider: string;
  reviewer_model_id: string;
  reviewer_provider: string;
  supervisor_model_id: string;
  supervisor_provider: string;
  reasoning_effort: string;
  suggestion_basis: string;
};

type CouncilDeliberationResult = {
  status?: string;
  decision_class?: string;
  gate_type?: string;
  risk_flags?: string[];
  human_gate_ticket_id?: string;
  consensus_ratio?: number;
  minimum_ratio?: number;
  critic_signature?: Record<string, unknown> | null;
  consensus?: {
    verdict?: string;
    critic_signed?: boolean;
    total_weight?: number;
    weights?: Record<string, number>;
  };
  session?: {
    session_id?: string;
    phase?: string;
    consolidated_suggestion?: string;
  };
  analyses?: Array<{
    model_id?: string;
    role?: string;
    participant?: {
      role?: string;
    };
    verdict?: string;
    confidence?: number;
    rationale?: string;
    source?: string;
    sentinel_blocks?: string[];
  }>;
};

type V10CouncilReviewBasis = {
  risk_level: string;
  risk_basis: string;
  budget_limit_usd: number;
  cost_delta_usd: number;
  monthly_cost_delta_usd: number;
  vps_workers: number;
  vps_basis: string;
  external_action: boolean;
  external_action_basis: string;
  production_deploy: boolean;
  production_deploy_basis: string;
  final_action: boolean;
  legal_or_financial_action: boolean;
  scope: string[];
};

type V10CouncilReviewDraft = {
  risk_level: "auto" | "low" | "medium" | "high" | "critical";
  cost_delta_usd: string;
  monthly_cost_delta_usd: string;
  vps_workers: string;
  external_action: boolean;
  production_deploy: boolean;
  final_action: boolean;
  legal_or_financial_action: boolean;
};

const DEFAULT_V10_REVIEW_DRAFT: V10CouncilReviewDraft = {
  risk_level: "auto",
  cost_delta_usd: "0",
  monthly_cost_delta_usd: "0",
  vps_workers: "0",
  external_action: false,
  production_deploy: false,
  final_action: false,
  legal_or_financial_action: false,
};

const MODEL_LABELS: Record<string, string> = {
  "gpt-5": "OpenAI GPT-5",
  "openai:gpt-5": "OpenAI GPT-5",
  "gpt-5-mini": "OpenAI GPT-5 mini",
  "openai:gpt-5-mini": "OpenAI GPT-5 mini",
  "gpt-4.1": "OpenAI GPT-4.1",
  "openai:gpt-4.1": "OpenAI GPT-4.1",
  "gpt-4o": "OpenAI GPT-4o",
  "openai:gpt-4o": "OpenAI GPT-4o",
  "gpt-4o-mini": "OpenAI GPT-4o mini",
  "openai:gpt-4o-mini": "OpenAI GPT-4o mini",
  "claude-opus-4-7": "Claude Opus 4.7",
  "anthropic:claude-opus-4-7": "Claude Opus 4.7",
  "claude-sonnet-4-7": "Claude Sonnet 4.7",
  "anthropic:claude-sonnet-4-7": "Claude Sonnet 4.7",
  "claude-sonnet-4-6": "Claude Sonnet 4.6",
  "anthropic:claude-sonnet-4-6": "Claude Sonnet 4.6",
  "claude-haiku-4-5": "Claude Haiku 4.5",
  "anthropic:claude-haiku-4-5": "Claude Haiku 4.5",
  "gemini-2.0-flash": "Gemini 2.0 Flash",
  "google:gemini-2.0-flash": "Gemini 2.0 Flash",
  "gemini-2.5-flash": "Gemini 2.5 Flash",
  "google:gemini-2.5-flash": "Gemini 2.5 Flash",
  "glm-4-plus": "Z.ai GLM 4 Plus",
  "zai:glm-4-plus": "Z.ai GLM 4 Plus",
  "kimi-k2.6": "Kimi K2.6",
  "moonshot:kimi-k2.6": "Kimi K2.6",
  sonar: "Perplexity Sonar",
  "perplexity:sonar": "Perplexity Sonar",
  "openrouter/auto": "OpenRouter Auto",
  "openrouter:openrouter/auto": "OpenRouter Auto",
  "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M": "Bielik 11B v2.3 Q4_K_M",
  "PRIHLOP/PLLuM:12B-chat-Q8_0": "PLLuM 12B chat Q8_0",
  "qwen2.5:0.5b": "Qwen 2.5 0.5B lokalny",
  "qwen2.5:7b-instruct": "Qwen 2.5 7B lokalny",
  "qwen2.5:72b-instruct": "Qwen 2.5 72B lokalny",
  "qwen3.5:latest": "Qwen 3.5 lokalny",
  "mistral:7b": "Mistral 7B lokalny",
  "llama3.2:3b": "Llama 3.2 3B lokalny",
  "phi3:mini": "Phi-3 Mini lokalny",
  "gemma2:9b": "Gemma 2 9B lokalny",
  "gpt-oss:20b": "GPT-OSS 20B lokalny",
};

const MODEL_OPTIONS = [
  { value: "gpt-5", label: "OpenAI GPT-5" },
  { value: "gpt-5-mini", label: "OpenAI GPT-5 mini" },
  { value: "gpt-4.1", label: "OpenAI GPT-4.1" },
  { value: "gpt-4o", label: "OpenAI GPT-4o" },
  { value: "gpt-4o-mini", label: "OpenAI GPT-4o mini" },
  { value: "claude-opus-4-7", label: "Claude Opus 4.7" },
  { value: "claude-sonnet-4-7", label: "Claude Sonnet 4.7" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5", label: "Claude Haiku 4.5" },
  { value: "gemini-2.0-flash", label: "Google Gemini 2.0 Flash" },
  { value: "sonar", label: "Perplexity Sonar" },
  { value: "qwen2.5:7b-instruct", label: "Qwen 2.5 7B local" },
];

const REASONING_OPTIONS = [
  { value: "low", label: "Niska - szybka odpowiedź" },
  { value: "medium", label: "Średnia - standard Rady" },
  { value: "high", label: "Wysoka - decyzję D3+" },
  { value: "xhigh", label: "Bardzo wysoka - krytyk / architekt" },
];

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
  perplexity: "Perplexity",
  zai: "Z.ai",
  openrouter: "OpenRouter",
  ollama: "Ollama lokalnie",
  moonshot: "Kimi",
};

const EXECUTION_ROLE_LABELS: Record<"worker" | "reviewer" | "supervisor", string> = {
  worker: "Robotnik",
  reviewer: "Recenzent",
  supervisor: "Nadzorca",
};

const MODULE_NAME_LABELS: Record<string, string> = {
  application_core: "Rdzeń aplikacji",
  app_core: "Rdzeń aplikacji",
  core: "Rdzeń aplikacji",
  interface_core: "Interfejs użytkownika",
  interface_layer: "Interfejs użytkownika",
  ui_layer: "Interfejs użytkownika",
  integration_validation: "Integracje i walidacja",
  validation_layer: "Walidacja jakości",
  funding_scan: "Analiza finansowania",
  release_governance: "Nadzór wydania",
  audit_evidence_pack: "Pakiet dowodowy audytu",
};

const STATIC_MODEL_CATALOG: ModelCatalogItem[] = MODEL_OPTIONS.map((option) => ({
  model_id: option.value,
  display_name: option.label,
  provider: inferProvider(option.value) || "manual",
  source: "static",
  locality: option.value.includes(":") ? "local" : "cloud",
}));

const V10_RISK_LEVEL_OPTIONS = [
  { value: "auto", label: "Automatycznie z ustawień" },
  { value: "low", label: "Niski" },
  { value: "medium", label: "Średni" },
  { value: "high", label: "Wysoki" },
  { value: "critical", label: "Krytyczny" },
] as const;

const ROLE_LABELS: Record<string, string> = {
  planner: "planista",
  architect: "architekt",
  critic: "krytyk",
  verifier: "weryfikator",
  governance: "nadzór",
};

const RANK_LABELS: Record<string, string> = {
  primary: "główny",
  validation_only: "tylko walidacja",
  senior: "senior",
};

const RESPONSIBILITY_LABELS: Record<string, string> = {
  "source of truth and masterplan coherence": "kanon, źródło prawdy i spójność masterplanu",
  "architecture, module boundaries and runtime topology": "architektura, granice modułów i topologia runtime",
  "risk, scope drift and governance challenge": "ryzyko, dryf zakresu i kontrargument zarządczy",
  "tests, evidence and operator-readiness": "testy, dowody i gotowość operatora",
  "Human Gate, cost, production and external-action policy": "Human Gate, koszty, produkcja i polityka działań zewnętrznych",
};

const STATUS_LABELS: Record<string, string> = {
  requires_human_gate: "Wymaga akceptacji HumanGate",
  auto_approved: "Zaakceptowano automatycznie",
  blocked: "Zablokowane",
  rejected: "Odrzucone",
  approved: "Zaakceptowane",
  pending: "Oczekuje",
  unknown: "Nieznany",
};

const VERDICT_LABELS: Record<string, string> = {
  approve: "akceptacja",
  approved: "akceptacja",
  conditional: "warunkowo",
  reject: "odrzucenie",
  rejected: "odrzucenie",
  tie: "remis",
  no_data: "brak danych",
  warn: "ostrzeżenie",
};

const RISK_FLAG_LABELS: Record<string, string> = {
  affects_architecture: "zakres: architektura",
  affects_masterplan: "zakres: Masterplan",
  affects_source_of_truth: "zakres: źródło prawdy",
  external_action: "akcja zewnętrzna",
  production_deploy: "wdrożenie produkcyjne",
  final_action: "akcja finalna",
  legal_or_financial_action: "czynność prawna lub finansowa",
  cost_delta_gt_25_usd: "limit kosztu powyżej 25 USD",
  monthly_cost_delta_gt_100_usd: "miesięczny koszt powyżej 100 USD",
  vps_workers_gt_3: "więcej niż 3 workery VPS",
  risk_level_high: "wysoki poziom ryzyka",
  risk_level_critical: "krytyczny poziom ryzyka",
};

const SENTINEL_LABELS: Record<string, string> = {
  cost: "koszt",
  security: "bezpieczeństwo",
  legal: "prawny",
  none: "brak blokady",
};

const SOURCE_LABELS: Record<string, string> = {
  real_llm: "realna odpowiedź modelu",
  llm_unavailable: "model niedostępny",
  llm_error: "błąd modelu",
  llm_timeout: "timeout modelu",
  persisted_project_event: "zapisane zdarze?ie projektu",
};

const LEGACY_ARTIFICIAL_V10_FLAGS = new Set([
  "cost_delta_gt_25_usd",
  "monthly_cost_delta_gt_100_usd",
  "external_action",
  "risk_level_high",
  "risk_level_critical",
  "vps_workers_gt_3",
]);

function modelLabel(member: CouncilMember): string {
  if (member.model_id) return modelDisplayName(member.model_id);
  const firstPreferred = member.preferred_models?.[0] || member.config?.preferred_models?.[0];
  return firstPreferred ? modelDisplayName(firstPreferred) : "model nieprzypisany";
}

function canonicalModelId(modelId: string): string {
  const raw = String(modelId || "").trim();
  const lower = raw.toLowerCase();
  const providerPrefixes = [
    "openai:",
    "anthropic:",
    "google:",
    "perplexity:",
    "zai:",
    "moonshot:",
    "openrouter:",
    "ollama:",
  ];
  const prefix = providerPrefixes.find((candidate) => lower.startsWith(candidate));
  return prefix ? raw.slice(prefix.length) : raw;
}

function modelDisplayName(modelId: string, displayName?: string): string {
  const raw = String(modelId || "").trim();
  const canonical = canonicalModelId(raw);
  const candidateName = String(displayName || "").trim();
  const canonicalDisplayName = candidateName && !candidateName.includes(": ") ? canonicalModelId(candidateName).trim() : candidateName;
  return (
    MODEL_OPTIONS.find((option) => option.value === raw || option.value === canonical)?.label ||
    MODEL_LABELS[raw] ||
    MODEL_LABELS[canonical] ||
    (candidateName && (MODEL_LABELS[candidateName] || MODEL_LABELS[canonicalDisplayName] || canonicalDisplayName)) ||
    canonical ||
    raw
  );
}

function reasoningLabel(value: string): string {
  return REASONING_OPTIONS.find((option) => option.value === value)?.label || humanizeToken(value);
}

function reasoningShortLabel(value: string): string {
  const labels: Record<string, string> = {
    low: "Niska",
    medium: "Średnia",
    high: "Wysoka",
    xhigh: "Bardzo wysoka",
  };
  return labels[value] || humanizeToken(value);
}

function memberRole(member: CouncilMember): string {
  return member.role || member.member_role || "rola nieznana";
}

function memberRoleLabel(member: CouncilMember): string {
  const role = memberRole(member);
  return ROLE_LABELS[role] || role;
}

function roleLabel(role: string): string {
  return ROLE_LABELS[role] || {
    cost_sentinel: "sentinel kosztów",
    security_sentinel: "sentinel bezpieczeństwa",
    domain_specialist: "ekspert domenowy",
    persisted_vote: "głos zapisany w audycie",
  }[role] || humanizeToken(role);
}

function memberRank(member: CouncilMember): string {
  return member.rank || member.config?.rank || "?";
}

function memberRankLabel(member: CouncilMember): string {
  const rank = memberRank(member);
  return RANK_LABELS[rank] || rank;
}

function memberResponsibility(member: CouncilMember): string {
  const responsibility = member.config?.responsibility || "";
  return RESPONSIBILITY_LABELS[responsibility] || responsibility || "Rola Rady dla decyzji projektowych.";
}

function memberWeight(member: CouncilMember): number {
  return Number(member.weight ?? member.voting_weight ?? 1);
}

function memberModelId(member: CouncilMember): string {
  return member.model_id || member.preferred_models?.[0] || member.config?.preferred_models?.[0] || "";
}

function memberReasoningEffort(member: CouncilMember): string {
  return member.reasoning_effort || member.config?.reasoning_effort || member.config?.thinking_depth || "medium";
}

function inferProvider(modelId: string): string {
  const original = String(modelId || "").trim().toLowerCase();
  const value = canonicalModelId(modelId).toLowerCase();
  if (original.startsWith("openrouter:") || value.startsWith("openrouter/")) return "openrouter";
  if (original.startsWith("ollama:")) return "ollama";
  if (
    value.includes("bielik") ||
    value.includes("pllum") ||
    value.startsWith("qwen") ||
    value.startsWith("mistral:") ||
    value.startsWith("llama") ||
    value.startsWith("phi") ||
    value.startsWith("gemma") ||
    value.startsWith("gpt-oss:")
  ) {
    return "ollama";
  }
  if (value.includes("claude")) return "anthropic";
  if (value.includes("gpt") || value.includes("o1") || value.includes("o3")) return "openai";
  if (value.includes("gemini")) return "google";
  if (value.includes("sonar")) return "perplexity";
  if (value.includes("glm")) return "zai";
  if (value.includes("kimi")) return "moonshot";
  if (value.includes(":")) return "ollama";
  if (value.includes("/")) return "openrouter";
  return "";
}

function uniqueStrings(values: Array<string | undefined | null>): string[] {
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean)));
}

function providerFromKeyEntry(entry: unknown): string {
  if (!entry || typeof entry !== "object") return "";
  const row = entry as { provider?: unknown; provider_id?: unknown; name?: unknown; is_active?: unknown; active?: unknown };
  return String(row.provider || row.provider_id || row.name || "").trim();
}

function isActiveKeyEntry(entry: unknown): boolean {
  if (!entry || typeof entry !== "object") return false;
  const row = entry as { is_active?: unknown; active?: unknown; status?: unknown };
  if (row.is_active === false || row.active === false) return false;
  if (typeof row.status === "string" && row.status.toLowerCase() === "inactive") return false;
  return true;
}

function modelIdFromRegistryEntry(entry: unknown): string {
  if (!entry || typeof entry !== "object") return "";
  const row = entry as { model_id?: unknown; id?: unknown; name?: unknown; display_name?: unknown };
  return String(row.model_id || row.id || row.name || row.display_name || "").trim();
}

function providerLabel(provider: string | undefined): string {
  if (!provider) return "provider";
  return PROVIDER_LABELS[provider] || humanizeToken(provider);
}

function registryEntryToCatalog(entry: unknown): ModelCatalogItem | null {
  if (!entry || typeof entry !== "object") return null;
  const row = entry as {
    model_id?: unknown;
    id?: unknown;
    name?: unknown;
    display_name?: unknown;
    provider?: unknown;
    config_json?: unknown;
  };
  const modelId = modelIdFromRegistryEntry(row);
  if (!modelId) return null;
  const provider = String(row.provider || inferProvider(modelId) || "registry").trim();
  return {
    model_id: modelId,
    display_name: modelDisplayName(modelId, String(row.display_name || row.name || "").trim()),
    provider,
    source: "registry",
    locality: provider === "ollama" ? "local" : "cloud",
  };
}

function ollamaEntryToCatalog(entry: unknown): ModelCatalogItem | null {
  if (!entry || typeof entry !== "object") return null;
  const row = entry as {
    name?: unknown;
    model?: unknown;
    family?: unknown;
    parameter_size?: unknown;
    details?: { family?: unknown; parameter_size?: unknown };
  };
  const modelId = String(row.name || row.model || "").trim();
  if (!modelId) return null;
  return {
    model_id: modelId,
    display_name: modelDisplayName(modelId),
    provider: "ollama",
    source: "ollama",
    locality: "local",
    family: String(row.family || row.details?.family || "").trim(),
    parameter_size: String(row.parameter_size || row.details?.parameter_size || "").trim(),
  };
}

function openRouterEntryToCatalog(entry: unknown): ModelCatalogItem | null {
  if (!entry || typeof entry !== "object") return null;
  const row = entry as {
    model_id?: unknown;
    id?: unknown;
    name?: unknown;
    display_name?: unknown;
    context_length?: unknown;
    pricing?: Record<string, unknown>;
  };
  const modelId = String(row.model_id || row.id || "").trim();
  if (!modelId) return null;
  return {
    model_id: modelId,
    display_name: modelDisplayName(modelId, String(row.display_name || row.name || "").trim()),
    provider: "openrouter",
    source: "openrouter",
    locality: "cloud",
    context_length: typeof row.context_length === "number" ? row.context_length : undefined,
    pricing: row.pricing || {},
  };
}

function dedupeModelCatalog(items: Array<ModelCatalogItem | null | undefined>): ModelCatalogItem[] {
  const priority: Record<ModelCatalogItem["source"], number> = {
    registry: 0,
    ollama: 1,
    openrouter: 2,
    static: 3,
  };
  const byId = new Map<string, ModelCatalogItem>();
  for (const item of items) {
    if (!item?.model_id) continue;
    const current = byId.get(item.model_id);
    if (!current || priority[item.source] < priority[current.source]) {
      byId.set(item.model_id, item);
    }
  }
  return Array.from(byId.values()).sort((a, b) => {
    if (a.source !== b.source) return priority[a.source] - priority[b.source];
    return a.display_name.localeCompare(b.display_name);
  });
}

function modelCatalogLabel(item: ModelCatalogItem): string {
  const source =
    item.source === "ollama"
      ? "lokalny"
      : item.source === "openrouter"
        ? "OpenRouter"
        : providerLabel(item.provider);
  const context = item.context_length ? `, kontekst ${Math.round(item.context_length / 1000)}k` : "";
  return `${item.display_name} - ${source}${context}`;
}

function findCatalogEntry(catalog: ModelCatalogItem[], modelId: string): ModelCatalogItem | undefined {
  return catalog.find((item) => item.model_id === modelId);
}

function providerForModel(catalog: ModelCatalogItem[], modelId: string): string {
  return findCatalogEntry(catalog, modelId)?.provider || inferProvider(modelId) || "manual";
}

function moduleDisplayName(value: string | undefined, fallback = "Moduł projektu"): string {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  const normalized = raw.toLowerCase().replace(/[\s-]+/g, "_");
  if (MODULE_NAME_LABELS[normalized]) return MODULE_NAME_LABELS[normalized];
  if (/^[a-z0-9_]+$/.test(raw)) {
    return raw
      .split("_")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }
  return raw;
}

function projectModuleRows(project: ProjectState | null): Array<{ module_id: string; name: string }> {
  const modules = (project?.modules || [])
    .map((module, index) => ({
      module_id: String(module.module_id || `module_${index + 1}`),
      name: moduleDisplayName(String(module.name || module.module_id || ""), `Moduł ${index + 1}`),
    }))
    .filter((module) => module.name.trim());
  if (modules.length) return modules;
  const planModules = (project?.worker_plan?.modules || [])
    .map((name, index) => ({
      module_id: `worker_plan_${index + 1}`,
      name: moduleDisplayName(String(name || ""), `Moduł ${index + 1}`),
    }))
    .filter((module) => module.name.trim());
  if (planModules.length) return planModules;
  return [{ module_id: "project_overview", name: project?.title || "Projekt" }];
}

function modelPatternsFor(role: "worker" | "reviewer" | "supervisor", moduleName: string, projectKind: string): string[] {
  const value = `${moduleName} ${projectKind}`.toLowerCase();
  if (role === "supervisor") {
    return ["gpt-5", "claude-opus", "claude-sonnet", "openrouter/auto", "qwen2.5:72b"];
  }
  if (role === "reviewer") {
    return ["claude-opus", "claude-sonnet", "gpt-5", "qwen2.5:72b", "openrouter/auto"];
  }
  if (/(privacy|pii|local|polish|polski|dane|safety|guard)/.test(value)) {
    return ["bielik", "pllum", "qwen2.5:72b", "claude-sonnet", "gpt-5"];
  }
  if (/(funding|grant|research|source|market|nab[oó]r|wniosek|krs)/.test(value)) {
    return ["sonar", "perplexity", "gemini", "openrouter/auto", "gpt-5"];
  }
  if (/(security|auth|rbac|payment|fraud|legal|compliance)/.test(value)) {
    return ["gpt-5", "claude-sonnet", "claude-opus", "qwen2.5:72b"];
  }
  if (/(ui|front|dashboard|console|crm|admin|mobile)/.test(value)) {
    return ["gpt-5", "claude-sonnet", "gpt-4o", "gemini", "qwen2.5:72b"];
  }
  return ["gpt-5", "claude-sonnet", "kimi", "glm", "qwen2.5:72b", "openrouter/auto"];
}

function chooseCatalogModel(catalog: ModelCatalogItem[], patterns: string[]): ModelCatalogItem {
  for (const pattern of patterns) {
    const lowerPattern = pattern.toLowerCase();
    const match = catalog.find((item) => {
      const haystack = `${item.model_id} ${item.display_name}`.toLowerCase();
      return haystack.includes(lowerPattern);
    });
    if (match) return match;
  }
  return catalog.find((item) => item.model_id === "openrouter/auto") || catalog[0] || STATIC_MODEL_CATALOG[0];
}

function buildExecutionModelSuggestions(
  project: ProjectState | null,
  catalog: ModelCatalogItem[],
): ExecutionModelAssignment[] {
  const modules = projectModuleRows(project);
  const masterplanReady = Boolean(project?.masterplan_frozen_at || project?.masterplan);
  const projectKind = project?.project_kind || "application";
  return modules.map((module) => {
    const worker = chooseCatalogModel(catalog, modelPatternsFor("worker", module.name, projectKind));
    const reviewer = chooseCatalogModel(catalog, modelPatternsFor("reviewer", module.name, projectKind));
    const supervisor = chooseCatalogModel(catalog, modelPatternsFor("supervisor", module.name, projectKind));
    return {
      module_id: module.module_id,
      module_name: module.name,
      worker_model_id: worker.model_id,
      worker_provider: worker.provider,
      reviewer_model_id: reviewer.model_id,
      reviewer_provider: reviewer.provider,
      supervisor_model_id: supervisor.model_id,
      supervisor_provider: supervisor.provider,
      reasoning_effort: /security|payment|legal|safety|privacy|pii/i.test(module.name) ? "high" : "medium",
      suggestion_basis: masterplanReady
        ? "Sugestia po Masterplanie: dobór do modułu i roli wykonawczej."
        : "Szkic przed zamrożeniem Masterplanu: finalny dobór powinien wrócić po zatwierdzeniu modułów.",
    };
  });
}

function normalizeExecutionAssignments(input: unknown): ExecutionModelAssignment[] {
  if (!Array.isArray(input)) return [];
  return input
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Partial<ExecutionModelAssignment>;
      const moduleId = String(row.module_id || "").trim();
      const moduleName = moduleDisplayName(String(row.module_name || moduleId || "").trim());
      if (!moduleId || !moduleName) return null;
      return {
        module_id: moduleId,
        module_name: moduleName,
        worker_model_id: String(row.worker_model_id || "").trim(),
        worker_provider: String(row.worker_provider || inferProvider(String(row.worker_model_id || "")) || "").trim(),
        reviewer_model_id: String(row.reviewer_model_id || "").trim(),
        reviewer_provider: String(row.reviewer_provider || inferProvider(String(row.reviewer_model_id || "")) || "").trim(),
        supervisor_model_id: String(row.supervisor_model_id || "").trim(),
        supervisor_provider: String(row.supervisor_provider || inferProvider(String(row.supervisor_model_id || "")) || "").trim(),
        reasoning_effort: String(row.reasoning_effort || "medium").trim(),
        suggestion_basis: String(row.suggestion_basis || "").trim(),
      };
    })
    .filter(Boolean) as ExecutionModelAssignment[];
}

function suggestionRequiresProbe(suggestion: CouncilSuggestion | null): boolean {
  if (!suggestion) return true;
  if (suggestion.requires_model_probe !== undefined) return Boolean(suggestion.requires_model_probe);
  if (suggestion.plan?.requires_model_probe !== undefined) return Boolean(suggestion.plan.requires_model_probe);
  if (suggestion.model_probe?.completed === true || suggestion.plan?.model_probe?.completed === true) return false;
  return (suggestion.suggestion_stage || suggestion.plan?.suggestion_stage || "provisional") !== "profiled";
}

function humanizeToken(value: string | undefined, fallback = "brak"): string {
  if (!value) return fallback;
  return value.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

function labelFromMap(value: string | undefined, labels: Record<string, string>, fallback = "brak"): string {
  if (!value) return fallback;
  return labels[value] || humanizeToken(value, fallback);
}

function verdictLabel(value: string | undefined): string {
  return labelFromMap(value, VERDICT_LABELS, "brak werdyktu");
}

function statusLabel(value: string | undefined): string {
  return labelFromMap(value || "unknown", STATUS_LABELS, "Nieznany");
}

function riskLevelLabel(value: string | undefined): string {
  return {
    low: "niski",
    medium: "średni",
    high: "wysoki",
    critical: "krytyczny",
  }[value || ""] || humanizeToken(value, "nieznany");
}

function riskLabels(flags: string[] | undefined): string[] {
  return (flags || []).map((flag) => labelFromMap(flag, RISK_FLAG_LABELS)).filter(Boolean);
}

function isLegacyArtificialV10Result(result: CouncilDeliberationResult, basis: V10CouncilReviewBasis | null): boolean {
  if (basis) return false;
  const flags = result.risk_flags || [];
  return flags.includes("risk_level_high") || flags.includes("vps_workers_gt_3") || flags.includes("external_action");
}

function effectiveRiskFlags(result: CouncilDeliberationResult, basis: V10CouncilReviewBasis | null): string[] {
  const flags = result.risk_flags || [];
  if (!isLegacyArtificialV10Result(result, basis)) return flags;
  return flags.filter((flag) => !LEGACY_ARTIFICIAL_V10_FLAGS.has(flag));
}

function sentinelLabels(values: string[] | undefined): string[] {
  return (values || [])
    .map((value) => labelFromMap(value, SENTINEL_LABELS))
    .filter((value) => value && value !== "brak blokady");
}

function nonNegativeNumber(value: string | number | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function formatUsdValue(value: string | number | null | undefined): string {
  return nonNegativeNumber(value ?? 0).toFixed(2);
}

function v10ReviewDraftSnapshot(draft: V10CouncilReviewDraft): string {
  return JSON.stringify(draft);
}

function v10ReviewDraftStorageKey(projectId: string): string {
  return `aeis:v10-review-draft:${projectId}`;
}

function normalizeV10ReviewDraft(value: unknown): V10CouncilReviewDraft {
  const raw = value && typeof value === "object" ? (value as Partial<V10CouncilReviewDraft>) : {};
  const riskLevel = ["auto", "low", "medium", "high", "critical"].includes(String(raw.risk_level))
    ? (raw.risk_level as V10CouncilReviewDraft["risk_level"])
    : DEFAULT_V10_REVIEW_DRAFT.risk_level;
  return {
    risk_level: riskLevel,
    cost_delta_usd: String(raw.cost_delta_usd ?? DEFAULT_V10_REVIEW_DRAFT.cost_delta_usd),
    monthly_cost_delta_usd: String(raw.monthly_cost_delta_usd ?? DEFAULT_V10_REVIEW_DRAFT.monthly_cost_delta_usd),
    vps_workers: String(raw.vps_workers ?? DEFAULT_V10_REVIEW_DRAFT.vps_workers),
    external_action: Boolean(raw.external_action),
    production_deploy: Boolean(raw.production_deploy),
    final_action: Boolean(raw.final_action),
    legal_or_financial_action: Boolean(raw.legal_or_financial_action),
  };
}

function riskLevelForV10Review(
  autonomyLevel: string | undefined,
  draft: V10CouncilReviewDraft,
  values: { costDelta: number; monthlyCostDelta: number; vpsWorkers: number },
): string {
  if (draft.risk_level !== "auto") return draft.risk_level;
  if (draft.final_action || draft.legal_or_financial_action || draft.production_deploy) return "high";
  if (
    draft.external_action ||
    values.vpsWorkers > 3 ||
    values.monthlyCostDelta > 100 ||
    values.costDelta > 25 ||
    autonomyLevel === "L3" ||
    autonomyLevel === "L4"
  ) {
    return "medium";
  }
  return "low";
}

function buildV10CouncilReview(
  budget: BudgetState | null,
  autonomy: AutonomyState | null,
  draft: V10CouncilReviewDraft,
): { request: Record<string, unknown>; basis: V10CouncilReviewBasis } {
  const budgetLimit = Math.max(0, Number(budget?.cap_usd ?? 0) || 0);
  const autonomyLevel = autonomy?.level || "L0";
  const costDelta = nonNegativeNumber(draft.cost_delta_usd);
  const monthlyCostDelta = nonNegativeNumber(draft.monthly_cost_delta_usd);
  const vpsWorkers = Math.max(0, Math.floor(nonNegativeNumber(draft.vps_workers)));
  const riskLevel = riskLevelForV10Review(autonomyLevel, draft, {
    costDelta,
    monthlyCostDelta,
    vpsWorkers,
  });
  const scope = ["źródło prawdy", "Masterplan", "architektura"];
  const basis: V10CouncilReviewBasis = {
    risk_level: riskLevel,
    risk_basis:
      draft.risk_level === "auto"
        ? `Poziom wyliczony z ustawień formularza tego uruchomienia i autonomii ${autonomyLevel}.`
        : "Poziom ustawiony ręcznie przez operatora w formularzu tego uruchomienia.",
    budget_limit_usd: budgetLimit,
    cost_delta_usd: costDelta,
    monthly_cost_delta_usd: monthlyCostDelta,
    vps_workers: vpsWorkers,
    vps_basis: "Liczba workerów VPS pochodzi wyłącznie z pola ustawionego przez operatora przed uruchomieniem Rady.",
    external_action: draft.external_action,
    external_action_basis: draft.external_action
      ? "Operator zaznaczył, że oceniany plan obejmuje akcję poza systemem."
      : "Operator nie zaznaczył akcji poza systemem; jeżeli plan ją obejmuje, ten przełącznik trzeba włączyć przed Radą.",
    production_deploy: draft.production_deploy,
    production_deploy_basis: draft.production_deploy
      ? "Operator zaznaczył, że oceniany plan obejmuje wdrożenie produkcyjne."
      : "Operator nie zaznaczył wdrożenia produkcyjnego; jeżeli plan je obejmuje, ten przełącznik trzeba włączyć przed Radą.",
    final_action: draft.final_action,
    legal_or_financial_action: draft.legal_or_financial_action,
    scope,
  };

  return {
    basis,
    request: {
      title: "Pełny przegląd gotowości Rady V10",
      description:
        "Uruchomiony z dashboardu przegląd V10 w trybie read-only. Sprawdź gotowość kanonu, Masterplanu i architektury, budżet projektu, barierę odpowiedzi modeli, podpis krytyka, sentinele, mapę sprzeciwu i eskalację HumanGate przed ewentualną budową albo akcją zewnętrzną.",
      change_type: "v10_audit_project_readiness",
      risk_level: riskLevel,
      external_action: draft.external_action,
      production_deploy: draft.production_deploy,
      final_action: draft.final_action,
      legal_or_financial_action: draft.legal_or_financial_action,
      affects_source_of_truth: true,
      affects_masterplan: true,
      affects_architecture: true,
      cost_delta_usd: costDelta,
      monthly_cost_delta_usd: monthlyCostDelta,
      vps_workers: vpsWorkers,
    },
  };
}

function v10CouncilBasisLines(result: CouncilDeliberationResult, basis: V10CouncilReviewBasis | null): string[] {
  if (basis) {
    const scope = Array.isArray(basis.scope) && basis.scope.length > 0 ? basis.scope : ["źródło prawdy", "Masterplan", "architektura"];
    const vpsWorkers = Math.max(0, Math.floor(nonNegativeNumber(basis.vps_workers)));
    return [
      `Poziom ryzyka: ${riskLevelLabel(basis.risk_level)} - ${basis.risk_basis}`,
      `Budżet: limit projektu ${formatUsdValue(basis.budget_limit_usd)} USD; oceniany przyrost kosztu ${formatUsdValue(basis.cost_delta_usd)} USD i miesięczny przyrost ${formatUsdValue(basis.monthly_cost_delta_usd)} USD.`,
      `VPS/workery: ${vpsWorkers} - ${basis.vps_basis || "brak zapisanej podstawy liczby workerów"}`,
      `Akcja zewnętrzna: ${basis.external_action ? "tak" : "nie zaznaczono"} - ${basis.external_action_basis}`,
      `Wdrożenie produkcyjne: ${basis.production_deploy ? "tak" : "nie zaznaczono"} - ${basis.production_deploy_basis}`,
      `Akcja finalna: ${basis.final_action ? "tak" : "nie zaznaczono"}; czynność prawna/finansowa: ${basis.legal_or_financial_action ? "tak" : "nie zaznaczono"}.`,
      `Zakres przeglądu: ${scope.join(", ")}. To oznacza zakres audytu, nie automatyczną modyfikację tych artefaktów.`,
    ];
  }

  const flags = result.risk_flags || [];
  if (flags.includes("risk_level_high") || flags.includes("vps_workers_gt_3") || flags.includes("external_action")) {
    return [
      "Ten wynik pochodzi ze starszego uruchomienia Rady. Poprzedni payload zawierał sztuczne założenia: risk_level=high, external_action=true, vps_workers=4 oraz cost_delta_usd ustawiony z limitu budżetu.",
      "Fałszywe flagi zostały odfiltrowane z głównej listy ryzyk. Poprawione nowe uruchomienia V10 nie zakładają wysokiego ryzyka, akcji zewnętrznej, przyrostu kosztu ani liczby VPS bez danych z projektu/infrastruktury.",
    ];
  }

  return ["Brak zapisanej podstawy payloadu dla historycznego wyniku. Nowe uruchomienia zapisują i pokazują podstawę oceny w tym panelu."];
}

function analysisSummary(
  analysis: NonNullable<CouncilDeliberationResult["analyses"]>[number],
  flags: string[] | undefined,
): string {
  const role = roleLabel(analysis.role || analysis.participant?.role || "");
  const verdict = verdictLabel(analysis.verdict);
  const source = SOURCE_LABELS[analysis.source || ""];
  const sentinels = sentinelLabels(analysis.sentinel_blocks);
  const risks = riskLabels(flags).slice(0, 4);
  const confidence =
    typeof analysis.confidence === "number" && analysis.confidence > 0
      ? ` Pewność: ${Math.round(analysis.confidence * 100)}%.`
      : "";
  const sourceNote = analysis.source && analysis.source !== "real_llm"
    ? ` Źródło: ${source || humanizeToken(analysis.source)}; wymagana kontrola operatora.`
    : "";
  const riskNote = risks.length ? ` Zakres kontroli: ${risks.join(", ")}.` : " Brak blokujących ryzyk w zakresie Rady.";
  const sentinelNote = sentinels.length ? ` Sentinele: ${sentinels.join(", ")}.` : "";

  return `${role}: ${verdict}.${riskNote}${sentinelNote}${confidence}${sourceNote}`;
}

function normalizeCouncilMember(member: CouncilMember): CouncilMember {
  const modelId = memberModelId(member);
  const reasoning = memberReasoningEffort(member);
  return {
    ...member,
    model_id: modelId,
    provider: member.provider || inferProvider(modelId),
    preferred_models: member.preferred_models?.length ? member.preferred_models : modelId ? [modelId] : [],
    config: {
      ...(member.config ?? {}),
      rank: memberRank(member),
      preferred_models: member.config?.preferred_models?.length
        ? member.config.preferred_models
        : modelId
          ? [modelId]
          : [],
      reasoning_effort: reasoning,
      thinking_depth: reasoning,
    },
    reasoning_effort: reasoning,
  };
}

function memberToPlanEntry(member: CouncilMember): Record<string, unknown> {
  const normalized = normalizeCouncilMember(member);
  return {
    role: memberRole(normalized),
    rank: memberRank(normalized),
    provider: normalized.provider,
    model_id: normalized.model_id,
    preferred_models: normalized.preferred_models,
    voting_weight: memberWeight(normalized),
    reasoning_effort: memberReasoningEffort(normalized),
    responsibility: normalized.config?.responsibility ?? "",
    required_signature: Boolean(normalized.config?.required_signature),
  };
}

function latestV10CouncilFromProject(project: ProjectState | null): CouncilDeliberationResult | null {
  const latest = (project?.events || [])
    .filter((event) => event.event_type === "project.council.deliberation.requires_human_gate")
    .sort((a, b) => Number(b.emitted_at || 0) - Number(a.emitted_at || 0))[0];
  const payload = latest?.payload;
  if (!payload) return null;
  const riskFlags = Array.isArray(payload.risk_flags)
    ? payload.risk_flags
    : String(payload.risk_flags || "").split(/\s+/).filter(Boolean);
  const byModel = payload.consensus?.by_model || [];
  return {
    status: payload.status || "requires_human_gate",
    decision_class: payload.decision_class || "D4",
    gate_type: payload.gate_type || "external_action",
    risk_flags: riskFlags,
    human_gate_ticket_id: payload.ticket_id,
    consensus_ratio: Number(payload.ratio ?? 0),
    minimum_ratio: 0.6,
    consensus: payload.consensus,
    session: {
      session_id: payload.council_session_id,
      phase: "v10_audit_project_readiness",
    },
    analyses: byModel.map((item) => ({
      model_id: item.model_id,
      role: "persisted_vote",
      verdict: item.verdict,
      confidence: Number(item.weight ?? 0),
      source: "persisted_project_event",
      rationale: "Persisted Council vote from project event log.",
    })),
  };
}

export default function ProjectOrchestrationPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = String(params?.projectId || "");
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [council, setCouncil] = useState<CouncilState | null>(null);
  const [councilDraft, setCouncilDraft] = useState<CouncilMember[]>([]);
  const [councilSaving, setCouncilSaving] = useState(false);
  const [councilNotice, setCouncilNotice] = useState<string | null>(null);
  const [budget, setBudget] = useState<BudgetState | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomyState | null>(null);
  const [suggestion, setSuggestion] = useState<CouncilSuggestion | null>(null);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [modelReadiness, setModelReadiness] = useState<ModelReadinessState>({
    status: "unchecked",
    activeProviders: [],
    registeredModels: [],
    projectCandidateModels: [],
  });
  const [budgetDraftCap, setBudgetDraftCap] = useState("0");
  const [budgetDraftSoft, setBudgetDraftSoft] = useState("0");
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [budgetNotice, setBudgetNotice] = useState<string | null>(null);
  const [autonomyDraft, setAutonomyDraft] = useState("L0");
  const [autonomySaving, setAutonomySaving] = useState(false);
  const [autonomyNotice, setAutonomyNotice] = useState<string | null>(null);
  const [project, setProject] = useState<ProjectState | null>(null);
  const [round2Loading, setRound2Loading] = useState(false);
  const [round2Notice, setRound2Notice] = useState<string | null>(null);
  const [round2Approved, setRound2Approved] = useState(false);
  const [buildLoading, setBuildLoading] = useState(false);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [buildOk, setBuildOk] = useState<string | null>(null);
  const [v10CouncilLoading, setV10CouncilLoading] = useState(false);
  const [v10CouncilError, setV10CouncilError] = useState<string | null>(null);
  const [v10CouncilResult, setV10CouncilResult] = useState<CouncilDeliberationResult | null>(null);
  const [v10CouncilBasis, setV10CouncilBasis] = useState<V10CouncilReviewBasis | null>(null);
  const [v10HumanGateState, setV10HumanGateState] = useState<string | null>(null);
  const [v10ReviewDraft, setV10ReviewDraft] = useState<V10CouncilReviewDraft>(DEFAULT_V10_REVIEW_DRAFT);
  const [v10ReviewSavedSnapshot, setV10ReviewSavedSnapshot] = useState(v10ReviewDraftSnapshot(DEFAULT_V10_REVIEW_DRAFT));
  const [v10ReviewNotice, setV10ReviewNotice] = useState<string | null>(null);
  const [registeredModelCatalog, setRegisteredModelCatalog] = useState<ModelCatalogItem[]>([]);
  const [localModelCatalog, setLocalModelCatalog] = useState<ModelCatalogItem[]>([]);
  const [openRouterModelCatalog, setOpenRouterModelCatalog] = useState<ModelCatalogItem[]>([]);
  const [modelCatalogLoading, setModelCatalogLoading] = useState(false);
  const [modelCatalogNotice, setModelCatalogNotice] = useState<string | null>(null);
  const [executionModelDraft, setExecutionModelDraft] = useState<ExecutionModelAssignment[]>([]);
  const [executionModelSaving, setExecutionModelSaving] = useState(false);
  const [executionModelNotice, setExecutionModelNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [pj, c, b, a, executionModels] = await Promise.allSettled([
        api.getProjectDetail(projectId),
        api.getProjectCouncil(projectId),
        api.getProjectBudget(projectId),
        api.getProjectAutonomy(projectId),
        api.getProjectExecutionModels(projectId),
      ]);
      if (pj.status === "fulfilled") {
        setProject(pj.value);
        setV10CouncilResult((current) => current || latestV10CouncilFromProject(pj.value));
      }
      const nextCouncil = c.status === "fulfilled" ? c.value : null;
      setCouncil(nextCouncil);
      const nextCouncilMembers = (nextCouncil?.members?.length ? nextCouncil.members : nextCouncil?.plan?.members) ?? [];
      setCouncilDraft(nextCouncilMembers.map((member: CouncilMember) => normalizeCouncilMember(member)));
      const nextBudget = b.status === "fulfilled" ? b.value : null;
      const nextAutonomy = a.status === "fulfilled" ? a.value : null;
      setBudget(nextBudget);
      setAutonomy(nextAutonomy);
      setBudgetDraftCap(String(nextBudget?.cap_usd ?? 0));
      setBudgetDraftSoft(String(nextBudget?.soft_warn_usd ?? 0));
      setAutonomyDraft(nextAutonomy?.level ?? "L0");
      if (executionModels.status === "fulfilled") {
        const assignments = normalizeExecutionAssignments(executionModels.value?.assignments);
        setExecutionModelDraft(assignments);
      } else if (pj.status === "fulfilled") {
        setExecutionModelDraft(normalizeExecutionAssignments(pj.value?.execution_plan?.model_assignments));
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const loadModelCatalog = useCallback(async () => {
    setModelCatalogLoading(true);
    setModelCatalogNotice(null);
    try {
      const [registered, local, openRouter] = await Promise.allSettled([
        api.listRegisteredModels(),
        api.listOllamaModels(),
        api.listOpenRouterModels(1000),
      ]);
      if (registered.status === "fulfilled") {
        setRegisteredModelCatalog(
          ((registered.value?.models || []) as unknown[])
            .map(registryEntryToCatalog)
            .filter(Boolean) as ModelCatalogItem[],
        );
      }
      if (local.status === "fulfilled") {
        setLocalModelCatalog(
          ((local.value?.models || []) as unknown[])
            .map(ollamaEntryToCatalog)
            .filter(Boolean) as ModelCatalogItem[],
        );
      }
      if (openRouter.status === "fulfilled" && openRouter.value?.available !== false) {
        setOpenRouterModelCatalog(
          ((openRouter.value?.models || []) as unknown[])
            .map(openRouterEntryToCatalog)
            .filter(Boolean) as ModelCatalogItem[],
        );
        setModelCatalogNotice(
          `Katalog OpenRouter: wczytano ${openRouter.value?.count ?? 0} z ${openRouter.value?.total_count ?? openRouter.value?.count ?? 0} modeli.`,
        );
      } else if (openRouter.status === "fulfilled") {
        setModelCatalogNotice(`OpenRouter katalog niedostępny: ${openRouter.value?.error || "brak szczegółów"}.`);
      }
    } catch (err) {
      setModelCatalogNotice(err instanceof Error ? `Nie udało się wczytać katalogu modeli: ${err.message}` : "Nie udało się wczytać katalogu modeli.");
    } finally {
      setModelCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, [load]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadModelCatalog();
    });
  }, [loadModelCatalog]);

  useEffect(() => {
    if (!projectId || typeof window === "undefined") return;
    queueMicrotask(() => {
      try {
        const saved = window.localStorage.getItem(v10ReviewDraftStorageKey(projectId));
        const nextDraft = saved ? normalizeV10ReviewDraft(JSON.parse(saved)) : DEFAULT_V10_REVIEW_DRAFT;
        setV10ReviewDraft(nextDraft);
        setV10ReviewSavedSnapshot(v10ReviewDraftSnapshot(nextDraft));
        setV10ReviewNotice(saved ? "Wczytano zapisany zakres Rady V10 dla tego projektu." : null);
      } catch {
        setV10ReviewDraft(DEFAULT_V10_REVIEW_DRAFT);
        setV10ReviewSavedSnapshot(v10ReviewDraftSnapshot(DEFAULT_V10_REVIEW_DRAFT));
        setV10ReviewNotice("Nie udało się wczytać zapisanego zakresu Rady V10. Używam wartości domyślnych.");
      }
    });
  }, [projectId]);

  useEffect(() => {
    const ticketId = v10CouncilResult?.human_gate_ticket_id || "";
    let cancelled = false;
    if (!ticketId) {
      queueMicrotask(() => {
        if (!cancelled) setV10HumanGateState(null);
      });
      return () => {
        cancelled = true;
      };
    }
    api.governanceTicketGet(ticketId)
      .then((ticket) => {
        if (!cancelled) setV10HumanGateState(String(ticket?.state || ""));
      })
      .catch(() => {
        if (!cancelled) setV10HumanGateState(null);
      });
    return () => {
      cancelled = true;
    };
  }, [v10CouncilResult?.human_gate_ticket_id]);

  const handleSuggest = async () => {
    setSuggestLoading(true);
    setCouncilNotice(
      "Advisor tworzy wstępny skład Rady z profilu projektu. Finalny dobór wymaga rozpoznania dostępnych modeli/API na danych projektu.",
    );
    try {
      const r = await api.getProjectCouncilSuggest(projectId);
      setSuggestion(r);
      await load();
    } catch (err) {
      setSuggestion({
        rationale:
          err instanceof Error
            ? `Advisor niedostępny: ${err.message}`
            : "Advisor niedostępny",
      });
    } finally {
      setSuggestLoading(false);
    }
  };

  const checkModelReadiness = async () => {
    setModelReadiness((current) => ({ ...current, status: "checking", message: "SprawdŹam lokalny rejestr modeli i aktywne API." }));
    try {
      const [keysResult, modelsResult] = await Promise.allSettled([
        api.listAPIKeys(),
        api.listRegisteredModels(),
      ]);
      const keysPayload = keysResult.status === "fulfilled" ? keysResult.value : { keys: [] };
      const modelsPayload = modelsResult.status === "fulfilled" ? modelsResult.value : { models: [] };
      const activeProviders = uniqueStrings(
        ((keysPayload as { keys?: unknown[] }).keys || [])
          .filter(isActiveKeyEntry)
          .map(providerFromKeyEntry),
      );
      const registeredModels = uniqueStrings(
        ((modelsPayload as { models?: unknown[] }).models || []).map(modelIdFromRegistryEntry),
      );
      const projectCandidateModels = uniqueStrings(members.flatMap((member) => [
        memberModelId(member),
        ...(member.preferred_models || []),
        ...(member.config?.preferred_models || []),
      ]));
      const hasSignal = activeProviders.length > 0 || registeredModels.length > 0 || projectCandidateModels.length > 0;
      setModelReadiness({
        status: hasSignal ? "limited" : "error",
        activeProviders,
        registeredModels,
        projectCandidateModels,
        checkedAt: new Date().toISOString(),
        message: hasSignal
          ? "Preflight sprawdźił konfigurację lokalną. To nadal nie jest porównanie jakości modeli na załącznikach projektu."
          : "Brak aktywnych providerów lub modeli w lokalnym rejestrze. Rada może być tylko szkicem.",
      });
    } catch (err) {
      setModelReadiness({
        status: "error",
        activeProviders: [],
        registeredModels: [],
        projectCandidateModels: [],
        checkedAt: new Date().toISOString(),
        message: err instanceof Error ? err.message : "Nie udało się sprawdźić modeli i API.",
      });
    }
  };

  const updateCouncilDraftMember = (index: number, updates: Partial<CouncilMember>) => {
    setCouncilNotice(null);
    setCouncilDraft((current) =>
      current.map((member, memberIndex) => {
        if (memberIndex !== index) return member;
        const modelId = updates.model_id ?? memberModelId(member);
        const reasoning = updates.reasoning_effort ?? memberReasoningEffort(member);
        return normalizeCouncilMember({
          ...member,
          ...updates,
          model_id: modelId,
          provider: updates.provider ?? inferProvider(modelId),
          preferred_models: modelId ? [modelId] : [],
          config: {
            ...(member.config ?? {}),
            ...(updates.config ?? {}),
            preferred_models: modelId ? [modelId] : [],
            reasoning_effort: reasoning,
            thinking_depth: reasoning,
          },
          reasoning_effort: reasoning,
        });
      }),
    );
  };

  const saveCouncil = async () => {
    if (!projectId || councilDraft.length === 0) return;
    setCouncilNotice(null);
    setCouncilSaving(true);
    try {
      const normalizedMembers = councilDraft.map((member) => normalizeCouncilMember(member));
      await api.updateProjectCouncil(projectId, {
        members: normalizedMembers,
        plan: {
          ...(council?.plan ?? {}),
          enabled: councilEnabled,
          active_size: normalizedMembers.filter((member) => member.active !== false).length,
          suggested_size: normalizedMembers.length,
          members: normalizedMembers.map(memberToPlanEntry),
        },
      });
      setCouncilNotice("Rada projektu zapisana: role, modele i głębokość myślenia są ustawione dla tego projektu.");
      await load();
    } catch (err) {
      setCouncilNotice(err instanceof Error ? `Błąd zapisu Rady: ${err.message}` : "Błąd zapisu Rady");
    } finally {
      setCouncilSaving(false);
    }
  };

  const saveBudget = async () => {
    const hard = Number(budgetDraftCap);
    const soft = Number(budgetDraftSoft);
    setBudgetNotice(null);
    if (!Number.isFinite(hard) || hard < 0) {
      setBudgetNotice("Błąd: limit musi być liczbą >= 0.");
      return;
    }
    if (!Number.isFinite(soft) || soft < 0) {
      setBudgetNotice("Błąd: próg ostrzegawczy musi być liczbą >= 0.");
      return;
    }
    if (soft > hard && hard > 0) {
      setBudgetNotice("Błąd: próg ostrzegawczy nie może przekraczać twardego limitu.");
      return;
    }
    setBudgetSaving(true);
    try {
      await api.updateProjectBudget(projectId, {
        hard_limit_usd: hard,
        soft_warn_usd: soft,
      });
      setBudgetNotice("Budżet zapisany dla tego projektu.");
      await load();
    } catch (err) {
      setBudgetNotice(err instanceof Error ? `Błąd: ${err.message}` : "Błąd zapisu budżetu");
    } finally {
      setBudgetSaving(false);
    }
  };

  const saveAutonomy = async () => {
    setAutonomyNotice(null);
    setAutonomySaving(true);
    try {
      await api.updateProjectAutonomy(projectId, {
        level: autonomyDraft,
        overrides: {
          source: "project_orchestration_ui",
          changed_by: "operator",
        },
      });
      setAutonomyNotice("Autonomia zapisana dla tego projektu.");
      await load();
    } catch (err) {
      setAutonomyNotice(err instanceof Error ? `Błąd: ${err.message}` : "Błąd zapisu autonomii");
    } finally {
      setAutonomySaving(false);
    }
  };

  const currentModelCatalog = () =>
    dedupeModelCatalog([
      ...registeredModelCatalog,
      ...localModelCatalog,
      ...openRouterModelCatalog,
      ...STATIC_MODEL_CATALOG,
    ]);

  const applyExecutionModelSuggestions = () => {
    const catalog = currentModelCatalog();
    setExecutionModelDraft(buildExecutionModelSuggestions(project, catalog));
    setExecutionModelNotice("Zastosowano sugestie modeli wykonawczych dla aktualnych modułów. Zapisz, żeby utrwalić je w projekcie.");
  };

  const updateExecutionModelAssignment = (
    index: number,
    role: "worker" | "reviewer" | "supervisor",
    modelId: string,
    visibleAssignments: ExecutionModelAssignment[],
  ) => {
    const catalog = currentModelCatalog();
    const provider = providerForModel(catalog, modelId);
    const baseDraft = executionModelDraft.length ? executionModelDraft : visibleAssignments;
    setExecutionModelDraft(
      baseDraft.map((assignment, assignmentIndex) => {
        if (assignmentIndex !== index) return assignment;
        if (role === "worker") {
          return { ...assignment, worker_model_id: modelId, worker_provider: provider };
        }
        if (role === "reviewer") {
          return { ...assignment, reviewer_model_id: modelId, reviewer_provider: provider };
        }
        return { ...assignment, supervisor_model_id: modelId, supervisor_provider: provider };
      }),
    );
    setExecutionModelNotice("Masz niezapisane zmiany w planie modeli wykonawczych.");
  };

  const updateExecutionReasoning = (index: number, reasoning: string, visibleAssignments: ExecutionModelAssignment[]) => {
    const baseDraft = executionModelDraft.length ? executionModelDraft : visibleAssignments;
    setExecutionModelDraft(
      baseDraft.map((assignment, assignmentIndex) =>
        assignmentIndex === index ? { ...assignment, reasoning_effort: reasoning } : assignment,
      ),
    );
    setExecutionModelNotice("Masz niezapisane zmiany w planie modeli wykonawczych.");
  };

  const saveExecutionModels = async (visibleAssignments: ExecutionModelAssignment[]) => {
    const assignments = executionModelDraft.length ? executionModelDraft : visibleAssignments;
    setExecutionModelSaving(true);
    setExecutionModelNotice(null);
    try {
      await api.updateProjectExecutionModels(projectId, {
        assignments,
        catalog_source: "project_orchestration_ui",
      });
      setExecutionModelNotice("Plan modeli wykonawczych zapisany w projekcie.");
      await load();
    } catch (err) {
      setExecutionModelNotice(err instanceof Error ? `Błąd zapisu modeli: ${err.message}` : "Błąd zapisu modeli.");
    } finally {
      setExecutionModelSaving(false);
    }
  };

  const updateV10ReviewDraft = (updates: Partial<V10CouncilReviewDraft>) => {
    setV10CouncilBasis(null);
    setV10ReviewNotice("Masz niezapisane zmiany zakresu Rady V10.");
    setV10ReviewDraft((current) => ({ ...current, ...updates }));
  };

  const saveV10ReviewDraft = () => {
    if (!projectId || typeof window === "undefined") return;
    try {
      const snapshot = v10ReviewDraftSnapshot(v10ReviewDraft);
      window.localStorage.setItem(v10ReviewDraftStorageKey(projectId), snapshot);
      setV10ReviewSavedSnapshot(snapshot);
      setV10ReviewNotice("Zapisano zakres Rady V10 dla tego projektu.");
    } catch {
      setV10ReviewNotice("Nie udało się zapisać zakresu Rady V10 w tej przeglądarce.");
    }
  };

  const approveRound2 = async () => {
    if (!projectId) return;
    setRound2Notice(null);
    setRound2Loading(true);
    try {
      await api.governanceTicketSubmit({
        origin: "workspace",
        project_id: projectId,
        kind: "round2_meta_approval",
        title: "Runda 2 - Księga -> Masterplan",
        reason: "Operator zatwierdza skład rady i zasady planowania na Rundę 2.",
      });
      setRound2Approved(true);
      setRound2Notice("Wniosek o zatwierdzenie Rundy 2 wysłany do HumanGate.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Błąd zatwierdzania";
      setRound2Notice(`Błąd: ${msg}`);
    } finally {
      setRound2Loading(false);
    }
  };

  const authorizeBuild = async () => {
    if (!projectId) return;
    setBuildError(null);
    setBuildOk(null);
    setBuildLoading(true);
    try {
      const body = {
        cost_cap_usd: budget?.cap_usd ?? 0,
        autonomy_level: autonomy?.level ?? "L0",
        external_actions_policy: {},
      };
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/projects/${encodeURIComponent(projectId)}/build/authorize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        setBuildError(`Błąd autoryzacji (${res.status}): ${text || "brak szczegółów"}`);
        return;
      }
      const data = await res.json().catch(() => ({}));
      const ticketId =
        data?.ticket_id ||
        data?.pending_governance_ticket_id ||
        data?.approval?.ticket_id ||
        "";
      setBuildOk(
        ticketId
          ? `Utworzono zgłoszenie HumanGate: ${ticketId}. Otwórz /human-gate, aby je zatwierdzić.`
          : "Autoryzacja budowy została wysłana. Otwórz /human-gate, aby ją zatwierdzić.",
      );
      await load();
    } catch (err) {
      setBuildError(
        err instanceof Error
          ? `Backend niedostępny: ${err.message}`
          : "Backend niedostępny",
      );
    } finally {
      setBuildLoading(false);
    }
  };

  const runV10Council = async () => {
    if (!projectId) return;
    setV10CouncilError(null);
    setV10CouncilLoading(true);
    try {
      saveV10ReviewDraft();
      const review = buildV10CouncilReview(budget, autonomy, v10ReviewDraft);
      setV10CouncilBasis(review.basis);
      const result = await api.councilDeliberate(projectId, review.request);
      setV10CouncilResult(result as CouncilDeliberationResult);
      await load();
    } catch (err) {
      setV10CouncilError(err instanceof Error ? err.message : "Nie udało się uruchomić Rady");
    } finally {
      setV10CouncilLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
        <Loader2 className="w-5 h-5 animate-spin mx-auto text-sylion-blue" />
      </Card>
    );
  }

  const sourceMembers = (council?.members?.length ? council.members : council?.plan?.members) ?? [];
  const members = councilDraft.length ? councilDraft : sourceMembers.map((member) => normalizeCouncilMember(member));
  const councilEnabled = Boolean(council?.enabled ?? council?.plan?.enabled);
  const suggestedMembers = suggestion?.plan?.members ?? [];
  const suggestionNeedsProbe = suggestionRequiresProbe(suggestion);
  const readinessChecked = modelReadiness.status !== "unchecked" && modelReadiness.status !== "checking";
  const cap = budget?.cap_usd ?? 0;
  const spent = budget?.spent_usd ?? 0;
  const usagePct = cap > 0 ? Math.min(100, Math.round((spent / cap) * 100)) : 0;
  const buildPendingTicketId = project?.approvals?.build_pending_ticket_id || "";
  const buildPending = Boolean(buildPendingTicketId);
  const v10ReviewDirty = v10ReviewDraftSnapshot(v10ReviewDraft) !== v10ReviewSavedSnapshot;
  const v10Status = v10CouncilResult?.status || "";
  const v10HumanGateTicketId = v10CouncilResult?.human_gate_ticket_id || "";
  const v10HumanGateApproved = v10HumanGateState === "approved";
  const v10NeedsHumanGate = !v10HumanGateApproved && (Boolean(v10HumanGateTicketId) || v10Status === "requires_human_gate");
  const v10Blocked =
    v10Status === "blocked" ||
    v10Status === "rejected" ||
    v10CouncilResult?.consensus?.verdict === "reject" ||
    v10CouncilResult?.consensus?.verdict === "rejected";
  const v10ReadyForNextStep = Boolean(v10CouncilResult) && (v10HumanGateApproved || (!v10NeedsHumanGate && !v10Blocked));
  const modelCatalog = currentModelCatalog();
  const executionAssignments = executionModelDraft.length
    ? executionModelDraft
    : buildExecutionModelSuggestions(project, modelCatalog);
  const masterplanModelBasis = Boolean(project?.masterplan_frozen_at || project?.masterplan);
  const catalogCounts = {
    registry: registeredModelCatalog.length,
    local: localModelCatalog.length,
    openrouter: openRouterModelCatalog.length,
  };

  return (
    <div className="mx-auto w-full max-w-[1920px] space-y-6 px-3 text-base [&_button]:!min-h-10 [&_button]:!text-sm [&_h1]:!text-2xl [&_h2]:!text-lg [&_input]:!h-11 [&_input]:!text-base [&_label]:!text-sm [&_li]:!text-sm [&_p]:!text-sm [&_span]:!text-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 -ml-2"
            onClick={() => router.push(`/projects/${encodeURIComponent(projectId)}`)}
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Projekt
          </Button>
          <div className="w-8 h-8 rounded-lg bg-sylion-amber/15 flex items-center justify-center">
            <Settings2 className="w-4 h-4 text-sylion-amber" />
          </div>
          <div>
            <h1 className="text-lg font-semibold flex items-center gap-2">
              Meta-orkiestracja projektu
              <HelpTip text="Ustawienia rady, budżetu, autonomii i modeli dla tego projektu. Te wartości nadpisują globalne domyślne ustawieńia z /orchestration. Jeśli sekcja pokazuje dziedziczenie, projekt używa wartości globalnej." />
            </h1>
            <p className="text-[11px] text-muted-foreground">
              {project?.title || projectId}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={load}>
          <RefreshCw className="w-3 h-3 mr-1" />
          Odśwież
        </Button>
      </div>

      <Card className="p-3 border-sylion-blue/30 bg-sylion-blue/5">
        <p className="text-[11px] text-muted-foreground flex items-start gap-2">
          <Activity className="w-3.5 h-3.5 mt-0.5 text-sylion-blue shrink-0" />
          <span>
            Każda sekcja może być ustawiona dla projektu albo dziedziczyć wartości globalne{" "}
            (<a href="/orchestration" className="underline hover:text-foreground">/orchestration</a>).
            Doradca zna profil pomysłu, ale dopóki nie sprawdźisz dostępnych modeli/API i nie ma
            rozpoznania na danych projektu, skład Rady jest tylko wstępny.
          </span>
        </p>
      </Card>

      {project?.canon_frozen_at && !project?.masterplan_frozen_at && (
        <Card className="p-4 border-sylion-amber/30 bg-sylion-amber/5 space-y-3" data-testid="round-2-banner">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-sylion-amber/40 text-sylion-amber text-[10px]">
              RUNDA 2
            </Badge>
            <h2 className="text-sm font-semibold text-sylion-amber flex items-center gap-1.5">
              Księga -&gt; Masterplan
              <HelpTip text="Po zamrożeniu Źródła Prawdy rada projektowa potwierdza skład i zasady planowania, zanim zacznie powstawać Masterplan. Zatwierdzenie tworzy ticket w HumanGate." />
            </h2>
          </div>
          <p className="text-xs text-muted-foreground">
            Po zamrożeniu Źródła Prawdy potwierdź skład Rady i zasady planowania
            dla Masterplanu. Założenia mogły się zmienić od Rundy 1.
          </p>
          <ul className="text-xs space-y-1 ml-4 list-disc text-muted-foreground">
            <li>Czy obecny skład Rady pasuje do zakresu z Księgi?</li>
            <li>Czy budżet wymaga aktualizacji?</li>
            <li>Czy autonomia jest właściwa dla zakresu?</li>
          </ul>
          <div className="flex items-center justify-between gap-2">
            <Button
              data-testid="approve-round-2"
              onClick={approveRound2}
              disabled={round2Loading || round2Approved}
              className="h-8 text-xs bg-sylion-amber/20 text-sylion-amber hover:bg-sylion-amber/30 border border-sylion-amber/40"
            >
              {round2Loading ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : round2Approved ? (
                <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
              ) : null}
              {round2Approved ? "Runda 2 zatwierdzona" : "Zatwierdź Rundę 2"}
            </Button>
            {round2Notice && (
              <p data-testid="round-2-notice" className="text-[10px] text-muted-foreground italic max-w-[60%] text-right">
                {round2Notice}
              </p>
            )}
          </div>
        </Card>
      )}

      {project?.masterplan_frozen_at && !project?.build_authorized_at && (
        <Card className="p-4 border-sylion-red/30 bg-sylion-red/5 space-y-3" data-testid="round-3-banner">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-sylion-red/40 text-sylion-red">
              RUNDA 3
            </Badge>
            <h2 className="text-sm font-semibold text-sylion-red flex items-center gap-1.5">
              Masterplan -&gt; Budowa
              <HelpTip text="Punkt bez powrotu. Po autoryzacji budowy każde przekroczenie limitu kosztu wymaga kolejnego HumanGate finansowego. Ten przycisk otworzy wielobramkowe zgłoszenie HumanGate: finanse, produkcja i akcja zewnętrzna." />
            </h2>
          </div>
          <p className="text-xs text-muted-foreground">
            Zablokuj koszt, zatwierdź modele wykonawcze, ustaw politykę akcji zewnętrznych
            i autoryzuj rozpoczęcie budowy. Po autoryzacji każde przekroczenie limitu
            wymaga kolejnego HumanGate financial.
          </p>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded border border-border/40 p-2">
              <span className="text-muted-foreground">Limit kosztu:</span>
              <span className="font-mono ml-2">${cap.toFixed(2)}</span>
            </div>
            <div className="rounded border border-border/40 p-2">
              <span className="text-muted-foreground">Autonomia:</span>
              <span className="font-mono ml-2">{autonomy?.level || "L0"}</span>
            </div>
          </div>

          {buildPending && (
            <div
              className="rounded border border-sylion-amber/30 bg-sylion-amber/10 px-3 py-2 text-xs text-sylion-amber"
              data-testid="build-pending-human-gate-badge"
            >
              Autoryzacja budowy czeka w HumanGate: {buildPendingTicketId}. Otwórz /human-gate, aby ją zatwierdzić.
            </div>
          )}
          {buildError && (
            <div className="rounded border border-sylion-red/30 bg-sylion-red/10 px-3 py-2 text-xs text-sylion-red flex items-start gap-2">
              <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>{buildError}</span>
            </div>
          )}
          {buildOk && (
            <div className="rounded border border-sylion-green/30 bg-sylion-green/10 px-3 py-2 text-xs text-sylion-green">
              {buildOk}
            </div>
          )}

          <Button
            onClick={authorizeBuild}
            data-testid="authorize-build"
            disabled={buildLoading || buildPending}
            className="bg-sylion-red/20 text-sylion-red hover:bg-sylion-red/30 border border-sylion-red/40"
          >
            {buildLoading && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
            {buildPending
              ? "Wniosek czeka w HumanGate"
              : "Zatwierdź budowę (finanse, produkcja i akcja zewnętrzna)"}
          </Button>
        </Card>
      )}

      <Card
        id="v10-full-council"
        className="p-4 bg-[#0f1629] border-sylion-amber/30 space-y-3 scroll-mt-24"
        data-testid="v10-full-council-panel"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-sylion-amber" />
              Pełna Rada V10
              <HelpTip text="Uruchamia projektówą deliberację Rady: role, wagi, kworum, podpis krytyka, sentinele, zdanie odrębne i HumanGate dla decyzji D4/D5. To nie jest szybka dyskusja Idea Vault." />
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Pełna projektowa Rada V10: bariera odpowiedzi modeli, podpis krytyka,
              sentinele kosztów i bezpieczeństwa, zdanie odrębne oraz eskalacja HumanGate przed budową albo akcją zewnętrzną.
            </p>
          </div>
          <Button
            onClick={runV10Council}
            disabled={v10CouncilLoading || !councilEnabled || members.length === 0}
            data-testid="run-v10-full-council"
            className="shrink-0 bg-sylion-amber/20 text-sylion-amber hover:bg-sylion-amber/30 border border-sylion-amber/40"
          >
            {v10CouncilLoading ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <Scale className="w-3.5 h-3.5 mr-1.5" />
            )}
            Uruchom pełną Radę V10
          </Button>
        </div>

        <div className="rounded-lg border border-sylion-amber/20 bg-sylion-amber/5 p-3" data-testid="v10-council-scope">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-sylion-amber">Zakres oceniany przez Radę V10</p>
              <p className="text-xs text-muted-foreground">
                Te wartości opisują plan, który Rada ma ocenić. Kliknięcie tak/nie tylko zmienia formularz; zapisz zakres albo uruchom Radę.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
              <Badge
                variant="outline"
                className={v10ReviewDirty ? "border-sylion-amber/40 text-sylion-amber" : "border-sylion-green/30 text-sylion-green"}
                data-testid="v10-scope-save-state"
              >
                {v10ReviewDirty ? "niezapisane zmiany" : "zakres zapisany"}
              </Badge>
              <Button
                type="button"
                variant="outline"
                className="border-sylion-amber/40 text-sylion-amber hover:bg-sylion-amber/10"
                data-testid="save-v10-review-scope"
                onClick={saveV10ReviewDraft}
                disabled={!v10ReviewDirty}
              >
                <CheckCircle2 className="mr-1.5 h-4 w-4" />
                Zapisz zakres
              </Button>
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-4">
            <label className="space-y-1 text-sm text-muted-foreground">
              Poziom ryzyka
              <select
                value={v10ReviewDraft.risk_level}
                onChange={(event) =>
                  updateV10ReviewDraft({ risk_level: event.target.value as V10CouncilReviewDraft["risk_level"] })
                }
                className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-sylion-blue"
                data-testid="v10-risk-level"
              >
                {V10_RISK_LEVEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm text-muted-foreground">
              Przyrost kosztu USD
              <input
                value={v10ReviewDraft.cost_delta_usd}
                onChange={(event) => updateV10ReviewDraft({ cost_delta_usd: event.target.value })}
                inputMode="decimal"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                data-testid="v10-cost-delta"
              />
            </label>

            <label className="space-y-1 text-sm text-muted-foreground">
              Przyrost miesięczny USD
              <input
                value={v10ReviewDraft.monthly_cost_delta_usd}
                onChange={(event) => updateV10ReviewDraft({ monthly_cost_delta_usd: event.target.value })}
                inputMode="decimal"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                data-testid="v10-monthly-cost-delta"
              />
            </label>

            <label className="space-y-1 text-sm text-muted-foreground">
              Workery VPS
              <input
                value={v10ReviewDraft.vps_workers}
                onChange={(event) => updateV10ReviewDraft({ vps_workers: event.target.value })}
                inputMode="numeric"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                data-testid="v10-vps-workers"
              />
            </label>
          </div>

          <div className="mt-3 grid gap-2 md:grid-cols-4">
            {[
              { key: "external_action", label: "Akcja zewnętrzna" },
              { key: "production_deploy", label: "Wdrożenie produkcyjne" },
              { key: "final_action", label: "Akcja finalna" },
              { key: "legal_or_financial_action", label: "Czynność prawna/finansowa" },
            ].map((item) => {
              const key = item.key as keyof Pick<
                V10CouncilReviewDraft,
                "external_action" | "production_deploy" | "final_action" | "legal_or_financial_action"
              >;
              return (
                <Button
                  key={item.key}
                  type="button"
                  variant={v10ReviewDraft[key] ? "default" : "outline"}
                  className="justify-start"
                  data-testid={`v10-${item.key}`}
                  onClick={() => updateV10ReviewDraft({ [key]: !v10ReviewDraft[key] } as Partial<V10CouncilReviewDraft>)}
                >
                  {item.label}: {v10ReviewDraft[key] ? "tak" : "nie zaznaczono"}
                </Button>
              );
            })}
          </div>
          {v10ReviewNotice ? (
            <p className={v10ReviewDirty ? "mt-3 text-xs text-sylion-amber" : "mt-3 text-xs text-sylion-green"} data-testid="v10-review-save-notice">
              {v10ReviewNotice}
            </p>
          ) : null}
        </div>

        {!councilEnabled && (
          <div className="rounded border border-sylion-red/30 bg-sylion-red/10 px-3 py-2 text-xs text-sylion-red">
            Rada projektu jest wyłączona. Najpierw włącz albo uzgodnij skład rady.
          </div>
        )}
        {councilEnabled && members.length === 0 && (
          <div className="rounded border border-sylion-red/30 bg-sylion-red/10 px-3 py-2 text-xs text-sylion-red">
            Brak aktywnych członków rady. Zasugeruj skład rady albo odśwież projekt.
          </div>
        )}
        {v10CouncilLoading && (
          <div className="rounded border border-sylion-blue/30 bg-sylion-blue/10 px-3 py-2 text-xs text-sylion-blue">
            Trwa realna deliberacja modeli. Panel zostanie uzupełniony po odpowiedzi backendu.
          </div>
        )}
        {v10CouncilError && (
          <div className="rounded border border-sylion-red/30 bg-sylion-red/10 px-3 py-2 text-xs text-sylion-red">
            Błąd Rady: {v10CouncilError}
          </div>
        )}

        {v10CouncilResult && (
          <div className="space-y-3" data-testid="v10-full-council-result">
            <div className="grid grid-cols-5 gap-2 text-[11px]">
              <div className="rounded border border-border/40 p-2">
                <span className="block text-muted-foreground">Status</span>
                <span className="font-medium">{v10HumanGateApproved ? "HumanGate zatwierdzony" : statusLabel(v10CouncilResult.status)}</span>
              </div>
              <div className="rounded border border-border/40 p-2">
                <span className="block text-muted-foreground">Klasa</span>
                <span className="font-mono">{v10CouncilResult.decision_class || "-"}</span>
              </div>
              <div className="rounded border border-border/40 p-2">
                <span className="block text-muted-foreground">Kworum</span>
                <span className="font-mono">
                  {Number(v10CouncilResult.consensus_ratio ?? 0).toFixed(2)}
                  /{Number(v10CouncilResult.minimum_ratio ?? 0).toFixed(2)}
                </span>
              </div>
              <div className="rounded border border-border/40 p-2">
                <span className="block text-muted-foreground">Podpis krytyka</span>
                <span className="font-medium">
                  {v10CouncilResult.consensus?.critic_signed || v10CouncilResult.critic_signature ? "podpisany" : "brak podpisu"}
                </span>
              </div>
              <div className="rounded border border-border/40 p-2">
                <span className="block text-muted-foreground">HumanGate</span>
                <span className="font-mono break-all">
                  {v10CouncilResult.human_gate_ticket_id || "brak zgłoszenia"}
                  {v10HumanGateApproved ? " · zatwierdzony" : ""}
                </span>
              </div>
            </div>

            <div className="rounded border border-border/40 p-2 text-[11px]">
              <span className="text-muted-foreground">Ryzyka i sentinele: </span>
              <span className="font-medium">
                {riskLabels(effectiveRiskFlags(v10CouncilResult, v10CouncilBasis)).join(", ") || "brak blokujących ryzyk"}
              </span>
            </div>

            <div className="rounded border border-sylion-blue/20 bg-sylion-blue/5 p-3 text-xs" data-testid="v10-council-risk-basis">
              <p className="mb-1 font-semibold text-sylion-blue">Podstawa oceny</p>
              <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
                {v10CouncilBasisLines(v10CouncilResult, v10CouncilBasis).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>

            <div
              className={
                v10NeedsHumanGate
                  ? "rounded-lg border border-sylion-amber/35 bg-sylion-amber/10 p-3"
                  : v10Blocked
                    ? "rounded-lg border border-sylion-red/35 bg-sylion-red/10 p-3"
                    : "rounded-lg border border-sylion-green/35 bg-sylion-green/10 p-3"
              }
              data-testid="v10-next-step"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 space-y-1">
                  <p className="font-semibold">
                    {v10NeedsHumanGate
                      ? "Następny krok: decyzja HumanGate"
                      : v10HumanGateApproved
                        ? "HumanGate zatwierdzony - gotowe do następnego kroku"
                        : v10Blocked
                        ? "Rada V10 zatrzymała ten krok"
                        : "Gotowe do następnego kroku"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {v10NeedsHumanGate
                      ? `Wynik Rady wymaga akceptacji operatora. Bilet ${v10HumanGateTicketId || "jest w kolejce HumanGate"} blokuje dalsze działania do czasu decyzji.`
                      : v10HumanGateApproved
                        ? "Bilet HumanGate został zatwierdzony. Przejdź do lifecycle projektu i kontynuuj z odblokowanego etapu."
                        : v10Blocked
                        ? "Najpierw popraw wskazane ryzyka albo zmień zakres oceny, a potem uruchom Radę ponownie."
                        : "Rada nie utworzyła blokującego HumanGate. Możesz przejść do lifecycle projektu i kontynuować pracę."}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {v10NeedsHumanGate ? (
                    <Button
                      className="bg-sylion-amber/20 text-sylion-amber hover:bg-sylion-amber/30 border border-sylion-amber/40"
                      data-testid="v10-open-human-gate"
                      onClick={() =>
                        router.push(
                          v10HumanGateTicketId
                            ? `/human-gate?ticket=${encodeURIComponent(v10HumanGateTicketId)}`
                            : "/human-gate",
                        )
                      }
                    >
                      <ShieldAlert className="mr-1.5 h-4 w-4" />
                      Otwórz HumanGate
                    </Button>
                  ) : null}
                  {v10ReadyForNextStep ? (
                    <Button
                      className="bg-sylion-green/20 text-sylion-green hover:bg-sylion-green/30 border border-sylion-green/40"
                      data-testid="v10-open-lifecycle"
                      onClick={() => router.push(`/projects/${encodeURIComponent(projectId)}/lifecycle`)}
                    >
                      <CheckCircle2 className="mr-1.5 h-4 w-4" />
                      Przejdź do lifecycle
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      data-testid="v10-open-lifecycle"
                      onClick={() => router.push(`/projects/${encodeURIComponent(projectId)}/lifecycle`)}
                    >
                      Otwórz lifecycle projektu
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    data-testid="v10-open-project"
                    onClick={() => router.push(`/projects/${encodeURIComponent(projectId)}`)}
                  >
                    Otwórz projekt
                  </Button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2" data-testid="v10-council-analyses">
              {(v10CouncilResult.analyses || []).slice(0, 8).map((analysis, index) => (
                <div
                  key={`${analysis.model_id || "model"}-${index}`}
                  className="rounded border border-[rgba(148,163,184,0.08)] p-2 text-[11px]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-foreground">{modelDisplayName(analysis.model_id || "model")}</span>
                    <Badge variant="outline" className="text-[9px] shrink-0">
                      {roleLabel(analysis.role || analysis.participant?.role || "")} / {verdictLabel(analysis.verdict)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground line-clamp-3">
                    {analysisSummary(analysis, effectiveRiskFlags(v10CouncilResult, v10CouncilBasis))}
                  </p>
                  {sentinelLabels(analysis.sentinel_blocks).length ? (
                    <p className="mt-1 text-sylion-amber">
                      Kontrola sentinelowa: {sentinelLabels(analysis.sentinel_blocks).join(", ")}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card
          id="project-council"
          className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-3 scroll-mt-24"
        >
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Scale className="w-3 h-3" />
              Rada projektu
              <HelpTip text="Skład rady, czyli modele, role, rangi i wagi dla tego projektu. Advisor może zasugerować skład pod profil pomysłu, a zmiana powinna być widoczna w planie i audit events." />
            </p>
            <Badge
              variant="outline"
              className={councilEnabled ? "text-[9px] border-sylion-green/30 text-sylion-green" : "text-[9px]"}
            >
              {councilEnabled ? "Aktywna" : "Wyłączona"}
            </Badge>
          </div>

          <div
            className="rounded-lg border border-sylion-amber/25 bg-sylion-amber/5 p-3 text-sm"
            data-testid="project-council-model-readiness"
          >
            <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant="outline"
                    className={
                      modelReadiness.status === "limited" || modelReadiness.status === "ready"
                        ? "border-sylion-amber/40 text-sylion-amber"
                        : modelReadiness.status === "error"
                          ? "border-sylion-red/40 text-sylion-red"
                          : "border-muted-foreground/30 text-muted-foreground"
                    }
                  >
                    {modelReadiness.status === "unchecked"
                      ? "brak rozpoznania modeli"
                      : modelReadiness.status === "checking"
                        ? "sprawdźanie modeli"
                        : modelReadiness.status === "error"
                          ? "brak gotowości modeli"
                          : "preflight modeli wykonany"}
                  </Badge>
                  <span className="text-xs font-medium text-foreground">Sugestia Rady jest wstępna do czasu próby modeli.</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Ten preflight sprawdźa lokalnie aktywne API i rejestr modeli. Nie uruchamia kosztownej analizy
                  przez wszystkie modele i nie zastępuje późniejszej deliberacji na załącznikach projektu.
                </p>
                {modelReadiness.message ? (
                  <p className="text-[11px] text-muted-foreground" data-testid="project-council-readiness-message">
                    {modelReadiness.message}
                  </p>
                ) : null}
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-9 min-w-[220px] border-sylion-amber/40 text-sylion-amber hover:bg-sylion-amber/10"
                onClick={() => void checkModelReadiness()}
                disabled={modelReadiness.status === "checking"}
                data-testid="check-project-model-readiness"
              >
                {modelReadiness.status === "checking" ? (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Bot className="mr-2 h-3.5 w-3.5" />
                )}
                Sprawdź dostępne API i modele
              </Button>
            </div>
            {readinessChecked ? (
              <div className="mt-3 grid gap-2 text-[11px] text-muted-foreground md:grid-cols-3">
                <div className="rounded border border-border/40 bg-background/35 px-2 py-1">
                  <span className="block uppercase tracking-wider">Aktywne API</span>
                  <span className="font-mono text-foreground">
                    {modelReadiness.activeProviders.length ? modelReadiness.activeProviders.join(", ") : "brak"}
                  </span>
                </div>
                <div className="rounded border border-border/40 bg-background/35 px-2 py-1">
                  <span className="block uppercase tracking-wider">Modele w rejestrze</span>
                  <span className="font-mono text-foreground">
                    {modelReadiness.registeredModels.length}
                  </span>
                </div>
                <div className="rounded border border-border/40 bg-background/35 px-2 py-1">
                  <span className="block uppercase tracking-wider">Kandydaci Rady</span>
                  <span className="font-mono text-foreground">
                    {modelReadiness.projectCandidateModels.length || members.length}
                  </span>
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-1" data-testid="project-council-members">
            {members.length === 0 ? (
              <p className="text-[11px] text-muted-foreground italic">
                Rada nie jest skonfigurowana - dziedziczy z ustawień domyślnych albo czeka na inicjalizację przez Advisor.
              </p>
            ) : (
                            members.slice(0, 8).map((member, index) => {
                const selectedModel = memberModelId(member);
                const selectedReasoning = memberReasoningEffort(member);
                const councilModelCatalog = modelCatalog.length > 0 ? modelCatalog : STATIC_MODEL_CATALOG;
                const modelKnown = councilModelCatalog.some((option) => option.model_id === selectedModel);
                return (
                  <div
                    key={member.member_id || member.council_member_id || `${memberRole(member)}-${index}`}
                    className="grid gap-3 rounded-lg border border-[rgba(148,163,184,0.12)] bg-background/35 p-3 text-sm xl:grid-cols-[1.2fr_1fr_0.9fr_auto]"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-foreground">{memberRoleLabel(member)}</span>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {memberRankLabel(member)} · waga {memberWeight(member).toFixed(1)}
                        </Badge>
                        <Badge variant="outline" className="shrink-0 border-sylion-amber/30 text-xs text-sylion-amber">
                          Myślenie: {reasoningShortLabel(selectedReasoning)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {memberResponsibility(member)}
                      </p>
                    </div>

                    <label className="space-y-1 text-sm text-muted-foreground">
                      Model językowy
                      <select
                        value={selectedModel}
                        onChange={(event) => updateCouncilDraftMember(index, { model_id: event.target.value })}
                        className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-sylion-blue"
                        data-testid={`project-council-model-${index}`}
                      >
                        {!selectedModel ? <option value="">Wybierz model</option> : null}
                        {!modelKnown && selectedModel ? <option value={selectedModel}>{modelDisplayName(selectedModel)}</option> : null}
                        {councilModelCatalog.map((option) => (
                          <option key={`council-${option.model_id}`} value={option.model_id}>
                            {modelCatalogLabel(option)}
                          </option>
                        ))}
                      </select>
                      {selectedModel ? (
                        <span className="block text-xs text-muted-foreground">
                          Wybrany: {modelDisplayName(selectedModel)}
                        </span>
                      ) : null}
                    </label>

                    <label className="space-y-1 text-sm text-muted-foreground">
                      Głębokość myślenia modelu
                      <select
                        value={selectedReasoning}
                        onChange={(event) => updateCouncilDraftMember(index, { reasoning_effort: event.target.value })}
                        className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-sylion-blue"
                        data-testid={`project-council-reasoning-${index}`}
                      >
                        {REASONING_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <span className="block text-xs text-muted-foreground">{reasoningLabel(selectedReasoning)}</span>
                    </label>

                    <div className="flex items-center justify-end">
                      <Badge variant="outline" className="border-sylion-blue/30 text-xs text-sylion-blue">
                        {providerLabel(providerForModel(councilModelCatalog, selectedModel) || member.provider || inferProvider(selectedModel))}
                      </Badge>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <Button
              variant="outline"
              size="sm"
              className="h-10 w-full border-sylion-blue/40 text-sylion-blue hover:bg-sylion-blue/10"
              onClick={saveCouncil}
              disabled={councilSaving || members.length === 0}
              data-testid="save-project-council"
            >
              {councilSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              Zapisz Radę projektu
            </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-10 w-full border-sylion-amber/40 text-sm text-sylion-amber hover:bg-sylion-amber/10"
            onClick={handleSuggest}
            disabled={suggestLoading}
            data-testid="suggest-project-council"
          >
            {suggestLoading ? (
              <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            ) : (
              <Sparkles className="w-3 h-3 mr-1" />
            )}
            {readinessChecked ? "Zasugeruj skład Rady po preflight" : "Wstępnie zasugeruj skład Rady"}
          </Button>

          </div>

          {councilNotice ? (
            <p className="rounded-md border border-sylion-blue/25 bg-sylion-blue/5 px-3 py-2 text-sm text-muted-foreground" data-testid="project-council-notice">
              {councilNotice}
            </p>
          ) : null}

          {suggestion && (
            <div className="rounded border border-sylion-amber/30 bg-sylion-amber/5 p-2 space-y-1" data-testid="council-suggestion">
              <p className="text-[10px] uppercase tracking-wider text-sylion-amber">
                {suggestionNeedsProbe ? "Wstępna rekomendacja advisora" : "Rekomendacja advisora po rozpoznaniu"}
              </p>
              {suggestionNeedsProbe ? (
                <p className="rounded border border-sylion-amber/25 bg-background/35 px-2 py-1 text-[11px] text-sylion-amber">
                  Brak dowodu porównania modeli na danych projektu. Ten skład jest szkicem do rozmowy, nie finalną decyzją Rady.
                </p>
              ) : null}
              {suggestion.rationale && (
                <p className="text-[11px] text-muted-foreground italic">
                  {suggestion.rationale}
                </p>
              )}
              {(suggestion.recommended_models || suggestedMembers || []).slice(0, 8).map((rec: SuggestedCouncilItem, index: number) => (
                <div key={`${rec.role || "role"}-${index}`} className="flex items-center justify-between text-[11px] gap-2">
                  <div className="min-w-0 flex-1">
                    <span className="text-foreground">{roleLabel(rec.role || "rola")}</span>
                    <span className="ml-2 text-muted-foreground/80">
                      {modelDisplayName(rec.model_id || rec.preferred_models?.[0] || "model")}
                      {rec.provider ? ` · ${providerLabel(rec.provider)}` : ""}
                    </span>
                  </div>
                  <span className="text-[10px] text-sylion-amber/80 shrink-0">{RANK_LABELS[rec.rank || ""] || rec.rank || "ranga"}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-3">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
            <Wallet className="w-3 h-3" />
            Budżet projektu
            <HelpTip text="Limit kosztów API dla projektu w USD. Twarde zatrzymanie blokuje dalsze wywołania po przekroczeniu limitu. Ten limit jest używany przy autoryzacji Rundy 3." />
          </p>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">Limit</span>
              <span className="text-sm font-mono text-foreground">${cap.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">Wykorzystane</span>
              <span className="text-sm font-mono text-foreground">${spent.toFixed(2)} ({usagePct}%)</span>
            </div>

            <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
              <div
                className={usagePct >= 90 ? "h-full bg-sylion-red" : usagePct >= 70 ? "h-full bg-sylion-amber" : "h-full bg-sylion-green"}
                style={{ width: `${usagePct}%` }}
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                Twarde zatrzymanie
                <HelpTip text="Gdy włączone: po przekroczeniu limitu projekt natychmiast wstrzymuje wywołania API. Gdy wyłączone: wysyła alert, ale pozwala działać dalej." />
              </span>
              <Badge variant="outline" className="text-[9px]">
                {budget?.hard_stop ? "WŁĄCZONE" : "Tylko alert"}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-2">
              <label className="space-y-1 text-[10px] text-muted-foreground">
                Twardy limit USD
                <input
                  data-testid="project-budget-hard-limit"
                  aria-label="Twardy limit USD"
                  value={budgetDraftCap}
                  onChange={(event) => setBudgetDraftCap(event.target.value)}
                  inputMode="decimal"
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
                />
              </label>
              <label className="space-y-1 text-[10px] text-muted-foreground">
                Próg ostrzegawczy USD
                <input
                  data-testid="project-budget-soft-warning"
                  aria-label="Próg ostrzegawczy USD"
                  value={budgetDraftSoft}
                  onChange={(event) => setBudgetDraftSoft(event.target.value)}
                  inputMode="decimal"
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
                />
              </label>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-full text-[10px]"
              onClick={saveBudget}
              disabled={budgetSaving}
              data-testid="save-project-budget"
            >
              {budgetSaving && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
              Zapisz budżet projektu
            </Button>
            {budgetNotice && <p className="text-[10px] text-muted-foreground">{budgetNotice}</p>}
          </div>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-3">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
            <Sliders className="w-3 h-3" />
            Autonomia
            <HelpTip text="Poziom samodzielności agenta. L0 = tylko sugestie, L1 = automatyzacja D0-D1, L2 = automatyzacja do D2, L3 = wysoka autonomia z bramką na D4-D5, L4 = pełna autonomia z raportami po fakcie." />
          </p>

          <div className="flex items-center justify-between">
            <span className="text-[11px]">Poziom</span>
            <Badge variant="outline" className="text-[10px] border-sylion-blue/30 text-sylion-blue font-mono">
              {autonomy?.level || "L0"}
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-[11px] flex items-center gap-1">
              Wymaga zatwierdzania
              <HelpTip text="Gdy włączone: przed znaczącą akcją agent prosi operatora o akceptację w HumanGate." />
            </span>
            <Badge variant="outline" className="text-[9px]">
              {autonomy?.approval_required ? "TAK" : "NIE"}
            </Badge>
          </div>

          <div className="grid grid-cols-5 gap-1">
            {["L0", "L1", "L2", "L3", "L4"].map((level) => (
              <Button
                key={level}
                variant={autonomyDraft === level ? "default" : "outline"}
                size="sm"
                className="h-7 text-[10px]"
                data-testid={`project-autonomy-${level}`}
                onClick={() => setAutonomyDraft(level)}
              >
                {level}
              </Button>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-[10px]"
            onClick={saveAutonomy}
            disabled={autonomySaving}
            data-testid="save-project-autonomy"
          >
            {autonomySaving && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
            Zapisz autonomię projektu
          </Button>
          {autonomyNotice && <p className="text-[10px] text-muted-foreground">{autonomyNotice}</p>}
        </Card>

        <Card className="col-span-2 p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 space-y-2">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                <Bot className="w-3 h-3" />
                Modele wykonawcze projektu
                <HelpTip text="Osobny plan dla modeli, które faktycznie budują, recenzują i nadzorują moduły. Rada projektu pozostaje warstwą decyzyjną, a ten panel opisuje role wykonawcze po Masterplanie." />
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue">
                  Rejestr: {catalogCounts.registry}
                </Badge>
                <Badge variant="outline" className="border-sylion-green/30 text-sylion-green">
                  Lokalne: {catalogCounts.local}
                </Badge>
                <Badge variant="outline" className="border-sylion-amber/30 text-sylion-amber">
                  OpenRouter: {catalogCounts.openrouter}
                </Badge>
                <Badge variant="outline">
                  {masterplanModelBasis ? "sugestie po Masterplanie" : "szkic przed Masterplanem"}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Wybierz modele dla ról: robotnik buduje moduł, recenzent sprawdźa wynik, nadzorca pilnuje spójności i ryzyk. Finalna sugestia ma sens dopiero po Masterplanie, bo wtedy wiadomo, jakie moduły trzeba wykonać.
              </p>
              {modelCatalogNotice ? (
                <p className="text-xs text-muted-foreground" data-testid="project-model-catalog-notice">
                  {modelCatalogNotice}
                </p>
              ) : null}
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-3 xl:w-auto xl:min-w-[520px]">
              <Button
                type="button"
                variant="outline"
                className="h-10 border-sylion-blue/40 text-sylion-blue hover:bg-sylion-blue/10"
                onClick={() => void loadModelCatalog()}
                disabled={modelCatalogLoading}
                data-testid="refresh-project-model-catalog"
              >
                {modelCatalogLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Odśwież katalog
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-10 border-sylion-amber/40 text-sylion-amber hover:bg-sylion-amber/10"
                onClick={applyExecutionModelSuggestions}
                data-testid="apply-project-model-suggestions"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Zastosuj sugestie
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-10 border-sylion-green/40 text-sylion-green hover:bg-sylion-green/10"
                onClick={() => void saveExecutionModels(executionAssignments)}
                disabled={executionModelSaving || executionAssignments.length === 0}
                data-testid="save-project-execution-models"
              >
                {executionModelSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                Zapisz plan
              </Button>
            </div>
          </div>

          {executionModelNotice ? (
            <p className="rounded-md border border-sylion-blue/25 bg-sylion-blue/5 px-3 py-2 text-sm text-muted-foreground" data-testid="project-execution-model-notice">
              {executionModelNotice}
            </p>
          ) : null}

          <div className="space-y-3" data-testid="project-execution-models">
            {executionAssignments.map((assignment, index) => (
              <div
                key={`${assignment.module_id}-${index}`}
                className="rounded-lg border border-[rgba(148,163,184,0.12)] bg-background/35 p-3"
              >
                <div className="mb-3 flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-foreground">{assignment.module_name}</p>
                      <Badge variant="outline" className="border-sylion-amber/30 text-xs text-sylion-amber">
                        Myślenie: {reasoningShortLabel(assignment.reasoning_effort)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{assignment.suggestion_basis}</p>
                  </div>
                  <label className="w-full space-y-1 text-sm text-muted-foreground lg:w-[220px]">
                    Głębokość myślenia dla modułu
                    <select
                      value={assignment.reasoning_effort}
                      onChange={(event) => updateExecutionReasoning(index, event.target.value, executionAssignments)}
                      className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-sylion-blue"
                      data-testid={`project-execution-reasoning-${index}`}
                    >
                      {REASONING_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <span className="block text-xs text-muted-foreground">{reasoningLabel(assignment.reasoning_effort)}</span>
                  </label>
                </div>

                <div className="grid gap-3 xl:grid-cols-3">
                  {(["worker", "reviewer", "supervisor"] as const).map((role) => {
                    const selectedModel =
                      role === "worker"
                        ? assignment.worker_model_id
                        : role === "reviewer"
                          ? assignment.reviewer_model_id
                          : assignment.supervisor_model_id;
                    const selectedProvider =
                      role === "worker"
                        ? assignment.worker_provider
                        : role === "reviewer"
                          ? assignment.reviewer_provider
                          : assignment.supervisor_provider;
                    const provider = selectedProvider || providerForModel(modelCatalog, selectedModel);
                    return (
                      <label
                        key={role}
                        className="space-y-2 rounded-md border border-[rgba(148,163,184,0.1)] bg-background/25 p-3 text-sm text-muted-foreground"
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="font-medium text-foreground">{EXECUTION_ROLE_LABELS[role]}</span>
                          <Badge variant="outline" className="border-sylion-amber/25 text-xs text-sylion-amber">
                            {reasoningShortLabel(assignment.reasoning_effort)}
                          </Badge>
                        </span>
                        <select
                          value={selectedModel}
                          onChange={(event) => updateExecutionModelAssignment(index, role, event.target.value, executionAssignments)}
                          className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-sylion-blue"
                          data-testid={`project-execution-model-${index}-${role}`}
                        >
                          {!selectedModel ? <option value="">Wybierz model</option> : null}
                          {selectedModel && !findCatalogEntry(modelCatalog, selectedModel) ? (
                            <option value={selectedModel}>{modelDisplayName(selectedModel)}</option>
                          ) : null}
                          {modelCatalog.map((item) => (
                            <option key={item.model_id} value={item.model_id}>
                              {modelCatalogLabel(item)}
                            </option>
                          ))}
                        </select>
                        <span className="block text-xs text-muted-foreground">
                          Dostawca: {providerLabel(provider)} · Model: {modelDisplayName(selectedModel)}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-[rgba(148,163,184,0.1)] bg-background/30 p-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Katalog kandydatów</p>
              <span className="text-xs text-muted-foreground">{modelCatalog.length} modeli w selektorach</span>
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              {modelCatalog.slice(0, 12).map((item) => (
                <div key={`catalog-${item.model_id}`} className="min-w-0 rounded border border-[rgba(148,163,184,0.08)] px-2 py-1.5">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className={item.locality === "local" ? "h-3 w-3 shrink-0 text-sylion-green" : "h-3 w-3 shrink-0 text-sylion-blue"} />
                    <span className="truncate text-xs font-medium text-foreground">{item.display_name}</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {providerLabel(item.provider)} · {item.source === "openrouter" ? "katalog OpenRouter" : item.locality || item.source}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {false ? (
        <Card className="hidden">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
            <Bot className="w-3 h-3" />
            Modele projektu
            <HelpTip text="Lista modeli LLM, których ten projekt może używać. Domyślnie dziedziczy z globalnej hierarchii w /orchestration. Advisor potrafi zasugerować skład zależny od domeny pomysłu." />
          </p>

          <div className="space-y-1" data-testid="project-models">
            {members.length === 0 ? (
              <p className="text-[11px] text-muted-foreground italic">
            Zasugeruj skład rady (Advisor)
              </p>
            ) : (
              Array.from(new Set(members.map(modelLabel).filter(Boolean))).slice(0, 6).map((modelId) => (
                <div
                  key={modelId}
                  className="flex items-center gap-2 text-[11px] rounded border border-[rgba(148,163,184,0.06)] px-2 py-1"
                >
                  <ShieldCheck className="w-3 h-3 text-sylion-green" />
                  <span className="font-mono">{modelId}</span>
                </div>
              ))
            )}
          </div>
        </Card>
        ) : null}
      </div>
    </div>
  );
}
