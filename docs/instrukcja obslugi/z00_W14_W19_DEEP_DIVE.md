# 00 — W14-W19 DEEP DIVE — Lifecycle + Quality + Policy Planes

> **Source**: AEIS_W1_to_W19_kompletny_opis.md, sekcje W14-W19
> **Cel**: szczegółowy opis 6 warstw lifecycle (testing, ontology, apps, deploy, terminal, policy)
> **Pozycja**: Czytaj **PO** `00_ARCHITEKTURA_W1_W19.md`
>
> **Kontekst**: W oryginalnej tabeli W1-W19 te warstwy były scharakteryzowane krótko.
> Ten dokument rozwija każdą warstwę żeby manual operatora był kompletny.

---

# W14 — Testing Ontology

**Cel**: **operacyjne testowanie** — charters, findings, simulations, auto-repair, guardians, release rail.

**Esencja**: 12 epików (E1-E12) z 25 typami obiektów + 12 enums + OntologyStore.

## 12 epików (E1-E12)

### E1 — Test Charter (declarative test definition)
- **Cel**: deklaratywny opis "co testujemy + jak + acceptance criteria"
- **Format**: YAML z scope, levels (L1-L5), success criteria
- **Storage**: `test_charters` table

### E2 — Findings (detected issues)
- **Cel**: log każdego znalezionego issue z severity + provenance
- **Severity levels**: INFO / WARNING / ERROR / CRITICAL / BLOCKER
- **Provenance**: który L poziom, który test, który Guard wykrył

### E3 — Simulations (synthetic test scenarios)
- **Cel**: realistic test scenarios bez actual user interaction
- **Types**: load (k6), chaos engineering, fault injection, time-travel
- **Output**: pass/fail z metryki + recommendations

### E4 — Auto-Repair (self-healing tests)
- **Cel**: gdy test fails, attempt fix bez operator intervention
- **Limit**: per autonomy preset (Production: 0, Aggressive: 5)
- **Audit**: każdy auto-repair w `auto_repair.jsonl`

### E5 — Guardians (continuous validators)
- **Cel**: continuously verify quality invariants podczas runtime
- **Scope**: code review, contract validation, performance regression
- **Integration**: Guards (W11-W13) → Guardians (W14)

### E6 — Release Rail (gated promotion)
- **Cel**: gated promotion through environments (dev → staging → prod)
- **Gates**: per environment, per-quality-threshold
- **Rollback**: automatic gdy gate fail post-promotion

### E7 — Coverage Tracking
- **Cel**: track test coverage per module + per AC
- **Levels**: line / branch / functional / acceptance criteria
- **Targets**: per autonomy + per D-level (D4: 85%+, D5: 95%+)

### E8 — Performance Baselines
- **Cel**: baseline performance metrics, detect regressions
- **Storage**: `performance_baselines` table
- **Regression threshold**: configurable (default >20% degradation)

### E9 — Mutation Testing
- **Cel**: validate testów (test the tests)
- **Tool**: `mutmut` (Python), Stryker (JS)
- **Mutation score target**: 70%+ dla critical paths

### E10 — Property-Based Testing
- **Cel**: hypothesis-based testing dla input space
- **Tools**: Hypothesis (Python), fast-check (JS)
- **Application**: validators, parsers, format converters

### E11 — Contract Testing
- **Cel**: verify API contracts między services
- **Tools**: Pact, Schemathesis
- **Integration**: OpenAPI specs + Pact contracts

### E12 — Chaos Engineering
- **Cel**: deliberate failures dla resilience testing
- **Scope**: pod kills, network partitions, latency injection
- **Tools**: Chaos Mesh, Litmus
- **Activation**: D4+ projects, pre-production

## 25 typów obiektów + 12 enums

```yaml
# Object types (25):
TestCharter, TestRun, TestSuite, TestCase, TestStep,
Finding, FindingResolution, AutoRepair, RepairAttempt,
Simulation, SimulationScenario, SimulationResult,
Guardian, GuardianCheck, GuardianViolation,
ReleaseRailGate, RailPromotion, RailRollback,
CoverageReport, CoverageGap,
PerformanceBaseline, PerformanceRegression,
MutationReport, PropertyTestResult, ContractViolation

# Enums (12):
TestLevel (L1-L5), TestStatus, FindingSeverity,
RepairStatus, SimulationType, GuardianType,
RailGateStatus, CoverageType, RegressionType,
MutationStatus, PropertyResult, ContractStatus
```

## OntologyStore

