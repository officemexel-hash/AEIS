# SYLION AEIS — Pełny opis warstw i modułów

> **Stan na:** 2026-04-28
> **Źródła:** `docs/claude_system_audit/CLAUDE_AEIS_CANON_COMPLETE_2026.md`,
> `docs/Ksiega_AEIS_v3_5_full.md`, `docs/plan_15_multi_team.md`,
> `docs/v2/MODULES_INDEX.md`, faktyczny kod w
> `src/sylion-pipeline/sylion/`.

Dokument ma trzy części:

1. **12 warstw kanonicznych (L1–L12)** — fundament logiczny.
2. **15 faz przepływu** — od intake do compact.
3. **Moduły runtime** — co robi każdy katalog/plik w kodzie.

Plus załączniki: klasy decyzji D0–D5, skład Rady (Council), 11-stanowy
lifecycle pomysłu.

---

## CZĘŚĆ I — 12 WARSTW KANONICZNYCH

Warstwy odzwierciedlają logiczny stos AEIS od źródła prawdy do wyjścia.
Każda warstwa to **plan kontraktu**: ma wejścia, wyjścia, audytowalne
zdarzenia, własne metryki.

### **L1 — Canon (Źródło Prawdy)**

**Po co:** Single source of truth — Księga, Masterplan, manifesty
modułów. Każda zmiana wyższych warstw musi być spójna z L1; jeśli nie
jest, otwiera się **ticket dryfu** w L14 audit.

**Składniki:**
- `docs/Ksiega_AEIS_v3_5_full.md` (462 strony specyfikacji)
- `docs/Masterplan_*.md` (priorytetyzacja faz)
- `src/sylion-pipeline/sylion/contracts/manifests/*.json` (kontrakty 132 modułów)
- `aeis_v2/ontology/manifest.py` — runtime walidator manifestów

**Polityka:** żadna zmiana w L1 bez wpisu D4+ z radą 4/4 + Human Gate.

### **L2 — Model Council**

**Po co:** Pełny organ deliberacyjny. Planner proponuje, Critic
kwestionuje, Verifier sprawdza spójność, Sentinels (Cost/Security)
mogą zablokować. Krytyk **musi** podpisać każdą decyzję ≥D3.

**Składniki:**
- `governance/council_hybrid.py` — silnik 9 ról (planner, critic,
  security, legal, finance, governance, qa, red_team, council_chair)
- `aeis_v2/council_v2/` — wedge dla W16 (cascade match → council
  → audit chain) + adaptery LLM (Ollama, scripted dla testów)
- `cognitive/council/voting.py` — sortuje role do tier'ów modeli
  (cheap/deep) na podstawie klasy decyzji

**Audit:** każdy głos i sygnatura krytyka leci do `council_wedge.jsonl`
(hash-chain). 9 verdict typów: `approve`, `conditional`, `reject`,
`tie`, `no_data` × 4 podtypy.

### **L3 — Memory (Pamięć)**

**Po co:** Wszystko co rada „przeczytała", co operator zatwierdził, co
worker wyprodukował — musi być wyszukiwalne, hash-chained,
przywracalne.

**Składniki:**
- `aeis_v2/audit_chain/chain.py` — hash-chained JSONL (`prev_hash` /
  `content` / `content_hash`) z `verify_chain()` i `AuditRotator`
- `cognitive/idea_vault.py` — IdeaVault z 15 statusami i historią
- `aeis_v2/embeddings/` — provider abstraction (Ollama nomic-embed-text)
  + cache hit-rate (`PgEmbeddingCache`)
- `governance/decision_snapshot.py` — point-in-time snapshots stanu
  decyzji
- `aeis_v2/replay_v2/` — `SessionSnapshot` + `ReplayFork` z divergence
  scoring

### **L4 — Skills (Umiejętności)**

**Po co:** Manifest-driven runtime. Każda umiejętność (skill) to
kontrakt + executor + rejestr. Workery się wiążą do skilli przez
`SkillBindings`, nie przez kod.

**Składniki:**
- `core/contract_registry.py` — `ContractRegistry`, bundle assembler
- `contracts/manifests/*.json` — manifesty 132 modułów
- `aeis/skills/` (oryginalne v3.5)
- `aeis_v2/role_match/` — hybrid task→skill matcher (tag overlap +
  embeddings)

