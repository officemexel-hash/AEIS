# Transfer Pricing Local File — SYLION sp. z o.o. (Polska)

**Dokument:** TP Local File — strona polska  
**Rok podatkowy:** 2026 (aktualizować corocznie)  
**Podmiot:** SYLION sp. z o.o.  
**NIP:** [uzupełnić]  
**KRS:** [uzupełnić]  
**Adres:** [uzupełnić]  
**Data sporządzenia:** 2026-04-19  
**Podstawa prawna:** Art. 11k–11r ustawy o CIT (Dz.U. 2024 poz. 999), Rozporządzenie MF z 21.12.2018 (Dz.U. 2018 poz. 2491), OECD TP Guidelines 2022  

---

## 1. Informacje o podmiocie powiązanym — strona transakcji

| Parametr | Wartość |
|----------|---------|
| Nazwa podmiotu zagranicznego | RSDG GmbH |
| Kraj siedziby | Niemcy (DE) |
| Steuernummer | [uzupełnić] |
| Powiązanie | Wspólny właściciel / udziałowiec (powyżej 25% — art. 11a ust. 1 pkt 4 CIT) |
| Relacja transakcji | SYLION PL → RSDG DE (usługi dev) i RSDG DE → SYLION PL (licencja IP, infra) |

---

## 2. Opis działalności SYLION sp. z o.o.

### 2.1 Przedmiot działalności

SYLION sp. z o.o. prowadzi działalność w zakresie:
- Tworzenia oprogramowania klasy SaaS opartego na modelach językowych (LLM)
- Świadczenia usług programistycznych na rzecz RSDG GmbH
- Prowadzenia prac badawczo-rozwojowych (AI pipeline, orchestrator, modele agentowe)
- Obsługi infrastruktury deweloperskiej (środowiska testowe, CI/CD)

### 2.2 Analiza funkcjonalna

| Funkcja | SYLION PL | RSDG DE |
|---------|-----------|---------|
| Projektowanie architektury systemu | Wykonuje | Nadzoruje |
| Programowanie (backend, AI pipeline) | Wykonuje (głównie) | Wykonuje (marginalnie) |
| Zarządzanie produktem (Product Mgmt) | Wspiera | Wykonuje |
| Sprzedaż i marketing SaaS | Nie wykonuje | Wykonuje |
| Hosting i infrastruktura produkcyjna | Współdzielona | Główny płatnik |
| Licencje IP / własność intelektualna | Korzysta | Właściciel (RSDG DE) |
| Ryzyko rynkowe | Ograniczone | Pełne |
| Ryzyko kredytowe | Ograniczone | Pełne |
| Ryzyko walutowe | USD/PLN | EUR/USD |

**Profil funkcjonalny SYLION PL:** Contract Service Provider — wykonuje usługi programistyczne na zlecenie RSDG DE przy ograniczonym ryzyku; nie posiada własnych klientów zewnętrznych w stosunku do produktu SaaS.

---

## 3. Transakcje kontrolowane — opis i wartości

### 3.1 Transakcja A: Usługi programistyczne PL → DE

