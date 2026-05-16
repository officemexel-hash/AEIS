"""
gobd_retention.py — SYLION v5.9.1 / v5.10
GoBD-konforme Aufbewahrung und Unveränderlichkeit für RSDG GmbH (DE).

Rechtliche Grundlagen:
  • GoBD 2019 (BMF-Schreiben 28.11.2019)     — Unveränderlichkeit, maschinelle Lesbarkeit
  • HGB §257                                  — 10 Jahre Aufbewahrungsfrist (Handelsbücher, Belege)
  • AO §147                                   — 10 Jahre (steuerrelevante Unterlagen)
  • GoBD Rn. 103                              — WORM (Write Once Read Many) oder äquivalenter Schutz
  • DSGVO Art. 5 Abs. 1 lit. e                — Speicherbegrenzung (Interessenabwägung)

Architektur:
  - WORM-Flag in DB (is_worm_locked) + DB-Trigger (fn_worm_guard)
  - Hashchain (SHA-256): jedes Dokument bekommt einen Hash;
    jeder Audit-Eintrag kettet Hash(prev_hash || content) → Manipulationsnachweis
  - Retention-Scan: täglich cron job, archiviert fällige Dokumente
  - Audit-Trail: audit_trail_accounting (10 Jahre, INSERT-only)
  - Cloud-WORM: S3 Object Lock / GCS Bucket Lock Konfigurationshelfer

Dieses Modul enthält:
  1. WORMManager     — Setzt WORM-Lock, berechnet und speichert Hash
  2. RetentionPolicy — 10-Jahres-Regel, Berechnungen, Fälligkeitsprüfung
  3. AuditTrailWriter— Schreibt in audit_trail_accounting (immutable INSERT)
  4. HashChain       — Blockchain-ähnliche Integritätskette
  5. S3WORMConfig    — AWS S3 Object Lock Konfiguration
  6. GCSWORMConfig   — Google Cloud Storage Bucket Lock Konfiguration
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
RETENTION_YEARS      = 10      # HGB §257 / AO §147
COMMERCIAL_LETTERS_Y = 6       # HGB §257 Abs. 4 (Handelsbriefe)
WORM_HASH_ALGORITHM  = "sha256"


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────
class DocumentType(str, Enum):
    INVOICE         = "invoice"
    COMPLIANCE_REPORT = "compliance_report"
    BOOKING_JOURNAL = "booking_journal"
    ANNUAL_ACCOUNT  = "annual_account"
    BANK_STATEMENT  = "bank_statement"
    CONTRACT        = "contract"
    COMMERCIAL_LETTER = "commercial_letter"


class AuditAction(str, Enum):
    CREATE          = "CREATE"
    UPDATE          = "UPDATE"
    DELETE          = "DELETE"
    WORM_LOCK       = "WORM_LOCK"
    EXPORT          = "EXPORT"
    SUBMIT          = "SUBMIT"
    VIEW            = "VIEW"
    DOWNLOAD_UPO    = "DOWNLOAD_UPO"
    RETENTION_SCAN  = "RETENTION_SCAN"
    ARCHIVE         = "ARCHIVE"
    HASH_VERIFIED   = "HASH_VERIFIED"
    HASH_MISMATCH   = "HASH_MISMATCH"


# ─────────────────────────────────────────────
# RetentionPolicy
# ─────────────────────────────────────────────
class RetentionPolicy:
    """
    Berechnet Aufbewahrungsfristen nach HGB §257 / AO §147 / GoBD 2019.

    Aufbewahrungsfristen:
      10 Jahre: Handelsbücher, Inventare, Jahresabschlüsse, Buchungsbelege (inkl. E-Rechnungen)
       6 Jahre: Handelsbriefe (empfangen + gesendet), Angebote etc.

    Frist beginnt: Ende des Kalenderjahres, in dem das Dokument erstellt wurde.
    """

    @staticmethod
    def retention_end(document_date: date, doc_type: DocumentType) -> date:
        """
        Berechnet das Ende der Aufbewahrungsfrist.

        Args:
            document_date: Datum des Belegs (z.B. Rechnungsdatum)
            doc_type:      Dokumenttyp

        Returns:
            Letzter Aufbewahrungstag (document kann danach gelöscht werden)
        """
        if doc_type == DocumentType.COMMERCIAL_LETTER:
            years = COMMERCIAL_LETTERS_Y
        else:
            years = RETENTION_YEARS

        # Frist ab Ende des Entstehungsjahres
        year_end = date(document_date.year, 12, 31)
        return year_end + timedelta(days=years * 365 + 2)  # +2 leap day buffer

    @staticmethod
    def is_overdue_for_deletion(document_date: date, doc_type: DocumentType) -> bool:
        """True wenn die Aufbewahrungsfrist abgelaufen ist."""
        return date.today() > RetentionPolicy.retention_end(document_date, doc_type)

    @staticmethod
    def must_be_retained(document_date: date, doc_type: DocumentType) -> bool:
        """True solange das Dokument aufbewahrt werden muss (Frist läuft noch)."""
        return not RetentionPolicy.is_overdue_for_deletion(document_date, doc_type)

    @staticmethod
    def days_remaining(document_date: date, doc_type: DocumentType) -> int:
        """Verbleibende Aufbewahrungstage (negativ = Frist abgelaufen)."""
        end = RetentionPolicy.retention_end(document_date, doc_type)
        return (end - date.today()).days


# ─────────────────────────────────────────────
# HashChain
# ─────────────────────────────────────────────
@dataclass
class HashChainEntry:
    sequence_id: int
    document_id: str
    document_hash: str          # SHA-256 des Dokument-Inhalts
    chain_hash: str             # SHA-256(prev_chain_hash || document_hash)
    timestamp: str
    actor_id: Optional[str]


class HashChain:
    """
    Manipulationsresistente Hashkette für GoBD-konforme Unveränderlichkeit.

    Jeder neue Eintrag verknüpft: chain_hash = SHA-256(prev_chain_hash + document_hash)
    → Wie eine Blockchain-ähnliche Integritätskette.
    → Jede nachträgliche Änderung bricht alle nachfolgenden chain_hashes.

    Speicherung: In-memory für Tests; in Produktion in
    audit_trail_accounting.payload_hash oder separater chain-Tabelle.
    """

    GENESIS_HASH = "0" * 64  # Startwert der Kette

    def __init__(self) -> None:
        self._entries: List[HashChainEntry] = []
        self._last_chain_hash = self.GENESIS_HASH

    def append(
        self,
        document_id: str,
        content: bytes,
        actor_id: Optional[str] = None,
    ) -> HashChainEntry:
        """
        Fügt ein Dokument der Hashkette hinzu.

        Args:
            document_id: UUID oder Kennung des Dokuments
            content:     Byte-Inhalt des Dokuments (XML, PDF, JSON)
            actor_id:    Kennung des auslösenden Nutzers/Systems

        Returns:
            HashChainEntry mit dokumentiertem chain_hash
        """
        doc_hash   = hashlib.sha256(content).hexdigest()
        chain_data = (self._last_chain_hash + doc_hash).encode()
        chain_hash = hashlib.sha256(chain_data).hexdigest()
        seq_id     = len(self._entries) + 1
        ts         = datetime.now(timezone.utc).isoformat()

        entry = HashChainEntry(
            sequence_id=seq_id,
            document_id=document_id,
            document_hash=doc_hash,
            chain_hash=chain_hash,
            timestamp=ts,
            actor_id=actor_id,
        )
        self._entries.append(entry)
        self._last_chain_hash = chain_hash
        logger.debug(
            "HashChain: seq=%d doc_id=%s chain_hash=%.16s...",
            seq_id, document_id, chain_hash,
        )
        return entry

    def verify_chain(self) -> bool:
        """
        Verifiziert die gesamte Kette von Anfang an.

        Returns:
            True wenn Kette integer ist, False bei Manipulation
        """
        prev_hash = self.GENESIS_HASH
        for entry in self._entries:
            expected_chain = hashlib.sha256(
                (prev_hash + entry.document_hash).encode()
            ).hexdigest()
            if expected_chain != entry.chain_hash:
                logger.error(
                    "HashChain-Manipulation entdeckt: seq=%d doc_id=%s",
                    entry.sequence_id, entry.document_id,
                )
                return False
            prev_hash = entry.chain_hash
        logger.info("HashChain verifiziert: %d Einträge integer.", len(self._entries))
        return True

    def export_json(self) -> str:
        return json.dumps(
            [asdict(e) for e in self._entries], indent=2, ensure_ascii=False
        )


# ─────────────────────────────────────────────
# AuditTrailWriter
# ─────────────────────────────────────────────
@dataclass
class AuditEvent:
    object_type: str
    object_id: str
    action: AuditAction
    actor_id: Optional[str] = None
    actor_service: Optional[str] = None
    actor_ip: Optional[str] = None
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ksef_id: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

    def to_db_row(self, retain_until: date) -> Dict[str, Any]:
        ip_hash = None
        if self.actor_ip:
            ip_hash = hashlib.sha256(self.actor_ip.encode()).hexdigest()
        payload = json.dumps(asdict(self), ensure_ascii=False, default=str)
        return {
            "event_time":    datetime.now(timezone.utc).isoformat(),
            "actor_id":      self.actor_id,
            "actor_ip":      self.actor_ip,
            "ip_hash":       ip_hash,
            "actor_service": self.actor_service,
            "object_type":   self.object_type,
            "object_id":     self.object_id,
            "action":        self.action.value,
            "field_name":    self.field_name,
            "old_value":     self.old_value,
            "new_value":     self.new_value,
            "ksef_id":       self.ksef_id,
            "session_id":    self.session_id,
            "retain_until":  str(retain_until),
            "payload_hash":  hashlib.sha256(payload.encode()).hexdigest(),
        }


class AuditTrailWriter:
    """
    Schreibt GoBD-konforme Audit-Ereignisse in audit_trail_accounting.

    Die Tabelle ist INSERT-only (PG-Regeln verhindern UPDATE + DELETE).
    Aufbewahrung: 10 Jahre (AO §147 / HGB §257).

    Verwendung mit SQLAlchemy AsyncSession oder direktem psycopg2-Connection.
    """

    RETENTION_YEARS = RETENTION_YEARS
    TABLE           = "audit_trail_accounting"

    def __init__(self, db_conn=None):
        """
        Args:
            db_conn: psycopg2 connection, asyncpg connection,
                     oder None (dry-run / test mode)
        """
        self._conn = db_conn
        self._pending: List[Dict[str, Any]] = []

    def record(self, event: AuditEvent) -> Dict[str, Any]:
        """
        Erstellt einen Audit-Datensatz.

        Args:
            event: AuditEvent

        Returns:
            Datensatz-Dict (noch nicht in DB geschrieben wenn db_conn=None)
        """
        retain_until = date.today() + timedelta(days=self.RETENTION_YEARS * 365 + 2)
        row = event.to_db_row(retain_until)
        self._pending.append(row)
        if self._conn:
            self._flush_sync(row)
        logger.debug(
            "AuditTrail [%s]: %s %s %s",
            row["event_time"], event.action.value,
            event.object_type, event.object_id,
        )
        return row

    def record_worm_lock(
        self,
        object_type: str,
        object_id: str,
        content_hash: str,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convenience: protokolliert WORM-Lock-Ereignis."""
        return self.record(AuditEvent(
            object_type=object_type,
            object_id=object_id,
            action=AuditAction.WORM_LOCK,
            actor_id=actor_id,
            actor_service="gobd_retention",
            new_value=content_hash,
            extra={"note": "GoBD WORM lock applied — document is now immutable"},
        ))

    def record_hash_verification(
        self,
        object_id: str,
        computed_hash: str,
        stored_hash: str,
        matched: bool,
    ) -> Dict[str, Any]:
        """Protokolliert Hashketten-Verifikation (GoBD Nachweisführung)."""
        return self.record(AuditEvent(
            object_type="hash_chain",
            object_id=object_id,
            action=AuditAction.HASH_VERIFIED if matched else AuditAction.HASH_MISMATCH,
            actor_service="gobd_retention",
            old_value=stored_hash,
            new_value=computed_hash,
            extra={"integrity": "OK" if matched else "VIOLATION"},
        ))

    def _flush_sync(self, row: Dict[str, Any]) -> None:
        """Writes a single row to DB (synchronous psycopg2-style)."""
        cols   = ", ".join(row.keys())
        placeholders = ", ".join(f"%({k})s" for k in row.keys())
        sql = f"INSERT INTO {self.TABLE} ({cols}) VALUES ({placeholders})"
        try:
            cur = self._conn.cursor()
            cur.execute(sql, row)
            self._conn.commit()
        except Exception as exc:
            logger.error("AuditTrail DB write failed: %s", exc)
            raise

    def flush_pending(self) -> List[Dict[str, Any]]:
        """Returns accumulated dry-run rows and clears buffer."""
        rows = list(self._pending)
        self._pending.clear()
        return rows


