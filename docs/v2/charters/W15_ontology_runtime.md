# W15 Charter — Ontology Runtime Plane

> Status: **DRAFT** (2026-04-27)
> D-level: **D5**
> Estymacja solo: **16-19 tygodni**
> Depends on: AEIS v1 baseline (sylion.core.event_bus, sylion.surface.command_bus,
> sylion.db.pg_migration), W14 E1-E12 (testing ontology jako migration source)

## 1. Cel

W15 to **generalna warstwa modelu danych** dla SYLION AEIS — odpowiednik Palantir
Foundry Ontology / OSDK. Cel: Robert (i każdy operator) ma definiować *dowolne*
typy obiektów (Customer, Vehicle, Inspection, Funding Application, Demo Project,
Idea, Charter, Finding, …) przez **manifest YAML**, a system automatycznie
generuje DDL PostgreSQL, REST endpoints, gRPC stubs i Python OSDK — bez ręcznego
pisania boilerplate'u w 10 plikach.

Dziś AEIS v1 ma 35 top-level subsystems i 110 SQLite tables, każdy z własnym
ręcznie pisanym dataclass + Store + REST router. W14 dodało kolejnych 25 obiektów
testing w `sylion/aeis/testing/ontology/`. Wzorzec się powtarza: dataclass +
SQLite schema migration + JSON serializer + REST router + frontend hook + test
suite — łącznie ~500-1000 LOC per typ, kilka dni pracy. **W15 redukuje to do
~50 linii YAML i `make migrate`.**

W15 jest oznaczony **D5 (krytyczny)** ponieważ jest fundamentem dla W16
(Operational Apps Builder czyta W15 manifest), W17 (deployment manifest tracker
przechowuje stan releases jako W15 obiekty) i W18 (event log jest persisted
jako W15 obiekt z lineage). Bez stabilnego W15 G2 cała warstwa v2 stoi.
PDF §2.2 (decyzja podjęta) jednoznacznie przesądza Wariant A: **lift W14 testing
ontology to W15** — czyli W15 zaczynamy od tego co już jest, refactor + migracja
SQLite→PG, side-by-side validation 1 tydzień, potem cutover.

## 2. Scope IN

- **Object Type Registry** — discovery i ładowanie manifestów YAML.
  - Lokalizacja: `sylion/aeis_v2/ontology/manifests/*.yaml` (built-in) +
    `~/.sylion/ontology/*.yaml` (user-defined).
  - Schema versioning — każdy manifest ma `version: 1.2.3` z semver semantyką.
  - Hot-reload w dev mode (file watcher), restart-required w prod.
  - Manifest validation: required fields, type constraints, FK resolution,
    cycle detection.

- **Object Storage Engine** — PostgreSQL 15+ jako primary backend.
  - **Hybrid storage**: pierwsze N "hot" properties (zdefiniowane w manifeście
    jako `indexed: true` lub `frequent: true`) jako dedicated columns,
    reszta w `properties JSONB`. Trade-off: query speed na hot fields vs
    schema flexibility.
  - DDL auto-gen: `CREATE TABLE`, indeksy B-tree, GIN na JSONB, foreign keys,
    triggery audytu.
  - Alembic-compatible migrations generated z diffu manifestu.
  - Connection pool: asyncpg z 10-50 connections.

- **Object Query API** — trzy presentation layers nad jednym storage.
  - **REST** (`/api/v2/ontology/{type}`) — list/get/create/update/delete +
    filtering (`?status=ACTIVE`), pagination (`?limit=50&offset=100`),
    sorting (`?order_by=-created_at`), expand (`?expand=lineage`).
  - **gRPC** — auto-gen z manifestu jako `OntologyService.{Type}.{Method}`,
    używa istniejącego `sylion.grpc` infra.
  - **OSDK** (Python auto-generated module) — `from sylion.osdk import Customer`,
    `Customer.objects.filter(status="ACTIVE").all()`. Type-safe, IDE
    completion, mypy-clean.

