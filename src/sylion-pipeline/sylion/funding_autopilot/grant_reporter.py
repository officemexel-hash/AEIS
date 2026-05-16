"""
SYLION Funding Autopilot — Grant Reporter (K1.3)

Comprehensive reporting and analytics for the funding pipeline.
Produces funnel metrics, financial summaries, portfolio diversification,
success rates, time-to-submit analytics, and risk aggregation.

Hook v1.0 (2026-04-24)
Changes: initial
Owner: K-SURF
"""

from __future__ import annotations

import statistics
import time
from typing import Any

from .store import FundingAutopilotStore, get_funding_store


class GrantReporter:
    """Analytics reporter for the funding autopilot pipeline."""

    def __init__(self, store: FundingAutopilotStore | None = None):
        self.store = store or get_funding_store()

    # ------------------------------------------------------------------
    # Pipeline funnel
    # ------------------------------------------------------------------

    def pipeline_funnel(self, company_id: str = "default") -> dict[str, Any]:
        """Return counts at each pipeline stage."""
        calls = self.store.list_calls()
        ideas = self.store.list_ideas(company_id)
        projects = self.store.list_projects(company_id)
        applications = self.store.list_applications(company_id)
        submissions = [
            app for app in applications
            if app.get("status") == "submitted"
        ]
        return {
            "calls_in_catalogue": len(calls),
            "ideas_generated": len(ideas),
            "projects_created": len(projects),
            "applications_drafted": len(applications),
            "applications_submitted": len(submissions),
            "conversion_idea_to_project": _safe_rate(len(projects), len(ideas)),
            "conversion_project_to_application": _safe_rate(len(applications), len(projects)),
            "conversion_application_to_submitted": _safe_rate(len(submissions), len(applications)),
            "overall_pipeline_yield": _safe_rate(len(submissions), len(calls)),
        }

    # ------------------------------------------------------------------
    # Financial summary
    # ------------------------------------------------------------------

    def financial_summary(self, company_id: str = "default") -> dict[str, Any]:
        """Aggregate financial metrics across all applications."""
        applications = self.store.list_applications(company_id)
        total_requested = 0.0
        total_budget = 0.0
        by_status: dict[str, dict] = {}

        for app in applications:
            pkg = app.get("package_json", {})
            budget = pkg.get("budget", {})
            req = float(budget.get("grant_requested", 0) or 0)
            tot = float(budget.get("budget_total", 0) or 0)
            status = app.get("status", "unknown")

            total_requested += req
            total_budget += tot

            if status not in by_status:
                by_status[status] = {"count": 0, "grant_requested": 0.0, "budget_total": 0.0}
            by_status[status]["count"] += 1
            by_status[status]["grant_requested"] += req
            by_status[status]["budget_total"] += tot

        return {
            "total_applications": len(applications),
            "total_grant_requested": round(total_requested, 2),
            "total_budget_planned": round(total_budget, 2),
            "average_grant_per_application": round(_safe_div(total_requested, len(applications)), 2),
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Success metrics
    # ------------------------------------------------------------------

    def success_metrics(self, company_id: str = "default") -> dict[str, Any]:
        """Win rates, approval rates, and rejection analysis."""
        applications = self.store.list_applications(company_id)
        if not applications:
            return {"win_rate": 0.0, "approval_rate": 0.0, "rejection_reasons": []}

        submitted = [a for a in applications if a.get("status") == "submitted"]
        approved = [a for a in applications if a.get("status") == "approved"]
        rejected = [a for a in applications if a.get("status") == "rejected"]

        # Rejection reasons from review_json
        reasons: list[str] = []
        for app in rejected:
            review = app.get("review_json", {})
            for mode, result in review.items():
                if isinstance(result, dict) and result.get("passed") is False:
                    reasons.append(f"{mode}: {result.get('summary', 'failed')}")

        return {
            "win_rate": _safe_rate(len(approved), len(submitted)),
            "approval_rate": _safe_rate(len(approved), len(applications)),
            "submission_rate": _safe_rate(len(submitted), len(applications)),
            "rejection_rate": _safe_rate(len(rejected), len(applications)),
            "rejection_reasons": reasons[:10],
            "total_submitted_value": sum(
                float(a.get("package_json", {}).get("budget", {}).get("grant_requested", 0) or 0)
                for a in submitted
            ),
        }

    # ------------------------------------------------------------------
    # Portfolio diversification
    # ------------------------------------------------------------------

    def portfolio_diversification(self, company_id: str = "default") -> dict[str, Any]:
        """Break down active pipeline by programme, country, and theme."""
        applications = self.store.list_applications(company_id)
        programmes: dict[str, int] = {}
        countries: dict[str, int] = {}
        themes: dict[str, int] = {}

        for app in applications:
            call_id = app.get("call_id")
            if call_id:
                call = self.store.get_call(call_id)
                if call:
                    prog = call.get("programme_id", "unknown")
                    programmes[prog] = programmes.get(prog, 0) + 1
                    country = call.get("country", "unknown")
                    countries[country] = countries.get(country, 0) + 1
                    for theme in call.get("themes", []):
                        themes[theme] = themes.get(theme, 0) + 1

        return {
            "by_programme": programmes,
            "by_country": countries,
            "by_theme": themes,
            "concentration_risk": _top_heavy_ratio(programmes),
        }

    # ------------------------------------------------------------------
    # Time metrics
    # ------------------------------------------------------------------

    def time_metrics(self, company_id: str = "default") -> dict[str, Any]:
        """Average time spent at each pipeline stage."""
        applications = self.store.list_applications(company_id)
        idea_to_project: list[float] = []
        project_to_app: list[float] = []
        app_to_submit: list[float] = []

        for app in applications:
            pkg = app.get("package_json", {})
            timeline = pkg.get("timeline", {})
            if timeline.get("idea_at") and timeline.get("project_at"):
                idea_to_project.append(timeline["project_at"] - timeline["idea_at"])
            if timeline.get("project_at") and timeline.get("application_at"):
                project_to_app.append(timeline["application_at"] - timeline["project_at"])
            if timeline.get("application_at") and timeline.get("submitted_at"):
                app_to_submit.append(timeline["submitted_at"] - timeline["application_at"])

        def _avg(vals: list[float]) -> float:
            return round(statistics.mean(vals), 1) if vals else 0.0

        return {
            "avg_days_idea_to_project": round(_avg(idea_to_project) / 86400, 1),
            "avg_days_project_to_application": round(_avg(project_to_app) / 86400, 1),
            "avg_days_application_to_submit": round(_avg(app_to_submit) / 86400, 1),
            "samples": {
                "idea_to_project": len(idea_to_project),
                "project_to_app": len(project_to_app),
                "app_to_submit": len(app_to_submit),
            },
        }

    # ------------------------------------------------------------------
    # Risk register
    # ------------------------------------------------------------------

    def risk_register(self, company_id: str = "default") -> dict[str, Any]:
        """Aggregate risks across all active (non-submitted) applications."""
        applications = self.store.list_applications(company_id)
        active = [a for a in applications if a.get("status") not in ("submitted", "approved", "rejected")]
        risks: list[dict] = []
        for app in active:
            review = app.get("review_json", {})
            for mode, result in review.items():
                if isinstance(result, dict):
                    for risk in result.get("risks", []):
                        risks.append({
                            "application_id": app["application_id"],
                            "mode": mode,
                            "risk": risk,
                        })
        # Also include scoring risks if store supports get_scoring
        if hasattr(self.store, "get_scoring"):
            for app in active:
                scoring = self.store.get_scoring(app["project_id"], app.get("call_id"))
                if scoring and isinstance(scoring, dict):
                    for risk in scoring.get("risks", []):
                        risks.append({
                            "application_id": app["application_id"],
                            "mode": "scoring",
                            "risk": risk,
                        })
        return {
            "active_applications": len(active),
            "total_risks": len(risks),
            "risks": risks[:50],
        }

    # ------------------------------------------------------------------
    # Executive dashboard
    # ------------------------------------------------------------------

    def executive_dashboard(self, company_id: str = "default") -> dict[str, Any]:
        """Combined one-page executive report."""
        return {
            "generated_at": time.time(),
            "company_id": company_id,
            "funnel": self.pipeline_funnel(company_id),
            "financials": self.financial_summary(company_id),
            "success": self.success_metrics(company_id),
            "portfolio": self.portfolio_diversification(company_id),
            "timing": self.time_metrics(company_id),
            "risks": self.risk_register(company_id),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def _safe_div(numerator: float, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _top_heavy_ratio(counter: dict[str, int]) -> dict[str, Any]:
    """Return concentration metrics for a counter dict."""
    total = sum(counter.values())
    if not total:
        return {"max_share_pct": 0.0, "top_3_share_pct": 0.0}
    sorted_vals = sorted(counter.values(), reverse=True)
    max_share = sorted_vals[0] / total * 100
    top3_share = sum(sorted_vals[:3]) / total * 100
    return {
        "max_share_pct": round(max_share, 2),
        "top_3_share_pct": round(top3_share, 2),
        "recommendation": "diversify" if max_share > 60 else "balanced",
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_reporter: GrantReporter | None = None


def get_grant_reporter(store: FundingAutopilotStore | None = None) -> GrantReporter:
    global _reporter
    if _reporter is None:
        _reporter = GrantReporter(store)
    return _reporter


def reset_grant_reporter(store: FundingAutopilotStore | None = None) -> GrantReporter:
    global _reporter
    _reporter = GrantReporter(store)
    return _reporter