### **L5 — Planning**

**Po co:** Z **masterplan** generuje **execution_plan** (per projekt)
i **worker_plan** (per worker pool). Wykonywalna mapa kto-co-kiedy.

**Składniki:**
- `aeis/advisor/orchestration_engine.py` — orchestruje pipeline
- `aeis_v2/workflow_v2/` — deklaratywny silnik workflow (YAML rules,
  conditions, actions; triggers `on_status_change` / `on_create` /
  `on_cron`)
- `governance/decision_ladder.py` — klasyfikacja D0-D5

### **L6 — Human Gate / Governance**

**Po co:** Operator człowiek **musi** móc zatrzymać pipeline w
dowolnym momencie. Tickety klasy D0-D5 z mandatorymi: D3+ = council
4/4, D4+ = council + ludzki podpis, D5 = council + human + zewnętrzny
recenzent.

**Składniki:**
- `governance/decision_ladder.py` — klasyfikacja D0-D5
- `governance/gates_registry.py` — entry/exit gates per faza
- `governance/evidence_packs.py` — paczki dowodów dla D3+
- `aeis_v2/governance_v2/` — ADR sign-off (`compute_adr_signature`,
  `evaluate_signoff`)
- `api/governance_routes.py` — POST /proposals, /approve, /reject,
  /execute
- `api/human_gate_routes.py` — `/api/v1/gates/human/requests`,
  `/reviews`, `/escalate`
- `aeis_v2/policy_v2/` — W19 evaluator (Jinja2 sandbox) +
  `StagedRolloutGate` (canary 0/1/5/25/50/100%) + `RoutingGate`

### **L7 — Coordination**

**Po co:** Partycjonowanie pracy na lane'y, reconciliation, resolver
zależności. Zapobiega konfliktom dwóch workerów na tym samym zasobie.

**Składniki:**
- `governance/conflict_resolver.py` — wykrywa i rozwiązuje konflikty
- `governance/compliance_engine.py` — ewaluacja reguł zgodności
- `aeis_v2/adapter_bus_v2/` — adapter bus między modułami
- `aeis/advisor/scaling.py` — orkiestrator skalowania advisora

### **L8 — Worker**

**Po co:** Pula workerów wykonuje moduły, emituje evidence + audit
events. Każdy worker ma `worker_id`, łączy się z kontraktem przez L4
SkillBinding.

**Składniki:**
- `aeis_v2/deployment/agent.py` — `DeployAgent` orchestracja
- `aeis_v2/deployment/federation.py` — `FederationRouter` z
  routingiem deterministycznym (privacy → model → cost → locality)
- `aeis_v2/terminal/sessions.py` — multi-session context, sessions
  store

### **L9 — Integration (LAB extensions)**

**Po co:** Specjalne integracje sprzętowe: cellular control plane,
SDR (software-defined radio), VPS deployment, container management,
device discovery.

**Składniki:**
- `cellular/` — Class M cellular control plane
- `containers/` — manager Dockera
- `devices/` — device discovery + registry (transports)
- `aeis_v2/deployment/nodes.py` — `Node`, `NodeKind`, `PrivacyLevel`,
  `NodeStatus`

### **L10 — Operator Console (Web)**

**Po co:** Workspace UI, projects view, council settings, idea-vault.
Wszystko co widzi operator-człowiek przez przeglądarkę.

**Składniki:**
- `src/sylion-frontend/src/app/(app)/` — Next.js 16 App Router
  - `idea-vault/` — IdeaVault + create/transition modals
  - `apps-builder/wizard/` — W16 cascade UI
  - `governance/` — proposals/voting/policies/compliance
  - `v2/admin/` — KPI dashboard z 6 cards (W19, canary, audit, violations,
    circuits, renders)
  - `terminal/`, `role-catalog/`, `federation/`, `policy/`
  - `orchestration/` — llm-routing, council-rules, dispatch, conversations
- `components/system/BackendOfflineGuard.tsx` — gate na backend health
- `components/idea-vault/`, `components/advisor/`, etc.

### **L11 — Operator Mobile**

**Po co:** HMAC bind, follow-me push notifications, kolejka zadań
offline, mobile UI.

