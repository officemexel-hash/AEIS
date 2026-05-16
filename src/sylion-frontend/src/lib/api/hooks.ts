"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { api } from "./client";

let _backendReachable: boolean | null = null;
let _lastBackendCheck = 0;
const BACKEND_CHECK_INTERVAL = 3000;
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const HEALTH_URL = API_BASE ? `${API_BASE}/health` : "/api/v1/health";

async function isBackendReachable(): Promise<boolean> {
  const now = Date.now();
  if (_backendReachable !== null && now - _lastBackendCheck < BACKEND_CHECK_INTERVAL) {
    return _backendReachable;
  }
  try {
    const res = await fetch(HEALTH_URL, {
      signal: AbortSignal.timeout(3000),
      cache: "no-store",
    });
    _backendReachable = res.ok;
    _lastBackendCheck = now;
    return _backendReachable;
  } catch {
    _backendReachable = false;
    _lastBackendCheck = now;
    return false;
  }
}

export function useApi<T>(fetcher: () => Promise<T>, fallback: T, refreshMs?: number) {
  const [data, setData] = useState<T>(fallback);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const doFetch = useCallback(() => {
    if (!mountedRef.current) return;
    isBackendReachable().then((reachable) => {
      if (!reachable || !mountedRef.current) {
        setLoading(false);
        return;
      }
      fetcher()
        .then((d) => { if (mountedRef.current) { setData(d); setError(null); } })
        .catch(() => {})
        .finally(() => { if (mountedRef.current) setLoading(false); });
    });
  }, []);

  const refresh = useCallback(() => {
    isBackendReachable().then((reachable) => {
      if (!reachable || !mountedRef.current) return;
      fetcher()
        .then((d) => { if (mountedRef.current) { setData(d); setError(null); } })
        .catch(() => {});
    });
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    let interval: ReturnType<typeof setInterval> | null = null;

    doFetch();

    if (refreshMs) {
      interval = setInterval(() => {
        if (!mountedRef.current) return;
        isBackendReachable().then((ok) => {
          if (!ok || !mountedRef.current) return;
          fetcher()
            .then((d) => { if (mountedRef.current) setData(d); })
            .catch(() => {});
        });
      }, refreshMs);
    }

    return () => {
      mountedRef.current = false;
      if (interval) clearInterval(interval);
    };
  }, [refreshMs]);

  return { data, loading, error, refresh };
}

// System
export const useHealth = () => useApi(() => api.health(), { status: "unknown", version: "", modules: 0, endpoints: 0, db_mode: "" }, 5000);

// Core
export const useModules = () => useApi(() => api.listModules(), { modules: [] });
export const usePlans = () => useApi(() => api.listPlans(), { plans: [] });
export const useProjects = () => useApi(() => api.listProjects(), { projects: [] }, 10000);
export const useEvents = () => useApi(() => api.listEvents(), { events: [] }, 10000);
export const useContracts = () => useApi(() => api.listContracts(), { contracts: [] });
export const useEvidence = () => useApi(() => api.listEvidence(), { entries: [] });

// Governance
export const useProposals = () => useApi(() => api.listProposals(), { proposals: [] });
export const useGates = () => useApi(() => api.listGates(), { gates: [] });
export const usePolicies = () => useApi(() => api.listPolicies(), { policies: [] });

// Cognitive
export const useModels = () => useApi(() => api.listModels(), { models: [] });
export const useEvaluations = () => useApi(() => api.listEvaluations(), { evaluations: [] });

// Execution
export const useTools = () => useApi(() => api.listTools(), { tools: [] });
export const useWorkflows = () => useApi(() => api.listWorkflows(), { workflows: [] });
export const useJobs = () => useApi(() => api.listJobs(), { jobs: [] });

// Security
export const useAuditLog = () => useApi(() => api.listAuditLog(), { entries: [] });
export const useSessions = () => useApi(() => api.listSessions(), { sessions: [] });

// Skills
export const useSkills = () => useApi(() => api.listSkills(), { skills: [] });
export const useSkillExecutions = () => useApi(() => api.listSkillExecutions(), { executions: [] });
export const useDemandSignals = () => useApi(() => api.listDemandSignals(), { signals: [] });

// Memory
export const useKanonSections = () => useApi(() => api.listKanonSections(), { sections: [] });

// Devices
export const useDiscoveredDevices = () => useApi(() => api.listDiscoveredDevices(), { devices: [] });
export const useRegisteredDevices = () => useApi(() => api.listRegisteredDevices(), { devices: [] });
export const useDeployments = () => useApi(() => api.listDeployments(), { deployments: [] });
export const useDeviceTests = () => useApi(() => api.listDeviceTests(), { tests: [] });

