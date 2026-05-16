"""
SYLION API -- Monitoring routes.

Endpoints for: code_bloat, cost_envelope, self_observation, self_preservation,
              model_performance, anomaly_detector, notification_engine,
              sla_monitor, metric_aggregator, config_drift_detector.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sylion.efficiency.code_bloat import get_code_bloat_tracker
from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
from sylion.aeis.self_observation import get_self_observation
from sylion.aeis.self_preservation import get_self_preservation_engine

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "monitoring",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Code Bloat Tracker
# ---------------------------------------------------------------------------

@router.post("/bloat/measure")
def measure_bloat(module_id: str, loc: int, complexity: int,
                  files: int = 0, deps: int = 0):
    """Measure and record code bloat metrics for a module."""
    tracker = get_code_bloat_tracker()
    return tracker.measure(module_id, loc, complexity, files=files, deps=deps)


@router.get("/bloat/modules")
def list_bloat_modules(bloat_threshold: float | None = None):
    """List modules with bloat metrics, optionally filtered by threshold."""
    tracker = get_code_bloat_tracker()
    return {"modules": tracker.list_modules(bloat_threshold=bloat_threshold)}


@router.get("/bloat/modules/{module_id}")
def get_bloat_module(module_id: str):
    """Get bloat metrics for a specific module."""
    tracker = get_code_bloat_tracker()
    result = tracker.get_module(module_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not tracked")
    return result


@router.post("/bloat/delta")
def record_bloat_delta(module_id: str, before: int, after: int):
    """Record a lines-of-code delta for a module."""
    tracker = get_code_bloat_tracker()
    return tracker.record_delta(module_id, before, after)


@router.get("/bloat/history/{module_id}")
def get_bloat_history(module_id: str, limit: int = 20):
    """Get delta history for a module."""
    tracker = get_code_bloat_tracker()
    return {"history": tracker.get_history(module_id, limit=limit)}


@router.get("/bloat/budget/{module_id}")
def check_bloat_budget(module_id: str, budget_percent: float = 20.0):
    """Check if a module is within its code bloat budget."""
    tracker = get_code_bloat_tracker()
    within = tracker.is_within_budget(module_id, budget_percent)
    return {"module_id": module_id, "within_budget": within,
            "budget_percent": budget_percent}


# ---------------------------------------------------------------------------
# Cost Envelope Tracker
# ---------------------------------------------------------------------------

@router.post("/cost/records", status_code=201)
def record_cost(provider: str, model_id: str,
                input_tokens: int, output_tokens: int,
                cost_usd: float, task_type: str = ""):
    """Record an LLM cost entry."""
    tracker = get_cost_envelope_tracker()
    return tracker.record(provider, model_id, input_tokens, output_tokens,
                          cost_usd, task_type=task_type)


@router.get("/cost/records")
def list_cost_records(provider: str | None = None, limit: int = 100):
    """List recent cost records."""
    tracker = get_cost_envelope_tracker()
    return {"records": tracker.get_records(provider=provider, limit=limit)}


@router.post("/cost/budgets")
def set_cost_budget(provider: str, daily_limit: float = 0,
                    monthly_limit: float = 0,
                    alert_threshold: float = 0.8):
    """Set or update cost budget for a provider."""
    tracker = get_cost_envelope_tracker()
    return tracker.set_budget(provider, daily_limit=daily_limit,
                              monthly_limit=monthly_limit,
                              alert_threshold=alert_threshold)


@router.get("/cost/budgets/{provider}")
def check_cost_budget(provider: str):
    """Check spending against budget for a provider."""
    tracker = get_cost_envelope_tracker()
    return tracker.check_budget(provider)


@router.get("/cost/daily")
def daily_spend(provider: str | None = None):
    """Get total spend today."""
    tracker = get_cost_envelope_tracker()
    return {"daily_spend": tracker.get_daily_spend(provider)}


@router.get("/cost/monthly")
def monthly_spend(provider: str | None = None):
    """Get total spend this month."""
    tracker = get_cost_envelope_tracker()
    return {"monthly_spend": tracker.get_monthly_spend(provider)}


@router.get("/cost/within-budget/{provider}")
def check_within_budget(provider: str):
    """Check if a provider is within budget limits."""
    tracker = get_cost_envelope_tracker()
    within = tracker.is_within_budget(provider)
    return {"provider": provider, "within_budget": within}


# ---------------------------------------------------------------------------
# Self-Observation
# ---------------------------------------------------------------------------

@router.post("/observations", status_code=201)
def record_observation(metric: str, value: float, unit: str = "",
                       source: str = ""):
    """Record a metric observation."""
    observer = get_self_observation()
    return observer.record(metric, value, unit=unit, source=source)


@router.get("/observations/{metric}")
def get_observations(metric: str, limit: int = 100):
    """Get recent observations for a metric."""
    observer = get_self_observation()
    return {"observations": observer.get_observations(metric, limit=limit)}


@router.get("/observations/aggregate/{metric}")
def get_observation_aggregate(metric: str):
    """Get aggregate stats for a metric."""
    observer = get_self_observation()
    result = observer.get_aggregate(metric)
    if not result:
        raise HTTPException(status_code=404, detail=f"No aggregate for metric {metric}")
    return result


@router.get("/observations/dashboard")
def observation_dashboard():
    """Get all aggregate data for dashboard display."""
    observer = get_self_observation()
    return {"metrics": observer.get_dashboard()}


@router.get("/observations/stats")
def observation_stats():
    """Get observation statistics."""
    observer = get_self_observation()
    return observer.get_stats()


# ---------------------------------------------------------------------------
# Self-Preservation
# ---------------------------------------------------------------------------

@router.get("/preservation/mode")
def get_preservation_mode():
    """Get the current preservation mode."""
    engine = get_self_preservation_engine()
    return {"mode": engine.get_mode()}


@router.post("/preservation/mode")
def set_preservation_mode(mode: str):
    """Set the preservation mode (normal/caution/critical/shutdown)."""
    engine = get_self_preservation_engine()
    try:
        return engine.set_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/preservation/health")
def get_health_score():
    """Get the overall health score."""
    engine = get_self_preservation_engine()
    return {"health_score": engine.get_health_score()}


@router.post("/preservation/checks", status_code=201)
def check_health(component: str, status: str = "healthy",
                 message: str = "", score: float = 1.0):
    """Record a component health check."""
    engine = get_self_preservation_engine()
    return engine.check_health(component, status=status,
                               message=message, score=score)


@router.get("/preservation/checks")
def list_health_checks(component: str | None = None, limit: int = 50):
    """List health checks."""
    engine = get_self_preservation_engine()
    return {"checks": engine.get_checks(component=component, limit=limit)}


@router.get("/preservation/should-shutdown")
def should_shutdown():
    """Check if the system should initiate safety shutdown."""
    engine = get_self_preservation_engine()
    return {"should_shutdown": engine.should_shutdown()}


@router.get("/preservation/stats")
def preservation_stats():
    """Get preservation statistics."""
    engine = get_self_preservation_engine()
    return engine.get_stats()


# ---------------------------------------------------------------------------
# Model Performance Tracker -- lazy accessor
# ---------------------------------------------------------------------------

_perf = None


def _get_perf():
    global _perf
    if _perf is not None:
        return _perf
    from sylion.monitoring.model_performance import get_model_performance
    _perf = get_model_performance()
    return _perf


# ---------------------------------------------------------------------------
# Model Performance Tracker -- request models
# ---------------------------------------------------------------------------

class CompareModelsRequest(BaseModel):
    model_ids: list[str]
    metric_type: str
    from_time: Optional[float] = None
    to_time: Optional[float] = None


class RecordMetricRequest(BaseModel):
    model_id: str
    metric_type: str
    value: float
    unit: str
    task_type: Optional[str] = None
    session_id: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# Model Performance Tracker -- endpoints
# (static routes before parameterized /{model_id} routes)
# ---------------------------------------------------------------------------

@router.get("/performance/metrics")
def get_metrics(model_id: Optional[str] = None,
                metric_type: Optional[str] = None,
                task_type: Optional[str] = None,
                from_time: Optional[float] = None,
                to_time: Optional[float] = None,
                limit: int = 100):
    """Return metrics matching the given filters."""
    perf = _get_perf()
    return {"metrics": perf.get_metrics(
        model_id=model_id,
        metric_type=metric_type,
        task_type=task_type,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
    )}


@router.get("/performance/summaries")
def get_all_summaries():
    """Return performance summaries for all models."""
    perf = _get_perf()
    return {"summaries": perf.get_all_summaries()}


@router.get("/performance/leaderboard")
def get_leaderboard(metric_type: str = "quality_score",
                    task_type: Optional[str] = None,
                    limit: int = 10):
    """Rank models by average value of a metric type."""
    perf = _get_perf()
    return {"leaderboard": perf.get_leaderboard(
        metric_type=metric_type,
        task_type=task_type,
        limit=limit,
    )}


@router.post("/performance/compare")
def compare_models(body: CompareModelsRequest):
    """Compare models side by side on a metric type."""
    perf = _get_perf()
    return {"comparison": perf.get_model_comparison(
        model_ids=body.model_ids,
        metric_type=body.metric_type,
        from_time=body.from_time,
        to_time=body.to_time,
    )}


@router.get("/performance/anomalies")
def detect_anomalies(model_id: Optional[str] = None,
                     window_seconds: float = 3600):
    """Detect unusual metric values within the given time window."""
    perf = _get_perf()
    return {"anomalies": perf.detect_anomalies(
        model_id=model_id,
        window_seconds=window_seconds,
    )}


@router.get("/performance/summary/{model_id}")
def get_model_summary(model_id: str):
    """Return the performance summary for a model."""
    perf = _get_perf()
    summary = perf.get_model_summary(model_id)
    if not summary:
        raise HTTPException(status_code=404,
                            detail=f"Model {model_id} not tracked")
    return summary


@router.get("/performance/trend/{model_id}")
def get_trend(model_id: str, metric_type: str = "quality_score",
              hours: float = 24):
    """Return time-series data for charting a model's metric."""
    perf = _get_perf()
    return {"trend": perf.get_trend(model_id, metric_type, hours=hours)}


