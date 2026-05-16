---
name: aeis-domain-surface-auditor
description: Use when auditing AEIS domain and operator surfaces: funding, mobile/operator, frontend routes, legacy dashboard, laboratory modules, device flows, and prompt-only planned components. Helps classify what is live, what is partial, and what is only planned.
---

# AEIS Domain Surface Auditor

Use this skill when the audit moves from core modules to domain-facing and operator-facing capabilities.

## Priority Surfaces

- Funding Autopilot
- Operator Console
- Operator Mobile or mobile-adjacent backend support
- frontend Next.js routes
- legacy dashboard
- laboratory modules (`cellular`, `sdr`, `vps`, `container`, `devices`)

## Workflow

1. Inspect code and routes for each surface.
2. Verify whether the surface has:
   - backend service
   - API routes
   - frontend route or UI
   - test coverage
   - runtime proof
3. Treat prompt-only assets as plan evidence, not implementation evidence.
4. For mobile:
   - search for code, scaffold, API hooks, token/device flows, push/deep-link hooks
   - if absent, classify as `PLANOWANY / NIEZAIMPLEMENTOWANY`
5. For funding:
   - confirm service/store/routes/schemas/config
   - map Human Gate boundaries around legally binding steps

## Classification Notes

- Funding is a first-class AEIS domain, not a sidecar.
- Mobile is a global operator surface, not a funding accessory.
- Laboratory modules are intentional extensions and must be described, not “cleaned up”.

## Output Targets

- `CODEX_AEIS_FUNCTIONAL_AUDIT.md`
- `CODEX_AEIS_API_UI_COVERAGE_MAP.md`
- `CODEX_AEIS_PRODUCTION_READINESS_MAP.md`
- `CODEX_AEIS_REPAIR_BACKLOG.md`
