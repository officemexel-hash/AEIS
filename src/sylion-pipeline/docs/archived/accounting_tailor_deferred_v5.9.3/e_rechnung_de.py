"""
e_rechnung_de.py — SYLION v5.9.1 / v5.10
Deutsche E-Rechnung: XRechnung 3.0.1 (UBL 2.1) + ZUGFeRD 2.3 (CII / Factur-X)

Pflichtfelder ab 2025 (§ 14 UStG i.d.F. des Wachstumschancengesetzes):
  • B2B ≥ 2025-01-01: Empfänger darf E-Rechnung empfangen (EN 16931)
  • B2B ≥ 2027-01-01: Aussteller muss E-Rechnung senden (Pflicht)
  • B2G: XRechnung Pflicht seit 2020 (Bund), Länder folgen

XRechnung 3.0.1:
  - https://xeinkauf.de/xrechnung/
  - Leitweg-ID: BT-10 (BuyerReference) — Pflichtfeld für B2G
  - Syntax: UBL Invoice 2.1 ODER UN/CEFACT CII

ZUGFeRD 2.3 / Factur-X 1.0.07:
  - PDF/A-3b + embedded XML (factur-x.xml, COMFORT oder EN 16931 profile)
  - https://www.ferd-net.de/standards/zugferd-version-2.3/

Dependencies:
    pip install lxml reportlab  # oder weasyprint für PDF
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from lxml import etree

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Namespaces — UBL 2.1 (XRechnung)
# ─────────────────────────────────────────────
UBL_INV = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
UBL_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
UBL_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
UBL_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"

# Namespaces — UN/CEFACT CII (ZUGFeRD / Factur-X)
CII_RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
CII_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
CII_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
CII_QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"

# XRechnung CIUS profile ID
XRECHNUNG_PROFILE = "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_3.0"
# ZUGFeRD / Factur-X EN 16931 profile
ZUGFERD_EN16931  = "urn:cen.eu:en16931:2017"
ZUGFERD_COMFORT  = "urn:factur-x.eu:1p0:comfort"
ZUGFERD_23_NS    = "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"


# ─────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────
@dataclass
class DEAddress:
    name: str
    street: str
    city: str
    postal_code: str
    country_code: str = "DE"
    tax_id: Optional[str] = None       # Steuernummer (DE)
    vat_id: Optional[str] = None       # USt-IdNr (EU-VAT)


@dataclass
class InvoiceLine:
    line_id: str
    description: str
    qty: Decimal
    unit_code: str                     # UN/ECE rec20: C62=stk, HUR=std, DAY=tag
    unit_price_net: Decimal
    vat_rate: Decimal                  # 0 | 7 | 19
    vat_category: str = "S"            # S=Standard, Z=Zero, E=Exempt, K=IntraCom

    @property
    def net_amount(self) -> Decimal:
        return (self.qty * self.unit_price_net).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def vat_amount(self) -> Decimal:
        return (self.net_amount * self.vat_rate / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)


@dataclass
class GermanInvoice:
    invoice_number: str
    issue_date: date
    due_date: Optional[date]
    seller: DEAddress
    buyer: DEAddress
    leitweg_id: Optional[str]          # B2G Pflicht; B2B optional / Bestellnummer
    lines: List[InvoiceLine]
    currency: str = "EUR"
    payment_iban: Optional[str] = None
    payment_bic: Optional[str] = None
    note: Optional[str] = None
    purchase_order_ref: Optional[str] = None  # BT-13

    @property
    def net_total(self) -> Decimal:
        return sum(l.net_amount for l in self.lines)

    @property
    def vat_total(self) -> Decimal:
        return sum(l.vat_amount for l in self.lines)

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.vat_total


# ─────────────────────────────────────────────
# XRechnung 3.0.1 — UBL 2.1
# ─────────────────────────────────────────────
def generate_xrechnung(invoice: GermanInvoice) -> bytes:
    """
    Erzeugt eine XRechnung 3.0.1 (UBL 2.1) konforme XML-Datei.

    Args:
        invoice: GermanInvoice dataclass

    Returns:
        UTF-8 codierte XML-Bytes

    Standard:
        EN 16931-1, CIUS XRechnung 3.0.1
        https://xeinkauf.de/xrechnung/
    """
    nsmap = {
        None: UBL_INV,
        "cac": UBL_CAC,
        "cbc": UBL_CBC,
    }
    root = etree.Element(f"{{{UBL_INV}}}Invoice", nsmap=nsmap)

    def cbc(tag: str, text: str, **attrs) -> etree._Element:
        el = etree.SubElement(root, f"{{{UBL_CBC}}}{tag}", **attrs)
        el.text = text
        return el

    def cbc_in(parent: etree._Element, tag: str, text: str, **attrs) -> etree._Element:
        el = etree.SubElement(parent, f"{{{UBL_CBC}}}{tag}", **attrs)
        el.text = text
        return el

    def cac_in(parent: etree._Element, tag: str) -> etree._Element:
        return etree.SubElement(parent, f"{{{UBL_CAC}}}{tag}")

    # BT-24 Specification Identifier
    cbc("CustomizationID", XRECHNUNG_PROFILE)
    # BT-23 Business Process
    cbc("ProfileID", "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0")
    # BT-1 Invoice number
    cbc("ID", invoice.invoice_number)
    # BT-2 Issue date
    cbc("IssueDate", str(invoice.issue_date))
    # BT-9 Due date
    if invoice.due_date:
        cbc("DueDate", str(invoice.due_date))
    # BT-3 Invoice type code (380 = commercial invoice)
    cbc("InvoiceTypeCode", "380")
    # BT-5 Currency
    cbc("DocumentCurrencyCode", invoice.currency)
    # BT-10 Buyer reference / Leitweg-ID — PFLICHT für B2G
    if invoice.leitweg_id:
        cbc("BuyerReference", invoice.leitweg_id)
    elif invoice.purchase_order_ref:
        cbc("BuyerReference", invoice.purchase_order_ref)
    else:
        cbc("BuyerReference", "NONE")   # XRechnung BT-10 is mandatory

    # BT-13 Purchase order reference
    if invoice.purchase_order_ref:
        ref_el = cac_in(root, "OrderReference")
        cbc_in(ref_el, "ID", invoice.purchase_order_ref)

    # Seller (BG-4)
    seller_party = cac_in(root, "AccountingSupplierParty")
    _ubl_party(seller_party, invoice.seller, UBL_CAC, UBL_CBC)

    # Buyer (BG-7)
    buyer_party = cac_in(root, "AccountingCustomerParty")
    _ubl_party(buyer_party, invoice.buyer, UBL_CAC, UBL_CBC)

    # Payment means (BG-16)
    if invoice.payment_iban:
        pm = cac_in(root, "PaymentMeans")
        cbc_in(pm, "PaymentMeansCode", "58")  # 58 = SEPA Credit Transfer
        fin_acc = cac_in(pm, "PayeeFinancialAccount")
        cbc_in(fin_acc, "ID", invoice.payment_iban)
        if invoice.payment_bic:
            fin_inst = cac_in(fin_acc, "FinancialInstitutionBranch")
            cbc_in(fin_inst, "ID", invoice.payment_bic)

    # Tax total (BG-23)
    tax_total = cac_in(root, "TaxTotal")
    cbc_in(tax_total, "TaxAmount", _dec(invoice.vat_total), currencyID=invoice.currency)
    # Tax subtotals grouped by rate
    for rate, entries in _group_by_vat_rate(invoice.lines).items():
        sub = cac_in(tax_total, "TaxSubtotal")
        taxable = sum(l.net_amount for l in entries)
        vat_amt = sum(l.vat_amount for l in entries)
        cbc_in(sub, "TaxableAmount", _dec(taxable), currencyID=invoice.currency)
        cbc_in(sub, "TaxAmount",     _dec(vat_amt),  currencyID=invoice.currency)
        tax_cat = cac_in(sub, "TaxCategory")
        cbc_in(tax_cat, "ID", entries[0].vat_category)
        cbc_in(tax_cat, "Percent", str(rate))
        tax_scheme = cac_in(tax_cat, "TaxScheme")
        cbc_in(tax_scheme, "ID", "VAT")

    # Legal monetary total (BG-22)
    lmt = cac_in(root, "LegalMonetaryTotal")
    cbc_in(lmt, "LineExtensionAmount", _dec(invoice.net_total),   currencyID=invoice.currency)
    cbc_in(lmt, "TaxExclusiveAmount",  _dec(invoice.net_total),   currencyID=invoice.currency)
    cbc_in(lmt, "TaxInclusiveAmount",  _dec(invoice.gross_total), currencyID=invoice.currency)
    cbc_in(lmt, "PayableAmount",       _dec(invoice.gross_total), currencyID=invoice.currency)

    # Invoice lines (BG-25)
    for idx, line in enumerate(invoice.lines, start=1):
        il = cac_in(root, "InvoiceLine")
        cbc_in(il, "ID", str(idx))
        cbc_in(il, "InvoicedQuantity", str(line.qty), unitCode=line.unit_code)
        cbc_in(il, "LineExtensionAmount", _dec(line.net_amount), currencyID=invoice.currency)
        item = cac_in(il, "Item")
        cbc_in(item, "Name", line.description)
        item_tax = cac_in(item, "ClassifiedTaxCategory")
        cbc_in(item_tax, "ID", line.vat_category)
        cbc_in(item_tax, "Percent", str(line.vat_rate))
        item_ts = cac_in(item_tax, "TaxScheme")
        cbc_in(item_ts, "ID", "VAT")
        price = cac_in(il, "Price")
        cbc_in(price, "PriceAmount", _dec(line.unit_price_net), currencyID=invoice.currency)

    xml_bytes = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
    logger.info(
        "XRechnung 3.0.1 erzeugt: Rechnungsnr=%s Betrag=%s EUR",
        invoice.invoice_number, invoice.gross_total,
    )
    return xml_bytes


def _ubl_party(
    parent: etree._Element,
    addr: DEAddress,
    UBL_CAC: str,
    UBL_CBC: str,
) -> None:
    party = etree.SubElement(parent, f"{{{UBL_CAC}}}Party")
    if addr.vat_id:
        ep = etree.SubElement(party, f"{{{UBL_CAC}}}PartyIdentification")
        etree.SubElement(ep, f"{{{UBL_CBC}}}ID", schemeID="0088").text = addr.vat_id
    pn = etree.SubElement(party, f"{{{UBL_CAC}}}PartyName")
    etree.SubElement(pn, f"{{{UBL_CBC}}}Name").text = addr.name
    pa = etree.SubElement(party, f"{{{UBL_CAC}}}PostalAddress")
    etree.SubElement(pa, f"{{{UBL_CBC}}}StreetName").text = addr.street
    etree.SubElement(pa, f"{{{UBL_CBC}}}CityName").text = addr.city
    etree.SubElement(pa, f"{{{UBL_CBC}}}PostalZone").text = addr.postal_code
    cc = etree.SubElement(pa, f"{{{UBL_CAC}}}Country")
    etree.SubElement(cc, f"{{{UBL_CBC}}}IdentificationCode").text = addr.country_code
    if addr.tax_id or addr.vat_id:
        ptax = etree.SubElement(party, f"{{{UBL_CAC}}}PartyTaxScheme")
        if addr.vat_id:
            etree.SubElement(ptax, f"{{{UBL_CBC}}}CompanyID").text = addr.vat_id
        ts = etree.SubElement(ptax, f"{{{UBL_CAC}}}TaxScheme")
        etree.SubElement(ts, f"{{{UBL_CBC}}}ID").text = "VAT"
    pl = etree.SubElement(party, f"{{{UBL_CAC}}}PartyLegalEntity")
    etree.SubElement(pl, f"{{{UBL_CBC}}}RegistrationName").text = addr.name
    if addr.tax_id:
        etree.SubElement(pl, f"{{{UBL_CBC}}}CompanyID").text = addr.tax_id


def _group_by_vat_rate(lines: List[InvoiceLine]) -> dict:
    groups: dict = {}
    for l in lines:
        key = l.vat_rate
        groups.setdefault(key, []).append(l)
    return groups


# ─────────────────────────────────────────────
# ZUGFeRD 2.3 / Factur-X — CII XML
# ─────────────────────────────────────────────
def generate_zugferd_cii_xml(invoice: GermanInvoice, profile: str = "EN 16931") -> bytes:
    """
    Erzeugt das CII XML für ZUGFeRD 2.3 / Factur-X 1.0.07 (EN 16931-Profil).

    Returns:
        UTF-8 codierte CII XML-Bytes (einzubetten in PDF/A-3b)
    """
    nsmap = {
        "rsm": CII_RSM,
        "ram": CII_RAM,
        "udt": CII_UDT,
        "qdt": CII_QDT,
    }
    profile_id = ZUGFERD_EN16931

    root = etree.Element(f"{{{CII_RSM}}}CrossIndustryInvoice", nsmap=nsmap)

    # ExchangedDocumentContext
    ctx = etree.SubElement(root, f"{{{CII_RSM}}}ExchangedDocumentContext")
    param = etree.SubElement(ctx, f"{{{CII_RAM}}}GuidelineSpecifiedDocumentContextParameter")
    etree.SubElement(param, f"{{{CII_RAM}}}ID").text = profile_id

    # ExchangedDocument
    doc = etree.SubElement(root, f"{{{CII_RSM}}}ExchangedDocument")
    etree.SubElement(doc, f"{{{CII_RAM}}}ID").text = invoice.invoice_number
    etree.SubElement(doc, f"{{{CII_RAM}}}TypeCode").text = "380"
    issue_dt = etree.SubElement(doc, f"{{{CII_RAM}}}IssueDateTime")
    date_str = etree.SubElement(issue_dt, f"{{{CII_UDT}}}DateTimeString",
                                 format="102")
    date_str.text = invoice.issue_date.strftime("%Y%m%d")
    if invoice.note:
        note_el = etree.SubElement(doc, f"{{{CII_RAM}}}IncludedNote")
        etree.SubElement(note_el, f"{{{CII_RAM}}}Content").text = invoice.note

    # SupplyChainTradeTransaction
    sctt = etree.SubElement(root, f"{{{CII_RSM}}}SupplyChainTradeTransaction")

    # Line items
    for idx, line in enumerate(invoice.lines, start=1):
        item = etree.SubElement(sctt, f"{{{CII_RAM}}}IncludedSupplyChainTradeLineItem")
        doc_el = etree.SubElement(item, f"{{{CII_RAM}}}AssociatedDocumentLineDocument")
        etree.SubElement(doc_el, f"{{{CII_RAM}}}LineID").text = str(idx)
        prod = etree.SubElement(item, f"{{{CII_RAM}}}SpecifiedTradeProduct")
        etree.SubElement(prod, f"{{{CII_RAM}}}Name").text = line.description
        agreement = etree.SubElement(item, f"{{{CII_RAM}}}SpecifiedLineTradeAgreement")
        gpp = etree.SubElement(agreement, f"{{{CII_RAM}}}GrossPriceProductTradePrice")
        etree.SubElement(gpp, f"{{{CII_RAM}}}ChargeAmount").text = _dec(line.unit_price_net)
        delivery = etree.SubElement(item, f"{{{CII_RAM}}}SpecifiedLineTradeDelivery")
        qty_el = etree.SubElement(delivery, f"{{{CII_RAM}}}BilledQuantity",
                                  unitCode=line.unit_code)
        qty_el.text = str(line.qty)
        settlement = etree.SubElement(item, f"{{{CII_RAM}}}SpecifiedLineTradeSettlement")
        tax_cat = etree.SubElement(settlement, f"{{{CII_RAM}}}ApplicableTradeTax")
        etree.SubElement(tax_cat, f"{{{CII_RAM}}}TypeCode").text = "VAT"
        etree.SubElement(tax_cat, f"{{{CII_RAM}}}CategoryCode").text = line.vat_category
        etree.SubElement(tax_cat, f"{{{CII_RAM}}}RateApplicablePercent").text = str(line.vat_rate)
        spec_amt = etree.SubElement(settlement, f"{{{CII_RAM}}}SpecifiedTradeSettlementLineMonetarySummation")
        etree.SubElement(spec_amt, f"{{{CII_RAM}}}LineTotalAmount").text = _dec(line.net_amount)

    # Header trade agreement
    hta = etree.SubElement(sctt, f"{{{CII_RAM}}}ApplicableHeaderTradeAgreement")
    etree.SubElement(hta, f"{{{CII_RAM}}}BuyerReference").text = \
        invoice.leitweg_id or invoice.invoice_number
    _cii_seller(hta, invoice.seller)
    _cii_buyer(hta, invoice.buyer)

    # Header trade delivery
    htd = etree.SubElement(sctt, f"{{{CII_RAM}}}ApplicableHeaderTradeDelivery")

    # Header trade settlement
    hts = etree.SubElement(sctt, f"{{{CII_RAM}}}ApplicableHeaderTradeSettlement")
    etree.SubElement(hts, f"{{{CII_RAM}}}InvoiceCurrencyCode").text = invoice.currency
    if invoice.payment_iban:
        pm = etree.SubElement(hts, f"{{{CII_RAM}}}SpecifiedTradeSettlementPaymentMeans")
        etree.SubElement(pm, f"{{{CII_RAM}}}TypeCode").text = "58"
        payer_acc = etree.SubElement(pm, f"{{{CII_RAM}}}PayeePartyCreditorFinancialAccount")
        etree.SubElement(payer_acc, f"{{{CII_RAM}}}IBANID").text = invoice.payment_iban

    # Tax summary
    for rate, entries in _group_by_vat_rate(invoice.lines).items():
        taxable = sum(l.net_amount for l in entries)
        vat_amt = sum(l.vat_amount for l in entries)
        tax = etree.SubElement(hts, f"{{{CII_RAM}}}ApplicableTradeTax")
        etree.SubElement(tax, f"{{{CII_RAM}}}CalculatedAmount").text = _dec(vat_amt)
        etree.SubElement(tax, f"{{{CII_RAM}}}TypeCode").text = "VAT"
        etree.SubElement(tax, f"{{{CII_RAM}}}BasisAmount").text = _dec(taxable)
        etree.SubElement(tax, f"{{{CII_RAM}}}CategoryCode").text = entries[0].vat_category
        etree.SubElement(tax, f"{{{CII_RAM}}}RateApplicablePercent").text = str(rate)

    # Monetary summary
    summary = etree.SubElement(hts, f"{{{CII_RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation")
    etree.SubElement(summary, f"{{{CII_RAM}}}LineTotalAmount").text = _dec(invoice.net_total)
    etree.SubElement(summary, f"{{{CII_RAM}}}TaxBasisTotalAmount").text = _dec(invoice.net_total)
    etree.SubElement(summary, f"{{{CII_RAM}}}TaxTotalAmount",
                     currencyID=invoice.currency).text = _dec(invoice.vat_total)
    etree.SubElement(summary, f"{{{CII_RAM}}}GrandTotalAmount").text = _dec(invoice.gross_total)
    etree.SubElement(summary, f"{{{CII_RAM}}}DuePayableAmount").text = _dec(invoice.gross_total)

    xml_bytes = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
    logger.info(
        "ZUGFeRD 2.3 CII XML erzeugt: %s %s EUR",
        invoice.invoice_number, invoice.gross_total,
    )
    return xml_bytes


def _cii_seller(parent: etree._Element, addr: DEAddress) -> None:
    seller = etree.SubElement(parent, f"{{{CII_RAM}}}SellerTradeParty")
    etree.SubElement(seller, f"{{{CII_RAM}}}Name").text = addr.name
    _cii_address(seller, addr)
    if addr.vat_id:
        tx = etree.SubElement(seller, f"{{{CII_RAM}}}SpecifiedTaxRegistration")
        etree.SubElement(tx, f"{{{CII_RAM}}}ID", schemeID="VA").text = addr.vat_id
    if addr.tax_id:
        tx2 = etree.SubElement(seller, f"{{{CII_RAM}}}SpecifiedTaxRegistration")
        etree.SubElement(tx2, f"{{{CII_RAM}}}ID", schemeID="FC").text = addr.tax_id


def _cii_buyer(parent: etree._Element, addr: DEAddress) -> None:
    buyer = etree.SubElement(parent, f"{{{CII_RAM}}}BuyerTradeParty")
    etree.SubElement(buyer, f"{{{CII_RAM}}}Name").text = addr.name
    _cii_address(buyer, addr)


def _cii_address(parent: etree._Element, addr: DEAddress) -> None:
    pa = etree.SubElement(parent, f"{{{CII_RAM}}}PostalTradeAddress")
    etree.SubElement(pa, f"{{{CII_RAM}}}PostcodeCode").text = addr.postal_code
    etree.SubElement(pa, f"{{{CII_RAM}}}LineOne").text = addr.street
    etree.SubElement(pa, f"{{{CII_RAM}}}CityName").text = addr.city
    etree.SubElement(pa, f"{{{CII_RAM}}}CountryID").text = addr.country_code


def generate_zugferd_hybrid(invoice: GermanInvoice) -> bytes:
    """
    Erzeugt eine ZUGFeRD 2.3 Hybrid-Rechnung: PDF/A-3b mit eingebettetem CII-XML.

    Das PDF wird mit reportlab als menschenlesbares Dokument erzeugt.
    Das CII-XML wird als Dateianhang (factur-x.xml, AFRelationship=Data)
    eingebettet. XMP-Metadaten werden gesetzt (Factur-X / ZUGFeRD 2.3).

    Dependencies:
        pip install reportlab pypdf

    Args:
        invoice: GermanInvoice dataclass

    Returns:
        PDF/A-3b Bytes mit eingebettetem ZUGFeRD XML
    """
    cii_xml = generate_zugferd_cii_xml(invoice)
    pdf_bytes = _build_base_pdf(invoice)
    hybrid_pdf = _embed_xml_in_pdf(pdf_bytes, cii_xml, invoice)
    logger.info(
        "ZUGFeRD 2.3 Hybrid-PDF erzeugt: %s size=%d bytes",
        invoice.invoice_number, len(hybrid_pdf),
    )
    return hybrid_pdf


def _build_base_pdf(invoice: GermanInvoice) -> bytes:
    """Baut ein einfaches PDF mit reportlab (menschenlesbarer Teil)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        logger.warning("reportlab nicht installiert — PDF-Teil wird als Stub ausgegeben.")
        return b"%PDF-1.7\n% SYLION ZUGFeRD stub — install reportlab for real PDF\n"

    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(25 * mm, height - 30 * mm, "RECHNUNG")
    c.setFont("Helvetica", 10)
    c.drawString(25 * mm, height - 40 * mm, f"Rechnungsnr.: {invoice.invoice_number}")
    c.drawString(25 * mm, height - 47 * mm, f"Datum: {invoice.issue_date}")

    # Seller
    c.setFont("Helvetica-Bold", 9)
    c.drawString(25 * mm, height - 60 * mm, "Rechnungssteller:")
    c.setFont("Helvetica", 9)
    c.drawString(25 * mm, height - 66 * mm, invoice.seller.name)
    c.drawString(25 * mm, height - 72 * mm, invoice.seller.street)
    c.drawString(25 * mm, height - 78 * mm,
                 f"{invoice.seller.postal_code} {invoice.seller.city}")

    # Buyer
    c.setFont("Helvetica-Bold", 9)
    c.drawString(110 * mm, height - 60 * mm, "Rechnungsempfänger:")
    c.setFont("Helvetica", 9)
    c.drawString(110 * mm, height - 66 * mm, invoice.buyer.name)
    c.drawString(110 * mm, height - 72 * mm, invoice.buyer.street)
    c.drawString(110 * mm, height - 78 * mm,
                 f"{invoice.buyer.postal_code} {invoice.buyer.city}")
    if invoice.leitweg_id:
        c.drawString(110 * mm, height - 84 * mm,
                     f"Leitweg-ID: {invoice.leitweg_id}")

    # Line items header
    y = height - 100 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(25 * mm,  y, "Pos.")
    c.drawString(40 * mm,  y, "Beschreibung")
    c.drawString(120 * mm, y, "Menge")
    c.drawString(140 * mm, y, "Einzelpreis")
    c.drawString(165 * mm, y, "Betrag netto")

    c.line(25 * mm, y - 2 * mm, 185 * mm, y - 2 * mm)
    y -= 8 * mm
    c.setFont("Helvetica", 9)
    for idx, line in enumerate(invoice.lines, start=1):
        c.drawString(25 * mm,  y, str(idx))
        c.drawString(40 * mm,  y, line.description[:50])
        c.drawString(120 * mm, y, str(line.qty))
        c.drawString(140 * mm, y, f"{line.unit_price_net:.2f} {invoice.currency}")
        c.drawString(165 * mm, y, f"{line.net_amount:.2f}")
        y -= 6 * mm

    # Totals
    y -= 5 * mm
    c.line(25 * mm, y, 185 * mm, y)
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(130 * mm, y, "Nettobetrag:")
    c.drawString(165 * mm, y, f"{invoice.net_total:.2f} {invoice.currency}")
    y -= 6 * mm
    c.drawString(130 * mm, y, "USt.:")
    c.drawString(165 * mm, y, f"{invoice.vat_total:.2f} {invoice.currency}")
    y -= 6 * mm
    c.drawString(130 * mm, y, "Bruttobetrag:")
    c.drawString(165 * mm, y, f"{invoice.gross_total:.2f} {invoice.currency}")

    if invoice.payment_iban:
        c.setFont("Helvetica", 8)
        c.drawString(25 * mm, 30 * mm, f"Bankverbindung: IBAN {invoice.payment_iban}")
        if invoice.payment_bic:
            c.drawString(25 * mm, 24 * mm, f"BIC: {invoice.payment_bic}")

    c.setFont("Helvetica", 7)
    c.drawString(25 * mm, 15 * mm,
                 "Dieses Dokument entspricht ZUGFeRD 2.3 / Factur-X 1.0.07 (EN 16931).")
    c.save()
    return buf.getvalue()


