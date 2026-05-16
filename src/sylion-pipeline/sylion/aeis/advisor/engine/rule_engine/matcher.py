"""Match incoming events to rules whose hook_event_pattern matches the topic."""

from __future__ import annotations

import fnmatch
import re

from sylion.aeis.advisor.engine._models import Rule
from sylion.aeis.advisor.engine.rule_engine.dsl import evaluate
from sylion.aeis.advisor.engine.rule_engine.loader import load_active_rules


def _topic_matches(pattern: str, topic: str) -> bool:
    """Pattern accepts:
    - exact: 'aeis.idea.intake.completed'
    - glob: 'aeis.advisor.*'
    - regex (prefixed with re:): 're:aeis\\.production\\..*'"""
    if pattern.startswith("re:"):
        return bool(re.match(pattern[3:], topic))
    return fnmatch.fnmatchcase(topic, pattern)


def match_event_to_rules(topic: str, context: dict) -> list[tuple[Rule, str]]:
    """Return list of (rule, debug_path) where pattern matched and DSL evaluated true."""
    matches: list[tuple[Rule, str]] = []
    for rule in load_active_rules():
        if not _topic_matches(rule.hook_event_pattern, topic):
            continue
        ok, path = evaluate(rule.precondition, context)
        if ok:
            matches.append((rule, path))
    return matches
