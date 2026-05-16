# 00 · BASELINE KANON — planowana architektura SYLION AEIS v3.5

Dokument zbiera planowaną (kanoniczną) architekturę systemu SYLION AEIS v3.5 tak, jak
została opisana w trzech źródłach:

- `pdf_extract_1.txt` — AEIS Distributed Build Architecture (290 linii, roboczy opis
  rozproszonej produkcji kodu)
- `pdf_extract_2.txt` — SYLION AEIS Implementation Masterplan v3.5 (10 420 linii, plany
  P01–P20, Kernel + 12 klas modułów, ~65 klocków)
- `pdf_extract_3.txt` — SYLION AEIS Dokumentacja zintegrowana v3.5 (1 450 linii, 20
  planów kanonicznych + 18 aneksów A–R)

Dokument NIE porównuje planu z kodem. To jest wyłącznie baseline kanonu.

---

## 1. Warstwy architektoniczne (wg Księgi)

### 1a. Sześć warstw AEIS (Dokumentacja v3.5, §0.4, linie ~862–1019)

Kanon v3.5 definiuje **sześć warstw AEIS** — wg `pdf_extract_3.txt` linie 862–1019:

| # | Warstwa | Odpowiedzialność | Plany |
|---|---------|------------------|-------|
| 1 | **Cognitive** | Rozumowanie, planowanie, dekompozycja zadań, routing LLM; produkuje plan, nie wykonuje | Plan 02, 03, 17 |
| 2 | **Execution** | Uruchamianie, integracje zewnętrzne, adaptery, workflow runtime; działa na polecenie Cognitive | Plan 04, 05, 11 |
| 3 | **Security** | Auth, policy, guard, secrets, audit, PHANTOM; bramy bezpieczeństwa dla wszystkich wywołań | Plan 06, 12, Aneks D |
| 4 | **Memory** | Persystencja, indeksowanie, retrieval — Księga, Evidence, Self-Model; jedyne moduły z trwałym stanem cross-session | Plan 08, 16, Aneks E |
| 5 | **Self-Evolution** (NOWA v3.5) | Self-Observation, Improvement Queue, Self-Explanation, Self-Limitation, Self-Preservation; własne SLP-010..020 | Plan 19, Plan 20 |
| 6 | **Governance** | Drabina decyzyjna D0–D5, Council, Gates, Policy Registry, Evidence workflow | Plan 13, 14, 15 |

### 1b. Siedem warstw Distributed Build (Distributed Build Architecture, linie 30–74)

Warstwa produkcji rozproszonej zdefiniowana w `pdf_extract_1.txt` (linie 30–74):

| Warstwa | Komponenty | Odpowiedzialność |
|---------|-----------|------------------|
| A. Canon Layer | Canon Manager, Księga Store, Policy Store, Decision Class Registry | Jedno źródło prawdy: intencja, zasady, granice, canon snapshot |
| B. Planning & Decomposition | Decomposition Engine, Dependency Analyzer, Ownership Planner, Contract Freeze Manager | Rozkład na moduły, kontrakty, zależności, workstreamy |
| C. Coordination | Assignment Orchestrator, Global Build State, Compact Generator, Status Aggregator | Przypisywanie zadań, heartbeaty, lokalne compacty |
| D. Worker Build | Worker Runtime, repo sandbox, local tests, patch builder | Niezależna implementacja przypisanych modułów |
| E. Integration & Validation | Integration Orchestrator, contract tests, integration tests, drift detector | Ciągła walidacja kompatybilności |
| F. Governance | Decision Classifier, Approval Engine, Rollback Planner, Evidence Pack Builder | Klasyfikacja D0–D5, approval flow, rollback, evidence |
| G. Operator / Control Plane | Dashboard Simple, Dashboard Pro, worker fleet view, build topology view | Widoczność, sterowanie, eskalacje, monitoring |

### 1c. Kernel + 12 klas modułów (Masterplan R0.6, linie ~463–512)

Masterplan v3.5 operacjonalizuje architekturę jako **Kernel + 12 klas modułów**:

- **A. Core Kernel (8)** — nieruchomy rdzeń, D3+ do modyfikacji
- **B. Cognitive (7)**
- **C. Execution (6)**
- **D. Memory (7)**
- **E. Governance (7)**
- **F. Security (8)** — wszystkie od dnia 1 w profilu dev-light
- **G. Efficiency (4)**
- **H. AEIS Self-* (5)**
- **I. Skills/Demand (3)**
- **J. Surface (3)**
- **K. Rebuildability (4)**
- **L. Quality (3)**

**Zasada architektury** (Masterplan R0.6): „Rdzeń jest mały i nieruchomy; wszystko poza
rdzeniem jest wymienialne przez kontrakt. Łącznie ~65 modułów."

---

## 2. Planowane moduły — pełna lista

Kompletny katalog ~65 modułów SYLION, źródło: `pdf_extract_2.txt` (Masterplan R1.4,
linie ~1000–1566).

