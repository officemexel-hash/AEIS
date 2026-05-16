# RODO Full Audit — SYLION v5.9.1

**Data raportu: 2026-04-19**

**Zakres:** Sylion (PL) + RSDG GmbH (DE)  
**Data audytu:** 2026-04-19  
**Wersja kodu:** 5.9.1 (`dashboard/db.py`, `dashboard/app.py`, `dashboard/retention_cleaner.py`)  
**Audytor:** Automated Compliance Review — Legal/Compliance subagent  
**Dokumenty źródłowe:** `docs/PRIVACY_POLICY_PL.md`, `docs/PRIVACY_POLICY_DE.md`, `docs/RODO_COMPLIANCE.md`, `docs/DPIA_v591.md`, `docs/INCIDENT_RESPONSE.md`, `docs/adr/ADR-0009`, `docs/adr/ADR-0021`

---

## SEKCJA 1 — TABELA 12 OBSZARÓW RODO

| # | Artykuł | Obszar | Status | Evidence (plik:linia) | Rekomendacja |
|---|---------|--------|--------|-----------------------|--------------|
| 1 | Art. 5 | Zasady (minimalizacja, ograniczenie celu) | **WARN** | `db.py:130-265` (users, audit_log, cost_log, sessions), `RODO_COMPLIANCE.md:182-194` (runs/artifacts bez retencji) | Zdefiniować politykę retencji dla `runs`, `run_artifacts`, `human_gate`; wyznaczyć cel przetwarzania dla `cost_log` |
| 2 | Art. 6 | Podstawa prawna | **WARN** | `PRIVACY_POLICY_PL.md:41-50` (art.6(1)(f) dla wszystkiego), `RODO_COMPLIANCE.md:70-83` | Rozważyć art.6(1)(b) dla uwierzytelniania; uzupełnić Balancing Test LIA; brak zgody (art.6(1)(a)) — OK jeśli wyłącznie operatorzy wewnętrzni |
| 3 | Art. 7 | Zgoda | **WARN** | `templates/index.html:106-114` (cookie banner), `static/js/app.js:5250-5291` | Cookie banner obecny, ale brak mechanizmu wycofania zgody (opcja "odrzuć"); w modelu B2B/LI zgoda nie jest wymagana — potwierdzić model wdrożenia |
| 4 | Art. 13/14 | Obowiązek informacyjny | **WARN** | `PRIVACY_POLICY_PL.md:1-3` (wersja 5.9.0, "draft"), `PRIVACY_POLICY_DE.md:1-5` | PP oznaczone jako "draft — wymaga weryfikacji prawnej"; brakuje: tożsamości administratora (placeholder), informacji o DeepSeek/xAI; zaktualizować wersję do 5.9.1 |
| 5 | Art. 15 | Prawo dostępu | **WARN** | `PRIVACY_POLICY_PL.md:114` (email-only), `RODO_COMPLIANCE.md:246-263` | Brak samoobsługowego endpointu Art.15 — `/api/auth/me/export` obejmuje profil+audit_log+sesje, ale dostęp wymaga aktywnego konta; uzupełnić procedurę dla b. pracowników |
| 6 | Art. 16 | Prawo do sprostowania | **PASS** | `app.py:1208-1250` (`PUT /api/users/{id}` — owner), `RODO_COMPLIANCE.md:287-295` | Endpoint działa, zalogowany do audit_log. Uwaga: użytkownik nie może samodzielnie edytować własnego profilu (username) — wymaga interwencji ownera |
| 7 | Art. 17 | Prawo do usunięcia (erasure) | **WARN** | `app.py:993-1069` (`DELETE /api/auth/me/data`), `retention_cleaner.py:92-139` | Implementacja prawidłowa (soft-delete + anonimizacja audit_log + cascade sessions/uploads). **GAP KRYTYCZNY:** brak kaskady do `cost_log` (user_id dodany w v5.9.1 db.py:993-1008) oraz `runs`/`run_artifacts`. Dane kosztowe użytkownika pozostają po erasure. |
| 8 | Art. 20 | Przenoszenie danych | **PASS** | `app.py:1075-1140` (`GET /api/auth/me/export`) | Export ZIP (profile.json, audit_log.json, sessions.json, README.md) w formacie JSON — maszynowo czytelny. Uwaga: `PRIVACY_POLICY_DE.md:118` nadal oznacza jako "w przygotowaniu" — zaktualizować |
| 9 | Art. 25 | Privacy by design | **WARN** | `db.py:87-95` (WAL, foreign_keys), `db.py:1325-1380` (argon2id), `app.py:328-336` (Secure cookie default TRUE), `DPIA_v591.md:46` | SQLite bez szyfrowania at-rest (udokumentowane jako znane ograniczenie dev); backupy plaintext; API keys w DB plaintext mimo `secret=1` flagi (kolumna `value` niezaszyfrowana) |
| 10 | Art. 28 | Umowa powierzenia (DPA sub-procesorzy) | **FAIL** | `RODO_COMPLIANCE.md:386-421`, `DPIA_v591.md:30` | DPA brak/niezweryfikowane dla: Anthropic, OpenAI (Enterprise), Google AI, Perplexity. **NOWI sub-procesorzy xAI i DeepSeek** nieuwzględnieni w Privacy Policy PL/DE. DeepSeek: brak decyzji adekwatności dla Chin — CRITICAL |
| 11 | Art. 32 | Bezpieczeństwo | **WARN** | `db.py:1325-1450` (argon2id), `app.py:657-688` (rate limiting), `app.py:764` (Secure/HttpOnly/SameSite), `app.py:1820-1829` (CSRF double-submit) | Hashing: OK (argon2id). Rate limiting: OK (in-memory — ryzyko przy wieloprocesorowym deploy). CSRF: OK. **GAP:** _DEFAULT_API_KEYS hardcoded w `db.py:1144-1157` (żywe klucze OpenAI/Anthropic/Perplexity); szyfrowanie at-rest brak; TLS wymagany zewnętrzny proxy |
| 12 | Art. 33/34 | Zgłaszanie naruszeń (72h) | **WARN** | `RODO_COMPLIANCE.md:362-376`, `INCIDENT_RESPONSE.md:173-198` | Procedura udokumentowana (UODO/BfDI + timeline); brak: (a) rejestru naruszeń (art.33 ust.5), (b) formalnego procesu eskalacji do IOD/DPO, (c) automatycznego alertu przy anomalii auth |