@router.post("/performance/record", status_code=201)
def record_metric(body: RecordMetricRequest):
    """Record a performance metric for a model."""
    perf = _get_perf()
    return perf.record_metric(
        model_id=body.model_id,
        metric_type=body.metric_type,
        value=body.value,
        unit=body.unit,
        task_type=body.task_type,
        session_id=body.session_id,
        pipeline_run_id=body.pipeline_run_id,
        metadata=body.metadata,
    )


# ---------------------------------------------------------------------------
# Notification Engine
# ---------------------------------------------------------------------------

from sylion.monitoring.notification_engine import get_notification_engine


@router.get("/notifications/stats")
def notification_stats(user_id: str | None = None):
    """Get notification statistics."""
    ne = get_notification_engine()
    return ne.get_notification_stats(user_id=user_id)


@router.get("/notifications/unread-count/{user_id}")
def notification_unread_count(user_id: str):
    """Get unread notification count for a user."""
    ne = get_notification_engine()
    return {"count": ne.get_unread_count(user_id)}


@router.post("/notifications")
def send_notification(user_id: str, title: str, message: str,
                      category: str = "system", priority: str = "info",
                      metadata: str = ""):
    """Send a notification to a user."""
    import json as _json
    ne = get_notification_engine()
    md = _json.loads(metadata) if metadata else None
    return ne.send_notification(user_id, title, message,
                                category=category, priority=priority,
                                metadata=md)


