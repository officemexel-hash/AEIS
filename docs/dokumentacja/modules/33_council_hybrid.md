# 33. Council Hybrid — 9 ról × 5 rang × weighted vote
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Cross-cutting documentation — Rada Modeli (Council Hybrid): definicja 9 ról
> kanonicznych, 5 rang, weighted vote math, critic signature gate, sentinele,
> gated consolidation, quorum, tie-breaking, audit. Wersja: 1.0 (2026-04-26).

---

## Spis treści

1. [Filozofia rady](#1-filozofia-rady)
2. [9 ról kanonicznych](#2-9-ról-kanonicznych)
3. [5 rang (Junior → Master)](#3-5-rang-junior--master)
4. [Weighted vote math](#4-weighted-vote-math)
5. [Critic signature gate](#5-critic-signature-gate)
6. [Sentinele (cost + security)](#6-sentinele-cost--security)
7. [Gated consolidation](#7-gated-consolidation)
8. [Quorum i tie-breaking](#8-quorum-i-tie-breaking)
9. [Audit trail (gdzie składowane głosy)](#9-audit-trail-gdzie-składowane-głosy)
10. [Per-D-level Council usage](#10-per-d-level-council-usage)
11. [Case studies (3 różne D-poziomy)](#11-case-studies-3-różne-d-poziomy)
12. [Cross-references](#12-cross-references)

---

## 1. Filozofia rady

Rada Modeli (Council Hybrid) jest **organem deliberacyjnym LLM-owym** SYLION.
Każda decyzja D4 lub wyższa wymaga sesji rady, w której wielu modeli LLM
(z różnymi rolami i rangami) niezależnie ocenia decyzję, dyskutuje, a następnie
wynik jest agregowany przez weighted vote z gatami na critic signature i
sentineli.

Cele:

- **Multi-perspektywiczna ocena** — różne role widzą decyzję inaczej (planner
  patrzy na wykonalność, critic na luki, security na zagrożenia, finance na
  budżet, legal na zgodność).
- **Audytowalna deliberacja** — każdy podgłos jest zapisany z rationale i hashem,
  więc audytor może replayować sesję.
- **Skalowalna autonomia** — operator nie musi sam analizować decyzji od zera; rada
  daje pre-analizę z wieloma punktami widzenia.
- **Bezpieczeństwo** — sentinele cost i security mogą zablokować decyzję mimo
  pozytywnego głosowania.
- **Determinism** — przy seedingu i tym samym contextcie sesja jest powtarzalna
  (replay-safe), co jest wymagane dla compliance review.

### Reguła podstawowa

```
weighted vote NIE jest jedynym wymogiem.
Decyzja może być uchwalona TYLKO gdy:
  1. weighted vote ≥ próg dla D-level
  2. ≥1 critic role ma podpis (signature gate)
  3. Żaden sentinel nie zablokował (sentinel_blocks empty)
  4. Quorum ≥ wymagany dla D-level
```

---

## 2. 9 ról kanonicznych

```
planner            architect          critic
verifier           governance         cost_sentinel
security_sentinel  domain_specialist  funding_specialist
```

### 2.1 Per rola — opis i kompetencje

| Rola | Opis | Co ocenia | Kiedy aktywna |
|---|---|---|---|
| **planner** | Patrzy na wykonalność z perspektywy roadmapy/capacity. | Czy plan jest realizowalny w bieżącym kwartale? Czy nie konfliktuje z aktywnymi priorytetami? | Każda sesja D2+ |
| **architect** | Patrzy na strukturę techniczną, długoterminowy kierunek. | Czy decyzja pasuje do założonej architektury? Czy nie tworzy debtu? | Każda sesja D3+ |
| **critic** | Stress-test założeń. Szuka luk logicznych, brakujących evidence, nieuzasadnionych skoków. | Czy rationale trzyma się bez nieuzasadnionych skoków? Czy load-bearing assumption jest support'owana? | **Zawsze** — signature gate |
| **verifier** | Weryfikator — sprawdza, czy proponowane fidelity_test rzeczywiście zweryfikuje cel. | Czy fidelity_test jest mierzalny, falsyfikowalny? Czy data source jest dostępny? | Każda sesja D3+ |
| **governance** | Patrzy na zgodność z policies/regulami operatora i organizacji. | Czy decyzja respektuje hard preferences? Czy autonomy gates są honorowane? | Każda sesja D3+ |
| **cost_sentinel** | Sentinel kosztu — może **zablokować** decyzję jeśli koszt przekracza próg. | Czy koszt mieści się w budżecie? Czy nie ma niedoszacowania? | Każda sesja D3+ + **może blokować** |
| **security_sentinel** | Sentinel bezpieczeństwa — może **zablokować** decyzję ze względu na threat surface, secret handling. | Czy są nowe attack surfaces? Czy nie ma supply-chain risk? Czy least-privilege jest spełniony? | Każda sesja D3+ + **może blokować** |
| **domain_specialist** | Specjalista domeny projektu (software/research/funding/...) — opcjonalnie aktywny w zależności od `project_domain`. | Czy decyzja respektuje specyfikę domeny? | Sesje gdy `project_domain` ma zarejestrowanego specjalistę |
| **funding_specialist** | Specjalista grantów/dofinansowań — aktywny przy decyzjach typu `FUNDING_*`. | Czy decyzja koreluje z eligibility kryteriami grantów? | Sesje z `FundingCard` D3+ |

### 2.2 Tabela: rola → bias → keyword sensitivity

(Z implementacji `sylion.cognitive.council.voting`):

| Rola | bias (approve, reject, abstain) | Keyword nudges |
|---|---|---|
| planner | (0.55, 0.30, 0.15) | brak |
| critic | (0.30, 0.50, 0.20) | brak |
| security (security_sentinel) | (0.30, 0.55, 0.15) | nudge REJECT na: secret, password, token, exploit, vuln, cve, injection, rce, priv esc |
| legal (governance proxy) | (0.35, 0.40, 0.25) | nudge REJECT na: gdpr, ccpa, copyright, license, patent, export control, nda, contract |
| finance (cost_sentinel proxy) | (0.45, 0.40, 0.15) | brak |
| council_chair | (0.50, 0.35, 0.15) | brak |

Dla pozostałych ról niezdefiniowanych w `_ROLE_BIAS`: default (0.45, 0.40, 0.15).

### 2.3 Decision-class skew

Wyższe klasy decyzji "pchają" deliberację w stronę REJECT (wyższy próg
zatwierdzenia):

| Decision class | (Δ approve, Δ reject, Δ abstain) |
|---|---|
| D0 | +0.10, -0.05, -0.05 |
| D1 | +0.05, -0.02, -0.03 |
| D2 | +0.00, +0.00, +0.00 |
| D3 | -0.05, +0.05, +0.00 |
| D4 | -0.10, +0.10, +0.00 |
| D5 | -0.15, +0.15, +0.00 |

---

## 3. 5 rang (Junior → Master)

```
primary  →  senior  →  support  →  review_only  →  validation_only
```

Kanoniczne nazwy w SYLION (`sylion.governance.council_hybrid`):

| Ranga | Mnożnik wagi | Opis | Typowe zastosowanie |
|---|---|---|---|
| **primary** | 1.00 | Pełnoprawny członek z najwyższą wagą głosu | Decydujące role w sesji |
| **senior** | 0.80 | Doświadczony, prawie pełna waga | Wsparcie role primary |
| **support** | 0.50 | Wspomagająca | Dodatkowy punkt widzenia |
| **review_only** | 0.25 | Tylko dyskusja/obserwator | Nie liczone w final tally |
| **validation_only** | 0.10 | Walidacja techniczna | Tylko sprawdzenie poprawności formy |

### 3.1 Tabela ranga → uprawnienia

| Ranga | Vote count? | Może podpisać critic gate? | Może być sentinel block? | Discussion phase |
|---|---|---|---|---|
| primary | tak | tak | tak (jeśli rola=sentinel) | tak |
| senior | tak (×0.80) | tak | tak (×0.80 effective wagi blokady) | tak |
| support | tak (×0.50) | tak | nie (sentinel block jest binarny) | tak |
| review_only | nie | nie | nie | tak (komentarze do dyskusji) |
| validation_only | nie | nie | nie | nie (tylko walidacja form) |

### 3.2 Default rank assignment

Przy formacji rady (event `aeis.council.formation_requested`):

```
critic              → primary (always)
governance          → primary
cost_sentinel       → primary
security_sentinel   → primary
planner             → senior
architect           → senior
verifier            → support
domain_specialist   → support (review_only jeśli brak specjalisty)
funding_specialist  → support (validation_only jeśli FundingCard absent)
```

---

## 4. Weighted vote math

### 4.1 Wagi domyślne

```
DEFAULT_ROLE_WEIGHTS = {
    "planner":            1.0,
    "architect":          1.0,
    "critic":             1.0,
    "verifier":           0.6,
    "governance":         1.0,
    "cost_sentinel":      1.0,
    "security_sentinel":  1.0,
    "domain_specialist":  0.8,
    "funding_specialist": 0.6,
}

RANK_MULTIPLIER = {
    "primary":         1.00,
    "senior":          0.80,
    "support":         0.50,
    "review_only":     0.25,
    "validation_only": 0.10,
}
```

### 4.2 Formuła

```
voting_weight(role, rank) = DEFAULT_ROLE_WEIGHTS[role] × RANK_MULTIPLIER[rank]
```

### 4.3 Tabela przykładów

| Role | Rank | Weight |
|---|---|---|
| critic | primary | 1.00 × 1.00 = **1.00** |
| critic | senior | 1.00 × 0.80 = **0.80** |
| cost_sentinel | support | 1.00 × 0.50 = **0.50** |
| planner | primary | 1.00 × 1.00 = **1.00** |
| planner | support | 1.00 × 0.50 = **0.50** |
| verifier | support | 0.60 × 0.50 = **0.30** |
| domain_specialist | review_only | 0.80 × 0.25 = **0.20** (nie liczone w tally) |
| funding_specialist | primary | 0.60 × 1.00 = **0.60** |
| funding_specialist | validation_only | 0.60 × 0.10 = **0.06** (nie liczone) |

### 4.4 Tally

```
total_weight_in_favor      = Σ weight_i × indicator(vote_i == "approve")
total_weight_against       = Σ weight_i × indicator(vote_i == "reject")
total_weight_voting        = total_weight_in_favor + total_weight_against
total_weight_abstaining    = Σ weight_i × indicator(vote_i == "abstain")

approval_ratio = total_weight_in_favor / total_weight_voting
```

### 4.5 Przykład wyliczenia (D4 sesja)

Skład rady (8 voting members, 1 review_only):

| Role | Rank | Weight | Vote |
|---|---|---|---|
| planner | primary | 1.00 | approve |
| architect | senior | 0.80 | approve |
| critic | primary | 1.00 | reject |
| verifier | support | 0.30 | approve |
| governance | primary | 1.00 | approve |
| cost_sentinel | primary | 1.00 | approve |
| security_sentinel | primary | 1.00 | reject |
| domain_specialist | senior | 0.64 | approve |
| funding_specialist | review_only | 0.15 | (nie liczone) |

Tally:
```
in_favor   = 1.00 + 0.80 + 0.30 + 1.00 + 1.00 + 0.64 = 4.74
against    = 1.00 + 1.00 = 2.00
voting_total = 4.74 + 2.00 = 6.74
approval_ratio = 4.74 / 6.74 = 0.703 (70.3%)
```

D4 wymaga ≥66% (zob. §10). 70.3% ≥ 66% → vote pass. Ale:
- Critic vote = reject → critic signature gate **NIE pass**.
- Security_sentinel vote = reject → sentinel block **aktywne**.

Final outcome: **NOT consolidated**, decision blocked, wraca do operatora z dissenting opinions.

---

## 5. Critic signature gate

### 5.1 Reguła

Aby decyzja D3+ przeszła consolidation, **co najmniej 1 critic** musi explicitly
podpisać (signature) — nie tylko zagłosować approve, ale wykonać krok podpisu
po review final rationale + rollback + fidelity_test.

```python
def consolidate_with_signatures(text, require_critic=True, require_sentinels_pass=True):
    if require_critic:
        critic_signs = [s for s in session.signatures if s.role == "critic"]
        if len(critic_signs) < 1:
            return ConsolidationResult(consolidated=False, reason="no_critic_signature")
    ...
```

### 5.2 Co znaczy podpis krytyka

Podpis krytyka to **explicit potwierdzenie**, że:

1. Krytyk przeczytał całą Evidence Pack (rationale, rollback, fidelity).
2. Krytyk uznał, że nie ma niezaadresowanego load-bearing assumption.
3. Krytyk akceptuje, że decyzja może być wykonana.

Podpis ≠ głos approve. Krytyk może zagłosować approve ale **nie podpisać** (np. "OK, ale nie biorę odpowiedzialności"), albo zagłosować reject i tym samym signature gate jest blokowany.

### 5.3 Tabela: kombinacje vote + signature

| critic vote | critic signature | Outcome |
|---|---|---|
| approve | signed | **OK** — gate pass |
| approve | NOT signed | gate fail (operator musi rerun lub przekonać krytyka do podpisu) |
| reject | (nie wymaga) | gate fail (vote reject = no-go) |
| abstain | NOT signed | gate fail |

### 5.4 Endpoint do podpisu

```
POST /api/v1/workspace/council/sessions/{sid}/critic/sign
{
  "critic_id": "council-critic-001",
  "rationale": "Reviewed all assumptions; no load-bearing leaps detected",
  "signature_payload": "base64:..."
}
```

Skutek: insert do `council_critic_signatures`, emit
`aeis.advisor.council.critic_signed` event.

---

## 6. Sentinele (cost + security)

### 6.1 Cel

Sentinele są **niezależnymi blokerami**, działającymi obok normalnego głosowania.
Sentinel może przepuścić decyzję (signoff: reviewed=true, approved=true) lub
zablokować (signoff: approved=false → trafia do `sentinel_blocks`).

### 6.2 Cost sentinel

Patrzy na:
- Estymowany koszt vs budżet operatora.
- Czy nie ma niedoszacowania (sandbagging).
- Czy break-even ma sens.
- Czy alternatywne tańsze opcje były rozważone.

Może zablokować nawet jeśli vote przegłosował i operator zaakceptował, jeżeli:
- Koszt przekracza preferowany ceiling z preferences.
- Estymowany koszt ≥ 2× zadeklarowany.
- Brak rationale dla wybranej opcji vs tańszej alternatywy.

### 6.3 Security sentinel

Patrzy na:
- Threat surface zmiany.
- Secret handling.
- Supply chain (nowe dependencies, nowi providers).
- Least-privilege compliance.
- CVE detection.

Może zablokować jeśli:
- Wprowadza nowy attack surface bez mitigation.
- Decyzja wymaga share'owania secrets na granicy zaufania.
- Wymaga nowego provider'a, który nie ma audytu compliance.

### 6.4 Endpoint sentinel

```
POST /api/v1/workspace/council/sessions/{sid}/sentinels/evaluate
{
  "sentinel_kind": "cost" | "security",
  "sentinel_id": "...",
  "reviewed": true,
  "approved": false,
  "block_reason": "Cost estimate $1500 exceeds preferred ceiling $200",
  "notes": "..."
}
```

### 6.5 Reguła: sentinel block jest binarny

Sentinele nie głosują weighted, tylko binarnie:
- `reviewed=true, approved=true` → pass.
- `reviewed=true, approved=false` → **block** (blokuje consolidation niezależnie od vote).
- `reviewed=false` → not yet evaluated; gate nie może pass do momentu sentinel review.

### 6.6 Override sentinel block

Operator może **override sentinel block** tylko poprzez ścieżkę D5 z dodatkowym
multi-sig (operator + ≥2 council members + drugi sentinel z explicit notatką).
Override jest zapisywany jako separate Evidence Pack.

---

## 7. Gated consolidation

### 7.1 Endpoint

```
POST /api/v1/workspace/council/sessions/{sid}/consolidate-gated
```

### 7.2 Atomic gates checked

```python
def consolidate_with_signatures(session_id, text, require_critic=True, require_sentinels_pass=True):
    # Gate 1: Quorum
    if not has_quorum(session_id):
        return Result(consolidated=False, reason="no_quorum")

    # Gate 2: Vote threshold
    tally = compute_weighted_tally(session_id)
    threshold = THRESHOLD_BY_DECISION_CLASS[session.decision_class]
    if tally.approval_ratio < threshold:
        return Result(consolidated=False, reason="vote_below_threshold",
                      tally=tally, threshold=threshold)

    # Gate 3: Critic signature
    if require_critic:
        if count_critic_signatures(session_id) < 1:
            return Result(consolidated=False, reason="no_critic_signature")

    # Gate 4: Sentinel pass
    if require_sentinels_pass:
        cost_signoff = get_sentinel_signoff(session_id, "cost")
        sec_signoff = get_sentinel_signoff(session_id, "security")
        if not (cost_signoff and cost_signoff.approved):
            return Result(consolidated=False, reason="cost_sentinel_blocks",
                          block_reason=cost_signoff.notes if cost_signoff else "not_evaluated")
        if not (sec_signoff and sec_signoff.approved):
            return Result(consolidated=False, reason="security_sentinel_blocks",
                          block_reason=sec_signoff.notes if sec_signoff else "not_evaluated")

    # All gates pass: persist consolidated text
    persist_consolidated(session_id, text, tally)
    emit_event("aeis.advisor.council.session_consolidated", {...})
    return Result(consolidated=True, tally=tally)
```

### 7.3 Tabela: który gate dla którego D-level

| Gate | D2 | D3 | D4 | D5 |
|---|---|---|---|---|
| Quorum | optional | required | required | required (większy) |
| Vote threshold | ≥50% | ≥60% | ≥66% | ≥75% |
| Critic signature | optional | optional | required | required |
| Cost sentinel pass | optional | optional | required | required |
| Security sentinel pass | optional | optional | required | required |
| Multi-signature pack | n/a | n/a | n/a | required (3+) |

---

## 8. Quorum i tie-breaking

### 8.1 Quorum

Minimum liczba uczestników aktywnie głosujących (not abstaining), per D-level:

| D-level | Min voting members | Min different roles | Min different ranks |
|---|---|---|---|
| D2 | 2 | 2 | dowolne |
| D3 | 4 | 3 | dowolne |
| D4 | 6 | 4 | ≥2 (primary lub senior) |
| D5 | 7 | 5 | ≥3 (primary) |

### 8.2 Tie-breaking

Gdy weighted vote daje **dokładnie próg** (np. dokładnie 66.0% dla D4), tie-breaker
jest `council_chair`:

```
if approval_ratio == threshold (within 0.001 epsilon):
    council_chair_vote determines outcome (approve → pass, reject → fail, abstain → fail)
```

Jeżeli `council_chair` nie jest obecny w sesji:
```
fallback: rola "governance" w randze primary
fallback 2: rola "architect" w randze primary
fallback 3: vote NIE przechodzi (default-deny przy ties)
```

### 8.3 Tie-breaking po vote: dissenting opinions

Wszystkie głosy `reject` w sesji która consolidated muszą zostać zapisane jako
`dissenting_opinions` w Evidence Pack:

```yaml
council_vote:
  ...
  dissenting_opinions:
    - role: critic
      opinion: "Concerned about precedent of using override..."
    - role: governance
      opinion: "Insufficient soak time in staging..."
```

### 8.4 Brak konsensusu (consensus_reached = false)

Sesja może consolidated nawet bez full consensus, jeżeli:
- Vote ratio ≥ threshold dla D-level.
- Critic signature jest.
- Sentinele OK.
- Operator explicitnie zaakceptuje override z dodatkowym rationale.

W tym przypadku Evidence Pack zawiera notatkę "consensus_reached=false, override
explanation=..." i wymaga dodatkowego signature operatora.

---

## 9. Audit trail (gdzie składowane głosy)

### 9.1 Tabele

```
hybrid_council_sessions      — meta sesji (session_id, decision_class, created_at, status)
council_participants         — kto uczestniczy (session_id, role, rank, model_id, weight)
council_critic_signatures    — podpisy krytyków (session_id, critic_id, signed_at, signature_payload)
council_sentinel_evaluations — sentinel signoffs (session_id, sentinel_kind, reviewed, approved, notes)
council_votes                — pojedyncze głosy (session_id, participant_id, vote, rationale, rationale_hash)
```

Wszystkie keyed off `hybrid_council_sessions.session_id`.

### 9.2 Eventy emitowane

| Event | Trigger |
|---|---|
| `aeis.advisor.council.session_started` | Nowa sesja zarejestrowana |
| `aeis.advisor.council.participant_joined` | Member dołączył |
| `aeis.advisor.council.vote_recorded` | Pojedynczy głos zapisany |
| `aeis.advisor.council.critic_signed` | Critic podpisał |
| `aeis.advisor.council.sentinel_evaluated` | Sentinel signoff |
| `aeis.advisor.council.session_consolidated` | Consolidation pass — wszystkie gates OK |
| `aeis.advisor.council.session_blocked` | Consolidation fail — gate failed |

### 9.3 Replay i determinism

Każdy głos jest deterministycznym wynikiem `seeded_vote(idea, role, seed,
decision_class)`:

```python
@dataclass
class SeededVote:
    idea: str
    role: str
    seed: int
    decision_class: str
    vote: str           # "approve" | "reject" | "abstain"
    rationale: str
    rationale_hash: str
    model_id: str
```

Same `(idea, role, seed)` zawsze produces same vote + same rationale_hash. Replay:

```python
votes = replay_votes([
    (idea_text, "planner", 42, "D4"),
    (idea_text, "critic", 42, "D4"),
    (idea_text, "security_sentinel", 42, "D4"),
])
```

---

## 10. Per-D-level Council usage

| D-level | Council session? | Composition | Próg approval |
|---|---|---|---|
| D0 | nie | – | – |
| D1 | nie | – | – |
| D2 | opcjonalnie (jeżeli operator poprosi) | minimal: planner + critic | ≥50% |
| D3 | opcjonalnie (Light EP path) | core 5: planner + critic + governance + cost_sentinel + security_sentinel | ≥60% |
| D4 | **wymagane** | full 7-9 ról | ≥66% |
| D5 | **wymagane** + multi-sig | full 9 ról primary + dodatkowe support specialists | ≥75% |

---

## 11. Case studies (3 różne D-poziomy)

### Case study 1 — D3 Council session (Subscription PURCHASE_PLAN)

**Setup:**
- Operator otrzymuje kartę `REC_TYPE_PURCHASE_PLAN` (Anthropic Pro $80/mo).
- D3 (default subscription).
- LIGHT Evidence Pack required.
- Council session opcjonalna, ale operator poprosił o opinię.

**Skład sesji (5 ról):**

| Role | Rank | Weight | Model |
|---|---|---|---|
| planner | primary | 1.00 | claude-sonnet-4-6 |
| critic | primary | 1.00 | claude-sonnet-4-6 |
| governance | primary | 1.00 | claude-sonnet-4-6 |
| cost_sentinel | primary | 1.00 | claude-sonnet-4-6 |
| security_sentinel | primary | 1.00 | claude-sonnet-4-6 |

**Głosy:**

| Role | Vote | Notes |
|---|---|---|
| planner | approve | "Predictable cost is good for capacity planning" |
| critic | approve + signed | "Break-even rationale supported by 30-day usage history" |
| governance | approve | "No hard preference conflict" |
| cost_sentinel | approved (signoff) | "Within budget; saves $10–20/mo over pay-go variance" |
| security_sentinel | approved (signoff) | "No threat surface change" |

**Tally:**
- in_favor = 5.00, against = 0.00, ratio = 100%.
- Critic signed → gate pass.
- Sentinele approved → gate pass.

**Outcome:** **CONSOLIDATED**. Operator może podpisać LIGHT Evidence Pack i akcjonować kartę.

---

### Case study 2 — D4 Council session (VPS Multi-VPS scaling)

**Setup:**
- Operator otrzymuje `REC_TYPE_VPS_SCALING` z `current=local → multi_vps`.
- Default D3, ale `affects_production=true` → upgrade do D4 lub D5 (zależnie od kosztu).
- W tym kejsie cost = $200/mo → upgrade z D3 +1 = D4 (po `U1.a`).
- D4 = FULL Evidence Pack required + Council session required.

**Skład sesji (8 ról):**

| Role | Rank | Weight | Vote |
|---|---|---|---|
| planner | primary | 1.00 | approve |
| architect | primary | 1.00 | approve |
| critic | primary | 1.00 | approve + signed |
| verifier | support | 0.30 | approve |
| governance | primary | 1.00 | approve |
| cost_sentinel | primary | 1.00 | approve (signoff) |
| security_sentinel | primary | 1.00 | reject (signoff: approved=false) |
| domain_specialist | senior | 0.64 | approve |

**Tally:**
- in_favor = 1.00 + 1.00 + 1.00 + 0.30 + 1.00 + 1.00 + 0.64 = **5.94**
- against = 1.00 (security_sentinel)
- voting_total = 6.94
- ratio = 5.94 / 6.94 = **85.6%** ≥ 66% (D4 threshold)

**Gates:**
- Quorum 8 ≥ 6 minimum → OK.
- Vote ratio 85.6% ≥ 66% → OK.
- Critic signed → OK.
- Cost sentinel approved → OK.
- **Security sentinel block** → **BLOCK**.

**Outcome:** **NOT CONSOLIDATED**. Reason: security_sentinel podał notatkę:
"Multi-VPS exposes new attack surface (3 envs × 22 ports); mitigation plan
not adequate". Operator dostaje wynik z dissenting opinion + wymaganą akcją:
poprawić Evidence Pack (rozbudować mitigation w risk_analysis), uzyskać re-review
od security_sentinel, lub uzyskać override path D5 (multi-sig + drugi sentinel).

---

### Case study 3 — D5 Council session (Production deploy override)

**Setup:**
- Operator próbuje override blocked production deploy z critical hotfix.
- D5 (zawsze D5 dla deploy override).
- FULL Evidence Pack required + multi-sig (3+ podpisy).
- D5 vote threshold ≥75%.

**Skład sesji (9 ról primary):**

| Role | Rank | Weight | Vote |
|---|---|---|---|
| planner | primary | 1.00 | approve |
| architect | primary | 1.00 | approve |
| critic | primary | 1.00 | reject + NOT signed |
| verifier | primary | 0.60 | approve |
| governance | primary | 1.00 | reject |
| cost_sentinel | primary | 1.00 | approve (signoff) |
| security_sentinel | primary | 1.00 | approve (signoff: justified by active CVE) |
| domain_specialist | primary | 0.80 | approve |
| funding_specialist | review_only | 0.15 | (not counted) |

**Tally:**
- in_favor = 1.00 + 1.00 + 0.60 + 1.00 + 1.00 + 0.80 = **5.40**
- against = 1.00 + 1.00 = **2.00**
- voting_total = 7.40
- ratio = 5.40 / 7.40 = **72.97%**

**Gates:**
- Quorum 8 ≥ 7 minimum (D5) → OK.
- Vote ratio 72.97% < 75% (D5 threshold) → **FAIL**.
- Critic NOT signed → **FAIL** (additional gate).

**Outcome:** **NOT CONSOLIDATED** (dual fail: vote ratio + critic signature).

**Operator path:**
1. Może zwołać dodatkowych members (np. drugi senior planner) by zwiększyć vote
   ratio powyżej 75%.
2. Musi przekonać krytyka do podpisu (krytyk żąda 7-day timeline dla flagged
   security findings; operator może to zaakceptować i uzyskać podpis warunkowy).
3. Alternatywnie wycofuje override i czeka na proper SOT cycle.

W tym kejsie operator zdecydował się dodać dwa zewnętrzne resources (architect + governance),
zakończyć timeline dla security findings, uzyskać critic signature, i ponownie zwołać
sesję. Re-vote dał 88.5% i critic signed → consolidation pass.

---

## 12. Cross-references

- D-ladder pełna: `31_d_ladder_complete.md`
- Evidence Pack templates: `32_evidence_pack_templates.md` (sekcja 5: D5 Full + council_vote field)
- LLM pool routing per role: `34_llm_pool_routing.md`
- Eventy `aeis.advisor.council.*`: `30_event_taxonomy_full.md`
- Architektura: `00_architektura_systemu.md` §6 Rada Modeli
- Pełny opis decyzji: `05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md`
- Kod council voting: `src/sylion-pipeline/sylion/cognitive/council/voting.py`
- Implementacja CouncilHybrid: `src/sylion-pipeline/sylion/governance/council_hybrid.py` (referowany w architekturze)
- Memory canonical: project_council_canonical (9 ról × 5 rang × weighted vote, critic signature gate, sentinele)
- API: `/api/v1/workspace/council/*` (endpointy w architekturze §6.5)
