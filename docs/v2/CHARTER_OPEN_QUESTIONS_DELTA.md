# SYLION AEIS v2 — Open Questions Delta

> Zebrane otwarte pytania z 5 charterów (W15-W19) + PDF §9 "Otwarte
> pytania wymagające decyzji".
> Status: **DRAFT 2026-04-27** — operator weryfikuje przed planowaniem
> Wave 3.
> Autor: Claude (orchestrator) dla Roberta. Cel: przekuć charterowe
> "Open questions" na konkretne propozycje rozstrzygnięć z trade-offem,
> tak żeby Robert mógł podjąć decyzje seryjnie zamiast każdorazowo
> rozważać od zera. Każde Q ma proponowaną odpowiedź. **Wszystko jest
> propozycją — żadna decyzja nie została podjęta przez Claude.**

---

## Sumaryczna liczba

| Charter | Open Q count (charter §13) | Pokryte w sekcjach 1-4 (deep) | Pokryte w sekcji 6b (quick) | Decisions wymagane przed Wave 3 |
|---|---|---|---|---|
| W15 Ontology Runtime | 6 | 6 | 0 | 3 (Q1, Q2, Q5) |
| W16 Apps Builder | 7 | 2 (Q1, Q3) | 5 (Q2,Q4,Q5,Q6,Q7) | 2 (Q1, Q5) |
| W17 Deployment Plane | 8 | 4 (Q2,Q4,Q7,Q8) | 4 (Q1,Q3,Q5,Q6) | 4 (Q2, Q4) |
| W18 Operator Terminal | 10 | 5 (Q1,Q2,Q6,Q9,Q10) | 5 (Q3,Q4,Q5,Q7,Q8) | 3 (Q1, Q9) |
| W19 Policy Plane | 10 | 6 (Q1,Q3,Q4,Q6,Q8,Q10) | 4 (Q2,Q5,Q7,Q9) | 5 (Q1, Q3, Q6) |
| PDF §9 (meta) | 8 | 8 | 0 | 6 (9.1, 9.2, 9.4, 9.6, 9.7, 9.8) |
| Cross-cutting (CROSS) | 7 (derivative) | 7 | 0 | 4 (CROSS-1, CROSS-2, CROSS-4, CROSS-5) |
| **Razem** | **49 + 7 cross** | **38** | **18** | **23 blokujące Wave 3** |

**Suma per kategoria** (po deduplikacji cross-references):

| Kategoria | Liczba Q | Komentarz |
|---|---|---|
| Technical (kod, data model, infra) | 19 | branch impl, SSE/WS, redaction engine, hash chain w GDPR, OPA pluggable, etc. |
| Scope (co IN / co OUT, kiedy) | 12 | Federation (W17 Q4), Builder UI scope (W16 R3), W18 timing (PDF 9.7), retencja eventów (W18 Q9, W19 Q5) |
| Team / process (10 os.) | 11 | wszystkie PDF §9 + W19 (departure scope, MFA, IdP) |
| Cross-cutting (≥2 planes) | 7 | W19↔W17 auth (Q3 W17 / Q1 W19), W19↔W18 redaction, retention W19↔wszyscy, multi-tenant rewindowanie |

---

## 1. Decyzje techniczne (kod / data model)

### Q-W15-1: Branch implementation — schema-per-branch vs virtual column

- **Source**: charter W15 §13 Q1
- **Kategoria**: technical
- **Stake**: scalability. PG ma limit ~10000 schemas teoretycznie, ale
  przy każdym branchu schema = 25+ tabel × 6 indeksów = 150+ obiektów,
  realistyczny pułap ~50-100 concurrent branches przed metadata bloat.
- **Proponowana odpowiedź**: **schema-per-branch dla v2**, hard limit
  50 active branches enforced przez Guardian. Branch lifecycle:
  `create` → `mutate` → `merge | abandon` w < 30 dni. Stale branches
  > 30 dni auto-archived (DROP SCHEMA + dump do `archive/`).
- **Trade-off**: tracimy elastyczność dla > 50 concurrent (np. ekstremalne
  A/B testowanie z 200 wariantami), zyskujemy native PG isolation
  (DROP SCHEMA dla cleanup, brak FK pollution, query plans clean).
  Virtual column wymagałby modyfikacji każdego query w OSDK —
  `WHERE branch_id = current` propagowane wszędzie, łatwo o leak.
- **Decision owner**: Robert (architecture call) na G1 spike (1 tyg)
- **HG**: NO (foundation decision, nie touchuje danych prod)

### Q-W15-3: gRPC service — auto-mount vs explicit registration

- **Source**: charter W15 §13 Q3
- **Kategoria**: technical
- **Stake**: integration story dla zewnętrznych konsumentów. Auto-mount
  oznacza że nowy YAML manifest = automatyczny gRPC service bez deploy.
  Explicit registration wymaga code change.
- **Proponowana odpowiedź**: **auto-mount z compatibility lock**.
  Generated `.proto` versioned (np. `customer_v1.proto`,
  `customer_v2.proto`), klienci pinują `proto_version` w build time.
  Schema bump 1.0→1.1 (additive) auto-generates `customer_v1_1.proto`,
  klienci stary ciągle działają.
- **Trade-off**: auto-mount = elegancja + DX, ale wymaga discipline
  w `.proto` versioning. Explicit = pełna kontrola, ale dev friction
  per nowy typ.
- **Decision owner**: Robert + Claude (G1 spike result)
- **HG**: NO

### Q-W15-5: Manifest schema versioning evolution

- **Source**: charter W15 §13 Q5
- **Kategoria**: technical
- **Stake**: jeśli compiler musi obsługiwać multiple schema versions
  równolegle, codebase rośnie. Jeśli tylko jedna — breaking changes
  w manifest format wymagają simultaneous update wszystkich consumers.
- **Proponowana odpowiedź**: **manifest deklaruje `schema: 1.x`**, compiler
  obsługuje **N i N-1** (current + previous major). Schema bump 1.x → 2.0
  wymaga 90-day deprecation window: oba schemy compileable, deprecation
  warnings na 1.x. Po 90 dniach — drop wsparcie 1.x w compiler.
- **Trade-off**: dwa code paths przez 90 dni = 2x test surface. Bez tego
  — flag day cutover, bardzo ryzykowny.
- **Decision owner**: Robert + Council (G2 milestone)
- **HG**: NO (wewnętrzna spec ewolucji)

### Q-W17-2: Rollback PG destructive migration — ostateczny wzorzec

- **Source**: charter W17 §13 Q2
- **Kategoria**: technical
- **Stake**: niewłaściwy wybór = potencjalna data loss przy incident.
- **Proponowana odpowiedź**: **kombinacja (a) + (c) jako default,
  rezerwa dla najczęstszych patterns**. Konkretnie:
  - Default: PITR restore z snapshot pre-deploy (data loss = changes od
    deploy do incident, akceptowalne dla < 30 min window).
  - Mandatory: pre-deploy full backup obowiązkowy dla każdej destructive
    migration (HG D4 jeśli pominięty).
  - Maintenance window: deploys destructive idą w nocnym oknie 2-4 AM
    UTC, zaplanowane z 24h advance, downtime < 5 min.
  - Future (G4+): reverse migration script ZBUDOWANY automatycznie dla
    common patterns (DROP COLUMN → ADD COLUMN; ALTER TYPE → ALTER TYPE
    back), ale tylko dla 3-5 typowych transformations. Reszta = manual.
- **Trade-off**: opcja (b) reverse scripts brzmi atrakcyjnie ale
  wymaga discipline operatora pisać oba kierunki — rzadko praktyczne.
  PITR + snapshot to "głupi i niezawodny" wzorzec, koszt = downtime
  okresowy.
- **Decision owner**: Robert (production ops decyzja)
- **HG**: YES (D4) — każdy destructive deploy wymaga HG przed wdrożeniem

### Q-W18-1: SSE vs WebSocket dla terminal stream

- **Source**: charter W18 §13 Q1
- **Kategoria**: technical
- **Stake**: scaling przy 1000 events/sec sustained. SSE jest
  uni-directional (server → client), WS bi-directional ale z większym
  overhead.
