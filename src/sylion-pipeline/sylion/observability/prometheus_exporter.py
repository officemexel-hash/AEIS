"""
SYLION Observability -- Prometheus Exporter

Seeds the metrics registry with ≥20 AEIS metrics and provides
a helper to update gauges from live system state.
"""

from __future__ import annotations

import logging
from typing import Any

from .metrics_registry import MetricsRegistry, get_metrics_registry

log = logging.getLogger("sylion.observability.prometheus_exporter")


# ---------------------------------------------------------------------------
# Metric catalogue (≥20 metrics)
# ---------------------------------------------------------------------------

METRIC_SEED: list[dict[str, Any]] = [
    {"type": "counter", "name": "aeis_pipeline_runs_total", "desc": "Total pipeline runs", "labels": ["status", "decision_class"]},
    {"type": "counter", "name": "aeis_governance_tickets_total", "desc": "Governance tickets", "labels": ["origin", "gate_type", "priority", "state"]},
    {"type": "counter", "name": "aeis_skill_executions_total", "desc": "Skill executions", "labels": ["skill_id", "success"]},
    {"type": "gauge",   "name": "aeis_skill_loaded_count", "desc": "Currently loaded skills"},
    {"type": "counter", "name": "aeis_memory_evidence_appended_total", "desc": "Evidence items appended"},
    {"type": "counter", "name": "aeis_memory_search_total", "desc": "Memory searches", "labels": ["result_count_bucket"]},
    {"type": "counter", "name": "aeis_funding_calls_scanned_total", "desc": "Funding calls scanned", "labels": ["program"]},
    {"type": "counter", "name": "aeis_funding_submissions_total", "desc": "Funding submissions", "labels": ["program", "state"]},
    {"type": "counter", "name": "aeis_council_votes_total", "desc": "Council votes", "labels": ["decision_class", "outcome"]},
    {"type": "gauge",   "name": "aeis_worker_pool_size", "desc": "Worker pool size", "labels": ["type"]},
    {"type": "counter", "name": "aeis_worker_pool_orphans_total", "desc": "Worker pool orphans detected"},
    {"type": "counter", "name": "aeis_autonomy_transitions_total", "desc": "Autonomy state transitions", "labels": ["from_state", "to_state"]},
    {"type": "counter", "name": "aeis_audit_events_total", "desc": "Audit events", "labels": ["severity"]},
    {"type": "counter", "name": "aeis_security_profile_swaps_total", "desc": "Profile swaps", "labels": ["from", "to"]},
    {"type": "counter", "name": "aeis_mobile_notifications_sent_total", "desc": "Mobile notifications sent"},
    {"type": "counter", "name": "aeis_mobile_decisions_total", "desc": "Mobile decisions", "labels": ["decision"]},
    {"type": "histogram", "name": "aeis_pipeline_duration_seconds", "desc": "Pipeline run duration", "buckets": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0]},
    {"type": "histogram", "name": "aeis_council_vote_duration_seconds", "desc": "Council vote duration", "buckets": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]},
    {"type": "histogram", "name": "aeis_skill_execution_duration_seconds", "desc": "Skill execution duration", "buckets": [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]},
    {"type": "gauge",   "name": "aeis_http_requests_total", "desc": "HTTP requests (gauge mirror)", "labels": ["method", "path", "status"]},
]


def seed_metrics(registry: MetricsRegistry | None = None) -> MetricsRegistry:
    """Register all AEIS seed metrics."""
    reg = registry or get_metrics_registry()
    for spec in METRIC_SEED:
        try:
            if spec["type"] == "counter":
                reg.counter(spec["name"], spec.get("desc", ""), spec.get("labels"))
            elif spec["type"] == "gauge":
                reg.gauge(spec["name"], spec.get("desc", ""), spec.get("labels"))
            elif spec["type"] == "histogram":
                reg.histogram(spec["name"], spec.get("desc", ""), spec.get("labels"), spec.get("buckets"))
        except Exception as exc:
            log.warning("Failed to seed metric %s: %s", spec["name"], exc)
    log.info("Seeded %d metrics", len(METRIC_SEED))
    return reg


def update_live_gauges(registry: MetricsRegistry | None = None) -> None:
    """Update gauge values from live system state.

    Called periodically (e.g. by /metrics endpoint or background task).
    """
    reg = registry or get_metrics_registry()

    # --- Funding scanner (our scope) ---
    try:
        from sylion.funding_autopilot.store import FundingAutopilotStore
        from sylion.funding_autopilot.config import funding_db_path
        store = FundingAutopilotStore(db_path=funding_db_path())
        calls = store.list_calls()
        by_program: dict[str, int] = {}
        for c in calls:
            prog = c.get("programme_id", "unknown").replace("programme_", "")
            by_program[prog] = by_program.get(prog, 0) + 1
        for prog, cnt in by_program.items():
            reg.set("aeis_funding_calls_scanned_total", cnt, {"program": prog})
        store.close()
    except Exception as exc:
        log.debug("update_live_gauges funding: %s", exc)

    # --- Security dedup (our scope) ---
    try:
        from sylion.security.audit_trail_aggregator import get_audit_trail_aggregator
        agg = get_audit_trail_aggregator()
        stats = agg.get_stats()
        reg.set("aeis_audit_events_total", stats.get("total_entries", 0), {"severity": "all"})
    except Exception as exc:
        log.debug("update_live_gauges audit: %s", exc)

    # --- Placeholder: other domains will be wired by their owners ---
    # Skills, memory, council, worker, autonomy — A/B will increment counters
    # via get_metrics_registry().inc(...) in their modules.
