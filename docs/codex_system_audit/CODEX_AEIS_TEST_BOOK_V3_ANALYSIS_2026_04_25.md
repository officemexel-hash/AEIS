# CODEX AEIS Test Book V3 Analysis - 2026-04-25

## Source

- PDF: `C:\Users\razor\Downloads\AEIS_KSIEGA_TESTOW_SCALONA_V3_2026.pdf`
- Extracted text: `output/aeis_audit/AEIS_KSIEGA_TESTOW_SCALONA_V3_2026_extract.txt`
- Extracted index: `output/aeis_audit/AEIS_TEST_BOOK_V3_INDEX.json`
- PDF pages: `14`

## What The New Test Book Adds

The V3 test book is not a simple UI click list. It defines AEIS production-readiness as a controlled-autonomy behavior test:

- The truth order is `code -> runtime -> API -> UI -> tests -> documentation`.
- Human Gate starts at idea intake, not only at final submit/deploy.
- A PASS requires evidence: JSON, screenshot, logs, API response, DB/audit record, or test output.
- Every failure must enter the R0-R9 loop: detect, reproduce, classify, patch, retest, evidence, learning, gate.
- Production readiness is vetoed by unresolved P0/P1, Human Gate bypass, external/final action without approval, split truth plane, missing audit, or `/idea-vault` crash.

## Test Taxonomy

The book defines these core axes:

- Severity: `P0-P4`.
- Decision risk: `D0-D5`.
- Autonomy mode: `A0-A5`.
- Human Gate types: `blocking`, `non_blocking`, `batch`, `emergency`, `financial`, `legal`, `production`, `security`, `external_action`, `final`.
- Global checkpoints: `C1-C20`.
- Repair loop: `R0-R9`.
- Human-like flows: `S0-S18`.
- Base 500 scenario families: `SMOKE`, `CODE`, `API`, `UI`, `IDEA`, `COUNCIL`, `PLAN`, `SKILL`, `MEM`, `WORKER`, `MOBILE`, `FUND`, `SEC`, `OBS`, `CHAOS`, `REPAIR`, `E2E`.

## V3 Extension Index

The PDF says the V3 extension adds 240 new scenarios, but the visible extracted appendix contains 220 unique V3 IDs:

- `V3-IDEAVAULT`: 20 planned, extraction found 22 ID mentions because some IDs repeat in references.
- `V3-ROUTE`: 20.
- `V3-HG-BYPASS`: 20.
- `V3-LLM`: 20.
- `V3-UXA`: 20.
- `V3-DATA`: 20.
- `V3-ART`: 20.
- `V3-COST`: 20.
- `V3-OBS`: 20.
- `V3-PERF`: 20.
- `V3-LAB`: 20.
- `V3-SELF`: 20.

Audit note: the `240` claim needs source reconciliation. Runtime planning should treat the extracted 220 IDs as the executable appendix until the missing 20 are identified.

## Current Coverage After Latest Repairs

Already covered with runtime evidence:

- `S0` route smoke: `67/67` dashboard routes render without critical errors.
- `S1` Idea Vault intake: P0 runner confirms create/persist behavior through UI.
- `S7` Human Gate production path: P0 runner confirms production deploy is blocked, approved, then allowed with ticket.
- `S10` Funding flow: core runner proves API E2E including final submit blocked until Human Gate approval.
- `S11` Operator console partial: `/agents` now proves runtime fleet visibility in P0.
- `S13` Memory runtime surface: core runner proves project memory endpoint/surface.
- `S14` Skills runtime surface: core runner proves project skill bindings endpoint/surface.
- `S15` Audit trail surface: core runner proves unified audit surface.
- `V3-ROUTE-001/002`: mostly covered by route discovery/crawl.
- `V3-ROUTE-006`: partially covered indirectly by API negative tests, but not across all core endpoints.
- `V3-COST` foundation: model budget API/dashboard contract repaired and tested.
- `V3-PERF` lock class: route crawl plus post-crawl Idea Vault write now proves no route-induced SQLite write lock.

Latest evidence baseline:

- Route crawl: `output/aeis_audit/route_crawl_regression_1777137170220.json`, `67/67 PASS`.
- P0 runner: `output/aeis_audit/functional_p0_1777137245522.json`, technical `4 PASS`, system `4 PASS`.
- Core runner: `output/aeis_audit/functional_core_layers_1777137260370.json`, technical `8 PASS`, system `7 PASS`, `1 PARTIAL`.
- Test Book V3 P0 runner after governance hardening: `output/aeis_audit/testbook_v3_p0_1777138478582.json`, technical `13 PASS`, system `13 PASS`.
- Test Book V3 governance/bypass runner after repair: `output/aeis_audit/testbook_v3_governance_1777138466635.json`, technical `9 PASS`, system `9 PASS`.
- Focused pytest after V3 P0 + governance repair: `270 passed`, `6 warnings`.

## Major Coverage Gaps