- **Action Types** — funkcje transformujące obiekty.
  - Manifest definiuje action: nazwa, parametry, D-level (D0-D5),
    HG required boolean, target ontology types, side-effects.
  - Dispatcher integruje się z istniejącym `sylion.surface.command_bus`.
  - Przy D3+ automatyczne wstrzyknięcie HG (Human Gate) przed execute.
  - Każdy invoke produkuje `ActionInvocation` (audit obj) z hash chain do
    poprzedniej akcji na tym targecie.

- **Lineage & Events** — hash-chained DAG operacji.
  - Każda mutacja obiektu produkuje `LineageEvent` z `prev_hash` (chain),
    `actor`, `action_type`, `payload_hash`, `timestamp`.
  - Replay lineage: `customer-123.lineage()` zwraca list of events od creation.
  - Integracja z istniejącym `sylion.core.evidence_spine` jako rozszerzenie.
  - Append-only — DELETE oznaczony jako `DELETED` event, fizyczne dane
    zostają w `_archived_<table>`.

- **Search & Index** — wbudowane wsparcie dla discovery.
  - `pg_trgm` na text properties dla fuzzy search.
  - B-tree na hot columns (zgodnie z manifestem).
  - GIN na `properties JSONB` dla queries po dowolnym polu (slower, ale
    backstop).
  - **Opcjonalnie pgvector** dla embedding-based semantic search (default
    OFF; włączane per type w manifeście jako `embeddings: true`).

- **W14 Migration** — concrete migration path zgodnie z PDF §6.3 (10 kroków).
  - 25 obiektów `sylion/aeis/testing/ontology/objects.py` → 25 manifestów
    YAML w `aeis_v2/ontology/manifests/w14/*.yaml`.
  - Side-by-side: nowy schemat PG równolegle z istniejącym SQLite, oba
    zapisują przez 1 tydzień, diff verifier.
  - Cutover decyzja na G3 z HG.

- **Branches & Sandboxing** — z W14 §12, podniesione na poziom W15.
  - `Branch` jako first-class W15 type. Każdy branch to copy-on-write
    namespace przez schema (PG schema-per-branch) lub virtual marker
    column (decision log: §13 Open Q).
  - Use cases: simulation environment dla W14 testing, A/B test changes
    przed merge, rollback-ready operations.

## 3. Scope OUT

- **Multi-tenant** — PDF §2.3, świadoma decyzja: SYLION jest dla Roberta, nie
  ma `tenant_id`. Re-evaluation w kontekście 10-os zespołu odłożona do W19
  (Open Q §9.1).
- **ACL per object / markings** — zostaje minimalny RBAC z
  `sylion.security.rbac`, brak fine-grained per-row policies.
- **OPA / rego** — PDF §2.5: minimal JSON rules zamiast OPA.
- **GraphQL** — REST + gRPC + OSDK pokrywają potrzeby. GraphQL adds
  complexity without proportional value dla single-user.
- **Apache AGE / dedicated graph DB** — graph queries zostają emulowane
  przez recursive CTE w PG (lineage walks). AGE / Neo4j out of scope.
- **Real-time WebSocket subscriptions** — push notifications via SSE
  (W18 territory). Ontology layer pozostaje request/response.
- **CRDT / multi-master replication** — single-master PG. Multi-node przez
  W17 Deployment Plane, nie W15.

## 4. Exit gates

### G1 — Foundation (week 4)
- **Deliverables**:
  - `sylion/aeis_v2/ontology/registry.py` — manifest discovery + load.
  - `sylion/aeis_v2/ontology/compiler.py` — YAML → DDL + REST + OSDK gen.
  - `sylion/aeis_v2/ontology/manifests/example_customer.yaml` — 1 example type.
  - PG migration `0050_w15_example_customer.py` generated automatycznie.
  - Schema compiler MVP: czyta YAML, produkuje DDL string, można aplikować
    przez `alembic upgrade head`.
  - 1 example type z REST CRUD + 1 OSDK example call w `examples/`.
  - Pytest: 30+ testów (registry load, compiler unit, schema diff).
