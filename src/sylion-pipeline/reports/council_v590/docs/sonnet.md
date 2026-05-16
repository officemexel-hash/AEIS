# SYLION v5.9.0 Doc Analysis — Analyst: Claude Sonnet 4.6
**Role:** Technical Writer / Cross-Reference Specialist
**Scope:** Terminological consistency, internal cross-references, feature claims accuracy, style

---

## Classification: TECHNICAL

All 6 documents are TECHNICAL (changelogs, status reports, implementation tracker, architecture overview). No user-facing or marketing material detected.

---

## Cross-File Terminological Consistency Audit

### Term: "agents" count

| File | Claimed Count | Context |
|---|---|---|
| README.md header | 47 | "47 agentów AI" |
| README.md agents table | 47 rows listed (11-15 as range, 16-19 as range, etc.) | Actual distinct entries = 38 rows in table; ranges 11-15, 16-19, 34-37, 40-43, 44-46 each count as multi |
| PIPELINE_IMPLEMENTATION_STATUS.md | 47 total | "Agents (agents.yaml): 47" |
| STREAMING_IMPLEMENTATION_STATUS.md | 47 agents, 10 streaming | agents.yaml validation |
| CHANGELOG_v5.8.8.md Bug 3 | "48-agent fallback" | Pre-fix fallback list |
| CHANGELOG_v5.8.8.md Finding C | "agents.yaml defaultuje enabled=true dla wszystkich 48" | Note: says 48 |
| CHANGELOG_v5.8.8.1.md Finding C | "agents.yaml defaultuje enabled=true dla wszystkich 48" | Same: 48 |

**INC-T01 (MEDIUM): 47 vs 48 discrepancy**
- agents.yaml canonical count = 47 (PIPELINE_STATUS, README header)
- But CHANGELOG_v5.8.8.md Finding C description says "48 agentów" as the fallback AND "agents.yaml defaultuje enabled=true dla wszystkich 48"
- This is contradictory: if canonical is 47, why does YAML default 48 enabled agents?
- Possible root cause: 48 was old count, one agent removed/merged, docs not fully updated
- REPORT.md: "48-agent fallback" (Bug 3 context) — confirmed

### Term: "council models"

| File | Models Referenced | Version strings |
|---|---|---|
| CHANGELOG_v5.8.8.md | Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro | Specific versions |
| README.md agent table | claude-opus, claude-sonnet, claude-haiku, gpt-5, gemini-pro | Generic names |
| PIPELINE_STATUS | claude-opus, claude-sonnet, gpt-5, gemini-pro, deepseek-v3, grok-3 | Generic names |

**INC-T02 (LOW): Model versioning inconsistency**
- CHANGELOG uses precise version identifiers (Opus 4.7 etc.)
- Status files use generic identifiers (claude-opus)
- In v5.9.0, a MODEL_VERSIONS.md or agents.yaml section should lock model versions

### Term: "port"

| File | Port | Context |
|---|---|---|
| CHANGELOG_v5.8.8.md Bug 6 | 8420→8421 (fix) | Default port changed |
| README.md orchestrator example | 8420 | "Dashboard: http://localhost:8420" — STALE |
| README.md dashboard section | 8421 | `--port 8421` startup |
| REPORT.md | 18422 | "HTTP 200 na porcie 18422" |
| CHANGELOG_v5.8.8.1.md | N/A | No port mentioned |

**INC-T03 (HIGH): THREE different port numbers appear — 8420 (stale), 8421 (correct fix), 18422 (test override)**
README orchestrator section retains pre-fix 8420 reference. This directly contradicts Bug 6 fix.

### Term: "tests passing"

| File | Test count | Suite |
|---|---|---|
| CHANGELOG_v5.8.8.md | 9/9 | tests/test_regressions_v588.py |
| CHANGELOG_v5.8.8.1.md | 15/15 + 73/73 E2E | test_regressions + test_concurrency + E2E |
| README.md | 262 | Full suite (6 files) |
| STREAMING_IMPL_STATUS.md | 193/193 | Streaming-specific suite |
| REPORT.md | 9/9 | Same regression file |

**INC-T04 (MEDIUM): No document explains the relationship between these counts**
- 9 (v5.8.8 regression) ⊂ 15 (v5.8.8.1 extended regression) ⊂ 193 (streaming suite) ⊂ 262 (full suite)
- None of these numbers are contradictory per se, but there is zero cross-referencing
- A reader cannot understand the hierarchy without reading all 6 docs simultaneously

