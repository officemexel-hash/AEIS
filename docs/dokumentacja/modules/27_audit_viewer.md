# 27. Unified Audit Trail Viewer — Chain Integrity i Tamper Detection
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja warstwy frontend dla powierzchni `/audit`. Strona prezentuje
> zunifikowany evidence chain ze wszystkich obszarów SYLION AEIS: governance,
> projekty, council, workspace, advisor, lifecycle hooks, IT-AUDIT. Każdy event
> ma `hash` linkujący do poprzedniego (Merkle-tree style), co pozwala na
> weryfikację integrity i wykrywanie tamperingu. Strona jest **read-only** z
> dwoma akcjami: Verify Chain + Tamper Check.

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
| Ścieżka | `/audit` |
| Plik źródłowy | `src/sylion-frontend/src/app/(app)/audit/page.tsx` |
| Komponent główny | `AuditPage` (default export) |
| Layout | `(app)` route group; lewy sidebar widoczny |
| Persona | Operator + Audit Reviewer (read-only); Compliance Officer |
| Cel | Globalny rejestr `aeis.*` events, weryfikacja chain integrity |
| Refresh | `useAuditEvents({ limit: 100 })`, `useAuditSummary()` polling |
| Strict requirement | **Wymaga live backend** — bez połączenia full-page error |

W przeciwieństwie do `/evidence` (który pokazuje **packs** z artefaktami), `/audit`
pokazuje **flat event stream** ze wszystkich źródeł w systemie. Każdy event ma:

- `event_type` (np. `aeis.governance.proposal_voted`, `aeis.lifecycle.h08_decision`)
- `source` (governance/lifecycle/council/advisor/...)
- `actor` (operator_id, agent_id, lub system)
- `action` (human-readable opis)
- `severity` (critical/high/medium/low/info)
- `outcome` (success/failure/denied/error)
- `hash` (SHA-256 linkowany do poprzedniego eventu w chainie)

Strona implementuje 2 critical-path akcje:

1. **Verify Chain** — re-computes Merkle root i porównuje z stored value.
2. **Tamper Check** — verifies każdy `hash` w chainie i raportuje liczbę tampered events.

---

## 2. Komponenty UI

```
┌─────────────────────────────────────────────────────────────┐
│ Header (Lock icon + title + Refresh button)                 │
├─────────────────────────────────────────────────────────────┤
│ IF loading: Skeleton (3 placeholder boxes)                  │
│ IF !backendLive: Full-page error Card with WifiOff + Retry  │
│ ELSE:                                                       │
│   Stats row (2 cards):                                      │
│     ├ Total Events                                          │
│     └ Chain Integrity (UNKNOWN/VALID/INVALID)               │
│   Chain Verification panel:                                 │
│     ├ Verify Chain button                                   │
│     ├ Tamper Check button                                   │
│     └ Result badge (NO TAMPERING / TAMPERING DETECTED)      │
│   Audit Events table (timestamp/type/actor/action/severity) │
└─────────────────────────────────────────────────────────────┘
```

### 2.1. Header (linie 238–255)

| Element | Treść |
|---------|-------|
| Container | `flex items-start justify-between` |
| Icon box | `w-9 h-9 rounded-lg bg-sylion-green/10` z `Lock` icon |
| H1 | "Unified Audit Trail" |
| Sub-line | "Operator-visible governance, project, council, and workspace evidence chain" |
| Refresh button | `<Button variant="outline">` z `RefreshCw` icon |

W trybie offline icon box ma `bg-sylion-red/10` zamiast green.

### 2.2. Loading skeleton (linie 184–202)

Placeholder dla initial load — gdy `useHealth()` jeszcze fetchuje. Skeleton ma:

```tsx
<div className="space-y-5">
  <div className="flex items-center gap-3">
    <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
    <div>
      <div className="h-6 w-36 bg-muted animate-pulse rounded" />
      <div className="h-4 w-52 bg-muted animate-pulse rounded mt-1" />
    </div>
  </div>
  <div className="grid grid-cols-2 gap-3">
    {[1, 2].map((i) => <div className="h-20 bg-muted animate-pulse rounded-lg" />)}
  </div>
  <div className="h-64 bg-muted animate-pulse rounded-lg" />
</div>
```

`animate-pulse` zapewnia visual feedback że ładowanie trwa.

### 2.3. Empty state — backend offline

```tsx
<Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
  <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
    <WifiOff className="w-7 h-7 text-sylion-red" />
  </div>
  <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend Not Reachable</h2>
  <p className="text-sm text-muted-foreground max-w-md mb-4">
    The SYLION backend is not responding. Audit trail data, chain verification, and tamper detection require a running backend.
  </p>
  <Button variant="outline" size="sm" onClick={handleRefreshAll}>
    <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
    Retry Connection
  </Button>
</Card>
```

