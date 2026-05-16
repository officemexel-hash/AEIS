# Intercompany Agreement — Umowa Wewnętrzna Grupy
## SYLION sp. z o.o. ↔ RSDG GmbH

**Typ dokumentu:** Intercompany Service & License Agreement  
**Wersja:** 1.0  
**Data zawarcia:** [dd.mm.rrrr]  
**Data wejścia w życie:** [dd.mm.rrrr] (retroaktywnie od [dd.mm.rrrr] jeśli dotyczy)  
**Następna obowiązkowa rewizja:** [31.12.20XX] (corocznie)  

---

## STRONY UMOWY / VERTRAGSPARTEIEN

**Strona A / Partei A:**  
SYLION sp. z o.o.  
ul. [adres], [kod pocztowy] [miasto], Polska  
NIP: [numer]  
KRS: [numer]  
Reprezentowana przez: [imię i nazwisko, stanowisko]  
(zwana dalej: „SYLION PL" lub „Usługodawca")

**Strona B / Partei B:**  
RSDG GmbH  
[Strasse, Hausnummer], [PLZ] [Stadt], Deutschland  
Steuernummer: [numer]  
HRB-Nummer: [numer]  
Vertreten durch: [Vor- und Nachname, Funktion]  
(nachfolgend: „RSDG DE" oder „Auftraggeber" / zwana dalej: „RSDG DE" lub „Nabywca")

---

## PREAMBUŁA / PRÄAMBEL

SYLION PL i RSDG DE są podmiotami powiązanymi w rozumieniu art. 11a ustawy o CIT (PL) oraz § 1 AStG (DE) i wspólnie tworzą Grupę SYLION. Niniejsza umowa reguluje warunki świadczenia usług wewnątrzgrupowych oraz licencjonowania IP zgodnie z zasadą arm's length (OECD TP Guidelines 2022, Article 9 OECD Model Tax Convention) i obowiązującymi przepisami podatkowymi obu krajów.

---

## CZĘŚĆ I — USŁUGI PROGRAMISTYCZNE (PL → DE)
### Abschnitt I — Softwareentwicklungsdienstleistungen

**Art. 1. Przedmiot usług**

1.1 SYLION PL zobowiązuje się świadczyć na rzecz RSDG DE usługi programistyczne obejmujące:
   - (a) Projektowanie, implementację i utrzymanie platformy SaaS SYLION (backend, AI pipeline, orchestrator)
   - (b) Integrację modeli językowych (LLM) z infrastrukturą produkcyjną
   - (c) Prace badawczo-rozwojowe (B+R) w zakresie architektury AI
   - (d) Wsparcie techniczne i utrzymanie systemów

1.2 Zakres prac może być doprecyzowany w miesięcznych Załącznikach (Statement of Work), podpisywanych przez obie Strony.

**Art. 2. Wynagrodzenie za usługi programistyczne**

2.1 Wynagrodzenie obliczane jest metodą **Cost Plus (Kostenaufschlag)**:

```
Wynagrodzenie = Koszt bezpośredni × (1 + Markup)
```

gdzie:
- **Koszt bezpośredni** = suma kosztów LLM API per user_id przypisanego do SYLION PL z tabeli `cost_log` za dany miesiąc
- **Markup** = **5%** (pięć procent) — zgodnie z OECD par. 7.61 (low value-adding intra-group services)

2.2 Zakres arm's length Markup: 3%–10%. Zmiana Markup wymaga aneksu do umowy i uzasadnienia benchmarkingowego.

2.3 Waluta: USD. Przeliczenie na EUR następuje po kursie EBC (Europejski Bank Centralny) z ostatniego dnia roboczego miesiąca rozliczeniowego.

**Art. 3. Fakturowanie i płatność**

3.1 SYLION PL wystawia miesięczną notę obciążeniową (fakturę IC) do 10. dnia miesiąca następującego po miesiącu rozliczeniowym.

3.2 Nota jest generowana automatycznie przez `cost_allocation.py` na podstawie danych z `cost_log`.

3.3 Termin płatności: 30 dni od daty wystawienia noty.

3.4 Faktura VAT: dostawa usług B2B PL→DE objęta mechanizmem odwrotnego obciążenia (art. 28b ustawy o VAT PL / § 13b UStG DE). Na fakturze adnotacja: *„Reverse charge — nabywca rozlicza VAT / Steuerschuldnerschaft des Leistungsempfängers"*.

