# W19 Charter — Policy / Security Plane

> Status: **DRAFT** (2026-04-26)
> D-level: **D5**
> Estymacja solo: **10-14 tygodni** / z zespołem 10 os.: **4-6 tygodni**
> (parallel z W17). Depends on: **W15 G2 (HARD)** dla policy/audit ontology
> types, **W17 G2 (HARD)** dla node-level enforcement; **soft**: W18 G2
> (terminal events redaction). PDF §9.1 jako ultimate driver decyzji.

## 1. Cel

W19 to **plane bezpieczeństwa, autoryzacji i policy** dla SYLION AEIS — re-
introdukcja warstwy, która została **świadomie wycięta** w fazie solo-dev
(PDF §9.1: "system jest tylko dla mnie, Policy plane wycięty"). Z momentu
gdy w pętli pojawia się **10-osobowy zespół**, ta decyzja przestaje
obowiązywać. PDF §9.1 stawia pięć pytań krytycznych, których nie da się
zignorować bez ryzyka kompromitacji danych:

> - Czy zespół ma dostęp do production data?
> - Czy każdy widzi wszystkie API keys do prod LLM providers?
> - Czy zespół ma dostęp do grant applications, financial data, klient
>   information?
> - Co jeśli ktoś z zespołu odejdzie nieprzyjaźnie?
> - Czy keys plaintext (zapamiętane jako preferencja) jest dalej OK?

Cel W19: dostarczyć **operator-grade policy backbone**, który przekształca
te pięć pytań w mierzalne, audytowalne, automatyczne mechanizmy. Każde
żądanie do AEIS (REST, gRPC, OSDK call, terminal slash command, agent
action) **przechodzi przez authentication → authorization → policy
evaluation → audit log** — bez wyjątków, bez "dev bypass" w produkcji.

W19 to **nie nowa technologia od zera** — re-używa istniejący kawałek
`sylion/api/rbac_enforcement.py` (rozszerza, nie zastępuje) i istniejący
KeyVault (zamienia plaintext + wprowadza per-key audit). Kluczowy zasięg:

1. **Authentication backbone** (JWT + OAuth 2.1 + IdP federation).
2. **Authorization extended** (RBAC z 5 nowymi rolami + per-project ACL).
3. **Secrets management** (audited KeyVault + optional Vault adapter).
4. **Data access policies** (field-level redaction + privacy levels per
   idea/project).
5. **Audit & compliance** (hash-chained log z retention + GDPR erasure).
6. **Departure handling** (one-click revocation + break-glass admin).
7. **Privacy-aware LLM routing** (PDF §8.4 tags `must run locally` /
   `OK external` / `OK any provider`).

PDF §2.5 zostawiło "minimal JSON rules" jako obecny silnik W17. W19 nie
zmusza do migracji do OPA/rego — pluggable engine pozwala JSON dla
prostych przypadków, OPA jako future opcja. Decision punkt §13 Q6.

W19 oznaczony **D5 (krytyczny)** ponieważ każdy bug w policy plane =
potencjalny **data breach** dla 10-os zespołu, a w połączeniu z grant
applications + financial data + klient information **incident jest
nieodwracalny** (dane wyciekły zostają wyciekłe). PDF §9.1 explicite
deklaruje że "fundamentalne decyzje (Policy plane, struktura, role)
wpływają na 6-8 miesięcy pracy 10 osób" — błąd w W19 propaguje na
wszystkie warstwy v2 i v3.

## 2. Scope IN

- **Authentication backbone** — pełny lifecycle tokenów + IdP federation.
  - **JWT bearer tokens** via OAuth 2.1: PKCE flow dla SPA (sylion-
    frontend, terminal W18), `client_credentials` dla machine-to-machine
    (W17 central plane ↔ nodes).
  - **Token lifecycle**: access token 1h, refresh token 7-day, automatic
    rotation. Revocation list (RL) cache w Redis z 60s TTL refresh —
    revoked token rejected w < 60s globally.
  - **Identity providers**: local (PostgreSQL `User` ontology type w W15),
    Google Workspace OIDC, GitHub OAuth, Microsoft Entra (Azure AD).
    IdP-agnostic mapping `{idp_id, external_id} → User` — operator może
    podlinkować Google + GitHub do jednego konta.
  - **Session management**: każdy autoryzowany request ma `request.state.
    user` z `id`, `role`, `tenant`, `session_id`, `idp_origin`. Propagacja
    do downstream calls (W11 LLM calls, W17 deploy commands, W18 audit).
  - **MFA**: opt-in TOTP (Google Authenticator compatible) dla `owner` +
    `tech_lead` ról. WebAuthn/passkeys post-G4.

- **Authorization (RBAC) — extended, NOT replaced**.
  - Ekstensja istniejącego `sylion/api/rbac_enforcement.py` — nie
    re-write. POLICY map deklaratywny: `{endpoint_pattern, http_method,
    required_role, resource_scope}`.
  - **Nowe role** (PDF §9.1 zespół 10 os.):
    - `owner` (1-2 osoby, full access, break-glass admin).
    - `tech_lead` (deploy, rotate keys, manage roles).
    - `developer` (read/write code-related ontology, brak rotate keys).
    - `auditor` (read-only do audit log + lineage, brak read do plaintext
      secrets).
    - `read_only` (dashboards, no mutations).
    - `external_collaborator` (per-project scoped, time-limited token,
      bezpieczne tokeny).
  - **Per-project access control**: `ProjectMembership` ontology type w
    W15 — `{project_id, user_id, role_in_project, expires_at}`. Projekty
    z `sensitivity: financial | grant | klient_data` wymagają explicit
    membership niezależnie od global role.
  - **Resource × action matrix**: developer może czytać projekty ale
    **nie może rotować API keys**, auditor czyta audit log ale **nie
    decryptuje plaintext secrets**, etc. Matrix w `policy/rbac/policy_
    matrix.yaml`, single-source-of-truth.
  - **POLICY map coverage**: 100% `/api/v1/*` + `/api/v2/*` endpoints
    mapped do role × action. CI check: nowy endpoint bez wpisu w POLICY
    map → build fail.

