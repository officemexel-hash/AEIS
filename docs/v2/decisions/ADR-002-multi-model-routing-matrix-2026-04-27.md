# ADR-002: Multi-Model Routing Matrix (2026-04-27)

> **Status**: ACCEPTED
> **Date**: 2026-04-27
> **Decision-maker**: Robert (operator/founder, founder rank 5)
> **Scope**: SYLION AEIS v2 cron orchestrator — backend model selection per task type
> **Supersedes**: ad-hoc agent dispatch in `MAIN_TASK_v2.md` "Aktywne subagenty CLI" table; resolves Q-NEW-OPS-MULTI-MODEL.
> **Author of record**: cron orchestrator round 2026-04-27 (operator chose "Option A" — different model backends for different task types; verbatim emphasis: "uzywaj wiecej ollama jest darmowa, proste rzeczy zrobi").
> **Companion**: [ADR-001](ADR-001-five-architectural-decisions-2026-04-27.md) (architectural fork-points — same operator round).

## Table of contents

1. [Executive summary](#executive-summary)
2. [Context](#context)
3. [Decision — routing matrix per task type](#decision--routing-matrix-per-task-type)
4. [Operational notes](#operational-notes)
5. [Guidelines for cron operator](#guidelines-for-cron-operator)
6. [Consequences](#consequences)
7. [Cross-references](#cross-references)

---

## Executive summary

On 2026-04-27 the operator (Robert) chose **Option A** for cron-orchestrator
backend strategy: instead of routing every cron task to Claude bg agents, the
orchestrator picks the cheapest-adequate backend per task type. The operator
emphasized "uzywaj wiecej ollama jest darmowa, proste rzeczy zrobi" — i.e.
ollama is free and handles simple tasks, so prefer it for low-stakes work and
reserve Claude bg for the cases that genuinely require atomic multi-file
commits and full tool loops. This ADR locks the routing matrix, captures the
operational quirks of each backend (encoding crashes, ANSI escape codes, stdin
behavior in bg subprocess mode, token cost), and dispatches the matrix as the
default policy for subsequent cron rounds.

---

## Context

The cron orchestrator has access to four CLI/agent backends, each with a
different cost/latency/quality/reliability profile. Routing every task to the
strongest (Claude bg) backend wastes paid tokens on work that a local model
handles fine; routing every task to the cheapest (ollama) backend produces low-
quality output for tasks that need multi-file context or atomic commits. The
four backends:

- **Claude bg agent** (Anthropic cloud) — full agent loop with tool access
  (Read/Edit/Bash/Grep/Glob), self-commits, atomic file operations,
  ~10 min per task. Token cost: real $.
- **Codex `exec`** (OpenAI cloud) — non-interactive code generation. Subagent
  mode also writes files via tools. Stdin pipe works for synchronous use; bg
  subprocess `&` doesn't capture output reliably. Token cost: real $.
- **Kimi `-p`** (Moonshot cloud, CN) — print mode. **WARNING**: cp1250
  encoding crash @ ~26 KB on Polish output (documented in
  `KIMI_REVIEW_W18_*_PARTIAL.md` files). Use only for SHORT English output or
  tightly-bounded prompts. Token cost: free tier so far.
- **Ollama lokalny** (gpt-oss:20b, qwen2.5:7b-instruct, qwen3.5:latest,
  qwen2.5:0.5b) — local GPU/CPU. ZERO cost. Latency 30-180s per call. Output
  has terminal escape codes (need `OLLAMA_NOSPINNER=1` env + ANSI strip via
  sed). "Thinking..." preamble must be skipped.

Without an explicit routing policy the orchestrator defaults to "use Claude bg
for everything", which (a) burns paid tokens on trivial work, (b) under-uses
the local GPU, and (c) leaves kimi's free tier on the table.

---

## Decision — routing matrix per task type

**Operator decision verbatim**:

> Use Option A: route per task type. "uzywaj wiecej ollama jest darmowa,
> proste rzeczy zrobi" — use ollama more, it's free, can handle simple tasks.

The matrix below is the canonical mapping. Primary = first-choice backend;
fallback = used when primary is unavailable, output is rejected, or task
exceeds the primary's safe envelope (e.g. kimi >20 KB Polish output).

| Task type | Primary | Fallback | Why |
|---|---|---|---|
| Code w/ self-commit | Claude bg | (manual) | tool loop + atomic commit |
| Adversarial code review | Kimi -p | Claude bg | free tier; PL crash known — keep prompts in EN |
| Doc writing/translation PL | ollama gpt-oss:20b | Claude bg | local, free, mocny w PL |
| Test stub generation | ollama gpt-oss:20b | codex exec | local iteration cheap |
| Demo data YAML | ollama gpt-oss:20b | (manual) | structured output OK |
| Single-function code gen | codex exec | ollama qwen2.5:7b | sync stdin works |
| Architecture decisions | Claude bg (orchestrator) | — | requires multi-file context |
| FAQ/help text | ollama gpt-oss:20b | — | natural PL output |

The matrix is **not exhaustive** — task types not listed default to Claude bg
with a one-line rationale captured in `_cron_log.md`. New task types added to
the matrix in subsequent ADRs.

---

## Operational notes

Each backend has documented quirks that the cron orchestrator must handle to
avoid silent failure modes:

### Ollama post-processing

- Always strip `\x1b\[...]` ANSI escape codes via `sed` (terminal spinner
  output otherwise leaks into committed files).
- Skip the model's "Thinking..." preamble using
  `sed -n '/done thinking/,$p'` — the gpt-oss:20b reasoning preamble must
  not be persisted as content.
- Set `OLLAMA_NOSPINNER=1` env var to suppress the spinner at the source.
- Latency 30-180s is normal — don't time out aggressively.

### Codex bg subprocess

- `&` mode loses stdin — output capture is unreliable when invoked as a
  background subprocess.
- **Fix**: use synchronous bash invocation, OR write the prompt to a file
  and redirect (`codex exec < /tmp/prompt.txt > /tmp/out.txt`).
- Subagent mode (codex writing files via its own tools) is the cleanest
  path when output >a few KB.

### Kimi encoding

- cp1250 encoding crash at ~26 KB threshold on **Polish** output (multiple
  partial-output review files are evidence:
  `KIMI_REVIEW_W18_*_PARTIAL.md`).
- **Mitigation**: keep kimi prompts and outputs **English-only**, OR cap
  expected output at <20 KB to stay under the crash threshold.
- Adversarial review of EN code (test files, English doc-strings, error
  messages) is the safe sweet spot.

### Claude bg quotas

- Token cost is real $ — prefer ollama for low-stakes work (test stubs, doc
  translation, demo data generation, FAQ text).
- Reserve Claude bg for tasks that genuinely need multi-file context, atomic
  commit semantics, or the full tool loop (Read/Edit/Bash/Grep/Glob with
  side-effect rollback).

---

## Guidelines for cron operator

The operator's "uzywaj wiecej ollama" directive translates into four
practical guidelines for the cron orchestrator's dispatch logic:

1. **Generate "easy stuff" on ollama batches of 10+ in parallel.** Test stubs,
   doc translation, demo data YAML, FAQ entries — these are well within
   gpt-oss:20b's capability and the marginal token cost is zero. Batch them
   wide rather than serializing through Claude bg.
2. **Use Claude bg only when atomic commit + multi-file edits required.**
   Anything that needs `Read → Edit → Bash → git add → git commit` in one
   transaction belongs to Claude bg. Single-file output can usually be
   delegated.
3. **Use codex when single-function code gen with sync output is needed.**
   The synchronous stdin pipe is reliable; the output is small enough to
   round-trip through the orchestrator and commit from there. Avoid the
   bg subprocess mode (`&`) — output capture breaks.
4. **Use kimi for short adversarial reviews of EN code only.** Free-tier
   tokens are valuable, but only for tasks that fit kimi's safe envelope:
   English-only, <20 KB output, narrow review prompts (security, edge cases,
   alternative implementations).

---

## Consequences

**Positive**:

- **Lower token spend on Anthropic.** The largest consumer of paid tokens
  (Claude bg) is reserved for tasks that need its full tool loop. Trivial
  tasks shift to ollama (zero cost) or kimi (free tier).
- **Visible local GPU/CPU activity.** The Ollama models on the workstation
  start carrying real load instead of sitting idle. Latency 30-180s per call
  is acceptable for batched cron work.
- **Free tier extracted on kimi.** Adversarial review of EN code lands on
  kimi where it can run without burning paid tokens.

**Negative**:

- **Some quality variability with ollama needs supervision.** gpt-oss:20b is
  strong in Polish doc generation but produces occasional structural drift on
  YAML/test-stub generation. The orchestrator must validate ollama output
  (lint, schema check, smoke test) before committing.
- **Routing matrix must be maintained.** New task types arrive over time;
  this ADR captures the v1 matrix and subsequent ADRs (or a living index)
  must extend it as scope grows.
- **Operator must triage matrix mismatches.** When primary fails and fallback
  also fails, the cron orchestrator escalates to the operator — this is a new
  failure mode that did not exist in the "always Claude bg" baseline.

---

## Cross-references

| Topic | Where |
|---|---|
| ADR-001 (operator decisions on architecture) | [`ADR-001-five-architectural-decisions-2026-04-27.md`](ADR-001-five-architectural-decisions-2026-04-27.md) |
| Cron progress + matrix dispatch trail | `docs/v2/_cron_log.md` (managed by main agent) |
| Active subagent CLI inventory (pre-matrix baseline) | [`docs/v2/MAIN_TASK_v2.md`](../MAIN_TASK_v2.md) §"Aktywne subagenty CLI" |
| Open question resolved by this ADR | `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-OPS-MULTI-MODEL §8 |
| Kimi cp1250 crash evidence | `KIMI_REVIEW_W18_*_PARTIAL.md` files |

Linked memory entries:

- "SYLION user preferences" (auto-run tests, no verbal reports, continuous
  work, Windows encoding) — encoding constraints inform the kimi cp1250
  mitigation above.
- "Fix all errors inline" — applies to ollama-output validation: defects
  found post-generation are fixed inline, not parked.

---

*ADR-002 archived 2026-04-27 by cron orchestrator. Operator decision text is
verbatim ("uzywaj wiecej ollama jest darmowa, proste rzeczy zrobi"); routing
matrix and operational notes are editorial, derived from documented behavior
of each backend (kimi cp1250 crashes, codex bg stdin loss, ollama ANSI
output) observed during prior cron rounds.*