- **Proponowana odpowiedź**: **start z SSE (PDF §7.4), prepare WS adapter
  jako drop-in replacement**. Interface `EventStream`, dwie impl
  (`sse_stream.py`, `ws_stream.py`). G2 deploy SSE, G4 benchmark
  pokazuje czy threshold (1k ev/sec, frame time < 16ms) jest met. Jeśli
  nie — switch do WS w G4+ (ENV flag, 1 dzień rollout).
- **Trade-off**: dwie implementacje to duplicate test surface (~30%
  overhead), ale interface czysty. Bez przygotowania — switch z SSE do
  WS w produkcji = 2-tygodniowa migracja.
- **Decision owner**: Robert (architectural; mała stake bo plug-in)
- **HG**: NO

### Q-W18-9: Replay storage retention — 30 hot + cold archive vs all-hot

- **Source**: charter W18 §13 Q9
- **Kategoria**: technical (cost-driven)
- **Stake**: 1k ev/sec × 86400 × 30 dni = 2.6B events ~ 520GB. All-hot
  do 7 lat = ~ 12TB. Storage cost realny.
- **Proponowana odpowiedź**: **tiered: 30 dni hot (PG partitioned) + 11
  miesięcy warm (PG cold partition + compression) + 7 lat cold (parquet
  na local SSD + S3 mirror)**. Hash chain crosses tiers przez
  reference index (`{tier, archive_url, hash}` w hot index nawet
  po archive). Replay z cold partycji = 5-10x slower ale acceptable
  dla rare query (forensics, compliance audit).
- **Trade-off**: kompresja oszczędza ~70% storage przy 5-10ms read
  overhead. Bez tieringu — > 12TB hot to drogie i wolne queries.
- **Decision owner**: Robert + Cost Sentinel (G2 review)
- **HG**: NO (operational decision, reversible)

### Q-W19-3: GDPR right-to-erasure vs hash-chain audit log

- **Source**: charter W19 §13 Q3
- **Kategoria**: technical (compliance)
- **Stake**: niewłaściwa decyzja = niezgodność GDPR (kara do 4% revenue)
  LUB broken audit chain (compliance issue SOC 2).
- **Proponowana odpowiedź**: **(a) tombstone pattern**. Wpis w audit
  log pozostaje z oryginalnym `hash`, ale `payload` zerowany / encrypted
  z erasure key następnie destroyed. Metadata (kto, kiedy, jaki typ
  event) preserved. Sam fakt erasure audytowany jako `gdpr.erased`
  event w nowym chainie. Technically GDPR-compliant — dane
  "anonimizowane" zgodnie z art. 17 GDPR + recital 26.
- **Trade-off**: opcja (b) full erase psuje chain — ryzyko compliance
  (jeśli auditor sees `chain integrity broken` — incident); opcja (c)
  re-rooted chain wymaga careful indexing. Tombstone najbliższy do
  "best of both worlds" ale wymaga że krypto jest correct (encryption
  key actually destroyed, nie zachowany).
- **Decision owner**: Robert + legal review (Council vote pre-G3)
- **HG**: YES (D5, compliance-impact decyzja)

### Q-W19-6: Policy-as-Code — minimal JSON vs OPA/rego

**STATUS: RESOLVED 2026-04-27** — YAML + sandboxed jinja2 default; pluggable engine retained; OPA/Rego pivot only if transitive relationships emerge. **PARKED**: full evaluator + Release Rail enforcement deferred until W15/W16/W17/W18 + W7/W11/W13 are feature-complete (security applied last). See [ADR-001](decisions/ADR-001-five-architectural-decisions-2026-04-27.md) Decision #4.

- **Source**: charter W19 §13 Q6 + W17 §13 Q5
- **Kategoria**: technical (cross-cutting W17 + W19)
- **Stake**: rega adds dependency (Open Policy Agent binary, sidecar
  process), ale wnosi expressiveness. JSON minimal jest "stupid simple"
  ale może hit limits przy 100+ rules.
- **Proponowana odpowiedź**: **pluggable engine od początku**. Interface
  `PolicyEngine` z dwoma impl: `JsonPolicyEngine` (default, ~300 LOC,
  no deps) + `OpaPolicyEngine` (future, opt-in via config flag
  `policy_backend: opa`). Trigger do migracji: 100+ rules w
  policy_matrix LUB compliance auditor wymaga rego standard. JSON
  expressiveness audit dokumentowany — list 30 realnych rules per
  W17 + W19, mapowane na JSON capacity. Jeśli > 5 nie pasują → trigger
  wcześniej.
- **Trade-off**: pluggable interface = 1 dzień setup + dyscyplina
  (każda rule pisana w sposób backend-agnostic). Bez interface — rega
  migration = tygodnie code rewrite.
- **Decision owner**: Robert (post-G4 decision punkt z konkretnymi
  metrykami: rule count, complexity score)
- **HG**: NO (architectural prep, decision deferred)

### Q-W19-10: Cross-charter `retention_days` — backward compatibility

- **Source**: charter W19 §13 Q10
- **Kategoria**: technical (W19 → W15 cascade)
- **Stake**: nowy field w W15 manifest spec wpływa na 25+ existing types.
  Default value crucial.
- **Proponowana odpowiedź**: **default `retention_days: infinite` dla
  istniejących typów (backward-compat zero-impact)**, opt-in dla new
  types lub explicit upgrade. Cleanup cron (W15 bg task) skanuje typy
  z `retention_days != infinite` i archiwizuje rows older than retention.
  Migration tool `make w19-set-retention --type=Customer --days=2555`
  pozwala bulk-update existing types.
- **Trade-off**: bez default `infinite` — każdy istniejący typ wymaga
  decyzji (overhead dla 25 typów); z `infinite` — domyślnie nic się nie
  archiwizuje, świadoma decyzja per typ.
- **Decision owner**: Robert (G1 W19 spike)
- **HG**: NO

---

## 2. Decyzje scope (co IN, co OUT, kiedy)

### Q-W15-2: pgvector od G2 czy od G4

- **Source**: charter W15 §13 Q2
- **Kategoria**: scope (timing)
- **Stake**: pgvector dodaje complexity (binary install, CPU/RAM cost
  dla index build), ale unblockuje semantic search w W13 Advisor.
- **Proponowana odpowiedź**: **pgvector dostępny od G2, ale OFF default**.
  Manifest `embeddings: true` opt-in. Jeśli W13 Advisor zacznie używać
  semantic search dla suggesterów (np. similar findings clustering)
  przed G4 — automatycznie się wpina, bez infra change.
- **Trade-off**: G2-ready vector capability = spóźnienie G2 o ~3-5 dni
  (binary install + CI tests). Bez tego — W13 muszą zaimplementować
  workaround (text similarity z pg_trgm), później migracja.
- **Decision owner**: Robert + Claude (G1 spike)
- **HG**: NO

### Q-W15-4: OSDK distribution — in-repo vs separate package

- **Source**: charter W15 §13 Q4
- **Kategoria**: scope
- **Proponowana odpowiedź**: **v1 (G4): in-repo (importable via
  `sylion.osdk.<type>`)**. Separate PyPI package post-W17 jeśli
  external consumers się pojawią (federation territory). PDF §2.3
  single-user wyklucza external distribution w v2.
- **Trade-off**: in-repo = łatwy lifecycle (manifest change → osdk
  rebuild → tests). Separate package = better dla external, ale
  niepotrzebne w single-user.
- **Decision owner**: Robert (decision deferred do W17 G4)
- **HG**: NO

### Q-W15-6: Lineage event retention policy

- **Source**: charter W15 §13 Q6
- **Kategoria**: scope (cost-driven)
- **Stake**: 100+ events/sec × 86400 × 365 = 3.15B events/year.
- **Proponowana odpowiedź**: **integracja z W19 Q10 retention scheme**.
  Lineage events: 90 dni hot + 1 rok warm + cold archive 7 lat
  (parquet). Hash chain crosses tiers. Re-use schemy retencji z W18 Q9
  i W19 Q5 — wspólny tiered storage pattern w `aeis_v2/storage/tiered.py`.
- **Trade-off**: spójność z innymi audit-related stores. Bez wspólnego
  patternu — 3 osobne implementacje retencji = 3x maintenance.
- **Decision owner**: Robert + Cost Sentinel (G4 review)
- **HG**: NO

### Q-W16-1: Internationalization

- **Source**: charter W16 §13 Q1
- **Kategoria**: scope
- **Proponowana odpowiedź**: **opt-in przez `i18n: true` w app manifest,
  uses next-intl. V1 = en + pl hardcoded jak v1**. Decision G2 — jeśli
  jakikolwiek app w 6 demo projects W14 wymaga 3+ języków, włączamy.
