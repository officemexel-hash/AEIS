# 05 SECURITY LAYER DEEP DIVE — Deduplication & Consolidation

**Date:** 2026-04-24
**Layer:** L5 Security (18 modules)
**Status:** Analysis for consolidation planning

---

## 1. Canonical vs Extended (8+10)

### Canonical Security Modules (Book v3.5)

| Module | LoC | Status | Purpose |
|--------|-----|--------|---------|
| security.auth_provider | 843 | FULL | Local token → Keycloak OIDC |
| security.bootstrap_init | 169 | PARTIAL | Admin init → secure seed + hardware token |
| security.session_broker | 266 | FULL | Sessions → Redis + JWT rotation |
| security.policy_engine | 550 | FULL | Allow-list → OPA + fine-grained |
| security.execution_guard | 469 | FULL | Subprocess isolation → PHANTOM + gVisor |
| security.secret_provider | 385 | FULL | .env → HashiCorp Vault |
| security.audit_sink | 500 | FULL | Event routing engine (webhook/file/db) |
| security.phantom_wrapper | 332 | FULL | Sandbox wrapper → full PHANTOM |

### Extended Security Modules (10 — additions beyond Canon)

| Module | LoC | Status | Purpose | Conflicts With |
|--------|-----|--------|---------|-----------------|
| security.audit_query | 361 | FULL | Indexed audit query engine | audit_sink |
| security.audit_trail_aggregator | 462 | FULL | Unified audit trail + hash chain | audit_sink, audit_query |
| security.bootstrap_flow | 499 | FULL | Bootstrap orchestration flow | bootstrap_init |
| security.evidence_signer | 478 | FULL | Evidence signing (Ed25519) | evidence_spine (core) |
| security.hardened_audit | 358 | FULL | Security findings + remediation | audit_sink, security_audit |
| security.key_vault | 767 | FULL | Key storage & rotation | secret_provider |
| security.profile_swap | 383 | FULL | Profile swap orchestration | security_profiles |
| security.profiles | 67 | STUB | Security profile definitions | security_profiles |
| security.security_audit | 532 | FULL | Audit findings & scans | audit_sink, audit_query |
| security.security_profiles | 509 | FULL | Profile management (DB-backed) | profiles, profile_swap |

---

## 2. Duplication Analysis

### Cluster A: Audit & Event Logging (4 modules)

**Problem:** Four overlapping implementations for audit/event tracking

- **audit_sink** (500 LoC, FULL): Event routing engine
  - Subscribes to events via EventBus, routes to webhooks/file/db
  - Single delivery per subscription
  - No query capability

- **audit_query** (361 LoC, FULL): Indexed query over audit events
  - Fast query engine with filtering, indexing, tags
  - No routing, no subscriptions
  - Pure read interface

- **audit_trail_aggregator** (462 LoC, FULL): Unified audit trail
  - Aggregates from multiple sources (api, security, governance, pipeline, council, workspace)
  - Hash-chain for integrity verification
  - Query + filtering built-in

- **security_audit** (532 LoC, FULL): Findings + remediation
  - Findings (severity: info/low/medium/high/critical)
  - Scans and remediation tracking
  - Separate from event audit

**Status:** Audit_query + security_audit are duplicative of audit_trail_aggregator

**Recommendation:**
- **CONSOLIDATE to audit_trail_aggregator** (keep only this one)
  - Add routing/subscription layer (from audit_sink)
  - Add query API (from audit_query)
  - Add findings tracking (from security_audit)
- **REMOVE:** audit_query (query layer merges to aggregator)
- **REMOVE:** security_audit (findings merges to aggregator)
- **REMOVE:** hardened_audit (findings subset merges)
- **KEEP but rewrite:** audit_sink → audit_subscription service

**Consolidation effort:** ~2 days (merge 4 modules into 1 comprehensive)

### Cluster B: Security Profiles (3 modules)

- **profiles** (67 LoC, STUB): Data class with hardcoded profile defs (dev-light, test-light, prod-strict)
  - NO database persistence
  - NO lifecycle management
  - Just static constants

