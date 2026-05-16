# 34. LLM Pool Routing — pełna matrix
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Cross-cutting documentation — pełna macierz routingu modeli LLM dla AEIS
> Advisor: per role, judge_purpose, risk_level, project_domain, recommendation_type.
> Fallback chains, cost ceilings, override mechanism, weryfikacja.
> Wersja: 1.0 (2026-04-26).

---

## Spis treści

1. [Filozofia routingu (rola → model)](#1-filozofia-routingu-rola--model)
2. [Catalog dostępnych modeli](#2-catalog-dostępnych-modeli)
3. [Routing matrix — pełna tabela](#3-routing-matrix--pełna-tabela)
4. [Fallback chains (gdy model unavailable)](#4-fallback-chains-gdy-model-unavailable)
5. [Cost ceiling per recommendation](#5-cost-ceiling-per-recommendation)
6. [Override mechanism](#6-override-mechanism)
7. [`role_routing_defaults.yaml` — pełen plik z komentarzami](#7-role_routing_defaultsyaml--pełen-plik-z-komentarzami)
8. [Algorytm `resolve_judge_model` / `resolve_role_model`](#8-algorytm-resolve_judge_model--resolve_role_model)
9. [Przykłady routing decisions (5+)](#9-przykłady-routing-decisions-5)
10. [Weryfikacja — jak sprawdzić routing per request](#10-weryfikacja--jak-sprawdzić-routing-per-request)
11. [Eventy emitowane przez resolver](#11-eventy-emitowane-przez-resolver)
12. [Cross-references](#12-cross-references)

---

## 1. Filozofia routingu (rola → model)

Routing modeli LLM w AEIS Advisor nie jest hardcoded — to **konfigurowalny system
preferencji** z deterministyczną kaskadą fallbacków. Każde wywołanie LLM (czy to
do generowania rationale, oceny risk, budowy alternatyw, czy prostego scoringu)
przechodzi przez `role_resolver`, który decyduje:

> *Który model, u którego providera, w jakim koszcie, z jakim fallbackiem.*

### Cele

- **Cost transparency** — operator widzi koszt każdego call, ma cost ceilings per
  risk_level.
- **Provider neutrality** — operator może blokować providerów (np. OpenAI), system
  automatycznie używa alternatyw.
- **Quality tiering** — niskie ryzyko = tańsze modele (lub lokalne), wysokie ryzyko
  = top-tier modele (Opus, GPT-5).
- **Local-first option** — Qwen lokalnie jako fallback, gdy wszystko inne zablokowane.
- **Operator override** — wymuszenie konkretnego modelu dla pary (rola/risk).

### Kolejność priorytetów

```
1. Operator override (preferences.llm_judge_routing_override)
2. Blocked providers exclusion (preferences.blocked_providers)
3. Cost ceiling enforcement (preferences.cost_ceilings per risk)
4. Default routing matrix (DEFAULT_ROUTING_BY_PURPOSE / DEFAULT_ROUTING_BY_ROLE)
5. Generic fallback (any known model within ceiling)
6. Local fallback (Qwen 7B / 72B)
```

---

## 2. Catalog dostępnych modeli

### 2.1 Modele zewnętrzne (cloud)

| Model ID | Provider | Tier | Latency typ. | Cost/1M in tokens | Cost/1M out tokens | Notes |
|---|---|---|---|---|---|---|
| `claude-opus-4-7` | anthropic | premium | 4–8 s | $15.00 | $75.00 | Top-tier reasoning, najwyższa jakość |
| `claude-sonnet-4-6` | anthropic | balanced | 1–3 s | $3.00 | $15.00 | Workhorse model, default dla większości |
| `gpt-5` | openai | premium | 3–6 s | $10.00 | $30.00 | Cross-validation dla critical decyzji |
| `gemini-2.5-pro` | google | balanced | 1–3 s | $3.50 | $10.50 | Specjalizacja: funding/research domeny |
| `qwen2.5:72b-instruct` | local (Ollama) | balanced | 6–18 s | $0 | $0 | Lokalny, wymaga GPU |
| `qwen2.5:7b-instruct` | local (Ollama) | minimal | 1–4 s | $0 | $0 | Lokalny, lightweight |

### 2.2 Provider mapping

```python
def _provider_of(model_id: str) -> str:
    if model_id.startswith("claude"):  return "anthropic"
    if model_id.startswith("gpt"):     return "openai"
    if model_id.startswith("gemini"):  return "google"
    if model_id.startswith("qwen"):    return "local"
    return "unknown"
```

### 2.3 Tier hierarchy (per `cognitive.council.voting`)

```
"haiku-tier"    →  cheap-fast    →  qwen2.5:7b-instruct, claude-sonnet-4-6 (low risk)
"sonnet-tier"   →  balanced      →  claude-sonnet-4-6, gemini-2.5-pro
"opus-tier"     →  deep-slow     →  claude-opus-4-7, gpt-5
```

Decision-class → tier (per `cognitive.council.voting.DECISION_CLASS_TIERS`):

| D-level | Tier |
|---|---|
| D0, D1 | haiku-tier |
| D2, D3 | sonnet-tier |
| D4, D5 | opus-tier |

---

## 3. Routing matrix — pełna tabela

### 3.1 Default by `judge_purpose` × `risk_level`

(Source: `role_routing_defaults.yaml` + `routing_table.DEFAULT_ROUTING_BY_PURPOSE`.)

| judge_purpose | low | medium | high | critical |
|---|---|---|---|---|
| `rationale_generation` | qwen2.5:7b-instruct | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 |
| `alternatives_ranking` | qwen2.5:72b-instruct | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `risk_assessment` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `funding_scoring` | gemini-2.5-pro | gemini-2.5-pro | [claude-opus-4-7, gemini-2.5-pro] (ensemble) | [claude-opus-4-7, gpt-5] (cross-validate) |
| `consortium_matching` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_rationale` | qwen2.5:7b-instruct | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 |
| `evidence_rollback` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_fidelity` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_risk` (D4+) | – | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `evidence_compliance` (D4+) | – | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |

### 3.2 Default by `role` × `risk_level`

(Source: `routing_table.DEFAULT_ROUTING_BY_ROLE`.)

| role | low | medium | high | critical |
|---|---|---|---|---|
| `planner` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `worker` | qwen2.5:72b-instruct | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 |
| `critic` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `governance` | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 | claude-opus-4-7 |
| `local_verifier` | qwen2.5:7b-instruct | qwen2.5:72b-instruct | qwen2.5:72b-instruct | qwen2.5:72b-instruct |

### 3.3 Routing per `recommendation_type` × `project_domain` × risk

Pełna tabela z mappingiem operacyjnym (recommendation_type wybiera dominujący `judge_purpose`):

| RecommendationType | Dominant judge_purpose | Default risk | Override per project_domain |
|---|---|---|---|
| `REC_TYPE_MODEL_SETUP` | rationale_generation | low | – |
| `REC_TYPE_API_PROVIDER_SETUP` | rationale_generation | low | – |
| `REC_TYPE_BUDGET_CONFIG` | rationale_generation | medium | – |
| `REC_TYPE_IDEA_INTAKE_GUIDANCE` | rationale_generation | low (D5 idea → high) | – |
| `REC_TYPE_SOT_MODEL_SELECTION` | alternatives_ranking | medium | – |
| `REC_TYPE_COUNCIL_FORMATION` | alternatives_ranking | medium | – |
| `REC_TYPE_AUTONOMY_POLICY` | risk_assessment | high (D3 default) | – |
| `REC_TYPE_SOT_DRAFTING` | rationale_generation | low | – |
| `REC_TYPE_MASTERPLAN_GUIDANCE` | alternatives_ranking | medium | – |
| `REC_TYPE_RUNTIME_TOPOLOGY` | risk_assessment | medium | scaling: high jeśli production |
| `REC_TYPE_VPS_SCALING` | risk_assessment | high (D3) → critical (D4+) | – |
| `REC_TYPE_SKILL_SELECTION` | alternatives_ranking | medium | – |
| `REC_TYPE_PRODUCTION_EXECUTION` | risk_assessment | critical (D5) | – |
| `REC_TYPE_TESTING_GUIDANCE` | rationale_generation | low | – |
| `REC_TYPE_HUMAN_GATE_BATCH` | rationale_generation | low | – |
| `REC_TYPE_FINAL_APPROVAL` | risk_assessment | high → critical | – |
| `REC_TYPE_REDUCE_PREMIUM_USAGE` | alternatives_ranking | medium | – |
| `REC_TYPE_MOVE_TO_CHEAPER_MODEL` | alternatives_ranking | medium | – |
| `REC_TYPE_ADD_CRITIC_MODEL` | rationale_generation | low | – |
| `REC_TYPE_SPLIT_LARGE_MODULE` | alternatives_ranking | medium | – |
| `REC_TYPE_BATCH_HUMAN_GATE_TICKETS` | rationale_generation | low | – |
| `REC_TYPE_BLOCK_PRODUCTION_DEPLOY` | risk_assessment | critical | – |
| `REC_TYPE_PURCHASE_PLAN` | alternatives_ranking | high (D3 + cost) | – |
| `REC_TYPE_DOWNGRADE_PLAN` | alternatives_ranking | medium | – |
| `REC_TYPE_CANCEL_PLAN` | risk_assessment | high (D3+) | – |
| **Funding cards** (ogólnie) | funding_scoring | per scoring depth | funding domain → gemini-2.5-pro preferred |
| `FUNDING_GRANT_FIT` | funding_scoring | low | gemini-2.5-pro |
| `FUNDING_HOW_TO_QUALIFY` | funding_scoring | medium | gemini-2.5-pro |
| `FUNDING_FORM_COMPANY` | risk_assessment | high (D3) | claude-opus-4-7 (regulatory complexity) |
| `FUNDING_CHANGE_LEGAL_FORM` | risk_assessment | high (D3) | claude-opus-4-7 |
| `FUNDING_REGIONAL_RELOCATION` | risk_assessment | high (D3) | claude-opus-4-7 |
| `FUNDING_FIND_CONSORTIUM` | consortium_matching | medium | claude-sonnet-4-6 |
| `FUNDING_ADJUST_IDEA_FOR_GRANT` | alternatives_ranking | medium | claude-sonnet-4-6 |
| `FUNDING_DEADLINE_WARNING` | rationale_generation | low | qwen2.5:7b-instruct |
| `FUNDING_GAP_CLOSURE_PLAN` | rationale_generation | medium | claude-sonnet-4-6 |
| `FUNDING_SCOPE_ADJUSTMENT` | alternatives_ranking | medium | claude-sonnet-4-6 |

### 3.4 Pełna macierz rec_type × risk × domain → model (rozwinięcie)

Przykład (rozwinięcie dla `REC_TYPE_PURCHASE_PLAN`):

| project_domain | risk | judge_purpose | Default model | Cost ceiling check |
|---|---|---|---|---|
| software | low | alternatives_ranking | qwen2.5:72b-instruct | tak |
| software | medium | alternatives_ranking | claude-sonnet-4-6 | tak |
| software | high | alternatives_ranking | claude-opus-4-7 | tak |
| software | critical | alternatives_ranking | claude-opus-4-7 | tak |
| funding | low | funding_scoring | gemini-2.5-pro | tak |
| funding | medium | funding_scoring | gemini-2.5-pro | tak |
| funding | high | funding_scoring | [claude-opus-4-7, gemini-2.5-pro] (ensemble) | tak |
| funding | critical | funding_scoring | [claude-opus-4-7, gpt-5] (cross-validate) | tak |
| research | low | rationale_generation | qwen2.5:7b-instruct | tak |
| research | medium | rationale_generation | claude-sonnet-4-6 | tak |
| research | high | rationale_generation | claude-sonnet-4-6 | tak |
| research | critical | rationale_generation | claude-opus-4-7 | tak |

---

## 4. Fallback chains (gdy model unavailable)

### 4.1 Generic fallback order

Gdy domyślny model jest **unavailable** (zablokowany, poza ceiling, nieznany):

```
1. Default model (z DEFAULT_ROUTING_BY_PURPOSE)
2. Generic loop: any known model w katalogu pricing within ceiling
3. Local fallback:
   a) qwen2.5:72b-instruct (jeśli dostępny lokalnie)
   b) qwen2.5:7b-instruct (lightweight backup)
4. RuntimeError "No available model"
```

### 4.2 Fallback per kategoria provider

Jeżeli operator zablokuje danego providera, fallback wygląda tak:

| Blocked | Fallback chain (per risk=high) |
|---|---|
| anthropic | gpt-5 → gemini-2.5-pro → qwen2.5:72b-instruct |
| openai | claude-opus-4-7 → gemini-2.5-pro → qwen2.5:72b-instruct |
| google | claude-opus-4-7 → gpt-5 → qwen2.5:72b-instruct |
| anthropic + openai | gemini-2.5-pro → qwen2.5:72b-instruct |
| anthropic + openai + google | qwen2.5:72b-instruct → qwen2.5:7b-instruct |
| wszystko | qwen2.5:7b-instruct (last-resort lokalny) |

### 4.3 Ensemble fallback

Dla `funding_scoring` z ensemble (np. `[claude-opus-4-7, gemini-2.5-pro]`):

```python
default = ["claude-opus-4-7", "gemini-2.5-pro"]
for cand in default:
    if _is_model_available(cand) and _within_cost_ceiling(cand, risk_level):
        return ModelChoice(model_id=cand, reason="default_ensemble_pick")
# Jeśli żaden członek ensemble nie dostępny, dalej generic fallback
```

W praktyce:
- Pierwszy z listy ma pierwszeństwo, nie odbywa się równoczesna kalkulacja.
- Ensemble **może** być rozszerzony do prawdziwego cross-validation (zob. §9 Case 5).

### 4.4 Fallback timeline

| Krok | Próbowany model | Akcja przy fail |
|---|---|---|
| 1 | Operator override (jeśli ustawiony) | przejdź do kroku 2 |
| 2 | Default by purpose (single) lub default ensemble (lista) | przejdź do kroku 3 |
| 3 | Generic loop po wszystkich katalogowych modelach | przejdź do kroku 4 |
| 4 | qwen2.5:72b-instruct lokalny | przejdź do kroku 5 |
| 5 | qwen2.5:7b-instruct lokalny | przejdź do kroku 6 |
| 6 | RAISE RuntimeError | – |

---

## 5. Cost ceiling per recommendation

### 5.1 Domyślne ceilings (per risk_level)

| risk_level | Default ceiling (USD per single call) |
|---|---|
| low | $25 |
| medium | $25 |
| high | $150 |
| critical | $200 |

(Zob. README role_resolver: "Domyślnie: low=$25, medium=$25, high=$150, critical=$200".)

### 5.2 Estymowanie kosztu

```python
def _within_cost_ceiling(model_id: str, risk_level: str, operator_id: str) -> bool:
    ceilings = get_preferences().get_effective(
        user_id=operator_id, preference_key="cost_ceilings"
    ).value or {}
    ceiling = float(ceilings.get(risk_level, 6.0))
    # Estimate cost for typical 2k input + 1k output call
    est = estimate_cost(model_id, 2000, 1000)
    return float(est.total_cost_usd) <= ceiling
```

Estymacja jest oparta na **typowej** długości promptu (2K input / 1K output).
Faktyczny koszt może być inny — engine zapisuje real cost po wywołaniu w
`aeis.advisor.engine.llm_judge_call_completed`.

### 5.3 Cost ceiling override per recommendation_type

Operator może ustawić ceilings per typ:

```yaml
preferences:
  cost_ceilings:
    low: 25
    medium: 25
    high: 150
    critical: 200
  cost_ceilings_per_recommendation_type:
    REC_TYPE_PURCHASE_PLAN: 5         # tylko cheap models dla subscription rec
    REC_TYPE_PRODUCTION_EXECUTION: 1000   # bardzo wysokie dla production override
```

### 5.4 Cost-driven downgrade

Gdy cost ceiling blokuje top-tier model dla risk=high (np. operator ustawił high=$1
bo budżet bardzo ograniczony):

```
default high → claude-opus-4-7 ($est 0.21)
ceiling = $1
0.21 < 1 → OK, używamy Opus

ceiling = $0.10
0.21 > 0.10 → NOK, downgrade do następnego: claude-sonnet-4-6 ($est 0.055)
0.055 < 0.10 → OK
```

### 5.5 Cost ceiling hit event

Gdy ceiling hit:

```
emit aeis.advisor.engine.cost_ceiling_hit {
  risk_level: "high",
  ceiling_usd: 0.10,
  attempted_cost_usd: 0.21,
  model_id: "claude-opus-4-7",
  fallback_picked: "claude-sonnet-4-6"
}
```

---

## 6. Override mechanism

### 6.1 Per-operator override

Operator ustawia w preferences (`llm_judge_routing_override`):

```json
{
  "rationale_generation:high": "claude-opus-4-7",
  "alternatives_ranking": "gpt-5",
  "funding_scoring:critical": "gemini-2.5-pro"
}
```

Klucze:
- Pełny: `<judge_purpose>:<risk_level>` — wymusza model dla tej specyficznej pary.
- Skrócony: `<judge_purpose>` — wymusza dla **wszystkich** poziomów ryzyka tego purpose.

### 6.2 Algorytm override resolution

```python
def _get_operator_override(operator_id, judge_purpose, risk_level):
    override_raw = get_preferences().get_effective(
        user_id=operator_id, preference_key="llm_judge_routing_override"
    ).value or {}
    return (
        override_raw.get(f"{judge_purpose}:{risk_level}")
        or override_raw.get(judge_purpose)
    )
```

### 6.3 Per-project_type override (advanced)

Operator może też ustawić scoped override per `project_type`:

```yaml
preferences_scoped:
  user_id: op-7c9d
  project_type: research
  preference_key: llm_judge_routing_override
  value:
    rationale_generation: gemini-2.5-pro     # research projects → Gemini
    funding_scoring: gemini-2.5-pro
```

Resolver użyje override scoped przed sprawdzeniem global.

### 6.4 Override constraints

Override jest stosowany TYLKO jeśli:

- Wskazany model **istnieje** w `pricing.catalog`.
- Provider modelu **nie jest** na liście `blocked_providers`.
- Cost estimate nie przekracza ceiling dla risk_level (chyba że operator explicit wyłączył ceiling check tym samym hard preference).

Jeśli warunki nie są spełnione, override jest **ignorowany** i używany jest default routing — z log `aeis.advisor.role_resolver.routing_decision` z reason="override_invalid_falling_back".

### 6.5 Override audit

Każde użycie override emituje event:

```
aeis.advisor.role_resolver.override_applied {
  operator_id: "op-7c9d",
  override_key: "rationale_generation:high",
  resolved_model: "claude-opus-4-7"
}
```

---

## 7. `role_routing_defaults.yaml` — pełen plik z komentarzami

Faktyczna zawartość pliku w `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/role_routing_defaults.yaml`:

```yaml
# Default role routing configuration.
# Operator-editable defaults. Loaded by routing_table.py as reference.
# For runtime resolution, use routing_table.DEFAULT_ROUTING_BY_ROLE and
# routing_table.DEFAULT_ROUTING_BY_PURPOSE.

# === ROLES (high-level abstract roles) ===
# Used by resolve_role_model(operator_id, role, risk_level).
roles:
  planner:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  worker:
    low: qwen2.5:72b-instruct        # local for low risk worker tasks
    medium: claude-sonnet-4-6
    high: claude-sonnet-4-6
    critical: claude-opus-4-7
  critic:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  governance:
    low: claude-sonnet-4-6
    medium: claude-opus-4-7          # governance is more conservative — Opus from medium
    high: claude-opus-4-7
    critical: claude-opus-4-7
  local_verifier:
    low: qwen2.5:7b-instruct         # always local
    medium: qwen2.5:72b-instruct
    high: qwen2.5:72b-instruct
    critical: qwen2.5:72b-instruct

# === PURPOSES (specific judge call purposes) ===
# Used by resolve_judge_model(operator_id, judge_purpose, risk_level).
# Lists indicate ensemble — first available is picked.
purposes:
  rationale_generation:
    low: qwen2.5:7b-instruct          # cheap rationale for low risk
    medium: claude-sonnet-4-6
    high: claude-sonnet-4-6
    critical: claude-opus-4-7

  alternatives_ranking:
    low: qwen2.5:72b-instruct
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7

  risk_assessment:
    low: claude-sonnet-4-6            # always external for risk
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7

  funding_scoring:
    low: gemini-2.5-pro               # Gemini optimized for grant scoring
    medium: gemini-2.5-pro
    high:                             # ensemble for high-risk funding decisions
      - claude-opus-4-7
      - gemini-2.5-pro
    critical:                         # cross-validate via 2 different providers
      - claude-opus-4-7
      - gpt-5

  consortium_matching:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
```

### 7.1 Komentarze projektowe (dlaczego takie defaults)

- `rationale_generation.low = qwen2.5:7b-instruct` — generowanie krótkiego rationale
  dla D0/D1 kart nie wymaga najwyższej jakości. Lokalny Qwen 7B jest wystarczający
  i zerowe koszty.
- `governance.medium = claude-opus-4-7` — governance jest świadomie dobierany
  konserwatywnie. Już od medium używa Opus, bo zła decyzja governance ma wysoki
  blast radius (np. autonomy override).
- `funding_scoring` używa Gemini 2.5 Pro jako default — Gemini ma silne wyniki na
  benchmarkach research/grant matching.
- `funding_scoring.high = ensemble` — wysokie ryzyko (np. recommend FORM_COMPANY)
  używa zarówno Opus (rozumienie regulacji) i Gemini (matching kryteriów grantu).
  System bierze pierwszy dostępny.
- `funding_scoring.critical = cross-validate` — najwyższe ryzyko: faktyczna
  cross-walidacja Opus vs GPT-5 (różne providery dla redukcji bias).
- `local_verifier` zawsze lokalny — dlatego, że to ostatni etap walidacji (pre-emit),
  ma być szybki i nie blokować na cloud latency.

---

## 8. Algorytm `resolve_judge_model` / `resolve_role_model`

### 8.1 `resolve_judge_model`

```python
def resolve_judge_model(operator_id, judge_purpose, risk_level):
    """Resolve judge model for given purpose and risk level."""
    # 1. Check operator override
    override = _get_operator_override(operator_id, judge_purpose, risk_level)
    if override and _is_model_available(operator_id, override):
        return ModelChoice(model_id=override, reason="operator_override")

    # 2. Default routing (DEFAULT_ROUTING_BY_PURPOSE)
    default = DEFAULT_ROUTING_BY_PURPOSE.get(judge_purpose, {}).get(risk_level)
    if isinstance(default, list):
        # Ensemble — pick first available
        for cand in default:
            if _is_model_available(operator_id, cand):
                # 3. Cost ceiling check
                if _within_cost_ceiling(cand, risk_level, operator_id):
                    return ModelChoice(model_id=cand, reason="default_ensemble_pick")
    elif default and _is_model_available(operator_id, default):
        if _within_cost_ceiling(default, risk_level, operator_id):
            return ModelChoice(model_id=default, reason="default_routing")

    # 4. Generic fallback (any known model within ceiling)
    for m in catalog.list_models():
        mid = m.model_id
        if _is_model_available(operator_id, mid) and _within_cost_ceiling(mid, risk_level, operator_id):
            return ModelChoice(model_id=mid, reason="generic_fallback")

    # 5. Local fallback
    local = _find_local_fallback(operator_id)
    if local:
        return ModelChoice(model_id=local, reason="local_fallback", is_local_fallback=True)

    raise RuntimeError(f"No available model for {judge_purpose}/{risk_level}")
```

### 8.2 `resolve_role_model`

```python
def resolve_role_model(operator_id, role, risk_level):
    default = DEFAULT_ROUTING_BY_ROLE.get(role, {}).get(risk_level)
    if isinstance(default, list):
        for cand in default:
            if _is_model_available(operator_id, cand):
                if _within_cost_ceiling(cand, risk_level, operator_id):
                    return ModelChoice(model_id=cand, reason="default_role_ensemble")
    elif default and _is_model_available(operator_id, default):
        if _within_cost_ceiling(default, risk_level, operator_id):
            return ModelChoice(model_id=default, reason="default_role_routing")

    # Local fallback
    local = _find_local_fallback(operator_id)
    if local:
        return ModelChoice(model_id=local, reason="local_fallback", is_local_fallback=True)

    raise RuntimeError(f"No available model for role {role}/{risk_level}")
```

### 8.3 Helpers

```python
def _is_model_available(operator_id, model_id):
    blocked = get_preferences().get_blocked_providers(user_id=operator_id) or []
    provider = _provider_of(model_id)
    if provider in blocked:
        return False
    return catalog.get_model(model_id) is not None

def _find_local_fallback(operator_id):
    local_models = ["qwen2.5:72b-instruct", "qwen2.5:7b-instruct"]
    for m in local_models:
        if _is_model_available(operator_id, m):
            return m
    return None
```

---

## 9. Przykłady routing decisions (5+)

### Case 1 — Default routing, software project, medium risk

**Setup:**
- operator_id = op-7c9d, project_domain = software, autonomy = suggest.
- Karta `REC_TYPE_BUDGET_CONFIG` → judge_purpose = `rationale_generation`, risk_level = `medium`.
- Brak override; brak blocked providers; ceilings default.

**Algorithm trace:**
```
1. operator_override(rationale_generation:medium) = None
2. default = DEFAULT_ROUTING_BY_PURPOSE["rationale_generation"]["medium"] = "claude-sonnet-4-6"
3. _is_model_available("claude-sonnet-4-6") → True
4. _within_cost_ceiling("claude-sonnet-4-6", "medium") → True ($0.055 ≤ $25)
→ ModelChoice(model_id="claude-sonnet-4-6", reason="default_routing")
```

Event:

```json
{
  "event_type": "aeis.advisor.role_resolver.routing_decision",
  "payload": {
    "operator_id": "op-7c9d",
    "judge_purpose": "rationale_generation",
    "risk_level": "medium",
    "resolved_model": "claude-sonnet-4-6",
    "reason": "default_routing",
    "estimated_cost_usd": 0.055
  }
}
```

---

### Case 2 — Operator override, blocked Anthropic

**Setup:**
- operator_id = op-7c9d, blocked_providers = ["anthropic"].
- Override: `{"rationale_generation": "claude-opus-4-7"}` (operator chciał wymusić Opus, ale zablokował Anthropic).
- Risk = high.

**Algorithm trace:**
```
1. operator_override("rationale_generation:high") = "claude-opus-4-7"
2. _is_model_available("claude-opus-4-7") → False (anthropic blocked)
3. Default = "claude-sonnet-4-6" (też anthropic) → False
4. Generic fallback: iter catalog.list_models()
   - "gpt-5" → openai not blocked → available → ceiling $25, est $0.06 → OK
→ ModelChoice(model_id="gpt-5", reason="generic_fallback")
```

Eventy:

```json
{"event_type":"aeis.advisor.role_resolver.routing_decision","payload":{
  "resolved_model":"gpt-5","reason":"generic_fallback",
  "rejected_candidates":[
    {"model_id":"claude-opus-4-7","reason":"blocked_provider"},
    {"model_id":"claude-sonnet-4-6","reason":"blocked_provider"}
  ]
}}
```

---

### Case 3 — Wszystkie zewnętrzne zablokowane, lokalny fallback

**Setup:**
- operator paranoidalnie: blocked_providers = ["anthropic", "openai", "google"].
- Risk = high.
- judge_purpose = alternatives_ranking.

**Algorithm trace:**
```
1. override = None
2. default = "claude-opus-4-7" → blocked
3. Generic fallback: iter catalog
   - claude-* → blocked
   - gpt-* → blocked
   - gemini-* → blocked
   - qwen-* → unknown provider="local"; available
   - "qwen2.5:72b-instruct" → ceiling ($150) NA, but free ($0)
   → ModelChoice(model_id="qwen2.5:72b-instruct", reason="generic_fallback") — but local
   actually fallback path catches this earlier:

Note: Implementation precyzyjnie: local nie jest "blocked" (provider="local"),
ale generic_fallback iterates pricing.catalog. Jeśli Qwen jest w katalogu,
zostaje wybrany w generic_fallback. Jeśli nie ma w katalogu, fallback path 5
wybiera local explicitly:

5. local = _find_local_fallback() → "qwen2.5:72b-instruct"
→ ModelChoice(model_id="qwen2.5:72b-instruct", reason="local_fallback",
              is_local_fallback=True)
```

Event:

```json
{"event_type":"aeis.advisor.role_resolver.fallback_to_local","payload":{
  "operator_id":"op-7c9d","judge_purpose":"alternatives_ranking",
  "risk_level":"high","resolved_model":"qwen2.5:72b-instruct",
  "reason":"all_external_blocked"
}}
```

---

### Case 4 — Funding ensemble, high risk, software domain (forced into funding by FundingCard)

**Setup:**
- operator includes funding_advisor_enabled.
- Karta FundingCard z `suggestion_type=FUNDING_FORM_COMPANY` → D3 (default funding) → risk=high.
- judge_purpose = `funding_scoring` (per mapping).

**Algorithm trace:**
```
1. override = None
2. default = DEFAULT_ROUTING_BY_PURPOSE["funding_scoring"]["high"]
         = ["claude-opus-4-7", "gemini-2.5-pro"]   ← lista (ensemble)
3. iter ensemble:
   - "claude-opus-4-7" → available → ceiling check ($0.21 ≤ $150) → OK
→ ModelChoice(model_id="claude-opus-4-7", reason="default_ensemble_pick")
```

Gdyby Opus był zablokowany, ensemble wybrałoby "gemini-2.5-pro".

---

### Case 5 — Critical funding decision, cross-validate ensemble

**Setup:**
- Karta `FUNDING_FORM_COMPANY` z risk_assessment-judge purpose, ale operator
  poprosił o critical (eskalacja).
- judge_purpose = `funding_scoring`, risk_level = `critical`.

**Algorithm trace:**
```
1. override = None
2. default = DEFAULT_ROUTING_BY_PURPOSE["funding_scoring"]["critical"]
         = ["claude-opus-4-7", "gpt-5"]   ← lista cross-validate
3. iter ensemble:
   - "claude-opus-4-7" → available → ceiling check ($0.21 ≤ $200) → OK
→ ModelChoice(model_id="claude-opus-4-7", reason="default_ensemble_pick")
```

W praktyce dla critical funding system **może** uruchomić oba modele i porównać:
- Wynik = "use_both_for_cross_validate".
- Engine wywołuje LLM-judge dwa razy (1× Opus, 1× GPT-5).
- Porównuje rationale_hash; jeśli różne → escalation do human.

To jest rozszerzenie podstawowego algorytmu (zob. `advisor.engine.cross_validate_module`,
poza scope tego dokumentu).

---

### Case 6 — Cost ceiling triggers downgrade

**Setup:**
- operator budget-conscious: ustawił `cost_ceilings = {"high": 0.10}` (bardzo niski ceiling).
- judge_purpose = risk_assessment, risk_level = high.

**Algorithm trace:**
```
1. override = None
2. default = "claude-opus-4-7"
3. _is_model_available("claude-opus-4-7") → True
4. _within_cost_ceiling("claude-opus-4-7", "high") → est $0.21 > $0.10 → False
5. Generic fallback:
   - "claude-sonnet-4-6" → available → est $0.055 < $0.10 → OK
→ ModelChoice(model_id="claude-sonnet-4-6", reason="generic_fallback")
```

Event:

```json
{"event_type":"aeis.advisor.engine.cost_ceiling_hit","payload":{
  "risk_level":"high","ceiling_usd":0.10,"attempted_cost_usd":0.21,
  "model_id":"claude-opus-4-7","fallback_picked":"claude-sonnet-4-6"
}}
```

---

### Case 7 — Specific override per project_type (research)

**Setup:**
- operator scoped override:
  ```json
  {"user_id":"op-7c9d","project_type":"research",
   "preference_key":"llm_judge_routing_override",
   "value":{"funding_scoring":"gemini-2.5-pro"}}
  ```
- Karta FundingCard z risk=critical w project_type=research.

**Algorithm trace:**
```
1. operator_override scoped("research")["funding_scoring:critical"] = None
2. operator_override scoped("research")["funding_scoring"] = "gemini-2.5-pro"
3. _is_model_available("gemini-2.5-pro") → True
→ ModelChoice(model_id="gemini-2.5-pro", reason="operator_override")
```

Event:

```json
{"event_type":"aeis.advisor.role_resolver.override_applied","payload":{
  "operator_id":"op-7c9d","override_key":"funding_scoring",
  "scope":"project_type=research","resolved_model":"gemini-2.5-pro"
}}
```

---

## 10. Weryfikacja — jak sprawdzić routing per request

### 10.1 Z poziomu UI

Operator → Audit Trail → filter `aeis.advisor.role_resolver.*`. Każda decyzja ma
operator_id, judge_purpose, risk_level, resolved_model, reason, estimated_cost_usd.

### 10.2 Z poziomu CLI / Python

```python
from sylion.aeis.advisor.role_resolver.resolver import resolve_judge_model

choice = resolve_judge_model(
    operator_id="op-7c9d",
    judge_purpose="rationale_generation",
    risk_level="high",
)
print(choice.model_id, choice.reason, choice.is_local_fallback)
```

### 10.3 Z poziomu DB

```sql
-- Distribution modeli per purpose w ostatnich 7 dniach
SELECT
  payload_jsonb ->> 'judge_purpose' AS purpose,
  payload_jsonb ->> 'resolved_model' AS model,
  count(*) AS calls,
  avg((payload_jsonb ->> 'estimated_cost_usd')::numeric) AS avg_cost,
  sum((payload_jsonb ->> 'estimated_cost_usd')::numeric) AS total_cost
FROM advisor_events.events
WHERE event_type = 'aeis.advisor.role_resolver.routing_decision'
  AND produced_at > now() - interval '7 days'
GROUP BY purpose, model
ORDER BY total_cost DESC;

-- Local fallback rate per operator
SELECT
  payload_jsonb ->> 'operator_id' AS operator,
  count(*) FILTER (WHERE event_type = 'aeis.advisor.role_resolver.fallback_to_local') AS fallback_count,
  count(*) FILTER (WHERE event_type = 'aeis.advisor.role_resolver.routing_decision') AS total_count,
  round(100.0 * count(*) FILTER (WHERE event_type = 'aeis.advisor.role_resolver.fallback_to_local')
        / nullif(count(*) FILTER (WHERE event_type = 'aeis.advisor.role_resolver.routing_decision'),0), 1) AS pct
FROM advisor_events.events
WHERE event_type LIKE 'aeis.advisor.role_resolver.%'
  AND produced_at > now() - interval '30 days'
GROUP BY operator
ORDER BY pct DESC NULLS LAST;
```

### 10.4 Tracing per single card

```sql
SELECT event_type, payload_jsonb
FROM advisor_events.events
WHERE correlation_id = $card_correlation_id
  AND event_type LIKE 'aeis.advisor.role_resolver.%' OR event_type LIKE 'aeis.advisor.engine.llm_judge_%'
ORDER BY sequence_no ASC;
```

---

## 11. Eventy emitowane przez resolver

| Event | Kiedy | Pola |
|---|---|---|
| `aeis.advisor.role_resolver.routing_decision` | Każda normalna decyzja | `operator_id`, `judge_purpose`/`role`, `risk_level`, `resolved_model`, `reason`, `estimated_cost_usd`, `rejected_candidates[]` |
| `aeis.advisor.role_resolver.override_applied` | Override aktywny | `operator_id`, `override_key`, `resolved_model` |
| `aeis.advisor.role_resolver.fallback_to_local` | Wszystkie zewnętrzne wykluczone | `operator_id`, `judge_purpose`/`role`, `resolved_model`, `reason` |
| `aeis.advisor.engine.cost_ceiling_hit` | Default model przekroczył ceiling | `risk_level`, `ceiling_usd`, `attempted_cost_usd`, `model_id`, `fallback_picked` |
| `aeis.advisor.engine.llm_judge_call_started` | Resolver wybrał, engine uruchamia call | `judge_purpose`, `model_id`, `prompt_token_count` |
| `aeis.advisor.engine.llm_judge_call_completed` | LLM call zakończony | `judge_purpose`, `model_id`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms` |
| `aeis.advisor.engine.llm_judge_call_failed` | LLM call failed | `judge_purpose`, `model_id`, `error_kind`, `retry_count` |
| `aeis.advisor.engine.local_fallback_used` | Engine forced local po LLM call fail | `original_model_id`, `fallback_model_id`, `reason` |

---

## 12. Cross-references

- D-ladder (mapping risk_level per D-level): `31_d_ladder_complete.md`
- Evidence Pack (judge_purposes for evidence_*): `32_evidence_pack_templates.md` §13
- Council Hybrid (role models per council role): `33_council_hybrid.md`
- Eventy resolver: `30_event_taxonomy_full.md` §6.4
- Architektura kosztów: `00_architektura_systemu.md` §7 (cost ceilings)
- Pełny opis decyzji: `05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md`
- Plik źródłowy YAML: `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/role_routing_defaults.yaml`
- Routing table (Python constants): `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/routing_table.py`
- Resolver implementation: `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/resolver.py`
- README operatora: `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/README.md`
- Manifest: `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.role_resolver.json`
- Council voting tier selection (decision_class → tier): `src/sylion-pipeline/sylion/cognitive/council/voting.py`
