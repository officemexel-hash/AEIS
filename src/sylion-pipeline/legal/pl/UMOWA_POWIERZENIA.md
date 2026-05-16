# Umowa Powierzenia Przetwarzania Danych Osobowych

**na podstawie art. 28 Rozporządzenia Parlamentu Europejskiego i Rady (UE) 2016/679 (RODO)**

**Wersja:** 1.0  
**Data:** 2026-04-19  
**Produkt:** SYLION Pipeline v5.9.1

---

## Strony

**Administrator Danych (Zleceniodawca):**

```
Nazwa:   {{CLIENT_COMPANY_NAME}}
Adres:   {{CLIENT_ADDRESS}}
NIP/KRS: {{CLIENT_KRS_NIP}}
E-mail:  {{CLIENT_CONTACT_EMAIL}}
```

(dalej: „**Administrator**")

**Podmiot Przetwarzający (Zleceniobiorca):**

```
Nazwa:   {{COMPANY_NAME_PL}}
Adres:   {{ADDRESS_PL}}
NIP/KRS: {{KRS_NIP_PL}}
E-mail:  {{CONTACT_EMAIL_PL}}
```

(dalej: „**Procesor**")

Administrator i Procesor są dalej łącznie określani jako „**Strony**".

---

## Preambuła

Strony zawarły umowę główną na korzystanie z oprogramowania SYLION Pipeline v5.9.1 (dalej: „**Umowa Główna**"), w ramach której Procesor może przetwarzać dane osobowe powierzone przez Administratora. Niniejsza Umowa Powierzenia Przetwarzania Danych (dalej: „**DPA**") określa szczegółowe zasady przetwarzania danych osobowych zgodnie z wymogami art. 28 ust. 3 RODO.

---

## §1. Przedmiot, charakter i cel przetwarzania

1. Przedmiotem niniejszej DPA jest powierzenie przez Administratora Procesorowi przetwarzania danych osobowych w związku ze świadczeniem usług SYLION Pipeline v5.9.1.
2. Charakter przetwarzania: przetwarzanie techniczne — uwierzytelnianie, zarządzanie sesją, logowanie audytowe, orkiestracja potoku AI.
3. **Cel przetwarzania:** świadczenie Usługi zgodnie z Umową Główną — analiza kodu, obsługa dashboardu, generowanie raportów AI.
4. Przetwarzanie odbywa się wyłącznie na **udokumentowane polecenie Administratora**, chyba że Procesor jest zobowiązany do przetwarzania na mocy prawa Unii lub prawa polskiego (w takim przypadku Procesor niezwłocznie informuje Administratora o tym obowiązku prawnym przed rozpoczęciem przetwarzania, o ile prawo to nie zakazuje takiej informacji ze względu na ważny interes publiczny).

---

## §2. Czas trwania przetwarzania

Przetwarzanie danych osobowych trwa przez czas obowiązywania Umowy Głównej. Po jej wygaśnięciu lub rozwiązaniu Procesor usuwa lub zwraca Administratorowi wszelkie powierzone dane osobowe, zgodnie z §10 niniejszej DPA.

---

## §3. Rodzaj danych osobowych

W ramach niniejszej DPA Procesor przetwarza następujące kategorie danych osobowych:

| Kategoria | Przykłady | Retencja |
|-----------|-----------|----------|
| Dane konta operatora | Nazwa użytkownika, skrót hasła (argon2id) | Do rozwiązania konta |
| Dane sesji | ID sesji, IP, czas logowania, rola RBAC | 30 dni od wygaśnięcia |
| Dziennik zdarzeń (audit log) | Nazwa użytkownika, typ akcji, timestamp, ID obiektu | 365 dni |
| Historia przesyłania (upload_history) | ID użytkownika, nazwa pliku, timestamp | 90 dni |
| Dziennik kosztów AI (cost_log) | user_id, model AI, liczba tokenów, koszt | 90 dni |
| Treść promptów (jeśli zawierają dane os.) | Kod, zapytania, dokumenty | Czas trwania sesji / pipeline run |

> Administrator jest odpowiedzialny za zapewnienie, że powierzone dane są przetwarzane zgodnie z RODO, w szczególności w zakresie podstawy prawnej przetwarzania.

**Dane szczególnych kategorii (art. 9 RODO):** SYLION Pipeline **nie jest przeznaczony** do przetwarzania danych szczególnych kategorii. Administrator zobowiązuje się nie wprowadzać takich danych do systemu bez uprzedniego uzyskania odpowiedniej zgody i poinformowania Procesora.

---

## §4. Kategorie podmiotów danych

Przetwarzaniu podlegają dane osobowe następujących kategorii podmiotów:
- Operatorzy systemu (pracownicy lub zleceniobiorcy Administratora korzystający z SYLION Pipeline),
- Osoby, których dane mogą być zawarte w treści promptów i dokumentów przesyłanych do analizy (o ile Administrator zdecyduje o ich przesłaniu — Administrator ponosi za to odpowiedzialność).

---

## §5. Obowiązki Procesora

Procesor zobowiązuje się do:

### 5.1 Przetwarzania wyłącznie na polecenie
Przetwarzania danych osobowych wyłącznie na udokumentowane polecenie Administratora (w tym w zakresie przekazywania danych do państw trzecich), chyba że przepis prawa stanowi inaczej.

### 5.2 Poufności personelu
Zapewnienia, że osoby upoważnione do przetwarzania danych osobowych są związane zobowiązaniem do zachowania poufności lub podlegają odpowiedniemu ustawowemu obowiązkowi zachowania tajemnicy.

### 5.3 Środków bezpieczeństwa (art. 32 RODO)
Wdrożenia odpowiednich technicznych i organizacyjnych środków bezpieczeństwa, w szczególności:
- hashing haseł algorytmem argon2id;
- RBAC (kontrola dostępu oparta na rolach);
- audit log każdej akcji z timestampem;
- rate limiting prób logowania;
- cookies sesji: HttpOnly, Secure, SameSite=Strict;
- automatyczne retencja i prune zgodnie z §3.

### 5.4 Podprocesorów (art. 28 ust. 2 i 4 RODO)
Przestrzegania zasad opisanych w §6 niniejszej DPA.

### 5.5 Pomocy przy realizacji praw podmiotów danych
Wspomagania Administratora, w zakresie możliwości technicznych, w wywiązywaniu się z obowiązku odpowiadania na żądania podmiotów danych w zakresie praw wynikających z art. 15–22 RODO (dostęp, sprostowanie, usunięcie, ograniczenie, przenoszenie, sprzeciw).  
**Dostępne mechanizmy techniczne:** GET /api/auth/me/export (art. 15, 20), DELETE /api/auth/me/data (art. 17).

### 5.6 Pomocy przy naruszeniach ochrony danych
W przypadku wykrycia naruszenia ochrony danych osobowych Procesor powiadamia Administratora **niezwłocznie, nie później niż w ciągu 24 godzin** od stwierdzenia naruszenia, w celu umożliwienia Administratorowi dopełnienia obowiązku zgłoszenia do UODO w terminie 72 godzin (art. 33 RODO). Powiadomienie zawiera: opis charakteru naruszenia, kategorie i przybliżoną liczbę podmiotów danych, opis prawdopodobnych konsekwencji, opis środków zaradczych.

### 5.7 Pomocy przy DPIA
Wspomagania Administratora w przeprowadzeniu oceny skutków dla ochrony danych (art. 35 RODO) oraz uprzednich konsultacjach z organem nadzorczym (art. 36 RODO).

### 5.8 Usunięcia lub zwrotu danych
Po zakończeniu świadczenia usług Procesor, według wyboru Administratora, usuwa lub zwraca wszelkie powierzone dane osobowe i usuwa istniejące kopie, chyba że prawo Unii lub prawo polskie wymaga przechowywania danych osobowych. Termin: 30 dni od wygaśnięcia lub rozwiązania Umowy Głównej.

### 5.9 Prawa do audytu
Udostępniania Administratorowi wszelkich informacji niezbędnych do wykazania spełnienia obowiązków wynikających z art. 28 RODO oraz umożliwiania przeprowadzania audytów (w tym inspekcji) przez Administratora lub upoważnionego przez niego audytora.  
W pierwszej kolejności akceptuje się: raport SOC 2 Type II (jeśli dostępny) lub kwestionariusz bezpieczeństwa. Audyt on-site jest możliwy z 30-dniowym wyprzedzeniem, nie częściej niż raz w roku, na koszt Administratora.

---

## §6. Podprocesorzy

1. Administrator udziela ogólnego pisemnego upoważnienia (art. 28 ust. 2 RODO) na korzystanie z podprocesorów wymienionych poniżej.
2. Procesor informuje Administratora o wszelkich planowanych zmianach (dodaniu lub zastąpieniu) podprocesorów z **14-dniowym** wyprzedzeniem, umożliwiając Administratorowi wniesienie sprzeciwu.
3. Aktualna lista podprocesorów:

| Podprocesor | Kraj | Cel przetwarzania | Mechanizm transferu |
|------------|------|------------------|---------------------|
| OpenAI, Inc. | USA | Zewnętrzny model AI — GPT | EU-US DPF + DPA z OpenAI |
| Anthropic, PBC | USA | Zewnętrzny model AI — Claude | SCC Moduł 2 (2021/914) + DPA z Anthropic |
| Google LLC | USA/EU | Zewnętrzny model AI — Gemini | EU-US DPF + DPA z Google |
| Perplexity AI, Inc. | USA | Wyszukiwanie AI | SCC Moduł 2 (2021/914) + DPA z Perplexity |
| xAI, Inc. | USA | Zewnętrzny model AI — Grok | SCC Moduł 2 (2021/914) + DPA w weryfikacji |
| DeepSeek AI Co., Ltd. | Chiny | Zewnętrzny model AI — DeepSeek | **TIA w toku — aktywacja warunkowa** |

4. Procesor zapewnia, że podprocesorzy są zobowiązani do przestrzegania wymagań ochrony danych co najmniej równoważnych niniejszej DPA (art. 28 ust. 4 RODO).
5. Procesor pozostaje w pełni odpowiedzialny wobec Administratora za wypełnienie przez podprocesora jego zobowiązań.

---

## §7. Transfery danych poza EOG

1. Transfery danych do podprocesorów mających siedzibę poza Europejskim Obszarem Gospodarczym (EOG) odbywają się wyłącznie z zastosowaniem odpowiednich zabezpieczeń (art. 46 RODO):
   - Standardowych Klauzul Umownych (SCC) Moduł 2 (decyzja Komisji 2021/914) — patrz Załącznik SCC_Module_2.md,
   - Decyzji adekwatności (EU-US DPF dla kwalifikujących się podmiotów z USA),
   - Transfer Impact Assessment (TIA) wymaganego przez Wytyczne EROD 05/2021.
2. Dla DeepSeek AI Co., Ltd. (Chiny): transfer PII jest zakazany do czasu zakończenia TIA i podpisania SCC Moduł 2.

---

## §8. Obowiązki Administratora

Administrator zobowiązuje się do:
1. Przekazywania do przetwarzania wyłącznie danych osobowych zbieranych zgodnie z RODO, w szczególności posiadając ważną podstawę prawną przetwarzania.
2. Nieumieszczania w promptach danych szczególnych kategorii (art. 9 RODO) bez uprzedniej zgody Procesora.
3. Niezwłocznego informowania Procesora o wszelkich zmianach w zakresie przetwarzanych danych osobowych.
4. Zapewnienia odpowiednich zasobów technicznych (szyfrowanie, kontrola dostępu) dla środowiska produkcyjnego zgodnie z zaleceniami Procesora.

---

## §9. Kontakt i punkty kontaktowe

| Strona | Punkt kontaktowy DPA | Adres e-mail |
|-------|----------------------|-------------|
| Administrator | {{CLIENT_DPA_CONTACT}} | {{CLIENT_CONTACT_EMAIL}} |
| Procesor | {{COMPANY_DPA_CONTACT}} | {{CONTACT_EMAIL_PL}} |

---

## §10. Zwrot / usunięcie danych po zakończeniu umowy

1. W terminie 30 dni od wygaśnięcia lub rozwiązania Umowy Głównej Procesor:
   a) Na wybór Administratora: usunie wszystkie dane osobowe lub zwróci je w formacie JSON/CSV i potwierdzi usunięcie na piśmie;  
   b) Usunie dane ze wszystkich kopii zapasowych w regularnym harmonogramie (max. 90 dni).