- **security_profiles** (509 LoC, FULL): DB-backed profile management
  - CRUD on profiles
  - Rule binding (profile_rules table)
  - Event emission

- **profile_swap** (383 LoC, FULL): Profile swap orchestration
  - Pending/completed swap tracking
  - Swap audit trail
  - State machine for swap workflow

**Status:** profiles.py is unused stub

**Recommendation:**
- **REMOVE:** profiles.py (stub, replaced by security_profiles)
- **MERGE:** profile_swap → security_profiles as swap_service()
  - Unify profile lifecycle + swap operations

**Consolidation effort:** ~1 day (merge profile_swap into security_profiles)

### Cluster C: Bootstrap Security (2 modules)

- **bootstrap_init** (169 LoC, PARTIAL): Initialize secure bootstrap
  - Create admin seed, hardware token binding
  - Migration path from plaintext

- **bootstrap_flow** (499 LoC, FULL): Full bootstrap orchestration
  - Multi-stage bootstrap workflow
  - Covers auth→secrets→policy→audit pipeline
  - State machine for bootstrap phases

**Status:** bootstrap_init is canonical but incomplete; bootstrap_flow extends it

**Recommendation:**
- **MERGE:** bootstrap_flow into bootstrap_init
  - Expand bootstrap_init from 169 to 500+ LoC
  - Make it the canonical bootstrap orchestrator

**Consolidation effort:** ~1 day

### Cluster D: Secret/Key Storage (2 modules)

- **secret_provider** (385 LoC, FULL): Secrets mgmt → HashiCorp Vault
  - Canonical secret storage
  - Supports M0→M5 evolution

- **key_vault** (767 LoC, FULL): Key storage + rotation
  - Specialized for key material (not general secrets)
  - Rotation policies
  - Hardware token binding

**Status:** Overlapping scope

**Recommendation:**
- **KEEP secret_provider** (canonical)
- **MERGE key_vault into secret_provider** as key_rotation service
  - key_vault functionality → secret_provider module

**Consolidation effort:** ~1.5 days

### Cluster E: Evidence Signing (1 module + cross-layer)

- **evidence_signer** (478 LoC, FULL): Ed25519 evidence signing
  - BUT: evidence_spine (core layer) also does signing
  - CONFLICT: two implementations of append-only Ed25519 log

**Recommendation:**
- **CONSOLIDATE:** evidence_signer → evidence_spine
  - evidence_spine in core layer should be canonical
  - Remove security.evidence_signer

**Consolidation effort:** ~1 day (if evidence_spine is kept clean)

---

## 3. Summary: 18→10 Consolidation Map

| Action | Modules | Result | Effort |
|--------|---------|--------|--------|
| Remove STUB | profiles | 17 modules | 0h |
| Consolidate audit | audit_query + security_audit + hardened_audit → audit_trail_aggregator | 14 modules | 8h |
| Consolidate profiles | profile_swap → security_profiles | 13 modules | 4h |
| Merge bootstrap | bootstrap_flow → bootstrap_init | 12 modules | 4h |
| Merge key vault | key_vault → secret_provider | 11 modules | 6h |
| Consolidate evidence | evidence_signer → evidence_spine | 10 modules | 4h |

**Final L5 Security:** 10 consolidated modules (from 18)

---

## 4. Recommendation Summary

**Modules to DELETE (stub or clearly redundant):**
1. security.profiles (67 LoC, STUB) — replaced by security_profiles

**Modules to REMOVE via consolidation:**
1. security.audit_query → merge to audit_trail_aggregator
2. security.security_audit → merge to audit_trail_aggregator
3. security.hardened_audit → merge to audit_trail_aggregator
4. security.profile_swap → merge to security_profiles
5. security.bootstrap_flow → merge to bootstrap_init
6. security.key_vault → merge to secret_provider
7. security.evidence_signer → consolidate to core.evidence_spine

**Result:** 18 modules → 10 consolidated + canonical modules

**Total effort:** ~3-4 days of focused consolidation work

