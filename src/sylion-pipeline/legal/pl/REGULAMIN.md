# Ogólne Warunki Korzystania z Usługi — SYLION Pipeline

**Produkt:** SYLION Pipeline v5.9.1  
**Wersja dokumentu:** 1.0  
**Data wydania:** 2026-04-19  
**Strona:** {{COMPANY_NAME_PL}} (dalej: „Dostawca")  
**Adres:** {{ADDRESS_PL}} | **KRS/NIP:** {{KRS_NIP_PL}}  
**Kontakt:** {{CONTACT_EMAIL_PL}}

> **PLACEHOLDER — PRZED DYSTRYBUCJĄ:** Zastąp wszystkie znaczniki `{{…}}` faktycznymi danymi.  
> Dokument przeznaczony wyłącznie do stosunków B2B (pomiędzy przedsiębiorcami).  
> Niniejsze OWU podlegają prawu polskiemu. Przed dystrybucją wymagana weryfikacja przez radcę prawnego.

---

## §1. Postanowienia ogólne i zakres

1. Niniejsze Ogólne Warunki Korzystania z Usługi (dalej: „OWU") regulują zasady korzystania z oprogramowania SYLION Pipeline (dalej: „Usługa") przez podmioty gospodarcze (dalej: „Klient").
2. OWU stosuje się wyłącznie do stosunków B2B — pomiędzy przedsiębiorcami w rozumieniu art. 431 Kodeksu cywilnego. Niniejsze OWU **nie mają zastosowania do konsumentów** w rozumieniu art. 221 k.c.
3. Zawarcie umowy następuje przez pisemne (lub elektroniczne w formacie PDF z podpisem kwalifikowanym) przyjęcie oferty Dostawcy lub przez pierwszą aktywację klucza licencyjnego lub klucza API przez Klienta.
4. Wszelkie odbiegające od OWU warunki zakupu lub inne regulaminy Klienta są nieskuteczne, chyba że Dostawca wyraźnie wyraził na nie pisemną zgodę.

---

## §2. Opis Usługi i zakres licencji

1. SYLION Pipeline to **lokalne oprogramowanie AI** do audytu kodu i analizy, działające na infrastrukturze Klienta (on-premise lub private cloud).
2. Usługa jest udostępniana na warunkach licencji MIT (plik `LICENSE.md` dołączony do oprogramowania), z zastrzeżeniami wynikającymi z niniejszych OWU.
3. Licencja obejmuje:
   - instalację i uruchomienie Usługi na infrastrukturze Klienta;
   - korzystanie z interfejsu użytkownika (Dashboard) i API SYLION;
   - dostęp do dokumentacji technicznej.
4. Licencja **nie obejmuje**:
   - modyfikowania kodu źródłowego w celu dystrybucji jako odrębnego produktu;
   - sublicencjonowania bez pisemnej zgody Dostawcy;
   - dostępu do zewnętrznych modeli AI (OpenAI, Anthropic, Google, Perplexity, xAI, DeepSeek) — Klient zawiera odrębne umowy z tymi dostawcami na własny koszt i ryzyko.
5. Dostawca zastrzega prawo do aktualizacji Usługi. Aktualizacje istotnie zmieniające funkcjonalność wymagają uprzedniego powiadomienia Klienta z 14-dniowym wyprzedzeniem.

---

## §3. Brak SLA — świadczenie „as-is"

1. **Usługa jest świadczona w stanie, w jakim się znajduje ("as-is")**, bez gwarancji nieprzerwanego działania, wolności od błędów, przydatności do określonego celu lub osiągnięcia konkretnych wyników.
2. Dostawca **nie gwarantuje** (o ile nie jest to odrębnie uzgodnione na piśmie w Umowie SLA):
   - dostępności Usługi na określonym poziomie (brak SLA);
   - czasu odpowiedzi API zewnętrznych dostawców AI;
   - ciągłości działania przy aktualizacjach.
3. SYLION jest **narzędziem deweloperskim** — wszelkie dane przetwarzane przez AI wymagają weryfikacji przez człowieka. Decyzje biznesowe, prawne lub finansowe podejmowane wyłącznie na podstawie wyników AI są podejmowane na ryzyko Klienta.
4. Środowisko lokalne SQLite (dev) nie jest szyfrowane — konfiguracja produkcyjna jest obowiązkiem Klienta.

---

## §4. Wynagrodzenie i płatności

1. Wynagrodzenie Dostawcy jest określone w odrębnym Zamówieniu lub Ofercie handlowej.
2. Faktury są wystawiane zgodnie z harmonogramem płatności wskazanym w Zamówieniu.
3. Termin płatności: 14 dni od daty wystawienia faktury, chyba że Zamówienie stanowi inaczej.
4. Za opóźnienie w płatności naliczane są odsetki ustawowe za opóźnienie w transakcjach handlowych (art. 7 ustawy z dnia 8 marca 2013 r. o przeciwdziałaniu nadmiernym opóźnieniom w transakcjach handlowych).
5. Dostawca zastrzega prawo do zawieszenia dostępu do Usługi w przypadku opóźnienia płatności przekraczającego 30 dni, po uprzednim wezwaniu do zapłaty.
6. Wszystkie ceny są cenami netto i podlegają powiększeniu o podatek VAT wg stawki obowiązującej w dniu wystawienia faktury.

---

## §5. Ograniczenie odpowiedzialności

1. **Łączna odpowiedzialność Dostawcy** wobec Klienta z tytułu wszelkich roszczeń wynikających lub związanych z niniejszą umową jest ograniczona do kwoty wynagrodzenia netto zapłaconego przez Klienta w ciągu ostatnich **12 miesięcy** poprzedzających zdarzenie wywołujące szkodę.
2. Dostawca **nie ponosi odpowiedzialności** za:
   a) szkody pośrednie, wynikowe, utratę zysku, utratę danych, utratę dobrego imienia;  
   b) przerwy w działaniu spowodowane przez awarie infrastruktury Klienta, zewnętrznych dostawców AI lub siły wyższe;  
   c) wyniki analiz AI — Klient ponosi wyłączną odpowiedzialność za decyzje podjęte na ich podstawie;  
   d) naruszenia RODO wynikające z wprowadzenia przez Klienta danych osobowych do promptów, wbrew zaleceniom Dostawcy.
