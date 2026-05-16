"""D4 — Human-Like operator walk via FastAPI TestClient (8 surfaces).

This stands in for the Chrome MCP walkthrough. Each "screen" = the REST
surface the frontend would call when an operator opens the page. We
record per-screen: status code, payload shape, time, and any P0/P1
indicators (5xx / unexpected 4xx). Evidence is captured as JSON files
under `docs/claude_system_audit/screenshots/` so D6 can cite them.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "claude_system_audit" / "screenshots"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


SCREENS = [
    ("01-workspace",       "/api/v1/workspace/sessions"),
    ("02-projects",        "/api/v1/projects"),
    ("03-workers",         "/api/v1/workers"),
    ("04-observability",   "/api/v1/metrics"),
    ("05-governance",      "/api/v1/governance/tickets"),
    ("06-funding",         "/api/v1/funding/programmes"),
    ("07-skills",          "/api/v1/skills"),
    ("08-operator-mobile", "/api/v1/mobile/queue?operator_id=op-d-integrate"),
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    from sylion.api.app import app
    with TestClient(app) as c:
        yield c


def _save(name: str, blob: dict[str, Any]) -> None:
    path = EVIDENCE_DIR / f"{name}.json"
    path.write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")


@pytest.mark.parametrize("name,url", SCREENS)
def test_screen_responds_without_p0(client: TestClient, name: str, url: str) -> None:
    started = time.perf_counter()
    response = client.get(url)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    body: Any
    try:
        body = response.json()
    except Exception:
        body = response.text[:1000]

    evidence = {
        "screen": name,
        "url": url,
        "status_code": response.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "content_type": response.headers.get("content-type", ""),
        "p0_indicator": response.status_code >= 500,
        "p1_indicator": response.status_code in (401, 403, 404, 405, 422),
        "body_preview": body if isinstance(body, dict) else (body[:500] if isinstance(body, str) else None),
        "body_shape": (
            list(body.keys())[:30] if isinstance(body, dict)
            else f"list[{len(body)}]" if isinstance(body, list)
            else str(type(body).__name__)
        ),
    }
    _save(name, evidence)

    assert response.status_code < 500, (
        f"P0: {name} ({url}) returned {response.status_code} 5xx"
    )


def test_p0_p1_summary_index(client: TestClient) -> None:
    """Aggregate index of all 8 screens — D6 will cite this file."""
    rollup: list[dict[str, Any]] = []
    for name, url in SCREENS:
        path = EVIDENCE_DIR / f"{name}.json"
        if path.exists():
            rollup.append(json.loads(path.read_text(encoding="utf-8")))

    p0 = [s for s in rollup if s.get("p0_indicator")]
    p1 = [s for s in rollup if s.get("p1_indicator") and not s.get("p0_indicator")]
    summary = {
        "total_screens": len(rollup),
        "p0_count": len(p0),
        "p1_count": len(p1),
        "p0_screens": [s["screen"] for s in p0],
        "p1_screens": [s["screen"] for s in p1],
        "verdict": (
            "BLOCK" if p0
            else "STAGING-WITH-WARNINGS" if p1
            else "PRODUCTION READY"
        ),
    }
    (EVIDENCE_DIR / "00-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    assert summary["p0_count"] == 0, f"P0 surfaces present: {summary['p0_screens']}"
