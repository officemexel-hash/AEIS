"use client";

import { useCallback, useMemo, useState } from "react";
import { useAutoscalerHistory, useAutoscalerPolicy, useAutoscalerStatus, useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn, fmtDateTime } from "@/lib/utils";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Gauge,
  History,
  Loader2,
  Minus,
  RefreshCw,
  Save,
  Settings,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

type AutoscalerStatus = {
  timestamp?: number;
  decision?: string;
  reason?: string;
  pending_assignments?: number;
  active_workers?: number;
  total_capacity?: number;
  in_cooldown?: boolean;
  cooldown_remaining_sec?: number;
};

type AutoscalerHistoryItem = {
  timestamp?: number;
  action?: string;
  worker_id?: string;
  result?: string;
};

type AutoscalerPolicy = {
  min_workers?: number;
  max_workers?: number;
  target_queue_depth?: number;
  scale_up_threshold_ratio?: number;
  scale_down_threshold_ratio?: number;
  cooldown_sec?: number;
};

type PolicyForm = {
  min_workers: string;
  max_workers: string;
  target_queue_depth: string;
  scale_up_threshold_ratio: string;
  scale_down_threshold_ratio: string;
  cooldown_sec: string;
};

const getErrorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Unexpected autoscaler API error";

const formatDecisionLabel = (decision?: string) => {
  if (!decision) return "Unknown";
  if (decision === "scale_up") return "Scale Up";
  if (decision === "scale_down") return "Scale Down";
  return "Maintain";
};

const renderDecisionIcon = (decision?: string, className?: string) => {
  if (decision === "scale_up") return <TrendingUp className={className} />;
  if (decision === "scale_down") return <TrendingDown className={className} />;
  return <Minus className={className} />;
};

const decisionBadgeClass = (decision?: string) => {
  if (decision === "scale_up") return "border-sylion-red/20 bg-sylion-red/10 text-sylion-red";
  if (decision === "scale_down") return "border-sylion-amber/20 bg-sylion-amber/10 text-sylion-amber";
  return "border-sylion-green/20 bg-sylion-green/10 text-sylion-green";
};

const policyToForm = (policy?: AutoscalerPolicy): PolicyForm => ({
  min_workers: policy?.min_workers?.toString() ?? "",
  max_workers: policy?.max_workers?.toString() ?? "",
  target_queue_depth: policy?.target_queue_depth?.toString() ?? "",
  scale_up_threshold_ratio: policy?.scale_up_threshold_ratio?.toString() ?? "",
  scale_down_threshold_ratio: policy?.scale_down_threshold_ratio?.toString() ?? "",
  cooldown_sec: policy?.cooldown_sec?.toString() ?? "",
});

const parsePolicyForm = (form: PolicyForm) => {
  const parsed = {
    min_workers: Number(form.min_workers),
    max_workers: Number(form.max_workers),
    target_queue_depth: Number(form.target_queue_depth),
    scale_up_threshold_ratio: Number(form.scale_up_threshold_ratio),
    scale_down_threshold_ratio: Number(form.scale_down_threshold_ratio),
    cooldown_sec: Number(form.cooldown_sec),
  };

  if (Object.values(parsed).some((value) => Number.isNaN(value))) {
    throw new Error("All policy fields must be valid numbers.");
  }
  if (parsed.min_workers < 0 || parsed.max_workers < 1 || parsed.target_queue_depth < 0 || parsed.cooldown_sec < 0) {
    throw new Error("Worker counts, queue depth and cooldown must be non-negative.");
  }
  if (parsed.min_workers > parsed.max_workers) {
    throw new Error("Minimum workers cannot exceed maximum workers.");
  }
  if (parsed.scale_up_threshold_ratio <= 0 || parsed.scale_down_threshold_ratio < 0) {
    throw new Error("Threshold ratios must be positive values.");
  }

  return parsed;
};