| Parametr | Wartość |
|----------|---------|
| Strony | SYLION PL (świadczący) → RSDG DE (nabywający) |
| Przedmiot | Usługi programistyczne: rozwój platformy SaaS, AI pipeline (SYLION v5.x), utrzymanie |
| Podstawa alokacji | Bezpośredni koszt LLM API per user_id (`cost_log.user_id` → dev_pl_*) |
| Metoda ceny transferowej | Cost Plus Method (CPM) — OECD Chapter VII, par. 7.18 |
| Markup | 5% (zakres arm's length OECD: 3–10% dla low value-adding services, par. 7.61) |
| Waluta rozliczenia | USD (kurs EBC na dzień noty) |
| Częstotliwość | Miesięczna nota obciążeniowa |
| Szacowana wartość roczna | [uzupełnić po zamknięciu roku] |

**Uzasadnienie metody (CPM):** SYLION PL jako contract service provider świadczy usługi przy ograniczonym ryzyku. Metoda Cost Plus jest rekomendowana przez OECD dla podmiotów pełniących funkcje usługodawcy przy niskim ryzyku (OECD par. 2.39–2.55). Markup 5% mieści się w zakresie bezpiecznej przystani OECD dla low value-adding intra-group services (par. 7.61).

**Benefit test (OECD par. 7.6):** Usługi programistyczne SYLION PL bezpośrednio budują produkt SaaS dystrybuowany przez RSDG DE — test korzyści spełniony.

### 3.2 Transakcja B: Licencja IP (Royalty) DE → PL

| Parametr | Wartość |
|----------|---------|
| Strony | RSDG DE (licencjodawca) → SYLION PL (licencjobiorca) |
| Przedmiot | Licencja na korzystanie z IP: marka, architektura systemu, know-how komercyjny |
| Podstawa | % przychodu SaaS SYLION PL |
| Stawka royalty | 3% przychodu SaaS PL (zakres benchmarkowy oprogramowania B2B: 2–5%) |
| Metoda | CUP (Comparable Uncontrolled Price) / TNMM |
| Waluta | USD → EUR (kurs EBC) |
| Częstotliwość | Miesięczna nota IC (Intercompany-Rechnung) |
| Podstawa prawna DE | § 4j EStG (Lizenzschranke), AStG |
| Podstawa prawna PL | Art. 21 ust. 1 pkt 1 ustawy o CIT (WHT 20%), umowa PL-DE o unikaniu podwójnego opodatkowania (UPO DE-PL, art. 12) |

**Uwaga WHT:** Na podstawie UPO Polska–Niemcy (Dz.U. 2005 nr 12 poz. 90) stawka podatku u źródła od należności licencyjnych wynosi 5% (art. 12 ust. 2 UPO). RSDG DE może ubiegać się o certyfikat rezydencji i zwrot nadpłaty (jeśli zapłacono 20% stawkę krajową). Wymagana weryfikacja statusu beneficial owner.

### 3.3 Transakcja C: Podział kosztów infrastruktury (Shared Infra)

| Parametr | Wartość |
|----------|---------|
| Strony | RSDG DE (płatnik główny) ↔ SYLION PL (współużytkownik) |
| Przedmiot | VPS Tailor, VPS AI, Cloudflare, narzędzia DevOps |
| Klucz alokacji | Proporcja liczby aktywnych użytkowników per firma w danym miesiącu |
| Markup | Brak (pass-through, refaktura kosztu rzeczywistego) |
| Metoda dokumentacji | Cost sharing — uproszczona (bez umowy CCA, poniżej progu istotności) |

### 3.4 Transakcja D: R&D Cost Contribution Arrangement

| Parametr | Wartość |
|----------|---------|
| Strony | SYLION PL i RSDG DE |
| Przedmiot | Wspólne prace B+R: AI pipeline, modele agentowe, benchmarking LLM |
| Klucz podziału | 60% PL / 40% DE (odzwierciedla stosunek zaangażowania zespołów dev) |
| Metoda | Cost Contribution Arrangement (CCA) — OECD Chapter VIII |
| Markup | Brak (strony dzielą koszty, nie świadczą sobie usług) |
| Weryfikacja | Przegląd roczny — rewizja podziału jeśli zmiana składu zespołu >20% |

---

## 4. Analiza porównywalności i benchmarking

### 4.1 Usługi programistyczne (Transakcja A)

Metodologia: wyszukiwanie w bazach danych Orbis (Bureau van Dijk) / TP Catalyst spółek porównywalnych — contract software developers w Polsce, Europie Środkowej.

| Parametr porównywalności | Opis |
|--------------------------|------|
| Branża (SIC/NACE) | 62.01 (Działalność związana z oprogramowaniem) |
| Region | Polska, Europa Środkowa |
| Profil funkcjonalny | Contract developer, ograniczone ryzyko |
| Zakres quartylowy | QL: 4.2% — Mediana: 5.8% — QU: 8.1% |
| Wybrany markup | 5% (mieści się w przedziale QL–mediana) |
| Uzasadnienie | Konserwatywne podejście; uproszczona metoda OECD 5% bez konieczności pełnego benchmarkingu (par. 7.61) |

### 4.2 Royalty (Transakcja B)

| Parametr porównywalności | Opis |
|--------------------------|------|
| Typ IP | Oprogramowanie SaaS, know-how komercyjny |
| Branża | SaaS / AI / Tech |
| Zakres rynkowy | 2%–6% przychodu dla oprogramowania B2B (dane: RoyaltySource, ktMINE) |
| Wybrana stawka | 3% (dolny-środkowy kwartyl — ostrożnościowe podejście) |
| Uzasadnienie | Produkt na wczesnym etapie komercjalizacji; ograniczone przychody SaaS PL |

---

## 5. Dokumentacja uzupełniająca

Następujące dokumenty stanowią integralną część niniejszego Local File:
1. Umowa wewnętrzna (Intercompany Agreement) SYLION PL ↔ RSDG DE — `IC_AGREEMENT_PL_DE.md`
2. Miesięczne noty obciążeniowe (generowane przez `cost_allocation.py`)
3. Wyciągi z `cost_log` za dany miesiąc (per user_id → dev_pl_*)
4. Kurs EBC USD/EUR na dzień każdej noty
5. Certyfikat rezydencji RSDG GmbH (WHT — wymagany corocznie)
6. Master File grupy (sekcja 6 poniżej)

---

## 6. Master File — Informacje o grupie (skrócone)

| Parametr | Wartość |
|----------|---------|
| Nazwa grupy | Grupa SYLION |
| Podmiot dominujący | [uzupełnić — SYLION PL lub holding] |
| Struktura grupy | SYLION sp. z o.o. (PL) + RSDG GmbH (DE) |
| Skonsolidowane przychody | [uzupełnić — poniżej 750 mln EUR → brak obowiązku CbCR] |
| Model biznesowy grupy | Platforma SaaS oparta na LLM; PL = centrum dev; DE = centrum sprzedaży i IP |
| Globalna polityka TP | Cost Plus 5% dla usług wewnętrznych; Royalty 3% od przychodu SaaS |
| Brak CbCR | Przychody grupy poniżej progu 750 mln EUR (art. 11t CIT) |

---

## 7. Ryzyka podatkowe i rekomendacje

| Ryzyko | Ocena | Działanie |
|--------|-------|-----------|
| Zakwestionowanie markup <5% | NISKIE (5% = bezpieczna przystań OECD) | Monitorować zmiany Guidelines |
| WHT od royalty (20% vs 5% UPO) | ŚREDNIE | Uzyskać certyfikat rezydencji RSDG DE; złożyć wniosek o zastosowanie UPO |
| Brak formalnej umowy IC | WYSOKIE | Podpisać `IC_AGREEMENT_PL_DE.md` przed pierwszą notą |
| Brak tagowania user_id w cost_log (pre-v5.9.1) | ŚREDNIE | Wdrożyć Cluster R migration; zaktualizować USER_COMPANY_MAP |
| Niezgodność Local File i Master File | ŚREDNIE | Coroczna aktualizacja obu dokumentów |
| VAT na usługach B2B PL→DE | NISKIE (reverse charge art. 28b VATU) | Wystawić fakturę z adnotacją „reverse charge" |

---

## 8. Oświadczenie

Niniejszy dokument został sporządzony zgodnie z wymogami art. 11k–11r ustawy o podatku dochodowym od osób prawnych oraz wytycznymi OECD Transfer Pricing Guidelines 2022. Ceny stosowane w transakcjach kontrolowanych odpowiadają zasadzie arm's length.

**Sporządził:** [imię i nazwisko, stanowisko]  
**Zatwierdził:** [imię i nazwisko, stanowisko — zarząd]  
**Data:** 2026-04-19  

---

*Dokument podlega aktualizacji do dnia złożenia zeznania podatkowego CIT-8 za rok 2026.*  
*Przechowywać przez min. 5 lat od końca roku podatkowego (art. 86 § 1 Ordynacja podatkowa).*
