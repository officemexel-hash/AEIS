# v2 Cron Integration Log - 2026-04-27

Curation pass over local-model output in `docs/v2/_drafts/`.
Operator decision (Robert): multi-model routing per ADR-002. The drafts here
are a mix of production-ready and incomplete. This log records what was
extracted, what was skipped, and why.

## Outputs (3 atomic commits)

### Commit 1 - `[v2 cron] docs: add ontology demo manifests`
**Target:** `src/sylion-pipeline/sylion/aeis_v2/ontology/manifests/_demos/`

| Source | New file | Notes |
|--------|----------|-------|
| `ollama_batch/05_customer_demos.yaml` | `customer_demos.yaml` | Stripped "Thinking..." preamble, kept 5 valid YAML docs. PyYAML parse OK. |
| `ollama_batch/batch_B/13_project_demos.yaml` | `project_demos.yaml` | Same; 5 docs OK. |
| `ollama_batch/batch_B/14_vehicle_demos.yaml` | `vehicle_demos.yaml` | Same; 17-char VINs preserved. |
| `ollama_batch/batch_C/c1_idea_demos.yaml` | `idea_demos.yaml` | Stripped markdown code fences, used `>-` block scalars for long descriptions. |
| `ollama_batch/batch_E/e6_school_manifests.yaml` | `school_domain_types.yaml` | These are TYPE definitions (not row instances) - kept as tutorial/reference, with header explaining they aren't loaded into prod registry. |
| (synthesized) | `README.md` | Explains what `_demos/` is and isn't; links to ADR-001/ADR-002. |

### Commit 2 - `[v2 cron] docs: add operator guide (FAQ, glossary, tooltips, sidebar)`
**Target:** `docs/v2/operator_guide/` (new directory)

| Source | New file | Notes |
|--------|----------|-------|
| `ollama_batch/06_sylion_faq.md` | `FAQ.md` | 5 PL Q&A; rewrote with explicit ADR-001/ADR-002 references; cleaned formatting. |
| `ollama_batch/batch_D/d3_tooltips.md` + `batch_E/e5_dashboard_help.md` + `batch_B/16_error_messages.md` | `tooltips.md` | Combined: module tooltips + status dot semantics + short error-code reference. |
| `ollama_batch/batch_D/d8_help_blocks.md` + `batch_C/c8_breaker_help.md` | `glossary.md` | 7 PL help blocks (manifest YAML, OSDK Python, JSONB, circuit breaker, cost ledger, federation node, routing decision); circuit-breaker block expanded with CLOSED/OPEN/HALF_OPEN states from c8. |
| `ollama_batch/batch_G/g8_sidebar_descriptions.md` | `sidebar_overview.md` | 6 page descriptions (4-sentence each); explicit "PARKED (ADR-001)" note on Policy Plane (W19). |

### Commit 3 - `[v2 cron] docs: relocate kimi reviews to round-2 archive`
**Target:** `docs/v2/reviews/_kimi_round2/`

| Source | New file |
|--------|----------|
| `_drafts/kimi_batch/k1_v2_applier_review.md` | `_kimi_round2/k1_applier_review.md` (`_v2` suffix dropped) |
| `_drafts/kimi_batch/k2_v2_compiler_sec.md` | `_kimi_round2/k2_compiler_sec.md` |
| `_drafts/kimi_batch/k4_rate_limit_review.md` | `_kimi_round2/k4_rate_limit_review.md` |
| `_drafts/kimi_batch/k5_breaker_thread_review.md` | `_kimi_round2/k5_breaker_thread_review.md` |
| `_drafts/kimi_batch/round3/k6_manifest_input_review.md` | `_kimi_round2/k6_manifest_input_review.md` |
| `_drafts/kimi_batch/round3/k7_migration_perf.md` | `_kimi_round2/k7_migration_perf.md` |
| `_drafts/kimi_batch/round3/k8_sessions_errors.md` | `_kimi_round2/k8_sessions_errors.md` |
| `_drafts/kimi_batch/round3/k9_cost_ledger_testability.md` | `_kimi_round2/k9_cost_ledger_testability.md` |
| `_drafts/kimi_batch/round3/k10_stream_thread_safety.md` | `_kimi_round2/k10_stream_thread_safety.md` |

## Skipped (left in `_drafts/`)

### Skipped because content is just "Thinking..." preamble or error stub

| Path | Reason |
|------|--------|
| `kimi_batch/k1_applier_review.md` (243 B) | CLI error stub: "Option '-p' requires an argument." |
| `kimi_batch/k2_compiler_security.md` (243 B) | Same CLI error stub. |
| `kimi_batch/k3_federation_bugs.md` (243 B) | Same CLI error stub. |
| `kimi_batch/k3_v2_federation_bugs.md` (238 B) | WinError 5 file-permission failure. |
| `ollama_batch/batch_G/g2_lineage_explainer.md` (0 B) | Empty - generation in flight. |
| `ollama_batch/batch_G/g4_add_type_tutorial.md` (0 B) | Empty. |
| `ollama_batch/batch_G/g5_mv_queries.sql` (0 B) | Empty. |
| `ollama_batch/batch_G/g6_commit_msgs.md` (0 B) | Empty. |
| `ollama_batch/batch_G/g7_decision_gates.md` (0 B) | Empty. |
| `ollama_batch/batch_G/g9_error_responses.json` (0 B) | Empty. |
| `ollama_batch/batch_G/g10_risk_categories.md` (0 B) | Empty. |