const policyFields: Array<{ key: keyof PolicyForm; label: string; step?: string }> = [
  { key: "min_workers", label: "Min workers", step: "1" },
  { key: "max_workers", label: "Max workers", step: "1" },
  { key: "target_queue_depth", label: "Target queue depth", step: "1" },
  { key: "scale_up_threshold_ratio", label: "Scale up ratio", step: "0.1" },
  { key: "scale_down_threshold_ratio", label: "Scale down ratio", step: "0.1" },
  { key: "cooldown_sec", label: "Cooldown (sec)", step: "1" },
];

export default function AutoscalerPage() {
  const { data: health } = useHealth();
  const {
    data: statusData,
    loading: statusLoading,
    error: statusError,
    refresh: refreshStatus,
  } = useAutoscalerStatus();
  const {
    data: historyData,
    loading: historyLoading,
    error: historyError,
    refresh: refreshHistory,
  } = useAutoscalerHistory(10);
  const {
    data: policyData,
    loading: policyLoading,
    error: policyError,
    refresh: refreshPolicy,
  } = useAutoscalerPolicy();

  const status = statusData as AutoscalerStatus | undefined;
  const history = Array.isArray((historyData as { history?: AutoscalerHistoryItem[] } | undefined)?.history)
    ? (((historyData as { history?: AutoscalerHistoryItem[] }).history) ?? [])
    : [];
  const policy = policyData as AutoscalerPolicy | undefined;

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);
  const [policyDraft, setPolicyDraft] = useState<PolicyForm | null>(null);
  const [policyDirty, setPolicyDirty] = useState(false);

  const backendLive = health?.status === "ok";
  const statusLabel = formatDecisionLabel(status?.decision);
  const statusBadge = decisionBadgeClass(status?.decision);

  const initialSurfaceLoading = statusLoading && historyLoading && policyLoading;
  const statusEmpty = !statusLoading && !statusError && (status?.active_workers ?? 0) === 0 && (status?.pending_assignments ?? 0) === 0;
  const historyEmpty = !historyLoading && !historyError && history.length === 0;
  const policyPristineSnapshot = useMemo(() => policyToForm(policy), [policy]);
  const policyForm = policyDirty ? (policyDraft ?? policyPristineSnapshot) : policyPristineSnapshot;
  const policyChanged = useMemo(() => JSON.stringify(policyForm) !== JSON.stringify(policyPristineSnapshot), [policyForm, policyPristineSnapshot]);

  const refreshAll = useCallback(() => {
    setActionError(null);
    setBusyAction("refresh");
    refreshStatus();
    refreshHistory();
    refreshPolicy();
    window.setTimeout(() => {
      setBusyAction((current) => (current === "refresh" ? null : current));
    }, 600);
  }, [refreshHistory, refreshPolicy, refreshStatus]);

  const handleEvaluate = useCallback(async () => {
    setActionError(null);
    setBusyAction("evaluate");
    try {
      const result = await api.evaluateAutoscaler();
      setLastResult(result as Record<string, unknown>);
      refreshStatus();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  }, [refreshStatus]);

  const handleExecute = useCallback(async (decision?: string) => {
    const resolvedDecision = decision ?? status?.decision ?? "maintain";
    setActionError(null);
    setBusyAction(`execute:${resolvedDecision}`);
    try {
      const result = await api.executeAutoscaler(resolvedDecision);
      setLastResult(result as Record<string, unknown>);
      refreshStatus();
      refreshHistory();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  }, [refreshHistory, refreshStatus, status?.decision]);

  const handlePolicyChange = useCallback((key: keyof PolicyForm, value: string) => {
    setPolicyDirty(true);
    setPolicyDraft((current) => ({
      ...(current ?? policyPristineSnapshot),
      [key]: value,
    }));
  }, [policyPristineSnapshot]);

  const handleSavePolicy = useCallback(async () => {
    setActionError(null);
    setBusyAction("save-policy");
    try {
      const nextPolicy = parsePolicyForm(policyForm);
      const result = await api.updateAutoscalerPolicy(nextPolicy);
      setLastResult(result as Record<string, unknown>);
      setPolicyDirty(false);
      setPolicyDraft(null);
      refreshPolicy();
      refreshStatus();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  }, [policyForm, refreshPolicy, refreshStatus]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
            <Gauge className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Autoskalowanie</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Live scaling evaluation, execution history and policy control for the worker fleet.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {backendLive && (
            <Badge variant="outline" className="border-sylion-green/30 text-[10px] text-sylion-green">
              <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-sylion-green pulse-glow-green" />
              LIVE
            </Badge>
          )}
          <Badge variant="outline" className={cn("text-[10px]", statusBadge)}>
            {renderDecisionIcon(status?.decision, "mr-1 h-3 w-3")}
            {statusLoading ? "Loading" : statusLabel}
          </Badge>
          <Button size="sm" variant="outline" onClick={refreshAll} disabled={busyAction !== null}>
            <RefreshCw className={cn("mr-1 h-3.5 w-3.5", busyAction === "refresh" && "animate-spin")} />
            Refresh
          </Button>
          <Button size="sm" variant="outline" onClick={() => void handleEvaluate()} disabled={busyAction !== null}>
            {busyAction === "evaluate" ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Gauge className="mr-1 h-3.5 w-3.5" />
            )}
            Evaluate
          </Button>
          <Button size="sm" onClick={() => void handleExecute()} disabled={busyAction !== null}>
            {busyAction === `execute:${status?.decision ?? "maintain"}` ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
            )}
            Execute Decision
          </Button>
        </div>
      </div>

      {actionError && (
        <Card className="border-sylion-red/20 bg-sylion-red/5 p-4" aria-live="polite">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-sylion-red" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-red">Autoscaler action failed</p>
              <p className="text-sm text-muted-foreground">{actionError}</p>
            </div>
          </div>
        </Card>
      )}

      {initialSurfaceLoading ? (
        <Card className="border-sylion-border p-6" aria-live="polite">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading autoscaler surface...
          </div>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Card className="border-sylion-border bg-card p-4">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Decision</p>
              <p className="mt-1 text-2xl font-semibold">{statusLabel}</p>
              <p className="mt-1 text-xs text-muted-foreground">{status?.reason ?? "No evaluation details yet."}</p>
            </Card>
            <Card className="border-sylion-border bg-card p-4">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Pending Assignments</p>
              <p className="mt-1 text-2xl font-semibold">{status?.pending_assignments ?? 0}</p>
            </Card>
            <Card className="border-sylion-border bg-card p-4">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Active Workers</p>
              <p className="mt-1 text-2xl font-semibold">{status?.active_workers ?? 0}</p>
            </Card>
            <Card className="border-sylion-border bg-card p-4">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Total Capacity</p>
              <p className="mt-1 text-2xl font-semibold">{status?.total_capacity ?? 0}</p>
            </Card>
            <Card className="border-sylion-border bg-card p-4">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Cooldown</p>
              <p className="mt-1 text-2xl font-semibold">
                {status?.in_cooldown ? `${Math.ceil(status?.cooldown_remaining_sec ?? 0)}s` : "Ready"}
              </p>
            </Card>
          </div>

          {statusError ? (
            <Card className="border-sylion-red/20 bg-sylion-red/5 p-5" aria-live="polite">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-sylion-red">Autoscaler status unavailable</p>
                  <p className="text-sm text-muted-foreground">{statusError}</p>
                </div>
                <Button size="sm" variant="outline" onClick={refreshAll} disabled={busyAction !== null}>
                  Retry
                </Button>
              </div>
            </Card>
          ) : statusEmpty ? (
            <Card className="border-dashed border-sylion-border p-5">
              <div className="space-y-3">
                <p className="text-sm font-medium">No active workers or pending assignments</p>
                <p className="text-sm text-muted-foreground">
                  Register workers or queue assignments first. The autoscaler has nothing to evaluate yet.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => void handleEvaluate()} disabled={busyAction !== null}>
                    Evaluate now
                  </Button>
                  <Button size="sm" variant="outline" onClick={refreshAll} disabled={busyAction !== null}>
                    Refresh surface
                  </Button>
                </div>
              </div>
            </Card>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Card className="border-sylion-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Recent Actions</h2>
                </div>
                {historyLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
              </div>

              {historyError ? (
                <div className="space-y-1 rounded-lg border border-sylion-red/20 bg-sylion-red/5 p-4">
                  <p className="text-sm font-medium text-sylion-red">History unavailable</p>
                  <p className="text-sm text-muted-foreground">{historyError}</p>
                </div>
              ) : historyEmpty ? (
                <div className="rounded-lg border border-dashed border-sylion-border p-4">
                  <p className="text-sm font-medium">No scaling actions yet</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Evaluate the fleet or execute a decision to create the first autoscaler event.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {history.map((entry, index) => {
                    return (
                      <div key={`${entry.timestamp ?? "entry"}-${index}`} className="flex items-start gap-3 rounded-lg border border-sylion-border px-3 py-3">
                        <div className="mt-0.5 rounded-full bg-primary/10 p-1.5">
                          {renderDecisionIcon(entry.action, "h-3.5 w-3.5 text-primary")}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline" className={cn("text-[10px]", decisionBadgeClass(entry.action))}>
                              {formatDecisionLabel(entry.action)}
                            </Badge>
                            {entry.worker_id && (
                              <span className="font-mono text-[10px] text-muted-foreground">{entry.worker_id}</span>
                            )}
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {entry.timestamp ? fmtDateTime(entry.timestamp) : "Timestamp unavailable"}
                            {entry.result ? ` · ${entry.result}` : ""}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            <Card className="border-sylion-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Settings className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Policy</h2>
                </div>
                <Button size="sm" variant="outline" onClick={() => void handleSavePolicy()} disabled={busyAction !== null || !policyChanged}>
                  {busyAction === "save-policy" ? (
                    <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="mr-1 h-3.5 w-3.5" />
                  )}
                  Save Policy
                </Button>
              </div>

              {policyLoading && !policyDirty ? (
                <div className="flex items-center gap-3 rounded-lg border border-sylion-border p-4 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading policy...
                </div>
              ) : policyError ? (
                <div className="space-y-1 rounded-lg border border-sylion-red/20 bg-sylion-red/5 p-4">
                  <p className="text-sm font-medium text-sylion-red">Policy unavailable</p>
                  <p className="text-sm text-muted-foreground">{policyError}</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {policyFields.map((field) => (
                      <label key={field.key} className="space-y-1.5">
                        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                          {field.label}
                        </span>
                        <input
                          value={policyForm[field.key]}
                          onChange={(event) => handlePolicyChange(field.key, event.target.value)}
                          inputMode="decimal"
                          type="number"
                          step={field.step ?? "1"}
                          className="h-9 w-full rounded-md border border-[rgba(148,163,184,0.08)] bg-[#0f1629] px-3 text-sm text-foreground outline-none transition-colors focus:border-primary/30"
                        />
                      </label>
                    ))}
                  </div>
                  <div className="rounded-lg border border-sylion-border bg-background/30 p-3">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Cpu className="h-3.5 w-3.5" />
                      Policy changes apply immediately to future evaluations and executions.
                    </div>
                  </div>
                </div>
              )}
            </Card>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Button variant="outline" onClick={() => void handleExecute("scale_up")} disabled={busyAction !== null}>
              {busyAction === "execute:scale_up" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <TrendingUp className="mr-2 h-4 w-4" />
              )}
              Scale Up
            </Button>
            <Button variant="outline" onClick={() => void handleExecute("scale_down")} disabled={busyAction !== null}>
              {busyAction === "execute:scale_down" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <TrendingDown className="mr-2 h-4 w-4" />
              )}
              Scale Down
            </Button>
            <Button variant="outline" onClick={() => void handleExecute("maintain")} disabled={busyAction !== null}>
              {busyAction === "execute:maintain" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Minus className="mr-2 h-4 w-4" />
              )}
              Maintain
            </Button>
          </div>

          {lastResult && (
            <Card className="border-sylion-border bg-card p-5">
              <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Last Action Result</h2>
              <pre className="mt-3 overflow-x-auto rounded-lg bg-[#0f1629] p-3 text-xs text-foreground">
                {JSON.stringify(lastResult, null, 2)}
              </pre>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
