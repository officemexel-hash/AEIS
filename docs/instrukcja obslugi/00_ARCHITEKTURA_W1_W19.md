# 00 — ARCHITEKTURA AEIS — Warstwy W1-W19

> **Status**: 🟢 Active draft (uzupełnienie 41-fazowego manuala)
> **Cel**: zmapować architektoniczne warstwy AEIS na operacyjne fazy 1-41
> **Źródło**: `AEIS_W1_to_W19_kompletny_opis.md` (54KB, 1195 linii)
>
> **Pozycja w manualu**: Fundament. Czytaj **PRZED** fazami 1-41.
> 41 faz to **workflow** (co operator robi). 19 warstw to **architektura**
> (co system jest pod spodem). Faza działa na konkretnych warstwach.
>
> **Krytyczna zasada**: Manual 41-fazowy opisywał workflow zakładając
> że operator wie z czego AEIS jest zbudowany. Ten dokument dostarcza
> tę wiedzę explicit.

---

# CZĘŚĆ I — Trzy poziomy abstrakcji

```
┌──────────────────────────────────────────────────────────────┐
│  LEVEL 3 — Operacje (workflow)                                │
│   41 FAZ od onboardingu do closure                            │
│   Co operator robi krok po kroku                              │
│                                                              │
│  ↓ wykonuje się NA warstwach ↓                                │
│                                                              │
│  LEVEL 2 — Architektura (system)                              │
│   19 WARSTW W1-W19                                            │
│   Z czego AEIS jest zbudowany                                 │
│                                                              │
│  ↓ aktywowana przez ↓                                         │
│                                                              │
│  LEVEL 1 — Inteligencja (Advisor)                             │
│   ADVISOR LAYER (W13) — proaktywna inteligencja              │
│   16 lifecycle hooks emituje AdvisorCards                     │
└──────────────────────────────────────────────────────────────┘
```

**Najprościej**: faza to "krok w procesie", warstwa to "część systemu", Advisor to "AI który zauważa, sugeruje, ostrzega".

---

# CZĘŚĆ II — Trzy grupy warstw

## Grupa A — Foundation (W1-W7) — fundament infrastruktury

System wie kim jest operator, gdzie trzyma dane, jakie ma modele, gdzie wolno mu uruchamiać kod.

**W1 — Operator Interface**
Next.js 16 frontend, dark theme cybersecurity aesthetic. 13 frontend surfaces: `advisor_feed`, `onboarding_wizard` (10 kroków), `lifecycle_dashboard`, `operator_monitor`, `settings_advisor`, `evidence_pack_viewer`, `council_voting`, `audit_viewer`, `faq_runbook`, `ai_models_config`, `idea_vault`, `cockpit_project_hub`, `mobile_app`. BackendOfflineGuard. Live Feed (toast + modal + bubble counter).

**W2 — Idea Lifecycle**
**11 stanów** (poprawione z 15 v1):
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

**W3 — Council Hybrid** (poprawione z mojego manuala)
**9 ról × 5 rang × 4 fazy deliberacji + mandatory critic gate**:
- 9 ról: Planner / Critic / Security / Legal / Finance / Governance / QA / Red Team / Council Chair
- 5 rang per rola: `primary` (1.0) / `support` (0.7) / `observer` (0.4) / `cost_sentinel` (0.35) / `security_sentinel` (0.35)
- 4 fazy: parallel verdicts → discussion → consolidated vote → **critic signature** (mandatory D3+)

**W4 — Decision Gates D-ladder D0-D5** (poprawione z D1-D5)
| Klasa | Nazwa | Gate | Human | Rollback |
|---|---|---|---|---|
| **D0** | Informational | auto | nie | — |
| **D1** | Trivial | 1 agent | nie | — |
| **D2** | Standard | 2 agents + Review | nie | opcjonalny |
| **D3** | Significant | Full Board Council 4/4 | opcjonalny | **WYMAGANY** |
| **D4** | Critical | Council 4/4 + Human | tak + Code Optimizer veto | WYMAGANY + LPW |
| **D5** | Greenfield/Systemic | Council 4/4 + Human + External | tak + zewnętrzny | WYMAGANY + LPW + CFT |

**Reguły eskalacji U1-U6**:
- U1 cost magnitude: >$100/$1k/$10k → +1/+2/+3 D-level
- U2 blast radius: multi-project / prod → +1
- U3 reversibility: rollback >1d → +1, data loss → min D4
- U4 hard preferences: blocked_providers/cost_ceilings → min D3
- U5 autonomy: `manual` → wszystko ≥D3
- U6 max: cap na D5

