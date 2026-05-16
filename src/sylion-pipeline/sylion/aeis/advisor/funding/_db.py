"""Funding DB layer — uses shared PG pool from `sylion.aeis.advisor._db`.

Per `08_audit_revisions.md` Revision 2 the advisor layer is PG-only. The
canonical schema (`advisor_funding.*`) lives in `sylion/db/advisor_layer.sql`
and ships via Alembic revision `20260425_0002_advisor_layer.py`. This module
reads/writes pre-existing PG tables; it does NOT create them. SQLite remains
permitted only as in-memory test fixture (see
`tests/aeis/advisor/engine/_pg_test_pool.py`).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.funding._models import (
    Company,
    CompanyPerson,
    ConsortiumPartner,
    DEFAULT_COMPONENT_WEIGHTS,
    DEFAULT_HARD_FLOORS,
    FundingResearchLog,
    GrantProgram,
    ProfileComponentEntry,
    ScoringComponent,
    ScoringHistoryEntry,
    ScoringProfile,
    UNIVERSAL_COMPONENT_IDS,
)

log = logging.getLogger("sylion.aeis.advisor.funding._db")


_UNIVERSAL_COMPONENT_DESCRIPTIONS = {
    "eligibility": "Formal criteria: legal form, MSME, branch, location, age",
    "thematic_alignment": "Match between idea and grant call topic",
    "capacity": "Team experience, R&D budget, references",
    "competitive_position": "Comparison vs benchmark applicants in past calls",
    "regional_fit": "Company location vs regional grant requirements",
    "consortium_readiness": "Required consortium partners present or readily found",
    "timeline_fit": "Time-to-deadline vs project/company readiness",
}


def init_funding_schema() -> None:
    """Seed universal scoring components if missing.

    Schema itself lives in Alembic; this only seeds the catalog rows that the
    funding service expects to find on first use.
    """
    _seed_universal_components()


def reset_funding_db() -> None:
    """No-op in PG-only mode. Test fixtures own per-test reset."""
    return None


def get_funding_conn():
    """Return a pooled PG connection (context manager). Backward-compat shim."""
    return shared_db.get_pool().connection()


def _seed_universal_components() -> None:
    now = time.time()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        for cid in UNIVERSAL_COMPONENT_IDS:
            cur.execute(
                "SELECT 1 FROM advisor_funding.scoring_components WHERE component_id = %s",
                (cid,),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """INSERT INTO advisor_funding.scoring_components
                   (component_id, display_name, description, measurement_dsl, is_system, created_at)
                   VALUES (%s, %s, %s, %s, 1, %s)""",
                (
                    cid,
                    cid.replace("_", " ").title(),
                    _UNIVERSAL_COMPONENT_DESCRIPTIONS.get(cid, ""),
                    json.dumps({}),
                    now,
                ),
            )


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------


def insert_company(c: Company) -> None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.companies
               (company_id, operator_id, is_own, legal_name, legal_form, registration_number,
                tax_id, statistical_id, pkd_codes, country, region, size_category,
                employee_count, annual_revenue_usd, founding_date, is_msme, description,
                rd_budget_history, innovation_certifications, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                c.company_id, c.operator_id, int(c.is_own), c.legal_name,
                c.legal_form or None, c.registration_number or None,
                c.tax_id or None, c.statistical_id or None,
                json.dumps(c.pkd_codes), c.country, c.region or None,
                c.size_category or None, c.employee_count or None,
                c.annual_revenue_usd or None, c.founding_date or None,
                int(c.is_msme), c.description or None,
                json.dumps(c.rd_budget_history),
                json.dumps(c.innovation_certifications),
                c.created_at, c.updated_at,
            ),
        )


def update_company(company_id: str, patch: dict[str, Any]) -> None:
    init_funding_schema()
    if not patch:
        return
    allowed = {
        "legal_name", "legal_form", "registration_number", "tax_id",
        "statistical_id", "country", "region", "size_category", "employee_count",
        "annual_revenue_usd", "founding_date", "is_msme", "description",
    }
    cols = []
    params: list[Any] = []
    for k, v in patch.items():
        if k not in allowed:
            continue
        cols.append(f"{k} = %s")
        params.append(int(v) if k == "is_msme" else v)
    if "pkd_codes" in patch:
        cols.append("pkd_codes = %s")
        params.append(json.dumps(patch["pkd_codes"]))
    if "rd_budget_history" in patch:
        cols.append("rd_budget_history = %s")
        params.append(json.dumps(patch["rd_budget_history"]))
    if "innovation_certifications" in patch:
        cols.append("innovation_certifications = %s")
        params.append(json.dumps(patch["innovation_certifications"]))
    if not cols:
        return
    cols.append("updated_at = %s")
    params.append(time.time())
    params.append(company_id)
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE advisor_funding.companies SET {', '.join(cols)} WHERE company_id = %s",
            tuple(params),
        )


def fetch_company(company_id: str) -> Company | None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.companies WHERE company_id = %s",
            (company_id,),
        )
        row = cur.fetchone()
    return _row_to_company(row) if row else None


def fetch_companies_for_operator(operator_id: str) -> list[Company]:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.companies WHERE operator_id = %s ORDER BY created_at ASC",
            (operator_id,),
        )
        rows = cur.fetchall()
    return [_row_to_company(r) for r in rows]


def _maybe_load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return value


def _row_to_company(row: dict[str, Any]) -> Company:
    return Company(
        company_id=row["company_id"],
        operator_id=row["operator_id"],
        is_own=bool(row["is_own"]),
        legal_name=row["legal_name"],
        legal_form=row["legal_form"] or "",
        registration_number=row["registration_number"] or "",
        tax_id=row["tax_id"] or "",
        statistical_id=row["statistical_id"] or "",
        pkd_codes=_maybe_load(row["pkd_codes"], []),
        country=row["country"],
        region=row["region"] or "",
        size_category=row["size_category"] or "",
        employee_count=row["employee_count"] or 0,
        annual_revenue_usd=row["annual_revenue_usd"] or 0.0,
        founding_date=row["founding_date"] or "",
        is_msme=bool(row["is_msme"]),
        description=row["description"] or "",
        rd_budget_history=_maybe_load(row["rd_budget_history"], []),
        innovation_certifications=_maybe_load(row["innovation_certifications"], []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Company persons
# ---------------------------------------------------------------------------


def insert_company_person(p: CompanyPerson) -> None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.company_persons
               (person_id, company_id, full_name, role, ownership_pct, experience_summary,
                experience_years, qualifications, team_role, is_kp, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                p.person_id, p.company_id, p.full_name, p.role,
                p.ownership_pct or None, p.experience_summary or None,
                p.experience_years or None, json.dumps(p.qualifications),
                p.team_role or None, int(p.is_kp), p.created_at, p.updated_at,
            ),
        )


def fetch_persons_for_company(company_id: str) -> list[CompanyPerson]:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.company_persons WHERE company_id = %s "
            "ORDER BY created_at ASC",
            (company_id,),
        )
        rows = cur.fetchall()
    return [
        CompanyPerson(
            person_id=r["person_id"],
            company_id=r["company_id"],
            full_name=r["full_name"],
            role=r["role"],
            ownership_pct=r["ownership_pct"] or 0.0,
            experience_summary=r["experience_summary"] or "",
            experience_years=r["experience_years"] or 0,
            qualifications=_maybe_load(r["qualifications"], []),
            team_role=r["team_role"] or "",
            is_kp=bool(r["is_kp"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Grant programs
# ---------------------------------------------------------------------------


def insert_grant_program(g: GrantProgram) -> None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.grant_programs
               (program_id, program_code, display_name, source, country, region,
                managing_body, description, amount_min_usd, amount_max_usd,
                call_open_at, call_close_at, source_url, source_documents,
                scoring_profile_id, custom_criteria, is_active, is_user_loaded,
                loaded_by, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                g.program_id, g.program_code or None, g.display_name, g.source,
                g.country, g.region or None, g.managing_body or None,
                g.description or None, g.amount_min_usd or None,
                g.amount_max_usd or None, g.call_open_at or None,
                g.call_close_at or None, g.source_url or None,
                json.dumps(g.source_documents),
                g.scoring_profile_id or None,
                json.dumps(g.custom_criteria),
                int(g.is_active), int(g.is_user_loaded),
                g.loaded_by or None, g.created_at, g.updated_at,
            ),
        )


def update_grant_program(program_id: str, patch: dict[str, Any]) -> None:
    init_funding_schema()
    if not patch:
        return
    allowed = {"is_active", "scoring_profile_id", "display_name", "description"}
    cols = []
    params: list[Any] = []
    for k, v in patch.items():
        if k not in allowed:
            continue
        if k == "is_active":
            v = int(v)
        cols.append(f"{k} = %s")
        params.append(v)
    if not cols:
        return
    cols.append("updated_at = %s")
    params.append(time.time())
    params.append(program_id)
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE advisor_funding.grant_programs SET {', '.join(cols)} WHERE program_id = %s",
            tuple(params),
        )


def fetch_grant_program(program_id: str) -> GrantProgram | None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.grant_programs WHERE program_id = %s",
            (program_id,),
        )
        row = cur.fetchone()
    return _row_to_grant(row) if row else None


def fetch_active_grant_programs(
    *, country: str | None = None, region: str | None = None
) -> list[GrantProgram]:
    init_funding_schema()
    sql = "SELECT * FROM advisor_funding.grant_programs WHERE is_active = 1"
    params: list[Any] = []
    if country:
        sql += " AND country = %s"
        params.append(country)
    if region:
        sql += " AND (region = %s OR region IS NULL)"
        params.append(region)
    sql += " ORDER BY created_at ASC"
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [_row_to_grant(r) for r in rows]


def _row_to_grant(row: dict[str, Any]) -> GrantProgram:
    return GrantProgram(
        program_id=row["program_id"],
        program_code=row["program_code"] or "",
        display_name=row["display_name"],
        source=row["source"],
        country=row["country"],
        region=row["region"] or "",
        managing_body=row["managing_body"] or "",
        description=row["description"] or "",
        amount_min_usd=row["amount_min_usd"] or 0.0,
        amount_max_usd=row["amount_max_usd"] or 0.0,
        call_open_at=row["call_open_at"] or 0.0,
        call_close_at=row["call_close_at"] or 0.0,
        source_url=row["source_url"] or "",
        source_documents=_maybe_load(row["source_documents"], []),
        scoring_profile_id=row["scoring_profile_id"] or "",
        custom_criteria=_maybe_load(row["custom_criteria"], {}),
        is_active=bool(row["is_active"]),
        is_user_loaded=bool(row["is_user_loaded"]),
        loaded_by=row["loaded_by"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Scoring components / profiles
# ---------------------------------------------------------------------------


def fetch_components() -> list[ScoringComponent]:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.scoring_components ORDER BY component_id ASC"
        )
        rows = cur.fetchall()
    return [
        ScoringComponent(
            component_id=r["component_id"],
            display_name=r["display_name"],
            description=r["description"] or "",
            measurement_dsl=_maybe_load(r["measurement_dsl"], {}),
            is_system=bool(r["is_system"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


def insert_scoring_profile(p: ScoringProfile) -> None:
    init_funding_schema()
    components_json = json.dumps(
        [{"component_id": c.component_id, "weight": c.weight, "hard_floor": c.hard_floor}
         for c in p.components]
    )
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.scoring_profiles
               (profile_id, program_id, version, components, custom_criteria,
                total_weight, is_active, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                p.profile_id, p.program_id, p.version, components_json,
                json.dumps(p.custom_criteria), p.total_weight, int(p.is_active),
                p.created_at,
            ),
        )


def fetch_active_profile_for_program(program_id: str) -> ScoringProfile | None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.scoring_profiles "
            "WHERE program_id = %s AND is_active = 1 "
            "ORDER BY version DESC LIMIT 1",
            (program_id,),
        )
        row = cur.fetchone()
    return _row_to_profile(row) if row else None


def fetch_profile_by_id(profile_id: str) -> ScoringProfile | None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_funding.scoring_profiles WHERE profile_id = %s",
            (profile_id,),
        )
        row = cur.fetchone()
    return _row_to_profile(row) if row else None


def _row_to_profile(row: dict[str, Any]) -> ScoringProfile:
    raw = _maybe_load(row["components"], [])
    comps = [
        ProfileComponentEntry(
            component_id=c["component_id"],
            weight=float(c.get("weight", 0.0)),
            hard_floor=float(c.get("hard_floor", 0.0)),
        )
        for c in raw
    ]
    return ScoringProfile(
        profile_id=row["profile_id"],
        program_id=row["program_id"],
        version=row["version"],
        components=comps,
        custom_criteria=_maybe_load(row["custom_criteria"], {}),
        total_weight=row["total_weight"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )


def make_default_profile(program_id: str) -> ScoringProfile:
    """Build a default profile with universal weights summing to 100."""
    components = [
        ProfileComponentEntry(
            component_id=cid,
            weight=DEFAULT_COMPONENT_WEIGHTS[cid],
            hard_floor=DEFAULT_HARD_FLOORS.get(cid, 0.0),
        )
        for cid in UNIVERSAL_COMPONENT_IDS
    ]
    return ScoringProfile(program_id=program_id, components=components, total_weight=100.0)


# ---------------------------------------------------------------------------
# Scoring history
# ---------------------------------------------------------------------------


def insert_scoring_history(h: ScoringHistoryEntry) -> None:
    init_funding_schema()
    breakdown = [
        {
            "component_id": c.component_id,
            "component_name": c.component_name,
            "weight_in_grant": c.weight_in_grant,
            "score": c.score,
            "hard_floor": c.hard_floor,
            "floor_breached": c.floor_breached,
            "explanation": c.explanation,
            "driving_factors": c.driving_factors,
        }
        for c in h.component_breakdown
    ]
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.scoring_history
               (scoring_id, operator_id, company_id, idea_id, program_id,
                scoring_profile_id, total_score, component_breakdown,
                eligibility_floor_breached, triggering_event, card_id,
                llm_judge_audit_id, computed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                h.scoring_id, h.operator_id, h.company_id or None,
                h.idea_id or None, h.program_id, h.scoring_profile_id,
                h.total_score, json.dumps(breakdown),
                int(h.eligibility_floor_breached), h.triggering_event or None,
                h.card_id or None, h.llm_judge_audit_id or None, h.computed_at,
            ),
        )


def fetch_scoring_history(
    *, company_id: str = "", idea_id: str = "", program_id: str = "", limit: int = 50
) -> list[dict[str, Any]]:
    init_funding_schema()
    sql = "SELECT * FROM advisor_funding.scoring_history WHERE 1=1"
    params: list[Any] = []
    if company_id:
        sql += " AND company_id = %s"
        params.append(company_id)
    if idea_id:
        sql += " AND idea_id = %s"
        params.append(idea_id)
    if program_id:
        sql += " AND program_id = %s"
        params.append(program_id)
    sql += " ORDER BY computed_at DESC LIMIT %s"
    params.append(limit)
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Consortium pool
# ---------------------------------------------------------------------------


def insert_consortium_partner(p: ConsortiumPartner) -> None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.consortium_pool
               (partner_id, display_name, entity_type, country, region,
                qualifications, contact_info, added_by, notes, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                p.partner_id, p.display_name, p.entity_type, p.country or None,
                p.region or None, json.dumps(p.qualifications),
                json.dumps(p.contact_info), p.added_by or None, p.notes or None,
                p.created_at,
            ),
        )


def fetch_consortium_partners(
    *,
    entity_type: str | None = None,
    country: str | None = None,
    region: str | None = None,
) -> list[ConsortiumPartner]:
    init_funding_schema()
    sql = "SELECT * FROM advisor_funding.consortium_pool WHERE 1=1"
    params: list[Any] = []
    if entity_type:
        sql += " AND entity_type = %s"
        params.append(entity_type)
    if country:
        sql += " AND country = %s"
        params.append(country)
    if region:
        sql += " AND (region = %s OR region IS NULL OR region = '')"
        params.append(region)
    sql += " ORDER BY created_at ASC"
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [
        ConsortiumPartner(
            partner_id=r["partner_id"],
            display_name=r["display_name"],
            entity_type=r["entity_type"],
            country=r["country"] or "",
            region=r["region"] or "",
            qualifications=_maybe_load(r["qualifications"], []),
            contact_info=_maybe_load(r["contact_info"], {}),
            added_by=r["added_by"] or "",
            notes=r["notes"] or "",
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Research logs (token budget)
# ---------------------------------------------------------------------------


def insert_research_log(log_entry: FundingResearchLog) -> None:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_funding.research_logs
               (log_id, operator_id, research_purpose, prompt_tokens, response_tokens,
                cost_usd, model_id, external_research, related_card_id, performed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                log_entry.log_id, log_entry.operator_id, log_entry.research_purpose,
                log_entry.prompt_tokens, log_entry.response_tokens,
                log_entry.cost_usd, log_entry.model_id,
                int(log_entry.external_research), log_entry.related_card_id or None,
                log_entry.performed_at,
            ),
        )


def sum_research_tokens_for_period(
    *, operator_id: str, since_epoch: float
) -> int:
    init_funding_schema()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT COALESCE(SUM(prompt_tokens), 0) + COALESCE(SUM(response_tokens), 0)
               AS total
               FROM advisor_funding.research_logs
               WHERE operator_id = %s AND performed_at >= %s""",
            (operator_id, since_epoch),
        )
        row = cur.fetchone()
    return int(row["total"]) if row else 0
