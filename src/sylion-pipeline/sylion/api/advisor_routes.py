"""SYLION AEIS Advisor — REST API.

Bridges the frontend `lib/api/advisor.ts` client to the existing synchronous
service singletons:

  * `advisor.engine.AdvisorEngineService`        — cards + evidence packs
  * `advisor.actions.ActionsService`             — accept/reject/modify routing
  * `advisor.preferences.PreferencesService`     — preference CRUD + onboarding
  * `advisor.funding.AdvisorFundingService`      — grants catalog

The frontend assumes:
  * `GET /api/v1/advisor/cards?operator_id=...` returns `{cards: [...]}`
  * `GET /api/v1/advisor/cards/{id}` returns one envelope
  * `POST /api/v1/advisor/cards/{id}/actions` records an action
  * `GET /api/v1/advisor/evidence/{packId}`
  * `POST /api/v1/advisor/evidence/{packId}/finalize`
  * `POST /api/v1/advisor/evidence/{packId}/sign`
  * `GET / PUT / DELETE /api/v1/advisor/preferences[...]`
  * `GET /api/v1/advisor/preferences/audit`
  * `GET /api/v1/advisor/onboarding/state`
  * `PUT /api/v1/advisor/onboarding/step/{step}`
  * `POST /api/v1/advisor/onboarding/complete`
  * `GET /api/v1/advisor/projects/{project_id}/lifecycle`
  * `GET /api/v1/advisor/monitoring/snapshot`
  * `GET /api/v1/advisor/funding/grants`
  * `GET /api/v1/advisor/funding/deadlines`

Honest empty responses are returned when the underlying services have no data;
callers must NOT receive synthetic numbers.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import tempfile
import time
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from sylion.aeis_v2.audit_chain import append_to_chain, verify_chain
from sylion.aeis_v2.audit_profile import resolve_audit_chain_dir, resolve_audit_chain_path

log = logging.getLogger("sylion.api.advisor")

router = APIRouter(prefix="/api/v1/advisor", tags=["advisor"])

# Default operator_id used when the frontend has no logged-in user yet.
# Mirrors `MOCK_OPERATOR_ID` in `lib/api/advisor.ts`. Replace with real auth
# once `request.state.user` is populated.
_DEFAULT_OPERATOR = "00000000-0000-0000-0000-000000000001"

# Onboarding state lives in advisor_preferences under these keys; the wizard is
# treated as a special preference namespace so the data persists in PG.
_ONBOARDING_STATE_KEY = "onboarding_state"
_ONBOARDING_COMPLETED_KEY = "advisor_onboarded"
_PHASE1_COMPLETED_KEY = "phase_1_completed"

# Process-local cache so the wizard works even if the preferences table is
# unavailable (e.g. fresh install before migrations, or test fixtures that
# use a partial schema). PG persistence below is best-effort: when it
# succeeds we still hit the real preferences table; when it fails we fall
# back to this cache so the route never returns 500.
_ONBOARDING_CACHE: dict[str, dict[str, Any]] = {}

_ADVISOR_AUDIT_CHAIN = "advisor_audit.jsonl"
_PHASE1_AUDIT_CHAIN = "onboarding.jsonl"

_RESOLVED_CARD_TAGS = frozenset({"accepted", "rejected", "not_useful", "human_gate", "masterplan"})
_BLOCKED_CARD_TAGS = frozenset({"rejected", "not_useful"})

_SECRET_FIELD_HINTS = (
    "key",
    "token",
    "secret",
    "password",
    "credential",
    "consumer_key",
    "application_secret",
)


def _mask_secret(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _is_secret_field(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _SECRET_FIELD_HINTS)


def _redact_onboarding_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe for API responses without leaking raw credentials."""
    redacted = deepcopy(state)
    values = redacted.get("values")
    if not isinstance(values, dict):
        return redacted

    api_keys = values.get("api_keys")
    if isinstance(api_keys, list):
        for entry in api_keys:
            if isinstance(entry, dict) and "key" in entry:
                entry["key"] = _mask_secret(entry.get("key"))
                entry["key_masked"] = True

    hosting_providers = values.get("hosting_providers")
    if isinstance(hosting_providers, list):
        for entry in hosting_providers:
            if not isinstance(entry, dict):
                continue
            fields = entry.get("fields")
            if not isinstance(fields, dict):
                continue
            for field_name, field_value in list(fields.items()):
                if _is_secret_field(str(field_name)):
                    fields[field_name] = _mask_secret(field_value)
            entry["secrets_masked"] = True

    return redacted


def _card_tags(env: dict[str, Any]) -> set[str]:
    tags = ((env.get("header", {}) or {}).get("tags") or [])
    if isinstance(tags, str):
        return {tags}
    if not isinstance(tags, list):
        return set()
    return {str(tag) for tag in tags if str(tag)}


def _is_resolved_card(env: dict[str, Any]) -> bool:
    return bool(_card_tags(env) & _RESOLVED_CARD_TAGS)


def _phase_status_for_cards(bucket: list[dict[str, Any]]) -> str:
    if not bucket:
        return "pending"
    if any(not _is_resolved_card(env) for env in bucket):
        return "in_progress"
    if any(_card_tags(env) & _BLOCKED_CARD_TAGS for env in bucket):
        return "blocked"
    return "approved"


def _summarize_onboarding_values(values: Any) -> dict[str, Any]:
    """Summarize wizard values for audit without writing secrets."""
    if not isinstance(values, dict):
        return {}

    summary: dict[str, Any] = {"changed_keys": sorted(str(k) for k in values.keys())}
    api_keys = values.get("api_keys")
    if isinstance(api_keys, list):
        providers: list[str] = []
        validation: dict[str, int] = {}
        for entry in api_keys:
            if not isinstance(entry, dict):
                continue
            provider = str(entry.get("provider") or "").strip()
            if provider:
                providers.append(provider)
            status = str(entry.get("validation_status") or "unknown")
            validation[status] = validation.get(status, 0) + 1
        summary["api_key_count"] = len(api_keys)
        summary["api_key_providers"] = sorted(set(providers))
        summary["api_key_validation"] = validation

    hosting = values.get("hosting_providers")
    if isinstance(hosting, list):
        summary["hosting_provider_count"] = len(hosting)
        summary["hosting_providers"] = sorted(
            {
                str(entry.get("provider") or "").strip()
                for entry in hosting
                if isinstance(entry, dict) and entry.get("provider")
            }
        )

    local_models = values.get("local_models")
    if isinstance(local_models, list):
        summary["local_models_installed"] = sum(
            1 for entry in local_models if isinstance(entry, dict) and entry.get("status") == "installed"
        )

    for key in (
        "default_project_domain",
        "custom_domain_prefix",
        "autonomy_level",
        "council_size",
        "cost_ceilings",
        "llm_judge_routing",
        "quality_speed_cost",
        "trusted_providers",
        "blocked_providers",
        "funding_advisor_enabled",
        "funding_countries",
        "funding_pl_regions",
        "idea_skipped",
    ):
        if key in values:
            summary[key] = values[key]

    if "first_idea_title" in values or "first_idea_description" in values:
        summary["first_idea_supplied"] = bool(
            str(values.get("first_idea_title") or "").strip()
            or str(values.get("first_idea_description") or "").strip()
        )
    return summary


_PHASE1_WORKSPACE_FOLDERS = (
    "workspace",
    "backups",
    "audit_chain",
    "artifacts",
    "projects",
    "tutorial",
    "models",
    "logs",
    "metrics",
    "settings",
    "secrets",
    "exports",
    "imports",
    "cache",
    "tmp",
)


def _phase1_system_name(value: Any, fallback: Any = "operator") -> str:
    raw = str(value or fallback or "operator").strip().lower()
    raw = re.sub(r"[^a-z0-9.]+", ".", raw)
    raw = re.sub(r"\.+", ".", raw).strip(".")
    if not raw:
        raw = "operator"
    return raw[:32]


def _phase1_default_workspace(values: dict[str, Any] | None = None) -> str:
    vals = values or {}
    system_name = _phase1_system_name(vals.get("system_name"), vals.get("operator_name"))
    return str(Path.home() / ".sylion" / system_name)


def _phase1_is_cloud_synced(path: Path) -> bool:
    lowered = str(path).lower()
    markers = ("onedrive", "dropbox", "google drive", "icloud", "box sync")
    return any(marker in lowered for marker in markers)


def _phase1_is_blocked_path(path: Path) -> bool:
    resolved = str(path.expanduser()).lower().replace("/", "\\")
    blocked_exact = {
        "\\",
        "c:\\",
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
    }
    if resolved.rstrip("\\") in blocked_exact:
        return True
    blocked_parts = (
        "\\windows\\",
        "\\program files\\",
        "\\program files (x86)\\",
        "\\system32\\",
        "\\syswow64\\",
    )
    return any(part in resolved for part in blocked_parts)


def _phase1_probe_parent(path: Path) -> tuple[Path | None, list[str], str | None]:
    """Return an existing directory suitable for non-mutating write probes."""
    if path.exists():
        if path.is_dir():
            return path, [], None
        return None, [], "workspace_path_is_file"

    missing: list[str] = []
    probe_parent = path.parent
    while not probe_parent.exists() and probe_parent != probe_parent.parent:
        missing.append(str(probe_parent))
        probe_parent = probe_parent.parent

    if not probe_parent.exists():
        return None, missing, "parent_missing"
    if not probe_parent.is_dir():
        return None, missing, "parent_not_directory"
    return probe_parent, missing, None


