"""
jpk_exporter.py — SYLION v5.9.1 / v5.10
JPK (Jednolity Plik Kontrolny) exporter.

Obsługuje:
  • JPK_V7M(3)  — ewidencja VAT + deklaracja (od 2026-02-01 schema v3)
    Nowe pola: NrKSeF (obowiązkowy jeśli faktura przez KSeF) lub znacznik
    OFF / BFK / DI (gdy KSeF niedostępny / B2C / inna przesłanka)
  • JPK_FA(4)   — rejestr faktur sprzedaży i zakupu

Specyfikacja MF: https://www.gov.pl/web/finanse/struktury-jpk
Schema JPK_V7M(3): dostępna od 2025-11, obowiązkowa od 2026-02-01
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Sequence
from uuid import UUID
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Namespaces
# ─────────────────────────────────────────────
# JPK_V7M(3) — ministerialny namespace (zaktualizowany dla v3)
NS_V7M = "http://jpk.mf.gov.pl/wzor/2023/09/29/9781/"
# JPK_FA(4)
NS_FA  = "http://jpk.mf.gov.pl/wzor/2022/02/17/9852/"

XSI    = "http://www.w3.org/2001/XMLSchema-instance"

# ─────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────
@dataclass
class VATEntry:
    """Single VAT ewidencja row (sprzedaż lub zakup)."""
    lp: int
    data_wystawienia: date
    data_sprzedazy: Optional[date]
    nrfaktury: str
    nr_ksef: Optional[str]           # NumerKSeF — obowiązkowy od 2026-02-01 w KSeF
    ksef_flag: Optional[str]         # OFF | BFK | DI (gdy nr_ksef is None)
    nip_nabywcy: Optional[str]
    nazwa_nabywcy: str
    k_15: Decimal = Decimal("0")     # netto 5%
    k_16: Decimal = Decimal("0")     # VAT 5%
    k_17: Decimal = Decimal("0")     # netto 8%
    k_18: Decimal = Decimal("0")     # VAT 8%
    k_19: Decimal = Decimal("0")     # netto 23%
    k_20: Decimal = Decimal("0")     # VAT 23%
    k_21: Decimal = Decimal("0")     # netto ZW
    k_10: Decimal = Decimal("0")     # netto 0% krajowy
    k_11: Decimal = Decimal("0")     # netto WDT (VAT-UE)
    # Zakup (pola K_40..K_48)
    k_40: Decimal = Decimal("0")     # nabycie śr. trwałych netto
    k_41: Decimal = Decimal("0")     # nabycie śr. trwałych VAT
    k_42: Decimal = Decimal("0")     # nabycie pozostałe netto
    k_43: Decimal = Decimal("0")     # nabycie pozostałe VAT
    typ: str = "sprzedaz"            # "sprzedaz" | "zakup"


@dataclass
class DeclarationTotals:
    """Pola deklaracyjne P_xxx w JPK_V7M."""
    p_10: Decimal = Decimal("0")     # dostawa 0% krajowa
    p_11: Decimal = Decimal("0")     # WDT
    p_13: Decimal = Decimal("0")     # netto 5%
    p_14: Decimal = Decimal("0")     # VAT 5%
    p_15: Decimal = Decimal("0")     # netto 8%
    p_16: Decimal = Decimal("0")     # VAT 8%
    p_19: Decimal = Decimal("0")     # netto 23%
    p_20: Decimal = Decimal("0")     # VAT 23%
    p_33: Decimal = Decimal("0")     # całkowity VAT należny
    p_40: Decimal = Decimal("0")     # nabycia śr. trwałych — VAT do odliczenia
    p_41: Decimal = Decimal("0")     # nabycia pozostałe — VAT do odliczenia
    p_48: Decimal = Decimal("0")     # VAT do zwrotu
    p_49: Decimal = Decimal("0")     # VAT do zapłaty
    p_360: Optional[str] = None      # NOWE w v3: liczba faktur bez NrKSeF


@dataclass
class EntityHeader:
    nip: str
    pelna_nazwa: str
    kraj: str = "PL"
    kod_urzedu: str = "0271"         # kod urzędu skarbowego


# ─────────────────────────────────────────────
# JPK_V7M(3) exporter
# ─────────────────────────────────────────────
def export_jpk_v7m(
    month: str,
    entity: EntityHeader,
    sprzedaz: List[VATEntry],
    zakup: List[VATEntry],
    totals: Optional[DeclarationTotals] = None,
) -> str:
    """
    Generuje JPK_V7M(3) XML (ewidencja VAT + deklaracja VAT-7).
    Obowiązuje od 2026-02-01 — nowe pola NrKSeF / K_360 / P_360.

    Args:
        month:   Okres w formacie YYYY-MM (np. "2026-02")
        entity:  Dane podmiotu składającego JPK
        sprzedaz: Lista wpisów rejestru sprzedaży
        zakup:    Lista wpisów rejestru zakupu
        totals:   Sumy deklaracyjne (auto-obliczane z list jeśli None)

    Returns:
        Zserializowany XML jako string UTF-8
    """
    year, mon = month.split("-")
    data_od = f"{year}-{mon}-01"
    # last day — uproszczone
    last_day = _last_day_of_month(int(year), int(mon))
    data_do  = f"{year}-{mon}-{last_day:02d}"
    now_ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if totals is None:
        totals = _compute_totals(sprzedaz, zakup)

    # Buduj XML ──────────────────────────────────────
    ET.register_namespace("", NS_V7M)
    ET.register_namespace("xsi", XSI)

    root = ET.Element(f"{{{NS_V7M}}}JPK")
    root.set(f"{{{XSI}}}schemaLocation",
             f"{NS_V7M} {NS_V7M}JPK_VAT_Deklaracja_v3-0E.xsd")

    # Nagłówek
    nagl = ET.SubElement(root, f"{{{NS_V7M}}}Naglowek")
    ET.SubElement(nagl, f"{{{NS_V7M}}}KodFormularza",
                  kodSystemowy="JPK_VAT", wersjaSchemy="3-0E").text = "JPK_VAT"
    ET.SubElement(nagl, f"{{{NS_V7M}}}WariantFormularza").text = "2"
    ET.SubElement(nagl, f"{{{NS_V7M}}}DataWytworzeniaJPK").text = now_ts
    ET.SubElement(nagl, f"{{{NS_V7M}}}DataOd").text = data_od
    ET.SubElement(nagl, f"{{{NS_V7M}}}DataDo").text = data_do
    ET.SubElement(nagl, f"{{{NS_V7M}}}NazwaSystemu").text = "SYLION v5.10"
    ET.SubElement(nagl, f"{{{NS_V7M}}}CelZlozenia").text = "1"    # 1=złożenie, 2=korekta

    # Podmiot
    podmiot = ET.SubElement(root, f"{{{NS_V7M}}}Podmiot1")
    ident   = ET.SubElement(podmiot, f"{{{NS_V7M}}}IdentyfikatorPodmiotu")
    ET.SubElement(ident, f"{{{NS_V7M}}}NIP").text = entity.nip
    ET.SubElement(ident, f"{{{NS_V7M}}}PelnaNazwa").text = entity.pelna_nazwa

    # ── Ewidencja SprzedazCtrl ──
    sprzedaz_ctrl = ET.SubElement(root, f"{{{NS_V7M}}}SprzedazCtrl")
    ET.SubElement(sprzedaz_ctrl, f"{{{NS_V7M}}}LiczbaWierszySprzedazy").text = \
        str(len(sprzedaz))
    sp_netto_sum = sum(
        e.k_19 + e.k_17 + e.k_15 + e.k_10 + e.k_11 for e in sprzedaz
    )
    ET.SubElement(sprzedaz_ctrl, f"{{{NS_V7M}}}PodatekNalezny").text = \
        _fmt(sum(e.k_20 + e.k_18 + e.k_16 for e in sprzedaz))

    # Wpisy sprzedaży
    for entry in sprzedaz:
        sp_wiersz = ET.SubElement(root, f"{{{NS_V7M}}}SprzedazWiersz")
        ET.SubElement(sp_wiersz, f"{{{NS_V7M}}}LpSprzedazy").text = str(entry.lp)
        _optional(sp_wiersz, NS_V7M, "NIPNabywcy", entry.nip_nabywcy)
        ET.SubElement(sp_wiersz, f"{{{NS_V7M}}}NazwaKontrahenta").text = entry.nazwa_nabywcy
        ET.SubElement(sp_wiersz, f"{{{NS_V7M}}}DowodSprzedazy").text = entry.nrfaktury
        ET.SubElement(sp_wiersz, f"{{{NS_V7M}}}DataWystawienia").text = \
            str(entry.data_wystawienia)
        _optional(sp_wiersz, NS_V7M, "DataSprzedazy",
                  str(entry.data_sprzedazy) if entry.data_sprzedazy else None)

        # ── NOWE POLE v3: NrKSeF lub znacznik ──
        if entry.nr_ksef:
            ET.SubElement(sp_wiersz, f"{{{NS_V7M}}}NrKSeF").text = entry.nr_ksef
        elif entry.ksef_flag in ("OFF", "BFK", "DI"):
            ET.SubElement(sp_wiersz, f"{{{NS_V7M}}}ZnacznikKSeF").text = entry.ksef_flag
        else:
            # Blokuj eksport — JPK v3 odrzuci plik bez NrKSeF lub znacznika
            raise ValueError(
                f"Faktura {entry.nrfaktury} (lp={entry.lp}) nie ma NrKSeF ani "
                f"ważnego znacznika (OFF/BFK/DI). JPK_V7M(3) odrzuci plik."
            )

        # Kwoty
        _vat_fields_sprzedaz(sp_wiersz, NS_V7M, entry)

    # ── Ewidencja ZakupCtrl ──
    zakup_ctrl = ET.SubElement(root, f"{{{NS_V7M}}}ZakupCtrl")
    ET.SubElement(zakup_ctrl, f"{{{NS_V7M}}}LiczbaWierszyZakupow").text = \
        str(len(zakup))
    ET.SubElement(zakup_ctrl, f"{{{NS_V7M}}}PodatekNaliczony").text = \
        _fmt(sum(e.k_41 + e.k_43 for e in zakup))

    for entry in zakup:
        zk_wiersz = ET.SubElement(root, f"{{{NS_V7M}}}ZakupWiersz")
        ET.SubElement(zk_wiersz, f"{{{NS_V7M}}}LpZakupu").text = str(entry.lp)
        _optional(zk_wiersz, NS_V7M, "NIPDostawcy", entry.nip_nabywcy)
        ET.SubElement(zk_wiersz, f"{{{NS_V7M}}}NazwaDostawcy").text = entry.nazwa_nabywcy
        ET.SubElement(zk_wiersz, f"{{{NS_V7M}}}DowodZakupu").text = entry.nrfaktury
        ET.SubElement(zk_wiersz, f"{{{NS_V7M}}}DataZakupu").text = \
            str(entry.data_wystawienia)
        if entry.nr_ksef:
            ET.SubElement(zk_wiersz, f"{{{NS_V7M}}}NrKSeF").text = entry.nr_ksef
        elif entry.ksef_flag in ("OFF", "BFK", "DI"):
            ET.SubElement(zk_wiersz, f"{{{NS_V7M}}}ZnacznikKSeF").text = entry.ksef_flag

        _optional_dec(zk_wiersz, NS_V7M, "K_40", entry.k_40)
        _optional_dec(zk_wiersz, NS_V7M, "K_41", entry.k_41)
        _optional_dec(zk_wiersz, NS_V7M, "K_42", entry.k_42)
        _optional_dec(zk_wiersz, NS_V7M, "K_43", entry.k_43)

    # ── Deklaracja ──
    dekl = ET.SubElement(root, f"{{{NS_V7M}}}Deklaracja")
    _deklaracja_fields(dekl, NS_V7M, totals, entity, year, mon, data_od, data_do)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    import io
    buf = io.BytesIO()
    tree.write(buf, xml_declaration=True, encoding="UTF-8")
    xml_str = buf.getvalue().decode("utf-8")
    logger.info(
        "JPK_V7M(3) wygenerowany: miesiąc=%s wiersze_sp=%d wiersze_zk=%d",
        month, len(sprzedaz), len(zakup),
    )
    return xml_str


# ─────────────────────────────────────────────
# JPK_FA exporter
# ─────────────────────────────────────────────
@dataclass
class InvoiceLine:
    lp: int
    nazwa_towaru: str
    jednostka_miary: str
    ilosc: Decimal
    cena_jednostkowa: Decimal
    stawka_vat: Decimal
    wartosc_netto: Decimal
    kwota_vat: Decimal


@dataclass
class JPKInvoice:
    lp: int
    nrfaktury: str
    nr_ksef: Optional[str]
    ksef_flag: Optional[str]
    data_wystawienia: date
    nip_sprzedawcy: str
    nazwa_sprzedawcy: str
    nip_nabywcy: Optional[str]
    nazwa_nabywcy: str
    netto: Decimal
    vat: Decimal
    brutto: Decimal
    waluta: str = "PLN"
    linie: List[InvoiceLine] = field(default_factory=list)


def export_jpk_fa(
    period: str,
    entity: EntityHeader,
    invoices: List[JPKInvoice],
) -> str:
    """
    Generuje JPK_FA(4) XML — rejestr faktur sprzedaży.

    Args:
        period:   YYYY-MM
        entity:   dane podmiotu
        invoices: lista faktur

    Returns:
        Zserializowany XML jako string UTF-8
    """
    year, mon = period.split("-")
    data_od   = f"{year}-{mon}-01"
    last_day  = _last_day_of_month(int(year), int(mon))
    data_do   = f"{year}-{mon}-{last_day:02d}"
    now_ts    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ET.register_namespace("", NS_FA)
    ET.register_namespace("xsi", XSI)

    root = ET.Element(f"{{{NS_FA}}}JPK")
    nagl = ET.SubElement(root, f"{{{NS_FA}}}Naglowek")
    ET.SubElement(nagl, f"{{{NS_FA}}}KodFormularza",
                  kodSystemowy="JPK_FA", wersjaSchemy="4-0").text = "JPK_FA"
    ET.SubElement(nagl, f"{{{NS_FA}}}WariantFormularza").text = "4"
    ET.SubElement(nagl, f"{{{NS_FA}}}DataWytworzeniaJPK").text = now_ts
    ET.SubElement(nagl, f"{{{NS_FA}}}DataOd").text = data_od
    ET.SubElement(nagl, f"{{{NS_FA}}}DataDo").text = data_do
    ET.SubElement(nagl, f"{{{NS_FA}}}NazwaSystemu").text = "SYLION v5.10"

    podmiot = ET.SubElement(root, f"{{{NS_FA}}}Podmiot1")
    ident   = ET.SubElement(podmiot, f"{{{NS_FA}}}IdentyfikatorPodmiotu")
    ET.SubElement(ident, f"{{{NS_FA}}}NIP").text = entity.nip
    ET.SubElement(ident, f"{{{NS_FA}}}PelnaNazwa").text = entity.pelna_nazwa

    fa_ctrl = ET.SubElement(root, f"{{{NS_FA}}}FakturaCtrl")
    ET.SubElement(fa_ctrl, f"{{{NS_FA}}}LiczbaFaktur").text = str(len(invoices))
    ET.SubElement(fa_ctrl, f"{{{NS_FA}}}WartoscFaktur").text = \
        _fmt(sum(inv.brutto for inv in invoices))

    for inv in invoices:
        fa_el = ET.SubElement(root, f"{{{NS_FA}}}Faktura")
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_1").text = str(inv.data_wystawienia)
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_2").text = inv.nrfaktury
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_3A").text = inv.nazwa_sprzedawcy
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_3B").text = inv.nazwa_nabywcy
        _optional(fa_el, NS_FA, "P_3C", inv.nip_sprzedawcy)
        _optional(fa_el, NS_FA, "P_3D", inv.nip_nabywcy)
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_13_1").text = _fmt(inv.netto)
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_14_1").text = _fmt(inv.vat)
        ET.SubElement(fa_el, f"{{{NS_FA}}}P_15").text  = _fmt(inv.brutto)
        ET.SubElement(fa_el, f"{{{NS_FA}}}KodWaluty").text = inv.waluta

        # NrKSeF — obowiązkowy od 2026-02-01
        if inv.nr_ksef:
            ET.SubElement(fa_el, f"{{{NS_FA}}}NrKSeF").text = inv.nr_ksef
        elif inv.ksef_flag:
            ET.SubElement(fa_el, f"{{{NS_FA}}}ZnacznikBrakuKSeF").text = inv.ksef_flag

        # Wiersze faktury
        for line in inv.linie:
            wiersz = ET.SubElement(root, f"{{{NS_FA}}}FakturaWiersz")
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_2B").text = inv.nrfaktury
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_7").text  = line.nazwa_towaru
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_8A").text = line.jednostka_miary
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_8B").text = str(line.ilosc)
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_9A").text = _fmt(line.cena_jednostkowa)
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_11").text = _fmt(line.wartosc_netto)
            ET.SubElement(wiersz, f"{{{NS_FA}}}P_12").text = str(line.stawka_vat)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    import io
    buf = io.BytesIO()
    tree.write(buf, xml_declaration=True, encoding="UTF-8")
    xml_str = buf.getvalue().decode("utf-8")
    logger.info(
        "JPK_FA(4) wygenerowany: okres=%s faktury=%d",
        period, len(invoices),
    )
    return xml_str


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────
def _fmt(d: Decimal) -> str:
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _optional(parent: ET.Element, ns: str, tag: str, val: Optional[str]) -> None:
    if val:
        ET.SubElement(parent, f"{{{ns}}}{tag}").text = val


def _optional_dec(parent: ET.Element, ns: str, tag: str, val: Decimal) -> None:
    if val != Decimal("0"):
        ET.SubElement(parent, f"{{{ns}}}{tag}").text = _fmt(val)


def _vat_fields_sprzedaz(parent: ET.Element, ns: str, entry: VATEntry) -> None:
    for field_name, value in [
        ("K_10", entry.k_10), ("K_11", entry.k_11),
        ("K_15", entry.k_15), ("K_16", entry.k_16),
        ("K_17", entry.k_17), ("K_18", entry.k_18),
        ("K_19", entry.k_19), ("K_20", entry.k_20),
        ("K_21", entry.k_21),
    ]:
        _optional_dec(parent, ns, field_name, value)


def _deklaracja_fields(
    parent: ET.Element, ns: str, t: DeclarationTotals,
    entity: EntityHeader, year: str, mon: str,
    data_od: str, data_do: str,
) -> None:
    ET.SubElement(parent, f"{{{ns}}}MiesiacRozliczeniowy").text = mon
    ET.SubElement(parent, f"{{{ns}}}RokRozliczeniowy").text = year
    for fname, val in [
        ("P_10", t.p_10), ("P_11", t.p_11),
        ("P_13", t.p_13), ("P_14", t.p_14),
        ("P_15", t.p_15), ("P_16", t.p_16),
        ("P_19", t.p_19), ("P_20", t.p_20),
        ("P_33", t.p_33), ("P_40", t.p_40),
        ("P_41", t.p_41), ("P_48", t.p_48),
        ("P_49", t.p_49),
    ]:
        _optional_dec(parent, ns, fname, val)
    # P_360 — nowe w schema v3 (liczba faktur bez NrKSeF ze znacznikiem)
    if t.p_360 is not None:
        ET.SubElement(parent, f"{{{ns}}}P_360").text = t.p_360


def _compute_totals(sprzedaz: List[VATEntry], zakup: List[VATEntry]) -> DeclarationTotals:
    t = DeclarationTotals()
    t.p_10  = sum(e.k_10 for e in sprzedaz)
    t.p_11  = sum(e.k_11 for e in sprzedaz)
    t.p_13  = sum(e.k_15 for e in sprzedaz)
    t.p_14  = sum(e.k_16 for e in sprzedaz)
    t.p_15  = sum(e.k_17 for e in sprzedaz)
    t.p_16  = sum(e.k_18 for e in sprzedaz)
    t.p_19  = sum(e.k_19 for e in sprzedaz)
    t.p_20  = sum(e.k_20 for e in sprzedaz)
    t.p_33  = t.p_14 + t.p_16 + t.p_20
    t.p_40  = sum(e.k_41 for e in zakup)
    t.p_41  = sum(e.k_43 for e in zakup)
    vat_odl = t.p_40 + t.p_41
    if t.p_33 > vat_odl:
        t.p_49 = t.p_33 - vat_odl
    else:
        t.p_48 = vat_odl - t.p_33
    bfk_count = sum(1 for e in sprzedaz + zakup
                    if e.ksef_flag in ("OFF", "BFK", "DI"))
    t.p_360 = str(bfk_count) if bfk_count > 0 else None
    return t


def _last_day_of_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


def compute_xml_hash(xml_str: str) -> str:
    """SHA-256 of the JPK XML — stored in compliance_reports.hash."""
    return hashlib.sha256(xml_str.encode("utf-8")).hexdigest()
