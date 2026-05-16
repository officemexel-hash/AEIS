"""Canonical AEIS architecture layer map W1-W19."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/architecture-layers", tags=["Architecture Layers"])


GROUPS: list[dict[str, str]] = [
    {
        "id": "foundation",
        "label": "Fundament systemu W1-W9",
        "range": "W1-W9",
        "summary": "Kanon, instalacja, operator, modele, runtime, autonomia, governance, pamięć i skills.",
    },
    {
        "id": "project_truth_plan",
        "label": "Projekt, prawda i plan W10-W13",
        "range": "W10-W13",
        "summary": "Intake projektu, Rada modeli, Księga jako Source of Truth i Masterplan.",
    },
    {
        "id": "execution_external",
        "label": "Jakość, wykonanie i świat zewnętrzny W14-W17",
        "range": "W14-W17",
        "summary": "Quality Gates, Ontology, workery, artefakty, integracje i external actions.",
    },
    {
        "id": "operator_console",
        "label": "Stała powierzchnia operatora W18",
        "range": "W18",
        "summary": "Terminal i cockpit, który prowadzi operatora przez cały projekt.",
    },
    {
        "id": "audit_learning",
        "label": "Audyt, zamknięcie i uczenie W19",
        "range": "W19",
        "summary": "Audit trail, final package, memory snapshot, lessons learned i ewolucja systemu.",
    },
]


SURFACES: dict[str, dict[str, str]] = {
    "advisor": {"label": "Doradca na żywo", "href": "/advisor"},
    "advisor_cockpit": {"label": "Kokpit Advisora", "href": "/advisor/cockpit"},
    "settings_advisor": {"label": "Ustawienia Advisora", "href": "/settings/advisor"},
    "onboarding": {"label": "Pierwsze uruchomienie", "href": "/onboarding"},
    "workspace": {"label": "Obszar pracy", "href": "/workspace"},
    "health": {"label": "Zdrowie systemu", "href": "/health"},
    "settings_profile": {"label": "Profil operatora", "href": "/settings/profile"},
    "auth": {"label": "Uwierzytelnianie", "href": "/auth"},
    "roles": {"label": "Role", "href": "/roles"},
    "ai_models": {"label": "Modele AI", "href": "/ai-models"},
    "llm_routing": {"label": "Routing LLM", "href": "/orchestration/llm-routing"},
    "secrets": {"label": "Sekrety providerow", "href": "/secrets"},
    "budget": {"label": "Budżet modeli", "href": "/budget"},
    "environments": {"label": "Środowiska", "href": "/environments"},
    "environment_theater": {"label": "Teatr środowisk", "href": "/environments/theater"},
    "federation": {"label": "Federacja", "href": "/federation"},
    "workspace_defaults": {"label": "Domyślny obszar pracy", "href": "/workspace-defaults"},
    "autonomy": {"label": "Autonomia", "href": "/autonomy"},
    "policy": {"label": "Polityki systemu", "href": "/policy"},
    "human_gate": {"label": "Bramka człowieka", "href": "/human-gate"},
    "gates": {"label": "Bramki zarządzania", "href": "/gates"},
    "coherence_guard": {"label": "Strażnik spójności", "href": "/coherence-guard"},
    "cost_guard": {"label": "Strażnik kosztów", "href": "/cost-guard"},
    "security_guard": {"label": "Strażnik bezpieczeństwa", "href": "/security-guard"},
    "quality_guard": {"label": "Strażnik jakości", "href": "/quality-guard"},
    "provenance_guard": {"label": "Strażnik pochodzenia", "href": "/provenance-guard"},
    "memory": {"label": "Pamięć", "href": "/memory"},
    "skills": {"label": "Umiejętności", "href": "/skills"},
    "templates": {"label": "Szablony", "href": "/templates-setup"},
    "project_start": {"label": "Start projektu", "href": "/project-start"},
    "idea_vault": {"label": "Skarbiec pomysłów", "href": "/idea-vault"},
    "projects": {"label": "Projekty", "href": "/projects"},
    "council": {"label": "Deliberacja i Księga", "href": "/council-to-ksiega"},
    "model_council": {"label": "Rada modeli", "href": "/model-council"},
    "book": {"label": "Księga", "href": "/book"},
    "source_of_truth": {"label": "Source of Truth", "href": "/source-of-truth"},
    "planning": {"label": "Planowanie", "href": "/planning"},
    "masterplan": {"label": "Masterplan", "href": "/masterplan"},
    "test_center": {"label": "Centrum testów", "href": "/test-center"},
    "test_theater": {"label": "Teatr modeli i agentów", "href": "/test-center/theater"},
    "ontology": {"label": "Ontologia", "href": "/ontology"},
    "contracts": {"label": "Kontrakty", "href": "/contracts"},
    "execution": {"label": "Start wykonania", "href": "/execution-start"},
    "workers": {"label": "Workery", "href": "/workers"},
    "build_state": {"label": "Stan budowy", "href": "/build-state"},
    "integrations": {"label": "Integracje", "href": "/integrations"},
    "funding": {"label": "Granty i finansowanie", "href": "/funding"},
    "operator_mobile": {"label": "Operator Mobile", "href": "/operator-mobile"},
    "devices": {"label": "Urządzenia", "href": "/devices"},
    "sdr": {"label": "Laboratorium SDR", "href": "/sdr"},
    "cellular": {"label": "Laboratorium sieci komórkowej", "href": "/cellular"},
    "deploy": {"label": "Wdrożenia", "href": "/deploy"},
    "terminal": {"label": "Terminal W18", "href": "/terminal"},
    "audit": {"label": "Ścieżka audytu", "href": "/audit"},
}


def _s(*keys: str) -> list[dict[str, str]]:
    return [SURFACES[key] for key in keys]


LAYERS: list[dict[str, Any]] = [
    {
        "id": "W1",
        "number": 1,
        "canonical_name": "Canon / System Constitution",
        "polish_name": "Kanon i konstytucja systemu",
        "group": "foundation",
        "summary": "Najgłębsza warstwa zasad: czym AEIS jest, czego nie wolno mu robić i kiedy człowiek musi zatwierdzić decyzję.",
        "operator_meaning": "Modele mogą proponować, analizować i tworzyć kandydatów, ale operator zatwierdza kierunek, Source of Truth, produkcję, external actions, koszty i final closure.",
        "phase_touchpoints": [1, 5, 7, 12, 13, 20, 25, 28, 39, 40, 41],
        "surfaces": _s("book", "policy", "human_gate", "gates"),
        "subsystems": ["system canon", "decision constitution", "source-of-truth rules", "production rules", "external-action rules", "audit obligation"],
        "operator_controls": ["tryb systemu", "twardość polityk", "governance veto", "autonomia sandboxu", "blokada produkcji bez zgody"],
        "human_gates": ["direction_gate", "source_of_truth_gate", "masterplan_gate", "cost_gate", "production_gate", "external_action_gate", "final_gate"],
        "hard_rules": [
            "Najpierw prawda, potem plan, potem wykonanie.",
            "Modele proponują; operator zatwierdza prawdę, produkcję, external submit, działania prawne, działania finansowe i finalne zamknięcie.",
            "Każda strategiczna zmiana musi mieć audit trail.",
        ],
        "runtime_assertion": "Canon mówi: modele proponują, operator zatwierdza.",
    },
    {
        "id": "W2",
        "number": 2,
        "canonical_name": "Bootstrap / Installation / Workspace",
        "polish_name": "Bootstrap, instalacja i workspace",
        "group": "foundation",
        "summary": "Warstwa pierwszego uruchomienia, lokalnej aplikacji, backendu, frontendu, SQLite, ścieżek danych, backupów i diagnostyki.",
        "operator_meaning": "AEIS działa lokalnie na maszynie operatora i ma gotowy workspace do przechowywania projektów, audytu, sekretów, pamięci oraz skills.",
        "phase_touchpoints": [1],
        "surfaces": _s("onboarding", "workspace", "health"),
        "subsystems": ["Tauri shell", "FastAPI backend", "Next.js frontend", "SQLite database", "workspace path", "backup path", "system check"],
        "operator_controls": ["ścieżka workspace", "strategia backupów", "retencja backupów", "custom path", "kontynuacja po ostrzeżeniach"],
        "human_gates": ["workspace_path_gate", "database_init_gate", "audit_chain_init_gate", "minimum_model_gate", "recovery_seed_gate"],
        "hard_rules": [
            "Workspace musi być zapisywalny.",
            "Baza i audit chain muszą zostać zainicjowane przed pracą projektową.",
            "Minimum jeden model albo demo mode jest wymagane do ukończenia wejścia do systemu.",
        ],
        "runtime_assertion": "Workspace działa lokalnie.",
    },
    {
        "id": "W3",
        "number": 3,
        "canonical_name": "Operator Identity / Permissions / Operator Profile",
        "polish_name": "Tożsamość, uprawnienia i profil operatora",
        "group": "foundation",
        "summary": "Tożsamość operatora, rola, język, strefa czasu, uprawnienia, final approvals, mobile approvals i ślad odpowiedzialności.",
        "operator_meaning": "Każda decyzja w Human Gate, audit chain, raporcie i final approval musi mieć konkretnego operatora lub delegata.",
        "phase_touchpoints": [1, 5, 7, 39, 40, 41],
        "surfaces": _s("settings_profile", "auth", "roles", "human_gate"),
        "subsystems": ["operator profile", "RBAC", "session identity", "trusted device status", "secure token policy", "approval authority"],
        "operator_controls": ["display name", "email", "rola", "język", "timezone", "uprawnienia do kosztów", "uprawnienia do produkcji"],
        "human_gates": ["re_auth_gate", "production_approval_gate", "external_submit_approval_gate", "delegate_gate"],
        "hard_rules": [
            "Final approval nie może być anonimowy.",
            "Produkcję i external submit zatwierdza właściciel albo jawnie delegowana rola.",
            "Decyzje krytyczne mogą wymagać ponownego hasła lub secure token.",
        ],
        "runtime_assertion": "Operator Ylion ma uprawnienia właściciela.",
    },
    {
        "id": "W4",
        "number": 4,
        "canonical_name": "Provider & Model Catalog",
        "polish_name": "Katalog providerów i modeli",
        "group": "foundation",
        "summary": "Lista modeli lokalnych i API wraz z kosztami, limitami, specjalizacją, rolami, dostępem do narzędzi i fallback chains.",
        "operator_meaning": "Operator widzi, które modele są dostępne lokalnie lub przez API oraz do jakich ról mogą być użyte.",
        "phase_touchpoints": [2, 20, 26],
        "surfaces": _s("ai_models", "llm_routing", "budget", "secrets"),
        "subsystems": ["provider catalog", "model registry", "local model scan", "API keys", "fallback chains", "council model roles"],
        "operator_controls": ["klucze API", "modele aktywne", "modele wyłączone", "fallback chains", "limity kosztowe", "modele review-only"],
        "human_gates": ["paid_provider_gate", "expensive_model_gate", "external_model_data_gate", "governance_model_change_gate"],
        "hard_rules": [
            "Model bez aktywnego providera nie jest dostępny.",
            "Użycie drogiego modelu ponad próg wymaga zgody.",
            "Wysyłka danych wrażliwego projektu do API wymaga polityki i Human Gate.",
        ],
        "runtime_assertion": "Dostępne są modele lokalne i/lub API.",
    },
    {
        "id": "W5",
        "number": 5,
        "canonical_name": "Runtime / Environment / Infrastructure",
        "polish_name": "Runtime, środowisko i infrastruktura",
        "group": "foundation",
        "summary": "Warstwa trybów local-only, local-first, containers, VPS, cloud, browser automation, staging, production i rollback.",
        "operator_meaning": "AEIS wie, gdzie działa system i gdzie wolno wykonywać pracę projektu.",
        "phase_touchpoints": [3, 32, 39, 40],
        "surfaces": _s("environments", "environment_theater", "federation", "execution", "deploy"),
        "subsystems": ["runtime mode", "environment theater", "containers", "VPS", "cloud providers", "workers", "staging", "production", "rollback environments"],
        "operator_controls": ["local-first", "Teatr środowisk", "kontenery", "VPS", "liczba workerów", "browser automation", "staging", "production", "auto scaling"],
        "human_gates": ["runtime_gate", "vps_gate", "production_gate", "paid_infrastructure_gate", "browser_external_gate", "device_action_gate"],
        "hard_rules": [
            "Produkcja jest zablokowana bez zatwierdzonego runtime i rollbacku.",
            "Płatna infrastruktura lub zwiększenie workerów ponad limit wymaga zgody.",
            "Browser automation na zewnętrznych stronach nie może ruszyć bez bramki.",
        ],
        "runtime_assertion": "Runtime ustawiony local-first.",
    },
    {
        "id": "W6",
        "number": 6,
        "canonical_name": "Defaults / Autonomy / System Policies",
        "polish_name": "Defaulty, autonomia i polityki systemowe",
        "group": "foundation",
        "summary": "Domyślne zachowanie AEIS: autonomia, runtime, budżet, testy, Human Gate, Rada modeli, logi i warianty A/B/C/D/E.",
        "operator_meaning": "System startuje z jasno ustawionym profilem ostrożności, kosztów i samodzielności.",
        "phase_touchpoints": [4, 5],
        "surfaces": _s("workspace_defaults", "autonomy", "policy"),
        "subsystems": ["autonomy preset", "workspace defaults", "cost policy", "production policy", "external action policy", "test defaults"],
        "operator_controls": ["poziom autonomii", "retry", "równoległość", "budżet", "testy", "mockupy", "build lokalny", "external actions"],
        "human_gates": ["cost_gate", "source_of_truth_gate", "runtime_gate", "production_gate", "external_action_gate"],
        "hard_rules": [
            "Autonomia jest risk-based, nie task-based.",
            "Production, external actions i Source of Truth pozostają za Human Gate.",
            "Przekroczenie kosztu ponad próg wymaga zatwierdzenia.",
        ],
        "runtime_assertion": "Autonomia ustawiona medium.",
    },
    {
        "id": "W7",
        "number": 7,
        "canonical_name": "Guards / Human Gate / Governance",
        "polish_name": "Guards, Human Gate i governance",
        "group": "foundation",
        "summary": "Rdzeń bezpieczeństwa decyzyjnego: blokady, findings, kolejka Human Gate, cost/security/quality/coherence/provenance/runtime/external/production guard.",
        "operator_meaning": "Human Gate blokuje tylko gałąź wymagającą decyzji człowieka, a nie całe AEIS.",
        "phase_touchpoints": [5, 6, 7, 8, 9, 10, 20, 25, 28, 39, 40],
        "surfaces": _s("human_gate", "gates", "coherence_guard", "cost_guard", "security_guard", "quality_guard", "provenance_guard"),
        "subsystems": ["Human Gate Queue", "approval policies", "blocking gates", "batch gates", "findings", "override audit", "governance escalation"],
        "operator_controls": ["progi kosztowe", "progi ryzyka", "blocking/non-blocking", "delegacja", "mobile approvals", "timeouty", "priorytety P0-P4"],
        "human_gates": ["direction_gate", "source_of_truth_gate", "masterplan_gate", "model_council_gate", "cost_gate", "runtime_gate", "production_gate", "external_action_gate"],
        "hard_rules": [
            "Critical finding blokuje chronioną gałąź.",
            "Override musi mieć autora, powód i ślad audytu.",
            "Human Gate dla kierunku, SoT, Masterplanu, kosztów i produkcji jest aktywny.",
        ],
        "runtime_assertion": "Human Gate aktywny dla kierunku, SoT, Masterplanu, kosztów i produkcji.",
    },
    {
        "id": "W8",
        "number": 8,
        "canonical_name": "Memory Layer",
        "polish_name": "Pamięć systemu",
        "group": "foundation",
        "summary": "Pamięć projektów, decyzji, SoT, masterplanów, kosztów, błędów, skuteczności modeli, skuteczności skills i preferencji operatora.",
        "operator_meaning": "AEIS nie zaczyna każdego projektu od zera, tylko szuka podobnych przypadków i ostrzega przed powtarzaniem błędów.",
        "phase_touchpoints": [16, 19, 20, 26, 41],
        "surfaces": _s("memory", "projects", "source_of_truth"),
        "subsystems": ["memory snapshots", "similarity search", "operator preferences", "model performance memory", "skill performance memory", "drift history"],
        "operator_controls": ["czy pamięć jest aktywna", "similarity search", "lokalność pamięci", "prywatność", "co zapisywać po projekcie"],
        "human_gates": ["cross_project_memory_gate", "memory_export_gate", "lessons_promotion_gate"],
        "hard_rules": [
            "Pamięć nie może ujawniać danych projektu poza dozwolonym zakresem.",
            "Promowanie wniosków do przyszłych projektów wymaga Provenance i Quality review.",
        ],
        "runtime_assertion": "Memory szuka podobnych projektów operatorskich.",
    },
    {
        "id": "W9",
        "number": 9,
        "canonical_name": "Skills Layer",
        "polish_name": "Kompetencje systemu",
        "group": "foundation",
        "summary": "Formalne procedury i kompetencje: operator_console, source_of_truth, model_council, human_gate, testing_human_like, documentation_export i inne.",
        "operator_meaning": "Skill to procedura wykonania, testowania albo dokumentacji, nie zwykły prompt.",
        "phase_touchpoints": [11, 12, 13, 14, 15, 27, 32, 41],
        "surfaces": _s("skills", "templates"),
        "subsystems": ["skills registry", "skills executor", "skill binding", "template catalog", "promotion decisions"],
        "operator_controls": ["skills wymagane", "skills opcjonalne", "skills eksperymentalne", "skills zablokowane", "tools access", "SoT write access"],
        "human_gates": ["skill_import_gate", "skill_promotion_gate", "external_tool_skill_gate"],
        "hard_rules": [
            "Skill bez manifestu, wersji i źródła nie może być promowany.",
            "Skill piszący do Księgi działa przez kandydatów, nie przez ciche nadpisanie prawdy.",
        ],
        "runtime_assertion": "Skills dobierają operator_console, source_of_truth, model_council.",
    },
    {
        "id": "W10",
        "number": 10,
        "canonical_name": "Project Intake / Project Understanding",
        "polish_name": "Intake i rozumienie projektu",
        "group": "project_truth_plan",
        "summary": "Surowa intencja operatora, pliki, brief, repo, klasyfikacja domeny, ryzyko, złożoność, braki danych i pytania.",
        "operator_meaning": "Intake przyjmuje pomysł, ale nie jest Source of Truth.",
        "phase_touchpoints": [16, 17, 18, 19],
        "surfaces": _s("project_start", "idea_vault", "projects", "advisor"),
        "subsystems": ["intake record", "domain classification", "risk pre-score", "complexity pre-score", "missing data", "clarifying questions"],
        "operator_controls": ["zatwierdź klasyfikację", "popraw klasyfikację", "dodaj domenę", "usuń domenę", "przyjmij założenia", "oznacz eksperymentalny"],
        "human_gates": ["direction_gate", "project_acceptance_gate"],
        "hard_rules": [
            "Intake nie zatwierdza prawdy.",
            "Braki danych muszą być widoczne przed Radą modeli.",
        ],
        "runtime_assertion": "Intake przyjmuje pomysł panelu AEIS.",
    },
    {
        "id": "W11",
        "number": 11,
        "canonical_name": "Model Council",
        "polish_name": "Rada modeli",
        "group": "project_truth_plan",
        "summary": "Role modeli analizują, krytykują, głosują, proponują warianty A/B/C/D/E, ryzyka i kandydatów do Księgi.",
        "operator_meaning": "Rada nie kończy się ścianą tekstu; kończy się zgodą modeli, sporami, wariantami, rekomendacją, ryzykiem i Human Gate.",
        "phase_touchpoints": [20, 21, 22, 23, 24, 25, 34],
        "surfaces": _s("council", "model_council", "test_theater", "ai_models"),
        "subsystems": ["role assignment", "weighted votes", "rounds", "red team", "governance veto", "variant generation", "verdict consolidation", "model theater"],
        "operator_controls": ["skład rady", "preset", "role", "wagi głosów", "tryb debaty", "liczba rund", "Teatr modeli", "Red Team", "governance veto"],
        "human_gates": ["model_council_gate", "direction_gate", "tie_break_gate", "governance_veto_gate"],
        "hard_rules": [
            "Rada proponuje, nie zatwierdza Source of Truth.",
            "Zmiana modelu governance lub final verifier wymaga śladu decyzji.",
        ],
        "runtime_assertion": "Rada modeli analizuje i proponuje warianty A/B/C/D/E.",
    },
    {
        "id": "W12",
        "number": 12,
        "canonical_name": "Source of Truth / Księga",
        "polish_name": "Source of Truth i Księga",
        "group": "project_truth_plan",
        "summary": "Cel, zakres, poza zakresem, założenia, hipotezy, decyzje operatora, ryzyka, constraints, Human Gates, kryteria sukcesu i wymagane artefakty.",
        "operator_meaning": "Księga jest źródłem prawdy projektu. Modele mogą proponować wpisy, ale tylko operator zatwierdza status PRAWDA.",
        "phase_touchpoints": [20, 21, 22, 23, 24, 25, 28, 36, 39],
        "surfaces": _s("book", "source_of_truth", "council"),
        "subsystems": ["SoT entries", "truth statuses", "change proposals", "conflict detection", "operator approvals", "audit links"],
        "operator_controls": ["zatwierdź jako PRAWDA", "oznacz HIPOTEZA", "edytuj", "odeślij do Rady", "odrzuć", "utwórz Change Proposal"],
        "human_gates": ["source_of_truth_gate", "change_gate", "conflict_gate"],
        "hard_rules": [
            "Source of Truth jest ważniejsze niż chwilowa dyskusja.",
            "Kod i Masterplan nie mogą przeczyć Księdze bez Change Proposal.",
        ],
        "runtime_assertion": "Księga zapisuje wybrany kierunek jako Source of Truth.",
    },
    {
        "id": "W13",
        "number": 13,
        "canonical_name": "Advisor / Masterplan / Coordination / Execution Plan",
        "polish_name": "Advisor, Masterplan, koordynacja i plan wykonania",
        "group": "project_truth_plan",
        "summary": "Advisor prowadzi operatora przez rekomendacje i ostrzeżenia, a Masterplan obejmuje moduły, zależności, kolejność, modele, zespoły agentów, skills, runtime, testy, Human Gates, rollback, koszty, terminy i ryzyka.",
        "operator_meaning": "Advisor obserwuje projekt i podpowiada decyzje; Masterplan zamienia prawdę z Księgi w realny plan wykonania.",
        "phase_touchpoints": [26, 27, 28, 29, 30, 31, 35],
        "surfaces": _s("advisor", "advisor_cockpit", "settings_advisor", "planning", "masterplan", "execution"),
        "subsystems": ["advisor cards", "advisor preferences", "recommendation engine", "module decomposition", "dependency graph", "critical path", "resource profile", "worker routing", "test plan", "rollback points"],
        "operator_controls": ["otwórz Advisora", "otwórz kokpit Advisora", "konfiguruj Advisora", "zatwierdź rekomendację", "zatwierdź plan", "zatwierdź MVP", "zmniejsz zakres", "zwiększ testy", "zmień runtime", "zmień budżet", "odeślij do Rady"],
        "human_gates": ["masterplan_gate", "budget_gate", "runtime_gate", "scope_change_gate"],
        "hard_rules": [
            "Zatwierdzenie Masterplanu jest twardym Human Gate.",
            "Plan musi wskazać zależności, testy, koszty i rollback points.",
        ],
        "runtime_assertion": "Advisor prowadzi operatora przez rekomendacje, a Masterplan dzieli projekt na moduły.",
    },
    {
        "id": "W14",
        "number": 14,
        "canonical_name": "Quality Gates / Tests / Verification",
        "polish_name": "Quality Gates, testy i weryfikacja",
        "group": "execution_external",
        "summary": "Unit, integration, E2E, browser, API contract, UI flow, operator flow, human-like, security, cost, runtime, rollback i quality verdict.",
        "operator_meaning": "Warstwa odpowiada na pytanie, czy wynik jest dobry, bezpieczny i zgodny z prawdą.",
        "phase_touchpoints": [37, 38, 39],
        "surfaces": _s("quality_guard", "test_center", "test_theater", "execution"),
        "subsystems": ["quality gates", "human-like tests", "contract tests", "agent/model theater", "release gate", "security review", "cost review", "rollback test"],
        "operator_controls": ["zaakceptuj wynik", "popraw wynik", "uruchom ponowne testy", "otwórz Teatr modeli", "zmień kryteria", "cofnij do Masterplanu", "odrzuć final approval"],
        "human_gates": ["quality_gate", "release_gate", "final_approval_gate"],
        "hard_rules": [
            "Critical test failure blokuje deploy.",
            "Human-like testy muszą pokryć przepływy operatora i klienta.",
        ],
        "runtime_assertion": "Quality Gates sprawdzają wynik.",
    },
    {
        "id": "W15",
        "number": 15,
        "canonical_name": "Ontology / Contracts / Domain Model",
        "polish_name": "Ontologia, kontrakty i model domenowy",
        "group": "execution_external",
        "summary": "Encje, relacje, statusy, eventy, API contracts, proto, schematy, modele bazy, kontrakty UI, reguły biznesowe i permissions.",
        "operator_meaning": "AEIS ustala, jakie obiekty istnieją w projekcie, jak są powiązane i które zmiany wymagają Human Gate.",
        "phase_touchpoints": [20, 25, 26, 28, 29],
        "surfaces": _s("ontology", "contracts", "source_of_truth"),
        "subsystems": ["domain entities", "relations", "workflow states", "API contracts", "schemas", "permissions model", "event taxonomy"],
        "operator_controls": ["zatwierdź model domenowy", "zmień byty", "zmień kontrakt API", "zmień statusy workflow", "zmień relacje", "oznacz dane wrażliwe"],
        "human_gates": ["ontology_gate", "contract_change_gate", "sensitive_data_gate"],
        "hard_rules": [
            "Zmiana W15 może wymagać Rady modeli, bo wpływa na cały system.",
            "Główne byty domenowe muszą mieć relacje, status i zakres odpowiedzialności.",
        ],
        "runtime_assertion": "Ontology definiuje Project, CouncilSession, HumanGateTicket, SoTEntry.",
    },
    {
        "id": "W16",
        "number": 16,
        "canonical_name": "Worker Execution / Artifacts / Build",
        "polish_name": "Wykonanie workerów, artefakty i build",
        "group": "execution_external",
        "summary": "Warstwa, w której AEIS tworzy UI, API, dokumenty, testy, formularze, dashboardy, lokalne buildy i artefakty.",
        "operator_meaning": "Workery wykonują zadania, ale zmiany prawdy, kosztów, runtime i produkcji przechodzą przez bramki.",
        "phase_touchpoints": [32, 33, 34, 35, 36],
        "surfaces": _s("execution", "workers", "build_state"),
        "subsystems": ["worker runs", "agent teams", "task queues", "build artifacts", "generated code", "generated docs", "repair loops", "module status"],
        "operator_controls": ["liczba workerów", "równoległość", "retry count", "review per moduł", "Change Proposal by worker", "auto build", "documentation update"],
        "human_gates": ["scope_change_gate", "masterplan_change_gate", "cost_gate", "runtime_gate", "external_action_gate", "architecture_change_gate"],
        "hard_rules": [
            "Worker nie może po cichu zmienić Księgi ani Masterplanu.",
            "Build produkcyjny wymaga Gate.",
        ],
        "runtime_assertion": "Workery budują UI, API, testy i dokumentację.",
    },
    {
        "id": "W17",
        "number": 17,
        "canonical_name": "Integrations / External Actions / Funding / Devices",
        "polish_name": "Integracje, external actions, funding i urządzenia",
        "group": "execution_external",
        "summary": "Zewnętrzne API, browser automation, wysyłki, uploady, płatności, granty, VPS, devices, lab, produkcja i komunikacja zewnętrzna.",
        "operator_meaning": "To warstwa największego ryzyka, więc domyślnie blokuje external actions, a funding/mobile/lab mogą być oznaczone jako future.",
        "phase_touchpoints": [3, 7, 8, 9, 39, 40],
        "surfaces": _s("integrations", "funding", "operator_mobile", "devices", "sdr", "cellular", "deploy"),
        "subsystems": ["external APIs", "browser automation", "grant submissions", "payments", "email/SMS", "mobile bridge", "device bridge", "lab extensions", "artifact deployer"],
        "operator_controls": ["external actions blocked", "browser local-only", "funding submit gate", "VPS approval", "payments sandbox", "device lab gate"],
        "human_gates": ["external_upload_gate", "external_submit_gate", "production_gate", "payment_gate", "legal_gate", "funding_gate", "device_gate", "cloud_provisioning_gate"],
        "hard_rules": [
            "External submit, płatności, działania prawne i działania finansowe wymagają silnego Gate.",
            "Produkcja i browser automation na portalu zewnętrznym nie mogą ruszyć po cichu.",
        ],
        "runtime_assertion": "External actions są zablokowane, funding/mobile/lab jako future.",
    },
    {
        "id": "W18",
        "number": 18,
        "canonical_name": "Operator Console / W18 Terminal",
        "polish_name": "Konsola operatora i terminal W18",
        "group": "operator_console",
        "summary": "Stałe centrum sterowania AEIS: terminal komend, dialog naturalny, warianty A/B/C/D/E, Human Gate prompts, status, Rada, Księga, execution, runtime, koszty i testy.",
        "operator_meaning": "Operator nie powinien szukać funkcji po rozproszonych ekranach. W18 prowadzi projekt i przyjmuje komendy jak cockpit AEIS.",
        "phase_touchpoints": list(range(1, 42)),
        "surfaces": _s("terminal", "advisor", "execution", "book", "human_gate"),
        "subsystems": ["command terminal", "slash commands", "command history", "decision cards", "SoT side panel", "council preview", "execution controls", "cost controls"],
        "operator_controls": ["komendy naturalne", "slash commands", "warianty", "Human Gate decisions", "runtime commands", "test commands", "final approval commands"],
        "human_gates": ["operator_prompt_gate", "command_confirmation_gate", "final_approval_gate"],
        "hard_rules": [
            "Kliknięcie w UI powinno generować komendę w W18.",
            "W18 ma utrzymywać ciągły kontekst Source of Truth.",
            "W18 nie zastępuje Human Gate; pokazuje go operatorowi.",
        ],
        "runtime_assertion": "Operator prowadzi wszystko przez terminal W18.",
    },
    {
        "id": "W19",
        "number": 19,
        "canonical_name": "Audit / Closure / Learning / Evolution",
        "polish_name": "Audyt, zamknięcie, uczenie i ewolucja",
        "group": "audit_learning",
        "summary": "Audit trail, decyzje, głosy modeli, Human Gates, Change Proposals, testy, runtime, koszty, final package, memory snapshot i lessons learned.",
        "operator_meaning": "AEIS zamyka projekt, zapisuje wnioski i uczy się, które modele, skills, bramki i decyzje działały.",
        "phase_touchpoints": [36, 40, 41],
        "surfaces": _s("audit", "memory", "execution", "templates"),
        "subsystems": ["audit trail", "decision trail", "final package", "memory snapshot", "lessons learned", "model performance", "skill performance", "drift analysis", "documentation export"],
        "operator_controls": ["zatwierdź final package", "zatwierdź z zastrzeżeniami", "cofnij do testów", "cofnij do Masterplanu", "zamknij nieukończone", "zapisz memory snapshot"],
        "human_gates": ["closure_gate", "memory_snapshot_gate", "documentation_export_gate", "backlog_creation_gate"],
        "hard_rules": [
            "Projekt nie jest zamknięty bez final package, audytu, rozliczenia kosztów i decyzji o pamięci.",
            "Lessons learned nie mogą ominąć Provenance i Quality review.",
        ],
        "runtime_assertion": "Audit i memory zapisują wnioski końcowe.",
    },
]


OVERLAY_RULES: list[dict[str, str]] = [
    {
        "id": "truth_before_plan",
        "label": "Prawda przed planem",
        "rule": "W12 Source of Truth jest nadrzędne wobec W13 Masterplanu i W16 wykonania. Konflikt wraca do W7 Human Gate i W11 Rady.",
    },
    {
        "id": "models_propose_operator_approves",
        "label": "Modele proponują, operator zatwierdza",
        "rule": "W11 tworzy warianty i rekomendacje, ale W1/W7 wymagają operatora dla kierunku, SoT, kosztów, produkcji, external actions i closure.",
    },
    {
        "id": "w18_everywhere",
        "label": "W18 to stały cockpit",
        "rule": "Każde kliknięcie w UI powinno mieć równoważną komendę w W18, a W18 powinno utrzymywać kontekst Księgi i Human Gate.",
    },
    {
        "id": "external_actions_blocked",
        "label": "Świat zewnętrzny jest blokowany",
        "rule": "W17 zaczyna jako blocked/future dla external submit, funding, mobile i lab, dopóki operator nie zatwierdzi konkretnej gałęzi.",
    },
    {
        "id": "learning_loop",
        "label": "Pętla uczenia",
        "rule": "W19 zamyka projekt i zasila W8 pamięć oraz W9 skills, ale tylko z zachowanym audytem i przeglądem jakości.",
    },
]


TALIOR_FLOW: list[dict[str, str]] = [
    {"layer": "W1", "text": "Canon mówi: modele proponują, operator zatwierdza."},
    {"layer": "W2", "text": "Workspace działa lokalnie."},
    {"layer": "W3", "text": "Operator Ylion ma uprawnienia właściciela."},
    {"layer": "W4", "text": "Dostępne są modele lokalne i/lub API."},
    {"layer": "W5", "text": "Runtime ustawiony local-first."},
    {"layer": "W6", "text": "Autonomia ustawiona medium."},
    {"layer": "W7", "text": "Human Gate aktywny dla kierunku, SoT, Masterplanu, kosztów i produkcji."},
    {"layer": "W8", "text": "Memory szuka podobnych projektów operatorskich."},
    {"layer": "W9", "text": "Skills dobierają operator_console, source_of_truth, model_council."},
    {"layer": "W10", "text": "Intake przyjmuje pomysł panelu AEIS."},
    {"layer": "W11", "text": "Rada modeli analizuje i proponuje warianty A/B/C/D/E."},
    {"layer": "W12", "text": "Księga zapisuje wybrany kierunek jako Source of Truth."},
    {"layer": "W13", "text": "Masterplan dzieli projekt na moduły."},
    {"layer": "W15", "text": "Ontology definiuje Project, CouncilSession, HumanGateTicket, SoTEntry."},
    {"layer": "W16", "text": "Workery budują UI, API, testy i dokumentację."},
    {"layer": "W14", "text": "Quality Gates sprawdzają wynik."},
    {"layer": "W17", "text": "External actions są zablokowane, funding/mobile/lab jako future."},
    {"layer": "W18", "text": "Operator prowadzi wszystko przez terminal W18."},
    {"layer": "W19", "text": "Audit i memory zapisują wnioski końcowe."},
]


CORE_PRINCIPLES: list[dict[str, str]] = [
    {
        "id": "truth_before_execution",
        "label": "Najpierw prawda, potem realizacja",
        "description": "AEIS nie buduje na luźnych rozmowach. Najpierw ustala kierunek i Source of Truth.",
    },
    {
        "id": "plan_before_execution",
        "label": "Najpierw plan, potem wykonanie",
        "description": "Po Source of Truth powstaje Masterplan jako operacyjny plan wykonania.",
    },
    {
        "id": "council_for_significant_change",
        "label": "Istotne zmiany przechodzą przez Radę modeli",
        "description": "Skala Rady zależy od ryzyka, ale strategiczny zwrot nie powinien iść bez deliberacji.",
    },
    {
        "id": "human_gate_for_risk",
        "label": "Ryzykowne decyzje przechodzą przez Human Gate",
        "description": "Human Gate jest centralnym mechanizmem odpowiedzialności, nie końcowym popupem.",
    },
    {
        "id": "risk_based_autonomy",
        "label": "Autonomia jest risk-based",
        "description": "System pyta o zgodę, gdy rośnie ryzyko, koszt, odpowiedzialność albo wpływ.",
    },
    {
        "id": "adaptive_scale",
        "label": "System dobiera skalę działania",
        "description": "AEIS proponuje liczbę zespołów, modeli, skills i środowisk zamiast wymagać ręcznego schedulingu.",
    },
    {
        "id": "memory_changes_planning",
        "label": "Pamięć wpływa na przyszłe planowanie",
        "description": "Memory nie jest archiwum. Ma zmieniać wybór modeli, skills, runtime i ostrzeżenia.",
    },
    {
        "id": "skills_are_capabilities",
        "label": "Skills są kompetencjami systemu",
        "description": "Skill to procedura wykonania, testowania, dokumentacji lub integracji, a nie tylko prompt.",
    },
    {
        "id": "multi_model_operation",
        "label": "AEIS pracuje wielomodelowo",
        "description": "System zarządza rolami, rangami, wagami głosu i odpowiedzialnościami modeli.",
    },
    {
        "id": "operator_decides_direction",
        "label": "Operator steruje decyzjami, nie mikrozadaniami",
        "description": "Człowiek zatwierdza kierunek, ryzyko, koszty, produkcję i działania wiążące.",
    },
]


CORE_ENTITIES: list[dict[str, str]] = [
    {"id": "Project", "label": "Projekt", "description": "Jednostka nadrzędna z celem, zakresem, ryzykiem, ograniczeniami, historią, decyzjami i stanem realizacji."},
    {"id": "IntakeRecord", "label": "Idea / Intake Record", "description": "Pierwszy zapis intencji operatora; jeszcze nie Source of Truth."},
    {"id": "SourceOfTruth", "label": "Source of Truth", "description": "Kanoniczny opis projektu po zatwierdzeniu kierunku przez człowieka."},
    {"id": "Masterplan", "label": "Masterplan", "description": "Operacyjny plan wykonania oparty o Source of Truth."},
    {"id": "ChangeProposal", "label": "Change Proposal", "description": "Propozycja zmiany prawdy, planu, modułu, kosztu, architektury lub runtime."},
    {"id": "ModelProfile", "label": "Model Profile", "description": "Opis modelu AI: rola, ranga, koszt, specjalizacja, waga głosu, skuteczność i limity autonomii."},
    {"id": "ModelCouncilSession", "label": "Model Council Session", "description": "Sesja Rady modeli dotycząca etapu, wariantu lub zmiany."},
    {"id": "SkillBinding", "label": "Skill Binding", "description": "Przypisanie skillu do projektu, modułu, zespołu albo modelu."},
    {"id": "AgentTeam", "label": "Agent Team", "description": "Zespół agentów lub modeli odpowiedzialny za konkretny zakres."},
    {"id": "ExecutionModule", "label": "Execution Module", "description": "Jednostka realizacyjna Masterplanu: API, UI, testy, dokumentacja, funding, mobile lub runtime."},
    {"id": "HumanGateTicket", "label": "Human Gate Ticket", "description": "Element kolejki decyzji człowieka z typem, priorytetem, trybem i audytem."},
    {"id": "RuntimeTarget", "label": "Runtime Target", "description": "Środowisko wykonania: local, VPS, container, device albo browser automation."},
    {"id": "ApprovalPolicy", "label": "Approval Policy", "description": "Reguły, kiedy system działa sam, a kiedy musi wrócić do człowieka."},
    {"id": "AuditRecord", "label": "Audit Record", "description": "Zapis decyzji, zmian, głosowań, wykonania, wyników i odchyleń."},
    {"id": "MemorySnapshot", "label": "Memory Snapshot", "description": "Zapis doświadczenia projektu po ważnym etapie albo po zakończeniu."},
]


DEFAULT_POLICIES: list[dict[str, str]] = [
    {"id": "runtime", "label": "Runtime", "value": "local-first"},
    {"id": "autonomy", "label": "Autonomia", "value": "medium"},
    {"id": "production", "label": "Produkcja", "value": "zawsze Human Gate"},
    {"id": "external_actions", "label": "External upload/submit", "value": "zawsze Human Gate"},
    {"id": "final_action", "label": "Final action", "value": "zawsze Human Gate"},
    {"id": "cost_single_action", "label": "Koszt pojedynczej akcji", "value": "approval powyżej ok. 25 EUR"},
    {"id": "cost_monthly", "label": "Koszt miesięczny", "value": "approval powyżej ok. 100 EUR"},
    {"id": "vps_workers", "label": "VPS workers", "value": "approval powyżej ok. 3 workerów"},
    {"id": "mobile", "label": "Mobile approval", "value": "tylko zbindowane urządzenie, secure token, follow-me off"},
    {"id": "memory", "label": "Pamięć", "value": "similarity search on, zapisy po głównych etapach"},
    {"id": "skills", "label": "Skills", "value": "auto-dobór; ryzykowne rozszerzenia przez człowieka"},
]


IMPLEMENTATION_PLANES: list[dict[str, str]] = [
    {"id": "W1", "label": "Operator Interface", "description": "Next.js frontend, onboarding wizard, lifecycle dashboard, operator monitor, advisor feed, cockpit i mobile app."},
    {"id": "W2", "label": "Idea Lifecycle", "description": "11 stanów idei i projektu od draft do hard_deleted z boczną gałęzią blocked."},
    {"id": "W3", "label": "Council Hybrid", "description": "9 ról, 5 rang, 4 fazy deliberacji i mandatory critic signature dla D3+."},
    {"id": "W4", "label": "Decision Gates D0-D5", "description": "D-ladder z D0 Informational oraz regułami eskalacji U1-U6."},
    {"id": "W5", "label": "SoT + Masterplan", "description": "Księga jako canonical reference i drift detection przy konflikcie z decyzjami Rady."},
    {"id": "W6", "label": "Execution Pipeline", "description": "State machine planning -> executing -> reviewing -> done/failed z cascade rollback."},
    {"id": "W7", "label": "Skills Registry", "description": "Manifest-driven runtime, SkillBindings i hybrid task-to-skill matcher."},
    {"id": "W8", "label": "Demand Signal Analyzer", "description": "Telemetria użycia skills, demand-supply gap i deprecated skill detection."},
    {"id": "W9", "label": "Memory + Vault", "description": "6 typów pamięci, vault dla sekretów i replay-as-fork primitives."},
    {"id": "W10", "label": "Governance + Evidence Spine", "description": "Immutable audit trail, Evidence Pack dla D3+ i 17 audit chains."},
    {"id": "W11", "label": "Adapter Bus", "description": "Multi-LLM routing, subscription waterfall, PAYG cap i metryki providerów."},
    {"id": "W12", "label": "Operator Mobile", "description": "Mobile approvals, device binding, HMAC, push, biometric step-up i offline queue."},
    {"id": "W13", "label": "Advisor Layer", "description": "Proaktywna inteligencja AEIS: preferences, recommendation engine, specialized advisors i guided UX."},
    {"id": "W14", "label": "Testing Ontology", "description": "12 epików testowych, 25 typów obiektów, enums, OntologyStore i release rail."},
    {"id": "W15", "label": "Ontology Runtime Plane", "description": "Formalny model projektu jako runtime artifact i walidacja manifestów."},
    {"id": "W16", "label": "Operational Apps Builder Plane", "description": "G1 cascade, G2 template generation, G3 demand signals migration i panele operatora."},
    {"id": "W17", "label": "Deployment Plane", "description": "Hybrid deploy local/VPS/container/device, cost ledger i routing decisions."},
    {"id": "W18", "label": "Operator Terminal Plane", "description": "Główna płaszczyzna operatora, przez którą 41 faz manuala działa w UI."},
    {"id": "W19", "label": "Policy / Security Plane", "description": "PgPolicyRegistry, federation policy, jinja evaluator i routing gate decisions."},
]


ADVISOR_LAYER: dict[str, Any] = {
    "id": "W13",
    "label": "Advisor Layer",
    "summary": "Proaktywna inteligencja AEIS: system obserwuje runtime, emituje AdvisorCards, sugeruje, ostrzega i eskaluje do Human Gate.",
    "pillars": [
        "Adaptive Preferences",
        "Recommendation Engine",
        "Specialized Advisors",
        "Guided UX",
    ],
    "specialized_advisors": [
        "Subscription Advisor",
        "Scaling Advisor",
        "Funding Advisor",
        "Role Resolver Advisor",
        "Variants Generator",
    ],
    "lifecycle_hooks": [
        "operator_login",
        "project_inception",
        "goal_definition",
        "council_convening",
        "council_deliberation",
        "ksiega_generation",
        "model_selection",
        "skill_synthesis",
        "masterplan",
        "preflight_cost",
        "build_initialization",
        "mid_build_issue",
        "quality_gates",
        "acceptance_testing",
        "pre_deploy",
        "project_closure",
    ],
}


PHASE_PATCHES: list[dict[str, str]] = [
    {
        "id": "phase_5_d0_d5",
        "phase": "5",
        "severity": "HIGH",
        "label": "D-ladder D0-D5",
        "description": "Faza 5 musi używać 6 klas decyzji D0-D5 oraz reguł eskalacji U1-U6.",
    },
    {
        "id": "phase_7_subscription_waterfall",
        "phase": "7",
        "severity": "CRITICAL",
        "label": "Subscription waterfall",
        "description": "Cost Guard musi liczyć koszt przez subscription tier -> PAYG -> hard cap, a nie tylko PAYG.",
    },
    {
        "id": "phase_20_25_council_hybrid",
        "phase": "20-25",
        "severity": "CRITICAL",
        "label": "Council Hybrid",
        "description": "Council ma 9 ról, 5 rang, 4 fazy deliberacji i critic signature dla D3+.",
    },
    {
        "id": "phase_30_subscription_advisor",
        "phase": "30",
        "severity": "HIGH",
        "label": "Subscription Advisor",
        "description": "Pre-Flight Cost musi używać Advisor W13 do hard gate decyzji subscription/PAYG.",
    },
    {
        "id": "customer_y_cost",
        "phase": "Customer Y CRM",
        "severity": "CRITICAL",
        "label": "Rekalkulacja kosztów",
        "description": "Koszty Customer Y CRM muszą uwzględniać subscription waterfall zamiast 100% PAYG.",
    },
]


AUDIT_STAGES: list[dict[str, str]] = [
    {"id": "0", "label": "Kalibracja kanonu", "description": "Porównanie rozmowy, założeń, PDF-ów, promptów i dokumentów."},
    {"id": "1", "label": "Inwentaryzacja", "description": "Pełna lista modułów, ścieżek, API, UI i testów."},
    {"id": "2", "label": "Architektura rzeczywista", "description": "Mapa warstw, zależności i przepływów według kodu i runtime."},
    {"id": "3", "label": "Memory, skills, autonomia, Rada", "description": "Sprawdzenie, czy system jest adaptacyjny, a nie tylko statyczny."},
    {"id": "4", "label": "Human Gate", "description": "Weryfikacja globalnych decyzji, typów gate, batch, delegacji, eskalacji i audytu."},
    {"id": "5", "label": "Funding", "description": "Osobny audyt domeny fundingowej i formalnych akcji zewnętrznych."},
    {"id": "6", "label": "Mobile", "description": "Osobny audyt operator mobile, device binding, secure token i follow-me mode."},
    {"id": "7", "label": "Functional audit", "description": "Status działania moduł po module."},
    {"id": "8", "label": "Runtime verification", "description": "Uruchomienie backendu, frontendu, dashboardu i API."},
    {"id": "9", "label": "Testy jak człowiek", "description": "Scenariusze end-to-end przez dashboard, formularze, approvale i W18."},
    {"id": "10", "label": "Drift analysis", "description": "Porównanie kanonu z kodem, runtime, dokumentacją i poprzednimi wersjami."},
    {"id": "11", "label": "Klasyfikacja", "description": "CORE, EXTENSIONS, EXPERIMENTAL, DUPLICATE, LEGACY i PLANOWANY."},
    {"id": "12", "label": "Backlog naprawczy", "description": "Lista napraw i braków po audycie."},
    {"id": "13", "label": "Nowa księga systemowa", "description": "Jedna aktualna dokumentacja po ustaleniu prawdy."},
]


MODULE_AUDIT_FIELDS: list[str] = [
    "nazwa",
    "ścieżka",
    "warstwa",
    "typ",
    "zależności",
    "czy jest w kanonie",
    "czy ma API",
    "czy ma UI",
    "czy ma testy",
    "czy ma ślady runtime",
    "czy ma Human Gate touchpoints",
    "czy korzysta z pamięci",
    "czy korzysta ze skills",
    "czy ma przypisanie do Rady modeli",
    "czy ma operator surface",
    "czy ma dokumentację",
    "czy dokumentacja zgadza się z kodem",
]


WORKING_MODEL: dict[str, Any] = {
    "definition": "AEIS jest systemem operacyjnym dla projektów: kontrolowaną platformą autonomii, deliberacji, planowania, wykonania, governance, pamięci i audytu.",
    "outputs": [
        "aplikacje backendowe",
        "aplikacje frontendowe",
        "dashboardy operatorskie",
        "kontrakty API i proto",
        "dokumentacja techniczna i kanoniczna",
        "audyty i mapy driftu",
        "masterplany",
        "Source of Truth",
        "testy techniczne i testy jak człowiek",
        "paczki deploymentowe",
        "workflow operatorskie",
        "Operator Mobile",
        "grant packages",
        "raporty i backlogi naprawcze",
        "workflow urządzeniowe i laboratoryjne",
    ],
    "principles": CORE_PRINCIPLES,
    "entities": CORE_ENTITIES,
    "default_policies": DEFAULT_POLICIES,
    "audit_stages": AUDIT_STAGES,
    "module_audit_fields": MODULE_AUDIT_FIELDS,
    "runtime_truth_order": ["kod", "runtime", "API", "UI", "testy", "dokumentacja"],
    "module_statuses": [
        "LIVE_VERIFIED",
        "PARTIAL",
        "BROKEN",
        "API_ONLY",
        "UI_ONLY",
        "UNDOCUMENTED",
        "DOC_DRIFT",
        "LEGACY",
        "DUPLICATE",
        "PLANOWANY / NIEZAIMPLEMENTOWANY",
    ],
    "implementation_planes": IMPLEMENTATION_PLANES,
    "advisor_layer": ADVISOR_LAYER,
    "phase_patches": PHASE_PATCHES,
}


GROUP_BY_ID = {group["id"]: group for group in GROUPS}
LAYER_BY_ID = {layer["id"]: layer for layer in LAYERS}


def _phase_overlay() -> dict[str, list[str]]:
    overlay: dict[str, list[str]] = {str(phase): [] for phase in range(1, 42)}
    for layer in LAYERS:
        for phase in layer["phase_touchpoints"]:
            overlay[str(phase)].append(layer["id"])
    return overlay


PHASE_OVERLAY = _phase_overlay()


def _enrich_layer(layer: dict[str, Any]) -> dict[str, Any]:
    group = GROUP_BY_ID[layer["group"]]
    phases = layer["phase_touchpoints"]
    return {
        **layer,
        "group_label": group["label"],
        "phase_span": "1-41" if layer["id"] == "W18" else f"{min(phases)}-{max(phases)}",
        "coverage": {
            "phase_count": len(phases),
            "surface_count": len(layer["surfaces"]),
            "human_gate_count": len(layer["human_gates"]),
            "subsystem_count": len(layer["subsystems"]),
        },
    }


@router.get("")
def list_architecture_layers() -> dict[str, Any]:
    layers = [_enrich_layer(layer) for layer in LAYERS]
    return {
        "schema_version": "2026-05-02",
        "title": "AEIS Architecture Layers W1-W19",
        "summary": {
            "layer_count": len(layers),
            "phase_count": 41,
            "principle": "Warstwy W1-W19 opisują architekturę AEIS; fazy 1-41 opisują przebieg pracy operatora.",
            "short_definition": "W1-W9 przygotowują system, W10-W13 ustalają prawdę i plan, W14-W17 wykonują i integrują wynik, W18 steruje całością, W19 zamyka audyt i uczenie.",
        },
        "groups": GROUPS,
        "layers": layers,
        "phase_overlay": PHASE_OVERLAY,
        "overlay_rules": OVERLAY_RULES,
        "talior_flow": TALIOR_FLOW,
        "working_model": WORKING_MODEL,
        "implementation_planes": IMPLEMENTATION_PLANES,
        "advisor_layer": ADVISOR_LAYER,
        "phase_patches": PHASE_PATCHES,
        "source_documents": [
            "docs/instrukcja obslugi/00_ARCHITEKTURA_W1_W19.md",
            "docs/instrukcja obslugi/00_ADVISOR_LAYER.md",
            "docs/instrukcja obslugi/00_PATCHES_FAZ.md",
            "docs/instrukcja obslugi/00_architecture_layers_w1_w19.md",
        ],
    }


@router.get("/{layer_id}")
def get_architecture_layer(layer_id: str) -> dict[str, Any]:
    normalized = layer_id.strip().upper()
    if normalized.isdigit():
        normalized = f"W{int(normalized)}"
    layer = LAYER_BY_ID.get(normalized)
    if layer is None:
        raise HTTPException(status_code=404, detail=f"Unknown architecture layer: {layer_id}")
    return {
        "schema_version": "2026-05-02",
        "layer": _enrich_layer(layer),
        "related_phases": {
            str(phase): PHASE_OVERLAY[str(phase)]
            for phase in layer["phase_touchpoints"]
        },
    }
