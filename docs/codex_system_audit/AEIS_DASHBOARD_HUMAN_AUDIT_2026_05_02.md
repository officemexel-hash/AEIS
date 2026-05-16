# AEIS - audyt dashboardowy jak operator, 2026-05-02

## Zakres

Audyt wykonany przez lokalny dashboard `http://127.0.0.1:3000`, z klikaniem i wpisywaniem w UI. Scenariusz testowy:

`AeroLab Nexus - SaaS, funding i mobile approvals`

Projekt celowo laczyl SaaS, funding, mobile approvals, Rade Modeli, adversarial critic, Human Gate, Source of Truth, Masterplan, lokalny runtime, opcjonalne VPS jako future approval, testy i audit trail.

## Przeplyw wykonany przez dashboard

1. Utworzono pomysl w Idea Vault.
2. Uruchomiono szybka dyskusje modeli.
3. Promowano pomysl do projektu.
4. Odpowiedziano na pytania operatora:
   - pelniejszy zakres,
   - `hybrid-later` bez realnego provisioningu.
5. Zamrozono Ksiege jako Source of Truth przez Human Gate.
6. Zamrozono Masterplan przez Human Gate.
7. Autoryzowano budowe przez Human Gate.
8. System wykonal build lokalny, walidacje, audyt i broadcast.
9. Otworzono wygenerowany artefakt HTML.
10. W artefakcie przetestowano:
    - brak notatki zrodlowej blokuje intake,
    - fikcyjny URL blokuje source verification,
    - scoring blokuje sie bez `official_source_review`,
    - poprawny wpis z przyszlym deadlinem przechodzi scoring lokalny,
    - eksport dokumentow blokuje sie bez `document_export`,
    - po lokalnym `document_export` eksport przechodzi, a submission zewnetrzny pozostaje zablokowany.
11. W Operator Monitor przetestowano regulacje runtime:
    - `VPS planowane` zmienione testowo na 2 i zapisane przez dashboard,
    - `Srodowiska` zmienione na 3,
    - `Max rownolegle` zmienione na 5,
    - W18 dopisal komende `/runtime ustaw ...`.
12. Uruchomiono i zatrzymano lokalny smoke worker z dashboardu.
13. Po tescie ustawiono `VPS planowane` z powrotem na 0, bez provisioningu i bez kosztu.

## Wyniki runtime

- Projekt: `project_11f22535845c`
- Status: `completed`
- Faza koncowa: `broadcast`
- Artefakt: `src/results/projects/project_11f22535845c/artifacts/app.html`
- Build: `bld_7555626143be`
- Walidacja: pass
- Audyty: 6/6 pass
- VPS/provisioning: nie uruchomiono, `hybrid-later` pozostaje future approval; planowane VPS po tescie: 0.
- Runtime controls: liczba VPS, liczba srodowisk i max rownolegle sa edytowalne z dashboardu i loguja komendy W18.
- Smoke workers: start/stop dziala lokalnie; stan koncowy `Uruchomione: 0/2`.

## Bledy wykryte i poprawione

1. Terminal W18 przykrywal kontrolki autoryzacji budowy.
   - Poprawiono panel projektu: mniejsza wysokosc terminala, mniejsze dokowanie, przewijanie terminala.

2. Round Meta mial niespojny kontrakt:
   - ponowne freeze po realnym zamrozeniu powinno zwracac 400 dla jawnego requestu,
   - legacy request bez body nadal zwraca stan projektu dla kompatybilnosci testow,
   - build authorization ma minimalna klase D4, bo laczy koszt, produkcje i akcje zewnetrzne.

3. Operator Monitor mial widoczny angielski naglowek i tekst `auto-refresh`.
   - Zmieniono na polski naglowek `Kokpit operatora AEIS`,
   - zmieniono label na `odswiezanie co 30 s`,
   - przetlumaczono hero kokpitu.

4. Produkcyjny frontend dzialal przez `next start`, wiec zmiany nie byly widoczne bez rebuild/restart.
   - Wykonano `npm run build`,
   - zrestartowano lokalny frontend na `127.0.0.1:3000`.

5. Operator Monitor mial martwy, ukryty blok tekstu oraz ryzyko mojibake w subtitle.
   - Usunieto martwy blok,
   - widoczne subtitle ustawiono w polskim ASCII.

## Wnioski audytowe

