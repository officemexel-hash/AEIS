"""AdvisorFundingService — singleton facade for the funding advisor.

Exposes the public API used by REST/gRPC adapters and tests. Holds no
per-request state; the SQLite store is the source of truth and is reset via
`reset_funding_db()` between tests.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from sylion.aeis.advisor.funding import (
    _db,
    card_builder,
    company_manager,
    grant_catalog,
    token_budget,
)
from sylion.aeis.advisor.funding._models import (
    Company,
    GrantProgram,
    IdeaContext,
    ScoringHistoryEntry,
    ScoringProfile,
    SimulationScenario,
)
from sylion.aeis.advisor.funding.consortium import matcher as consortium_matcher
from sylion.aeis.advisor.funding.matcher import (
    gap_analyzer,
    grants_to_ideas,
    idea_to_grants,
)
from sylion.aeis.advisor.funding.scoring import calculator as scoring_calculator
from sylion.aeis.advisor.funding.simulator import (
    auto_scenarios,
    dynamic_scenario,
    static_scenarios,
)

log = logging.getLogger("sylion.aeis.advisor.funding.service")


_PREF_OPT_IN_KEY = "funding_advisor_enabled"
_PREF_COUNTRIES_KEY = "funding_countries"


def _try_get_preferences_resolver():
    """Return preferences resolver if the sibling module is loadable, else None."""
    try:
        from sylion.aeis.advisor.preferences.resolver import get_resolver
    except Exception:
        return None
    try:
        return get_resolver()
    except Exception:  # pragma: no cover
        return None


class AdvisorFundingService:
    """High-level facade. Singleton; initialised lazily."""

    def __init__(self) -> None:
        _db.init_funding_schema()
        self._lock = threading.Lock()
        self._event_bus: Any = None
        self._subscribed = 0
        # Local fallback for opt-in / country filter when preferences module
        # isn't loaded yet (sibling sub-agent). Per Revision 4, when the
        # preferences module is wired the resolver wins.
        self._local_enabled: dict[tuple[str, str], bool] = {}
        self._local_countries: dict[tuple[str, str], list[str]] = {}

    # -- preferences / activation --------------------------------------

    def is_enabled(self, operator_id: str, project_id: str = "") -> bool:
        resolver = _try_get_preferences_resolver()
        if resolver is not None:
            pref = resolver.resolve_effective(operator_id, project_id, None, _PREF_OPT_IN_KEY)
            if pref.value is not None:
                return bool(pref.value)
        return self._local_enabled.get((operator_id, project_id), False)

    def set_enabled(self, *, operator_id: str, project_id: str = "", enabled: bool) -> None:
        resolver = _try_get_preferences_resolver()
        if resolver is not None:
            resolver.set_preference(
                operator_id, project_id, _PREF_OPT_IN_KEY, bool(enabled), source="operator"
            )
        self._local_enabled[(operator_id, project_id)] = bool(enabled)
        topic = "aeis.advisor.funding.module_enabled" if enabled else "aeis.advisor.funding.module_disabled"
        self._publish(topic, {"operator_id": operator_id, "project_id": project_id})

    def country_filter(self, operator_id: str, project_id: str = "") -> list[str]:
        resolver = _try_get_preferences_resolver()
        if resolver is not None:
            pref = resolver.resolve_effective(operator_id, project_id, None, _PREF_COUNTRIES_KEY)
            if isinstance(pref.value, list):
                return [str(c) for c in pref.value]
        return list(self._local_countries.get((operator_id, project_id), []))

    def set_country_filter(
        self, *, operator_id: str, project_id: str = "", countries: list[str]
    ) -> None:
        resolver = _try_get_preferences_resolver()
        if resolver is not None:
            resolver.set_preference(
                operator_id, project_id, _PREF_COUNTRIES_KEY, list(countries), source="operator"
            )
        self._local_countries[(operator_id, project_id)] = list(countries)
        self._publish(
            "aeis.advisor.funding.country_filter_changed",
            {"operator_id": operator_id, "countries": list(countries)},
        )

    # -- companies ------------------------------------------------------

    def create_company(self, *, operator_id: str, **kwargs: Any) -> Company:
        return company_manager.create_company(operator_id=operator_id, **kwargs)

    def update_company(self, *, company_id: str, patch: dict[str, Any]) -> Company | None:
        return company_manager.update_company(company_id, patch)

    def attach_person(self, **kwargs: Any) -> Any:
        return company_manager.attach_person(**kwargs)

    def list_companies(self, operator_id: str) -> list[Company]:
        return company_manager.list_companies(operator_id)

    # -- grants ---------------------------------------------------------

    def load_grant_manually(
        self,
        *,
        operator_id: str,
        display_name: str,
        source: str = "custom",
        country: str = "PL",
        region: str = "",
        description: str = "",
        amount_max_usd: float = 0.0,
        custom_criteria: dict[str, Any] | None = None,
        profile_overrides: dict[str, dict[str, float]] | None = None,
    ) -> tuple[GrantProgram, ScoringProfile]:
        return grant_catalog.load_grant_manually(
            operator_id=operator_id,
            display_name=display_name,
            source=source,
            country=country,
            region=region,
            description=description,
            amount_max_usd=amount_max_usd,
            custom_criteria=custom_criteria,
            profile_overrides=profile_overrides,
        )

    def register_grant(self, **kwargs: Any) -> tuple[GrantProgram, ScoringProfile]:
        return grant_catalog.register_grant(**kwargs)

    def list_grants(
        self, *, country: str | None = None, region: str | None = None
    ) -> list[GrantProgram]:
        return grant_catalog.list_grants(country=country, region=region)

    # -- scoring --------------------------------------------------------

    def compute_scoring(
        self,
        *,
        operator_id: str,
        company_id: str,
        idea: IdeaContext,
        program_id: str,
        profile_id: str = "",
        triggering_event: str = "manual_recalc",
    ) -> ScoringHistoryEntry:
        if not self.is_enabled(operator_id):
            raise RuntimeError("funding_advisor_disabled")
        company = company_manager.get_company(company_id)
        if company is None:
            raise ValueError(f"unknown company_id: {company_id}")
        grant = grant_catalog.get_grant(program_id)
        if grant is None:
            raise ValueError(f"unknown program_id: {program_id}")

        budget_projection = 1500
        token_budget.check_budget_or_raise(operator_id, budget_projection)
        token_budget.record_usage(
            operator_id=operator_id,
            research_purpose="scoring_assessment",
            prompt_tokens=600,
            response_tokens=200,
            cost_usd=0.0,
            model_id="stub",
        )

        entry = scoring_calculator.compute_score(
            operator_id=operator_id,
            company=company,
            idea=idea,
            grant=grant,
            triggering_event=triggering_event,
            profile_id=profile_id,
        )
        self._publish(
            "aeis.advisor.funding.scoring_calculated",
            {
                "operator_id": operator_id,
                "company_id": company_id,
                "program_id": program_id,
                "scoring_id": entry.scoring_id,
                "total_score": entry.total_score,
            },
        )
        if entry.eligibility_floor_breached:
            self._publish(
                "aeis.advisor.funding.eligibility_floor_breached",
                {
                    "operator_id": operator_id,
                    "company_id": company_id,
                    "program_id": program_id,
                    "scoring_id": entry.scoring_id,
                },
            )
        return entry

    def get_scoring_history(
        self, *, company_id: str = "", idea_id: str = "", program_id: str = ""
    ) -> list[dict[str, Any]]:
        return _db.fetch_scoring_history(
            company_id=company_id, idea_id=idea_id, program_id=program_id
        )

    # -- matching -------------------------------------------------------

    def list_eligible_grants(
        self,
        *,
        operator_id: str,
        company_id: str,
        idea: IdeaContext,
        countries: list[str] | None = None,
    ) -> list[idea_to_grants.GrantMatch]:
        if not self.is_enabled(operator_id):
            return []
        if countries is None:
            countries = self.country_filter(operator_id) or None
        return idea_to_grants.list_eligible_grants(
            operator_id=operator_id,
            company_id=company_id,
            idea=idea,
            countries=countries,
        )

    def list_matching_ideas(
        self,
        *,
        operator_id: str,
        program_id: str,
        company_id: str,
        candidate_ideas: list[IdeaContext],
    ) -> list[grants_to_ideas.IdeaMatch]:
        company = company_manager.get_company(company_id)
        if company is None:
            return []
        return grants_to_ideas.list_matching_ideas(
            operator_id=operator_id,
            program_id=program_id,
            company=company,
            candidate_ideas=candidate_ideas,
        )

    def suggest_gap_closure(
        self,
        *,
        operator_id: str,
        company_id: str,
        idea: IdeaContext,
        program_id: str,
    ) -> dict[str, Any]:
        entry = self.compute_scoring(
            operator_id=operator_id,
            company_id=company_id,
            idea=idea,
            program_id=program_id,
            triggering_event="manual_recalc",
        )
        gaps = gap_analyzer.analyze_gaps(entry)
        return {
            "scoring": entry,
            "gap_analysis": gaps,
        }

    # -- consortium -----------------------------------------------------

    def suggest_consortium(
        self, *, operator_id: str, program_id: str, company_id: str, requirements: list[str] | None = None
    ) -> list[Any]:
        grant = grant_catalog.get_grant(program_id)
        company = company_manager.get_company(company_id)
        if grant is None or company is None:
            return []
        suggestions = consortium_matcher.suggest_partners(
            grant=grant, company=company, requirements=requirements
        )
        if suggestions:
            self._publish(
                "aeis.advisor.funding.consortium_suggested",
                {
                    "operator_id": operator_id,
                    "program_id": program_id,
                    "count": len(suggestions),
                },
            )
        return suggestions

    # -- simulation -----------------------------------------------------

    def simulate(
        self,
        *,
        operator_id: str,
        company_id: str,
        idea: IdeaContext,
        program_id: str,
        mode: str = "static",
        operator_changes: dict[str, Any] | None = None,
    ) -> list[SimulationScenario]:
        company = company_manager.get_company(company_id)
        grant = grant_catalog.get_grant(program_id)
        if company is None or grant is None:
            return []
        token_budget.check_budget_or_raise(operator_id, 200)
        token_budget.record_usage(
            operator_id=operator_id,
            research_purpose="simulation",
            prompt_tokens=120,
            response_tokens=80,
            cost_usd=0.0,
            model_id="stub",
        )
        if mode == "static":
            scenarios = static_scenarios(company, idea, grant)
        elif mode == "dynamic":
            scenarios = [
                dynamic_scenario(company, idea, grant, operator_changes or {})
            ]
        elif mode == "auto":
            scenarios = auto_scenarios(company, idea, grant)
        else:
            raise ValueError(f"unknown simulation mode: {mode}")
        self._publish(
            "aeis.advisor.funding.simulation_completed",
            {"operator_id": operator_id, "program_id": program_id, "mode": mode, "count": len(scenarios)},
        )
        return scenarios

    # -- card / envelope build -----------------------------------------

    def build_funding_card(
        self,
        *,
        operator_id: str,
        company_id: str,
        idea: IdeaContext,
        program_id: str,
        suggestion_type: str = "FUNDING_HOW_TO_QUALIFY",
        include_simulations: bool = True,
    ) -> dict[str, Any]:
        if not self.is_enabled(operator_id):
            return {}
        gap = self.suggest_gap_closure(
            operator_id=operator_id,
            company_id=company_id,
            idea=idea,
            program_id=program_id,
        )
        scoring: ScoringHistoryEntry = gap["scoring"]
        gap_analysis = gap["gap_analysis"]
        grant = grant_catalog.get_grant(program_id)
        company = company_manager.get_company(company_id)
        consortium_suggestions = []
        if grant and company and (grant.custom_criteria or {}).get("requires_consortium", False):
            consortium_suggestions = [
                {
                    "suggestion_id": s.suggestion_id,
                    "entity_type": s.entity_type,
                    "suggested_name": s.suggested_name,
                    "required_qualifications": s.required_qualifications,
                    "region_constraint": s.region_constraint,
                    "rationale": s.rationale,
                }
                for s in consortium_matcher.suggest_partners(grant=grant, company=company)
            ]
        static_sims, dyn_sims, auto_sims = [], [], []
        if include_simulations and grant:
            static_sims = self.simulate(
                operator_id=operator_id, company_id=company_id, idea=idea,
                program_id=program_id, mode="static",
            )
            auto_sims = self.simulate(
                operator_id=operator_id, company_id=company_id, idea=idea,
                program_id=program_id, mode="auto",
            )

        body = card_builder.build_funding_card_body(
            suggestion_type=suggestion_type,
            grant=grant,
            scoring=scoring,
            gap_analysis=gap_analysis,
            headline_recommendation=_default_headline(suggestion_type, grant),
            consortium_required=bool((grant.custom_criteria or {}).get("requires_consortium", False)),
            consortium_suggestions=consortium_suggestions,
            static_simulations=static_sims,
            dynamic_simulations=dyn_sims,
            auto_simulations=auto_sims,
            match_confidence=min(1.0, scoring.total_score / 100.0),
        )
        env = card_builder.build_funding_envelope(
            operator_id=operator_id,
            project_id=idea.idea_id,
            idea_id=idea.idea_id,
            body=body,
            rationale=f"Funding match for {grant.display_name} based on profile {scoring.scoring_profile_id}.",
            confidence_score=min(1.0, scoring.total_score / 100.0),
            risk_level="medium" if scoring.total_score >= 50 else "high",
        )
        return _envelope_to_dict(env)

    # -- research initiation -------------------------------------------

    def initiate_research(
        self,
        *,
        operator_id: str,
        query: str,
        scope: str = "grant_discovery",
        projected_tokens: int = 2000,
    ) -> str:
        token_budget.check_budget_or_raise(operator_id, projected_tokens)
        log_id = str(uuid.uuid4())
        token_budget.record_usage(
            operator_id=operator_id,
            research_purpose=scope,
            prompt_tokens=int(projected_tokens * 0.6),
            response_tokens=int(projected_tokens * 0.4),
            cost_usd=0.0,
            model_id="stub",
            external_research=True,
        )
        self._publish(
            "aeis.advisor.funding.research_initiated",
            {"operator_id": operator_id, "scope": scope, "query": query, "log_id": log_id},
        )
        return log_id

    # -- event bus glue -------------------------------------------------

    def attach_to_event_bus(self, event_bus: Any) -> int:
        with self._lock:
            self._event_bus = event_bus
            self._subscribed = 0
        log.info("funding service attached to event_bus")
        return self._subscribed

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            event = SylionEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.funding",
                timestamp=time.time(),
            )
            self._event_bus.publish(event)
        except Exception as exc:  # pragma: no cover
            log.warning("funding publish failed topic=%s err=%s", topic, exc)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service: AdvisorFundingService | None = None
_service_lock = threading.Lock()


def get_funding_service() -> AdvisorFundingService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = AdvisorFundingService()
    return _service


def reset_funding_service() -> None:
    """For tests: drop the singleton."""
    global _service
    with _service_lock:
        _service = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_headline(suggestion_type: str, grant: GrantProgram | None) -> str:
    if grant is None:
        return ""
    if suggestion_type == "FUNDING_GRANT_FIT":
        return f"Twoja propozycja pasuje pod {grant.display_name}."
    if suggestion_type == "FUNDING_HOW_TO_QUALIFY":
        return f"Jak zakwalifikować się do {grant.display_name}."
    if suggestion_type == "FUNDING_FORM_COMPANY":
        return f"Załóż firmę pod kontem {grant.display_name}."
    if suggestion_type == "FUNDING_REGIONAL_RELOCATION":
        return f"Przenieś działalność do {grant.region or grant.country} dla {grant.display_name}."
    if suggestion_type == "FUNDING_FIND_CONSORTIUM":
        return f"Znajdź partnera konsorcjalnego dla {grant.display_name}."
    return f"Funding suggestion for {grant.display_name}"


def _envelope_to_dict(env: Any) -> dict[str, Any]:
    return {
        "envelope_version": env.envelope_version,
        "header": env.header.__dict__,
        "funding": env.funding.__dict__ if env.funding is not None else None,
    }
