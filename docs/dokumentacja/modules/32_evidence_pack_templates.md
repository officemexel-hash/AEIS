# 32. Evidence Pack — D3 Light + D5 Full templates
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Cross-cutting documentation — pełne specyfikacje obu szablonów Evidence Pack
> używanych przez AEIS Advisor + przykłady wypełnione + lifecycle + walidacja
> + storage. Wersja: 1.0 (2026-04-26).

---

## Spis treści

1. [Czym jest Evidence Pack](#1-czym-jest-evidence-pack)
2. [Kiedy jest wymagany](#2-kiedy-jest-wymagany)
3. [D3 Light — pełen schema](#3-d3-light--pełen-schema)
4. [D3 Light — przykład wypełniony](#4-d3-light--przykład-wypełniony)
5. [D5 Full — pełen schema](#5-d5-full--pełen-schema)
6. [D5 Full — przykład wypełniony](#6-d5-full--przykład-wypełniony)
7. [Required fields per D-level](#7-required-fields-per-d-level)
8. [Storage — gdzie składowane](#8-storage--gdzie-składowane)
9. [Lifecycle (create → review → seal → archive)](#9-lifecycle-create--review--seal--archive)
10. [Verification — jak audytor sprawdza](#10-verification--jak-audytor-sprawdza)
11. [Templates jako YAML/JSON do skopiowania](#11-templates-jako-yamljson-do-skopiowania)
12. [Per-domain extensions](#12-per-domain-extensions)
13. [LLM-judge generation flow](#13-llm-judge-generation-flow)
14. [Cross-references](#14-cross-references)

---

## 1. Czym jest Evidence Pack

Evidence Pack to **strukturalny artefakt audytowy** towarzyszący każdej decyzji
D3 lub wyższej. Składa się z:

- **rationale** — dlaczego ta decyzja (>200 słów dla LIGHT, >500 dla FULL)
- **rollback_plan** — jak ją cofnąć (>100 słów LIGHT, >300 FULL)
- **fidelity_test** — jak zweryfikować że działa (>50 słów LIGHT, >100 FULL)
- (FULL only) **risk_analysis**, **compliance_check**, **council_vote**, **sentinel_signoffs**
- **signatures** — podpisy uczestników (operator + Council member + Sentinel)
- **confidence_breakdown** — komponenty pewności wyliczone przez engine
- **llm_judge_audit_ids** — referencje do wszystkich wywołań LLM, które stworzyły draft

Każda decyzja D3+ MUSI mieć Evidence Pack przed wykonaniem.

### Dwa szablony

- **D3 Light** — minimalna struktura dla decyzji znaczących, ale odwracalnych.
- **D5 Full** — pełna struktura dla decyzji krytycznych, częściowo nieodwracalnych
  lub regulacyjnych.

D4 używa szablonu D5 Full (z luźniejszymi limitami liczby słów).

---

## 2. Kiedy jest wymagany

| Trigger | Wymagany szablon |
|---|---|
| `d_level == D5` | **D5 Full** (mandatory, blokuje emisję) |
| `d_level == D4` | **D5 Full** |
| Cost recommendation (`PURCHASE_PLAN`, `MOVE_TO_CHEAPER_MODEL`, `BLOCK_PRODUCTION_DEPLOY`) na D3 | **D3 Light** (per G8) |
| Subscription rec na ≥D3 | **D3 Light** |
| Funding `FORM_COMPANY` / `CHANGE_LEGAL_FORM` / `REGIONAL_RELOCATION` (D3+) | **D3 Light** |
| Production deploy override | **D5 Full** |
| `REC_TYPE_AUTONOMY_POLICY` D3 | **D3 Light** |
| `REC_TYPE_VPS_SCALING` D3 | **D3 Light** |
| `REC_TYPE_FINAL_APPROVAL` D3 | **D3 Light** |
| Inne karty D0..D2 | **NONE** |

### Implementacja gate

```python
# src/sylion-pipeline/sylion/aeis/advisor/engine/d_ladder/evidence_gate.py

def determine_evidence_pack_requirement(*, d_level, recommendation_type="", suggestion_type=None):
    if d_level == "D5": return EvidencePackRequirement.FULL
    if d_level == "D4": return EvidencePackRequirement.FULL
    if d_level == "D3":
        if recommendation_type in COST_OR_SUBSCRIPTION_TYPES:
            return EvidencePackRequirement.LIGHT
        if suggestion_type in FUNDING_D3_TYPES:
            return EvidencePackRequirement.LIGHT
        if recommendation_type in {"REC_TYPE_AUTONOMY_POLICY", "REC_TYPE_VPS_SCALING", "REC_TYPE_FINAL_APPROVAL"}:
            return EvidencePackRequirement.LIGHT
    return EvidencePackRequirement.NONE
```

### Bramka emisji karty

```
Engine determines d_level → assigns evidence pack requirement
↓
If LIGHT or FULL:
  Engine creates pack in 'draft' status (empty content)
  Engine fires LLM-judge calls (rationale, rollback, fidelity, [risk, compliance])
  LLM-judge populates draft
  Operator UI shows draft for review
  Operator signs → pack moves 'finalized' (if signatures complete)
  (D5 only) Council vote + Sentinel signoffs required
↓
Pack 'finalized' → Card emission proceeds (operator can act)
↓
Pack NOT finalized → Card stays in 'awaiting_evidence' state, operator cannot accept
```

---

## 3. D3 Light — pełen schema

```yaml
# Storage: advisor_evidence.evidence_packs (pack_template = 'd3_light')

evidence_pack_id:        UUID                    # generowany
card_id:                 UUID                    # back-reference do karty
d_level:                 'D3' | 'D4'             # actual level (D4 może też używać light dla cost-only)
pack_template:           'd3_light'
decision_class:          string                  # np. 'subscription_purchase', 'cost_threshold_change',
                                                 # 'funding_form_company', 'autonomy_policy_change'
domain:                  string                  # project_domain (software/research/funding/...)
created_by:              UUID                    # operator_id wywołujący
created_at:              timestamp
finalized_at:            timestamp | null
status:                  'draft' | 'finalized' | 'rejected'

# === Wymagane treści ===
rationale: |
  Multi-paragraph wyjaśnienie DLACZEGO podejmowana jest ta decyzja.
  Musi zawierać:
    - Problem do rozwiązania
    - Rozważone alternatywy
    - Dlaczego wybrana opcja jest preferowana
    - Oczekiwane skutki
  Długość: 200–800 słów.

rollback_plan: |
  Step-by-step plan cofnięcia decyzji JEŻELI skutki nie spełnią oczekiwań.
  Musi zawierać:
    - Konkretne akcje per krok (nie ogólniki)
    - Estymowany czas per krok
    - Odpowiedzialna strona (operator | provider | system)
    - Kryteria detekcji — jak rozpoznajemy że trzeba rollback?
  Długość: 100–400 słów.

fidelity_test: |
  Jak zweryfikujemy, że decyzja osiąga zamierzony cel?
  Musi zawierać:
    - Kwantytatywną metrykę sukcesu (np. "miesięczny koszt redukcja ≥20% w 30 dni")
    - Okno pomiarowe
    - Źródło danych do pomiaru
    - Akceptowalna wariancja
  Długość: 50–200 słów.

# === Confidence breakdown (engine populuje) ===
confidence_breakdown:
  council_match:               float (0.0–1.0)   # zgodność z preferencjami council
  history_match:               float             # zgodność z historią akcji operatora
  pricing_quality:             float             # świeżość/rzetelność danych cenowych
  historical_acceptance_rate:  float             # acceptance rate dla podobnych kart
  used_local_fallback:         bool              # czy LLM-judge upadł do lokalnego
  final_score:                 float             # zagregowany score

# === References ===
historical_acceptance_rate:    float (0.0–1.0)
llm_judge_audit_ids:           [UUID]            # wszystkie LLM calls
related_card_ids:              [UUID]            # podobne karty z przeszłości

# === Signatures (wymagane do finalize) ===
signatures:
  - signer_role:        'operator'
    signer_id:          UUID
    signed_at:          timestamp
    signature_payload:  string (base64)
```

### 3.1 D3 Light — minimum requirements

| Pole | Minimum |
|---|---|
| `rationale` | ≥ 200 słów |
| `rollback_plan` | ≥ 100 słów |
| `fidelity_test` | ≥ 50 słów |
| `signatures[]` | ≥ 1 (operator) |
| `confidence_breakdown` | wszystkie 5 komponentów obecne |
| `llm_judge_audit_ids` | ≥ 1 |
| `decision_class` | non-empty string |

---

## 4. D3 Light — przykład wypełniony

```yaml
evidence_pack_id: "ep-9f1c5b2e-..."
card_id: "card-abc-123"
d_level: "D3"
pack_template: "d3_light"
decision_class: "subscription_purchase"
domain: "software"
created_by: "op-7c9d"
created_at: "2026-04-26T12:34:56Z"
finalized_at: "2026-04-26T13:02:11Z"
status: "finalized"

rationale: |
  Operator's monthly Anthropic API spend has grown to $80 across two active
  software projects. The pay-as-you-go model charges $3 per million input
  tokens for Claude Sonnet 4.6 and ~$1 per million for output. Our usage
  pattern (mostly rationale_generation and alternatives_ranking purposes,
  averaging 12K input / 3K output per request × ~600 requests/month) puts
  us right at the break-even point of the Anthropic Pro plan ($80/month
  flat, includes priority support and 50% rate-limit increase).

  Considered alternatives:
    - Stay on pay-as-you-go: marginal cost stays at ~$80/month with no
      additional benefits.
    - Switch to Claude Haiku for low-risk purposes: would save ~$25/month
      but reduce rationale quality significantly (30% loss in F1 vs Sonnet
      on adversarial bench).
    - Move all rationale_generation to local Qwen 72B: saves money but
      latency triples (avg 6s → 18s) and quality drops.

  The Pro plan is preferred because it converts variable cost to fixed,
  removes rate-limit anxiety during burst usage (30% of weeks have spikes),
  and the priority support has a non-trivial ROI when troubleshooting
  outages. Expected outcome: predictable monthly cost, 14-day break-even
  vs current trajectory, no quality regression.

rollback_plan: |
  Step 1 (operator action, ~2 min): Cancel the Pro plan via Anthropic's
  billing portal at https://console.anthropic.com/settings/billing.
  Cancellation is effective at the end of the current billing cycle —
  no penalty.

  Step 2 (system, automatic): Within 24h of cancellation, AEIS subscription
  module emits `usage_recorded` events flagged as `pay_as_you_go`. Cost
  ceiling preferences automatically revert to pay-go semantics.

  Step 3 (operator monitoring, week 1 post-rollback): Watch for unexpected
  rate-limit hits during burst usage. If hit ≥3 times in a week, consider
  re-subscribing or switching to a higher plan.

  Detection criteria for rollback: monthly cost exceeds $120 for two
  consecutive months without proportional output growth, OR Anthropic
  service quality drops measurably (latency p95 > 10s for two weeks).

fidelity_test: |
  Success metric: Total monthly Anthropic spend ≤ $80 (the plan price)
  for at least 3 consecutive billing cycles, with no degradation in
  request success rate (≥99.5% non-error responses).

  Measurement window: 30-day rolling, aggregated from
  `aeis.advisor.subscription.usage_recorded` events.

  Data source: `advisor_subscription.usage` table (provider=anthropic).

  Acceptable variance: ±5% on monthly cost (allows for prorations and
  price changes).

confidence_breakdown:
  council_match: 0.82                # 4 z 5 ról rady wsparłoby decyzję
  history_match: 0.91                # operator wcześniej akceptował podobne
  pricing_quality: 0.95              # dane cenowe live, fresh <24h
  historical_acceptance_rate: 0.78   # 78% kart purchase_plan w historii zaakceptowanych
  used_local_fallback: false
  final_score: 0.86

historical_acceptance_rate: 0.78
llm_judge_audit_ids:
  - "judge-aud-rationale-001"
  - "judge-aud-rollback-002"
  - "judge-aud-fidelity-003"
related_card_ids:
  - "card-prev-purchase-1"
  - "card-prev-purchase-2"

signatures:
  - signer_role: "operator"
    signer_id: "op-7c9d"
    signed_at: "2026-04-26T13:02:11Z"
    signature_payload: "base64:0fXt9V..."
```

---

## 5. D5 Full — pełen schema

D5 Full rozszerza D3 Light o sekcje obowiązkowe dla decyzji krytycznych.

```yaml
# Wszystkie pola D3 Light (z większymi minimalami) plus:

# === Risk analysis (D5 only) ===
risk_analysis:
  identified_risks:
    - risk_id:        string
      description:    string
      probability:    'low' | 'medium' | 'high'
      impact:         'low' | 'medium' | 'high' | 'critical'
      mitigation:     string
  worst_case_scenario: |
    Description of the worst plausible outcome and its consequences.
    Length: 100–300 słów.

# === Compliance (D5 only) ===
compliance_check:
  regulatory_constraints_reviewed:  bool
  compliance_concerns:              [string]
  legal_review_completed:           bool
  legal_review_notes:               string

# === Council vote record (D5 zawsze wymaga vote) ===
council_vote:
  vote_id:              UUID                   # → external Council module
  council_size:         integer
  votes_in_favor:       integer
  votes_against:        integer
  abstentions:          integer
  consensus_reached:    bool
  dissenting_opinions:  [
    { role: string, opinion: string }
  ]

# === Sentinel signoffs (D5 wymaga obu sentineli) ===
sentinel_signoffs:
  cost_sentinel:
    reviewed:   bool
    approved:   bool
    notes:      string
    signed_by:  UUID
    signed_at:  timestamp
  security_sentinel:
    reviewed:   bool
    approved:   bool
    notes:      string
    signed_by:  UUID
    signed_at:  timestamp

# === Simulations (specifically dla funding D5) ===
simulation_results:
  - scenario_id:         UUID
    label:               string
    delta_score:         float
    cost_to_implement:   Money
    time_to_implement:   duration

# === Multi-signature (D5 — minimum 3 podpisy) ===
signatures:
  - signer_role: 'operator'           # required
    signer_id:   UUID
    signed_at:   timestamp
  - signer_role: 'council_member'     # required (≥1)
    signer_id:   UUID
    signed_at:   timestamp
  - signer_role: 'sentinel'           # required (≥1, cost lub security)
    signer_id:   UUID
    signed_at:   timestamp
```

### 5.1 D5 Full minimum requirements

| Pole | Minimum |
|---|---|
| Wszystko z D3 Light | tak |
| `rationale` | ≥ 500 słów |
| `rollback_plan` | ≥ 300 słów |
| `fidelity_test` | ≥ 100 słów |
| `risk_analysis.identified_risks` | ≥ 1 |
| `risk_analysis.worst_case_scenario` | ≥ 100 słów |
| `compliance_check.regulatory_constraints_reviewed` | `true` |
| `council_vote.consensus_reached` | `true` (lub explicit override z rationale) |
| `sentinel_signoffs.cost_sentinel` | `reviewed=true, approved=true` |
| `sentinel_signoffs.security_sentinel` | `reviewed=true, approved=true` |
| `signatures` | ≥ 3 (operator + ≥1 council_member + ≥1 sentinel) |

---

## 6. D5 Full — przykład wypełniony

```yaml
evidence_pack_id: "ep-deploy-prod-001"
card_id: "card-deploy-prod-001"
d_level: "D5"
pack_template: "d5_full"
decision_class: "production_deploy_override"
domain: "software"
created_by: "op-7c9d"
created_at: "2026-04-26T08:00:00Z"
finalized_at: "2026-04-26T11:45:30Z"
status: "finalized"

rationale: |
  Production deploy of release v3.7.0 was blocked by AEIS engine because
  the SOT validation failed (sot_approved=false) and the security gate
  reported 2 medium-severity findings. We are requesting an override
  because the release contains a CRITICAL hotfix for CVE-2026-0147 (RCE
  in our auth middleware) that is currently being exploited in the wild.
  The two security findings flagged by the gate are:
    1. Outdated dependency cryptography==41.0.7 (fixed version 42.0+ has
       known DoS vulnerability in pyproject deserialization, not exploitable
       in our use case but flagged generically by the scanner).
    2. New dependency pyjwt==2.8.0 (no known CVEs but new addition triggers
       an "unaudited new dependency" rule in our policy).

  Considered alternatives:
    - Wait for proper SOT approval cycle (24–48h): NOT acceptable given
      active exploitation.
    - Patch the vulnerable middleware in place via hotfix without full
      deploy: REJECTED — the fix requires schema migration that cannot
      be applied in-place.
    - Roll back to v3.6.x and apply minimal patch only: would reintroduce
      Issue #4421 (token refresh race condition) that v3.7.0 fixes.
    - Deploy to a single canary instance first: PARTIALLY MITIGATING but
      still requires override because gate blocks any production deploy.

  The decision is to deploy v3.7.0 to production with the override, with
  the following compensating controls:
    a) Heightened monitoring for 72h post-deploy (alert thresholds halved).
    b) On-call engineer available 24/7 for the next 48h.
    c) Pre-staged rollback script tested in staging within last 2h.
    d) Communication to all operators that the override is in effect and
       why.

  Expected outcome: critical RCE patched within 4h, no quality regressions,
  monitoring confirms no exploit attempts succeed against patched
  middleware. Open follow-up: schedule formal compliance review of the
  two flagged security findings within 7 days.

rollback_plan: |
  This is a multi-step rollback plan tested in staging at 2026-04-26T10:00Z.

  Step 1 (immediate, automated, ~3 min): Trigger the pre-staged
  /ops/rollback?to=v3.6.4 endpoint. This switches the load balancer to
  the v3.6.4 production pool which is kept warm. Schema migration from
  v3.7.0 is reverted via backwards-compatible reverse migration.

  Step 2 (within 5 min, automated): Verify rollback success via
  /healthz endpoint on v3.6.4 + smoke test suite. Expected pass: 100%.

  Step 3 (within 15 min, operator action): Notify stakeholders via the
  #incidents Slack channel that rollback occurred and reason. Update the
  Evidence Pack with rollback timestamp and reason.

  Step 4 (within 1h, operator + on-call): Apply the standalone CVE
  patch (already prepared as PR #4567, reviewed but not deployed) directly
  to v3.6.4 via emergency patch procedure. This addresses the RCE without
  the full v3.7.0 changes.

  Step 5 (within 24h, council review): Formal post-mortem with
  Council to determine why the override was insufficient, document
  lessons learned, and update the override procedure.

  Detection criteria for rollback:
    - Any 5xx error rate > 0.5% on critical endpoints for 5 minutes.
    - Any successful auth bypass detected by IDS in first 4 hours.
    - Latency p99 increase > 50% on hot paths for 10 minutes.
    - Any data corruption signal from the integrity-checker job.

  Rollback ownership: SRE on-call (primary), backed up by infra team lead.
  Estimated rollback time end-to-end: 8 minutes from decision to fully
  reverted.

fidelity_test: |
  Success metrics, measured over 72h post-deploy:
    1. CVE-2026-0147 exploitation attempts in IDS log: must show
       attempts blocked at the patched layer (we expect attempts; we
       require zero successes).
    2. Standard SLO metrics maintain or improve:
       - p95 latency < 250ms on /api/auth (was 240ms baseline).
       - 5xx rate < 0.1%.
       - Throughput > 10K req/s peak.
    3. No new error classes introduced in the error-rate dashboard.
    4. Auth refresh success rate > 99.95% (was 99.91%, the v3.7.0 fix).
    5. Post-deploy security scan (run at T+1h) shows no new findings
       beyond the two already documented.

  Measurement window: 72 hours starting from deploy completion timestamp.
  Data source: Prometheus + IDS log aggregation + Sentry. Variance:
  no tolerance for security regressions; ±10% on perf metrics.

confidence_breakdown:
  council_match: 0.71                # mieszane głosy dotyczące override'u
  history_match: 0.55                # rzadkie sytuacje, mała próba historyczna
  pricing_quality: 1.00              # nie dotyczy (no LLM cost path)
  historical_acceptance_rate: 0.45   # tylko 2 z 4 podobnych override'ów zaakceptowane
  used_local_fallback: false
  final_score: 0.68

historical_acceptance_rate: 0.45
llm_judge_audit_ids:
  - "judge-aud-rationale-d5-001"
  - "judge-aud-rollback-d5-002"
  - "judge-aud-fidelity-d5-003"
  - "judge-aud-risk-d5-004"
  - "judge-aud-compliance-d5-005"

risk_analysis:
  identified_risks:
    - risk_id: "R1"
      description: "Schema migration may fail on a subset of replicas"
      probability: "low"
      impact: "high"
      mitigation: "Pre-migration dry-run executed against snapshot of prod data; rollback script tested"
    - risk_id: "R2"
      description: "v3.7.0 contains new logging that may exceed log-storage budget"
      probability: "medium"
      impact: "medium"
      mitigation: "Log rate-limiter active; alert if storage usage > 80%"
    - risk_id: "R3"
      description: "Override may set precedent that erodes gate effectiveness"
      probability: "medium"
      impact: "high"
      mitigation: "Council post-mortem mandated; override audit reviewed quarterly"
  worst_case_scenario: |
    The deploy succeeds but introduces a previously-undetected regression
    in the auth refresh flow that causes 1–5% of users to be unable to
    authenticate for the duration until rollback. Combined with the
    elevated traffic from public CVE disclosure, this could amplify into a
    multi-hour outage if rollback automation fails. Compensating controls
    (24/7 on-call, automated rollback) keep MTTR < 15 minutes even in
    worst case. Worst-case business impact: ~3% of user-base experiences
    auth issues for 15 minutes — recoverable, but reputationally damaging.

compliance_check:
  regulatory_constraints_reviewed: true
  compliance_concerns: [
    "GDPR: deploy does not change PII handling — verified",
    "AI Act: not applicable (this is auth middleware, not AI)",
    "SOC 2: change management procedure followed via this Evidence Pack"
  ]
  legal_review_completed: true
  legal_review_notes: |
    Legal counsel reviewed the override rationale and confirms that
    expediting the patch is consistent with our duty of reasonable care
    given active exploitation. Legal opinion archived in DMS at
    legal/2026-04-26-cve-override-opinion.pdf.

council_vote:
  vote_id: "vote-cv-001"
  council_size: 9
  votes_in_favor: 6
  votes_against: 2
  abstentions: 1
  consensus_reached: true   # ≥66% in favor
  dissenting_opinions:
    - role: "critic"
      opinion: "Concerned about precedent of using override for security findings rather than treating them as fix-blockers. Recommends 7-day timeline for formal addressing of the two flagged dependencies."
    - role: "governance"
      opinion: "Vote against because v3.7.0 has insufficient soak time in staging (only 18h vs typical 48h)."

sentinel_signoffs:
  cost_sentinel:
    reviewed: true
    approved: true
    notes: "Override has no significant cost impact. Standard deploy + compensating monitoring well within budget."
    signed_by: "sentinel-cost-001"
    signed_at: "2026-04-26T11:30:00Z"
  security_sentinel:
    reviewed: true
    approved: true
    notes: "Override is justified by active exploitation. Two flagged findings reviewed: cryptography 41.0.7 DoS not exploitable in our usage; pyjwt 2.8.0 newly added but pinned and audit scheduled. Monitoring uplifted as documented."
    signed_by: "sentinel-sec-001"
    signed_at: "2026-04-26T11:35:00Z"

simulation_results: []  # not applicable for production deploy override

signatures:
  - signer_role: "operator"
    signer_id: "op-7c9d"
    signed_at: "2026-04-26T11:40:00Z"
    signature_payload: "base64:..."
  - signer_role: "council_member"
    signer_id: "council-finance-007"
    signed_at: "2026-04-26T11:42:00Z"
  - signer_role: "council_member"
    signer_id: "council-architect-003"
    signed_at: "2026-04-26T11:43:00Z"
  - signer_role: "sentinel"
    signer_id: "sentinel-sec-001"
    signed_at: "2026-04-26T11:35:00Z"
  - signer_role: "sentinel"
    signer_id: "sentinel-cost-001"
    signed_at: "2026-04-26T11:30:00Z"
```

---

## 7. Required fields per D-level

### Tabela porównawcza

| Pole | D3 Light (D3) | D4 (Full) | D5 (Full mandatory) |
|---|---|---|---|
| `rationale` ≥ słów | 200 | 350 | 500 |
| `rollback_plan` ≥ słów | 100 | 200 | 300 |
| `fidelity_test` ≥ słów | 50 | 75 | 100 |
| `confidence_breakdown` | required | required | required |
| `llm_judge_audit_ids` | ≥ 1 | ≥ 3 | ≥ 5 |
| `risk_analysis` | optional | required (≥1 risk) | required (≥1 risk) |
| `risk_analysis.worst_case_scenario` ≥ słów | – | 50 | 100 |
| `compliance_check` | optional | required | required |
| `council_vote` | optional | required (consensus) | required (consensus, można override z rationale) |
| `sentinel_signoffs.cost_sentinel` | optional | required | required (reviewed+approved) |
| `sentinel_signoffs.security_sentinel` | optional | required | required (reviewed+approved) |
| `signatures` | ≥1 (operator) | ≥2 (operator + council) | ≥3 (operator + council + sentinel) |
| Retention | 5 lat | 10 lat | forever |

### Pola wspólne (zawsze obecne)

```
evidence_pack_id, card_id, d_level, pack_template, decision_class, domain,
created_by, created_at, status, rationale, rollback_plan, fidelity_test,
confidence_breakdown, llm_judge_audit_ids, signatures
```

---

## 8. Storage — gdzie składowane

### 8.1 Tabela główna

```
schema:  advisor_evidence
table:   evidence_packs

columns:
  evidence_pack_id  UUID PRIMARY KEY
  card_id           UUID NOT NULL REFERENCES advisor_engine.recommendations(card_id)
  d_level           text NOT NULL CHECK (d_level IN ('D3','D4','D5'))
  pack_template     text NOT NULL CHECK (pack_template IN ('d3_light','d5_full'))
  decision_class    text NOT NULL
  domain            text
  created_by        UUID NOT NULL
  created_at        timestamptz NOT NULL DEFAULT now()
  finalized_at      timestamptz NULL
  status            text NOT NULL CHECK (status IN ('draft','finalized','rejected'))
  rationale         text NOT NULL DEFAULT ''
  rollback_plan     text NOT NULL DEFAULT ''
  fidelity_test     text NOT NULL DEFAULT ''
  body_jsonb        jsonb NOT NULL DEFAULT '{}'
  attachments       jsonb NOT NULL DEFAULT '[]'

indexes:
  (card_id), (status), (created_at), (d_level, status), GIN(body_jsonb)
```

### 8.2 Tabela podpisów

```
schema:  advisor_evidence
table:   evidence_pack_signatures

columns:
  signature_id      UUID PRIMARY KEY
  evidence_pack_id  UUID NOT NULL REFERENCES advisor_evidence.evidence_packs(evidence_pack_id)
  signer_role       text NOT NULL CHECK (signer_role IN ('operator','council_member','sentinel'))
  signer_id         UUID NOT NULL
  signed_at         timestamptz NOT NULL
  signature_payload bytea
  metadata          jsonb DEFAULT '{}'

indexes:
  (evidence_pack_id), (signer_role)
```

### 8.3 Załączniki (poza DB)

`attachments` JSONB array zawiera URI do object storage:

```json
[
  {"kind": "pdf", "uri": "s3://sylion-evidence/ep-001/legal-opinion.pdf",
   "size_bytes": 184320, "sha256": "..."},
  {"kind": "log", "uri": "s3://sylion-evidence/ep-001/staging-test-output.log",
   "size_bytes": 49152, "sha256": "..."}
]
```

Pliki są **immutable** w object storage (versioning + object lock).

### 8.4 Ograniczenia wymuszone w DB

```sql
-- D5 musi mieć evidence_pack_id NOT NULL na karcie
ALTER TABLE advisor_engine.recommendations
ADD CONSTRAINT chk_d5_must_have_evidence_pack
CHECK (d_level <> 'D5' OR evidence_pack_id IS NOT NULL);

-- finalized pack must have finalized_at
ALTER TABLE advisor_evidence.evidence_packs
ADD CONSTRAINT chk_finalized_has_timestamp
CHECK (status <> 'finalized' OR finalized_at IS NOT NULL);
```

---

## 9. Lifecycle (create → review → seal → archive)

### 9.1 Stany

```
draft  → finalized       (operator + required signatures completed)
draft  → rejected        (operator chose not to proceed; pack archived but card cancelled)
finalized → archived     (po retention window — D5+ packs forever)
```

### 9.2 Tabela przejść

| Z → Do | Warunki | Skutek |
|---|---|---|
| `draft → finalized` | Wszystkie wymagane podpisy + min content lengths | Karta może być akcjonowana |
| `draft → rejected` | Operator klika "do not proceed" | Karta archived; brak emisji |
| `finalized → archived` | Po 90 dni post-decyzja (D5 nigdy archived) | Cold storage |

### 9.3 Diagram

```
[create]
    │
    └──→ DRAFT (LLM-judge populating)
            │
            ├──→ operator edits / regenerates
            │
            ├──[reject]──→ REJECTED ──[after 30d]──→ purged
            │
            └──[all signatures + min lengths]──→ FINALIZED
                                                    │
                                                    ├──[D3/D4 + 90d]──→ ARCHIVED
                                                    │
                                                    └──[D5]──→ retained forever
```

### 9.4 Eventy lifecycle

| Event | Kiedy emitowane |
|---|---|
| `aeis.advisor.engine.evidence_pack_required` | Engine zdeterminował, że pack jest wymagany |
| `aeis.advisor.engine.evidence_pack_finalized` | Wszystkie warunki spełnione, status=finalized |
| `aeis.advisor.engine.evidence_pack_rejected` | Operator wybrał reject |
| `aeis.advisor.engine.evidence_pack_archived` | Po 90 dni przeszło do archive |

---

## 10. Verification — jak audytor sprawdza

### 10.1 Checklist audytora

Dla każdego packa w stanie `finalized`:

1. **Schema validation** — czy wszystkie wymagane pola obecne? (zob. §7)
2. **Min lengths** — `rationale`, `rollback_plan`, `fidelity_test` mają wystarczającą długość?
3. **Signatures** — required signers obecni? Czy podpisy są kryptograficznie poprawne?
4. **LLM-judge audit chain** — czy `llm_judge_audit_ids` linkują do realnych wpisów audytu?
5. **Confidence breakdown** — czy wszystkie 5 komponentów obecne?
6. **D5-specific** — risk_analysis ≥1, compliance reviewed, council_vote consensus, sentinel approvals.
7. **Card linkage** — `card_id` istnieje i ma `evidence_pack_id` wskazujące z powrotem na ten pack.
8. **Retention** — pack nie został przedwcześnie archived.

### 10.2 Kwerenda walidacji w SQL

```sql
-- Find finalized packs that fail D5 minimum requirements
SELECT
  ep.evidence_pack_id,
  ep.d_level,
  length(ep.rationale) AS rationale_chars,
  length(ep.rollback_plan) AS rollback_chars,
  length(ep.fidelity_test) AS fidelity_chars,
  jsonb_array_length(ep.body_jsonb -> 'risk_analysis' -> 'identified_risks') AS risks_count,
  (ep.body_jsonb -> 'compliance_check' ->> 'regulatory_constraints_reviewed')::bool AS compl_reviewed,
  (ep.body_jsonb -> 'council_vote' ->> 'consensus_reached')::bool AS consensus,
  (SELECT count(*) FROM advisor_evidence.evidence_pack_signatures eps
    WHERE eps.evidence_pack_id = ep.evidence_pack_id) AS sig_count
FROM advisor_evidence.evidence_packs ep
WHERE ep.d_level = 'D5' AND ep.status = 'finalized'
  AND (
    length(ep.rationale) < 2500   -- ~500 słów × 5 znaków
    OR length(ep.rollback_plan) < 1500
    OR length(ep.fidelity_test) < 500
    OR jsonb_array_length(ep.body_jsonb -> 'risk_analysis' -> 'identified_risks') < 1
    OR (ep.body_jsonb -> 'compliance_check' ->> 'regulatory_constraints_reviewed')::bool IS NOT TRUE
    OR (ep.body_jsonb -> 'council_vote' ->> 'consensus_reached')::bool IS NOT TRUE
    OR (SELECT count(*) FROM advisor_evidence.evidence_pack_signatures eps
         WHERE eps.evidence_pack_id = ep.evidence_pack_id) < 3
  );
```

### 10.3 Walidacja w aplikacji

```python
def validate_evidence_pack(pack: EvidencePack) -> list[ValidationError]:
    errors = []

    if word_count(pack.rationale) < pack_template_min['rationale_words']:
        errors.append("rationale too short")
    if word_count(pack.rollback_plan) < pack_template_min['rollback_words']:
        errors.append("rollback_plan too short")
    if word_count(pack.fidelity_test) < pack_template_min['fidelity_words']:
        errors.append("fidelity_test too short")

    if not pack.confidence_breakdown.is_complete():
        errors.append("confidence_breakdown incomplete")

    required_signers = REQUIRED_SIGNERS_BY_TEMPLATE[pack.pack_template]
    actual_signers = {sig.signer_role for sig in pack.signatures}
    missing = required_signers - actual_signers
    if missing:
        errors.append(f"missing signatures: {missing}")

    if pack.pack_template == 'd5_full':
        if not pack.risk_analysis or len(pack.risk_analysis.identified_risks) == 0:
            errors.append("D5 requires risk_analysis with ≥1 identified risk")
        if not pack.compliance_check.regulatory_constraints_reviewed:
            errors.append("D5 requires regulatory_constraints_reviewed=true")
        if not pack.council_vote.consensus_reached:
            errors.append("D5 requires Council consensus or explicit override")
        for s in [pack.sentinel_signoffs.cost, pack.sentinel_signoffs.security]:
            if not (s.reviewed and s.approved):
                errors.append(f"D5 requires {s.role} sentinel approval")

    return errors
```

---

## 11. Templates jako YAML/JSON do skopiowania

### 11.1 D3 Light starter (YAML)

```yaml
evidence_pack_id: ""
card_id: ""
d_level: "D3"
pack_template: "d3_light"
decision_class: ""
domain: ""
created_by: ""
created_at: ""
status: "draft"

rationale: ""               # >=200 słów
rollback_plan: ""           # >=100 słów
fidelity_test: ""           # >=50 słów

confidence_breakdown:
  council_match: 0.0
  history_match: 0.0
  pricing_quality: 0.0
  historical_acceptance_rate: 0.0
  used_local_fallback: false
  final_score: 0.0

historical_acceptance_rate: 0.0
llm_judge_audit_ids: []
related_card_ids: []

signatures: []
```

### 11.2 D5 Full starter (YAML)

```yaml
evidence_pack_id: ""
card_id: ""
d_level: "D5"
pack_template: "d5_full"
decision_class: ""
domain: ""
created_by: ""
created_at: ""
status: "draft"

rationale: ""               # >=500 słów
rollback_plan: ""           # >=300 słów
fidelity_test: ""           # >=100 słów

confidence_breakdown:
  council_match: 0.0
  history_match: 0.0
  pricing_quality: 0.0
  historical_acceptance_rate: 0.0
  used_local_fallback: false
  final_score: 0.0

historical_acceptance_rate: 0.0
llm_judge_audit_ids: []
related_card_ids: []

risk_analysis:
  identified_risks: []
  worst_case_scenario: ""

compliance_check:
  regulatory_constraints_reviewed: false
  compliance_concerns: []
  legal_review_completed: false
  legal_review_notes: ""

council_vote:
  vote_id: ""
  council_size: 0
  votes_in_favor: 0
  votes_against: 0
  abstentions: 0
  consensus_reached: false
  dissenting_opinions: []

sentinel_signoffs:
  cost_sentinel:
    reviewed: false
    approved: false
    notes: ""
    signed_by: ""
    signed_at: ""
  security_sentinel:
    reviewed: false
    approved: false
    notes: ""
    signed_by: ""
    signed_at: ""

simulation_results: []
signatures: []
```

### 11.3 D3 Light starter (JSON)

```json
{
  "evidence_pack_id": "",
  "card_id": "",
  "d_level": "D3",
  "pack_template": "d3_light",
  "decision_class": "",
  "domain": "",
  "created_by": "",
  "created_at": "",
  "status": "draft",
  "rationale": "",
  "rollback_plan": "",
  "fidelity_test": "",
  "confidence_breakdown": {
    "council_match": 0.0,
    "history_match": 0.0,
    "pricing_quality": 0.0,
    "historical_acceptance_rate": 0.0,
    "used_local_fallback": false,
    "final_score": 0.0
  },
  "historical_acceptance_rate": 0.0,
  "llm_judge_audit_ids": [],
  "related_card_ids": [],
  "signatures": []
}
```

---

## 12. Per-domain extensions

Niektóre domeny wymagają dodatkowych pól (zapisane w `body_jsonb` jako sub-objects):

### 12.1 Funding domain

```yaml
funding_extensions:
  grant_program_id:                UUID
  scoring_profile_id:              UUID
  scoring_profile_version:         integer
  pre_change_score:                float (0.0–100.0)
  predicted_post_change_score:     float
  affected_other_grants: [
    { program_id: UUID, score_delta: float }
  ]
```

### 12.2 Subscription domain

```yaml
subscription_extensions:
  plan_id:                         string
  observed_monthly_cost_usd:       numeric
  predicted_savings_usd:           numeric
  break_even_days:                 integer
  cancellation_penalty_usd:        numeric (jeśli dotyczy)
  alternative_plans_considered: [
    { plan_id: string, monthly_cost: numeric, projected_savings: numeric }
  ]
```

### 12.3 Scaling domain

```yaml
scaling_extensions:
  current_topology:                TopologyOption
  proposed_topology:               TopologyOption
  speed_gain_pct:                  float
  cost_delta_monthly_usd:          numeric
  module_conflict_risk_assessment: string
  staging_recommended:             bool
  staging_phases: [
    { phase: integer, env_count: integer, duration_days: integer, validation_gate: string }
  ]
```

---

## 13. LLM-judge generation flow

Gdy engine determinuje, że Evidence Pack jest wymagany:

```
1. Engine creates pack with status='draft', empty content fields.
2. Engine fires LLM-judge calls (różne `judge_purpose` per sekcja):
     a) rationale_generator      (judge_purpose='evidence_rationale')
     b) rollback_planner         (judge_purpose='evidence_rollback')
     c) fidelity_test_designer   (judge_purpose='evidence_fidelity')
     d) (D5 only) risk_analyzer  (judge_purpose='evidence_risk')
     e) (D5 only) compliance_checker (judge_purpose='evidence_compliance')
3. Każde wywołanie LLM-judge → zapis w advisor_engine.llm_judge_audit
   → ID linkowane przez llm_judge_audit_ids w packu.
4. Pack content wypełniony LLM draftami.
5. Operator UI pokazuje pack do review/edit przed signing.
6. Operator może:
     - Edytować dowolne pole (autosave).
     - "Regenerate with different model" (override role_resolver).
     - Dodać własne notatki ("Add my notes" dopisuje pod LLM content).
     - Zaakceptować as-is.
7. Operator klika sign → pack moves to 'finalized' jeśli signatures complete.
8. (D5 only) Council vote requested → Council module updates pack with vote_id.
9. (D5 only) Sentinels review → updates pack with their signoffs.
10. Wszystkie signatures present → pack 'finalized', card może być akcjonowana.
```

### 13.1 Routing modeli per judge_purpose

(Pełna tabela w `34_llm_pool_routing.md`.)

| judge_purpose | low risk | medium | high | critical |
|---|---|---|---|---|
| `evidence_rationale` | qwen2.5:7b | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 |
| `evidence_rollback` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_fidelity` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_risk` | — | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_compliance` | — | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |

---

## 14. Cross-references

- D-ladder pełna: `31_d_ladder_complete.md`
- Eventy `evidence_pack_required` / `evidence_pack_finalized`: `30_event_taxonomy_full.md`
- Council vote (D5 wymagane): `33_council_hybrid.md`
- Routing modeli LLM-judge: `34_llm_pool_routing.md`
- AdvisorCard schema (`evidence_pack_id` field): `01_modul_aeis_advisor.md`
- Skill: `.claude/skills/evidence-pack-writer/SKILL.md`
- Kod evidence gate: `src/sylion-pipeline/sylion/aeis/advisor/engine/d_ladder/evidence_gate.py`
- DB tables: `advisor_evidence.evidence_packs`, `advisor_evidence.evidence_pack_signatures`
- Architektura: `00_architektura_systemu.md`
- Pełny opis decyzji: `05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md`
