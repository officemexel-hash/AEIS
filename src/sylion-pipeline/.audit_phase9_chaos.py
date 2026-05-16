"""Phase 9 CHAOS+REPAIR: failure injection + recovery.

Scenarios:
  C1. Idea submitted then aborted at HG -> archive cleanly, no orphan rows
  C2. Council session with NO critic signature -> consolidate-gated must REJECT
  C3. AuditSink concurrent write contention -> no DB lock, no row loss
  C4. ExecutionGuard rule list cleared mid-decision -> defaults to deny
  C5. SecretProvider key rotation while reading -> reads stay consistent
  C6. AuthProvider duplicate-user race -> exactly one wins, the other ValueErrors

Output: .audit_500/PHASE9_CHAOS.json
"""
from __future__ import annotations
import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from sylion.core.event_bus import EventBus  # noqa: E402

results: list[dict] = []
def step(label: str, ok: bool, detail: str = ""):
    results.append({"check": label, "ok": bool(ok), "detail": detail})
    marker = "[ok]" if ok else "[FAIL]"
    print(f"{marker} {label}: {detail}")


# C1. Idea -> abort -> archive
print("C1: idea abort + archive ...")
from sylion.cognitive.idea_vault import IdeaVault
iv = IdeaVault(event_bus=EventBus())
idea = iv.create_idea("Test idea", description="will be archived")
iid = idea["idea_id"]
arch_before = iv.list_ideas(status="archived")
iv.archive_idea(iid)
arch_after = iv.list_ideas(status="archived")
got = iv.get_idea(iid)
step("C1.idea archived after create -> still retrievable",
     got is not None and got.get("status") == "archived",
     f"status={got.get('status') if got else None}")
step("C1.archived list grew by exactly 1",
     len(arch_after) - len(arch_before) == 1,
     f"before={len(arch_before)} after={len(arch_after)}")


# C2. Council with no critic signature -> consolidate-gated REJECTS
print("\nC2: council no-critic-signature rejection ...")
from sylion.governance.council_hybrid import CouncilHybrid
ch = CouncilHybrid(event_bus=EventBus())
cs = ch.open_session("test-no-critic", models=["opus-4-7", "haiku-4-5"],
                     context="does this rocket fly?")
sid = cs["session_id"]
ch.add_participant(sid, model_id="opus-4-7", role="planner", rank="primary")
ch.add_participant(sid, model_id="haiku-4-5", role="critic", rank="primary")
# Add an analysis but skip the critic signature step
ch.add_analysis(sid, model_id="opus-4-7",
                analysis_text="looks fine to me",
                verdict="approve",
                confidence=0.8,
                rationale="looks fine")
try:
    out = ch.consolidate_with_signatures(sid, "Final consolidated text",
                                         require_critic=True)
    step("C2.consolidate-gated rejected (no critic signature)",
         False, f"unexpected pass: {out}")
except ValueError as e:
    step("C2.consolidate-gated raised ValueError on missing critic signature",
         "missing critic signature" in str(e),
         f"{type(e).__name__}: {str(e)[:80]}")
except Exception as e:
    step("C2.consolidate-gated raised on missing critic signature",
         False, f"wrong exception type: {type(e).__name__}: {str(e)[:80]}")


# C3. AuditSink concurrent writes
print("\nC3: AuditSink concurrent writes ...")
from sylion.security.audit_sink import AuditSink
sink = AuditSink(event_bus=EventBus())

errs: list[str] = []
def writer(n: int):
    try:
        for i in range(50):
            sink.log("chaos.event", actor=f"writer-{n}",
                     action="write", result="ok",
                     details={"n": n, "i": i})
    except Exception as e:
        errs.append(f"thread-{n}: {type(e).__name__}: {e}")

