"""
SYLION Funding Autopilot -- Program Scanner (FIX-100)

Automated scanners for funding programmes:
  - Horizon Europe / EU Funding & Tenders public snapshots
  - PARP/FENG public calls
  - Digital Europe / ECCC public calls
  - EU tenders relevant for quantum and secure connectivity

All scanners return FundingCall dataclasses.  scan_all() orchestrates,
deduplicates by call code, persists via FundingAutopilotStore, and
returns the combined list.

Match scoring uses TF-IDF cosine against company profile text.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import time
from typing import Any

from .config import funding_db_path
from .store import FundingAutopilotStore

log = logging.getLogger("sylion.funding_autopilot.program_scanner")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class FundingCall:
    call_id: str = ""
    programme_id: str = ""
    title: str = ""
    code: str = ""
    country: str = ""
    region: str = ""
    portal_url: str = ""
    opens_at: float | None = None
    closes_at: float | None = None
    min_project_budget: float = 0.0
    max_project_budget: float = 0.0
    grant_intensity_pct: float = 0.0
    trl_min: int = 0
    trl_max: int = 9
    requires_consortium: bool = False
    target_beneficiaries: list[str] = dataclasses.field(default_factory=list)
    themes: list[str] = dataclasses.field(default_factory=list)
    required_documents: list[str] = dataclasses.field(default_factory=list)
    required_partner_types: list[str] = dataclasses.field(default_factory=list)
    eligible_costs: list[str] = dataclasses.field(default_factory=list)
    evaluation_weights: dict = dataclasses.field(default_factory=dict)
    metadata: dict = dataclasses.field(default_factory=dict)

    def to_store_payload(self) -> dict[str, Any]:
        """Convert to the dict shape expected by FundingAutopilotStore.create_call."""
        return {
            "call_id": self.call_id,
            "programme_id": self.programme_id,
            "title": self.title,
            "code": self.code,
            "country": self.country,
            "region": self.region,
            "portal_url": self.portal_url,
            "opens_at": self.opens_at,
            "closes_at": self.closes_at,
            "min_project_budget": self.min_project_budget,
            "max_project_budget": self.max_project_budget,
            "grant_intensity_pct": self.grant_intensity_pct,
            "trl_min": self.trl_min,
            "trl_max": self.trl_max,
            "requires_consortium": self.requires_consortium,
            "target_beneficiaries": self.target_beneficiaries,
            "themes": self.themes,
            "required_documents": self.required_documents,
            "required_partner_types": self.required_partner_types,
            "eligible_costs": self.eligible_costs,
            "evaluation_weights": self.evaluation_weights,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Legacy scanner snapshots retained for migration history; runtime definitions below override them.
# ---------------------------------------------------------------------------

def _future_ts(days: int) -> float:
    return time.time() + days * 86400


def scan_horizon_europe() -> list[FundingCall]:
    """Legacy Horizon Europe sample; superseded by the source-backed runtime definition below."""
    programme_id = "programme_horizon_europe"
    now = time.time()
    return [
        FundingCall(
            programme_id=programme_id,
            title="HORIZON-CL4-2025-Digital-EMERGING",
            code="HE-2025-DIGITAL-01",
            country="EU",
            region="",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HE-2025-DIGITAL-01",
            opens_at=now,
            closes_at=_future_ts(90),
            min_project_budget=2_000_000,
            max_project_budget=5_000_000,
            grant_intensity_pct=70.0,
            trl_min=4,
            trl_max=6,
            requires_consortium=True,
            target_beneficiaries=["SME", "RTO", "Large Enterprise"],
            themes=["AI", "Digital Twins", "Cloud Computing"],
            required_documents=["Part A", "Part B", "Mandate"],
            required_partner_types=["Coordinator", "Partner"],
            eligible_costs=["Personnel", "Subcontracting", "Equipment"],
            metadata={"programme": "Horizon Europe", "pillar": "Digital, Industry and Space"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="HORIZON-CL4-2025-Space-EO",
            code="HE-2025-SPACE-02",
            country="EU",
            region="",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HE-2025-SPACE-02",
            opens_at=now,
            closes_at=_future_ts(120),
            min_project_budget=1_500_000,
            max_project_budget=4_000_000,
            grant_intensity_pct=70.0,
            trl_min=3,
            trl_max=5,
            requires_consortium=True,
            target_beneficiaries=["SME", "RTO"],
            themes=["Earth Observation", "Satellite Data", "Climate Monitoring"],
            required_documents=["Part A", "Part B"],
            eligible_costs=["Personnel", "Equipment", "Travel"],
            metadata={"programme": "Horizon Europe", "pillar": "Digital, Industry and Space"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="HORIZON-CL5-2025-Climate-Neutral",
            code="HE-2025-CLIMATE-03",
            country="EU",
            region="",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HE-2025-CLIMATE-03",
            opens_at=now,
            closes_at=_future_ts(60),
            min_project_budget=3_000_000,
            max_project_budget=8_000_000,
            grant_intensity_pct=60.0,
            trl_min=5,
            trl_max=7,
            requires_consortium=True,
            target_beneficiaries=["Large Enterprise", "RTO", "SME"],
            themes=["Green Hydrogen", "Carbon Capture", "Circular Economy"],
            required_documents=["Part A", "Part B", "Financial Declaration"],
            eligible_costs=["Personnel", "Subcontracting", "Consumables"],
            metadata={"programme": "Horizon Europe", "pillar": "Climate, Energy and Mobility"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="HORIZON-CL3-2025-Security-Cyber",
            code="HE-2025-SECURITY-04",
            country="EU",
            region="",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HE-2025-SECURITY-04",
            opens_at=now,
            closes_at=_future_ts(75),
            min_project_budget=1_000_000,
            max_project_budget=3_000_000,
            grant_intensity_pct=70.0,
            trl_min=4,
            trl_max=6,
            requires_consortium=True,
            target_beneficiaries=["SME", "RTO"],
            themes=["Cybersecurity", "AI for Security", "Resilient Infrastructure"],
            required_documents=["Part A", "Part B"],
            eligible_costs=["Personnel", "Equipment"],
            metadata={"programme": "Horizon Europe", "pillar": "Civil Security for Society"},
        ),
    ]


def scan_ncbr() -> list[FundingCall]:
    """Legacy NCBR sample; superseded by the source-backed runtime definition below."""
    programme_id = "programme_ncbr"
    now = time.time()
    return [
        FundingCall(
            programme_id=programme_id,
            title="Szybka Ścieżka – Sztuczna Inteligencja",
            code="NCBR-2025-SZ-AI-01",
            country="PL",
            region="",
            portal_url="https://www.ncbr.gov.pl/fundusze-europejskie/szybka-sciezka/",
            opens_at=now,
            closes_at=_future_ts(45),
            min_project_budget=500_000,
            max_project_budget=2_000_000,
            grant_intensity_pct=80.0,
            trl_min=3,
            trl_max=6,
            requires_consortium=False,
            target_beneficiaries=["SME", "Large Enterprise"],
            themes=["AI", "Machine Learning", "NLP"],
            required_documents=["Wniosek", "Biznesplan", "Oświadczenie"],
            eligible_costs=["Personnel", "Equipment", "Software"],
            metadata={"programme": "NCBR", "scheme": "Szybka Ścieżka"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="Szybka Ścieżka – Zielona Energetyka",
            code="NCBR-2025-SZ-GREEN-02",
            country="PL",
            region="",
            portal_url="https://www.ncbr.gov.pl/fundusze-europejskie/szybka-sciezka/",
            opens_at=now,
            closes_at=_future_ts(60),
            min_project_budget=400_000,
            max_project_budget=1_500_000,
            grant_intensity_pct=80.0,
            trl_min=4,
            trl_max=7,
            requires_consortium=False,
            target_beneficiaries=["SME"],
            themes=["Renewable Energy", "Energy Storage", "Smart Grid"],
            required_documents=["Wniosek", "Biznesplan"],
            eligible_costs=["Personnel", "Equipment", "Consumables"],
            metadata={"programme": "NCBR", "scheme": "Szybka Ścieżka"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="Programy Badawcze – Cyberbezpieczeństwo",
            code="NCBR-2025-PB-CYBER-03",
            country="PL",
            region="",
            portal_url="https://www.ncbr.gov.pl/programy-badawcze/",
            opens_at=now,
            closes_at=_future_ts(100),
            min_project_budget=1_000_000,
            max_project_budget=5_000_000,
            grant_intensity_pct=100.0,
            trl_min=2,
            trl_max=5,
            requires_consortium=True,
            target_beneficiaries=["RTO", "University", "SME"],
            themes=["Cybersecurity", "Cryptography", "Quantum Safety"],
            required_documents=["Wniosek", "Konsorcjum", "Harmonogram"],
            eligible_costs=["Personnel", "Equipment", "Travel", "Subcontracting"],
            metadata={"programme": "NCBR", "scheme": "Programy Badawcze"},
        ),
    ]


def scan_feng() -> list[FundingCall]:
    """Legacy FENG sample; superseded by the Polish source-backed runtime definition below."""
    programme_id = "programme_feng"
    now = time.time()
    return [
        FundingCall(
            programme_id=programme_id,
            title="Klimaschutz in Unternehmen – Industrie 4.0",
            code="FENG-2025-KLIMA-01",
            country="DE",
            region="BW",
            portal_url="https://www.energie-forschung.de/foerderung/",
            opens_at=now,
            closes_at=_future_ts(80),
            min_project_budget=1_000_000,
            max_project_budget=3_500_000,
            grant_intensity_pct=50.0,
            trl_min=5,
            trl_max=8,
            requires_consortium=False,
            target_beneficiaries=["SME", "Large Enterprise"],
            themes=["Energy Efficiency", "Industry 4.0", "Decarbonisation"],
            required_documents=["Antrag", "Finanzplan", "Umweltbericht"],
            eligible_costs=["Personnel", "Equipment", "Consulting"],
            metadata={"programme": "FENG", "level": "federal"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="Energieforschung – Wasserstofftechnologien",
            code="FENG-2025-H2-02",
            country="DE",
            region="BY",
            portal_url="https://www.energie-forschung.de/foerderung/",
            opens_at=now,
            closes_at=_future_ts(110),
            min_project_budget=2_000_000,
            max_project_budget=6_000_000,
            grant_intensity_pct=45.0,
            trl_min=4,
            trl_max=7,
            requires_consortium=True,
            target_beneficiaries=["RTO", "SME", "Large Enterprise"],
            themes=["Hydrogen", "Fuel Cells", "Electrolysis"],
            required_documents=["Antrag", "Konsortiumsvereinbarung", "Technische Beschreibung"],
            eligible_costs=["Personnel", "Equipment", "Subcontracting"],
            metadata={"programme": "FENG", "level": "federal"},
        ),
    ]


def scan_regional() -> list[FundingCall]:
    """Legacy regional sample; superseded by the source-backed runtime definition below."""
    programme_id = "programme_regional"
    now = time.time()
    return [
        FundingCall(
            programme_id=programme_id,
            title="EFRR 2021-2027 – Digitalisierung der Wirtschaft",
            code="REG-2025-EFRR-DIGI-01",
            country="DE",
            region="Sachsen",
            portal_url="https://www.free-state-saxony.de/efrr/",
            opens_at=now,
            closes_at=_future_ts(50),
            min_project_budget=200_000,
            max_project_budget=1_000_000,
            grant_intensity_pct=50.0,
            trl_min=6,
            trl_max=9,
            requires_consortium=False,
            target_beneficiaries=["SME"],
            themes=["Digitalisation", "E-commerce", "Cloud Migration"],
            required_documents=["Antrag", "Kostenplan"],
            eligible_costs=["Software", "Personnel", "Training"],
            metadata={"programme": "Regional", "fund": "EFRR"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="Inteligentny Rozwój – Innowacje Mazowsze",
            code="REG-2025-FE-MZ-02",
            country="PL",
            region="Mazowieckie",
            portal_url="https://www.mazowia.eu/fundusze-europejskie/",
            opens_at=now,
            closes_at=_future_ts(65),
            min_project_budget=300_000,
            max_project_budget=1_200_000,
            grant_intensity_pct=70.0,
            trl_min=5,
            trl_max=8,
            requires_consortium=False,
            target_beneficiaries=["SME"],
            themes=["Innovation", "R&D", "Product Development"],
            required_documents=["Wniosek", "Plan finansowy"],
            eligible_costs=["Personnel", "Equipment", "Materials"],
            metadata={"programme": "Regional", "fund": "FE"},
        ),
        FundingCall(
            programme_id=programme_id,
            title="Horizon Teaming – Widening",
            code="REG-2025-WIDENING-03",
            country="EU",
            region="",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/widening",
            opens_at=now,
            closes_at=_future_ts(95),
            min_project_budget=1_000_000,
            max_project_budget=2_500_000,
            grant_intensity_pct=100.0,
            trl_min=3,
            trl_max=5,
            requires_consortium=True,
            target_beneficiaries=["University", "RTO"],
            themes=["Widening", "Excellence", "Capacity Building"],
            required_documents=["Part A", "Part B", "Mandate"],
            eligible_costs=["Personnel", "Travel", "Training"],
            metadata={"programme": "Regional", "fund": "Widening"},
        ),
    ]


# ---------------------------------------------------------------------------
# Source-backed scanner snapshots used by runtime
# ---------------------------------------------------------------------------

def _date_ts(value: str) -> float:
    parsed = dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return parsed.timestamp()


def scan_horizon_europe() -> list[FundingCall]:
    """Return source-backed Horizon Europe Cluster 4 calls verified on 2026-04-29."""
    return [
        FundingCall(
            programme_id="programme_horizon_europe",
            title="HORIZON-CL4-2026-04-DATA-06: Efficient and compliant access to and use of data",
            code="HORIZON-CL4-2026-04-DATA-06",
            country="EU",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/horizon-cl4-2026-04-data-06",
            opens_at=_date_ts("2026-01-15"),
            closes_at=_date_ts("2026-04-15"),
            min_project_budget=12_500_000,
            max_project_budget=25_000_000,
            grant_intensity_pct=70.0,
            trl_min=6,
            trl_max=8,
            requires_consortium=True,
            target_beneficiaries=["SME", "MŚP", "Mid-cap", "Large Enterprise", "RTO"],
            themes=["AI", "synthetic data", "data compliance", "privacy", "sovereign data"],
            required_documents=["Part A", "Part B", "DoH", "consortium agreement", "ethics self-assessment"],
            required_partner_types=["coordinator", "industry validator", "RTO"],
            eligible_costs=["personnel", "equipment", "subcontracting", "travel"],
            metadata={
                "source_url": "https://hadea.ec.europa.eu/news/horizon-europe-2026-digital-calls-now-published-2026-01-14_en",
                "verified_at": "2026-04-29",
                "programme": "Horizon Europe",
                "pillar": "Cluster 4 - Digital, Industry and Space",
            },
        ),
        FundingCall(
            programme_id="programme_horizon_europe",
            title="HORIZON-CL4-2026-04-DATA-02: Open Internet Stack Sovereign Solutions",
            code="HORIZON-CL4-2026-04-DATA-02",
            country="EU",
            portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/horizon-cl4-2026-04-data-02",
            opens_at=_date_ts("2026-01-15"),
            closes_at=_date_ts("2026-04-15"),
            min_project_budget=2_000_000,
            max_project_budget=6_000_000,
            grant_intensity_pct=70.0,
            trl_min=4,
            trl_max=7,
            requires_consortium=True,
            target_beneficiaries=["SME", "MŚP", "RTO", "open-source foundation"],
            themes=["open internet stack", "sovereign infrastructure", "cybersecurity", "open source"],
            required_documents=["Part A", "Part B", "DoH", "consortium agreement"],
            required_partner_types=["coordinator", "open-source maintainer", "cybersecurity validator"],
            eligible_costs=["personnel", "software", "equipment", "travel"],
            metadata={
                "source_url": "https://hadea.ec.europa.eu/news/horizon-europe-2026-digital-calls-now-published-2026-01-14_en",
                "verified_at": "2026-04-29",
                "programme": "Horizon Europe",
                "pillar": "Cluster 4 - Digital, Industry and Space",
            },
        ),
    ]


def scan_ncbr() -> list[FundingCall]:
    """NCBR is not auto-seeded without a current source-backed open call."""
    return []


def scan_feng() -> list[FundingCall]:
    """Return source-backed Polish FENG/PARP calls verified on 2026-04-29."""
    return [
        FundingCall(
            programme_id="programme_feng",
            title="Ścieżka SMART 2026: wdrożenie wyników prac B+R dla MŚP",
            code="PARP-SMART-WDROZENIA-2026-05",
            country="PL",
            region="Polska",
            portal_url="https://www.parp.gov.pl/component/content/article/90493%3Ado-50-mln-zl-na-wdrozenie-innowacji-parp-oglasza-nabor-w-sciezce-smart",
            opens_at=_date_ts("2026-05-14"),
            closes_at=_date_ts("2026-06-11"),
            min_project_budget=500_000,
            max_project_budget=50_000_000,
            grant_intensity_pct=70.0,
            trl_min=6,
            trl_max=9,
            requires_consortium=False,
            target_beneficiaries=["SME", "MŚP"],
            themes=["B+R", "wdrożenie innowacji", "AI", "cyberbezpieczeństwo", "kryptografia"],
            required_documents=["financial_statement", "tax_clearance", "social_security_clearance", "incorporation_document", "model_finansowy", "wniosek"],
            required_partner_types=[],
            eligible_costs=["personel", "sprzęt", "podwykonawstwo", "certyfikacja", "wdrożenie"],
            metadata={
                "source_url": "https://www.parp.gov.pl/component/content/article/90493%3Ado-50-mln-zl-na-wdrozenie-innowacji-parp-oglasza-nabor-w-sciezce-smart",
                "verified_at": "2026-04-29",
                "programme": "FENG Ścieżka SMART",
                "institution": "PARP",
                "budget_note": "700 mln zł, do 50 mln zł dotacji według komunikatu PARP z 2026-04-29",
            },
        ),
        FundingCall(
            programme_id="programme_feng",
            title="Ścieżka SMART - nabór projektów B+R nr FENG.01.01-IP.02-001/26",
            code="FENG.01.01-IP.02-001/26",
            country="PL",
            region="Polska",
            portal_url="https://feng.parp.gov.pl/component/grants/grants/sciezka-smart",
            opens_at=_date_ts("2026-02-26"),
            closes_at=_date_ts("2026-03-31"),
            min_project_budget=500_000,
            max_project_budget=50_000_000,
            grant_intensity_pct=70.0,
            trl_min=3,
            trl_max=8,
            requires_consortium=False,
            target_beneficiaries=["SME", "MŚP"],
            themes=["B+R", "innowacje", "AI", "cyberbezpieczeństwo", "kryptografia postkwantowa"],
            required_documents=["financial_statement", "tax_clearance", "social_security_clearance", "incorporation_document", "model_finansowy", "wniosek"],
            required_partner_types=[],
            eligible_costs=["personel", "sprzęt", "podwykonawstwo", "badania przemysłowe", "prace rozwojowe"],
            metadata={
                "source_url": "https://feng.parp.gov.pl/component/grants/grants/sciezka-smart",
                "verified_at": "2026-04-29",
                "programme": "FENG Ścieżka SMART",
                "institution": "PARP",
                "status_note": "nabór zakończony 2026-03-31, służy do testu guardów daty",
            },
        ),
    ]


def scan_regional() -> list[FundingCall]:
    """Return source-backed EU digital and tender opportunities verified on 2026-04-29."""
    return [
        FundingCall(
            programme_id="programme_digital_europe",
            title="Digital Europe / ECCC: AI powered cybersecurity and cyber resilience calls",
            code="DIGITAL-ECCC-2025-CYBER-04",
            country="EU",
            portal_url="https://digital-strategy.ec.europa.eu/hu/node/14655",
            opens_at=_date_ts("2025-10-28"),
            closes_at=_date_ts("2026-03-31"),
            min_project_budget=500_000,
            max_project_budget=10_000_000,
            grant_intensity_pct=50.0,
            trl_min=5,
            trl_max=9,
            requires_consortium=True,
            target_beneficiaries=["SME", "MŚP", "public authority", "RTO"],
            themes=["AI cybersecurity", "cyber resilience", "SME uptake", "readiness testing"],
            required_documents=["Part A", "Part B", "security declaration", "consortium agreement"],
            required_partner_types=["cybersecurity competence centre", "SME pilot", "public authority"],
            eligible_costs=["personnel", "equipment", "subcontracting", "testing"],
            metadata={
                "source_url": "https://digital-strategy.ec.europa.eu/hu/node/14655",
                "verified_at": "2026-04-29",
                "programme": "Digital Europe Programme",
                "status_note": "nabór zakończony 2026-03-31, używany do testu guardów daty",
            },
        ),
        FundingCall(
            programme_id="programme_eu_tenders",
            title="IRIS² / QKD microsatellite pilot mission for quantum key distribution",
            code="EC-CNECT/2025/OP/0129",
            country="EU",
            portal_url="https://digital-strategy.ec.europa.eu/en/funding/call-tenders-microsatellite-pilot-mission-validate-quantum-key-distribution-qkd-technology-space",
            opens_at=_date_ts("2026-02-17"),
            closes_at=_date_ts("2026-05-18"),
            min_project_budget=1_000_000,
            max_project_budget=20_000_000,
            grant_intensity_pct=100.0,
            trl_min=5,
            trl_max=8,
            requires_consortium=True,
            target_beneficiaries=["SME", "MŚP", "Large Enterprise", "RTO"],
            themes=["quantum key distribution", "QKD", "secure connectivity", "microsatellite", "quantum networks"],
            required_documents=["tender offer", "technical specification", "financial offer", "legal entity form"],
            required_partner_types=["space integrator", "quantum payload provider", "security validator"],
            eligible_costs=["personnel", "equipment", "subcontracting", "testing", "space validation"],
            metadata={
                "source_url": "https://digital-strategy.ec.europa.eu/en/funding/call-tenders-microsatellite-pilot-mission-validate-quantum-key-distribution-qkd-technology-space",
                "verified_at": "2026-04-29",
                "programme": "EU tender / IRIS²",
                "institution": "European Commission DG CNECT",
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def scan_all(since_days: int = 30,
             force_refresh: bool = False,
             store: FundingAutopilotStore | None = None) -> list[FundingCall]:
    """Run all programme scanners, deduplicate by code, persist new calls.

    Returns only calls that are still open. Closed source snapshots are kept
    in scanner definitions as guard fixtures, but they must not be persisted
    or displayed as active operator suggestions.
    """
    now = time.time()
    all_calls: list[FundingCall] = []
    all_calls.extend(scan_horizon_europe())
    all_calls.extend(scan_ncbr())
    all_calls.extend(scan_feng())
    all_calls.extend(scan_regional())

    log.info("scan_all: found %d raw calls", len(all_calls))

    # Deduplicate by code, then keep only currently open calls.
    seen: set[str] = set()
    deduped: list[FundingCall] = []
    for call in all_calls:
        if call.code and call.code in seen:
            continue
        if call.code:
            seen.add(call.code)
        if _is_open_call(call, now):
            deduped.append(call)
        else:
            log.info("scan_all: excluded closed call %s", call.code or call.title)

    log.info("scan_all: %d after dedup", len(deduped))

    # Persist via store
    _store = store or FundingAutopilotStore(db_path=funding_db_path())
    _ensure_programmes(_store)
    _delete_closed_calls(_store, now)

    existing_codes = _existing_call_codes(_store)
    inserted = 0
    skipped = 0

    for call in deduped:
        if call.code in existing_codes and not force_refresh:
            skipped += 1
            continue
        try:
            if force_refresh and call.code in existing_codes:
                _delete_call_by_code(_store, call.code)
            _store.create_call(call.to_store_payload())
            inserted += 1
        except Exception as exc:
            log.warning("Failed to persist call %s: %s", call.code, exc)

    log.info("scan_all: inserted=%d skipped=%d", inserted, skipped)
    return deduped


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def _ensure_programmes(store: FundingAutopilotStore) -> None:
    """Create source programme records if missing."""
    programmes = {
        "programme_horizon_europe": {
            "programme_id": "programme_horizon_europe",
            "source_id": "scanner",
            "name": "Horizon Europe",
            "country": "EU",
            "institution": "European Commission",
            "funding_type": "grant",
        },
        "programme_ncbr": {
            "programme_id": "programme_ncbr",
            "source_id": "scanner",
            "name": "NCBR",
            "country": "PL",
            "institution": "Narodowe Centrum Badań i Rozwoju",
            "funding_type": "grant",
        },
        "programme_feng": {
            "programme_id": "programme_feng",
            "source_id": "scanner",
            "name": "FENG Ścieżka SMART",
            "country": "PL",
            "institution": "PARP",
            "funding_type": "grant",
        },
        "programme_regional": {
            "programme_id": "programme_regional",
            "source_id": "scanner",
            "name": "Regional / Cohesion",
            "country": "EU",
            "institution": "European Regional Development Fund",
            "funding_type": "grant",
        },
        "programme_digital_europe": {
            "programme_id": "programme_digital_europe",
            "source_id": "scanner",
            "name": "Digital Europe Programme",
            "country": "EU",
            "institution": "European Commission / ECCC",
            "funding_type": "grant",
        },
        "programme_eu_tenders": {
            "programme_id": "programme_eu_tenders",
            "source_id": "scanner",
            "name": "EU Tenders / IRIS²",
            "country": "EU",
            "institution": "European Commission DG CNECT",
            "funding_type": "tender",
        },
    }
    for pid, payload in programmes.items():
        if not store.get_programme(pid):
            try:
                store.create_programme(payload)
            except Exception as exc:
                log.debug("programme %s already exists or error: %s", pid, exc)


def _existing_call_codes(store: FundingAutopilotStore) -> set[str]:
    """Return set of existing call codes in the store."""
    rows = store.list_calls()
    return {r.get("code", "") for r in rows if r.get("code")}


def _is_open_call(call: FundingCall, now: float | None = None) -> bool:
    """Return True when a scanner call can still be acted on."""
    if call.closes_at is None:
        return True
    return float(call.closes_at) >= float(now if now is not None else time.time())


def _is_open_row(row: dict[str, Any], now: float | None = None) -> bool:
    """Return True when a stored call can still be acted on."""
    closes_at = row.get("closes_at")
    if closes_at is None:
        return True
    return float(closes_at) >= float(now if now is not None else time.time())


def _delete_closed_calls(store: FundingAutopilotStore, now: float | None = None) -> int:
    """Delete closed calls during force refresh so stale suggestions vanish."""
    cutoff = float(now if now is not None else time.time())
    conn = store._get_conn()
    cur = conn.execute(
        "DELETE FROM funding_calls WHERE closes_at IS NOT NULL AND closes_at < ?",
        (cutoff,),
    )
    conn.commit()
    deleted = int(cur.rowcount or 0)
    if deleted:
        try:
            from sylion.funding_autopilot.store import _invalidate_funding_cache
            _invalidate_funding_cache()
        except Exception:                          # noqa: BLE001
            log.warning("funding.programs cache invalidation failed", exc_info=True)
    return deleted


def _delete_call_by_code(store: FundingAutopilotStore, code: str) -> None:
    """Delete all calls with the given code (used by force_refresh).

    Phase 3 W1.3: invalidates the funding.programs cache.
    """
    conn = store._get_conn()
    conn.execute("DELETE FROM funding_calls WHERE code = ?", (code,))
    conn.commit()
    try:
        from sylion.funding_autopilot.store import _invalidate_funding_cache
        _invalidate_funding_cache()
    except Exception:                              # noqa: BLE001
        log.warning("funding.programs cache invalidation failed", exc_info=True)


# ---------------------------------------------------------------------------
# Match scoring
# ---------------------------------------------------------------------------

def _profile_text(profile: dict[str, Any]) -> str:
    """Extract searchable text from a company profile dict."""
    parts: list[str] = []
    for key in (
        "description",
        "sectors",
        "keywords",
        "tech_stack",
        "country",
        "region",
        "technologies",
        "products",
        "services",
        "team_competencies",
        "strategic_goals",
        "export_markets",
    ):
        val = profile.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(v) for v in val)
    return " ".join(parts).lower()


def _call_text(call: FundingCall | dict) -> str:
    """Extract searchable text from a FundingCall or store dict."""
    if isinstance(call, FundingCall):
        parts = [call.title, call.country, call.region]
        parts.extend(call.themes)
        parts.extend(call.target_beneficiaries)
        meta = call.metadata or {}
    else:
        parts = [call.get("title", ""), call.get("country", ""), call.get("region", "")]
        parts.extend(call.get("themes_json", []) or [])
        parts.extend(call.get("target_beneficiaries_json", []) or [])
        meta = call.get("metadata_json", {}) or {}
    parts.append(meta.get("programme", ""))
    parts.append(meta.get("pillar", ""))
    return " ".join(str(p) for p in parts if p).lower()


def compute_match_scores(company_id: str = "default",
                         store: FundingAutopilotStore | None = None) -> list[dict[str, Any]]:
    """Return funding calls scored by TF-IDF cosine vs company profile.

    Each result dict contains the call row plus `match_score` (0.0-1.0).
    """
    _store = store or FundingAutopilotStore(db_path=funding_db_path())
    profile = _store.get_company_profile(company_id)
    if profile is None:
        log.warning("No company profile for %s; returning un-scored calls", company_id)
        calls = [c for c in _store.list_calls() if _is_open_row(c)]
        for c in calls:
            c["match_score"] = 0.0
        return calls

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception as exc:
        log.warning("scikit-learn not available (%s); falling back to keyword overlap", exc)
        return _keyword_overlap_scores(_store, profile)

    calls = [c for c in _store.list_calls() if _is_open_row(c)]
    if not calls:
        return []

    profile_txt = _profile_text(profile)
    call_texts = [_call_text(c) for c in calls]

    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf = vectorizer.fit_transform([profile_txt] + call_texts)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()
    except ValueError:
        # Empty vocabulary
        for c in calls:
            c["match_score"] = 0.0
        return calls

    for idx, c in enumerate(calls):
        c["match_score"] = round(float(sims[idx]), 4)

    return sorted(calls, key=lambda x: x["match_score"], reverse=True)


def _keyword_overlap_scores(store: FundingAutopilotStore,
                            profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback keyword-overlap scorer when sklearn is missing."""
    calls = [c for c in store.list_calls() if _is_open_row(c)]
    profile_words = set(_profile_text(profile).split())
    for c in calls:
        call_words = set(_call_text(c).split())
        overlap = profile_words & call_words
        total = profile_words | call_words
        c["match_score"] = round(len(overlap) / len(total), 4) if total else 0.0
    return sorted(calls, key=lambda x: x["match_score"], reverse=True)