---

## SEKCJA 2 — SZCZEGÓŁOWA ANALIZA KLUCZOWYCH OBSZARÓW

### Art. 5 — Zasady przetwarzania

**Minimalizacja (art.5(1)(c)):**
- `users` table: minimal — id, username, display_name, password_hash, role, created_at, last_login — OK.
- `sessions` table: ip_address przechowywany — quasi-PII, uzasadnienie art.6(1)(f) udokumentowane w RoPA PA-01.
- `audit_log`: actor (username), action, target, detail — niezbędne dla celów bezpieczeństwa.
- `cost_log.user_id`: dodany w v5.9.1 (db.py:993-1008) — powiązanie kosztów z użytkownikiem; brak udokumentowanego celu w RoPA.

**Ograniczenie przechowywania (art.5(1)(e)):**

| Tabela | Retencja | Mechanizm | Status |
|--------|----------|-----------|--------|
| `users` | soft-delete 30d → hard purge | `purge_soft_deleted_users()` | ✅ |
| `sessions` | 30d konfig. | `prune_sessions()` | ✅ |
| `audit_log` | 365d konfig. | `prune_audit_log()` | ✅ |
| `upload_history` | 90d konfig. (R-02 fix) | `prune_upload_history()` | ✅ |
| `workspace_uploads` | 90d konfig. | `prune_workspace_uploads()` | ✅ |
| `event_stream` | 7d stałe | `prune_event_stream()` | ✅ |
| `cost_log` | **BRAK** | Brak pruning | ❌ |
| `runs` | **BRAK** | Brak pruning | ❌ |
| `run_artifacts` | **BRAK** | Brak pruning | ❌ |
| `human_gate` | **BRAK** | Brak pruning | ❌ |
| Backupy SQLite | **NIEOKREŚLONA** | Brak automatycznego usuwania | ❌ |

**Ograniczenie celu (art.5(1)(b)):**
- Cel przetwarzania `cost_log.user_id` niezudokumentowany w RoPA (PA-XX brak).
- Dane z `prompt_history`/`baselines` mogą zawierać PII jeśli operator wklei je do promptów — brak polityki.

---

### Art. 7 — Zgoda

