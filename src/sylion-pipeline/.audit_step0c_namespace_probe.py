"""Step 0c -- Pełna enumeracja namespaces po openapi.json.

Iteruje przez WSZYSTKIE GET routes (paramless lub z prostymi defaults),
hitting each via TestClient. Zlicza status codes per namespace, surfaces
any 5xx, any AttributeError/TypeError z body. To jest probe szerszy niż
audit_500 -- pokrywa /workspace, /projects, /skills, /memory, /mobile,
/funding, /governance, /aeis itp.

Output: .audit_500/STEP0C_NAMESPACE_PROBE.json
"""
from __future__ import annotations
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sylion.api.app import app  # noqa: E402

client = TestClient(app)
spec = app.openapi()

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

print(f"namespaces under /api/v1/: {len(ns_routes)}")
print(f"total GET routes: {sum(len(v) for v in ns_routes.values())}")

results: dict[str, dict] = {}
all_errors: list[dict] = []

# Skip routes with required path params we can't satisfy synthetically.
# We hit only GET routes whose path has no {param} OR whose path params we
# fill with a probe value. Routes with required query params get default ''.
def fill_path(path: str) -> str | None:
    """Return a concrete probe path, or None if it has params we
    can't synthesize."""
    if "{" not in path:
        return path
    # naive: replace any {x} with 'probe-x'
    return re.sub(r"\{([^}]+)\}", lambda m: f"probe-{m.group(1)}", path)

for ns, routes in sorted(ns_routes.items()):
    summary = {"total": 0, "200": 0, "404": 0, "422": 0, "5xx": 0,
               "other": 0, "other_codes": {}, "errors": []}
    for path, op_def in routes:
        probe_path = fill_path(path)
        if probe_path is None:
            continue
        try:
            resp = client.get(probe_path)
        except Exception as exc:
            summary["5xx"] += 1
            err = {
                "ns": ns, "path": path,
                "exception": f"{type(exc).__name__}: {str(exc)[:200]}",
            }
            summary["errors"].append(err)
            all_errors.append(err)
            summary["total"] += 1
            continue
        summary["total"] += 1
        sc = resp.status_code
        if sc == 200:
            summary["200"] += 1
        elif sc == 404:
            summary["404"] += 1
        elif sc == 422:
            summary["422"] += 1
        elif sc >= 500:
            summary["5xx"] += 1
            body_preview = resp.text[:300] if resp.text else ""
            err = {
                "ns": ns, "path": path,
                "status": sc, "body_preview": body_preview,
            }
            summary["errors"].append(err)
            all_errors.append(err)
        else:
            summary["other"] += 1
            sc_key = str(sc)
            summary["other_codes"][sc_key] = summary["other_codes"].get(sc_key, 0) + 1
            # Collect a single sample per (ns, sc) for diagnosis
            if summary["other_codes"][sc_key] == 1:
                body_preview = resp.text[:300] if resp.text else ""
                summary["errors"].append({
                    "ns": ns, "path": path,
                    "status": sc, "body_preview": body_preview,
                })
    results[ns] = summary

# Print summary
print()
print("=" * 78)
print(f"{'namespace':<26} {'total':>6} {'200':>5} {'404':>5} {'422':>5} {'5xx':>5} {'oth':>5}")
print("-" * 78)
for ns in sorted(results):
    s = results[ns]
    print(f"{ns:<26} {s['total']:>6} {s['200']:>5} {s['404']:>5} "
          f"{s['422']:>5} {s['5xx']:>5} {s['other']:>5}")
print("-" * 78)
total = {k: sum(s[k] for s in results.values())
         for k in ["total", "200", "404", "422", "5xx", "other"]}
print(f"{'TOTAL':<26} {total['total']:>6} {total['200']:>5} {total['404']:>5} "
      f"{total['422']:>5} {total['5xx']:>5} {total['other']:>5}")

print()
print(f"5xx errors: {len(all_errors)}")
for e in all_errors[:15]:
    body = e.get("body_preview", "") or e.get("exception", "")
    print(f"  [{e['ns']}] {e['path']:<60} -> {body[:150]}")

OUT = ROOT.parent.parent / ".audit_500" / "STEP0C_NAMESPACE_PROBE.json"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({
    "namespaces": results,
    "totals": total,
    "all_errors": all_errors,
}, indent=2, default=str), encoding="utf-8")
print(f"\nWROTE {OUT}")
