"""Forever-retention audit of every LLM judge call."""

from __future__ import annotations

import logging
import uuid

from sylion.aeis.advisor.engine._db import insert_llm_judge_audit
from sylion.aeis.advisor.engine.llm_judge.client import JudgeResponse

log = logging.getLogger("sylion.aeis.advisor.engine.llm_judge.audit")


def record_audit(
    *,
    operator_id: str,
    judge_purpose: str,
    prompt: str,
    response: JudgeResponse,
    card_id: str | None = None,
    parent_audit_id: str | None = None,
) -> str:
    audit_id = str(uuid.uuid4())
    insert_llm_judge_audit(
        audit_id=audit_id,
        card_id=card_id,
        operator_id=operator_id,
        judge_purpose=judge_purpose,
        model_id=response.model_id,
        prompt_full=prompt,
        response_full=response.text or "",
        prompt_tokens=response.prompt_tokens,
        response_tokens=response.response_tokens,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
        was_local_fallback=(
            response.was_stub
            or bool(response.fallback_used and response.provider_id == "ollama_local")
        ),
        fallback_reason=response.error or response.fallback_reason or None,
        parent_audit_id=parent_audit_id,
    )
    log.debug(
        "audit recorded id=%s purpose=%s model=%s tokens=%d/%d stub=%s",
        audit_id,
        judge_purpose,
        response.model_id,
        response.prompt_tokens,
        response.response_tokens,
        response.was_stub,
    )
    return audit_id