**Cookie banner (Q-6 fix, v5.9.1):**
- `templates/index.html:106-114`: baner informacyjny z przyciskiem "OK".
- `static/js/app.js:5250-5291`: preferencja w `localStorage['sylion_cookie_consent']`.
- **GAP:** Brak opcji "Odrzuć" / "Nie zgadzam się" — wymagane dla art.7(3) i ePrivacy jeśli cookies inne niż niezbędne. Sesja opisana jako art.6(1)(b) — niezbędna, więc baner informacyjny (nie opt-in) jest dopuszczalny. Dokumentacja powinna to wyraźnie wyjaśniać.
- Uwaga: system to narzędzie wewnętrzne (B2B) — zgoda pracownicza w DE regulowana §26 BDSG.

---

### Art. 13/14 — Obowiązek informacyjny

**Privacy Policy PL (PRIVACY_POLICY_PL.md):**
- Wersja 5.9.0 (nie zaktualizowana do 5.9.1).
- Placeholder `[IMIĘ I NAZWISKO / NAZWA ORGANIZACJI]` nie uzupełniony.
- Brak DeepSeek i xAI w sekcji 5 (Przekazywanie danych do zewnętrznych dostawców AI) — krytyczny gap.
- Art.20 opisany jako "endpoint w przygotowaniu" — nieaktualne (wdrożony w v5.9.1).
- DSR contact: `support@sylion.example` (placeholder).

**Privacy Policy DE (PRIVACY_POLICY_DE.md):**
- Podobne gaps; art.20 jako "in Vorbereitung".
- §26 BDSG i §87 BetrVG uwzględnione — pozytywne dla DE.
- Brak DeepSeek/xAI.

---

### Art. 17 — Prawo do usunięcia

**Endpoint `DELETE /api/auth/me/data` (app.py:993-1069):**

Co jest usuwane/anonimizowane:
1. ✅ `users.deleted_at = now(), enabled = 0` (soft-delete)
2. ✅ `audit_log` — anonimizacja actor+detail
3. ✅ `sessions` — DELETE
4. ✅ `workspace_uploads` — DELETE + disk cleanup
5. ✅ `upload_history` — anonimizacja uploaded_by+filename
6. ✅ `config WHERE key LIKE USER_{id}_%` — DELETE

**BRAKUJE:**
- ❌ `cost_log WHERE user_id = ?` — dane kosztowe z user_id pozostają
- ❌ `runs` — powiązane uruchomienia pipeline (brak user_id w `runs`, ale mogą zawierać dane)
- ❌ `ollama_shadow_log`, `ollama_memory` — potencjalne dane użytkownika

**Ważne (art.17 ust.3):** Anonimizacja `audit_log` (a nie usunięcie) uzasadniona art.17(3)(e) — obrona roszczeń, udokumentowane w `RODO_COMPLIANCE.md:285`.

---

### Art. 28 — Umowy powierzenia

**Zidentyfikowani sub-procesorzy:**

| Procesor | Kraj | DPA | Mechanizm transferu | Risk |
|----------|------|-----|---------------------|------|
| OpenAI | USA | ⚠️ Do podpisania (Enterprise) | EU-US DPF + SCC M2 | MEDIUM |
| Anthropic | USA | ⚠️ Do podpisania | SCC M2 (2021) | HIGH |
| Google AI | USA/EU | ⚠️ Weryfikacja Cloud DPA | EU-US DPF + SCC | MEDIUM |
| Perplexity | USA | ⚠️ Do podpisania | SCC M2 | HIGH |
| **DeepSeek** | **Chiny** | ❌ BRAK | **Brak decyzji adekwatności** | **CRITICAL** |
| **xAI (Grok)** | **USA** | ❌ BRAK | Niezidentyfikowany | HIGH |

DeepSeek (`app.py:4720-4726`, `db.py:1163`): Transfer do Chin bez mechanizmu prawnego — **CRITICAL** naruszenie art.46 RODO.

---

### Art. 32 — Bezpieczeństwo

