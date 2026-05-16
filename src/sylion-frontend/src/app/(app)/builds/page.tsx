"use client";

import { useCallback, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useCandidateBuilds, useDriftSummary, useDrifts, useHealth } from "@/lib/api/hooks";
import { cn, fmtDateTime } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  GitCompare,
  Layers,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";

const statusColor = (status: string) => {
  if (status === "ready" || status === "promoted") return "bg-sylion-green/15 text-sylion-green border-sylion-green/20";
  if (status === "rejected" || status.endsWith("_failed")) return "bg-sylion-red/15 text-sylion-red border-sylion-red/20";
  if (status === "validating") return "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20";
  if (status.endsWith("_passed")) return "bg-sylion-blue/15 text-sylion-blue border-sylion-blue/20";
  return "bg-muted text-muted-foreground border-muted";
};

const severityColor = (severity: string) => {
  if (severity === "critical") return "bg-sylion-red/15 text-sylion-red border-sylion-red/20";
  if (severity === "warning") return "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20";
  return "bg-muted text-muted-foreground border-muted";
};

const getErrorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Unexpected API error";

type CandidateBuild = {
  build_id: string;
  name: string;
  status: string;
  patch_ids?: string[];
  module_ids?: string[];
  created_at?: number;
};

type DriftItem = {
  drift_id: string;
  description: string;
  source_module: string;
  target_module?: string | null;
  severity: string;
  status: string;
};

