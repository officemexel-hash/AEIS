# Variants — Operator Guide

## Co robi ten moduł

Generuje **3 warianty strategiczne** wykonania każdego projektu AEIS: oszczędny (cost-saving), zbalansowany (balanced) i agresywny (aggressive). Każdy wariant zawiera szacowany koszt (USD), czas, poziom ryzyka i jakość. Operator może porównać warianty i wybrać najlepszy dla swojego budżetu lub terminu.

## Kiedy operator wchodzi w interakcję

- **Na etapie planowania projektu** — AEIS wyświetla kartę *Warianty wykonania* z trzema propozycjami.
- **W panelu Operator → Warianty** — możesz wygenerować warianty ręcznie dla dowolnego kontekstu.
- **W porównywarce** — po wygenerowaniu AEIS pokazuje macierz porównawczą (najtańszy, najszybszy, najbezpieczniejszy, najwyższa jakość).

## Konfiguracja

Aktualnie warianty są generowane na podstawie **szablonów wbudowanych**; operator może wpłynąć na nie pośrednio przez preferencje:

| Ustawienie | Gdzie w UI | Efekt na warianty |
|---|---|---|
| **Blokowani providerzy** | Preferencje → Bezpieczeństwo | Jeśli zablokujesz wszystkich zewnętrznych providerów, warianty *balanced* i *aggressive* automatycznie przełączą się na lokalne modele (koszt spadnie, jakość może się zmienić). |
| **Limit kosztu (cost ceiling)** | Preferencje → Budżet | Wariant przekraczający limit zostanie oznaczony jako ryzykowny lub niedostępny. |
| **Council size override** | Preferencje → Rada (future) | Pozwoli wymusić liczbę członków rady we wszystkich wariantach. *(Czeka na Codex Phase 2)* |

> W przyszłości w panelu **Warianty → Konfiguracja** będzie można bezpośrednio edytować: `council_size`, `vps_envs`, `use_external_apis`, `critic_model`.

## Rozwiązywanie problemów

### 1. Warianty mają koszt $0.00 — czy to błąd?

**Symptom**: Wszystkie warianty pokazują koszt 0 USD, nawet aggressive z Claude Opus.

**Przyczyna**: Baza cenowa (`pricing_estimator`) nie zna danego modelu lub jest w trybie lokalnym (wszystkie lokalne modele są darmowe).

**Rozwiązanie**:
1. Sprawdź w logu event `aeis.advisor.variants.generated` — zobacz, które modele zostały użyte.
2. Jeśli wszystkie to `qwen*` — upewnij się, że providerzy zewnętrzni nie są zablokowani.
3. Jeśli model jest nieznany — oznacza to, że baza cenowa jest tymczasowym stubem; czekamy na Codex Phase 2 (moduł pricing).

### 2. Warianty nie są deterministyczne — za każdym razem inne ID

**Symptom**: Generujesz warianty dla tego samego projektu i za każdym razem inne `variant_id`.

**Przyczyna**: `variant_id` to UUID, a `generated_at` to timestamp — oba są losowe/zależne od czasu. To **prawidłowe zachowanie**.

**Rozwiązanie**: Nie martw się o ID. Porównuj warianty po nazwie i parametrach (`cost`, `time`, `risk`, `quality`). W logach event `aeis.advisor.variants.compared` zawiera zawsze stabilne wymiary.

### 3. Wariant "aggressive" jest tańszy niż "balanced"

**Symptom**: `aggressive` kosztuje mniej niż `balanced`, co wydaje się nielogiczne.

**Przyczyna**: Błędna konfiguracja preferencji (np. council_size override zmniejszyło radę w aggressive) lub baza cenowa zwraca 0 dla nieznanych modeli.

**Rozwiązanie**:
1. Sprawdź, czy nie masz aktywnego override council_size.
2. Sprawdź logi eventów — zobacz, jakie modele critic zostały przypisane.
3. Jeśli problem się powtarza — zgłoś do zespołu jako potencjalny błąd w tabeli routingu lub stubie cenowym.

### 4. Porównanie wariantów zwraca pusty wynik

**Symptom**: Po kliknięciu "Porównaj" AEIS pokazuje pustą tabelę lub błąd.

**Przyczyna**: Porównanie wymaga min. 2 wariantów lub brak historii dla danego `context_id`.

**Rozwiązanie**:
1. Upewnij się, że wygenerowałeś warianty przed porównaniem.
2. Sprawdź, czy nie porównujesz wariantów z różnych projektów (`context_id` musi się zgadzać).
3. W panelu wyczyść historię i wygeneruj warianty na nowo.

## Eventy emitowane (audit / debug)

| Event | Kiedy | Payload (kluczowe pola) |
|---|---|---|
| `aeis.advisor.variants.generated` | Po wygenerowaniu 3 wariantów | `context_id`, `variant_count`, `variant_names[]` |
| `aeis.advisor.variants.compared` | Po porównaniu wariantów | `context_id`, `variant_ids[]`, `dimensions[]`, `winner_per_dimension` |

> Eventy można podejrzeć w panelu **Operator → Audit Trail** lub w konsoli przez `EventBus.subscribe(...)`.

## Cross-references

- **Role Resolver** — wybiera modele critic/worker, które bezpośrednio wpływają na koszt i jakość wariantu.
- **Subscription** — warianty pokazują szacowany koszt; subscription trackuje faktyczne zużycie i porównuje z planem.
- **Scaling** — wariant *aggressive* może rekomendować `multi_vps`; scaling weryfikuje, czy topologia jest wykonalna.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md) — wybór wariantu to decyzja D2/D3.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md) — pełna taksonomia eventów advisor.
