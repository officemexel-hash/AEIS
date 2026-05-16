# SYLION v5.9.0 — Legal Check PL+DE (GPT-5.4 / Prawny)
**Audytor:** GPT-5.4 — Legal Compliance Council (PL + DE)  
**Data:** 2025-07-10  
**Zakres:** Prawo polskie (UODO, KSeF, JPK), prawo niemieckie (BDSG, DSGVO, GoBD, HGB)  
**Standard:** RODO art.5, 17, 30, 32; BDSG §26, §35; GoBD; HGB §257; KSeF; JPK

---

## EXECUTIVE SUMMARY

Z perspektywy prawnej polsko-niemieckiej, system SYLION v5.9.0 (lokalny pipeline developerski) ma dwa CRITICAL issues: hardkodowane klucze API (art.32 RODO / §64 BDSG) oraz brak RoPA (art.30 RODO). Przepisy KSeF/JPK są N/A dla tego use-case. BDSG §26 (dane pracownicze) częściowo dotyczy jeśli system przetwarza dane pracowników. GoBD nie jest naruszony przez retencję 365 dni audit_log.

---

## ANALIZA PRAWNA

### 1. POLSKA — RODO / UODO

#### CRITICAL

##### C-PL-01 — Naruszenie art.30 RODO — Brak Rejestru Czynności Przetwarzania
**Podstawa prawna:** RODO art.30 ust.1 (nakłada obowiązek prowadzenia RoPA na administratorów); art.83 ust.4 (kara do 10 mln EUR lub 2% globalnego obrotu za naruszenie art.30).  
**Stan:** Brak `docs/RODO_COMPLIANCE.md` lub jakiegokolwiek rejestru.  
**Uwaga:** Dla wewnętrznych systemów < 250 pracowników istnieje częściowe wyłączenie (art.30 ust.5), ALE tylko jeśli przetwarzanie nie jest regularne lub dotyczy danych wrażliwych/bezpieczeństwa. System SYLION przetwarza dane regularnie (audit_log, sesje) → wyłączenie nie ma zastosowania.  
**Rekomendacja:** Natychmiastowe wygenerowanie RoPA.  
**Severity:** CRITICAL

##### C-PL-02 — Naruszenie art.32 RODO — Klucze API w Kodzie
**Podstawa prawna:** RODO art.32 ust.1 lit.a ("pseudonimizacja i szyfrowanie danych osobowych"), lit.b ("zdolność do zapewnienia poufności").  
**Stan:** Klucze API w `_DEFAULT_API_KEYS` = naruszenie poufności środków technicznych.  
**Rekomendacja:** Secrets management (Vault, env var, .env).  
**Severity:** CRITICAL

---

#### HIGH

##### H-PL-01 — Art.17 RODO — Prawo do Usunięcia — Niekompletność
**Podstawa prawna:** RODO art.17 ust.1 ("prawo do usunięcia danych bez zbędnej zwłoki"), art.17 ust.3 lit.e ("uzasadniona potrzeba ochrony prawnej").  
**Stan:** 
- `DELETE /api/users/{user_id}` — usuwa konto i sesje → CZĘŚCIOWO OK.
- `audit_log` z wpisami `actor=username` — NIE usuwane → uzasadnienie: bezpieczeństwo (art.17.3e) — musi być udokumentowane w RoPA.
- Brak procedury DSR dla podmiotów zewnętrznych (nie-operatorów systemu).

**Analiza:** W kontekście dev pipeline, jeśli jedyni "podmioty danych" to operatorzy dashboardu (pracownicy), procedura art.17 przez UODO jest uproszczona. Jednak formalne wnioski muszą być obsługiwane w 30 dni.  
**Severity:** HIGH

##### H-PL-02 — Art.5.1.e — Minimalizacja Danych — Audit_Log 365 dni
**Podstawa prawna:** RODO art.5 ust.1 lit.e ("storage limitation").  
**Analiza:**
- 365 dni dla audit_log technicznego (security log) jest uzasadnione celem bezpieczeństwa, forensics, detekcją anomalii.
- UODO w wytycznych (2023) akceptuje roczną retencję logów bezpieczeństwa.
- WYMAGANE: udokumentowanie uzasadnienia w RoPA (cel: bezpieczeństwo, podstawa prawna: uzasadniony interes art.6.1f lub wypełnienie obowiązku prawnego art.6.1c).

