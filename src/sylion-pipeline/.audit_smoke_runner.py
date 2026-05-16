"""Phase 1 SMOKE runner — boot/health/openapi/inventory/sample probe.

Writes results to .audit_500/SMOKE_results.json so we never lose output to a
buffered shell pipe.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

os.environ["SYLION_RBAC_DISABLED"] = "1"
sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).resolve().parents[2] / ".audit_500" / "SMOKE_results.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

result: dict = {
    "phase": "P1-SMOKE",
    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def _write() -> None:
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")


def _step(name: str):
    """Decorator-like helper: runs a callable, captures status + ms + payload."""

    def runner(fn):
        t0 = time.time()
        try:
            payload = fn()
            result.setdefault("steps", {})[name] = {
                "status": "ok",
                "ms": int((time.time() - t0) * 1000),
                "data": payload,
            }
        except Exception as exc:  # pragma: no cover
            result.setdefault("steps", {})[name] = {
                "status": "fail",
                "ms": int((time.time() - t0) * 1000),
                "exc": f"{type(exc).__name__}: {exc}",
                "tb": traceback.format_exc(limit=4),
            }
        finally:
            _write()
        return result["steps"][name]

    return runner


_write()


def boot():
    t0 = time.time()
    from fastapi.testclient import TestClient
    from sylion.api.app import app

    return {
        "boot_seconds": round(time.time() - t0, 2),
        "route_count": len(app.routes),
        "client": id(TestClient(app)),
    }


_step("S1_boot")(boot)


# Reuse the imported app for subsequent probes
from fastapi.testclient import TestClient  # noqa: E402
from sylion.api.app import app  # noqa: E402

c = TestClient(app)


def health():
    r = c.get("/api/health")
    return {"status": r.status_code, "body": r.text[:300]}


_step("S2_health")(health)


def openapi():
    r = c.get("/openapi.json")
    if r.status_code != 200:
        return {"status": r.status_code}
    paths = r.json().get("paths", {})
    return {"status": 200, "path_count": len(paths)}


_step("S3_openapi")(openapi)


def inventory():
    static_get = []
    dynamic_get = []
    all_methods: dict[str, int] = {}
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        for m in route.methods:
            all_methods[m] = all_methods.get(m, 0) + 1
        if "GET" in route.methods:
            (dynamic_get if "{" in route.path else static_get).append(route.path)
    return {
        "static_get": len(static_get),
        "dynamic_get": len(dynamic_get),
        "method_counts": all_methods,
        "first_20_static": static_get[:20],
    }


inv = _step("S4_inventory")(inventory)["data"]


def probe():
    import signal
    import platform

    # Skip streaming/SSE/websocket/long-poll endpoints — TestClient blocks on them
    SKIP_PATTERNS = ("/stream", "/sse", "/ws/", "/websocket", "/upload", "/download", "/tail", "/follow", "/listen")
    static = [
        r.path
        for r in app.routes
        if hasattr(r, "methods") and "GET" in r.methods and hasattr(r, "path") and "{" not in r.path
        and not any(s in r.path for s in SKIP_PATTERNS)
    ]
    sampled = static[::5]
    issues = []
    counts = {"ok": 0, "auth": 0, "404": 0, "4xx_other": 0, "5xx": 0, "exc": 0, "timeout": 0}

    use_signal = platform.system() != "Windows"  # SIGALRM is Unix-only

    class TimeoutErr(Exception):
        pass

    def _alarm_handler(signum, frame):
        raise TimeoutErr("probe timeout")

    if use_signal:
        signal.signal(signal.SIGALRM, _alarm_handler)

    for i, p in enumerate(sampled):
        # Per-call streaming progress so we can see which path is the blocker
        result.setdefault("steps", {}).setdefault("S5_probe", {})["currently_probing"] = p
        _write()
        try:
            if use_signal:
                signal.alarm(5)
            rr = c.get(p)
            if use_signal:
                signal.alarm(0)
            sc = rr.status_code
            if sc in (401, 403):
                counts["auth"] += 1
            elif sc >= 500:
                counts["5xx"] += 1
                issues.append({"path": p, "status": sc, "snippet": rr.text[:160]})
            elif sc == 404:
                counts["404"] += 1
            elif sc >= 400:
                counts["4xx_other"] += 1
            else:
                counts["ok"] += 1
        except TimeoutErr:
            counts["timeout"] += 1
            issues.append({"path": p, "status": "TIMEOUT"})
        except Exception as exc:
            counts["exc"] += 1
            issues.append({"path": p, "status": "EXC", "exc": f"{type(exc).__name__}: {exc}"})
        finally:
            if use_signal:
                signal.alarm(0)
        if (i + 1) % 5 == 0:
            result["steps"]["S5_probe"]["progress"] = f"{i+1}/{len(sampled)} counts={counts}"
            _write()
    result["steps"]["S5_probe"]["progress"] = f"{len(sampled)}/{len(sampled)} done"
    return {"sample_size": len(sampled), "counts": counts, "issues": issues}


_step("S5_probe")(probe)


result["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
_write()
print(f"WROTE {OUT}")
print(json.dumps({k: v.get("status") for k, v in result.get("steps", {}).items()}, indent=2))