W odróżnieniu od `/evidence` (która ma simple WifiOff message), `/audit` ma **active
Retry button**. Powód: chain verification jest critical-path — operator musi mieć
sposób natychmiastowego retry.

### 2.4. Stats row (2 KPI cards)

| Card | Wartość | Color | Icon |
|------|---------|-------|------|
| Total Events | `auditSummary.total_entries` lub `events.length` | `text-sylion-blue` | `Activity` |
| Chain Integrity | `chainIntegrityLabel` ("UNKNOWN"/"VALID"/"INVALID") | dynamiczny | `CheckCircle2`/`XCircle`/`FileCheck` |

Chain Integrity card zmienia kolor w zależności od `chainStatus`:

| `chainStatus` | Label | Color | Icon | Background |
|---------------|-------|-------|------|------------|
| `'idle'` (initial) | "UNKNOWN" | `text-muted-foreground` | `FileCheck` | `bg-muted/20` |
| `'valid'` | "VALID" | `text-sylion-green` | `CheckCircle2` | `bg-sylion-green/10` |
| `'invalid'` | "INVALID" | `text-sylion-red` | `XCircle` | `bg-sylion-red/10` |

### 2.5. Chain Verification panel (linie 300–353)

Card z 4 elementami:

| Element | Layout |
|---------|--------|
| Title | `<FileCheck>` icon + "Chain Verification" |
| Verify Chain button | `<Button>` z `CheckCircle2` icon (lub spinner) |
| Tamper Check button | `<Button>` z `Shield` icon (lub spinner) |
| Result badge | NO TAMPERING (zielony) / TAMPERING DETECTED (czerwony) |

Buttons są disabled gdy odpowiednio `verifying` lub `tamperChecking` jest true.
Spinner `<RefreshCw className="animate-spin">` zastępuje icon.

### 2.6. Audit Events table

`<Table>` z 5 kolumnami:

| # | Header | Cell content | Style |
|---|--------|--------------|-------|
| 1 | Timestamp | `formatTimestamp(event.timestamp)` z `<Activity>` ikoną | `text-[11px] text-muted-foreground` |
| 2 | Event Type | `event.event_type` lub `event.source` | `text-xs font-mono` |
| 3 | Actor | `event.actor` | `text-xs text-muted-foreground` |
| 4 | Action | `event.action` truncated `max-w-[250px]` | `text-xs truncate block` |
| 5 | Severity | Badge z dot + uppercase severity | varies |

#### 2.6.1. Severity badge

5 wariantów per `severity`:

| Severity | Border | Text | Background | Dot |
|----------|--------|------|------------|-----|
| `critical` | `border-sylion-red/30` | `text-sylion-red` | `bg-sylion-red/5` | `bg-sylion-red` |
| `high` | `border-orange-400/30` | `text-orange-400` | `bg-orange-400/5` | `bg-orange-400` |
| `medium` | `border-sylion-amber/30` | `text-sylion-amber` | `bg-sylion-amber/5` | `bg-sylion-amber` |
| `low` | `border-sylion-green/30` | `text-sylion-green` | `bg-sylion-green/5` | `bg-sylion-green` |
| `info` | `border-sylion-blue/30` | `text-sylion-blue` | `bg-sylion-blue/5` | `bg-sylion-blue` |

#### 2.6.2. Empty events state

```tsx
<div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
  <Search className="w-8 h-8 mb-3 opacity-30" />
  <p className="text-xs">No audit events available</p>
  <p className="text-[10px] mt-1 opacity-60">
    Events will appear here as governance, project, council, and workspace actions are logged
  </p>
</div>
```

Renderowany gdy `events.length === 0` (rzadko — w live system zawsze są jakieś events).

### 2.7. Severity inference

Backend może zwracać `severity` field explicite, ale jeśli nie:

```ts
function eventSeverity(event: AuditEvent): string {
  const explicit = String(event.severity || event.metadata?.severity || "");
  if (explicit) return explicit;
  if (event.outcome === "failure" || event.outcome === "error") return "high";
  if (event.outcome === "denied") return "medium";
  return "info";
}
```

Heurystyka:
- explicit `severity` w event → wygrywa
- `metadata.severity` → fallback
- `outcome=failure/error` → `high`
- `outcome=denied` → `medium` (np. policy block)
- inaczej → `info`

---

## 3. Kontrolki i interakcje

### 3.1. Kliknięcie Refresh

```ts
const handleRefreshAll = () => {
  fetchHealth();
  refreshAudit();
  refreshSummary();
};
```

Trigger 3 osobnych re-fetches. Brak loading indicator w MVP. Hook'i mają własne
internal state — w UI operator widzi nowe dane gdy się pojawią. TODO: pokazać
spinner na refresh button.

### 3.2. Kliknięcie Verify Chain

```ts
const handleVerifyChain = useCallback(() => {
  setVerifying(true);
  api.getAuditIntegrity()
    .then((result: any) => {
      setChainStatus(result.valid === true ? "valid" : "invalid");
    })
    .catch(() => {
      setChainStatus("invalid");
    })
    .finally(() => {
      setVerifying(false);
    });
}, []);
```