**W5 — SoT (Source of Truth) + Masterplan**
Księga AEIS jako **canonical reference**. Każda zmiana wyższych warstw musi być spójna z Księgą. Drift detection: gdy rada decyduje inaczej niż Księga → otwiera się `drift_audit.jsonl` ticket.

**W6 — Execution Pipeline**
**State machine z cascade rollback**: gdy coś się zmienia w środku pipeline, system inteligentnie rolluje invalidated decyzje. Statuses: `planning → executing → reviewing → done/failed`. WorkflowEngine v2: 4 triggers, 4 actions, 9 condition operators, max_chain_depth=3.

**W7 — Skills Registry**
**Manifest-driven runtime**. Każda umiejętność ma kontrakt + executor + rejestr. Workery wiążą się przez SkillBindings, nie przez kod. 132 modules manifesty. Hybrid task→skill matcher (Jaccard tagi PL × 0.6 + cosine embeddings × 0.4).

## Grupa B — Governance (W8-W14) — kontrola, bezpieczeństwo, jakość

System pilnuje zasad — koszt, bezpieczeństwo, jakość, spójność, audit.

**W8 — Demand Signal Analyzer**
Telemetria użycia skills. Wykrywa wzorce: które skille są często używane, które są deprecated, gdzie demand-supply gap. 8 tabel SQLite.

**W9 — Memory + Vault**
**6 typów pamięci**:
1. **Projektowa** — per-projekt kontekst, decyzje, artifacts
2. **Operacyjna** — runtime state, sesje, czasowe
3. **Konfiguracji** — settings operatora, preferencje
4. **Skuteczności** — co działało, co nie (efficiency learning)
5. **Podobieństwa** — vector similarity (pgvector)
6. **Decyzji człowieka** — historia operator overrides, learning signal

Plus Vault dla secrets. Replay-as-fork primitives: `SessionSnapshot` w decision_point + `ReplayFork` z model_override / context_override + `divergence_score` (cosine + Jaccard).

**W10 — Governance + Evidence Spine**
Immutable audit trail dla wszystkiego. Hash-chained, tamper-evident, GDPR-compliant.

**Evidence Pack** (D3+ wymóg):
- D3 Light: rationale ≥200 słów + rollback ≥100 + fidelity ≥50 + 1 podpis krytyka
- D5 Full: + risk_analysis + worst_case + simulation + ≥2 podpisy operatora

**17 audit chains** (NIE jeden, jak w moim oryginalnym manualu):
1. `gdpr_dsr.jsonl` — DSR actions
2. `gdpr_hard_purge.jsonl` — soft-delete purges
3. `replay_fork.jsonl` — replay runs
4. `council_wedge.jsonl` — Council Hybrid decisions
5. `cost_ledger.jsonl` — W17 cost records
6. `w19_evaluator.jsonl` — W19 jinja renders
7. `idea_lifecycle.jsonl` — 11-state transitions
8. `session_lifecycle.jsonl` — 4-state transitions
9. `audit_rotation.jsonl` — rotator runs
10. `audit_chain_alert.jsonl` — monitor heartbeats + alerts
11. `rbac_v2.jsonl` — capability grants + checks
12. `workflow_engine.jsonl` — rule fires
13. `adr_signoff.jsonl` — Council ADR sign-off
14. `g2_template_gen.jsonl` — W16 G2 LLM generation
15. `federation_policy.jsonl` — W19 routing gate decisions
16. `policy_registry.jsonl` — PgPolicyRegistry CRUD
17. `cost_ledger_migration.jsonl` — JSONL→PG migrator runs

GDPR DSR: Article 15 (Access) / 16 (Rectification) / 17 (Erasure) / 20 (Portability). HardPurgeCron 30d grace.

**W11 — Adapter Bus**
Multi-LLM routing — jednorodne API dla wszystkich providerów.

**Subscription waterfall** (kluczowe — to czego brakowało w fazie 7):
```
1. Subscription tier (free, rate-limited)
   ↓ exhausted
2. PAYG (paid per-token)
   ↓ approaches budget
3. Budget Cap (hard halt)
```

