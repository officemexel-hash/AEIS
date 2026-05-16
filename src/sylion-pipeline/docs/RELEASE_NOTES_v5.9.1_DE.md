# SYLION v5.9.1 — Hardening Patch (Versionshinweise, DE)

**Veröffentlichungsdatum:** 2026-04-19
**Codename:** *Hardening Patch*
**Release-Typ:** PATCH (SemVer 5.9.0 → 5.9.1)
**Vorgängerversion:** v5.9.0 (*Breakthrough — 18 Skills Audit*, 2026-04-18)
**Charakter:** ausschließlich Bugfix + Sicherheitshärtung.
**Keine API-Änderungen. Keine Breaking Changes.**

> **Hinweis für RSDG GmbH:** Diese Veröffentlichung betrifft ausschließlich technische
> Härtung. Keine Änderungen an HGB/GoBD-Retention oder DSGVO-Verarbeitung.

Die originalen Release Notes für v5.9.1 wurden in snapshot_0052 archiviert und
gemäß Lücke Nr. 5 (identifiziert in audit_LATEST/18_user_manual.md) in die
LATEST-Dokumentation übertragen.

---

## Zusammenfassung

v5.9.1 ist ein Patch-Release nach dem Audit durch den Rat der 4 Modelle
(Opus 4.7 / Sonnet 4.6 / GPT-5.4 / Gemini 3.1 Pro) sowie 14 Domain-Skills
(insgesamt 18 Berichte). Der Audit identifizierte 33 Findings in v5.9.0 —
v5.9.1 behebt **13 davon**, inklusive aller BLOCKER-Findings bis auf einen
bewusst zurückgestellten (F-001).

**Wenn Sie v5.9.0 verwenden — sofortiges Upgrade auf v5.9.1 wird empfohlen.**

---

## Sicherheits-Fixes

### F-002 (HIGH) — Rate Limiter Login hinter Reverse-Proxy umgangen

In v5.9.0 startete uvicorn ohne `--proxy-headers`. Hinter Caddy sah der Rate
Limiter als Client-IP nur `127.0.0.1`. Ergebnis: Ein blockierter Angreifer
sperrte alle legitimen Benutzer für 5 Minuten aus.

**Fix:** uvicorn startet jetzt mit `proxy_headers=True, forwarded_allow_ips="127.0.0.1"`.
Neue Variable `SYLION_FORWARDED_ALLOW_IPS` für erweiterte Proxy-Liste (z. B. Cloudflare).
Vollständiges Caddyfile-Beispiel: `docs/RUNBOOK_DEPLOY.md §3.5`.

### F-010 (HIGH) — Stummer Fallback Argon2id → SHA-256

Wenn `argon2-cffi` fehlte, wechselte der Hashing-Backend stillschweigend auf SHA-256.
Der Operator wusste nicht von der Schwachstelle.

**Fix:** `RuntimeError("Argon2id backend required")` — kein Fallback.
`argon2-cffi>=23.1.0` ist jetzt eine HARTE Abhängigkeit.

### F-015 (MEDIUM) — `SESSION_COOKIE_SECURE` standardmäßig deaktiviert

Fail-Open: Session-Cookies wurden über HTTP übertragen. In Kombination mit F-002
ein Session-Hijacking-Vektor.

**Fix:** Standardwert `SESSION_COOKIE_SECURE = "1"`. Opt-Out nur über
`SESSION_COOKIE_SECURE=0` (z. B. für lokale Tests).

### F-009 (MEDIUM) — `assert` auf SQL-Pfaden in Ollama-Shadow-Queries

`assert column in ALLOWED_COLUMNS` wurde durch `python -O` entfernt → SQL-Injection möglich.

**Fix:** Ersetzt durch `if column not in ALLOWED_COLUMNS: raise ValueError(...)`.

### F-019 (MEDIUM) — Fehlender Index `idx_sessions_expires_at`

Scheduled Job `cleanup_expired_sessions()` führte alle 60 Sekunden einen Full-Table-Scan durch.

**Fix:** Neue Migration 1→2, Index wird automatisch beim Start hinzugefügt.
`_DB_TARGET_VERSION = 2`.

### F-026 (LOW) — Stille Exception-Unterdrückung in `config.py`

4× `except Exception: pass` verbargen Initialisierungsfehler.

**Fix:** Eingegrenzt auf `except (sqlite3.Error, OSError)` + Warn-Log.

---

## Operative Fixes (SRE / Deploy)

### F-004, F-005, F-006 (HIGH) — Komplette Neufassung von rollback.sh

Alter Skript: DB-Korruption durch WAL, falscher Backup-Pfad, fehlende Integritätsprüfung.

**Fix (327 Zeilen, zuvor 261):**
- Staged Restore — `PRAGMA integrity_check` VOR Überschreibung der Produktionsdatenbank.
- WAL/SHM-Handling.
- Suche in: `$HOME/sylion/backups/`, `./backups/`, `/var/backups/sylion/`.
- Neuer `--dry-run`-Modus.
- Exit-Codes: 0=Erfolg, 1=kein Backup, 2=Integrity-Check fehlgeschlagen, 3=keine Rechte.

