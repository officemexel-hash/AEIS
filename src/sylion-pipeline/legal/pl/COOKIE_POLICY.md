# Polityka Cookies — SYLION Pipeline

**Wersja:** 1.0  
**Data:** 2026-04-19  
**Produkt:** SYLION Pipeline v5.9.1  
**Administrator:** {{COMPANY_NAME_PL}}, {{ADDRESS_PL}}  
**Kontakt:** {{CONTACT_EMAIL_PL}}

> **PLACEHOLDER — PRZED DYSTRYBUCJĄ:** Zastąp wszystkie znaczniki `{{…}}` faktycznymi danymi.

---

## 1. Czym są pliki cookie?

Pliki cookie (ciasteczka) to małe pliki tekstowe zapisywane w przeglądarce internetowej przez odwiedzane strony i aplikacje. Służą do przechowywania informacji o sesji, preferencjach użytkownika lub do celów bezpieczeństwa.

---

## 2. Jakich cookies używa SYLION Pipeline?

SYLION Pipeline używa **wyłącznie niezbędnych plików cookie** (ang. *strictly necessary cookies*), które są konieczne do prawidłowego działania aplikacji. System **nie używa**:
- plików cookie analitycznych (Google Analytics itp.),
- plików cookie reklamowych lub remarketingowych,
- plików cookie śledzących aktywność użytkownika pomiędzy serwisami (cross-site tracking),
- plików cookie stron trzecich.

### 2.1 Pełna lista cookies SYLION Pipeline

| Nazwa cookie | Typ | Cel / Przeznaczenie | Czas życia | Atrybuty bezpieczeństwa | Podstawa prawna |
|-------------|-----|---------------------|------------|------------------------|-----------------|
| `sylion_session` | Niezbędny — sesja | Identyfikacja zalogowanej sesji użytkownika; zarządzanie uprawnieniami RBAC (owner/admin/member); utrzymanie stanu uwierzytelnienia | **24 godziny** od logowania | `HttpOnly` — niedostępny dla JavaScript; `Secure` — tylko HTTPS; `SameSite=Strict` — ochrona CSRF | Art. 6 ust. 1 lit. b RODO (niezbędność do świadczenia usługi) — **zgoda nie jest wymagana** |
| `_csrf_token` | Niezbędny — bezpieczeństwo | Ochrona przed atakami Cross-Site Request Forgery (CSRF); walidacja autentyczności żądań HTTP | **30 minut** od wygenerowania (odnawia się przy aktywności) | `Secure` — tylko HTTPS; `SameSite=Strict` | Art. 6 ust. 1 lit. b RODO (niezbędność do zapewnienia bezpieczeństwa usługi) — **zgoda nie jest wymagana** |

### 2.2 Dane sesji przechowywane po stronie serwera

Oprócz pliku cookie, SYLION przechowuje po stronie serwera (w bazie SQLite) następujące dane sesji:

| Dane | Cel | Retencja |
|------|-----|----------|
| ID sesji | Powiązanie cookie z rekordem sesji w bazie | 30 dni od wygaśnięcia |
| Adres IP | Bezpieczeństwo (wykrywanie anomalii) | 30 dni od wygaśnięcia |
| Timestamp logowania | Audit log | 365 dni |
| Rola RBAC | Kontrola dostępu | Czas trwania sesji |

---

## 3. Dlaczego nie wymagamy zgody na te cookies?

Pliki cookie `sylion_session` i `_csrf_token` są zaliczane do **cookies niezbędnych** (ang. *strictly necessary*), dla których:
- **zgoda użytkownika nie jest wymagana** (art. 6 ust. 1 lit. b RODO; motyw 47 RODO),
- nie można z nich zrezygnować bez utraty dostępu do usługi,
- służą wyłącznie do realizacji funkcji technicznych niezbędnych do działania aplikacji.

Stanowisko takie jest zgodne z Wytycznymi Europejskiej Rady Ochrony Danych (EROD) 05/2020 w sprawie zgody (paragraf 40) oraz z interpretacją polskiego organu nadzorczego (UODO).

