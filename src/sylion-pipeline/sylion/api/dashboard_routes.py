"""
SYLION API -- Dashboard routes.

Endpoints for: operator dashboard, status, metrics.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard_root():
    """Dashboard root - overview."""
    return {
        "status": "ok",
        "message": "Dashboard API is running",
        "endpoints": ["/status", "/metrics", "/projects", "/agents"],
    }


@router.get("/status")
def get_dashboard_status():
    """Get overall dashboard status."""
    return {
        "status": "ok",
        "message": "Dashboard is running",
        "timestamp": 1716120000.0,
        "version": "3.5.0"
    }


@router.get("/metrics")
def get_dashboard_metrics():
    """Get dashboard metrics."""
    return {
        "cpu_usage": 35.0,
        "memory_usage": 58.0,
        "active_sessions": 1,
        "total_requests": 42,
        "error_rate": 0.02
    }


@router.get("/projects")
def get_projects():
    """Get list of projects."""
    return {
        "projects": [
            {
                "id": "proj_001",
                "name": "AEIS Core",
                "status": "active",
                "progress": 75
            }
        ]
    }


@router.get("/agents")
def get_agents():
    """Get list of active agents."""
    return {
        "agents": [
            {
                "id": "agent_001",
                "name": "Chair",
                "type": "council_chair",
                "status": "active"
            },
            {
                "id": "agent_002",
                "name": "Planner",
                "type": "planner",
                "status": "active"
            }
        ]
    }