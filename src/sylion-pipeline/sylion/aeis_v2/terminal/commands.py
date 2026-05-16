"""W18 Terminal — command palette parser.

PDF §7.2 wymienia kanoniczny zestaw slash-commands:

    /status, /cost, /agents, /skip, /focus, /explain, /findings, /retry,
    /diff, /budget, /priority, /export, /report, /help
    /host {name}        — drill into specific host
    /model {name}       — drill into specific model usage
    /replay {session_id} — odtworzenie historycznej sesji jak film
    /diff sessions {id1} {id2} — porównanie sesji

Phase 0 implementuje parser (rozkład tekstu na (cmd, args) + walidacja
wymaganych argumentów) oraz 4 z 14 commands wykonują realne akcje
(``/status``, ``/help``, ``/agents``, ``/cost``). Reszta zwraca
not-implemented z hintem co ma robić w G2/G3.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

log = logging.getLogger(__name__)

# Pattern to redact common secret shapes from error messages.
# Covers: scheme://... URIs (incl. postgres, redis, http, bolt, file),
# emails, OpenAI-style sk-... keys, and Bearer tokens.
_SECRET_RE = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://[^\s]+)"                      # any scheme://...
    r"|(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"  # email
    r"|(?:sk-[a-zA-Z0-9_-]+)"                                # OpenAI-style keys
    r"|(?:Bearer\s+[a-zA-Z0-9._-]+)",                        # bearer tokens
    re.IGNORECASE,
)


def _sanitize_error_text(text: str) -> str:
    """Replace likely-secret tokens with ``<redacted>``.

    Used by :func:`parse_command` to prevent exception stringification from
    leaking credentials, URLs, or API keys into the operator UI. Returns a
    single-line message capped at 200 characters.
    """
    if not text:
        return text
    # First line only (avoid leaking traceback structure).
    first_line = text.splitlines()[0] if "\n" in text else text
    # Truncate to 200 chars before regex substitution.
    truncated = first_line[:200]
    return _SECRET_RE.sub("<redacted>", truncated)

# --------------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------------


@dataclass
class CommandResult:
    """Wynik wykonania komendy.

    UI renderuje na podstawie ``kind``:
    - ``text``: zwykły output, pole `text`.
    - ``table``: lista wierszy w `rows`, opcjonalnie `headers`.
    - ``error``: czerwony błąd, `text`.
    - ``redirect``: nakaz zmiany widoku, `target` (URL lub session_id).
    - ``not_implemented``: feature flag, `text` z hint co planowane.
    """

    kind: str               # text / table / error / redirect / not_implemented
    text: str = ""
    rows: list[dict[str, Any]] | None = None
    headers: list[str] | None = None
    target: str | None = None
    meta: dict[str, Any] | None = None


# --------------------------------------------------------------------------
# Command registry
# --------------------------------------------------------------------------

CommandHandler = Callable[[list[str], Mapping[str, Any]], CommandResult]


@dataclass
class CommandSpec:
    name: str                      # kanoniczna nazwa, bez slash'a
    summary_pl: str
    summary_en: str
    args: str = ""                 # przykładowe argumenty dla /help
    handler: CommandHandler | None = None
    aliases: tuple[str, ...] = ()

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases


# Tymczasowe handlery — Phase 0. Każdy używa ``ctx`` aby dostać dostęp do
# stanu (session_store, registry, advisor itd.). W G3 podzielimy je do
# osobnych modułów ``commands/<name>.py``.

def _h_status(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): real /status output.

    Aggregates live signals from:
      * health/v2 — services up/down + audit chain integrity
      * W18 SessionStore — active terminal sessions count
      * HumanGate — pending tickets count
      * ProjectModeStore — projects grouped by phase

    Phase 0 returned a hard-coded skeleton string. Phase 1 returns real
    metrics so /status answers "is the system healthy *right now*".
    """
    lines: list[str] = ["SYLION AEIS v2 — status systemu"]

    # Health (services + audit chain integrity)
    services_up = 0
    services_total = 0
    chains_clean = 0
    chains_total = 0
    try:
        from sylion.api.health_v2_routes import assemble_health
        h = assemble_health()
        services = h.get("services") or {}
        services_total = len(services)
        services_up = sum(1 for v in services.values() if v in {"up", "ok", True})
        chains = h.get("audit_chains") or {}
        chains_total = len(chains)
        chains_clean = sum(
            1 for v in chains.values() if v in {"clean", "ok", "present", "idle", True}
        )
        chains_present = sum(1 for v in chains.values() if v in {"clean", "ok", "present", True})
        chains_idle = sum(1 for v in chains.values() if v == "idle")
        chains_bad = max(0, chains_total - chains_clean)
        lines.append(
            f"  services    : {services_up}/{services_total} up "
            f"(status={h.get('status', 'unknown')})"
        )
        lines.append(
            f"  audit_chain : {chains_clean}/{chains_total} ok "
            f"(present={chains_present}, idle={chains_idle}, bad={chains_bad})"
        )
    except Exception as exc:
        lines.append(f"  services    : unavailable ({type(exc).__name__})")
        lines.append("  audit_chain : unavailable")

    # Terminal sessions
    try:
        from sylion.aeis_v2.terminal import get_session_store
        store = get_session_store()
        active_sessions = len(store.list_active())
        total_sessions = len(store.list_all())
        lines.append(
            f"  sessions    : {active_sessions} active / {total_sessions} total"
        )
    except Exception as exc:
        lines.append(f"  sessions    : unavailable ({type(exc).__name__})")
        active_sessions, total_sessions = 0, 0

    # Pending HG tickets
    pending_tickets = 0
    try:
        from sylion.governance.human_gate import get_human_gate
        hg = get_human_gate()
        pending_tickets = len(hg.list_requests(status="pending"))
        lines.append(f"  hg_tickets  : {pending_tickets} pending")
    except Exception as exc:
        lines.append(f"  hg_tickets  : unavailable ({type(exc).__name__})")

    # Projects by phase
    projects_by_phase: dict[str, int] = {}
    projects_total = 0
    try:
        from sylion.project_mode.store import get_project_mode_store
        ps = get_project_mode_store()
        projects = ps.list_projects()
        projects_total = len(projects)
        for p in projects:
            ph = (p.get("phase") or "unknown") or "unknown"
            projects_by_phase[ph] = projects_by_phase.get(ph, 0) + 1
        if projects_by_phase:
            phases_str = ", ".join(
                f"{k}={v}" for k, v in sorted(projects_by_phase.items())
            )
            lines.append(f"  projects    : {projects_total} ({phases_str})")
        else:
            lines.append(f"  projects    : {projects_total}")
    except Exception as exc:
        lines.append(f"  projects    : unavailable ({type(exc).__name__})")

    return CommandResult(
        kind="text",
        text="\n".join(lines),
        meta={
            "services_up": services_up,
            "services_total": services_total,
            "audit_chain_clean": chains_clean,
            "audit_chain_total": chains_total,
            "active_sessions": active_sessions,
            "total_sessions": total_sessions,
            "pending_hg_tickets": pending_tickets,
            "projects_total": projects_total,
            "projects_by_phase": projects_by_phase,
        },
    )