10+ modeli: claude-sonnet-4-6, claude-opus-4-7, gpt-5, gemini-2.5-pro, kimi-k2, glm-4.6, grok-4, qwen2.5:72b/7b lokalnie. Cost adapters per provider. 4 metric families: dispatch_total, dispatch_seconds, circuit_state, failures_total.

**W12 — Operator Mobile**
KMP (Kotlin Multiplatform). HMAC bind dla rejestracji urządzenia, follow-me push (FCM), biometric step-up auth, offline queue zadań.

**W13 — Advisor Layer** ⚡ KLUCZOWA WARSTWA — patrz osobny dokument `00_ADVISOR_LAYER.md`
**Aktywna inteligencja** AEIS: 4 filary, 16 lifecycle hooks, 5 Specialized Advisors. To była **NAJWIĘKSZA LUKA** w oryginalnym manualu.

**W14 — Testing Ontology**
**12 epików E1-E12 + 25 typów obiektów + 12 enums + OntologyStore**. Operacyjne testowanie: charters, findings, simulations, auto-repair, guardians, release rail.

## Grupa C — Project Lifecycle (W15-W19) — od idei do produkcji

System prowadzi projekt przez całe życie.

**W15 — Ontology Runtime Plane**
Formalny model projektu jako runtime artifact. Customer / Order / Product / Invoice / Payment / User / Role / Permission jako pojęcia domenowe. **Manifest validator** (`aeis_v2/ontology/manifest.py`) — runtime walidacja.

**W16 — Operational Apps Builder Plane**
G1 cascade (parallel verdicts) + G2 template generation + G3 demand signals migration. EvidencePackViewer / HumanGateInbox / CouncilVotePanel / AdvisorCardFeed.

**W17 — Deployment Plane (hybrid)**
Hybrid deploy: lokalne / VPS / hybrid / container / device. Cost ledger z JSONL→PG migration. Routing decisions per environment.

**W18 — Operator Terminal Plane**
Ten dokument = manual operatora. Faza-by-faza workflow przez UI. **41 faz manuala działa głównie tu.**

**W19 — Policy / Security Plane**
PgPolicyRegistry, federation policy, jinja-based policy evaluator, W19 routing gate decisions.

---

# CZĘŚĆ III — Mapowanie warstw na fazy 1-41

| Faza | Co operator robi | Warstwy aktywne | Advisor hooks |
|---|---|---|---|
| 1 | Setup + Onboarding | W1, W2, W3 (Identity), W9 (Vault) | Onboarding Wizard |
| 2 | Provider Catalog | W4, **W11 (Adapter Bus)**, **W13 Subscription Advisor** | hard gate |
| 3 | Environment Configuration | W6, W7 (Sovereignty), W17 | Scaling Advisor |
| 4 | Workspace Defaults | W8, W13 (Adaptive Preferences) | preferences |
| 5 | Autonomy Configuration | **W9 Hard Gates**, **W4 D-ladder D0-D5** | hooks/4 filary |
| 6 | Coherence Guard | **W11 Findings Hub**, **W12 Coherence&Provenance** | drift detection |
| 7 | Cost Guard | **W11 Adapter Bus subscription waterfall**, **W13** | cost ceiling |
| 8 | Security Guard | **W13 Cost+Security+Compliance**, W19 | compliance |
| 9 | Quality Guard | **W14 Quality Gates** | testing |
| 10 | Provenance Guard | **W12 + W10 Audit Chains** (17 chains!) | provenance |
| 11 | Skills Library | **W7 Skills Registry**, W8 Demand | usage analyzer |
| 12-15 | Templates | **W7 Skills Registry** + W3 Council templates | adaptive prefs |
| 16 | Project Inception | **W2 Idea Lifecycle (11 stanów)**, W16 | idea_lifecycle |
| 17 | Goal Definition | W15 Ontology Runtime, W5 SoT | role resolver |
| 18 | Scope Definition | W5 SoT + W15 Ontology | role resolver |
| 19 | Initial Council Config | **W3 Council Hybrid (9 ról × 5 rang)** | role resolver |
| 20 | Council Convening | **W3 Council Hybrid + W17 (4 fazy deliberacji)** | role resolver |
| 21 | Initial Verdicts | **W3 Phase 1 (parallel verdicts)** | — |
| 22 | Deliberation Rounds | **W3 Phase 2 (discussion)** | — |
| 23 | Consolidation | **W3 Phase 3 (consolidated vote) + Phase 4 (critic signature)** | — |
| 24 | Council Book | **W10 Evidence Spine** | adr_signoff |
| 25 | Księga Finalization | **W5 SoT (canonical reference)** | drift detection |
| 26 | Model Selection | **W5 Capability Routing**, W11 | role resolver |
| 27 | Skill Synthesis | **W7 Skills Registry**, W8 Demand | demand analyzer |
| 28 | Masterplan (z 28.4) | **W18 Planning + W6 Execution Pipeline** | scaling advisor |
| 29 | Test Plan | **W14 Testing Ontology** | testing advisor |
| 30 | Pre-Flight Cost | **W13 Cost+Compliance + Subscription Advisor** | cost waterfall |
| 31 | Pre-Flight Dry Run | W6 Execution Pipeline (cascade) | dry run |
| 32 | Build Initialization | **W19 Execution + W6 + W17 Deployment** | scaling advisor |
| 33 | Sequential Phase Execution | **W19 Execution Pipeline** | — |
| 34 | Mid-Build Council Reconvening | **W3 Council Hybrid (mini)** | role resolver |
| 35 | Build Orchestration | **W6 Cascade Rollback + W19** | — |
| 36 | Build Completion | **W12 + W14 Quality Gates** | — |
| 37 | Quality Gates | **W14 (12 epików E1-E12)** | testing advisor |
| 38 | Acceptance Testing | W14 + Customer notifications | — |
| 39 | Pre-Deploy Final Check | **W17 Deployment Plane**, W19 Policy | scaling advisor |
| 40 | Production Deploy | **W17 Hybrid Deploy + W19 Routing** | — |
| 41 | Project Closure | **W9 Memory + Vault (6 typów) + W10 Evidence Spine** | learning loop |

