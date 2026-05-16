# Glossary - SYLION v2 (operator help blocks PL)

> Bloki pomocy 2-zdaniowe dla nowych pojęć SYLION v2.
> Curated from `docs/v2/_drafts/ollama_batch/batch_D/d8_help_blocks.md`
> + `batch_C/c8_breaker_help.md`.

## Manifest YAML

Manifest YAML definiuje zasoby potrzebne do wdrożenia komponentów SYLION v2 - typy obiektów, role RBAC, szablony aplikacji - i jest centralnym formatem konfiguracji (decyzja A z ADR-001).
Plik jest walidowany podczas API `apply`, co zapewnia spójność środowiska w całej infrastrukturze i daje pełną historię zmian w git.

## OSDK Python

OSDK Python to zestaw bibliotek pozwalających na programowe operacje w SYLION v2 (rejestracja typów, query, mutacje, eventy).
Dzięki temu można łatwo tworzyć skrypty automatyzujące zadania operatora oraz integrować zewnętrzne usługi z federacją.

## JSONB Extension

Rozszerzenie JSONB to mechanizm PostgreSQL umożliwiający przechowywanie strukturalnych dokumentów JSON razem z indeksowaniem GIN i operatorami `@>`, `->>`.
SYLION v2 używa go do dynamicznych pól ontologii (poza `dedicated_columns`), co daje szybki dostęp i analizę bez sztywnego schematu.

## Circuit Breaker

Circuit breaker to wzorzec, który monitoruje zapytania do zewnętrznych serwisów (np. adapterów W11) i w razie błędów wyłącza kolejne żądania, aby zapobiec przeciążeniu.
W UI widzisz trzy stany: **CLOSED** (połączenie działa), **OPEN** (adapter wyłączony z powodu błędów), **HALF_OPEN** (próbna restauracja - sukces przełącza na CLOSED, kolejny błąd cofa do OPEN).

## Cost Ledger

Cost ledger to moduł śledzący koszty operacji w SYLION v2 - agregujący wydatki na poziomie modeli (Ollama, Codex, Anthropic), zapytań i komponentów.
Zgodnie z ADR-002 (multi-model routing) ledger jest źródłem prawdy dla decyzji routingu i progów kosztowych; raporty i alerty pomagają zarządzać budżetem.

## Federation Node

Węzeł federacji to instancja SYLION v2, która wymienia konfigurację i metadane z innymi węzłami przez podpisany kanał (heartbeat + manifest sync).
Każdy węzeł odpowiada za synchronizację stanu i rozproszone przetwarzanie zapytań - zmniejszenie liczby węzłów obniża odporność na awarie.

## Routing Decision

Decyzja routingu to wybór modelu (lokalny Ollama vs. zdalny) podejmowany dla każdego zapytania zgodnie z macierzą ADR-002.
Wysoki współczynnik decyzji świadczy o aktywności ruchu; brak decyzji (zero) sugeruje brak zapytań lub problem z rozgłaszaniem.

## Powiązane

- **Tooltips** - `tooltips.md`
- **FAQ** - `FAQ.md`
- **ADR-001** - manifesty, parking W19
- **ADR-002** - macierz routingu modeli
