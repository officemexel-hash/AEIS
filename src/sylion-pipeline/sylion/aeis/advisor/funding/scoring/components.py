"""Per-component scoring functions.

Each scorer returns `(score_0_100, driving_factors)` so the calculator can
assemble a `ComponentScore` with explanations. These are deterministic heuristics
suitable for the MVP — the LLM judge layer (`llm_scorer`) refines explanations
on top of these values.
"""

from __future__ import annotations

import time

from sylion.aeis.advisor.funding._models import (
    Company,
    GrantProgram,
    IdeaContext,
)


_LEGAL_FORM_SCORES = {
    "sp_z_o_o": 100.0,
    "sa": 95.0,
    "limited_uk": 80.0,
    "fundacja": 70.0,
    "jdg": 30.0,
    "": 0.0,
}

_SIZE_TO_MSME = {"micro", "small", "medium"}


def score_eligibility(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    custom = grant.custom_criteria or {}

    legal_form = (company.legal_form or "").lower()
    legal_score = _LEGAL_FORM_SCORES.get(legal_form, 40.0)
    if "required_legal_forms" in custom:
        required = {f.lower() for f in custom["required_legal_forms"]}
        legal_score = 100.0 if legal_form in required else 0.0
        factors.append(f"legal_form={legal_form or 'unset'} required={sorted(required)}")
    else:
        factors.append(f"legal_form={legal_form or 'unset'}")

    msme_required = bool(custom.get("requires_msme", False))
    msme_score = 100.0
    if msme_required:
        msme_score = 100.0 if (company.is_msme or company.size_category in _SIZE_TO_MSME) else 0.0
        factors.append(f"msme_required={msme_required} msme={company.is_msme}")

    pkd_score = 100.0
    if "required_pkd_prefixes" in custom and custom["required_pkd_prefixes"]:
        prefixes = list(custom["required_pkd_prefixes"])
        pkd_score = 0.0
        for code in company.pkd_codes:
            for pref in prefixes:
                if str(code).startswith(str(pref)):
                    pkd_score = 100.0
                    break
            if pkd_score:
                break
        factors.append(f"pkd_codes={company.pkd_codes} required_prefixes={prefixes}")

    age_score = 100.0
    min_age_years = float(custom.get("min_company_age_years", 0))
    if min_age_years > 0:
        if not company.founding_date:
            age_score = 0.0
            factors.append(f"min_age_years={min_age_years} founding_date=missing")
        else:
            try:
                year = int(str(company.founding_date)[:4])
                this_year = time.gmtime().tm_year
                age_score = 100.0 if (this_year - year) >= min_age_years else 0.0
                factors.append(f"company_age_years={this_year - year} min={min_age_years}")
            except ValueError:
                age_score = 0.0
                factors.append(f"founding_date_parse_failed={company.founding_date}")

    score = (legal_score + msme_score + pkd_score + age_score) / 4.0
    return score, factors


def score_thematic_alignment(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    grant_text = " ".join(filter(None, [
        grant.display_name,
        grant.description or "",
    ])).lower()
    idea_kw = {kw.lower() for kw in (idea.keywords or [])}
    idea_text = (idea.title + " " + idea.description).lower()

    if not grant_text:
        factors.append("grant_text=empty")
        return 50.0, factors

    matches = 0
    for kw in idea_kw:
        if kw and kw in grant_text:
            matches += 1
    factors.append(f"keyword_matches={matches}/{len(idea_kw)}")

    domain_match = idea.domain and (idea.domain.lower() in grant_text)
    if domain_match:
        factors.append(f"domain_match={idea.domain}")

    base = 40.0
    if idea_kw:
        base += min(50.0, matches * 50.0 / max(1, len(idea_kw)))
    if domain_match:
        base += 10.0
    if any(tok in grant_text for tok in idea_text.split() if len(tok) > 4):
        base += 5.0
    return min(100.0, base), factors


def score_capacity(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    rd_total = sum(float(rec.get("budget_usd", 0.0)) for rec in (company.rd_budget_history or []))
    employees = company.employee_count or 0
    factors.append(f"rd_total_usd={rd_total} employees={employees}")
    rd_score = min(100.0, rd_total / 1000.0)
    employee_score = min(100.0, employees * 5.0)
    cert_score = min(100.0, 25.0 * len(company.innovation_certifications or []))
    score = (rd_score + employee_score + cert_score) / 3.0
    if not company.rd_budget_history and not company.innovation_certifications:
        score = max(score, 30.0)
    return score, factors


def score_competitive_position(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    rev = company.annual_revenue_usd or 0.0
    factors.append(f"annual_revenue_usd={rev}")
    if rev <= 0:
        return 50.0, factors
    if rev > 5_000_000:
        score = 90.0
    elif rev > 1_000_000:
        score = 75.0
    elif rev > 200_000:
        score = 60.0
    else:
        score = 45.0
    if company.innovation_certifications:
        score = min(100.0, score + 5.0 * len(company.innovation_certifications))
        factors.append(f"certifications={len(company.innovation_certifications)}")
    return score, factors


def score_regional_fit(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    if not grant.region:
        factors.append("grant_region=national")
        return 100.0, factors
    if (company.region or "").upper() == grant.region.upper():
        factors.append(f"company_region={company.region} matches grant_region={grant.region}")
        return 100.0, factors
    factors.append(f"company_region={company.region} grant_region={grant.region} mismatch")
    return 0.0, factors


def score_consortium_readiness(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    custom = grant.custom_criteria or {}
    if not custom.get("requires_consortium", False) and not idea.requires_consortium:
        factors.append("consortium_required=false")
        return 100.0, factors
    factors.append("consortium_required=true; pool lookup deferred to consortium.matcher")
    return 50.0, factors


def score_timeline_fit(
    company: Company,
    grant: GrantProgram,
    idea: IdeaContext,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    now = time.time()
    if grant.call_close_at <= 0:
        factors.append("call_close_at=unset")
        return 70.0, factors
    days = (grant.call_close_at - now) / 86400.0
    factors.append(f"days_to_close={int(days)}")
    if days < 0:
        return 0.0, factors
    if days >= 90:
        return 100.0, factors
    if days >= 30:
        return 80.0, factors
    if days >= 14:
        return 50.0, factors
    return 20.0, factors


COMPONENT_SCORERS = {
    "eligibility": score_eligibility,
    "thematic_alignment": score_thematic_alignment,
    "capacity": score_capacity,
    "competitive_position": score_competitive_position,
    "regional_fit": score_regional_fit,
    "consortium_readiness": score_consortium_readiness,
    "timeline_fit": score_timeline_fit,
}
