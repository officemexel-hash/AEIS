"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  GitBranch,
  Loader2,
  Monitor,
  Pause,
  Play,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Square,
  TestTube2,
  Users,
  type LucideIcon,
} from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

type PhaseConfig = {
  id: string;
  label: string;
  help: string;
  icon: LucideIcon;
};

type PhaseOverviewRow = {
  accepted?: boolean;
};

type ExecutionOverview = {
  phases?: PhaseOverviewRow[];
  group?: {
    complete?: boolean;
  };
};

type RuntimeConfiguration = {
  external_cost?: boolean;
  provisioning_state?: string;
};

type RuntimeConstraints = {
  vps_blocked_until_human_gate?: boolean;
  production_blocked_until_human_gate?: boolean;
  external_blocked_until_human_gate?: boolean;
};

type CanonSnapshot = {
  runtime_constraints?: RuntimeConstraints;
  domain_profile?: {
    runtime_constraints?: RuntimeConstraints;
  };
};

type BuildWorker = {
  id?: string;
  worker_id?: string;
  domain?: string;
  role?: string;
  module?: string;
  status?: unknown;
};

type BuildEnvironment = {
  id?: string;
  environment_id?: string;
  label?: string;
  type?: string;
  target?: string;
  status?: unknown;
};

type BuildPhase = {
  id?: string;
  title?: unknown;
  status?: unknown;
  cost_usd?: unknown;
};

type GuardTelemetry = {
  status?: unknown;
};

type BuildInitialization = {
  workers?: BuildWorker[];
  environments?: BuildEnvironment[];
};

type LiveWorkerSession = {
  worker_id?: string;
  session_name?: string;
  pid?: number;
  state?: string;
  alive?: boolean;
  log_lines?: number;
  last_log?: string;
};

type LiveSpawnStatus = {
  active?: boolean;
  backend?: string;
  mode?: string;
  running?: number;
  total?: number;
  duration_seconds?: number;
  sessions?: LiveWorkerSession[];
  safety?: {
    external_cost?: boolean;
    docker_run?: boolean;
    hetzner?: boolean;
  };
};

type SequentialExecution = {
  build_phases?: BuildPhase[];
  total_progress_percent?: number;
  guards?: Record<string, GuardTelemetry>;
  real_execution_evidence?: WorkerEvidenceSummary;
  status?: string;
  timeline_status?: string;
  operator_controls?: string[];
};

type DispatchControlEvent = {
  event?: string;
  action?: string;
  state?: string;
  previous_state?: string;
  operator_id?: string;
  reason?: string;
  command?: string;
};

type DispatchControlStatus = {
  state?: string;
  previous_state?: string;
  run_id?: string;
  owner?: string;
  progress_status?: string;
  timeline_status?: string;
  controls_available?: {
    pause?: boolean;
    resume?: boolean;
    cancel?: boolean;
  };
  command_owner_rules?: {
    active_route_owner?: string;
    target_resolution?: string;
    model_agent_rule?: string;
    external_runtime_rule?: string;
    worker_pool?: string[];
    environment_pool?: string[];
  };
  events?: DispatchControlEvent[];
  last_event?: DispatchControlEvent;
};

type MidBuildCouncil = {
  session_id?: string;
  decision?: {
    impact_category?: unknown;
    human_gate_required?: boolean;
  };
  weighted_vote?: {
    weighted_score?: number;
    total_weight?: number;
    approval_ratio?: number;
    quorum?: {
      met?: boolean;
      present_roles?: number;
      required_roles?: number;
    };
    governance_veto?: {
      enabled?: boolean;
      active?: boolean;
      veto_roles?: string[];
    };
    human_gate_required?: boolean;
    adversarial_critic?: {
      present?: boolean;
      signed?: boolean;
      weight?: number;
    };
  };
  governance_veto?: {
    enabled?: boolean;
    active?: boolean;
    veto_roles?: string[];
  };
};

type BuildOrchestration = {
  active?: boolean;
  lifetime_stats?: {
    tasks_completed?: number;
  };
  worker_run_evidence?: WorkerEvidenceSummary;
};

type WorkerEvidenceSummary = {
  run_id?: string;
  status?: string;
  workers_completed?: number;
  artifacts_written?: number;
  diffs_written?: number;
  logs_written?: number;
  tests_passed?: number;
};

type AuditTruthMap = {
  status_counts?: Record<string, number>;
  coverage?: {
    modules_total?: number;
    live_verified?: number;
    live_verified_percent?: number;
  };
  modules?: Array<{
    module?: string;
    status?: string;
  }>;
};

type BuildCompletion = {
  artifacts_inventory?: {
    total_files?: number;
  };
  cost_reconciliation?: {
    build_actual_usd?: unknown;
  };
  final_coherence?: {
    status?: unknown;
  };
  worker_decommissioning?: {
    decommissioned?: number;
    expected?: number;
  };
  worker_run_evidence?: WorkerEvidenceSummary;
  audit_truth_map?: AuditTruthMap;
};

type QualityGates = {
  summary?: {
    functional_passed_effective?: number;
    functional_tests_effective?: number;
    pass_rate_percent?: number;
    quality_guard_verdict?: unknown;
  };
  coverage?: {
    l1_percent?: number;
  };
};

type AcceptanceTesting = {
  staging_deployment?: {
    deployed?: boolean;
  };
  feedback?: {
    total?: number;
  };
  resolution?: {
    important_fixed?: number;
    minor_fixed?: number;
    feature_requests_deferred?: number;
  };
  signoff?: {
    received?: boolean;
  };
};

type PredeployState = {
  production_environment?: {
    provisioned?: boolean;
    provider?: string;
    region?: string;
  };
  dns?: {
    domain?: string;
  };
  deploy_plan?: {
    rollback_test?: {
      tested_in_staging?: boolean;
      rollback_minutes?: number;
    };
  };
  authorization?: {
    approved?: boolean;
  };
};

type CanaryStage = {
  verdict?: string;
};

type ProductionDeploy = {
  canary_stages?: CanaryStage[];
  serving_traffic?: boolean;
  external_effects?: {
    mode?: string;
  };
  observation_24h?: {
    uptime_percent?: number;
    invoices_ksef_accepted?: number;
    successful_payments?: number;
    documents_processed?: number;
    financial_events?: number;
  };
};

type ProjectClosure = {
  reports?: {
    operator_report_generated?: boolean;
  };
  skills?: {
    promoted?: unknown[];
  };
  cost_reconciliation?: {
    final_actual_usd?: unknown;
    operator_profit_usd?: unknown;
  };
  warranty?: {
    started?: boolean;
    start?: string;
    end?: string;
  };
};

type ExecutionData = {
  build_initialization?: BuildInitialization;
  sequential_execution?: SequentialExecution;
  dispatch_control?: DispatchControlStatus;
  mid_build_council?: MidBuildCouncil;
  build_orchestration?: BuildOrchestration;
  build_completion?: BuildCompletion;
  quality_gates?: QualityGates;
  acceptance_testing?: AcceptanceTesting;
  predeploy?: PredeployState;
  production_deploy?: ProductionDeploy;
  project_closure?: ProjectClosure;
  audit_truth_map?: AuditTruthMap;
  model_effectiveness?: {
    tracked_roles?: number;
    adversarial_critic_tracked?: boolean;
  };
};

type ExecutionProject = {
  project_id?: string;
  name?: string;
  title?: string;
  state?: string;
  execution?: ExecutionData;
  canon_snapshot?: CanonSnapshot;
};

type AcceptanceCheck = {
  id?: string;
  label?: unknown;
  status?: unknown;
  evidence?: unknown;
};

type AcceptancePhase = {
  accepted?: boolean;
  checks?: AcceptanceCheck[];
  dod?: {
    passed_required?: number;
    required?: number;
  };
};

type EdgeCaseItem = {
  id?: string;
  severity?: string;
  category?: unknown;
  title?: unknown;
};

type EdgeCasesData = {
  phases?: Record<string, { edge_cases?: EdgeCaseItem[] }>;
};

type DiagnosisData = {
  case?: EdgeCaseItem;
};

const phases: PhaseConfig[] = [
  {
    id: "32",
    label: "Inicjalizacja budowy",
    help: "Tworzy katalog pracy, gałęzie, wykonawców, środowiska i monitoring. To punkt startowy realnego wykonania po zakończeniu planowania.",
    icon: Rocket,
  },
  {
    id: "33",
    label: "Sekwencyjne wykonanie faz",
    help: "Uruchamia pętlę budowy: kolejne fazy są wykonywane, raportują koszt, postęp i stan strażników.",
    icon: Play,
  },
  {
    id: "34",
    label: "Rada w trakcie budowy",
    help: "Pozwala ponownie zwołać radę, gdy w trakcie wykonania pojawi się zmiana zakresu, ryzyko albo konflikt techniczny.",
    icon: Users,
  },
  {
    id: "35",
    label: "Orkiestracja budowy",
    help: "Włącza koordynację wykonawców, kolejki zadań, blokady, odzyskiwanie po błędach i kontrolę spójności między modułami.",
    icon: GitBranch,
  },
  {
    id: "36",
    label: "Zamknięcie budowy",
    help: "Waliduje artefakty, koszt, końcową spójność, raport podsumowujący oraz wygasza wykonawców.",
    icon: CheckCircle2,
  },
  {
    id: "37",
    label: "Bramki jakości",
    help: "Uruchamia testy L1-L5, mierzy pokrycie, wydajność, błędy krytyczne oraz werdykt strażnika jakości.",
    icon: ShieldCheck,
  },
  {
    id: "38",
    label: "Testy akceptacyjne klienta",
    help: "Wystawia środowisko testówe, zbiera uwagi klienta, rozdziela poprawki i zapisuje formalny podpis akceptacyjny.",
    icon: TestTube2,
  },
  {
    id: "39",
    label: "Finalna kontrola przed wydaniem",
    help: "SprawdŹa środowisko docelowe, rollback, monitoring, obsługę klienta i twardą autoryzację. Dla projektu local-only oznacza lokalny release rehearsal, nie produkcję.",
    icon: Monitor,
  },
  {
    id: "40",
    label: "Wdrożenie / próba lokalna",
    help: "Przeprowadza kontrolowane wdrożenie albo lokalny release rehearsal. Akcje zewnętrzne i produkcja wymagają osobnego Human Gate.",
    icon: Rocket,
  },
  {
    id: "41",
    label: "Zamknięcie projektu",
    help: "Tworzy raporty końcowe, archiwum, fakturę, decyzję o promowaniu umiejętności, przekazanie klientowi i okres gwarancyjny.",
    icon: CheckCircle2,
  },
];

