"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Gauge,
  Layers3,
  Loader2,
  LockKeyhole,
  RefreshCw,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TestTube2,
  TimerReset,
  Workflow,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const selectClass =
  "h-9 rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary";

function levelNum(level: string | undefined) {
  if (!level) return 0;
  const parsed = Number(level.replace("L", ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />;
  if (status === "warn") return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-amber" />;
  return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />;
}

function Metric({ label, value, tone = "default" }: { label: string; value: string | number; tone?: "default" | "green" | "amber" }) {
  return (
    <Card className={cn("border-sylion-border bg-card p-4", tone === "green" && "border-sylion-green/30", tone === "amber" && "border-sylion-amber/30")}>
      <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
    </Card>
  );
}

function MiniRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs">
      <span className="truncate font-medium">{label}</span>
      <span className="truncate text-muted-foreground">{value}</span>
    </div>
  );
}

export default function AutonomyPage() {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";
  const [goal, setGoal] = useState("apps_internal");
  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [activeDimension, setActiveDimension] = useState("cost_decisions");
  const [activeStep, setActiveStep] = useState(1);
  const [trace, setTrace] = useState<any | null>(null);
  const [diagnosis, setDiagnosis] = useState<any | null>(null);

  const load = useCallback(async () => {
    if (!backendLive) {
      setSnapshot(null);
      setLoading(false);
      setStatus("Backend niedostępny.");
      return;
    }
    setLoading(true);
    try {
      const data = await api.getAutonomyConfiguration(goal);
      setSnapshot(data);
      setActiveStep(Number(data.settings?.wizard?.current_step || 1));
      setStatus("");
    } catch (err: any) {
      setStatus(`Autonomy configuration error: ${err.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive, goal]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const settings = snapshot?.settings || {};
  const templates = snapshot?.templates || {};
  const acceptance = snapshot?.acceptance || {};
  const dimensions = settings.dimensions || {};
  const hardGates = settings.hard_gates || [];
  const customGates = settings.custom_hard_gates || [];
  const activeGates = useMemo(
    () => [...hardGates, ...customGates].filter((gate: any) => gate.enabled),
    [hardGates, customGates],
  );
  const dimensionRows = useMemo(
    () => (templates.dimensions || []).map((dimension: any) => ({ ...dimension, config: dimensions[dimension.id] || {} })),
    [templates.dimensions, dimensions],
  );
  const activeDimensionRow = dimensionRows.find((item: any) => item.id === activeDimension) || dimensionRows[0];
  const activeDimensionConfig = activeDimensionRow?.config || {};
  const activeLevel = activeDimensionConfig.level || "L0";
  const activeLevelInfo = (templates.levels || []).find((item: any) => item.id === activeLevel);
  const risk = settings.risk_preview || {};

  const withBusy = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setStatus("");
    try {
      await action();
    } catch (err: any) {
      setStatus(err.message || String(err));
    } finally {
      setBusy("");
    }
  };

  const applyPreset = () =>
    withBusy("preset", async () => {
      const data = await api.applyAutonomyPreset({ goal, mode: "quick", accept_phase4_preset: true });
      setSnapshot(data);
      setStatus(`Preset applied: ${data.settings?.selected_preset}.`);
    });

  const setMode = (mode: string) =>
    withBusy(`mode:${mode}`, async () => {
      const data = await api.setAutonomyWizardMode({ mode });
      setSnapshot(data.snapshot);
      setStatus(`Wizard mode: ${mode}.`);
    });

  const saveStep = (skipped = false) =>
    withBusy("step", async () => {
      const data = await api.saveAutonomyWizardStep({
        step: activeStep,
        skipped,
        values: { goal, saved_from_dashboard: true },
      });
      setSnapshot(data.snapshot);
      setActiveStep(Number(data.wizard?.current_step || activeStep));
      setStatus(skipped ? "Step skipped with preset inheritance." : "Step saved.");
    });

  const saveDimensionLevel = (dimensionId: string, level: string) =>
    withBusy(`dim:${dimensionId}`, async () => {
      const body: Record<string, unknown> = {
        dimension_id: dimensionId,
        level,
        reason: "phase5_dashboard_adjustment",
      };
      if (dimensionId === "cost_decisions") body.settings = { requires_budget_cap: true, budget_switch_threshold_pct: 70 };
      if (dimensionId === "quality_verdicts") body.d_level_adaptive = { D1: "L4", D2: "L3", D3: "L2", D4: "L1", D5: "L0" };
      const data = await api.saveAutonomyDimensionConfig(body);
      setSnapshot(data.snapshot);
      setActiveDimension(dimensionId);
      setStatus(`${dimensionId} saved as ${level}.`);
    });

  const applyDLevelQuality = () =>
    withBusy("dlevel", async () => {
      const data = await api.saveAutonomyDLevelOverrides({
        dimension_id: "quality_verdicts",
        enabled: true,
        overrides: { D1: "L4", D2: "L3", D3: "L2", D4: "L1", D5: "L0" },
      });
      setSnapshot(data.snapshot);
      setActiveDimension("quality_verdicts");
      setStatus("Quality per-D-level adaptive table saved.");
    });

  const reviewGates = () =>
    withBusy("review-gates", async () => {
      const data = await api.reviewAutonomyHardGates({
        reviewed_gate_ids: hardGates.map((gate: any) => gate.id),
        accepted_baseline: true,
        no_custom_needed: true,
      });
      setSnapshot(data.snapshot);
      setStatus("Baseline hard gates reviewed.");
    });

  const addDemoCustomGate = () =>
    withBusy("custom-gate", async () => {
      const data = await api.addAutonomyCustomHardGate({
        label: "Customer email blast over 100 recipients",
        condition: "email_recipients > 100",
        category: "operator_custom",
        dimension_lock: "cascade_re_evaluation",
        timeout_minutes: 30,
      });
      setSnapshot(data.snapshot);
      setStatus("Demo custom hard gate added.");
    });

  const createOverride = () =>
    withBusy("override", async () => {
      const data = await api.createAutonomyOverride({
        dimension_id: "cost_decisions",
        level: "L4",
        scope: "per_build",
        reason: "short experiment with cheaper-model switching",
        project_id: "operator_project",
        expires_in_hours: 5,
      });
      setSnapshot(data.snapshot);
      setStatus(data.override?.conflict ? "Override saved with hard-gate conflict note." : "Cost override saved.");
    });

  const traceInheritance = () =>
    withBusy("trace", async () => {
      const data = await api.traceAutonomyInheritance({
        dimension_id: activeDimension || "cost_decisions",
        goal,
        d_level: goal === "public_products" ? "D4" : "D3",
        project_id: "operator_project",
      });
      setTrace(data);
      await load();
      setStatus(`Inheritance trace effective level: ${data.effective_level}.`);
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      const data = await api.diagnoseAutonomyEdgeCase({
        case_id: "EC-C4",
        context: { source: "phase5_dashboard", dimension_id: activeDimension },
      });
      setDiagnosis(data);
      setStatus("Edge case EC-C4 diagnosed.");
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      const data = await api.runAutonomyConfigurationAcceptanceTest(goal);
      setSnapshot(await api.getAutonomyConfiguration(goal));
      setStatus(data.accepted ? "Phase 5 acceptance passed." : `Phase 5 hard blocks: ${data.hard_blocks?.length || 0}.`);
    });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Gauge className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Autonomy Configuration - Faza 5</h1>
            <p className="text-sm text-muted-foreground">10 wymiarow, L0-L5, hard gates, overrides, inheritance i acceptance.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className={cn(selectClass, "w-[180px]")} value={goal} onChange={(event) => setGoal(event.target.value)}>
            {["apps_internal", "public_products", "cybersecurity", "research"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
            Refresh
          </Button>
          <Button size="sm" className="h-8 text-xs" onClick={applyPreset} disabled={busy === "preset"}>
            {busy === "preset" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Sparkles className="mr-1 h-3 w-3" />}
            Apply Phase 4 preset
          </Button>
          <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
            {backendLive ? "BACKEND DZIAŁA" : "BACKEND NIEDOSTĘPNY"}
          </Badge>
          <Badge variant="outline" className={cn("text-[10px]", acceptance.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
            {acceptance.accepted ? "PHASE 5 READY" : "PHASE 5 PENDING"}
          </Badge>
        </div>
      </div>

      {status ? <Card className="border-sylion-amber/30 bg-sylion-amber/10 p-3 text-xs text-sylion-amber">{status}</Card> : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        <Metric label="Dimensions" value={dimensionRows.length || 0} />
        <Metric label="Levels" value={(templates.levels || []).length || 0} />
        <Metric label="Active gates" value={activeGates.length || 0} tone="green" />
        <Metric label="Custom gates" value={customGates.length || 0} />
        <Metric label="Edge cases" value={(templates.edge_cases || []).length || 0} />
        <Metric label="Risk x" value={risk.risk_multiplier || "--"} tone={Number(risk.risk_multiplier || 0) > 1.8 ? "amber" : "default"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="border-sylion-border bg-card p-3">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Workflow className="h-4 w-4 text-primary" />
            Wizard 1-10
          </div>
          <div className="space-y-1">
            {(templates.wizard_steps || []).map((step: any) => (
              <button
                key={step.step}
                type="button"
                onClick={() => setActiveStep(step.step)}
                className={cn("flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-xs", activeStep === step.step ? "bg-primary text-primary-foreground" : "bg-secondary/10 text-muted-foreground hover:text-foreground")}
              >
                <span>{step.step}. {step.label}</span>
                <ChevronRight className="h-3 w-3" />
              </button>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-muted-foreground">
            <div>Done: {(settings.wizard?.completed_steps || []).length}</div>
            <div>Skipped: {(settings.wizard?.skipped_steps || []).length}</div>
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <SlidersHorizontal className="h-4 w-4 text-primary" />
                Step {activeStep}/10 - {(templates.wizard_steps || []).find((step: any) => step.step === activeStep)?.label || "Autonomy"}
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">Mode: {settings.wizard?.mode || "quick"} / preset: {settings.selected_preset || "balanced"}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => saveStep(true)} disabled={busy === "step"}>Skip step</Button>
              <Button size="sm" className="h-8 text-xs" onClick={() => saveStep(false)} disabled={busy === "step"}>
                {busy === "step" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckCircle2 className="mr-1 h-3 w-3" />}
                Save step
              </Button>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-5">
            {(templates.wizard_modes || []).map((mode: any) => (
              <button
                key={mode.id}
                type="button"
                onClick={() => setMode(mode.id)}
                className={cn("rounded-md border p-3 text-left text-xs", settings.wizard?.mode === mode.id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10")}
              >
                <div className="font-medium">{mode.label}</div>
                <div className="mt-1 text-[10px] text-muted-foreground">{mode.duration}</div>
              </button>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-4">
            <MiniRow label="Speed multiplier" value={`${risk.speed_multiplier || "--"}x`} />
            <MiniRow label="Average level" value={String(risk.average_level ?? "--")} />
            <MiniRow label="Cost variance" value={`${risk.cost_variance_pct ?? "--"}%`} />
            <MiniRow label="Conflicts" value={String((snapshot?.conflicts || []).length)} />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Layers3 className="h-4 w-4 text-primary" />
              10 autonomy dimensions
            </h2>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={applyDLevelQuality} disabled={busy === "dlevel"}>
              <Route className="mr-1 h-3 w-3" />
              Apply D-level table
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
            {dimensionRows.map((dimension: any) => (
              <button
                key={dimension.id}
                type="button"
                onClick={() => setActiveDimension(dimension.id)}
                className={cn("rounded-md border p-3 text-left transition-colors", activeDimension === dimension.id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10 hover:bg-secondary/20")}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="h-5 text-[9px]">{dimension.code}</Badge>
                      <span className="truncate text-xs font-semibold">{dimension.name}</span>
                    </div>
                    <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{dimension.regulates}</div>
                  </div>
                  <Badge variant="outline" className={cn("h-6 text-[10px]", levelNum(dimension.config?.level) >= 4 ? "border-sylion-amber/30 text-sylion-amber" : "border-primary/30 text-primary")}>
                    {dimension.config?.level || "L0"}
                  </Badge>
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Gauge className="h-4 w-4 text-primary" />
            {activeDimensionRow?.code || "DIM"} - {activeDimensionRow?.name || "Dimension"}
          </h2>
          <div className="mt-3 space-y-2">
            <MiniRow label="Current level" value={`${activeLevel} / ${activeLevelInfo?.label || ""}`} />
            <MiniRow label="Inherited from" value={activeDimensionConfig.inherited_from || settings.selected_preset || "preset"} />
            <MiniRow label="Risk profile" value={activeDimensionRow?.risk_profile || "n/a"} />
            <MiniRow label="Operator range" value={activeDimensionRow?.operator_range || "n/a"} />
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {(templates.levels || []).map((level: any) => (
              <Button
                key={level.id}
                variant={activeLevel === level.id ? "default" : "outline"}
                size="sm"
                className="h-8 text-xs"
                onClick={() => saveDimensionLevel(activeDimensionRow?.id || "cost_decisions", level.id)}
                disabled={busy === `dim:${activeDimensionRow?.id}`}
              >
                {level.id}
              </Button>
            ))}
          </div>
          <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
            <div className="font-medium">{activeLevelInfo?.label || activeLevel}</div>
            <div className="mt-1 text-[11px] text-muted-foreground">{activeLevelInfo?.behavior || "No level details."}</div>
          </div>
          <Button className="mt-3 h-8 w-full text-xs" size="sm" onClick={() => saveDimensionLevel("cost_decisions", "L4")} disabled={busy === "dim:cost_decisions"}>
            <Zap className="mr-1 h-3 w-3" />
            Save DIM-3 L4
          </Button>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <LockKeyhole className="h-4 w-4 text-primary" />
                Hard gates baseline
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">{hardGates.length} baseline / {customGates.length} custom / {activeGates.length} active</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={reviewGates} disabled={busy === "review-gates"}>
                <ShieldCheck className="mr-1 h-3 w-3" />
                Review baseline gates
              </Button>
              <Button size="sm" className="h-8 text-xs" onClick={addDemoCustomGate} disabled={busy === "custom-gate"}>
                <Zap className="mr-1 h-3 w-3" />
                Add demo custom gate
              </Button>
            </div>
          </div>
          <div className="mt-3 grid max-h-[420px] grid-cols-1 gap-2 overflow-auto pr-1 md:grid-cols-2">
            {[...hardGates, ...customGates].map((gate: any) => (
              <div key={gate.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{gate.label}</div>
                    <div className="mt-1 truncate text-[10px] text-muted-foreground">{gate.category} / {gate.default_condition || gate.condition}</div>
                  </div>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", gate.enabled ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                    {gate.enabled ? "ON" : "OFF"}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <TimerReset className="h-4 w-4 text-primary" />
            Overrides and inheritance
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={createOverride} disabled={busy === "override"}>
              <TimerReset className="mr-1 h-3 w-3" />
              Create cost override
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={traceInheritance} disabled={busy === "trace"}>
              <GitBranch className="mr-1 h-3 w-3" />
              Trace inheritance
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={busy === "edge"}>
              <AlertTriangle className="mr-1 h-3 w-3" />
              Diagnose EC-C4
            </Button>
            <Button size="sm" className="h-8 text-xs" onClick={runAcceptance} disabled={busy === "acceptance"}>
              {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <TestTube2 className="mr-1 h-3 w-3" />}
              Run acceptance
            </Button>
          </div>
          <div className="mt-3 space-y-2">
            <MiniRow label="Active overrides" value={String((settings.overrides || []).filter((item: any) => item.status === "active").length)} />
            <MiniRow label="Inheritance traces" value={String((settings.inheritance_traces || []).length)} />
            <MiniRow label="Conflict count" value={String((snapshot?.conflicts || []).length)} />
            {trace ? <MiniRow label="Trace effective" value={`${trace.dimension_id}: ${trace.effective_level}`} /> : null}
            {diagnosis ? <MiniRow label="Edge runbook" value={diagnosis.case?.title || ""} /> : null}
          </div>
          {trace ? (
            <div className="mt-3 space-y-2 rounded-md border border-sylion-border bg-secondary/10 p-3">
              {trace.trace?.map((item: any, index: number) => (
                <div key={`${item.scope}-${index}`} className="flex items-center justify-between gap-3 text-xs">
                  <span className="truncate">{item.scope}</span>
                  <Badge variant="outline" className="h-5 text-[9px]">{item.level}</Badge>
                </div>
              ))}
            </div>
          ) : null}
        </Card>
      </div>

      <Card className="border-sylion-border bg-card p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <TestTube2 className="h-4 w-4 text-primary" />
              Phase 5 acceptance
            </h2>
            <div className="mt-1 text-[11px] text-muted-foreground">DoD: common, customization, goal-specific checks, hard blocks and soft warnings.</div>
          </div>
          <Badge variant="outline" className={cn("text-[10px]", acceptance.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
            {acceptance.dod?.counts?.checks_passed || 0}/{acceptance.dod?.counts?.checks_total || 0} checks
          </Badge>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
          {(acceptance.checks || []).map((check: any) => (
            <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <StatusIcon status={check.status} />
              <div className="min-w-0">
                <div className="truncate font-medium">{check.label}</div>
                <div className="mt-1 truncate text-[10px] text-muted-foreground">{check.evidence}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
