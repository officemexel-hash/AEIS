---
name: aeis-runtime-evidence-auditor
description: Use when verifying AEIS runtime truth through process startup, OpenAPI, frontend routes, dashboard behavior, logs, tests, and screenshots. This skill is for proving what is actually wired end-to-end, not what modules merely exist on disk.
---

# AEIS Runtime Evidence Auditor

Use this skill after the first inventory pass and before declaring any module `LIVE_VERIFIED`.

## Goals

- Confirm backend, frontend, and operator surfaces in runtime.
- Distinguish code-backed modules from live end-to-end flows.
- Collect evidence for API, UI, logs, and screenshots.
- Verify or falsify claims from `docs/claude_system_audit/`.

## Workflow

1. Inspect startup entrypoints and environment defaults.
2. Start backend and frontend from repo-native scripts unless they are already running and healthy.
3. Capture:
   - `/health`
   - `/openapi.json`
   - critical route availability
   - frontend route rendering
   - operator/dashboard screenshots
4. Map runtime evidence back to inventory rows:
   - API exists only in code
   - API responds in runtime
   - frontend route exists only in filesystem
   - frontend route renders and loads data
5. Run focused tests when they validate a concrete claim. Avoid blind full-suite runs until critical flows are identified.

## Required Evidence

- startup command or script path
- effective ports
- health response
- OpenAPI dump or endpoint list
- frontend route proof
- screenshot proof for dashboard/operator pages
- logs for failing subsystems

## Classification Rules

- `LIVE_VERIFIED`: code exists and runtime proof exists.
- `PARTIAL`: code exists and some runtime proof exists, but flow is incomplete.
- `API_ONLY`: route responds but no corresponding UI or end-to-end surface.
- `UI_ONLY`: page exists without live backend support.
- `BROKEN`: code exists but runtime contradicts the intended flow.

## Cross-check Rules

- If Claude marked a module live, demand runtime proof.
- If Claude marked a module missing, but runtime or API disproves that, record a disagreement with evidence.
