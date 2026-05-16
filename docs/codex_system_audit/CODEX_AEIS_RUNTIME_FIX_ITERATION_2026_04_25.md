# CODEX AEIS Runtime Fix Iteration - 2026-04-25

## Scope

Ta iteracja objela audyt runtime, szybkie poprawki P0 oraz regresje po poprawkach. Celem bylo sprawdzenie, czy operator moze uzyc dashboardu i podstawowych kanonicznych flow AEIS bez crashy oraz czy pierwsze governance gates nie omijaja Human Gate.

## Runtime setup used

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://localhost:3001`
- Backend test env: `SYLION_RBAC_DISABLED=1`, `SYLION_RATE_LIMIT_DISABLED=1`
- Backend health: `status=ok`, `version=3.5.0`, `modules=90`, `endpoints=1421`, `db_mode=sqlite`

Rate limit zostal wylaczony na czas dashboard crawl, bo szybkie przejscie kilkudziesieciu tras generowalo `429`, ktore przez ordering middleware wychodzilo w przegladarce jako CORS failure. To jest osobny punkt do hardeningu produkcyjnego: odpowiedzi middleware powinny zachowywac CORS headers albo rate-limit powinien miec tryb testowy w oficjalnym start script.

## Fixes completed

- Naprawiono `/idea-vault` crash na `truncate(item.content)`, gdy rekordy backendu nie mialy pola `content`.
- Dopasowano Idea Vault do realnego kontraktu backendu: UI pokazuje `content || description || title`.
- Naprawiono zapis idei: frontend wysylal `priority: 0`, backend oczekiwal stringa, co dawalo `422`.
- Naprawiono fallback pipeline client path: tworzenie runa idzie przez `/api/v1/pipeline/ideas`, a nie nieobslugiwany `POST /api/v1/pipeline/runs`.
- Rozdzielono intake od wykonania: przycisk w Idea Vault zapisuje draft/intake jako `Save Idea` i nie wysyla automatycznie do pipeline.
- Naprawiono hook-order runtime errors w `/agents`, `/decisions`, `/security-scan`.
- Dodano brakujace API client methods i hooks wymagane przez dashboard surfaces.
- Dodano canonical bridge pages dla `/human-gate`, `/model-council`, `/source-of-truth`, `/masterplan`, `/memory`, `/runtime`.
- Naprawiono governance dla `canon/freeze` i `masterplan/freeze`: endpointy tworza unified Human Gate governance ticket, a approval ticketu aplikuje projektowy approval.
- Zmieniono `/human-gate` z canonical bridge na realna kolejke unified governance tickets z filtrem pending/all, metrykami, payload preview oraz akcjami `Approve`/`Reject`.
- Naprawiono frontend API dla unified tickets: lista filtruje po `state`, a resolve wysyla `reviewer/reason` zgodnie z backendem.
- Dodano powtarzalne runnery audytowe:
  - `output/aeis_audit/run_functional_p0.cjs`
  - `output/aeis_audit/run_functional_core_layers.cjs`
  - `output/aeis_audit/run_route_crawl.cjs`

## Latest evidence

- Full dashboard route crawl: `output/aeis_audit/route_crawl_regression_1777125490091.json`
- Result: `66/66 RENDERED_NO_CRITICAL_ERRORS`, `failures=[]`

- P0 functional test: `output/aeis_audit/functional_p0_1777125441344.json`
- Result: `4/4 technical PASS`
- System result: `S1 Idea Vault Intake UI = PASS`, `S7 Human Gate Operator Queue UI = PASS`, remaining P0 surfaces `PARTIAL`

- Core layer functional test: `output/aeis_audit/functional_core_layers_1777125465983.json`
- Result: `8/8 technical PASS`
- System result: `Human Gate Required For Canon/Masterplan Freeze = PASS`

## Important system findings still open

- Model Council is still `PARTIAL`: project council suggestion works and includes roles/weights, but runtime voting, dispute resolution, model-rank policy, and effectiveness memory are not yet proven end-to-end.
- Memory is still `PARTIAL`: APIs respond, but audit has not yet proven adaptive reuse of previous project memory for team scaling, model choice, skill binding, or topology choice.
- Skills are still `PARTIAL`: registry/runtime surfaces respond, but audit has not yet proven automatic skill binding to project modules and effectiveness feedback.
- Funding is still `PARTIAL`: API and UI are live, and fake final submit is rejected, but full grant flow still needs test coverage from company profile through application, approval request, and final gated submit.
- Human Gate UI P0 is now `PASS` for viewing and rejecting unified governance tickets from operator console. It still needs expanded tests for batch, non-blocking, emergency, financial, legal, security, external-action, final gates, and continuation of independent work under a blocked decision.
- Audit trail is still `PARTIAL`: project events and audit surfaces exist, but all strategic actions are not yet proven to be linked into one unified Human Gate + audit chain.

## Next repair targets

- Implement/verify Model Council session flow with roles, ranks, weighted voting, tally, conflict, and Human Gate escalation.
- Expand Human Gate behavior tests across all gate types and blocked-work continuation.
- Add memory learning test: project A completion must influence project B planning.
- Add skills binding test: project type must select skills, attach them to modules, execute or record usage, and store effectiveness.
- Expand funding human-like tests to full flow with approval-gated submission.
- Add official test-mode startup script that sets RBAC/rate-limit/CORS-safe defaults for local audit runs.

## AI Models Control Plane repair - 2026-04-25

Trigger: operator dashboard did not expose a usable control plane for local/external AI models, API keys, live per-model budget, language profile, intelligence depth, access level, and Human Gate approval policy.

Implemented surfaces:

- Added `/ai-models` to the operator sidebar and created `AI Models Control Plane`.
- Providers and Keys: lists external providers, tests provider readiness, stores keys through backend KeyVault, and displays masked key previews only.
- Model Registry: registers local/external models with provider, role, rank, voting weight, context window, fallback model, capabilities, language profile, intelligence depth, access level, and approval policy.
- Budget and Access: shows per-model daily/monthly budget limits, spend bars, language/depth/access badges, approval policy, council role/rank/weight, and fallback.
- Council Routing: configures council member role, rank, voting weight, priority, specialization, and max tokens.
- Local Ollama: detects local Ollama runtime, lists local models, allows registering local models, and tests Ollama chat without API key.

Backend fixes:

- `ai_providers_routes.py`: added `ollama` provider support with `/api/v1/ai-providers/ollama/models`, env/base-url detection, HTTP chat call, CLI fallback for `ollama list`, and no key requirement.
- `key_vault.py`: council member config now persists rank, voting weight, specialization, and max tokens.
- `ai_workspace_routes.py`: council member request accepts the new routing fields.
- `app.py`: model registry, KeyVault, and model budget are initialized against the shared app DB instead of accidental in-memory instances.
- `model_registry.py`, `key_vault.py`, `model_budget.py`: added SQLite `busy_timeout`/connection timeout to avoid `database is locked` during parallel dashboard requests.

Validation evidence:

- Backend health: `status=ok`, `version=3.5.0`, `modules=90`, `endpoints=1422`.
- Frontend route: `http://localhost:3001/ai-models` returned `200`.
- Ollama runtime: `/api/v1/ai-providers/ollama/models` returned `available=true` with local models detected.
- Direct API smoke with browser Origin registered a temporary Ollama model, created daily/monthly budget, and soft-deleted it successfully.
- Playwright UI smoke registered a temporary model through `/ai-models`, verified it in `Budget and Access`, confirmed daily/monthly budget via API, then soft-deleted it.
- UI smoke result: `ok=true`, failed requests `[]`, console messages `[]`.
- Screenshot: `output/aeis_audit/ai_models_panel_ui_budget_access_smoke.png`.
- 2026-04-25 retest: `npx tsc --noEmit --pretty false` in `src/sylion-frontend` passed.
- 2026-04-25 retest: `.env` contains provider key names for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `ZAI_API_KEY`, `PERPLEXITY_API_KEY` plus vault/infra tokens; values were not printed.
- 2026-04-25 retest: browser smoke registered a temporary local `ollama` model through `/ai-models`, configured daily/monthly budget, language profile `polish_primary`, intelligence depth `deep`, access `review_only`, approval policy `always_human_gate`, verified Budget and Access, then removed the temporary model through API cleanup. Result: `ok=true`, failed requests `[]`, console messages `[]`.
- 2026-04-25 retest: browser smoke verified operator-side model removal from `/ai-models`; after clicking `Remove`, the registry returned `404` for the removed temporary model. Result: `ok=true`, failed requests `[]`, console messages `[]`.
- Retest artifacts:
  - `output/aeis_audit/ai_models_control_plane_smoke.json`
  - `output/aeis_audit/ai_models_control_plane_delete_smoke.json`
  - `output/aeis_audit/ai_models_control_plane_smoke.png`

Security note:

- Raw API keys are not rendered back into the dashboard. During local audit, legacy ad-hoc test files were found that contain hardcoded API keys. They should be removed or rewritten to use environment variables before production hardening.

## Model Runtime Policy enforcement - 2026-04-25

Trigger: the operator panel could configure budgets, access levels and approval policies, but runtime model calls still needed a single enforcement point so models could not bypass governance.

Implemented enforcement:

- Added `sylion.cognitive.model_runtime_policy` as the shared preflight and usage-recording layer for model execution.
- Runtime preflight resolves registered model config, access level, approval policy, provider type, and current budget before a call is allowed.
- Blocked calls create a Human Gate request through `ai_model_runtime_policy` instead of silently falling through.
- Budget-exceeded models are blocked before provider execution and create a Human Gate ticket.
- `read_only` and `disabled` models cannot execute runtime calls.
- `review_only` models are limited to review/validation/connectivity-test actions.
- `no_external_actions` blocks external providers.
- `always_human_gate`, `ask_for_external_actions`, `ask_for_architecture_changes`, `ask_for_code_changes`, `ask_for_risky_changes`, and `auto_low_risk_only` are enforced at runtime.
- `ai_providers_routes.py` now runs model preflight before provider tests and records token/cost usage after successful calls.
- `ai_providers_routes.py` blocks registered provider mismatch, so a model registered as `ollama` cannot be invoked through the `openai` provider path.
- `llm_adapter.py` now resolves registered model provider/runtime model, supports KeyVault provider keys, records budget usage, returns blocked calls as `status=blocked`, and emits `llm.call_blocked`.
- `model_budget.py` now persists budget-exceeded alerts created after usage recording.
- `model_router.py` and `llm_adapter.py` now use SQLite busy timeouts and are initialized against the shared app DB at startup.
- The `/ai-models` form now includes `Cost per 1K tokens USD`, and `Budget and Access` shows `Cost / 1K`.
- Added regression tests in `src/sylion-pipeline/tests/test_model_runtime_policy.py`.

Validation evidence:

- `py_compile` passed for `model_runtime_policy.py`, `llm_adapter.py`, `model_router.py`, `model_budget.py`, `ai_providers_routes.py`, and `app.py`.
- `npx tsc --noEmit --pretty false` passed.
- Backend health after restart: `status=ok`, `version=3.5.0`, `endpoints=1422`.
- Policy negative test: registered temporary OpenAI model with `access_level=read_only`; provider test returned HTTP `423` before provider call and created Human Gate request `b32aaa9bdf7f`.
- Budget recording test: registered local `qwen3.5:latest` with `cost_per_1k_tokens_usd=1.0`; Ollama provider test recorded `17` tokens and updated `spent_today` to `0.017`.
- Budget block test: lowering daily budget below current spend caused next provider call to return HTTP `423` and created Human Gate request `89d0709c796b`.
- LLMAdapter runtime test: `/api/v1/cognitive/llm/call` used registered provider `ollama`, provider model `qwen3.5:latest`, returned `status=completed`, and increased `spent_today` from `0.017` to `0.032`.
- LLMAdapter negative test: registered temporary `read_only` model; `/api/v1/cognitive/llm/call` returned `status=blocked` and created Human Gate request `84b4886e1c0c`.
- Provider mismatch test: calling `/api/v1/ai-providers/test/openai` with registered `ollama` model `qwen3.5:latest` returned HTTP `400` with `provider_mismatch`.
- UI smoke after pricing field: `/ai-models` rendered `Cost per 1K tokens USD`, `Cost / 1K`, and local `qwen3.5:latest` without failed requests or console errors.
- Regression tests: `pytest src/sylion-pipeline/tests/test_model_runtime_policy.py -q` => `3 passed`.

Remaining hardening:

- Wire these policy decisions into every future model execution path, especially council voting, autonomous worker execution, funding document generation, and self-repair loops.
- Add idempotency/deduplication for repeated blocked-call Human Gate tickets so one failing action does not spam the queue.
- Add official tests for all approval policies and access levels.
- Add provider-specific pricing presets, while keeping operator-configured pricing as the source of truth.

