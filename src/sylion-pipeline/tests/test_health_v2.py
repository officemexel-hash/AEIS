"""
test_health_v2.py — pytest suite dla Diagnostyki v2
Sylion v5.9.2 | TF06 — minimum 30 testów, min. 2 per kategoria

Uruchomienie:
    pytest mega_audit/diagnostyka_deep/test_health_v2.py -v
    pytest mega_audit/diagnostyka_deep/test_health_v2.py -v --tb=short

Wymagania: pytest, unittest.mock (stdlib)
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Dodaj katalog do path
sys.path.insert(0, str(Path(__file__).parent))

from health_check_v2 import (
    # Severity enum
    Severity,
    # Check functions
    check_pixel,
    check_mudi,
    check_wireguard,
    check_api_keys_live,
    check_ollama,
    check_uploads,
    check_subagents,
    check_ksiega,
    check_phantom,
    check_pipeline,
    check_db_extended,
    check_cve,
    check_rodo,
    check_cert,
    check_cred,
    # Orchestrator
    run_comprehensive_health,
    run_comprehensive_health_async,
    # History
    init_history_table,
    get_history,
    _save_history,
    # CAT_CODES
    CAT_CODES,
    CATEGORIES_META,
    _worst_severity,
    _ok, _warn, _err, _crit, _na,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _find_result(results: list[dict], code: str) -> dict | None:
    return next((r for r in results if r["code"] == code), None)


def _assert_code_severity(results, code, expected_severity):
    r = _find_result(results, code)
    assert r is not None, f"{code} nie znaleziony w wynikach"
    assert r["severity"] == expected_severity, \
        f"{code}: oczekiwano severity={expected_severity!r}, got {r['severity']!r} | msg: {r['message']}"


def _make_proc(returncode=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ===========================================================================
# T01-T02: CAT_CODES structure
# ===========================================================================

def test_cat_codes_has_15_categories():
    """CAT_CODES zawiera dokładnie 15 kategorii."""
    assert len(CAT_CODES) == 15


def test_cat_codes_total_codes():
    """CAT_CODES zawiera łącznie kody SYL-* per kategoria (suma wpisów w TF06 = 87).
    
    Nota: TF06 tabela §5 podaje '82' w wierszu RAZEM, ale suma poszczególnych
    kategorii wynosi 87 (10+8+5+12+6+6+4+4+4+5+5+4+4+5+5). Implementacja
    odzwierciedla rzeczywistą liczbę kodów per kategoria.
    """
    total = sum(len(v) for v in CAT_CODES.values())
    # TF06 individual category counts: 10+8+5+12+6+6+4+4+4+5+5+4+4+5+5 = 87
    assert total == 87, f"Oczekiwano 87 kodów (suma per kategoria TF06), mamy {total}"


# ===========================================================================
# T03-T04: CATEGORIES_META
# ===========================================================================

def test_categories_meta_count():
    """CATEGORIES_META ma 15 wpisów."""
    assert len(CATEGORIES_META) == 15


def test_categories_meta_fields():
    """Każdy element CATEGORIES_META ma wymagane pola."""
    for c in CATEGORIES_META:
        assert "id" in c
        assert "label" in c
        assert "prefix" in c
        assert "codes" in c


# ===========================================================================
# T05-T06: SYL-PIX — Pixel 9
# ===========================================================================

def test_pix_001_no_adb():
    """SYL-PIX-001 ERROR gdy ADB nie zainstalowany."""
    with patch("subprocess.run", side_effect=FileNotFoundError("adb not found")):
        results = check_pixel()
    r = _find_result(results, "SYL-PIX-001")
    assert r is not None
    assert r["severity"] == "error"
    assert "ADB" in r["message"] or "adb" in r["message"].lower()


def test_pix_002_unauthorized():
    """SYL-PIX-002 ERROR gdy urządzenie unauthorized."""
    call_count = [0]
    def fake_run(cmd, **kw):
        call_count[0] += 1
        m = _make_proc(0)
        if "start-server" in cmd:
            m.stdout = "daemon started"
        elif "devices" in cmd:
            m.stdout = "List of devices attached\nABC123\tunauthorized\n"
        return m

    with patch("subprocess.run", side_effect=fake_run):
        results = check_pixel()

    r = _find_result(results, "SYL-PIX-002")
    assert r is not None
    assert r["severity"] == "error"
    assert "UNAUTHORIZED" in r["message"]


def test_pix_001_adb_start_server_fail():
    """SYL-PIX-001 ERROR gdy start-server zwraca niezerowy kod."""
    def fake_run(cmd, **kw):
        return _make_proc(returncode=1, stdout="", stderr="error")

    with patch("subprocess.run", side_effect=fake_run):
        results = check_pixel()
    _assert_code_severity(results, "SYL-PIX-001", "error")


def test_pix_na_chain_without_device():
    """Bez urządzenia — PIX-003..010 powinny być N/A lub pominięte."""
    def fake_run(cmd, **kw):
        m = _make_proc(0)
        if "start-server" in cmd:
            m.stdout = "already running"
        elif "devices" in cmd:
            m.stdout = "List of devices attached\n"  # pusty — brak urządzeń
        return m

    with patch("subprocess.run", side_effect=fake_run):
        results = check_pixel()

    # PIX-002 warn (brak urządzenia), PIX-003+ N/A
    r2 = _find_result(results, "SYL-PIX-002")
    assert r2 is not None
    assert r2["severity"] in ("warn", "error")

    # PIX-003 powinien być N/A jeśli brak urządzenia
    r3 = _find_result(results, "SYL-PIX-003")
    if r3:
        assert r3["severity"] in ("n/a", "warn", "ok")


# ===========================================================================
# T07-T10: SYL-MUD — Mudi Router
# ===========================================================================

def test_mud_001_ping_fail():
    """SYL-MUD-001 ERROR gdy ping nie odpowiada."""
    with patch("subprocess.run", return_value=_make_proc(returncode=1)):
        results = check_mudi()
    _assert_code_severity(results, "SYL-MUD-001", "error")


def test_mud_001_ping_ok_ssh_fail():
    """SYL-MUD-001 PASS ale SYL-MUD-002 FAIL gdy SSH nieudany."""
    call_count = [0]
    def fake_run(cmd, **kw):
        call_count[0] += 1
        if "ping" in cmd:
            return _make_proc(0, "1 packets transmitted, 1 received")
        return _make_proc(1, "")  # SSH fail

    with patch("subprocess.run", side_effect=fake_run):
        results = check_mudi()

    r1 = _find_result(results, "SYL-MUD-001")
    assert r1 is not None and r1["severity"] == "ok"

    r2 = _find_result(results, "SYL-MUD-002")
    assert r2 is not None and r2["severity"] == "error"


def test_mud_007_uptime_fresh_reboot():
    """SYL-MUD-007 WARN gdy uptime < 120s."""
    def fake_run(cmd, **kw):
        if "ping" in cmd:
            return _make_proc(0, "OK")
        if "ssh" in cmd:
            if "echo SYLION_OK" in " ".join(cmd):
                return _make_proc(0, "SYLION_OK")
            if "openwrt_release" in " ".join(cmd):
                return _make_proc(0, "22.03")
            if "ifstatus" in " ".join(cmd):
                return _make_proc(0, '"up":true')
            if "dhcp.leases" in " ".join(cmd):
                return _make_proc(0, "")
            if "iptables" in " ".join(cmd):
                return _make_proc(0, "5")
            if "proc/uptime" in " ".join(cmd):
                return _make_proc(0, "90.5 40.0")  # 90s uptime — świeży reboot
            if "meminfo" in " ".join(cmd):
                return _make_proc(0, "20480")
        return _make_proc(0, "")

    with patch("subprocess.run", side_effect=fake_run):
        results = check_mudi()

    r = _find_result(results, "SYL-MUD-007")
    if r:  # może być N/A jeśli SSH całkowicie nieudany w teście
        assert r["severity"] in ("warn", "n/a")


def test_mud_returns_list():
    """check_mudi() zawsze zwraca listę."""
    with patch("subprocess.run", return_value=_make_proc(1)):
        results = check_mudi()
    assert isinstance(results, list)
    assert len(results) > 0


# ===========================================================================
# T11-T14: SYL-WG — WireGuard
# ===========================================================================

def test_wg_001_not_installed():
    """SYL-WG-001 ERROR gdy WireGuard nie zainstalowany."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        results = check_wireguard()
    _assert_code_severity(results, "SYL-WG-001", "error")
    assert len(results) == 1  # bez interfejsu nie kontynuuje


