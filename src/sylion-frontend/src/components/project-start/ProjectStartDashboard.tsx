"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileCheck2,
  FolderKanban,
  GitBranch,
  Loader2,
  Play,
  RefreshCw,
  Rocket,
  ShieldCheck,
  SlidersHorizontal,
  TestTube2,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const phases = [
  { id: "16", label: "Utworzenie projektu", state: "READY_FOR_GOAL_DEFINITION", icon: Rocket },
  { id: "17", label: "Definicja celów", state: "READY_FOR_SCOPE_DEFINITION", icon: FileCheck2 },
  { id: "18", label: "Definicja zakresu", state: "READY_FOR_COUNCIL_CONFIG", icon: SlidersHorizontal },
  { id: "19", label: "Konfiguracja Rady", state: "READY_FOR_COUNCIL_CONVENING", icon: Users },
];

const initialForm = {
  creation_path: "idea",
  name: "Customer Y CRM",
  idea_text:
    "Zbuduj polski CRM klienta z płatnościami Stripe, fakturami KSeF, zgodnością RODO, interfejsem PL/EN i dostarczeniem finansowanym przez klienta.",
  customer_context: "Customer Y, 10-50 pracowników, jurysdykcja polska",
  deadline: "2026-06",
  budget_hint_eur: "3000",
  template_id: "polish_saas_payment",
  reference: "",
};

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

function fieldClass() {
  return "min-h-9 rounded-md border border-sylion-border bg-background px-3 py-2 text-xs outline-none transition-colors focus:border-primary/50";
}

const PROJECT_START_TEXT_LABELS: Record<string, string> = {
  READY_FOR_GOAL_DEFINITION: "gotowe do definicji celów",
  READY_FOR_SCOPE_DEFINITION: "gotowe do definicji zakresu",
  READY_FOR_COUNCIL_CONFIG: "gotowe do konfiguracji Rady",
  READY_FOR_COUNCIL_CONVENING: "gotowe do zwołania Rady",
  NO_PROJECT: "brak projektu",
  CLOSED: "zamknięty",
  idea: "pomysł",
  template: "szablon",
  fork: "fork",
  internal_app: "aplikacja wewnętrzna",
  mobile_approval: "mobilne akceptacje",
  polish_saas_payment: "polski SaaS z płatnościami",
  "Polish SaaS with payment": "Polski SaaS z płatnościami",
  "Internal CRM": "Wewnętrzny CRM",
  "Local AI cost monitor": "Lokalny monitor kosztów AI",
  "Funding assistant": "Asystent finansowania",
  "Mobile approval queue": "Mobilna kolejka akceptacji",
  "Local automation runtime": "Lokalne środowisko automatyzacji",
  "AEIS multi-domain local platform": "Lokalna platforma wielodomenowa AEIS",
  "Research experiment": "Eksperyment badawczy",
  "Edge/IoT integration": "Integracja Edge/IoT",
  "Workspace exists": "Obszar pracy istnieje",
  "phase 1 workspace ready": "faza 1: obszar pracy gotowy",
  "At least 1 LLM provider configured": "Skonfigurowano co najmniej 1 dostawcę LLM",
  "phase 2 provider catalog accepted": "faza 2: katalog dostawców zaakceptowany",
  "At least 1 environment available": "Dostępne co najmniej 1 środowisko",
  "phase 3 environment catalog accepted": "faza 3: katalog środowisk zaakceptowany",
  "Autonomy preset configured": "Preset autonomii skonfigurowany",
  "phase 5 autonomy accepted": "faza 5: autonomia zaakceptowana",
  "Guards active": "Strażnicy aktywni",
  "coherence/cost/security/quality/provenance accepted": "spójność/koszt/bezpieczeństwo/jakość/pochodzenie zaakceptowane",
  "Templates available": "Szablony dostępne",
  "phases 11-15 accepted": "fazy 11-15 zaakceptowane",
  "Budget reservation inside cap": "Rezerwacja budżetu mieści się w limicie",
  "cost policy inherited": "polityka kosztu odziedziczona",
  "Provenance audit chain ready": "Łańcuch audytu pochodzenia gotowy",
  "phase 10 provenance accepted": "faza 10: pochodzenie zaakceptowane",
  "Project entity created": "Encja projektu utworzona",
  "D-level classified": "Poziom D sklasyfikowany",
  "Templates assigned": "Szablony przypisane",
  "Resources reserved": "Zasoby zarezerwowane",
  "Pre-flight checks passed": "Kontrole przedstartowe zaliczone",
  "all pre-flight checks": "wszystkie kontrole przedstartowe",
  "Audit chain genesis entry": "Pierwszy wpis łańcucha audytu",
  project_inception: "utworzenie projektu",
  "budget/env/LLM quota": "budżet/środowisko/kwota LLM",
  idea_analysis: "analiza pomysłu",
  mandatory: "wymagana",
  role: "rola",
  ready: "gotowa",
};