# ─────────────────────────────────────────────
# WORMManager
# ─────────────────────────────────────────────
class WORMManager:
    """
    Setzt den WORM-Lock für Rechnungen und Compliance-Berichte.

    GoBD Rn. 103: „Die Unveränderlichkeit kann durch organisatorische
    oder technische Maßnahmen sichergestellt werden."

    Technische Maßnahmen in SYLION:
      1. DB-Trigger fn_worm_guard — blockiert UPDATE/DELETE nach Lock
      2. hash_sha256 in invoices — SHA-256 des kanonischen XML
      3. Cloud-WORM: S3 Object Lock COMPLIANCE mode / GCS Bucket Lock
      4. Audit-Eintrag in audit_trail_accounting
    """

    def __init__(
        self,
        audit_writer: Optional[AuditTrailWriter] = None,
        hash_chain: Optional[HashChain] = None,
    ):
        self.audit = audit_writer or AuditTrailWriter()
        self.chain = hash_chain or HashChain()

    def lock_invoice(
        self,
        invoice_id: str,
        content: bytes,
        actor_id: Optional[str] = None,
        db_update_fn=None,
    ) -> str:
        """
        Setzt WORM-Lock auf eine Rechnung.

        Args:
            invoice_id:   UUID der Rechnung (str)
            content:      Kanonisches XML oder JSON der Rechnung
            actor_id:     Benutzer/Service der den Lock auslöst
            db_update_fn: Callable(invoice_id, hash, locked_at) → None
                          Führt DB UPDATE aus (vor Lock durch Trigger erlaubt)

        Returns:
            SHA-256 Hashwert (hex) des Dokuments
        """
        doc_hash = hashlib.sha256(content).hexdigest()
        chain_entry = self.chain.append(invoice_id, content, actor_id)
        locked_at = datetime.now(timezone.utc)

        if db_update_fn:
            try:
                db_update_fn(invoice_id, doc_hash, locked_at)
            except Exception as exc:
                logger.error("WORM DB lock failed for %s: %s", invoice_id, exc)
                raise

        self.audit.record_worm_lock(
            object_type="invoice",
            object_id=invoice_id,
            content_hash=doc_hash,
            actor_id=actor_id,
        )
        logger.info(
            "WORM locked: invoice_id=%s hash=%.16s... chain_seq=%d",
            invoice_id, doc_hash, chain_entry.sequence_id,
        )
        return doc_hash

    def lock_compliance_report(
        self,
        report_id: str,
        content: bytes,
        actor_id: Optional[str] = None,
        db_update_fn=None,
    ) -> str:
        """Setzt WORM-Lock auf einen Compliance-Bericht (JPK, GoBD-Export etc.)."""
        doc_hash = hashlib.sha256(content).hexdigest()
        chain_entry = self.chain.append(report_id, content, actor_id)
        locked_at = datetime.now(timezone.utc)

        if db_update_fn:
            db_update_fn(report_id, doc_hash, locked_at)

        self.audit.record_worm_lock(
            object_type="compliance_report",
            object_id=report_id,
            content_hash=doc_hash,
            actor_id=actor_id,
        )
        logger.info(
            "WORM locked: report_id=%s hash=%.16s...", report_id, doc_hash
        )
        return doc_hash

    def verify_document(
        self, document_id: str, current_content: bytes, stored_hash: str
    ) -> bool:
        """
        Prüft Integrität durch Neuberechnung und Vergleich mit gespeichertem Hash.

        Gibt True zurück wenn Hash übereinstimmt (Dokument unverändert).
        Protokolliert Ergebnis in audit_trail_accounting.
        """
        computed = hashlib.sha256(current_content).hexdigest()
        matched  = computed == stored_hash
        self.audit.record_hash_verification(
            document_id, computed, stored_hash, matched
        )
        if not matched:
            logger.error(
                "INTEGRITÄTSVERLETZUNG: document_id=%s stored=%.16s... computed=%.16s...",
                document_id, stored_hash, computed,
            )
        return matched


