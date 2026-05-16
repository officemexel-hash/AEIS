# 31. Decision Ladder D0–D5 — kompletna specyfikacja
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Cross-cutting documentation — pełna definicja drabiny decyzji, default mapping
> per recommendation_type, reguły upgrade/downgrade, override mechanism, audit
> trail, case studies. Wersja: 1.0 (2026-04-26).

---

## Spis treści

1. [Filozofia D-ladder](#1-filozofia-d-ladder)
2. [Definicje 6 stopni (D0..D5)](#2-definicje-6-stopni-d0d5)
3. [Domyślne D-level per recommendation_type](#3-domyślne-d-level-per-recommendation_type)
4. [Upgrade rules (U1..U5)](#4-upgrade-rules-u1u5)
5. [Downgrade rules (rzadkie)](#5-downgrade-rules-rzadkie)
6. [Algorytm `assign_d_level`](#6-algorytm-assign_d_level)
7. [Wymagania Evidence Pack per D-level](#7-wymagania-evidence-pack-per-d-level)
8. [Override mechanism](#8-override-mechanism)
9. [Audit trail D-level assignment](#9-audit-trail-d-level-assignment)
10. [Case studies (5 real-world)](#10-case-studies-5-real-world)
11. [Korelacja z autonomy_level](#11-korelacja-z-autonomy_level)
12. [Cross-references](#12-cross-references)

---

## 1. Filozofia D-ladder

D-ladder to kanoniczna **6-poziomowa drabina decyzji** (D0..D5) używana w całym
systemie SYLION (AEIS, governance, advisor). Każda decyzja, którą operator
podejmuje lub którą advisor proponuje, jest klasyfikowana pojedynczym poziomem
od D0 do D5 — od trywialnej po krytyczną.

Cel:

- **Audytowalność** — każda decyzja ma jasny "ciężar gatunkowy".
- **Selektywne bramki** — gates (Human Gate, Council, Multi-sig) angażują się tylko
  tam, gdzie naprawdę trzeba.
- **Selektywne Evidence Packs** — wymóg dokumentacji rośnie monotonicznie z
  poziomem decyzji.
- **Spójność** — wszystkie moduły (advisor, kernels, governance) używają tej samej
  drabiny.

### Reguła monotoniczna

Reguły upgrade'u D-level są **tylko rosnące** (z wyjątkami w §5). Jeżeli kilka
reguł się nakłada, wynik to suma podniesień (cumulative), z ograniczeniem do D5.
Nie wolno obniżać D-level poniżej `default_from_type` bez explicit override
operatora z uzasadnieniem.

---

## 2. Definicje 6 stopni (D0..D5)

| D | Nazwa | Audyt | Approval | Evidence Pack | Koszt | Autonomia | Przykłady |
|---|---|---|---|---|---|---|---|
| **D0** | Trivial | Domyślny log | Brak | Brak | 0 | dowolna (auto OK) | Wpisanie komentarza, save draft, hint UI |
| **D1** | Minor | Logged event | Brak | Brak | <$0.01 LLM | dowolna | Zmiana preferencji, ustawienie tagu, dodanie krytyka |
| **D2** | Moderate | Logged event | Opcjonalnie HG | Brak (light context w audicie) | <$1 LLM | suggest+ | Wybór rozmiaru rady, autonomy=suggest, scope adjustment |
| **D3** | Significant | Logged + Human Gate ticket | **Human Gate wymagany** | **Light** (rationale + rollback + fidelity) | <$10 LLM | suggest/auto z HG | Dodanie VPS, autonomy=auto, purchase plan, FORM_COMPANY |
| **D4** | High-impact | Logged + Council vote | **Council vote wymagany** | **Full** | <$100 LLM | po HG zawsze | Multi-VPS, scope-wide autonomy=auto, change_legal_form |
| **D5** | Critical | Logged + multi-sig | **operator + Council + Sentinel** | **Full obowiązkowo** | <$1000 LLM | manual gate | Production deploy, override safety gate, archive project |

### Szczegółowe atrybuty per D-level

#### D0 — Trivial

| Aspekt | Wartość |
|---|---|
| Czas decyzji | natychmiast |
| Wymagana wiedza operatora | minimalna |
| Reverse cost | zerowy |
| Audit retention | 30 dni (default) |
| Notification | brak |
| Confidence threshold | none |
| Skip reason allowed | tak (brak skutku) |

#### D1 — Minor

| Aspekt | Wartość |
|---|---|
| Czas decyzji | <1 min |
| Wymagana wiedza | niska |
| Reverse cost | trywialny (1 click rollback) |
| Audit retention | 90 dni |
| Notification | inline UI |
| Confidence threshold | ≥0.50 dla auto |
| Skip reason allowed | tak |

#### D2 — Moderate

| Aspekt | Wartość |
|---|---|
| Czas decyzji | <5 min |
| Wymagana wiedza | średnia (operator powinien rozumieć skutki) |
| Reverse cost | niski (kilka kliknięć / kilka godzin) |
| Audit retention | 1 rok |
| Notification | inline + opcjonalny push |
| Confidence threshold | ≥0.65 dla auto |
| Skip reason allowed | tak (wymagany komentarz) |

#### D3 — Significant

| Aspekt | Wartość |
|---|---|
| Czas decyzji | <1h |
| Wymagana wiedza | wysoka (operator powinien znać konsekwencje finansowe/operacyjne) |
| Reverse cost | znaczący (godziny/dni) |
| Audit retention | 5 lat |
| Notification | push + email + Slack |
| Confidence threshold | ≥0.75 |
| Evidence Pack | LIGHT |
| Approval | Human Gate ticket |
| Skip reason | nie (musi być explicit decision) |

#### D4 — High-impact

| Aspekt | Wartość |
|---|---|
| Czas decyzji | <24h |
| Wymagana wiedza | bardzo wysoka |
| Reverse cost | wysoki (dni/tygodnie) |
| Audit retention | 10 lat |
| Notification | push + email + Slack + escalation jeśli brak akcji w 24h |
| Confidence threshold | ≥0.80 |
| Evidence Pack | FULL |
| Approval | Council vote (quorum + critic signature + sentinel ok) |

#### D5 — Critical

| Aspekt | Wartość |
|---|---|
| Czas decyzji | jak długo trzeba (multi-sig) |
| Wymagana wiedza | ekspercka |
| Reverse cost | bardzo wysoki / nieodwracalny / regulacyjny |
| Audit retention | zawsze (forever) |
| Notification | wszystkie kanały + cron eskalacja |
| Confidence threshold | ≥0.85 |
| Evidence Pack | FULL obowiązkowo (blokuje emisję karty) |
| Approval | operator + ≥1 council member + ≥1 sentinel |

---

## 3. Domyślne D-level per recommendation_type

Engine przy budowaniu AdvisorCard przypisuje początkowy D-level z poniższego
mappingu, a następnie aplikuje upgrade rules (§4).

### 3.1 Operational types (DecisionCard)

| RecommendationType | Default | Upgrade triggers | Evidence Pack |
|---|---|---|---|
| `REC_TYPE_MODEL_SETUP` | D1 | First-time setup (operator nie ma providerów) → D2 | Brak |
| `REC_TYPE_API_PROVIDER_SETUP` | D1 | Dodanie paid providera → D2 | Brak |
| `REC_TYPE_BUDGET_CONFIG` | D2 | Redukcja poniżej kosztów pending projektów → D3 | Light jeśli ≥D3 |
| `REC_TYPE_IDEA_INTAKE_GUIDANCE` | D0 | Idea sklasyfikowana jako D5 → D2 (sugestia mocniejszej rady) | Brak |
| `REC_TYPE_SOT_MODEL_SELECTION` | D1 | Model przekraczałby cost ceiling → D2 | Brak |
| `REC_TYPE_COUNCIL_FORMATION` | D2 | Override poza preferencje → D3 | Light jeśli ≥D3 |
| `REC_TYPE_AUTONOMY_POLICY` | **D3** | Zawsze D3 (is_hard_change=true na autonomy_level) | **Light** |
| `REC_TYPE_SOT_DRAFTING` | D0 | Brak | Brak |
| `REC_TYPE_MASTERPLAN_GUIDANCE` | D1 | Major restructure (>50% modułów) → D3 | Light jeśli ≥D3 |
| `REC_TYPE_RUNTIME_TOPOLOGY` | D2 | Local→VPS = D3, VPS→Multi-VPS = D4 | Light D3, Full D4+ |
| `REC_TYPE_VPS_SCALING` | **D3** | Multi-VPS / parallel splits → D4 | Light D3, Full D4+ |
| `REC_TYPE_SKILL_SELECTION` | D1 | Usunięcie krytyka/governance ze skilli prod → D3 | Light jeśli ≥D3 |
| `REC_TYPE_PRODUCTION_EXECUTION` | **D3** | Override blocked deploy (sot_approved=false) → **D5** | Full D5 zawsze |
| `REC_TYPE_TESTING_GUIDANCE` | D0 | Skip required test → D2 | Brak |
| `REC_TYPE_HUMAN_GATE_BATCH` | D1 | Brak | Brak |
| `REC_TYPE_FINAL_APPROVAL` | **D3** | Budget overrun → D4; security gate fail → D5 | Light D3, Full D4+ |

### 3.2 Cost-driven types

| RecommendationType | Default | Evidence Pack |
|---|---|---|
| `REC_TYPE_REDUCE_PREMIUM_USAGE` | D2 (D3 jeśli zmienia baseline routing) | Light jeśli D3 |
| `REC_TYPE_MOVE_TO_CHEAPER_MODEL` | D2 (D3 jeśli prod project) | Light jeśli D3 |
| `REC_TYPE_ADD_CRITIC_MODEL` | D1 | Brak |
| `REC_TYPE_SPLIT_LARGE_MODULE` | D2 | Brak |
| `REC_TYPE_BATCH_HUMAN_GATE_TICKETS` | D1 | Brak |
| `REC_TYPE_BLOCK_PRODUCTION_DEPLOY` | **D5** | **Full obowiązkowo** |

### 3.3 Subscription types (zawsze ≥D3 z Evidence Pack — per G8)

| RecommendationType | D-level | Evidence Pack |
|---|---|---|
| `REC_TYPE_PURCHASE_PLAN` | **D3** | **Light auto-attached** |
| `REC_TYPE_DOWNGRADE_PLAN` | D2 (D3 jeśli mid-cycle penalty) | Light jeśli D3 |
| `REC_TYPE_CANCEL_PLAN` | D3 (D4 jeśli aktywne commitments) | Light D3, Full D4 |

### 3.4 Funding types (FundingCard.suggestion_type)

| FundingSuggestionType | D-level | Evidence Pack | Uwagi |
|---|---|---|---|
| `FUNDING_GRANT_FIT` | D0 | Brak | Informacyjne |
| `FUNDING_HOW_TO_QUALIFY` | D1 | Brak | Lista akcji, brak commitment |
| `FUNDING_FORM_COMPANY` | **D3** | **Light auto-attached** | Major commitment |
| `FUNDING_CHANGE_LEGAL_FORM` | **D3** | **Light** | Zmiana formy prawnej |
| `FUNDING_REGIONAL_RELOCATION` | **D3** | **Light** | Relokacja siedziby |
| `FUNDING_FIND_CONSORTIUM` | D2 | Brak | Connection-making |
| `FUNDING_ADJUST_IDEA_FOR_GRANT` | D2 (D3 jeśli zmienia scope) | Light jeśli D3 | |
| `FUNDING_DEADLINE_WARNING` | D1 | Brak | Heads-up only |
| `FUNDING_GAP_CLOSURE_PLAN` | D2 | Brak | Plan, nie commitment |
| `FUNDING_SCOPE_ADJUSTMENT` | D2 (D3 jeśli zmienia Masterplan) | Light jeśli D3 | |

### 3.5 Future card types (placeholders)

| Card type | Default | Uwagi |
|---|---|---|
| `SecurityCard` (v2) | D2 (D5 jeśli critical CVE on prod) | Severity → D-level |
| `ScalingCard` | D2 (D3 dla VPS, D4 dla multi-VPS) | == VPS_SCALING |
| `OnboardingCard` | D0 | Wizard kroki = guidance only |

---

## 4. Upgrade rules (U1..U5)

Engine MUSI ewaluować poniższe reguły **w kolejności** po przypisaniu defaultu.
Każda reguła może niezależnie podnieść D-level. Aplikacja jest kumulatywna z
ograniczeniem D5 (cap, U6).

### Rule U1 — Cost magnitude

```
if cost_impact_usd > $100      → upgrade by 1 level
if cost_impact_usd > $1,000    → upgrade by 2 levels (cumulative, NOT additive)
if cost_impact_usd > $10,000   → upgrade by 3 levels
```

Kod (uproszczony):

```python
cost = context.cost_estimate_usd
if cost > 10_000:
    level = bump(level, +3, rule="U1_cost_magnitude")
elif cost > 1_000:
    level = bump(level, +2, rule="U1_cost_magnitude")
elif cost > 100:
    level = bump(level, +1, rule="U1_cost_magnitude")
```

### Rule U2 — Blast radius

```
if affects_multiple_projects      → upgrade by 1 level
if affects_production             → upgrade by 1 level (cumulative z poprzednim)
```

Implementacja patrzy na `context.affects_multiple_projects` i `context.affects_production`.

### Rule U3 — Reversibility

```
if rollback_takes_days >= 1       → upgrade by 1 level
if rollback_data_loss == True     → set MIN D4 (nie addytywne, ale floor)
```

Druga reguła jest **floor**, nie delta — ustawia `min(D4, current)`.

### Rule U4 — Hard preferences

```
if changing any of:
  autonomy_level, runtime_strategy, approval_timeout_behavior,
  trusted_providers, blocked_providers,
  funding_advisor_enabled, funding_countries,
  meta_recommendations_enabled
→ enforce min D3
```

Kod:

```python
HARD_KEYS = {"autonomy_level","runtime_strategy", ...}
if (changing_keys & HARD_KEYS) and current_idx < D3_idx:
    current_idx = D3_idx
    rules_applied.append({"rule": "U4_hard_preferences", "delta": "min_D3"})
```

### Rule U5 — Operator-set autonomy

```
if autonomy_level == "manual" AND current > D0:
    enforce min D3 (każda nie-trywialna karta wymaga HG)
if autonomy_level == "suggest":
    no change (default mapping applies)
if autonomy_level == "auto":
    operational cards can execute D0..D2 bez HG;
    D3+ STILL requires HG (governance hard rule)
```

### Rule U6 — Cap

```
Maximum upgrade is to D5. Cannot exceed.
Once at D5, Evidence Pack (full) is mandatory and emission must wait for pack.
```

### 4.1 Tabela: warunek → from D_n to D_n+k

| Reguła | Warunek | Delta |
|---|---|---|
| U1.a | $100 < cost ≤ $1k | +1 |
| U1.b | $1k < cost ≤ $10k | +2 |
| U1.c | cost > $10k | +3 |
| U2.a | affects_multiple_projects | +1 |
| U2.b | affects_production | +1 |
| U3.a | rollback ≥ 1 day | +1 |
| U3.b | rollback data_loss=true | floor=D4 |
| U4 | changing hard preference | floor=D3 |
| U5.a | autonomy=manual, current>D0 | floor=D3 |
| U5.b | autonomy=auto, default ≤ D2 | (no change) |
| U6 | cap | min(D5, current) |

### 4.2 Przykład skomulowanej eskalacji

Karta `REC_TYPE_VPS_SCALING` z parametrami:
- `cost_impact_usd = $2400/year` → U1.b → +2
- `affects_production = true` → U2.b → +1
- `rollback_takes_days = 0.5` → U3.a nie aplikuje
- `autonomy_level = manual` → U5.a → floor=D3 (już spełniony)

Default = D3. Po U1.b: D5. Po U2.b: D6 → cap D5. Final = D5, Evidence Pack FULL.

---

## 5. Downgrade rules (rzadkie)

D-ladder jest **monotoniczna w górę**, ale są dwa wyjątki:

### 5.1 Operator override z uzasadnieniem

Operator może obniżyć D-level karty pod warunkiem:
- Wpisania uzasadnienia tekstowego (≥100 znaków).
- Karta nie jest typu finansowego (`PURCHASE_PLAN`, `BLOCK_PRODUCTION_DEPLOY`).
- Operator nie jest w stanie autonomy=manual (manual zabrania downgrade'u).

Skutek:
- Emit `aeis.advisor.engine.d_level_overridden` (audit).
- Override jest zapisany w `body_jsonb.d_level_override` z timestampem i id operatora.
- Następne karty tego samego typu **nie dziedziczą** override'u (pojedynczy przypadek).

### 5.2 Sentinel veto downgrade

Sentinel (cost / security) może w **pojedynczych przypadkach** obniżyć D-level
**z D5 do D4**, jeżeli zidentyfikuje, że klasyfikacja D5 wynikała z błędnej
heurystyki (np. fałszywie podniesione przez U2.b z powodu projektu oznaczonego
production, ale który nie ma faktycznych skutków produkcyjnych — np. test stage
nazwany prod-like).

Wymaga:
- Council vote z poparciem ≥2/3 ról.
- Audit trail z explicit notatką i podpisem sentinela.
- Cap downgrade: max o 1 poziom (z D5 do D4, nigdy poniżej).

### 5.3 Brak innych downgrade'ów

W szczególności:
- Cost downgrade po fakcie (np. okazało się, że karta ma niższy koszt) — NIE.
  Karta z błędnym estymowanym kosztem powinna być **anulowana** i wystawiona na nowo.
- "Operator klika ignore" — NIE wpływa na D-level. Karta jest dismissed, ale jej
  D-level pozostaje w audicie.

---

## 6. Algorytm `assign_d_level`

Pseudokod (faktyczna implementacja: `src/sylion-pipeline/sylion/aeis/advisor/engine/d_ladder/assigner.py`):

```python
def assign_d_level(*, recommendation_type, suggestion_type=None, context):
    # Step 1: Default mapping
    default = _DEFAULT_MAPPING.get(recommendation_type, "D1")
    if suggestion_type:
        default = max_level(default, _FUNDING_DEFAULT_MAPPING.get(suggestion_type, "D0"))

    current_idx = _LEVEL_INDEX[default]
    rules_applied = []

    if context is not None:
        # U1 cost magnitude
        cost = context.cost_estimate_usd
        if cost > 10_000:
            current_idx, rules_applied = bump(current_idx, rules_applied, "U1_cost_magnitude", f"${cost}", 3)
        elif cost > 1_000:
            current_idx, rules_applied = bump(current_idx, rules_applied, "U1_cost_magnitude", f"${cost}", 2)
        elif cost > 100:
            current_idx, rules_applied = bump(current_idx, rules_applied, "U1_cost_magnitude", f"${cost}", 1)

        # U2 blast radius
        if context.affects_multiple_projects:
            current_idx, rules_applied = bump(current_idx, rules_applied, "U2_blast_radius", "multi_project", 1)
        if context.affects_production:
            current_idx, rules_applied = bump(current_idx, rules_applied, "U2_blast_radius", "production", 1)

        # U3 reversibility
        if context.rollback_takes_days >= 1.0:
            current_idx, rules_applied = bump(current_idx, rules_applied, "U3_reversibility", "rollback>=1d", 1)
        if context.rollback_data_loss:
            if current_idx < _LEVEL_INDEX["D4"]:
                rules_applied.append({"rule": "U3_reversibility", "input": "data_loss_risk", "delta": f"min_D4"})
                current_idx = _LEVEL_INDEX["D4"]

        # U4 hard preferences
        prefs = context.preferences or {}
        changing_keys = set(prefs.get("__changing_keys__") or [])
        if changing_keys & _HARD_CHANGE_PREFERENCE_KEYS:
            if current_idx < _LEVEL_INDEX["D3"]:
                rules_applied.append({"rule": "U4_hard_preferences", "delta": "min_D3"})
                current_idx = _LEVEL_INDEX["D3"]

        # U5 autonomy
        autonomy = context.autonomy_level or prefs.get("autonomy_level") or "suggest"
        if autonomy == "manual" and current_idx > _LEVEL_INDEX["D0"]:
            if current_idx < _LEVEL_INDEX["D3"]:
                rules_applied.append({"rule": "U5_autonomy", "delta": "min_D3 for non-D0 cards"})
                current_idx = _LEVEL_INDEX["D3"]

    # U6 cap
    capped = False
    if current_idx > _LEVEL_INDEX["D5"]:
        current_idx = _LEVEL_INDEX["D5"]
        capped = True

    return DLevelAssignment(
        final_level=_LEVEL_BY_INDEX[current_idx],
        default_from_type=default,
        rules_applied=rules_applied,
        capped_at_d5=capped,
    )
```

---

## 7. Wymagania Evidence Pack per D-level

Skrót wymagań (pełen opis w `32_evidence_pack_templates.md`):

| D-level | Pack template | Wymagane elementy | Kto podpisuje |
|---|---|---|---|
| D0 | NONE | — | — |
| D1 | NONE | — | — |
| D2 | NONE | — | — |
| D3 | LIGHT | rationale (≥200 słów), rollback (≥100), fidelity (≥50), ≥1 LLM-judge audit, confidence breakdown | operator |
| D4 | FULL | wszystko z LIGHT (z większymi limitami) + risk_analysis + compliance + council_vote + sentinel_signoffs | operator + ≥1 council + ≥1 sentinel |
| D5 | FULL (mandatory) | jak D4 + multi-sig + rationale ≥500 słów, rollback ≥300, fidelity ≥100 | operator + ≥1 council + ≥1 sentinel (cost lub security) |

### 7.1 Funkcja `determine_evidence_pack_requirement`

```python
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

---

## 8. Override mechanism

Operator MOŻE przesterować klasyfikację D-level w **bardzo ograniczonym zakresie**.

### 8.1 Co operator może zrobić

| Akcja | Warunek | Skutek |
|---|---|---|
| Podnieść D-level (np. D2→D3) | zawsze | Karta zostaje sklasyfikowana wyżej; wymóg Evidence Pack zgodnie z nowym poziomem |
| Obniżyć D-level (np. D4→D3) | uzasadnienie ≥100 znaków, nie-finansowy typ, nie autonomy=manual | Karta sklasyfikowana niżej; Evidence Pack adekwatny do nowego poziomu; emit `d_level_overridden` |
| Override autonomy_level | hard_change=true | Wymaga confirmation token; nie zmienia istniejących kart, ale wpływa na nowe |

### 8.2 Czego operator nie może

- Obniżyć D5 do <D4 dla jakichkolwiek kart finansowych (`PURCHASE_PLAN`, `BLOCK_PRODUCTION_DEPLOY`).
- Obniżyć D4/D5 dla `REC_TYPE_PRODUCTION_EXECUTION` (production deploy zawsze ≥D3).
- Pominąć Evidence Pack przy D3+, nawet jeśli D-level został zmieniony.
- Zmienić D-level po podjęciu decyzji (akcja na karcie zamyka klasyfikację).

### 8.3 Rejestracja override

```sql
UPDATE advisor_engine.recommendations
SET body_jsonb = jsonb_set(body_jsonb, '{d_level_override}',
                           jsonb_build_object(
                             'old', body_jsonb->>'d_level',
                             'new', $new_level,
                             'reason', $reason_text,
                             'overridden_by', $operator_id,
                             'overridden_at', now()
                           ))
WHERE card_id = $card_id;
```

---

## 9. Audit trail D-level assignment

Każda karta ma `d_level` + `body_jsonb -> 'd_level_assignment_trace'`:

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

### 9.1 Kwerendy audytora

```sql
-- Histogram D-level w ostatnim miesiącu
SELECT d_level, count(*)
FROM advisor_engine.recommendations
WHERE created_at > now() - interval '30 days'
GROUP BY d_level
ORDER BY d_level;

-- Karty z capped at D5 (czy klasyfikacja zachowuje się jak oczekiwano)
SELECT card_id, recommendation_type,
       body_jsonb -> 'd_level_assignment_trace' AS trace
FROM advisor_engine.recommendations
WHERE (body_jsonb -> 'd_level_assignment_trace' ->> 'capped_at_d5') = 'true';

-- Karty z override
SELECT card_id, body_jsonb -> 'd_level_override'
FROM advisor_engine.recommendations
WHERE body_jsonb ? 'd_level_override';
```

### 9.2 Eventy audit

| Event | Trigger |
|---|---|
| `aeis.advisor.engine.recommendation_emitted` | Karta wystawiona z `d_level` (final) |
| `aeis.advisor.engine.d_level_overridden` | Operator zmienił D-level po fakcie |
| `aeis.advisor.engine.evidence_pack_required` | Karta wymaga packa |
| `aeis.advisor.engine.evidence_pack_finalized` | Pack jest finalised |

---

## 10. Case studies (5 real-world)

### Case 1: Mały refactor w research project

**Kontekst:**
- Operator ma research project, project_domain=software, autonomy=suggest.
- Idea: "Przerefactoruj moduł X" (małe zmiany, <100 linii).

**Klasyfikacja:**

```
recommendation_type = REC_TYPE_IDEA_INTAKE_GUIDANCE
default = D0
context.cost_estimate_usd = 0.05 (LLM-judge tylko)
context.affects_multiple_projects = false
context.affects_production = false
rules_applied = []   # nic nie aplikuje
final = D0
evidence_pack = NONE
```

**Skutek**: Karta D0, operator może ack lub ignorować, brak HG/Council.

---

### Case 2: Subscription Advisor sugeruje Anthropic Pro plan

**Kontekst:**
- Operator: monthly Anthropic spend = $80, autonomy=suggest.
- Engine wykrywa, że plan Pro ($80/mo zamiast $80 pay-go) → break-even po 14 dniach.

**Klasyfikacja:**

```
recommendation_type = REC_TYPE_PURCHASE_PLAN
default = D3 (subscription rule)
context.cost_estimate_usd = $80   # monthly cost of plan
context.affects_multiple_projects = false
context.affects_production = false
rules_applied:
  U1: $80 → no upgrade (under $100)
final = D3
evidence_pack = LIGHT (auto-attached per G8)
```

**Skutek**: Karta D3, Light Evidence Pack auto-tworzony, Human Gate ticket.
Operator widzi rationale, rollback (cancel anytime), fidelity test.

---

### Case 3: Local → Multi-VPS dla produkcji

**Kontekst:**
- Production project, current=local, proposed=multi_vps (3 envs).
- Cena: ~$200/month total.

**Klasyfikacja:**

```
recommendation_type = REC_TYPE_VPS_SCALING
default = D3
context.cost_estimate_usd = 200       # monthly
context.affects_production = true
context.rollback_takes_days = 0.2     # godziny, nie aplikuje U3.a
rules_applied:
  U1: $200 > $100 → +1 → D4
  U2.b: production → +1 → D5
final = D5 (cap)
evidence_pack = FULL (mandatory)
```

**Skutek**: Karta D5, FULL Evidence Pack obowiązkowy, multi-signature
(operator + Council vote + Sentinel signoffs).

---

### Case 4: Funding Advisor sugeruje sp. z o.o. dla FENG

**Kontekst:**
- Operator zarejestrował idea, funding_advisor_enabled=true.
- Engine wykrywa, że grant FENG wymaga osobowości prawnej; operator ma JDG.
- Engine emituje FundingCard z `suggestion_type=FUNDING_FORM_COMPANY`.

**Klasyfikacja:**

```
recommendation_type = (FundingCard, brak Funding-specific RecType)
suggestion_type = FUNDING_FORM_COMPANY
default = D3 (funding mapping)
context.cost_estimate_usd = $1500    # opłaty rejestracyjne + pierwsze miesiące
context.rollback_takes_days = 30     # likwidacja sp. z o.o. trwa tygodnie
rules_applied:
  U1: $1500 > $1000 → +2 → D5
  U3.a: rollback >= 1 day → +1 → cap D5
final = D5
evidence_pack = FULL
```

**Skutek**: Council vote nad strategicznym kierunkiem (sp. z o.o. vs spółka komandytowa
vs pozostać JDG). FULL pack zawiera:
- Rationale (LLM-judge): dlaczego sp. z o.o. specifically.
- Rollback plan: jak rozwiązać spółkę jeśli grant nie wpłynie.
- Fidelity test: jak zweryfikować poprawność rejestracji.
- Simulation: delta_score na 3 grantach.
- Confidence breakdown.

---

### Case 5: Override blocked production deploy

**Kontekst:**
- Production deploy zablokowany przez engine (sot_approved=false, security gate failed).
- Operator chce mimo wszystko wdrożyć (np. krytyczna poprawka).

**Klasyfikacja:**

```
recommendation_type = REC_TYPE_PRODUCTION_EXECUTION
default = D3
context.affects_production = true
context.rollback_data_loss = true     # zła wersja może zniszczyć dane
override_blocked_deploy = true        # explicit triggers D5 path
rules_applied:
  U2.b: production → +1 → D4
  U3.b: data_loss_risk → floor D4 (już spełniony)
  override_blocked_deploy: → enforce D5
final = D5
evidence_pack = FULL (mandatory)
```

**Skutek**: Karta D5. Operator MUSI:
- Stworzyć FULL Evidence Pack z risk_analysis (worst case).
- Uzyskać podpis krytyka + cost sentinel + security sentinel.
- Council vote z quorum.
- Multi-signature przed faktycznym deploy.

---

## 11. Korelacja z autonomy_level

`autonomy_level` (preference operatora) wpływa na zachowanie D-ladder:

| autonomy | Default mapping ≤ D2 | D3+ | Hard preferences |
|---|---|---|---|
| `manual` | floor=D3 (każda karta wymaga HG) | bez zmian | dalej D3+ |
| `suggest` | bez zmian | bez zmian | bez zmian |
| `auto` | wykonuje się bez HG (D0..D2) | wymaga HG (governance hard rule) | dalej D3+ |

**Uwaga**: `autonomy_level` jest sam w sobie hard preference — jego zmiana to zawsze D3.

---

## 12. Cross-references

- Definicje recommendation_types: `01_modul_aeis_advisor.md` (sekcja AdvisorCard)
- Wymagania Evidence Pack: `32_evidence_pack_templates.md`
- Eventy `recommendation_emitted` / `evidence_pack_required`: `30_event_taxonomy_full.md`
- Council voting (D4/D5 path): `33_council_hybrid.md`
- Routing modeli per risk (LLM-judge): `34_llm_pool_routing.md`
- Kod assigner: `src/sylion-pipeline/sylion/aeis/advisor/engine/d_ladder/assigner.py`
- Kod evidence gate: `src/sylion-pipeline/sylion/aeis/advisor/engine/d_ladder/evidence_gate.py`
- Architektura: `00_architektura_systemu.md` §6 (Rada Modeli) + §7 (D-ladder skrót)
- Pełny opis decyzji: `05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md`
- Skill `decision-classifier`: `.claude/skills/decision-classifier/SKILL.md`
