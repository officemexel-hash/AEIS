"""
cost_allocation.py — Transfer Pricing Cost Allocation Engine
SYLION sp. z o.o. (PL) ↔ RSDG GmbH (DE)

Metodologia:
  - OECD Transfer Pricing Guidelines 2022, Chapter VII (Intra-group services)
  - Arm's length principle: Article 9 OECD Model Tax Convention
  - Metoda: Cost Plus (CPM) z markup 5% (OECD BEPS Action 8-10, par. 7.61)
    dla low value-adding intra-group services

Typy transakcji:
  1. PL → DE: Usługi programistyczne (dev services)
     Podstawa: cost bezpośredni user_id przypisanego do PL
     Markup: 5–8% arm's length (default 5% OECD simplified approach)

  2. DE → PL: Licencja IP / Royalty SaaS
     Podstawa: % przychodu SaaS SYLION PL (konfigurowalne, default 3%)
     Metoda: CUP / TNMM

  3. Wspólna infrastruktura (VPS, API baseline): split proporcjonalny do user count

  4. Wspólne R&D: split 60% PL / 40% DE (Cost Contribution Arrangement)

Schemat cost_log (SQLite, unified AEIS runtime DB):
  id, ts, run_id, agent_id, model_id, provider, model_name,
  tokens_in, tokens_out, cost_usd, latency_ms, stage, success, error
  + user_id (Cluster R migration, db.py line ~515)

Uwaga: user_id nie jest w bazowym CREATE TABLE SNAPSHOT (dodany w v5.9.1 R).
       Kolumna user_id mapuje na company poprzez USER_COMPANY_MAP poniżej.
"""

from __future__ import annotations

import sqlite3
import calendar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------------------------

# Mapowanie user_id → company
# Konwencja: user_id zaczyna się od prefiksu firmy lub jest jawnie wymieniony
# Uzupełnij przed produkcyjnym uruchomieniem!
USER_COMPANY_MAP: Dict[str, str] = {
    # SYLION PL — dev team
    "dev_pl_jan": "SYLION_PL",
    "dev_pl_anna": "SYLION_PL",
    "dev_pl_piotr": "SYLION_PL",
    "dev_pl_marta": "SYLION_PL",
    "(system)": "SYLION_PL",   # pipeline system calls — domyślnie PL
    # RSDG DE — prod/ops team
    "prod_de_system": "RSDG_DE",
    "ops_de_thomas": "RSDG_DE",
    "ops_de_lisa": "RSDG_DE",
}

# Prefiks auto-mapowania (jeśli user_id nie jest jawnie wymieniony)
USER_PREFIX_MAP: Dict[str, str] = {
    "dev_pl_": "SYLION_PL",
    "dev_pl": "SYLION_PL",
    "prod_de_": "RSDG_DE",
    "ops_de_": "RSDG_DE",
}

COMPANIES = ("SYLION_PL", "RSDG_DE")

# Dostawcy klasyfikowani jako SHARED INFRA (split proporcjonalny)
SHARED_INFRA_PROVIDERS = {"vps", "hetzner", "ovh", "cloudflare", "aws", "gcp"}

# Dostawcy klasyfikowani jako DEV/LLM (przypisanie per user)
LLM_PROVIDERS = {"anthropic", "openai", "google", "deepseek", "xai", "perplexity", "ollama"}

# Markup arm's length dla usług wewnętrznych PL→DE
# OECD par. 7.61: 5% dla low value-adding services (bez konieczności benchmarkingu)
# Zakres arm's length EU JTPF: 3–10%
MARKUP_RATE: float = 0.05  # 5%

# Royalty rate DE→PL (licencja IP / SaaS revenue share)
# Metoda: CUP / TNMM; zakres rynkowy dla oprogramowania B2B: 2–5%
ROYALTY_RATE: float = 0.03  # 3% od przychodu SaaS PL

# R&D split (Cost Contribution Arrangement, OECD Chapter VIII)
RD_SPLIT: Dict[str, float] = {
    "SYLION_PL": 0.60,
    "RSDG_DE": 0.40,
}

