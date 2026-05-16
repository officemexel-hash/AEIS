"""GuardianBase — common skeleton for the 13 W14 guardians.

A guardian is a thin event subscriber that turns suspicious events into
GuardianAlert records. Subclasses override:

  - name           : guardian name (matches GuardianClass enum)
  - subscribed_events : list of event topics to react to
  - on_event(event) -> GuardianAlert | None : detection logic
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sylion.aeis.testing.ontology.enums import GuardianClass, Severity
from sylion.aeis.testing.ontology.objects import GuardianAlert
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.guardians.base")

# Idempotency cache size — prunes oldest events once exceeded so memory
# never grows unbounded for a long-running guardian.
_DEDUP_CACHE_MAX = 4096


class GuardianBase:
    """Subscribe to events on the bus, emit GuardianAlert when triggered.

    Thread-safe: state mutations (alerts_24h, last_alert_at, health, dedup
    cache) all run under ``self._lock``. Idempotent: a (guardian, event_id)
    pair is processed at most once via the LRU-bounded dedup set.
    """

    # Pytest: do NOT collect any subclass starting with "Test"
    __test__ = False

    name: str = ""
    subscribed_events: tuple[str, ...] = ()
    default_severity: Severity = Severity.P2

    def __init__(
        self,
        ontology: OntologyStore | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self.ontology = ontology
        self.event_bus = event_bus
        self._lock = threading.RLock()
        self.alerts_24h: int = 0
        self.last_alert_at: float = 0.0
        self.health: str = "GREEN"
        self.persistence_failed: bool = False
        # Idempotency: track event_ids we've already handled.
        self._seen_event_ids: list[str] = []
        self._seen_event_set: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_event(self, event: Any) -> GuardianAlert | None:
        """Override in subclass. Return GuardianAlert if event is suspicious."""
        return None

    def handle_event(self, event: Any) -> GuardianAlert | None:
        """Wrap on_event with idempotency + crash isolation.

        EventBus subscribers should be wired to ``handle_event`` (not
        ``on_event``) so a malformed event never tears down the dispatch
        loop and re-delivery of the same event_id never produces a
        duplicate alert. Both id-coercion and dedup live INSIDE the
        try/except so a bad event_id type cannot kill the subscriber.
        """
        try:
            raw = getattr(event, "event_id", None) or getattr(event, "id", None)
            event_id = str(raw) if raw is not None else None
            if event_id:
                with self._lock:
                    if event_id in self._seen_event_set:
                        return None
                    self._remember_event_id(event_id)
            return self.on_event(event)
        except Exception:  # crash isolation per Kimi attack #1
            log.exception(
                "guardian %s crashed on event", self.name,
            )
            return None

    def _remember_event_id(self, event_id: str) -> None:
        self._seen_event_set.add(event_id)
        self._seen_event_ids.append(event_id)
        if len(self._seen_event_ids) > _DEDUP_CACHE_MAX:
            old = self._seen_event_ids.pop(0)
            self._seen_event_set.discard(old)

    def status(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "health": self.health,
                "last_alert_at": self.last_alert_at,
                "alerts_24h": self.alerts_24h,
            }

    def subscribe(self, event_bus: Any | None = None) -> None:
        """Attach handle_event to every topic in ``subscribed_events``.

        Stores the bus on ``self.event_bus`` if not already set so
        downstream alerts reach the same bus the subscription used.
        """
        bus = event_bus or self.event_bus
        if bus is None:
            log.warning("guardian %s: no event_bus to subscribe to", self.name)
            return
        if self.event_bus is None:
            self.event_bus = bus
        if not hasattr(bus, "subscribe"):
            log.warning("guardian %s: bus %r has no subscribe()",
                        self.name, type(bus).__name__)
            return
        for topic in self.subscribed_events:
            try:
                bus.subscribe(topic, self.handle_event)
            except Exception:  # pragma: no cover
                log.exception("guardian %s subscribe to %s failed",
                              self.name, topic)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _alert(
        self,
        guardian: str | GuardianClass,
        severity: str | Severity,
        reason: str,
        evidence_link: dict,
        finding_id: str | None = None,
        trace_id: str | None = None,
    ) -> GuardianAlert:
        gname = guardian.value if isinstance(guardian, GuardianClass) else str(guardian)
        sev = severity.value if isinstance(severity, Severity) else str(severity)

        alert = GuardianAlert(
            guardian=gname,
            severity=sev,
            evidence_link=evidence_link,
            reason=reason,
            finding_id=finding_id,
        )
        persisted = True
        if self.ontology is not None:
            try:
                self.ontology.create(alert)
            except Exception:  # pragma: no cover
                log.exception("guardian %s ontology persist failed", gname)
                persisted = False
        with self._lock:
            self.last_alert_at = time.time()
            self.alerts_24h += 1
            if not persisted:
                # Surface the failure on health so an oncall sees it
                # instead of trusting the silently-emitted alert
                # (Kimi attack #5: silent persist swallowing).
                self.health = "RED"
                self.persistence_failed = True
            elif sev in ("P0", "P1"):
                self.health = "RED"
            elif self.health != "RED":
                self.health = "YELLOW"
        # Codex bug #4: every guardian alert event must carry trace_id
        # so the downstream audit trail can correlate.
        emit_payload = {
            "alert_id": alert.alert_id,
            "guardian": gname,
            "severity": sev,
            "reason": reason,
            "trace_id": trace_id or evidence_link.get("trace_id", ""),
        }
        self._emit_event("aeis.testing.guardian.alert", emit_payload)
        return alert

    def _emit_event(self, topic: str, payload: dict) -> None:
        if self.event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self.event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module=f"aeis.testing.guardians.{self.name}",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed: %s", e)


__all__ = ["GuardianBase"]
