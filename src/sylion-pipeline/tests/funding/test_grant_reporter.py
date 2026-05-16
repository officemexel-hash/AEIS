"""
Tests for sylion.funding_autopilot.grant_reporter (K1.3).
"""

from __future__ import annotations

import pytest

from sylion.funding_autopilot.grant_reporter import (
    GrantReporter,
    _safe_div,
    _safe_rate,
    _top_heavy_ratio,
    get_grant_reporter,
    reset_grant_reporter,
)
from sylion.funding_autopilot.store import FundingAutopilotStore


@pytest.fixture
def fresh_store() -> FundingAutopilotStore:
    """Return a fresh in-memory store for each test."""
    return FundingAutopilotStore(":memory:")


@pytest.fixture
def reporter(fresh_store) -> GrantReporter:
    return GrantReporter(fresh_store)


class TestPipelineFunnel:
    def test_empty_pipeline(self, reporter):
        result = reporter.pipeline_funnel()
        assert result["calls_in_catalogue"] == 0
        assert result["ideas_generated"] == 0
        assert result["conversion_idea_to_project"] == 0.0

    def test_with_data(self, reporter, fresh_store):
        fresh_store.upsert_company_profile("default", {"legal_name": "Acme"})
        fresh_store.create_programme({"programme_id": "p1", "name": "P1", "country": "EU"})
        fresh_store.create_call({"call_id": "c1", "programme_id": "p1", "title": "Call 1", "code": "C1"})
        fresh_store.create_project({"project_id": "proj_1", "company_id": "default", "title": "Proj 1", "summary": "S1"})
        fresh_store.create_application({"application_id": "a1", "company_id": "default", "project_id": "proj_1", "call_id": "c1", "status": "draft"})
        fresh_store.create_application({"application_id": "a2", "company_id": "default", "project_id": "proj_1", "call_id": "c1", "status": "submitted"})

        result = reporter.pipeline_funnel()
        assert result["calls_in_catalogue"] == 1
        assert result["projects_created"] == 1
        assert result["applications_drafted"] == 2
        assert result["applications_submitted"] == 1
        assert result["conversion_application_to_submitted"] == 50.0


class TestFinancialSummary:
    def test_empty(self, reporter):
        result = reporter.financial_summary()
        assert result["total_applications"] == 0
        assert result["total_grant_requested"] == 0.0

    def test_aggregates_by_status(self, reporter, fresh_store):
        fresh_store.upsert_company_profile("default", {"legal_name": "Acme"})
        fresh_store.create_project({"project_id": "p1", "company_id": "default", "title": "P1", "summary": "S1"})
        fresh_store.create_application({
            "application_id": "a1",
            "company_id": "default",
            "project_id": "p1",
            "status": "draft",
            "package": {"budget": {"grant_requested": 100_000, "budget_total": 200_000}},
        })
        fresh_store.create_application({
            "application_id": "a2",
            "company_id": "default",
            "project_id": "p1",
            "status": "submitted",
            "package": {"budget": {"grant_requested": 250_000, "budget_total": 500_000}},
        })
        result = reporter.financial_summary()
        assert result["total_grant_requested"] == 350_000.0
        assert result["total_budget_planned"] == 700_000.0
        assert result["average_grant_per_application"] == 175_000.0
        assert "draft" in result["by_status"]
        assert "submitted" in result["by_status"]


class TestSuccessMetrics:
    def test_empty(self, reporter):
        result = reporter.success_metrics()
        assert result["win_rate"] == 0.0

    def test_rates(self, reporter, fresh_store):
        fresh_store.upsert_company_profile("default", {"legal_name": "Acme"})
        fresh_store.create_project({"project_id": "p1", "company_id": "default", "title": "P1", "summary": "S1"})
        fresh_store.create_application({"application_id": "a1", "company_id": "default", "project_id": "p1", "status": "approved"})
        fresh_store.create_application({"application_id": "a2", "company_id": "default", "project_id": "p1", "status": "submitted"})
        fresh_store.create_application({"application_id": "a3", "company_id": "default", "project_id": "p1", "status": "rejected", "review": {"formal": {"passed": False, "summary": "missing doc"}}})
        result = reporter.success_metrics()
        assert result["approval_rate"] == 33.33
        assert result["submission_rate"] == 33.33
        assert len(result["rejection_reasons"]) == 1


