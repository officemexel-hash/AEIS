from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]


def test_legacy_dashboard_package_is_absent():
    assert not (PROJECT_ROOT / "dashboard").exists()


def test_root_start_scripts_use_modular_api_runtime():
    scripts = [
        REPO_ROOT / "scripts" / "start-server.sh",
        REPO_ROOT / "scripts" / "start-server.ps1",
        REPO_ROOT / "scripts" / "start-server.bat",
    ]
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "sylion.api.app:app" in text
        assert "DASHBOARD_DB_PATH" not in text


def test_compose_variants_use_unified_runtime_entrypoint():
    legacy_start = "dashboard" + "/start.py"

    compose_dev = yaml.safe_load((PROJECT_ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"))
    dev_command = "\n".join(compose_dev["services"]["sylion-dashboard"]["command"])
    assert "python -m sylion.server" in dev_command
    assert legacy_start not in dev_command

    compose_override = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")
    )
    override_command = "\n".join(compose_override["services"]["sylion-dashboard"]["command"])
    assert "sylion.server" in override_command
    assert legacy_start not in override_command


def test_operational_scripts_do_not_call_legacy_runtime():
    legacy_start = "python " + "dashboard" + "/start.py"
    for path in [
        PROJECT_ROOT / "install.sh",
        PROJECT_ROOT / "install.bat",
        PROJECT_ROOT / "rollback.sh",
        PROJECT_ROOT / "scripts" / "build_release.sh",
    ]:
        text = path.read_text(encoding="utf-8")
        assert legacy_start not in text.replace("\\", "/")