// SDR
export const useSDRDevices = () => useApi(() => api.listSDRDevices(), { devices: [] });
export const useCaptures = () => useApi(() => api.listCaptures(), { captures: [] });
export const useAnalyses = () => useApi(() => api.listAnalyses(), { analyses: [] });
export const useRFPolicies = () => useApi(() => api.listRFPolicies(), { policies: [] });

// Cellular
export const useRANStacks = () => useApi(() => api.listRANStacks(), { stacks: [] });
export const useCoreNetworks = () => useApi(() => api.listCoreNetworks(), { cores: [] });
export const useUEDevices = () => useApi(() => api.listUEDevices(), { ues: [] });
export const useIsolationChecks = () => useApi(() => api.listIsolationChecks(), { checks: [] });
export const useAttackVectors = () => useApi(() => api.listAttackVectors(), { vectors: [] });
export const useCPAnalyses = () => useApi(() => api.listCPAnalyses(), { analyses: [] });
export const useCellularEvidence = () => useApi(() => api.listCellularEvidence(), { evidence: [] });

// Quality
export const useGoldenSets = () => useApi(() => api.listGoldenSets(), { sets: [] });
export const useRegressions = () => useApi(() => api.listRegressions(), { alerts: [] });

// Rebuild
export const useRebuildPlans = () => useApi(() => api.listRebuildPlans(), { plans: [] });
export const useLPW = () => useApi(() => api.listLPW(), { entries: [] });

// Autonomy
export const useAutonomyStatus = () => useApi(() => api.getAutonomyStatus(), { status: {} });

// AEIS (extended)
export const useExplanations = () => useApi(() => api.listExplanations(), { explanations: [] });
export const useRatePolicies = () => useApi(() => api.listRatePolicies(), { policies: [] });

// Governance — Lifecycle
export const useLifecycleStages = () => useApi(() => api.listLifecycleStages(), { stages: [] });
export const useLifecycleEntries = (moduleId?: string) => useApi(() => api.listLifecycleEntries(moduleId), { entries: [] });

// Governance (extended)
export const useDecisionGates = () => useApi(() => api.listDecisionGates(), { gates: [] });

// Efficiency
export const usePerfBudgets = () => useApi(() => api.listPerfBudgets(), { budgets: [] });
export const useOverBudget = () => useApi(() => api.listOverBudget(), { items: [] });
export const useConfigDrift = () => useApi(() => api.listConfigDrift(), { drift: [] });
export const useCircuits = () => useApi(() => api.listCircuits(), { circuits: [] });

// Cost Envelope
export const useCostRecords = () => useApi(() => api.listCostRecords(), { records: [] });
export const useDailySpend = () => useApi(() => api.getDailySpend(), { daily_spend: 0 });
export const useMonthlySpend = () => useApi(() => api.getMonthlySpend(), { monthly_spend: 0 });

// Cost Monitor (alerts + summary)
export const useCostAlerts = (limit?: number) => useApi(() => api.getCostAlerts(limit), { alerts: [] });
export const useCostSummary = () => useApi(() => api.getCostSummary(), { providers: [], timestamp: 0 });

// Budget Monitoring
export const useModelBudgets = () => useApi(() => api.getModelBudgets(), { budgets: [] }, 10000);
export const useModelTransactions = (modelId?: string, limit?: number) => useApi(() => api.getModelTransactions(modelId, limit), { transactions: [] }, 10000);
export const useSpendingSummary = () => useApi(() => api.getSpendingSummary(), { total_budget: 0, total_spent: 0, total_remaining: 0, by_model: [] }, 10000);

// Security Profiles (Phase 5)
export function useSecurityProfiles() { return useApi(() => api.listSecurityProfiles(), { profiles: [] }); }
export function useActiveSecurityProfile() { return useApi(() => api.getActiveSecurityProfile(), { profile: {} as any }); }

// Core (parameterized)
export function useModule(id: string) { return useApi(() => api.getModule(id), {} as any); }
export function useContractVersions(name: string) { return useApi(() => api.listContractVersions(name), { versions: [] }); }

// Governance (parameterized)
export function useCompliance(scope: string) { return useApi(() => api.checkCompliance(scope), { compliance: {} as any }); }

// Execution (extended)
export function useRetryAttempts() { return useApi(() => api.listRetryAttempts(), { attempts: [] }); }

// Security (extended)
export function useAuthUsers() { return useApi(() => api.listAuthProviderUsers(), { users: [] }); }

