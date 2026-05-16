"""Multi-provider LLM judge client.

Dashboard/runtime calls go through ``sylion.cognitive.llm_runtime`` so API keys
entered in the onboarding dashboard are used directly from KeyVault. Missing
providers are explicit failures unless ``SYLION_ALLOW_LLM_STUB=1`` is set for
unit-test fixtures.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("sylion.aeis.advisor.engine.llm_judge.client")


@dataclass
class JudgeResponse:
    text: str
    model_id: str
    prompt_tokens: int
    response_tokens: int
    latency_ms: int
    provider_id: str
    cost_usd: float = 0.0
    was_stub: bool = False
    error: str = ""
    requested_model_id: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""


class LLMJudgeClient:
    """Sync wrapper over Anthropic / OpenAI / Google / Ollama.

    Per-provider clients are lazy-initialised. A deterministic local stub is
    used when no provider matches or when SDKs are unavailable, so engine flow
    can be exercised end-to-end in CI without real API keys.
    """

    def __init__(self) -> None:
        self._anthropic = None
        self._openai = None
        self._google = None
        self._lock = threading.Lock()

    def call(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        timeout_s: float = 30.0,
    ) -> JudgeResponse:
        start = time.time()
        if str(os.environ.get("SYLION_FORCE_LLM_STUB", "")).lower() in {"1", "true", "yes"}:
            resp = self._call_stub(model_id, prompt, max_tokens, temperature, "forced_test_stub")
            resp.latency_ms = int((time.time() - start) * 1000)
            return resp
        try:
            from sylion.cognitive.llm_runtime import call_llm, infer_provider_for_model

            provider = infer_provider_for_model(model_id)
            result = call_llm(
                prompt,
                provider=provider,
                model=model_id,
                role="critic",
                max_tokens=max_tokens,
            )
            resp = JudgeResponse(
                text=result.text,
                model_id=result.model,
                prompt_tokens=result.prompt_tokens,
                response_tokens=result.completion_tokens,
                latency_ms=result.latency_ms,
                provider_id=("ollama_local" if result.provider == "ollama" else result.provider),
                cost_usd=result.estimated_cost_usd,
                was_stub=False,
                error="",
                requested_model_id=model_id,
                fallback_used=bool(result.fallback_used),
                fallback_reason=(
                    f"requested={result.provider_requested or infer_provider_for_model(model_id)}:"
                    f"{result.model_requested or model_id}; used={result.provider}:{result.model}"
                    if result.fallback_used else ""
                ),
            )
        except Exception as exc:
            if str(os.environ.get("SYLION_ALLOW_LLM_STUB", "")).lower() in {"1", "true", "yes"}:
                log.warning("LLM call failed model=%s err=%s; explicit test stub enabled", model_id, exc)
                resp = self._call_stub(model_id, prompt, max_tokens, temperature, str(exc))
            else:
                raise

        resp.latency_ms = int((time.time() - start) * 1000)
        return resp

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _call_anthropic(self, model_id, prompt, max_tokens, temp, timeout_s):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return self._call_stub(model_id, prompt, max_tokens, temp, "missing_anthropic_key")
        try:
            from anthropic import Anthropic  # type: ignore
        except Exception as exc:
            return self._call_stub(model_id, prompt, max_tokens, temp, f"anthropic_sdk_missing:{exc}")
        with self._lock:
            if self._anthropic is None:
                self._anthropic = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = self._anthropic.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temp,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout_s,
        )
        text = msg.content[0].text if msg.content else ""
        return JudgeResponse(
            text=text,
            model_id=model_id,
            prompt_tokens=msg.usage.input_tokens,
            response_tokens=msg.usage.output_tokens,
            latency_ms=0,
            provider_id="anthropic",
        )

    def _call_openai(self, model_id, prompt, max_tokens, temp, timeout_s):
        if not os.environ.get("OPENAI_API_KEY"):
            return self._call_stub(model_id, prompt, max_tokens, temp, "missing_openai_key")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            return self._call_stub(model_id, prompt, max_tokens, temp, f"openai_sdk_missing:{exc}")
        with self._lock:
            if self._openai is None:
                self._openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = self._openai.chat.completions.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temp,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout_s,
        )
        text = resp.choices[0].message.content or ""
        return JudgeResponse(
            text=text,
            model_id=model_id,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else len(prompt) // 4,
            response_tokens=resp.usage.completion_tokens if resp.usage else len(text) // 4,
            latency_ms=0,
            provider_id="openai",
        )

    def _call_google(self, model_id, prompt, max_tokens, temp, timeout_s):
        if not os.environ.get("GOOGLE_API_KEY"):
            return self._call_stub(model_id, prompt, max_tokens, temp, "missing_google_key")
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as exc:
            return self._call_stub(model_id, prompt, max_tokens, temp, f"google_sdk_missing:{exc}")
        with self._lock:
            if self._google is None:
                genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
                self._google = genai
        model = self._google.GenerativeModel(model_id)
        resp = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens, "temperature": temp},
        )
        text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        return JudgeResponse(
            text=text,
            model_id=model_id,
            prompt_tokens=getattr(usage, "prompt_token_count", len(prompt) // 4),
            response_tokens=getattr(usage, "candidates_token_count", len(text) // 4),
            latency_ms=0,
            provider_id="google",
        )

    def _call_ollama(self, model_id, prompt, max_tokens, temp, timeout_s):
        try:
            import httpx  # type: ignore
        except Exception as exc:
            return self._call_stub(model_id, prompt, max_tokens, temp, f"httpx_missing:{exc}")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            resp = httpx.post(
                f"{base_url}/api/generate",
                json={
                    "model": model_id,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temp, "num_predict": max_tokens},
                },
                timeout=timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return self._call_stub(model_id, prompt, max_tokens, temp, f"ollama_unreachable:{exc}")
        text = data.get("response", "")
        return JudgeResponse(
            text=text,
            model_id=model_id,
            prompt_tokens=data.get("prompt_eval_count", len(prompt) // 4),
            response_tokens=data.get("eval_count", len(text) // 4),
            latency_ms=0,
            provider_id="ollama_local",
        )

    def _call_stub(self, model_id, prompt, max_tokens, temp, reason):
        """Deterministic offline stub used only by explicit test fixtures."""
        synthetic = {
            "rationale": (
                "Testowy stub sedziego LLM (brak dostepnego providera). "
                "Doradca emituje strukturalna rekomendacje na podstawie reguly "
                "i snapshotu kosztow, ale wynik musi zostac zastapiony realnym "
                "modelem przed audytem produkcyjnym. Powod: " + reason
            ),
            "expected_benefit": "Operator dostaje konkretna rekomendacje do oceny.",
            "expected_downside": "Stub uzywa gotowych sformulowan; jakosc jest nizsza niz przy realnym sedzim LLM.",
            "quality_impact": "Struktura karty pozostaje poprawna, ale narracja jest generyczna.",
            "alternatives": [],
        }
        text = json.dumps(synthetic)
        return JudgeResponse(
            text=text,
            model_id=model_id,
            prompt_tokens=len(prompt) // 4,
            response_tokens=len(text) // 4,
            latency_ms=0,
            provider_id="stub",
            was_stub=True,
            error=reason,
        )


_client: LLMJudgeClient | None = None
_client_lock = threading.Lock()


def get_client() -> LLMJudgeClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = LLMJudgeClient()
    return _client
