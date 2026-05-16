"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  FileText,
  GitBranch,
  Layers3,
  Loader2,
  RefreshCw,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TestTube2,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const phases = [
  { id: "26", label: "Model Selection", state: "READY_FOR_SKILL_SYNTHESIS", icon: Brain },
  { id: "27", label: "Skill Synthesis", state: "READY_FOR_MASTERPLAN", icon: Wrench },
  { id: "28", label: "Masterplan Synthesis", state: "READY_FOR_TEST_PLAN", icon: ClipboardCheck },
  { id: "29", label: "Test Plan", state: "READY_FOR_PREFLIGHT_COST", icon: TestTube2 },
  { id: "30", label: "Pre-Flight Cost", state: "READY_FOR_DRY_RUN", icon: SlidersHorizontal },
  { id: "31", label: "Dry Run", state: "READY_FOR_BUILD", icon: ShieldCheck },
];

function safeList(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />;
  if (status === "info") return <Clock3 className="mt-0.5 h-3.5 w-3.5 text-primary" />;
  return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />;
}

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "green" | "amber" | "red";
}) {
  return (
    <Card
      className={cn(
        "border-sylion-border bg-card p-4",
        tone === "green" && "border-sylion-green/30",
        tone === "amber" && "border-sylion-amber/30",
        tone === "red" && "border-sylion-red/30",
      )}
    >
      <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 truncate text-2xl font-semibold tracking-tight">{value}</div>
    </Card>
  );
}

function MiniRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs">
      <span className="truncate font-medium">{label}</span>
      <span className="truncate text-muted-foreground">{value}</span>
    </div>
  );
}

