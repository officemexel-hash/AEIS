# Moduł: sylion.aeis.advisor.subscription
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

Moduł `sylion.aeis.advisor.subscription` jest **trackerem zużycia i doradcą subskrypcji** dla operatora SYLION. Po pierwsze: rejestruje każdą operację zużywającą tokeny lub generującą koszt (per provider, per model, per operator) w tabeli `subscription_usage`. Po drugie: liczy ROI na podstawie zużycia w oknie obserwacyjnym 30 dni i rekomenduje jedną z czterech akcji: **keep / upgrade / downgrade / purchase**. Po trzecie: udostępnia katalog domyślnych planów subskrypcyjnych (Anthropic Pro, OpenAI Team, Google Paid) oraz pozwala operatorowi rejestrować własne plany niestandardowe.

Najistotniejszą cechą modułu jest **HARD GATE D3+** dla wszystkich rekomendacji typu *PURCHASE_PLAN*. AEIS NIGDY nie kupuje subskrypcji automatycznie. Każda karta zakupu musi mieć: (a) `d_level >= D3`, (b) niepusty `evidence_pack_id`, (c) `human_gate_required=True`. Naruszenie któregokolwiek z tych warunków rzuca `AssertionError("subscription cards must be D3+")` — co jest celowym blokerem zaprojektowanym, by uniemożliwić nawet błędnemu kodowi advisor obejście Human Gate. Karty `DOWNGRADE` są lżejsze (D2, bez Evidence Pack) — operator może je zignorować.

## 2. Architektura modułu

### Pliki w module

| Plik | Rola |
|---|---|
| `__init__.py` | Eksport publicznego API. |
| `service.py` | `SubscriptionService` — fasada. Trzyma asercje HARD GATE w `emit_purchase_recommendation`. |
| `_models.py` | Dataclassy: `UsageRecord`, `UsageReport`, `Plan`, `ROICalculation`, `RecommendationCard`. |
| `_db.py` | No-op w trybie PG-only. Schema żyje w Alembic migration. |
| `plan_catalog.py` | CRUD nad `subscription_plans` + seed `DEFAULT_PLANS` + `subscription_custom_plans` dla operator-specific. |
| `roi_calculator.py` | `compute_roi(operator_id, plan_id, window_days=30)` — wylicza break-even i recommendation. |
| `usage_tracker.py` | `record_usage(...)` insert do `subscription_usage`; `get_usage_report(operator, start, end)` aggregation. |
| `grpc_server.py` | Stub gRPC servicer. |
| `README.md` | Operator guide po polsku — pokrywa downgrade, ROI unknown_plan, threshold spam. |

### Dependencies

**Wewnętrzne:**

- `sylion.aeis.advisor.pricing` (manifest depends_on, używane jako kontekst — sam serwis nie wywołuje pricing bezpośrednio).
- `sylion.aeis.advisor._db` — wspólny pool PG (`shared_db.get_pool()`).
- `sylion.core.event_bus` — emisja eventów.

**Zewnętrzne:**

- `psycopg.rows.dict_row` — PG driver.
- Standard library: `json`, `time`, `uuid`, `logging`.

### Storage

| Schema | Tabele |
|---|---|
| `subscription_usage` | `subscription_usage` |
| `subscription_plans` | `subscription_plans` |
| `subscription_custom_plans` | `subscription_custom_plans` |

Schemat jest tworzony Alembic migration; moduł nie tworzy tabel w runtime (`_db.ensure_tables()` to no-op).

### Workers / threads / async loops

Brak. Wszystko synchroniczne. Sprawdzanie progu `>$10/24h` przy każdym `record_usage` (brak debounce — known limit).

## 3. Konfiguracja

### Environment variables

Brak.

### Hardcoded thresholds (w `service.py`)

