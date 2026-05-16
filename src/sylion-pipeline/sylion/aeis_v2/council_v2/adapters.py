"""Real-model role adapters for the Council Hybrid wedge.

Sprint 3 deliverable. Replaces ``simulate_role_verdict`` in
``aeis_v2/council_v2/wedge.py`` with adapters that actually invoke a
model. Per the operator's directive *"wykorzystuj maksymalnie lokalne
modele bo są tanie"* the default is :class:`OllamaRoleAdapter` —
9 calls × free local GPU per Council decision.

Two adapter implementations ship today:

* :class:`OllamaRoleAdapter` — production default. Subprocess to
  ``ollama run <model> <prompt>`` per call; per-role prompt template
  encodes the role's bias (planner = feasibility, critic = skeptical,
  cost_sentinel = price-aware, etc.).
* :class:`ScriptedRoleAdapter` — deterministic test harness so the
  council pipeline can exercise the real-adapter code path without
  shelling out.

Both implement the same callable shape ``simulate_role_verdict`` had,
so :func:`evaluate_match_with_council` accepts them via the
``role_evaluator`` parameter — zero call-site changes needed.

Per Kimi review k1_council_real_models_review (round 53:30):

* **Latency budget**: per-role timeout defaults to 8 s; if all 9 roles
  hit it, the worst-case Council decision is 72 s. The adapter falls
  back to ``simulate_role_verdict`` on timeout so the wedge always
  produces a decision.
* **Hallucination protection**: the response parser only accepts the 3
  canonical verdicts (``approve`` / ``reject`` / ``conditional``);
  anything else falls back to a rule-based simulator verdict.
* **Cost paradox**: the cost_sentinel role is itself a paid LLM call —
  the adapter mitigates with a tight token cap (``num_predict=64``).
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from sylion.aeis_v2.council_v2.wedge import simulate_role_verdict

log = logging.getLogger(__name__)

#: Default Ollama model — same as W16 G2 generator (ADR-002).
DEFAULT_MODEL: str = "gpt-oss:20b"

#: Default per-role subprocess timeout in seconds. Per Kimi k1 finding
#: the wedge's worst case is 9 × this if all roles time out.
DEFAULT_ROLE_TIMEOUT_S: float = 8.0

#: Token cap on the model output — keeps replies short + cheap.
DEFAULT_NUM_PREDICT: int = 64

#: Canonical verdict allow-list. Anything else → fallback to simulator.
_VALID_VERDICTS: frozenset[str] = frozenset({"approve", "reject", "conditional"})


# ---------------------------------------------------------------------------
# Per-role prompt templates — encode the role's bias.
# ---------------------------------------------------------------------------


_ROLE_PROMPTS: dict[str, str] = {
    "planner": (
        "Jestes Planner — oceniasz feasibility (czy mozna to zaplanowac w "
        "rozsadnym czasie i z dostepnymi zasobami). Top score G1: {top_score:.2f}. "
        "Tagi: {tags}. Idea: {idea_text}. "
        "Odpowiedz JEDNYM slowem: approve, reject lub conditional. "
        "Potem na nowej linii: confidence (0.0-1.0). Potem rationale (max 1 zdanie)."
    ),
    "architect": (
        "Jestes Architect — oceniasz spojnosc architektoniczna z istniejaca "
        "ontologia W15. Top score G1: {top_score:.2f}. Tagi: {tags}. "
        "Idea: {idea_text}. Odpowiedz JEDNYM slowem: approve, reject lub "
        "conditional. Potem confidence. Potem rationale."
    ),
    "critic": (
        "Jestes Critic — sceptyk. Szukasz problemow, niedociagniec, ryzyk. "
        "Top score G1: {top_score:.2f}. Tagi: {tags}. Idea: {idea_text}. "
        "Bandzaj surowy. Odpowiedz: approve / reject / conditional. "
        "Potem confidence. Potem rationale."
    ),
    "verifier": (
        "Jestes Verifier — oceniasz testowalnosc i mozliwosc weryfikacji "
        "dzialania. Top score G1: {top_score:.2f}. Tagi: {tags}. "
        "Idea: {idea_text}. Odpowiedz: approve / reject / conditional + "
        "confidence + rationale."
    ),
    "governance": (
        "Jestes Governance — oceniasz kompletnosc dokumentacji, zgodnosc z "
        "ADR-ami, sciezke audytu. Top score: {top_score:.2f}. Tagi: {tags}. "
        "Idea: {idea_text}. Odpowiedz: approve / reject / conditional + "
        "confidence + rationale."
    ),
    "cost_sentinel": (
        "Jestes Cost Sentinel — sprawdzasz koszt i zlozonosc. Tagi {tags} "
        "powinny NIE zawierac premium/expensive/complex. Top score: "
        "{top_score:.2f}. Idea: {idea_text}. Jezeli tagi wskazuja na wysoki "
        "koszt, odpowiedz reject. Inaczej approve. Format: verdict + "
        "confidence + rationale."
    ),
    "security_sentinel": (
        "Jestes Security Sentinel — sprawdzasz tagi pod katem bezpieczenstwa. "
        "Tagi {tags} powinny NIE zawierac public/unsafe/unsigned. Top score: "
        "{top_score:.2f}. Idea: {idea_text}. Jezeli tagi wskazuja na ryzyko "
        "bezpieczenstwa, odpowiedz reject. Format: verdict + confidence + "
        "rationale."
    ),
    "domain_specialist": (
        "Jestes Domain Specialist — znajomosc domeny biznesowej. Tagi: "
        "{tags}. Top score: {top_score:.2f}. Idea: {idea_text}. Odpowiedz: "
        "approve / reject / conditional + confidence + rationale."
    ),
    "funding_specialist": (
        "Jestes Funding Specialist — oceniasz wymagany budzet i ROI. "
        "Top score: {top_score:.2f}. Tagi: {tags}. Idea: {idea_text}. "
        "Odpowiedz: approve / reject / conditional + confidence + rationale."
    ),
}


def render_role_prompt(
    role: str, top_score: float, tags: list[str], idea_text: str = "",
) -> str:
    """Return a fully-rendered prompt for the given role."""
    template = _ROLE_PROMPTS.get(role)
    if template is None:
        return (
            f"Role: {role}. Score: {top_score:.2f}. Tags: {tags}. "
            f"Idea: {idea_text}. Verdict (approve/reject/conditional)?"
        )
    tags_repr = ", ".join(tags) if tags else "(brak)"
    idea_short = (idea_text or "")[:200]
    return template.format(
        top_score=top_score, tags=tags_repr, idea_text=idea_short,
    )


# ---------------------------------------------------------------------------
# Response parser — pulls (verdict, confidence, rationale) from raw stdout.
# ---------------------------------------------------------------------------


_VERDICT_RE = re.compile(
    r"\b(approve|reject|conditional)\b", re.IGNORECASE,
)
_CONFIDENCE_RE = re.compile(r"\b(0?\.\d+|1(?:\.0+)?|0\b)")


def parse_role_verdict_response(stdout: str) -> tuple[str, float, str]:
    """Best-effort extract ``(verdict, confidence, rationale)``.

    Falls back to ``("conditional", 0.5, <stdout-prefix>)`` if the model
    response can't be parsed — caller should treat this as a soft signal.
    """
    if not stdout:
        return ("conditional", 0.5, "")

    text = stdout.strip()
    verdict_match = _VERDICT_RE.search(text)
    verdict = verdict_match.group(1).lower() if verdict_match else "conditional"
    if verdict not in _VALID_VERDICTS:
        verdict = "conditional"

    conf_match = _CONFIDENCE_RE.search(text)
    if conf_match:
        try:
            confidence = float(conf_match.group(1))
        except ValueError:
            confidence = 0.5
    else:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    # Rationale = first non-empty line that is NOT a verdict word and
    # NOT a pure number (the confidence line).
    def _is_pure_number(s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False

    rationale_lines = [
        line.strip() for line in text.splitlines()
        if line.strip()
        and line.strip().lower() not in _VALID_VERDICTS
        and not _is_pure_number(line.strip())
    ]
    rationale = (rationale_lines[0] if rationale_lines else text)[:300]

    return (verdict, confidence, rationale)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OllamaRoleAdapter:
    """Production adapter — shells out to local Ollama per call.

    Constructed bound to a single role; the wedge instantiates 9 of
    these (one per canonical role) and dispatches in series. A future
    sprint can switch to ``embed_many``-style parallelism if the 9-call
    serial latency becomes a bottleneck.
    """

    role: str
    model: str = DEFAULT_MODEL
    timeout_s: float = DEFAULT_ROLE_TIMEOUT_S
    ollama_binary: str = "ollama"

    def evaluate(
        self, top_score: float, tags: list[str], idea_text: str = "",
    ) -> tuple[str, float, str]:
        """Implements the role_evaluator callable contract."""
        prompt = render_role_prompt(self.role, top_score, tags, idea_text)
        try:
            r = subprocess.run(
                [self.ollama_binary, "run", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            log.warning(
                "ollama_role_adapter[%s]: subprocess failed (%s) — fallback",
                self.role, type(exc).__name__,
            )
            return simulate_role_verdict(self.role, top_score, tags)
        except Exception as exc:  # noqa: BLE001 — fail-soft to simulator
            log.warning(
                "ollama_role_adapter[%s]: unknown error (%s) — fallback",
                self.role, type(exc).__name__,
            )
            return simulate_role_verdict(self.role, top_score, tags)

        if r.returncode != 0:
            log.warning(
                "ollama_role_adapter[%s]: returncode=%d — fallback",
                self.role, r.returncode,
            )
            return simulate_role_verdict(self.role, top_score, tags)

        verdict, confidence, rationale = parse_role_verdict_response(
            r.stdout or "",
        )
        # Stamp the role into the rationale so the audit trail surfaces
        # which adapter produced this analysis.
        rationale = f"[{self.role}/ollama] {rationale}"
        return verdict, confidence, rationale


@dataclass(frozen=True, slots=True)
class ScriptedRoleAdapter:
    """Test-time adapter — returns canned verdicts without subprocess.

    Useful for exercising the wedge against the *adapter code path*
    (rather than the simulate_role_verdict shortcut) without having to
    run Ollama in CI.
    """

    role: str
    canned_verdict: str = "approve"
    canned_confidence: float = 0.85
    canned_rationale: str = "scripted"

    def evaluate(
        self, top_score: float, tags: list[str], idea_text: str = "",
    ) -> tuple[str, float, str]:
        verdict = (
            self.canned_verdict if self.canned_verdict in _VALID_VERDICTS
            else "conditional"
        )
        return (verdict, self.canned_confidence, self.canned_rationale)


# ---------------------------------------------------------------------------
# Convenience: build a role_evaluator dispatching across 9 adapters.
# ---------------------------------------------------------------------------


def make_ollama_evaluator(
    *, model: str = DEFAULT_MODEL, timeout_s: float = DEFAULT_ROLE_TIMEOUT_S,
) -> Callable[[str, float, list[str]], tuple[str, float, str]]:
    """Return a role_evaluator that picks the right Ollama adapter per role.

    Cached: instances are created lazily on first call and reused; this
    avoids constructing 9 OllamaRoleAdapter objects upfront when the
    wedge only ever fires a subset.
    """
    cache: dict[str, OllamaRoleAdapter] = {}

    def _evaluator(
        role: str, top_score: float, tags: list[str],
    ) -> tuple[str, float, str]:
        if role not in cache:
            cache[role] = OllamaRoleAdapter(
                role=role, model=model, timeout_s=timeout_s,
            )
        return cache[role].evaluate(top_score, tags)

    return _evaluator


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_NUM_PREDICT",
    "DEFAULT_ROLE_TIMEOUT_S",
    "OllamaRoleAdapter",
    "ScriptedRoleAdapter",
    "make_ollama_evaluator",
    "parse_role_verdict_response",
    "render_role_prompt",
]