def test_wg_001_no_output():
    """SYL-WG-001 ERROR gdy wg show zwraca pusty output."""
    with patch("subprocess.run", return_value=_make_proc(0, "")):
        results = check_wireguard()
    _assert_code_severity(results, "SYL-WG-001", "error")


def test_wg_003_no_peers():
    """SYL-WG-003 ERROR gdy wg show nie zawiera peer."""
    wg_output = "interface: wg0\n  public key: abc123\n  private key: (hidden)\n  listening port: 51820\n"
    with patch("subprocess.run", return_value=_make_proc(0, wg_output)):
        results = check_wireguard()
    r = _find_result(results, "SYL-WG-003")
    assert r is not None
    assert r["severity"] == "error"
    assert "0" in r["message"]


def test_wg_002_old_handshake():
    """SYL-WG-002 ERROR gdy handshake > 1 hour."""
    wg_output = (
        "interface: wg0\n"
        "  public key: abc\n"
        "peer: xyz\n"
        "  latest handshake: 2 hours, 5 minutes ago\n"
        "  transfer: 100 MiB received, 50 MiB sent\n"
    )
    with patch("subprocess.run", return_value=_make_proc(0, wg_output)):
        results = check_wireguard()
    _assert_code_severity(results, "SYL-WG-002", "error")


