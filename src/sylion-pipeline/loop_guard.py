#!/usr/bin/env python3
"""
SYLION Loop Guard — Anti-Loop Detection + Context Persistence + Iteration Tracker

Trzy komponenty chroniące przed nieskończonymi pętlami korekcji między agentami:

  1. LoopGuard       — wykrywanie pętli, limity twardej iteracji, eskalacja
  2. ContextPersistence — zapis podsumowań łatek i etapów, okno kontekstu
  3. IterationTracker  — śledzenie pełnego stanu pętli korekcji

Architektura:
  Agent łata plik → Audytor wykrywa błąd → Agent łata ponownie → PĘTLA
  LoopGuard wykrywa schemat → Zatrzymuje agenta → Eskaluje do Human Gate
"""

from __future__ import annotations

import difflib
import enum
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("loop_guard")

# ---------------------------------------------------------------------------
# ANSI colors — identyczne z supervisor.py
# ---------------------------------------------------------------------------
class C:
    RESET     = "\033[0m"
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    RED       = "\033[91m"
    GREEN     = "\033[92m"
    YELLOW    = "\033[93m"
    BLUE      = "\033[94m"
    MAGENTA   = "\033[95m"
    CYAN      = "\033[96m"
    WHITE     = "\033[97m"
    BG_RED    = "\033[41m"
    BG_GREEN  = "\033[42m"
    BG_YELLOW = "\033[43m"


# ---------------------------------------------------------------------------
# Enumeracje statusów
# ---------------------------------------------------------------------------

class LoopStatus(str, enum.Enum):
    """Status pętli korekcji zwracany przez check_loop()."""
    OK            = "ok"             # Wszystko w porządku
    WARNING       = "warning"        # Zbliżamy się do limitu
    LOOP_DETECTED = "loop_detected"  # Wykryto pętlę semantyczną/oscylacyjną
    HARD_LIMIT    = "hard_limit"     # Przekroczono twardy limit iteracji


class EscalationChoice(str, enum.Enum):
    """Opcje eskalacji do człowieka po wykryciu pętli."""
    FORCE_CONTINUE    = "force_continue"    # a) Wymuszenie kontynuacji (override limitu)
    SKIP              = "skip"              # b) Pominięcie pliku/znaleziska
    MANUAL_INTERVENE  = "manual_intervene"  # c) Ręczna interwencja człowieka
    ASSIGN_NEW_MODEL  = "assign_new_model"  # d) Przydzielenie innemu modelowi


class EventType(str, enum.Enum):
    """Typy zdarzeń w osi czasu."""
    PATCH_APPLIED    = "patch_applied"
    AUDIT_FINDING    = "audit_finding"
    LOOP_DETECTED    = "loop_detected"
    ESCALATED        = "escalated"
    HUMAN_DECISION   = "human_decision"
    STAGE_COMPLETE   = "stage_complete"
    AGENT_RESET      = "agent_reset"
    CONTEXT_SNAPSHOT = "context_snapshot"
    ITERATION_START  = "iteration_start"
    ITERATION_END    = "iteration_end"


# ---------------------------------------------------------------------------
# Dataclassy — struktury danych
# ---------------------------------------------------------------------------

@dataclass
class IterationRecord:
    """Rekord pojedynczej iteracji agenta dla danego pliku."""
    iteration_number: int
    agent_id: str
    file_path: str
    action: str                          # np. "patch", "audit", "review", "hallucination"
    finding_id: str | None
    patch_diff: str | None               # Ujednolicony diff łatki
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cost_usd: float = 0.0
    duration_sec: float = 0.0
    # --- File Verification metadata ---
    hallucination_detected: bool = False         # True if verification found hallucination
    hallucination_type: str | None = None        # HallucinationType value if detected
    verification_verdict: str | None = None      # Verdict from file verification
    sha_before: str | None = None                # SHA-256 before agent ran
    sha_after: str | None = None                 # SHA-256 after agent ran

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration_number": self.iteration_number,
            "agent_id": self.agent_id,
            "file_path": self.file_path,
            "action": self.action,
            "finding_id": self.finding_id,
            "patch_diff": self.patch_diff,
            "timestamp": self.timestamp.isoformat(),
            "cost_usd": self.cost_usd,
            "duration_sec": self.duration_sec,
            # File verification metadata
            "hallucination_detected": self.hallucination_detected,
            "hallucination_type": self.hallucination_type,
            "verification_verdict": self.verification_verdict,
            "sha_before": self.sha_before,
            "sha_after": self.sha_after,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IterationRecord":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        # Handle records created before file verification was added
        d.setdefault("hallucination_detected", False)
        d.setdefault("hallucination_type", None)
        d.setdefault("verification_verdict", None)
        d.setdefault("sha_before", None)
        d.setdefault("sha_after", None)
        return cls(**d)


@dataclass
class LoopReport:
    """Szczegółowy raport wykrytej pętli korekcji."""
    agent_id: str
    file_path: str
    status: LoopStatus
    loop_score: float                    # 0.0–1.0
    iteration_count: int
    oscillation_detected: bool
    semantic_loop_detected: bool
    repeated_findings: list[str]
    patch_overlap_ratio: float
    iterations: list[IterationRecord]
    recommendation: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    escalation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "file_path": self.file_path,
            "status": self.status.value,
            "loop_score": self.loop_score,
            "iteration_count": self.iteration_count,
            "oscillation_detected": self.oscillation_detected,
            "semantic_loop_detected": self.semantic_loop_detected,
            "repeated_findings": self.repeated_findings,
            "patch_overlap_ratio": self.patch_overlap_ratio,
            "iterations": [it.to_dict() for it in self.iterations],
            "recommendation": self.recommendation,
            "timestamp": self.timestamp.isoformat(),
            "escalation_id": self.escalation_id,
        }


@dataclass
class PatchSummary:
    """Podsumowanie zastosowanej łatki — zapisywane po każdej udanej poprawce."""
    file_path: str
    diff_preview: str                    # Pierwsze 400 znaków diffa
    findings_addressed: list[str]        # Lista ID znalezisk, które łatka rozwiązuje
    model_used: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    iteration_number: int = 0
    agent_id: str = ""
    patch_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "file_path": self.file_path,
            "diff_preview": self.diff_preview,
            "findings_addressed": self.findings_addressed,
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
            "iteration_number": self.iteration_number,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PatchSummary":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


@dataclass
class StageSummary:
    """Podsumowanie zakończonego etapu audytu."""
    stage_name: str
    agents_involved: list[str]
    findings_found: int
    findings_resolved: int
    findings_remaining: int
    duration_sec: float
    cost_usd: float
    human_decisions: list[str]           # Lista decyzji człowieka w tym etapie
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stage_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "agents_involved": self.agents_involved,
            "findings_found": self.findings_found,
            "findings_resolved": self.findings_resolved,
            "findings_remaining": self.findings_remaining,
            "duration_sec": self.duration_sec,
            "cost_usd": self.cost_usd,
            "human_decisions": self.human_decisions,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StageSummary":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