| Parametr | Wartość | Lokalizacja | Znaczenie |
|---|---|---|---|
| Próg dziennego kosztu | `$10.00` | `service.record_usage` | Po przekroczeniu emituje `usage_threshold_crossed`. |
| Okno ROI | `30 dni` | `roi_calculator.compute_roi` | Default `observation_window_days`. |
| Próg downgrade | `< 30%` planu | `roi_calculator.compute_roi` | `usage_cost < plan_cost_for_window * 0.3` → recommendation `downgrade`. |
| Próg upgrade | `> 150%` planu | `roi_calculator.compute_roi` | `usage_cost > plan_cost_for_window * 1.5` → recommendation `upgrade`. |
| Threshold od którego brak limitu downgrade | `usage_cost == 0` | `roi_calculator.compute_roi` | Brak zużycia → automatic `downgrade`. |

### Default plan catalog (`plan_catalog.DEFAULT_PLANS`)

| plan_id | provider_id | monthly_price_usd | included_tokens | rpm | tpm | source |
|---|---|---|---|---|---|---|
| `anthropic_pro` | `anthropic` | $200 | 5,000,000 | 4,000 | 400,000 | https://www.anthropic.com/pricing |
| `openai_team` | `openai` | $500 | 10,000,000 | 10,000 | 2,000,000 | https://openai.com/pricing |
| `google_paid` | `google` | $100 | 5,000,000 | 3,600 | 2,000,000 | https://ai.google.dev/pricing |

Wszystkie domyślne plany mają `is_assumption=True` (oznacza że ceny są szacunkowe i mogą wymagać aktualizacji).

### Custom plan registration

Operator może zarejestrować własny plan przez `register_custom_plan(plan_data)`:

```python
{
    "plan_id": "my_enterprise_plan",
    "operator_id": "op-1",
    "provider_id": "internal",
    "monthly_price_usd": 1500,
    "included_tokens": 50_000_000,
    "rate_limits": {"rpm": 50000, "tpm": 5_000_000},
    "source_url": "internal_contract.pdf",
}
```

## 4. Funkcje (gRPC RPCs / REST endpoints)

### 4.1 `record_usage(operator_id, provider_id, model_id, tokens_in, tokens_out, cost) -> UsageRecord`

- **Sygnatura proto:** `rpc RecordUsage(UsageRequest) returns (UsageRecord)`.
- **Input:** wszystkie pola wymagane.
- **Output:** `UsageRecord` z auto-generowanym `record_id` (UUID hex) i `timestamp`.
- **Side effects:**
  - Insert do `subscription_usage`.
  - Emituje `aeis.advisor.subscription.usage_recorded` (z `record_id, operator_id, cost_usd`).
  - Sprawdza cumulative cost w 24h. Jeśli `> $10` → emituje `usage_threshold_crossed`.
- **Errors:** brak (wymagane wszystkie pola, nie waliduje provider/model).

### 4.2 `get_usage_report(operator_id, period_start, period_end) -> UsageReport`

- **Sygnatura:** `rpc GetUsageReport(UsageReportRequest) returns (UsageReport)`.
- **Input:** epoch start/end.
- **Output:** `UsageReport` z aggregations: `total_tokens_in`, `total_tokens_out`, `total_cost_usd`, `record_count`.
- **SQL:** `SUM(tokens_in), SUM(tokens_out), SUM(cost_usd), COUNT(*)` z `WHERE operator_id = ? AND timestamp BETWEEN ? AND ?`.

### 4.3 `compute_roi(operator_id, plan_id, observation_window_days=30) -> ROICalculation`

- **Sygnatura:** `rpc ComputeROI(ROIRequest) returns (ROICalculation)`.
- **Input:**
  - `plan_id` — z catalog (default lub custom).
  - `observation_window_days` (int, default 30).
- **Output:** `ROICalculation`:
  - `usage_cost_without_plan` — co operator wydałby bez planu (z `subscription_usage`).
  - `plan_cost` — `monthly_price_usd * window/30`.
  - `break_even_days` — `monthly_price_usd / daily_usage` lub `None` jeśli usage=0.
  - `recommendation` — `keep | upgrade | downgrade | purchase | unknown_plan`.

#### Logika rekomendacji

```python
if plan is None:
    return ROICalculation(..., recommendation="unknown_plan")

if usage_cost == 0:
    recommendation = "downgrade"
elif usage_cost > plan_cost_for_window * 1.5:
    recommendation = "upgrade"
elif usage_cost < plan_cost_for_window * 0.3:
    recommendation = "downgrade"
else:
    recommendation = "keep"
```