- Human Gate dziala end-to-end dla freeze Ksiegi, freeze Masterplanu i autoryzacji budowy.
- Lokalny build projektu dziala i tworzy artefakt domenowy, nie pusty placeholder.
- Funding flow w artefakcie ma realne blokady lokalne dla zrodel, deadline, scoringu i eksportu.
- Rola `adversarial critic` jest ujeta w intencji i modelach jako critic, ale nadal warto utwardzic ja w UI jako osobna, obowiazkowa rola Rady.
- Klasyfikator nadal zawaza projekt wielodomenowy do `funding`; to jest akceptowalne dla obecnego artefaktu, ale do pelnego AEIS powinien zachowac tagi multi-domain: SaaS, funding, mobile, runtime.

## Weryfikacja

- `npx tsc --noEmit` - pass
- `npm run build` - pass
- `pytest test_projects_routes + round_meta` - 67 passed
- Browser dashboard:
  - `/dashboard/operator-monitor` renderuje polski naglowek,
  - runtime pozwala regulowac planowane VPS, srodowiska i rownoleglosc bez realnego provisioningu,
  - `/projects/project_11f22535845c` pokazuje projekt, artefakt, autoryzacje i W18,
  - artefakt lokalny renderuje i reaguje na klikniecia/formularze.

---

## Retest po poprawkach Codex - 2026-05-02, projekt dashboardowy

### Cel

Sprawdzic od poczatku flow operatora przez dashboard po wykryciu, ze projekt wielodomenowy byl zawazany do `funding`, a twarda rola `adversarial_critic` nie byla jasno widoczna w UI Rady.

### Projekt testowy

- Idea utworzona przez dashboard: `AeroLab Nexus final retest 1777723808485`
- Idea ID: `04af3f59c9ad4bd4b729f2326f878103`
- Projekt ID: `project_29bd966008a5`
- Flow wykonany przez UI:
  1. Skarbiec Pomyslow -> Nowy pomysl.
  2. Szczegoly idei -> Promuj do projektu.
  3. Projekt -> Kogo pytamy -> zatwierdzony sklad Rady.
  4. Projekt -> analizy modeli -> dyskusja -> wniosek Rady.
  5. Projekt -> pytania operatora -> wybrano `direction_full_scope` i `runtime_hybrid_later`.
  6. Projekt -> Zamroz Ksiege -> Human Gate.
  7. Human Gate -> zatwierdzono `source_of_truth_gate`.
  8. Projekt -> Zamroz Masterplan -> Human Gate.
  9. Human Gate -> zatwierdzono `masterplan_gate`.
  10. Projekt -> Autoryzuj budowe z limitem testowym 1 USD -> utworzono Round 3 gate bez deployu i bez kosztu.

### Naprawione bledy

1. `IdeaVault` mial osobna sciezke promocji do projektu i tracil overlay domen wspierajacych.
   - Naprawiono `ai_workspace_routes.py` i `idea_routes.py`, zeby promocja idei uzywala tych samych helperow profilu domenowego co bezposrednie tworzenie projektu.

2. Klasyfikator projektu zawazal zlozony SaaS z funding/mobile/runtime do typu `funding`.
   - Naprawiono profil domenowy: primary zostaje `project_management_system`, a `funding`, `operator_mobile`, `runtime`, `governance` sa domenami wspierajacymi.
   - Potwierdzono w runtime: 24 moduly, obecne `funding_scan`, `mobile_approval_bridge`, `runtime_environment_matrix`, `cross_domain_orchestration`, brak `funding_intake` jako glownego flow.

3. Rola `adversarial_critic` byla ukryta w UI jako ogolny `Krytyk / czerwony zespol`.
   - Backend: dodano twarda role `adversarial_critic` z `required_signature=true`.
   - Council quorum: `weighted_majority_with_adversarial_critic_signature`.
   - Frontend: dodano osobna karte `Adwersarialny krytyk` oraz widoczna twarda regule.

4. Freeze Ksiegi i Masterplanu tworzyl Human Gate z `gate_type=production`.
   - Naprawiono semantyke governance:
     - Ksiegi: `source_of_truth_gate`,
     - Masterplanu: `masterplan_gate`,
     - Round 3 build authorization pozostaje `financial` z payload `financial`, `production`, `external_action`.
   - Rozszerzono walidator governance ticketow o `direction_gate`, `source_of_truth_gate`, `masterplan_gate`.

5. Frontend dzialal przez `next start`, wiec po zmianie UI potrzebowal rebuild/restart.
   - Wykonano `npm run build`.
   - Zrestartowano frontend na `127.0.0.1:3000`.

### Dowody runtime

- Projekt po promocji z dashboardu:
  - `project_kind = project_management_system`
  - domeny: `project_operations`, `funding`, `operator_mobile`, `runtime`, `governance`
  - moduly: 24
  - `adversarial_critic` obecny w `council_plan.members`
  - `adversarial_critic.required_signature = true`
  - quorum wymaga podpisow `critic` i `adversarial_critic`
