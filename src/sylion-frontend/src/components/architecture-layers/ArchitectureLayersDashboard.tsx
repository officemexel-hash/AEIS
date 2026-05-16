"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BookOpen,
  Boxes,
  CheckCircle2,
  Database,
  GitBranch,
  KeyRound,
  Layers,
  Loader2,
  Network,
  RefreshCw,
  Route,
  Search,
  Settings2,
  ShieldCheck,
  Terminal,
  Users,
  Wallet,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Surface = {
  label: string;
  href: string;
};

type Layer = {
  id: string;
  number: number;
  canonical_name: string;
  polish_name: string;
  group: string;
  group_label: string;
  summary: string;
  operator_meaning: string;
  phase_touchpoints: number[];
  phase_span: string;
  surfaces: Surface[];
  subsystems: string[];
  operator_controls: string[];
  human_gates: string[];
  hard_rules: string[];
  runtime_assertion: string;
  coverage: {
    phase_count: number;
    surface_count: number;
    human_gate_count: number;
    subsystem_count: number;
  };
};

type LayerGroup = {
  id: string;
  label: string;
  range: string;
  summary: string;
};

type ArchitectureData = {
  summary: {
    layer_count: number;
    phase_count: number;
    principle: string;
    short_definition: string;
  };
  groups: LayerGroup[];
  layers: Layer[];
  phase_overlay: Record<string, string[]>;
  overlay_rules: Array<{ id: string; label: string; rule: string }>;
  talior_flow: Array<{ layer: string; text: string }>;
  working_model?: {
    definition: string;
    outputs: string[];
    principles: Array<{ id: string; label: string; description: string }>;
    entities: Array<{ id: string; label: string; description: string }>;
    default_policies: Array<{ id: string; label: string; value: string }>;
    audit_stages: Array<{ id: string; label: string; description: string }>;
    module_audit_fields: string[];
    runtime_truth_order: string[];
    module_statuses: string[];
  };
  implementation_planes?: Array<{ id: string; label: string; description: string }>;
  advisor_layer?: {
    id: string;
    label: string;
    summary: string;
    pillars: string[];
    specialized_advisors: string[];
    lifecycle_hooks: string[];
  };
  phase_patches?: Array<{ id: string; phase: string; severity: string; label: string; description: string }>;
  source_documents?: string[];
};

type LayerAction = {
  label: string;
  href: string;
  description: string;
  icon: LucideIcon;
  primary?: boolean;
};

const iconMap: Record<string, LucideIcon> = {
  W1: BookOpen,
  W2: Activity,
  W3: ShieldCheck,
  W4: Zap,
  W5: Boxes,
  W6: Zap,
  W7: ShieldCheck,
  W8: Database,
  W9: Wrench,
  W10: Search,
  W11: Users,
  W12: BookOpen,
  W13: GitBranch,
  W14: CheckCircle2,
  W15: Database,
  W16: Boxes,
  W17: AlertTriangle,
  W18: Terminal,
  W19: Layers,
};

function safeList<T>(value: T[] | undefined | null): T[] {
  return Array.isArray(value) ? value : [];
}

function groupTone(group: string): string {
  if (group === "foundation") return "border-sky-500/30 bg-sky-500/10 text-sky-200";
  if (group === "project_truth_plan") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  if (group === "execution_external") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  if (group === "operator_console") return "border-violet-500/30 bg-violet-500/10 text-violet-200";
  return "border-rose-500/30 bg-rose-500/10 text-rose-200";
}

function layerIcon(layer: Layer): LucideIcon {
  return iconMap[layer.id] ?? Layers;
}

function formatPhaseList(phases: number[]): string {
  if (!phases.length) return "brak";
  if (phases.length > 18) return "1-41";
  return phases.map((phase) => `F${phase}`).join(", ");
}

function layerCommand(layer: Layer): string {
  if (layer.id === "W18") return 'W18 > /projekt cockpit tryb="operator"';
  if (layer.id === "W11") return "W18 > /rada warianty A/B/C/D/E";
  if (layer.id === "W12") return "W18 > /księga pokaż źródło_prawdy";
  if (layer.id === "W13") return "W18 > /masterplan pokaż moduły";
  return `W18 > /warstwa pokaż ${layer.id}`;
}

const LAYER_TECHNICAL_LABELS: Record<string, string> = {
  W1: "Kanon / Konstytucja systemu",
  W2: "Bootstrap / Instalacja / Obszar pracy",
  W3: "Tożsamość operatora / Uprawnienia / Profil",
  W4: "Katalog providerów i modeli",
  W5: "Środowisko wykonania / Infrastruktura",
  W6: "Defaulty / Autonomia / Polityki",
  W7: "Guards / Bramka człowieka / Nadzór",
  W8: "Pamięć systemu",
  W9: "Umiejętności systemu",
  W10: "Przyjęcie projektu",
  W11: "Rada modeli",
  W12: "Źródło Prawdy / Księga",
  W13: "Advisor / Masterplan / Koordynacja",
  W14: "Bramki jakości / Testy / Weryfikacja",
  W15: "Ontologia / Kontrakty / Model domenowy",
  W16: "Workery / Artefakty / Budowa",
  W17: "Integracje / Akcje zewnętrzne / Finansowanie / Urządzenia",
  W18: "Konsola operatora / Terminal W18",
  W19: "Audyt / Zamknięcie / Uczenie systemu",
};