- **Secrets management** — audited KeyVault + optional Vault adapter.
  - **Migracja z plaintext .env do KeyVault**: 90-day deadline plus
    `scripts/secrets_migrate_dotenv.py` jako bulk migration tool.
    `grep_diff` weryfikator szuka pozostałych plaintext keys w git history
    + working copies + laptop home dirs.
  - **Per-key access control**: `KeyVault.read_secret(key, actor)` checks
    `KeyACL` (kto może decryptować). Zasada **least privilege** —
    `developer` nie ma access do `prod_anthropic_api_key`, tylko
    `tech_lead` + `owner`.
  - **Audit log każdego decryption**: `SecretAccessEvent` ontology type w
    W15 — `{key_id, actor, timestamp, target_provider, ip, request_id,
    session_id}`. Hash-chained (R8 below). Retention: 7 lat (compliance).
  - **Optional HashiCorp Vault adapter**: dla teams które już mają Vault
    infrastructure. `SecretsBackend` interface, default impl = `audited_
    vault.py` (file-based AES-GCM), opt-in `vault_adapter.py`
    (HashiCorp). Per-tenant decision.
  - **File-based crypto**: AES-GCM 256-bit z key derivation z master
    passphrase (Argon2id). Master key offline, sealed envelope (R3 below).

- **Data access policies** — field-level redaction + privacy levels.
  - **Field-level redaction**: deklaratywny w manifest W15 — per ontology
    type, lista pól z `redact_for_roles: [developer, read_only, external_
    collaborator]`. API response renderer (FastAPI middleware) zamienia
    `klient_email: "robert@klient.pl"` na `klient_email: "[redacted by
    policy: pii_email]"`. Czytelne dla operatora — wie co jest redagowane
    i przez którą regułę (R4 mitigation).
  - **Project-level visibility**: `Project.visibility` enum — `private`
    (only owner + explicit members), `team` (wszyscy w org), `public`
    (cross-org, post-G4 future). REST list endpoints filter na backend
    przed serializacją.
  - **Idea Vault privacy levels**: `Idea.privacy` — `public` (każdy w org
    widzi), `team` (tylko team_id członkowie), `private` (tylko autor),
    `sealed` (zaszyfrowane, decrypt wymaga HG D4). Re-use field-level
    redaction engine.

- **Audit & compliance** — centralized hash-chained log.
  - **Centralized AuditEvent** dla wszystkich mutations + access events.
    Re-use wzorca z W15 lineage + W18 TerminalEvent — hash-chained per
    event type, append-only, weryfikowalny.
  - **Event taxonomy**: `auth.login`, `auth.logout`, `auth.token_refresh`,
    `rbac.access_granted`, `rbac.access_denied`, `secret.read`,
    `secret.rotate`, `data.read_pii`, `mutation.{create|update|delete}`,
    `policy.rule_changed`, `departure.revoked`. ~25 event types G2.
  - **Hash chain integrity**: `make w19-verify-audit` walks chain dla 1M
    entries w < 30s (P-W19-04). Break w chain → automatic Guardian alert
    + email/Slack ping do owner.
  - **GDPR right-to-erasure**: kasowanie danych użytkownika (cascading
    delete poprzez W15 FK) z **immutable audit trail** — sam fakt erasure
    audytowany jako `gdpr.erased{user_id, requested_by, scope, completed_
    at, hash_of_erased_data}`. Tombstone pattern (Q3 below) preserves
    chain integrity.
  - **Retention policies per object type**: nowe pole w W15 manifest
    `retention_days: 365 | 2555 | infinite`. Cold storage do parquet
    archive po expiry hot retention; hash chain crosses tiers
    (consistency z W18 R4).
  - **SOC 2 / ISO 27001 readiness**: audit replay + segregation of duties
    (auditor role nie może modyfikować audit log) + access reviews
    quarterly.

- **Departure handling** — one-click revocation + break-glass.
  - **Departure runbook**: `sylion deploy-departure --user {id}` wykonuje:
    (1) deactivate user account, (2) invalidate wszystkie active sessions,
    (3) rotate API keys które user mógł znać (z `KeyACL` mapping), (4)
    revoke OAuth grants (Google/GitHub disconnect), (5) audit log
    `departure.executed`. SLA: < 60 sekund (DX-W19-04).
  - **Break-glass admin**: zawsze **>= 2 owners** (N+1 pattern). Backup
    owner credentials w sealed offline envelope (paper + Yubikey),
    drill co 6 miesięcy weryfikuje że envelope jest dostępne i działa.
  - **Access review report**: `sylion audit access-report --format=pdf`
    generuje "kto ma dostęp do czego" — listing wszystkich users × roles
    × projects × secrets. Quarterly compliance check.
  - **Unfriendly departure scenario**: jeśli odchodzący user **był
    owner** — tylko inny owner może wywołać runbook. Procedural lock —
    żaden pojedynczy actor nie może odebrać dostępu sam sobie.