### Klasa A — Core Kernel (8 modułów, linie ~1006–1087)

| Nazwa modułu | Warstwa | Cel | Plan |
|--------------|---------|-----|------|
| sylion.core.module_registry | A Kernel | Jedyne źródło prawdy o żyjących modułach (module_id, kind, contract_version, lifecycle_stage) | P01 |
| sylion.core.manifest_loader | A Kernel | Parser/validator module.yaml względem M-Schema, rozwiązywanie zależności | P01 |
| sylion.core.contract_registry | A Kernel | Wersjonowane repozytorium kontraktów (Command/Query/Event/Telemetry/Rollback); buf breaking | P01 |
| sylion.core.event_bus | A Kernel | Wrapper NATS JetStream (publish/subscribe/replay, event_id UUIDv7, idempotentność) | P01 |
| sylion.core.decision_gate_engine | A Kernel | Silnik drabiny D0–D5 oraz bram G-* (G-AEIS, G-EFF, G-PERF, G-MEM, G-COST) | P04+P12 |
| sylion.core.evidence_spine | A Kernel | Append-only Ed25519 log; niemutowalny łańcuch dowodów | P06 |
| sylion.core.environment_orchestrator | A Kernel | Abstrakcja środowiska (Compose M0–M4 → K8s M5); hot swap shadow→dual→cutover | P01 |
| sylion.core.bundle_assembler | A Kernel | Składanie bundla z listy module_id; jedyna ścieżka do runtime | P01 |

### Klasa B — Cognitive (7 modułów, linie ~1086–1143)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.cognitive.planner | B Cognitive | Planowanie, dekompozycja zadań | P08 |
| sylion.cognitive.evaluator | B Cognitive | Ewaluacja propozycji | P08 |
| sylion.cognitive.reasoner | B Cognitive | Rozumowanie | P08 |
| sylion.cognitive.code_agent | B Cognitive | Agent kodu | P08 |
| sylion.cognitive.context_builder | B Cognitive | Budowa kontekstu (compact + Księga) | P02+P16 |
| sylion.cognitive.model_router | B Cognitive | Routing między modelami (LiteLLM wrapper) | P08 |
| sylion.cognitive.llm_adapter | B Cognitive | Wymienialny adapter LLM | P08 |

### Klasa C — Execution (6 modułów, linie ~1144–1207)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.execution.tool_runner | C Execution | Uruchamianie narzędzi | P07 |
| sylion.execution.connector_framework | C Execution | Ramka konektorów zewnętrznych | P07 |
| sylion.execution.workflow_engine | C Execution | Silnik workflow | P07 |
| sylion.execution.job_runner | C Execution | Uruchamianie jobów | P07 |
| sylion.execution.adapter_bus | C Execution | Szyna adapterów | P07 |
| sylion.execution.retry_orchestrator | C Execution | Retry / backoff | P07 |

### Klasa D — Memory (7 modułów, linie ~1207–1265)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.memory.kanon_access | D Memory | Księga Access Layer | P02 |
| sylion.memory.compact_layer | D Memory | canon_compact.md + CFT | P16 |
| sylion.memory.evidence_store | D Memory | Ewidencja decyzji D2+ | P06 |
| sylion.memory.self_model_store | D Memory | Formalny self-model AEIS (Aneks O) | P19 |
| sylion.memory.kb_adapter | D Memory | Adapter KB | P18 |
| sylion.memory.indexer | D Memory | Indeksowanie (pgvector) | P02+P16 |
| sylion.memory.retrieval | D Memory | Wyszukiwanie | P02+P16 |

### Klasa E — Governance (7 modułów, linie ~1265–1336)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.governance.decision_ladder | E Governance | Drabina D0–D5 | P04 |
| sylion.governance.council_workflow | E Governance | Council 4/4 | P05 |
| sylion.governance.roles | E Governance | Role Board × 7 działów | P05+P15 |
| sylion.governance.gates_registry | E Governance | Rejestr bram G-* | P12+P13 |
| sylion.governance.policy_registry | E Governance | Polityki, w tym SLP-001..030 | P11+Aneks Q |
| sylion.governance.self_explanation_validator | E Governance | Walidacja self_explanation.json (Aneks R) | P19 |
| sylion.governance.evidence_workflow | E Governance | Workflow Evidence Pack | P06 |

### Klasa F — Security (8 modułów, wszystkie od dnia 1, linie ~1337–1393)

| Nazwa | Warstwa | Cel (profil M0 → M5) | Plan |
|-------|---------|---------------------|------|
| sylion.security.auth_provider | F Security | local token bootstrap → Keycloak OIDC | P09 |
| sylion.security.bootstrap_init | F Security | plaintext admin init → secure seed + hardware token | P09 |
| sylion.security.session_broker | F Security | in-memory sessions → Redis + JWT + refresh rotation | P09 |
| sylion.security.policy_engine | F Security | allow-list basic → OPA + fine-grained policies | P09 |
| sylion.security.execution_guard | F Security | subprocess isolation → PHANTOM + gVisor/Firecracker | P09 |
| sylion.security.secret_provider | F Security | .env + local file → HashiCorp Vault | P09 |
| sylion.security.audit_sink | F Security | append log → Ed25519 signed chain | P06+P09 |
| sylion.security.phantom_wrapper | F Security | skeleton sandbox → full PHANTOM strict | P09 |