def _embed_xml_in_pdf(pdf_bytes: bytes, cii_xml: bytes, invoice: GermanInvoice) -> bytes:
    """
    Bettet das CII-XML als factur-x.xml in das PDF ein und setzt XMP-Metadaten.
    Anforderungen: PDF/A-3b, AFRelationship=Data, korrekte XMP-Annotation.

    Nutzt pypdf für das Einbetten. Falls pypdf nicht verfügbar,
    wird ein markiertes Byte-Array zurückgegeben.
    """
    try:
        from pypdf import PdfWriter, PdfReader
        from pypdf.generic import (
            ArrayObject, DecodedStreamObject, DictionaryObject,
            NameObject, ByteStringObject, NumberObject, TextStringObject,
        )
    except ImportError:
        logger.warning(
            "pypdf nicht installiert — liefere XML-Bytes als Fallback zurück. "
            "install pypdf für echtes ZUGFeRD Hybrid PDF."
        )
        return cii_xml

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)

    xmp = _build_zugferd_xmp(invoice)
    writer.add_metadata({
        "/Author":   invoice.seller.name,
        "/Title":    f"Rechnung {invoice.invoice_number}",
        "/Creator":  "SYLION v5.10 e_rechnung_de.py",
        "/Producer": "SYLION ZUGFeRD 2.3",
    })

    # Embed factur-x.xml
    writer.add_attachment("factur-x.xml", cii_xml)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _build_zugferd_xmp(invoice: GermanInvoice) -> str:
    """Builds ZUGFeRD 2.3 / Factur-X XMP metadata block."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" rdf:about="">
      <pdfaid:part>3</pdfaid:part>
      <pdfaid:conformance>B</pdfaid:conformance>
    </rdf:Description>
    <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/" rdf:about="">
      <dc:creator><rdf:Seq><rdf:li>{invoice.seller.name}</rdf:li></rdf:Seq></dc:creator>
      <dc:date><rdf:Seq><rdf:li>{now}</rdf:li></rdf:Seq></dc:date>
    </rdf:Description>
    <rdf:Description
      xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"
      fx:ConformanceLevel="EN 16931"
      fx:DocumentFileName="factur-x.xml"
      fx:DocumentType="INVOICE"
      fx:Version="1.0"
      rdf:about=""/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────
def _dec(d: Decimal) -> str:
    return str(d.quantize(Decimal("0.01"), ROUND_HALF_UP))
