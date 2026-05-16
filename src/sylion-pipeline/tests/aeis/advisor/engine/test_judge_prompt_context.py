from __future__ import annotations

import json

from sylion.aeis.advisor.engine._models import CardContext
from sylion.aeis.advisor.engine.orchestrator import _judge_prompt_context


def test_judge_prompt_context_includes_actual_idea_values() -> None:
    ctx = CardContext(
        operator_id="op-1",
        triggering_event_topic="aeis.idea.intake.completed",
        triggering_event_payload={
            "project_id": "project_1",
            "title": "Prosty kalkulator kosztow LLM",
            "idea_preview": "Formularz tokenow, progi 80/100 procent i eksport CSV.",
            "api_key": "sk-should-not-leak",
        },
        project_id="project_1",
        idea_id="idea_1",
        project_type="application",
        project_domain="software",
        preferences={"llm_judge_routing": {"low": "bielik"}},
    )

    out = _judge_prompt_context(context=ctx, operator_id="op-1")
    rendered = json.dumps(out, ensure_ascii=False)

    assert "Prosty kalkulator kosztow LLM" in rendered
    assert "Formularz tokenow" in rendered
    assert "payload_keys" in out
    assert "sk-should-not-leak" not in rendered
    assert out["payload"]["api_key"] == "<redacted>"
