"""Wave A-LLM FIX-016 -- per-role prompt templates.

DoD per PROMPT_01 sec 7:
  [x] Every Council role has a template.
"""

from __future__ import annotations

import pytest

from sylion.cognitive.council import (
    COUNCIL_ROLES,
    ROLE_PROMPT_TEMPLATES,
    format_role_prompt,
    get_role_template,
    register_role_template,
    reset_role_templates,
)


@pytest.fixture(autouse=True)
def _reset_templates():
    reset_role_templates()
    yield
    reset_role_templates()


# ---------------------------------------------------------------------------
# Coverage -- every canonical role has a template
# ---------------------------------------------------------------------------

class TestRoleCoverage:

    def test_canonical_roles_count(self):
        assert len(COUNCIL_ROLES) == 6

    def test_canonical_roles_include_required(self):
        assert "planner" in COUNCIL_ROLES
        assert "critic" in COUNCIL_ROLES
        assert "security" in COUNCIL_ROLES
        assert "legal" in COUNCIL_ROLES
        assert "finance" in COUNCIL_ROLES
        assert "council_chair" in COUNCIL_ROLES

    @pytest.mark.parametrize("role", [
        "planner", "critic", "security", "legal", "finance", "council_chair",
    ])
    def test_every_role_has_template(self, role):
        assert role in ROLE_PROMPT_TEMPLATES
        tpl = get_role_template(role)
        assert isinstance(tpl, str) and len(tpl) > 50

    @pytest.mark.parametrize("role", list(COUNCIL_ROLES))
    def test_template_contains_idea_placeholder(self, role):
        assert "{idea}" in get_role_template(role)

    @pytest.mark.parametrize("role", list(COUNCIL_ROLES))
    def test_template_contains_decision_class_placeholder(self, role):
        assert "{decision_class}" in get_role_template(role)

    @pytest.mark.parametrize("role", list(COUNCIL_ROLES))
    def test_template_mentions_role(self, role):
        # Role name (or a synonym) must appear so the model knows its seat.
        tpl = get_role_template(role).lower()
        synonyms = {
            "planner": ["planner", "roadmap"],
            "critic": ["critic", "stress-test"],
            "security": ["security"],
            "legal": ["legal"],
            "finance": ["finance"],
            "council_chair": ["chair"],
        }[role]
        assert any(s in tpl for s in synonyms), tpl


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRendering:

    def test_format_substitutes_idea(self):
        rendered = format_role_prompt(
            "planner", idea="ship a kill-switch for autonomy",
            decision_class="D3",
        )
        assert "ship a kill-switch for autonomy" in rendered
        assert "D3" in rendered
        assert "{idea}" not in rendered
        assert "{decision_class}" not in rendered

    def test_format_unknown_role_raises(self):
        with pytest.raises(KeyError):
            format_role_prompt("not_a_role", "x")

    def test_format_default_decision_class_is_d2(self):
        rendered = format_role_prompt("critic", "test idea")
        assert "D2" in rendered

    def test_each_role_renders_with_distinct_focus(self):
        idea = "ship a refactor of the council voting plane"
        rendered = {
            role: format_role_prompt(role, idea, "D3").lower()
            for role in COUNCIL_ROLES
        }
        # Each role's rendered text differs from every other role's.
        for r1, t1 in rendered.items():
            for r2, t2 in rendered.items():
                if r1 != r2:
                    assert t1 != t2, f"{r1} and {r2} share identical template"


# ---------------------------------------------------------------------------
# Registry mutation
# ---------------------------------------------------------------------------

class TestRegistryMutation:

    def test_register_new_role(self):
        register_role_template(
            "operations",
            "You are the Ops Reviewer. Idea: {idea}\nclass {decision_class}",
        )
        assert "operations" in ROLE_PROMPT_TEMPLATES
        out = format_role_prompt("operations", "deploy v3", "D1")
        assert "deploy v3" in out and "D1" in out

    def test_register_overrides_existing(self):
        register_role_template(
            "planner",
            "OVERRIDDEN PLANNER: {idea} for {decision_class}",
        )
        out = format_role_prompt("planner", "x", "D0")
        assert out.startswith("OVERRIDDEN PLANNER: x for D0")

    def test_reset_restores_default(self):
        register_role_template(
            "planner",
            "OVERRIDE: {idea} {decision_class}",
        )
        reset_role_templates()
        assert "OVERRIDE" not in get_role_template("planner")
        # Original 6 roles restored.
        for role in COUNCIL_ROLES:
            assert role in ROLE_PROMPT_TEMPLATES

    def test_register_without_idea_placeholder_rejected(self):
        with pytest.raises(ValueError):
            register_role_template("bad", "no placeholders here")

    def test_register_without_decision_class_placeholder_rejected(self):
        with pytest.raises(ValueError):
            register_role_template("bad", "{idea} only")
