# W17 Charter — Deployment Plane (hybrid)

> Status: **DRAFT** (2026-04-27)
> D-level: **D5**
> Estymacja solo: **16-20 tygodni**
> Depends on: **W15 G2 (HARD)**, **W16 G2 (HARD)**, AEIS v1 baseline
> (sylion.core.health_monitor, sylion.core.environment_orchestrator,
> sylion.core.evidence_spine, docker-compose stack).

## 1. Cel

W17 to **lekki control plane** dla zarządzania wieloma instancjami SYLION —
odpowiednik Palantir Apollo, ale w wersji "minimal viable" dla hybrid
local + central setup. Cel: Robert (i ewentualnie zespół 10 os.) zarządza
flotą instancji (laptop dev, VPS staging, fabryka klienta produkcja) z
**central plane**, gdzie każda instancja **może działać standalone offline**.

Dziś AEIS v1 jest single-instance: jeden `docker-compose up`, jedno
PostgreSQL, jeden frontend. Brak built-in mechanizmu na: deploy nowej
wersji na 5 instancji, sprawdzenie czy wszystkie healthy, rollback gdy
jedna fail. PDF §5.1 zarysowuje vision: **hybrid local + central** —
local instance jest zawsze nadrzędna (offline-capable), central plane
opt-in dla orkiestracji multi-node.

W17 oznaczony **D5** ponieważ:
- Touchuje **production deploy lifecycle** — błąd może powalić wszystkie
  instancje na raz.
- **Blue-green dla stateful PG** historycznie trudny problem (PDF §5.5 R1).
- **Audit trail jest hash-chained** zgodnie z `evidence_spine` wzorcem —
  niezgodność narusza compliance posture całego systemu.
- **Central plane jako single point of failure** (PDF §5.5 R2) wymaga
  particular care w fault tolerance.

PDF §2.5 decyzja: **docker-compose + Caddy reverse proxy**, NIE Kubernetes.
Decyzja świadoma — Robert + zespół nie chcą operate K8s overhead. Caddy
zamiast nginx dla auto-HTTPS i prostej konfiguracji. **Policy engine
minimal JSON rules**, NIE OPA/rego (PDF §2.5; PDF §5.5 R3 ostrzega o
prymitywizmie, mitigation w sekcji 6).

## 2. Scope IN