### Klasa G — Efficiency (4 moduły, linie ~1394–1441)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.efficiency.code_bloat | G Efficiency | Code Bloat / LoC / complexity | P10 |
| sylion.efficiency.runtime_perf | G Efficiency | p95/p99 latency, throughput, USE method | P10 |
| sylion.efficiency.memory_footprint | G Efficiency | RSS, heap, leaks, cgroup | P10 |
| sylion.efficiency.cost_envelope | G Efficiency | Budżet tokenowo-kosztowy miesięczny | P10 |

### Klasa H — AEIS Self-* (5 modułów, linie ~1441–1471)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.aeis.self_observation | H AEIS | 100% runtime observation od M4 | P19 |
| sylion.aeis.improvement_queue | H AEIS | Klasyfikacja propozycji wg D0–D5 | P19 |
| sylion.aeis.self_explanation | H AEIS | Dokumentacja self-modification (Aneks R) | P19 |
| sylion.aeis.self_limitation | H AEIS | Enforce SLP-001..030 | P19 |
| sylion.aeis.self_preservation | H AEIS | Ochrona misji (nie instancji) | P19 |

### Klasa I — Skills / Demand (3 moduły, linie ~1471–1491)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.skills.registry | I Skills | Skill lifecycle DRAFT → PUBLISHED → DEPRECATED | P18+P20 |
| sylion.skills.executor | I Skills | Sandbox executor skilli | P18+P20 |
| sylion.aeis.demand_signal | I Skills | Skill Demand Engine (Aneks P) | P18+P20 |

### Klasa J — Surface (3 moduły, linie ~1492–1510)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.surface.console_api | J Surface | gRPC-web/tRPC gateway | P17 |
| sylion.surface.console_ui | J Surface | Next.js 14 + shadcn/ui | P17 |
| sylion.surface.ws_gateway | J Surface | WebSocket gateway (kontrakty Aneks K) | P17 |

### Klasa K — Rebuildability (4 moduły, linie ~1511–1535)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.rebuild.orchestrator | K Rebuild | SYSTEM_REBUILD_MODE orchestration | P14 |
| sylion.rebuild.lpw_manager | K Rebuild | Legacy Preservation Window (§14.8) | P14 |
| sylion.rebuild.cutover_controller | K Rebuild | Maszyna stanów shadow→dual→cutover | P14 |
| sylion.rebuild.cft_runner | K Rebuild | Compact Fidelity Test (Aneks I) | P14+P16 |

### Klasa L — Quality (3 moduły, linie ~1536–1566)

| Nazwa | Warstwa | Cel | Plan |
|-------|---------|-----|------|
| sylion.quality.golden_set_registry | L Quality | Golden sets kontraktowe | P11 |
| sylion.quality.test_runner | L Quality | Contract / integration / performance tests | P11 |
| sylion.quality.regression_detector | L Quality | Auto-rollback trigger przy regresji | P11 |

**Łącznie: 65 modułów** (8 + 7 + 6 + 7 + 7 + 8 + 4 + 5 + 3 + 3 + 4 + 3 = 65).

---

## 3. Plany 01–20 z Masterplanu

Źródło: `pdf_extract_3.txt` linie 161–204 (spis treści Dokumentacji) oraz `pdf_extract_2.txt`
linie ~485–644 (mapa 20 planów v3.5).

