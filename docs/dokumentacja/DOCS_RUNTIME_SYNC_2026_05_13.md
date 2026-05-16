# AEIS documentation runtime sync - 2026-05-13

**Status dokumentacji:** DONE_SYNC_P3_004  
**Zakres:** dokumentacja operatorska, modulowa, API/runtime reference i `AEIS_SYSTEM_BOOK_2026.md` po R3.14.  
**Zrodlo prawdy:** kod + runtime evidence z `docs/aeis_repair_v2/evidence/`.

## 1. Snapshot obowiazujacy po R3.14

| Obszar | Stan po synchronizacji |
|---|---|
| Backend dev | `uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010` |
| Frontend dev | Next.js `16.2.4`, React `19.2.4`, kanonicznie `127.0.0.1:3001` |
| Health smoke R3.14 | `status=ok`, `version=3.5.0`, `modules=138`, `endpoints=1953` |
| Runtime DB | `SYLION_DB_PATH`, domyslnie `sylion_aeis.db` |
| Legacy dashboard | katalog `src/sylion-pipeline/dashboard/` usuniety w R3.13; backup tylko jako artefakt rollback |
| Funding UI | `/funding` ma zakladke `Raporty`, wykresy Recharts, CSV pipeline, PDF/XLSX backend downloads i szkice e-mail |
| Funding export API | `GET /api/v1/funding/application/{application_id}/export/{artifact_type}` |
| Operator mobile | web surfaces i REST gateway istnieja czesciowo; natywna aplikacja pozostaje planowana/czesciowa |

## 2. Zasady utrzymania dokumentacji

1. Aktywne instrukcje uruchomieniowe nie moga wskazywac `dashboard/start.py` ani portu backendu `8000`.
2. Dokumentacja ma rozrozniac: `LIVE_VERIFIED`, `PARTIAL`, `LEGACY_REMOVED`, `PLANNED`.
3. Historyczne audyty z `docs/codex_system_audit/` i `docs/claude_system_audit/` moga zachowac stare fakty, ale aktywne docs musza zawierac aktualny override.
4. Liczba plikow modulowych w `docs/dokumentacja/modules/` wynosi obecnie 41; wartosc `51` w planie P3-004 byla zalozeniem historycznym.
5. Kazdy nowy endpoint publiczny musi trafic do dokumentacji modulowej albo do tej karty sync.
6. Kazda zmiana operator surface musi aktualizowac index, manual lub odpowiedni module doc.

## 3. Status plikow modulowych

| Plik | Zakres | Status P3-004 | Uwaga |
|---|---|---|---|
| `01_preferences.md` | preferencje Advisor | DONE_SYNC | opis warstwy advisor, bez runtime smoke w R3.15 |
| `02_pricing.md` | pricing/koszty | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `03_actions.md` | actions | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `04_events.md` | event glue | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `05_engine.md` | advisor engine | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `06_history.md` | historia/learning | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `07_funding.md` | funding | DONE_SYNC | zaktualizowany po R3.14: `/funding`, raporty, eksporty |
| `08_role_resolver.md` | role resolver | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `09_variants.md` | warianty strategii | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `10_subscription.md` | subskrypcje | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `11_scaling.md` | scaling/topology | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `12_mobile_gateway.md` | mobile gateway | DONE_SYNC | mobile opisany jako PARTIAL, nie pelna natywna app |
| `20_advisor_feed.md` | advisor feed | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `21_onboarding_wizard.md` | onboarding | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `22_lifecycle_dashboard.md` | lifecycle dashboard | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `23_operator_monitor.md` | operator monitor | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `24_settings_advisor.md` | settings advisor | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `25_evidence_pack_viewer.md` | evidence viewer | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `26_council_voting.md` | governance/council UI | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `27_audit_viewer.md` | audit viewer | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `28_orchestration_panel.md` | orchestration config | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `29_faq_runbook.md` | FAQ/runbook | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `30_event_taxonomy_full.md` | event taxonomy | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `30_offline_guard.md` | offline guard | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `31_d_ladder_complete.md` | decision ladder | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `32_evidence_pack_templates.md` | evidence templates | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `33_council_hybrid.md` | model council | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `34_llm_pool_routing.md` | LLM routing | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `35_cockpit_project_hub.md` | project hub | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `40_setup_step_by_step.md` | setup | DONE_SYNC | aktywne start docs wskazuja unified runtime |
| `41_environment_variables.md` | env vars | DONE_SYNC | `SYLION_DB_PATH` jest runtime DB source of truth |
| `42_configuration_files.md` | config files | DONE_SYNC | legacy dashboard traktowany jako removed |
| `43_ai_models_config.md` | AI models | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `44_idea_vault.md` | idea vault | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `45_mobile_app.md` | mobile app | DONE_SYNC | PARTIAL/PLANNED: web/mobile gateway istnieje, natywna app nie jest pelna |
| `46_w14_ontology.md` | W14 ontology | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `47_w14_charter_finding.md` | W14 charter/finding | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `48_w14_human_lab.md` | W14 human lab | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `49_w14_test_center.md` | W14 test center | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `50_w14_demo_projects.md` | W14 demo projects | DONE_SYNC | status dokumentacyjny zsynchronizowany |
| `51_w14_agent_team_theater.md` | W14 agent theater | DONE_SYNC | status dokumentacyjny zsynchronizowany |

## 4. Nowe endpointy i surfaces dopisane w P3-004

| Typ | Identyfikator | Dokumentacja |
|---|---|---|
| API | `GET /api/v1/funding/application/{application_id}/export/{artifact_type}` | `modules/07_funding.md`, system book |
| API | `GET /api/v1/funding/reports/executive` | `modules/07_funding.md`, manual |
| UI | `/funding` -> zakladka `Raporty` | index, manual, funding module |
| UI | `FundingReportingPanel` | funding module |
| Artefakty | PDF/CSV/XLSX funding reports | funding module, manual |

## 5. Evidence uzyte do sync

- `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/r3_13_cleanup_summary.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/runtime_api_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/playwright_reporting_smoke.json`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/funding_reporting_desktop.png`
- `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/funding_reporting_mobile.png`