@router.get("/notifications")
def list_notifications(user_id: str | None = None,
                       category: str | None = None,
                       priority: str | None = None,
                       unread_only: bool = False,
                       limit: int = 50):
    """List notifications with optional filters."""
    ne = get_notification_engine()
    return {"notifications": ne.list_notifications(
        user_id=user_id, category=category, priority=priority,
        unread_only=unread_only, limit=limit,
    )}


@router.get("/notifications/{notification_id}")
def get_notification(notification_id: str):
    """Get a notification by ID."""
    ne = get_notification_engine()
    result = ne.get_notification(notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str):
    """Mark a notification as read."""
    ne = get_notification_engine()
    result = ne.mark_read(notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found or already read")
    return result


@router.post("/notifications/read-all/{user_id}")
def mark_all_notifications_read(user_id: str):
    """Mark all notifications as read for a user."""
    ne = get_notification_engine()
    count = ne.mark_all_read(user_id)
    return {"marked_count": count}


@router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: str):
    """Delete a notification."""
    ne = get_notification_engine()
    ok = ne.delete_notification(notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"deleted": notification_id}


@router.post("/notifications/preferences")
def set_notification_preference(user_id: str, category: str,
                                channel: str = "in_app",
                                enabled: bool = True):
    """Set a notification preference."""
    ne = get_notification_engine()
    return ne.set_preference(user_id, category, channel=channel, enabled=enabled)