- **Local Mode** — każda instancja działa standalone offline.
  - `docker-compose.yml` z całym stack: PG, Redis, FastAPI backend,
    Next.js frontend, Caddy reverse proxy, optional Ollama.
  - `make local-up` / `make local-down` — pełen lifecycle.
  - Embedded TLS via Caddy (self-signed dla dev, Let's Encrypt opt-in).
  - Default: brak zewnętrznej zależności od central plane. Dane lokalne,
    backups lokalne.

- **Central Plane** — opcjonalny lekki FastAPI service.
  - Robert hostuje na własnym VPS (jednym), nie SaaS.
  - Endpoints: register node, heartbeat, query state, push deploy command,
    fetch deploy artifacts.
  - Storage: PostgreSQL (re-use W15 OSDK dla deploy-related ontology types
    jak `Node`, `Deployment`, `Release`).
  - HTTP API + dashboard (W16 app).
  - Auth: pre-shared token per node, mTLS opcjonalny.

- **Node Registry** — manifest, heartbeat, tags, lifecycle.
  - `node_manifest.yaml` per instancja:
    `name`, `tags` (np. `prod`, `eu-west`, `factory-customer-A`),
    `capabilities` (np. `gpu: true`, `models: [llama3, qwen2.5]`),
    `version`, `endpoint_url`, `pre_shared_secret`.
  - Heartbeat: HTTP POST co 30s do central z `health_aggregate` payload.
  - Lifecycle: `registered` → `active` → `draining` → `retired`.
  - Tags driven routing/grouping w deployment commands.

- **Version Manifest** — semver per moduł, build artifacts.
  - Każdy release ma `release_manifest.yaml`:
    `version: 2.5.3`, `modules: [{name: w15, version: 2.5.3}, ...]`,
    `artifacts` (docker images SHA256, Python wheel hashes),
    `migrations: [0050_w15_..., 0051_w16_...]`,
    `compat: {min_node_version: 2.4.0}`.
  - Version pinning per node — node deklaruje `target_version: 2.5.3`,
    central waliduje compat.
  - Semver semantyka: major bump = breaking, minor = additive, patch = bug.

- **Rollout Strategy** — blue-green, pre-flight, multi-node cascade.
  - **Pre-flight checks** (per node): version compat, disk space, free
    memory, PG accessibility, current health green.
  - **Blue-green**: nowy stack uruchamiany w "green" namespace
    (docker-compose project name `sylion-green`), PG schema migrated z
    online migration tool (osobno w sekcji 12), Caddy switch traffic do
    green po canary period.
  - **Multi-node cascade**: nodes sortowane po `tags` priority. Domyślny
    rollout: 1 staging → 1 prod canary (5min wait + health green) →
    rest of prod batch'ami po N (configurable).
  - Pause na każdym etapie: jeśli alert przekroczony, automatic pause +
    HG required.

- **Rollback** — automatic na fail w < 60s.
  - Auto-trigger criteria: health red > 60s po cutover, error rate > 5%
    over 30s, p99 latency > 2x baseline over 60s.
  - Caddy switch traffic z green do blue (pre-deployment stack), green
    deprovisioned async.
  - PG: rollback migration (alembic downgrade) jeśli safe migration
    (additive) lub PITR restore z snapshot pre-deploy (destructive).
  - Audit: każdy rollback produkuje W15 obiekt `Rollback` z reason,
    affected node, timing, MTTR.

- **Health Monitoring** — `/health/aggregate` + central scrape.
  - Each node exposes `GET /health/aggregate` zwracający JSON ze statusem
    każdego subsystem (PG, Redis, Ollama, FastAPI, frontend health,
    Guardians status z W14 E5).
  - Central plane scrape co 30s, persists do `Node.health_history` w W15.
  - Alerts (basic): `health: red` > 60s → notification.
  - Re-use `sylion.core.health_monitor` jako node-side aggregator.

- **Policy-as-Code** — minimal JSON rules.
  - Format: JSON z `rule_id`, `match` (selector), `conditions`, `actions`.
  - Przykład: `{rule_id: "prod_no_unstable", match: {tags: ["prod"]},
    conditions: {version_channel: "stable"}, actions: ["block_deploy"]}`.
  - Engine: pure Python evaluator (~300 LOC), brak JIT, brak external deps.
  - Rules stored w W15 jako `PolicyRule` type. Versioned.
  - **OUT**: rego, OPA — PDF §2.5 świadomy minimalizm. Open Q §13: kiedy
    rega evaluation reignite (W19?).

- **Configuration Management** — per-node overlays + secrets.
  - Base config: `config/base.yaml` (defaults dla wszystkich nodes).
  - Overlay: `config/{node_name}.yaml` (selective override).
  - Secrets: encrypted z `age` (modern alt to PGP), per-node decrypt key
    pre-shared.
  - Templating: minimal mustache-like dla expansion variables (np.
    `${NODE_TAGS}`, `${VERSION}`).
  - Reload bez full restart: signal `SIGHUP` lub `/admin/reload-config`
    endpoint.

- **Audit Trail** — hash-chained jak Evidence Spine.
  - Każda akcja deployment (deploy, rollback, config change, policy edit)
    produkuje audit event z `prev_hash` chain.
  - Storage: dedicated W15 type `DeployAuditEvent`, append-only.
  - Verify: `make w17-verify-audit` walks chain, validates, raise alert
    na break.
  - Re-use `sylion.core.evidence_spine` infra.

- **Multi-Environment** — dev/staging/prod jako YAML.
  - `environments/dev.yaml`, `environments/staging.yaml`, `environments/prod.yaml`
    deklaruje który node należy do którego env, deploy windows, policy
    enforcement level.
  - Promotion ścieżka: dev → staging → prod, każda wymaga green status na
    poprzednim etapie.

## 3. Scope OUT

- **Multi-tenant** — PDF §2.3 świadoma decyzja, single-user model.
- **Kubernetes Operators** — overkill, PDF §2.5. Re-eval w v3.x jeśli
  flota > 20 nodes.
- **Service mesh** (Istio, Linkerd) — overhead niepotrzebny przy
  docker-compose scale.
- **Distributed tracing full stack** (Jaeger, OpenTelemetry full pipeline) —
  basic OTel SDK init może być, ale brak central collector w W17 v1.
- **Auto-scaling per metrics** (HPA-equivalent) — single instances, manual
  scale up. Auto-scaling re-eval gdy traffic patterns to wymuszą.
- **Multi-cloud orchestration** — out of scope. Central plane jest jednym
  hostem, klienci na własnych VPS / on-premise.

## 4. Exit gates

### G1 — Local Mode Hardened (week 4)
- **Deliverables**:
  - `sylion/aeis_v2/deployment/local_mode.py` — local lifecycle helpers.
  - `sylion/aeis_v2/deployment/health_aggregator.py` — `/health/aggregate`
    endpoint.
  - `docker-compose.yml` z complete stack + Caddy + secrets injection.
  - `make local-up`, `make local-down`, `make local-deploy` polecenia.
  - Pre-flight checks (single-node) działają.
  - 1-node deploy z rollback działa end-to-end.
  - 30+ pytest, 5 integration tests.
- **Success criteria**:
  - Cold `make local-up` → healthy w < 90s.
  - Pre-flight catches: low disk, PG down, version mismatch.
  - Rollback po simulated bad deploy < 60s.
- **HG required**: NO (foundational).

### G2 — Central Plane MVP (week 8)
- **Deliverables**:
  - `sylion/aeis_v2/deployment/central_plane.py` — central FastAPI service.
  - `sylion/aeis_v2/deployment/node_registry.py` — register, heartbeat,
    state tracking (uses W15 OSDK).
  - `sylion/api/deployment_routes.py` — endpoints dla node ↔ central.
  - W15 ontology types: `Node`, `Deployment`, `Release`, `PolicyRule`.
  - Basic dashboard (W16 app: `apps/deployment_console`).
  - Multi-node deploy z 3 nodes (1 staging + 2 prod) działa.
  - 100+ pytest + 10+ integration tests.
- **Success criteria**:
  - 5.1 SC F-W17-01..F-W17-04 zielone.
  - Deploy do 3 nodes z cascade działa, healthy nodes całość.
- **HG required**: YES (D5 milestone, Council vote).

### G3 — Rollout & Rollback (week 12)
- **Deliverables**:
  - `sylion/aeis_v2/deployment/rollout_engine.py` — blue-green, cascade,
    pause/resume.
  - `sylion/aeis_v2/deployment/rollback_engine.py` — auto-trigger criteria,
    Caddy switch, PG migration handling.
  - `sylion/aeis_v2/deployment/policy_engine.py` — JSON rules evaluator.
  - PG online migration handling: classify migration jako `additive` vs
    `destructive`, decision tree dla rollback path.
  - Disaster recovery (DR) drill scripts: `scripts/dr_drill_*.py`.
  - 6+ end-to-end deploy + rollback scenarios w E2E tests.
- **Success criteria**:
  - 5.1 SC F-W17-05..F-W17-08 zielone.
  - Auto-rollback < 60s w 3 simulated failure scenarios (PG down, FastAPI
    crash, frontend 500s).
  - Policy: 5 rules block 5 wrong deploy attempts.
- **HG required**: NO (incremental).

### G4 — Production-ready (week 16-20)
- **Deliverables**:
  - Wszystkie 20 SC zielone.
  - DR drills pass: snapshot + restore, full re-bootstrap node.
  - Multi-environment (dev/staging/prod) configurated, promotion ścieżka
    działa.
  - Documentation: deployment guide, troubleshooting, DR runbook.
  - 4-week soak: 3+ realne deploys per week, zero unplanned downtime.
  - Audit trail integrity verified daily, zero break.
- **Success criteria**:
  - Reliability + Performance SC all green over 4 weeks.
  - MTTR (mean time to recover) < 5 minut na simulated incidents.
- **HG required**: YES (production promotion D5).

## 5. Success criteria

### 5.1 Functional (8)
1. **F-W17-01**: Local mode `make local-up` from clean state →
   wszystkie services healthy w < 90s.
2. **F-W17-02**: Node registers w central plane przez API token,
   heartbeat każde 30s, state visible w dashboard.
3. **F-W17-03**: Multi-node deploy 1 staging + 2 prod z cascade,
   pre-flight pass + canary + batch.
4. **F-W17-04**: Health aggregator zwraca JSON z 5+ subsystem statuses,
   parseable przez central scrape.
5. **F-W17-05**: Auto-rollback wykonuje się w < 60s gdy criterion
   przekroczony (health red 60s).
6. **F-W17-06**: Policy rule blokuje deploy unstable build do prod tag,
   z czytelnym error message.
7. **F-W17-07**: Audit trail każdej deployment akcji hash-chained,
   `make w17-verify-audit` zielony.
8. **F-W17-08**: PG online migration (additive) deployed bez downtime,
   destructive migration flagged + wymaga HG.

### 5.2 Performance (4)
1. **P-W17-01**: Multi-node cascade 5 nodes, default pacing → total deploy
   time < 30 minut (5min canary + 4×3min batch + verification).
2. **P-W17-02**: Health aggregator endpoint < 100ms p95 (no I/O blocking).
3. **P-W17-03**: Policy engine evaluation 100 rules < 50ms.
4. **P-W17-04**: Auto-rollback latency (detect → traffic switch → green
   ready) < 60s p95.

### 5.3 Reliability (4)
1. **R-W17-01**: Central plane crash → nodes kontynuują działanie offline,
   reconcile po central recovery.
2. **R-W17-02**: Node network partition (5 min) → state reconciliation
   pose recovery, brak data loss.
3. **R-W17-03**: Concurrent deployments (2 simultaneous) na różnych nodes
   nie kolidują, każdy ma own audit chain.
4. **R-W17-04**: Audit trail integrity weryfikowalny daily, break automatic
   alerts (Guardian + email/Slack/console).

### 5.4 Developer Experience (4)
1. **DX-W17-01**: Robert deployuje nową wersję na flotę 5 nodes 1 komendą
   (`sylion deploy --version 2.5.3 --env prod`) bez ręcznej interwencji.
2. **DX-W17-02**: Deploy progress real-time w dashboard z per-node status,
   rollback button always available.
3. **DX-W17-03**: Pre-flight failure raporty zawierają root cause +
   suggested fix.
4. **DX-W17-04**: DR runbook (`docs/dr_runbook.md`) testowany monthly,
   procedura execute-able przez junior dev w < 30 minut.

## 6. Top ryzyka

### R1: Blue-green dla stateful PG historycznie trudny
- **Probability**: H
- **Impact**: H
- **Mitigation**: PG migration classification jako pierwszorzędny obowiązek:
  `additive` (add column, add index CONCURRENTLY, add table) → blue-green
  bezpieczne, oba stack'y mogą równolegle czytać/pisać. `destructive`
  (drop column, alter type, rename) → blue-green NIE działa, fallback do
  maintenance window deploy z downtime <2 min. Wszystkie PG migrations
  generated przez W15 schema compiler są klasyfikowane automatycznie
  (compiler analizuje DDL diff). Każda destructive migration wymaga HG
  D4 + dedicated migration window. **Online schema migrations tools**
  (np. `pg-osc` lub własny wrapper) opcjonalnie dla complex destructive
  scenarios w v2 plan.
- **Trigger to escalate**: 3+ destructive migrations w jednym release →
  freeze release, redesign jako serię additive (HG D4).

### R2: Central plane jako single point of failure
- **Probability**: M
- **Impact**: H
- **Mitigation**: Decyzja architektoniczna: **central plane jest opcjonalny**.
  Local instances działają w pełni offline (PDF §2.4). Central plane
  utracony = brak orkiestracji multi-node, ale nodes kontynuują działanie.
  Reconcile po central recovery: nodes batch'ują pending heartbeats, queue
  deploy commands w local store, replay przy reconnection. Central plane
  sam ma backup: PG snapshot daily + WAL archive, restore < 30 minut.
  Central plane stateless poza PG — można re-bootstrap z innego VPS w
  < 1h. Brak konieczności HA cluster.
- **Trigger to escalate**: Central downtime > 24h → trigger DR procedure,
  rebuild from backup, post-mortem.

### R3: Policy engine za prymitywny — Robert chce rego później
- **Probability**: H
- **Impact**: M
- **Mitigation**: Świadoma decyzja PDF §2.5: minimal JSON rules dla v2.
  Mitigation:
  - Architecture allows pluggable engine: `PolicyEngine` interface, JSON
    impl jako default, OPA impl jako future.
  - Rules expressiveness audit: lista 30+ realnych use cases, konfront z
    JSON capacity. Jeśli >5 wymagają nieoczekiwane patterns → znak że
    rega potrzebny już teraz.
  - W19 (Policy Plane) zaplanowany jako separate charter, decision punkt
    PDF §9.1 (kontekst 10-os zespołu).
- **Trigger to escalate**: Rules require complex computed fields, transitive
  evaluation, lub 100+ rules → HG D4 wprowadź OPA jako alternatywa engine.

### R4: Central plane authentication / authorization
- **Probability**: M
- **Impact**: H
- **Mitigation**: V1: pre-shared token per node + mTLS opcjonalny. Tokens
  rotated every 90 dni przez `sylion rotate-tokens` polecenie. Audit każdego
  failed auth. Brute force protection: rate limit per IP (Caddy level).
  Token storage: encrypted via `age` w `~/.sylion/secrets/`. NIE OAuth2 /
  OIDC w v1 — overkill dla flota 5-10 nodes. V2 (W19): RBAC integration
  z zespołem dla central console access.
- **Trigger to escalate**: Token leak incident → emergency rotate
  wszystkie tokens, audit affected nodes (HG D5 incident response).

### R5: Configuration drift — node config rozjazd z central manifest
- **Probability**: M
- **Impact**: M
- **Mitigation**: Codzienny `config_drift_audit` cron (Guardian wzorzec
  W14 E5) — central pyta każdy node `GET /admin/effective-config` (hash
  only), porównuje z expected per-node manifest. Drift detected →
  alert + auto-suggest reconcile (apply central config + restart). Każda
  manual zmiana config na node generuje audit event z `actor` (kto, kiedy).
- **Trigger to escalate**: Drift > 1h bez audit log entry → security
  incident, freeze deploys do reconcile.

## 7. Tech stack

| Component | Choice | Rationale |
|---|---|---|
| Container runtime | docker + docker-compose | PDF §2.5; już używane w v1; Robert+team familiar. |
| Reverse proxy | Caddy v2 | PDF §2.5; auto-HTTPS, prosta konfiguracja, hot reload. |
| Backend (central) | FastAPI | Spójność z v1; async; asyncpg. |
| Storage | PostgreSQL 15+ przez W15 OSDK | Spójność z W15; ontology types dla deploy obj. |
| Frontend (dashboard) | W16 app `apps/deployment_console` | Eat own dogfood. |
| Health monitoring | własny health_aggregator + Caddy probes | Lightweight; integration z `sylion.core.health_monitor`. |
| Policy engine | Custom JSON evaluator (~300 LOC Python) | PDF §2.5 minimalizm. |
| Secrets | `age` (modern alt do PGP) + per-node decrypt key | Lightweight, modern, no GPG complexity. |
| PG migrations | Alembic (additive) + custom classifier | Re-use W15 alembic infra, classifier flaguje destructive. |
| Online schema | pg-osc lub własny wrapper | Optional dla destructive migrations. |
| DR snapshots | pg_basebackup + WAL archive (S3 / local) | Standard PG, lightweight. |
| Inter-node RPC | HTTP + JSON (z mTLS opcjonalny) | Simple, debuggable; brak gRPC overhead w v1. |
| Audit storage | W15 type `DeployAuditEvent` + hash chain | Re-use `evidence_spine` patterns. |
| Testing | pytest + testcontainers + own multi-node harness | Multi-node integration testowane w docker-compose CI. |

## 8. Dependencies

- **Hard**:
  - **W15 G2** — OSDK dla deploy ontology types, hash chain audit.
  - **W16 G2** — `deployment_console` jako W16 app (dashboard).
  - `sylion.core.evidence_spine` — wzorzec hash chain.
  - `sylion.core.health_monitor` — node-side health aggregator.
  - `sylion.core.environment_orchestrator` — environment lifecycle.
  - Docker engine + docker-compose v2 dostępny na nodes.
- **Soft**:
  - W14 Guardians (E5 wzorzec audit + drift detection).
  - W18 Operator Terminal (deploy events streamowane do terminal).
  - W11 (jeśli central plane potrzebuje LLM dla diagnostic).

## 9. Modules created

- `sylion/aeis_v2/deployment/__init__.py` — public API.
- `sylion/aeis_v2/deployment/local_mode.py` — local lifecycle, docker-compose
  helpers, pre-flight checks.
- `sylion/aeis_v2/deployment/central_plane.py` — central FastAPI service:
  registry, heartbeat, deploy orchestration.
- `sylion/aeis_v2/deployment/node_registry.py` — node registration,
  heartbeat ingestion, state tracking via W15 OSDK.
- `sylion/aeis_v2/deployment/health_aggregator.py` — node-side
  `/health/aggregate` endpoint logic.
- `sylion/aeis_v2/deployment/version_manifest.py` — release manifest
  parser, semver compat checker.
- `sylion/aeis_v2/deployment/rollout_engine.py` — blue-green, cascade,
  pause/resume, canary timing.
- `sylion/aeis_v2/deployment/rollback_engine.py` — auto-trigger criteria,
  Caddy traffic switch, PG migration unwind.
- `sylion/aeis_v2/deployment/policy_engine.py` — JSON rules evaluator,
  pluggable interface dla future OPA.
- `sylion/aeis_v2/deployment/config_manager.py` — per-node overlay,
  secrets, hot-reload.
- `sylion/aeis_v2/deployment/audit.py` — hash-chained DeployAuditEvent
  recorder.
- `sylion/api/deployment_routes.py` — REST endpoints.
- `apps/deployment_console/app.yaml` — W16 dashboard app.
- `scripts/dr_drill_*.py` — DR procedure scripts.
- `docs/dr_runbook.md` — disaster recovery runbook.

## 10. Migration from v1

| Step | What | Rollback |
|---|---|---|
| 1 | **Audit current local stack**: docker-compose v1, Caddy config, scripts. Output: `docs/v2/migration/V1_DEPLOY_INVENTORY.md`. | Audit-only. |
| 2 | **Pilot Local Mode** na dev laptop: re-create docker-compose z W17 conventions, side-by-side z v1 stack. | Disable W17 stack, v1 docker-compose primary. |
| 3 | **Health aggregator deployment**: wdrażamy `/health/aggregate` na 1 node, bez central plane (standalone). | Endpoint backward-compat z `/health` v1, no removal. |
| 4 | **Central Plane bootstrap** na VPS Roberta: instal central FastAPI, register pierwszy node (laptop). | Central plane idle, nodes kontynuują działanie. |
| 5 | **Wave 1**: dodaj 1 staging VPS jako 2nd node, deploy z central → staging via cascade. | Per-node feature flag `USE_W17_DEPLOY=false`, manual deploy. |
| 6 | **Migration test**: simulate prod release przez staging → 1 prod canary, verify auto-rollback. | Rollback path proven. |
| 7 | **Wave 2**: prod nodes joined, batch deployment ścieżka. | Decommission per node jeśli regression. |
| 8 | **Cleanup v1 deploy scripts**: po 30 dni stable z W17. | Restore from git history. |

PDF §6.1 wersjonowanie: AEIS v3.0 = W15 + W16 + W17 G4. W17 dostarcza
production-grade deploy lifecycle. v3.0 promotion wymaga 4-week soak
(G4 SC).

## 11. D-level rationale

**D5** (najwyższy):
- **Production deploy lifecycle** — błąd może powalić wszystkie instancje
  na raz (catastrophic blast radius).
- **Stateful PG cutover** — destructive migration błędnie sklasyfikowana
  jako additive może utracić dane.
- **Audit trail integrity** — break w hash chain narusza compliance posture
  całego systemu.
- **Auto-rollback decyzje są nieodwracalne** w czasie incident — błędna
  rollback po false-positive criterion = unnecessary downtime.
- **HG required**: G2, G4, każdy destructive migration deploy, każdy
  policy rule change w prod tag.

Dlaczego nie D4: D4 dla "important but reversible" — W17 deploy decisions
dotyczą żywych production instances z user data, niewystarczająco
reversible po committed migrations. → D5.

## 12. Test plan

- **Unit** (pytest):
  - `tests/aeis_v2/deployment/test_local_mode.py` — pre-flight, lifecycle,
    healing.
  - `tests/aeis_v2/deployment/test_node_registry.py` — register, heartbeat,
    state transitions.
  - `tests/aeis_v2/deployment/test_version_manifest.py` — semver parsing,
    compat matrix.
  - `tests/aeis_v2/deployment/test_rollout_engine.py` — blue-green logic,
    cascade timing, pause/resume.
  - `tests/aeis_v2/deployment/test_rollback_engine.py` — trigger criteria,
    Caddy switch, PG unwind decision tree.
  - `tests/aeis_v2/deployment/test_policy_engine.py` — rules evaluation,
    edge cases, performance.
  - `tests/aeis_v2/deployment/test_audit.py` — hash chain integrity,
    tamper detection.
  - `tests/aeis_v2/deployment/test_config_manager.py` — overlay merging,
    secrets decrypt, hot-reload.

- **Integration** (multi-container z testcontainers):
  - `tests/aeis_v2/integration/test_local_to_central.py` — node register
    → heartbeat → central state sync.
  - `tests/aeis_v2/integration/test_3node_cascade_deploy.py` — pełen cascade
    z verification.
  - `tests/aeis_v2/integration/test_auto_rollback.py` — simulated failure
    triggers rollback.
  - `tests/aeis_v2/integration/test_pg_additive_migration.py` — additive
    migration deployed bez downtime.
  - `tests/aeis_v2/integration/test_pg_destructive_migration.py` —
    destructive flagged, HG required.

- **E2E** (real multi-host, dedicated test cluster):
  - `e2e/deploy/test_full_release_lifecycle.sh` — release artifact build →
    deploy do 3 nodes → verify → rollback drill.
  - `e2e/deploy/test_dr_drill.sh` — full disaster: simulate central plane
    crash → restore from backup → verify.
  - `e2e/deploy/test_network_partition.sh` — partition node from central
    5min → verify reconciliation post-recovery.

- **Performance benchmark**:
  - `scripts/bench_w17.py` — cascade timing dla 5/10/20 nodes,
    health aggregator latency, policy engine z 1k rules.

- **Chaos engineering** (opt-in, post-G3):
  - Random node kill during deploy.
  - PG slow query injection.
  - Central plane network jitter.
  - Goal: weryfikacja R-W17-01..R-W17-04.

- **DR drills** (recurring):
  - Monthly snapshot + restore verification.
  - Quarterly full re-bootstrap node.
  - Bi-annual full central plane rebuild.

## 13. Open questions

- **Q1**: Multi-tenant w przyszłości? PDF §2.3 świadomie odrzucone, ale
  z 10-os zespołem (PDF §9.1 open Q) może wrócić jako W19. Wpływ na W17:
  jeśli yes, `Node` ontology potrzebuje `tenant_id`, RBAC per node group.
  Plan: re-eval na G4.

- **Q2**: Rollback PG destructive migration — ostateczny wzorzec?
  Opcje: (a) PITR restore z snapshot pre-deploy (data loss = changes
  od deploy), (b) reverse migration script (manualnie napisany per
  destructive op, wymaga discipline), (c) maintenance window + pre-deploy
  full backup. V1: kombinacja (a) + (c). V2 (G4+): rozważ (b) dla
  najczęstszych patterns.

- **Q3**: Central plane HA — czy ever potrzebne? V1: single instance,
  brak HA. Z 10-os zespołem może być nice-to-have. Decyzja: post-G4
  jeśli incident-driven need.

- **Q4**: Compute Provider Federation (PDF §8.4) — czy włączone do W17 G4
  czy odłożone do v3.x? Federation routing (task → compute provider)
  wymaga: privacy levels per task, capability tagging w nodes (już w
  Node manifest), routing engine. **Recommendation: split do W17.5
  (separate phase post-G4) lub ekstension W17 G5 +6-8 tyg**.

- **Q5**: Policy engine evolution — kiedy migrate do OPA? PDF §2.5 minimal
  JSON. Planowany trigger: 100+ rules lub policy expressiveness gap. W19
  Policy Plane może provide answer.

- **Q6**: Node onboarding self-service vs central-driven? V1: central
  generates token, sysadmin manually applies. V2: bootstrap script
  przyjazny operator (download script, run, follow prompts).

- **Q7**: Deploy artifact distribution — pull (nodes pull from central
  artifact store) vs push (central pushes do nodes). V1: pull (node
  decides timing per pre-flight), brak push do nodes z prod tag bez
  explicit ack. Zmiana paradygmatu: lazy pull post-confirmation.

- **Q8**: Observability stack — czy włączamy OpenTelemetry SDK init w v1
  z plan na zewnętrzny collector w v2? Decision: G2 spike (lightweight
  init OK), full pipeline w v3.x.

---

## Architectural Decision (2026-04-27)

See [ADR-001](../decisions/ADR-001-five-architectural-decisions-2026-04-27.md) — Decision #3.

**Resolved:** Cost-ledger persistence is hybrid — event-sourced ground truth (`cost.recorded` events on event_bus, immutable + hash-chained) plus PG materialized view `mv_cost_ledger` refreshed every 30s for fast queries. Reads from view, audits from events. Refresh-frequency tuning (trigger-based for active sessions, cron for historical) is open sub-question for W17 G2 spike.
