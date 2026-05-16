"""Phase 6: deep probe of skills + memory + mobile + funding namespaces."""
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

STREAM = ("/stream", "/sse", "/ws/", "/websocket", "/upload",
          "/download", "/tail", "/follow", "/listen", "/events/poll")
TARGET_NS = ("skills", "memory", "mobile", "funding")


def collect():
    by_ns: dict[str, list[str]] = defaultdict(list)
    for r in app.routes:
        p = getattr(r, "path", "")
        methods = getattr(r, "methods", set()) or set()
        if "GET" not in methods:
            continue
        if "{" in p or any(s in p for s in STREAM):
            continue
        parts = p.split("/")
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "v1":
            ns = parts[3]
            if ns in TARGET_NS:
                by_ns[ns].append(p)
    return by_ns


def probe(path: str) -> dict:
    t = time.monotonic()
    try:
        r = client.get(path, timeout=5.0)
        ms = int((time.monotonic() - t) * 1000)
        return {"path": path, "status": r.status_code, "ms": ms,
                "size": len(r.content), "exc": None}
    except Exception as exc:
        ms = int((time.monotonic() - t) * 1000)
        return {"path": path, "status": None, "ms": ms, "size": 0,
                "exc": f"{type(exc).__name__}: {str(exc)[:200]}",
                "tb": traceback.format_exc()[-1500:]}


def main():
    by_ns = collect()
    out = {"phase": "P6-SKILL-MEM-MOBILE-FUND",
           "boot_seconds": boot_seconds,
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "namespaces": {}, "issues": [], "totals": {}}
    grand: dict[str, int] = defaultdict(int)
    issues: list[dict] = []

    for ns in TARGET_NS:
        paths = by_ns.get(ns, [])
        ns_counts: dict[str, int] = defaultdict(int)
        for p in paths:
            res = probe(p)
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
        print(f"{marker} {ns:10s}  total={total:3d}  ok={ok:3d}  5xx={five}  "
              f"exc={ex}  auth={ns_counts.get('auth',0)}  "
              f"404={ns_counts.get('404',0)}  422={ns_counts.get('422',0)}")

    out["totals"] = dict(grand)
    out["issues"] = issues
    out["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    OUT = ROOT.parent.parent / ".audit_500" / "PHASE6_SKILL_MEM_MOBILE_FUND.json"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nWROTE {OUT}")
    print(f"Grand totals: {dict(grand)}")
    return grand["5xx"] + grand["exc"]


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