- Rada modeli:
  - sesja `dca69a924bba`
  - 3 analizy modeli
  - 3 wypowiedzi w dyskusji
  - wniosek Rady gotowy
- Human Gate:
  - stary bledny ticket `production` dla freeze Ksiegi zostal odrzucony przez dashboard jako artefakt sprzed poprawki.
  - nowy ticket Ksiegi: `99c396cf6656420792a879ce74de71ba`, `gate_type=source_of_truth_gate`, zatwierdzony.
  - nowy ticket Masterplanu: `dfd3f1187148481882e6c8d0dd14fdd4`, `gate_type=masterplan_gate`, zatwierdzony.
  - Round 3 ticket: `7a942893977749f18ea97a450513c5e4`, `gate_type=financial`, payload `gate_types=[financial, production, external_action]`, `cost_cap_usd=1`, pending.

### Weryfikacja techniczna

- `npm run lint -- "src/app/(app)/projects/[projectId]/page.tsx"` - pass
- `npm run build` - pass
- `pytest test_round_meta_freeze.py + test_projects_routes.py + test_ai_workspace_routes.py + test_council_hybrid.py` - 239 passed, 6 warnings
- Backend po restarcie: `/api/v1/health` zwraca `status=ok`, `version=3.5.0`, `endpoints=1954`.

### Co zrobiono z wlasnej inicjatywy w ramach zgody "naprawiaj na biezaco"

- Poprawiono obie sciezki promocji idei, bo dashboard uzywal innej niz bezposrednie API projektu.
- Utwardzono `adversarial_critic` w backendzie, quorum i UI.
- Zmieniono semantyke `gate_type` dla freeze Ksiegi/Masterplanu, bo `production` falszowalo obraz Human Gate.
- Odrzucono stary, blednie sklasyfikowany lokalny ticket freeze Ksiegi i utworzono nowy poprawny ticket.

### Czego nie zrobiono

- Nie uruchomiono Hetznera.
- Nie utworzono VPS.
- Nie wykonano deployu produkcyjnego.
- Nie wydano realnego kosztu. Round 3 utworzyl tylko lokalny pending ticket z limitem testowym 1 USD.

## Dogrywka naprawcza UI Rady i Human Gate - 2026-05-02

Zakres naprawiony od razu po wykryciu w klikanym tescie:

- Ekran projektu nie nadpisuje juz gotowej dyskusji Rady pusta tablica z odpowiedzi API. Frontend wybiera pierwsza niepusta liste z `result.rounds`, `result.created` albo summary backendu.
- Po uruchomieniu analizy, dyskusji i konsolidacji Rady UI przechodzi na nastepny etap bez recznego odswiezania.
- Pasek decyzji operatora filtruje smieciowe warianty: pojedyncze `A/B`, sklejki `A / B / ...`, pytania, checklisty robocze i kandydatow do Ksiegi zamiast decyzji.
- Warianty awaryjne sa strategiczne: local-first, governance/adwersarialny krytyk, MVP/future domains, brakujace dowody, Change Proposal.
- Human Gate pokazuje semantyczne bramki po polsku: kierunek, Zrodlo Prawdy, Masterplan. Surowe typy `source_of_truth_gate`, `masterplan_gate`, `direction_gate` nie sa widoczne w UI.
- Bilet autoryzacji budowy rundy 3 ma polski tytul, opis i szczegoly payloadu: limit kosztu, autonomia, bramki.
- Monitor operatora renderuje sie po restarcie; naprawiono synchroniczne `setState` w efektach runtime card.

Weryfikacja:

- `npm run lint -- "src/app/(app)/projects/[projectId]/page.tsx" "src/app/(app)/human-gate/page.tsx" "src/app/(app)/dashboard/operator-monitor/page.tsx"`: 0 bledow, pozostaly tylko stare ostrzezenia o `any` w monitorze.
- `npm run build`: OK.
- `pytest` dla regresji projektow, Idea Vault, freeze gates i Council Hybrid: 239 passed, 6 warnings.
- Browser Use przez dashboard:
  - projekt `project_29bd966008a5`,
  - kliknieta dyskusja Rady,
  - kliknieta konsolidacja Rady,
  - potwierdzono `Dyskusja modeli gotowe` i `Wniosek Rady gotowe`,
  - potwierdzono czyste warianty A-E bez pytan i sklejonych `A / B`,
  - potwierdzono Human Gate bez surowych nazw gate type,
  - potwierdzono render `/dashboard/operator-monitor`.
