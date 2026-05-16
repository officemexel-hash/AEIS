# SYLION v5.9.0 — Cross-Border EU Compliance (Gemini / EU Cross-Border)
**Audytor:** Gemini 3.1 Pro — Cross-Border EU Compliance Council  
**Data:** 2025-07-10  
**Zakres:** Transgraniczne aspekty RODO, AI Act EU 2024/1689, EDPB Guidelines, SCCs, international transfers  
**Standard:** RODO art.44-49, EDPB Guidelines 05/2021, AI Act, NIS2 Directive, ePrivacy

---

## EXECUTIVE SUMMARY

Analiza cross-border wykazuje, że główne ryzyko EU dotyczy transferów danych do dostawców API US (OpenAI, Anthropic, Google) bez udokumentowanych SCCs. SYLION jako dev pipeline jest w kategorii niskiego ryzyka AI Act. Architektura multi-agent z human-gate spełnia art.14 AI Act. NIS2 nie dotyczy (brak klasyfikacji jako podmiot istotny/ważny).

---

## FINDINGS

### CRITICAL

#### C-EU-01 — Transfer Danych do Państw Trzecich — Brak SCCs
**Podstawa prawna:** RODO art.44 (zakaz transferu bez odpowiedniej ochrony), art.46 ust.2 lit.c (SCC jako mechanizm transferu), EDPB Guidelines 05/2021 on transfers.  
**Lokalizacja:** `db.py:_DEFAULT_API_KEYS` → sync do `os.environ` → wywołania OpenAI API / Anthropic API / Google AI API  
**Opis:** System SYLION przekazuje dane (treści promptów, wyniki agentów, potencjalnie dane osobowe w promptach) do:
- **OpenAI** (USA) — serwery w USA/EU (zależnie od konfiguracji)
- **Anthropic** (USA) — serwery w USA
- **Google AI** (USA/EU) — Gemini API
- **Perplexity** (USA)

Każdy z tych transferów wymaga:
1. Ważnego mechanizmu transferu (SCC module 2: Controller-to-Processor, wersja EU 2021)
2. Transfer Impact Assessment (TIA) dla transferów US
3. Dokumentacji w RoPA

**Stan:** Brak dokumentacji jakichkolwiek SCCs lub DPA z dostawcami API.  
**Uwaga:** EU-US Data Privacy Framework (DPF, lipiec 2023) obejmuje OpenAI i Google — jeśli są certyfikowani DPF, SCC nie jest wymagany, ale DPF cert musi być zweryfikowany.  
**Severity:** CRITICAL

---

### HIGH

#### H-EU-01 — EDPB Guidelines 05/2021 — Transfer Impact Assessment (TIA)
**Podstawa prawna:** EDPB Guidelines 05/2021 on supplementary measures, Schrems II wyrok TSUE C-311/18.  
**Opis:** Po Schrems II każdy transfer do USA wymaga TIA (Transfer Impact Assessment):
1. Weryfikacja regulacji US (FISA 702, EO 12333) wpływających na dostęp do danych.
2. Ocena czy dostawca może faktycznie wdrożyć SCC.
3. Supplementary measures (szyfrowanie end-to-end, pseudonimizacja przed transferem).

**Stan dla SYLION:**
- Prompty mogą zawierać dane osobowe (jeśli użytkownik wkleja dane do analizy).
- Brak pseudonimizacji danych przed wysłaniem do API.
- Brak TIA dokumentu.

**Rekomendacja:** Wdrożyć politykę zakazującą umieszczania danych osobowych w promptach (technical control + policy) lub przeprowadzić TIA dla każdego dostawcy.  
**Severity:** HIGH

#### H-EU-02 — Brak Data Processing Agreements z Dostawcami API
**Podstawa prawna:** RODO art.28 (umowa z podmiotem przetwarzającym).  
**Opis:** Dostawcy API (OpenAI, Anthropic, Google) działają jako **podmioty przetwarzające** (processors) dane przekazywane w promptach. Wymagana jest formalna DPA (Data Processing Agreement):
- OpenAI: DPA dostępna (Enterprise tier), standardowy API bez DPA — PROBLEM.
- Anthropic: Commercial DPA dostępna na żądanie.
- Google: DPA dostępna w Workspace/Cloud, ale Gemini API (consumer) może nie obejmować.

**Stan:** Brak dokumentacji podpisanych DPA.  
**Severity:** HIGH

---

### MEDIUM

#### M-EU-01 — AI Act EU 2024/1689 — Klasyfikacja Ryzyka Pipeline
**Podstawa prawna:** Rozporządzenie EU 2024/1689 (AI Act), Annex III (high-risk AI systems).  
**Analiza:**
- SYLION = developerski pipeline orchestracji agentów AI.
- Zastosowanie: wewnętrzne narzędzie deweloperskie, nie system podejmujący decyzji o osobach.
- Annex III AI Act: katalog systemów wysokiego ryzyka (zatrudnienie, kredyty, prawa socjalne, edukacja, usługi krytyczne) — SYLION nie wchodzi do żadnej kategorii.
- Klasyfikacja: **General Purpose AI** lub **Limited Risk** (art.50 AI Act — obowiązki transparentności).

**Wymagania dla Limited Risk:**
- art.50 ust.1: systemy AI wchodzące w kontakt z ludźmi muszą informować że interaktują z AI.
- Human-gate spełnia ten wymóg (human-in-the-loop).

