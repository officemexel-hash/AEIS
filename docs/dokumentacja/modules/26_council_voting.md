# 26. Council Voting & Governance — Proposals, Voting, Policies, Compliance
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja warstwy frontend dla powierzchni `/governance`. Strona jest centrum
> kontrolnym Council i policy management — operatorzy mogą tworzyć propozycje,
> głosować na otwarte, przeglądać policies, i monitorować compliance per scope.
> Council w SYLION AEIS to *9-rolowy* hybrydowy system z 5 rangami i ważonym
> głosowaniem. Surface obsługuje 4 zakładki: Proposals, Voting Activity, Policies,
> Compliance.

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
| Ścieżka | `/governance` |
| Plik źródłowy | `src/sylion-frontend/src/app/(app)/governance/page.tsx` |
| Komponent główny | `GovernancePage` (default export) |
| Layout | `(app)` route group; lewy sidebar widoczny |
| Persona | Operator + Council member (każdy operator może głosować) |
| Cel | Zarządzanie propozycjami, głosowanie, przegląd policies i compliance |
| Refresh | Polling przez `useProposals`, `usePolicies`, `useDecisionGates` (default 30 s) |
| Strict requirement | Wymaga live backend — bez połączenia pokazuje offline state |

Surface ten odpowiada za:

1. **Proposals** — lifecycle propozycji: open → closed → implemented/rejected.
2. **Voting Activity** — agregacja statystyk głosowania, vote distribution per proposal, recent timeline.
3. **Policies** — rejestr policies systemowych z filterem po category (security/deployment/budget/access).
4. **Compliance** — score per scope (pipeline/council/memory/security) + lista rules pass/fail/warning.

Strona NIE pokazuje detali per-vote per-role z ważonym wynikiem (TBD), ale pokazuje
agregaty `votes_for / votes_against / votes_abstain`.

---

## 2. Komponenty UI

```
┌─────────────────────────────────────────────────────────────┐
│ Header (Scale icon + title + LIVE/OFFLINE badge + Refresh)  │
├─────────────────────────────────────────────────────────────┤
│ IF !backendLive: Card with WifiOff + "Backend not reachable"│
│ ELSE:                                                       │
│   Stats row (4 cards):                                      │
│     ├ Active Proposals                                      │
│     ├ Policies Enacted                                      │
│     ├ Compliance Score (CircularScore SVG)                  │
│     └ Pending Votes                                         │
│   Tabs (proposals / voting / policies / compliance)         │
│     ├ Proposals: Create form + list of cards                │
│     ├ Voting: 3 KPIs + distribution + timeline              │
│     ├ Policies: filter chips + accordion list               │
│     └ Compliance: gauge + scope cards + rules table         │
└─────────────────────────────────────────────────────────────┘
```

### 2.1. Header (linie 444–481)

| Element | Treść |
|---------|-------|
| Container | `flex items-start justify-between` |
| Icon box | `w-9 h-9 rounded-lg bg-accent-amber-dim` z `Scale` icon |
| H1 | "Governance" |
| Sub-line | "Proposals, voting, policies, and compliance" |
| Status badge | LIVE (zielony) lub OFFLINE (czerwony z `WifiOff` icon) |
| Refresh button | `<Button variant="outline">` z `RefreshCw` icon (animuje gdy `refreshing`) |

### 2.2. Stats row (4 KPI cards, linie 499–564)

| Card | Wartość | Color | Icon | Sub-line |
|------|---------|-------|------|----------|
| Active Proposals | `activeProposals.length` | `text-sylion-blue` | `Gavel` | "{N} total" |
| Policies Enacted | `implementedCount` | `text-sylion-green` | `ShieldCheck` | "{N} active policies" |
| Compliance Score | `avgCompliance %` | `complianceTextColor()` | `CircularScore` (size=48) | "{N} passed / {M} issues" |
| Pending Votes | `totalPendingVotes` | `text-sylion-amber` | `Vote` | "{X}% participation" |

`CircularScore` to SVG progress circle z dynamicznym kolorem:
- `>= 80` → `#17C964` zielony
- `>= 50` → `#F59E0B` amber
- `< 50` → `#F31260` czerwony

### 2.3. Tabs (proposals / voting / policies / compliance)

```tsx
<Tabs value={activeTab} onValueChange={setActiveTab}>
  <TabsList>
    <TabsTrigger value="proposals"> Proposals </TabsTrigger>
    <TabsTrigger value="voting"> Voting Activity </TabsTrigger>
    <TabsTrigger value="policies"> Policies </TabsTrigger>
    <TabsTrigger value="compliance"> Compliance </TabsTrigger>
  </TabsList>
  ...
</Tabs>
```

Default tab: `proposals`. Tab state w komponencie React (nie w URL query param — TODO).

### 2.4. Proposals tab

#### 2.4.1. Header

```
{N} proposals total                              [+ Create Proposal]
```

Klik na "Create Proposal" otwiera inline form (akordeon).

#### 2.4.2. Create proposal form