Disabled gdy `verifying`. Button text: "Verify Chain" → "Verifying...". Po sukcesie
chain stat card zmienia się z UNKNOWN na VALID lub INVALID. Brak detail dialog —
operator widzi tylko binary status.

### 3.3. Kliknięcie Tamper Check

```ts
const handleTamperCheck = useCallback(() => {
  setTamperChecking(true);
  api.getAuditIntegrity()
    .then((result: any) => {
      setTamperStatus(result.valid === true && (result.tampered_count || 0) === 0 ? "clean" : "detected");
    })
    .catch(() => {
      setTamperStatus("detected");
    })
    .finally(() => {
      setTamperChecking(false);
    });
}, []);
```

Disabled gdy `tamperChecking`. Button text: "Tamper Check" → "Checking...". Po sukcesie
pokazuje się badge:
- "NO TAMPERING" (zielony) jeśli `result.valid && tampered_count === 0`
- "TAMPERING DETECTED" (czerwony) inaczej

### 3.4. Tabela — sortowanie i filtrowanie

Brak. Eventy są presortowane DESC po timestamp przez backend. TODO:
- Dodać clickable headers (sort by Type, Actor, Severity)
- Dodać filter chips (severity, source, actor)
- Dodać search input (po `action`, `event_type`)

### 3.5. Tabela — paginacja

Brak. `useAuditEvents({ limit: 100 })` zwraca top 100 events. Nie ma "Load more"
ani cursor-based pagination. TODO: dodać `?cursor=...&limit=...` z infinite scroll.

### 3.6. Tabela — drill-down do detail

Brak. Kliknięcie wiersza nie robi nic. TODO: dodać `<Dialog>` z full event details
(metadata, hash, related events).

---

## 4. Zarządzanie stanem

### 4.1. Hooki React

```ts
const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
const healthData = healthRaw as { status: string; version: string; modules: number; endpoints: number; db_mode?: string };
const backendLive = healthData.status === "ok";

const { data: auditData, refresh: refreshAudit } = useAuditEvents({ limit: 100 });
const { data: summaryData, refresh: refreshSummary } = useAuditSummary();

const events: AuditEvent[] = (auditData as any).events ?? [];
const auditSummary = summaryData as any;

const [verifying, setVerifying] = useState(false);
const [tamperChecking, setTamperChecking] = useState(false);
const [chainStatus, setChainStatus] = useState<"idle" | "valid" | "invalid">("idle");
const [tamperStatus, setTamperStatus] = useState<"idle" | "clean" | "detected">("idle");
```

| Stan | Typ | Cel |
|------|-----|-----|
| `healthData` | `{ status, version, modules, endpoints, db_mode }` | Backend health |
| `loading` | `boolean` | Initial fetch state — pokazuje skeleton |
| `auditData` | `{ events: AuditEvent[], total, ... }` | Lista eventów |
| `summaryData` | `{ total_entries, by_severity, ... }` | Aggregate counts |
| `verifying` | `boolean` | Verify Chain in-progress |
| `tamperChecking` | `boolean` | Tamper Check in-progress |
| `chainStatus` | `'idle' \| 'valid' \| 'invalid'` | Wynik ostatniej weryfikacji |
| `tamperStatus` | `'idle' \| 'clean' \| 'detected'` | Wynik ostatniego tamper check |

### 4.2. Memoizacja

```ts
const chainIntegrityLabel = useMemo(() => {
  if (chainStatus === "valid") return "VALID";
  if (chainStatus === "invalid") return "INVALID";
  return "UNKNOWN";
}, [chainStatus]);

const chainIntegrityColor = useMemo(() => {
  if (chainStatus === "valid") return "text-sylion-green";
  if (chainStatus === "invalid") return "text-sylion-red";
  return "text-muted-foreground";
}, [chainStatus]);
```

Memoized derived state dla stat card (Total Events / Chain Integrity).

### 4.3. Initial state

| Komponent ładowania | UI |
|---------------------|-----|
| `loading=true` (hooks fetching) | Skeleton |
| `backendLive=false` (po fetch) | Error card |
| Init `chainStatus='idle'` | Card pokazuje UNKNOWN |
| Init `tamperStatus='idle'` | Brak badge "NO TAMPERING" / "TAMPERING DETECTED" |

Operator MUSI manually kliknąć Verify Chain i Tamper Check aby zobaczyć stan.
Strona NIE auto-verifies przy load. Powód: weryfikacja może być expensive na
wielkich chainach (10000+ events).

---

## 5. Integracja API

### 5.1. Endpointy