// Monitoring
export function useCodeBloat() { return useApi(() => api.listCodeBloat(), { modules: [] }); }
export function useCostEnvelope() { return useApi(() => api.listCostEnvelope(), { records: [] }); }

// Memory (extended)
export function useSelfModels() { return useApi(() => api.listSelfModels(), { models: [] }); }
export function useEvidenceStore() { return useApi(() => api.listEvidenceStore(), { items: [] }); }

// AEIS (extended)
export function useImprovements() { return useApi(() => api.listImprovements(), { items: [] }); }
export function useAutonomyStages() { return useApi(() => api.listAutonomyStages(), { stages: [] }); }
export function useSelfObservation() { return useApi(() => api.listSelfObservation(), { mode: "active", metrics: {}, status: "healthy" } as any); }

// Rebuild (extended)
export function useCutoverPlans() { return useApi(() => api.listCutoverPlans(), { plans: [] }); }

// Surface
export function useAPIEndpoints() { return useApi(() => api.listAPIEndpoints(), { endpoints: [] }); }
export function useUIComponents() { return useApi(() => api.listUIComponents(), { components: [] }); }
export function useWSConnections() { return useApi(() => api.listWSConnections(), { connections: [] }); }

// Model Performance
export function useModelSummaries() { return useApi(() => api.getAllModelSummaries(), { summaries: [] }, 30000); }
export function useModelLeaderboard(metricType?: string) { return useApi(() => api.getModelLeaderboard(metricType), { leaderboard: [] }, 30000); }

// Decision Audit
export function useDecisionAuditLog(limit = 50) { return useApi(() => api.getDecisionAuditLog({ limit }), { entries: [] }, 15000); }

// ---------------------------------------------------------------------------
// Workspace WebSocket — real-time event streaming
// ---------------------------------------------------------------------------

export interface WSEvent {
  type: string;
  topic: string;
  payload: any;
  source_module: string;
  timestamp: number;
}

export function useWorkspaceWS(topics?: string[]) {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
    const wsUrl = base.replace(/^http/, "ws") + "/ws/workspace";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      if (topics && topics.length > 0) {
        ws.send(JSON.stringify({ type: "subscribe", topics }));
      }
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "event") {
          setEvents((prev) => [...prev.slice(-49), data]);
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, []);

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { events, connected, send };
}

// ---------------------------------------------------------------------------
// Pipeline runs (enhanced with real-time via WS)
// ---------------------------------------------------------------------------

export function usePipelineRunsWithWS() {
  const { data, loading, error, refresh } = useApi(() => api.listPipelineRuns(), { runs: [] }, 5000);
  const { events } = useWorkspaceWS(["pipeline."]);

  // Auto-refresh on pipeline events
  const lastEvent = events[events.length - 1];
  useEffect(() => {
    if (lastEvent && lastEvent.topic.startsWith("pipeline.")) {
      refresh();
    }
  }, [lastEvent, refresh]);

  return { data, loading, error, refresh };
}

// ---------------------------------------------------------------------------
// Notification count with WS updates
// ---------------------------------------------------------------------------

export function useNotificationCountWS(userId: string) {
  const [baseCount, setBaseCount] = useState(0);
  const { events, connected } = useWorkspaceWS(["notification."]);
  const liveNotificationCount = useMemo(
    () => events.filter((event) => event.topic === "notification.sent").length,
    [events],
  );

  useEffect(() => {
    api.getNotificationUnreadCount(userId).then((d: any) => setBaseCount(d.count ?? 0)).catch(() => {});
  }, [userId]);

  return { count: baseCount + liveNotificationCount, connected };
}

// Hallucination Detector
export const useHallucinationChecks = (status?: string) => useApi(() => api.listHallucinationChecks(status), { checks: [] });
export const useHallucinationStats = () => useApi(() => api.getHallucinationStats(), { stats: {} });

// Code Snapshots
export const useSnapshots = (moduleId?: string) => useApi(() => api.listSnapshots(moduleId), { snapshots: [] });

// Cascade Analyzer
export const useCascadeAnalyses = (sourceModule?: string) => useApi(() => api.listCascadeAnalyses(sourceModule), { analyses: [] });
export const useCascadeStats = () => useApi(() => api.getCascadeStats(), { stats: {} });

// Conflict Detector
export const useConflicts = (status?: string) => useApi(() => api.listConflicts(status), { conflicts: [] });
export const useConflictStats = () => useApi(() => api.getConflictStats(), { stats: {} });

