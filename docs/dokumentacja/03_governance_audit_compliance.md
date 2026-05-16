# Governance, Audit, Compliance

> Perspektywa audytora i officera zgodności. Co jest egzekwowane, gdzie szukać dowodów,
> jak dokumentować decyzje.
> Wersja: 2026-04-26.

## Spis treści

- [1. Decision ladder D0–D5](#1-decision-ladder-d0d5)
- [2. Evidence Pack — kiedy i jaki template](#2-evidence-pack--kiedy-i-jaki-template)
- [3. Audit trails — gdzie szukać](#3-audit-trails--gdzie-szukać)
- [4. Hard preferences wymagające operator click](#4-hard-preferences-wymagające-operator-click)
- [5. Sentinel signoffs](#5-sentinel-signoffs)
- [6. Council voting](#6-council-voting)
- [7. Compliance](#7-compliance)
- [8. Cross-references](#8-cross-references)

---

## 1. Decision ladder D0–D5

### Co

Każda decyzja w AEIS jest klasyfikowana na 6-poziomowej drabinie. Klasyfikacja determinuje
wymogi audytu, zatwierdzenia i Evidence Pack.

### Definicje + przykłady

| D | Nazwa | Audit | Approval | Evidence Pack | Przykłady |
|---|---|---|---|---|---|
| **D0** | Trivial | default log | brak | brak | "Wpisz komentarz", "Save draft idei" |
| **D1** | Minor | logged event | brak | brak | "Zmień soft preference", "Set tag", "Add critic model" |
| **D2** | Moderate | logged event | optional HG | brak (light context) | "Choose Council size", "autonomy = suggest", "Find consortium" |
| **D3** | Significant | logged + HG ticket | **HG required** | **D3 Light** | "Add VPS env", "autonomy = auto", "Purchase plan", "Form sp. z o.o." |
| **D4** | High-impact | logged + Council vote | **Council vote** | **D5 Full** | "autonomy = auto globally", "Multi-VPS", "Cancel active commitment" |
| **D5** | Critical | logged + multi-sig | **operator + Council + Sentinel** | **D5 Full mandatory** | "Production deploy", "Override safety gate", "Archive project" |

### Reguły eskalacji (U1–U6)

Default D-level może być eskalowany (NIGDY downgrade'owany):

#### U1 — Cost magnitude
```
cost > $100   → +1 level
cost > $1000  → +2 levels (cumulative)
cost > $10000 → +3 levels (cumulative)
```

#### U2 — Blast radius
```
multi-project              → +1
production environment     → +1 (cumulative)
```

#### U3 — Reversibility
```
rollback > 1 day           → +1
rollback involves data loss → +2 (set min D4)
```

#### U4 — Hard preferences
```
zmiana preferencji is_hard_change=true → min D3 enforced
```

Hard preferences:
- `autonomy_level`
- `runtime_strategy`
- `approval_timeout_behavior`
- `trusted_providers`, `blocked_providers`
- `funding_*_enabled`
- `meta_recommendations_enabled`

#### U5 — Operator-set autonomy
```
autonomy = manual  → ALL non-D0 cards become D3+ (HG required)
autonomy = suggest → default mapping
autonomy = auto    → D2 może exec without HG; D3+ NADAL wymaga HG (governance hard rule)
```

#### U6 — Cap
```
Maksymalnie D5. Nie można przekroczyć.
Po osiągnięciu D5 → Evidence Pack Full mandatory + emisja czeka na pack.
```

### Audit trail of D-level

Każda karta przechowuje pełną decyzyjną ścieżkę w `body_jsonb.d_level_assignment_trace`:

```json
{
  "default_from_type": "D2",
  "rules_applied": [
    {"rule": "U1_cost_magnitude", "input": "$1500", "delta": "+2"},
    {"rule": "U2_blast_radius", "input": "production", "delta": "+1"}
  ],
  "final": "D5",
  "capped_at_d5": true
}
```

Reconstruct query:
```sql
SELECT card_id, d_level, body_jsonb -> 'd_level_assignment_trace' AS trace
FROM advisor_engine.recommendations
WHERE card_id = '<uuid>';
```

---

## 2. Evidence Pack — kiedy i jaki template

### Decyzja matrix

| Trigger | Template | Status blocking? |
|---|---|---|
| `d_level == D5` | **D5 Full** | TAK — emit blocked until pack exists |
| `d_level == D4` | **D5 Full** | TAK |
| Cost recommendation @ D3 (per G8) | **D3 Light** | TAK |
| Subscription rec @ D ≥ D3 | **D3 Light** | TAK |
| Funding `FORM_COMPANY` / `CHANGE_LEGAL_FORM` / `REGIONAL_RELOCATION` (D3+) | **D3 Light** | TAK |
| Production deploy override | **D5 Full** | TAK |
| Inne | None | — |

### Egzekwowanie

- Engine MUST stworzyć pack BEFORE emisji karty.
- Karta ma `header.evidence_pack_id` referencujący pack.
- Pack musi istnieć w `advisor_evidence.evidence_packs` ze statusem `draft` lub `finalized`.
- Akcje operatora (accept / convert→HG) NIE mogą być wykonane przed `finalized`.

### D3 Light template — required fields

```yaml
evidence_pack_id:        UUID
card_id:                 UUID
d_level:                 D3 | D4
pack_template:           'd3_light'
decision_class:          string  # e.g. 'subscription_purchase', 'funding_form_company'
domain:                  string  # project_domain
created_by:              UUID
created_at:              timestamp
status:                  'draft' | 'finalized' | 'rejected'

rationale:               # ≥200 słów
  Multi-paragraph WHY:
  - Problem being solved
  - Considered alternatives
  - Why this option preferred
  - Expected outcomes

rollback_plan:           # ≥100 słów
  Step-by-step undo:
  - Concrete actions per step
  - Estimated time per step
  - Responsible party
  - Detection criteria — kiedy rollback?

fidelity_test:           # ≥50 słów
  How verify decision works:
  - Quantitative success metric
  - Measurement window
  - Data source
  - Acceptable variance

confidence_breakdown:
  council_match:                0.0–1.0
  history_match:                0.0–1.0
  pricing_quality:              0.0–1.0
  historical_acceptance_rate:   0.0–1.0
  used_local_fallback:          bool
  final_score:                  0.0–1.0

llm_judge_audit_ids:     [UUID]    # all LLM calls
related_card_ids:        [UUID]    # similar past cards

signatures:              # ≥1 (operator)
  - signer_role: 'operator'
    signer_id: UUID
    signed_at: timestamp
    signature_payload: string
```

#### D3 Light minimum

- `rationale` ≥ 200 słów
- `rollback_plan` ≥ 100 słów
- `fidelity_test` ≥ 50 słów
- ≥ 1 podpis (operator)
- `confidence_breakdown` populated by engine
- `llm_judge_audit_ids` ≥ 1

### D5 Full template — extends D3 Light

Wszystko z D3 Light + dodatkowo:

```yaml
risk_analysis:
  identified_risks:
    - risk_id:      string
      description:  string
      probability:  'low' | 'medium' | 'high'
      impact:       'low' | 'medium' | 'high' | 'critical'
      mitigation:   string
  worst_case_scenario:        # narrative
    Multi-paragraph what-if-everything-fails

simulation_results:           # ≥1 simulation run
  - scenario:                 string
    outcome_score:            0.0–1.0
    cost_impact_usd:          numeric
    rollback_feasibility:     'easy' | 'moderate' | 'hard'

# Council vote required
council_session_id:          UUID
council_consensus:           'accept' | 'reject' | 'abstain'
council_critic_signed:       bool
council_sentinel_passes:     [{role, verdict}]

# Multi-signature
signatures:                  # ≥2: operator + Council member
  - signer_role: 'operator'
    ...
  - signer_role: 'council'
    council_role: 'critic' | 'verifier' | 'governance' | ...
    ...
```

### Storage

Tabele:
```
advisor_evidence.evidence_packs       -- master records
advisor_evidence.signatures           -- per-pack signatures
advisor_evidence.simulation_results   -- D5 only
advisor_evidence.risk_analyses        -- D5 only
```

Retention: forever. Indeksowane po `card_id`, `decision_class`, `created_at`.

---

## 3. Audit trails — gdzie szukać

### Per-module audit tables

| Moduł | Audit table | Zawartość |
|---|---|---|
| `preferences` | `advisor_preferences.preferences_audit` | Wszystkie zmiany pref (append-only) |
| `pricing` | `advisor_pricing.pricing_history` | Snapshoty cen per (model, timestamp) |
| `engine` | `advisor_engine.recommendations` | Każda wyemitowana karta z full body |
| `engine` | `advisor_engine.llm_judge_audit` | **Forever-retention**: prompt + response + cost + latency |
| `history` | `advisor_history.events` | Event-sourced log akcji operatora |
| `actions` | `advisor_actions.action_log` | Każde wykonane action (z handler outcome) |
| `evidence` | `advisor_evidence.evidence_packs` | Wszystkie packi |
| `evidence` | `advisor_evidence.signatures` | Wszystkie podpisy |

### Hash-chained audit (Evidence Spine)

Cały system ma globalny audit chain:

`sylion/governance/evidence_spine.py`:
- Każdy event audyt-able dodawany jako block.
- Każdy block hash'uje previous block (blockchain-like).
- `verify_chain()` wykrywa tampering.
- Frontend: `evidence-spine/page.tsx` → wizualizacja + verification button.

### Append-only enforcement

Tabele audit mają DB-level constraints zapobiegające UPDATE/DELETE:

```sql
CREATE OR REPLACE FUNCTION prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Audit table is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update BEFORE UPDATE ON advisor_preferences.preferences_audit
  FOR EACH ROW EXECUTE FUNCTION prevent_modification();
CREATE TRIGGER no_delete BEFORE DELETE ON advisor_preferences.preferences_audit
  FOR EACH ROW EXECUTE FUNCTION prevent_modification();
```

### LLM judge full audit

KAŻDY LLM judge call jest audytowany w `advisor_engine.llm_judge_audit`:

```
audit_id           UUID
card_id            UUID
model_id           string         (e.g. 'claude-sonnet-4-6')
provider_id        string
prompt_full        text           (cały prompt w JSON)
response_full      text           (cała odpowiedź w JSON)
input_tokens       integer
output_tokens      integer
cost_usd           numeric
latency_ms         integer
created_at         timestamp
```

**Retention: forever** (partitioned monthly dla archival cost).

PII redaction: pre-storage filter usuwa typowe PII patterns (emails, telefony, NIP).

### Decision audit (existing)

`sylion/governance/decision_audit.py` — central log zdarzeń decyzyjnych dla całego AEIS,
nie tylko Advisor.

Frontend: `audit/page.tsx`.

### Cascade analysis trail

Przy każdej zmianie decyzji (`decision_snapshot.change_decision()`):
- Strong deps → invalidated (audit)
- Weak deps → warning (audit)
- Pipeline cascade → state machine `handle_decision_change()` → rollback do `planning`

Frontend: `decisions/page.tsx → Cascade Impact tab`.

---

## 4. Hard preferences wymagające operator click

### Lista hard preferences

| Preference | Default | Skutek zmiany |
|---|---|---|
| `autonomy_level` | suggest | Zmienia behavior całego systemu |
| `runtime_strategy` | hybrid | Wpływa na cost + latency |
| `approval_timeout_behavior` | manual_review | Co po timeout HG |
| `trusted_providers` | [anthropic, openai, google] | Routing matrix |
| `blocked_providers` | [] | Hard-block w pricing + engine |
| `funding_advisor_enabled` | OFF | Włącza pełen pion funding |
| `meta_recommendations_enabled` | OFF | Pozwala advisor modyfikować swoją konfigurację |

### Egzekwowanie

Próba zmiany hard preference programowo (np. soft learning):
```
1. Engine wykrywa change request
2. Emituje aeis.advisor.preferences.hard_change_requested
3. Surface_feed pokazuje modal: "To jest hard preference. Confirm?"
4. Operator click → emituje aeis.advisor.preferences.hard_change_confirmed
5. Tylko PO confirm → rzeczywista zmiana w DB
6. Audit entry z timestamp + signature_payload
```

Bez kliknięcia operatora: change NIE jest aplikowany. Audit trail w
`advisor_preferences.preferences_audit` z `outcome='confirmed'` lub `outcome='abandoned'`.

---

## 5. Sentinel signoffs

### Co

Dwa specjalne role w Council Hybrid mają power vetoing decyzji:
- **cost_sentinel** — sprawdza cost impact
- **security_sentinel** — sprawdza security implications

### Kiedy są wymagane

| Scenariusz | Wymagani sentinele |
|---|---|
| D4+ decision | minimum 1 sentinel signoff |
| D5 decision | OBA sentinele (cost + security) |
| Production deploy | OBA |
| External upload/submit | security_sentinel |
| Subscription purchase | cost_sentinel |
| Multi-VPS scaling | OBA |

### API

```python
council.record_sentinel_evaluation(
    session_id=...,
    sentinel_role='cost_sentinel',
    model_id=...,
    verdict='accept' | 'reject' | 'abstain',
    rationale=...,
)
```

### Sentinel block

Reject verdict od sentinela → wpisany do `consensus.sentinel_blocks`. Atomic gated
consolidation:

```python
council.consolidate_with_signatures(
    text=consensus_text,
    require_critic=True,
    require_sentinels_pass=True   # ← egzekwuje sentinel block
)
# raises GatedConsolidationBlocked jeśli sentinel reject
```

Operator widzi reason → musi adresować przed retry.

### Audit

Tabela: `council_sentinel_evaluations` (keyed off `hybrid_council_sessions.session_id`).
Zawiera: timestamp, model_id, verdict, rationale, signature_payload.

---

## 6. Council voting

### 9 ról kanonicznych

```
planner             architect           critic
verifier            governance          cost_sentinel
security_sentinel   domain_specialist   funding_specialist
```

### 5 rang

```
primary  →  senior  →  support  →  review_only  →  validation_only
```

### Weighted vote formula

```
voting_weight = DEFAULT_ROLE_WEIGHTS[role] × RANK_MULTIPLIER[rank]
```

| Role | Default weight |
|---|---|
| critic | 1.0 |
| planner | 1.0 |
| architect | 0.9 |
| verifier | 0.9 |
| governance | 0.8 |
| cost_sentinel | 0.7 |
| security_sentinel | 0.7 |
| domain_specialist | 0.6 |
| funding_specialist | 0.6 |

| Rank | Multiplier |
|---|---|
| primary | 1.0 |
| senior | 0.85 |
| support | 0.5 |
| review_only | 0.3 |
| validation_only | 0.0 (only validation, no vote) |

### Critic gate (mandatory)

Bez przynajmniej 1 podpisu od `role=critic` → consolidation blocked.

`record_critic_signature(session_id, model_id)`:
- Model musi być uczestnikiem sesji w `role='critic'`.
- Inaczej `ValueError: Model is not a critic in this session`.

### Voting policy

- **Zwykła większość ważona** — `total_weight_accept > total_weight_reject`.
- **Brak veta governance** — governance role NIE ma vetoing power.
- **Critic signature gate** — mandatory niezależnie od weighted majority.
- **Sentinel block** — reject od sentinela blocks gated consolidation.

### Flow consolidation

```
1. open_session(decision_id, d_level)
2. add_participant(session_id, model_id, role, rank) × N
3. add_analysis(session_id, model_id, verdict, analysis_text) × N
4. record_critic_signature(session_id, critic_model_id)
5. record_sentinel_evaluation(session_id, sentinel_role, model_id, verdict, rationale) × M
6. compute_weighted_consensus(session_id) → {verdict, weights, total_weight, critic_signed, sentinel_blocks}
7. consolidate_with_signatures(text, require_critic=True, require_sentinels_pass=True)
8. AuditRecord append do evidence_spine
```

### Tabele

```
hybrid_council_sessions               -- master sessions
council_participants                  -- model_id, role, rank per session
council_critic_signatures             -- signed_at + signature_payload
council_sentinel_evaluations          -- per-sentinel verdicts
model_analyses                        -- per-model analysis + verdict
```

### API endpoints (`/api/v1/workspace/council/`)

```
GET    /roles
POST   /sessions
POST   /sessions/{sid}/participants
DELETE /sessions/{sid}/participants/{pid}
POST   /sessions/{sid}/critic/sign
GET    /sessions/{sid}/critic/signatures
POST   /sessions/{sid}/sentinels/evaluate
GET    /sessions/{sid}/sentinels?sentinel_role=cost_sentinel
GET    /sessions/{sid}/consensus
POST   /sessions/{sid}/consolidate-gated
```

---

## 7. Compliance

### RBAC

`SYLION_RBAC_DISABLED=1` → tylko dev/test environment. W produkcji enforced:
- Per-domain access (e.g. funding tylko jeśli moduł enabled + permission).
- Per-route permission check.
- Audit każdego access denied.

Backend: `sylion/security/rbac.py`.

### PII redaction

Pre-storage filter usuwa typowe PII patterns przed long-term storage:
- Emails (`*@*.*`)
- Telefony (E.164 format)
- NIP / REGON / KRS (PL identifiers)
- Numery kart kredytowych (Luhn check)
- IP addresses (configurable: redact lub anonymize)

Stosowany do:
- `advisor_engine.llm_judge_audit.prompt_full` / `response_full`
- `advisor_history.events.payload`
- Każdy outbound payload do Slack/email/webhook

### Append-only enforcement

DB-level triggers (przykład w sekcji 3) blokują UPDATE/DELETE na audit tables.

Verification:
```sql
SELECT triggers FROM information_schema.triggers
WHERE event_object_schema LIKE 'advisor_%'
  AND trigger_name LIKE '%no_update%' OR trigger_name LIKE '%no_delete%';
```

### Compliance engine (D0–D5 rules)

`sylion/governance/compliance_engine.py` — silnik reguł egzekwujący wymogi:
- Evidence Pack (presence + content minimum)
- Council vote (presence + critic signed + sentinels pass)
- Human Gate (presence + acknowledged)
- External review (gdy required)

79 testów.

Per-route check przed wykonaniem action: `compliance_engine.check(decision_id) → (allowed, reasons)`.

### Audit chain integrity

Periodic verification via `evidence_spine.verify_chain()`:
- Każdy block hash'uje previous block
- Tampering wykryte → audit alert + emergency HG ticket
- Frontend: `evidence-spine/page.tsx` → "Verify chain" button

### Data retention policy

| Data type | Retention |
|---|---|
| LLM judge audit | forever (partitioned monthly) |
| Preferences audit | forever |
| Decision audit | forever |
| Evidence Packs | forever |
| Pricing history | forever |
| Validation failures | 90 dni rolling |
| Active session state | session lifetime |

### Privacy notes

- LLM audit logs redact PII before long-term storage (per existing PII policy).
- Mobile cache: encrypted at rest (Android Keystore).
- Provider API keys: never in advisor preferences (separate Vault).

---

## 8. Cross-references

| Temat | Plik |
|---|---|
| Architektura całego systemu | [00_architektura_systemu.md](./00_architektura_systemu.md) |
| Advisor Layer deep-dive | [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) |
| Codzienny workflow | [02_operational_manual.md](./02_operational_manual.md) |
| Onboarding developera | [04_dla_developera.md](./04_dla_developera.md) |
| Decision ladder (źródło) | `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` |
| Evidence Pack templates (źródło) | `docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md` |
| Council Hybrid implementation | `src/sylion-pipeline/sylion/governance/council_hybrid.py` |
| Evidence Spine implementation | `src/sylion-pipeline/sylion/governance/evidence_spine.py` |
| Compliance Engine | `src/sylion-pipeline/sylion/governance/compliance_engine.py` |