---

## CZĘŚĆ II — LICENCJA IP (DE → PL)
### Abschnitt II — IP-Lizenz

**Art. 4. Przedmiot licencji**

4.1 RSDG DE jako właściciel IP Grupy SYLION udziela SYLION PL niewyłącznej, niezbywalnej licencji na korzystanie z:
   - (a) Marki i nazwy handlowej „SYLION"
   - (b) Architektura systemu i dokumentacja techniczna
   - (c) Komercyjnego know-how (modele sprzedaży, strategie cenowe SaaS)

4.2 Licencja obejmuje wyłącznie terytorium Polski i jest ograniczona do działalności wewnątrzgrupowej.

**Art. 5. Opłata licencyjna (Royalty)**

5.1 SYLION PL płaci RSDG DE miesięczną opłatę licencyjną:

```
Royalty = Przychód SaaS SYLION PL (miesięczny) × Stawka Royalty
```

gdzie **Stawka Royalty = 3%** (trzy procent).

5.2 Zakres arm's length: 2%–6% dla oprogramowania SaaS B2B (źródła: RoyaltySource, ktMINE). Stawka 3% mieści się w dolnym kwartylu — uzasadniona wczesną fazą komercjalizacji.

5.3 Stawka podlega przeglądowi co 2 lata (lub przy zmianie struktury przychodów >30%).

**Art. 6. Podatek u źródła (WHT)**

6.1 Na podstawie Umowy między Polską a Niemcami w sprawie unikania podwójnego opodatkowania (UPO PL-DE, art. 12): stawka WHT od należności licencyjnych = **5%** (zamiast 20% stawki krajowej PL).

6.2 SYLION PL pobiera WHT 5% i przekazuje do urzędu skarbowego do 7. dnia miesiąca następnego.

6.3 RSDG DE dostarcza SYLION PL aktualny Certyfikat Rezydencji (Ansässigkeitsbescheinigung) do 31.01 każdego roku.

6.4 Netto-Royalty (po WHT 5%) jest wypłacane do RSDG DE na wskazane konto bankowe.

---

## CZĘŚĆ III — INFRASTRUKTURA WSPÓŁDZIELONA
### Abschnitt III — Gemeinsame Infrastruktur

**Art. 7. Podział kosztów infrastruktury**

7.1 Koszty wspólnej infrastruktury (VPS Tailor, VPS AI, Cloudflare, narzędzia DevOps) są dzielone proporcjonalnie do liczby aktywnych użytkowników każdej firmy w danym miesiącu.

7.2 Klucz alokacji:
```
Udział firmy X = Liczba aktywnych userów firmy X / Łączna liczba userów obu firm
```

7.3 RSDG DE jako główny płatnik refakturuje na SYLION PL jej część kosztów infra bez dodatkowego markup (pass-through).

7.4 Faktura refakturacyjna: wystawiana do 10. dnia miesiąca następnego, termin płatności 30 dni.

---

## CZĘŚĆ IV — WSPÓŁPRACA BADAWCZO-ROZWOJOWA (CCA)
### Abschnitt IV — F&E-Kostenumlagevereinbarung (CCA)

**Art. 8. Cost Contribution Arrangement**

8.1 Strony ustanawiają CCA (Cost Contribution Arrangement) zgodnie z OECD Chapter VIII dla wspólnych prac B+R obejmujących: AI pipeline, modele agentowe, benchmarking LLM.

8.2 Podział kosztów B+R: **60% SYLION PL / 40% RSDG DE**.

8.3 Klucz podziału odzwierciedla stosunek zaangażowania zespołów deweloperskich i podlega rocznemu przeglądowi.

8.4 Brak dodatkowego markup — strony dzielą koszty, nie świadczą sobie wzajemnie usług.

8.5 Efekty B+R (IP, patenty, know-how) stają się własnością stron proporcjonalnie do ich udziału kosztowego, chyba że strony postanowią inaczej w formie pisemnego aneksu.

---

## CZĘŚĆ V — POSTANOWIENIA OGÓLNE
### Abschnitt V — Allgemeine Bestimmungen

**Art. 9. Dokumentacja i raportowanie**

9.1 SYLION PL prowadzi pełną dokumentację cen transferowych zgodnie z art. 11k CIT (PL).

9.2 RSDG DE prowadzi dokumentację VP zgodnie z § 90 Abs. 3 AO i GAufzV (DE).

