# PATCH FAZY 20-25 — Council Hybrid (9 ról × 5 rang × 4 fazy)

> **Source**: AEIS_W1_to_W19_kompletny_opis.md, sekcja W3 — Council Hybrid
> **Target**: `20_25_council_to_ksiega.md`
> **Severity**: CRITICAL
> **Apply**: Czytaj razem z phase 20-25 file

---

## Problem

Phase 20-25 mają **3 niezgodności** z kanoniczną architekturą W3:

1. **12 ról** zamiast kanonicznych **9**
2. **Brak 5 rang** per rola (flat structure)
3. **5 faz deliberacji** zamiast kanonicznych **4** (i brak mandatory critic signature)

## Replace section "Council composition"

W `20_25_council_to_ksiega.md`, sekcja "Council Composition":

### OLD (incorrect, 12 ról flat)

```
12 Council roles:
  1. Planner
  2. Critic
  3. Security
  4. Legal
  5. Finance
  6. Governance
  7. QA
  8. Red Team
  9. Council Chair
  10. Compliance Specialist
  11. UX Designer
  12. Risk Assessor
```

### NEW (correct, 9 ról kanoniczne + 5 rang)

```
## Council Hybrid — kanoniczna architektura (W3)

### 9 stałych ról

| Rola | Cel | Mandatory? |
|---|---|---|
| Planner | Proponuje rozwiązanie | Tak |
| Critic | Kwestionuje propozycje | Tak (signature D3+) |
| Security | Wykrywa luki bezpieczeństwa | Tak |
| Legal | Compliance, zgodność z prawem | Tak |
| Finance | Koszt, ROI, budget | Tak |
| Governance | Proces, lifecycle, audit | Tak |
| QA | Testowalność, edge cases | Tak |
| Red Team | Adversarial perspective | Tak |
| Council Chair | Moderator, agregator | Tak |

### 5 rang per rola (waga × rola)

| Rang | Waga | Zastosowanie |
|---|---|---|
| `primary` | 1.0 | główna decyzja (core ekspertyza) |
| `support` | 0.7 | wsparcie głosu (secondary expertise) |
| `observer` | 0.4 | obserwuje, zaleca |
| `cost_sentinel` | 0.35 | może zablokować na cost (veto power) |
| `security_sentinel` | 0.35 | może zablokować na security (veto power) |

### Sentinele — special veto power

`cost_sentinel` i `security_sentinel` mają **niski waga głosu** (0.35),
ALE **veto power** — mogą zablokować Council decision **niezależnie**
od weighted vote outcome.

Veto trigger conditions:
  cost_sentinel veto:
    - Total cost > project_budget × 1.2 bez justification
    - Cost trajectory unsustainable
    - Hidden cost detected (vendor pass-through)
  
  security_sentinel veto:
    - CVE w proposed dependency
    - Authentication bypass possibility
    - PII handling violation
    - Compliance violation (GDPR/PCI/etc.)

Veto musi być z explicit reasoning + alternative proposal.

### Invited specialists (NOT permanent roles)

Compliance Specialist, UX Designer, Risk Assessor — to **invited
specialists** dla konkretnych decyzji, nie stałe role Council.

Per project, można invite specialists z rangą:
  - `primary` gdy ekspertyza jest core dla decyzji
  - `support` gdy ekspertyza jest secondary
  - `observer` gdy baseline awareness sufficient

### Customer Y CRM — Council composition

9 stałych ról wszystkie present, plus invited specialists:

  Planner: primary (1.0)
  Critic: primary (1.0)
  Security: primary (1.0)  ← payment + KSeF
  Legal: primary (1.0)  ← GDPR + Polish law
  Finance: primary (1.0)  ← customer-funded
  Governance: support (0.7)
  QA: primary (1.0)
  Red Team: support (0.7)
  Council Chair: observer (0.4)
  cost_sentinel: 0.35 (veto power)
  security_sentinel: 0.35 (veto power)
  
  Invited specialists:
    + Polish Tax Specialist: primary (1.0)  ← KSeF compliance
    + UX Designer: support (0.7)  ← customer-facing
    + Compliance Specialist: observer (0.4)  ← baseline GDPR/PCI

  Total weighted votes available: ~10.7 (z sentinels) lub 10 (without)
```

## Replace "Deliberation phases"

W phases 20-25, znajdź sekcję dla deliberation rounds (faza 22) i zastąp:

### OLD (incorrect, 5 phases mixed)

```
Phase 20: Council convening
Phase 21: Initial verdicts
Phase 22: Deliberation rounds (3-5 rounds)
Phase 23: Consolidation
Phase 24: Council Book generation
Phase 25: Księga finalization
```

### NEW (correct, 4 deliberation phases w W3)

```
Council Hybrid w 4 fazach (W3 — INTERNAL deliberation):

PHASE 1 — Parallel Verdicts (Independent)
  Wszystkie 9 ról + invited specialists głosują NIEZALEŻNIE
  Brak komunikacji między rolami (no anchoring effect)
  Format verdict (9 typów):
    approve / conditional / reject / tie / no_data
    × 4 sub-types
  
  + sentinels emit verdicts (cost_sentinel, security_sentinel)
  
  Output: 9-12 verdicts, raw, unaggregated

PHASE 2 — Discussion Rounds (1-2 typowo)
  Verdicts ujawnione całemu Council
  Role mogą:
    - Argumentować swoje verdyk
    - Zmienić verdyk po słyszeniu innych
    - Challenge inne verdykty (Critic specifically)
  
  Round 1: cross-role argumentation
  Round 2 (if needed): focused on disagreements
  
  Termination conditions:
    - Consensus reached (>66% weighted agreement)
    - Diminishing returns (no opinion changes between rounds)
    - Time budget exceeded (operator can intervene)
    - Maximum 5 rounds (hard cap)

PHASE 3 — Consolidated Vote (Final Weighted)
  Per option, compute:
    weighted_sum = Σ (role_verdict × role_weight)
  
  Highest weighted_sum option = winner (jeśli no veto)
  
  Sentinel veto check:
    if cost_sentinel.verdict == "block":
      check_veto_justification()
      if justified:
        reject winning option, force re-deliberation
        OR escalate to operator (D3+ Evidence)
    
    Same dla security_sentinel

PHASE 4 — Critic Signature (MANDATORY D3+)
  
  This phase is MANDATORY dla wszystkich D3+ decisions.
  
  Critic role MUSI signature final decision z:
    "I sign as Critic. Final decision is sound.
     My remaining concerns: [list of 0-N concerns]
     Mitigations applied: [list]
     Open risks acknowledged: [list]"
  
  Bez Critic signature:
    - Decision INVALIDATED
    - Council MUST re-convene Phase 2 (additional discussion)
    - OR escalate to operator (manual override z reasoning)
  
  Critic refuses signature gdy:
    - Major concerns nieadresowane
    - Decision proceeds despite critic challenges
    - Critic believes risks unacceptable
  
  Audit chain entry: adr_signoff.jsonl
```

## Replace "Termination conditions"

```
6 termination conditions Council deliberation:

1. CONSENSUS REACHED
   Weighted agreement > 66% on winning option
   No sentinel veto pending
   Critic signature obtained

2. SUPERMAJORITY OVERRIDE
   80%+ weighted agreement
   Sentinels concur (no veto)
   Auto-progress to Phase 4

3. DIMINISHING RETURNS DETECTED
   Round N vs Round N-1: no opinion changes
   Stuck in disagreement
   Action: operator intervention OR force consolidation

4. TIME BUDGET EXCEEDED
   Operator-set budget reached
   Council Chair forces consolidation
   May require operator final decision

5. SENTINEL VETO
   cost_sentinel or security_sentinel blocks
   Action: re-deliberate OR escalate

6. CRITIC REFUSES SIGNATURE
   Phase 4 fails
   Action: address Critic concerns + re-deliberate
   OR operator override (D5 Evidence Pack required)
```

## Customer Y CRM — Concrete example (re-done correctly)

