from __future__ import annotations

import os
from pathlib import Path


def funding_results_root() -> Path:
    configured = os.environ.get("SYLION_FUNDING_RESULTS_ROOT", "").strip()
    if configured:
        root = Path(configured)
    else:
        root = Path(__file__).resolve().parents[3] / "results" / "funding"
    root.mkdir(parents=True, exist_ok=True)
    return root


def funding_db_path() -> str:
    from sylion.aeis_v2.audit_profile import resolve_db_path

    return str(resolve_db_path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db")))