2. Procesor zachowuje prawo do przechowywania danych osobowych wyłącznie w zakresie i przez czas wymagany przez prawo Unii lub prawo polskie.

---

## §11. Prawo właściwe i jurysdykcja

Niniejsza DPA podlega prawu polskiemu. Wszelkie spory wynikające z niniejszej DPA będą rozstrzygane przez sąd właściwy dla siedziby Procesora.

---

## §12. Postanowienia końcowe

1. Niniejsza DPA stanowi integralną część Umowy Głównej.
2. W przypadku sprzeczności pomiędzy DPA a Umową Główną, w zakresie ochrony danych osobowych, pierwszeństwo ma DPA.
3. Zmiany niniejszej DPA wymagają formy pisemnej pod rygorem nieważności.

---

## Załączniki

- Załącznik 1: Lista podprocesorów (aktualizowana przez Procesora)
- Załącznik 2: Techniczne i organizacyjne środki bezpieczeństwa (TOM)
- Załącznik 3: Standardowe Klauzule Umowne — SCC Moduł 2 (patrz: SCC_Module_2.md)

---

**Podpisy:**

| Administrator | Procesor |
|---------------|---------|
| {{CLIENT_COMPANY_NAME}} | {{COMPANY_NAME_PL}} |
| Miejscowość, Data: _________________ | Miejscowość, Data: _________________ |
| Podpis: __________________________ | Podpis: __________________________ |
| Funkcja: _________________________ | Funkcja: _________________________ |

