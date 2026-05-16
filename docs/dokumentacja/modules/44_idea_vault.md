# 44. Idea Vault — skarbiec idei z cyklem zycia 15-stanowym
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja modulu IdeaVault: frontend `/idea-vault`, biblioteka API `lib/api/ideas.ts`,
> komponenty `idea-card`, `status-badge`, `create-idea-modal`, `status-transition-modal`.
> Backend: `GET|POST|PUT|DELETE /api/v1/ideas/` (FastAPI, SQLite/PG).

## Spis tresci

1. [Cel modulu](#1-cel-modulu)
2. [Architektura](#2-architektura)
3. [Cykl zycia idei — 15 statusow](#3-cykl-zycia-idei--15-statusow)
4. [API biblioteki (ideas.ts)](#4-api-biblioteki-ideasts)
5. [Komponenty React](#5-komponenty-react)
6. [REST API backend](#6-rest-api-backend)
7. [Schemat danych](#7-schemat-danych)
8. [Przykladowe przeplywy](#8-przykladowe-przeplywy)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modulu

IdeaVault jest repozytorium idei operatora AEIS. Kazda idea przechodzi przez zdefiniowany
cykl zycia (15 stanow) z regolami przejsc, a kluczowe stany (`awaiting_approval`,
`council_review`) integruja sie z Human Gate i CouncilHybrid. Modul zapewnia:

- tworzenie i edycje idei z metadanymi (kategoria, priorytet, tagi, domain, zrodlo),
- zarzadzanie cyklem zycia (transitions) z kontrola dozwolonych przejsc,
- automatyczne wykrywanie nieaktywnych idei (`stale`) po 30 dniach bez zmiany stanu,
- soft-delete (kosz) i hard-delete z trwałym usunieciem,
- log historii zmian statusu (`append-only`),
- statystyki zbiorcze per status.

---

## 2. Architektura

```
idea-vault/
├── page.tsx                       — lista idei + filtry + karta tworz
├── [id]/page.tsx                  — widok szczegolowy idei + historia
components/idea-vault/
├── idea-card.tsx                  — karta na liscie z akcjami
├── status-badge.tsx               — badge kolorowy per status
├── create-idea-modal.tsx          — modal tworzenia nowej idei
└── status-transition-modal.tsx    — modal zmiany statusu z potwierdzeniem

lib/api/ideas.ts                   — klient API (fetch wrapper) + typy + stale detection
```

---

## 3. Cykl zycia idei — 15 statusow

### 3.1. Lista statusow

| Status | Etykieta PL | Typ |
|--------|-------------|-----|
| `draft` | Szkic | aktywny |
| `created` | Nowy | aktywny |
| `clarification` | Wyjasnienie | aktywny |
| `submitted` | Zgloszony | aktywny |
| `council_review` | Rada | aktywny |
| `awaiting_approval` | Oczekuje | aktywny (HG) |
| `accepted` | Zaakceptowany | aktywny |
| `approved` | Zatwierdzony | aktywny |
| `implemented` | Wdrozony | terminalny |
| `rejected` | Odrzucony | terminalny |
| `stale` | Nieaktywny | auto-wykrywany |
| `abandoned` | Porzucony | terminalny |
| `archived` | Zarchiwizowany | terminalny |
| `deleted_soft` | W koszu | soft-delete |
| `deleted_hard` | Usuniety | hard-delete |

### 3.2. Graf przejsc (kluczowe sciezki)

```
draft / created → clarification → council_review → awaiting_approval → accepted → implemented
                               ↘ rejected
submitted → council_review → awaiting_approval → accepted
rejected → draft  (mozliwe wznowienie)
stale → draft / abandoned / archived
deleted_soft → draft  (mozliwe odtworzenie)
implemented → archived
```

Pelna macierz: `ALLOWED_TRANSITIONS` w `lib/api/ideas.ts`. Przejscia spoza macierzy
sa blokowane przez backend (walidacja + 422).

### 3.3. Stale detection

Idea jest `stale` gdy:
- `updated_at < now - 30 dni`
- status nalezy do `ACTIVE_STATUSES` (nie jest w stanie terminalnym)

Frontend sygalizuje to ikona `AlertTriangle` w `IdeaCard` i oznaczeniem "(nieaktywny)".
Funkcja: `isStaleIdea(idea: Idea): boolean` z `lib/api/ideas.ts`.

---

## 4. API biblioteki (ideas.ts)

### 4.1. Typy kluczowe

```typescript
export type IdeaStatus = "draft" | "created" | ... (15 wartosci)

export interface Idea {
  idea_id: string;
  title: string;
  description: string;
  author: string;
  status: IdeaStatus;
  category: string;
  priority: string;
  source: string;
  tags: string[];
  upvotes: number;
  created_at: number;   // Unix epoch float
  updated_at: number;
}

export interface IdeaLifecycleEntry {
  entry_id: string;
  idea_id: string;
  from_status: IdeaStatus | null;
  to_status: IdeaStatus;
  changed_by: string;
  changed_at: number;
  note?: string;
}

export interface IdeaStats {
  total: number;
  by_status: Record<IdeaStatus, number>;
}
```

### 4.2. Funkcje klienta

| Funkcja | HTTP | Opis |
|---------|------|------|
| `listIdeas({ status?, limit?, author? })` | `GET /api/v1/ideas` | Lista z filtrami |
| `listAllIdeas()` | wielokrotny GET | Pobiera wszystkie statusy przez `Promise.allSettled` (deduplication po `idea_id`) |
| `getIdea(ideaId)` | `GET /api/v1/ideas/:id` | Pojedyncza idea |
| `createIdea({ title, description?, author?, tags? })` | `POST /api/v1/ideas` | Tworzy nowa idee (status=`draft`) |
| `updateIdea(ideaId, { title?, description?, author?, status? })` | `PUT /api/v1/ideas/:id` | Aktualizuje (takze zmiana statusu) |
| `setIdeaStatus(ideaId, status)` | `PUT /api/v1/ideas/:id` | Skrot do zmiany statusu |
| `hardDeleteIdea(ideaId)` | `DELETE /api/v1/ideas/:id` | Trwale usuniecie |
| `getIdeaHistory(ideaId)` | `GET /api/v1/ideas/:id/history` | Log przejsc statusow |
| `getIdeaStats()` | `GET /api/v1/ideas/stats` | Statystyki zbiorcze |

### 4.3. Helpery

| Funkcja | Opis |
|---------|------|
| `isStaleIdea(idea)` | True gdy `updated_at < now - 30d` i status aktywny |
| `getDomain(idea)` | Mapuje `category` na `Domain` enum (14 domen) |
| `getDisplayTags(idea)` | Zwraca pierwsze 3 tagi z opcjonalnym "+N" |

---

## 5. Komponenty React

### 5.1. `IdeaCard`

Props: `{ idea, onView, onSoftDelete, className }`.

Wyswietla: tytuł, `StatusBadge`, ikone stale (jesli `isStaleIdea`), domain badge, 3 tagi,
wzgledny timestamp (`formatRelative`), przyciski "Podglad" i "Usun do kosza".

### 5.2. `StatusBadge`

Props: `{ status, className }`.

Renderuje `Badge` z kolorem per status:
- draft/created → neutral
- clarification/submitted → blue
- council_review → purple
- awaiting_approval → orange
- accepted/approved → green
- implemented → emerald
- rejected/deleted_soft → red
- stale → yellow
- abandoned/archived → slate/muted

### 5.3. `CreateIdeaModal`

Props: `{ open, onOpenChange, onCreate }`. Formularz: title (required), description, author, tags (comma-separated). Submit → `createIdea(body)`.

### 5.4. `StatusTransitionModal`

Props: `{ idea, open, onOpenChange, onTransition }`. Wyswietla dozwolone przejscia z `ALLOWED_TRANSITIONS[idea.status]` z label-ami z `TRANSITION_LABELS`. Potwierdzenie → `setIdeaStatus(ideaId, targetStatus)`.

---

## 6. REST API backend

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/v1/ideas` | GET | Lista z filtrami `status`, `limit`, `author` |
| `/api/v1/ideas` | POST | Tworzy idee (`title` required, `status=draft`) |
| `/api/v1/ideas/{id}` | GET | Szczegoly idei |
| `/api/v1/ideas/{id}` | PUT | Aktualizuje idee; waliduje `status` transition |
| `/api/v1/ideas/{id}` | DELETE | Hard-delete |
| `/api/v1/ideas/{id}/history` | GET | Log historii statusow |
| `/api/v1/ideas/stats` | GET | Statystyki per status |

Backendowe endpointy zdefiniowane w `src/sylion-pipeline/sylion/api/` (router `ideas_routes.py`).

---

## 7. Schemat danych

```sql
-- Glowna tabela
ideas (
  idea_id       TEXT PRIMARY KEY,  -- uuid4-hex
  title         TEXT NOT NULL,
  description   TEXT,
  author        TEXT,
  status        TEXT DEFAULT 'draft',
  category      TEXT,
  priority      TEXT DEFAULT 'medium',
  source        TEXT DEFAULT 'operator',
  tags          TEXT,              -- JSON array
  upvotes       INTEGER DEFAULT 0,
  created_at    REAL,              -- Unix epoch
  updated_at    REAL
)

-- Historia zmian (append-only)
idea_lifecycle (
  entry_id      TEXT PRIMARY KEY,
  idea_id       TEXT REFERENCES ideas(idea_id),
  from_status   TEXT,
  to_status     TEXT NOT NULL,
  changed_by    TEXT,
  changed_at    REAL,
  note          TEXT
)
```

---

## 8. Przykladowe przeplywy

### 8.1. Zgloszenie idei do Rady

```typescript
// 1. Operator tworzy idee
const idea = await createIdea({ title: "Wdrozenie cache L2", author: "ops-team" });
// idea.status === "draft"

// 2. Operator zglasza do Rady
await setIdeaStatus(idea.idea_id, "council_review");

// 3. Rada zatwierdza
await setIdeaStatus(idea.idea_id, "awaiting_approval");

// 4. Human Gate approves
await setIdeaStatus(idea.idea_id, "accepted");

// 5. Wdrozenie
await setIdeaStatus(idea.idea_id, "implemented");
```

### 8.2. Soft-delete i odtworzenie

```typescript
// Przenies do kosza
await setIdeaStatus(idea.idea_id, "deleted_soft");
// Odtworzenie
await setIdeaStatus(idea.idea_id, "draft");
// Trwale usuniecie
await hardDeleteIdea(idea.idea_id);
```

---

## 9. Troubleshooting

| Problem | Mozliwa przyczyna | Rozwiazanie |
|---------|-------------------|-------------|
| Przejscie statusu blokowane (422) | Status nie w `ALLOWED_TRANSITIONS` | Sprawdz macierz przejsc w `lib/api/ideas.ts` |
| Lista ideas pusta | Backend niedostepny | Sprawdz `GET /api/v1/ideas`; czy tabela `ideas` istnieje |
| `stale` wyswietla sie bez powodu | Zegar systemu lub `updated_at` niepoprawny | Sprawdz timestamp w bazie |
| Historia pusta | `idea_lifecycle` nie jest zapisywana | Sprawdz logike backendu przy PUT status change |

---

## 10. Cross-references

- [`26_council_voting.md`](26_council_voting.md) — status `council_review` integruje z CouncilHybrid
- [`33_council_hybrid.md`](33_council_hybrid.md) — architektura CouncilHybrid i Human Gate
- [`05_engine.md`](05_engine.md) — engine moze generowac karty ze zmianami dla idei
- [`27_audit_viewer.md`](27_audit_viewer.md) — historia zmian idei jest czescia audit trail
- Patrz rowniez: pamiec `project_idea_lifecycle.md` (kanoniczny model 15-stanowy, HG handoff)