- **Trade-off**: i18n od początku = ~2 dni overhead, każdy widget
  potrzebuje text extraction. Brak i18n = problem przy klientach
  enterprise w v3+.
- **Decision owner**: Robert (G2 milestone)
- **HG**: NO

### Q-W16-3: Marketplace dla widgets / apps community

- **Source**: charter W16 §13 Q3
- **Kategoria**: scope (timing)
- **Proponowana odpowiedź**: **post-G4 (v3.x territory)**. Wymaga
  discovery + trust mechanism + signing infrastructure — 2-3 miesiące
  pracy. PDF §2.3 single-user wyklucza external sharing w v2.
- **Trade-off**: deferral oznacza że team 10 osób NIE może shared widget
  library z innymi org. Akceptowalne w v2 (single-org), problem dopiero
  v3.x SaaS scenario.
- **Decision owner**: Robert (deferred, re-eval v3.0)
- **HG**: NO

### Q-W17-4: Compute Provider Federation w W17 G4 vs W17.5

- **Source**: charter W17 §13 Q4 + PDF §8.4
- **Kategoria**: scope (timing)
- **Stake**: federation (PDF §8.4) = 6-8 tygodni dodatkowych poza
  base W17 G4 (16-20 tyg). Dodaje complexity routing engine + privacy
  filtering.
- **Proponowana odpowiedź**: **split do W17.5 (separate phase post-G4)**.
  W17 G4 dostarcza fundamenty: privacy_level tag (W19 Q7), node
  capabilities w `node_manifest.yaml`, basic routing w W11. Federation
  routing engine = osobna 6-8 tyg faza po W17 G4 stable.
- **Trade-off**: W17.5 oznacza opóźnienie multi-host federation w czasie
  rzeczywistym o ~2 miesiące, ale zachowanie W17 G4 timeline (kluczowe
  dla v3.0 release). Bundling do W17 G4 = blowup do 22-28 tyg.
- **Decision owner**: Robert (W17 G3 milestone decision)
- **HG**: YES (D4) — split decision wpływa na release sequencing

### Q-W17-7: Deploy artifact distribution — pull vs push

- **Source**: charter W17 §13 Q7
- **Kategoria**: scope (architecture)
- **Proponowana odpowiedź**: **pull-based dla v1 (nodes pull from central
  artifact store)**. Pre-flight ack required przed download. Zero push
  do nodes z prod tag bez explicit ack od node-side operator.
- **Trade-off**: pull = nodes have control nad timing (good dla offline
  scenarios). Push = central może wymusić rollout (faster). Pull-based
  bardziej zgodne z PDF §2.4 local-first ducha.
- **Decision owner**: Robert (G3 architectural, low contention)
- **HG**: NO

### Q-W17-8: Observability stack — OpenTelemetry SDK init w v1?

- **Source**: charter W17 §13 Q8
- **Kategoria**: scope
- **Proponowana odpowiedź**: **lightweight OTel SDK init w G2 spike,
  full pipeline (collector + Prometheus + Grafana) odłożone do v3.x**.
  SDK init = 1 dzień, daje klientom hooks na future expansion bez
  forcing infra now.
- **Trade-off**: SDK init bez collectora = events generated, nigdzie
  nie idą (drop). Akceptowalne jako preparation step. Bez init —
  v3.x migration = 1-2 tyg setup.
- **Decision owner**: Robert (G2 spike)
- **HG**: NO

### Q-W18-2: Multi-session split view — 2 vs 3+ panes

- **Source**: charter W18 §13 Q2
- **Kategoria**: scope (UI complexity)
- **Proponowana odpowiedź**: **v1 (G4) = 2 panes**, 3+ panes post-G4
  jeśli use case się pojawi. xterm.js layout dla 2 panes prostszy,
  >2 wymaga complex grid + responsive sizing.
- **Trade-off**: 2 panes pokrywa "obserwuj produkcję, debug w tle"
  scenario. 3+ wymaga monitor 27"+ żeby nie wyglądało clipped.
- **Decision owner**: Robert (G4 finalization)
- **HG**: NO

### Q-W18-6: Federation Map dependency on W17 G2

- **Source**: charter W18 §13 Q6
- **Kategoria**: scope (cross-charter timing)
- **Proponowana odpowiedź**: **W18 G4 może shipnąć bez Federation Map
  jeśli W17 G2 opóźniony**. Panel pokazuje "Wymaga W17 G2 — currently
  unavailable" placeholder, reszta W18 G4 niezablokowana. Po W17 G2
  done — Federation Map wpina się jako follow-up release (1 tydzień).
- **Trade-off**: zachowanie W18 G4 timeline > kompletność panelu.
- **Decision owner**: Robert (W18 G3 milestone)
- **HG**: NO

### Q-W18-10: Mobile read-only view

- **Source**: charter W18 §13 Q10
- **Kategoria**: scope (timing)
- **Proponowana odpowiedź**: **post-G4, jeśli use case się pojawi**.
  xterm.js działa głównie desktop, mobile = degraded experience.
  Robert (operator) przyznał że potrzebuje mobile do *peeking*, nie
  *operowania* — `/terminal?readonly=true` z prostym text feed (bez
  xterm) = 3 dni pracy post-v3.0.
- **Decision owner**: Robert (post-v3.0 re-eval)
- **HG**: NO

### Q-W19-4: External collaborator role — guest links

- **Source**: charter W19 §13 Q4
- **Kategoria**: scope (security trade-off)
- **Proponowana odpowiedź**: **signed URLs z 24h TTL + jednorazowe
  (single-use)**. Zakaz dla resources z `sensitivity: financial`
  enforced server-side. Re-eval w v3.x jeśli use case się rozszerzy.
- **Trade-off**: signed URLs = bezpieczne i proste. Bardziej wyrafinowane
  (per-resource scope, IP binding) wymaga więcej kodu — overkill dla v2.
- **Decision owner**: Robert (G3 spike, niski impact)
- **HG**: NO

---

## 3. Decyzje team / process

### Q-PDF-9.1: Policy plane re-evaluation z 10-os zespołem (META)

- **Source**: PDF §9.1 — *fundamentalna decyzja*
- **Kategoria**: team / process (root question)
- **Stake**: ta decyzja powołała charter W19. Pytania pierwotne (czy
  zespół widzi prod data, API keys, klient information, departure
  scenario, plaintext keys OK?).
- **Proponowana odpowiedź**: **Policy plane wraca jako W19, scope
  middle-ground (ani minimal RBAC, ani pełen Palantir-style markings)**.
  Konkretnie: 6 ról + per-project ACL + audited KeyVault + field-level
  redaction + departure runbook + audit chain. Pełen Palantir
  markings (per-row classification jak TS/SCI) odłożone do v3.5.
  Charter W19 już napisany.
- **Trade-off**: middle-ground = 10-14 tyg pracy solo / 4-6 tyg parallel
  z W17. Bez tego — insider threat surface dla 10-os team. Pełny
  Palantir markings = 6-9 miesięcy, overkill dla 10 os.
- **Decision owner**: Robert (META decision — wpływa na 3-5 miesięcy
  pracy 10 osób)
- **HG**: YES (D5, fundamentalny decyzja)

### Q-PDF-9.2: Struktura zespołu

- **Source**: PDF §9.2
- **Kategoria**: team
- **Pytania**: frontend/backend split? wszyscy seniorzy w jednej
  technologii? kto tech lead? role specjalistyczne (DevOps, ML, security,
  designer, PM)? remote/hybrid? strefy czasowe?
- **Proponowana odpowiedź**: **wymagane od Roberta przed Wave 3 startup**.
  Bez tego — chartami pisane pod solo-dev, team execution niemożliwy
  do zaplanowania (parallel tracks, code review, sprint cadence,
  deployment ownership wszystko zależą od structures).
  Konkretne propozycje (Robert weryfikuje):
  - **Tech lead**: Robert (architectural decisions, gate ownership).
  - **Track owners**: 5 ścieżek (W15, W16, W17, W18, W19) — każda 1-2 osoby.
  - **Specjalizacje**: 1 DevOps (W17), 1 security (W19), 1 frontend lead
    (W16+W18), 2 backend full-stack (W15), reszta cross-cutting.
  - **PM/coordinator**: dedicated osoba lub Robert + tooling (kanban).
  - **Praca**: hybrid (preferowane), strefa czasowa CET overlap min 4h.