---

## Instrukcja Wypełnienia Placeholderów

| Placeholder | Opis |
|-------------|------|
| `{{CLIENT_COMPANY_NAME}}` | Pełna nazwa firmy Administratora (klient) |
| `{{CLIENT_ADDRESS}}` | Adres siedziby Administratora |
| `{{CLIENT_KRS_NIP}}` | Numer KRS/NIP Administratora |
| `{{CLIENT_CONTACT_EMAIL}}` | E-mail kontaktowy Administratora ds. RODO |
| `{{CLIENT_DPA_CONTACT}}` | Imię, nazwisko i funkcja osoby kontaktowej ds. DPA po stronie Administratora |
| `{{COMPANY_NAME_PL}}` | Pełna nazwa firmy Procesora (Dostawcy SYLION) |
| `{{ADDRESS_PL}}` | Adres siedziby Procesora |
| `{{KRS_NIP_PL}}` | Numer KRS/NIP Procesora |
| `{{CONTACT_EMAIL_PL}}` | E-mail kontaktowy Procesora ds. RODO |
| `{{COMPANY_DPA_CONTACT}}` | Imię, nazwisko i funkcja osoby kontaktowej ds. DPA po stronie Procesora |

---

*Umowa Powierzenia Przetwarzania Danych v1.0 | SYLION Pipeline v5.9.1 | 2026-04-19*  
*Podstawa prawna: art. 28 Rozporządzenia (UE) 2016/679 (RODO).*  
*Dokument wymaga weryfikacji przez radcę prawnego przed podpisaniem.*
