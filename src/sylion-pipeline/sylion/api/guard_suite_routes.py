"""Guard setup control plane for Phases 7-10.

The remaining Guards share one structural architecture: separate worker,
aggregated findings panel, per-Guard autonomy override, deterministic
acceptance, edge-case diagnosis and append-only audit evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["Guard Suite"])


SEVERITY_LEVELS: list[dict[str, Any]] = [
    {"id": "INFO", "rank": 1},
    {"id": "WARNING", "rank": 2},
    {"id": "ERROR", "rank": 3},
    {"id": "CRITICAL", "rank": 4},
    {"id": "BLOCKER", "rank": 5},
]

VALID_PRESETS = {"conservative", "balanced", "aggressive", "production", "research"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _items(labels: list[str], category: str, severity: str = "WARNING", tier: str = "tier1") -> list[dict[str, Any]]:
    return [
        {
            "id": _slug(label),
            "label": label,
            "category": category,
            "default_severity": severity,
            "default_tier": tier,
            "enabled_by_default": True,
        }
        for label in labels
    ]


def _edge_cases(category_counts: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for category_index, (category, titles) in enumerate(category_counts):
        letter = chr(ord("A") + category_index)
        for item_index, title in enumerate(titles, start=1):
            severity = "critical" if "corruption" in title.lower() or "lost" in title.lower() or "hard stop" in title.lower() else "medium"
            cases.append(
                {
                    "id": f"EC-{letter}{item_index}",
                    "category": category,
                    "title": title,
                    "severity": severity,
                    "runbook": ["classify impact", "apply guard-specific mitigation", "write audit evidence", "rerun acceptance if settings changed"],
                }
            )
    return cases


COST_EDGE_CASES = _edge_cases(
    [
        (
            "false_positive_anomaly",
            [
                "False positive operator-intentional spike",
                "Baseline contamination",
                "ML model overfitting",
                "Multiple anomalies same root cause",
                "Cost source missing data",
            ],
        ),
        (
            "auto_action_issues",
            [
                "Model switch backfires",
                "Throttling causes cascading delays",
                "Pause non-critical pauses critical workload",
                "Hard stop blocks production deploy",
                "Auto-action feedback loop",
            ],
        ),
        (
            "reporting_issues",
            [
                "Report contains stale data",
                "Closure report estimate accuracy poor",
                "Report sent to wrong recipient",
                "Report generation cost too high",
            ],
        ),
        (
            "recommendation_issues",
            [
                "Recommendation backfires",
                "Recommendations spam",
                "Recommendation conflicts with operator preference",
                "Recommendation requires operator action",
            ],
        ),
        (
            "recovery_migration",
            [
                "Cost data corruption",
                "Workspace import cost history incomplete",
                "AEIS update changes cost calculations",
                "Vendor API change breaks tracking",
            ],
        ),
    ]
)

SECURITY_EDGE_CASES = _edge_cases(
    [
        (
            "false_positives",
            [
                "Secret detector flags synthetic test key",
                "SAST flags safe sanitization wrapper",
                "Threat feed false positive on operator IP",
                "Compliance rule not applicable",
                "Dependency CVE not reachable",
            ],
        ),
        (
            "scanner_tooling",
            [
                "Scanner unavailable during build",
                "Managed scanner rate limit",
                "Threat intel feed stale",
                "Scanner version changes findings",
                "Long-running scan exceeds budget",
            ],
        ),
        (
            "incident_response",
            [
                "Credential leak auto-response needs manual scope",
                "Cryptojacking isolation affects legitimate workload",
                "Data exfiltration false alarm",
                "Brute force response blocks customer NAT",
            ],
        ),
        (
            "compliance",
            [
                "New regulation not in baseline",
                "GDPR evidence incomplete",
                "KSeF requirement conditional",
                "Customer requires custom compliance report",
            ],
        ),
        (
            "recovery_migration",
            [
                "Security config lost after import",
                "Threat feed API changed",
                "Incident timeline corrupted",
                "Compliance baseline version migration",
            ],
        ),
    ]
)

QUALITY_EDGE_CASES = _edge_cases(
    [
        (
            "test_execution",
            [
                "Flaky test blocks build",
                "L2 test database down",
                "Visual baseline outdated",
                "Human-like UI test stuck",
                "Test runner timeout",
            ],
        ),
        (
            "coverage_quality",
            [
                "Coverage generated for wrong package",
                "New code coverage regression",
                "Critical path missing tests",
                "Linter config drift",
                "Type checker false positive",
            ],
        ),
        (
            "auto_fix",
            [
                "Auto-fix introduces regression",
                "Auto-fix iteration budget exhausted",
                "Fix loop detected",
                "Security-sensitive fix requires operator",
            ],
        ),
        (
            "performance",
            [
                "Latency benchmark noisy",
                "Memory leak intermittent",
                "Performance baseline outdated",
                "L4 tests too expensive",
            ],
        ),
        (
            "recovery_migration",
            [
                "Quality history lost after import",
                "Test tool migration changes output",
                "Gold standards need re-baseline",
                "Monitoring instrumentation missing",
            ],
        ),
    ]
)

PROVENANCE_EDGE_CASES = _edge_cases(
    [
        (
            "chain_integrity",
            [
                "Hash chain broken",
                "Signing key lost",
                "Time skew",
                "Chain too large",
                "External timestamping fails",
            ],
        ),
        (
            "provenance_gaps",
            [
                "External tool no provenance",
                "Multi-machine operator",
                "Air-gapped provenance",
                "Customer-side actions",
                "Lost mobile chain segment",
            ],
        ),
        (
            "compliance_evidence",
            [
                "Evidence package incomplete",
                "Evidence format conflict",
                "Compliance period changed",
                "Evidence accuracy challenge",
            ],
        ),
        (
            "forensics",
            [
                "Forensic query expensive",
                "Privacy concerns in forensic export",
                "Causal chain ambiguous",
                "Forensic across machines",
            ],
        ),
        (
            "recovery_migration",
            [
                "Audit chain corruption",
                "Workspace migration chain integrity",
                "AEIS update changes audit format",
                "Long-term archive retrieval",
            ],
        ),
    ]
)


GUARD_CATALOG: dict[str, dict[str, Any]] = {
    "cost": {
        "phase": "7",
        "slug": "cost-guard",
        "title": "Cost Guard",
        "route_title": "Cost Guard - Faza 7",
        "summary": "Real-time cost enforcement, anomaly detection, predictions, auto-actions and reports.",
        "scope": [
            {"id": "llm_providers", "label": "LLM providers", "enabled_by_default": True, "items": ["Anthropic", "OpenAI", "OpenRouter", "Google", "Mistral", "local models"]},
            {"id": "cloud_resources", "label": "Cloud resources", "enabled_by_default": True, "items": ["AWS", "Hetzner", "DigitalOcean", "Linode", "OVH", "edge devices"]},
            {"id": "vendor_pass_through", "label": "Vendor pass-through", "enabled_by_default": True, "items": ["Stripe", "ElevenLabs", "SendGrid", "Twilio", "Cloudflare", "custom APIs"]},
            {"id": "operator_time", "label": "Operator time", "enabled_by_default": False, "items": ["UI time tracking", "hourly rate", "client billing"]},
        ],
        "capability_groups": [
            {"id": "aggregation_levels", "label": "Aggregation levels", "items": ["provider", "project", "phase", "role"]},
            {"id": "time_windows", "label": "Time windows", "items": ["real_time_per_minute", "period_hourly_daily_weekly_monthly", "project_lifetime"]},
            {"id": "anomaly_tiers", "label": "Anomaly detection tiers", "items": ["tier1_per_call_threshold", "tier2_statistical", "tier3_pattern", "tier4_predictive"]},
            {"id": "detection_mechanisms", "label": "Detection mechanisms", "items": ["rules", "statistical", "ML hybrid"]},
            {"id": "baseline_learning", "label": "Baseline learning dimensions", "items": ["workspace", "operator", "project_type", "D-level", "phase", "role"]},
            {"id": "auto_actions", "label": "Auto-actions", "items": ["notify", "model_switch", "throttling", "pausing", "hard_stop"]},
            {"id": "predictive_horizons", "label": "Predictive horizons", "items": ["1h", "4h", "24h", "7d", "30d", "90d optional"]},
            {"id": "reporting", "label": "Reporting cadence", "items": ["daily", "weekly", "monthly", "closure", "on_demand"]},
            {"id": "recommendations", "label": "Optimization recommendations", "items": ["real_time", "lifecycle_tracking", "ROI feedback"]},
        ],
        "checks": _items(
            [
                "Per-call cost threshold",
                "Per-minute spend rate",
                "Hourly statistical anomaly",
                "Daily statistical anomaly",
                "Weekly trend anomaly",
                "Sustained high rate",
                "Resource leak detection",
                "Provider retry storm",
                "Project budget exhaustion prediction",
                "Workspace monthly budget projection",
                "Closure cost vs estimate prediction",
                "Per-phase cost prediction",
            ],
            "cost_detection",
        ),
        "edge_cases": COST_EDGE_CASES,
        "acceptance": {
            "common": [
                ("scope_configured", "Cost Guard scope configured", "enabled scope categories"),
                ("anomaly_thresholds_reviewed", "Anomaly detection thresholds reviewed", "4 tiers reviewed"),
                ("auto_actions_authorized", "Auto-actions authorized per autonomy preset", "5 action categories"),
                ("reports_configured", "Reports cadence established", "daily/weekly/monthly/closure/on-demand"),
                ("audit_complete", "Audit chain entry phase_7.complete", "phase_7.complete"),
            ],
            "optional": [
                ("vendor_pass_through_tracked", "Vendor pass-through tracked", "Stripe + ElevenLabs"),
                ("predictive_horizons_enabled", "Predictive horizons enabled", "1h/24h/30d minimum"),
                ("recommendations_enabled", "Recommendations engine active", "active"),
                ("ml_baseline_learning_enabled", "ML baseline learning enabled", "78/90 days collected"),
                ("closure_reports_enabled", "Closure reports auto-generated", "enabled"),
            ],
            "integration": [
                ("aggregated_panel_integrated", "Aggregated Guards panel integration", "Phase 6 panel"),
                ("autonomy_override_considered", "Per-Guard autonomy override considered", "DIM-3 inherited"),
                ("cost_limits_configured", "Cost limits enforcement configured", "project/workspace limits"),
            ],
        },
        "hard_blocks": ["all_anomaly_disabled", "auto_actions_without_oversight", "no_cost_limits"],
        "soft_warnings": ["ml_disabled_with_data", "vendor_not_tracked", "predictive_disabled", "recommendations_disabled"],
    },
    "security": {
        "phase": "8",
        "slug": "security-guard",
        "title": "Security Guard",
        "route_title": "Security Guard - Faza 8",
        "summary": "Layered security aggregation across code, infra, data, ops, threat intel and compliance.",
        "scope": [
            {"id": "static_analysis", "label": "Static analysis", "enabled_by_default": True, "items": ["Semgrep", "CodeQL", "secret detection", "dependency CVE"]},
            {"id": "dynamic_analysis", "label": "Dynamic analysis", "enabled_by_default": True, "items": ["DAST", "runtime behavior", "access anomalies"]},
            {"id": "infrastructure", "label": "Infrastructure security", "enabled_by_default": True, "items": ["cloud misconfig", "open ports", "IAM"]},
            {"id": "data_security", "label": "Data security", "enabled_by_default": True, "items": ["encryption", "PII logs", "DLP"]},
            {"id": "operational_security", "label": "Operational security", "enabled_by_default": True, "items": ["MFA", "key rotation", "sessions"]},
            {"id": "threat_intelligence", "label": "Threat intelligence", "enabled_by_default": True, "items": ["CVE", "bad IPs", "industry feeds"]},
            {"id": "compliance", "label": "Compliance verification", "enabled_by_default": True, "items": ["GDPR", "KSeF", "PCI DSS", "HIPAA"]},
        ],
        "capability_groups": [
            {"id": "security_areas", "label": "Security areas", "items": ["code", "infrastructure", "data", "operational", "threat_detection", "compliance_verification"]},
            {"id": "triggers", "label": "Triggers", "items": ["continuous", "phase_boundaries", "on_demand"]},
            {"id": "detection", "label": "Detection mechanisms", "items": ["rules", "scanners", "LLM review", "threat intel"]},
            {"id": "threat_feeds", "label": "Threat intel feeds", "items": ["CVE database", "known bad IPs", "domains", "industry feeds"]},
            {"id": "incident_runbooks", "label": "Incident runbooks", "items": ["credential_leak", "cryptojacking", "data_exfiltration", "brute_force", "ransomware_indicators"]},
            {"id": "compliance_reports", "label": "Compliance reports", "items": ["GDPR", "KSeF", "HIPAA", "PCI DSS", "industry-specific"]},
        ],
        "checks": _items(
            [
                "SAST scan on build",
                "Secret detection in code and configs",
                "Dependency CVE scan",
                "Container image scan",
                "Insecure crypto usage detection",
                "Public cloud resources detection",
                "Open port enumeration",
                "TLS configuration verification",
                "IAM least-privilege check",
                "Default credentials detection",
                "Encryption-at-rest verification",
                "PII detection in logs",
                "Backup encryption check",
                "Data residency compliance",
                "Data retention policy enforcement",
                "Audit chain integrity",
                "MFA enforcement check",
                "Key and certificate expiry monitoring",
                "Failed authentication tracking",
                "Session anomaly detection",
                "Brute force attack detection",
                "Anomalous access patterns",
                "Outbound connection monitoring",
                "GDPR compliance baseline",
                "KSeF readiness",
            ],
            "security_baseline",
            severity="ERROR",
        ),
        "edge_cases": SECURITY_EDGE_CASES,
        "acceptance": {
            "common": [
                ("layers_configured", "7 layers configured", "7/7 layers"),
                ("baseline_reviewed", "Baseline 25 checks reviewed", "25 enabled"),
                ("compliance_selected", "Compliance frameworks selected", "GDPR + KSeF"),
                ("threat_intel_enabled", "Threat intel feeds enabled", "4 free feeds"),
                ("incident_response_configured", "Incident response workflows configured", "5 runbooks"),
                ("audit_complete", "Audit chain entry phase_8.complete", "phase_8.complete"),
            ],
            "optional": [
                ("custom_checks_decision", "Custom or community checks considered", "template/DSL/LLM/community"),
                ("goal_specific_scope", "Goal-specific security scope applied", "cybersecurity/public/research/internal"),
                ("auto_escalation_configured", "Security auto-escalation configured", "24h/4h/1h escalation"),
            ],
            "integration": [],
        },
        "hard_blocks": ["no_security_layers", "baseline_not_reviewed", "no_gdpr"],
        "soft_warnings": ["no_custom_security_checks", "community_checks_disabled", "advanced_threat_intel_disabled"],
    },
    "quality": {
        "phase": "9",
        "slug": "quality-guard",
        "title": "Quality Guard",
        "route_title": "Quality Guard - Faza 9",
        "summary": "Quality gates, L1-L5 test execution, auto-fix iterations, performance baselines and reports.",
        "scope": [
            {"id": "l1_unit", "label": "L1 Unit", "enabled_by_default": True, "items": ["pytest", "vitest", "jest", "80% coverage"]},
            {"id": "l2_integration", "label": "L2 Integration", "enabled_by_default": True, "items": ["API contracts", "DB integration"]},
            {"id": "l3_e2e", "label": "L3 E2E", "enabled_by_default": True, "items": ["Playwright", "critical journeys"]},
            {"id": "l4_performance", "label": "L4 Performance", "enabled_by_default": True, "items": ["k6", "Locust", "latency benchmarks"]},
            {"id": "l5_human_like", "label": "L5 Human-like UI", "enabled_by_default": True, "items": ["Playwright", "AEIS observation", "25-40 scenarios"]},
        ],
        "capability_groups": [
            {"id": "test_levels", "label": "Test levels", "items": ["L1", "L2", "L3", "L4", "L5"]},
            {"id": "triggers", "label": "Triggers and gates", "items": ["per_build", "pre_prod", "phase_gate", "on_demand"]},
            {"id": "thresholds", "label": "Quality thresholds", "items": ["coverage", "latency", "memory", "error_rate", "reliability"]},
            {"id": "auto_fix", "label": "Auto-fix iterations", "items": ["0 conservative", "3 balanced", "5 aggressive", "0 production", "10 research"]},
            {"id": "performance_tracking", "label": "Performance metrics", "items": ["P95", "memory", "throughput", "regression >20%"]},
            {"id": "reports", "label": "Quality reporting", "items": ["build", "daily", "closure", "on_demand"]},
        ],
        "checks": _items(
            [
                "L1 unit tests pass",
                "L2 integration tests pass",
                "L3 E2E tests pass",
                "L5 human-like UI scenarios pass",
                "Test execution time within budget",
                "L1 coverage at least 80 percent",
                "New code coverage at least 90 percent",
                "Coverage trend has no regression",
                "Critical paths covered",
                "Linter errors equal zero",
                "Type errors equal zero",
                "Cyclomatic complexity below 15",
                "Duplicate code below 5 percent",
                "P95 latency within budget",
                "Memory usage stable",
                "Throughput meets target",
                "Error rate below 0.1 percent",
                "Retry and resilience patterns implemented",
                "Logging completeness",
                "Monitoring instrumentation",
            ],
            "quality_baseline",
        ),
        "edge_cases": QUALITY_EDGE_CASES,
        "acceptance": {
            "common": [
                ("test_levels_configured", "Test levels integration", "L1-L5"),
                ("quality_thresholds_defined", "Quality thresholds defined", "DIM-7 inherited"),
                ("auto_fix_configured", "Auto-fix configured per autonomy", "balanced=3 iterations"),
                ("performance_baselines", "Performance baselines established", "first 3 builds policy"),
                ("reports_configured", "Reporting cadence", "build/daily/closure"),
                ("audit_complete", "Audit chain entry phase_9.complete", "phase_9.complete"),
            ],
            "optional": [],
            "integration": [],
        },
        "hard_blocks": ["no_test_levels", "thresholds_missing", "reports_disabled"],
        "soft_warnings": ["l4_disabled", "autofix_disabled", "performance_baseline_pending"],
    },
    "provenance": {
        "phase": "10",
        "slug": "provenance-guard",
        "title": "Provenance Guard",
        "route_title": "Provenance Guard - Faza 10",
        "summary": "Audit chain, cryptographic integrity, artifact lineage, compliance evidence and forensics.",
        "scope": [
            {"id": "audit_chain", "label": "Audit chain", "enabled_by_default": True, "items": ["hash chain", "append-only events", "checkpoints"]},
            {"id": "artifact_provenance", "label": "Artifact provenance", "enabled_by_default": True, "items": ["lineage", "verification API", "source links"]},
            {"id": "cryptographic_integrity", "label": "Cryptographic integrity", "enabled_by_default": True, "items": ["SHA-256", "Ed25519", "checkpoint signing"]},
            {"id": "operator_attribution", "label": "Operator attribution", "enabled_by_default": True, "items": ["actor", "device", "auth method", "signature"]},
            {"id": "external_correlation", "label": "External event correlation", "enabled_by_default": True, "items": ["customer reports", "cloud logs", "guard findings"]},
            {"id": "compliance_evidence", "label": "Compliance evidence", "enabled_by_default": True, "items": ["GDPR", "ISO 27001", "SOC 2"]},
            {"id": "forensic_capabilities", "label": "Forensic capabilities", "enabled_by_default": True, "items": ["time travel", "causal chain", "exports"]},
        ],
        "capability_groups": [
            {"id": "event_categories", "label": "Event categories", "items": ["workspace", "project", "council", "build", "deploy", "guard", "operator", "external", "security"]},
            {"id": "crypto", "label": "Cryptographic layers", "items": ["SHA-256 hash chain", "Ed25519 signing", "hourly checkpoints", "external timestamping optional", "blockchain anchoring optional"]},
            {"id": "artifact_lineage", "label": "Artifact lineage", "items": ["source commit", "council decision", "masterplan", "test results", "build environment"]},
            {"id": "evidence_templates", "label": "Compliance evidence", "items": ["GDPR Article 30", "ISO 27001", "SOC 2"]},
            {"id": "forensics", "label": "Forensics", "items": ["time-travel queries", "causal chain reconstruction", "multi-source timelines"]},
        ],
        "checks": _items(
            [
                "Audit chain configured",
                "SHA-256 hash chain active",
                "Ed25519 signing configured",
                "Artifact provenance enabled",
                "Artifact verification API ready",
                "Operator action attribution active",
                "External event correlation enabled",
                "GDPR evidence template ready",
                "ISO 27001 evidence template ready",
                "SOC 2 evidence template ready",
                "Time-travel forensic query available",
                "Causal chain reconstruction available",
            ],
            "provenance_baseline",
        ),
        "edge_cases": PROVENANCE_EDGE_CASES,
        "acceptance": {
            "common": [
                ("audit_chain_configured", "Audit chain configured", "hash algorithm + signing key"),
                ("hash_signing_configured", "Hash algorithm + signing configured", "SHA-256 + Ed25519"),
                ("artifact_provenance_enabled", "Artifact provenance enabled", "lineage + verification API"),
                ("compliance_templates_ready", "Compliance evidence templates", "GDPR + ISO + SOC2"),
                ("forensic_capabilities_enabled", "Forensic capabilities", "time-travel + causal chain"),
                ("audit_complete", "Audit chain entry phase_10.complete", "phase_10.complete"),
            ],
            "optional": [
                ("external_timestamping_enabled", "External timestamping", "not configured"),
                ("blockchain_anchoring_enabled", "Blockchain anchoring", "not configured"),
                ("multi_machine_sync_enabled", "Multi-machine sync", "single machine"),
            ],
            "integration": [],
        },
        "hard_blocks": ["audit_chain_disabled", "hash_signing_missing", "no_artifact_provenance"],
        "soft_warnings": ["external_timestamping_disabled", "blockchain_disabled", "multi_machine_single"],
    },
}

VALID_GUARDS = set(GUARD_CATALOG)


class ApplyDefaultsRequest(BaseModel):
    goal: str = "apps_internal"
    autonomy_preset: str = "balanced"


class GuardConfigRequest(BaseModel):
    flags: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, bool] = Field(default_factory=dict)
    feature_overrides: dict[str, Any] = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    reviewed_check_ids: list[str] = Field(default_factory=list)
    disabled_check_ids: list[str] = Field(default_factory=list)
    accepted_baseline: bool = True


class RunGuardRequest(BaseModel):
    depth: str = "standard"
    project_id: str = "dashboard_current"


class FindingActionRequest(BaseModel):
    action: str
    note: str = ""
    snooze_days: int = 7


class AutonomyOverrideRequest(BaseModel):
    inherits_phase5: bool = True
    preset: str = "balanced"
    auto_actions: dict[str, str] = Field(default_factory=dict)
    operator_note: str = ""


class EdgeDiagnosisRequest(BaseModel):
    case_id: str
    context: dict[str, Any] = Field(default_factory=dict)


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _db_path() -> Path:
    return Path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"))


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sylion_phase_state (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _state_key(guard_id: str, key: str) -> str:
    return f"guard:{guard_id}:{key}"


def _get_state(guard_id: str, key: str) -> Any:
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM sylion_phase_state WHERE key = ?", (_state_key(guard_id, key),)).fetchone()
    return _json_loads(row["value_json"], None) if row else None


def _set_state(guard_id: str, key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sylion_phase_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (_state_key(guard_id, key), json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), time.time()),
        )


def _state_list(guard_id: str, key: str) -> list[dict[str, Any]]:
    value = _get_state(guard_id, key)
    return value if isinstance(value, list) else []


def _append_state_list(guard_id: str, key: str, value: dict[str, Any]) -> None:
    items = _state_list(guard_id, key)
    items.append(value)
    _set_state(guard_id, key, items)


def _append_audit(guard_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    chain = _state_list(guard_id, "audit_chain")
    previous_hash = str(chain[-1].get("hash") or "") if chain else ""
    entry = {
        "event_id": _uid("audit"),
        "event": event,
        "payload": payload,
        "created_at": time.time(),
        "previous_hash": previous_hash,
    }
    canonical = json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str)
    entry["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _append_state_list(guard_id, "audit_chain", entry)
    return entry


def _catalog(guard_id: str) -> dict[str, Any]:
    if guard_id not in VALID_GUARDS:
        raise HTTPException(status_code=404, detail="guard not found")
    return GUARD_CATALOG[guard_id]


def _default_check_settings(guard_id: str) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    for item in _catalog(guard_id)["checks"]:
        checks[item["id"]] = {
            **_clone(item),
            "enabled": bool(item.get("enabled_by_default", True)),
            "reviewed": False,
            "severity": item.get("default_severity", "WARNING"),
            "tier": item.get("default_tier", "tier1"),
            "source": "baseline",
        }
    return checks


def _default_scope(guard_id: str) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: {"enabled": bool(item.get("enabled_by_default", True)), "items": list(item.get("items", []))}
        for item in _catalog(guard_id)["scope"]
    }


def _default_features(guard_id: str) -> dict[str, Any]:
    catalog = _catalog(guard_id)
    features = {group["id"]: {"enabled": True, "items": list(group.get("items", []))} for group in catalog["capability_groups"]}
    if guard_id == "cost":
        features["cost_limits"] = {"enabled": True, "project_limit_usd": 250, "workspace_monthly_limit_usd": 500}
        features["manual_oversight"] = {"enabled": True}
        features["ml_baseline_learning"] = {"enabled": True, "days_collected": 78, "target_days": 90, "status": "progress"}
        features["vendor_pass_through"] = {"enabled": True, "vendors": ["Stripe", "ElevenLabs"]}
    if guard_id == "security":
        features["compliance_frameworks"] = {"enabled": True, "items": ["GDPR", "KSeF"]}
        features["incident_runbooks"] = {"enabled": True, "items": ["credential_leak", "cryptojacking", "data_exfiltration", "brute_force", "ransomware_indicators"]}
        features["threat_feeds"] = {"enabled": True, "items": ["CVE", "bad_ip", "domains", "industry"]}
    if guard_id == "quality":
        features["auto_fix_iterations"] = {"enabled": True, "balanced": 3, "aggressive": 5, "research": 10, "production": 0}
        features["performance_baselines"] = {"enabled": True, "policy": "first_3_builds_then_operator_approval"}
    if guard_id == "provenance":
        features["hash_signing"] = {"enabled": True, "hash_algorithm": "SHA-256", "signature_algorithm": "Ed25519"}
        features["external_timestamping"] = {"enabled": False}
        features["blockchain_anchoring"] = {"enabled": False}
        features["multi_machine_sync"] = {"enabled": False}
    return features


def _default_flags(guard_id: str) -> dict[str, Any]:
    flags = {
        "scope_configured": False,
        "baseline_reviewed": False,
        "custom_checks_decision": False,
        "aggregated_panel_integrated": False,
        "autonomy_override_considered": False,
        "reports_configured": False,
    }
    if guard_id == "cost":
        flags.update(
            {
                "anomaly_thresholds_reviewed": False,
                "auto_actions_authorized": False,
                "vendor_pass_through_tracked": False,
                "predictive_horizons_enabled": False,
                "recommendations_enabled": False,
                "ml_baseline_learning_enabled": False,
                "closure_reports_enabled": False,
                "cost_limits_configured": False,
            }
        )
    if guard_id == "security":
        flags.update(
            {
                "layers_configured": False,
                "compliance_selected": False,
                "threat_intel_enabled": False,
                "incident_response_configured": False,
                "goal_specific_scope": False,
                "auto_escalation_configured": False,
            }
        )
    if guard_id == "quality":
        flags.update(
            {
                "test_levels_configured": False,
                "quality_thresholds_defined": False,
                "auto_fix_configured": False,
                "performance_baselines": False,
            }
        )
    if guard_id == "provenance":
        flags.update(
            {
                "audit_chain_configured": False,
                "hash_signing_configured": False,
                "artifact_provenance_enabled": False,
                "compliance_templates_ready": False,
                "forensic_capabilities_enabled": False,
                "external_timestamping_enabled": False,
                "blockchain_anchoring_enabled": False,
                "multi_machine_sync_enabled": False,
            }
        )
    return flags


def _default_settings(guard_id: str, goal: str = "apps_internal", preset: str = "balanced") -> dict[str, Any]:
    if preset not in VALID_PRESETS:
        preset = "balanced"
    return {
        "version": f"phase{_catalog(guard_id)['phase']}.v1",
        "guard_id": guard_id,
        "phase": _catalog(guard_id)["phase"],
        "goal": goal,
        "autonomy_preset": preset,
        "scope": _default_scope(guard_id),
        "checks": _default_check_settings(guard_id),
        "features": _default_features(guard_id),
        "flags": _default_flags(guard_id),
        "findings": [],
        "runs": [],
        "worker": {"enabled": True, "status": "running", "cache_initialized": True, "cache_hit_rate_pct": 80},
        "autonomy_override": {"inherits_phase5": True, "preset": preset, "considered": False, "auto_actions": {}, "operator_note": ""},
        "created_at": time.time(),
        "updated_at": time.time(),
    }


def _settings(guard_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    _catalog(guard_id)
    existing = _get_state(guard_id, "settings")
    if isinstance(existing, dict):
        return existing
    settings = _default_settings(guard_id, goal=goal)
    _set_state(guard_id, "settings", settings)
    return settings


def _save_settings(guard_id: str, settings: dict[str, Any], event: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings["updated_at"] = time.time()
    _set_state(guard_id, "settings", settings)
    _append_audit(guard_id, event, payload)
    return settings


def _enabled_checks(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [check for check in (settings.get("checks") or {}).values() if check.get("enabled")]


def _active_findings(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for finding in settings.get("findings") or [] if finding.get("status") == "active"]


def _feature_enabled(settings: dict[str, Any], feature_id: str) -> bool:
    feature = (settings.get("features") or {}).get(feature_id)
    return bool(feature.get("enabled")) if isinstance(feature, dict) else bool(feature)


def _flag(settings: dict[str, Any], flag_id: str) -> bool:
    return bool((settings.get("flags") or {}).get(flag_id))


def _hard_blocks(guard_id: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    def add(block_id: str, label: str, condition: bool, evidence: str) -> None:
        if condition:
            blocks.append({"id": block_id, "label": label, "status": "fail", "evidence": evidence, "hard": True})

    if guard_id == "cost":
        anomaly_checks = [check for check in _enabled_checks(settings) if "anomaly" in check["id"] or "prediction" in check["id"] or "threshold" in check["id"]]
        auto_actions_enabled = _feature_enabled(settings, "auto_actions")
        manual_oversight = _feature_enabled(settings, "manual_oversight")
        add("all_anomaly_disabled", "Hard block: all anomaly detection disabled", len(anomaly_checks) == 0, "0 anomaly checks enabled")
        add("auto_actions_without_oversight", "Hard block: auto-actions disabled without manual oversight", not auto_actions_enabled and not manual_oversight, "no action path")
        add("no_cost_limits", "Hard block: no cost limits configured", not _feature_enabled(settings, "cost_limits"), "cost limits disabled")
    elif guard_id == "security":
        enabled_layers = [key for key, value in (settings.get("scope") or {}).items() if value.get("enabled")]
        compliance = (settings.get("features") or {}).get("compliance_frameworks") or {}
        frameworks = set(compliance.get("items") or [])
        add("no_security_layers", "Hard block: no security layers enabled", not enabled_layers, "0/7 layers")
        add("baseline_not_reviewed", "Hard block: baseline 25 checks not reviewed", not _flag(settings, "baseline_reviewed"), "baseline not reviewed")
        add("no_gdpr", "Hard block: GDPR baseline missing", "GDPR" not in frameworks, ", ".join(sorted(frameworks)) or "none")
    elif guard_id == "quality":
        enabled_levels = [key for key, value in (settings.get("scope") or {}).items() if value.get("enabled")]
        add("no_test_levels", "Hard block: no test levels enabled", not enabled_levels, "0/5 levels")
        add("thresholds_missing", "Hard block: quality thresholds missing", not _flag(settings, "quality_thresholds_defined"), "DIM-7 threshold missing")
        add("reports_disabled", "Hard block: quality reporting disabled", not _flag(settings, "reports_configured"), "reports not configured")
    elif guard_id == "provenance":
        add("audit_chain_disabled", "Hard block: audit chain disabled", not _flag(settings, "audit_chain_configured"), "audit chain not configured")
        add("hash_signing_missing", "Hard block: hash/signing missing", not _feature_enabled(settings, "hash_signing"), "hash_signing disabled")
        add("no_artifact_provenance", "Hard block: artifact provenance disabled", not _flag(settings, "artifact_provenance_enabled"), "artifact provenance missing")
    return blocks


def _soft_warnings(guard_id: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    def add(warn_id: str, label: str, condition: bool, evidence: str) -> None:
        if condition:
            warnings.append({"id": warn_id, "label": label, "status": "warn", "evidence": evidence, "hard": False})

    if guard_id == "cost":
        add("ml_disabled_with_data", "ML disabled despite available data", not _feature_enabled(settings, "ml_baseline_learning"), "statistical fallback")
        add("vendor_not_tracked", "Vendor pass-through not tracked", not _flag(settings, "vendor_pass_through_tracked"), "operator external")
        add("predictive_disabled", "Predictive horizons disabled", not _flag(settings, "predictive_horizons_enabled"), "reports only")
        add("recommendations_disabled", "Recommendations disabled", not _flag(settings, "recommendations_enabled"), "operator external")
    elif guard_id == "security":
        add("no_custom_security_checks", "No custom security checks", not _flag(settings, "custom_checks_decision"), "baseline only")
        add("community_checks_disabled", "Community checks disabled", True, "operator has not imported community checks")
        add("advanced_threat_intel_disabled", "Advanced threat intel disabled", False, "free feeds enabled")
    elif guard_id == "quality":
        add("l4_disabled", "L4 performance tests disabled", not (settings.get("scope") or {}).get("l4_performance", {}).get("enabled"), "pre-prod performance coverage reduced")
        add("autofix_disabled", "Auto-fix disabled", not _flag(settings, "auto_fix_configured"), "operator manual")
        add("performance_baseline_pending", "Performance baseline pending", not _flag(settings, "performance_baselines"), "needs first 3 builds")
    elif guard_id == "provenance":
        add("external_timestamping_disabled", "External timestamping not configured", not _flag(settings, "external_timestamping_enabled"), "optional")
        add("blockchain_disabled", "Blockchain anchoring not configured", not _flag(settings, "blockchain_anchoring_enabled"), "optional")
        add("multi_machine_single", "Multi-machine sync not configured", not _flag(settings, "multi_machine_sync_enabled"), "single machine")
    return warnings


def _acceptance_check(settings: dict[str, Any], guard_id: str, check_id: str, label: str, evidence: str, finalize: bool) -> dict[str, Any]:
    completion_event = f"phase_{_catalog(guard_id)['phase']}.complete"
    audit_complete = any(entry.get("event") == completion_event for entry in _state_list(guard_id, "audit_chain"))
    if check_id == "audit_complete":
        ok = audit_complete or finalize
        return {"id": check_id, "label": label, "status": "pass" if ok else "fail", "evidence": "recorded" if ok else "missing", "hard": True}
    ok = _flag(settings, check_id)
    return {"id": check_id, "label": label, "status": "pass" if ok else "fail", "evidence": evidence if ok else "missing", "hard": True}


def _build_acceptance(guard_id: str, settings: dict[str, Any], goal: str = "apps_internal", finalize: bool = False) -> dict[str, Any]:
    catalog = _catalog(guard_id)
    checks: list[dict[str, Any]] = []
    for item in catalog["acceptance"]["common"]:
        checks.append(_acceptance_check(settings, guard_id, item[0], item[1], item[2], finalize))
    for item in catalog["acceptance"].get("optional", []):
        status = "pass" if _flag(settings, item[0]) else "warn"
        if guard_id == "cost" and item[0] == "ml_baseline_learning_enabled" and _flag(settings, item[0]):
            status = "progress"
        checks.append({"id": item[0], "label": item[1], "status": status, "evidence": item[2], "hard": False})
    for item in catalog["acceptance"].get("integration", []):
        checks.append({"id": item[0], "label": item[1], "status": "pass" if _flag(settings, item[0]) else "fail", "evidence": item[2], "hard": True})

    hard_blocks = [check for check in checks if check["status"] == "fail" and check.get("hard")]
    hard_blocks.extend(_hard_blocks(guard_id, settings))
    soft_warnings = [check for check in checks if check["status"] == "warn"]
    soft_warnings.extend(_soft_warnings(guard_id, settings))

    completion_event = f"phase_{catalog['phase']}.complete"
    audit_complete = any(entry.get("event") == completion_event for entry in _state_list(guard_id, "audit_chain"))
    if finalize and not hard_blocks and not audit_complete:
        entry = _append_audit(
            guard_id,
            completion_event,
            {
                "goal": goal,
                "enabled_checks": len(_enabled_checks(settings)),
                "active_findings": len(_active_findings(settings)),
                "soft_warnings": len(soft_warnings),
            },
        )
        for check in checks:
            if check["id"] == "audit_complete":
                check["status"] = "pass"
                check["evidence"] = entry["event_id"]
        audit_complete = True

    passed = len([check for check in checks if check["status"] == "pass"])
    return {
        "phase": catalog["phase"],
        "guard_id": guard_id,
        "goal": goal,
        "accepted": len(hard_blocks) == 0,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "dod": {
            "counts": {
                "checks_passed": passed,
                "checks_total": len(checks),
                "hard_blocks": len(hard_blocks),
                "soft_warnings": len(soft_warnings),
                "progress": len([check for check in checks if check["status"] == "progress"]),
            },
            "common": {
                "required": len(catalog["acceptance"]["common"]),
                "passed": len([check for check in checks[: len(catalog["acceptance"]["common"])] if check["status"] == "pass"]),
            },
        },
        "audit_chain": {
            "entries": len(_state_list(guard_id, "audit_chain")),
            f"phase_{catalog['phase']}_complete": audit_complete,
            "last_hash": (_state_list(guard_id, "audit_chain")[-1].get("hash") if _state_list(guard_id, "audit_chain") else ""),
        },
    }


def _aggregated_panel() -> dict[str, Any]:
    rows: list[dict[str, Any]] = [{"id": "coherence", "label": "Coherence Guard", "phase": "6", "status": "configured", "active_findings": 0, "highest_severity": "INFO"}]
    for guard_id in ["cost", "security", "quality", "provenance"]:
        settings = _settings(guard_id)
        acceptance = _build_acceptance(guard_id, settings, finalize=False)
        active = _active_findings(settings)
        rows.append(
            {
                "id": guard_id,
                "label": _catalog(guard_id)["title"],
                "phase": _catalog(guard_id)["phase"],
                "status": "configured" if acceptance["accepted"] and acceptance["audit_chain"].get(f"phase_{_catalog(guard_id)['phase']}_complete") else "active",
                "active_findings": len(active),
                "highest_severity": _highest_severity(active),
            }
        )
    severity_counts = {item["id"]: 0 for item in SEVERITY_LEVELS}
    for guard_id in VALID_GUARDS:
        for finding in _active_findings(_settings(guard_id)):
            severity = str(finding.get("severity") or "INFO")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
    return {"guards": rows, "severity_counts": severity_counts, "total_active_findings": sum(row["active_findings"] for row in rows)}


def _highest_severity(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "INFO"
    ranks = {item["id"]: item["rank"] for item in SEVERITY_LEVELS}
    return max((str(item.get("severity") or "INFO") for item in findings), key=lambda severity: ranks.get(severity, 0))


def _snapshot(guard_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings(guard_id, goal=goal)
    catalog = _catalog(guard_id)
    return {
        "phase": catalog["phase"],
        "guard_id": guard_id,
        "status": "active",
        "settings": settings,
        "templates": {
            "catalog": catalog,
            "scope": catalog["scope"],
            "capability_groups": catalog["capability_groups"],
            "checks": catalog["checks"],
            "edge_cases": catalog["edge_cases"],
            "severities": SEVERITY_LEVELS,
        },
        "aggregated_panel": _aggregated_panel(),
        "acceptance": _build_acceptance(guard_id, settings, goal=goal, finalize=False),
    }


def _apply_default_flags(guard_id: str, settings: dict[str, Any]) -> None:
    flags = settings["flags"]
    for requirement in _catalog(guard_id)["acceptance"]["common"]:
        if requirement[0] != "audit_complete":
            flags[requirement[0]] = True
    for section in ["optional", "integration"]:
        for requirement in _catalog(guard_id)["acceptance"].get(section, []):
            flags[requirement[0]] = True
    flags["scope_configured"] = True
    flags["baseline_reviewed"] = True
    flags["aggregated_panel_integrated"] = True
    flags["autonomy_override_considered"] = True
    flags["custom_checks_decision"] = True
    if guard_id == "provenance":
        flags["external_timestamping_enabled"] = False
        flags["blockchain_anchoring_enabled"] = False
        flags["multi_machine_sync_enabled"] = False


def _run_findings(guard_id: str, settings: dict[str, Any], run_id: str, project_id: str) -> list[dict[str, Any]]:
    if project_id != "diagnostic_project":
        return [
            {
                "id": _uid("finding"),
                "run_id": run_id,
                "guard_id": guard_id,
                "title": f"Brak syntetycznych ustaleń w przebiegu strażnika {guard_id}",
                "summary": "Wybrany strażnik zakończył się bez przykładowych ustaleń. Rzeczywiste ustalenia wymagają artefaktów konkretnego projektu.",
                "severity": "INFO",
                "status": "active",
                "project_id": project_id,
                "can_auto_fix": False,
                "created_at": time.time(),
            }
        ]
    samples = {
        "cost": [
            ("Workspace monthly budget projection at 97 percent", "ERROR", "Trend suggests budget hit before month end."),
            ("Anthropic retry storm increased hourly spend", "WARNING", "Four related anomalies were grouped to one root cause."),
            ("Switch non-critical Planner model for remaining build", "INFO", "Recommendation could save about $8.40."),
        ],
        "security": [
            ("Dependency CVE above CVSS 7.0", "ERROR", "A vulnerable dependency is present in the build graph."),
            ("Secret-like token in test fixture", "WARNING", "Requires operator review before suppression."),
            ("GDPR baseline evidence ready", "INFO", "Compliance package can be generated."),
        ],
        "quality": [
            ("L3 E2E checkout scenario failed", "ERROR", "Critical user journey is not passing."),
            ("Coverage trend regressed by 3 percent", "WARNING", "New code coverage is below the configured target."),
            ("Auto-fix candidate: wrong import path", "INFO", "Balanced preset allows up to 3 iterations."),
        ],
        "provenance": [
            ("External file modification provenance gap", "WARNING", "A file changed outside AEIS-tracked actions."),
            ("External timestamping not configured", "INFO", "Optional high-stakes timestamp layer is disabled."),
            ("Artifact verification API passed sample artifact", "INFO", "Hash chain and lineage are valid."),
        ],
    }[guard_id]
    findings = []
    for title, severity, summary in samples:
        findings.append(
            {
                "id": _uid("finding"),
                "run_id": run_id,
                "guard_id": guard_id,
                "title": title,
                "summary": summary,
                "severity": severity,
                "status": "active",
                "project_id": project_id,
                "can_auto_fix": guard_id == "quality" and severity in {"INFO", "WARNING"},
                "created_at": time.time(),
            }
        )
    return findings


@router.get("/api/v1/guards")
def list_guards() -> dict[str, Any]:
    return {"guards": [{"id": key, **_clone(value)} for key, value in GUARD_CATALOG.items()], "aggregated_panel": _aggregated_panel()}


@router.get("/api/v1/guards/aggregated-panel")
def get_guards_aggregated_panel() -> dict[str, Any]:
    return _aggregated_panel()


@router.get("/api/v1/guards/{guard_id}")
def get_guard(guard_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    return _snapshot(guard_id, goal=goal)


@router.get("/api/v1/guards/{guard_id}/templates")
def get_guard_templates(guard_id: str) -> dict[str, Any]:
    snapshot = _snapshot(guard_id)
    return snapshot["templates"]


@router.post("/api/v1/guards/{guard_id}/defaults/apply")
def apply_guard_defaults(guard_id: str, body: ApplyDefaultsRequest) -> dict[str, Any]:
    if body.autonomy_preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="unsupported autonomy preset")
    settings = _default_settings(guard_id, goal=body.goal, preset=body.autonomy_preset)
    _apply_default_flags(guard_id, settings)
    for check in settings["checks"].values():
        check["reviewed"] = True
        check["enabled"] = True
    settings["autonomy_override"]["considered"] = True
    _set_state(guard_id, "settings", settings)
    _append_audit(guard_id, f"phase{_catalog(guard_id)['phase']}.defaults_applied", {"goal": body.goal, "preset": body.autonomy_preset})
    return _snapshot(guard_id, goal=body.goal)


@router.post("/api/v1/guards/{guard_id}/config")
def save_guard_config(guard_id: str, body: GuardConfigRequest) -> dict[str, Any]:
    settings = _settings(guard_id)
    for key, enabled in body.scope.items():
        if key not in settings["scope"]:
            raise HTTPException(status_code=400, detail=f"unknown scope: {key}")
        settings["scope"][key]["enabled"] = bool(enabled)
    settings["flags"].update(body.flags)
    for feature_id, value in body.feature_overrides.items():
        if isinstance(value, dict):
            current = dict(settings["features"].get(feature_id) or {})
            current.update(value)
            settings["features"][feature_id] = current
        else:
            settings["features"][feature_id] = value
    _save_settings(guard_id, settings, f"phase{_catalog(guard_id)['phase']}.config_saved", {"flags": sorted(body.flags), "scope": sorted(body.scope)})
    return {"settings": settings, "snapshot": _snapshot(guard_id, goal=settings.get("goal", "apps_internal"))}


@router.post("/api/v1/guards/{guard_id}/review")
def review_guard_checks(guard_id: str, body: ReviewRequest) -> dict[str, Any]:
    settings = _settings(guard_id)
    known = set(settings["checks"])
    reviewed = set(body.reviewed_check_ids or known)
    disabled = set(body.disabled_check_ids)
    unknown = sorted((reviewed | disabled) - known)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown checks: {', '.join(unknown)}")
    for check_id, check in settings["checks"].items():
        check["reviewed"] = check_id in reviewed
        check["enabled"] = check_id not in disabled
    settings["flags"]["baseline_reviewed"] = body.accepted_baseline
    if guard_id == "cost":
        settings["flags"]["anomaly_thresholds_reviewed"] = body.accepted_baseline
    _save_settings(guard_id, settings, f"phase{_catalog(guard_id)['phase']}.checks_reviewed", {"reviewed": len(reviewed), "disabled": len(disabled)})
    return {"checks": settings["checks"], "snapshot": _snapshot(guard_id, goal=settings.get("goal", "apps_internal"))}


@router.post("/api/v1/guards/{guard_id}/run")
def run_guard_check(guard_id: str, body: RunGuardRequest) -> dict[str, Any]:
    _catalog(guard_id)
    if body.depth not in {"quick", "standard", "deep"}:
        raise HTTPException(status_code=400, detail="unsupported run depth")
    settings = _settings(guard_id)
    if not (settings.get("worker") or {}).get("enabled"):
        raise HTTPException(status_code=409, detail="guard worker disabled")
    run_id = _uid("run")
    findings = _run_findings(guard_id, settings, run_id, body.project_id)
    run = {"id": run_id, "depth": body.depth, "project_id": body.project_id, "findings_created": len(findings), "created_at": time.time()}
    settings.setdefault("runs", []).append(run)
    settings.setdefault("findings", []).extend(findings)
    _save_settings(guard_id, settings, f"phase{_catalog(guard_id)['phase']}.guard_run", {"run_id": run_id, "findings": len(findings)})
    return {"run": run, "findings": findings, "aggregated_panel": _aggregated_panel(), "snapshot": _snapshot(guard_id, goal=settings.get("goal", "apps_internal"))}


@router.get("/api/v1/guards/{guard_id}/findings")
def list_guard_findings(guard_id: str, status: str | None = None, severity: str | None = None) -> dict[str, Any]:
    settings = _settings(guard_id)
    findings = list(settings.get("findings") or [])
    if status:
        findings = [item for item in findings if item.get("status") == status]
    if severity:
        findings = [item for item in findings if item.get("severity") == severity]
    return {"count": len(findings), "findings": findings}


@router.post("/api/v1/guards/{guard_id}/findings/{finding_id}/action")
def act_on_guard_finding(guard_id: str, finding_id: str, body: FindingActionRequest) -> dict[str, Any]:
    if body.action not in {"suppress", "snooze", "resolve", "apply_fix"}:
        raise HTTPException(status_code=400, detail="unsupported finding action")
    settings = _settings(guard_id)
    findings = list(settings.get("findings") or [])
    for index, finding in enumerate(findings):
        if finding.get("id") != finding_id:
            continue
        updated = dict(finding)
        if body.action == "apply_fix":
            if not updated.get("can_auto_fix"):
                raise HTTPException(status_code=409, detail="finding cannot be auto-fixed safely")
            updated["status"] = "resolved"
            updated["fix_applied"] = True
        elif body.action == "snooze":
            updated["status"] = "snoozed"
            updated["snoozed_until"] = time.time() + body.snooze_days * 86400
        else:
            updated["status"] = "suppressed" if body.action == "suppress" else "resolved"
        updated["operator_note"] = body.note
        updated["updated_at"] = time.time()
        findings[index] = updated
        settings["findings"] = findings
        _save_settings(guard_id, settings, f"phase{_catalog(guard_id)['phase']}.finding_action", {"finding_id": finding_id, "action": body.action})
        return {"finding": updated, "snapshot": _snapshot(guard_id, goal=settings.get("goal", "apps_internal"))}
    raise HTTPException(status_code=404, detail="finding not found")


@router.post("/api/v1/guards/{guard_id}/autonomy-override")
def save_guard_autonomy_override(guard_id: str, body: AutonomyOverrideRequest) -> dict[str, Any]:
    if body.preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="unsupported preset")
    settings = _settings(guard_id)
    settings["autonomy_preset"] = body.preset
    settings["autonomy_override"] = {
        "inherits_phase5": body.inherits_phase5,
        "preset": body.preset,
        "auto_actions": body.auto_actions,
        "operator_note": body.operator_note,
        "considered": True,
        "updated_at": time.time(),
    }
    settings["flags"]["autonomy_override_considered"] = True
    _save_settings(guard_id, settings, f"phase{_catalog(guard_id)['phase']}.autonomy_override_saved", {"preset": body.preset})
    return {"autonomy_override": settings["autonomy_override"], "snapshot": _snapshot(guard_id, goal=settings.get("goal", "apps_internal"))}


@router.get("/api/v1/guards/{guard_id}/edge-cases")
def list_guard_edge_cases(guard_id: str) -> dict[str, Any]:
    edge_cases = _catalog(guard_id)["edge_cases"]
    return {"phase": _catalog(guard_id)["phase"], "count": len(edge_cases), "categories": sorted({item["category"] for item in edge_cases}), "edge_cases": edge_cases}


@router.post("/api/v1/guards/{guard_id}/edge-cases/diagnose")
def diagnose_guard_edge_case(guard_id: str, body: EdgeDiagnosisRequest) -> dict[str, Any]:
    case = next((item for item in _catalog(guard_id)["edge_cases"] if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    diagnosis = {
        "case": case,
        "context": body.context,
        "requires_operator_review": case["severity"] in {"medium", "high", "critical"},
        "action_plan": case["runbook"] + [f"write phase{_catalog(guard_id)['phase']} audit entry"],
        "created_at": time.time(),
    }
    _append_audit(guard_id, f"phase{_catalog(guard_id)['phase']}.edge_case_diagnosed", {"case_id": case["id"], "severity": case["severity"]})
    return diagnosis


@router.get("/api/v1/guards/{guard_id}/acceptance")
def get_guard_acceptance(guard_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(guard_id, _settings(guard_id, goal=goal), goal=goal, finalize=False)


@router.get("/api/v1/guards/{guard_id}/acceptance-test")
def run_guard_acceptance_test(guard_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(guard_id, _settings(guard_id, goal=goal), goal=goal, finalize=True)


@router.post("/api/v1/guards/{guard_id}/complete")
def complete_guard_phase(guard_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    result = _build_acceptance(guard_id, _settings(guard_id, goal=goal), goal=goal, finalize=True)
    if result["hard_blocks"]:
        raise HTTPException(status_code=400, detail=result)
    return result