```
Q15: "MVP scope vs comprehensive — co priorytet?"

PHASE 1 — Parallel verdicts (10 minut, $2.40):

  Independent verdicts:
    Planner (primary, 1.0): "comprehensive" 
      reasoning: "differentiation matters dla SaaS launch"
    Critic (primary, 1.0): "MVP" 
      challenge: "scope creep risk — Customer X had this issue"
    Security (primary, 1.0): "MVP" 
      reasoning: "less attack surface"
    Legal (primary, 1.0): "MVP" 
      reasoning: "less compliance complexity"
    Finance (primary, 1.0): "MVP" 
      reasoning: "tight budget, $345"
    Governance (support, 0.7): "comprehensive" 
      reasoning: "audit easier z full picture"
    QA (primary, 1.0): "MVP" 
      reasoning: "testability, smaller scope"
    Red Team (support, 0.7): "MVP" 
      reasoning: "smaller threat surface"
    Council Chair (observer, 0.4): "comprehensive" 
      reasoning: "synthesis perspective"
    cost_sentinel (0.35): "MVP" + no veto
    security_sentinel (0.35): "MVP" + no veto
    
  Polish Tax Specialist invited (primary, 1.0): "MVP" 
    reasoning: "KSeF first, extras later"

  Weighted sums:
    MVP: 1.0+1.0+1.0+1.0+1.0+1.0+0.7+0.35+0.35+1.0 = 8.4
    Comprehensive: 1.0+0.7+0.4 = 2.1
    
  MVP leads decisively (Round 1).

PHASE 2 — Discussion (1 round, 15 min, $1.80):

  Planner challenged: "Why MVP if we have 8.5 weeks?"
  Critic responded: "Customer X took 12 weeks z scope creep.
                     Polish customers tend to add features mid-build."
  Polish Tax Specialist supported Critic: "KSeF is unique requirement,
                                            don't dilute focus."
  
  No verdicts changed.
  Diminishing returns detected after Round 1.

PHASE 3 — Consolidated vote:

  MVP: 8.4 (vs comprehensive: 2.1)
  Sentinel check: cost_sentinel concurs, security_sentinel concurs
  No veto.
  
  Winner: MVP

PHASE 4 — Critic Signature (MANDATORY D4):
  
  Critic signature:
    "I sign as Critic. Final decision MVP-first is sound.
     My remaining concerns:
       - Phase 2 contract scope must be explicit
       - Customer expectations mid-build must be managed
     Mitigations applied:
       - Out-of-scope explicit in Goal definition (faza 17)
       - Customer notification template prepared
     Open risks acknowledged:
       - Scope creep attempts likely (Polish customer pattern)"
  
  ✓ Signed (mandatory dla D4)
  
  Audit chain entries:
    council_wedge.jsonl: deliberation transcript
    adr_signoff.jsonl: critic signature
    decision_snapshot.jsonl: point-in-time state
```

## Audit chain — 17 separate chains (z W10)

W oryginalnym manualu wszystko szło do "audit/chain.jsonl" (1247 entries).

W realnym AEIS, **per category osobny chain**:

```
Per Council deliberation:
  council_wedge.jsonl — full deliberation transcript
  adr_signoff.jsonl — critic signature (mandatory D3+)
  decision_snapshot.jsonl — point-in-time state
  evidence_chain.jsonl — Evidence Pack references

Per faza 24 Council Book generation:
  council_wedge.jsonl — book reference
  evidence_chain.jsonl — book artifact

Per faza 25 Księga finalization:
  drift_audit.jsonl — Council vs Księga consistency check
  evidence_chain.jsonl — Księga artifact

Plus general chains:
  workflow_engine.jsonl — Workflow rule fires
  rbac_v2.jsonl — capability checks
  audit_chain_alert.jsonl — monitor heartbeats
```

## Audit chain entries

```json
[
  {
    "patch_id": "patch_phase_20_25_council_v1",
    "applied_to": "20_25_council_to_ksiega.md",
    "changes": [
      "12 roles → 9 canonical roles + invited specialists",
      "Flat structure → 5 ranks (primary/support/observer/2 sentinels)",
      "5 mixed phases → 4 canonical phases (parallel/discussion/consolidated/critic_signature)",
      "Critic signature: optional → MANDATORY D3+",
      "Single audit chain → 17 separate chains"
    ],
    "source_layer": "W3 (Council Hybrid)",
    "verified_against": "Customer Y CRM Q15 deliberation",
    "signature": "ed25519:..."
  }
]
```

## Co operator rozumie po patchu

1. **Council to NIE 12 ról flat** — to 9 stałych + invited specialists
2. **5 rang z różnymi wagami** — głosowanie weighted, sentinele mają veto
3. **4 fazy deliberacji** — parallel → discussion → consolidated → **critic signature**
4. **Critic signature mandatory dla D3+** — bez niej decision invalidated
5. **17 audit chains** — nie jeden chain, każda kategoria osobno
6. **Customer Y CRM Q15** — re-done correctly z weighted votes 8.4 vs 2.1
