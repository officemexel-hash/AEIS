"""Smoke tests for register_testing_actions."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.actions import (
    ALL_HANDLER_CLASSES, register_testing_actions,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.enums import DLevel


@pytest.fixture
def store():
    return OntologyStore()


def test_all_handler_classes_present():
    assert len(ALL_HANDLER_CLASSES) == 20


def test_register_returns_20_handlers(store):
    handlers = register_testing_actions(ontology=store)
    assert len(handlers) == 20


def test_each_handler_unique_target_action(store):
    handlers = register_testing_actions(ontology=store)
    names = list(handlers.keys())
    assert len(names) == len(set(names))


def test_handler_class_attributes_set():
    """Each subclass must override target_action, d_level, phase."""
    for cls in ALL_HANDLER_CLASSES:
        assert cls.target_action != "", f"{cls.__name__} missing target_action"
        assert isinstance(cls.d_level, DLevel)
        assert cls.phase in ("TWO_PHASE", "IMMEDIATE")


def test_d_level_distribution(store):
    """Sanity check on D-level distribution per spec."""
    handlers = register_testing_actions(ontology=store)
    by_d = {}
    for h in handlers.values():
        by_d.setdefault(h.d_level, 0)
        by_d[h.d_level] += 1
    assert by_d[DLevel.D1] >= 6  # At least 6 D1 (immediate utilities)
    assert by_d[DLevel.D2] >= 4
    assert by_d[DLevel.D3] >= 5
    assert by_d[DLevel.D4] == 1  # only disable_test


def test_immediate_handlers_dont_mirror_ticket(store):
    """IMMEDIATE actions are mostly D0/D1 read/utility — no ticket needed."""
    handlers = register_testing_actions(ontology=store)
    for h in handlers.values():
        if h.phase == "IMMEDIATE":
            # All IMMEDIATE actions are D1 utilities — none mirror
            assert h.mirror_to_ticket is False, (
                f"{h.target_action}: IMMEDIATE+mirror_to_ticket=True is unusual"
            )


def test_two_phase_d2_or_higher_mirrors_ticket_default(store):
    """TWO_PHASE D2+ should default to mirror_to_ticket=True (audit chain).

    Exception: apply_patch_to_branch (already ticketed at proposal stage).
    """
    handlers = register_testing_actions(ontology=store)
    exempted = {"apply_patch_to_branch"}
    for h in handlers.values():
        if h.phase == "TWO_PHASE" and h.d_level.value >= "D2":
            if h.target_action in exempted:
                continue
            assert h.mirror_to_ticket is True, (
                f"{h.target_action}: D2+ TWO_PHASE without ticket mirror"
            )


def test_register_attaches_to_bus():
    """If bus given, handlers attached as bus._testing_handlers."""
    class FakeBus:
        pass
    bus = FakeBus()
    handlers = register_testing_actions(bus=bus, ontology=OntologyStore())
    assert hasattr(bus, "_testing_handlers")
    assert bus._testing_handlers is handlers
