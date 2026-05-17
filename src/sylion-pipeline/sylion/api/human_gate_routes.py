"""
SYLION API -- Human Gate routes.

Endpoints for: human gate approvals, decisions.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List

router = APIRouter(prefix="/api/human-gate", tags=["human-gate"])


@router.get("")
def get_human_gate_items(status: Optional[str] = None, limit: int = 100):
    """Get list of human gate items with optional status filter."""
    items = [
        {
            "id": "hg_001",
            "title": "AEIS Core Decision",
            "status": status or "pending",
            "created_at": 1716120000.0,
            "updated_at": 1716120000.0,
            "description": "Review and approve AEIS core configuration changes"
        }
    ]
    
    return {"items": items}


@router.get("/{item_id}")
def get_human_gate_item(item_id: str):
    """Get a specific human gate item by ID."""
    if item_id != "hg_001":
        raise HTTPException(status_code=404, detail=f"Human gate item {item_id} not found")
    
    return {
        "id": item_id,
        "title": "AEIS Core Decision",
        "status": "pending",
        "created_at": 1716120000.0,
        "updated_at": 1716120000.0,
        "description": "Review and approve AEIS core configuration changes",
        "decision_class": "D3",
        "proposer": "system",
        "evidence": [],
        "votes": []
    }


@router.post("/{item_id}/approve")
def approve_human_gate_item(item_id: str, notes: str = ""):
    """Approve a human gate item."""
    if item_id != "hg_001":
        raise HTTPException(status_code=404, detail=f"Human gate item {item_id} not found")
    
    return {
        "id": item_id,
        "status": "approved",
        "message": "Item approved successfully",
        "notes": notes,
        "approved_at": 1716120000.0
    }


@router.post("/{item_id}/reject")
def reject_human_gate_item(item_id: str, reason: str = ""):
    """Reject a human gate item."""
    if item_id != "hg_001":
        raise HTTPException(status_code=404, detail=f"Human gate item {item_id} not found")
    
    return {
        "id": item_id,
        "status": "rejected",
        "message": "Item rejected successfully",
        "reason": reason,
        "rejected_at": 1716120000.0
    }


@router.post("/{item_id}/defer")
def defer_human_gate_item(item_id: str, reason: str = ""):
    """Defer a human gate item for later review."""
    if item_id != "hg_001":
        raise HTTPException(status_code=404, detail=f"Human gate item {item_id} not found")
    
    return {
        "id": item_id,
        "status": "deferred",
        "message": "Item deferred successfully",
        "reason": reason,
        "deferred_at": 1716120000.0
    }


@router.get("/{item_id}/history")
def get_human_gate_history(item_id: str, limit: int = 50):
    """Get history of actions for a human gate item."""
    if item_id != "hg_001":
        raise HTTPException(status_code=404, detail=f"Human gate item {item_id} not found")
    
    return {
        "history": [
            {
                "timestamp": 1716120000.0,
                "action": "created",
                "user": "system",
                "notes": "Human gate item created"
            },
            {
                "timestamp": 1716120001.0,
                "action": "review_requested",
                "user": "Chair",
                "notes": "Review requested from council"
            }
        ]
    }


@router.get("/stats")
def get_human_gate_stats():
    """Get human gate statistics."""
    return {
        "total_items": 1,
        "pending_items": 1,
        "approved_items": 0,
        "rejected_items": 0,
        "deferred_items": 0,
        "avg_processing_time": 3600.0
    }