**Składniki (status v3.5):** projektowane, runtime częściowo działa
przez REST. Pełna implementacja mobile native = backlog.

### **L12 — Output**

**Po co:** Reports, books (długie), evidence packs, snapshot exports.
To co wychodzi POZA system: PDF/MD raporty, paczki ZIP z dowodami,
eksporty GDPR portability (Article 20).

**Składniki:**
- `governance/evidence_packs.py` — generator paczek dowodów
- `aeis_v2/gdpr_v2/dsr_service.py` — eksport portability
- `workspace/books/` — generacja długich książek przez radę
- `api/efficiency_routes.py` — raporty kosztowe / budżetowe

---

## CZĘŚĆ II — 15 FAZ PRZEPŁYWU

Każda faza to **transition w idea lifecycle**, z gate'em
wejściowym/wyjściowym i obowiązkowymi audytami.

| # | Faza | Wejście | Owner | Audit chain | Gate |
|---|---|---|---|---|---|
| 1 | **Intake** | operator wpisuje pomysł | IdeaVault | `idea_lifecycle.jsonl` | none |
| 2 | **Source of Truth** | draft canonical_book + canonical_book_input | Book Interpreter | `apply_audit.jsonl` | none |
| 3 | **Masterplan draft** | przez Council planner | Architecture | `council_wedge.jsonl` | D2 |
| 4 | **Idea Debate** | rada głosuje, krytyk podpisuje | Council Hybrid | `council_wedge.jsonl` | D3 |
| 5 | **Plan Approval** | ticket D2/D3, opcjonalnie HG | Decision Ladder | `governance.jsonl` | D2/D3 |
| 6 | **Team Scaling** | execution_plan → worker_pool | L7 Coordination | `worker_audit.jsonl` | D2 |
| 7 | **Skill Binding** | wybór SkillBindings z manifestów | L4 Skills | `apply_audit.jsonl` | D2 |
| 8 | **Execution** | workery uruchamiają moduły | L8 Worker | `routing_audit.jsonl` + `worker_audit.jsonl` | D1 |
| 9 | **Mid-flight Steering** | autonomy stage, D2+ ticket | Operator/Council | `governance.jsonl` | D2-D4 |
| 10 | **Verification (human-like)** | operator przechodzi UI ręcznie | Operator | `verification.jsonl` | D2 |
| 11 | **Final Approval** | D4/D5 ticket, council + 2 ops | Council + HG | `governance.jsonl` | D4/D5 |
| 12 | **External Action** | submission, deploy, publish | Deploy Agent | `deploy_audit.jsonl` | D5 |
| 13 | **Memory Snapshot** | evidence pack frozen, hash-chained | L3 Memory | `evidence_chain.jsonl` | none |
| 14 | **Drift Audit** | diff vs canonical_book → backlog | L1 Canon | `drift_audit.jsonl` | none |
| 15 | **Memory Compact** | long-term layer + book regen | L3 Memory | `compact_audit.jsonl` | D3 |

---

## CZĘŚĆ III — MODUŁY RUNTIME

### `core/` — Substrat

| Plik | Funkcja |
|---|---|
| `contract_registry.py` | Rejestr manifestów modułów + bundle assembler |
| `event_bus.py` | Backbone domain events (`SylionEvent`, `EventBus`) |
| `decision_gate_engine.py` | Egzekwowanie gate'ów wejścia/wyjścia per faza |
| `bundle_assembler.py` | Assembly + dependency resolver bundli |
| `lifecycle_gates.py` | Walidacja przejść D0-D5 |
| `environment_orchestrator.py` | Multi-env deploy state |
| `hot_swap.py` | Hot-reload kernel (zero-downtime) |
| `embedding_hash_collision_detector.py` | Wykrywanie kolizji fingerprintów |

### `governance/` — Plan Decyzji

| Plik | Funkcja |
|---|---|
| `decision_ladder.py` | Klasyfikator D0-D5 (`classify_decision`) |
| `council_hybrid.py` | Silnik rady 9-rolowej + sygnatura krytyka |
| `gates_registry.py` | Rejestr entry/exit gate'ów na lifecycle |
| `evidence_packs.py` | Generator paczek dowodów dla D3+ |
| `audit_chain.py` | Hash-chain audytu governance |
| `tickets.py` | `GovernanceTicket` + `TicketStore` (Hook v1.0) |
| `compliance_engine.py` | Ewaluacja reguł zgodności |
| `conflict_resolver.py` | Wykrywanie konfliktów architektonicznych |
| `decision_snapshot.py` | Snapshoty stanu decyzji |
| `policy_registry.py` | Rejestr polityk (W19) |

