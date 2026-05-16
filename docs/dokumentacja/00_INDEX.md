# SYLION AEIS — indeks dokumentacji

> Główny punkt wejścia do dokumentacji operatorskiej, deweloperskiej i audytorskiej.
> Wersja: runtime sync P3-004 z 2026-05-13, po R3.14 funding reporting i usunieciu legacy dashboardu.

## Spis treści

- [1. Dokumenty strategiczne (rdzeń)](#1-dokumenty-strategiczne-rdzeń)
- [2. Dokumentacja moduł-po-moduł](#2-dokumentacja-moduł-po-moduł)
  - [2.1 Backend modules (12)](#21-backend-modules-12)
  - [2.2 Frontend surfaces (8)](#22-frontend-surfaces-8)
  - [2.3 Cross-cutting concerns (12)](#23-cross-cutting-concerns-12)
  - [2.4 Setup + ops (3)](#24-setup--ops-3)
- [3. Ścieżki czytania per rola](#3-ścieżki-czytania-per-rola)
- [4. Konwencje dokumentacji](#4-konwencje-dokumentacji)

---

## 1. Dokumenty strategiczne (rdzeń)

| Dokument | Kogo dotyczy | Co znajdziesz |
|---|---|---|
| [00_architektura_systemu.md](./00_architektura_systemu.md) | Wszyscy | 12 warstw + 13. Advisor, 15 faz cyklu, 10 typów Human Gate, Rada Modeli, D-ladder D0–D5, progi kosztowe, 13 etapów audytu |
| [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) | Operator, dev | Deep-dive 13. warstwy: 4 filary, 11 modułów backend, 4 surfaces frontend, 16 lifecycle hooks, AdvisorCard, hybrid LLM-as-judge |
| [02_operational_manual.md](./02_operational_manual.md) | Operator | Codzienna praca z systemem |
| [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) | Audytor, compliance | Decision Gates, Evidence Spine, audit trails |
| [04_dla_developera.md](./04_dla_developera.md) | Developer | Konwencje kodu, testy, kontrybucje |
| [05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md](./05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md) | Wszyscy | Snapshot decyzji architektonicznych z 2026-04-25 |
| [DOCS_RUNTIME_SYNC_2026_05_13.md](./DOCS_RUNTIME_SYNC_2026_05_13.md) | Wszyscy | Aktualny override runtime: porty, endpointy, funding reporting, status plikow modulowych |

---

## 2. Dokumentacja moduł-po-moduł

Folder `modules/` zawiera **41 plikow** dokumentacji modulowej. Plan P3-004 zakladal 51 plikow, ale aktualny stan repo zawiera 41 aktywnych plikow `.md`; ich status sync jest zapisany w [DOCS_RUNTIME_SYNC_2026_05_13.md](./DOCS_RUNTIME_SYNC_2026_05_13.md).

Każdy plik:
- ma TOC,
- ma 10-sekcyjną strukturę (Cel, Architektura, Konfiguracja, Funkcje, Eventy, Storage, Przykłady, Verification, Troubleshooting, Cross-refs),
- jest po polsku z kodem/JSON/YAML w angielskim,
- zawiera konkretne przykłady (commands, code snippets, operator flows).

### 2.1 Backend modules (13)

| # | Plik | Moduł | Główny cel |
|---|---|---|---|
| 01 | [modules/01_preferences.md](./modules/01_preferences.md) | `sylion.aeis.advisor.preferences` | 3D matrix `(user × project_type × project_domain)`, 4-level fallback, append-only audit |
| 02 | [modules/02_pricing.md](./modules/02_pricing.md) | `sylion.aeis.advisor.pricing` | Provider adapters, profile catalog, live metadata, ASSUMPTION flag |
| 03 | [modules/03_actions.md](./modules/03_actions.md) | `sylion.aeis.advisor.actions` | Action handlers, retry, routing table, audit |
| 04 | [modules/04_events.md](./modules/04_events.md) | `sylion.aeis.advisor.events` | Audit subscriber + proto registry + lifecycle event glue |
| 05 | [modules/05_engine.md](./modules/05_engine.md) | `sylion.aeis.advisor.engine` | Hybrid rule engine + LLM-judge + D-ladder + AdvisorCard builder |
| 06 | [modules/06_history.md](./modules/06_history.md) | `sylion.aeis.advisor.history` | Event-sourced learning, partition manager, recorder |
| 07 | [modules/07_funding.md](./modules/07_funding.md) | `sylion.aeis.advisor.funding` + `sylion.funding_autopilot` | Per-grant scoring, scanner, aplikacje, submission, raporty PDF/CSV/XLSX |
| 08 | [modules/08_role_resolver.md](./modules/08_role_resolver.md) | `sylion.aeis.advisor.role_resolver` | Routing role → model LLM, defaults YAML |
| 09 | [modules/09_variants.md](./modules/09_variants.md) | `sylion.aeis.advisor.variants` | 3 strategiczne warianty: cost-saving / balanced / aggressive |
| 10 | [modules/10_subscription.md](./modules/10_subscription.md) | `sylion.aeis.advisor.subscription` | HARD GATE D3+, ROI calculator, plan catalog, usage tracker |
| 11 | [modules/11_scaling.md](./modules/11_scaling.md) | `sylion.aeis.advisor.scaling` | Topology recommender (local / VPS / hybrid), staging planner |
| 12 | [modules/12_mobile_gateway.md](./modules/12_mobile_gateway.md) | `sylion.aeis.advisor.mobile_gateway` | REST → gRPC translator, JWT auth, openapi.yaml, biometric step-up |
| 28 | [modules/28_orchestration_panel.md](./modules/28_orchestration_panel.md) | `sylion.aeis.advisor.orchestration_config` | Meta-orkiestracja J1–J9: routing LLM, Rada, audytor, fixer, dispatch, test catalog, zespoły, event map, inter-model |

### 2.1b Backend modules — sprint4+5 (Subscription-First + Project Hub)

| # | Plik | Moduł / Feature | Główny cel |
|---|---|---|---|
| 02+ | [modules/02_pricing.md §4.9](./modules/02_pricing.md) | `pricing.estimator.effective_cost_estimate` | Subscription-first cost routing + Source.SUBSCRIPTION (sprint4) |
| 08+ | [modules/08_role_resolver.md §4.8](./modules/08_role_resolver.md) | `role_resolver.resolver` priority routing | Subscription → PAYG → Budget Cap waterfall; ModelChoice.used_subscription (sprint4) |
| 10+ | [modules/10_subscription.md §10.5](./modules/10_subscription.md) | `subscription.quota_tracker` + DB | QuotaStatus, active_subscriptions, quota_usage tabele (sprint4) |

### 2.2 Frontend surfaces (13)

| # | Plik | Surface | Route |
|---|---|---|---|
| 20 | [modules/20_advisor_feed.md](./modules/20_advisor_feed.md) | Live Advisor Feed | `/advisor` |
| 21 | [modules/21_onboarding_wizard.md](./modules/21_onboarding_wizard.md) | Onboarding (10 kroków) | `/onboarding` |
| 22 | [modules/22_lifecycle_dashboard.md](./modules/22_lifecycle_dashboard.md) | Project Lifecycle Dashboard | `/projects/[id]/lifecycle` |
| 23 | [modules/23_operator_monitor.md](./modules/23_operator_monitor.md) | Operator Monitor | `/dashboard/operator-monitor` |
| 24 | [modules/24_settings_advisor.md](./modules/24_settings_advisor.md) | Settings Advisor | `/settings/advisor` |
| 25 | [modules/25_evidence_pack_viewer.md](./modules/25_evidence_pack_viewer.md) | Evidence Pack Viewer | `/evidence` |
| 26 | [modules/26_council_voting.md](./modules/26_council_voting.md) | Council Voting | `/governance` |
| 27 | [modules/27_audit_viewer.md](./modules/27_audit_viewer.md) | Audit Viewer | `/audit` |
| 29 | [modules/29_faq_runbook.md](./modules/29_faq_runbook.md) | FAQ i Runbook | `/faq` |
| 43 | [modules/43_ai_models_config.md](./modules/43_ai_models_config.md) | AI Models Config | `/ai-models` |
| 44 | [modules/44_idea_vault.md](./modules/44_idea_vault.md) | Idea Vault | `/idea-vault` |
| 35 | [modules/35_cockpit_project_hub.md](./modules/35_cockpit_project_hub.md) | Cockpit Project Hub | `/advisor/cockpit` — ProjectSwitcher, NewProjectModal, RecentProjectsStrip, ProjectHubProvider (sprint5) |
| R3.14 | [modules/07_funding.md §R3.14](./modules/07_funding.md#r314-runtime-update--funding-autopilot-i-raportowanie) | Funding Autopilot Reporting | `/funding` |
| 45 | [modules/45_mobile_app.md](./modules/45_mobile_app.md) | Operator Mobile web/gateway + planned native app | `/operator-mobile`, `/mobile`, Android/iOS planned |

### 2.3 Cross-cutting concerns (12)

| # | Plik | Temat |
|---|---|---|
| 30 | [modules/30_event_taxonomy_full.md](./modules/30_event_taxonomy_full.md) | Pelna taksonomia eventow (internal + outbound) per modul |
| 31 | [modules/31_d_ladder_complete.md](./modules/31_d_ladder_complete.md) | D0-D5 — kompletna specyfikacja, upgrade rules U1-U6, case studies |
| 32 | [modules/32_evidence_pack_templates.md](./modules/32_evidence_pack_templates.md) | D3 Light + D5 Full templates z wypelnionymi przykladami |
| 33 | [modules/33_council_hybrid.md](./modules/33_council_hybrid.md) | 9 rol x 5 rang x weighted vote math + critic/cost/security sentinels |
| 34 | [modules/34_llm_pool_routing.md](./modules/34_llm_pool_routing.md) | Pelna routing matrix per recommendation_type x risk x project_domain |
| 30og | [modules/30_offline_guard.md](./modules/30_offline_guard.md) | BackendOfflineGuard — polling /health, blur overlay gdy backend offline |
| 46 | [modules/46_w14_ontology.md](./modules/46_w14_ontology.md) | W14 Testing Ontology — 25 obiektow, 12 enums, Store, REST (E1) + Testing Actions 20 handlerow (E2) + Branches/Simulation L0-L4 (E3) + Auto-Repair R0-R9/LoopGovernor/MergeGuard (E4) + 13 Guardians/TruthAlignment (E5) + Release Rail 12+6 (E6) + cross-refs E7-E12 (§16) |
| 47 | [modules/47_w14_charter_finding.md](./modules/47_w14_charter_finding.md) | W14 E7 — CharterStore (draft→proposed→approved→archived) + FindingStore (R0-R9 flow) + auto-mirror D2+ → governance tickets + 27 testow |
| 48 | [modules/48_w14_human_lab.md](./modules/48_w14_human_lab.md) | W14 E8 — 8 person startowych (Anna/Marek/Katarzyna/Tomek/Marcin/Piotr/Ewa/Adam) + 10 scenariuszy pokrywajacych D3-D5 + cognitive runtime + 14 testow |
| 49 | [modules/49_w14_test_center.md](./modules/49_w14_test_center.md) | W14 E9+E10 — Test Center UI (8 stron /test-center/*) + TestingMemoryStore (4 tabele) + W14SelfAudit (10 filarow) + sidebar link + 12 testow |
| 50 | [modules/50_w14_demo_projects.md](./modules/50_w14_demo_projects.md) | W14 E11 — 6 projektow demo (D3-D5): manifesty YAML, DemoProjectOrchestrator, execute_demo, 51 REST endpoints, 6 stron FE, 151 testow |
| 51 | [modules/51_w14_agent_team_theater.md](./modules/51_w14_agent_team_theater.md) | W14 E12 — AgentTheaterAggregator read-only (topology/council/repair/guardians/locals) + 6 REST endpoints + /test-center/theater dashboard + 9 testow |

### 2.4 Setup + ops (3)

| # | Plik | Temat |
|---|---|---|
| 40 | [modules/40_setup_step_by_step.md](./modules/40_setup_step_by_step.md) | Pełny setup krok po kroku (PG, env, alembic, npm, troubleshooting) |
| 41 | [modules/41_environment_variables.md](./modules/41_environment_variables.md) | Wszystkie env vars (backend + frontend + Docker + CI/CD) |
| 42 | [modules/42_configuration_files.md](./modules/42_configuration_files.md) | Wszystkie config files (manifesty, YAML, docker-compose, frontend, test) |

---

## 3. Ścieżki czytania per rola

### Operator (codzienna praca)
1. [00_architektura_systemu.md](./00_architektura_systemu.md) §3–8 — warstwy, fazy, Human Gate, koszty
2. [02_operational_manual.md](./02_operational_manual.md) — codzienne procedury
3. [modules/40_setup_step_by_step.md](./modules/40_setup_step_by_step.md) §8 — onboarding wizard
4. [modules/20_advisor_feed.md](./modules/20_advisor_feed.md) — Live Feed (główny ekran)
5. [modules/24_settings_advisor.md](./modules/24_settings_advisor.md) — preferencje
6. [modules/31_d_ladder_complete.md](./modules/31_d_ladder_complete.md) — co wymaga gate'a

### Nowy developer
1. [04_dla_developera.md](./04_dla_developera.md) — konwencje, testy, PR
2. [modules/40_setup_step_by_step.md](./modules/40_setup_step_by_step.md) — setup środowiska
3. [modules/41_environment_variables.md](./modules/41_environment_variables.md) + [modules/42_configuration_files.md](./modules/42_configuration_files.md) — config
4. [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) — przegląd warstwy
5. Wybierz moduł z `modules/01-12_*.md` zgodny z taskiem
6. [modules/30_event_taxonomy_full.md](./modules/30_event_taxonomy_full.md) — eventy

### Audytor
1. [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) — Decision Gates, Evidence Spine
2. [modules/31_d_ladder_complete.md](./modules/31_d_ladder_complete.md) — D-ladder
3. [modules/32_evidence_pack_templates.md](./modules/32_evidence_pack_templates.md) — Evidence Pack
4. [modules/33_council_hybrid.md](./modules/33_council_hybrid.md) — Rada
5. [modules/27_audit_viewer.md](./modules/27_audit_viewer.md) — Audit UI
6. [modules/04_events.md](./modules/04_events.md) — audit subscriber

### Stakeholder zewnętrzny
1. [00_architektura_systemu.md](./00_architektura_systemu.md) §1–3 i §12
2. [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) §1–4

---

## 4. Konwencje dokumentacji

- **Operator-facing prose**: po polsku.
- **Code, SQL, JSON, YAML, gRPC schemas**: po angielsku (zachowanie precyzji).
- **TOC**: na początku każdego pliku > 200 linii.
- **Cross-references**: linki zamiast duplikacji treści.
- **Konkretne przykłady**: komendy do skopiowania, snippety, operator flows krok-po-kroku.
- **Bez emoji**: chyba że operator explicitly poprosi.
- **Tabele**: dla treści mapping-heavy (events, env vars, RPC mappings).
- **Source of truth**: dokumentacja referuje źródło prawdy w kodzie / manifeście, nie duplikuje.

---

**Kontakt / pytania**: wszystkie problemy z dokumentacją zgłaszaj jako GitHub Issue z labelem `docs`.