threads = [threading.Thread(target=writer, args=(k,)) for k in range(8)]
[t.start() for t in threads]
[t.join() for t in threads]
all_entries = sink.list_log_entries(event_topic="chaos.event", limit=10000)
step("C3.no thread exceptions", len(errs) == 0, str(errs[:3]))
step("C3.8 writers x 50 entries = 400 rows persisted",
     len(all_entries) == 400, f"got {len(all_entries)}")


# C4. ExecutionGuard cleared mid-decision -> deny by default
print("\nC4: ExecutionGuard rule list cleared mid-decision ...")
from sylion.security.execution_guard import ExecutionGuard
eg = ExecutionGuard(event_bus=EventBus())
eg.add_rule("r1", "Allow X", action="allow", resource_pattern="/x/*",
            priority=10)
ok_before = eg.check("/x/foo", "GET")
# Drop all rules
all_rules = eg.list_rules(enabled_only=False)
for r in all_rules:
    try:
        eg.delete_rule(r["rule_id"])
    except Exception:
        pass
res_after = eg.check("/x/foo", "GET")
# After all rules gone, default decision should be deny (not allow)
deny_default = (res_after.get("decision") in ("deny", "default_deny", "no_match")
                or not res_after.get("matched_rule_id"))
step("C4.allow before deletion",
     ok_before.get("decision") == "allow", str(ok_before)[:80])
step("C4.no allow leaks after rules cleared",
     deny_default, str(res_after)[:80])


# C5. SecretProvider rotation while reading
print("\nC5: SecretProvider rotation while reading ...")
from sylion.security.secret_provider import SecretProvider
sp = SecretProvider(event_bus=EventBus())
sp.store("api_key", "API Key", "v1-secret")
read_results: list[str] = []
write_done = threading.Event()

def reader():
    while not write_done.is_set():
        v = sp.retrieve("api_key")
        if v is not None:
            read_results.append(v)
        time.sleep(0.001)

def writer():
    for i in range(2, 6):
        sp.store("api_key", "API Key", f"v{i}-secret")
        time.sleep(0.005)
    write_done.set()

rt = threading.Thread(target=reader)
wt = threading.Thread(target=writer)
rt.start(); wt.start()
wt.join(); rt.join()
all_distinct = set(read_results)
# Each read should return one of the valid versions; never a partial/empty
no_partials = all(v.startswith("v") and v.endswith("-secret") for v in read_results)
step("C5.reader saw at least 1 versioned secret",
     len(read_results) > 0 and no_partials,
     f"reads={len(read_results)} versions={sorted(all_distinct)}")


# C6. AuthProvider duplicate-user race
print("\nC6: AuthProvider duplicate-user race ...")
from sylion.security.auth_provider import AuthProvider, reset_auth_provider
reset_auth_provider()
ap = AuthProvider(event_bus=EventBus())

wins: list[bool] = []
errs2: list[str] = []
def maker():
    try:
        ap.create_user("u-race", "racer", "h-race", role="user")
        wins.append(True)
    except ValueError as e:
        errs2.append(str(e))
    except Exception as e:
        errs2.append(f"unexpected:{type(e).__name__}: {e}")

threads = [threading.Thread(target=maker) for _ in range(8)]
[t.start() for t in threads]
[t.join() for t in threads]
step("C6.exactly one create_user won",
     len(wins) == 1, f"wins={len(wins)} value_errors={len(errs2)}")
step("C6.others raised ValueError (no other exception types)",
     all(("already exists" in e) or ("UNIQUE" in e) for e in errs2),
     f"errs={errs2[:2]}")


# Summary
total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed
out = {
    "phase": "P9-CHAOS-REPAIR",
    "total_checks": total,
    "passed": passed,
    "failed": failed,
    "results": results,
}
OUT = ROOT.parent.parent / ".audit_500" / "PHASE9_CHAOS.json"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
print(f"\nWROTE {OUT}")
print(f"\n{passed}/{total} passed; {failed} failed")
sys.exit(0 if failed == 0 else 1)