### `aeis/` — Oryginalny v3.5

| Subkatalog | Funkcja |
|---|---|
| `advisor/` | Decision cards, confidence scoring, funding matcher |
| `advisor/engine/` | Rule engine, LLM judge, decision ladder, confidence |
| `advisor/funding/` | Consortium matcher, funding scoring |
| `advisor/history/` | Confidence provider z historii decyzji |
| `advisor/role_resolver.py` | Przypisywanie ról + task matching |
| `testing/` | Harness integracyjny: ontologia, simulation, personas |
| `self_healing_orchestrator.py` | Anomaly/error/threshold → restart/rollback |

### `aeis_v2/` — Plany Sprintów 2/3/4

#### `aeis_v2/audit_chain/` (Sprint 2 D6)

Hash-chained JSONL z SHA-256 content_hash chain.

- `chain.py` — `append_to_chain`, `verify_chain`, `AuditChainEntry`,
  `Tampered`, `GENESIS_HASH = "0000000000000000"`
- `rotator.py` — `AuditRotator` (rotacja przy size > N)
- Per-line legacy detection (mixed files, fix 2026-04-28)

#### `aeis_v2/council_v2/` (Sprint 2 G1)

Wedge dla W16 cascade — łączy match results z radą.

- `evaluate_match_with_council()` — wywołuje 9 ról równolegle
  (`ThreadPoolExecutor`), zlicza ważone głosy
- `OllamaRoleAdapter` — wywołania do Ollama gpt-oss:20b
- `ScriptedRoleAdapter` — deterministyczny stub do testów
- `CouncilWedgeDecision` — verdict + dissents + sentinel_blocks

#### `aeis_v2/embeddings/` (W13/W16 G1)

Swappable provider abstraction.

- `EmbeddingProvider` (interface)
- `OllamaEmbeddingProvider` — nomic-embed-text (default)
- `StubEmbeddingProvider` — deterministyczny do testów
- `cosine_similarity()`, `get_default_provider()`
- `PgEmbeddingCache` — psycopg-backed cache (lazy import)

#### `aeis_v2/role_match/` (W13 ADR-001 #5)

Hybrid task↔role matcher.

- `tag_overlap_score()` — Jaccard po tagach PL
- `cosine_similarity()` — embeddings refinement
- `hybrid_match()` — combined scoring (overlap × 0.6 + cosine × 0.4)
- `HybridMatch` — wynik z reason_pl

#### `aeis_v2/lifecycle_v2/` (Sprint 3)

11-stanowa maszyna pomysłu + 4-stanowa sesji.

- `IdeaLifecycle` — states: draft → submitted → under_review →
  approved/rejected → in_progress → blocked → completed → archived →
  soft_deleted → hard_deleted
- `SessionLifecycle` — created → active → paused → terminated
- `transition()`, `is_valid_transition()`, `is_terminal()`
- Append-only audit log per przejście

#### `aeis_v2/policy_v2/` (W19 ADR-003)

Jinja2 sandbox-based policy evaluator.

- `render_template()` — `SandboxedEnvironment` z timeout + size cap
- `is_evaluator_enabled()` — feature gate (env var)
- `JinjaRenderResult` — output + metadata
- `RoutingGate` — 3-gate composition (filter → route → audit)
- `StagedRolloutGate` — canary 0/1/5/25/50/100% bucket per request_id
- `chaos_payloads.py` — chaos suite (CWE-94 / SSTI testy)

#### `aeis_v2/replay_v2/` (Sprint 2 D5)

Replay-as-fork primitives.

- `SessionSnapshot` — capture stanu w decision_point
- `ReplayFork` — replay z model_override / context_override
- `ReplayResult` — divergence_score (cosine na decisions + Jaccard na final)
- `ReplayStorageLRU` — bounded snapshot store
- `compute_divergence_score()`, `cosine_similarity_floats()`,
  `jaccard_set_similarity()`

#### `aeis_v2/gdpr_v2/` (Sprint 2 D5)

