"""W7 Role Catalog loader.

Loads all role manifests at import time and exposes:

- ``ROLE_REGISTRY``: ``dict[str, Role]``
- :func:`list_roles` — filter by category
- :func:`get_role` — fetch a specific role by id
- :func:`list_categories` — list category metadata from ``_index.yaml``
- :func:`match_role_to_task` — heuristic placeholder; the full Task-to-Role
  Suggester lives in W13.

Manifest source: ``sylion/skills/roles/<id>.yaml`` and the registry index
``sylion/skills/roles/_index.yaml``.

Schema reference: SYLION v2 PDF §8.2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

log = logging.getLogger("sylion.skills.roles")

_ROLES_DIR = Path(__file__).resolve().parent
_INDEX_FILE = _ROLES_DIR / "_index.yaml"


VALID_CATEGORIES = (
    "text",
    "code",
    "visual",
    "audio",
    "strategy",
    "mobile",
    "web",
    "domain",
    "research",
)
VALID_COST_PROFILES = ("low", "medium", "high")
VALID_SKILL_LEVELS = ("junior", "mid", "senior", "principal", "any")
DEFAULT_SKILL_LEVEL = "any"
# Order used for skill-level filtering ("senior" requires senior+).
_SKILL_LEVEL_RANK = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "principal": 4,
    "any": 0,
}


@dataclass(frozen=True)
class Role:
    """Single role manifest from ``sylion/skills/roles/<id>.yaml``.

    The capability/skill_level/required_tools/prerequisite_roles fields are
    the W7 Role Catalog Phase-0 extension (PDF §8.2 + W7 charter ext.). They
    default to empty/``"any"`` so legacy YAML manifests keep loading without
    edits.
    """

    id: str
    name_pl: str
    name_en: str
    category: str
    description_pl: str
    description_en: str
    preferred_capabilities: tuple[str, ...]
    preferred_models: tuple[str, ...]
    fallback_models: tuple[str, ...]
    typical_tasks: tuple[str, ...]
    cost_profile: str
    system_prompt: str
    source_file: str = ""
    capabilities: tuple[str, ...] = ()
    skill_level: str = DEFAULT_SKILL_LEVEL
    required_tools: tuple[str, ...] = ()
    prerequisite_roles: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (REST-friendly)."""
        return {
            "id": self.id,
            "name_pl": self.name_pl,
            "name_en": self.name_en,
            "category": self.category,
            "description_pl": self.description_pl,
            "description_en": self.description_en,
            "preferred_capabilities": list(self.preferred_capabilities),
            "preferred_models": list(self.preferred_models),
            "fallback_models": list(self.fallback_models),
            "typical_tasks": list(self.typical_tasks),
            "cost_profile": self.cost_profile,
            "system_prompt": self.system_prompt,
            "source_file": self.source_file,
            "capabilities": list(self.capabilities),
            "skill_level": self.skill_level,
            "required_tools": list(self.required_tools),
            "prerequisite_roles": list(self.prerequisite_roles),
        }

    def to_summary(self) -> dict[str, Any]:
        """Lightweight summary for list endpoints."""
        return {
            "id": self.id,
            "name_pl": self.name_pl,
            "name_en": self.name_en,
            "category": self.category,
            "cost_profile": self.cost_profile,
            "preferred_capabilities": list(self.preferred_capabilities),
            "capabilities": list(self.capabilities),
            "skill_level": self.skill_level,
        }


def _coerce_str_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    return ()


