# 29. FAQ i Runbook — Pomoc i pytania często zadawane
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja powierzchni `/faq` oraz towarzyszącego widgetu `CockpitFAQWidget`.
> Strona zawiera 15 pytań i odpowiedzi pogrupowanych w 13 kategorii — praktyczny
> przewodnik operatora po decyzjach, zachowaniach i ograniczeniach systemu SYLION AEIS.

## Spis treści

1. [Cel i lokalizacja](#1-cel-i-lokalizacja)
2. [Architektura strony](#2-architektura-strony)
3. [Dane FAQ — faq-entries.ts](#3-dane-faq--faq-entriest)
4. [Komponenty UI](#4-komponenty-ui)
5. [Integracja API (stub)](#5-integracja-api-stub)
6. [Stan i interakcje](#6-stan-i-interakcje)
7. [Kategorie i pytania](#7-kategorie-i-pytania)
8. [Przykłady użycia operatora](#8-przykłady-użycia-operatora)
9. [Weryfikacja](#9-weryfikacja)
10. [Cross-references](#10-cross-references)

---

## 1. Cel i lokalizacja

| Pole | Wartość |
|------|---------|
| Route | `/faq` |
| Plik strony | `src/sylion-frontend/src/app/(app)/faq/page.tsx` |
| Dane statyczne | `src/sylion-frontend/src/data/faq-entries.ts` |
| Komponenty | `src/sylion-frontend/src/components/faq/` |
| Backend route | `src/sylion-pipeline/sylion/api/faq_routes.py` |
| API prefix | `/api/v1/faq/` (stub — search i entries są aktualnie client-side) |

Strona `/faq` jest praktycznym przewodnikiem dla operatora zawierającym odpowiedzi
na pytania operacyjne: kiedy wymagany jest Human Gate, kiedy skalować VPS, jak działa
fallback lokalny, co robią Sentinele itd. Treść jest obecnie statyczna (plik TypeScript),
docelowo ma być przeniesiona do tabeli PG z edycją bez redeploy frontendu.

Dodatkowy punkt wejścia: `CockpitFAQWidget` w `operator-monitor` (tryb Cockpit) pokazuje
skróconą wersję FAQ z linkiem „Otwórz pełne FAQ →".

---

## 2. Architektura strony

```
FaqPage (page.tsx — "use client")
├── Header (ikona BookOpen + tytuł "Pomoc i FAQ" + liczba pytań)
├── FaqSearch           — pole tekstowe + licznik wyników
├── Kategorie (chips)   — "Wszystkie" + 13 kategorii z licznikami
└── Lista wpisów        — filtered FAQ_ENTRIES → FaqEntryCard per wpis
```

Renderowanie jest czysto client-side: filtrowanie i wyszukiwanie odbywa się przez
`useMemo` na tablicy `FAQ_ENTRIES` importowanej ze stałego pliku TypeScript.

### 2.1. Linkowanie głębokie przez hash

Strona obsługuje deep-linking przez URL hash:

```
/faq#human_gate.when_needed
```

`useEffect` przy montowaniu czyta `window.location.hash`, ustawia `openId` na odpowiedni wpis
i scrolluje do elementu za pomocą `scrollIntoView({ behavior: "smooth" })`.

---

## 3. Dane FAQ — faq-entries.ts

Plik: `src/sylion-frontend/src/data/faq-entries.ts` (666 linii)

### 3.1. Struktura wpisu

```typescript
export type FaqEntry = {
  id: string;               // format: "category.slug" np. "human_gate.when_needed"
  question: string;         // pytanie operatora
  shortAnswer: string;      // krótka odpowiedź (1-2 zdania), widoczna bez rozwinięcia
  fullAnswer: string;       // pełna odpowiedź markdown (może zawierać listy, bold)
  category: FaqCategory;    // jedna z 13 kategorii
  tags: string[];           // tagi do wyszukiwania
  contextHints: string[];   // klucze kontekstowe dla HelpHint (np. "lifecycle.blocked")
  relatedIds: string[];     // id powiązanych wpisów
};
```

### 3.2. Kategorie

```typescript
export type FaqCategory =
  | "human_gate"       | "production_control" | "council_critic"
  | "council_size"     | "worker_routing"     | "subscription"
  | "scaling"          | "local_fallback"     | "skills"
  | "agent_teams"      | "sentinels"          | "card_lifecycle"
  | "transparency";
```

---

## 4. Komponenty UI

Folder: `src/sylion-frontend/src/components/faq/`

| Komponent | Plik | Opis |
|-----------|------|------|
| `FaqSearch` | `FaqSearch.tsx` | Pole wyszukiwania z licznikiem wyników. Wyczyszczanie przez ikonę `×` |
| `FaqEntryCard` | `FaqEntry.tsx` | Rozwijany accordion: header z pytaniem + shortAnswer, body z fullAnswer + tagi + powiązane wpisy |
| `HelpHint` | `HelpHint.tsx` | Kontekstowy hint — mały przycisk `?` który pokazuje tooltip z wpisami FAQ pasującymi do `contextHints` danego widgetu |

### 4.1. FaqEntryCard

Każda karta pokazuje:
- Pytanie jako nagłówek (`<h3>`)
- Etykieta kategorii jako pill
- `shortAnswer` zawsze widoczny
- `fullAnswer` widoczny po kliknięciu/rozwinięciu (stan `openId === entry.id`)
- Tagi jako małe pilulki
- Linki do powiązanych wpisów (`relatedIds`) — klik ustawia `openId` i scrolluje

### 4.2. HelpHint

Komponent `HelpHint` przyjmuje `contextKey: string` i wyświetla tooltip z wpisami FAQ,
które mają `contextKey` w polu `contextHints`. Używany obok kart decyzyjnych, alertów
i lifecycle steps — operator widzi podpowiedź bez przechodzenia do `/faq`.

---

## 5. Integracja API (stub)

Plik: `src/sylion-pipeline/sylion/api/faq_routes.py`

Backend udostępnia 3 endpointy, wszystkie obecnie zwracają puste listy
(wyszukiwanie i wpisy są obsługiwane po stronie frontendu):

| Metoda | Ścieżka | Status | Przyszłość |
|--------|---------|--------|------------|
| `GET` | `/api/v1/faq/search?q=...&category=...` | Stub → `[]` | RAG po docs modułów (Phase 2) |
| `GET` | `/api/v1/faq/entries` | Stub → `[]` | PG-backed wpisy edytowalne |
| `GET` | `/api/v1/faq/contextual/{context_key}` | Stub → `[]` | Kontekstowe podpowiedzi z backendu |

Docelowa migracja do PG: tabela `advisor.faq_entries` z kolumnami odpowiadającymi `FaqEntry`.

---

## 6. Stan i interakcje

| Stan | Typ | Opis |
|------|-----|------|
| `query` | `string` | Tekst wyszukiwania. Aktualizowany w `FaqSearch` |
| `activeCategory` | `FaqCategory \| null` | Aktywna kategoria. `null` = "Wszystkie" |
| `openId` | `string \| null` | ID otwartego wpisu. Ustawiany przez klik lub URL hash |

### 6.1. Filtrowanie

```typescript
const filtered = useMemo(() =>
  FAQ_ENTRIES.filter((e) => {
    if (activeCategory && e.category !== activeCategory) return false;
    return matchesQuery(e, query);  // szuka w question, shortAnswer, fullAnswer, tags
  })
, [query, activeCategory]);
```

### 6.2. Liczniki kategorii

Każdy chip kategorii pokazuje liczbę wyników pasujących do bieżącego `query`
(nie filtru kategorii) — operator widzi ile wpisów w danej kategorii pasuje do szukanej frazy.

---

## 7. Kategorie i pytania

| Kategoria | Etykieta PL | Pytanie |
|-----------|-------------|---------|
| `human_gate` | Human Gate | Kiedy potrzebny jest Human Gate? |
| `production_control` | Kontrola produkcji | Kiedy zatrzymac produkcje? |
| `council_critic` | Critic model | Kiedy dodac critic model? |
| `council_size` | Rozmiar Council | Kiedy zwiekszyc Council? |
| `worker_routing` | Routing modeli | Kiedy uzywac tanszego workera? |
| `worker_routing` | Routing modeli | Kiedy uzywac modelu premium? |
| `subscription` | Subskrypcja | Kiedy kupic subskrypcje? |
| `scaling` | Skalowanie VPS | Kiedy skalowac VPS? |
| `local_fallback` | Local fallback | Jak dziala local fallback? |
| `skills` | Skills | Jak dzialaja Skills? |
| `agent_teams` | Zespoly agentow | Jak dzialaja zespoly agentow? |
| `sentinels` | Sentinele | Co robi cost sentinel i security sentinel? |
| `card_lifecycle` | Lifecycle kart | Dlaczego karta sie nie pojawila? |
| `card_lifecycle` | Lifecycle kart | Dlaczego karta zostala zablokowana? |
| `transparency` | Przejrzystosc systemu | Co system moze zrobic, a czego nie powinien robic po cichu? |

---

## 8. Przykłady użycia operatora

### 8.1. Szybkie szukanie odpowiedzi na pytanie o VPS

1. Operator otwiera `/faq`.
2. Wpisuje "vps" w pole wyszukiwania.
3. Chips: "Skalowanie VPS" pokazuje `(1)` — 1 wynik pasuje.
4. Lista pokazuje jeden wpis: "Kiedy skalowac VPS?".
5. Klik → `fullAnswer` rozwinięty: kryteria skalowania, koszty, harmonogram.

### 8.2. Przejście do FAQ z Cockpit

1. Operator jest na `/dashboard/operator-monitor` (tryb Cockpit).
2. `CockpitFAQWidget` w dolnej sekcji pokazuje 3 FAQ entries.
3. Klik "Otwórz pełne FAQ" → nawigacja do `/faq`.

### 8.3. Kontekstowa podpowiedź przy karcie decyzyjnej

1. Karta "Production deploy blocked" jest widoczna w `CockpitDecisionSection`.
2. Obok karty `HelpHint` z `contextKey="production.blocked"` pokazuje `?` przycisk.
3. Najechanie → tooltip z wpisem FAQ "Kiedy zatrzymac produkcje?" (bo `contextHints` zawiera `"production_control"`).

### 8.4. Deep-link do konkretnego wpisu

```
/faq#sentinels.what_they_do
```

Strona otwiera się, scroll do wpisu "Co robi cost sentinel i security sentinel?" z
automatycznie otwartym `fullAnswer`.

---

## 9. Weryfikacja

```bash
# Sprawdź czy strona /faq istnieje
curl -s http://localhost:3000/faq | grep -c "Pomoc i FAQ"

# Sprawdź backend FAQ health
curl -s http://127.0.0.1:8010/api/v1/faq/entries
# Oczekiwane: {"entries": [], "source": "static", "note": "..."}

# Sprawdź backend FAQ search
curl -s "http://127.0.0.1:8010/api/v1/faq/search?q=human+gate"
# Oczekiwane: {"results": [], "note": "Search is done client-side..."}
```

Liczba wpisów FAQ:

```bash
grep -c 'question:' src/sylion-frontend/src/data/faq-entries.ts
# Oczekiwane: 15 (plus 1 linia z definicją pola w type)
```

---

## 10. Cross-references

### 10.1. Powiązane komponenty

| Komponent | Relacja |
|-----------|---------|
| `CockpitFAQWidget` | `src/sylion-frontend/src/components/dashboard/CockpitFAQWidget.tsx` — skrócona wersja w Cockpit |
| `HelpHint` | `src/sylion-frontend/src/components/faq/HelpHint.tsx` — kontekstowe hinty w innych widokach |
| `CockpitDecisionSection` | Używa `HelpHint` przy kartach decyzyjnych |

### 10.2. Powiązane moduły backend

| Moduł | Relacja |
|-------|---------|
| `faq_routes.py` | Stub API — `GET /api/v1/faq/search`, `entries`, `contextual/{key}` |
| Orchestration config (J6) | Test catalog FAQ widget będzie linkował do katalogu testów (`/api/v1/orchestration/test-catalog`) |

### 10.3. Powiązane powierzchnie

| Surface | Plik | Relacja |
|---------|------|---------|
| Operator Monitor Cockpit | [`23_operator_monitor.md`](23_operator_monitor.md) | `CockpitFAQWidget` jako element Cockpit layout |
| D-ladder | [`31_d_ladder_complete.md`](31_d_ladder_complete.md) | FAQ "kiedy Human Gate" referuje poziomy D3–D5 |
| Council Hybrid | [`33_council_hybrid.md`](33_council_hybrid.md) | FAQ "kiedy zwiększyć Council" opisuje reguły quorum |

### 10.4. Plany rozwoju (Phase 2)

- Migracja `FAQ_ENTRIES` z TypeScript do tabeli PG `advisor.faq_entries` (edycja bez redeploy).
- Server-side RAG (`GET /api/v1/faq/search`) po plikach `docs/dokumentacja/modules/`.
- Kontekstowy FAQ w sidebar (kontekst per-route).
- Import/export wpisów FAQ jako JSON.
