"""SYLION API - Event Backbone monitoring routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from sylion.core.event_backbone import EventBackboneError

router = APIRouter(prefix="/api/v1/event-backbone", tags=["event-backbone"])

_backbone = None


def _get_backbone():
    global _backbone
    if _backbone is not None:
        return _backbone
    from sylion.core.event_backbone import get_event_backbone

    _backbone = get_event_backbone()
    return _backbone


def _raise_backbone_error(exc: EventBackboneError) -> None:
    raise HTTPException(status_code=exc.http_status, detail=exc.to_dict())


def _raise_generic_error(operation: str, exc: Exception) -> None:
    raise HTTPException(
        status_code=503,
        detail={
            "backend": "unknown",
            "operation": operation,
            "status": "error",
            "message": str(exc),
        },
    )


def _health_status_code(payload: dict) -> int:
    return 200 if payload.get("status") == "ok" else 503


def _safe_health() -> dict:
    try:
        return _get_backbone().health()
    except EventBackboneError as exc:
        return exc.to_dict()
    except Exception as exc:
        return {
            "backend": "unknown",
            "status": "error",
            "message": str(exc),
        }


@router.get("/health")
def backbone_health():
    payload = _safe_health()
    status_code = _health_status_code(payload)
    if status_code == 200:
        return payload
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/catalog")
def backbone_catalog():
    try:
        bb = _get_backbone()
        return {"topics": bb.get_catalog()}
    except EventBackboneError as exc:
        _raise_backbone_error(exc)
    except Exception as exc:
        _raise_generic_error("catalog", exc)


@router.get("/events")
def backbone_events(topic: str | None = None, limit: int = 100):
    try:
        bb = _get_backbone()
        return {"events": bb.query(topic=topic, limit=limit)}
    except EventBackboneError as exc:
        _raise_backbone_error(exc)
    except Exception as exc:
        _raise_generic_error("query", exc)