// Compliance Checker
export const useCompliancePolicies = (scope?: string) => useApi(() => api.listCompliancePolicies(scope), { policies: [] });
export const useComplianceChecks = (moduleId?: string) => useApi(() => api.listComplianceChecks(moduleId), { checks: [] });
export const useComplianceStats = () => useApi(() => api.getComplianceStats(), { stats: {} });

// Session Manager
export const useSecurityUsers = () => useApi(() => api.listSecurityUsers(), { users: [] });
export const useSecuritySessions = () => useApi(() => api.listSecuritySessions(), { sessions: [] });
export const useAuditTrail = (limit?: number) => useApi(() => api.listAuditTrail(undefined, undefined, limit), { events: [] });

// Audit Trail (extended)
export const useAuditEvents = (params?: Record<string, unknown>) => useApi(() => api.listAuditEvents(params as any), { events: [] });
export const useAuditSummary = () => useApi(() => api.getAuditSummary(), {});
export const useEvidenceTimelines = () => useApi(() => api.listEvidenceTimelines(), { timelines: [] });
export const useEvidenceTimeline = (id: string) => useApi(() => api.getEvidenceTimeline(id), {});
export const useHealingRules = () => useApi(() => api.listHealingRules(), { rules: [] });
export const useHealingActions = (limit?: number) => useApi(() => api.listHealingActions(limit), { actions: [] });
export const useCapacityResources = () => useApi(() => api.listCapacityResources(), { resources: [] });
export const useCapacityRecommendations = () => useApi(() => api.getCapacityRecommendations(), { recommendations: [] });
export const useRiskScores = (moduleId?: string) => useApi(() => api.listRiskScores(moduleId), { scores: [] });
export const useChangeProposals = (status?: string) => useApi(() => api.listChangeProposals(status), { proposals: [] });
export const useAnomalies = (status?: string) => useApi(() => api.listAnomalies(status), { anomalies: [] });
export const useSlaPolicies = () => useApi(() => api.listSlaPolicies(), { policies: [] });
export const useConfigDrifts = (status?: string) => useApi(() => api.listConfigDrifts(status), { drifts: [] });
export const useMetricSummary = (metricName: string) => useApi(
  () => metricName ? api.getMetricSummary(metricName) : Promise.resolve({}),
  {},
);

// Worker fleet and autoscaler
export const useWorkers = () => useApi(() => api.listWorkers(), { workers: [] }, 10000);
export const useTopologies = () => useApi(() => api.listWorkerTopologies(), { topologies: [] }, 10000);
export const useAutoscalerStatus = () => useApi(() => api.getAutoscalerStatus(), {}, 10000);
export const useAutoscalerHistory = (limit?: number) => useApi(() => api.getAutoscalerHistory(limit), { history: [] }, 10000);
export const useAutoscalerPolicy = () => useApi(() => api.getAutoscalerPolicy(), {}, 30000);
export const useRuntimeAgents = () => useApi(() => api.listRuntimeAgents(), { agents: [] }, 10000);
export const useAgentRuntimeStats = () => useApi(() => api.getAgentRuntimeStats(), {}, 10000);
export const useAgentExecutions = (limit?: number) => useApi(() => api.listAgentExecutions(undefined, undefined, limit), { executions: [] }, 10000);

// Build, deploy, event backbone, and observability surfaces
export const useBuildState = () => useApi(() => api.getBuildState(), {});
export const useCandidateBuilds = () => useApi(() => api.listCandidateBuilds(), { builds: [] }, 10000);
export const useDrifts = () => useApi(() => api.listDrifts(), { drifts: [] }, 10000);
export const useDriftSummary = () => useApi(() => api.getDriftSummary(), {}, 10000);
export const useDeploySummary = () => useApi(() => api.getDeploySummary(), {}, 10000);
export const useDeployTopologies = () => useApi(() => api.getDeployTopologies(), { topologies: [] }, 10000);
export const useBackboneHealth = () => useApi(() => api.getBackboneHealth(), {});
export const useBackboneCatalog = () => useApi(() => api.getBackboneCatalog(), { topics: [], schemas: [] });
export const useBackboneEvents = (limit?: number) => useApi(() => api.listBackboneEvents(limit), { events: [] }, 10000);
export const useObservabilitySnapshot = () => useApi(() => api.getObservabilitySnapshot(), {});
export const useLogs = (service?: string, level?: string, limit?: number) => useApi(() => api.listObservabilityLogs(service, level, limit), { logs: [] }, 10000);
export const useMetrics = () => useApi(() => api.listObservabilityMetrics(), { metrics: [] }, 10000);
export const useTraces = (service?: string, limit?: number) => useApi(() => api.listObservabilityTraces(service, limit), { traces: [] }, 10000);

