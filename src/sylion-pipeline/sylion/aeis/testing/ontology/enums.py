"""W14 Testing Ontology — canonical enums.

All enums are str subclasses so SQLite can persist them as TEXT and
JSON serialization is trivial. Each enum exposes a `.values()` classmethod
returning a tuple of canonical string values for validators / migrations.

Spec: docs/w14_workplan/ontology_spec.yaml (FROZEN 2026-04-26).
"""
from __future__ import annotations

from enum import Enum


class _SylionEnum(str, Enum):
    """Base for all W14 enums — adds .values() classmethod."""

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls.values()

    def __str__(self) -> str:
        return self.value


class DLevel(_SylionEnum):
    """Decision class D0-D5 (canonical AEIS D-ladder)."""
    D0 = "D0"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"
    D5 = "D5"


class RStatus(_SylionEnum):
    """Finding repair lifecycle (R0-R9 + waiting/escalation states)."""
    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    REPRODUCED = "REPRODUCED"
    CLASSIFIED = "CLASSIFIED"
    REPAIR_PROPOSED = "REPAIR_PROPOSED"
    WAITING_FOR_HUMAN_GATE = "WAITING_FOR_HUMAN_GATE"
    REPAIRING = "REPAIRING"
    READY_FOR_RETEST = "READY_FOR_RETEST"
    REGRESSION_FAILED = "REGRESSION_FAILED"
    VERIFIED = "VERIFIED"
    ESCALATED = "ESCALATED"
    WAIVED_BY_HUMAN = "WAIVED_BY_HUMAN"
    CLOSED = "CLOSED"


class TestClass(_SylionEnum):
    """T0-T19 testing classes."""

    __test__ = False  # pytest: this is the W14 enum, not a test container
    SPEC_ALIGNMENT = "T0"
    MASTERPLAN_ALIGNMENT = "T1"
    UNIT = "T2"
    API_CONTRACT = "T3"
    INTEGRATION = "T4"
    UI_E2E = "T5"
    HUMAN_LIKE = "T6"
    HUMAN_ERROR_INJECTION = "T7"
    NEGATIVE_ADVERSARIAL = "T8"
    REGRESSION = "T9"
    SECURITY = "T10"
    GOVERNANCE = "T11"
    PERFORMANCE = "T12"
    CHAOS_RECOVERY = "T13"
    REAL_EXAMPLE = "T14"
    RELEASE_REHEARSAL = "T15"
    PROPERTY_BASED = "T16"
    MUTATION_TESTING = "T17"
    DIFFERENTIAL_SHADOW = "T18"
    LLM_BEHAVIORAL = "T19"


class ReleaseStatus(_SylionEnum):
    """10 release lifecycle statuses."""
    NOT_TESTED = "NOT_TESTED"
    TESTING_IN_PROGRESS = "TESTING_IN_PROGRESS"
    BLOCKED_BY_FINDINGS = "BLOCKED_BY_FINDINGS"
    BLOCKED_BY_GOVERNANCE = "BLOCKED_BY_GOVERNANCE"
    READY_FOR_RELEASE_CANDIDATE = "READY_FOR_RELEASE_CANDIDATE"
    RELEASE_CANDIDATE = "RELEASE_CANDIDATE"
    READY_FOR_PRODUCTION = "READY_FOR_PRODUCTION"
    PRODUCTION_RELEASED = "PRODUCTION_RELEASED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    ARCHIVED = "ARCHIVED"


class Severity(_SylionEnum):
    """Finding severity P0-P4."""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class GateType(_SylionEnum):
    """10 canonical gate types (mirrored to existing tickets plane)."""
    BLOCKING = "blocking"
    NON_BLOCKING = "non_blocking"
    BATCH = "batch"
    EMERGENCY = "emergency"
    FINANCIAL = "financial"
    LEGAL = "legal"
    PRODUCTION = "production"
    SECURITY = "security"
    EXTERNAL_ACTION = "external_action"
    FINAL = "final"


class HumanErrorClass(_SylionEnum):
    """14 core + 7 extended human error classes."""
    # Core 14
    WRONG_CLICK = "wrong_click"
    GATE_SKIP = "gate_skip"
    PREMATURE_ACTION = "premature_action"
    STALE_DATA_ACTION = "stale_data_action"
    MOCK_AS_LIVE = "mock_as_live"
    BYPASS_ATTEMPT = "bypass_attempt"
    TYPO_PAYLOAD = "typo_payload"
    MULTI_TAB_CONFUSION = "multi_tab_confusion"
    PANIC_CANCEL = "panic_cancel"
    WRONG_CONTEXT = "wrong_context"
    PERMISSION_OVERREACH = "permission_overreach"
    TIMEOUT_ABANDONMENT = "timeout_abandonment"
    AUTHORITY_ABUSE = "authority_abuse"
    COGNITIVE_OVERLOAD = "cognitive_overload"
    # Extended 7
    CARGO_CULT_APPROVAL = "cargo_cult_approval"
    CONFIRMATION_BIAS = "confirmation_bias"
    ANCHOR_MISMATCH = "anchor_mismatch"
    SUNK_COST_TRAP = "sunk_cost_trap"
    HALO_EFFECT = "halo_effect"
    TIME_PRESSURE_SHORTCUT = "time_pressure_shortcut"
    AUTHORITY_DEFERENCE = "authority_deference"


class EvidenceTier(_SylionEnum):
    """H0-H4 evidence quality tiers."""
    H0 = "H0"  # static_heuristic_ui
    H1 = "H1"  # simulated_persona
    H2 = "H2"  # llm_persona_with_trace
    H3 = "H3"  # real_human_controlled_test
    H4 = "H4"  # production_telemetry_feedback


class BranchType(_SylionEnum):
    """Types of branches in W14."""
    SIMULATION = "simulation"
    REPAIR = "repair"
    TEST = "test"
    RELEASE = "release"


class BranchState(_SylionEnum):
    OPEN = "open"
    MERGED = "merged"
    DISCARDED = "discarded"


class PersonaCapability(_SylionEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class GuardianClass(_SylionEnum):
    """13 guardians (8 core + 5 NEW)."""
    SOT_GUARDIAN = "sot_guardian"
    MASTERPLAN_GUARDIAN = "masterplan_guardian"
    TEST_INTEGRITY_GUARDIAN = "test_integrity_guardian"
    MOCK_FALLBACK_GUARDIAN = "mock_fallback_guardian"
    EVIDENCE_GUARDIAN = "evidence_guardian"
    GATE_GUARDIAN = "gate_guardian"
    COUNCIL_GUARDIAN = "council_guardian"
    RELEASE_GUARDIAN = "release_guardian"
    LOOP_GUARDIAN = "loop_guardian"
    LLM_DRIFT_GUARDIAN = "llm_drift_guardian"
    COST_SENTINEL = "cost_sentinel"
    PII_GUARDIAN = "pii_guardian"
    TRACE_COMPLETENESS_GUARDIAN = "trace_completeness_guardian"


ALL_ENUMS: tuple[type[_SylionEnum], ...] = (
    DLevel,
    RStatus,
    TestClass,
    ReleaseStatus,
    Severity,
    GateType,
    HumanErrorClass,
    EvidenceTier,
    BranchType,
    BranchState,
    PersonaCapability,
    GuardianClass,
)


__all__ = [
    "DLevel", "RStatus", "TestClass", "ReleaseStatus",
    "Severity", "GateType", "HumanErrorClass", "EvidenceTier",
    "BranchType", "BranchState", "PersonaCapability", "GuardianClass",
    "ALL_ENUMS",
]