Pojawia się przez `<AnimatePresence>` z framer-motion. Pola:

| Pole | Typ | Validation |
|------|-----|------------|
| Title | `<input type="text">` | required (`!newTitle.trim()` blokuje submit) |
| Description | `<textarea rows={3}>` | optional |
| Scope | `<select>` z opcjami: Pipeline / Council / Memory / Security | required |

Submit button: `Loader2` spinner gdy `submitting`. Cancel: `<Button variant="ghost">`.

#### 2.4.3. Proposal cards

Każda propozycja renderowana jako `<Card>` z:

| Element | Treść |
|---------|-------|
| Status icon box | `w-9 h-9 rounded-lg` z odpowiednim kolorem (open/implemented/rejected/closed) |
| Title | `text-sm font-semibold` |
| Status badge | open/closed/implemented/rejected z `statusConfig[].bgColor` |
| Scope badge | pipeline/council/memory/security z `scopeColor[]` |
| Description | `text-[11px] line-clamp-2` |
| Meta line | `proposal_id` (font-mono) + "by {proposer}" + `formatDate(created_at)` |
| Vote bar | progress bar (zielony For / czerwony Against / szary Abstain) |
| Vote counts | ThumbsUp + ThumbsDown + Minus z licznikami |
| Vote buttons | "For" / "Against" / "Abstain" (tylko jeśli `status === 'open'`) |

### 2.5. Voting Activity tab

#### 2.5.1. Summary cards (3-column grid)

| Card | Wartość | Color |
|------|---------|-------|
| Participation Rate | `participationRate %` | `text-sylion-blue` |
| Votes For | `voteHistory.filter(v.vote === "for").length` | `text-sylion-green` |
| Votes Against | `voteHistory.filter(v.vote === "against").length` | `text-sylion-red` |

#### 2.5.2. Vote Distribution by Proposal

Lista wszystkich proposals z `total > 0`. Każdy wpis:

```
{title}                        {total} votes
[========green=========][===red===][gray]
For: 5    Against: 2    Abstain: 1
```

Progress bar `h-3 rounded-full` z trzema segmentami w jednym `<div>`.

#### 2.5.3. Recent Vote Timeline

Lista 10 ostatnich votes (`voteHistory.slice(0, 10)`). Każdy wpis:

```
[ThumbsUp]  agent_a1 voted [for]
            Proposal: "Increase council size to 7"
            5m ago
```

Pionowa linia łącząca (`absolute left-[11px] top-7 bottom-0 w-px`) — timeline visualization.

UWAGA: `voteHistory` jest **generowany syntetycznie** z proposals. W MVP backend zwraca
tylko agregaty (`votes_for`, `votes_against`, `votes_abstain`) bez per-voter records.
Frontend tworzy fake records `agent_a1..agent_a4` i `board` jako placeholdery. TODO:
backend powinien expose'ować `/api/v1/governance/proposals/{id}/votes` z prawdziwymi voter IDs.

### 2.6. Policies tab

#### 2.6.1. Filter chips

```
{N} policies registered          [All] [Security] [Deployment] [Budget] [Access]
```

Klik na chip ustawia `policyFilter`. Default: `"all"`. Dynamicznie generuje chips z
unikalnych `category` w policies.

#### 2.6.2. Policy cards (accordion)

Każda policy jako `<Card>` clickable:

```
[Shield icon]  {name}  [active] [scope] [category] [hard/soft]    [chevron]
```

Klik rozwija expanded body (2-column grid):

| Lewa kolumna | Prawa kolumna |
|--------------|----------------|
| Description (opis polityki) | ID (font-mono) |
|                              | Scope (capitalize) |
|                              | Enforcement (kolorowo: hard=red, soft=amber) |

Tylko **jedna** policy może być rozwinięta jednocześnie (single-select, jak w evidence packs).

### 2.7. Compliance tab

#### 2.7.1. Compliance score grid (5-column)

| Col | Component | Width |
|-----|-----------|-------|
| 1 | Big CircularScore (size=100) z `pass / fail / warn` legend | 1 col |
| 2-5 | Per-scope cards: pipeline / council / memory / security | 4 cols |

Każda scope card:

| Element | Treść |
|---------|-------|
| Icon box (z `scopeBgColor[scope]`) | `Shield` |
| Scope name | `text-xs font-semibold capitalize` |
| Sub-line | "{rules_count} rules" |
| Score | `text-lg font-bold` z `complianceTextColor()` |
| Progress bar | `h-1.5 rounded-full` z `complianceColor()` |
| Violation alert | `text-sylion-red` "{N} violation(s)" jeśli `scopeFails > 0` |

#### 2.7.2. Compliance Rules table

Lista wszystkich `complianceRules` z divider. Każdy wiersz:

```
[icon] {name}  [scope badge]               [PASS/WARNING/FAIL]   {timeAgo}
       {description}
```

Background koloru:
- `pass` → brak (default)
- `warning` → `bg-sylion-amber/5`
- `fail` → `bg-sylion-red/5`

