"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { HelpTip } from "@/components/common/HelpTip";
import {
  FolderKanban,
  GitBranch,
  Shield,
  Wallet,
  RefreshCw,
  AlertTriangle,
  Loader2,
  Snowflake,
  ExternalLink,
  MessageSquare,
  UsersRound,
  ArrowRight,
  Send,
  Play,
  Sparkles,
  CheckCircle2,
  Upload,
  TerminalSquare,
  BookOpen,
  ListChecks,
} from "lucide-react";

type ProjectDetail = {
  title?: string;
  idea?: string;
  project_kind?: string;
  phase?: string;
  status?: string;
  cost_cap_usd?: number | null;
  autonomy_level?: string | null;
  execution_plan?: {
    budget_usd?: number | null;
    hard_limit_usd?: number | null;
    cap_usd?: number | null;
  };
  governance_policy?: {
    autonomy_mode?: string | null;
    level?: string | null;
  };
  canonical_book?: string;
  masterplan?: string;
  build_authorized_at?: number | null;
  launch?: {
    artifact_path?: string;
    artifact_sha256?: string;
    status?: string;
  };
  // FE-2 / FE-3: freeze gates (epoch seconds — set by BE-1 / BE-2 on success)
  canon_frozen_at?: number | null;
  masterplan_frozen_at?: number | null;
  approvals?: {
    book?: boolean;
    operating_model?: boolean;
    book_pending_ticket_id?: string;
    operating_model_pending_ticket_id?: string;
    build_pending_ticket_id?: string;
  };
  attachments?: ProjectAttachment[];
  source_idea_id?: string;
};
type ProjectAttachment = {
  attachment_id: string;
  idea_id?: string;
  filename?: string;
  file_type?: string;
  file_size?: number;
  analysis?: ProjectAttachmentAnalysis[];
};
type ProjectAttachmentAnalysis = {
  analysis_id?: string;
  attachment_id?: string;
  detected_kind?: string;
  extracted_text_preview?: string;
  tags?: string[];
  risks?: string[];
  missing_info?: string[];
  suggested_skills?: string[];
  decision_class?: string;
  human_gate_required?: boolean;
};
type TimelineStage = {
  stage?: string;
  updated_at?: number;
  status?: string;
};
type PendingQuestion = {
  question_id: string;
  context?: string;
  phase?: string;
  key?: string;
  choices?: PendingChoice[];
  free_text_allowed?: boolean;
};
type PendingChoice = {
  choice_id: string;
  label?: string;
  rationale?: string;
  consequences?: string;
};
type ProjectCanon = {
  book?: string;
};
type ProjectMasterplan = {
  summary?: string;
};
type ProjectModule = {
  module_id: string;
  name?: string;
  status?: string;
  host_target?: string;
  docker_profile?: string;
};
type AuditResult = {
  audit_result_id: string;
  audit_type?: string;
  status?: string;
  executed_at?: number;
};
type CostEntry = {
  cost_entry_id: string;
  provider?: string;
  model?: string;
  timestamp?: number;
  cost_usd?: number;
};
type CostLedger = {
  running_total?: number;
  records: CostEntry[];
};
type ProjectCouncilSession = {
  session_id: string;
  topic?: string;
  phase?: string;
  status?: string;
  context?: string;
  created_at?: number;
  consolidated_text?: string;
  consolidated?: {
    consolidated_text?: string;
    consensus_level?: number;
  } | null;
  analyses?: ProjectCouncilAnalysis[];
  discussion?: ProjectCouncilRound[];
};
type ProjectCouncilAnalysis = {
  model_id?: string;
  verdict?: string;
  confidence?: number;
  rationale?: string;
  analysis_text?: string;
  project_purpose?: unknown;
  how_it_works?: unknown;
  documentation_findings?: unknown;
  functional_inventory?: unknown;
  module_map?: unknown;
  evidence_matrix?: unknown;
  runtime_deploy_assessment?: unknown;
  sandbox_test_plan?: unknown;
  runtime_blockers?: unknown;
  implemented_vs_unclear?: unknown;
  functionality_gaps?: unknown;
  file_observations?: unknown;
  decision_options?: unknown;
  council_questions?: unknown;
  source_of_truth_candidates?: unknown;
};
type ProjectCouncilRound = {
  round_number?: number;
  model_id?: string;
  contribution?: string;
};
type CouncilTerminalLine = {
  speaker: string;
  text: string;
  kind: "operator" | "analysis" | "discussion" | "conclusion";
};
type ProjectTerminalLine = {
  role: "system" | "operator" | "aeis" | "error";
  text: string;
};
type ProjectTerminalResult = {
  kind?: string;
  text?: string;
  rows?: unknown[];
  headers?: string[];
  target?: string;
};
type ProjectAttachmentUploadResult = {
  uploadedNames: string[];
  skippedNames: string[];
  error?: string;
};
type ProjectCouncilRoleSpec = {
  title: string;
  mission: string;
  does: string[];
  choices: string[];
  guardrail?: string;
};
type CouncilOperatorChoice = {
  label: string;
  text: string;
  source: string;
  kind: "variant" | "question";
};
type CouncilStageId = "idea" | "models" | "analysis" | "discussion" | "proposal" | "book";
type CouncilProcessStep = {
  id: CouncilStageId;
  title: string;
  body: string;
  status: string;
};

