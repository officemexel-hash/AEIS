"""SYLION AEIS v2 — Prometheus metrics endpoint.

Sprint 2 day 6/7 deliverable. Exposes a single GET /api/v1/metrics/v2
endpoint that returns plain-text Prometheus exposition format covering
the v2 surface area:

    sylion_v2_audit_chain_size{module}            — chained JSONL row counts
    sylion_v2_audit_chain_violations_total{module} — verify_chain fault counts
    sylion_v2_embeddings_cache_size                — idea cache row count
    sylion_v2_embeddings_cache_hit_rate            — sampled hit rate
    sylion_v2_gdpr_dsr_actions_total{action}       — counter (computed from JSONL)
    sylion_v2_council_decisions_total{verdict}     — counter (from JSONL)
    sylion_v2_replay_runs_total                    — counter (from JSONL)

Implementation notes:

* No ``prometheus-client`` dependency — the format is simple enough to
  emit by hand and we want to keep v2 deps minimal.
* All counters are recomputed on each scrape from the chained audit
  JSONL files. This is O(n) per scrape, and daily JSONL rotation
  bounds the worst-case cost below 100ms/scrape on typical workloads.
* RBAC: ``auditor`` or ``owner`` only — operators get the cheaper
  /api/v1/health/v2 endpoint instead.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics_v2"])

#: Default audit JSONL log root. Mirrors the v2 convention used by
#: gdpr_dsr / replay_fork / council_wedge / hard_purge:
#: every producer at ``aeis_v2/<sub>/<module>.py`` writes to
#: ``parents[3] / logs / v2``. From ``api/metrics_v2_routes.py`` the
#: equivalent is ``parents[2] / logs / v2`` (one level shallower because
#: ``api/`` and ``aeis_v2/`` share the same parent ``sylion/``).
#:
#: Bug fixed at runtime check 2026-04-28: previous ``parents[1]`` pointed
#: to ``sylion-pipeline/sylion/logs/v2`` which is WRONG — actual logs live
#: at ``sylion-pipeline/logs/v2``. Counters always read 0 in production.
_DEFAULT_LOG_ROOT = (
    Path(__file__).resolve().parents[2] / "logs" / "v2"
)

#: Mapping ``module_label -> (filename, default_action_label)``. Used by
#: the action-counter computation below.
_AUDIT_FILES: dict[str, str] = {
    "gdpr_dsr": "gdpr_dsr.jsonl",
    "gdpr_hard_purge": "gdpr_hard_purge.jsonl",
    "replay_fork": "replay_fork.jsonl",
    "council_wedge": "council_wedge.jsonl",
}


def _format_metric_line(
    name: str,
    value: float,
    labels: dict[str, str] | None = None,
) -> str:
    """Format a single Prometheus metric line."""
    if not labels:
        return f"{name} {value}"
    label_str = ",".join(
        f'{k}="{_escape(str(v))}"' for k, v in sorted(labels.items())
    )
    return f"{name}{{{label_str}}} {value}"


def _escape(s: str) -> str:
    """Prometheus label value escaping (limited to common cases)."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _safe_iter_chain_contents(path: Path) -> Iterable[dict[str, Any]]:
    """Yield ``content`` dicts from a chained JSONL file.

    Skips unparseable lines silently — the audit-chain integrity
    checker is a separate metric, not a parser strictness gate.
    """
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    d = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                content = d.get("content")
                if isinstance(content, dict):
                    yield content
    except OSError as exc:
        log.warning("metrics_v2: read failed for %s (%s)", path, exc)


def _count_chain_rows(path: Path) -> int:
    """Return the number of rows in a JSONL file (0 if missing)."""
    if not path.exists():
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def _legacy_line_numbers(path: Path) -> set[int]:
    """Return 1-based line numbers in ``path`` that are pre-migration legacy
    raw rows (no ``prev_hash`` AND no ``content_hash`` fields).

    Mixed files like ``council_wedge.jsonl`` have a contiguous legacy
    prefix and a chained tail (the tail starts at GENESIS so it's a valid
    sub-chain). The CLI ``verify_audit_chains.py`` treats whole-file legacy
    layouts as out-of-scope; for mixed files we have to filter per-line.
    """
    import json as _json

    out: set[int] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln, raw in enumerate(f, start=1):
                s = raw.strip()
                if not s:
                    continue
                try:
                    d = _json.loads(s)
                except _json.JSONDecodeError:
                    continue
                if not isinstance(d, dict):
                    continue
                if "prev_hash" not in d and "content_hash" not in d:
                    out.add(ln)
    except OSError:
        return out
    return out


def _count_violations(path: Path) -> int:
    """Return the number of tampered rows reported by verify_chain,
    EXCLUDING legacy raw-JSONL rows that pre-date the chain migration.

    Bug fixed 2026-04-28: ``council_wedge.jsonl`` is a mixed file (98
    legacy rows + 45 chained rows starting fresh at GENESIS). Naive
    ``len(verify_chain(path))`` returned 98 false-positive violations,
    which made ``sylion_v2_audit_chain_violations_total{module="council_wedge"}``
    fire synthetic alerts. The CLI already treats whole-file legacy layouts
    as out-of-scope; the metric now does the same per-line.
    """
    if not path.exists():
        return 0
    raw_faults = verify_chain(path)
    if not raw_faults:
        return 0
    legacy_lines = _legacy_line_numbers(path)
    return sum(1 for f in raw_faults if f.line_no not in legacy_lines)


def _aggregate_dsr_actions(path: Path) -> dict[str, int]:
    """Tally ``content.action`` values for the GDPR DSR JSONL stream."""
    counts: dict[str, int] = {}
    for c in _safe_iter_chain_contents(path):
        action = str(c.get("action") or "unknown")
        counts[action] = counts.get(action, 0) + 1
    return counts


