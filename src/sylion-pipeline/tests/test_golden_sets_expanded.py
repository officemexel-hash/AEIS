"""
test_golden_sets_expanded.py - 25+ tests for expanded golden sets.

Tests cover:
  1. Each golden set JSON is loadable and valid (schema checks)
  2. Each golden set has required fields
  3. Validation script infrastructure works
  4. Integration: run golden sets against in-memory modules
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import pytest

# Ensure project root is on sys.path so `import sylion.*` works
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = _PROJECT_ROOT
GOLDEN_SETS_DIR = PROJECT_ROOT / "sylion" / "contracts" / "golden_sets"

GOLDEN_FILES = {
    "core_module_registry": GOLDEN_SETS_DIR / "core_module_registry.json",
    "core_contract_registry": GOLDEN_SETS_DIR / "core_contract_registry.json",
    "security_evidence_spine": GOLDEN_SETS_DIR / "security_evidence_spine.json",
    "governance_council": GOLDEN_SETS_DIR / "governance_council.json",
    "core_legacy": GOLDEN_SETS_DIR / "core.json",
}


# ===================================================================
# PART 1: Golden set JSON loading & schema validation (5 tests)
# ===================================================================

class TestGoldenSetLoading:
    """Each golden set file is valid JSON and loadable."""

    @pytest.mark.parametrize("name,path", list(GOLDEN_FILES.items()))
    def test_golden_set_is_valid_json(self, name, path):
        """Golden set file exists and parses as JSON."""
        assert path.exists(), f"Golden set file missing: {path}"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{name}: root must be a dict"

    @pytest.mark.parametrize("name,path", list(GOLDEN_FILES.items()))
    def test_golden_set_has_required_top_level_fields(self, name, path):
        """Every golden set must have 'class', 'module', and 'tests'."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "class" in data, f"{name}: missing 'class'"
        assert "module" in data, f"{name}: missing 'module'"
        assert "tests" in data, f"{name}: missing 'tests'"
        assert isinstance(data["tests"], list), f"{name}: 'tests' must be a list"

    @pytest.mark.parametrize("name,path", list(GOLDEN_FILES.items()))
    def test_golden_set_tests_have_method_field(self, name, path):
        """Every test entry in a golden set must have a 'method' field."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for i, test in enumerate(data["tests"]):
            assert "method" in test, f"{name} test[{i}]: missing 'method'"

    @pytest.mark.parametrize("name,path", [
        (k, v) for k, v in GOLDEN_FILES.items() if k != "core_legacy"
    ])
    def test_golden_set_tests_have_id_field(self, name, path):
        """Every test entry should have an 'id' field for traceability."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for i, test in enumerate(data["tests"]):
            assert "id" in test, f"{name} test[{i}]: missing 'id'"

    @pytest.mark.parametrize("name,path", list(GOLDEN_FILES.items()))
    def test_golden_set_test_ids_are_unique(self, name, path):
        """Test IDs within a golden set must be unique."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = [t.get("id") for t in data["tests"] if "id" in t]
        assert len(ids) == len(set(ids)), f"{name}: duplicate test IDs found"


# ===================================================================
# PART 2: Golden set content validation (10 tests)
# ===================================================================

class TestGoldenSetContent:
    """Validate the content structure of each expanded golden set."""

    def test_module_registry_has_register_tests(self):
        with open(GOLDEN_FILES["core_module_registry"], "r", encoding="utf-8") as f:
            data = json.load(f)
        methods = {t["method"] for t in data["tests"]}
        assert "register" in methods, "core_module_registry: missing 'register' test"
        assert "get" in methods, "core_module_registry: missing 'get' test"
        assert "transition" in methods, "core_module_registry: missing 'transition' test"

    def test_module_registry_has_lifecycle_transitions(self):
        """Golden set should cover the full lifecycle: draft -> stable -> deprecated."""
        with open(GOLDEN_FILES["core_module_registry"], "r", encoding="utf-8") as f:
            data = json.load(f)
        transition_tests = [t for t in data["tests"] if t["method"] == "transition"]
        targets = {t["input"].get("target") for t in transition_tests}
        for stage in ("build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"):
            assert stage in targets, f"Missing transition to '{stage}'"

    def test_module_registry_has_error_cases(self):
        """Golden set should test error paths."""
        with open(GOLDEN_FILES["core_module_registry"], "r", encoding="utf-8") as f:
            data = json.load(f)
        error_tests = [t for t in data["tests"] if "expected_error" in t]
        assert len(error_tests) >= 3, "Should have at least 3 error test cases"

    def test_contract_registry_has_publish_and_get(self):
        with open(GOLDEN_FILES["core_contract_registry"], "r", encoding="utf-8") as f:
            data = json.load(f)
        methods = {t["method"] for t in data["tests"]}
        assert "publish" in methods
        assert "get" in methods
        assert "check_compatibility" in methods
        assert "list_versions" in methods

    def test_contract_registry_covers_breaking_change(self):
        """Should test a major version bump (breaking change)."""
        with open(GOLDEN_FILES["core_contract_registry"], "r", encoding="utf-8") as f:
            data = json.load(f)
        publish_tests = [t for t in data["tests"]
                         if t["method"] == "publish" and "expected" in t]
        breaking = [t for t in publish_tests if t["expected"].get("breaking") is True]
        assert len(breaking) >= 1, "Should test at least one breaking change"

    def test_evidence_spine_has_append_and_query(self):
        with open(GOLDEN_FILES["security_evidence_spine"], "r", encoding="utf-8") as f:
            data = json.load(f)
        methods = {t["method"] for t in data["tests"]}
        assert "append" in methods
        assert "query" in methods
        assert "verify_chain" in methods

    def test_evidence_spine_genesis_has_zero_prev_hash(self):
        """First append should reference the genesis zero hash."""
        with open(GOLDEN_FILES["security_evidence_spine"], "r", encoding="utf-8") as f:
            data = json.load(f)
        append_tests = [t for t in data["tests"] if t["method"] == "append"]
        genesis = [t for t in append_tests if t.get("id") == "append_genesis"]
        assert len(genesis) == 1, "Missing append_genesis test"
        assert genesis[0]["expected"]["prev_hash"] == "0" * 64

    def test_council_has_session_and_vote_methods(self):
        with open(GOLDEN_FILES["governance_council"], "r", encoding="utf-8") as f:
            data = json.load(f)
        methods = {t["method"] for t in data["tests"]}
        assert "open_session" in methods
        assert "cast_vote" in methods
        assert "tally" in methods

    def test_council_covers_approval_and_rejection(self):
        """Should cover both approval and rejection flows."""
        with open(GOLDEN_FILES["governance_council"], "r", encoding="utf-8") as f:
            data = json.load(f)
        tally_tests = [t for t in data["tests"] if t["method"] == "tally" and "expected" in t]
        outcomes = {t["expected"].get("outcome") for t in tally_tests}
        assert "approved" in outcomes, "Missing approval flow"
        assert "rejected" in outcomes, "Missing rejection flow"

    def test_all_four_expanded_golden_sets_have_minimum_tests(self):
        """Each expanded golden set should have at least 10 test cases."""
        for name in ("core_module_registry", "core_contract_registry",
                     "security_evidence_spine", "governance_council"):
            with open(GOLDEN_FILES[name], "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data["tests"]) >= 10, (
                f"{name} has only {len(data['tests'])} tests, need >= 10"
            )


# ===================================================================
# PART 3: Validation script infrastructure (4 tests)
# ===================================================================

class TestValidationScript:
    """Test the validate_golden_sets.py script infrastructure."""

    def test_validation_script_exists(self):
        script_path = PROJECT_ROOT / "scripts" / "validate_golden_sets.py"
        assert script_path.exists(), "validate_golden_sets.py missing"

    def test_validation_script_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_golden_sets",
            str(PROJECT_ROOT / "scripts" / "validate_golden_sets.py")
        )
        assert spec is not None

    def test_deep_match_function(self):
        """Test the deep subset matching logic."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_golden_sets",
            str(PROJECT_ROOT / "scripts" / "validate_golden_sets.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Exact match
        assert mod._deep_match({"a": 1, "b": 2}, {"a": 1}) == []

        # Missing key
        devs = mod._deep_match({"a": 1}, {"b": 2})
        assert len(devs) > 0

        # Nested match
        assert mod._deep_match(
            {"x": {"y": 1, "z": 2}}, {"x": {"y": 1}}
        ) == []

    def test_list_contains_subset_function(self):
        """Test the list subset checking logic."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_golden_sets",
            str(PROJECT_ROOT / "scripts" / "validate_golden_sets.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod._list_contains_subset(
            [{"a": 1, "b": 2}, {"c": 3}], {"a": 1}
        )
        assert not mod._list_contains_subset(
            [{"a": 1}, {"c": 3}], {"a": 2}
        )


# ===================================================================
# PART 4: Integration - ModuleRegistry golden tests (8 tests)
# ===================================================================

class TestModuleRegistryGoldenIntegration:
    """Run ModuleRegistry golden tests against live in-memory instances."""

    def _make_registry(self):
        from sylion.core.module_registry import ModuleRegistry
        return ModuleRegistry(db_path=":memory:")

    def test_register_minimal(self):
        from sylion.core.module_registry import ModuleManifest, ModuleKind
        registry = self._make_registry()
        manifest = ModuleManifest(
            module_id="golden.mod_reg_01",
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
            description="Golden test module 01",
        )
        result = registry.register(manifest)
        assert result["module_id"] == "golden.mod_reg_01"
        assert result["module_kind"] == "A"
        assert result["owner_plan"] == "P01"
        assert result["lifecycle_stage"] == "draft"

    def test_register_full_fields(self):
        from sylion.core.module_registry import ModuleManifest, ModuleKind, SecurityProfile
        registry = self._make_registry()
        manifest = ModuleManifest(
            module_id="golden.mod_reg_02",
            module_kind=ModuleKind.COGNITIVE,
            owner_plan="P05",
            implementation_strategy="strangler-fig",
            contract_version="2.1.0",
            decision_class_entry="D4",
            security_profile=SecurityProfile.STAGING_STRICT,
            auth_mode="jwt",
            execution_guard="sandbox",
            audit_mode="full",
            depends_on=[],
            description="Golden full-field module",
            version="3.0.0",
            milestone="M3",
        )
        result = registry.register(manifest)
        assert result["module_id"] == "golden.mod_reg_02"
        assert result["module_kind"] == "B"
        assert result["milestone"] == "M3"

    def test_register_with_dependency(self):
        from sylion.core.module_registry import ModuleManifest, ModuleKind
        registry = self._make_registry()
        # Register parent first
        registry.register(ModuleManifest(
            module_id="parent.mod", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01",
        ))
        child = ModuleManifest(
            module_id="child.mod", module_kind=ModuleKind.EXECUTION, owner_plan="P01",
            depends_on=["parent.mod"],
        )
        result = registry.register(child)
        assert result["module_id"] == "child.mod"

    def test_register_duplicate_raises(self):
        from sylion.core.module_registry import ModuleManifest, ModuleKind
        registry = self._make_registry()
        registry.register(ModuleManifest(
            module_id="dup.mod", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01",
        ))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(ModuleManifest(
                module_id="dup.mod", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01",
            ))

    def test_get_existing(self):
        from sylion.core.module_registry import ModuleManifest, ModuleKind
        registry = self._make_registry()
        registry.register(ModuleManifest(
            module_id="get.mod", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01",
        ))
        result = registry.get("get.mod")
        assert result is not None
        assert result["module_id"] == "get.mod"
        assert result["lifecycle"] == "draft"

    def test_get_nonexistent(self):
        registry = self._make_registry()
        result = registry.get("nonexistent")
        assert result is None

    def test_list_with_filters(self):
        from sylion.core.module_registry import ModuleManifest, ModuleKind
        registry = self._make_registry()
        registry.register(ModuleManifest(
            module_id="filter.a", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01",
        ))
        registry.register(ModuleManifest(
            module_id="filter.b", module_kind=ModuleKind.COGNITIVE, owner_plan="P02",
        ))
        result = registry.list_modules(kind="A")
        assert len(result) == 1
        assert result[0]["module_id"] == "filter.a"

    def test_full_lifecycle_transition(self):
        from sylion.core.module_registry import ModuleManifest, ModuleLifecycleStage, ModuleKind
        registry = self._make_registry()
        registry.register(ModuleManifest(
            module_id="life.mod", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01",
        ))
        stages = ["build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"]
        for stage in stages:
            result = registry.transition("life.mod", ModuleLifecycleStage(stage))
            assert result["lifecycle"] == stage


# ===================================================================
# PART 5: Integration - ContractRegistry golden tests (7 tests)
# ===================================================================

class TestContractRegistryGoldenIntegration:
    """Run ContractRegistry golden tests against live in-memory instances."""

    def _make_registry(self):
        from sylion.core.contract_registry import ContractRegistry
        return ContractRegistry(db_path=":memory:")

    def test_publish_initial(self):
        from sylion.core.contract_registry import Contract, ContractType
        registry = self._make_registry()
        contract = Contract(
            name="golden.contract_auth",
            contract_type=ContractType.GRPC_SERVICE,
            version="1.0.0",
            schema_def="service AuthService { rpc Login(LoginReq) returns (LoginRes); }",
            producer_module="golden.mod_auth",
            consumer_modules=["golden.mod_api"],
            description="Auth service contract v1",
        )
        result = registry.publish(contract)
        assert result["name"] == "golden.contract_auth"
        assert result["version"] == "1.0.0"
        assert result["breaking"] is False

    def test_publish_major_breaking(self):
        from sylion.core.contract_registry import Contract, ContractType
        registry = self._make_registry()
        # First version
        registry.publish(Contract(
            name="golden.breaking", contract_type=ContractType.GRPC_SERVICE,
            version="1.0.0",
        ))
        # Major bump
        result = registry.publish(Contract(
            name="golden.breaking", contract_type=ContractType.GRPC_SERVICE,
            version="2.0.0",
        ))
        assert result["breaking"] is True

    def test_get_latest_version(self):
        from sylion.core.contract_registry import Contract, ContractType
        registry = self._make_registry()
        registry.publish(Contract(name="golden.get_test", version="1.0.0"))
        registry.publish(Contract(name="golden.get_test", version="1.1.0"))
        result = registry.get("golden.get_test")
        assert result["version"] == "1.1.0"
        assert result["is_latest"] == 1

    def test_get_specific_version(self):
        from sylion.core.contract_registry import Contract
        registry = self._make_registry()
        registry.publish(Contract(name="golden.spec_ver", version="1.0.0"))
        registry.publish(Contract(name="golden.spec_ver", version="2.0.0"))
        result = registry.get("golden.spec_ver", version="1.0.0")
        assert result["version"] == "1.0.0"
        assert result["is_latest"] == 0

    def test_get_nonexistent(self):
        registry = self._make_registry()
        result = registry.get("no.such.contract")
        assert result is None

    def test_check_compatibility_compatible(self):
        from sylion.core.contract_registry import Contract
        registry = self._make_registry()
        registry.publish(Contract(name="golden.compat", version="1.0.0"))
        result = registry.check_compatibility("golden.compat", "1.2.0")
        assert result["compatible"] is True
        assert result["breaking"] is False

    def test_check_compatibility_breaking(self):
        from sylion.core.contract_registry import Contract
        registry = self._make_registry()
        registry.publish(Contract(name="golden.compat2", version="1.0.0"))
        result = registry.check_compatibility("golden.compat2", "2.0.0")
        assert result["compatible"] is False
        assert result["breaking"] is True
        assert "breaking change detected" in result["message"]

    def test_list_versions(self):
        from sylion.core.contract_registry import Contract
        registry = self._make_registry()
        registry.publish(Contract(name="golden.versions", version="1.0.0"))
        registry.publish(Contract(name="golden.versions", version="1.1.0"))
        registry.publish(Contract(name="golden.versions", version="2.0.0"))
        versions = registry.list_versions("golden.versions")
        assert len(versions) == 3


# ===================================================================
# PART 6: Integration - EvidenceSpine golden tests (5 tests)
# ===================================================================

class TestEvidenceSpineGoldenIntegration:
    """Run EvidenceSpine golden tests against live in-memory instances."""

    def _make_spine(self):
        from sylion.core.evidence_spine import EvidenceSpine
        return EvidenceSpine(db_path=":memory:")

    def test_append_genesis(self):
        from sylion.core.evidence_spine import EvidenceEntry
        spine = self._make_spine()
        entry = EvidenceEntry(
            source_plan="P01",
            event_type="decision.made",
            payload={"decision": "deploy", "module": "golden.test"},
            actor_id="agent.alpha",
        )
        result = spine.append(entry)
        assert result["prev_hash"] == "0" * 64
        assert len(result["hash"]) == 64
        assert result["entry_id"] == entry.entry_id

    def test_append_chain_links(self):
        from sylion.core.evidence_spine import EvidenceEntry
        spine = self._make_spine()
        r1 = spine.append(EvidenceEntry(
            source_plan="P01", event_type="e1", payload={"x": 1},
        ))
        r2 = spine.append(EvidenceEntry(
            source_plan="P01", event_type="e2", payload={"x": 2},
        ))
        # Second entry's prev_hash must be first entry's hash
        assert r2["prev_hash"] == r1["hash"]

    def test_query_by_plan(self):
        from sylion.core.evidence_spine import EvidenceEntry
        spine = self._make_spine()
        spine.append(EvidenceEntry(source_plan="P01", event_type="e1", payload={"x": 1}))
        spine.append(EvidenceEntry(source_plan="P02", event_type="e2", payload={"x": 2}))
        spine.append(EvidenceEntry(source_plan="P01", event_type="e3", payload={"x": 3}))

        p01 = spine.query(source_plan="P01")
        assert len(p01) == 2

    def test_query_by_event_type(self):
        from sylion.core.evidence_spine import EvidenceEntry
        spine = self._make_spine()
        spine.append(EvidenceEntry(source_plan="P01", event_type="decision.made", payload={}))
        spine.append(EvidenceEntry(source_plan="P01", event_type="review.done", payload={}))
        results = spine.query(event_type="decision.made")
        assert len(results) == 1
        assert results[0]["event_type"] == "decision.made"

    def test_verify_chain_valid(self):
        from sylion.core.evidence_spine import EvidenceEntry
        spine = self._make_spine()
        for i in range(5):
            spine.append(EvidenceEntry(
                source_plan="P01", event_type=f"event_{i}",
                payload={"index": i},
            ))
        valid, msg = spine.verify_chain()
        assert valid is True
        assert "5 entries" in msg

    def test_verify_chain_empty(self):
        spine = self._make_spine()
        valid, msg = spine.verify_chain()
        assert valid is True
        assert "empty" in msg.lower()


# ===================================================================
# PART 7: Integration - CouncilWorkflow golden tests (7 tests)
# ===================================================================

class TestCouncilWorkflowGoldenIntegration:
    """Run CouncilWorkflow golden tests against live in-memory instances."""

    def _make_council(self):
        from sylion.governance.council_workflow import CouncilWorkflow
        return CouncilWorkflow(db_path=":memory:")

    def _open_session(self, council, proposal_id="prop.golden_001", decision_class="D3"):
        from sylion.governance.council_workflow import CouncilSession
        from sylion.core.decision_gate_engine import DecisionClass
        session = CouncilSession(
            proposal_id=proposal_id,
            decision_class=DecisionClass(decision_class),
            title=f"Session for {proposal_id}",
        )
        return council.open_session(session)

    def test_open_session(self):
        council = self._make_council()
        result = self._open_session(council)
        assert result["status"] == "open"
        assert "session_id" in result

    def test_cast_vote_and_tally_approved(self):
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        session = self._open_session(council)
        sid = session["session_id"]

        for i in range(1, 5):
            result = council.cast_vote(Vote(
                session_id=sid,
                member_id=f"council.m{i}",
                value=VoteValue.APPROVE,
                rationale=f"Approve {i}",
            ))
            assert result["cast"] is True

        tally = council.tally(sid)
        assert tally["approves"] == 4
        assert tally["rejects"] == 0
        assert tally["resolved"] is True
        assert tally["outcome"] == "approved"

    def test_cast_vote_and_tally_rejected(self):
        """Test rejection: first reject auto-resolves because rejects(1) > (4 - 4) = 0."""
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        session = self._open_session(council, "prop.reject_test")
        sid = session["session_id"]

        # Cast first reject -- this auto-resolves since rejects(1) > (4 - 4) = 0
        result = council.cast_vote(Vote(
            session_id=sid,
            member_id="council.r1",
            value=VoteValue.REJECT,
            rationale="Reject 1",
        ))
        assert result["cast"] is True

        tally = council.tally(sid)
        assert tally["rejects"] == 1
        assert tally["total"] == 1
        assert tally["resolved"] is True
        assert tally["outcome"] == "rejected"

    def test_duplicate_vote_rejected(self):
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        session = self._open_session(council)
        sid = session["session_id"]

        council.cast_vote(Vote(
            session_id=sid, member_id="dup.member", value=VoteValue.APPROVE,
        ))
        result = council.cast_vote(Vote(
            session_id=sid, member_id="dup.member", value=VoteValue.APPROVE,
        ))
        assert result["cast"] is False
        assert "already voted" in result["message"].lower()

    def test_vote_on_nonexistent_session(self):
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        result = council.cast_vote(Vote(
            session_id="no.such.session",
            member_id="council.m1",
            value=VoteValue.APPROVE,
        ))
        assert result["cast"] is False
        assert "not found" in result["message"].lower()

    def test_get_session_after_closure(self):
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        session = self._open_session(council)
        sid = session["session_id"]

        for i in range(1, 5):
            council.cast_vote(Vote(
                session_id=sid, member_id=f"council.g{i}",
                value=VoteValue.APPROVE,
            ))

        result = council.get_session(sid)
        assert result["status"] == "closed_approved"
        assert result["proposal_id"] == "prop.golden_001"

    def test_list_sessions_by_status(self):
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        s1 = self._open_session(council, "prop.list_1")
        s2 = self._open_session(council, "prop.list_2")

        # Approve s1
        for i in range(1, 5):
            council.cast_vote(Vote(
                session_id=s1["session_id"],
                member_id=f"council.l1_{i}",
                value=VoteValue.APPROVE,
            ))

        open_sessions = council.list_sessions(status="open")
        approved_sessions = council.list_sessions(status="closed_approved")

        # s2 should still be open
        assert any(s["session_id"] == s2["session_id"] for s in open_sessions)
        # s1 should be closed_approved
        assert any(s["session_id"] == s1["session_id"] for s in approved_sessions)

    def test_human_gate_for_d4(self):
        from sylion.governance.council_workflow import Vote, VoteValue
        council = self._make_council()
        session = self._open_session(council, "prop.d4_test", "D4")
        sid = session["session_id"]

        # Approve all 4 votes first
        for i in range(1, 5):
            council.cast_vote(Vote(
                session_id=sid, member_id=f"council.d4_{i}",
                value=VoteValue.APPROVE,
            ))

        result = council.human_gate_decide(sid, "approved", "human.operator")
        assert result["decided"] is True
        assert result["human_gate"] == "approved"