# Shared infra split — proporcjonalny do user count (obliczany dynamicznie)
# lub fallback stały jeśli brak user_id w cost_log
SHARED_INFRA_SPLIT_FALLBACK: Dict[str, float] = {
    "SYLION_PL": 0.60,
    "RSDG_DE": 0.40,
}


# ---------------------------------------------------------------------------
# MODELE DANYCH
# ---------------------------------------------------------------------------

@dataclass
class CostRecord:
    ts: float
    run_id: str
    agent_id: str
    model_id: str
    provider: str
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    stage: str
    user_id: str = ""

    @property
    def company(self) -> str:
        return resolve_company(self.user_id)

    @property
    def cost_type(self) -> str:
        p = self.provider.lower()
        if p in SHARED_INFRA_PROVIDERS:
            return "shared_infra"
        if "r&d" in self.stage.lower() or "research" in self.stage.lower():
            return "rd"
        return "direct"


@dataclass
class IntercompanyNote:
    """Wewnętrzna nota księgowa (obciążeniowa / Intercompany-Rechnung)."""
    period: str                  # YYYY-MM
    from_company: str            # sprzedający usługę
    to_company: str              # nabywający usługę
    transaction_type: str        # "dev_services" | "ip_royalty" | "shared_infra" | "rd_contribution"
    base_cost_usd: float         # koszt bazowy (bez markup)
    markup_rate: float           # 0.05 = 5%
    markup_usd: float            # markup w USD
    total_usd: float             # koszt + markup
    currency_rate_eur: float     # kurs USD/EUR w dacie noty
    total_eur: float             # kwota w EUR
    details: List[Dict] = field(default_factory=list)  # szczegóły per user

    def as_dict(self) -> Dict:
        return {
            "period": self.period,
            "from_company": self.from_company,
            "to_company": self.to_company,
            "transaction_type": self.transaction_type,
            "base_cost_usd": round(self.base_cost_usd, 4),
            "markup_rate_pct": round(self.markup_rate * 100, 2),
            "markup_usd": round(self.markup_usd, 4),
            "total_usd": round(self.total_usd, 4),
            "currency_rate_eur": self.currency_rate_eur,
            "total_eur": round(self.total_eur, 4),
            "details": self.details,
        }


@dataclass
class AllocationResult:
    period: str
    by_company: Dict[str, Dict[str, float]]          # company → {user_id: direct_cost}
    intercompany_notes: List[IntercompanyNote]
    summary: Dict[str, float]                         # company → total allocated USD (incl. markup)
    user_counts: Dict[str, int]                       # company → active user count
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# POMOCNICZE
# ---------------------------------------------------------------------------

def resolve_company(user_id: str) -> str:
    """Mapuje user_id → company. Fallback: SYLION_PL."""
    if not user_id or user_id == "(system)":
        return USER_COMPANY_MAP.get("(system)", "SYLION_PL")
    if user_id in USER_COMPANY_MAP:
        return USER_COMPANY_MAP[user_id]
    for prefix, company in USER_PREFIX_MAP.items():
        if user_id.startswith(prefix):
            return company
    # Nieznany user_id → domyślnie PL (z ostrzeżeniem)
    return "SYLION_PL"


def month_to_ts_range(period: str) -> Tuple[float, float]:
    """Konwertuje 'YYYY-MM' → (ts_start, ts_end) w Unix timestamp UTC."""
    year, month = int(period[:4]), int(period[5:7])
    dt_start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    dt_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return dt_start.timestamp(), dt_end.timestamp()


def usd_to_eur(usd: float, rate: float = 1.08) -> float:
    """Konwersja USD → EUR. rate = USD/EUR (np. 1.08 = 1 EUR = 1.08 USD)."""
    return usd / rate


# ---------------------------------------------------------------------------
# GŁÓWNA FUNKCJA ALOKACJI
# ---------------------------------------------------------------------------