Centralny storage dla wszystkich W14 objects. PostgreSQL z 25 tables + 12 enum types.

## Customer Y CRM W14 activity

```
Test Charter dla Customer Y CRM:
  scope: "Full SaaS CRM z payment + KSeF compliance"
  levels: [L1, L2, L3, L4, L5]
  success_criteria:
    L1 unit: 85% coverage, 100% pass
    L2 integration: 100% API contracts
    L3 E2E: 23 critical journeys
    L5 human-like: 32 mandatory scenarios

Test runs: 6 (across build phases)
Findings: 7 (all auto-repaired in faza 37)
Simulations: 5 (load, KSeF chaos, Stripe failure, timeout, network partition)
Guardians active: 4 (Coherence, Cost, Security, Quality)
Release Rail gates: 3 (dev → staging → prod)
Coverage report: 87% L1 (target 85% ✓)
Performance baselines: 12 metrics tracked
Mutation tests: 70% score on payment module
```

---

# W15 — Ontology Runtime Plane

**Cel**: **formalny model projektu jako runtime artifact** — projekt ma pojęcia domenowe (Customer, Order, Invoice) zdefiniowane jako runtime entities, validatable, evolvable.

**Status**: NEW v2 plane, sprint 4 production-complete.

## Filozofia

W1 mówi "co projekt robi" (frontend surfaces).  
W2 mówi "jak projekt żyje" (lifecycle stany).  
W5 mówi "czego projekt jest źródłem prawdy" (Księga).  

**W15 mówi: "z czego projekt jest zbudowany w kategoriach domenowych"**.

## Manifest validator

Każdy moduł projektu ma `manifest.json`:

```yaml
module_manifest:
  id: "customer_management"
  domain: "crm"
  ontology_entities:
    - Customer
    - CustomerContact
    - CustomerCategory
  
  ontology_relationships:
    - Customer.has_many(CustomerContact)
    - Customer.belongs_to(CustomerCategory)
  
  validation_rules:
    - Customer.email: valid_email_format
    - Customer.tax_id: valid_polish_NIP
  
  capabilities_required:
    - polish_identifier_validation
    - email_validation
  
  api_contracts:
    - openapi_spec: "customer_v1.yaml"
    - graphql_schema: "customer.graphql"
```

`aeis_v2/ontology/manifest.py` — runtime validator.

## Domain entities (per project)

Customer Y CRM ontology:

```yaml
ontology:
  Customer:
    fields: [id, name, tax_id (NIP), address, contacts, status]
    relationships:
      - has_many: Invoice, Payment
      - belongs_to: CustomerCategory
    validation: valid_polish_business_entity
  
  Invoice:
    fields: [id, customer_id, ksef_id, amount, status, line_items]
    relationships:
      - belongs_to: Customer
      - has_many: PaymentTransaction
    state_machine: draft → submitted_to_ksef → accepted → paid
  
  Payment:
    fields: [id, invoice_id, stripe_charge_id, amount, status]
    relationships:
      - belongs_to: Invoice
    state_machine: pending → succeeded / failed → refunded
  
  User:
    fields: [id, email, role, ...]
    
  Role:
    fields: [name, permissions]
    
  Permission:
    fields: [resource, action]
```

## Drift detection

Ontology Runtime sprawdza spójność: kod ↔ manifest ↔ Księga.

Drift triggers:
- Code dodaje field nie w manifest
- Manifest field nie used w code
- Księga mentions entity not in ontology
- Migration changes schema bez ontology update

Drift → ticket w `drift_audit.jsonl`.

## Customer Y CRM W15 events

```
Faza 17 (Goal definition):
  Initial ontology defined: 6 entities (Customer, Invoice, Payment, User, Role, Permission)

Faza 25 (Księga finalization):
  Ontology locked. Manifest validator activated.

Faza 32-36 (Build):
  Workers add entities/fields zgodnie z manifest.
  Ontology Runtime continuous validation.
  3 drift alerts:
    1. Worker added "Customer.notes" — added to manifest, OK
    2. Worker added "InvoiceLineItem" — created sub-entity, OK
    3. Worker accidentally referenced "Discount" — not in ontology
       Fix: removed reference (out of scope).

Faza 41 (Closure):
  Final ontology snapshot dla Customer Y CRM
  Stored: ontology_snapshots/customer_y_crm_v1.json
```

---

# W16 — Operational Apps Builder Plane

**Cel**: **deklaratywne tworzenie aplikacji operacyjnych** z templates + LLM generation + Council validation.