def _h_help(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    rows = [
        {
            "command": "/" + spec.name,
            "args": spec.args,
            "summary_pl": spec.summary_pl,
            "summary_en": spec.summary_en,
        }
        for spec in BUILTIN_COMMANDS
    ]
    return CommandResult(
        kind="table",
        headers=["command", "args", "summary_pl", "summary_en"],
        rows=rows,
        text=f"{len(rows)} comendy dostepne.",
    )


def _h_agents(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): listuje 9 kanonicznych ról rady + ich domyślne wagi.

    Phase 0 pokazywało providerów (claude/gpt/ollama). Phase 1 zmienia
    semantykę na "agenci rady": 9 ról kanonicznych z council_hybrid
    (planner/architect/critic/verifier/governance/cost_sentinel/
    security_sentinel/domain_specialist/funding_specialist) + ich wagi
    głosu i mnożniki rang. To jest faktycznie to czego operator
    potrzebuje sprawdzając "kto bierze udział w decyzji".
    """
    try:
        from sylion.governance.council_hybrid import (
            VALID_ROLES, DEFAULT_ROLE_WEIGHTS, SENTINEL_ROLES,
        )
    except Exception as exc:
        return CommandResult(kind="error", text=f"failed to import council roles: {exc}")
    rows = []
    for role in VALID_ROLES:
        rows.append({
            "role": role,
            "default_weight": f"{DEFAULT_ROLE_WEIGHTS.get(role, 1.0):.2f}",
            "is_sentinel": "yes" if role in SENTINEL_ROLES else "no",
        })
    return CommandResult(
        kind="table",
        headers=["role", "default_weight", "is_sentinel"],
        rows=rows,
        text=(
            f"{len(rows)} kanonicznych ról rady modeli "
            f"({len(SENTINEL_ROLES)} sentineli)."
        ),
        meta={
            "roles": list(VALID_ROLES),
            "sentinel_roles": list(SENTINEL_ROLES),
            "weights": dict(DEFAULT_ROLE_WEIGHTS),
        },
    )


def _h_cost(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): real /cost output.

    Liczy:
      * Wydatki dzisiaj (od północy UTC) sumarycznie i per-provider.
      * Wydatki bieżącego miesiąca + procent wykorzystania capa
        (jeśli W6 budget envelope jest skonfigurowany).
    Źródło: ``logs/v2/cost_ledger.jsonl`` (aeis_v2.deployment.cost_ledger).
    """
    import time as _time
    from datetime import datetime as _dt, timezone as _tz

    try:
        from sylion.aeis_v2.deployment.cost_ledger import (
            aggregate_cost_by, query_cost_jsonl,
        )
    except Exception as exc:
        return CommandResult(kind="error", text=f"cost_ledger unavailable: {exc}")

    now = _time.time()
    today_start = _dt.now(_tz.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).timestamp()
    month_start = _dt.now(_tz.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).timestamp()

    # Dzisiaj — sumaryczne i per-model
    today_rows = query_cost_jsonl(since_ts=today_start, until_ts=now)
    today_total = sum(r.cost_usd for r in today_rows)
    today_by_model = aggregate_cost_by(
        since_ts=today_start, until_ts=now, group_by="model"
    )

    # Miesiąc
    month_rows = query_cost_jsonl(since_ts=month_start, until_ts=now)
    month_total = sum(r.cost_usd for r in month_rows)

    # Cap miesięczny (best-effort z W6 budget envelope)
    monthly_cap_usd: float | None = None
    cap_progress_pct: float | None = None
    try:
        from sylion.monitoring.cost_envelope import get_cost_envelope
        env = get_cost_envelope()
        records = env.list_records()
        # Wybierz record z monthly_cap_usd > 0
        for rec in records:
            cap = rec.get("monthly_cap_usd") or rec.get("cap_usd")
            if cap and float(cap) > 0:
                monthly_cap_usd = float(cap)
                break
        if monthly_cap_usd:
            cap_progress_pct = (month_total / monthly_cap_usd) * 100.0
    except Exception:
        # Brak modułu / brak rekordu — pomijamy (operator zobaczy "—")
        pass

    lines: list[str] = ["SYLION AEIS v2 — koszty"]
    lines.append(f"  dzisiaj_total : ${today_total:.4f}")
    lines.append(f"  liczba_calli  : {len(today_rows)}")
    if today_by_model:
        lines.append("  per-model dzisiaj:")
        for model, agg in sorted(today_by_model.items()):
            lines.append(
                f"    - {model or '<empty>'}: ${agg['total_usd']:.4f} "
                f"({int(agg['call_count'])} call)"
            )
    lines.append(f"  miesiac_total : ${month_total:.4f}")
    if monthly_cap_usd is not None:
        lines.append(
            f"  monthly_cap   : ${monthly_cap_usd:.2f} "
            f"(zuzycie {cap_progress_pct:.1f}%)"
        )
    else:
        lines.append("  monthly_cap   : (brak konfiguracji — set in W6)")

    return CommandResult(
        kind="text",
        text="\n".join(lines),
        meta={
            "today_total_usd": today_total,
            "today_call_count": len(today_rows),
            "today_by_model": today_by_model,
            "month_total_usd": month_total,
            "monthly_cap_usd": monthly_cap_usd,
            "cap_progress_pct": cap_progress_pct,
        },
    )


def _h_replay(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    if not args:
        return CommandResult(kind="error", text="usage: /replay <session_id>")
    session_id = args[0]
    return CommandResult(
        kind="not_implemented",
        text=(
            f"G3: odtworzy sesje {session_id} step-by-step jak film "
            "(append-only event log + hash chain).\n"
            "Phase 0: GET /api/v1/terminal/sessions/{session_id} zwroci "
            "metadata sesji bez full replay."
        ),
        target=session_id,
    )


def _h_focus(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    if not args:
        return CommandResult(
            kind="error",
            text="usage: /focus <session_id> | /focus host <name> | /focus model <name>",
        )
    scope = "session"
    target = args[0]
    if args[0] in {"host", "model"} and len(args) >= 2:
        scope = args[0]
        target = args[1]
    return CommandResult(
        kind="text",
        text=f"Focus W18 ustawiony: {scope}={target}.",
        meta={"scope": scope, "target": target, "args": args},
    )


def _h_diff(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    if len(args) >= 3 and args[0] == "sessions":
        return CommandResult(
            kind="not_implemented",
            text=f"G3: porowna sesje {args[1]} vs {args[2]} (event-by-event diff).",
            meta={"a": args[1], "b": args[2]},
        )
    return CommandResult(kind="error", text="usage: /diff sessions <id1> <id2>")


def _h_skip(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    session_id = str(ctx.get("session_id") or "")
    task_id = args[0] if args else str(ctx.get("task_id") or "")
    if not session_id:
        return CommandResult(
            kind="error",
            text="usage: /skip <task_id> with ctx.session_id, or set active terminal session first.",
        )
    try:
        from sylion.aeis_v2.terminal import get_session_store

        store = get_session_store()
        session = store.get(session_id)
        if session is None:
            return CommandResult(kind="error", text=f"Session not found: {session_id}")
        if not task_id:
            current_idx = session.current_task_idx
            if current_idx is None or current_idx >= len(session.tasks):
                return CommandResult(kind="error", text="No current task to skip.")
            task_id = session.tasks[current_idx].task_id
        task = next((task for task in session.tasks if task.task_id == task_id), None)
        if task is None:
            return CommandResult(kind="error", text=f"Task not found: {task_id}")
        before = task.status
        ok = store.update_task(session_id, task_id, status="skipped", progress=1.0)
        if not ok:
            return CommandResult(kind="error", text=f"Could not skip task: {task_id}")
    except Exception as exc:
        return CommandResult(kind="error", text=f"skip failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="text",
        text=f"Task skipped: {task_id}.",
        meta={"session_id": session_id, "task_id": task_id, "before_status": before, "status": "skipped"},
    )


def _h_retry(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    return CommandResult(
        kind="not_implemented",
        text="G2: ponowi biezacy task z reset progress.",
    )


def _h_explain(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): real /explain — pokazuje rationale ostatniej decyzji.

    Czyta z ``decision_records`` (DecisionGateEngine), bierze najświeższy
    rekord po ``timestamp`` desc i pokazuje description + decision_class
    + source_plan + module. Operator widzi "co, kiedy, dlaczego" jednej
    najświeższej decyzji bez przewijania całego łańcucha audytu.
    """
    try:
        from sylion.core.decision_gate_engine import get_decision_engine
        engine = get_decision_engine()
        decisions = engine.get_decisions()
    except Exception as exc:
        return CommandResult(
            kind="error",
            text=f"DecisionGateEngine unavailable: {exc}",
        )

    if not decisions:
        return CommandResult(
            kind="text",
            text="Brak decyzji w łańcuchu audytu.",
            meta={"decision_count": 0},
        )

    # decisions is already sorted DESC by timestamp (see get_decisions SQL)
    latest = decisions[0]
    decision_id = latest.get("decision_id", "?")
    d_class = latest.get("decision_class", "?")
    desc = latest.get("description", "")
    source = latest.get("source_plan", "")
    module = latest.get("module_id", "")
    change = latest.get("change_type", "")
    blast = latest.get("blast_radius", "")
    ts = latest.get("timestamp", 0.0)

    lines = [
        "SYLION AEIS v2 — najświeższa decyzja (rationale)",
        f"  decision_id    : {decision_id}",
        f"  decision_class : {d_class}",
        f"  source_plan    : {source}",
        f"  module_id      : {module}",
        f"  change_type    : {change}",
        f"  blast_radius   : {blast}",
        f"  timestamp      : {ts:.0f}",
        "",
        "  description / rationale:",
        f"    {desc}",
    ]
    return CommandResult(
        kind="text",
        text="\n".join(lines),
        meta={
            "decision_id": decision_id,
            "decision_class": d_class,
            "source_plan": source,
            "rationale": desc,
            "decision_count": len(decisions),
        },
    )


def _h_findings(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): real /findings — listuje otwarte F-### / security findings.

    Korzysta z ``SecurityAuditor.list_findings(status="open")`` (singleton,
    SQLite-backed). Filtr severity opcjonalny:
    /findings           → wszystkie otwarte
    /findings critical  → tylko critical
    """
    import warnings as _warnings
    severity_filter = args[0].lower() if args else None

    try:
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore", DeprecationWarning)
            from sylion.security.security_audit import get_security_auditor
            store = get_security_auditor()
    except Exception as exc:
        return CommandResult(
            kind="error",
            text=f"SecurityAuditor unavailable: {exc}",
        )

    try:
        findings = store.list_findings(
            severity=severity_filter,
            status="open",
        )
    except Exception as exc:
        return CommandResult(
            kind="error",
            text=f"SecurityAuditor.list_findings failed: {exc}",
        )

    rows = []
    for f in findings:
        rows.append({
            "finding_id": str(f.get("finding_id", "?")),
            "severity": str(f.get("severity", "?")),
            "module": str(f.get("module", "")),
            "title": (str(f.get("title", "")) or "")[:60],
        })
    return CommandResult(
        kind="table",
        headers=["finding_id", "severity", "module", "title"],
        rows=rows,
        text=(
            f"{len(rows)} otwartych findings"
            + (f" (severity={severity_filter})" if severity_filter else "")
            + "."
        ),
        meta={"count": len(rows), "severity_filter": severity_filter},
    )


def _h_budget(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): real /budget — capy projektów + ich zużycie.

    Listuje projekty z ``ProjectModeStore`` razem z ``cost_cap_usd``
    i sumą wydatków z cost_ledger przefiltrowaną per session_id =
    project.human_gate_session_id (proxy w Phase 1; G2 doda dedykowany
    project_id na cost-records).
    """
    try:
        from sylion.project_mode.store import get_project_mode_store
        from sylion.aeis_v2.deployment.cost_ledger import query_cost_jsonl
        store = get_project_mode_store()
        projects = store.list_projects()
    except Exception as exc:
        return CommandResult(
            kind="error",
            text=f"ProjectModeStore unavailable: {exc}",
        )

    rows = []
    for p in projects:
        cap = p.get("cost_cap_usd")
        sid = p.get("human_gate_session_id") or ""
        spent = 0.0
        if sid:
            try:
                cost_rows = query_cost_jsonl(session_id=sid)
                spent = sum(r.cost_usd for r in cost_rows)
            except Exception:
                spent = 0.0
        cap_str = f"${float(cap):.2f}" if cap else "-"
        progress = ""
        if cap and float(cap) > 0:
            progress = f"{(spent / float(cap)) * 100:.1f}%"
        rows.append({
            "project_id": p.get("project_id", "?"),
            "title": (p.get("title") or "")[:32],
            "phase": p.get("phase", "?"),
            "cost_cap": cap_str,
            "spent_usd": f"${spent:.4f}",
            "progress": progress,
        })

    return CommandResult(
        kind="table",
        headers=["project_id", "title", "phase", "cost_cap", "spent_usd", "progress"],
        rows=rows,
        text=f"{len(rows)} projektów (capy + zużycie).",
        meta={"project_count": len(rows)},
    )


def _h_priority(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    return CommandResult(
        kind="not_implemented",
        text="G2: zmieni priorytet biezacego taska.",
    )


def _h_export(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    return CommandResult(
        kind="not_implemented",
        text="G3: export sesji do JSON/Markdown (replay-friendly).",
    )


def _h_request(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    if not args or args[0] not in {"checkpoint", "punkt-kontrolny"}:
        return CommandResult(kind="error", text="usage: /request checkpoint")
    project_id = str(ctx.get("project_id") or "")
    command_id = uuid.uuid4().hex
    if project_id:
        try:
            from sylion.project_mode import get_project_mode_store

            store = get_project_mode_store()
            if store.get_project(project_id):
                store.add_event(
                    project_id,
                    "terminal.checkpoint.requested",
                    {
                        "command_id": command_id,
                        "source_surface": ctx.get("source_surface") or ctx.get("route") or "terminal",
                    },
                )
        except Exception as exc:
            return CommandResult(kind="error", text=f"checkpoint failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="text",
        text=f"Checkpoint zapisany dla W18. command_id={command_id}.",
        meta={"checkpoint": True, "command_id": command_id, "project_id": project_id},
    )


def _audit_db_connect() -> sqlite3.Connection:
    from sylion.aeis_v2.audit_profile import resolve_db_path

    conn = sqlite3.connect(resolve_db_path("sylion_aeis.db"))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row and row["c"])


def _latest_project(conn: sqlite3.Connection) -> sqlite3.Row | None:
    if not _table_exists(conn, "project_projects"):
        return None
    return conn.execute(
        "SELECT * FROM project_projects ORDER BY updated_at DESC, created_at DESC LIMIT 1"
    ).fetchone()


def _json_obj(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _json_any(raw: Any) -> Any:
    if raw in (None, ""):
        return None
    try:
        return json.loads(str(raw))
    except Exception:
        return None


def _row_get(row: sqlite3.Row | Mapping[str, Any], *names: str, default: Any = "") -> Any:
    try:
        keys = set(row.keys())  # type: ignore[attr-defined]
    except Exception:
        keys = set(row.keys()) if isinstance(row, Mapping) else set()
    for name in names:
        if name in keys:
            try:
                return row[name]  # type: ignore[index]
            except Exception:
                return default
    return default


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    try:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    except Exception:
        return set()


def _looks_like_project_id(value: str) -> bool:
    return bool(str(value or "").startswith(("project_", "proj_", "p_")))


def _looks_like_session_id(value: str) -> bool:
    raw = str(value or "").strip()
    return bool(raw and not _looks_like_project_id(raw) and len(raw) >= 8)


def _latest_council_session(
    conn: sqlite3.Connection,
    token: str | None = None,
) -> sqlite3.Row | None:
    if not _table_exists(conn, "hybrid_council_sessions"):
        return None
    if token:
        row = conn.execute(
            "SELECT * FROM hybrid_council_sessions WHERE session_id=? LIMIT 1",
            (token,),
        ).fetchone()
        if row:
            return row
        like = f"%{token}%"
        return conn.execute(
            "SELECT * FROM hybrid_council_sessions "
            "WHERE topic LIKE ? OR context LIKE ? "
            "ORDER BY created_at DESC LIMIT 1",
            (like, like),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM hybrid_council_sessions ORDER BY created_at DESC LIMIT 1"
    ).fetchone()


def _session_models(raw: Any) -> list[str]:
    value = _json_any(raw)
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _participant_rows(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    if not _table_exists(conn, "council_participants"):
        return []
    return list(conn.execute(
        "SELECT * FROM council_participants WHERE session_id=? ORDER BY joined_at ASC",
        (session_id,),
    ))


def _analysis_rows(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    if not _table_exists(conn, "model_analyses"):
        return []
    return list(conn.execute(
        "SELECT * FROM model_analyses WHERE session_id=? ORDER BY created_at ASC",
        (session_id,),
    ))


def _discussion_rows(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    if not _table_exists(conn, "discussion_rounds"):
        return []
    return list(conn.execute(
        "SELECT * FROM discussion_rounds WHERE session_id=? ORDER BY round_number ASC, created_at ASC",
        (session_id,),
    ))


def _critic_rows(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    if not _table_exists(conn, "council_critic_signatures"):
        return []
    return list(conn.execute(
        "SELECT * FROM council_critic_signatures WHERE session_id=? ORDER BY signed_at ASC",
        (session_id,),
    ))


def _sentinel_rows(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    if not _table_exists(conn, "council_sentinel_evaluations"):
        return []
    return list(conn.execute(
        "SELECT * FROM council_sentinel_evaluations WHERE session_id=? ORDER BY evaluated_at ASC",
        (session_id,),
    ))


def _latest_sentinel_rows(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    latest_by_role: dict[str, sqlite3.Row] = {}
    for row in rows:
        role = str(_row_get(row, "sentinel_role", default="")).strip()
        if role:
            latest_by_role[role] = row
    return list(latest_by_role.values())


def _blocking_sentinel_roles(rows: list[sqlite3.Row]) -> list[str]:
    blocking_verdicts = {"fail", "block", "reject"}
    blocked: list[str] = []
    for row in _latest_sentinel_rows(rows):
        verdict = str(_row_get(row, "verdict", default="")).lower()
        if verdict in blocking_verdicts:
            blocked.append(str(_row_get(row, "sentinel_role", default="")))
    return blocked


def _project_council_rows(conn: sqlite3.Connection, project_id: str | None) -> list[sqlite3.Row]:
    if not _table_exists(conn, "project_council_members"):
        return []
    if project_id:
        return list(conn.execute(
            "SELECT * FROM project_council_members WHERE project_id=? "
            "ORDER BY rowid ASC",
            (project_id,),
        ))
    return list(conn.execute(
        "SELECT * FROM project_council_members ORDER BY rowid DESC LIMIT 80"
    ))


def _cfg(row: sqlite3.Row) -> dict[str, Any]:
    return _json_obj(_row_get(row, "config_json", "config", default="{}"))


def _project_filter_from_args(
    conn: sqlite3.Connection,
    args: list[str],
    ctx: Mapping[str, Any] | None = None,
) -> str | None:
    if args and args[0] not in {"current-run", "all"}:
        return args[0]
    ctx_project_id = str((ctx or {}).get("project_id") or "")
    if ctx_project_id:
        return ctx_project_id
    latest = _latest_project(conn)
    return str(latest["project_id"]) if latest else None


def _h_report_workers(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    try:
        with _audit_db_connect() as conn:
            if not _table_exists(conn, "project_worker_pool"):
                return CommandResult(kind="text", text="Brak tabeli project_worker_pool w aktywnej bazie.")
            pid = _project_filter_from_args(conn, args, ctx)
            params: list[Any] = []
            where = ""
            if pid and (not args or args[0] != "all"):
                where = "WHERE project_id=?"
                params.append(pid)
            rows = [
                {
                    "project_id": r["project_id"],
                    "worker": r["name"],
                    "type": r["worker_type"],
                    "role": r["role"],
                    "endpoint": r["endpoint"],
                    "model": r["model_id"] or "-",
                    "active": "yes" if int(r["active"]) else "no",
                }
                for r in conn.execute(
                    f"SELECT * FROM project_worker_pool {where} ORDER BY project_id, name LIMIT 80",
                    params,
                )
            ]
    except Exception as exc:
        return CommandResult(kind="error", text=f"report workers failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["project_id", "worker", "type", "role", "endpoint", "model", "active"],
        rows=rows,
        text=f"{len(rows)} workerów w planie wykonania" + (f" dla {pid}" if pid else "") + ".",
        meta={"variant": "workers", "project_id": pid, "count": len(rows)},
    )


def _h_report_gates(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "governance_tickets"):
                for r in conn.execute(
                    "SELECT ticket_id, project_id, decision_class, gate_type, priority, state, title "
                    "FROM governance_tickets ORDER BY created_at DESC LIMIT 50"
                ):
                    rows.append({
                        "id": r["ticket_id"],
                        "plane": "governance_ticket",
                        "project_id": r["project_id"] or "-",
                        "class": r["decision_class"],
                        "gate": r["gate_type"],
                        "priority": r["priority"],
                        "state": r["state"],
                        "title": str(r["title"])[:80],
                    })
            if _table_exists(conn, "human_gate_requests"):
                for r in conn.execute(
                    "SELECT request_id, title, status, priority, requested_by FROM human_gate_requests "
                    "ORDER BY created_at DESC LIMIT 50"
                ):
                    rows.append({
                        "id": r["request_id"],
                        "plane": "human_gate_legacy",
                        "project_id": "-",
                        "class": "-",
                        "gate": r["requested_by"] or "-",
                        "priority": r["priority"],
                        "state": r["status"],
                        "title": str(r["title"])[:80],
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report gates failed: {_sanitize_error_text(str(exc))}")
    pending = sum(1 for row in rows if str(row.get("state")) == "pending")
    return CommandResult(
        kind="table",
        headers=["id", "plane", "project_id", "class", "gate", "priority", "state", "title"],
        rows=rows,
        text=f"{len(rows)} gate/ticket rekordów, pending={pending}.",
        meta={"variant": "gates", "count": len(rows), "pending": pending},
    )


def _h_report_tests(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_audit_results"):
                for r in conn.execute(
                    "SELECT project_id, module_id, audit_type, status, executed_at FROM project_audit_results "
                    "ORDER BY executed_at DESC LIMIT 50"
                ):
                    rows.append({
                        "project_id": r["project_id"],
                        "module": r["module_id"] or "-",
                        "test_or_audit": r["audit_type"],
                        "status": r["status"],
                        "executed_at": f"{float(r['executed_at']):.0f}",
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report tests failed: {_sanitize_error_text(str(exc))}")
    text = (
        f"{len(rows)} zapisanych wyników testów/audytów."
        if rows
        else "0 zapisanych wyników testów/audytów. Release gate nie może być uznany za pokryty bez evidence."
    )
    return CommandResult(
        kind="table",
        headers=["project_id", "module", "test_or_audit", "status", "executed_at"],
        rows=rows,
        text=text,
        meta={"variant": "tests", "count": len(rows)},
    )


def _h_report_deploy(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_masterplans"):
                for r in conn.execute(
                    "SELECT project_id, status, deployment_topology_json, frozen_at, updated_at "
                    "FROM project_masterplans ORDER BY updated_at DESC LIMIT 50"
                ):
                    topo = _json_obj(r["deployment_topology_json"])
                    rows.append({
                        "project_id": r["project_id"],
                        "status": r["status"],
                        "mode": topo.get("deployment_mode", "-"),
                        "provisioning": topo.get("provisioning_mode", "-"),
                        "vps_workers": str(topo.get("vps_workers", 0)),
                        "auto_provision": str(bool(topo.get("auto_provision", False))).lower(),
                        "frozen": "yes" if float(r["frozen_at"] or 0) else "no",
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report deploy failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["project_id", "status", "mode", "provisioning", "vps_workers", "auto_provision", "frozen"],
        rows=rows,
        text=f"{len(rows)} topologii deploymentu w masterplanach.",
        meta={"variant": "deploy", "count": len(rows)},
    )


def _h_report_skills(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    pid: str | None = None
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_skill_reuse_log"):
                pid = _project_filter_from_args(conn, args, ctx)
                params: list[Any] = []
                where = ""
                if pid and (not args or args[0] != "all"):
                    where = "WHERE project_id=?"
                    params.append(pid)
                for r in conn.execute(
                    "SELECT project_id, module_id, reused_skill_id, similarity_score, adaptation_notes, created_at "
                    f"FROM project_skill_reuse_log {where} ORDER BY created_at DESC LIMIT 80",
                    params,
                ):
                    rows.append({
                        "project_id": r["project_id"],
                        "module": r["module_id"],
                        "skill": r["reused_skill_id"],
                        "score": f"{float(r['similarity_score']):.3f}",
                        "notes": str(r["adaptation_notes"])[:80],
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report skills failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["project_id", "module", "skill", "score", "notes"],
        rows=rows,
        text=f"{len(rows)} wpisów skill matching/reuse" + (f" dla {pid}" if pid else "") + ".",
        meta={"variant": "skills", "project_id": pid, "count": len(rows)},
    )


def _h_report_council(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_council_members"):
                for r in conn.execute("SELECT * FROM project_council_members ORDER BY rowid DESC LIMIT 80"):
                    row = dict(r)
                    rows.append({
                        "project_id": row.get("project_id", "-"),
                        "role": row.get("role") or row.get("member_role") or "-",
                        "model": row.get("model_id") or row.get("model") or "-",
                        "weight": str(row.get("weight", row.get("vote_weight", "-"))),
                        "mandatory": str(row.get("mandatory", "-")),
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report council failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["project_id", "role", "model", "weight", "mandatory"],
        rows=rows,
        text=f"{len(rows)} członków/ról Rady w projektach.",
        meta={"variant": "council", "count": len(rows)},
    )


def _h_report_costs(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_cost_ledger"):
                for r in conn.execute(
                    "SELECT project_id, provider, model, SUM(tokens_in) AS tokens_in, "
                    "SUM(tokens_out) AS tokens_out, SUM(cost_usd) AS cost_usd "
                    "FROM project_cost_ledger GROUP BY project_id, provider, model "
                    "ORDER BY cost_usd DESC LIMIT 80"
                ):
                    rows.append({
                        "project_id": r["project_id"],
                        "provider": r["provider"] or "-",
                        "model": r["model"] or "-",
                        "tokens_in": int(r["tokens_in"] or 0),
                        "tokens_out": int(r["tokens_out"] or 0),
                        "cost_usd": f"{float(r['cost_usd'] or 0):.6f}",
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report costs failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["project_id", "provider", "model", "tokens_in", "tokens_out", "cost_usd"],
        rows=rows,
        text=f"{len(rows)} agregatów kosztów projektowych.",
        meta={"variant": "costs", "count": len(rows)},
    )


def _h_report_model_slots(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    token = args[0] if args else ""
    project_id = token if _looks_like_project_id(token) else None
    session_id = token if token and not project_id else ""
    try:
        with _audit_db_connect() as conn:
            if project_id:
                for r in _project_council_rows(conn, project_id):
                    cfg = _cfg(r)
                    role = str(_row_get(r, "member_role", "role", default="-") or "-")
                    rows.append({
                        "scope": "project",
                        "project_id": project_id,
                        "slot": str(_row_get(r, "council_member_id", "member_id", default="-")),
                        "provider": str(_row_get(r, "provider", default="-") or "-"),
                        "model": str(_row_get(r, "model_id", "model", default="-") or "-"),
                        "role": role,
                        "rank": str(cfg.get("rank") or "-"),
                        "weight": f"{float(_row_get(r, 'voting_weight', 'weight', default=1.0) or 1.0):.2f}",
                        "mandatory": "yes" if bool(cfg.get("required_signature") or role in {"critic", "governance", "security_sentinel"}) else "no",
                        "timeout_s": str(cfg.get("timeout_s") or cfg.get("timeout_seconds") or 30),
                        "cost_cap_usd": str(cfg.get("cost_cap_usd") or cfg.get("approval_threshold_usd") or "-"),
                        "output_contract": str(cfg.get("output_contract") or cfg.get("required_json_contract") or "verdict+reasoning+dissents"),
                        "status": "configured",
                    })
            sess = _latest_council_session(conn, session_id or project_id or None)
            if sess:
                sid = str(sess["session_id"])
                analyses_by_model = {str(r["model_id"]): r for r in _analysis_rows(conn, sid)}
                for p in _participant_rows(conn, sid):
                    model = str(p["model_id"])
                    analysis = analyses_by_model.get(model)
                    rows.append({
                        "scope": "session",
                        "project_id": project_id or "-",
                        "slot": str(p["participant_id"]),
                        "provider": "-",
                        "model": model,
                        "role": str(p["role"]),
                        "rank": str(p["rank"]),
                        "weight": f"{float(p['weight'] or 0):.2f}",
                        "mandatory": "yes",
                        "timeout_s": "30",
                        "cost_cap_usd": "-",
                        "output_contract": "model_analysis_json",
                        "status": "responded" if analysis else "pending",
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report model-slots failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=[
            "scope", "project_id", "slot", "provider", "model", "role", "rank",
            "weight", "mandatory", "timeout_s", "cost_cap_usd", "output_contract", "status",
        ],
        rows=rows,
        text=f"{len(rows)} slotow modeli/Rady" + (f" dla {token}" if token else "") + ".",
        meta={"variant": "model-slots", "token": token, "count": len(rows)},
    )


def _h_report_council_sync(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"variant": "council-sync", "token": token}
    try:
        with _audit_db_connect() as conn:
            project_id = token if _looks_like_project_id(token) else None
            sess = _latest_council_session(conn, None if project_id else token or None)
            if not sess and project_id:
                sess = _latest_council_session(conn, project_id)
            if sess:
                sid = str(sess["session_id"])
                participants = _participant_rows(conn, sid)
                analyses = _analysis_rows(conn, sid)
                signatures = _critic_rows(conn, sid)
                sentinels = _sentinel_rows(conn, sid)
                expected = [str(p["model_id"]) for p in participants] or _session_models(sess["models"])
                received = {str(a["model_id"]) for a in analyses}
                missing = [m for m in expected if m not in received]
                failed = [
                    str(a["model_id"]) for a in analyses
                    if "REAL_LLM_" in str(a["analysis_text"] or "")
                ]
                sentinel_blocks = _blocking_sentinel_roles(sentinels)
                barrier_status = "satisfied" if not missing and not failed else "blocked"
                if sentinel_blocks:
                    barrier_status = "guard_blocked"
                next_enabled = barrier_status == "satisfied" and bool(signatures or not expected)
                rows.append({
                    "barrier_id": f"barrier-{sid}",
                    "project_id": project_id or "-",
                    "session_id": sid,
                    "phase": str(sess["phase"]),
                    "expected_blocking": len(expected),
                    "received_blocking": len(received),
                    "missing": ", ".join(missing) or "-",
                    "failed": ", ".join(failed) or "-",
                    "sentinel_blocks": ", ".join(sentinel_blocks) or "-",
                    "critic_signed": "yes" if signatures else "no",
                    "barrier_status": barrier_status,
                    "next_stage_enabled": "yes" if next_enabled else "no",
                    "audit_ref": str(sess["session_id"]),
                })
                meta.update({
                    "session_id": sid,
                    "expected_blocking_models": len(expected),
                    "received_blocking_models": len(received),
                    "missing_blocking_models": missing,
                    "failed_models": failed,
                    "barrier_status": barrier_status,
                    "next_stage_enabled": next_enabled,
                })
            elif project_id:
                members = _project_council_rows(conn, project_id)
                rows.append({
                    "barrier_id": f"project-roster-{project_id}",
                    "project_id": project_id,
                    "session_id": "-",
                    "phase": "no_runtime_session",
                    "expected_blocking": len(members),
                    "received_blocking": 0,
                    "missing": "runtime council session not recorded",
                    "failed": "-",
                    "sentinel_blocks": "-",
                    "critic_signed": "no",
                    "barrier_status": "blocked",
                    "next_stage_enabled": "no",
                    "audit_ref": "project_council_members",
                })
                meta.update({"project_id": project_id, "barrier_status": "blocked", "next_stage_enabled": False})
    except Exception as exc:
        return CommandResult(kind="error", text=f"report council-sync failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=[
            "barrier_id", "project_id", "session_id", "phase", "expected_blocking",
            "received_blocking", "missing", "failed", "sentinel_blocks",
            "critic_signed", "barrier_status", "next_stage_enabled", "audit_ref",
        ],
        rows=rows,
        text=f"{len(rows)} rekordow bariery synchronizacji Council.",
        meta={**meta, "count": len(rows)},
    )


def _h_report_guard_decisions(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    project_id = token if _looks_like_project_id(token) else None
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "governance_tickets"):
                params: list[Any] = []
                where = ""
                if project_id:
                    where = "WHERE project_id=?"
                    params.append(project_id)
                for r in conn.execute(
                    "SELECT * FROM governance_tickets "
                    f"{where} ORDER BY created_at DESC LIMIT 80",
                    params,
                ):
                    payload = _json_obj(r["payload_json"])
                    state = str(r["state"] or "")
                    decision = "block" if state == "pending" else "allow" if state == "approved" else state or "unknown"
                    rows.append({
                        "guard_id": r["ticket_id"],
                        "project_id": r["project_id"] or "-",
                        "stage": str(payload.get("target") or payload.get("action") or r["origin"] or "-")[:60],
                        "guard": str(r["gate_type"] or "-"),
                        "policy_ref": str(payload.get("policy_ref") or r["requested_by"] or "-")[:80],
                        "decision": decision,
                        "severity": r["priority"] or "-",
                        "reason": str(r["summary"] or r["title"] or "")[:120],
                        "human_gate_ref": r["ticket_id"],
                        "audit_ref": r["audit_chain_ref"] or "-",
                    })
            if _table_exists(conn, "gate_evaluations"):
                for r in conn.execute("SELECT * FROM gate_evaluations ORDER BY evaluated_at DESC LIMIT 40"):
                    ctx_obj = _json_obj(r["context_json"])
                    if project_id and ctx_obj.get("project_id") != project_id:
                        continue
                    rows.append({
                        "guard_id": r["evaluation_id"],
                        "project_id": ctx_obj.get("project_id", "-"),
                        "stage": ctx_obj.get("stage", "-"),
                        "guard": r["gate_id"],
                        "policy_ref": "gate_evaluations",
                        "decision": r["result"],
                        "severity": ctx_obj.get("severity", "-"),
                        "reason": str(r["message"] or "")[:120],
                        "human_gate_ref": "-",
                        "audit_ref": r["evaluation_id"],
                    })
            if _table_exists(conn, "w14_guardian_alerts"):
                for r in conn.execute("SELECT * FROM w14_guardian_alerts ORDER BY created_at DESC LIMIT 40"):
                    payload = _json_obj(r["payload"])
                    if project_id and payload.get("project_id") != project_id:
                        continue
                    rows.append({
                        "guard_id": r["obj_id"],
                        "project_id": payload.get("project_id", "-"),
                        "stage": payload.get("stage", "-"),
                        "guard": payload.get("guardian", payload.get("class", "W14 guardian")),
                        "policy_ref": payload.get("policy_ref", "w14_guardian_alerts"),
                        "decision": payload.get("decision", payload.get("severity", "alert")),
                        "severity": payload.get("severity", "-"),
                        "reason": str(payload.get("message") or payload.get("reason") or "")[:120],
                        "human_gate_ref": payload.get("human_gate_ref", "-"),
                        "audit_ref": r["obj_id"],
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report guard-decisions failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["guard_id", "project_id", "stage", "guard", "policy_ref", "decision", "severity", "reason", "human_gate_ref", "audit_ref"],
        rows=rows[:100],
        text=f"{len(rows[:100])} decyzji guardow/gate'ow.",
        meta={"variant": "guard-decisions", "project_id": project_id, "count": len(rows[:100])},
    )


def _h_report_debate_graph(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"variant": "debate-graph", "token": token}
    try:
        with _audit_db_connect() as conn:
            sess = _latest_council_session(conn, token or None)
            if not sess:
                return CommandResult(
                    kind="table",
                    headers=["node", "type", "model_or_guard", "role", "relation", "status", "text"],
                    rows=[],
                    text="0 wezlow: brak utrwalonej sesji Council dla podanego filtra.",
                    meta={**meta, "count": 0, "graph_status": "missing_session"},
                )
            sid = str(sess["session_id"])
            participants = {str(p["model_id"]): p for p in _participant_rows(conn, sid)}
            analyses = _analysis_rows(conn, sid)
            discussions = _discussion_rows(conn, sid)
            sentinels = _sentinel_rows(conn, sid)
            for a in analyses:
                p = participants.get(str(a["model_id"]))
                rows.append({
                    "node": a["analysis_id"],
                    "type": "model_analysis",
                    "model_or_guard": str(a["model_id"]),
                    "role": str(_row_get(p, "role", default="-")) if p else "-",
                    "relation": "root_analysis",
                    "status": str(a["verdict"]),
                    "text": str(a["rationale"] or a["analysis_text"] or "")[:160],
                })
            for d in discussions:
                relation = f"critiques:{d['reaction_to']}" if d["reaction_to"] else "discussion"
                rows.append({
                    "node": d["round_id"],
                    "type": "discussion_round",
                    "model_or_guard": str(d["model_id"]),
                    "role": str(_row_get(participants.get(str(d["model_id"])), "role", default="-")),
                    "relation": relation,
                    "status": f"round_{d['round_number']}",
                    "text": str(d["contribution"] or "")[:160],
                })
            for s in sentinels:
                rows.append({
                    "node": s["evaluation_id"],
                    "type": "guard_decision",
                    "model_or_guard": str(s["sentinel_role"]),
                    "role": "sentinel",
                    "relation": "constrains_synthesis",
                    "status": str(s["verdict"]),
                    "text": str(s["details"] or "")[:160],
                })
            isolated = max(0, len(analyses) - len({str(d["reaction_to"]) for d in discussions if d["reaction_to"]}))
            graph_status = "cross_reply_present" if discussions else "parallel_only"
            meta.update({
                "session_id": sid,
                "nodes": len(rows),
                "analysis_nodes": len(analyses),
                "discussion_nodes": len(discussions),
                "guard_nodes": len(sentinels),
                "isolated_messages": isolated,
                "graph_status": graph_status,
            })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report debate-graph failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["node", "type", "model_or_guard", "role", "relation", "status", "text"],
        rows=rows,
        text=f"{len(rows)} wezlow grafu dyskusji Council.",
        meta=meta,
    )


def _h_report_dissent(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"variant": "dissent", "token": token}
    try:
        with _audit_db_connect() as conn:
            sess = _latest_council_session(conn, token or None)
            if sess:
                sid = str(sess["session_id"])
                participants = {str(p["model_id"]): p for p in _participant_rows(conn, sid)}
                analyses = _analysis_rows(conn, sid)
                weights: dict[str, float] = {}
                for a in analyses:
                    verdict = str(a["verdict"] or "unknown")
                    p = participants.get(str(a["model_id"]))
                    weights[verdict] = weights.get(verdict, 0.0) + float(_row_get(p, "weight", default=1.0) or 1.0)
                majority = max(weights, key=weights.get) if weights else ""
                for a in analyses:
                    verdict = str(a["verdict"] or "unknown")
                    p = participants.get(str(a["model_id"]))
                    if verdict != majority:
                        rows.append({
                            "source": "model",
                            "session_id": sid,
                            "model": str(a["model_id"]),
                            "role": str(_row_get(p, "role", default="-")) if p else "-",
                            "verdict": verdict,
                            "majority": majority or "-",
                            "dissent": str(a["rationale"] or a["analysis_text"] or "")[:180],
                        })
                for s in _sentinel_rows(conn, sid):
                    if str(s["verdict"]).lower() in {"warn", "fail", "block", "reject", "conditional"}:
                        rows.append({
                            "source": "sentinel",
                            "session_id": sid,
                            "model": str(s["model_id"]),
                            "role": str(s["sentinel_role"]),
                            "verdict": str(s["verdict"]),
                            "majority": majority or "-",
                            "dissent": str(s["details"] or "")[:180],
                        })
                meta.update({"session_id": sid, "majority": majority, "dissent_count": len(rows)})
            elif _looks_like_project_id(token) and _table_exists(conn, "governance_tickets"):
                for r in conn.execute(
                    "SELECT * FROM governance_tickets WHERE project_id=? AND state!='approved' "
                    "ORDER BY created_at DESC LIMIT 50",
                    (token,),
                ):
                    rows.append({
                        "source": "human_gate",
                        "session_id": "-",
                        "model": "-",
                        "role": r["gate_type"],
                        "verdict": r["state"],
                        "majority": "approved_only_after_hg",
                        "dissent": str(r["summary"] or r["title"] or "")[:180],
                    })
                meta.update({"project_id": token, "dissent_count": len(rows)})
    except Exception as exc:
        return CommandResult(kind="error", text=f"report dissent failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["source", "session_id", "model", "role", "verdict", "majority", "dissent"],
        rows=rows,
        text=f"{len(rows)} dissent/minority raportow.",
        meta=meta,
    )


def _h_report_loop_guard(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    project_id = token if _looks_like_project_id(token) else None
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "w14_loop_reports"):
                for r in conn.execute("SELECT * FROM w14_loop_reports ORDER BY created_at DESC LIMIT 80"):
                    payload = _json_obj(r["payload"])
                    required_decision = payload.get("required_decision")
                    if not isinstance(required_decision, dict):
                        required_decision = {}
                    row_project_id = (
                        payload.get("project_id")
                        or required_decision.get("project_id")
                        or "-"
                    )
                    if project_id and row_project_id != project_id:
                        continue
                    rows.append({
                        "loop_id": r["obj_id"],
                        "project_id": row_project_id,
                        "process": payload.get("process_type", payload.get("process", "-")),
                        "stage": payload.get("stage_id", payload.get("stage", "-")),
                        "max_attempts": payload.get("max_attempts", required_decision.get("max_attempts", "-")),
                        "attempts_seen": payload.get("attempts_seen", payload.get("attempts_n", "-")),
                        "trigger": payload.get("trigger", payload.get("loop_type", required_decision.get("reason", "-"))),
                        "status": payload.get("loop_status", payload.get("status", required_decision.get("status", "-"))),
                        "human_gate_ref": payload.get("human_gate_ref", required_decision.get("human_gate_ref", "-")),
                    })
            repair_attempts = 0
            if _table_exists(conn, "w14_repair_attempts"):
                for r in conn.execute("SELECT payload FROM w14_repair_attempts ORDER BY created_at DESC LIMIT 200"):
                    payload = _json_obj(r["payload"])
                    if not project_id or payload.get("project_id") == project_id:
                        repair_attempts += 1
            if not rows and project_id:
                rows.append({
                    "loop_id": f"loopguard-{project_id}",
                    "project_id": project_id,
                    "process": "fixer/runtime",
                    "stage": "all",
                    "max_attempts": "3",
                    "attempts_seen": repair_attempts,
                    "trigger": "no repeated-state trigger recorded",
                    "status": "armed_not_triggered",
                    "human_gate_ref": "-",
                })
    except Exception as exc:
        return CommandResult(kind="error", text=f"report loop-guard failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["loop_id", "project_id", "process", "stage", "max_attempts", "attempts_seen", "trigger", "status", "human_gate_ref"],
        rows=rows,
        text=f"{len(rows)} rekordow LoopGuard.",
        meta={"variant": "loop-guard", "project_id": project_id, "count": len(rows)},
    )


def _h_report(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    """Phase 1 (AR-6.2): real /report — najczęstszy wariant ``current-run``.

    /report current-run → najświeższy projekt (max ``updated_at``) z fazą,
        statusem, cost_cap, autonomy_level i krótkim podsumowaniem
        modułów + decyzji (count).

    Inne warianty pozostają jako placeholdery (``daily``, ``weekly``).
    """
    variant = (args[0] if args else "current-run").lower()
    if variant == "workers":
        return _h_report_workers(args[1:], ctx)
    if variant == "gates":
        return _h_report_gates(args[1:], ctx)
    if variant == "tests":
        return _h_report_tests(args[1:], ctx)
    if variant == "deploy":
        return _h_report_deploy(args[1:], ctx)
    if variant == "skills":
        return _h_report_skills(args[1:], ctx)
    if variant == "council":
        return _h_report_council(args[1:], ctx)
    if variant in {"cost", "costs"}:
        return _h_report_costs(args[1:], ctx)
    if variant in {"model-slots", "modelslots"}:
        return _h_report_model_slots(args[1:], ctx)
    if variant in {"council-sync", "council-wait", "wait-barrier"}:
        return _h_report_council_sync(args[1:], ctx)
    if variant in {"model-barriers", "model-barrier", "pending-models"}:
        return _h_show_pending_models(args[1:], ctx)
    if variant in {"guard-decisions", "guards"}:
        return _h_report_guard_decisions(args[1:], ctx)
    if variant in {"debate-graph", "discussion-graph"}:
        return _h_report_debate_graph(args[1:], ctx)
    if variant == "dissent":
        return _h_report_dissent(args[1:], ctx)
    if variant in {"loop-guard", "loopguard"}:
        return _h_report_loop_guard(args[1:], ctx)
    if variant != "current-run":
        return CommandResult(
            kind="not_implemented",
            text=(
                f"Wariant '/report {variant}' jeszcze nie zaimplementowany. "
                "Dostępne: /report current-run/workers/gates/tests/deploy/skills/council/costs/model-barriers."
            ),
        )

    try:
        from sylion.project_mode.store import get_project_mode_store
        store = get_project_mode_store()
        projects = store.list_projects()
    except Exception as exc:
        return CommandResult(
            kind="error",
            text=f"ProjectModeStore unavailable: {exc}",
        )

    if not projects:
        return CommandResult(
            kind="text",
            text="Brak projektów w systemie.",
            meta={"project_count": 0},
        )

    # Wybierz najświeższy po updated_at
    latest = max(projects, key=lambda p: float(p.get("updated_at", 0.0)))
    pid = latest.get("project_id", "?")
    title = latest.get("title", "?")
    phase = latest.get("phase", "?")
    status = latest.get("status", "?")
    cap = latest.get("cost_cap_usd")
    autonomy = latest.get("autonomy_level", "")
    n_modules = len(latest.get("modules") or [])
    n_decisions = len(latest.get("decisions") or [])
    n_questions_pending = len(latest.get("pending_questions") or [])
    updated_at = float(latest.get("updated_at", 0.0))

    lines = [
        "SYLION AEIS v2 — current-run (najświeższy projekt)",
        f"  project_id     : {pid}",
        f"  title          : {title}",
        f"  phase          : {phase}",
        f"  status         : {status}",
        f"  cost_cap_usd   : {f'${float(cap):.2f}' if cap else '(brak)'}",
        f"  autonomy_level : {autonomy or '(default)'}",
        f"  modules        : {n_modules}",
        f"  decisions      : {n_decisions}",
        f"  pending_questions: {n_questions_pending}",
        f"  updated_at     : {updated_at:.0f}",
    ]
    return CommandResult(
        kind="text",
        text="\n".join(lines),
        meta={
            "project_id": pid,
            "title": title,
            "phase": phase,
            "status": status,
            "cost_cap_usd": cap,
            "autonomy_level": autonomy,
            "module_count": n_modules,
            "decision_count": n_decisions,
            "pending_question_count": n_questions_pending,
            "updated_at": updated_at,
        },
    )


def _h_host(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    if not args:
        return CommandResult(kind="error", text="usage: /host <name>")
    host = " ".join(args).strip()
    needle = host.lower()
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_worker_pool"):
                for r in conn.execute(
                    "SELECT project_id, name, worker_type, endpoint, model_id, role, active "
                    "FROM project_worker_pool ORDER BY project_id, name LIMIT 500"
                ):
                    endpoint = str(r["endpoint"] or "")
                    worker_type = str(r["worker_type"] or "")
                    endpoint_l = endpoint.lower()
                    type_l = worker_type.lower()
                    local_match = needle == "local" and (
                        endpoint_l in {"localhost", "local", "127.0.0.1", "::1"}
                        or endpoint_l.startswith("localhost:")
                        or endpoint_l.startswith("127.0.0.1:")
                        or "local" in type_l
                    )
                    if local_match or needle in endpoint_l or needle in type_l:
                        rows.append({
                            "source": "worker",
                            "project_id": r["project_id"],
                            "name": r["name"],
                            "type": worker_type,
                            "endpoint": endpoint or "-",
                            "role": r["role"] or "-",
                            "model": r["model_id"] or "-",
                            "active": "yes" if int(r["active"] or 0) else "no",
                        })
            if _table_exists(conn, "project_masterplans"):
                for r in conn.execute(
                    "SELECT project_id, status, deployment_topology_json, frozen_at "
                    "FROM project_masterplans ORDER BY updated_at DESC LIMIT 200"
                ):
                    topo = _json_obj(r["deployment_topology_json"])
                    mode = str(topo.get("deployment_mode") or "")
                    provisioning = str(topo.get("provisioning_mode") or "")
                    target = f"{mode} {provisioning}".lower()
                    local_match = needle == "local" and (
                        "local" in target or int(topo.get("local_docker_workers") or 0) > 0
                    )
                    if local_match or needle in target:
                        rows.append({
                            "source": "masterplan",
                            "project_id": r["project_id"],
                            "name": r["status"],
                            "type": mode or "-",
                            "endpoint": provisioning or "-",
                            "role": f"vps={topo.get('vps_workers', 0)} local={topo.get('local_docker_workers', 0)}",
                            "model": "-",
                            "active": "yes" if float(r["frozen_at"] or 0) else "no",
                        })
    except Exception as exc:
        return CommandResult(kind="error", text=f"host drill-down failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["source", "project_id", "name", "type", "endpoint", "role", "model", "active"],
        rows=rows[:100],
        text=f"{len(rows[:100])} runtime/deploy wpisów dla hosta '{host}'.",
        meta={"host": host, "count": len(rows[:100])},
    )


def _h_model(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    if not args:
        return CommandResult(kind="error", text="usage: /model <name>")
    model = " ".join(args).strip()
    needle = model.lower()
    like = f"%{needle}%"
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "project_worker_pool"):
                for r in conn.execute(
                    "SELECT project_id, name, worker_type, model_id, role, active "
                    "FROM project_worker_pool WHERE lower(model_id) LIKE ? "
                    "ORDER BY project_id, name LIMIT 80",
                    (like,),
                ):
                    rows.append({
                        "source": "worker",
                        "project_id": r["project_id"],
                        "role_or_provider": r["role"] or r["worker_type"] or "-",
                        "model": r["model_id"] or "-",
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost_usd": "0.000000",
                        "active": "yes" if int(r["active"] or 0) else "no",
                    })
            if _table_exists(conn, "project_council_members"):
                for r in conn.execute(
                    "SELECT project_id, member_role, provider, model_id, voting_weight, active "
                    "FROM project_council_members "
                    "WHERE lower(model_id) LIKE ? OR lower(provider) LIKE ? "
                    "ORDER BY project_id, member_role LIMIT 80",
                    (like, like),
                ):
                    rows.append({
                        "source": "council",
                        "project_id": r["project_id"],
                        "role_or_provider": r["member_role"] or r["provider"] or "-",
                        "model": r["model_id"] or r["provider"] or "-",
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost_usd": "0.000000",
                        "active": "yes" if int(r["active"] or 0) else "no",
                    })
            if _table_exists(conn, "project_cost_ledger"):
                for r in conn.execute(
                    "SELECT project_id, provider, model, SUM(tokens_in) AS tokens_in, "
                    "SUM(tokens_out) AS tokens_out, SUM(cost_usd) AS cost_usd "
                    "FROM project_cost_ledger "
                    "WHERE lower(model) LIKE ? OR lower(provider) LIKE ? "
                    "GROUP BY project_id, provider, model ORDER BY cost_usd DESC LIMIT 80",
                    (like, like),
                ):
                    rows.append({
                        "source": "cost_ledger",
                        "project_id": r["project_id"],
                        "role_or_provider": r["provider"] or "-",
                        "model": r["model"] or "-",
                        "tokens_in": int(r["tokens_in"] or 0),
                        "tokens_out": int(r["tokens_out"] or 0),
                        "cost_usd": f"{float(r['cost_usd'] or 0):.6f}",
                        "active": "-",
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"model drill-down failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["source", "project_id", "role_or_provider", "model", "tokens_in", "tokens_out", "cost_usd", "active"],
        rows=rows[:100],
        text=f"{len(rows[:100])} wpisów runtime/kosztów dla modelu '{model}'.",
        meta={"model": model, "count": len(rows[:100])},
    )


# Kolejnosc w liscie = kolejnosc w /help (PDF §7.2 zachowuje grupowanie).
def _h_show_audit_tail(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    limit = 20
    if args:
        try:
            limit = max(1, min(100, int(args[0])))
        except ValueError:
            return CommandResult(kind="error", text="usage: /show audit-tail [limit]")
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_dir

        root = Path(resolve_audit_chain_dir())
        files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        rows: list[dict[str, Any]] = []
        for path in files[:10]:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in reversed(lines[-limit:]):
                if not line.strip():
                    continue
                safe = _SECRET_RE.sub("<redacted>", line[:2000])
                try:
                    raw_payload = json.loads(safe)
                except Exception:
                    raw_payload = {"raw": safe}
                content = raw_payload.get("content") if isinstance(raw_payload, dict) else None
                payload = content if isinstance(content, dict) else raw_payload
                nested = payload.get("payload") if isinstance(payload, dict) else None
                details = payload.get("details") if isinstance(payload, dict) else None
                if not isinstance(nested, dict):
                    nested = {}
                if not isinstance(details, dict):
                    details = {}
                rows.append({
                    "file": path.name,
                    "kind": str(payload.get("kind") or payload.get("event_type") or payload.get("topic") or payload.get("action") or "-")[:60],
                    "project_id": str(payload.get("project_id") or nested.get("project_id") or details.get("project_id") or payload.get("primary_key") or "-")[:60],
                    "ref": str(
                        raw_payload.get("content_hash")
                        or payload.get("hash")
                        or payload.get("event_id")
                        or payload.get("audit_chain_ref")
                        or "-"
                    )[:80],
                })
                if len(rows) >= limit:
                    break
            if len(rows) >= limit:
                break
    except Exception as exc:
        return CommandResult(kind="error", text=f"show audit-tail failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["file", "kind", "project_id", "ref"],
        rows=rows,
        text=f"Ostatnie {len(rows)} wpisów z audit chain.",
        meta={"variant": "audit-tail", "count": len(rows)},
    )


def _h_show_blockers(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            if _table_exists(conn, "governance_tickets"):
                for r in conn.execute(
                    "SELECT ticket_id, project_id, priority, decision_class, gate_type, title "
                    "FROM governance_tickets WHERE state='pending' ORDER BY created_at DESC LIMIT 50"
                ):
                    rows.append({
                        "source": "governance_ticket",
                        "id": r["ticket_id"],
                        "severity": r["priority"],
                        "project_id": r["project_id"] or "-",
                        "title": str(r["title"])[:90],
                    })
            if _table_exists(conn, "human_gate_requests"):
                for r in conn.execute(
                    "SELECT request_id, priority, title FROM human_gate_requests "
                    "WHERE status='pending' ORDER BY created_at DESC LIMIT 50"
                ):
                    rows.append({
                        "source": "human_gate_legacy",
                        "id": r["request_id"],
                        "severity": r["priority"],
                        "project_id": "-",
                        "title": str(r["title"])[:90],
                    })
            if _table_exists(conn, "project_questions"):
                q_cols = {r["name"] for r in conn.execute("PRAGMA table_info(project_questions)")}
                title_col = "question_text" if "question_text" in q_cols else "context"
                order_col = "created_at" if "created_at" in q_cols else "asked_at"
                for r in conn.execute(
                    f"SELECT project_id, question_id, {title_col} AS title, status FROM project_questions "
                    f"WHERE status NOT IN ('answered','closed','resolved') ORDER BY {order_col} DESC LIMIT 50"
                ):
                    rows.append({
                        "source": "project_question",
                        "id": r["question_id"],
                        "severity": "info",
                        "project_id": r["project_id"],
                        "title": str(r["title"])[:90],
                    })
    except Exception as exc:
        return CommandResult(kind="error", text=f"show blockers failed: {_sanitize_error_text(str(exc))}")

    try:
        from sylion.security.security_audit import get_security_auditor
        auditor = get_security_auditor()
        for finding in auditor.list_findings(status="open"):
            severity = str(finding.get("severity", ""))
            if severity in {"high", "critical"}:
                rows.append({
                    "source": "security_finding",
                    "id": str(finding.get("finding_id", "?")),
                    "severity": severity,
                    "project_id": "-",
                    "title": str(finding.get("title", ""))[:90],
                })
    except Exception:
        pass

    return CommandResult(
        kind="table",
        headers=["source", "id", "severity", "project_id", "title"],
        rows=rows,
        text=f"{len(rows)} aktywnych blockerów do sprawdzenia.",
        meta={"variant": "blockers", "count": len(rows)},
    )


def _h_show_pending_models(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            sess = _latest_council_session(conn, token or None)
            if not sess:
                return CommandResult(
                    kind="table",
                    headers=["session_id", "model", "role", "status", "reason"],
                    rows=[],
                    text="0 pending modeli: brak utrwalonej sesji Council dla filtra.",
                    meta={"variant": "pending-models", "token": token, "count": 0},
                )
            sid = str(sess["session_id"])
            participants = _participant_rows(conn, sid)
            analyses = {str(r["model_id"]): r for r in _analysis_rows(conn, sid)}
            if participants:
                for p in participants:
                    model = str(p["model_id"])
                    if model not in analyses:
                        rows.append({
                            "session_id": sid,
                            "model": model,
                            "role": str(p["role"]),
                            "status": "pending",
                            "reason": "mandatory participant has no analysis row",
                        })
            else:
                for model in _session_models(sess["models"]):
                    if model not in analyses:
                        rows.append({
                            "session_id": sid,
                            "model": model,
                            "role": "-",
                            "status": "pending",
                            "reason": "session model has no analysis row",
                        })
            if not rows:
                rows.append({
                    "session_id": sid,
                    "model": "-",
                    "role": "-",
                    "status": "all_resolved",
                    "reason": "all expected models have analysis rows",
                })
    except Exception as exc:
        return CommandResult(kind="error", text=f"show pending-models failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["session_id", "model", "role", "status", "reason"],
        rows=rows,
        text=f"{len(rows)} rekordow pending/all-resolved modeli.",
        meta={"variant": "pending-models", "token": token, "count": len(rows)},
    )


def _h_show_council_state(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    token = args[0] if args else ""
    rows: list[dict[str, Any]] = []
    try:
        with _audit_db_connect() as conn:
            project_id = token if _looks_like_project_id(token) else None
            if project_id:
                for r in _project_council_rows(conn, project_id):
                    cfg = _cfg(r)
                    rows.append({
                        "scope": "project_roster",
                        "id": str(_row_get(r, "council_member_id", "member_id", default="-")),
                        "project_id": project_id,
                        "phase": "-",
                        "role": str(_row_get(r, "member_role", "role", default="-")),
                        "model": str(_row_get(r, "model_id", default="-")),
                        "state": "active" if int(_row_get(r, "active", default=1) or 0) else "inactive",
                        "details": f"rank={cfg.get('rank', '-')}; weight={_row_get(r, 'voting_weight', default='-')}",
                    })
            sess = _latest_council_session(conn, None if project_id else token or None)
            if sess:
                rows.append({
                    "scope": "runtime_session",
                    "id": str(sess["session_id"]),
                    "project_id": project_id or "-",
                    "phase": str(sess["phase"]),
                    "role": "moderator",
                    "model": str(sess["moderator_model"] or "-"),
                    "state": str(sess["status"]),
                    "details": str(sess["topic"])[:140],
                })
    except Exception as exc:
        return CommandResult(kind="error", text=f"show council-state failed: {_sanitize_error_text(str(exc))}")
    return CommandResult(
        kind="table",
        headers=["scope", "id", "project_id", "phase", "role", "model", "state", "details"],
        rows=rows,
        text=f"{len(rows)} rekordow stanu Rady.",
        meta={"variant": "council-state", "token": token, "count": len(rows)},
    )


def _h_show(args: list[str], ctx: dict[str, Any]) -> CommandResult:
    if not args:
        return CommandResult(kind="error", text="usage: /show audit-tail [limit] | /show blockers | /show pending-models [id] | /show council-state [id]")
    target = args[0].lower()
    if target == "audit-tail":
        return _h_show_audit_tail(args[1:], ctx)
    if target == "blockers":
        return _h_show_blockers(args[1:], ctx)
    if target == "pending-models":
        return _h_show_pending_models(args[1:], ctx)
    if target == "council-state":
        return _h_show_council_state(args[1:], ctx)
    return CommandResult(kind="error", text="usage: /show audit-tail [limit] | /show blockers | /show pending-models [id] | /show council-state [id]")


def _h_runtime_truth(args: list[str], ctx: Mapping[str, Any]) -> CommandResult:
    """Show the same runtime truth signal that the operator dashboard uses."""
    try:
        import os
        import platform
        import sys
        import time
        from pathlib import Path

        from sylion.api.runtime_truth_routes import (
            CHECK_PORTS,
            _classify,
            _db_candidates,
            _git_value,
            _port_open,
        )

        cwd = Path.cwd().resolve()
        port_rows = [
            {"port": port, "label": label, "open": _port_open(port)}
            for port, label in CHECK_PORTS
        ]
        status, warnings, blockers = _classify(None, port_rows)
        git_branch = _git_value(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "unknown"
        git_commit = _git_value(["rev-parse", "--short", "HEAD"], cwd) or "unknown"
        dirty = _git_value(["status", "--porcelain"], cwd)
        rows = [
            {"scope": "api", "key": "pid", "value": str(os.getpid())},
            {"scope": "api", "key": "cwd", "value": str(cwd)},
            {"scope": "api", "key": "python", "value": sys.version.split()[0]},
            {"scope": "api", "key": "platform", "value": platform.platform()},
            {"scope": "git", "key": "branch", "value": git_branch},
            {"scope": "git", "key": "commit", "value": git_commit},
            {"scope": "git", "key": "dirty_entries", "value": str(len([line for line in dirty.splitlines() if line.strip()]))},
            {"scope": "database", "key": "mode", "value": "postgres" if os.environ.get("SYLION_DB_URL") else "sqlite/local"},
            {"scope": "database", "key": "candidates", "value": " | ".join(_db_candidates(cwd)[:3]) or "-"},
        ]
        for row in port_rows:
            rows.append({
                "scope": "port",
                "key": f"{row['port']} {row['label']}",
                "value": "open" if row["open"] else "closed",
            })
        for blocker in blockers:
            rows.append({"scope": "blocker", "key": blocker, "value": "active"})
        for warning in warnings:
            rows.append({"scope": "warning", "key": warning, "value": "active"})
        return CommandResult(
            kind="table",
            headers=["scope", "key", "value"],
            rows=rows,
            text=f"Runtime Truth: {status} ({time.strftime('%H:%M:%S')}).",
            meta={"status": status, "warnings": warnings, "blockers": blockers},
        )
    except Exception as exc:
        return CommandResult(kind="error", text=f"runtime-truth failed: {_sanitize_error_text(str(exc))}")


BUILTIN_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("status", "Stan systemu w jednym widoku.",
                "System status overview.", "", _h_status,
                aliases=("st",)),
    CommandSpec("cost", "Zsumowany koszt sesji / projektu.",
                "Aggregated cost.", "", _h_cost),
    CommandSpec("agents", "Lista zarejestrowanych agentow / modeli.",
                "List registered agents/models.", "", _h_agents,
                aliases=("models", "providers")),
    CommandSpec("skip", "Pomin biezacy task.", "Skip current task.", "", _h_skip),
    CommandSpec("focus", "Zawezi widok activity stream.",
                "Narrow activity stream.", "<session|host|model>",
                _h_focus),
    CommandSpec("explain", "WHY-trace ostatniej decyzji.",
                "WHY-trace last decision.", "", _h_explain),
    CommandSpec("findings", "Aktywne F-### w biezacej sesji.",
                "Active F-###.", "", _h_findings),
    CommandSpec("retry", "Powtorz biezacy task.", "Retry current task.", "",
                _h_retry),
    CommandSpec("diff", "Diff dwoch sesji event-po-event.",
                "Diff two sessions.", "sessions <id1> <id2>", _h_diff),
    CommandSpec("budget", "Budzet vs zuzycie projektu.",
                "Budget vs spend.", "", _h_budget),
    CommandSpec("priority", "Zmien priorytet biezacego taska.",
                "Change task priority.", "", _h_priority),
    CommandSpec("export", "Export sesji do JSON/MD.",
                "Export session.", "<format>", _h_export),
    CommandSpec("request", "Zglos prosbe operatorska, np. checkpoint.",
                "Operator request.", "checkpoint", _h_request),
    CommandSpec("report", "Raport runtime: current-run/workers/gates/tests/deploy/skills/council/costs/model-barriers/model-slots/council-sync/guard-decisions/debate-graph/dissent/loop-guard.",
                "Runtime report.", "<variant>", _h_report),
    CommandSpec("runtime-truth", "Faktyczny backend, porty, baza i worktree.",
                "Runtime truth: backend, ports, database and worktree.", "", _h_runtime_truth,
                aliases=("truth", "runtime")),
    CommandSpec("show", "Pokaż audit-tail albo aktywne blockery.",
                "Show audit tail, blockers, pending models or council state.", "audit-tail|blockers|pending-models|council-state", _h_show),
    CommandSpec("help", "Lista komend.", "Command list.", "", _h_help,
                aliases=("?",)),
    CommandSpec("host", "Drill-down do konkretnego hosta.",
                "Drill into host.", "<name>", _h_host),
    CommandSpec("model", "Filtruj activity stream do modelu.",
                "Filter by model.", "<name>", _h_model),
    CommandSpec("replay", "Odtworz historyczna sesje.",
                "Replay session.", "<session_id>", _h_replay),
)


# P1-2 fix: command names + aliases are restricted to a strict ASCII
# subset. Anything else (whitespace, slash, unicode letter, dot) would
# either collide with the parser's tokenizer (shlex) or fail to round-
# trip through casefold() — better to reject at import than to ship a
# silent shadow.
#
# Names: ``[a-z0-9_-]+``.
# Aliases: same set, plus the single short-form ``?`` (well-known
# operator UX shortcut for /help; ASCII punctuation, safe through shlex
# and casefold).
_VALID_NAME_RE = re.compile(r"^[a-z0-9_-]+$")
_VALID_ALIAS_RE = re.compile(r"^(?:[a-z0-9_-]+|\?)$")


def _validate_command_table(commands: tuple[CommandSpec, ...] = BUILTIN_COMMANDS) -> None:
    """P1-1 fix: enforce uniqueness of command names + aliases at load time.

    Also (P1-2 extension): enforce that every name and alias matches
    ``[a-z0-9_-]+`` — locking the alias surface so casefold() is a
    no-op on the canonical tokens and shlex tokenization is stable.

    Raises:
      ValueError if any name or alias contains characters outside the
        allowed set (P1-2 hardening).
      RuntimeError if any name appears twice, any alias appears twice,
        or any alias matches another command's name (P1-1).

    Use this from tests too::

        _validate_command_table(BUILTIN_COMMANDS)  # passes
        _validate_command_table(buggy_table)       # raises
    """
    # We compare with casefold() to stay symmetric with the parser
    # (parse_command does cmd_name.casefold() before lookup). For ASCII
    # tokens that pass _VALID_NAME_RE / _VALID_ALIAS_RE, casefold() is
    # a no-op — but being explicit hardens the contract.
    seen_names: dict[str, str] = {}     # casefolded token -> origin label
    for spec in commands:
        # P1-2: lock the surface — names must be [a-z0-9_-]+, aliases
        # the same set plus the single shortcut '?'.
        if not _VALID_NAME_RE.match(spec.name):
            raise ValueError(
                f"invalid command name '{spec.name}': must match "
                f"[a-z0-9_-]+ (no whitespace, slashes, or non-ASCII)"
            )
        for alias in spec.aliases:
            if not _VALID_ALIAS_RE.match(alias):
                raise ValueError(
                    f"invalid alias '{alias}' on command '{spec.name}': "
                    f"must match [a-z0-9_-]+ or '?' (no whitespace, "
                    f"slashes, or non-ASCII)"
                )

        # P1-1: collision check on the casefolded surface.
        name_key = spec.name.casefold()
        if name_key in seen_names:
            raise RuntimeError(
                f"command name collision: '{spec.name}' registered twice "
                f"(also in earlier command)"
            )
        seen_names[name_key] = spec.name
        for alias in spec.aliases:
            alias_key = alias.casefold()
            if alias_key in seen_names:
                raise RuntimeError(
                    f"alias collision: alias '{alias}' on command "
                    f"'{spec.name}' clashes with existing name/alias "
                    f"'{seen_names[alias_key]}'"
                )
            seen_names[alias_key] = f"{spec.name} (alias)"


# Run validation eagerly at import time. Fail-fast on misconfiguration.
_validate_command_table()


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def parse_command(
    line: str, ctx: Mapping[str, Any] | None = None
) -> CommandResult:
    """Sparsuj i wykonaj jedno polecenie.

    ``line`` musi zaczynac sie od ``/``. Argumenty pareowane przez
    ``shlex`` (cytowane wartosci dozwolone). ``ctx`` to dowolna mapa
    przekazywana do handlera (np. ``{"operator_id": "...", ...}``).

    P1-3 (foot-gun shutdown): ``ctx`` jest opakowywany w
    :class:`types.MappingProxyType` zanim trafi do handlera. Handlery
    MUSZA traktowac go jako read-only — proba mutacji
    (``ctx["x"] = 1``, ``ctx.update(...)``, ``del ctx["k"]``) podniesie
    ``TypeError`` z komunikatem typu "'mappingproxy' object does not
    support item assignment". Jezeli handler chce przekazac stan dla
    kolejnego kroku, MUSI zwrocic go w ``CommandResult.meta``, nie
    mutowac ``ctx``. Dzieki temu:
      * zadne ukryte side-effects miedzy wywolaniami,
      * caller widzi wlasny dict bez zmian,
      * nieswiadoma mutacja wybucha glosno w testach a nie cicho w
        produkcji.
    """
    line = line.strip()
    if not line.startswith("/"):
        return CommandResult(
            kind="error",
            text="Polecenia musza zaczynac sie od '/'. Wpisz /help aby zobaczyc liste.",
        )
    body = line[1:].strip()
    if not body:
        return CommandResult(kind="error", text="Pusta komenda. /help aby zobaczyc liste.")

    try:
        tokens = shlex.split(body, posix=True)
    except ValueError as exc:
        return CommandResult(kind="error", text=f"Blad parsowania argumentow: {exc}")
    if not tokens:
        return CommandResult(kind="error", text="Pusta komenda.")
    cmd_name, *args = tokens
    # P1-2 fix: use casefold() (Unicode-aware) not lower() so non-ASCII
    # operator input ("ß" → "ss", "ﬁ" → "fi", "Ł" → "ł") folds correctly
    # before alias lookup. _validate_command_table() folds the alias
    # surface with the same casefold() so the comparisons stay symmetric.
    cmd_name = cmd_name.casefold()

    spec = next((s for s in BUILTIN_COMMANDS if s.matches(cmd_name)), None)
    if not spec:
        return CommandResult(
            kind="error",
            text=f"Nieznana komenda: /{cmd_name}. Wpisz /help.",
        )
    if not spec.handler:
        return CommandResult(
            kind="not_implemented",
            text=f"Handler dla /{cmd_name} jeszcze nie podpiety (Phase 0).",
        )
    # P1-3: wrap ctx in MappingProxyType so handlers cannot accidentally
    # leak per-call state into a caller-shared dict. The proxy is built
    # over an *existing* mapping (no copy) — read-through, write-blocked.
    # ``dict(ctx)`` snapshot avoids the proxy reflecting later mutations
    # of the original dict mid-handler-call (defensive isolation).
    ctx_view: Mapping[str, Any] = MappingProxyType(dict(ctx) if ctx else {})
    try:
        return spec.handler(args, ctx_view)
    except (KeyboardInterrupt, SystemExit):
        # P0-1: never swallow shutdown signals.
        raise
    except asyncio.CancelledError:
        # P1-3 fix: CancelledError IS-A Exception in Python 3.8+, so the
        # broad ``except Exception`` below would silently swallow task
        # cancellation. When G2 makes handlers async, a cancelled task
        # MUST propagate up so the awaiting caller can clean up. Keep
        # this clause above the broad catch.
        raise
    except (ValueError, TypeError) as exc:
        # P0-1: programmer / argument errors — surface a sanitized first
        # line so the operator can correct their input. Strips URLs,
        # emails, and token-shaped substrings.
        return CommandResult(
            kind="error",
            text=f"Bledne uzycie /{cmd_name}: {_sanitize_error_text(str(exc))}",
        )
    except Exception:
        # P0-1: unexpected — log full traceback, return opaque error_id
        # to the operator so backend logs can be grep'd by that ID.
        # Defense in depth — terminal nigdy nie powinno zabic backendu.
        error_id = uuid.uuid4().hex[:8]
        log.exception(
            "commands./%s handler failed (error_id=%s)", cmd_name, error_id,
        )
        return CommandResult(
            kind="error",
            text=(
                f"Wewnetrzny blad handlera /{cmd_name} (error_id={error_id}). "
                f"Sprawdz logi backendu pod tym ID."
            ),
        )


def list_commands() -> list[dict[str, str]]:
    """Diagnostyczna lista wszystkich komend dla GET /api/v1/terminal/commands."""
    return [
        {
            "name": s.name,
            "args": s.args,
            "summary_pl": s.summary_pl,
            "summary_en": s.summary_en,
            "aliases": ",".join(s.aliases),
            "implemented": "yes" if s.handler else "no",
        }
        for s in BUILTIN_COMMANDS
    ]
