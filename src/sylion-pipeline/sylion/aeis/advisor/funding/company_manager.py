"""Company + person CRUD for the funding advisor."""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import Company, CompanyPerson


def create_company(
    *,
    operator_id: str,
    legal_name: str,
    country: str,
    is_own: bool = True,
    legal_form: str = "",
    region: str = "",
    registration_number: str = "",
    tax_id: str = "",
    statistical_id: str = "",
    pkd_codes: list[str] | None = None,
    size_category: str = "",
    is_msme: bool = False,
    employee_count: int = 0,
    annual_revenue_usd: float = 0.0,
    founding_date: str = "",
    description: str = "",
    rd_budget_history: list[dict[str, Any]] | None = None,
    innovation_certifications: list[dict[str, Any]] | None = None,
) -> Company:
    company = Company(
        operator_id=operator_id,
        is_own=is_own,
        legal_name=legal_name,
        legal_form=legal_form,
        country=country,
        region=region,
        registration_number=registration_number,
        tax_id=tax_id,
        statistical_id=statistical_id,
        pkd_codes=list(pkd_codes or []),
        size_category=size_category,
        is_msme=is_msme,
        employee_count=employee_count,
        annual_revenue_usd=annual_revenue_usd,
        founding_date=founding_date,
        description=description,
        rd_budget_history=list(rd_budget_history or []),
        innovation_certifications=list(innovation_certifications or []),
    )
    _db.insert_company(company)
    return company


def update_company(company_id: str, patch: dict[str, Any]) -> Company | None:
    _db.update_company(company_id, patch)
    return _db.fetch_company(company_id)


def get_company(company_id: str) -> Company | None:
    return _db.fetch_company(company_id)


def list_companies(operator_id: str) -> list[Company]:
    return _db.fetch_companies_for_operator(operator_id)


def attach_person(
    *,
    company_id: str,
    full_name: str,
    role: str,
    ownership_pct: float = 0.0,
    experience_summary: str = "",
    experience_years: int = 0,
    qualifications: list[dict[str, Any]] | None = None,
    team_role: str = "",
    is_kp: bool = False,
) -> CompanyPerson:
    person = CompanyPerson(
        company_id=company_id,
        full_name=full_name,
        role=role,
        ownership_pct=ownership_pct,
        experience_summary=experience_summary,
        experience_years=experience_years,
        qualifications=list(qualifications or []),
        team_role=team_role,
        is_kp=is_kp,
    )
    _db.insert_company_person(person)
    return person


def list_persons(company_id: str) -> list[CompanyPerson]:
    return _db.fetch_persons_for_company(company_id)
