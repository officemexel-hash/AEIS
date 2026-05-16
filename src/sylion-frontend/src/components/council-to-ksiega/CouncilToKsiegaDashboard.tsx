"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Clock3,
  FileCheck,
  FileLock,
  GitBranch,
  Loader2,
  RefreshCw,
  Settings2,
  ShieldCheck,
  TestTube2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const phases = [
  { id: "20", label: "Zwołanie Rady", state: "READY_FOR_INITIAL_VERDICTS", icon: Users },
  { id: "21", label: "Pierwsze werdykty", state: "READY_FOR_DELIBERATION_ROUNDS", icon: FileCheck },
  { id: "22", label: "Rundy deliberacji", state: "READY_FOR_CONSOLIDATION", icon: GitBranch },
  { id: "23", label: "Konsolidacja", state: "READY_FOR_BOOK_GENERATION", icon: ShieldCheck },
  { id: "24", label: "Księga Rady", state: "READY_FOR_KSIEGA_GENERATION", icon: BookOpen },
  { id: "25", label: "Finalizacja Księgi", state: "READY_FOR_PLANNING", icon: FileLock },
];

const roleLabels: Record<string, string> = {
  "Adversarial Critic": "Krytyk adwersarialny",
  Chair: "Przewodniczący",
  "Compliance GDPR": "Zgodność RODO",
  "Compliance KSeF": "Zgodność KSeF",
  "Cost Sentinel": "Strażnik kosztów",
  Critic: "Krytyk",
  "Deployment Lead": "Lider wdrożenia",
  "Funding Specialist": "Specjalista ds. finansowania",
  "HumanGate Sentinel": "Strażnik HumanGate",
  "Local Verifier": "Weryfikator lokalny",
  "Memory Steward": "Opiekun pamięci",
  "Mobile Operator": "Operator mobilny",
  "Observability Sentinel": "Strażnik obserwowalności",
  "Payment Specialist": "Specjalista płatności",
  Planner: "Planista",
  QA: "QA",
  "Runtime Operator": "Operator runtime",
  Security: "Bezpieczeństwo",
  UX: "UX",
};

const statusLabels: Record<string, string> = {
  approved: "zatwierdzone",
  pass: "zaliczone",
  ready: "gotowe",
  reject: "odrzucone",
  rejected: "odrzucone",
};

const stateLabels: Record<string, string> = {
  NO_ACTIVE_PROJECT: "brak aktywnego projektu",
  READY_FOR_BOOK_GENERATION: "gotowe do Księgi Rady",
  READY_FOR_CONSOLIDATION: "gotowe do konsolidacji",
  READY_FOR_COUNCIL_CONVENING: "gotowe do zwołania Rady",
  READY_FOR_INITIAL_VERDICTS: "gotowe do pierwszych werdyktów",
  READY_FOR_KSIEGA_GENERATION: "gotowe do generowania Księgi",
  READY_FOR_PLANNING: "gotowe do planowania",
};

const edgeCategoryLabels: Record<string, string> = {
  aggregation: "agregacja",
  awakening: "uruchamianie ról",
  briefing: "briefing",
  conflict_resolution: "rozstrzyganie konfliktów",
  cost: "koszt",
  generation: "generowanie",
  lock_workflow: "blokada Księgi",
  operator: "operator",
  operator_approval: "akceptacja operatora",
  operator_review: "przegląd operatora",
  quality: "jakość",
  questions: "pytania",
  readiness: "gotowość",
  recovery: "odtwarzanie",
  round_mechanics: "mechanika rund",
};

