const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  const text = await res.text();
  if (!text.trim()) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

const BASE = "/api/v1/orchestration";

export const orchestrationApi = {
  // Health
  health: () => req<{ status: string }>(`${BASE}/health`),

  // J1 — LLM Judge Routing
  getLLMRouting: () => req<any>(`${BASE}/llm-judge-routing`),
  updateLLMRouting: (cells: any[], preset: string) =>
    req<any>(`${BASE}/llm-judge-routing`, {
      method: "PUT",
      body: JSON.stringify({ cells, preset }),
    }),
  resetLLMRoutingCell: (recommendation_type: string, risk_level: string) =>
    req<any>(`${BASE}/llm-judge-routing/reset-cell`, {
      method: "POST",
      body: JSON.stringify({ recommendation_type, risk_level }),
    }),
  applyLLMRoutingPreset: (preset: "cost-saving" | "balanced" | "aggressive") =>
    req<any>(`${BASE}/llm-judge-routing/preset/${preset}`, { method: "POST" }),

  // J2 — Council Rules
  getCouncilRules: () => req<any>(`${BASE}/council-rules`),
  updateCouncilRules: (data: any) =>
    req<any>(`${BASE}/council-rules`, { method: "PUT", body: JSON.stringify(data) }),
  simulateCouncilVote: (votes: { rank: number; vote: "for" | "against" | "abstain" }[]) =>
    req<any>(`${BASE}/council-rules/simulate-vote`, {
      method: "POST",
      body: JSON.stringify({ votes }),
    }),

  // J3 — Auditor Cadence
  getAuditorCadence: () => req<any>(`${BASE}/auditor-cadence`),
  updateAuditorCadence: (data: any) =>
    req<any>(`${BASE}/auditor-cadence`, { method: "PUT", body: JSON.stringify(data) }),
  triggerAuditNow: () => req<any>(`${BASE}/auditor-cadence/trigger-now`, { method: "POST" }),
  getStopFixRestartStatus: () => req<any>(`${BASE}/stop-fix-restart/status`),
  runStopFixRestart: (payload?: { phase?: string; limit?: number }) =>
    req<any>(`${BASE}/stop-fix-restart/run`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),

  // J4 — Fixer Protocol
  getFixerProtocol: () => req<any>(`${BASE}/fixer-protocol`),
  updateFixerProtocol: (data: any) =>
    req<any>(`${BASE}/fixer-protocol`, { method: "PUT", body: JSON.stringify(data) }),

  // J5 — Dispatch Config
  getDispatchConfig: () => req<any>(`${BASE}/dispatch-config`),
  updateDispatchConfig: (data: any) =>
    req<any>(`${BASE}/dispatch-config`, { method: "PUT", body: JSON.stringify(data) }),

  // J6 — Test Catalog
  getTestCatalog: (params?: { module?: string; status?: string; test_type?: string }) => {
    const qs = params ? "?" + new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][]
    ).toString() : "";
    return req<{ tests: any[] }>(`${BASE}/test-catalog${qs}`);
  },
  getTestCatalogRuns: (limit?: number) =>
    req<{ runs: any[] }>(`${BASE}/test-catalog/runs${limit ? `?limit=${limit}` : ""}`),
  triggerTestRun: (params?: { test_id?: string; suite?: string }) =>
    req<any>(`${BASE}/test-catalog/run-now`, {
      method: "POST",
      body: JSON.stringify(params ?? {}),
    }),

  // J7 — Team Formation Rules
  getTeamFormationRules: () => req<{ rules: any[]; active_teams: any[] }>(`${BASE}/team-formation-rules`),
  updateTeamFormationRules: (rules: any[]) =>
    req<{ rules: any[] }>(`${BASE}/team-formation-rules`, {
      method: "PUT",
      body: JSON.stringify({ rules }),
    }),
  addTeamFormationRule: (rule: any) =>
    req<any>(`${BASE}/team-formation-rules`, { method: "POST", body: JSON.stringify(rule) }),
  triggerTeamFormation: (payload: { event_label: string; task: string }) =>
    req<any>(`${BASE}/team-formation-rules/trigger`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // J8 — Event Map
  getEventMap: (topicPrefix?: string) =>
    req<any>(`${BASE}/event-map${topicPrefix ? `?topic_prefix=${encodeURIComponent(topicPrefix)}` : ""}`),

  // J9 — Inter-Model Conversation
  getInterModelConversation: () => req<any>(`${BASE}/inter-model-conversation`),
  updateInterModelConversation: (data: any) =>
    req<any>(`${BASE}/inter-model-conversation`, { method: "PUT", body: JSON.stringify(data) }),
  triggerInterModelConversation: (payload: { topic: string }) =>
    req<any>(`${BASE}/inter-model-conversation/trigger`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