@dataclass
class TimelineEntry:
    """Pojedynczy wpis w osi czasu — wszystko co się zdarzyło."""
    event_type: EventType
    agent_id: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "description": self.description,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TimelineEntry":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        d["event_type"] = EventType(d["event_type"])
        return cls(**d)


@dataclass
class ContextWindow:
    """Okno kontekstu — ostatnie N operacji do wstrzyknięcia w prompt agenta."""
    entries: list[TimelineEntry] = field(default_factory=list)
    max_entries: int = 20

    def add(self, entry: TimelineEntry) -> None:
        """Dodaje wpis, usuwając najstarszy jeśli przekroczono max_entries."""
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def format(self) -> str:
        """Zwraca sformatowany kontekst gotowy do wstrzyknięcia w prompt."""
        if not self.entries:
            return "Brak historii operacji w oknie kontekstu."
        lines = ["=== KONTEKST OSTATNICH OPERACJI ==="]
        for entry in self.entries:
            ts = entry.timestamp.strftime("%H:%M:%S")
            lines.append(f"[{ts}] [{entry.event_type.value.upper()}] agent={entry.agent_id}: {entry.description}")
        lines.append("=== KONIEC KONTEKSTU ===")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Wpis iteracji dla IterationTracker
# ---------------------------------------------------------------------------

@dataclass
class IterationState:
    """Stan jednej iteracji pętli korekcji dla danego pliku."""
    iteration_number: int
    patch_applied: str | None            # Diff zastosowanej łatki
    audit_result: str | None             # Wynik audytu (opis)
    findings_new: list[str]              # Nowe znaleziska w tej iteracji
    findings_resolved: list[str]         # Znaleziska rozwiązane w tej iteracji
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str = ""
    model_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration_number": self.iteration_number,
            "patch_applied": self.patch_applied,
            "audit_result": self.audit_result,
            "findings_new": self.findings_new,
            "findings_resolved": self.findings_resolved,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "model_used": self.model_used,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IterationState":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


# ═══════════════════════════════════════════════════════════════════════════
# CZĘŚĆ 1: LoopGuard — wykrywanie i zapobieganie nieskończonym pętlom
# ═══════════════════════════════════════════════════════════════════════════