---

# CZĘŚĆ IV — Cross-cutting concerns

Niektóre rzeczy działają **przez wiele warstw** — to są cross-cutting concerns:

## 4.1. Audit chain — wszędzie
17 audit chains operują **continuously across all phases**. Każda akcja w fazie 1-41 generuje wpis w odpowiednim chain.

## 4.2. Advisor hooks — w każdej fazie
16 lifecycle hooks emituje AdvisorCards w runtime. **W żadnej fazie nie ma "ciszy"** — Advisor zawsze może zasugerować coś operatorowi.

## 4.3. RBAC + capabilities (W7+)
Każda akcja sprawdza capability. 5-tier canonical RBAC + 3 nowe role v2 (`replay_operator`, `lifecycle_manager`, `metrics_viewer`).

## 4.4. Subscription waterfall (W11)
Cost decisions **nigdy** nie są o pojedynczym providerze — zawsze idą przez waterfall: subscription → PAYG → cap.

## 4.5. Drift detection (W5+W12)
Każda decyzja sprawdza spójność z Księgą. Drift → ticket w `drift_audit.jsonl`.

## 4.6. Replay-as-fork (W9)
W każdej fazie operator może "fork" decision point z model_override. Nie zaakceptował verdyktu Council? Replay z innym modelem.

---

# CZĘŚĆ V — Customer Y CRM przez warstwy

Pełen lifecycle Customer Y CRM **mapowany na warstwy**:

