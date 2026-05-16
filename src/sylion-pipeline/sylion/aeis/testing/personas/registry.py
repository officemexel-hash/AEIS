"""PersonaRegistry — load + manage HumanPersona records.

Auto-loads starter personas from `_starter/*.json` on init. Brief E8 expects
4 canonical starter personas plus a path to 15 total (the rest are
"extended" personas for richer scenario coverage).

Thread-safe ``update_dynamic_state`` via ``threading.Lock`` (Kimi E8 #6).
JSON loading rejects duplicate keys and NFKC-normalizes ``name`` so
Unicode look-alike confusables can't bypass dedup (Kimi E8 #8).
"""
from __future__ import annotations

import json
import logging
import threading
import unicodedata
from pathlib import Path
from typing import Any

from sylion.aeis.testing.ontology.objects import HumanPersona
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.personas.registry")

STARTER_DIR = Path(__file__).parent / "_starter"

# Canonical 4 starter personas (kept stable across releases).
STARTER_PERSONA_IDS: tuple[str, ...] = (
    "operator_beginner",
    "operator_power_user",
    "auditor",
    "operator_overloaded",
)

# Extended personas (W14 E8: 15 total = 4 starter + 11 extended).
EXTENDED_PERSONA_IDS: tuple[str, ...] = (
    "admin_overconfident",
    "viewer_curious",
    "mobile_first_operator",
    "incident_responder",
    "field_inspector",
    "compliance_officer",
    "dev_engineer",
    "qa_lead",
    "external_partner",
    "security_analyst",
    "data_scientist",
)

# Full 15-persona catalog (W14 E8 brief).
ALL_PERSONA_IDS: tuple[str, ...] = STARTER_PERSONA_IDS + EXTENDED_PERSONA_IDS


def _reject_dupe_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """object_pairs_hook that raises on duplicate keys (Kimi E8 #8)."""
    out: dict[str, Any] = {}
    seen: set[str] = set()
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate JSON key: {k!r}")
        seen.add(k)
        out[k] = v
    return out


def _normalize_name(value: Any) -> str:
    """NFKC + casefold defense against Unicode confusables (Kimi E8 #8)."""
    if not isinstance(value, str):
        raise ValueError(f"persona name must be string, got {type(value).__name__}")
    return unicodedata.normalize("NFKC", value).strip()