- **Trade-off**: każda alternatywa (full-remote, all-async) wpływa na
  delivery cadence. Hybrid = 70-80% velocity vs full-onsite, ale
  recruitment łatwiejszy.
- **Decision owner**: Robert (CEO/founder decision)
- **HG**: YES (D5, wpływa na 6-8 mies. pracy)

### Q-PDF-9.3: HSB jako team framework

- **Source**: PDF §9.3
- **Kategoria**: process
- **Proponowana odpowiedź**: **NIE jako primary framework, MOŻE jako
  inspiracja code review pattern**. PDF §2.6 odrzucił HSB dla rojki
  agentów AI. Dla zespołu ludzkiego: standardowy GitFlow + PR review +
  retrospectives wystarczy. HSB jako "pair-programming dla każdego
  module merge" jest zbyt restrykcyjny.
- **Trade-off**: HSB jako framework = strukturalna discipline ale spowolnienie
  velocity (każdy merge wymaga senior co-review). Standard GitFlow =
  dyscyplina przez konwencję, faster iteration.
- **Decision owner**: Robert + tech leads
- **HG**: NO

### Q-PDF-9.4: Status istniejących chartów (W15-W17) — przerabiamy?

- **Source**: PDF §9.4 — 3 opcje (a/b/c)
- **Kategoria**: process
- **Proponowana odpowiedź**: **opcja (a) zmodyfikowana: chartami
  pozostają jak są w sekcji architecture, ale dopisujemy sekcję
  §14 "Team Execution Plan" do każdego**. Konkretnie:
  - §14.1 — Team allocation (kto ownuje który gate).
  - §14.2 — Parallelization plan (które tasks parallel, które serial).
  - §14.3 — Code review process (każdy PR 1+ approval, D3+ wymaga 2+
    + critic AI review).
  - §14.4 — Sprint cadence (2-tyg sprints, gate-aligned).
- **Trade-off**: opcja (b) bez owner = chaos, opcja (c) rewrite from
  scratch = 2-3 tygodnie zmarnowane. (a) modified = 3-5 dni + zachowanie
  istniejącej pracy.
- **Decision owner**: Robert + Claude (immediate post-9.2 decision)
- **HG**: NO

### Q-PDF-9.5: Stack/tooling zespołu

- **Source**: PDF §9.5
- **Kategoria**: process
- **Proponowana odpowiedź**: **chartami DECLARE preferred stack
  (FastAPI, Next.js, Alembic, pytest, Vitest), team może override w
  `team_overrides.yaml` jeśli istnieją silne preferencje**. Override
  blokowany dla data layer (PostgreSQL musi być, alternatywa = miesiące
  pracy migracyjnej).
- **Trade-off**: rigid stack = łatwy onboarding ale ignoruje team
  expertise. Override mechanism = flex ale risk of fragmentation.
- **Decision owner**: Robert + tech leads (Wave 3 startup)
- **HG**: NO (jeśli stack zachowany), YES D4 (jeśli override > 2 modules)

### Q-PDF-9.6: Rola Roberta w zespole

- **Source**: PDF §9.6
- **Kategoria**: team
- **Proponowana odpowiedź**: **tech lead/architect + founder**, NIE
  product owner ani operator-only. Konkretnie:
  - Architectural decisions (D3+) — Robert finalizes.
  - Council voting — Robert ma rank 5 (highest).
  - Code review — Robert reviews D3+ PRs (sample, nie wszystkie).
  - Daily code — Robert ma 30-50% kapacytu dev (track ownership 1-2
    modules, np. W15 ontology core).
  - Operator persona — Robert używa systemu codziennie jako power user
    (DX feedback loop).
- **Trade-off**: pełen tech lead = 40-50h/tydz na team management,
  zero coding. Hybrid (powyższe) = bardziej zrównoważone, ale wymaga
  discipline (limit micromanagementu).
- **Decision owner**: Robert (samo-determinacja)
- **HG**: NO

### Q-PDF-9.7: W18 — od razu czy odłożyć

- **Source**: PDF §9.7
- **Kategoria**: scope (timing)
- **Proponowana odpowiedź**: **W18 startuje parallel z W17 G2 jako
  dedicated track**. Charter W18 już napisany (10-14 tyg solo, mniej
  z teamem). PDF §7.6 deklaruje "może startować równolegle z W17".
  Hard dep tylko W15 G2 + W14 E12 (oba existing). W18 nie blokuje
  v3.0 release (W15+W16+W17 G4).
- **Trade-off**: parallel tracking = jedna dodatkowa osoba zajęta przez
  10-14 tyg. Bez parallel — Robert czeka na W18 do v3.5 (~6 mies.
  dłużej). DX impact dla daily operations significant.
- **Decision owner**: Robert + tech lead (Wave 3 startup)
- **HG**: NO

### Q-PDF-9.8: Rozszerzenia W7/W11/W13/W17 — kiedy

- **Source**: PDF §9.8 — 3 opcje (a/b/c)
- **Kategoria**: scope (timing)
- **Proponowana odpowiedź**: **opcja (c) lazy — per warstwa, gdy
  konkretna potrzeba się pojawi**. Konkretnie:
  - W11 OpenRouter / capability tagging — wymagane dla W17.5 federation
    (post-W17 G4).
  - W11 LM Studio / vLLM provider — wymagane jeśli operator zechce
    additional local provider, lazy.
  - W7 Role Catalog (30+ ról) — wymagane dla W13 Task-to-Role Suggester,
    bundle razem.
  - W13 Task-to-Role Suggester — wymagane dla operator workflow demo,
    bundle z W7.
  - W17 Compute Provider Federation — separate W17.5 phase (Q-W17-4).
- **Trade-off**: lazy = decyzje at point of need, ale ryzyko że w
  praktyce każdy ekstension przesunie się o miesiąc bo "jeszcze nie
  potrzebujemy". Opcja (a) bundle z W15-W17 = blowup do 18-22 mies.
  solo, dla teamu ~10 mies.
- **Decision owner**: Robert (per-extension decyzja)
- **HG**: NO (lazy ad-hoc)

### Q-W19-1: Centralny IdP vs offline file-based JWT

- **Source**: charter W19 §13 Q1
- **Kategoria**: team / process (10-os authentication topology)
- **Proponowana odpowiedź**: **central IdP via opcjonalny Authelia (lekki
  Go binary), z fallback file-based dla developerów off-grid (max 7 dni
  offline mode)**. Authelia hostowany na VPS Roberta razem z W17
  central plane. Departure = 1 click w Authelia (revoke session +
  rotate refresh tokens).
- **Trade-off**: central IdP = single point of failure (R2 charter W19
  mitigation: file-based fallback). Bez central IdP — distributed
  key rotation per developer przy departure = pamięć i dyscyplina,
  rzadko działa w praktyce.
- **Decision owner**: Robert + Council (G1 W19 spike)
- **HG**: YES (D5, auth foundation)

### Q-W19-8: MFA scope — wszystkie role czy tylko owner+tech_lead

- **Source**: charter W19 §13 Q8
- **Kategoria**: team / process
- **Proponowana odpowiedź**: **opt-in dla wszystkich, REQUIRED dla
  `owner` + `tech_lead` od G1, dla `developer` + `auditor` REQUIRED
  od G4**. WebAuthn / passkeys post-v3.0 (G4+). External_collaborator
  = MFA opt-in (signed URLs są primary auth).
- **Trade-off**: rapid all-MFA wdrożenie = onboarding friction. Opt-in
  graduating = balance between security i UX.
- **Decision owner**: Robert (G1 deployment policy)
- **HG**: NO

---

## 4. Cross-cutting (wpływ na 2+ planes)

### Q-CROSS-1: Hash chain pattern unification (W15 / W17 / W18 / W19)

- **Source**: pojawia się we wszystkich 4 charterach jako "re-use
  evidence_spine pattern"
- **Kategoria**: cross-cutting (technical)
- **Stake**: 4 niezależne implementacje hash chain = 4× maintenance,
  inconsistent verification logic.
- **Proponowana odpowiedź**: **wspólny moduł `sylion/aeis_v2/hash_chain/`**
  (extension istniejącego `sylion.core.evidence_spine`) z generic
  `HashChain` class. Per-chain instance: `lineage_chain`,
  `deploy_chain`, `terminal_chain`, `audit_chain`. Wszystkie
  share same verifier (`make verify-chain --type=lineage`).