- **Success criteria**:
  - Można dodać nowy YAML, uruchomić `make compile-ontology`, dostać
    działający REST endpoint w < 60s.
  - Compiler waliduje błędne manifesty (missing required fields, FK do
    nieistniejących typów, cycles) z czytelnymi error messages.
- **HG required**: NO (foundational, internal API)

### G2 — Core (week 8)
- **Deliverables**:
  - Wszystkie 8 functional SC (5.1) zielone.
  - 5 example types: Customer, Vehicle, Inspection, FundingApplication,
    DemoProject (każdy z 5+ properties + 1+ FK).
  - Action Types framework działa z 5 przykładami (1 D0, 2 D2, 2 D3 z HG).
  - OSDK Python module auto-gen dla wszystkich 5.
  - Lineage tracking enabled, hash chain weryfikowalny.
  - REST + gRPC + OSDK feature parity testowane equivalence suite.
  - Pytest: 200+ testów, coverage >= 85%.
- **Success criteria**:
  - Performance benchmark: 5.2 SC perf (1k objects insert < 5s, list 100
    < 100ms p95).
  - DX benchmark: 5.4 SC (nowy type od YAML do live REST < 5 minut).
- **HG required**: YES — Council vote przed promocją G2 (D5 milestone).

### G3 — W14 Migration (week 12)
- **Deliverables**:
  - 25 manifestów dla wszystkich W14 testing obiektów.
  - Migration script: SQLite W14 ontology → PG via OSDK, idempotent.
  - Side-by-side runtime: oba storage backends zapisują równolegle 7 dni.
  - Diff verifier: automatic cron porównuje row counts + sample diffs (10%).
  - Cutover plan: switch read path do W15 OSDK, SQLite read-only.
  - W14 test suite (732 tests) przechodzi na W15 ontology.
  - Rollback path: każdy z 10 kroków PDF §6.3 ma rollback documented.
- **Success criteria**:
  - Zero regression w W14 — wszystkie 732 testy zielone na W15.
  - Diff verifier 0 difference przez 7 dni side-by-side.
  - Performance W15 read >= W14 SQLite read (no degradation).
- **HG required**: YES — cutover to nieodwracalna operacja na production data.

### G4 — Production-ready (week 16)
- **Deliverables**:
  - Wszystkie 20 SC zielone.
  - W14SelfAudit (z E10) extended dla W15 health checks.
  - Dokumentacja: OSDK API reference, manifest schema reference, migration
    cookbook.
  - Disaster recovery: backup + restore drill, tested z prawdziwym snapshot.
  - 10+ types in production use.
  - Branch operations testowane na 3 use case'ach (simulation, A/B,
    rollback-staging).
  - 4-week soak run bez incidents.
- **Success criteria**:
  - Reliability SC (5.3) all green over 4 weeks.
  - Self-Audit returns `status: green` codziennie przez 4 tyg.
- **HG required**: YES — production promotion D5.

## 5. Success criteria

### 5.1 Functional (8)
1. **F-W15-01**: Manifest YAML z 5 typów properties (string, int, float,
   bool, datetime), 1 FK, 1 enum kompiluje do DDL w < 1s.
2. **F-W15-02**: REST endpoint dla nowego typu obsługuje CRUD + filter +
   pagination + sort bez kodowania routera.
3. **F-W15-03**: OSDK Python module auto-gen produkuje import-able klasę
   z type hints, mypy-clean.
4. **F-W15-04**: Action Type z `d_level: D3` automatycznie wstrzykuje HG
   przed execute, brak HG approval blokuje commit.
5. **F-W15-05**: Lineage event chain weryfikowalny — modyfikacja `prev_hash`
   in-flight wykryta przez `verify_chain()`.
6. **F-W15-06**: Schema migration 1.0 → 1.1 (add property) zachowuje dane,
   1.0 → 2.0 (breaking) wymaga explicit migration script.
7. **F-W15-07**: Branch operacje: create branch, mutate, diff, merge — 3 testy
   passing dla simulation use case.