### 4.4 `list_available_plans(provider_id=None) -> list[dict]`

- **Sygnatura:** `rpc ListAvailablePlans(ListPlansRequest) returns (PlansResponse)`.
- Listuje plany z `subscription_plans`, opcjonalnie filtrowane po providerze.
- Sortowane po `monthly_price_usd` rosnąco.

### 4.5 `register_custom_plan(plan_data: dict) -> None`

- **Sygnatura:** `rpc RegisterCustomPlan(CustomPlanRequest) returns (Empty)`.
- Insert/update do `subscription_custom_plans` (ON CONFLICT update).
- Emituje `aeis.advisor.subscription.custom_plan_registered`.

### 4.6 `emit_purchase_recommendation(operator_id, plan_id, roi_calc, evidence_pack_id) -> RecommendationCard`

- **Sygnatura:** `rpc EmitPurchaseRecommendation(PurchaseRequest) returns (RecommendationCard)`.
- **HARD GATE:** kod zawiera 4 asercje:
  ```python
  assert card.d_level in ("D3","D4","D5"), "subscription cards must be D3+"
  assert card.evidence_pack_id is not None, "subscription cards must have Evidence Pack"
  assert card.evidence_pack_id != "", "subscription cards must have non-empty Evidence Pack"
  assert card.human_gate_required is True, "subscription cards must require Human Gate"
  ```
- **Output:** `RecommendationCard` z `card_id, d_level=D3, recommendation_type=PURCHASE_PLAN, evidence_pack_id, human_gate_required=True, payload={"roi": ...}`.
- **Side effects:** emituje `aeis.advisor.subscription.purchase_recommended`.
- **Errors:** `AssertionError` przy próbie obejścia gate.

### 4.7 `emit_downgrade_recommendation(operator_id, plan_id, roi_calc) -> RecommendationCard`

- **Sygnatura:** `rpc EmitDowngradeRecommendation(DowngradeRequest) returns (RecommendationCard)`.
- Karta D2, bez Evidence Pack, bez Human Gate.
- Emituje `aeis.advisor.subscription.downgrade_recommended`.
- Operator może zignorować.

### Decision Ladder

| recommendation_type | d_level | evidence_pack | human_gate |
|---|---|---|---|
| `PURCHASE_PLAN` | D3+ | required (non-empty) | True |
| `DOWNGRADE` | D2 | None | False |
| `KEEP` | D0 | — | False (no card) |
| `UPGRADE` | D3+ (Etap 2) | required | True |

## 5. Eventy

### Emitted

| Topic | Kiedy | Payload |
|---|---|---|
| `aeis.advisor.subscription.usage_recorded` | Każde `record_usage` | `record_id, operator_id, cost_usd` |
| `aeis.advisor.subscription.usage_threshold_crossed` | Gdy 24h cost > $10 | `operator_id, daily_cost_usd, threshold (=10.0)` |
| `aeis.advisor.subscription.custom_plan_registered` | Po `register_custom_plan` | `plan_id, operator_id` |
| `aeis.advisor.subscription.purchase_recommended` | Po `emit_purchase_recommendation` (po HARD GATE pass) | `card_id, operator_id, plan_id, d_level, evidence_pack_id` |
| `aeis.advisor.subscription.downgrade_recommended` | Po `emit_downgrade_recommendation` | `card_id, operator_id, plan_id, d_level (=D2)` |

### Subscribed

Brak. Manifest deklaruje `"events_subscribe": []`.

## 6. Database tables

### 6.1 `subscription_usage`

| Kolumna | Typ | Opis |
|---|---|---|
| `record_id` | UUID PK | UUID hex. |
| `operator_id` | TEXT | — |
| `provider_id` | TEXT | `anthropic`, `openai`, `google`, `local`, ... |
| `model_id` | TEXT | `claude-sonnet-4-6`, `gpt-5`, ... |
| `tokens_in, tokens_out` | INT | — |
| `cost_usd` | REAL | $0.00 dla local. |
| `timestamp` | REAL | epoch. |

