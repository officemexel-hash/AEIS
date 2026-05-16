from __future__ import annotations

from health_check_v2 import CAT_CODES, CATEGORIES_META, get_history


def _handler_categories() -> dict:
    return {
        "count": len(CATEGORIES_META),
        "categories": CATEGORIES_META,
        "total_codes": sum(len(items) for items in CAT_CODES.values()),
    }


def _handler_history(limit: int = 20) -> dict:
    history = get_history(limit=limit)
    return {"count": len(history), "history": history}