| Metoda | Endpoint | Hook / call | Cel |
|--------|----------|-------------|-----|
| GET | `/api/health` | `useHealth()` | Health probe |
| GET | `/api/v1/audit/events?limit=100` | `useAuditEvents({ limit: 100 })` | Lista eventów |
| GET | `/api/v1/audit/summary` | `useAuditSummary()` | Aggregate counts |
| GET | `/api/v1/audit/integrity` | `api.getAuditIntegrity()` | Verify chain + tamper count |
| GET | `/api/v1/audit/export?format=csv\|json` | (nieużywane w MVP) | Export raportu |

### 5.2. Schema `AuditEvent`

```ts
interface AuditEvent {
  event_id?: string;
  entry_id?: string;                  // alternatywne ID (DB primary key)
  timestamp?: number;                 // Unix epoch (s lub ms)
  event_type?: string;                // np. "aeis.governance.proposal_voted"
  source?: string;                    // np. "governance"
  actor?: string;                     // operator_id, agent_id, "system"
  action?: string;                    // human-readable, np. "voted for proposal X"
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info';
  outcome?: 'success' | 'failure' | 'denied' | 'error';
  resource?: string;                  // affected resource ID
  details?: string;                   // additional details
  metadata?: Record<string, unknown>; // arbitrary metadata
  hash?: string;                      // SHA-256 hash (chain link)
}
```

### 5.3. Schema `AuditSummary`

```ts
interface AuditSummary {
  total_entries: number;
  by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  by_source: Record<string, number>; // np. { governance: 234, lifecycle: 892, ... }
  by_outcome: {
    success: number;
    failure: number;
    denied: number;
    error: number;
  };
  date_range: {
    earliest: string; // ISO 8601
    latest: string;
  };
}
```

### 5.4. Schema `IntegrityResult`

```ts
interface IntegrityResult {
  valid: boolean;
  chain_height: number;             // total events checked
  tampered_count: number;           // 0 if clean
  tampered_event_ids: string[];     // empty if clean
  merkle_root: string;              // computed root
  expected_root: string;            // stored root
  verified_at: string;              // ISO 8601
}
```

### 5.5. Response — events list

```http
GET /api/v1/audit/events?limit=100 HTTP/1.1

HTTP/1.1 200 OK
{
  "events": [
    {
      "entry_id": "evt_20260426_a1b2c3",
      "timestamp": 1745660000,
      "event_type": "aeis.governance.proposal_voted",
      "source": "governance",
      "actor": "op_demo_2026",
      "action": "voted for proposal prop_council_xyz",
      "severity": "info",
      "outcome": "success",
      "resource": "prop_council_xyz",
      "metadata": { "vote": "for", "weight": 2.0 },
      "hash": "0x8f2a1b3c4d5e..."
    },
    {
      "entry_id": "evt_20260426_d4e5f6",
      "timestamp": 1745659200,
      "event_type": "aeis.lifecycle.h08_decision_gate",
      "source": "lifecycle",
      "actor": "system",
      "action": "Escalated D3 to council",
      "severity": "medium",
      "outcome": "success",
      "resource": "proj_abc/h08",
      "metadata": { "decision_class": "D3", "gate": "council" },
      "hash": "0x7f1a2b3c..."
    }
  ],
  "total": 2456,
  "limit": 100,
  "offset": 0
}
```

### 5.6. Response — summary

```http
GET /api/v1/audit/summary HTTP/1.1

HTTP/1.1 200 OK
{
  "total_entries": 12847,
  "by_severity": {
    "critical": 2,
    "high": 18,
    "medium": 142,
    "low": 587,
    "info": 12098
  },
  "by_source": {
    "governance": 234,
    "lifecycle": 8921,
    "council": 412,
    "advisor": 1834,
    "evidence": 982,
    "it_audit": 464
  },
  "by_outcome": {
    "success": 12698,
    "failure": 87,
    "denied": 41,
    "error": 21
  },
  "date_range": {
    "earliest": "2026-01-15T08:00:00Z",
    "latest": "2026-04-26T11:42:18Z"
  }
}
```

### 5.7. Response — integrity check

```http
GET /api/v1/audit/integrity HTTP/1.1

HTTP/1.1 200 OK
{
  "valid": true,
  "chain_height": 12847,
  "tampered_count": 0,
  "tampered_event_ids": [],
  "merkle_root": "0xabcdef0123456789...",
  "expected_root": "0xabcdef0123456789...",
  "verified_at": "2026-04-26T11:42:30Z"
}
```

### 5.8. Response — integrity check (tampered)

```http
HTTP/1.1 200 OK
{
  "valid": false,
  "chain_height": 12847,
  "tampered_count": 3,
  "tampered_event_ids": ["evt_20260420_xyz", "evt_20260421_abc", "evt_20260422_def"],
  "merkle_root": "0x1111111111111111...",
  "expected_root": "0xabcdef0123456789...",
  "verified_at": "2026-04-26T11:42:30Z"
}
```

