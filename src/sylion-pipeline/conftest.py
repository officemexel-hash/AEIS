import pytest
import os

# Force SQLite :memory: for all tests
os.environ["SYLION_DB_PATH"] = ":memory:"


@pytest.fixture
def event_bus():
    from sylion.core.event_bus import EventBus
    return EventBus()


@pytest.fixture
def bus(event_bus):
    return event_bus


@pytest.fixture
def registry():
    from sylion.core.module_registry import ModuleRegistry
    return ModuleRegistry()


@pytest.fixture
def spine(event_bus):
    from sylion.core.evidence_spine import EvidenceSpine
    return EvidenceSpine(event_bus=event_bus)