@router.get("/notifications/preferences/{user_id}")
def get_notification_preferences(user_id: str):
    """Get notification preferences for a user."""
    ne = get_notification_engine()
    return {"preferences": ne.get_preferences(user_id)}


@router.post("/notifications/channels")
def register_notification_channel(user_id: str, channel_type: str,
                                  config: str = ""):
    """Register a notification channel for a user."""
    import json as _json
    ne = get_notification_engine()
    cfg = _json.loads(config) if config else None
    return ne.register_channel(user_id, channel_type, config=cfg)


@router.get("/notifications/channels/{user_id}")
def get_notification_channels(user_id: str):
    """Get notification channels for a user."""
    ne = get_notification_engine()
    return {"channels": ne.get_channels(user_id)}


@router.post("/notifications/bulk")
def bulk_notify(user_ids: str = "[]", title: str = "", message: str = "",
                category: str = "system", priority: str = "info"):
    """Send notification to multiple users."""
    import json as _json
    ne = get_notification_engine()
    ids = _json.loads(user_ids) if isinstance(user_ids, str) else user_ids
    return {"notifications": ne.bulk_notify(
        ids, title, message, category=category, priority=priority,
    )}


@router.post("/notifications/cleanup")
def cleanup_read_notifications(older_than_days: int = 30):
    """Clean up read notifications older than N days."""
    ne = get_notification_engine()
    count = ne.cleanup_read(older_than_days=older_than_days)
    return {"removed": count}


# ---------------------------------------------------------------------------
# Anomaly Detector -- lazy accessor
# ---------------------------------------------------------------------------

_anomaly_detector = None


def _get_anomaly_detector():
    global _anomaly_detector
    if _anomaly_detector is not None:
        return _anomaly_detector
    from sylion.monitoring.anomaly_detector import get_anomaly_detector
    _anomaly_detector = get_anomaly_detector()
    return _anomaly_detector


# ---------------------------------------------------------------------------
# Anomaly Detector -- request models
# ---------------------------------------------------------------------------

class RecordObservationRequest(BaseModel):
    metric_name: str
    module_id: str
    value: float


# ---------------------------------------------------------------------------
# Anomaly Detector -- endpoints
# (static routes before parameterized /{anomaly_id} routes)
# ---------------------------------------------------------------------------

@router.post("/anomalies/observe", status_code=201)
def record_anomaly_observation(body: RecordObservationRequest):
    """Record a metric observation and check for anomalies."""
    detector = _get_anomaly_detector()
    return detector.record_observation(
        body.metric_name, body.module_id, body.value,
    )