```
FAZA 1-15 (Operator Setup):
  Aktywne: W1 (UI), W2 (idea state: brak), W3 (operator profile),
           W4 (D-ladder zainicjalizowane), W7 (skills loaded),
           W8 (demand baseline), W9 (memory init z 6 typami),
           W11 (Adapter Bus z subscription waterfall)
  
  Advisor hooks emitowane:
    - Onboarding Wizard 10 kroków
    - Subscription Advisor (przy dodawaniu providers): "Anthropic Pro
      tier saved $40/mo vs PAYG dla expected workload"
    - Scaling Advisor: "Lokalne GPU zalecane dla Bielik (free)"

FAZA 16-19 (Project Inception):
  W2 Idea Lifecycle: draft → submitted → under_review → approved
  W3 Council Hybrid: 9 ról zaalokowane
  W4 D-level: D4 (Critical) — payment + customer-facing
  W5 SoT: Księga zarezerwowana
  W15 Ontology: Customer/Invoice/Payment domain entities
  
  Advisor hooks:
    - Role Resolver: "Dla Polish KSeF compliance, dodaj rolę
      Polish Tax Specialist do Council"
    - Funding Advisor (opt-in): "FENG SMART 1.1 grant 30M PLN
      potential dla cybersecurity-adjacent CRM"

FAZA 20-25 (Council → Księga):
  W3 Council Hybrid: 4 fazy deliberacji × 9 ról
    Phase 1: parallel verdicts (9 niezależnych)
    Phase 2: discussion (1-2 rundy)
    Phase 3: consolidated vote (weighted)
    Phase 4: Critic signature (mandatory D4)
  W5 SoT: Księga jako canonical
  W10 Evidence Spine: D4 Evidence Pack (rationale ≥200, rollback ≥100,
    fidelity ≥50, critic signature)
  
  Audit chains aktywne:
    - council_wedge.jsonl (Council decisions)
    - adr_signoff.jsonl (ADR sign-off)

FAZA 26-31 (Planning):
  W6 Execution Pipeline: planning state
  W18 Planning Plane: layer decomposition + 5 resource profiles
  W14 Testing Ontology: 12 epików zaplanowane
  
  Advisor hooks:
    - Scaling Advisor: "Profile 2 (2 workers, 1 staging) optimal
      dla 50-user SaaS"
    - Variants Generator: 3 plany cost-saving / balanced / aggressive
    - Subscription Advisor: "Anthropic subscription już
      consumed 65% — switching to PAYG dla Stage 4"

FAZA 32-36 (Build Execution):
  W6 Execution Pipeline: planning → executing → reviewing → done
  W17 Deployment Plane: staging Hetzner CX21 provisioned
  W19 Policy: routing gate dla EU-only data
  
  Cascade rollback (W6) aktywne — mid-build Council scope change
  invalidate Phase 4-5 decisions, cascade rollback Phase 4 tasks.

FAZA 37-41 (Testing + Deploy + Closure):
  W14 Testing Ontology: L1-L5 ze wszystkich 12 epików
  W17 Deployment: production CX31, canary stages
  W9 Memory: post-closure — projekt move to "Skuteczności" pamięć
    (efficiency learning: co działało, co nie)
  W10 Evidence Spine: final D5 Evidence Pack (closure)
  
  Replay-as-fork (W9): Customer Y CRM dostępny do replay
  jako template dla future Polish SaaS projects.
```

**Subscription waterfall w trakcie projektu** (W11):

| Faza | Subscription tier used | PAYG used | Total |
|---|---|---|---|
| 1-15 (Setup) | $0 | $0.0003 | $0.0003 |
| 16-25 (Council) | ~$30 (Anthropic Pro) | $26.60 | $56.60 |
| 26-31 (Planning) | $30 (subscription) | $32.10 | $32.10* |
| 32-36 (Build) | $40 (Pro tier consumed) | $142.30 | $142.30* |
| 37-41 (Test+Deploy+Closure) | Subscription exhausted | $127.20 | $127.20 |
| **TOTAL** | **~$100 z subscription** | **~$258 PAYG** | **~$358** |

\* Te kwoty po reduction z subscription tier

**Key insight**: Z subscription waterfall, paid spend **na key** to ~$258 / 9 keys ~ $30 per key. **Mieści się w $5-100 per key cap** Roberta dla testing.

---

# CZĘŚĆ VI — Korekta planu testowego z 9 throwaway keys

**Oryginalne błędne założenie**: $50-100 per key × 9 keys = $450-900 budget

**Faktyczne**: 
- $5 per model (cap per test environment)
- 10 testów planowanych = $0.50 per test budget
- Subscription tokens ZAWSZE pierwsze (free tier)
- 9 modeli total = **$45 testowy budget total**

**Co się zmienia w Cost Guard (faza 7)** — pełen patch:

```
{
  "subscription_tracking": {
    "anthropic_pro": {
      "monthly_quota_remaining": "$30 (Pro tier)",
      "consumed_this_month": "$0",
      "reset_date": "2026-05-01"
    },
    "openai_plus": {
      "monthly_quota_remaining": "$20 (Plus tier)",
      ...
    },
    ...
  },
  "paid_tokens": {
    "anthropic_payg": {
      "spent_this_month": "$0",
      "hard_cap": "$5 (test environment)",
      "remaining_budget": "$5"
    },
    ...
  },
  "decision_priority": [
    "1. Use subscription tier first (free quota)",
    "2. Switch to PAYG only when subscription exhausted",
    "3. Hard halt at PAYG cap ($5)",
    "4. Trigger Subscription Advisor jeśli PAYG approaching cap"
  ]
}
```