8. **F-W15-08**: Search po `pg_trgm`: fuzzy match 80% similarity, optional
   pgvector dla embedding-based, oba przez OSDK.

### 5.2 Performance (4)
1. **P-W15-01**: Insert 1000 obiektów (5 props + 5 JSONB props) < 5s na
   laptopie referencyjnym (16GB RAM, NVMe).
2. **P-W15-02**: List 100 obiektów z filter na hot column + sort < 100ms
   p95 (n=10k baseline).
3. **P-W15-03**: OSDK call overhead vs raw asyncpg < 15% w benchmark.
4. **P-W15-04**: Manifest compile + DDL gen + apply dla nowego typu < 30s
   end-to-end.

### 5.3 Reliability (4)
1. **R-W15-01**: Crash w trakcie migration nie pozostawia partial state
   (transactional + journaled).
2. **R-W15-02**: Backup + restore drill: 1k obiektów, 100 lineage events,
   restore identyczny (verified by hash diff).
3. **R-W15-03**: Concurrent writes (10 workers, 100 ops each) bez data loss
   ani lost updates (test z optimistic locking).
4. **R-W15-04**: Hash chain weryfikacja po crash + restart — chain valid,
   brak orphaned events.

### 5.4 Developer Experience (4)
1. **DX-W15-01**: Nowy typ od YAML do live REST endpoint < 5 minut wall-clock
   dla deweloperza znającego konwencje.
2. **DX-W15-02**: Manifest validation errors zawierają line number, exact
   field path, suggested fix.
3. **DX-W15-03**: OSDK ma działające IDE completion (PyCharm + VSCode), mypy
   strict mode zielony.
4. **DX-W15-04**: Migration cookbook (Markdown) zawiera 5 typowych scenariuszy
   z run-able snippetami.

## 6. Top ryzyka

### R1: Manifest schema zbyt restrykcyjny — niektóre W14 obiekty się nie wpasują
- **Probability**: M
- **Impact**: H
- **Mitigation**: Pre-W15 phase Module Inventory & Classification (PDF §6.2,
  ~1-2 tyg) — przed G1 robi dry-run audit każdego z 25 W14 typów + 50
  najczęściej używanych v1 typów. Identifikuje "trudne" pattern (np.
  polymorphic FK, partial indexes na expression, computed columns) i albo
  rozszerza manifest spec, albo kwalifikuje typ do "hand-coded escape hatch"
  (klasa B → C migracja).
- **Trigger to escalate**: 3+ z 25 W14 typów wymagają escape hatch — wtedy
  re-design manifest spec (HG D4) zanim G1 idzie dalej.

### R2: Migracja SQLite → PG traci dane
- **Probability**: M
- **Impact**: H
- **Mitigation**: Side-by-side 7 dni przed cutover (G3 deliverable). Diff
  verifier compares row counts hourly + sample diff 10% daily. Rollback
  switch: jeden config flag w `~/.sylion/config.yaml` cofa read path do
  SQLite. Pre-migration backup obowiązkowy (PDF §6.5). 6 demo projects
  uruchomione na W15 jako acceptance test przed cutover.
- **Trigger to escalate**: Diff verifier pokazuje >0 difference w jakimkolwiek
  z 7 dni — pause migration, root cause, fix, restart 7-day window.

### R3: Performance JSONB extension fields gorsze niż oczekiwane
- **Probability**: H
- **Impact**: M
- **Mitigation**: Hybrid storage decyzja architektoniczna — hot fields jako
  dedicated columns, JSONB tylko dla "cold" / rzadko queried. Manifest
  pozwala escalować property z JSONB do dedicated column bez data loss.
  Benchmarks na realnych volumach W14 (10k findings, 1k charters) przed G2.
  Fallback: GIN index na `properties JSONB` z explicit ops `@>` zamiast
  `->>` na hot path.
- **Trigger to escalate**: P-W15-02 (list 100 < 100ms p95) failuje na 10k
  baseline → re-design hybrid threshold (HG D4).