#### 2.7.3. Recent Compliance Checks timeline

Top 6 rules sortowanych DESC po `last_checked`. Każdy wpis ma `CircleDot` z odpowiednim
kolorem statusu i pionową linię timeline.

---

## 3. Kontrolki i interakcje

### 3.1. Refresh All

```ts
const handleRefreshAll = useCallback(async () => {
  setRefreshing(true);
  try {
    refreshHealth();
    refreshProposals();
    refreshPolicies();
    if (backendLive) {
      await fetchCompliance();
      await fetchComplianceRules();
    }
  } finally {
    setTimeout(() => setRefreshing(false), 600);
  }
}, [...]);
```

Klik wywołuje wszystkie hooki re-fetch. `setTimeout(600ms)` zapewnia że spinner
"animate-spin" jest widoczny minimum 600 ms (UX smoothing — bez tego user nie
widzi że coś się stało przy fast network).

### 3.2. Vote (For/Against/Abstain)

```ts
const handleVote = async (proposalId: string, vote: string) => {
  setVotingId(proposalId);
  setVoteAction(vote);
  try {
    if (backendLive) {
      await api.voteProposal(proposalId, vote);
      refreshProposals();
    }
  } catch {
    // silently ignore for demo
  }
  setTimeout(() => {
    setVotingId(null);
    setVoteAction(null);
  }, 800);
};
```

Optimistic UI: button zamienia się na "Recording {vote}…" z `Loader2`. Po `setTimeout(800ms)`
clear loading state. Backend write + refresh dzieje się w tle. Errors są **silently ignored**
w MVP — TODO: dodać toast z error message.

### 3.3. Create Proposal

```ts
const handleCreateProposal = async () => {
  if (!newTitle.trim()) return;
  setSubmitting(true);
  try {
    if (backendLive) {
      await api.createProposal(newTitle, newDesc, newScope);
      refreshProposals();
    }
    setShowNewProposal(false);
    setNewTitle("");
    setNewDesc("");
    setNewScope("pipeline");
  } catch {
    // silently ignore
  }
  setSubmitting(false);
};
```

Validation: tylko `newTitle.trim() !== ""` jest wymagane. Description i scope mają
defaults. Po sukcesie: form się zamyka, fields są reset, lista się odświeża.

### 3.4. Tab change

```ts
<Tabs value={activeTab} onValueChange={setActiveTab}>
```

Standard Radix Tabs. Brak persistencji w URL ani localStorage. Refresh strony
wraca do default `proposals`.

### 3.5. Policy filter

```ts
const filteredPolicies = useMemo(() => {
  if (policyFilter === "all") return policies;
  return policies.filter((p) => (p.category ?? "deployment") === policyFilter);
}, [policies, policyFilter]);
```

Single-select filter. Klik na chip aktywuje filter. Memoized derived state.

### 3.6. Policy expand/collapse

```ts
onClick={() => setExpandedPolicy(isExpanded ? null : policy.policy_id)}
```

Single-select expand. Klik innej policy zamyka poprzednią.

### 3.7. Generate Report (compliance tab)

Klik "Generate Report" wywołuje `handleRefreshAll` (refetch compliance data). UWAGA:
nazwa "Generate Report" jest myląca — w MVP nie generuje raportu PDF/CSV, tylko
re-fetchuje dane. TODO: dodać prawdziwy export endpoint.

---

## 4. Zarządzanie stanem

### 4.1. Hooki React

```ts
const { data: health, refresh: refreshHealth } = useHealth();
const { data: proposalsData, refresh: refreshProposals } = useProposals();
const { data: policiesData, refresh: refreshPolicies } = usePolicies();
const { data: gatesData } = useDecisionGates();   // unused w MVP

const [mounted, setMounted] = useState(false);
const [activeTab, setActiveTab] = useState("proposals");
const [votingId, setVotingId] = useState<string | null>(null);
const [voteAction, setVoteAction] = useState<string | null>(null);
const [complianceData, setComplianceData] = useState<ComplianceScope[]>([]);
const [complianceRules, setComplianceRules] = useState<ComplianceRule[]>([]);
const [showNewProposal, setShowNewProposal] = useState(false);
const [newTitle, setNewTitle] = useState("");
const [newDesc, setNewDesc] = useState("");
const [newScope, setNewScope] = useState("pipeline");
const [submitting, setSubmitting] = useState(false);
const [expandedPolicy, setExpandedPolicy] = useState<string | null>(null);
const [policyFilter, setPolicyFilter] = useState<string>("all");
const [refreshing, setRefreshing] = useState(false);
```

### 4.2. Memoized derived state

```ts
const proposals: Proposal[] = useMemo(() => {
  if (!backendLive) return [];
  return (proposalsData.proposals ?? []).map((p: any) => {
    let status: ProposalStatus = "open";
    const raw = (p.status ?? "").toLowerCase();
    if (raw === "implemented" || raw === "approved") status = "implemented";
    else if (raw === "rejected") status = "rejected";
    else if (raw === "closed") status = "closed";
    else if (raw === "draft") status = "open";
    else status = "open";
    return { ...p, status };
  });
}, [backendLive, proposalsData]);
```

