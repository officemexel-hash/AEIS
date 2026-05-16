"""W14 Testing Ontology — canonical 25 objects + 12 enums + OntologyStore.

Spec: docs/w14_workplan/ontology_spec.yaml (FROZEN, E0 HG approved 2026-04-26).
"""
from sylion.aeis.testing.ontology.enums import (
    BranchState,
    BranchType,
    DLevel,
    EvidenceTier,
    GateType,
    GuardianClass,
    HumanErrorClass,
    PersonaCapability,
    ReleaseStatus,
    RStatus,
    Severity,
    TestClass,
)
from sylion.aeis.testing.ontology.objects import (
    Branch,
    EvaluationSuite,
    Finding,
    GuardianAlert,
    HumanDecisionTrace,
    HumanErrorInjection,
    HumanNearMiss,
    HumanPersona,
    HumanScenario,
    LoopReport,
    PatchProposal,
    RegressionRun,
    ReleaseCandidate,
    ReleaseDecision,
    ReleaseReadinessReport,
    RepairAttempt,
    Requirement,
    SimulationBranch,
    SimulationContract,
    SimulationEvidence,
    TestCase,
    TestCharter,
    TestPlan,
    TestRun,
    TestSuite,
)
from sylion.aeis.testing.ontology.store import OntologyStore

ALL_OBJECTS: tuple[type, ...] = (
    Requirement,
    TestCharter,
    TestPlan,
    TestSuite,
    TestCase,
    EvaluationSuite,
    TestRun,
    RegressionRun,
    Finding,
    PatchProposal,
    RepairAttempt,
    LoopReport,
    GuardianAlert,
    SimulationContract,
    SimulationBranch,
    SimulationEvidence,
    HumanPersona,
    HumanScenario,
    HumanErrorInjection,
    HumanDecisionTrace,
    HumanNearMiss,
    Branch,
    ReleaseCandidate,
    ReleaseDecision,
    ReleaseReadinessReport,
)

__all__ = [
    # enums
    "BranchState", "BranchType", "DLevel", "EvidenceTier", "GateType",
    "GuardianClass", "HumanErrorClass", "PersonaCapability",
    "ReleaseStatus", "RStatus", "Severity", "TestClass",
    # objects
    "Branch", "EvaluationSuite", "Finding", "GuardianAlert",
    "HumanDecisionTrace", "HumanErrorInjection", "HumanNearMiss",
    "HumanPersona", "HumanScenario", "LoopReport", "PatchProposal",
    "RegressionRun", "ReleaseCandidate", "ReleaseDecision",
    "ReleaseReadinessReport", "RepairAttempt", "Requirement",
    "SimulationBranch", "SimulationContract", "SimulationEvidence",
    "TestCase", "TestCharter", "TestPlan", "TestRun", "TestSuite",
    # store
    "OntologyStore",
    # registry
    "ALL_OBJECTS",
]
