# AEIS clean install release

This document defines how to produce an installable AEIS package for a new
machine with no runtime data.

## Build package

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_clean_install.ps1
```

Output:

- `dist/aeis-clean-install-<timestamp>/aeis`
- `dist/aeis-clean-install-<timestamp>.zip`
- `dist/aeis-clean-install-<timestamp>/CLEAN_INSTALL_MANIFEST.json`

## What is included

- Source code under `src/`
- Documentation under `docs/`, excluding audit/draft/runtime reports
- Infra, manifests, operator-mobile, scripts, tools and tests
- Generated first-run scripts:
  - `install_clean.ps1`
  - `start_clean.ps1`
  - `verify_clean.ps1`
  - `FIRST_RUN_CLEAN.md`

## What is excluded

- `.env`, `.env.local`, `.env.generated`
- SQLite/DB files
- Logs
- JSONL runtime streams
- Evidence, audit screenshots, generated projects and outputs
- `node_modules`, `.venv`, `.next`, Playwright results and caches
- Local agent worktrees and local tool caches

## Guards

The builder fails if the output contains:

- DB/runtime files such as `*.db`, `*.sqlite`, `*.log`, `*.pid`, `*.jsonl`
- `node_modules`, `.next`, `test-results`, `playwright-report`
- Common real API-key patterns for OpenAI, Anthropic, Perplexity, OpenRouter,
  Kimi and Google Gemini

## First run on a clean machine

Unzip the package, open PowerShell in the `aeis` folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\verify_clean.ps1 -PackageMode
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install_clean.ps1
powershell -ExecutionPolicy Bypass -File .\start_clean.ps1
```

Then open:

```text
http://localhost:3000/onboarding
```

The first-run installer creates runtime directories and generates local
secrets in `.env.generated`. It does not ship any operator data.