function plProjectStartText(value: unknown): string {
  const text = String(value ?? "").trim();
  if (!text) return "-";
  if (PROJECT_START_TEXT_LABELS[text]) return PROJECT_START_TEXT_LABELS[text];
  if (text.startsWith("Project state: ")) {
    return `Stan projektu: ${plProjectStartText(text.slice("Project state: ".length))}`;
  }
  return text.replace(/_/g, " ");
}

function toCreatePayload(form: typeof initialForm) {
  return {
    ...form,
    budget_hint_eur: form.budget_hint_eur.trim() ? Number(form.budget_hint_eur) : null,
    reference: form.reference.trim() || null,
  };
}

export function ProjectStartDashboard() {
  const { data: health, loading: healthLoading } = useHealth();
  const backendLive = health.status === "ok";
  const backendPending = healthLoading || health.status === "unknown";
  const [overview, setOverview] = useState<any | null>(null);
  const [project, setProject] = useState<any | null>(null);
  const [acceptance, setAcceptance] = useState<Record<string, any>>({});
  const [edgeCases, setEdgeCases] = useState<any | null>(null);
  const [preview, setPreview] = useState<any | null>(null);
  const [diagnosis, setDiagnosis] = useState<any | null>(null);
  const [activePhase, setActivePhase] = useState("16");
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const projectId = project?.project_id as string | undefined;
  const phaseRows = overview?.phases || [];
  const groupComplete = Boolean(overview?.group?.complete);
  const currentAcceptance = acceptance[activePhase] || {};
  const currentPhase = phases.find((item) => item.id === activePhase) || phases[0];
  const CurrentPhaseIcon = currentPhase.icon;
  const activeEdgeCases = edgeCases?.phases?.[activePhase]?.edge_cases || [];
  const projectList = overview?.projects || [];
  const phaseReady = Boolean(currentAcceptance.accepted);
  const hardBlocks = currentAcceptance.hard_blocks?.length || 0;
  const auditEntries = project?.audit_chain?.length || currentAcceptance.audit_chain?.entries || 0;
  const stateLabel = plProjectStartText(project?.state || "NO_PROJECT");

  const load = useCallback(async () => {
    if (!backendLive) {
      if (backendPending) {
        setStatus("Łączenie z backendem...");
        setLoading(false);
        return;
      }
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
      const overviewData = await api.getProjectStartOverview();
      setOverview(overviewData);
      const active = overviewData.active_project;
      if (active?.project_id) {
        const projectData = await api.getProjectStartProject(active.project_id);
        setProject(projectData.project);
        setAcceptance(projectData.acceptance || {});
        try {
          const edgeData = await api.getProjectStartEdgeCases(active.project_id);
          setEdgeCases(edgeData);
        } catch {
          setEdgeCases(null);
        }
      } else {
        setProject(null);
        setAcceptance({});
        setEdgeCases(null);
      }
      setStatus("");
    } catch (err: any) {
      setStatus(`Błąd startu projektu: ${err.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive, backendPending]);

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

  const updateForm = (key: keyof typeof initialForm, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const previewProject = () =>
    withBusy("preview", async () => {
      const data = await api.previewProjectStart(toCreatePayload(form));
      setPreview(data.analysis);
      setStatus(`Podgląd gotowy: ${data.analysis.d_level_label} / ${data.analysis.project_type}.`);
    });

  const createProject = () =>
    withBusy("create", async () => {
      const data = await api.createProjectStartProject(toCreatePayload(form));
      setProject(data.project);
      setAcceptance({ ...acceptance, "16": data.acceptance });
      setPreview(data.project.classification);
      setActivePhase("16");
      setStatus(`Projekt ${data.project.project_id} utworzony.`);
    });

  const ensureProject = () => {
    if (!projectId) {
      setStatus("Najpierw utwórz projekt.");
      return false;
    }
    return true;
  };

  const applyPhase17 = () =>
    withBusy("phase17", async () => {
      if (!ensureProject()) return;
      const id = projectId as string;
      const data = await api.applyProjectStartGoalDefaults(id, { operator_id: "operator" });
      setProject(data.project);
      setAcceptance({ ...acceptance, "17": data.acceptance });
      setActivePhase("17");
      setStatus("Domyślne cele fazy 17 zastosowane.");
    });

  const applyPhase18 = () =>
    withBusy("phase18", async () => {
      if (!ensureProject()) return;
      const id = projectId as string;
      const data = await api.applyProjectStartScopeDefaults(id, { operator_id: "operator" });
      setProject(data.project);
      setAcceptance({ ...acceptance, "18": data.acceptance });
      setActivePhase("18");
      setStatus("Domyślny zakres fazy 18 zastosowany.");
    });

  const applyPhase19 = () =>
    withBusy("phase19", async () => {
      if (!ensureProject()) return;
      const id = projectId as string;
      const data = await api.applyProjectStartCouncilDefaults(id, { operator_id: "operator" });
      setProject(data.project);
      setAcceptance({ ...acceptance, "19": data.acceptance });
      setActivePhase("19");
      setStatus("Szkic Rady dla fazy 19 przygotowany.");
    });

  const approvePhase19 = () =>
    withBusy("approve19", async () => {
      if (!ensureProject()) return;
      const id = projectId as string;
      const data = await api.approveProjectStartCouncil(id, {
        approved: true,
        operator_id: "operator",
        notes: "Akceptacja z dashboardu do zwołania fazy 20.",
      });
      setProject(data.project);
      setAcceptance({ ...acceptance, "19": data.acceptance });
      setActivePhase("19");
      setStatus("Gotowość Rady zatwierdzona.");
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      if (!ensureProject()) return;
      const id = projectId as string;
      const data = await api.runProjectStartAcceptanceTest(id, activePhase);
      setAcceptance({ ...acceptance, [activePhase]: data });
      setStatus(data.accepted ? `Faza ${activePhase} zaliczona.` : `Faza ${activePhase}: blokady twarde ${data.hard_blocks?.length || 0}.`);
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      if (!ensureProject()) return;
      const caseId = activeEdgeCases[0]?.id || "EC-A1";
      const id = projectId as string;
      const data = await api.diagnoseProjectStartEdgeCase(id, {
        phase: activePhase,
        case_id: caseId,
        context: { source: "project_start_dashboard", state: project?.state || "unknown" },
      });
      setDiagnosis(data);
      setStatus(`${caseId}: diagnoza gotowa.`);
    });

  const visibleGoals = useMemo(() => project?.goals?.primary_goals || [], [project]);
  const visibleScope = useMemo(() => project?.scope?.in_scope || [], [project]);
  const visibleCouncil = useMemo(() => project?.council?.roles || [], [project]);

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Start projektu - Fazy 16-19</h1>
            <Badge variant="outline" className={cn("text-[10px]", groupComplete ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {groupComplete ? "GRUPA B GOTOWA" : "GRUPA B AKTYWNA"}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", phaseReady ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {phaseReady ? `FAZA ${activePhase} GOTOWA` : `FAZA ${activePhase} AKTYWNA`}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : backendPending ? "border-sylion-amber/30 text-sylion-amber" : "border-sylion-red/30 text-sylion-red")}>
            {backendLive ? "BACKEND DZIAŁA" : backendPending ? "ŁĄCZENIE Z BACKENDEM" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
          </div>
          <div className="mt-1 max-w-4xl text-xs text-muted-foreground">
            Deterministyczne przyjęcie projektu, cele, zakres i początkowa konfiguracja Rady z użyciem faz 1-15 jako odziedziczonej konfiguracji obszaru pracy.
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3 w-3", loading && "animate-spin")} />
            Odśwież
          </Button>
          <Button size="sm" className="h-9 text-xs" onClick={runAcceptance} disabled={!projectId || busy === "acceptance"}>
            {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <TestTube2 className="mr-1 h-3 w-3" />}
            Uruchom akceptację
          </Button>
        </div>
      </div>

      {status ? <div className="rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs text-muted-foreground">{status}</div> : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(360px,480px)_minmax(0,1fr)]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <FolderKanban className="h-4 w-4 text-primary" />
              Tworzenie projektu
            </h2>
            <Badge variant="outline" className="h-6 text-[10px]">{stateLabel}</Badge>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3">
            <label className="grid gap-1 text-xs">
              <span className="font-medium">Ścieżka utworzenia</span>
              <select
                aria-label="Creation path"
                className={fieldClass()}
                value={form.creation_path}
                onChange={(event) => updateForm("creation_path", event.target.value)}
              >
                <option value="idea">pomysł</option>
                <option value="template">szablon</option>
                <option value="fork">fork</option>
              </select>
            </label>
            <label className="grid gap-1 text-xs">
              <span className="font-medium">Nazwa projektu</span>
              <input aria-label="Nazwa projektu" className={fieldClass()} value={form.name} onChange={(event) => updateForm("name", event.target.value)} />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="font-medium">Opis pomysłu</span>
              <textarea
                aria-label="Opis pomysłu"
                className={cn(fieldClass(), "min-h-[112px] resize-y")}
                value={form.idea_text}
                onChange={(event) => updateForm("idea_text", event.target.value)}
              />
            </label>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <label className="grid gap-1 text-xs md:col-span-3">
                <span className="font-medium">Kontekst klienta</span>
                <input aria-label="Customer context" className={fieldClass()} value={form.customer_context} onChange={(event) => updateForm("customer_context", event.target.value)} />
              </label>
              <label className="grid gap-1 text-xs">
                <span className="font-medium">Termin</span>
                <input aria-label="Termin" className={fieldClass()} value={form.deadline} onChange={(event) => updateForm("deadline", event.target.value)} />
              </label>
              <label className="grid gap-1 text-xs">
                <span className="font-medium">Budżet EUR</span>
                <input aria-label="Budżet EUR" className={fieldClass()} value={form.budget_hint_eur} onChange={(event) => updateForm("budget_hint_eur", event.target.value)} />
              </label>
              <label className="grid gap-1 text-xs">
                <span className="font-medium">Szablon</span>
                <select aria-label="Szablon" className={fieldClass()} value={form.template_id} onChange={(event) => updateForm("template_id", event.target.value)}>
                  {(overview?.templates || []).map((template: any) => (
                    <option key={template.id} value={template.id}>{plProjectStartText(template.name)}</option>
                  ))}
                  {!overview?.templates?.length ? <option value="polish_saas_payment">Polski SaaS z płatnościami</option> : null}
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" size="sm" className="h-9 text-xs" onClick={previewProject} disabled={!backendLive || busy === "preview"}>
                {busy === "preview" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Play className="mr-1 h-3 w-3" />}
                Pokaż analizę
              </Button>
              <Button size="sm" className="h-9 text-xs" onClick={createProject} disabled={!backendLive || busy === "create"}>
                {busy === "create" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Rocket className="mr-1 h-3 w-3" />}
                Utwórz projekt
              </Button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            {phases.map((item) => {
              const Icon = item.icon;
              const row = phaseRows.find((phaseRow: any) => phaseRow.phase === item.id);
              const active = activePhase === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActivePhase(item.id)}
                  className={cn(
                    "rounded-md border p-3 text-left transition-colors",
                    active ? "border-primary/40 bg-primary/10" : "border-sylion-border bg-card hover:border-primary/30",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <Icon className={cn("h-4 w-4", active ? "text-primary" : "text-muted-foreground")} />
                    <Badge variant="outline" className={cn("h-5 text-[9px]", row?.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
                      P{item.id}
                    </Badge>
                  </div>
                  <div className="mt-2 text-xs font-semibold">{item.label}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {row ? `${row.accepted ? "zaliczona" : `${row.hard_blocks || 0} blokad`} / ${row.edge_cases} PP` : plProjectStartText(item.state)}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Metric label="Projekty" value={projectList.length} tone={projectList.length ? "green" : "amber"} />
            <Metric label="Poziom D" value={project?.classification?.d_level_label || preview?.d_level_label || "-"} tone={project?.classification?.d_level >= 4 ? "amber" : "green"} />
            <Metric label="Przypadki problemowe" value={overview?.group?.edge_cases || 66} tone="green" />
            <Metric label="Blokady twarde" value={hardBlocks} tone={hardBlocks ? "red" : "green"} />
            <Metric label="Wpisy audytu" value={auditEntries} tone={auditEntries ? "green" : "amber"} />
          </div>

          <Card className="border-sylion-border bg-card p-4">
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <GitBranch className="h-4 w-4 text-primary" />
                  Aktywny stan projektu
                </h2>
                <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                  <MiniRow label="Projekt" value={project?.name || "brak"} />
                  <MiniRow label="ID" value={project?.project_id || "nie utworzono"} />
                  <MiniRow label="Typ" value={plProjectStartText(project?.classification?.project_type || preview?.project_type || "-")} />
                  <MiniRow label="Domena" value={plProjectStartText(project?.classification?.domain || preview?.domain || "-")} />
                  <MiniRow label="Rezerwa zasobów" value={project?.resources?.llm_budget_reserved_usd ? `$${project.resources.llm_budget_reserved_usd}` : "-"} />
                  <MiniRow label="Katalog projektu" value={project?.shell?.root || "-"} />
                </div>
              </div>
              <div>
                <h3 className="text-xs font-semibold uppercase text-muted-foreground">Akcje operatora</h3>
                <div className="mt-3 grid grid-cols-1 gap-2">
                  <Button variant="outline" size="sm" className="h-8 text-xs" onClick={applyPhase17} disabled={!projectId || busy === "phase17"}>
                    <FileCheck2 className="mr-1 h-3 w-3" />
                    Zastosuj domyślne fazy 17
                  </Button>
                  <Button variant="outline" size="sm" className="h-8 text-xs" onClick={applyPhase18} disabled={!projectId || busy === "phase18"}>
                    <SlidersHorizontal className="mr-1 h-3 w-3" />
                    Zastosuj domyślne fazy 18
                  </Button>
                  <Button variant="outline" size="sm" className="h-8 text-xs" onClick={applyPhase19} disabled={!projectId || busy === "phase19"}>
                    <Users className="mr-1 h-3 w-3" />
                    Zastosuj domyślne fazy 19
                  </Button>
                  <Button variant="outline" size="sm" className="h-8 text-xs" onClick={approvePhase19} disabled={!projectId || busy === "approve19"}>
                    <ShieldCheck className="mr-1 h-3 w-3" />
                    Zatwierdź gotowość
                  </Button>
                  <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={!projectId || busy === "edge"}>
                    <AlertTriangle className="mr-1 h-3 w-3" />
                    Diagnozuj przypadek problemowy
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <CurrentPhaseIcon className="h-4 w-4 text-primary" />
            Faza {activePhase}: {currentPhase.label}
          </h2>
          <div className="mt-3 grid max-h-[520px] grid-cols-1 gap-2 overflow-auto pr-1 md:grid-cols-2 xl:grid-cols-3">
            {activePhase === "16"
              ? (project?.preflight_checks || []).map((item: any) => (
                  <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                    <div className="flex items-start gap-2">
                      <StatusIcon status={item.status} />
                      <div className="min-w-0">
                        <div className="truncate font-medium">{plProjectStartText(item.label)}</div>
                        <div className="mt-1 truncate text-[10px] text-muted-foreground">{plProjectStartText(item.evidence)}</div>
                      </div>
                    </div>
                  </div>
                ))
              : null}
            {activePhase === "17"
              ? visibleGoals.map((goal: any) => (
                  <div key={goal.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="truncate font-medium">{plProjectStartText(goal.title)}</div>
                      <Badge variant="outline" className="h-5 text-[9px]">{goal.priority}</Badge>
                    </div>
                    <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{(goal.acceptance_criteria || []).slice(0, 2).map(plProjectStartText).join(", ")}</div>
                  </div>
                ))
              : null}
            {activePhase === "18"
              ? visibleScope.slice(0, 12).map((item: any) => (
                  <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                    <div className="font-medium">{plProjectStartText(item.title)}</div>
                    <div className="mt-1 text-[10px] text-muted-foreground">{item.id}</div>
                  </div>
                ))
              : null}
            {activePhase === "19"
              ? visibleCouncil.map((item: any) => (
                  <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="truncate font-medium">{plProjectStartText(item.role)}</div>
                      <Badge variant="outline" className="h-5 text-[9px]">{item.mandatory ? "wymagana" : "rola"}</Badge>
                    </div>
                    <div className="mt-1 truncate text-[10px] text-muted-foreground">{item.model_id}</div>
                  </div>
                ))
              : null}
            {!projectId ? (
              <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
                Utwórz pierwszy projekt, aby wypełnić dowody fazy.
              </div>
            ) : null}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <TestTube2 className="h-4 w-4 text-primary" />
            Akceptacja fazy {activePhase}
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <MiniRow label="Wymagane" value={`${currentAcceptance.dod?.passed_required || 0}/${currentAcceptance.dod?.required || 0}`} />
            <MiniRow label="Blokady twarde" value={hardBlocks} />
            <MiniRow label="Wpisy audytu" value={currentAcceptance.audit_chain?.entries || auditEntries} />
            {diagnosis ? <MiniRow label="Diagnoza przypadku" value={diagnosis.case?.id || "gotowa"} /> : null}
          </div>
          <div className="mt-3 max-h-[360px] space-y-2 overflow-auto pr-1">
            {(currentAcceptance.checks || []).map((check: any) => (
              <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <StatusIcon status={check.status} />
                <div className="min-w-0">
                  <div className="truncate font-medium">{plProjectStartText(check.label)}</div>
                  <div className="mt-1 truncate text-[10px] text-muted-foreground">{plProjectStartText(check.evidence)}</div>
                </div>
              </div>
            ))}
            {!currentAcceptance.checks?.length ? (
              <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
                Brak migawki akceptacji.
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <Card className="border-sylion-border bg-card p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <AlertTriangle className="h-4 w-4 text-primary" />
          Faza {activePhase}: przypadki problemowe
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
          {activeEdgeCases.slice(0, 10).map((item: any) => (
            <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.id}</span>
                <Badge variant="outline" className="h-5 text-[9px]">{plProjectStartText(item.category)}</Badge>
              </div>
              <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{plProjectStartText(item.title)}</div>
            </div>
          ))}
          {!activeEdgeCases.length ? (
            <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
              Przypadki problemowe pojawią się po utworzeniu pierwszego projektu.
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
