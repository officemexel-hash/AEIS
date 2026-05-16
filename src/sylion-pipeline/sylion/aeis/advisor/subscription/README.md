# Subscription — Operator Guide

## Co robi ten moduł

Śledzi zużycie tokenów i kosztów per operator, liczy zwrot z inwestycji (ROI) w subskrypcję oraz rekomenduje: utrzymaj plan, zmień na wyższy, obniż lub kup nowy. **Każda rekomendacja zakupu jest twardo zablokowana na poziomie D3+** — wymaga Evidence Pack i Human Gate; AEIS nigdy nie kupi niczego automatycznie.

## Kiedy operator wchodzi w interakcję

- **Panel Operator → Subskrypcje** — przeglądasz aktualny plan, miesięczny koszt i historię zużycia.
- **Karta rekomendacji *Downgrade*** — gdy zużycie spadnie poniżej 30% wartości planu, AEIS sugeruje obniżenie.
- **Karta rekomendacji *Purchase*** — gdy nie masz planu lub ROI wskazuje, że opłaca się kupić wyższy; karta jest D3 i wymaga Twojego potwierdzenia.
- **Panel Operator → Użycie** — szczegółowe raporty per model, per dzień, z prognozą break-even.

## Konfiguracja

Obecnie moduł **nie ma** konfiguracji per-operator w UI. Wszystkie progi są hardcoded:

| Parametr | Wartość | Znaczenie |
|---|---|---|
| Próg zużycia (24h) | **$10.00** | Po przekroczeniu emituje event `usage_threshold_crossed`. |
| Okno obserwacji ROI | **30 dni** | Na podstawie ostatnich 30 dni liczymy czy plan się opłaca. |
| Próg downgrade | **< 30%** planu | Gdy koszt < 30% ceny planu → rekomendacja downgrade. |
| Próg upgrade | **> 150%** planu | Gdy koszt > 150% ceny planu → rekomendacja upgrade. |

> Plan możesz wybrać z katalogu domyślnego (Anthropic Pro, OpenAI Team, Google Paid) lub zarejestrować własny w panelu **Subskrypcje → Niestandardowy plan**.

## Rozwiązywanie problemów

### 1. AEIS sugeruje downgrade, ale chcę zostać przy obecnym planie

**Symptom**: Karta *Downgrade* pojawia się co miesiąc, choć świadomie płacisz za wyższy plan.

**Przyczyna**: Prog 30% jest zbyt agresywny dla Twojego wzorca użycia (np. sezonowe projekty).

**Rozwiązanie**:
1. W panelu **Subskrypcje → Użycie** sprawdź wykres ostatnich 30 dni.
2. Jeśli zużycie jest nieregularne (góry/doliny) — zignoruj rekomendację; AEIS jej nie wymusza.
3. Jeśli chcesz całkowicie wyłączyć downgrade — ustaw flagę `opt_out` w konfiguracji operatora (panel **Operator → Ustawienia → Opt-out z doradztwa finansowego**).

### 2. W logach pojawia się `AssertionError: subscription cards must be D3+`

**Symptom**: Czerwony błąd w konsoli / logach, AEIS przerywa przetwarzanie.

**Przyczyna**: Kod próbował utworzyć rekomendację zakupu bez spełnienia HARD GATE (brak Evidence Pack, zły poziom D, brak Human Gate).

**Rozwiązanie**:
1. To **błąd wewnętrzny AEIS**, nie Twoja wina. Zgłoś do zespołu.
2. W logu eventu `aeis.advisor.subscription.purchase_recommended` sprawdź, czy `evidence_pack_id` jest obecny.
3. Tymczasowo restart AEIS; resolver powinien wygenerować poprawną kartę przy następnym cyklu.

### 3. Zużycie pokazuje $0, mimo że pracowałem cały dzień

**Symptom**: Panel Operator → Użycie pokazuje 0 tokenów i 0 koszt.

**Przyczyna**: AEIS nie zdążył jeszcze zebrać metryk lub lokalne modele (Qwen) nie raportują kosztu.

**Rozwiązanie**:
1. Poczekaj do końca cyklu billingowego (do 24h opóźnienia dla zewnętrznych API).
2. Upewnij się, że masz aktywny plan w panelu **Subskrypcje**.
3. Jeśli używasz tylko lokalnych modeli — koszt jest $0 (brak płatnych API). Jest to prawidłowe.

### 4. ROI pokazuje "unknown_plan" i brak break-even

**Symptom**: W karcie ROI widzisz `unknown_plan` i brak dni do break-even.

**Przyczyna**: AEIS nie zna planu, który wpisałeś (nie ma go w katalogu ani w niestandardowych planach).

**Rozwiązanie**:
1. Wejdź w **Subskrypcje → Niestandardowy plan** i zarejestruj swój plan z podaniem: `provider_id`, `monthly_price_usd`, `included_tokens`.
2. Upewnij się, że `plan_id` w konfiguracji operatora zgadza się z ID w katalogu.
3. Po rejestracji ROI zostanie przeliczone przy następnym cyklu (co najmniej 1h).

### 5. Event `usage_threshold_crossed` spamuje co minutę

**Symptom**: W audit trail co chwilę pojawia się alert przekroczenia $10.

**Przyczyna**: Próg $10 jest sprawdzany przy *każdym* rekordzie zużycia; jeśli jesteś powyżej budżetu, alert leci za każdym razem (brak debounce).

**Rozwiązanie**:
1. To znany limit w obecnej wersji (brak debounce). Zignoruj duplikaty w audit trail.
2. Sprawdź **Subskrypcje → Użycie** i podnieś limit w preferencjach operatora (future: konfiguracja progu w UI).
3. Jeśli zużycie jest anomalne — sprawdź w logach, który model/provider generuje najwięcej kosztu.

## Eventy emitowane (audit / debug)

| Event | Kiedy | Payload (kluczowe pola) |
|---|---|---|
| `aeis.advisor.subscription.usage_recorded` | Po każdym zapisie zużycia | `operator_id`, `provider_id`, `model_id`, `tokens_in`, `tokens_out`, `cost_usd` |
| `aeis.advisor.subscription.usage_threshold_crossed` | Gdy koszt 24h > $10 | `operator_id`, `threshold`, `current_24h_cost` |
| `aeis.advisor.subscription.custom_plan_registered` | Po rejestracji niestandardowego planu | `operator_id`, `plan_id`, `monthly_price_usd` |
| `aeis.advisor.subscription.purchase_recommended` | Po wygenerowaniu karty D3+ | `operator_id`, `plan_id`, `d_level`, `evidence_pack_id` |
| `aeis.advisor.subscription.downgrade_recommended` | Po wygenerowaniu karty downgrade | `operator_id`, `plan_id`, `roi_recommendation` |

> Eventy można podejrzeć w panelu **Operator → Audit Trail** lub w konsoli przez `EventBus.subscribe(...)`.

## Cross-references

- **Role Resolver** — wybiera modele, które generują koszt; subscription trackuje ten koszt per operator.
- **Variants** — pokazuje szacowany koszt projektu; subscription weryfikuje, czy operatora stać na plan obsługujący dany wariant.
- **Scaling** — rekomendacja VPS (D3+) może wymagać nowego planu; subscription sprawdza ROI przed zatwierdzeniem.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md) — D3+ HARD GATE dla zakupów.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md) — wymagana zawartość Evidence Pack przy zakupie.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md) — pełna taksonomia eventów advisor.
