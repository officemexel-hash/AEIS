"""Soft learning auto-application.

Best-effort attempt to push a learning signal into the preferences module.
Per the WP6 stub policy: when the preferences gRPC isn't reachable, log a
warning and return `applied=false, reason="preferences_grpc_unreachable"`.

The caller (`AdvisorHistoryService.apply_soft_signal`) is responsible for
flipping `applied_to_preference` and emitting the
`aeis.advisor.history.soft_learning_applied` event.
"""

from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.advisor.history._db import update_signal_applied
from sylion.aeis.advisor.history._models import LearningSignal

log = logging.getLogger("sylion.aeis.advisor.history.learning.soft_learning")


def apply_soft_signal(signal: LearningSignal) -> dict[str, Any]:
    """Try to apply `signal` to the preferences module.

    Returns a result envelope:
        {"applied": bool, "reason": str, "preference_id": str}
    """
    if signal.applied_to_preference:
        return {"applied": True, "reason": "already_applied", "preference_id": ""}

    try:
        from sylion.aeis.advisor.preferences.service import (  # type: ignore
            get_preferences_service,
        )
    except Exception as exc:  # pragma: no cover - import error path
        log.warning("preferences module not importable: %s", exc)
        return {
            "applied": False,
            "reason": "preferences_grpc_unreachable",
            "preference_id": "",
        }

    try:
        svc = get_preferences_service()
    except Exception as exc:
        log.warning("preferences service unavailable: %s", exc)
        return {
            "applied": False,
            "reason": "preferences_grpc_unreachable",
            "preference_id": "",
        }

    set_pref = getattr(svc, "set_preference", None) or getattr(svc, "upsert_preference", None)
    if set_pref is None:
        log.warning("preferences service has no set_preference / upsert_preference")
        return {
            "applied": False,
            "reason": "preferences_grpc_unreachable",
            "preference_id": "",
        }

    soft_value = {
        "signal_type": signal.signal_type,
        "signal_strength": signal.signal_strength,
        "source_card_id": signal.source_card_id,
    }
    common_kwargs = {
        "preference_key": signal.preference_key,
        "project_type": signal.context_project_type or None,
        "project_domain": signal.context_project_domain or None,
        "value": soft_value,
    }
    try:
        try:
            result = set_pref(
                user_id=signal.operator_id,
                set_by="soft_learning",
                reason=f"soft_learning:{signal.signal_type}",
                **common_kwargs,
            )
        except TypeError:
            result = set_pref(
                operator_id=signal.operator_id,
                source="soft_learning",
                **common_kwargs,
            )
    except Exception as exc:
        log.warning("preferences set_preference call failed: %s", exc)
        return {
            "applied": False,
            "reason": "preferences_grpc_unreachable",
            "preference_id": "",
            "underlying_error": f"{type(exc).__name__}:{exc}",
        }

    pref_id = ""
    if isinstance(result, dict):
        pref_id = str(result.get("preference_id") or result.get("id") or "")
    elif isinstance(result, str):
        pref_id = result

    update_signal_applied(signal.signal_id)
    return {"applied": True, "reason": "ok", "preference_id": pref_id}