**Indexes:** `(operator_id, timestamp)`.

**Sample queries:**

```sql
-- Daily cost in last 7 days
SELECT date_trunc('day', to_timestamp(timestamp)) as day,
       SUM(cost_usd) as daily_cost
FROM subscription_usage
WHERE operator_id = $1
  AND timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '7 days')
GROUP BY day
ORDER BY day DESC;

-- Top model by cost in last 30 days
SELECT model_id, SUM(cost_usd) as total
FROM subscription_usage
WHERE operator_id = $1
  AND timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')
GROUP BY model_id
ORDER BY total DESC
LIMIT 10;
```

### 6.2 `subscription_plans`

| Kolumna | Typ | Opis |
|---|---|---|
| `plan_id` | TEXT PK | — |
| `provider_id` | TEXT | — |
| `monthly_price_usd` | REAL | — |
| `included_tokens` | INT | — |
| `rate_limits` | JSONB | `{rpm, tpm}`. |
| `is_assumption` | INT | `1` jeśli cena szacunkowa. |
| `source_url` | TEXT | URL do oficjalnego pricingu. |

**Sample:**

```sql
SELECT * FROM subscription_plans WHERE provider_id = 'anthropic';
```

### 6.3 `subscription_custom_plans`

| Kolumna | Typ | Opis |
|---|---|---|
| `plan_id` | TEXT PK | — |
| `operator_id` | TEXT | Właściciel custom plan. |
| `plan_data` | JSONB | Cały dict z `register_custom_plan`. |
| `created_at` | REAL | epoch. |

## 7. Przykład użycia

### 7.1 Record + ROI workflow (Python)

```python
from sylion.aeis.advisor.subscription.service import get_subscription_service

svc = get_subscription_service()

# 1. Record usage (zwykle robi to engine/role_resolver po każdym call)
svc.record_usage(
    operator_id="op-1",
    provider_id="anthropic",
    model_id="claude-sonnet-4-6",
    tokens_in=1500,
    tokens_out=800,
    cost=0.045,
)

# 2. Sprawdź usage report za ostatnie 30 dni
import time
end = time.time()
start = end - 30 * 86400
report = svc.get_usage_report("op-1", start, end)
print(f"30-day cost: ${report.total_cost_usd:.2f} ({report.record_count} records)")

# 3. Compute ROI dla planu Anthropic Pro
roi = svc.compute_roi("op-1", "anthropic_pro", observation_window_days=30)
print(f"Plan ${roi.plan_cost:.0f} vs usage ${roi.usage_cost_without_plan:.0f}")
print(f"Break-even: {roi.break_even_days} days")
print(f"Recommendation: {roi.recommendation}")
```

### 7.2 Emit purchase recommendation (D3 hard gate)

```python
# Operator chciałby kupić plan — AEIS musi przejść hard gate
roi = svc.compute_roi("op-1", "anthropic_pro")

# Evidence Pack musi istnieć przed wywołaniem
evidence_pack_id = "evp_subscription_anthropic_pro_op1_20260426"

card = svc.emit_purchase_recommendation(
    operator_id="op-1",
    plan_id="anthropic_pro",
    roi_calc=roi,
    evidence_pack_id=evidence_pack_id,
)
print(f"Card {card.card_id} D-level={card.d_level} HG={card.human_gate_required}")
# Karta jest teraz w pending — wymaga akceptacji w panelu Operator → Human Gate
```

### 7.3 Próba obejścia HARD GATE (rzuca AssertionError)

```python
# To ZAWSZE zrzuci AssertionError — by-design protection
try:
    bad_card = RecommendationCard(
        d_level="D2",  # < D3 → assertion fails
        recommendation_type="PURCHASE_PLAN",
        evidence_pack_id=None,
        human_gate_required=False,
    )
    # This would never reach a real call — assertions prevent.
except AssertionError as e:
    print("Blocked:", e)
```

### 7.4 Register custom plan

