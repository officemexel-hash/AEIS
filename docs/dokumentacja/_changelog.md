# Changelog dokumentacji SYLION AEIS

> Automatyczne wpisy generowane przez Docs Watcher (agent Claude Sonnet).
> Format: jedna iteracja = jeden blok. Zmiany śledzą commits w `src/` od anchora.

---

## 2026-05-13 P3-004 runtime sync po R3.14

### Zakres

- `DOCS_RUNTIME_SYNC_2026_05_13.md` — nowy aktywny override runtime: porty, health, legacy dashboard removed, funding reporting, status 41 plikow modulowych.
- `00_INDEX.md` — zaktualizowano wersje, liczbe aktywnych plikow `modules/` do 41, dodano link do sync card i wpis `/funding` reporting.
- `02_operational_manual.md` — dopisano runtime workflow `/funding`, eksporty PDF/CSV/XLSX i status szkicow e-mail.
- `modules/07_funding.md` — dopisano R3.14 runtime update dla `sylion.funding_autopilot`, endpointow raportowych i UI.
- `modules/*.md` — dodano status `DONE_SYNC_P3_004 (2026-05-13)` do 41 plikow modulowych.
- `modules/41_environment_variables.md` — usunieto aktywne instrukcje `DASHBOARD_DB_PATH` / `sylion_dashboard.db`.
- `docs/system_audit/00_RUNTIME_STARTUP.md` — przepisano aktywny startup na backend `8010`, frontend `3001`, legacy dashboard removed i health po R3.14.
- `AEIS_SYSTEM_BOOK_2026.md` — podniesiono do wersji final runtime sync P3-004.

### Evidence

- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/runtime_api_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/playwright_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/r3_13_cleanup_summary.json`

---

## 2026-04-26 sync v5 (catchup A+C — sprint4+5 advisor + W14 E3-E6)

### A. Advisor sprint4+5 commits

- `d6eb4d15` — subscription waterfall + Step3 subs UI:
  - `modules/10_subscription.md` — nowa sekcja §10.5: Quota Tracker, tabele `active_subscriptions` + `quota_usage`, migracja `phase4_0003_subscription_quota`, funkcje `get_quota_status`/`consume_quota`/`_compute_billing_period`, integracja z pricing i role_resolver
  - `modules/02_pricing.md` — nowa sekcja §4.9: `effective_cost_estimate()`, nowe pole `Source.SUBSCRIPTION`, zwracana krotka `(CostEstimate, used_subscription)`
  - `modules/08_role_resolver.md` — nowa sekcja §4.8: 6-krokowa hierarchia routingu (Subscription → PAYG → Budget Cap), subscription pool z max-remaining-first sort, nowe pola `ModelChoice.used_subscription`/`budget_exceeded`/`suggested_alternative`, tabela przyrostkow `reason`
  - `modules/21_onboarding_wizard.md` — nowa podsekcja §3.4.1: sekcja "Aktywne subskrypcje" w Step 3, SUGGESTED_PLANS (6 planow), SubscriptionRow, waterfall visualization; nowa sekcja §7.8: tryby Step 3 z/bez subskrypcji, localStorage `subscriptions`, crossrefs

- `df504823` — Cockpit v4 Project Hub:
  - `modules/35_cockpit_project_hub.md` — NOWY PLIK: pelna dokumentacja Project Hub; komponenty ProjectSwitcher/NewProjectModal/RecentProjectsStrip/ProjectHubProvider; API client `lib/api/projects.ts` (list/get/create/update); localStorage `sylion.cockpit.active_project`; bootstrap sequence; propagacja `activeProjectId` do LifecycleRail; operator flows

### C. W14 E3-E6 commits

- `7db93cdb` — E3 Branches + Simulation L0-L4 + 4 persony + 7 bledow:
  - `modules/46_w14_ontology.md` — nowa sekcja §12: BranchManager (4 typy), SimulationContract (L0 + twardie limity REJECTS), TransactionalSandbox (L1), SimulationEngine (L0-L4), PersonaRegistry (4 starters), PersonaRuntime (simulate_workflow/decision/inject_error), 7 klas bledow ludzkich, znany bug OntologyStore.list naprawiony

- `787426d1` — E4 Auto-Repair R0-R9 + Loop Governor + Merge Guard:
  - `modules/46_w14_ontology.md` — nowa sekcja §13: LoopGovernor (8 limitow per spec sec 12.1, 6 typow LoopReport), MergeGuard (8 regul odrzucenia, heurystyki diff), AutoRepairController (R0-R9 state machine, integracja LoopGovernor przy R3/R4, MergeGuard przy R9, persystencja RepairAttempt)

- `a612756f` — E5 13 Guardians + Truth Alignment Matrix:
  - `modules/46_w14_ontology.md` — nowa sekcja §14: GuardianBase (alert/status/emit/RGY), tabela 13 guardianow (8 core + 5 nowych: LLMDrift/CostSentinel/PII/TraceCompleteness + 1 brakujacy z core), TruthAlignmentMatrix (7 warstw, 5 regul dryfu, build_for_feature/list_drifts/health_summary), register_all_guardians

- `306ef4bb` — E6 Release Rail: 12+6 checklist + 10 ReleaseStatus:
  - `modules/46_w14_ontology.md` — nowa sekcja §15: ReleaseRail.evaluate + generate_report, RC_CHECKLIST (12 punktow per sec 17.2), PROD_CHECKLIST (6 punktow per sec 17.3), 4 stany status (READY_FOR_PRODUCTION / RC / BLOCKED_BY_GOVERNANCE / BLOCKED_BY_FINDINGS), EvaluationContext z hints, auto-rekomendacje z blockerow, comprehension_score

### Index

- `00_INDEX.md` — dodano §2.1b (sprint4+5 backend modules), nowy wpis `35_cockpit_project_hub.md` w Frontend surfaces, zaktualizowano opis `46_w14_ontology.md` o E3-E6, licznik plikow 36 → 42

### Anchor

Anchor przed sync v5: `73a440ba`. Anchor po sync v5: `3e6c9dbd` (HEAD).

---

## 2026-04-26 iter-3 (sprint4 docs watcher v4)

### Brak nowych commitów src/

Anchor: `73a440ba`. Brak nowych commitów `src/` od iter-2. W working tree istnieje wiele zmodyfikowanych plików (subscription/quota_tracker.py, pricing/estimator.py, advisor_routes.py — Subscriptions API) które nie zostaly jeszcze zacommitowane. Watcher zakończony po iter-3 (1 pusta po 2 produktywnych). Dokumentacja zostanie uzupelniona przy nastepnym sesji gdy pojawiaja sie commity src/ dla tych modulow.

---

## 2026-04-26 iter-2 (sprint4 docs watcher v4)

### Przetworzone commity (anchor: 4c0bfd37 → HEAD 73a440ba)

Commity src/: `634027e1`, `782b58c9`

### Zaktualizowane pliki dokumentacji

- `modules/21_onboarding_wizard.md` — sekcja 3.7: Step6Council adaptive (nowe propsy, inwentarz modeli, dual-judge, banner ostrzegawczy, capowanie slidera); sekcja 7.6: `deriveInventory` + `suggestModelForRisk` — logika Model Inventory z `_lib/available-models.ts`
- `modules/08_role_resolver.md` — sekcja 4.7: `_validators.py` — `check_model_available`, `ModelNotAvailableError`, polska komunikaty, Ollama subprocess check, subskrypcja coverage, mapa ENV_KEY_BY_PROVIDER

---

## 2026-04-26 iter-1 (sprint4 docs watcher v4)

### Przetworzone commity (anchor: c960ed6 → 4c0bfd37)

Commity src/: `de60df95`, `4c0bfd37`

### Zaktualizowane pliki dokumentacji

- `modules/21_onboarding_wizard.md` — sekcja 3.3: Sekcja C "Modele lokalne (Ollama)" w Step 2 — typy `LocalModelEntry`/`LocalModelStatus`, 6 suggested models, logika `pullModel`, endpoint `/api/v1/brain/models/pull`; sekcja 5.2: `local_models` dodane do `WizardValues`; sekcja 7.6: tryby statusow Ollama (not_installed/downloading/installed/error)
- `modules/46_w14_ontology.md` — nowa sekcja 11 "W14 Testing Actions (E2)": architektura pakietu `sylion.aeis.testing.actions`, klasa bazowa `TestingActionHandler`, tabela wszystkich 20 akcji z D-level/phase/mirror_to_ticket, SLA per D-level, kluczowe invarianty walidacji, `register_testing_actions()`, eventy, weryfikacja

### Pokrycie testow

- W14 Actions (E2): 63 testy w 6 plikach (`test_register.py` 8, `test_charter_actions.py` 12, `test_finding_actions.py` 9, `test_repair_actions.py` 11, `test_persona_actions.py` 12, `test_release_actions.py` 11)

---

## 2026-04-26 iter-4 (sprint3 docs watcher v2)

### Przetworzone commity (anchor: 1ecdbce → c960ed6)

Commity: `6e18b93`, `a48326b`, `f75b6c5`, `f32713c`, `6739ec2`, `6344222`, `c960ed6`

### Zaktualizowane pliki dokumentacji

- `modules/05_engine.md` — sekcja 4.12: gRPC Servicer `EngineServicer` (4 RPC: ListRecommendations, GetCard, RecordAction, FinalizeEvidence)
- `modules/07_funding.md` — sekcja 4.20: gRPC Servicer `FundingServicer` (3 RPC: ListGrants, ScoreProject, SimulateGrant)
- `modules/08_role_resolver.md` — sekcja 4.6: gRPC Servicer `RoleResolverServicer` (4 RPC: ResolveRole, ResolveJudgeModel, ListAvailableRoles, GetRoutingMatrix)
- `modules/09_variants.md` — sekcja 4.3: gRPC Servicer `VariantsServicer` (2 RPC: GenerateVariants, CompareVariants)
- `modules/11_scaling.md` — sekcja 4.5: gRPC Servicer `ScalingServicer` (4 RPC: RecommendTopology, ProposeStagingPlan, GetEnvInventory, RegisterEnv)
- `modules/40_setup_step_by_step.md` — sekcja 10: Testy E2E Playwright (5 plikow: cockpit_v4, faq, mode_switch, offline_guard, wizard)
- `modules/28_orchestration_panel.md` — sekcja 10/11: LLM Routing Matrix Editor (`/orchestration/llm-routing`): presety, domain filter, bulk update

### Nowe pliki dokumentacji

- `modules/43_ai_models_config.md` — strona `/ai-models`: 7 zakladek, 10 zrodel API, provider management, registry, Rada modeli, Ollama
- `modules/44_idea_vault.md` — IdeaVault: 15 statusow, graf przejsc, stale detection, API library, 5 komponentow React, REST API, schemat DB
- `modules/45_mobile_app.md` — KMP Etap 2: Android auth+biometria+EncryptedTokenStore+FCM stub, iOS skeleton CocoaPods
- `modules/46_w14_ontology.md` — W14 Ontology E1: 25 dataclasses (4 grupy), 12 enums, OntologyStore (CRUD+relacje+historia), REST `/api/v1/testing/`

### Aktualizacje indeksu

- `00_INDEX.md` — dodano 43, 44, 45 do Frontend surfaces; 46 do Cross-cutting; liczniki: 36 plikow

---

## 2026-04-26 iter-3 (sprint3 docs watcher v2)

### Brak nowych commitów

Anchor: 1ecdbce. Brak nowych src commits. Liczne zmiany w working tree
(idea-vault/page.tsx, operator-mobile, gRPC servicers, cognitive/*.py) —
oczekują na commit. Watcher zakończony po 3 iteracjach (2 produktywne + 1 pusta).

---

## 2026-04-26 iter-2 (sprint3 docs watcher v2)

### Przetworzone commity (anchor: 9c45020 → HEAD 1ecdbce)

Commit: `1ecdbce` — [advisor][codex][sprint3] 3 missing backend endpoints

### Zaktualizowane pliki dokumentacji

- `modules/23_operator_monitor.md` — rozszerzenie endpointow i schematow:
  - Sekcja 5.1: dodano 3 nowe endpointy z dokumentacja parametrow i odpowiedzi:
    `GET /api/v1/advisor/audit/recent`, `GET /api/v1/advisor/teams/topology`,
    `GET /api/v1/advisor/preferences/counts`
  - Sekcja 5.2 `MonitoringSnapshot`: dodano 5 nowych pol (`strategy`, `active_teams`,
    `avg_confidence`, `pending_hg`, `hg_breakdown`)
  - Sekcja 5.3: zaktualizowany przyklad odpowiedzi z nowymi polami

- `modules/05_engine.md` — aktualizacja opisu `_db.py`:
  - Dodano 4 nowe helpery DB: `fetch_recent_audit_entries`, `fetch_avg_confidence`,
    `fetch_human_gate_metrics`, `fetch_configuration_counts`

---

## 2026-04-26 iter-1 (sprint3 docs watcher v2)

### Przetworzone commity (anchor: 0048c5b → HEAD 9c45020)

Commit: `9c45020` — [advisor][sprint2][consolidated] frontend agent uncommitted work bundle

### Zaktualizowane pliki dokumentacji

- `modules/24_settings_advisor.md` — AuditHistoryPanel:
  - Usunięto `mockAudit()` inicjalizację stanu; panel startuje z `[]`, `loading=true`
  - Dodano `useEffect` auto-load przy mount
  - PL etykiety: "Preferences audit log" → "Log audytowy preferencji", "Reload" → "Odswież"
  - Zaktualizowano sekcje 2.3, 3.5, 3.6, 4.4, 7.3, 9.4

- `modules/21_onboarding_wizard.md` — Step2Providers + WizardShell:
  - Step2Providers pełny refaktor: statyczne 4 pola zastąpione dynamiczną listą wpisów
  - 8 AI providerów: Anthropic, OpenAI, Google AI, OpenRouter, Mistral, xAI/Grok, Groq, Ollama
  - Nowa sekcja Hosting Providers: 8 platform (Cloudflare, AWS, Vercel, Render, Fly.io, Railway, DigitalOcean, custom)
  - Nowe typy: `ApiKeyEntry`, `HostingEntry`
  - Przycisk "Skip" → "Pomine na razie" (sekcje 3.1, 7.5)
  - Zaktualizowano `WizardValues` interface (nowe pola `api_keys`, `hosting_providers`)

- `modules/30_offline_guard.md` — ApiOfflineBanner (nowy komponent):
  - Dodano sekcję 1.2: `ApiOfflineBanner` — nieblokujący amber toast bottom-right
  - Tabela porównawcza: Guard (blokujący) vs Banner (nieblokujący)
  - Aktualizacja nagłówka modułu i sekcji cross-references (10.2)

- `modules/20_advisor_feed.md` — usunięcie mock danych:
  - `advisorMocks.cards()` → `[]` (sprint2 usunął demo karty)
  - `advisorMocks.evidencePack()` → `null`
  - Zaktualizowano sekcje 4.2, 4.3, 5.4, 7.1, 7.4, 9.3

---

## 2026-04-26 iter-4

### Przetworzone commity (anchor: 7b004ef → HEAD 34f9a1b)

Commit: `34f9a1b` — [advisor][claude][sprint2] cockpit v4 (Orbital Glass Command Deck)

### Zaktualizowane pliki dokumentacji

- `modules/20_advisor_feed.md` — rozszerzona sekcja 1 "Cel + URL" o podsekcję 1.1
  "Cockpit v4 — Orbital Glass Command Deck":
  - Nowa route `/advisor/cockpit` — główny widok operatora po onboardingu
  - Układ 6 sekcji CockpitV4Page
  - 6 nowych komponentów: `AdvisorCore`, `DecisionCommandCard`, `LifecycleRail`,
    `AgentTopology`, `ConfigurationControlCards`, `AuditTrailCard`
  - 15 faz lifecycle projektu (vs 16 faz H01–H16 w Cockpit v3 z iter-1)
  - Logika priorytetu kart (D4+ → D3 → fallback)
  - CSS scoped `.cockpit-v4` (`operating-advisor-v4.css`, 601 linii)
  - Aktualizacja cross-refs 10.3 (dodano `/advisor/cockpit`)

---

## 2026-04-26 iter-3

### Przetworzone commity (anchor: 7e3b38d → HEAD 7b004ef)

Commit: `7b004ef` — [advisor][claude][sprint2] PL i18n audit + backend offline guard

### Nowe pliki dokumentacji

- `modules/30_offline_guard.md` — **NOWY** (~170 linii) — dokumentacja `BackendOfflineGuard`:
  - Polling `/health` co 5s, timeout 3s
  - 3 stany: `checking`/`online`/`offline`
  - UI offline: blur + overlay + instrukcje naprawy
  - Konfiguracja `NEXT_PUBLIC_API_URL`
  - Integracja w `app/(app)/layout.tsx`

### Zaktualizowane pliki dokumentacji

- `modules/27_audit_viewer.md` — dodana uwaga i18n w sekcji cross-references:
  strona jest w języku polskim, daty formatowane z locale `pl-PL`

- `00_INDEX.md` — dodano wpis modułu `30_offline_guard`; zmieniono "Cross-cutting (5)" → "(6)";
  licznik 31 → 32 pliki

### Pominięte

- i18n na stronach `agents`, `auth`, `budget`, `costs`, `decisions`, `idea-vault`,
  `security-scan`, `onboarding` — tłumaczenia UI strings, bez zmiany architektury;
  wymienione strony nie mają dedykowanych dokumentów modułowych w serii 20-29

---

## 2026-04-26 iter-2

### Przetworzone commity (anchor: 2280b69 → HEAD 7e3b38d)

Commit: `7e3b38d` — [advisor][kimi][sprint2] module-by-module test+fix loop

### Zaktualizowane pliki dokumentacji

- `modules/05_engine.md` — dodana uwaga w sekcji 2.3 (Storage) o bool() vs int() fix
  dla kolumn BOOLEAN w `recommendations`, `llm_judge_audit`, `rule_definitions`.
  Psycopg3 obsługuje natywny Python bool bez konwersji int() (reliktu kompatybilności SQLite)

- `modules/28_orchestration_panel.md` — aktualizacja tabeli tabel PG w sekcji 3.2:
  dodano `config_kv` (klucz TEXT, wartość JSONB) — obecna w `advisor_layer.sql`
  i w conftest izolacji testów, ale pominięta w migracji alembic (planowane uzupełnienie)

### Pominięte (tylko test infrastructure)

- Nowe pliki conftest (`mobile_gateway/`, `orchestration_config/`, `_perf/`,
  `scaling/`, `subscription/`) — izolacja testów w PG, bez wpływu na API
  ani zachowanie serwisów dokumentowane w modułach

---

## 2026-04-26 iter-1

### Przetworzone commity (anchor: 58847db → HEAD f48c232)

Zakresy commitów: `0592958`, `4f9ed74`, `2a3cf80`, `6a9c3ea`, `5f57861`, `f48c232`

### Nowe pliki dokumentacji

- `modules/28_orchestration_panel.md` — **NOWY** (~310 linii) — pełna dokumentacja modułu
  `sylion.aeis.advisor.orchestration_config` (sekcja J):
  - 9 subsystemów J1–J9 (LLM routing, Council rules, Auditor cadence, Fixer protocol,
    Dispatch config, Test catalog, Team formation, Event map, Inter-model conversations)
  - 24 endpointy REST `/api/v1/orchestration/`
  - Schemat PG `advisor_orchestration` (11 tabel, migracja `phase4_0002_orchestration`)
  - Modele danych (18 dataclass)
  - 8 przykładów curl z odpowiedziami
  - (commit `5f57861` + `6a9c3ea` + `f48c232`)

### Zaktualizowane pliki dokumentacji

- `modules/24_settings_advisor.md` — dodana sekcja **7.7 Tryby interfejsu — Operator vs Techniczny**:
  - Hook `useAdvisorMode` (localStorage + custom events `sylion:advisor-mode`)
  - Komponent `ModeBadge` (niebieski operator / bursztynowy technical)
  - Komponent `ModeSwitcher` (przełącznik w TopCommandBar)
  - CSS: `operator-mode.css` + `technical-mode.css`
  - Sekcje sidebar per tryb (4 sekcje operatorskie)
  - Aktualizacja sekcji 10.4 (hooki) + 10.5 (utilities) o nowe pliki
  - (commit `2a3cf80` + `4f9ed74`)

- `00_INDEX.md` — aktualizacje:
  - Dodano wpis modułu 28 w tabeli "Backend modules"
  - Zmieniono licznik z 28 → 29 plików
  - Zmieniono "Backend modules (12)" → "(13)"

### Dodatkowe commity w iteracji 1 (sprint2, wykryte po starcie)

Commity `036566a` → `2280b69` (weszły do repo w trakcie iteracji):

- `modules/23_operator_monitor.md` — dodana sekcja **7.5 Tryb interfejsu: Operating Advisor Cockpit**:
  - Dwa tryby strony (operator Cockpit / technical tabbed)
  - Tabela i opis 6 nowych komponentów Cockpit (`CockpitHero`, `CockpitDecisionSection`,
    `CockpitLifecycleStrip`, `CockpitAgentFlow`, `CockpitConfigStats`, `CockpitFAQWidget`)
  - 16 faz lifecycle H01–H16 z polskimi etykietami
  - Dodatkowe hooki Cockpit
  - Aktualizacja cross-refs (10.3, 10.4)
  - (commit `2280b69`)

- `modules/29_faq_runbook.md` — **NOWY** (~190 linii) — pełna dokumentacja surface `/faq`:
  - 15 pytań w 13 kategoriach (`human_gate`, `production_control`, ..., `transparency`)
  - `FaqEntry` struktura TypeScript + `faq-entries.ts` (666 linii)
  - Komponenty: `FaqSearch`, `FaqEntryCard`, `HelpHint`
  - Backend stub API: `/api/v1/faq/search`, `/entries`, `/contextual/{key}`
  - Deep-linking przez URL hash
  - (commit `f54e049`)

- `00_INDEX.md` — dodano wpis modułu 29; zmieniono "Frontend surfaces (8)" → "(10)";
  licznik plików 28 → 31.

### Pominięte (bez wpływu na dokumentację)

- `0592958` — usunięcie `_db_sqlite.py` i `_db.sqlite_backup.py`: dokumentacja w
  `06_history.md` i `07_funding.md` już poprawnie opisuje PG-only mode; SQLite jest
  wspomniany tylko jako test fixture — opis pozostaje aktualny.
- `32108ca` — fix 500 w `advisor_routes.py` (fallback routes): zmiany wewnętrzne, bez
  wpływu na publiczne API; dokumentacja `20_advisor_feed.md` opisuje endpointy poprawnie.
- `1ae04bd` — weryfikacja 28/28 endpointów: raport w `_handoff/sprint2/`, nie wymaga
  aktualizacji dokumentacji modułów.

---

## 2026-04-26 sync v6 (catchup B — W14 E7-E12)

### Przetworzone commity (12)

- `c8263ea4` E7 CharterStore + FindingStore → **NEW** `modules/47_w14_charter_finding.md`
  - CharterStore: draft→proposed→approved→archived lifecycle + TRANSITIONS enforcement
  - FindingStore: R0-R9 full state machine (_ALLOWED) + auto-mirror D2+ do governance tickets
  - 27 testów (11 charter + 16 findings)

- `4faab428` E8 Human Lab 8 person + 10 scenariuszy → **NEW** `modules/48_w14_human_lab.md`
  - 4 nowe persony (05-08): admin_overconfident/viewer_curious/mobile_first_operator/incident_responder
  - 10 scenariuszy startowych pokrywających wszystkie 8 person + D3-D5 governance paths
  - `starter_scenarios()` factory; 14 testów

- `bad4c2c0` E9+E10 Test Center UI + Memory + Self-Audit → **NEW** `modules/49_w14_test_center.md`
  - 8 stron frontend `/test-center/*` (hub + dashboard + truth-alignment + simulation
    + auto-repair + human-lab + release-gate + catalog)
  - `TestingMemoryStore` (4 tabele SQLite: lessons/root_causes/flaky_patterns/anti_patterns)
  - `W14SelfAudit` 10-filarowy smoke check (W14 testuje siebie)
  - 12 testów

- `3fd53a06` E11 6 manifestów + DemoProjectOrchestrator:
- `df31e83b` E11 execute_demo end-to-end lifecycle (6 kroków):
- `c5e509f0` E11-full Mobile Field Inspector (models+store+service+REST+FE+38 testów):
- `3e6c9dbd` E11-full 5 remaining demos (portal/factory/crm/funding/marketplace, 92 testy):
- `4fcc42ee` E11-rest 5 routerów REST (40 nowych endpoints):
- `26cb526c` E11-fe 5 stron frontend (portal/factory/crm/funding/marketplace):
  → **NEW** `modules/50_w14_demo_projects.md`
  - 6 manifestów YAML (D3×1, D4×3, D5×2; 6 różnych typów domenowych)
  - `DemoProjectOrchestrator.validate_all()` + `execute_demo()` 6-krokowy lifecycle W14
  - 51 REST endpoints łącznie (6 routerów demo w app.py)
  - 6 stron frontend w `/demo/*` z W14 governance showcase + adversarial buttons
  - 151 testów (17 manifest + 4 lifecycle + 38 mobile + 92 remaining demos)

- `ec2205a9` E12-BE + `50773c5a` E12-FE Agent Team Theater → **NEW** `modules/51_w14_agent_team_theater.md`
  - `AgentTheaterAggregator`: 5 metod read-only (topology/council/repair/guardians/locals)
  - 6 REST endpoints `/api/v1/agent-theater/*`
  - `/test-center/theater` dashboard z kartami Topology/Guardians/Local Models + 5s auto-refresh
  - 9 testów

- `cec149cb` integration — cross-refs w `46_w14_ontology.md` i `49_w14_test_center.md`:
  - `register_testing_actions()` w `app.py` (non-fatal, 20 handlerów)
  - Sidebar sekcja "Testowanie i Release" → `/test-center`

### Zaktualizowane pliki dokumentacji

- `modules/46_w14_ontology.md` — dodana sekcja §16 "Cross-references E7-E12" (tabela 5 nowych modułów)
- `00_INDEX.md` — dodano entries 47-51, licznik 42 → 47 plików, Cross-cutting (7) → (12)
- `_changelog.md` — ten wpis (v6)

### Raport

- `docs/claude_parallel/aeis_advisor/_handoff/sprint5/claude_docs_watcher_v6_w14_report.md`

### Stan końcowy

- `modules/` 42 → 47 plików
- 5 nowych docs W14 (E7-E12)
- 12 commitów zsynchronizowanych
- Łączna baza testów E0-E12: 567 (W14 moduły) + 151 (demo) = 718 testów

### Anchor

Poprzedni anchor: `ad1a09b3`
Nowy anchor: `26cb526c` (HEAD branch advisor-etap1)