GDPR Data Subject Requests (Article 15/16/17/20).

- `DsrService` — orchestracja access/rectification/erasure/portability
- `InMemoryUserDataStore`, `PgUserDataStore` — pluggable store
- `HardPurgeCron` — 30-dniowy soft-delete → hard-purge
- Każda akcja → wpis do `gdpr_dsr.jsonl` (chained)

#### `aeis_v2/rbac_v2/` (W7 Sprint 3)

Fine-grained capabilities extension.

- `has_capability()`, `grant_role_capabilities()`,
  `register_role_capabilities()`
- Capabilities: `replay_operator`, `lifecycle_manager`,
  `metrics_viewer`, `audit_viewer`

#### `aeis_v2/governance_v2/` (Sprint 3)

ADR sign-off machinery.

- `compute_adr_signature()` — SHA-256 nad ADR markdown
- `load_adr_status()`, `set_adr_status()`
- `evaluate_signoff()` — sprawdza minimalne kworum
- `AdrSignoffRequest`, `AdrSignoffResult`

#### `aeis_v2/ontology/` (W15)

Generic data model przez YAML manifesty.

- `manifest.py` — `ObjectTypeManifest`, `ObjectTypeSpec`,
  `DedicatedColumn`, `JsonbExtension`, `load_manifest`
- `compiler.py` — `compile_to_ddl()`, generuje migrations
- `registry.py` — `ObjectTypeRegistry`
- `applier.py` — `apply_manifest()` na żywą bazę
- `osdk_gen.py` — auto-gen Python SDK z manifestu
- `osdk_ts_gen.py` — auto-gen TypeScript klient

#### `aeis_v2/apps_v2/` (W16)

Idea→app studio (cascade Phase 0 → G1 → G2).

- `AppTemplate`, `MatchResult`, `DEMO_TEMPLATES` (5 PL templates:
  inspection_field, approval_workflow, inventory_lite,
  customer_records, support_tickets)
- `match_idea_to_templates()` — Phase 0 Jaccard tag-overlap
- `match_idea_to_templates_g1()` — G1 z embeddings cosine
- `match_idea_to_templates_g1_with_council()` — pełny cascade z radą
- `idea_embedding_cache_stats()` — cache stats

#### `aeis_v2/deployment/` (W17)

Hybrid local+central federation.

- `nodes.py` — `Node`, `NodeKind` (local/vps/edge/managed),
  `PrivacyLevel`, `NodeStatus`
- `registry.py` — `NodeRegistry` singleton
- `federation.py` — `FederationRouter` z 4-phase routing
  (privacy → model → cost → locality)
- `agent.py` — `DeployAgent` orchestracja blue-green

#### `aeis_v2/terminal/` (W18)

Live activity stream + sessions.

- `sessions.py` — `TerminalSession`, `SessionStore`, multi-context
- `commands.py` — `parse_command`, `BUILTIN_COMMANDS` (`/status`,
  `/cost`, `/agents`, etc.)

#### `aeis_v2/workflow_v2/` (W15 G3)

Deklaratywny silnik workflow.

- `WorkflowRule` — YAML rule (trigger + condition + action)
- `WorkflowEngine.fire()` — dispatcher
- Triggers: `on_status_change`, `on_create`, `on_update`, `on_cron`
- Actions: `emit_event`, `call_webhook`, `send_email`,
  `run_script` (sandboxed stub)

### `cognitive/` — Pamięć i Rada

| Plik | Funkcja |
|---|---|
| `idea_vault.py` | IdeaVault z 15 statusami + history + soft/hard delete + stale detection |
| `council/voting.py` | Role prompts, seeded votes (replay-safe), tier selection |
| `council/COUNCIL_ROLES` | 9 ról: planner, critic, security, legal, finance, governance, qa, red_team, council_chair |
| `council/DECISION_CLASS_TIERS` | Mapping D0/D1/D2 → cheap-fast LLMs, D3+ → deep-slow |

### `observability/` — Telemetria

| Plik | Funkcja |
|---|---|
| `log_aggregator.py` | Centralna agregacja logów + query |
| `metrics_registry.py` | Prometheus metrics registry |
| `tracing.py` | Distributed tracing (spans, events) |
| `prometheus_exporter.py` | `/metrics` endpoint |
| `pii_redactor.py` | Auto-mask PII w logach |
| `hub.py` | Observability hub coordinator |