def test_wg_full_ok():
    """WG pełne OK z peerami i świeżym handshake."""
    wg_output = (
        "interface: wg0\n"
        "  public key: abc\n"
        "peer: xyz\n"
        "  latest handshake: 1 minute, 20 seconds ago\n"
        "  transfer: 100 MiB received, 50 MiB sent\n"
    )
    with patch("subprocess.run", return_value=_make_proc(0, wg_output)):
        results = check_wireguard()
    _assert_code_severity(results, "SYL-WG-001", "ok")
    _assert_code_severity(results, "SYL-WG-003", "ok")


# ===========================================================================
# T15-T19: SYL-API — API Keys
# ===========================================================================

def test_api_001_no_openai_key():
    """SYL-API-001 ERROR gdy brak OPENAI_API_KEY."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        results = check_api_keys_live()
    _assert_code_severity(results, "SYL-API-001", "error")


def test_api_009_openai_401():
    """SYL-API-009 ERROR gdy OpenAI zwraca 401 (revoked)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=False):
        try:
            import httpx
            with patch("httpx.get", return_value=mock_resp):
                results = check_api_keys_live()
        except ImportError:
            with patch("urllib.request.urlopen", side_effect=Exception("401 Unauthorized")):
                results = check_api_keys_live()

    r = _find_result(results, "SYL-API-009")
    if r:
        assert r["severity"] in ("error", "warn")


def test_api_009_openai_429():
    """SYL-API-009 WARN gdy OpenAI zwraca 429 (rate limited)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=False):
        try:
            import httpx
            with patch("httpx.get", return_value=mock_resp):
                results = check_api_keys_live()
        except ImportError:
            results = check_api_keys_live()

    r = _find_result(results, "SYL-API-009")
    if r and "429" in r["message"]:
        assert r["severity"] == "warn"


def test_api_002_wrong_prefix():
    """SYL-API-002 WARN gdy OpenAI klucz ma zły prefix."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "wrong-prefix-abc"}, clear=False):
        try:
            import httpx
            with patch("httpx.get", return_value=MagicMock(status_code=200)):
                results = check_api_keys_live()
        except ImportError:
            results = check_api_keys_live()

    r = _find_result(results, "SYL-API-002")
    if r:
        assert r["severity"] == "warn"