const STATE_LABELS: Record<string, string> = {
  NO_ACTIVE_PROJECT: "Brak aktywnego projektu",
  BUILDING: "Budowa trwa",
  BUILD_COMPLETE: "Budowa zakończona",
  READY_FOR_ACCEPTANCE_TESTING: "Gotowe do akceptacji",
  READY_FOR_PREDEPLOY: "Gotowe do kontroli przed wdrożeniem",
  READY_FOR_PRODUCTION_DEPLOY: "Gotowe do produkcji",
  DEPLOYED: "Wdrożone",
  CLOSED: "Zamknięte",
};

const STATUS_LABELS: Record<string, string> = {
  active: "aktywne",
  approved: "zatwierdzone",
  authorized: "autoryzowane",
  blocked: "zablokowane",
  complete: "ukończone",
  completed: "ukończone",
  deployed: "wdrożone",
  failed: "niezaliczone",
  final: "finalne",
  fixed: "naprawione",
  guarded: "chronione",
  info: "informacja",
  in_progress: "w toku",
  missing: "brak",
  on_budget: "w budżecie",
  open: "otwarte",
  pass: "zaliczone",
  PASS: "zaliczone",
  pending: "oczekuje",
  ready: "gotowe",
  received: "otrzymane",
  recovered: "odzyskane",
  signed: "podpisane",
};

const ACCEPTANCE_LABELS: Record<string, string> = {
  "Workspace allocated": "Obszar roboczy przydzielony",
  "Workers activated": "Wykonawcy aktywowani",
  "Environments provisioned": "Środowiska przygotowane",
  "Repository initialized": "Repozytorium zainicjowane",
  "Live monitoring active": "Monitoring na żywo aktywny",
  "Pre-build verification": "Weryfikacja przed budową",
  "Operator authorized": "Operator zatwierdził etap",
  "Audit chain entry build_initialized": "Wpis audytu: inicjalizacja budowy",
  "Project state BUILDING": "Stan projektu co najmniej: budowa trwa",
  "Sequential execution loop active": "Pętla wykonania sekwencyjnego aktywna",
  "Foundation phase completed": "Faza fundamentu ukończona",
  "Next build phase in progress or complete": "Następna faza budowy trwa albo jest ukończona",
  "Live progress computed": "Postęp liczony na żywo",
  "Cost within build budget": "Koszt mieści się w budżecie budowy",
  "Continuous Guards monitoring": "Stały monitoring strażników",
  "Operator live controls available": "Kontrolki operatora dostępne na żywo",
  "Audit chain entry sequential_execution_started": "Wpis audytu: start wykonania sekwencyjnego",
  "Mid-build Council trigger recorded": "Powód zwołania rady zapisany",
  "Council reconvened with relevant roles": "Rada zwołana z właściwymi rolami",
  "Mini-deliberation complete": "Mini-deliberacja zakończona",
  "Decision documented with reasoning": "Decyzja zapisana z uzasadnieniem",
  "Build plan context updated": "Kontekst planu budowy zaktualizowany",
  "Audit chain entry mid_build_council_decision": "Wpis audytu: decyzja rady w trakcie budowy",
  "Build state resumed": "Stan budowy wznowiony",
  "Build orchestration active": "Orkiestracja budowy aktywna",
  "Worker coordination primitives": "Mechanizmy koordynacji wykonawców gotowe",
  "Per-phase orchestration tracked": "Orkiestracja śledzona per faza",
  "Cross-worker Coherence Guard passed": "Strażnik spójności między wykonawcami zaliczony",
  "Layer parallelism configured": "Równoległość warstw skonfigurowana",
  "Error recovery cascades ready": "Kaskady odzyskiwania po błędach gotowe",
  "Mid-build profile switching guarded": "Zmiana profilu w trakcie budowy chroniona",
  "Lifetime orchestration stats": "Statystyki orkiestracji zapisane",
  "Audit chain entry build_orchestration_active": "Wpis audytu: orkiestracja budowy aktywna",
  "All phase artifacts validated": "Wszystkie artefakty faz zwalidowane",
  "Final coherence check passed": "Końcowa kontrola spójności zaliczona",
  "Comprehensive Guards sweep passed": "Pełny przegląd strażników zaliczony",
  "Artifacts inventory complete": "Inwentarz artefaktów kompletny",
  "Cost reconciliation done": "Rozliczenie kosztu wykonane",
  "Workers decommissioned": "Wykonawcy wygaszeni",
  "Build summary report generated": "Raport podsumowania budowy wygenerowany",
  "Audit chain entry build_complete": "Wpis audytu: budowa zakończona",
  "Project state BUILD_COMPLETE": "Stan projektu co najmniej: budowa zakończona",
  "All L1 unit tests executed": "Wszystkie testy jednostkowe L1 wykonane",
  "All L2 integration tests executed": "Wszystkie testy integracyjne L2 wykonane",
  "All L3 E2E tests executed": "Wszystkie testy E2E L3 wykonane",
  "L4 performance tests executed": "Testy wydajności L4 wykonane",
  "All L5 human-like scenarios executed": "Scenariusze L5 jak użytkownik wykonane",
  "Coverage targets met": "Cele pokrycia spełnione",
  "All critical findings resolved": "Wszystkie krytyczne ustalenia rozwiązane",
  "Quality Guard verdict PASS": "Werdykt strażnika jakości: zaliczone",
  "Audit chain entry quality_gates_passed": "Wpis audytu: bramki jakości zaliczone",
  "Project state READY_FOR_ACCEPTANCE_TESTING": "Stan projektu co najmniej: gotowe do akceptacji",
  "Staging deployed with latest build": "Środowisko testówe wdrożone z najnowszą budową",
  "Customer access provided": "Dostęp klienta przekazany",
  "Customer test plan delivered": "Plan testów klienta dostarczony",
  "Customer review window completed": "Okno przeglądu klienta zakończone",
  "Customer feedback collected": "Uwagi klienta zebrane",
  "All feedback addressed": "Wszystkie uwagi obsłużone",
  "Customer formal sign-off": "Formalny podpis akceptacyjny klienta",
  "Audit chain entry customer_signoff_received": "Wpis audytu: akceptacja klienta otrzymana",
  "Project state READY_FOR_PREDEPLOY": "Stan projektu co najmniej: gotowe do kontroli przed wdrożeniem",
  "Production env provisioned": "Środowisko produkcyjne przygotowane",
  "Pre-deploy checklist passed": "Lista kontroli przed wdrożeniem zaliczona",
  "Rollback plan verified": "Plan rollbacku zweryfikowany",
  "Monitoring and alerting configured": "Monitoring i alerty skonfigurowane",
  "Customer support workflow ready": "Proces obsługi klienta gotowy",
  "Operator availability confirmed": "Dostępność operatora potwierdzona",
  "Final hard gate authorization": "Finalna twarda autoryzacja",
  "Audit chain entry predeploy_authorized": "Wpis audytu: kontrola przed wdrożeniem autoryzowana",
  "Project state READY_FOR_PRODUCTION_DEPLOY": "Stan projektu co najmniej: gotowe do produkcji",
  "Production env serving traffic": "Produkcja obsługuje ruch",
  "All canary stages passed": "Wszystkie etapy wdrożenia stopniowego zaliczone",
  "No critical errors in 24h post-deploy": "Brak błędów krytycznych przez 24h po wdrożeniu",
  "Customer post-deploy verification done": "Weryfikacja klienta po wdrożeniu zakończona",
  "Customer training completed": "Szkolenie klienta zakończone",
  "System uptime 100% in 24h": "Dostępność systemu 100% przez 24h",
  "Production handed off to customer": "Produkcja przekazana klientowi",
  "Audit chain entry production_deployed": "Wpis audytu: produkcja wdrożona",
  "Project state DEPLOYED": "Stan projektu co najmniej: wdrożone",
  "Final operator report generated": "Raport końcowy operatora wygenerowany",
  "Customer-facing closure report sent": "Raport końcowy dla klienta wysłany",
  "Calibration data extracted": "Dane kalibracyjne wyciągnięte",
  "Customer fully trained": "Klient w pełni przeszkolony",
  "Customer received docs, runbooks, support": "Klient otrzymał dokumenty, runbooki i kontakt do obsługi",
  "Workspace archived read-only": "Workspace zarchiwizowany jako tylko do odczytu",
  "Audit chain finalized": "Łańcuch audytu sfinalizowany",
  "Skills promotion decisions made": "Decyzje o promowaniu umiejętności zapisane",
  "Cost reconciliation final": "Finalne rozliczenie kosztów",
  "Closure email sent in Polish": "Mail zamknięcia wysłany po polsku",
  "Final invoice sent and KSeF submitted": "Faktura końcowa wysłana i zgłoszona do KSeF",
  "30-day warranty period started": "30-dniowy okres gwarancyjny rozpoczęty",
  "Project state CLOSED": "Stan projektu: zamknięte",
};

const EDGE_CATEGORY_LABELS: Record<string, string> = {
  archival_skills: "archiwum i umiejętności",
  artifacts: "artefakty",
  coherence: "spójność",
  compliance: "zgodność",
  coordination: "koordynacja",
  cost: "koszt",
  customer: "klient",
  customer_handoff: "przekazanie klientowi",
  customer_interaction: "kontakt z klientem",
  customer_side: "strona klienta",
  dashboard: "dashboard",
  decommission: "wygaszanie",
  deliberation: "deliberacja",
  environments: "środowiska",
  external_services: "usługi zewnętrzne",
  feedback_resolution: "obsługa uwag",
  invoice_recovery: "faktura i odzyskiwanie",
  operator_recovery: "odzyskiwanie operatora",
  parallelism: "równoległość",
  performance: "wydajność",
  phase_loop: "pętla faz",
  production_env: "środowisko produkcyjne",
  profile_switch: "zmiana profilu",
  recovery: "odzyskiwanie",
  recovery_postdeploy: "odzyskiwanie po wdrożeniu",
  reporting: "raportowanie",
  repository: "repozytorium",
  signoff: "podpis akceptacyjny",
  stage_rollback: "wdrożenie stopniowe i rollback",
  staging: "środowisko testówe",
  test_execution: "wykonanie testów",
  triggers: "wyzwalacze",
  visibility: "widoczność",
  workers: "wykonawcy",
  workspace: "workspace",
};

