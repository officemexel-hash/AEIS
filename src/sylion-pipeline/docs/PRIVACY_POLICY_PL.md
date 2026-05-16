# Polityka Prywatności — SYLION Pipeline

**Wersja:** 1.0 (draft — do weryfikacji prawnej przed dystrybucją)  
**Data:** 2026-04-19  
**Produkt:** SYLION v5.9.0 — lokalny pipeline AI  
**Kontakt:** support@sylion.example

> **NOTA:** Ten dokument to Polityka Prywatności skierowana do użytkowników systemu  
> (art.13 RODO — obowiązek informacyjny). Jest odrębna od Rejestru Czynności Przetwarzania  
> (RoPA, art.30 RODO) zawartego w `docs/RODO_COMPLIANCE.md`.

---

## 1. Administrator Danych Osobowych

Administratorem Twoich danych osobowych jest:

```
[IMIĘ I NAZWISKO / NAZWA ORGANIZACJI]
[ADRES]
[KRS/NIP lub odpowiednik]
E-mail: support@sylion.example
```

*(Uzupełnij powyższe przed dystrybucją.)*

---

## 2. Czym jest SYLION?

SYLION to **lokalny pipeline AI** do audytu kodu i analizy. System działa wyłącznie na Twoim urządzeniu (localhost). Dane procesowane przez SYLION **nie są automatycznie wysyłane do zewnętrznych serwerów**, z wyjątkiem treści promptów kierowanych do zewnętrznych modeli AI (patrz sekcja 5).

---

## 3. Jakie dane osobowe przetwarza SYLION?

### 3.1 Dane operatorów dashboardu (użytkowników systemu)

| Kategoria danych | Przykłady | Podstawa prawna |
|-----------------|-----------|-----------------|
| Dane konta | Nazwa użytkownika (login), skrót hasła (argon2id) | Art.6 ust.1 lit.f RODO (uzasadniony interes — bezpieczeństwo systemu) |
| Dane sesji | Identyfikator sesji, czas logowania, czas wygaśnięcia, rola RBAC | Art.6 ust.1 lit.f RODO |
| Dziennik zdarzeń (audit log) | Nazwa użytkownika, typ akcji, czas, identyfikator obiektu | Art.6 ust.1 lit.f RODO (bezpieczeństwo, ochrona przed nadużyciami) |

### 3.2 Treści przekazywane do systemu (prompty i dokumenty)

| Kategoria danych | Przykłady | Podstawa prawna |
|-----------------|-----------|-----------------|
| Treść promptów | Kod źródłowy, pytania, dokumenty przekazane do analizy | Art.6 ust.1 lit.f RODO |
| Wyniki pipeline | Raporty, analizy wygenerowane przez agentów AI | Art.6 ust.1 lit.f RODO |

> **Ważne:** SYLION **nie prosi o podawanie danych osobowych** w promptach. Jeśli Twoje zapytania zawierają dane osobowe osób trzecich, to Ty jesteś odpowiedzialny za zgodność takiego przetwarzania z RODO.

### 3.3 Dane konfiguracyjne

| Kategoria danych | Przykłady | Podstawa prawna |
|-----------------|-----------|-----------------|
| Klucze API | Klucze do zewnętrznych serwisów AI (OpenAI, Anthropic, Google, Perplexity) | Art.6 ust.1 lit.f RODO (operacyjność systemu) |

---

## 4. Jak długo przechowujemy dane?

| Typ danych | Okres retencji | Mechanizm |
|-----------|----------------|-----------|
| Konto użytkownika | Do ręcznego usunięcia przez administratora | Endpoint DELETE /api/users/{id} |
| Sesje RBAC | 30 dni od wygaśnięcia (domyślnie; konfigurowalny) | Automatyczny prune codzienny |
| Audit log | 365 dni (domyślnie; konfigurowalny) | Automatyczny prune codzienny |
| Zdarzenia operacyjne (event_stream) | 7 dni (stałe) | Automatyczny prune codzienny |
| Wyniki pipeline (runs, artifacts) | Do ręcznego usunięcia | Brak automatycznego prune |
| Kopie zapasowe bazy danych | [Uzupełnij — zalecane: 90 dni] | [Uzupełnij] |

Uzasadnienie retencji 365 dni dla audit log: bezpieczeństwo systemu, wykrywanie anomalii, forensics (NIST SP 800-92), obrona roszczeń (art.17 ust.3 lit.e RODO).

---

## 5. Przekazywanie danych do zewnętrznych dostawców AI

SYLION komunikuje się z zewnętrznymi modelami AI:

| Dostawca | Kraj | Cel | Mechanizm ochrony |
|----------|------|-----|-------------------|
| OpenAI | USA | Generowanie odpowiedzi przez GPT | EU-US Data Privacy Framework (DPF) + Data Processing Agreement |
| Anthropic | USA | Generowanie odpowiedzi przez Claude | Standard Contractual Clauses (SCC Module 2, 2021) + DPA |
| Google AI | USA/EU | Generowanie odpowiedzi przez Gemini | EU-US DPF + DPA |
| Perplexity | USA | Wyszukiwanie AI | SCC Module 2 + DPA |

