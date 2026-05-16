"""End-to-end Phase 4 lifecycle probe via TestClient.

Walks: create -> clarify -> council -> request-approval (Human Gate)
       -> approve -> implement (terminal positive path)
And: create -> archive -> unarchive -> abandon
And: create -> soft-delete -> restore -> hard-delete
And: detect-stale (with sub-second threshold to force trigger)
And: history endpoint
And: route inventory diff (idea routes before/after).
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

# Reset singletons so we get a clean DB
from sylion.cognitive.idea_vault import reset_idea_vault  # noqa: E402
from sylion.governance.human_gate import reset_human_gate  # noqa: E402
reset_idea_vault()
reset_human_gate()

from sylion.api.app import app  # noqa: E402

client = TestClient(app)
results: dict[str, object] = {"phase": "P4-IDEA", "checks": []}

def step(name: str, ok: bool, **payload):
    results["checks"].append({"name": name, "ok": ok, **payload})
    print(f"{'OK ' if ok else 'FAIL'}  {name}")
    if not ok:
        print(json.dumps(payload, indent=2, default=str))

# ---------------------------------------------------------------------
# Route inventory: count idea routes before any traffic
# ---------------------------------------------------------------------
idea_routes = sorted({r.path for r in app.routes if "/ideas" in r.path})
results["idea_route_count"] = len(idea_routes)
results["idea_routes"] = idea_routes

# ---------------------------------------------------------------------
# Path 1: full positive flow
# ---------------------------------------------------------------------
r = client.post("/api/v1/ideas", json={
    "title": "Smart cache invalidation",
    "description": "When upstream changes, invalidate cache",
    "author": "alice",
    "tags": ["cache", "perf"],
})
step("create idea", r.status_code == 201,
     status=r.status_code, body=r.json() if r.status_code < 500 else r.text)
idea = r.json()
iid = idea["idea_id"]
assert idea["status"] == "draft"

r = client.post(f"/api/v1/ideas/{iid}/clarify", json={
    "notes": "What's the TTL policy?", "actor": "alice"})
step("clarify", r.status_code == 200 and r.json()["status"] == "clarification",
     status=r.status_code, current=r.json().get("status"))

r = client.post(f"/api/v1/ideas/{iid}/submit-council",
                json={"actor": "alice"})
step("submit-council",
     r.status_code == 200 and r.json()["status"] == "council_review",
     status=r.status_code, current=r.json().get("status"))

r = client.post(f"/api/v1/ideas/{iid}/request-approval",
                json={"requested_by": "alice", "priority": "high"})
step("request-approval",
     r.status_code == 200 and r.json()["status"] == "awaiting_approval",
     status=r.status_code, current=r.json().get("status"),
     gate_id=r.json().get("human_gate_request_id"))
gate_request_id = r.json().get("human_gate_request_id")

# Confirm Human Gate request actually exists
r2 = client.get(f"/api/v1/gates/human/requests/{gate_request_id}")
step("human-gate request exists",
     r2.status_code == 200 and r2.json().get("status") == "pending",
     status=r2.status_code,
     hg_status=r2.json().get("status") if r2.status_code == 200 else None)

r = client.post(f"/api/v1/ideas/{iid}/approve",
                json={"approver": "bob", "rationale": "looks good"})
step("approve",
     r.status_code == 200 and r.json()["status"] == "accepted",
     status=r.status_code, current=r.json().get("status"))

r = client.post(f"/api/v1/ideas/{iid}/implement",
                json={"actor": "alice"})
step("implement (terminal)",
     r.status_code == 200 and r.json()["status"] == "implemented",
     status=r.status_code, current=r.json().get("status"))

r = client.get(f"/api/v1/ideas/{iid}/history")
step("history (>= 6 transitions)",
     r.status_code == 200 and len(r.json()["history"]) >= 6,
     status=r.status_code, count=len(r.json().get("history", [])))

# ---------------------------------------------------------------------
# Path 2: archive + unarchive + abandon
# ---------------------------------------------------------------------
r = client.post("/api/v1/ideas", json={"title": "Archive test", "author": "x"})
iid2 = r.json()["idea_id"]

r = client.post(f"/api/v1/ideas/{iid2}/archive",
                json={"actor": "ops", "reason": "noisy"})
step("archive", r.status_code == 200 and r.json()["status"] == "archived",
     status=r.status_code, current=r.json().get("status"),
     archived_at=r.json().get("archived_at"))

# Verify archived ideas are HIDDEN by default in list
r = client.get("/api/v1/ideas")
shown = [i for i in r.json() if i["idea_id"] == iid2]
step("archived hidden by default", len(shown) == 0,
     status=r.status_code, found=len(shown))

# Verify archived included when include_archived=true
r = client.get("/api/v1/ideas?include_archived=true")
shown = [i for i in r.json() if i["idea_id"] == iid2]
step("archived visible with include_archived=true", len(shown) == 1,
     status=r.status_code, found=len(shown))

r = client.post(f"/api/v1/ideas/{iid2}/unarchive", json={"actor": "ops"})
step("unarchive returns to draft",
     r.status_code == 200 and r.json()["status"] == "draft",
     status=r.status_code, current=r.json().get("status"))

r = client.post(f"/api/v1/ideas/{iid2}/abandon",
                json={"reason": "no traction", "actor": "x"})
step("abandon",
     r.status_code == 200 and r.json()["status"] == "abandoned",
     status=r.status_code, current=r.json().get("status"),
     abandoned_at=r.json().get("abandoned_at"))

# ---------------------------------------------------------------------
# Path 3: soft delete + restore + hard delete
# ---------------------------------------------------------------------
r = client.post("/api/v1/ideas", json={"title": "Delete test", "author": "x"})
iid3 = r.json()["idea_id"]

r = client.post(f"/api/v1/ideas/{iid3}/soft-delete",
                json={"reason": "duplicate", "actor": "x"})
step("soft-delete",
     r.status_code == 200 and r.json()["status"] == "deleted_soft",
     status=r.status_code, current=r.json().get("status"),
     deleted_at=r.json().get("deleted_at"))

r = client.get("/api/v1/ideas")
shown = [i for i in r.json() if i["idea_id"] == iid3]
step("soft-deleted hidden by default", len(shown) == 0,
     status=r.status_code, found=len(shown))

r = client.get("/api/v1/ideas?include_deleted=true")
shown = [i for i in r.json() if i["idea_id"] == iid3]
step("soft-deleted visible with include_deleted=true",
     len(shown) == 1, status=r.status_code, found=len(shown))

r = client.post(f"/api/v1/ideas/{iid3}/restore", json={"actor": "x"})
step("restore from soft-delete",
     r.status_code == 200 and r.json()["status"] == "draft",
     status=r.status_code, current=r.json().get("status"))

# Hard delete via existing DELETE
r = client.delete(f"/api/v1/ideas/{iid3}")
step("hard delete", r.status_code == 200 and r.json().get("deleted") is True,
     status=r.status_code, body=r.json())

r = client.get(f"/api/v1/ideas/{iid3}")
step("hard-deleted returns 404", r.status_code == 404,
     status=r.status_code)

# ---------------------------------------------------------------------
# Path 4: stale detection
# ---------------------------------------------------------------------
r = client.post("/api/v1/ideas", json={"title": "Stale test", "author": "x"})
iid4 = r.json()["idea_id"]

# Force last_activity_at to past via direct vault access
from sylion.cognitive.idea_vault import get_idea_vault
v = get_idea_vault()
past = time.time() - (60 * 86400)  # 60 days ago
v._conn.execute(
    "UPDATE ideas SET last_activity_at = ?, updated_at = ? WHERE idea_id = ?",
    (past, past, iid4),
)
v._conn.commit()

r = client.post("/api/v1/ideas/maintenance/detect-stale",
                json={"threshold_days": 30, "dry_run": False})
step("detect-stale finds aged idea",
     r.status_code == 200 and any(i["idea_id"] == iid4 for i in r.json()["ideas"]),
     status=r.status_code, count=r.json().get("count"))

r = client.get(f"/api/v1/ideas/{iid4}")
step("stale idea has status=stale",
     r.status_code == 200 and r.json()["status"] == "stale",
     status=r.status_code, current=r.json().get("status"))

# ---------------------------------------------------------------------
# Path 5: 404 on unknown ids for every lifecycle endpoint
# ---------------------------------------------------------------------
fake = "deadbeefdeadbeefdeadbeefdeadbeef"
for path, body in [
    (f"/api/v1/ideas/{fake}/clarify", {"notes": "q", "actor": "z"}),
    (f"/api/v1/ideas/{fake}/submit-council", {"actor": "z"}),
    (f"/api/v1/ideas/{fake}/approve", {"approver": "z", "rationale": ""}),
    (f"/api/v1/ideas/{fake}/reject", {"approver": "z", "rationale": ""}),
    (f"/api/v1/ideas/{fake}/abandon", {"reason": "", "actor": "z"}),
    (f"/api/v1/ideas/{fake}/archive", {"reason": "", "actor": "z"}),
    (f"/api/v1/ideas/{fake}/unarchive", {"actor": "z"}),
    (f"/api/v1/ideas/{fake}/soft-delete", {"reason": "", "actor": "z"}),
    (f"/api/v1/ideas/{fake}/restore", {"actor": "z"}),
    (f"/api/v1/ideas/{fake}/implement", {"actor": "z"}),
]:
    rr = client.post(path, json=body)
    step(f"404 {path[len('/api/v1/ideas/'+fake):]}",
         rr.status_code == 404, status=rr.status_code,
         body=rr.json() if rr.status_code < 500 else rr.text)

# ---------------------------------------------------------------------
# Path 6: maintenance/detect-stale must NOT be shadowed by /{idea_id}
# ---------------------------------------------------------------------
r = client.get("/api/v1/ideas/maintenance")
# This should hit GET /{idea_id} -> 404 (no idea named "maintenance")
step("get /ideas/maintenance returns 404 (not 200 on a real idea)",
     r.status_code == 404, status=r.status_code)

# ---------------------------------------------------------------------
# Final stats summary
# ---------------------------------------------------------------------
r = client.get("/api/v1/ideas/stats")
results["final_stats"] = r.json()
step("stats endpoint", r.status_code == 200, status=r.status_code)

# Record summary
ok_count = sum(1 for c in results["checks"] if c["ok"])
total = len(results["checks"])
results["summary"] = {"ok": ok_count, "total": total,
                      "pass": ok_count == total}

OUT = ROOT.parent.parent / ".audit_500" / "PHASE4_IDEA_results.json"
OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\n{ok_count}/{total} checks pass — wrote {OUT}")
sys.exit(0 if ok_count == total else 1)
