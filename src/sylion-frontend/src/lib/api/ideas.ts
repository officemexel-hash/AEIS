const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type IdeaStatus =
  | "draft" | "created" | "clarification" | "submitted"
  | "council_review" | "awaiting_approval" | "accepted"
  | "approved" | "implemented" | "rejected"
  | "stale" | "abandoned" | "archived"
  | "deleted_soft" | "deleted_hard";

export const IDEA_STATUSES: IdeaStatus[] = [
  "draft", "created", "clarification", "submitted",
  "council_review", "awaiting_approval", "accepted",
  "approved", "implemented", "rejected",
  "stale", "abandoned", "archived",
  "deleted_soft", "deleted_hard",
];

export const ACTIVE_STATUSES: IdeaStatus[] = [
  "draft", "created", "clarification", "submitted",
  "council_review", "awaiting_approval", "approved", "accepted",
];

export const TERMINAL_STATUSES: IdeaStatus[] = [
  "rejected", "implemented", "abandoned", "archived",
  "deleted_soft", "deleted_hard",
];

export const DOMAINS = [
  "engineering", "product", "design", "research",
  "infrastructure", "security", "compliance", "finance",
  "marketing", "sales", "operations", "data", "strategy", "other",
] as const;

export type Domain = typeof DOMAINS[number];

export const DOMAIN_LABELS: Record<Domain, string> = {
  engineering: "Inżynieria",
  product: "Produkt",
  design: "Design",
  research: "Badania",
  infrastructure: "Infrastruktura",
  security: "Bezpieczeństwo",
  compliance: "Compliance",
  finance: "Finanse",
  marketing: "Marketing",
  sales: "Sprzedaż",
  operations: "Operacje",
  data: "Dane",
  strategy: "Strategia",
  other: "Inne",
};

export const STATUS_LABELS: Record<IdeaStatus, string> = {
  draft: "Szkic",
  created: "Nowy",
  clarification: "Wyjaśnienie",
  submitted: "Zgłoszony",
  council_review: "Rada",
  awaiting_approval: "Oczekuje",
  accepted: "Zaakceptowany",
  approved: "Zatwierdzony",
  implemented: "Wdrożony",
  rejected: "Odrzucony",
  stale: "Nieaktywny",
  abandoned: "Porzucony",
  archived: "Zarchiwizowany",
  deleted_soft: "W koszu",
  deleted_hard: "Usunięty",
};

// Allowed transitions from each status
export const ALLOWED_TRANSITIONS: Partial<Record<IdeaStatus, IdeaStatus[]>> = {
  draft: ["clarification", "submitted", "council_review", "awaiting_approval", "abandoned", "archived", "deleted_soft"],
  created: ["clarification", "submitted", "council_review", "awaiting_approval", "abandoned", "archived", "deleted_soft"],
  clarification: ["draft", "council_review", "abandoned", "archived", "deleted_soft"],
  submitted: ["clarification", "council_review", "awaiting_approval", "accepted", "rejected", "abandoned", "archived", "deleted_soft"],
  council_review: ["awaiting_approval", "clarification", "rejected", "abandoned", "archived", "deleted_soft"],
  awaiting_approval: ["accepted", "rejected", "council_review", "abandoned", "deleted_soft"],
  approved: ["accepted", "awaiting_approval", "implemented", "abandoned", "archived", "deleted_soft"],
  accepted: ["implemented", "abandoned", "archived", "deleted_soft"],
  implemented: ["archived"],
  rejected: ["draft", "archived", "deleted_soft"],
  stale: ["draft", "abandoned", "archived", "deleted_soft"],
  abandoned: ["draft", "archived", "deleted_soft"],
  archived: ["draft"],
  deleted_soft: ["draft"],
  deleted_hard: [],
};

export const TRANSITION_LABELS: Partial<Record<IdeaStatus, string>> = {
  draft: "Przywróć do szkicu",
  clarification: "Wyślij do wyjaśnienia",
  submitted: "Zgłoś",
  council_review: "Wyślij do Rady",
  awaiting_approval: "Zażądaj zatwierdzenia",
  accepted: "Zaakceptuj",
  approved: "Zatwierdź",
  implemented: "Oznacz jako wdrożony",
  rejected: "Odrzuć",
  abandoned: "Porzuć",
  archived: "Zarchiwizuj",
  deleted_soft: "Przenieś do kosza",
  deleted_hard: "Usuń trwale",
};