> **Uwaga:** Przed wdrożeniem produkcyjnym upewnij się, że zawarto umowy DPA z powyższymi dostawcami. Treść promptów wysyłanych do zewnętrznych API może być tam przetwarzana zgodnie z ich własnymi politykami prywatności.

**Zalecenie:** Nie umieszczaj w promptach danych osobowych osób trzecich.

---

## 6. Lokalizacja danych

Wszystkie dane SYLION przechowywane są **lokalnie** na Twoim urządzeniu:

```
Baza danych:    ~/sylion/sylion.db  (SQLite)
Kopie zapasowe: ~/sylion/sylion.db.bak.*.sqlite3
Logi:           [konfigurowalny]
```

Dane **nie są** automatycznie przesyłane na zewnętrzne serwery przez samą aplikację SYLION (z wyjątkiem promptów wysyłanych do zewnętrznych API AI, patrz sekcja 5).

---

## 7. Twoje prawa jako podmiotu danych

Przysługują Ci następujące prawa wynikające z RODO:

| Prawo | Artykuł RODO | Jak skorzystać |
|-------|-------------|----------------|
| Prawo dostępu | Art.15 | E-mail na adres administratora; odpowiedź w 30 dni |
| Prawo do sprostowania | Art.16 | E-mail do administratora |
| Prawo do usunięcia | Art.17 | E-mail do administratora; w systemie: DELETE /api/users/{id} |
| Prawo do ograniczenia przetwarzania | Art.18 | E-mail do administratora |
| Prawo do przenoszenia danych | Art.20 | Eksport JSON przez API (endpoint w przygotowaniu) |
| Prawo sprzeciwu | Art.21 | E-mail do administratora |

**Kontakt DSR:** support@sylion.example  
**Termin odpowiedzi:** 30 dni kalendarzowych (możliwe przedłużenie o 60 dni przy skomplikowanych żądaniach, z poinformowaniem wnioskodawcy).

---

## 8. Bezpieczeństwo danych

SYLION stosuje następujące środki bezpieczeństwa:

- **Hashing haseł:** algorytm argon2id (NIST-compliant) jako podstawowy; bcrypt jako fallback.
- **Kontrola dostępu:** RBAC (Role-Based Access Control) z rolami: owner, admin, member.
- **Audit log:** każda akcja jest logowana z timestampem i nazwą aktora.
- **WAL-safe backup:** kopie zapasowe przed migracjami bazy danych.
- **Rate limiting:** ograniczenie prób logowania (FIX-01, SYLION v5.9.0).
- **Human-gate:** decyzje AI wymagają zatwierdzenia przez człowieka (AI Act art.14).

**Znane ograniczenia (środowisko dev):**
- Baza danych SQLite nie jest szyfrowana (plaintext). W środowisku produkcyjnym zalecane szyfrowanie at-rest.
- Kopie zapasowe nie są szyfrowane. W środowisku produkcyjnym zalecane szyfrowanie backupów.

---

## 9. Pliki cookie i śledzenie

SYLION jest aplikacją lokalną i **nie używa plików cookie** w tradycyjnym sensie. Sesje użytkownika są zarządzane przez JWT lub tokeny sesji przechowywane lokalnie w bazie SQLite, a nie w cookie przeglądarki.

---

## 10. Dzieci

SYLION jest narzędziem deweloperskim przeznaczonym dla profesjonalistów. Nie jest skierowany do osób poniżej 16. roku życia i nie zbiera świadomie danych od osób niepełnoletnich.

---

## 11. Zmiany w Polityce Prywatności

W przypadku istotnych zmian w sposobie przetwarzania danych, niniejsza Polityka zostanie zaktualizowana. Zalecamy regularne sprawdzanie pliku `PRIVACY_POLICY_PL.md` w repozytorium projektu.

---

## 12. Kontakt i organ nadzorczy

**Administrator:** support@sylion.example

**Prawo do skargi:** Jeśli uważasz, że przetwarzanie Twoich danych narusza RODO, masz prawo wnieść skargę do organu nadzorczego:

- **Polska:** Urząd Ochrony Danych Osobowych (UODO)  
  ul. Stawki 2, 00-193 Warszawa  
  Tel.: +48 22 531 03 00  
  https://uodo.gov.pl

- **Niemcy (federalny):** Der Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI)  
  https://www.bfdi.bund.de

---

*Polityka Prywatności v1.0 | SYLION v5.9.0 | Draft — wymaga weryfikacji prawnej przed dystrybucją komercyjną.*  
*Opracowanie: Legal Re-Audit Council, 2026-04-19.*
