"""W13 Advisor — Task-to-Role Suggester (PDF §8.3).

Operator definiuje task w plain Polish (np. "napisz książkę o SYLION"),
suggester analizuje typ output, skalę, etap i domain, a potem zwraca
**pipeline ról** z W7 Role Catalog z preferowanymi modelami z W11
Adapter Bus.

PDF §8.3:
    1. Operator definiuje task (np. "napisz książkę o SYLION")
    2. Advisor analizuje typ output, skala, etap, domain
    3. Sugeruje pipeline ról — np. researcher → strategist →
       ghostwriter → fact_checker → editor → final_reviewer
    4. Pokazuje jako AdvisorCard z HG: Akceptuj / Modyfikuj / Auto
    5. Każda rola w pipeline może być na innym hoście (federacja)

Phase 0 implementacja:

- Heurystyka keyword-based: mapowanie słów kluczowych task'u na
  kategorie W7 (text/code/visual/audio/strategy/research/...).
- Fallback do "balanced pipeline" (research → plan → execute → review)
  dla niejednoznacznych zadań.
- Brak LLM call — czysta deterministyczna heurystyka. G2 doda
  LLM-based reasoning warstwy (np. critic model decyduje czy heurystyka
  trafiona, czy potrzebny inny pipeline).

REST: ``POST /api/v1/advisor/suggest-pipeline``.
Wpinane przez ``advisor_routes.py`` osobnym sub-routerem.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Output types
# --------------------------------------------------------------------------


@dataclass
class PipelineStep:
    """Jeden krok w sugerowanym pipeline.

    Mapuje 1:1 na W7 rolę. Klient (frontend AdvisorCard) renderuje
    listę kroków ze szczegółami modelu i estymacją kosztu.
    """

    role_id: str
    rationale_pl: str
    preferred_model: str = ""
    fallback_model: str = ""
    cost_profile: str = "medium"      # low / medium / high
    estimated_minutes: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "rationale_pl": self.rationale_pl,
            "preferred_model": self.preferred_model,
            "fallback_model": self.fallback_model,
            "cost_profile": self.cost_profile,
            "estimated_minutes": self.estimated_minutes,
        }


@dataclass
class PipelineSuggestion:
    """Top-level wynik suggester'a.

    ``confidence`` służy do ekspozycji w UI (np. "Confidence 60% —
    sugeruję dokładnie sprawdzić skład pipeline'a").
    """

    task_summary: str
    detected_categories: list[str]
    detected_signals: list[str]
    steps: list[PipelineStep]
    confidence: float = 0.6
    estimated_total_minutes: int = 0
    estimated_total_cost_usd: float = 0.0
    notes_pl: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_summary": self.task_summary,
            "detected_categories": list(self.detected_categories),
            "detected_signals": list(self.detected_signals),
            "steps": [s.to_dict() for s in self.steps],
            "confidence": self.confidence,
            "estimated_total_minutes": self.estimated_total_minutes,
            "estimated_total_cost_usd": self.estimated_total_cost_usd,
            "notes_pl": list(self.notes_pl),
        }


# --------------------------------------------------------------------------
# Heuristic vocabulary
# --------------------------------------------------------------------------

# Keyword → (kategoria W7, signal label). Polski + angielski.
# Lower-case match. Word-boundary aware.
_KEYWORD_MAP: dict[str, tuple[str, str]] = {
    # text / writing
    "napisz": ("text", "writing"),
    "tekst": ("text", "writing"),
    "artykuł": ("text", "writing"),
    "blog": ("text", "writing"),
    "landing": ("text", "marketing"),
    "copy": ("text", "marketing"),
    "headline": ("text", "marketing"),
    "książka": ("text", "long_form"),
    "książki": ("text", "long_form"),
    "książke": ("text", "long_form"),
    "book": ("text", "long_form"),
    "rozdział": ("text", "long_form"),
    "tłumacz": ("text", "translation"),
    "translation": ("text", "translation"),
    "redagowanie": ("text", "editing"),
    "edycja": ("text", "editing"),
    "korekta": ("text", "editing"),
    "edit": ("text", "editing"),
    # code
    "code": ("code", "implementation"),
    "kod": ("code", "implementation"),
    "implementuj": ("code", "implementation"),
    "implement": ("code", "implementation"),
    "function": ("code", "implementation"),
    "funkcję": ("code", "implementation"),
    "refaktor": ("code", "refactor"),
    "refactor": ("code", "refactor"),
    "debug": ("code", "debug"),
    "test": ("code", "testing"),
    "tests": ("code", "testing"),
    "testy": ("code", "testing"),
    "security": ("code", "security_audit"),
    "audit": ("code", "security_audit"),
    "review": ("code", "review"),
    "review code": ("code", "review"),
    # visual
    "logo": ("visual", "branding"),
    "design": ("visual", "ui"),
    "ui": ("visual", "ui"),
    "ux": ("visual", "ui"),
    "ilustracja": ("visual", "illustration"),
    "ilustracje": ("visual", "illustration"),
    "illustration": ("visual", "illustration"),
    "graphic": ("visual", "graphic"),
    "grafika": ("visual", "graphic"),
    "zdjęcie": ("visual", "photo"),
    "photo": ("visual", "photo"),
    "image": ("visual", "photo"),
    "video": ("visual", "video"),
    "wideo": ("visual", "video"),
    # audio
    "muzyk": ("audio", "music"),
    "music": ("audio", "music"),
    "kompozycja": ("audio", "music"),
    "voiceover": ("audio", "voice"),
    "lektor": ("audio", "voice"),
    "transkry": ("audio", "transcription"),
    "transcript": ("audio", "transcription"),
    "podcast": ("audio", "podcast"),
    # strategy / research
    "strategia": ("strategy", "planning"),
    "strategy": ("strategy", "planning"),
    "plan": ("strategy", "planning"),
    "planuj": ("strategy", "planning"),
    "research": ("research", "investigation"),
    "badania": ("research", "investigation"),
    "analiza": ("research", "analysis"),
    "analyze": ("research", "analysis"),
    "analysis": ("research", "analysis"),
    "fakty": ("research", "fact_check"),
    "fact": ("research", "fact_check"),
    # mobile / web
    "ios": ("mobile", "ios"),
    "android": ("mobile", "android"),
    "react native": ("mobile", "react_native"),
    "frontend": ("web", "frontend"),
    "backend": ("web", "backend"),
    "fullstack": ("web", "fullstack"),
    "api": ("web", "backend"),
    "rest": ("web", "backend"),
    # domain
    "prawnik": ("domain", "legal"),
    "prawo": ("domain", "legal"),
    "lawyer": ("domain", "legal"),
    "umowa": ("domain", "legal"),
    "kontrakt": ("domain", "legal"),
    "księgowoś": ("domain", "accounting"),
    "accounting": ("domain", "accounting"),
    "podatki": ("domain", "accounting"),
    "marketing": ("domain", "marketing"),
    "sprzedaż": ("domain", "sales"),
    "sales": ("domain", "sales"),
    "wsparcie": ("domain", "customer_support"),
    "support": ("domain", "customer_support"),
    "naukowy": ("domain", "scientific"),
    "scientific": ("domain", "scientific"),
}

# Hint signals → favorite role pipeline (PDF §8.3 wymienia ten kanoniczny:
# researcher → strategist → ghostwriter → fact_checker → editor → final_reviewer).
_PIPELINE_TEMPLATES: dict[str, list[str]] = {
    "long_form": [
        "researcher", "strategist", "ghostwriter",
        "fact_checker", "editor", "technical_writer",
    ],
    "writing": [
        "researcher", "copywriter", "fact_checker", "editor",
    ],
    "marketing": [
        "researcher", "marketer", "copywriter", "editor",
    ],
    "translation": [
        "translator", "editor", "fact_checker",
    ],
    "editing": [
        "editor", "fact_checker",
    ],
    # code
    "implementation": [
        "researcher", "code_implementer", "test_writer", "code_reviewer",
    ],
    "refactor": [
        "code_reviewer", "refactorer", "test_writer", "code_reviewer",
    ],
    "debug": [
        "debugger", "test_writer", "code_reviewer",
    ],
    "testing": [
        "test_writer", "code_reviewer",
    ],
    "security_audit": [
        "security_auditor", "code_reviewer",
    ],
    "review": [
        "code_reviewer", "security_auditor",
    ],
    # visual
    "branding": ["graphic_designer", "ui_designer"],
    "ui": ["ui_designer", "graphic_designer"],
    "illustration": ["illustrator", "ui_designer"],
    "graphic": ["graphic_designer"],
    "photo": ["photo_editor"],
    "video": ["video_editor", "sound_designer"],
    # audio
    "music": ["composer"],
    "voice": ["voiceover_artist"],
    "transcription": ["transcriber", "editor"],
    "podcast": ["transcriber", "editor", "sound_designer"],
    # strategy / research
    "planning": ["researcher", "strategist", "planner", "project_manager"],
    "investigation": ["researcher", "fact_checker", "analyst"],
    "analysis": ["analyst", "researcher", "strategist"],
    "fact_check": ["fact_checker", "researcher"],
    # mobile / web
    "ios": ["ios_specialist", "code_reviewer", "test_writer"],
    "android": ["android_specialist", "code_reviewer", "test_writer"],
    "react_native": ["react_native_specialist", "code_reviewer", "test_writer"],
    "frontend": ["frontend_specialist", "code_reviewer", "test_writer"],
    "backend": ["backend_specialist", "code_reviewer", "test_writer", "security_auditor"],
    "fullstack": ["fullstack_implementer", "code_reviewer", "test_writer"],
    # domain
    "legal": ["lawyer", "researcher"],
    "accounting": ["accountant", "researcher"],
    "sales": ["sales", "marketer"],
    "customer_support": ["customer_support"],
    "scientific": ["scientist", "researcher", "fact_checker"],
}

# Default fallback gdy nic nie pasuje.
_DEFAULT_PIPELINE = ["researcher", "planner", "project_manager"]


# --------------------------------------------------------------------------
# Heuristic core
# --------------------------------------------------------------------------


def _detect_signals(task: str) -> tuple[list[str], list[str]]:
    """Lower-case scan task'u przez keyword map.

    Zwraca (categories, signals) — listy unique zachowane w kolejności
    pierwszego wystąpienia (deterministyczne).
    """
    text = task.lower()
    cats: list[str] = []
    sigs: list[str] = []
    for kw, (cat, sig) in _KEYWORD_MAP.items():
        # word-boundary aware (regex \b nie działa dla polskich znaków
        # w Pythonie 3.14 stabilnie — fallback to substring).
        if kw in text:
            if cat not in cats:
                cats.append(cat)
            if sig not in sigs:
                sigs.append(sig)
    return cats, sigs


def _pick_pipeline(signals: list[str]) -> tuple[list[str], str]:
    """Z signali wybierz template pipeline'a.

    Strategia:
    - Jeśli pojedynczy strong signal → użyj template'a tego signala.
    - Jeśli wiele → konkatenuj template'y w kolejności wykrycia,
      deduplikuj zachowując kolejność.
    - Jeśli brak → default pipeline.
    """
    if not signals:
        return list(_DEFAULT_PIPELINE), "fallback"
    seen: set[str] = set()
    out: list[str] = []
    for s in signals:
        for role_id in _PIPELINE_TEMPLATES.get(s, []):
            if role_id not in seen:
                seen.add(role_id)
                out.append(role_id)
    if not out:
        return list(_DEFAULT_PIPELINE), "fallback"
    return out, signals[0]  # primary signal


# --------------------------------------------------------------------------
# Role catalog integration
# --------------------------------------------------------------------------


def _load_role_catalog() -> dict[str, Any] | None:
    """Best-effort import katalogu W7. Zwraca None gdy nie zaintegrowany.

    Phase 0 może istnieć lub nie istnieć (W7 task w toku). Suggester
    działa nawet bez niego — degraduje gracefully do role_id-only output.
    """
    try:
        from sylion.skills.roles import ROLE_REGISTRY, get_role  # type: ignore
        return {"ROLE_REGISTRY": ROLE_REGISTRY, "get_role": get_role}
    except Exception as exc:
        log.debug("role_catalog niezaintegrowany: %s", exc)
        return None


def _augment_step(
    role_id: str,
    rationale_pl: str,
    catalog: dict[str, Any] | None,
    available_models: set[str] | None,
) -> PipelineStep:
    """Zbuduj krok z preferowanym modelem z W7 catalogue (gdy dostępny).

    Strategia wyboru modelu:
    1. preferred_models[0] jeśli w available_models.
    2. preferred_models[i] dla i>0 jeśli w available_models.
    3. fallback_models[0] jeśli w available_models.
    4. preferred_models[0] (operator zobaczy że niedostępny).
    """
    step = PipelineStep(role_id=role_id, rationale_pl=rationale_pl)
    if not catalog:
        return step
    role = catalog["get_role"](role_id)
    if role is None:
        step.rationale_pl += " (rola nieznana w W7 katalogu)"
        return step

    prefs = list(getattr(role, "preferred_models", []) or [])
    fbs = list(getattr(role, "fallback_models", []) or [])
    cost = getattr(role, "cost_profile", "medium")
    step.cost_profile = cost

    available = available_models or set()
    chosen = ""
    fallback = ""
    for m in prefs:
        if not available or m in available:
            chosen = m
            break
    if not chosen and prefs:
        chosen = prefs[0]
    for m in fbs:
        if m == chosen:
            continue
        if not available or m in available:
            fallback = m
            break
    if not fallback and fbs:
        fallback = fbs[0]

    step.preferred_model = chosen
    step.fallback_model = fallback
    return step


def _estimate_minutes(role_id: str, signal: str) -> int:
    """Bardzo zgrubna heurystyka czasu per krok, w minutach.

    long-form / scientific → 30 min, code review / writing → 10 min,
    fact_check / minor edit → 5 min.
    """
    long_roles = {
        "ghostwriter", "researcher", "scientist", "code_implementer",
        "fullstack_implementer", "ios_specialist", "android_specialist",
        "react_native_specialist", "frontend_specialist", "backend_specialist",
    }
    short_roles = {
        "fact_checker", "editor", "translator", "transcriber",
        "customer_support", "sales",
    }
    if role_id in long_roles:
        return 30
    if role_id in short_roles:
        return 5
    return 10


def _estimate_cost(step: PipelineStep) -> float:
    """Bardzo zgrubna heurystyka kosztu w USD per krok.

    Używa cost_profile + 1k tokens per minute (proxy).
    """
    rate = {"low": 0.005, "medium": 0.02, "high": 0.10}.get(step.cost_profile, 0.02)
    return round(rate * step.estimated_minutes, 4)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def suggest_pipeline(
    task: str,
    available_models: list[str] | None = None,
) -> PipelineSuggestion:
    """Sugeruj pipeline ról dla podanego task'u.

    Args:
        task: Polski lub angielski opis zadania (>= 3 znaki).
        available_models: Lista dostępnych model_id (z W11 + W17). Gdy
            None, suggester nie filtruje preferred_models.

    Returns:
        ``PipelineSuggestion`` z listą ``steps`` w kolejności wykonania.
    """
    task_clean = (task or "").strip()
    if len(task_clean) < 3:
        return PipelineSuggestion(
            task_summary=task_clean,
            detected_categories=[],
            detected_signals=[],
            steps=[],
            confidence=0.0,
            notes_pl=["Task za krotki — nie da sie heurystycznie sugerowac pipeline'a."],
        )

    cats, sigs = _detect_signals(task_clean)
    role_ids, primary_signal = _pick_pipeline(sigs)
    catalog = _load_role_catalog()
    avail = set(available_models or [])

    steps: list[PipelineStep] = []
    for rid in role_ids:
        rationale = f"Krok zidentyfikowany przez signal '{primary_signal}'."
        step = _augment_step(rid, rationale, catalog, avail)
        step.estimated_minutes = _estimate_minutes(rid, primary_signal)
        steps.append(step)

    total_minutes = sum(s.estimated_minutes for s in steps)
    total_cost = round(sum(_estimate_cost(s) for s in steps), 4)

    # Confidence: 0.6 base, +0.1 per matched signal, capped at 0.95.
    # 0 detected signals → 0.3 (default fallback used, low confidence).
    if not sigs:
        confidence = 0.3
    else:
        confidence = min(0.95, 0.5 + 0.1 * len(sigs))

    notes: list[str] = []
    if catalog is None:
        notes.append(
            "W7 Role Catalog niezaintegrowany — kroki maja role_id ale brak "
            "preferowanego modelu i system_prompt."
        )
    if confidence < 0.5:
        notes.append(
            "Confidence ponizej 50% — sugeruje recznie zweryfikowac sklad pipeline'a "
            "(/diff sessions po wykonaniu zeby porownac alternatywy)."
        )
    if avail:
        unavailable = [s.preferred_model for s in steps if s.preferred_model and s.preferred_model not in avail]
        if unavailable:
            notes.append(
                f"Niedostepne preferred_models: {', '.join(sorted(set(unavailable)))} "
                "— pipeline uzyje fallback."
            )

    return PipelineSuggestion(
        task_summary=task_clean[:200],
        detected_categories=cats,
        detected_signals=sigs,
        steps=steps,
        confidence=round(confidence, 2),
        estimated_total_minutes=total_minutes,
        estimated_total_cost_usd=total_cost,
        notes_pl=notes,
    )
