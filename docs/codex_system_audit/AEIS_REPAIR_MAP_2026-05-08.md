# AEIS Repair Map 2026-05-08

Status: active repair roadmap
Owner: Codex runtime audit
Rule: Stop-Fix-Restart. Kazdy P0/P1 znaleziony w klikanym tescie blokuje dalsza symulacje do czasu naprawy i ponownego startu scenariusza.

## Dlaczego nie wszystko zostalo naprawione od razu

AEIS nie ma jednego malego bledu. System ma szeroki control-plane: frontend, FastAPI, projekty, Rade, Human Gate, skills, funding, srodowiska, terminal, test center, audytora i teatry runtime. Wczesniejsze poprawki szly wedlug biezacych blockerow ujawnianych przez dashboard. To naprawilo konkretne miejsca, ale nie stworzylo jeszcze jednej globalnej kolejki napraw.

Od teraz naprawy ida wedlug tej mapy:

1. P0: brak mozliwosci wykonania lub falszywe runtime.
2. P1: funkcja istnieje, ale nie jest spieta end-to-end.
3. P2: funkcja dziala, ale jest niespojna, zle opisana albo niepelnie po polsku.
4. P3: ergonomia, porzadkowanie, typowanie, redukcja dlugu.

## Aktualny obraz gotowosci

Dowody runtime z 2026-05-08:

- Backend `8010` dziala: `/health` zwraca `ok`.
- Frontend `3001` dziala.
- OpenAPI: 1615 sciezek.
- Projekty: 22 rekordy przez `/api/v1/projects`.
- Agent theater: `ok=True`, 4 aktorow, 13 guardianow.
- Environment theater: 17 aktorow, 15 relacji, 4 zajete porty.
- UI routes istnieja dla: architecture-layers, project-start, council-to-ksiega, execution-start, test-center, test-center/theater, environments, environments/theater, agents, terminal, funding, skills, human-gate, orchestration/conversations.

Ocena robocza: 58/100.

System jest juz lokalnym control-plane AEIS, ale nie jest jeszcze udowodnionym autonomicznym wykonawca projektow end-to-end.

## P0 - naprawy blokujace

### P0.1 Jedna prawda runtime i portow

Problem:
Frontend uzywa `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010`, ale rownolegle pojawialy sie procesy backendu na `8000`. To grozi testowaniem nie tej instancji.

Naprawa:
- Dodac widoczny panel `Runtime Truth` w operator monitor / terminal.
- Pokazac aktywny backend URL, frontend URL, PID, cwd, git worktree.
- Ostrzegac, gdy istnieje drugi backend AEIS na innym porcie.

Kryterium zaliczenia:
- Dashboard pokazuje `frontend=3001`, `api=8010`, `db`, `cwd`.
- Test manualny nie musi zgadywac, ktory backend jest prawdziwy.

### P0.2 Stop-Fix-Restart jako mechanizm systemowy

Problem:
Zasada Stop-Fix-Restart jest stosowana przez operatora/testera, ale nie jest jeszcze wymuszona globalnie przez AEIS.

Naprawa:
- Dodac centralny `repair_state` dla projektu.
- Kazdy P0/P1 finding z testu UI/API/no-mock/human-like ustawia projekt w `blocked_repair`.
- `execution-start` i test center musza pokazac przyczyne blokady i przycisk restartu scenariusza po naprawie.

Kryterium zaliczenia:
- Wykryty mock/stub zatrzymuje scenariusz.
- Po naprawie system wymaga ponownego startu testu od wskazanego checkpointu.

### P0.3 Mock/stub detection jako twarda bramka

Problem:
No-mock scan istnieje w test center, ale nie jest jeszcze twardo podlaczony do wszystkich symulacji projektow.

Naprawa:
- Wlaczyc `/test-center/no-mock-scan` w kazdej symulacji P1-P5.
- Dodac wynik jako gate do W14.
- Zapisac wynik w raporcie projektu.

Kryterium zaliczenia:
- Kazdy produkt symulacji ma wynik `mock_scan=pass/fail`.
- `fail` blokuje final approval.

## P1 - przeplyw projektu end-to-end

### P1.1 Sciezka P1 od intake do raportu

Zakres:
Najpierw jeden maly projekt, bez VPS, lokalnie.

Kroki testu:
1. `/project-start` - intake.
2. `/ai-models` - modele gotowe.
3. `/council-to-ksiega` - Rada.
4. `/orchestration/conversations` - rozmowy modeli.
5. `/human-gate` - decyzja operatora.
6. `/planning` / `/execution-start` - plan i start.
7. `/environments/theater` - runtime.
8. `/agents` i `/test-center/theater` - agenci/modele.
9. `/test-center` - testy.
10. Raport: dziala / atrapa / zepsute / do naprawy.

Kryterium zaliczenia:
- Powstaje produkt.
- Produkt jest klikany jak czlowiek.
- Testy produktu sa zapisane.
- Raport ma dowody.

### P1.2 Rada modeli musi zmieniac decyzje, nie tylko wyswietlac role

Problem:
Rada ma UI i endpointy, ale trzeba udowodnic, ze decyzje Rady wplywaja na Ksiege, Masterplan i execution.

Naprawa:
- Dodac widoczny `council_decision_id` w Ksieze i Masterplanie.
- Dodac porownanie wariantow A/B/C/D/E.
- Dodac podpis krytyka dla D3+.

Kryterium zaliczenia:
- Zmiana wariantu w Radzie zmienia wynik Masterplanu.
- Brak decyzji Rady blokuje chroniony etap.

### P1.3 Human Gate jako blokada galezi, nie dekoracja

Problem:
Human Gate ma endpointy i UI, ale trzeba konsekwentnie pokazac, ktora galaz jest zablokowana.