**Status**: NEW v2 plane, sprint 3 audit chain complete.

## 3 G's: G1 + G2 + G3

### G1 — Cascade (parallel verdicts)

G1 jest fast path dla prostych decyzji:
- Template selection
- Configuration validation
- Quick approvals

Gate: Council Hybrid wedge (`aeis_v2/council_v2/wedge.py`) z 9 per-role prompts (Ollama lokalne preferred).

### G2 — Template Generation (LLM)

Generuje aplikacje z templates:
- Operator describes app w naturalnym języku
- LLM wybiera template
- LLM customizes template z operator's context
- Output: working app skeleton

Audit chain: `g2_template_gen.jsonl`

### G3 — Demand Signals Migration

Migracja demand signals z W8 do operational use:
- Track which apps są często requested
- Auto-suggest popular templates
- Deprecation signals dla unused

## UI Components

Frontend surfaces dla W16:

```
EvidencePackViewer:
  - View D3+ Evidence Packs
  - Drill down per Council deliberation
  - Cross-reference z audit chains

HumanGateInbox:
  - Pending hard gates queue
  - Per-gate context + options
  - Mobile push integration

CouncilVotePanel:
  - Live Council deliberation view
  - Per-role verdicts visible
  - Sentinel veto indicators
  - Weighted vote calculation

AdvisorCardFeed:
  - Toast notifications
  - Modal dialogs (hard gates)
  - Bubble counter (pending)
  - Card history (resolved/expired)
```

## Customer Y CRM W16 events

```
Faza 16 (Project Inception):
  G2 template generation: "Polish SaaS z payment + e-invoicing"
  Generated app skeleton: 12 modules, 8 entities, 47 endpoints
  Time: 2 minutes
  Cost: $0.30 (LLM template gen)
  
Faza 38 (Acceptance Testing):
  HumanGateInbox: 5 customer feedback items pending
  CouncilVotePanel: not used (no mid-build Council needed)
  AdvisorCardFeed: 18 cards w faza 37-38

Faza 41 (Closure):
  EvidencePackViewer: 4 D3+ Evidence Packs accessible
    - Council deliberation z faza 22
    - Subscription Advisor decision z faza 30
    - Production deploy authorization z faza 39
    - Customer sign-off z faza 38
```

---

# W17 — Deployment Plane (hybrid)

**Cel**: **multi-target deployment** — local / VPS / hybrid / container / device / serverless.

**Status**: NEW v2 plane, cost ledger production-complete.

## Deployment targets

```
LOCAL:
  - Operator's machine
  - Dev environment only
  - $0 cost
  - Best dla: development, testing

VPS (Hetzner / AWS / GCP / Azure):
  - Cloud VMs
  - Cost: $5-200/mo per VM
  - Best dla: staging, production small-medium

HYBRID:
  - Mix lokalne + cloud
  - Operator's machine dla dev
  - VPS dla staging + prod
  - Best dla: solo operator z customer projects (Robert's setup)

CONTAINER:
  - Docker / Kubernetes
  - Cost: variable (per container)
  - Best dla: multi-customer SaaS

DEVICE:
  - Edge devices (IoT, on-prem appliances)
  - Cost: hardware + ops
  - Best dla: data sovereignty critical

SERVERLESS:
  - AWS Lambda, Cloud Functions
  - Cost: per invocation
  - Best dla: variable load apps
```

## Cost ledger

W17 utrzymuje **per-deployment cost ledger** w PostgreSQL (zmigrowane z JSONL):

```
cost_ledger schema:
  - deployment_id
  - environment (dev/staging/prod)
  - provider (Hetzner/AWS/etc.)
  - cost_record_timestamp
  - cost_amount
  - cost_currency
  - cost_breakdown (compute/network/storage/bandwidth)
  - billing_period
```

Audit chain: `cost_ledger.jsonl` + migration log `cost_ledger_migration.jsonl`.

## Routing decisions

W17 routes deployments based on:
- Project D-level (D4+ requires production env)
- Compliance requirements (EU sovereignty → Hetzner Helsinki)
- Cost preferences (Adaptive Preferences W13)
- Customer preferences (per-customer policy)

```
Customer Y CRM routing:
  Dev: lokalne (operator's machine)
  Staging: Hetzner CX21 Helsinki (€4.50/mo)
  Prod: Hetzner CX31 Helsinki (€8.40/mo)
  Reason: EU sovereignty (Polish gov-funded)
  Total deployment cost: $13/mo
```

## Customer Y CRM W17 events