**Status:** Ogólnie ZGODNY. Brak dokumentacji systemu AI (art.11 → dokumentacja techniczna).  
**Severity:** MEDIUM

#### M-EU-02 — AI Act art.14 — Human Oversight — Analiza Architektury
**Podstawa prawna:** AI Act art.14 (human oversight).  
**Analiza architektury SYLION:**
```
Multi-agent pipeline (48 agentów)
    ↓
human_gate (tabela z mode/deferred_until/escalated_to)
    ↓
Zatwierdzenie/odrzucenie przez człowieka
    ↓
Wykonanie akcji
```
**Ocena art.14:**
- ✓ art.14 ust.1: środki umożliwiające efektywny nadzór — human_gate SPEŁNIA
- ✓ art.14 ust.2: możliwość zawieszenia — `deferred_until` SPEŁNIA
- ✓ art.14 ust.4 lit.a: interpret wyniki — UI dashboardu SPEŁNIA
- ✓ art.14 ust.4 lit.e: override decyzji — `status='approved'/'rejected'` SPEŁNIA
- ⚠ art.14 ust.4 lit.b: świadomość limitów — brak udokumentowanej "karty systemu AI"

**Status:** Human-gate SPEŁNIA art.14. Brak dokumentacji technicznej systemu.  
**Severity:** MEDIUM (dokumentacja, nie architektura)

#### M-EU-03 — NIS2 Directive — Ocena Zastosowania
**Podstawa prawna:** Dyrektywa NIS2 (2022/2555), implementacja krajowa.  
**Analiza:** NIS2 dotyczy "podmiotów istotnych" i "ważnych" (essential/important entities) w sektorach: energia, transport, bankowość, finanse, zdrowie, woda, infrastruktura cyfrowa, ICT services, administracja publiczna, przestrzeń kosmiczna.  
**Status:** SYLION jako wewnętrzny dev pipeline nie kwalifikuje się jako podmiot NIS2. N/A.  
**Severity:** N/A

#### M-EU-04 — ePrivacy — Cookies i Sesje Webowe
**Podstawa prawna:** Dyrektywa ePrivacy 2002/58/WE, implementacje krajowe.  
**Analiza:** Dashboard SYLION używa sesji HTTP (cookie-based authentication). ePrivacy wymaga:
- Zgody użytkownika na cookies (z wyjątkiem cookies niezbędnych technicznie).
- Sesje uwierzytelniające = cookies niezbędne technicznie → WYJĘTE spod obowiązku zgody.
- Brak analytics cookies → brak dodatkowych obowiązków.

**Status:** OK (sesje auth = niezbędne technicznie).  
**Severity:** LOW

#### M-EU-05 — RODO art.5.1.e — Retencja Cross-Border
**Opis:** Dane przetwarzane przez zagraniczne API (OpenAI, Anthropic) mają własne okresy retencji definiowane przez DPA każdego dostawcy:
- OpenAI: domyślnie 30 dni retencja API data (configurable)
- Anthropic: per DPA
- Google: per DPA

Brak kontroli SYLION nad retencją danych po stronie dostawców. SCC/DPA muszą określać czas retencji i obowiązek zwrotu/usunięcia (art.28 ust.3 lit.g RODO).  
**Severity:** MEDIUM

---

### LOW

#### L-EU-01 — EU-US Data Privacy Framework (DPF) — Weryfikacja Certyfikacji
**Opis:** DPF (lipiec 2023) stanowi adekwatną ochronę dla transferów US → nie wymaga SCC jeśli dostawca certyfikowany. Weryfikacja:
- OpenAI: certyfikowany DPF ✓ (weryfikacja: privacyshield.gov → DPF list)
- Google: certyfikowany DPF ✓
- Anthropic: weryfikacja wymagana (status zmienny)
- Perplexity: weryfikacja wymagana

**Rekomendacja:** Udokumentować status DPF każdego dostawcy w RoPA. DPF może zostać znowu podważony (ryzyko polityczne — Schrems II precedens).  
**Severity:** LOW (z uwagą na niestabilność DPF)

#### L-EU-02 — Europejski Inspektor Ochrony Danych — N/A
**Opis:** EDPS dotyczy instytucji EU. N/A dla prywatnego podmiotu.  
**Severity:** N/A

---

## TABELA CROSS-BORDER RISK MATRIX

| Dostawca | Kraj | Transfer Mechanism | DPA Status | Risk |
|----------|------|--------------------|------------|------|
| OpenAI | USA | DPF (certyfikowany) | Enterprise DPA (wymagana) | MEDIUM |
| Anthropic | USA | SCC 2021 (Module 2) | Commercial DPA (do podpisania) | HIGH |
| Google AI | USA/EU | DPF + SCC | Cloud DPA (do weryfikacji) | MEDIUM |
| Perplexity | USA | SCC 2021 (Module 2) | DPA wymagana | HIGH |

## PODSUMOWANIE EU CROSS-BORDER

| Severity | Liczba | Opis |
|----------|--------|------|
| CRITICAL | 1 | Brak SCCs/DPA z dostawcami API |
| HIGH | 2 | Brak TIA, Brak DPA |
| MEDIUM | 4 | AI Act dokumentacja, ePrivacy (OK), retencja API |
| LOW | 1 | DPF weryfikacja |
| N/A | 2 | NIS2, EDPS |

**Priorytet:** Podpisanie DPA z OpenAI/Anthropic/Google → dokumentacja TIA → aktualizacja RoPA z transferami.