Normalizacja statusów (backend może zwrócić "approved", "draft", etc., frontend
mapuje na 4 kanoniczne).

### 4.3. Compliance fetch

```ts
const fetchCompliance = useCallback(async () => {
  if (!backendLive) return;
  const scopes = ["pipeline", "council", "memory", "security"];
  const results = await Promise.allSettled(
    scopes.map(async (s) => {
      try {
        const res = await api.checkCompliance(s);
        const c = res.compliance ?? res;
        return { scope: s, score: c.score ?? c.percentage ?? 0, details: c.details ?? "" };
      } catch {
        return { scope: s, score: 0, details: "Unable to fetch" };
      }
    })
  );
  setComplianceData(results.map((r) => (r.status === "fulfilled" ? r.value : { scope: "", score: 0, details: "" })));
}, [backendLive]);
```

`Promise.allSettled` zapewnia, że failure jednego scope (np. memory) nie blokuje
fetcha innych. Każdy scope ma własny try/catch.

### 4.4. Vote history derivation

`voteHistory` jest **synthesized** z proposals. Backend nie expose'uje per-vote
records w MVP. Frontend tworzy fake records:

```ts
const voteHistory: VoteRecord[] = useMemo(() => {
  if (!backendLive) return [];
  const records: VoteRecord[] = [];
  let idx = 0;
  for (const p of proposals) {
    const total = (p.votes_for ?? 0) + (p.votes_against ?? 0) + (p.votes_abstain ?? 0);
    if (total === 0) continue;
    const voters = ["agent_a1", "agent_a2", "agent_a3", "board"];
    for (let i = 0; i < Math.min(total, 4); i++) {
      const vote = i < (p.votes_for ?? 0) ? "for" : ...;
      records.push({ id: `v-gen-${idx++}`, voter: voters[i], proposal_id: p.proposal_id, ... });
    }
  }
  return records;
}, [backendLive, proposals]);
```

UWAGA: to **placeholder** dla prawdziwych danych. Operatorzy widzą fake voter IDs.
TODO: dodać `/api/v1/governance/proposals/{id}/votes` endpoint z prawdziwymi records.

### 4.5. Hydration guard

`mounted` flag używany dla `formatDate` i `timeAgo` (timezone-dependent).

---

## 5. Integracja API

### 5.1. Endpointy

| Metoda | Endpoint | Hook / call | Cel |
|--------|----------|-------------|-----|
| GET | `/api/health` | `useHealth()` | Health probe |
| GET | `/api/v1/governance/proposals` | `useProposals()` | Lista propozycji |
| POST | `/api/v1/governance/proposals` | `api.createProposal(title, desc, scope)` | Nowa propozycja |
| POST | `/api/v1/governance/proposals/{id}/vote` | `api.voteProposal(id, vote)` | Głos |
| GET | `/api/v1/governance/policies` | `usePolicies()` | Lista policies |
| GET | `/api/v1/governance/gates` | `useDecisionGates()` | Decision gates (unused MVP) |
| GET | `/api/v1/governance/compliance/{scope}` | `api.checkCompliance(scope)` | Compliance score per scope |
| GET | `/api/v1/governance/compliance/rules` | `api.listComplianceRules()` | Lista compliance rules |

### 5.2. Schema `Proposal`

```ts
interface Proposal {
  proposal_id: string;          // np. "prop_2026_xyz"
  title: string;
  description?: string;
  proposer?: string;            // operator_id lub agent_id
  status: 'open' | 'closed' | 'implemented' | 'rejected';
  scope?: 'pipeline' | 'council' | 'memory' | 'security';
  votes_for?: number;
  votes_against?: number;
  votes_abstain?: number;
  created_at?: string;          // ISO 8601
}
```

### 5.3. Schema `Policy`

```ts
interface Policy {
  policy_id: string;
  name: string;
  scope: string;
  category?: 'security' | 'deployment' | 'budget' | 'access';
  enforcement_level: 'hard' | 'soft';
  description?: string;
  active?: boolean;
  status?: 'active' | 'draft' | 'archived';
}
```

### 5.4. Schema `ComplianceRule`

```ts
interface ComplianceRule {
  rule_id: string;
  name: string;
  scope: string;
  status: 'pass' | 'fail' | 'warning';
  description?: string;
  last_checked?: string;
}
```

### 5.5. Request — Create proposal

```http
POST /api/v1/governance/proposals HTTP/1.1
Content-Type: application/json

{
  "title": "Increase council size to 7",
  "description": "Current 5-member council leaves potential for tie. Recommend 7 to ensure odd-numbered majority.",
  "scope": "council"
}
```

```http
HTTP/1.1 201 Created
{
  "proposal_id": "prop_council_20260426_8a2c",
  "title": "Increase council size to 7",
  "status": "open",
  "scope": "council",
  "proposer": "op_demo_2026",
  "votes_for": 0,
  "votes_against": 0,
  "votes_abstain": 0,
  "created_at": "2026-04-26T11:42:18Z"
}
```

