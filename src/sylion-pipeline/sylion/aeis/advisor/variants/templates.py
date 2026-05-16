"""Strategic variant templates."""

from __future__ import annotations

from typing import Any

COST_SAVING_TEMPLATE: dict[str, Any] = {
    "name": "cost_saving",
    "description": "Local-first, minimal council, cheaper workers, slower",
    "parameters": {
        "council_size": 3,
        "use_local_models": True,
        "use_external_apis": False,
        "vps_envs": 0,
        "topology": "local_only",
        "critic_model": None,
    },
}

BALANCED_TEMPLATE: dict[str, Any] = {
    "name": "balanced",
    "description": "Local + selected external APIs, moderate council, limited VPS",
    "parameters": {
        "council_size": 5,
        "use_local_models": True,
        "use_external_apis": True,
        "vps_envs": 1,
        "topology": "local_plus_vps",
        "critic_model": "claude-sonnet-4-6",
    },
}

AGGRESSIVE_TEMPLATE: dict[str, Any] = {
    "name": "aggressive",
    "description": "Multiple models, parallel envs, VPS scaling, faster + more expensive",
    "parameters": {
        "council_size": 7,
        "use_local_models": True,
        "use_external_apis": True,
        "vps_envs": 3,
        "topology": "multi_vps",
        "critic_model": "claude-opus-4-7",
    },
}

ALL_TEMPLATES = [COST_SAVING_TEMPLATE, BALANCED_TEMPLATE, AGGRESSIVE_TEMPLATE]