### Term: "safety layers"

| File | Count | Items |
|---|---|---|
| README.md | 8 numbered sections | Supervisor, BookGuardian, BudgetGuard, Human Gate, Safe Runner, Anti-Hallucination, Loop Guard, Context Persistence |
| PIPELINE_STATUS.md | 5 "Safety layers" | Supervisor+Human Gate, BookGuardian, BudgetGuard, LoopGuard (missing Context Persistence) |
| PIPELINE_STATUS.md | 5 "Anti-hallucination layers" | Separate count |

**INC-T05 (MEDIUM): Safety layer count inconsistency**
- README lists 8 protection mechanisms
- PIPELINE_STATUS splits into "5 safety + 5 anti-hallucination" = 10 distinct items
- README's sections 7 (Loop Guard) and 8 (Context Persistence) aren't in the Safety table
- README anti-hallucination (section 6) refers to Layer 1 + mentions 6 hallucination types, STREAMING_STATUS lists 5 layers
- No document reconciles these taxonomies

---

## Feature Claims Accuracy

### Claim: "Zero external dependencies for dashboard_server.py"
- README.md line 172-174: "serwer HTTP na stdlib (zero zewnętrznych zależności)"
- BUT: dashboard section lists `pip install -r dashboard/requirements.txt` (line 287)
- CHANGELOG_v5.8.8.1.md: "Stack: FastAPI + SQLite + vanilla HTML/JS/CSS"
- **INC-T06 (HIGH): README contradicts itself** — "zero zewnętrznych zależności" is FALSE; dashboard uses FastAPI which is an external dependency. Line 172 refers to `dashboard_server.py` (possibly an older embedded HTTP server?), while the actual deployed dashboard uses FastAPI (`dashboard/start.py`). This distinction is never explained.

### Claim: "HARD GATE" stages
- PIPELINE_STATUS: 2 hard gates (6.5 and 7.5)
- README pipeline diagram: correctly shows 2 hard gates
- STREAMING_STATUS: also 2 hard gates
- ✅ Consistent across files

### Claim: Security (CVE 30, zero eval/exec/pickle)
- CHANGELOG_v5.8.8.md and REPORT.md both state: 30 CVE, 0 eval, 0 exec, 0 pickle
- ✅ Consistent across files

---

## Style and Format Issues

**INC-T07 (LOW): Language mixing**
- PIPELINE_STATUS.md and STREAMING_STATUS.md are in English
- CHANGELOG files, README, REPORT are in Polish
- In v5.9.0, a language policy should be established (recommend: headers/interfaces in English, narrative in Polish per existing convention)

**INC-T08 (LOW): Date format**
- CHANGELOG_v5.8.8.md: `**Data:** 2026-04-18` (bold MD field)
- CHANGELOG_v5.8.8.1.md: `Data wydania: 2026-04-18` (plain text)
- Status files: `Last updated: 2026-04-11`
- Should standardize to ISO 8601 with consistent label

**INC-T09 (LOW): "Pion D" never defined in README or STATUS files**
- Used in README ("Pion D streaming stack"), PIPELINE_STATUS ("STREAMING" stage), STREAMING_STATUS title
- No glossary entry explaining what "Pion D" means
- New users/reviewers cannot understand the term

---

## Missing Content (Gaps for v5.9.0)

**MISS-01:** No GLOSSARY.md — terms like "Pion D", "Strażnik Księgi", "Rada" are not defined outside their first use.

**MISS-02:** No CONTRIBUTING.md or DEVELOPER_GUIDE.md — how does a new developer add a new agent?

**MISS-03:** No explicit CHANGELOG format standard — v5.8.8 uses custom format, v5.8.8.1 uses "Keep a Changelog 1.1.0" — these should be unified.

**MISS-04:** No `docs/adr/` index — ADR-001 and ADR-002 are referenced but no ADR-INDEX.md exists.

**MISS-05:** No cross-version compatibility matrix — which versions of Python, litellm, FastAPI are supported/tested?

**MISS-06:** The REPORT.md references `/home/user/workspace/council/round-prerelease-*.md` files — these are local paths and the files may not be in the distribution ZIP.

---

## Verdict

**9 terminological/style inconsistencies (1 HIGH, 4 MEDIUM, 4 LOW)**
**6 content gaps identified for v5.9.0**
Total: 15 findings
