"""
ksef_client.py — SYLION v5.9.1 / v5.10
KSeF 2.0 API client (Krajowy System e-Faktur)
Obowiązkowy KSeF od 2026-02-01 (VAT-UE + wszyscy zarejestrowani podatnicy VAT).

Endpoints (produkcja): https://ksef.mf.gov.pl/api
Endpoints (test):      https://ksef-test.mf.gov.pl/api

Schemat FA(2): https://ksef.mf.gov.pl/schema/FA(2)

Auth flow (token):
  1. POST /online/Session/AuthorisationChallenge   → challenge.timestamp + challenge.challenge
  2. Zbuduj InitSessionTokenRequest — podpisz tokenem (HMAC-SHA256 base64)
  3. POST /online/Session/InitToken                → sessionToken
  4. Użyj sessionToken w nagłówku SessionToken dla kolejnych zapytań
  5. POST /online/Invoice/Send                     → invoiceStatus (elementReferenceNumber)
  6. GET  /online/Invoice/Status/{referenceNumber} → processingCode
  7. POST /online/Session/Terminate                → sesja zamknięta → UPO dostępne
  8. GET  /online/Session/Status/{sessionReferenceNumber} → zawiera listę numerów KSeF
  9. GET  /common/Invoice/KSeF                     → pobierz faktury

Dependencies: httpx, lxml, cryptography
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx
from lxml import etree

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
KSEF_PROD_URL  = "https://ksef.mf.gov.pl/api"
KSEF_TEST_URL  = "https://ksef-test.mf.gov.pl/api"

FA2_NAMESPACE  = "http://crd.gov.pl/wzor/2023/06/29/9781/"
FA2_XSD_PATH   = "FA_VAT(2)_v1-0E.xsd"   # lokalnie zwaliduj przed wysłaniem

HTTP_TIMEOUT   = 30.0   # seconds


# ─────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────
@dataclass
class KSeFSession:
    session_token: str
    reference_number: str
    timestamp: str
    nip: str


@dataclass
class InvoiceStatus:
    element_reference_number: str
    processing_code: int           # 200 = OK, 400 = pending, 500 = error
    ksef_reference_number: Optional[str] = None
    status_description: str = ""
    acquisition_timestamp: Optional[str] = None


@dataclass
class KSeFConfig:
    nip: str                       # NIP podatnika (bez myślników)
    token: str                     # token KSeF wygenerowany w e-urzędzie skarbowym
    environment: str = "test"      # "test" | "prod"
    timeout: float = HTTP_TIMEOUT

    @property
    def base_url(self) -> str:
        return KSEF_PROD_URL if self.environment == "prod" else KSEF_TEST_URL


# ─────────────────────────────────────────────
# Core client
# ─────────────────────────────────────────────
class KSeFClient:
    """
    Async KSeF 2.0 REST client.

    Usage:
        cfg = KSeFConfig(nip="1234563218", token="abc...", environment="test")
        async with KSeFClient(cfg) as client:
            ksef_id = await client.send_invoice(fa2_xml_bytes)
            status  = await client.fetch_invoice_status(ksef_id)
            upo     = await client.download_upo(ksef_id)
    """

    def __init__(self, config: KSeFConfig):
        self.config = config
        self._http: Optional[httpx.AsyncClient] = None
        self._session: Optional[KSeFSession] = None

    async def __aenter__(self) -> "KSeFClient":
        self._http = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        await self._open_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._session:
                await self._close_session()
        finally:
            if self._http:
                await self._http.aclose()

    # ── Session management ────────────────────────────────
    async def _open_session(self) -> None:
        """Authenticates via token and opens an interactive KSeF session."""
        # Step 1 — challenge
        challenge_resp = await self._http.post(
            "/online/Session/AuthorisationChallenge",
            json={
                "contextIdentifier": {
                    "type": "onip",
                    "identifier": self.config.nip,
                }
            },
        )
        challenge_resp.raise_for_status()
        challenge_data = challenge_resp.json()
        challenge    = challenge_data["challenge"]
        timestamp_ms = challenge_data["timestamp"]

        # Step 2 — HMAC-SHA256 signature over challenge
        signature = self._sign_token(challenge, timestamp_ms)

        # Step 3 — init session
        init_resp = await self._http.post(
            "/online/Session/InitToken",
            json={
                "context": {
                    "challenge": {
                        "challenge": challenge,
                        "timestamp": timestamp_ms,
                    },
                    "identifier": {
                        "type": "onip",
                        "identifier": self.config.nip,
                    },
                    "token": {
                        "value": signature,
                    },
                }
            },
        )
        init_resp.raise_for_status()
        session_data = init_resp.json()

        self._session = KSeFSession(
            session_token=session_data["sessionToken"]["token"],
            reference_number=session_data["sessionToken"]["referenceNumber"],
            timestamp=session_data["timestamp"],
            nip=self.config.nip,
        )
        # Inject session token into default headers
        self._http.headers["SessionToken"] = self._session.session_token
        logger.info("KSeF session opened: ref=%s", self._session.reference_number)

    async def _close_session(self) -> None:
        """Terminates the session and makes UPO available."""
        resp = await self._http.get(
            f"/online/Session/Terminate"
        )
        if resp.status_code not in (200, 201):
            logger.warning("KSeF session terminate returned %d", resp.status_code)
        else:
            logger.info("KSeF session terminated: ref=%s", self._session.reference_number)
        self._session = None

    def _sign_token(self, challenge: str, timestamp_ms: int) -> str:
        """
        Builds the token signature per KSeF 2.0 spec:
        HMAC-SHA256( base64(token) || '|' || timestamp_ms_str, challenge )
        returned as base64-encoded string.
        """
        token_b64  = base64.b64encode(self.config.token.encode()).decode()
        message    = f"{token_b64}|{timestamp_ms}".encode()
        signature  = hmac.new(challenge.encode(), message, hashlib.sha256).digest()
        return base64.b64encode(signature).decode()

    # ── Public API ────────────────────────────────────────
    async def send_invoice(self, fa2_xml: bytes) -> str:
        """
        Sends a FA(2)-compliant XML invoice to KSeF.

        Args:
            fa2_xml: Valid UTF-8 XML bytes conforming to FA_VAT(2) schema.

        Returns:
            element_reference_number — use to poll status until ksef_reference_number assigned.

        Raises:
            httpx.HTTPStatusError: on HTTP error
            ValueError: if XML fails basic sanity checks
        """
        _validate_fa2_xml(fa2_xml)

        invoice_b64 = base64.b64encode(fa2_xml).decode()
        invoice_hash = hashlib.sha256(fa2_xml).hexdigest()

        payload = {
            "invoiceHash": {
                "hashSHA": {
                    "algorithm": "SHA-256",
                    "encoding": "Base64",
                    "value": base64.b64encode(bytes.fromhex(invoice_hash)).decode(),
                },
                "fileSize": len(fa2_xml),
            },
            "invoicePayload": {
                "type": "plain",
                "invoiceBody": invoice_b64,
            },
        }

        resp = await self._http.put(
            "/online/Invoice/Send",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        element_ref = data["elementReferenceNumber"]
        logger.info("Invoice sent to KSeF: elementRef=%s", element_ref)
        return element_ref

    async def fetch_invoice_status(self, element_reference_number: str) -> InvoiceStatus:
        """
        Polls KSeF for invoice processing status.

        processingCode values:
          200 — accepted (ksef_reference_number populated)
          400 — processing in progress
          500 — rejected (check processingDescription)

        Args:
            element_reference_number: returned by send_invoice()

        Returns:
            InvoiceStatus dataclass
        """
        resp = await self._http.get(
            f"/online/Invoice/Status/{element_reference_number}"
        )
        resp.raise_for_status()
        data = resp.json()

        status = InvoiceStatus(
            element_reference_number=element_reference_number,
            processing_code=data.get("processingCode", 0),
            ksef_reference_number=data.get("ksefReferenceNumber"),
            status_description=data.get("processingDescription", ""),
            acquisition_timestamp=data.get("acquisitionTimestamp"),
        )
        logger.debug(
            "KSeF status: ref=%s code=%d ksef_ref=%s",
            element_reference_number,
            status.processing_code,
            status.ksef_reference_number,
        )
        return status

    async def poll_until_accepted(
        self,
        element_reference_number: str,
        max_attempts: int = 20,
        interval_s: float = 3.0,
    ) -> InvoiceStatus:
        """
        Polls fetch_invoice_status() until processingCode == 200 or max_attempts exhausted.
        """
        for attempt in range(1, max_attempts + 1):
            status = await self.fetch_invoice_status(element_reference_number)
            if status.processing_code == 200:
                logger.info(
                    "KSeF accepted after %d attempt(s): ksef_id=%s",
                    attempt, status.ksef_reference_number,
                )
                return status
            if status.processing_code == 500:
                raise ValueError(
                    f"KSeF rejected invoice: {status.status_description}"
                )
            logger.debug("KSeF pending (attempt %d/%d)...", attempt, max_attempts)
            await _async_sleep(interval_s)

        raise TimeoutError(
            f"KSeF did not accept invoice after {max_attempts} attempts"
        )

    async def download_upo(self, ksef_id: str) -> bytes:
        """
        Downloads UPO (Urzędowe Poświadczenie Odbioru) for an accepted invoice.

        The session must be TERMINATED before UPO becomes available.
        This method auto-terminates the session if still open.

        Args:
            ksef_id: NumerKSeF (ksef_reference_number from InvoiceStatus)

        Returns:
            PDF bytes of the UPO document.
        """
        if self._session:
            await self._close_session()

        # UPO is an XML; the MF system also provides a PDF rendering
        resp = await self._http.get(
            f"/common/Invoice/KSeF",
            params={"InvoiceKsefNumber": ksef_id},
            headers={"Accept": "application/octet-stream"},
        )
        resp.raise_for_status()
        upo_bytes = resp.content
        logger.info(
            "UPO downloaded: ksef_id=%s size=%d bytes", ksef_id, len(upo_bytes)
        )
        return upo_bytes

    async def get_session_upo(self) -> bytes:
        """
        Downloads session-level UPO after closing the session.
        Contains all invoices sent in the session.
        """
        if not self._session:
            raise RuntimeError("Session already closed; no reference available.")
        ref = self._session.reference_number
        await self._close_session()

        resp = await self._http.get(
            f"/online/Session/Status/{ref}",
        )
        resp.raise_for_status()
        # The session status response includes invoice-level KSeF reference numbers
        return resp.content


# ─────────────────────────────────────────────
# FA(2) XML builder helper
# ─────────────────────────────────────────────
def build_fa2_xml(invoice: dict) -> bytes:
    """
    Builds a minimal FA(2) XML (KSeF schema) from an invoice dict.

    Required keys in `invoice`:
        number, issue_date (str YYYY-MM-DD), seller_nip, seller_name,
        seller_address, buyer_nip, buyer_name, buyer_address,
        lines: list of {description, qty, unit_price, vat_rate}
        currency (default PLN)

    Returns:
        UTF-8 encoded XML bytes
    """
    ns   = FA2_NAMESPACE
    date = invoice["issue_date"]
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    root = etree.Element(
        f"{{{ns}}}Faktura",
        nsmap={"etd": ns},
    )

    # Nagłówek
    header = etree.SubElement(root, f"{{{ns}}}Naglowek")
    etree.SubElement(header, f"{{{ns}}}KodFormularza",
                     kodSystemowy="FA (2)", wersjaSchemy="1-0E").text = "FA"
    etree.SubElement(header, f"{{{ns}}}WariantFormularza").text = "2"
    etree.SubElement(header, f"{{{ns}}}DataWytworzeniaFa").text = now
    etree.SubElement(header, f"{{{ns}}}NazwaSystemu").text = "SYLION v5.10"

    # Podmiot1 (sprzedawca)
    p1 = etree.SubElement(root, f"{{{ns}}}Podmiot1")
    sp = etree.SubElement(p1, f"{{{ns}}}DaneIdentyfikacyjne")
    etree.SubElement(sp, f"{{{ns}}}NIP").text = invoice["seller_nip"]
    etree.SubElement(sp, f"{{{ns}}}PelnaNazwa").text = invoice["seller_name"]
    _add_address(p1, ns, invoice["seller_address"])

    # Podmiot2 (nabywca)
    p2 = etree.SubElement(root, f"{{{ns}}}Podmiot2")
    nb = etree.SubElement(p2, f"{{{ns}}}DaneIdentyfikacyjne")
    etree.SubElement(nb, f"{{{ns}}}NIP").text = invoice.get("buyer_nip", "")
    etree.SubElement(nb, f"{{{ns}}}PelnaNazwa").text = invoice["buyer_name"]
    _add_address(p2, ns, invoice["buyer_address"])

    # Fa (dane faktury)
    fa = etree.SubElement(root, f"{{{ns}}}Fa")
    etree.SubElement(fa, f"{{{ns}}}KodWaluty").text = invoice.get("currency", "PLN")
    etree.SubElement(fa, f"{{{ns}}}P_1").text = date        # data wystawienia
    etree.SubElement(fa, f"{{{ns}}}P_2").text = invoice["number"]  # numer faktury
    etree.SubElement(fa, f"{{{ns}}}RodzajFaktury").text = "VAT"

    # Linie faktury
    net_total = 0.0
    vat_total = 0.0
    for idx, line in enumerate(invoice.get("lines", []), start=1):
        net  = round(line["qty"] * line["unit_price"], 2)
        vat  = round(net * line["vat_rate"] / 100, 2)
        net_total += net
        vat_total += vat

        fa_row = etree.SubElement(fa, f"{{{ns}}}FaWiersz")
        etree.SubElement(fa_row, f"{{{ns}}}NrWierszaFa").text = str(idx)
        etree.SubElement(fa_row, f"{{{ns}}}P_7").text  = line["description"]
        etree.SubElement(fa_row, f"{{{ns}}}P_8A").text = str(line.get("unit", "szt"))
        etree.SubElement(fa_row, f"{{{ns}}}P_8B").text = str(line["qty"])
        etree.SubElement(fa_row, f"{{{ns}}}P_9A").text = f"{line['unit_price']:.2f}"
        etree.SubElement(fa_row, f"{{{ns}}}P_11").text = f"{net:.2f}"
        etree.SubElement(fa_row, f"{{{ns}}}P_12").text = str(int(line["vat_rate"]))

    # Sumy
    etree.SubElement(fa, f"{{{ns}}}P_13_1").text = f"{net_total:.2f}"  # netto 23%
    etree.SubElement(fa, f"{{{ns}}}P_14_1").text = f"{vat_total:.2f}"  # VAT 23%
    etree.SubElement(fa, f"{{{ns}}}P_15").text   = f"{net_total + vat_total:.2f}"

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _add_address(parent: etree._Element, ns: str, addr: dict) -> None:
    adres = etree.SubElement(parent, f"{{{ns}}}Adres")
    etree.SubElement(adres, f"{{{ns}}}AdresL1").text = addr.get("street", "")
    etree.SubElement(adres, f"{{{ns}}}KodPocztowy").text = addr.get("postal_code", "")
    etree.SubElement(adres, f"{{{ns}}}Miejscowosc").text = addr.get("city", "")


def _validate_fa2_xml(xml_bytes: bytes) -> None:
    """Minimal sanity check — production should validate against FA(2) XSD."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Invalid FA(2) XML: {exc}") from exc
    if "Faktura" not in root.tag:
        raise ValueError(
            "XML root element must be <Faktura> per KSeF FA(2) schema"
        )


async def _async_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)