def allocate_costs(
    period: str,
    db_path: Optional[str] = None,
    cost_records: Optional[List[CostRecord]] = None,
    saas_revenue_pl_usd: float = 0.0,
    usd_eur_rate: float = 1.08,
    markup_rate: Optional[float] = None,
    royalty_rate: Optional[float] = None,
) -> AllocationResult:
    """
    Alokuje koszty z cost_log na firmy SYLION_PL i RSDG_DE za dany miesiąc.

    Parametry:
        period: miesiąc w formacie 'YYYY-MM', np. '2026-04'
        db_path: ścieżka do SQLite (dashboard/sylion.db). Jeśli None,
                 używa cost_records jako źródła danych.
        cost_records: lista CostRecord (alternatywa dla db_path, np. w testach)
        saas_revenue_pl_usd: przychód SaaS SYLION PL w USD za dany miesiąc
                             (potrzebny do kalkulacji royalty DE→PL)
        usd_eur_rate: kurs wymiany USD/EUR (pobierz z EBC lub ECB API)
        markup_rate: override domyślnego MARKUP_RATE (5%)
        royalty_rate: override domyślnego ROYALTY_RATE (3%)

    Zwraca:
        AllocationResult z podziałem kosztów, notami IC i podsumowaniem.

    Przykład użycia:
        result = allocate_costs(
            period="2026-04",
            db_path="/opt/sylion/dashboard/sylion.db",
            saas_revenue_pl_usd=5000.0,
            usd_eur_rate=1.085,
        )
        for note in result.intercompany_notes:
            print(note.as_dict())
    """
    _markup = markup_rate if markup_rate is not None else MARKUP_RATE
    _royalty = royalty_rate if royalty_rate is not None else ROYALTY_RATE
    warnings: List[str] = []

    # --- 1. Pobierz rekordy kosztów ---
    records = _load_records(period, db_path, cost_records, warnings)

    # --- 2. Podział na kategorie ---
    direct_by_company: Dict[str, Dict[str, float]] = {c: {} for c in COMPANIES}
    shared_infra_costs: List[CostRecord] = []
    rd_costs: List[CostRecord] = []
    unknown_users: set = set()

    for rec in records:
        company = resolve_company(rec.user_id)
        if company not in COMPANIES:
            unknown_users.add(rec.user_id)
            company = "SYLION_PL"

        if rec.cost_type == "shared_infra":
            shared_infra_costs.append(rec)
        elif rec.cost_type == "rd":
            rd_costs.append(rec)
        else:
            # Direct cost — przypisany bezpośrednio do user/company
            uid = rec.user_id or "(system)"
            direct_by_company[company][uid] = (
                direct_by_company[company].get(uid, 0.0) + rec.cost_usd
            )

    if unknown_users:
        warnings.append(
            f"Nieznane user_id przypisane domyślnie do SYLION_PL: {sorted(unknown_users)}. "
            "Zaktualizuj USER_COMPANY_MAP."
        )

    # --- 3. Policz aktywnych użytkowników per firma ---
    user_counts: Dict[str, int] = {
        c: len([u for u in direct_by_company[c] if u != "(system)"])
        for c in COMPANIES
    }
    total_users = sum(user_counts.values()) or 1

    # --- 4. Alokacja shared infra proporcjonalnie do user count ---
    infra_split = {
        c: (user_counts[c] / total_users) if total_users > 0
        else SHARED_INFRA_SPLIT_FALLBACK[c]
        for c in COMPANIES
    }
    total_infra = sum(r.cost_usd for r in shared_infra_costs)
    infra_per_company = {c: total_infra * infra_split[c] for c in COMPANIES}

    # Dodaj infra do direct_by_company jako wirtualny wpis
    for company, infra_cost in infra_per_company.items():
        if infra_cost > 0:
            direct_by_company[company]["__shared_infra__"] = (
                direct_by_company[company].get("__shared_infra__", 0.0) + infra_cost
            )

    # --- 5. Alokacja R&D (Cost Contribution Arrangement) ---
    total_rd = sum(r.cost_usd for r in rd_costs)
    rd_per_company = {c: total_rd * RD_SPLIT.get(c, 0.0) for c in COMPANIES}
    for company, rd_cost in rd_per_company.items():
        if rd_cost > 0:
            direct_by_company[company]["__rd_contribution__"] = (
                direct_by_company[company].get("__rd_contribution__", 0.0) + rd_cost
            )

    # --- 6. Wygeneruj noty intercompany ---
    notes: List[IntercompanyNote] = []

    # 6A. PL → DE: Usługi programistyczne
    pl_dev_cost = sum(
        v for k, v in direct_by_company["SYLION_PL"].items()
        if k not in ("__shared_infra__", "__rd_contribution__")
    )
    if pl_dev_cost > 0:
        markup = pl_dev_cost * _markup
        total = pl_dev_cost + markup
        notes.append(IntercompanyNote(
            period=period,
            from_company="SYLION_PL",
            to_company="RSDG_DE",
            transaction_type="dev_services",
            base_cost_usd=pl_dev_cost,
            markup_rate=_markup,
            markup_usd=markup,
            total_usd=total,
            currency_rate_eur=usd_eur_rate,
            total_eur=usd_to_eur(total, usd_eur_rate),
            details=[
                {"user_id": uid, "cost_usd": round(cost, 6)}
                for uid, cost in direct_by_company["SYLION_PL"].items()
                if uid not in ("__shared_infra__", "__rd_contribution__")
            ],
        ))

    # 6B. DE → PL: Licencja IP / Royalty
    if saas_revenue_pl_usd > 0:
        royalty = saas_revenue_pl_usd * _royalty
        notes.append(IntercompanyNote(
            period=period,
            from_company="RSDG_DE",
            to_company="SYLION_PL",
            transaction_type="ip_royalty",
            base_cost_usd=royalty,
            markup_rate=0.0,
            markup_usd=0.0,
            total_usd=royalty,
            currency_rate_eur=usd_eur_rate,
            total_eur=usd_to_eur(royalty, usd_eur_rate),
            details=[{
                "saas_revenue_pl_usd": round(saas_revenue_pl_usd, 2),
                "royalty_rate_pct": round(_royalty * 100, 2),
            }],
        ))
    else:
        warnings.append(
            "saas_revenue_pl_usd=0 → nota royalty DE→PL pominięta. "
            "Przekaż rzeczywisty przychód SaaS PL."
        )

    # 6C. Shared infra IC note (informacyjna, brak dodatkowego markup)
    if total_infra > 0:
        pl_infra = infra_per_company["SYLION_PL"]
        de_infra = infra_per_company["RSDG_DE"]
        notes.append(IntercompanyNote(
            period=period,
            from_company="RSDG_DE",   # DE zazwyczaj płaci za infra prod
            to_company="SYLION_PL",
            transaction_type="shared_infra_recharge",
            base_cost_usd=pl_infra,
            markup_rate=0.0,
            markup_usd=0.0,
            total_usd=pl_infra,
            currency_rate_eur=usd_eur_rate,
            total_eur=usd_to_eur(pl_infra, usd_eur_rate),
            details=[{
                "total_infra_cost_usd": round(total_infra, 4),
                "pl_share_pct": round(infra_split["SYLION_PL"] * 100, 1),
                "de_share_pct": round(infra_split["RSDG_DE"] * 100, 1),
                "user_count_pl": user_counts["SYLION_PL"],
                "user_count_de": user_counts["RSDG_DE"],
            }],
        ))

    # 6D. R&D Cost Contribution (informacyjna)
    if total_rd > 0:
        notes.append(IntercompanyNote(
            period=period,
            from_company="SYLION_PL",
            to_company="RSDG_DE",
            transaction_type="rd_cost_contribution",
            base_cost_usd=rd_per_company["RSDG_DE"],
            markup_rate=0.0,
            markup_usd=0.0,
            total_usd=rd_per_company["RSDG_DE"],
            currency_rate_eur=usd_eur_rate,
            total_eur=usd_to_eur(rd_per_company["RSDG_DE"], usd_eur_rate),
            details=[{
                "total_rd_cost_usd": round(total_rd, 4),
                "pl_share_pct": RD_SPLIT["SYLION_PL"] * 100,
                "de_share_pct": RD_SPLIT["RSDG_DE"] * 100,
            }],
        ))

    # --- 7. Podsumowanie ---
    summary: Dict[str, float] = {}
    for company in COMPANIES:
        total_allocated = sum(direct_by_company[company].values())
        # Dodaj koszt royalty (jeśli PL płaci DE)
        royalty_notes = [
            n for n in notes
            if n.transaction_type == "ip_royalty" and n.to_company == company
        ]
        total_allocated += sum(n.total_usd for n in royalty_notes)
        summary[company] = round(total_allocated, 4)

    return AllocationResult(
        period=period,
        by_company=direct_by_company,
        intercompany_notes=notes,
        summary=summary,
        user_counts=user_counts,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# ŁADOWANIE DANYCH
# ---------------------------------------------------------------------------

def _load_records(
    period: str,
    db_path: Optional[str],
    cost_records: Optional[List[CostRecord]],
    warnings: List[str],
) -> List[CostRecord]:
    """Ładuje CostRecord z SQLite lub przekazanej listy."""
    if cost_records is not None:
        return cost_records

    if db_path is None:
        warnings.append("Brak db_path i cost_records — zwrócono puste wyniki.")
        return []

    path = Path(db_path)
    if not path.exists():
        warnings.append(f"Plik bazy danych nie istnieje: {db_path}")
        return []

    ts_start, ts_end = month_to_ts_range(period)
    records: List[CostRecord] = []

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Sprawdź czy kolumna user_id istnieje (dodana w Cluster R v5.9.1)
        cols = [r[1] for r in cur.execute("PRAGMA table_info(cost_log)").fetchall()]
        has_user_id = "user_id" in cols

        if has_user_id:
            sql = """
                SELECT ts, run_id, agent_id, model_id, provider, model_name,
                       tokens_in, tokens_out, cost_usd, latency_ms, stage,
                       COALESCE(NULLIF(user_id, ''), '(system)') AS user_id
                FROM cost_log
                WHERE ts BETWEEN ? AND ?
                ORDER BY ts ASC
            """
        else:
            warnings.append(
                "Kolumna user_id brak w cost_log (baza pre-v5.9.1 R). "
                "Wszystkie koszty przypisane do SYLION_PL. "
                "Uruchom migrację Cluster R."
            )
            sql = """
                SELECT ts, run_id, agent_id, model_id, provider, model_name,
                       tokens_in, tokens_out, cost_usd, latency_ms, stage,
                       '(system)' AS user_id
                FROM cost_log
                WHERE ts BETWEEN ? AND ?
                ORDER BY ts ASC
            """

        for row in cur.execute(sql, (ts_start, ts_end)).fetchall():
            records.append(CostRecord(
                ts=row["ts"],
                run_id=row["run_id"],
                agent_id=row["agent_id"],
                model_id=row["model_id"],
                provider=row["provider"],
                model_name=row["model_name"],
                tokens_in=row["tokens_in"],
                tokens_out=row["tokens_out"],
                cost_usd=row["cost_usd"],
                latency_ms=row["latency_ms"],
                stage=row["stage"],
                user_id=row["user_id"],
            ))

        conn.close()

    except sqlite3.Error as e:
        warnings.append(f"Błąd SQLite: {e}")

    return records


# ---------------------------------------------------------------------------
# RAPORTOWANIE
# ---------------------------------------------------------------------------

def format_report(result: AllocationResult, lang: str = "pl") -> str:
    """
    Formatuje AllocationResult jako Markdown nota księgowa.
    lang: 'pl' → polska nota obciążeniowa, 'de' → Intercompany-Rechnung (DE)
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = []

    if lang == "pl":
        lines += [
            f"# Nota Obciążeniowa Wewnętrzna — {result.period}",
            f"**Wystawca:** SYLION sp. z o.o. (NIP: xxxxxxxxxx)",
            f"**Nabywca:** RSDG GmbH (Steuernummer: xxxxxxxxxx)",
            f"**Data wystawienia:** {now}",
            f"**Okres:** {result.period}",
            "",
            "## Podsumowanie alokacji",
            f"| Firma | Koszt bezpośredni (USD) |",
            f"|-------|------------------------|",
        ]
        for company, total in result.summary.items():
            lines.append(f"| {company} | {total:.4f} |")
    else:
        lines += [
            f"# Intercompany-Rechnung — {result.period}",
            f"**Aussteller:** RSDG GmbH (Steuernummer: xxxxxxxxxx)",
            f"**Empfänger:** SYLION sp. z o.o. (NIP: xxxxxxxxxx)",
            f"**Datum:** {now}",
            f"**Periode:** {result.period}",
            "",
            "## Kostenallokation — Zusammenfassung",
        ]

    lines += ["", "## Noty Intercompany / IC Notes"]
    for note in result.intercompany_notes:
        d = note.as_dict()
        lines += [
            f"",
            f"### {d['transaction_type']} | {d['from_company']} → {d['to_company']}",
            f"- Koszt bazowy / Basiskosten: **${d['base_cost_usd']:.4f} USD**",
            f"- Markup ({d['markup_rate_pct']:.1f}%): ${d['markup_usd']:.4f} USD",
            f"- **Łącznie / Gesamt: ${d['total_usd']:.4f} USD = €{d['total_eur']:.4f} EUR**",
            f"- Kurs USD/EUR: {d['currency_rate_eur']}",
        ]
        if d.get("details"):
            lines.append("- Szczegóły:")
            for det in d["details"][:10]:  # max 10 wierszy
                lines.append(f"  - {det}")

    if result.warnings:
        lines += ["", "## Ostrzeżenia / Warnungen"]
        for w in result.warnings:
            lines.append(f"- ⚠ {w}")

    lines += [
        "",
        "---",
        f"*Wygenerowano: cost_allocation.py | Transfer Pricing SYLION↔RSDG | {now}*",
        "*Metodologia: OECD TP Guidelines 2022, Cost Plus Method, Arm's Length Principle*",
    ]

    return "\n".join(lines)


def export_notes_json(result: AllocationResult) -> List[Dict]:
    """Eksportuje noty IC jako lista słowników (JSON-serializable)."""
    return [note.as_dict() for note in result.intercompany_notes]


# ---------------------------------------------------------------------------
# PRZYKŁAD UŻYCIA / MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # Przykład z danymi testowymi (bez dostępu do SQLite)
    test_records = [
        CostRecord(ts=1745000000, run_id="run1", agent_id="ag1", model_id="m1",
                   provider="anthropic", model_name="claude-3-5-sonnet",
                   tokens_in=1200, tokens_out=400, cost_usd=0.0096,
                   latency_ms=1500, stage="development", user_id="dev_pl_jan"),
        CostRecord(ts=1745001000, run_id="run2", agent_id="ag2", model_id="m2",
                   provider="openai", model_name="gpt-4o",
                   tokens_in=800, tokens_out=300, cost_usd=0.0068,
                   latency_ms=1200, stage="development", user_id="dev_pl_anna"),
        CostRecord(ts=1745002000, run_id="run3", agent_id="ag3", model_id="m3",
                   provider="hetzner", model_name="vps",
                   tokens_in=0, tokens_out=0, cost_usd=25.0,
                   latency_ms=0, stage="infrastructure", user_id="prod_de_system"),
        CostRecord(ts=1745003000, run_id="run4", agent_id="ag4", model_id="m4",
                   provider="openai", model_name="gpt-4o",
                   tokens_in=600, tokens_out=200, cost_usd=0.0045,
                   latency_ms=900, stage="development", user_id="dev_pl_piotr"),
        CostRecord(ts=1745004000, run_id="run5", agent_id="ag5", model_id="m5",
                   provider="anthropic", model_name="claude-opus",
                   tokens_in=2000, tokens_out=800, cost_usd=0.045,
                   latency_ms=3000, stage="r&d research", user_id="dev_pl_marta"),
    ]

    result = allocate_costs(
        period="2026-04",
        cost_records=test_records,
        saas_revenue_pl_usd=5000.0,
        usd_eur_rate=1.085,
    )

    print("=== ALLOKACJA KOSZTÓW ===")
    print(f"Okres: {result.period}")
    print(f"User counts: {result.user_counts}")
    print(f"Summary: {result.summary}")
    print()

    print("=== NOTY INTERCOMPANY ===")
    print(json.dumps(export_notes_json(result), indent=2, ensure_ascii=False))
    print()

    print("=== RAPORT PL (NOTA OBCIĄŻENIOWA) ===")
    print(format_report(result, lang="pl"))

    if result.warnings:
        print("\n=== OSTRZEŻENIA ===")
        for w in result.warnings:
            print(f"  WARN: {w}")