const EDGE_TITLE_TRANSLATIONS: Record<string, string> = {
  "Workspace path unavailable": "Ścieżka workspace jest niedostępna",
  "Storage allocation insufficient": "Przydział dysku jest za mały",
  "Artifact permission fails": "Uprawnienia do artefaktów nie przechodzą",
  "Metadata write corruption": "Zapis metadanych jest uszkodzony",
  "Worker activation fails": "Aktywacja wykonawcy nie przechodzi",
  "Model quota unavailable": "Limit modelu jest niedostępny",
  "Skill loading fails": "Ładowanie umiejętności nie przechodzi",
  "Worker role assignment conflict": "Konflikt przypisania roli wykonawcy",
  "Stage 1 fails immediately": "Etap 1 pada natychmiast",
  "Stage 2 marginal performance": "Etap 2 ma graniczną wydajność",
  "Stage 3 customer complaint mid-stage": "Klient zgłasza problem w trakcie etapu 3",
  "Stage 4 sudden spike": "Nagły skok obciążenia w etapie 4",
  "Multiple stages have issues": "Problemy pojawiają się w wielu etapach",
  "Stripe production outage during deploy": "Awaria Stripe w produkcji podczas wdrożenia",
  "KSeF rejects production invoices": "KSeF odrzuca faktury produkcyjne",
  "Mailjet rate limit hit": "Mailjet trafia w limit wysyłki",
  "TLS certificate issue": "Problem z certyfikatem TLS",
  "Customer DNS not propagated": "DNS klienta nie został rozpropagowany",
  "Customer reports immediate problems": "Klient zgłasza natychmiastowe problemy",
  "Customer clients confused": "Użytkownicy klienta są zdezorientowani",
  "Customer wants pause mid-deploy": "Klient chce wstrzymać wdrożenie w trakcie",
  "Production data corruption detected": "Wykryto uszkodzenie danych produkcyjnych",
  "Real Stripe transaction fails": "Realna transakcja Stripe nie przechodzi",
  "Customer training session disrupted": "Sesja szkoleniowa klienta została przerwana",
  "24h monitoring detects subtle issue": "Monitoring 24h wykrywa subtelny problem",
  "Operator unavailable after deploy": "Operator jest niedostępny po wdrożeniu",
  "Final report generation fails": "Generowanie raportu końcowego nie przechodzi",
  "Customer-facing report ill-tone": "Raport dla klienta ma zły ton komunikacji",
  "Calibration data extraction fails": "Ekstrakcja danych kalibracyjnych nie przechodzi",
  "Cost reconciliation discrepancy": "Rozbieżność w rozliczeniu kosztów",
  "Customer not satisfied with documentation": "Klient nie jest zadowolony z dokumentacji",
  "Customer cannot access materials": "Klient nie ma dostępu do materiałów",
  "Customer wants additional training": "Klient chce dodatkowe szkolenie",
  "Customer disputes deliverables": "Klient kwestionuje zakres dostarczonych elementów",
  "Archive encryption fails": "Szyfrowanie archiwum nie przechodzi",
  "Skills promotion regresses": "Promowanie umiejętności powoduje regresję",
  "Workspace too large for archive": "Workspace jest za duży do archiwum",
  "Audit chain finalization fails": "Finalizacja łańcucha audytu nie przechodzi",
  "KSeF rejects final invoice": "KSeF odrzuca fakturę końcową",
  "Customer delays payment": "Klient opóźnia płatność",
  "Customer disputes final invoice": "Klient kwestionuje fakturę końcową",
};

const HELP = {
  header: "Ten ekran prowadzi operatora przez fazy 32-41: od rozpoczęcia budowy, przez testy i kontrolę przed wdrożeniem, do wdrożenia produkcyjnego oraz zamknięcia projektu.",
  metrics: "Metryki pokazują szybki stan przepływu: ile faz jest zaakceptowanych, ilu wykonawców i środowisk działa, jaki jest wskaźnik zaliczenia lub dostępność oraz w jakim stanie znajduje się projekt.",
  activeProject: "Aktywny projekt jest pobierany z backendu jako bieżący kontekst wykonania. Wszystkie akcje na tym ekranie zapisują artefakty i audyt właśnie do tego projektu.",
  actions: "Przyciski uruchamiają kolejne fazy. Po każdej akcji dashboard odświeża projekt, akceptację i edge case'y.",
  acceptance: "Lista wymagań DoD dla aktywnej fazy. Status zielony oznacza, że warunek przeszedł; czerwony blokuje akceptację fazy.",
  guards: "Telemetria strażników uruchomionych w trakcie budowy. To szybki podgląd, czy spójność, koszt, bezpieczeństwo i pochodzenie artefaktów są pod kontrolą.",
  edgeCases: "Przypadki brzegowe dla aktywnej fazy. Diagnoza wybiera pierwszy przypadek z listy i zapisuje ścieżkę naprawy w kontekście projektu.",
};

function safeList<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function formatState(value: unknown): string {
  const raw = String(value || "NO_ACTIVE_PROJECT");
  return STATE_LABELS[raw] ?? raw;
}

function formatStateForProject(value: unknown, localOnly: boolean): string {
  const raw = String(value || "NO_ACTIVE_PROJECT");
  if (localOnly && raw === "READY_FOR_PRODUCTION_DEPLOY") return "Gotowe do lokalnej próby wydania";
  if (localOnly && raw === "DEPLOYED") return "Lokalna próba wydania wykonana";
  return formatState(raw);
}

function formatStatus(value: unknown): string {
  if (value === true) return "tak";
  if (value === false) return "nie";
  const raw = String(value ?? "pending");
  return STATUS_LABELS[raw] ?? raw.replaceAll("_", " ");
}

function formatUsdValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "oczekuje";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "oczekuje";
  return `$${amount}`;
}

function formatSeverity(value: unknown): string {
  const raw = String(value || "");
  if (raw === "high") return "wysoki";
  if (raw === "medium") return "średni";
  if (raw === "low") return "niski";
  return raw || "nieznany";
}

function formatPhaseTitle(value: unknown): string {
  const raw = String(value || "");
  const labels: Record<string, string> = {
    Foundation: "Fundament",
    "KSeF and invoicing": "KSeF i fakturowanie",
    "CRM workflow": "Workflow CRM",
    "Billing integration": "Integracja płatności",
    "Customer portal": "Portal klienta",
    "Admin reporting": "Raportowanie admina",
  };
  return labels[raw] ?? raw;
}