export default function BuildsPage() {
  const { data: health } = useHealth();
  const {
    data: buildsData,
    loading: buildsLoading,
    error: buildsError,
    refresh: refreshBuilds,
  } = useCandidateBuilds();
  const {
    data: driftsData,
    loading: driftsLoading,
    error: driftsError,
    refresh: refreshDrifts,
  } = useDrifts();
  const {
    data: driftSummary,
    loading: driftSummaryLoading,
    error: driftSummaryError,
    refresh: refreshSummary,
  } = useDriftSummary();

  const builds = Array.isArray(buildsData?.builds) ? (buildsData.builds as CandidateBuild[]) : [];
  const drifts = Array.isArray(driftsData?.drifts) ? (driftsData.drifts as DriftItem[]) : [];
  const backendLive = health?.status === "ok";

  const [selectedBuildId, setSelectedBuildId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const stats = {
    ready: builds.filter((build) => build.status === "ready").length,
    promoted: builds.filter((build) => build.status === "promoted").length,
    rejected: builds.filter((build) => build.status === "rejected").length,
    count: builds.length,
  };

  const buildsSectionLoading = buildsLoading && builds.length === 0;
  const driftSectionLoading = (driftsLoading || driftSummaryLoading) && drifts.length === 0;
  const driftSectionError = driftsError ?? driftSummaryError;
  const isRefreshing = busy === "refresh";

  const handleRefresh = useCallback(() => {
    setActionError(null);
    setBusy("refresh");
    refreshBuilds();
    refreshDrifts();
    refreshSummary();
    window.setTimeout(() => {
      setBusy((currentBusy) => (currentBusy === "refresh" ? null : currentBusy));
    }, 600);
  }, [refreshBuilds, refreshDrifts, refreshSummary]);

  const handleCreateBuild = useCallback(async () => {
    setActionError(null);
    setBusy("create");
    try {
      await api.createCandidateBuild({
        name: `Build-${Date.now()}`,
        description: "Auto-generated candidate build",
        module_ids: ["core.worker"],
      });
      refreshBuilds();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [refreshBuilds]);

  const handleValidate = useCallback(async (buildId: string) => {
    setActionError(null);
    setBusy(`val-${buildId}`);
    try {
      await api.validateCandidateBuild(buildId);
      refreshBuilds();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [refreshBuilds]);

  const handlePromote = useCallback(async (buildId: string) => {
    setActionError(null);
    setBusy(`prom-${buildId}`);
    try {
      await api.promoteCandidateBuild(buildId);
      refreshBuilds();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [refreshBuilds]);

  const handleReject = useCallback(async (buildId: string) => {
    setActionError(null);
    setBusy(`rej-${buildId}`);
    try {
      await api.rejectCandidateBuild(buildId, { reason: "Manual rejection from dashboard" });
      refreshBuilds();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [refreshBuilds]);

  const handleDetectDrift = useCallback(async () => {
    setActionError(null);
    setBusy("drift");
    try {
      await api.detectDrift();
      refreshDrifts();
      refreshSummary();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [refreshDrifts, refreshSummary]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
            <Layers className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Fabryka buildów</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">Candidate builds, validation & drift detection</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {backendLive && (
            <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
              <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-sylion-green pulse-glow-green" />
              LIVE
            </Badge>
          )}
          <Button size="sm" variant="ghost" onClick={handleRefresh} disabled={!!busy}>
            <RefreshCw className={cn("mr-1 h-3.5 w-3.5", isRefreshing && "animate-spin")} />
            Refresh
          </Button>
          <Button size="sm" variant="outline" onClick={handleCreateBuild} disabled={!!busy}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            New Build
          </Button>
          <Button size="sm" variant="outline" onClick={handleDetectDrift} disabled={!!busy}>
            <GitCompare className={cn("mr-1 h-3.5 w-3.5", busy === "drift" && "animate-spin")} />
            Detect Drift
          </Button>
        </div>
      </div>

      {actionError && (
        <Card className="border-sylion-red/20 bg-sylion-red/5 p-4" aria-live="polite">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-sylion-red" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-red">Build action failed</p>
              <p className="text-sm text-muted-foreground">{actionError}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="border-sylion-border bg-card p-4"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">Builds</p><p className="mt-1 text-2xl font-semibold">{stats.count}</p></Card>
        <Card className="border-sylion-border bg-card p-4"><p className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground"><CheckCircle2 className="h-3 w-3 text-sylion-green" /> Ready</p><p className="mt-1 text-2xl font-semibold text-sylion-green">{stats.ready}</p></Card>
        <Card className="border-sylion-border bg-card p-4"><p className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground"><Activity className="h-3 w-3 text-sylion-blue" /> Promoted</p><p className="mt-1 text-2xl font-semibold text-sylion-blue">{stats.promoted}</p></Card>
        <Card className="border-sylion-border bg-card p-4"><p className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground"><XCircle className="h-3 w-3 text-sylion-red" /> Rejected</p><p className="mt-1 text-2xl font-semibold text-sylion-red">{stats.rejected}</p></Card>
        <Card className="border-sylion-border bg-card p-4"><p className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground"><ShieldAlert className="h-3 w-3 text-sylion-amber" /> Drift Open</p><p className="mt-1 text-2xl font-semibold text-sylion-amber">{driftSummary?.total_open ?? 0}</p></Card>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Candidate Builds</h2>
          {buildsLoading && !buildsSectionLoading && (
            <span className="text-xs text-muted-foreground">Refreshing build list...</span>
          )}
        </div>

        {buildsSectionLoading ? (
          <Card className="border-sylion-border p-6" aria-live="polite">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Loading candidate builds...
            </div>
          </Card>
        ) : buildsError ? (
          <Card className="border-sylion-red/20 bg-sylion-red/5 p-6" aria-live="polite">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-sylion-red">Build data unavailable</p>
                <p className="text-sm text-muted-foreground">{buildsError}</p>
              </div>
              <Button size="sm" variant="outline" onClick={handleRefresh} disabled={!!busy}>
                <RefreshCw className="mr-1 h-3.5 w-3.5" />
                Retry builds
              </Button>
            </div>
          </Card>
        ) : builds.length === 0 ? (
          <Card className="border-sylion-border p-6">
            <div className="space-y-3">
              <p className="text-sm font-medium">No candidate builds yet</p>
              <p className="text-sm text-muted-foreground">
                Create a build to verify the live integration flow against the backend route contract.
              </p>
              <Button size="sm" variant="outline" onClick={handleCreateBuild} disabled={!!busy}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                Create first build
              </Button>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {builds.map((build) => {
              const isSelected = selectedBuildId === build.build_id;
              return (
                <Card
                  key={build.build_id}
                  className={cn(
                    "cursor-pointer border-sylion-border bg-card p-4 transition-all hover:border-primary/30",
                    isSelected && "border-primary/30 ring-1 ring-primary/40"
                  )}
                  onClick={() => setSelectedBuildId(isSelected ? null : build.build_id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Layers className="h-4 w-4 text-primary" />
                      <div>
                        <p className="text-sm font-medium">{build.name}</p>
                        <p className="font-mono text-[10px] text-muted-foreground">{build.build_id}</p>
                      </div>
                    </div>
                    <Badge variant="outline" className={cn("text-[10px] capitalize", statusColor(build.status))}>
                      {build.status}
                    </Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
                    <span>{build.module_ids?.length ?? 0} module(s)</span>
                    <span>{build.patch_ids?.length ?? 0} patch(es)</span>
                    <span className="sm:ml-auto"><Clock className="mr-0.5 inline h-3 w-3" />{fmtDateTime(build.created_at ?? "")}</span>
                  </div>
                  {isSelected && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); handleValidate(build.build_id); }} disabled={!!busy}>
                        <Play className="mr-1 h-3 w-3" />
                        Validate
                      </Button>
                      {build.status === "ready" && (
                        <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); handlePromote(build.build_id); }} disabled={!!busy}>
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Promote
                        </Button>
                      )}
                      <Button size="sm" variant="destructive" onClick={(event) => { event.stopPropagation(); handleReject(build.build_id); }} disabled={!!busy}>
                        <XCircle className="mr-1 h-3 w-3" />
                        Reject
                      </Button>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Contract Drift</h3>
          <p className="text-xs text-sylion-amber">{driftSummary?.total_open ?? 0} open</p>
        </div>
        {driftSectionLoading ? (
          <Card className="border-sylion-border p-4" aria-live="polite">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Loading drift status...
            </div>
          </Card>
        ) : driftSectionError ? (
          <Card className="border-sylion-amber/20 bg-sylion-amber/5 p-4" aria-live="polite">
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-amber">Drift data unavailable</p>
              <p className="text-sm text-muted-foreground">{driftSectionError}</p>
            </div>
          </Card>
        ) : drifts.length === 0 ? (
          <Card className="border-sylion-border p-4">
            <p className="text-sm font-medium">No open drift detected.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Run drift detection to verify the current integration contract surface.
            </p>
          </Card>
        ) : (
          <div className="space-y-2">
            {drifts.slice(0, 10).map((drift) => (
              <Card key={drift.drift_id} className="flex items-center gap-3 border-sylion-border bg-card p-3">
                <GitCompare className="h-4 w-4 text-sylion-amber" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{drift.description}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{drift.source_module} -&gt; {drift.target_module || "n/a"}</p>
                </div>
                <Badge variant="outline" className={cn("text-[10px] capitalize", severityColor(drift.severity))}>{drift.severity}</Badge>
                <Badge variant="outline" className="text-[10px] capitalize">{drift.status}</Badge>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