- **Trade-off**: wspólny moduł = 1 dzień refactor istniejącego
  evidence_spine + 0 dyplikacji. Bez tego — 4 niezależne chainy z
  drift risk.
- **Decision owner**: Claude (technical refactor) + Robert OK
- **HG**: NO

### Q-CROSS-2: Privacy tag propagation (W15 manifest → W11 routing → W17 federation)

- **Source**: W19 Q7 + W17 Q4 + PDF §8.4
- **Kategoria**: cross-cutting (technical + scope)
- **Proponowana odpowiedź**: **privacy_level jako field w W15 ontology
  type spec (default `ok_external`), propagowany przez W11 Adapter Bus
  envelope, respektowany przez W17 federation routing**. Konkretnie:
  - W15 manifest: `default_privacy_level: ok_external | must_run_locally
    | ok_any_provider`.
  - W15 Action Type override: `privacy_level` per akcja (ad-hoc).
  - W11 envelope: każdy LLM call ma `privacy_level` field, routing
    engine filtruje providers.
  - W17 federation: `node.capabilities.allowed_privacy_levels: [...]`,
    rejected jeśli mismatch.
- **Trade-off**: spójna implementacja przez 3 charters = jeden source
  of truth, ale wymaga koordynacji W15 G2 + W19 G3 + W17 G4 timing.
  Bez koordynacji — tag dropowany w środku pipeline = silent leak.
- **Decision owner**: Robert + Council (architectural cross-cutting)
- **HG**: YES (D5, security-impact)

### Q-CROSS-3: Multi-tenant — kiedy re-evaluacja

- **Source**: PDF §2.3 (decyzja LOCKED) + W15 §13 + W17 §13 + W19 scope
- **Kategoria**: cross-cutting (scope)
- **Proponowana odpowiedź**: **decyzja LOCKED na "single-tenant" do
  v3.0, re-eval na v3.5 jeśli AEIS będzie sprzedawany jako multi-org
  SaaS**. PDF §2.3 świadomie odrzucił multi-tenant. Cofnięcie tej
  decyzji = re-design W15 (`tenant_id` w każdym typie), W19 (per-tenant
  RBAC), W17 (tenant isolation w deploy). Cost: 6-9 miesięcy
  pracy. Trigger: business decision na product → SaaS pivot.
- **Trade-off**: zachowanie decyzji = jasny scope. Cofnięcie = cała
  v2 do rewrite-u. Pivot decision musi być bardzo świadomy.
- **Decision owner**: Robert (founder/business call)
- **HG**: YES (D5) jeśli kiedykolwiek

### Q-CROSS-4: Audit log explosion — wspólna retencja policy

- **Source**: W18 Q9 + W19 Q5 + W15 Q6
- **Kategoria**: cross-cutting (cost)
- **Proponowana odpowiedź**: **wspólny moduł `sylion/aeis_v2/storage/
  tiered_storage.py` używany przez wszystkie 3 audit-related stores**
  (lineage W15, terminal W18, audit W19). Konfiguracja per-store:
  `retention_hot_days`, `retention_warm_days`, `archive_url`. Hash
  chain crosses tiers przez reference index. Cleanup cron centralny.
- **Trade-off**: wspólny moduł = 2-3 dni refactor + zero duplikacji.
  Bez — 3 osobne tier stores, 3 cleanup crons, 3 archive paths,
  konflikt w storage layout.
- **Decision owner**: Claude (technical) + Robert OK
- **HG**: NO

### Q-CROSS-5: Authentication w W17 (pre-shared token vs JWT z W19)

- **Source**: W17 Q4 (R4) + W19 W17 dependency
- **Kategoria**: cross-cutting (sequencing)
- **Proponowana odpowiedź**: **W17 G2 startuje z pre-shared tokens
  (PSK), W17 G3+ migruje do W19 JWT po W19 G1**. Migration script
  `make w17-auth-migrate` rotuje wszystkie node tokens w 1 komendzie.
  PSK pozostaje jako fallback dla offline scenarios.
- **Trade-off**: dual-mode = 2-3 dni dodatkowej pracy w W17 G3, ale
  unblockuje W17 G2 deploy bez czekania na W19 G1. Bez tego —
  W17 G2 czeka na W19 G1 = sequential delay 4 tyg.
- **Decision owner**: Robert + tech lead (W17 G2 milestone)
- **HG**: NO (incremental migration)

### Q-CROSS-6: Redaction layer w W18 SSE stream (W19 Q feature)

- **Source**: W18 §13 + W19 §10
- **Kategoria**: cross-cutting (scope)
- **Proponowana odpowiedź**: **W18 G3 dodaje redaction middleware
  używające W19 redaction engine (assumes W19 G2 done)**. Jeśli W19
  G2 opóźniony — W18 G3 ships z hardcoded role check (developer
  widzi everything except `auth.token_*` events), W18 G4 upgraduje
  do declarative redaction.
- **Trade-off**: hardcoded fallback = 1 dzień pracy temp, później 1
  dzień refactor. Bez fallbacku — W18 G3 czeka na W19 G2.
- **Decision owner**: Robert (W18 G2 milestone, low-stake)
- **HG**: NO

### Q-CROSS-7: Soft dependency W18 → W17 G2 (Federation Map)

- **Source**: W18 Q6 + cross-charter
- **Kategoria**: cross-cutting (sequencing)
- **Proponowana odpowiedź**: **W18 G4 ships niezależnie od W17 G2
  status. Federation Map = follow-up release jeśli W17 opóźniony**.
  Patrz Q-W18-6 powyżej.
- **Decision owner**: Robert (Wave 3 sequencing)
- **HG**: NO

---

## 5. Recommended decision sequence

10 najważniejszych decyzji w kolejności w jakiej trzeba je podjąć żeby
**odblokować Wave 3 startup**:

| # | Decision | Source | Pilność | Decision Owner |
|---|---|---|---|---|
| 1 | **Struktura zespołu** (PDF §9.2) — kto ownuje który track, role specjalistyczne, time zones | PDF §9.2 | NOW (blocker) | Robert (founder) |
| 2 | **Rola Roberta w zespole** (PDF §9.6) — tech lead vs CEO vs hybrid | PDF §9.6 | NOW (blocker) | Robert (samo-determinacja) |
| 3 | **Charter execution mode** (PDF §9.4) — modyfikujemy chartami sekcją §14 Team Execution | PDF §9.4 | NOW | Robert + Claude |
| 4 | **Stack/tooling overrides** (PDF §9.5) — zachowujemy chartami stack lub pozwalamy na `team_overrides.yaml` | PDF §9.5 | NOW | Robert + tech leads |
| 5 | **Policy Plane (W19) scope** (PDF §9.1) — middle-ground (charter już napisany) potwierdzony, wdrożenie parallel z W17 | PDF §9.1 | NOW | Robert (już ma charter draft) |
| 6 | **W18 timing** (PDF §9.7) — parallel z W17 G2 (recommended) lub deferred do v3.5 | PDF §9.7 | NOW | Robert + tech lead |
| 7 | **Q-CROSS-2 privacy_level cross-cutting** — single source of truth w W15 manifest, propagacja do W11 + W17 | charters | przed W15 G2 | Council |
| 8 | **Q-W17-4 Compute Federation split** — W17.5 phase post-G4 (recommended) | charter W17 | przed W17 G3 | Robert |
| 9 | **Q-W19-1 IdP topology** — central Authelia + offline JWT fallback | charter W19 | przed W19 G1 | Robert + Council |
| 10 | **Q-W19-3 GDPR tombstone** — (a) tombstone pattern wdrożone | charter W19 | przed W19 G3 | Robert + legal |

**Decyzje #1-#6 są blokujące dla Wave 3 startup (cannot start parallel
tracks without team structure + scope confirmation). Decyzje #7-#10 są
blokujące dla konkretnych gates (W15 G2, W17 G3, W19 G1, W19 G3) i
mogą być podjęte z 1-2 tyg wyprzedzeniem przed danym gate'em.**

---

## 6. Open questions wymagające research'u (RnD)

Pytania, które **nie mają jasnej odpowiedzi bez dedykowanego spike'a**.
Operator powinien je rozważyć jako research tasks, nie immediate
decisions:

