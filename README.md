# SYLION Pipeline v6.2.0 — Release Package

**Codename**: Breakthrough — 18 Skills Audit  
**Build date**: 2026-04-19  
**Poprzednik**: v6.0.0 (baseline fix-plan)  
**Nagrywany w**: `sylion-pipeline-6.2.0-<ts>.zip`

## Co zawiera ta paczka

Pełne źródła SYLION Pipeline v6.2.0 z naprawionymi 17 bugami z `SYLION-v600-FIX-PLAN.pdf`:
bezpieczeństwo (JWT/metrics/litellm), stabilność (graceful shutdown, async cancel), spójność (DB_PATH, version), performance (BookGuardian 676× szybszy), RESTful cleanup (`/api/human-gate/*` canonical dash-case z deprecation window dla legacy underscore do 2026-12-31).

## Szybki start

1. Rozpakuj: `unzip sylion-pipeline-6.2.0-*.zip -d sylion-6.2.0`
2. `cd sylion-6.2.0`
3. Instalacja:
   - Linux/Mac: `./scripts/install.sh`
   - Windows: `scripts\install.bat`
4. Weryfikacja: `./scripts/verify.sh`
5. Start serwera (dev): zobacz `INSTALL.md` sekcja "Uruchomienie lokalne"

## Wymagania

- Python 3.11+
- SQLite 3.35+ (wbudowany w Python)
- Dostępny port `8422` (lub ustaw `SYLION_PORT`)
- Opcjonalnie: Ollama @ localhost lub w Dockerze jako `ollama:11434`

## Struktura paczki

```
sylion-pipeline-6.2.0/
├── README.md                # ten plik
├── CHANGELOG.md             # Keep-a-Changelog v6.0.0 → v6.2.0
├── INSTALL.md               # instalacja krok po kroku
├── ROLLBACK.md              # cofnięcie do v6.0.0
├── SKILL_MANIFEST.md        # checklist-enforcer POST-TASK
├── MANIFEST.json            # metadata paczki
├── CHECKSUMS.sha256         # hashe wszystkich plików
├── VERSION                  # "6.2.0"
├── src/sylion-pipeline/     # pełne źródła (Python)
├── evidence/                # dowody PASS dla 17 bugów (fazaA..fazaF)
├── ULTRA_TEST_REPORT_v2.md  # raport PASS/FAIL + delta pytest
└── scripts/                 # install.sh/.bat/.ps1 + rollback.sh + verify.sh
```

## Dokumentacja szczegółowa

- [CHANGELOG.md](./CHANGELOG.md) — 17 bugów z podziałem Added/Changed/Fixed/Deprecated/Security
- [ULTRA_TEST_REPORT_v2.md](./ULTRA_TEST_REPORT_v2.md) — pełny raport testów
- [INSTALL.md](./INSTALL.md) — pre-requisites + troubleshooting
- [ROLLBACK.md](./ROLLBACK.md) — jak cofnąć do v6.0.0
- [SKILL_MANIFEST.md](./SKILL_MANIFEST.md) — wykaz użytych skilli

## Status 17 bugów

**17/17 PASS.** Zero regresji. Evidence w `evidence/faza{A,B,C,D,E,F}/`.

Szczegół: [ULTRA_TEST_REPORT_v2.md](./ULTRA_TEST_REPORT_v2.md).

## Wsparcie

- Endpoint health: `GET /api/health` → `{"status":"ok","version":"6.2.0"}`
- Endpoint version: `GET /api/version`
- Metrics (localhost lub bearer): `GET /api/metrics`
- Logi: domyślnie `/tmp/sylion.log` lub `SYLION_LOG_PATH`

## Licencja

Własność SYLION / RSDG GmbH. Wszelkie prawa zastrzeżone. Projekty wewnętrzne.