export interface Idea {
  idea_id: string;
  title: string;
  description: string;
  author: string;
  status: IdeaStatus;
  category: string;
  priority: string;
  source: string;
  tags: string[];
  upvotes: number;
  downvotes: number;
  created_at: number;
  updated_at: number;
  last_activity_at: number;
  archived_at: number | null;
  deleted_at: number | null;
  stale_at: number | null;
  abandoned_at: number | null;
  previous_status: string;
  human_gate_required: number;
  human_gate_request_id: string;
  human_gate_decision: string;
  human_gate_decided_by: string;
  human_gate_decided_at: number | null;
  clarification_notes: string;
}

export interface IdeaLifecycleEntry {
  log_id: string;
  idea_id: string;
  from_status: string;
  to_status: string;
  actor: string;
  rationale: string;
  logged_at: number;
}

export interface IdeaStats {
  total: number;
  by_status: Record<string, number>;
  top_tags: [string, number][];
  total_votes: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export const STALE_DAYS = 30;
export const TRASH_RETENTION_DAYS = 30;

export function isStaleIdea(idea: Idea): boolean {
  if (!ACTIVE_STATUSES.includes(idea.status)) return false;
  const lastActivity = idea.last_activity_at || idea.updated_at || idea.created_at;
  const diffDays = (Date.now() / 1000 - lastActivity) / 86400;
  return diffDays > STALE_DAYS;
}

export function trashAge(idea: Idea): number {
  if (idea.status !== "deleted_soft" || !idea.deleted_at) return 0;
  return (Date.now() / 1000 - idea.deleted_at) / 86400;
}

export function canHardDelete(idea: Idea): boolean {
  return idea.status === "deleted_soft" && trashAge(idea) >= TRASH_RETENTION_DAYS;
}

export function getDomain(idea: Idea): string {
  const tag = idea.tags.find((t) => t.startsWith("domain:"));
  return tag ? tag.slice(7) : idea.category || "";
}

export function encodeDomain(domain: string, tags: string[]): string[] {
  const filtered = tags.filter((t) => !t.startsWith("domain:"));
  if (domain) filtered.push(`domain:${domain}`);
  return filtered;
}

export function getDisplayTags(idea: Idea): string[] {
  return idea.tags.filter((t) => !t.startsWith("domain:"));
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${body || res.statusText}`);
  }
  const text = await res.text();
  if (!text.trim()) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

// Canonical GET /api/v1/ideas returns array directly
export async function listIdeas(opts: {
  status?: IdeaStatus;
  tag?: string;
  limit?: number;
} = {}): Promise<Idea[]> {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.tag) params.set("tag", opts.tag);
  params.set("limit", String(opts.limit ?? 200));
  const data = await apiFetch<Idea[] | { ideas: Idea[] }>(`/api/v1/ideas?${params}`);
  return Array.isArray(data) ? data : ((data as { ideas: Idea[] }).ideas ?? []);
}

export async function listAllIdeas(): Promise<Idea[]> {
  const statuses: IdeaStatus[] = [
    ...ACTIVE_STATUSES.filter((s) => !["approved", "accepted"].includes(s)),
    "approved", "accepted", "stale", "abandoned",
    "rejected", "implemented", "archived", "deleted_soft",
  ];
  const results = await Promise.allSettled(
    statuses.map((s) => listIdeas({ status: s, limit: 200 }))
  );
  const all: Idea[] = [];
  const seen = new Set<string>();
  for (const r of results) {
    if (r.status === "fulfilled") {
      for (const idea of r.value) {
        if (!seen.has(idea.idea_id)) {
          seen.add(idea.idea_id);
          all.push(idea);
        }
      }
    }
  }
  return all;
}

export async function getIdea(ideaId: string): Promise<Idea | null> {
  try {
    return await apiFetch<Idea>(`/api/v1/ideas/${encodeURIComponent(ideaId)}`);
  } catch {
    return null;
  }
}

export async function createIdea(body: {
  title: string;
  description?: string;
  author?: string;
  tags?: string[];
}): Promise<Idea> {
  const result = await apiFetch<Idea>("/api/v1/ideas", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return result;
}

export async function updateIdea(
  ideaId: string,
  body: { title?: string; description?: string; author?: string; status?: IdeaStatus }
): Promise<Idea> {
  return apiFetch<Idea>(`/api/v1/ideas/${encodeURIComponent(ideaId)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function setIdeaStatus(ideaId: string, status: IdeaStatus): Promise<Idea> {
  return updateIdea(ideaId, { status });
}

export async function hardDeleteIdea(ideaId: string): Promise<void> {
  await apiFetch<unknown>(`/api/v1/ideas/${encodeURIComponent(ideaId)}`, {
    method: "DELETE",
  });
}

export async function getIdeaHistory(ideaId: string): Promise<IdeaLifecycleEntry[]> {
  const data = await apiFetch<{ history: IdeaLifecycleEntry[] }>(
    `/api/v1/ideas/${encodeURIComponent(ideaId)}/history`
  );
  return data.history ?? [];
}

export async function getIdeaStats(): Promise<IdeaStats | null> {
  try {
    return await apiFetch<IdeaStats>("/api/v1/ideas/stats");
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// F-032: discussion + promote-to-project
// ---------------------------------------------------------------------------

export interface PromoteIdeaPayload {
  project_name?: string;
  constraints?: string;
  preferred_stack?: string[];
  attachments?: Array<Record<string, unknown>>;
  auto_execute?: boolean;
  owner_id?: string;
  team_id?: string;
}

export interface PromotedProject {
  project_id: string;
  title?: string;
  status?: string;
  project_kind?: string;
  source_idea_id?: string;
}

export async function promoteIdeaToProject(
  ideaId: string,
  payload: PromoteIdeaPayload = {},
): Promise<{ idea_id: string; project: PromotedProject }> {
  return apiFetch(`/api/v1/ideas/${encodeURIComponent(ideaId)}/promote-to-project`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface DiscussIdeaPayload {
  prompt?: string;
  model_ids?: string[];
  rounds?: number;
}

export interface IdeaDiscussionStart {
  idea_id: string;
  session_id: string | null;
  model_ids: string[];
  rounds: number;
}

export async function startIdeaDiscussion(
  ideaId: string,
  payload: DiscussIdeaPayload = {},
): Promise<IdeaDiscussionStart> {
  return apiFetch(`/api/v1/ideas/${encodeURIComponent(ideaId)}/discuss`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface IdeaDiscussionSession {
  session_id?: string;
  title?: string;
  created_at?: number;
  model_ids?: string[];
}

export async function getIdeaDiscussion(
  ideaId: string,
): Promise<{ idea_id: string; sessions: IdeaDiscussionSession[] }> {
  try {
    return await apiFetch(`/api/v1/ideas/${encodeURIComponent(ideaId)}/discussion`);
  } catch {
    return { idea_id: ideaId, sessions: [] };
  }
}

// ---------------------------------------------------------------------------
// Idea attachments
// ---------------------------------------------------------------------------

export interface IdeaAttachment {
  attachment_id: string;
  idea_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  created_at: number;
}

export interface IdeaAttachmentAnalysis {
  analysis_id: string;
  attachment_id: string;
  idea_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  content_sha256?: string;
  detected_kind?: string;
  extracted_text_preview?: string;
  tags: string[];
  risks: string[];
  missing_info: string[];
  suggested_skills: string[];
  decision_class: string;
  human_gate_required: boolean;
  image_analysis_status?: string;
  created_at: number;
}

export async function listIdeaAttachments(
  ideaId: string,
): Promise<{ attachments: IdeaAttachment[] }> {
  return apiFetch(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/attachments`);
}

export async function analyzeIdeaAttachments(
  ideaId: string,
): Promise<{ idea_id: string; analyses: IdeaAttachmentAnalysis[] }> {
  return apiFetch(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/attachments/analyze`, {
    method: "POST",
  });
}

export async function listIdeaAttachmentAnalysis(
  ideaId: string,
): Promise<{ idea_id: string; analyses: IdeaAttachmentAnalysis[] }> {
  return apiFetch(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/attachments/analysis`);
}

// ---------------------------------------------------------------------------
// FE-1 (round_meta_orchestration): operator answers clarification question
// asked by the council. Sends free-text answer that gets appended to
// `clarification_notes` and lifecycle history.
// ---------------------------------------------------------------------------

export interface ClarificationAnswerPayload {
  answer: string;
  author?: string;
}

export interface ClarificationAnswerResponse {
  idea_id: string;
  clarification_notes: string;
  status?: IdeaStatus;
}

export async function submitClarificationAnswer(
  ideaId: string,
  payload: ClarificationAnswerPayload,
): Promise<ClarificationAnswerResponse> {
  return apiFetch<ClarificationAnswerResponse>(
    `/api/v1/ideas/${encodeURIComponent(ideaId)}/clarification-response`,
    {
      method: "POST",
      body: JSON.stringify({
        response: payload.answer,
        responder: payload.author || "operator",
      }),
    },
  );
}