### F-007 (MEDIUM) — Falscher Entry Point in Runbooks

9 Stellen `app.main:app` → korrigiert auf `dashboard.app:app` in `RUNBOOK_DEPLOY.md`.

### F-008 (MEDIUM) — `INCIDENT_RESPONSE.md` verwendete nginx statt Caddy

Vollständige Neufassung des Abschnitts „Reverse Proxy" — Caddy-Diagnose, Port 8421,
`/api/health`, korrekter Pfad `/var/log/caddy/`.

### F-016, F-023 (LOW) — Inkonsistente Python-Versionen in der Dokumentation

Python 3.12 ist jetzt als Mindestanforderung in ALLEN Dokumenten vereinheitlicht
(nicht mehr 3.11+).

---

## Dokumentations-Fixes

| ID | Fix |
|----|-----|
| F-003 | Frühere „halluzinierte" Release Notes v5.9.0 durch verifizierten Bericht ersetzt. |
| F-017 | `QUICKSTART_DE.md` warnt explizit vor `your-org/sylion.git`-Placeholder. |
| F-018 | Rechtschreibfehler: „Datenbanksperfehler" → „Datenbanksperrfehler" in `FAQ_DE.md`. |
| F-025 | Falsche Testnamen in `CHANGELOG_v5.9.0.md` auf tatsächlich vorhandene Dateien korrigiert. |
| F-022 | `.github/workflows/validate-manifest.yml` entfernt (verletzte Constraint C-103). |

---

## Abhängigkeits-Updates (CVE-Patch-Ebene)

| Paket | v5.9.0 | v5.9.1 | Begründung |
|-------|--------|--------|------------|
| `starlette` | `0.46.2` | `0.47.2` | Path Traversal in `StaticFiles` |
| `python-multipart` | `0.0.20` | `0.0.21` | DoS via malformed multipart boundary |
| `pypdf` | `5.4.0` | `5.5.0` | Infinite Loop in `EncodedStreamObject` |

Lockfile `requirements-lock.txt` aktualisiert, Prüfsummen erneuert.

---

## NICHT behoben (bewusste Zurückstellungen)

### F-001 — Hartcodierte API-Keys in `dashboard/db.py:1081-1086` (CRITICAL)

Keys wurden vom Operator noch nicht rotiert — verschoben auf v5.9.2.

**PFLICHT VOR DEPLOYMENT:**
1. Alle 4 Keys rotieren (OpenAI, Anthropic, Perplexity, Google).
2. Ausschließlich über `.env` konfigurieren.
3. Verifizieren: `grep -n "sk-" dashboard/db.py` — Ausgabe muss leer sein.

### F-011, F-013 (LOW)

Geringfügige Inkonsistenzen in `DISASTER_RECOVERY.md` — auf v5.9.2 verschoben.

---

## Upgrade von v5.9.0 auf v5.9.1

```bash
# 1. DB-Backup VOR dem Upgrade
sqlite3 ~/sylion/sylion.db \
  ".backup '~/sylion/backups/sylion-pre-v591-$(date +%Y%m%d-%H%M%S).db.bak'"

# 2. Service stoppen
sudo systemctl stop sylion

# 3. v5.9.1 einspielen
rsync -a --delete /tmp/sylion-v591/sylion-pipeline/ /opt/sylion/sylion-pipeline/

# 4. Abhängigkeiten aktualisieren (argon2-cffi ist jetzt Pflicht!)
pip install -r requirements-lock.txt --upgrade

# 5. API-Keys rotieren — KRITISCH (F-001)

# 6. Caddyfile aktualisieren (RUNBOOK_DEPLOY.md §3.5.2)
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy

# 7. Service starten
sudo systemctl start sylion

# 8. Verifizierung: 6 Login-Versuche → 5× 401 + 1× 429 erwartet
```

### Rollback

```bash
sudo systemctl stop sylion
./rollback.sh --dry-run   # Vorschau
./rollback.sh             # Ausführung
sudo systemctl start sylion
```

---

## Compliance

- **DSGVO/RODO:** Keine Änderungen an der Verarbeitung personenbezogener Daten.
- **KSeF / JPK (PL):** Keine Änderungen an Rechnungsmodulen.
- **HGB / GoBD:** Keine Änderungen an audit_log-Retention (10 Jahre).
- **Cross-border PL↔DE:** Keine Änderungen an SCC / Transferpreisen.

Vollständiger Audit-Trail: `docs/council-reports/FIX_MAP_v5.9.1.md`

---

## Kontakt

Issues / Bugs: `${SYLION_ONCALL_CONTACT}`
Dokumentation: `docs/` im Installationsverzeichnis
Key-Rotation (F-001): vor dem Deployment ausführen — `docs/ROLLBACK_PLAN.md`
