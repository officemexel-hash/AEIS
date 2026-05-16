from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

KRS_ODPIS_URL = "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/{krs}?rejestr=P&format=json"
RDF_SEARCH_URL = "https://ekrs.ms.gov.pl/rdf/pd/search_df"
IMSIG_REPORTS_URL = "https://www.imsig.pl/krs/{krs}/sprawozdania"


def normalize_krs(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if not digits:
        raise ValueError("KRS is required")
    if len(digits) > 10:
        raise ValueError("KRS must have at most 10 digits")
    return digits.zfill(10)


def _get_path(data: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _fetch_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SYLION-AEIS-Funding-Audit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8"))


def _latest_financial_mentions(dane: dict[str, Any]) -> list[dict[str, str]]:
    wzmianki = _get_path(
        dane,
        ["dzial3", "wzmiankiOZlozonychDokumentach", "wzmiankaOZlozeniuRocznegoSprawozdaniaFinansowego"],
        [],
    )
    result: list[dict[str, str]] = []
    for item in _list(wzmianki):
        if isinstance(item, dict):
            result.append(
                {
                    "filed_at": str(item.get("dataZlozenia") or ""),
                    "period": str(item.get("zaOkresOdDo") or ""),
                    "document_type": "annual_financial_statement",
                }
            )
    return result[-6:]


def _registry_risks(data: dict[str, Any], filings: list[dict[str, str]]) -> list[str]:
    risks: list[str] = []
    dzial4 = _get_path(data, ["odpis", "dane", "dzial4"], {}) or {}
    dzial5 = _get_path(data, ["odpis", "dane", "dzial5"], {}) or {}
    dzial6 = _get_path(data, ["odpis", "dane", "dzial6"], {}) or {}
    if dzial4:
        risks.append("KRS dział 4 nie jest pusty: wymaga przeglądu zadłużeń i zaległości.")
    if dzial5:
        risks.append("KRS dział 5 nie jest pusty: wymaga przeglądu kuratora lub zarządu przymusowego.")
    if dzial6:
        risks.append("KRS dział 6 nie jest pusty: sprawdź likwidację, upadłość albo restrukturyzację.")
    if not filings:
        risks.append("Brak wzmianki o rocznych sprawozdaniach finansowych w aktualnym odpisie KRS.")
    return risks


def fetch_krs_company_profile(krs: str) -> dict[str, Any]:
    normalized = normalize_krs(krs)
    url = KRS_ODPIS_URL.format(krs=normalized)
    try:
        data = _fetch_json(url)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"KRS registry returned HTTP {exc.code} for {normalized}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"KRS registry lookup failed for {normalized}: {exc}") from exc

    odpis = data.get("odpis") or {}
    dane = odpis.get("dane") or {}
    dzial1 = dane.get("dzial1") or {}
    dane_podmiotu = dzial1.get("danePodmiotu") or {}
    identyfikatory = dane_podmiotu.get("identyfikatory") or {}
    siedziba = _get_path(dzial1, ["siedzibaIAdres", "siedziba"], {}) or {}
    adres = _get_path(dzial1, ["siedzibaIAdres", "adres"], {}) or {}
    pkd_main = _list(_get_path(dane, ["dzial3", "przedmiotDzialalnosci", "przedmiotPrzewazajacejDzialalnosci"], []))
    filings = _latest_financial_mentions(dane)
    registry_sync = {
        "source": "api-krs.ms.gov.pl",
        "source_url": url,
        "rdf_search_url": RDF_SEARCH_URL,
        "imsig_reports_url": IMSIG_REPORTS_URL.format(krs=normalized),
        "krs": normalized,
        "synced_at": time.time(),
        "odpis_type": odpis.get("rodzaj", "Aktualny"),
        "odpis_generated_at": _get_path(odpis, ["naglowekA", "dataCzasOdpisu"], ""),
        "registry_state_date": _get_path(odpis, ["naglowekA", "stanZDnia"], ""),
        "last_entry_date": _get_path(odpis, ["naglowekA", "dataOstatniegoWpisu"], ""),
        "financial_filings": filings,
        "risk_flags": _registry_risks(data, filings),
        "pkd": pkd_main[:6],
    }
    profile_patch = {
        "legal_name": dane_podmiotu.get("nazwa", ""),
        "tax_id": identyfikatory.get("nip", ""),
        "registration_id": normalized,
        "country": siedziba.get("kraj", "POLSKA").title() if siedziba.get("kraj") else "Poland",
        "region": siedziba.get("wojewodztwo", "").title(),
        "city": (adres.get("miejscowosc") or siedziba.get("miejscowosc") or "").title(),
        "legal_form": dane_podmiotu.get("formaPrawna", "").title(),
        "services": [item.get("opis", "").title() for item in pkd_main if isinstance(item, dict) and item.get("opis")],
        "registry_sync": registry_sync,
    }
    return {
        "status": "ok",
        "profile_patch": profile_patch,
        "registry_sync": registry_sync,
        "raw_summary": {
            "krs": normalized,
            "name": profile_patch["legal_name"],
            "nip": profile_patch["tax_id"],
            "regon": identyfikatory.get("regon", ""),
        },
    }
