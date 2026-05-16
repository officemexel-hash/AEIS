"""W16 G2 — LLM-generated AppTemplate.

Sprint 3 deliverable. The W16 G1 cascade (Phase 0 tag-overlap → G1 step
2 embeddings refinement → G1 step 3 Council Hybrid wedge) handles the
case where the operator's idea matches an existing demo template.

When *no* demo template fits well (every G1 score < ``no_match_threshold``),
G2 takes over: it asks an LLM (Ollama by default) to generate a fresh
``AppTemplate`` from scratch.

The generator is a thin wrapper around ``ollama run`` — per the user's
directive *"wykorzystuj maksymalnie lokalne modele bo są tanie"* we
keep the heavy text generation on the free local GPU and reserve the
cloud model budget for adversarial review (Kimi) and small Python
helpers (Codex).

Public API:

    LlmTemplateGenerator(model="gpt-oss:20b", timeout_s=30.0)
        .generate(idea_text) -> AppTemplate | None

    should_invoke_g2(matches, threshold=0.4) -> bool

Audit emission goes through ``append_to_chain`` to
``logs/v2/g2_template_gen.jsonl`` so each generation attempt (success
or fallback) leaves a tamper-evident trail.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sylion.aeis_v2.apps_v2 import DEMO_TEMPLATES, AppTemplate, MatchResult

log = logging.getLogger(__name__)

#: Default Ollama model — matches ADR-002 (multi-model routing matrix).
DEFAULT_MODEL: str = "gpt-oss:20b"

#: Subprocess timeout — generous enough for cold-start GPU load.
DEFAULT_TIMEOUT_S: float = 30.0

#: G1 score below which we trigger G2 generation. Per W16 charter §4
#: this is a tunable; 0.4 matches the W16 G1 step 3 (Council wedge)
#: ``conditional`` floor.
DEFAULT_NO_MATCH_THRESHOLD: float = 0.4

#: Audit JSONL path (chained).
G2_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "g2_template_gen.jsonl"
)

#: Prompt template — instructs Ollama to return strict JSON.
_PROMPT_TEMPLATE = """Wygeneruj JSON dla AppTemplate dla pomyslu uzytkownika.

Wymagany format (BEZ dodatkowych komentarzy, czysty JSON):
{
  "id": "<snake_case_id, max 30 znakow>",
  "name_pl": "<polska nazwa, max 60 znakow>",
  "description_pl": "<polski opis, 50-200 znakow>",
  "object_type_ids": ["<id1>", "<id2>", "<id3>"],
  "widget_ids": ["<widget1>", "<widget2>", "<widget3>"],
  "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"]
}

object_type_ids do wyboru: customer, project, task, idea, contract, invoice, asset, document, employee
widget_ids do wyboru: ObjectListView, ObjectFormEditor, ChartWidget, AlertBanner, KpiCard, CommandButton, TabsWidget, DateRangePicker, MapWidget, MetricCard

Pomysl uzytkownika: {idea_text}

Odpowiedz tylko czystym JSON:
"""


@dataclass(frozen=True, slots=True)
class GenerationOutcome:
    """Result of a single G2 invocation."""

    succeeded: bool
    template: AppTemplate | None
    error: str | None
    elapsed_ms: float
    model: str
    fallback_used: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "template": self.template.to_dict() if self.template else None,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "model": self.model,
            "fallback_used": self.fallback_used,
        }


def should_invoke_g2(
    matches: Iterable[MatchResult],
    *,
    threshold: float = DEFAULT_NO_MATCH_THRESHOLD,
) -> bool:
    """Return ``True`` when no G1 match clears the threshold.

    The G1 cascade hands off to G2 only when the best match scored
    below the no-match floor — i.e. the user's idea doesn't fit any
    existing demo template.
    """
    best = -1.0
    for m in matches:
        if m.score > best:
            best = m.score
    return best < threshold


def _fallback_template() -> AppTemplate:
    """Used when Ollama is unreachable or returns garbage."""
    return DEMO_TEMPLATES[0]  # ``inspection_field`` is the safest catch-all


_JSON_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def _extract_json(stdout: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of an Ollama stdout dump.

    Ollama sometimes prefixes/suffixes the JSON with chatter; we tolerate
    that by greedily matching the first ``{...}`` block.
    """
    if not stdout:
        return None
    match = _JSON_RE.search(stdout)
    if not match:
        return None
    try:
        d = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    return d


def _validate_template_dict(d: dict[str, Any]) -> tuple[bool, list[str]]:
    """Required-key + bounds validation. Mirrors codex h3 helper contract."""
    errors: list[str] = []

    def _str_ok(key: str, max_len: int) -> None:
        v = d.get(key)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"{key}: must be non-empty str")
        elif len(v) > max_len:
            errors.append(f"{key}: too long ({len(v)} > {max_len})")

    _str_ok("id", 30)
    _str_ok("name_pl", 60)
    desc = d.get("description_pl")
    if not isinstance(desc, str) or not (
        50 <= len(desc.strip()) <= 200
    ):
        errors.append("description_pl: must be 50-200 chars")

    def _list_ok(key: str, min_len: int, max_len: int) -> None:
        v = d.get(key)
        if not isinstance(v, list):
            errors.append(f"{key}: must be list")
            return
        if not all(isinstance(x, str) and x.strip() for x in v):
            errors.append(f"{key}: every element must be non-empty str")
            return
        if not (min_len <= len(v) <= max_len):
            errors.append(
                f"{key}: length {len(v)} not in [{min_len}, {max_len}]",
            )

    _list_ok("object_type_ids", 3, 5)
    _list_ok("widget_ids", 3, 5)
    _list_ok("tags", 5, 8)

    return (not errors, errors)