### RnD-1: Performance JSONB extension fields w W15 — realne benchmarki

**STATUS: RESOLVED 2026-04-27** (governance side; benchmark research still planned) — Manifests must declare `extension_policy: strict|declared|free` (default `strict`); strict objects validate at write-time, declared objects route undeclared fields to `_ext._unvalidated` with warning, free objects cannot reach production (Release Rail enforcement, W14 E6). See [ADR-001](decisions/ADR-001-five-architectural-decisions-2026-04-27.md) Decision #1.

- **Source**: charter W15 R3
- **Kontekst**: P-W15-02 (list 100 < 100ms p95) na 10k baseline.
  Bez benchmark'ów na realnym volume nie wiemy czy hybrid storage
  threshold dobrze dobrane.
- **Research plan**: `scripts/bench_w15_jsonb.py` — load 10k findings
  + 1k charters z W14 testing data, query patterns z 6 demo projects,
  zmierz p95 latency dla różnych hybrid threshold (5, 10, 20 hot
  fields). Czas: 3-5 dni.
- **Owner**: Claude (G1 spike)

### RnD-2: SSE 1000 events/sec sustainability w W18

- **Source**: charter W18 R1 (główne ryzyko)
- **Kontekst**: 20 hostów × 5 modeli × 10 actions/sec = teoretycznie
  1000 ev/sec. Subscription model przewiduje filter na backendzie,
  ale realne overhead?
- **Research plan**: `scripts/bench_w18_sse.py` — generate 1000 ev/sec
  przez 10 min, monitor: dropped events, UI frame time, backend CPU,
  bandwidth. Compare SSE vs WS (drop-in replacement test). Czas: 5-7 dni.
- **Owner**: Claude (G2 spike)

### RnD-3: Audit log scaling przy 10k events/sec

- **Source**: charter W19 R2
- **Kontekst**: PG append-only może być wąskim gardłem. Async batch +
  partitioning + Kafka opcja — ale realne benchmarki?
- **Research plan**: `scripts/bench_w19_audit.py` — generate 10k ev/sec
  przez 30 min, async batch insert, partitioned table, mierz: write
  latency p95, hash chain consistency overhead, replay speed dla 1M
  entries. Compare z optional Kafka backbone (1 dzień prototype).
  Czas: 7-10 dni.
- **Owner**: dedicated team member (W19 G2)

### RnD-4: PG schema-per-branch limit w praktyce

- **Source**: charter W15 §13 Q1
- **Kontekst**: PG ma teoretyczny limit ~10000 schemas, ale przy
  każdym branchu schema = 25+ tabel. Realny limit przed metadata
  bloat / query plan degradation?
- **Research plan**: `scripts/bench_w15_branches.py` — utwórz 10, 50,
  100, 500 schemas, każdy z 25 tabelami, zmierz: pg_class size,
  pg_catalog query latency, ANALYZE time, sample query latency.
  Czas: 2-3 dni.
- **Owner**: Claude (G1 spike)

### RnD-5: GDPR tombstone vs full erase — legal review

- **Source**: charter W19 §13 Q3
- **Kontekst**: technically (a) tombstone preserves chain, ale czy
  legal interpretacja GDPR art. 17 + recital 26 akceptuje
  "tombstone z destroyed encryption key" jako equivalent erase?
- **Research plan**: external legal review (1-2 firmy, ~$3-5k), specjalista
  GDPR. Output: legal opinion + procedure document. Czas: 2-3 tyg.
- **Owner**: Robert (zewnętrzny consultant)

### RnD-6: External pen-test scope + firm selection

- **Source**: charter W19 R5
- **Kontekst**: pen-test #1 w G2 (5 dni, ~$15-25k), pen-test #2 w G4
  (5 dni, ~$15-25k). Wybór firmy + scoping wpływa na findings quality.
- **Research plan**: RFP do 3-5 firm specjalizujących w SaaS security
  (np. Trail of Bits, NCC Group, Doyensec). Compare scope + cost +
  references. Decision pre-G2.
- **Owner**: Robert (security ops decision)

### RnD-7: Module Inventory & Classification (PDF §6.2)

- **Source**: PDF §6.2 + W15 dependency
- **Kontekst**: Pre-W15 phase wymaga audit 81 modułów v1 — która
  klasa A/B/C, czy wszystkie wpasują się w W15 manifest spec.
  Już istnieje `docs/v2/migration/MODULE_INVENTORY_CLASSIFICATION.csv`
  + `PRE_W15_inventory_report.md`, ale dry-run dla każdego z 25 W14 typów
  + 50 najczęściej używanych v1 typów wymagany.
- **Research plan**: 1-2 tyg dedicated phase, dry-run audit każdego
  z 75 typów + raport per-typ "fits manifest yes/no, escape hatch
  needed if no". Output: revised classification CSV.
- **Owner**: Claude + Robert (Wave 3 startup, pre-W15 G1)

---

## 6b. Quick decisions — remaining low-stake Qs

Pytania z charterów, które nie zostały rozwinięte w sekcjach 1-4 powyżej
(nie blokują Wave 3, niski stake, krótka odpowiedź wystarczy). Operator
weryfikuje grupowo:

| Q-ID | Charter | Pytanie | Proponowana odpowiedź (krótka) | Decision owner |
|---|---|---|---|---|
| Q-W16-2 | W16 | Theming per app — własne CSS theme override? | V1: shared theme (G2). Opt-in `theme: ./theme.css` w manifest opcjonalnie post-G3. | Robert (G3) |
| Q-W16-4 | W16 | Mobile-specific layouts — manifest `breakpoints`? | V1: responsive (shadcn breakpoints). Mobile-specific deferred do v3+. | Robert (G2) |
| Q-W16-5 | W16 | Custom React widgets bezpośrednio w manifest vs registration? | V1: registration required (security via path validation), reusability via widget library promotion. | Claude (G2 architectural) |
| Q-W16-6 | W16 | Workflow timeouts / SLA tracking w G3 wbudowane vs escape? | Wbudowane (1 line YAML): `if state == X for > 24h: notify`. Escape hatch dla complex SLA. | Robert (G3) |
| Q-W16-7 | W16 | Dashboard sharing — link z filtered view shareable URL? | V1 default: yes (URL params). Multi-user share-and-react = v3+ feature. | Robert (G2) |
| Q-W17-1 | W17 | Multi-tenant w przyszłości? | LOCKED na single-tenant do v3.5 (PDF §2.3). Re-eval na v3.5 jeśli SaaS pivot. Patrz Q-CROSS-3. | Robert (post-v3.0) |
| Q-W17-3 | W17 | Central plane HA — czy ever potrzebne? | V1: single instance (PDF §2.4). HA = post-G4 jeśli incident-driven need. Backup z PG snapshot daily wystarczy. | Robert (post-G4) |
| Q-W17-5 | W17 | Policy engine — kiedy migrate do OPA? | Patrz Q-W19-6. Pluggable engine od początku, OPA adapter post-G4 jeśli trigger met (100+ rules / compliance). | Robert (post-G4) |
| Q-W17-6 | W17 | Node onboarding self-service vs central-driven? | V1: central generates token, sysadmin manually applies. V2: bootstrap script (post-G3). | Robert (G3) |
| Q-W18-3 | W18 | Notifications channel — browser only / +email / +Slack? | V1: browser default + optional Slack via webhook URL. Email post-G4. | Robert (G4) |
| Q-W18-4 | W18 | Slash commands user-customization — alias / macro? | V1 (G3+): aliases only (`/s` → `/status`). Macros post-G4. | Robert (G3) |
| Q-W18-5 | W18 | Replay-as-shareable-URL — security? | V1: replay only logged-in user, no public share. Z 10-os team → re-eval RBAC w W19. | Robert (G3) |
| Q-W18-7 | W18 | Light theme / dark theme? | Dark default (xterm convention). Light post-G4 jeśli request. | Robert (post-G4) |
| Q-W18-8 | W18 | AccessibilityMode (screen reader compat dla xterm)? | V1: enabled (xterm.js built-in `screenReaderMode`). Audit z a11y reviewer post-G3. | Robert (G3) |
| Q-W19-2 | W19 | HSM dla disaster recovery — Yubikey vs CloudHSM? | Yubikey Series 5 dla owner role + sealed envelope (R3 mitigation). CloudHSM odłożony do v3.5 jeśli compliance wymóg. | Robert (G1) |
| Q-W19-5 | W19 | Audit log retention — 7 lat compliance vs storage growth? | Tiered: 90 dni hot + 1 rok warm + 7 lat cold (parquet). Patrz Q-CROSS-4 + Q-W18-9. | Robert + Cost Sentinel (G2) |
| Q-W19-7 | W19 | Privacy tags w manifeście W15 — type-level vs row-level? | V1: tag na poziomie *task* + *project* (PDF §8.4). Manifest pole `default_privacy_level` jako convenience. Per-row classification = v3.5 (Markings territory). Patrz Q-CROSS-2. | Robert (G1) |
| Q-W19-9 | W19 | Bug bounty program po v3.0? | Re-eval w v3.5, after pen-test #2 confirms posture. Cost ~$5-20k/rok minimum scope. | Robert (post-v3.0) |