### `api/` — REST Surface (FastAPI)

| Plik | Endpointy |
|---|---|
| `app.py` | Bootstrap + middleware (Auth/RBAC/RateLimit/CORS) |
| `aeis_routes.py` | `/v1/aeis/*` (advisor, evolution, integration) |
| `apps_routes.py` | `/v1/apps/match-idea`, `/v1/apps/match-idea-g1[-with-council]` |
| `governance_routes.py` | `/v1/governance/proposals`, `/voting`, `/policies`, `/compliance` |
| `replay_routes.py` | `/v1/terminal/sessions/{sid}/snapshot`, `/v1/replay/run`, `/v1/replay/list` |
| `gdpr_routes.py` | `/v1/gdpr/dsr/access\|rectification\|erasure\|portability` |
| `human_gate_routes.py` | `/v1/gates/human/requests`, `/reviews`, `/escalate` |
| `metrics_v2_routes.py` | `/v1/metrics/v2` (Prometheus exposition) |
| `health_v2_routes.py` | `/v1/health/v2` (audit_chain, gdpr_dsr, council_wedge status) |
| `ontology_routes.py` | `/v1/ontology/types`, manifest CRUD |
| `terminal_routes.py` | `/v1/terminal/sessions`, `/run`, `/history` |
| `role_catalog_routes.py` | `/v1/role-catalog`, `/capabilities`, `/match-task` |
| `federation_routes.py` | `/v1/federation/*` |
| `efficiency_routes.py` | `/v1/efficiency/budgets`, `/over`, `/drift`, `/circuits` |

---

## ZAŁĄCZNIK A — Klasy decyzji D0–D5

| Klasa | Nazwa | Gate | Human | Rollback | Efficiency |
|---|---|---|---|---|---|
| **D0** | Informational | auto | nie | — | — |
| **D1** | Trivial | 1 agent | nie | — | — |
| **D2** | Standard | 2 agents + Review | nie | opcjonalny | opcjonalny |
| **D3** | Significant | Full Board Council 4/4 | opcjonalny | **WYMAGANY** | **WYMAGANY** |
| **D4** | Critical | Council 4/4 + Human | tak + **Code Optimizer veto** | WYMAGANY + LPW | WYMAGANY + benchmark |
| **D5** | Greenfield/Systemic | Council 4/4 + Human + External Review | tak + zewnętrzny | WYMAGANY + LPW + CFT pass | WYMAGANY + perf/cost sign-off |

---

## ZAŁĄCZNIK B — Skład Rady (7 departamentów × role × wagi)

| Departament | Rola kluczowa (waga) | Mandatoryjność |
|---|---|---|
| **Architecture** | Chief Architect — Gemini 2.5 Pro (1.25) | D3+ |
| **Architecture** | Systems Analyst — Claude Opus 4 (1.00) | D3+ rebuild |
| **Platform** | Platform Lead — Claude Opus 4 (1.00) | D4+ |
| **Platform** | SRE — GLM-5.1 (0.60) | ad-hoc |
| **Implementation** | Impl Lead — Claude Opus 4 (1.00) | D3+ refactor |
| **Implementation** | Module Engineer — Qwen3.5 (0.35) | ad-hoc |
| **Testing/Validation** | QA Lead — GPT-5 (1.00) | D3+ quality |
| **Testing/Validation** | Regression Analyst — gpt-oss-20b (0.35) | ad-hoc |
| **Red Team** | Red Lead — Grok-3 (1.00) | D3+ rebuild |
| **Blue Team** | Blue Lead — Claude Opus 4 (1.00) | D3+ security |
| **Governance** | Governance Lead — Claude Opus 4 (1.00) | D3+ — **ONE REJECT = auto-escalate D4** |
| **Governance** | Compliance Officer — Gemini 2.5 Pro (1.25) | D3+ |

**Reguły 4/4 składu Rady:**
1. Zawsze: Governance Lead + Compliance Officer
2. Zawsze: reprezentant najbardziej dotkniętego departamentu
3. D3+ rebuild/refactor: + Red Lead + Chief Architect
4. D4 Critical: + Platform Lead
5. D5 Greenfield: wszyscy 7 Leadów + External Reviewer

