"""
SYLION API -- AEIS Decomposition Engine routes.

  POST /api/v1/aeis/decompose           -- decompose a prompt into task specs
  POST /api/v1/aeis/decompose-and-build -- decompose + assign + dispatch
                                           (local + remote) + merge + evidence

The ``decompose-and-build`` endpoint reads ``infra/hetzner_host_b.json`` if
it exists to add Host B as a worker target. Otherwise dispatch is
local-only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sylion.aeis.decomposition_engine import (
    _rule_decompose,
    decompose_and_build,
)

log = logging.getLogger("sylion.api.decomposition")

router = APIRouter(prefix="/api/v1/aeis", tags=["AEIS Decomposition"])


class DecomposeRequest(BaseModel):
    prompt: str


class DecomposeAndBuildRequest(BaseModel):
    prompt: str
    include_host_b: bool = True
    persist: bool = True


@router.post("/decompose")
def decompose(req: DecomposeRequest) -> dict:
    tasks = _rule_decompose(req.prompt)
    return {
        "prompt": req.prompt,
        "task_count": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
    }


def _resolve_host_b() -> str | None:
    """Return 'host_b:<ip>' if infra/hetzner_host_b.json exists."""
    # repo root: api/../../../../
    here = Path(__file__).resolve()
    for candidate in [
        here.parents[3] / "infra" / "hetzner_host_b.json",
        here.parents[4] / "infra" / "hetzner_host_b.json",
    ]:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text())
                ip = data.get("ipv4")
                if ip:
                    return f"host_b:root@{ip}"
            except Exception as exc:  # noqa: BLE001
                log.warning("failed reading %s: %s", candidate, exc)
    return None


@router.post("/decompose-and-build")
def decompose_and_build_ep(req: DecomposeAndBuildRequest) -> dict:
    workers = ["host_a"]
    if req.include_host_b:
        host_b = _resolve_host_b()
        if host_b:
            workers.append(host_b)
        else:
            log.info("Host B not configured, local-only dispatch")

    artifact_dir = None
    if req.persist:
        # Write artifacts next to repo root for easy gh browsing.
        repo_root = Path(__file__).resolve().parents[3]
        artifact_dir = repo_root / "results" / "decomposed"

    try:
        result = decompose_and_build(
            prompt=req.prompt,
            workers=workers,
            artifact_dir=artifact_dir,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("decompose_and_build failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "pack_id": result.pack_id,
        "prompt": result.prompt,
        "workers_used": workers,
        "elapsed_ms": result.elapsed_ms,
        "task_count": len(result.tasks),
        "tasks": result.tasks,
        "assignments": result.assignments,
        "results": result.results,
        "artifact_path": result.artifact_path,
        "artifact_sha256": result.artifact_sha256,
        "evidence": result.evidence,
    }