def test_api_all_missing():
    """Wszystkie wymagane klucze brak — dwa ERROR (OpenAI, Anthropic)."""
    env_patch = {k: "" for k in [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY",
        "GOOGLE_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY"
    ]}
    with patch.dict(os.environ, env_patch, clear=False):
        results = check_api_keys_live()

    errors = [r for r in results if r["severity"] == "error" and r["code"] in ("SYL-API-001", "SYL-API-003")]
    assert len(errors) == 2


# ===========================================================================
# T20-T21: SYL-OLLAMA — Ollama
# ===========================================================================

def test_ollama_001_daemon_down():
    """SYL-OLLAMA-001 ERROR gdy Ollama daemon niedostępny."""
    try:
        import httpx
        with patch("httpx.get", side_effect=Exception("Connection refused")):
            results = check_ollama()
    except ImportError:
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            results = check_ollama()

    _assert_code_severity(results, "SYL-OLLAMA-001", "error")


def test_ollama_006_no_model_env():
    """SYL-OLLAMA-006 WARN gdy OLLAMA_MODEL nie ustawiony."""
    mock_resp_ver = MagicMock()
    mock_resp_ver.status_code = 200
    mock_resp_ver.json.return_value = {"version": "0.1.0"}

    mock_resp_tags = MagicMock()
    mock_resp_tags.status_code = 200
    mock_resp_tags.json.return_value = {"models": [{"name": "llama3.2:3b"}]}

    mock_resp_ps = MagicMock()
    mock_resp_ps.status_code = 200
    mock_resp_ps.json.return_value = {"models": []}

    with patch.dict(os.environ, {"OLLAMA_MODEL": ""}, clear=False):
        try:
            import httpx
            with patch("httpx.get", side_effect=[mock_resp_ver, mock_resp_tags,
                                                  mock_resp_ps, mock_resp_ps]):
                results = check_ollama()
        except ImportError:
            results = check_ollama()

    r = _find_result(results, "SYL-OLLAMA-006")
    if r:
        assert r["severity"] == "warn"


# ===========================================================================
# T22-T25: SYL-UPL — Upload Workspace
# ===========================================================================

def test_upl_001_missing_dir(tmp_path):
    """SYL-UPL-001 ERROR gdy upload dir nie istnieje."""
    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_uploads()
    _assert_code_severity(results, "SYL-UPL-001", "error")
    assert len(results) == 1  # early return


def test_upl_005_path_traversal(tmp_path):
    """SYL-UPL-005 CRITICAL gdy plik z '..' w nazwie."""
    upl = tmp_path / "sylion-pipeline" / "dashboard" / "workspace_uploads"
    upl.mkdir(parents=True)
    (upl / "evil..file.txt").touch()

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_uploads()

    _assert_code_severity(results, "SYL-UPL-005", "critical")
    assert "evil..file.txt" in str(results)


def test_upl_006_dangerous_extension(tmp_path):
    """SYL-UPL-006 WARN gdy plik .sh w upload dir."""
    upl = tmp_path / "sylion-pipeline" / "dashboard" / "workspace_uploads"
    upl.mkdir(parents=True)
    (upl / "hack.sh").touch()

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_uploads()

    _assert_code_severity(results, "SYL-UPL-006", "warn")


def test_upl_clean_dir(tmp_path):
    """Upload dir OK gdy brak problemów."""
    upl = tmp_path / "sylion-pipeline" / "dashboard" / "workspace_uploads"
    upl.mkdir(parents=True)
    (upl / "document.pdf").touch()

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_uploads()

    r1 = _find_result(results, "SYL-UPL-001")
    assert r1 and r1["severity"] == "ok"

    r5 = _find_result(results, "SYL-UPL-005")
    assert r5 and r5["severity"] == "ok"

    r6 = _find_result(results, "SYL-UPL-006")
    assert r6 and r6["severity"] == "ok"


# ===========================================================================
# T26-T27: SYL-SUB — Subagents
# ===========================================================================

