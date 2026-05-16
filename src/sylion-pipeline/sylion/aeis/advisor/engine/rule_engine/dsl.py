"""Rule precondition DSL evaluator.

DSL is JSON stored in `rule_definitions.precondition`. Supported shapes:

  {"and": [<sub>, <sub>, ...]}            -- all subs must match
  {"or":  [<sub>, <sub>, ...]}            -- any sub must match
  {"not": <sub>}                          -- negation
  {"field": "<dotted.path>", "op": "<op>", "value": <v>}

Comparison ops: ==, !=, >, >=, <, <=, in, not_in, contains, is_null,
is_not_null, matches_regex.

The empty precondition {} always matches (used for "always-fire" rules like
idea-intake initial guidance).
"""

from __future__ import annotations

import re
from typing import Any


def evaluate(precondition: dict | None, context: dict) -> tuple[bool, str]:
    """Return (matched, debug_path) for an introspectable result."""
    if not precondition:
        return True, "empty_precondition"

    if "and" in precondition:
        for sub in precondition["and"]:
            ok, path = evaluate(sub, context)
            if not ok:
                return False, f"and[{path}]"
        return True, "and:all_matched"

    if "or" in precondition:
        for sub in precondition["or"]:
            ok, path = evaluate(sub, context)
            if ok:
                return True, f"or[{path}]"
        return False, "or:none_matched"

    if "not" in precondition:
        ok, path = evaluate(precondition["not"], context)
        return (not ok), f"not[{path}]"

    if "field" in precondition:
        field_path = precondition["field"]
        op = precondition.get("op", "==")
        target = precondition.get("value")
        actual = _resolve_field(field_path, context)
        return _compare(actual, op, target), f"{field_path} {op} {target!r} (actual={actual!r})"

    return False, "unknown_precondition_shape"


def _resolve_field(path: str, context: dict) -> Any:
    parts = path.split(".")
    cur: Any = context
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, (list, tuple)):
            if p.lstrip("-").isdigit():
                idx = int(p)
                cur = cur[idx] if -len(cur) <= idx < len(cur) else None
            else:
                return None
        else:
            return None
    return cur


def _compare(actual: Any, op: str, target: Any) -> bool:
    if op == "is_null":
        return actual is None
    if op == "is_not_null":
        return actual is not None
    if actual is None:
        return False
    try:
        if op == "==":
            return actual == target
        if op == "!=":
            return actual != target
        if op == ">":
            return actual > target
        if op == ">=":
            return actual >= target
        if op == "<":
            return actual < target
        if op == "<=":
            return actual <= target
        if op == "in":
            return actual in (target or [])
        if op == "not_in":
            return actual not in (target or [])
        if op == "contains":
            return target in actual
        if op == "matches_regex":
            return bool(re.search(str(target), str(actual)))
    except TypeError:
        return False
    return False