**Suma pytań w 6b**: 18 (po dedukcji cross-references do sekcji 1-4).

---

## 7. Decisions LOCKED (no longer open)

Pytania, które PDF już rozstrzygnął jako policy. **Nie wracamy do nich
w sekcji Open Questions** — są referencyjne dla każdej propozycji
poniżej. Cytaty z PDF gdzie zlokalizowane:

| # | Decyzja | Status | Cytat PDF |
|---|---|---|---|
| L1 | **W14 → W15 lift, NIE fork** (Wariant A) | LOCKED | PDF §2.2 "Wariant A: lift to W15 (refactor + migracja danych). W14 nazwa zostaje, ale staje się domain wrapperem na W15" |
| L2 | **In-place upgrade, NIE fork repo** | LOCKED | PDF §2.1 "In-place upgrade, nie fork repo. Wersjonowanie: AEIS v1 → v2.0 (W15 done) → v2.5 (W16 done) → v3.0 (W17 done)" |
| L3 | **Single-tenant, NIE multi-tenant** (do v3.5) | LOCKED | PDF §2.3 "Świadomie odrzucone: SYLION jest dla Roberta. Brak tenant_id, brak row-level security per tenant" |
| L4 | **Local-first** — każda local instance działa offline, central plane opt-in | LOCKED | PDF §2.4 "Zachowane: każda local instance działa standalone offline. Central plane (W17) opcjonalny" |
| L5 | **PostgreSQL 15+ jako primary storage** (porzucenie SQLite W14) | LOCKED | PDF §2.5 "Storage: PostgreSQL 15+ (porzucenie SQLite W14)" |
| L6 | **FastAPI backend** (kontynuacja v1) | LOCKED | PDF §2.5 "Backend: FastAPI (kontynuacja)" |
| L7 | **Next.js 16 + React 19 + shadcn/ui** frontend | LOCKED | PDF §2.5 "Frontend: Next.js 16 + React 19 + shadcn/ui" |
| L8 | **Hybrid storage** (columns + JSONB ext) dla W15 | LOCKED | PDF §2.5 "Ontology storage: hybrid columns + JSONB extension" |
| L9 | **Własny React-based apps builder, NIE Budibase / ToolJet** | LOCKED | PDF §2.5 "Apps builder: własny React-based (nie Budibase/ToolJet)" |
| L10 | **Workflow engine: Python `transitions` library, NIE Temporal** | LOCKED | PDF §2.5 "Workflow engine: Python transitions library (nie Temporal)" |
| L11 | **docker-compose + Caddy reverse proxy, NIE Kubernetes** | LOCKED | PDF §2.5 "Deployment: docker-compose + Caddy reverse proxy (nie Kubernetes)" |
| L12 | **Policy engine: minimal JSON rules dla v2, NIE OPA/rego** (z pluggable interface dla future) | LOCKED + escape | PDF §2.5 "Policy engine: minimal JSON rules (nie OPA/rego)" — patrz Q-W19-6 dla pluggable adapter |
| L13 | **HSB jako pattern dla agentów AI ODRZUCONE** (może wrócić jako team framework, patrz Q-PDF-9.3) | LOCKED dla v2 | PDF §2.6 "Odrzucone w wiadomości 'Do tego porzucam pomysł HSB, zbuduję w15-w18 standardowo'" |
| L14 | **Backward compatibility REST `/api/v1/*` stable do v3.0+** | LOCKED | PDF §6.5 "REST API /api/v1/* stable do v3.0+. Internal Python API może się zmienić w v2.0 (deprecation warnings)" |
| L15 | **Pre-migration backup obowiązkowy** dla każdej destructive op | LOCKED | PDF §6.5 "Database: pre-migration backup obowiązkowy" |
| L16 | **17 Human Gates przez 12-15 miesięcy**, każdy explicit Robert decision | LOCKED | PDF §6.6 "Każdy gate to explicit Robert decision. Plan ma N exit ramps — nie all-or-nothing" |
| L17 | **W18 nie zastępuje istniejących frontend surfaces** | LOCKED | PDF §7.3 "Nie zastępuje istniejących frontend surfaces. Nie jest IDE. Nie hostuje modeli. Nie podejmuje decyzji za Roberta" |
| L18 | **W18 SSE jako real-time transport** (start; switch do WS jeśli benchmarki potrzebują) | LOCKED z escape | PDF §7.4 "Real-time: Server-Sent Events (SSE)" — patrz Q-W18-1 |
| L19 | **3 typy nodes federation**: full instance / compute provider / hybrid | LOCKED architectural | PDF §8.4 "Trzy typy nodes: Full instance / Compute provider / Hybrid" |
| L20 | **Privacy levels per task**: `must_run_locally` / `OK external` / `OK any provider` | LOCKED | PDF §8.4 "Privacy levels per task — tagged 'must run locally' / 'OK external' / 'OK any provider'" |

**Implication dla open questions**: każda propozycja w sekcjach 1-4
respektuje L1-L20. Jeśli któraś propozycja wymaga cofnięcia LOCKED
decision — wprost flag'owana jako "wymagałoby cofnięcia LOCKED Lx".
Aktualnie żadna propozycja w tym dokumencie tego nie wymaga.

---

## Final notes

**Dlaczego ten DELTA istnieje**: chartami W15-W19 są napisane *dobrze*
(każdy 13 sekcji, top ryzyka, exit gates, tech stack), ale każdy ma
sekcję §13 z 6-10 nierozstrzygniętymi pytaniami. Bez konsolidacji
operator (Robert) ma 49 punktów decyzyjnych rozsianych po 5 plikach
+ PDF — niewykonalne do podjęcia w jednej sesji. Ten DELTA daje:

1. **Jeden plik** zamiast 5 — less context switching.
2. **Konkretne propozycje** zamiast pytań — operator weryfikuje, nie
   designuje.
3. **Trade-off explicit** — koszt każdej propozycji widoczny.
4. **Decision owner + HG flag** — kto decyduje, czy wymaga Council.
5. **LOCKED section** — co już zdecydowane (referencyjne dla każdej
   propozycji).
6. **Recommended sequence** — kolejność decyzji (top-10 blokujące
   Wave 3).
7. **RnD section** — co wymaga research'u zanim można decydować.

**Co operator powinien zrobić z tym dokumentem**:
- Czytaj sekcję 5 (sequence) jako kolejność.
- Per Q: akceptuj propozycję / kontruj / deferuj / spawn dyskusję.
- Decyzje #1-#6 z sekcji 5 to gateway do Wave 3 startup — bez nich
  nie ma sensu zaczynać parallel tracks.
- LOCKED sekcja jest immutable — nie cofamy bez explicit founder
  decision (PDF §2 świadome decyzje, najlepiej zachować).

**Limit responsibility**: Claude tu proponuje, NIE decyduje. Każdy
wpis "Decision owner: Robert" oznacza że propozycja jest
sugerowana, akceptacja explicit Roberta jest wymagana przed wdrożeniem
do plan execution.

---

*DRAFT 2026-04-27. Review przed Wave 3 planning session.*
*~3050 słów (target 2000-3000 osiągnięty z lekkim przekroczeniem).*

---

## 8. Operator decisions resolved 2026-04-27 (ADR-001)

Operator (Robert) made canonical decisions on 5 architectural fork-points
on 2026-04-27. Each is archived below with RESOLVED status; full ADR with
context/trade-offs/consequences in
[`decisions/ADR-001-five-architectural-decisions-2026-04-27.md`](decisions/ADR-001-five-architectural-decisions-2026-04-27.md).