- **Privacy levels per task** — PDF §8.4 Compute Provider Federation.
  - **Tag każdego LLM call**: w manifeście task / agent / project,
    `privacy_level: must_run_locally | ok_external | ok_any_provider`.
    Default `ok_external` (bezpieczne, nie cloud-hostile).
  - **Routing engine respects tags**: W11 Adapter Bus + W17 Federation
    Routing czyta tag, filtruje kandydatów compute providers. `must_
    run_locally` task NIGDY nie wysyłany do cloud provider (Anthropic
    API, OpenAI). Brak fallback fail-open — task waits albo fails
    explicit (zamiast cicho leak'ować).
  - **Audit każdego routing decision**: `RoutingEvent` z `{task_id,
    privacy_level, candidates, chosen_provider, rejected_due_to_privacy
    [provider_ids]}`. Pozwala później dowieść że task X faktycznie poszedł
    lokalnie.
  - **Policy override**: tylko `owner` może w runtime promować task do
    wyższej skali (`must_run_locally → ok_external`) — wymaga HG D4
    + audit log.

## 3. Scope OUT

- **Zero-trust networking** (mTLS między nodes, SPIFFE/SPIRE) — to
  terytorium W17 (deployment plane). W19 dotyczy aplikacyjnej autoryzacji,
  nie network-level identity.
- **DLP (Data Loss Prevention)** na poziomie packet inspection — wymaga
  network proxy, eDPI, wykraczające poza application boundaries. Out of
  scope W19; rozważyć w v3.x jeśli compliance regulacja wymusi.
- **HSM (Hardware Security Module) backup** dla MVP — tylko file-based
  AES-GCM. Yubikey jako sealed envelope element jest acceptable (`break-
  glass` only). CloudHSM / Thales / Luna out of scope. Decision Q2.
- **Federated identity (cross-organization SSO)** — single-org tylko.
  Multi-org SAML federation post-v3.x jeśli AEIS będzie sprzedawany jako
  multi-tenant SaaS (świadomie odrzucone PDF §2.3).
- **Pełen Palantir-style markings** (per-row classification labels jak
  TS/SCI) — overkill dla 10-os zespołu (PDF §9.1 stage). W19 dostarcza
  per-project + per-field redaction; markings re-eval w v3.5.
- **Threat detection / SIEM integration** (Splunk, Elastic SIEM) — audit
  log jest exporter-friendly (JSON Lines + hash chain), ale sam SIEM
  pipeline jest customer concern, nie W19 deliverable.
- **Penetration testing as continuous service** — external pen-test
  jednorazowy w G2 + G4 (kontraktowo); ciągłe red-teaming post-v3.x.

## 4. Exit gates

### G1 — Auth Backbone + Extended RBAC (week 4)
- **Deliverables**:
  - `sylion/aeis_v2/policy/auth/jwt.py` — JWT issuance + validation +
    revocation list cache.
  - `sylion/aeis_v2/policy/auth/oauth.py` — OAuth 2.1 PKCE + client_
    credentials flows.
  - `sylion/aeis_v2/policy/auth/providers/{local,google,github,microsoft}.
    py` — IdP integrations.
  - `sylion/aeis_v2/policy/rbac/extended_policy.py` — extends istniejący
    `sylion/api/rbac_enforcement.py` z 5 nowymi rolami.
  - `policy/rbac/policy_matrix.yaml` — single source of truth dla role ×
    action.
  - `sylion/aeis_v2/policy/secrets/audited_vault.py` — wraps istniejący
    KeyVault z `SecretAccessEvent` log.
  - W15 ontology types: `User`, `Session`, `Role`, `ProjectMembership`,
    `KeyACL`, `SecretAccessEvent`.
  - 60+ pytest, 8 integration tests.
- **Success criteria**:
  - JWT auth working dla `/api/v1/*` + `/api/v2/*` (z optional dev bypass
    flag dla migration period).
  - 5 nowych ról zdefiniowanych, RBAC POLICY map pokrywa min. 80%
    endpoints.
  - KeyVault audit log działa — every `read_secret` produces `SecretAccess
    Event`, weryfikowalny.
  - SC F-W19-01..F-W19-03 zielone.
- **HG required**: YES (D5 milestone, Council vote).

### G2 — Field Redaction + Departure Runbook + Pen-Test #1 (week 8)
- **Deliverables**:
  - `sylion/aeis_v2/policy/data/redaction.py` — declarative field-level
    redaction engine (FastAPI middleware + OSDK serializer hook).
  - Field redaction wdrożona w 3 najczęściej używanych endpointach
    (`/api/v1/customers`, `/api/v1/funding`, `/api/v1/ideas`).
  - `sylion/aeis_v2/policy/departure/runbook.py` — automated revocation
    flow z step-by-step audit.
  - **Departure drill done**: simulujemy odejście developera + auditora,
    zmierzymy MTTR, dokumentujemy.
  - W15 manifest extension: `retention_days` field per type.
  - **External pen-test #1** (early, R5 mitigation) — independent firm,
    findings → backlog do G4.
- **Success criteria**:
  - SC F-W19-04..F-W19-06 zielone.
  - Departure procedure < 60s (DX-W19-04).
  - Pen-test report identifies < 5 medium-severity, 0 critical/high.
- **HG required**: YES (production data redaction goes live).

### G3 — Privacy Routing + Audit Hash Chain End-to-End (week 11)
- **Deliverables**:
  - `sylion/aeis_v2/policy/privacy/routing_tags.py` — privacy-level
    propagation do W11 + W17 routing.
  - `sylion/aeis_v2/policy/audit/chain.py` — full hash chain z verify
    tool, integration z W15 lineage + W18 terminal events.
  - GDPR right-to-erasure flow: tested end-to-end na fake user data,
    chain integrity preserved post-erasure.
  - 6+ E2E scenariuszy (10-user team z all roles, full workflow).
- **Success criteria**:
  - SC F-W19-07..F-W19-08 zielone.
  - Audit log replay 1M entries < 30s (P-W19-04).
  - Zero `must_run_locally` task wysłany do cloud provider (E2E test).
- **HG required**: NO (incremental, no new D5 surface).

### G4 — Production-Ready + External Pen-Test #2 (week 14)
- **Deliverables**:
  - Wszystkie 20 SC zielone.
  - **External pen-test #2** (final) — passed (< 3 medium, 0 critical/
    high).
  - 4-week soak: zespół 10 os. używa W19 codziennie, zero incident.
  - Documentation: policy guide, departure runbook, secrets migration
    cookbook, GDPR procedure.
  - Removal of dev bypass — strict by default.
  - 0 plaintext secrets w git history (post-cleanup verifier zielony).
- **Success criteria**:
  - SC: F (8) + P (4) + R (4) + DX (4) — wszystkie zielone over 4 weeks.
  - Pen-test #2 final report — production sign-off.
- **HG required**: YES (production promotion D5).

## 5. Success criteria

### 5.1 Functional (8)
1. **F-W19-01**: Każdy POST/PUT/DELETE `/api/v1/*` + `/api/v2/*`
   propaguje `actor` (z JWT) do audit log; brak audit entry → request
   fails closed.
2. **F-W19-02**: 5 nowych ról (`owner`, `tech_lead`, `developer`,
   `auditor`, `read_only`, `external_collaborator`) działa, RBAC POLICY
   map pokrywa **100% endpoints** (CI guard).
3. **F-W19-03**: API key decryption emit immutable `SecretAccessEvent`,
   weryfikowalny przez `make w19-verify-secret-audit`.
4. **F-W19-04**: Field-level redaction działa deklaratywnie z W15
   manifest — bez kodu Python, tylko YAML rules. `klient_email` redacted
   dla `developer` role w API response.
5. **F-W19-05**: Departure procedure (deactivate user + invalidate
   sessions + rotate 5 keys + audit) wykonuje się < 60 sekund.
6. **F-W19-06**: GDPR right-to-erasure: kasowanie user data cascades
   poprzez W15 FK, audit chain post-erasure pozostaje weryfikowalny.
7. **F-W19-07**: Privacy tag `must_run_locally` na task → routing engine
   wybiera tylko local providers; jeśli żaden niedostępny, task explicit-
   fails (no silent leak do cloud).
8. **F-W19-08**: 0 plaintext secrets w git history po G4 — `git log -p
   | grep -E "sk-|api_key=|password="` pusty (po BFG/git filter-branch
   cleanup).

### 5.2 Performance (4)
1. **P-W19-01**: Auth check (JWT validate + RBAC eval) median latency
   < 5ms p95 (in-process check, no network round-trip per request).