**Severity:** HIGH (jeśli brak dokumentacji uzasadnienia)

---

#### MEDIUM

##### M-PL-01 — KSeF / JPK — Status N/A
**Podstawa prawna:** Ustawa o VAT art.106nf-106nk (KSeF); Rozporządzenie MF ws. JPK.  
**Analiza:** SYLION v5.9.0 jest lokalnym pipeline developerskim, NIE systemem wystawiania faktur ani systemem ERP. Brak przetwarzania faktur VAT, danych JPK, transakcji skarbowych. KSeF/JPK nie ma zastosowania.  
**Status:** N/A — bez findings.  
**Severity:** N/A

##### M-PL-02 — Art.13 RODO — Obowiązek Informacyjny dla Operatorów
**Stan:** Brak widocznej klauzuli informacyjnej (art.13) przy logowaniu do dashboardu.  
**Rekomendacja:** Dodać klauzulę informacyjną (kim jest administrator, cel przetwarzania, retencja, prawa podmiotów danych, DPO jeśli wymagany).  
**Severity:** MEDIUM

---

### 2. NIEMCY — DSGVO / BDSG / GoBD

#### CRITICAL

##### C-DE-01 — §64 BDSG / Art.32 DSGVO — Klucze API w Kodzie
**Podstawa prawna:** §64 BDSG (technische und organisatorische Maßnahmen), art.32 DSGVO.  
**Stan:** Identyczne jak C-PL-02. W Niemczech BfDI (Bundesbeauftragter für den Datenschutz) szczególnie rygorystycznie traktuje naruszenia art.32 — precedensowe kary.  
**Severity:** CRITICAL

#### HIGH

##### H-DE-01 — BDSG §26 — Przetwarzanie Danych Pracowniczych
**Podstawa prawna:** BDSG §26 (Datenverarbeitung für Zwecke des Beschäftigungsverhältnisses).  
**Analiza:** Jeśli operatorzy dashboardu to pracownicy firmy:
- Przetwarzanie audit_log (kto co zrobił, kiedy) = dane pracownicze.
- §26 ust.1: przetwarzanie dozwolone tylko jeśli niezbędne do realizacji stosunku pracy.
- Wymagane: poinformowanie Rady Pracowniczej (Betriebsrat) jeśli istnieje — §87 BetrVG.
- Wymagane: udokumentowanie podstawy prawnej w RoPA.

**Severity:** HIGH (jeśli operator to pracodawca w DE)

##### H-DE-02 — BDSG §35 — Prawo do Usunięcia/Sprostowania
**Podstawa prawna:** BDSG §35 (Recht auf Löschung bei automatisierter Verarbeitung).  
**Analiza:** §35 BDSG uszczegóławia art.17 RODO dla kontekstu niemieckiego. Wymagania:
- Potwierdzenie usunięcia na piśmie (§35 ust.6 BDSG),
- Szczegółowe uzasadnienie odmowy (§35 ust.5),
- Obowiązek poinformowania podmiotów którym dane przekazano (§35 ust.4).

**Stan:** Brak procedury spełniającej §35 BDSG.  
**Rekomendacja:** Procedura DSR musi być zgodna z §35 BDSG.  
**Severity:** HIGH (jeśli dane pracowników DE)

---

#### MEDIUM

##### M-DE-01 — GoBD / HGB §257 — Retencja Audit_Log 365 dni — OCENA
**Podstawa prawna:** GoBD (Grundsätze zur ordnungsmäßigen Führung und Aufbewahrung von Büchern), §147 AO, §257 HGB.  
**Analiza:**
- GoBD wymagają 10-letniej retencji dla **dokumentów handlowych** (Handelsbrief, Buchungsbeleg).
- `audit_log` w SYLION = **dziennik techniczny**, nie dokument handlowy → retencja 365 dni NIE narusza GoBD.
- JEDNAK: jeśli audit_log zawiera zapisy zdarzeń biznesowych (np. zatwierdzenia transakcji), może kwalifikować się jako "sonstige Unterlagen" (§147 ust.1 Nr.5 AO) → wtedy 6 lat.
- Obecna implementacja (security events, logins, config changes) → GoBD N/A.