UWAGA: w MVP frontend pokazuje tylko binary "TAMPERING DETECTED" — bez listy
tampered IDs. TODO: rozszerzyć UI o detail dialog z listą tampered events i opcją
quarantine/restore.

### 5.9. Error handling

| Sytuacja | UI |
|----------|-----|
| `useHealth` initial fetch | Skeleton |
| `health.status !== "ok"` | Full-page error card z Retry button |
| 401 | Redirect do `/auth` (axios interceptor) |
| 403 (no audit access) | Empty state — "No audit events available" (TBD: dedicated 403 message) |
| Verify Chain timeout | `setChainStatus('invalid')` + button enabled |
| Tamper Check timeout | `setTamperStatus('detected')` + button enabled |
| Empty events list | `<Search>` icon + "No audit events available" |

---

## 6. Persistencja

### 6.1. Tabela `audit.events`

```sql
CREATE TABLE audit.events (
  entry_id TEXT PRIMARY KEY,
  timestamp BIGINT NOT NULL,                  -- Unix epoch (s)
  event_type TEXT NOT NULL,                   -- aeis.* taxonomy
  source TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  severity TEXT CHECK (severity IN ('critical','high','medium','low','info')),
  outcome TEXT CHECK (outcome IN ('success','failure','denied','error')),
  resource TEXT,
  details TEXT,
  metadata JSONB,
  hash TEXT NOT NULL,                         -- SHA-256(prev_hash + payload)
  prev_hash TEXT,                             -- pointer to previous event
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_timestamp ON audit.events(timestamp DESC);
CREATE INDEX idx_audit_source ON audit.events(source);
CREATE INDEX idx_audit_severity ON audit.events(severity);
CREATE INDEX idx_audit_actor ON audit.events(actor);
```

### 6.2. Hash chain

Każdy event ma:

```
hash = SHA256(prev_hash || event_id || timestamp || event_type || actor || action || severity || resource || metadata)
```

Pierwszy event ma `prev_hash = '0x00...00'` (genesis). Merkle root computed
periodically (co 1 min) i zapisany w `audit.chain_state`:

```sql
CREATE TABLE audit.chain_state (
  state_id SERIAL PRIMARY KEY,
  chain_height BIGINT NOT NULL,
  merkle_root TEXT NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 6.3. Tamper detection algorithm

Backend's `/api/v1/audit/integrity`:

1. Pobiera `expected_root` z najnowszego `chain_state`.
2. Iteruje przez wszystkie events w chronological order.
3. Dla każdego event recomputes hash i porównuje z stored `hash`.
4. Buduje Merkle tree i computes root.
5. Porównuje computed `merkle_root` z `expected_root`.
6. Zwraca `valid=true` jeśli match, plus `tampered_count` (liczba events gdzie hash mismatch).

Performance: dla chain z 12k events ~200ms. Dla 1M events ~30s. TODO: dodać
incremental verification (verify tylko od ostatniej znanej-good position).

### 6.4. Frontend cache

| Klucz | Storage | TTL |
|-------|---------|-----|
| `react-query: audit:events` | in-memory | 30 s staleTime |
| `react-query: audit:summary` | in-memory | 60 s staleTime |
| `react-query: health` | in-memory | 15 s |
| `chainStatus`, `tamperStatus` | useState (component-local) | unmount = reset |

Brak persistencji do localStorage — chain verification result jest zawsze ad-hoc.

### 6.5. Retention policy

Default backend retention: 365 dni dla events, 7 lat dla `chain_state`. Po 365 dniach
events są archived do cold storage (S3 Glacier), ale `chain_state` zachowywany dla
long-term verification.

---

## 7. Tryby i warianty

### 7.1. Loading state

| State | UI |
|-------|-----|
| Initial mount, `loading=true` | Skeleton (3 placeholder boxes) |
| `loading=false`, `backendLive=false` | Error card |
| `loading=false`, `backendLive=true` | Pełna strona |

### 7.2. Chain status

| `chainStatus` | Card label | Color | Icon | Background |
|---------------|-----------|-------|------|------------|
| `'idle'` | UNKNOWN | muted | `FileCheck` | `bg-muted/20` |
| `'valid'` | VALID | green | `CheckCircle2` | `bg-sylion-green/10` |
| `'invalid'` | INVALID | red | `XCircle` | `bg-sylion-red/10` |

### 7.3. Tamper status

| `tamperStatus` | Badge | Visible? |
|----------------|-------|----------|
| `'idle'` | (brak) | nie |
| `'clean'` | "NO TAMPERING" zielony z `CheckCircle2` | tak |
| `'detected'` | "TAMPERING DETECTED" czerwony z `AlertTriangle` | tak |

### 7.4. Severity (per event)

5 wariantów (patrz 2.6.1). Severity inferowany z `eventSeverity()` jeśli nie podany explicite.

### 7.5. Event source taxonomy

Backend's `aeis.*` taxonomy:

| Source | Przykładowe event_types |
|--------|--------------------------|
| `governance` | `aeis.governance.proposal_created`, `aeis.governance.proposal_voted`, `aeis.governance.policy_enforced` |
| `lifecycle` | `aeis.lifecycle.h01_inception`, `aeis.lifecycle.h08_decision_gate`, `aeis.lifecycle.h16_archived` |
| `council` | `aeis.council.session_started`, `aeis.council.consensus_reached`, `aeis.council.critic_signed` |
| `advisor` | `aeis.advisor.card_created`, `aeis.advisor.card_accepted`, `aeis.advisor.preference_changed` |
| `evidence` | `aeis.evidence.pack_created`, `aeis.evidence.signed`, `aeis.evidence.validated` |
| `it_audit` | `aeis.it_audit.scan_started`, `aeis.it_audit.violation_detected`, `aeis.it_audit.auto_fix_applied` |
| `funding` | `aeis.funding.deadline_check`, `aeis.funding.grant_match` |

### 7.6. Outcome variants

| Outcome | Implied severity if no explicit |
|---------|---------------------------------|
| `success` | `info` |
| `denied` | `medium` |
| `failure` | `high` |
| `error` | `high` |

### 7.7. Empty events

| State | UI |
|-------|-----|
| `events.length === 0` | `<Search>` icon + "No audit events available" |
| `events.length > 0` | Tabela ze 100 entries |

---

## 8. Dostępność

### 8.1. Klawiatura

| Klawisz | Akcja | Status |
|---------|-------|--------|
| `Tab` / `Shift+Tab` | Nawigacja | OK (natywne) |
| `Enter/Space` na "Verify Chain" | Trigger verify | OK |
| `Enter/Space` na "Tamper Check" | Trigger check | OK |
| `Enter/Space` na "Refresh" | Trigger refresh | OK |
| `Tab` na table rows | **Brak** focusable rows | **TODO** |

Tabela nie ma row interactivity w MVP — operator nie może drill-down do detail.

### 8.2. ARIA

- `<Table>` z Radix ma natywne `role="table"` z `<th>` headers.
- Buttons mają text content + ikony dekoracyjne.
- Severity badges: kolor + tekst (UPPERCASE) — czytelne przez SR.
- TODO: dodać `aria-busy` na tabelę gdy refreshing.
- TODO: dodać `aria-live="polite"` dla nowych events (jeśli bedzie real-time updates).

### 8.3. Kontrast

| Element | Status |
|---------|--------|
| H1 + sub-line | OK |
| Stat cards | OK |
| Verify/Tamper buttons | OK |
| Severity badge `text-[9px]` | granica AA — uppercase + font-weight pomaga |
| Event row text-[11px] | OK |
| Action truncate `max-w-[250px]` | granica — może obciąć ważną treść |

TODO: zwiększyć size badge'y do `text-[10px]`, dodać tooltip na truncated action.

### 8.4. Reduced motion

`framer-motion` `<motion.div>` z `transition={{ duration: 0.3 }}` honoruje
`prefers-reduced-motion`. `animate-spin` na RefreshCw — można zatrzymać przy reduced motion.

### 8.5. Color-only encoding

Severity: kolor + tekst UPPERCASE. Chain status: kolor + tekst (VALID/INVALID/UNKNOWN).
Tamper: kolor + tekst (NO TAMPERING / TAMPERING DETECTED) + ikona. Spełnia WCAG.

### 8.6. Screen reader for chain verification

Operator z screen readerem klika "Verify Chain", słyszy:
1. "Verify Chain, button" (przed kliknięciem).
2. "Verifying..., button, dimmed" (in-progress, button disabled, gdyby był tekst zmieniony do "Verifying...").
3. (Po finish) screen reader nie auto-announces nowego stanu — operator musi przetabować z powrotem.

TODO: dodać `aria-live` region z status messages.

---

## 9. Przepływy operatora

### 9.1. Operator otwiera audit page po raz pierwszy

1. Operator nawiguje do `/audit`.
2. Skeleton się pokazuje (3 placeholder boxes z `animate-pulse`).
3. `useHealth()` resolve'uje, `health.status="ok"` → `loading=false`, `backendLive=true`.
4. `useAuditEvents()` zwraca 100 events.
5. `useAuditSummary()` zwraca `total_entries=12847`.
6. UI renderuje:
   - Total Events: 12847
   - Chain Integrity: UNKNOWN (operator jeszcze nie verifikował)
   - Audit Events table z 100 najnowszymi eventami.
7. Operator scanuje listę — najnowszy event to `aeis.governance.proposal_voted` z minutę temu.

### 9.2. Operator wykonuje pełną weryfikację chainu

1. Operator klika **Verify Chain**.
2. Button text zmienia się na "Verifying..." z spinning RefreshCw.
3. Frontend wywołuje `api.getAuditIntegrity()`.
4. Backend (~200ms dla 12k events):
   a. Pobiera latest `chain_state.merkle_root`.
   b. Iteruje przez events, recomputes hashes.
   c. Builds Merkle tree.
   d. Porównuje computed root z stored.
   e. Zwraca `{valid: true, chain_height: 12847, tampered_count: 0, ...}`.
5. Frontend ustawia `chainStatus='valid'`.
6. Card "Chain Integrity" zmienia się: UNKNOWN → VALID (zielony, `CheckCircle2`).
7. Button reverts do "Verify Chain" (enabled).
8. Operator widzi że chain jest valid.

### 9.3. Operator wykrywa tampering

1. Operator klika **Tamper Check**.
2. Button text: "Checking...".
3. Frontend `api.getAuditIntegrity()`.
4. Backend zwraca `{valid: false, tampered_count: 3, tampered_event_ids: [...]}`.
5. Frontend ustawia `tamperStatus='detected'`.
6. Badge "TAMPERING DETECTED" pojawia się czerwony z `AlertTriangle` icon.
7. Operator panicuje.
8. (Poza UI) operator kontaktuje się z security team.
9. (TODO future) klika "View Tampered Events" → otwiera modal z listą 3 IDs i ich details.
10. (TODO future) Operator może zacząć investigation — sprawdzić logi backupu, identify time of tamper.

### 9.4. Operator monitoruje krytyczne eventy

1. Operator otwiera `/audit`.
2. Scanuje listę po severity.
3. Widzi 1 event z czerwonym badge "CRITICAL":
   - Timestamp: Apr 26, 11:30 AM
   - Event Type: `aeis.it_audit.violation_detected`
   - Actor: `system`
   - Action: "Hard policy violation: TLS 1.2 connection blocked from external"
   - Severity: CRITICAL
4. Operator decyduje że to warto zbadać.
5. (TODO future) klika wiersz → modal z full metadata (`source_ip`, `endpoint`, `policy_id`).
6. W MVP operator musi użyć backend logs lub admin tool aby zobaczyć szczegóły.

### 9.5. Operator analizuje voting activity

1. Operator chce zobaczyć kto głosował na proposal `prop_council_xyz` w ostatnim tygodniu.
2. W `/audit` brak filtrów — operator scrolluje 100 events i wzrokowo szuka.
3. Znajduje 5 events z `event_type=aeis.governance.proposal_voted`:
   - `op_a` voted (info)
   - `op_b` voted (info)
   - `op_c` voted (info)
   - `op_d` voted (info)
   - `op_e` voted (info)
4. Pożądana funkcja TODO: filter `event_type=aeis.governance.*` + `resource=prop_council_xyz`.
5. Lub directly w `/governance` Voting Activity tab (patrz [`26_council_voting.md`](26_council_voting.md)).

### 9.6. Backend wraca po awarii

1. Operator otwiera `/audit` w trakcie awarii backendu.
2. Skeleton → po fetch `health.status="down"` → error card "Backend Not Reachable".
3. Operator widzi `<WifiOff>` icon, message, i Retry button.
4. (Operator separately uruchamia backend.)
5. Operator klika **Retry Connection**.
6. `handleRefreshAll()` → `fetchHealth()` re-tries.
7. `health.status="ok"` → re-render to pełna strona.
8. Operator widzi normalny audit feed.

### 9.7. Compliance officer prepares quarterly report

1. Officer otwiera `/audit`.
2. Klik **Verify Chain** → VALID.
3. Klik **Tamper Check** → NO TAMPERING.
4. Officer screenshotuje stat cards (Total Events: 12847, Chain Integrity: VALID).
5. Officer klika `<button>` Export (TODO: not implemented in MVP).
6. (TODO) Backend generuje CSV z events od ostatniego kwartału.
7. (TODO) Download starts: `audit_q1_2026.csv` (np. 234 KB).
8. Officer załącza CSV + screenshots do quarterly compliance report.
9. W MVP officer musi użyć backend CLI: `python -m sylion.audit.export --from 2026-01-01 --to 2026-04-26 --format csv`.

---

## 10. Cross-references

### 10.1. Powiązane surfaces

| Surface | Plik | Relacja |
|---------|------|---------|
| `/evidence` | [`25_evidence_pack_viewer.md`](25_evidence_pack_viewer.md) | Evidence packs są audited (event_type=`aeis.evidence.*`) |
| `/governance` | [`26_council_voting.md`](26_council_voting.md) | Vote/create proposal events widoczne tutaj |
| `/advisor` | [`20_advisor_feed.md`](20_advisor_feed.md) | Każda kard akcja generuje `aeis.advisor.*` event |
| `/projects/[id]/lifecycle` | [`22_lifecycle_dashboard.md`](22_lifecycle_dashboard.md) | Lifecycle hooks H01-H16 emitują events |
| `/dashboard/operator-monitor` | [`23_operator_monitor.md`](23_operator_monitor.md) | Alerts banner pokazuje critical events; "View all alerts" linkuje do `/audit?severity=critical` (TBD) |
| `/settings/advisor` | [`24_settings_advisor.md`](24_settings_advisor.md) | Preference changes → `aeis.advisor.preference_changed` event |

### 10.2. Powiązane backend modules

| Moduł | Folder | Rola |
|-------|--------|------|
| Audit Engine | `src/sylion-pipeline/sylion/audit/` | Append events, build chain, verify |
| Audit API | `src/sylion-pipeline/sylion/api/audit_routes.py` | `/api/v1/audit/*` endpoints |
| Audit Chain | `src/sylion-pipeline/sylion/audit/chain.py` | Hash chain logic, Merkle root computation |
| Audit Exporter | `src/sylion-pipeline/sylion/audit/exporter.py` | CSV/JSON export (TODO: integrated into UI) |
| Event Bus | `src/sylion-pipeline/sylion/events/bus.py` | `aeis.*` event taxonomy publisher |

### 10.3. Powiązane hooki

| Hook | Plik |
|------|------|
| `useHealth` | `src/sylion-frontend/src/lib/api/hooks.ts` |
| `useAuditEvents` | `src/sylion-frontend/src/lib/api/hooks.ts` |
| `useAuditSummary` | `src/sylion-frontend/src/lib/api/hooks.ts` |

### 10.4. Powiązane API client methods

| Method | Plik |
|--------|------|
| `api.getAuditIntegrity()` | `src/sylion-frontend/src/lib/api/client.ts` |

### 10.5. Powiązane komponenty UI

| Komponent | Plik |
|-----------|------|
| `Table/TableHeader/TableBody/TableRow/TableCell/TableHead` | `src/sylion-frontend/src/components/ui/table.tsx` |
| `Card` | `src/sylion-frontend/src/components/ui/card.tsx` |
| `Badge` | `src/sylion-frontend/src/components/ui/badge.tsx` |
| `Button` | `src/sylion-frontend/src/components/ui/button.tsx` |

### 10.6. Powiązane utilities

| Symbol | Plik |
|--------|------|
| `cn` (classnames merge) | `src/sylion-frontend/src/lib/utils.ts` |
| `formatTimestamp` (inline) | `src/sylion-frontend/src/app/(app)/audit/page.tsx` (linie 88–98) |
| `eventSeverity` (inline) | tamże (linie 105–111) |
| `getSeverityStyles` (inline) | tamże (linie 100–103) |

**Uwaga i18n (sprint2, commit 7b004ef):** Cała strona jest w języku polskim. Data/czas formatowany
jest z locale `pl-PL` przez `toLocaleDateString("pl-PL", {...})`. Nazwy kolumn, akcji, statusów
i komunikatów błędów są przetłumaczone na polski. Zmienne wewnętrzne, nazwy pól API i wartości
stanu (np. `status: "success"`) pozostają w angielskim.

### 10.7. Powiązane dokumenty governance

| Dokument | Wpływ |
|----------|-------|
| AEIS Canonical Full Model 2026-04-24 | 13 etapów audytu, prefix `CLAUDE_AEIS_*`, 12 warstw |
| AEIS extended model | 9-warstwowy model z pamięcią + skills + audit chain integrity |
| Decision Gates & Governance | Każda decision D3+ generuje audit event z `severity` zależnym od D-level |
| Idea lifecycle canonical 11-state | Każda transition statusu ideas → audit event |
| Council canonical | Vote events, weighted score events, critic signatures |

### 10.8. Powiązane testy

| Test | Plik |
|------|------|
| AuditPage smoke | `src/sylion-frontend/src/app/(app)/audit/__tests__/page.test.tsx` (TBD) |
| `useAuditEvents` hook | `src/sylion-frontend/src/lib/api/__tests__/hooks.test.ts` |
| Audit chain integrity | `src/sylion-pipeline/tests/unit/test_audit_chain.py` |
| Event bus pub/sub | `src/sylion-pipeline/tests/unit/test_event_bus.py` |
| Tamper detection e2e | `src/sylion-pipeline/tests/e2e/test_audit_tamper_detection.py` |

### 10.9. Open questions / TODO

- Filter chips: severity (multi-select), source, actor.
- Search input: po `action`, `event_type`, `resource`, hash.
- Sort headers w tabeli.
- Pagination cursor-based (load more / infinite scroll).
- Drill-down dialog z full event details (metadata, hash, prev_hash, related events).
- Export CSV / JSON button (`/api/v1/audit/export`).
- Tampered events viewer: po "TAMPERING DETECTED" pokazać listę 3 IDs i details.
- Real-time updates przez WebSocket (zamiast polling co 30s).
- A11y: `aria-live` dla nowych events, focusable rows, large severity badges.
- Auto-verify on page load (toggle in settings).
- Quarantine workflow dla tampered events.
- Compare with backup: weryfikacja że chain matches snapshot z N dni temu.