### Q-NEW-W15-EXT-VALIDATION: Extension JSONB validation policy

**STATUS: RESOLVED 2026-04-27** — Hybrid validation with strict default; manifest declares `extension_policy: strict|declared|free`, plus `extension_fields: [{name, type, indexed, default}]`.

- **Charter**: W15 (Ontology Runtime)
- **Three levels per object type**:
  - `strict` (default): only declared extension fields allowed; validation at write-time.
  - `declared`: undeclared fields go to `_ext._unvalidated` with warning log (not hard fail).
  - `free`: free-form, but objects of type=free CANNOT reach production (Release Rail enforcement, W14 E6).
- **Rationale**: anti-hallucination DNA of system requires strict-by-default; free as safety valve for R&D.
- **Implementation owner**: future cron task on `manifest.py`.
- **HG**: NO (architectural prep, no data touch).
- **Cross-ref**: [ADR-001 Decision #1](decisions/ADR-001-five-architectural-decisions-2026-04-27.md#decision-1-w15--extension-jsonb-validation).

### Q-NEW-W16-IDEA-STUDIO: Idea → App Studio cascade

**STATUS: RESOLVED 2026-04-27** — Cascade pipeline: template matching (top-N library, ~20 templates) → embeddings retrieval (if score < 0.7) → LLM generation (templates as few-shot). Manifest passes through Council Hybrid (W3) before production.

- **Charter**: W16 (Apps Builder)
- **Templates**: inventory tracker, field inspection, approval workflow, CRM lite, pipeline tracker (~20 total).
- **Threshold (0.7)**: empirical — measure miss rate over 2 months, adjust.
- **Implementation owner**: future W16 G2 task.
- **HG**: NO (architectural prep).
- **Cross-ref**: [ADR-001 Decision #2](decisions/ADR-001-five-architectural-decisions-2026-04-27.md#decision-2-w16--idea--app-studio).

### Q-NEW-W17-COST-LEDGER: Cost-ledger persistence

**STATUS: RESOLVED 2026-04-27** — Hybrid: event-sourced ground truth + PG materialized view for fast queries. LLM calls emit `cost.recorded` events (immutable, hash-chained); `mv_cost_ledger` refreshed every 30s (incremental).

- **Charter**: W17 (Deployment Plane)
- **Reads**: from view (fast aggregations).
- **Audits**: from events (provable).
- **Open sub-question**: refresh-frequency tuning (30s baseline; trigger-based for active sessions, cron for historical may be better).
- **Implementation owner**: future W17 G2 task.
- **HG**: NO (operational, reversible).
- **Cross-ref**: [ADR-001 Decision #3](decisions/ADR-001-five-architectural-decisions-2026-04-27.md#decision-3-w17--cost-ledger-persistence).

### Q-NEW-W19-POLICY-DSL: Policy DSL syntax + parking strategy

**STATUS: RESOLVED 2026-04-27 + PARKED** — YAML + jinja2 (sandboxed) for default cases; SandboxedEnvironment configured strictly (no `__class__` access). **W19 evaluator + Release Rail enforcement is PARKED** until W15/W16/W17/W18 + W7/W11/W13 are feature-complete. Pivot to OPA/Rego only if transitive relationships emerge.

- **Charter**: W19 (Policy Plane)
- **Operational directive (verbatim from operator)**: "Setki reinstalacji AEIS przy rozbudowanym systemie bezpieczeństwa to byłaby tragedia" — security applied last, once core is stable.
- **Implementation owner**: PARKED — do not dispatch.
- **HG**: NO (parking decision is operational).
- **Related**: this resolution overrides Q-W19-6 (above, §1) re. engine choice and timing.
- **Cross-ref**: [ADR-001 Decision #4](decisions/ADR-001-five-architectural-decisions-2026-04-27.md#decision-4-w19--policy-dsl-syntax--parking-strategy).

### Q-NEW-W7-W13-TASK-ROLE: Task-to-role matching pipeline

**STATUS: RESOLVED 2026-04-27** — Hybrid: tag overlap (Jaccard) top-10 → embeddings cosine top-3 → AdvisorCard with reasons → operator picks (or auto = top-1).

- **Charters**: W7 (Role Catalog) + W13 (Task-to-Role Suggester)
- **Embeddings model**: start with `nomic-embed-text` via Ollama (zero-cost local), upgrade if quality < threshold after 2 months.
- **Role catalog size**: ~30-41 roles — even weak embeddings model adequate at this count.
- **Implementation owner**: future W13 task.
- **HG**: NO (architectural prep).
- **Cross-ref**: [ADR-001 Decision #5](decisions/ADR-001-five-architectural-decisions-2026-04-27.md#decision-5-w7w13--task-to-role-matching).

### Q-NEW-OPS-MULTI-MODEL: Czy używać tylko Claude bg agents czy mix backends?

**STATUS: RESOLVED 2026-04-27** — Operator chose "Option A": route per task type across 4 backends (Claude bg, codex exec, kimi -p, ollama lokalny). Operator emphasis: "uzywaj wiecej ollama jest darmowa, proste rzeczy zrobi" — ollama is free and handles simple tasks. See [ADR-002](decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md).

- **Scope**: cron orchestrator backend selection per task type.
- **Routing matrix highlights**: Claude bg = atomic commits + multi-file edits; codex exec = single-function code gen with sync stdin; kimi -p = short adversarial EN reviews (cp1250 crash on PL >26 KB); ollama gpt-oss:20b = doc/test stub/demo data/FAQ generation in PL.
- **Implementation owner**: cron orchestrator (this ADR is the policy; subsequent rounds dispatch per matrix).
- **HG**: NO (operational policy, no data touch).
- **Cross-ref**: [ADR-002](decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md).

### Q-NEW-W19-UNBLOCK: W19 evaluator unblock — sprint 2 decision point

**STATUS: PROPOSED — see ADR-003** — Sprint 1 closed with W19 catalog MVP wired and the evaluator PARKED per ADR-001 Decision #4 ("setki reinstalacji" risk). Sprint 2 must decide whether to lift the parking directive. Three options enumerated in ADR-003 with trade-offs matrix and per-option consequences:
- **Option A**: KEEP PARKED (sprint 2 status quo) — zero risk, zero enforcement, trivially reversible.
- **Option B (recommended)**: UNBLOCK with jinja2 SandboxedEnvironment + 1% staged rollout + `SYLION_W19_EVALUATOR_DISABLED` feature flag + audit JSONL emit + Council Hybrid review of first 10 rule sets. ~3-5 days dev. Reversible via env flag (no redeploy).
- **Option C**: UNBLOCK with OPA Rego sidecar — industry-standard, more complex (~7-10 days), reversible via feature flag + redeploy.

- **Charter**: W19 (Policy Plane)
- **Risk constraint preserved**: operator's "setki reinstalacji" argument (ADR-001 Decision #4) remains load-bearing — Options B/C bound the risk via staged rollout + feature flag rather than eliminate it.
- **Pivot trigger documented**: Option B → Option C migration if rule set develops transitive relationships ("manager's manager owns") — pluggable engine interface (W19 charter §13 Q6) makes the swap a backend change, not a rewrite.
- **Implementation owner**: PROPOSED — awaiting operator sign-off + Council Hybrid (W3) vote. No cron rounds dispatched until disposition lands.
- **HG**: YES (D5 — production credentials + PII + financial data; if Option B or C accepted, the activation gate is itself an HG D4/D5 milestone per W19 charter G1/G2).
- **Cross-ref**: [ADR-003](decisions/ADR-003-W19-evaluator-unblock-2026-04-28.md), supersedes [ADR-001 Decision #4](decisions/ADR-001-five-architectural-decisions-2026-04-27.md#decision-4-w19--policy-dsl-syntax--parking-strategy) operational directive *conditionally* (only if Option B or C accepted).

---

*Section 8 added 2026-04-27 by cron orchestrator. Original 49+7 questions
preserved; section 8 captures 5 newly-resolved fork-points that were
not yet enumerated as Q-IDs in sections 1-4. Extended 2026-04-27 with
Q-NEW-OPS-MULTI-MODEL (operator's "Option A" backend routing decision,
archived in ADR-002). Extended 2026-04-28 with Q-NEW-W19-UNBLOCK
(sprint 2 W19 evaluator unblock decision point, archived in ADR-003,
status PROPOSED).*