# ─────────────────────────────────────────────
# Cloud WORM Configurations
# ─────────────────────────────────────────────
@dataclass
class S3WORMConfig:
    """
    AWS S3 Object Lock Konfiguration für GoBD-konforme Archivierung.

    COMPLIANCE mode: selbst der Root-Account kann nicht löschen.
    GOVERNANCE mode: nur berechtigte IAM-Rollen können überschreiben.

    GoBD-Empfehlung: COMPLIANCE mode für steuerrelevante Unterlagen.
    """
    bucket_name: str
    region: str = "eu-central-1"    # Frankfurt — DSGVO-konform
    retention_mode: str = "COMPLIANCE"   # COMPLIANCE | GOVERNANCE
    retention_days: int = RETENTION_YEARS * 365 + 30  # +30 Puffer

    def get_object_lock_config(self) -> Dict[str, Any]:
        return {
            "ObjectLockEnabled": "Enabled",
            "Rule": {
                "DefaultRetention": {
                    "Mode": self.retention_mode,
                    "Days": self.retention_days,
                }
            },
        }

    def get_put_object_args(self, key: str) -> Dict[str, Any]:
        """Argumente für boto3 put_object mit WORM-Schutz."""
        retain_until = (
            datetime.now(timezone.utc) + timedelta(days=self.retention_days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "Bucket":                    self.bucket_name,
            "Key":                       key,
            "ObjectLockMode":            self.retention_mode,
            "ObjectLockRetainUntilDate": retain_until,
        }

    def boto3_enable_bucket_lock(self) -> str:
        """Gibt boto3-Code als String zurück (für Infrastruktur-Setup)."""
        return f"""
import boto3, datetime
s3 = boto3.client('s3', region_name='{self.region}')
s3.put_object_lock_configuration(
    Bucket='{self.bucket_name}',
    ObjectLockConfiguration={self.get_object_lock_config()!r}
)
print("S3 Object Lock COMPLIANCE aktiviert auf s3://{self.bucket_name}")
"""


@dataclass
class GCSWORMConfig:
    """
    Google Cloud Storage Bucket Lock (Retention Policy) für GoBD.

    Bucket Lock macht Retention Policy permanent unwiderruflich.
    """
    bucket_name: str
    project_id: str
    retention_seconds: int = RETENTION_YEARS * 365 * 24 * 3600
    location: str = "europe-west3"    # Frankfurt

    def gsutil_command(self) -> str:
        """gsutil Kommando zum Setzen der Retention Policy."""
        days = self.retention_seconds // 86400
        return (
            f"gsutil retention set {days}d gs://{self.bucket_name}\n"
            f"gsutil retention lock gs://{self.bucket_name}"
        )

    def python_client_code(self) -> str:
        return f"""
from google.cloud import storage
from datetime import timedelta
client = storage.Client(project='{self.project_id}')
bucket = client.get_bucket('{self.bucket_name}')
bucket.retention_period = timedelta(seconds={self.retention_seconds})
bucket.patch()
bucket.make_public = False
# Bucket Lock — unwiderruflich!
bucket.lock_retention_policy()
print("GCS Retention Policy locked: gs://{self.bucket_name}")
"""


# ─────────────────────────────────────────────
# Retention Scanner (für cron job)
# ─────────────────────────────────────────────
class RetentionScanner:
    """
    Täglicher Scan für Retention-Aktionen:
      - Identifiziert Dokumente deren 10-Jahres-Frist abgelaufen ist
      - Triggert Archivierung in WORM-Speicher
      - Protokolliert in audit_trail_accounting

    Aufruf: täglich via cron / Celery Beat / AWS EventBridge
    """

    def __init__(
        self,
        audit_writer: Optional[AuditTrailWriter] = None,
        worm_manager: Optional[WORMManager] = None,
    ):
        self.audit = audit_writer or AuditTrailWriter()
        self.worm  = worm_manager or WORMManager(audit_writer=self.audit)

    def scan_invoices(self, db_query_fn=None) -> Dict[str, Any]:
        """
        Scannt Rechnungen und archiviert/WORM-locked fällige Dokumente.

        Args:
            db_query_fn: Callable() → List[dict mit keys: id, issue_date, is_worm_locked]
                         Wenn None: gibt Scan-Report ohne DB-Zugriff zurück.

        Returns:
            Scan-Report Dict
        """
        now = datetime.now(timezone.utc).isoformat()
        report = {
            "scan_time": now,
            "to_lock": [],
            "overdue_for_deletion": [],
            "errors": [],
        }

        invoices = db_query_fn() if db_query_fn else []
        for inv in invoices:
            inv_date = inv["issue_date"]
            if isinstance(inv_date, str):
                inv_date = date.fromisoformat(inv_date)
            try:
                if not inv.get("is_worm_locked") and RetentionPolicy.must_be_retained(
                    inv_date, DocumentType.INVOICE
                ):
                    report["to_lock"].append(inv["id"])
                elif RetentionPolicy.is_overdue_for_deletion(inv_date, DocumentType.INVOICE):
                    report["overdue_for_deletion"].append(inv["id"])
            except Exception as exc:
                report["errors"].append({"id": inv.get("id"), "error": str(exc)})

        self.audit.record(AuditEvent(
            object_type="retention_scan",
            object_id=str(uuid.uuid4()),
            action=AuditAction.RETENTION_SCAN,
            actor_service="gobd_retention.RetentionScanner",
            extra=report,
        ))
        logger.info(
            "RetentionScan: to_lock=%d overdue=%d errors=%d",
            len(report["to_lock"]),
            len(report["overdue_for_deletion"]),
            len(report["errors"]),
        )
        return report


# ─────────────────────────────────────────────
# Convenience factory
# ─────────────────────────────────────────────
def create_gobd_stack(db_conn=None) -> Dict[str, Any]:
    """
    Erstellt den vollständigen GoBD-Stack für SYLION.

    Returns dict mit:
        worm_manager, audit_writer, hash_chain,
        retention_policy, retention_scanner
    """
    audit   = AuditTrailWriter(db_conn=db_conn)
    chain   = HashChain()
    worm    = WORMManager(audit_writer=audit, hash_chain=chain)
    scanner = RetentionScanner(audit_writer=audit, worm_manager=worm)

    return {
        "audit_writer":      audit,
        "hash_chain":        chain,
        "worm_manager":      worm,
        "retention_policy":  RetentionPolicy,
        "retention_scanner": scanner,
        "s3_config":  S3WORMConfig(bucket_name="sylion-accounting-archive"),
        "gcs_config": GCSWORMConfig(
            bucket_name="sylion-accounting-archive",
            project_id="sylion-prod",
        ),
    }