```python
svc.register_custom_plan({
    "plan_id": "company_enterprise",
    "operator_id": "op-1",
    "provider_id": "anthropic",
    "monthly_price_usd": 2000,
    "included_tokens": 30_000_000,
    "rate_limits": {"rpm": 20000, "tpm": 5_000_000},
    "source_url": "internal_contract.pdf",
})

plans = svc.list_available_plans(provider_id="anthropic")
for p in plans:
    print(p["plan_id"], p["monthly_price_usd"])
```

### 7.5 curl (Etap 2 REST)

```bash
curl -X POST http://127.0.0.1:8010/advisor/subscription/usage \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "operator_id": "op-1",
    "provider_id": "anthropic",
    "model_id": "claude-sonnet-4-6",
    "tokens_in": 1500,
    "tokens_out": 800,
    "cost": 0.045
  }'

curl http://127.0.0.1:8010/advisor/subscription/roi/op-1/anthropic_pro \
  -H "Authorization: Bearer $JWT"
```

## 8. Verification

### 8.1 Pytest

```bash
cd src/sylion-pipeline
pytest tests/aeis/advisor/subscription/ -v
```

Kluczowe scenariusze:

- `test_record_usage_inserts_row` — DB write.
- `test_threshold_crossed_emits_event` — kumulacja >$10/24h.
- `test_purchase_card_requires_d3` — assertion gate.
- `test_purchase_card_requires_evidence_pack` — assertion gate.
- `test_purchase_card_requires_human_gate` — assertion gate.
- `test_downgrade_card_is_d2_no_evidence` — lżejsza ścieżka.
- `test_roi_unknown_plan_returns_recommendation` — nieznany plan.
- `test_roi_zero_usage_recommends_downgrade` — usage=0.
- `test_roi_high_usage_recommends_upgrade` — >150% planu.
- `test_custom_plan_register_and_list` — CRUD.

### 8.2 PostgreSQL — kontrola schematu

```bash
psql -h localhost -U sylion -d sylion -c "\dt subscription_*"
psql -h localhost -U sylion -d sylion -c "SELECT * FROM subscription_plans;"
```

Powinno zwrócić 3 wiersze (DEFAULT_PLANS).

### 8.3 Smoke test

```python
python -c "
from sylion.aeis.advisor.subscription.service import get_subscription_service
svc = get_subscription_service()
print(svc.list_available_plans())
"
```

### 8.4 HARD GATE assertion test

```python
import pytest
from sylion.aeis.advisor.subscription._models import RecommendationCard

# To powinno przejść
good = RecommendationCard(
    d_level="D3",
    evidence_pack_id="evp_xyz",
    human_gate_required=True,
    recommendation_type="PURCHASE_PLAN",
)
assert good.d_level == "D3"

# To w service.emit_purchase_recommendation rzuca AssertionError
# (kod tworzy kartę D3 hardcoded; jeśli ktoś zmodyfikuje na D2, assertion zadziała)
```

## 9. Troubleshooting

