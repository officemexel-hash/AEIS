"""W14 BE-6 round_meta post-approval listeners.

When a Human Gate ticket submitted by ``api/projects_freeze_routes.py``
(canon freeze, masterplan freeze, build authorize) is resolved with
``decision == "approved"``, this module is responsible for completing
the corresponding side-effect on the project record:

* ``project_freeze`` + ``target=canon``        → ``project.canon_frozen_at``
                                                + ``phase="masterplan_in_progress"``
* ``project_freeze`` + ``target=masterplan``   → ``project.masterplan_frozen_at``
                                                + ``phase="build_authorization"``
* ``project_build_authorize``                  → ``project.build_authorized_at``
                                                + cost cap + autonomy level
                                                + status="building"
                                                + ``phase="execution"``

W14 BE-8.3 (F-Idea6-2 P3): the phase assignments above were added so
the operator dashboard advances the project lifecycle without manual
edits — see ``test_round_meta_post_approval.py`` and
``test_be8_backend_extensions.py`` for the contract.

For every completion an entry is appended to the matching
``logs/v2/<round>.jsonl`` chain with ``kind="round_meta.<round>.completed"``
so the audit replay tool can pair the request → completion records.

Idempotency: if the corresponding ``*_frozen_at`` / ``build_authorized_at``
is already set, the listener no-ops and emits no audit row. This guards
against double-fire when the governance plane retries a resolve.

Hook is registered via ``sylion.governance.tickets.register_post_resolve_hook``
on first import of :mod:`sylion.project_mode`.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.project_mode.round_meta_hooks")

# Resolved lazily so test harnesses that patch the audit chain dir or the
# project store can do so without importing this module first.


def _store():
    from sylion.project_mode import get_project_mode_store

    return get_project_mode_store()


def _audit_path(filename: str) -> Path:
    from sylion.aeis_v2.audit_profile import resolve_audit_chain_dir

    return resolve_audit_chain_dir() / filename


def _append_chain(filename: str, entry: dict[str, Any]) -> None:
    from sylion.aeis_v2.audit_chain import append_to_chain

    try:
        append_to_chain(_audit_path(filename), entry)
    except Exception:                                  # noqa: BLE001
        log.warning(
            "round_meta: append_to_chain(%s) failed (continuing)",
            filename, exc_info=True,
        )


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Per-round completion handlers
# ---------------------------------------------------------------------------


def _complete_canon_freeze(
    project: dict[str, Any], ticket_id: str, payload: dict[str, Any],
) -> bool:
    if project.get("canon_frozen_at"):
        # Idempotent: already completed.
        return False
    canon_text = str(project.get("canonical_book") or "")
    now = time.time()
    project["canon_frozen_at"] = now
    project["canon_hash"] = _sha256(canon_text)
    approvals = dict(project.get("approvals") or {})
    approvals["book"] = True
    approvals.pop("book_pending_ticket_id", None)
    project["approvals"] = approvals
    # W14 BE-8.3 (F-Idea6-2 P3): canon freeze approved → masterplan
    # work begins. Operators see the dashboard advance from the
    # planning phase to the masterplan phase without manual edits.
    project["phase"] = "masterplan_in_progress"
    project["updated_at"] = now
    _store().upsert_project(project)
    _store().add_event(
        project["project_id"],
        "project.canon.freeze.completed",
        {"ticket_id": ticket_id, "canon_hash": project["canon_hash"]},
    )
    _store().add_event(
        project["project_id"],
        "project.canon.frozen",
        {"ticket_id": ticket_id, "canon_hash": project["canon_hash"]},
    )
    _append_chain(
        "canon_freeze.jsonl",
        {
            "kind": "round_meta.canon.freeze.completed",
            "project_id": project["project_id"],
            "ticket_id": ticket_id,
            "ts": now,
            "canon_hash": project["canon_hash"],
        },
    )
    return True


def _complete_masterplan_freeze(
    project: dict[str, Any], ticket_id: str, payload: dict[str, Any],
) -> bool:
    if project.get("masterplan_frozen_at"):
        return False
    masterplan_text = str(project.get("masterplan") or "")
    now = time.time()
    project["masterplan_frozen_at"] = now
    project["masterplan_hash"] = _sha256(masterplan_text)
    approvals = dict(project.get("approvals") or {})
    approvals["operating_model"] = True
    approvals.pop("operating_model_pending_ticket_id", None)
    project["approvals"] = approvals
    # Masterplan approval unlocks Round 3, but it does not start workers.
    # The build may start only after the separate financial/production/
    # external-action authorization ticket is approved.
    project["phase"] = "build_authorization"
    project["updated_at"] = now
    _store().upsert_project(project)
    _store().add_event(
        project["project_id"],
        "project.masterplan.freeze.completed",
        {
            "ticket_id": ticket_id,
            "masterplan_hash": project["masterplan_hash"],
        },
    )
    _store().add_event(
        project["project_id"],
        "project.masterplan.frozen",
        {
            "ticket_id": ticket_id,
            "masterplan_hash": project["masterplan_hash"],
        },
    )
    _append_chain(
        "masterplan_freeze.jsonl",
        {
            "kind": "round_meta.masterplan.freeze.completed",
            "project_id": project["project_id"],
            "ticket_id": ticket_id,
            "ts": now,
            "masterplan_hash": project["masterplan_hash"],
        },
    )
    return True


def _complete_build_authorize(
    project: dict[str, Any], ticket_id: str, payload: dict[str, Any],
) -> bool:
    if project.get("build_authorized_at"):
        return False
    now = time.time()
    project["build_authorized_at"] = now
    approvals = dict(project.get("approvals") or {})
    approvals["build"] = True
    approvals.pop("build_pending_ticket_id", None)
    project["approvals"] = approvals
    cost_cap = payload.get("cost_cap_usd")
    if cost_cap is not None:
        try:
            project["cost_cap_usd"] = float(cost_cap)
        except (TypeError, ValueError):
            log.warning(
                "round_meta: invalid cost_cap_usd=%r in payload, skipping",
                cost_cap,
            )
    autonomy = payload.get("autonomy_level")
    if autonomy:
        project["autonomy_level"] = str(autonomy)
    project["status"] = "building"
    # W14 BE-8.3 (F-Idea6-2 P3): build authorize approved → execution
    # phase. Status stays "building" (already set above) so legacy
    # callers that key off status keep working.
    project["phase"] = "execution"
    project["updated_at"] = now
    _store().upsert_project(project)
    _store().add_event(
        project["project_id"],
        "project.build.authorize.completed",
        {
            "ticket_id": ticket_id,
            "cost_cap_usd": project.get("cost_cap_usd"),
            "autonomy_level": project.get("autonomy_level"),
        },
    )
    _append_chain(
        "build_authorize.jsonl",
        {
            "kind": "round_meta.build.authorize.completed",
            "project_id": project["project_id"],
            "ticket_id": ticket_id,
            "ts": now,
            "cost_cap_usd": project.get("cost_cap_usd"),
            "autonomy_level": project.get("autonomy_level"),
        },
    )
    _start_execution_after_build_authorize(project["project_id"], ticket_id)
    return True


def _start_execution_after_build_authorize(project_id: str, ticket_id: str) -> None:
    """Run the real project execution engine after Round 3 approval.

    The previous Round 3 behavior only flipped the project to
    ``building/execution``. That made the operator dashboard look unblocked
    while no workers, module outputs, artifact, validation, audit, deployment
    bundle or memory write actually happened. Round 3 is the authorization
    boundary, so the side effect must be a real execution start.
    """
    current = _store().get_project(project_id)
    launch = dict((current or {}).get("launch") or {})
    if launch.get("artifact_path") or launch.get("status") in {"completed", "blocked"}:
        return

    now = time.time()
    _store().add_event(
        project_id,
        "project.execution.auto_start.requested",
        {"ticket_id": ticket_id, "trigger": "round3_build_authorize"},
    )
    _append_chain(
        "build_authorize.jsonl",
        {
            "kind": "round_meta.build.execution.starting",
            "project_id": project_id,
            "ticket_id": ticket_id,
            "ts": now,
        },
    )
    try:
        from sylion.project_mode import get_project_execution_engine

        result = get_project_execution_engine(_store()).run_project(
            project_id,
            auto_execute=True,
        )
        _store().add_event(
            project_id,
            "project.execution.auto_start.completed",
            {
                "ticket_id": ticket_id,
                "artifact_path": result.get("artifact_path", ""),
                "artifact_sha256": result.get("artifact_sha256", ""),
                "validation_success": bool((result.get("validation") or {}).get("success")),
                "audit_results": len((result.get("audit") or {}).get("results") or []),
            },
        )
        _append_chain(
            "build_authorize.jsonl",
            {
                "kind": "round_meta.build.execution.completed",
                "project_id": project_id,
                "ticket_id": ticket_id,
                "ts": time.time(),
                "artifact_path": result.get("artifact_path", ""),
                "artifact_sha256": result.get("artifact_sha256", ""),
                "validation_success": bool((result.get("validation") or {}).get("success")),
            },
        )
    except Exception as exc:                         # noqa: BLE001
        project = _store().get_project(project_id)
        if project:
            project["status"] = "blocked_on_execution"
            project["phase"] = "execution_failed"
            project["updated_at"] = time.time()
            _store().upsert_project(project)
        _store().add_event(
            project_id,
            "project.execution.auto_start.failed",
            {"ticket_id": ticket_id, "error": str(exc)},
        )
        _append_chain(
            "build_authorize.jsonl",
            {
                "kind": "round_meta.build.execution.failed",
                "project_id": project_id,
                "ticket_id": ticket_id,
                "ts": time.time(),
                "error": str(exc),
            },
        )
        log.warning(
            "round_meta: auto execution after build authorize failed for project=%s",
            project_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Public hook entrypoint
# ---------------------------------------------------------------------------


def round_meta_post_resolve(ticket: Any, decision: str) -> None:
    """Post-resolve listener registered via governance.tickets.

    Only mutates state when ``decision == "approved"``. Rejected/expired
    tickets are a no-op so we don't leak partial completion.

    Exceptions raised here are caught by the central
    ``_fire_post_resolve_hooks`` wrapper — but we still try/except per
    round because we want a single bad payload to disable only its own
    branch, not the whole listener.
    """
    if decision != "approved":
        return
    payload = dict(getattr(ticket, "payload", None) or {})
    action = str(payload.get("action") or "")
    target = str(payload.get("target") or "")
    project_id = getattr(ticket, "project_id", None)
    if not project_id:
        return
    project = _store().get_project(project_id)
    if not project:
        log.warning(
            "round_meta: project %s missing for ticket %s — skipping",
            project_id, getattr(ticket, "ticket_id", "?"),
        )
        return
    ticket_id = str(getattr(ticket, "ticket_id", "") or "")
    try:
        if action == "project_freeze" and target == "canon":
            _complete_canon_freeze(project, ticket_id, payload)
        elif action == "project_freeze" and target == "masterplan":
            _complete_masterplan_freeze(project, ticket_id, payload)
        elif action == "project_build_authorize":
            _complete_build_authorize(project, ticket_id, payload)
    except Exception:                                   # noqa: BLE001
        log.warning(
            "round_meta: completion for action=%s target=%s failed",
            action, target, exc_info=True,
        )


_REGISTERED = False


def register_round_meta_hook() -> None:
    """Register :func:`round_meta_post_resolve` once per process.

    Called from :mod:`sylion.project_mode.__init__` on import. Repeat
    calls are no-ops (the underlying registry already de-dupes by
    callable identity, but we also short-circuit here).
    """
    global _REGISTERED
    if _REGISTERED:
        return
    from sylion.governance.tickets import register_post_resolve_hook

    register_post_resolve_hook(round_meta_post_resolve)
    _REGISTERED = True


__all__ = [
    "register_round_meta_hook",
    "round_meta_post_resolve",
]