```
Faza 32 (Build Initialization):
  Staging provisioning: Hetzner CX21 Helsinki (8 min, €4.50/mo)
  Cost ledger entry: deployment_id=staging_2026_05_15

Faza 39 (Pre-Deploy Final Check):
  Production provisioning: Hetzner CX31 Helsinki (10 min, €8.40/mo)
  Routing decision: hybrid (local dev + cloud staging+prod)
  Cost ledger entry: deployment_id=prod_2026_06_25

Faza 40 (Production Deploy):
  Canary deployment: 5% → 25% → 100%
  Cost ledger continuous tracking

Faza 41 (Closure):
  Final cost ledger:
    Staging total: €13.50 (3 weeks)
    Prod total: €1 (4 dni z faza 40-41)
    Subtotal monthly: €8.40 ongoing
```

---

# W18 — Operator Terminal Plane

**Cel**: **comprehensive operator UI** — phase-by-phase workflow przez UI.

**Status**: NEW v2 plane, **THIS MANUAL = main UI**.

## Position w architekturze

W18 to **gdzie 41-fazowy manual głównie działa**. Każda faza w manualu = workflow przez W18 frontend surfaces.

W1 dostarcza **components** (frontend pieces).  
W18 dostarcza **terminal experience** (operator workflow przez wszystkie fazy).

## Frontend surfaces (z W1)

W1 ma 13 frontend surfaces. W18 organizuje je w spójne workflows:

```
Onboarding flow (faza 1):
  onboarding_wizard → settings_advisor → ai_models_config → idea_vault

Project lifecycle (fazy 16-41):
  cockpit_project_hub
    ├── lifecycle_dashboard (project state)
    ├── council_voting (faza 20-25)
    ├── operator_monitor (live runtime)
    ├── audit_viewer (audit chains)
    └── evidence_pack_viewer (D3+ artifacts)

Continuous (cross-fazy):
  advisor_feed (toast + modal + bubble)
  faq_runbook (docs reference)
  mobile_app (companion)
```

## Per-faza terminal experience

Każda z 41 faz ma **dedykowany workflow** przez W18 surfaces:

```
Faza 1: onboarding_wizard (10 steps)
Faza 2-3: ai_models_config + settings_advisor
Faza 4-15: settings_advisor (defaults + autonomy + Guards + skills)
Faza 16-19: idea_vault + cockpit_project_hub (project setup)
Faza 20-25: council_voting (4 phases deliberation visualization)
Faza 26-31: cockpit_project_hub (planning views) + advisor_feed
Faza 32-36: operator_monitor (live runtime) + advisor_feed
Faza 37-38: cockpit_project_hub (testing dashboard) + audit_viewer
Faza 39-40: operator_monitor (deploy dashboard) + mobile_app (push)
Faza 41: evidence_pack_viewer + audit_viewer (closure)
```

---

# W19 — Policy / Security Plane

**Cel**: **runtime policy enforcement** — federation, routing rules, security policies.

**Status**: NEW v2 plane, PgPolicyRegistry production-complete.

## PgPolicyRegistry

Centralny registry policies w PostgreSQL:

```yaml
policy_categories:
  
  ROUTING_POLICIES:
    - per-customer routing rules
    - geographic constraints (EU only, etc.)
    - provider preferences
    - cost ceilings
  
  SECURITY_POLICIES:
    - access control rules
    - data classification
    - encryption requirements
    - audit retention
  
  COMPLIANCE_POLICIES:
    - GDPR enforcement
    - PCI requirements
    - HIPAA (jeśli applicable)
    - Customer-specific compliance
  
  FEDERATION_POLICIES:
    - inter-AEIS communication rules
    - shared resource access
    - role propagation
```

## Federation policy

W19 supports **federation** między AEIS instances (multi-operator):

```
Federation use cases:
  - Operator współpracuje z innym operatorem na projekcie
  - Customer ma own AEIS instance, operator dostarcza skill
  - Marketplace skills shared between operators
  
Federation policies:
  - Authentication (mutual TLS + signed tokens)
  - Authorization (role propagation rules)
  - Data sharing (GDPR-compliant)
  - Cost attribution (which operator pays for what)

Audit chain: federation_policy.jsonl
```

**Note**: dla Roberta (single-operator), federation jest minimal use.

## Jinja-based policy evaluator

Policies są template-based (Jinja2):

