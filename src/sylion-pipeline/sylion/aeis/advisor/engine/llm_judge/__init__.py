"""LLM-as-judge sub-package."""

from sylion.aeis.advisor.engine.llm_judge.client import LLMJudgeClient, JudgeResponse, get_client
from sylion.aeis.advisor.engine.llm_judge.audit import record_audit
from sylion.aeis.advisor.engine.llm_judge.fallback import resolve_judge_model
from sylion.aeis.advisor.engine.llm_judge.parser import parse_json_response

__all__ = [
    "LLMJudgeClient",
    "JudgeResponse",
    "get_client",
    "record_audit",
    "resolve_judge_model",
    "parse_json_response",
]
