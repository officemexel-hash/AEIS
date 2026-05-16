# Co nowego w SYLION v5.9.0

**Data wydania:** 2026-04-19  
**Typ wersji:** Minor release z poprawkami błędów i nowymi skillami

---

## Co nowego?

### Council 4 modeli — tryb równoległy

Cztery modele AI (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) teraz zawsze działają równolegle, a nie sekwencyjnie. Czas odpowiedzi skrócił się o ok. 60% przy tym samym poziomie jakości analizy.

### Nowy panel agentów

Zakładka **Agenci** w Dashboard pokazuje teraz:

- stan każdego z 48 agentów w czasie rzeczywistym
- czas ostatniego uruchomienia
- statystyki (liczba uruchomień, średni czas, współczynnik sukcesu)

### Human gate z edycją inline

Przy zatwierdzaniu etapu (stage) z human gate możesz teraz edytować wynik agenta bezpośrednio w panelu zatwierdzania, zamiast odrzucać i uruchamiać od nowa.

### Eksport raportów do HTML

Do dotychczasowych formatów (JSON, Markdown) doszedł eksport do HTML ze stylami — raport jest gotowy do udostępnienia bez dodatkowego formatowania.

### Tryb WAL — automatyczna konfiguracja

SYLION automatycznie ustawia tryb WAL przy tworzeniu nowej bazy danych. Nie wymaga ręcznej konfiguracji.

### Zapis stanu council między sesjami

Kontekst rozmowy z council jest teraz zapisywany w bazie i dostępny po restarcie serwera. Możesz kontynuować poprzednią sesję bez utraty historii.

---

## Co zostało naprawione? (11 poprawek)

1. **Błąd przy długich promptach** — pipeline zawieszał się przy zapytaniach powyżej 8 000 tokenów. Teraz automatycznie dzieli duże dane wejściowe na fragmenty.

2. **Rate limiter blokował lokalny adres IP** — przy teście z localhost wyzwalał się limit. Naprawione — localhost i 127.0.0.1 są wykluczone z rate limitera.

3. **Nieprawidłowe kodowanie znaków w raportach** — polskie litery (ą, ę, ś, ź itp.) czasem pojawiały się jako znaki zastępcze przy eksporcie do Markdown. Naprawione, wszystkie raporty są teraz w UTF-8.

4. **Agent "security_scan" ignorował pliki .env** — skaner bezpieczeństwa pomijał pliki konfiguracyjne. Teraz skanuje wszystkie pliki w projekcie, włącznie z ukrytymi.

5. **Błąd 500 po wygaśnięciu sesji** — zamiast przekierowania na stronę logowania, serwer zwracał błąd wewnętrzny. Naprawione — sesja wygasła = przekierowanie na /login.

6. **Council timeout nie był respektowany** — wartość `COUNCIL_TIMEOUT_SECONDS` z `.env` była ignorowana. Teraz jest poprawnie odczytywana przy starcie serwera.

7. **Zduplikowane wpisy w historii pipeline'ów** — przy restarcie serwera podczas działającego pipeline'u pojawiały się duplikaty w liście. Naprawione przez atomowe zapisy statusu.

8. **Human gate nie zapisywał decyzji do bazy** — decyzje "Zatwierdź/Odrzuć" były logowane tylko w pamięci. Po restarcie historię tracono. Teraz zapisywane trwale.

9. **Błąd importu na Windows przy ścieżkach z polskimi znakami** — katalog projektu z polską nazwą (np. `Pulpit`) powodował błąd importu modułów. Naprawione przez normalizację ścieżek.

10. **Panel agentów nie odświeżał się automatycznie** — żeby zobaczyć aktualny stan agenta, trzeba było ręcznie odświeżyć stronę. Teraz działa automatyczne odświeżanie co 5 sekund (WebSocket).

11. **Błąd przy pustej odpowiedzi Gemini** — jeśli Gemini 3.1 Pro zwrócił pustą odpowiedź (np. przy filtrowaniu treści), council rzucał wyjątek. Teraz taka odpowiedź jest obsługiwana gracefully, z komunikatem w raporcie.

---

## Upgrade z v5.8.x

Aktualizacja z v5.8.x do v5.9.0 wymaga migracji bazy danych. SYLION wykonuje ją automatycznie przy pierwszym uruchomieniu nowej wersji.

Przed aktualizacją:

```bash
# Zrób ręczny backup
cp ~/sylion/sylion.db ~/backup/sylion_pre_v590.db
```

Następnie:

```bash
git pull origin main
./install.sh
python -m sylion migrate
python -m sylion serve
```

Szczegółowy przewodnik migracji: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md).

---

## Nowe skille audytowe (18 skilli)

W tej wersji dodano 18 nowych skilli do zestawu agentów audytowych:

| Skill | Opis |
|-------|------|
| `sql_injection_scan` | Wykrywa podatności SQL injection w kodzie |
| `secret_leak_detect` | Szuka kluczy API i haseł w kodzie źródłowym |
| `dependency_audit` | Sprawdza znane CVE w zależnościach (npm, pip) |
| `license_compliance` | Weryfikuje zgodność licencji bibliotek |
| `dead_code_finder` | Identyfikuje nieużywany kod |
| `complexity_score` | Oblicza cyklomatyczną złożoność funkcji |
| `test_coverage_check` | Sprawdza pokrycie kodu testami |
| `doc_completeness` | Ocenia kompletność dokumentacji (docstringi, README) |
| `api_contract_lint` | Weryfikuje zgodność kodu z definicją OpenAPI |
| `type_hint_audit` | Sprawdza obecność i poprawność type hintów (Python) |
| `env_variable_check` | Wykrywa hardcoded wartości, które powinny być w .env |
| `async_pattern_review` | Sprawdza poprawność użycia async/await |
| `error_handling_audit` | Ocenia jakość obsługi wyjątków |
| `logging_consistency` | Weryfikuje spójność logowania w projekcie |
| `migration_safety_check` | Sprawdza bezpieczeństwo migracji baz danych |
| `performance_hotspot` | Identyfikuje potencjalne bottlenecki wydajności |
| `accessibility_lint` | Sprawdza dostępność w projektach frontendowych (WCAG) |
| `dockerfile_audit` | Analizuje bezpieczeństwo i optymalizację Dockerfile |

Skille są automatycznie dostępne po aktualizacji — brak konfiguracji wymagana.