---

## 4. Jak długo obowiązują cookies?

| Cookie | Czas życia w przeglądarce | Czas retencji danych sesji na serwerze |
|--------|---------------------------|---------------------------------------|
| `sylion_session` | 24 godziny (wygasa po zamknięciu sesji lub 24h od logowania) | 30 dni od wygaśnięcia cookie |
| `_csrf_token` | 30 minut (odnawia się przy aktywności) | Nie jest przechowywany na serwerze |

---

## 5. Jak zarządzać plikami cookie i wycofać zgodę?

Ponieważ SYLION Pipeline używa wyłącznie **niezbędnych cookies sesji**, jedynym sposobem na ich usunięcie (i tym samym zakończenie sesji) jest:

### 5.1 Wylogowanie przez interfejs SYLION
- Kliknij przycisk „Wyloguj" w interfejsie aplikacji,
- System usunie cookie `sylion_session` i `_csrf_token` oraz unieważni sesję po stronie serwera.

### 5.2 Ręczne usunięcie cookies w przeglądarce

**Google Chrome:**  
Ustawienia → Prywatność i bezpieczeństwo → Pliki cookie i inne dane witryn → Znajdź `localhost` lub domenę SYLION → Usuń

**Mozilla Firefox:**  
Ustawienia → Prywatność i bezpieczeństwo → Pliki cookie i dane witryn → Zarządzaj danymi → Usuń

**Microsoft Edge:**  
Ustawienia → Pliki cookie i uprawnienia witryn → Zarządzaj i usuń pliki cookie

**Safari:**  
Preferencje → Prywatność → Zarządzaj danymi witryn → Usuń

### 5.3 Blokowanie cookies przez przeglądarkę

Możesz skonfigurować przeglądarkę, aby blokowała wszystkie pliki cookie. Pamiętaj jednak, że **zablokowanie cookies sesji (`sylion_session`) uniemożliwi zalogowanie się do SYLION Pipeline**.

---

## 6. Cookies a lokalna aplikacja SYLION

SYLION Pipeline jest aplikacją działającą **lokalnie na urządzeniu operatora** (localhost lub prywatna sieć). W odróżnieniu od typowych serwisów internetowych:
- cookies są ustawiane wyłącznie przez domenę/hosta, na którym działa SYLION,
- brak jakichkolwiek cookies zewnętrznych lub śledzących stron trzecich,
- dane nie są przesyłane do zewnętrznych serwerów analitycznych,
- w środowisku produkcyjnym zalecamy atrybut `Secure` (HTTPS) oraz konfigurację `SameSite=Strict`.

---

## 7. Zmiany w Polityce Cookies

W przypadku wprowadzenia nowych rodzajów plików cookie, niniejsza Polityka zostanie zaktualizowana i podana do wiadomości użytkowników z co najmniej 14-dniowym wyprzedzeniem. Kontynuowanie korzystania z Usługi po dacie wejścia zmian w życie oznacza ich akceptację.

---

## 8. Kontakt i organ nadzorczy

**Kontakt:** {{CONTACT_EMAIL_PL}}

W przypadku pytań lub wątpliwości dotyczących przetwarzania danych w cookies masz prawo wnieść skargę do organu nadzorczego:

**Polska — UODO:**  
Urząd Ochrony Danych Osobowych  
ul. Stawki 2, 00-193 Warszawa  
https://uodo.gov.pl

---

## Instrukcja Wypełnienia Placeholderów

| Placeholder | Opis |
|-------------|------|
| `{{COMPANY_NAME_PL}}` | Pełna nazwa firmy lub imię i nazwisko administratora |
| `{{ADDRESS_PL}}` | Adres siedziby |
| `{{CONTACT_EMAIL_PL}}` | Adres e-mail do kontaktu RODO/cookies |

---

*Polityka Cookies v1.0 | SYLION Pipeline v5.9.1 | 2026-04-19*  
*Cookies: wyłącznie niezbędne (art. 6 ust. 1 lit. b RODO). Brak cookies analitycznych, reklamowych ani śledzących.*