const edgeTitleLabels: Record<string, string> = {
  "Audit chain corruption": "Uszkodzenie łańcucha audytu",
  "Audit chain does not match Book": "Łańcuch audytu nie zgadza się z Księgą Rady",
  "Audit chain integrity issue": "Problem integralności łańcucha audytu",
  "Audit chain mismatch with Księga": "Łańcuch audytu nie zgadza się z Księgą",
  "Audit signature mismatch": "Niezgodność podpisu audytu",
  "Book file corruption": "Uszkodzenie pliku Księgi Rady",
  "Briefing missing section": "W briefingu brakuje sekcji",
  "Briefing too large": "Briefing jest zbyt duży",
  "Coherence check fails": "Kontrola spójności nie przechodzi",
  "Compliance gaps discovered": "Wykryto luki zgodności",
  "Context window exhausted": "Wyczerpane okno kontekstu",
  "Contradictory stance": "Sprzeczne stanowisko",
  "Cost budget exhausted mid-round": "Budżet kosztów wyczerpany w trakcie rundy",
  "Cost estimate missing": "Brakuje estymacji kosztów",
  "Cost reconciliation discrepancy": "Niezgodność rozliczenia kosztów",
  "Customer-facing version leaks internal info": "Wersja dla klienta ujawnia informacje wewnętrzne",
  "Customer changes mind during finalization": "Klient zmienia decyzję podczas finalizacji",
  "Customer disagrees post-Księga": "Klient zgłasza sprzeciw po Księdze",
  "Customer wants Book early": "Klient chce Księgę Rady wcześniej",
  "Customer wants pre-lock review": "Klient chce przeglądu przed blokadą",
  "Decision summary inaccurate": "Podsumowanie decyzji jest niedokładne",
  "Duplicate verdict submitted": "Zduplikowany werdykt",
  "Format issues": "Problemy z formatem",
  "Generation cost overrun": "Przekroczenie kosztu generowania",
  "Generation fails mid-section": "Generowanie pada w środku sekcji",
  "Generation hallucinations": "Halucynacje w generowaniu",
  "Generation timeout for complex project": "Timeout generowania dla złożonego projektu",
  "Generated content shallow": "Wygenerowana treść jest zbyt płytka",
  "Hard gate timeout": "Timeout twardej bramki",
  "Hard gate unavailable": "Twarda bramka niedostępna",
  "Hallucinated regulation": "Zmyślona regulacja",
  "Hallucinated regulations": "Zmyślone regulacje",
  "Hidden disagreement": "Ukryta rozbieżność",
  "Internal contradictions in Book": "Wewnętrzne sprzeczności w Księdze Rady",
  "Knowledge base unavailable": "Baza wiedzy niedostępna",
  "Late-discovered conflict": "Późno wykryty konflikt",
  "Missing key decisions": "Brakuje kluczowych decyzji",
  "Missing role weight": "Brakuje wagi roli",
  "Mid-finalization crash": "Awaria w trakcie finalizacji",
  "Mid-round AEIS update": "Aktualizacja AEIS w trakcie rundy",
  "Operator absent for hard gate timeout": "Operator nieobecny przy timeoucie twardej bramki",
  "Operator approval timeout": "Timeout akceptacji operatora",
  "Operator approves but later regrets": "Operator zatwierdza, potem wycofuje decyzję",
  "Operator changes mind on Council": "Operator zmienia decyzję wobec Rady",
  "Operator decision changes everything": "Decyzja operatora zmienia cały wynik",
  "Operator decision violates compliance": "Decyzja operatora narusza zgodność",
  "Operator delays lock indefinitely": "Operator odkłada blokadę bez terminu",
  "Operator finds error post-signoff": "Operator znajduje błąd po podpisie",
  "Operator finds errors in detailed specs": "Operator znajduje błędy w specyfikacji",
  "Operator has no time for full review": "Operator nie ma czasu na pełny przegląd",
  "Operator notes contradict Council decisions": "Notatki operatora przeczą decyzjom Rady",
  "Operator own verdict conflicts with Council": "Werdykt operatora koliduje z Radą",
  "Operator rejects questions": "Operator odrzuca pytania",
  "Operator unable to decide": "Operator nie może podjąć decyzji",
  "Operator wants major edits": "Operator chce dużych zmian",
  "Operator wants pause for thought": "Operator chce pauzy na decyzję",
  "Operator wants veto override": "Operator chce nadpisać weto",
  "Parallel awakening resource contention": "Konflikt zasobów przy równoległym uruchamianiu ról",
  "Partial verdict set": "Niepełny zestaw werdyktów",
  "Per-role cost imbalance": "Nierówny koszt między rolami",
  "Polish translation issues": "Problemy z polskim tłumaczeniem",
  "Polish translation quality issues": "Problemy jakości polskiego tłumaczenia",
  "Pre-lock scope creep": "Rozszerzanie zakresu przed blokadą",
  "Provider outage mid-round": "Awaria dostawcy w trakcie rundy",
  "Question duplicates existing scope": "Pytanie dubluje istniejący zakres",
  "Question set misses compliance": "Zestaw pytań pomija zgodność",
  "Question set too broad": "Zestaw pytań jest zbyt szeroki",
  "Role model unavailable": "Model roli niedostępny",
  "Role prompt invalid": "Prompt roli jest nieprawidłowy",
  "Role produces invalid format": "Rola zwraca nieprawidłowy format",
  "Role refuses question": "Rola odmawia odpowiedzi na pytanie",
  "Role repeats briefing only": "Rola tylko powtarza briefing",
  "Role timeout for verdict": "Timeout roli przy werdykcie",
  "Role-specific briefing mismatch": "Briefing nie pasuje do roli",
  "Roles parrot each other": "Role powtarzają się nawzajem",
  "Round consensus measurement disagrees": "Pomiar konsensusu rundy jest niespójny",
  "Round cost spike": "Skok kosztu rundy",
  "Round produces no useful new info": "Runda nie wnosi użytecznych informacji",
  "Round restart needed": "Wymagany restart rundy",
  "Round runs forever": "Runda nie kończy się",
  "Specialist deadlock": "Zakleszczenie specjalistów",
  "Specialist override not detected": "Nie wykryto nadpisania specjalisty",
  "Timeline reconciliation problem": "Problem uzgodnienia harmonogramu",
  "Total deliberation cost over budget": "Całkowity koszt deliberacji przekracza budżet",
  "Unsupported confidence": "Nieobsługiwany poziom pewności",
  "Verdict file corruption": "Uszkodzenie pliku werdyktu",
  "Verdict too shallow": "Werdykt jest zbyt płytki",
};

