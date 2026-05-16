"""Engine service singleton.

Wraps lifecycle subscription + rule seeding + public API used by REST/gRPC
adapters. Threading.Lock used for singleton init per the existing module
pattern (see governance/council_workflow.py).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from sylion.aeis.advisor.engine._db import (
    fetch_evidence_pack,
    fetch_evidence_signatures,
    fetch_llm_judge_audits,
    fetch_recommendation_by_id,
    fetch_recommendations,
    init_engine_schema,
    insert_evidence_signature,
    update_evidence_pack_status,
)
from sylion.aeis.advisor.engine._db import envelope_from_row
from sylion.aeis.advisor.engine.lifecycle import (
    GateDecision,
    evaluate_gate,
    register_lifecycle_subscribers,
)
from sylion.aeis.advisor.engine.orchestrator import process_event
from sylion.aeis.advisor.engine.rule_engine import seed_default_rules
from sylion.aeis.advisor.engine.rule_engine.loader import (
    invalidate_cache,
    load_active_rules,
)

log = logging.getLogger("sylion.aeis.advisor.engine.service")


class AdvisorEngineService:
    """High-level facade. Holds no per-request state; safe to share."""

    def __init__(self) -> None:
        init_engine_schema()
        seed_default_rules()
        self._subscribed = 0
        self._lock = threading.Lock()

    # -- subscriptions --------------------------------------------------

    def attach_to_event_bus(self, event_bus: Any) -> int:
        with self._lock:
            self._subscribed = register_lifecycle_subscribers(event_bus)
        log.info("engine attached to event_bus, %d subscriptions", self._subscribed)
        return self._subscribed

    # -- card emission --------------------------------------------------

    def submit_event(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        operator_id: str,
        triggering_event_id: str = "",
    ) -> list[dict[str, Any]]:
        """Drive the engine for a single event (used by tests + REST adapters)."""
        envelopes = process_event(
            topic=topic,
            payload=payload,
            operator_id=operator_id,
            triggering_event_id=triggering_event_id,
        )
        return [self._envelope_to_dict(env) for env in envelopes]

    def evaluate_gate(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        operator_id: str,
        timeout_s: float = 5.0,
        triggering_event_id: str = "",
    ) -> GateDecision:
        return evaluate_gate(
            topic=topic,
            payload=payload,
            operator_id=operator_id,
            triggering_event_id=triggering_event_id,
            timeout_s=timeout_s,
        )

    # -- queries --------------------------------------------------------

    def list_recommendations(self, *, operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [envelope_from_row(r) for r in fetch_recommendations(operator_id, limit=limit)]

    def get_recommendation(self, *, card_id: str) -> dict[str, Any] | None:
        row = fetch_recommendation_by_id(card_id)
        return envelope_from_row(row) if row else None

    def list_audits_for_card(self, *, card_id: str) -> list[dict[str, Any]]:
        return fetch_llm_judge_audits(card_id)

    def get_evidence_pack(self, *, pack_id: str) -> dict[str, Any] | None:
        pack = fetch_evidence_pack(pack_id)
        if not pack:
            return None
        pack["signatures"] = fetch_evidence_signatures(pack_id)
        return pack

    # -- evidence pack lifecycle ---------------------------------------

    def sign_evidence_pack(
        self,
        *,
        pack_id: str,
        signer_id: str,
        signer_role: str,
        signature_payload: str,
    ) -> str:
        return insert_evidence_signature(
            evidence_pack_id=pack_id,
            signer_id=signer_id,
            signer_role=signer_role,
            signature_payload=signature_payload,
        )

    def finalize_evidence_pack(self, *, pack_id: str) -> bool:
        pack = fetch_evidence_pack(pack_id)
        if not pack:
            return False
        update_evidence_pack_status(pack_id, "finalized", finalized=True)
        return True

    # -- rules CRUD -----------------------------------------------------

    def list_rules(self) -> list[dict[str, Any]]:
        return [r.__dict__ for r in load_active_rules(force=True)]

    def invalidate_rule_cache(self) -> None:
        invalidate_cache()

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _envelope_to_dict(env) -> dict[str, Any]:
        from sylion.aeis.advisor.engine._db import envelope_to_dict

        return envelope_to_dict(env)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service: AdvisorEngineService | None = None
_service_lock = threading.Lock()


def get_engine_service() -> AdvisorEngineService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = AdvisorEngineService()
    return _service


def reset_engine_service() -> None:
    """For tests: drop the singleton."""
    global _service
    with _service_lock:
        _service = None
