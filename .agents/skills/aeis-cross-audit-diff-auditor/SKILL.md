---
name: "aeis-cross-audit-diff-auditor"
description: "Porownuje ustalenia Codex i Claude dla AEIS. Szuka ostrych roznic w klasyfikacji, brakach runtime, statusach memory/skills/funding/mobile i tworzy liste korekt lub potwierdzen."
---

# AEIS Cross Audit Diff Auditor

Uzyj tego skillu przy pracy na:

- `docs/claude_system_audit/*`
- `docs/codex_system_audit/CODEX_AEIS_CANON_VS_REALITY.md`
- `docs/codex_system_audit/CODEX_AEIS_REPAIR_BACKLOG.md`

## Cel

Nie powielac bezkrytycznie audytu Claude'a. Zamiast tego:

- odnotowac miejsca, gdzie Claude byl trafny
- odnotowac miejsca, gdzie Claude niedoszacowal implementacji
- odnotowac miejsca, gdzie runtime probe Codex wykryl realny bug lub split

## Obszary priorytetowe

- memory
- skills
- workspace
- funding
- operator console
- mobile
- governance / Human Gate
- council / autonomy

## Wynik

Kazda roznica ma byc sklasyfikowana jako jedno z:

- `CLAUDE_UNDERCALL`
- `CLAUDE_OVERCALL`
- `CLAUDE_CONFIRMED`
- `BOTH_UNCERTAIN`

## Zasada

Dowod wygrywa z interpretacja:

`kod > runtime > API > UI > testy > dokumentacja > inny audit`