def _parse_role(payload: dict[str, Any], source_file: str) -> Role:
    """Build a Role from a parsed YAML dict; raises ValueError on schema issues."""
    required = (
        "id",
        "name_pl",
        "name_en",
        "category",
        "description_pl",
        "description_en",
        "system_prompt",
    )
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise ValueError(
            f"role manifest {source_file!r} missing required keys: {missing}"
        )

    category = str(payload["category"]).strip()
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"role {payload['id']!r} has invalid category {category!r} "
            f"(allowed: {VALID_CATEGORIES})"
        )

    cost_profile = str(payload.get("cost_profile", "medium")).strip().lower()
    if cost_profile not in VALID_COST_PROFILES:
        raise ValueError(
            f"role {payload['id']!r} has invalid cost_profile {cost_profile!r} "
            f"(allowed: {VALID_COST_PROFILES})"
        )

    skill_level_raw = payload.get("skill_level", DEFAULT_SKILL_LEVEL)
    skill_level = str(skill_level_raw or DEFAULT_SKILL_LEVEL).strip().lower()
    if skill_level not in VALID_SKILL_LEVELS:
        raise ValueError(
            f"role {payload['id']!r} has invalid skill_level {skill_level!r} "
            f"(allowed: {VALID_SKILL_LEVELS})"
        )

    return Role(
        id=str(payload["id"]).strip(),
        name_pl=str(payload["name_pl"]).strip(),
        name_en=str(payload["name_en"]).strip(),
        category=category,
        description_pl=str(payload["description_pl"]).strip(),
        description_en=str(payload["description_en"]).strip(),
        preferred_capabilities=_coerce_str_list(payload.get("preferred_capabilities")),
        preferred_models=_coerce_str_list(payload.get("preferred_models")),
        fallback_models=_coerce_str_list(payload.get("fallback_models")),
        typical_tasks=_coerce_str_list(payload.get("typical_tasks")),
        cost_profile=cost_profile,
        system_prompt=str(payload["system_prompt"]).strip(),
        source_file=source_file,
        capabilities=_coerce_str_list(payload.get("capabilities")),
        skill_level=skill_level,
        required_tools=_coerce_str_list(payload.get("required_tools")),
        prerequisite_roles=_coerce_str_list(payload.get("prerequisite_roles")),
    )


