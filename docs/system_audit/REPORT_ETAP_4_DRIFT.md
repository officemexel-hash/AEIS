# REPORT ETAP 4 — Drift Analysis (Canon vs Reality)

**Data:** 2026-04-24
**Zakres:** konsolidacja 3 raportów warstwowych (L0-L8) + 6 scenariuszy (S1-S6) + extended model (A1-A7)
**Cel:** zidentyfikować gdzie realizacja odbiega od kanonu, zmierzyć skalę, zaproponować mapę naprawy

## Metodologia

Drift = różnica między zadeklarowanym kontraktem kanonu (manifesty, spec 3.5, Human Gate spec, extended model) a zaobserwowanym zachowaniem (kod + runtime API + scenariusze).

Klasyfikacja severity:
- 🔴 **CRITICAL** — blokuje produkcję, ryzyko bezpieczeństwa/integralności
- 🟠 **HIGH** — poważna luka funkcjonalna, ale system działa
- 🟡 **MEDIUM** — ograniczenie, workaroundable

## 16 głównych drifts

### D-01 🔴 Pipeline omija Human Gate [CRITICAL]
**Kanon:** D3-D5 decyzje blokowane na Human Gate
**Runtime:** 0 wywołań `HumanGate.create_request()` w execution path
**Evidence:** `core/pipeline_controller.py:198-389`, grep w state_machine.py = 0, S1-S6 × 0 HG
**Effort:** 4h (FIX-001) + 2h (FIX-007) + 3h (integration test FIX-008) = **9h**
**Depends on:** D-03 (bootstrap), D-08 (classifier działający)

### D-02 🔴 Decision classifier zawsze D0 [CRITICAL]
**Kanon:** risk-based classification per słowa kluczowe (prod, deploy, PII, credentials → D3+)
**Runtime:** 15/15 kroków S3 (auth+PII) = D0, 10/10 S6 (payment) = D0
**Evidence:** `governance/decision_snapshot` API, wszystkie snapshots D0
**Effort:** 6h (FIX-019)
**Depends on:** D-07 (unifikacja decision_gate_engine)

### D-03 🔴 Bootstrap Canon broken [CRITICAL]
**Kanon:** manifesty ładowane do contract_registry przy starcie
**Runtime:** 119 manifestów na dysku, `/api/v1/contracts` zwraca `[]`
**Evidence:** L0 audit
**Effort:** 3h (FIX-003)
**Depends on:** —

### D-04 🔴 Cross-run gate namespace collision [CRITICAL]
**Kanon:** każdy run ma własne bramki
**Runtime:** 11/15 kroków S3 odczytało gate_name ze snapshotów z S1/S2
**Evidence:** S2/S3 reports, gate_id=`pipeline_step_{N}` globalnie keyed
**Effort:** 2h (FIX-015)
**Severity:** data integrity w evidence spine
**Depends on:** —

### D-05 🔴 Orphan decision snapshots [CRITICAL]
**Kanon:** każdy snapshot linkowany do pipeline_run_id
**Runtime:** `pipeline_run_id=null` dla wszystkich snapshots w S3
**Evidence:** `/api/v1/decision-snapshots` probe w S3
**Effort:** 1h (FIX-021)
**Depends on:** —

### D-06 🔴 Silent fallback planner dla złożonych idei [CRITICAL]
**Kanon:** planner ma być adaptacyjny i bogatszy dla złożonych projektów
**Runtime:** S4 (6 zespołów, Kafka, ML) → 5 kroków stub „analyze/design/implement/test/review"
**Evidence:** S4 report, `step_id: "s1".."s5"` (string), plan.source=?  (brak pola)
**Effort:** 2h observability (FIX-024) + 8h multi-pass planner (FIX-025) + 3h warning (FIX-026) = **13h**
**Depends on:** —

### D-07 🟠 Dwie konkurencyjne implementacje decision_gate_engine [HIGH]
**Kanon:** jedna kanoniczna implementacja
**Runtime:** `core/` i `governance/` mają osobne
**Evidence:** L1 audit
**Effort:** 4h (FIX-002)
**Depends on:** —

### D-08 🔴 execution_guard: OFF dla wszystkich L4 [CRITICAL]
**Kanon:** strict dla modułów wykonawczych
**Runtime:** wszystkie 8 L4 modułów ma guard=OFF w manifestach
**Evidence:** L3-L5 audit
**Effort:** 2h (FIX-004)
**Depends on:** D-03

### D-09 🔴 Memory=0% [CRITICAL]
**Kanon:** similarity search podobnych projektów + reuse skills
**Runtime:** `/memory/search` 404, `/aeis/similar` 404, explicit `run_id` w idei zignorowany, plan S5 gorszy od S2
**Evidence:** S5 report
**Effort:** 4h (FIX-029) + 16h (FIX-030 embeddings) + 8h (FIX-031 few-shot) + 4h (FIX-032 evidence) = **32h**
**Depends on:** D-10 (skills musi być pierwsze)

### D-10 🔴 Brak katalogu skills [CRITICAL]
**Kanon:** Skills jako warstwa rdzeniowa (patrz [02_AEIS_EXTENDED_MODEL.md](02_AEIS_EXTENDED_MODEL.md))
**Runtime:** 0 skills registered, żaden run nie dobiera kompetencji
**Evidence:** S1-S6 × 0 skills w evidence
**Effort:** ~40h (nowa warstwa)
**Depends on:** —

### D-11 🔴 Brak mechanizmu doboru topologii zespołów [CRITICAL]
**Kanon:** A1 — system proponuje 1 agent / 3 zespoły / pełny podział
**Runtime:** zawsze 1 agent sekwencyjnie
**Effort:** 16h (FIX-027 team decomposition) + 12h (FIX-028 parallel exec) = **28h**
**Depends on:** D-10