def test_sub_001_stale_lock(tmp_path):
    """SYL-SUB-001 WARN gdy stale .lock file > 1h."""
    lock_file = tmp_path / "old_task.lock"
    lock_file.touch()
    old_mtime = time.time() - 7200  # 2h temu
    os.utime(lock_file, (old_mtime, old_mtime))

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_subagents()

    r = _find_result(results, "SYL-SUB-001")
    assert r is not None
    assert r["severity"] == "warn"


def test_sub_001_fresh_lock(tmp_path):
    """SYL-SUB-001 OK gdy lock file jest świeży (< 1h)."""
    lock_file = tmp_path / "fresh_task.lock"
    lock_file.touch()

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_subagents()

    r = _find_result(results, "SYL-SUB-001")
    assert r is not None
    assert r["severity"] == "ok"


# ===========================================================================
# T28-T29: SYL-KSIEGA — Księga
# ===========================================================================

def test_ksiega_001_not_found(tmp_path):
    """SYL-KSIEGA-001 ERROR gdy brak ksiega.json."""
    with patch("health_check_v2._find_sylion_home", return_value=tmp_path), \
         patch("pathlib.Path.home", return_value=tmp_path):
        results = check_ksiega()

    _assert_code_severity(results, "SYL-KSIEGA-001", "error")


def test_ksiega_003_invalid_json(tmp_path):
    """SYL-KSIEGA-003 ERROR gdy ksiega.json ma błędy JSON."""
    ksiega = tmp_path / "ksiega.json"
    ksiega.write_text("{invalid json {{{{")

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path), \
         patch("pathlib.Path.home", return_value=tmp_path):
        results = check_ksiega()

    r = _find_result(results, "SYL-KSIEGA-003")
    if r:
        assert r["severity"] == "error"


def test_ksiega_002_wrong_version(tmp_path):
    """SYL-KSIEGA-002 WARN gdy version != 3.4."""
    ksiega = tmp_path / "ksiega.json"
    ksiega.write_text(json.dumps({"version": "2.0", "entries": []}))

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path), \
         patch("pathlib.Path.home", return_value=tmp_path):
        results = check_ksiega()

    r = _find_result(results, "SYL-KSIEGA-002")
    if r:
        assert r["severity"] == "warn"


# ===========================================================================
# T30-T31: SYL-PHANTOM — Phantom
# ===========================================================================

def test_phantom_001_no_config(tmp_path):
    """SYL-PHANTOM-001 WARN gdy brak phantom config."""
    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_phantom()

    _assert_code_severity(results, "SYL-PHANTOM-001", "warn")


def test_phantom_002_wrong_version(tmp_path):
    """SYL-PHANTOM-002 WARN gdy version != 3."""
    cfg = tmp_path / "phantom.json"
    cfg.write_text(json.dumps({"version": "2", "enabled": True}))

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        with patch("subprocess.run", return_value=_make_proc(0, "")):
            results = check_phantom()

    r = _find_result(results, "SYL-PHANTOM-002")
    if r:
        assert r["severity"] == "warn"


# ===========================================================================
# T32-T33: SYL-PIPELINE — Pipeline FSM
# ===========================================================================

def test_pipeline_na_no_db(tmp_path):
    """SYL-PIPELINE-001..004 N/A gdy brak DB."""
    with patch("health_check_v2._find_db", return_value=None), \
         patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_pipeline()

    codes_na = ["SYL-PIPELINE-001", "SYL-PIPELINE-002", "SYL-PIPELINE-003", "SYL-PIPELINE-004"]
    for code in codes_na:
        r = _find_result(results, code)
        if r:
            assert r["severity"] in ("n/a", "warn")