const BADGE_LABELS: Record<string, string> = {
  direction_gate: "bramka kierunku",
  source_of_truth_gate: "bramka Źródła Prawdy",
  masterplan_gate: "bramka Masterplanu",
  model_council_gate: "bramka Rady modeli",
  cost_gate: "bramka kosztowa",
  runtime_gate: "bramka środowiska",
  production_gate: "bramka produkcyjna",
  external_action_gate: "bramka akcji zewnętrznej",
  final_gate: "bramka finalna",
  workspace_path_gate: "bramka ścieżki workspace",
  database_init_gate: "bramka bazy danych",
  audit_chain_init_gate: "bramka ścieżki audytu",
  minimum_model_gate: "bramka minimum jednego modelu",
  recovery_seed_gate: "bramka odzyskiwania",
  paid_provider_gate: "bramka płatnego providera",
  expensive_model_gate: "bramka drogiego modelu",
  external_model_data_gate: "bramka danych do modelu zewnętrznego",
  governance_model_change_gate: "bramka zmiany modelu nadzoru",
  vps_gate: "bramka VPS",
  paid_infrastructure_gate: "bramka płatnej infrastruktury",
  browser_external_gate: "bramka przeglądarki zewnętrznej",
  device_action_gate: "bramka urządzenia",
  cross_project_memory_gate: "bramka pamięci międzyprojektówej",
  memory_export_gate: "bramka eksportu pamięci",
  lessons_promotion_gate: "bramka promowania wniosków",
};

