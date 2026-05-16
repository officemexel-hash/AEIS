"""Phase 5 COUNCIL e2e: roles, ranks, weights, critic signature, sentinels.

End-to-end verification of the canonical 9-role / 5-rank council with
weighted voting, mandatory critic signature, and cost+security sentinel
gates -- all driven through the public HTTP surface (FastAPI TestClient).

Output: .audit_500/PHASE5_COUNCIL_e2e.json with all 30+ checks.
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

t0 = time.monotonic()
from sylion.api.app import app  # noqa: E402
boot_seconds = round(time.monotonic() - t0, 2)

# Reset council singleton so a clean DB
from sylion.governance.council_hybrid import reset_council_hybrid  # noqa: E402
reset_council_hybrid()

client = TestClient(app)

results: list[dict] = []
def step(label: str, ok: bool, detail: str = "", data: object = None):
    results.append({
        "check": label,
        "ok": bool(ok),
        "detail": detail,
        "data": data,
    })
    marker = "[ok]" if ok else "[FAIL]"
    print(f"{marker} {label}: {detail}")


# ----------------------------------------------------------------------
# 1. Roles index endpoint
# ----------------------------------------------------------------------
r = client.get("/api/v1/workspace/council/roles")
roles = r.json() if r.status_code == 200 else {}
step("roles index 200", r.status_code == 200, str(r.status_code))
step("9 canonical roles",
     len(roles.get("roles", [])) == 9,
     f"got {len(roles.get('roles', []))}")
step("5 canonical ranks",
     len(roles.get("ranks", [])) == 5,
     f"got {len(roles.get('ranks', []))}")
step("critic role present",
     "critic" in roles.get("roles", []),
     str("critic" in roles.get("roles", [])))
step("cost_sentinel role present",
     "cost_sentinel" in roles.get("roles", []),
     "ok")
step("security_sentinel role present",
     "security_sentinel" in roles.get("roles", []),
     "ok")
step("default weight for critic == 1.0",
     roles.get("default_role_weights", {}).get("critic") == 1.0,
     str(roles.get("default_role_weights", {}).get("critic")))
step("rank multiplier validation_only < primary",
     roles.get("rank_multiplier", {}).get("validation_only", 1.0) <
     roles.get("rank_multiplier", {}).get("primary", 0.0),
     "ok")


# ----------------------------------------------------------------------
# 2. Open a session
# ----------------------------------------------------------------------
r = client.post("/api/v1/workspace/council/sessions",
                json={"topic": "Approve $200k spend",
                      "description": "Phase 5 e2e",
                      "model_ids": ["gpt-4o", "claude-opus", "gemini-pro",
                                    "grok-mini", "qwen-coder"]})
ok = r.status_code in (200, 201)
sess = r.json() if ok else {}
sid = sess.get("session_id", "")
step("open session", ok and bool(sid), f"sid={sid[:12]}")


# ----------------------------------------------------------------------
# 3. Add 5 participants in 3 roles + 2 sentinels
# ----------------------------------------------------------------------
plan = [
    ("gpt-4o",      "planner",           "primary"),
    ("claude-opus", "architect",         "primary"),
    ("gemini-pro",  "critic",            "primary"),
    ("grok-mini",   "cost_sentinel",     "support"),
    ("qwen-coder",  "security_sentinel", "support"),
]
for mid, role, rank in plan:
    r = client.post(f"/api/v1/workspace/council/sessions/{sid}/participants",
                    json={"model_id": mid, "role": role, "rank": rank})
    ok = r.status_code == 200
    step(f"add participant {mid}/{role}/{rank}", ok,
         f"{r.status_code} weight={r.json().get('weight') if ok else '-'}")

# Reject invalid role
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/participants",
                json={"model_id": "noop", "role": "INVALID_ROLE",
                      "rank": "primary"})
step("reject invalid role", r.status_code == 400, str(r.status_code))

# Reject invalid rank
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/participants",
                json={"model_id": "noop2", "role": "planner",
                      "rank": "INVALID_RANK"})
step("reject invalid rank", r.status_code == 400, str(r.status_code))

# Reject duplicate
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/participants",
                json={"model_id": "gpt-4o", "role": "planner",
                      "rank": "primary"})
step("reject duplicate participant", r.status_code == 400, str(r.status_code))


# ----------------------------------------------------------------------
# 4. List participants + filter
# ----------------------------------------------------------------------
r = client.get(f"/api/v1/workspace/council/sessions/{sid}/participants")
parts = r.json().get("participants", []) if r.status_code == 200 else []
step("list 5 participants", len(parts) == 5, f"got {len(parts)}")

r = client.get(f"/api/v1/workspace/council/sessions/{sid}/participants?role=critic")
crits = r.json().get("participants", []) if r.status_code == 200 else []
step("filter participants by role=critic",
     len(crits) == 1 and crits[0]["model_id"] == "gemini-pro",
     f"got {len(crits)}")


# ----------------------------------------------------------------------
# 5. Add analyses (verdict mix to test weighted voting)
# ----------------------------------------------------------------------
# 3 approve (planner+architect+critic) vs 2 reject (sentinels)
from sylion.governance.council_hybrid import get_council_hybrid
council = get_council_hybrid()
council.add_analysis(sid, "gpt-4o",      "approve plan",      "approve",
                     0.9, "looks ok")
council.add_analysis(sid, "claude-opus", "approve arch",      "approve",
                     0.85, "design is sound")
council.add_analysis(sid, "gemini-pro",  "approve with caveats", "approve",
                     0.75, "tight schedule")
council.add_analysis(sid, "grok-mini",   "reject -- $$$",     "reject",
                     0.95, "blows budget")
council.add_analysis(sid, "qwen-coder",  "reject -- security", "reject",
                     0.95, "PII leak risk")

# Compute consensus -- weights so far (no sentinel evals yet):
# approve = w(planner.primary) + w(architect.primary) + w(critic.primary)
#         = 1.0 + 1.0 + 1.0 = 3.0
# reject  = w(cost_sentinel.support) + w(security_sentinel.support)
#         = 0.5 * 0.7 + 0.5 * 0.7 = 0.35 + 0.35 = 0.7
r = client.get(f"/api/v1/workspace/council/sessions/{sid}/consensus")
cs = r.json() if r.status_code == 200 else {}
step("consensus 200", r.status_code == 200, str(r.status_code))
step("verdict approves on weighted vote",
     cs.get("verdict") == "approve",
     f"verdict={cs.get('verdict')}")
step("approve weight ~3.0",
     2.9 <= cs.get("weights", {}).get("approve", 0) <= 3.1,
     f"approve_w={cs.get('weights', {}).get('approve')}")
step("reject weight ~0.7",
     0.65 <= cs.get("weights", {}).get("reject", 0) <= 0.75,
     f"reject_w={cs.get('weights', {}).get('reject')}")
step("critic_signed=False before signature",
     cs.get("critic_signed") is False,
     str(cs.get("critic_signed")))
step("no sentinel_blocks before evaluations",
     cs.get("sentinel_blocks") == [],
     str(cs.get("sentinel_blocks")))


# ----------------------------------------------------------------------
# 6. Critic signature flow
# ----------------------------------------------------------------------
# Try non-critic signing -> 400
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/critic/sign",
                json={"model_id": "gpt-4o", "signed_decision": "approve",
                      "rationale": "fake"})
step("non-critic cannot sign", r.status_code == 400, str(r.status_code))

# Invalid decision -> 400
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/critic/sign",
                json={"model_id": "gemini-pro",
                      "signed_decision": "BANANAS"})
step("invalid decision rejected", r.status_code == 400, str(r.status_code))

# Real critic signs
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/critic/sign",
                json={"model_id": "gemini-pro",
                      "signed_decision": "approve",
                      "rationale": "approved with caveats"})
ok = r.status_code == 200 and r.json().get("signature_hash")
step("critic signature accepted", ok,
     f"{r.status_code} hash={r.json().get('signature_hash', '')[:8]}")

# Verify list
r = client.get(f"/api/v1/workspace/council/sessions/{sid}/critic/signatures")
sigs_payload = r.json() if r.status_code == 200 else {}
step("critic signatures listed",
     len(sigs_payload.get("signatures", [])) == 1
     and sigs_payload.get("signed") is True,
     f"count={len(sigs_payload.get('signatures', []))}")


# ----------------------------------------------------------------------
# 7. Sentinel evaluations
# ----------------------------------------------------------------------
# Cost sentinel rejects
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/sentinels/evaluate",
                json={"sentinel_role": "cost_sentinel",
                      "model_id": "grok-mini",
                      "verdict": "reject",
                      "score": 0.92,
                      "details": "exceeds Q2 budget"})
step("cost_sentinel reject recorded", r.status_code == 200, str(r.status_code))

# Security sentinel approves
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/sentinels/evaluate",
                json={"sentinel_role": "security_sentinel",
                      "model_id": "qwen-coder",
                      "verdict": "approve",
                      "score": 0.4,
                      "details": "PII flag mitigated"})
step("security_sentinel approve recorded", r.status_code == 200, str(r.status_code))

# Invalid sentinel role
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/sentinels/evaluate",
                json={"sentinel_role": "FAKE_SENTINEL",
                      "model_id": "x",
                      "verdict": "reject"})
step("invalid sentinel role rejected", r.status_code == 400, str(r.status_code))

r = client.get(f"/api/v1/workspace/council/sessions/{sid}/sentinels")
step("sentinel list returns 2",
     len(r.json().get("evaluations", [])) == 2,
     f"got {len(r.json().get('evaluations', []))}")

r = client.get(f"/api/v1/workspace/council/sessions/{sid}/sentinels?sentinel_role=cost_sentinel")
step("filter sentinels by role=cost_sentinel",
     len(r.json().get("evaluations", [])) == 1,
     f"got {len(r.json().get('evaluations', []))}")


# ----------------------------------------------------------------------
# 8. Consolidate-gated -- cost_sentinel block must fail
# ----------------------------------------------------------------------
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/consolidate-gated",
                json={"consolidated_text": "Approved.",
                      "require_critic": True,
                      "require_sentinels_pass": True})
step("gated consolidation blocked by sentinel",
     r.status_code == 400 and "sentinel" in r.text.lower(),
     f"{r.status_code} {r.text[:80]}")

# Allow sentinel block, but still require critic -> should pass
r = client.post(f"/api/v1/workspace/council/sessions/{sid}/consolidate-gated",
                json={"consolidated_text": "Approved (override).",
                      "require_critic": True,
                      "require_sentinels_pass": False})
step("gated consolidation passes when sentinels override allowed",
     r.status_code == 200,
     f"{r.status_code}")
step("consensus_level computed",
     0 < r.json().get("consensus_level", -1) <= 1.0,
     f"level={r.json().get('consensus_level')}")


# ----------------------------------------------------------------------
# 9. Open second session, NO critic signature, gated must fail
# ----------------------------------------------------------------------
r = client.post("/api/v1/workspace/council/sessions",
                json={"topic": "Test critic gate",
                      "model_ids": ["m-a"]})
sid2 = r.json().get("session_id", "")
client.post(f"/api/v1/workspace/council/sessions/{sid2}/participants",
            json={"model_id": "m-a", "role": "planner", "rank": "primary"})
council.add_analysis(sid2, "m-a", "ok", "approve", 0.5, "ok")

r = client.post(f"/api/v1/workspace/council/sessions/{sid2}/consolidate-gated",
                json={"consolidated_text": "no critic",
                      "require_critic": True,
                      "require_sentinels_pass": True})
step("gated consolidation blocked when critic missing",
     r.status_code == 400 and "critic" in r.text.lower(),
     f"{r.status_code} {r.text[:80]}")


# ----------------------------------------------------------------------
# 10. 404 / 400 hygiene
# ----------------------------------------------------------------------
r = client.get("/api/v1/workspace/council/sessions/NONEXISTENT/consensus")
step("consensus on missing session -> 404",
     r.status_code == 404, str(r.status_code))

r = client.post("/api/v1/workspace/council/sessions/NONEXISTENT/participants",
                json={"model_id": "x", "role": "planner", "rank": "primary"})
step("add participant to missing session -> 400/404",
     r.status_code in (400, 404), str(r.status_code))

# Remove participant
r = client.get(f"/api/v1/workspace/council/sessions/{sid}/participants?role=planner")
plist = r.json().get("participants", [])
pid_to_remove = plist[0]["participant_id"] if plist else ""
r = client.delete(
    f"/api/v1/workspace/council/sessions/{sid}/participants/{pid_to_remove}"
)
step("remove participant 200", r.status_code == 200, str(r.status_code))

r = client.delete(
    f"/api/v1/workspace/council/sessions/{sid}/participants/{pid_to_remove}"
)
step("double-remove participant -> 404", r.status_code == 404, str(r.status_code))


# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------
total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed
out = {
    "phase": "P5-COUNCIL-E2E",
    "boot_seconds": boot_seconds,
    "total_checks": total,
    "passed": passed,
    "failed": failed,
    "session_id": sid,
    "results": results,
}
OUT = ROOT.parent.parent / ".audit_500" / "PHASE5_COUNCIL_e2e.json"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
print(f"\nWROTE {OUT}")
print(f"\n{passed}/{total} passed; {failed} failed")
sys.exit(0 if failed == 0 else 1)