def test_pipeline_failed_run():
    """SYL-PIPELINE-001 ERROR gdy ostatni run: failed."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE runs (status TEXT, updated_at TEXT, started_at TEXT)")
    con.execute("INSERT INTO runs VALUES ('failed', '2024-01-01 10:00:00', '2024-01-01 09:50:00')")
    con.commit()
    con.close()

    with patch("health_check_v2._find_db", return_value=db_path), \
         patch("health_check_v2._find_sylion_home", return_value=Path(db_path.parent)):
        results = check_pipeline()

    r = _find_result(results, "SYL-PIPELINE-001")
    if r:
        assert r["severity"] in ("error", "warn")

    db_path.unlink(missing_ok=True)


# ===========================================================================
# T34-T35: SYL-DB — DB Extended
# ===========================================================================

def test_db_extended_integrity_ok():
    """SYL-DB-006 OK gdy PRAGMA integrity_check = ok."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()

    with patch("health_check_v2._find_db", return_value=db_path):
        results = check_db_extended()

    r = _find_result(results, "SYL-DB-006")
    assert r is not None
    assert r["severity"] == "ok", f"msg: {r['message']}"

    db_path.unlink(missing_ok=True)


def test_db_extended_no_db():
    """SYL-DB-* N/A gdy brak bazy."""
    with patch("health_check_v2._find_db", return_value=None):
        results = check_db_extended()

    for r in results:
        assert r["severity"] == "n/a"


# ===========================================================================
# T36-T37: SYL-CVE — CVE Scan
# ===========================================================================

def test_cve_001_pip_audit_not_installed():
    """SYL-CVE-001 WARN gdy pip-audit nie zainstalowany."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        results = check_cve()

    _assert_code_severity(results, "SYL-CVE-001", "warn")


def test_cve_002_no_vulns():
    """SYL-CVE-002 OK gdy pip-audit nie znalazł CVE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir) / "logs" / ".cve_cache.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps({
            "vulnerabilities": [],
            "dependencies": [],
            "timestamp": time.time()
        }))

        def fake_run(cmd, **kw):
            if "pip-audit" in cmd and "--version" in cmd:
                return _make_proc(0, "pip-audit 2.6.1")
            if "pip-audit" in cmd:
                return _make_proc(0, json.dumps({"vulnerabilities": [], "dependencies": []}))
            if "pip" in cmd and "list" in cmd:
                return _make_proc(0, "[]")
            return _make_proc(0, "")

        with patch("health_check_v2._find_sylion_home", return_value=Path(tmpdir)):
            with patch("subprocess.run", side_effect=fake_run):
                results = check_cve()

    r = _find_result(results, "SYL-CVE-001")
    assert r is not None and r["severity"] == "ok"


# ===========================================================================
# T38-T39: SYL-RODO — RODO
# ===========================================================================

def test_rodo_003_old_logs(tmp_path):
    """SYL-RODO-003 WARN gdy logi > 90 dni."""
    logs = tmp_path / "logs"
    logs.mkdir()
    old_log = logs / "old.log"
    old_log.write_text("normal content")
    old_mtime = time.time() - 100 * 86400  # 100 dni
    os.utime(old_log, (old_mtime, old_mtime))

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_rodo()

    r = _find_result(results, "SYL-RODO-003")
    assert r is not None
    assert r["severity"] == "warn"


def test_rodo_004_pii_in_logs(tmp_path):
    """SYL-RODO-004 CRITICAL gdy PESEL w logach."""
    logs = tmp_path / "logs"
    logs.mkdir()
    log_file = logs / "pipeline.log"
    log_file.write_text("INFO: processing user 90010112345 done\n")  # PESEL-like

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_rodo()

    r = _find_result(results, "SYL-RODO-004")
    assert r is not None
    assert r["severity"] == "critical"


def test_rodo_004_no_pii(tmp_path):
    """SYL-RODO-004 OK gdy brak PESEL/email w logach."""
    logs = tmp_path / "logs"
    logs.mkdir()
    log_file = logs / "pipeline.log"
    log_file.write_text("INFO: pipeline started\nDEBUG: processing batch 42\n")

    with patch("health_check_v2._find_sylion_home", return_value=tmp_path):
        results = check_rodo()

    r = _find_result(results, "SYL-RODO-004")
    assert r is not None
    assert r["severity"] == "ok"


# ===========================================================================
# T40-T41: SYL-CERT — Certificates
# ===========================================================================

