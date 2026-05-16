# Polityka Prywatności — SYLION Pipeline

**Wersja dokumentu:** v5.9.1  
**Data wydania:** 2026-04-19  
**Ostatnia aktualizacja:** 2026-04-19  
**Produkt:** SYLION v5.9.1 — lokalny pipeline AI  
**Kontakt:** support@sylion.example

> **NOTA:** Ten dokument to Polityka Prywatności skierowana do użytkowników systemu  
> (art. 13 RODO — obowiązek informacyjny). Jest odrębna od Rejestru Czynności Przetwarzania  
> (RoPA, art. 30 RODO) zawartego w `docs/RODO_COMPLIANCE.md`.
>
> **PLACEHOLDER — PRZED DYSTRYBUCJĄ:** Zastąp wszystkie znaczniki `{{…}}` faktycznymi danymi  
> podmiotu. Patrz Instrukcja Wypełnienia na końcu dokumentu.

---

## 1. Administrator Danych Osobowych

Administratorem Twoich danych osobowych jest:

```
{{COMPANY_NAME_PL}}
{{ADDRESS_PL}}
{{KRS_NIP_PL}}
E-mail: {{CONTACT_EMAIL_PL}}
```

*(Uzupełnij wszystkie pola `{{…}}` przed dystrybucją — Art. 13 ust. 1 lit. a RODO.)*

---

## 2. Czym jest SYLION?

SYLION to **lokalny pipeline AI** do audytu kodu i analizy. System działa wyłącznie na urządzeniu operatora (localhost). Dane procesowane przez SYLION **nie są automatycznie wysyłane do zewnętrznych serwerów**, z wyjątkiem treści promptów kierowanych do zewnętrznych modeli AI (patrz § 5).

---

## 3. Jakie dane osobowe przetwarza SYLION?

### 3.1 Dane operatorów dashboardu (użytkowników systemu)

| Kategoria danych | Przykłady | Podstawa prawna |
|-----------------|-----------|-----------------|
| Dane konta | Nazwa użytkownika (login), skrót hasła (argon2id) | Art. 6 ust. 1 lit. f RODO (uzasadniony interes — bezpieczeństwo systemu) |
| Dane sesji | Identyfikator sesji, czas logowania, czas wygaśnięcia, rola RBAC | Art. 6 ust. 1 lit. f RODO |
| Dziennik zdarzeń (audit log) | Nazwa użytkownika, typ akcji, czas, identyfikator obiektu | Art. 6 ust. 1 lit. f RODO (bezpieczeństwo, ochrona przed nadużyciami) |
| Dziennik kosztów AI (cost_log) | user_id, model AI, liczba tokenów, koszt jednostkowy, timestamp | Art. 6 ust. 1 lit. f RODO (zarządzanie zasobami; obrona roszczeń finansowych) |

### 3.2 Treści przekazywane do systemu (prompty i dokumenty)

| Kategoria danych | Przykłady | Podstawa prawna |
|-----------------|-----------|-----------------|
| Treść promptów | Kod źródłowy, pytania, dokumenty przekazane do analizy | Art. 6 ust. 1 lit. f RODO |
| Wyniki pipeline | Raporty, analizy wygenerowane przez agentów AI | Art. 6 ust. 1 lit. f RODO |

> **Ważne:** SYLION **nie prosi o podawanie danych osobowych** w promptach. Jeśli Twoje zapytania zawierają dane osobowe osób trzecich, to Ty jesteś odpowiedzialny za zgodność takiego przetwarzania z RODO.

### 3.3 Dane konfiguracyjne

| Kategoria danych | Przykłady | Podstawa prawna |
|-----------------|-----------|-----------------|
| Klucze API | Klucze do zewnętrznych serwisów AI (OpenAI, Anthropic, Google, Perplexity, xAI, DeepSeek) | Art. 6 ust. 1 lit. f RODO (operacyjność systemu) |

---

## 4. Jak długo przechowujemy dane?

| Typ danych | Okres retencji | Mechanizm |
|-----------|----------------|-----------|
| Konto użytkownika | Do ręcznego usunięcia; miękkie usunięcie + twarde usunięcie po 30 dniach | Endpoint DELETE /api/auth/me/data; purge_soft_deleted_users() |
| Sesje RBAC | 30 dni od wygaśnięcia (domyślnie; konfigurowalny) | Automatyczny prune codzienny — retention_cleaner.py |
| Audit log | 365 dni (domyślnie; konfigurowalny) | Automatyczny prune codzienny — retention_cleaner.py |
| Zdarzenia operacyjne (event_stream) | 7 dni (stałe) | Automatyczny prune codzienny |
| Historia przesyłania (upload_history) | 90 dni (domyślnie; konfigurowalny via UPLOAD_HISTORY_RETENTION_DAYS) | retention_cleaner.py (v5.9.1) |
| Wyniki pipeline (runs, artifacts) | Do ręcznego usunięcia | Brak automatycznego prune (planowane) |
| **Dziennik kosztów AI (cost_log)** | **90 dni** (art. 5 ust. 1 lit. e RODO — minimalizacja danych) | retention_cleaner.py — prune_cost_log() |
| Kopie zapasowe bazy danych | 90 dni (zalecane) | Harmonogram backupów — do konfiguracji przez operatora |