## Funding Final Submit Human Gate enforcement - 2026-04-25

Trigger: funding governance had a D4 final-submission ticket generator, but runtime submission paths still allowed unsafe ordering: browser automation could click final submit without checking the ticket, and `/api/v1/funding/submission/submit` created the D4 ticket after the logical submit.

Implemented enforcement:

- `FundingAutopilotService.request_approval(...)` now creates a unified governance D4 ticket before final submit and stores `governance_ticket_id` in the funding approval event payload.
- `FundingAutopilotService.submit(...)` now refuses final submit until the linked governance ticket is approved.
- The final submit audit event now includes the approved `governance_ticket_id`.
- `/api/v1/funding/submission/submit` no longer creates a post-factum ticket; it delegates to service-level pre-submit enforcement.
- `FundingFormFiller.run(..., action="submit")` now gates browser automation before login/fill/submit.
- Browser submit without a ticket creates a D4 Human Gate ticket and returns `blocked=true` without touching the portal driver.
- Browser submit with a pending ticket returns `blocked=true` and does not click submit.
- Browser submit with an approved ticket proceeds and records the portal submit reference.

Validation evidence:

- `python -m py_compile` passed for `funding_autopilot/service.py`, `funding_autopilot/routes.py`, and `funding_autopilot/browser_automation.py`.
- `python -m pytest src/sylion-pipeline/tests/funding/test_browser_automation.py src/sylion-pipeline/tests/funding/test_governance_bridge.py -q` => `30 passed`.
- `python -m pytest src/sylion-pipeline/tests/test_funding_autopilot_routes.py -q` => `3 passed`.
- Combined focused regression across model runtime policy, council policy, agent blocking, code-agent blocking, funding browser automation, governance bridge, and funding routes => `40 passed`.

Remaining hardening:

- Connect the real browser automation result back into the Funding service receipt path when production portals are enabled.
- Add UI-level Human-Like Funding Flow test through dashboard: company profile -> call -> project -> application -> approval request -> Human Gate approval -> final submit.
- Add idempotency for repeated funding final-submit approval requests so retries reuse the active ticket where appropriate.

## Project Mode, Freeze Gates, and Production Deploy enforcement - 2026-04-25

Trigger: project mode still had gaps against the canonical AEIS flow. Project creation did not always expose Source of Truth/Masterplan-ready state, freeze endpoints could be treated as direct state changes, generated launch evidence missed module outputs for legacy project payloads, and production deployment/bundle deploy needed a shared Human Gate preflight.

Implemented enforcement:

- `projects_routes.create_project(...)` now returns a structured project envelope with project kind, canonical book, masterplan, canon snapshot, memory policy, worker plan, council plan, execution plan, governance policy, audit plan, pending operator questions, and typed modules.
- Added lightweight intent classification for common project types: application, chat app, dashboard, funding, operator mobile, design tool, and laboratory/device-style work.
- Added default project blueprints so project mode starts from Source of Truth/Masterplan-oriented metadata instead of a bare idea record.
- `canon/freeze` and `masterplan/freeze` now create unified Human Gate governance tickets and only apply the approval after the linked governance ticket is approved.
- `launch_project(...)` now uses `ProjectExecutionEngine.run_project(...)`, returns execution evidence, and preserves blocked/completed status instead of overwriting it with `running`.
- `ProjectExecutionEngine` now emits `module_outputs` into project launch state.
- Added domain build paths for chat apps and room/furniture design tools so generated artifacts are human-testable HTML flows with viewport, registration/login/room/message or canvas/furniture interactions.
- Fixed project-mode build evidence bug where task result generation referenced nonexistent `result.name/result.kind` instead of `task.name/task.kind`.
- UX audit no longer blocks non-UI Python artifacts for missing `viewport`; viewport is enforced only for HTML/UI-like artifacts.
- Added `sylion.governance.deployment_gate` as a shared production target preflight.
- `/api/v1/deployment/deployments` now blocks production-like targets unless an approved production Human Gate ticket is supplied.
- `/api/v1/bundles/deploy` now blocks production-like bundle deploys unless an approved production Human Gate ticket is supplied.
- Approved production deployments store `governance_ticket_id`, `requires_human_gate`, and `production_target` in deployment metadata.
- Test isolation now defaults backend rate limiting off for ordinary test suites and resets `sylion.infra.cache` per test; dedicated rate-limit tests delete the env var and still validate limiter behavior.

Validation evidence:

- `python -m py_compile` passed for `ai_workspace_routes.py`, `projects_routes.py`, `project_mode/engine.py`, deployment gate/routes, bundle routes, and funding files touched in this iteration.
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py src/sylion-pipeline/tests/test_deploy_routes.py -q` => `11 passed`.
- Focused cross-module regression across model runtime policy, council policy, agent policy blocking, funding browser automation, funding governance bridge, funding routes, project routes, and deploy routes => `51 passed`.
- Rate-limit/security regression: `python -m pytest src/sylion-pipeline/tests/api/test_rate_limit.py src/sylion-pipeline/tests/test_fix01_rate_limit_explicit.py src/sylion-pipeline/tests/test_rate_limiter_proxy.py -q` => `43 passed`.
- Deployment pipeline regression: `python -m pytest src/sylion-pipeline/tests/test_deployment_orchestrator.py src/sylion-pipeline/tests/test_bundle_assembler.py -q` => `148 passed`.

Remaining hardening:

- Add UI-level Human-Like Project Mode test through dashboard: idea -> direction approval -> Source of Truth -> masterplan -> freeze approvals -> launch -> deployment gate.
- Add idempotency for repeated canon/masterplan freeze approval requests.
- Expand domain builders beyond chat/design-tool into SaaS, funding, operator mobile, and laboratory/device project families.
- Link project launch module outputs into operator-facing artifact previews and audit trail views.

## Dashboard route regression repair - 2026-04-25

Trigger: post-repair route crawl found two remaining dashboard runtime crashes:

- `/budget`: `TypeError: Cannot read properties of undefined (reading 'toUpperCase')`
- `/costs`: `TypeError: Cannot read properties of undefined (reading 'toFixed')`

Root cause:

- Older cost/budget pages expected the legacy monitoring budget shape: `provider`, `budget_limit`, `spent`, `remaining`, `status`.
- Current canonical model-budget backend returns: `daily_limit`, `monthly_limit`, `spent_today`, `spent_this_month`, `alert_threshold_pct`.
- The pages cast backend records directly instead of normalizing them, so undefined fields reached formatting/status logic.

Implemented repair:

- Added defensive numeric formatting and API-shape normalization to `/budget`.
- Added defensive numeric formatting, budget normalization, transaction normalization, and timestamp normalization to `/costs`.
- Both pages now tolerate legacy monitoring-budget data and canonical model-budget data.

Validation evidence:

- `npx tsc --noEmit --pretty false` in `src/sylion-frontend` passed.
- Route crawl before repair: `65/67 RENDERED_NO_CRITICAL_ERRORS`, failures: `/budget`, `/costs`.
- Route crawl after repair: `67/67 RENDERED_NO_CRITICAL_ERRORS`, failures: `[]`.
- Latest route crawl artifact: `output/aeis_audit/route_crawl_regression_1777132002572.json`.
- P0 functional test after repair: `4/4 technical PASS`; system: `2 PASS`, `2 PARTIAL`.
- Latest P0 artifact: `output/aeis_audit/functional_p0_1777132079136.json`.
- Core layer functional test after repair: `8/8 technical PASS`; system: `1 PASS`, `7 PARTIAL`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777132079150.json`.

