# Checklist onboardingu — SYLION v5.9.1

10 kroków od instalacji do pełnego wdrożenia.

Odhaczaj kroki w miarę postępów. Cały proces zajmuje ok. 20–30 minut.

---

## Krok 1: Weryfikacja wymagań systemowych

Przed instalacją potwierdź, że spełniasz wymagania:

- [ ] Python 3.12 lub nowszy zainstalowany i dostępny w PATH
- [ ] Minimum 8 GB RAM dostępne
- [ ] Minimum 2 GB wolnego miejsca na dysku
- [ ] System operacyjny: Linux, macOS lub Windows 10/11
- [ ] Dostęp do internetu (potrzebny do instalacji zależności i korzystania z modeli AI)

Weryfikacja Pythona:

```bash
python --version
```

---

## Krok 2: Pobranie i instalacja

- [ ] Repozytorium pobrane (`git clone` lub archiwum ZIP)
- [ ] Instalator uruchomiony (`./install.sh` lub `install.bat`)
- [ ] Instalacja zakończyła się bez błędów (ostatnia linia: `SYLION installed successfully`)

Jeśli instalacja nie powiodła się, sprawdź [TROUBLESHOOTING_PL.md](TROUBLESHOOTING_PL.md), problemy 9 i 15.

---

## Krok 3: Konfiguracja kluczy API

- [ ] Plik `.env` otwarty w edytorze
- [ ] Klucz Anthropic API wpisany (`ANTHROPIC_API_KEY`)
- [ ] Klucz OpenAI API wpisany (`OPENAI_API_KEY`)
- [ ] Klucz Google API wpisany (`GOOGLE_API_KEY`)
- [ ] Plik `.env` zapisany

Jeśli nie masz wszystkich kluczy, możesz uruchomić SYLION z brakującymi — modele bez klucza będą wyłączone z council.

---

## Krok 4: Pierwsze uruchomienie serwera

- [ ] Serwer uruchomiony: `python dashboard/start.py`
- [ ] W konsoli widoczny setup token (`[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX`)
- [ ] Setup token skopiowany do schowka lub zapisany

---

## Krok 5: Ustawienie hasła administratora

- [ ] Otwarta strona `http://localhost:8421/setup` w przeglądarce
- [ ] Setup token wklejony w polu "Setup Token"
- [ ] Hasło administratora ustawione (minimum 12 znaków, zalecane: litery + cyfry + znak specjalny)
- [ ] Konto administratora utworzone pomyślnie

---

## Krok 6: Pierwsze logowanie i eksploracja Dashboard

- [ ] Zalogowano się przez `http://localhost:8421/login`
- [ ] Dashboard załadowany poprawnie
- [ ] Sprawdzona zakładka **Pipeline** — lista stage'ów widoczna
- [ ] Sprawdzona zakładka **Agenci** — wyświetleni wszyscy 48 agentów
- [ ] Sprawdzona zakładka **Council** — widoczne cztery modele
- [ ] Sprawdzona zakładka **Ustawienia** — dostępna konfiguracja

---

## Krok 7: Weryfikacja council

- [ ] Otwarta zakładka **Council** w Dashboard
- [ ] Wpisano testowe zapytanie (np. "Opisz krótko co to jest SQL injection")
- [ ] Kliknięto "Uruchom Council"
- [ ] Odpowiedzi od wszystkich czterech modeli pojawiły się w panelu
- [ ] Konsensus wyświetlony na dole panelu

Jeśli któryś model nie odpowiada, sprawdź odpowiedni klucz API w Ustawieniach.

---

## Krok 8: Uruchomienie pierwszego pipeline'u audytu

- [ ] Otwarta zakładka **Pipeline**
- [ ] Nowy pipeline utworzony (przycisk "Nowy pipeline")
- [ ] Dane wejściowe podane (plik lub katalog z kodem)
- [ ] Pipeline uruchomiony
- [ ] Postęp pipeline'u widoczny w panelu
- [ ] Pipeline zakończył się statusem `completed`

Jeśli pipeline utknął, sprawdź [TROUBLESHOOTING_PL.md](TROUBLESHOOTING_PL.md), problem 15.

---

## Krok 9: Konfiguracja backupu

- [ ] Zrozumiana lokalizacja bazy danych: `~/sylion/sylion.db`
- [ ] Skrót do ręcznego backupu przygotowany lub zapamiętany:

```bash
cp ~/sylion/sylion.db ~/backup/sylion_$(date +%Y%m%d_%H%M%S).db
```

- [ ] (Opcjonalnie) Harmonogram automatycznego backupu skonfigurowany (cron na Linuxie/macOS lub Harmonogram zadań na Windows)

Zalecane: backup raz dziennie do osobnego katalogu lub zewnętrznego nośnika.

---

## Krok 10: Dokumentacja — lektura

- [ ] Przeczytany [QUICKSTART_PL.md](QUICKSTART_PL.md) — wiesz jak startować
- [ ] Przejrzany [FAQ_PL.md](FAQ_PL.md) — znasz odpowiedzi na najczęstsze pytania
- [ ] Przejrzany [TROUBLESHOOTING_PL.md](TROUBLESHOOTING_PL.md) — wiesz gdzie szukać pomocy przy problemach
- [ ] Przejrzany [RELEASE_NOTES_v5.9.0_PL.md](RELEASE_NOTES_v5.9.0_PL.md) — wiesz co nowego w tej wersji

---

## Gotowe

Po odhaczeniu wszystkich 10 kroków SYLION jest w pełni wdrożony i gotowy do pracy.

W razie pytań lub problemów: support@sylion.example