class LoopGuard:
    """Wykrywa i zapobiega nieskończonym pętlom korekcji między agentami.

    Monitoruje wzorce takie jak:
    - Agent A łata plik X → Audytor wykrywa nowy błąd w X → Agent A łata X ponownie
    - To samo znalezisko raportowane 3+ razy w kolejnych iteracjach
    - Agent produkuje identyczne lub bardzo podobne wyjście
    - Przekroczenie budżetu kosztów/czasu
    """

    # Progi punktacji pętli (0.0–1.0)
    WARNING_THRESHOLD: float = 0.45
    LOOP_THRESHOLD:    float = 0.70

    # Próg podobieństwa znalezisk (SequenceMatcher ratio)
    FINDING_SIMILARITY_THRESHOLD: float = 0.75

    def __init__(
        self,
        max_iterations: int = 5,
        max_cost_usd_per_agent: float = 5.0,
        max_cost_usd_per_file: float = 2.0,
        max_time_sec_per_file: float = 300.0,
        results_dir: Path | None = None,
    ) -> None:
        self.max_iterations            = max_iterations
        self.max_cost_usd_per_agent    = max_cost_usd_per_agent
        self.max_cost_usd_per_file     = max_cost_usd_per_file
        self.max_time_sec_per_file     = max_time_sec_per_file
        self.results_dir               = results_dir or Path("results")

        # Słownik: (agent_id, file_path) → lista IterationRecord
        self._records: dict[tuple[str, str], list[IterationRecord]] = {}

        # Słownik: agent_id → statystyki agenta
        self._agent_stats: dict[str, dict[str, Any]] = {}

        # Wykryte pętle — (agent_id, file_path) → LoopReport
        self._loop_reports: dict[tuple[str, str], LoopReport] = {}

        # Nadpisane limity (po decyzji człowieka force_continue)
        self._overridden: set[tuple[str, str]] = set()

        logger.info("LoopGuard zainicjalizowany — maks. %d iteracji na agenta/plik", max_iterations)

    # ------------------------------------------------------------------
    # Rejestrowanie iteracji
    # ------------------------------------------------------------------

    def record_iteration(
        self,
        agent_id: str,
        file_path: str,
        action: str,
        finding_id: str | None = None,
        patch_diff: str | None = None,
        cost_usd: float = 0.0,
        duration_sec: float = 0.0,
    ) -> LoopStatus:
        """Rejestruje co się stało w tej iteracji i zwraca aktualny status pętli.

        Args:
            agent_id:     Identyfikator agenta (np. "programmer_go_1")
            file_path:    Ścieżka pliku który był modyfikowany/audytowany
            action:       Typ akcji: "patch" | "audit" | "review" | ...
            finding_id:   ID znaleziska z audytu (jeśli dotyczy)
            patch_diff:   Ujednolicony diff łatki (jeśli action == "patch")
            cost_usd:     Koszt tej operacji w USD
            duration_sec: Czas trwania tej operacji w sekundach

        Returns:
            Aktualny LoopStatus dla tej pary (agent_id, file_path)
        """
        key = (agent_id, file_path)
        if key not in self._records:
            self._records[key] = []

        iteration_number = len(self._records[key]) + 1
        record = IterationRecord(
            iteration_number=iteration_number,
            agent_id=agent_id,
            file_path=file_path,
            action=action,
            finding_id=finding_id,
            patch_diff=patch_diff,
            cost_usd=cost_usd,
            duration_sec=duration_sec,
        )
        self._records[key].append(record)

        # Aktualizuj statystyki agenta
        self._update_agent_stats(agent_id, file_path, cost_usd, duration_sec)

        status = self.check_loop(agent_id, file_path)
        logger.debug(
            "Iteracja %d zapisana — agent=%s plik=%s akcja=%s status=%s",
            iteration_number, agent_id, file_path, action, status.value,
        )
        return status

    # ------------------------------------------------------------------
    # Sprawdzanie statusu pętli
    # ------------------------------------------------------------------

    def check_loop(self, agent_id: str, file_path: str) -> LoopStatus:
        """Sprawdza status pętli dla danej pary (agent_id, file_path).

        Returns:
            OK / WARNING / LOOP_DETECTED / HARD_LIMIT
        """
        key = (agent_id, file_path)

        # Twardy override po decyzji człowieka
        if key in self._overridden:
            return LoopStatus.OK

        records = self._records.get(key, [])
        if not records:
            return LoopStatus.OK

        count = len(records)

        # Twardy limit iteracji
        if count >= self.max_iterations:
            logger.warning(
                "TWARDY LIMIT — agent=%s plik=%s iteracje=%d/%d",
                agent_id, file_path, count, self.max_iterations,
            )
            return LoopStatus.HARD_LIMIT

        # Oblicz wynik pętli
        score = self._calculate_loop_score(agent_id, file_path)

        if score >= self.LOOP_THRESHOLD:
            logger.warning(
                "PĘTLA WYKRYTA — agent=%s plik=%s wynik=%.2f iteracje=%d",
                agent_id, file_path, score, count,
            )
            return LoopStatus.LOOP_DETECTED

        if score >= self.WARNING_THRESHOLD:
            logger.info(
                "OSTRZEŻENIE pętli — agent=%s plik=%s wynik=%.2f iteracje=%d",
                agent_id, file_path, score, count,
            )
            return LoopStatus.WARNING

        return LoopStatus.OK

    # ------------------------------------------------------------------
    # Obliczanie wyniku pętli
    # ------------------------------------------------------------------

    def _calculate_loop_score(self, agent_id: str, file_path: str) -> float:
        """Oblicza wynik pętli (0.0–1.0) na podstawie trzech sygnałów.

        Składniki:
          - iteration_score:  proporcja zużytych iteracji (waga 0.35)
          - finding_score:    podobieństwo powtarzających się znalezisk (waga 0.40)
          - patch_score:      nakładanie się łatek (oscylacja) (waga 0.25)
        """
        key = (agent_id, file_path)
        records = self._records.get(key, [])
        if not records:
            return 0.0

        count = len(records)

        # Składnik 1: Iteracje (0.35)
        iteration_score = min(count / self.max_iterations, 1.0)

        # Składnik 2: Podobieństwo znalezisk (0.40)
        finding_score = self._calculate_finding_similarity_score(records)

        # Składnik 3: Nakładanie się łatek (0.25)
        patch_score = self._calculate_patch_overlap_score(records)

        total = (
            0.35 * iteration_score +
            0.40 * finding_score +
            0.25 * patch_score
        )
        return min(total, 1.0)

    def _calculate_finding_similarity_score(self, records: list[IterationRecord]) -> float:
        """Wykrywa czy te same znaleziska powtarzają się (pętla semantyczna)."""
        finding_ids = [r.finding_id for r in records if r.finding_id is not None]
        if len(finding_ids) < 2:
            return 0.0

        # Sprawdź dokładne duplikaty
        from collections import Counter
        counts = Counter(finding_ids)
        max_repeat = max(counts.values())
        if max_repeat >= 3:
            return 1.0
        if max_repeat == 2:
            # Wzmocnij jeśli wiele znalezisk się powtarza
            repeated_count = sum(1 for v in counts.values() if v >= 2)
            return min(0.6 + 0.1 * repeated_count, 1.0)

        # Sprawdź rozmyte podobieństwo dla znalezisk bez dokładnych duplikatów
        # Używamy finding_id jako tekstu — może zawierać opis
        max_similarity = 0.0
        for i in range(len(finding_ids)):
            for j in range(i + 1, len(finding_ids)):
                ratio = difflib.SequenceMatcher(
                    None, finding_ids[i], finding_ids[j]
                ).ratio()
                if ratio > max_similarity:
                    max_similarity = ratio

        if max_similarity >= self.FINDING_SIMILARITY_THRESHOLD:
            return max_similarity * 0.8
        return 0.0

    def _calculate_patch_overlap_score(self, records: list[IterationRecord]) -> float:
        """Wykrywa oscylacyjne łatki — zmienianie tych samych linii tam i z powrotem."""
        patches = [r.patch_diff for r in records if r.patch_diff is not None]
        if len(patches) < 2:
            return 0.0

        # Porównaj ostatnią łatkę z poprzednimi
        last_patch = patches[-1]
        max_overlap = 0.0
        for earlier_patch in patches[:-1]:
            ratio = difflib.SequenceMatcher(None, earlier_patch, last_patch).ratio()
            if ratio > max_overlap:
                max_overlap = ratio

        # Oscylacja: wysoka podobność do starszej łatki = cofanie zmian
        if max_overlap >= 0.85:
            return 1.0
        if max_overlap >= 0.60:
            return max_overlap
        return max_overlap * 0.5

    # ------------------------------------------------------------------
    # Generowanie raportu pętli
    # ------------------------------------------------------------------

    def get_loop_report(self, agent_id: str, file_path: str) -> LoopReport:
        """Zwraca szczegółowy raport analizy pętli dla danej pary agent/plik."""
        key = (agent_id, file_path)
        records = self._records.get(key, [])
        status = self.check_loop(agent_id, file_path)
        score = self._calculate_loop_score(agent_id, file_path)

        # Wykryj oscylację
        patches = [r.patch_diff for r in records if r.patch_diff is not None]
        oscillation = False
        patch_overlap = 0.0
        if len(patches) >= 2:
            patch_overlap = self._calculate_patch_overlap_score(records)
            oscillation = patch_overlap >= 0.85

        # Wykryj pętlę semantyczną i powtarzające się znaleziska
        from collections import Counter
        finding_ids = [r.finding_id for r in records if r.finding_id is not None]
        counts = Counter(finding_ids)
        repeated = [fid for fid, cnt in counts.items() if cnt >= 2]
        semantic_loop = len(repeated) > 0 or score >= self.LOOP_THRESHOLD

        # Generuj rekomendację
        if status == LoopStatus.HARD_LIMIT:
            recommendation = (
                "Przekroczono twardy limit iteracji. Wymagana interwencja człowieka. "
                "Sugerowane opcje: (c) interwencja manualna lub (d) zmiana modelu."
            )
        elif oscillation:
            recommendation = (
                "Wykryto oscylacyjne łatki — agent cofa własne zmiany. "
                "Sugerowane: (d) przydziel innemu modelowi lub (c) interwencja manualna."
            )
        elif semantic_loop:
            recommendation = (
                f"Znaleziska powtarzają się: {repeated}. "
                "Agent tkwi w pętli semantycznej. Sugerowane: (b) pomiń znalezisko lub (d) nowy model."
            )
        else:
            recommendation = (
                "Zbliżamy się do limitu iteracji. Monitoruj dalej lub rozważ "
                "(a) wymuszenie kontynuacji z wyższym limitem."
            )

        report = LoopReport(
            agent_id=agent_id,
            file_path=file_path,
            status=status,
            loop_score=score,
            iteration_count=len(records),
            oscillation_detected=oscillation,
            semantic_loop_detected=semantic_loop,
            repeated_findings=repeated,
            patch_overlap_ratio=patch_overlap,
            iterations=list(records),
            recommendation=recommendation,
        )
        self._loop_reports[key] = report
        return report

    # ------------------------------------------------------------------
    # Eskalacja do człowieka
    # ------------------------------------------------------------------

    def escalate_to_human(
        self,
        agent_id: str,
        file_path: str,
    ) -> EscalationChoice:
        """Prezentuje człowiekowi opcje eskalacji po wykryciu pętli.

        Opcje:
          a) Wymuszenie kontynuacji (override limitu)
          b) Pominięcie tego pliku/znaleziska
          c) Ręczna interwencja (człowiek sam naprawi)
          d) Przydziel innemu modelowi (świeża perspektywa)

        Returns:
            Wybór człowieka jako EscalationChoice
        """
        report = self.get_loop_report(agent_id, file_path)
        self._print_escalation_prompt(report)

        choice = self._read_human_choice()
        logger.info(
            "Decyzja człowieka dla agent=%s plik=%s: %s",
            agent_id, file_path, choice.value,
        )

        # Zastosuj decyzję
        if choice == EscalationChoice.FORCE_CONTINUE:
            self._overridden.add((agent_id, file_path))
            print(f"\n{C.YELLOW}⚠  Override zastosowany — agent może kontynuować.{C.RESET}\n")

        elif choice == EscalationChoice.SKIP:
            print(f"\n{C.BLUE}⊘  Plik/znalezisko pominięte.{C.RESET}\n")

        elif choice == EscalationChoice.MANUAL_INTERVENE:
            print(f"\n{C.CYAN}✋  Tryb ręcznej interwencji — agent wstrzymany.{C.RESET}\n")

        elif choice == EscalationChoice.ASSIGN_NEW_MODEL:
            print(f"\n{C.MAGENTA}🔄  Zadanie zostanie przydzielone innemu modelowi.{C.RESET}\n")

        return choice

    def _print_escalation_prompt(self, report: LoopReport) -> None:
        """Wyświetla szczegółowy prompt eskalacji dla człowieka."""
        sep = C.BG_RED + " " * 70 + C.RESET
        print(f"\n{sep}")
        print(f"{C.BG_RED}{C.BOLD}  ESKALACJA — WYKRYTO PĘTLĘ KOREKCJI  {C.RESET}")
        print(sep)
        print(f"\n{C.BOLD}Agent:{C.RESET}  {C.YELLOW}{report.agent_id}{C.RESET}")
        print(f"{C.BOLD}Plik: {C.RESET}  {C.CYAN}{report.file_path}{C.RESET}")
        print(f"{C.BOLD}Status:{C.RESET} {_status_colored(report.status)}")
        print(f"{C.BOLD}Wynik pętli:{C.RESET} {_score_bar(report.loop_score)}")
        print(f"{C.BOLD}Iteracje:{C.RESET} {report.iteration_count}/{self.max_iterations}")

        if report.oscillation_detected:
            print(f"\n{C.RED}  ↺  Wykryto oscylacyjne łatki (nakładanie: {report.patch_overlap_ratio:.0%}){C.RESET}")
        if report.semantic_loop_detected:
            fids = ", ".join(report.repeated_findings[:5])
            print(f"{C.RED}  ∞  Pętla semantyczna — powtarzające się znaleziska: {fids}{C.RESET}")

        print(f"\n{C.DIM}Rekomendacja: {report.recommendation}{C.RESET}")
        print(f"\n{C.BOLD}Wybierz opcję:{C.RESET}")
        print(f"  {C.GREEN}a){C.RESET}  Wymuszenie kontynuacji (override limitu)")
        print(f"  {C.YELLOW}b){C.RESET}  Pominięcie tego pliku/znaleziska")
        print(f"  {C.CYAN}c){C.RESET}  Ręczna interwencja (sam naprawię)")
        print(f"  {C.MAGENTA}d){C.RESET}  Przydziel innemu modelowi")
        print()

    def _read_human_choice(self) -> EscalationChoice:
        """Odczytuje wybór człowieka z wejścia standardowego."""
        mapping = {
            "a": EscalationChoice.FORCE_CONTINUE,
            "b": EscalationChoice.SKIP,
            "c": EscalationChoice.MANUAL_INTERVENE,
            "d": EscalationChoice.ASSIGN_NEW_MODEL,
        }
        while True:
            try:
                raw = input(f"{C.BOLD}Twój wybór (a/b/c/d): {C.RESET}").strip().lower()
                if raw in mapping:
                    return mapping[raw]
                print(f"{C.RED}Nieprawidłowy wybór. Wpisz a, b, c lub d.{C.RESET}")
            except (EOFError, KeyboardInterrupt):
                # Nieinteraktywne środowisko — domyślnie pomiń
                logger.warning("Nieinteraktywne wejście — domyślna decyzja: SKIP")
                return EscalationChoice.SKIP

    # ------------------------------------------------------------------
    # Statystyki agenta
    # ------------------------------------------------------------------

    def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Zwraca statystyki agenta: iteracje, wykryte pętle, pliki, koszt."""
        base = self._agent_stats.get(agent_id, {
            "total_iterations": 0,
            "loops_detected": 0,
            "files_touched": set(),
            "total_cost_usd": 0.0,
            "total_duration_sec": 0.0,
        })
        # Policz wykryte pętle dla tego agenta
        loops = sum(
            1 for (aid, _), report in self._loop_reports.items()
            if aid == agent_id and report.status in (LoopStatus.LOOP_DETECTED, LoopStatus.HARD_LIMIT)
        )
        return {
            "agent_id": agent_id,
            "total_iterations": base.get("total_iterations", 0),
            "loops_detected": loops,
            "files_touched": list(base.get("files_touched", set())),
            "total_cost_usd": round(base.get("total_cost_usd", 0.0), 4),
            "total_duration_sec": round(base.get("total_duration_sec", 0.0), 2),
        }

    def _update_agent_stats(
        self,
        agent_id: str,
        file_path: str,
        cost_usd: float,
        duration_sec: float,
    ) -> None:
        """Aktualizuje wewnętrzne statystyki agenta."""
        if agent_id not in self._agent_stats:
            self._agent_stats[agent_id] = {
                "total_iterations": 0,
                "loops_detected": 0,
                "files_touched": set(),
                "total_cost_usd": 0.0,
                "total_duration_sec": 0.0,
            }
        stats = self._agent_stats[agent_id]
        stats["total_iterations"] += 1
        stats["total_cost_usd"] += cost_usd
        stats["total_duration_sec"] += duration_sec
        stats["files_touched"].add(file_path)

    # ------------------------------------------------------------------
    # Reset agenta
    # ------------------------------------------------------------------

    def reset_agent(self, agent_id: str) -> None:
        """Resetuje liczniki agenta po ręcznej interwencji człowieka."""
        keys_to_remove = [key for key in self._records if key[0] == agent_id]
        for key in keys_to_remove:
            del self._records[key]
        loop_keys_to_remove = [key for key in self._loop_reports if key[0] == agent_id]
        for key in loop_keys_to_remove:
            del self._loop_reports[key]
        override_keys = [(aid, fp) for (aid, fp) in self._overridden if aid == agent_id]
        for key in override_keys:
            self._overridden.discard(key)
        if agent_id in self._agent_stats:
            del self._agent_stats[agent_id]
        logger.info("Agent %s zresetowany — wszystkie liczniki wyczyszczone.", agent_id)

    # ------------------------------------------------------------------
    # Dashboard CLI
    # ------------------------------------------------------------------

    def print_loop_dashboard(self) -> None:
        """Wyświetla bogaty widok CLI wszystkich śledzonych pętli."""
        print(f"\n{C.BOLD}{C.BG_YELLOW}{'':>2}{'SYLION LOOP GUARD — DASHBOARD':^66}{'':>2}{C.RESET}")
        print(f"{C.DIM}{'─' * 70}{C.RESET}")

        if not self._records:
            print(f"  {C.DIM}Brak zarejestrowanych iteracji.{C.RESET}\n")
            return

        # Grupuj po agencie
        agents: dict[str, list[tuple[str, str]]] = {}
        for (agent_id, file_path) in self._records:
            agents.setdefault(agent_id, []).append((agent_id, file_path))

        for agent_id, keys in sorted(agents.items()):
            stats = self.get_agent_stats(agent_id)
            print(f"\n  {C.BOLD}{C.CYAN}{agent_id}{C.RESET}")
            print(
                f"    Łączne iteracje: {C.WHITE}{stats['total_iterations']}{C.RESET}  "
                f"Koszt: {C.WHITE}${stats['total_cost_usd']:.4f}{C.RESET}  "
                f"Czas: {C.WHITE}{stats['total_duration_sec']:.1f}s{C.RESET}  "
                f"Wykryte pętle: {C.RED}{stats['loops_detected']}{C.RESET}"
            )
            for (aid, file_path) in sorted(keys, key=lambda k: k[1]):
                records = self._records[(aid, file_path)]
                status = self.check_loop(aid, file_path)
                score = self._calculate_loop_score(aid, file_path)
                short_path = _truncate_path(file_path, max_len=45)
                print(
                    f"    {C.DIM}│{C.RESET} {short_path:<46} "
                    f"iter={C.WHITE}{len(records)}{C.RESET}/{self.max_iterations}  "
                    f"{_status_colored(status)}  "
                    f"{_score_bar(score)}"
                )

        print(f"\n{C.DIM}{'─' * 70}{C.RESET}")
        total_agents = len(agents)
        total_files = len(self._records)
        total_loops = sum(
            1 for r in self._loop_reports.values()
            if r.status in (LoopStatus.LOOP_DETECTED, LoopStatus.HARD_LIMIT)
        )
        print(
            f"  Razem: {C.WHITE}{total_agents}{C.RESET} agentów, "
            f"{C.WHITE}{total_files}{C.RESET} plików, "
            f"{C.RED}{total_loops}{C.RESET} wykrytych pętli\n"
        )


# ═══════════════════════════════════════════════════════════════════════════
# CZĘŚĆ 2: ContextPersistence — pamięć podsumowań i migawki stanu
# ═══════════════════════════════════════════════════════════════════════════

class ContextPersistence:
    """Zapobiega utracie kontekstu podczas długich pętli audytu.

    Po każdej udanej łatce zapisuje strukturalne podsumowanie, aby agenci
    mogli odtworzyć kontekst nawet gdy okno LLM się przepełni.
    """

    SNAPSHOT_INTERVAL: int = 10  # Co ile wpisów osi czasu rób migawkę

    def __init__(
        self,
        results_dir: Path | None = None,
        context_window_size: int = 20,
    ) -> None:
        self.results_dir = Path(results_dir or "results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Okno kontekstu — ostatnie N operacji
        self._context_window = ContextWindow(max_entries=context_window_size)

        # Pełna oś czasu
        self._timeline: list[TimelineEntry] = []

        # Podsumowania łatek: patch_id → PatchSummary
        self._patch_summaries: dict[str, PatchSummary] = {}

        # Podsumowania etapów: stage_id → StageSummary
        self._stage_summaries: dict[str, StageSummary] = {}

        # Licznik do wyzwalania migawek
        self._entry_counter: int = 0

        logger.info(
            "ContextPersistence zainicjalizowany — katalog: %s, okno: %d",
            self.results_dir, context_window_size,
        )

    # ------------------------------------------------------------------
    # Zapis podsumowań łatek
    # ------------------------------------------------------------------

    def save_patch_summary(self, summary: PatchSummary) -> None:
        """Zapisuje podsumowanie łatki do pamięci i na dysk."""
        self._patch_summaries[summary.patch_id] = summary

        entry = TimelineEntry(
            event_type=EventType.PATCH_APPLIED,
            agent_id=summary.agent_id,
            description=(
                f"Łatka #{summary.iteration_number} zastosowana do {summary.file_path} "
                f"przez {summary.model_used} — znaleziska: {summary.findings_addressed}"
            ),
            details=summary.to_dict(),
        )
        self._add_timeline_entry(entry)

        # Zapisz na dysk
        out_file = self.results_dir / f"patch_{summary.patch_id}.json"
        _write_json(out_file, summary.to_dict())
        logger.debug("Podsumowanie łatki %s zapisane do %s", summary.patch_id, out_file)

    # ------------------------------------------------------------------
    # Zapis podsumowań etapów
    # ------------------------------------------------------------------

    def save_stage_summary(self, summary: StageSummary) -> None:
        """Zapisuje podsumowanie etapu do pamięci i na dysk."""
        self._stage_summaries[summary.stage_id] = summary

        entry = TimelineEntry(
            event_type=EventType.STAGE_COMPLETE,
            agent_id="pipeline",
            description=(
                f"Etap '{summary.stage_name}' zakończony — "
                f"znaleziska: {summary.findings_found}/{summary.findings_resolved} rozwiązane, "
                f"koszt: ${summary.cost_usd:.4f}"
            ),
            details=summary.to_dict(),
        )
        self._add_timeline_entry(entry)

        out_file = self.results_dir / f"stage_{summary.stage_id}.json"
        _write_json(out_file, summary.to_dict())
        logger.info("Podsumowanie etapu '%s' zapisane do %s", summary.stage_name, out_file)

    # ------------------------------------------------------------------
    # Zdarzenia osi czasu
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: EventType,
        agent_id: str,
        description: str,
        details: dict[str, Any] | None = None,
    ) -> TimelineEntry:
        """Rejestruje dowolne zdarzenie w osi czasu."""
        entry = TimelineEntry(
            event_type=event_type,
            agent_id=agent_id,
            description=description,
            details=details or {},
        )
        self._add_timeline_entry(entry)
        return entry

    def _add_timeline_entry(self, entry: TimelineEntry) -> None:
        """Dodaje wpis do osi czasu i okna kontekstu; wyzwala migawki."""
        self._timeline.append(entry)
        self._context_window.add(entry)
        self._entry_counter += 1

        # Periodyczna migawka pełnego stanu
        if self._entry_counter % self.SNAPSHOT_INTERVAL == 0:
            self._save_memory_snapshot()

    # ------------------------------------------------------------------
    # Kontekst dla agenta
    # ------------------------------------------------------------------

    def get_context_for_agent(self, agent_id: str) -> str:
        """Zwraca sformatowany ciąg kontekstu gotowy do wstrzyknięcia w prompt agenta.

        Zawiera:
          1. Globalne okno kontekstu (ostatnie N operacji)
          2. Ostatnie łatki tego agenta
          3. Niezakończone znaleziska (z ostatniego etapu)
        """
        lines: list[str] = []

        # Sekcja 1: Globalne okno
        lines.append(self._context_window.format())

        # Sekcja 2: Łatki tego agenta
        agent_patches = [
            ps for ps in self._patch_summaries.values()
            if ps.agent_id == agent_id
        ]
        agent_patches.sort(key=lambda p: p.timestamp)
        if agent_patches:
            lines.append("\n=== TWOJE OSTATNIE ŁATKI ===")
            for ps in agent_patches[-5:]:  # Ostatnie 5
                ts = ps.timestamp.strftime("%H:%M:%S")
                lines.append(
                    f"  [{ts}] {ps.file_path} (iter #{ps.iteration_number}, "
                    f"model: {ps.model_used})"
                )
                if ps.findings_addressed:
                    lines.append(f"    → Rozwiązane znaleziska: {', '.join(ps.findings_addressed)}")
                if ps.diff_preview:
                    preview = ps.diff_preview[:200].replace("\n", "\\n")
                    lines.append(f"    → Podgląd diff: {preview}...")

        # Sekcja 3: Ostatni etap
        if self._stage_summaries:
            last_stage = max(self._stage_summaries.values(), key=lambda s: s.timestamp)
            lines.append(f"\n=== OSTATNI ETAP: {last_stage.stage_name} ===")
            lines.append(
                f"  Znaleziska: {last_stage.findings_found} znalezionych, "
                f"{last_stage.findings_resolved} rozwiązanych, "
                f"{last_stage.findings_remaining} pozostałych"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Pełna oś czasu
    # ------------------------------------------------------------------

    def get_full_timeline(self) -> list[TimelineEntry]:
        """Zwraca uporządkowaną listę wszystkich zdarzeń."""
        return list(self._timeline)

    # ------------------------------------------------------------------
    # Migawki pamięci (checkpointy)
    # ------------------------------------------------------------------

    def _save_memory_snapshot(self) -> None:
        """Zapisuje pełny stan do pliku JSON jako checkpoint restartu."""
        snapshot_id = f"snapshot_{self._entry_counter:06d}"
        snapshot = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(self._timeline),
            "patch_summaries": {k: v.to_dict() for k, v in self._patch_summaries.items()},
            "stage_summaries": {k: v.to_dict() for k, v in self._stage_summaries.items()},
            "timeline": [e.to_dict() for e in self._timeline],
            "context_window": [e.to_dict() for e in self._context_window.entries],
        }
        out_file = self.results_dir / f"{snapshot_id}.json"
        _write_json(out_file, snapshot)
        logger.info("Migawka pamięci zapisana: %s", out_file)

    def save_checkpoint(self) -> Path:
        """Wymusza natychmiastowy zapis migawki i zwraca ścieżkę pliku."""
        self._save_memory_snapshot()
        snapshot_id = f"snapshot_{self._entry_counter:06d}"
        return self.results_dir / f"{snapshot_id}.json"

    def load_checkpoint(self, checkpoint_path: Path) -> None:
        """Ładuje stan z wcześniejszej migawki (restart po awarii)."""
        data = _read_json(checkpoint_path)
        if not data:
            logger.error("Nie można wczytać migawki z %s", checkpoint_path)
            return

        self._patch_summaries = {
            k: PatchSummary.from_dict(v)
            for k, v in data.get("patch_summaries", {}).items()
        }
        self._stage_summaries = {
            k: StageSummary.from_dict(v)
            for k, v in data.get("stage_summaries", {}).items()
        }
        self._timeline = [
            TimelineEntry.from_dict(e) for e in data.get("timeline", [])
        ]
        ctx_entries = [
            TimelineEntry.from_dict(e) for e in data.get("context_window", [])
        ]
        self._context_window.entries = ctx_entries
        self._entry_counter = data.get("entry_count", len(self._timeline))
        logger.info(
            "Checkpoint wczytany z %s — %d wpisów osi czasu",
            checkpoint_path, len(self._timeline),
        )

    # ------------------------------------------------------------------
    # Eksport do JSON
    # ------------------------------------------------------------------

    def export_timeline(self, output_path: Path | None = None) -> Path:
        """Eksportuje pełną oś czasu do pliku JSON."""
        out = output_path or (self.results_dir / "timeline_export.json")
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(self._timeline),
            "entries": [e.to_dict() for e in self._timeline],
        }
        _write_json(out, data)
        logger.info("Oś czasu wyeksportowana do %s (%d wpisów)", out, len(self._timeline))
        return out


# ═══════════════════════════════════════════════════════════════════════════
# CZĘŚĆ 3: IterationTracker — pełny stan pętli korekcji
# ═══════════════════════════════════════════════════════════════════════════

class IterationTracker:
    """Śledzi stan iteracyjnych pętli korekcji.

    Mapuje: plik → [iteracja_1, iteracja_2, ...], gdzie każda iteracja zawiera:
    patch_applied, audit_result, findings_new, findings_resolved
    """

    def __init__(self, results_dir: Path | None = None) -> None:
        self.results_dir = Path(results_dir or "results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Słownik: file_path → lista IterationState
        self._file_iterations: dict[str, list[IterationState]] = {}

        # Aktywne iteracje: (agent_id, file_path) → czas startu
        self._active: dict[tuple[str, str], float] = {}

        # Globalne znaleziska: finding_id → status
        self._findings: dict[str, str] = {}   # "open" | "resolved" | "skipped"

        logger.info("IterationTracker zainicjalizowany — katalog: %s", self.results_dir)

    # ------------------------------------------------------------------
    # Zarządzanie iteracjami
    # ------------------------------------------------------------------

    def start_iteration(self, agent_id: str, file_path: str) -> int:
        """Rozpoczyna nową iterację i zwraca jej numer."""
        key = (agent_id, file_path)
        self._active[key] = time.monotonic()

        if file_path not in self._file_iterations:
            self._file_iterations[file_path] = []

        iteration_number = len(self._file_iterations[file_path]) + 1
        logger.debug("Iteracja %d rozpoczęta — agent=%s plik=%s", iteration_number, agent_id, file_path)
        return iteration_number

    def finish_iteration(
        self,
        agent_id: str,
        file_path: str,
        patch_applied: str | None = None,
        audit_result: str | None = None,
        findings_new: list[str] | None = None,
        findings_resolved: list[str] | None = None,
        model_used: str = "",
    ) -> IterationState:
        """Kończy bieżącą iterację i zapisuje jej stan.

        Args:
            agent_id:          Identyfikator agenta
            file_path:         Ścieżka pliku
            patch_applied:     Diff zastosowanej łatki (lub None)
            audit_result:      Wynik audytu (opis tekstowy)
            findings_new:      Lista ID nowych znalezisk
            findings_resolved: Lista ID rozwiązanych znalezisk
            model_used:        Nazwa modelu LLM użytego w tej iteracji

        Returns:
            Zapisany IterationState
        """
        key = (agent_id, file_path)
        start_time = self._active.pop(key, time.monotonic())
        duration = time.monotonic() - start_time

        if file_path not in self._file_iterations:
            self._file_iterations[file_path] = []

        iteration_number = len(self._file_iterations[file_path]) + 1
        state = IterationState(
            iteration_number=iteration_number,
            patch_applied=patch_applied,
            audit_result=audit_result,
            findings_new=findings_new or [],
            findings_resolved=findings_resolved or [],
            agent_id=agent_id,
            model_used=model_used,
        )
        self._file_iterations[file_path].append(state)

        # Zaktualizuj globalny słownik znalezisk
        for fid in state.findings_new:
            self._findings[fid] = "open"
        for fid in state.findings_resolved:
            self._findings[fid] = "resolved"

        logger.debug(
            "Iteracja %d zakończona — plik=%s czas=%.1fs nowe=%d rozwiązane=%d",
            iteration_number, file_path, duration,
            len(state.findings_new), len(state.findings_resolved),
        )

        # Zapis do JSON
        self._persist_file_iterations(file_path)
        return state

    # ------------------------------------------------------------------
    # Odpytywanie stanu
    # ------------------------------------------------------------------

    def get_iterations(self, file_path: str) -> list[IterationState]:
        """Zwraca wszystkie iteracje dla danego pliku."""
        return list(self._file_iterations.get(file_path, []))

    def get_iteration_count(self, file_path: str) -> int:
        """Zwraca liczbę iteracji dla danego pliku."""
        return len(self._file_iterations.get(file_path, []))

    def get_open_findings(self) -> list[str]:
        """Zwraca listę ID otwartych (nierozwiązanych) znalezisk."""
        return [fid for fid, status in self._findings.items() if status == "open"]

    def get_resolved_findings(self) -> list[str]:
        """Zwraca listę ID rozwiązanych znalezisk."""
        return [fid for fid, status in self._findings.items() if status == "resolved"]

    def get_all_tracked_files(self) -> list[str]:
        """Zwraca listę wszystkich śledzonych plików."""
        return list(self._file_iterations.keys())

    def get_file_summary(self, file_path: str) -> dict[str, Any]:
        """Zwraca skrócone podsumowanie historii iteracji dla pliku."""
        iterations = self._file_iterations.get(file_path, [])
        all_new = [fid for it in iterations for fid in it.findings_new]
        all_resolved = [fid for it in iterations for fid in it.findings_resolved]
        models_used = list({it.model_used for it in iterations if it.model_used})
        agents_used = list({it.agent_id for it in iterations if it.agent_id})
        patches_applied = sum(1 for it in iterations if it.patch_applied is not None)

        return {
            "file_path": file_path,
            "total_iterations": len(iterations),
            "patches_applied": patches_applied,
            "total_new_findings": len(all_new),
            "total_resolved_findings": len(all_resolved),
            "open_findings": list(set(all_new) - set(all_resolved)),
            "models_used": models_used,
            "agents_used": agents_used,
        }

    def get_global_summary(self) -> dict[str, Any]:
        """Zwraca globalne podsumowanie wszystkich śledzonych plików."""
        total_iterations = sum(len(iters) for iters in self._file_iterations.values())
        return {
            "total_files": len(self._file_iterations),
            "total_iterations": total_iterations,
            "open_findings": len(self.get_open_findings()),
            "resolved_findings": len(self.get_resolved_findings()),
            "active_iterations": len(self._active),
        }

    # ------------------------------------------------------------------
    # Śledzenie znalezisk
    # ------------------------------------------------------------------

    def mark_finding_skipped(self, finding_id: str) -> None:
        """Oznacza znalezisko jako pominięte (decyzja człowieka)."""
        self._findings[finding_id] = "skipped"
        logger.info("Znalezisko %s oznaczone jako pominięte.", finding_id)

    def add_finding(self, finding_id: str) -> None:
        """Rejestruje nowe znalezisko bez powiązania z iteracją."""
        if finding_id not in self._findings:
            self._findings[finding_id] = "open"

    # ------------------------------------------------------------------
    # Trwałość danych
    # ------------------------------------------------------------------

    def _persist_file_iterations(self, file_path: str) -> None:
        """Zapisuje iteracje danego pliku do JSON."""
        safe_name = file_path.replace("/", "_").replace("\\", "_")[:80]
        out_file = self.results_dir / f"iterations_{safe_name}.json"
        data = {
            "file_path": file_path,
            "iterations": [it.to_dict() for it in self._file_iterations[file_path]],
        }
        _write_json(out_file, data)

    def save_all(self) -> Path:
        """Zapisuje pełny stan IterationTracker do JSON i zwraca ścieżkę."""
        out_file = self.results_dir / "iteration_tracker_state.json"
        data = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "file_iterations": {
                fp: [it.to_dict() for it in iters]
                for fp, iters in self._file_iterations.items()
            },
            "findings": dict(self._findings),
        }
        _write_json(out_file, data)
        logger.info("Stan IterationTracker zapisany do %s", out_file)
        return out_file

    def load_state(self, state_path: Path) -> None:
        """Wczytuje stan z wcześniejszego zapisu."""
        data = _read_json(state_path)
        if not data:
            logger.error("Nie można wczytać stanu z %s", state_path)
            return
        self._file_iterations = {
            fp: [IterationState.from_dict(it) for it in iters]
            for fp, iters in data.get("file_iterations", {}).items()
        }
        self._findings = data.get("findings", {})
        logger.info(
            "Stan wczytany z %s — %d plików, %d znalezisk",
            state_path, len(self._file_iterations), len(self._findings),
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def print_iteration_dashboard(self) -> None:
        """Wyświetla przegląd śledzonych iteracji dla wszystkich plików."""
        summary = self.get_global_summary()
        print(f"\n{C.BOLD}{C.BG_YELLOW}{'':>2}{'ITERATION TRACKER — DASHBOARD':^66}{'':>2}{C.RESET}")
        print(f"{C.DIM}{'─' * 70}{C.RESET}")
        print(
            f"  Pliki: {C.WHITE}{summary['total_files']}{C.RESET}  "
            f"Iteracje: {C.WHITE}{summary['total_iterations']}{C.RESET}  "
            f"Otwarte znaleziska: {C.RED}{summary['open_findings']}{C.RESET}  "
            f"Rozwiązane: {C.GREEN}{summary['resolved_findings']}{C.RESET}"
        )

        if not self._file_iterations:
            print(f"  {C.DIM}Brak śledzonych plików.{C.RESET}\n")
            return

        print()
        for file_path in sorted(self._file_iterations):
            fs = self.get_file_summary(file_path)
            short_path = _truncate_path(file_path, max_len=50)
            open_count  = len(fs["open_findings"])
            status_color = C.RED if open_count > 0 else C.GREEN
            print(
                f"  {C.DIM}│{C.RESET} {short_path:<51} "
                f"iter={C.WHITE}{fs['total_iterations']}{C.RESET}  "
                f"łatki={C.CYAN}{fs['patches_applied']}{C.RESET}  "
                f"otwarte={status_color}{open_count}{C.RESET}"
            )

        print(f"\n{C.DIM}{'─' * 70}{C.RESET}\n")


# ═══════════════════════════════════════════════════════════════════════════
# FUNKCJE POMOCNICZE
# ═══════════════════════════════════════════════════════════════════════════

def _status_colored(status: LoopStatus) -> str:
    """Zwraca kolorowany ciąg statusu pętli."""
    mapping = {
        LoopStatus.OK:            f"{C.GREEN}OK{C.RESET}",
        LoopStatus.WARNING:       f"{C.YELLOW}OSTRZEŻENIE{C.RESET}",
        LoopStatus.LOOP_DETECTED: f"{C.RED}PĘTLA WYKRYTA{C.RESET}",
        LoopStatus.HARD_LIMIT:    f"{C.BG_RED}{C.WHITE}HARD LIMIT{C.RESET}",
    }
    return mapping.get(status, status.value)


def _score_bar(score: float, width: int = 10) -> str:
    """Zwraca wizualny pasek wynik pętli (0.0–1.0)."""
    filled = round(score * width)
    bar = "█" * filled + "░" * (width - filled)
    if score >= 0.70:
        color = C.RED
    elif score >= 0.45:
        color = C.YELLOW
    else:
        color = C.GREEN
    return f"{color}{bar}{C.RESET} {score:.0%}"


def _truncate_path(path: str, max_len: int = 50) -> str:
    """Skraca ścieżkę do max_len znaków, zachowując koniec."""
    if len(path) <= max_len:
        return path
    return "…" + path[-(max_len - 1):]


def _write_json(path: Path, data: Any) -> None:
    """Zapisuje dane do pliku JSON z obsługą błędów."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    except OSError as exc:
        logger.error("Błąd zapisu do %s: %s", path, exc)