| Problem | Diagnoza | Fix |
|---|---|---|
| AEIS sugeruje downgrade co miesiąc, mimo że chcę zostać | Próg `< 30%` planu jest zbyt agresywny dla nieregularnych wzorców użycia. | (a) Zignoruj kartę — AEIS jej nie wymusza. (b) Ustaw flagę `opt_out` w preferencjach (panel **Operator → Ustawienia**). (c) Czekaj na konfigurowalny próg w UI (Etap 2). |
| `AssertionError: subscription cards must be D3+` | Kod próbował utworzyć kartę purchase z d_level<D3 lub bez evidence_pack. | To wewnętrzny błąd AEIS — protection by-design. Sprawdź log eventu `purchase_recommended`. Jeśli `evidence_pack_id` puste — problem w pipeline tworzącym EP. Restart AEIS. |
| Zużycie pokazuje $0 mimo aktywnego użytkowania | (a) AEIS nie zdążył jeszcze zebrać metryk. (b) Lokalne modele (Qwen) nie raportują kosztu. | (a) Czekaj do końca cyklu billingowego (24h dla zewn. API). (b) Lokalne = $0 by-design. (c) Sprawdź log `usage_recorded` — czy event w ogóle jest emitowany. |
| ROI: `recommendation="unknown_plan"`, brak break-even | Plan nie istnieje w `subscription_plans` ani `subscription_custom_plans`. | (a) Wywołaj `register_custom_plan(...)` z `plan_id, monthly_price_usd, included_tokens`. (b) Upewnij się że `plan_id` zgadza się dokładnie. (c) ROI przeliczy się przy następnym cyklu. |
| `usage_threshold_crossed` emituje co minutę | Brak debounce w MVP — próg sprawdzany przy każdym `record_usage`. | (a) Zignoruj duplikaty w audit trail. (b) Podnieś próg (przyszłość: konfiguracja per-operator). (c) Jeśli zużycie anomalne — sprawdź który model generuje koszt (`SELECT model_id, SUM(cost_usd) ...`). |
| `compute_roi` zwraca `usage_cost_without_plan=0` mimo aktywności | Operator nie miał recorded usage w oknie obserwacyjnym lub `record_usage` nie był wywoływany przez engine. | (a) Sprawdź `subscription_usage` SQL: `SELECT * WHERE operator_id=... AND timestamp >= ...`. (b) Sprawdź czy engine wywołuje `record_usage` po każdym call (Etap 2 enhancement). |
| `break_even_days=None` | `daily_usage = 0.0` → division-by-zero protection. | Operator nie używał API w oknie obserwacyjnym. Brak zużycia → brak break-even. |
| Nieaktywny plan w `list_available_plans` | Default plans seedowane są tylko jeśli tabela pusta. | Sprawdź `seed_defaults()` log; manualnie wstaw przez `register_custom_plan`. |
| `recommendation="upgrade"` ale plan_cost niski | `usage_cost > plan_cost_for_window * 1.5`. Upgrade sygnalizuje że obecny plan za mały. | Wybierz wyższy plan (np. anthropic_pro → custom enterprise). Lub obniż użycie przez `cost_ceilings` w resolwerze. |
| Custom plan zarejestrowany, ale nie pojawia się w `list_available_plans` | `list_available_plans` czyta tylko `subscription_plans`. Custom są w osobnej tabeli `subscription_custom_plans`. | (Etap 2) Połącz query. Tymczasowo: czytaj custom plans osobno przez bezpośredni SQL. |
| Eventy `purchase_recommended` nie zawierają `evidence_pack_id` | Eventy są deklaratywne — kod gwarantuje że pole jest niepuste przez assertion przed emisją. | Jeśli widzisz pusty `evidence_pack_id` w event payload — to jest bug; zgłoś. |

## 10.5 Quota Tracker — Subscription-First Routing [sprint4, commit d6eb4d15]

> Etap sprint4 (commit `d6eb4d15`) rozszerzył modul subscription o aktywne sledzenie kwoty i priorytetowe
> routing subscription-first. Ponizsze podsekcje opisuja nowe klasy, funkcje i tabele DB.

### 10.5.1 Cel i zasada dzialania

Przed sprint4 modul subscription rejestrował zużycie *post-factum* i doradzał zakup/downgrade planu.
Po sprint4 modul aktywnie uczestniczy w routingu kazedgo wywolania modelu:

```
Call do model X
   │
   ├─ quota_tracker.get_quota_status(operator_id, model_id)
   │      has_quota=True?
   │         ├─ TAK → effective_cost = $0, source=SUBSCRIPTION, quota decremented
   │         └─ NIE → fallback PAYG (pricing.estimate_cost → cost_ceilings check)
   │
   └─ Jesli PAYG cost > cost_ceiling → reject + suggested_alternative
```

### 10.5.2 Nowe pliki (sprint4)

| Plik | Rola |
|------|------|
| `subscription/quota_tracker.py` | `get_quota_status()`, `consume_quota()`, obliczanie okresu rozliczeniowego |
| `subscription/_models.py` | `SubscriptionQuota` dataclass; `QuotaStatus` NamedTuple |
| `subscription/_db.py` (rozszerzony) | `get_subscription_covering_model()`, `get_quota_usage()`, `upsert_quota_usage()`, `get_subscription()` |
| `alembic/versions/20260427_0001_subscription_quota.py` | Migracja DB: tabele `active_subscriptions` + `quota_usage` |

### 10.5.3 Funkcje quota_tracker.py

