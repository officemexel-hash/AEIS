"""W14 Agent Team Theater REST + WS routes.

Read-only surface for the dashboard: topology, council session view,
repair theater, guardian status, local models status.

Per docs/CLAUDE_AEIS_W14_TESTING.md sec 36 + W14_INTEGRATION_CONTRACTS.md C13.

E12 catch-up: ``/ws/agent-theater`` pushes topology + guardians + locals
every ``AGENT_THEATER_WS_INTERVAL_S`` seconds (default 2.0) so the UI
no longer needs 5s HTTP polling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

log = logging.getLogger("sylion.api.agent_theater")

router = APIRouter(prefix="/api/v1/agent-theater", tags=["agent-theater"])

# Separate WS router (no /api/v1 prefix — matches workspace_ws_routes pattern).
ws_router = APIRouter(tags=["agent-theater-ws"])


def _aggregator() -> Any:
    """Lazy-construct AgentTheaterAggregator with shared OntologyStore."""
    from sylion.aeis.testing.agent_theater import AgentTheaterAggregator
    from sylion.aeis.testing.ontology.store import get_ontology_store
    from sylion.aeis_v2.audit_profile import resolve_db_path

    db_name = os.environ.get("SYLION_W14_DB") or os.environ.get(
        "SYLION_DB_PATH", "sylion_aeis.db",
    )
    store = get_ontology_store(db_path=resolve_db_path(db_name))
    return AgentTheaterAggregator(ontology=store)


@router.get("/topology")
def get_topology(project_id: str | None = Query(default=None)) -> dict:
    """Real-time snapshot of active agents + edges."""
    try:
        return _aggregator().get_topology(project_id=project_id)
    except Exception as e:
        log.exception("topology failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/council/{session_id}")
def get_council_view(session_id: str) -> dict:
    """Council session view: votes, signatures, sentinels."""
    try:
        result = _aggregator().get_council_session_view(session_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.exception("council view failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repair/{finding_id}")
def get_repair_theater(finding_id: str) -> dict:
    """Auto-Repair session R-status + Loop Governor budget."""
    try:
        result = _aggregator().get_repair_theater(finding_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.exception("repair theater failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guardians")
def get_guardian_status() -> list[dict]:
    """13 guardians with health + alert counts."""
    try:
        return _aggregator().get_guardian_status()
    except Exception as e:
        log.exception("guardian status failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locals")
def get_local_models_status() -> list[dict]:
    """qwen2.5/qwen3.5/gpt-oss workload."""
    try:
        return _aggregator().get_local_models_status()
    except Exception as e:
        log.exception("local models status failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health() -> dict:
    """Quick liveness check for the aggregator."""
    try:
        agg = _aggregator()
        topo = agg.get_topology()
        return {
            "ok": True,
            "actors": len(topo.get("actors", [])),
            "guardians": len(agg.get_guardian_status()),
            "as_of": topo.get("as_of"),
        }
    except Exception as e:
        log.exception("agent_theater health failed")
        return {"ok": False, "error": str(e)}


@ws_router.websocket("/ws/agent-theater/updates")
@ws_router.websocket("/ws/agent-theater")
async def ws_agent_theater(websocket: WebSocket):
    """Push topology + guardians + locals snapshots periodically.

    Outgoing (server -> client) JSON shape::

        {"type": "snapshot",
         "topology": {...},
         "guardians": [...],
         "locals": [...],
         "as_of": <epoch>}

    Incoming (client -> server)::

        {"type": "ping"}            -> {"type": "pong"}
        {"type": "set_interval", "seconds": 1.5}

    Interval defaults to ``AGENT_THEATER_WS_INTERVAL_S`` env var
    (fallback 2.0s). Clients that disconnect cleanly raise
    WebSocketDisconnect; the publisher task is cancelled.
    """
    await websocket.accept()
    try:
        agg = _aggregator()
    except Exception as e:
        log.exception("aggregator init failed for ws client")
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close()
        return

    interval_default = float(os.environ.get("AGENT_THEATER_WS_INTERVAL_S", "2.0"))
    state: dict[str, float] = {"interval": max(0.5, interval_default)}

    async def _publisher() -> None:
        try:
            while True:
                payload = {
                    "type": "snapshot",
                    "topology": agg.get_topology(),
                    "guardians": agg.get_guardian_status(),
                    "locals": agg.get_local_models_status(),
                }
                await websocket.send_text(json.dumps(payload, default=str))
                await asyncio.sleep(state["interval"])
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("agent-theater ws publisher error")

    publisher_task = asyncio.create_task(_publisher())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "invalid json"})
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await websocket.send_json({"type": "pong"})
            elif mtype == "set_interval":
                try:
                    seconds = float(msg.get("seconds", interval_default))
                    state["interval"] = max(0.5, min(seconds, 30.0))
                    await websocket.send_json({
                        "type": "interval_set",
                        "seconds": state["interval"],
                    })
                except Exception:
                    await websocket.send_json({
                        "type": "error", "detail": "invalid set_interval payload",
                    })
            else:
                await websocket.send_json({
                    "type": "error", "detail": f"unknown message type: {mtype!r}",
                })
    except WebSocketDisconnect:
        log.info("agent-theater ws client disconnected")
    finally:
        publisher_task.cancel()


__all__ = ["router", "ws_router"]