def _read_json(path: Path) -> Any:
    """Odczytuje dane z pliku JSON z obsługą błędów."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Błąd odczytu z %s: %s", path, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# DEMO / QUICK TEST
# ═══════════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Szybka demonstracja działania wszystkich komponentów."""
    import tempfile

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    print(f"\n{C.BOLD}{C.MAGENTA}{'═' * 70}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}  SYLION Loop Guard — Demo{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}{'═' * 70}{C.RESET}\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        results_dir = Path(tmpdir) / "results"

        # --- LoopGuard ---
        print(f"{C.CYAN}[1/3] LoopGuard{C.RESET}")
        lg = LoopGuard(max_iterations=5, results_dir=results_dir)

        agent = "programmer_go_1"
        fpath = "internal/auth/jwt.go"

        diff1 = "--- a/jwt.go\n+++ b/jwt.go\n@@ -10 +10 @@ func Verify() {\n-  return nil\n+  return err\n"
        diff2 = "--- a/jwt.go\n+++ b/jwt.go\n@@ -10 +10 @@ func Verify() {\n-  return err\n+  return nil\n"

        for i, (diff, fid) in enumerate([
            (diff1, "FIND-001: nil dereference"),
            (diff2, "FIND-001: nil dereference"),
            (diff1, "FIND-001: nil dereference"),
            (diff2, "FIND-002: unhandled error"),
        ], start=1):
            status = lg.record_iteration(agent, fpath, "patch", fid, diff, cost_usd=0.02, duration_sec=3.5)
            score  = lg._calculate_loop_score(agent, fpath)
            print(
                f"  Iteracja {i}: status={_status_colored(status)}  "
                f"wynik={_score_bar(score)}"
            )

        report = lg.get_loop_report(agent, fpath)
        print(f"\n  Raport pętli:")
        print(f"    oscylacja={report.oscillation_detected}  "
              f"semantyczna={report.semantic_loop_detected}  "
              f"powtarzające się znaleziska={report.repeated_findings}")
        print(f"    Rekomendacja: {C.DIM}{report.recommendation}{C.RESET}")

        lg.print_loop_dashboard()

        # --- ContextPersistence ---
        print(f"{C.CYAN}[2/3] ContextPersistence{C.RESET}")
        cp = ContextPersistence(results_dir=results_dir, context_window_size=10)

        cp.save_patch_summary(PatchSummary(
            file_path=fpath,
            diff_preview=diff1[:200],
            findings_addressed=["FIND-001"],
            model_used="gpt-4o",
            iteration_number=1,
            agent_id=agent,
        ))
        cp.save_stage_summary(StageSummary(
            stage_name="Audyt bezpieczeństwa JWT",
            agents_involved=[agent, "auditor_sec_1"],
            findings_found=3,
            findings_resolved=1,
            findings_remaining=2,
            duration_sec=45.2,
            cost_usd=0.18,
            human_decisions=["SKIP FIND-003"],
        ))
        cp.record_event(EventType.LOOP_DETECTED, agent, f"Pętla wykryta dla {fpath}")

        ctx = cp.get_context_for_agent(agent)
        print(f"\n  Kontekst dla agenta ({len(ctx)} znaków):")
        print(f"  {C.DIM}{ctx[:300]}...{C.RESET}\n")

        checkpoint = cp.save_checkpoint()
        print(f"  Checkpoint zapisany: {checkpoint.name}")

        timeline = cp.get_full_timeline()
        print(f"  Oś czasu: {len(timeline)} wpisów")

        # --- IterationTracker ---
        print(f"\n{C.CYAN}[3/3] IterationTracker{C.RESET}")
        it = IterationTracker(results_dir=results_dir)

        files = ["internal/auth/jwt.go", "pkg/db/conn.go", "cmd/server/main.go"]
        for fp in files:
            for n in range(3):
                it.start_iteration(agent, fp)
                it.finish_iteration(
                    agent, fp,
                    patch_applied=diff1 if n % 2 == 0 else diff2,
                    audit_result=f"Iteracja {n+1} — znaleziono {2-n} problemów",
                    findings_new=[f"F-{fp[:3]}-{n*10+1}"] if n < 2 else [],
                    findings_resolved=[f"F-{fp[:3]}-{(n-1)*10+1}"] if n > 0 else [],
                    model_used="gpt-4o-mini",
                )

        it.print_iteration_dashboard()

        state_path = it.save_all()
        print(f"  Stan zapisany: {state_path.name}")
        print(f"  Otwarte znaleziska: {it.get_open_findings()}")
        print(f"  Globalne podsumowanie: {it.get_global_summary()}")

    print(f"\n{C.BOLD}{C.GREEN}Demo zakończone pomyślnie.{C.RESET}\n")


if __name__ == "__main__":
    _demo()