**Uzasadnienie retencji:**
- **Audit log 365 dni:** bezpieczeństwo systemu, wykrywanie anomalii, forensics (NIST SP 800-92), obrona roszczeń (art. 17 ust. 3 lit. e RODO).
- **cost_log 90 dni:** minimalizacja danych zgodnie z art. 5 ust. 1 lit. e RODO; wystarczający okres dla rozliczeń i obrony roszczeń finansowych.

---

## 5. Przekazywanie danych do zewnętrznych dostawców AI (sub-procesorzy)

SYLION komunikuje się z zewnętrznymi modelami AI. Poniżej lista aktualnych sub-procesorów (aktywnych i skonfigurowanych jako opcjonalni):

| Dostawca | Siedziba | Cel | Mechanizm ochrony transferu | Status |
|----------|---------|-----|----------------------------|--------|
| OpenAI, Inc. | USA | Generowanie odpowiedzi przez GPT | EU-US Data Privacy Framework (DPF) + Data Processing Agreement | Aktywny |
| Anthropic, PBC | USA | Generowanie odpowiedzi przez Claude | Standard Contractual Clauses (SCC Moduł 2, 2021/914) + DPA | Aktywny |
| Google LLC | USA/UE | Generowanie odpowiedzi przez Gemini | EU-US DPF + DPA | Aktywny |
| Perplexity AI, Inc. | USA | Wyszukiwanie wspomagane AI | SCC Moduł 2 (2021/914) + DPA | Aktywny |
| **DeepSeek AI Co., Ltd.** | **Chiny (PRC)** | **Generowanie odpowiedzi przez DeepSeek-R1/V3** | **BRAK decyzji adekwatności (art. 45 RODO); Transfer Impact Assessment (TIA) w toku; SCC Moduł 2 — w negocjacji** | **Opcjonalny — nieaktywny w środowisku produkcyjnym do zakończenia TIA** |
| **xAI, Inc.** | **USA** | **Generowanie odpowiedzi przez Grok** | **Standard Contractual Clauses (SCC Moduł 2, 2021/914) + DPA — w weryfikacji** | **Opcjonalny — nieaktywny do weryfikacji DPA** |

> **⚠ Ostrzeżenie — DeepSeek (Chiny):** Chińska Republika Ludowa nie posiada decyzji adekwatności Komisji Europejskiej (art. 45 RODO). Przekazywanie danych osobowych do DeepSeek AI Co., Ltd. wymaga zastosowania odpowiednich zabezpieczeń (art. 46 RODO), w szczególności SCC Moduł 2 oraz wykonanego TIA. Do czasu zakończenia TIA i podpisania SCC **zakazuje się aktywacji DeepSeek w trybie przetwarzania danych osobowych**.

> **Ostrzeżenie — Schrems II:** Każdy transfer danych do USA wymaga oceny TIA zgodnie z Wytycznymi EROD 05/2021. OpenAI, Google i Perplexity są certyfikowane w ramach EU-US DPF; Anthropic stosuje SCC M2 jako podstawę.

> **Zalecenie:** Nie umieszczaj w promptach danych osobowych osób trzecich.

---

## 6. Lokalizacja danych

Wszystkie dane SYLION przechowywane są **lokalnie** na urządzeniu operatora:

```
Baza danych:    ~/sylion/sylion.db  (SQLite)
Kopie zapasowe: ~/sylion/sylion.db.bak.*.sqlite3
Logi:           [konfigurowalny katalog]
```

Dane **nie są** automatycznie przesyłane na zewnętrzne serwery przez samą aplikację SYLION, z wyjątkiem treści promptów wysyłanych do zewnętrznych API AI (§ 5).

---

## 7. Twoje prawa jako podmiotu danych

Przysługują Ci następujące prawa wynikające z RODO:

| Prawo | Artykuł RODO | Jak skorzystać |
|-------|-------------|----------------|
| Prawo dostępu | Art. 15 | E-mail na adres administratora; odpowiedź w 30 dni; eksport danych: GET /api/auth/me/export |
| Prawo do sprostowania | Art. 16 | E-mail do administratora |
| Prawo do usunięcia | Art. 17 | E-mail do administratora; w systemie: DELETE /api/auth/me/data |
| Prawo do ograniczenia przetwarzania | Art. 18 | E-mail do administratora |
| Prawo do przenoszenia danych | Art. 20 | Eksport JSON przez API: GET /api/auth/me/export (dostępny od v5.9.1) |
| Prawo sprzeciwu | Art. 21 | E-mail do administratora |

**Kontakt DSR:** {{CONTACT_EMAIL_PL}}  
**Termin odpowiedzi:** 30 dni kalendarzowych (możliwe przedłużenie o 60 dni przy skomplikowanych żądaniach — art. 12 ust. 3 RODO; wnioskodawca jest informowany przed upływem 30 dni).

---

## 8. Bezpieczeństwo danych

SYLION stosuje następujące środki bezpieczeństwa zgodnie z art. 32 RODO:

- **Hashing haseł:** algorytm argon2id (NIST-compliant) jako podstawowy; bcrypt jako fallback.
- **Kontrola dostępu:** RBAC (Role-Based Access Control) z rolami: owner, admin, member.
- **Audit log:** każda akcja jest logowana z timestampem i nazwą aktora.
- **WAL-safe backup:** kopie zapasowe przed migracjami bazy danych.
- **Rate limiting:** ograniczenie prób logowania (FIX-01, SYLION v5.9.0).
- **Human-gate:** decyzje AI wymagają zatwierdzenia przez człowieka (art. 14 Rozporządzenia UE 2024/1689 — AI Act).
- **Cookies sesji:** HttpOnly, Secure, SameSite=Strict (patrz § 9).

**Znane ograniczenia (środowisko dev):**
- Baza danych SQLite nie jest szyfrowana (plaintext). W środowisku produkcyjnym zalecane szyfrowanie at-rest (SQLCipher lub odpowiednik).
- Kopie zapasowe nie są szyfrowane. W środowisku produkcyjnym zalecane szyfrowanie backupów.

---

## 9. Pliki cookie i mechanizm wycofania zgody

SYLION używa **wyłącznie niezbędnych plików cookie** do zarządzania sesją użytkownika. Nie używamy plików cookie analitycznych, reklamowych ani śledzących.

| Nazwa cookie | Typ | Cel | Czas życia | Atrybuty bezpieczeństwa |
|-------------|-----|-----|------------|------------------------|
| `sylion_session` | Niezbędny (sesja) | Identyfikacja zalogowanej sesji użytkownika; zarządzanie RBAC | 24 godziny | HttpOnly, Secure, SameSite=Strict |
| `_csrf_token` | Niezbędny (bezpieczeństwo) | Ochrona przed atakami Cross-Site Request Forgery (CSRF) | 30 minut | Secure, SameSite=Strict |

**Podstawa prawna:** Art. 6 ust. 1 lit. b RODO (niezbędność do wykonania umowy / świadczenia usługi) — zgoda użytkownika nie jest wymagana dla cookies niezbędnych.

**Wycofanie zgody / wylogowanie:** Ponieważ są to cookies niezbędne do działania usługi, ich usunięcie jest równoznaczne z wylogowaniem. Możesz:
- Wylogować się przez interfejs SYLION (usuwa cookie sesji),
- Ręcznie usunąć cookies w ustawieniach przeglądarki,
- Zamknąć przeglądarkę (sesja wygasa po 24h niezależnie).

---

## 10. Dzieci

SYLION jest narzędziem deweloperskim przeznaczonym wyłącznie dla profesjonalistów. Nie jest skierowany do osób poniżej 16. roku życia i nie zbiera świadomie danych od osób niepełnoletnich.

---

## 11. Zmiany w Polityce Prywatności

W przypadku istotnych zmian w sposobie przetwarzania danych, niniejsza Polityka zostanie zaktualizowana, a data „Ostatnia aktualizacja" zmieniona. Użytkownicy zostaną poinformowani o zmianach przez interfejs systemu lub e-mail. Zalecamy regularne sprawdzanie pliku `PP_v591_PL.md` w repozytorium projektu.

---

## 12. Kontakt i organ nadzorczy

**Administrator:** {{CONTACT_EMAIL_PL}}

**Prawo do skargi:** Jeśli uważasz, że przetwarzanie Twoich danych narusza RODO, masz prawo wnieść skargę do organu nadzorczego:

- **Polska:** Urząd Ochrony Danych Osobowych (UODO)  
  ul. Stawki 2, 00-193 Warszawa  
  Tel.: +48 22 531 03 00  
  https://uodo.gov.pl

- **Niemcy (federalny):** Der Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI)  
  https://www.bfdi.bund.de

---

## Instrukcja Wypełnienia Placeholderów

> Przed dystrybucją zastąp poniższe znaczniki faktycznymi danymi. Usuń tę sekcję po wypełnieniu.

| Placeholder | Opis | Przykład |
|-------------|------|---------|
| `{{COMPANY_NAME_PL}}` | Pełna nazwa firmy lub imię i nazwisko administratora | SYLION sp. z o.o. |
| `{{ADDRESS_PL}}` | Adres siedziby (ulica, kod, miasto) | ul. Przykładowa 1, 00-001 Warszawa |
| `{{KRS_NIP_PL}}` | Numer KRS (spółka) lub NIP (osoba fizyczna prowadząca działalność) | KRS: 0000000000, NIP: 1234567890 |
| `{{CONTACT_EMAIL_PL}}` | Adres e-mail do kontaktu RODO/DSR | rodo@sylion.pl |

---

*Polityka Prywatności v5.9.1 | SYLION v5.9.1 | Final Draft — wymaga weryfikacji prawnej przed dystrybucją komercyjną.*  
*Opracowanie: Legal Re-Audit Council, 2026-04-19.*  
*Zastąpiono v1.0 (SYLION v5.9.0): zaktualizowano §5 (DeepSeek, xAI), §9 (cookies), §4 (cost_log retencja), schemat wersjonowania.*
