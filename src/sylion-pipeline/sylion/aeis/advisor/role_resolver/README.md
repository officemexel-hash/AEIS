# Role Resolver — Operator Guide

## Co robi ten moduł

Wybiera konkretny model LLM dla każdej roli AEIS (planner, worker, critic, governance, judge) na podstawie poziomu ryzyka zadania oraz Twoich preferencji. Zanim AEIS wyśle zapytanie do zewnętrznego API, ten moduł decyduje: *który model, u którego providera, za ile*.

## Kiedy operator wchodzi w interakcję

- **Przy tworzeniu nowego projektu** — resolver wybiera model plannera i pierwszego workera.
- **Przez panel Preferencje → Routing modeli** — możesz wymusić konkretny model dla danej roli.
- **Przez panel Preferencje → Blokowani providerzy** — wykluczasz providerów (np. OpenAI, Anthropic).
- **W podglądzie rekomendacji** (gdy AEIS wyświetla kartę *Routing*) — resolver pokazuje dlaczego wybrał dany model i jakie były alternatywy.

## Konfiguracja

W panelu **Operator → Preferencje → AI Models** ustawiasz trzy rzeczy, które bezpośrednio wpływają na resolver:

| Ustawienie | Gdzie w UI | Efekt |
|---|---|---|
| **Blokowani providerzy** | Preferencje → Bezpieczeństwo → Blokowani providerzy | Modele z zablokowanej firmy są pomijane (np. `claude` → Anthropic, `gpt` → OpenAI). |
| **Limit kosztu (cost ceiling)** | Preferencje → Budżet → Limit kosztu per poziom ryzyka | Modele droższe niż limit są odrzucane. Domyślnie: low=$25, medium=$25, high=$150, critical=$200. |
| **Nadpisanie routingu** | Preferencje → AI Models → Routing override | Wymuszasz konkretny model dla roli/poziomu ryzyka. Ma pierwszeństwo przed wszystkim. |

> **Uwaga**: Wszystkie ustawienia są per-operator. Jeśli nie ustawisz niczego, resolver użyje tabeli domyślnej (Claude Sonnet/Opus w zależności od ryzyka, Qwen jako lokalny fallback).

## Rozwiązywanie problemów

### 1. AEIS ciągle wybiera lokalny model (Qwen) zamiast zewnętrznego

**Symptom**: Wszystkie rekomendacje mają `is_local_fallback=True`, model to `qwen2.5:72b-instruct`.

**Przyczyna**: Wszyscy zewnętrzni providerzy są zablokowani lub limit kosztu jest za niski.

**Rozwiązanie**:
1. Wejdź w **Preferencje → Bezpieczeństwo → Blokowani providerzy**.
2. Upewnij się, że lista nie zawiera providera, którego chcesz używać (usuń np. `anthropic`, `openai`, `google`).
3. Sprawdź **Preferencje → Budżet** i podnieś limit dla poziomu `high` / `critical`.
4. Wyczyść pamięć podręczną AEIS (restart operatora).

### 2. Pomimo ustawienia override model się nie zmienia

**Symptom**: Wpisałeś override np. `"planner:critical" → "gpt-5"`, ale resolver dalej wybiera Claude Opus.

**Przyczyna**: Wybrany model jest zablokowany lub nie ma go w bazie cenowej.

**Rozwiązanie**:
1. Sprawdź, czy provider modelu (np. `openai` dla `gpt-5`) nie jest na liście blokowanych.
2. Sprawdź, czy model istnieje w bazie (`resolver.py` loguje `unknown model` w eventach).
3. Upewnij się, że klucz override jest dokładny: `"planner:critical"` lub `"planner"` (bez spacji, wielkość liter ma znaczenie).

### 3. Wysoki koszt — resolver wybiera drogi model Opus na każdym zadaniu

**Symptom**: Miesięczny rachunek rośnie, a wszystkie zadania "critical" idą do Opus.

**Przyczyna**: Nie ustawiono limitu kosztu (`cost ceiling`) lub jest on za wysoki.

**Rozwiązanie**:
1. Wejdź w **Preferencje → Budżet → Limit kosztu**.
2. Ustaw realistyczne wartości (np. critical=$100 zamiast domyślnych $200).
3. Resolver automatycznie odrzuci modele powyżej limitu i wybierze tańszą alternatywę (Sonnet, Gemini) lub lokalny model.

### 4. W konsoli widać `RuntimeError: No available model for ...`

**Symptom**: AEIS rzuca wyjątek i nie może wykonać zadania.

**Przyczyna**: Wszystkie modele (również lokalne) zostały wykluczone przez blokady lub limity.

**Rozwiązanie**:
1. Sprawdź log eventu `aeis.advisor.role_resolver.fallback_to_local` — zobacz jaki model próbował wybrać.
2. Tymczasowo usuń wszystkich zablokowanych providerów lub ustaw limity na `0` (brak limitu).
3. Upewnij się, że lokalny Ollama/Qwen jest uruchomiony.

## Eventy emitowane (audit / debug)

| Event | Kiedy | Payload (kluczowe pola) |
|---|---|---|
| `aeis.advisor.role_resolver.routing_decision` | Po każdej normalnej decyzji | `operator_id`, `role`, `risk_level`, `resolved_model`, `reason`, `estimated_cost_usd` |
| `aeis.advisor.role_resolver.override_applied` | Gdy operator wymusił model override | `operator_id`, `role`, `resolved_model`, `override_key` |
| `aeis.advisor.role_resolver.fallback_to_local` | Gdy wszystkie zewnętrzne modele odrzucone | `operator_id`, `role`, `resolved_model`, `reason` |

> Eventy można podejrzeć w panelu **Operator → Audit Trail** lub w konsoli przez `EventBus.subscribe(...)`.

## Cross-references

- **Variants** — resolver wybiera model, variants decydują o składzie rady i topologii.
- **Subscription** — resolver patrzy na `cost_ceilings` z preferencji; subscription trackuje faktyczne koszty.
- **Scaling** — decyzja o VPS/multi-VPS wpływa na dostępność lokalnych modeli, co zmienia fallback resolvera.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md) — poziomy ryzyka i D-ladder.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md) — pełna taksonomia eventów advisor.
