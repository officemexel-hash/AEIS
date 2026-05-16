# SYLION v5.9.0 Doc Analysis — Analyst: Gemini 3.1 Pro
**Role:** Architecture & Integration Auditor / Gap Analysis Specialist
**Scope:** Architecture claims, integration points, missing docs, v5.9.0 planning gaps

---

## Classification: TECHNICAL

All 6 files are TECHNICAL documentation. Language: Polish (README, changelogs, REPORT) and English (status trackers). Audience: internal engineering team.

---

## Architecture Claim Verification

### Pipeline Stage Count

| File | Stage count | Details |
|---|---|---|
| README.md | 12 | "Pipeline (12 etapów)" diagram |
| PIPELINE_STATUS.md | 13 rows | 0, 1, 2, 3, 4, 5, 6, 6.5, 7, 7.5, 8, 8.5, 9 = 13 distinct stages |
| STREAMING_STATUS.md orchestrator section | "Stages: 1, 2, 3, 4, 5, 5.5, 5.6, 6, 6.5, 7, 7.5, 8, 8.5, 9" = 14 stages |

**INC-A01 (HIGH): Stage count inconsistency — 12 vs 13 vs 14**
- README says "12 etapów" but lists Stage 0, 1, 2, 3, 4, 5, 6, 6.5, 7, 7.5, 8, 8.5, 9 = 13 distinct stages (or 14 counting sub-stages differently)
- STREAMING_STATUS adds Stage 5.5 and 5.6 that appear NOWHERE in README or PIPELINE_STATUS
- These are undocumented stages. Stage 5.5 is described as "RUNTIME health checks (8 subsystems)" in STREAMING_STATUS but has no row in PIPELINE_STATUS.

**INC-A02 (MEDIUM): Stage 5.5 and 5.6 not documented**
- STREAMING_STATUS.md: "Stages: 1, 2, 3, 4, 5, 5.5, 5.6, 6, 6.5..."
- STREAMING_STATUS.md: "Stage 5.5 RUNTIME: Now checks 8 subsystems (was 4)"
- Stage 5.6: "independent LLM fact-check before Stage 6 (Deploy)" = fact_checker.py
- These stages are IMPLEMENTED but absent from README pipeline diagram and PIPELINE_STATUS table

### Agent Distribution by Stage

PIPELINE_STATUS.md: Stage 0 = 8 agents (supervisor, coordinator, book_guardian, budget_guard, file_verifier, stream_monitor, search_agent, reasoning_agent)

README.md Stage 0 text: "Supervisor + Coordinator + BookGuardian + BudgetGuard + FileVerifier + StreamMonitor + Search + Reasoning (meta-agenty)" = 8 ✅

PIPELINE_STATUS.md Stage 2: "5 auditors" ✅ matches audit table (11-15)

PIPELINE_STATUS.md Stage 8: "4 agents (Red Team ×2 + Blue Team ×2)"
README.md Stage 8: "Red/Blue Team ×4 (sieciowy + app + monitor + hardener)" ✅

STREAMING_STATUS Executive Summary: "10 streaming agents (all stages)"
- Stage 6.5 = 7
- Stage 7.5 = 2
- Stage 0 (stream_monitor) = 1
- Total = 10 ✅

✅ Streaming agent counts are internally consistent across STREAMING_STATUS.

### Anti-Hallucination Layer Count

| File | Count | Description |
|---|---|---|
| README.md section 6 | 1 section "Anti-Hallucination Layer" | file_verification_complete.py, 6 hallucination types |
| README.md (implied via modules) | mentions build_verification in pipeline but not numbered separately |
| PIPELINE_STATUS | 5 layers | L1 file_verification, L2 build_verification, L3 claim_provenance, L4 semantic_dedup, L5 fact_checker |
| STREAMING_STATUS | 5 layers | Same as PIPELINE_STATUS |

**INC-A03 (MEDIUM): README describes only 1 anti-hallucination layer (file verification)**
README section 6 only describes SHA-256 file verification (L1). Layers L2-L5 are not documented in README at all. A developer reading only README would not know about build_verification.py, claim_provenance.py, semantic_dedup.py, or fact_checker.py.

### Dashboard Architecture

**INC-A04 (HIGH): Dual dashboard architecture never explained**

README mentions TWO dashboard systems with no explanation of their relationship:

1. **`dashboard_server.py`** (line 172-195): "wbudowany panel... serwer HTTP na stdlib (zero zewnętrznych zależności). Startuje automatycznie razem z pipeline." — Shows: 4 panels (Pipeline, Streaming, Security, Devices). Runs on unspecified port (says 8420 in example).

2. **`dashboard/`** directory (line 281-311): "Pełny panel operacyjny pipeline — dashboard/ w projekcie." Uses FastAPI + SQLite. Runs on port 8421. Shows: Dashboard, Human Gate, Agenci, Prompty, Ustawienia, Monitoring, Audit Log.