def _emit_audit(payload: dict[str, Any]) -> None:
    try:
        from sylion.aeis_v2.audit_chain import append_to_chain

        append_to_chain(G2_AUDIT_LOG_PATH, payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("g2_template_gen: audit emit failed (%s)", exc)


class LlmTemplateGenerator:
    """Generate a fresh AppTemplate via Ollama (or any compatible CLI).

    The class is intentionally simple: one method, one subprocess call,
    one fallback path. Callers instantiate per use; there is no
    process-wide singleton.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        ollama_binary: str = "ollama",
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._model = model
        self._timeout_s = timeout_s
        self._ollama_binary = ollama_binary

    @property
    def model(self) -> str:
        return self._model

    def _build_prompt(self, idea_text: str) -> str:
        return _PROMPT_TEMPLATE.replace("{idea_text}", idea_text)

    def _invoke_ollama(self, prompt: str) -> tuple[str, str | None]:
        """Run ``ollama run <model> <prompt>`` and return (stdout, error)."""
        try:
            r = subprocess.run(
                [self._ollama_binary, "run", self._model, prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
        except FileNotFoundError:
            return ("", "ollama_binary_not_found")
        except subprocess.TimeoutExpired:
            return ("", "subprocess_timeout")
        except Exception as exc:  # noqa: BLE001 — fail-closed
            return ("", f"subprocess_error: {type(exc).__name__}")

        if r.returncode != 0:
            return ("", f"ollama_returncode: {r.returncode}")
        return (r.stdout or "", None)

    def generate(self, idea_text: str) -> GenerationOutcome:
        """Generate a fresh AppTemplate. Falls back to demo on any failure."""
        if not idea_text or not idea_text.strip():
            outcome = GenerationOutcome(
                succeeded=False, template=None,
                error="empty_idea_text", elapsed_ms=0.0,
                model=self._model, fallback_used=False,
            )
            _emit_audit({"kind": "g2_template_gen.attempt", **outcome.to_dict()})
            return outcome

        prompt = self._build_prompt(idea_text)
        start = time.perf_counter()
        stdout, err = self._invoke_ollama(prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Subprocess error path — fall back to demo.
        if err is not None:
            template = _fallback_template()
            outcome = GenerationOutcome(
                succeeded=False, template=template,
                error=err, elapsed_ms=elapsed_ms,
                model=self._model, fallback_used=True,
            )
            _emit_audit({
                "kind": "g2_template_gen.attempt",
                "idea_hash": _idea_hash(idea_text),
                **outcome.to_dict(),
            })
            return outcome

        # Parse + validate.
        d = _extract_json(stdout)
        if d is None:
            template = _fallback_template()
            outcome = GenerationOutcome(
                succeeded=False, template=template,
                error="json_parse_failed", elapsed_ms=elapsed_ms,
                model=self._model, fallback_used=True,
            )
            _emit_audit({
                "kind": "g2_template_gen.attempt",
                "idea_hash": _idea_hash(idea_text),
                "stdout_len": len(stdout),
                **outcome.to_dict(),
            })
            return outcome

        ok, errors = _validate_template_dict(d)
        if not ok:
            template = _fallback_template()
            outcome = GenerationOutcome(
                succeeded=False, template=template,
                error="validation_failed: " + "; ".join(errors),
                elapsed_ms=elapsed_ms,
                model=self._model, fallback_used=True,
            )
            _emit_audit({
                "kind": "g2_template_gen.attempt",
                "idea_hash": _idea_hash(idea_text),
                **outcome.to_dict(),
            })
            return outcome

        template = AppTemplate(
            id=d["id"],
            name_pl=d["name_pl"],
            description_pl=d["description_pl"],
            object_type_ids=list(d["object_type_ids"]),
            widget_ids=list(d["widget_ids"]),
            tags=list(d["tags"]),
        )
        outcome = GenerationOutcome(
            succeeded=True, template=template,
            error=None, elapsed_ms=elapsed_ms,
            model=self._model, fallback_used=False,
        )
        _emit_audit({
            "kind": "g2_template_gen.attempt",
            "idea_hash": _idea_hash(idea_text),
            **outcome.to_dict(),
        })
        return outcome


def _idea_hash(idea_text: str) -> str:
    """Stable 16-char hash for audit trace without leaking the idea text."""
    return hashlib.sha256(idea_text.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_NO_MATCH_THRESHOLD",
    "DEFAULT_TIMEOUT_S",
    "G2_AUDIT_LOG_PATH",
    "GenerationOutcome",
    "LlmTemplateGenerator",
    "should_invoke_g2",
]
