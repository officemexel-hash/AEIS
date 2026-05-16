"""Phase 3 API deep sweep: per-namespace probe, OpenAPI alignment.

For each namespace (council, skills, memory, funding, mobile, security,
governance, monitoring, aeis, core, projects, ideas), exercise EVERY
static GET endpoint and report any 5xx / unexpected exception.

Filters:
- Skip streaming endpoints (already proven hangy in Phase 1)
- Skip endpoints that need Path params we can't synthesize
- Note 401/403 separately (not bugs, expected when RBAC is on)
- Note 404 separately (route registered but resource not present)

Output: .audit_500/PHASE3_API_results.json with per-namespace counts +
issues array containing every 5xx/exception with traceback snippet.
"""
from __future__ import annotations
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

t0 = time.monotonic()
from sylion.api.app import app  # noqa: E402
boot_seconds = round(time.monotonic() - t0, 2)

client = TestClient(app)

STREAM_PATTERNS = ("/stream", "/sse", "/ws/", "/websocket", "/upload",
                   "/download", "/tail", "/follow", "/listen", "/events/poll")

NAMESPACES = [
    "core", "governance", "ideas", "council", "council_workflow", "skills",
    "memory", "funding", "mobile", "security", "monitoring", "aeis",
    "projects", "lifecycle", "quality", "ai", "deploy", "evidence",
    "hooks", "policies", "snapshots", "ml", "efficiency", "data",
    "workspace", "production", "audit",
]


def is_static(path: str) -> bool:
    return "{" not in path


def get_static_routes_by_ns() -> dict[str, list[str]]:
    """Group static GET routes by namespace prefix."""
    by_ns: dict[str, list[str]] = defaultdict(list)
    for r in app.routes:
        path = getattr(r, "path", "")
        methods = getattr(r, "methods", set()) or set()
        if "GET" not in methods:
            continue
        if not is_static(path):
            continue
        if any(p in path for p in STREAM_PATTERNS):
            continue
        # Parse namespace: /api/v1/<ns>/...
        parts = path.split("/")
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "v1":
            ns = parts[3]
            by_ns[ns].append(path)
        else:
            by_ns["other"].append(path)
    return by_ns


def probe_one(path: str) -> dict:
    """Probe a single endpoint. Return dict with status, ms, errors."""
    t = time.monotonic()
    try:
        r = client.get(path, timeout=5.0)
        ms = int((time.monotonic() - t) * 1000)
        return {
            "path": path, "status": r.status_code, "ms": ms,
            "size": len(r.content), "exc": None,
        }
    except Exception as exc:
        ms = int((time.monotonic() - t) * 1000)
        return {
            "path": path, "status": None, "ms": ms, "size": 0,
            "exc": f"{type(exc).__name__}: {str(exc)[:200]}",
            "tb": traceback.format_exc()[-2000:],
        }


def main():
    by_ns = get_static_routes_by_ns()
    out: dict[str, object] = {
        "phase": "P3-API-DEEP",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "boot_seconds": boot_seconds,
        "namespaces": {},
        "issues": [],
        "totals": {},
    }

    grand: dict[str, int] = defaultdict(int)
    issues: list[dict] = []

    for ns in sorted(by_ns):
        paths = by_ns[ns]
        ns_counts = defaultdict(int)
        for path in paths:
            res = probe_one(path)
            sc = res["status"]
            if res["exc"]:
                ns_counts["exc"] += 1
                grand["exc"] += 1
                issues.append({"namespace": ns, **res})
            elif sc is None:
                ns_counts["null"] += 1
                grand["null"] += 1
            elif sc >= 500:
                ns_counts["5xx"] += 1
                grand["5xx"] += 1
                issues.append({"namespace": ns, **res})
            elif sc in (401, 403):
                ns_counts["auth"] += 1
                grand["auth"] += 1
            elif sc == 404:
                ns_counts["404"] += 1
                grand["404"] += 1
            elif sc == 422:
                ns_counts["422"] += 1
                grand["422"] += 1
            elif 400 <= sc < 500:
                ns_counts["4xx_other"] += 1
                grand["4xx_other"] += 1
            elif 200 <= sc < 300:
                ns_counts["ok"] += 1
                grand["ok"] += 1
            else:
                ns_counts["other"] += 1
                grand["other"] += 1
        out["namespaces"][ns] = {
            "static_get_count": len(paths),
            "counts": dict(ns_counts),
        }
        total = sum(ns_counts.values())
        ok = ns_counts.get("ok", 0)
        five = ns_counts.get("5xx", 0)
        ex = ns_counts.get("exc", 0)
        marker = "[5xx!]" if (five + ex) > 0 else "[ok]"
        print(f"{marker} {ns:20s}  total={total:3d}  ok={ok:3d}  "
              f"5xx={five}  exc={ex}  auth={ns_counts.get('auth',0)}  "
              f"404={ns_counts.get('404',0)}  422={ns_counts.get('422',0)}")

    out["totals"] = dict(grand)
    out["issues"] = issues
    out["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    OUT = ROOT.parent.parent / ".audit_500" / "PHASE3_API_results.json"
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nWROTE {OUT}")
    print(f"Grand totals: {dict(grand)}")
    print(f"5xx + exc count: {grand['5xx'] + grand['exc']}")
    return grand["5xx"] + grand["exc"]


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