def _phase1_storage_validation(path_value: Any, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a candidate workspace path without permanently mutating it."""
    raw = str(path_value or "").strip() or _phase1_default_workspace(values)
    path = Path(raw).expanduser()
    result: dict[str, Any] = {
        "path": str(path),
        "ok": False,
        "writable": False,
        "sqlite_ok": False,
        "would_create": not path.exists(),
        "warnings": [],
        "errors": [],
    }

    if _phase1_is_blocked_path(path):
        result["errors"].append("blocked_system_path")
        return result

    if _phase1_is_cloud_synced(path):
        result["warnings"].append("cloud_synced_path")

    probe_parent, missing_parents, probe_error = _phase1_probe_parent(path)
    if missing_parents:
        result["warnings"].append("workspace_parent_will_be_created")
        result["missing_parents"] = missing_parents
    if probe_error or probe_parent is None:
        result["errors"].append(probe_error or "parent_missing")
        return result
    result["probe_path"] = str(probe_parent)

    try:
        usage = shutil.disk_usage(str(probe_parent))
        free_gb = round(usage.free / (1024 ** 3), 2)
        result["free_gb"] = free_gb
        if free_gb < 2:
            result["errors"].append("disk_space_below_2gb")
        elif free_gb < 5:
            result["warnings"].append("disk_space_below_5gb")
    except Exception as exc:  # noqa: BLE001
        result["warnings"].append(f"disk_usage_unavailable:{type(exc).__name__}")

    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix=".aeis_phase1_", dir=str(probe_parent)) as tmp_dir:
            tmp_path = Path(tmp_dir)
            probe = tmp_path / "write_test.bin"
            payload = b"aeis-phase1-storage-check" * 4096
            probe.write_bytes(payload)
            if probe.read_bytes() != payload:
                result["errors"].append("readback_mismatch")
            elapsed = max(time.perf_counter() - started, 0.001)
            mbps = round((len(payload) / (1024 * 1024)) / elapsed, 2)
            result["write_mbps"] = mbps
            if mbps < 10:
                result["warnings"].append("write_speed_below_10mbps")
            sqlite_path = tmp_path / "sqlite_test.db"
            conn = sqlite3.connect(sqlite_path)
            try:
                conn.execute("CREATE TABLE phase1_probe(id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO phase1_probe(value) VALUES (?)", ("ok",))
                row = conn.execute("SELECT value FROM phase1_probe WHERE id=1").fetchone()
                result["sqlite_ok"] = bool(row and row[0] == "ok")
                if not result["sqlite_ok"]:
                    result["errors"].append("sqlite_readback_failed")
            finally:
                conn.close()
        result["writable"] = "readback_mismatch" not in result["errors"]
    except PermissionError:
        result["errors"].append("permission_denied")
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"write_test_failed:{type(exc).__name__}")

    result["ok"] = result["writable"] and result["sqlite_ok"] and not result["errors"]
    return result


def _phase1_local_model_probe(run_test: bool = False) -> dict[str, Any]:
    """Probe local model availability for the Phase 1 hard gate."""
    models: list[dict[str, Any]] = []
    reachable = False
    try:
        from sylion.api.ai_providers_routes import _ollama_installed_models, _ollama_reachable

        models = _ollama_installed_models()
        reachable = bool(models) or bool(_ollama_reachable())
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "ollama",
            "reachable": False,
            "models": [],
            "count": 0,
            "functional_check": {"status": "error", "error": type(exc).__name__},
        }

    functional: dict[str, Any] = {"status": "not_run"}
    if run_test and models:
        model_name = str(models[0].get("name") or "").strip()
        functional = _phase1_ollama_echo_check(model_name)

    return {
        "provider": "ollama",
        "reachable": reachable,
        "models": models,
        "count": len(models),
        "functional_check": functional,
    }


def _phase1_ollama_echo_check(model_name: str) -> dict[str, Any]:
    if not model_name:
        return {"status": "error", "error": "missing_model"}
    try:
        import httpx
        from sylion.api.ai_providers_routes import OLLAMA_BASE_URL

        started = time.perf_counter()
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": 'Reply with exactly: Hello AEIS',
                    "stream": False,
                    "options": {"num_predict": 8},
                },
            )
        latency = round(time.perf_counter() - started, 3)
        if res.status_code >= 400:
            return {"status": "error", "model": model_name, "latency_seconds": latency, "error": f"http_{res.status_code}"}
        body = res.json()
        text = str(body.get("response") or "")
        return {
            "status": "ok" if "hello" in text.lower() and "aeis" in text.lower() else "warning",
            "model": model_name,
            "latency_seconds": latency,
            "available_but_slow": latency >= 30,
            "sample": text[:80],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "model": model_name, "error": type(exc).__name__}


def _phase1_model_gate(values: dict[str, Any] | None = None, run_test: bool = False) -> dict[str, Any]:
    vals = values or {}
    local_probe = _phase1_local_model_probe(run_test=run_test)
    state_models = [
        row for row in vals.get("local_models", [])
        if isinstance(row, dict) and row.get("status") == "installed"
    ] if isinstance(vals.get("local_models"), list) else []
    api_rows = vals.get("api_keys") if isinstance(vals.get("api_keys"), list) else []
    has_api = any(
        isinstance(row, dict)
        and str(row.get("provider") or "").strip()
        and str(row.get("key") or "").strip()
        and not _is_masked_secret(row.get("key"))
        for row in api_rows
    )
    demo = bool(vals.get("demo_mode_accepted"))
    local_count = max(int(local_probe.get("count") or 0), len(state_models))
    passed = local_count > 0 or has_api or demo
    return {
        "passed": passed,
        "local_model_count": local_count,
        "has_api_key": has_api,
        "demo_mode": demo,
        "local_probe": local_probe,
        "required": "minimum_one_model_or_api_or_demo",
    }


def _phase1_system_check(values: dict[str, Any] | None = None) -> dict[str, Any]:
    workspace_path = Path(str((values or {}).get("workspace_path") or _phase1_default_workspace(values))).expanduser()
    probe_parent = workspace_path if workspace_path.exists() else workspace_path.parent
    storage = _phase1_storage_validation(str(workspace_path), values)
    model_probe = _phase1_local_model_probe(run_test=False)
    return {
        "status": "ok" if not storage.get("errors") else "warning",
        "workspace_default": _phase1_default_workspace(values),
        "disk": {
            "path": str(probe_parent),
            "free_gb": storage.get("free_gb"),
            "min_required_gb": 2,
            "recommended_gb": 50,
        },
        "ram": {"status": "unknown", "min_required_gb": 8, "recommended_gb": 16},
        "gpu": {"status": "not_benchmarked", "class": "unknown"},
        "local_models": {
            "count": model_probe.get("count", 0),
            "ollama_reachable": model_probe.get("reachable", False),
            "models": model_probe.get("models", []),
        },
        "backend": {"health": "ok"},
    }


def _phase1_core_checks(state: dict[str, Any]) -> list[dict[str, Any]]:
    values = state.get("values") if isinstance(state.get("values"), dict) else {}
    checks: list[dict[str, Any]] = []

    def add(key: str, ok: bool, label: str, detail: Any = None) -> None:
        checks.append({"key": key, "ok": bool(ok), "label": label, "detail": detail})

    display = str(values.get("operator_name") or values.get("display_name") or "").strip()
    system_name = str(values.get("system_name") or "").strip()
    reserved = {"admin", "root", "system", "aeis"}
    add(
        "identity",
        bool(display)
        and 1 <= len(display) <= 64
        and bool(re.fullmatch(r"[a-z0-9.]{1,32}", system_name or ""))
        and system_name not in reserved
        and bool(values.get("operator_role"))
        and bool(values.get("timezone_confirmed") or values.get("timezone")),
        "Identity check",
        {"display_name": display, "system_name": system_name, "role": values.get("operator_role")},
    )
    email = str(values.get("operator_email") or "").strip()
    add(
        "email",
        bool(values.get("email_skipped")) or bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)),
        "Email handled",
        {"skipped": bool(values.get("email_skipped"))},
    )
    storage = values.get("storage_validation") if isinstance(values.get("storage_validation"), dict) else {}
    add("storage", bool(storage.get("ok")), "Storage check", storage)
    security_mode = str(values.get("security_mode") or "")
    add(
        "security",
        (security_mode == "password" and bool(values.get("master_password_configured")))
        or (security_mode == "low_security" and str(values.get("low_security_confirm") or "").strip().upper() == "ROZUMIEM"),
        "Security check",
        {"mode": security_mode},
    )
    goals = values.get("goals") if isinstance(values.get("goals"), list) else []
    add(
        "profile",
        (1 <= len(goals) <= 3 or bool(values.get("goals_decide_later")))
        and str(values.get("initial_autonomy_preset") or "") in {"conservative", "balanced", "aggressive"},
        "Profile check",
        {"goals": goals, "autonomy": values.get("initial_autonomy_preset")},
    )
    tutorial_mode = str(values.get("tutorial_mode") or "")
    tutorial_project = str(values.get("tutorial_project") or "")
    add(
        "tutorial",
        tutorial_mode == "skip" or (tutorial_mode in {"quick", "standard", "full"} and bool(tutorial_project)),
        "Tutorial check",
        {"mode": tutorial_mode, "project": tutorial_project},
    )
    gate = _phase1_model_gate(values, run_test=False)
    add("model_gate", bool(gate.get("passed")), "Hard gate check", gate)
    add(
        "notifications",
        str(values.get("notification_channel") or "in_app") == "in_app"
        and bool(values.get("telemetry_consent")) is False,
        "Notifications and telemetry check",
        {"notification_channel": values.get("notification_channel") or "in_app", "telemetry_consent": bool(values.get("telemetry_consent"))},
    )
    return checks


def _phase1_acceptance_report(operator_id: str, state: dict[str, Any]) -> dict[str, Any]:
    checks = _phase1_core_checks(state)
    chain_path = resolve_audit_chain_path(_PHASE1_AUDIT_CHAIN)
    try:
        tampered = verify_chain(chain_path)
        chain_lines = 0
        last_action = ""
        if chain_path.exists():
            with open(chain_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        chain_lines += 1
                        try:
                            last_action = str(json.loads(line).get("content", {}).get("action") or last_action)
                        except Exception:
                            pass
        audit_ok = chain_lines >= 8 and not tampered and last_action == "phase_1.complete"
        audit_detail = {"path": str(chain_path), "entries": chain_lines, "last_action": last_action, "tampered": len(tampered)}
    except Exception as exc:  # noqa: BLE001
        audit_ok = False
        audit_detail = {"path": str(chain_path), "error": type(exc).__name__}
    checks.append({"key": "audit_chain", "ok": audit_ok, "label": "Audit chain check", "detail": audit_detail})

    values = state.get("values") if isinstance(state.get("values"), dict) else {}
    workspace_path = Path(str(values.get("workspace_path") or _phase1_default_workspace(values))).expanduser()
    folder_count = sum(1 for folder in _PHASE1_WORKSPACE_FOLDERS if (workspace_path / folder).exists())
    completed_marker = bool(
        state.get("phase1_completed_at")
        or state.get("completed_at")
        or audit_ok
        or _has_completed_onboarding(operator_id)
    )
    checks.append({
        "key": "exit_state",
        "ok": completed_marker and folder_count >= len(_PHASE1_WORKSPACE_FOLDERS),
        "label": "Exit state check",
        "detail": {
            "workspace_path": str(workspace_path),
            "folders": folder_count,
            "required_folders": len(_PHASE1_WORKSPACE_FOLDERS),
            "completed_marker": completed_marker,
            "state_completed_at": bool(state.get("phase1_completed_at") or state.get("completed_at")),
            "audit_completed": audit_ok,
        },
    })

    passed = sum(1 for item in checks if item["ok"])
    return {
        "operator_id": operator_id,
        "accepted": passed == len(checks),
        "passed": passed,
        "total": len(checks),
        "checks": checks,
    }


def _phase1_bootstrap_workspace(values: dict[str, Any]) -> dict[str, Any]:
    workspace_path = Path(str(values.get("workspace_path") or _phase1_default_workspace(values))).expanduser()
    workspace_path.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for folder in _PHASE1_WORKSPACE_FOLDERS:
        target = workspace_path / folder
        target.mkdir(parents=True, exist_ok=True)
        created.append(str(target))
    return {"workspace_path": str(workspace_path), "folders": created}


def _emit_phase1_chain(operator_id: str, action: str, details: dict[str, Any] | None = None) -> None:
    content = {
        "action": action,
        "module": "phase_1.onboarding",
        "actor": "operator",
        "user_id": operator_id,
        "timestamp": time.time(),
        "details": details or {},
    }
    append_to_chain(resolve_audit_chain_path(_PHASE1_AUDIT_CHAIN), content)


def _emit_advisor_audit(
    kind: str,
    *,
    actor: str = "operator",
    module: str = "advisor",
    user_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append a real hash-chained advisor audit event.

    This deliberately writes only summaries. Raw API keys, hosting tokens,
    first-idea text, and other sensitive payload fields never go into this
    dashboard chain.
    """
    try:
        append_to_chain(
            resolve_audit_chain_path(_ADVISOR_AUDIT_CHAIN),
            {
                "kind": kind,
                "module": module,
                "actor": actor,
                "user_id": user_id or _DEFAULT_OPERATOR,
                "timestamp": time.time(),
                "details": details or {},
            },
        )
    except Exception as exc:  # pragma: no cover - audit must not break UX.
        log.warning("advisor audit emit failed: %s", exc, exc_info=True)


def _content_timestamp(content: dict[str, Any], fallback: float) -> float:
    for key in ("timestamp", "ts", "created_at", "updated_at"):
        value = content.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return fallback


def _read_recent_chain_entries(limit: int) -> list[dict[str, Any]]:
    root = resolve_audit_chain_dir()
    if not root.exists():
        return []

    entries: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.jsonl")):
        try:
            fallback_ts = path.stat().st_mtime
            with path.open("r", encoding="utf-8") as f:
                for line_no, raw in enumerate(f, start=1):
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    try:
                        row = json.loads(stripped)
                    except json.JSONDecodeError:
                        entries.append({
                            "id": f"{path.name}:{line_no}:parse_error",
                            "action": "audit_chain.parse_error",
                            "actor": "system",
                            "timestamp": fallback_ts,
                            "module": path.stem,
                            "chain_file": path.name,
                            "line_no": line_no,
                        })
                        continue
                    content = row.get("content") if isinstance(row, dict) else None
                    if not isinstance(content, dict):
                        continue
                    action = str(
                        content.get("kind")
                        or content.get("event_type")
                        or content.get("action")
                        or path.stem
                    )
                    module = str(content.get("module") or content.get("source_module") or path.stem)
                    actor = str(content.get("actor") or content.get("set_by") or "system")
                    entries.append({
                        "id": str(row.get("content_hash") or f"{path.name}:{line_no}"),
                        "action": action,
                        "actor": actor,
                        "timestamp": _content_timestamp(content, fallback_ts),
                        "module": module,
                        "chain_file": path.name,
                        "line_no": line_no,
                    })
        except OSError as exc:
            log.warning("advisor audit chain read failed for %s: %s", path, exc, exc_info=True)

    entries.sort(key=lambda e: (float(e.get("timestamp") or 0), str(e.get("id") or "")), reverse=True)
    return entries[:limit]
_ONBOARDING_DONE: dict[str, bool] = {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _normalize_provider(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "")


def _is_masked_secret(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return not text or text == "***" or "..." in text


def _persist_onboarding_api_keys(
    *,
    operator_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Move validated wizard API keys into the runtime KeyVault.

    Step 2 keeps raw keys only in browser/local wizard state. Completing
    onboarding is the point where the runtime must become usable. We only
    persist keys that the operator validated successfully and did not block.
    """
    rows = values.get("api_keys")
    if not isinstance(rows, list) or not rows:
        return {"attempted": 0, "stored": [], "reused": [], "skipped": [], "errors": []}

    blocked = {
        _normalize_provider(provider)
        for provider in values.get("blocked_providers", [])
        if str(provider or "").strip()
    }
    result: dict[str, Any] = {
        "attempted": 0,
        "stored": [],
        "reused": [],
        "skipped": [],
        "errors": [],
    }
    try:
        from sylion.security.key_vault import get_key_vault
        vault = get_key_vault()
    except Exception as exc:  # pragma: no cover - startup wiring failure.
        for row in rows:
            if isinstance(row, dict) and row.get("key"):
                result["errors"].append({
                    "provider": _normalize_provider(row.get("provider")),
                    "reason": f"key_vault_unavailable:{type(exc).__name__}",
                })
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = _normalize_provider(row.get("provider"))
        key = row.get("key")
        status = str(row.get("validation_status") or "").strip().lower()
        if not provider or not isinstance(key, str) or not key.strip():
            continue
        if provider in blocked:
            result["skipped"].append({"provider": provider, "reason": "blocked_by_operator"})
            continue
        if _is_masked_secret(key):
            result["skipped"].append({"provider": provider, "reason": "masked_or_empty_secret"})
            continue
        if status not in {"ok", "valid", "success", "phase1_shortcut"}:
            result["skipped"].append({
                "provider": provider,
                "reason": f"not_validated:{status or 'missing'}",
            })
            continue

        result["attempted"] += 1
        try:
            reused_id = None
            for existing in vault.list_keys(provider=provider):
                key_id = existing.get("key_id")
                if not key_id:
                    continue
                if vault.get_decrypted_key(str(key_id)) == key:
                    reused_id = str(key_id)
                    break
            if reused_id:
                vault.activate_key(reused_id)
                result["reused"].append({"provider": provider, "key_id": reused_id})
                continue

            record = vault.store_key(
                provider,
                key,
                display_name=f"{provider} (advisor onboarding)",
                metadata={
                    "source": "advisor_onboarding",
                    "operator_id": operator_id,
                    "validation_status": status,
                    "validation_info": row.get("validation_info") or {},
                    "stored_at": time.time(),
                },
            )
            key_id = str(record.get("key_id") or "")
            if key_id:
                vault.activate_key(key_id)
            result["stored"].append({"provider": provider, "key_id": key_id})
        except Exception as exc:  # noqa: BLE001
            log.warning("onboarding key persistence failed provider=%s: %s", provider, exc, exc_info=True)
            result["errors"].append({"provider": provider, "reason": type(exc).__name__})

    return result


def _persist_onboarding_connectors(
    *,
    operator_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Move wizard hosting credentials into the persistent connector store."""
    rows = values.get("hosting_providers")
    if not isinstance(rows, list) or not rows:
        return {"attempted": 0, "registered": [], "skipped": [], "errors": []}

    result: dict[str, Any] = {"attempted": 0, "registered": [], "skipped": [], "errors": []}
    try:
        from sylion.security.cloud_connectors import get_cloud_connector_store
        store = get_cloud_connector_store()
    except Exception as exc:  # pragma: no cover - startup wiring failure.
        for row in rows:
            if isinstance(row, dict) and row.get("provider"):
                result["errors"].append({
                    "provider": _normalize_provider(row.get("provider")),
                    "reason": f"connector_store_unavailable:{type(exc).__name__}",
                })
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = _normalize_provider(row.get("provider"))
        fields = row.get("fields")
        if not provider or not isinstance(fields, dict):
            continue
        credentials = {
            str(k): str(v).strip()
            for k, v in fields.items()
            if isinstance(v, (str, int, float)) and str(v).strip()
        }
        if not credentials:
            result["skipped"].append({"provider": provider, "reason": "missing_credentials"})
            continue
        if any(_is_masked_secret(v) for v in credentials.values()):
            result["skipped"].append({"provider": provider, "reason": "masked_secret"})
            continue

        result["attempted"] += 1
        scope = str(credentials.get("project") or values.get("custom_domain_prefix") or operator_id)
        name = f"{provider} (advisor onboarding)"
        try:
            upsert = getattr(store, "upsert", None)
            record = (upsert or store.register)(
                provider=provider,
                name=name,
                credentials=credentials,
                scope=scope,
            )
            result["registered"].append({
                "provider": provider,
                "connector_id": record.get("connector_id"),
                "scope": scope,
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("onboarding connector persistence failed provider=%s: %s", provider, exc, exc_info=True)
            result["errors"].append({"provider": provider, "reason": type(exc).__name__})

    return result


def _split_routing_models(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.replace(",", "+").split("+") if part.strip()]


def _infer_model_provider(model_id: str, installed_local: set[str]) -> str:
    lowered = model_id.lower()
    if model_id in installed_local or any(
        token in lowered
        for token in ("qwen", "llama", "mistral", "gemma", "phi", "gpt-oss")
    ):
        return "ollama"
    if lowered.startswith("claude"):
        return "anthropic"
    if lowered.startswith("gpt"):
        return "openai"
    if lowered.startswith("sonar"):
        return "perplexity"
    if lowered.startswith("glm"):
        return "zai"
    if "openrouter" in lowered:
        return "openrouter"
    return ""


def _model_budget_limits(values: dict[str, Any], provider: str) -> tuple[float, float]:
    ceilings = values.get("cost_ceilings")
    if provider == "ollama":
        return 0.0, 0.0
    if not isinstance(ceilings, dict):
        return 0.25, 5.0
    daily = float(ceilings.get("medium") or ceilings.get("low") or 0.25)
    monthly = float(ceilings.get("critical") or ceilings.get("high") or daily * 20 or 5.0)
    return max(daily, 0.0), max(monthly, 0.0)


def _persist_onboarding_model_plane(
    *,
    operator_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Seed model registry, budgets and council roles from onboarding.

    API keys alone are not enough for AEIS. The model control plane must see
    registered models, budget rows and council members before ideas can be
    deliberated by the configured Council.
    """
    result: dict[str, Any] = {
        "models_registered": [],
        "budgets_set": [],
        "council_members": [],
        "errors": [],
    }
    try:
        from sylion.api.ai_providers_routes import DEFAULT_MODELS
        from sylion.cognitive.model_registry import get_model_registry
        from sylion.monitoring.model_budget import get_model_budget
        from sylion.security.key_vault import get_key_vault

        registry = get_model_registry()
        budget = get_model_budget()
        vault = get_key_vault()
    except Exception as exc:  # pragma: no cover - startup wiring failure.
        result["errors"].append({"plane": "model_control", "reason": type(exc).__name__})
        return result

    active_providers = {
        str(row.get("provider") or "").strip().lower()
        for row in vault.list_keys()
        if row.get("is_active")
    }
    installed_local = {
        str(row.get("name") or "").strip()
        for row in values.get("local_models", [])
        if isinstance(row, dict) and row.get("status") == "installed" and row.get("name")
    }
    model_specs: dict[str, dict[str, Any]] = {}
    for provider in sorted(active_providers):
        model_id = DEFAULT_MODELS.get(provider)
        if not model_id:
            continue
        model_specs[model_id] = {
            "provider": provider,
            "display_name": f"{provider}:{model_id}",
            "source": "active_provider",
        }
    for model_id in sorted(installed_local):
        model_specs[model_id] = {
            "provider": "ollama",
            "display_name": model_id,
            "source": "local_ollama",
        }
    routing = values.get("llm_judge_routing")
    if isinstance(routing, dict):
        for risk, raw_model in routing.items():
            for model_id in _split_routing_models(raw_model):
                provider = _infer_model_provider(model_id, installed_local)
                if provider == "ollama" or provider in active_providers:
                    model_specs.setdefault(model_id, {
                        "provider": provider,
                        "display_name": f"{provider}:{model_id}" if provider else model_id,
                        "source": f"llm_judge_{risk}",
                    })

    for model_id, spec in sorted(model_specs.items()):
        provider = str(spec.get("provider") or "")
        try:
            registry.register_model(
                model_id=model_id,
                provider=provider,
                display_name=str(spec.get("display_name") or model_id),
                config_json=json.dumps({
                    "source": "advisor_onboarding",
                    "operator_id": operator_id,
                    "locality": "local" if provider == "ollama" else "cloud",
                    "selection_source": spec.get("source"),
                }, sort_keys=True),
            )
            daily, monthly = _model_budget_limits(values, provider)
            budget.set_budget(
                model_id=model_id,
                daily_limit=daily,
                monthly_limit=monthly,
                alert_threshold_pct=80.0,
                provider=provider,
                fallback_model_id="",
            )
            result["models_registered"].append({"model_id": model_id, "provider": provider})
            result["budgets_set"].append({"model_id": model_id, "provider": provider})
        except Exception as exc:  # noqa: BLE001
            log.warning("onboarding model-plane persistence failed model=%s: %s", model_id, exc, exc_info=True)
            result["errors"].append({"model_id": model_id, "reason": type(exc).__name__})

    preferred_roles = [
        ("planner", "openai", 100, "primary", 1.0, "planning"),
        ("critic", "anthropic", 90, "primary", 1.2, "critic_signature"),
        ("research", "perplexity", 80, "support", 0.8, "web_research"),
        ("engineer", "zai", 70, "primary", 1.0, "implementation"),
        ("cost_sentinel", "openrouter", 60, "support", 0.4, "cost_sentinel"),
        ("local_verifier", "ollama", 50, "validation_only", 0.5, "offline_verification"),
    ]
    max_members = int(values.get("council_size") or 5)
    chosen = 0
    for role, provider, priority, rank, weight, specialization in preferred_roles:
        if chosen >= max_members:
            break
        model_id = next(
            (
                mid
                for mid, spec in model_specs.items()
                if str(spec.get("provider") or "") == provider
            ),
            "",
        )
        if not model_id:
            continue
        try:
            member = vault.configure_council_member(
                f"onboarding-{role}",
                model_id,
                role,
                priority,
                None,
                rank=rank,
                voting_weight=weight,
                specialization=specialization,
                max_tokens=2048 if provider != "ollama" else 1024,
            )
            result["council_members"].append({
                "member_id": member.get("member_id"),
                "model_id": model_id,
                "role": role,
            })
            chosen += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("onboarding council member persistence failed role=%s: %s", role, exc, exc_info=True)
            result["errors"].append({"role": role, "reason": type(exc).__name__})

    return result


def _to_jsonable(value: Any) -> Any:
    """Convert dataclasses, datetimes, and nested structures to JSON-safe types."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return _to_jsonable(vars(value))
    return str(value)


def _operator_id(request: Request, fallback: str | None = None) -> str:
    user = getattr(request.state, "user", None) if hasattr(request, "state") else None
    return user or fallback or _DEFAULT_OPERATOR


def _card_event_topic(env: dict[str, Any]) -> str:
    header = env.get("header", {}) or {}
    body = env.get("body", {}) or {}
    metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
    return str(
        header.get("emitting_event_topic")
        or metadata.get("triggering_topic")
        or metadata.get("triggering_event_topic")
        or ""
    )


def _normalize_card_event_topics(envelopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for env in envelopes:
        if not isinstance(env, dict):
            continue
        header = env.setdefault("header", {})
        if isinstance(header, dict) and not header.get("emitting_event_topic"):
            topic = _card_event_topic(env)
            if topic:
                header["emitting_event_topic"] = topic
    return envelopes


def _is_backend_unavailable(exc: Exception) -> bool:
    name = type(exc).__name__
    detail = str(exc).lower()
    return (
        name in {
            "PoolTimeout",
            "OperationalError",
            "DatatypeMismatch",
            "InvalidTextRepresentation",
            "ForeignKeyViolation",
            "UndefinedFunction",
        }
        or "couldn't get a connection" in detail
        or "connection to server" in detail
        or "role \"razor\" does not exist" in detail
        or "invalid input syntax for type uuid" in detail
        or "violates foreign key constraint" in detail
        or "operator does not exist" in detail
    )


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@router.get("/cards")
def list_cards(
    request: Request,
    operator_id: str | None = Query(None),
    project_id: str | None = Query(None),
    include_resolved: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
):
    op = operator_id or _operator_id(request)
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        svc = get_engine_service()
        envelopes = svc.list_recommendations(operator_id=op, limit=limit)
    except Exception as exc:
        log.warning("advisor.list_cards failed: %s", exc, exc_info=True)
        envelopes = []
    if project_id:
        envelopes = [
            env for env in envelopes
            if (env.get("header", {}) or {}).get("project_id") == project_id
        ]
    if not include_resolved:
        envelopes = [
            env for env in envelopes
            if not _is_resolved_card(env)
        ]
    return {"cards": _to_jsonable(_normalize_card_event_topics(envelopes))}


@router.get("/cards/{card_id}")
def get_card(card_id: str):
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        svc = get_engine_service()
        env = svc.get_recommendation(card_id=card_id)
    except Exception as exc:
        log.warning("advisor.get_card failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {"card_id": card_id, "card": None, "status": "backend_unavailable"}
        raise HTTPException(status_code=500, detail=str(exc))
    if env is None:
        raise HTTPException(status_code=404, detail=f"card {card_id} not found")
    return _to_jsonable(env)


@router.post("/cards/{card_id}/actions")
def handle_card_action(
    request: Request,
    card_id: str,
    payload: dict[str, Any] = Body(...),
):
    action = str(payload.get("action") or "").strip()
    if not action:
        raise HTTPException(status_code=400, detail="action is required")
    op = _operator_id(request, payload.get("operator_id"))

    from sylion.aeis.advisor.actions.service import get_actions_service
    from types import SimpleNamespace

    req = SimpleNamespace(
        card_id=card_id,
        action=action,
        operator_id=op,
        operator_note=payload.get("operator_note") or "",
        modified_recommendation=payload.get("modified_recommendation") or "",
        preference_key=payload.get("preference_key") or "",
        preference_project_type=payload.get("preference_project_type") or "",
        preference_project_domain=payload.get("preference_project_domain") or "",
        preference_value=payload.get("preference_value"),
        dont_learn_flag=bool(payload.get("dont_learn_flag", False)),
    )
    try:
        result = get_actions_service().HandleAction(req)
    except Exception as exc:
        log.warning("advisor.handle_action failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {
                "card_id": card_id,
                "action": action,
                "accepted": False,
                "status": "backend_unavailable",
            }
        raise HTTPException(status_code=500, detail=f"action failed: {exc}")
    return _to_jsonable(result)


# ---------------------------------------------------------------------------
# Evidence packs
# ---------------------------------------------------------------------------


@router.get("/evidence/{pack_id}")
def get_evidence_pack(pack_id: str):
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        pack = get_engine_service().get_evidence_pack(pack_id=pack_id)
    except Exception as exc:
        log.warning("advisor.get_evidence_pack failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {"pack_id": pack_id, "pack": None, "status": "backend_unavailable"}
        raise HTTPException(status_code=500, detail=str(exc))
    if pack is None:
        raise HTTPException(status_code=404, detail=f"evidence pack {pack_id} not found")
    return _to_jsonable(pack)


@router.post("/evidence/{pack_id}/finalize")
def finalize_evidence_pack(pack_id: str, payload: dict[str, Any] = Body(default={})):
    _ = payload  # edits not yet supported
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        ok = get_engine_service().finalize_evidence_pack(pack_id=pack_id)
    except Exception as exc:
        log.warning("advisor.finalize_evidence_pack failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {"ok": False, "pack_id": pack_id, "status": "backend_unavailable"}
        raise HTTPException(status_code=500, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail=f"evidence pack {pack_id} not found")
    return {"ok": True}


@router.post("/evidence/{pack_id}/sign")
def sign_evidence_pack(
    request: Request,
    pack_id: str,
    payload: dict[str, Any] = Body(...),
):
    signature = str(payload.get("signature_payload") or payload.get("signature") or "").strip()
    role = str(payload.get("signer_role") or "operator").strip()
    if not signature:
        raise HTTPException(status_code=400, detail="signature_payload is required")
    op = _operator_id(request, payload.get("signer_id"))
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        sig_id = get_engine_service().sign_evidence_pack(
            pack_id=pack_id,
            signer_id=op,
            signer_role=role,
            signature_payload=signature,
        )
    except Exception as exc:
        log.warning("advisor.sign_evidence_pack failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {
                "signature_id": None,
                "pack_id": pack_id,
                "status": "backend_unavailable",
            }
        raise HTTPException(status_code=500, detail=str(exc))
    return {"signature_id": sig_id}


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


@router.get("/preferences")
def list_preferences(
    request: Request,
    user_id: str | None = Query(None),
    project_type: str | None = Query(None),
    project_domain: str | None = Query(None),
    preference_key: str | None = Query(None),
):
    op = user_id or _operator_id(request)
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        prefs = PreferencesService().list_preferences(
            user_id=op,
            project_type=project_type,
            project_domain=project_domain,
            preference_key=preference_key,
        )
    except Exception as exc:
        log.warning("advisor.list_preferences failed: %s", exc, exc_info=True)
        prefs = []
    return {"preferences": _to_jsonable(prefs)}


@router.put("/preferences/{key}")
def set_preference(
    request: Request,
    key: str,
    payload: dict[str, Any] = Body(...),
):
    op = _operator_id(request, payload.get("user_id"))
    from sylion.aeis.advisor.preferences import catalog
    from sylion.aeis.advisor.preferences.service import PreferencesService
    meta = catalog.get_preference_key_metadata(key)
    if meta is None:
        return _to_jsonable({
            "user_id": op,
            "project_type": payload.get("project_type"),
            "project_domain": payload.get("project_domain"),
            "preference_key": key,
            "preference_value": payload.get("value"),
            "set_by": payload.get("set_by") or "user",
            "updated_at": time.time(),
            "result": {
                "success": False,
                "requires_hard_confirmation": False,
                "hard_change_request_id": "",
                "error_message": "unknown preference key",
                "status": "unknown_preference_key",
            },
        })
    try:
        result = PreferencesService().set_preference(
            user_id=op,
            project_type=payload.get("project_type"),
            project_domain=payload.get("project_domain"),
            preference_key=key,
            value=payload.get("value"),
            set_by=payload.get("set_by") or "user",
            reason=payload.get("reason"),
            bypass_hard_check=bool(payload.get("bypass_hard_check", False)),
        )
    except Exception as exc:
        log.warning("advisor.set_preference failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return _to_jsonable({
                "user_id": op,
                "project_type": payload.get("project_type"),
                "project_domain": payload.get("project_domain"),
                "preference_key": key,
                "preference_value": payload.get("value"),
                "set_by": payload.get("set_by") or "user",
                "updated_at": time.time(),
                "result": {
                    "success": False,
                    "requires_hard_confirmation": False,
                    "hard_change_request_id": "",
                    "error_message": str(exc),
                    "status": "backend_unavailable",
                },
            })
        raise HTTPException(status_code=500, detail=str(exc))
    return _to_jsonable({
        "user_id": op,
        "project_type": payload.get("project_type"),
        "project_domain": payload.get("project_domain"),
        "preference_key": key,
        "preference_value": payload.get("value"),
        "set_by": payload.get("set_by") or "user",
        "updated_at": time.time(),
        "result": result,
    })


@router.delete("/preferences/{key}")
def reset_preference(
    request: Request,
    key: str,
    payload: dict[str, Any] = Body(default={}),
):
    op = _operator_id(request, payload.get("user_id"))
    from sylion.aeis.advisor.preferences.service import PreferencesService
    ok = PreferencesService().reset_preference(
        user_id=op,
        project_type=payload.get("project_type"),
        project_domain=payload.get("project_domain"),
        preference_key=key,
        reason=payload.get("reason"),
    )
    return {"ok": bool(ok)}


@router.get("/preferences/audit")
def preferences_audit(
    request: Request,
    user_id: str | None = Query(None),
    key: str | None = Query(None, alias="key"),
    limit: int = Query(100, ge=1, le=1000),
):
    op = user_id or _operator_id(request)
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        entries = PreferencesService().get_audit(user_id=op, limit=limit, preference_key=key)
    except Exception as exc:
        log.warning("advisor.preferences_audit failed: %s", exc, exc_info=True)
        entries = []
    return {"entries": _to_jsonable(entries)}


@router.get("/preferences/counts")
def preferences_counts():
    try:
        from sylion.aeis.advisor.engine import _db as engine_db

        counts = engine_db.fetch_configuration_counts()
    except Exception as exc:
        log.warning("advisor.preferences_counts failed: %s", exc, exc_info=True)
        counts = {
            "api_keys": 0,
            "local_models": 0,
            "routing_rules": 0,
            "skills": 0,
        }
    return counts


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


def _default_state() -> dict[str, Any]:
    return {"step": 1, "completed_steps": [], "values": {}}


def _read_onboarding_state(operator_id: str) -> dict[str, Any]:
    """Read wizard state, preferring volatile raw cache during active setup."""
    cached = _ONBOARDING_CACHE.get(operator_id)
    if isinstance(cached, dict):
        return deepcopy(cached)
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        row = PreferencesService().get_explicit(
            user_id=operator_id,
            project_type=None,
            project_domain=None,
            preference_key=_ONBOARDING_STATE_KEY,
        )
    except Exception:
        log.debug("onboarding read fell back to cache", exc_info=True)
        row = None

    if row is None:
        return dict(_ONBOARDING_CACHE.get(operator_id, _default_state()))

    raw = row.preference_value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return dict(_ONBOARDING_CACHE.get(operator_id, _default_state()))
    if not isinstance(raw, dict):
        return dict(_ONBOARDING_CACHE.get(operator_id, _default_state()))
    raw.setdefault("step", 1)
    raw.setdefault("completed_steps", [])
    raw.setdefault("values", {})
    return raw


def _write_onboarding_state(operator_id: str, state: dict[str, Any]) -> None:
    """Write wizard state without persisting raw credentials.

    The in-process cache may temporarily hold raw keys so a multi-step wizard
    can complete and move them into KeyVault/connectors. Persistent preferences,
    API responses and audit rows must only receive the redacted copy.
    """
    _ONBOARDING_CACHE[operator_id] = deepcopy(state)
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        PreferencesService().set_preference(
            user_id=operator_id,
            project_type=None,
            project_domain=None,
            preference_key=_ONBOARDING_STATE_KEY,
            value=_redact_onboarding_state(state),
            set_by="wizard",
            bypass_hard_check=True,
        )
    except Exception:
        log.debug("onboarding write deferred to cache", exc_info=True)


def _reset_onboarding_state(operator_id: str) -> dict[str, Any]:
    """Clear persisted first-run state for a clean Phase 1 pass."""
    _ONBOARDING_CACHE.pop(operator_id, None)
    _ONBOARDING_DONE.pop(operator_id, None)
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService

        prefs = PreferencesService()
        for key in (
            _ONBOARDING_STATE_KEY,
            _ONBOARDING_COMPLETED_KEY,
            _PHASE1_COMPLETED_KEY,
            "operator_name",
            "display_name",
            "system_name",
            "operator_email",
            "operator_role",
            "timezone",
            "language",
            "workspace_path",
            "backup_frequency",
            "backup_retention_days",
            "security_mode",
            "goals",
            "initial_autonomy_preset",
            "tutorial_mode",
            "tutorial_project",
            "notification_channel",
            "telemetry_consent",
        ):
            try:
                prefs.reset_preference(
                    user_id=operator_id,
                    project_type=None,
                    project_domain=None,
                    preference_key=key,
                    reason="phase1_reset",
                )
            except Exception:
                log.debug("phase1 reset skipped preference %s", key, exc_info=True)
    except Exception:
        log.debug("phase1 reset preferences unavailable", exc_info=True)
    return _default_state()


def _looks_like_masked_secret(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return stripped == "***" or "..." in stripped or "…" in stripped


def _merge_api_key_values(existing_values: dict[str, Any], new_values: dict[str, Any]) -> dict[str, Any]:
    """Merge wizard patches without letting redacted API keys destroy raw keys."""
    if "api_keys" not in new_values or not isinstance(new_values.get("api_keys"), list):
        return {**existing_values, **new_values}

    merged_values = {**existing_values, **new_values}
    existing_rows = existing_values.get("api_keys")
    if not isinstance(existing_rows, list):
        return merged_values

    by_id = {
        str(row.get("id")): row
        for row in existing_rows
        if isinstance(row, dict) and row.get("id")
    }
    by_provider = {
        str(row.get("provider")): row
        for row in existing_rows
        if isinstance(row, dict) and row.get("provider")
    }

    merged_rows: list[Any] = []
    for incoming in new_values.get("api_keys") or []:
        if not isinstance(incoming, dict):
            merged_rows.append(incoming)
            continue
        incoming_key = incoming.get("key")
        is_masked = bool(incoming.get("key_masked")) or _looks_like_masked_secret(incoming_key)
        if not is_masked:
            merged_rows.append(incoming)
            continue
        previous = by_id.get(str(incoming.get("id"))) or by_provider.get(str(incoming.get("provider")))
        if not isinstance(previous, dict) or _looks_like_masked_secret(previous.get("key")):
            merged_rows.append(incoming)
            continue
        restored = {**previous, **incoming, "key": previous.get("key")}
        restored.pop("key_masked", None)
        if incoming.get("validation_status") in {"error", "testing"} and previous.get("validation_status") == "ok":
            restored["validation_status"] = "ok"
            restored["validation_info"] = previous.get("validation_info")
        merged_rows.append(restored)

    merged_values["api_keys"] = merged_rows
    return merged_values


def _has_completed_onboarding(operator_id: str) -> bool:
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        phase1_row = PreferencesService().get_explicit(
            user_id=operator_id,
            project_type=None,
            project_domain=None,
            preference_key=_PHASE1_COMPLETED_KEY,
        )
        if phase1_row and phase1_row.preference_value:
            return True
        row = PreferencesService().get_explicit(
            user_id=operator_id,
            project_type=None,
            project_domain=None,
            preference_key=_ONBOARDING_COMPLETED_KEY,
        )
    except Exception:
        row = None
    completed = bool(row and row.preference_value)
    if not completed:
        completed = bool(_ONBOARDING_DONE.get(operator_id, False))
    return completed


@router.get("/onboarding/phase1/system-check")
def phase1_system_check(request: Request, user_id: str | None = Query(None)):
    op = user_id or _operator_id(request)
    state = _read_onboarding_state(op)
    values = state.get("values") if isinstance(state.get("values"), dict) else {}
    return _phase1_system_check(values)


@router.post("/onboarding/phase1/storage/validate")
def phase1_validate_storage(
    request: Request,
    payload: dict[str, Any] = Body(default={}),
    user_id: str | None = Query(None),
):
    op = user_id or _operator_id(request, payload.get("user_id"))
    state = _read_onboarding_state(op)
    values = state.get("values") if isinstance(state.get("values"), dict) else {}
    path_value = payload.get("path") or values.get("workspace_path") or _phase1_default_workspace(values)
    validation = _phase1_storage_validation(path_value, values)
    state["values"] = {
        **values,
        "workspace_path": validation["path"],
        "storage_validation": validation,
    }
    _write_onboarding_state(op, state)
    _emit_advisor_audit(
        "phase_1.storage.validated",
        module="phase_1.onboarding",
        user_id=op,
        details={
            "path": validation["path"],
            "ok": validation["ok"],
            "warnings": validation.get("warnings", []),
            "errors": validation.get("errors", []),
        },
    )
    return validation


@router.get("/onboarding/phase1/model-gate")
def phase1_model_gate(
    request: Request,
    user_id: str | None = Query(None),
    run_test: bool = Query(False),
):
    op = user_id or _operator_id(request)
    state = _read_onboarding_state(op)
    values = state.get("values") if isinstance(state.get("values"), dict) else {}
    gate = _phase1_model_gate(values, run_test=run_test)
    state["values"] = {**values, "phase1_model_gate": gate}
    _write_onboarding_state(op, state)
    return gate


@router.post("/onboarding/phase1/complete")
def complete_phase1_onboarding(
    request: Request,
    payload: dict[str, Any] = Body(default={}),
    user_id: str | None = Query(None),
):
    op = user_id or _operator_id(request, payload.get("user_id"))
    state = _read_onboarding_state(op)
    values = state.get("values") if isinstance(state.get("values"), dict) else {}
    new_values = payload.get("values") or {}
    if isinstance(new_values, dict):
        values = _merge_api_key_values(values, new_values)
        state["values"] = values

    storage = values.get("storage_validation") if isinstance(values.get("storage_validation"), dict) else {}
    if not storage.get("ok"):
        storage = _phase1_storage_validation(values.get("workspace_path"), values)
        values["workspace_path"] = storage["path"]
        values["storage_validation"] = storage

    checks = _phase1_core_checks(state)
    failed = [check for check in checks if not check.get("ok")]
    if failed:
        _write_onboarding_state(op, state)
        raise HTTPException(status_code=400, detail={
            "message": "phase 1 acceptance checks failed",
            "failed": failed,
            "checks": checks,
        })

    workspace = _phase1_bootstrap_workspace(values)
    state["values"] = {
        **values,
        "workspace_path": workspace["workspace_path"],
        "notification_channel": values.get("notification_channel") or "in_app",
        "telemetry_consent": bool(values.get("telemetry_consent")),
    }
    state["completed_at"] = time.time()
    state["phase1_completed_at"] = state["completed_at"]
    _write_onboarding_state(op, state)
    _ONBOARDING_DONE[op] = True

    for step in range(1, 9):
        _emit_phase1_chain(op, f"phase_1.step_{step}.complete", {"step": step})
    _emit_phase1_chain(op, "phase_1.complete", {"workspace_path": workspace["workspace_path"]})
    _emit_advisor_audit(
        "phase_1.completed",
        module="phase_1.onboarding",
        user_id=op,
        details={
            "workspace_path": workspace["workspace_path"],
            "completed_steps": state.get("completed_steps") or [],
            "model_gate": _phase1_model_gate(state["values"], run_test=False),
        },
    )

    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        prefs = PreferencesService()
        prefs.set_preference(
            user_id=op,
            project_type=None,
            project_domain=None,
            preference_key=_PHASE1_COMPLETED_KEY,
            value=True,
            set_by="phase1",
            bypass_hard_check=True,
        )
        prefs.set_preference(
            user_id=op,
            project_type=None,
            project_domain=None,
            preference_key=_ONBOARDING_COMPLETED_KEY,
            value=True,
            set_by="phase1",
            bypass_hard_check=True,
        )
        for key in (
            "operator_name",
            "display_name",
            "system_name",
            "operator_email",
            "operator_role",
            "timezone",
            "language",
            "workspace_path",
            "backup_frequency",
            "backup_retention_days",
            "security_mode",
            "goals",
            "initial_autonomy_preset",
            "tutorial_mode",
            "tutorial_project",
            "notification_channel",
            "telemetry_consent",
        ):
            if key in state["values"]:
                prefs.set_preference(
                    user_id=op,
                    project_type=None,
                    project_domain=None,
                    preference_key=key,
                    value=state["values"][key],
                    set_by="phase1",
                    bypass_hard_check=True,
                )
    except Exception:
        log.warning("phase1 preference fan-out failed", exc_info=True)

    response = _redact_onboarding_state(state)
    response["phase1_acceptance"] = _phase1_acceptance_report(op, state)
    response["workspace_bootstrap"] = workspace
    return response


@router.get("/onboarding/phase1/acceptance-test")
def phase1_acceptance_test(request: Request, user_id: str | None = Query(None)):
    op = user_id or _operator_id(request)
    state = _read_onboarding_state(op)
    return _phase1_acceptance_report(op, state)


@router.get("/onboarding/state")
def get_onboarding_state(request: Request, user_id: str | None = Query(None)):
    op = user_id or _operator_id(request)
    return _redact_onboarding_state(_read_onboarding_state(op))


@router.delete("/onboarding/state")
def reset_onboarding_state(request: Request, user_id: str | None = Query(None)):
    op = user_id or _operator_id(request)
    fresh = _reset_onboarding_state(op)
    _emit_advisor_audit(
        "phase_1.reset",
        module="phase_1.onboarding",
        user_id=op,
        details={"reason": "operator_requested_clean_run"},
    )
    return fresh


@router.put("/onboarding/step/{step}")
def save_onboarding_step(
    request: Request,
    step: int,
    payload: dict[str, Any] = Body(...),
    user_id: str | None = Query(None),
):
    op = user_id or _operator_id(request, payload.get("user_id"))
    state = _read_onboarding_state(op)
    new_values = payload.get("values") or {}
    state["values"] = _merge_api_key_values(
        state.get("values", {}) if isinstance(state.get("values"), dict) else {},
        new_values if isinstance(new_values, dict) else {},
    )
    completed = set(state.get("completed_steps") or [])
    completed.add(int(step))
    state["completed_steps"] = sorted(completed)
    state["step"] = int(step)
    _write_onboarding_state(op, state)
    _emit_advisor_audit(
        "advisor.onboarding.step_saved",
        module="advisor.onboarding",
        user_id=op,
        details={"step": int(step), **_summarize_onboarding_values(new_values)},
    )
    return _redact_onboarding_state(state)


@router.post("/onboarding/complete")
def complete_onboarding(
    request: Request,
    payload: dict[str, Any] = Body(default={}),
    user_id: str | None = Query(None),
):
    op = user_id or _operator_id(request, payload.get("user_id"))
    state = _read_onboarding_state(op)
    new_values = payload.get("values") or {}
    if isinstance(new_values, dict):
        state["values"] = _merge_api_key_values(
            state.get("values", {}) if isinstance(state.get("values"), dict) else {},
            new_values,
        )
    state["completed_at"] = time.time()
    runtime_setup = {
        "api_keys": _persist_onboarding_api_keys(
            operator_id=op,
            values=state.get("values") or {},
        ),
        "connectors": _persist_onboarding_connectors(
            operator_id=op,
            values=state.get("values") or {},
        ),
        "model_plane": _persist_onboarding_model_plane(
            operator_id=op,
            values=state.get("values") or {},
        ),
    }
    runtime_errors = [
        *runtime_setup["api_keys"].get("errors", []),
        *runtime_setup["connectors"].get("errors", []),
        *runtime_setup["model_plane"].get("errors", []),
    ]
    if runtime_errors:
        _emit_advisor_audit(
            "advisor.onboarding.runtime_persist_failed",
            module="advisor.onboarding",
            user_id=op,
            details={
                "api_key_error_count": len(runtime_setup["api_keys"].get("errors", [])),
                "connector_error_count": len(runtime_setup["connectors"].get("errors", [])),
                "model_plane_error_count": len(runtime_setup["model_plane"].get("errors", [])),
                "providers": sorted({
                    str(item.get("provider") or "")
                    for item in runtime_errors
                    if isinstance(item, dict) and item.get("provider")
                }),
            },
        )
        raise HTTPException(status_code=500, detail={
            "message": "onboarding runtime persistence failed",
            "runtime_setup": runtime_setup,
        })

    _write_onboarding_state(op, state)
    _ONBOARDING_DONE[op] = True
    _emit_advisor_audit(
        "advisor.onboarding.completed",
        module="advisor.onboarding",
        user_id=op,
        details={
            "completed_steps": state.get("completed_steps") or [],
            "runtime_setup": {
                "api_key_attempted": runtime_setup["api_keys"].get("attempted", 0),
                "api_key_stored": len(runtime_setup["api_keys"].get("stored", [])),
                "api_key_reused": len(runtime_setup["api_keys"].get("reused", [])),
                "api_key_skipped": len(runtime_setup["api_keys"].get("skipped", [])),
                "connector_attempted": runtime_setup["connectors"].get("attempted", 0),
                "connector_registered": len(runtime_setup["connectors"].get("registered", [])),
                "connector_skipped": len(runtime_setup["connectors"].get("skipped", [])),
                "models_registered": len(runtime_setup["model_plane"].get("models_registered", [])),
                "budgets_set": len(runtime_setup["model_plane"].get("budgets_set", [])),
                "council_members": len(runtime_setup["model_plane"].get("council_members", [])),
            },
            **_summarize_onboarding_values(state.get("values") or {}),
        },
    )

    # Persist the "I'm onboarded" flag separately so the first-run banner can
    # query a single flat key.
    try:
        from sylion.aeis.advisor.preferences.service import PreferencesService
        PreferencesService().set_preference(
            user_id=op,
            project_type=None,
            project_domain=None,
            preference_key=_ONBOARDING_COMPLETED_KEY,
            value=True,
            set_by="wizard",
            bypass_hard_check=True,
        )

        # Best-effort: persist the wizard answers as individual preferences so
        # the advisor cascade can read them. Non-fatal on failure.
        applied: list[str] = []
        for key in (
            "default_project_domain",
            "autonomy_level",
            "council_size",
            "quality_speed_cost",
            "trusted_providers",
            "blocked_providers",
            "funding_advisor_enabled",
            "funding_countries",
            "funding_pl_regions",
            "funding_model_profile",
            "cost_ceilings",
            "llm_judge_routing",
            "operator_name",
            "goals",
            "usage_cadence",
        ):
            if key in state["values"]:
                try:
                    PreferencesService().set_preference(
                        user_id=op,
                        project_type=None,
                        project_domain=None,
                        preference_key=key,
                        value=state["values"][key],
                        set_by="wizard",
                        bypass_hard_check=True,
                    )
                    applied.append(key)
                except Exception:
                    log.debug("wizard fan-out failed for %s", key, exc_info=True)
        log.info("onboarding complete: applied %d preferences for %s", len(applied), op)
    except Exception:
        log.warning("onboarding flag write failed", exc_info=True)
    response = _redact_onboarding_state(state)
    response["runtime_setup"] = runtime_setup
    return response


@router.get("/onboarding/has_completed")
def has_completed_onboarding(request: Request, user_id: str | None = Query(None)):
    op = user_id or _operator_id(request)
    return {"completed": _has_completed_onboarding(op)}


@router.get("/preferences/{user_id}/has_completed_onboarding")
def has_completed_onboarding_legacy(user_id: str):
    return {"completed": _has_completed_onboarding(user_id)}


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------


_DEFAULT_HOOKS = [
    "aeis.system.model_setup_requested",
    "aeis.system.api_provider_setup_requested",
    "aeis.system.budget_config_requested",
    "aeis.idea.intake.completed",
    "aeis.idea.sot_model_selection_requested",
    "aeis.council.formation_requested",
    "aeis.system.autonomy_policy_change_requested",
    "aeis.idea.sot_drafted",
    "aeis.masterplan.created",
    "aeis.system.runtime_topology_change_requested",
    "aeis.system.vps_scaling_requested",
    "aeis.system.skill_selection_requested",
    "aeis.production.deploy_requested",
    "aeis.testing.started",
    "aeis.human_gate.ticket_pending",
    "aeis.final_approval.requested",
]


@router.get("/audit/recent")
def recent_audit(limit: int = Query(5, ge=1, le=50), user_id: str = Query("default")):
    _ = user_id
    entries = _read_recent_chain_entries(limit=limit)
    if entries:
        return {"entries": _to_jsonable(entries)}
    try:
        from sylion.aeis.advisor.engine import _db as engine_db

        entries = engine_db.fetch_recent_audit_entries(limit=limit)
    except Exception as exc:
        log.warning("advisor.recent_audit failed: %s", exc, exc_info=True)
        entries = []
    return {"entries": _to_jsonable(entries)}


@router.get("/projects/{project_id}/lifecycle")
def get_project_lifecycle(project_id: str):
    """Return the 16-hook lifecycle view for a project.

    Cards are filtered by `header.project_id` and grouped by the event topic
    recorded by the AdvisorEngine decision body metadata.
    """
    cards: list[dict[str, Any]] = []
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        envelopes = get_engine_service().list_recommendations(operator_id=_DEFAULT_OPERATOR, limit=200)
        cards = _normalize_card_event_topics([
            env for env in envelopes
            if (env.get("header", {}) or {}).get("project_id") == project_id
        ])
    except Exception:
        cards = []

    by_hook: dict[str, list[dict[str, Any]]] = {h: [] for h in _DEFAULT_HOOKS}
    for env in cards:
        topic = _card_event_topic(env)
        if topic in by_hook:
            by_hook[topic].append(env)

    phases = []
    for idx, topic in enumerate(_DEFAULT_HOOKS, start=1):
        bucket = by_hook.get(topic, [])
        latest = max(
            (
                float((env.get("header", {}) or {}).get("created_at") or 0)
                for env in bucket
                if isinstance(env, dict)
            ),
            default=0.0,
        )
        phases.append({
            "hook_id": f"H{idx:02d}",
            "hook_event_type": topic,
            "status": _phase_status_for_cards(bucket),
            "cards": _to_jsonable(bucket),
            "last_event_at": latest or None,
        })

    first_header = (cards[0].get("header", {}) if cards else {}) or {}
    return {
        "project_id": project_id,
        "project_type": first_header.get("project_type") or "",
        "project_domain": first_header.get("project_domain") or "",
        "phases": phases,
    }


# ---------------------------------------------------------------------------
# Operator monitoring snapshot
# ---------------------------------------------------------------------------


@router.get("/monitoring/snapshot")
def monitoring_snapshot(request: Request):
    """Honest snapshot. Returns whatever data the engine has; empty arrays
    rather than synthetic mock numbers when nothing is recorded yet.
    """
    op = _operator_id(request)
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
        envelopes = get_engine_service().list_recommendations(operator_id=op, limit=500)
    except Exception:
        envelopes = []

    strategy = "Balanced"
    active_teams = 0
    avg_confidence = 0.0
    pending_hg = 0
    hg_breakdown = ""

    try:
        from sylion.aeis.advisor.orchestration_config.service import get_orchestration_service

        routing = get_orchestration_service().get_llm_routing()
        preset = str(getattr(routing, "preset", "") or "").strip().lower()
        strategy = {
            "cost-saving": "Cost-saving",
            "balanced": "Balanced",
            "aggressive": "Aggressive",
            "database": "Balanced",
        }.get(preset, "Balanced")

        teams = get_orchestration_service().get_active_teams()
        active_teams = len(teams)
    except Exception:
        pass

    try:
        from sylion.aeis.advisor.engine import _db as engine_db

        avg_confidence = engine_db.fetch_avg_confidence(operator_id=op, limit=20)
        hg_metrics = engine_db.fetch_human_gate_metrics(operator_id=op)
        pending_hg = int(hg_metrics.get("pending_hg") or 0)
        hg_breakdown = str(hg_metrics.get("hg_breakdown") or "")
    except Exception as exc:
        log.warning("advisor.monitoring_metrics failed: %s", exc, exc_info=True)

    # Group by project_id
    project_index: dict[str, dict[str, Any]] = {}
    for env in envelopes:
        h = env.get("header", {}) or {}
        pid = h.get("project_id") or ""
        if not pid:
            continue
        slot = project_index.setdefault(pid, {
            "project_id": pid,
            "project_name": pid,
            "project_type": h.get("project_type") or "",
            "project_domain": h.get("project_domain") or "",
            "active_phase": "",
            "active_cards": 0,
            "accept_rate": 0.0,
            "spend_usd_month": 0.0,
            "budget_usd_month": 0.0,
        })
        slot["active_cards"] += 1

    alerts = []
    for env in envelopes:
        h = env.get("header", {}) or {}
        if h.get("risk_level") in ("high", "critical"):
            alerts.append({
                "id": f"alert-{h.get('card_id')}",
                "severity": h.get("risk_level"),
                "title": h.get("title", "(no title)"),
                "card_id": h.get("card_id"),
            })

    snapshot = {
        "strategy": strategy,
        "active_teams": active_teams,
        "avg_confidence": round(float(avg_confidence or 0.0), 4),
        "pending_hg": pending_hg,
        "hg_breakdown": hg_breakdown,
        "projects": list(project_index.values()),
        "throughput": [],
        "cost_vs_budget": {"spend_usd": 0.0, "budget_usd": 0.0, "per_project": {}},
        "council_activity": [],
        "subscription_recommendations": [],
        "alerts": alerts,
    }
    return _to_jsonable(snapshot)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions")
def list_subscriptions(
    request: Request,
    operator_id: str | None = Query(None),
):
    op = operator_id or _operator_id(request)
    try:
        from sylion.aeis.advisor.subscription import _db
        from sylion.aeis.advisor.subscription.quota_tracker import get_quota_status

        subs = _db.list_active_subscriptions(op)
        payload = []
        for sub in subs:
            covered_models = list(sub.get("models_covered") or [])
            quota_status = get_quota_status(op, covered_models[0]) if covered_models else None
            payload.append({
                **_to_jsonable(sub),
                "quota_status": _to_jsonable(quota_status._asdict()) if quota_status else None,
            })
        return {"subscriptions": payload}
    except Exception as exc:
        log.warning("advisor.list_subscriptions failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {"subscriptions": [], "status": "backend_unavailable"}
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/subscriptions")
def create_subscription(
    request: Request,
    payload: dict[str, Any] = Body(...),
    operator_id: str | None = Query(None),
):
    op = operator_id or _operator_id(request)
    provider_id = str(payload.get("provider_id") or "").strip()
    plan_id = str(payload.get("plan_id") or "").strip()
    if not provider_id or not plan_id:
        raise HTTPException(status_code=400, detail="provider_id and plan_id are required")
    try:
        from sylion.aeis.advisor.subscription import _db

        sub = _db.create_subscription(
            operator_id=op,
            provider_id=provider_id,
            plan_id=plan_id,
            monthly_quota_tokens=payload.get("monthly_quota_tokens"),
            monthly_quota_usd=payload.get("monthly_quota_usd"),
            reset_day_of_month=int(payload.get("reset_day_of_month") or 1),
            models_covered=[str(item) for item in payload.get("models_covered", [])],
            active_until=payload.get("active_until"),
            monthly_fee_usd=payload.get("monthly_fee_usd"),
            is_active=bool(payload.get("is_active", True)),
        )
    except Exception as exc:
        log.warning("advisor.create_subscription failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {"subscription_id": None, "status": "backend_unavailable"}
        raise HTTPException(status_code=500, detail=str(exc))
    return {"subscription_id": sub["subscription_id"]}


@router.delete("/subscriptions/{sub_id}")
def delete_subscription(sub_id: str):
    try:
        from sylion.aeis.advisor.subscription import _db

        deleted = _db.deactivate_subscription(sub_id)
    except Exception as exc:
        log.warning("advisor.delete_subscription failed: %s", exc, exc_info=True)
        if _is_backend_unavailable(exc):
            return {"ok": False, "status": "backend_unavailable"}
        raise HTTPException(status_code=500, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"subscription {sub_id} not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


@router.get("/funding/grants")
def list_funding_grants(
    country: str | None = Query(None),
    region: str | None = Query(None),
):
    try:
        from sylion.aeis.advisor.funding.service import get_funding_service
        grants = get_funding_service().list_grants(country=country, region=region)
    except Exception as exc:
        log.warning("advisor.list_grants failed: %s", exc, exc_info=True)
        grants = []
    serialized = []
    for g in grants:
        d = asdict(g) if is_dataclass(g) else _to_jsonable(g)
        serialized.append({
            "program_id": d.get("program_id", ""),
            "program_code": d.get("program_code", ""),
            "display_name": d.get("display_name", ""),
            "source": d.get("source", ""),
            "country": d.get("country", ""),
            "region": d.get("region") or None,
            "managing_body": d.get("managing_body") or None,
            "amount_min_usd": float(d.get("amount_min_usd", 0.0) or 0.0) or None,
            "amount_max_usd": float(d.get("amount_max_usd", 0.0) or 0.0) or None,
            "call_open_at": d.get("call_open_at") or None,
            "call_close_at": d.get("call_close_at") or None,
            "is_active": bool(d.get("is_active", True)),
        })
    return {"grants": serialized}


@router.get("/funding/deadlines")
def funding_deadlines():
    try:
        from sylion.aeis.advisor.funding.service import get_funding_service
        grants = get_funding_service().list_grants()
    except Exception:
        grants = []
    now = time.time()
    deadlines = []
    for g in grants:
        d = asdict(g) if is_dataclass(g) else _to_jsonable(g)
        close_at = float(d.get("call_close_at", 0.0) or 0.0)
        if close_at <= now:
            continue
        deadlines.append({
            "grant_program_id": d.get("program_id", ""),
            "display_name": d.get("display_name", ""),
            "deadline": close_at,
            "days_remaining": int((close_at - now) / 86400),
        })
    deadlines.sort(key=lambda x: x["deadline"])
    return {"deadlines": deadlines}


# ---------------------------------------------------------------------------
# Health (lightweight readiness probe used by the frontend reachability check)
# ---------------------------------------------------------------------------


@router.get("/health")
def advisor_health():
    return {"status": "ok", "module": "sylion.aeis.advisor"}


@router.post("/validate/judge-models")
def validate_judge_models_route(
    request: Request,
    payload: dict[str, Any] = Body(...),
    operator_id: str | None = Query(None),
):
    """Validate proposed judge-model assignments for wizard/settings flows."""
    from sylion.aeis.advisor.role_resolver._validators import validate_judge_models

    op = operator_id or _operator_id(request)
    judge_models = payload.get("judge_models", {}) or {}
    if not isinstance(judge_models, dict):
        raise HTTPException(status_code=400, detail="judge_models must be an object")

    errors = validate_judge_models(op, judge_models)
    visible_errors = {risk: reason for risk, reason in errors.items() if reason is not None}
    return {
        "valid": not visible_errors,
        "errors": visible_errors,
    }


# ---------------------------------------------------------------------------
# W13 Task-to-Role Suggester (PDF §8.3)
# ---------------------------------------------------------------------------


@router.post("/suggest-pipeline")
def suggest_pipeline_route(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """W13 Task-to-Role Suggester.

    Body: ``{"task": str, "available_models": list[str] | None}``.
    Returns ``PipelineSuggestion.to_dict()`` — patrz
    ``sylion.aeis.advisor.role_suggester``.

    Phase 0: heuristic-v0 (keyword-based). G2 doda LLM-based reasoning.
    """
    from sylion.aeis.advisor.role_suggester import suggest_pipeline

    task = str(payload.get("task") or "").strip()
    if not task:
        raise HTTPException(400, "field 'task' is required (non-empty string)")
    available = payload.get("available_models")
    if available is not None and not isinstance(available, list):
        raise HTTPException(400, "field 'available_models' must be list[str] or null")

    suggestion = suggest_pipeline(task, available_models=available)
    return suggestion.to_dict()
