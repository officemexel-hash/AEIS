"""
SYLION API -- Runs routes.

Endpoints for: pipeline runs, execution runs.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def get_runs(status: Optional[str] = None, limit: int = 100):
    """Get list of runs with optional status filter."""
    runs = [
        {
            "id": "run_001",
            "name": "AEIS Pipeline Run",
            "status": status or "running",
            "progress": 75,
            "created_at": 1716120000.0,
            "updated_at": 1716120000.0
        }
    ]
    
    return {"runs": runs}


@router.get("/{run_id}")
def get_run(run_id: str):
    """Get a specific run by ID."""
    if run_id != "run_001":
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "id": run_id,
        "name": "AEIS Pipeline Run",
        "status": "running",
        "progress": 75,
        "created_at": 1716120000.0,
        "updated_at": 1716120000.0,
        "steps": [
            {"id": "step_001", "name": "Initialization", "status": "completed"},
            {"id": "step_002", "name": "Processing", "status": "running"},
            {"id": "step_003", "name": "Finalization", "status": "pending"}
        ]
    }


@router.post("", status_code=201)
def create_run(name: str, description: str = ""):
    """Create a new run."""
    return {
        "id": "run_001",
        "name": name,
        "description": description,
        "status": "created",
        "progress": 0,
        "created_at": 1716120000.0,
        "updated_at": 1716120000.0
    }


@router.post("/{run_id}/start")
def start_run(run_id: str):
    """Start a run."""
    if run_id != "run_001":
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "id": run_id,
        "status": "running",
        "message": "Run started successfully"
    }


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str):
    """Cancel a run."""
    if run_id != "run_001":
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "id": run_id,
        "status": "cancelled",
        "message": "Run cancelled successfully"
    }


@router.get("/{run_id}/logs")
def get_run_logs(run_id: str, limit: int = 100):
    """Get logs for a specific run."""
    if run_id != "run_001":
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "logs": [
            {
                "timestamp": 1716120000.0,
                "level": "info",
                "message": "Run started"
            },
            {
                "timestamp": 1716120001.0,
                "level": "info",
                "message": "Processing step 1"
            }
        ]
    }