- Are these the SAME system? DIFFERENT systems? Is dashboard_server.py the OLD version replaced by dashboard/?
- CHANGELOG_v5.8.8.md fixes are all in `dashboard/db.py`, `dashboard/app.py`, `dashboard/start.py` — suggesting `dashboard/` is the CURRENT system
- `dashboard_server.py` is never mentioned in any changelog fix or status file
- bridge.py (CHANGELOG_v5.8.8.1 H-02) is in `dashboard/bridge.py` — confirms dashboard/ is primary
- **Conclusion: `dashboard_server.py` reference in README may be STALE/LEGACY documentation**

---

## Integration Point Gaps

### INC-I01 (HIGH): agents.yaml never described in detail

- README: "Single Source of Truth: agents.yaml" (callout box)
- PIPELINE_STATUS: "agents.yaml: canonical agent config"
- But NO document describes the agents.yaml FORMAT, SCHEMA, or FIELDS
- CHANGELOG_v5.8.8 Bug 3: mentions `_parse_agents_yaml`, role fields like `Strażnik Księgi`, `Weryfikator`
- CHANGELOG Finding C: mentions `enabled=true` default for all agents
- No document answers: what fields are supported? What happens if a required field is missing? How do you add a new agent?

### INC-I02 (MEDIUM): `sylion_deps.py` mentions — M-05 roadmap item

CHANGELOG_v5.8.8.1.md:
- Added: `ADR-002-doc-scope-mismatch.md` documents the PDF mismatch ("18 declared fixes, 16 fictional about non-existent sylion_deps.py")
- M-05: "sylion_deps.py jeśli zdecydujemy się wdrożyć architekturę z PDF"

The original `SYLION_v588_dokumentacja.pdf` apparently described a `sylion_deps.py` that does not exist. ADR-002 documents this. But v5.9.0 has no decision document about whether to implement or permanently abandon `sylion_deps.py`. This architectural ghost should be formally resolved.

### INC-I03 (MEDIUM): No documented rollback procedure

- CHANGELOG_v5.8.8.1.md `deployment-council`: "rollback 3-warstwowy OK"
- But no RUNBOOK or document describes what the 3-layer rollback IS
- If deployer follows docs, they have no rollback procedure

### INC-I04 (LOW): StreamMonitor described inconsistently

- PIPELINE_IMPLEMENTATION_STATUS.md: Stage 5.5 health checks now cover 8 subsystems (was 4) — but Stage 5.5 does not appear in the pipeline stages table
- STREAMING_STATUS: stream_monitor at Stage 0 monitors 8 subsystems "continuously" but also triggers during Stage 5.5
- When exactly is stream_monitor active? Stage 0 only? Also Stage 5.5? Continuous daemon?

---

## v5.9.0 Planning Gaps — What MUST be Created

Based on analysis of all 6 documents:

### Tier 1 — CRITICAL (must exist before v5.9.0 ZIP)

1. **CHANGELOG_v5.9.0.md** — obvious requirement, does not exist yet
2. **MIGRATION_v5.8.8.1_to_v5.9.0.md** — two breaking changes in v5.8.8, more expected in v5.9.0. Operators MUST know what to change.
3. **STATUS files date update** — PIPELINE_STATUS and STREAMING_STATUS dated 2026-04-11 (7 days before v5.8.8 release). Must be regenerated or hand-updated.
4. **v5.8.9 roadmap resolution** — each of the 5 PLANNED v5.8.9 security items needs explicit status (done/deferred/dropped).

### Tier 2 — HIGH (strongly recommended)

5. **UPGRADE_GUIDE.md** — step-by-step from v5.8.x to v5.9.0 including DB migration, config changes
6. **agents.yaml SCHEMA REFERENCE** — at minimum a commented template showing all supported fields
7. **RUNBOOK.md** — operational day-to-day: how to start, stop, check health, rollback, add agent
8. **README port fix** — at minimum fix the 8420 vs 8421 contradiction and explain 18422 test port
9. **Dashboard architecture clarification** — is `dashboard_server.py` legacy? Document clearly.

### Tier 3 — RECOMMENDED

10. **GLOSSARY.md** — "Pion D", "Strażnik Księgi", "Księga SYLION 3.4 FIXED", "Rada", "Human Gate", etc.
11. **RODO_COMPLIANCE.md** — document data flows, audit log retention policy, key storage rationale
12. **ADR-003-v590-scope.md** — what this release addresses, what was deferred from v5.8.9
13. **ADR-INDEX.md** — index of all ADRs in `docs/adr/`
14. **TEST_INVENTORY.md** — single document mapping all test files to test counts to what they cover
15. **COMPATIBILITY_MATRIX.md** — Python version, OS, key dependency versions tested

---

## Verdict

**Architecture inconsistencies: 4 (2 HIGH, 2 MEDIUM)**
**Integration gaps: 4 (1 HIGH, 2 MEDIUM, 1 LOW)**
**New documents for v5.9.0: 15 identified (3 critical, 6 high, 6 recommended)**
**Total findings: 8 inconsistencies + 15 planned docs**
