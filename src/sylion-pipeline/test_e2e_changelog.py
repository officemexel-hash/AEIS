#!/usr/bin/env python3
"""
End-to-end test: CHANGELOG-v3.4.13 hallucination scenario.

Simulates the full pipeline flow:
  1. HallucinationGuard.before_iteration() snapshots handler.go
  2. Agent "runs" but does NOT modify the file
  3. Agent claims: "Fixed err.Error() in handler.go" (CHANGELOG-v3.4.13)
  4. HallucinationGuard.after_iteration() verifies → HALLUCINATION detected
  5. LoopGuard records action="hallucination"
  6. Human Gate receives GateLevel.CRITICAL escalation

Run:
  cd sylion-pipeline
  python test_e2e_changelog.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Add current dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from file_verification import (
    AgentClaim,
    ClaimAction,
    FileVerificationLayer,
    HallucinationType,
    Verdict,
)
from file_verification import HallucinationGuard


# ---------------------------------------------------------------------------
# Mock LoopGuard and HumanGate for testing
# ---------------------------------------------------------------------------

class MockLoopGuard:
    """Captures record_iteration calls."""
    def __init__(self):
        self.records = []

    def record_iteration(self, agent_id, file_path, action, **kw):
        self.records.append({
            "agent_id": agent_id,
            "file_path": file_path,
            "action": action,
            **kw,
        })


class MockHumanGate:
    """Captures request_approval calls."""
    def __init__(self):
        self.requests = []

    def request_approval(self, request):
        self.requests.append(request)


# ---------------------------------------------------------------------------
# E2E Test
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("E2E TEST: CHANGELOG-v3.4.13 Hallucination Scenario")
    print("=" * 70)

    # Setup
    tmp = tempfile.mkdtemp(prefix="sylion_e2e_")
    repo = Path(tmp)
    (repo / "internal" / "handler").mkdir(parents=True)

    handler_content = (
        'package handler\n\n'
        'import (\n'
        '    "fmt"\n'
        '    "net/http"\n'
        ')\n\n'
        'func Handle(w http.ResponseWriter, r *http.Request) {\n'
        '    err := doSomething()\n'
        '    if err != nil {\n'
        '        fmt.Fprintf(w, "error: %s", err.Error())\n'
        '        return\n'
        '    }\n'
        '    fmt.Fprintf(w, "OK")\n'
        '}\n\n'
        'func doSomething() error {\n'
        '    return nil\n'
        '}\n'
    )
    (repo / "internal" / "handler" / "handler.go").write_text(
        handler_content, encoding="utf-8"
    )

    # Initialize components
    file_layer = FileVerificationLayer(
        repo_root=repo,
        fail_closed=True,
        log_dir=repo / ".logs",
    )
    mock_loop_guard = MockLoopGuard()
    mock_human_gate = MockHumanGate()

    guard = HallucinationGuard(
        file_layer=file_layer,
        loop_guard=mock_loop_guard,
        human_gate=mock_human_gate,
        audit_log_path=repo / ".logs" / "hallucinations.jsonl",
        auto_escalate=True,
    )

    # --- STEP 1: Before iteration ---
    print("\n[STEP 1] before_iteration — snapshotting handler.go")
    ctx = guard.before_iteration(
        agent_id="programmer_go_1",
        declared_files=["internal/handler/handler.go"],
    )
    sha_before = ctx.snapshots["internal/handler/handler.go"].sha256
    print(f"  SHA-256 before: {sha_before[:32]}...")

    # --- STEP 2: Agent "runs" but does NOTHING ---
    print("\n[STEP 2] Agent runs — but does NOT modify handler.go")
    print("  (Simulating hallucination: agent thinks it fixed err.Error())")

    # --- STEP 3: Agent produces claims ---
    print("\n[STEP 3] Agent claims: FIXED handler.go (CHANGELOG-v3.4.13)")
    claims = [AgentClaim(
        file_path="internal/handler/handler.go",
        action=ClaimAction.FIXED,
        description=(
            "Fixed err.Error() handling in Handle() — replaced with "
            "fmt.Errorf for better error context. Addresses finding "
            "F-SEC-042 from security audit (CHANGELOG-v3.4.13 fix)."
        ),
        finding_id="F-SEC-042",
        agent_id="programmer_go_1",
    )]

    # --- STEP 4: After iteration — verify ---
    print("\n[STEP 4] after_iteration — verifying claims vs reality")
    result = guard.after_iteration(
        agent_id="programmer_go_1",
        claims=claims,
        ctx=ctx,
    )

    # --- STEP 5: Check results ---
    sha_after = file_layer.snapshot_file("internal/handler/handler.go").sha256
    print(f"\n  SHA-256 after:  {sha_after[:32]}...")
    print(f"  SHA match: {sha_before == sha_after} (should be True — no change)")
    print(f"\n  Verdict: {result.verdict.value}")
    print(f"  Hallucinations: {result.hallucination_count}")
    print(f"  Blocked: {result.blocked}")

    if result.hallucinations:
        h = result.hallucinations[0]
        print(f"\n  Hallucination type: {h.hallucination_type.value}")
        print(f"  File: {h.file_path}")
        print(f"  Description: {h.description}")
        print(f"  SHA before == SHA after: {h.sha_before == h.sha_after}")

    # --- STEP 6: Check LoopGuard recorded hallucination ---
    print(f"\n[STEP 5] LoopGuard records: {len(mock_loop_guard.records)}")
    if mock_loop_guard.records:
        r = mock_loop_guard.records[0]
        print(f"  action: {r['action']} (should be 'hallucination')")

    # --- STEP 7: Check Human Gate escalation ---
    print(f"\n[STEP 6] Human Gate escalations: {len(mock_human_gate.requests)}")
    if mock_human_gate.requests:
        req = mock_human_gate.requests[0]
        print(f"  level: {req.level.value} (should be 'critical')")
        print(f"  title: {req.title}")

    # --- STEP 8: Check audit log ---
    log_path = repo / ".logs" / "hallucinations.jsonl"
    if log_path.exists():
        import json
        with open(log_path) as f:
            entry = json.loads(f.readline())
        print(f"\n[STEP 7] Audit log entry written: verdict={entry['verdict']}")

    # --- Assertions ---
    print("\n" + "=" * 70)
    print("ASSERTIONS")
    print("=" * 70)

    all_pass = True

    def check(name, condition):
        nonlocal all_pass
        status = "PASS" if condition else "FAIL"
        if not condition:
            all_pass = False
        print(f"  [{status}] {name}")

    check("SHA before == SHA after (file unchanged)",
          sha_before == sha_after)
    check("Verdict is HALLUCINATION",
          result.verdict == Verdict.HALLUCINATION)
    check("Exactly 1 hallucination detected",
          result.hallucination_count == 1)
    check("Type is NO_ACTUAL_CHANGE",
          result.hallucinations[0].hallucination_type == HallucinationType.NO_ACTUAL_CHANGE)
    check("Agent is blocked",
          result.blocked is True)
    check("LoopGuard recorded action='hallucination'",
          mock_loop_guard.records[0]["action"] == "hallucination")
    check("Human Gate received CRITICAL escalation",
          len(mock_human_gate.requests) == 1
          and mock_human_gate.requests[0].level.value == "critical")
    check("Audit log written",
          log_path.exists())

    # Cleanup
    shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 70)
    if all_pass:
        print("RESULT: ALL 8 ASSERTIONS PASSED")
        print("CHANGELOG-v3.4.13 hallucination correctly detected and blocked.")
    else:
        print("RESULT: SOME ASSERTIONS FAILED")
    print("=" * 70)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
