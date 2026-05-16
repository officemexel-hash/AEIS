# CODEX AEIS - audyt finalny runtime/UI względem instrukcji obsługi

Data audytu: 2026-05-02  
Profil audytu: `v10_20260502_codex_04`  
Zakres kanonu: `C:\Users\razor\Desktop\pipeline_glm\docs\instrukcja obslugi`

## Zakres dokumentacji

Przeanalizowany folder `docs\instrukcja obslugi` zawiera 30 plików o łącznym rozmiarze 2 174 834 bajtów. Zakres obejmuje fazy 1-41, warstwy W1-W19, patche D0-D5, waterfall subskrypcji, deep dive W14-W19 oraz symulacje faz 16-41.

Najważniejsze źródła kanonu:

- `00_ADVISOR_LAYER.md`
- `00_architecture_layers_w1_w19.md`
- `00_ARCHITEKTURA_W1_W19.md`
- `00_PATCHES_FAZ.md`
- `01_setup_and_onboarding_v3.md` do `40_41_deploy_closure.md`
- `z00_W14_W19_DEEP_DIVE.md`
- `zPATCH_FAZA_05_D0_D5.md`
- `zPATCH_FAZA_07_SUBSCRIPTION_WATERFALL.md`
- `zPATCH_FAZY_20_25_COUNCIL.md`
- `zSYMULACJE_FAZY_16_25.md` do `zSYMULACJE_FAZY_37_41.md`

## Dowody runtime

Backend:

- URL: `http://127.0.0.1:8010/health`
- Status: `ok`
- Wersja: `3.5.0`
- Moduły: `138`
- Endpointy: `1947`
- DB/event mode: `sqlite`

Frontend:

- URL: `http://127.0.0.1:3000`
- Status: `frontend_ok`

Skan dashboardu przez in-app browser:

- Plik dowodowy: `logs/audit/v10_20260502_codex_04/dashboard_route_polish_helptip_final_clean_scan.json`
- Trasy sprawdzone: `28`
- Błędy: `0`
- Trasy bez HelpTipów: `0`
- Wykryte angielskie markery z listy kontrolnej: `0`

Sprawdzone trasy rdzeniowe: `/`, `/onboarding`, `/ai-models`, `/environments`, `/workspace-defaults`, `/autonomy`, `/coherence-guard`, `/cost-guard`, `/security-guard`, `/quality-guard`, `/provenance-guard`, `/skills`, `/templates-setup`, `/project-start`, `/council-to-ksiega`, `/planning`, `/execution-start`, `/test-center`, `/deploy`, `/idea-vault`, `/human-gate`, `/source-of-truth`, `/model-council`, `/masterplan`, `/audit-trail`, `/memory`, `/funding`, `/mobile`.

## Naprawy wykonane podczas audytu

1. Human Gate dla Idea Vault:
   - Backend nie pozwala już zatwierdzić statusu pozytywnego ani promować idei do projektu, jeśli wymagana decyzja Human Gate nie jest zaakceptowana.
   - Direct API bypass został zamknięty: pozytywna zmiana statusu daje `400`, promocja bez zgody daje `409`.

2. Przepływ człowieka przez dashboard:
   - Utworzono testową ideę V10 przez UI z lokalnym załącznikiem.
   - Sprawdzono blokadę promocji przed Human Gate.
   - Zatwierdzono ticket w `/human-gate`.
   - Wypromowano ideę do projektu `project_5af4f9114dea`.
   - Sprawdzono ekran projektu, W18, komendy `/pomoc`, linki do Księgi, Wykonania i Bramki.

3. Polonizacja i HelpTipy:
   - Dodano globalny HelpTip w topbarze dashboardu.
   - Uzupełniono HelpTipy i polskie teksty w kluczowych ekranach faz 1-41.
   - Usunięto fałszywe komunikaty typu "Backend offline" podczas ładowania.
   - Przetłumaczono dynamiczne etykiety w Strażniku spójności, wdrożeniu, testach, środowiskach, workspace defaults, templates setup, Operator Mobile i ekranach operatora.

4. Brakujące trasy:
   - Dodano alias `/audit-trail` do ekranu audytu.
   - Dodano alias `/mobile` do ekranu Operator Mobile.

5. W18:
   - Lokalna komenda `/pomoc` daje odpowiedź bez zależności od backendowego terminala.
   - Akcja "Kontynuuj Radę" daje feedback zamiast wyglądać jak martwy przycisk.

## Walidacja techniczna

Frontend:

```text
npx tsc --noEmit
PASS
```

Backend:

```text
python -m pytest src\sylion-pipeline\tests\test_idea_vault.py -q
65 passed, 4 warnings
```

Ostrzeżenia testowe dotyczą istniejących deprecacji modułów bezpieczeństwa:

- `hardened_audit` -> `audit_trail_aggregator`
- `secret_provider` -> `key_store_unified`
- `profile_swap` -> `profile_unified`
- `security_audit` -> `audit_trail_aggregator`

## Zgodność z kanonem po naprawach

W sprawdzonym przepływie operatora system jest zgodny z kluczowymi zasadami dokumentacji:

- Modele i system mogą proponować, ale decyzje kierunku/promocji wracają do Human Gate.
- Workspace działa lokalnie, runtime pozostaje local-first.
- Human Gate jest widoczny i blokuje realną promocję projektu.
- Księga, Masterplan, Rada, testy, deploy, guards i wykonanie mają powierzchnie dashboardowe.
- Operator może przejść rdzeniową ścieżkę przez dashboard bez martwych przycisków w sprawdzonym zakresie.
- HelpTipy są dostępne na każdej z 28 sprawdzonych powierzchni.
- UI w sprawdzonym zakresie nie pokazuje już wybranych angielskich markerów krytycznych.

## Pozostały backlog

Nie należy traktować tego audytu jako zamknięcia całego repo w 100%. Repo ma większą powierzchnię niż rdzeniowe trasy faz 1-41.

Pozostaje do osobnego przebiegu:

- pełny skan wszystkich 126 tras frontendu, także demo/legacy/lab,
- pełna redukcja 373 brakujących referencji klient API z raportu pokrycia,
- osobny test runtime funding/autopilot bez finalnych submissionów,
- osobny test Operator Mobile z tokenami i device binding w trybie lokalnym,
- osobna kwalifikacja modułów laboratoryjnych jako CORE/EXTENSION/LAB/LEGACY,
- uporządkowanie deprecacji backendowych modułów security,
- docelowe spięcie audit reportu z Księgą systemową AEIS.

## Ważna uwaga o sekretach i kosztach

W audycie nie użyto przekazanych kluczy API ani danych logowania do Hetznera. Nie wykonano płatnego deployu, nie tworzono zasobów zewnętrznych i nie wykonano żadnego external submit. Zgodnie z kanonem AEIS takie działania wymagają osobnego, świadomego Human Gate.
