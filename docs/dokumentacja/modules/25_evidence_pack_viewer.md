# 25. Evidence Pack Viewer — Audit Trail i Fidelity
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja warstwy frontend dla powierzchni `/evidence`. Strona pokazuje
> globalny rejestr Evidence Packs (D1-D5) z całego systemu — nie tylko z Advisor
> warstwy. Każdy pack zawiera artefakty (analyses, baselines, plans, audit logs,
> sign-offs, signatures) z hashami SHA-256, statusem walidacji i fidelity score.
> Strona jest **read-only** — operatorzy nie tworzą tu packs (to robi backend
> przy każdej decyzji D3+), ale przeglądają je w celach audytowych.

## Spis treści

1. [Cel i URL](#1-cel-i-url)
2. [Komponenty UI](#2-komponenty-ui)
3. [Kontrolki i interakcje](#3-kontrolki-i-interakcje)
4. [Zarządzanie stanem](#4-zarządzanie-stanem)
5. [Integracja API](#5-integracja-api)
6. [Persistencja](#6-persistencja)
7. [Tryby i warianty](#7-tryby-i-warianty)
8. [Dostępność](#8-dostępność)
9. [Przepływy operatora](#9-przepływy-operatora)
10. [Cross-references](#10-cross-references)

---

## 1. Cel i URL

| Pole | Wartość |
|------|---------|
| Ścieżka | `/evidence` |
| Plik źródłowy | `src/sylion-frontend/src/app/(app)/evidence/page.tsx` |
| Komponent główny | `EvidencePage` (default export) |
| Layout | `(app)` route group; lewy sidebar widoczny |
| Persona | Operator + Audit Reviewer (read-only) |
| Cel | Przeglądanie evidence packs, weryfikacja fidelity, drill-down do artefaktów |
| Refresh | Polling przez `useEvidence()` z TTL ~30 s |
| Strict requirement | **Wymaga live backend** — w trybie offline pokazuje WiFi-off empty state |

Surface różni się od Advisor Evidence (`/api/v1/advisor/evidence/{id}`) — tutaj
używamy **core evidence** (`/api/v1/core/evidence`), który agreguje wszystkie packs
z systemu (Council, IdeaVault, Lifecycle hooks, Funding decisions, IT-AUDIT, etc.).
Advisor evidence jest podzbiorem (filter `source='advisor'`).

---

## 2. Komponenty UI

```
┌──────────────────────────────────────────────────────────────┐
│ Header (FileCheck icon + title + LIVE badge)                 │
├──────────────────────────────────────────────────────────────┤
│  IF !backendLive: WifiOff empty state (centered)             │
│  ELSE:                                                       │
│    Stats row (4 cards):                                      │
│      ├ Total Packs                                           │
│      ├ Validated                                             │
│      ├ Chain Integrity (always "Live")                       │
│      └ Fidelity Score (avg %)                                │
│    Evidence Packs Table (collapsed rows + expand artefacts)  │
│    Fidelity Metrics chart (recharts AreaChart, last N packs) │
└──────────────────────────────────────────────────────────────┘
```

### 2.1. Header (linie 143–161)

| Element | Treść |
|---------|-------|
| Ikona | `FileCheck` (Lucide), `w-5 h-5 text-primary` |
| H1 | "Evidence & Audit Trail" |
| Sub-line | "Auditability, traceability, and evidence pack management" |
| LIVE badge | `<Badge variant="outline">` z `bg-sylion-green` dot, widoczny tylko gdy `backendLive` |

### 2.2. Empty state — backend offline

```tsx
{!backendLive && (
  <div className="flex flex-col items-center justify-center py-24 text-center">
    <WifiOff className="w-10 h-10 text-muted-foreground mb-4" />
    <h2 className="text-lg font-semibold text-muted-foreground">Backend not reachable</h2>
    <p className="text-sm text-muted-foreground mt-1 max-w-md">
      The SYLION backend API is not responding. Evidence data requires a live connection to the backend service.
    </p>
  </div>
)}
```

Strict design: bez fallbacku na mock data. Operator MUSI mieć działające połączenie
żeby zobaczyć evidence packs. Powód: chain integrity verification wymaga live verification.

### 2.3. Stats row (4 KPI cards)

| Card | Wartość | Kolor | Sub-line |
|------|---------|-------|----------|
| Total Packs | `displayPacks.length` | foreground | "Evidence packs tracked" |
| Validated | filtered count `status in [validated, submitted]` | `text-sylion-green` | "Packs validated or submitted" |
| Chain Integrity | "Live" (z `ShieldCheck` icon) | `text-sylion-green` | "Verified via API" |
| Fidelity Score | `avgFidelity * 100` % | `getFidelityColor(avgFidelity)` (zielony/amber/red) | "Average across packs" |

`avgFidelity` jest liczone jako średnia tylko z packs gdzie `fidelity > 0`
(omijając draft i nieukończone packs).

### 2.4. Evidence Packs Table

`<Table>` z 8 kolumnami:

| # | Header | Cell type | Width hint |
|---|--------|-----------|------------|
| 1 | (chevron) | ChevronRight/Down | `w-8` |
| 2 | Pack ID | `font-mono text-[11px] font-medium` | auto |
| 3 | Proposal | `font-mono text-[11px] text-muted-foreground` | auto |
| 4 | Class | Badge (D0/D1/D2/D3/D4/D5) z kolorem `getDecisionClassBgColor()` | auto |
| 5 | Status | Badge (validated/submitted/draft/archived) | auto |
| 6 | Artefacts | liczba `artefacts_count` | auto |
| 7 | Fidelity | progress bar `w-10 h-1.5` + procent | auto |
| 8 | Timestamp | sformatowany `formatDate()` | auto |

Każdy `<TableRow>` jest `cursor-pointer` z `onClick={() => setExpandedPack(...)}`.
Hover: `hover:bg-muted/30`. Expanded row: `bg-muted/20`.

### 2.5. Expanded artefact detail

Gdy `expandedPack === pack.id`, renderowany jest dodatkowy `<TableRow>` z `colSpan={8}`:

```tsx
<div className="px-12 py-3">
  <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
    Artefacts ({artefacts.length})
  </p>
  {artefacts.map((art) => {
    const AIcon = artefactTypeIcon[art.type] || FileCheck;
    return (
      <div className="flex items-center gap-3 p-2 rounded-md bg-background/50 border border-border/30">
        <AIcon className="w-3.5 h-3.5 text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="text-[11px] font-medium truncate">{art.name}</span>
          <Badge variant="outline" className="text-[8px] h-4">{art.type}</Badge>
          <span className="font-mono text-[9px]">{art.hash}</span>
          {art.size && <span className="text-[9px]">{art.size}</span>}
        </div>
        {art.validated ? (
          <Badge className="border-sylion-green/30 text-sylion-green">
            <CheckCircle2 /> Validated
          </Badge>
        ) : (
          <Badge className="border-sylion-amber/30 text-sylion-amber">
            <Clock /> Pending
          </Badge>
        )}
      </div>
    );
  })}
</div>
```

Padding `px-12` = 48 px lewa wcięta — wizualne oddzielenie od głównej tabeli.

### 2.6. Mapa ikon artefaktów

| Type | Icon | Use case |
|------|------|----------|
| `analysis` | `Activity` | Risk analysis, complexity metrics |
| `baseline` | `TrendingUp` | Baseline metrics przed zmianą (D3+) |
| `plan` | `FileCheck` | Implementation plan (D3+) |
| `audit` | `ShieldCheck` | IT-AUDIT findings |
| `matrix` | `Layers` | Compliance matrix (D5) |
| `timeline` | `Clock` | Project timeline snapshot |
| `procedure` | `FileCheck` | Standard operating procedure |
| `signoff` | `CheckCircle2` | Operator sign-off (D5) |
| `log` | `Hash` | Decision audit log |
| `architecture` | `Layers` | System architecture diagram |
| `benchmark` | `TrendingUp` | Performance benchmark |
| `evidence` | `FileCheck` | Generic evidence file |
| `review` | `FileCheck` | Council review document |
| `signature` | `Hash` | Cryptographic signature (Ed25519) |

Fallback ikona: `FileCheck`.

### 2.7. Fidelity Metrics chart (recharts)

Rendowany **tylko** gdy `fidelityChartData.length > 0`. AreaChart z recharts:

| Element | Konfiguracja |
|---------|--------------|
| Wysokość | `260 px` |
| X-axis | `dataKey="time"`, format `Apr 26, 11AM` |
| Y-axis | `domain={[0, 100]}`, format `${v}%` |
| Stroke | `#17C964` (sylion-green) |
| Fill | `linearGradient` od `0.3` opacity do `0` |
| Tooltip | `bg #0f1629`, `border rgba(148,163,184,0.12)`, fontSize 11 px |

Pod chartem 3-kolumnowy footer:

| Kolumna | Wartość |
|---------|---------|
| Latest Fidelity | `fidelityChartData[last].fidelity` % |
| Average | mean over chart data |
| Packs | `fidelityChartData.length` |

---

## 3. Kontrolki i interakcje

### 3.1. Kliknięcie wiersza pack

```ts
onClick={() => setExpandedPack(isExpanded ? null : pack.id)}
```

Toggle state — tylko **jeden** pack może być rozwinięty na raz (single-select
behavior). Kliknięcie innego wiersza zamyka poprzedni i otwiera nowy.

### 3.2. Sortowanie

Brak. Tabela jest sortowana DESC po `created_at` (default backend order).
TODO: dodać `<TableHead>` clickable dla sort by Class, Status, Fidelity, Timestamp.

### 3.3. Filtrowanie

Brak. Wszystkie packs są widoczne. TODO: dodać filter bar dla:
- Decision class (D0-D5 multi-select)
- Status (draft/submitted/validated/archived multi-select)
- Date range
- Search po `pack_id` lub `proposal_id`

### 3.4. Paginacja

Brak. W MVP `useEvidence()` zwraca max 100 entries, sortowane DESC po `created_at`.
TODO: server-side pagination z cursor-based API.

### 3.5. Hover na progress bar fidelity

Brak tooltipu w MVP. TODO: dodać Radix `<Tooltip>` z dokładną wartością `0.9847` zamiast `98%`.

### 3.6. Hover na hash artefaktu

Brak. Hash pokazany jako truncated `font-mono text-[9px]`. TODO: dodać click-to-copy.

### 3.7. Klik na chevron — keyboard

`<TableRow>` jest `<tr>` z `cursor-pointer` ale **nie** focusable natywnie. Operator
musi kliknąć myszą. TODO: dodać `tabIndex=0` + `onKeyDown` (Enter/Space) dla a11y.

---

## 4. Zarządzanie stanem

### 4.1. Hooki React

```ts
const { data: health } = useHealth();
const { data: evidenceData } = useEvidence();

const [mounted, setMounted] = useState(false);
const [expandedPack, setExpandedPack] = useState<string | null>(null);

useEffect(() => { setMounted(true); }, []);
```

| Stan | Typ | Cel |
|------|-----|-----|
| `health` | `{ status: 'ok' \| 'down' }` | Determinuje `backendLive` |
| `evidenceData` | `{ entries: EvidenceEntry[] }` | Surowa lista z backendu |
| `mounted` | `boolean` | SSR/hydration guard — `formatDate` używa `toLocaleString()` (timezone-dependent) |
| `expandedPack` | `string \| null` | Aktualnie rozwinięty pack ID |

### 4.2. Memoizacja

```ts
const displayPacks = useMemo(() => {
  if (!backendLive) return [];
  return liveEntries.map((e) => ({
    id: e.evidence_id ?? e.id,
    proposal_id: e.proposal_id || "--",
    decision_class: e.decision_class || "D1",
    status: e.status || "draft",
    artefacts_count: e.artefacts_count ?? 1,
    fidelity: e.fidelity ?? 0,
    created_at: e.created_at || new Date().toISOString(),
    artefacts: e.artefacts ?? [],
  }));
}, [backendLive, liveEntries]);
```

Re-mapowanie z surowych entries do display-friendly objects. Re-build tylko gdy
backend stan lub entries się zmienią.

```ts
const fidelityChartData = useMemo(() => {
  return displayPacks
    .filter((p) => p.fidelity > 0)
    .map((p) => ({
      time: new Date(p.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit" }),
      fidelity: Math.round(p.fidelity * 1000) / 10,
      pack_id: p.id,
    }));
}, [displayPacks]);
```

`Math.round(p.fidelity * 1000) / 10` daje 1 decimal place precision (e.g. `98.5%`).

### 4.3. Hydration guard

`mounted` flag używany tylko dla `formatDate(pack.created_at)` i fidelity chart —
oba używają user-locale APIs które różnią się między server (UTC) a client. Bez
guard byłby hydration mismatch.

```tsx
{mounted ? formatDate(pack.created_at) : "--"}
{mounted ? `${(avgFidelity * 100).toFixed(1)}%` : "--"}
```

### 4.4. `backendLive` derivation

```ts
const backendLive = health.status === "ok";
```

`useHealth()` hook poll'uje `/api/health` co 15 s. Każda zmiana `health.status`
auto-rerender'uje stronę.

---

## 5. Integracja API

### 5.1. Endpointy

| Metoda | Endpoint | Hook | Cel |
|--------|----------|------|-----|
| GET | `/api/health` | `useHealth()` | Health probe |
| GET | `/api/v1/core/evidence` | `useEvidence()` | Lista packs (max 100) |
| GET | `/api/v1/core/evidence/{id}` | (nieużywane w MVP) | Detal pack ze wszystkimi artefaktami |
| GET | `/api/v1/core/evidence/{id}/verify` | (TBD) | Re-verify chain integrity |
| GET | `/api/v1/core/evidence/{id}/download` | (TBD) | Download ZIP z artefaktami |

### 5.2. Schema `EvidenceEntry`

```ts
interface EvidenceEntry {
  evidence_id: string;             // np. "ev_d3_20260426_a1b2"
  proposal_id: string | null;      // np. "prop_council_xyz"
  decision_class: 'D0' | 'D1' | 'D2' | 'D3' | 'D4' | 'D5';
  status: 'draft' | 'submitted' | 'validated' | 'archived';
  artefacts_count: number;
  fidelity: number;                // 0..1, np. 0.987
  created_at: string;              // ISO 8601
  template: 'd3_light' | 'd5_full' | 'audit_only' | 'council_signoff';
  source: 'advisor' | 'council' | 'idea_vault' | 'lifecycle' | 'funding' | 'it_audit';
  signed: boolean;
  signature_algo: 'ed25519' | null;
  artefacts: Artefact[];           // empty list jeśli compact view
}
```

### 5.3. Schema `Artefact`

```ts
interface Artefact {
  type: string;                    // 'analysis' | 'baseline' | 'plan' | 'audit' | ...
  name: string;                    // np. "risk_analysis_v3.pdf"
  hash: string;                    // SHA-256 hex (64 chars)
  validated: boolean;              // czy hash matchuje stored value
  size: string;                    // human-readable, np. "2.4 MB"
  mime_type?: string;              // np. "application/pdf"
  storage_uri?: string;            // np. "s3://sylion-evidence/2026/04/abc.pdf"
}
```

### 5.4. Response — lista packs

```http
GET /api/v1/core/evidence?limit=100 HTTP/1.1

HTTP/1.1 200 OK
{
  "entries": [
    {
      "evidence_id": "ev_d3_20260426_8f2a",
      "proposal_id": "prop_council_2026_xyz",
      "decision_class": "D3",
      "status": "validated",
      "artefacts_count": 5,
      "fidelity": 0.9847,
      "created_at": "2026-04-26T11:42:18Z",
      "template": "d3_light",
      "source": "council",
      "signed": true,
      "signature_algo": "ed25519",
      "artefacts": [
        { "type": "analysis", "name": "risk_analysis.pdf", "hash": "a1b2c3...", "validated": true, "size": "1.2 MB" },
        { "type": "baseline", "name": "metrics_baseline.json", "hash": "d4e5f6...", "validated": true, "size": "8 KB" },
        { "type": "plan", "name": "implementation_plan.md", "hash": "789abc...", "validated": true, "size": "12 KB" },
        { "type": "review", "name": "council_review.json", "hash": "def012...", "validated": true, "size": "4 KB" },
        { "type": "signature", "name": "operator_signature.sig", "hash": "345678...", "validated": true, "size": "256 B" }
      ]
    }
  ],
  "total": 247,
  "page": 1,
  "page_size": 100
}
```

### 5.5. Response — health probe

```http
GET /api/health HTTP/1.1

HTTP/1.1 200 OK
{ "status": "ok", "service": "sylion-frontend", "uptime_s": 86400 }

# vs error case:
HTTP/1.1 503 Service Unavailable
{ "status": "down", "errors": ["backend timeout"] }
```

### 5.6. Error handling

| Sytuacja | UI |
|----------|-----|
| `health.status !== "ok"` | Empty state z `WifiOff` icon + "Backend not reachable" |
| 401 Unauthorized | Redirect do `/auth` (axios interceptor) |
| 403 Forbidden | Empty state + "You don't have permission to view evidence" (TBD) |
| 500 Internal | Empty state z generic error (TBD) |
| Pusty list | Pokazuje 4 stat cards z `0` ale **nie** pokazuje fidelity chart |

---

## 6. Persistencja

### 6.1. Backend storage

Evidence packs są przechowywane w trzech warstwach:

| Layer | Storage | Cel |
|-------|---------|-----|
| Metadata | PostgreSQL `core.evidence_packs` | Pack metadata (id, class, status, fidelity, signature) |
| Artefact metadata | PostgreSQL `core.evidence_artefacts` | Artefact records (type, name, hash, size, storage_uri) |
| Artefact files | S3 / MinIO bucket `sylion-evidence` | Actual files (PDFs, JSON, MD, images, signatures) |
| Chain integrity | Append-only log `core.evidence_chain` | Hash chain Merkle-tree style |

### 6.2. Schema `core.evidence_packs`

```sql
CREATE TABLE core.evidence_packs (
  evidence_id TEXT PRIMARY KEY,
  proposal_id TEXT,
  decision_class TEXT NOT NULL CHECK (decision_class IN ('D0','D1','D2','D3','D4','D5')),
  status TEXT NOT NULL CHECK (status IN ('draft','submitted','validated','archived')),
  artefacts_count INTEGER NOT NULL DEFAULT 0,
  fidelity NUMERIC(5,4) NOT NULL DEFAULT 0,  -- 0.0000 to 1.0000
  template TEXT NOT NULL CHECK (template IN ('d3_light','d5_full','audit_only','council_signoff')),
  source TEXT NOT NULL,
  signed BOOLEAN NOT NULL DEFAULT FALSE,
  signature_algo TEXT,
  signature_value TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  archived_at TIMESTAMPTZ
);
CREATE INDEX idx_ev_status_created ON core.evidence_packs(status, created_at DESC);
CREATE INDEX idx_ev_class_status ON core.evidence_packs(decision_class, status);
```

### 6.3. Schema `core.evidence_artefacts`

```sql
CREATE TABLE core.evidence_artefacts (
  artefact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evidence_id TEXT NOT NULL REFERENCES core.evidence_packs(evidence_id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  hash TEXT NOT NULL,                   -- SHA-256 hex
  validated BOOLEAN NOT NULL DEFAULT FALSE,
  validated_at TIMESTAMPTZ,
  size_bytes BIGINT NOT NULL,
  mime_type TEXT,
  storage_uri TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_artef_evidence ON core.evidence_artefacts(evidence_id);
```

### 6.4. Frontend cache

| Klucz | Storage | TTL |
|-------|---------|-----|
| `react-query: evidence:list` | in-memory (TanStack Query) | 30 s `staleTime`, 5 min `cacheTime` |
| `react-query: health` | in-memory | 15 s `staleTime` |
| `expandedPack` | React useState (component-local) | unmount = reset |

Brak persistencji do localStorage — evidence dane są zawsze fresh-fetched.

### 6.5. Chain integrity verification

Backend przy każdym GET na `/evidence/{id}/verify`:

1. Pobiera Merkle root z `core.evidence_chain`.
2. Recomputes hash chain ze wszystkich `artefact.hash` w packu.
3. Verifies signature z public key (`signature_algo='ed25519'`).
4. Returns `{ valid: true, chain_height: 12345, last_verified: "2026-04-26T11:42:18Z" }`.

W MVP frontend pokazuje tylko statyczny "Live" badge bez wywoływania verify.
Operator musi ufać że backend's "validated" status jest prawdziwy.

---

## 7. Tryby i warianty

### 7.1. Backend availability

| `health.status` | UI |
|-----------------|-----|
| `"ok"` | Pełna strona: stats + table + chart |
| `"down"` | Empty state z `WifiOff` |

### 7.2. Pack status

| `status` | Badge color | Semantyka |
|----------|-------------|-----------|
| `validated` | `bg-sylion-green/15 text-sylion-green` | Hash chain weryfikuje, signature OK |
| `submitted` | `bg-accent-blue-dim text-sylion-blue` | Pack stworzony, oczekuje na walidację |
| `draft` | `bg-accent-amber-dim text-sylion-amber` | Pack w trakcie tworzenia, brakuje artefaktów |
| `archived` | `bg-muted/50 text-muted-foreground` | Stary pack, retention period passed |

### 7.3. Decision class

| Class | `getDecisionClassBgColor()` | Wymaga Evidence Pack? |
|-------|----------------------------|----------------------|
| D0 | `bg-muted/30 text-muted-foreground` | nie (informational) |
| D1 | `bg-sylion-blue/15 text-sylion-blue` | nie (low risk) |
| D2 | `bg-sylion-blue/20 text-sylion-blue` | opcjonalnie |
| D3 | `bg-sylion-amber/15 text-sylion-amber` | **tak** (`d3_light`) |
| D4 | `bg-orange-400/15 text-orange-400` | **tak** (`d3_light` lub `d5_full`) |
| D5 | `bg-sylion-red/15 text-sylion-red` | **tak** (`d5_full` z signoff + signature) |

### 7.4. Fidelity color

`getFidelityColor(value)` z `lib/utils.ts`:

| Range | Color |
|-------|-------|
| `>= 0.99` | `text-sylion-green` |
| `0.95..0.99` | `text-emerald-400` |
| `0.90..0.95` | `text-sylion-blue` |
| `0..0.90` | `text-sylion-amber` |
| `0` | `text-muted-foreground` |

### 7.5. Artefact validation

| `validated` | Badge | Semantyka |
|-------------|-------|-----------|
| `true` | `border-sylion-green/30 text-sylion-green` z `CheckCircle2` | Hash matchuje stored value |
| `false` | `border-sylion-amber/30 text-sylion-amber` z `Clock` | Pending validation lub hash mismatch |

UWAGA: w MVP `validated=false` może być **legitimately pending** (pack w trakcie
tworzenia) lub **hash mismatch** (tampered). UI nie rozróżnia tych dwóch przypadków.
TODO: dodać `validation_error` field i pokazać czerwony badge przy mismatch.

### 7.6. Empty fidelity chart

Chart renderuje się tylko gdy `fidelityChartData.length > 0`. Jeśli wszystkie
packs mają `fidelity=0` (draft), chart jest ukryty i operator widzi tylko table.

---

## 8. Dostępność

### 8.1. Klawiatura

| Klawisz | Akcja | Status |
|---------|-------|--------|
| `Tab` | Nawigacja między LIVE badge i header | OK (natywne) |
| `Tab` (na table) | **Brak** focusowalnych elementów w wierszu | **TODO** |
| `Enter/Space` (na pack row) | Toggle expand | **TODO — currently mouse only** |
| `Esc` (z expanded) | Collapse | **TODO** |

W MVP tabela jest **mouse-only**. Powinno się dodać `tabIndex=0` + `role="button"`
+ `aria-expanded={isExpanded}` na każdy `<TableRow>`.

### 8.2. Screen reader

- Header poprawnie czytelny: `<h1>` + sub-line.
- Stats cards: 4 osobne `<Card>` z `<p>` label + `<p>` value — czytelne ale brak `aria-label` opisujący pełny kontekst.
- Tabela: native `<table>` semantics (Radix/shadcn) — działa z NVDA/JAWS w trybie czytania tabel.
- Expanded artefacts: brak `aria-live` — screen reader nie wie że nowe wiersze się pojawiły.

### 8.3. Kontrast

| Element | Foreground | Background | WCAG AA |
|---------|-----------|------------|---------|
| Pack ID font-mono | foreground | card | OK |
| Decision class badge | varies (D0-D5) | przez `bg-XX/15` | OK (kolorowe badge'e są w 4.5:1+ w dark mode) |
| Fidelity progress bar | sylion-green | secondary | OK |
| Fidelity text `text-[10px]` | varies | card | granica AA — `text-[10px]` jest mały, ale używamy `font-medium` |
| Artefact hash `text-[9px]` font-mono | muted | bg-background/50 | **POD AA** — hash może być nieczytelny |

TODO: zwiększyć rozmiar hash do `text-[10px]` lub dodać tooltip na hover z większym tekstem.

### 8.4. Reduced motion

Recharts AreaChart nie ma własnych animacji nie-respektujących prefers-reduced-motion.
Chevron toggle nie jest animowany — natychmiastowy switch.

### 8.5. Color-only encoding

UWAGA: status pack jest sygnalizowany **kolorem badge'a** + **tekstem** ("validated"/"draft"/etc).
Decision class to **kolor + tekst** ("D3"). Fidelity to **kolor progress bar + procent**.
Operatorzy z deuteranopia/protanopia będą polegać na tekście, co jest spełnione.

---

## 9. Przepływy operatora

### 9.1. Audytor przegląda evidence packs po decyzji D5

1. Audytor loguje się i wchodzi na `/evidence`.
2. Strona ładuje dane: `useHealth()` → `health.status="ok"`, `useEvidence()` → 247 entries.
3. Stats row pokazuje: Total 247, Validated 198, Chain Live, Fidelity 96.4%.
4. Audytor scrolluje listę i widzi pack `ev_d5_20260425_xy12` z class D5, status validated.
5. Klika wiersz → expand pokazuje 11 artefaktów.
6. Sprawdza `signature.sig` artefakt → validated badge zielony, hash widoczny.
7. Sprawdza `compliance_matrix.xlsx` → validated.
8. Audytor decyduje że pack jest kompletny i zgadza się z proposal.
9. (Poza UI) audytor robi screenshot lub eksportuje pack przez backend API.

### 9.2. Operator monitoruje fidelity trend

1. Operator otwiera `/evidence`.
2. Stats: Fidelity Score 96.4% — `text-emerald-400` (95%-99% range).
3. Scroll w dół do "Fidelity Metrics Over Time" chart.
4. Widzi area chart pokazujący fidelity packs z ostatnich tygodni.
5. Pod chartem: Latest 98.7%, Average 96.4%, Packs 47.
6. Operator zauważa że ostatnie 3 packs miały fidelity rosnące (94 → 97 → 98.7) — pozytywny trend.
7. Brak akcji — view-only.

### 9.3. Sprawdzenie konkretnego proposal-id z innego kontekstu

1. Operator dostaje notyfikację z Council: "Proposal `prop_council_xyz` zatwierdzony, evidence pack `ev_d3_20260426_8f2a`".
2. Otwiera `/evidence`.
3. Brak search bara w MVP — operator scrolluje listę.
4. Znajduje wiersz z `Pack ID = ev_d3_20260426_8f2a` (pierwsza kolumna `font-mono`).
5. Klika → expand.
6. Sprawdza że `proposal_id` matchuje `prop_council_xyz` (kolumna 3).
7. Sprawdza listę artefaktów (5 sztuk: analysis, baseline, plan, review, signature).
8. Wszystkie validated, fidelity 98.5%.
9. Akceptuje że proposal jest dobrze udokumentowany.

TODO future: dodać `?proposal_id=...` query param i auto-scroll/auto-expand do matching pack.

### 9.4. Backend offline scenario

1. Backend pada (deploy lub awaria).
2. Frontend `useHealth()` zwraca `health.status="down"` po 5 s polling.
3. `backendLive=false` → stats row + table + chart się **nie** renderują.
4. Operator widzi WifiOff icon + "Backend not reachable" message.
5. Czeka albo refresh'uje stronę ręcznie. Brak retry button w MVP.
6. Po 30 s backend wraca, `useHealth()` retry'uje i `health.status="ok"`.
7. Strona auto-rerenderuje pełną zawartość bez akcji operatora.

### 9.5. Drill-down do artefaktu (read-only)

1. Operator klika wiersz pack → expand.
2. Widzi listę artefaktów: każdy ma type icon, name, hash (truncated), size, validation badge.
3. Brak akcji "download" w MVP — operator musi użyć backend CLI lub admin tool.
4. TODO: dodać download button per artefakt (`storage_uri` → presigned S3 URL z 5-min expiry).
5. TODO: dodać "View hash" copy button.
6. TODO: dodać preview dla `mime_type=application/pdf`.

---

## 10. Cross-references

### 10.1. Powiązane surfaces

| Surface | Plik | Relacja |
|---------|------|---------|
| `/advisor` | [`20_advisor_feed.md`](20_advisor_feed.md) | Karty D3+ mają inline `EvidenceDialog` (advisor-specific evidence pack) |
| `/governance` | [`26_council_voting.md`](26_council_voting.md) | Council proposals D3+ generują evidence packs widoczne tutaj |
| `/audit` | [`27_audit_viewer.md`](27_audit_viewer.md) | Audit events mają `evidence_id` link → zewnętrzne kliknięcie do `/evidence?id=X` |
| `/projects/[id]/lifecycle` | [`22_lifecycle_dashboard.md`](22_lifecycle_dashboard.md) | Lifecycle hooks H08 (Decision Gate) i H10 (Audit) tworzą packs |
| `/dashboard/operator-monitor` | [`23_operator_monitor.md`](23_operator_monitor.md) | KPI "Evidence packs created today" (TBD) |

### 10.2. Powiązane backend modules

| Moduł | Folder | Rola |
|-------|--------|------|
| Evidence Manager | `src/sylion-pipeline/sylion/evidence/` | Tworzy packs, computes fidelity, signs |
| Evidence Chain | `src/sylion-pipeline/sylion/evidence/chain.py` | Merkle-tree integrity verification |
| Evidence Templates | `src/sylion-pipeline/sylion/evidence/templates/` | `d3_light`, `d5_full`, `audit_only`, `council_signoff` |
| Storage Adapter | `src/sylion-pipeline/sylion/storage/s3_adapter.py` | S3/MinIO file ops |
| Core API | `src/sylion-pipeline/sylion/api/core_routes.py` | `/api/v1/core/evidence` endpoint |

### 10.3. Powiązane hooki

| Hook | Plik |
|------|------|
| `useHealth` | `src/sylion-frontend/src/lib/api/hooks.ts` |
| `useEvidence` | `src/sylion-frontend/src/lib/api/hooks.ts` |

### 10.4. Powiązane utilities i typy

| Symbol | Plik |
|--------|------|
| `EvidencePack` (type) | `src/sylion-frontend/src/lib/types.ts` |
| `cn` (classnames merge) | `src/sylion-frontend/src/lib/utils.ts` |
| `getDecisionClassBgColor` | `src/sylion-frontend/src/lib/utils.ts` |
| `getFidelityColor` | `src/sylion-frontend/src/lib/utils.ts` |

### 10.5. Powiązane templates evidence

| Template | Wymagane artefakty |
|----------|---------------------|
| `d3_light` | analysis, baseline, plan |
| `d5_full` | analysis, baseline, plan, audit, matrix, timeline, procedure, signoff, log, architecture, signature |
| `audit_only` | audit, log |
| `council_signoff` | review, signoff, signature |

### 10.6. Powiązane dokumenty governance

| Dokument | Wpływ |
|----------|-------|
| AEIS Canonical Full Model 2026-04-24 | Definiuje 6 D-levels, evidence requirements per level, 13 etapów audytu |
| Decision Gates & Governance | Code snapshots, cascade analysis, compliance matrix, conflicts, evidence spine |
| AEIS extended model | Hash chain integrity (9-warstwowy model) |

### 10.7. Powiązane testy

| Test | Plik |
|------|------|
| EvidencePage smoke | `src/sylion-frontend/src/app/(app)/evidence/__tests__/page.test.tsx` (TBD) |
| `useEvidence` hook | `src/sylion-frontend/src/lib/api/__tests__/hooks.test.ts` |
| Evidence Manager unit | `src/sylion-pipeline/tests/unit/test_evidence_manager.py` |
| Chain integrity | `src/sylion-pipeline/tests/unit/test_evidence_chain.py` |

### 10.8. Open questions / TODO

- Dodać search bar (po `evidence_id`, `proposal_id`).
- Dodać multi-select filtry (class, status, source, template).
- Dodać sort headers w tabeli.
- Dodać download button per artefakt + per pack (ZIP).
- Dodać "Verify chain" button per pack — wywołanie `/verify` endpoint i pokaż real-time results.
- Dodać preview dla PDF / image artefaktów (Radix Dialog z embedded viewer).
- Dodać paginację cursor-based.
- Dodać `?proposal_id=...` query param dla auto-scroll/auto-expand.
- A11y: `tabIndex` + `aria-expanded` + keyboard navigation w tabeli.
- Dodać "Live verify" — re-verify chain co 5 min w tle, pokaż toast jeśli mismatch.
- Eksport raportu CSV/JSON.
