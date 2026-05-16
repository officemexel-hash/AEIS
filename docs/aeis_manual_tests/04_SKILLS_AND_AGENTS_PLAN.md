# AEIS Skills And Agents Plan

Status: draft

## Execution Rule

Agents are not launched during planning. They are launched only when the execution phase starts and only for concrete bounded tasks. Skills are loaded when their audit area begins.

## Skills To Load For The Procedure

These skills already exist locally and must be used during the relevant phase.

| Skill | When To Use | Purpose |
|---|---|---|
| `aeis-module-inventory-auditor` | Checkpoints 4-5 | Build module census from code, routes, contracts, skills, prompts, addons, and legacy surfaces. |
| `aeis-api-ui-coverage-auditor` | Checkpoint 5 | Map Dashboard routes to API references and runtime coverage. |
| `aeis-runtime-evidence-auditor` | Runtime verification and project simulations | Verify actual runtime truth through process startup, OpenAPI, routes, logs, tests, and screenshots. |
| `aeis-governance-council-auditor` | Human Gate and Council tests | Audit Human Gate, governance, decision ladder, council workflows, model roles, and approval integration. |
| `aeis-canon-drift-writer` | After each project and final report | Compare code/runtime reality against canon and record drift. |
| `aeis-cross-audit-diff-auditor` | After manual and AEIS self-test reports | Compare our results with other audit findings and flag disagreements. |
| `aeis-system-book-writer` | Final synthesis only | Write or update final system-book style synthesis after evidence stabilizes. |
| `dashboard-implementation` | Repair phase for Dashboard defects | Use when fixing operator console, Dashboard panels, Human Gate UI, artifact control, process canvas, readiness, or replay. |
| `decision-classifier` | Human Gate and external action decisions | Classify D0-D5 decisions and identify which decisions require approval evidence. |
| `evidence-pack-writer` | D3+ and external-action gates | Create evidence packs for high-impact decisions. |
| `gate-check-runner` | Guard and release-gate validation | Run entry/exit gate checklists for lifecycle transitions. |
| `code-bloat-detector` | Repair phase | Check risky repaired modules for bloat and complexity. |
| `efficiency-audit` | P4/P5 resource profile tests | Audit performance, memory, cost, and bloat impacts. |
| `skill-registry-implementer` | If Skills Registry is broken | Repair or extend registry behavior. |
| `skill-executor-implementer` | If Skills Runtime is broken | Repair or extend sandbox execution, timeout, result capture. |
| `skill-yaml-validator` | If AEIS creates or edits skills | Validate skill manifests. |
| `contract-test-writer` | Repair verification | Add focused integration tests for contract compliance. |
| `golden-set-writer` | Regression sets | Build small golden tests for critical contracts. |
| `browser-use:browser` | Manual Dashboard execution | Click through local Dashboard and capture browser evidence. |
| `playwright` | Browser automation verification | Run scripted browser checks/screenshots when needed. |

## Missing Procedure Skills To Create Or Emulate

These do not currently exist as dedicated local skills. During planning they are roles/checklists; during execution we can either create them as Codex skills or perform them manually with the agents below.

| Needed Skill | Purpose | Create Before Execution? |
|---|---|---|
| `aeis-stop-fix-restart-controller` | Enforce blocker stop, repair, restart-from-beginning discipline. | Recommended |
| `aeis-product-artifact-tester` | Test generated products from P1-P5 as real local apps. | Recommended |
| `aeis-guards-matrix-runner` | Drive guard bad-condition tests and recovery checks. | Recommended |
| `aeis-funding-flow-tester` | Execute funding criteria without external submit. | Recommended |
| `aeis-skills-adaptivity-auditor` | Check skill detection, creation, execution, and reuse. | Recommended |
| `aeis-cost-time-resource-auditor` | Check cheap/slow, balanced, fast/expensive profile effects. | Recommended |
| `aeis-memory-reuse-auditor` | Check memory write, retrieval, and reuse from P1-P4 in P5. | Recommended |
| `aeis-test-center-auditor` | Test AEIS Test Center and release gates. | Recommended |
| `aeis-report-ledger-writer` | Keep Obsidian/Markdown ledger, evidence, and final report aligned. | Recommended |

## Test Roles

| Role | Responsibility |
|---|---|
| Lead Operator | Runs Dashboard steps in order and does not skip checklist items. |
| Evidence Reporter | Records screenshots, IDs, API responses, logs, artifact paths, and memory evidence. |
| QA Sentinel | Enforces Stop-Fix-Restart and rejects unsupported PASS claims. |
| Repair Engineer | Fixes blockers and runs focused verification. |
| Architecture Auditor | Classifies surfaces and modules after evidence is collected. |

