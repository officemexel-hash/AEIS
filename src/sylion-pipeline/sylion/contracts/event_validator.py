"""Event taxonomy validator for SYLION AEIS.

Validates that runtime events conform to the canonical taxonomy defined in
events.yaml (172 events). Every event has an owner module, uses format
``<domain>.<subject>.<verb>``, and must be registered by its owning module.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# Canonical topic format: domain.subject.verb  (e.g. "bundle.assembled")
_TOPIC_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,5}$")


class EventTaxonomyValidator:
    """Validates that runtime events conform to the canonical taxonomy."""

    def __init__(self, taxonomy_path: str | Path) -> None:
        """Load taxonomy from *events.yaml*.

        Parameters
        ----------
        taxonomy_path:
            Path to the ``events.yaml`` file.

        Raises
        ------
        FileNotFoundError
            If *taxonomy_path* does not exist.
        ValueError
            If the YAML structure is missing required keys.
        """
        path = Path(taxonomy_path)
        if not path.exists():
            raise FileNotFoundError(f"Taxonomy file not found: {path}")

        with path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh)

        taxonomy = raw.get("event_taxonomy")
        if taxonomy is None:
            raise ValueError("YAML missing top-level 'event_taxonomy' key")

        events_raw = taxonomy.get("events", [])
        if not isinstance(events_raw, list):
            raise ValueError("'events' must be a list")

        self._version: str = taxonomy.get("version", "unknown")
        self._declared_total: int = taxonomy.get("total_events", 0)

        # topic -> event definition
        self._events: dict[str, dict[str, Any]] = {}
        # owner module -> list of topics
        self._owner_map: dict[str, list[str]] = {}

        for entry in events_raw:
            if not isinstance(entry, dict):
                continue
            topic: str | None = entry.get("topic")
            owner: str | None = entry.get("owner")
            if topic is None or owner is None:
                continue
            self._events[topic] = entry

            # An owner field may contain multiple comma-separated module ids
            # (e.g. "security.session_broker, security.auth_provider").
            for owner_id in self._split_owners(owner):
                self._owner_map.setdefault(owner_id, []).append(topic)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def version(self) -> str:
        """Taxonomy version string."""
        return self._version

    @property
    def event_count(self) -> int:
        """Number of events loaded from the taxonomy."""
        return len(self._events)

    @property
    def topics(self) -> set[str]:
        """All registered topic strings."""
        return set(self._events.keys())

    @property
    def owner_modules(self) -> set[str]:
        """All distinct owner module identifiers."""
        return set(self._owner_map.keys())

    def validate_event(self, topic: str, source_module: str) -> dict:
        """Check if *topic* is in taxonomy and *source_module* is a valid owner.

        Returns
        -------
        dict
            ``{"valid": bool, "error": str | None, "topic": str, "owner": str | None}``
        """
        result: dict[str, Any] = {
            "valid": False,
            "error": None,
            "topic": topic,
            "owner": None,
        }

        entry = self._events.get(topic)
        if entry is None:
            result["error"] = f"Topic '{topic}' not found in taxonomy"
            return result

        owner_raw: str = entry["owner"]
        owners = self._split_owners(owner_raw)
        result["owner"] = owner_raw

        if source_module not in owners:
            result["error"] = (
                f"Module '{source_module}' is not an owner of '{topic}' "
                f"(expected: {owner_raw})"
            )
            return result

        result["valid"] = True
        return result

    def validate_all(self) -> list[dict]:
        """Validate every event in the taxonomy for structural consistency.

        Checks performed for each event:
        - topic matches the ``<domain>.<subject>.<verb>`` format
        - ``owner`` is non-empty
        - ``payload_keys`` is a list
        - ``description`` is a non-empty string

        Returns a list of issue dicts, one per problem found (empty = healthy).
        """
        issues: list[dict[str, Any]] = []

        # Check declared total against actual count
        if self._declared_total and self.event_count != self._declared_total:
            issues.append({
                "check": "total_events",
                "error": (
                    f"Declared total_events={self._declared_total} "
                    f"but actual count={self.event_count}"
                ),
            })

        for topic, entry in self._events.items():
            # Topic format
            if not _TOPIC_RE.match(topic):
                issues.append({
                    "check": "topic_format",
                    "topic": topic,
                    "error": f"Topic '{topic}' does not match <domain>.<subject>.<verb>",
                })

            # Owner non-empty
            owner = entry.get("owner")
            if not owner or not isinstance(owner, str) or not owner.strip():
                issues.append({
                    "check": "owner_missing",
                    "topic": topic,
                    "error": f"Topic '{topic}' has empty or missing owner",
                })

            # Payload keys is a list
            pk = entry.get("payload_keys")
            if pk is not None and not isinstance(pk, list):
                issues.append({
                    "check": "payload_keys_type",
                    "topic": topic,
                    "error": f"Topic '{topic}' payload_keys must be a list",
                })

            # Description present
            desc = entry.get("description")
            if not desc or not isinstance(desc, str) or not desc.strip():
                issues.append({
                    "check": "description_missing",
                    "topic": topic,
                    "error": f"Topic '{topic}' has empty or missing description",
                })

        return issues

    def get_events_for_module(self, module_id: str) -> list[str]:
        """Return all topic strings owned by *module_id*."""
        return list(self._owner_map.get(module_id, []))

    def get_orphan_events(self, registered_modules: list[str]) -> list[dict]:
        """Find events whose owner module is not in *registered_modules*.

        Parameters
        ----------
        registered_modules:
            List of module ids that actually exist in the system.

        Returns
        -------
        list[dict]
            Each dict has ``topic`` and ``owner`` keys.
        """
        module_set = set(registered_modules)
        orphans: list[dict[str, str]] = []
        for topic, entry in self._events.items():
            owners = self._split_owners(entry["owner"])
            if not any(o in module_set for o in owners):
                orphans.append({"topic": topic, "owner": entry["owner"]})
        return orphans

    def get_unregistered_events(self, emitted_topics: list[str]) -> list[str]:
        """Return topics emitted at runtime but absent from the taxonomy."""
        taxonomy_topics = self._events.keys()
        return [t for t in emitted_topics if t not in taxonomy_topics]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _split_owners(owner_str: str) -> list[str]:
        """Split a potentially comma-separated owner string into clean ids."""
        return [o.strip() for o in owner_str.split(",") if o.strip()]
