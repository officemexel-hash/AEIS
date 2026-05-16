# PATCH FAZA 05 — D-ladder D0-D5

> **Source**: AEIS_W1_to_W19_kompletny_opis.md, sekcja W4 — Decision Gates
> **Target**: `05_autonomy_configuration.md`
> **Severity**: HIGH
> **Apply**: Czytaj razem z phase 5 file

---

## Problem

Phase 5 używa D-ladder z **5 klas D1-D5**. Kanoniczna architektura W4 ma **6 klas D0-D5** z **D0 Informational** + **6 reguł eskalacji U1-U6**.

## Replace section

W `05_autonomy_configuration.md`, sekcja "D-level Hard Gates" — zastąp:

### OLD (incorrect, 5 klas)

```
D-level system:
  D1 Trivial — quick decisions, 1 agent
  D2 Light — moderate review, 2 agents
  D3 Standard — Council 4/4
  D4 Critical — Council + Human approval
  D5 Mission-critical — Council + Human + External
```

### NEW (correct, 6 klas + U1-U6)

```
D-ladder — 6 klas decyzji (W4):

| Klasa | Nazwa | Gate | Human | Rollback | Efficiency |
|---|---|---|---|---|---|
| D0 | Informational | auto | nie | — | — |
| D1 | Trivial | 1 agent | nie | — | — |
| D2 | Standard | 2 agents + Review | nie | opcjonalny | opcjonalny |
| D3 | Significant | Full Board Council 4/4 | opcjonalny | WYMAGANY | WYMAGANY |
| D4 | Critical | Council 4/4 + Human | tak + Code Optimizer veto | WYMAGANY + LPW | WYMAGANY + benchmark |
| D5 | Greenfield/Systemic | Council 4/4 + Human + External | tak + zewnętrzny | WYMAGANY + LPW + CFT | WYMAGANY + perf/cost sign-off |

Reguły eskalacji U1-U6 (mandatory algorithm):

U1 cost magnitude:
  > $100 → +1 D-level
  > $1,000 → +2 D-levels
  > $10,000 → +3 D-levels

U2 blast radius:
  multi-project impact → +1
  production environment → +1

U3 reversibility:
  rollback time > 1 day → +1
  data loss possible → minimum D4

U4 hard preferences violation:
  blocked_provider used → minimum D3
  cost_ceiling exceeded → minimum D3

U5 autonomy override:
  autonomy_level=manual → wszystko ≥ D3
  
U6 cap:
  maximum D5 (no D6+)

Algorytm classify_decision():
  base_d_level = compute_from_decision_type()
  for rule in [U1, U2, U3, U4, U5]:
    base_d_level = max(base_d_level, rule.evaluate())
  return min(base_d_level, U6.max)
```

## Examples

### D0 Informational (auto, brak hard gate)

```yaml
- "Selecting cheapest model dla L1 unit test generation"
- "Auto-rotation audit chain dla 90-day retention"
- "Skill version bump (patch release, no breaking change)"
- "Updating provider health metrics"
- "Bielik tokenization dla Polish content"
```

### D1 Trivial (1 agent, no rollback needed)

```yaml
- "Adding standard React component (button, card, modal)"
- "Generating unit test dla simple function"
- "Routine cost calculation"
```

### D2 Standard (2 agents + Review)

```yaml
- "Generating new API endpoint within existing module"
- "Adding new translation strings (PL+EN)"
- "Refactoring within single file"
```

### D3 Significant (Full Board Council 4/4 + WYMAGANY rollback)

```yaml
- "Database schema migration (data preservation)"
- "Adding new external integration (3rd party API)"
- "Customer Y branding skill creation"
```

### D4 Critical (Council + Human approval)

```yaml
- "Customer Y CRM payment integration (Stripe)"
- "KSeF compliance implementation"
- "Production deployment of customer-facing system"
- "Security architecture decisions"
```

### D5 Greenfield/Systemic (Council + Human + External)

```yaml
- "Multi-tenant architecture decision (rejected per memory)"
- "Switching primary LLM provider strategy"
- "Migration to fundamentally different storage system"
- "Greenfield project z >$10k budget"
```

## Customer Y CRM classification — verified

```
Customer Y CRM project initial classification:
  Base D-level: D2 (Standard SaaS project)
  
  U1 cost: project budget $345 → no escalation (under $1k)
  U2 blast radius: production + customer-facing → +1 → D3
  U3 reversibility: payment flows = data integrity critical → minimum D4
  U4 hard preferences: customer-funded → cost ceiling enforcement → confirms D3+
  U5 autonomy: Production preset, not manual → no override
  U6 cap: stays at D4 (not D5 because not greenfield)
  
  FINAL D-level: D4 ✓ (confirmed)
```

## Audit chain entry

```json
{
  "patch_id": "patch_phase_5_d0_d5_v1",
  "applied_to": "05_autonomy_configuration.md",
  "section": "D-level Hard Gates",
  "change": "D1-D5 → D0-D5 + U1-U6 rules",
  "source_layer": "W4 (Decision Gates)",
  "verified_against": "Customer Y CRM (D4)",
  "signature": "ed25519:..."
}
```

## Co dalej

Operator po przeczytaniu tego patcha rozumie:
- D0 istnieje (informational auto)
- U1-U6 algorytm jest deterministyczny (każda decyzja klasyfikowana mechanicznie)
- Customer Y CRM D4 verified per algorytm
- Hard gates dla D3+ są mandatory (nie opcjonalne)
