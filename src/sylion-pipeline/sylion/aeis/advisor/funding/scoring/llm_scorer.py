"""LLM judge for soft criteria + per-component explanations.

Re-uses the engine LLM client (per CLAUDE_AEIS guidance — no second client). For
unit tests we keep a deterministic stub mode so smoke tests don't depend on
network availability.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

log = logging.getLogger("sylion.aeis.advisor.funding.scoring.llm_scorer")


@dataclass
class LLMScorerResponse:
    explanations: dict[str, str]
    rationale: str
    prompt_tokens: int
    response_tokens: int
    cost_usd: float
    model_id: str
    was_stub: bool


def _stub_response(component_ids: list[str], reason: str) -> LLMScorerResponse:
    explanations = {
        cid: f"Stub explanation for {cid} (offline mode: {reason})."
        for cid in component_ids
    }
    return LLMScorerResponse(
        explanations=explanations,
        rationale="Stub rationale — no LLM provider reachable; deterministic fallback used.",
        prompt_tokens=64,
        response_tokens=32,
        cost_usd=0.0,
        model_id="stub",
        was_stub=True,
    )


def evaluate_soft_criteria(
    *,
    component_ids: list[str],
    grant_summary: str,
    company_summary: str,
    idea_summary: str,
    model_id: str = "claude-haiku",
    force_stub: bool = False,
) -> LLMScorerResponse:
    """Produce per-component explanations + an overall rationale."""
    if force_stub or os.environ.get("SYLION_ADVISOR_FUNDING_STUB_LLM") == "1":
        return _stub_response(component_ids, reason="forced_stub")

    try:
        from sylion.aeis.advisor.engine.llm_judge.client import get_client
    except Exception as exc:
        log.warning("engine llm client unavailable: %s; using stub", exc)
        return _stub_response(component_ids, reason=f"engine_client_missing:{exc}")

    prompt = _build_prompt(component_ids, grant_summary, company_summary, idea_summary)
    try:
        client = get_client()
        resp = client.call(model_id=model_id, prompt=prompt, max_tokens=1024, temperature=0.2)
    except Exception as exc:
        log.warning("LLM call failed: %s; using stub", exc)
        return _stub_response(component_ids, reason=f"llm_failed:{exc}")

    if getattr(resp, "was_stub", False):
        return _stub_response(component_ids, reason=resp.error or "engine_stub")

    parsed = _safe_parse(resp.text, component_ids)
    return LLMScorerResponse(
        explanations=parsed["explanations"],
        rationale=parsed["rationale"],
        prompt_tokens=resp.prompt_tokens,
        response_tokens=resp.response_tokens,
        cost_usd=resp.cost_usd,
        model_id=resp.model_id,
        was_stub=False,
    )


def _build_prompt(
    component_ids: list[str],
    grant_summary: str,
    company_summary: str,
    idea_summary: str,
) -> str:
    return (
        "You are a funding-grant judge. Produce per-component explanation and a "
        "short overall rationale.\n\n"
        f"Components: {', '.join(component_ids)}\n"
        f"Grant: {grant_summary}\n"
        f"Company: {company_summary}\n"
        f"Idea: {idea_summary}\n\n"
        "Return JSON of the form:\n"
        "{\n"
        "  \"explanations\": {\"<component_id>\": \"...\"},\n"
        "  \"rationale\": \"...\"\n"
        "}\n"
    )


def _safe_parse(text: str, component_ids: list[str]) -> dict:
    try:
        data = json.loads(text)
        explanations = data.get("explanations") or {}
        if not isinstance(explanations, dict):
            explanations = {}
        rationale = str(data.get("rationale", ""))
        for cid in component_ids:
            explanations.setdefault(cid, "")
        return {"explanations": explanations, "rationale": rationale}
    except Exception:
        return {
            "explanations": {cid: "" for cid in component_ids},
            "rationale": text[:512],
        }
