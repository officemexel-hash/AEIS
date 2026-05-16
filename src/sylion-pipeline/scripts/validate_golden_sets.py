#!/usr/bin/env python3
"""
SYLION AEIS - Expanded Golden Set Validator

Runs each golden set against live in-memory module instances:
  1. Load golden set JSON
  2. Instantiate the target module in-memory
  3. Execute test cases sequentially, respecting prerequisites
  4. Compare actual output to expected output
  5. Report pass/fail with detailed deviations

Supports extended golden set fields:
  - expected_error: expect an exception containing this substring
  - expected_type: assert result is of this Python type
  - expected_length: assert list/tuple has exact length
  - expected_min_length / expected_max_length: length bounds
  - expected_has: assert result dict contains these keys
  - expected_contains: assert a list item contains the given dict subset
  - expected_first: for tuple results, assert first element value
  - expected_tally: match the auto-tally dict within cast_vote result
  - prerequisite: test id that must have been executed before this one
  - session_id_ref: reference to a prior test that returned a session_id

Exit codes:
  0 = all tests pass
  1 = one or more failures
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GOLDEN_SETS_DIR = PROJECT_ROOT / "sylion" / "contracts" / "golden_sets"


# ---------------------------------------------------------------------------
# Deep subset matching
# ---------------------------------------------------------------------------

def _deep_match(actual: Any, expected: Any, path: str = "") -> list[str]:
    """Check that actual is a superset of expected (recursive)."""
    deviations: list[str] = []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            deviations.append(f"{path or 'root'}: expected dict, got {type(actual).__name__}")
            return deviations
        for key, exp_val in expected.items():
            sub_path = f"{path}.{key}" if path else key
            if key not in actual:
                deviations.append(f"{sub_path}: missing key (expected {exp_val!r})")
            else:
                deviations.extend(_deep_match(actual[key], exp_val, sub_path))
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            deviations.append(f"{path or 'root'}: expected list, got {type(actual).__name__}")
            return deviations
        if len(actual) != len(expected):
            deviations.append(
                f"{path or 'root'}: list length mismatch (expected {len(expected)}, got {len(actual)})"
            )
        for i, (a_item, e_item) in enumerate(zip(actual, expected)):
            deviations.extend(_deep_match(a_item, e_item, f"{path}[{i}]"))
    else:
        if actual != expected:
            deviations.append(
                f"{path or 'root'}: value mismatch (expected {expected!r}, got {actual!r})"
            )

    return deviations


def _list_contains_subset(lst: list, subset: dict) -> bool:
    """Check if any item in lst (list of dicts) contains all keys from subset."""
    for item in lst:
        if not isinstance(item, dict):
            continue
        if all(item.get(k) == v for k, v in subset.items()):
            return True
    return False


# ---------------------------------------------------------------------------
# Module constructors
# ---------------------------------------------------------------------------

def _make_module_registry():
    from sylion.core.module_registry import ModuleRegistry
    return ModuleRegistry(db_path=":memory:")


def _make_contract_registry():
    from sylion.core.contract_registry import ContractRegistry
    return ContractRegistry(db_path=":memory:")


def _make_evidence_spine():
    from sylion.core.evidence_spine import EvidenceSpine
    return EvidenceSpine(db_path=":memory:")


def _make_council_workflow():
    from sylion.governance.council_workflow import CouncilWorkflow
    return CouncilWorkflow(db_path=":memory:")


MODULE_BUILDERS = {
    "core.module_registry": _make_module_registry,
    "core.contract_registry": _make_contract_registry,
    "core.evidence_spine": _make_evidence_spine,
    "governance.council_workflow": _make_council_workflow,
}


# ---------------------------------------------------------------------------
# Result store (for prerequisite / session_id_ref lookups)
# ---------------------------------------------------------------------------

class ResultStore:
    """Stores test results by test id for cross-test references."""

    def __init__(self):
        self._results: dict[str, Any] = {}
        self._session_ids: dict[str, str] = {}

    def store(self, test_id: str, result: Any):
        self._results[test_id] = result
        # Auto-extract session_id if present
        if isinstance(result, dict) and "session_id" in result:
            self._session_ids[test_id] = result["session_id"]

    def get_result(self, test_id: str) -> Any:
        return self._results.get(test_id)

    def get_session_id(self, test_id: str) -> str | None:
        return self._session_ids.get(test_id)


# ---------------------------------------------------------------------------
# Test executor for a single golden set file
# ---------------------------------------------------------------------------

def run_golden_set(gs_path: Path) -> tuple[int, int, list[str]]:
    """Run one golden set file. Returns (passed, failed, details)."""
    with open(gs_path, "r", encoding="utf-8") as f:
        gs_data = json.load(f)

    module_fqn = gs_data.get("module", "")
    tests = gs_data.get("tests", [])
    class_letter = gs_data.get("class", "?")

    passed = 0
    failed = 0
    details: list[str] = []

    if not module_fqn:
        details.append("  SKIP: no 'module' field in golden set")
        return 0, 0, details

    # Create the live module instance
    builder = MODULE_BUILDERS.get(module_fqn)
    if builder is None:
        for t in tests:
            method = t.get("method", "?")
            details.append(f"  FAIL [{module_fqn}.{method}]: no builder for module")
            failed += 1
        return passed, failed, details

    try:
        instance = builder()
    except Exception as e:
        for t in tests:
            method = t.get("method", "?")
            details.append(f"  FAIL [{module_fqn}.{method}]: build error: {e}")
            failed += 1
        return passed, failed, details

    store = ResultStore()

    for test in tests:
        test_id = test.get("id", "?")
        method_name = test.get("method", "?")
        test_input = dict(test.get("input", {}))
        expected = test.get("expected", None)
        expected_error = test.get("expected_error", None)
        expected_type = test.get("expected_type", None)
        expected_length = test.get("expected_length", None)
        expected_min_length = test.get("expected_min_length", None)
        expected_max_length = test.get("expected_max_length", None)
        expected_has = test.get("expected_has", None)
        expected_contains = test.get("expected_contains", None)
        expected_first = test.get("expected_first", None)
        expected_tally = test.get("expected_tally", None)

        full_label = f"{module_fqn}::{method_name} [{test_id}] (class {class_letter})"

        # Resolve session_id_ref -> actual session_id
        session_ref = test_input.pop("session_id_ref", None)
        if session_ref:
            resolved = store.get_session_id(session_ref)
            if resolved:
                test_input["session_id"] = resolved
            else:
                details.append(f"  FAIL [{full_label}]: session_id_ref '{session_ref}' not found")
                failed += 1
                continue

        # Resolve gate_action (special handling for human_gate_decide)
        gate_action = test_input.pop("gate_action", None)

        try:
            result = _execute_test(instance, method_name, test_input, gate_action, store)

            if result is not None:
                store.store(test_id, result)

            deviations: list[str] = []
            got_error = False

            # Check expected error - should have thrown
            if expected_error is not None:
                deviations.append(
                    f"  expected error containing '{expected_error}' but got result: {result!r}"
                )

            # Check expected dict subset (skip empty dict)
            has_other_assertions = any(x is not None for x in [
                expected_type, expected_length, expected_min_length,
                expected_max_length, expected_has, expected_contains,
                expected_first, expected_tally,
            ])
            if (expected is not None and isinstance(expected, dict)
                    and len(expected) > 0 and isinstance(result, dict)):
                devs = _deep_match(result, expected)
                deviations.extend(devs)

            # Check expected is None (only when no other assertion fields present)
            if expected is None and result is not None and not has_other_assertions:
                deviations.append(f"  expected None, got {type(result).__name__}")

            # Check expected_type
            if expected_type is not None:
                type_map = {
                    "list": list, "dict": dict, "tuple": tuple,
                    "str": str, "int": int, "bool": bool, "float": float,
                }
                expected_python_type = type_map.get(expected_type)
                if expected_python_type and not isinstance(result, expected_python_type):
                    deviations.append(
                        f"  expected type {expected_type}, got {type(result).__name__}"
                    )

            # Check expected_length
            if expected_length is not None:
                if hasattr(result, "__len__") and len(result) != expected_length:
                    deviations.append(
                        f"  expected length {expected_length}, got {len(result)}"
                    )

            # Check expected_min_length
            if expected_min_length is not None:
                if hasattr(result, "__len__") and len(result) < expected_min_length:
                    deviations.append(
                        f"  expected min length {expected_min_length}, got {len(result)}"
                    )

            # Check expected_max_length
            if expected_max_length is not None:
                if hasattr(result, "__len__") and len(result) > expected_max_length:
                    deviations.append(
                        f"  expected max length {expected_max_length}, got {len(result)}"
                    )

            # Check expected_has (keys present in dict)
            if expected_has is not None and isinstance(result, dict):
                for key in expected_has:
                    if key not in result:
                        deviations.append(f"  expected key '{key}' not found in result")

            # Check expected_contains (list item contains dict subset)
            if expected_contains is not None and isinstance(result, list):
                if not _list_contains_subset(result, expected_contains):
                    deviations.append(
                        f"  no list item contains expected subset: {expected_contains}"
                    )

            # Check expected_first (for tuples)
            if expected_first is not None:
                if isinstance(result, tuple) and len(result) >= 1:
                    if result[0] != expected_first:
                        deviations.append(
                            f"  expected first element {expected_first!r}, got {result[0]!r}"
                        )
                else:
                    deviations.append(
                        f"  expected tuple with first element, got {type(result).__name__}"
                    )

            # Check expected_tally (within cast_vote result)
            if expected_tally is not None and isinstance(result, dict):
                tally_data = result.get("tally", {})
                if tally_data:
                    tally_devs = _deep_match(tally_data, expected_tally)
                    deviations.extend(tally_devs)
                else:
                    deviations.append("  expected tally in result but none found")

            if deviations:
                details.append(f"  FAIL [{full_label}]:")
                for d in deviations:
                    details.append(f"    {d}")
                failed += 1
            else:
                details.append(f"  PASS [{full_label}]")
                passed += 1

        except Exception as exc:
            store.store(test_id, {"_error": str(exc)})

            if expected_error is not None:
                if expected_error.lower() in str(exc).lower():
                    details.append(f"  PASS [{full_label}] (expected error: {exc})")
                    passed += 1
                else:
                    details.append(
                        f"  FAIL [{full_label}]: error '{exc}' does not contain '{expected_error}'"
                    )
                    failed += 1
            else:
                details.append(f"  FAIL [{full_label}]: execution error: {exc}")
                failed += 1

    return passed, failed, details


def _execute_test(instance: Any, method_name: str, input_kwargs: dict,
                  gate_action: str | None, store: ResultStore) -> Any:
    """Execute a single test method on the instance."""
    method = getattr(instance, method_name, None)
    if method is None:
        raise AttributeError(f"Method '{method_name}' not found on {type(instance).__name__}")

    # Special handling for ModuleRegistry methods
    if type(instance).__name__ == "ModuleRegistry":
        return _execute_module_registry(instance, method_name, input_kwargs)

    # Special handling for ContractRegistry methods
    if type(instance).__name__ == "ContractRegistry":
        return _execute_contract_registry(instance, method_name, input_kwargs)

    # Special handling for EvidenceSpine methods
    if type(instance).__name__ == "EvidenceSpine":
        return _execute_evidence_spine(instance, method_name, input_kwargs)

    # Special handling for CouncilWorkflow methods
    if type(instance).__name__ == "CouncilWorkflow":
        return _execute_council_workflow(instance, method_name, input_kwargs, gate_action, store)

    # Generic fallback: try to call with kwargs
    return method(**input_kwargs)


def _execute_module_registry(registry, method_name: str, kwargs: dict) -> Any:
    """Execute ModuleRegistry methods with proper dataclass construction."""
    from sylion.core.module_registry import ModuleManifest, ModuleLifecycleStage, ModuleKind

    if method_name == "register":
        # Coerce module_kind string to enum
        if "module_kind" in kwargs and isinstance(kwargs["module_kind"], str):
            kwargs["module_kind"] = ModuleKind(kwargs["module_kind"])
        # Coerce security_profile string to enum
        from sylion.core.module_registry import SecurityProfile
        if "security_profile" in kwargs and isinstance(kwargs["security_profile"], str):
            kwargs["security_profile"] = SecurityProfile(kwargs["security_profile"])
        manifest = ModuleManifest(**kwargs)
        return registry.register(manifest)
    elif method_name == "get":
        return registry.get(kwargs["module_id"])
    elif method_name == "list_modules":
        return registry.list_modules(
            kind=kwargs.get("kind"),
            milestone=kwargs.get("milestone"),
            lifecycle=kwargs.get("lifecycle"),
        )
    elif method_name == "transition":
        target = ModuleLifecycleStage(kwargs["target"])
        return registry.transition(kwargs["module_id"], target)
    elif method_name == "deregister":
        return registry.deregister(kwargs["module_id"])
    elif method_name == "heartbeat":
        registry.heartbeat(kwargs["module_id"])
        return {"heartbeat": True, "module_id": kwargs["module_id"]}
    else:
        return getattr(registry, method_name)(**kwargs)


def _execute_contract_registry(registry, method_name: str, kwargs: dict) -> Any:
    """Execute ContractRegistry methods with proper dataclass construction."""
    from sylion.core.contract_registry import Contract, ContractType

    if method_name == "publish":
        ct = ContractType(kwargs.get("contract_type", "grpc_service"))
        contract = Contract(
            name=kwargs["name"],
            contract_type=ct,
            version=kwargs.get("version", "1.0.0"),
            schema_def=kwargs.get("schema_def", ""),
            producer_module=kwargs.get("producer_module", ""),
            consumer_modules=kwargs.get("consumer_modules", []),
            description=kwargs.get("description", ""),
        )
        return registry.publish(contract)
    elif method_name == "get":
        return registry.get(kwargs["name"], version=kwargs.get("version"))
    elif method_name == "check_compatibility":
        return registry.check_compatibility(kwargs["name"], kwargs["new_version"])
    elif method_name == "list_versions":
        return registry.list_versions(kwargs["name"])
    elif method_name == "list_all":
        return registry.list_all(contract_type=kwargs.get("contract_type"))
    else:
        return getattr(registry, method_name)(**kwargs)


def _execute_evidence_spine(spine, method_name: str, kwargs: dict) -> Any:
    """Execute EvidenceSpine methods with proper dataclass construction."""
    from sylion.core.evidence_spine import EvidenceEntry

    if method_name == "append":
        entry = EvidenceEntry(
            source_plan=kwargs.get("source_plan", ""),
            event_type=kwargs.get("event_type", ""),
            payload=kwargs.get("payload", {}),
            actor_id=kwargs.get("actor_id", ""),
        )
        return spine.append(entry)
    elif method_name == "query":
        return spine.query(
            source_plan=kwargs.get("source_plan"),
            event_type=kwargs.get("event_type"),
            since=kwargs.get("since"),
            limit=kwargs.get("limit", 100),
        )
    elif method_name == "verify_chain":
        return spine.verify_chain()
    elif method_name == "replay":
        return spine.replay(since=kwargs.get("since"))
    else:
        return getattr(spine, method_name)(**kwargs)


def _execute_council_workflow(council, method_name: str, kwargs: dict,
                              gate_action: str | None, store: ResultStore) -> Any:
    """Execute CouncilWorkflow methods with proper dataclass construction."""
    from sylion.governance.council_workflow import (
        CouncilSession, Vote, VoteValue, SessionStatus,
    )
    from sylion.core.decision_gate_engine import DecisionClass

    if method_name == "open_session":
        dc_val = kwargs.get("decision_class", "D3")
        dc = DecisionClass(dc_val)
        session = CouncilSession(
            proposal_id=kwargs.get("proposal_id", ""),
            decision_class=dc,
            title=kwargs.get("title", ""),
            description=kwargs.get("description", ""),
            evidence_ref=kwargs.get("evidence_ref", ""),
        )
        return council.open_session(session)

    elif method_name == "cast_vote":
        session_id = kwargs.get("session_id", "")
        vv = VoteValue(kwargs.get("value", "abstain"))
        vote = Vote(
            session_id=session_id,
            member_id=kwargs.get("member_id", ""),
            value=vv,
            rationale=kwargs.get("rationale", ""),
        )
        return council.cast_vote(vote)

    elif method_name == "tally":
        session_id = kwargs.get("session_id", "")
        return council.tally(session_id)

    elif method_name == "get_session":
        session_id = kwargs.get("session_id", "")
        return council.get_session(session_id)

    elif method_name == "list_sessions":
        return council.list_sessions(status=kwargs.get("status"))

    elif method_name == "human_gate_decide":
        session_id = kwargs.get("session_id", "")
        decision = kwargs.get("decision", "approved")
        by = kwargs.get("by", "")

        # If gate_action says to first approve all votes, do that
        if gate_action == "first_approve_all_votes":
            # Cast 4 approve votes to reach quorum
            for i in range(1, 5):
                vote = Vote(
                    session_id=session_id,
                    member_id=f"gate_voter_{i}",
                    value=VoteValue.APPROVE,
                    rationale=f"Auto-approve for gate test {i}",
                )
                council.cast_vote(vote)

        return council.human_gate_decide(session_id, decision, by)

    else:
        return getattr(council, method_name)(**kwargs)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("SYLION AEIS - Expanded Golden Set Validator")
    print("=" * 72)

    total_pass = 0
    total_fail = 0

    if not GOLDEN_SETS_DIR.exists():
        print(f"\nERROR: Golden sets directory not found: {GOLDEN_SETS_DIR}")
        return 1

    golden_files = sorted(GOLDEN_SETS_DIR.glob("*.json"))
    if not golden_files:
        print(f"\nWARNING: No golden set files found in {GOLDEN_SETS_DIR}")
        return 0

    print(f"\nFound {len(golden_files)} golden set file(s):")
    for gf in golden_files:
        print(f"  - {gf.name}")

    for gf in golden_files:
        print(f"\n--- {gf.name} ---")
        p, f, details = run_golden_set(gf)
        total_pass += p
        total_fail += f
        for d in details:
            try:
                print(d)
            except UnicodeEncodeError:
                # Windows console may not handle Unicode arrows etc.
                print(d.encode("ascii", "replace").decode("ascii"))

    # Summary
    print("\n" + "=" * 72)
    print(f"GOLDEN SET RESULTS: {total_pass} passed, {total_fail} failed")

    if total_fail > 0:
        print("One or more golden set tests FAILED.")
        print("=" * 72)
        return 1
    else:
        print("All golden set tests passed.")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(main())