Remaining system-level partials:

- Agents Operator Surface: renders technically but does not yet prove full runtime team scaling and council execution.
- Human Gate Production Ticket API: creates/verifies tickets, but wider blocked-work continuation and all gate classes still need coverage.
- Model Council: suggestion works, but full weighted voting, dispute resolution, and effectiveness memory remain partial.
- Memory, Skills, Funding, Audit Trail: runtime surfaces pass, but adaptive reuse, automatic skill binding, full funding flow, and unified audit chain still need deeper tests and/or implementation.

## Project Council ranked/weighted bridge - 2026-04-25

Trigger: Model Council runtime was still partly decorative at the Project Mode boundary. The hybrid council engine already supported canonical roles, ranks, weights, critic signatures, sentinel checks, and weighted consensus, but `/api/v1/projects/{project_id}/council/suggest` generated flat roles such as `lead/sentinel/scribe` without ranks, voting weights, quorum policy, or signature requirements.

Implemented repair:

- Project council suggestions now use canonical roles: `planner`, `architect`, `critic`, `verifier`, `governance`, plus domain-specific roles where needed.
- Each suggested member includes `rank`, `voting_weight`, `responsibility`, `preferred_models`, `required_signature`, and `approval_scope`.
- Suggestion output includes `quorum_policy` with `weighted_majority_with_critic_signature`, `minimum_weight_ratio=0.6`, and `tie_breaker=human_gate`.
- Project store council reconciliation now preserves rank, voting weight, required critic signature, approval scope, preferred models, and responsibility into `project_council_members.config`.
- Added regression test proving Project Mode -> Council Truth Plane reconciliation carries weighted/ranked council metadata.
- Updated `run_functional_core_layers.cjs` to accept the current project creation envelope `{ project }` and record council ranks/weights in evidence.

Validation evidence:

- `python -m py_compile src/sylion-pipeline/sylion/api/projects_routes.py src/sylion-pipeline/sylion/project_mode/store.py` passed.
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py src/sylion-pipeline/tests/test_council_model_policy.py -q` => `8 passed`.
- Focused cross-module regression after council repair => `52 passed`.
- Backend restarted and `/health` returned `status=ok`, `endpoints=1422`.
- Core-layer functional after restart: `8/8 technical PASS`; council details include roles `planner/architect/critic/verifier/governance`, ranks `primary/primary/primary/validation_only/senior`, weights `1/1/1/0.32/0.9`, and quorum policy `weighted_majority_with_critic_signature`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777132424363.json`.
- Latest route crawl after backend restart: `67/67 RENDERED_NO_CRITICAL_ERRORS`, failures `[]`.
- Latest route crawl artifact: `output/aeis_audit/route_crawl_regression_1777132449905.json`.

Remaining hardening:

- Wire Project Council suggestions into an actual per-project deliberation session, not only suggested roster metadata.
- Add runtime voting/tally/weighted consensus test against project change proposals.
- Escalate project council tie/conflict to Human Gate automatically.
- Record model effectiveness after council decisions and feed it into future model/team selection.

## Project Council runtime deliberation bridge - 2026-04-25

Trigger: the project council had ranked/weighted roster metadata, but no project-scoped runtime endpoint that actually opened a council session, collected votes, computed weighted consensus, and escalated risky changes to Human Gate.

Implemented repair:

- Added `POST /api/v1/council/{project_id}/deliberate`.
- The endpoint reads the active project council roster from the model registry truth plane.
- It opens a `CouncilHybrid` session with project context, risk flags, and quorum policy.
- It attaches council participants with canonical roles, ranks, and voting weights.
- It records deterministic role-based analyses and verdicts for each active member.
- It records a critic signature for approve/conditional critic verdicts.
- It computes weighted consensus through `CouncilHybrid.compute_weighted_consensus`.
- It auto-approves only low-risk local changes inside autonomy boundaries.
- It creates a unified `GovernanceTicket(origin="council")` for production, external, final, legal/financial, cost-threshold, VPS-threshold, source-of-truth, masterplan, architecture, tie, weak quorum, missing critic signature, or reject/no-data outcomes.
- It writes a project event: `project.council.deliberation.auto_approved` or `project.council.deliberation.requires_human_gate`.

Validation evidence:

- `python -m py_compile src/sylion-pipeline/sylion/api/council_routes.py` passed.
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py -q` => `8 passed`.
- Focused cross-module regression after council deliberation bridge => `54 passed`.
- Backend restarted and `/health` returned `status=ok`, `endpoints=1423`.
- Runtime smoke through live API passed: low-risk local change => `auto_approved` with no ticket; production change => `requires_human_gate` with `gate_type=production`.
- Runtime smoke artifact: `output/aeis_audit/council_deliberation_smoke_1777140064.json`.
- P0 functional after backend restart: `4/4 technical PASS`; system: `2 PASS`, `2 PARTIAL`.
- Latest P0 artifact: `output/aeis_audit/functional_p0_1777132874256.json`.
- Core-layer functional after backend restart: `8/8 technical PASS`; system: `1 PASS`, `7 PARTIAL`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777132874257.json`.
- Route crawl after backend restart: `67/67 RENDERED_NO_CRITICAL_ERRORS`, failures `[]`.
- Latest route crawl artifact: `output/aeis_audit/route_crawl_regression_1777132893483.json`.