| # | Plan | Status | Główny cel | Kluczowe moduły |
|---|------|--------|-----------|-----------------|
| 00 | **AEIS — Autonomous Engineering Intelligence System** | NADRZĘDNY v3.5 | Meta-zasada Autonomy under Canon, 6 warstw, 5 form uczenia, 5 mech. self-*, mission preservation | wszystkie AEIS Self-* (klasa H) |
| 01 | Admin Control Plane (ACP) | BASE v3.0 | Manifesty modułów z implementation_strategy; Kernel jako gniazdo klocków | Core Kernel (8) |
| 02 | VPS — maszyna stanów środowisk | v3.1 EXPAND | Stany cutover: CUTOVER_READY/PENDING/ACTIVE, STABILIZATION, HOT/WARM_STANDBY, LEGACY_DECOMMISSION | environment_orchestrator |
| 03 | Knowledge Base (KB) | BASE v3.0 | Schema versioning pod rebuild, legacy view | memory.kb_adapter, indexer, retrieval |
| 04 | Secrets Vault | BASE v3.0 | Vault migration patterns dla rebuild | security.secret_provider |
| 05 | Model Engine — Board × 7 działów | BASE v3.0 | Board × 7 działów, wagi per dział | governance.roles, council_workflow |
| 06 | Agent Lifecycle + Team Lifecycle | BASE v3.0 | Auto-rozwój zespołów, propozycje D3+, human approve | evidence_spine, evidence_store |
| 07 | Evolution Safety | v3.1 EXPAND | §7.11 Rollback post-cutover, auto-rollback triggers, fencing/lease | execution.* (6 modułów) |
| 08 | Canonical Evolution (rdzeń) | BASE v3.0 | Trzy ścieżki: Evolution · Refactor · Rebuild; decision tree | cognitive.* (7) |
| 09 | Operator Environment | BASE v3.0 | Rebuild orchestration UI (rozszerzany w Planie 17) | security.* (8) |
| 10 | Cost Governance | v3.3 EXPAND | §10.10 cztery budżety per moduł: bloat / perf / memory / cost; LPW jako pozycja budżetu D4/D5 | efficiency.* (4) |
| 11 | Run Lifecycle | BASE v3.0 | Multi-track runs (legacy + target) | quality.* (3) |
| 12 | Bundle + Testing | v3.3 EXPAND | §12.8 bramy G-EFF-01..04, G-PERF-01..03, G-MEM-01..02, G-COST-01..02 jako pre-bundle | bundle_assembler, decision_gate_engine |
| 13 | Governance & Evidence | v3.3 EXPAND | §13.13 rejestr bram + 4 artefakty efficiency w Evidence pack; D5 + external review | governance.evidence_workflow, gates_registry |
| 14 | Greenfield Rebuild Orchestration | v3.1 EXPAND | §14.8 Post-Cutover Legacy Preservation Window (LPW 7 dni) | rebuild.* (4) |
| 15 | Multi-Team Pipeline Organization | v3.3 EXPAND | §15.10 cztery role stałe: Code Optimizer (hard veto), Performance Engineer, Memory Auditor, Cost Optimizer | governance.roles |
| 16 | Compaction & Memory Protocol | v3.3 EXPAND | §16.12 efficiency metrics w canon_compact (bloat_score, p95_latency, peak_rss, monthly_spend); CFT §16.11 | memory.compact_layer, cft_runner |
| 17 | Operator Console & Dashboard UI/UX | NOWY v3.3 | Design system, 8 paneli, 7 widoków RBAC, kontrakty WebSocket, WCAG AA | surface.* (3) |
| 18 | Skills & Knowledge Pipeline | NOWY v3.3 | Skill jako artefakt 1st-class; lifecycle DRAFT → PUBLISHED → DEPRECATED; skill.yaml; 30+ skilli (Aneks M) | skills.registry, skills.executor |
| 19 | Self-Evolution Engine | NOWY v3.5 | Self-Model Store + Observation Bus + Improvement Queue + Self-Limitation Engine + Sandbox + bramy G-AEIS-01..05 | aeis.self_* (5) |
| 20 | Skill Demand Engine | NOWY v3.5 | Demand signals + skill_outline + brama G-AEIS-SKILL-01 + 4 Skill Generation Modes + deprecation by demand | aeis.demand_signal |

---

## 4. Kluczowe zasady kanonu

### 4.1 Pięć meta-zasad (stack addytywny, Masterplan R0.2, linie ~192–222)

| # | Meta-zasada | Wersja | Pytanie kanoniczne |
|---|-------------|--------|--------------------|
| 1 | Rebuildability over Lineage | v3.0 | Czy możemy przebudować to od zera? |
| 2 | Reversibility & Fidelity | v3.1 | Czy możemy się wycofać — bez utraty wierności? |
| 3 | Efficiency by Default | v3.3 | Czy to jest wydajne — z definicji, nie jako optymalizacja? |
| 4 | Autonomy under Canon | v3.5 | Czy system może to zrobić sam — nie łamiąc Księgi? |
| 5 | **Modularity by Contract** | v3.5 (Masterplan) | Czy można wymienić ten klocek bez zmian architektury? |

### 4.2 Drabina decyzji D0–D5 (Dokumentacja v3.5, linie ~310–402)

| Klasa | Nazwa | Typowy zakres | Gate | Human | Rollback/CFT | Efficiency 4× |
|-------|-------|---------------|------|-------|--------------|---------------|
| D0 | Informational | Odczyt, raport | auto | nie | — | — |
| D1 | Trivial | Patch, kosmetyka | 1 agent | nie | — | — |
| D2 | Standard | Zmiana w module | 2 agenci + Review | nie | zalecane | opcjonalne (delta) |
| D3 | Significant | Refactor, zmiana kontraktu | Full Board Council 4/4 | opcjonalnie | WYMAGANE | WYMAGANE 4/4 |
| D4 | Critical | Rebuild modułu, zmiana Księgi lokalna | Council 4/4 + Human | tak | WYMAGANE + LPW | WYMAGANE + Code Optimizer veto |
| D5 | Greenfield/Systemic | Pełny rebuild, zmiana fundamentów Księgi | Council 4/4 + Human + External Review | tak + external | WYMAGANE + LPW + CFT pass | WYMAGANE + perf benchmark + cost envelope sign-off |

