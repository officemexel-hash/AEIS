# RODO Compliance — SYLION v5.9.0
## Rejestr Czynności Przetwarzania (RoPA) + Procedury Praw Podmiotów Danych

> **Dokument:** Rejestr Czynności Przetwarzania (Art. 30 RODO / Art. 30 DSGVO)  
> **Wersja:** 1.0.0 (zgodna z SYLION v5.9.0)  
> **Data utworzenia:** 2025-07-10  
> **Ostatnia aktualizacja:** 2025-07-10  
> **Weryfikacja:** Co 12 miesięcy lub przy każdej zmianie czynności przetwarzania  
> **Podstawa prawna dokumentu:** RODO art.30 / DSGVO Art.30 / BDSG §70  

---

## SPIS TREŚCI

1. [Dane Administratora](#1-dane-administratora)
2. [Rejestr Czynności Przetwarzania](#2-rejestr-czynności-przetwarzania)
3. [Harmonogram Retencji Danych](#3-harmonogram-retencji-danych)
4. [Procedury Praw Podmiotów Danych](#4-procedury-praw-podmiotów-danych)
5. [Środki Bezpieczeństwa (Art. 32 RODO)](#5-środki-bezpieczeństwa-art-32-rodo)
6. [Transfery Międzynarodowe](#6-transfery-międzynarodowe)
7. [Podmioty Przetwarzające (Procesorzy)](#7-podmioty-przetwarzające-procesorzy)
8. [Ocena Skutków dla Ochrony Danych (DPIA)](#8-ocena-skutków-dla-ochrony-danych-dpia)
9. [AI Act — Dokumentacja Systemu AI](#9-ai-act--dokumentacja-systemu-ai)
10. [Historia Zmian Dokumentu](#10-historia-zmian-dokumentu)

---

## 1. DANE ADMINISTRATORA

### Administrator Danych Osobowych

```
Nazwa organizacji:    [NAZWA ORGANIZACJI]
Adres siedziby:       [ADRES]
KRS/NIP (PL):         [NUMER]
Handelsregisternr (DE): [NUMER]
E-mail kontaktowy:    [EMAIL]
Telefon:              [TELEFON]
```

### Inspektor Ochrony Danych (IOD / DSB)

> **NOTA:** Obowiązek wyznaczenia IOD (art.37 RODO / §38 BDSG) ocenić na podstawie:  
> - Systematyczne przetwarzanie na dużą skalę: [TAK/NIE]  
> - Dane wrażliwe (art.9): [TAK/NIE]  
> - Organy/podmioty publiczne: [TAK/NIE]  
> - Niemcy: ≥20 stale zatrudnionych przetwarzających automatycznie: [TAK/NIE]

```
IOD/DSB:              [IMIĘ I NAZWISKO lub N/A]
E-mail IOD:           [EMAIL lub N/A]
Status obowiązku:     [OBOWIĄZKOWY / DOBROWOLNY / N/A]
```

### Współadministratorzy / Przedstawiciel w EU

```
Współadministrator:   [BRAK / NAZWA]
Przedstawiciel EU:    [BRAK / NAZWA — wymagany jeśli podmiot spoza EU]
```

---

## 2. REJESTR CZYNNOŚCI PRZETWARZANIA

### Czynność PA-01: Uwierzytelnianie i Zarządzanie Sesjami RBAC

| Pole | Wartość |
|------|---------|
| **Nazwa czynności** | Logowanie użytkowników do dashboardu SYLION; zarządzanie sesjami RBAC |
| **Cel przetwarzania** | Weryfikacja tożsamości operatora; kontrola dostępu do funkcji systemu; bezpieczeństwo systemu |
| **Podstawa prawna (PL)** | Art.6 ust.1 lit.f RODO (prawnie uzasadniony interes — bezpieczeństwo systemu) |
| **Podstawa prawna (DE)** | Art.6 ust.1 lit.f DSGVO; §26 ust.1 BDSG (przetwarzanie w ramach stosunku pracy, jeśli dotyczy pracowników) |
| **Kategorie podmiotów danych** | Operatorzy dashboardu (pracownicy, kontraktorzy) |
| **Kategorie danych osobowych** | Nazwa użytkownika (login), hash hasła (argon2id/bcrypt), rola RBAC, ID sesji, czas logowania, czas wygaśnięcia sesji |
| **Dane wrażliwe (art.9)?** | NIE |
| **Odbiorcy danych** | Brak (dane wewnętrzne) |
| **Transfer poza EU?** | NIE |
| **Okres retencji** | Konto użytkownika: do usunięcia przez administratora; Sesje: 30 dni (SESSIONS_RETENTION_DAYS, konfigurowalny) |
| **Mechanizm retencji** | `prune_sessions()` — codziennie, batch 1000/tx, WAL-safe |
| **Środki bezpieczeństwa** | Hashing argon2id/bcrypt; RBAC role-based; audit_log każdej akcji; HTTPS (zalecane) |
| **Tabele DB** | `users`, `sessions` |
| **Lokalizacja danych** | SQLite — `/dashboard/sylion_dashboard.db` (lokalnie) |
| **DPIA wymagana?** | NIE (brak przetwarzania na dużą skalę, brak danych wrażliwych) |

---

### Czynność PA-02: Dziennik Zdarzeń Bezpieczeństwa (Audit Log)

| Pole | Wartość |
|------|---------|
| **Nazwa czynności** | Rejestrowanie akcji operatorów w audit_log |
| **Cel przetwarzania** | Bezpieczeństwo systemu; wykrywanie anomalii; forensics; odpowiedzialność operacyjna |
| **Podstawa prawna (PL)** | Art.6 ust.1 lit.f RODO (uzasadniony interes — bezpieczeństwo); art.6 ust.1 lit.c (obowiązek prawny — jeśli wymagany przepisami) |
| **Podstawa prawna (DE)** | Art.6 ust.1 lit.f DSGVO; §26 ust.1 BDSG (monitoring pracowniczy w uzasadnionym zakresie); informacja Betriebsrat (§87 BetrVG) jeśli dotyczy |
| **Kategorie podmiotów danych** | Operatorzy dashboardu |
| **Kategorie danych osobowych** | Nazwa aktora (username), typ zdarzenia, identyfikator obiektu, timestamp (Unix), adres IP (jeśli logowany) |
| **Dane wrażliwe (art.9)?** | NIE |
| **Odbiorcy danych** | Brak zewnętrznych; wewnętrznie: administrator systemu, właściciel (owner) |
| **Transfer poza EU?** | NIE |
| **Okres retencji** | 365 dni (AUDIT_LOG_RETENTION_DAYS, konfigurowalny) |
| **Uzasadnienie retencji 365 dni** | Bezpieczeństwo systemu wymaga analizy historycznej zdarzeń; UODO (PL) akceptuje roczną retencję logów bezpieczeństwa; odpowiada standardom NIST SP 800-92 |
| **Relacja do GoBD/HGB** | audit_log = dziennik techniczny, NIE dokument handlowy; GoBD (10 lat) NIE ma zastosowania |
| **Relacja do KSeF/JPK** | N/A — brak przetwarzania faktur VAT |
| **Mechanizm retencji** | `prune_audit_log()` — codziennie, batch 1000/tx, WAL-safe |
| **Tabele DB** | `audit_log` |
| **DPIA wymagana?** | NIE (wewnętrzny dziennik, uzasadniony cel bezpieczeństwa) |
| **Uwaga art.17.3** | Usunięcie konta operatora NIE powoduje usunięcia wpisów audit_log — podstawa: art.17 ust.3 lit.e (obrona roszczeń) + bezpieczeństwo; decyzja udokumentowana |

---

### Czynność PA-03: Konfiguracja Systemu i Klucze API

| Pole | Wartość |
|------|---------|
| **Nazwa czynności** | Przechowywanie kluczy API (OPENAI, ANTHROPIC, GOOGLE, PERPLEXITY) w konfiguracji |
| **Cel przetwarzania** | Integracja z zewnętrznymi modelami AI (OpenAI GPT, Anthropic Claude, Google Gemini) |
| **Podstawa prawna** | Art.6 ust.1 lit.f RODO (uzasadniony interes — operacyjność systemu) |
| **Kategorie danych** | Klucze API (techniczne dane dostępowe — nie są danymi osobowymi per se, ale wymagają ochrony art.32) |
| **Dane osobowe?** | Pośrednio (klucze identyfikują konto organizacji); pełne dane osobowe mogą być w treściach promptów |
| **Środki bezpieczeństwa** | `secret=1` w DB (ochrona UI); szyfrowanie wymagane (patrz CRIT-01 plan naprawczy) |
| **Transfer poza EU?** | TAK — patrz PA-04 i Sekcja 6 |
| **Tabele DB** | `config` (kolumna `secret=1`) |
| **⚠ DZIAŁANIE WYMAGANE** | Usunąć hardkodowane klucze z `db.py:_DEFAULT_API_KEYS`; używać zmiennych środowiskowych |

---

### Czynność PA-04: Wywołania Zewnętrznych API AI (Transfer do USA)

| Pole | Wartość |
|------|---------|
| **Nazwa czynności** | Przesyłanie promptów do zewnętrznych modeli AI (OpenAI, Anthropic, Google, Perplexity) |
| **Cel przetwarzania** | Generowanie wyników przez pipeline multi-agentowy |
| **Podstawa prawna** | Art.6 ust.1 lit.f RODO (uzasadniony interes — funkcjonalność systemu) |
| **Kategorie podmiotów danych** | Osoby, których dane mogą być zawarte w promptach (pośrednio) |
| **Kategorie danych osobowych** | Treść promptów (potencjalnie zawierające dane osobowe jeśli użytkownik wklei) |
| **Transfer poza EU?** | TAK — USA (OpenAI: San Francisco, Anthropic: San Francisco, Google: USA/EU zależnie od API) |
| **Mechanizm transferu** | EU-US Data Privacy Framework (DPF) dla OpenAI i Google (wymagana weryfikacja); SCC Module 2 (2021) dla Anthropic i Perplexity |
| **DPA status** | ⚠ DO PODPISANIA z każdym dostawcą (art.28 RODO) |
| **TIA wykonane?** | ⚠ NIE — wymagane po Schrems II |
| **Retencja po stronie dostawcy** | OpenAI: do 30 dni (API, nie trenuje na danych API); pozostałe: per DPA |
| **Środki minimalizacji** | Polityka zakazująca umieszczania danych osobowych w promptach (zalecane); pseudonimizacja przed wysłaniem (zalecane) |
| **DPIA wymagana?** | ROZWAŻYĆ — transfer masowy do państwa trzeciego + przetwarzanie dużej liczby promptów |

---

### Czynność PA-05: Zarządzanie Agentami AI (Multi-Agent Pipeline)

| Pole | Wartość |
|------|---------|
| **Nazwa czynności** | Orchestracja 48 agentów AI; zarządzanie zadaniami; human-gate |
| **Cel przetwarzania** | Automatyzacja zadań programistycznych i analitycznych; nadzór człowieka nad decyzjami AI |
| **Podstawa prawna** | Art.6 ust.1 lit.f RODO (uzasadniony interes — operacyjność systemu deweloperskiego) |
| **Dane osobowe?** | Pośrednio — treści zadań mogą zawierać dane osobowe |
| **Human-gate** | Tabela `human_gate` — decyzje wymagają zatwierdzenia człowieka (AI Act art.14) |
| **Event Stream** | Retencja 7 dni (`EVENT_STREAM_RETENTION_DAYS`) |
| **Tabele DB** | `agents`, `runs`, `run_artifacts`, `human_gate`, `event_stream` |
| **AI Act klasyfikacja** | Limited Risk / General Purpose — human-gate spełnia art.14 |

---

### Czynność PA-06: Kopie Zapasowe Bazy Danych (M-08)

| Pole | Wartość |
|------|---------|
| **Nazwa czynności** | Automatyczne backupy SQLite przed migracjami (WAL-safe) |
| **Cel przetwarzania** | Zapewnienie dostępności danych; ciągłość działania; możliwość przywrócenia |
| **Podstawa prawna** | Art.32 ust.1 lit.c RODO (zdolność do odtworzenia dostępu) |
| **Dane osobowe** | Wszystkie dane z tabel produkcyjnych (users, sessions, audit_log, config) |
| **Lokalizacja backup** | `~/sylion/sylion.db.bak.{version}.{date}.sqlite3` |
| **Retencja backupów** | ⚠ NIEOKREŚLONA — zalecane: 90 dni dla backupów, potem usunięcie |
| **Szyfrowanie backupów** | ⚠ BRAK — wymagane dla środowisk produkcyjnych |
| **Guard bezpieczeństwa** | F-04 (path traversal guard) — AKTYWNY |
| **⚠ DZIAŁANIE WYMAGANE** | Określić retencję backupów; dodać szyfrowanie; dodać SHA-256 checksum |

---

## 3. HARMONOGRAM RETENCJI DANYCH

### Tabela Retencji — Przegląd

| Tabela DB | Typ Danych | Retencja | Mechanizm | Podstawa | GoBD |
|-----------|-----------|---------|-----------|---------|------|
| `users` | Konta operatorów | Do usunięcia (manualne) | `DELETE /api/users/{id}` | Art.5.1.e | N/A |
| `sessions` | Sesje RBAC | **30 dni** (konfigurowalny) | `prune_sessions()` codziennie | Art.5.1.e | N/A |
| `audit_log` | Zdarzenia bezpieczeństwa | **365 dni** (konfigurowalny) | `prune_audit_log()` codziennie | Art.5.1.e + bezpieczeństwo | N/A — nie doc. handlowy |
| `event_stream` | Zdarzenia operacyjne | **7 dni** (stałe) | `prune_event_stream()` codziennie | Art.5.1.e | N/A |
| `config` | Konfiguracja + klucze API | Do manualnegousuniecia | Brak pruning | Art.32 | N/A |
| `agents` | Definicje agentów | Trwałe (operacyjne) | Manualne | N/A | N/A |
| `runs` | Wyniki pipeline | ⚠ NIEOKREŚLONA | Brak pruning | Do zdefiniowania | N/A |
| `run_artifacts` | Artefakty pipeline | ⚠ NIEOKREŚLONA | Brak pruning | Do zdefiniowania | N/A |
| `human_gate` | Decyzje gate | ⚠ NIEOKREŚLONA | Brak pruning | Do zdefiniowania | N/A |
| Backupy SQLite | Wszystkie dane | ⚠ NIEOKREŚLONA | Brak automatycznego usuwania | Art.32 | N/A |

### Parametry Konfiguracji Retencji (UI-edytowalne)

```
AUDIT_LOG_RETENTION_DAYS  = 365  # Retencja audit_log (dni). Min: 7, Max: 1825 (5 lat)
SESSIONS_RETENTION_DAYS   = 30   # Retencja wygasłych sesji RBAC (dni). Min: 1, Max: 365
EVENT_STREAM_RETENTION     = 7    # Stała (w kodzie) — zmiana wymaga release
```

### Uzasadnienie Retencji 365 dni (Audit Log)

Retencja 365 dni dla `audit_log` jest uzasadniona następującymi celami:
1. **Bezpieczeństwo systemu** — wykrywanie anomalii wymagające analizy historycznej wzorców (min. 90 dni zalecane przez NIST SP 800-92).
2. **Odpowiedzialność operacyjna** — możliwość dochodzenia roszczeń wewnętrznych (art.17 ust.3 lit.e RODO).
3. **Forensics** — analiza incydentów bezpieczeństwa (branżowy standard: 12 miesięcy).
4. **Zgodność z UODO** — urząd akceptuje roczną retencję logów bezpieczeństwa.

Podstawa prawna: art.6 ust.1 lit.f RODO (uzasadniony interes — bezpieczeństwo) + Balancing Test:
- Interes administratora: bezpieczeństwo > ryzyko dla podmiotów danych (dane techniczne, nie wrażliwe).
- Wynik: Balancing Test pozytywny.

### Zgodność GoBD / HGB

| Element | Status | Uzasadnienie |
|---------|--------|--------------|
| audit_log retencja 365 dni | ✅ ZGODNY | Dziennik techniczny ≠ dokument handlowy (HGB §257, AO §147) |
| Faktury/transakcje finansowe | N/A | System nie przetwarza faktur VAT |
| JPK/KSeF | N/A | Dev pipeline, nie produkt komercyjny |
| Bookkeeping records | N/A | Brak przetwarzania dokumentów handlowych |

---

## 4. PROCEDURY PRAW PODMIOTÓW DANYCH

### 4.1 Punkt Kontaktowy DSR

```
Email DSR:          [DSR@ORGANIZACJA.COM]
Formularz online:   [URL lub N/A]
Adres pocztowy:     [ADRES]
Termin odpowiedzi:  30 dni kalendarzowych (art.12 ust.3 RODO)
Możliwe przedłużenie: +60 dni (złożone wnioski — z poinformowaniem wnioskodawcy)
```

### 4.2 Procedura Weryfikacji Tożsamości

Przed realizacją DSR, tożsamość wnioskodawcy MUSI być zweryfikowana:

1. **Operatorzy systemu (users):** Potwierdzenie przez zalogowanie do dashboardu LUB e-mail z konta organizacyjnego.
2. **Zewnętrzne podmioty danych:** Kombinacja: imię/nazwisko + e-mail + dodatkowy dokument (skan dowodu, jeśli duże ryzyko fraudu).
3. **Wniosek od pełnomocnika:** Wymagane pełnomocnictwo pisemne.

### 4.3 Prawo Dostępu (Art. 15 RODO)

**SLA:** 30 dni od weryfikacji tożsamości.

**Procedura:**
1. Odebrać wniosek na DSR e-mail.
2. Zweryfikować tożsamość.
3. Uruchomić skrypt ekstrakcji danych:
   ```sql
   -- Dane konta
   SELECT id, username, role, created_at FROM users WHERE username = ?;
   -- Sesje
   SELECT id, created_at, expires_at FROM sessions WHERE user_id = ?;
   -- Audit log
   SELECT event, object_id, created_at FROM audit_log WHERE actor = ?;
   ```
4. Odpowiedzieć w formacie maszynowo czytelnym (JSON) lub czytelnym dla człowieka (PDF).
5. Zalogować odpowiedź w audit_log: `dsr.access_response`.

### 4.4 Prawo do Usunięcia (Art. 17 RODO / §35 BDSG)

**SLA:** 30 dni od weryfikacji tożsamości (RODO) / niezwłocznie po weryfikacji (BDSG §35 ust.6).

**Procedura:**
1. Odebrać wniosek.
2. Sprawdzić wyjątki (art.17 ust.3):
   - Obrona roszczeń prawnych (lit.e) — jeśli TAK: odmowa z uzasadnieniem pisemnym (BDSG §35 ust.5).
   - Obowiązek prawny retencji — jeśli TAK: odmowa z uzasadnieniem.
3. Jeśli brak wyjątków — wykonać:
   ```bash
   # Via API (owner token required)
   DELETE /api/users/{user_id}
   # Anonimizacja audit_log (nie kasowanie — cel bezpieczeństwa)
   UPDATE audit_log SET actor='[deleted]' WHERE actor = ?;
   ```
4. **Poinformowanie podmiotów którym dane przekazano** (BDSG §35 ust.4): powiadomić dostawców API jeśli dane użytkownika były przesyłane.
5. Potwierdzenie pisemne usunięcia (wymagane BDSG §35 ust.6, zalecane RODO).
6. Zalogować: `dsr.erasure_completed` lub `dsr.erasure_refused` w audit_log.

**Uwaga dot. audit_log:** Wpisy `audit_log` z `actor=<username>` NIE są kasowane — podstawa: art.17 ust.3 lit.e (obrona roszczeń + bezpieczeństwo). Zamiast kasowania: anonimizacja `actor` → `[deleted_YYYYMMDD]`. Decyzja udokumentowana w niniejszym RoPA.

### 4.5 Prawo do Sprostowania (Art. 16 RODO)

**SLA:** 30 dni.

**Procedura:**
1. Odebrać wniosek ze wskazaniem błędnych danych.
2. Wykonać: `PUT /api/users/{user_id}` (zmiana username/roli przez owner).
3. Zalogować: `dsr.rectification_completed`.

### 4.6 Prawo do Ograniczenia Przetwarzania (Art. 18 RODO)

**Procedura:**
1. Na czas rozpatrzenia wniosku: zablokować konto (`status='disabled'`) bez usuwania danych.
2. Zalogować: `dsr.restriction_applied`.

### 4.7 Prawo do Przenoszenia Danych (Art. 20 RODO)

**Dotyczy tylko:** danych dostarczonych przez podmiot na podstawie zgody lub umowy.  
**Format eksportu:** JSON (API: `GET /api/users/export/{user_id}`).  
**⚠ ENDPOINT DO IMPLEMENTACJI.**

### 4.8 Prawo Sprzeciwu (Art. 21 RODO)

Jeśli podstawa prawna to art.6 ust.1 lit.f (uzasadniony interes), podmiot danych ma prawo sprzeciwu. Administrator musi udowodnić nadrzędność swojego interesu lub zaprzestać przetwarzania.

### 4.9 Rejestry DSR

Wszystkie DSR muszą być rejestrowane:

| Pole | Opis |
|------|------|
| ID wniosku | UUID |
| Typ prawa | access/erasure/rectification/restriction/portability/objection |
| Data wpłynięcia | |
| Tożsamość zweryfikowana | TAK/NIE |
| Termin odpowiedzi | D+30 (lub D+90 jeśli przedłużenie) |
| Status | pending/completed/refused |
| Podstawa odmowy | art.17.3a/b/c/d/e/f lub N/A |
| Potwierdzenie wysłane | TAK/NIE + data |

---

## 5. ŚRODKI BEZPIECZEŃSTWA (ART. 32 RODO)

### 5.1 Środki Techniczne — Status

| Środek | Status | Szczegóły |
|--------|--------|-----------|
| Hashing haseł | ✅ WDROŻONE | argon2id (primary), bcrypt (fallback) — NIST-compliant |
| RBAC (Role-Based Access Control) | ✅ WDROŻONE | Role: owner, admin, member; granularne uprawnienia |
| Audit Log | ✅ WDROŻONE | Każda akcja logowana z actorem, timestampem |
| Retencja danych | ✅ WDROŻONE | Konfigurowalny prune (M-03) — sessions/audit_log |
| Backup WAL-safe | ✅ WDROŻONE | M-08 — przed migracjami, guard F-04 |
| API Keys `secret=1` | ✅ WDROŻONE | Ochrona wyświetlania w UI |
| SQLite WAL mode | ✅ WDROŻONE | Concurrent reads, crash recovery |
| Thread-safe init | ✅ WDROŻONE | `_db_init_lock` — serialize startup |
| **API Keys hardcoded** | ❌ WYMAGANA AKCJA | CRIT-01: usunąć `_DEFAULT_API_KEYS` z kodu |
| **Szyfrowanie at-rest** | ⚠ BRAK | SQLite plaintext — akceptowalne dla dev; wymagane dla prod |
| **Szyfrowanie backupów** | ⚠ BRAK | Backupy w plaintext — wymagane szyfrowanie |
| **HTTPS/TLS** | ⚠ WERYFIKACJA | Upewnić się że nginx/reverse proxy szyfruje połączenie |
| **Rate limiting login** | ⚠ BRAK | Dodać rate limit na `/api/auth/login` |
| **Szyfrowanie kolumny `value` dla sekretów** | ⚠ BRAK | Encrypt-at-rest dla config.value gdzie secret=1 |

### 5.2 Środki Organizacyjne

| Środek | Status | Szczegóły |
|--------|--------|-----------|
| RoPA (ten dokument) | ✅ UTWORZONO | art.30 RODO — SYLION v5.9.0 |
| Polityka retencji | ✅ UDOKUMENTOWANA | Sekcja 3 |
| Procedury DSR | ✅ UDOKUMENTOWANE | Sekcja 4 |
| **Szkolenie RODO dla operatorów** | ⚠ WYMAGANE | Podstawowe szkolenie z RODO dla każdego operatora dashboardu |
| **Polityka czystego biurka** | ⚠ DO WDROŻENIA | Dotyczy stacji roboczych z dostępem do systemu |
| **Procedura naruszenia danych** | ⚠ DO WDROŻENIA | Art.33 RODO: zgłoszenie do UODO/BfDI w 72h |
| **DPA z dostawcami API** | ⚠ WYMAGANE | OpenAI, Anthropic, Google, Perplexity |

### 5.3 Procedura Naruszenia Danych (Art. 33-34 RODO)

**Jeśli dojdzie do naruszenia:**
1. **Godzina 0:** Izolacja systemu; zablokowanie podejrzanego dostępu.
2. **Godzina 0-4:** Ocena skali naruszenia (jakie dane, ilu podmiotów, ryzyko dla osób).
3. **Godzina 0-72:** Zgłoszenie do organu nadzorczego:
   - Polska: UODO (uodo.gov.pl) — formularz online.
   - Niemcy: BfDI lub właściwy LfDI danego landu.
4. **Jeśli wysokie ryzyko dla osób:** Powiadomić podmioty danych bez zbędnej zwłoki (art.34 RODO).
5. **Dokumentacja:** Każde naruszenie dokumentować w rejestrze naruszeń (art.33 ust.5).

```
Kontakt UODO (PL):    uodo.gov.pl / (+48) 22 531 03 00
Kontakt BfDI (DE):    bfdi.bund.de / poststelle@bfdi.bund.de
```

---

## 6. TRANSFERY MIĘDZYNARODOWE

### 6.1 Mapa Transferów

| Dostawca | Kraj | Kategoria | Mechanizm Transferu | DPA Status | Risk |
|----------|------|-----------|--------------------|--------------------|------|
| **OpenAI** | USA | Podmiot przetwarzający | EU-US DPF (verify) + SCC Module 2 (2021) | ⚠ Do podpisania (Enterprise) | MEDIUM |
| **Anthropic** | USA | Podmiot przetwarzający | SCC Module 2 (2021) | ⚠ Do podpisania | HIGH |
| **Google AI** | USA/EU | Podmiot przetwarzający | EU-US DPF + SCC | ⚠ Weryfikacja Cloud DPA | MEDIUM |
| **Perplexity** | USA | Podmiot przetwarzający | SCC Module 2 (2021) | ⚠ Do podpisania | HIGH |

### 6.2 Transfer Impact Assessment (TIA) — Wymagania

Zgodnie z wyrokiem TSUE Schrems II (C-311/18) i EDPB Guidelines 05/2021:

**Dla każdego dostawcy US należy:**
1. Ocenić regulacje US wpływające na dostęp do danych (FISA 702, EO 12333, CLOUD Act).
2. Sprawdzić certyfikację DPF na: [privacyshield.gov/participants](https://www.privacyshield.gov/ps/active-participants).
3. Jeśli DPF certyfikowany → transfer dozwolony (do momentu ewentualnego podważenia DPF).
4. Jeśli brak DPF → wymagane SCC Module 2 (Controller-to-Processor, wersja czerwiec 2021).
5. Dokumentować wynik TIA.

**Status TIA:** ⚠ WYMAGANE — do przeprowadzenia przed produkcją.

### 6.3 Minimalizacja Ryzyka Transferów

1. **Polityka treści promptów:** Zakazać umieszczania danych osobowych osób trzecich w promptach wysyłanych do zewnętrznych API.
2. **Pseudonimizacja:** Przed wysłaniem do API, dane osobowe zastąpić pseudonimami (technicznie możliwe jako pre-processing krok pipeline).
3. **Data residency:** Jeśli dostępne — wybrać EU data centers u dostawców (OpenAI Enterprise: EU processing option; Google Cloud: EU region).

---

## 7. PODMIOTY PRZETWARZAJĄCE (PROCESORZY)

### 7.1 Rejestr Procesorów

| Procesor | Rola | Dane przekazywane | DPA | SCC | Art.28 compliant |
|----------|------|-------------------|-----|-----|-----------------|
| OpenAI | AI model API | Treści promptów | ⚠ Do podpisania | DPF/SCC | ⚠ W trakcie |
| Anthropic | AI model API | Treści promptów | ⚠ Do podpisania | SCC M2 | ⚠ W trakcie |
| Google AI | AI model API | Treści promptów | ⚠ Weryfikacja | DPF/SCC | ⚠ W trakcie |
| Perplexity | AI search API | Zapytania wyszukiwania | ⚠ Do podpisania | SCC M2 | ⚠ W trakcie |
| [Hosting/IaaS] | Infrastruktura | Wszystkie dane | [Do uzupełnienia] | [Do uzupełnienia] | [Do uzupełnienia] |

### 7.2 Sub-Procesorzy

Każdy procesor musi ujawnić swoich sub-procesorów. Administrator musi być powiadomiony o zmianach sub-procesorów (art.28 ust.2 RODO). Wymagać od procesorów: lista sub-procesorów + prawo sprzeciwu.

---

## 8. OCENA SKUTKÓW DLA OCHRONY DANYCH (DPIA)

### 8.1 Screening — Czy DPIA Jest Wymagana?

Zgodnie z art.35 RODO i listami organów nadzorczych:

| Kryterium | Status SYLION v5.9.0 |
|-----------|----------------------|
| Systematyczna ocena osób (profilowanie) | NIE |
| Przetwarzanie na dużą skalę danych wrażliwych (art.9) | NIE |
| Systematyczne monitorowanie na dużą skalę | NIE |
| Innowacyjna technologia + duże ryzyko | ROZWAŻYĆ (AI pipeline) |
| Transfer masowy do państw trzecich + duże ryzyko | ROZWAŻYĆ |

**Wstępna ocena:** DPIA nie jest bezwzględnie wymagana dla wewnętrznego dev pipeline. Przy skalowaniu lub komercjalizacji — DPIA WYMAGANA.

**Rekomendacja:** Przeprowadzić uproszczoną DPIA dokumentując ocenę ryzyka transferów US API.

---

## 9. AI ACT — DOKUMENTACJA SYSTEMU AI

### 9.1 Klasyfikacja Systemu AI

| Parametr | Wartość |
|----------|---------|
| Nazwa systemu | SYLION Multi-Agent Pipeline |
| Wersja | v5.9.0 |
| Klasyfikacja ryzyka | Limited Risk / General Purpose AI |
| Annex III (high-risk)? | NIE |
| General Purpose AI? | TAK — orchestracja modeli GPT/Claude/Gemini |

### 9.2 Human Oversight — Art. 14 AI Act

| Wymóg | Status | Implementacja |
|-------|--------|---------------|
| Efektywny nadzór nad systemem | ✅ SPEŁNIONY | `human_gate` table z mode/deferred_until |
| Możliwość zatrzymania | ✅ SPEŁNIONY | Dashboard — pause/stop agentów |
| Możliwość zawieszenia decyzji | ✅ SPEŁNIONY | `deferred_until` field |
| Eskalacja do człowieka | ✅ SPEŁNIONY | `escalated_to`, `escalation_reason` |
| Świadomość limitów systemu | ⚠ DO WDROŻENIA | Dokumentacja techniczna (art.11) |
| Override decyzji AI | ✅ SPEŁNIONY | `status='approved'/'rejected'` w human_gate |
| Poinformowanie o interakcji z AI | ✅ SPEŁNIONY | Dashboard wyraźnie oznacza agentów AI |

### 9.3 Transparentność — Art. 13 AI Act

**Do uzupełnienia przez właściciela systemu:**
- Opis przeznaczenia systemu: [OPIS]
- Znane ograniczenia i błędy: [LISTA]
- Środki nadzoru przez człowieka: `human_gate` (patrz wyżej)
- Informacje kontaktowe producenta: [KONTAKT]

---

## 10. HISTORIA ZMIAN DOKUMENTU

| Wersja | Data | Autor | Zmiany |
|--------|------|-------|--------|
| 1.0.0 | 2025-07-10 | RODO Council (Opus/Sonnet/GPT-5.4/Gemini) | Inicjalna wersja RoPA — SYLION v5.9.0 |

### Harmonogram Przeglądów

- **Co 12 miesięcy** — przegląd kompletności RoPA.
- **Przy każdej zmianie przetwarzania** — aktualizacja odpowiedniej czynności (PA-XX).
- **Przy zmianie dostawców API** — aktualizacja Sekcji 6-7.
- **Po każdym incydencie bezpieczeństwa** — aktualizacja Sekcji 5.

---

## ZAŁĄCZNIK A — LINKI REFERENCYJNE

| Dokument | URL |
|----------|-----|
| RODO (PL) | https://uodo.gov.pl/pl/p/rodo |
| DSGVO (DE) | https://www.bfdi.bund.de/DE/Datenschutz/Ueberblick/MeineRechte/meine_rechte_node.html |
| BDSG | https://www.gesetze-im-internet.de/bdsg_2018/ |
| AI Act EU 2024/1689 | https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX:32024R1689 |
| SCCs (2021) | https://ec.europa.eu/info/law/law-topic/data-protection/international-dimension-data-protection/standard-contractual-clauses-scc_en |
| EU-US DPF | https://www.privacyshield.gov/ps/active-participants |
| EDPB Guidelines 05/2021 | https://edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-052021-interplay-application-article-46_en |
| OpenAI DPA | https://openai.com/policies/data-processing-addendum |
| Anthropic DPA | https://www.anthropic.com/legal/dpa |
| Google Cloud DPA | https://cloud.google.com/terms/data-processing-addendum |
| NIST SP 800-92 (log retention) | https://csrc.nist.gov/publications/detail/sp/800-92/final |
| GoBD (DE) | https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Weitere_Steuerthemen/Abgabenordnung/2019-11-28-GoBD.html |
| UODO (PL) | https://uodo.gov.pl |
| BfDI (DE) | https://www.bfdi.bund.de |

---

*Dokument wygenerowany przez RODO Compliance Council (Opus/Sonnet/GPT-5.4/Gemini) w ramach audytu SYLION v5.9.0.*  
*Nie stanowi porady prawnej — przed wdrożeniem produkcyjnym zaleca się konsultację z radcą prawnym specjalizującym się w RODO/DSGVO.*