**Środki techniczne:**
- ✅ argon2id (time_cost=3, memory_cost=65536) — `db.py:1366-1380`; bcrypt fallback
- ✅ Secure=True default cookie — `app.py:331`, ADR-0009
- ✅ HttpOnly=True, SameSite=Strict — `app.py:764`
- ✅ CSRF double-submit (X-CSRF-Token header) — `app.py:1820-1829`
- ✅ Rate limiting login (in-memory sliding window) — `app.py:657-688`
- ✅ RBAC (owner/operator/security/readonly) — `db.py:130-139`
- ✅ Foreign keys ON, WAL mode — `db.py:87-95`
- ⚠️ Szyfrowanie at-rest: BRAK (SQLite plaintext, udokumentowane jako dev limitation)
- ❌ **API keys hardcoded** `db.py:1144-1157`: OpenAI `sk-proj-JwEw...`, Anthropic `sk-ant-api03-rV...`, Perplexity `pplx-o2ZY...`, Google API key — klucze produkcyjne wbudowane w kod źródłowy

---

### Art. 33/34 — Zgłaszanie naruszeń

**Co jest:**
- Procedura 72h udokumentowana: `RODO_COMPLIANCE.md:362-376`, `INCIDENT_RESPONSE.md:173-198`
- Kontakty UODO (PL) i BfDI/LfDI (DE)
- Severity matrix P0-P4

**Co brakuje:**
- ❌ Rejestr naruszeń (art.33 ust.5) — plik/tabela do ewidencji każdego naruszenia
- ❌ IOD/DPO nie wyznaczony (placeholder w RoPA)
- ❌ Automatyczny alert przy podejrzanej aktywności auth (brute-force w logach, brak integracji alertingu)
- ❌ Test procedury (dry-run / tabletop exercise)

---

## SEKCJA 3 — CROSS-BORDER PL↔DE

### Art. 26 GDPR / §26 BDSG — Współadministrowanie

**Status:** Umowa współadministrowania (JCA, art.26 RODO) **NIE ISTNIEJE** między Sylion (PL) a RSDG GmbH (DE).

**Wymagane działania:**
1. Ustalić, czy RSDG GmbH jest współadministratorem (przetwarza dane własnych pracowników w SYLION) czy podmiotem przetwarzającym.
2. Jeśli współadministrowanie: zawrzeć JCA art.26 — dokumentować zakres, cele, odpowiedzialność za realizację praw podmiotów danych.
3. §26 BDSG (Niemcy) — przetwarzanie danych pracowników: wymaga podstawy prawnej, poinformowania pracowników, ewentualnie konsultacji z Betriebsrat (§87 BetrVG Abs.1 Nr.6).

**Transfer PL→DE:**
- Wewnątrz UE/EOG — transfer swobodny (art.44-46 RODO nie ma zastosowania do transferów wewnątrz EOG).
- **Wymagane:** wzajemne DPA lub JCA, dokumentacja celu transferu w RoPA.

### SCC dla sub-procesorów spoza EOG

| Procesor | Kraj | Aktualny status SCC | Wymagane działanie |
|----------|------|---------------------|--------------------|
| OpenAI | USA | SCC M2 (2021) deklarowane | Podpisać DPA, zweryfikować TIA |
| Anthropic | USA | SCC M2 (2021) deklarowane | Podpisać DPA, przeprowadzić TIA |
| Google AI | USA/EU | DPF + SCC | Aktywować Cloud DPA, wybrać EU region |
| Perplexity | USA | SCC M2 deklarowane | Podpisać DPA |
| **DeepSeek** | **Chiny** | **BRAK** | **STOP: TIA + SCC wymagane przed jakimkolwiek PII transfer** |
| **xAI** | **USA** | **BRAK** | Podpisać DPA + SCC M2 |