New regression coverage:

- Low-risk local change: council session is created, all members approve, critic signs, consensus is `approve`, no Human Gate ticket is created.
- Production change: council session is created, risk flags include `production_deploy`, result is `requires_human_gate`, decision class is `D5`, gate type is `production`, and a pending unified council ticket is linked to the council session.

Remaining hardening:

- Replace deterministic role analyses with real model calls when models are configured and allowed by model runtime policy.
- Add explicit tie scenario tests and operator resolution flow.
- Feed council outcomes and later human decisions back into model effectiveness memory.
- Surface project council deliberation results in the dashboard's Model Council / Human Gate views.

## Project Memory and Skills runtime binding - 2026-04-25

Trigger: Memory and Skills surfaces existed, but Project Mode did not prove the canonical AEIS behavior where a new project automatically receives skills and similar future projects reuse proven skill patterns.

Implemented repair:

- Added canonical AEIS project skill definitions for planning, source of truth, masterplan, local validation, audit trail, Human Gate policy, chat app auth/messaging, e2e testing, canvas UI, funding scoring/document packaging, mobile approval security, and operator console surfaces.
- Project Mode now assigns `skill_bindings` and `skills` into each module spec during project upsert.
- Default skill binding uses project kind and module name.
- Project Mode now registers these AEIS skills into the Skills Registry as `PUBLISHED` when they are needed.
- Project Mode now performs similarity lookup against existing project records before writing a new project.
- Similar projects are recorded in `memory_policy.similar_projects`.
- Skill reuse is recorded in `memory_policy.reused_skill_ids`.
- Per-module memory confirmations are persisted to `project_skill_reuse_log`.
- Added `GET /api/v1/projects/{project_id}/skills` for operator/API visibility into project skill bindings, memory reuse, and reuse log.

Validation evidence:

- `python -m py_compile src/sylion-pipeline/sylion/project_mode/store.py src/sylion-pipeline/sylion/api/projects_routes.py` passed.
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py -q` => `10 passed`.
- Focused cross-module regression after memory/skills binding => `56 passed`.
- Backend restarted and `/health` returned `status=ok`, `endpoints=1424`.
- Runtime smoke through live API passed: first chat project received default skill bindings; second similar chat project detected the first as similar and wrote skill reuse evidence.
- Runtime smoke artifact: `output/aeis_audit/memory_skills_reuse_smoke_1777140425.json`.
- P0 functional after backend restart: `4/4 technical PASS`; system: `2 PASS`, `2 PARTIAL`.
- Latest P0 artifact: `output/aeis_audit/functional_p0_1777133235577.json`.
- Core-layer functional after backend restart: `8/8 technical PASS`; system: `1 PASS`, `7 PARTIAL`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777133235577.json`.
- Route crawl after backend restart: `67/67 RENDERED_NO_CRITICAL_ERRORS`, failures `[]`.
- Latest route crawl artifact: `output/aeis_audit/route_crawl_regression_1777133255846.json`.

Remaining hardening:

- Feed actual post-execution success/failure scores into skill effectiveness, not only reuse evidence.
- Use skill effectiveness to alter future team sizing and model assignment.
- Surface project-level skill bindings and memory reuse in the dashboard.
- Extend reuse scoring beyond token similarity with embeddings when the memory index is available.

## SQLite busy-timeout hardening and post-lock verification - 2026-04-25

Trigger: running the P0 functional runner and route crawl in parallel exposed intermittent SQLite `database is locked` failures. In the browser this presented as a CORS-style failure on `/api/v1/workspace/ideas`, but the underlying cause was a backend 500 while the SQLite writer was locked.

Implemented repair:

- Added `timeout=30.0` and `PRAGMA busy_timeout = 30000` to SQLite connections used by Idea Vault.
- Added the same busy-timeout policy to unified governance tickets.
- Added the same busy-timeout policy to Funding Autopilot storage.
- Added the same busy-timeout policy to Project Mode storage.
- Added the same busy-timeout policy to Skills Registry storage.
- Kept runner execution sequential for evidence collection so functional failures are not masked by test-runner contention.

Validation evidence:

- `python -m py_compile` passed for:
  - `sylion/cognitive/idea_vault.py`
  - `sylion/governance/ticket.py`
  - `sylion/funding_autopilot/store.py`
  - `sylion/project_mode/store.py`
  - `sylion/skills/registry.py`
- Backend `/health` returned `status=ok`, `version=3.5.0`, `modules=90`, `endpoints=1424`.
- Direct POST with frontend origin to `/api/v1/workspace/ideas` returned `200` and `access-control-allow-origin=http://localhost:3001`.
- P0 functional after busy-timeout repair: `4/4 technical PASS`; system: `2 PASS`, `2 PARTIAL`.
- Latest P0 artifact: `output/aeis_audit/functional_p0_1777133939265.json`.
- Core-layer functional after busy-timeout repair: `8/8 technical PASS`; system: `4 PASS`, `4 PARTIAL`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777133960595.json`.
- Full frontend route crawl after busy-timeout repair: `67/67 RENDERED_NO_CRITICAL_ERRORS`, failures `[]`.
- Latest route crawl artifact: `output/aeis_audit/route_crawl_regression_1777133989458.json`.
- Focused backend regression across model runtime policy, council policy, agent blocking, code-agent blocking, funding browser automation, funding governance bridge, funding routes, project routes, and deploy routes => `56 passed`.

Remaining hardening:

- Add explicit concurrency stress tests for Idea Vault, Human Gate ticket creation, Project Mode, Funding, and Skills Registry.
- Move high-write runtime stores from SQLite toward the configured production database mode before production deployment.
- Ensure unhandled backend 500 responses still pass through CORS middleware and produce operator-readable incident records.

## Unified Audit Trail bridge - 2026-04-25

Trigger: project events, Human Gate tickets, governance chain entries, and the `/audit` dashboard surface were split. Runtime evidence proved that strategic project events existed, but `/api/v1/audit/events` and the `/audit` page did not show one operator-facing chain for project and Human Gate actions.

Implemented repair:

- Backend startup now initializes `AuditTrailAggregator` with the same configured SQLite runtime DB as governance chain and ticket store.
- `AuditTrailAggregator` now uses SQLite busy timeout to avoid the same short-write lock class already fixed in Idea Vault, Project Mode, Funding, Skills, and Governance tickets.
- `TicketStore.submit/resolve/withdraw/escalate` mirrors governance ticket lifecycle events into `/api/v1/audit/events`.
- Project Mode `add_event(...)` mirrors project lifecycle events into both governance audit chain and unified audit trail.
- Added `GET /api/v1/audit/events` so frontend and human-like tests can query audit entries without POST-only query semantics.
- `/audit` now reads unified audit events and summary instead of the deprecated hardened-only log, while chain verification uses `/api/v1/audit/integrity`.
- Added regression proving project creation, canon freeze request, Human Gate ticket submission, ticket resolution, and canon frozen events all appear in unified audit.

Runtime evidence:

- Live smoke: project -> canon freeze request -> Human Gate approval -> canon frozen produced all required unified audit actions.
- Live smoke artifact: `output/aeis_audit/unified_audit_smoke_1777134483972.json`.
- Core-layer functional after audit bridge: `8/8 technical PASS`; system: `5 PASS`, `3 PARTIAL`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777134508205.json`.
- Route crawl after `/audit` change: `67/67 RENDERED_NO_CRITICAL_ERRORS`, failures `[]`.
- Latest route crawl artifact: `output/aeis_audit/route_crawl_regression_1777134529435.json`.
- P0 functional after backend restart: `4/4 technical PASS`; system: `2 PASS`, `2 PARTIAL`.
- Latest P0 artifact: `output/aeis_audit/functional_p0_1777134819435.json`.
- Frontend typecheck: `npx tsc --noEmit --pretty false` passed.
- Focused backend regression after audit bridge => `57 passed`.