#### `get_quota_status(operator_id, model_id) -> QuotaStatus | None`

- Wyszukuje aktywna subskrypcje pokrywajaca `model_id` dla operatora.
- Oblicza biezacy okres rozliczeniowy (`period_start`, `period_end`) na podstawie `reset_day_of_month`.
- Pobiera zuzyte tokeny/USD z `quota_usage` dla danego okresu.
- Zwraca `QuotaStatus` lub `None` jesli brak aktywnej subskrypcji.

```python
class QuotaStatus(NamedTuple):
    has_quota: bool          # True jesli remaining_tokens > 0 LUB remaining_usd > 0
    remaining_tokens: int    # quota_tokens - tokens_consumed (0 jesli brak quota_tokens)
    remaining_usd: Decimal   # quota_usd - usd_consumed (0 jesli brak quota_usd)
    period_end: datetime     # UTC timestamp konca biezacego okresu
    plan_id: str             # np. "claude-pro", "custom"
    subscription_id: str     # UUID subskrypcji
```

`has_quota` jest `True` gdy spelnione SA OBA warunki: `has_token_quota` i `has_usd_quota`. Jesli subskrypcja nie definiuje `monthly_quota_tokens`, wtedy `has_token_quota=True` (nielimitowane tokeny w ramach kwoty USD).

#### `consume_quota(subscription_id, tokens, cost_usd) -> None`

- Wywolywane *po* kazdym wywolaniu modelu ze subskrypcji.
- `UPSERT` do `quota_usage(subscription_id, period_start)` — inkrementuje `tokens_consumed`, `usd_consumed`, `call_count`, ustawia `last_call_at`.

#### `_compute_billing_period(now, reset_day) -> (period_start, period_end)`

- Oblicza granice biezacego okresu rozliczeniowego.
- `reset_day` jest clampowany do `[1, 28]` (zapobiega problemom dla krotkich miesiecy).
- Przyklad: `reset_day=15`, `now=2026-04-20` → `period_start=2026-04-15`, `period_end=2026-05-15`.

### 10.5.4 Nowe tabele DB (migracja `phase4_0003_subscription_quota`)

Migracja: `alembic/versions/20260427_0001_subscription_quota.py` (revision: `phase4_0003_subscription_quota`).

#### `advisor_subscription.active_subscriptions`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `subscription_id` | UUID PK | auto `gen_random_uuid()` |
| `operator_id` | UUID NOT NULL | ID operatora |
| `provider_id` | TEXT NOT NULL | `anthropic`, `openai`, `google`, `openrouter`, `custom` |
| `plan_id` | TEXT NOT NULL | `claude-pro`, `claude-max`, `chatgpt-plus`, `custom`, ... |
| `monthly_quota_tokens` | BIGINT | NULL = nielimitowane tokeny (ograniczone tylko USD) |
| `monthly_quota_usd` | NUMERIC(10,2) | NULL = nielimitowane USD (ograniczone tylko tokenami) |
| `reset_day_of_month` | INT NOT NULL DEFAULT 1 | Dzien miesiaca resetu kwoty (1–28) |
| `models_covered` | TEXT[] | Lista `model_id` objetych subskrypcja |
| `active_from` | TIMESTAMPTZ NOT NULL DEFAULT `now()` | |
| `active_until` | TIMESTAMPTZ | NULL = aktywna bez ograniczen czasowych |
| `monthly_fee_usd` | NUMERIC(10,2) | Miesieczna oplata (informacyjnie dla ROI) |
| `is_active` | BOOLEAN NOT NULL DEFAULT `true` | Soft-disable |

**Indeks:** `idx_active_subscriptions_operator ON (operator_id, is_active)`.