**Status:** OK dla bieżącego use-case.  
**Severity:** MEDIUM (uwaga na przyszłość)

##### M-DE-02 — Brak SCCs dla Transferów Poza EU
**Podstawa prawna:** DSGVO art.44-49 (transfer do państw trzecich), EU-US Data Privacy Framework (DPF 2023).  
**Analiza:** System korzysta z API zewnętrznych (OpenAI/US, Anthropic/US, Google/US). Dane przekazywane do tych API (np. treści promptów z danymi osobowymi) = transfer do państwa trzeciego.
- OpenAI: DPA + EU Standard Contractual Clauses (SCC) 2021 — dostępne, ale wymagają podpisania.
- Anthropic: DPA + SCC — dostępne.
- Google: DPA + SCC — dostępne.
- **Brak dokumentacji** podpisanych SCC w projekcie.

**Rekomendacja:** Podpisać DPA + SCC z każdym dostawcą API, udokumentować w RoPA jako "Transfer Impact Assessment".  
**Severity:** MEDIUM → HIGH jeśli dane osobowe w promptach

##### M-DE-03 — BDSG §38 — DSB (Datenschutzbeauftragter)
**Podstawa prawna:** BDSG §38 (Datenschutzbeauftragter — obowiązkowy przy ≥20 stale zatrudnionych przetwarzających dane automatycznie).  
**Analiza:** Dla dev pipeline < 20 osób — brak obowiązku. Przy skalowaniu — wymagany.  
**Severity:** LOW

---

### 3. AI ACT — EU 2024/1689

#### MEDIUM

##### M-AI-01 — Art.14 AI Act — Human Oversight — Status SPEŁNIONY
**Podstawa prawna:** Rozporządzenie EU 2024/1689 art.14 (human oversight measures).  
**Analiza:** `human_gate` table z polami `mode`, `deferred_until`, `escalated_to`, `category`, `priority` wskazuje na zaawansowany mechanizm kontroli ludzkiej:
- Możliwość zawieszenia decyzji automatycznych (`deferred_until`),
- Eskalacja do człowieka (`escalated_to`, `escalation_reason`),
- Kategoryzacja (`category`) → selektywna kontrola.

Multi-agent pipeline z human-gate **spełnia art.14** AI Act o ile dokumentacja systemu (art.11) zawiera opis mechanizmu nadzoru.  

**Brak:** Dokumentacja techniczna systemu AI (art.11 AI Act) — karta systemu z: opisem funkcji, limitami, mechanizmem oversight.  
**Severity:** MEDIUM

##### M-AI-02 — AI Act — Klasyfikacja Ryzyka
**Analiza:** SYLION to wewnętrzny pipeline developerski — brak klasyfikacji "high-risk AI system" (Annex III AI Act). Kategoria: **general purpose AI** lub **limited risk** → minimalne wymagania.  
**Status:** OK, brak obowiązków wysokiego ryzyka.  
**Severity:** LOW

---

## TABELA PODSUMOWUJĄCA

| ID | Regulacja | Severity | Opis |
|----|-----------|----------|------|
| C-PL-01 | RODO art.30 | CRITICAL | Brak RoPA |
| C-PL-02 | RODO art.32 | CRITICAL | API Keys hardcoded |
| C-DE-01 | DSGVO/BDSG §64 | CRITICAL | API Keys hardcoded |
| H-PL-01 | RODO art.17 | HIGH | DSR niekompletny |
| H-PL-02 | RODO art.5.1.e | HIGH | Retencja bez dokumentacji |
| H-DE-01 | BDSG §26 | HIGH | Dane pracownicze |
| H-DE-02 | BDSG §35 | HIGH | Procedura usunięcia DE |
| M-PL-01 | KSeF/JPK | N/A | Nie dotyczy dev pipeline |
| M-PL-02 | RODO art.13 | MEDIUM | Brak klauzuli info |
| M-DE-01 | GoBD/HGB | OK | Audit_log nie jest doc. księgowym |
| M-DE-02 | DSGVO art.44 | MEDIUM | Brak SCC dla API |
| M-AI-01 | AI Act art.14 | MEDIUM | Human-gate OK, brak dok. |

**Priorytet naprawczy:** C-PL-01 (RoPA) → C-PL-02/C-DE-01 (API keys) → H-DE-01/H-DE-02 (BDSG procedury)