> Future cron rounds: when batch G completes, re-run curation - several entries (lineage_explainer, add_type_tutorial, decision_gates, risk_categories) are obvious targets for `operator_guide/`.

### Skipped because lower-priority test stubs / code samples (per brief)

These are kept in `_drafts/` for reference but not promoted to production this round:

- `ollama_batch/01_cost_ledger_tests.md` - test stubs, brief said skip.
- `ollama_batch/02_federation_tests.md` - same.
- `ollama_batch/04_retry_review.md` - review of existing code, not a doc.
- `ollama_batch/07_cost_ledger_pl_comments.md` - PL comments for code, would require touching `src/`.
- `ollama_batch/10_federation_adversarial.md` - adversarial review, kept as reference.
- `ollama_batch/batch_B/11_session_tests.md` - test stubs.
- `ollama_batch/batch_B/12_adapter_bus_review.md` - review.
- `ollama_batch/batch_B/15_task_descriptions.md` - PL strings; not yet tied to a UI key map.
- `ollama_batch/batch_B/17_role_description.md` - single role, integrate later when role catalog is finalized.
- `ollama_batch/batch_B/18_openapi_match.yaml` - needs cross-check with real OpenAPI spec.
- `ollama_batch/batch_B/19_hybrid_module_doc.md` - module doc, would need to land in actual module dir; deferred.
- `ollama_batch/batch_B/20_apps_v2_edge_tests.md` - tests, skip.
- `ollama_batch/batch_C/c2_polish_chars_test.md` - test stub.
- `ollama_batch/batch_C/c3_policy_v2_docstring.md` - W19 PARKED per ADR-001.
- `ollama_batch/batch_C/c4_cost_samples.json` - sample data; defer until cost-ledger schema is locked.
- `ollama_batch/batch_C/c5_sessions_review.md` - review.
- `ollama_batch/batch_C/c6_routing_samples.json` - integrate once ADR-002 routing test harness exists.
- `ollama_batch/batch_C/c7_rbac_roles.yaml` - needs alignment with W7 role catalog before promotion.
- `ollama_batch/batch_C/c9_adapter_stats_tests.md` - tests.
- `ollama_batch/batch_C/c10_aeis_v2_readme.md` - candidate for top-level README; defer until ADR-002 lands stably.
- `ollama_batch/batch_D/d1_task_samples.yaml` - sample tasks, defer.
- `ollama_batch/batch_D/d2_frontend_readme.md` - frontend doc; deferred (lives outside this repo's scope this round).
- `ollama_batch/batch_D/d4_changelog.md` - generated changelog; main agent owns _cron_log.md.
- `ollama_batch/batch_D/d5_commit_templates.md` - commit-msg templates; not part of CI yet.
- `ollama_batch/batch_D/d6_advisor_pattern.md` - long architectural essay; cross-check with charters.
- `ollama_batch/batch_D/d7_sample_queries.sql` - SQL samples; defer.
- `ollama_batch/batch_D/d9_reap_tests.md` - tests.
- `ollama_batch/batch_D/d10_blog_federation.md` - blog post; out of scope.
- `ollama_batch/batch_E/e1_terminal_requests.json` - sample data, defer.
- `ollama_batch/batch_E/e2_terminal_events.json` - same.
- `ollama_batch/batch_E/e3_apptemplate_tests.md` - tests.
- `ollama_batch/batch_E/e4_routing_decisions.json` - sample data; defer until routing harness lands.
- `ollama_batch/batch_E/e7_extension_strict_tests.md` - tests.
- `ollama_batch/batch_E/e8_migration_doc.md` - migration doc; superseded by `docs/v2/migration/`.
- `ollama_batch/batch_E/e9_csv_headers.csv` - CSV headers; defer.
- `ollama_batch/batch_E/e10_user_persona.md` - operator persona; useful for charters, defer.
- `ollama_batch/batch_F/f*` (10 files) - new batch, mix of test stubs / sample data / metric docs; revisit next round.
- `codex_batch/p*.md` and `round3/p*.md` - codex code stubs; per brief, skip unless obviously clean.
- `local_models_poc/` - POC artifacts, archive only.

## Provenance & ADR alignment

- All extracted docs link back to `ADR-001` (five architectural decisions) and `ADR-002` (multi-model routing).
- Where W19 is mentioned, the doc is explicit that W19 is **PARKED** per ADR-001.
- All YAML demo files validated with `python -c "import yaml; list(yaml.safe_load_all(...))"` - 5 docs each.

## Sizes

- Before this round: `_drafts/` ~ 50 ollama files + 10 codex + 8 kimi + 2 POC pieces.
- After this round: 8 kimi files relocated to `reviews/_kimi_round2/`. `_drafts/` retains ollama + codex + POC for next cron.

## Next steps for future cron rounds

1. Pick up batch G entries when generation completes (lineage explainer, add-type tutorial, decision gates).
2. Review batch F (f1-f10) - several look promising (SSE samples, DDL samples, decision gate doc, replay endpoint doc).
3. After ADR-002 routing harness lands, promote `c6_routing_samples.json` and `e4_routing_decisions.json` as fixtures.
4. After W7 role catalog stabilises, promote `c7_rbac_roles.yaml` to a real config.