### 5.6. Request — Vote

```http
POST /api/v1/governance/proposals/prop_council_20260426_8a2c/vote
Content-Type: application/json

{
  "vote": "for",
  "voter_id": "op_demo_2026"
}
```

```http
HTTP/1.1 200 OK
{
  "proposal_id": "prop_council_20260426_8a2c",
  "vote_recorded": "for",
  "votes_for": 3,
  "votes_against": 1,
  "votes_abstain": 0,
  "current_status": "open",
  "quorum_reached": false,
  "weighted_score": 0.62
}
```

UWAGA: `weighted_score` zwracany jest przez backend (Council canonical: 9 ról, 5 rang,
weighted vote), ale **nie** wyświetlany w UI w MVP. Frontend pokazuje tylko surowe
liczniki for/against/abstain.

### 5.7. Request — Check compliance

```http
GET /api/v1/governance/compliance/security HTTP/1.1

HTTP/1.1 200 OK
{
  "compliance": {
    "scope": "security",
    "score": 92,
    "details": "2 rules failed: missing 2FA enforcement, weak password policy",
    "rules_total": 25,
    "rules_passed": 23,
    "rules_failed": 2,
    "rules_warning": 0
  }
}
```

### 5.8. Error handling

| Sytuacja | UI |
|----------|-----|
| `health.status !== "ok"` | Strona pokazuje OFFLINE banner + Card "Backend not reachable" + komenda do uruchomienia uvicorn |
| 401 | Redirect do `/auth` (axios interceptor) |
| 403 (vote forbidden — np. operator nie jest council member) | Silent ignore w MVP. TODO: toast z error |
| 409 (vote already cast) | Silent ignore. TODO: toast "You already voted on this proposal" |
| 422 (invalid scope) | Silent ignore. TODO: form-level validation |
| Compliance fetch error per scope | Score=0, details="Unable to fetch", inne scopes nadal renderują się |

---

## 6. Persistencja

### 6.1. Backend tables

```sql
-- Propozycje
CREATE TABLE governance.proposals (
  proposal_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  proposer TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','closed','implemented','rejected')),
  scope TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMPTZ,
  implemented_at TIMESTAMPTZ
);

-- Głosy (per voter, per proposal)
CREATE TABLE governance.votes (
  vote_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id TEXT NOT NULL REFERENCES governance.proposals,
  voter_id TEXT NOT NULL,
  vote TEXT NOT NULL CHECK (vote IN ('for','against','abstain')),
  weight NUMERIC(4,2) NOT NULL DEFAULT 1.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (proposal_id, voter_id)
);

-- Policies
CREATE TABLE governance.policies (
  policy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scope TEXT NOT NULL,
  category TEXT,
  enforcement_level TEXT NOT NULL CHECK (enforcement_level IN ('hard','soft')),
  description TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  status TEXT NOT NULL DEFAULT 'active'
);

-- Compliance rules (cached, refresh co 5 min od backend)
CREATE TABLE governance.compliance_rules (
  rule_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scope TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pass','fail','warning')),
  description TEXT,
  last_checked TIMESTAMPTZ
);
```

### 6.2. Frontend cache

| Klucz | Storage | TTL |
|-------|---------|-----|
| `react-query: proposals` | in-memory | 30 s staleTime |
| `react-query: policies` | in-memory | 60 s staleTime |
| `react-query: gates` | in-memory | 60 s |
| `complianceData` | useState (component-local) | unmount = reset |
| `complianceRules` | useState (component-local) | unmount = reset |

Brak localStorage — wszystkie dane są fresh-fetched.

### 6.3. Council weighted vote (backend logic)

Backend implementuje:

| Rank | Weight |
|------|--------|
| Senior Architect | 2.5 |
| Lead Council | 2.0 |
| Council Member | 1.5 |
| Junior Council | 1.0 |
| Observer | 0.5 |

`weighted_score = sum(vote_weight * vote_value) / sum(vote_weight)` gdzie
`vote_value = +1 (for) | -1 (against) | 0 (abstain)`. Quorum = `>=60%` rang Council
Member i wyższych. Frontend nie renderuje tych szczegółów w MVP.

---

## 7. Tryby i warianty

### 7.1. Backend status

| `health.status` | Banner | Tabs render |
|-----------------|--------|--------------|
| `"ok"` | LIVE (zielony) | Wszystkie 4 tabs aktywne |
| `"down"` | OFFLINE (czerwony) | Brak — Card "Backend not reachable" |

### 7.2. Proposal status

| Status | Badge color | Border (open) | Icon |
|--------|-------------|--------------|------|
| `open` | `bg-accent-blue-dim text-sylion-blue` | `border-sylion-blue/30` | `Activity` |
| `closed` | `bg-accent-amber-dim text-sylion-amber` | (default) | `Clock` |
| `implemented` | `bg-sylion-green/15 text-sylion-green` | (default) | `CheckCircle2` |
| `rejected` | `bg-sylion-red/15 text-sylion-red` | (default) | `XCircle` |