2. **P-W19-02**: Audit log ingest > 1k events/sec sustainable bez drop
   events (async batch insert, optional Kafka backbone post-G4).
3. **P-W19-03**: Field redaction overhead < 2ms p95 dla typowego JSON
   response (10 pól, 2 redacted) — pure-Python serializer, no JIT
   needed.
4. **P-W19-04**: Audit log replay weryfikuje hash chain 1M entries
   < 30s (single-thread; parallelizable post-G4).

### 5.3 Reliability (4)
1. **R-W19-01**: 99.95% availability auth service (mierzone przez
   synthetic probes, target 4.4 hrs downtime/year).
2. **R-W19-02**: Audit log replay weryfikuje hash chain integrity w
   < 30s dla 1M entries; break automatic alerts (Guardian + email +
   Slack).
3. **R-W19-03**: KeyVault decrypt fail z brakiem master key (drill) →
   fallback do break-glass envelope w < 4h, zero data loss.
4. **R-W19-04**: Concurrent role mutations (10 admins, 100 ops each)
   bez lost updates — optimistic locking + audit chain consistency.

### 5.4 Developer Experience (4)
1. **DX-W19-01**: Adding new role = 1 linia w `policy_matrix.yaml` +
   1 test (golden case). Brak Python coding required.
2. **DX-W19-02**: Field redaction declarative w W15 manifest, nie kod
   — operator zmienia `redact_for_roles: [developer]` w YAML i
   redeployuje.
3. **DX-W19-03**: Operator widzi `[redacted by policy: pii_email]` z
   tooltip "request elevation" przyciskiem (R4 mitigation) — czyta
   nazwę policy + ma path do eskalacji.
4. **DX-W19-04**: Departure runbook execute-able przez tech_lead w 1
   komendzie (`sylion deploy-departure --user X`) z checklist UI
   pokazującym 5 kroków + zielone/czerwone per step.

## 6. Top ryzyka

### R1: Migration storm — operatorzy mają plaintext keys w .env od miesięcy
- **Probability**: H
- **Impact**: H
- **Mitigation**: Operatorzy mogą mieć plaintext keys nie tylko w
  centralnym `.env`, ale w **prywatnych branchach, gist'ach, slack
  pinach, laptop home dir**. Bulk migration tool `secrets_migrate_dotenv.
  py` skanuje znane lokalizacje + git history (`git log -p | grep -E "sk-
  |api_key="`); generuje raport z `severity: high|medium|low` per
  finding. **90-day deadline** liczone od G1 release. Każdy plaintext
  finding po deadline blokuje deploy do `prod` tag w W17 policy engine.
  Cleanup procedure z `git filter-branch` lub BFG dla legacy plaintext;
  rotate wszystkie keys znalezione w git history (zakładamy że są
  compromised).
- **Trigger to escalate**: 5+ keys znalezione post-deadline → freeze
  release, mandatory training session, HG D4 review.

### R2: Audit log jako hot-spot performance — W17 cluster z 20 nodes
- **Probability**: H
- **Impact**: H
- **Mitigation**: 20 nodes × ~50 events/sec = ~1k events/sec sustained,
  burst do 10k/sec podczas deploys. PostgreSQL append-only może być
  wąskim gardłem przy synchronous writes. Architectura:
  - **Async batch insert**: events buforowane w Redis stream 100ms
    windows, batch insert COPY co 1s.
  - **Partitioning**: PG table partitioned po `event_type` + `month` —
    write spread po wielu partycjach.
  - **Optional Kafka backbone** dla teams z volume > 10k/sec sustained
    (post-G4 deliverable, hidden behind `audit_backend: kafka` config
    flag).
  - **Hash chain consistency**: chain liczony per event type — jeden
    `secret.read` chain niezależny od `auth.login` chain. Pozwala na
    parallel writes.
  - Performance test G2/G4: 10k events/sec generated, mierzone P-W19-02.
- **Trigger to escalate**: Test pokazuje sustained > 5% write latency
  > 100ms → Kafka backbone wcześniej (HG D4) lub partition strategy
  redesign.

### R3: Backup admin lockout — break-glass scenario
- **Probability**: M
- **Impact**: H (catastrophic)
- **Mitigation**: Single owner zwolniony / niedostępny → kto teraz
  rotuje keys, kto autoryzuje destructive deploys? Mitigations:
  - **N+1 owners zawsze**: minimum 2 active owners w każdym momencie.
    System blocks deactivation jeśli to ostatni active owner — wymaga
    explicit reasignment.
  - **Sealed offline envelope**: paper trail + Yubikey z pre-generated
    break-glass token w fizycznej kopercie u Roberta + 1 trusted backup
    person. Drill co 6 miesięcy: open envelope, verify token works,
    re-seal.
  - **Time-locked recovery**: gdyby cały zespół zniknął, master key
    recovery wymaga 7-dniowego time-lock (audytowalne, alertowalne) —
    nie da się spontanicznie podmienić auth backend.
  - **Audit access-report quarterly**: PDF report "kto jest owner, kiedy
    last login, kiedy MFA last verified".
- **Trigger to escalate**: Drill envelope nie działa lub token expired →
  immediate re-issue + RCA (incident D5).

### R4: Field redaction false positives — operator widzi `redacted_***` zamiast danych
- **Probability**: M
- **Impact**: M
- **Mitigation**: Klasyczny UX problem — operator otwiera ticket
  klienta, widzi `klient_email: [redacted]` i myśli że dane są stracone /
  system się zepsuł. Mitigations:
  - **Explicit reason**: zamiast `[redacted]` renderujemy `[redacted by
    policy: pii_email]` — operator wie którą regułę.
  - **Tooltip + escalation button**: hover na `[redacted ...]` → tooltip
    "Twoja rola (`developer`) nie ma dostępu do tego pola. **Request
    elevation** przycisk → wysyła HG D3 do tech_lead z auto-context.
  - **Decision telemetry**: zliczamy ile razy operator klikował
    "elevation" — jeśli >50% requests dla danej reguły są elevowane,
    znaczy że redaction matrix jest źle skalibrowany, re-eval.
  - **Audit log każdego elevation request** — rola pop-up dla escalation
    abuse.
- **Trigger to escalate**: > 100 elevations/tydzień dla jednego pola →
  redaction policy review (Council vote, może downgrade severity).

