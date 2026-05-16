# Council Report — Opus Model
## Artifact: RUNBOOK_DEPLOY.md

**Status:** COMPLETE  
**Generated:** 2025-07-11  
**Output path:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/docs/RUNBOOK_DEPLOY.md`  
**Size:** 10,070 bytes | 432 lines

---

## Artifact Summary

Full deployment runbook in Polish for SYLION v5.9.0 (SQLite + FastAPI).

### Sections delivered

| # | Section | Content |
|---|---------|---------|
| 1 | **Prerequisites** | Python 3.11+, pip 23+, venv, SQLite 3.35+, curl, disk/RAM minimums; install commands for Debian/Ubuntu, RHEL/Fedora, macOS, Windows |
| 2 | **Linux Installation** | ZIP extraction, chmod, `install.sh` invocation, systemd service setup with example `sylion.service` unit |
| 3 | **Windows Installation** | PowerShell/Explorer ZIP extraction, `install.bat` invocation, NSSM Windows service registration |
| 4 | **Healthcheck** | curl + PowerShell + curl.exe variants; expected JSON response; full endpoint table (`/api/health`, `/api/health/db`, `/api/agents`, `/api/version`) |
| 5 | **Top 10 Troubleshooting** | 10 issues with symptoms + multi-platform resolution steps |
| 6 | **Escalation** | L1/L2/L3 contacts and P1 incident SLA |

### Top 10 issues covered

1. `python: command not found`
2. Python version < 3.11
3. pip install failures (no internet / corporate proxy / private PyPI)
4. Permission denied on venv/directory
5. SQLite init_db failure / database locked
6. Port 8421 already in use
7. agents.yaml parse errors / encoding issues
8. FastAPI process hanging / no response
9. SSL/TLS certificate errors
10. requirements-lock.txt hash mismatch / version conflicts

### Quality notes

- All code blocks include OS-specific variants (Linux/macOS/Windows)
- systemd service unit template included for VPS deployment
- Troubleshooting commands are copy-pasteable with variable placeholders
- Consistent Polish language throughout (technical terms in English as standard)

---

## Compliance Checklist

| Requirement | Status |
|-------------|--------|
| Written in Polish | ✓ |
| Prerequisites section (Python 3.11+, pip, venv) | ✓ |
| Linux install steps with `install.sh` | ✓ |
| Windows install steps with `install.bat` | ✓ |
| Healthcheck after start | ✓ |
| Top 10 troubleshooting issues | ✓ (exactly 10) |
| Correct output path | ✓ |
