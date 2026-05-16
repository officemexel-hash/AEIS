# 03 · S5 SCENARIUSZ — "Reuse projektu z pamięci" (MEMORY TEST)

**Data:** 2026-04-24
**Cel:** sprawdzić czy AEIS używa pamięci poprzednich projektów — eksplicytnie prosimy o reuse run_id=4ca263... (S2 TODO CRUD)

## Idea zgłoszona

"Build another TODO list webapp with FastAPI + React + SQLite, **just like the one you built earlier (run 4ca263e9e99e486fb8d1a7e5ca947385). Reuse the skills, plan structure and lessons learned from that previous run.**"

**Oczekiwanie wg kanonu:** similarity search znajduje S2, planner adaptuje/poprawia plan S2 (nie zaczyna od zera), skills reuse, memory reference w evidence.

## Wynik (run_id=d49af53057d94c01a0e5496afb8a5713)

- **10 kroków** (S2 miał 11 — niepodobny)
- **Plan bardziej generyczny niż S2** (❗ regresja zamiast improvement):

| # | S2 plan (oryginał) | S5 plan (z prośbą o reuse) |
|---|---|---|
| 1 | Analyze Requirements | Analyze Requirements |
| 2 | Define API Specifications | Design Architecture |
| 3 | Design Database Schema | Set Up Environment |
| 4 | Design Application Architecture | **Implement Backend** (no FastAPI name) |
| 5 | Setup Development Environment | **Implement Frontend** (no React name) |
| 6 | Implement FastAPI Backend | Write Tests |
| 7 | Implement React Frontend | Conduct Testing |
| 8 | Implement Integrated Testing | Review and Refactor |
| 9 | Conduct Auditing | Deploy Application |
| 10 | Review and Refactor Code | Gather Feedback |
| 11 | Deploy Application | — |

**S5 stracił specyfikę technologiczną (FastAPI, React, Database Schema).** System zignorował referencję do konkretnego runu.

## 🔴 Memory endpoints — stan po probie

| Endpoint | Status |
|---|---|
| `GET /api/v1/memory/search?q=TODO` | **404 Not Found** |
| `GET /api/v1/aeis/similar?run_id=...` | **404 Not Found** |
| `GET /api/v1/aeis/improvements` | 200, body `[]` (pusta lista) |
| `GET /api/v1/pipeline/runs` | 200, 5 runów — ale **brak indeksu similarity** |

**Brak funkcjonalnej pamięci podobnych projektów.** Runtime ma tylko listę runów po ID, brak wyszukiwania treściowego.

## DRIFT K — Pipeline nie czyta swojej własnej bazy runów

W idei podałem konkretny `run_id`. Runtime:
- Nie pobrał planu S2 z bazy przed planowaniem S5
- Nie użył jego plan_id jako template
- Nie dodał do evidence pack referencji "similar_to: S2"
- Całkowicie zignorował wskazówkę

## Compliance A1-A7 (adaptive)

| Oś | S5 status |
|---|---|
| A1 dobór zespołów | Nadal 1 sekwencyjny agent |
| **A2 pamięć podobnych** | **0% — nie odczytuje własnej bazy runów nawet gdy się podaje ID** 🔴 |
| A3 skills | 0 |
| **A4 reuse** | **0% — plan generowany od zera, bardziej generyczny niż oryginał** 🔴 |
| A5 autonomia | brak polityk |
| A6 topologia | brak |
| A7 Human Gate systemowy | 0 |

## Najgroźniejsza konsekwencja

**AEIS nie jest "uczącym się" systemem.** Każdy run startuje od zera. Operator powtarzający podobne projekty nie zyskuje nic od systemu — nawet pogarsza wynik (S5 gorszy od S2 mimo że S2 był dostępny w bazie).

Kanonowy model (z [02_AEIS_EXTENDED_MODEL.md](02_AEIS_EXTENDED_MODEL.md)):
> *"Następny podobny projekt startuje już z doświadczeniem systemu"*

Runtime:
> Następny podobny projekt startuje z gorszym planem niż poprzedni.

## Nowe FIX-y

| ID | Opis | Effort |
|---|---|---|
| FIX-029 | `/api/v1/memory/search` endpoint (text query → podobne runy) | 4h |
| FIX-030 | Similarity index (embedding-based) dla planów | 16h |
| FIX-031 | Planner pre-step: "znajdź 3 najbliższe runy → użyj jako few-shot" | 8h |
| FIX-032 | Evidence pack zawiera `similar_runs: [...]` + `reused_skills: [...]` | 4h |
| FIX-033 | Gdy idea cytuje `run_id` — automatyczny fetch i włączenie w kontekst | 2h |
| FIX-034 | AEIS Improvement Queue musi DOSTAWAĆ sygnał z każdego runu, nie pusta | 6h |

## Dalej

S6 — ostatni scenariusz: multi-step z błędem w środku + próba recovery. Sprawdzi self-healing + rollback + Human Gate na błąd.