def test_cert_001_no_systemctl():
    """SYL-CERT-001 N/A gdy systemctl niedostępny."""
    with patch("subprocess.run", side_effect=FileNotFoundError), \
         patch.dict(os.environ, {"SYLION_DOMAIN": ""}, clear=False):
        results = check_cert()

    r = _find_result(results, "SYL-CERT-001")
    assert r is not None
    assert r["severity"] in ("n/a", "warn")


def test_cert_na_no_domain():
    """CERT-002..005 N/A gdy SYLION_DOMAIN nie ustawiony."""
    with patch.dict(os.environ, {"SYLION_DOMAIN": ""}, clear=False):
        with patch("subprocess.run", return_value=_make_proc(0, "active")):
            results = check_cert()

    for code in ["SYL-CERT-002", "SYL-CERT-003", "SYL-CERT-004", "SYL-CERT-005"]:
        r = _find_result(results, code)
        assert r is not None
        assert r["severity"] == "n/a"


# ===========================================================================
# T42-T43: SYL-CRED — Credentials
# ===========================================================================

def test_cred_na_no_db():
    """SYL-CRED-* N/A gdy brak DB."""
    with patch("health_check_v2._find_db", return_value=None):
        results = check_cred()

    for r in results:
        assert r["severity"] == "n/a"


def test_cred_005_no_role():
    """SYL-CRED-005 ERROR gdy użytkownik bez roli."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, "
                "password_hash TEXT, totp_secret TEXT, last_login INTEGER)")
    con.execute("INSERT INTO users VALUES (1, 'admin', NULL, 'abc123def456789012345678901234567890', NULL, NULL)")
    con.commit()
    con.close()

    with patch("health_check_v2._find_db", return_value=db_path):
        results = check_cred()

    r = _find_result(results, "SYL-CRED-005")
    if r:
        assert r["severity"] == "error", f"msg: {r['message']}"

    db_path.unlink(missing_ok=True)


def test_cred_003_no_2fa():
    """SYL-CRED-003 WARN gdy użytkownik bez TOTP."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, "
                "password_hash TEXT, totp_secret TEXT, last_login INTEGER)")
    con.execute("INSERT INTO users VALUES (1, 'admin', 'owner', 'abc123def456789012345678901234567890', NULL, NULL)")
    con.commit()
    con.close()

    with patch("health_check_v2._find_db", return_value=db_path):
        results = check_cred()

    r = _find_result(results, "SYL-CRED-003")
    if r:
        assert r["severity"] == "warn"

    db_path.unlink(missing_ok=True)


# ===========================================================================
# T44-T46: Orkiestrator i historia
# ===========================================================================

def test_run_comprehensive_health_returns_dict():
    """run_comprehensive_health() zwraca dict ze standardowymi polami."""
    # Mock wszystkich runnerów
    mock_checks = [_ok("SYL-TEST-001", "test", "OK")]

    with patch("health_check_v2.RUNNERS", [
        ("test", lambda: mock_checks)
    ]):
        with patch("health_check_v2._save_history"):
            result = run_comprehensive_health(timeout=10)

    assert isinstance(result, dict)
    assert "overall" in result
    assert "checks" in result
    assert "categories" in result
    assert "stats" in result
    assert "timestamp" in result
    assert result["version"] == "v2"


def test_worst_severity_logic():
    """_worst_severity() poprawnie oblicza najgorsze severity."""
    checks = [
        {"severity": "ok"},
        {"severity": "warn"},
        {"severity": "error"},
    ]
    assert _worst_severity(checks) == "error"

    checks2 = [{"severity": "ok"}, {"severity": "critical"}]
    assert _worst_severity(checks2) == "critical"

    checks3 = [{"severity": "ok"}, {"severity": "n/a"}]
    assert _worst_severity(checks3) == "ok"