Vote buttons widoczne **tylko** dla `status === 'open'`.

### 7.3. Scope colors

| Scope | Border | Background |
|-------|--------|------------|
| `pipeline` | `border-sylion-blue/30` | `bg-accent-blue-dim` |
| `council` | `border-cyan-500/30` | `bg-cyan-500/15` |
| `memory` | `border-violet-500/30` | `bg-violet-500/15` |
| `security` | `border-sylion-amber/30` | `bg-accent-amber-dim` |

### 7.4. Policy enforcement

| Level | Border | Icon |
|-------|--------|------|
| `hard` | `border-sylion-red/30 text-sylion-red` | `ShieldAlert` |
| `soft` | `border-sylion-amber/30 text-sylion-amber` | `AlertTriangle` |

Hard policies blokują action backendowo (`HG-Block`). Soft policies generują warning ale nie blokują.

### 7.5. Compliance score color

| Range | Bar color | Text color |
|-------|-----------|-----------|
| `>= 80` | `bg-sylion-green` | `text-sylion-green` |
| `>= 50` | `bg-sylion-amber` | `text-sylion-amber` |
| `< 50` | `bg-sylion-red` | `text-sylion-red` |

### 7.6. Voting state (per proposal)

| `votingId` | Effect |
|-----------|--------|
| `null` | Wszystkie open proposals pokazują 3 buttons |
| `proposal_id_xyz` | Ten proposal pokazuje "Recording {voteAction}…" + Loader2 |

Po `setTimeout(800ms)` clear → return to buttons (z odświeżonymi licznikami).

### 7.7. CircularScore variants

| Use case | Size | Stroke |
|----------|------|--------|
| Stat card | 48 px | 4 px |
| Compliance gauge | 100 px | 8 px |

---

## 8. Dostępność

### 8.1. Klawiatura

| Klawisz | Akcja | Status |
|---------|-------|--------|
| `Tab` / `Shift+Tab` | Nawigacja | OK (natywne) |
| `Enter/Space` na proposal card | brak | (cards nie są focusable) |
| `Enter/Space` na "For/Against/Abstain" | Trigger vote | OK |
| `Tab` na Tabs | Strzałki ←→ wybierają tabę | OK (Radix Tabs) |
| `Enter` na policy header | Toggle expand | OK (`<button>`) |
| `Esc` | Brak | TODO |

### 8.2. ARIA

- `<Tabs>` z Radix ma natywne `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`.
- Buttons mają text content — czytelne przez SR.
- `<button>` na policy header — focusable.
- Vote buttons mają text "For", "Against", "Abstain" + ikona dekoracyjna.
- TODO: `aria-live="polite"` dla `voteHistory` timeline (nowe entry powinny być announced).
- TODO: `aria-expanded` i `aria-controls` na policy header.

### 8.3. Kontrast

| Element | Status |
|---------|--------|
| Tab triggers | OK |
| Vote count text (`text-sylion-green/red font-medium`) | OK |
| `text-[10px]` muted-foreground | granica AA — TODO zwiększyć size |
| `text-[8px]` badges | **POD AA** — bardzo mały tekst |
| Vote buttons | OK |

`text-[8px]` używany w policy badges — operator z słabszym wzrokiem może mieć trudność. TODO: zwiększyć do `text-[10px]` minimum.

### 8.4. Focus indicators

Radix Tabs i Button mają default `focus-visible:ring-2`. Inputs w form (`<input>`,
`<textarea>`, `<select>`) mają `focus:border-sylion-blue` (wizualny focus marker).

### 8.5. Reduced motion

`framer-motion` `<AnimatePresence>` i `<motion.div>` honorują `prefers-reduced-motion`.
`animate-spin` na Loader2 i RefreshCw — można pomyśleć o disable przy reduced motion.

### 8.6. Color-only encoding

Status proposal: kolor + tekst ("open"/"implemented"/etc) + ikona. Vote buttons:
kolor + tekst + ikona. Compliance: kolor + procent + (przy fail) tekst "violations".
Spełnia WCAG dla użytkowników z deuteranopia/protanopia.

---

## 9. Przepływy operatora

### 9.1. Operator tworzy nową propozycję

1. Operator wchodzi na `/governance`. Aktywna tab: Proposals.
2. Stats: 3 active, 12 implemented, 87% compliance, 18 pending votes.
3. Klika **"Create Proposal"**.
4. Form rozwija się (animacja height: 0 → auto).
5. Wpisuje:
   - Title: "Increase council size to 7"
   - Description: "Current 5-member council leaves potential for tie. Recommend 7 to ensure odd-numbered majority decisions."
   - Scope: `Council`