```jinja2
{# Customer Y CRM routing policy #}
{% if customer.country == "Poland" %}
  {% set allowed_providers = ["anthropic", "bielik_lokalny"] %}
  {% set allowed_regions = ["nbg1", "fsn1", "hel1"] %}
{% endif %}

{% if project.D_level >= 4 %}
  {% set min_encryption = "aes-256-gcm" %}
  {% set audit_chain_signed = True %}
{% endif %}

{% if compliance.includes("KSeF") %}
  {% set required_skills = ["polish_identifier_validation", "ksef_invoice_generation"] %}
{% endif %}
```

Audit chain: `w19_evaluator.jsonl`

## Policy registry CRUD

Audit chain: `policy_registry.jsonl`

Operations:
- create_policy
- update_policy (versioning)
- activate_policy
- deactivate_policy
- evaluate_policy (per request)

## Customer Y CRM W19 policies

```
Active policies dla Customer Y CRM:
  
  ROUTING:
    - Customer Y is Polish gov-funded → EU regions only
    - Allowed providers: Anthropic + Bielik (z subscription waterfall W11)
    - Allowed regions: Hetzner nbg1/fsn1/hel1
  
  SECURITY:
    - D4 project → AES-256-GCM mandatory
    - Audit chain signed (Ed25519)
    - 7-year retention dla audit
  
  COMPLIANCE:
    - GDPR: full compliance + DPA signed
    - KSeF: Polish e-invoicing mandatory
    - PCI DSS: scope minimization (only via Stripe)
    - WCAG 2.1 AA: customer-facing must comply
  
  FEDERATION:
    - No federation (single operator)
```

---

# CZĘŚĆ Z — Cross-cutting integration W14-W19

## Audit chains z 17 chains (z W10)

Per layer audit chains:

| Warstwa | Audit chain |
|---|---|
| W14 Testing Ontology | (część workflow_engine.jsonl) |
| W15 Ontology Runtime | drift_audit.jsonl |
| W16 Apps Builder | g2_template_gen.jsonl |
| W17 Deployment | cost_ledger.jsonl + cost_ledger_migration.jsonl |
| W18 Operator Terminal | (działa across multiple chains) |
| W19 Policy/Security | federation_policy.jsonl + policy_registry.jsonl + w19_evaluator.jsonl |

## Customer Y CRM W14-W19 summary

```
W14 (Testing Ontology):
  - 12 epików aktywne (E1-E12)
  - 25 typów obiektów created
  - Test Charter: 1 (full project)
  - Findings: 7 (auto-repaired)
  - Guardians: 4 active

W15 (Ontology Runtime):
  - 6 domain entities (Customer, Invoice, Payment, User, Role, Permission)
  - 12 modules manifest validators
  - 3 drift alerts (resolved)
  - Final ontology snapshot saved

W16 (Apps Builder):
  - G2 template generation: 1 (initial app skeleton)
  - 4 D3+ Evidence Packs created
  - 18 AdvisorCards in faza 37-38
  - HumanGateInbox: 5 customer feedback items

W17 (Deployment):
  - Hybrid deployment (local + Hetzner Helsinki)
  - 2 environments provisioned (staging + prod)
  - Cost ledger: continuous tracking
  - Total deployment cost: ~$13/mo ongoing

W18 (Operator Terminal):
  - 13 frontend surfaces all utilized
  - Per-faza dedicated workflow
  - Mobile companion: paired + active throughout

W19 (Policy/Security):
  - 4 active policies (routing/security/compliance/federation)
  - 100% compliance (GDPR + KSeF + PCI + WCAG)
  - Audit chain integrity: 100%
  - 7-year retention enforced
```

---

# Co operator rozumie po przeczytaniu W14-W19

1. **W14** — Testowanie nie jest ad-hoc — to **operacyjna ontology** z 12 epików E1-E12, 25 typów obiektów, OntologyStore.

2. **W15** — Projekt ma **formalny domain model** (entities, relationships, validators) — runtime drift detection.

3. **W16** — Apps są **deklaratywnie tworzone** z templates + LLM, z UI surfaces dla operator (EvidencePackViewer, HumanGateInbox, CouncilVotePanel, AdvisorCardFeed).

4. **W17** — Deployment to **hybrid multi-target** z cost ledger, routing decisions, environment management.

5. **W18** — Operator Terminal to **gdzie 41-fazowy manual żyje** — comprehensive UI z per-faza workflows.

6. **W19** — Policies są **runtime-enforced** przez Jinja evaluator + PgPolicyRegistry, z federation support.

🎯 **Manual jest teraz architecturally complete** — wszystkie 19 warstw scharakteryzowane.