function fmt(ts?: number): string {
  if (!ts) return "brak daty";
  return new Date(ts * 1000).toLocaleString("pl-PL", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const STAGE_LABELS: Record<string, string> = {
  ingest: "Przyjęcie",
  canon: "Księga / Źródło Prawdy",
  masterplan: "Masterplan",
  build_authorization: "Autoryzacja budowy",
  build_in_progress: "Budowa w toku",
  decomposition: "Dekompozycja",
  contract_freeze: "Zamrożenie kontraktu",
  assignment: "Przydział workerów",
  build: "Budowa",
  validate: "Walidacja",
  governance: "Nadzór",
  merge: "Scalenie",
  broadcast: "Publikacja zdarzeń",
  council_deliberation_rounds_complete: "Rundy deliberacji Rady zakończone",
  council_finalized: "Rada sfinalizowana",
  council_book_generated: "Księga Rady wygenerowana",
  council_book_signed: "Księga Rady podpisana",
  ksiega_finalized: "Księga sfinalizowana",
  models_assigned: "Modele przypisane",
  worker_run_evidence_attached_to_orchestration: "Dowody pracy workerów dołączone do orkiestracji",
  audit_truth_map_generated: "Mapa prawdy audytowej wygenerowana",
  build_complete: "Budowa zakończona",
  quality_gates_passed: "Bramki jakości zaliczone",
  customer_signoff_received: "Akceptacja odbiorcy zapisana",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "oczekuje",
  completed: "ukończone",
  complete: "ukończone",
  in_progress: "w toku",
  blocked: "zablokowane",
  failed: "nieudane",
  planned: "zaplanowane",
  draft: "szkic",
  active: "aktywne",
  definition_in_progress: "definicja w toku",
  definition_complete: "definicja ukończona",
  canon: "księga",
  masterplan: "masterplan",
};

const AUDIT_LABELS: Record<string, string> = {
  council_finalized: "Rada sfinalizowana",
  council_book_generated: "Księga Rady wygenerowana",
  council_book_signed: "Księga Rady podpisana",
  ksiega_finalized: "Księga sfinalizowana",
  models_assigned: "Modele przypisane",
  worker_run_evidence_attached_to_orchestration: "Dowody pracy workerów dołączone do orkiestracji",
  audit_truth_map_generated: "Mapa prawdy audytowej wygenerowana",
  build_complete: "Budowa zakończona",
  quality_gates_passed: "Bramki jakości zaliczone",
  customer_signoff_received: "Akceptacja odbiorcy zapisana",
  project_closed: "Projekt zamknięty",
  long_horizon_memory_synced: "Pamięć długoterminowa zsynchronizowana",
};

const PROJECT_COUNCIL_MODELS = ["gpt-4o-mini", "claude-haiku-4-5", "glm-4-plus"];
const PROJECT_ATTACHMENT_PREVIEW_LIMIT_CHARS = 52000;
const PROJECT_ATTACHMENT_CONTEXT_LIMIT_CHARS = 70000;
const PROJECT_COUNCIL_MODEL_LABELS: Record<string, string> = {
  "gpt-4o-mini": "OpenAI GPT-4o mini",
  "claude-haiku-4-5": "Claude Haiku 4.5",
  "glm-4-plus": "Z.ai GLM 4 Plus",
};
const COUNCIL_PHASE_LABELS: Record<string, string> = {
  parallel_analysis: "oczekuje na analizę",
  verdicts: "analizy gotowe",
  discussion: "dyskusja modeli",
  consolidated: "wniosek gotowy",
  closed: "zamknięta",
};

const COUNCIL_STAGE_LABELS: Record<CouncilStageId, string> = {
  idea: "Pomysł i materiały",
  models: "Kogo pytamy",
  analysis: "Analizy modeli",
  discussion: "Dyskusja modeli",
  proposal: "Warianty i wybór",
  book: "Księga robocza",
};
const PROJECT_TERMINAL_QUICK_COMMANDS = ["co dalej", "analizy", "dyskusja", "warianty", "role rady", "/status", "/pomoc"];
const PROJECT_TERMINAL_CAPABILITIES = [
  "komendy",
  "rozmowa",
  "decyzję",
  "log",
  "rada modeli",
  "księga",
  "bramki człowieka",
  "wykonanie",
];
const PROJECT_COUNCIL_ROLE_SPECS: ProjectCouncilRoleSpec[] = [
  {
    title: "Moderator W18",
    mission: "Prowadzi proces Rady i pilnuje formatu rundy.",
    does: ["ustawia etap", "zbiera odpowiedzi", "tnie ściany tekstu", "tworzy warianty A/B/C/D/E", "wskazuje bramkę człowieka i następny krok"],
    guardrail: "Nie zatwierdza prawdy, nie podejmuje decyzji strategicznych i nie udaje operatora.",
    choices: ["A) przejdź do analiz", "B) uruchom dyskusję", "C) zbuduj warianty", "D) otwórz bramkę człowieka", "E) wpisz kandydatów do Księgi"],
  },
  {
    title: "Strateg",
    mission: "Ocena sensu projektu, wartości produktu, priorytetów i MVP.",
    does: ["proponuje kierunki", "ocenia wartość produktu", "ustala priorytety", "wskazuje MVP"],
    choices: ["A) produkt osobisty", "B) B2B", "C) system operacyjny projektów", "D) ramy pracy dla agentów", "E) kierunek łączony"],
  },
  {
    title: "Architekt",
    mission: "Układa warstwy systemu, zależności, środowisko wykonania i podział na moduły.",
    does: ["proponuje warstwy", "sprawdźa zależności", "ocenia środowisko wykonania", "ocenia zespoły agentów"],
    choices: ["A) monolit", "B) moduły", "C) lokalny backend + konsola", "D) lokalnie + VPS", "E) lokalnie + VPS + mobile + automatyzacja przeglądarki"],
  },
  {
    title: "Krytyk logiczny",
    mission: "SprawdŹa spójność argumentów, zakresu, ryzyk oraz fałszywej pewności.",
    does: ["szuka sprzeczności", "wskazuje ryzyka", "wykrywa przeskalowanie", "oznacza otwarte założenia"],
    choices: ["A) zaakceptuj ryzyko", "B) zmniejsz zakres", "C) uruchom dodatkową analizę", "D) oznacz jako otwarte założenie", "E) wróć do operatora"],
  },
  {
    title: "Adwersarialny krytyk",
    mission: "Twarda rola Rady: bezlitośnie kwestionuje założenia operatora i pozostałych modeli oraz szuka błędów matematycznych, luk logicznych i ukrytych trybów porażki.",
    does: ["wymaga podpisu", "atakuje konsensus", "sprawdźa rachunek i logikę", "szuka ukrytych porażek"],
    guardrail: "Nie buduje kompromisu dla wygody. Jeśli widzi lukę, ma wymusić bramkę człowieka albo kolejną rundę Rady.",
    choices: ["A) podpisz zastrzeżenia", "B) odrzuć konsensus", "C) wymuś kontrdowód", "D) otwórz bramkę człowieka", "E) wróć do Source of Truth"],
  },
  {
    title: "Weryfikator",
    mission: "SprawdŹa, czy wniosek wynika z danych i jest spójny z Księgą jako Źródłem Prawdy.",
    does: ["sprawdźa dowody", "wykrywa halucynacje zależności", "kontroluje spójność z Księgą", "ocenia uzasadnienie decyzji"],
    choices: ["A) można zatwierdzić", "B) zatwierdź jako hipotezę", "C) dopytaj operatora", "D) uruchom dodatkową rundę", "E) zablokuj decyzję"],
  },
  {
    title: "Doradca nadzoru",
    mission: "Klasyfikuje ryzyko, koszt, akcje zewnętrzne i wymagane bramki.",
    does: ["klasyfikuje ryzyko", "wykrywa produkcję i akcje zewnętrzne", "sprawdźa bramki prawne, finansowe i bezpieczeństwa", "kontroluje autonomię"],
    choices: ["A) automatyczna zgoda", "B) zgoda nieblokująca", "C) zgoda zbiorcza", "D) blokująca bramka człowieka", "E) bramka awaryjna"],
  },
  {
    title: "Strażnik kosztów",
    mission: "Pilnuje kosztów modeli, VPS, środowiska wykonania i progów akceptacji.",
    does: ["szacuje koszt modeli", "szacuje VPS i środowisko", "sprawdźa progi zgody", "wykrywa wzrost kosztu"],
    choices: ["A) lokalnie najpierw", "B) tani wariant", "C) zapytaj o płatne zasoby", "D) przekrocz próg po zgodzie", "E) wstrzymaj kosztowną ścieżkę"],
  },
  {
    title: "Strażnik bezpieczeństwa",
    mission: "Ocenia bezpieczeństwo danych, sekretów, przesyłania plików i automatyzacji.",
    does: ["ocenia dane i sekrety", "sprawdźa zewnętrzne wysyłki", "ocenia urządzenia", "kontroluje automatyzację przeglądarki"],
    choices: ["A) kontynuuj lokalnie", "B) wymagaj izolacji", "C) wymagaj zgody", "D) zablokuj akcję zewnętrzną", "E) eskaluj do operatora"],
  },
  {
    title: "Specjalista domenowy",
    mission: "Wnosi wiedzę domenową: funding, mobile, lab, telco, device, backend, frontend lub prawo.",
    does: ["dobiera warianty domenowe", "sprawdźa wymagania branżowe", "proponuje specjalistyczne ścieżki", "oznacza braki danych"],
    choices: ["A) wariant domenowy 1", "B) wariant domenowy 2", "C) projekt R&D", "D) projekt inwestycyjny", "E) poczekaj na lepszy warunek/nabór"],
  },
  {
    title: "Księgarz",
    mission: "Wyciąga kandydatów do Księgi i oddziela fakty od hipotez.",
    does: ["zapisuje decyzję operatora", "oznacza konflikty", "wersjonuje Źródło Prawdy", "oddziela fakty od hipotez"],
    choices: ["A) zatwierdź do Księgi", "B) zapisz jako kandydat", "C) zapisz jako hipotezę", "D) odrzuć", "E) wyślij do kolejnej rundy"],
  },
  {
    title: "Arbiter jakości",
    mission: "Ocenia jakość dyskusji, zgodę modeli, siłę argumentów i gotowość decyzji.",
    does: ["ocenia poziom zgody", "ocenia pewność", "wskazuje braki informacyjne", "rekomenduje status decyzji"],
    choices: ["A) zatwierdź kierunek", "B) zatwierdź jako hipotezę", "C) dopytaj operatora", "D) kolejna runda", "E) zablokuj decyzję"],
  },
];
const PROJECT_OPERATOR_AXIS = [
  "Przyjęcie",
  "Zrozumienie",
  "Rada modeli",
  "Analiza",
  "Warianty",
  "Źródło Prawdy",
  "Masterplan",
  "Wykonanie",
  "Finalna zgoda",
  "Zapis pamięci",
];
const PROJECT_BOOK_ENTRY_STATUSES = ["SZKIC", "KANDYDAT", "PRAWDA", "HIPOTEZA", "KONFLIKT", "OTWARTE PYTANIE"];
const PROJECT_HUMAN_GATE_TYPES = [
  "kierunek",
  "Źródło Prawdy",
  "Masterplan",
  "zmiana",
  "koszt",
  "środowisko",
  "produkcja",
  "akcja zewnętrzna",
  "bezpieczeństwo",
  "finalna zgoda",
];
const PROJECT_STAGE_OPERATOR_CHOICES: Record<CouncilStageId, string[]> = {
  idea: ["A) opisz pomysł", "B) dodaj plik", "C) poproś modele o pytania", "D) przyjmij założenia robocze", "E) zatrzymaj projekt"],
  models: ["A) zatwierdź skład", "B) dodaj rolę", "C) zmień model", "D) zwiększ nadzór", "E) pełna Rada"],
  analysis: ["A) uruchom analizy", "B) dodaj materiał", "C) ogranicz zakres", "D) pytania doprecyzowujące", "E) ponów głębiej"],
  discussion: ["A) uruchom dyskusję", "B) poproś o kontrargumenty", "C) adwersarialny krytyk", "D) dopytaj operatora", "E) przejdź do wariantów"],
  proposal: ["A) wybierz wariant", "B) połącz warianty", "C) odrzuć wariant", "D) nowa pula", "E) bramka człowieka"],
  book: ["A) zatwierdź do Księgi", "B) kandydat", "C) hipoteza", "D) odrzuć", "E) kolejna runda"],
};
const PROJECT_STAGE_AXIS_INDEX: Record<CouncilStageId, number> = {
  idea: 0,
  models: 2,
  analysis: 3,
  discussion: 3,
  proposal: 4,
  book: 5,
};
const PROJECT_TERMINAL_SECRET_RE =
  /(?:[a-z][a-z0-9+.-]*:\/\/[^\s"'<>]+)|(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})|(?:sk-[a-zA-Z0-9_-]+)|(?:Bearer\s+[a-zA-Z0-9._-]+)|(?:pplx-[a-zA-Z0-9_-]+)|(?:AIza[0-9A-Za-z_-]+)|(?:[A-Za-z0-9_-]{64,})/g;

function normalizeProjectTerminalCommand(value: string): string {
  return String(value || "")
    .trim()
    .replace(/^\//, "")
    .replace(/_/g, " ")
    .toLocaleLowerCase("pl-PL")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");
}

function projectTerminalQuickCommandTestId(command: string): string {
  return normalizeProjectTerminalCommand(command).replace(/^\//, "").replace(/[^a-z0-9]+/g, "-");
}

function projectTerminalSlashAlias(normalized: string): string | null {
  if (normalized === "status" || normalized === "stan" || normalized === "stan systemu") return "/status";
  if (normalized === "pomoc" || normalized === "help" || normalized === "?") return "/help";
  if (normalized === "koszt" || normalized === "koszty" || normalized === "bud?et") return "/cost";
  if (normalized === "agenci" || normalized === "modele ai" || normalized === "lista modeli") return "/agents";
  return null;
}

function projectTerminalStageIntent(normalized: string): CouncilStageId | null {
  const wantsOpen = /^(pokaz|otworz|przejdz|idz|wejdz|ustaw|wybierz)\b/.test(normalized);
  if (!wantsOpen) return null;
  if (normalized.includes("pomysl") || normalized.includes("material") || normalized.includes("zalacznik") || normalized.includes("plik")) return "idea";
  if (normalized.includes("kogo pytamy") || normalized.includes("sklad rady") || normalized.includes("modele")) return "models";
  if (normalized.includes("analiz")) return "analysis";
  if (normalized.includes("dyskus")) return "discussion";
  if (normalized.includes("wariant") || normalized.includes("wniosek") || normalized.includes("propozyc")) return "proposal";
  if (normalized.includes("ksieg") || normalized.includes("source of truth") || normalized.includes("zrodlo prawdy") || normalized.includes("kanon")) return "book";
  return null;
}

function projectCouncilRolePrompt(): string {
  return [
    "Kontrakt W18/Rady:",
    "Każda odpowiedź ma być krótka, strukturalna i decyzyjna. Bez ścian tekstu. Każda rola ma podać warianty A/B/C/D/E albo jasno powiedzieć, że wariantów jeszcze nie da się uczciwie wybrać.",
    "Format odpowiedzi modelu: rola; stanowisko; dowody/zalozenia; warianty_A_B_C_D_E; human_gate; nastepny_krok_operatora; do_ksiegi_fakty; do_ksiegi_hipotezy; konflikty.",
    "Moderator W18 syntetyzuje proces i następne kroki, ale nie zatwierdza prawdy, nie podejmuje decyzji strategicznych i nie udaje operatora.",
    ...PROJECT_COUNCIL_ROLE_SPECS.map((role) => {
      const lines = [
        `${role.title}: ${role.mission}`,
        `Robi: ${role.does.join("; ")}.`,
        `Wyb?ry: ${role.choices.join(" | ")}.`,
      ];
      if (role.guardrail) lines.push(`Nie robi: ${role.guardrail}`);
      return lines.join("\n");
    }),
    "Arbiter jakości na końcu ma zwrócić: Poziom zgody modeli (%), Poziom pewności, Ryzyko, Rekomendacja, Czy decyzja nadaje się do bramki człowieka.",
  ].join("\n\n");
}

function projectCouncilRoleSummary(): string {
  return PROJECT_COUNCIL_ROLE_SPECS
    .map((role) => `${role.title}: ${role.choices.slice(0, 3).join(" | ")}`)
    .join("\n");
}

function councilModelLabel(modelId?: string): string {
  const raw = String(modelId || "").trim();
  return PROJECT_COUNCIL_MODEL_LABELS[raw] || raw.replace(/^openai:|^anthropic:|^zai:/, "") || "model";
}

function councilText(value?: string): string {
  const text = String(value || "").trim();
  return text || "brak treści w zapisie Rady";
}

function parseCouncilAnalysisJson(value?: string): Record<string, unknown> | null {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const unfenced = raw
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/```\s*$/i, "")
    .trim();
  const start = unfenced.indexOf("{");
  const end = unfenced.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    const parsed = JSON.parse(unfenced.slice(start, end + 1));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function councilStringValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => councilStringValue(item)).filter(Boolean).join(", ");
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const title = councilStringValue(record.title || record.label || record.name || record.option || record.variant || record.question);
    const details = [
      record.description,
      record.summary,
      record.recommendation,
      record.rationale,
      record.impact,
      record.risk,
      record.evidence,
      record.files,
      record.next_step,
    ]
      .map((item) => councilStringValue(item))
      .filter(Boolean);
    if (title || details.length > 0) {
      return [title, ...details].filter(Boolean).join(" - ");
    }
    return Object.entries(record)
      .map(([key, item]) => {
        const text = councilStringValue(item);
        return text ? `${key}: ${text}` : "";
      })
      .filter(Boolean)
      .join(" | ");
  }
  return "";
}

function councilAnalysisList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => councilStringValue(item)).filter(Boolean);
  }
  const text = councilStringValue(value);
  return text ? [text] : [];
}

function councilAnalysisSource(analysis: ProjectCouncilAnalysis): Record<string, unknown> {
  return (
    parseCouncilAnalysisJson(analysis.analysis_text) ||
    parseCouncilAnalysisJson(analysis.rationale) ||
    (analysis as Record<string, unknown>)
  );
}

function councilAnalysisSections(analysis: ProjectCouncilAnalysis): { title: string; items: string[] }[] {
  const source = councilAnalysisSource(analysis);
  return [
    { title: "Cel projektu", items: councilAnalysisList(source.project_purpose) },
    { title: "Jak ma działać", items: councilAnalysisList(source.how_it_works) },
    { title: "Dokumentacja", items: councilAnalysisList(source.documentation_findings) },
    { title: "Funkcje i workflow", items: councilAnalysisList(source.functional_inventory) },
    { title: "Mapa modułów", items: councilAnalysisList(source.module_map) },
    { title: "Macierz dowodów", items: councilAnalysisList(source.evidence_matrix) },
    { title: "Wdrożenie / uruchomienie", items: councilAnalysisList(source.runtime_deploy_assessment) },
    { title: "Plan testu sandbox", items: councilAnalysisList(source.sandbox_test_plan) },
    { title: "Blokery środowiska wykonania", items: councilAnalysisList(source.runtime_blockers) },
    { title: "Potwierdzone / niepewne", items: councilAnalysisList(source.implemented_vs_unclear) },
    { title: "Luki funkcjonalne", items: councilAnalysisList(source.functionality_gaps) },
    { title: "Obserwacje plikowe", items: councilAnalysisList(source.file_observations) },
    { title: "Warianty decyzji", items: councilAnalysisList(source.decision_options) },
    { title: "Pytania Rady", items: councilAnalysisList(source.council_questions) },
    { title: "Do Księgi", items: councilAnalysisList(source.source_of_truth_candidates) },
  ].filter((section) => section.items.length > 0);
}

function dedupeCouncilItems(items: string[], limit = 8): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of items) {
    const text = item.replace(/\s+/g, " ").trim();
    if (!text) continue;
    const key = text.toLocaleLowerCase("pl-PL");
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(text);
    if (result.length >= limit) break;
  }
  return result;
}

function isMeaningfulCouncilChoiceText(value: string): boolean {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length < 18) return false;
  if (
    /formatu\s+JSON|JSON\s+zgodn|odnie[śs]c\s+si[eę]\s+do\s+nast[eę]puj[aą]cych\s+p[oó]l\s+JSON|verdict|confidence|attachment_coverage|project_purpose|how_it_works|decision_options|council_questions|source_of_truth_candidates/i.test(
      text,
    )
  ) {
    return false;
  }
  if (/^w odpowiedzi prosz/i.test(text)) return false;
  if (/^[A-E][\).:\-]?$/.test(text)) return false;
  if (/^wariant\s+[A-E][\).:\-]?$/i.test(text)) return false;
  if (/\b[A-E]\s*\/\s*[A-E]\s*\//.test(text)) return false;
  if (text.includes("?")) return false;
  if (/^(tak|nie|approve|reject|doradzić|kontynuować)$/i.test(text)) return false;
  if (/^(pytanie operatora dotyczy|odpowiedź dotyczy|decyzja jest warunkowa|brak danych uniemożliwia|brakuje kilku kluczowych elementów)/i.test(text)) return false;
  if (/^(raportowanie wyników|fakt do księgi|kandydat do księgi)/i.test(text)) return false;
  if (/^(doradzić deweloperom|umówić się|oceniać postęp|poinformować zespół)/i.test(text)) return false;
  if (/(zidentyfikować i stworzyć wymagane zasoby|skompletować brakującą dokumentację|przygotować plan testów)/i.test(text)) return false;
  if (
    /^(zidentyfikować|skompletować|przygotować|stworzyć|dostarczyć|sprawdźić|napisać|dodać)(\s|$)/i.test(text) &&
    !/(operator|human gate|bramk|źródło prawdy|source of truth|księg|masterplan|runtime|governance|koszt|produkcj|zewnętrzn|local-first|mvp|zakres|rada|adwersarial)/i.test(text)
  ) {
    return false;
  }
  return /[a-ząćęłńóśźż]{4,}/i.test(text);
}

function isReadableCouncilTerminalText(value: string): boolean {
  const text = value.replace(/\s+/g, " ").trim();
  if (!text) return false;
  if (/^[A-E][\).:\-]?$/.test(text)) return false;
  if (/\b[A-E]\s*\/\s*[A-E]\s*\//.test(text)) return false;
  return true;
}

function firstNonEmptyCouncilList<T>(...lists: Array<T[] | null | undefined>): T[] {
  return lists.find((items) => Array.isArray(items) && items.length > 0) ?? [];
}

function isUsableCouncilAnalysis(analysis: ProjectCouncilAnalysis): boolean {
  const record = analysis as Record<string, unknown>;
  const source = String(record.source || "");
  const text = `${analysis.analysis_text || ""}\n${analysis.rationale || ""}`;
  if (source === "llm_error") return false;
  if (text.includes("REAL_LLM_UNAVAILABLE") || text.includes("REAL_LLM_CALL_ERROR")) return false;
  return Boolean((analysis.analysis_text || analysis.rationale || "").trim());
}

function usableCouncilAnalyses(analyses: ProjectCouncilAnalysis[]): ProjectCouncilAnalysis[] {
  return analyses.filter(isUsableCouncilAnalysis);
}

function dedupeCouncilDecisionItems(items: string[], limit = 8): string[] {
  return dedupeCouncilItems(items.filter(isMeaningfulCouncilChoiceText), limit);
}

function fallbackCouncilDecisionChoices(project?: ProjectDetail | null, consolidated?: string): string[] {
  const projectName = project?.title?.trim() || "projekt";
  const base = [
    `Kontynuuj ${projectName} w trybie local-first, bez produkcji i bez działań zewnętrznych, dopóki operator nie zatwierdzi Księgi oraz Masterplanu.`,
    "Wzmocnij governance: uruchom dodatkową rundę Rady z adwersarialnym krytykiem i wróć do Human Gate dla kierunku, kosztów, runtime oraz Source of Truth.",
    "Ogranicz zakres do kontrolowanego MVP: zachowaj funding, mobile i VPS jako domeny wspierające albo future, a wykonanie prowadź lokalnie z pełnym audytem.",
    "Wróć do Rady po brakujące dowody: dopisz luki, ryzyka, testy jak człowiek i warunki blokujące przed zamrożeniem Księgi.",
    "Zatrzymaj przejście dalej i utwórz Change Proposal, jeżeli Rada nie potrafi wskazać spójnych dowodów dla Księgi, Masterplanu i Human Gate.",
  ];
  if (consolidated?.trim()) {
    base.unshift(`Przyjmij wniosek Rady jako wariant roboczy i przepisz go do Księgi po decyzji operatora: ${councilSnippet(consolidated, 240)}`);
  }
  return dedupeCouncilDecisionItems(base, 5);
}

function collectCouncilAnalysisItems(
  analyses: ProjectCouncilAnalysis[],
  keys: string[],
  limit = 8,
): string[] {
  const items: string[] = [];
  for (const analysis of analyses) {
    const source = councilAnalysisSource(analysis);
    for (const key of keys) {
      items.push(...councilAnalysisList(source[key]));
    }
  }
  return dedupeCouncilItems(items, limit);
}

function councilChoiceLabel(index: number): string {
  return String.fromCharCode(65 + index);
}

function councilSnippet(text: string, maxLength = 360): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1).trim()}…`;
}

function redactProjectTerminalText(value: string): string {
  return String(value || "").replace(PROJECT_TERMINAL_SECRET_RE, "<redacted>");
}

function formatProjectTerminalResult(result: ProjectTerminalResult): string {
  const parts = [result.text?.trim() || `[${result.kind || "text"}]`];
  const rows = Array.isArray(result.rows) ? result.rows : [];
  if (rows.length > 0) {
    const headers = Array.isArray(result.headers) ? result.headers : [];
    const preview = rows.slice(0, 6).map((row) => {
      if (row && typeof row === "object") {
        const record = row as Record<string, unknown>;
        const keys = headers.length > 0 ? headers : Object.keys(record).slice(0, 5);
        return keys.map((key) => `${key}: ${String(record[key] ?? "")}`).join(" | ");
      }
      return String(row);
    });
    parts.push(preview.join("\n"));
    if (rows.length > preview.length) {
      parts.push(`... jeszcze ${rows.length - preview.length} wiersz(y)`);
    }
  }
  if (result.target) {
    parts.push(`Cel: ${result.target}`);
  }
  return councilSnippet(redactProjectTerminalText(parts.filter(Boolean).join("\n")), 2800);
}

function councilReadableModelText(value?: string): string {
  const parsed = parseCouncilAnalysisJson(value);
  if (parsed) {
    const structuredItems = [
      parsed.recommendation,
      parsed.summary,
      parsed.reasoning,
      parsed.analysis,
      parsed.contribution,
      parsed.decision_options,
      parsed.council_questions,
      parsed.source_of_truth_candidates,
      parsed.next_steps,
      parsed.proposed_actions,
    ]
      .flatMap((item) => councilAnalysisList(item))
      .filter(isReadableCouncilTerminalText);
    const readable = dedupeCouncilItems(structuredItems, 5).join(" / ");
    if (readable) return readable;
    const fallback = councilStringValue(parsed);
    if (fallback) return fallback;
  }
  const raw = String(value || "");
  const looseJsonItems = ["recommendation", "summary", "reasoning", "analysis", "contribution", "next_steps"]
    .map((field) => {
      const match = raw.match(new RegExp(`"${field}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`));
      return match?.[1]
        ?.replace(/\\"/g, "\"")
        .replace(/\\n/g, " ")
        .replace(/\\\\/g, "\\")
        .trim();
    })
    .filter((item): item is string => typeof item === "string" && isReadableCouncilTerminalText(item)) as string[];
  if (looseJsonItems.length > 0) return dedupeCouncilItems(looseJsonItems, 4).join(" / ");
  return councilText(value);
}

function councilAnalysisTerminalText(analysis: ProjectCouncilAnalysis): string {
  const source = councilAnalysisSource(analysis);
  const preferred = dedupeCouncilDecisionItems(
    [
      ...councilAnalysisList(source.decision_options).slice(0, 2),
      ...councilAnalysisList(source.council_questions).slice(0, 1),
      ...councilAnalysisList(source.source_of_truth_candidates).slice(0, 1),
    ],
    4,
  );
  if (preferred.length > 0) return preferred.join(" / ");
  const structuredFallback = [
    source.summary,
    source.reasoning,
    source.analysis,
    source.recommendation,
    source.next_steps,
    source.proposed_actions,
  ]
    .map((item) => councilStringValue(item))
    .filter(Boolean);
  if (structuredFallback.length > 0) return structuredFallback.join(" / ");
  return councilReadableModelText(analysis.rationale || analysis.analysis_text);
}

function buildCouncilTerminalLines(
  analyses: ProjectCouncilAnalysis[],
  discussion: ProjectCouncilRound[],
  consolidated: string,
  nextStep: string,
): CouncilTerminalLine[] {
  const lines: CouncilTerminalLine[] = [];
  if (analyses.length === 0 && discussion.length === 0 && !consolidated.trim()) {
    lines.push({
      speaker: "AEIS",
      text: nextStep,
      kind: "operator",
    });
    return lines;
  }
  analyses.slice(0, 4).forEach((analysis) => {
    lines.push({
      speaker: councilModelLabel(analysis.model_id),
      text: councilAnalysisTerminalText(analysis),
      kind: "analysis",
    });
  });
  discussion.slice(-6).forEach((round, index) => {
    lines.push({
      speaker: councilModelLabel(round.model_id),
      text: councilReadableModelText(round.contribution),
      kind: index % 2 === 0 ? "discussion" : "analysis",
    });
  });
  if (consolidated.trim()) {
    lines.push({
      speaker: "Wniosek Rady",
      text: consolidated,
      kind: "conclusion",
    });
  }
  return lines.slice(-9);
}

function formatFileSize(bytes?: number): string {
  const size = Number(bytes || 0);
  if (!Number.isFinite(size) || size <= 0) return "0 B";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function latestAttachmentAnalysis(attachment: ProjectAttachment): ProjectAttachmentAnalysis | null {
  const analyses = Array.isArray(attachment.analysis) ? attachment.analysis : [];
  return analyses[0] || null;
}

function projectAttachmentIdeaIds(project: ProjectDetail): string[] {
  const ids = new Set<string>();
  for (const attachment of project.attachments ?? []) {
    const ideaId = String(attachment.idea_id || "").trim();
    if (ideaId) ids.add(ideaId);
  }
  const sourceIdeaId = String(project.source_idea_id || "").trim();
  if (sourceIdeaId) ids.add(sourceIdeaId);
  return Array.from(ids);
}

function projectAttachmentContext(project: ProjectDetail): string {
  const attachments = Array.isArray(project.attachments) ? project.attachments : [];
  if (attachments.length === 0) return "";
  const lines = [
    "AEIS_ATTACHMENT_AUDIT_V2: pełny lokalny raport załączników projektu widoczny dla Rady.",
    "Modele muszą odnieść się do konkretnych plików, katalogów, preview treści, luk pokrycia i ryzyk. Ogólna odpowiedź bez ustaleń plikowych jest niewystarczająca.",
    ...attachments.slice(0, 8).map((attachment, index) => {
      const analysis = latestAttachmentAnalysis(attachment);
      const bits = [
        `\n## Załącznik ${index + 1}: ${attachment.filename || attachment.attachment_id}`,
        `typ=${attachment.file_type || "nieznany"}`,
        `rozmiar=${formatFileSize(attachment.file_size)}`,
      ];
      if (analysis) {
        bits.push(`analiza=${analysis.detected_kind || "nieznana"}`);
        bits.push(`klasa=${analysis.decision_class || "D1"}`);
        const tags = (analysis.tags || []).slice(0, 6).join(", ");
        if (tags) bits.push(`tagi=${tags}`);
        const risks = (analysis.risks || []).slice(0, 3).join(" | ");
        if (risks) bits.push(`ryzyka=${risks}`);
        const missing = (analysis.missing_info || []).slice(0, 3).join(" | ");
        if (missing) bits.push(`braki=${missing}`);
        const preview = String(analysis.extracted_text_preview || "").trim();
        if (preview) {
          bits.push(
            [
              "Raport lokalnej analizy pliku:",
              preview.slice(0, PROJECT_ATTACHMENT_PREVIEW_LIMIT_CHARS),
              preview.length > PROJECT_ATTACHMENT_PREVIEW_LIMIT_CHARS
                ? `[ucięto ${preview.length - PROJECT_ATTACHMENT_PREVIEW_LIMIT_CHARS} znaków raportu; wymagane dalsze lokalne drążenie przed decyzją]`
                : "",
            ].filter(Boolean).join("\n"),
          );
        }
      } else {
        bits.push("analiza=brak; najpierw uruchom analizę załączników");
      }
      return bits.join("\n");
    }),
  ];
  if (attachments.length > 8) {
    lines.push(`Pominięto w kontekście ${attachments.length - 8} dalszych załączników.`);
  }
  return lines.join("\n").slice(0, PROJECT_ATTACHMENT_CONTEXT_LIMIT_CHARS);
}

function projectCouncilSessionMatches(projectId: string, session: ProjectCouncilSession): boolean {
  const marker = `[project:${projectId}]`;
  return String(session.topic || "").includes(marker) || String(session.context || "").includes(projectId);
}

function projectCouncilSessionIsDirectionRound(session: ProjectCouncilSession): boolean {
  const combined = `${session.topic || ""}\n${session.context || ""}`.toLowerCase();
  return (
    !combined.includes("pełny przegląd gotowości rady v10") &&
    !combined.includes("pełny przegląd gotowości council v10") &&
    !combined.includes("full council") &&
    !combined.includes("review council change proposal") &&
    !combined.includes("project_change_review")
  );
}

function projectCouncilSessionNeedsDeepAttachmentRerun(session: ProjectCouncilSession, project?: ProjectDetail | null): boolean {
  const hasAttachments = Boolean(project?.attachments?.length);
  if (!hasAttachments) return false;
  const context = String(session.context || "");
  if (!context.includes("AEIS_ATTACHMENT_AUDIT_V2")) return true;
  return (project?.attachments ?? []).some((attachment) => {
    const filename = String(attachment.filename || "").trim();
    return filename.length > 0 && !context.includes(filename);
  });
}

function projectCouncilSessionTitle(session: ProjectCouncilSession): string {
  return String(session.topic || session.session_id || "Sesja Rady").replace(/^\[project:[^\]]+\]\s*/, "");
}

function projectCouncilSessionsByRound(sessions: ProjectCouncilSession[]): ProjectCouncilSession[] {
  return [...sessions].sort((left, right) => Number(left.created_at || 0) - Number(right.created_at || 0));
}

function projectCouncilRoundNumber(session: ProjectCouncilSession, sessions: ProjectCouncilSession[]): number {
  const sorted = projectCouncilSessionsByRound(sessions);
  const index = sorted.findIndex((item) => item.session_id === session.session_id);
  return index >= 0 ? index + 1 : sorted.length + 1;
}

function labelStage(value?: string): string {
  const key = String(value || "").trim();
  return STAGE_LABELS[key] ?? (key.replace(/_/g, " ") || "nieznana faza");
}

function labelStatus(value?: string): string {
  const key = String(value || "").trim();
  return STATUS_LABELS[key] ?? (key.replace(/_/g, " ") || "brak statusu");
}

function labelAuditType(value?: string): string {
  const key = String(value || "").trim();
  return AUDIT_LABELS[key] ?? (key.replace(/_/g, " ") || "wpis audytu");
}

function labelProjectVisibleText(value?: string): string {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.includes("Mobile app for field inspectors performing on-site verification visits")) {
    return [
      "Aplikacja mobilna dla inspektorów terenowych wykonujących wizyty weryfikacyjne na miejscu.",
      "Operator rejestruje dowody zdjęciowe, GPS i podpis, wysyła je z urządzenia mobilnego w trybie online albo do kolejki offline, a system synchronizuje je automatycznie po odzyskaniu połączenia.",
      "Demo wykonania AEIS musi pozostać lokalne i oparte na dowodach: realna deliberacja Rady, podpisane Księgi, masterplan, jedna pełna lokalna faza budowy, dowody testów W14, próba wydania, dowody rollbacku i bilety Human Gate dla działań D3+.",
      "W tym przebiegu demo nie wolno wdrażać VPS, używać płatnej chmury, poświadczeń produkcyjnych ani wykonywać zewnętrznych zgłoszeń.",
    ].join(" ");
  }
  return text
    .replace(/\bphoto evidence\b/gi, "dowody zdjęciowe")
    .replace(/\bevidence-based\b/gi, "oparte na dowodach")
    .replace(/\boffline-queued\b/gi, "w kolejce offline")
    .replace(/\bauto-syncs\b/gi, "synchronizuje automatycznie")
    .replace(/\blocal-first\b/gi, "lokalnym jako pierwszym")
    .replace(/\bgovernance\b/gi, "nadzór")
    .replace(/\bruntime\b/gi, "środowisko wykonania")
    .replace(/\bfunding\b/gi, "finansowanie")
    .replace(/\bfuture\b/gi, "przyszłościowe")
    .replace(/\bgenerated\b/gi, "wygenerowano")
    .replace(/\bChange Proposal\b/g, "propozycję zmiany")
    .replace(/\bSource of Truth\b/g, "Źródło Prawdy")
    .replace(/\bEvidence Pack\b/g, "Pakiet dowodowy");
}

function buildExternalPolicyLabels(projectKind?: string): { blockLabel: string; exportLabel: string } {
  switch (projectKind) {
    case "employee_portal":
      return {
        blockLabel: "Blokuj zewnętrzne przetwarzanie PII/HR (LLM, API, VPS) do osobnej bramki DPO.",
        exportLabel: "Wymagaj bramki DPO przed usunięciem DSR i finalnym pakietem dowodowym.",
      };
    case "funding":
      return {
        blockLabel: "Blokuj wysyłkę wniosków grantowych i danych firmy do osobnej bramki człowieka.",
        exportLabel: "Wymagaj bramki człowieka przed eksportem dokumentów aplikacyjnych.",
      };
    case "ecommerce_generator":
      return {
        blockLabel: "Blokuj publikację Allegro/Amazon do osobnej bramki człowieka.",
        exportLabel: "Wymagaj bramki człowieka przed eksportem CSV produktu.",
      };
    default:
      return {
        blockLabel: "Blokuj akcje zewnętrzne do osobnej bramki człowieka.",
        exportLabel: "Wymagaj bramki człowieka przed eksportem danych lub artefaktów.",
      };
  }
}

function buildExternalActionsPolicy(
  projectKind: string | undefined,
  blockExternalAction: boolean,
  requireHumanGatePerExport: boolean,
) {
  if (projectKind === "employee_portal") {
    return {
      external_llm_processing: blockExternalAction ? "blocked_until_dpo_human_gate" : "allowed_after_dpo_review",
      gdpr_dsr_erasure: requireHumanGatePerExport ? "dpo_human_gate_required" : "manual_operator_review",
      require_human_gate_per_external_action: requireHumanGatePerExport,
      block_external_processing: blockExternalAction,
    };
  }
  if (projectKind === "funding") {
    return {
      grant_submission: blockExternalAction ? "blocked_until_future_human_gate" : "allowed_after_review",
      document_export: requireHumanGatePerExport ? "human_gate_required" : "local_operator_review",
      require_human_gate_per_export: requireHumanGatePerExport,
      block_external_submission: blockExternalAction,
    };
  }
  if (projectKind === "ecommerce_generator") {
    return {
      marketplace_publish: blockExternalAction ? "blocked_until_future_human_gate" : "allowed_after_review",
      csv_export: requireHumanGatePerExport ? "human_gate_required" : "local_operator_review",
      require_human_gate_per_export: requireHumanGatePerExport,
      block_external_publish: blockExternalAction,
    };
  }
  return {
    external_action: blockExternalAction ? "blocked_until_future_human_gate" : "allowed_after_review",
    artifact_export: requireHumanGatePerExport ? "human_gate_required" : "local_operator_review",
    require_human_gate_per_export: requireHumanGatePerExport,
    block_external_action: blockExternalAction,
  };
}

function normalizeBuildAutonomyLevel(value?: string | null): string {
  const raw = String(value || "").trim();
  if (["L0", "L1", "L2", "L3", "L4"].includes(raw)) return raw;
  return "L2";
}

function projectBuildCostCap(project: ProjectDetail): string {
  const execution = project.execution_plan || {};
  const raw =
    project.cost_cap_usd ??
    execution.budget_usd ??
    execution.hard_limit_usd ??
    execution.cap_usd ??
    25;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? String(parsed) : "25";
}

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = String(params?.projectId || "");
  const { data: health, loading: healthLoading } = useHealth();
  const backendLive = health.status === "ok";

  const [loading, setLoading] = useState(true);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelineStage[]>([]);
  const [pendingQuestions, setPendingQuestions] = useState<PendingQuestion[]>([]);
  const [canon, setCanon] = useState<ProjectCanon | null>(null);
  const [masterplan, setMasterplan] = useState<ProjectMasterplan | null>(null);
  const [modules, setModules] = useState<ProjectModule[]>([]);
  const [audit, setAudit] = useState<AuditResult[]>([]);
  const [cost, setCost] = useState<CostLedger>({ running_total: 0, records: [] });
  const [answeringQuestionId, setAnsweringQuestionId] = useState<string | null>(null);
  const [answerNotice, setAnswerNotice] = useState<string | null>(null);
  const [customAnswers, setCustomAnswers] = useState<Record<string, string>>({});
  const [answerRationales, setAnswerRationales] = useState<Record<string, string>>({});

  // FE-2 / FE-3: freeze button state
  const [freezeCanonLoading, setFreezeCanonLoading] = useState(false);
  const [freezeCanonNotice, setFreezeCanonNotice] = useState<string | null>(null);
  const [freezeMpLoading, setFreezeMpLoading] = useState(false);
  const [freezeMpNotice, setFreezeMpNotice] = useState<string | null>(null);
  const [launchLoading, setLaunchLoading] = useState(false);
  const [launchNotice, setLaunchNotice] = useState<string | null>(null);
  const [buildAuthorizeLoading, setBuildAuthorizeLoading] = useState(false);
  const [buildAuthorizeNotice, setBuildAuthorizeNotice] = useState<string | null>(null);
  const [buildCostCapUsd, setBuildCostCapUsd] = useState("25");
  const [buildAutonomyLevel, setBuildAutonomyLevel] = useState("L2");
  const [blockExternalPublish, setBlockExternalPublish] = useState(true);
  const [requireHgPerExport, setRequireHgPerExport] = useState(true);
  const [projectCouncilSessions, setProjectCouncilSessions] = useState<ProjectCouncilSession[]>([]);
  const [activeCouncilSessionId, setActiveCouncilSessionId] = useState("");
  const [councilQuestion, setCouncilQuestion] = useState("");
  const [selectedCouncilStage, setSelectedCouncilStage] = useState<CouncilStageId | null>(null);
  const [selectedCouncilChoiceLabel, setSelectedCouncilChoiceLabel] = useState<string | null>(null);
  const [newBookItem, setNewBookItem] = useState("");
  const [manualBookItems, setManualBookItems] = useState<string[]>([]);
  const [approvedBookItems, setApprovedBookItems] = useState<Record<string, boolean>>({});
  const [councilAnalyses, setCouncilAnalyses] = useState<ProjectCouncilAnalysis[]>([]);
  const [councilDiscussion, setCouncilDiscussion] = useState<ProjectCouncilRound[]>([]);
  const [councilConsolidated, setCouncilConsolidated] = useState("");
  const [councilNotice, setCouncilNotice] = useState<string | null>(null);
  const [councilBusy, setCouncilBusy] = useState<"start" | "load" | "analysis" | "discussion" | "consolidate" | null>(null);
  const [councilAttachmentUploading, setCouncilAttachmentUploading] = useState(false);
  const [projectTerminalOpen, setProjectTerminalOpen] = useState(true);
  const [projectTerminalBusy, setProjectTerminalBusy] = useState(false);
  const [projectTerminalCommand, setProjectTerminalCommand] = useState("");
  const projectTerminalInputRef = useRef<HTMLInputElement | null>(null);
  const [projectTerminalLines, setProjectTerminalLines] = useState<ProjectTerminalLine[]>([
    { role: "system", text: "W18 gotowy. Polecenia wykonują się w kontekście tego projektu." },
  ]);
  const activeCouncilSession = projectCouncilSessions.find((session) => session.session_id === activeCouncilSessionId);
  const councilRounds = projectCouncilSessionsByRound(projectCouncilSessions);
  const activeCouncilRoundNumber = activeCouncilSession
    ? projectCouncilRoundNumber(activeCouncilSession, projectCouncilSessions)
    : Math.max(1, councilRounds.length + 1);
  const councilNeedsDeepAttachmentRerun = activeCouncilSession
    ? projectCouncilSessionNeedsDeepAttachmentRerun({ ...activeCouncilSession, analyses: councilAnalyses }, project)
    : false;
  const validCouncilAnalyses = usableCouncilAnalyses(councilAnalyses);
  const councilAnalysisErrorCount = councilAnalyses.length - validCouncilAnalyses.length;
  const councilAnalysesReady = validCouncilAnalyses.length >= 2 && !councilNeedsDeepAttachmentRerun;
  const councilDiscussionReady = councilDiscussion.length > 0;
  const councilConclusionReady = councilConsolidated.trim().length > 0;
  const councilNextStep = project?.canon_frozen_at
    ? "Księga jest zamrożona. Kolejna zmiana wymaga nowej rundy Rady."
    : !activeCouncilSessionId
    ? "Wpisz pytanie i utwórz sesję Rady."
    : councilNeedsDeepAttachmentRerun
      ? "Poprzednia sesja ma zbyt płytki skrót plików. Uzupełnij głęboką analizę."
      : !councilAnalysesReady
        ? "Uruchom analizę modeli."
        : !councilDiscussionReady
          ? "Analizy są gotowe. Teraz uruchom dyskusję modeli."
          : !councilConclusionReady
            ? "Dyskusja jest gotowa. Teraz zbuduj wniosek Rady."
            : "Wniosek Rady jest gotowy. Jeśli nie wystarcza, wpisz kolejne pytanie jako nową rundę; jeśli wystarcza, zamroź Księgę.";
  const councilProcessSteps: CouncilProcessStep[] = [
    {
      id: "idea",
      title: "Pomysł i materiały",
      body: `${project?.title || "Projekt"}${project?.attachments?.length ? ` · ${project.attachments.length} załącznik(i)` : " · bez załączników"}`,
      status: project?.title || project?.idea ? "gotowe" : "oczekuje",
    },
    {
      id: "models",
      title: "Kogo pytamy",
      body: "Możesz zmienić skład Rady i głębokość myślenia, ale możesz też iść dalej na domyślnym ustawieńiu.",
      status: activeCouncilSessionId || projectCouncilSessions.length > 0 ? "gotowe" : "ustaw",
    },
    {
      id: "analysis",
      title: `Runda ${activeCouncilRoundNumber}: analizy`,
      body: councilAnalysesReady ? `${validCouncilAnalyses.length} stanowiska modeli zapisane.` : "Modele osobno analizują pomysł, pliki, ryzyka i możliwe kierunki.",
      status: councilAnalysesReady ? "gotowe" : councilBusy === "analysis" ? "w toku" : "następne",
    },
    {
      id: "discussion",
      title: "Dyskusja modeli",
      body: councilDiscussionReady ? `${councilDiscussion.length} wypowiedzi w dyskusji.` : "Modele odnoszą się do siebie, a operator może dodać decyzję lub pytanie jako kolejną rundę.",
      status: councilDiscussionReady ? "gotowe" : councilAnalysesReady ? "następne" : "oczekuje",
    },
    {
      id: "proposal",
      title: "Wniosek Rady",
      body: councilConclusionReady ? "Rekomendacja jest gotowa do decyzji operatora." : "Po dyskusji Rada syntetyzuje warianty, warunki i blokery.",
      status: councilConclusionReady ? "gotowe" : councilDiscussionReady || councilAnalysesReady ? "następne" : "oczekuje",
    },
    {
      id: "book",
      title: "Księga / Źródło Prawdy",
      body: project?.canon_frozen_at ? `Zatwierdzona ${fmt(project.canon_frozen_at)}.` : "Po tylu rundach, ile trzeba, operator zatwierdza Księgę jako kanon projektu.",
      status: project?.canon_frozen_at ? "gotowe" : councilConclusionReady ? "następne" : "oczekuje",
    },
  ];
  const explicitCouncilDecisionChoices = dedupeCouncilDecisionItems(
    collectCouncilAnalysisItems(councilAnalyses, [
      "decision_options",
      "next_steps",
      "recommendations",
      "proposed_directions",
    ], 12),
    7,
  );
  const inferredCouncilDecisionChoices = dedupeCouncilDecisionItems(
    [
      ...councilAnalyses.map((analysis) => councilAnalysisTerminalText(analysis)),
      councilConsolidated ? `Wniosek Rady: ${councilConsolidated}` : "",
    ],
    5,
  );
  const councilDecisionChoiceTexts = dedupeCouncilDecisionItems(
    [
      ...(explicitCouncilDecisionChoices.length > 0 ? explicitCouncilDecisionChoices : inferredCouncilDecisionChoices),
      ...fallbackCouncilDecisionChoices(project, councilConsolidated),
    ],
    5,
  );
  const councilQuestionChoiceTexts = collectCouncilAnalysisItems(councilAnalyses, [
    "council_questions",
    "operator_questions",
    "clarifying_questions",
  ], 5);
  const councilBookDraftItems = dedupeCouncilItems(
    [
      ...collectCouncilAnalysisItems(councilAnalyses, [
        "source_of_truth_candidates",
        "project_purpose",
        "implemented_vs_unclear",
        "functional_inventory",
      ], 10),
      councilConsolidated ? `Wniosek Rady: ${councilConsolidated}` : "",
      canon?.book ? `Aktualna Księga: ${councilSnippet(canon.book, 480)}` : "",
      project?.canonical_book ? `Księga projektu: ${councilSnippet(project.canonical_book, 480)}` : "",
    ],
    10,
  );
  const councilOperatorChoices: CouncilOperatorChoice[] = councilDecisionChoiceTexts.slice(0, 5).map((text, index) => ({
    label: councilChoiceLabel(index),
    text,
    source: explicitCouncilDecisionChoices.length > 0 ? "wariant z analizy modeli" : "wariant roboczy z wypowiedzi Rady",
    kind: "variant",
  }));
  const councilQuestionChoices: CouncilOperatorChoice[] = councilQuestionChoiceTexts.slice(0, 4).map((text, index) => ({
    label: `P${index + 1}`,
    text,
    source: "pytanie doprecyzowujące Rady",
    kind: "question",
  }));
  const councilTerminalLines = buildCouncilTerminalLines(councilAnalyses, councilDiscussion, councilConsolidated, councilNextStep);
  const councilGuideStatus = !activeCouncilSessionId
    ? {
        title: "Napisz jednym zdaniem, co Rada ma ustalić.",
        body: "Możesz też dodać plik. Potem kliknij jeden przycisk, a AEIS sam uruchomi analizę modeli.",
        label: "Wyślij do Rady i analizuj",
      }
    : councilNeedsDeepAttachmentRerun
      ? {
          title: "Załączniki trzeba przeanalizować głębiej.",
          body: "Poprzednia runda nie ma pełnego lokalnego raportu plików, więc AEIS utworzy świeżą rundę z pełniejszym kontekstem.",
          label: "Uzupełnij analizę plików",
        }
      : !councilAnalysesReady
        ? {
            title: "Rada potrzebuje najpierw osobnych opinii modeli.",
            body: "AEIS poprosi każdy model o własną analizę pomysłu, plików, ryzyk i możliwych kierunków.",
            label: "Uruchom opinie modeli",
          }
        : !councilDiscussionReady
          ? {
              title: "Opinie są gotowe. Teraz modele powinny odpowiedzieć sobie nawzajem.",
              body: "To jest moment dyskusji: modele kwestionują sw?je wnioski i szukają lepszych wariantów.",
              label: "Niech modele dyskutują",
            }
          : !councilConclusionReady
            ? {
                title: "Dyskusja jest gotowa. AEIS może ułożyć warianty do wyboru.",
                body: "Zamiast ściany tekstu dostaniesz warianty A/B/C i pytania, które operator może rozstrzygnąć.",
                label: "Pokaż warianty wyboru",
              }
            : councilQuestion.trim()
              ? {
                  title: selectedCouncilChoiceLabel
                    ? `Wybrano ${selectedCouncilChoiceLabel}. Wyślij to jako następną rundę.`
                    : "Masz wpisaną odpowiedź do Rady.",
                  body: "AEIS potraktuje to jak kolejną wiadomość w rozmowie i znów poprosi modele o analizę w nowym kierunku.",
                  label: "Wyślij mój wybór",
                }
              : {
                  title: "Wybierz wariant albo dopisz pytanie.",
                  body: "Kliknij A/B/C lub wpisz własną odpowiedź. Księga robocza będzie aktualizowana po kolejnych rundach.",
                  label: "Czekam na wybór",
                };
  const councilGuideSteps = [
    { label: "Pytanie", done: Boolean(activeCouncilSessionId), active: !activeCouncilSessionId },
    { label: "Opinie", done: councilAnalysesReady, active: Boolean(activeCouncilSessionId) && !councilAnalysesReady },
    { label: "Dyskusja", done: councilDiscussionReady, active: councilAnalysesReady && !councilDiscussionReady },
    { label: "Warianty", done: councilConclusionReady, active: councilDiscussionReady && !councilConclusionReady },
    { label: "Księga", done: Boolean(project?.canon_frozen_at), active: councilConclusionReady },
  ];
  const activeCouncilStageId: CouncilStageId = !activeCouncilSessionId
    ? "idea"
    : councilNeedsDeepAttachmentRerun || !councilAnalysesReady
      ? "analysis"
      : !councilDiscussionReady
        ? "discussion"
        : !councilConclusionReady
          ? "proposal"
          : "book";
  const visibleCouncilStage = selectedCouncilStage || activeCouncilStageId;
  const allCouncilBookItems = dedupeCouncilItems([...councilBookDraftItems, ...manualBookItems], 18);
  const approvedBookCount = allCouncilBookItems.filter((item) => approvedBookItems[item]).length;
  const pendingHumanGateCount = [
    project?.approvals?.book_pending_ticket_id,
    project?.approvals?.operating_model_pending_ticket_id,
    project?.approvals?.build_pending_ticket_id,
  ].filter(Boolean).length;
  const operatorAxisCurrentIndex = project?.build_authorized_at
    ? 7
    : project?.masterplan_frozen_at
      ? 6
      : project?.canon_frozen_at
        ? 5
        : activeCouncilSessionId
          ? PROJECT_STAGE_AXIS_INDEX[visibleCouncilStage]
          : 0;
  const operatorDecisionChoices =
    councilOperatorChoices.length > 0
      ? councilOperatorChoices.map((choice) => `${choice.label}) ${labelProjectVisibleText(choice.text)}`)
      : PROJECT_STAGE_OPERATOR_CHOICES[visibleCouncilStage];

  function applyCouncilOperatorChoice(choice: CouncilOperatorChoice) {
    const intro =
      choice.kind === "variant"
        ? `Wybieram wariant ${choice.label}: ${choice.text}`
        : `Odpowiadam na pytanie ${choice.label}: ${choice.text}`;
    setSelectedCouncilChoiceLabel(choice.kind === "variant" ? `wariant ${choice.label}` : `pytanie ${choice.label}`);
    setCouncilQuestion(
      `${intro}\n\nPoproszę Radę o kolejną rundę w tym kierunku: doprecyzuj wpływ na Księgę jako Źródło Prawdy, Masterplan, zakres modułów, ryzyka, blokery i decyzję operatora.`,
    );
    setCouncilNotice("Wybór jest gotowy do wysłania. Kliknij „Wyślij mój wybór”, żeby Rada kontynuowała rozmowę.");
  }

  function handleAddManualBookItem() {
    const item = newBookItem.trim();
    if (!item) {
      setCouncilNotice("Wpisz punkt, który ma wejść do roboczej Księgi.");
      return;
    }
    setManualBookItems((prev) => dedupeCouncilItems([...prev, item], 20));
    setApprovedBookItems((prev) => ({ ...prev, [item]: true }));
    setNewBookItem("");
    setCouncilNotice("Punkt dodany do roboczej Księgi i oznaczony jako zaakceptowany.");
  }

  function handleConfirmBookDraft() {
    const approved = allCouncilBookItems.filter((item) => approvedBookItems[item]);
    if (approved.length === 0) {
      setCouncilNotice("Zaznacz przynajmniej jeden punkt Księgi albo dodaj własny punkt.");
      return;
    }
    setCouncilQuestion(
      [
        "Zatwierdzam poniższe punkty roboczej Księgi i proszę Radę o kolejną rundę tylko wokół braków, sprzeczności i warunków zamrożenia:",
        ...approved.map((item, index) => `${index + 1}. ${item}`),
      ].join("\n"),
    );
    setSelectedCouncilChoiceLabel("robocza Księga");
    setCouncilNotice("Zaznaczone punkty są wpisane jako decyzja operatora. Możesz wysłać je do kolejnej rundy albo zamrozić Księgę niżej.");
  }

  function appendProjectTerminalLine(line: ProjectTerminalLine) {
    setProjectTerminalLines((prev) => [...prev.slice(-49), line]);
  }

  async function executeBackendProjectTerminalCommand(command: string) {
    const result = (await api.execTerminalCommand(command, {
      project_id: projectId,
      project_title: project?.title || "",
      route: "project_detail",
      source_surface: "project_w18_terminal",
      active_council_stage: visibleCouncilStage,
      active_council_stage_label: COUNCIL_STAGE_LABELS[visibleCouncilStage],
      council_session_id: activeCouncilSessionId || null,
      council_round: activeCouncilRoundNumber,
      selected_choice: selectedCouncilChoiceLabel || null,
      canon_frozen: Boolean(project?.canon_frozen_at),
      build_cost_cap_usd: buildCostCapUsd,
      build_autonomy_level: buildAutonomyLevel,
      external_actions_policy: buildExternalActionsPolicy(
        project?.project_kind,
        blockExternalPublish,
        requireHgPerExport,
      ),
    })) as ProjectTerminalResult;
    appendProjectTerminalLine({
      role: result.kind === "error" || result.kind === "not_implemented" ? "error" : "aeis",
      text: formatProjectTerminalResult(result),
    });
  }

  async function executeLocalProjectTerminalCommand(command: string): Promise<boolean> {
    const normalized = normalizeProjectTerminalCommand(command);
    if (normalized === "pomoc" || normalized === "help" || normalized === "?") {
      appendProjectTerminalLine({
        role: "aeis",
        text: [
          "Dostępne komendy W18:",
          "- co dalej: uruchamia następny logiczny krok Rady",
          "- analizy / dyskusja / warianty: prowadzą rundę modeli",
          "- role rady: pokazuje skład funkcjonalny Rady",
          "- pokaż księgę: otwiera Księgę roboczą",
          "- pokaż wykonanie: pokazuje autoryzację budowy i artefakty",
          "- bramka człowieka: pokazuje oczekujące decyzję operatora",
          "- zamroź Księgę / zamroź Masterplan / autoryzuj budowę: tworzą formalną bramkę człowieka",
        ].join("\n"),
      });
      return true;
    }
    const stageIntent = projectTerminalStageIntent(normalized);
    if (stageIntent) {
      setSelectedCouncilStage(stageIntent);
      appendProjectTerminalLine({ role: "aeis", text: `Otwieram etap: ${COUNCIL_STAGE_LABELS[stageIntent]}.` });
      return true;
    }
    if ((normalized.startsWith("ksiega") || normalized.includes("source of truth") || normalized.includes("zrodlo prawdy") || normalized.includes("kanon")) && (normalized.includes("pokaz") || normalized.includes("otworz") || normalized.includes("status") || normalized === "ksiega")) {
      setSelectedCouncilStage("book");
      appendProjectTerminalLine({
        role: "aeis",
        text: [
          "Otwieram Księgę roboczą projektu.",
          `Statusy wpisów: ${PROJECT_BOOK_ENTRY_STATUSES.join(", ")}.`,
          allCouncilBookItems.length > 0
            ? `Kandydaci widoczni w panelu: ${allCouncilBookItems.length}.`
            : "Nie ma jeszcze kandydatów z Rady. Dodaj punkt ręcznie albo uruchom analizy i warianty.",
        ].join("\n"),
      });
      return true;
    }
    if (normalized.startsWith("projekt opisz") || normalized === "projekt opis" || normalized === "projekt pokaz") {
      setSelectedCouncilStage("idea");
      appendProjectTerminalLine({ role: "aeis", text: "Otwieram etap Pomysł i materiały. Tu wpisujesz opis projektu i dodajesz pliki dla Rady." });
      return true;
    }
    if (normalized.startsWith("projekt dodaj plik") || normalized.startsWith("projekt dodaj zalacznik")) {
      setSelectedCouncilStage("idea");
      appendProjectTerminalLine({ role: "aeis", text: "Użyj przycisku „Dodaj plik” w W18 albo w etapie Pomysł i materiały. Przesłanie pliku z terminala graficznego zostaje zapisane do materiałów projektu i analizowane lokalnie." });
      return true;
    }
    if (normalized.startsWith("rada ") && (normalized.includes("zaproponuj") || normalized.includes("ustaw") || normalized.includes("dodaj") || normalized.includes("role") || normalized.includes("pelna"))) {
      setSelectedCouncilStage("models");
      appendProjectTerminalLine({
        role: "aeis",
        text: [
          "Proponowany kontrakt Rady W18 jest otwarty w etapie Kogo pytamy.",
          projectCouncilRoleSummary(),
          "",
          "To są role funkcjonalne. Konkretne modele, providerzy, klucze API i głębokość myślenia są dobierane w meta-orkiestracji oraz po Masterplanie dla modułów wykonawczych.",
        ].join("\n"),
      });
      return true;
    }
    if (normalized.startsWith("masterplan") && (normalized.includes("pokaz") || normalized.includes("modul"))) {
      appendProjectTerminalLine({
        role: "aeis",
        text: [
          `Masterplan: ${masterplan?.summary || project?.masterplan || "brak zatwierdzonego szkicu"}`,
          modules.length > 0 ? `Moduły:\n${modules.map((module) => `- ${module.name || module.module_id}: ${labelStatus(module.status)}`).join("\n")}` : "Moduły nie są jeszcze rozpisane.",
        ].join("\n"),
      });
      return true;
    }
    if (["co dalej", "dalej", "kontynuuj", "kontynuuj rade", "nastepny krok", "idz dalej"].includes(normalized)) {
      appendProjectTerminalLine({ role: "aeis", text: "Uruchamiam kolejny logiczny krok Rady dla tego projektu." });
      await handleCouncilGuideContinue();
      return true;
    }
    if (normalized.includes("role rady") || normalized.includes("sklad rady") || normalized.includes("kto w radzie")) {
      setSelectedCouncilStage("models");
      appendProjectTerminalLine({
        role: "aeis",
        text: [
          "Skład funkcjonalny Rady W18:",
          projectCouncilRoleSummary(),
          "",
          "Moderator W18 pilnuje procesu i wariantów, ale decyzję strategiczne i prawda należą do operatora.",
        ].join("\n"),
      });
      return true;
    }
    if (normalized.includes("analiz")) {
      setSelectedCouncilStage("analysis");
      appendProjectTerminalLine({ role: "aeis", text: "Uruchamiam analizę modeli w kontekście pomysłu, materiałów i aktualnej rundy." });
      await handleRunProjectCouncilAnalysis();
      return true;
    }
    if (normalized.includes("dyskus")) {
      setSelectedCouncilStage("discussion");
      appendProjectTerminalLine({ role: "aeis", text: "Uruchamiam dyskusję modeli na podstawie zapisanych analiz." });
      await handleRunProjectCouncilDiscussion();
      return true;
    }
    if (normalized.includes("wariant") || normalized.includes("wniosek") || normalized.includes("propozyc")) {
      setSelectedCouncilStage("proposal");
      appendProjectTerminalLine({ role: "aeis", text: "Buduję wniosek Rady i warianty decyzyjne dla operatora." });
      await handleConsolidateProjectCouncil();
      return true;
    }
    if (normalized.includes("zatwierdz") && (normalized.includes("ksieg") || normalized.includes("source of truth") || normalized.includes("zrodlo prawdy") || normalized.includes("kanon"))) {
      setSelectedCouncilStage("book");
      handleConfirmBookDraft();
      appendProjectTerminalLine({ role: "aeis", text: "Zaznaczone punkty Księgi zostały przepisane jako decyzja operatora do kolejnej rundy." });
      return true;
    }
    if (normalized.includes("zamroz") && (normalized.includes("ksieg") || normalized.includes("source of truth") || normalized.includes("zrodlo prawdy") || normalized.includes("kanon"))) {
      setSelectedCouncilStage("book");
      appendProjectTerminalLine({ role: "aeis", text: "Przekazuję żądanie zamrożenia Księgi do istniejącego mechanizmu AEIS i bramki człowieka." });
      await executeBackendProjectTerminalCommand(command);
      await load();
      return true;
    }
    if (normalized.includes("zamroz") && normalized.includes("masterplan")) {
      appendProjectTerminalLine({ role: "aeis", text: "Przekazuję żądanie zamrożenia Masterplanu do istniejącego mechanizmu AEIS i bramki człowieka." });
      await executeBackendProjectTerminalCommand(command);
      await load();
      return true;
    }
    if (normalized.includes("autoryzuj") && (normalized.includes("budow") || normalized.includes("runda 3") || normalized.includes("build"))) {
      appendProjectTerminalLine({ role: "aeis", text: "Tworzę autoryzację budowy przez istniejący tor bramki człowieka. Budowa nie ruszy bez akceptacji bramki." });
      await executeBackendProjectTerminalCommand(command);
      await load();
      return true;
    }
    if (normalized.includes("human") || normalized.includes("bramka")) {
      await executeBackendProjectTerminalCommand(command);
      await load();
      return true;
    }
    if (normalized.includes("log") || normalized.includes("historia") || normalized.includes("stan aeis")) {
      await executeBackendProjectTerminalCommand("/status");
      return true;
    }
    if ((normalized.includes("pokaz") || normalized.includes("status")) && (normalized.includes("wykonanie") || normalized.includes("build"))) {
      appendProjectTerminalLine({
        role: "aeis",
        text: [
          `Autoryzacja budowy: ${project?.build_authorized_at ? `tak, ${fmt(project.build_authorized_at)}` : "nie"}`,
          `Artefakt: ${project?.launch?.artifact_path || "brak"}`,
          `Status uruchomienia: ${project?.launch?.status || "brak"}`,
          project?.approvals?.build_pending_ticket_id ? `Bramka budowy oczekuje: ${project.approvals.build_pending_ticket_id}` : "",
        ].filter(Boolean).join("\n"),
      });
      return true;
    }
    if ((normalized.includes("uruchom") || normalized.includes("odpal")) && (normalized.includes("wykonanie") || normalized.includes("build") || normalized.includes("deploy"))) {
      appendProjectTerminalLine({
        role: "error",
        text: "To polecenie może uruchamiać wykonanie kodu/artefaktów. W18 nie wykonuje go automatycznie z tekstu; użyj jawnej autoryzacji budowy i bramki człowieka.",
      });
      return true;
    }
    if (normalized.includes("usun") || normalized.includes("skasuj") || normalized.includes("wyczysc") || normalized.includes("reset")) {
      appendProjectTerminalLine({
        role: "error",
        text: "Polecenia usuwania albo resetowania wymagają osobnego, jawnego i zawężonego wykonawcy. Ten terminal ich teraz nie uruchamia.",
      });
      return true;
    }
    if (command.includes("?") || normalized.startsWith("zapytaj") || normalized.startsWith("zadaj") || normalized.startsWith("przeanalizuj")) {
      const currentProject = project;
      if (!currentProject) {
        appendProjectTerminalLine({ role: "error", text: "Projekt nie jest jeszcze załadowany, więc nie mogę wysłać pytania do Rady." });
        return true;
      }
      setSelectedCouncilStage("analysis");
      appendProjectTerminalLine({ role: "aeis", text: "Traktuję to jako wiadomość do Rady i uruchamiam rundę analizy modeli." });
      setCouncilBusy("analysis");
      setCouncilNotice(null);
      try {
        const sessionId = await createProjectCouncilQuestionSession(currentProject, command, { clearQuestion: true });
        setSelectedCouncilChoiceLabel(null);
        setCouncilDiscussion([]);
        setCouncilConsolidated("");
        const result = await api.runParallelAnalysis(sessionId);
        const summary = await fetchProjectCouncilSessionSummary(sessionId);
        const analyses = firstNonEmptyCouncilList<ProjectCouncilAnalysis>(
          result.analyses as ProjectCouncilAnalysis[] | undefined,
          result.created as ProjectCouncilAnalysis[] | undefined,
          summary?.analyses,
        );
        setCouncilAnalyses(analyses);
        if (analyses.length >= 2) setSelectedCouncilStage("discussion");
        await load();
        appendProjectTerminalLine({ role: "aeis", text: "Rada przyjęła polecenie i zapisała opinie modeli. Następny krok: dyskusja." });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "błąd rozmowy z Radą";
        setCouncilNotice(`Błąd: ${msg}`);
        appendProjectTerminalLine({ role: "error", text: `Błąd Rady: ${redactProjectTerminalText(msg)}` });
      } finally {
        setCouncilBusy(null);
      }
      return true;
    }
    return false;
  }

  async function handleProjectTerminalExec(commandOverride?: string) {
    const commandSource = commandOverride ?? (projectTerminalCommand || projectTerminalInputRef.current?.value || "");
    const command = commandSource.trim();
    if (!command || projectTerminalBusy) return;
    setProjectTerminalBusy(true);
    setProjectTerminalCommand("");
    if (projectTerminalInputRef.current) projectTerminalInputRef.current.value = "";
    appendProjectTerminalLine({ role: "operator", text: `$ ${redactProjectTerminalText(command)}` });
    try {
      const normalized = normalizeProjectTerminalCommand(command);
      const slashAlias = projectTerminalSlashAlias(normalized);
      const handled = await executeLocalProjectTerminalCommand(command);
      if (handled) return;
      if (command.startsWith("/") || slashAlias) {
        await executeBackendProjectTerminalCommand(slashAlias || command);
        return;
      }
      appendProjectTerminalLine({
        role: "error",
        text: [
          "Nie mam jeszcze podpiętego wykonawcy AEIS dla tego polecenia.",
          "Dostępne teraz: co dalej, /projekt opisz, /projekt dodaj_plik, /rada role, /rada analiza_indywidualna, /rada dyskusja, /warianty pokaż, /księga pokaż, /masterplan pokaż_moduły, zamroź Księgę, zamroź Masterplan, autoryzuj budowę, status, koszty, agenci, pomoc.",
          "Docelowo każde polecenie powinno trafić do backendowego Command Bus z lokalnym modelem jako plannerem, a UI ma tylko pokazać i audytować rezultat.",
        ].join("\n"),
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd terminala W18";
      appendProjectTerminalLine({ role: "error", text: `Błąd terminala W18: ${redactProjectTerminalText(msg)}` });
    } finally {
      setProjectTerminalBusy(false);
    }
  }

  async function handleProjectTerminalFileUpload(files: FileList | null) {
    const fileItems = Array.from(files ?? []);
    if (fileItems.length === 0) return;
    const fileSummary = fileItems
      .map((file) => `${redactProjectTerminalText(file.name)} (${formatFileSize(file.size)})`)
      .join(", ");
    appendProjectTerminalLine({ role: "operator", text: `$ dodaj plik ${fileSummary}` });
    const result = await handleUploadProjectCouncilAttachments(files);
    if (!result) {
      appendProjectTerminalLine({ role: "error", text: "Nie udało się dołączyć pliku: projekt nie jest gotowy." });
      return;
    }
    const parts: string[] = [];
    if (result.uploadedNames.length > 0) {
      parts.push(
        `Dodano do materiałów projektu i przeanalizowano lokalnie: ${result.uploadedNames
          .map(redactProjectTerminalText)
          .join(", ")}.`,
      );
    }
    if (result.skippedNames.length > 0) {
      parts.push(`Pominięto pliki większe niż 50 MB: ${result.skippedNames.map(redactProjectTerminalText).join(", ")}.`);
    }
    if (result.error) {
      parts.push(`Błąd: ${redactProjectTerminalText(result.error)}`);
    }
    appendProjectTerminalLine({
      role: result.error ? "error" : "aeis",
      text: parts.join("\n") || "Nie dodano żadnego pliku.",
    });
  }

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [projectRes, timelineRes, questionsRes, canonRes, masterplanRes, modulesRes, auditRes, costRes, councilSessionsRes] = await Promise.all([
        api.getProjectDetail(projectId),
        api.getProjectTimeline(projectId),
        api.listProjectQuestionsCanonical(projectId, "pending"),
        api.getProjectCanon(projectId),
        api.getProjectMasterplan(projectId),
        api.getProjectModules(projectId),
        api.getProjectAudit(projectId),
        api.getProjectCost(projectId),
        api.listCouncilSessions().catch(() => ({ sessions: [] })),
      ]);
      const projectDetail = projectRes as ProjectDetail;
      setProject(projectDetail);
      if (!projectDetail.build_authorized_at && !projectDetail.approvals?.build_pending_ticket_id) {
        setBuildCostCapUsd(projectBuildCostCap(projectDetail));
        setBuildAutonomyLevel(
          normalizeBuildAutonomyLevel(
            projectDetail.autonomy_level ||
              projectDetail.governance_policy?.autonomy_mode ||
              projectDetail.governance_policy?.level,
          ),
        );
      }
      setTimeline((timelineRes.stages ?? []) as TimelineStage[]);
      setPendingQuestions((questionsRes.questions ?? []) as PendingQuestion[]);
      setCanon(canonRes as ProjectCanon);
      setMasterplan(masterplanRes as ProjectMasterplan);
      setModules((modulesRes.modules ?? []) as ProjectModule[]);
      setAudit((auditRes.results ?? []) as AuditResult[]);
      const normalizedCost = costRes as Partial<CostLedger>;
      setCost({
        running_total: normalizedCost.running_total ?? 0,
        records: Array.isArray(normalizedCost.records) ? normalizedCost.records : [],
      });
      const projectSessions = ((councilSessionsRes.sessions ?? []) as ProjectCouncilSession[]).filter((session) =>
        projectCouncilSessionMatches(projectId, session) && projectCouncilSessionIsDirectionRound(session),
      );
      setProjectCouncilSessions(projectSessions);
      const selectedSessionId = (
        activeCouncilSessionId && projectSessions.some((session) => session.session_id === activeCouncilSessionId)
          ? activeCouncilSessionId
          : projectSessions[0]?.session_id || ""
      );
      if (selectedSessionId) {
        try {
          const summary = (await api.getCouncilSessionSummary(selectedSessionId)) as ProjectCouncilSession;
          applyProjectCouncilSessionSummary(summary);
        } catch {
          setActiveCouncilSessionId(selectedSessionId);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [projectId, activeCouncilSessionId]);

  useEffect(() => {
    if (!backendLive) return;
    const timer = window.setTimeout(() => {
      void load().catch(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [backendLive, load]);

  // FE-2 (round_meta): freeze Canon (Source of Truth) — Round 1 -> Round 2 gate
  async function handleFreezeCanon() {
    if (!projectId) return;
    setFreezeCanonNotice(null);
    setFreezeCanonLoading(true);
    try {
      const result = await api.freezeProjectCanon(projectId, { reason: "Round 1 -> Round 2" });
      if (result?.status === "pending_human_gate") {
        const ticket = result.pending_governance_ticket_id || result.ticket_id || "brak ID";
        setFreezeCanonNotice(`Utworzono bramkę człowieka dla zamrożenia Księgi: ${ticket}. Księga nie jest zamrożona do czasu akceptacji.`);
      } else if (result?.freeze_status === "already_frozen") {
        setFreezeCanonNotice("Księga była już zamrożona.");
      } else {
        setFreezeCanonNotice("Odpowiedź zamrożenia Księgi odebrana. Sprawdź status bramki człowieka przed Rundą 2.");
      }
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd zamrożenia";
      setFreezeCanonNotice(`Błąd: ${msg}`);
    } finally {
      setFreezeCanonLoading(false);
    }
  }

  // FE-3 (round_meta): freeze Masterplan — Round 2 -> Round 3 gate
  async function handleFreezeMasterplan() {
    if (!projectId) return;
    setFreezeMpNotice(null);
    setFreezeMpLoading(true);
    try {
      const result = await api.freezeProjectMasterplan(projectId, { reason: "Round 2 -> Round 3" });
      if (result?.status === "pending_human_gate") {
        const ticket = result.pending_governance_ticket_id || result.ticket_id || "brak ID";
        setFreezeMpNotice(`Utworzono bramkę człowieka dla zamrożenia Masterplanu: ${ticket}. Budowa pozostaje zablokowana do akceptacji.`);
      } else if (result?.freeze_status === "already_frozen") {
        setFreezeMpNotice("Masterplan był już zamrożony.");
      } else {
        setFreezeMpNotice("Odpowiedź zamrożenia Masterplanu odebrana. Sprawdź status bramki człowieka przed Rundą 3.");
      }
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd zamrożenia";
      setFreezeMpNotice(`Błąd: ${msg}`);
    } finally {
      setFreezeMpLoading(false);
    }
  }

  if (!healthLoading && !backendLive) {
    return (
      <Card className="p-6 bg-sylion-red/5 border-sylion-red/20">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-sylion-red" />
          <div>
            <p className="text-sm font-medium text-sylion-red">Backend jest niedostępny</p>
            <p className="text-xs text-muted-foreground mt-1">Szczegóły projektu wymagają działającego API SYLION.</p>
          </div>
        </div>
      </Card>
    );
  }

  if (healthLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-24 rounded-xl bg-muted animate-pulse" />
        <div className="grid grid-cols-2 gap-4">
          <div className="h-64 rounded-xl bg-muted animate-pulse" />
          <div className="h-64 rounded-xl bg-muted animate-pulse" />
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <Card className="p-6 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
        <p className="text-sm font-medium">Nie znaleziono projektu.</p>
      </Card>
    );
  }

  async function handleAnswerQuestion(question: PendingQuestion, choiceId?: string, custom = false) {
    if (!projectId || !question.question_id) return;
    const customResponse = (customAnswers[question.question_id] || "").trim();
    const rationale = (answerRationales[question.question_id] || "").trim();
    if (custom && !customResponse) {
      setAnswerNotice("Wpisz własną odpowiedź operatora przed wysłaniem decyzji.");
      return;
    }
    if (!custom && !choiceId) {
      setAnswerNotice("Wybierz wariant Rady albo wpisz własną decyzję.");
      return;
    }
    setAnsweringQuestionId(question.question_id);
    setAnswerNotice(null);
    try {
      await api.answerProjectQuestion(projectId, question.question_id, {
        choice_id: custom ? "" : choiceId,
        custom_response: custom ? customResponse : "",
        rationale,
        source: "human-dashboard",
      });
      setAnswerNotice("Decyzja operatora zapisana. Projekt, audyt i skutki planistyczne zostały odświeżone.");
      setCustomAnswers((prev) => ({ ...prev, [question.question_id]: "" }));
      setAnswerRationales((prev) => ({ ...prev, [question.question_id]: "" }));
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd zapisu decyzji";
      setAnswerNotice(`Błąd: ${msg}`);
    } finally {
      setAnsweringQuestionId(null);
    }
  }

  function applyProjectCouncilSessionSummary(summary: ProjectCouncilSession) {
    const sessionId = summary.session_id;
    if (!sessionId) return;
    setActiveCouncilSessionId(sessionId);
    setCouncilAnalyses(summary.analyses ?? []);
    setCouncilDiscussion(summary.discussion ?? []);
    setCouncilConsolidated(summary.consolidated?.consolidated_text || summary.consolidated_text || "");
    setProjectCouncilSessions((prev) => {
      const next = prev.filter((session) => session.session_id !== sessionId);
      return [summary, ...next];
    });
  }

  async function fetchProjectCouncilSessionSummary(sessionId: string): Promise<ProjectCouncilSession | null> {
    if (!sessionId) return null;
    const summary = (await api.getCouncilSessionSummary(sessionId)) as ProjectCouncilSession;
    applyProjectCouncilSessionSummary(summary);
    return summary;
  }

  async function loadProjectCouncilSession(sessionId: string) {
    if (!sessionId) return;
    setCouncilBusy("load");
    setCouncilNotice(null);
    try {
      await fetchProjectCouncilSessionSummary(sessionId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd odczytu sesji Rady";
      setCouncilNotice(`Błąd: ${msg}`);
    } finally {
      setCouncilBusy(null);
    }
  }

  async function createProjectCouncilQuestionSession(
    currentProject: ProjectDetail,
    question: string,
    options: { clearQuestion?: boolean } = {},
  ): Promise<string> {
    let projectForCouncil = currentProject;
    const attachmentIdeaIds = projectAttachmentIdeaIds(currentProject);
    if (attachmentIdeaIds.length > 0) {
      setCouncilNotice("Analizuję załączniki lokalnie przed utworzeniem sesji Rady.");
      await Promise.all(
        attachmentIdeaIds.map((ideaId) => api.analyzeIdeaAttachments(ideaId)),
      );
      projectForCouncil = (await api.getProjectDetail(projectId)) as ProjectDetail;
      setProject(projectForCouncil);
    }
    const topic = `[project:${projectId}] ${question.slice(0, 96)}`;
    const attachmentsContext = projectAttachmentContext(projectForCouncil);
    const description = [
      `Projekt: ${projectForCouncil.title || projectId}`,
      `Pomysł: ${projectForCouncil.idea || "brak opisu pomysłu"}`,
      `Obecna faza: ${labelStage(projectForCouncil.phase)} / ${labelStatus(projectForCouncil.status)}`,
      attachmentsContext || "Załączniki projektu: brak załączników albo brak analizy załączników w danych projektu.",
      `Pytanie operatora: ${question}`,
      projectCouncilRolePrompt(),
      "Zadanie Rady: przedyskutuj możliwe kierunki, wskaż ryzyka, zależności i rekomendację dla operatora w formacie W18. Jeżeli pytanie dotyczy pliku, każdy model musi odnieść się do konkretnych plików, katalogów i luk pokrycia z sekcji AEIS_ATTACHMENT_AUDIT_V2. Jeżeli raport lokalny jest niewystarczający, podaj dokładnie jakie pliki albo typy treści wymagają dalszej lokalnej analizy. Nie wykonuj akcji zewnętrznych.",
    ].join("\n\n");
    const result = await api.openHybridCouncil(topic, description, PROJECT_COUNCIL_MODELS);
    const sessionId = result.session_id;
    if (!sessionId) throw new Error("Backend nie zwrócił ID sesji Rady.");
    setActiveCouncilSessionId(sessionId);
    setCouncilAnalyses([]);
    setCouncilDiscussion([]);
    setCouncilConsolidated("");
    if (options.clearQuestion ?? true) setCouncilQuestion("");
    await load();
    await fetchProjectCouncilSessionSummary(sessionId);
    return sessionId;
  }

  async function resolveProjectCouncilSessionForAction(allowCreateFromQuestion: boolean): Promise<string | null> {
    if (activeCouncilSessionId) return activeCouncilSessionId;
    const reusable = projectCouncilSessions[0]?.session_id;
    if (reusable) {
      await fetchProjectCouncilSessionSummary(reusable);
      return reusable;
    }
    if (allowCreateFromQuestion && project) {
      const question = councilQuestion.trim();
      if (question) {
        setCouncilNotice("Tworzę sesję Rady z wpisanego pytania i od razu przechodzę do analizy modeli.");
        return createProjectCouncilQuestionSession(project, question, { clearQuestion: true });
      }
    }
    return null;
  }

  async function handleStartProjectCouncilQuestion() {
    const currentProject = project;
    if (!currentProject) return;
    const question = councilQuestion.trim();
    if (!question) {
      setCouncilNotice("Wpisz pytanie albo temat, który Rada ma przedyskutować.");
      return;
    }
    setCouncilBusy("start");
    setCouncilNotice(null);
    try {
      const sessionId = await createProjectCouncilQuestionSession(currentProject, question);
      setCouncilNotice("Sesja Rady utworzona. Uruchom analizę modeli, potem dyskusję i wniosek.");
      await fetchProjectCouncilSessionSummary(sessionId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd utworzenia sesji Rady";
      setCouncilNotice(`Błąd: ${msg}`);
    } finally {
      setCouncilBusy(null);
    }
  }

  async function handleUploadProjectCouncilAttachments(files: FileList | null): Promise<ProjectAttachmentUploadResult | null> {
    const currentProject = project;
    if (!files || files.length === 0 || !currentProject) return null;
    const uploadedNames: string[] = [];
    const skippedNames: string[] = [];
    setCouncilAttachmentUploading(true);
    setCouncilNotice(null);
    try {
      let latestProject = currentProject;
      let targetIdeaId = projectAttachmentIdeaIds(latestProject)[0] || `project-${projectId}-council`;
      for (const file of Array.from(files)) {
        if (file.size > 50 * 1024 * 1024) {
          setCouncilNotice(`${file.name}: plik jest większy niż limit 50 MB.`);
          skippedNames.push(file.name);
          continue;
        }
        const uploaded = await api.uploadIdeaFile(file, targetIdeaId);
        const ideaId = String(uploaded.idea_id || uploaded.idea_id_used || targetIdeaId);
        targetIdeaId = ideaId;
        const analysisResult = await api.analyzeIdeaAttachments(ideaId);
        const analysis = (analysisResult.analyses ?? []).find(
          (item: ProjectAttachmentAnalysis) => item.attachment_id === uploaded.attachment_id,
        );
        latestProject = (await api.addProjectAttachment(
          projectId,
          analysis ? { ...uploaded, idea_id: ideaId, analysis } : { ...uploaded, idea_id: ideaId },
          "project_council_question",
        )) as ProjectDetail;
        uploadedNames.push(file.name);
      }
      setProject(latestProject);
      await load();
      setCouncilNotice(
        uploadedNames.length === 1
          ? "Załącznik dodany, przeanalizowany lokalnie i będzie dołączony do pytania Rady."
          : `Dodano i przeanalizowano ${uploadedNames.length} załączników do pytania Rady.`,
      );
      return { uploadedNames, skippedNames };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd uploadu załącznika";
      setCouncilNotice(`Błąd załącznika: ${msg}`);
      return { uploadedNames, skippedNames, error: msg };
    } finally {
      setCouncilAttachmentUploading(false);
    }
  }

  async function handleRunProjectCouncilAnalysis() {
    setCouncilBusy("analysis");
    setCouncilNotice(null);
    try {
      let sessionId = await resolveProjectCouncilSessionForAction(true);
      if (!sessionId) {
        setCouncilNotice("Wpisz pytanie i kliknij Analiza modeli albo wybierz istniejącą sesję Rady.");
        return;
      }
      let before = await fetchProjectCouncilSessionSummary(sessionId);
      if (before && projectCouncilSessionNeedsDeepAttachmentRerun(before, project)) {
        const question = projectCouncilSessionTitle(before) || councilQuestion.trim() || "Przeanalizuj załączniki projektu";
        setCouncilNotice("Poprzednia sesja miała za płytki skrót plików. Tworzę nową sesję z pełnym raportem lokalnej analizy załączników.");
        if (!project) {
          setCouncilNotice("Brak danych projektu do ponownej głębokiej analizy załączników.");
          return;
        }
        sessionId = await createProjectCouncilQuestionSession(project, question, { clearQuestion: false });
        before = await fetchProjectCouncilSessionSummary(sessionId);
      }
      if ((before?.analyses ?? []).length >= 2) {
        setSelectedCouncilStage("discussion");
        setCouncilNotice("Analizy modeli są już gotowe dla tej sesji. Następny krok: kliknij Dyskusja modeli.");
        return;
      }
      const result = await api.runParallelAnalysis(sessionId);
      const summary = await fetchProjectCouncilSessionSummary(sessionId);
      const analyses = firstNonEmptyCouncilList<ProjectCouncilAnalysis>(
        result.analyses as ProjectCouncilAnalysis[] | undefined,
        result.created as ProjectCouncilAnalysis[] | undefined,
        summary?.analyses,
      );
      setCouncilAnalyses(analyses);
      if (analyses.length >= 2) setSelectedCouncilStage("discussion");
      setCouncilNotice("Analizy modeli gotowe. Teraz uruchom dyskusję między modelami.");
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd analizy modeli";
      setCouncilNotice(`Błąd: ${msg}`);
    } finally {
      setCouncilBusy(null);
    }
  }

  async function handleRunProjectCouncilDiscussion() {
    setCouncilBusy("discussion");
    setCouncilNotice(null);
    try {
      const sessionId = await resolveProjectCouncilSessionForAction(false);
      if (!sessionId) {
        setCouncilNotice("Najpierw wpisz pytanie i uruchom analizę modeli.");
        return;
      }
      const summary = await fetchProjectCouncilSessionSummary(sessionId);
      if ((summary?.analyses ?? []).length < 2) {
        setCouncilNotice("Najpierw uruchom analizę modeli. Dyskusja wymaga co najmniej dwóch stanowisk modeli.");
        return;
      }
      const result = await api.runDiscussion(sessionId, 1);
      const summaryAfter = await fetchProjectCouncilSessionSummary(sessionId);
      const discussion = firstNonEmptyCouncilList<ProjectCouncilRound>(
        result.rounds as ProjectCouncilRound[] | undefined,
        result.created as ProjectCouncilRound[] | undefined,
        summaryAfter?.discussion,
      );
      setCouncilDiscussion(discussion);
      if (discussion.length > 0) setSelectedCouncilStage("proposal");
      setCouncilNotice("Dyskusja modeli zapisana. Możesz teraz zbudować wniosek Rady.");
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd dyskusji modeli";
      setCouncilNotice(`Błąd: ${msg}`);
    } finally {
      setCouncilBusy(null);
    }
  }

  async function handleConsolidateProjectCouncil() {
    setCouncilBusy("consolidate");
    setCouncilNotice(null);
    try {
      const sessionId = await resolveProjectCouncilSessionForAction(false);
      if (!sessionId) {
        setCouncilNotice("Najpierw wpisz pytanie i uruchom analizę modeli.");
        return;
      }
      const summary = await fetchProjectCouncilSessionSummary(sessionId);
      if ((summary?.analyses ?? []).length === 0) {
        setCouncilNotice("Najpierw uruchom analizę modeli albo wybierz sesję, która ma już stanowiska modeli.");
        return;
      }
      const result = await api.consolidateCouncil(sessionId);
      const summaryAfter = await fetchProjectCouncilSessionSummary(sessionId);
      const text =
        result.consolidated_suggestion ||
        result.consolidated?.consolidated_text ||
        summaryAfter?.consolidated?.consolidated_text ||
        summaryAfter?.consolidated_text ||
        "";
      setCouncilConsolidated(text);
      if (text.trim()) setSelectedCouncilStage("book");
      setCouncilNotice("Wniosek Rady gotowy. Operator może na tej podstawie wybrać kierunek albo zadać kolejne pytanie.");
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd budowy wniosku Rady";
      setCouncilNotice(`Błąd: ${msg}`);
    } finally {
      setCouncilBusy(null);
    }
  }

  async function handleCouncilGuideContinue() {
    const currentProject = project;
    if (!currentProject) return;
    const question = councilQuestion.trim();

    if (!activeCouncilSessionId || (question && (councilAnalysesReady || councilDiscussionReady || councilConclusionReady))) {
      if (!question) {
        const notice = "Napisz wiadomość do Rady albo wybierz jeden z wariantów A/B/C.";
        setCouncilNotice(notice);
        appendProjectTerminalLine({ role: "aeis", text: notice });
        return;
      }
      setCouncilBusy("analysis");
      setCouncilNotice(null);
      try {
        const sessionId = await createProjectCouncilQuestionSession(currentProject, question, { clearQuestion: true });
        setSelectedCouncilChoiceLabel(null);
        setCouncilDiscussion([]);
        setCouncilConsolidated("");
        const result = await api.runParallelAnalysis(sessionId);
        const summary = await fetchProjectCouncilSessionSummary(sessionId);
        const analyses = firstNonEmptyCouncilList<ProjectCouncilAnalysis>(
          result.analyses as ProjectCouncilAnalysis[] | undefined,
          result.created as ProjectCouncilAnalysis[] | undefined,
          summary?.analyses,
        );
        setCouncilAnalyses(analyses);
        if (analyses.length >= 2) setSelectedCouncilStage("discussion");
        setCouncilNotice("Rada przyjęła wiadomość i przygotowała opinie modeli. Kliknij „Niech modele dyskutują”.");
        await load();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "błąd rozmowy z Radą";
        setCouncilNotice(`Błąd: ${msg}`);
      } finally {
        setCouncilBusy(null);
      }
      return;
    }

    if (!councilAnalysesReady) {
      await handleRunProjectCouncilAnalysis();
      return;
    }
    if (!councilDiscussionReady) {
      await handleRunProjectCouncilDiscussion();
      return;
    }
    if (!councilConclusionReady) {
      await handleConsolidateProjectCouncil();
      return;
    }
    setCouncilNotice("Wybierz wariant A/B/C albo wpisz pytanie, żeby Rada kontynuowała rozmowę.");
  }

  async function handleLaunchExecution() {
    if (!projectId) return;
    setLaunchNotice(null);
    setLaunchLoading(true);
    try {
      const result = await api.launchProject(projectId, {
        auto_execute: true,
        wait_for_completion: true,
      });
      const artifactPath = result?.execution?.artifact_path || result?.project?.launch?.artifact_path || "";
      setLaunchNotice(
        artifactPath
          ? `Wykonanie zakończone. Artefakt: ${artifactPath}`
          : "Wykonanie zakończone bez ścieżki artefaktu - sprawdź audyt i logi.",
      );
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd uruchomienia wykonania";
      setLaunchNotice(`Błąd: ${msg}`);
    } finally {
      setLaunchLoading(false);
    }
  }

  async function handleAuthorizeBuild() {
    if (!projectId) return;
    const costCap = Number(buildCostCapUsd);
    if (!Number.isFinite(costCap) || costCap <= 0) {
      setBuildAuthorizeNotice("Podaj poprawny limit kosztu USD dla Rundy 3.");
      return;
    }
    setBuildAuthorizeNotice(null);
    setBuildAuthorizeLoading(true);
    try {
      const result = await api.authorizeProjectBuild(projectId, {
        cost_cap_usd: costCap,
        autonomy_level: buildAutonomyLevel,
        external_actions_policy: buildExternalActionsPolicy(project?.project_kind, blockExternalPublish, requireHgPerExport),
      });
      const ticket = result?.pending_governance_ticket_id || result?.ticket_id || "brak ID";
      setBuildAuthorizeNotice(`Utworzono bramkę człowieka Rundy 3: ${ticket}. Budowa ruszy dopiero po akceptacji.`);
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "błąd autoryzacji budowy";
      setBuildAuthorizeNotice(`Błąd: ${msg}`);
    } finally {
      setBuildAuthorizeLoading(false);
    }
  }

  const buildPolicyLabels = buildExternalPolicyLabels(project.project_kind);

  return (
    <div className={`space-y-5 ${projectTerminalOpen ? "pb-[28rem]" : "pb-20"}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <FolderKanban className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{project.title}</h1>
            <p className="text-sm text-muted-foreground mt-1">{labelProjectVisibleText(project.idea)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px]">{labelStage(project.phase)}</Badge>
          <Badge variant="outline" className="text-[10px]">{labelStatus(project.status)}</Badge>
          {project.build_authorized_at ? (
            <Button
              variant="outline"
              size="sm"
              data-testid="launch-project-execution"
              onClick={() => handleLaunchExecution().catch(() => {})}
              disabled={launchLoading}
            >
              {launchLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : null}
              {project.launch?.artifact_path ? "Ponów wykonanie" : "Uruchom wykonanie"}
            </Button>
          ) : null}
          {project.launch?.artifact_path ? (
            <a
              href={api.projectArtifactUrl(projectId)}
              data-testid="open-project-artifact"
              className="inline-flex h-7 items-center gap-1 rounded-lg border border-border bg-background px-2.5 text-[0.8rem] font-medium hover:bg-muted"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Otwórz artefakt
            </a>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => load().catch(() => {})}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {launchNotice && (
        <Card
          className="p-3 border-sylion-blue/30 bg-sylion-blue/5 text-xs text-muted-foreground"
          data-testid="launch-project-notice"
        >
          {launchNotice}
        </Card>
      )}

      <Card
        className="border-sylion-blue/25 bg-[#0f1629] p-4"
        data-testid="aeis-command-center-model"
      >
        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold">Centrum dowodzenia AEIS</p>
                  <HelpTip text="Główny kokpit projektu. Pokazuje etap Rady, Księgę, bramki człowieka, pasek decyzji i terminal W18, żeby operator prowadził projekt z jednego miejsca." />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  W18 jest główną powierzchnią sterowania projektem. Dashboard pokazuje stan, Księgę, bramki człowieka, decyzję i wykonanie.
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5 text-[10px]">
                <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue">
                  tryb: lokalnie najpierw
                </Badge>
                <Badge variant="outline" className="border-sylion-amber/30 text-sylion-amber">
                  bramki: {pendingHumanGateCount}
                </Badge>
                <Badge variant="outline" className="border-sylion-green/30 text-sylion-green">
                  {project?.canon_frozen_at ? "Księga zatwierdzona" : "szkic Księgi"}
                </Badge>
              </div>
            </div>

            <div className="grid gap-2 md:grid-cols-3" data-testid="aeis-command-center-pillars">
              <div className="rounded-lg border border-sylion-blue/20 bg-sylion-blue/5 p-3">
                <p className="text-xs font-semibold text-sylion-blue">W18</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  komendy, rozmowa, decyzję, log, Rada, Księga, bramki człowieka i wykonanie.
                </p>
              </div>
              <div className="rounded-lg border border-sylion-green/20 bg-sylion-green/5 p-3">
                <p className="text-xs font-semibold text-sylion-green">Księga</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  statusy: {PROJECT_BOOK_ENTRY_STATUSES.join(", ")}.
                </p>
              </div>
              <div className="rounded-lg border border-sylion-amber/20 bg-sylion-amber/5 p-3">
                <p className="text-xs font-semibold text-sylion-amber">Bramki człowieka</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  typy: {PROJECT_HUMAN_GATE_TYPES.slice(0, 5).join(", ")} i kolejne bramki produkcyjne/finalne.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5" data-testid="aeis-operator-axis">
              {PROJECT_OPERATOR_AXIS.map((step, index) => {
                const done = index < operatorAxisCurrentIndex;
                const current = index === operatorAxisCurrentIndex;
                return (
                  <span
                    key={step}
                    className={`rounded-full border px-2 py-1 text-[10px] ${
                      current
                        ? "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue"
                        : done
                          ? "border-sylion-green/30 bg-sylion-green/10 text-sylion-green"
                          : "border-[rgba(148,163,184,0.1)] bg-black/10 text-muted-foreground"
                    }`}
                  >
                    {step}
                  </span>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg border border-[rgba(148,163,184,0.1)] bg-black/15 p-3" data-testid="aeis-decision-bar">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold">Pasek decyzji operatora</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  Domyślnie pokazuje wybory zależne od etapu. Po analizie Rady zastępują je realne warianty modeli.
                </p>
              </div>
              <Badge variant="outline" className="border-sylion-blue/30 text-[10px] text-sylion-blue">
                {COUNCIL_STAGE_LABELS[visibleCouncilStage]}
              </Badge>
            </div>
            <div className="space-y-1.5">
              {operatorDecisionChoices.slice(0, 5).map((choice, index) => (
                <button
                  key={`operator-decision-${index}`}
                  type="button"
                  className="w-full rounded-md border border-[rgba(148,163,184,0.1)] bg-[#0b1020] px-3 py-2 text-left text-xs text-muted-foreground transition hover:border-sylion-blue/35 hover:bg-sylion-blue/10"
                  data-testid={`aeis-decision-option-${index + 1}`}
                  onClick={() => {
                    setSelectedCouncilStage(visibleCouncilStage);
                    setCouncilQuestion(`${choice}\n\nProszę Radę o kolejną rundę w tym kierunku: warianty, ryzyka, bramki człowieka i kandydaci do Księgi.`);
                    setSelectedCouncilChoiceLabel(`decyzja ${councilChoiceLabel(index)}`);
                    setCouncilNotice("Decyzja została wpisana do pola Rady. Wyślij ją jako kolejną rundę, jeśli to właściwy kierunek.");
                  }}
                >
                  {councilSnippet(choice, 240)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card
        id="project-directions"
        className="p-4 bg-[#0f1629] border-sylion-blue/25 space-y-4"
        data-testid="project-council-start-panel"
      >
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-sylion-blue/10 flex items-center justify-center">
                <MessageSquare className="w-4 h-4 text-sylion-blue" />
              </div>
              <div>
                <p className="text-sm font-semibold">Dyskusja i wybór kierunku projektu</p>
                <p className="text-xs text-muted-foreground">
                  Projekt przechodzi przez tyle rund Rady, ile trzeba: pomysł, materiały, opinie modeli, dyskusja, decyzję operatora i dopiero potem Księga jako Źródło Prawdy.
                </p>
              </div>
            </div>
            <div className="grid gap-2 text-xs md:grid-cols-2 xl:grid-cols-3" data-testid="project-council-process-map">
              {councilProcessSteps.map((step, index) => (
                (() => {
                  const activeStep = step.status === "następne" || step.status === "w toku" || step.status === "ustaw";
                  const doneStep = step.status === "gotowe";
                  const selectedStep = visibleCouncilStage === step.id;
                  return (
                    <div
                      key={step.title}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedCouncilStage(step.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedCouncilStage(step.id);
                        }
                      }}
                      className={`rounded-lg border px-3 py-2 transition ${
                        selectedStep
                          ? "border-sylion-amber/45 bg-sylion-amber/10 shadow-[0_0_0_1px_rgba(245,158,11,0.16)]"
                          : activeStep
                          ? "border-sylion-blue/35 bg-sylion-blue/10 shadow-[0_0_0_1px_rgba(59,130,246,0.12)]"
                          : doneStep
                            ? "border-sylion-green/20 bg-sylion-green/5"
                            : "border-[rgba(148,163,184,0.08)] bg-black/10"
                      }`}
                      data-testid={`project-council-process-step-${index + 1}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-semibold text-foreground">{index + 1}. {step.title}</p>
                        <Badge
                          variant="outline"
                          className={`shrink-0 text-[9px] ${
                            activeStep
                              ? "border-sylion-blue/35 text-sylion-blue"
                              : doneStep
                                ? "border-sylion-green/30 text-sylion-green"
                                : ""
                          }`}
                        >
                          {step.status}
                        </Badge>
                      </div>
                      <p className="mt-1 text-muted-foreground">{step.body}</p>
                      {activeStep ? (
                        index === 1 && step.status === "ustaw" ? (
                          <Link
                            href={`/projects/${encodeURIComponent(projectId)}/orchestration#project-council`}
                            onClick={(event) => event.stopPropagation()}
                            className="mt-2 inline-flex h-7 items-center gap-1.5 rounded-md border border-sylion-blue/35 bg-sylion-blue/10 px-2.5 text-[10px] font-semibold text-sylion-blue transition hover:bg-sylion-blue/20"
                            data-testid="project-council-process-configure"
                          >
                            Ustaw Radę
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        ) : (
                          <Button
                            size="sm"
                            className="mt-2 h-7 px-2.5 text-[10px]"
                            data-testid={`project-council-process-continue-${index + 1}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              handleCouncilGuideContinue().catch(() => {});
                            }}
                            disabled={councilBusy !== null}
                          >
                            {councilBusy !== null ? (
                              <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
                            ) : (
                              <ArrowRight className="mr-1.5 h-3 w-3" />
                            )}
                            {councilGuideStatus.label}
                          </Button>
                        )
                      ) : null}
                    </div>
                  );
                })()
              ))}
            </div>
            <div
              className="rounded-lg border border-sylion-amber/25 bg-sylion-amber/5 p-3"
              data-testid="project-council-stage-workspace"
            >
              {visibleCouncilStage === "idea" ? (
                <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs font-semibold text-sylion-amber">1. Pomysł i materiały</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Tu opisujesz temat własnymi słowami. To jest treść, którą Rada będzie rozbierać na obszary, funkcje, ryzyka i pytania.
                      </p>
                    </div>
                    <textarea
                      className="min-h-[112px] w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 py-2 text-sm outline-none focus:border-sylion-amber/60"
                      data-testid="project-council-stage-idea-input"
                      placeholder="Opisz pomysł, co system ma robić, dla kogo, jakie pliki mają znaczenie i jakie decyzję chcesz uzyskać od Rady."
                      value={councilQuestion}
                      onChange={(event) => {
                        setCouncilQuestion(event.target.value);
                        setSelectedCouncilChoiceLabel(null);
                      }}
                    />
                    <div className="flex flex-wrap gap-2">
                      <label
                        className={`inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-sylion-blue/35 bg-sylion-blue/10 px-3 text-xs font-semibold text-sylion-blue transition hover:bg-sylion-blue/20 ${
                          councilAttachmentUploading ? "pointer-events-none opacity-70" : ""
                        }`}
                        data-testid="project-council-stage-upload"
                      >
                        {councilAttachmentUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                        Dodaj materiały
                        <input
                          type="file"
                          multiple
                          className="sr-only"
                          disabled={councilAttachmentUploading || councilBusy !== null}
                          onChange={(event) => {
                            void handleUploadProjectCouncilAttachments(event.currentTarget.files).finally(() => {
                              event.currentTarget.value = "";
                            });
                          }}
                        />
                      </label>
                      <Button
                        size="sm"
                        className="h-8"
                        data-testid="project-council-stage-idea-next"
                        onClick={() => setSelectedCouncilStage("models")}
                      >
                        Dalej: kogo pytamy
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-black/10 p-3 text-xs text-muted-foreground">
                    <p className="font-semibold text-foreground">Materiały projektu</p>
                    {(project?.attachments ?? []).length === 0 ? (
                      <p className="mt-2">Brak załączników. Możesz iść dalej bez plików albo dodać dokumentację/kod/ZIP.</p>
                    ) : (
                      <div className="mt-2 space-y-2">
                        {(project?.attachments ?? []).map((attachment) => {
                          const analysis = latestAttachmentAnalysis(attachment);
                          return (
                            <div key={attachment.attachment_id} className="rounded-md border border-[rgba(148,163,184,0.08)] bg-background/25 px-2 py-2">
                              <p className="font-medium text-foreground">{attachment.filename || attachment.attachment_id}</p>
                              <p className="mt-0.5">
                                {formatFileSize(attachment.file_size)} · {analysis?.detected_kind || "czeka na analizę"}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ) : null}

              {visibleCouncilStage === "models" ? (
                <div className="space-y-3">
                  <div>
                    <p className="text-xs font-semibold text-sylion-amber">2. Kogo pytamy</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Wybierz skład Rady świadomie: różne modele mają różne role. Domyślny skład wystarczy do startu, a pełną konfigurację zmienisz w meta-orkiestracji.
                    </p>
                  </div>
                  <div className="grid gap-2 lg:grid-cols-2 xl:grid-cols-3" data-testid="project-council-role-grid">
                    {PROJECT_COUNCIL_ROLE_SPECS.map((role) => (
                      <div key={role.title} className="rounded-lg border border-sylion-blue/20 bg-sylion-blue/5 p-3 text-xs">
                        <p className="font-semibold text-foreground">{role.title}</p>
                        <p className="mt-1 text-muted-foreground">{role.mission}</p>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {role.does.slice(0, 3).map((item) => (
                            <span
                              key={`${role.title}-${item}`}
                              className="rounded-full border border-[rgba(148,163,184,0.12)] bg-black/20 px-2 py-0.5 text-[10px] text-muted-foreground"
                            >
                              {item}
                            </span>
                          ))}
                        </div>
                        <p className="mt-2 font-mono text-[10px] leading-relaxed text-sylion-blue">
                          {role.choices.slice(0, 3).join(" / ")}
                        </p>
                        {role.guardrail ? (
                          <p className="mt-2 rounded-md border border-sylion-amber/25 bg-sylion-amber/10 px-2 py-1 text-[10px] font-medium text-sylion-amber">
                            Twarda reguła: {role.guardrail}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                  <div className="rounded-lg border border-sylion-amber/20 bg-sylion-amber/5 p-3 text-xs text-muted-foreground">
                    <p className="font-semibold text-sylion-amber">Modele wykonawcze</p>
                    <p className="mt-1">
                      Obecnie aktywne modele bazowe: {PROJECT_COUNCIL_MODELS.map(councilModelLabel).join(", ")}. Role powyżej są kontraktem dyskusji; pełny dobór modeli, providerów, kluczy i głębokości myślenia pozostaje w meta-orkiestracji i powinien być doprecyzowany po Masterplanie.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={`/projects/${encodeURIComponent(projectId)}/orchestration#project-council`}
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-sylion-blue/35 bg-sylion-blue/10 px-3 text-xs font-semibold text-sylion-blue transition hover:bg-sylion-blue/20"
                      data-testid="project-council-stage-open-models"
                    >
                      Zmień modele i role
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                    <Button
                      size="sm"
                      className="h-8"
                      data-testid="project-council-stage-models-next"
                      onClick={() => setSelectedCouncilStage("analysis")}
                    >
                      Zatwierdzam skład
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ) : null}

              {visibleCouncilStage === "analysis" ? (
                <div className="space-y-3">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="text-xs font-semibold text-sylion-amber">3. Analizy modeli</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Każdy model najpierw daje osobną opinię o pomyśle i materiałach. Dopiero potem ma sens dyskusja między modelami.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      className="h-8"
                      data-testid="project-council-stage-run-analysis"
                      onClick={() => handleRunProjectCouncilAnalysis().catch(() => {})}
                      disabled={councilBusy !== null || councilAnalysesReady}
                    >
                      {councilBusy === "analysis" ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                      {councilAnalysesReady ? "Analizy gotowe" : "Uruchom analizy"}
                    </Button>
                  </div>
                  {councilAnalyses.length === 0 ? (
                    <p className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2 text-xs text-muted-foreground">
                      Po uruchomieniu zobaczysz osobne opinie modeli, a nie jedną zbiorczą ścianę tekstu.
                    </p>
                  ) : (
                    <div className="grid gap-2 lg:grid-cols-3">
                      {councilAnalyses.map((analysis, index) => (
                        <div key={`${analysis.model_id || "model"}-${index}`} className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-black/10 p-3 text-xs">
                          <p className="font-semibold text-foreground">{councilModelLabel(analysis.model_id)}</p>
                          <p className="mt-1 line-clamp-5 text-muted-foreground">{councilSnippet(councilAnalysisTerminalText(analysis), 360)}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {councilAnalysesReady ? (
                    <Button size="sm" className="h-8" onClick={() => setSelectedCouncilStage("discussion")} data-testid="project-council-stage-analysis-next">
                      Dalej: dyskusja modeli
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                </div>
              ) : null}

              {visibleCouncilStage === "discussion" ? (
                <div className="space-y-3">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="text-xs font-semibold text-sylion-amber">4. Dyskusja modeli</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Modele odnoszą się do swoich opinii, kwestionują założenia i przygotowują grunt pod propozycje dla operatora.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      className="h-8"
                      data-testid="project-council-stage-run-discussion"
                      onClick={() => handleRunProjectCouncilDiscussion().catch(() => {})}
                      disabled={councilBusy !== null || !councilAnalysesReady}
                    >
                      {councilBusy === "discussion" ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <UsersRound className="mr-1.5 h-3.5 w-3.5" />}
                      {councilDiscussionReady ? "Dyskusja gotowa" : "Uruchom dyskusję"}
                    </Button>
                  </div>
                  {councilDiscussion.length === 0 ? (
                    <p className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2 text-xs text-muted-foreground">
                      Najpierw muszą być gotowe opinie modeli. Potem uruchom dyskusję i zobacz, gdzie modele się zgadzają albo spierają.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {councilDiscussion.map((round, index) => (
                        <div key={`${round.model_id || "model"}-${round.round_number || index}`} className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-black/10 p-3 text-xs">
                          <p className="font-semibold text-foreground">{councilModelLabel(round.model_id)}</p>
                          <p className="mt-1 text-muted-foreground">{councilSnippet(councilReadableModelText(round.contribution), 520)}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {councilDiscussionReady ? (
                    <Button size="sm" className="h-8" onClick={() => setSelectedCouncilStage("proposal")} data-testid="project-council-stage-discussion-next">
                      Dalej: propozycje A/B/C
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                </div>
              ) : null}

              {visibleCouncilStage === "proposal" ? (
                <div className="space-y-3">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="text-xs font-semibold text-sylion-amber">5. Wniosek Rady i wybór wariantu</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Tu Rada powinna pokazać propozycje A/B/C/D. Operator może wybrać wariant albo wpisać własny kierunek.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      className="h-8"
                      data-testid="project-council-stage-consolidate"
                      onClick={() => handleConsolidateProjectCouncil().catch(() => {})}
                      disabled={councilBusy !== null || !councilAnalysesReady}
                    >
                      {councilBusy === "consolidate" ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-1.5 h-3.5 w-3.5" />}
                      {councilConclusionReady ? "Odśwież warianty" : "Pokaż warianty"}
                    </Button>
                  </div>
                  {councilOperatorChoices.length > 0 ? (
                    <div className="grid gap-2 lg:grid-cols-2">
                      {councilOperatorChoices.map((choice) => (
                        <button
                          key={`stage-choice-${choice.label}`}
                          type="button"
                          className="rounded-lg border border-sylion-blue/25 bg-[#0b1020] p-3 text-left text-xs transition hover:border-sylion-blue/45 hover:bg-sylion-blue/10"
                          data-testid={`project-council-stage-choice-${choice.label}`}
                          onClick={() => applyCouncilOperatorChoice(choice)}
                        >
                          <span className="font-semibold text-sylion-blue">Wariant {choice.label}</span>
                          <span className="mt-1 block text-muted-foreground">{councilSnippet(labelProjectVisibleText(choice.text), 360)}</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2 text-xs text-muted-foreground">
                      Kliknij „Pokaż warianty”, żeby Rada zsyntetyzowała propozycje wyboru.
                    </p>
                  )}
                  <div className="space-y-2">
                    <label className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Inny kierunek operatora
                    </label>
                    <textarea
                      className="min-h-[78px] w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 py-2 text-sm outline-none focus:border-sylion-amber/60"
                      data-testid="project-council-stage-custom-choice"
                      placeholder="Wpisz własną decyzję albo warunek, np. wybieram B, ale najpierw tylko MVP bez modułu płatności."
                      value={councilQuestion}
                      onChange={(event) => {
                        setCouncilQuestion(event.target.value);
                        setSelectedCouncilChoiceLabel("własny wariant");
                      }}
                    />
                    <Button
                      size="sm"
                      className="h-8"
                      data-testid="project-council-stage-send-choice"
                      onClick={() => handleCouncilGuideContinue().catch(() => {})}
                      disabled={councilBusy !== null || !councilQuestion.trim()}
                    >
                      Wyślij wybór do kolejnej rundy
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ) : null}

              {visibleCouncilStage === "book" ? (
                <div className="space-y-3">
                  <div>
                    <p className="text-xs font-semibold text-sylion-amber">6. Księga / Źródło Prawdy</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Księga powstaje punkt po punkcie. Zaznacz to, co jest już rozstrzygnięte, dodaj brakujące punkty i kontynuuj rundy, dopóki nie da się jej zatwierdzić.
                    </p>
                  </div>
                  {allCouncilBookItems.length === 0 ? (
                    <p className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2 text-xs text-muted-foreground">
                      Po analizach i wariantach pojawią się kandydaci do Księgi. Możesz też dodać pierwszy punkt ręcznie.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {allCouncilBookItems.map((item, index) => (
                        <label key={`stage-book-${index}`} className="flex gap-3 rounded-lg border border-sylion-green/15 bg-black/10 p-3 text-xs">
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={Boolean(approvedBookItems[item])}
                            onChange={(event) =>
                              setApprovedBookItems((prev) => ({ ...prev, [item]: event.target.checked }))
                            }
                          />
                          <span className="text-muted-foreground">
                            <span className="mr-2 font-semibold text-sylion-green">{index + 1}.</span>
                            {councilSnippet(item, 560)}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                  <div className="grid gap-2 lg:grid-cols-[1fr_auto]">
                    <input
                      className="h-9 rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 text-sm outline-none focus:border-sylion-amber/60"
                      data-testid="project-council-stage-book-new-item"
                      placeholder="Dodaj punkt do Księgi, np. System ma obsługiwać etap ofertowania i produkcji."
                      value={newBookItem}
                      onChange={(event) => setNewBookItem(event.target.value)}
                    />
                    <Button size="sm" className="h-9" onClick={handleAddManualBookItem} data-testid="project-council-stage-book-add">
                      Dodaj punkt
                    </Button>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" className="h-8" onClick={handleConfirmBookDraft} data-testid="project-council-stage-book-confirm">
                      Zatwierdź zaznaczone ({approvedBookCount})
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                      onClick={() => handleFreezeCanon().catch(() => {})}
                      disabled={freezeCanonLoading || (!canon?.book && !project?.canonical_book)}
                      data-testid="project-council-stage-freeze-canon"
                    >
                      {freezeCanonLoading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Snowflake className="mr-1.5 h-3.5 w-3.5" />}
                      Zamroź Księgę
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2 xl:justify-end">
            <Link
              href={`/projects/${encodeURIComponent(projectId)}/orchestration#project-council`}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-sylion-blue/35 bg-sylion-blue/10 px-3 text-xs font-semibold text-sylion-blue transition hover:bg-sylion-blue/20"
              data-testid="open-project-council-config"
            >
              <UsersRound className="w-3.5 h-3.5" />
              Ustaw Radę
            </Link>
            <Link
              href={`/projects/${encodeURIComponent(projectId)}/orchestration#v10-full-council`}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-sylion-amber/35 bg-sylion-amber/10 px-3 text-xs font-semibold text-sylion-amber transition hover:bg-sylion-amber/20"
              data-testid="open-project-council-deliberation"
            >
              Rozpocznij dyskusję V10
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <a
              href="#project-pending-decisions"
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-sylion-green/35 bg-sylion-green/10 px-3 text-xs font-semibold text-sylion-green transition hover:bg-sylion-green/20"
              data-testid="open-project-direction-decisions"
            >
              Wybierz kierunek
            </a>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Pytania oczekujące</p>
          <p className="text-2xl font-semibold mt-1">{pendingQuestions.length}</p>
        </Card>
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Moduły</p>
          <p className="text-2xl font-semibold mt-1">{modules.length}</p>
        </Card>
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Koszt bieżący</p>
          <p className="text-2xl font-semibold mt-1">${Number(cost.running_total ?? 0).toFixed(2)}</p>
        </Card>
      </div>

      <Card id="project-pending-decisions" className="p-4 bg-[#0f1629] border-sylion-blue/20 space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <UsersRound className="w-4 h-4 text-sylion-blue" />
              Rozmowa z Radą
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Pisz jak w terminalu: jedno pytanie, jeden wybór, jedna kontynuacja. AEIS sam prowadzi opinie modeli, ich dyskusję, warianty A/B/C i roboczą Księgę.
            </p>
          </div>
          <Badge variant="outline" className="w-fit border-sylion-blue/30 text-sylion-blue">
            {activeCouncilSessionId ? `Runda ${activeCouncilRoundNumber} · sesja ${activeCouncilSessionId.slice(0, 8)}` : "brak aktywnej rundy"}
          </Badge>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-3 rounded-lg border border-[rgba(148,163,184,0.1)] bg-black/10 p-3">
            <div
              className="rounded-lg border border-sylion-blue/20 bg-[#080d19] p-3"
              data-testid="project-council-cli-guide"
              aria-live="polite"
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <TerminalSquare className="h-4 w-4 text-sylion-blue" />
                  <span className="font-mono text-xs font-semibold text-sylion-blue">AEIS &gt;</span>
                  <span className="text-xs font-semibold">{councilGuideStatus.title}</span>
                </div>
                <Badge variant="outline" className="border-sylion-blue/25 text-[10px] text-sylion-blue">
                  {selectedCouncilChoiceLabel || `Runda ${activeCouncilRoundNumber}`}
                </Badge>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">{councilGuideStatus.body}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-5">
                {councilGuideSteps.map((step, index) => (
                  <div
                    key={step.label}
                    className={`rounded-md border px-2 py-2 text-center text-[10px] ${
                      step.done
                        ? "border-sylion-green/25 bg-sylion-green/10 text-sylion-green"
                        : step.active
                          ? "border-sylion-blue/35 bg-sylion-blue/10 text-sylion-blue"
                          : "border-[rgba(148,163,184,0.08)] bg-black/10 text-muted-foreground"
                    }`}
                  >
                    <span className="block font-mono">{index + 1}</span>
                    <span className="block font-semibold">{step.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <label className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Twoja wiadomość do Rady
            </label>
            <textarea
              className="min-h-[116px] w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 py-2 text-sm outline-none focus:border-primary/60"
              data-testid="project-council-question-input"
              placeholder="Np. przeanalizuj ten projekt i pokaż mi 3 możliwe kierunki. Albo: wybieram wariant B, ale chcę tańszy MVP."
              value={councilQuestion}
              onChange={(event) => {
                setCouncilQuestion(event.target.value);
                setSelectedCouncilChoiceLabel(null);
              }}
            />
            <div className="flex flex-wrap items-center gap-2">
              <label
                className={`inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-sylion-blue/35 bg-sylion-blue/10 px-3 text-xs font-semibold text-sylion-blue transition hover:bg-sylion-blue/20 ${
                  councilAttachmentUploading ? "pointer-events-none opacity-70" : ""
                }`}
                data-testid="project-council-upload-attachment"
              >
                {councilAttachmentUploading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Upload className="w-3.5 h-3.5" />
                )}
                {councilAttachmentUploading ? "Analizuję załącznik" : "Dodaj załącznik"}
                <input
                  type="file"
                  multiple
                  className="sr-only"
                  disabled={councilAttachmentUploading || councilBusy !== null}
                  onChange={(event) => {
                    void handleUploadProjectCouncilAttachments(event.currentTarget.files).finally(() => {
                      event.currentTarget.value = "";
                    });
                  }}
                />
              </label>
              <span className="text-xs text-muted-foreground">
                PDF, DOCX, TXT, Markdown, kod, ZIP, obrazy i inne pliki trafiają do lokalnej analizy przed wysłaniem pytania.
              </span>
            </div>
            {(project.attachments ?? []).length > 0 ? (
              <div
                className="rounded-md border border-sylion-blue/15 bg-sylion-blue/5 px-3 py-2 text-xs text-muted-foreground"
                data-testid="project-council-attachment-context-summary"
              >
                <p className="font-medium text-foreground">Załączniki dołączane do pytania Rady</p>
                <div className="mt-1 space-y-1">
                  {(project.attachments ?? []).slice(0, 3).map((attachment) => {
                    const analysis = latestAttachmentAnalysis(attachment);
                    return (
                      <div key={attachment.attachment_id} className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{attachment.filename || attachment.attachment_id}</span>
                        <span>{formatFileSize(attachment.file_size)}</span>
                        <Badge variant="outline" className="text-[9px]">
                          {analysis?.detected_kind || "bez analizy"}
                        </Badge>
                        {analysis?.extracted_text_preview ? (
                          <span className="text-sylion-green">podgląd gotowy</span>
                        ) : (
                          <span className="text-sylion-amber">brak podglądu treści</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
            <div
              className="rounded-md border border-sylion-blue/20 bg-sylion-blue/5 px-3 py-2 text-xs text-muted-foreground"
              data-testid="project-council-next-step"
              aria-live="polite"
            >
              <span className="font-semibold text-sylion-blue">Co dalej: </span>
              {councilNextStep}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Button
                size="sm"
                className="h-10 w-full justify-center sm:w-auto"
                data-testid="project-council-guide-continue"
                onClick={() => handleCouncilGuideContinue().catch(() => {})}
                disabled={councilBusy !== null}
              >
                {councilBusy !== null ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : councilConclusionReady && councilQuestion.trim() ? (
                  <Send className="mr-2 h-4 w-4" />
                ) : councilAnalysesReady && !councilConclusionReady ? (
                  <Sparkles className="mr-2 h-4 w-4" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                {councilBusy === "analysis"
                  ? "Rada analizuje"
                  : councilBusy === "discussion"
                    ? "Modele dyskutują"
                    : councilBusy === "consolidate"
                      ? "AEIS układa warianty"
                      : councilGuideStatus.label}
              </Button>
              <span className="text-xs text-muted-foreground">
                Jeden przycisk prowadzi rozmowę przez kolejne kroki.
              </span>
            </div>
            <details className="rounded-md border border-[rgba(148,163,184,0.08)] bg-background/20 p-2">
              <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Ręczne kroki AEIS
              </summary>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  className="h-8"
                  data-testid="project-council-start-question"
                  onClick={() => handleStartProjectCouncilQuestion().catch(() => {})}
                  disabled={councilBusy !== null}
                >
                  {councilBusy === "start" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1.5" />}
                  Nowa runda Rady
                </Button>
                <Button
                  size="sm"
                  variant={!councilAnalysesReady ? "default" : "outline"}
                  className="h-8"
                  data-testid="project-council-run-analysis"
                  onClick={() => handleRunProjectCouncilAnalysis().catch(() => {})}
                  disabled={councilBusy !== null || councilAnalysesReady}
                >
                  {councilBusy === "analysis" ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : councilAnalysesReady ? (
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  ) : (
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  {councilBusy === "analysis"
                    ? "Analizuję modele"
                    : councilAnalysesReady
                      ? "Analizy gotowe"
                      : councilNeedsDeepAttachmentRerun
                        ? "Uzupełnij analizę"
                        : "Analiza modeli"}
                </Button>
                <Button
                  size="sm"
                  variant={councilAnalysesReady && !councilDiscussionReady ? "default" : "outline"}
                  className="h-8"
                  data-testid="project-council-run-discussion"
                  onClick={() => handleRunProjectCouncilDiscussion().catch(() => {})}
                  disabled={councilBusy !== null || !councilAnalysesReady}
                >
                  {councilBusy === "discussion" ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : councilDiscussionReady ? (
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  ) : (
                    <UsersRound className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  {councilBusy === "discussion"
                    ? "Dyskutuję"
                    : councilDiscussionReady
                      ? "Dyskusja gotowa"
                      : "Dyskusja modeli"}
                </Button>
                <Button
                  size="sm"
                  variant={councilAnalysesReady && !councilConclusionReady ? "default" : "outline"}
                  className="h-8 border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                  data-testid="project-council-consolidate"
                  onClick={() => handleConsolidateProjectCouncil().catch(() => {})}
                  disabled={councilBusy !== null || !councilAnalysesReady}
                >
                  {councilBusy === "consolidate" ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : councilConclusionReady ? (
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  {councilBusy === "consolidate"
                    ? "Buduję wniosek"
                    : councilConclusionReady
                      ? "Wniosek gotowy"
                      : "Wniosek Rady"}
                </Button>
              </div>
            </details>
            {councilNotice ? (
              <p className="rounded-md border border-sylion-blue/20 bg-sylion-blue/5 px-3 py-2 text-xs text-muted-foreground" data-testid="project-council-notice">
                {councilNotice}
              </p>
            ) : null}
            {councilAnalysisErrorCount > 0 ? (
              <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive" data-testid="project-council-analysis-errors">
                {councilAnalysisErrorCount} odpowiedzi modeli nie nadaje się do decyzji. Rada pozostaje zablokowana do czasu uzyskania co najmniej dwóch realnych analiz.
              </p>
            ) : null}
          </div>

          <div className="space-y-2 rounded-lg border border-[rgba(148,163,184,0.1)] bg-black/10 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Rundy Rady do Księgi</p>
            {projectCouncilSessions.length === 0 ? (
              <p className="text-xs text-muted-foreground">Nie ma jeszcze rund dyskusji. Wpisz pomysł, decyzję albo pytanie i kliknij „Nowa runda Rady”.</p>
            ) : (
              <div className="space-y-1">
                {councilRounds.slice().reverse().slice(0, 5).map((session) => {
                  const roundNumber = projectCouncilRoundNumber(session, projectCouncilSessions);
                  return (
                    <button
                      key={session.session_id}
                      type="button"
                      className={`w-full rounded-md border px-3 py-2 text-left text-xs transition ${
                        activeCouncilSessionId === session.session_id
                          ? "border-sylion-blue/35 bg-sylion-blue/10 text-foreground"
                          : "border-[rgba(148,163,184,0.08)] bg-background/30 text-muted-foreground hover:bg-muted/20"
                      }`}
                      data-testid={`project-council-session-${session.session_id}`}
                      onClick={() => loadProjectCouncilSession(session.session_id).catch(() => {})}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium">Runda {roundNumber}: {projectCouncilSessionTitle(session)}</span>
                        <span className="shrink-0 rounded-full border border-sylion-blue/20 px-1.5 py-0.5 text-[9px] text-sylion-blue">
                          {activeCouncilSessionId === session.session_id ? "aktywna" : "wybierz"}
                        </span>
                      </span>
                      <span className="mt-0.5 block text-[10px]">
                        {COUNCIL_PHASE_LABELS[String(session.phase || "")] || labelStatus(session.status)}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[1.15fr_0.95fr_0.9fr]" data-testid="project-council-decision-workspace">
          <div className="rounded-lg border border-[rgba(148,163,184,0.1)] bg-background/25 p-3" data-testid="project-council-terminal">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <TerminalSquare className="h-4 w-4 text-sylion-blue" />
                <p className="text-xs font-semibold">Terminal Rady</p>
              </div>
              <Badge variant="outline" className="text-[10px]">
                {councilTerminalLines.length} wpisów
              </Badge>
            </div>
            <div className="max-h-[430px] space-y-2 overflow-auto rounded-lg border border-[rgba(148,163,184,0.08)] bg-[#080d19] p-2">
              {councilTerminalLines.map((line, index) => (
                <div
                  key={`${line.kind}-${line.speaker}-${index}`}
                  className={`rounded-md border px-3 py-2 ${
                    line.kind === "conclusion"
                      ? "border-sylion-green/25 bg-sylion-green/10"
                      : "border-[rgba(148,163,184,0.08)] bg-black/20"
                  }`}
                >
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wider">
                    <span className="font-mono text-sylion-blue">&gt;</span>
                    <span className={line.kind === "conclusion" ? "text-sylion-green" : "text-sylion-blue"}>
                      {line.speaker}
                    </span>
                    <span className="text-muted-foreground">
                      {line.kind === "operator"
                        ? "status"
                        : line.kind === "analysis"
                          ? "analiza"
                          : line.kind === "discussion"
                            ? "dyskusja"
                            : "wniosek"}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap break-words text-xs leading-relaxed text-muted-foreground">
                    {councilSnippet(line.text, line.kind === "conclusion" ? 620 : 360)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-sylion-blue/20 bg-sylion-blue/5 p-3" data-testid="project-council-operator-choices">
            <div className="mb-3 flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-sylion-blue" />
              <div>
                <p className="text-xs font-semibold">Wybór operatora</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">Wybierz wariant jak w dialogu CLI, dopisz warunek i uruchom następną rundę.</p>
              </div>
            </div>
            {councilOperatorChoices.length === 0 ? (
              <p className="rounded-md border border-[rgba(148,163,184,0.08)] bg-background/25 px-3 py-2 text-xs text-muted-foreground">
                Po analizie modeli pojawią się warianty A/B/C. Jeśli wariantów nie ma, to jest błąd jakości odpowiedzi Rady i trzeba powtórzyć analizę głębiej.
              </p>
            ) : (
              <div className="space-y-2">
                {councilOperatorChoices.map((choice) => (
                  <button
                    key={`${choice.kind}-${choice.label}`}
                    type="button"
                    className="w-full rounded-md border border-sylion-blue/25 bg-[#0b1020] px-3 py-2 text-left transition hover:border-sylion-blue/45 hover:bg-sylion-blue/10"
                    data-testid={`project-council-choice-${choice.label}`}
                    onClick={() => applyCouncilOperatorChoice(choice)}
                  >
                    <span className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-sylion-blue">Wariant {choice.label}</span>
                      <span className="text-[10px] text-muted-foreground">{choice.source}</span>
                    </span>
                    <span className="mt-1 block break-words text-xs leading-relaxed text-muted-foreground">
                      {councilSnippet(labelProjectVisibleText(choice.text), 300)}
                    </span>
                  </button>
                ))}
              </div>
            )}
            <div className="mt-3 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Pytania Rady do rozstrzygnięcia</p>
              {councilQuestionChoices.length === 0 ? (
                <p className="text-xs text-muted-foreground">Brak zapisanych pytań doprecyzowujących w tej rundzie.</p>
              ) : (
                councilQuestionChoices.map((choice) => (
                  <button
                    key={`${choice.kind}-${choice.label}`}
                    type="button"
                    className="w-full rounded-md border border-[rgba(148,163,184,0.08)] bg-background/25 px-3 py-2 text-left transition hover:bg-muted/20"
                    data-testid={`project-council-question-choice-${choice.label}`}
                    onClick={() => applyCouncilOperatorChoice(choice)}
                  >
                    <span className="text-[10px] font-semibold text-sylion-amber">{choice.label}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{councilSnippet(labelProjectVisibleText(choice.text), 220)}</span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="rounded-lg border border-sylion-green/20 bg-sylion-green/5 p-3" data-testid="project-council-book-draft">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-sylion-green" />
              <div>
                <p className="text-xs font-semibold text-sylion-green">Księga robocza</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">Tu trafiają kandydaci do Źródła Prawdy z analiz, dyskusji i wniosku.</p>
              </div>
            </div>
            {councilBookDraftItems.length === 0 ? (
              <p className="text-xs text-muted-foreground">Księga zacznie się wypełniać po analizie załączników i pierwszej rundzie modeli.</p>
            ) : (
              <ul className="max-h-[430px] space-y-2 overflow-auto text-xs leading-relaxed text-muted-foreground">
                {councilBookDraftItems.map((item, index) => (
                  <li key={`book-draft-${index}`} className="rounded-md border border-sylion-green/15 bg-black/10 px-3 py-2">
                    <span className="mr-2 font-semibold text-sylion-green">{index + 1}.</span>
                    {councilSnippet(item, 520)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <details className="rounded-lg border border-[rgba(148,163,184,0.1)] bg-background/20 p-3">
          <summary className="cursor-pointer text-xs font-semibold text-sylion-blue">
            Pełne analizy i zapis dyskusji
          </summary>
          <div className="mt-3 grid gap-3 xl:grid-cols-3">
            <div className="rounded-lg border border-[rgba(148,163,184,0.1)] bg-background/25 p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold">Analizy modeli</p>
                <Badge variant="outline" className="text-[10px]">{councilAnalyses.length}</Badge>
              </div>
              {councilAnalyses.length === 0 ? (
                <p className="text-xs text-muted-foreground">Po kliknięciu „Analiza modeli” pojawią się osobne stanowiska modeli.</p>
              ) : (
                <div className="space-y-2">
                  {councilAnalyses.map((analysis, index) => {
                    const summaryText = councilText(analysis.rationale || analysis.analysis_text);
                    const fullText = councilText(analysis.analysis_text || analysis.rationale);
                    const analysisSections = councilAnalysisSections(analysis);
                    return (
                      <div key={`${analysis.model_id || "model"}-${index}`} className="rounded-md border border-[rgba(148,163,184,0.08)] px-2 py-2 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{councilModelLabel(analysis.model_id)}</span>
                          <Badge variant="outline" className="text-[9px]">{labelStatus(analysis.verdict)}</Badge>
                        </div>
                        <p className="mt-1 text-muted-foreground">{summaryText}</p>
                        {analysisSections.length > 0 ? (
                          <div className="mt-2 space-y-2 rounded-md border border-sylion-blue/10 bg-sylion-blue/5 p-2">
                            {analysisSections.map((section) => (
                              <div key={section.title}>
                                <p className="text-[10px] font-semibold uppercase tracking-wider text-sylion-blue">{section.title}</p>
                                <ul className="mt-1 space-y-1 text-[10px] leading-relaxed text-muted-foreground">
                                  {section.items.slice(0, 5).map((item, itemIndex) => (
                                    <li key={`${section.title}-${itemIndex}`}>- {item}</li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {fullText !== summaryText || fullText.length > 500 ? (
                          <details className="mt-2 rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-2 py-1">
                            <summary className="cursor-pointer text-[10px] font-semibold text-sylion-blue">
                              Pełna odpowiedź modelu
                            </summary>
                            <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-relaxed text-muted-foreground">
                              {fullText}
                            </pre>
                          </details>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="rounded-lg border border-[rgba(148,163,184,0.1)] bg-background/25 p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold">Dyskusja modeli</p>
                <Badge variant="outline" className="text-[10px]">{councilDiscussion.length}</Badge>
              </div>
              {councilDiscussion.length === 0 ? (
                <p className="text-xs text-muted-foreground">Po analizie uruchom „Dyskusja modeli”, żeby modele odniosły się do siebie nawzajem.</p>
              ) : (
                <div className="space-y-2">
                  {councilDiscussion.map((round, index) => (
                    <div key={`${round.model_id || "model"}-${round.round_number || index}`} className="rounded-md border border-[rgba(148,163,184,0.08)] px-2 py-2 text-xs">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[9px]">Runda {round.round_number || index + 1}</Badge>
                        <span className="font-medium">{councilModelLabel(round.model_id)}</span>
                      </div>
                      <p className="mt-1 line-clamp-5 text-muted-foreground">{councilText(round.contribution)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-lg border border-sylion-green/20 bg-sylion-green/5 p-3">
              <div className="mb-2 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sylion-green" />
                <p className="text-xs font-semibold text-sylion-green">Wniosek i kierunek</p>
              </div>
              {councilConsolidated ? (
                <pre className="max-h-[280px] whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">{councilConsolidated}</pre>
              ) : (
                <p className="text-xs text-muted-foreground">Kliknij „Wniosek Rady”, gdy są już analizy albo dyskusja. Tu pojawi się rekomendacja kierunku dla operatora.</p>
              )}
            </div>
          </div>
        </details>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <h2 className="text-sm font-semibold mb-3">Oś czasu</h2>
          <div className="space-y-2">
            {timeline.map((stage) => (
              <div key={stage.stage} className="flex items-center justify-between rounded-lg border border-[rgba(148,163,184,0.06)] px-3 py-2">
                <div>
                  <p className="text-xs font-medium">{labelStage(stage.stage)}</p>
                  <p className="text-[10px] text-muted-foreground">{fmt(stage.updated_at)}</p>
                </div>
                <Badge variant="outline" className="text-[9px]">{labelStatus(stage.status)}</Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <h2 className="text-sm font-semibold mb-3">Pytania Rady do operatora</h2>
          <div className="space-y-2">
            {pendingQuestions.length === 0 ? (
              <p className="text-xs text-muted-foreground">Rada nie zadała teraz pytań blokujących. Możesz zadać własne pytanie w panelu dyskusji modeli powyżej.</p>
            ) : (
              pendingQuestions.map((question) => (
                <div
                  key={question.question_id}
                  className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-3 space-y-3"
                  data-testid={`pending-question-${question.question_id}`}
                >
                  <div>
                    <p className="text-xs font-medium">{question.context}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      Faza: {labelStage(question.phase)} · klucz: {question.key || question.question_id}
                    </p>
                  </div>

                  <div className="space-y-2">
                    {(question.choices ?? []).map((choice) => (
                      <div
                        key={choice.choice_id}
                        className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold">{choice.label || choice.choice_id}</p>
                            {choice.rationale && (
                              <p className="text-[10px] text-muted-foreground mt-1">{choice.rationale}</p>
                            )}
                            {choice.consequences && (
                              <p className="text-[10px] text-sylion-amber mt-1">{choice.consequences}</p>
                            )}
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 shrink-0 text-[10px]"
                            data-testid={`answer-choice-${choice.choice_id}`}
                            disabled={answeringQuestionId === question.question_id}
                            onClick={() => handleAnswerQuestion(question, choice.choice_id).catch(() => {})}
                          >
                            {answeringQuestionId === question.question_id ? (
                              <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                            ) : null}
                            Wybierz
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2 border-t border-border/30 pt-3">
                    <label className="block text-[10px] uppercase tracking-wider text-muted-foreground">
                      Uzasadnienie operatora
                    </label>
                    <textarea
                      className="min-h-[54px] w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 py-2 text-xs outline-none focus:border-primary/60"
                      placeholder="Np. wybieram wariant pełniejszy, żeby wymusić więcej bramek człowieka i testów nadzoru."
                      value={answerRationales[question.question_id] || ""}
                      onChange={(event) =>
                        setAnswerRationales((prev) => ({ ...prev, [question.question_id]: event.target.value }))
                      }
                    />

                    <label className="block text-[10px] uppercase tracking-wider text-muted-foreground">
                      Własna odpowiedź, jeśli warianty Rady są niewystarczające
                    </label>
                    <textarea
                      className="min-h-[54px] w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 py-2 text-xs outline-none focus:border-primary/60"
                      data-testid={`custom-answer-${question.question_id}`}
                      placeholder="Wpisz decyzję ręczną. Zostanie zapisana jako human-dashboard i trafi do audytu."
                      value={customAnswers[question.question_id] || ""}
                      onChange={(event) =>
                        setCustomAnswers((prev) => ({ ...prev, [question.question_id]: event.target.value }))
                      }
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-[10px]"
                      data-testid={`submit-custom-answer-${question.question_id}`}
                      disabled={answeringQuestionId === question.question_id}
                      onClick={() => handleAnswerQuestion(question, undefined, true).catch(() => {})}
                    >
                      {answeringQuestionId === question.question_id ? (
                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                      ) : null}
                      Zapisz własną decyzję
                    </Button>
                  </div>
                </div>
              ))
            )}
            {answerNotice && (
              <p className="text-[10px] text-muted-foreground italic" data-testid="answer-question-notice">
                {answerNotice}
              </p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-1.5">
            Canon
            <HelpTip text="Kanoniczna Księga projektu jako Źródło Prawdy składana po Rundzie 1 dyskusji Rady. Po zatwierdzeniu możesz ją zamrozić. Od tego momentu zmiana wymaga formalnej ponownej rundy Rady. Zamrożenie odblokowuje Rundę 2, czyli Masterplan." />
          </h2>
          <pre className="text-[11px] whitespace-pre-wrap text-muted-foreground">{canon?.book || project.canonical_book}</pre>
          <div
            className="pt-3 border-t border-border/30 flex items-center justify-between gap-2"
            data-testid="canon-freeze-footer"
          >
            {project.canon_frozen_at ? (
              <Badge
                variant="outline"
                className="border-sylion-green/30 text-sylion-green text-[10px]"
                data-testid="canon-frozen-badge"
              >
                Zamrożone {fmt(project.canon_frozen_at)}
              </Badge>
            ) : project.approvals?.book_pending_ticket_id ? (
              <Badge
                variant="outline"
                className="border-sylion-amber/30 text-sylion-amber text-[10px]"
                data-testid="canon-pending-human-gate-badge"
              >
                Bramka oczekuje: {project.approvals.book_pending_ticket_id.slice(0, 12)}
              </Badge>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  data-testid="freeze-canon-btn"
                  onClick={handleFreezeCanon}
                  disabled={
                    freezeCanonLoading ||
                    (!canon?.book && !project.canonical_book)
                  }
                  className="h-7 text-[10px] bg-sylion-green/15 text-sylion-green hover:bg-sylion-green/25 border border-sylion-green/30"
                  title={
                    !canon?.book && !project.canonical_book
                      ? "Najpierw przygotuj Księgę (Rada Round 1)"
                      : undefined
                  }
                >
                  {freezeCanonLoading ? (
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  ) : (
                    <Snowflake className="w-3 h-3 mr-1" />
                  )}
                  Zamroź jako Źródło Prawdy
                </Button>
                <HelpTip text="Zamraża obecną Księgę jako kanoniczne Źródło Prawdy projektu. Po zamrożeniu zmiana wymaga formalnego rerun Rady (Round 1 -> Round 2 gate). Wymaga zatwierdzenia w Human Gate." />
              </div>
            )}
            {freezeCanonNotice && (
              <p
                data-testid="canon-freeze-notice"
                className="text-[10px] text-muted-foreground italic max-w-[60%] text-right"
              >
                {freezeCanonNotice}
              </p>
            )}
          </div>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-1.5">
            Masterplan
            <HelpTip text="Plan operacyjny: workerzy, lane, taski, koszty, autonomia. Powstaje w Rundzie 2 po zamrożeniu Księgi. Po zatwierdzeniu możesz go zamrozić. Od tego momentu workerzy mogą być dopuszczani do budowy (Runda 3)." />
          </h2>
          <pre className="text-[11px] whitespace-pre-wrap text-muted-foreground">{masterplan?.summary || project.masterplan}</pre>
          <div
            className="pt-3 border-t border-border/30 flex items-center justify-between gap-2"
            data-testid="masterplan-freeze-footer"
          >
            {project.masterplan_frozen_at ? (
              <Badge
                variant="outline"
                className="border-sylion-green/30 text-sylion-green text-[10px]"
                data-testid="masterplan-frozen-badge"
              >
                Zamrożone {fmt(project.masterplan_frozen_at)}
              </Badge>
            ) : project.approvals?.operating_model_pending_ticket_id ? (
              <Badge
                variant="outline"
                className="border-sylion-amber/30 text-sylion-amber text-[10px]"
                data-testid="masterplan-pending-human-gate-badge"
              >
                Bramka oczekuje: {project.approvals.operating_model_pending_ticket_id.slice(0, 12)}
              </Badge>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  data-testid="freeze-masterplan-btn"
                  onClick={handleFreezeMasterplan}
                  disabled={freezeMpLoading || !project.canon_frozen_at}
                  className="h-7 text-[10px] bg-sylion-amber/15 text-sylion-amber hover:bg-sylion-amber/25 border border-sylion-amber/30"
                  title={
                    !project.canon_frozen_at
                      ? "Najpierw zamroź Źródło Prawdy (Runda 1)"
                      : undefined
                  }
                >
                  {freezeMpLoading ? (
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  ) : (
                    <Snowflake className="w-3 h-3 mr-1" />
                  )}
                  Zamroź Masterplan
                </Button>
                <HelpTip text="Zamraża Masterplan po Rundzie 2. Wymaga wcześniejszego zamrożenia Księgi. Po zamrożeniu Masterplan staje się kontraktem dla workerów; zmiana wymaga rerun Round 2 i Human Gate." />
              </div>
            )}
            {freezeMpNotice && (
              <p
                data-testid="masterplan-freeze-notice"
                className="text-[10px] text-muted-foreground italic max-w-[60%] text-right"
              >
                {freezeMpNotice}
              </p>
            )}
          </div>
        </Card>
      </div>

      <Card
        className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4"
        data-testid="build-authorization-panel"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              Autoryzacja budowy
              <HelpTip text="Runda 3: blok kosztu, poziom autonomii i polityka akcji zewnętrznych. Bez tej zgody workery nie powinny ruszyć." />
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Po zatwierdzeniu biletu bramki człowieka system uruchamia realny silnik wykonania i zapisuje artefakt oraz dowody.
            </p>
          </div>
          {project.build_authorized_at ? (
            <Badge variant="outline" className="border-sylion-green/30 text-sylion-green text-[10px]">
              Autoryzowane {fmt(project.build_authorized_at)}
            </Badge>
          ) : project.approvals?.build_pending_ticket_id ? (
            <Badge variant="outline" className="border-sylion-amber/30 text-sylion-amber text-[10px]">
              Bramka oczekuje: {project.approvals.build_pending_ticket_id.slice(0, 12)}
            </Badge>
          ) : !project.masterplan_frozen_at ? (
            <Badge variant="outline" className="text-[10px]">Najpierw zamroź Masterplan</Badge>
          ) : (
            <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue text-[10px]">Gotowe do Rundy 3</Badge>
          )}
        </div>

        {!project.build_authorized_at && !project.approvals?.build_pending_ticket_id && project.masterplan_frozen_at ? (
          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_2fr_auto] lg:items-end">
            <label className="space-y-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              Limit kosztu USD
              <input
                className="mt-1 h-9 w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 text-xs text-foreground outline-none focus:border-primary/60"
                data-testid="build-cost-cap-input"
                inputMode="decimal"
                value={buildCostCapUsd}
                onChange={(event) => {
                  setBuildCostCapUsd(event.target.value);
                  setBuildAuthorizeNotice(null);
                }}
              />
            </label>
            <label className="space-y-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              Poziom autonomii
              <select
                className="mt-1 h-9 w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-[#0b1020] px-3 text-xs text-foreground outline-none focus:border-primary/60"
                data-testid="build-autonomy-select"
                value={buildAutonomyLevel}
                onChange={(event) => {
                  setBuildAutonomyLevel(event.target.value);
                  setBuildAuthorizeNotice(null);
                }}
              >
                <option value="L0">L0 - tylko człowiek</option>
                <option value="L1">L1 - ręczne decyzję</option>
                <option value="L2">L2 - półautomatycznie</option>
                <option value="L3">L3 - wysoka autonomia</option>
                <option value="L4">L4 - auto w kapsule</option>
              </select>
            </label>
            <div className="grid gap-2 rounded-lg border border-[rgba(148,163,184,0.08)] bg-black/10 p-3 text-xs text-muted-foreground">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={blockExternalPublish}
                  onChange={(event) => {
                    setBlockExternalPublish(event.target.checked);
                    setBuildAuthorizeNotice(null);
                  }}
                />
                {buildPolicyLabels.blockLabel}
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={requireHgPerExport}
                  onChange={(event) => {
                    setRequireHgPerExport(event.target.checked);
                    setBuildAuthorizeNotice(null);
                  }}
                />
                {buildPolicyLabels.exportLabel}
              </label>
            </div>
            <Button
              size="sm"
              className="h-9"
              data-testid="authorize-build-btn"
              disabled={buildAuthorizeLoading}
              onClick={() => handleAuthorizeBuild().catch(() => {})}
            >
              {buildAuthorizeLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : null}
              Autoryzuj budowę
            </Button>
          </div>
        ) : null}

        {buildAuthorizeNotice && (
          <p className="text-[10px] text-muted-foreground italic" data-testid="build-authorize-notice">
            {buildAuthorizeNotice}
          </p>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-2 mb-3">
            <GitBranch className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-semibold">Moduły</h2>
          </div>
          <div className="space-y-2">
            {modules.map((module) => (
              <div key={module.module_id} className="rounded-lg border border-[rgba(148,163,184,0.06)] px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-medium">{module.name}</p>
                  <Badge variant="outline" className="text-[9px]">{labelStatus(module.status)}</Badge>
                </div>
                <p className="text-[10px] text-muted-foreground mt-1">{module.host_target || module.docker_profile || "nieprzypisane"}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-semibold">Audyt</h2>
          </div>
          <div className="space-y-2">
            {audit.length === 0 ? (
              <p className="text-xs text-muted-foreground">Brak wpisów audytu.</p>
            ) : (
              audit.slice(0, 8).map((item) => (
                <div key={item.audit_result_id} className="rounded-lg border border-[rgba(148,163,184,0.06)] px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-medium">{labelAuditType(item.audit_type)}</p>
                    <Badge variant="outline" className="text-[9px]">{labelStatus(item.status)}</Badge>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1">{fmt(item.executed_at)}</p>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
        <div className="flex items-center gap-2 mb-3">
          <Wallet className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold">Rejestr kosztów</h2>
        </div>
        <div className="space-y-2">
          {(cost.records ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">Brak wpisów kosztów.</p>
          ) : (
            cost.records.slice(0, 10).map((entry) => (
              <div key={entry.cost_entry_id} className="flex items-center justify-between rounded-lg border border-[rgba(148,163,184,0.06)] px-3 py-2">
                <div>
                  <p className="text-xs font-medium">{entry.provider || "system"} / {entry.model || "kontroler"}</p>
                  <p className="text-[10px] text-muted-foreground">{fmt(entry.timestamp)}</p>
                </div>
                <p className="text-xs font-semibold">${Number(entry.cost_usd ?? 0).toFixed(2)}</p>
              </div>
            ))
          )}
        </div>
      </Card>

      <div
        className={`fixed bottom-4 left-4 right-4 z-[90] max-h-[30vh] overflow-y-auto rounded-xl border border-sylion-blue/25 bg-[#070b15]/95 shadow-2xl shadow-black/40 backdrop-blur sm:left-auto ${
          projectTerminalOpen ? "sm:w-[560px]" : "sm:w-[360px]"
        }`}
        data-testid="project-w18-terminal"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[rgba(148,163,184,0.1)] px-3 py-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <TerminalSquare className="h-4 w-4 text-sylion-blue" />
              <p className="truncate text-sm font-semibold">W18 Terminal AEIS</p>
              <Badge variant="outline" className="hidden text-[10px] sm:inline-flex">
                projekt
              </Badge>
            </div>
            <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
              Kontekst: {project.title || projectId} · {COUNCIL_STAGE_LABELS[visibleCouncilStage]} · runda {activeCouncilRoundNumber}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            data-testid="project-w18-terminal-toggle"
            onClick={() => setProjectTerminalOpen((open) => !open)}
          >
            {projectTerminalOpen ? "Zwiń" : "Otwórz"}
          </Button>
        </div>

        {projectTerminalOpen ? (
          <div className="space-y-2 p-3">
            <div className="flex flex-wrap gap-2 text-[10px]">
              <Badge variant="outline" className="font-mono">
                {projectId.slice(0, 18)}
              </Badge>
              <Badge variant="outline">
                {activeCouncilSessionId ? "sesja Rady aktywna" : "bez sesji Rady"}
              </Badge>
              <Badge variant="outline">
                {project?.canon_frozen_at ? "Księga zamrożona" : "Księga robocza"}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4" data-testid="project-w18-terminal-capabilities">
              {PROJECT_TERMINAL_CAPABILITIES.map((capability) => (
                <div
                  key={capability}
                  className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/20 px-2 py-1 text-[10px] text-muted-foreground"
                >
                  {capability}
                </div>
              ))}
            </div>

            <div
              className="rounded-lg border border-sylion-blue/20 bg-sylion-blue/5 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground"
              data-testid="project-w18-moderator-contract"
            >
              <span className="font-semibold text-sylion-blue">Moderator W18: </span>
              prowadzi etap, pilnuje formatu rundy i wariantów A/B/C/D/E. Nie zatwierdza prawdy, nie podejmuje decyzji strategicznych i nie udaje operatora.
            </div>

            <div className="max-h-[260px] space-y-2 overflow-auto rounded-lg border border-[rgba(148,163,184,0.08)] bg-[#050814] p-2">
              {projectTerminalLines.map((line, index) => (
                <div
                  key={`${line.role}-${index}`}
                  className={`rounded-md border px-3 py-2 ${
                    line.role === "error"
                      ? "border-sylion-red/30 bg-sylion-red/10"
                      : line.role === "operator"
                        ? "border-sylion-blue/25 bg-sylion-blue/10"
                        : "border-[rgba(148,163,184,0.08)] bg-black/20"
                  }`}
                >
                  <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider">
                    <span className="font-mono text-sylion-blue">&gt;</span>
                    <span className={line.role === "error" ? "text-sylion-red" : "text-sylion-blue"}>
                      {line.role === "operator" ? "operator" : line.role === "system" ? "system" : "AEIS"}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-muted-foreground">
                    {line.text}
                  </p>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              {PROJECT_TERMINAL_QUICK_COMMANDS.map((command) => (
                <Button
                  key={command}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 font-mono text-[11px]"
                  data-testid={`project-w18-terminal-quick-${projectTerminalQuickCommandTestId(command)}`}
                  disabled={projectTerminalBusy}
                  onClick={() => handleProjectTerminalExec(command).catch(() => {})}
                >
                  {command}
                </Button>
              ))}
              <label
                className={`inline-flex h-7 cursor-pointer items-center rounded-md border border-[rgba(148,163,184,0.16)] px-2 text-[11px] transition hover:border-sylion-blue/45 hover:bg-sylion-blue/10 ${
                  councilAttachmentUploading || councilBusy !== null ? "pointer-events-none opacity-60" : ""
                }`}
                data-testid="project-w18-terminal-file-label"
              >
                {councilAttachmentUploading ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                )}
                Dodaj plik
                <input
                  type="file"
                  multiple
                  className="sr-only"
                  data-testid="project-w18-terminal-file-input"
                  disabled={councilAttachmentUploading || councilBusy !== null}
                  onChange={(event) => {
                    const input = event.currentTarget;
                    void handleProjectTerminalFileUpload(input.files).finally(() => {
                      input.value = "";
                    });
                  }}
                />
              </label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-[11px]"
                data-testid="project-w18-terminal-book"
                onClick={() => handleProjectTerminalExec("pokaż księgę").catch(() => {})}
              >
                Księga
              </Button>
              <Link
                href="/human-gate"
                className="inline-flex h-7 items-center rounded-md border border-[rgba(148,163,184,0.16)] px-2 text-[11px] transition hover:border-sylion-blue/45 hover:bg-sylion-blue/10"
                data-testid="project-w18-terminal-human-gate"
              >
                Bramka człowieka
              </Link>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-[11px]"
                data-testid="project-w18-terminal-execution"
                onClick={() => handleProjectTerminalExec("pokaż wykonanie").catch(() => {})}
              >
                Wykonanie
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-[11px]"
                data-testid="project-w18-terminal-council-next"
                disabled={projectTerminalBusy || councilBusy !== null}
                onClick={() => {
                  appendProjectTerminalLine({ role: "operator", text: "$ kontynuuj Radę" });
                  handleCouncilGuideContinue().catch((err) => {
                    const msg = err instanceof Error ? err.message : "błąd kontynuacji Rady";
                    appendProjectTerminalLine({ role: "error", text: redactProjectTerminalText(msg) });
                  });
                }}
              >
                Kontynuuj Radę
              </Button>
            </div>

            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                handleProjectTerminalExec().catch(() => {});
              }}
            >
              <input
                ref={projectTerminalInputRef}
                className="min-w-0 flex-1 rounded-md border border-[rgba(148,163,184,0.14)] bg-black/35 px-3 py-2 font-mono text-sm outline-none transition focus:border-sylion-blue/50"
                data-testid="project-w18-terminal-input"
                value={projectTerminalCommand}
                onChange={(event) => setProjectTerminalCommand(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    handleProjectTerminalExec().catch(() => {});
                  }
                }}
                placeholder="Napisz polecenie: co dalej, analizuj modele, pokaż księgę, /pomoc..."
              />
              <Button
                type="button"
                size="sm"
                className="h-10 px-3"
                data-testid="project-w18-terminal-submit"
                disabled={projectTerminalBusy}
                onMouseDown={(event) => {
                  event.preventDefault();
                  handleProjectTerminalExec().catch(() => {});
                }}
              >
                {projectTerminalBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </form>
          </div>
        ) : null}
      </div>
    </div>
  );
}
