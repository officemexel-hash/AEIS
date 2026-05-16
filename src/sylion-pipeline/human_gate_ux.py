#!/usr/bin/env python3
"""
human_gate_ux.py — Enhanced Human Gate UX for SYLION pipeline.

Provides consequence-aware decision menus so the administrator can see
exactly what will happen before choosing each option.

Designed to be imported by supervisor.py; has zero internal project imports.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# ANSI colors — identical to supervisor.py so this module can be used
# standalone or imported without colour conflicts.
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
# Helpers
# ---------------------------------------------------------------------------

def format_cost(dollars: float) -> str:
    """Convert a dollar amount to a human-readable string.

    Examples:
        0.0   -> "$0.00"
        0.5   -> "~$0.50"
        1.234 -> "~$1.23"
    """
    if dollars == 0.0:
        return "$0.00"
    return f"~${dollars:.2f}"


def format_time(seconds: float) -> str:
    """Convert seconds to a human-readable duration string.

    Examples:
        30    -> "~30 sek"
        90    -> "~1 min"
        3700  -> "~1 godz 1 min"
    """
    if seconds < 60:
        return f"~{int(seconds)} sek"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"~{minutes} min"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes == 0:
        return f"~{hours} godz"
    return f"~{hours} godz {remaining_minutes} min"


def _wrap(text: str, width: int = 70, indent: str = "") -> str:
    """Wrap text to *width* columns with a fixed *indent* on each line."""
    return textwrap.fill(text, width=width, initial_indent=indent,
                         subsequent_indent=indent)


def _bullet_lines(items: list[str], prefix: str = "  • ") -> list[str]:
    """Return each item prefixed with *prefix*, wrapped to 68 chars."""
    result = []
    for item in items:
        wrapped = textwrap.fill(item, width=68,
                                initial_indent=prefix,
                                subsequent_indent=" " * len(prefix))
        result.append(wrapped)
    return result


# ---------------------------------------------------------------------------
# ConsequenceInfo dataclass
# ---------------------------------------------------------------------------

@dataclass
class ConsequenceInfo:
    """Full consequence description for a single decision option."""

    decision: str               # Internal key: "approve", "reject", …
    label: str                  # Short Polish label shown in menu
    icon: str                   # Emoji / symbol prefix
    will_happen: list[str]      # What WILL happen if chosen
    wont_happen: list[str]      # What gets skipped / will NOT happen
    risks: list[str]            # Warnings and risk notes
    reversible: bool            # Can the action be undone?
    reversibility_note: str     # How to reverse (or why not possible)
    estimated_time: str         # Human-readable duration, e.g. "~5 min"
    estimated_cost: str         # Human-readable cost, e.g. "~$0.50"
    affected_agents: list[str]  # Agent names impacted by this decision
    recommendation: str         # "" | "ZALECANE" | "OSTROŻNOŚĆ" | "NIEBEZPIECZNE"


# ---------------------------------------------------------------------------
# ConsequenceDescriptor — maps action_type + context → ConsequenceInfo dict
# ---------------------------------------------------------------------------

class ConsequenceDescriptor:
    """Generates human-readable descriptions of what will happen
    if the administrator picks each available option.

    Context-aware: the descriptions change based on what's being approved
    (e.g. deploying to a device vs running a test vs starting an audit).
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def describe_consequences(
        self, action_type: str, context: dict[str, Any]
    ) -> dict[str, ConsequenceInfo]:
        """Return a mapping of decision name → ConsequenceInfo.

        Parameters
        ----------
        action_type:
            One of the known context types (pipeline_start, agent_run, …).
        context:
            Arbitrary metadata about the specific action being approved.
            Common keys: agent_name, model, stage, title, file_path,
            iteration, max_iterations, current_model, num_files, cost_est,
            time_est_secs, findings, etc.
        """
        # PIPELINE-004 fix: _HANDLERS holds unbound function refs,
        # called as handler(self, context). Fallback must be the unbound
        # function too, not a bound method, otherwise self is passed twice.
        handler = self._HANDLERS.get(action_type, ConsequenceDescriptor._generic)
        return handler(self, context)

    # ------------------------------------------------------------------ #
    # Internal builder helpers
    # ------------------------------------------------------------------ #

    def _make(
        self,
        decision: str,
        label: str,
        icon: str,
        will_happen: list[str],
        wont_happen: list[str] | None = None,
        risks: list[str] | None = None,
        reversible: bool = True,
        reversibility_note: str = "",
        estimated_time: str = "",
        estimated_cost: str = "",
        affected_agents: list[str] | None = None,
        recommendation: str = "",
    ) -> ConsequenceInfo:
        return ConsequenceInfo(
            decision=decision,
            label=label,
            icon=icon,
            will_happen=will_happen,
            wont_happen=wont_happen or [],
            risks=risks or [],
            reversible=reversible,
            reversibility_note=reversibility_note,
            estimated_time=estimated_time,
            estimated_cost=estimated_cost,
            affected_agents=affected_agents or [],
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------ #
    # Handler: pipeline_start
    # ------------------------------------------------------------------ #

    def _pipeline_start(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        pipeline_name = ctx.get("pipeline_name", "SYLION Pipeline")
        stages = ctx.get("stages") or []
        # Defensive: ensure stages is iterable of strings (not int/float)
        if isinstance(stages, (int, float)):
            stage_list = f"{stages} etap(\u00f3w)"
        elif isinstance(stages, (list, tuple)):
            stage_list = ", ".join(str(s) for s in stages) if stages else "wszystkie etapy"
        else:
            stage_list = str(stages)
        total_cost = ctx.get("total_cost_est", 0.0)
        total_time = ctx.get("total_time_est_secs", 0.0)

        approve = self._make(
            decision="approve",
            label="URUCHOM PIPELINE",
            icon="✅",
            will_happen=[
                f"Pipeline '{pipeline_name}' zostanie uruchomiony od początku.",
                f"Etapy do wykonania: {stage_list}.",
                f"Szacowany łączny czas: {format_time(total_time)}.",
                f"Szacowany łączny koszt API: {format_cost(total_cost)}.",
                "Supervisor zacznie nadzorować wszystkich agentów.",
                "Każdy etap będzie wymagał osobnej zgody w Human Gate.",
            ],
            wont_happen=[
                "Żaden etap nie zostanie pominięty bez Twojej zgody.",
            ],
            risks=[
                "Koszty API są naliczane per-token — nieodwracalne po rozpoczęciu etapu.",
                "Jeśli pipeline zostanie przerwany, wyniki częściowe mogą być niespójne.",
            ],
            reversible=True,
            reversibility_note="Każdy etap można zatrzymać w Human Gate przed wykonaniem.",
            estimated_time=format_time(total_time),
            estimated_cost=format_cost(total_cost),
            affected_agents=ctx.get("agents", []),
            recommendation="ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ANULUJ",
            icon="❌",
            will_happen=[
                "Pipeline NIE zostanie uruchomiony.",
                "Żaden agent nie wykona żadnej akcji.",
                "Proces zakończy się natychmiast.",
            ],
            wont_happen=[
                f"Pipeline '{pipeline_name}' nie ruszy.",
                "Żadne koszty API nie zostaną poniesione.",
            ],
            risks=[],
            reversible=True,
            reversibility_note="Możesz uruchomić pipeline ponownie w dowolnym momencie.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[],
            recommendation="",
        )

        defer = self._make(
            decision="defer",
            label="ODŁÓŻ",
            icon="⏸️",
            will_happen=[
                "Pipeline zostanie wstrzymany przed startem.",
                "Decyzja zostanie zapamiętana — możesz wrócić później.",
            ],
            wont_happen=["Żaden agent nie zostanie uruchomiony."],
            risks=["Zbyt długie odkładanie może zdezaktualizować kontekst."],
            reversible=True,
            reversibility_note="Wróć do decyzji gdy będziesz gotowy.",
            estimated_time="—",
            estimated_cost="$0.00",
            affected_agents=[],
            recommendation="",
        )

        return {"approve": approve, "reject": reject, "defer": defer}

    # ------------------------------------------------------------------ #
    # Handler: agent_run
    # ------------------------------------------------------------------ #

    def _agent_run(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        agent = ctx.get("agent_name", "Agent")
        model = ctx.get("model", "nieznany model")
        stage = ctx.get("stage", "?")
        num_files = ctx.get("num_files", 0)
        cost_est = ctx.get("cost_est", 0.0)
        time_est = ctx.get("time_est_secs", 0.0)
        output_path = ctx.get("output_path", "results/")
        total_agents = ctx.get("total_agents_in_stage", 1)
        consensus_threshold = ctx.get("consensus_threshold", "")

        approve = self._make(
            decision="approve",
            label="ZATWIERDŹ",
            icon="✅",
            will_happen=[
                f"Agent {agent} [{model}] zostanie uruchomiony.",
                f"Przeanalizuje {num_files} plików w etapie {stage}.",
                f"Wynik zapisany w: {output_path}.",
                f"Szacowany czas: {format_time(time_est)}, koszt: {format_cost(cost_est)}.",
            ],
            wont_happen=[],
            risks=[
                f"Koszt API ({format_cost(cost_est)}) jest nieodwracalny po starcie.",
                "LLM może wygenerować wyniki wymagające ręcznego przeglądu.",
            ],
            reversible=True,
            reversibility_note=f"Wynik można odrzucić na etapie Merge (Stage 4).",
            estimated_time=format_time(time_est),
            estimated_cost=format_cost(cost_est),
            affected_agents=[agent],
            recommendation="ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ODRZUĆ",
            icon="❌",
            will_happen=[
                f"Agent {agent} [{model}] NIE uruchomi się.",
                f"Wynik tego agenta nie będzie uwzględniony w konsensusie.",
                f"Audyt odbędzie się z {total_agents - 1} zamiast {total_agents} modeli.",
                f"Próg konsensusu: {consensus_threshold}" if consensus_threshold else
                "Sprawdź czy zmniejszona liczba agentów nie wpływa na próg konsensusu.",
            ],
            wont_happen=[
                f"Agent {agent} nie wykona żadnych operacji.",
                f"Żadne koszty API za {agent} nie zostaną naliczone.",
            ],
            risks=[
                "Mniej perspektyw = potencjalnie pominięte problemy bezpieczeństwa.",
                f"Jeśli {agent} był jedynym agentem etapu, etap zostanie pominięty.",
            ],
            reversible=True,
            reversibility_note="Możesz uruchomić agenta ponownie w kolejnym przebiegu.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        modify = self._make(
            decision="modify",
            label="MODYFIKUJ",
            icon="✏️",
            will_happen=[
                f"Możesz zmienić plan agenta {agent} przed uruchomieniem.",
                "Np. ograniczyć liczbę plików, zmienić focus areas, dostosować parametry.",
                "Po modyfikacji agent uruchomi się z nowym planem.",
            ],
            wont_happen=[
                "Agent nie uruchomi się dopóki nie zatwierdzisz zmodyfikowanego planu.",
            ],
            risks=[
                "Nieprawidłowa modyfikacja może spowodować błędy agenta.",
                "Modyfikacja może zmienić koszt i czas wykonania.",
            ],
            reversible=True,
            reversibility_note="Możesz cofnąć modyfikację przed ostatecznym zatwierdzeniem.",
            estimated_time=f"Twój czas + {format_time(time_est)}",
            estimated_cost=f"Zależne od modyfikacji (baza: {format_cost(cost_est)})",
            affected_agents=[agent],
            recommendation="",
        )

        defer = self._make(
            decision="defer",
            label="ODŁÓŻ",
            icon="⏸️",
            will_happen=[
                f"Agent {agent} czeka — pipeline kontynuuje pozostałe etapy.",
                "Wrócisz do tej decyzji później.",
            ],
            wont_happen=[f"Agent {agent} nie uruchomi się teraz."],
            risks=[
                "Etapy zależne od tego agenta mogą być zablokowane.",
                "Zbyt długie odkładanie może zdezaktualizować kontekst zadania.",
            ],
            reversible=True,
            reversibility_note="Możesz zatwierdzić agenta w dowolnym momencie.",
            estimated_time="—",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        escalate = self._make(
            decision="escalate",
            label="ESKALUJ",
            icon="⚠️",
            will_happen=[
                f"Agent {agent} zostanie wstrzymany.",
                "Supervisor wygeneruje szczegółowy raport z kontekstem decyzji.",
                "Możliwa głębsza analiza przed uruchomieniem.",
            ],
            wont_happen=[f"Agent {agent} nie uruchomi się bez dodatkowej analizy."],
            risks=["Opóźnienie pipeline'u o czas analizy."],
            reversible=True,
            reversibility_note="Po analizie możesz zatwierdzić lub odrzucić agenta.",
            estimated_time="Zależne od analizy",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        return {
            "approve": approve,
            "reject": reject,
            "modify": modify,
            "defer": defer,
            "escalate": escalate,
        }

    # ------------------------------------------------------------------ #
    # Handler: command_execution
    # ------------------------------------------------------------------ #

    def _command_execution(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        cmd = ctx.get("command", "<komenda>")
        description = ctx.get("description", "wykonanie komendy")
        target = ctx.get("target", "urządzenie")
        is_destructive = ctx.get("is_destructive", False)
        agent = ctx.get("agent_name", "Agent")

        approve = self._make(
            decision="approve",
            label="ZATWIERDŹ KOMENDĘ",
            icon="✅",
            will_happen=[
                f"Komenda zostanie wykonana na: {target}.",
                f"Cel: {description}.",
                f"Komenda: {cmd}",
                "Wynik zostanie przekazany do agenta i zalogowany.",
            ],
            wont_happen=[],
            risks=(
                [
                    "DESTRUKTYWNA operacja — może spowodować nieodwracalne zmiany.",
                    f"Upewnij się, że {target} jest odpowiednio skonfigurowany.",
                ]
                if is_destructive else
                [f"Niski poziom ryzyka dla komendy: {description}."]
            ),
            reversible=not is_destructive,
            reversibility_note=(
                "Operacja NIEODWRACALNA — upewnij się przed zatwierdzeniem."
                if is_destructive else
                "Efekty komendy można cofnąć ręcznie jeśli potrzeba."
            ),
            estimated_time=ctx.get("estimated_time", "~5 sek"),
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="OSTROŻNOŚĆ" if is_destructive else "ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ODRZUĆ",
            icon="❌",
            will_happen=[
                "Komenda NIE zostanie wykonana.",
                f"Agent {agent} otrzyma informację o odrzuceniu.",
                "Agent może zaproponować alternatywne podejście.",
            ],
            wont_happen=[f"Brak zmian na: {target}."],
            risks=["Agent może nie móc kontynuować bez tej komendy."],
            reversible=True,
            reversibility_note="Możesz zatwierdzić komendę w kolejnej próbie.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        modify = self._make(
            decision="modify",
            label="MODYFIKUJ",
            icon="✏️",
            will_happen=[
                "Możesz zmienić parametry komendy przed wykonaniem.",
                f"Oryginalna komenda: {cmd}",
                "Zmodyfikowana wersja zostanie wykonana po zatwierdzeniu.",
            ],
            wont_happen=["Oryginalna komenda nie zostanie wykonana."],
            risks=["Nieprawidłowa modyfikacja może spowodować błąd lub szkodę."],
            reversible=True,
            reversibility_note="Możesz anulować modyfikację.",
            estimated_time="Twój czas + czas wykonania",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        return {"approve": approve, "reject": reject, "modify": modify}

    # ------------------------------------------------------------------ #
    # Handler: patch_application
    # ------------------------------------------------------------------ #

    def _patch_application(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        file_path = ctx.get("file_path", "<plik>")
        agent = ctx.get("agent_name", "patcher")
        patch_summary = ctx.get("patch_summary", "zmiana w kodzie")
        lines_changed = ctx.get("lines_changed", 0)
        test_required = ctx.get("test_required", True)

        approve = self._make(
            decision="approve",
            label="ZASTOSUJ PATCH",
            icon="✅",
            will_happen=[
                f"Patch zostanie zastosowany do pliku: {file_path}.",
                f"Zmiana: {patch_summary}.",
                f"Liczba zmienionych linii: {lines_changed}.",
                "Plik zostanie nadpisany nową wersją.",
                "Poprzednia wersja zapisana w backupie (jeśli skonfigurowano).",
                "Agenci audytu zweryfikują wynik w kolejnym etapie." if test_required else "",
            ],
            wont_happen=[],
            risks=[
                "Patch może wprowadzić nowe błędy (regresja).",
                "Jeśli testy nie są skonfigurowane, regresja może nie zostać wykryta.",
            ],
            reversible=True,
            reversibility_note="Przywróć backup lub użyj git checkout.",
            estimated_time="~10 sek",
            estimated_cost="$0.00",
            affected_agents=[agent, "auditor"],
            recommendation="ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ODRZUĆ PATCH",
            icon="❌",
            will_happen=[
                f"Plik {file_path} pozostanie bez zmian.",
                f"Finding powiązany z tym patchem zostanie oznaczony jako REJECTED.",
                "Agent może zaproponować alternatywny patch.",
            ],
            wont_happen=[f"Brak zmian w: {file_path}."],
            risks=["Podatność/błąd opisany w findingu pozostanie nienaprawiony."],
            reversible=True,
            reversibility_note="Możesz zatwierdzić patch lub inny fix w kolejnym przebiegu.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        modify = self._make(
            decision="modify",
            label="MODYFIKUJ PATCH",
            icon="✏️",
            will_happen=[
                "Możesz edytować diff przed zastosowaniem.",
                "Supervisor otworzy edytor z propozycją patcha.",
                "Zmodyfikowany patch zostanie zastosowany po zatwierdzeniu.",
            ],
            wont_happen=["Oryginalny patch nie zostanie zastosowany."],
            risks=["Ręczna modyfikacja diffa wymaga doświadczenia z formatem patch."],
            reversible=True,
            reversibility_note="Możesz anulować modyfikację.",
            estimated_time="Twój czas edycji",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        return {"approve": approve, "reject": reject, "modify": modify}

    # ------------------------------------------------------------------ #
    # Handler: device_deploy
    # ------------------------------------------------------------------ #

    def _device_deploy(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        device = ctx.get("device", "urządzenie")
        binary = ctx.get("binary", "<plik>")
        deploy_type = ctx.get("deploy_type", "deployment")
        agent = ctx.get("agent_name", "deployer")
        risk_level = ctx.get("risk_level", "medium")

        approve = self._make(
            decision="approve",
            label=f"WGRAJ NA {device.upper()}",
            icon="✅",
            will_happen=[
                f"Plik {binary} zostanie wgrany na: {device}.",
                f"Operacja: {deploy_type}.",
                "Urządzenie może wymagać restartu po wgraniu.",
                "Stan urządzenia po deployu zostanie zalogowany.",
            ],
            wont_happen=[],
            risks=(
                [
                    "WYSOKI POZIOM RYZYKA — operacja może zbrickować urządzenie.",
                    "Upewnij się, że masz kopię zapasową firmware/danych.",
                    "Operacja nieodwracalna bez ręcznej interwencji.",
                ]
                if risk_level == "high" else
                [
                    "Wgranie nieprawidłowego pliku może wymagać ręcznej naprawy urządzenia.",
                    "Sprawdź kompatybilność pliku z urządzeniem.",
                ]
            ),
            reversible=risk_level != "high",
            reversibility_note=(
                "NIEODWRACALNE bez narzędzi serwisowych."
                if risk_level == "high" else
                f"Poprzednią wersję można przywrócić przez ADB/SSH na {device}."
            ),
            estimated_time=ctx.get("estimated_time", "~2 min"),
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="OSTROŻNOŚĆ" if risk_level == "high" else "ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ANULUJ DEPLOY",
            icon="❌",
            will_happen=[
                f"Plik NIE zostanie wgrany na {device}.",
                "Urządzenie pozostanie w aktualnym stanie.",
                "Możesz wrócić do deployu gdy będziesz gotowy.",
            ],
            wont_happen=[f"Brak zmian na {device}."],
            risks=["Funkcja wymagająca nowego binaru nie będzie dostępna."],
            reversible=True,
            reversibility_note="Możesz wykonać deploy w dowolnym momencie.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        defer = self._make(
            decision="defer",
            label="ODŁÓŻ",
            icon="⏸️",
            will_happen=[
                f"Deploy na {device} zostanie wstrzymany.",
                "Pipeline kontynuuje inne etapy (jeśli są niezależne).",
                "Możesz wrócić do deployu później.",
            ],
            wont_happen=[f"Brak zmian na {device} w tym momencie."],
            risks=["Etapy zależne od tego deployu będą zablokowane."],
            reversible=True,
            reversibility_note="Wróć do decyzji gdy będziesz gotowy.",
            estimated_time="—",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        return {"approve": approve, "reject": reject, "defer": defer}

    # ------------------------------------------------------------------ #
    # Handler: sdr_operation
    # ------------------------------------------------------------------ #

    def _sdr_operation(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        test_name = ctx.get("test_name", "test SDR")
        frequency = ctx.get("frequency_mhz", "?")
        duration = ctx.get("duration_secs", 0.0)
        agent = ctx.get("agent_name", "sdr_agent")
        legal_note = ctx.get("legal_note", "")

        approve = self._make(
            decision="approve",
            label="URUCHOM TEST SDR",
            icon="✅",
            will_happen=[
                f"Test '{test_name}' zostanie uruchomiony.",
                f"Częstotliwość: {frequency} MHz.",
                f"Czas testu: {format_time(duration)}.",
                "Wyniki trafią do analizy agenta.",
                legal_note if legal_note else
                "Upewnij się, że emisja RF jest zgodna z lokalnym prawem.",
            ],
            wont_happen=[],
            risks=[
                "Emisja RF na nieautoryzowanych częstotliwościach jest nielegalna.",
                "Sprawdź regulacje ITU/UKE przed uruchomieniem.",
                "Test może zakłócać inne urządzenia w pobliżu.",
            ],
            reversible=True,
            reversibility_note="Test można przerwać w każdej chwili.",
            estimated_time=format_time(duration),
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="OSTROŻNOŚĆ",
        )

        reject = self._make(
            decision="reject",
            label="ANULUJ TEST",
            icon="❌",
            will_happen=[
                f"Test '{test_name}' NIE zostanie uruchomiony.",
                "Żadna emisja RF nie nastąpi.",
                "Agent SDR otrzyma informację o anulowaniu.",
            ],
            wont_happen=["Brak emisji RF."],
            risks=["Wyniki SDR dla tego testu nie będą dostępne."],
            reversible=True,
            reversibility_note="Możesz uruchomić test w dowolnym momencie.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        return {"approve": approve, "reject": reject}

    # ------------------------------------------------------------------ #
    # Handler: error_escalation
    # ------------------------------------------------------------------ #

    def _error_escalation(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        agent = ctx.get("agent_name", "Agent")
        error = ctx.get("error_summary", "błąd agenta")
        retry_count = ctx.get("retry_count", 0)
        max_retries = ctx.get("max_retries", 3)

        retry = self._make(
            decision="retry",
            label="SPRÓBUJ PONOWNIE",
            icon="🔄",
            will_happen=[
                f"Agent {agent} zostanie uruchomiony ponownie.",
                f"Próba {retry_count + 1}/{max_retries}.",
                "Supervisor przekaże agentowi pełny kontekst błędu.",
            ],
            wont_happen=[],
            risks=[
                "Jeśli błąd jest systemowy, ponowna próba może zakończyć się tak samo.",
                f"Pozostałe próby: {max_retries - retry_count - 1}.",
            ],
            reversible=True,
            reversibility_note="Możesz odrzucić wynik po ponownej próbie.",
            estimated_time=ctx.get("estimated_time", "~10 min"),
            estimated_cost=ctx.get("estimated_cost", "~$0.50"),
            affected_agents=[agent],
            recommendation="ZALECANE" if retry_count == 0 else "",
        )

        skip = self._make(
            decision="skip",
            label="POMIŃ AGENTA",
            icon="⏭️",
            will_happen=[
                f"Agent {agent} zostanie pominięty.",
                f"Błąd '{error}' zostanie zalogowany jako SKIPPED.",
                "Pipeline przejdzie do kolejnego agenta/etapu.",
            ],
            wont_happen=[f"Agent {agent} nie wykona swojego zadania."],
            risks=["Pominięcie może wpłynąć na kompletność wyników."],
            reversible=True,
            reversibility_note="Możesz uruchomić agenta osobno po naprawie błędu.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        escalate = self._make(
            decision="escalate",
            label="ESKALUJ DO NADZORU",
            icon="⚠️",
            will_happen=[
                "Pipeline zostanie wstrzymany.",
                "Supervisor wygeneruje pełny raport diagnostyczny.",
                "Czekam na Twoją decyzję z pełnym kontekstem.",
            ],
            wont_happen=["Pipeline nie ruszy bez Twojej decyzji."],
            risks=["Opóźnienie pipeline'u."],
            reversible=True,
            reversibility_note="Po analizie wybierz retry lub skip.",
            estimated_time="Twój czas analizy",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        return {"retry": retry, "skip": skip, "escalate": escalate}

    # ------------------------------------------------------------------ #
    # Handler: loop_detected
    # ------------------------------------------------------------------ #

    def _loop_detected(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        agent = ctx.get("agent_name", "patcher")
        file_path = ctx.get("file_path", "<plik>")
        iteration = ctx.get("iteration", 0)
        max_iter = ctx.get("max_iterations", 5)
        current_model = ctx.get("current_model", "claude")
        alternative_model = ctx.get("alternative_model", "gpt-4o")
        extra_iterations = ctx.get("extra_iterations", 3)
        loop_desc = ctx.get("loop_description", "Patch → Audyt → Nowy bug → Patch → …")

        force = self._make(
            decision="force_continue",
            label=f"WYMUŚ KONTYNUACJĘ (+{extra_iterations} iteracji)",
            icon="🔄",
            will_happen=[
                f"Limit iteracji zwiększony do {max_iter + extra_iterations}.",
                f"Agent {agent} spróbuje ponownie od iteracji {iteration + 1}.",
                f"Supervisor będzie monitorował kolejne próby.",
            ],
            wont_happen=[],
            risks=[
                f"Ryzyko: kontynuacja tej samej pętli ({loop_desc}).",
                "Dodatkowy koszt API za kolejne iteracje.",
                "Brak gwarancji przełamania pętli.",
            ],
            reversible=True,
            reversibility_note="Możesz przerwać w kolejnym Human Gate.",
            estimated_time=f"~{extra_iterations * 10} min",
            estimated_cost=f"~${extra_iterations * 0.50:.2f}",
            affected_agents=[agent, "auditor"],
            recommendation="OSTROŻNOŚĆ",
        )

        skip_file = self._make(
            decision="skip_file",
            label="POMIŃ TEN PLIK",
            icon="⏭️",
            will_happen=[
                f"Plik {file_path} pozostanie bez zmian.",
                f"Finding powiązany z plikiem oznaczony jako MANUAL_REVIEW.",
                "Pipeline przejdzie do następnego pliku/zadania.",
                "Raport będzie zawierał informację o pominiętym pliku.",
            ],
            wont_happen=[f"Brak dalszych prób naprawy {file_path}."],
            risks=[
                "Problem w pliku pozostanie nierozwiązany automatycznie.",
                "Wymaga ręcznej interwencji po zakończeniu pipeline'u.",
            ],
            reversible=True,
            reversibility_note="Możesz ręcznie naprawić plik po zakończeniu pipeline'u.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="ZALECANE",
        )

        manual = self._make(
            decision="manual_intervention",
            label="RĘCZNA INTERWENCJA",
            icon="👤",
            will_happen=[
                "Pipeline zostanie całkowicie wstrzymany.",
                "Pełny raport pętli (diff wszystkich iteracji) zostanie wyświetlony.",
                "Możesz ręcznie wprowadzić patch lub decyzję.",
                "Pipeline wznowi się po Twojej interwencji.",
            ],
            wont_happen=["Pipeline nie ruszy bez Twojej interwencji."],
            risks=["Opóźnienie pipeline'u o czas Twojej analizy."],
            reversible=True,
            reversibility_note="Ty decydujesz co dalej po analizie.",
            estimated_time="Twój czas",
            estimated_cost="$0.00",
            affected_agents=[agent],
            recommendation="",
        )

        switch_model = self._make(
            decision="switch_model",
            label=f"ZMIEŃ MODEL ({current_model} → {alternative_model})",
            icon="🔀",
            will_happen=[
                f"Agent zmieniony z {current_model} na {alternative_model}.",
                "Liczba iteracji resetowana do 0.",
                f"Plik {file_path} zostanie przeanalizowany od nowa.",
                "Świeża perspektywa może przełamać pętlę.",
            ],
            wont_happen=[],
            risks=[
                f"Model {alternative_model} może mieć inne problemy z tym plikiem.",
                "Reset iteracji = dodatkowy koszt API.",
            ],
            reversible=True,
            reversibility_note="Możesz wrócić do poprzedniego modelu.",
            estimated_time="~15 min",
            estimated_cost="~$0.80",
            affected_agents=[agent],
            recommendation="",
        )

        return {
            "force_continue": force,
            "skip_file": skip_file,
            "manual_intervention": manual,
            "switch_model": switch_model,
        }

    # ------------------------------------------------------------------ #
    # Handler: stage_summary
    # ------------------------------------------------------------------ #

    def _stage_summary(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        stage = ctx.get("stage", "?")
        findings = ctx.get("findings_count", 0)
        next_stage = ctx.get("next_stage", "kolejny etap")
        agents_involved = ctx.get("agents", [])

        approve = self._make(
            decision="approve",
            label=f"PRZEJDŹ DO: {next_stage.upper()}",
            icon="✅",
            will_happen=[
                f"Wyniki etapu {stage} zaakceptowane ({findings} findings).",
                f"Pipeline przejdzie do etapu: {next_stage}.",
                "Zatwierdzone wyniki zostaną użyte jako wejście dla kolejnych agentów.",
            ],
            wont_happen=[],
            risks=["Jeśli wyniki zawierają błędy, przeniosą się do kolejnych etapów."],
            reversible=False,
            reversibility_note="Po przejściu do kolejnego etapu powrót wymaga ręcznego restartu.",
            estimated_time="~1 min",
            estimated_cost="$0.00",
            affected_agents=agents_involved,
            recommendation="ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ODRZUĆ WYNIKI ETAPU",
            icon="❌",
            will_happen=[
                f"Wyniki etapu {stage} odrzucone.",
                "Pipeline nie przejdzie do kolejnego etapu.",
                "Możesz powtórzyć etap z innymi parametrami.",
            ],
            wont_happen=[f"Etap {next_stage} nie zostanie uruchomiony."],
            risks=["Powtórzenie etapu oznacza dodatkowy koszt API."],
            reversible=True,
            reversibility_note="Możesz zatwierdzić wyniki po ręcznej analizie.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=agents_involved,
            recommendation="",
        )

        return {"approve": approve, "reject": reject}

    # ------------------------------------------------------------------ #
    # Handler: pipeline_results
    # ------------------------------------------------------------------ #

    def _pipeline_results(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        total_findings = ctx.get("total_findings", 0)
        report_path = ctx.get("report_path", "results/final_report.json")
        agents = ctx.get("agents", [])
        patches_applied = ctx.get("patches_applied", 0)

        accept = self._make(
            decision="accept",
            label="ZAAKCEPTUJ WYNIKI",
            icon="✅",
            will_happen=[
                f"Finalne wyniki ({total_findings} findings) zaakceptowane.",
                f"Raport zapisany w: {report_path}.",
                f"Zastosowane patche: {patches_applied}.",
                "Pipeline zakończy się sukcesem.",
                "Wyniki dostępne do eksportu/dalszego przetwarzania.",
            ],
            wont_happen=[],
            risks=["Upewnij się, że wszystkie krytyczne findings zostały zaadresowane."],
            reversible=True,
            reversibility_note="Możesz uruchomić pipeline ponownie z nowymi parametrami.",
            estimated_time="~1 min",
            estimated_cost="$0.00",
            affected_agents=agents,
            recommendation="ZALECANE",
        )

        reject = self._make(
            decision="reject",
            label="ODRZUĆ — URUCHOM PONOWNIE",
            icon="❌",
            will_happen=[
                "Wyniki finalne odrzucone.",
                "Pipeline może zostać uruchomiony ponownie z poprawioną konfiguracją.",
                "Poprzednie wyniki zostaną zachowane jako archiwum.",
            ],
            wont_happen=["Raport nie zostanie oznaczony jako finalny."],
            risks=["Ponowne uruchomienie pipeline'u = pełny koszt API."],
            reversible=True,
            reversibility_note="Poprzedni raport jest dostępny w archiwum.",
            estimated_time="~0 sek",
            estimated_cost="$0.00",
            affected_agents=agents,
            recommendation="",
        )

        return {"accept": accept, "reject": reject}

    # ------------------------------------------------------------------ #
    # Generic fallback handler
    # ------------------------------------------------------------------ #

    def _generic(self, ctx: dict) -> dict[str, ConsequenceInfo]:
        agent = ctx.get("agent_name", "Agent")
        title = ctx.get("title", "akcja")

        approve = self._make(
            decision="approve",
            label="ZATWIERDŹ",
            icon="✅",
            will_happen=[f"Akcja '{title}' zostanie wykonana.", "Wynik przekazany do agenta."],
            wont_happen=[],
            risks=["Sprawdź szczegóły akcji przed zatwierdzeniem."],
            reversible=True,
            reversibility_note="Zależy od rodzaju akcji.",
            affected_agents=[agent],
            recommendation="",
        )

        reject = self._make(
            decision="reject",
            label="ODRZUĆ",
            icon="❌",
            will_happen=[f"Akcja '{title}' NIE zostanie wykonana.", "Agent otrzyma informację."],
            wont_happen=[f"'{title}' nie nastąpi."],
            risks=[],
            reversible=True,
            reversibility_note="Możesz zatwierdzić ponownie.",
            affected_agents=[agent],
            recommendation="",
        )

        return {"approve": approve, "reject": reject}

    # ------------------------------------------------------------------ #
    # Dispatch table — maps action_type → handler method
    # ------------------------------------------------------------------ #

    _HANDLERS: dict[str, Any] = {
        "pipeline_start":    _pipeline_start,
        "agent_run":         _agent_run,
        "command_execution": _command_execution,
        "stage_summary":     _stage_summary,
        "patch_application": _patch_application,
        "device_deploy":     _device_deploy,
        "sdr_operation":     _sdr_operation,
        "error_escalation":  _error_escalation,
        "loop_detected":     _loop_detected,
        "pipeline_results":  _pipeline_results,
    }


# ---------------------------------------------------------------------------
# EnhancedDisplay — Rich CLI display with consequences
# ---------------------------------------------------------------------------

class EnhancedDisplay:
    """Enhanced terminal display for Human Gate decisions.

    Shows each option with its full consequences so the admin
    can make an informed decision.
    """

    # Width of the outer border
    _WIDTH = 62

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def display_decision_menu(
        self,
        consequences: dict[str, ConsequenceInfo],
        gate_level: str,
        header: dict[str, str] | None = None,
    ) -> None:
        """Print the full decision menu with consequences for each option.

        Parameters
        ----------
        consequences:
            Mapping of decision key → ConsequenceInfo (from ConsequenceDescriptor).
        gate_level:
            One of "info", "review", "required", "critical".
        header:
            Optional dict with keys: agent, stage, title, icon.
        """
        self._print_header(gate_level, header or {})
        self._print_section_separator("OPCJE — SKUTKI KAŻDEJ DECYZJI:")
        for info in consequences.values():
            self._print_option_block(info)
        self._print_footer()

    def display_consequence_detail(self, info: ConsequenceInfo) -> None:
        """Print a detailed view of a single ConsequenceInfo."""
        w = self._WIDTH
        print()
        print(f"{C.BOLD}{C.CYAN}{'═' * w}{C.RESET}")
        label = f"  {info.icon}  {info.label}"
        rec = self._recommendation_badge(info.recommendation)
        print(f"{C.BOLD}{label}  {rec}{C.RESET}")
        print(f"{C.CYAN}{'═' * w}{C.RESET}")

        self._print_detail_section("Co się stanie:", info.will_happen, C.GREEN)
        if info.wont_happen:
            self._print_detail_section("Co NIE nastąpi:", info.wont_happen, C.BLUE)
        if info.risks:
            self._print_detail_section("Ryzyka:", info.risks, C.YELLOW)

        print(f"\n  {C.BOLD}Szczegóły:{C.RESET}")
        rev_str = "TAK" if info.reversible else "NIE"
        rev_color = C.GREEN if info.reversible else C.RED
        print(f"    Odwracalność  : {rev_color}{rev_str}{C.RESET} — {info.reversibility_note}")
        if info.estimated_time:
            print(f"    Szac. czas    : {C.CYAN}{info.estimated_time}{C.RESET}")
        if info.estimated_cost:
            print(f"    Szac. koszt   : {C.CYAN}{info.estimated_cost}{C.RESET}")
        if info.affected_agents:
            # Defensive: coerce to list of strings if scalar was passed
            agents = info.affected_agents if isinstance(info.affected_agents, (list, tuple)) else [str(info.affected_agents)]
            agents_str = ", ".join(str(a) for a in agents)
            print(f"    Agenci        : {C.DIM}{agents_str}{C.RESET}")
        print(f"{C.CYAN}{'─' * w}{C.RESET}")

    def display_comparison(self, options: list[ConsequenceInfo]) -> None:
        """Print a side-by-side comparison table of multiple options.

        For terminals that are wide enough (>=120 chars), shows columns;
        otherwise falls back to a sequential summary.
        """
        print()
        print(f"{C.BOLD}{C.CYAN}  PORÓWNANIE OPCJI{C.RESET}")
        print(f"{C.CYAN}{'─' * self._WIDTH}{C.RESET}")

        # Header row
        col_width = max(18, self._WIDTH // max(len(options), 1) - 2)
        header_parts = [
            f"{C.BOLD}{info.icon} {info.label[:col_width - 3]:<{col_width}}{C.RESET}"
            for info in options
        ]
        print("  " + "  |  ".join(header_parts))
        print(f"{'─' * self._WIDTH}")

        # Row: reversible
        rev_parts = []
        for info in options:
            rev_text = "Odwracalne: TAK" if info.reversible else "Odwracalne: NIE"
            color = C.GREEN if info.reversible else C.RED
            rev_parts.append(f"{color}{rev_text:<{col_width}}{C.RESET}")
        print("  " + "  |  ".join(rev_parts))

        # Row: cost
        cost_parts = [
            f"{C.CYAN}Koszt: {info.estimated_cost:<{col_width - 7}}{C.RESET}"
            for info in options
        ]
        print("  " + "  |  ".join(cost_parts))

        # Row: time
        time_parts = [
            f"{C.CYAN}Czas:  {info.estimated_time:<{col_width - 7}}{C.RESET}"
            for info in options
        ]
        print("  " + "  |  ".join(time_parts))

        # Row: recommendation
        rec_parts = []
        for info in options:
            badge = self._recommendation_badge(info.recommendation)
            rec_parts.append(f"{badge:<{col_width}}")
        print("  " + "  |  ".join(rec_parts))

        print(f"{C.CYAN}{'─' * self._WIDTH}{C.RESET}")

    # ------------------------------------------------------------------ #
    # Internal rendering helpers
    # ------------------------------------------------------------------ #

    def _print_header(self, gate_level: str, header: dict) -> None:
        """Print the top banner with gate level, agent, stage, title."""
        w = self._WIDTH
        level_colors = {
            "info":     C.BLUE,
            "review":   C.YELLOW,
            "required": f"{C.BOLD}{C.YELLOW}",
            "critical": f"{C.BOLD}{C.RED}",
        }
        level_icons = {
            "info":     "ℹ️ ",
            "review":   "👁️ ",
            "required": "🔒",
            "critical": "🚨",
        }
        level_labels = {
            "info":     "INFORMACJA",
            "review":   "PRZEGLĄD",
            "required": "WYMAGANE",
            "critical": "KRYTYCZNE",
        }

        color = level_colors.get(gate_level, C.WHITE)
        icon = level_icons.get(gate_level, "🔒")
        label = level_labels.get(gate_level, gate_level.upper())

        print()
        print(f"{color}{'═' * w}{C.RESET}")
        gate_line = f"  {icon} HUMAN GATE — {label}"
        print(f"{C.BOLD}{color}{gate_line}{C.RESET}")
        print(f"{color}{'═' * w}{C.RESET}")

        if header.get("agent"):
            print(f"  {C.DIM}Agent:{C.RESET}  {C.BOLD}{header['agent']}{C.RESET}")
        if header.get("stage"):
            print(f"  {C.DIM}Etap:{C.RESET}   {header['stage']}")
        if header.get("title"):
            print(f"  {C.DIM}Tytuł:{C.RESET}  {C.BOLD}{header['title']}{C.RESET}")
        if header:
            print()

    def _print_section_separator(self, title: str) -> None:
        w = self._WIDTH
        print(f"{C.DIM}{'─' * w}{C.RESET}")
        print(f"  {C.BOLD}{title}{C.RESET}")
        print(f"{C.DIM}{'─' * w}{C.RESET}")

    def _print_footer(self) -> None:
        w = self._WIDTH
        print(f"{C.DIM}{'─' * w}{C.RESET}")

    def _print_option_block(self, info: ConsequenceInfo) -> None:
        """Print a single option block with box-drawing characters."""
        # Key letter: first char of decision, uppercase
        key = info.decision[0].upper()

        # Recommendation badge
        rec_badge = self._recommendation_badge(info.recommendation)
        rec_suffix = f"  {rec_badge}" if info.recommendation else ""

        # Option header line
        label_color = self._option_color(info.recommendation, info.decision)
        print(f"\n  [{C.BOLD}{key}{C.RESET}] {label_color}{info.icon}  {info.label}{C.RESET}{rec_suffix}")

        # Box with details
        lines: list[str] = []

        # What will happen
        if info.will_happen:
            lines.append(f"{C.GREEN}Co się stanie:{C.RESET}")
            for item in info.will_happen:
                if item:
                    lines.append(f"   {C.DIM}•{C.RESET} {item}")

        # Time and cost on one line if available
        meta_parts = []
        if info.estimated_time:
            meta_parts.append(f"Czas: {C.CYAN}{info.estimated_time}{C.RESET}")
        if info.estimated_cost:
            meta_parts.append(f"Koszt: {C.CYAN}{info.estimated_cost}{C.RESET}")
        if meta_parts:
            lines.append(f"   {C.DIM}→{C.RESET} " + "  |  ".join(meta_parts))

        # What won't happen
        if info.wont_happen:
            lines.append("")
            lines.append(f"{C.BLUE}Nie nastąpi:{C.RESET}")
            for item in info.wont_happen:
                if item:
                    lines.append(f"   {C.DIM}•{C.RESET} {C.DIM}{item}{C.RESET}")

        # Risks
        if info.risks:
            lines.append("")
            lines.append(f"{C.YELLOW}Ryzyka:{C.RESET}")
            for risk in info.risks:
                if risk:
                    lines.append(f"   {C.YELLOW}!{C.RESET} {risk}")

        # Reversibility
        rev_label = "TAK" if info.reversible else "NIE"
        rev_color = C.GREEN if info.reversible else C.RED
        rev_line = f"Odwracalność: {rev_color}{rev_label}{C.RESET}"
        if info.reversibility_note:
            rev_line += f" — {C.DIM}{info.reversibility_note}{C.RESET}"
        lines.append("")
        lines.append(rev_line)

        # Affected agents
        if info.affected_agents:
            # Defensive: coerce to list of strings if scalar was passed
            agents = info.affected_agents if isinstance(info.affected_agents, (list, tuple)) else [str(info.affected_agents)]
            lines.append(
                f"{C.DIM}Agenci: {', '.join(str(a) for a in agents)}{C.RESET}"
            )

        # Render with box-drawing
        for i, line in enumerate(lines):
            is_last = (i == len(lines) - 1)
            prefix = "      └ " if is_last else "      │ "
            if line == "":
                print(f"      │")
            else:
                print(f"{prefix}{line}")
        # Opening brace on first line, closing on last — done above implicitly;
        # print the top border before the first line:
        if lines:
            pass  # border is handled by prefix logic above

        # Print opening ┌ before the block (retrospectively not possible —
        # instead we use │ on all lines for a clean look, which matches
        # the spec example style).

    def _recommendation_badge(self, recommendation: str) -> str:
        """Return a coloured badge string for a recommendation level."""
        badges = {
            "ZALECANE":     f"{C.BG_GREEN}{C.BOLD} ZALECANE {C.RESET}",
            "OSTROŻNOŚĆ":   f"{C.BG_YELLOW}{C.BOLD} OSTROŻNOŚĆ {C.RESET}",
            "NIEBEZPIECZNE": f"{C.BG_RED}{C.BOLD} NIEBEZPIECZNE {C.RESET}",
        }
        return badges.get(recommendation, "")

    def _option_color(self, recommendation: str, decision: str) -> str:
        """Return ANSI color for the option label based on recommendation."""
        if recommendation == "NIEBEZPIECZNE":
            return f"{C.BOLD}{C.RED}"
        if recommendation == "OSTROŻNOŚĆ":
            return f"{C.BOLD}{C.YELLOW}"
        if recommendation == "ZALECANE":
            return f"{C.BOLD}{C.GREEN}"
        if decision in ("reject", "skip", "skip_file"):
            return C.RED
        if decision in ("defer", "deferred"):
            return C.BLUE
        if decision in ("escalate", "escalated", "escalation"):
            return C.MAGENTA
        return C.WHITE

    def _print_detail_section(
        self, title: str, items: list[str], color: str
    ) -> None:
        """Print a titled bullet list with colour."""
        print(f"\n  {C.BOLD}{color}{title}{C.RESET}")
        for item in items:
            if item:
                wrapped = textwrap.fill(
                    item, width=58,
                    initial_indent="    • ",
                    subsequent_indent="      ",
                )
                print(wrapped)


# ---------------------------------------------------------------------------
# LoopConsequences — Specialised loop-guard menu
# ---------------------------------------------------------------------------

class LoopConsequences:
    """Generates and displays the specialised Human Gate for loop detection.

    When the loop guard triggers (patcher iterating on the same file without
    making progress), this class provides the four specialised options with
    their full consequence descriptions.
    """

    def __init__(self) -> None:
        self._descriptor = ConsequenceDescriptor()
        self._display = EnhancedDisplay()

    def show_loop_menu(self, ctx: dict) -> None:
        """Display the full loop-detection Human Gate menu.

        Parameters
        ----------
        ctx:
            Context dict with keys:
            - agent_name, file_path, iteration, max_iterations,
              current_model, alternative_model, loop_description,
              extra_iterations (optional, default 3)
        """
        agent = ctx.get("agent_name", "patcher")
        file_path = ctx.get("file_path", "<plik>")
        iteration = ctx.get("iteration", 0)
        max_iter = ctx.get("max_iterations", 5)
        loop_desc = ctx.get("loop_description", "Patch → Audyt → Nowy bug → Patch → …")

        # Print banner
        w = 62
        print()
        print(f"{C.BG_RED}{C.BOLD}{'═' * w}{C.RESET}")
        print(f"{C.BG_RED}{C.BOLD}  ⚠️   WYKRYTO PĘTLĘ POPRAWEK!{' ' * (w - 30)}{C.RESET}")
        print(f"{C.BG_RED}{C.BOLD}{'═' * w}{C.RESET}")
        print()
        print(f"  {C.DIM}Agent:{C.RESET}    {C.BOLD}{agent}{C.RESET}")
        print(f"  {C.DIM}Plik:{C.RESET}     {C.BOLD}{file_path}{C.RESET}")
        print(f"  {C.DIM}Iteracja:{C.RESET} {C.RED}{C.BOLD}{iteration}/{max_iter} (LIMIT){C.RESET}")
        print()
        print(f"  {C.DIM}Pętla:{C.RESET}    {C.YELLOW}{loop_desc}{C.RESET}")

        # Get consequences and display
        consequences = self._descriptor.describe_consequences("loop_detected", ctx)
        self._display._print_section_separator("OPCJE WYJŚCIA Z PĘTLI:")
        for info in consequences.values():
            self._display._print_option_block(info)
        self._display._print_footer()


# ---------------------------------------------------------------------------
# Convenience factory — build EnhancedDisplay + ConsequenceDescriptor together
# ---------------------------------------------------------------------------

def build_gate_ux() -> tuple[ConsequenceDescriptor, EnhancedDisplay]:
    """Return a ready-to-use (ConsequenceDescriptor, EnhancedDisplay) pair."""
    return ConsequenceDescriptor(), EnhancedDisplay()


# ---------------------------------------------------------------------------
# Quick smoke-test — run this file directly to preview the output
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    descriptor, display = build_gate_ux()

    # --- Example 1: agent_run ---
    ctx_agent = {
        "agent_name": "Auditor [claude]",
        "model": "claude-3-5-sonnet",
        "stage": "Stage 2 — AUDIT",
        "title": "Uruchomienie audytu bezpieczeństwa",
        "num_files": 847,
        "cost_est": 1.20,
        "time_est_secs": 900,
        "output_path": "results/stage2_audit/audit_claude.json",
        "total_agents_in_stage": 4,
        "consensus_threshold": "3/4 = ACCEPT",
    }
    consequences = descriptor.describe_consequences("agent_run", ctx_agent)
    display.display_decision_menu(
        consequences,
        gate_level="required",
        header={
            "agent": "Auditor [claude]",
            "stage": "Stage 2 — AUDIT",
            "title": "Uruchomienie audytu bezpieczeństwa",
        },
    )

    input(f"\n  {C.DIM}[Naciśnij Enter aby zobaczyć przykład pętli…]{C.RESET}")

    # --- Example 2: loop_detected ---
    loop_ctx = {
        "agent_name": "patcher_1 [claude]",
        "file_path": "internal/api/auth.go",
        "iteration": 5,
        "max_iterations": 5,
        "current_model": "claude",
        "alternative_model": "gpt-4o",
        "loop_description": "Patch → Audyt → Nowy bug → Patch → Audyt → …",
        "extra_iterations": 3,
    }
    loop = LoopConsequences()
    loop.show_loop_menu(loop_ctx)

    input(f"\n  {C.DIM}[Naciśnij Enter aby zobaczyć szczegóły opcji…]{C.RESET}")

    # --- Example 3: detail view ---
    first_option = next(iter(consequences.values()))
    display.display_consequence_detail(first_option)

    input(f"\n  {C.DIM}[Naciśnij Enter aby zobaczyć porównanie…]{C.RESET}")

    # --- Example 4: comparison ---
    display.display_comparison(list(consequences.values()))

    # --- Helper demos ---
    print(f"\n  format_time demos:")
    for s in [30, 90, 600, 3661]:
        print(f"    {s}s → {format_time(s)}")

    print(f"\n  format_cost demos:")
    for d in [0.0, 0.5, 1.234, 10.99]:
        print(f"    ${d} → {format_cost(d)}")