### R5: External pen-test surprises — niezależny audyt znajduje niespodzianki
- **Probability**: M
- **Impact**: H
- **Mitigation**: Independent pen-test firmy często znajdują dziury,
  które inhouse tests miss (timing attacks, race conditions w token
  refresh, OAuth state parameter abuse, JWT algorithm confusion). Brief
  zalecił **pen-test w G2 (early), nie G4** — i to jest świadome
  decyzja.
  - **Pen-test #1 w G2**: 5 dni, focus auth + secrets + RBAC. Findings
    feed do G3+G4 backlog. Cost ~$15-25k.
  - **Pen-test #2 w G4**: 5 dni, focus regression + production-readiness
    + GDPR + audit chain. Cost similar.
  - **Bug bounty post-v3.0** opcjonalnie via Hacker0ne (rozważyć w v3.5).
  - **Threat model document** w G1 — STRIDE per komponent, recenzowany
    przez external firm jako pre-pen-test.
- **Trigger to escalate**: Pen-test #1 znajdzie 1+ critical lub 3+ high
  → freeze G3, dedicated 4-week remediation sprint, re-test pre-G3.

## 7. Tech stack

| Component | Choice | Rationale |
|---|---|---|
| Auth | OAuth 2.1 + PKCE | Standard, no custom crypto, mature client libs. |
| JWT | python-jose / pyjwt | Already in v1 stack; mature, good defaults dla `RS256` (asymmetric). |
| Identity providers | local + Google + GitHub + Microsoft Entra | PDF §9.1 implied 10-os zespołu — 80% zespołów ma już Google/GitHub/MS account. |
| MFA | TOTP (pyotp) + WebAuthn (post-G4) | TOTP universal, WebAuthn passkeys for owner role v3.x. |
| Secrets (default) | extension istniejącego KeyVault + AES-GCM-256 + Argon2id KDF | Already integrated; modern crypto; no new ext deps. |
| Secrets (file-level) | sops + age | dla files w git (config overlays z W17), declarative encryption. |
| Secrets (optional) | HashiCorp Vault adapter | Plug-in dla teams z istniejącą Vault infra. |
| Audit storage | hash-chain table per event type w PG (W15 pattern) | Spójność z lineage approach (evidence_spine). |
| Field redaction | declarative w W15 manifest, FastAPI middleware + OSDK hook | Single source of truth, zero kod-coupling. |
| Policy engine | pluggable: JSON (default, z W17) + OPA adapter (future) | PDF §2.5 minimalizm, escape hatch dla complex rules. |
| Privacy routing | adapter w W11 + W17 federation router | Re-use existing routing infra, dodajemy filter layer. |
| GDPR erasure | tombstone pattern + W15 cascade FK + audit immutable | Hash chain preserved (Q3). |
| Testing | pytest + testcontainers + Playwright + external pen-test | Spójność + independent assurance. |

## 8. Dependencies

- **Hard**:
  - **W15 G2** — OSDK dla policy/audit ontology types (`User`, `Session`,
    `Role`, `ProjectMembership`, `KeyACL`, `SecretAccessEvent`,
    `AuditEvent`, `RoutingEvent`, `RedactionRule`).
  - **W17 G2** — node-level policy enforcement (multi-node deploys
    propagują JWT + RBAC do remote calls, central plane authoritative
    dla token issuance).
  - `sylion/api/rbac_enforcement.py` (v1) — extension target, nie
    replacement.
  - `sylion.core.event_bus` — auth events publishing.
  - Existing KeyVault module — wrapped w `audited_vault.py`.
- **Soft**:
  - **W18 G2** — terminal events redaction (W18 stream pokazuje events
    z różnych ról; redaction engine W19 filtruje przed SSE write).
  - W14 E5 Guardians — alert injection na audit chain breaks.
  - W11 Adapter Bus — privacy tag propagation do LLM call routing.
- **External**:
  - PostgreSQL 15+ (z W15) — partition support dla audit log scale.
  - Redis (z v1) — JWT revocation list cache + audit batch buffer.
  - External pen-test firm (kontrakt, ~$30-50k total dla 2 sessions).

## 9. Modules created

- `sylion/aeis_v2/policy/__init__.py` — public API exports.
- `sylion/aeis_v2/policy/auth/jwt.py` — JWT issuance + validation +
  revocation list cache.
- `sylion/aeis_v2/policy/auth/oauth.py` — OAuth 2.1 PKCE + client_
  credentials flows.
- `sylion/aeis_v2/policy/auth/providers/local.py` — local PG-backed users.
- `sylion/aeis_v2/policy/auth/providers/google.py` — Google Workspace OIDC.
- `sylion/aeis_v2/policy/auth/providers/github.py` — GitHub OAuth.
- `sylion/aeis_v2/policy/auth/providers/microsoft.py` — Microsoft Entra.
- `sylion/aeis_v2/policy/auth/mfa.py` — TOTP, WebAuthn (post-G4).
- `sylion/aeis_v2/policy/rbac/extended_policy.py` — extends v1
  `rbac_enforcement.py` z 5 nowymi rolami + per-project scope.
- `sylion/aeis_v2/policy/rbac/policy_matrix_loader.py` — YAML loader +
  CI guard "every endpoint mapped".
- `sylion/aeis_v2/policy/secrets/audited_vault.py` — wraps istniejący
  KeyVault z `SecretAccessEvent` log + `KeyACL` enforcement.
- `sylion/aeis_v2/policy/secrets/vault_adapter.py` — opcjonalny
  HashiCorp Vault backend.
- `sylion/aeis_v2/policy/data/redaction.py` — field-level redaction
  engine (FastAPI middleware + OSDK hook).
- `sylion/aeis_v2/policy/audit/chain.py` — hash-chained audit log,
  verify tool, GDPR-aware tombstone.
- `sylion/aeis_v2/policy/audit/events.py` — event taxonomy + builders.
- `sylion/aeis_v2/policy/departure/runbook.py` — automated revocation
  flow z step-by-step audit.
- `sylion/aeis_v2/policy/privacy/routing_tags.py` — privacy-level
  propagation do W11 + W17 routing.
- `sylion/api/policy_routes.py` — REST endpoints (login, logout, refresh,
  rotate-keys, departure, access-report).
- `policy/rbac/policy_matrix.yaml` — single source of truth dla role ×
  action matrix.
- `policy/audit/event_taxonomy.yaml` — event types catalog.
- `scripts/secrets_migrate_dotenv.py` — bulk migration tool.
- `scripts/access_review_pdf.py` — quarterly compliance report generator.
- `scripts/dr_drill_break_glass.sh` — semi-annual envelope drill.
- W15 manifests: `User`, `Session`, `Role`, `ProjectMembership`,
  `KeyACL`, `SecretAccessEvent`, `AuditEvent`, `RoutingEvent`,
  `RedactionRule`, `GdprErasureRecord`.