6. Klika **Submit**.
7. Frontend wywołuje `api.createProposal(title, desc, scope)`.
8. Backend INSERT `governance.proposals` z status `open`, proposer `op_demo_2026`, `created_at NOW()`.
9. Zwraca `proposal_id=prop_council_20260426_8a2c`.
10. `refreshProposals()` re-fetchuje listę.
11. Form się zamyka (pola reset).
12. Nowa propozycja pojawia się na top listy (z 0 votes).

### 9.2. Operator głosuje na propozycji

1. Operator widzi propozycję `prop_council_20260426_8a2c` w liście.
2. Status: `open`, 0 votes.
3. Czyta description, decyduje że jest za.
4. Klika **For** button.
5. Frontend ustawia `votingId=prop_council_20260426_8a2c`, `voteAction="for"`.
6. Buttons znikają, pojawia się `<Loader2 />` + "Recording for...".
7. Frontend wywołuje `api.voteProposal('prop_council_20260426_8a2c', 'for')`.
8. Backend:
   a. INSERT `governance.votes` z `voter_id=op_demo_2026`, `vote=for`, `weight=2.0` (Lead Council rank).
   b. UPDATE `proposals.votes_for = votes_for + 1`.
   c. Compute weighted_score.
   d. Check quorum (current: 1/5 voters, no quorum).
9. Zwraca `votes_for: 1, votes_against: 0, votes_abstain: 0, weighted_score: 0.4`.
10. `refreshProposals()` re-fetchuje listę.
11. Po `800ms` Loader znika, vote bar pokazuje 100% green (1 for, 0 against).
12. Operator widzi swój vote zarejestrowany.

### 9.3. Quorum reached + auto-implementation

1. 5 operatorów Council głosuje na `prop_council_20260426_8a2c`.
2. Wynik: 4 for, 1 against, 0 abstain. Weighted score: 0.85 (>0.6 quorum).
3. Backend (poza UI) automatycznie zmienia `status=implemented` po decision gate `D3`.
4. Tworzy evidence pack (template `council_signoff`) z artefaktami:
   - `proposal.json`
   - `votes.json` (per-voter records)
   - `weighted_score_calculation.md`
   - `council_signature.sig`
5. Pack jest widoczny w `/evidence` jako `ev_d3_20260426_xxx`, source=council.
6. Operator wracając na `/governance` Proposals tab widzi:
   - Status: `implemented` (zielony)
   - Stats: Active Proposals -1, Policies Enacted +1.

### 9.4. Sprawdzenie compliance scope security

1. Operator klika tab **Compliance**.
2. Strona ładuje 4 scopes: pipeline (95%), council (92%), memory (88%), security (62%).
3. Big gauge: 84% (avgCompliance) — amber.
4. Per-scope cards. Security ma 62% z `text-sylion-red`.
5. Pod nazwą "security": "12 rules" i `XCircle` "3 violations".
6. Operator scrolluje do "Compliance Rules" table.
7. Filtruje wzrokowo czerwone wiersze (`bg-sylion-red/5`).
8. Znajduje:
   - "Two-factor authentication required" — FAIL — "User accounts without 2FA: 4"
   - "Password complexity policy" — WARNING — "Soft policy not yet enforced"
   - "Session timeout < 24h" — FAIL — "Sessions found with timeout > 24h"
9. Decyduje stworzyć propozycję `Enforce 2FA for all operators` w scope=security.
10. Wraca do tab Proposals, klik "Create Proposal".

### 9.5. Filter policies po category

1. Operator klika tab **Policies**.
2. Lista 23 policies, filter chips: All, Security, Deployment, Budget, Access.
3. Klika **Security**.
4. `policyFilter="security"`, `filteredPolicies` zwraca 7 polityk security category.
5. Operator klika `Enforce TLS 1.3 minimum` policy.
6. Card rozwija się.
7. Description: "All inbound HTTPS connections must use TLS 1.3 or higher."
8. Right column: ID `pol_sec_001`, Scope `security`, Enforcement `hard` (czerwony).
9. Operator wie że to hard policy — nie ma override mechanism, każde naruszenie blokowane przez `HG-Block`.

### 9.6. Refresh wszystkich danych

1. Operator widzi że dane mają 5 minut (timestamps `5m ago`).
2. Klika **Refresh** w nagłówku.
3. `refreshing=true`, `<RefreshCw>` zaczyna się obracać (`animate-spin`).
4. Wszystkie 4 hooki re-fetchują (`useHealth`, `useProposals`, `usePolicies`, plus `fetchCompliance`, `fetchComplianceRules`).
5. Po `setTimeout(600ms)` `refreshing=false`.
6. Strona pokazuje fresh data (timestamps `1s ago`).

### 9.7. Backend offline scenario

1. Backend dies podczas pracy operatora.
2. `useHealth` next poll → `health.status='down'`.
3. `backendLive=false`.
4. UI auto-rerender: status badge zmienia się z LIVE na OFFLINE.
5. Stats row + tabs **znikają** całkowicie.
6. Pokazuje się Card "Backend not reachable" + instrukcja `python -m uvicorn sylion.api.app:app --port 8010`.
7. Operator uruchamia backend.
8. Po następnym health poll (15 s), `health.status='ok'`.
9. UI auto-rerender: pełna strona wraca z fresh danymi.