// Contracts (parameterized)
export const useContractsList = (activeOnly?: boolean) => useApi(() => api.listContractsActive(activeOnly), { contracts: [] });
export const useBundles = (status?: string) => useApi(() => api.listBundles(status), { bundles: [] });
export const useNotificationsList = (status?: string) => useApi(() => api.listNotifications(status), { notifications: [] });
export const useCircuitBreakers = (status?: string) => useApi(() => api.listCircuitBreakers(status), { breakers: [] });
export const useGoldenSetsList = (category?: string) => useApi(() => api.listGoldenSetsByCategory(category), { sets: [] });
export const useGovernanceGates = (gateType?: string) => useApi(() => api.listGovernanceGates(gateType), { gates: [] });
export const useHumanGateRequests = (status?: string) => useApi(() => api.listHumanGateRequests(status), { requests: [] });
export const useRoles = () => useApi(() => api.listRoles(), { roles: [] });
export const useExecutionPolicies = (scope?: string) => useApi(() => api.listExecutionPolicies(scope), { policies: [] });
export const useDecisionBoundaries = (scope?: string) => useApi(() => api.listDecisionBoundaries(scope), { boundaries: [] });
export const useDecisionSnapshotsList = (decisionId?: string) => useApi(() => api.listDecisionSnapshotsByDecision(decisionId), { snapshots: [] });
export const useHardenedAuditEvents = (eventType?: string) => useApi(() => api.getHardenedAuditEvents(eventType), { events: [] });

// Evaluator
export const useEvaluationCriteria = () => useApi(() => api.listEvaluationCriteria(), { criteria: [] });
export const useEvaluatorEvaluations = (status?: string) => useApi(() => api.listEvaluatorEvaluations(status), { evaluations: [] });

// Model Budget
export const useModelBudgetEntries = () => useApi(() => api.listModelBudgetEntries(), { budgets: [] });
export const useBudgetAlerts = (modelId?: string) => useApi(() => api.listBudgetAlerts(modelId), { alerts: [] });

// Integrations
export const useIntegrations = (type?: string) => useApi(() => api.listIntegrations(type), { integrations: [] });

// Connectors
export const useConnectors = (type?: string) => useApi(() => api.listConnectors(type), { connectors: [] });
export const useAdapters = (protocol?: string) => useApi(() => api.listAdapters(protocol), { adapters: [] });
export const useSecrets = (scope?: string) => useApi(() => api.listSecrets(scope), { secrets: [] });
export const useSecurityProfilesByLevel = (level?: string) => useApi(() => api.listSecurityProfilesByLevel(level), { profiles: [] });
export const useSecurityFindings = (severity?: string) => useApi(() => api.listSecurityFindings(severity), { findings: [] });
export const useSecurityScans = (status?: string) => useApi(() => api.listSecurityScans(status), { scans: [] });
export const useAuthProviders = (type?: string) => useApi(() => api.listAuthProviders(type), { providers: [] });
export const useBootstrapFlows = (status?: string) => useApi(() => api.listBootstrapFlows(status), { flows: [] });
export const useProfileSwaps = (status?: string) => useApi(() => api.listProfileSwaps(status), { swaps: [] });

// W14 E9 — Test Center hooks (K3 contract)
import { testingApi, type Severity } from "./testing";

export const useTestCharters = (projectId?: string) =>
  useApi(() => testingApi.listCharters(projectId), { kind: "TestCharter", items: [] as any[] });

export const useFindings = (severity?: Severity) =>
  useApi(() => testingApi.listFindings(severity), { kind: "Finding", items: [] as any[] });

export const useReleaseGate = (projectId: string) =>
  useApi(
    () => testingApi.evaluateRelease(projectId),
    { status: "blocked" as const, checklist_results: {}, blockers: [] as string[] },
  );

export const useTruthAlignment = (featureId?: string) =>
  useApi(() => testingApi.truthAlignment(featureId), { rows: [] as any[] });

export const useGuardianAlerts = () =>
  useApi(() => testingApi.guardianAlerts(), { kind: "GuardianAlert", items: [] as any[] });

export const usePersonas = () =>
  useApi(() => testingApi.personas(), { kind: "HumanPersona", items: [] as any[] });

export const useSimulationRuns = (limit: number = 50) =>
  useApi(() => testingApi.simulationRuns(limit), { kind: "TestRun", items: [] as any[] });

export const useLoopReports = () =>
  useApi(() => testingApi.loopReports(), { kind: "LoopReport", items: [] as any[] });

export const useRepairSessions = () =>
  useApi(() => testingApi.repairSessions(), { kind: "RepairAttempt", items: [] as any[] });
