const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const HEALTH_PATH = API_BASE ? "/health" : "/api/v1/health";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const method = String(opts?.method || "GET").toUpperCase();
  const fetchOnce = () =>
    fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...opts?.headers },
      ...opts,
    });
  let res: Response;
  try {
    res = await fetchOnce();
  } catch (err) {
    if (method !== "GET") throw err;
    await sleep(150);
    res = await fetchOnce();
  }
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

function fundingCompanyQuery(companyId?: string): string {
  const value = String(companyId || "").trim();
  return value ? `?company_id=${encodeURIComponent(value)}` : "";
}

export const api = {
  // System
  health: () => request<{ status: string; version: string; modules: number; endpoints: number; db_mode?: string }>(HEALTH_PATH),
  getRuntimeTruth: () => request<any>("/api/v1/runtime/truth"),

  // Core
  listModules: () => request<{ modules: any[] }>("/api/v1/core/modules"),
  getModule: (id: string) => request<any>(`/api/v1/core/modules/${encodeURIComponent(id)}`),
  registerModule: (id: string, kind: string, plan: string) =>
    request<any>(`/api/v1/core/modules?module_id=${id}&module_kind=${kind}&owner_plan=${plan}`, { method: "POST" }),
  listEvents: () => request<{ events: any[] }>("/api/v1/core/events"),
  listEvidence: () => request<{ entries: any[] }>("/api/v1/core/evidence"),
  listContracts: () => request<{ contracts: any[] }>("/api/v1/core/contracts"),
  listContractVersions: (name: string) => request<{ versions: any[] }>(`/api/v1/contracts/${encodeURIComponent(name)}/versions`),

  // Governance
  listProposals: () => request<{ proposals: any[] }>("/api/v1/governance/proposals"),
  listGates: () => request<{ gates: any[] }>("/api/v1/governance/gates"),
  listPolicies: () => request<{ policies: any[] }>("/api/v1/governance/policies"),

  // Cognitive
  listPlans: () => request<{ plans: any[] }>("/api/v1/cognitive/plans"),
  listModels: () => request<{ models: any[] }>("/api/v1/cognitive/models"),
  listEvaluations: () => request<{ evaluations: any[] }>("/api/v1/cognitive/evaluations"),

  // Execution
  listTools: () => request<{ tools: any[] }>("/api/v1/execution/tools"),
  listWorkflows: () => request<{ workflows: any[] }>("/api/v1/execution/workflows"),
  listJobs: () => request<{ jobs: any[] }>("/api/v1/execution/jobs"),
  listRetryAttempts: () => request<{ attempts: any[] }>("/api/v1/execution/retry/attempts"),

  // Security
  listAuthProviderUsers: () => request<{ users: any[] }>("/api/v1/security/auth/users"),
  listSessions: () => request<{ sessions: any[] }>("/api/v1/security/sessions"),
  listAuditLog: () => request<{ entries: any[] }>("/api/v1/security/audit"),

  // Monitoring
  listCodeBloat: () => request<{ modules: any[] }>("/api/v1/monitoring/bloat/modules"),
  listCostEnvelope: () => request<{ records: any[] }>("/api/v1/monitoring/cost/records"),
  listSelfObservation: () => request<{ mode: string, [key: string]: any }>("/api/v1/monitoring/preservation/health"),

  // Memory
  listKanonSections: () => request<{ sections: any[] }>("/api/v1/memory/kanon/sections"),
  listEvidenceStore: () => request<{ items: any[] }>("/api/v1/memory/evidence-store"),
  memoryStats: () => request<any>("/api/v1/memory/stats"),
  memoryRecent: (limit = 20) => request<{ items: any[]; count: number }>(`/api/v1/memory/recent?limit=${limit}`),
  storeKanonSection: (payload: { section_id: string; title: string; content: string; chapter?: string; section_number?: number }) =>
    request<any>(
      `/api/v1/memory/kanon/sections?section_id=${encodeURIComponent(payload.section_id)}&title=${encodeURIComponent(payload.title)}&content=${encodeURIComponent(payload.content)}&chapter=${encodeURIComponent(payload.chapter ?? "")}&section_number=${encodeURIComponent(String(payload.section_number ?? 0))}`,
      { method: "POST" },
    ),
  storeMemoryEvidence: (payload: { evidence_id: string; pack_id: string; artefact_type: string; name: string; content: string; metadata?: Record<string, unknown> }) =>
    request<any>(
      `/api/v1/memory/evidence?evidence_id=${encodeURIComponent(payload.evidence_id)}&pack_id=${encodeURIComponent(payload.pack_id)}&artefact_type=${encodeURIComponent(payload.artefact_type)}&name=${encodeURIComponent(payload.name)}&content=${encodeURIComponent(payload.content)}&metadata=${encodeURIComponent(JSON.stringify(payload.metadata ?? {}))}`,
      { method: "POST" },
    ),
  indexMemorySection: (payload: { section_id: string; title: string; content: string }) =>
    request<any>(
      `/api/v1/memory/index/sections?section_id=${encodeURIComponent(payload.section_id)}&title=${encodeURIComponent(payload.title)}&content=${encodeURIComponent(payload.content)}`,
      { method: "POST" },
    ),
  memorySearch: (query: string, limit = 10) =>
    request<any>(`/api/v1/memory/index/search?query=${encodeURIComponent(query)}&limit=${limit}`),
  memoryContext: (query: string, maxTokens = 4000) =>
    request<any>(`/api/v1/memory/retrieval/context?query=${encodeURIComponent(query)}&max_tokens=${maxTokens}`),
  obsidianConnector: () => request<any>("/api/v1/memory/obsidian/connector"),
  obsidianGraph: () => request<any>("/api/v1/memory/obsidian/graph"),
  obsidianStatus: (projectId: string) =>
    request<any>(`/api/v1/memory/obsidian/status?project_id=${encodeURIComponent(projectId)}`),
  obsidianSyncProject: (payload: { project_id: string; related_project_ids?: string[]; force?: boolean; source?: string }) =>
    request<any>("/api/v1/memory/obsidian/sync", {
      method: "POST",
      body: JSON.stringify({
        project_id: payload.project_id,
        related_project_ids: payload.related_project_ids ?? [],
        force: payload.force ?? false,
        source: payload.source ?? "memory_dashboard",
      }),
    }),
  obsidianNote: (projectId: string) =>
    request<any>(`/api/v1/memory/obsidian/notes/${encodeURIComponent(projectId)}`),
  listSelfModels: () =>
    request<any>("/api/v1/brain/models").then((data) => {
      const installed = Array.isArray(data.installed) ? data.installed : [];
      const missing = Array.isArray(data.missing) ? data.missing : [];
      const optional = Array.isArray(data.optional) ? data.optional : [];
      return {
        ...data,
        models: [
          ...installed.map((model_id: string) => ({ model_id, status: "installed" })),
          ...missing.map((model_id: string) => ({ model_id, status: "missing" })),
          ...optional.map((model_id: string) => ({ model_id, status: "optional" })),
        ],
      };
    }),

  // Skills
  listSkills: () => request<{ skills: any[] }>("/api/v1/skills/skills?limit=1000"),
  listSkillExecutions: () => request<{ executions: any[] }>("/api/v1/skills/executions"),
  listDemandSignals: () => request<{ signals: any[] }>("/api/v1/skills/demand/signals"),
  registerSkill: (payload: { skill_id: string; name: string; domain: string; owner_role?: string; description?: string }) =>
    request<any>(
      `/api/v1/skills/skills?skill_id=${encodeURIComponent(payload.skill_id)}&name=${encodeURIComponent(payload.name)}&domain=${encodeURIComponent(payload.domain)}&owner_role=${encodeURIComponent(payload.owner_role ?? "operator")}&description=${encodeURIComponent(payload.description ?? "")}`,
      { method: "POST" },
    ),
  executeSkill: (skillId: string, inputData: Record<string, unknown> = {}) =>
    request<any>(
      `/api/v1/skills/executions?skill_id=${encodeURIComponent(skillId)}&input_data=${encodeURIComponent(JSON.stringify(inputData))}`,
      { method: "POST" },
    ),
  recordDemandSignal: (payload: { signal_type: string; source: string; skill_id: string; confidence: number; details?: Record<string, unknown> }) =>
    request<any>(
      `/api/v1/skills/demand/signals?signal_type=${encodeURIComponent(payload.signal_type)}&source=${encodeURIComponent(payload.source)}&skill_id=${encodeURIComponent(payload.skill_id)}&confidence=${encodeURIComponent(String(payload.confidence))}&details=${encodeURIComponent(JSON.stringify(payload.details ?? {}))}`,
      { method: "POST" },
    ),
  analyzeDemand: () => request<any>("/api/v1/skills/demand/analyze", { method: "POST" }),
  runSkillLifecycleLongRunTest: (payload: { project_id: string; domain: string; owner_role?: string; cycles?: number; include_retirement?: boolean }) =>
    request<any>("/api/v1/skills/lifecycle/long-run-test", {
      method: "POST",
      body: JSON.stringify({
        project_id: payload.project_id,
        domain: payload.domain,
        owner_role: payload.owner_role ?? "operator",
        cycles: payload.cycles ?? 1,
        include_retirement: payload.include_retirement ?? false,
      }),
    }),

  // Quality
  listGoldenSets: () => request<{ sets: any[] }>("/api/v1/quality/golden-sets"),
  listRegressions: () => request<{ alerts: any[] }>("/api/v1/quality/regression/alerts"),

  // Rebuild
  listRebuildPlans: () => request<{ plans: any[] }>("/api/v1/rebuild/orchestrator/plans"),
  listLPW: () => request<{ entries: any[] }>("/api/v1/rebuild/lpw"),
  listCutoverPlans: () => request<{ plans: any[] }>("/api/v1/rebuild/cutover/plans"),

  // Surface
  listAPIEndpoints: () => request<{ endpoints: any[] }>("/api/v1/surface/console/endpoints"),
  listUIComponents: () => request<{ components: any[] }>("/api/v1/surface/ui/components"),
  listWSConnections: () => request<{ connections: any[] }>("/api/v1/surface/ws/connections"),

  // AEIS
  listSelfExplanations: () => request<{ explanations: any[] }>("/api/v1/aeis/explanations"),
  listImprovements: () => request<{ items: any[] }>("/api/v1/aeis/improvements"),
  listSelfLimitations: () => request<{ policies: any[] }>("/api/v1/aeis/limitation/policies"),
  listAutonomyStages: () => request<{ stages: any[] }>("/api/v1/aeis/autonomy/stages"),
  getAutonomyStatus: () => request<{ status: any }>("/api/v1/aeis/autonomy/status"),
  listExplanations: () => request<{ explanations: any[] }>("/api/v1/aeis/explanations"),
  listRatePolicies: () => request<{ policies: any[] }>("/api/v1/aeis/limitation/policies"),

  // Governance — Lifecycle
  listLifecycleStages: () => request<{ stages: any[] }>("/api/v1/governance/lifecycle/stages"),
  listLifecycleEntries: (moduleId?: string) => request<{ entries: any[] }>(`/api/v1/governance/lifecycle/entries${moduleId ? `?module_id=${moduleId}` : ""}`),

  // Governance (extended)
  listDecisionGates: () => request<{ gates: any[] }>("/api/v1/governance/gates"),
  evaluateGate: (gateId: string, context: Record<string, unknown>) =>
    request<{ gate_id: string; result: string; details: any }>(`/api/v1/governance/gates/${encodeURIComponent(gateId)}/evaluate`, {
      method: "POST",
      body: JSON.stringify({ context }),
    }),
  checkCompliance: (scope: string) => request<{ compliance: any }>(`/api/v1/governance/compliance/${encodeURIComponent(scope)}`),
  listComplianceRules: () =>
    request<{ rules: any[] }>("/api/v1/governance/compliance/rules"),
  getComplianceReport: () =>
    request<{ report: any }>("/api/v1/governance/compliance/report/latest"),
  createProposal: (title: string, description: string, scope: string) =>
    request<{ proposal_id: string }>("/api/v1/governance/proposals", {
      method: "POST",
      body: JSON.stringify({ title, description, scope }),
    }),
  voteProposal: (proposalId: string, vote: string) =>
    request<{ proposal_id: string; vote: string }>(`/api/v1/governance/proposals/${encodeURIComponent(proposalId)}/vote`, {
      method: "POST",
      body: JSON.stringify({ vote }),
    }),

  // Efficiency
  listPerfBudgets: () => request<{ budgets: any[] }>("/api/v1/efficiency/budgets"),
  listOverBudget: () => request<{ items: any[] }>("/api/v1/efficiency/budgets/over"),
  listConfigDrift: () => request<{ drift: any[] }>("/api/v1/efficiency/drift"),
  listCircuits: () => request<{ circuits: any[] }>("/api/v1/efficiency/circuits"),

  // Devices (Class M)
  listDiscoveredDevices: () => request<{ devices: any[] }>("/api/v1/devices/discovery"),
  listRegisteredDevices: () => request<{ devices: any[] }>("/api/v1/devices/registry"),
  scanDevices: (transport?: string) => request<{ discovered: any[] }>(`/api/v1/devices/discovery/scan${transport ? `?transport=${transport}` : ""}`, { method: "POST" }),
  listDeployments: () => request<{ deployments: any[] }>("/api/v1/devices/deployments"),
  listDeviceTests: () => request<{ tests: any[] }>("/api/v1/devices/tests"),

  // SDR (Class N)
  listSDRDevices: () => request<{ devices: any[] }>("/api/v1/sdr/devices"),
  listCaptures: () => request<{ captures: any[] }>("/api/v1/sdr/captures"),
  listAnalyses: () => request<{ analyses: any[] }>("/api/v1/sdr/analysis"),
  listRFPolicies: () => request<{ policies: any[] }>("/api/v1/sdr/rf/policies"),

  // Cellular (Class O)
  listRANStacks: () => request<{ stacks: any[] }>("/api/v1/cellular/ran"),
  listCoreNetworks: () => request<{ cores: any[] }>("/api/v1/cellular/cores"),
  listUEDevices: () => request<{ ues: any[] }>("/api/v1/cellular/ue"),
  listIsolationChecks: () => request<{ checks: any[] }>("/api/v1/cellular/isolation"),
  listAttackVectors: () => request<{ vectors: any[] }>("/api/v1/cellular/attack-vectors"),
  listCPAnalyses: () => request<{ analyses: any[] }>("/api/v1/cellular/control-plane"),
  listCellularEvidence: () => request<{ evidence: any[] }>("/api/v1/cellular/evidence"),

  // Cost Envelope
  listCostRecords: (provider?: string) => request<{ records: any[] }>(`/api/v1/efficiency/cost/records${provider ? `?provider=${provider}` : ""}`),
  getDailySpend: (provider?: string) => request<{ daily_spend: number }>(`/api/v1/efficiency/cost/daily${provider ? `?provider=${provider}` : ""}`),
  getMonthlySpend: (provider?: string) => request<{ monthly_spend: number }>(`/api/v1/efficiency/cost/monthly${provider ? `?provider=${provider}` : ""}`),

  // Cost Monitor (alerts + summary)
  getCostAlerts: (limit?: number) => request<{ alerts: any[] }>(`/api/v1/efficiency/cost/alerts${limit ? `?limit=${limit}` : ""}`),
  getCostSummary: () => request<{ providers: any[]; timestamp: number }>("/api/v1/efficiency/cost/summary"),

  // Budget Monitoring
  getModelBudgets: () => request<{ budgets: any[] }>("/api/v1/monitoring/budget"),
  getModelBudget: (modelId: string) => request<any>(`/api/v1/monitoring/budget/${encodeURIComponent(modelId)}`),
  configureModelBudget: (modelId: string, budgetLimit: number, provider?: string, fallbackModelId?: string) =>
    request<any>(`/api/v1/monitoring/budget/${encodeURIComponent(modelId)}`, {
      method: "PUT",
      body: JSON.stringify({ budget_limit: budgetLimit, provider: provider || "", fallback_model_id: fallbackModelId || "" }),
    }),
  recordModelUsage: (modelId: string, amount: number, tokensIn: number, tokensOut: number, taskType: string) =>
    request<{ recorded: boolean }>(`/api/v1/monitoring/budget/${encodeURIComponent(modelId)}/usage`, {
      method: "POST",
      body: JSON.stringify({ amount, tokens_in: tokensIn, tokens_out: tokensOut, task_type: taskType }),
    }),
  getModelTransactions: (modelId?: string, limit?: number) =>
    request<{ transactions: any[] }>(`/api/v1/monitoring/budget/transactions${modelId ? `?model_id=${encodeURIComponent(modelId)}` : ""}${limit ? `${modelId ? "&" : "?"}limit=${limit}` : ""}`),
  getSpendingSummary: () =>
    request<{ total_budget: number; total_spent: number; total_remaining: number; by_model: any[] }>("/api/v1/monitoring/budget/summary"),
  resetModelBudget: (modelId: string) =>
    request<{ reset: boolean }>(`/api/v1/monitoring/budget/${encodeURIComponent(modelId)}/reset`, { method: "POST" }),

  // Decision Snapshots & Cascade
  captureDecisionSnapshot: (data: { decision_id: string; gate_id?: string; session_id?: string; pipeline_run_id?: string; choice_made?: string; choice_id?: string; consequences?: Record<string, unknown> }) =>
    request<{ snapshot: any }>("/api/v1/governance/decision-snapshots", { method: "POST", body: JSON.stringify(data) }),
  getDecisionSnapshot: (snapshotId: string) =>
    request<{ snapshot: any }>(`/api/v1/governance/decision-snapshots/${encodeURIComponent(snapshotId)}`),
  listDecisionSnapshots: (params?: { decision_class?: string; is_active?: boolean; limit?: number }) =>
    request<{ snapshots: any[] }>(`/api/v1/governance/decision-snapshots${params ? `?${new URLSearchParams(Object.entries(params).filter(([,_]) => _ !== undefined).map(([k,v]) => [k, String(v)])).toString()}` : ""}`),
  getDecisionTimeline: (params?: { decision_id?: string; gate_id?: string; session_id?: string }) =>
    request<{ timeline: any[] }>(`/api/v1/governance/decision-snapshots/timeline${params ? `?${new URLSearchParams(Object.entries(params).filter(([,_]) => _ !== undefined && _ !== "").map(([k,v]) => [k, String(v)])).toString()}` : ""}`),
  getActiveDecisionChain: () =>
    request<{ chain: any[] }>("/api/v1/governance/decision-snapshots/active-chain"),
  changeDecision: (snapshotId: string, data: { new_choice: string; new_consequences?: Record<string, unknown> }) =>
    request<{ new_snapshot: any; cascade_events: any[]; invalidated_decisions: any[] }>(`/api/v1/governance/decision-snapshots/${encodeURIComponent(snapshotId)}/change`, { method: "POST", body: JSON.stringify(data) }),
  getCascadeImpact: (snapshotId: string) =>
    request<{ impact_tree: any }>(`/api/v1/governance/decision-snapshots/${encodeURIComponent(snapshotId)}/cascade-impact`),
  getSnapshotDiff: (id1: string, id2: string) =>
    request<{ diff: any }>(`/api/v1/governance/decision-snapshots/${encodeURIComponent(id1)}/diff/${encodeURIComponent(id2)}`),
  acknowledgeCascade: (eventId: string, actionTaken?: string) =>
    request<{ event: any }>(`/api/v1/governance/cascade-events/${encodeURIComponent(eventId)}/acknowledge`, { method: "POST", body: JSON.stringify({ action_taken: actionTaken || "" }) }),
  listCascadeEvents: (requiresHuman?: boolean) =>
    request<{ events: any[] }>(`/api/v1/governance/cascade-events${requiresHuman !== undefined ? `?requires_human=${requiresHuman}` : ""}`),

  // Security Profiles (Phase 5)
  listSecurityProfiles: () => request<{ profiles: any[] }>("/api/v1/security/hardened-profiles"),
  getActiveSecurityProfile: () => request<{ profile: any }>("/api/v1/security/hardened-profiles/active"),
  setActiveSecurityProfile: (name: string) => request<{ profile: any }>("/api/v1/security/hardened-profiles/active", { method: "POST", body: JSON.stringify({ name }) }),

  // Pipeline (Phase 6)
  submitPipelineIdea: (idea: string, context?: Record<string, unknown>) =>
    request<{ run_id: string; status: string }>("/api/v1/pipeline/ideas", {
      method: "POST",
      body: JSON.stringify({ idea, context }),
    }),
  executeRun: (runId: string) =>
    request<{ run_id: string; status: string; steps: any[] }>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}/execute`, { method: "POST" }),
  getRun: (runId: string) =>
    request<{ run_id: string; idea: string; status: string; plan: any; steps: any[]; created_at: number; completed_at: number }>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}`),
  listRuns: () =>
    request<{ runs: any[] }>("/api/v1/pipeline/runs"),
  cancelRun: (runId: string) =>
    request<{ run_id: string; status: string }>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" }),
  getRunSteps: (runId: string) =>
    request<{ steps: any[] }>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}/steps`),
  getExecutionRuntimeCapabilities: () =>
    request<{ capabilities: any; checklist: any[]; operator_gate_required: boolean; active_project_id?: string | null; live_spawn?: any }>("/api/v1/execution-start/runtime-capabilities"),
  getExecutionLiveWorkers: (projectId: string) =>
    request<{ project_id: string; live_spawn: any }>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase32/live-spawn-workers`),
  liveSpawnExecutionWorkers: (projectId: string, payload: Record<string, unknown>) =>
    request<{ project: any; live_spawn: any }>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase32/live-spawn-workers`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  stopExecutionLiveWorkers: (projectId: string, payload: Record<string, unknown>) =>
    request<{ project: any; live_spawn: any }>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase32/stop-live-workers`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // AI Workspace — Chat
  createChatSession: (title: string, modelIds: string[], systemPrompt?: string, teamId?: string, projectId?: string) =>
    request<{ session_id: string; title: string }>("/api/v1/workspace/sessions", {
      method: "POST",
      body: JSON.stringify({ title, model_ids: modelIds, system_prompt: systemPrompt || "", team_id: teamId || "", project_id: projectId || "" }),
    }),
  listChatSessions: (status?: string) =>
    request<{ sessions: any[] }>(`/api/v1/workspace/sessions${status ? `?status=${status}` : ""}`),
  getChatSession: (id: string) =>
    request<any>(`/api/v1/workspace/sessions/${encodeURIComponent(id)}`),
  sendChatMessage: (sessionId: string, content: string, modelId?: string) =>
    request<{ user_message: any; assistant_message: any }>(`/api/v1/workspace/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ role: "user", content, model_id: modelId || "" }),
    }),
  listChatMessages: (sessionId: string, limit?: number) =>
    request<{ messages: any[] }>(`/api/v1/workspace/sessions/${encodeURIComponent(sessionId)}/messages${limit ? `?limit=${limit}` : ""}`),

  // AI Workspace — Council
  openHybridCouncil: (topic: string, description: string, modelIds: string[]) =>
    request<{ session_id: string }>("/api/v1/workspace/council/sessions", {
      method: "POST",
      body: JSON.stringify({ topic, description, model_ids: modelIds }),
    }),
  runParallelAnalysis: (sessionId: string) =>
    request<{ analyses?: any[]; created?: any[] }>(`/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/analyze`, { method: "POST" }),
  runDiscussion: (sessionId: string, roundsPerModel?: number) =>
    request<{ rounds?: any[]; created?: any[] }>(`/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/discuss`, {
      method: "POST",
      body: JSON.stringify({ rounds_per_model: roundsPerModel || 2 }),
    }),
  consolidateCouncil: (sessionId: string) =>
    request<{ consolidated: any; consolidated_suggestion: string }>(`/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/consolidate`, { method: "POST" }),
  listCouncilSessions: (phase?: string) =>
    request<{ sessions: any[] }>(`/api/v1/workspace/council/sessions${phase ? `?phase=${phase}` : ""}`),
  getCouncilSessionSummary: (sessionId: string) =>
    request<any>(`/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/summary`),

  // AR-6.1 — canonical Council surface (9 roles / 5 ranks / critic / sentinels)
  getCouncilRoles: () =>
    request<{
      roles: string[];
      ranks: string[];
      default_role_weights: Record<string, number>;
      rank_multiplier: Record<string, number>;
      sentinel_roles: string[];
    }>("/api/v1/workspace/council/roles"),
  createCouncilSession: (topic: string, description: string, modelIds: string[]) =>
    request<{ session_id: string }>("/api/v1/workspace/council/sessions", {
      method: "POST",
      body: JSON.stringify({ topic, description, model_ids: modelIds }),
    }),
  getCouncilSession: (sessionId: string) =>
    request<any>(`/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}`),
  addCouncilParticipant: (
    sessionId: string,
    payload: { model_id: string; role: string; rank: string; weight?: number | null },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/participants`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  listCouncilParticipants: (sessionId: string) =>
    request<{ participants: any[] }>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/participants`,
    ),
  signCriticDecision: (
    sessionId: string,
    payload: { model_id: string; signed_decision: string; rationale?: string },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/critic/sign`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  listCriticSignatures: (sessionId: string) =>
    request<{ signatures: any[]; signed: boolean }>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/critic/signatures`,
    ),
  evaluateSentinel: (
    sessionId: string,
    payload: {
      sentinel_role: string;
      model_id: string;
      verdict: string;
      score?: number;
      details?: string;
    },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/sentinels/evaluate`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  listSentinelEvaluations: (sessionId: string) =>
    request<{ evaluations: any[] }>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/sentinels`,
    ),
  getCouncilConsensus: (sessionId: string) =>
    request<{
      verdict?: string;
      weights?: Record<string, number>;
      total_weight?: number;
      by_model?: Record<string, any>;
      critic_signed?: boolean;
      sentinel_blocks?: any[];
      [key: string]: any;
    }>(`/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/consensus`),
  consolidateGated: (
    sessionId: string,
    payload: {
      consolidated_text: string;
      require_critic: boolean;
      require_sentinels_pass: boolean;
    },
  ) =>
    request<any>(
      `/api/v1/workspace/council/sessions/${encodeURIComponent(sessionId)}/consolidate-gated`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  // AI Providers and model control plane
  listAIProviders: () => request<{ providers: any[] }>("/api/v1/ai-providers/list"),
  getProviderCatalog: (goal = "mixed") =>
    request<any>(`/api/v1/provider-catalog?goal=${encodeURIComponent(goal)}`),
  getProviderCatalogTemplates: () =>
    request<any>("/api/v1/provider-catalog/templates"),
  refreshProviderCatalogLocal: () =>
    request<any>("/api/v1/provider-catalog/refresh-local", { method: "POST" }),
  getProviderCatalogAcceptance: (goal = "mixed") =>
    request<any>(`/api/v1/provider-catalog/acceptance?goal=${encodeURIComponent(goal)}`),
  autoArrangeModelCouncil: (body?: { force?: boolean; max_members?: number }) =>
    request<any>("/api/v1/provider-catalog/council/auto-arrange", {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  rebuildModelCouncilHierarchy: () =>
    request<any>("/api/v1/provider-catalog/council/rebuild-hierarchy", { method: "POST" }),

  // Phase 3 — Environment Catalog
  getEnvironmentCatalog: (view = "type", autoScan = true) =>
    request<any>(`/api/v1/environment-catalog?view=${encodeURIComponent(view)}&auto_scan=${autoScan ? "true" : "false"}`),
  getEnvironmentTheater: (autoScan = true) =>
    request<any>(`/api/v1/environment-catalog/theater?auto_scan=${autoScan ? "true" : "false"}`),
  getEnvironmentCatalogTemplates: () =>
    request<any>("/api/v1/environment-catalog/templates"),
  getEnvironmentCatalogAcceptance: () =>
    request<any>("/api/v1/environment-catalog/acceptance"),
  scanLocalEnvironment: (body?: { auto_create_local_dev?: boolean; deep_scan?: boolean }) =>
    request<any>("/api/v1/environment-catalog/scan-local", {
      method: "POST",
      body: JSON.stringify(body || { auto_create_local_dev: true, deep_scan: false }),
    }),
  acceptLocalDevEnvironment: (body?: { display_name?: string; purpose?: string; notes?: string }) =>
    request<any>("/api/v1/environment-catalog/local-dev/accept", {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  addDetectedEnvironmentProviders: (providers?: string[]) =>
    request<any>("/api/v1/environment-catalog/providers/detected", {
      method: "POST",
      body: JSON.stringify(providers ? { providers } : {}),
    }),
  createEnvironmentCatalogEntry: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/environments", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createEdgeEnvironmentDevice: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/edge-devices", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  evaluateEnvironmentSovereignty: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/sovereignty/evaluate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getEnvironmentNetwork: () =>
    request<any>("/api/v1/environment-catalog/network"),
  updateEnvironmentNetworkPolicy: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/network/policy", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runEnvironmentNetworkDiagnostic: (body?: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/network/diagnostic", {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  getEnvironmentResidency: () =>
    request<any>("/api/v1/environment-catalog/residency"),
  saveEnvironmentResidencyRule: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/residency/rules", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  checkEnvironmentResidency: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/residency/check", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getEnvironmentResidencyAudit: () =>
    request<any>("/api/v1/environment-catalog/residency/audit"),
  getEnvironmentCosts: () =>
    request<any>("/api/v1/environment-catalog/costs"),
  saveEnvironmentCostAlert: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/costs/alerts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getEnvironmentCleanup: () =>
    request<any>("/api/v1/environment-catalog/cleanup"),
  saveEnvironmentCleanupPolicy: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/cleanup/policy", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createEnvironmentBulkCleanupPlan: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/cleanup/bulk-plan", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getEnvironmentEdgeCases: () =>
    request<any>("/api/v1/environment-catalog/edge-cases"),
  diagnoseEnvironmentEdgeCase: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/edge-cases/diagnose", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  resolveEnvironmentInheritance: (body: Record<string, unknown>) =>
    request<any>("/api/v1/environment-catalog/inheritance/resolve", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runEnvironmentAcceptanceTest: (goal = "apps_internal") =>
    request<any>(`/api/v1/environment-catalog/acceptance-test?goal=${encodeURIComponent(goal)}`),

  // Phase 4 — Workspace Defaults
  getWorkspaceDefaults: (goal = "apps_internal") =>
    request<any>(`/api/v1/workspace-defaults?goal=${encodeURIComponent(goal)}`),
  getWorkspaceDefaultTemplates: () =>
    request<any>("/api/v1/workspace-defaults/templates"),
  applyWorkspaceSmartDefaults: () =>
    request<any>("/api/v1/workspace-defaults/smart-defaults/apply", { method: "POST" }),
  saveWorkspaceDefaultWizardStep: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/wizard/step", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceBudgetTemplate: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/budgets/templates", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  estimateWorkspaceProjectBudget: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/budgets/estimate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceAutonomyMapping: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/autonomy/mapping", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceNotificationMatrix: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/notifications/matrix", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  pairWorkspaceMobile: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/mobile/pair", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceCleanupDefaults: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/cleanup/defaults", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceUiSettings: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/ui", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceShortcut: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/shortcuts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceNavigation: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/navigation", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceApprovals: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/approvals", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceTestStrategy: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/test-strategy", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveWorkspaceCouncilTemplate: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/council/templates", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getWorkspaceDefaultEdgeCases: () =>
    request<any>("/api/v1/workspace-defaults/edge-cases"),
  diagnoseWorkspaceDefaultEdgeCase: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/edge-cases/diagnose", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  previewWorkspaceInheritance: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workspace-defaults/inheritance/preview", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getWorkspaceDefaultsAcceptance: (goal = "apps_internal") =>
    request<any>(`/api/v1/workspace-defaults/acceptance?goal=${encodeURIComponent(goal)}`),
  runWorkspaceDefaultsAcceptanceTest: (goal = "apps_internal") =>
    request<any>(`/api/v1/workspace-defaults/acceptance-test?goal=${encodeURIComponent(goal)}`),

  // Phase 5 - Autonomy Configuration
  getAutonomyConfiguration: (goal = "apps_internal") =>
    request<any>(`/api/v1/autonomy/configuration?goal=${encodeURIComponent(goal)}`),
  getAutonomyConfigurationTemplates: () =>
    request<any>("/api/v1/autonomy/configuration/templates"),
  applyAutonomyPreset: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/apply-preset", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setAutonomyWizardMode: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/wizard/mode", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveAutonomyWizardStep: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/wizard/step", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveAutonomyDimensionConfig: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/dimensions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveAutonomyDLevelOverrides: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/d-level-overrides", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reviewAutonomyHardGates: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/hard-gates/review", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  addAutonomyCustomHardGate: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/hard-gates/custom", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  toggleAutonomyHardGate: (gateId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/autonomy/configuration/hard-gates/${encodeURIComponent(gateId)}/toggle`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createAutonomyOverride: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/overrides", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  traceAutonomyInheritance: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/inheritance/trace", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getAutonomyEdgeCases: () =>
    request<any>("/api/v1/autonomy/configuration/edge-cases"),
  diagnoseAutonomyEdgeCase: (body: Record<string, unknown>) =>
    request<any>("/api/v1/autonomy/configuration/edge-cases/diagnose", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getAutonomyConfigurationAcceptance: (goal = "apps_internal") =>
    request<any>(`/api/v1/autonomy/configuration/acceptance?goal=${encodeURIComponent(goal)}`),
  runAutonomyConfigurationAcceptanceTest: (goal = "apps_internal") =>
    request<any>(`/api/v1/autonomy/configuration/acceptance-test?goal=${encodeURIComponent(goal)}`),

  // Phase 6 - Coherence Guard
  getCoherenceGuard: (goal = "apps_internal") =>
    request<any>(`/api/v1/coherence-guard?goal=${encodeURIComponent(goal)}`),
  getCoherenceGuardTemplates: () =>
    request<any>("/api/v1/coherence-guard/templates"),
  applyCoherenceGuardDefaults: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/defaults/apply", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveCoherenceGuardScope: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/scope", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveCoherenceGuardTriggers: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/triggers", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reviewCoherenceSeverity: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/severity/review", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reviewCoherenceChecks: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/checks/review", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  configureCoherenceCheck: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/checks/config", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  addCoherenceCustomCheck: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/custom-checks", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runCoherenceCheck: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCoherenceFindings: (params?: { status?: string; severity?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.severity) qs.set("severity", params.severity);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<any>(`/api/v1/coherence-guard/findings${suffix}`);
  },
  actOnCoherenceFinding: (findingId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/coherence-guard/findings/${encodeURIComponent(findingId)}/action`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveCoherencePerformance: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/performance", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveCoherenceAutonomyOverride: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/autonomy-override", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCoherenceAggregatedPanel: () =>
    request<any>("/api/v1/coherence-guard/aggregated-panel"),
  getCoherenceEdgeCases: () =>
    request<any>("/api/v1/coherence-guard/edge-cases"),
  diagnoseCoherenceEdgeCase: (body: Record<string, unknown>) =>
    request<any>("/api/v1/coherence-guard/edge-cases/diagnose", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCoherenceAcceptance: (goal = "apps_internal") =>
    request<any>(`/api/v1/coherence-guard/acceptance?goal=${encodeURIComponent(goal)}`),
  runCoherenceAcceptanceTest: (goal = "apps_internal") =>
    request<any>(`/api/v1/coherence-guard/acceptance-test?goal=${encodeURIComponent(goal)}`),

  // Phases 7-10 - Cost/Security/Quality/Provenance Guards
  listGuardSuite: () =>
    request<any>("/api/v1/guards"),
  getGuardSuiteAggregatedPanel: () =>
    request<any>("/api/v1/guards/aggregated-panel"),
  getGuardSetup: (guardId: string, goal = "apps_internal") =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}?goal=${encodeURIComponent(goal)}`),
  getGuardTemplates: (guardId: string) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/templates`),
  applyGuardDefaults: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/defaults/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveGuardConfig: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/config`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reviewGuardChecks: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runGuardCheck: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGuardFindings: (guardId: string, params?: { status?: string; severity?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.severity) qs.set("severity", params.severity);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/findings${suffix}`);
  },
  actOnGuardFinding: (guardId: string, findingId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/findings/${encodeURIComponent(findingId)}/action`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveGuardAutonomyOverride: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/autonomy-override`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGuardEdgeCases: (guardId: string) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/edge-cases`),
  diagnoseGuardEdgeCase: (guardId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/edge-cases/diagnose`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGuardAcceptance: (guardId: string, goal = "apps_internal") =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/acceptance?goal=${encodeURIComponent(goal)}`),
  runGuardAcceptanceTest: (guardId: string, goal = "apps_internal") =>
    request<any>(`/api/v1/guards/${encodeURIComponent(guardId)}/acceptance-test?goal=${encodeURIComponent(goal)}`),

  // Phases 11-15 - Skills Library and Templates Setup
  getTemplatesSetupOverview: () =>
    request<any>("/api/v1/templates-setup"),
  getTemplatesSetupPhase: (phaseId: string, goal = "apps_internal") =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}?goal=${encodeURIComponent(goal)}`),
  applyTemplatesSetupDefaults: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/defaults/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reviewTemplatesSetupArtifacts: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createTemplatesSetupCustomArtifact: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/custom-artifacts`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  simulateTemplatesSetupPhase: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/simulate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getTemplatesSetupEdgeCases: (phaseId: string) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/edge-cases`),
  diagnoseTemplatesSetupEdgeCase: (phaseId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/edge-cases/diagnose`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getTemplatesSetupAcceptance: (phaseId: string) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/acceptance`),
  runTemplatesSetupAcceptanceTest: (phaseId: string) =>
    request<any>(`/api/v1/templates-setup/${encodeURIComponent(phaseId)}/acceptance-test`),

  // Phases 16-19 - Project Start
  getProjectStartOverview: () =>
    request<any>("/api/v1/project-start"),
  getProjectStartTemplates: () =>
    request<any>("/api/v1/project-start/templates"),
  previewProjectStart: (body: Record<string, unknown>) =>
    request<any>("/api/v1/project-start/projects/preview", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createProjectStartProject: (body: Record<string, unknown>) =>
    request<any>("/api/v1/project-start/projects/create", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listProjectStartProjects: () =>
    request<any>("/api/v1/project-start/projects"),
  getActiveProjectStartProject: () =>
    request<any>("/api/v1/project-start/active"),
  getProjectStartProject: (projectId: string) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}`),
  applyProjectStartGoalDefaults: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/goals/defaults`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  applyProjectStartScopeDefaults: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/scope/defaults`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  applyProjectStartCouncilDefaults: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/council/defaults`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  approveProjectStartCouncil: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/council/approve-readiness`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProjectStartAcceptance: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance`),
  runProjectStartAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance-test`),
  getProjectStartEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/edge-cases`),
  diagnoseProjectStartEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/project-start/projects/${encodeURIComponent(projectId)}/edge-cases/diagnose`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Phases 20-25 - Council to Ksiega
  getCouncilToKsiegaOverview: () =>
    request<any>("/api/v1/council-to-ksiega"),
  getActiveCouncilToKsiegaProject: () =>
    request<any>("/api/v1/council-to-ksiega/active"),
  getCouncilToKsiegaProject: (projectId: string) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}`),
  conveneCouncilPhase20: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phase20/convene`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generateInitialVerdictsPhase21: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phase21/initial-verdicts`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runDeliberationRoundsPhase22: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phase22/deliberate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  consolidateCouncilPhase23: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phase23/consolidate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generateCouncilBookPhase24: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phase24/generate-book`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  finalizeKsiegaPhase25: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phase25/finalize-ksiega`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCouncilToKsiegaAcceptance: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance`),
  runCouncilToKsiegaAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance-test`),
  getCouncilToKsiegaEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/edge-cases`),
  diagnoseCouncilToKsiegaEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council-to-ksiega/projects/${encodeURIComponent(projectId)}/edge-cases/diagnose`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Phases 26-28 - Planning Part 1
  getPlanningOverview: () =>
    request<any>("/api/v1/planning"),
  getActivePlanningProject: () =>
    request<any>("/api/v1/planning/active"),
  getPlanningResourceProfiles: () =>
    request<any>("/api/v1/planning/resource-profiles"),
  getPlanningProject: (projectId: string) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}`),
  assignModelsPhase26: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phase26/assign-models`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  synthesizeSkillsPhase27: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phase27/synthesize-skills`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generateMasterplanPhase28: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phase28/generate-masterplan`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generateTestPlanPhase29: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phase29/generate-test-plan`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generatePreflightCostPhase30: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phase30/preflight-cost`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runDryRunPhase31: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phase31/dry-run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getPlanningAcceptance: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance`),
  runPlanningAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance-test`),
  getPlanningEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/edge-cases`),
  diagnosePlanningEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/planning/projects/${encodeURIComponent(projectId)}/edge-cases/diagnose`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Phases 32-39 - Execution, Testing, Pre-Deploy
  getExecutionStartOverview: () =>
    request<any>("/api/v1/execution-start"),
  getActiveExecutionStartProject: () =>
    request<any>("/api/v1/execution-start/active"),
  getExecutionStartProject: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}`),
  getExecutionRuntimeConfiguration: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/runtime-configuration`),
  updateExecutionRuntimeConfiguration: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/runtime-configuration`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getExecutionW18Commands: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/w18-commands`),
  getExecutionAuditTruthMap: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/audit-truth-map`),
  rebuildExecutionAuditTruthMap: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/audit-truth-map/rebuild`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  initializeBuildPhase32: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase32/initialize-build`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startSequentialExecutionPhase33: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase33/start-execution`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getExecutionDispatchControl: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase33/dispatch-control`),
  pauseExecutionDispatch: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase33/pause-dispatch`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  resumeExecutionDispatch: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase33/resume-dispatch`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelExecutionDispatch: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase33/cancel-dispatch`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reconveneMidBuildCouncilPhase34: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase34/reconvene-council`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  activateOrchestrationPhase35: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase35/activate-orchestration`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  completeBuildPhase36: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase36/complete-build`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runQualityGatesPhase37: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase37/run-quality-gates`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  completeAcceptanceTestingPhase38: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase38/complete-acceptance`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  authorizePredeployPhase39: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase39/authorize-predeploy`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  executeProductionDeployPhase40: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase40/execute-production-deploy`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  closeProjectPhase41: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phase41/close-project`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getExecutionStartAcceptance: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance`),
  runExecutionStartAcceptanceTest: (projectId: string, phaseId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/phases/${encodeURIComponent(phaseId)}/acceptance-test`),
  getExecutionStartEdgeCases: (projectId: string) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/edge-cases`),
  diagnoseExecutionStartEdgeCase: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/execution-start/projects/${encodeURIComponent(projectId)}/edge-cases/diagnose`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  testAIProvider: (provider: string, data?: { prompt?: string; model?: string; max_tokens?: number; api_key?: string }) =>
    request<any>(`/api/v1/ai-providers/test/${encodeURIComponent(provider)}`, {
      method: "POST",
      body: JSON.stringify({
        prompt: data?.prompt || "Say OK",
        model: data?.model || null,
        max_tokens: data?.max_tokens || 24,
        api_key: data?.api_key || null,
      }),
    }),
  getAIProviderKeyInfo: (provider: string, apiKey?: string) =>
    request<any>(`/api/v1/ai-providers/key-info/${encodeURIComponent(provider)}`, {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey || null }),
    }),
  listOllamaModels: () => request<any>("/api/v1/ai-providers/ollama/models"),
  listInstalledLocalModels: () => request<any>("/api/v1/ai-providers/local-models/installed"),
  listOpenRouterModels: (limit = 1000) =>
    request<any>(`/api/v1/ai-providers/openrouter/models?limit=${encodeURIComponent(String(limit))}`),
  pullOllamaModel: (model: string) =>
    request<any>("/api/v1/brain/models/pull", {
      method: "POST",
      body: JSON.stringify({ model }),
    }),

  listRegisteredModels: (provider?: string, capability?: string) => {
    const params = new URLSearchParams();
    if (provider) params.set("provider", provider);
    if (capability) params.set("capability", capability);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ models: any[] }>(`/api/v1/model-registry/models${qs}`);
  },
  getModelRegistryStats: () => request<any>("/api/v1/model-registry/models/stats"),
  registerModel: (body: { model_id: string; provider: string; display_name: string; config_json?: string }) =>
    request<any>("/api/v1/model-registry/models", {
      method: "POST",
      body: JSON.stringify({
        model_id: body.model_id,
        provider: body.provider,
        display_name: body.display_name,
        config_json: body.config_json || "{}",
      }),
    }),
  updateRegisteredModel: (modelId: string, body: { provider?: string; display_name?: string; config_json?: string }) =>
    request<any>(`/api/v1/model-registry/models/${encodeURIComponent(modelId)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deregisterModel: (modelId: string) =>
    request<any>(`/api/v1/model-registry/models/${encodeURIComponent(modelId)}`, { method: "DELETE" }),
  addModelCapability: (modelId: string, capability: string, metadata?: Record<string, unknown>) =>
    request<any>("/api/v1/model-registry/capabilities", {
      method: "POST",
      body: JSON.stringify({
        model_id: modelId,
        capability,
        metadata_json: JSON.stringify(metadata || {}),
      }),
    }),
  configureModelBudgetLimit: (modelId: string, budgetLimit: number, provider?: string, fallbackModelId?: string) =>
    request<any>("/api/v1/monitoring/budget/configure", {
      method: "POST",
      body: JSON.stringify({
        model_id: modelId,
        budget_limit: budgetLimit,
        provider: provider || "",
        fallback_model_id: fallbackModelId || "",
      }),
    }),
  setModelBudgetFull: (modelId: string, dailyLimit: number, monthlyLimit: number, alertThresholdPct?: number) =>
    request<any>("/api/v1/model-budget/budgets", {
      method: "POST",
      body: JSON.stringify({
        model_id: modelId,
        daily_limit: dailyLimit,
        monthly_limit: monthlyLimit,
        alert_threshold_pct: alertThresholdPct ?? 80,
      }),
    }),

  // AI Workspace — Settings
  listAPIKeys: () => request<{ keys: any[] }>("/api/v1/workspace/settings/keys"),
  storeAPIKey: (provider: string, encryptedKey: string, displayName?: string, metadata?: Record<string, unknown>) =>
    request<{ entry_id: string }>("/api/v1/workspace/settings/keys", {
      method: "POST",
      body: JSON.stringify({ provider, encrypted_key: encryptedKey, display_name: displayName || "", metadata: metadata || null }),
    }),
  activateAPIKey: (keyId: string) =>
    request<{ entry_id: string }>(`/api/v1/workspace/settings/keys/${encodeURIComponent(keyId)}/activate`, { method: "POST" }),
  validateAPIKey: (keyId: string) =>
    request<{ key_id: string; valid: boolean; details?: any }>(`/api/v1/workspace/settings/keys/${encodeURIComponent(keyId)}/validate`, { method: "POST" }),
  listHierarchies: () => request<{ hierarchies: any[] }>("/api/v1/workspace/settings/hierarchies"),
  saveHierarchy: (name: string, levels: any[]) =>
    request<{ hierarchy_id: string }>("/api/v1/workspace/settings/hierarchies", {
      method: "POST",
      body: JSON.stringify({ name, levels }),
    }),
  listCouncilMemberConfigs: () => request<{ members: any[] }>("/api/v1/workspace/settings/council-members"),
  configureCouncilMember: (memberId: string, modelId: string, role: string, priority?: number, systemPrompt?: string, extra?: Record<string, unknown>) =>
    request<{ config_id: string }>("/api/v1/workspace/settings/council-members", {
      method: "POST",
      body: JSON.stringify({
        member_id: memberId,
        model_id: modelId,
        role,
        priority: priority || 0,
        system_prompt: systemPrompt || null,
        ...(extra || {}),
      }),
    }),

  // AI Workspace — Prompts
  listPromptTemplates: (category?: string) =>
    request<{ templates: any[] }>(`/api/v1/workspace/prompts${category ? `?category=${category}` : ""}`),
  createPromptTemplate: (name: string, category: string, content: string) =>
    request<{ template_id: string }>("/api/v1/workspace/prompts", {
      method: "POST",
      body: JSON.stringify({ name, category, content }),
    }),
  updatePromptTemplate: (templateId: string, content: string) =>
    request<any>(`/api/v1/workspace/prompts/${encodeURIComponent(templateId)}`, {
      method: "PUT",
      body: JSON.stringify({ name: "", category: "", content }),
    }),
  resolvePromptTemplate: (templateId: string, variables: Record<string, string>) =>
    request<{ resolved: string }>(`/api/v1/workspace/prompts/${encodeURIComponent(templateId)}/resolve`, {
      method: "POST",
      body: JSON.stringify(variables),
    }),

  // AI Workspace — Books
  createBook: (title: string, description?: string) =>
    request<{ book_id: string }>("/api/v1/workspace/books", {
      method: "POST",
      body: JSON.stringify({ title, description: description || "" }),
    }),
  generateBookFromChat: (bookId: string, sessionIds: string[]) =>
    request<{ book_id: string; chapter_count: number }>(`/api/v1/workspace/books/${encodeURIComponent(bookId)}/generate/chat`, {
      method: "POST",
      body: JSON.stringify({ session_ids: sessionIds }),
    }),
  generateBookFromCouncil: (bookId: string, councilSessionIds: string[]) =>
    request<{ book_id: string; chapter_count: number }>(`/api/v1/workspace/books/${encodeURIComponent(bookId)}/generate/council`, {
      method: "POST",
      body: JSON.stringify({ council_session_ids: councilSessionIds }),
    }),
  listBooks: (status?: string) =>
    request<{ books: any[] }>(`/api/v1/workspace/books${status ? `?status=${status}` : ""}`),
  getBook: (id: string) =>
    request<any>(`/api/v1/workspace/books/${encodeURIComponent(id)}`),
  exportBook: (id: string, format?: string) =>
    request<{ content: string }>(`/api/v1/workspace/books/${encodeURIComponent(id)}/export?format=${format || "markdown"}`),

  // Pipeline (for workspace right panel)
  submitPipelineRun: (idea: string) =>
    request<{ run_id: string; status: string }>("/api/v1/pipeline/ideas", {
      method: "POST",
      body: JSON.stringify({ idea }),
    }),
  listPipelineRuns: () =>
    request<{ runs: any[] }>("/api/v1/pipeline/runs"),
  getPipelineRun: (runId: string) =>
    request<any>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}`),
  executePipelineRun: (runId: string) =>
    request<any>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}/execute`, { method: "POST" }),
  cancelPipelineRun: (runId: string) =>
    request<any>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" }),
  getPipelineRunSteps: (runId: string) =>
    request<{ steps: any[] }>(`/api/v1/pipeline/runs/${encodeURIComponent(runId)}/steps`),

  // HumanGate
  createHumanGateSession: (title: string, description?: string) =>
    request<{ session_id: string; root_node_id: string }>("/api/v1/workspace/humangate/sessions", {
      method: "POST",
      body: JSON.stringify({ title, description: description || "" }),
    }),
  presentHumanGateDecision: (nodeId: string, context: string, choices: { label: string; description: string; consequences: string }[], phase?: string) =>
    request<{ node_id: string; choices: any[] }>(`/api/v1/workspace/humangate/nodes/${encodeURIComponent(nodeId)}/present`, {
      method: "POST",
      body: JSON.stringify({ context, choices, phase: phase || "" }),
    }),
  makeHumanGateChoice: (nodeId: string, choiceId: string) =>
    request<{ node_id: string; child_node_id: string }>(`/api/v1/workspace/humangate/nodes/${encodeURIComponent(nodeId)}/choose`, {
      method: "POST",
      body: JSON.stringify({ choice_id: choiceId }),
    }),
  undoHumanGateChoice: (sessionId: string) =>
    request<{ rolled_back_to_node_id: string }>(`/api/v1/workspace/humangate/sessions/${encodeURIComponent(sessionId)}/undo`, { method: "POST" }),
  rollbackHumanGateTo: (sessionId: string, nodeId: string) =>
    request<any>(`/api/v1/workspace/humangate/sessions/${encodeURIComponent(sessionId)}/rollback`, {
      method: "POST",
      body: JSON.stringify({ node_id: nodeId }),
    }),
  getHumanGateTree: (sessionId: string) =>
    request<{ nodes: any[]; edges: any[]; current_node_id: string }>(`/api/v1/workspace/humangate/sessions/${encodeURIComponent(sessionId)}/tree`),
  getHumanGateHistory: (sessionId: string) =>
    request<{ history: any[] }>(`/api/v1/workspace/humangate/sessions/${encodeURIComponent(sessionId)}/history`),
  getHumanGateCurrentDecision: (sessionId: string) =>
    request<any>(`/api/v1/workspace/humangate/sessions/${encodeURIComponent(sessionId)}/current`),
  listHumanGateSessions: () =>
    request<{ sessions: any[] }>("/api/v1/workspace/humangate/sessions"),

  // Idea Vault
  submitIdea: (content: string, category?: string, priority?: string | number, source?: string, tags?: string[]) =>
    request<{ idea_id: string }>("/api/v1/workspace/ideas", {
      method: "POST",
      body: JSON.stringify({
        content,
        category: category || "",
        priority: priority === undefined || priority === null || priority === "" ? "normal" : String(priority),
        source: source || "manual",
        tags: tags || [],
      }),
    }),
  listIdeas: (status?: string, category?: string, limit?: number) =>
    request<{ ideas: any[] }>(`/api/v1/workspace/ideas${status ? `?status=${status}` : ""}${category ? `&category=${category}` : ""}${limit ? `&limit=${limit}` : ""}`),
  getIdea: (ideaId: string) =>
    request<any>(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}`),
  updateIdea: (ideaId: string, data: { content?: string; category?: string; priority?: string | number; tags?: string[] }) =>
    request<any>(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}`, {
      method: "PUT",
      body: JSON.stringify({
        ...data,
        ...(data.priority !== undefined ? { priority: String(data.priority) } : {}),
      }),
    }),
  submitIdeaToPipeline: (ideaId: string) =>
    request<{ pipeline_run_id: string }>(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/submit-pipeline`, { method: "POST" }),
  deleteIdea: (ideaId: string) =>
    request<any>(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}`, { method: "DELETE" }),
  ideaStats: () =>
    request<any>("/api/v1/workspace/ideas/stats"),
  searchIdeas: (query: string) =>
    request<{ ideas: any[] }>(`/api/v1/workspace/ideas/search?q=${encodeURIComponent(query)}`),

  // Evidence Spine
  getSpineEntries: (fromSeq?: number, toSeq?: number, entryType?: string) => {
    const params = new URLSearchParams(
      Object.entries({ from_seq: fromSeq, to_seq: toSeq, entry_type: entryType })
        .filter(([_, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    );
    return request<{ entries: any[] }>(`/api/v1/governance/spine${params.toString() ? "?" + params.toString() : ""}`);
  },
  getSpineEntry: (entryId: string) =>
    request<{ entry: any }>(`/api/v1/governance/spine/${encodeURIComponent(entryId)}`),
  getSpineForDecision: (decisionId: string) =>
    request<{ entries: any[] }>(`/api/v1/governance/spine/decision/${encodeURIComponent(decisionId)}`),
  verifySpineChain: () =>
    request<{ valid: boolean; total_entries: number; tampered_count: number; broken_at: string | null }>("/api/v1/governance/spine/verify"),
  getSpineStats: () =>
    request<{ total_entries: number; chain_valid: boolean; last_hash: string; last_sequence: number }>("/api/v1/governance/spine/stats"),

  // Model Performance
  recordModelMetric: (data: { model_id: string; metric_type: string; value: number; unit: string; task_type?: string; session_id?: string; pipeline_run_id?: string; metadata?: Record<string, unknown> }) =>
    request<{ metric_id: string }>("/api/v1/monitoring/performance/record", { method: "POST", body: JSON.stringify(data) }),
  getModelMetrics: (params?: { model_id?: string; metric_type?: string; task_type?: string; from_time?: number; to_time?: number; limit?: number }) => {
    const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([_, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString() : "";
    return request<{ metrics: any[] }>(`/api/v1/monitoring/performance/metrics${qs}`);
  },
  getModelSummary: (modelId: string) =>
    request<{ summary: any }>(`/api/v1/monitoring/performance/summary/${encodeURIComponent(modelId)}`),
  getAllModelSummaries: () =>
    request<{ summaries: any[] }>("/api/v1/monitoring/performance/summaries"),
  getModelLeaderboard: (metricType?: string, taskType?: string) => {
    const params = new URLSearchParams();
    if (metricType) params.set("metric_type", metricType);
    if (taskType) params.set("task_type", taskType);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ leaderboard: any[] }>(`/api/v1/monitoring/performance/leaderboard${qs}`);
  },
  compareModels: (data: { model_ids: string[]; metric_type: string; from_time?: number; to_time?: number }) =>
    request<{ comparison: any }>("/api/v1/monitoring/performance/compare", { method: "POST", body: JSON.stringify(data) }),
  detectAnomalies: (modelId?: string, windowSeconds?: number) => {
    const params = new URLSearchParams();
    if (modelId) params.set("model_id", modelId);
    if (windowSeconds) params.set("window_seconds", String(windowSeconds));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ anomalies: any[] }>(`/api/v1/monitoring/performance/anomalies${qs}`);
  },
  getModelTrend: (modelId: string, metricType?: string, hours?: number) => {
    const params = new URLSearchParams();
    if (metricType) params.set("metric_type", metricType);
    if (hours) params.set("hours", String(hours));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ trend: any[] }>(`/api/v1/monitoring/performance/trend/${encodeURIComponent(modelId)}${qs}`);
  },

  // Decision Audit
  getDecisionAuditLog: (params?: { decision_id?: string; event_type?: string; severity?: string; from_time?: number; to_time?: number; limit?: number }) => {
    const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([_, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString() : "";
    return request<{ entries: any[] }>(`/api/v1/governance/audit/log${qs}`);
  },
  getAuditTimeline: (decisionId: string) =>
    request<{ timeline: any[] }>(`/api/v1/governance/audit/timeline/${encodeURIComponent(decisionId)}`),
  getAuditStats: () =>
    request<{ stats: any }>("/api/v1/governance/audit/stats"),

  // Notifications
  getNotificationUnreadCount: (userId: string) =>
    request<{ count: number }>(`/api/v1/workspace/notifications/${encodeURIComponent(userId)}/unread-count`),

  // Idea attachments
  uploadIdeaFile: (file: File, ideaId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (ideaId) form.append("idea_id", ideaId);
    return fetch(`${API_BASE}/api/v1/workspace/ideas/upload`, {
      method: "POST",
      body: form,
    }).then(r => r.json());
  },
  listIdeaAttachments: (ideaId: string) =>
    request<{ attachments: any[] }>(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/attachments`),
  analyzeIdeaAttachments: (ideaId: string) =>
    request<{ idea_id: string; analyses: any[] }>(`/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/attachments/analyze`, { method: "POST" }),
  deleteIdeaAttachment: (attachmentId: string) =>
    request<{ ok: boolean }>(`/api/v1/workspace/ideas/attachments/${encodeURIComponent(attachmentId)}`, { method: "DELETE" }),
  addProjectAttachment: (projectId: string, attachment: any, source = "project_council_question") =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/attachments`, {
      method: "POST",
      body: JSON.stringify({ attachment, source }),
    }),

  // Hallucination Detector
  listHallucinationChecks: (status?: string, sourceType?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (sourceType) params.set("source_type", sourceType);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ checks: any[] }>(`/api/v1/cognitive/hallucinations${qs}`);
  },
  getHallucinationCheck: (checkId: string) =>
    request<any>(`/api/v1/cognitive/hallucinations/${encodeURIComponent(checkId)}`),
  checkHallucinationClaim: (sourceType: string, sourceId: string, claim: string, expectedAnswer?: string) =>
    request<any>("/api/v1/cognitive/hallucinations", { method: "POST", body: JSON.stringify({ source_type: sourceType, source_id: sourceId, claim, expected_answer: expectedAnswer || "" }) }),
  verifyHallucinationCheck: (checkId: string, isHallucination: boolean, confidence: number, evidence?: string) =>
    request<any>(`/api/v1/cognitive/hallucinations/${encodeURIComponent(checkId)}/verify`, { method: "POST", body: JSON.stringify({ is_hallucination: isHallucination, confidence, evidence: evidence || "" }) }),
  getHallucinationStats: () =>
    request<{ stats: any }>("/api/v1/cognitive/hallucinations/stats"),

  // Code Snapshots
  listSnapshots: (moduleId?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (moduleId) params.set("module_id", moduleId);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ snapshots: any[] }>(`/api/v1/snapshots${qs}`);
  },
  getSnapshot: (snapshotId: string) =>
    request<any>(`/api/v1/snapshots/${encodeURIComponent(snapshotId)}`),
  createSnapshot: (moduleId: string, version: string, filePath: string, content: string, metadata?: any) =>
    request<any>("/api/v1/snapshots", { method: "POST", body: JSON.stringify({ module_id: moduleId, version, file_path: filePath, content, metadata }) }),
  diffSnapshots: (fromId: string, toId: string) =>
    request<any>(`/api/v1/snapshots/${encodeURIComponent(fromId)}/diff/${encodeURIComponent(toId)}`, { method: "POST" }),
  getLatestSnapshot: (moduleId: string) =>
    request<any>(`/api/v1/snapshots/latest/${encodeURIComponent(moduleId)}`),

  // Cascade Analyzer
  listCascadeAnalyses: (sourceModule?: string, riskLevel?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (sourceModule) params.set("source_module", sourceModule);
    if (riskLevel) params.set("risk_level", riskLevel);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ analyses: any[] }>(`/api/v1/governance/cascade/analyses${qs}`);
  },
  getCascadeAnalysis: (analysisId: string) =>
    request<any>(`/api/v1/governance/cascade/analyses/${encodeURIComponent(analysisId)}`),
  getCascadePaths: (analysisId: string) =>
    request<{ paths: any[] }>(`/api/v1/governance/cascade/analyses/${encodeURIComponent(analysisId)}/paths`),
  getCascadeStats: () =>
    request<{ stats: any }>("/api/v1/governance/cascade/stats"),

  // Conflict Detector
  listConflicts: (status?: string, moduleId?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (moduleId) params.set("module_id", moduleId);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ conflicts: any[] }>(`/api/v1/governance/conflict-detections${qs}`);
  },
  getConflict: (conflictId: string) =>
    request<any>(`/api/v1/governance/conflict-detections/${encodeURIComponent(conflictId)}`),
  getConflictStats: () =>
    request<{ stats: any }>("/api/v1/governance/conflict-detections/stats"),
  listConflictRules: () =>
    request<{ rules: any[] }>("/api/v1/governance/conflict-detections/rules"),

  // Compliance Checker
  listCompliancePolicies: (scope?: string, enabled?: boolean) => {
    const params = new URLSearchParams();
    if (scope) params.set("scope", scope);
    if (enabled !== undefined) params.set("enabled", String(enabled));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ policies: any[] }>(`/api/v1/governance/checker/policies${qs}`);
  },
  listComplianceChecks: (moduleId?: string, policyId?: string, status?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (moduleId) params.set("module_id", moduleId);
    if (policyId) params.set("policy_id", policyId);
    if (status) params.set("status", status);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ checks: any[] }>(`/api/v1/governance/checker/checks${qs}`);
  },
  getComplianceStats: () =>
    request<{ stats: any }>("/api/v1/governance/checker/stats"),

  // Session Manager
  listSecurityUsers: (role?: string) => {
    const params = new URLSearchParams();
    if (role) params.set("role", role);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ users: any[] }>(`/api/v1/security/session-manager/users${qs}`);
  },
  listSecuritySessions: (userId?: string) => {
    const params = new URLSearchParams();
    if (userId) params.set("user_id", userId);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ sessions: any[] }>(`/api/v1/security/session-manager/sessions${qs}`);
  },
  listAuditTrail: (userId?: string, action?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (userId) params.set("user_id", userId);
    if (action) params.set("action", action);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ events: any[] }>(`/api/v1/security/session-manager/audit${qs}`);
  },

  // Audit Trail
  listAuditEvents: (params?: { source?: string; module?: string; actor?: string; action?: string; event_type?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.source || params?.module) query.set("source", String(params.source || params.module));
    if (params?.actor) query.set("actor", String(params.actor));
    if (params?.action || params?.event_type) query.set("action", String(params.action || params.event_type));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<{ events: any[] }>(`/api/v1/audit/events${qs}`);
  },
  getAuditSummary: () =>
    request<any>("/api/v1/audit/summary"),
  getAuditIntegrity: () =>
    request<any>("/api/v1/audit/integrity"),
  exportAuditTrail: () =>
    request<any>("/api/v1/audit/export"),

  // Evidence Timeline
  listEvidenceTimelines: () =>
    request<{ timelines: any[] }>("/api/v1/evidence-timeline/timelines"),
  getEvidenceTimeline: (timelineId: string) =>
    request<any>(`/api/v1/evidence-timeline/timelines/${encodeURIComponent(timelineId)}`),
  createEvidenceTimeline: (data: Record<string, unknown>) =>
    request<any>("/api/v1/evidence-timeline/timelines", { method: "POST", body: JSON.stringify(data) }),
  verifyTimelineIntegrity: (timelineId: string) =>
    request<any>(`/api/v1/evidence-timeline/timelines/${encodeURIComponent(timelineId)}/verify`, { method: "POST" }),

  // Self-Healing
  listHealingRules: () =>
    request<{ rules: any[] }>("/api/v1/self-healing/rules"),
  getHealingStatus: (ruleId: string) =>
    request<any>(`/api/v1/self-healing/rules/${encodeURIComponent(ruleId)}/status`),
  createHealingRule: (data: Record<string, unknown>) =>
    request<any>("/api/v1/self-healing/rules", { method: "POST", body: JSON.stringify(data) }),
  listHealingActions: (limit?: number) =>
    request<any>("/api/v1/self-healing/sessions").then((data) => ({
      actions: Array.isArray(data.actions) ? data.actions : data.sessions ?? [],
    })),
  triggerHealing: (ruleId: string) =>
    request<any>(`/api/v1/self-healing/rules/${encodeURIComponent(ruleId)}/trigger`, { method: "POST" }),

  // Capacity Planning
  listCapacityResources: () =>
    request<any>("/api/v1/capacity/usage").then((data) => ({
      resources: Array.isArray(data.resources) ? data.resources : data.usage ?? [],
    })),
  getCapacityForecast: (resourceId: string) =>
    request<any>(`/api/v1/capacity/resources/${encodeURIComponent(resourceId)}/forecast`),
  registerCapacityResource: (data: Record<string, unknown>) =>
    request<any>("/api/v1/capacity/resources", { method: "POST", body: JSON.stringify(data) }),
  getCapacityRecommendations: () =>
    request<any>("/api/v1/capacity/bottlenecks").then((data) => ({
      recommendations: (Array.isArray(data.bottlenecks) ? data.bottlenecks : []).map(
        (item: Record<string, unknown>) => ({
          ...item,
          recommendation:
            "Zweryfikuj limit pojemnosci i zaplanuj zwiekszenie zasobu albo redukcje obciazenia.",
        }),
      ),
    })),

  // Risk Scoring
  listRiskScores: (moduleId?: string) =>
    request<{ scores: any[] }>("/api/v1/risk/scores"),
  getRiskAssessment: (targetId: string, targetType: string) =>
    request<any>(`/api/v1/risk/assessment/${encodeURIComponent(targetType)}/${encodeURIComponent(targetId)}`),

  // Change Proposals
  listChangeProposals: (status?: string) =>
    request<{ proposals: any[] }>("/api/v1/governance/proposals"),
  getChangeProposal: (proposalId: string) =>
    request<any>(`/api/v1/governance/proposals/${encodeURIComponent(proposalId)}`),
  createChangeProposal: (data: Record<string, unknown>) =>
    request<any>("/api/v1/governance/proposals", { method: "POST", body: JSON.stringify(data) }),

  // Anomaly Detection
  listAnomalies: (status?: string) =>
    request<{ anomalies: any[] }>("/api/v1/monitoring/anomalies"),
  getAnomalyBaseline: (metricName: string) =>
    request<any>(`/api/v1/monitoring/anomalies/baselines/${encodeURIComponent(metricName)}`),

  // SLA Monitor
  listSlaPolicies: () =>
    request<any>("/api/v1/monitoring/sla").then((data) => ({
      policies: Array.isArray(data.policies) ? data.policies : data.slas ?? [],
    })),
  getSlaCompliance: (policyId: string) =>
    request<any>(`/api/v1/monitoring/sla/policies/${encodeURIComponent(policyId)}/compliance`),

  // Config Drift
  listConfigDrifts: (status?: string) =>
    request<any>("/api/v1/monitoring/drift/reports").then((data) => ({
      drifts: Array.isArray(data.drifts) ? data.drifts : data.reports ?? [],
    })),
  getConfigDriftSnapshot: (snapshotId: string) =>
    request<any>(`/api/v1/monitoring/drift/snapshots/${encodeURIComponent(snapshotId)}`),

  // Metric Aggregation
  getMetricSummary: (metricName: string) =>
    request<any>(`/api/v1/monitoring/metrics/latest/${encodeURIComponent(metricName)}`),
  getMetricBuckets: (metricName: string, bucketSize?: string) =>
    request<any>(`/api/v1/monitoring/metrics/${encodeURIComponent(metricName)}/buckets`),

  // Contracts
  listContractsActive: (activeOnly?: boolean) =>
    request<any>(`/contracts?active_only=${activeOnly ?? ''}`),
  getContract: (contractId: string) =>
    request<any>(`/contracts/${encodeURIComponent(contractId)}`),
  registerContract: (data: Record<string, unknown>) =>
    request<any>('/contracts', { method: 'POST', body: JSON.stringify(data) }),
  bindContract: (data: Record<string, unknown>) =>
    request<any>('/contracts/bindings', { method: 'POST', body: JSON.stringify(data) }),

  // Bundles
  listBundles: (status?: string) =>
    request<any>(`/api/v1/bundles/list?status=${status ?? ''}`),
  getBundle: (bundleId: string) =>
    request<any>(`/bundles/${encodeURIComponent(bundleId)}`),
  createBundle: (data: Record<string, unknown>) =>
    request<any>('/bundles', { method: 'POST', body: JSON.stringify(data) }),
  deployBundle: (bundleId: string, targetEnv: string) =>
    request<any>(`/bundles/${encodeURIComponent(bundleId)}/deploy?target_env=${encodeURIComponent(targetEnv)}`, { method: 'POST' }),

  // Notifications
  listNotificationChannels: (type?: string) =>
    request<any>(`/api/v1/notifications/channels?type=${type ?? ''}`),
  listNotifications: (status?: string, limit?: number) =>
    request<any>(`/api/v1/notifications?status=${status ?? ''}&limit=${limit ?? 50}`),
  markNotificationRead: (notificationId: string) =>
    request<any>(`/api/v1/notifications/${encodeURIComponent(notificationId)}/read`, { method: 'POST' }),
  markNotificationUnread: (notificationId: string) =>
    request<any>(`/api/v1/notifications/${encodeURIComponent(notificationId)}/unread`, { method: 'POST' }),

  // Circuit Breakers
  listCircuitBreakers: (status?: string) =>
    request<any>(`/api/v1/circuit-breakers/list?status=${status ?? ''}`),
  getCircuitBreaker: (breakerId: string) =>
    request<any>(`/circuit-breakers/${encodeURIComponent(breakerId)}`),
  getBreakerState: (breakerId: string) =>
    request<any>(`/circuit-breakers/${encodeURIComponent(breakerId)}/state`),

  // Golden Sets (parameterized)
  listGoldenSetsByCategory: (category?: string) =>
    request<any>(`/api/v1/golden-sets/sets?category=${category ?? ''}`),
  getGoldenSet: (setId: string) =>
    request<any>(`/golden-sets/${encodeURIComponent(setId)}`),
  listGoldenRuns: (setId?: string) =>
    request<any>(`/golden-sets/runs?set_id=${setId ?? ''}`),

  // Governance Gates
  listGovernanceGates: (gateType?: string) =>
    request<any>(`/api/v1/gates/list?gate_type=${gateType ?? ''}`),
  listHumanGateRequests: (status?: string) =>
    request<any>(`/api/v1/gates/human/requests?status=${status ?? ''}`),
  submitHumanReview: (requestId: string, data: Record<string, unknown>) =>
    request<any>('/api/v1/gates/human/reviews', {
      method: 'POST',
      body: JSON.stringify({ request_id: requestId, ...data }),
    }),

  // Evidence Signing
  listSigningKeys: () =>
    request<any>('/security/evidence/keys'),
  listSignedEvidence: (evidenceId?: string) =>
    request<any>(`/security/evidence/signed?evidence_id=${evidenceId ?? ''}`),

  // Execution Guard
  listExecutionPolicies: (scope?: string) =>
    request<any>(`/execution-guard/policies?scope=${scope ?? ''}`),
  checkExecution: (data: Record<string, unknown>) =>
    request<any>('/execution-guard/check', { method: 'POST', body: JSON.stringify(data) }),

  // Roles
  listRoles: () =>
    request<any>('/api/v1/roles'),
  getUserRoles: (userId: string) =>
    request<any>(`/roles/users/${encodeURIComponent(userId)}/roles`),
  checkPermission: (userId: string, permission: string) =>
    request<any>('/roles/check-permission', { method: 'POST', body: JSON.stringify({ user_id: userId, permission }) }),

  // Decision Boundaries
  listDecisionBoundaries: (scope?: string) =>
    request<any>(`/decision-boundaries/boundaries?scope=${scope ?? ''}`),

  // Decision Snapshots (by decision ID)
  listDecisionSnapshotsByDecision: (decisionId?: string) =>
    request<any>(`/decision-snapshots?decision_id=${decisionId ?? ''}`),

  // Self-Explanation
  listExplanationTemplates: (scope?: string) =>
    request<any>(`/self-explanation/templates?scope=${scope ?? ''}`),

  // Phantom Sessions
  listPhantomSessions: (userId?: string) =>
    request<any>(`/phantom/sessions?user_id=${userId ?? ''}`),

  // Hardened Audit
  getHardenedAuditEvents: (eventType?: string, actor?: string) =>
    request<any>(`/api/v1/hardened-audit/events?event_type=${eventType ?? ''}&actor=${actor ?? ''}`),
  verifyAuditChain: () =>
    request<any>('/api/v1/hardened-audit/chain/verify', { method: 'POST' }),
  tamperCheck: () =>
    request<any>('/api/v1/hardened-audit/chain/tamper-check', { method: 'POST' }),

  // Evaluator
  listEvaluationCriteria: () =>
    request<any>('/evaluator/criteria'),
  listEvaluatorEvaluations: (status?: string) =>
    request<any>(`/evaluator/evaluations?status=${status ?? ''}`),
  getEvaluationSummary: (evaluationId: string) =>
    request<any>(`/evaluator/evaluations/${encodeURIComponent(evaluationId)}/summary`),

  // Model Budget
  listModelBudgetEntries: () =>
    request<any>('/model-budget/budgets'),
  checkModelBudget: (modelId: string) =>
    request<any>(`/model-budget/check?model_id=${encodeURIComponent(modelId)}`),
  getBudgetSummary: () =>
    request<any>('/model-budget/summary'),
  listBudgetAlerts: (modelId?: string) =>
    request<any>(`/model-budget/alerts?model_id=${modelId ?? ''}`),

  // Integrations
  listIntegrations: (type?: string) =>
    request<any>(`/api/v1/integrations?type=${type ?? ''}`).then((data) => (
      Array.isArray(data) ? { integrations: data } : data
    )),
  getIntegrationHealth: (integrationId: string) =>
    request<any>(`/integrations/${encodeURIComponent(integrationId)}/health`),

  // Connectors
  listConnectors: (type?: string) =>
    request<any>(`/api/v1/connectors/list?type=${type ?? ''}`),
  getConnector: (connectorId: string) =>
    request<any>(`/connectors/${encodeURIComponent(connectorId)}`),
  getConnectorHealth: (connectorId: string) =>
    request<any>(`/connectors/${encodeURIComponent(connectorId)}/health`),
  // FE-9.2 / FE-9.4 — cloud connector registration UI (BE-8 endpoints under /cloud-connectors)
  // BE-8 created /api/v1/cloud-connectors (not /connectors which is legacy connector_routes)
  registerConnector: (body: { provider: string; name: string; scope: string; credentials: Record<string, unknown> }) =>
    request<any>('/api/v1/cloud-connectors', { method: 'POST', body: JSON.stringify(body) }),
  listCloudConnectors: () =>
    request<any>('/api/v1/cloud-connectors'),
  deleteConnector: (connectorId: string) =>
    request<any>(`/api/v1/cloud-connectors/${encodeURIComponent(connectorId)}`, { method: 'DELETE' }),
  testConnector: (connectorId: string) =>
    request<any>(`/api/v1/cloud-connectors/${encodeURIComponent(connectorId)}/test`, { method: 'POST' }),
  listCloudConnectorProviders: () =>
    request<any>('/api/v1/cloud-connectors/providers'),

  // Projects (FE-9.3 — list for per-project worker view)
  listProjects: (status?: string) =>
    request<any>(`/api/v1/projects${status ? `?status=${encodeURIComponent(status)}` : ''}`),

  // Adapters
  listAdapters: (protocol?: string) =>
    request<any>(`/adapters?protocol=${protocol ?? ''}`),

  // Secrets
  listSecrets: (scope?: string) =>
    request<any>(`/api/v1/secrets/list?scope=${scope ?? ''}`),
  getSecret: (name: string) =>
    request<any>(`/api/v1/secrets/${encodeURIComponent(name)}`),
  // FE-9.1 — create secret (BE-8 endpoint at /secrets/create operator-friendly body)
  createSecret: (body: { name: string; scope: string; value: string }) =>
    request<any>('/api/v1/secrets/create', { method: 'POST', body: JSON.stringify(body) }),

  // Security Profiles
  listSecurityProfilesByLevel: (level?: string) =>
    request<any>(`/security-profiles?level=${level ?? ''}`),

  // Security Audit
  listSecurityFindings: (severity?: string, status?: string) =>
    request<any>(`/api/v1/security-audit/findings/list?severity=${severity ?? ''}&status=${status ?? ''}`),
  listSecurityScans: (status?: string) =>
    request<any>(`/api/v1/security-audit/scans/list?status=${status ?? ''}`),

  // Auth
  listAuthProviders: (type?: string) =>
    request<any>(`/api/v1/auth/providers/list?type=${type ?? ''}`),
  listAuthSessions: (userId?: string) =>
    request<any>(`/api/v1/auth/sessions/list?user_id=${userId ?? ''}`),

  // Bootstrap
  listBootstrapFlows: (status?: string) =>
    request<any>(`/bootstrap?status=${status ?? ''}`),

  // Profile Swaps
  listProfileSwaps: (status?: string) =>
    request<any>(`/profile-swaps?status=${status ?? ''}`),

  // Worker fleet and autoscaler
  listWorkers: () => request<any>("/api/v1/workers"),
  registerWorker: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workers", { method: "POST", body: JSON.stringify(body) }),
  heartbeatWorker: (workerId: string) =>
    request<any>(`/api/v1/workers/${encodeURIComponent(workerId)}/heartbeat`, { method: "POST" }),
  deleteWorker: (workerId: string) =>
    request<any>(`/api/v1/workers/${encodeURIComponent(workerId)}`, { method: "DELETE" }),
  rebalanceAssignments: () =>
    request<any>("/api/v1/workers/assignments/rebalance", { method: "POST" }),
  listWorkerTopologies: () => request<any>("/api/v1/workers/topology/all"),
  getAutoscalerStatus: () => request<any>("/api/v1/workers/autoscaler/status"),
  getAutoscalerHistory: (limit?: number) =>
    request<any>(`/api/v1/workers/autoscaler/history${limit ? `?limit=${limit}` : ""}`),
  getAutoscalerPolicy: () => request<any>("/api/v1/workers/autoscaler/policy"),
  updateAutoscalerPolicy: (body: Record<string, unknown>) =>
    request<any>("/api/v1/workers/autoscaler/policy", { method: "POST", body: JSON.stringify(body) }),
  evaluateAutoscaler: () =>
    request<any>("/api/v1/workers/autoscaler/evaluate", { method: "POST" }),
  executeAutoscaler: (decision?: string) =>
    request<any>("/api/v1/workers/autoscaler/execute", {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),

  // Build, deploy, event backbone, and observability surfaces
  getBuildState: () => request<any>("/api/v1/build-state"),
  listCandidateBuilds: () => request<any>("/api/v1/integration/builds"),
  createCandidateBuild: (body: Record<string, unknown>) =>
    request<any>("/api/v1/integration/builds", { method: "POST", body: JSON.stringify(body) }),
  validateCandidateBuild: (buildId: string) =>
    request<any>(`/api/v1/integration/builds/${encodeURIComponent(buildId)}/validate`, { method: "POST" }),
  promoteCandidateBuild: (buildId: string) =>
    request<any>(`/api/v1/integration/builds/${encodeURIComponent(buildId)}/promote`, { method: "POST" }),
  rejectCandidateBuild: (buildId: string, body?: Record<string, unknown>) =>
    request<any>(`/api/v1/integration/builds/${encodeURIComponent(buildId)}/reject`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  listDrifts: () => request<any>("/api/v1/integration/drift"),
  getDriftSummary: () => request<any>("/api/v1/integration/drift/summary"),
  detectDrift: () => request<any>("/api/v1/integration/drift/detect", { method: "POST" }),
  getDeploySummary: () => request<any>("/api/v1/deploy/summary"),
  getDeployTopologies: () => request<any>("/api/v1/deploy/topologies"),
  generateDeployTopology: (variant: string) =>
    request<any>(`/api/v1/deploy/topologies/${encodeURIComponent(variant)}`, { method: "POST" }),
  listHetznerDeployments: (projectId?: string) =>
    request<any>(`/api/v1/deploy/hetzner/deployments${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
  provisionHetznerProject: (body: Record<string, unknown>) =>
    request<any>("/api/v1/deploy/hetzner/provision", { method: "POST", body: JSON.stringify(body) }),
  checkHetznerDeploymentHealth: (deploymentId: string) =>
    request<any>(`/api/v1/deploy/hetzner/${encodeURIComponent(deploymentId)}/health`, { method: "POST" }),
  deleteHetznerDeployment: (deploymentId: string, confirmDelete: boolean) =>
    request<any>(`/api/v1/deploy/hetzner/${encodeURIComponent(deploymentId)}/delete`, {
      method: "POST",
      body: JSON.stringify({ confirm_delete: confirmDelete }),
    }),
  getBackboneHealth: () => request<any>("/api/v1/event-backbone/health"),
  getBackboneCatalog: () => request<any>("/api/v1/event-backbone/catalog"),
  listBackboneEvents: (limit?: number) =>
    request<any>(`/api/v1/event-backbone/events${limit ? `?limit=${limit}` : ""}`),
  getObservabilitySnapshot: () => request<any>("/api/v1/observability/snapshot"),
  listObservabilityLogs: (service?: string, level?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (service) params.set("service", service);
    if (level) params.set("level", level);
    if (limit) params.set("limit", String(limit));
    return request<any>(`/api/v1/observability/logs${params.toString() ? `?${params}` : ""}`);
  },
  listObservabilityMetrics: () => request<any>("/api/v1/observability/metrics"),
  listObservabilityTraces: (service?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (service) params.set("service", service);
    if (limit) params.set("limit", String(limit));
    return request<any>(`/api/v1/observability/traces${params.toString() ? `?${params}` : ""}`);
  },

  // Funding Autopilot
  getFundingCompanyProfile: (companyId?: string) => request<any>(`/api/v1/funding/company-profile${fundingCompanyQuery(companyId)}`),
  saveFundingCompanyProfile: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/company-profile", { method: "PUT", body: JSON.stringify(body) }),
  getFundingCompanyReadiness: (companyId?: string) => request<any>(`/api/v1/funding/company-profile/readiness${fundingCompanyQuery(companyId)}`),
  listFundingCompanyDocuments: (companyId?: string) => request<any>(`/api/v1/funding/company-profile/documents${fundingCompanyQuery(companyId)}`),
  addFundingCompanyDocument: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/company-profile/documents", { method: "POST", body: JSON.stringify(body) }),
  getFundingStateAid: (companyId?: string) => request<any>(`/api/v1/funding/company-profile/state-aid${fundingCompanyQuery(companyId)}`),
  getFundingCompanyRegistrySync: (companyId?: string) => request<any>(`/api/v1/funding/company-profile/registry-sync${fundingCompanyQuery(companyId)}`),
  syncFundingCompanyRegistry: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/company-profile/registry-sync", { method: "POST", body: JSON.stringify(body) }),
  listFundingSources: () => request<any>("/api/v1/funding/sources"),
  listFundingProgrammes: () => request<any>("/api/v1/funding/programmes"),
  createFundingProgramme: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/programmes", { method: "POST", body: JSON.stringify(body) }),
  listFundingCalls: () => request<any>("/api/v1/funding/calls"),
  createFundingCall: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/calls", { method: "POST", body: JSON.stringify(body) }),
  triggerFundingScan: (params?: { force_refresh?: boolean; since_days?: number }) =>
    request<any>(
      `/api/v1/funding/scan/trigger?force_refresh=${encodeURIComponent(String(params?.force_refresh ?? false))}&since_days=${encodeURIComponent(String(params?.since_days ?? 30))}`,
      { method: "POST" }
    ),
  searchFundingCalls: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/calls/search", { method: "POST", body: JSON.stringify(body) }),
  getFundingCall: (callId: string) =>
    request<any>(`/api/v1/funding/calls/${encodeURIComponent(callId)}`),
  listFundingIdeas: (companyId?: string) => request<any>(`/api/v1/funding/ideas${fundingCompanyQuery(companyId)}`),
  getFundingIdea: (ideaId: string) =>
    request<any>(`/api/v1/funding/ideas/${encodeURIComponent(ideaId)}`),
  generateFundingIdeas: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/ideas/generate", { method: "POST", body: JSON.stringify(body) }),
  convertFundingIdeaToProject: (ideaId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/funding/ideas/${encodeURIComponent(ideaId)}/convert-to-project`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listFundingProjects: (companyId?: string) => request<any>(`/api/v1/funding/projects${fundingCompanyQuery(companyId)}`),
  getFundingMatchingResults: (projectId: string) =>
    request<any>(`/api/v1/funding/matching/results/${encodeURIComponent(projectId)}`),
  runFundingMatching: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/matching/run", { method: "POST", body: JSON.stringify(body) }),
  getFundingScoring: (projectId: string) =>
    request<any>(`/api/v1/funding/scoring/${encodeURIComponent(projectId)}`),
  analyzeFundingConsortium: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/analyze", { method: "POST", body: JSON.stringify(body) }),
  searchFundingPartners: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/partners/search", { method: "POST", body: JSON.stringify(body) }),
  shortlistFundingPartners: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/partners/shortlist", { method: "POST", body: JSON.stringify(body) }),
  generateFundingOutreach: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/consortium/outreach/generate", { method: "POST", body: JSON.stringify(body) }),
  createFundingApplication: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/application/create", { method: "POST", body: JSON.stringify(body) }),
  getFundingApplication: (applicationId: string) =>
    request<any>(`/api/v1/funding/application/${encodeURIComponent(applicationId)}`),
  getFundingApplicationDocuments: (applicationId: string) =>
    request<any>(`/api/v1/funding/application/${encodeURIComponent(applicationId)}/documents`),
  reviewFundingApplication: (applicationId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/funding/application/${encodeURIComponent(applicationId)}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportFundingApplication: (applicationId: string) =>
    request<any>(`/api/v1/funding/application/${encodeURIComponent(applicationId)}/export`, { method: "POST" }),
  fundingApplicationExportUrl: (applicationId: string, artifactType: string) =>
    `${API_BASE}/api/v1/funding/application/${encodeURIComponent(applicationId)}/export/${encodeURIComponent(artifactType)}`,
  listFundingCrmApplications: (companyId?: string) => request<any>(`/api/v1/funding/crm/applications${fundingCompanyQuery(companyId)}`),
  listFundingDeadlines: (companyId?: string) => request<any>(`/api/v1/funding/deadlines${fundingCompanyQuery(companyId)}`),
  listFundingAlerts: (companyId?: string) => request<any>(`/api/v1/funding/alerts${fundingCompanyQuery(companyId)}`),
  getFundingExecutiveReport: (companyId?: string) => request<any>(`/api/v1/funding/reports/executive${fundingCompanyQuery(companyId)}`),
  prepareFundingSubmission: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/submission/prepare", { method: "POST", body: JSON.stringify(body) }),
  fillFundingSubmission: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/submission/fill", { method: "POST", body: JSON.stringify(body) }),
  saveFundingSubmissionDraft: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/submission/save-draft", { method: "POST", body: JSON.stringify(body) }),
  requestFundingSubmissionApproval: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/submission/request-approval", { method: "POST", body: JSON.stringify(body) }),
  submitFundingApplication: (body: Record<string, unknown>) =>
    request<any>("/api/v1/funding/submission/submit", { method: "POST", body: JSON.stringify(body) }),
  listFundingSubmissionSessions: (applicationId?: string) =>
    request<any>(`/api/v1/funding/submission/sessions${applicationId ? `?application_id=${encodeURIComponent(applicationId)}` : ""}`),
  listFundingSubmissionApprovals: (applicationId?: string) =>
    request<any>(`/api/v1/funding/submission/approvals${applicationId ? `?application_id=${encodeURIComponent(applicationId)}` : ""}`),
  getFundingSubmissionReceipt: (sessionId?: string) =>
    request<any>(`/api/v1/funding/submission/receipt${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`),

  // Project detail canonical flow
  getProjectDetail: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}`),
  getProjectTimeline: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/timeline`),
  listProjectQuestionsCanonical: (projectId: string, status?: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/questions${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  answerProjectQuestion: (
    projectId: string,
    questionId: string,
    body: { choice_id?: string; custom_response?: string; rationale?: string; source?: string },
  ) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/questions/${encodeURIComponent(questionId)}/answer`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProjectCanon: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/canon`),
  getProjectMasterplan: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/masterplan`),
  // FE-2 (round_meta): freeze Canon (Source of Truth) — calls BE-1
  freezeProjectCanon: (
    projectId: string,
    body: { reason: string; evidence_pack_id?: string },
  ) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/canon/freeze`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // FE-3 (round_meta): freeze Masterplan (Round 2 -> Round 3 gate) — calls BE-2
  freezeProjectMasterplan: (projectId: string, body: { reason: string }) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/masterplan/freeze`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  authorizeProjectBuild: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/build/authorize`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProjectModules: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/modules`),
  getProjectAudit: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/audit`),
  getProjectCost: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/cost`),
  launchProject: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/launch`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  projectArtifactUrl: (projectId: string) =>
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/artifact/raw`,

  // F-030: per-project meta-orchestration (rada, budzet, autonomia, modele)
  getProjectCouncil: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/council`),
  getProjectCouncilSuggest: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/council/suggest`),
  updateProjectCouncil: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/council`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  getProjectBudget: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/budget`),
  getProjectAutonomy: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/autonomy`),
  updateProjectAutonomy: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/autonomy`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  updateProjectBudget: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/budget`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  getProjectExecutionModels: (projectId: string) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/execution-models`),
  updateProjectExecutionModels: (projectId: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/execution-models`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  // Phase 2 D-INTEGRATE: Operator Mobile (B5)
  mobileBindDevice: (operator_id: string, device_label: string) =>
    request<any>(`/api/v1/mobile/devices/bind`, {
      method: "POST",
      body: JSON.stringify({ operator_id, device_label }),
    }),
  mobileListDevices: (operator_id?: string) =>
    request<any>(`/api/v1/mobile/devices${operator_id ? `?operator_id=${encodeURIComponent(operator_id)}` : ""}`),
  mobileUnbindDevice: (device_id: string) =>
    request<any>(`/api/v1/mobile/devices/${encodeURIComponent(device_id)}`, { method: "DELETE" }),
  mobileQueueList: (operator_id?: string) =>
    request<any>(`/api/v1/mobile/queue${operator_id ? `?operator_id=${encodeURIComponent(operator_id)}` : ""}`),
  mobileQueueDetail: (ticket_id: string) =>
    request<any>(`/api/v1/mobile/queue/${encodeURIComponent(ticket_id)}`),
  mobileApprove: (ticket_id: string, operator_id: string, comment?: string) =>
    request<any>(`/api/v1/mobile/queue/${encodeURIComponent(ticket_id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ operator_id, comment }),
    }),
  mobileReject: (ticket_id: string, operator_id: string, comment?: string) =>
    request<any>(`/api/v1/mobile/queue/${encodeURIComponent(ticket_id)}/reject`, {
      method: "POST",
      body: JSON.stringify({ operator_id, comment }),
    }),

  // Phase 2 D-INTEGRATE: Governance unified tickets (A1)
  governanceTicketsList: (origin?: string, state?: string) => {
    const params = new URLSearchParams();
    if (origin) params.set("origin", origin);
    if (state) params.set("state", state);
    return request<any>(`/api/v1/governance/tickets${params.toString() ? "?" + params : ""}`);
  },
  governanceTicketGet: (ticket_id: string) =>
    request<any>(`/api/v1/governance/tickets/${encodeURIComponent(ticket_id)}`),
  governanceTicketSubmit: (body: Record<string, unknown>) => {
    if (body.kind === "round2_meta_approval" && typeof body.project_id === "string") {
      return request<any>(`/api/v1/projects/${encodeURIComponent(body.project_id)}/masterplan/freeze`, {
        method: "POST",
        body: JSON.stringify({
          reason: String(body.reason || body.summary || "Operator zatwierdza Runde 2."),
          evidence_pack_id: String(body.evidence_pack_id || ""),
        }),
      });
    }
    return request<any>(`/api/v1/governance/tickets`, { method: "POST", body: JSON.stringify(body) });
  },
  governanceTicketResolve: (ticket_id: string, decision: string, actor: string, comment?: string) =>
    request<any>(`/api/v1/governance/tickets/${encodeURIComponent(ticket_id)}/resolve`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer: actor, reason: comment || "" }),
    }),

  // Phase 2 D-INTEGRATE: Council semantics (A3)
  councilState: (project_id: string) =>
    request<any>(`/api/v1/council/${encodeURIComponent(project_id)}/state`),
  councilReconcile: (project_id: string) =>
    request<any>(`/api/v1/council/${encodeURIComponent(project_id)}/reconcile`, { method: "POST" }),
  councilEnable: (project_id: string, enabled: boolean) =>
    request<any>(`/api/v1/council/${encodeURIComponent(project_id)}/enable`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  councilDeliberate: (project_id: string, body: Record<string, unknown>) =>
    request<any>(`/api/v1/council/${encodeURIComponent(project_id)}/deliberate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Agent Runtime
  listRuntimeAgents: (status?: string, agentType?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (agentType) params.set("agent_type", agentType);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ agents: any[] }>(`/api/v1/agents/list${qs}`);
  },
  getAgentRuntimeStats: () =>
    request<any>("/api/v1/agents/stats"),
  listAgentExecutions: (agentId?: string, status?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (agentId) params.set("agent_id", agentId);
    if (status) params.set("status", status);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<{ executions: any[] }>(`/api/v1/agents/executions${qs}`);
  },
  registerRuntimeAgent: (body: {
    name: string;
    agent_type?: string;
    provider?: string;
    model_id?: string;
    system_prompt?: string;
    max_tokens?: number;
    temperature?: number;
    tools?: string;
    capabilities?: string;
  }) => {
    const params = new URLSearchParams();
    Object.entries(body).forEach(([key, value]) => {
      if (value !== undefined && value !== null) params.set(key, String(value));
    });
    return request<any>(`/api/v1/agents/register?${params.toString()}`, { method: "POST" });
  },
  updateRuntimeAgent: (agentId: string, body: {
    name?: string;
    agent_type?: string;
    provider?: string;
    model_id?: string;
    system_prompt?: string;
    max_tokens?: number;
    temperature?: number;
    tools?: string;
    capabilities?: string;
    status?: string;
  }) => {
    const params = new URLSearchParams();
    Object.entries(body).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    });
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<any>(`/api/v1/agents/${encodeURIComponent(agentId)}${qs}`, { method: "PUT" });
  },
  executeRuntimeAgent: (agentId: string, body: { task: string; context?: string }) => {
    const params = new URLSearchParams();
    params.set("task", body.task);
    if (body.context) params.set("context", body.context);
    return request<any>(`/api/v1/agents/${encodeURIComponent(agentId)}/execute?${params.toString()}`, { method: "POST" });
  },
  deleteRuntimeAgent: (agentId: string) =>
    request<any>(`/api/v1/agents/${encodeURIComponent(agentId)}`, { method: "DELETE" }),

  // Phase 2 D-INTEGRATE: Autonomy stage machine (A5)
  autonomyState: (project_id: string) =>
    request<any>(`/api/v1/autonomy/${encodeURIComponent(project_id)}/state`),
  autonomyAdvance: (project_id: string, decision_class?: string) =>
    request<any>(`/api/v1/autonomy/${encodeURIComponent(project_id)}/advance`, {
      method: "POST",
      body: JSON.stringify({ decision_class }),
    }),
  autonomySteer: (project_id: string, target_phase: string, decision_class?: string) =>
    request<any>(`/api/v1/autonomy/${encodeURIComponent(project_id)}/steer`, {
      method: "POST",
      body: JSON.stringify({ target_phase, decision_class }),
    }),
  autonomyEvent: (project_id: string, event_type?: string) =>
    request<any>(`/api/v1/autonomy/${encodeURIComponent(project_id)}/event`, {
      method: "POST",
      body: JSON.stringify({ event_type }),
    }),
  autonomyTransitions: (project_id: string, limit?: number) =>
    request<any>(`/api/v1/autonomy/${encodeURIComponent(project_id)}/transitions${limit ? `?limit=${limit}` : ""}`),

  // Phase 2 D-INTEGRATE: Prometheus metrics (K3)
  metrics: () => fetch(`${API_BASE}/api/v1/metrics`).then((r) => r.text()),

  // Phase 2 D-INTEGRATE: Skills runtime (B1)
  skillsRuntimeList: () => request<{ skills: any[] }>(`/api/v1/skills`),
  skillsRuntimeState: (skill_id: string) =>
    request<any>(`/api/v1/skills/${encodeURIComponent(skill_id)}/state`),
  skillsRuntimeExecute: (skill_id: string, context: Record<string, unknown>) =>
    request<any>(`/api/v1/skills/${encodeURIComponent(skill_id)}/execute`, {
      method: "POST",
      body: JSON.stringify(context),
    }),

  // Phase 2 D-INTEGRATE: Memory shared plane (B3-B4)
  memoryEvidenceStats: () => request<any>(`/api/v1/memory/evidence/stats`),
  memorySearchSimilar: (query: string, limit?: number) =>
    request<any>(`/api/v1/memory/index/search?query=${encodeURIComponent(query)}${limit ? `&limit=${limit}` : ""}`),

  // ===========================================================
  // SYLION AEIS v2 — Phase 0
  // ===========================================================

  // AEIS Architecture Layers W1-W19
  getArchitectureLayers: () => request<any>("/api/v1/architecture-layers"),
  getArchitectureLayer: (id: string) =>
    request<any>(`/api/v1/architecture-layers/${encodeURIComponent(id)}`),

  // W15: Ontology Browser
  listOntologyTypes: () => request<any>("/api/v1/ontology/types"),
  getOntologyType: (id: string) =>
    request<any>(`/api/v1/ontology/types/${encodeURIComponent(id)}`),
  getOntologyDdl: (id: string) =>
    request<any>(`/api/v1/ontology/types/${encodeURIComponent(id)}/ddl`),
  getOntologyActions: (id: string) =>
    request<any>(`/api/v1/ontology/types/${encodeURIComponent(id)}/actions`),
  reloadOntology: () =>
    request<any>("/api/v1/ontology/reload", { method: "POST" }),

  // W18: Operator Terminal
  listTerminalSessions: () => request<any>("/api/v1/terminal/sessions"),
  createTerminalSession: (title: string) =>
    request<any>("/api/v1/terminal/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  execTerminalCommand: (line: string, ctx?: Record<string, unknown>) =>
    request<any>("/api/v1/terminal/exec", {
      method: "POST",
      body: JSON.stringify({ line, ctx: ctx ?? null }),
    }),

  // W7: Role Catalog
  listRoleCatalog: () => request<any>("/api/v1/role-catalog"),
  getRole: (id: string) =>
    request<any>(`/api/v1/role-catalog/${encodeURIComponent(id)}`),

  // W13: Pipeline suggester (advisor)
  suggestPipeline: (task: string, available?: string[] | null) =>
    request<any>("/api/v1/advisor/suggest-pipeline", {
      method: "POST",
      body: JSON.stringify({ task, available_models: available ?? null }),
    }),

  // W17: Compute Provider Federation
  listFederationNodes: () =>
    request<{ count: number; nodes: any[] }>("/api/v1/federation/nodes"),
  listFederationActiveNodes: (staleSecs?: number) =>
    request<{ count: number; stale_secs?: number; nodes: any[] }>(
      `/api/v1/federation/nodes/active${staleSecs !== undefined ? `?stale_secs=${staleSecs}` : ""}`,
    ),
  getFederationHealth: () => request<any>("/api/v1/federation/health"),
  routeFederation: (
    model_id: string,
    privacy_level: string,
    max_cost_per_1k?: number | null,
  ) =>
    request<any>("/api/v1/federation/route", {
      method: "POST",
      body: JSON.stringify({
        model_id,
        privacy_level,
        max_cost_per_1k: max_cost_per_1k ?? null,
      }),
    }),
};

// Helper: build absolute URL for API base (used for native EventSource).
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "";