---

## 10. Cross-references

### 10.1. Powiązane surfaces

| Surface | Plik | Relacja |
|---------|------|---------|
| `/evidence` | [`25_evidence_pack_viewer.md`](25_evidence_pack_viewer.md) | Implemented proposals tworzą evidence packs (source=council, template=council_signoff) |
| `/audit` | [`27_audit_viewer.md`](27_audit_viewer.md) | Każdy vote i create generuje `aeis.governance.*` audit event |
| `/advisor` | [`20_advisor_feed.md`](20_advisor_feed.md) | Council recommendations z D3+ pojawiają się w advisor feed |
| `/projects/[id]/lifecycle` | [`22_lifecycle_dashboard.md`](22_lifecycle_dashboard.md) | Lifecycle hook H08 (Decision Gate) konsultuje council przy D3+ proposals |

### 10.2. Powiązane backend modules

| Moduł | Folder | Rola |
|-------|--------|------|
| Council Hybrid | `src/sylion-pipeline/sylion/council/hybrid.py` | 9 ról, 5 rang, weighted vote, critic signature gate |
| Governance API | `src/sylion-pipeline/sylion/api/council_routes.py` | `/api/v1/governance/proposals*` |
| Compliance Engine | `src/sylion-pipeline/sylion/governance/compliance.py` | Per-scope compliance scoring |
| Policy Engine | `src/sylion-pipeline/sylion/governance/policies.py` | Enforce policies (hard/soft) |
| Decision Gates | `src/sylion-pipeline/sylion/governance/gates.py` | D3+ ladder, escalation logic |

### 10.3. Powiązane hooki

| Hook | Plik |
|------|------|
| `useHealth` | `src/sylion-frontend/src/lib/api/hooks.ts` |
| `useProposals` | `src/sylion-frontend/src/lib/api/hooks.ts` |
| `usePolicies` | `src/sylion-frontend/src/lib/api/hooks.ts` |
| `useDecisionGates` | `src/sylion-frontend/src/lib/api/hooks.ts` |

### 10.4. Powiązane API client methods

| Method | Plik |
|--------|------|
| `api.checkCompliance(scope)` | `src/sylion-frontend/src/lib/api/client.ts` |
| `api.listComplianceRules()` | `src/sylion-frontend/src/lib/api/client.ts` |
| `api.voteProposal(id, vote)` | `src/sylion-frontend/src/lib/api/client.ts` |
| `api.createProposal(title, desc, scope)` | `src/sylion-frontend/src/lib/api/client.ts` |

### 10.5. Powiązane komponenty UI

| Komponent | Plik |
|-----------|------|
| `Tabs/TabsList/TabsTrigger/TabsContent` | `src/sylion-frontend/src/components/ui/tabs.tsx` |
| `Card` | `src/sylion-frontend/src/components/ui/card.tsx` |
| `Badge` | `src/sylion-frontend/src/components/ui/badge.tsx` |
| `Button` | `src/sylion-frontend/src/components/ui/button.tsx` |
| `CircularScore` (inline) | `src/sylion-frontend/src/app/(app)/governance/page.tsx` (linie 196–216) |
| `FadeSection` (inline wrapper) | tamże (linie 105–116) |

### 10.6. Powiązane dokumenty governance

| Dokument | Wpływ |
|----------|-------|
| Council canonical | 9 ról, 5 rang, ważone głosowanie, critic signature gate, cost+security sentinels |
| AEIS Canonical Full Model 2026-04-24 | 12 warstw, 13 etapów audytu, prefix `CLAUDE_AEIS_*` |
| Decision Gates & Governance | D0-D5 ladder, evidence requirements, compliance enforcement |

### 10.7. Powiązane testy

| Test | Plik |
|------|------|
| GovernancePage smoke | `src/sylion-frontend/src/app/(app)/governance/__tests__/page.test.tsx` (TBD) |
| Council weighted vote | `src/sylion-pipeline/tests/unit/test_council_hybrid.py` |
| Compliance engine | `src/sylion-pipeline/tests/unit/test_compliance.py` |

### 10.8. Open questions / TODO

- Pokazywać `weighted_score` per proposal (nie tylko surowe liczniki).
- Pokazywać quorum status (`X/5 votes`, kolorowy badge "QUORUM REACHED").
- Endpoint `/api/v1/governance/proposals/{id}/votes` z prawdziwymi per-voter records (zastąpić `voteHistory` synthesis).
- Generate Report button — prawdziwy export PDF/CSV.
- Toast notifications zamiast silent ignore na vote/create errors.
- URL query param dla active tab (`?tab=compliance`).
- Filtry/sort dla proposal list (po status, scope, date).
- Pagination dla policies > 100 entries.
- Per-voter view: "My votes" tab z historią głosów operatora.
- Real-time updates przez WebSocket (zamiast polling).
- A11y: `aria-expanded`, `aria-live`, większy text-[8px] badges.