9.3 Obie Strony przechowują dokumentację przez min. 5 lat (PL) / 10 lat (DE) od końca roku podatkowego.

9.4 `cost_allocation.py` jest narzędziem technicznym alokacji — nie zastępuje formalnej decyzji biznesowej Stron w sprawie cen.

**Art. 10. Przegląd i aktualizacja**

10.1 Umowa podlega obligatoryjnemu przeglądowi **raz do roku** (do 31 marca każdego roku za rok poprzedni).

10.2 Strony mogą zmienić warunki cenowe (markup, royalty rate, klucze alokacji) wyłącznie przez pisemny Aneks, podpisany przez upoważnionych reprezentantów obu Stron.

10.3 Każda zmiana struktury biznesowej (nowy produkt, nowy rynek, zmiana właściciela IP) wymaga natychmiastowego przeglądu umowy.

**Art. 11. Rozstrzyganie sporów**

11.1 Strony dążą do polubownego rozwiązania sporów w terminie 60 dni.

11.2 W przypadku braku porozumienia — procedura wzajemnego porozumiewania się (MAP — Mutual Agreement Procedure) na podstawie art. 25 UPO PL-DE lub Konwencji Arbitrażowej EU 90/436/EEC.

11.3 Sądem właściwym (jeśli MAP nie rozstrzygnie): [sąd arbitrażowy do uzgodnienia — np. ICC Paris lub Sąd Arbitrażowy przy KIG Warszawa].

**Art. 12. Prawo właściwe**

12.1 Umowę reguluje prawo polskie (w zakresie obowiązków SYLION PL) i prawo niemieckie (w zakresie obowiązków RSDG DE).

12.2 W kwestiach podatkowych stosuje się UPO PL-DE (Dz.U. 2005 nr 12 poz. 90 / BGBl. 2004 II S. 1304).

**Art. 13. Poufność**

13.1 Treść niniejszej Umowy oraz wszelkie dane finansowe i operacyjne udostępniane na jej podstawie są poufne i nie podlegają ujawnieniu osobom trzecim bez pisemnej zgody drugiej Strony, za wyjątkiem organów podatkowych.

**Art. 14. Wejście w życie i czas trwania**

14.1 Umowa wchodzi w życie z dniem podpisania przez obie Strony.

14.2 Zawarta na czas nieokreślony z możliwością wypowiedzenia z zachowaniem 6-miesięcznego okresu wypowiedzenia.

14.3 Wypowiedzenie nie wpływa na zobowiązania powstałe przed datą jego skuteczności.

---

## ZAŁĄCZNIKI / ANLAGEN

- **Załącznik A / Anlage A:** Mapa user_id → company (USER_COMPANY_MAP) — aktualizowana kwartalnie
- **Załącznik B / Anlage B:** Wzór miesięcznej noty obciążeniowej (PL) / IC-Rechnung (DE)
- **Załącznik C / Anlage C:** Polityka cen transferowych Grupy SYLION (Transfer Pricing Policy)
- **Załącznik D / Anlage D:** Certyfikat rezydencji RSDG GmbH (aktualny rok)
- **Załącznik E / Anlage E:** Certyfikat rezydencji SYLION sp. z o.o. (aktualny rok)

---

## PODPISY / UNTERSCHRIFTEN

**W imieniu SYLION sp. z o.o.:**

| | |
|--|--|
| Imię i nazwisko | _________________________ |
| Stanowisko | _________________________ |
| Data | _________________________ |
| Podpis | _________________________ |

**Im Namen der RSDG GmbH:**

| | |
|--|--|
| Vor- und Nachname | _________________________ |
| Funktion | _________________________ |
| Datum | _________________________ |
| Unterschrift | _________________________ |

---

*Umowę sporządzono w dwóch egzemplarzach, po jednym dla każdej ze Stron.*  
*Der Vertrag wurde in zwei Exemplaren ausgefertigt, je eines für jede Partei.*  
*Języki autentyczne: polski i angielski. W przypadku rozbieżności: wersja angielska jest rozstrzygająca.*  
*Authentische Sprachen: Polnisch und Englisch. Bei Abweichungen ist die englische Fassung maßgeblich.*

---

**Historia wersji / Versionshistorie:**

| Wersja | Data | Zmiana | Zatwierdził |
|--------|------|--------|-------------|
| 1.0 | 2026-04-19 | Wersja inicjalna | — |
