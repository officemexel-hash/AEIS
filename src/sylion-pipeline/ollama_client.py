"""
SYLION v5.9.1 — OllamaClient
==============================
Async HTTP client for the Ollama local inference daemon (http://localhost:11434).

Design goals
------------
* LiteLLM-compatible chat interface (pass-through to `ollama_chat/<model>`).
* Circuit breaker: automatic fallback to cloud if daemon is down or too slow.
* Warmup: preload model weights into VRAM on pipeline start (avoids 8–15 s
  cold-start on the first real request).
* GPU/VRAM health check: guard against OOM before dispatching a job.
* Benchmark: measure tokens/sec throughput for FinOps tier routing decisions.
* Structured logging via stdlib `logging`; no external deps beyond httpx.

Dependencies
------------
    httpx>=0.27          (already in requirements-lock.txt)
    litellm>=1.67        (already in requirements-lock.txt)

Usage
-----
    from ollama_client import OllamaClient, CircuitOpen

    client = OllamaClient(base_url="http://localhost:11434")

    # health + warmup on pipeline start
    health = await client.health()
    if health.online:
        await client.warmup("llama3")

    # chat call — falls back to `fallback_fn` if circuit is open
    resp = await client.chat(
        model="llama3",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # benchmark throughput
    result = await client.benchmark("llama3")
    print(result.tokens_per_sec)
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from urllib.parse import urlparse, urlunparse

import httpx

# ---------------------------------------------------------------------------
# Optional LiteLLM import — only needed for the litellm_completion() helper.
# ---------------------------------------------------------------------------
try:
    import litellm as _litellm
    _LITELLM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _litellm = None  # type: ignore[assignment]
    _LITELLM_AVAILABLE = False

log = logging.getLogger("sylion.ollama_client")

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
def _resolve_ollama_base_url(raw_url: str) -> str:
    """CONN-001: Resolve Ollama base URL with DNS fallback.

    If the hostname in ``raw_url`` cannot be resolved via DNS (e.g. a Docker
    alias like ``ollama`` on a machine where the container is not running),
    fall back to ``localhost`` on the same port/scheme so that a local
    daemon is still reachable. This prevents NXDOMAIN crashes when the
    environment is only partially configured (common on first-run / dev).

    Guarantees:
    * Never raises — on any error, returns ``raw_url`` unchanged.
    * Pure function, no side effects beyond DNS lookup + debug log.
    * Opt-out via env ``SYLION_OLLAMA_DNS_FALLBACK=0`` (default: enabled).
    """
    if os.getenv("SYLION_OLLAMA_DNS_FALLBACK", "1") == "0":
        return raw_url
    try:
        parsed = urlparse(raw_url)
        host = parsed.hostname
        if not host or host in ("localhost", "127.0.0.1", "::1"):
            return raw_url
        try:
            socket.gethostbyname(host)
            return raw_url
        except (socket.gaierror, OSError) as dns_err:
            port = parsed.port or 11434
            new_netloc = f"localhost:{port}"
            fallback = urlunparse(parsed._replace(netloc=new_netloc))
            log.warning(
                "CONN-001 DNS fallback: host=%r not resolvable (%s) → using %s",
                host, dns_err, fallback,
            )
            return fallback
    except Exception as exc:  # noqa: BLE001 — pure safety net
        log.debug("CONN-001 resolve failed (%s); keeping raw url=%s", exc, raw_url)
        return raw_url


_DEFAULT_BASE_URL: str = _resolve_ollama_base_url(
    os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
)
_DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# Circuit breaker thresholds
_CB_FAILURE_THRESHOLD: int = 3      # consecutive failures before opening
_CB_RECOVERY_TIMEOUT_S: float = 30.0  # seconds to wait before half-open probe
_CB_HALF_OPEN_MAX: int = 1          # requests allowed in half-open state

# Warmup / benchmark
_WARMUP_PROMPT: str = "Respond with exactly the word: ready"
_BENCHMARK_PROMPT: str = (
    "List 20 Python best practices for writing clean, maintainable code. "
    "Be concise but complete."
)
_BENCHMARK_REPEAT: int = 3          # average over N runs

# Health check
_HEALTH_TIMEOUT_S: float = 5.0      # hard cap for /api/tags probe
_VRAM_WARN_THRESHOLD_GB: float = 1.0  # warn if free VRAM below this


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "closed"       # normal operation
    OPEN = "open"           # daemon is down — route to cloud
    HALF_OPEN = "half_open" # probing after recovery timeout


@dataclass
class HealthResult:
    """Result of OllamaClient.health()."""
    online: bool
    base_url: str
    models: list[str] = field(default_factory=list)
    latency_ms: int = 0
    vram_free_gb: Optional[float] = None    # None if not available
    vram_total_gb: Optional[float] = None
    error: str = ""

    @property
    def has_model(self) -> Callable[[str], bool]:
        """Returns a closure: health.has_model("llama3")."""
        def _check(model_name: str) -> bool:
            return any(model_name in m for m in self.models)
        return _check


@dataclass
class ChatResponse:
    """Parsed response from /api/chat."""
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    done: bool = True


@dataclass
class BenchmarkResult:
    """Result of OllamaClient.benchmark()."""
    model: str
    tokens_per_sec: float
    latency_ms_avg: float
    latency_ms_p95: float
    runs: int
    error: str = ""


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------

class CircuitOpen(RuntimeError):
    """Raised when the circuit breaker is OPEN and no fallback is configured."""
    pass


class OllamaError(RuntimeError):
    """Raised on non-recoverable Ollama API errors."""
    pass


# ---------------------------------------------------------------------------
# Circuit Breaker (minimal, thread-safe via asyncio.Lock)
# ---------------------------------------------------------------------------

class _CircuitBreaker:
    """
    Three-state circuit breaker:
      CLOSED   → OPEN after `failure_threshold` consecutive failures
      OPEN     → HALF_OPEN after `recovery_timeout` seconds
      HALF_OPEN → CLOSED on success / OPEN on failure
    """

    def __init__(
        self,
        failure_threshold: int = _CB_FAILURE_THRESHOLD,
        recovery_timeout: float = _CB_RECOVERY_TIMEOUT_S,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float = 0.0
        self._half_open_count = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def before_call(self) -> None:
        """Call before every Ollama request. Raises CircuitOpen if blocked."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.recovery_timeout:
                    log.info(
                        "circuit breaker: OPEN → HALF_OPEN (%.1f s elapsed)", elapsed
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_count = 0
                else:
                    raise CircuitOpen(
                        f"Ollama circuit OPEN — retrying in "
                        f"{self.recovery_timeout - elapsed:.0f}s"
                    )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_count >= _CB_HALF_OPEN_MAX:
                    raise CircuitOpen("Ollama circuit HALF_OPEN — probe already in flight")
                self._half_open_count += 1

    async def on_success(self) -> None:
        async with self._lock:
            if self._state != CircuitState.CLOSED:
                log.info("circuit breaker: %s → CLOSED", self._state)
            self._state = CircuitState.CLOSED
            self._failures = 0

    async def on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failures += 1
            log.warning(
                "circuit breaker: failure #%d (%s: %s)",
                self._failures, type(exc).__name__, exc,
            )
            if self._state == CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                log.error(
                    "circuit breaker: → OPEN (will probe after %.0f s)",
                    self.recovery_timeout,
                )


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------

class OllamaClient:
    """
    Async HTTP client for Ollama with circuit breaker, warmup, and benchmark.

    Parameters
    ----------
    base_url:
        Ollama base URL (default: $OLLAMA_API_BASE or http://localhost:11434).
    timeout:
        Default request timeout in seconds for chat calls.
    failure_threshold:
        Circuit breaker opens after this many consecutive failures.
    recovery_timeout:
        Seconds to wait before probing after circuit opens.
    fallback_fn:
        Optional async callable invoked when circuit is OPEN.
        Signature: ``async (model, messages, **kwargs) -> ChatResponse``
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 120.0,
        failure_threshold: int = _CB_FAILURE_THRESHOLD,
        recovery_timeout: float = _CB_RECOVERY_TIMEOUT_S,
        fallback_fn: Optional[
            Callable[..., Coroutine[Any, Any, ChatResponse]]
        ] = None,
    ) -> None:
        # CONN-001: apply DNS fallback also on user-provided base_url
        self.base_url = _resolve_ollama_base_url(base_url).rstrip("/")
        self.timeout = timeout
        self.fallback_fn = fallback_fn
        self._cb = _CircuitBreaker(failure_threshold, recovery_timeout)
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _client(self) -> httpx.AsyncClient:
        """Lazily create and reuse a single AsyncClient per OllamaClient instance."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._http

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def health(self, timeout: float = _HEALTH_TIMEOUT_S) -> HealthResult:
        """
        Probe the Ollama daemon.

        Returns a HealthResult with:
        - online: bool
        - models: list of installed model names
        - latency_ms: round-trip time for /api/tags
        - vram_free_gb / vram_total_gb: parsed from /api/ps if available
        - error: human-readable error if offline

        Does NOT affect the circuit breaker state.
        """
        t0 = time.monotonic()
        result = HealthResult(online=False, base_url=self.base_url)
        http = await self._client()

        # --- Step 1: check daemon + installed models ---
        try:
            resp = await http.get("/api/tags", timeout=timeout)
            result.latency_ms = int((time.monotonic() - t0) * 1000)
            resp.raise_for_status()
            payload = resp.json()
            result.models = [
                m.get("name", "") if isinstance(m, dict) else str(m)
                for m in payload.get("models", [])
            ]
            result.online = True
        except Exception as exc:
            result.error = f"Ollama health check failed: {exc}"
            log.warning("ollama health: %s", result.error)
            return result

        # --- Step 2: VRAM check via /api/ps (Ollama ≥0.1.38) ---
        # SYL-OLLAMA-VRAM-01: guard against dispatch to an OOM'd daemon.
        try:
            ps_resp = await http.get("/api/ps", timeout=timeout)
            if ps_resp.status_code == 200:
                ps_data = ps_resp.json()
                # /api/ps returns running models; sum their size_vram fields
                # to estimate used VRAM. Total VRAM comes from the first model's
                # `details` block if exposed (varies by Ollama version).
                total_vram: Optional[float] = None
                used_vram: float = 0.0
                for m in ps_data.get("models", []):
                    used_vram += (m.get("size_vram", 0) or 0)
                    if total_vram is None and m.get("details", {}).get("total_vram"):
                        total_vram = m["details"]["total_vram"] / 1024**3
                result.vram_free_gb = (
                    (total_vram - used_vram / 1024**3)
                    if total_vram is not None
                    else None
                )
                result.vram_total_gb = total_vram

                if (
                    result.vram_free_gb is not None
                    and result.vram_free_gb < _VRAM_WARN_THRESHOLD_GB
                ):
                    log.warning(
                        "SYL-OLLAMA-VRAM-01: free VRAM %.2f GB < threshold %.2f GB — "
                        "large model calls may fail with OOM",
                        result.vram_free_gb,
                        _VRAM_WARN_THRESHOLD_GB,
                    )
        except Exception:
            pass  # /api/ps is optional; do not fail health check

        log.info(
            "ollama health: online=True models=%d latency=%d ms vram_free=%s GB",
            len(result.models),
            result.latency_ms,
            f"{result.vram_free_gb:.1f}" if result.vram_free_gb is not None else "n/a",
        )
        return result

    async def warmup(self, model: str = _DEFAULT_MODEL) -> bool:
        """
        Preload the model weights into VRAM by sending a minimal dummy prompt.

        Ollama loads model weights on the first inference call, which can
        take 8–15 seconds (cold start). Calling warmup() during pipeline
        startup hides this latency from the first real audit request.

        SYL-OLLAMA-WARMUP-01: call once per model per process startup.

        Returns True if warmup completed successfully, False otherwise.
        """
        log.info("ollama warmup: loading model=%s into VRAM …", model)
        t0 = time.monotonic()
        try:
            await self._cb.before_call()
            http = await self._client()
            resp = await http.post(
                "/api/generate",
                json={
                    "model": model,
                    "prompt": _WARMUP_PROMPT,
                    "stream": False,
                    "options": {"num_predict": 5, "temperature": 0},
                },
                timeout=60.0,  # warmup may take 20-30s on first cold start
            )
            resp.raise_for_status()
            elapsed = time.monotonic() - t0
            await self._cb.on_success()
            log.info("ollama warmup: done in %.1f s (model=%s)", elapsed, model)
            return True
        except CircuitOpen as exc:
            log.warning("ollama warmup skipped — circuit OPEN: %s", exc)
            return False
        except Exception as exc:
            await self._cb.on_failure(exc)
            log.error("ollama warmup failed: %s", exc)
            return False

    async def chat(
        self,
        model: str = _DEFAULT_MODEL,
        messages: Optional[list[dict[str, str]]] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 0.1,
        num_ctx: int = 8192,
        num_predict: int = 4096,
        stream: bool = False,
        **extra_options: Any,
    ) -> ChatResponse:
        """
        Send a chat request to Ollama.

        Interface is compatible with LiteLLM's ``/chat/completions`` shape:
        - messages: list of ``{"role": "user"|"assistant"|"system", "content": "..."}``
        - tools: list of function-call tool specs (Ollama ≥0.3 required).

        Circuit breaker
        ---------------
        If the circuit is OPEN and ``self.fallback_fn`` is set, the fallback
        is invoked transparently. If no fallback is configured, raises
        ``CircuitOpen``.

        Parameters
        ----------
        model:
            Ollama model name, e.g. "llama3" or "llama3:70b".
        messages:
            OpenAI-style message list.
        tools:
            Optional OpenAI function-call tools (Ollama ≥0.3).
        temperature:
            Sampling temperature (0.1 for deterministic audit use).
        num_ctx:
            Context window size. Keep ≤8192 for 8 GB VRAM; 131072 needs ≥16 GB.
        num_predict:
            Max output tokens.
        stream:
            If True, return first chunk only (streaming not fully implemented here).
        """
        if messages is None:
            messages = []

        try:
            await self._cb.before_call()
        except CircuitOpen:
            if self.fallback_fn:
                log.warning("ollama circuit OPEN — invoking fallback for model=%s", model)
                return await self.fallback_fn(model=model, messages=messages, tools=tools)
            raise

        t0 = time.monotonic()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                **extra_options,
            },
        }
        if tools:
            payload["tools"] = tools

        try:
            http = await self._client()
            resp = await http.post("/api/chat", json=payload)
            latency_ms = int((time.monotonic() - t0) * 1000)
            resp.raise_for_status()
            data = resp.json()

            content = ""
            msg = data.get("message", {})
            if isinstance(msg, dict):
                content = msg.get("content", "")

            # Ollama token usage in eval_count / prompt_eval_count
            tokens_out = data.get("eval_count", 0) or 0
            tokens_in = data.get("prompt_eval_count", 0) or 0

            await self._cb.on_success()
            log.debug(
                "ollama chat: model=%s tokens_in=%d tokens_out=%d latency=%d ms",
                model, tokens_in, tokens_out, latency_ms,
            )
            return ChatResponse(
                content=content,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                done=data.get("done", True),
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            await self._cb.on_failure(exc)
            if self.fallback_fn:
                log.warning("ollama call failed (%s) — invoking fallback", exc)
                return await self.fallback_fn(model=model, messages=messages, tools=tools)
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        except httpx.HTTPStatusError as exc:
            # 5xx → circuit breaker; 4xx → caller error, no CB penalty
            if exc.response.status_code >= 500:
                await self._cb.on_failure(exc)
            if self.fallback_fn and exc.response.status_code >= 500:
                return await self.fallback_fn(model=model, messages=messages, tools=tools)
            raise OllamaError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc

    async def benchmark(
        self,
        model: str = _DEFAULT_MODEL,
        prompt: str = _BENCHMARK_PROMPT,
        repeat: int = _BENCHMARK_REPEAT,
    ) -> BenchmarkResult:
        """
        Measure inference throughput (tokens/sec) for FinOps tier routing.

        Sends `repeat` identical prompts, measures eval_duration per run,
        returns average and P95 latency.

        SYL-OLLAMA-BENCH-01: run after warmup so weights are already in VRAM.
        Expected baseline: llama3 8B ≈ 35–80 tok/s on RTX 3090.

        Parameters
        ----------
        model:
            Ollama model name to benchmark.
        prompt:
            Benchmark payload (default: ~200 token code explanation).
        repeat:
            Number of measurement runs (default 3).
        """
        log.info("ollama benchmark: model=%s runs=%d …", model, repeat)

        latencies: list[float] = []
        toks_per_sec_list: list[float] = []

        for i in range(repeat):
            t0 = time.monotonic()
            try:
                http = await self._client()
                resp = await http.post(
                    "/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0, "num_predict": 200},
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
            except Exception as exc:
                log.error("ollama benchmark run %d failed: %s", i + 1, exc)
                return BenchmarkResult(
                    model=model,
                    tokens_per_sec=0.0,
                    latency_ms_avg=0.0,
                    latency_ms_p95=0.0,
                    runs=i,
                    error=str(exc),
                )

            elapsed_ms = (time.monotonic() - t0) * 1000
            data = resp.json()

            # eval_count = output tokens, eval_duration = nanoseconds
            eval_tokens: int = data.get("eval_count", 0) or 0
            eval_ns: int = data.get("eval_duration", 0) or 0

            if eval_tokens > 0 and eval_ns > 0:
                tps = eval_tokens / (eval_ns / 1e9)
                toks_per_sec_list.append(tps)
            latencies.append(elapsed_ms)
            log.debug(
                "benchmark run %d: %.1f tok/s, %.0f ms total", i + 1,
                toks_per_sec_list[-1] if toks_per_sec_list else 0,
                elapsed_ms,
            )

        if not latencies:
            return BenchmarkResult(
                model=model, tokens_per_sec=0.0,
                latency_ms_avg=0.0, latency_ms_p95=0.0, runs=0,
                error="no successful runs",
            )

        sorted_lat = sorted(latencies)
        p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
        avg_tps = sum(toks_per_sec_list) / len(toks_per_sec_list) if toks_per_sec_list else 0.0

        result = BenchmarkResult(
            model=model,
            tokens_per_sec=round(avg_tps, 1),
            latency_ms_avg=round(sum(latencies) / len(latencies), 1),
            latency_ms_p95=round(sorted_lat[p95_idx], 1),
            runs=len(latencies),
        )
        log.info(
            "ollama benchmark: model=%s avg=%.1f tok/s p95=%.0f ms",
            model, result.tokens_per_sec, result.latency_ms_p95,
        )
        return result

    # ------------------------------------------------------------------
    # LiteLLM bridge
    # ------------------------------------------------------------------

    async def litellm_completion(
        self,
        model: str = _DEFAULT_MODEL,
        messages: Optional[list[dict]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Call Ollama via LiteLLM's ollama_chat provider.

        This bridges the pipeline's existing LiteLLM call-sites to Ollama
        without changing their interface. LiteLLM translates
        ``ollama_chat/<model>`` to Ollama's /api/chat endpoint.

        Example::

            response = await client.litellm_completion(
                model="llama3",
                messages=[{"role": "user", "content": "Hello"}],
            )
            print(response.choices[0].message.content)

        Raises ImportError if litellm is not installed.
        Raises CircuitOpen if the circuit breaker is OPEN.
        """
        if not _LITELLM_AVAILABLE:
            raise ImportError(
                "litellm is required for litellm_completion(). "
                "Install with: pip install litellm"
            )

        try:
            await self._cb.before_call()
        except CircuitOpen:
            if self.fallback_fn:
                log.warning("ollama circuit OPEN in litellm_completion — fallback")
                return await self.fallback_fn(
                    model=model, messages=messages or [], **kwargs
                )
            raise

        t0 = time.monotonic()
        try:
            response = await asyncio.to_thread(
                _litellm.completion,
                model=f"ollama_chat/{model}",
                messages=messages or [],
                api_base=self.base_url,
                **kwargs,
            )
            await self._cb.on_success()
            log.debug(
                "litellm_completion: model=%s latency=%.0f ms",
                model, (time.monotonic() - t0) * 1000,
            )
            return response
        except Exception as exc:
            # LiteLLM wraps connection errors; treat all as CB-eligible
            await self._cb.on_failure(exc)
            if self.fallback_fn:
                return await self.fallback_fn(
                    model=model, messages=messages or [], **kwargs
                )
            raise

    # ------------------------------------------------------------------
    # Convenience: circuit breaker introspection
    # ------------------------------------------------------------------

    @property
    def circuit_state(self) -> CircuitState:
        """Current circuit breaker state."""
        return self._cb.state

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive failures tracked by the circuit breaker."""
        return self._cb._failures


# ---------------------------------------------------------------------------
# Module-level singleton — used by ai_review.py and ollama_local_learner
# ---------------------------------------------------------------------------

_DEFAULT_CLIENT: Optional[OllamaClient] = None


def get_default_client() -> OllamaClient:
    """
    Return the process-level singleton OllamaClient.

    Creates it on first call using $OLLAMA_API_BASE / $OLLAMA_MODEL.
    Fallback is not configured here — callers that need cloud fallback
    should construct OllamaClient(fallback_fn=...) directly.
    """
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = OllamaClient(base_url=_DEFAULT_BASE_URL)
    return _DEFAULT_CLIENT


# ---------------------------------------------------------------------------
# LiteLLM provider registration helper
# ---------------------------------------------------------------------------

def register_ollama_litellm_provider(
    base_url: str = _DEFAULT_BASE_URL,
    models: Optional[list[str]] = None,
) -> None:
    """
    Register Ollama as a LiteLLM custom provider so that any call to
    ``litellm.completion(model="ollama_chat/<model>", ...)`` routes to
    the local daemon at `base_url`.

    Call once at pipeline startup (before any LLM calls):

        from ollama_client import register_ollama_litellm_provider
        register_ollama_litellm_provider()

    This is a no-op if litellm is not installed.

    See: https://docs.litellm.ai/docs/providers/ollama
    """
    if not _LITELLM_AVAILABLE:
        log.warning(
            "register_ollama_litellm_provider: litellm not installed — skipped"
        )
        return

    # LiteLLM reads OLLAMA_API_BASE from env; we also set it programmatically.
    os.environ.setdefault("OLLAMA_API_BASE", base_url)

    # Optionally pre-configure model list for cost tracking
    if models:
        for m in models:
            model_key = f"ollama_chat/{m}"
            # Only set if not already configured (idempotent)
            if model_key not in (_litellm.model_cost or {}):
                _litellm.register_model({
                    model_key: {
                        "max_tokens": 131072,
                        "input_cost_per_token": 0.0,
                        "output_cost_per_token": 0.0,
                        "litellm_provider": "ollama_chat",
                        "mode": "chat",
                    }
                })

    log.info(
        "LiteLLM Ollama provider registered: base_url=%s models=%s",
        base_url, models or ["auto-detected"],
    )


# ---------------------------------------------------------------------------
# CLI smoke-test (python -m ollama_client health)
# ---------------------------------------------------------------------------

async def _cli_main() -> None:
    import json
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "health"
    model = sys.argv[2] if len(sys.argv) > 2 else _DEFAULT_MODEL

    client = OllamaClient()

    if cmd == "health":
        h = await client.health()
        print(json.dumps({
            "online": h.online,
            "base_url": h.base_url,
            "models": h.models,
            "latency_ms": h.latency_ms,
            "vram_free_gb": h.vram_free_gb,
            "vram_total_gb": h.vram_total_gb,
            "error": h.error,
        }, indent=2))

    elif cmd == "warmup":
        ok = await client.warmup(model)
        print(f"warmup {'OK' if ok else 'FAILED'}")

    elif cmd == "benchmark":
        b = await client.benchmark(model)
        print(json.dumps({
            "model": b.model,
            "tokens_per_sec": b.tokens_per_sec,
            "latency_ms_avg": b.latency_ms_avg,
            "latency_ms_p95": b.latency_ms_p95,
            "runs": b.runs,
            "error": b.error,
        }, indent=2))

    elif cmd == "chat":
        r = await client.chat(model=model, messages=[{"role": "user", "content": "Say: SYLION OK"}])
        print(r.content)

    else:
        print(f"Usage: python ollama_client.py [health|warmup|benchmark|chat] [model]")

    await client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_cli_main())