- `V3-IDEAVAULT-004..020`: empty/long/ambiguous ideas, production intent from intake, PII/payment classification, trash/restore/abandon/hard-delete lifecycle, duplicate detection, cross-user delete protection, deep link to idea, and Idea -> Council transition are not fully automated yet.
- `V3-HG-BYPASS-001..020`: wrong-project ticket use, missing reason validation, reject ignored by worker, double approve idempotency, approve/reject race, mobile unbound approval, cost split attack, VPS expansion, production alias detection, browser external submit, legal signing, delegation scope, timeout escalation, withdrawn final gate, and D5 two-operator policy still need explicit tests.
- `V3-LLM-001..020`: model outage, council disagreement, prompt injection, cost/security sentinel behavior, critic signature, weighted vote math, historical accuracy weighting, hallucinated endpoint verification, council retry versioning, role multiplexing, and strategic escalation are not fully proven with real models.
- `V3-UXA-001..020`: operator next action, risk explanation, draft/approved distinction, actionable errors, keyboard navigation, screen reader labels, mobile viewport, localization, reject reason, cost/runtime clarity, evidence discoverability, and dead-end prevention need browser/a11y tests.
- `V3-DATA-001..020`: orphan gates/artifacts, migration rollback, audit hash tamper, artifact non-null, lifecycle state machine, privacy/redaction, retention/legal hold, unique IDs under load, memory boundaries, DB unavailable, event bus loss, path traversal, idempotency, schema drift, soft-delete visibility, and evidence hash verification need DB/API tests.
- `V3-ART-001..020`: SoT/masterplan exports, PDF/DOCX/XLSX generation, OpenAPI/proto artifacts, artifact diff/versioning, final immutability, download integrity, privacy redaction, funding docs versioning, screenshot evidence, null artifact prevention, storage failure, external publish gate, traceability, hallucinated file paths, audit export, and system book generation need artifact tests.
- `V3-COST-001..020`: financial thresholds, currency conversion, per-run model cost, VPS thresholds, cost cap enforcement, split-cost aggregation, unpriced action warning, budget change audit, funding cost plan, production cost estimate, emergency spending, cost UI consistency, ledger export, and cost memory learning need explicit governance tests.
- `V3-OBS-001..020`: health components, metrics, trace correlation, incident creation, P0 alerting, log redaction, observability panel truth, audit/log consistency, heartbeat, timeout, error budget, evidence dashboard, recovery status, mobile alert routing, portal errors, memory index corruption, repair ledger visibility, and readiness rollup need observability tests.
- `V3-PERF-001..020`: concurrent ideas/projects, parallel workers, blocked-branch continuation, approval storm, memory query scale, long council, browser latency, large artifacts, cold start, restart mid-run, duplicate events, pagination, search filters, approve/reject race, memory write contention, worker reconcile, websocket freshness, and perf regression evidence need load/chaos tests.
- `V3-LAB-001..020`: lab opt-in, device/container/VPS/SDR gates, lab labeling, failure recovery, external integration errors, browser no-submit, cleanup, access control, artifact deployer, remote worker continuity, lab memory boundary, safety checklist, rollback, network action monitoring, real-device audit, and lab documentation drift need isolated LAB tests.
- `V3-SELF-001..020`: full inventory, canon-vs-reality, backlog generation, auto-repair, no split-plane repair policy, no test deletion, root-cause learning, related-surface retest, evidence pack, regression coordination, readiness verdict, system book update, model prompt package, previous-book comparison, post-repair drift, operator acceptance retest, and memory-improves-second-audit need final audit automation.

## Next Runner Plan

Create a new runner set under `output/aeis_audit/`:

- `run_testbook_v3_p0.cjs`: implemented. Current result is `13/13 technical PASS`, `13/13 system PASS`.
- `run_testbook_v3_governance.cjs`: implemented initial bypass/council subset. Current result is `9/9 technical PASS`, `9/9 system PASS`.
- `run_testbook_v3_data_artifacts.cjs`: `V3-DATA`, `V3-ART`, evidence pack and artifact integrity tests.
- `run_testbook_v3_perf_chaos.cjs`: concurrent ideas, route crawl under write load, ticket race, memory contention, restart mid-run.
- `run_testbook_v3_operator_browser.cjs`: UX/a11y/mobile viewport/operator clarity tests.
- `run_testbook_v3_outputs.cjs`: creates at least 10 different project outputs/programs and verifies artifact/delete/archive flows.

## Recommended Immediate Next Wave

1. Expand Idea Vault tests from the P0 subset into the remaining V3 cases: ambiguous idea, production intent, PII/payment classification, trash/restore/abandon/hard-delete, duplicate detection, cross-user delete protection, deep link, and Idea -> Council transition.
2. Extend `run_testbook_v3_governance.cjs` into the remaining bypass cases: reject ignored by worker, approve/reject race, mobile unbound approval, cost split attack, withdrawn final gate, and D5 two-operator policy if adopted as strict canon.
3. Extend cost tests from numeric thresholds into real currency normalization: `25 EUR`, monthly `100 EUR`, exchange-rate handling, split-cost aggregation, unpriced action warning, and budget-ledger export.
4. Implement route-crawl-under-write-load instead of only post-crawl write health.
5. Add first output-production test pack: 10 project types, artifact non-null, delete/archive/trash behavior, and audit evidence.

## Current Verdict Against Test Book V3

The latest runtime baseline is significantly better than before the repair:

- Dashboard stability is `PASS`.
- P0 human-like flow is `PASS`.
- Core AEIS layers are mostly `PASS`.
- One known core item remains `PARTIAL`: canonical/domain route probe because some canonical pages are still bridge pages rather than full control planes.

Against the full V3 book, the system is not yet `PRODUCTION READY` because most bypass, data-retention, artifact, performance, lab, and self-repair tests are not yet executed. The right current classification is `STAGING CANDIDATE AFTER P0 PASS`, pending the next V3 runner wave.