### 4.3 Contract Freeze Milestone (Masterplan R2 + Distributed Build §7)

Przed równoległą pracą wielu zespołów/workerów MUSI być zamrożonych **7 artefaktów**:

1. Manifest Schema (module.yaml → M-Schema)
2. Contract Registry (Command/Query/Event/Telemetry/Rollback)
3. Event Taxonomy (`<domain>.<subject>.<verb>`, idempotent UUIDv7)
4. Module Lifecycle (draft → build → validate → shadow → dual → cutover → stable → deprecated)
5. Dependency Rules (graf zależności + ownership)
6. Decision Boundaries per Module (decision_class_entry)
7. Security Profile Abstraction (dev-light / test-light / staging-strict / prod-strict)

Zmiana któregokolwiek po freeze = minimum D3 (zmiana cross-module lub publicznego kontraktu).

### 4.4 Lifecycle gates i bramy G-*

- **G-AEIS-01..05** — bramy self-modification AEIS (Plan 19)
- **G-AEIS-SKILL-01** — brama generacji skilli (Plan 20)
- **G-EFF-01..04** — code bloat / runtime / memory / cost (pre-bundle, Plan 12 §12.8)
- **G-PERF-01..03** — performance baselines (SLO p95/p99)
- **G-MEM-01..02** — memory profile
- **G-COST-01..02** — cost envelope
- **G-CUT / G-COMP / G-CFT** — cutover / compaction / compact fidelity (v3.1, Plan 13)
- **G-AUTONOMY-1..5** — bramy 5-etapowego Autonomy Rollout

### 4.5 Evidence Pack (obowiązkowy dla D3+)

Każda decyzja D3+ MUSI publikować (Dokumentacja §120–129, Masterplan R9):

- Rollback Plan (Reversibility)
- Compact Fidelity Test result (Fidelity, Aneks I)
- `code_efficiency_report.json`
- `performance_baseline.yaml`
- `memory_profile.json`
- `cost_envelope.json`
- **(v3.5)** `self_explanation.json` (Aneks R)
- **(v3.5)** dowód zgodności ze SLP-001..030 (Aneks Q)

Brak choćby jednego artefaktu = **automatyczna odmowa quorum** przez bramę G-EFF-01 /
G-AEIS-01. Code Optimizer Agent ma **hard veto** na bundle build (override tylko Council
4/4).

### 4.6 Human Gate

- D0–D2: bez człowieka
- D3: opcjonalnie
- D4: **wymagane** (Council 4/4 + Human)
- D5: **wymagane + External Review** (drugi operator / zewnętrzny red team / audytor —
  ma prawo weta)
- Autonomy Auditor (v3.5) — weto na A3+ naruszające Mission Preservation (G-AEIS-05)

### 4.7 Self-Limitation Policies (SLP-001..030, Aneks Q)

Skończona, kanoniczna lista działań, których AEIS NIE MOŻE wykonać bez Human Gate:

- SLP-001: modyfikacja definicji misji w Księdze
- SLP-002: usunięcie/osłabienie bramy decyzyjnej
- SLP-003: rozszerzenie własnych uprawnień PHANTOM
- SLP-010..020: ograniczenia warstwy Self-Evolution
- (…do SLP-030)

### 4.8 Compaction & Memory Protocol (Plan 16)

- **canon_compact.md** generowany w 3 triggerach: co 24h + przed każdą D3+ + przed
  każdym bundle build
- **Dwa poziomy**: agent-compact (wstrzykiwany agentom) + operator-compact (do
  człowieka)
- **Compact Fidelity Test** (CFT, Aneks I) — mierzalna funkcja wierności compactu wobec
  kanonu; CFT pass jest wymagane dla D5

### 4.9 Antywzorce zakazane (Distributed Build §18)

1. Parallel Build Without Frozen Contracts
2. Silent Cross-Module Changes
3. Late Integration
4. Worker Full-Repo Blind Editing
5. Everyone Touches Everything
6. Contract Drift Without Governance
7. Merge Before Evidence
8. Shared Internal Structures Instead of Public Contracts
9. Direct Python import między modułami (Masterplan R1.6, blokowane przez
   import-linter)
10. Cross-schema SQL ad-hoc (tylko przez widoki w Contract Registry)

### 4.10 Trzy ścieżki implementacyjne (Dokumentacja, linie ~256–309)

| Ścieżka | Zakres | Kontrakty | Klasa min | Artefakty |
|---------|--------|-----------|-----------|-----------|
| Evolution | reuse + patch + extend + migrate | zachowane | D0–D2 | patch_plan.md, migration.yaml |
| Refactor | odcięcie modułu + nowa impl. + gradual cutover | zachowane (D3) lub zmienione (D4) | D3 (Council 4/4) | refactor_plan.md, contract_delta.json, cutover_strategy.md |
| Rebuild | nowy target + greenfield + controlled cutover | mogą być nowe | D4 (moduł) / D5 (system) | rebuild_decision_report.md, target_architecture_delta.json, greenfield_module_map.json, cutover_strategy.md |

