# Data Protection Impact Assessment — v5.9.1

**Trigger:** pipeline processes contractual data + user credentials + potentially biometric (Pixel adb key) → art.35 RODO high risk assessment needed.

**Document type:** DPIA stub (Data Protection Impact Assessment / Ocena Skutków dla Ochrony Danych)  
**Version:** 1.0.0 (v5.9.1)  
**Date:** 2026-04-19  
**Status:** STUB — to be completed before SaaS/multi-user production deployment  
**Legal basis:** Art.35 RODO (DSGVO)

---

## Scope

- Users table (email, password hash — Argon2)
- Audit log (IP, timestamps, actions)
- Device records (model, serial)
- API keys (LLM provider credentials — NOT user PII)

---

## 1. Description of Processing

| Element | Detail |
|---------|--------|
| **System** | SYLION Dashboard v5.9.1 — AI pipeline orchestration |
| **Deployment** | Local WSL2 (single operator: Robert); planned SaaS/RSDG GmbH |
| **Data controller** | [FILL IN: operator name / RSDG GmbH] |
| **Data processor** | N/A (self-hosted) |
| **Sub-processors** | OpenAI, Anthropic, Google (Gemini), Perplexity, xAI, DeepSeek |
| **Categories of data subjects** | System operators (employees/contractors) |
| **Nature of processing** | Authentication, session management, audit logging, device management, AI pipeline orchestration |
| **Purposes** | System access control; operational audit trail; AI pipeline management |
| **Legal basis** | Art.6(1)(b) RODO — contract performance; Art.6(1)(f) — legitimate interest (audit) |

---

## 2. Necessity and Proportionality

| Criterion | Assessment |
|-----------|------------|
| **Data minimisation** | Users table: minimal (id, username, display_name, password_hash, role). No PESEL, no address, no phone. |
| **Purpose limitation** | Audit log used only for operational security review, not profiling |
| **Retention** | sessions: 30d; audit_log: 365d; upload_history: 90d (post v5.9.1 fix) |
| **Access controls** | RBAC (owner/architect/readonly); argon2id password hashing |
| **Encryption at rest** | SQLite not encrypted (acceptable for local single-operator; SQLCipher recommended for prod) |
| **IP address** | Stored in sessions table; 30-day retention; Art.6(1)(f) basis (security monitoring) |

---

## Risks identified

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Credential theft via db.py plaintext | Medium (offline) | High | User accepts risk (ADR note) |
| Session hijack | Low (SameSite=Strict) | Medium | Cookie Secure default TRUE, logout-all |
| Audit log retention breach | Low | Medium | 365d retention + scheduled purge |
| LLM data leakage (Anthropic/OpenAI) | Low (technical prompts only) | Medium (if PII added) | DPA with providers required at SaaS |
| DeepSeek cross-border transfer (China) | Medium (no adequacy decision) | High | Transfer Impact Assessment required before PII transfer |
| Soft-deleted user data residual | Low | Medium | Hard-purge after 30d (v5.9.1 retention_cleaner) |
| Biometric inference from Pixel adb key | Low (device serial ≠ biometric) | Low | Device records contain model/serial only |

---

## 3. Legal basis

- art.6(1)(b) contract performance — authentication, session management
- art.6(1)(f) legitimate interest (audit) — audit_log, security logging

---

## 4. Consultation

| Stakeholder | Status |
|-------------|--------|
| DPO / IOD | N/A — not yet designated; required if SaaS > 250 users processing regularly |
| Data subjects | Operators informed via Privacy Policy (docs/PRIVACY_POLICY_PL.md, docs/PRIVACY_POLICY_DE.md) |
| Supervisory authority (UODO/BfDI) | Prior consultation not required for current scope (Art.36 threshold not met) |
| RSDG Betriebsrat | Required before RSDG workplace deployment (BetrVG §87(1)(6)) |

---

## 5. Residual risk: ACCEPTABLE (local deployment, single operator)

**Assessment:** For the current single-operator local deployment on WSL2, the residual privacy risk is **ACCEPTABLE**. The system processes minimal PII (username, IP, session data) with proper technical controls (argon2id, SameSite=Strict cookies, 30-day session retention, 365-day audit retention).

**Conditions for re-assessment (full DPIA required):**
- Transition to SaaS or multi-tenant deployment
- Processing data of RSDG GmbH employees (→ BDSG §26 + BetrVG §87)
- Addition of invoicing module with financial data
- Integration of analytics or profiling features
- Cross-border transfer of PII to DeepSeek or other non-adequacy-decision countries

---

## 6. Measures implemented in v5.9.1

| Measure | Implementation |
|---------|---------------|
| DSR endpoints (Art.15-20) | `DELETE /api/auth/me/data`, `GET /api/auth/me/export` |
| Retention enforcement | `dashboard/retention_cleaner.py` — all personal data tables |
| upload_history retention | 90-day default, configurable (`UPLOAD_HISTORY_RETENTION_DAYS`) |
| Soft-delete + hard-purge | `deleted_at` column + `purge_soft_deleted_users()` after 30d |
| Cookie consent notice | Banner in dashboard UI (art.6(1)(b) basis disclosed) |
| RoPA update | `docs/RODO_COMPLIANCE.md` § v5.9.1 update |
| KSeF/E-Rechnung status | `docs/KSEF_ERECHNUNG.md` — N/A documented |

---

## 7. Review schedule

| Event | Action |
|-------|--------|
| Every 12 months | Review and update this DPIA |
| Before SaaS launch | Full DPIA with DPO consultation |
| Before RSDG deployment | BDSG §26 analysis + Betriebsrat consultation |
| After any data breach | Immediate DPIA re-assessment + Art.33 notification within 72h |

---

*DPIA stub created by Fix Cluster Q — RODO/KSeF Compliance, SYLION v5.9.1, 2026-04-19.*  
*This is a preliminary assessment, not a legal opinion. Consult a RODO/DSGVO specialist before production deployment.*