---

## ZAŁĄCZNIK C — 11-stanowy lifecycle pomysłu

```
draft → submitted → under_review → approved → in_progress → completed
                                 ↓
                              rejected
                                 ↓
                              archived
                                 ↓
                            soft_deleted (30d grace)
                                 ↓
                            hard_deleted

  + blocked (boczna gałąź z in_progress, można wrócić)
```

Każde przejście jest **append-only** w `idea_lifecycle.jsonl`
(hash-chained). Operacje: `transition`, `is_valid_transition`,
`is_terminal`. Stale detection: brak aktywności 30 dni → `stale`.

---

## ZAŁĄCZNIK D — Audit chains (17 strumieni)

| Chain | Producer | Format |
|---|---|---|
| `apply_audit.jsonl` | DDL applier | legacy (pre-migration) |
| `routing_audit.jsonl` | FederationRouter | legacy |
| `cost_ledger/*.jsonl` | per-day cost | legacy |
| `council_wedge.jsonl` | CouncilHybrid | mixed (legacy + chained) |
| `gdpr_dsr.jsonl` | DsrService | chained |
| `replay_fork.jsonl` | ReplayFork | chained |
| `gdpr_hard_purge.jsonl` | HardPurgeCron | chained |
| `idea_lifecycle.jsonl` | IdeaLifecycle | chained |
| `session_lifecycle.jsonl` | SessionLifecycle | chained |
| `worker_audit.jsonl` | Worker pool | legacy |
| `governance.jsonl` | Decision Ladder | mixed |
| `evidence_chain.jsonl` | Evidence Packs | chained |
| `drift_audit.jsonl` | Canon drift detector | chained |
| `compact_audit.jsonl` | Memory Compact | chained |
| `verification.jsonl` | Operator verification | chained |
| `deploy_audit.jsonl` | DeployAgent | chained |
| `w19_audit.jsonl` | W19 evaluator | chained |

**Weryfikacja:** `python scripts/v2/verify_audit_chains.py` → raportuje
`[OK]`/`[LEGACY]`/`[FAULT]` per chain. Mixed pliki obsługiwane przez
per-line legacy filter (fix 2026-04-28).

---

## ZAŁĄCZNIK E — Status implementacji

| Warstwa | v3.5 | v2 (Sprint 2-4) | Brakujące |
|---|---|---|---|
| L1 Canon | ✓ Księga, Masterplan, manifesty | — | — |
| L2 Council | ✓ council_hybrid 9 ról | ✓ council_v2 wedge + Ollama | drift detection per role |
| L3 Memory | ✓ IdeaVault, snapshots | ✓ audit_chain, replay_v2, embeddings | long-term compact |
| L4 Skills | ✓ contract_registry | ✓ role_match hybrid | runtime executor (private) |
| L5 Planning | ✓ orchestration_engine | ✓ workflow_v2 deklaratywny | execution_plan derivation |
| L6 HG/Gov | ✓ decision_ladder, gates_registry | ✓ policy_v2 W19, governance_v2 | full HG UI |
| L7 Coord | ✓ conflict_resolver | ✓ adapter_bus_v2 | lane partitioning |
| L8 Worker | partial | ✓ deployment/agent | private worker pool |
| L9 Integration | ✓ cellular, containers, devices | — | SDR integration |
| L10 Console | partial | ✓ /v2/admin, idea-vault, governance, wizard | full mobile parity |
| L11 Mobile | backlog | — | wszystko |
| L12 Output | partial | ✓ gdpr portability, evidence | books generator |

---

## Bibliografia

- `docs/Ksiega_AEIS_v3_5_full.md` — pełna specyfikacja (462 strony, PL)
- `docs/claude_system_audit/CLAUDE_AEIS_CANON_COMPLETE_2026.md` — model 12-warstwowy + 15 faz + 13 etapów audytu
- `docs/claude_system_audit/CLAUDE_AEIS_CANON_VS_REALITY.md` — drift report
- `docs/plan_15_multi_team.md` — skład Rady 7 departamentów
- `docs/v2/MODULES_INDEX.md` — master mapa 40 commitów [v2 cron]
- `docs/v2/operations/audit_chains_catalogue.md` — katalog 17 strumieni audit