Remaining hardening:

- Add unified audit mirrors for model budget changes, AI provider/key changes, and model council effectiveness outcomes.
- Add dashboard filters for source/action/project/ticket and direct navigation from Human Gate tickets to audit entries.
- Add integrity drill that intentionally tampers with a copied audit DB and proves detection without touching production data.

## Funding E2E runtime proof - 2026-04-25

Trigger: Funding Autopilot had broad API coverage and service tests, but the core runtime runner still classified it as `PARTIAL` because it only checked surfaces plus a negative submit for a missing session. The AEIS canon requires proving the whole funding chain, especially final submit blocked by Human Gate.

Runtime proof added:

- Added full Funding E2E flow to the core functional runner:
  - company profile
  - company documents
  - readiness
  - programme
  - call
  - generated idea
  - idea-to-project conversion
  - matching
  - eligibility
  - scoring
  - application creation
  - document readiness
  - application review
  - export package
  - submission prepare/fill/save-draft
  - final-submit approval request
  - blocked submit before Human Gate approval
  - Human Gate ticket approval
  - final submit
  - receipt
- S10 now only returns system `PASS` if the full E2E flow passes and the pre-approval final submit is blocked.

Runtime evidence:

- Standalone live Funding E2E smoke passed.
- Live smoke artifact: `output/aeis_audit/funding_e2e_smoke_1777134953919.json`.
- Core-layer functional after adding Funding E2E: `8/8 technical PASS`; system: `6 PASS`, `2 PARTIAL`.
- Latest core-layer artifact: `output/aeis_audit/functional_core_layers_1777135021477.json`.
- P0 functional after Funding E2E: `4/4 technical PASS`; system: `2 PASS`, `2 PARTIAL`.
- Latest P0 artifact: `output/aeis_audit/functional_p0_1777135042799.json`.

Remaining hardening:

- Add browser-level Funding dashboard E2E: operator creates/inspects the chain from `/funding` rather than direct API only.
- Add idempotency for repeated final-submit approval requests.
- Add direct audit links from funding approval events to Human Gate ticket and unified audit entries.

## Runtime module registration and operator fleet closure - 2026-04-25

Trigger: backend health showed fewer registered modules than manifest inventory, and the `/agents` surface rendered but did not prove live runtime-agent visibility.

Implemented repair:

- `auto_register.py` now resolves manifests in dependency-aware passes instead of one alphabetical pass.
- Added missing manifests for `funding_autopilot.store` and `governance.tickets`.
- Fixed invalid lifecycle value in `funding_autopilot.browser_automation.json`.
- Runtime health now reports `modules=125`, `endpoints=1425`.
- `/agents` now shows a live `Runtime Fleet` backed by runtime-agent APIs instead of only static/operator shell data.
- P0 runner now creates a temporary runtime agent and asserts that the operator surface renders that agent.
- P0 Human Gate production test now uses the real deployment endpoint path: production cutover is blocked, ticket is approved, and redeploy with `approval_ticket_id` succeeds.

Validation evidence:

- Manifest validation: `manifestCount=125`, `missingDependencyCount=0`, `invalidLifecycleCount=0`.
- `python -m pytest src/sylion-pipeline/tests/test_auto_register.py -q` => `12 passed`.
- `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py src/sylion-pipeline/tests/test_deploy_routes.py src/sylion-pipeline/tests/test_auto_register.py -q` => `29 passed`.
- Latest backend health after restart: `status=ok`, `version=3.5.0`, `modules=125`, `endpoints=1425`, `db_mode=sqlite`, `event_mode=sqlite`.
- P0 functional after these repairs: `output/aeis_audit/functional_p0_1777135963545.json`, `4/4 technical PASS`, `4/4 system PASS`.

Remaining hardening:

- Add dashboard controls for runtime-agent lifecycle beyond visibility.
- Connect runtime-agent execution outcomes into project memory and skill-effectiveness scoring.
- Add multi-agent/team-scaling human-like tests that prove AEIS chooses fleet size from project complexity.

## SQLite write-lock root-cause closure - 2026-04-25

Trigger: after a full dashboard route crawl, `/api/v1/workspace/ideas` returned `500 Internal Server Error`. The browser symptom looked like `/idea-vault` instability, but backend logs proved the real cause was a shared SQLite writer lock left open by dashboard read surfaces.

Evidence before repair:

- Full route crawl rendered `67/67` pages, but a direct POST to `/api/v1/workspace/ideas` immediately after crawl returned `500`.
- Backend stderr showed `sqlite3.OperationalError: database is locked` at `sylion/cognitive/idea_vault.py:create_idea`.
- Route-level bisect artifact: `output/aeis_audit/route_lock_bisect_1777136787702.json`.
- Bisect result: `/` and `/agents` kept Idea Vault writes healthy, but `/ai-models` caused the next Idea Vault write to fail.
- Endpoint isolation showed `GET /api/v1/monitoring/budget` was enough to poison the next write.

Root causes:

- `FundingAutopilotService.list_alerts(...)` was a GET/read route but called `store.replace_alerts(...)`, which performed `DELETE/INSERT` during dashboard render.
- `ModelBudgetManager.list_budgets(...)`, `get_budget(...)`, `check_budget(...)`, and `get_budget_summary(...)` may call `_auto_reset_periods(...)`, which performs `UPDATE`. These read APIs did not reliably commit or roll back after the implicit write, leaving SQLite transactions open.
- The monitoring budget router did not fully match the dashboard contract: dashboard used `PUT /budget/{model_id}` and `POST /budget/{model_id}/usage`, while backend primarily exposed body-based routes.
- Budget summary and budget detail responses could expose `inf`, which is invalid JSON under Starlette's strict JSON response encoder.

Implemented repair:

- Funding Alerts GET is now read-only and returns derived runtime alerts without persisting them during dashboard render.
- Model budget read paths now commit after auto-reset side effects and roll back on SQLite errors.
- Monitoring budget API now supports dashboard-native routes:
  - `PUT /api/v1/monitoring/budget/{model_id}`
  - `POST /api/v1/monitoring/budget/{model_id}/usage`
  - `GET /api/v1/monitoring/budget/transactions`
  - `GET /api/v1/monitoring/budget/summary`
- Model budget storage now persists `provider`, `fallback_model_id`, `tokens_in`, `tokens_out`, `task_type`, and `session_id`.
- Budget summaries now expose dashboard fields: `total_budget`, `total_spent`, `total_remaining`, `by_model`, `period_budget`, and `period_spend`.
- API-facing unlimited budget fields use `null` instead of JSON-invalid `Infinity`; internal `check_budget(...)` keeps `float("inf")` for Python logic/tests.
- Monitoring budget route singleton now honors `SYLION_DB_PATH`, which restores persistence and test isolation.

Validation evidence after repair:

- Direct `/ai-models` retest: baseline Idea Vault write returned `200`; `/ai-models` loaded all model-control endpoints; post-`/ai-models` Idea Vault write returned `200`.
- Full dashboard route crawl: `output/aeis_audit/route_crawl_regression_1777137170220.json`.
- Crawl result: `67/67 RENDERED_NO_CRITICAL_ERRORS`, `failures=[]`.
- Direct Idea Vault write immediately after full crawl returned `200`.
- P0 human-like runner: `output/aeis_audit/functional_p0_1777137245522.json`.
- P0 result: `4/4 technical PASS`, `4/4 system PASS`.
- Core-layer runner: `output/aeis_audit/functional_core_layers_1777137260370.json`.
- Core result: `8/8 technical PASS`, system `7 PASS`, `1 PARTIAL`.
- Focused pytest regression:
  - `src/sylion-pipeline/tests/test_projects_routes.py`
  - `src/sylion-pipeline/tests/test_deploy_routes.py`
  - `src/sylion-pipeline/tests/test_auto_register.py`
  - `src/sylion-pipeline/tests/funding/test_browser_automation.py`
  - `src/sylion-pipeline/tests/funding/test_governance_bridge.py`
  - `src/sylion-pipeline/tests/test_funding_autopilot_routes.py`
  - `src/sylion-pipeline/tests/test_audit_trail_aggregator.py`
  - `src/sylion-pipeline/tests/workspace/test_audit_unified.py`
  - `src/sylion-pipeline/tests/test_model_budget.py`
  - `src/sylion-pipeline/tests/test_monitoring_budget_routes.py`
- Focused pytest result: `202 passed`, `6 warnings`.
- Backend stderr after final crawl and functional tests: no new `database is locked`, no new `OperationalError`, no new ASGI traceback.

Current status after this iteration:

- Dashboard route stability: `PASS` for 67 discovered routes.
- `/idea-vault` write after route crawl: `PASS`.
- `/agents` runtime fleet visibility: `PASS` in P0.
- Production deploy Human Gate block/approve path: `PASS` in P0.
- Funding API E2E with final Human Gate: `PASS` in core runner.
- Unified audit runtime surface: `PASS` in core runner.
- Remaining `PARTIAL`: canonical/domain route probe still uses bridge pages for some canonical AEIS domains. This is no longer a crash, but it means some routes are not yet full domain-control planes.

Next repair targets:

- Replace remaining canonical bridge pages with full operator surfaces where needed.
- Expand human-like tests beyond P0/core into the 500-scenario book, including production of at least 10 different application/program outputs and delete/remove flows.
- Add concurrency stress tests that intentionally crawl `/ai-models`, `/funding`, `/audit`, `/idea-vault`, and `/human-gate` while writing ideas, tickets, budgets, and project events.
- Start the next audit pass from the new evidence baseline: route crawl PASS, P0 PASS, core PASS except one known canonical bridge partial.

## Test Book V3 P0 runner and Idea Vault validation closure - 2026-04-25

Trigger: the new `AEIS_KSIEGA_TESTOW_SCALONA_V3_2026.pdf` extends the required human-like/runtime checks. The first executable subset needed to prove that the recent `/idea-vault`, route-crawl, Human Gate, cost, VPS, and low-risk-autonomy repairs survive a stricter V3 test model.

Implemented test automation:

- Added `output/aeis_audit/run_testbook_v3_p0.cjs`.
- Covered V3 scenarios:
  - `V3-IDEAVAULT-001`: `/idea-vault` route renders without critical browser/runtime errors.
  - `V3-IDEAVAULT-002`: normal idea intake creates an IdeaRecord with id, status, and timestamps.
  - `V3-IDEAVAULT-003`: idea persists after UI refresh and API reload.
  - `V3-IDEAVAULT-004`: empty idea must be rejected without HTTP 500 and without creating `"(untitled)"`.
  - `V3-IDEAVAULT-005`: long idea input does not crash backend.
  - `V3-PERF-001`: 10 concurrent Idea Vault writes are stable and unique.
  - `V3-ROUTE-001/002/020`: latest route crawl has no critical failures and does not poison the next Idea Vault write.
  - `V3-HG-BYPASS-013`: production alias `prod` is blocked by Human Gate.
  - `V3-HG-BYPASS-004`: double approval cannot duplicate final action.
  - `V3-COST-001`: single paid action above threshold requires financial Human Gate.
  - `V3-COST-002`: monthly budget above threshold requires Human Gate.
  - `V3-COST-006`: VPS workers above three require Human Gate.
  - `V3-HG-BYPASS-018`: low-risk local draft is auto-approved and does not block on Human Gate.

