"use client";

/**
 * SYLION AEIS Advisor — React hooks.
 *
 * Mirrors the existing pattern in `lib/api/hooks.ts`: each hook wraps a single
 * advisor REST call and returns an honest empty/error state when backend data
 * is unavailable. It must not synthesize demo Advisor decisions.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  advisorApi,
  AdvisorCardEnvelope,
  CardAction,
  EvidencePack,
  GrantProgram,
  HandleActionResponse,
  DEFAULT_OPERATOR_ID,
  OnboardingState,
  PreferenceEntry,
  ProjectLifecycleState,
  RiskLevel,
} from "@/lib/api/advisor";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const HEALTH_URL = API_BASE ? `${API_BASE}/health` : "/api/v1/health";
const REACHABLE_TTL_MS = 15000;

let _reachable: boolean | null = null;
let _checkedAt = 0;

async function isBackendReachable(): Promise<boolean> {
  const now = Date.now();
  if (_reachable !== null && now - _checkedAt < REACHABLE_TTL_MS) return _reachable;
  try {
    const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(2500), cache: "no-store" });
    _reachable = res.ok;
  } catch {
    _reachable = false;
  }
  _checkedAt = now;
  return _reachable;
}

interface FetchState<T> {
  data: T;
  loading: boolean;
  error: string | null;
  source: "live" | "error" | "loading";
}

function useFetch<T>(fetcher: () => Promise<T>, fallback: T, refreshMs?: number): FetchState<T> & { refresh: () => void } {
  const [data, setData] = useState<T>(fallback);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"live" | "error" | "loading">("loading");
  const mounted = useRef(true);

  const run = useCallback(async () => {
    if (!mounted.current) return;
    const reachable = await isBackendReachable();
    if (!reachable) {
      if (!mounted.current) return;
      setData(fallback);
      setError("backend_unreachable");
      setSource("error");
      setLoading(false);
      return;
    }
    try {
      const value = await fetcher();
      if (!mounted.current) return;
      setData(value);
      setError(null);
      setSource("live");
    } catch (err) {
      if (!mounted.current) return;
      setError(err instanceof Error ? err.message : String(err));
      setData(fallback);
      setSource("error");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [fetcher, fallback]);

  useEffect(() => {
    mounted.current = true;
    queueMicrotask(() => void run());
    let timer: ReturnType<typeof setInterval> | null = null;
    if (refreshMs) {
      timer = setInterval(() => {
        if (mounted.current) run();
      }, refreshMs);
    }
    return () => {
      mounted.current = false;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMs]);

  return { data, loading, error, source, refresh: run };
}

// ---------------------------------------------------------------------------
// Live feed
// ---------------------------------------------------------------------------

export function useAdvisorFeed(opts?: { project_id?: string; refreshMs?: number }) {
  const fetcher = useCallback(
    () => advisorApi.listCards({ operator_id: DEFAULT_OPERATOR_ID, project_id: opts?.project_id, limit: 50 }).then((r) => r.cards),
    [opts?.project_id],
  );
  return useFetch<AdvisorCardEnvelope[]>(fetcher, [], opts?.refreshMs ?? 8000);
}

export function useAdvisorCard(cardId: string | null) {
  const fetcher = useCallback(
    async (): Promise<AdvisorCardEnvelope | null> => (cardId ? advisorApi.getCard(cardId) : null),
    [cardId],
  );
  const fallback: AdvisorCardEnvelope | null = null;
  const { data, loading, error, source, refresh } = useFetch<AdvisorCardEnvelope | null>(
    fetcher,
    fallback,
  );
  return { card: data, loading, error, source, refresh };
}

// ---------------------------------------------------------------------------
// Card actions (mutation, no fallback — but degrades gracefully)
// ---------------------------------------------------------------------------

export function useCardActions() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(
    async (
      cardId: string,
      action: CardAction,
      payload?: {
        operator_note?: string;
        modified_recommendation?: string;
        preference_key?: string;
        preference_project_type?: string;
        preference_project_domain?: string;
        preference_value?: unknown;
        dont_learn_flag?: boolean;
      },
      biometricVerified = false,
    ): Promise<HandleActionResponse | null> => {
      setSubmitting(true);
      setError(null);
      try {
        const reachable = await isBackendReachable();
        if (!reachable) {
          throw new Error("backend_unreachable");
        }
        return await advisorApi.handleAction(cardId, action, payload, biometricVerified);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [],
  );

  return { submit, submitting, error };
}

// ---------------------------------------------------------------------------
// Evidence pack
// ---------------------------------------------------------------------------

export function useEvidencePack(packId: string | null) {
  const fetcher = useCallback(
    async (): Promise<EvidencePack | null> => (packId ? advisorApi.getEvidencePack(packId) : null),
    [packId],
  );
  const fallback: EvidencePack | null = null;
  const { data, loading, error, source, refresh } = useFetch<EvidencePack | null>(fetcher, fallback);
  return { pack: data, loading, error, source, refresh };
}

// ---------------------------------------------------------------------------
// Onboarding
// ---------------------------------------------------------------------------

const ONBOARDING_LS_KEY = "sylion.advisor.onboarding";

function maskSecret(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) return "";
  if (value.length <= 8) return "***";
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function isSecretField(name: string): boolean {
  const lowered = name.toLowerCase();
  return (
    lowered.includes("key") ||
    lowered.includes("token") ||
    lowered.includes("secret") ||
    lowered.includes("password") ||
    lowered.includes("credential")
  );
}

function redactOnboardingForLocalStorage(state: OnboardingState): OnboardingState {
  const copy = JSON.parse(JSON.stringify(state)) as OnboardingState;
  const values = copy.values || {};
  const apiKeys = values.api_keys;
  if (Array.isArray(apiKeys)) {
    for (const row of apiKeys) {
      if (row && typeof row === "object" && "key" in row) {
        const record = row as Record<string, unknown>;
        record.key = maskSecret(record.key);
        record.key_masked = true;
      }
    }
  }
  const hostingProviders = values.hosting_providers;
  if (Array.isArray(hostingProviders)) {
    for (const row of hostingProviders) {
      if (!row || typeof row !== "object") continue;
      const record = row as Record<string, unknown>;
      const fields = record.fields;
      if (!fields || typeof fields !== "object") continue;
      for (const [key, value] of Object.entries(fields as Record<string, unknown>)) {
        if (isSecretField(key)) {
          (fields as Record<string, unknown>)[key] = maskSecret(value);
        }
      }
      record.secrets_masked = true;
    }
  }
  return copy;
}

function readLocalOnboarding(): OnboardingState {
  if (typeof window === "undefined") return { step: 1, completed_steps: [], values: {} };
  try {
    const raw = window.localStorage.getItem(ONBOARDING_LS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore
  }
  return { step: 1, completed_steps: [], values: {} };
}

function writeLocalOnboarding(state: OnboardingState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ONBOARDING_LS_KEY, JSON.stringify(redactOnboardingForLocalStorage(state)));
  } catch {
    // ignore
  }
}

export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>(() => ({ step: 1, completed_steps: [], values: {} }));
  const [submitting, setSubmitting] = useState(false);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(async () => {
      try {
        const reachable = await isBackendReachable();
        const liveState = reachable ? await advisorApi.getOnboardingState() : readLocalOnboarding();
        if (cancelled) return;
        setState(liveState);
        stateRef.current = liveState;
        writeLocalOnboarding(liveState);
      } catch {
        if (cancelled) return;
        const localState = readLocalOnboarding();
        setState(localState);
        stateRef.current = localState;
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const saveStep = useCallback(
    async (step: number, values: Record<string, unknown>) => {
      setSubmitting(true);
      const current = stateRef.current;
      const next: OnboardingState = {
        step,
        completed_steps: Array.from(new Set([...current.completed_steps, step])),
        values: { ...current.values, ...values },
        completed_at: current.completed_at,
      };
      stateRef.current = next;
      setState(next);
      writeLocalOnboarding(next);
      try {
        const reachable = await isBackendReachable();
        if (reachable) {
          await advisorApi.saveOnboardingStep(step, values);
        }
      } catch {
        // backend not ready — local state still saved
      } finally {
        setSubmitting(false);
      }
      return next;
    },
    [],
  );

  const complete = useCallback(async () => {
    const current = stateRef.current;
    const next: OnboardingState = { ...current, completed_at: Date.now() / 1000 };
    const reachable = await isBackendReachable();
    if (!reachable) {
      throw new Error("Backend jest niedostepny, konfiguracja runtime nie zostala zapisana.");
    }
    const completed = await advisorApi.completeOnboarding(current.values);
    const safeNext: OnboardingState = {
      ...completed,
      completed_at: next.completed_at,
    };
    stateRef.current = safeNext;
    setState(safeNext);
    writeLocalOnboarding(safeNext);
    return safeNext;
  }, []);

  const completePhase1 = useCallback(async (values: Record<string, unknown>) => {
    const current = stateRef.current;
    const reachable = await isBackendReachable();
    if (!reachable) {
      throw new Error("Backend jest niedostepny, faza 1 nie zostala zapisana.");
    }
    const completed = await advisorApi.completePhase1({ ...current.values, ...values });
    stateRef.current = completed;
    setState(completed);
    writeLocalOnboarding(completed);
    return completed;
  }, []);

  const reset = useCallback(() => {
    const fresh: OnboardingState = { step: 1, completed_steps: [], values: {} };
    stateRef.current = fresh;
    setState(fresh);
    writeLocalOnboarding(fresh);
    void isBackendReachable()
      .then((reachable) => (reachable ? advisorApi.resetOnboarding() : fresh))
      .then((serverState) => {
        const next = serverState ?? fresh;
        stateRef.current = next;
        setState(next);
        writeLocalOnboarding(next);
      })
      .catch(() => {
        // Local reset is still useful when the API is offline.
      });
    return fresh;
  }, []);

  return { state, saveStep, complete, completePhase1, reset, submitting };
}

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

export function usePreferences(userId: string = DEFAULT_OPERATOR_ID) {
  const fetcher = useCallback(() => advisorApi.listPreferences(userId).then((r) => r.preferences), [userId]);
  const fallback = emptyPreferences();
  const { data, loading, error, source, refresh } = useFetch<PreferenceEntry[]>(fetcher, fallback);
  return { preferences: data, loading, error, source, refresh };
}

function emptyPreferences(): PreferenceEntry[] {
  return [];
}

// ---------------------------------------------------------------------------
// Lifecycle dashboard
// ---------------------------------------------------------------------------

export function useProjectLifecycle(projectId: string | null) {
  const fetcher = useCallback(
    async (): Promise<ProjectLifecycleState | null> =>
      projectId ? advisorApi.getProjectLifecycle(projectId) : null,
    [projectId],
  );
  const fallback: ProjectLifecycleState | null = null;
  const { data, loading, error, source, refresh } = useFetch<ProjectLifecycleState | null>(fetcher, fallback, 12000);
  return { lifecycle: data, loading, error, source, refresh };
}

// ---------------------------------------------------------------------------
// Monitoring dashboard
// ---------------------------------------------------------------------------

export function useMonitoringSnapshot(refreshMs: number = 30000) {
  const fetcher = useCallback(() => advisorApi.getMonitoringSnapshot(), []);
  const fallback = { projects: [], throughput: [], cost_vs_budget: { spend_usd: 0, budget_usd: 0, per_project: {} as Record<string, { spend: number; budget: number }> }, council_activity: [], subscription_recommendations: [] as AdvisorCardEnvelope[], alerts: [] as Array<{ id: string; severity: RiskLevel; title: string; card_id?: string }> };
  const { data, loading, error, source, refresh } = useFetch(fetcher, fallback, refreshMs);
  return { snapshot: data, loading, error, source, refresh };
}

// ---------------------------------------------------------------------------
// Funding
// ---------------------------------------------------------------------------

export function useGrantPrograms(filters?: { country?: string; region?: string }) {
  const country = filters?.country;
  const region = filters?.region;
  const fetcher = useCallback(
    () => advisorApi.listGrants({ country, region }).then((r) => r.grants),
    [country, region],
  );
  const fallback: GrantProgram[] = [];
  const { data, loading, error, source, refresh } = useFetch(fetcher, fallback);
  return { grants: data, loading, error, source, refresh };
}

export function useFundingDeadlines() {
  const fetcher = useCallback(() => advisorApi.getFundingDeadlines().then((r) => r.deadlines), []);
  const fallback: Array<{ grant_program_id: string; display_name: string; deadline: number; days_remaining: number }> = [];
  const { data, loading, error, source, refresh } = useFetch(fetcher, fallback);
  return { deadlines: data, loading, error, source, refresh };
}