**Schrems II (C-311/18) / EDPB GL 05/2021:**
- Dla USA: EU-US Data Privacy Framework (DPF) obowiązuje od 07.2023 — weryfikować certyfikację na [privacyshield.gov](https://privacyshield.gov).
- Dla Chin: BRAK decyzji adekwatności, BRAK DPF — jedyna opcja to SCC Module 2 + TIA + środki uzupełniające. FISA 702 i chińskie prawo o cyberbezpieczeństwie/danychbezp. tworzą wysokie ryzyko — TIA może wykazać nieadekwatność SCC bez silnych środków technicznych (end-to-end encryption, pseudonimizacja).

**Transfer pricing (nota podatkowa):** Poza zakresem audytu RODO — wymaga osobnego przeglądu przez doradcę podatkowego dla transakcji PL↔DE.

---

## SEKCJA 4 — FINDINGS MATRIX

### Legend
- **CRITICAL** — Bezpośrednie naruszenie prawa; wymaga natychmiastowej akcji
- **HIGH** — Znaczące ryzyko; naprawić przed wdrożeniem produkcyjnym
- **MEDIUM** — Ryzyko; zaadresować w ciągu 90 dni
- **LOW** — Ulepszenia; wdrożyć w kolejnym cyklu

---

| ID | Priorytet | Obszar | Tytuł | Evidence | Zalecenie | Termin |
|----|-----------|--------|-------|----------|-----------|--------|
| F-01 | **CRITICAL** | Art. 28 / Art. 44-46 | DeepSeek — transfer do Chin bez mechanizmu prawnego | `db.py:1163`, `DPIA_v591.md:30`, `app.py:4720-4726` | Zablokować transfer PII do DeepSeek API do czasu: (a) SCC Module 2 + TIA lub (b) rezygnacji z DeepSeek. Zaktualizować PP PL/DE | Natychmiast |
| F-02 | **CRITICAL** | Art. 32 | Hardcoded API keys (OpenAI/Anthropic/Perplexity/Google) w kodzie źródłowym | `db.py:1144-1157` | Usunąć wszystkie klucze z kodu; wczytywać wyłącznie z env vars lub sealed secret store; rotować skompromitowane klucze ASAP | Natychmiast |
| F-03 | **HIGH** | Art. 17 | Brak kaskady erasure do `cost_log` | `app.py:993-1069` (brak DELETE cost_log), `db.py:993-1008` (user_id w cost_log) | Dodać `DELETE FROM cost_log WHERE user_id = ?` w `erase_my_data()`; dodać do RoPA | 30 dni |
| F-04 | **HIGH** | Art. 28 | Brak DPA z xAI (Grok) i aktualizacja PP | `db.py:1163`, `app.py:4734-4738` | Podpisać DPA z xAI; dodać xAI do sekcji 5 PP PL i PP DE; przeprowadzić TIA | 30 dni |
| F-04b | **HIGH** | Art. 13/14 | Privacy Policy nieaktualne (wersja 5.9.0, placeholder admin, brak xAI/DeepSeek) | `PRIVACY_POLICY_PL.md:1-6`, `PRIVACY_POLICY_DE.md:1-6` | Uzupełnić dane administratora; zaktualizować do v5.9.1; dodać xAI+DeepSeek; zaktualizować status Art.20 | 30 dni |
| F-05 | **HIGH** | Art. 26 | Brak JCA/DPA między Sylion PL a RSDG GmbH DE | `RODO_COMPLIANCE.md:55-60` (placeholder) | Określić relację prawną (joint controller vs processor); zawrzeć odpowiednią umowę; przeprowadzić §26 BDSG + BetrVG §87 analizę | 60 dni |
| F-06 | **HIGH** | Art. 28 | DPA brak/niezweryfikowane dla Anthropic, Perplexity | `RODO_COMPLIANCE.md:387-421` | Podpisać DPA z Anthropic i Perplexity (SCC M2 2021); przeprowadzić TIA dla USA | 60 dni |
| F-07 | **MEDIUM** | Art. 5 | Brak retencji dla `cost_log`, `runs`, `run_artifacts`, `human_gate` | `RODO_COMPLIANCE.md:190-193`, `db.py:484-560` | Zdefiniować okresy retencji; dodać prune tasks w `retention_cleaner.py`; udokumentować w RoPA | 60 dni |
| F-08 | **MEDIUM** | Art. 5 | Brak polityki retencji dla backupów SQLite | `RODO_COMPLIANCE.md:171-174` | Zdefiniować retencję (np. 90 dni); dodać automatyczne usuwanie; wdrożyć szyfrowanie backupów (SQLCipher lub GPG) | 60 dni |
| F-09 | **MEDIUM** | Art. 33 | Brak formalnego rejestru naruszeń (art.33 ust.5) | `RODO_COMPLIANCE.md:362-376` | Stworzyć rejestr naruszeń (plik/tabela); wdrożyć procedurę dokumentowania każdego incydentu bezpieczeństwa | 60 dni |
| F-10 | **MEDIUM** | Art. 25 | API keys w DB plaintext mimo `secret=1` flag | `db.py:117-125` (config.value niezaszyfrowane), `RODO_COMPLIANCE.md:344-348` | Zaszyfrować kolumnę `config.value` dla wierszy `secret=1` (AES-256-GCM lub SQLCipher) | 90 dni |
| F-11 | **MEDIUM** | Art. 6 / Art. 5 | `cost_log.user_id` bez dokumentacji celu w RoPA | `db.py:993-1008` | Dodać czynność PA-XX do RoPA dla cost_log; udokumentować cel, podstawę prawną, retencję | 60 dni |
| F-12 | **MEDIUM** | Art. 28 | TIA (Transfer Impact Assessment) nie przeprowadzone dla żadnego sub-procesora | `RODO_COMPLIANCE.md:391-402` | Przeprowadzić TIA dla OpenAI, Anthropic, Google, Perplexity zgodnie z EDPB GL 05/2021 | 90 dni |
| F-13 | **LOW** | Art. 16 | Użytkownik nie może samodzielnie edytować własnego profilu | `app.py:1208` (owner-only PUT) | Rozważyć endpoint `PUT /api/auth/me/profile` dla samodzielnej edycji display_name | Backlog |
| F-14 | **LOW** | Art. 7 | Cookie banner bez opcji "Odrzuć" | `templates/index.html:106-114` | Jeśli cookies niezbędne do działania (art.6(1)(b)) — baner informacyjny wystarczy; jawnie udokumentować brak opt-out; jeśli analytics — dodać opt-out | 90 dni |
| F-15 | **LOW** | Art. 13 | Art.20 opisany jako "w przygotowaniu" w obu PP | `PRIVACY_POLICY_PL.md:118`, `PRIVACY_POLICY_DE.md:118` | Zaktualizować tekst PP — endpoint wdrożony w v5.9.1 | 30 dni |
| F-16 | **LOW** | Art. 37 | IOD/DPO nie wyznaczony (placeholder) | `RODO_COMPLIANCE.md:41-52` | Ocenić obowiązek wyznaczenia IOD (art.37); dla RSDG GmbH: obowiązek przy ≥20 pracownikach regularnie przetwarzających elektronicznie (§38 BDSG) | 60 dni |
| F-17 | **LOW** | Art. 32 | Rate limiter in-memory — ryzyko przy multi-process | `app.py:635-688` | Dodać komentarz ADR o ograniczeniu; dla multi-worker: przenieść do Redis/DB | Backlog |

---

## SEKCJA 5 — PODSUMOWANIE STATUSÓW

| Artykuł | Status | Główne uzasadnienie |
|---------|--------|---------------------|
| Art. 5 (zasady) | ⚠️ WARN | Brak retencji dla cost_log, runs, run_artifacts, human_gate, backupów |
| Art. 6 (podstawa prawna) | ⚠️ WARN | art.6(1)(f) LIA dla wszystkiego — wymaga Balancing Test; cost_log.user_id nieudokumentowane |
| Art. 7 (zgoda) | ⚠️ WARN | Cookie banner OK, ale brak opt-out; B2B/LI może nie wymagać — doprecyzować |
| Art. 13/14 (obowiązek info.) | ⚠️ WARN | PP jako "draft", placeholder admin, brakuje xAI/DeepSeek, wersja nieaktualna |
| Art. 15 (dostęp) | ⚠️ WARN | Export endpoint wdrożony, ale email-only procedura dla b. pracowników |
| Art. 16 (sprostowanie) | ✅ PASS | PUT /api/users/{id} działa + audit log |
| Art. 17 (usunięcie) | ⚠️ WARN | Endpoint istnieje, ale brak kaskady do cost_log |
| Art. 20 (przenoszenie) | ✅ PASS | GET /api/auth/me/export → ZIP JSON — prawidłowy |
| Art. 25 (privacy by design) | ⚠️ WARN | Argon2id OK; Secure cookie OK; brak szyfrowania at-rest; API keys hardcoded w kodzie |
| Art. 28 (DPA sub-procesorzy) | ❌ FAIL | DPA brak dla wszystkich; DeepSeek CRITICAL (Chiny bez adekwatności); xAI HIGH |
| Art. 32 (bezpieczeństwo) | ⚠️ WARN | Dobre środki tech.; **hardcoded API keys CRITICAL**; brak szyfrowania at-rest |
| Art. 33/34 (naruszenia 72h) | ⚠️ WARN | Procedura opisana, brak: rejestru naruszeń, IOD, automatycznych alertów |

**Legenda:** ✅ PASS = w pełni zgodny | ⚠️ WARN = częściowo zgodny z lukami | ❌ FAIL = niezgodny

---

## SEKCJA 6 — PRIORYTETY NAPRAWCZE

### Natychmiastowe (przed następnym uruchomieniem z PII)
1. **F-02** — Rotować i usunąć hardcoded klucze API z `db.py`
2. **F-01** — Zablokować transfer PII do DeepSeek API (brak mechanizmu prawnego)

### Krótkoterminowe (≤ 30 dni)
3. **F-03** — Dodać CASCADE erasure do `cost_log` w `erase_my_data()`
4. **F-04/F-04b** — Podpisać DPA z xAI; zaktualizować Privacy Policy PL+DE

### Średnioterminowe (≤ 60 dni)
5. **F-05** — Zawrzeć JCA/DPA Sylion PL ↔ RSDG GmbH DE
6. **F-06** — Podpisać DPA z Anthropic, Perplexity
7. **F-07** — Retencja dla cost_log, runs, run_artifacts, human_gate
8. **F-09** — Rejestr naruszeń (art.33 ust.5)
9. **F-11** — Dokumentacja celu cost_log.user_id w RoPA

### Długoterminowe (≤ 90 dni)
10. **F-08** — Retencja + szyfrowanie backupów
11. **F-10** — Szyfrowanie kolumny config.value dla secret=1
12. **F-12** — TIA dla wszystkich sub-procesorów USA
13. **F-14/F-15/F-16** — PP aktualizacja, IOD ocena

---

## SEKCJA 7 — METRYKI AUDYTU

| Metryka | Wartość |
|---------|---------|
| Obszarów ocenionych | 12 |
| PASS | 2 (Art.16, Art.20) |
| WARN | 9 (Art.5, 6, 7, 13, 15, 17, 25, 32, 33) |
| FAIL | 1 (Art.28) |
| Findings łącznie | 17 |
| CRITICAL | 2 (F-01 DeepSeek, F-02 hardcoded keys) |
| HIGH | 4 (F-03, F-04, F-04b, F-05, F-06) |
| MEDIUM | 6 (F-07 – F-12) |
| LOW | 5 (F-13 – F-17) |
| Obszary wymagające natychmiastowej akcji | 2 |

---

## ZAŁĄCZNIK — TABELA RETENCJI (STAN PO v5.9.1)

| Tabela | Dane osobowe | Retencja | Mechanizm | Art. RODO | Status |
|--------|-------------|----------|-----------|-----------|--------|
| `users` | username, display_name, password_hash, role | 30d (soft-delete) + hard purge | `purge_soft_deleted_users()` | Art.5(1)(e), Art.17 | ✅ |
| `sessions` | user_id, ip_address, token | 30d konfig. | `prune_sessions()` | Art.5(1)(e) | ✅ |
| `audit_log` | actor (username), action, detail | 365d konfig. | `prune_audit_log()` | Art.5(1)(e), Art.6(1)(f) | ✅ |
| `upload_history` | uploaded_by, filename | 90d konfig. (R-02 fix) | `prune_upload_history()` | Art.5(1)(e) | ✅ |
| `workspace_uploads` | uploaded_by, disk_path | 90d konfig. | `prune_workspace_uploads()` | Art.5(1)(e) | ✅ |
| `event_stream` | (operacyjne) | 7d stałe | `prune_event_stream()` | Art.5(1)(e) | ✅ |
| `cost_log` | user_id (v5.9.1) | ❌ BRAK | — | — | ❌ |
| `runs` | (operacyjne, pot. PII w summary) | ❌ BRAK | — | — | ❌ |
| `run_artifacts` | (treść artefaktów) | ❌ BRAK | — | — | ❌ |
| `human_gate` | decided_by, description | ❌ BRAK | — | — | ❌ |
| Backupy `.sqlite3` | Wszystkie powyższe | ❌ NIEOKREŚLONA | — | Art.32 | ❌ |

---

*Raport wygenerowany automatycznie — RODO Full Audit SYLION v5.9.1, 2026-04-19.*  
*Nie stanowi porady prawnej. Przed wdrożeniem produkcyjnym zalecana konsultacja z radcą prawnym specjalizującym się w RODO/DSGVO.*  
*Następny przegląd: przy każdej zmianie architektury przetwarzania lub co 12 miesięcy.*