### 4.11 Pięć etapów Autonomy Rollout (Plan 19 / R7)

`observe → propose → sandbox → limited-prod → full-governed`, z bramami
G-AUTONOMY-1..5 między etapami.

### 4.12 Board × 7 działów (Dokumentacja, linie ~430–455)

Organizacja pipeline jako wielozespołowa firma programistyczna — **wszystkie 7 działów
są stałe, żadnego „on-demand"**:

1. Architektura (interpretacja Księgi, target architectures, blast radius)
2. Platforma (ACP, VPS, provisioning, bundle, observability)
3. Implementacja (moduły, kompatybilność, migracje) — **+ Code Optimizer z hard veto**
4. Testy i walidacja (contract, regresja, integracja) — **+ Performance Engineer,
   Memory Auditor, Cost Optimizer**
5. Red Team (adversarial scenarios przed promocją do baseline)
6. Blue Team (detekcja, telemetria, SOC/DFIR)
7. Governance & Compliance (zgodność z Księgą, propozycje zmian, Evidence pack)

---

## 5. Distributed Build — jak miało działać

Źródło: `pdf_extract_1.txt` (cały dokument, 290 linii).

### 5.1 Zasada nadrzędna (§2, linie 24–29)

**Distributed Buildability by Contract**: każdy baseline projektowany przez AEIS musi
być rozkładalny na niezależne moduły rozwijane równolegle przez wielu agentów.
**Równoległa implementacja jest dozwolona wyłącznie po zamrożeniu kontraktów,
ownership, dependency graph i zasad integracji.** Żaden worker nie może samowolnie
zmieniać granic modułu ani publicznych interfejsów.

### 5.2 Przepływ od pomysłu do kodu (§6, linie 114–131)

1. **Ingestion** — operator wprowadza pomysł, Księgę, ograniczenia, preferencje tech.
2. **Canon Snapshot** — Canon Manager publikuje aktualną prawdę kanoniczną.
3. **Decomposition** — Decomposition Engine rozbija na kernel, moduły, kontrakty,
   workstreamy.
4. **Contract Freeze** — zamrożone: publiczne kontrakty, event taxonomy, ownership,
   dependency graph, integration rules, security profile abstraction.
5. **Assignment** — Assignment Orchestrator dzieli moduły między workerów wg
   workstream planu.
6. **Worker Build** — każdy worker pobiera lokalny compact, implementuje swój zakres,
   odpala testy lokalne, zgłasza patch proposal.
7. **Integration Validation** — Integration Orchestrator uruchamia contract tests,
   integration tests, lint, typecheck, smoke tests.
8. **Governance Check** — Decision Classifier klasyfikuje, włącza gate'y, review,
   rollback plan, evidence.
9. **Merge / Promote** — tylko zmiany zgodne z kontraktami + testami + governance
   wchodzą do gałęzi integracyjnej.
10. **Broadcast & Re-sync** — zmiany publikowane jako eventy; workery dostają nowe
    compacty.

### 5.3 Model workera (§8–9, linie 142–163)

**Worker MUSI:** pobrać assignment + compact, pracować w przypisanym zakresie, odpalać
testy lokalne, publikować heartbeat/status, zgłaszać patch proposal.

**Worker NIE MOŻE:** zmieniać cudzych kontraktów bez governance, czytać całego repo
przy każdej zmianie, robić nieautoryzowanych zmian architektonicznych, omijać
integracji i gate'ów, robić cichych merge'ów, wprowadzać cross-module driftu.

**Worker compact** zamiast pełnej pamięci: moduły + aktualne zadania, bezpośrednie
zależności, ostatnie ważne decyzje, ostatnie zmiany kontraktów dotyczące zakresu,
integration blockers, priorytet/deadline, lokalne acceptance criteria.

### 5.4 Mechanizm synchronizacji (§15, linie 230–239)

- **Pull** — worker pobiera assignment, compact, zmiany kontraktów
- **Push** — worker publikuje heartbeat, status, wyniki testów lokalnych, patch
  proposal
- **Event-driven update** — zmiany kontraktu/dependency/decyzji governance →
  natychmiastowa aktualizacja
- **Compact refresh** — nowy compact po istotnych zmianach
- **Global Build State** — dashboard widzi całość, worker tylko lokalny wycinek

### 5.5 Rejestry obowiązkowe (§5, linie 105–113)

- `module_registry.yaml` — mapa modułów, statusów, ownerów, workerów
- `contract_registry/` — publiczne API, eventy, payloady, wersje, compatibility rules
- `assignments.json` — kto co robi, priorytety, blockery, ETA
- `integration_status.json` — stan testów, contract mismatches, drift, promotion
  readiness