3. Powyższe ograniczenia nie mają zastosowania w przypadkach:
   a) szkody wyrządzonej umyślnie lub przez rażące niedbalstwo Dostawcy;  
   b) odpowiedzialności za naruszenie życia, zdrowia lub ciała;  
   c) odpowiedzialności z tytułu naruszenia istotnych zobowiązań umownych (Kardinalpflichten), przy czym w takim przypadku odpowiedzialność jest ograniczona do typowej, przewidywalnej szkody.
4. Klient jest zobowiązany do podjęcia rozsądnych kroków w celu zminimalizowania szkody.

---

## §6. Przetwarzanie danych osobowych

1. W zakresie, w jakim Klient powierza Dostawcy przetwarzanie danych osobowych w ramach korzystania z Usługi, strony zawierają odrębną **Umowę Powierzenia Przetwarzania Danych** (art. 28 RODO) — wzór stanowi Załącznik nr 1 lub odrębny dokument DPA.
2. Dostawca przetwarza dane operatorów (dane konta, dane sesji, audit log) jako administrator w zakresie opisanym w Polityce Prywatności (PP_v591_PL.md).
3. Klient przyjmuje do wiadomości, że treści promptów kierowanych do zewnętrznych modeli AI (OpenAI, Anthropic, Google, Perplexity, xAI, DeepSeek) podlegają polityce prywatności tych dostawców.

---

## §7. Przekazanie do sub-procesorów

1. Dostawca informuje Klienta o korzystaniu z następujących zewnętrznych modeli AI jako potencjalnych odbiorców danych:

| Dostawca AI | Kraj | Mechanizm ochrony |
|------------|------|------------------|
| OpenAI, Inc. | USA | EU-US DPF + DPA |
| Anthropic, PBC | USA | SCC Moduł 2 + DPA |
| Google LLC | USA/EU | EU-US DPF + DPA |
| Perplexity AI, Inc. | USA | SCC Moduł 2 + DPA |
| xAI, Inc. | USA | SCC Moduł 2 + DPA (w weryfikacji) |
| DeepSeek AI Co., Ltd. | Chiny | TIA w toku — aktywacja warunkowa |

2. Klient ma prawo wnieść sprzeciw wobec korzystania z konkretnego sub-procesora w ciągu 14 dni od powiadomienia. W przypadku zasadnego sprzeciwu Dostawca dołoży starań, aby zapewnić rozwiązanie alternatywne lub umożliwi Klientowi rozwiązanie umowy bez opłat.

---

## §8. Prawa własności intelektualnej

1. Oprogramowanie SYLION Pipeline jest własnością Dostawcy i udostępniane na warunkach licencji MIT.
2. Klient zachowuje wszelkie prawa do treści wprowadzanych do Usługi (kod źródłowy, dokumenty, prompty).
3. Raporty, analizy i wyniki wygenerowane przez Usługę są własnością Klienta.
4. Dostawca nie rości sobie żadnych praw do własności intelektualnej w odniesieniu do danych Klienta.
5. Klient nie ma prawa korzystać ze znaków towarowych Dostawcy bez jego uprzedniej pisemnej zgody.

