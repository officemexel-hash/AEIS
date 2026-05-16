"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileSearch,
  GitBranch,
  Layers3,
  Loader2,
  PackageCheck,
  Play,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  TestTube2,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";

const phases = [
  { id: "skills", phase: "11", label: "Biblioteka skills", icon: Wrench },
  { id: "council", phase: "12", label: "Szablony Rady", icon: GitBranch },
  { id: "test-strategy", phase: "13", label: "Strategia testów", icon: TestTube2 },
  { id: "deployment", phase: "14", label: "Wdrożenie", icon: PackageCheck },
  { id: "cost-policies", phase: "15", label: "Polityki kosztów", icon: ShieldCheck },
];

function tplText(value: unknown): string {
  const raw = String(value ?? "").trim();
  const labels: Record<string, string> = {
    baseline: "bazowe",
    loading: "ładowanie",
    ready: "gotowe",
    artifacts: "artefakty",
    operator_custom: "własne operatora",
    "Skills Library": "Biblioteka skills",
    "Council Templates": "Szablony Rady",
    "Test Strategy": "Strategia testów",
    Deployment: "Wdrożenie",
    "Cost Policies": "Polityki kosztów",
    "Skills Library plus Council, Test Strategy, Deployment and Cost Policy templates before Phase 16 project inception.": "Biblioteka skills oraz szablony Rady, strategii testów, wdrożenia i polityk kosztowych przed rozpoczęciem projektu w Fazie 16.",
  };
  const direct = labels[raw];
  if (direct) return direct;
  return raw
    .replace(/Skills Library/g, "Biblioteka skills")
    .replace(/Council Templates/g, "Szablony Rady")
    .replace(/Test Strategy/g, "Strategia testów")
    .replace(/Deployment/g, "Wdrożenie")
    .replace(/Cost Policies/g, "Polityki kosztów")
    .replace(/Generate/g, "Wygeneruj")
    .replace(/from application/g, "z aplikacji")
    .replace(/baseline system skills/g, "bazowych skills systemowych")
    .replace(/creation workflows/g, "workflow tworzenia")
    .replace(/discovery/g, "odkrywanie")
    .replace(/versioning/g, "wersjonowanie")
    .replace(/marketplace settings/g, "ustawieńia marketplace")
    .replace(/skill types/g, "typy skills")
    .replace(/_/g, " ");
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

export function TemplatesSetupDashboard() {
  const { data: health, loading: healthLoading } = useHealth();
  const backendLive = health.status === "ok";
  const backendPending = healthLoading || health.status === "unknown";
  const [activePhase, setActivePhase] = useState("skills");
  const [overview, setOverview] = useState<any | null>(null);
  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [diagnosis, setDiagnosis] = useState<any | null>(null);
  const activeDefinition = phases.find((item) => item.id === activePhase) || phases[0];

  const selectPhase = (phaseId: string) => {
    if (phaseId === activePhase) return;
    setActivePhase(phaseId);
    setSnapshot(null);
    setDiagnosis(null);
    setStatus("");
    setLoading(true);
  };

  const load = useCallback(async () => {
    if (!backendLive) {
      setOverview(null);
      setSnapshot(null);
      setLoading(false);
      setStatus(backendPending ? "Łączenie z backendem..." : "Backend niedostępny.");
      return;
    }
    setLoading(true);
    try {
      const [overviewData, phaseData] = await Promise.all([
        api.getTemplatesSetupOverview(),
        api.getTemplatesSetupPhase(activePhase, "apps_internal"),
      ]);
      setOverview(overviewData);
      setSnapshot(phaseData);
      setStatus("");
    } catch (err: any) {
      setStatus(`Błąd konfiguracji szablonów: ${err.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [activePhase, backendLive, backendPending]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const settings = snapshot?.settings || {};
  const templates = snapshot?.templates || {};
  const catalog = templates.catalog || {};
  const acceptance = snapshot?.acceptance || {};
  const artifacts = useMemo(() => Object.values(settings.artifacts || {}) as any[], [settings.artifacts]);
  const enabledArtifacts = artifacts.filter((artifact: any) => artifact.enabled);
  const customArtifacts = settings.custom_artifacts || [];
  const phase = activeDefinition.phase;
  const phaseReady = Boolean(acceptance.accepted && acceptance.audit_chain?.[`phase_${phase}_complete`]);
  const edgeCount = (templates.edge_cases || []).length;
  const baselineTarget = catalog.baseline_target || artifacts.length;
  const overviewRows = overview?.phases || [];
  const groupComplete = Boolean(overview?.group?.complete);

  const withBusy = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setStatus("");
    try {
      await action();
      const [overviewData, phaseData] = await Promise.all([
        api.getTemplatesSetupOverview(),
        api.getTemplatesSetupPhase(activePhase, "apps_internal"),
      ]);
      setOverview(overviewData);
      setSnapshot(phaseData);
    } catch (err: any) {
      setStatus(err.message || String(err));
    } finally {
      setBusy("");
    }
  };

  const applyDefaults = () =>
    withBusy("defaults", async () => {
      const data = await api.applyTemplatesSetupDefaults(activePhase, { operator_id: "operator", goal: "apps_internal" });
      setSnapshot(data);
      setStatus(`Domyślne ustawieńia fazy ${phase} zastosowane.`);
    });

  const reviewArtifacts = () =>
    withBusy("review", async () => {
      const data = await api.reviewTemplatesSetupArtifacts(activePhase, {
        accepted_artifact_ids: artifacts.map((artifact: any) => artifact.id),
        disabled_artifact_ids: [],
      });
      setSnapshot(data.snapshot);
      setStatus(`Bazowe artefakty fazy ${phase} sprawdźone.`);
    });

  const createCustomArtifact = () =>
    withBusy("custom", async () => {
      const data = await api.createTemplatesSetupCustomArtifact(activePhase, {
        name: `${catalog.title || "Szablon"} własna próbka`,
        category: "operator_custom",
        notes: "Utworzone z dashboardu konfiguracji szablonów.",
      });
      setSnapshot(data.snapshot);
      setStatus(`Własny artefakt fazy ${phase} utworzony.`);
    });

  const runSimulation = () =>
    withBusy("simulate", async () => {
      const data = await api.simulateTemplatesSetupPhase(activePhase, {
        project_type: activePhase === "cost-policies" ? "customer_funded" : "public_saas",
        d_level: activePhase === "council" ? 4 : 3,
        customer_specific: activePhase === "cost-policies",
      });
      setSnapshot(data.snapshot);
      setStatus(`Przykładowe mapowanie fazy ${phase} gotowe.`);
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      const caseId = (templates.edge_cases || [])[0]?.id || "EC-A1";
      const data = await api.diagnoseTemplatesSetupEdgeCase(activePhase, {
        case_id: caseId,
        context: { source: "templates_setup_dashboard", active_phase: activePhase },
      });
      setDiagnosis(data);
      setStatus(`Diagnoza ${caseId} gotowa.`);
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      const data = await api.runTemplatesSetupAcceptanceTest(activePhase);
      setStatus(data.accepted ? `Faza ${phase} zaakceptowana.` : `Faza ${phase}, twarde blokady: ${data.hard_blocks?.length || 0}.`);
    });

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              Konfiguracja szablonów - Fazy 11-15
              <HelpTip text="Warstwy W9/W10/W14: tutaj AEIS przygotowuje biblioteki skills, szablony Rady, strategię testów, szablony wdrożenia i polityki kosztów przed startem realnego projektu." />
            </h1>
            <Badge variant="outline" className={cn("text-[10px]", groupComplete ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {groupComplete ? "GRUPA A2 GOTOWA" : "GRUPA A2 AKTYWNA"}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", phaseReady ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {phaseReady ? `FAZA ${phase} GOTOWA` : `FAZA ${phase} AKTYWNA`}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
              {backendLive ? "BACKEND DZIAŁA" : backendPending ? "ŁĄCZENIE Z BACKENDEM" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
          </div>
          <div className="mt-1 max-w-4xl text-xs text-muted-foreground">
            Biblioteka skills oraz szablony Rady, strategii testów, wdrożenia i polityk kosztowych przed rozpoczęciem projektu w Fazie 16.
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3 w-3", loading && "animate-spin")} />
            Odśwież
          </Button>
          <Button size="sm" className="h-9 text-xs" onClick={applyDefaults} disabled={!backendLive || busy === "defaults"}>
            {busy === "defaults" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ShieldCheck className="mr-1 h-3 w-3" />}
            Zastosuj domyślne fazy {phase}
          </Button>
        </div>
      </div>

      {status ? <div className="rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs text-muted-foreground">{status}</div> : null}

      <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
        {phases.map((item) => {
          const Icon = item.icon;
          const row = overviewRows.find((phaseRow: any) => phaseRow.phase_id === item.id);
          const active = activePhase === item.id;
          return (
            <button
              key={item.id}
              onClick={() => selectPhase(item.id)}
              className={cn(
                "rounded-md border p-3 text-left transition-colors",
                active ? "border-primary/40 bg-primary/10" : "border-sylion-border bg-card hover:border-primary/30",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <Icon className={cn("h-4 w-4", active ? "text-primary" : "text-muted-foreground")} />
                <Badge variant="outline" className={cn("h-5 text-[9px]", row?.complete ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
                  P{item.phase}
                </Badge>
              </div>
              <div className="mt-2 text-xs font-semibold">{item.label}</div>
              <div className="mt-1 text-[10px] text-muted-foreground">
                {row ? `${row.enabled_artifacts}/${row.baseline_target} bazowe / ${row.edge_cases} PB` : "ładowanie"}
              </div>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Metric label="Włączone bazowe" value={`${enabledArtifacts.length}/${baselineTarget}`} tone={enabledArtifacts.length >= baselineTarget ? "green" : "amber"} />
        <Metric label="Artefakty własne" value={customArtifacts.length} tone={customArtifacts.length ? "green" : "default"} />
        <Metric label="Przypadki brzegowe" value={edgeCount} tone={edgeCount >= 15 ? "green" : "amber"} />
        <Metric label="Wymagane DoD" value={`${acceptance.dod?.passed_required || 0}/${acceptance.dod?.required || 0}`} tone={acceptance.dod?.passed_required === acceptance.dod?.required ? "green" : "amber"} />
        <Metric label="Twarde blokady" value={acceptance.hard_blocks?.length || 0} tone={acceptance.hard_blocks?.length ? "red" : "green"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Layers3 className="h-4 w-4 text-primary" />
                {tplText(catalog.route_title || "Konfiguracja fazy")}
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">{tplText(catalog.summary || "Bazowe artefakty fazy i zachowanie dziedziczenia.")}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={reviewArtifacts} disabled={busy === "review"}>
                <FileSearch className="mr-1 h-3 w-3" />
                Sprawdź bazowe artefakty
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={createCustomArtifact} disabled={busy === "custom"}>
                <SlidersHorizontal className="mr-1 h-3 w-3" />
                Utwórz artefakt własny
              </Button>
            </div>
          </div>
          <div className="mt-3 grid max-h-[500px] grid-cols-1 gap-2 overflow-auto pr-1 lg:grid-cols-2">
            {artifacts.map((artifact: any) => (
              <div key={artifact.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{tplText(artifact.name)}</div>
                    <div className="mt-1 truncate text-[10px] text-muted-foreground">{artifact.id}</div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Badge variant="outline" className="h-5 text-[9px]">{tplText(artifact.category || artifact.for || "baseline")}</Badge>
                    <Badge variant="outline" className={cn("h-5 text-[9px]", artifact.enabled ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                      {artifact.enabled ? "WŁ." : "WYŁ."}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Play className="h-4 w-4 text-primary" />
            Akcje operatora
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={runSimulation} disabled={busy === "simulate"}>
              <Play className="mr-1 h-3 w-3" />
              Uruchom przykładowe mapowanie
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={busy === "edge"}>
              <AlertTriangle className="mr-1 h-3 w-3" />
              Diagnozuj przypadek brzegowy
            </Button>
            <Button size="sm" className="h-8 text-xs" onClick={runAcceptance} disabled={busy === "acceptance"}>
              {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <TestTube2 className="mr-1 h-3 w-3" />}
              Uruchom akceptację
            </Button>
          </div>
          <div className="mt-3 space-y-2">
            <MiniRow label="Faza" value={`Faza ${phase}`} />
            <MiniRow label="Typ artefaktu" value={catalog.artifact_label || "artefakty"} />
            <MiniRow label="Symulacje" value={`${settings.simulations?.length || 0}`} />
            {diagnosis ? <MiniRow label="Diagnoza przypadku" value={diagnosis.case?.id || "gotowa"} /> : null}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Możliwości i dziedziczenie
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(templates.capabilities || []).map((capability: any) => (
              <div key={capability.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="font-medium">{capability.label}</div>
                <div className="mt-2 line-clamp-3 text-[10px] text-muted-foreground">{(capability.items || []).join(", ")}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <TestTube2 className="h-4 w-4 text-primary" />
            Akceptacja fazy {phase}
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <MiniRow label="Wymagane" value={`${acceptance.dod?.passed_required || 0}/${acceptance.dod?.required || 0}`} />
            <MiniRow label="Wszystkie kontrole" value={`${acceptance.dod?.passed_all || 0}/${acceptance.dod?.all || 0}`} />
            <MiniRow label="Wpisy audytu" value={`${acceptance.audit_chain?.entries || 0}`} />
          </div>
          <div className="mt-3 max-h-[360px] space-y-2 overflow-auto pr-1">
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

      <Card className="border-sylion-border bg-card p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Clock3 className="h-4 w-4 text-primary" />
          Przypadki brzegowe
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
          {(templates.edge_cases || []).slice(0, 10).map((item: any) => (
            <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.id}</span>
                <Badge variant="outline" className="h-5 text-[9px]">{item.category}</Badge>
              </div>
              <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{item.title}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