Naprawa:
- Kazdy protected action musi miec `gate_id`, `scope`, `blocked_branch`.
- UI pokazuje: co jest zablokowane, kto zatwierdza, jaki jest koszt/ryzyko.

Kryterium zaliczenia:
- Operator widzi, ze np. VPS/produkcja/funding submit jest zablokowany, ale lokalne testy moga isc dalej.

### P1.4 Terminal W18 jako dziennik semantyczny

Problem:
Terminal istnieje, ale nie wszystkie moduly emituja bogate zdarzenia semantyczne.

Naprawa:
- Ujednolic eventy: `project.*`, `council.*`, `gate.*`, `runtime.*`, `test.*`, `funding.*`, `skill.*`.
- Kazde klikniecie kluczowe w dashboardzie powinno miec odpowiednik eventu/komendy w W18.

Kryterium zaliczenia:
- W terminalu widac decyzje Rady, Human Gate, uruchomienia testow, teatry, funding i naprawy.

## P2 - powierzchnie wymagajace dopiecia

### P2.1 Globalne tlumaczenie dashboardu na polski

Problem:
Widoczne sa nadal angielskie i zle zakodowane teksty, np. w auditorze i czesci starszych paneli.

Naprawa:
- Przejsc route-by-route przez dashboard.
- Usunac mojibake.
- Nazwy techniczne zostawiac tylko tam, gdzie sa faktycznymi identyfikatorami.

Kryterium zaliczenia:
- Operator nie trafia na losowe angielskie ekrany w podstawowym flow.

### P2.2 Orchestration auditor

Problem:
Ekran `/orchestration/auditor` dziala, ale ma problemy z kodowaniem znakow i nie jest jeszcze spiety z mapa napraw.

Naprawa:
- Poprawic teksty PL.
- Dodac sekcje `Ostatnie findings`, `Blokery`, `Powiazane testy`, `Restart checkpoint`.
- `Audytuj teraz` powinien tworzyc wpis widoczny w terminalu i raporcie.

Kryterium zaliczenia:
- Auditor pokazuje realne wyniki audytu, nie tylko cadence.

### P2.3 Funding

Problem:
API funding jest szerokie, ale trzeba udowodnic scenariusz: profil firmy -> matching programow -> dokumenty -> scoring -> Human Gate przed wysylka.

Naprawa:
- Test P2 funding NGO.
- Funding Specialist w Radzie musi miec widoczny wklad.
- Submit zewnetrzny musi byc blokowany Human Gate.

Kryterium zaliczenia:
- Raport funding pokazuje scoring, braki dokumentow, rekomendacje i blokade external submit.

### P2.4 Skills lifecycle

Problem:
Skills API dziala, ale autonomiczne tworzenie i dopasowanie skills wymaga dlugiego testu.

Naprawa:
- Uruchomic `/api/v1/skills/lifecycle/long-run-test`.
- Testowac: wykrycie potrzeby -> szkic skillu -> review -> publish/deprecate -> uzycie w projekcie.

Kryterium zaliczenia:
- AEIS sam proponuje skill dla brakujacej kompetencji i zapisuje lifecycle.

### P2.5 Teatry runtime

Status:
- Teatr modeli i agentow istnieje.
- Teatr srodowisk istnieje.

Naprawa:
- Dodac event trail do obu teatrow.
- Dodac przejscie z aktora do konkretnego modulu/projektu/portu.
- Dodac status stalego odswiezania i ostatni blad.

Kryterium zaliczenia:
- Operator widzi kto/co pracuje, dlaczego, na czym i jaki ma status.

## P3 - dlug techniczny i ergonomia

### P3.1 Typowanie frontendu

Problem:
Panele srodowisk i kilka starszych ekranow uzywa `any`.

Naprawa:
- Dodac typy DTO dla environment catalog, theater, agents, council.
- Usuwac `any` przy okazji napraw P1/P2.

Kryterium zaliczenia:
- Nowe panele nie dodaja nowych `any`.

### P3.2 Spis tras i surface map

Problem:
AEIS ma wiele tras, ale operator potrzebuje mapy: ekran -> API -> modul -> warstwa W.

Naprawa:
- Wygenerowac `API/UI Coverage Map`.
- Pokazac to w dashboardzie jako `Mapa pokrycia`.

Kryterium zaliczenia:
- Kazdy ekran ma status: LIVE_VERIFIED, PARTIAL, API_ONLY, UI_ONLY, BROKEN.

## Kolejnosc wykonania

1. P0.1 Runtime Truth.
2. P0.2 Stop-Fix-Restart.
3. P0.3 No-mock hard gate.
4. P1.1 Jeden projekt P1 end-to-end.
5. P1.2 Rada -> Ksiega -> Masterplan.
6. P1.3 Human Gate branch blocking.
7. P1.4 Terminal W18 semantic events.
8. P2.1 Globalne PL/mojibake.
9. P2.2 Auditor jako repair cockpit.
10. P2.3 Funding scenario.
11. P2.4 Skills lifecycle long-run.
12. P2.5 Teatry runtime polish + events.
13. P3.1 Typowanie.
14. P3.2 API/UI coverage map.

## Checkpoint zaliczenia AEIS

AEIS moze zostac uznany za gotowy operacyjnie dopiero gdy:

- P1 przechodzi end-to-end lokalnie.
- P2 funding przechodzi bez external submit.
- P3 multi-agent project przechodzi z Rada i Human Gate.
- P4/P5 wykrywaja przynajmniej jeden blad i przechodza Stop-Fix-Restart.
- Kazdy produkt wypluty przez symulacje jest osobno testowany jak czlowiek.
- Raport koncowy rozroznia: dziala, atrapa, zepsute, naprawione, do naprawy pozniej.