## 10. Migration from v1

| Step | What | Rollback |
|---|---|---|
| 1 | **Audit current state**: skan których endpoints są unauth'd, które keys plaintext, które operacje pomijają audit. Output: `docs/v2/migration/V1_POLICY_INVENTORY.md`. Zawiera per-endpoint risk score. | Audit-only. |
| 2 | **Add JWT optional** (parallel z current dev bypass) by 1 month. `Authorization: Bearer X` accepted ale brak — stary path działa. Dual-mode. Test: 100% endpoints accept JWT, > 80% klientów (frontend, terminal) emitują JWT. | Toggle config flag `JWT_REQUIRED=false`, return do v1 behavior. |
| 3 | **Migrate KeyVault entries to audited variant**: per key, `audited_vault.read_secret(key, actor)` zastąpi raw `KeyVault.get(key)`. Bulk migration script. | Per-key revert do raw read; brak audit, no data loss. |
| 4 | **Roll out RBAC POLICY map updates per endpoint group** (auth, idea, funding, customers, ...). Każda grupa 1-2 dni walk-through, CI guard added incrementally. | Per-group feature flag — group revert do v1 RBAC enforcement. |
| 5 | **Field redaction in API responses** (declarative). Pilot na `/api/v1/customers` (PII ciężki), test z 3 ról (developer/auditor/owner). | Per-type feature flag `redaction.enabled: false`. |
| 6 | **Privacy tags integration** w W11 routing. Pilot z 1 LLM call type (np. summarization). | Tag ignored — fallback do default routing. |
| 7 | **External pen-test #1** (G2) — findings → G3 backlog. | N/A (audit only). |
| 8 | **External pen-test #2** (G4) — passed → cutover. | Re-mediate findings, re-test. |
| 9 | **Cutover** (remove dev bypass) — `JWT_REQUIRED=true` strict by default. Dev bypass usunięty z code. | Restore commit z dev bypass; emergency only z HG D5. |

W19 nie zastępuje istniejących RBAC z `sylion/api/rbac_enforcement.py` —
**rozszerza**. Migration jest *additive* + *enforcement strengthening*,
nie *replacement*.

## 11. D-level rationale

**D5** (najwyższy):
- **Każdy bug w policy plane = potencjalna kompromitacja danych zespołu**
  (10 osób, grant applications, financial data, klient information).