- `decision_log.md` — decyzje architektoniczne, uzasadnienia, approvals
- `worker_heartbeats.json` — heartbeat, obciążenie, stan testów, zdrowie workerów
- `recent_changes_compact.md` — skrócony stan systemu dla workerów
- `evidence/<change_id>/` — pełne artefakty dowodowe dla D3+

### 5.6 Topologia wdrożenia (§12–14, linie 186–228)

- **Wariant 5 serwerów** (minimalny): Control Plane + Worker A (Core/Registry) +
  Worker B (Cognitive/Memory) + Worker C (Execution/Skills) + Worker D + Integration
- **Wariant 8 serwerów (rekomendowany)**: Canon&Planning, Coordination&Governance,
  Data&Event Backbone (Postgres+NATS+MinIO+Secrets), Worker A Core, Worker B Cognitive,
  Worker C Execution, Worker D Security, Integration+Dashboard
- **Wariant 10 serwerów**: Canon, Planning, Coordination, Governance, Data, Worker A
  Core, Worker B Cognitive, Worker C Execution, Worker D Security, Worker E Surface

### 5.7 Drift detector i governance rozproszonego driftu (§11)

- Zmiana cross-module: min. D3
- Zmiana publicznego kontraktu: D3+
- Zmiana dependency graph lub granic modułów: D3/D4
- Zmiana globalnej topologii / organizacji build factory: D4/D5
- Evidence pack i rollback plan obowiązkowe dla odpowiednich klas zmian

### 5.8 Minimalna kolejność wdrożenia (§19, linie 263–274)

1. Canon Manager + spójny model Księgi/masterplanu
2. Module Registry + Contract Registry
3. Dependency Graph + Ownership Map
4. Assignment Orchestrator
5. Worker Runtime z local sandbox + local tests
6. Integration Orchestrator
7. Governance Gate + Evidence Pack Builder
8. Dashboard Pro z widokiem worker fleet / blokad / integracji / decyzji
9. Dopiero potem: skalowanie 5 → 8–10 serwerów

### 5.9 Repo i bezpieczeństwo (§16–17)

- **Monorepo** z mocnym contract governance
- Każdy worker pracuje na osobnym branchu / worktree
- Worker nie merge'uje bezpośrednio do baseline — tylko patch proposal przez
  integrację + governance
- Folder ownership + contract ownership ograniczają chaos
- **Osobny API key, worker_id, audit trail per worker**
- Każda propozycja zmiany ma ślad: kto, z jakiego serwera, na jakim zadaniu, na jakiej
  wersji compactu

---

## 6. Mobile AEIS — co Księga mówi

Źródła: `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt` (1409 linii) oraz
`AEIS_Funding_Autopilot_prompt.txt` (1192 linie).

### 6.1 Główna idea

AEIS Operator Mobile **nie jest aplikacją dotacyjną**. To **globalna mobilna wieża
kontroli całego programu AEIS** — wszystkich agentów, modułów, Dockerów, VPS-ów,
procesów, deploymentów, dokumentów, działań zewnętrznych, kosztów, alertów
bezpieczeństwa i decyzji wymagających człowieka. Funding Autopilot jest **jednym z
kanałów** w aplikacji.

### 6.2 Dwa ściśle połączone moduły

#### Moduł 1 — AEIS Human Gate Orchestrator (backend `sylion/decision_orchestrator/`)

Centralny system zarządzania decyzjami człowieka, zapobiegający sytuacji gdy „20
Dockerów i 10 VPS-ów stoi, bo każdy worker czeka osobno na decyzję". 13 podmodułów:

1. Decision Intake (zbieranie decyzji od wszystkich agentów/orkiestratorów/portali)
2. Decision Classifier (ryzyko/finanse/prawo/technika/produkcja/bezpieczeństwo +
   priorytet P0–P4)
3. Autonomy Policy Engine (reguły autozatwierdzania, limity kosztów/infra/API)
4. Decision Queue (kolejki P0 Emergency → P4 Low, blokujące vs nieblokujące)
5. Batch Approval Engine (grupowanie podobnych decyzji)
6. Delegation Engine (CTO/CFO/prawnik/admin infra/PM/zastępca)
7. Execution Continuity Engine (work stealing, deadlock detection, timeouty)
8. Decision Dependency Graph
9. Risk-Based Auto Approval (niskie ryzyko, w limitach budżetu)
10. Notification Routing (dashboard/mobile/email/SMS/Slack/Teams)
11. Decision SLA (czasy reakcji per priorytet, timeouty, eskalacje)
12. Audit Trail (kto/kiedy/urządzenie/co/alternatywy/ryzyka/koszt/wersja)
13. Decision Learning (uczenie preferencji operatora, sugerowanie automatyzacji)

**Zasada główna**: human gates są **risk-based, nie task-based**. Zgody wymaga ryzyko,
nie każdy task.

#### Moduł 2 — AEIS Operator Mobile (backend `sylion/operator_mobile/` + testing
`sylion/operator_mobile_testing/`)

