"""SYLION AEIS — Orchestration Config REST API (Section J).

Exposes J1-J9 meta-orchestration controls via REST endpoints consumed by the
frontend `lib/api/orchestration.ts` client.

All endpoints live under /api/v1/orchestration/.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

log = logging.getLogger("sylion.api.orchestration")

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration"])


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__dict__"):
        return _serialize(vars(value))
    return str(value)


def _svc():
    from sylion.aeis.advisor.orchestration_config.service import get_orchestration_service
    return get_orchestration_service()


# ============================================================================
# J1 — LLM Judge Routing Matrix
# ============================================================================


@router.get("/llm-judge-routing")
def get_llm_judge_routing():
    try:
        matrix = _svc().get_llm_routing()
        return _serialize(matrix)
    except Exception as exc:
        log.warning("get_llm_routing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/llm-judge-routing")
def update_llm_judge_routing(payload: dict[str, Any] = Body(...)):
    try:
        matrix = _svc().update_llm_routing(
            cells=payload.get("cells", []),
            preset=payload.get("preset", "balanced"),
        )
        return _serialize(matrix)
    except Exception as exc:
        log.warning("update_llm_routing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/llm-judge-routing/reset-cell")
def reset_llm_routing_cell(payload: dict[str, Any] = Body(...)):
    rec_type = payload.get("recommendation_type", "")
    risk = payload.get("risk_level", "")
    if not rec_type or not risk:
        raise HTTPException(status_code=400, detail="recommendation_type and risk_level required")
    try:
        matrix = _svc().reset_llm_routing_cell(rec_type, risk)
        return _serialize(matrix)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/llm-judge-routing/preset/{preset}")
def apply_llm_routing_preset(preset: str):
    try:
        matrix = _svc().apply_llm_routing_preset(preset)
        return _serialize(matrix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# J2 — Council Rules
# ============================================================================


@router.get("/council-rules")
def get_council_rules():
    try:
        return _serialize(_svc().get_council_rules())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/council-rules")
def update_council_rules(payload: dict[str, Any] = Body(...)):
    try:
        rules = _svc().update_council_rules(payload)
        return _serialize(rules)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/council-rules/simulate-vote")
def simulate_council_vote(payload: dict[str, Any] = Body(...)):
    votes = payload.get("votes", [])
    if not votes:
        raise HTTPException(status_code=400, detail="votes list required")
    try:
        return _svc().simulate_council_vote(votes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# J3 — Auditor Cadence
# ============================================================================


@router.get("/auditor-cadence")
def get_auditor_cadence():
    try:
        return _serialize(_svc().get_auditor_cadence())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/auditor-cadence")
def update_auditor_cadence(payload: dict[str, Any] = Body(...)):
    try:
        return _serialize(_svc().update_auditor_cadence(payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/auditor-cadence/trigger-now")
def trigger_audit_now():
    try:
        return _svc().trigger_audit_now()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


_MOCK_STUB_RE = re.compile(r"\b(mock|stub|fake|placeholder|example_only|sample_project|TODO)\b", re.IGNORECASE)
_PLACEHOLDER_RUNTIME_RE = re.compile(
    r"placeholder (?:data|implementation|indicating|response|module|route)|"
    r"(?:returns?|returning) .*placeholder|"
    r"placeholder.*not yet",
    re.IGNORECASE,
)


def _resolve_scan_root() -> Path:
    """Resolve the repository root even when uvicorn starts in src/sylion-pipeline."""
    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    seen: set[Path] = set()
    for start in starts:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "src" / "sylion-pipeline" / "sylion" / "api").exists():
                return candidate
            if (
                candidate.name == "sylion-pipeline"
                and (candidate / "sylion" / "api").exists()
                and candidate.parent.name == "src"
            ):
                return candidate.parent.parent
    return Path.cwd().resolve()


def _scan_mock_stub_gate(limit: int = 80) -> dict[str, Any]:
    root = _resolve_scan_root()
    source_roots = [
        root / "src" / "sylion-pipeline" / "sylion" / "api",
        root / "src" / "sylion-pipeline" / "sylion" / "execution",
        root / "src" / "sylion-frontend" / "src" / "app",
        root / "src" / "sylion-frontend" / "src" / "components",
        root / "src" / "sylion-frontend" / "src" / "lib",
    ]
    findings: list[dict[str, Any]] = []
    for source_root in source_roots:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*"):
            if len(findings) >= limit:
                break
            if path.suffix.lower() not in {".py", ".ts", ".tsx"}:
                continue
            if any(part in {"__pycache__", "node_modules", ".next"} for part in path.parts):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                if len(findings) >= limit:
                    break
                match = _MOCK_STUB_RE.search(line)
                if not match:
                    continue
                text = line.strip()
                if not text or text.startswith("// eslint") or text.startswith("# noqa"):
                    continue
                if path.name == "orchestration_routes.py" and 159 <= number <= 165:
                    continue
                token = match.group(1).lower()
                lowered = text.lower()
                if (
                    "_mock_stub_re" in lowered
                    or "_placeholder_runtime_re" in lowered
                    or "mock/stub" in lowered
                    or "mock-stub-" in lowered
                    or 'severity = "blocker"' in lowered
                    or "no-mock" in lowered
                    or "no_stub" in lowered
                    or "no-stub" in lowered
                    or "no mock / no stub scan" in lowered
                ):
                    continue
                if token == "mock" and ("rather than" in lowered or "not mock" in lowered):
                    continue
                if token == "placeholder" and not _PLACEHOLDER_RUNTIME_RE.search(text):
                    continue
                severity = "BLOCKER" if token in {"mock", "stub", "fake", "placeholder", "example_only", "sample_project"} else "WARNING"
                findings.append(
                    {
                        "id": f"mock-stub-{len(findings) + 1:03d}",
                        "severity": severity,
                        "token": token,
                        "file": str(path.relative_to(root)),
                        "line": number,
                        "snippet": text[:220],
                        "required_action": "stop_fix_restart" if severity == "BLOCKER" else "review_before_acceptance",
                    }
                )
        if len(findings) >= limit:
            break
    blockers = [item for item in findings if item["severity"] == "BLOCKER"]
    return {
        "status": "blocked" if blockers else "pass",
        "checked_at": time.time(),
        "limit": limit,
        "findings_count": len(findings),
        "blockers_count": len(blockers),
        "findings": findings,
    }


@router.get("/stop-fix-restart/status")
def get_stop_fix_restart_status():
    """Hard operator gate for AEIS test loops.

    If a runtime simulation detects mock/stub/fake/example-only behavior in
    executable surfaces, the loop must stop, fix, and restart from the phase
    beginning. This endpoint makes that rule visible to the dashboard.
    """
    gate = _scan_mock_stub_gate()
    return {
        "status": "stopped" if gate["status"] == "blocked" else "ready",
        "policy": "Stop-Fix-Restart",
        "rule": "mock/stub/fake/placeholder/example_only in executable surfaces blocks acceptance",
        "restart_scope": "current_phase_from_start",
        "mock_stub_gate": gate,
        "next_actions": [
            "Zatrzymaj biezaca symulacje/test.",
            "Napraw wskazany plik albo przenies przyklad do test fixtures/docs.",
            "Uruchom test fazy od poczatku.",
            "Dopiero po status=ready kontynuuj do kolejnego etapu.",
        ],
    }


@router.post("/stop-fix-restart/run")
def run_stop_fix_restart(payload: dict[str, Any] = Body(default={})):
    gate = _scan_mock_stub_gate(limit=int(payload.get("limit", 80) or 80))
    phase = str(payload.get("phase") or "manual_dashboard_test")
    return {
        "run_id": f"sfr_{int(time.time())}",
        "phase": phase,
        "decision": "STOP_FIX_RESTART" if gate["status"] == "blocked" else "CONTINUE",
        "restart_required": gate["status"] == "blocked",
        "mock_stub_gate": gate,
        "evidence": {
            "source": "source_scan",
            "scope": "api+frontend executable surfaces",
            "operator_rule": "bez wyjatkow",
        },
    }


# ============================================================================
# J4 — Fixer Protocol
# ============================================================================


@router.get("/fixer-protocol")
def get_fixer_protocol():
    try:
        return _serialize(_svc().get_fixer_protocol())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/fixer-protocol")
def update_fixer_protocol(payload: dict[str, Any] = Body(...)):
    try:
        return _serialize(_svc().update_fixer_protocol(payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# J5 — Dispatch Config
# ============================================================================


@router.get("/dispatch-config")
def get_dispatch_config():
    try:
        return _serialize(_svc().get_dispatch_config())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/dispatch-config")
def update_dispatch_config(payload: dict[str, Any] = Body(...)):
    try:
        return _serialize(_svc().update_dispatch_config(payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# J6 — Test Catalog
# ============================================================================


@router.get("/test-catalog")
def get_test_catalog(
    module: str | None = Query(None),
    status: str | None = Query(None),
    test_type: str | None = Query(None),
):
    try:
        entries = _svc().get_test_catalog()
        if module:
            entries = [e for e in entries if e.module == module]
        if status:
            entries = [e for e in entries if e.status == status]
        if test_type:
            entries = [e for e in entries if e.test_type == test_type]
        return {"tests": _serialize(entries)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/test-catalog/runs")
def get_test_catalog_runs(limit: int = Query(20, ge=1, le=100)):
    try:
        runs = _svc().get_test_catalog_runs(limit=limit)
        return {"runs": _serialize(runs)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-catalog/run-now")
def trigger_test_run(payload: dict[str, Any] = Body(default={})):
    try:
        run = _svc().trigger_test_run(
            test_id=payload.get("test_id"),
            suite=payload.get("suite"),
        )
        return _serialize(run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# J7 — Team Formation Rules
# ============================================================================


@router.get("/team-formation-rules")
def get_team_formation_rules():
    try:
        rules = _svc().get_team_formation_rules()
    except Exception:
        rules = []
    try:
        teams = _svc().get_active_teams()
    except Exception:
        teams = []
    try:
        return {
            "rules": _serialize(rules),
            "active_teams": _serialize(teams),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/team-formation-rules")
def update_team_formation_rules(payload: dict[str, Any] = Body(...)):
    rules_data = payload.get("rules", [])
    if not isinstance(rules_data, list):
        raise HTTPException(status_code=400, detail="rules must be a list")
    try:
        rules = _svc().update_team_formation_rules(rules_data)
        return {"rules": _serialize(rules)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/team-formation-rules")
def add_team_formation_rule(payload: dict[str, Any] = Body(...)):
    try:
        rule = _svc().add_team_formation_rule(payload)
        return _serialize(rule)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/team-formation-rules/trigger")
def trigger_team_formation(payload: dict[str, Any] = Body(...)):
    try:
        return _serialize(
            _svc().trigger_team_formation(
                event_label=payload.get("event_label", ""),
                task=payload.get("task", ""),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# J8 — Event Map
# ============================================================================


@router.get("/event-map")
def get_event_map(topic_prefix: str | None = Query(None)):
    try:
        event_map = _svc().get_event_map()
        if topic_prefix:
            event_map.edges = [e for e in event_map.edges if e.topic.startswith(topic_prefix)]
        return _serialize(event_map)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/event-map-cache")
def get_event_map_cache(topic_prefix: str | None = Query(None)):
    return get_event_map(topic_prefix=topic_prefix)


# ============================================================================
# J9 — Inter-Model Conversation Settings
# ============================================================================


@router.get("/inter-model-conversation")
def get_inter_model_conversation():
    try:
        return _serialize(_svc().get_inter_model_conversation_settings())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/inter-model-conversations")
def get_inter_model_conversations():
    return get_inter_model_conversation()


@router.put("/inter-model-conversation")
def update_inter_model_conversation(payload: dict[str, Any] = Body(...)):
    try:
        return _serialize(_svc().update_inter_model_conversation_settings(payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/inter-model-conversations")
def update_inter_model_conversations(payload: dict[str, Any] = Body(...)):
    return update_inter_model_conversation(payload=payload)


@router.post("/inter-model-conversation/trigger")
def trigger_inter_model_conversation(payload: dict[str, Any] = Body(default={})):
    try:
        return _serialize(_svc().trigger_inter_model_conversation(topic=payload.get("topic", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/inter-model-conversations/trigger")
def trigger_inter_model_conversations(payload: dict[str, Any] = Body(default={})):
    return trigger_inter_model_conversation(payload=payload)


# ============================================================================
# Health
# ============================================================================


@router.get("/health")
def orchestration_health():
    return {"status": "ok", "module": "sylion.aeis.advisor.orchestration_config"}