- **Departure scenario nieprzyjazny** = potencjalny insider threat. Brak
  W19 = brak technical control, tylko trust-based (PDF §9.1: "Co jeśli
  ktoś z zespołu odejdzie nieprzyjaźnie?").
- **External pen-test failure w G4 → company-wide compromise**.
- **Impact jest nieodwracalny**: dane wyciekły zostają wyciekłe, leaked
  API key musi być rotated + assume-compromised wszystkie poprzednie
  generated content na tym kluczu (GDPR / professional liability).
- **Audit log integrity** ma compliance implications (SOC 2, ISO 27001).
- **HG required**: G1 (auth backbone), G2 (production data redaction
  goes live), G4 (production promotion + remove dev bypass).

Dlaczego nie D4: D4 zarezerwowane dla "important but reversible". W19
działa na **production credentials** + **PII** + **financial data** —
incident jest niereversible w sensie compliance i trust. → D5 (parallel
z W15, W17 w severity).

Dlaczego nie wyższy: W AEIS D5 jest najwyższym poziomem; W19 plasuje się
na równi z W15 (data fundament) i W17 (deploy lifecycle).

## 12. Test plan

- **Unit** (pytest) — 100+ tests:
  - `tests/aeis_v2/policy/auth/test_jwt.py` — issuance, validation,
    expiry, revocation, algorithm confusion attack vectors.
  - `tests/aeis_v2/policy/auth/test_oauth.py` — PKCE flow, state
    parameter, CSRF, code interception.
  - `tests/aeis_v2/policy/auth/providers/test_*.py` — per-IdP integration
    z VCR cassettes.
  - `tests/aeis_v2/policy/rbac/test_extended_policy.py` — RBAC matrix:
    100% endpoints × 6 ról × 4 actions = 2400 cells, golden table.
  - `tests/aeis_v2/policy/secrets/test_audited_vault.py` — `SecretAccess
    Event` per read, KeyACL enforcement, hash chain integrity.
  - `tests/aeis_v2/policy/data/test_redaction.py` — declarative rules,
    nested fields, edge cases (null, list of dicts, JSONB).
  - `tests/aeis_v2/policy/audit/test_chain.py` — hash chain build,
    verify, tamper detection, GDPR tombstone consistency.
  - `tests/aeis_v2/policy/departure/test_runbook.py` — full revocation
    flow, idempotent re-runs, audit completeness.

- **Integration** (testcontainers PG + Redis + FastAPI):
  - `tests/aeis_v2/integration/test_full_oauth_flow.py` — login →
    callback → JWT → API call → logout, każdy IdP.
  - `tests/aeis_v2/integration/test_departure_drill.py` — simulate
    departure: deactivate, invalidate, rotate, audit. Mierzymy MTTR
    (target < 60s).
  - `tests/aeis_v2/integration/test_audit_replay.py` — generate 10k
    events, replay, verify chain. Target P-W19-04 (1M < 30s).
  - `tests/aeis_v2/integration/test_redaction_3_endpoints.py` —
    `/customers`, `/funding`, `/ideas` z 3 ról.
  - `tests/aeis_v2/integration/test_privacy_routing.py` — `must_run_
    locally` task → routing engine wybiera lokalny tylko, fallback
    fail-explicit.

- **E2E** (Playwright + multi-user scenario):
  - `e2e/policy/test_10_user_team_scenario.spec.ts` — 10 actors w
    różnych rolach, full workflow (login, project create, funding
    submit, idea privacy, departure of one). 30+ min walkthrough.
  - `e2e/policy/test_gdpr_erasure.spec.ts` — user requests erasure,
    cascading delete, audit trail intact, replay weryfikuje chain.

- **Performance benchmark**:
  - `scripts/bench_w19.py` — auth check latency, audit ingest sustained
    rate, redaction overhead, replay speed.

- **External pen-test**:
  - **G2 pen-test**: 5 dni, focus auth + secrets + RBAC. Independent
    firm, NDA. Output: report z findings + severity.
  - **G4 pen-test**: 5 dni, focus regression + GDPR + audit chain +
    privacy routing. Output: production sign-off.

- **DR drills** (recurring):
  - **Bi-annual** break-glass envelope drill (R3).
  - **Quarterly** access review report (manual sign-off owner).
  - **Annual** full DR simulation: lose master key, recover from
    sealed envelope, verify zero data loss.

- **DX validation**:
  - 3 reviewers (kimi, codex, GLM) walk-through "first-time operator"
    dla: dodanie nowej roli, pisanie redaction rule, departure runbook
    execute. Mierzymy czas-do-pierwszego-sukcesu.

## 13. Open questions

- **Q1**: **Centralny IdP vs offline file-based JWT** — Robert pracuje
  sam (laptop), ale daje OAuth dostęp 9 deweloperom. Dwie opcje:
  (a) **central IdP** (np. small Authelia / Keycloak instance na VPS) —
  jednolity SSO, łatwy departure, ale single point of failure;
  (b) **offline file-based JWT signing** (RS256 z key per developer) —
  rozproszone, robust offline, ale departure wymaga distributed key
  rotation. **Plan v1**: central IdP via opcjonalny Authelia (lekki,
  Go binary), z fallback file-based dla developerów off-grid (max 7
  dni offline mode). Decision punkt: G1 spike + Council vote.

- **Q2**: **HSM dla disaster recovery** — Yubikey vs CloudHSM. Yubikey
  ($55-70/sztuka, fizyczny token, sealed envelope use case ideal),
  CloudHSM ($1-3k/miesiąc, regulacyjne advantage dla compliance).
  **Plan**: Yubikey Series 5 dla owner role + sealed envelope (R3).
  CloudHSM odłożone do v3.5 jeśli compliance wymóg się pojawi.

- **Q3**: **GDPR right-to-erasure vs hash-chain audit log** — kasowanie
  wpisu psuje chain. Opcje:
  (a) **soft-delete + tombstone** (wpis pozostaje z hash, ale payload
  zerowany / encrypted z erasure key następnie destroyed) — chain
  preserved, technically GDPR-compliant ("data anonymized"),
  (b) **full erase** — wpis usunięty, chain re-computed dla downstream
  events (expensive, drift risk),
  (c) **erasure log w osobnym chainie** — cancel chain + re-rooted from
  point of erasure.
  **Plan v1**: (a) tombstone — najprostszy + audit preserves event
  metadata (kto, kiedy) bez payload. Decision: Council vote pre-G3.

- **Q4**: **External collaborator role: read-only "guest" link bez
  konta?** Use case: klient chce zobaczyć status grant application bez
  zakładania konta. Bezpieczne tokeny: signed URL z TTL + IP binding +
  per-resource scope, brak token reuse. **Plan v1**: signed URLs z 24h
  TTL + jednorazowe (single-use). Zakaz dla resources z `sensitivity:
  financial`. Re-eval w v3.x jeśli use case się rozszerzy.

- **Q5**: **Audit log retention vs storage growth** — 7 lat
  (compliance) ale storage rośnie. Plan tiered:
  - Hot (PG): 90 dni — fast queries, full hash chain.
  - Warm (PG, partitioned): 1 rok — slower queries, full chain.
  - Cold (S3 / Glacier / local archive): 7 lat — parquet, indexed po
    `event_type` + `month`, hash chain crosses tiers.
  - Beyond 7 lat: schedule erasure (chyba że legal hold).
  Decision punkt: G2 z Cost Sentinel review.

- **Q6**: **Policy-as-Code: minimal JSON jak W17 vs OPA/rego później?**
  PDF §2.5 minimal JSON dla v2. W19 inherits decision. Trigger do
  migration:
  - 100+ rules w policy_matrix → expressiveness gap.
  - Computed fields / transitive evaluation needed.
  - Compliance auditor wymaga rego standard.
  **Plan**: pluggable engine od początku — `PolicyEngine` interface,
  JSON impl default, OPA adapter w `sylion/aeis_v2/policy/engine/opa_
  adapter.py` jako future option (post-G4 decision punkt).

- **Q7**: **Privacy tags w manifeście W15** — czy nowy field `privacy_
  level` w ontology type spec? Pro: deklaratywny, single source of truth.
  Con: type-level tag może być za grube (jeden Customer może mieć
  różne privacy levels per row). **Plan v1**: tag na poziomie *task*
  (PDF §8.4) i *project* (W19 sekcja 2). Per-row classification odłożony
  do v3.5 (Markings territory). Manifest pole `default_privacy_level`
  jako convenience default dla typu.

- **Q8**: **MFA scope** — wszystkie role czy tylko owner + tech_lead?
  TOTP universal, ale UX cost. **Plan v1**: opt-in dla wszystkich, **
  required** dla `owner` + `tech_lead` od G1, dla developer + auditor
  required od G4. WebAuthn / passkeys post-v3.0.

- **Q9**: **Bug bounty program** — czy uruchamiać po v3.0 release? Pros:
  ciągłe red-teaming, community signal. Cons: koszt (~$5-20k/rok minimum
  scope). **Plan**: re-eval w v3.5, after pen-test #2 confirms posture.

- **Q10**: **Cross-charter privacy_level field** — W15 manifest
  `retention_days` (W19 sekcja 2) wpływa na **wszystkie** typy ontology.
  Cascade impact: W15 G2 cutover może być potrzeba bumped jeśli
  retention enforcement aktywne. Decision: G1 spike na backward-compat —
  default `retention_days: infinite` dla istniejących typów, opt-in dla
  new types.

---

## Final report (poza 13 sekcjami)

**Liczba słów chartera**: ~3850 słów (target 3000-4000 osiągnięty).

**Cross-charter dependencies — jak W19 wpływa na W15-W18**:

- **W15 Ontology Runtime**: W19 dodaje **10 nowych ontology types** do
  W15 manifestu (`User`, `Session`, `Role`, `ProjectMembership`,
  `KeyACL`, `SecretAccessEvent`, `AuditEvent`, `RoutingEvent`,
  `RedactionRule`, `GdprErasureRecord`). Dodaje **2 nowe pola** do W15
  manifest spec: `retention_days` (per type) + `redact_for_roles`
  (per property). W15 G2 schema musi zaakceptować te ekstensje przed
  W19 G1 deploy. Hash chain pattern z W15 lineage jest re-used 1:1 dla
  W19 audit. **Impact**: dodatkowe ~2 tygodnie na W15 G2 jeśli
  retention/redaction features muszą być w core spec; alternatywnie
  W19-specific extension package nie blokujący W15 G2.

- **W16 Apps Builder**: W19 udostępnia **deklaratywny redaction layer**,
  który W16 widget engine respektuje automatycznie (`ObjectListView`,
  `ObjectDetailView` zwracają redacted dla niewystarczającego role).
  W16 manifest może deklarować `required_role` per page / per widget.
  **Impact**: W19 G1 musi shipnąć przed W16 G2 wdraża pierwszą app z
  PII (np. `customer_console`). Inaczej W16 musi mieć tymczasowy
  hardcoded RBAC, który potem replaceujemy. Recommendation: W19 G1 i
  W16 G1 mogą iść w pełni parallel (oba bazują na W15 G2); W16 G2
  poczeka na W19 G1 (dependency soft, ale strongly recommended).

- **W17 Deployment Plane**: W19 dostarcza **JWT auth dla node ↔ central
  plane** (zastępuje pre-shared token z W17 Q4 / R4). W17 policy engine
  (minimal JSON rules) używa **W19 RBAC POLICY map** dla autoryzacji
  deploy commands. W17 audit trail łączy się z W19 hash chain. **Impact**:
  W17 G2 z pre-shared token jest first-pass; W17 G3+ migruje do JWT
  z W19. Departure runbook (W19) rotuje deployment tokens (W17)
  automatycznie. Recommendation: W17 i W19 idą **w pełni parallel**
  (oba zaczynają od W15 G2), W19 dostarcza upgrade path dla W17 auth.

- **W18 Operator Terminal**: W19 dodaje **redaction layer** do SSE event
  stream — events propagujące PII są redacted per subscriber's role
  przed wyemitowaniem do frontend. Slash command `/secret rotate {key}`
  używa W19 audited vault. HG modal w W18 honoruje W19 RBAC (operator
  bez `tech_lead` role nie widzi opcji `rotate keys`). **Impact**:
  W18 G2 może wdrożyć podstawowy stream, W18 G3+ doda redaction
  middleware (lekki narzut, ~2ms p95 P-W19-03). Recommendation: W18
  i W19 idą parallel; W18 G3 czeka na W19 G2 dla redaction features.

**Propozycja kolejności realizacji**:

Z perspektywy 10-os zespołu (PDF §9.1) i parallelu z W17:

```
Pre-W19 phase (1-2 tyg, dedicated)        ──────────────────────────
  Threat model document (STRIDE per komponent)
  V1 policy inventory audit
  External pen-test firm contracted

Faza 1 (równoległe tracki):
  W15 G2 ────────────────────────────────────────────────────────────
            (dostarcza ontology dla wszystkich pozostałych)
  W17 G1 ───────────────────────  (local mode hardened)
  W19 ────────  (czeka na W15 G2)

Faza 2 (parallel po W15 G2):
  W15 G2 ───── (done)
  W17 G2 ─────────────────────  (central plane MVP, pre-shared tokens)
  W19 G1 ──────────────  (auth backbone + RBAC + audit foundation)
  W18 G1 ──────────  (SSE skeleton)
  W16 G1 ──────────  (manifest + 5 widgets)

Faza 3:
  W17 G3 ───────  (rollout/rollback)
  W19 G2 ───────  (redaction + departure + pen-test #1)
  W18 G2 ───────  (sessions + replay)
  W16 G2 ───────  (apps builder MVP, requires W19 G1 dla RBAC)

Faza 4:
  W17 G4 ───────  (production-ready)
  W19 G3 ───────  (privacy routing + GDPR)
  W18 G3 ───────  (interventions + redaction middleware)
  W16 G3 ───────  (custom code escape hatch)

Faza 5:
  W19 G4 ───────  (production-ready + pen-test #2 + bypass removal)
  Wszystkie warstwy w soak parallel

Total wallclock z zespołem 10 osób:
  ~16-20 tygodni do wszystkich G4 (W15+W16+W17+W18+W19)
  ~10-14 tygodni jeśli W19 robione solo (single track po W15 G2)
```

**Kolejność rekomendowana**: **W19 idzie parallel z W17, oba startują po
W15 G2**. Powody:
1. Oba potrzebują W15 G2 (HARD dep dla W17, HARD dep dla W19 ontology
   types).
2. Oba dotyczą D5-level concerns (production-impact). Lepiej je robić
   razem z dedicated focus niż serial.
3. W17 pre-shared tokens jako first-pass auth → później upgrade do
   W19 JWT. Tymczasowy "v1" auth W17 nie blokuje W19 development.
4. Pen-test #1 w W19 G2 może zaadresować również W17 surfaces (centralny
   plane endpoint).
