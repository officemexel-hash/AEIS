# Moduł: sylion.aeis.advisor.variants
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (gRPC RPCs / REST endpoints)](#4-funkcje-grpc-rpcs--rest-endpoints)
5. [Eventy](#5-eventy)
6. [Database tables](#6-database-tables)
7. [Przykład użycia](#7-przykład-użycia)
8. [Verification](#8-verification)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modułu

Moduł `sylion.aeis.advisor.variants` generuje **3 strategiczne warianty wykonania** każdego projektu AEIS, dając operatorowi wybór między oszczędnością, balansem a maksymalną jakością/szybkością. Trzy warianty to *cost_saving* (lokalne modele, mała rada, brak VPS), *balanced* (lokalne + zewnętrzne API, średnia rada, 1 VPS) oraz *aggressive* (wszystkie zewnętrzne, duża rada, multi-VPS, dedykowany critic). Dla każdego wariantu moduł oblicza estymowany koszt (USD), czas wykonania (h), poziom ryzyka (`low/medium/high`) i prognozę jakości (0.0–1.0). Operator otrzymuje wynik jako kartę porównawczą i wybiera wariant pasujący do swojego budżetu i terminów.

Moduł jest **stateless w warstwie persystencji** (manifest deklaruje brak schematów PG), trzyma jedynie historię wygenerowanych zestawów wariantów per `context_id` w pamięci procesu (`_history: dict[str, VariantSet]`) na potrzeby porównań. Wariant jest deterministyczny pod kątem parametrów (cost/time/risk/quality liczone z `templates.py` + `pricing_estimator`), ale niedeterministyczny w identyfikatorach (`variant_id` to UUID, `generated_at` to timestamp). Wariant *aggressive* w odróżnieniu od dwóch pozostałych może rekomendować topologię `multi_vps`, co pociąga za sobą D3+ decyzję obsługiwaną przez `sylion.aeis.advisor.scaling`.

## 2. Architektura modułu

### Pliki w module

| Plik | Rola |
|---|---|
| `__init__.py` | Eksport publicznego API. |
| `service.py` | `VariantsService` — fasada: `generate_variants`, `compare_variants`. Trzyma in-memory `_history`. Emituje eventy. |
| `generator.py` | Pure-function logika: `generate_variants(context)`, `compare_variants(ids, set)`. Szacowanie cost/time/risk/quality. |
| `templates.py` | Trzy szablony jako stałe: `COST_SAVING_TEMPLATE`, `BALANCED_TEMPLATE`, `AGGRESSIVE_TEMPLATE`. |
| `_models.py` | Dataclassy: `Variant`, `VariantSet`, `VariantParameter`, `ComparisonDimension`, `ComparisonMatrix`. |
| `grpc_server.py` | Stub gRPC servicer. |
| `README.md` | Operator guide po polsku. |

### Dependencies

**Wewnętrzne:**

- `sylion.aeis.advisor.pricing.estimator.estimate_cost(model, input_tokens, output_tokens)` — wycena każdej rundy rady.
- `sylion.core.event_bus` — emisja eventów.

**Zewnętrzne:**

- Standard library: `time`, `uuid`, `logging`, `typing`, `dataclasses`.

### Storage

Brak. Manifest deklaruje `"postgres_schemas": []`. In-memory cache `_history: dict[context_id, VariantSet]` żyje tylko przez czas życia procesu.

### Workers / threads / async loops

Brak. Generowanie wariantów jest synchroniczne, czas O(1) (3 szablony × kilka kalkulacji).

## 3. Konfiguracja

### Environment variables

Brak.

### Wpływ preferencji operatora

| Preferencja | Wpływ |
|---|---|
| `blocked_providers` | Jeśli operator zablokuje wszystkich zewnętrznych providerów, `pricing_estimator` zwróci 0 dla `claude-sonnet-4-6`/`claude-opus-4-7`, więc warianty *balanced* i *aggressive* osiągną koszt 0. (Tu jest known limit MVP — w Etap 2 generator powinien wówczas przełączyć modele na lokalne explicitly). |
| `cost_ceilings` | Wariant przekraczający limit może być oznaczony jako ryzykowny (Etap 2 enhancement). |
| `council_size_override` | (Etap 2) Wymusi jedną liczbę członków rady we wszystkich wariantach. |

### Trzy szablony — pełna specyfikacja

| Parametr | cost_saving | balanced | aggressive |
|---|---|---|---|
| `name` | `cost_saving` | `balanced` | `aggressive` |
| `description` | "Local-first, minimal council, cheaper workers, slower" | "Local + selected external APIs, moderate council, limited VPS" | "Multiple models, parallel envs, VPS scaling, faster + more expensive" |
| `council_size` | **3** | **5** | **7** |
| `use_local_models` | `True` | `True` | `True` |
| `use_external_apis` | `False` | `True` | `True` |
| `vps_envs` | `0` | `1` | `3` |
| `topology` | `local_only` | `local_plus_vps` | `multi_vps` |
| `critic_model` | `None` | `claude-sonnet-4-6` | `claude-opus-4-7` |

### Wzory szacowania (z `generator.py`)

#### Koszt

```python
def _estimate_variant_cost(params: dict[str, Any]) -> float:
    cost = 0.0
    council_size = params.get("council_size", 5)
    vps_envs = params.get("vps_envs", 0)
    use_external = params.get("use_external_apis", False)
    critic = params.get("critic_model")

    calls_per_council_member = 4
    if use_external:
        for _ in range(council_size * calls_per_council_member):
            est = estimate_cost("claude-sonnet-4-6", 1500, 750)
            cost += float(est.total_cost_usd)
    else:
        for _ in range(council_size * calls_per_council_member):
            est = estimate_cost("qwen2.5:72b-instruct", 1500, 750)
            cost += float(est.total_cost_usd)  # zazwyczaj 0

    if critic:
        est = estimate_cost(critic, 2000, 1000)
        cost += float(est.total_cost_usd) * 2  # critic 2x per cycle

    cost += vps_envs * 20.0  # $20/month/env amortized
    return round(cost, 2)
```

#### Czas

```python
def _estimate_variant_time(params: dict[str, Any]) -> float:
    council_size = params.get("council_size", 5)
    vps_envs = params.get("vps_envs", 0)
    use_external = params.get("use_external_apis", False)

    base_time = 0.5
    if not use_external and params.get("use_local_models", True):
        base_time = 1.2  # lokalne wolniejsze
    if use_external:
        base_time = 0.5

    parallel_factor = max(1, vps_envs + 1)
    total_cycles = 3
    return round((base_time * council_size * total_cycles) / parallel_factor, 1)
```

#### Risk level

```python
def _assess_risk(params):
    if not use_external and council_size <= 3:
        return "low"
    if use_external and council_size >= 7 and vps_envs >= 2 and critic:
        return "high"
    if use_external and vps_envs >= 3:
        return "high"
    return "medium"
```

| Wariant | Spodziewany risk |
|---|---|
| cost_saving | `low` (council=3, no external) |
| balanced | `medium` (external + 1 VPS) |
| aggressive | `high` (council=7, vps=3, critic, external) |

#### Quality projection (0.0–1.0)

```python
def _project_quality(params):
    score = 0.5
    score += min(council_size * 0.03, 0.25)  # cap 0.25
    if use_external:
        score += 0.1
    if critic:
        score += 0.1
    score += min(vps_envs * 0.02, 0.05)
    return round(min(score, 1.0), 2)
```

| Wariant | council_size | external | critic | vps | quality |
|---|---|---|---|---|---|
| cost_saving | 3 | nie | nie | 0 | 0.5 + 0.09 = ~0.59 |
| balanced | 5 | tak | tak | 1 | 0.5 + 0.15 + 0.1 + 0.1 + 0.02 = ~0.87 |
| aggressive | 7 | tak | tak | 3 | 0.5 + 0.21 + 0.1 + 0.1 + 0.05 = ~0.96 |

## 4. Funkcje (gRPC RPCs / REST endpoints)

### 4.1 `generate_variants(context: dict | None = None) -> VariantSet`

- **Sygnatura proto:** `rpc GenerateVariants(VariantContext) returns (VariantSet)`.
- **Input:** `context` (dict opcjonalny):
  - `context_id` (str) — używany do indexu w historii. Default: `"default"`.
  - dowolne pola z `parameters` szablonu (np. `council_size`) — override per szablon.
- **Output:** `VariantSet`:
  - `context_id` — passed-in lub `"default"`.
  - `variants: list[Variant]` — zawsze 3 elementy w kolejności [cost_saving, balanced, aggressive].
  - `generated_at` — epoch.
- **Side effects:**
  - Wpisuje do `_history[context_id]`.
  - Emituje `aeis.advisor.variants.generated`.
- **Errors:** brak.

#### Variant struktura

```python
@dataclass
class Variant:
    variant_id: str = ""           # auto UUID4 hex
    name: str = ""                 # cost_saving | balanced | aggressive
    description: str = ""
    parameters: dict[str, Any] = {}  # snapshot szablonu (po override)
    estimated_cost_usd: float = 0.0
    estimated_time_hours: float = 0.0
    risk_level: str = "medium"     # low | medium | high
    quality_projection: float = 0.0  # 0.0–1.0
```

### 4.2 `compare_variants(variant_ids: list[str], context_id: str | None = None) -> dict`

- **Sygnatura proto:** `rpc CompareVariants(CompareRequest) returns (ComparisonMatrix)`.
- **Input:**
  - `variant_ids` (list[str]) — minimum 2 ID z tego samego `context_id`.
  - `context_id` (opt) — jeśli brak, użyje ostatniego z `_history`.
- **Output:** dict:
  ```python
  {
    "variant_ids": [...],
    "dimensions": [
      {
        "dimension": "estimated_cost_usd",
        "values": {"cost_saving": 0.0, "balanced": 12.5, "aggressive": 87.4},
        "winner": "cost_saving",
      },
      # ... estimated_time_hours, risk_level, quality_projection
    ]
  }
  ```
- **Logika winner:**
  - `cost_usd, time_hours` — `min` (mniej = lepiej).
  - `risk_level` — `min({low: 0, medium: 1, high: 2, critical: 3})`.
  - `quality_projection` — `max`.
- **Side effects:** emituje `aeis.advisor.variants.compared`.
- **Errors:**
  - Jeśli mniej niż 2 wybrane warianty — zwraca `{variant_ids, dimensions: []}`.
  - Jeśli `_history` puste — zwraca `{... "error": "no variants"}`.

### 4.3. gRPC Servicer — `VariantsServicer` (sprint3)

Plik: `sylion/aeis/advisor/variants/grpc_server.py`. Cienka warstwa RPC.

| RPC | Opis |
|-----|------|
| `GenerateVariants(GenerateVariantsRequest{parameters: map, context_id})` | Woła `generate_variants(parameters)` (context_id wstrzykiwany do params). Zwraca `VariantSet{context_id, variants[], generated_at}`. |
| `CompareVariants(CompareVariantsRequest{variant_ids[], context_id})` | Woła `compare_variants(variant_ids, context_id)`. Zwraca `ComparisonMatrix{variant_ids[], dimensions[]}`. |

Rejestracja: `register_variants_service(server, service=None) -> bool`.

---

## 5. Eventy

### Emitted

| Topic | Kiedy | Payload |
|---|---|---|
| `aeis.advisor.variants.generated` | Po `generate_variants` | `context_id, variant_count (=3), variant_names: ["cost_saving","balanced","aggressive"]` |
| `aeis.advisor.variants.compared` | Po `compare_variants` | `context_id, variant_ids, dimensions: [str]` |

### Subscribed

Brak. Manifest deklaruje `"events_subscribe": []`.

## 6. Database tables

Brak. Wszystkie dane są ulotne (in-memory `_history` w singleton-service).

## 7. Przykład użycia

### 7.1 Generate + inspect (Python)

```python
from sylion.aeis.advisor.variants.service import get_variants_service

svc = get_variants_service()

vs = svc.generate_variants(context={"context_id": "proj-001"})
for v in vs.variants:
    print(f"{v.name:12} cost=${v.estimated_cost_usd:>8.2f}  "
          f"time={v.estimated_time_hours:>5.1f}h  "
          f"risk={v.risk_level:<6}  "
          f"quality={v.quality_projection}")
```

Spodziewany output (przy znanych modelach w pricing.catalog):

```
cost_saving   cost=$    0.00  time= 10.8h  risk=low     quality=0.59
balanced      cost=$   54.00  time=  3.8h  risk=medium  quality=0.87
aggressive    cost=$  171.00  time=  1.3h  risk=high    quality=0.96
```

### 7.2 Compare variants (find best by dimension)

```python
ids = [v.variant_id for v in vs.variants]
result = svc.compare_variants(ids, context_id="proj-001")

for dim in result["dimensions"]:
    print(f"{dim['dimension']:30} → {dim['winner']}")
```

Output:

```
estimated_cost_usd             → cost_saving
estimated_time_hours           → aggressive
risk_level                     → cost_saving
quality_projection             → aggressive
```

### 7.3 Override parametrów per context

```python
# Wymuś council_size=4 we wszystkich wariantach
vs = svc.generate_variants(context={
    "context_id": "proj-002",
    "council_size": 4,
})
for v in vs.variants:
    assert v.parameters["council_size"] == 4
```

### 7.4 curl REST (Etap 2)

```bash
curl -X POST http://127.0.0.1:8010/advisor/variants/generate \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"context_id": "proj-001"}' | jq

curl -X POST http://127.0.0.1:8010/advisor/variants/compare \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "proj-001",
    "variant_ids": ["abc", "def", "ghi"]
  }' | jq
```

### 7.5 TypeScript klient

```typescript
const set = await fetch("/api/advisor/variants/generate", {
  method: "POST",
  body: JSON.stringify({ context_id: "proj-001" }),
}).then(r => r.json());

console.table(
  set.variants.map((v: any) => ({
    name: v.name,
    cost: v.estimated_cost_usd,
    time_h: v.estimated_time_hours,
    risk: v.risk_level,
    quality: v.quality_projection,
  })),
);
```

## 8. Verification

### 8.1 Pytest

```bash
cd src/sylion-pipeline
pytest tests/aeis/advisor/variants/ -v
```

Kluczowe scenariusze:

- `test_generate_returns_three_variants` — zawsze 3.
- `test_variant_names_match_templates` — `["cost_saving","balanced","aggressive"]`.
- `test_cost_saving_cheaper_than_balanced` — porządek cen.
- `test_aggressive_higher_quality_than_others` — porządek jakości.
- `test_compare_picks_minimum_cost` — winner po kosztach.
- `test_compare_with_one_variant_returns_empty_dimensions` — minimum 2 ID.
- `test_event_emitted_after_generate` — wykrycie `variants.generated`.

### 8.2 Smoke test

```python
python -c "
from sylion.aeis.advisor.variants.service import get_variants_service
vs = get_variants_service().generate_variants()
assert len(vs.variants) == 3
print(' '.join(v.name for v in vs.variants))
"
```

### 8.3 Manualny test edge case (wszyscy zewnętrzni zablokowani)

```python
from sylion.aeis.advisor.preferences import get_preferences

# Zablokuj wszystko poza local
get_preferences().set_preference(
    user_id="op-1",
    project_type=None,
    project_domain=None,
    preference_key="blocked_providers",
    value=["anthropic", "openai", "google"],
    source="operator",
)

vs = svc.generate_variants(context={"context_id": "blocked-test"})
# balanced i aggressive policzy z claude-sonnet-4-6 → koszt 0 (blocked)
# To jest known MVP limit (zob. README troubleshooting #1).
```

## 9. Troubleshooting

| Problem | Diagnoza | Fix |
|---|---|---|
| Wszystkie warianty mają koszt $0.00 | (a) Pricing catalog nie zna modeli używanych przez generator. (b) Wszyscy zewnętrzni providerzy są zablokowani. | (a) Sprawdź `pricing.catalog.get_model("claude-sonnet-4-6")` — powinno zwrócić obiekt. Jeśli `None`, baza cenowa to stub. (b) Sprawdź `blocked_providers` w preferencjach operatora. |
| `variant_id` różni się przy każdym wywołaniu | UUID4 generowany w `__post_init__`. | To by-design. Porównuj warianty po `name`, nie po `variant_id`. Zachowaj `variant_id` jeśli chcesz odwołać się do konkretnego wariantu w `compare_variants`. |
| Wariant `aggressive` tańszy niż `balanced` | Albo override `council_size` w aggressive zmniejszył radę, albo pricing.catalog zwraca 0 dla critic_model. | Sprawdź `parameters` wariantu. Jeśli `critic_model: "claude-opus-4-7"` ale `pricing.catalog.get_model("claude-opus-4-7")` to None — koszt critic = 0. |
| `compare_variants` zwraca pustą tabelę | Mniej niż 2 ID lub nie zgadzają się z `context_id`. | (a) Wybierz minimum 2 warianty. (b) Upewnij się, że wszystkie ID pochodzą z tego samego `VariantSet` (wpisanego w `_history` pod tym samym `context_id`). |
| `compare_variants` zwraca `{"error": "no variants"}` | `_history` puste — proces został zrestartowany. | Wywołaj `generate_variants` najpierw. Pamięć jest in-memory; restart procesu = utrata historii. |
| Wszystkie warianty mają `risk_level=medium` | Heurystyka `_assess_risk` traktuje (use_external=True, vps<3) jako medium. | To by-design. cost_saving ma low (no external + council=3); aggressive z vps=3 ma high. |
| `generated_at` przy każdej re-generacji rośnie | `time.time()` w `__post_init__`. | By-design — to nie jest cache, każda generacja jest świeża. Jeśli chcesz cache na `context_id` — zachowaj `VariantSet` po stronie wołającego. |
| Override w `context` nie wpływa na warianty | Klucz w `context` musi pokrywać się z kluczem w `parameters` szablonu (`council_size, use_local_models, use_external_apis, vps_envs, topology, critic_model`). | Inne klucze są ignorowane przez generator. |
| `aggressive` wymaga multi_vps, ale scaling odrzuca | Wariant generuje rekomendację bez konsultacji ze scaling. | To prawidłowe — variants generuje "co byłoby super", scaling weryfikuje wykonalność. Operator musi przejść przez D3 HG dla `multi_vps`. |
| Preview porównania pokazuje quality 0.0 | `quality_projection=0.0` przy default Variant — gdy generator nie został wykonany. | Sprawdź czy variant pochodzi z `generate_variants` (a nie ręcznie utworzony). |

## 10. Cross-references

### Powiązane moduły

- **`sylion.aeis.advisor.role_resolver`** — wybiera modele critic/worker, których koszty wlatują do `_estimate_variant_cost`. Jeśli operator zablokuje providerów, resolver zwróci local fallback i koszty wariantu spadną.
- **`sylion.aeis.advisor.pricing.estimator`** — `estimate_cost(model_id, input_tokens, output_tokens)` jest wołane wielokrotnie w cyklu council × calls_per_member.
- **`sylion.aeis.advisor.scaling`** — wariant `aggressive` ma `topology: "multi_vps"`. Scaling weryfikuje wykonalność i emituje D3+ kartę z Evidence Pack.
- **`sylion.aeis.advisor.subscription`** — pokazuje rzeczywiste koszty po wykonaniu wariantu; porównuje z `estimated_cost_usd` z variantu.
- **`sylion.aeis.advisor.engine`** — engine może wywołać `generate_variants` przed prezentacją kart, aby operator zobaczył opcje wykonania.

### Architecture refs

- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — wybór wariantu to D2/D3 (zwłaszcza aggressive).
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — pełna taksonomia eventów advisor.
- `src/sylion-pipeline/sylion/aeis/advisor/variants/README.md` — operator-friendly guide po polsku.
- `src/sylion-pipeline/sylion/aeis/advisor/variants/templates.py` — kanoniczne stałe szablonów.

### Wewnątrz dokumentacji

- [`docs/dokumentacja/01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md) — wysokopoziomowa rola wariantów w warstwie advisor.
- [`docs/dokumentacja/modules/06_pricing.md`](./06_pricing.md) — estimator używany w generatorze.
- [`docs/dokumentacja/modules/08_role_resolver.md`](./08_role_resolver.md) — resolver wpływa na to, jaki model używany jest w danej rundzie rady.
- [`docs/dokumentacja/modules/10_subscription.md`](./10_subscription.md) — subscription porównuje estymacje wariantów z faktycznymi kosztami.
- [`docs/dokumentacja/modules/11_scaling.md`](./11_scaling.md) — scaling weryfikuje wykonalność topologii zaproponowanej przez wariant.