function formatGuardName(value: string): string {
  const labels: Record<string, string> = {
    coherence: "Spójność",
    cost: "Koszt",
    provenance: "Pochodzenie",
    quality: "Jakość",
    security: "Bezpieczeństwo",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatImpact(value: unknown): string {
  const labels: Record<string, string> = {
    impact_1_no_current_build_change: "wpływ 1: bez zmiany bieżącej budowy",
    impact_2_requires_minor_plan_update: "wpływ 2: drobna zmiana planu",
    impact_3_requires_replan: "wpływ 3: wymaga przeplanowania",
  };
  const raw = String(value || "pending");
  return labels[raw] ?? formatStatus(raw);
}

function formatAcceptanceLabel(value: unknown): string {
  const raw = String(value || "");
  return ACCEPTANCE_LABELS[raw] ?? raw;
}

function formatEvidence(value: unknown): string {
  const raw = String(value ?? "");
  if (!raw) return "brak dowodu";
  return raw
    .replace("BUILDING", "budowa trwa")
    .replace("BUILD_COMPLETE", "budowa zakończona")
    .replace("READY_FOR_ACCEPTANCE_TESTING", "gotowe do akceptacji")
    .replace("READY_FOR_PREDEPLOY", "gotowe do kontroli przed wdrożeniem")
    .replace("READY_FOR_PRODUCTION_DEPLOY", "gotowe do produkcji")
    .replace("DEPLOYED", "wdrożone")
    .replace("CLOSED", "zamknięte")
    .replace("build_initialized", "audyt: inicjalizacja budowy")
    .replace("sequential_execution_started", "audyt: start wykonania")
    .replace("mid_build_council_decision", "audyt: decyzja rady")
    .replace("build_orchestration_active", "audyt: orkiestracja aktywna")
    .replace("build_complete", "audyt: budowa zakończona")
    .replace("quality_gates_passed", "audyt: bramki jakości zaliczone")
    .replace("customer_signoff_received", "audyt: akceptacja klienta")
    .replace("predeploy_authorized", "audyt: kontrola przed wdrożeniem")
    .replace("production_deployed", "audyt: produkcja wdrożona")
    .replace("project_closed", "audyt: projekt zamknięty")
    .replace("envs", "środowiska")
    .replace("roles", "ról")
    .replace("tasks", "zadań")
    .replace("files", "plików")
    .replace("branches", "gałęzi")
    .replace("days", "dni")
    .replace("items", "pozycji")
    .replace("waived", "pominięte")
    .replace("critical", "krytyczne")
    .replace("operator report", "raport operatora")
    .replace("customer report", "raport klienta")
    .replace("handoff complete", "przekazanie zakończone")
    .replace("secure access provided", "bezpieczny dostęp przekazany")
    .replace("support ready", "obsługa gotowa")
    .replace("live dashboard", "panel na żywo")
    .replace("all categories", "wszystkie kategorie")
    .replace("all complete", "wszystko ukończone")
    .replace("checks pass", "kontrole zaliczone")
    .replace("guards pass", "strażnicy zaliczeni")
    .replace("summary report", "raport podsumowujący")
    .replace("fixed or deferred", "naprawione albo odroczone")
    .replace("on budget", "w budżecie")
    .replace("authorized", "autoryzowane")
    .replace("signed", "podpisane");
}

function formatEdgeCategory(value: unknown): string {
  const raw = String(value || "");
  return EDGE_CATEGORY_LABELS[raw] ?? raw.replaceAll("_", " ");
}

function formatEdgeTitle(value: unknown): string {
  const raw = String(value || "");
  if (EDGE_TITLE_TRANSLATIONS[raw]) return EDGE_TITLE_TRANSLATIONS[raw];
  return raw
    .replace("fails", "nie przechodzi")
    .replace("unavailable", "niedostępne")
    .replace("missing", "brakuje")
    .replace("conflict", "konflikt")
    .replace("corruption", "uszkodzenie")
    .replace("blocked", "zablokowane")
    .replace("timeout", "timeout")
    .replace("overrun", "przekroczenie")
    .replace("Customer", "Klient")
    .replace("Worker", "Wykonawca")
    .replace("Production", "Produkcja")
    .replace("Build", "Budowa")
    .replace("Cost", "Koszt")
    .replace("Quality", "Jakość")
    .replace("Security", "Bezpieczeństwo")
    .replace("Environment", "Środowisko")
    .replace("Repository", "Repozytorium");
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />;
  if (status === "info") return <Clock3 className="mt-0.5 h-3.5 w-3.5 text-primary" />;
  return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />;
}

function Metric({
  label,
  value,
  help,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  help?: string;
  tone?: "default" | "green" | "amber";
}) {
  return (
    <Card className={cn("border-sylion-border bg-card p-4", tone === "green" && "border-sylion-green/30", tone === "amber" && "border-sylion-amber/30")}>
      <div className="flex items-center gap-1 text-[11px] uppercase text-muted-foreground">
        <span>{label}</span>
        {help ? <HelpTip text={help} side="bottom" /> : null}
      </div>
      <div className="mt-2 truncate text-2xl font-semibold tracking-tight">{value}</div>
    </Card>
  );
}

function MiniRow({ label, value, help }: { label: string; value: ReactNode; help?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs">
      <span className="flex min-w-0 items-center gap-1 font-medium">
        <span className="truncate">{label}</span>
        {help ? <HelpTip text={help} side="top" className="h-4 w-4" size={13} /> : null}
      </span>
      <span className="truncate text-muted-foreground">{value}</span>
    </div>
  );
}

function SectionTitle({
  icon: Icon,
  title,
  help,
  tone = "primary",
}: {
  icon: LucideIcon;
  title: string;
  help: string;
  tone?: "primary" | "amber";
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <Icon className={cn("h-5 w-5", tone === "amber" ? "text-sylion-amber" : "text-primary")} />
      <h2 className="text-lg font-semibold">{title}</h2>
      <HelpTip text={help} side="top" />
    </div>
  );
}

export function ExecutionStartDashboard() {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";
  const backendChecking = health.status === "unknown";
  const [overview, setOverview] = useState<ExecutionOverview | null>(null);
  const [project, setProject] = useState<ExecutionProject | null>(null);
  const [acceptance, setAcceptance] = useState<Record<string, AcceptancePhase>>({});
  const [edgeCases, setEdgeCases] = useState<EdgeCasesData | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null);
  const [activePhase, setActivePhase] = useState("32");
  const [operatorNotes, setOperatorNotes] = useState("Zatwierdzam start wykonania.");
  const [runtimeConfiguration, setRuntimeConfiguration] = useState<RuntimeConfiguration | null>(null);
  const [liveSpawn, setLiveSpawn] = useState<LiveSpawnStatus | null>(null);
  const [dispatchControl, setDispatchControl] = useState<DispatchControlStatus | null>(null);
  const [runtimeForm, setRuntimeForm] = useState({
    topology: "local-first",
    local_workers: "6",
    vps_workers: "0",
    environments: "6",
    max_parallel_workers: "6",
    max_monthly_vps_eur: "0",
    allow_paid_vps: false,
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const projectId = project?.project_id;
  const execution = project?.execution || {};
  const initialization = execution.build_initialization || {};
  const progress = execution.sequential_execution || {};
  const dispatch: DispatchControlStatus = dispatchControl || execution.dispatch_control || {};
  const midBuildCouncil = execution.mid_build_council || {};
  const orchestration = execution.build_orchestration || {};
  const completion = execution.build_completion || {};
  const qualityGates = execution.quality_gates || {};
  const acceptanceTesting = execution.acceptance_testing || {};
  const predeploy = execution.predeploy || {};
  const productionDeploy = execution.production_deploy || {};
  const projectClosure = execution.project_closure || {};
  const workerEvidence = completion.worker_run_evidence || orchestration.worker_run_evidence || progress.real_execution_evidence || {};
  const liveSessions = safeList<LiveWorkerSession>(liveSpawn?.sessions);
  const liveRunning = Number(liveSpawn?.running || 0);
  const liveTotal = Number(liveSpawn?.total || liveSessions.length || 0);
  const dispatchState = dispatch.state || (progress.status === "long_running" ? "running" : progress.status) || "not_started";
  const dispatchRules: NonNullable<DispatchControlStatus["command_owner_rules"]> = dispatch.command_owner_rules || {};
  const dispatchEvents = safeList<DispatchControlEvent>(dispatch.events).slice(-4).reverse();
  const weightedVote = midBuildCouncil.weighted_vote || {};
  const governanceVeto = midBuildCouncil.governance_veto || weightedVote.governance_veto || {};
  const truthMap = completion.audit_truth_map || execution.audit_truth_map || {};
  const truthCounts = truthMap.status_counts || {};
  const currentAcceptance = acceptance[activePhase] || {};
  const currentPhase = phases.find((item) => item.id === activePhase) || phases[0];
  const CurrentPhaseIcon = currentPhase.icon;
  const rows = useMemo(() => safeList<PhaseOverviewRow>(overview?.phases), [overview?.phases]);
  const groupComplete = Boolean(overview?.group?.complete);
  const activeEdgeCases = edgeCases?.phases?.[activePhase]?.edge_cases || [];
  const stateLabel = project?.state || "NO_ACTIVE_PROJECT";
  const runtimeConstraints = project?.canon_snapshot?.runtime_constraints || project?.canon_snapshot?.domain_profile?.runtime_constraints || {};
  const localOnlyProject = Boolean(
    runtimeConstraints.vps_blocked_until_human_gate ||
    runtimeConstraints.production_blocked_until_human_gate ||
    runtimeConstraints.external_blocked_until_human_gate ||
    productionDeploy.external_effects?.mode === "local_release_rehearsal_no_external_calls",
  );
  const displayProjectName = project?.name || project?.title || project?.project_id || "Brak aktywnego projektu";
  const acceptedCount = useMemo(() => rows.filter((row) => row.accepted).length, [rows]);

  const load = useCallback(async () => {
    if (!backendLive && !backendChecking) {
      setOverview(null);
      setProject(null);
      setAcceptance({});
      setEdgeCases(null);
      setDispatchControl(null);
      setLoading(false);
      setStatus("API jest offline.");
      return;
    }
    setLoading(true);
    try {
      const overviewData = await api.getExecutionStartOverview();
      setOverview(overviewData);
      const active = overviewData.active_project;
      if (active?.project_id) {
        const projectData = await api.getExecutionStartProject(active.project_id);
        setProject(projectData.project);
        setAcceptance(projectData.acceptance || {});
        const [edgeResult, runtimeResult, liveResult, dispatchResult] = await Promise.allSettled([
          api.getExecutionStartEdgeCases(active.project_id),
          api.getExecutionRuntimeConfiguration(active.project_id),
          api.getExecutionLiveWorkers(active.project_id),
          api.getExecutionDispatchControl(active.project_id),
        ]);
        setEdgeCases(edgeResult.status === "fulfilled" ? edgeResult.value : null);
        setLiveSpawn(liveResult.status === "fulfilled" ? liveResult.value.live_spawn || null : null);
        setDispatchControl(
          dispatchResult.status === "fulfilled"
            ? dispatchResult.value.dispatch_control || projectData.project?.execution?.dispatch_control || null
            : projectData.project?.execution?.dispatch_control || null,
        );
        if (runtimeResult.status === "fulfilled") {
          const config = runtimeResult.value.runtime_configuration || {};
          setRuntimeConfiguration(config);
          setRuntimeForm((previous) => ({
            ...previous,
            topology: config.topology || previous.topology,
            local_workers: String(config.local_workers ?? previous.local_workers),
            vps_workers: String(config.vps_workers ?? previous.vps_workers),
            environments: String(config.environments ?? previous.environments),
            max_parallel_workers: String(config.max_parallel_workers ?? previous.max_parallel_workers),
            max_monthly_vps_eur: String(config.max_monthly_vps_eur ?? previous.max_monthly_vps_eur),
            allow_paid_vps: Boolean(config.allow_paid_vps),
          }));
        } else {
          setRuntimeConfiguration(null);
        }
      } else {
        setProject(null);
        setAcceptance({});
        setEdgeCases(null);
        setRuntimeConfiguration(null);
        setLiveSpawn(null);
        setDispatchControl(null);
      }
      setStatus("");
    } catch (err: unknown) {
      setStatus(`Błąd panelu wykonania: ${errorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive, backendChecking]);

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
    } catch (err: unknown) {
      setStatus(errorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const ensureProject = () => {
    if (!projectId) {
      setStatus("Brak aktywnego projektu. Najpierw zakończ fazy 26-31.");
      return false;
    }
    return true;
  };

  const actionBody = { approved: true, operator_id: "operator", notes: operatorNotes };

  const setRuntimeField = (field: keyof typeof runtimeForm, value: string | boolean) => {
    setRuntimeForm((previous) => ({ ...previous, [field]: value }));
  };

  const runtimeNumber = (value: string, fallback: number, min: number, max: number) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.max(min, Math.min(max, Math.floor(parsed)));
  };

  const saveRuntimeConfiguration = () =>
    withBusy("runtime-config", async () => {
      if (!ensureProject()) return;
      const localWorkers = runtimeNumber(runtimeForm.local_workers, 1, 1, 60);
      const vpsWorkers = runtimeNumber(runtimeForm.vps_workers, 0, 0, 60);
      const environments = runtimeNumber(runtimeForm.environments, 1, 1, 12);
      const maxParallel = runtimeNumber(runtimeForm.max_parallel_workers, localWorkers + vpsWorkers, 1, 60);
      const monthlyCap = runtimeNumber(runtimeForm.max_monthly_vps_eur, 0, 0, 10000);
      const data = await api.updateExecutionRuntimeConfiguration(projectId as string, {
        approved: true,
        operator_id: "operator",
        notes: operatorNotes,
        topology: runtimeForm.topology,
        local_workers: localWorkers,
        vps_workers: vpsWorkers,
        environments,
        max_parallel_workers: maxParallel,
        max_monthly_vps_eur: monthlyCap,
        allow_paid_vps: runtimeForm.allow_paid_vps,
        apply_to_next_build: true,
      });
      setRuntimeConfiguration(data.runtime_configuration);
      setProject(data.project);
      setOverview(data.overview || overview);
      setStatus("Konfiguracja runtime zapisana. Uruchom ponownie fazę 32, aby odtworzyć wykonawców i środowiska.");
    });

  const initializeBuild = () =>
    withBusy("phase32", async () => {
      if (!ensureProject()) return;
      const data = await api.initializeBuildPhase32(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "32": data.acceptance });
      setActivePhase("32");
      setStatus("Faza 32: budowa zainicjowana.");
    });

  const startExecution = () =>
    withBusy("phase33", async () => {
      if (!ensureProject()) return;
      const data = await api.startSequentialExecutionPhase33(projectId as string, actionBody);
      setProject(data.project);
      setDispatchControl(data.dispatch_control || data.project?.execution?.dispatch_control || null);
      setAcceptance({ ...acceptance, "33": data.acceptance });
      setActivePhase("33");
      setStatus("Faza 33: wykonanie sekwencyjne rozpoczęte.");
    });

  const refreshDispatchControl = () =>
    withBusy("dispatch-refresh", async () => {
      if (!ensureProject()) return;
      const data = await api.getExecutionDispatchControl(projectId as string);
      setDispatchControl(data.dispatch_control || null);
      setStatus(`Dispatch: ${data.dispatch_control?.state || "not_started"}.`);
    });

  const pauseDispatch = () =>
    withBusy("dispatch-pause", async () => {
      if (!ensureProject()) return;
      const data = await api.pauseExecutionDispatch(projectId as string, { ...actionBody, reason: operatorNotes });
      setProject(data.project);
      setDispatchControl(data.dispatch_control || data.project?.execution?.dispatch_control || null);
      setAcceptance({ ...acceptance, "33": data.acceptance });
      setActivePhase("33");
      setStatus("Dispatch phase33 zatrzymany przez operatora.");
    });

  const resumeDispatch = () =>
    withBusy("dispatch-resume", async () => {
      if (!ensureProject()) return;
      const data = await api.resumeExecutionDispatch(projectId as string, { ...actionBody, reason: operatorNotes });
      setProject(data.project);
      setDispatchControl(data.dispatch_control || data.project?.execution?.dispatch_control || null);
      setAcceptance({ ...acceptance, "33": data.acceptance });
      setActivePhase("33");
      setStatus("Dispatch phase33 wznowiony.");
    });

  const cancelDispatch = () =>
    withBusy("dispatch-cancel", async () => {
      if (!ensureProject()) return;
      const data = await api.cancelExecutionDispatch(projectId as string, { ...actionBody, reason: operatorNotes });
      setProject(data.project);
      setDispatchControl(data.dispatch_control || data.project?.execution?.dispatch_control || null);
      setAcceptance({ ...acceptance, "33": data.acceptance });
      setActivePhase("33");
      setStatus("Dispatch phase33 anulowany i zapisany w W18.");
    });

  const refreshLiveWorkers = () =>
    withBusy("live-refresh", async () => {
      if (!ensureProject()) return;
      const data = await api.getExecutionLiveWorkers(projectId as string);
      setLiveSpawn(data.live_spawn || null);
      setStatus(`Live worker status: ${data.live_spawn?.running || 0}/${data.live_spawn?.total || 0} uruchomionych.`);
    });

  const startLiveWorkers = () =>
    withBusy("live-start", async () => {
      if (!ensureProject()) return;
      const data = await api.liveSpawnExecutionWorkers(projectId as string, {
        approved: true,
        operator_id: "operator",
        notes: operatorNotes,
        workers_limit: 2,
        duration_seconds: 30,
        mode: "smoke",
        allow_docker_run: false,
      });
      setProject(data.project);
      setLiveSpawn(data.live_spawn || null);
      setStatus(`Live smoke workers uruchomieni: ${data.live_spawn?.running || 0}/${data.live_spawn?.total || 0}.`);
    });

  const stopLiveWorkers = () =>
    withBusy("live-stop", async () => {
      if (!ensureProject()) return;
      const data = await api.stopExecutionLiveWorkers(projectId as string, actionBody);
      setProject(data.project);
      setLiveSpawn(data.live_spawn || null);
      setStatus(`Live smoke workers zatrzymani: ${data.live_spawn?.running || 0}/${data.live_spawn?.total || 0} nadal uruchomionych.`);
    });

  const reconveneCouncil = () =>
    withBusy("phase34", async () => {
      if (!ensureProject()) return;
      const data = await api.reconveneMidBuildCouncilPhase34(projectId as string, {
        ...actionBody,
        trigger: "customer_scope_change",
        issue_title: "Klient prosi o dodanie płatności subskrypcyjnych w trakcie budowy",
        impact_category: "impact_1_no_current_build_change",
      });
      setProject(data.project);
      setAcceptance({ ...acceptance, "34": data.acceptance });
      setActivePhase("34");
      setStatus("Faza 34: decyzja rady w trakcie budowy zapisana.");
    });

  const activateOrchestration = () =>
    withBusy("phase35", async () => {
      if (!ensureProject()) return;
      const data = await api.activateOrchestrationPhase35(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "35": data.acceptance });
      setActivePhase("35");
      setStatus("Faza 35: wewnętrzna pętla orkiestracji aktywna.");
    });

  const completeBuild = () =>
    withBusy("phase36", async () => {
      if (!ensureProject()) return;
      const data = await api.completeBuildPhase36(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "36": data.acceptance });
      setActivePhase("36");
      setStatus("Faza 36: budowa zakończona. Projekt gotowy do bramek jakości.");
    });

  const runQualityGates = () =>
    withBusy("phase37", async () => {
      if (!ensureProject()) return;
      const data = await api.runQualityGatesPhase37(projectId as string, actionBody);
      setProject(data.project);
      setAcceptance({ ...acceptance, "37": data.acceptance });
      setActivePhase("37");
      setStatus("Faza 37: bramki jakości zaliczone.");
    });

  const completeAcceptanceTesting = () =>
    withBusy("phase38", async () => {
      if (!ensureProject()) return;
      const data = await api.completeAcceptanceTestingPhase38(projectId as string, {
        ...actionBody,
        customer_representative: "Anna Kowalska, CTO",
        review_window_days: 5,
        signoff_text: "Akceptuję wdrożenie produkcyjne",
      });
      setProject(data.project);
      setAcceptance({ ...acceptance, "38": data.acceptance });
      setActivePhase("38");
      setStatus("Faza 38: podpis akceptacyjny klienta otrzymany.");
    });

  const authorizePredeploy = () =>
    withBusy("phase39", async () => {
      if (!ensureProject()) return;
      const data = await api.authorizePredeployPhase39(projectId as string, {
        ...actionBody,
        domain: "crm.customer-y.pl",
        deploy_day: "2026-06-25",
        authorization_option: "authorize_phase_40",
      });
      setProject(data.project);
      setAcceptance({ ...acceptance, "39": data.acceptance });
      setActivePhase("39");
      setStatus("Faza 39: kontrola przed wydaniem autoryzowana. Projekt gotowy do wdrożenia albo lokalnej próby.");
    });

  const executeProductionDeploy = () =>
    withBusy("phase40", async () => {
      if (!ensureProject()) return;
      const data = await api.executeProductionDeployPhase40(projectId as string, {
        ...actionBody,
        domain: "crm.customer-y.pl",
        deploy_day: "2026-06-25",
        strategy: "canary",
      });
      setProject(data.project);
      setAcceptance({ ...acceptance, "40": data.acceptance });
      setActivePhase("40");
      setStatus("Faza 40: wdrożenie albo lokalna próba wydania zapisane i stabilne.");
    });

  const closeProject = () =>
    withBusy("phase41", async () => {
      if (!ensureProject()) return;
      const data = await api.closeProjectPhase41(projectId as string, {
        ...actionBody,
        closed_date: "2026-06-27",
        warranty_start: "2026-06-27",
        warranty_end: "2026-07-27",
        final_invoice_number: "INV-2026-06-001",
      });
      setProject(data.project);
      setAcceptance({ ...acceptance, "41": data.acceptance });
      setActivePhase("41");
      setStatus("Faza 41: projekt zamknięty.");
    });

  const runAcceptance = () =>
    withBusy(`accept-${activePhase}`, async () => {
      if (!ensureProject()) return;
      const data = await api.runExecutionStartAcceptanceTest(projectId as string, activePhase);
      setAcceptance({ ...acceptance, [activePhase]: data });
      setStatus(`Faza ${activePhase}: test akceptacyjny ${data.accepted ? "zaakceptowany" : "zablokowany"}.`);
    });

  const diagnose = () =>
    withBusy(`diag-${activePhase}`, async () => {
      if (!ensureProject()) return;
      const caseId = activeEdgeCases[0]?.id || "EC-A1";
      const data = await api.diagnoseExecutionStartEdgeCase(projectId as string, {
        phase: activePhase,
        case_id: caseId,
        context: { surface: "execution-start-dashboard", state: stateLabel },
      });
      setDiagnosis(data);
      setStatus(`Zdiagnozowano ${data.case?.id || caseId}.`);
    });

  return (
    <div className="min-h-screen bg-background px-5 py-5 text-foreground lg:px-8">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">GRUPA E-F-G</Badge>
              <Badge variant={groupComplete ? "default" : "secondary"}>{groupComplete ? "PROJEKT ZAMKNIĘTY" : "WYKONANIE AKTYWNE"}</Badge>
              <Badge variant={backendLive || backendChecking ? "default" : "destructive"}>
                {backendLive ? "API DZIAŁA" : backendChecking ? "SPRAWDZAM API" : "API OFFLINE"}
              </Badge>
              <HelpTip text={HELP.header} side="bottom" />
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight md:text-3xl">Start wykonania</h1>
            <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
              Fazy 32-41 zamieniają zatwierdzony plan w budowę, testują ją L1-L5,
              przechodzą kontrolowane wdrożenie stopniowe i zamykają projekt z raportami,
              archiwum oraz gwarancją.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading || Boolean(busy)}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Odśwież
            </Button>
            <Button variant="outline" onClick={() => { window.location.href = "/planning"; }}>
              Planowanie
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
          <Metric label="Zaakceptowane fazy" value={`${acceptedCount}/10`} tone={groupComplete ? "green" : "amber"} help={HELP.metrics} />
              <Metric label="Wykonawcy" value={safeList(initialization.workers).length || 0} help="Liczba aktywowanych wykonawców przypisanych do budowy." />
          <Metric label="Środowiska" value={safeList(initialization.environments).length || 0} help="Liczba środowisk przygotowanych dla budowy, testów klienta i produkcji." />
          <Metric label="Dostępność / zaliczenie" value={productionDeploy.observation_24h?.uptime_percent ? `${productionDeploy.observation_24h.uptime_percent}%` : qualityGates.summary?.pass_rate_percent ? `${qualityGates.summary.pass_rate_percent}%` : progress.total_progress_percent ? `${progress.total_progress_percent}%` : "0%"} help="Po wdrożeniu pokazuje dostępność z obserwacji 24h. Wcześniej pokazuje wskaźnik zaliczenia bramek jakości albo postęp budowy." />
          <Metric
            label="Stan"
            value={formatStateForProject(stateLabel, localOnlyProject)}
            help="Stan lifecycle projektu po stronie backendu, pokazany w języku operatora."
            tone={stateLabel === "CLOSED" || stateLabel === "DEPLOYED" || stateLabel === "READY_FOR_PRODUCTION_DEPLOY" || stateLabel === "READY_FOR_PREDEPLOY" || stateLabel === "READY_FOR_ACCEPTANCE_TESTING" || stateLabel === "BUILD_COMPLETE" || stateLabel === "BUILDING" ? "green" : "default"}
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(380px,0.95fr)]">
          <div className="flex flex-col gap-5">
            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="flex items-center gap-1 text-xs uppercase text-muted-foreground">
                    <span>Aktywny projekt</span>
                    <HelpTip text={HELP.activeProject} side="bottom" />
                  </div>
                  <div className="mt-1 truncate text-lg font-semibold">{displayProjectName}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">{projectId || "Najpierw zakończ grupę D"}</div>
                </div>
                <Badge variant={["BUILDING", "BUILD_COMPLETE", "READY_FOR_ACCEPTANCE_TESTING", "READY_FOR_PREDEPLOY", "READY_FOR_PRODUCTION_DEPLOY", "DEPLOYED", "CLOSED"].includes(stateLabel) ? "default" : "secondary"}>{formatStateForProject(stateLabel, localOnlyProject)}</Badge>
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle
                icon={Monitor}
                title="Konfiguracja runtime"
                help="Pozwala operatorowi jawnie ustawić liczbę lokalnych wykonawców, środowisk, limit równoległości i ewentualny udział VPS przed ponowną inicjalizacją fazy 32. Dla testów local-first ustaw VPS na 0."
              />
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <label className="text-xs font-medium uppercase text-muted-foreground">
                  Topologia
                  <select
                    suppressHydrationWarning
                    data-testid="runtime-topology"
                    value={runtimeForm.topology}
                    onChange={(event) => setRuntimeField("topology", event.target.value)}
                    className="mt-1 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm normal-case outline-none focus:border-primary"
                  >
                    <option value="local-first">local-first</option>
                    <option value="local-only">local-only</option>
                    <option value="local-plus-vps">local + VPS</option>
                  </select>
                </label>
                <label className="text-xs font-medium uppercase text-muted-foreground">
                  Lokalni wykonawcy
                  <input
                    suppressHydrationWarning
                    data-testid="runtime-local-workers"
                    type="number"
                    min={1}
                    max={60}
                    value={runtimeForm.local_workers}
                    onChange={(event) => setRuntimeField("local_workers", event.target.value)}
                    className="mt-1 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm normal-case outline-none focus:border-primary"
                  />
                </label>
                <label className="text-xs font-medium uppercase text-muted-foreground">
                  Wykonawcy VPS
                  <input
                    suppressHydrationWarning
                    data-testid="runtime-vps-workers"
                    type="number"
                    min={0}
                    max={60}
                    value={runtimeForm.vps_workers}
                    onChange={(event) => setRuntimeField("vps_workers", event.target.value)}
                    className="mt-1 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm normal-case outline-none focus:border-primary"
                  />
                </label>
                <label className="text-xs font-medium uppercase text-muted-foreground">
                  Środowiska
                  <input
                    suppressHydrationWarning
                    data-testid="runtime-environments"
                    type="number"
                    min={1}
                    max={12}
                    value={runtimeForm.environments}
                    onChange={(event) => setRuntimeField("environments", event.target.value)}
                    className="mt-1 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm normal-case outline-none focus:border-primary"
                  />
                </label>
                <label className="text-xs font-medium uppercase text-muted-foreground">
                  Równoległość
                  <input
                    suppressHydrationWarning
                    data-testid="runtime-max-parallel"
                    type="number"
                    min={1}
                    max={60}
                    value={runtimeForm.max_parallel_workers}
                    onChange={(event) => setRuntimeField("max_parallel_workers", event.target.value)}
                    className="mt-1 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm normal-case outline-none focus:border-primary"
                  />
                </label>
                <label className="text-xs font-medium uppercase text-muted-foreground">
                  Limit VPS EUR/mies.
                  <input
                    suppressHydrationWarning
                    data-testid="runtime-monthly-cap"
                    type="number"
                    min={0}
                    max={10000}
                    value={runtimeForm.max_monthly_vps_eur}
                    onChange={(event) => setRuntimeField("max_monthly_vps_eur", event.target.value)}
                    className="mt-1 w-full rounded-md border border-sylion-border bg-background px-3 py-2 text-sm normal-case outline-none focus:border-primary"
                  />
                </label>
              </div>
              <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    suppressHydrationWarning
                    data-testid="runtime-allow-paid-vps"
                    type="checkbox"
                    checked={runtimeForm.allow_paid_vps}
                    onChange={(event) => setRuntimeField("allow_paid_vps", event.target.checked)}
                    className="h-4 w-4"
                  />
                  Zezwól na płatny VPS po osobnej zgodzie
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={runtimeConfiguration?.external_cost ? "destructive" : "secondary"}>
                    {runtimeConfiguration?.external_cost ? "koszt zewnętrzny" : "bez kosztu zewnętrznego"}
                  </Badge>
                  <Badge variant="outline">{runtimeConfiguration?.provisioning_state || "niezapisane"}</Badge>
                  <Button
                    data-testid="runtime-save"
                    variant="outline"
                    onClick={saveRuntimeConfiguration}
                    disabled={!projectId || Boolean(busy)}
                  >
                    {busy === "runtime-config" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Monitor className="mr-2 h-4 w-4" />}
                    Zapisz runtime
                  </Button>
                </div>
              </div>
            </Card>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {phases.map((phase) => {
                const Icon = phase.icon;
                const accepted = Boolean(acceptance[phase.id]?.accepted);
                const active = activePhase === phase.id;
                return (
                  <button
                    key={phase.id}
                    type="button"
                    onClick={() => setActivePhase(phase.id)}
                    title={phase.help}
                    className={cn("rounded-lg border p-4 text-left transition", active ? "border-primary bg-primary/10" : "border-sylion-border bg-card hover:border-primary/50")}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <Icon className={cn("h-5 w-5", accepted ? "text-sylion-green" : "text-muted-foreground")} />
                      <Badge variant={accepted ? "default" : "secondary"}>{accepted ? "ZALICZONA" : "OTWARTA"}</Badge>
                    </div>
                    <div className="mt-3 text-sm font-semibold">Faza {phase.id}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{phase.label}</div>
                  </button>
                );
              })}
            </div>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <CurrentPhaseIcon className="h-5 w-5 text-primary" />
                    <h2 className="text-lg font-semibold">Faza {activePhase}: {currentPhase.label}</h2>
                    <HelpTip text={currentPhase.help} side="bottom" />
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Kontrole akceptacyjne: {currentAcceptance.dod?.passed_required || 0}/{currentAcceptance.dod?.required || 0}.
                  </p>
                </div>
                <div className="min-w-0">
                  <div className="mb-2 flex items-center justify-start gap-2 lg:justify-end">
                    <span className="text-xs font-medium uppercase text-muted-foreground">Akcje operatora</span>
                    <HelpTip text={HELP.actions} side="left" />
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <Button onClick={initializeBuild} disabled={!projectId || Boolean(busy)} variant={activePhase === "32" ? "default" : "outline"}>
                      {busy === "phase32" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
                      Zainicjuj budowę
                    </Button>
                    <Button onClick={startExecution} disabled={!projectId || Boolean(busy)} variant={activePhase === "33" ? "default" : "outline"}>
                      {busy === "phase33" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                      Start wykonania
                    </Button>
                    <Button onClick={reconveneCouncil} disabled={!projectId || Boolean(busy)} variant={activePhase === "34" ? "default" : "outline"}>
                      {busy === "phase34" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Users className="mr-2 h-4 w-4" />}
                      Zwołaj radę
                    </Button>
                    <Button onClick={activateOrchestration} disabled={!projectId || Boolean(busy)} variant={activePhase === "35" ? "default" : "outline"}>
                      {busy === "phase35" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitBranch className="mr-2 h-4 w-4" />}
                      Uruchom orkiestrację
                    </Button>
                    <Button onClick={completeBuild} disabled={!projectId || Boolean(busy)} variant={activePhase === "36" ? "default" : "outline"}>
                      {busy === "phase36" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                      Zamknij budowę
                    </Button>
                    <Button onClick={runQualityGates} disabled={!projectId || Boolean(busy)} variant={activePhase === "37" ? "default" : "outline"}>
                      {busy === "phase37" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                      Bramki jakości
                    </Button>
                    <Button onClick={completeAcceptanceTesting} disabled={!projectId || Boolean(busy)} variant={activePhase === "38" ? "default" : "outline"}>
                      {busy === "phase38" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TestTube2 className="mr-2 h-4 w-4" />}
                      Akceptacja klienta
                    </Button>
                    <Button onClick={authorizePredeploy} disabled={!projectId || Boolean(busy)} variant={activePhase === "39" ? "default" : "outline"}>
                      {busy === "phase39" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Monitor className="mr-2 h-4 w-4" />}
                      Zatwierdź kontrolę
                    </Button>
                    <Button onClick={executeProductionDeploy} disabled={!projectId || Boolean(busy)} variant={activePhase === "40" ? "default" : "outline"}>
                      {busy === "phase40" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
                      Wdrożenie / próba
                    </Button>
                    <Button onClick={closeProject} disabled={!projectId || Boolean(busy)} variant={activePhase === "41" ? "default" : "outline"}>
                      {busy === "phase41" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                      Zamknij projekt
                    </Button>
                    <Button variant="outline" onClick={runAcceptance} disabled={!projectId || Boolean(busy)}>
                      {busy === `accept-${activePhase}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TestTube2 className="mr-2 h-4 w-4" />}
                      Test akceptacyjny
                    </Button>
                    <Button variant="outline" onClick={diagnose} disabled={!projectId || Boolean(busy)}>
                      {busy === `diag-${activePhase}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                      Diagnozuj
                    </Button>
                  </div>
                </div>
              </div>

              <label className="mt-4 flex items-center gap-1 text-xs font-medium uppercase text-muted-foreground">
                Notatki operatora
                <HelpTip text="Notatka trafia do żądania fazy jako kontekst zatwierdzenia operatora. Nie wpisuj tu sekretów ani danych wrażliwych." side="top" />
              </label>
              <textarea
                suppressHydrationWarning
                value={operatorNotes}
                onChange={(event) => setOperatorNotes(event.target.value)}
                className="mt-2 min-h-20 w-full resize-y rounded-md border border-sylion-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={Users} title="Wykonawcy i środowiska" help="Pokazuje wykonawców oraz środowiska utworzone przy inicjalizacji budowy. Braki w tej sekcji zwykle oznaczają, że faza 32 nie została jeszcze uruchomiona." />
              <div className="grid gap-2 md:grid-cols-2">
                {safeList<BuildWorker>(initialization.workers).map((worker, index) => {
                  const workerId = worker.id || worker.worker_id || `worker_${index + 1}`;
                  const workerRole = worker.domain || worker.role || worker.module || "lokalny wykonawca";
                  return <MiniRow key={workerId} label={workerId} value={`${workerRole} / ${formatStatus(worker.status)}`} />;
                })}
                {safeList<BuildEnvironment>(initialization.environments).map((env, index) => {
                  const envId = env.id || env.environment_id || env.label || `env_${index + 1}`;
                  const envType = env.type || env.target || env.label || "local";
                  return <MiniRow key={envId} label={envId} value={`${envType} / ${formatStatus(env.status)}`} />;
                })}
                {!safeList(initialization.workers).length && <div className="text-sm text-muted-foreground">Wykonawcy nie są jeszcze aktywni.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <SectionTitle icon={Monitor} title="Live smoke workers" help="Kontrolowany start/stop lokalnych procesow smoke worker. Ten flow nie uruchamia Dockera, VPS ani kosztow zewnetrznych." />
                  <div className="grid gap-2 md:grid-cols-2">
                    <MiniRow label="Backend" value={liveSpawn?.backend || "oczekuje"} />
                    <MiniRow label="Uruchomione" value={`${liveRunning}/${liveTotal}`} />
                    <MiniRow label="Tryb / czas" value={liveSpawn?.mode ? `${liveSpawn.mode} / ${liveSpawn.duration_seconds || 0}s` : "oczekuje"} />
                    <MiniRow label="Koszty zewnetrzne" value={liveSpawn?.safety?.external_cost || liveSpawn?.safety?.hetzner || liveSpawn?.safety?.docker_run ? "blokuj" : "brak"} />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 lg:justify-end">
                  <Button onClick={startLiveWorkers} disabled={!projectId || Boolean(busy) || liveRunning > 0} variant="outline">
                    {busy === "live-start" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                    Start live
                  </Button>
                  <Button onClick={stopLiveWorkers} disabled={!projectId || Boolean(busy) || liveTotal === 0} variant="outline">
                    {busy === "live-stop" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Square className="mr-2 h-4 w-4" />}
                    Stop live
                  </Button>
                  <Button onClick={refreshLiveWorkers} disabled={!projectId || Boolean(busy)} variant="outline">
                    {busy === "live-refresh" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    Odswiez
                  </Button>
                </div>
              </div>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                {liveSessions.map((session, index) => (
                  <MiniRow
                    key={`${session.worker_id || "worker"}-${session.pid || index}`}
                    label={session.worker_id || session.session_name || `worker_${index + 1}`}
                    value={`${session.state || "unknown"} / pid ${session.pid || "-"} / logi ${session.log_lines ?? 0}`}
                  />
                ))}
                {!liveSessions.length && <div className="text-sm text-muted-foreground">Brak live smoke worker sessions.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <SectionTitle icon={GitBranch} title="Dispatch control" help="Pauza, wznowienie i anulowanie phase33 przez centralny wlasciciel komend. Status pokazuje, kto rzadzi komenda i do jakiego zakresu projektu trafia." />
                  <div className="grid gap-2 md:grid-cols-2">
                    <MiniRow label="Stan" value={formatStatus(dispatchState)} />
                    <MiniRow label="Run" value={dispatch.run_id || "oczekuje"} />
                    <MiniRow label="Owner" value={dispatch.owner || dispatchRules.active_route_owner || "execution_start.dispatch_control"} />
                    <MiniRow label="Target" value={dispatchRules.target_resolution || "project -> phase33 -> workers"} />
                    <MiniRow label="Worker pool" value={(dispatchRules.worker_pool || []).length ? `${dispatchRules.worker_pool?.length} aktywnych` : "oczekuje"} />
                    <MiniRow label="Env pool" value={(dispatchRules.environment_pool || []).length ? `${dispatchRules.environment_pool?.length} lokalnych` : "oczekuje"} />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 lg:justify-end">
                  <Button onClick={pauseDispatch} disabled={!projectId || Boolean(busy) || dispatch.controls_available?.pause === false || dispatchState !== "running"} variant="outline">
                    {busy === "dispatch-pause" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Pause className="mr-2 h-4 w-4" />}
                    Pauza
                  </Button>
                  <Button onClick={resumeDispatch} disabled={!projectId || Boolean(busy) || dispatch.controls_available?.resume === false || dispatchState !== "paused"} variant="outline">
                    {busy === "dispatch-resume" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                    Wznow
                  </Button>
                  <Button onClick={cancelDispatch} disabled={!projectId || Boolean(busy) || dispatch.controls_available?.cancel === false || !["running", "paused"].includes(String(dispatchState))} variant="outline">
                    {busy === "dispatch-cancel" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Square className="mr-2 h-4 w-4" />}
                    Anuluj
                  </Button>
                  <Button onClick={refreshDispatchControl} disabled={!projectId || Boolean(busy)} variant="outline">
                    {busy === "dispatch-refresh" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    Odswiez
                  </Button>
                </div>
              </div>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <MiniRow label="Model/agent rule" value={dispatchRules.model_agent_rule || "project scoped"} />
                <MiniRow label="External rule" value={dispatchRules.external_runtime_rule || "blocked until Human Gate"} />
                {dispatchEvents.map((event, index) => (
                  <MiniRow key={`${event.event || "dispatch"}-${index}`} label={event.command || event.event || "event"} value={`${event.previous_state || "-"} -> ${event.state || "-"}`} />
                ))}
                {!dispatchEvents.length && <div className="text-sm text-muted-foreground">Brak zdarzen dispatch control.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={GitBranch} title="Dowody pracy workerów" help="Realne lokalne runy workerów zapisują artefakty, logi, diffy i wyniki testów. Ta sekcja odróżnia wykonanie udokumentowane od samego statusu procesu." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Run" value={workerEvidence.run_id || "oczekuje"} />
                <MiniRow label="Wykonawcy zakończeni" value={workerEvidence.workers_completed ?? "oczekuje"} />
                <MiniRow label="Artefakty / diffy" value={workerEvidence.artifacts_written !== undefined ? `${workerEvidence.artifacts_written} / ${workerEvidence.diffs_written ?? 0}` : "oczekuje"} />
                <MiniRow label="Logi / testy" value={workerEvidence.logs_written !== undefined ? `${workerEvidence.logs_written} / ${workerEvidence.tests_passed ?? 0}` : "oczekuje"} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={Monitor} title="Wykonanie sekwencyjne" help="Podgląd faz budowy uruchamianych po kolei. Każdy wiersz pokazuje status i koszt zapisany przez backend." />
              <div className="space-y-2">
                {safeList<BuildPhase>(progress.build_phases).map((phase, index) => (
                  <MiniRow key={phase.id || `phase_${index + 1}`} label={formatPhaseTitle(phase.title)} value={`${formatStatus(phase.status)} / ${formatUsdValue(phase.cost_usd)}`} />
                ))}
                {!safeList(progress.build_phases).length && <div className="text-sm text-muted-foreground">Pętla wykonania nie została jeszcze uruchomiona.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={Users} title="Rada i orkiestracja w trakcie budowy" help="Sekcja pokazuje, czy rada została zwołana z właściwego powodu oraz czy orkiestracja wykonawców działa po decyzji." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Sesja rady" value={midBuildCouncil.session_id || "oczekuje"} />
                <MiniRow label="Decyzja rady" value={formatImpact(midBuildCouncil.decision?.impact_category)} />
                <MiniRow label="Orkiestracja" value={orchestration.active ? "aktywna" : "oczekuje"} />
                <MiniRow label="Zadania ukończone" value={orchestration.lifetime_stats?.tasks_completed ? `${orchestration.lifetime_stats.tasks_completed}/47` : "oczekuje"} />
                <MiniRow label="Ważony wynik rady" value={weightedVote.weighted_score !== undefined ? `${weightedVote.weighted_score}/${weightedVote.total_weight}` : "oczekuje"} />
                <MiniRow label="Adversarial critic" value={weightedVote.adversarial_critic?.signed ? `podpisany / waga ${weightedVote.adversarial_critic.weight}` : "oczekuje"} />
                <MiniRow label="Governance veto" value={governanceVeto.enabled ? (governanceVeto.active ? `aktywne: ${(governanceVeto.veto_roles || []).join(", ")}` : "sprawdźone, brak veta") : "oczekuje"} />
                <MiniRow label="Human Gate" value={weightedVote.human_gate_required || midBuildCouncil.decision?.human_gate_required ? "wymagany dla zmiany" : "brak blokady"} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={ShieldCheck} title="Mapa prawdy modułów" help="Klasyfikacja modułów według dowodów runtime: LIVE_VERIFIED, PARTIAL, UI_ONLY, API_ONLY, SIMULATED albo BROKEN. Dokumentacja nie wygrywa z runtime." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Moduły" value={truthMap.coverage?.modules_total ?? "oczekuje"} />
                <MiniRow label="LIVE_VERIFIED" value={truthMap.coverage ? `${truthMap.coverage.live_verified ?? 0} / ${truthMap.coverage.live_verified_percent ?? 0}%` : "oczekuje"} />
                <MiniRow label="PARTIAL / SIMULATED" value={`${truthCounts.PARTIAL ?? 0} / ${truthCounts.SIMULATED ?? 0}`} />
                <MiniRow label="API_ONLY / UI_ONLY / BROKEN" value={`${truthCounts.API_ONLY ?? 0} / ${truthCounts.UI_ONLY ?? 0} / ${truthCounts.BROKEN ?? 0}`} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={CheckCircle2} title="Zamknięcie budowy" help="Finalne podsumowanie artefaktów, kosztu, spójności i wygaszania wykonawców przed testami jakości." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Wygenerowane pliki" value={completion.artifacts_inventory?.total_files || 0} />
                <MiniRow label="Koszt rzeczywisty budowy" value={formatUsdValue(completion.cost_reconciliation?.build_actual_usd)} />
                <MiniRow label="Końcowa spójność" value={formatStatus(completion.final_coherence?.status)} />
                <MiniRow label="Wykonawcy wygaszeni" value={completion.worker_decommissioning ? `${completion.worker_decommissioning.decommissioned}/${completion.worker_decommissioning.expected}` : "oczekuje"} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={ShieldCheck} title="Bramki jakości" help="Wynik testów jakościowych i technicznych. Ta sekcja decyduje, czy projekt może przejść do akceptacji klienta." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Testy efektywne" value={qualityGates.summary ? `${qualityGates.summary.functional_passed_effective}/${qualityGates.summary.functional_tests_effective}` : "oczekuje"} />
                <MiniRow label="Wskaźnik zaliczenia" value={qualityGates.summary?.pass_rate_percent ? `${qualityGates.summary.pass_rate_percent}%` : "oczekuje"} />
                <MiniRow label="Pokrycie" value={qualityGates.coverage?.l1_percent ? `${qualityGates.coverage.l1_percent}%` : "oczekuje"} />
                <MiniRow label="Werdykt" value={formatStatus(qualityGates.summary?.quality_guard_verdict)} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={TestTube2} title="Akceptacja klienta" help="Widok środowiska testówego, zebranych uwag, poprawek oraz formalnego podpisu akceptacyjnego klienta." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Środowisko testówe" value={acceptanceTesting.staging_deployment?.deployed ? "wdrożone" : "oczekuje"} />
                <MiniRow label="Uwagi" value={acceptanceTesting.feedback?.total ? `${acceptanceTesting.feedback.total} pozycji` : "oczekuje"} />
                <MiniRow
                  label="Naprawione / odroczone"
                  value={
                    acceptanceTesting.resolution
                      ? `${(acceptanceTesting.resolution.important_fixed ?? 0) + (acceptanceTesting.resolution.minor_fixed ?? 0)} naprawione / ${acceptanceTesting.resolution.feature_requests_deferred ?? 0} odroczone`
                      : "oczekuje"
                  }
                />
                <MiniRow label="Podpis akceptacyjny" value={acceptanceTesting.signoff?.received ? "otrzymany" : "oczekuje"} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={Monitor} title="Finalna bramka przed wydaniem" help="Ostatnie potwierdzenie środowiska docelowego, rollbacku, monitoringu, obsługi klienta i autoryzacji. Dla projektu local-only pozostaje lokalne." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Środowisko docelowe" value={predeploy.production_environment?.provisioned ? `${predeploy.production_environment.provider} ${predeploy.production_environment.region}` : "oczekuje"} />
                <MiniRow label="Cel / domena" value={predeploy.dns?.domain || "oczekuje"} />
                <MiniRow label="Test wycofania" value={predeploy.deploy_plan?.rollback_test?.tested_in_staging ? `${predeploy.deploy_plan.rollback_test.rollback_minutes} min` : "oczekuje"} />
                <MiniRow label="Autoryzacja" value={predeploy.authorization?.approved ? "podpisana" : "oczekuje"} />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={Rocket} title="Wdrożenie / próba lokalna" help="Faza 40 zapisuje kontrolowane wdrożenie albo lokalny release rehearsal jako artefakty: etapy, rollback, monitoring 24h i dowód braku niezatwierdzonych akcji zewnętrznych." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Etapy wydania" value={safeList<CanaryStage>(productionDeploy.canary_stages).length ? `${safeList<CanaryStage>(productionDeploy.canary_stages).filter((stage) => stage.verdict === "PASS").length}/4 zaliczone` : "oczekuje"} />
                <MiniRow label="Zakres ruchu" value={productionDeploy.serving_traffic ? (productionDeploy.external_effects?.mode === "local_release_rehearsal_no_external_calls" ? "100% lokalny rehearsal" : "100% produkcja") : "oczekuje"} />
                <MiniRow label="Dostępność 24h" value={productionDeploy.observation_24h?.uptime_percent ? `${productionDeploy.observation_24h.uptime_percent}%` : "oczekuje"} />
                <MiniRow
                  label="Integracje"
                  value={
                    productionDeploy.observation_24h
                      ? `${productionDeploy.observation_24h.documents_processed ?? productionDeploy.observation_24h.invoices_ksef_accepted ?? 0} dokumentów / ${
                          productionDeploy.observation_24h.financial_events ?? productionDeploy.observation_24h.successful_payments ?? 0
                        } płatności`
                      : "oczekuje"
                  }
                />
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={CheckCircle2} title="Zamknięcie projektu" help="Faza 41 zamyka projekt operacyjnie: raporty, archiwum, fakturę lub blokadę faktury, gwarancję i decyzję o promowaniu umiejętności." />
              <div className="grid gap-2 md:grid-cols-2">
                <MiniRow label="Raporty" value={projectClosure.reports?.operator_report_generated ? "operator + klient" : "oczekuje"} />
                <MiniRow label="Promowane umiejętności" value={projectClosure.skills?.promoted ? projectClosure.skills.promoted.length : "oczekuje"} />
                <MiniRow label="Koszt / zysk końcowy" value={projectClosure.cost_reconciliation ? `${formatUsdValue(projectClosure.cost_reconciliation.final_actual_usd)} / ${formatUsdValue(projectClosure.cost_reconciliation.operator_profit_usd)}` : "oczekuje"} />
                <MiniRow label="Gwarancja" value={projectClosure.warranty?.started ? `${projectClosure.warranty.start} - ${projectClosure.warranty.end}` : "oczekuje"} />
              </div>
            </Card>
          </div>

          <div className="flex flex-col gap-5">
            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={GitBranch} title="Akceptacja" help={HELP.acceptance} />
              <div className="mt-4 space-y-3">
                {safeList<AcceptanceCheck>(currentAcceptance.checks).map((check, index) => (
                  <div key={check.id || `check_${index + 1}`} className="flex gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-sm">
                    <StatusIcon status={typeof check.status === "string" ? check.status : undefined} />
                    <div className="min-w-0">
                      <div className="font-medium">{formatAcceptanceLabel(check.label)}</div>
                      <div className="mt-1 truncate text-xs text-muted-foreground">{formatEvidence(check.evidence)}</div>
                    </div>
                  </div>
                ))}
                {!safeList(currentAcceptance.checks).length && <div className="text-sm text-muted-foreground">Uruchom fazę albo test akceptacyjny, aby zobaczyć kontrole.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={ShieldCheck} title="Strażnicy" help={HELP.guards} />
              <div className="mt-4 space-y-2">
                {Object.entries(progress.guards || {}).map(([key, value]) => (
                  <MiniRow key={key} label={formatGuardName(key)} value={formatStatus(value?.status)} />
                ))}
                {!Object.keys(progress.guards || {}).length && <div className="text-sm text-muted-foreground">Brak telemetrii strażników.</div>}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <SectionTitle icon={AlertTriangle} title="Przypadki brzegowe" help={HELP.edgeCases} tone="amber" />
              <div className="mt-4 grid gap-2">
                {activeEdgeCases.slice(0, 8).map((item, index) => (
                  <div key={item.id || `edge_${index + 1}`} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{item.id}</span>
                      <Badge variant={item.severity === "high" ? "destructive" : "secondary"}>{formatSeverity(item.severity)}</Badge>
                    </div>
                    <div className="mt-1 font-medium text-muted-foreground">{formatEdgeCategory(item.category)}</div>
                    <div className="mt-1 text-muted-foreground">{formatEdgeTitle(item.title)}</div>
                  </div>
                ))}
              </div>
              {diagnosis && (
                <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                  <div className="font-semibold">Ostatnia diagnoza: {diagnosis.case?.id}</div>
                  <div className="mt-1 text-muted-foreground">{formatEdgeTitle(diagnosis.case?.title)}</div>
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