const LAYER_ACTIONS: Record<string, LayerAction[]> = {
  W1: [
    { label: "Polityki systemu", href: "/policy", description: "Reguły konstytucyjne i ograniczenia systemowe.", icon: ShieldCheck, primary: true },
    { label: "Human Gate", href: "/human-gate", description: "Kolejka decyzji człowieka i zatwierdzenia krytyczne.", icon: Users },
  ],
  W2: [
    { label: "Onboarding", href: "/onboarding", description: "Pierwsze uruchomienie, workspace i minimalna konfiguracja.", icon: Settings2, primary: true },
    { label: "Workspace", href: "/workspace", description: "Lokalny obszar pracy i stan katalogów projektu.", icon: Boxes },
    { label: "Zdrowie systemu", href: "/health", description: "Diagnostyka backendu, frontendu i runtime.", icon: Activity },
  ],
  W3: [
    { label: "Profil operatora", href: "/settings/profile", description: "Tożsamość, język i odpowiedzialność operatora.", icon: Users, primary: true },
    { label: "Katalog ról", href: "/role-catalog", description: "Role systemowe i uprawnienia w dashboardzie.", icon: ShieldCheck },
  ],
  W4: [
    { label: "Dodaj klucz API providera", href: "/ai-models", description: "Wpisz klucz OpenAI, Claude, Gemini, Kimi, OpenRouter albo innego dostawcy.", icon: KeyRound, primary: true },
    { label: "Katalog modeli", href: "/ai-models", description: "Aktywuj modele, sprawdź dostępność i wykonaj test połączenia.", icon: Zap },
    { label: "Routing LLM", href: "/orchestration/llm-routing", description: "Ustaw fallback chain, role modeli i priorytety providerów.", icon: Route },
    { label: "Budżety modeli", href: "/budget", description: "Limity kosztów, progi ostrzeżeń i twarde blokady.", icon: Wallet },
    { label: "Sekrety providerów", href: "/secrets", description: "Vault sekretów i rotacja kluczy API.", icon: KeyRound },
  ],
  W5: [
    { label: "Środowiska", href: "/environments", description: "Runtime lokalny, kontenery, VPS i limity środowisk.", icon: Boxes, primary: true },
    { label: "Teatr środowisk", href: "/environments/theater", description: "Live-topologia hosta, portów, providerów, środowisk, sieci i kosztów.", icon: Network },
    { label: "Start wykonania", href: "/execution-start", description: "Przygotowanie wykonania i faz runtime.", icon: Zap },
    { label: "Wdrożenia", href: "/deploy", description: "Ścieżka deploy, health i rollback.", icon: ArrowUpRight },
  ],
  W6: [
    { label: "Defaulty workspace", href: "/workspace-defaults", description: "Domyślne budżety, autonomia i profile projektu.", icon: Settings2, primary: true },
    { label: "Polityki", href: "/policy", description: "Systemowe ograniczenia zachowania AEIS.", icon: ShieldCheck },
  ],
  W7: [
    { label: "Human Gate", href: "/human-gate", description: "Decyzje i blokady wymagające człowieka.", icon: Users, primary: true },
    { label: "Cost Guard", href: "/cost-guard", description: "Kontrola kosztów i twarde limity.", icon: Wallet },
    { label: "Security Guard", href: "/security-guard", description: "Ochrona sekretów i bezpieczeństwo akcji.", icon: ShieldCheck },
    { label: "Quality Guard", href: "/quality-guard", description: "Blokady jakościowe i wyniki testów.", icon: CheckCircle2 },
  ],
  W8: [
    { label: "Pamięć", href: "/memory", description: "Wyszukiwanie i zapis doświadczeń projektu.", icon: Database, primary: true },
    { label: "Projekty", href: "/projects", description: "Kontekst i historia projektów.", icon: Boxes },
  ],
  W9: [
    { label: "Skills", href: "/skills", description: "Rejestr, lifecycle i uruchamianie skills.", icon: Wrench, primary: true },
    { label: "Szablony", href: "/templates-setup", description: "Szablony operacyjne i konfiguracja procedur.", icon: Settings2 },
  ],
  W10: [
    { label: "Start projektu", href: "/project-start", description: "Intake, pytania i klasyfikacja projektu.", icon: Search, primary: true },
    { label: "Skarbiec pomysłów", href: "/idea-vault", description: "Pomysły i załączniki przed projektem.", icon: BookOpen },
  ],
  W11: [
    { label: "Rada i Księga", href: "/council-to-ksiega", description: "Fazy 20-25, role Rady i werdykty.", icon: Users, primary: true },
    { label: "Reguły Rady", href: "/orchestration/council-rules", description: "Kworum, wagi rang, krytyk i wartownicy.", icon: Settings2 },
    { label: "Teatr modeli i agentów", href: "/test-center/theater", description: "Live-topologia modeli, ról, rozmów i zadań Rady.", icon: Network },
    { label: "Rozmowy modeli", href: "/orchestration/conversations", description: "Dyskusje agent-agent i arbitraż.", icon: GitBranch },
  ],
  W12: [
    { label: "Rada i Księga", href: "/council-to-ksiega", description: "Generowanie Księgi i finalna blokada prawdy.", icon: BookOpen, primary: true },
    { label: "Projekty", href: "/projects", description: "Artefakty i prawda projektu.", icon: Boxes },
  ],
  W13: [
    { label: "Advisor", href: "/advisor", description: "Rekomendacje, ostrzeżenia i karty doradcze dla operatora.", icon: Activity, primary: true },
    { label: "Kokpit Advisora", href: "/advisor/cockpit", description: "Topologia agentów, lifecycle, rekomendacje i bieżące decyzję.", icon: Users },
    { label: "Ustawienia Advisora", href: "/settings/advisor", description: "Preferencje, providerzy, budżety oraz zaufani i blokowani dostawcy.", icon: Settings2 },
    { label: "Planowanie", href: "/planning", description: "Masterplan i podział na moduły.", icon: GitBranch },
    { label: "Dispatch agentów", href: "/orchestration/dispatch", description: "Rozdział pracy i alokacje agentów.", icon: Route },
  ],
  W14: [
    { label: "Centrum testów", href: "/test-center", description: "Testy systemu i produktów symulacji.", icon: CheckCircle2, primary: true },
    { label: "Teatr modeli i agentów", href: "/test-center/theater", description: "Topologia modeli, agentów, zadań, rozmów i runtime W14.", icon: Users },
  ],
  W15: [
    { label: "Ontologia", href: "/ontology", description: "Typy domenowe, relacje i kontrakty.", icon: Database, primary: true },
    { label: "Katalog ról", href: "/role-catalog", description: "Role, odpowiedzialności i klasyfikacje.", icon: Users },
  ],
  W16: [
    { label: "Workery", href: "/workers", description: "Flota wykonawcza i przypisania zadań.", icon: Boxes, primary: true },
    { label: "Agenci", href: "/agents", description: "Rejestr agentów runtime i konfiguracja modeli.", icon: Users },
  ],
  W17: [
    { label: "Funding", href: "/funding", description: "Granty, finansowanie i zewnętrzne akcje formalne.", icon: Wallet, primary: true },
    { label: "Wdrożenia", href: "/deploy", description: "Deploy i akcje infrastrukturalne.", icon: ArrowUpRight },
    { label: "Federacja", href: "/federation", description: "Połączenia z nodami i środowiskami.", icon: Route },
  ],
  W18: [
    { label: "Terminal", href: "/terminal", description: "Sterowanie AEIS z jednego miejsca.", icon: Terminal, primary: true },
    { label: "Monitor operatora", href: "/dashboard/operator-monitor", description: "Status runtime, guardów i blokad.", icon: Activity },
  ],
  W19: [
    { label: "Audyt", href: "/audit", description: "Ścieżka audytu, zdarze?ia i dowody.", icon: ShieldCheck, primary: true },
    { label: "Pamięć", href: "/memory", description: "Snapshoty końcowe i uczenie systemu.", icon: Database },
  ],
};