export function PlanningDashboard() {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";
  const [overview, setOverview] = useState<any | null>(null);
  const [project, setProject] = useState<any | null>(null);
  const [acceptance, setAcceptance] = useState<Record<string, any>>({});
  const [edgeCases, setEdgeCases] = useState<any | null>(null);
  const [diagnosis, setDiagnosis] = useState<any | null>(null);
  const [resourceProfiles, setResourceProfiles] = useState<any[]>([]);
  const [activePhase, setActivePhase] = useState("26");
  const [selectedProfile, setSelectedProfile] = useState("profile_2");
  const [customWorkers, setCustomWorkers] = useState(3);
  const [customEnvironments, setCustomEnvironments] = useState(2);
  const [operatorNotes, setOperatorNotes] = useState("Approve Group D planning continuation.");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const projectId = project?.project_id as string | undefined;
  const planning = project?.planning || {};
  const modelSelection = planning.model_selection || {};
  const skillSynthesis = planning.skill_synthesis || {};
  const masterplan = planning.masterplan || {};
  const testPlan = planning.test_plan || {};
  const preflightCost = planning.preflight_cost || {};
  const dryRun = planning.dry_run || {};
  const currentAcceptance = acceptance[activePhase] || {};
  const currentPhase = phases.find((item) => item.id === activePhase) || phases[0];
  const CurrentPhaseIcon = currentPhase.icon;
  const activeEdgeCases = edgeCases?.phases?.[activePhase]?.edge_cases || [];
  const rows = overview?.phases || [];
  const groupComplete = Boolean(overview?.group?.complete);
  const hardBlocks = currentAcceptance.hard_blocks?.length || 0;
  const stateLabel = project?.state || "BRAK_AKTYWNEGO_PROJEKTU";
  const auditEntries = project?.audit_chain?.length || currentAcceptance.audit_chain?.entries || 0;
  const selectedProfileData = resourceProfiles.find((item) => item.id === selectedProfile);

  const acceptedCount = useMemo(
    () => rows.filter((row: any) => row.accepted).length,
    [rows],
  );

  const load = useCallback(async () => {
    if (!backendLive) {
      setOverview(null);
      setProject(null);
      setAcceptance({});
      setEdgeCases(null);
      setLoading(false);
      setStatus("Backend niedostępny.");
      return;
    }
    setLoading(true);
    try {
      const overviewData = await api.getPlanningOverview();
      setOverview(overviewData);
      setResourceProfiles(overviewData.resource_profiles || []);
      const active = overviewData.active_project;
      if (active?.project_id) {
        const [projectData, edgeData] = await Promise.all([
          api.getPlanningProject(active.project_id),
          api.getPlanningEdgeCases(active.project_id),
        ]);
        setProject(projectData.project);
        setAcceptance(projectData.acceptance || {});
        setEdgeCases(edgeData);
        setResourceProfiles(projectData.resource_profiles || overviewData.resource_profiles || []);
      } else {
        setProject(null);
        setAcceptance({});
        setEdgeCases(null);
      }
      setStatus("");
    } catch (err: any) {
      setStatus(`Planning error: ${err.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const withBusy = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setStatus("");
    try {
      await action();
      await load();
    } catch (err: any) {
      setStatus(err.message || String(err));
    } finally {
      setBusy("");
    }
  };

  const ensureProject = () => {
    if (!projectId) {
      setStatus("Brak aktywnego projektu. Najpierw zakończ fazy 16-25.");
      return false;
    }
    return true;
  };

  const actionBody = { approved: true, operator_id: "operator", notes: operatorNotes };

  const assignModels = () =>
    withBusy("phase26", async () => {
      if (!ensureProject()) return;
      const data = await api.assignModelsPhase26(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "26": data.acceptance });
      setActivePhase("26");
      setStatus("Phase 26 model assignment matrix generated.");
    });

  const synthesizeSkills = () =>
    withBusy("phase27", async () => {
      if (!ensureProject()) return;
      const data = await api.synthesizeSkillsPhase27(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "27": data.acceptance });
      setActivePhase("27");
      setStatus("Phase 27 skill synthesis complete.");
    });

  const generateMasterplan = () =>
    withBusy("phase28", async () => {
      if (!ensureProject()) return;
      const body =
        selectedProfile === "custom"
          ? {
              ...actionBody,
              profile_id: "custom",
              custom_profile: {
                name: "Custom operator profile",
                workers: customWorkers,
                environments: customEnvironments,
                guards: "hybrid local T1 + sonnet T2",
              },
            }
          : { ...actionBody, profile_id: selectedProfile };
      const data = await api.generateMasterplanPhase28(projectId as string, body);
      setProject(data.project);
      setAcceptance({ ...acceptance, "28": data.acceptance });
      setActivePhase("28");
      setStatus("Phase 28 masterplan generated and signed.");
    });

  const generateTestPlan = () =>
    withBusy("phase29", async () => {
      if (!ensureProject()) return;
      const data = await api.generateTestPlanPhase29(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "29": data.acceptance });
      setActivePhase("29");
      setStatus("Phase 29 test plan generated.");
    });

  const generatePreflightCost = () =>
    withBusy("phase30", async () => {
      if (!ensureProject()) return;
      const data = await api.generatePreflightCostPhase30(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "30": data.acceptance });
      setActivePhase("30");
      setStatus("Phase 30 pre-flight cost approved.");
    });

  const runDryRun = () =>
    withBusy("phase31", async () => {
      if (!ensureProject()) return;
      const data = await api.runDryRunPhase31(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "31": data.acceptance });
      setActivePhase("31");
      setStatus("Phase 31 dry run complete. Ready for build.");
    });

  const runAcceptance = () =>
    withBusy(`accept-${activePhase}`, async () => {
      if (!ensureProject()) return;
      const data = await api.runPlanningAcceptanceTest(projectId as string, activePhase);
      setAcceptance({ ...acceptance, [activePhase]: data });
      setStatus(`Faza ${activePhase}: ${data.accepted ? "zaliczona" : "zablokowana"}.`);
    });

  const diagnose = () =>
    withBusy(`diag-${activePhase}`, async () => {
      if (!ensureProject()) return;
      const caseId = activeEdgeCases[0]?.id || "EC-A1";
      const data = await api.diagnosePlanningEdgeCase(projectId as string, {
        phase: activePhase,
        case_id: caseId,
        context: { surface: "planning-dashboard", state: stateLabel },
      });
      setDiagnosis(data);
      setStatus(`Diagnosed ${data.case?.id || caseId}.`);
    });

  return (
    <div className="min-h-screen bg-background px-5 py-5 text-foreground lg:px-8">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">GROUP D</Badge>
              <Badge variant={groupComplete ? "default" : "secondary"}>
                {groupComplete ? "PLANNING PART 1 READY" : "PLANNING ACTIVE"}
              </Badge>
              <Badge variant={backendLive ? "default" : "destructive"}>{backendLive ? "BACKEND DZIAŁA" : "BACKEND NIEDOSTĘPNY"}</Badge>
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight md:text-3xl">Planowanie wykonania</h1>
            <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
              Fazy 26-28 przechodza od zablokowanej Ksiegi do wykonawczego masterplanu z modelami, skillami,
              warstwami, profilami zasobow i kosztami guardow.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading || Boolean(busy)}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Refresh
            </Button>
            <Button variant="outline" onClick={() => { window.location.href = "/council-to-ksiega"; }}>
              Group C
            </Button>
          </div>
        </div>

        {status && (
          <Card className="border-sylion-border bg-secondary/20 px-4 py-3 text-sm">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-sylion-amber" />
              <span>{status}</span>
            </div>
          </Card>
        )}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label="Zaliczone fazy" value={`${acceptedCount}/6`} tone={groupComplete ? "green" : "amber"} />
          <Metric label="Edge cases" value={overview?.group?.edge_cases || 98} />
          <Metric label="Model rows" value={safeList(modelSelection.assignment_matrix).length || 0} />
          <Metric label="Skill patterns" value={safeList(skillSynthesis.patterns).length || 0} />
          <Metric label="Ready state" value={stateLabel === "READY_FOR_BUILD" ? "BUILD" : safeList(masterplan.work_units).length || 0} tone={stateLabel === "READY_FOR_BUILD" ? "green" : "default"} />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(380px,0.9fr)]">
          <div className="flex flex-col gap-5">
            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-xs uppercase text-muted-foreground">Active project</div>
                  <div className="mt-1 truncate text-lg font-semibold">{project?.name || "Brak aktywnego projektu"}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">{projectId || "Najpierw ukończ Grupę C"}</div>
                </div>
                <Badge variant={stateLabel === "READY_FOR_TEST_PLAN" ? "default" : "secondary"}>{stateLabel}</Badge>
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                <MiniRow label="D-level" value={project?.classification?.d_level_label || "-"} />
                <MiniRow label="Audit entries" value={auditEntries} />
                <MiniRow label="Shell" value={project?.shell?.root ? "ready" : "missing"} />
              </div>
            </Card>

            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              {phases.map((phase) => {
                const Icon = phase.icon;
                const accepted = Boolean(acceptance[phase.id]?.accepted);
                const active = activePhase === phase.id;
                return (
                  <button
                    key={phase.id}
                    type="button"
                    onClick={() => setActivePhase(phase.id)}
                    className={cn(
                      "rounded-lg border p-4 text-left transition",
                      active ? "border-primary bg-primary/10" : "border-sylion-border bg-card hover:border-primary/50",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <Icon className={cn("h-5 w-5", accepted ? "text-sylion-green" : "text-muted-foreground")} />
                      <Badge variant={accepted ? "default" : "secondary"}>{accepted ? "ZALICZONA" : "OTWARTA"}</Badge>
                    </div>
                    <div className="mt-3 text-sm font-semibold">Phase {phase.id}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{phase.label}</div>
                    <div className="mt-3 truncate text-[11px] text-muted-foreground">{phase.state}</div>
                  </button>
                );
              })}
            </div>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <CurrentPhaseIcon className="h-5 w-5 text-primary" />
                    <h2 className="text-lg font-semibold">Phase {activePhase}: {currentPhase.label}</h2>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Blokady twarde: {hardBlocks}. Warunki akceptacji: {currentAcceptance.dod?.passed_required || 0}/{currentAcceptance.dod?.required || 0}.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={assignModels} disabled={!projectId || Boolean(busy)} variant={activePhase === "26" ? "default" : "outline"}>
                    {busy === "phase26" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Brain className="mr-2 h-4 w-4" />}
                    Przypisz modele
                  </Button>
                  <Button onClick={synthesizeSkills} disabled={!projectId || Boolean(busy)} variant={activePhase === "27" ? "default" : "outline"}>
                    {busy === "phase27" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                    Zsyntetyzuj skille
                  </Button>
                  <Button onClick={generateMasterplan} disabled={!projectId || Boolean(busy)} variant={activePhase === "28" ? "default" : "outline"}>
                    {busy === "phase28" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}
                    Wygeneruj masterplan
                  </Button>
                  <Button onClick={generateTestPlan} disabled={!projectId || Boolean(busy)} variant={activePhase === "29" ? "default" : "outline"}>
                    {busy === "phase29" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TestTube2 className="mr-2 h-4 w-4" />}
                    Wygeneruj plan testów
                  </Button>
                  <Button onClick={generatePreflightCost} disabled={!projectId || Boolean(busy)} variant={activePhase === "30" ? "default" : "outline"}>
                    {busy === "phase30" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <SlidersHorizontal className="mr-2 h-4 w-4" />}
                    Zatwierdź koszt
                  </Button>
                  <Button onClick={runDryRun} disabled={!projectId || Boolean(busy)} variant={activePhase === "31" ? "default" : "outline"}>
                    {busy === "phase31" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                    Uruchom próbę suchą
                  </Button>
                </div>
              </div>

              <label className="mt-4 block text-xs font-medium uppercase text-muted-foreground">Operator notes</label>
              <textarea
                value={operatorNotes}
                onChange={(event) => setOperatorNotes(event.target.value)}
                className="mt-2 min-h-20 w-full resize-y rounded-md border border-sylion-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />

              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="outline" onClick={runAcceptance} disabled={!projectId || Boolean(busy)}>
                  {busy === `accept-${activePhase}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TestTube2 className="mr-2 h-4 w-4" />}
                  Run acceptance
                </Button>
                <Button variant="outline" onClick={diagnose} disabled={!projectId || Boolean(busy)}>
                  {busy === `diag-${activePhase}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                  Diagnose edge case
                </Button>
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Resource profile selection</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Phase 28 uses the selected profile for timeline, guard scaling and cost trade-offs.</p>
                </div>
                <SlidersHorizontal className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {resourceProfiles.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    onClick={() => setSelectedProfile(profile.id)}
                    className={cn(
                      "rounded-lg border p-3 text-left transition",
                      selectedProfile === profile.id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10 hover:border-primary/50",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="truncate text-sm font-semibold">{profile.name}</div>
                      {profile.recommended && <Badge>recommended</Badge>}
                    </div>
                    <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                      <div>{profile.workers} workers, {profile.environment_label}</div>
                      <div>${profile.total_cost_usd} total, {profile.timeline_label}</div>
                      <div>{profile.guards}</div>
                    </div>
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setSelectedProfile("custom")}
                  className={cn(
                    "rounded-lg border p-3 text-left transition",
                    selectedProfile === "custom" ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10 hover:border-primary/50",
                  )}
                >
                  <div className="text-sm font-semibold">Custom profile</div>
                  <div className="mt-2 text-xs text-muted-foreground">Manual workers, environments and hybrid guards.</div>
                </button>
              </div>
              {selectedProfile === "custom" ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <label className="text-xs font-medium uppercase text-muted-foreground">
                    Workers
                    <input
                      type="number"
                      min={1}
                      max={16}
                      value={customWorkers}
                      onChange={(event) => setCustomWorkers(Number(event.target.value))}
                      className="mt-2 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                    />
                  </label>
                  <label className="text-xs font-medium uppercase text-muted-foreground">
                    Environments
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={customEnvironments}
                      onChange={(event) => setCustomEnvironments(Number(event.target.value))}
                      className="mt-2 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                    />
                  </label>
                </div>
              ) : selectedProfileData ? (
                <div className="mt-4 grid gap-2 md:grid-cols-4">
                  <MiniRow label="Profile" value={selectedProfileData.name} />
                  <MiniRow label="Cost" value={`$${selectedProfileData.total_cost_usd}`} />
                  <MiniRow label="Timeline" value={selectedProfileData.timeline_label} />
                  <MiniRow label="Ryzyko" value={selectedProfileData.risk} />
                </div>
              ) : null}
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <h2 className="text-lg font-semibold">Phase details</h2>
              <div className="mt-4 grid gap-4 xl:grid-cols-3">
                <div>
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <Brain className="h-4 w-4" />
                    Model matrix
                  </div>
                  <div className="space-y-2">
                    {safeList(modelSelection.assignment_matrix).slice(0, 8).map((row: any) => (
                      <MiniRow key={row.task_type} label={row.label} value={row.primary_model} />
                    ))}
                    {!safeList(modelSelection.assignment_matrix).length && <div className="text-sm text-muted-foreground">No model matrix yet.</div>}
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <Sparkles className="h-4 w-4" />
                    Skill patterns
                  </div>
                  <div className="space-y-2">
                    {safeList(skillSynthesis.patterns).slice(0, 8).map((pattern: any) => (
                      <MiniRow key={pattern.id} label={pattern.title} value={pattern.result} />
                    ))}
                    {!safeList(skillSynthesis.patterns).length && <div className="text-sm text-muted-foreground">No skill synthesis yet.</div>}
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <Layers3 className="h-4 w-4" />
                    Final checks
                  </div>
                  <div className="space-y-2">
                    <MiniRow label="Warstwy" value={safeList(masterplan.layers).length || 0} />
                    <MiniRow label="Pokrycie AC testami" value={testPlan.covered_acceptance_criteria ? `${testPlan.covered_acceptance_criteria}/${testPlan.total_acceptance_criteria}` : "oczekuje"} />
                    <MiniRow label="Decyzja kosztowa" value={preflightCost.operator_decision?.decision || "oczekuje"} />
                    <MiniRow label="Pewność próby suchej" value={dryRun.confidence ? `${Math.round(dryRun.confidence * 100)}%` : "oczekuje"} />
                  </div>
                </div>
              </div>
            </Card>
          </div>

          <div className="flex flex-col gap-5">
            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <Route className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Acceptance</h2>
              </div>
              <div className="mt-4 space-y-3">
                {safeList(currentAcceptance.checks).map((check: any) => (
                  <div key={check.id} className="flex gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-sm">
                    <StatusIcon status={check.status} />
                    <div className="min-w-0">
                      <div className="font-medium">{check.label}</div>
                      <div className="mt-1 truncate text-xs text-muted-foreground">{check.evidence}</div>
                    </div>
                  </div>
                ))}
                {!safeList(currentAcceptance.checks).length && <div className="text-sm text-muted-foreground">Run the phase or acceptance test to see checks.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Artifacts</h2>
              </div>
              <div className="mt-4 space-y-2">
                <MiniRow label="Faza 26" value={modelSelection.artifacts?.markdown?.path ? "zapisano" : "oczekuje"} />
                <MiniRow label="Faza 27" value={skillSynthesis.artifacts?.structured_data?.path ? "zapisano" : "oczekuje"} />
                <MiniRow label="Masterplan" value={masterplan.artifacts?.markdown?.path ? "zapisano" : "oczekuje"} />
                <MiniRow label="PDF" value={masterplan.artifacts?.pdf?.path ? "zapisano" : "oczekuje"} />
                <MiniRow label="Faza 29" value={testPlan.artifacts?.structured_data?.path ? "zapisano" : "oczekuje"} />
                <MiniRow label="Faza 30" value={preflightCost.artifacts?.structured_data?.path ? "zapisano" : "oczekuje"} />
                <MiniRow label="Faza 31" value={dryRun.artifacts?.structured_data?.path ? "zapisano" : "oczekuje"} />
              </div>
              {masterplan.artifacts?.markdown?.path && (
                <div className="mt-3 break-all rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
                  {masterplan.artifacts.markdown.path}
                </div>
              )}
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-sylion-amber" />
                <h2 className="text-lg font-semibold">Edge cases</h2>
              </div>
              <div className="mt-4 grid gap-2">
                {activeEdgeCases.slice(0, 8).map((item: any) => (
                  <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{item.id}</span>
                      <Badge variant={item.severity === "high" ? "destructive" : "secondary"}>{item.severity}</Badge>
                    </div>
                    <div className="mt-1 text-muted-foreground">{item.title}</div>
                  </div>
                ))}
              </div>
              {diagnosis && (
                <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                  <div className="font-semibold">Last diagnosis: {diagnosis.case?.id}</div>
                  <div className="mt-1 text-muted-foreground">{diagnosis.case?.title}</div>
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