class TestPortfolioDiversification:
    def test_empty(self, reporter):
        result = reporter.portfolio_diversification()
        assert result["by_programme"] == {}

    def test_diversification(self, reporter, fresh_store):
        fresh_store.upsert_company_profile("default", {"legal_name": "Acme"})
        fresh_store.create_programme({"programme_id": "horizon", "name": "HE", "country": "EU"})
        fresh_store.create_programme({"programme_id": "ncbr", "name": "NCBR", "country": "PL"})
        fresh_store.create_call({"call_id": "c1", "programme_id": "horizon", "title": "C1", "code": "C1", "country": "EU", "themes": ["ai", "energy"]})
        fresh_store.create_call({"call_id": "c2", "programme_id": "ncbr", "title": "C2", "code": "C2", "country": "PL", "themes": ["cyber"]})
        fresh_store.create_project({"project_id": "p1", "company_id": "default", "title": "P1", "summary": "S1"})
        fresh_store.create_application({"application_id": "a1", "company_id": "default", "project_id": "p1", "call_id": "c1"})
        fresh_store.create_application({"application_id": "a2", "company_id": "default", "project_id": "p1", "call_id": "c2"})
        result = reporter.portfolio_diversification()
        assert result["by_country"]["EU"] == 1
        assert result["by_country"]["PL"] == 1
        # Themes may not be stored as JSON list by store; verify structure only
        assert result["concentration_risk"]["recommendation"] == "balanced"


class TestTimeMetrics:
    def test_empty(self, reporter):
        result = reporter.time_metrics()
        assert result["avg_days_idea_to_project"] == 0.0

    def test_with_timeline(self, reporter, fresh_store):
        fresh_store.upsert_company_profile("default", {"legal_name": "Acme"})
        fresh_store.create_project({"project_id": "p1", "company_id": "default", "title": "P1", "summary": "S1"})
        t0 = 1_000_000
        fresh_store.create_application({
            "application_id": "a1",
            "company_id": "default",
            "project_id": "p1",
            "status": "submitted",
            "package": {
                "timeline": {
                    "idea_at": t0,
                    "project_at": t0 + 86400 * 5,
                    "application_at": t0 + 86400 * 10,
                    "submitted_at": t0 + 86400 * 20,
                }
            },
        })
        result = reporter.time_metrics()
        assert result["avg_days_idea_to_project"] == 5.0
        assert result["avg_days_project_to_application"] == 5.0
        assert result["avg_days_application_to_submit"] == 10.0


class TestRiskRegister:
    def test_empty(self, reporter):
        result = reporter.risk_register()
        assert result["total_risks"] == 0

    def test_with_risks(self, reporter, fresh_store):
        fresh_store.upsert_company_profile("default", {"legal_name": "Acme"})
        fresh_store.create_project({"project_id": "p1", "company_id": "default", "title": "P1", "summary": "S1"})
        fresh_store.create_application({
            "application_id": "a1",
            "company_id": "default",
            "project_id": "p1",
            "status": "draft",
            "review": {
                "formal": {"risks": ["missing signature"]},
                "financial": {"risks": ["budget mismatch"]},
            },
        })
        result = reporter.risk_register()
        assert result["active_applications"] == 1
        assert result["total_risks"] == 2


class TestExecutiveDashboard:
    def test_comprehensive_report(self, reporter):
        result = reporter.executive_dashboard()
        assert "generated_at" in result
        assert "funnel" in result
        assert "financials" in result
        assert "success" in result
        assert "portfolio" in result
        assert "timing" in result
        assert "risks" in result


class TestHelpers:
    def test_safe_rate(self):
        assert _safe_rate(1, 2) == 50.0
        assert _safe_rate(0, 0) == 0.0

    def test_safe_div(self):
        assert _safe_div(10.0, 2) == 5.0
        assert _safe_div(10.0, 0) == 0.0

    def test_top_heavy_ratio(self):
        assert _top_heavy_ratio({"a": 50, "b": 50})["recommendation"] == "balanced"
        assert _top_heavy_ratio({"a": 80, "b": 10, "c": 10})["recommendation"] == "diversify"
        assert _top_heavy_ratio({})["max_share_pct"] == 0.0


class TestSingleton:
    def test_get_and_reset(self):
        r1 = get_grant_reporter()
        r2 = get_grant_reporter()
        assert r1 is r2
        r3 = reset_grant_reporter()
        assert r3 is not r1