function plText(value?: unknown): string {
  let text = String(value ?? "");
  const replacements: Array<[RegExp, string]> = [
    [/\bSource of Truth\b/g, "Źródło Prawdy"],
    [/\bHuman Gates\b/g, "bramki człowieka"],
    [/\bHuman Gate\b/g, "bramka człowieka"],
    [/\bHumanGate\b/g, "bramka człowieka"],
    [/\bQuality Gates\b/g, "bramki jakości"],
    [/\bDeployment Plane\b/g, "płaszczyzna wdrożenia"],
    [/\bOperator Terminal Plane\b/g, "płaszczyzna terminala operatora"],
    [/\bOperational Apps Builder Plane\b/g, "płaszczyzna budowy aplikacji operacyjnych"],
    [/\bProvider Catalog\b/g, "katalog providerów"],
    [/\bRuntime\b/g, "środowisko wykonania"],
    [/\bruntime\b/g, "środowisko wykonania"],
    [/\bGovernance\b/g, "nadzór"],
    [/\bgovernance\b/g, "nadzór"],
    [/\bDeploy\b/g, "wdrożenie"],
    [/\bdeploy\b/g, "wdrożenie"],
    [/\bExecution\b/g, "wykonanie"],
    [/\bexecution\b/g, "wykonanie"],
    [/\bOntology\b/g, "ontologia"],
    [/\bHumanGateTicket\b/g, "Bilet bramki człowieka"],
    [/\bCouncilSession\b/g, "Sesja Rady"],
    [/\bSoTEntry\b/g, "Wpis Źródła Prawdy"],
    [/\bProject\b/g, "Projekt"],
    [/\bWorkery\b/g, "Workery"],
    [/\bfunding\/mobile\/lab\b/g, "finansowanie / mobile / laboratorium"],
    [/\bbrowser automation\b/g, "automatyzacja przeglądarki"],
    [/\blocal-only\b/g, "tylko lokalnie"],
    [/\blocal-first\b/g, "lokalnie najpierw"],
    [/\bstaging\b/g, "środowisko testówe"],
    [/\bproduction\b/g, "produkcja"],
    [/\bexternal actions\b/g, "akcje zewnętrzne"],
    [/\bExternal actions\b/g, "akcje zewnętrzne"],
    [/\bexternal submit\b/g, "zewnętrzna wysyłka"],
    [/\bfinal closure\b/g, "finalne zamknięcie"],
    [/\bfinal package\b/g, "pakiet finalny"],
    [/\bmemory snapshot\b/g, "zapis pamięci"],
    [/\blessons learned\b/g, "wnioski końcowe"],
    [/\bskills\b/g, "umiejętności"],
    [/\bSkills\b/g, "umiejętności"],
    [/\bAudit trail\b/g, "ścieżka audytu"],
    [/\baudit trail\b/g, "ścieżka audytu"],
    [/\bapproval\b/g, "zgoda"],
    [/\bapprovals\b/g, "zgody"],
    [/\bworkspace\b/g, "obszar pracy"],
    [/\bWorkspace\b/g, "obszar pracy"],
    [/\bintake\b/g, "przyjęcie"],
    [/\bIntake\b/g, "przyjęcie"],
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

function layerTechnicalLabel(layer: Layer): string {
  return LAYER_TECHNICAL_LABELS[layer.id] ?? plText(layer.canonical_name);
}

function badgeLabel(value: string): string {
  return BADGE_LABELS[value] ?? plText(value.replaceAll("_", " "));
}

function MiniMetric({ label, value, help }: { label: string; value: string | number; help: string }) {
  return (
    <Card className="border-sylion-border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase text-muted-foreground">{label}</span>
        <HelpTip text={help} side="bottom" />
      </div>
      <div className="mt-3 text-2xl font-semibold">{value}</div>
    </Card>
  );
}

const QUICK_RUNTIME_ACTIONS: Array<LayerAction & { layerId: string }> = [
  {
    layerId: "W4",
    label: "Modele i providerzy",
    href: "/ai-models",
    description: "Dodawanie providerów, modeli, test połączenia i wybór modeli do ról.",
    icon: KeyRound,
    primary: true,
  },
  {
    layerId: "W4",
    label: "Sekrety modeli",
    href: "/secrets",
    description: "Vault kluczy API oraz aliasy ChatGPT, Claude, Gemini, Kimi, OpenRouter, Perplexity i Z.AI.",
    icon: KeyRound,
  },
  {
    layerId: "W4",
    label: "Routing LLM",
    href: "/orchestration/llm-routing",
    description: "Fallback chain, priorytety, budżety i przypisania modeli do ról.",
    icon: Route,
  },
  {
    layerId: "W5",
    label: "Teatr środowisk",
    href: "/environments/theater",
    description: "Widok hosta, portów, środowisk, providerów, sieci i kosztów runtime.",
    icon: Network,
    primary: true,
  },
  {
    layerId: "W11",
    label: "Reguły Rady",
    href: "/orchestration/council-rules",
    description: "Kworum, role, wagi głosów, krytyk, compliance i kosztowy wartownik.",
    icon: Settings2,
  },
  {
    layerId: "W14",
    label: "Teatr modeli",
    href: "/test-center/theater",
    description: "Topologia modeli, agentów, rozmów, zadań i testów systemowych.",
    icon: Users,
    primary: true,
  },
  {
    layerId: "W16",
    label: "Agenci runtime",
    href: "/agents",
    description: "Rejestracja agentów, konfiguracja modeli, autonomia i test dymny.",
    icon: Users,
  },
  {
    layerId: "W18",
    label: "Terminal operatora",
    href: "/terminal",
    description: "Jedno miejsce sterowania, log czynności, rady, agentów i środowisk.",
    icon: Terminal,
  },
];

function QuickRuntimeActions({ onSelectLayer }: { onSelectLayer: (layerId: string) => void }) {
  return (
    <Card className="border-primary/25 bg-primary/5 p-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Settings2 className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Szybka konfiguracja i teatry runtime</h2>
            <HelpTip text="Te wejścia prowadzą bezpośrednio do paneli, których operator potrzebuje przy konfiguracji AEIS i obserwacji wykonania projektu." side="bottom" />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Warstwy W4, W5, W11, W14, W16 i W18 mają tu widoczne skróty do ustawień, teatrów, agentów i terminala.
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {QUICK_RUNTIME_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <div
              key={`${action.layerId}-${action.href}`}
              className={cn(
                "rounded-lg border p-3",
                action.primary ? "border-primary/45 bg-primary/10" : "border-sylion-border bg-background",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <button
                  type="button"
                  onClick={() => onSelectLayer(action.layerId)}
                  className="rounded border border-sylion-border bg-card px-2 py-1 text-xs font-semibold text-primary hover:border-primary/60"
                >
                  {action.layerId}
                </button>
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <Link href={action.href} className="mt-3 block text-sm font-semibold hover:text-primary">
                {action.label}
              </Link>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{action.description}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function ListBlock({ title, values }: { title: string; values: string[] }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase text-muted-foreground">{title}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.map((value) => (
          <Badge key={value} variant="secondary" className="max-w-full whitespace-normal text-left">
            {badgeLabel(value)}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function LayerOperations({ layer }: { layer: Layer }) {
  const actions = LAYER_ACTIONS[layer.id] ?? safeList(layer.surfaces).map((surface) => ({
    label: plText(surface.label),
    href: surface.href,
    description: "Otwórz powiązany panel dashboardu.",
    icon: ArrowUpRight,
  }));
  const primaryActions = actions.filter((action) => action.primary);
  const secondaryActions = actions.filter((action) => !action.primary);

  return (
    <div className="mt-5 rounded-lg border border-primary/25 bg-primary/5 p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-xs font-medium uppercase text-primary">Konfiguracja i operacje warstwy</div>
          <div className="mt-1 text-xs text-muted-foreground">
            Te przyciski prowadzą do realnych ustawień, reguł, runtime albo diagnostyki wybranej warstwy.
          </div>
        </div>
        <Badge variant="outline" className="h-5 text-[9px]">{layer.id}</Badge>
      </div>
      <div className="mt-3 grid gap-2">
        {[...primaryActions, ...secondaryActions].map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={`${layer.id}-${action.href}-${action.label}`}
              href={action.href}
              className={cn(
                "flex items-start gap-3 rounded-md border px-3 py-2 text-left transition hover:border-primary/50 hover:text-primary",
                action.primary ? "border-primary/40 bg-primary/10" : "border-sylion-border bg-background",
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span className="min-w-0">
                <span className="block text-xs font-semibold">{action.label}</span>
                <span className="mt-0.5 block text-[10px] leading-4 text-muted-foreground">{action.description}</span>
              </span>
              <ArrowUpRight className="ml-auto mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function ArchitectureLayersDashboard() {
  const [data, setData] = useState<ArchitectureData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState("all");
  const [selectedId, setSelectedId] = useState("W1");
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getArchitectureLayers();
      setData(response);
      if (!response.layers?.some((layer: Layer) => layer.id === selectedId)) {
        setSelectedId("W1");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się pobrać mapy warstw.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const layers = useMemo(() => data?.layers ?? [], [data?.layers]);
  const selected = layers.find((layer) => layer.id === selectedId) ?? layers[0];

  const filteredLayers = useMemo(() => {
    const q = query.trim().toLowerCase();
    return layers.filter((layer) => {
      const groupMatch = groupFilter === "all" || layer.group === groupFilter;
      const queryMatch =
        !q ||
        layer.id.toLowerCase().includes(q) ||
        layer.polish_name.toLowerCase().includes(q) ||
        layer.canonical_name.toLowerCase().includes(q) ||
        layer.summary.toLowerCase().includes(q);
      return groupMatch && queryMatch;
    });
  }, [groupFilter, layers, query]);

  const w18Layer = layers.find((layer) => layer.id === "W18");
  const totalGates = layers.reduce((sum, layer) => sum + layer.coverage.human_gate_count, 0);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-5 px-6 py-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Layers className="h-6 w-6 text-primary" />
              <h1 className="text-2xl font-semibold tracking-normal">Warstwy architektury AEIS W1-W19</h1>
              <HelpTip text="To jest kanoniczna mapa architektury. Fazy 1-41 są przebiegiem pracy, a W1-W19 pokazują subsystemy działające pod dashboardem." side="bottom" />
            </div>
            <p className="mt-2 max-w-5xl text-sm text-muted-foreground">{plText(data?.summary?.short_definition ?? "Ładowanie kanonu warstw...")}</p>
          </div>
          <Button variant="outline" onClick={load} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Odśwież
          </Button>
        </div>

        {error && (
          <Card className="border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </Card>
        )}

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MiniMetric label="Warstwy" value={data?.summary?.layer_count ?? 19} help="Liczba kanonicznych warstw architektury AEIS." />
          <MiniMetric label="Fazy operacyjne" value={data?.summary?.phase_count ?? 41} help="Fazy opisują kolejność pracy operatora, nie strukturę systemu." />
          <MiniMetric label="Bramki człowieka" value={totalGates || "—"} help="Suma typów bramek przypisanych do warstw W1-W19." />
          <MiniMetric label="W18" value={w18Layer ? "1-41" : "—"} help="W18 to stały terminal i cockpit operatora dostępny przez cały projekt." />
        </div>

        <QuickRuntimeActions onSelectLayer={setSelectedId} />

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_430px]">
          <div className="flex flex-col gap-5">
            <Card className="border-sylion-border bg-card p-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setGroupFilter("all")}
                    className={cn(
                      "rounded-md border px-3 py-2 text-sm transition",
                      groupFilter === "all" ? "border-primary bg-primary/10 text-primary" : "border-sylion-border bg-background text-muted-foreground hover:border-primary/50",
                    )}
                  >
                    Wszystkie
                  </button>
                  {safeList(data?.groups).map((group) => (
                    <button
                      key={group.id}
                      type="button"
                      onClick={() => setGroupFilter(group.id)}
                      className={cn(
                        "rounded-md border px-3 py-2 text-sm transition",
                        groupFilter === group.id ? "border-primary bg-primary/10 text-primary" : "border-sylion-border bg-background text-muted-foreground hover:border-primary/50",
                      )}
                      title={plText(group.summary)}
                    >
                      {group.range}
                    </button>
                  ))}
                </div>
                <label className="flex min-w-0 items-center gap-2 rounded-md border border-sylion-border bg-background px-3 py-2">
                  <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Szukaj W, nazwy lub zasady"
                    className="min-w-0 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                  />
                </label>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                {filteredLayers.map((layer) => {
                  const Icon = layerIcon(layer);
                  const active = selected?.id === layer.id;
                  return (
                    <button
                      key={layer.id}
                      type="button"
                      onClick={() => setSelectedId(layer.id)}
                      className={cn(
                        "min-h-44 rounded-lg border p-4 text-left transition",
                        active ? "border-primary bg-primary/10" : "border-sylion-border bg-background hover:border-primary/50",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className="flex h-9 w-9 items-center justify-center rounded-md border border-sylion-border bg-card">
                            <Icon className="h-5 w-5 text-primary" />
                          </span>
                          <div>
                            <div className="text-sm font-semibold">{layer.id}</div>
                            <div className="text-xs text-muted-foreground">{layer.phase_span}</div>
                          </div>
                        </div>
                        <Badge className={cn("border", groupTone(layer.group))}>{plText(layer.group_label).split(" ")[0]}</Badge>
                      </div>
                      <div className="mt-3 text-sm font-semibold">{plText(layer.polish_name)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{layerTechnicalLabel(layer)}</div>
                      <p className="mt-3 line-clamp-3 text-xs leading-5 text-muted-foreground">{plText(layer.summary)}</p>
                    </button>
                  );
                })}
                {!filteredLayers.length && (
                  <div className="rounded-lg border border-sylion-border bg-background p-4 text-sm text-muted-foreground md:col-span-2 2xl:col-span-3">
                    Brak warstw dla aktualnego filtra. Wyczyść szukanie albo pokaż wszystkie grupy.
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" onClick={() => setGroupFilter("all")}>Pokaż wszystkie grupy</Button>
                      <Button variant="outline" size="sm" onClick={() => setQuery("")}>Wyczyść szukanie</Button>
                    </div>
                  </div>
                )}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <Terminal className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Przepływ przykładowego projektu</h2>
                <HelpTip text="To jest operatorski przykład nałożenia warstw na projekt typu Sylion Talior. Kolejność nie musi odpowiadać numerom warstw." side="bottom" />
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-2">
                {safeList(data?.talior_flow).map((item) => (
                  <button
                    key={`${item.layer}-${item.text}`}
                    type="button"
                    onClick={() => setSelectedId(item.layer)}
                    className="flex gap-3 rounded-md border border-sylion-border bg-background p-3 text-left text-sm hover:border-primary/50"
                  >
                    <Badge variant={item.layer === selected?.id ? "default" : "secondary"}>{item.layer}</Badge>
                    <span className="text-muted-foreground">{plText(item.text)}</span>
                  </button>
                ))}
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Pełny model roboczy AEIS</h2>
                <HelpTip text="To jest kanoniczny obraz systemu do późniejszej weryfikacji względem kodu, środowiska wykonania, API, UI, testów i dokumentacji." side="bottom" />
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">{plText(data?.working_model?.definition)}</p>
              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <div>
                  <div className="text-xs font-medium uppercase text-muted-foreground">Zasady nadrzędne</div>
                  <div className="mt-2 space-y-2">
                    {safeList(data?.working_model?.principles).slice(0, 6).map((item) => (
                      <div key={item.id} className="rounded-md border border-sylion-border bg-background p-3">
                        <div className="text-sm font-semibold">{plText(item.label)}</div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">{plText(item.description)}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase text-muted-foreground">Domyślne polityki</div>
                  <div className="mt-2 space-y-2">
                    {safeList(data?.working_model?.default_policies).map((item) => (
                      <div key={item.id} className="flex items-start justify-between gap-3 rounded-md border border-sylion-border bg-background p-3 text-sm">
                        <span className="font-medium">{plText(item.label)}</span>
                        <span className="max-w-[58%] text-right text-muted-foreground">{plText(item.value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <div>
                  <div className="text-xs font-medium uppercase text-muted-foreground">Główne byty backendu</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {safeList(data?.working_model?.entities).map((entity) => (
                      <Badge key={entity.id} variant="secondary">{plText(entity.label)}</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase text-muted-foreground">Kolejność prawdy w audycie</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {safeList(data?.working_model?.runtime_truth_order).map((item, index) => (
                      <Badge key={item} variant="secondary">{index + 1}. {plText(item)}</Badge>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Zgodność z dokumentami bazowymi</h2>
                <HelpTip text="Ta sekcja nakłada model roboczy operatora na mapę implementacyjną z 00_ARCHITEKTURA_W1_W19.md, Advisor W13 i patche faz." side="bottom" />
              </div>
              <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
                <div>
                  <div className="text-xs font-medium uppercase text-muted-foreground">Mapa implementacyjna v2</div>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    {safeList(data?.implementation_planes).map((plane) => (
                      <div key={plane.id} className="rounded-md border border-sylion-border bg-background p-3">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary">{plane.id}</Badge>
                        <div className="text-sm font-semibold">{plText(plane.label)}</div>
                        </div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">{plText(plane.description)}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Advisor W13</div>
                    <div className="mt-2 rounded-md border border-sylion-border bg-background p-3">
                      <div className="text-sm font-semibold">{plText(data?.advisor_layer?.label)}</div>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{plText(data?.advisor_layer?.summary)}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {safeList(data?.advisor_layer?.specialized_advisors).map((item) => (
                          <Badge key={item} variant="secondary">{plText(item)}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Patche faz</div>
                    <div className="mt-2 space-y-2">
                      {safeList(data?.phase_patches).map((patch) => (
                        <div key={patch.id} className="rounded-md border border-sylion-border bg-background p-3">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold">Faza {patch.phase}: {plText(patch.label)}</span>
                            <Badge variant={patch.severity === "CRITICAL" ? "destructive" : "secondary"}>{patch.severity}</Badge>
                          </div>
                          <div className="mt-1 text-xs leading-5 text-muted-foreground">{plText(patch.description)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="border-sylion-border bg-card p-4">
              <div className="flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Nakładka faz 1-41</h2>
                <HelpTip text="W18 działa stale, więc w siatce pokazuję dodatkowe warstwy dotykające danej fazy. W18 jest kontekstem dla każdej komórki." side="bottom" />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-7">
                {Object.entries(data?.phase_overlay ?? {}).map(([phase, layerIds]) => {
                  const visible = layerIds.filter((id) => id !== "W18");
                  return (
                    <div key={phase} className="min-h-24 rounded-md border border-sylion-border bg-background p-3">
                      <div className="text-xs font-semibold">Faza {phase}</div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {(visible.length ? visible : ["W18"]).slice(0, 5).map((id) => (
                          <button
                            key={id}
                            type="button"
                            onClick={() => setSelectedId(id)}
                            className={cn(
                              "rounded border px-1.5 py-0.5 text-[11px]",
                              id === selected?.id ? "border-primary bg-primary/10 text-primary" : "border-sylion-border text-muted-foreground",
                            )}
                          >
                            {id}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>

          {selected && (
            <div className="flex flex-col gap-5">
              <Card className="border-sylion-border bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = layerIcon(selected);
                        return <Icon className="h-5 w-5 text-primary" />;
                      })()}
                      <h2 className="text-lg font-semibold">{selected.id} — {plText(selected.polish_name)}</h2>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{layerTechnicalLabel(selected)}</div>
                  </div>
                  <Badge className={cn("border", groupTone(selected.group))}>{plText(selected.group_label)}</Badge>
                </div>

                <div className="mt-4 rounded-md border border-sylion-border bg-background p-3 font-mono text-xs text-primary">
                  {layerCommand(selected)}
                </div>

                <p className="mt-4 text-sm leading-6 text-muted-foreground">{plText(selected.operator_meaning)}</p>

                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-md border border-sylion-border bg-background p-3">
                    <div className="text-[11px] uppercase text-muted-foreground">Fazy</div>
                    <div className="mt-1 text-sm font-semibold">{selected.phase_span}</div>
                  </div>
                  <div className="rounded-md border border-sylion-border bg-background p-3">
                    <div className="text-[11px] uppercase text-muted-foreground">Powierzchnie</div>
                    <div className="mt-1 text-sm font-semibold">{selected.coverage.surface_count}</div>
                  </div>
                  <div className="rounded-md border border-sylion-border bg-background p-3">
                    <div className="text-[11px] uppercase text-muted-foreground">Bramki</div>
                    <div className="mt-1 text-sm font-semibold">{selected.coverage.human_gate_count}</div>
                  </div>
                </div>

                <div className="mt-4 rounded-md border border-primary/30 bg-primary/10 p-3 text-sm">
                  <div className="text-xs font-medium uppercase text-primary">Asercja środowiska wykonania</div>
                  <div className="mt-1 text-muted-foreground">{plText(selected.runtime_assertion)}</div>
                </div>

                <LayerOperations layer={selected} />

                <div className="mt-5 space-y-5">
                  <ListBlock title="Bramki człowieka" values={safeList(selected.human_gates)} />
                  <ListBlock title="Kontrole operatora" values={safeList(selected.operator_controls)} />
                  <ListBlock title="Subsystemy" values={safeList(selected.subsystems)} />
                </div>

                <div className="mt-5">
                  <div className="text-xs font-medium uppercase text-muted-foreground">Twarde zasady</div>
                  <div className="mt-2 space-y-2">
                    {safeList(selected.hard_rules).map((rule) => (
                      <div key={rule} className="rounded-md border border-sylion-border bg-background p-3 text-sm text-muted-foreground">
                        {plText(rule)}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-5">
                  <div className="text-xs font-medium uppercase text-muted-foreground">Gdzie to widać w dashboardzie</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {safeList(selected.surfaces).map((surface) => (
                      <Link
                        key={`${selected.id}-${surface.href}`}
                        href={surface.href}
                        className="rounded-md border border-sylion-border bg-background px-3 py-2 text-xs text-muted-foreground hover:border-primary/50 hover:text-primary"
                      >
                        {plText(surface.label)}
                      </Link>
                    ))}
                  </div>
                </div>

                <div className="mt-5">
                  <div className="text-xs font-medium uppercase text-muted-foreground">Fazy dotykane przez warstwę</div>
                  <div className="mt-2 text-sm text-muted-foreground">{formatPhaseList(selected.phase_touchpoints)}</div>
                </div>
              </Card>

              <Card className="border-sylion-border bg-card p-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold">Reguły nakładania</h2>
                  <HelpTip text="Te reguły opisują, jak warstwy mają się pilnować nawzajem w realnym przepływie projektu." side="left" />
                </div>
                <div className="mt-4 space-y-3">
                  {safeList(data?.overlay_rules).map((rule) => (
                    <div key={rule.id} className="rounded-md border border-sylion-border bg-background p-3">
                      <div className="text-sm font-semibold">{plText(rule.label)}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{plText(rule.rule)}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