### R4: DDL drift między manifest a actual PG schema
- **Probability**: M
- **Impact**: H
- **Mitigation**: Codzienny `ontology_audit` cron — porównuje aktualny
  `information_schema.columns` z compiled manifest, alertuje na drift.
  Każde DDL change idzie tylko przez `compile + alembic` pipeline; ręczne
  ALTER TABLE blokowane przez Guardian (W14 E5 wzorzec). Pre-deploy check
  w CI: `make ontology-verify` musi być zielony.
- **Trigger to escalate**: Drift wykryty bez audit log entry → security
  incident, freeze deploys, manual reconciliation pod HG.

### R5: OSDK regen breakages na schema changes
- **Probability**: H
- **Impact**: M
- **Mitigation**: OSDK ma deklarowany `compatibility_version` per generated
  module. Schema bump 1.0 → 1.1 (additive) — OSDK auto-regens, stary kod
  działa. Schema bump 1.x → 2.0 (breaking) — OSDK regens, ale generuje
  deprecation shim 2 minor releases ("`Customer.legacy_field` deprecated,
  use `Customer.new_field`"). CI runs OSDK consumer tests przed merge
  manifest changes. Lock file `osdk.lock` w consumer repos pinuje wersję.
- **Trigger to escalate**: Breaking change dotyka >5 callers — wymaga D4
  Council vote + 2-week migration window + migration guide.

## 7. Tech stack

| Component | Choice | Rationale |
|---|---|---|
| Storage | PostgreSQL 15+ | PDF §2.5 decyzja. JSONB perf, pg_trgm, optional pgvector, mature replication. |
| Driver | asyncpg | Async-native, ~3x faster than psycopg2 in benchmarks, pool support. |
| Migrations | Alembic | Auto-gen z SQLAlchemy metadata, rollback, audit log built-in. Konwencja AEIS v1. |
| Manifest format | YAML 1.2 | Human-readable, comment support, Robert ma już 50+ YAML manifestów w v1 (skills, devices). |
| Manifest validation | pydantic v2 + jsonschema | Pydantic dla type model, jsonschema dla cross-field rules. |
| OSDK gen | Custom Jinja2 templates | Pełna kontrola nad output kodem, type hints, async/sync flavors. |
| REST | FastAPI | Kontynuacja v1 stack, auto-OpenAPI, type-safe. |
| gRPC | grpcio + grpc-tools | Re-use `sylion.grpc` infra. |
| Search | pg_trgm + GIN | Built-in PG, brak ext deps. pgvector opt-in. |
| Branch impl | PG schema-per-branch | Native isolation, easy DROP SCHEMA dla cleanup. Alt: virtual column odrzucone z powodu query complexity. |
| Lineage | hash-chained event log w PG | Re-use evidence_spine wzorzec, append-only table z `prev_hash`. |
| Testing | pytest + asyncpg fixtures | Spójność z W14. |

## 8. Dependencies

- **Hard**:
  - PostgreSQL 15+ available locally (already in W14 release rail config).
  - `sylion.core.event_bus` (publish lineage events).
  - `sylion.surface.command_bus` (action dispatch).
  - `sylion.db.pg_migration` (alembic infra).
  - `sylion.security.rbac` (HG checks).
- **Soft**:
  - W14 E12 Agent Theater Aggregator (consumer of W15 events for telemetry).
  - W11 Adapter Bus (action handlers mogą wołać LLM).
  - W13 Advisor (jako consumer manifestów dla suggesterów).
- **Pre-W15 phase**:
  - Module Inventory & Classification (PDF §6.2, 1-2 tyg, dedicated phase
    PRZED G1) — `docs/v2/migration/MODULE_INVENTORY_CLASSIFICATION.csv`.

## 9. Modules created

- `sylion/aeis_v2/ontology/__init__.py` — public API exports.
- `sylion/aeis_v2/ontology/registry.py` — Object Type Registry: discover,
  load, validate, hot-reload manifestów.
- `sylion/aeis_v2/ontology/compiler.py` — Schema Compiler: YAML → DDL → REST
  → OSDK; orchestrator pipeline.
- `sylion/aeis_v2/ontology/osdk.py` — OSDK generator: template-driven
  Python codegen; produkuje module per manifest do `sylion/osdk/`.
- `sylion/aeis_v2/ontology/actions.py` — Action Types runtime: dispatcher,
  D-level mapping, HG injection, audit trail.
- `sylion/aeis_v2/ontology/lineage.py` — LineageEvent + hash chain + replay
  + verify; integration z `evidence_spine`.
- `sylion/aeis_v2/ontology/branches.py` — Branch lifecycle: create, mutate,
  diff, merge, drop. Uses PG schema-per-branch.
- `sylion/aeis_v2/ontology/manifests/` — directory dla built-in manifestów
  (W14 migrated + 5 example types).
- `sylion/api/ontology_routes.py` — auto-generated REST routers per type
  (mounted dynamically).
- `sylion/grpc/ontology_service.py` — auto-generated gRPC service per type.

## 10. Migration from v1

| Step | What | Rollback |
|---|---|---|
| 1 | **Manifest authoring**: 25 W14 testing types → YAML (zaczynamy od `Charter`, `Finding`, `Persona`). | Delete manifest files; W14 SQLite continues serving. |
| 2 | **DDL generation + verification**: `make compile-ontology --type charter`. Compare gen DDL z planowanym, manual diff review. | DDL niedeployed; brak side-effect. |
| 3 | **Data export from SQLite**: per-table JSONL dump z W14 ontology Store. | Dumps w `migrations/exports/`, delete jeśli niepotrzebne. |
| 4 | **Data transformation**: per-type transformer functions (handle enum casts, datetime ISO, FK resolution). | Versioned transformers — restart from JSONL. |
| 5 | **Bulk import to PG**: COPY z transformed JSONL. | TRUNCATE PG schema; SQLite still authoritative. |
| 6 | **Verification**: row count match + sample diff 10% per type. | Block migration jeśli mismatch; investigate. |
| 7 | **Code refactor**: 1 W14 module at a time użyje OSDK zamiast SQLite Store. | Per-module feature flag `USE_W15_OSDK=false`. |
| 8 | **Side-by-side test**: 7 dni dual-write, daily diff verifier. | Disable dual-write, SQLite primary. |
| 9 | **Cutover**: switch read path do PG/OSDK. SQLite read-only, dual-write off. | Toggle config flag back; SQLite primary read again. |
| 10 | **Cleanup** (T+30 dni): archive SQLite plików, remove W14 ontology code. | Restore from archive jeśli regression w Tx30+. |

Każdy krok ma dedicated test w `tests/aeis_v2/migration/` + `make w14-migration-rollback-{step}` polecenie.

## 11. D-level rationale

**D5** (najwyższy) ponieważ:
- Fundament dla całej v2 (W16 czyta manifesty, W17 trackuje deploys jako
  obiekty, W18 persists event log).
- **Nieodwracalna data migration** w G3 (SQLite → PG cutover).
- Jeden manifest spec serves 80% przyszłych typów AEIS — błąd w spec
  propaguje na 100+ typów, kosztowne reverse.
- Touches wszystkie 9 ról Council (architect, security, cost, perf, DX,
  PM, integrator, critic, sentinel) — żadna nie może być pominięta.
- HG required dla G2 promotion, G3 cutover, G4 production — 3 explicit
  Robert decisions po drodze.

Dlaczego nie D4: D4 zarezerwowane dla "important but reversible" — W15
G3 cutover *jest* technically reversible przez 30 dni (krok 10), ale po
cutover każda nowa akcja produkuje dane tylko w PG, więc rollback wymaga
backwards transformation = praktycznie nieodwracalne. → D5.

## 12. Test plan

- **Unit** (pytest):
  - `tests/aeis_v2/ontology/test_registry.py` — manifest discovery, validation,
    hot-reload, error messages. ~40 testów.
  - `tests/aeis_v2/ontology/test_compiler.py` — YAML → DDL determinism,
    diff scenarios, breaking change detection. ~50 testów.
  - `tests/aeis_v2/ontology/test_osdk.py` — generated module structure, type
    hints, mypy strict pass, runtime calls. ~30 testów.
  - `tests/aeis_v2/ontology/test_actions.py` — D-level routing, HG injection,
    audit chain. ~30 testów.
  - `tests/aeis_v2/ontology/test_lineage.py` — chain integrity, tamper
    detection, replay. ~25 testów.
  - `tests/aeis_v2/ontology/test_branches.py` — create/diff/merge/drop. ~20 testów.

- **Integration** (testcontainers PG):
  - `tests/aeis_v2/integration/test_manifest_to_rest.py` — end-to-end
    YAML → live REST → response. ~20 testów.
  - `tests/aeis_v2/integration/test_w14_migration.py` — pełny 10-step
    migration smoke z 100 fake findings. ~10 testów.
  - `tests/aeis_v2/integration/test_concurrent_writes.py` — 10 workers,
    100 ops, optimistic locking validation.

- **E2E** (real services):
  - `tests/aeis_v2/e2e/test_demo_project_on_w15.py` — 1 demo project z W14
    E11 reuruchomiony na W15, full lifecycle. ~5 testów.
  - `tests/aeis_v2/e2e/test_branch_simulation_e11.py` — branch jako sandbox
    dla destructive op, merge after success.

- **Performance benchmark** (`scripts/bench_w15.py`):
  - Insert 10k obj, list 100, lineage walk depth 50, OSDK call overhead.
  - Run on every PR with regression detection (>10% slowdown blocks merge).

- **Migration drill**:
  - `scripts/w14_to_w15_migration_drill.py` — pełna migracja 25 typów na
    realnym dump'ie testing DB, verify roundtrip, time it.

## 13. Open questions

- **Q1**: Branch impl — PG schema-per-branch (proponowane) vs virtual column
  marker. Schema-per-branch ma czystszą semantykę ale nie skaluje > 50
  branches (PG schema limit). Czy AEIS v2 ever potrzebuje > 50 concurrent
  branches? Przy 50+ branchach sugeruje to repurpose Git/event-sourcing,
  nie ontology branching.

- **Q2**: pgvector od G2 czy od G4? pgvector add complexity (binary install,
  CPU/RAM cost dla index build). Default OFF, opt-in w manifeście. Ale
  jeśli W13 Advisor zacznie używać semantic search early — pchnie do G2.

- **Q3**: gRPC service — auto-mount (jeden service per type, dynamic
  registration) vs explicit (developer registers). Auto-mount eleganckie,
  ale generated `.proto` mogą się rozjechać między klientami. Decision
  punkt: G1 spike.

- **Q4**: OSDK distribution — czy generated module idzie do osobnego repo /
  PyPI package, czy zostaje w sylion-pipeline (importable via
  `sylion.osdk.<type>`)? V1: in-repo. Roadmap: separate package gdy
  zewnętrzni konsumenci się pojawią (W17 federation territory).

- **Q5**: Manifest schema versioning evolution — czy manifest sam ma
  ontology version field (`schema: 1.0` vs `schema: 1.1`)? Jeśli tak,
  compiler musi obsługiwać oba. Jeśli nie, breaking changes w manifest
  format wymagają wszystkich consumers update jednocześnie. Decision
  punkt: G1 + Council vote.

- **Q6**: Lineage event retention policy — append-only forever vs cold
  storage po N dniach. Z 100+ events/sec (W18 territory) annual volume
  ~3B events. Cold storage do parquet po 90 dniach? Decision: G4 +
  Cost Sentinel review.

---

## Architectural Decision (2026-04-27)

See [ADR-001](../decisions/ADR-001-five-architectural-decisions-2026-04-27.md) — Decision #1.

**Resolved:** Hybrid extension JSONB validation with `extension_policy: strict|declared|free` declared per object type in manifest; `strict` is default; `free` objects blocked from production via Release Rail (W14 E6).