def _load_index() -> dict[str, Any]:
    if not _INDEX_FILE.exists():
        log.warning("role index file not found at %s", _INDEX_FILE)
        return {}
    try:
        return yaml.safe_load(_INDEX_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        log.error("failed to parse role index %s: %s", _INDEX_FILE, exc)
        return {}


def _load_role_file(filename: str) -> Role | None:
    path = _ROLES_DIR / filename
    if not path.exists():
        log.warning("role manifest file missing: %s", path)
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        log.error("failed to parse role manifest %s: %s", path, exc)
        return None
    if not isinstance(payload, dict):
        log.error("role manifest %s did not parse to a dict (got %s)", path, type(payload))
        return None
    try:
        return _parse_role(payload, source_file=filename)
    except ValueError as exc:
        log.error("schema error in %s: %s", filename, exc)
        return None


def _bootstrap_registry() -> tuple[dict[str, Role], dict[str, Any]]:
    """Read _index.yaml + every referenced manifest into a dict[str, Role]."""
    index = _load_index()
    registry: dict[str, Role] = {}

    role_entries = index.get("roles") if isinstance(index, dict) else None
    if not role_entries:
        # Fallback: scan directory for *.yaml (excluding _index.yaml).
        log.info("role index empty/missing — scanning directory")
        for path in sorted(_ROLES_DIR.glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            role = _load_role_file(path.name)
            if role:
                registry[role.id] = role
        return registry, index

    for entry in role_entries:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("file")
        if not filename:
            continue
        role = _load_role_file(filename)
        if role is None:
            continue
        if role.id in registry:
            log.warning("duplicate role id %r — overriding", role.id)
        registry[role.id] = role

    return registry, index


_REGISTRY, _INDEX_DATA = _bootstrap_registry()
ROLE_REGISTRY: dict[str, Role] = _REGISTRY


def get_role(role_id: str) -> Role | None:
    """Return a Role by id, or ``None`` if unknown."""
    if not role_id:
        return None
    return ROLE_REGISTRY.get(role_id.strip())


def list_roles(category: str | None = None) -> list[Role]:
    """List roles, optionally filtered by category.

    ``category`` is matched case-insensitively against ``Role.category``.
    """
    roles = list(ROLE_REGISTRY.values())
    if category:
        wanted = category.strip().lower()
        roles = [r for r in roles if r.category == wanted]
    return sorted(roles, key=lambda r: r.id)


def list_categories() -> list[dict[str, Any]]:
    """Return category metadata from ``_index.yaml``.

    Each entry: ``{"id": str, "label_pl": str, "label_en": str, "role_ids": list[str]}``.
    """
    raw = _INDEX_DATA.get("categories") if isinstance(_INDEX_DATA, dict) else None
    if not isinstance(raw, dict):
        return []
    out: list[dict[str, Any]] = []
    for cat_id, meta in raw.items():
        if not isinstance(meta, dict):
            continue
        out.append(
            {
                "id": str(cat_id),
                "label_pl": str(meta.get("label_pl", cat_id)),
                "label_en": str(meta.get("label_en", cat_id)),
                "role_ids": list(meta.get("role_ids") or []),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Heuristic Task-to-Role matcher (placeholder — full impl in W13).
# ---------------------------------------------------------------------------

# Keyword -> role_id hints.  Matched against the task description, lowercased.
# Multilingual: Polish + English on purpose.
_KEYWORD_HINTS: dict[str, tuple[str, ...]] = {
    # text
    "landing": ("copywriter",),
    "copy": ("copywriter",),
    "tekst marketing": ("copywriter",),
    "headline": ("copywriter",),
    "redak": ("editor",),
    "popraw styl": ("editor",),
    "weryfikuj": ("fact_checker",),
    "fakt": ("fact_checker",),
    "tlumacz": ("translator",),
    "translat": ("translator",),
    "ksiazk": ("ghostwriter", "researcher", "editor"),
    "book": ("ghostwriter", "researcher", "editor"),
    "ghostwrit": ("ghostwriter",),
    "readme": ("technical_writer",),
    "dokumentacj": ("technical_writer",),
    "tutorial": ("technical_writer",),
    "runbook": ("technical_writer",),
    # code
    "implementuj": ("code_implementer", "fullstack_implementer"),
    "implement ": ("code_implementer", "fullstack_implementer"),
    "endpoint": ("backend_specialist", "code_implementer"),
    "review": ("code_reviewer",),
    "refaktor": ("refactorer",),
    "refactor": ("refactorer",),
    "debug": ("debugger",),
    "bug": ("debugger",),
    "traceback": ("debugger",),
    "test": ("test_writer",),
    "audyt bezp": ("security_auditor",),
    "security": ("security_auditor",),
    "owasp": ("security_auditor",),
    "etl": ("data_engineer",),
    "data warehouse": ("data_engineer",),
    "dbt": ("data_engineer",),
    "ml model": ("ml_engineer",),
    "evaluation harness": ("ml_engineer",),
    "llm eval": ("ml_engineer",),
    # visual
    "logo": ("graphic_designer",),
    "brand": ("graphic_designer", "marketer"),
    "ilustracj": ("illustrator",),
    "illustration": ("illustrator",),
    "ui": ("ui_designer", "frontend_specialist"),
    "ux": ("ui_designer",),
    "zdjec": ("photo_editor",),
    "photo": ("photo_editor",),
    "wideo": ("video_editor",),
    "video": ("video_editor",),
    "montaz": ("video_editor",),
    # audio
    "muzyk": ("composer",),
    "music": ("composer",),
    "kompozytor": ("composer",),
    "sound": ("sound_designer",),
    "dzwiek": ("sound_designer",),
    "lektor": ("voiceover_artist",),
    "voiceover": ("voiceover_artist",),
    "transkry": ("transcriber",),
    "transcript": ("transcriber",),
    # strategy
    "research": ("researcher",),
    "konkuren": ("researcher", "strategist"),
    "competitor": ("researcher", "strategist"),
    "analiz": ("analyst",),
    "analyz": ("analyst",),
    "strategi": ("strategist",),
    "go-to-market": ("strategist", "marketer"),
    "harmonogram": ("planner",),
    "plan ": ("planner", "project_manager"),
    "gantt": ("planner",),
    "sprint": ("project_manager",),
    "stand-up": ("project_manager",),
    "status report": ("project_manager",),
    # mobile
    "ios": ("ios_specialist",),
    "swift": ("ios_specialist",),
    "android": ("android_specialist",),
    "kotlin": ("android_specialist",),
    "react native": ("react_native_specialist",),
    # web
    "frontend": ("frontend_specialist",),
    "react": ("frontend_specialist", "react_native_specialist"),
    "next.js": ("frontend_specialist",),
    "nextjs": ("frontend_specialist",),
    "tailwind": ("frontend_specialist",),
    "backend": ("backend_specialist",),
    "fastapi": ("backend_specialist",),
    "rest api": ("backend_specialist", "code_implementer"),
    "fullstack": ("fullstack_implementer",),
    # domain
    "umow": ("lawyer",),
    "contract": ("lawyer",),
    "rodo": ("lawyer",),
    "gdpr": ("lawyer",),
    "ksiegow": ("accountant",),
    "vat": ("accountant",),
    "podatk": ("accountant",),
    "naukow": ("scientist",),
    "experiment": ("scientist",),
    "eksperyment": ("scientist",),
    "marketing": ("marketer",),
    "kampani": ("marketer",),
    "campaign": ("marketer",),
    "seo": ("marketer",),
    "sprzedaz": ("sales",),
    "sales": ("sales",),
    "discovery call": ("sales",),
    "ticket": ("customer_support",),
    "support": ("customer_support",),
    "faq": ("customer_support",),
}


def match_role_to_task(
    task_description: str,
    available_models: Iterable[str] | None = None,
    *,
    top_n: int = 5,
) -> list[Role]:
    """Heuristic role matcher.

    This is a *placeholder*. The full matcher with intent classification,
    pipeline composition and cost optimisation lives in W13 (Task-to-Role
    Suggester).

    Args:
        task_description: Operator-supplied free-form task.
        available_models: Optional whitelist of model ids the system can run.
            Roles whose preferred + fallback model lists are completely
            outside this set get heavily down-weighted (but not removed).
        top_n: Number of roles to return.

    Returns:
        Up to ``top_n`` roles ordered by descending match score.
    """
    if not task_description:
        return []
    if not ROLE_REGISTRY:
        return []

    text = task_description.lower()
    available = set(available_models or ())

    scores: dict[str, float] = {role_id: 0.0 for role_id in ROLE_REGISTRY}

    # Keyword matches.
    for keyword, role_ids in _KEYWORD_HINTS.items():
        if keyword in text:
            for role_id in role_ids:
                if role_id in scores:
                    scores[role_id] += 3.0

    # Typical tasks substring overlap (lighter signal).
    for role in ROLE_REGISTRY.values():
        for sample in role.typical_tasks:
            sample_lc = sample.lower()
            # any 2 consecutive words from sample appearing in text?
            tokens = [t for t in sample_lc.split() if len(t) > 3]
            hits = sum(1 for t in tokens if t in text)
            if hits >= 2:
                scores[role.id] += 0.5 * hits

    # Penalize roles whose models are entirely unavailable.
    if available:
        for role in ROLE_REGISTRY.values():
            all_models = set(role.preferred_models) | set(role.fallback_models)
            if all_models and all_models.isdisjoint(available):
                scores[role.id] -= 5.0

    # Discard zero/negative scores; rank desc.
    ranked = [
        (role_id, score)
        for role_id, score in scores.items()
        if score > 0
    ]
    ranked.sort(key=lambda item: (-item[1], item[0]))

    out: list[Role] = []
    for role_id, _score in ranked[: max(0, top_n)]:
        role = ROLE_REGISTRY.get(role_id)
        if role is not None:
            out.append(role)
    return out


# ---------------------------------------------------------------------------
# W7 Phase-0 capability taxonomy + skill-level helpers.
# ---------------------------------------------------------------------------


def list_capabilities() -> list[dict[str, Any]]:
    """Return deduplicated capability ids across the registry + role count.

    Each entry: ``{"id": <capability>, "role_count": <int>}`` sorted by id.
    """
    counts: dict[str, int] = {}
    for role in ROLE_REGISTRY.values():
        for cap in role.capabilities:
            cap_norm = cap.strip()
            if not cap_norm:
                continue
            counts[cap_norm] = counts.get(cap_norm, 0) + 1
    return [
        {"id": cap, "role_count": counts[cap]}
        for cap in sorted(counts.keys())
    ]


def list_roles_by_capability(capability_id: str) -> list[Role]:
    """Return every role that declares ``capability_id`` in ``capabilities``."""
    if not capability_id:
        return []
    needle = capability_id.strip()
    if not needle:
        return []
    matches = [
        role
        for role in ROLE_REGISTRY.values()
        if needle in role.capabilities
    ]
    return sorted(matches, key=lambda r: r.id)


def _skill_level_satisfies(role_level: str, requested: str) -> bool:
    """``True`` if ``role_level`` meets the ``requested`` minimum.

    ``"any"`` on either side acts as a wildcard. Otherwise the role's
    rank must be >= the requested rank.
    """
    role_norm = (role_level or DEFAULT_SKILL_LEVEL).strip().lower()
    req_norm = (requested or DEFAULT_SKILL_LEVEL).strip().lower()
    if req_norm in ("", "any"):
        return True
    if role_norm in ("", "any"):
        # A role that hasn't declared a level matches any explicit request
        # — keeps backward compat for legacy YAMLs.
        return True
    return _SKILL_LEVEL_RANK.get(role_norm, 0) >= _SKILL_LEVEL_RANK.get(req_norm, 0)


def match_role_to_task_v2(
    task_description: str | None = None,
    *,
    required_capabilities: Iterable[str] | None = None,
    skill_level: str = DEFAULT_SKILL_LEVEL,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Capability-overlap matcher for the ``/match-task`` endpoint.

    Phase-0 scoring:

    * +5.0 per required capability the role provides.
    * +1.0 per capability keyword that appears verbatim in the task text.
    * Roles whose ``skill_level`` is below the requested level are excluded.

    Returns a list of ``{"role": <summary>, "score": float, "matched": [...]}``
    sorted by descending score.

    G2 will replace this with embedding-based similarity. Until then this
    keeps the contract stable for the dashboard UI.
    """
    requested_caps: list[str] = []
    if required_capabilities:
        for cap in required_capabilities:
            cap_norm = str(cap).strip()
            if cap_norm:
                requested_caps.append(cap_norm)
    text_lc = (task_description or "").lower()

    out: list[dict[str, Any]] = []
    for role in ROLE_REGISTRY.values():
        if not _skill_level_satisfies(role.skill_level, skill_level):
            continue
        role_caps = set(role.capabilities)
        matched = sorted(c for c in requested_caps if c in role_caps)
        score = 5.0 * len(matched)
        if text_lc:
            for cap in role_caps:
                if cap.lower() in text_lc:
                    score += 1.0
        if score <= 0:
            continue
        out.append(
            {
                "role": role.to_summary(),
                "score": round(score, 3),
                "matched_capabilities": matched,
            }
        )

    out.sort(key=lambda item: (-item["score"], item["role"]["id"]))
    return out[: max(0, top_n)]


__all__ = [
    "DEFAULT_SKILL_LEVEL",
    "ROLE_REGISTRY",
    "Role",
    "VALID_CATEGORIES",
    "VALID_COST_PROFILES",
    "VALID_SKILL_LEVELS",
    "get_role",
    "list_capabilities",
    "list_categories",
    "list_roles",
    "list_roles_by_capability",
    "match_role_to_task",
    "match_role_to_task_v2",
]
