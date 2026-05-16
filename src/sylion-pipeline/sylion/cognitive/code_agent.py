"""
SYLION Cognitive -- Code Agent

Code generation and analysis via LLM. Supports generate, review,
analyze, and fix operations, recording all code operations for audit.

Thread-safe. SQLite-backed. Emits events on code operations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.cognitive.code_agent")


def _allow_stub() -> bool:
    return os.environ.get("SYLION_ALLOW_LLM_STUB") == "1"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CodeOperation:
    """A single code operation record."""
    op_id: str = ""
    operation: str = ""
    input_hash: str = ""
    output_hash: str = ""
    model_id: str = ""
    result: str = ""
    metadata: str = "{}"
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.op_id:
            self.op_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Code Agent
# ---------------------------------------------------------------------------

class CodeAgent:
    """Code generation and analysis via LLM.

    Thread-safe. SQLite-backed. Emits events on code operations.
    Uses llm_adapter.call internally if available.
    """

    def __init__(self, llm_adapter: Any = None,
                 event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._llm_adapter = llm_adapter
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS code_operations (
                op_id       TEXT PRIMARY KEY,
                operation   TEXT NOT NULL DEFAULT '',
                input_hash  TEXT NOT NULL DEFAULT '',
                output_hash TEXT NOT NULL DEFAULT '',
                model_id    TEXT NOT NULL DEFAULT '',
                result      TEXT NOT NULL DEFAULT '',
                metadata    TEXT NOT NULL DEFAULT '{}',
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_code_op ON code_operations(operation)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_code_ts ON code_operations(timestamp)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm_response(self, prompt: str, model_id: str = "") -> dict[str, Any]:
        """Call LLM adapter and return full metadata; deterministic stubs require opt-in."""
        if self._llm_adapter:
            try:
                response = self._llm_adapter.call(model_id, prompt)
                status = response.get("status")
                if response.get("blocked") or status == "blocked":
                    reason = (
                        response.get("policy", {}).get("reason")
                        or "CodeAgent LLM call blocked by model runtime policy"
                    )
                    raise PermissionError(reason)
                if status in {"stub", "fallback"} and not _allow_stub():
                    raise RuntimeError(f"LLM adapter returned disabled status={status}")
                return response
            except PermissionError:
                raise
            except Exception:
                if not _allow_stub():
                    raise
                log.exception("LLM call failed, using deterministic test stub")
        if not _allow_stub():
            raise RuntimeError("CodeAgent cannot run without a real LLM adapter")
        return {"text": "stub", "status": "stub", "model_id": "stub", "provider_model": "stub"}

    def _call_llm(self, prompt: str, model_id: str = "") -> str:
        """Call LLM adapter if available; deterministic stubs require opt-in."""
        return str(self._call_llm_response(prompt, model_id).get("text", ""))

    def _looks_like_placeholder(self, text: str) -> bool:
        """Detect generic chat output that should not pass as an AEIS product artifact."""
        lowered = text.lower()
        bad_markers = (
            "hello, world",
            "certainly!",
            "sure!",
            "below is",
            "oto przykład",
            "this is a very simple example",
            "rozważanie software idea",
            "bez_data.csv",
            "import pandas as pd",
            "data = pd.read_csv",
            "replace with your own values",
            "your_resource",
            "your-token",
            "alibaba cloud",
            "platformy slack",
            "platforma slack",
            "automatest.io",
            "przepraszam",
            "nie jestem w stanie",
            "nie mam dostępu do kontekstu",
            "nie jestem w stanie wygenerować",
            "nie jestem w stanie dostarczyć",
            "testy akceptacyjne nie",
            "nie jest wymagany test",
            "not required",
            "sample data",
        )
        return any(marker in lowered for marker in bad_markers) or self._has_blocked_example_host(lowered)

    def _normalize_for_quality(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text or "")
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return ascii_text.lower()

    def _domain_terms(self, prompt: str) -> set[str]:
        normalized = self._normalize_for_quality(prompt)
        stopwords = {
            "oraz", "przez", "ktory", "ktora", "ktore", "jako", "musi",
            "wynik", "wymagane", "zakazane", "pipeline", "kroku", "stworz",
            "naprawie", "rozszerzeniu", "guardow", "aplikacje", "lokalna",
            "local", "without", "polsku", "testy", "akceptacyjne", "hello",
            "world", "format", "jezyk",
        }
        words = set(re.findall(r"[a-z0-9_]{4,}", normalized))
        return {word for word in words if word not in stopwords}

    def _has_any_quality_marker(self, text: str, markers: tuple[str, ...]) -> bool:
        return any(marker in text for marker in markers)

    def _has_blocked_example_host(self, lowered: str) -> bool:
        """Block example.com as an endpoint, but allow reserved email fixtures."""
        without_fixture_emails = re.sub(
            r"\b[a-z0-9._%+-]+@example\.com\b",
            "",
            lowered,
        )
        return "example.com" in without_fixture_emails

    def _has_irrelevant_external_url(self, prompt_norm: str, lowered: str) -> bool:
        urls = re.findall(r"https?://[^\s)\]>'\"]+", lowered)
        if not urls:
            return False

        local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
        external_hosts = set()
        for url in urls:
            host = (urlparse(url).hostname or "").lower()
            if host and host not in local_hosts:
                external_hosts.add(host)

        if not external_hosts:
            return False

        return not any(token in prompt_norm for token in ("url", "www", "http", "api", "integracja"))

    def _artifact_contract_is_too_thin(self, prompt: str, text: str) -> bool:
        """Detect missing product substance without requiring one rigid template."""
        lowered = self._normalize_for_quality(text)
        prompt_norm = self._normalize_for_quality(prompt)
        product_markers = (
            "nazwa artefaktu", "artefakt", "produkt", "opis produktu",
            "opis projektu", "cel produktu", "funkcjonalnosci",
        )
        domain_markers = (
            "zalozenia", "domena", "uzytkownicy", "role", "profil",
            "model danych", "dane", "ekrany", "api", "przeplyw",
        )
        implementation_markers = (
            "kod", "specyfik", "class ", "def ", "endpoint", "post ",
            "get ", "schema", "model", "baza", "artifact", "plik",
        )
        test_markers = (
            "testy akceptacyjne", "test ", "dane wejsciowe",
            "oczekiwany wynik", "kryterium", "assert", "unittest",
            "zaliczenia",
        )
        risk_gate_markers = (
            "ryzyka", "ryzyko", "human gate", "guard", "bramka",
            "walidacja", "audit", "rollback", "release",
        )

        if "raport jakosci" in prompt_norm or "gotowosc produktu" in prompt_norm:
            if len(lowered.strip()) < 220:
                return True
            report_markers = (
                "ocena", "gotowosc", "braki", "ryzyka", "human gate",
                "guard", "test", "artefakt", "zaliczony", "popraw",
            )
            report_score = sum(1 for marker in report_markers if marker in lowered)
            return report_score < 5

        if len(lowered.strip()) < 900:
            return True

        score = sum(
            1
            for markers in (
                product_markers,
                domain_markers,
                implementation_markers,
                test_markers,
                risk_gate_markers,
            )
            if self._has_any_quality_marker(lowered, markers)
        )

        if "testy akceptacyjne" in prompt_norm:
            return not (
                self._has_any_quality_marker(lowered, test_markers)
                and self._has_any_quality_marker(lowered, domain_markers)
                and (
                    self._has_any_quality_marker(lowered, risk_gate_markers)
                    or self._has_any_quality_marker(lowered, implementation_markers)
                )
            )

        if "artefakt implementacyjny" in prompt_norm:
            return not (
                self._has_any_quality_marker(lowered, implementation_markers)
                and self._has_any_quality_marker(lowered, domain_markers)
                and self._has_any_quality_marker(lowered, test_markers)
            )

        return score < 4

    def _quality_findings(self, prompt: str, text: str) -> list[str]:
        """Return product-quality findings for generated pipeline artifacts."""
        lowered = self._normalize_for_quality(text)
        prompt_norm = self._normalize_for_quality(prompt)
        bad_markers = (
            "hello, world",
            "certainly!",
            "sure!",
            "below is",
            "oto przyklad",
            "przyklad produktowego",
            "this is a very simple example",
            "rozwazanie software idea",
            "bez_data.csv",
            "import pandas as pd",
            "data = pd.read_csv",
            "replace with your own values",
            "your_resource",
            "your-token",
            "alibaba cloud",
            "platformy slack",
            "platforma slack",
            "automatest.io",
            "przepraszam",
            "nie jestem w stanie",
            "nie mam dostepu do kontekstu",
            "nie jestem w stanie wygenerowac",
            "nie jestem w stanie dostarczyc",
            "nie mam dostepu",
            "nie moge",
            "testy akceptacyjne nie",
            "nie jest wymagany test",
            "not required",
            "sample data",
        )
        findings = [f"bad_marker:{marker}" for marker in bad_markers if marker in lowered]
        if self._has_blocked_example_host(lowered):
            findings.append("bad_marker:example.com")

        if self._artifact_contract_is_too_thin(prompt, text):
            findings.append("artifact_contract_too_thin")

        domain_terms = self._domain_terms(prompt)
        if domain_terms:
            domain_hits = {term for term in domain_terms if term in lowered}
            if len(domain_hits) < min(3, max(1, len(domain_terms) // 4)):
                findings.append("domain_terms_missing")

        if ("read_csv" in lowered or "pandas" in lowered) and "csv" not in prompt_norm:
            findings.append("irrelevant_dataframe_artifact")

        if self._has_irrelevant_external_url(prompt_norm, lowered):
            findings.append("irrelevant_external_url")

        return findings

    def _record_operation(self, operation: str, input_hash: str,
                          output_hash: str, model_id: str,
                          result: str, metadata: dict | None = None) -> dict:
        """Record a code operation and return its summary."""
        if metadata is None:
            metadata = {}

        op = CodeOperation(
            operation=operation,
            input_hash=input_hash,
            output_hash=output_hash,
            model_id=model_id,
            result=result,
            metadata=json.dumps(metadata, default=str),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO code_operations
                (op_id, operation, input_hash, output_hash,
                 model_id, result, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                op.op_id, op.operation, op.input_hash, op.output_hash,
                op.model_id, op.result, op.metadata, op.timestamp,
            ))
            self._conn.commit()

        self._emit("code.operation", {
            "op_id": op.op_id,
            "operation": operation,
            "input_hash": input_hash[:12],
            "model_id": model_id,
        })
        return {
            "op_id": op.op_id,
            "operation": operation,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "model_id": model_id,
            "result": result,
            "metadata": metadata,
            "timestamp": op.timestamp,
        }

    # ------------------------------------------------------------------
    # Code operations
    # ------------------------------------------------------------------

    def generate(self, prompt: str, language: str = "python") -> dict:
        """Generate code from a prompt. Returns operation dict."""
        input_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        llm_prompt = (
            "Jesteś wykonawczym agentem AEIS. Odpowiadasz po polsku, konkretnie i bez tekstu typu "
            "'Sure', 'Certainly', 'Hello World' albo przypadkowych integracji chmurowych.\n"
            "Wygeneruj produktowy artefakt dla kroku pipeline, nie przykład edukacyjny.\n"
            "Wynik ma zawierać:\n"
            "1. nazwa artefaktu,\n"
            "2. kompletne założenia domenowe,\n"
            "3. kod lub specyfikację pasującą dokładnie do opisu,\n"
            "4. testy akceptacyjne,\n"
            "5. ryzyka i bramki Human Gate/Guard, jeśli dotyczą.\n"
            f"Język/format kodu: {language}.\n"
            f"Opis kroku: {prompt}\n"
        )
        response = self._call_llm_response(llm_prompt)
        llm_result = str(response.get("text", ""))
        repaired = False
        repair_model = ""
        findings = self._quality_findings(prompt, llm_result)
        if findings:
            repair_model = os.environ.get("SYLION_QUALITY_REPAIR_MODEL", "gpt-4o-mini").strip()
            repair_prompt = (
                "Poprzedni wynik został odrzucony przez guard jakości AEIS jako placeholder/generic output. "
                "Napisz wynik od nowa po polsku, bez wstępów czatowych, bez Hello World, bez losowych AWS/Azure, "
                "z artefaktem dopasowanym do domeny i testami akceptacyjnymi.\n"
                f"Opis kroku: {prompt}\n"
            )
            response = self._call_llm_response(repair_prompt, repair_model)
            llm_result = str(response.get("text", ""))
            repaired = True
            findings = self._quality_findings(prompt, llm_result)
        output_hash = hashlib.sha256(llm_result.encode("utf-8")).hexdigest()
        model_id = (
            str(response.get("model_id") or "")
            or str(response.get("provider_model") or "")
            or getattr(self._llm_adapter, "_default_model", "")
        )

        log.info("generated code for prompt (hash=%s...)", input_hash[:12])
        return self._record_operation(
            operation="generate",
            input_hash=input_hash,
            output_hash=output_hash,
            model_id=model_id,
            result=llm_result,
            metadata={
                "language": language,
                "prompt_length": len(prompt),
                "quality_repair_attempted": repaired,
                "quality_repair_model": repair_model,
                "quality_guard_failed": bool(findings),
                "quality_findings": findings,
            },
        )

    def review(self, code: str, criteria: list | None = None) -> dict:
        """Review code against criteria. Returns operation dict."""
        if criteria is None:
            criteria = []

        input_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        criteria_str = ", ".join(criteria) if criteria else "general quality"
        llm_prompt = f"Review the following code for {criteria_str}:\n{code}"
        llm_result = self._call_llm(llm_prompt)
        output_hash = hashlib.sha256(llm_result.encode("utf-8")).hexdigest()

        log.info("reviewed code (hash=%s..., criteria=%d)",
                 input_hash[:12], len(criteria))
        return self._record_operation(
            operation="review",
            input_hash=input_hash,
            output_hash=output_hash,
            model_id="",
            result=llm_result,
            metadata={"criteria": criteria, "code_length": len(code)},
        )

    def analyze(self, code: str) -> dict:
        """Analyze code structure and quality. Returns operation dict."""
        input_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        llm_prompt = f"Analyze the following code:\n{code}"
        llm_result = self._call_llm(llm_prompt)
        output_hash = hashlib.sha256(llm_result.encode("utf-8")).hexdigest()

        log.info("analyzed code (hash=%s...)", input_hash[:12])
        return self._record_operation(
            operation="analyze",
            input_hash=input_hash,
            output_hash=output_hash,
            model_id="",
            result=llm_result,
            metadata={"code_length": len(code)},
        )

    def fix(self, code: str, issue: str) -> dict:
        """Fix code based on an issue description. Returns operation dict."""
        input_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        llm_prompt = f"Fix the following issue in the code.\nIssue: {issue}\nCode:\n{code}"
        llm_result = self._call_llm(llm_prompt)
        output_hash = hashlib.sha256(llm_result.encode("utf-8")).hexdigest()

        log.info("fixed code (hash=%s..., issue='%s')",
                 input_hash[:12], issue[:40])
        return self._record_operation(
            operation="fix",
            input_hash=input_hash,
            output_hash=output_hash,
            model_id="",
            result=llm_result,
            metadata={"issue": issue, "code_length": len(code)},
        )

    def list_operations(self, operation: str | None = None,
                        limit: int = 100) -> list[dict]:
        """List code operations, optionally filtered by operation type."""
        if operation:
            rows = self._conn.execute(
                "SELECT * FROM code_operations WHERE operation = ? ORDER BY timestamp DESC LIMIT ?",
                (operation, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM code_operations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.code_agent",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_agent: CodeAgent | None = None


def get_code_agent(llm_adapter: Any = None,
                   event_bus: EventBus | None = None,
                   db_path: str | Path | None = None) -> CodeAgent:
    global _agent
    if _agent is None:
        _agent = CodeAgent(llm_adapter, event_bus, db_path)
    return _agent