@router.get("/anomalies/baselines")
def list_anomaly_baselines(module_id: str | None = None):
    """List all metric baselines, optionally filtered by module_id."""
    detector = _get_anomaly_detector()
    return {"baselines": detector.list_baselines(module_id=module_id)}


@router.get("/anomalies/baselines/{metric_name}")
def get_anomaly_baselines_by_metric(metric_name: str):
    """Compatibility endpoint for metric-only baseline cards."""
    detector = _get_anomaly_detector()
    baselines = [
        item for item in detector.list_baselines(module_id=None)
        if item.get("metric_name") == metric_name
    ]
    return {"metric_name": metric_name, "baselines": baselines, "count": len(baselines)}


@router.get("/anomalies/baseline/{metric_name}/{module_id}")
def get_anomaly_baseline(metric_name: str, module_id: str):
    """Get the baseline for a specific metric / module pair."""
    detector = _get_anomaly_detector()
    result = detector.get_baseline(metric_name, module_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No baseline for {metric_name}/{module_id}")
    return result


@router.get("/anomalies")
def list_anomalies(module_id: Optional[str] = None,
                   severity: Optional[str] = None,
                   status: Optional[str] = None,
                   limit: int = 100):
    """List anomalies with optional filters."""
    detector = _get_anomaly_detector()
    return {"anomalies": detector.list_anomalies(
        module_id=module_id, severity=severity,
        status=status, limit=limit,
    )}


@router.get("/anomalies/stats")
def anomaly_detector_stats():
    """Get aggregate anomaly detector statistics."""
    return _get_anomaly_detector().get_stats()


@router.post("/anomalies/{anomaly_id}/resolve")
def resolve_anomaly(anomaly_id: str):
    """Mark an anomaly as resolved."""
    detector = _get_anomaly_detector()
    resolved = detector.resolve_anomaly(anomaly_id)
    if not resolved:
        raise HTTPException(status_code=404,
                            detail=f"Anomaly {anomaly_id} not found")
    return {"resolved": anomaly_id}


# ---------------------------------------------------------------------------
# SLA Monitor -- lazy accessor
# ---------------------------------------------------------------------------

_sla_monitor = None


def _get_sla_monitor():
    global _sla_monitor
    if _sla_monitor is not None:
        return _sla_monitor
    from sylion.monitoring.sla_monitor import get_sla_monitor
    _sla_monitor = get_sla_monitor()
    return _sla_monitor


# ---------------------------------------------------------------------------
# SLA Monitor -- endpoints
# (static routes before parameterized /{sla_id} routes)
# ---------------------------------------------------------------------------

@router.post("/sla", status_code=201)
def define_sla(name: str, target_metric: str, target_value: float,
               threshold: float, window_seconds: int = 300):
    """Define a new SLA."""
    monitor = _get_sla_monitor()
    try:
        return monitor.define_sla(name, target_metric, target_value,
                                  threshold, window_seconds=window_seconds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sla")
def list_slas(target_metric: Optional[str] = None,
              enabled: Optional[bool] = None):
    """List SLA definitions, optionally filtered by metric and/or enabled."""
    monitor = _get_sla_monitor()
    return {"slas": monitor.list_slas(target_metric=target_metric,
                                      enabled=enabled)}


@router.get("/sla/stats")
def sla_stats():
    """Get aggregate SLA compliance statistics."""
    monitor = _get_sla_monitor()
    return monitor.get_stats()


@router.get("/sla/checks")
def list_sla_checks(sla_id: Optional[str] = None,
                    compliant: Optional[bool] = None,
                    limit: int = 100):
    """List SLA checks with optional filters."""
    monitor = _get_sla_monitor()
    return {"checks": monitor.list_checks(sla_id=sla_id,
                                          compliant=compliant,
                                          limit=limit)}


@router.get("/sla/breaches")
def list_sla_breaches(sla_id: Optional[str] = None,
                      status: Optional[str] = None,
                      limit: int = 100):
    """List SLA breaches with optional filters."""
    monitor = _get_sla_monitor()
    try:
        return {"breaches": monitor.list_breaches(sla_id=sla_id,
                                                   status=status,
                                                   limit=limit)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sla/{sla_id}")
def get_sla(sla_id: str):
    """Get a single SLA definition by ID."""
    monitor = _get_sla_monitor()
    result = monitor.get_sla(sla_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"SLA {sla_id} not found")
    return result


@router.get("/sla/policies/{policy_id}/compliance")
def get_sla_policy_compliance(policy_id: str):
    """Compatibility endpoint for SLA policy compliance dashboard cards."""
    monitor = _get_sla_monitor()
    sla = monitor.get_sla(policy_id)
    if not sla:
        raise HTTPException(status_code=404,
                            detail=f"SLA {policy_id} not found")
    checks = monitor.list_checks(sla_id=policy_id, limit=100)
    compliant = [item for item in checks if item.get("compliant")]
    return {
        "policy_id": policy_id,
        "sla": sla,
        "checks": checks,
        "compliance_rate": (len(compliant) / len(checks)) if checks else None,
    }


@router.put("/sla/{sla_id}")
def update_sla(sla_id: str, enabled: Optional[bool] = None):
    """Update an SLA definition (toggle enabled)."""
    monitor = _get_sla_monitor()
    result = monitor.update_sla(sla_id, enabled=enabled)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"SLA {sla_id} not found")
    return result


@router.post("/sla/{sla_id}/check")
def check_sla(sla_id: str, actual_value: float):
    """Perform an SLA compliance check against an actual value."""
    monitor = _get_sla_monitor()
    try:
        return monitor.check_sla(sla_id, actual_value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sla/breaches/{breach_id}/resolve")
def resolve_sla_breach(breach_id: str):
    """Resolve an active SLA breach."""
    monitor = _get_sla_monitor()
    result = monitor.resolve_breach(breach_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Breach {breach_id} not found")
    return result


# ---------------------------------------------------------------------------
# Metric Aggregator -- lazy accessor
# ---------------------------------------------------------------------------

_metric_aggregator = None


def _get_metric_aggregator():
    global _metric_aggregator
    if _metric_aggregator is not None:
        return _metric_aggregator
    from sylion.monitoring.metric_aggregator import get_metric_aggregator
    _metric_aggregator = get_metric_aggregator()
    return _metric_aggregator


# ---------------------------------------------------------------------------
# Metric Aggregator -- endpoints
# (static routes before parameterized /{metric_name} routes)
# ---------------------------------------------------------------------------

@router.post("/metrics", status_code=201)
def record_metric_point(metric_name: str, value: float, source: str = "",
                        tags: str = ""):
    """Record a metric data point."""
    import json as _json
    agg = _get_metric_aggregator()
    parsed_tags = _json.loads(tags) if tags else None
    return agg.record(metric_name, value, source=source, tags=parsed_tags)


@router.get("/metrics")
def get_metric_points(metric_name: Optional[str] = None,
                      source: Optional[str] = None,
                      since: Optional[float] = None,
                      limit: int = 1000):
    """List raw metric points with optional filters."""
    agg = _get_metric_aggregator()
    if metric_name is None:
        raise HTTPException(status_code=400,
                            detail="metric_name is required")
    return {"points": agg.get_points(metric_name, source=source,
                                     since=since, limit=limit)}


@router.get("/metrics/stats")
def metric_stats():
    """Get aggregate metric store statistics."""
    agg = _get_metric_aggregator()
    return agg.get_stats()


@router.post("/metrics/aggregate")
def aggregate_metrics(metric_name: str, period: str = "1h",
                      source: Optional[str] = None):
    """Compute aggregates for a metric over the given period."""
    agg = _get_metric_aggregator()
    try:
        result = agg.aggregate(metric_name, period=period, source=source)
        return {"aggregates": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/metrics/aggregates")
def get_metric_aggregates(metric_name: str, period: Optional[str] = None,
                          limit: int = 100):
    """List stored aggregates for a metric."""
    agg = _get_metric_aggregator()
    return {"aggregates": agg.get_aggregates(metric_name, period=period,
                                             limit=limit)}


@router.get("/metrics/latest/{metric_name}")
def get_latest_metric(metric_name: str, source: Optional[str] = None):
    """Get the most recent data point for a metric."""
    agg = _get_metric_aggregator()
    result = agg.get_latest(metric_name, source=source)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No data for metric {metric_name}")
    return result


@router.get("/metrics/{metric_name}/buckets")
def get_metric_buckets(metric_name: str, bucket_size: str = "1h", limit: int = 100):
    """Compatibility endpoint for bucketed metric dashboard charts."""
    agg = _get_metric_aggregator()
    return {
        "metric_name": metric_name,
        "bucket_size": bucket_size,
        "buckets": agg.get_aggregates(metric_name, period=bucket_size, limit=limit),
    }


# ---------------------------------------------------------------------------
# Config Drift Detector -- lazy accessor
# ---------------------------------------------------------------------------

_config_drift = None


def _get_config_drift():
    global _config_drift
    if _config_drift is not None:
        return _config_drift
    from sylion.monitoring.config_drift_detector import get_config_drift_detector
    _config_drift = get_config_drift_detector()
    return _config_drift


# ---------------------------------------------------------------------------
# Config Drift Detector -- endpoints
# (static routes before parameterized /{report_id} routes)
# ---------------------------------------------------------------------------

@router.post("/drift/baselines", status_code=201)
def set_drift_baseline(module_id: str, config_key: str, expected_value: str):
    """Set or update an expected configuration baseline."""
    detector = _get_config_drift()
    return detector.set_baseline(module_id, config_key, expected_value)


@router.get("/drift/baselines")
def get_drift_baselines(module_id: Optional[str] = None):
    """List baselines, optionally filtered by module_id."""
    detector = _get_config_drift()
    return {"baselines": detector.get_baselines(module_id=module_id)}


@router.post("/drift/check")
def check_config_drift(module_id: str, config_key: str, actual_value: str):
    """Compare an actual value against the expected baseline."""
    detector = _get_config_drift()
    return detector.check_drift(module_id, config_key, actual_value)


@router.post("/drift/full-check")
def run_full_drift_check(module_id: Optional[str] = None):
    """Run a full drift check and generate a report."""
    detector = _get_config_drift()
    return detector.run_full_check(module_id=module_id)


@router.get("/drift/reports")
def list_drift_reports(module_id: Optional[str] = None,
                       severity: Optional[str] = None,
                       status: Optional[str] = None,
                       limit: int = 50):
    """List drift reports with optional filters."""
    detector = _get_config_drift()
    return {"reports": detector.list_drift_reports(module_id=module_id,
                                                    severity=severity,
                                                    status=status,
                                                    limit=limit)}


@router.get("/drift/stats")
def drift_stats():
    """Get aggregate drift detector statistics."""
    detector = _get_config_drift()
    return detector.get_stats()


@router.get("/drift/snapshots/{snapshot_id}")
def get_drift_snapshot(snapshot_id: str):
    """Compatibility endpoint mapping snapshot cards to drift reports."""
    detector = _get_config_drift()
    reports = detector.list_drift_reports(limit=1000)
    for report in reports:
        if report.get("report_id") == snapshot_id or report.get("snapshot_id") == snapshot_id:
            return report
    raise HTTPException(status_code=404,
                        detail=f"Drift snapshot {snapshot_id} not found")


@router.post("/drift/reports/{report_id}/resolve")
def resolve_drift_report(report_id: str):
    """Mark a drift report as resolved."""
    detector = _get_config_drift()
    resolved = detector.resolve_drift(report_id)
    if not resolved:
        raise HTTPException(status_code=404,
                            detail=f"Drift report {report_id} not found")
    return {"resolved": report_id}