## Agents To Launch During Execution

When execution starts, the main thread remains `Lead Operator`. Sub-agents are launched only for bounded parallel work.

| Agent | Type | Launch Time | Responsibilities | Must Not Do |
|---|---|---|---|---|
| Evidence Reporter | worker | Before Checkpoint 4 | Maintain `03_TEST_RUN_LEDGER.md`, evidence paths, screenshots list, API/log IDs, project IDs. | Must not mark PASS without evidence. |
| QA Sentinel | explorer/worker | Before first simulation | Enforce Stop-Fix-Restart, verify every checkpoint, flag shortcuts, review whether mock/stub/fallback requires restart. | Must not repair code directly unless reassigned. |
| Dashboard Inventory Agent | explorer | Checkpoint 4 | Inventory Dashboard routes, buttons, forms, risky fallback markers. | Must not change files. |
| API/Module Mapper | explorer | Checkpoint 5 | Map UI routes to API families and backend modules. | Must not infer LIVE without runtime evidence. |
| Runtime Evidence Agent | explorer/worker | During simulations | Collect health/OpenAPI/log/test/runtime evidence and classify `LIVE/PARTIAL/BROKEN`. | Must not hide flaky or contradictory results. |
| Product Artifact Tester | worker | After each local build | Open/test generated product, validate forms, buttons, placeholder risk, product-specific flow. | Must not treat artifact existence as product pass. |
| Guards Tester | worker | During P2/P4/P5 and Test Center | Trigger bad conditions for cost, security, external action, provenance, quality, coherence, Human Gate, no-mock, truth alignment. | Must not perform real external actions. |
| Funding Tester | worker | P2 and P5 | Test funding intake, scoring, documents, approvals, blocked submit, audit trail. | Must not submit externally. |
| Skills Adaptivity Tester | worker | Every project, deeper in P4/P5 | Check skill selection, missing skill detection, draft creation, execution, result integration, reuse. | Must not accept registry-only evidence as execution. |
| Memory Auditor | explorer/worker | After each project and P5 | Verify memory writes, retrieval, and reuse across simulations. | Must not use Obsidian notes as substitute for AEIS memory. |
| Provider/Budget Sentinel | explorer/worker | Before model-provider or Hetzner checks | Verify subscription-first provider policy, key-entry pause, cost caps, and secret redaction. | Must not request permanent secrets or print keys. |
| Repair Engineer | worker | Only after blocker | Make scoped fixes, run focused tests, report files changed. | Must not continue simulation after a blocker without retest from start. |
| Final Report Writer | worker | After self-test | Synthesize final report from ledger, evidence, findings, repair log, and AEIS self-test comparison. | Must not invent evidence. |

## External / Local Model Helpers

Local models, Kimi, and Claude Code may be used as reviewers in these roles:

- second-opinion reviewer for Council/Human Gate findings,
- report consistency checker,
- mock/stub risk reviewer,
- repair proposal reviewer,
- final report critique.

They do not decide PASS/FAIL. PASS/FAIL is decided only from evidence collected in Dashboard, API, runtime, logs, artifacts, memory, Test Center, and tests.

## Allowed Helpers

Local models, Kimi, and Claude Code may be used as helper reviewers or reporting agents. Final status must be based on UI/API/runtime/log/artifact/memory evidence, not model opinion.

## Skills To Test Inside AEIS

| Skill Capability | Required Evidence |
|---|---|
| Existing skill selection | AEIS selects a relevant existing skill for a project need. |
| Missing skill detection | AEIS records that a required skill is absent. |
| Draft skill creation | AEIS creates or proposes a draft skill when needed. |
| Skill execution | Skill runs and returns a result. |
| Skill result integration | Result appears in project, artifact, log, memory, or audit trail. |
| Skill reuse | Skill or learned need is reused in a later project. |
| Skill failure handling | Broken skill produces controlled error, retry/timeout evidence, and audit entry. |

## Skill Status Criteria

- `LIVE_ADAPTIVE`: detects need, creates/selects skill, executes it, and reuses it later.
- `LIVE`: executes correctly but without adaptive creation.
- `PARTIAL`: registry or runtime works, but integration is incomplete.
- `SHELL`: UI/registry exists without real execution.
- `BROKEN`: execution fails or blocks project flow.