### D-12 🟠 Governance dla rebuild.cutover/self_healing brak [HIGH]
**Kanon:** hot-swap/rollback/cutover/freeze w prod → approval + signature + timeout
**Runtime:** 0 governance na tych modułach
**Effort:** 6h (FIX-005)
**Depends on:** D-01

### D-13 🟠 improvement_queue pusta — brak sygnałów z runów [HIGH]
**Kanon:** każdy run zasila improvement_queue (co się wywaliło, co można ulepszyć)
**Runtime:** `/aeis/improvements` → `[]` po 6 runach
**Effort:** 4h (FIX-006) + 6h (FIX-034 sygnały z runów) = **10h**
**Depends on:** D-09

### D-14 🟡 LLM ignoruje constraints idei [MEDIUM]
**Kanon:** wygenerowany kod używa zadeklarowanych technologii
**Runtime:** idea "FastAPI+SQLite" → LLM zwraca Flask+in-memory
**Effort:** 4h (FIX-016 prompt) + 6h (FIX-017 validator) + 2h (FIX-023 context injection) = **12h**
**Depends on:** —

### D-15 🔴 Recovery endpoints brak [CRITICAL]
**Kanon:** self-healing, incidents, rollback API + failure triggers HG
**Runtime:** 3/4 endpointów 404, pipeline nie wykrywa błędów
**Effort:** 6h (FIX-036) + 8h (FIX-037 rollback) + 10h (FIX-038 step failure→incident) + 6h (FIX-039 chaos) = **30h**
**Depends on:** D-01, D-12

### D-16 🔴 Artefakty nieistniejące mimo status=complete [CRITICAL]
**Kanon:** status=complete → artefakt zapisany na dysku / w module
**Runtime:** `artifacts: None` dla wszystkich 6 runów
**Evidence:** S1-S6 × 0 artefaktów
**Effort:** 8h (persystencja output kroku jako artifact) — FIX-040 nowy
**Depends on:** —

## Tabela skumulowana

| ID | Severity | Effort | Zależności |
|---|---|---|---|
| D-01 HG integration | 🔴 | 9h | D-03, D-08 |
| D-02 Classifier | 🔴 | 6h | D-07 |
| D-03 Bootstrap | 🔴 | 3h | — |
| D-04 Gate namespace | 🔴 | 2h | — |
| D-05 Orphan snapshots | 🔴 | 1h | — |
| D-06 Silent fallback | 🔴 | 13h | — |
| D-07 Dual decision_gate | 🟠 | 4h | — |
| D-08 execution_guard OFF | 🔴 | 2h | D-03 |
| D-09 Memory 0% | 🔴 | 32h | D-10 |
| D-10 Skills brak | 🔴 | 40h | — |
| D-11 Topologia zespołów | 🔴 | 28h | D-10 |
| D-12 Governance cutover | 🟠 | 6h | D-01 |
| D-13 Improvement queue | 🟠 | 10h | D-09 |
| D-14 LLM constraints | 🟡 | 12h | — |
| D-15 Recovery brak | 🔴 | 30h | D-01, D-12 |
| D-16 Artefakty none | 🔴 | 8h | — |

**Total:** 206h ≈ 5-6 tygodni 1 dev / 2-3 tygodnie zespół 3-os.

**CRITICAL (12 drifts):** 174h
**HIGH (3):** 20h
**MEDIUM (1):** 12h

## Graf zależności naprawy

```
D-03 Bootstrap ──┐
                 ├─> D-08 execution_guard ──┐
                 │                           ├─> D-01 HG integration ──> D-12 governance cutover ──> D-15 recovery
D-07 Dual DG ────┴─> D-02 Classifier ───────┘
D-04 Gate namespace (niezależne)
D-05 Orphan snapshots (niezależne)
D-06 Silent fallback (niezależne)
D-10 Skills ──> D-09 Memory ──> D-13 Improvement queue
           └──> D-11 Topologia zespołów
D-14 LLM constraints (niezależne)
D-16 Artefakty (niezależne)
```

## Rekomendowana kolejność (sprints)

**Sprint 1 (tydzień 1) — fundamenty, 19h:**
D-05 (1h) → D-04 (2h) → D-03 (3h) → D-08 (2h) → D-07 (4h) → D-02 (6h) → D-16 start

**Sprint 2 (tydzień 2) — Human Gate + recovery, 59h:**
D-01 (9h) → D-12 (6h) → D-06 (13h) → D-15 (30h) → D-16 done (8h)

**Sprint 3 (tydzień 3-4) — adaptive model, 110h:**
D-10 Skills (40h) → D-09 Memory (32h) → D-11 Topologia (28h) → D-13 (10h)

**Sprint 4 (tydzień 5) — quality, 12h + bufor:**
D-14 LLM constraints (12h) + regresja, stabilizacja

## Zgodność z extended model AEIS

Przed fixami: **0/7 osi A1-A7 pokrytych**
Po D-10+D-11: A1, A3 spełnione
Po D-09: A2, A4 spełnione
Po D-12+D-15: A7 spełnione
Po FIX-038 (autonomy enforcement): A5, A8 spełnione
Po FIX-027 (topologia): A6 spełnione

Docelowo po wszystkich 16 drifts: **7/7 A + 12/12 HG.**

## Konkluzja ETAP 4

16 drifts = precyzyjna mapa naprawy AEIS. 12 krytycznych blokuje produkcję. Łącznie ~206h, rozpisane na 4 sprinty.

**Pierwszy raz w projekcie jest wymienialna lista "co dokładnie trzeba zrobić" z numerami linii kodu, effortem i zależnościami — zamiast ogólnika "system nie działa".**