Aplikacja mobilna (Google Pixel Live Test Mode) obsługująca **wszystkie moduły AEIS**:
Funding Autopilot, Code/Build, Infrastructure, Deployment, Security, Finance/Cost,
Legal/Compliance, External Communication, Browser/Web, Data/Document, AI
Research/Planning, System Health.

12 podmodułów (Global Critical Inbox, Module Channels, Push Notification Engine, Mobile
Human Gate, Secure Approval Layer, Operator Modes, System Status, Batch Approval,
Escalation System, Voice/Chat Operator, Audit & Compliance, Operator Preferences).

### 6.3 6 poziomów autonomii (Level 0–5)

- Level 0 Manual — każda decyzja wymaga człowieka
- Level 1 Assisted — AEIS proponuje, człowiek zatwierdza większość
- Level 2 Bounded Autonomy — AEIS sam wykonuje decyzje niskiego/średniego ryzyka w
  limitach
- Level 3 Supervised Autonomy — **domyślny** dla AEIS
- Level 4 High Autonomy
- Level 5 Full Autonomy — **nierekomendowany** dla systemu wykonującego działania
  prawne/finansowe/produkcyjne

### 6.4 3 typy Human Gate

- **Blocking Human Gate** — zatrzymuje zależną część procesu (finalny submit, prod
  deployment, podpis, migracja bazy prod, dokumenty finansowe)
- **Non-Blocking Human Gate** — decyzja czeka, system kontynuuje niezależne zadania
  (warianty UI, dodatkowe analizy, rozszerzenie dokumentacji)
- **Batch Human Gate** — zbieranie wielu małych decyzji w pakiet (20 decyzji
  technicznych, 30 tabel migracji dev/staging)

### 6.5 Pixel Live Test Mode

Założenie: do środowiska dev AEIS podłączony jest fizyczny **Google Pixel z Androidem**
jako realne urządzenie testowe. Obsługa przez `adb devices` + instalacja apk +
logcat/crash reports + testy push/deep-link/biometria/offline/token expiry/audit.
**15 testów minimalnych** (Device Detection → Mobile QA Report).

### 6.6 Bezpieczeństwo mobilne

- Push notification **nie zawiera sekretów** — na ekranie blokady tylko: „AEIS:
  wymagana decyzja krytyczna"
- Secure Approval Layer: biometria systemowa (Face Unlock/PIN), krótkotrwały approval
  token, device binding, podpis decyzji kluczem urządzenia, session timeout, device
  revoke
- P0/P1 wymagają świeżej autoryzacji + fingerprintu urządzenia + zapisu IP/urządzenia/
  czasu/wersji dokumentu
- Blokada zatwierdzeń po wykryciu root/jailbreak
- Tryb read-only po utracie zaufania urządzenia

### 6.7 Follow Me Mode + tryby operatora

- **Follow Me Mode** — krytyczne decyzje idą za operatorem na telefon, konfigurowalny
  czas, poziomy priorytetów, moduły aktywne, eskalacje
- **Tryby**: Full Control / Critical Only / Build Watch / Deployment Watch / Security
  Watch / Funding Watch / Night Build Mode / Do Not Disturb / Delegated Mode

### 6.8 Relacja Funding Autopilot ↔ Mobile

Funding Autopilot (1192 linie promptu) jest **jednym z ~12 kanałów** w Operator Mobile.
Wszystkie prawnie/finansowo wiążące akcje (submit wniosku, upload dokumentów fin.,
podpis elektroniczny, ePUAP/eIDAS, oświadczenia prawne, wysyłka maila do partnera)
przechodzą przez **Human Approval Gate** realizowany mobilnie z biometrią.

### 6.9 Finalny cel (z promptu)

> „AEIS może prowadzić bardzo duży projekt na wielu Dockerach i VPS, agenci nie
> blokują się bez potrzeby, decyzje niskiego ryzyka są autozatwierdzane, decyzje
> średnie są grupowane, decyzje krytyczne trafiają na telefon operatora, operator może
> zatwierdzać decyzje z Google Pixel, system działa także gdy operator nie siedzi przy
> komputerze, wszystkie działania są audytowane, żadne prawnie/finansowo/produkcyjnie/
> bezpieczeństwowo ryzykowne działanie nie dzieje się bez świadomej zgody człowieka."

---

## Meta

- **Baseline zebrany**: 2026-04-24
- **Źródła**: 3 PDF extrakty (pdf_extract_1..3.txt) + 2 prompty mobile/funding
- **Łączna objętość źródeł**: ~13 000 linii tekstu
- **Wersja kanonu**: SYLION AEIS v3.5 · Pipeline 8.5.0 · MZ 3.5.5 · Autonomy under Canon
- **Baseline implementacyjny**: Kernel 8 + 12 klas modułów = **65 modułów** w 20
  planach P01–P20, 20 sprintów w 6 milestones M0–M5 (~12 miesięcy)