const roleLabel = (value?: string) => (value ? roleLabels[value] || value : "");
const statusLabel = (value?: string | number) => {
  if (value === undefined || value === null) return "gotowe";
  const text = String(value);
  return statusLabels[text] || text;
};
const stateLabelPl = (value?: string) => (value ? stateLabels[value] || value : "brak aktywnego projektu");
const edgeCategoryLabel = (value?: string) => (value ? edgeCategoryLabels[value] || value : "");
const edgeTitleLabel = (value?: string) => (value ? edgeTitleLabels[value] || value : "");

function detailTitle(item: any, index: number) {
  if (item.role) return roleLabel(item.role);
  if (item.title) return edgeTitleLabel(item.title);
  return item.id || item.question_id || `Element ${index + 1}`;
}

function detailText(item: any) {
  if (item.acknowledgement && item.role) {
    return `${roleLabel(item.role)} wczytał briefing projektu, kontekst roli i właściwe fragmenty bazy wiedzy.`;
  }
  return item.acknowledgement || item.reasoning || item.focus?.join(", ") || item.path || item.evidence || item.question_id || "Artefakt fazy jest gotowy.";
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

function safeList(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

export function CouncilToKsiegaDashboard() {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";
  const [overview, setOverview] = useState<any | null>(null);
  const [project, setProject] = useState<any | null>(null);
  const [acceptance, setAcceptance] = useState<Record<string, any>>({});
  const [edgeCases, setEdgeCases] = useState<any | null>(null);
  const [diagnosis, setDiagnosis] = useState<any | null>(null);
  const [activePhase, setActivePhase] = useState("20");
  const [operatorNotes, setOperatorNotes] = useState("Zatwierdzam kontynuację Grupy C.");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const projectId = project?.project_id as string | undefined;
  const groupComplete = Boolean(overview?.group?.complete);
  const rows = overview?.phases || [];
  const currentAcceptance = acceptance[activePhase] || {};
  const currentPhase = phases.find((item) => item.id === activePhase) || phases[0];
  const CurrentPhaseIcon = currentPhase.icon;
  const activeEdgeCases = edgeCases?.phases?.[activePhase]?.edge_cases || [];
  const deliberation = project?.deliberation || {};
  const phaseReady = Boolean(currentAcceptance.accepted);
  const hardBlocks = currentAcceptance.hard_blocks?.length || 0;
  const auditEntries = project?.audit_chain?.length || currentAcceptance.audit_chain?.entries || 0;
  const stateLabel = project?.state || "NO_ACTIVE_PROJECT";

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
      const overviewData = await api.getCouncilToKsiegaOverview();
      setOverview(overviewData);
      const active = overviewData.active_project;
      if (active?.project_id) {
        const [projectData, edgeData] = await Promise.all([
          api.getCouncilToKsiegaProject(active.project_id),
          api.getCouncilToKsiegaEdgeCases(active.project_id),
        ]);
        setProject(projectData.project);
        setAcceptance(projectData.acceptance || {});
        setEdgeCases(edgeData);
      } else {
        setProject(null);
        setAcceptance({});
        setEdgeCases(null);
      }
      setStatus("");
    } catch (err: any) {
      setStatus(`Błąd przepływu Rada -> Księga: ${err.message || String(err)}`);
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
      setStatus("Brak aktywnego projektu. Najpierw zakończ fazy 16-19.");
      return false;
    }
    return true;
  };

  const actionBody = { approved: true, operator_id: "operator", notes: operatorNotes };

  const convene = () =>
    withBusy("phase20", async () => {
      if (!ensureProject()) return;
      const data = await api.conveneCouncilPhase20(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "20": data.acceptance });
      setActivePhase("20");
      setStatus("Faza 20: Rada została zwołana.");
    });

  const verdicts = () =>
    withBusy("phase21", async () => {
      if (!ensureProject()) return;
      const data = await api.generateInitialVerdictsPhase21(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "21": data.acceptance });
      setActivePhase("21");
      setStatus("Faza 21: pierwsze werdykty zostały wygenerowane.");
    });

  const rounds = () =>
    withBusy("phase22", async () => {
      if (!ensureProject()) return;
      const data = await api.runDeliberationRoundsPhase22(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "22": data.acceptance });
      setActivePhase("22");
      setStatus("Faza 22: rundy deliberacji zakończone.");
    });

  const consolidate = () =>
    withBusy("phase23", async () => {
      if (!ensureProject()) return;
      const data = await api.consolidateCouncilPhase23(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "23": data.acceptance });
      setActivePhase("23");
      setStatus("Faza 23: decyzję Rady skonsolidowane.");
    });

  const generateBook = () =>
    withBusy("phase24", async () => {
      if (!ensureProject()) return;
      const data = await api.generateCouncilBookPhase24(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "24": data.acceptance });
      setActivePhase("24");
      setStatus("Faza 24: Księga Rady wygenerowana.");
    });

  const finalizeKsiega = () =>
    withBusy("phase25", async () => {
      if (!ensureProject()) return;
      const data = await api.finalizeKsiegaPhase25(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "25": data.acceptance });
      setActivePhase("25");
      setStatus("Faza 25: Księga zablokowana.");
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      if (!ensureProject()) return;
      const data = await api.runCouncilToKsiegaAcceptanceTest(projectId as string, activePhase);
      setAcceptance({ ...acceptance, [activePhase]: data });
      setStatus(data.accepted ? `Faza ${activePhase} zaliczona.` : `Faza ${activePhase}: blokady twarde ${data.hard_blocks?.length || 0}.`);
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      if (!ensureProject()) return;
      const caseId = activeEdgeCases[0]?.id || "EC-A1";
      const data = await api.diagnoseCouncilToKsiegaEdgeCase(projectId as string, {
        phase: activePhase,
        case_id: caseId,
        context: { source: "council_to_ksiega_dashboard", state: project?.state || "unknown" },
      });
      setDiagnosis(data);
      setStatus(`${caseId}: diagnoza gotowa.`);
    });

  const detailItems = useMemo(() => {
    if (activePhase === "20") return safeList(deliberation.convening?.awakened_roles);
    if (activePhase === "21") return safeList(deliberation.initial_verdicts?.verdicts);
    if (activePhase === "22") return safeList(deliberation.rounds?.rounds);
    if (activePhase === "23") return safeList(deliberation.consolidation?.decisions);
    if (activePhase === "24") return safeList(deliberation.council_book?.sections).map((section: string) => ({ id: section, title: section }));
    if (activePhase === "25") {
      const ksiega = deliberation.ksiega || {};
      return ["markdown", "pdf", "structured_data", "customer_facing_markdown"].map((key) => ({ id: key, title: key, path: ksiega[key]?.path || "-" }));
    }
    return [];
  }, [activePhase, deliberation]);

  const acceptedCount = rows.filter((row: any) => row.accepted).length;
  const consensus = deliberation.rounds?.overall_consensus ? `${Math.round(deliberation.rounds.overall_consensus * 100)}%` : "-";
  const decisions = safeList(deliberation.consolidation?.decisions).length;
  const bookPath = deliberation.council_book?.markdown?.path || "-";
  const ksiegaPath = deliberation.ksiega?.markdown?.path || "-";

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Deliberacja do Księgi - Fazy 20-25</h1>
            <Badge variant="outline" className={cn("text-[10px]", groupComplete ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {groupComplete ? "GRUPA C GOTOWA" : "GRUPA C AKTYWNA"}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", phaseReady ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {phaseReady ? `FAZA ${activePhase} GOTOWA` : `FAZA ${activePhase} AKTYWNA`}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
            {backendLive ? "BACKEND DZIAŁA" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
          </div>
          <div className="mt-1 max-w-4xl text-xs text-muted-foreground">
            Wielorólowa deliberacja Rady, konsolidacja decyzji, generowanie Księgi Rady i blokada Księgi dla kolejnych etapów planowania.
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3 w-3", loading && "animate-spin")} />
            Odśwież
          </Button>
          <Link
            href="/orchestration/council-rules"
            className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted hover:text-foreground"
          >
            <Settings2 className="mr-1 h-3 w-3" />
            Reguły Rady
          </Link>
          <Button size="sm" className="h-9 text-xs" onClick={runAcceptance} disabled={!projectId || busy === "acceptance"}>
            {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <TestTube2 className="mr-1 h-3 w-3" />}
            Test akceptacyjny
          </Button>
        </div>
      </div>

      {status ? <div className="rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs text-muted-foreground">{status}</div> : null}

      <div className="grid grid-cols-1 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {phases.map((item) => {
          const Icon = item.icon;
          const row = rows.find((phaseRow: any) => phaseRow.phase === item.id);
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
                {row ? `${row.accepted ? "zaliczona" : `${row.hard_blocks || 0} blokad`} / ${row.edge_cases} PP` : "czeka na stan"}
              </div>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
        <Metric label="Zaliczone fazy" value={`${acceptedCount}/6`} tone={acceptedCount === 6 ? "green" : "amber"} />
        <Metric label="Przypadki problemowe" value={overview?.group?.edge_cases || 98} tone="green" />
        <Metric label="Konsensus" value={consensus} tone={consensus === "-" ? "default" : "green"} />
        <Metric label="Decyzje" value={decisions} tone={decisions >= 20 ? "green" : "amber"} />
        <Metric label="Blokady twarde" value={hardBlocks} tone={hardBlocks ? "red" : "green"} />
        <Metric label="Wpisy audytu" value={auditEntries} tone={auditEntries ? "green" : "amber"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <CurrentPhaseIcon className="h-4 w-4 text-primary" />
            Aktywny projekt i artefakty
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <MiniRow label="Projekt" value={project?.name || "brak"} />
            <MiniRow label="ID projektu" value={project?.project_id || "niegotowe"} />
            <MiniRow label="Stan" value={stateLabelPl(stateLabel)} />
            <MiniRow label="Poziom D" value={project?.classification?.d_level_label || "-"} />
            <MiniRow label="Księga Rady" value={bookPath} />
            <MiniRow label="Księga" value={ksiegaPath} />
          </div>
          {!projectId ? (
            <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
              <Link href="/project-start" className="text-primary underline-offset-2 hover:underline">Zakończ fazy 16-19</Link> przed Grupą C.
            </div>
          ) : null}
          <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
            Reguły głosowania, kworum, bramkę krytyka i wartowników edytujesz w panelu{" "}
            <Link href="/orchestration/council-rules" className="text-primary underline-offset-2 hover:underline">
              Reguły Rady
            </Link>.
          </div>
          <label className="mt-3 grid gap-1 text-xs">
            <span className="font-medium">Notatki operatora</span>
            <textarea
              aria-label="Notatki operatora"
              className="min-h-[76px] rounded-md border border-sylion-border bg-background px-3 py-2 text-xs outline-none transition-colors focus:border-primary/50"
              value={operatorNotes}
              onChange={(event) => setOperatorNotes(event.target.value)}
            />
          </label>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Akcje operatora
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={convene} disabled={!projectId || busy === "phase20"}>
              <Users className="mr-1 h-3 w-3" />
              Zwołaj Radę
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={verdicts} disabled={!projectId || busy === "phase21"}>
              <FileCheck className="mr-1 h-3 w-3" />
              Wygeneruj pierwsze werdykty
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={rounds} disabled={!projectId || busy === "phase22"}>
              <GitBranch className="mr-1 h-3 w-3" />
              Przeprowadź rundy deliberacji
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={consolidate} disabled={!projectId || busy === "phase23"}>
              <ShieldCheck className="mr-1 h-3 w-3" />
              Skonsoliduj decyzję
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={generateBook} disabled={!projectId || busy === "phase24"}>
              <BookOpen className="mr-1 h-3 w-3" />
              Wygeneruj Księgę Rady
            </Button>
            <Button size="sm" className="h-8 text-xs" onClick={finalizeKsiega} disabled={!projectId || busy === "phase25"}>
              {busy === "phase25" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <FileLock className="mr-1 h-3 w-3" />}
              Zablokuj Księgę
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={!projectId || busy === "edge"}>
              <AlertTriangle className="mr-1 h-3 w-3" />
              Diagnozuj przypadek problemowy
            </Button>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <CurrentPhaseIcon className="h-4 w-4 text-primary" />
            Szczegóły fazy {activePhase}: {currentPhase.label}
          </h2>
          <div className="mt-3 grid max-h-[520px] grid-cols-1 gap-2 overflow-auto pr-1 md:grid-cols-2 xl:grid-cols-3">
            {detailItems.slice(0, activePhase === "23" ? 20 : 12).map((item: any, index: number) => (
              <div key={item.id || item.verdict_id || item.role_id || index} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate font-medium">
                    {detailTitle(item, index)}
                  </div>
                  <Badge variant="outline" className="h-5 text-[9px]">
                    {statusLabel(item.status || item.round_type || item.final_stance || item.round)}
                  </Badge>
                </div>
                <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">
                  {detailText(item)}
                </div>
              </div>
            ))}
            {!detailItems.length ? (
              <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
                Brak artefaktów tej fazy.
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
            {diagnosis ? <MiniRow label="Diagnoza PP" value={diagnosis.case?.id || "gotowe"} /> : null}
          </div>
          <div className="mt-3 max-h-[360px] space-y-2 overflow-auto pr-1">
            {(currentAcceptance.checks || []).map((check: any) => (
              <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <StatusIcon status={check.status} />
                <div className="min-w-0">
                  <div className="truncate font-medium">{check.label}</div>
                  <div className="mt-1 truncate text-[10px] text-muted-foreground">{check.evidence}</div>
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
                <Badge variant="outline" className="h-5 text-[9px]">{edgeCategoryLabel(item.category)}</Badge>
              </div>
              <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{edgeTitleLabel(item.title)}</div>
            </div>
          ))}
          {!activeEdgeCases.length ? (
            <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
              Przypadki problemowe pojawią się po wybraniu aktywnego projektu.
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