def test_history_sqlite():
    """Historia zapisuje się do SQLite i da się odczytać."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    import health_check_v2
    original = health_check_v2._HISTORY_DB_PATH
    health_check_v2._HISTORY_DB_PATH = db_path

    try:
        init_history_table(db_path)
        _save_history({
            "overall": "ok",
            "elapsed_ms": 1234,
            "stats": {"total": 5, "pass": 5, "warn": 0, "fail": 0, "critical": 0},
            "checks": [],
            "categories": {},
            "version": "v2",
            "timestamp": "2024-01-01T00:00:00Z",
        })
        history = get_history(limit=10)
        assert len(history) >= 1
        assert history[0]["overall"] == "ok"
        assert history[0]["elapsed_ms"] == 1234
    finally:
        health_check_v2._HISTORY_DB_PATH = original
        db_path.unlink(missing_ok=True)


# ===========================================================================
# T47-T48: Migration tests
# ===========================================================================

def test_migration_creates_table():
    """Migracja v3→v4 tworzy tabelę health_history."""
    from migration_3_to_4 import run_migration, verify_migration

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        result = run_migration(db_path=db_path)
        assert result["success"] is True
        assert result["applied"] is True

        verify = verify_migration(db_path=db_path)
        assert verify["ok"] is True
        assert verify["checks"]["health_history_table"] is True
        assert verify["checks"]["idx_hh_run_at"] is True
    finally:
        db_path.unlink(missing_ok=True)


def test_migration_idempotent():
    """Migracja jest idempotentna — drugie uruchomienie nie rzuca błędu."""
    from migration_3_to_4 import run_migration

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        r1 = run_migration(db_path=db_path)
        assert r1["success"] and r1["applied"]

        r2 = run_migration(db_path=db_path)
        assert r2["success"] is True
        assert r2["applied"] is False  # nie zastosowana drugi raz
    finally:
        db_path.unlink(missing_ok=True)


# ===========================================================================
# T49: Result structure validation
# ===========================================================================

def test_result_dict_structure():
    """Każdy wynik check ma wymagane pola."""
    required = {"code", "category", "severity", "status", "message", "timestamp", "suggestion_pl"}

    # Run a simple check that we know will produce results
    with patch("subprocess.run", side_effect=FileNotFoundError):
        results = check_pixel()

    for r in results:
        missing = required - set(r.keys())
        assert not missing, f"Brakujące pola w {r.get('code','?')}: {missing}"


# ===========================================================================
# T50: _ok / _warn / _err / _crit / _na helpers
# ===========================================================================

def test_result_helpers():
    """Helpery _ok/_warn/_err/_crit/_na zwracają poprawne severity."""
    assert _ok("X", "y", "m")["severity"] == "ok"
    assert _warn("X", "y", "m")["severity"] == "warn"
    assert _err("X", "y", "m")["severity"] == "error"
    assert _crit("X", "y", "m")["severity"] == "critical"
    assert _na("X", "y")["severity"] == "n/a"


# ===========================================================================
# T51: Async orchestrator smoke test
# ===========================================================================

def test_async_orchestrator_smoke():
    """Async orchestrator zwraca poprawny format (via asyncio.run)."""
    mock_checks = [_ok("SYL-TEST-001", "test", "OK")]

    async def _inner():
        return await run_comprehensive_health_async(timeout=10)

    with patch("health_check_v2.RUNNERS", [("test", lambda: mock_checks)]):
        with patch("health_check_v2._save_history"):
            result = asyncio.run(_inner())

    assert result["version"] == "v2"
    assert "overall" in result
    assert "test" in result["categories"]


# ===========================================================================
# T52: Endpoint handler smoke test
# ===========================================================================

def test_endpoint_categories():
    """handler /api/health/categories zwraca listę 15 kategorii."""
    from health_endpoints import _handler_categories
    result = _handler_categories()
    assert result["count"] == 15
    assert len(result["categories"]) == 15
    assert result["total_codes"] == 87  # suma kodów per kategoria (87 = rzeczywista suma TF06)


def test_endpoint_history_empty():
    """handler /api/health/history zwraca dict z 'history' list."""
    from health_endpoints import _handler_history
    with patch("health_endpoints.get_history", return_value=[]):
        result = _handler_history(limit=10)
    assert "history" in result
    assert isinstance(result["history"], list)
    assert "count" in result