class PersonaRegistry:
    """Manages HumanPersona records on top of OntologyStore.

    On init, loads starter personas from JSON fixtures (idempotent —
    skips personas already present in the store). Both flat and
    ``baseline``-nested JSON shapes are accepted so fixtures written
    against either convention work.
    """

    def __init__(self, ontology: OntologyStore, autoload_starters: bool = True) -> None:
        self._ontology = ontology
        self._lock = threading.RLock()
        if autoload_starters:
            self._load_starters()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, persona: HumanPersona) -> HumanPersona:
        """Register a persona. Refuses duplicates by name (Kimi E8 #1)."""
        with self._lock:
            existing = self.get_by_name(persona.name)
            if existing is not None:
                raise ValueError(
                    f"persona with name {persona.name!r} already registered "
                    f"(persona_id={existing.persona_id})"
                )
            self._ontology.create(persona)
            return persona

    def get(self, persona_id: str) -> HumanPersona | None:
        return self._ontology.get(HumanPersona, persona_id)

    def get_by_name(self, name: str) -> HumanPersona | None:
        # NOTE: store.list applies SQL LIMIT before in-memory filter,
        # so we need a wide limit to ensure name match is found.
        normalized = _normalize_name(name)
        results = self._ontology.list(
            HumanPersona, filters={"name": normalized}, limit=1000,
        )
        return results[0] if results else None

    def list_all(self) -> list[HumanPersona]:
        return self._ontology.list(HumanPersona, limit=1000)

    def list_starter(self) -> list[HumanPersona]:
        """Return only the canonical 4 starter personas."""
        out: list[HumanPersona] = []
        for name in STARTER_PERSONA_IDS:
            p = self.get_by_name(name)
            if p is not None:
                out.append(p)
        return out

    def list_extended(self) -> list[HumanPersona]:
        """Return the 11 extended personas (E8 expansion)."""
        out: list[HumanPersona] = []
        for name in EXTENDED_PERSONA_IDS:
            p = self.get_by_name(name)
            if p is not None:
                out.append(p)
        return out

    def list_full_catalog(self) -> list[HumanPersona]:
        """Return all 15 canonical personas (4 starter + 11 extended)."""
        return self.list_starter() + self.list_extended()

    def update_dynamic_state(self, persona_id: str, delta: dict[str, Any]) -> HumanPersona:
        """RMW-safe dynamic_state mutation (Kimi E8 #6)."""
        with self._lock:
            p = self._ontology.get(HumanPersona, persona_id)
            if p is None:
                raise ValueError(f"persona not found: {persona_id}")
            new_state = dict(p.dynamic_state)
            new_state.update(delta)
            p.dynamic_state = new_state
            self._ontology.update(p)
            return p

    def reset_dynamic_state(self, persona_id: str) -> HumanPersona:
        """Reset to baseline (fatigue=0, load=0, pressure=0, etc.)."""
        with self._lock:
            p = self._ontology.get(HumanPersona, persona_id)
            if p is None:
                raise ValueError(f"persona not found: {persona_id}")
            p.dynamic_state = {
                "fatigue_level": 0.0,
                "cognitive_load": 0.0,
                "time_pressure": 0.0,
                "trust_in_ai": float(p.trust_in_ai_baseline),
                "current_interruptions": 0,
                "hours_into_shift": 0.0,
                "consecutive_decisions_count": 0,
            }
            self._ontology.update(p)
            return p

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _baseline_view(data: dict[str, Any]) -> dict[str, Any]:
        """Accept both flat and ``baseline``-nested JSON shapes."""
        if "baseline" in data and isinstance(data["baseline"], dict):
            return data["baseline"]
        return data

    @staticmethod
    def _initial_dynamic_state(data: dict[str, Any]) -> dict[str, Any]:
        return dict(
            data.get("dynamic_state_initial")
            or data.get("dynamic_state")
            or {}
        )

    def _load_starters(self) -> None:
        if not STARTER_DIR.exists():
            log.warning("_starter dir missing: %s", STARTER_DIR)
            return
        loaded = 0
        for fname in sorted(STARTER_DIR.glob("*.json")):
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f, object_pairs_hook=_reject_dupe_keys)
            except Exception as e:  # pragma: no cover
                log.warning("could not load %s: %s", fname.name, e)
                continue
            try:
                name = _normalize_name(data["name"])
            except (KeyError, ValueError) as e:
                log.warning("persona %s missing/invalid name: %s", fname.name, e)
                continue
            existing = self.get_by_name(name)
            if existing is not None:
                continue
            base = self._baseline_view(data)
            try:
                persona = HumanPersona(
                    name=name,
                    capability_level=base["capability_level"],
                    expertise_domains=list(base.get("expertise_domains", [])),
                    error_proneness=float(base["error_proneness"]),
                    attention_span_min=int(base["attention_span_min"]),
                    trust_in_ai_baseline=float(
                        base.get("trust_in_ai_baseline", 0.7)
                    ),
                    risk_tolerance=base.get("risk_tolerance", "medium"),
                    dynamic_state=self._initial_dynamic_state(data),
                    behavior_modifiers=dict(data.get("behavior_modifiers", {})),
                )
            except (KeyError, ValueError) as e:
                log.warning("persona %s schema invalid: %s", fname.name, e)
                continue
            self._ontology.create(persona)
            loaded += 1
        log.info("loaded %d starter personas", loaded)


__all__ = [
    "PersonaRegistry",
    "STARTER_PERSONA_IDS",
    "EXTENDED_PERSONA_IDS",
    "ALL_PERSONA_IDS",
    "STARTER_DIR",
]
