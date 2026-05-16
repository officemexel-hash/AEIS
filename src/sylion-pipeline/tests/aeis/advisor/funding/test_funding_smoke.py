"""Smoke tests for advisor.funding — golden minimums per manifest.

The 9 scenarios mirror manifest §8 `golden_tests.minimum_required`. DB layer
runs against an in-memory SQLite-backed shim of the shared PG pool (installed
via `conftest.py`). Module code uses the shared PG pool exclusively; the shim
is a TEST-ONLY fixture per `08_audit_revisions.md` Revision 2.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")

from sylion.aeis.advisor.funding import (
    get_funding_service,
    reset_funding_service,
)
from sylion.aeis.advisor.funding._models import (
    DEFAULT_COMPONENT_WEIGHTS,
    IdeaContext,
    UNIVERSAL_COMPONENT_IDS,
)
from sylion.aeis.advisor.funding.token_budget import (
    TokenBudgetExceeded,
)


def _try_reset_preferences():
    try:
        from sylion.aeis.advisor.preferences.resolver import reset_resolver
    except Exception:
        return
    reset_resolver()


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    monkeypatch.setenv("SYLION_ADVISOR_FUNDING_STUB_LLM", "1")
    # Default: large budget so unrelated tests don't blow up.
    monkeypatch.setenv("SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY", "1000000")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    reset_funding_service()
    _try_reset_preferences()
    svc = get_funding_service()
    svc.set_enabled(operator_id="op-1", enabled=True)
    yield
    reset_funding_service()
    _try_reset_preferences()


def _idea(idea_id: str = "idea-1") -> IdeaContext:
    return IdeaContext(
        idea_id=idea_id,
        title="AI-powered diagnostics",
        description="Innowacyjna platforma badawcza dla MŚP w branży medycznej.",
        domain="research",
        keywords=["ai", "research", "innowacyjna", "platforma"],
        rd_share_pct=40.0,
        target_country="PL",
        requires_consortium=False,
    )


def _typical_company(operator_id: str = "op-1", region: str = "PL-MZ"):
    svc = get_funding_service()
    return svc.create_company(
        operator_id=operator_id,
        legal_name="Acme R&D",
        country="PL",
        region=region,
        legal_form="sp_z_o_o",
        size_category="small",
        is_msme=True,
        employee_count=15,
        annual_revenue_usd=350_000.0,
        founding_date="2018-01-01",
        pkd_codes=["62.01.Z", "72.19.Z"],
        rd_budget_history=[{"year": 2025, "budget_usd": 80_000.0}],
        innovation_certifications=[{"name": "ISO 9001"}],
    )


def test_same_company_different_grants_different_scores():
    """Golden: same_company_different_grants_different_scores."""
    svc = get_funding_service()
    company = _typical_company()
    idea = _idea()

    grant_a, _ = svc.register_grant(
        display_name="FENG SMART",
        source="pl_national",
        country="PL",
        description="research and development for SMEs",
        amount_max_usd=500_000.0,
        custom_criteria={"requires_msme": True},
        profile_overrides={
            "eligibility": {"weight": 40, "hard_floor": 50},
            "thematic_alignment": {"weight": 30, "hard_floor": 0},
            "capacity": {"weight": 20, "hard_floor": 0},
            "regional_fit": {"weight": 10, "hard_floor": 0},
        },
    )
    grant_b, _ = svc.register_grant(
        display_name="Horizon Europe Pilot",
        source="eu",
        country="EU",
        description="multi-country research consortium",
        amount_max_usd=1_500_000.0,
        custom_criteria={"requires_consortium": True},
        profile_overrides={
            "eligibility": {"weight": 20, "hard_floor": 0},
            "thematic_alignment": {"weight": 25, "hard_floor": 0},
            "consortium_readiness": {"weight": 30, "hard_floor": 0},
            "capacity": {"weight": 25, "hard_floor": 0},
        },
    )

    s_a = svc.compute_scoring(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant_a.program_id,
    )
    s_b = svc.compute_scoring(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant_b.program_id,
    )
    assert s_a.scoring_profile_id != s_b.scoring_profile_id
    assert s_a.total_score != pytest.approx(s_b.total_score)


def test_eligibility_floor_breach_blocks_card():
    """Golden: eligibility_floor_breach_blocks_card."""
    svc = get_funding_service()
    company = svc.create_company(
        operator_id="op-1",
        legal_name="Big Corp",
        country="PL",
        region="PL-WP",
        legal_form="jdg",
        size_category="large",
        is_msme=False,
        employee_count=400,
        annual_revenue_usd=50_000_000.0,
        founding_date="2025-08-01",
    )
    idea = _idea()
    grant, _ = svc.register_grant(
        display_name="FENG MŚP only",
        source="pl_national",
        country="PL",
        custom_criteria={
            "requires_msme": True,
            "required_legal_forms": ["sp_z_o_o", "sa"],
            "min_company_age_years": 2,
        },
    )
    envelope = svc.build_funding_card(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant.program_id,
        suggestion_type="FUNDING_HOW_TO_QUALIFY",
        include_simulations=False,
    )
    funding = envelope["funding"]
    assert funding["eligibility_floor_breached"] is True
    assert len(funding["gaps_to_qualify"]) >= 1
    assert len(funding["recommended_actions"]) >= 1


def test_regional_grant_filtered_by_company_region():
    """Golden: regional_grant_filtered_by_company_region."""
    svc = get_funding_service()
    company = _typical_company(region="PL-WP")
    idea = _idea()
    svc.register_grant(
        display_name="RPO Mazowieckie",
        source="pl_regional",
        country="PL",
        region="PL-MZ",
    )
    matches = svc.list_eligible_grants(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        countries=["PL"],
    )
    assert all(m.grant.region != "PL-MZ" for m in matches)


def test_manual_grant_load_creates_profile_with_default_weights():
    """Golden: manual_grant_load_creates_profile_with_default_weights."""
    svc = get_funding_service()
    grant, profile = svc.load_grant_manually(
        operator_id="op-1",
        display_name="Custom Foundation Award",
        source="custom",
        country="PL",
    )
    weights = {c.component_id: c.weight for c in profile.components}
    assert set(weights.keys()) == set(UNIVERSAL_COMPONENT_IDS)
    for cid, expected in DEFAULT_COMPONENT_WEIGHTS.items():
        assert weights[cid] == pytest.approx(expected)
    assert profile.total_weight == pytest.approx(100.0)
    assert grant.is_user_loaded is True
    assert grant.scoring_profile_id == profile.profile_id


def test_simulation_static_returns_predefined():
    """Golden: simulation_static_returns_predefined."""
    svc = get_funding_service()
    company = _typical_company()
    idea = _idea()
    grant, _ = svc.register_grant(
        display_name="Simulator FX", source="pl_national", country="PL"
    )
    scenarios = svc.simulate(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant.program_id,
        mode="static",
    )
    assert len(scenarios) == 3
    assert all(s.mode == "static" for s in scenarios)
    labels = {s.label for s in scenarios}
    assert any("sp. z o.o." in lbl for lbl in labels)
    assert any("PL-MZ" in lbl for lbl in labels)
    assert any("R&D" in lbl for lbl in labels)


def test_simulation_dynamic_recomputes_with_operator_changes():
    """Golden: simulation_dynamic_recomputes_with_operator_changes."""
    svc = get_funding_service()
    company = svc.create_company(
        operator_id="op-1",
        legal_name="Form Toggle",
        country="PL",
        region="PL-MZ",
        legal_form="jdg",
        founding_date="2020-01-01",
        size_category="micro",
        is_msme=True,
    )
    idea = _idea()
    grant, _ = svc.register_grant(
        display_name="DynSim Test",
        source="pl_national",
        country="PL",
        custom_criteria={"required_legal_forms": ["sp_z_o_o"]},
    )
    baseline = svc.simulate(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant.program_id,
        mode="dynamic",
        operator_changes={"legal_form": "jdg"},
    )[0]
    upgraded = svc.simulate(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant.program_id,
        mode="dynamic",
        operator_changes={"legal_form": "sp_z_o_o"},
    )[0]
    assert upgraded.resulting_eligibility_score > baseline.resulting_eligibility_score


def test_simulation_auto_generated_returns_top_3_score_improving():
    """Golden: simulation_auto_generated_returns_top_3_score_improving."""
    svc = get_funding_service()
    company = svc.create_company(
        operator_id="op-1",
        legal_name="WeakCo",
        country="PL",
        region="PL-WP",
        legal_form="jdg",
        founding_date="2021-01-01",
        size_category="micro",
        is_msme=True,
    )
    idea = _idea()
    grant, _ = svc.register_grant(
        display_name="AutoSim Test",
        source="pl_regional",
        country="PL",
        region="PL-MZ",
        custom_criteria={"required_legal_forms": ["sp_z_o_o"]},
    )
    auto = svc.simulate(
        operator_id="op-1",
        company_id=company.company_id,
        idea=idea,
        program_id=grant.program_id,
        mode="auto",
    )
    assert 1 <= len(auto) <= 3
    assert all(s.mode == "auto_generated" for s in auto)
    deltas = [s.resulting_eligibility_score for s in auto]
    assert deltas == sorted(deltas, reverse=True)


def test_separate_token_budget_enforced(monkeypatch):
    """Golden: separate_token_budget_enforced."""
    monkeypatch.setenv("SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY", "100")
    svc = get_funding_service()
    with pytest.raises(TokenBudgetExceeded):
        svc.initiate_research(
            operator_id="op-1",
            query="grants for AI healthcare",
            scope="grant_discovery",
            projected_tokens=500,
        )


def test_opt_out_skips_module_entirely():
    """Golden: opt_out_skips_module_entirely."""
    svc = get_funding_service()
    svc.set_enabled(operator_id="op-2", enabled=False)
    company = svc.create_company(
        operator_id="op-2",
        legal_name="OptOut Co",
        country="PL",
        legal_form="sp_z_o_o",
        is_msme=True,
        founding_date="2018-01-01",
    )
    idea = _idea("idea-opt")
    grant, _ = svc.register_grant(
        display_name="Should-be-skipped", source="pl_national", country="PL"
    )

    matches = svc.list_eligible_grants(
        operator_id="op-2", company_id=company.company_id, idea=idea
    )
    assert matches == []

    envelope = svc.build_funding_card(
        operator_id="op-2",
        company_id=company.company_id,
        idea=idea,
        program_id=grant.program_id,
    )
    assert envelope == {}

    with pytest.raises(RuntimeError):
        svc.compute_scoring(
            operator_id="op-2",
            company_id=company.company_id,
            idea=idea,
            program_id=grant.program_id,
        )