5. Departure runbook (W19) i deployment lifecycle (W17) mają wspólne
   touchpointy (rotate deployment tokens przy departure) — synergiczna
   praca.
6. W18 i W16 czekają na W19 G1 (RBAC) + W19 G2 (redaction) jako soft
   deps — ich G2 milestones synchronizują z W19 G1/G2.

**Alternatywa**: jeśli pen-test #1 znajdzie krytyczne luki, W19 może
zwiększyć priorytet i blokować W17 G3+ do remediation. To akceptowalne
trade-off — W17 G2 produkuje deploys, ale nie powinno produkować
**production deploys** zanim W19 G2 (redaction + departure) nie jest
green.

---

## Architectural Decision (2026-04-27)

See [ADR-001](../decisions/ADR-001-five-architectural-decisions-2026-04-27.md) — Decision #4 (and Decision #5 for W7→W13 task-to-role matching, which folds into the Wave-3 W7+W13 plan tracked alongside W19).

**Resolved (Decision #4 — Policy DSL):** YAML + sandboxed jinja2 for default cases; SandboxedEnvironment configured strictly (no `__class__` access). Pluggable engine retained (Q-W19-6); pivot to OPA/Rego only if transitive relationships emerge.

**Resolved (Decision #4 — operational directive, PARKED):** W19 evaluator + Release Rail enforcement is **PARKED** until W15/W16/W17/W18 + W7/W11/W13 are feature-complete. Operator argument verbatim: *"Setki reinstalacji AEIS przy rozbudowanym systemie bezpieczeństwa to byłaby tragedia"* — security applied last, once core is stable. Audit-log capture (write-side hash-chain) and charter authoring continue; evaluator service, Release Rail RBAC enforcement, redaction engine production deploy, departure runbook, MFA, IdP integration are all parked. Single-tenant policy (PDF L3) carries the security guarantee in the meantime.

**Resolved (Decision #5 — Task-to-role matching, W7→W13):** Hybrid pipeline: tag overlap (Jaccard) top-10 → embeddings cosine top-3 → AdvisorCard with reasons → operator picks (or auto = top-1). Embeddings model: start with `nomic-embed-text` via Ollama (zero-cost local), upgrade if quality < threshold after 2 months. Role catalog ~30-41 roles — even weak embeddings adequate.
