"""Step 0c lite -- focused probe with rate-limit confirmation.

1. Hits a known route 200 times to confirm rate-limit-disabled is effective.
2. Then enumerates all paramless GET routes and records exact code distribution.
3. Saves to .audit_500/STEP0C_NAMESPACE_PROBE.json with full samples.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from collections import defaultdict, Counter
from pathlib import Path

os.environ["SYLION_RBAC_DISABLED"] = "1"
os.environ["SYLION_RATE_LIMIT_DISABLED"] = "1"
os.environ["SYLION_AUTH_BYPASS"] = "1"
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

t0 = time.time()
print(f"[{time.time()-t0:6.1f}s] importing app...", flush=True)
from fastapi.testclient import TestClient
from sylion.api.app import app

print(f"[{time.time()-t0:6.1f}s] app imported, building TestClient...", flush=True)
client = TestClient(app)
print(f"[{time.time()-t0:6.1f}s] TestClient ready, fetching openapi...", flush=True)
spec = app.openapi()
print(f"[{time.time()-t0:6.1f}s] openapi ready ({len(spec['paths'])} paths)", flush=True)

# Confirm rate-limit-disabled works
print(f"\n[{time.time()-t0:6.1f}s] rate-limit verification: hitting /api/v1/audit/sink/health 200x", flush=True)
codes_seen = Counter()
for i in range(200):
    r = client.get("/api/v1/audit/sink/health")
    codes_seen[r.status_code] += 1
print(f"[{time.time()-t0:6.1f}s] codes after 200 hits: {dict(codes_seen)}", flush=True)
if 429 in codes_seen:
    print("ERROR: rate limit kicked in despite env var", file=sys.stderr)
    sys.exit(2)

# Group GET routes by namespace prefix
PREFIX_RE = re.compile(r"^/api/v1/([^/]+)")
ns_routes: dict[str, list[tuple[str, dict]]] = defaultdict(list)
for path, ops in spec["paths"].items():
    if "get" not in ops:
        continue
    m = PREFIX_RE.match(path)
    if not m:
        continue
    ns = m.group(1)
    ns_routes[ns].append((path, ops["get"]))

total_routes = sum(len(v) for v in ns_routes.values())
print(f"\n[{time.time()-t0:6.1f}s] enumerating {total_routes} GET routes across {len(ns_routes)} namespaces", flush=True)


def fill_path(path: str) -> str | None:
    if "{" not in path:
        return path
    return re.sub(r"\{([^}]+)\}", lambda m: f"probe-{m.group(1)}", path)


results: dict[str, dict] = {}
all_5xx: list[dict] = []
all_other: list[dict] = []

import threading
def _hit_with_timeout(probe_path: str, t_sec: float = 5.0):
    """Hit a route via TestClient, return (status, body) or raise TimeoutError."""
    holder: dict = {}
    def runner():
        try:
            r = client.get(probe_path)
            holder["resp"] = r
        except Exception as e:  # noqa: BLE001
            holder["exc"] = e
    th = threading.Thread(target=runner, daemon=True)
    th.start()
    th.join(t_sec)
    if th.is_alive():
        raise TimeoutError(f"timed out after {t_sec}s")
    if "exc" in holder:
        raise holder["exc"]
    return holder["resp"]


for i, (ns, routes) in enumerate(sorted(ns_routes.items())):
    summary = {"total": 0, "by_code": {}, "samples": [], "5xx_errors": []}
    for path, op_def in routes:
        probe_path = fill_path(path)
        if probe_path is None:
            continue
        print(f"  [{time.time()-t0:6.1f}s] HIT {probe_path}", flush=True)
        try:
            resp = _hit_with_timeout(probe_path, t_sec=4.0)
            sc = resp.status_code
            body = resp.text[:300] if resp.text else ""
        except Exception as exc:
            summary["total"] += 1
            err = {
                "ns": ns, "path": path,
                "exception": f"{type(exc).__name__}: {str(exc)[:200]}",
            }
            summary["5xx_errors"].append(err)
            all_5xx.append(err)
            continue
        summary["total"] += 1
        sc_key = str(sc)
        summary["by_code"][sc_key] = summary["by_code"].get(sc_key, 0) + 1
        if sc >= 500:
            err = {"ns": ns, "path": path, "status": sc, "body_preview": body}
            summary["5xx_errors"].append(err)
            all_5xx.append(err)
        # First sample of unusual codes (not 200/404/422)
        if sc not in (200, 404, 422):
            if not any(s["status"] == sc for s in summary["samples"]):
                summary["samples"].append({"path": path, "status": sc, "body_preview": body})
                if sc not in (404, 422, 200, 401, 403):
                    all_other.append({"ns": ns, "path": path, "status": sc, "body": body[:120]})
    results[ns] = summary
    if (i + 1) % 10 == 0:
        elapsed = time.time() - t0
        print(f"[{elapsed:6.1f}s] processed {i+1}/{len(ns_routes)} namespaces", flush=True)

elapsed = time.time() - t0
print(f"\n[{elapsed:6.1f}s] DONE — {len(all_5xx)} 5xx errors, {len(all_other)} unusual non-5xx", flush=True)

# Print summary table
print()
print("=" * 96)
all_codes = set()
for s in results.values():
    all_codes.update(s["by_code"].keys())
codes_sorted = sorted(all_codes, key=lambda x: int(x))
header = f"{'namespace':<26} {'total':>6} " + " ".join(f"{c:>5}" for c in codes_sorted)
print(header)
print("-" * len(header))
totals = {"total": 0}
for c in codes_sorted:
    totals[c] = 0
for ns in sorted(results):
    s = results[ns]
    totals["total"] += s["total"]
    row = f"{ns:<26} {s['total']:>6} "
    cols = []
    for c in codes_sorted:
        n = s["by_code"].get(c, 0)
        totals[c] += n
        cols.append(f"{n:>5}" if n > 0 else f"{'.':>5}")
    row += " ".join(cols)
    print(row)
print("-" * len(header))
row = f"{'TOTAL':<26} {totals['total']:>6} "
row += " ".join(f"{totals[c]:>5}" for c in codes_sorted)
print(row)

# Print 5xx detail
print()
print(f"5xx errors: {len(all_5xx)}")
for e in all_5xx[:25]:
    body = e.get("body_preview", "") or e.get("exception", "")
    print(f"  [{e['ns']}] {e['path']:<70} -> {body[:140]}")

OUT = ROOT.parent.parent / ".audit_500" / "STEP0C_NAMESPACE_PROBE.json"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({
    "namespaces": results,
    "totals": totals,
    "all_5xx_errors": all_5xx,
    "all_unusual_non_5xx": all_other,
    "duration_sec": round(time.time() - t0, 1),
}, indent=2, default=str), encoding="utf-8")
print(f"\nWROTE {OUT}")