def _aggregate_council_decisions(path: Path) -> dict[str, int]:
    """Tally Council Hybrid wedge verdicts."""
    counts: dict[str, int] = {}
    for c in _safe_iter_chain_contents(path):
        if c.get("kind") != "council_wedge.decision":
            continue
        verdict = str(c.get("verdict") or "unknown")
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts


def _count_replay_runs(path: Path) -> int:
    """Tally replay_fork.run rows."""
    return sum(
        1 for c in _safe_iter_chain_contents(path)
        if c.get("kind") == "replay_fork.run"
    )


def _effective_log_root(explicit_root: Path | None = None) -> Path:
    """Resolve the chain root, respecting audit profile mode."""
    if explicit_root is not None:
        return explicit_root
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_dir

        return resolve_audit_chain_dir(_DEFAULT_LOG_ROOT)
    except Exception:  # noqa: BLE001
        return _DEFAULT_LOG_ROOT


def _embeddings_stats() -> dict[str, float]:
    """Pull idea-cache stats lazily — never raises if module is unloaded."""
    try:
        from sylion.aeis_v2.apps_v2 import idea_embedding_cache_stats

        return idea_embedding_cache_stats()  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics_v2: embeddings stats fetch failed (%s)", exc)
        return {"hits": 0, "misses": 0, "size": 0, "hit_rate": 0.0}


def render_metrics(log_root: Path | None = None) -> str:
    """Render the v2 metrics page as Prometheus exposition text.

    Pure function with explicit ``log_root`` so tests can pass a tmp_path.
    """
    root = _effective_log_root(log_root)
    lines: list[str] = []

    # 1) audit_chain_size + audit_chain_violations.
    lines.append("# HELP sylion_v2_audit_chain_size rows in chained JSONL stream")
    lines.append("# TYPE sylion_v2_audit_chain_size gauge")
    for module, fname in _AUDIT_FILES.items():
        path = root / fname
        size = _count_chain_rows(path)
        lines.append(_format_metric_line(
            "sylion_v2_audit_chain_size", size, {"module": module},
        ))

    lines.append("# HELP sylion_v2_audit_chain_violations_total tampered row count")
    lines.append("# TYPE sylion_v2_audit_chain_violations_total counter")
    for module, fname in _AUDIT_FILES.items():
        path = root / fname
        viol = _count_violations(path)
        lines.append(_format_metric_line(
            "sylion_v2_audit_chain_violations_total", viol, {"module": module},
        ))

    # 2) GDPR DSR action counts.
    dsr_path = root / "gdpr_dsr.jsonl"
    actions = _aggregate_dsr_actions(dsr_path)
    lines.append("# HELP sylion_v2_gdpr_dsr_actions_total DSR action count by type")
    lines.append("# TYPE sylion_v2_gdpr_dsr_actions_total counter")
    for action in ("access", "rectification", "erasure", "portability"):
        lines.append(_format_metric_line(
            "sylion_v2_gdpr_dsr_actions_total",
            actions.get(action, 0),
            {"action": action},
        ))

    # 3) Council decisions by verdict.
    council_path = root / "council_wedge.jsonl"
    council = _aggregate_council_decisions(council_path)
    lines.append("# HELP sylion_v2_council_decisions_total council verdicts")
    lines.append("# TYPE sylion_v2_council_decisions_total counter")
    for verdict in ("approve", "reject", "conditional", "tie", "no_data"):
        lines.append(_format_metric_line(
            "sylion_v2_council_decisions_total",
            council.get(verdict, 0),
            {"verdict": verdict},
        ))

    # 4) Replay runs.
    replay_path = root / "replay_fork.jsonl"
    replay_runs = _count_replay_runs(replay_path)
    lines.append("# HELP sylion_v2_replay_runs_total replay-as-fork executions")
    lines.append("# TYPE sylion_v2_replay_runs_total counter")
    lines.append(_format_metric_line("sylion_v2_replay_runs_total", replay_runs))

    # 5) Adapter Bus v2 metrics (sprint 3 W11 instrumentation).
    try:
        from sylion.aeis_v2.adapter_bus_v2.metrics import (
            render_adapter_bus_metrics,
        )

        ab_text = render_adapter_bus_metrics()
        if ab_text.strip():
            lines.append(ab_text.rstrip())
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics_v2: adapter_bus metrics fetch failed (%s)", exc)

    # 5b) W19 evaluator metrics (sprint 4 instrumentation).
    try:
        from sylion.aeis_v2.policy_v2.metrics import render_w19_metrics

        w19_text = render_w19_metrics()
        if w19_text.strip():
            lines.append(w19_text.rstrip())
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics_v2: w19 metrics fetch failed (%s)", exc)

    # 6) Embeddings cache stats.
    es = _embeddings_stats()
    lines.append("# HELP sylion_v2_embeddings_cache_size cached idea-text rows")
    lines.append("# TYPE sylion_v2_embeddings_cache_size gauge")
    lines.append(_format_metric_line(
        "sylion_v2_embeddings_cache_size", float(es.get("size") or 0),
    ))
    lines.append("# HELP sylion_v2_embeddings_cache_hit_rate idea cache hit ratio")
    lines.append("# TYPE sylion_v2_embeddings_cache_hit_rate gauge")
    lines.append(_format_metric_line(
        "sylion_v2_embeddings_cache_hit_rate",
        float(es.get("hit_rate") or 0.0),
    ))

    return "\n".join(lines) + "\n"


@router.get(
    "/v2",
    response_class=PlainTextResponse,
    dependencies=[Depends(requires_role("auditor", "owner"))],
)
def metrics_v2() -> str:
    """Return the v2 metrics page in Prometheus exposition format."""
    return render_metrics()