First runner result before repair:

- Artifact: `output/aeis_audit/testbook_v3_p0_1777137832929.json`.
- Result: `13/13 technical PASS`, `12/13 system PASS`, `1 system FAIL`.
- Failure: `V3-IDEAVAULT-004`.
- Actual behavior: whitespace-only idea returned `200` and created an IdeaRecord titled `"(untitled)"`.
- AEIS impact: false intake records can pollute planning, memory, audit, and later Source of Truth flow.

Implemented repair:

- `POST /api/v1/workspace/ideas` now rejects empty/whitespace-only `content` with `422`.
- `IdeaVault.submit_idea(...)` now also rejects empty/whitespace-only content so non-API callers cannot bypass the validation.
- Workspace `priority` now accepts legacy numeric inputs and normalizes them to strings, preserving older client/test behavior.
- Added regression tests:
  - `test_ai_workspace_routes.py::TestIdeaVault::test_submit_empty_idea_rejected`
  - `test_idea_vault.py::TestCreateIdea::test_submit_workspace_empty_content_rejected`

Validation evidence after repair:

- Re-run artifact: `output/aeis_audit/testbook_v3_p0_1777138053104.json`.
- Re-run result: `13/13 technical PASS`, `13/13 system PASS`.
- Focused regression plus previously closed backend areas:
  - `python -m pytest src/sylion-pipeline/tests/test_projects_routes.py src/sylion-pipeline/tests/test_deploy_routes.py src/sylion-pipeline/tests/test_auto_register.py src/sylion-pipeline/tests/funding/test_browser_automation.py src/sylion-pipeline/tests/funding/test_governance_bridge.py src/sylion-pipeline/tests/test_funding_autopilot_routes.py src/sylion-pipeline/tests/test_audit_trail_aggregator.py src/sylion-pipeline/tests/workspace/test_audit_unified.py src/sylion-pipeline/tests/test_model_budget.py src/sylion-pipeline/tests/test_monitoring_budget_routes.py src/sylion-pipeline/tests/test_ai_workspace_routes.py::TestIdeaVault::test_submit_idea src/sylion-pipeline/tests/test_ai_workspace_routes.py::TestIdeaVault::test_submit_empty_idea_rejected src/sylion-pipeline/tests/test_ai_workspace_routes.py::TestIdeaVault::test_update_idea src/sylion-pipeline/tests/test_idea_vault.py -q`
  - Result: `268 passed`, `6 warnings`.

Known limitation:

- Council cost-threshold runtime fields are currently named `*_usd`; the canon/user threshold is expressed as EUR. The P0 runner validates the numeric governance threshold behavior, but currency normalization/conversion remains a later `V3-COST` runner target.

## Test Book V3 governance/bypass runner and Human Gate hardening - 2026-04-25

Trigger: after the P0 subset passed, the next highest-risk test family was Human Gate bypass and council escalation. These tests verify that Human Gate is not just a queue, but a real runtime control boundary.

Implemented test automation:

- Added `output/aeis_audit/run_testbook_v3_governance.cjs`.
- Covered V3 scenarios:
  - `V3-HG-BYPASS-002`: D3+ ticket approval without `reason` must be rejected.
  - `V3-HG-BYPASS-001`: approved ticket for another action/module cannot authorize production deploy.
  - `V3-HG-BYPASS-003`: rejected ticket cannot authorize production deploy.
  - `V3-HG-BYPASS-014`: external action requires Human Gate.
  - `V3-HG-BYPASS-015`: final action requires final Human Gate.
  - `V3-HG-BYPASS-016`: legal/financial action requires legal D5 Human Gate.
  - `V3-HG-BYPASS-008`: strategic architecture/Source of Truth change requires Human Gate.
  - `V3-LLM-002`: council tie escalates to Human Gate.
  - `V3-LLM-001`: council unavailable/disabled escalates to Human Gate.

First runner result before repair:

- Artifact: `output/aeis_audit/testbook_v3_governance_1777138272479.json`.
- Result: `9/9 technical PASS`, `7/9 system PASS`, `2 system FAIL`.
- Failure 1: `V3-HG-BYPASS-002`; D4 production ticket resolved with `200` despite missing reason.
- Failure 2: `V3-HG-BYPASS-001`; an approved production ticket scoped to another module was accepted by deployment gate, proving the gate checked only `approved` state and not payload scope.

Implemented repair:

- `POST /api/v1/governance/tickets/{ticket_id}/resolve` now rejects `approved`/`rejected` decisions for D3-D5 tickets when `reason` is empty.
- Production deployment gate now validates approved ticket scope:
  - ticket exists
  - ticket state is `approved`
  - ticket `gate_type` is `production`
  - ticket payload `action` matches the attempted action
  - ticket payload target matches the target environment/stage
  - ticket payload identity keys such as `module_id` or `bundle_id` match the attempted resource
- The deployment gate response now includes `ticket_validation_reason` for auditability when a supplied approval ticket is rejected.
- Added regression tests:
  - `test_deploy_routes.py::test_d3_plus_ticket_resolution_requires_reason`
  - `test_deploy_routes.py::test_production_deployment_rejects_approved_ticket_for_other_module`

Validation evidence after repair:

- Governance re-run artifact: `output/aeis_audit/testbook_v3_governance_1777138466635.json`.
- Governance re-run result: `9/9 technical PASS`, `9/9 system PASS`.
- P0 re-run artifact after Human Gate hardening: `output/aeis_audit/testbook_v3_p0_1777138478582.json`.
- P0 re-run result: `13/13 technical PASS`, `13/13 system PASS`.
- Focused regression plus previous closed areas:
  - Result: `270 passed`, `6 warnings`.
- Backend stderr after governance/P0 reruns: no new traceback, no new `OperationalError`, no `database is locked`.

Current status after V3 P0 + governance wave:

- `/idea-vault` intake validation: `PASS`.
- Route crawl/post-crawl write health: `PASS`.
- Production deploy Human Gate: `PASS`.
- Wrong-ticket deployment bypass: `PASS` after repair.
- Missing D3-D5 reason bypass: `PASS` after repair.
- External/final/legal/canon/architecture council escalation: `PASS`.
- Council disabled/tie escalation: `PASS`.

Next governance hardening targets:

- Mobile unbound approval and secure device-binding bypass tests.
- Approve/reject race under concurrency.
- Cost split attack and currency normalization.
- Final-gate withdrawal behavior.
- D5 two-operator policy, if adopted as a strict production rule.