---

## §9. Poufność

1. Strony zobowiązują się do zachowania w tajemnicy wszelkich informacji poufnych drugiej strony, uzyskanych w związku z realizacją niniejszej umowy.
2. Zobowiązanie do poufności obowiązuje przez okres **5 lat** od ujawnienia informacji lub od dnia rozwiązania umowy, w zależności od tego, który termin jest późniejszy.
3. Szczegółowe warunki poufności B2B reguluje odrębna Umowa NDA (wzór: NDA_PL.md).

---

## §10. Rozwiązanie umowy

1. **Wypowiedzenie przez Klienta:** Klient może wypowiedzieć umowę z zachowaniem **30-dniowego okresu wypowiedzenia** ze skutkiem na koniec miesiąca, chyba że Zamówienie stanowi inaczej.
2. **Wypowiedzenie przez Dostawcę z ważnego powodu** — Dostawca może wypowiedzieć umowę ze skutkiem natychmiastowym w przypadku:
   a) opóźnienia w płatności przekraczającego 30 dni po bezskutecznym wezwaniu;  
   b) rażącego naruszenia OWU przez Klienta;  
   c) wszczęcia postępowania upadłościowego lub restrukturyzacyjnego wobec Klienta.
3. **Skutki rozwiązania:**  
   a) Klient zobowiązany jest do zaprzestania korzystania z Usługi i usunięcia wszystkich instalacji;  
   b) Dostawca usunie lub zwróci dane Klienta w terminie 30 dni od rozwiązania umowy;  
   c) Klient jest zobowiązany do uregulowania wszelkich zaległych płatności.
4. Klauzule dotyczące ograniczenia odpowiedzialności (§5), poufności (§9), prawa właściwego (§11) i jurysdykcji (§12) przeżywają rozwiązanie umowy.

---

## §11. Prawo właściwe

Niniejsze OWU podlegają prawu polskiemu, w szczególności:
- Ustawie z dnia 23 kwietnia 1964 r. — Kodeks cywilny (Dz.U. z 2023 r. poz. 1610 ze zm.),
- Ustawie z dnia 18 lipca 2002 r. o świadczeniu usług drogą elektroniczną,
- Rozporządzeniu Parlamentu Europejskiego i Rady (UE) 2016/679 (RODO).

Konwencja Narodów Zjednoczonych o umowach międzynarodowej sprzedaży towarów (CISG) jest wyłączona.

---

## §12. Jurysdykcja

1. Wszelkie spory wynikające z niniejszych OWU będą rozstrzygane przez sąd właściwy miejscowo dla siedziby Dostawcy.
2. Strony deklarują wolę polubownego rozstrzygnięcia sporów przed skierowaniem sprawy do sądu. W tym celu strony wyznaczają 30-dniowy termin na negocjacje.

---

## §13. Zmiany OWU

1. Dostawca zastrzega prawo do zmiany niniejszych OWU z 30-dniowym wyprzedzeniem.
2. Klient, który nie akceptuje zmian, może wypowiedzieć umowę przed dniem wejścia zmian w życie bez opłat.
3. Dalsze korzystanie z Usługi po dacie wejścia zmian w życie oznacza ich akceptację.

---

## §14. Postanowienia końcowe

1. Jeśli którekolwiek postanowienie OWU okaże się nieważne lub bezskuteczne, pozostałe postanowienia zachowują moc.
2. Wszelkie zmiany i uzupełnienia OWU wymagają formy pisemnej pod rygorem nieważności.
3. OWU stanowią całość porozumienia stron w zakresie korzystania z Usługi i zastępują wszelkie wcześniejsze uzgodnienia.

---

## Instrukcja Wypełnienia Placeholderów

| Placeholder | Opis | Przykład |
|-------------|------|---------|
| `{{COMPANY_NAME_PL}}` | Pełna nazwa firmy Dostawcy | SYLION sp. z o.o. |
| `{{ADDRESS_PL}}` | Adres siedziby Dostawcy | ul. Przykładowa 1, 00-001 Warszawa |
| `{{KRS_NIP_PL}}` | Numer KRS i NIP Dostawcy | KRS: 0000000000, NIP: 1234567890 |
| `{{CONTACT_EMAIL_PL}}` | Adres e-mail kontaktowy | kontakt@sylion.pl |

---

*Ogólne Warunki Korzystania z Usługi v1.0 | SYLION Pipeline v5.9.1 | SYLION sp. z o.o. | 2026-04-19*  
*Przeznaczone wyłącznie do stosunków B2B. Dokument wymaga weryfikacji przez radcę prawnego przed dystrybucją komercyjną.*