#### `advisor_subscription.quota_usage`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `usage_id` | UUID PK | auto |
| `subscription_id` | UUID NOT NULL FK → `active_subscriptions` | |
| `period_start` | TIMESTAMPTZ NOT NULL | Poczatek okresu rozliczeniowego |
| `period_end` | TIMESTAMPTZ NOT NULL | Koniec okresu rozliczeniowego |
| `tokens_consumed` | BIGINT NOT NULL DEFAULT 0 | Suma tokenow (in+out) w danym okresie |
| `usd_consumed` | NUMERIC(10,4) NOT NULL DEFAULT 0 | Suma kosztow USD (dla planow USD-capped) |
| `call_count` | INT NOT NULL DEFAULT 0 | Liczba wywolan |
| `last_call_at` | TIMESTAMPTZ | Ostatnie wywolanie (diagnostyka) |

**UNIQUE constraint:** `(subscription_id, period_start)` — jeden wiersz per subskrypcja per okres.

**Indeks:** `idx_quota_usage_lookup ON (subscription_id, period_start)`.

**Sample query — biezace zuzycie:**

```sql
SELECT qu.tokens_consumed, qu.usd_consumed, qu.call_count,
       s.monthly_quota_tokens, s.monthly_quota_usd, s.plan_id
FROM advisor_subscription.quota_usage qu
JOIN advisor_subscription.active_subscriptions s USING (subscription_id)
WHERE s.operator_id = $1
  AND s.is_active = true
  AND qu.period_start <= now()
  AND qu.period_end > now();
```

### 10.5.5 Integracja z innymi modulami

- `pricing.estimator.effective_cost_estimate()` — sprawdza quota_tracker przed zwroceniem kosztu PAYG; jesli subskrypcja aktywna → zwraca $0 + `Source.SUBSCRIPTION`.
- `role_resolver.resolver` — w hierarchii routingu kroki 1-2 (override + blocked) poprzedzaja krok 3 "subscription pool". Jesli model pokryty subskrypcja → `used_subscription=True` w `ModelChoice`.
- `subscription.service.record_usage()` — wywoluje `consume_quota()` po kazdym call, inkrementujac `quota_usage`.

## 10. Cross-references

### Powiązane moduły

- **`sylion.aeis.advisor.role_resolver`** — wybiera modele LLM. Każde wywołanie modelu generuje koszt, który `subscription` rejestruje przez `record_usage`.
- **`sylion.aeis.advisor.pricing`** — pricing.estimator dostarcza estymację kosztu, która jest porównywana z `cost_ceilings`. Subscription rejestruje *rzeczywisty* koszt.
- **`sylion.aeis.advisor.variants`** — `Variant.estimated_cost_usd` to przewidywanie. Subscription porównuje przewidywanie z faktycznym zużyciem.
- **`sylion.aeis.advisor.scaling`** — rekomendacja VPS (D3+) może wymagać nowego planu lub uzasadnienia ROI.
- **`sylion.aeis.advisor.engine`** — emituje karty rekomendacji; subscription emituje swoje karty (purchase, downgrade) tym samym kanałem.
- **`sylion.aeis.advisor.governance`** — Human Gate dla D3+ purchase requires konsultacji.
- **`funding_autopilot`** — funding module zużywa tokeny research, które wlatują do `subscription_usage`.

### Architecture refs

- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — D3+ HARD GATE dla zakupów (D-ladder).
- `docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md` — wymagana zawartość Evidence Pack przy zakupie planu.
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — pełna taksonomia eventów.
- `src/sylion-pipeline/sylion/aeis/advisor/subscription/README.md` — operator-friendly guide po polsku.

### Wewnątrz dokumentacji

- [`docs/dokumentacja/01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md) — wysokopoziomowa rola subscription.
- [`docs/dokumentacja/03_governance_audit_compliance.md`](../03_governance_audit_compliance.md) — D-ladder, Human Gate, Evidence Pack.
- [`docs/dokumentacja/modules/06_pricing.md`](./06_pricing.md) — estymacja kosztu (różne od faktycznego rejestrowanego tu).
- [`docs/dokumentacja/modules/08_role_resolver.md`](./08_role_resolver.md) — resolver wybiera model, którego koszt wpada do `subscription_usage`.
- [`docs/dokumentacja/modules/09_variants.md`](./09_variants.md) — variants.estimated_cost_usd vs subscription rzeczywiste.
- [`docs/dokumentacja/modules/11_scaling.md`](./11_scaling.md) — VPS scaling D3+ często wymaga upgrade'u planu.