**Subscription Advisor (W13) hard gate** w faza 7:
- Trigger: PAYG spending > 80% w 5 dni (sustainable concern)
- Action: emit AdvisorCard "Rozważ subscription upgrade — ROI x w 30 dni"
- Operator decision: upgrade subscription (D3+ Evidence required) lub continue PAYG

---

# CZĘŚĆ VII — Status implementacji warstw (z pliku 54KB)

| Warstwa | Status implementacji v1 | Status v2 | Komentarz |
|---|---|---|---|
| W1 Operator Interface | ✓ 13 surfaces | ✓ + nowe surfaces v2 | Next.js 16, dark theme |
| W2 Idea Lifecycle | ✓ 15 stanów | ✓ uproszczone do 11 (commit aa08334c) | Fully working |
| W3 Council Hybrid | ✓ 9 ról × 5 rang | ✓ + wedge dla W16 G1 cascade | 18/18 testów |
| W4 D-ladder | ✓ D0-D5 + U1-U6 | ✓ rozszerzone | classify_decision() |
| W5 SoT | ✓ Księga 462 strony | ✓ + manifest validator | Drift detection |
| W6 Execution Pipeline | ✓ + cascade analysis | ✓ WorkflowEngine v2 | 44/44 testy |
| W7 Skills Registry | ✓ 132 modules | ✓ hybrid task→skill matcher + RBAC v2 | 25/25 testów |
| W8 Demand Signal | ✓ + 8 tabel | — | Telemetria działa |
| W9 Memory + Vault | ✓ 6 typów | ✓ + audit chain v2 + Replay-as-fork | 24/24 + 31/31 testów |
| W10 Governance | ✓ Evidence Pack | ✓ + GDPR DSR + ADR sign-off | 28/28 + 25/25 testów |
| W11 Adapter Bus | ✓ ~10 modeli | ✓ + Prometheus metrics | 16/16 testów |
| W12 Operator Mobile | ✓ częściowo (REST) | — backlog | KMP planowane |
| **W13 Advisor** | **✓ 13 sub-services** | **— Task-to-Role Suggester** | **Najważniejsze v2 expansion** |
| W14 Testing Ontology | ✓ 12 epików E1-E12 | ✓ rozbudowane | OntologyStore działa |
| W15 Ontology Runtime | — | ✓ Sprint 4 production-complete | NEW v2 plane |
| W16 Apps Builder | — | ✓ G1+G2+G3 + audit chain | NEW v2 plane |
| W17 Deployment | — | ✓ hybrid + cost ledger PG | NEW v2 plane |
| W18 Operator Terminal | — | ✓ This manual = main UI | NEW v2 plane |
| W19 Policy/Security | — | ✓ PgPolicyRegistry + federation | NEW v2 plane |

**Implementation completeness**: ~85% (v1 fully done, v2 sprint 4 production-complete dla W15-W19, Advisor v2 expansion w toku).

---

# CZĘŚĆ VIII — Co dalej

Po przeczytaniu tego dokumentu, następne kroki:

1. **Przeczytaj** `00_ADVISOR_LAYER.md` — pełen W13 deep dive (najważniejsza warstwa)
2. **Przeczytaj** `00_PATCHES_FAZ.md` — naprawy fazy 5 (D0), 7 (Subscription waterfall), 20-25 (Council 9 ról × 5 rang)
3. **Wróć do** 41 faz z mapowaniem warstw — teraz każda faza ma kontekst architektoniczny

**Kluczowe rozumienie**:
- 41 faz = **operacyjny workflow** (co i kiedy)
- 19 warstw = **architektoniczny system** (z czego)
- Advisor (W13) = **proaktywna inteligencja** (co AEIS sam zauważa)

🎯 **Manual jest teraz kompletny** — workflow + architektura + Advisor.

---

# Załącznik — Kanoniczne nazewnictwo

W oryginalnym pliku 54KB jest też kanoniczna nazwa **L1-L12** (logiczny stos z `docs/claude_system_audit/`) — to **inny model** niż W1-W19. Ten dokument używa **W1-W19** (architektoniczne planes z Księgi i v2). L1-L12 osobno w `AEIS_LAYERS_AND_MODULES.md`.

**Konwencja w manualu 41-fazowym**: zawsze używamy **W1-W19**. Gdy faza działa na warstwie, oznaczamy `[W3]`, `[W11]`, etc.
