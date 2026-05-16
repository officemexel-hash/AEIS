# Architektura systemu SYLION AEIS

> Dokument referencyjny dla operatora, członków zespołu i audytorów.
> Wersja: runtime sync P3-004 z 2026-05-13 po R3.14.

## Spis treści

- [1. Wprowadzenie](#1-wprowadzenie)
- [2. Słownik podstawowych pojęć](#2-słownik-podstawowych-pojęć)
- [3. 12 warstw kanonu AEIS + Advisor (warstwa 13)](#3-12-warstw-kanonu-aeis--advisor-warstwa-13)
- [4. 15 faz cyklu życia pomysłu](#4-15-faz-cyklu-życia-pomysłu)
- [5. 10 typów Human Gate](#5-10-typów-human-gate)
- [6. Rada Modeli (Council Hybrid)](#6-rada-modeli-council-hybrid)
- [7. Decision ladder D0–D5](#7-decision-ladder-d0d5)
- [8. Domyślne progi kosztowe i autonomii](#8-domyślne-progi-kosztowe-i-autonomii)
- [9. 13 etapów audytu AEIS](#9-13-etapów-audytu-aeis)
- [10. Diagram zależności między warstwami](#10-diagram-zależności-między-warstwami)
- [11. Kluczowe byty systemu](#11-kluczowe-byty-systemu)
- [12. Zasada źródła prawdy](#12-zasada-źródła-prawdy)
- [13. Cross-references](#13-cross-references)

---

## 1. Wprowadzenie

### Co to jest SYLION AEIS

**SYLION AEIS** (Adaptive Evolutionary Intelligence System) to platforma kontrolowanej autonomii.
Nie jest to "kolejny orkiestrator agentów". Jest to **uczący się system**, który:

1. Prowadzi operatora od pomysłu do wdrożenia produkcyjnego.
2. Sam buduje strukturę wykonawczą per projekt — dynamicznie dobiera liczbę zespołów,
   topologię, polityki autonomii.
3. Posiada pamięć: operacyjną, projektową, konfiguracji, skuteczności i decyzji człowieka.
4. Reużywa skuteczne konfiguracje z podobnych projektów (similarity search).
5. Skaluje się: autonomia / koszt / ryzyko / czas — sterowane politykami i Human Gate.

### Dla kogo jest ten dokument

| Rola | Co znajdzie tu w pierwszej kolejności |
|---|---|
| Operator | Sekcje 3–8 (warstwy, fazy, gate, koszty) |
| Nowy członek zespołu | Sekcje 1–4 + [04_dla_developera.md](./04_dla_developera.md) |
| Stakeholder zewnętrzny | Sekcje 1–3 i 12 |
| Audytor | Sekcje 5–9 + [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) |

### Stan systemu (snapshot runtime 2026-05-13)

- Unified backend FastAPI: `sylion.api.app:app`, dev port `8010`.
- Runtime health po R3.14: `modules=138`, `endpoints=1953`, `db_mode=sqlite`, `event_mode=sqlite`.
- Frontend: Next.js `16.2.4`, React `19.2.4`, kanoniczny dev smoke `127.0.0.1:3001`.
- Legacy Python dashboard `src/sylion-pipeline/dashboard/` zostal usuniety w R3.13; backup istnieje tylko jako artefakt rollback.
- Funding Autopilot ma zweryfikowany runtime UI `/funding`, raporty, wykresy i eksporty PDF/CSV/XLSX po R3.14.
- Operator mobile: web surfaces i REST gateway sa czesciowe; pelna natywna aplikacja pozostaje planowana/czesciowa.

---

## 2. Słownik podstawowych pojęć

| Pojęcie | Definicja |
|---|---|
| **Idea** | Pomysł na projekt, wprowadzony w IdeaVault. Posiada 15 statusów cyklu życia. |
| **SourceOfTruth (SoT)** | Kanoniczny opis projektu po deliberacji modeli. Powstaje z idei. |
| **Masterplan** | Plan wykonawczy: zespoły, modele, środowiska, autonomia, lokalność. |
| **ChangeProposal** | Propozycja zmiany Masterplan / SoT — wymaga zatwierdzenia. |
| **ModelProfile** | Profil modelu LLM (provider, model_id, parametry, ranga, koszty). |
| **ModelCouncilSession** | Sesja deliberacyjna rady modeli (4-fazowa: parallel → verdicts → discussion → consolidated). |
| **SkillBinding** | Powiązanie projektu z konkretnym Skill z rejestru (Plan 18). |
| **AgentTeam** | Dynamicznie dobrany zespół agentów (deliberacyjny / architektoniczny / wykonawczy / walidacyjny / operatorski / dokumentacyjny). |
| **ExecutionModule** | Pojedynczy moduł wykonawczy (worker) w ramach Masterplan. |
| **HumanGateTicket** | Bilet do operatora: jeden z 10 typów (blocking / non-blocking / batch / emergency / financial / legal / production / security / external-action / final). |
| **RuntimeTarget** | Środowisko wykonawcze: local / VPS / hybrid / container / device. |
| **ApprovalPolicy** | Polityka decyzyjna: kto, kiedy i czego musi zatwierdzić. |
| **AuditRecord** | Pojedynczy zapis w łańcuchu audytu (hash-chained, append-only). |
| **MemorySnapshot** | Zrzut pamięci po fazie projektu (do reuse'u w przyszłych projektach). |
| **AdvisorCard** | Rekomendacja warstwy Advisor (DecisionCard, FundingCard). Zawsze z rationale + rollback + risk. |
| **Evidence Pack** | Audytowalny rekord decyzji (D3 Light lub D5 Full). |

---

## 3. 12 warstw kanonu AEIS + Advisor (warstwa 13)

System jest podzielony na 12 warstw kanonicznych. W kwietniu 2026 dodano 13. warstwę
(`Advisor Layer`) — patrz [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md).

### W1 — Operator Interface

**Co**: Powierzchnia interakcji operatora z systemem.

- Frontend Next.js 16 (`src/sylion-frontend/`), shadcn/ui + Tailwind.
- Operator Mobile: web surfaces `/operator-mobile` i `/mobile` oraz REST gateway istnieja czesciowo; natywna aplikacja Android/iOS nie jest jeszcze pelnym produktem.
- "Switch to Technical Mode" zawsze widoczny (legacy dashboards).
- Główne dashboardy: Project Lifecycle, Monitoring, AI Workspace, Governance, Costs.

### W2 — Idea Lifecycle (15 statusów)

**Co**: Pełen cykl życia pomysłu od draft do implementacji.

Statusy (kanoniczne 11 + legacy 4):
```
draft → submitted → created → clarification → council_review →
awaiting_approval → accepted → (rejected | implemented)
+ terminal: stale, abandoned, archived, deleted_soft, deleted_hard
+ legacy: approved (=accepted)
```

Kluczowe operacje (`sylion/cognitive/idea_vault.py`):
- `request_approval()` → tworzy HumanGate request, zapisuje request_id na idei
- `approve_idea()` / `reject_idea()` → automatycznie rozwiązują linked HumanGate review
- `soft_delete_idea()` → odwracalne (`restore_idea`)
- `delete_idea()` → nieodwracalne (drop tags + votes + row)
- `archive_idea()` / `unarchive_idea()` → revert do previous_status
- `detect_stale(threshold_days)` → `POST /api/v1/ideas/maintenance/detect-stale`

Każda mutacja → `_touch()` → bump `last_activity_at` + append do `idea_lifecycle_log`.

### W3 — Model Council (Rada Modeli)

**Co**: Pełen organ deliberacyjny LLM-owy. Patrz sekcja [6. Rada Modeli](#6-rada-modeli-council-hybrid).

- 9 ról kanonicznych, 5 rang, weighted vote, mandatory critic signature, sentinele.
- Implementacja: `sylion/governance/council_hybrid.py`.
- 4-fazowa deliberacja: parallel_analysis → verdicts → discussion → consolidated.

### W4 — Decision Gates (Bramki Decyzji)

**Co**: Drabina decyzyjna D0–D5 z code-aware snapshots i cascade analysis.

Backend (`sylion/governance/`):
- `decision_snapshot.py` — chwilowe zrzuty kodu w punktach decyzji
- `evidence_spine.py` — hash-chained audit trail
- `compliance_engine.py` — silnik reguł D0–D5 (79 testów)
- `conflict_resolver.py` — wykrywanie nakładania się zmian
- `decision_audit.py` — centralny log zdarzeń decyzyjnych

Cascade: zmiana decyzji → strong deps → invalidated, weak → warning.

Patrz sekcja [7. Decision ladder](#7-decision-ladder-d0d5).

### W5 — Source of Truth + Masterplan

**Co**: Kanoniczny opis projektu (SoT) → plan wykonawczy (Masterplan).

- SoT powstaje po deliberacji rady modeli i zatwierdzeniu operatora.
- Masterplan: zespoły, modele, środowiska, polityki autonomii, lokalność (local-first).
- Każda zmiana SoT/Masterplan → ChangeProposal → cascade analysis → approval.

### W6 — Execution Pipeline

**Co**: Pipeline wykonawczy od bundle do deployment.

State machine (`sylion/pipeline/state_machine.py`):
```
idle → planning → planned → generating → reviewing → complete
```

`handle_decision_change()` → rollback do `planning` jeśli cascade dotyka pipeline.
Hook H13 (production deploy) jest synchroniczny — czeka 5s na advisor decision.

API: 6 endpointów pipeline pod `/api/v1/pipeline/` (ideas, runs, execute, cancel, steps).

### W7 — Skills Registry (Plan 18)

**Co**: Katalog kompetencji systemu — procedur, reguł jakości, workflow, walidacji.

Lifecycle skill: `DRAFT → PUBLISHED → DEPRECATED`.
Manifest: `skill.yaml` walidowany przez `skill-yaml-validator`.

Skills NIE są tylko prompt helperami — to system kompetencji z auto-doborem do typu projektu
i reuse'em sprawdzonych zestawów (pamięć podobnych projektów).

### W8 — Demand Signal Analyzer (Plan 20)

**Co**: Klasteryzacja sygnałów popytu — predykcja zapotrzebowania na skills.

Komponenty:
- Collection: zbieranie sygnałów z idei, projektów, gate ticketów.
- Clustering: grupowanie po domain × type × pattern.
- Prediction: prognoza skill demand (jakie skills będą potrzebne).

### W9 — Memory + Vault

**Co**: Pamięć systemu — RDZEŃ (nie dodatek).

Typy pamięci:
- **Projektowa** — kontekst pojedynczego projektu.
- **Operacyjna** — historia interakcji operatora.
- **Konfiguracji** — sprawdzone setupy (zespół × skills × topologia).
- **Skuteczności** — mierzone wyniki past projects.
- **Podobieństwa** — similarity search po idei → rekomendacja topologii.
- **Decyzji człowieka** — log akceptacji/odrzuceń (soft + hard learning).

Vault: bezpieczne przechowywanie sekretów (provider keys, podpisy, klucze biometryczne).

### W10 — Governance + Evidence Spine

**Co**: Cała warstwa zarządzania zgodnością i audytem.

- `evidence_spine.py` — hash-chained audit trail (blockchain-like).
  `verify_chain()` wykrywa tampering.
- `compliance_engine.py` — egzekwowanie wymagań D0–D5.
- `conflict_resolver.py` — wykrywa overlap zmian.
- `decision_audit.py` — centralny log zdarzeń.

Frontend: `decisions/page.tsx` (5 zakładek), `evidence-spine/page.tsx`, `governance/page.tsx`.

Patrz [03_governance_audit_compliance.md](./03_governance_audit_compliance.md).

### W11 — Adapter Bus (multi-provider LLM)

**Co**: Routing zapytań LLM do różnych providerów + fallbacki.

Pool LLM (default w onboardingu):
- **Local (Ollama)**: `qwen2.5:72b-instruct` (primary), `qwen2.5:7b-instruct` (mini).
- **External primary**: Anthropic `claude-sonnet-4-6`, OpenAI `gpt-5`, Google `gemini-2.5-pro`.
- **Optional adapters**: `claude-opus-4-7`, `claude-haiku-4-5`, Kimi K2, GLM-4.6, Grok 4.

Env vars:
- `SYLION_LLM_PROVIDER` (`stub | anthropic | openai | ollama`)
- `SYLION_LLM_API_KEY`, `SYLION_LLM_MODEL`

### W12 — Operator Mobile (globalna warstwa)

**Co**: Mobilny operator z secure token + device binding + follow-me mode.

- Etap 1: tylko REST gateway w `sylion.aeis.advisor.mobile_gateway` (przygotowane).
- Etap 2: Android (Kotlin Multiplatform + Jetpack Compose).
- Etap 3: iOS (SwiftUI shared via KMP).

Cechy:
- Device-bound JWT w Android Keystore + biometric step-up (`BiometricPrompt`).
- Push: Firebase FCM.
- Offline cache: 50 last cards + 10 active projects + Human Gate pending + 30 funding deadlines.
- Default: follow-me mode OFF (operator musi włączyć świadomie).

### W13 — AEIS Advisor Layer (NOWA, Etap 1)

**Co**: Aktywny operator-asystent. Transformuje AEIS z pasywnego dashboard w aktywnego asystenta.

4 filary:
1. **Adaptive Preferences** — 10+ preferencji uczonych w macierzy 3D `(user × project_type × project_domain)`.
2. **Recommendation Engine** — 16 lifecycle hooks → `AdvisorCard`, hybrid rule + LLM-as-judge.
3. **Specialized Advisors** — Subscription, Scaling, Funding (opt-in), Role Resolver, Variants.
4. **Guided UX** — Onboarding Wizard (10 kroków) + Live Feed + Lifecycle Dashboard + Monitoring.

11 modułów backend + 4 surface frontend. Storage: PG-only (świadoma divergencja).
Pełen opis: [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md).

---

## 4. 15 faz cyklu życia pomysłu

Pełny flow od idei do produkcji to 15 faz (nie tylko "idea → plan → execute"):

| # | Faza | Co się dzieje | Kluczowy hook lifecycle |
|---|---|---|---|
| 1 | **Intake** | Operator wprowadza pomysł, klasyfikacja D0–D5 | H04 `aeis.idea.intake.completed` |
| 2 | **Clarification** | Doprecyzowanie kontekstu (auto-questions) | — |
| 3 | **Model Deliberation** | Rada modeli — 4-fazowa analiza | H06 `aeis.council.formation_requested` |
| 4 | **Memory Compare** | Similarity search w pamięci podobnych projektów | — |
| 5 | **Skills + Topology** | Auto-dobór skills + topologii zespołów | H12 `aeis.system.skill_selection_requested` |
| 6 | **Approval (idea)** | Zatwierdzenie idei → status `accepted` | (HumanGate) |
| 7 | **Source of Truth** | Wygenerowanie SoT (LLM authoring) | H05, H08 `sot_drafted` |
| 8 | **Masterplan** | Plan: zespoły, modele, środowiska, autonomia | H09 `aeis.masterplan.created` |
| 9 | **Approval (masterplan)** | Zatwierdzenie planu (D2/D3 zazwyczaj) | (HumanGate) |
| 10 | **Runtime + Scaling** | Wybór topologii (local / VPS / hybrid) | H10, H11 |
| 11 | **Execution** | Workery działają wg Masterplan | (continuous events) |
| 12 | **Human Gate (risk)** | Tylko dla ryzyka — nie punktowo | H15 `aeis.human_gate.ticket_pending` |
| 13 | **Testing** | golden / integration / e2e / security / load | H14 `aeis.testing.started` |
| 14 | **Final Approval** | Wszystkie gates passed → final | H16 `aeis.final_approval.requested` |
| 15 | **Memory Snapshot** | Zapis skuteczności do pamięci | (asynchroniczny) |

---

## 5. 10 typów Human Gate

Human Gate NIE jest jedną klasą biletów. Ma 10 kanonicznych typów — każdy ma własną
politykę i timeout:

| # | Typ | Trigger | Domyślne SLA | Można batch? |
|---|---|---|---|---|
| 1 | **blocking** | Krytyczna decyzja blokuje pipeline | natychmiast | nie |
| 2 | **non-blocking** | Sugestia / opcjonalna review | 7 dni | tak |
| 3 | **batch** | Niskie ryzyko, agregacja N ticketów | 24h | tak |
| 4 | **emergency** | Naruszenie polityki / sentinel alert | natychmiast | nie |
| 5 | **financial** | Akcja >25 EUR / miesiąc >100 EUR | 24h | tak (jeśli <25 EUR każdy) |
| 6 | **legal** | Zmiana formy prawnej / umowy | 72h | nie |
| 7 | **production** | Każde wdrożenie produkcyjne | 24h | nie |
| 8 | **security** | Audyt / CVE / podpis sentinel | 24h | nie |
| 9 | **external-action** | Upload / submit do systemu zewnętrznego | 24h | nie |
| 10 | **final** | Finalna akceptacja projektu | bez timeoutu | nie |

**Batch**: gdy `pending_count_user ≥ próg`, advisor sugeruje `REC_TYPE_HUMAN_GATE_BATCH`
("5 low-risk ticketów można rozpatrzyć łącznie").

---

## 6. Rada Modeli (Council Hybrid)

### 9 ról kanonicznych

```
planner            architect          critic
verifier           governance         cost_sentinel
security_sentinel  domain_specialist  funding_specialist
```

### 5 rang

```
primary  →  senior  →  support  →  review_only  →  validation_only
```

### Wagi głosu

```
voting_weight = DEFAULT_ROLE_WEIGHTS[role] × RANK_MULTIPLIER[rank]
```

Przykład: `critic.primary = 1.0`, `cost_sentinel.support = 0.35`.

### 4-fazowa deliberacja

```
1. parallel_analysis  →  każdy uczestnik niezależna analiza
2. verdicts           →  każdy zwraca verdict (accept/reject/abstain)
3. discussion         →  konstruktywna dyskusja, możliwa zmiana verdict
4. consolidated       →  konsensus z weighted vote
```

### Bramki obowiązkowe (gated consolidation)

`consolidate_with_signatures(text, require_critic=True, require_sentinels_pass=True)`:
- **Critic gate** — co najmniej 1 podpis modelu w roli `critic` (signature gate).
- **Sentinele** — `cost_sentinel` i `security_sentinel` mogą zablokować (`sentinel_blocks`).
- Brak veta governance (zawsze weighted vote, nie unanimity).

### API (`/api/v1/workspace/council/`)

| Endpoint | Cel |
|---|---|
| `GET /roles` | Lista ról + rang + default weights |
| `POST /sessions/{sid}/participants` | Dodaj uczestnika |
| `POST /sessions/{sid}/critic/sign` | Podpis krytyka |
| `POST /sessions/{sid}/sentinels/evaluate` | Ocena sentinela |
| `GET /sessions/{sid}/consensus` | Tally z weighted vote |
| `POST /sessions/{sid}/consolidate-gated` | Atomic gated consolidation |

### Tabele

`council_participants`, `council_critic_signatures`, `council_sentinel_evaluations` —
wszystkie keyed off `hybrid_council_sessions.session_id`.

Patrz `sylion/governance/council_hybrid.py` (91/91 testów green).

---

## 7. Decision ladder D0–D5

### Kanoniczne poziomy

| D | Nazwa | Audit | Approval | Evidence |
|---|---|---|---|---|
| **D0** | Trivial | default log | brak | brak |
| **D1** | Minor | logged event | brak | brak |
| **D2** | Moderate | logged event | optional HG | brak (light context) |
| **D3** | Significant | logged + HG ticket | **HG required** | **D3 Light** (rationale + rollback) |
| **D4** | High-impact | logged + Council vote | **Council vote** | **D5 Full** |
| **D5** | Critical | logged + multi-sig | **operator + Council + Sentinel** | **D5 Full mandatory** |

### Zasady eskalacji (rules U1–U5)

| Reguła | Trigger | Skutek |
|---|---|---|
| **U1 cost magnitude** | $>100 / $>1k / $>10k | +1 / +2 / +3 poziomy |
| **U2 blast radius** | multi-project / production env | +1 / +1 |
| **U3 reversibility** | rollback >1 dzień / data loss | +1 / +2 (min D4) |
| **U4 hard preferences** | autonomy_level / runtime_strategy etc. | min D3 |
| **U5 operator autonomy** | autonomy=manual → wszystko ≥D3 | egzekwowane globalnie |
| **U6 cap** | max D5, mandatory D5 Full | nie można przekroczyć |

### Evidence Pack templates

- **D3 Light** — rationale ≥200 słów + rollback_plan ≥100 + fidelity_test ≥50 + ≥1 podpis operatora.
- **D5 Full** — wszystko z D3 Light + risk_analysis + worst_case_scenario + simulation_results + ≥2 podpisy.

Pełen opis: [03_governance_audit_compliance.md](./03_governance_audit_compliance.md).

---

## 8. Domyślne progi kosztowe i autonomii

### Kanoniczne defaults (z onboarding wizard)

| Parametr | Wartość domyślna |
|---|---|
| `autonomy_level` | `medium` (suggest) |
| `runtime_strategy` | local-first |
| Produkcja (deployment) | zawsze Human Gate |
| Pojedyncza akcja | >25 EUR → HG |
| Miesięcznie | >100 EUR → HG |
| VPS | >3 workery → HG |
| External upload/submit | zawsze HG |
| Final publish | zawsze HG |
| Mobile follow-me | OFF (default) |

### Cost ceilings per risk level (configurable w onboarding)

| Risk | Ceiling |
|---|---|
| low | $0.10 |
| medium | $0.40 |
| high | $1.60 |
| critical | $6.00 |
| funding | $3.00 |

### Skala topologii

| Skala | Setup | Środowiska |
|---|---|---|
| **Mały** | 1 agent + 1 critic | local |
| **Średni** | 3–4 rada, FE+BE+test | local-first |
| **Duży** | pełna rada, wiele zespołów | VPS + container + browser + device |

---

## 9. 13 etapów audytu AEIS

Audyt systemu (prefix plików: `CLAUDE_AEIS_*` w `docs/claude_system_audit/`):

1. **Canon coverage** — czy wszystkie 12 warstw + Advisor istnieją
2. **Memory** — czy 6 typów pamięci jest zaimplementowane
3. **Skills** — czy katalog skills + auto-dobór działa
4. **Autonomy** — czy polityki realnie sterują (nie tylko flaga)
5. **Council** — 9 ról × 5 rang × weighted + critic + sentinele
6. **Human Gate** — czy 10 typów działa systemowo
7. **Funding** — pełen pion: profile → scanning → scoring → docs → consortium → submission → monitoring
8. **Mobile** — secure token + device binding + follow-me
9. **Runtime verification** — kod → runtime → API → UI → testy → docs (w tej kolejności)
10. **Testy "jak człowiek"** — scenariusze użytkownika, nie tylko unit/integration
11. **Drift** — czy kanon i implementacja są zgodne
12. **Klasyfikacja** — D0–D5 dla każdej decyzji
13. **Backlog + Księga** — co zostało, co jest w Księdze AEIS

Każdy etap ma listę pytań A1–A7 dodatkowych poza standardowymi 12 pytaniami HG.

---

## 10. Diagram zależności między warstwami

```
┌──────────────────────────────────────────────────────────────────┐
│                     W1 OPERATOR INTERFACE                        │
│   Web (Next.js) │ Mobile (Etap 2) │ "Switch to Technical"        │
└──────────────────────────────┬───────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ↓                      ↓                      ↓
┌───────────────┐      ┌──────────────┐      ┌──────────────────┐
│ W13 ADVISOR   │      │ W2 IDEA      │      │ W3 COUNCIL       │
│ (4 filary)    │←────→│ LIFECYCLE    │─────→│ HYBRID           │
│ 11 modułów    │      │ (15 statusów)│      │ (9 ról / 5 rang) │
└──────┬────────┘      └──────┬───────┘      └────────┬─────────┘
       │                      │                       │
       │              ┌───────┴────────┐              │
       │              ↓                ↓              │
       │      ┌───────────────┐ ┌─────────────┐      │
       │      │ W5 SoT +      │ │ W4 DECISION │←─────┘
       │      │   MASTERPLAN  │ │ GATES D0–D5 │
       │      └───────┬───────┘ └─────┬───────┘
       │              │               │
       │              ↓               ↓
       │      ┌────────────────────────────┐
       │      │ W6 EXECUTION PIPELINE       │
       │      │ (state machine + cascade)   │
       │      └──────────┬──────────────────┘
       │                 │
       │       ┌─────────┴──────────┐
       │       ↓                    ↓
       │  ┌──────────┐        ┌──────────────┐
       │  │ W7 SKILLS│        │ W8 DEMAND    │
       │  │ REGISTRY │        │ SIGNAL       │
       │  └────┬─────┘        └──────┬───────┘
       │       │                     │
       └───────┼─────────────────────┼──────────────────┐
               ↓                     ↓                  ↓
        ┌──────────────────────────────────────────────────┐
        │ W9 MEMORY + VAULT  │  W10 GOVERNANCE + EVIDENCE  │
        └────────┬───────────┴───────┬──────────────────────┘
                 │                   │
                 ↓                   ↓
         ┌─────────────────────────────┐
         │ W11 ADAPTER BUS (LLM pool)  │
         │  Anthropic / OpenAI / Google│
         │  Ollama / Kimi / GLM / Grok │
         └──────────────┬──────────────┘
                        │
                        ↓
                 ┌─────────────┐
                 │ W12 MOBILE  │
                 │ (Etap 2/3)  │
                 └─────────────┘
```

---

## 11. Kluczowe byty systemu

```
Project ─┬─ IdeaIntakeRecord (W2)
         ├─ SourceOfTruth (W5)
         ├─ Masterplan (W5)
         │   └─ ChangeProposal (W5)
         ├─ ModelProfile [N] (W11)
         ├─ ModelCouncilSession [N] (W3)
         ├─ SkillBinding [N] (W7)
         ├─ AgentTeam [N] (W6)
         │   └─ ExecutionModule [N] (W6)
         ├─ HumanGateTicket [N] (W4)
         ├─ RuntimeTarget [N] (W6)
         ├─ ApprovalPolicy (W4)
         ├─ AuditRecord [N] (W10)  ← hash-chained
         └─ MemorySnapshot [N] (W9)
```

Wszystkie byty mają `created_at`, `updated_at`, `last_activity_at` (gdzie ma sens) i są
indeksowane przez `project_id` + appropriate sub-key.

---

## 12. Zasada źródła prawdy

W AEIS obowiązuje hierarchia źródła prawdy:

```
1. KOD            (najwyższy autorytet)
2. RUNTIME        (co realnie działa)
3. API            (kontrakty endpointów)
4. UI             (co operator widzi)
5. TESTY          (co jest sprawdzone)
6. DOKUMENTACJA   (najniższy autorytet)
```

**Dokumentacja NIGDY nie wygrywa**. Jeśli docs mówi X, a kod robi Y → kod jest prawdą.

To ma praktyczne implikacje:
- Memory records są **point-in-time observations**, nie live state.
- Przed decyzją zawsze weryfikuj przeciw kodowi (`grep`, `read`).
- Audyt sprawdza w tej kolejności: kod → runtime → API → UI → testy → docs.

---

## 13. Cross-references

| Temat | Plik |
|---|---|
| Advisor Layer (W13) deep-dive | [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) |
| Codzienny workflow operatora | [02_operational_manual.md](./02_operational_manual.md) |
| Governance + audit + compliance | [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) |
| Onboarding developera | [04_dla_developera.md](./04_dla_developera.md) |
| Kanon AEIS pełny | `docs/Ksiega_AEIS_v3_5_full.md` |
| Masterplan AEIS | `docs/Masterplan_AEIS_v3_5.md` |
| Plan wdrożenia | `docs/PLAN_WDROZENIA.md` |
| Advisor architecture (źródło) | `docs/claude_parallel/aeis_advisor/00_architecture/` |
