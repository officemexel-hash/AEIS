#!/usr/bin/env python3
"""
SYLION Multi-Agent Pipeline — Orchestrator (47 agentów, 12 etapów + Supervisor)

Architectura bezpieczeństwa (5 warstw anti-hallucination):
  LLM generates plan → Supervisor → Human Gate → Safe Runner → Output → Cross Audit

  Layer 1: FileVerification   — SHA-256 per-agent iteration check
  Layer 2: BuildVerification  — go vet/build/test po każdej zmianie
  Layer 3: ClaimProvenance    — keyword matching w okolicy linii
  Layer 4: SemanticDedup      — sentence-transformers deduplikacja findingów
  Layer 5: FactCheckerAgent   — niezależny LLM check przed Stage 6

  ⚠️  LLM NIGDY nie wydaje raw shell. Generuje parametry do pre-approved
      scenariuszy. Chyba że dostanie fizycznie zgodę — wtedy musi pytać.

Pipeline: Księga → Kod → Audyt(×5) → Cross-verify(×4) → Merge → 
          Patch(×4) → Deploy(×2) → Test(×4) → RedBlue(×4) → SDR(×3) → Report

Supervisor oversees ALL stages, maintains checklist, enforces Human Gate.

Uruchomienie:
  python orchestrator.py --workspace /path/to/sylion --ksiega /path/to/ksiega.pdf
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, register_agent
from openhands.tools.delegate import DelegationVisualizer

from agents.definitions import (
    create_auditor,
    create_blue_team_agent,
    create_build_agent,
    create_coordinator,
    create_cross_verifier,
    create_ksiega_analyst,
    create_merger,
    create_patch_agent,
    create_pixel_deployer,
    create_red_team_agent,
    create_reporter,
    create_router_deployer,
    create_test_agent,
)
from agents.sdr_agents import (
    create_sdr_monitor_agent,
    create_rf_red_team_agent,
    create_rf_blue_team_agent,
)
from agent_manager import AgentManager
from config import AUDIT_MODELS, ModelConfig, PipelineConfig

# R3.13: legacy dashboard cost tracker removed; unified monitoring owns budget data.
_ORCH_COST_TRACKER_AVAILABLE = False
_orch_cost_tracker = None
_orch_compute_cost = None
from supervisor import (
    SupervisorAgent,
    HumanGate,
    DeterministicRunner,
    GateLevel,
    GateDecision,
    GateRequest,
    create_safety_stack,
)
from loop_guard import (
    LoopGuard,
    LoopStatus,
    ContextPersistence,
    EventType,
    IterationTracker,
)
from human_gate_ux import (
    ConsequenceDescriptor,
    EnhancedDisplay,
    LoopConsequences,
    build_gate_ux,
)
from file_verification import (
    FileVerificationLayer,
    HallucinationGuard,
    AgentClaim,
    ClaimAction,
    VerificationResult,
    Verdict,
)
from book_guardian import BookGuardian
from budget_guard import BudgetGuard
from build_verification import BuildVerification, BuildStatus, BuildResult
from claim_provenance import ClaimProvenance, ProvenanceClaim, ProvenanceVerdict
from semantic_dedup import SemanticDedup, DedupBackend
from fact_checker import FactCheckerAgent, FactCheckItem, FactCheckVerdict, FactCheckReport
from signaling_server import SignalingServer, SessionFlowController, ICEServerConfig
from device_harness import DeviceHarness, SafeCommandRunner, DeviceType, DeviceState
from metrics_ingestion import MetricsCollector, MetricsStore, AlertEngine, ThresholdConfig, MetricType
from abr_controller import ABRController, ABRState, CongestionSignal
from input_protocol import InputProtocolCodec, InputEventType, ReplayGuard
from audio_pipeline import AudioPipelineController, OpusConfig, EchoCancelState, AVSyncTracker
from stream_security import StreamSecurityVerifier, SecurityLevel, CheckResult as SecCheckResult
from benchmark_harness import BenchmarkHarness, BenchmarkThresholds, BenchmarkStatus
from e2e_session import E2ESessionController, E2ESessionReport, SessionState
from stream_monitor import StreamMonitor, MonitorSnapshot, MonitorAlert
from dashboard_server import DashboardServer
from orchestrator_anti_halluc_hook import anti_halluc_hook  # GAP-04 fix: anti_hallucination_log auto-feed

load_dotenv()

# P2-C fix: lock protecting mutable global state shared between asyncio stages
# and run_in_executor threads.  Acquire before reading/writing globals.
_globals_lock = threading.Lock()

# Global instances
agent_mgr: AgentManager | None = None
supervisor: SupervisorAgent | None = None
human_gate: HumanGate | None = None
safe_runner: DeterministicRunner | None = None
loop_guard: LoopGuard | None = None
ctx_persistence: ContextPersistence | None = None
iteration_tracker: IterationTracker | None = None
gate_ux: EnhancedDisplay | None = None
consequence_desc: ConsequenceDescriptor | None = None
halluc_guard: HallucinationGuard | None = None
file_layer: FileVerificationLayer | None = None
book_guardian: BookGuardian | None = None
budget_guard: BudgetGuard | None = None
build_verifier: BuildVerification | None = None
claim_prover: ClaimProvenance | None = None
semantic_deduper: SemanticDedup | None = None
fact_checker: FactCheckerAgent | None = None
signaling_srv: SignalingServer | None = None
device_harness: DeviceHarness | None = None
metrics_collector: MetricsCollector | None = None
abr_controller: ABRController | None = None
input_protocol: InputProtocolCodec | None = None
audio_pipeline: AudioPipelineController | None = None
stream_security: StreamSecurityVerifier | None = None
benchmark_harness: BenchmarkHarness | None = None
stream_monitor_inst: StreamMonitor | None = None
e2e_controller: E2ESessionController | None = None
dashboard_srv: DashboardServer | None = None


def init_agent_manager():
    """Initialize agent manager from agents.yaml."""
    global agent_mgr
    agent_mgr = AgentManager()
    issues = agent_mgr.validate()
    for issue in issues:
        if issue.startswith("ERROR"):
            log.error(issue)
        else:
            log.warning(issue)
    return agent_mgr


def init_supervisor(results_dir: Path, cfg: PipelineConfig | None = None):
    """Initialize Supervisor + Human Gate + Safe Runner + Loop Guard + Context + FileVerification.

    Only activates if 'supervisor' agent is enabled in agents.yaml.
    """
    global supervisor, human_gate, safe_runner
    global loop_guard, ctx_persistence, iteration_tracker
    global gate_ux, consequence_desc
    global halluc_guard, file_layer
    global book_guardian, budget_guard
    global build_verifier, claim_prover, semantic_deduper, fact_checker
    global signaling_srv, device_harness, metrics_collector, abr_controller
    global input_protocol, audio_pipeline, stream_security, benchmark_harness

    if agent_mgr is None or not is_agent_enabled("supervisor"):
        log.info("  Supervisor WYŁĄCZONY — pipeline bez nadzoru")
        return

    sup_cfg = agent_mgr.agents.get("supervisor")
    params = sup_cfg.params if sup_cfg else {}

    # --- Human Gate (with env-switch for DB polling mode) ---
    hg_params = params.get("human_gate", {})
    _hg_mode = os.environ.get("SYLION_HUMANGATE_MODE", "tty")
    if _hg_mode == "db":
        from supervisor import DbPollingHumanGate
        human_gate = DbPollingHumanGate(
            log_path=results_dir / "human_gate.json",
            auto_approve_info=hg_params.get("auto_approve_info", True),
            timeout_seconds=hg_params.get("timeout_seconds", 3600),
            run_id=os.environ.get("SYLION_RUN_ID", ""))
    else:
        human_gate = HumanGate(
            log_path=results_dir / "human_gate.json",
            auto_approve_info=hg_params.get("auto_approve_safe", False),
            timeout_seconds=hg_params.get("timeout", 300),
        )

    # --- Deterministic Runner ---
    safe_runner = DeterministicRunner(
        gate=human_gate,
        dry_run=False,
    )

    # --- Supervisor Agent ---
    supervisor = SupervisorAgent(
        gate=human_gate,
        runner=safe_runner,
    )

    # --- Loop Guard (Anti-Loop Detection) ---
    lg_params = params.get("loop_guard", {})
    loop_guard = LoopGuard(
        max_iterations=lg_params.get("max_iterations", 5),
        results_dir=results_dir / "loops",
    )

    # --- Context Persistence (Memory Snapshots) ---
    ctx_persistence = ContextPersistence(
        results_dir=results_dir / "context",
        context_window_size=lg_params.get("context_window_size", 50),
    )

    # --- Iteration Tracker ---
    iteration_tracker = IterationTracker(
        results_dir=results_dir / "iterations",
    )

    # --- Human Gate UX (consequence descriptions) ---
    consequence_desc = ConsequenceDescriptor()
    gate_ux = EnhancedDisplay()

    # --- File Verification Layer (Anti-Hallucination Guard) ---
    fv_params = params.get("file_verification", {})
    fv_enabled = fv_params.get("enabled", True)
    if cfg:
        fv_enabled = fv_enabled and cfg.file_verification_enabled

    if fv_enabled:
        workspace_path = cfg.workspace if cfg else Path(".")
        verification_dir = cfg.verification_output_dir if cfg else (results_dir / "verification")

        file_layer = FileVerificationLayer(
            repo_root=workspace_path,
            fail_closed=fv_params.get("fail_closed", True) if not (cfg and not cfg.verify_fail_closed) else False,
            log_dir=verification_dir,
        )

        halluc_guard = HallucinationGuard(
            file_layer=file_layer,
            loop_guard=loop_guard,
            human_gate=human_gate,
            context_persistence=ctx_persistence,
            audit_log_path=results_dir / "hallucinations.jsonl",
            auto_escalate=fv_params.get("auto_escalate", True),
        )
        log.info("  ✓ File Verification Layer zainicjalizowany")
        log.info(f"    Fail-closed:  {file_layer.fail_closed}")
        log.info(f"    Auto-escalate: {halluc_guard.auto_escalate}")
        log.info(f"    Log dir:      {verification_dir}")
    else:
        log.info("  File Verification Layer WYŁĄCZONY")

    # --- BookGuardian (Read-Only Protection for Księga) ---
    if cfg and cfg.ksiega_path:
        book_guardian = BookGuardian(
            ksiega_path=cfg.ksiega_path,
            human_gate=human_gate,
            context_persistence=ctx_persistence,
            log_dir=results_dir / "book_guardian",
            auto_halt=True,
        )
        log.info("  ✓ BookGuardian zainicjalizowany — Księga=%s SHA=%s",
                 cfg.ksiega_path, book_guardian.baseline_sha[:16])
    else:
        log.info("  BookGuardian POMINIĘTY — brak ścieżki do Księgi")

    # --- BudgetGuard (Global Daily Cost Cap) ---
    budget_guard = BudgetGuard(
        max_cost_usd_per_day=cfg.max_cost_usd_per_day if cfg else 50.0,
        warning_threshold=cfg.budget_warning_threshold if cfg else 0.80,
        human_gate=human_gate,
        log_dir=results_dir / "budget",
    )
    log.info("  ✓ BudgetGuard zainicjalizowany — cap=$%.2f, warning=%.0f%%",
             budget_guard.max_cost_usd_per_day,
             budget_guard.warning_threshold * 100)

    # --- Anti-Hallucination Layer 2: BuildVerification ---
    if cfg and cfg.build_verification_enabled:
        build_verifier = BuildVerification(
            workspace=cfg.workspace,
            run_tests=cfg.build_run_tests,
            test_timeout_s=cfg.build_test_timeout_s,
            vet_timeout_s=cfg.build_vet_timeout_s,
            build_timeout_s=cfg.build_build_timeout_s,
            log_dir=results_dir / "build_verification",
        )
        log.info("  ✓ BuildVerification (Layer 2) zainicjalizowany — tests=%s",
                 cfg.build_run_tests)
    else:
        log.info("  BuildVerification (Layer 2) WYŁĄCZONY")

    # --- Anti-Hallucination Layer 3: ClaimProvenance ---
    if cfg and cfg.claim_provenance_enabled:
        claim_prover = ClaimProvenance(
            workspace=cfg.workspace,
            context_window=cfg.provenance_context_window,
            min_match_ratio=cfg.provenance_min_match_ratio,
            log_dir=results_dir / "claim_provenance",
        )
        log.info("  ✓ ClaimProvenance (Layer 3) zainicjalizowany — window=%d, ratio=%.2f",
                 cfg.provenance_context_window, cfg.provenance_min_match_ratio)
    else:
        log.info("  ClaimProvenance (Layer 3) WYŁĄCZONY")

    # --- Anti-Hallucination Layer 4: SemanticDedup ---
    if cfg and cfg.semantic_dedup_enabled:
        semantic_deduper = SemanticDedup(
            similarity_threshold=cfg.dedup_similarity_threshold,
            model_name=cfg.dedup_model_name,
            log_dir=results_dir / "semantic_dedup",
        )
        log.info("  ✓ SemanticDedup (Layer 4) zainicjalizowany — threshold=%.2f, backend=%s",
                 cfg.dedup_similarity_threshold, semantic_deduper.backend.value)
    else:
        log.info("  SemanticDedup (Layer 4) WYŁĄCZONY")

    # --- Anti-Hallucination Layer 5: FactCheckerAgent ---
    if cfg and cfg.fact_checker_enabled:
        # Wire FactChecker to an actual LLM instance — use a DIFFERENT model
        # than the auditors to ensure independent verification (P0-B fix).
        _fc_model_name = cfg.fact_checker_model or "claude"
        # Prefer a model different from the primary auditors for independence.
        _fc_preferred_order = ["gpt", "gemini", "perplexity", "claude"]
        _fc_llm = None
        for _fc_candidate in _fc_preferred_order:
            if _fc_candidate != _fc_model_name:
                try:
                    _fc_llm = make_llm_by_name(_fc_candidate)
                    _fc_model_name = _fc_candidate
                    break
                except (ValueError, StopIteration):
                    continue
        if _fc_llm is None:
            _fc_llm = make_llm_by_name("claude")
        # T-03 FIX: _fc_llm is an LLM object, not callable.
        # FactCheckerAgent expects llm_caller: (system: str, user: str) -> str.
        _fc_llm_obj = _fc_llm
        def _fc_caller(system: str, user: str) -> str:  # noqa: E306
            return _fc_llm_obj.completion(
                [{"role": "system", "content": system},
                 {"role": "user", "content": user}]
            )["choices"][0]["message"]["content"]
        fact_checker = FactCheckerAgent(
            workspace=cfg.workspace,
            llm_caller=_fc_caller,  # T-03: adapter wraps LLM object as callable
            model_id=_fc_model_name,
            max_items_per_run=cfg.fact_checker_max_items,
            context_lines=cfg.fact_checker_context_lines,
            log_dir=results_dir / "fact_checker",
        )
        log.info("  ✓ FactCheckerAgent (Layer 5) zainicjalizowany — model=%s (LLM wired), max=%d",
                 _fc_model_name, cfg.fact_checker_max_items)
    else:
        log.info("  FactCheckerAgent (Layer 5) WYŁĄCZONY")

    # --- Pion D Runtime: Signaling Server ---
    ice_config = ICEServerConfig(
        stun_urls=[u.strip() for u in (cfg.signaling_stun_urls if cfg else "stun:stun.l.google.com:19302").split(",") if u.strip()],
        turn_urls=[u.strip() for u in (cfg.signaling_turn_urls if cfg else "").split(",") if u.strip()],
        turn_username=cfg.signaling_turn_username if cfg else "",
        turn_credential=cfg.signaling_turn_credential if cfg else "",
    )
    signaling_srv = SignalingServer(
        max_rooms=cfg.signaling_max_rooms if cfg else 50,
        ice_config=ice_config,
    )
    log.info("  ✓ SignalingServer zainicjalizowany — max_rooms=%d, STUN=%s",
             signaling_srv.max_rooms, cfg.signaling_stun_urls if cfg else "default")

    # P1-B fix: start cleanup loop to reclaim stale WebRTC rooms
    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(signaling_srv.start_cleanup_loop())
        log.info("  ✓ SignalingServer cleanup loop uruchomiony")
    except RuntimeError:
        # No running loop yet — will be started when the event loop is active
        log.warning("  ⚠ SignalingServer cleanup loop: brak aktywnej pętli zdarzeń, "
                    "zostanie uruchomiony przy starcie pipeline")

    # --- Pion D Runtime: Device Harness ---
    safe_cmd_runner = SafeCommandRunner(
        dry_run=cfg.device_harness_dry_run if cfg else True,
    )
    device_harness = DeviceHarness(
        runner=safe_cmd_runner,
        battery_threshold_pct=cfg.streaming_battery_threshold_pct if cfg else 20,
    )
    log.info("  ✓ DeviceHarness zainicjalizowany — dry_run=%s, battery_thr=%d%%",
             safe_cmd_runner.dry_run,
             cfg.streaming_battery_threshold_pct if cfg else 20)

    # --- Pion D Runtime: Metrics Ingestion ---
    _metrics_thresholds = [
        ThresholdConfig(
            metric_type=MetricType.LATENCY_VIDEO,
            warning_threshold=float(cfg.streaming_latency_p95_ms if cfg else 150),
            critical_threshold=float(cfg.streaming_latency_p99_ms if cfg else 300),
            unit="ms",
        ),
        ThresholdConfig(
            metric_type=MetricType.BITRATE_VIDEO,
            warning_threshold=float((cfg.streaming_min_bitrate_kbps if cfg else 500) * 1.2),
            critical_threshold=float(cfg.streaming_min_bitrate_kbps if cfg else 500),
            unit="kbps",
            direction="lower",
        ),
        ThresholdConfig(
            metric_type=MetricType.FPS,
            warning_threshold=float((cfg.streaming_target_fps if cfg else 30) * 0.8),
            critical_threshold=float((cfg.streaming_target_fps if cfg else 30) * 0.5),
            unit="fps",
            direction="lower",
        ),
    ]
    _metrics_log_dir = Path(cfg.metrics_log_dir) if (cfg and cfg.metrics_log_dir) else (results_dir / "metrics")
    _max_samples = cfg.metrics_max_samples_per_metric if cfg else 10000
    metrics_collector = MetricsCollector(
        store=MetricsStore(max_samples_per_metric=_max_samples),
        alert_engine=AlertEngine(thresholds=_metrics_thresholds),
        log_dir=_metrics_log_dir,
    )
    log.info("  ✓ MetricsCollector zainicjalizowany — max_samples=%d, thresholds=%d, log=%s",
             cfg.metrics_max_samples_per_metric if cfg else 10000,
             len(_metrics_thresholds), _metrics_log_dir)

    # --- Pion D Runtime: ABR Controller ---
    abr_controller = ABRController(
        initial_rung=cfg.abr_initial_rung if cfg else 1,
    )
    log.info("  ✓ ABRController zainicjalizowany — initial_rung=%d, ladder=%d rungs",
             cfg.abr_initial_rung if cfg else 1, len(abr_controller.ladder))

    # --- Pion D Runtime: Input Protocol ---
    _hmac_key = (cfg.input_protocol_hmac_key.encode() if (cfg and cfg.input_protocol_hmac_key) else b"")
    if _hmac_key:
        input_protocol = InputProtocolCodec(hmac_key=_hmac_key)
    else:
        input_protocol = InputProtocolCodec()  # Uses DEFAULT_HMAC_KEY
    log.info("  ✓ InputProtocol zainicjalizowany — hmac=%s",
             "custom" if _hmac_key else "default")

    # --- Pion D Runtime: Audio Pipeline ---
    _opus_cfg = OpusConfig(
        bitrate_bps=cfg.audio_opus_bitrate_bps if cfg else 32000,
        dtx_enabled=cfg.audio_opus_dtx_enabled if cfg else True,
    )
    audio_pipeline = AudioPipelineController(opus_config=_opus_cfg)
    log.info("  ✓ AudioPipeline zainicjalizowany — bitrate=%d, dtx=%s",
             _opus_cfg.bitrate_bps, _opus_cfg.dtx_enabled)

    # --- Pion D Runtime: Stream Security Verifier ---
    _pinned = [c.strip() for c in (cfg.stream_security_pinned_certs if cfg else "").split(",") if c.strip()]
    stream_security = StreamSecurityVerifier(
        production_mode=cfg.stream_security_production if cfg else True,
        pinned_certs=_pinned or None,
        custom_rate_limits={
            "signaling": cfg.stream_security_signaling_rate if cfg else 50,
            "datachannel": cfg.stream_security_dc_rate if cfg else 200,
        },
    )
    stream_security.WEAK_CIPHER_BLOCK = cfg.stream_security_weak_cipher_block if cfg else True
    stream_security.REQUIRE_RELAY_IN_PROD = cfg.stream_security_require_relay if cfg else True
    log.info("  ✓ StreamSecurityVerifier zainicjalizowany — prod=%s, pins=%d, weak_block=%s",
             stream_security._production_mode, len(_pinned),
             stream_security.WEAK_CIPHER_BLOCK)

    # --- Pion D Benchmark Harness ---
    if cfg and cfg.benchmark_enabled:
        _bench_thresholds = BenchmarkThresholds(
            setup_time_p95_ms=cfg.benchmark_setup_p95_ms,
            input_to_photon_p95_ms=cfg.benchmark_input_photon_p95_ms,
            abr_rampup_max_ms=cfg.benchmark_abr_rampup_ms,
            reconnect_p95_ms=cfg.benchmark_reconnect_p95_ms,
            frame_drop_ratio_fail=cfg.benchmark_frame_drop_fail_pct,
            av_sync_drift_fail_ms=cfg.benchmark_av_sync_fail_ms,
        )
        _bench_output = Path(cfg.benchmark_output_dir) if cfg.benchmark_output_dir else (results_dir / "benchmarks")
        benchmark_harness = BenchmarkHarness(
            thresholds=_bench_thresholds,
            output_dir=_bench_output,
        )
        log.info("  ✓ BenchmarkHarness zainicjalizowany — output=%s", _bench_output)
    else:
        log.info("  BenchmarkHarness WYŁĄCZONY")

    # --- Stream Monitor (real-time metrics consumer) ---
    global stream_monitor_inst
    stream_monitor_inst = StreamMonitor(
        metrics_collector=metrics_collector,
        abr_controller=abr_controller,
        signaling_srv=signaling_srv,
        stream_security=stream_security,
        device_harness=device_harness,
        audio_pipeline=audio_pipeline,
        latency_p95_warn_ms=float(cfg.streaming_latency_p95_ms if cfg else 150),
        latency_p95_crit_ms=float(cfg.streaming_latency_p99_ms if cfg else 300),
        frame_drop_warn_pct=2.0,
        frame_drop_crit_pct=5.0,
    )
    log.info("  ✓ StreamMonitor zainicjalizowany (real-time metrics consumer)")

    # --- E2E Session Controller ---
    global e2e_controller
    e2e_controller = E2ESessionController(
        signaling_srv=signaling_srv,
        device_harness=device_harness,
        metrics_collector=metrics_collector,
        abr_controller=abr_controller,
        input_protocol=input_protocol,
        audio_pipeline=audio_pipeline,
        stream_security=stream_security,
        benchmark_harness=benchmark_harness,
    )
    log.info("  ✓ E2ESessionController zainicjalizowany")

    log.info("  ✓ Supervisor zainicjalizowany")
    log.info(f"    Human Gate:   {'AUTO-APPROVE safe' if hg_params.get('auto_approve_safe') else 'KAŻDA akcja wymaga zgody'}")
    log.info(f"    Loop Guard:   max {lg_params.get('max_iterations', 5)} iteracji/plik, "
             f"próg podobieństwa {lg_params.get('similarity_threshold', 0.7):.0%}")
    log.info(f"    Kontekst:     rolling window {lg_params.get('context_window_size', 50)} wpisów, "
             f"snapshots co 10 operacji")
    log.info(f"    Gate UX:      opisy skutków każdej decyzji WŁĄCZONE")


def is_agent_enabled(name: str) -> bool:
    """Check if an agent is enabled in agents.yaml."""
    if agent_mgr is None:
        return True  # Fallback: all enabled if no manager
    agent = agent_mgr.agents.get(name)
    return agent.enabled if agent else True


def is_stage_enabled(stage: float) -> bool:
    """Check if any agent in a stage is enabled."""
    if agent_mgr is None:
        return True
    return any(
        a.enabled for a in agent_mgr.agents.values() if a.stage == stage
    )

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
log = logging.getLogger("orchestrator")


def setup_logging(level: str, log_file: Path | None = None):
    logging.basicConfig(level=getattr(logging, level.upper()), format=LOG_FORMAT)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(LOG_FORMAT))
        logging.getLogger().addHandler(fh)


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def make_llm(model: ModelConfig) -> LLM:
    return LLM(
        model=model.model_id,
        api_key=SecretStr(model.api_key),
        base_url=model.base_url,
        usage_id=f"sylion-{model.name}",
    )


def make_llm_by_name(name: str) -> LLM:
    # Fala 6 patch P6-07 (F-011): poprawiono next() bez default — wcześniej w async
    # context podnosiło RuntimeError: coroutine raised StopIteration, crashując
    # pipeline bez komunikatu. Teraz explicit ValueError z nazwą nieznanego modelu.
    model = next((m for m in AUDIT_MODELS if m.name == name), None)
    if model is None:
        available = ", ".join(m.name for m in AUDIT_MODELS)
        raise ValueError(
            f"Nieznany model LLM: {name!r}. Dostępne modele: {available}"
        )
    return make_llm(model)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def save_signal(results_dir: Path, name: str, data: dict | None = None):
    """Zapisz sygnał ukończenia etapu."""
    sig_dir = results_dir / "signals"
    sig_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signal": name,
        **(data or {}),
    }
    (sig_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Dashboard Cost Reporting Hook
# ---------------------------------------------------------------------------

def _report_cost_to_dashboard(
    agent_id: str = "",
    stage: str = "",
    cost_usd: float = 0.0,
    elapsed_ms: float = 0.0,
    model_name: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    success: bool = True,
    error: str = "",
    run_id: str = "",
):
    """Send cost record to dashboard API for live monitoring.

    Non-blocking: catches all exceptions silently so pipeline
    continues even if dashboard is offline.
    """
    try:
        import httpx  # Use httpx (already in requirements-lock) instead of requests
        port = os.environ.get("DASHBOARD_PORT", "8421")
        # Infer provider and model_id from model_name
        provider = ""
        model_id = ""
        if "claude" in model_name.lower():
            provider = "anthropic"
        elif "gpt" in model_name.lower():
            provider = "openai"
        elif "gemini" in model_name.lower():
            provider = "google"
        elif "deepseek" in model_name.lower():
            provider = "deepseek"
        elif "grok" in model_name.lower():
            provider = "xai"
        elif "sonar" in model_name.lower():
            provider = "perplexity"

        payload = {
            "run_id": run_id,
            "agent_id": agent_id,
            "model_id": model_id or model_name,
            "provider": provider,
            "model_name": model_name,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
            "latency_ms": elapsed_ms,
            "stage": stage,
            "success": success,
            "error": error,
        }
        internal_key = os.environ.get("SYLION_INTERNAL_API_KEY", "")
        headers = {"X-SYLION-Internal-Key": internal_key} if internal_key else {}
        httpx.post(
            f"http://127.0.0.1:{port}/api/costs/record",
            json=payload,
            headers=headers,
            timeout=3.0,
        )
    except Exception:
        pass  # Dashboard may be offline — never block pipeline

    # v5.9.1 Cluster R: also update in-process cost_tracker (works even when dashboard offline)
    if _ORCH_COST_TRACKER_AVAILABLE and _orch_cost_tracker is not None:
        try:
            # Infer provider from model name (same logic as above)
            _prov = "unknown"
            if "claude" in model_name.lower():
                _prov = "anthropic"
            elif "gpt" in model_name.lower():
                _prov = "openai"
            elif "gemini" in model_name.lower():
                _prov = "google"
            elif "deepseek" in model_name.lower():
                _prov = "deepseek"
            elif "grok" in model_name.lower():
                _prov = "xai"
            elif "sonar" in model_name.lower():
                _prov = "perplexity"

            _orch_cost_tracker.record_llm_call(
                provider=_prov,
                model=model_name,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                cost_usd=cost_usd,
                agent_id=agent_id,
                run_id=run_id,
                latency_ms=elapsed_ms,
                success=success,
                error=error or "",
            )
        except Exception:
            pass  # cost_tracker failure must never block pipeline


# ---------------------------------------------------------------------------
# File Verification Helpers
# ---------------------------------------------------------------------------

def _get_declared_files(agent_id: str) -> list[str]:
    """Get declared_files for an agent from agents.yaml config.

    Returns the list of file paths that the agent is allowed to modify.
    Empty list means 'monitor entire workspace with default extensions'.
    None means 'skip verification for this agent'.
    """
    if agent_mgr is None:
        return []

    agent_cfg = agent_mgr.agents.get(agent_id)
    if agent_cfg is None:
        return []

    # Get declared_files from agent config
    declared = getattr(agent_cfg, "declared_files", None)
    if declared is None:
        # No declared_files attribute — check params
        params = agent_cfg.params or {}
        declared = params.get("declared_files", None)

    if declared is None:
        # Agents without declared_files: auditors, verifiers, testers, etc.
        # These are read-only agents — still monitor for unexpected changes
        return []

    if isinstance(declared, list):
        return declared

    return []


def _extract_claims_from_conversation(conv, agent_id: str) -> list[AgentClaim]:
    """Extract file modification claims from agent conversation events.

    Parses the conversation events to detect which files the agent says
    it modified, created, deleted, etc. Falls back to empty if parsing fails.
    """
    claims: list[AgentClaim] = []

    try:
        from openhands.sdk.llm import content_to_str

        for event in conv.state.events:
            if not hasattr(event, "llm_message"):
                continue

            text = "".join(content_to_str(event.llm_message.content))
            if not text:
                continue

            # Strategy 1: Parse structured JSON patches from agent output
            # Agents produce JSON with "finding_id", "patch", "file" fields
            json_blocks = re.findall(
                r'```json\s*(.+?)```',
                text, re.DOTALL,
            )
            for block in json_blocks:
                try:
                    data = json.loads(block)
                    if isinstance(data, dict):
                        data = [data]
                    if isinstance(data, list):
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            # Check for patch output format
                            fpath = item.get("file", "") or item.get("file_path", "")
                            if fpath and (item.get("patch") or item.get("fix_suggestion")):
                                claims.append(AgentClaim(
                                    file_path=fpath,
                                    action=ClaimAction.FIXED,
                                    description=item.get("title", item.get("changelog_entry", "")),
                                    finding_id=item.get("finding_id"),
                                    agent_id=agent_id,
                                ))
                            elif fpath and item.get("verdict"):
                                # Cross-verify / audit result — NOOP claim
                                claims.append(AgentClaim(
                                    file_path=fpath,
                                    action=ClaimAction.NOOP,
                                    description=f"audit/verify: {item.get('verdict', '')}",
                                    finding_id=item.get("original_id", item.get("id", "")),
                                    agent_id=agent_id,
                                ))
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue

            # Strategy 2: Detect file write operations from tool calls
            if hasattr(event, "tool_call"):
                tc = event.tool_call
                tool_name = getattr(tc, "name", "") or getattr(tc, "function", {}).get("name", "")
                if tool_name in ("file_write", "write_file", "edit_file", "str_replace_editor"):
                    args = getattr(tc, "arguments", {}) or {}
                    fpath = args.get("path", args.get("file_path", ""))
                    if fpath:
                        claims.append(AgentClaim(
                            file_path=fpath,
                            action=ClaimAction.MODIFIED,
                            description=f"Tool call: {tool_name}",
                            agent_id=agent_id,
                        ))

    except Exception as e:
        log.warning(f"Failed to extract claims from conversation: {e}")

    return claims


def run_single_agent(agent, workspace: Path, task: str, label: str,
                     agent_id: str | None = None) -> str:
    """Run a single agent synchronously, through Supervisor if active.

    Flow when Supervisor enabled:
      1. Supervisor registers the agent run in its checklist
      2. Human Gate asks administrator for approval (if not auto-approved)
      3. DeterministicRunner validates all commands (whitelist only)
      4. Agent executes with Safe Runner wrapping subprocess calls
      5. Supervisor records result + updates checklist

    Flow when Supervisor disabled:
      Agent runs directly (legacy mode).
    """
    # P2-C fix: snapshot globals under lock to avoid reading partially-updated
    # references when multiple agents run concurrently via run_in_executor.
    with _globals_lock:
        _supervisor = supervisor
        _human_gate = human_gate
        _agent_mgr = agent_mgr
        _gate_ux = gate_ux
        _consequence_desc = consequence_desc
        _halluc_guard = halluc_guard
        _loop_guard = loop_guard
        _budget_guard = budget_guard

    log.info(f"  ▶ {label}")
    if _agent_mgr and agent_id:
        _agent_mgr.mark_running(agent_id)

    # --- Supervisor: register stage start ---
    if _supervisor:
        _supervisor.on_agent_start(agent_id or label, label, task)

    t0 = time.monotonic()

    try:
        # --- Human Gate: request approval before execution ---
        if _human_gate:
            # Build consequence descriptions if UX layer is available
            consequences = {}
            if _consequence_desc:
                consequences = _consequence_desc.describe_consequences(
                    "agent_run",
                    {"agent_name": agent_id or label, "stage": label,
                     "title": f"Uruchomienie agenta: {label}",
                     "task_preview": task[:500]},
                )

            gate_req = GateRequest(
                id=f"gate-agent-{(agent_id or label)}-{uuid.uuid4().hex[:6]}",
                agent_name=agent_id or label,
                stage=label,
                level=GateLevel.REVIEW,
                title=f"Uruchomienie agenta: {label}",
                description=(
                    f"Agent '{agent_id or label}' chce wykonać zadanie w etapie '{label}'.\n"
                    f"Podgląd: {task[:500]}"
                ),
                action_plan=[{"description": f"Run agent '{label}'", "status": "pending"}],
                risk_assessment="Standardowe uruchomienie agenta w pipeline",
                proposed_commands=[],
            )

            # Enhanced display if available
            if _gate_ux and consequences:
                _gate_ux.display_decision_menu(
                    consequences,
                    gate_level=gate_req.level.value,
                    header={"agent": agent_id or label, "stage": label,
                            "title": f"Uruchomienie agenta: {label}"},
                )

            approval = _human_gate.request_approval(gate_req)
            if approval.decision != GateDecision.APPROVED:
                reason = approval.human_notes or approval.decision.value if approval.decision else "unknown"
                msg = f"Human Gate: ODRZUCONO uruchomienie '{label}' — powód: {reason}"
                log.warning(msg)
                if _supervisor:
                    _supervisor.on_agent_rejected(agent_id or label, msg)
                return f"[REJECTED] {msg}"
            log.info(f"  ✅ Human Gate: ZATWIERDZONO '{label}'")

        # --- File Verification: BEFORE iteration (snapshot declared files) ---
        verification_ctx = None
        if _halluc_guard:
            declared = _get_declared_files(agent_id or label)
            if declared:
                verification_ctx = _halluc_guard.before_iteration(
                    agent_id=agent_id or label,
                    declared_files=declared,
                )
                log.info(f"  📸 FileVerification: snapshot {len(declared)} plików dla '{agent_id or label}'")

        conv = Conversation(
            agent=agent,
            workspace=str(workspace),
            visualizer=DelegationVisualizer(name=label),
        )
        conv.send_message(task)
        conv.run()

        elapsed = time.monotonic() - t0
        cost = conv.conversation_stats.get_combined_metrics().accumulated_cost
        log.info(f"  ✓ {label} — {elapsed:.0f}s, ${cost:.4f}")

        # --- File Verification: AFTER iteration (verify claims vs reality) ---
        if _halluc_guard and verification_ctx:
            claims = _extract_claims_from_conversation(conv, agent_id or label)
            vf_result = _halluc_guard.after_iteration(
                agent_id=agent_id or label,
                claims=claims,
                ctx=verification_ctx,
            )
            # ── GAP-04: auto-feed anti_hallucination_log dashboard table ──
            if vf_result.hallucinations:
                _n_rows = anti_halluc_hook(
                    vf_result=vf_result,
                    agent_id=agent_id or label,
                    run_id=run_id,
                )
                log.info(
                    "  anti_halluc_log: %d violation(s) persisted to dashboard DB",
                    _n_rows,
                )
            # ──────────────────────────────────────────────────────────
            if vf_result.blocked:
                log.error(
                    f"  ⚠️ HALLUCINATION BLOCKED — agent='{agent_id or label}' "
                    f"verdict={vf_result.verdict.value} "
                    f"hallucinations={vf_result.hallucination_count}"
                )
                if _supervisor:
                    _supervisor.on_agent_rejected(
                        agent_id or label,
                        f"FileVerification: {vf_result.hallucination_count} hallucination(s) detected, "
                        f"verdict={vf_result.verdict.value}",
                    )
                return f"[BLOCKED] FileVerification: {vf_result.summary()}"
            elif not vf_result.is_clean:
                log.warning(
                    f"  ⚠ FileVerification: {vf_result.hallucination_count} issues "
                    f"(not blocked) for '{agent_id or label}'"
                )
            else:
                log.info(f"  ✅ FileVerification: {vf_result.summary()}")

        # --- Layer 2: BuildVerification (go vet/build/test po zmianach Go) ---
        if build_verifier and _halluc_guard and verification_ctx:
            # v5.8.5 fix: VerificationResult has files_before/files_after, not snapshots
            go_files = []
            if hasattr(vf_result, 'files_after'):
                for fpath, snap_after in vf_result.files_after.items():
                    if fpath.endswith(".go"):
                        snap_before = vf_result.files_before.get(fpath)
                        if not snap_before or snap_before.sha256 != snap_after.sha256:
                            go_files.append(fpath)
            elif hasattr(vf_result, 'snapshots'):
                go_files = [
                    str(s.path) for s in vf_result.snapshots.values()
                    if s.changed and str(s.path).endswith(".go")
                ]
            if go_files:
                build_result = build_verifier.verify(
                    agent_name=agent_id or label,
                    stage=label,
                    changed_files=go_files,
                )
                if build_result.status in (
                    BuildStatus.FAIL_VET,
                    BuildStatus.FAIL_BUILD,
                    BuildStatus.FAIL_TEST,
                    BuildStatus.ERROR,
                ):
                    log.error(
                        f"  🔧 BuildVerification BLOCKED — agent='{agent_id or label}' "
                        f"status={build_result.status.value} "
                        f"error={build_result.error_message[:200]}"
                    )
                    if _supervisor:
                        _supervisor.on_agent_rejected(
                            agent_id or label,
                            f"BuildVerification: {build_result.error_message}",
                        )
                    return f"[BUILD_FAILED] {build_result.error_message}"
                else:
                    log.info(
                        f"  🔧 BuildVerification: {build_result.status.value} "
                        f"({len(go_files)} Go files checked)"
                    )

        # --- Layer 3: ClaimProvenance (file:line keyword matching) ---
        if claim_prover and _halluc_guard and verification_ctx and 'claims' in dir() and claims:
            prov_results = []
            for claim in claims:
                # Extract keywords from claim description (words > 3 chars)
                keywords = [w for w in claim.description.split() if len(w) > 3][:10]
                prov_claim = ProvenanceClaim(
                    finding_id=claim.finding_id or "",
                    agent_name=claim.agent_id or (agent_id or label),
                    file_path=str(claim.file_path),
                    line_number=0,  # AgentClaim has no line_number
                    keywords=keywords,
                    title=claim.description[:200],
                )
                prov_result = claim_prover.verify_claim(prov_claim)
                prov_results.append(prov_result)

            phantom = [
                r for r in prov_results
                if r.verdict in (ProvenanceVerdict.FILE_MISSING, ProvenanceVerdict.LINE_OOB)
            ]
            weak = [
                r for r in prov_results
                if r.verdict == ProvenanceVerdict.WEAK
            ]

            if phantom:
                log.error(
                    f"  📍 ClaimProvenance BLOCKED — agent='{agent_id or label}' "
                    f"phantom_claims={len(phantom)}/{len(prov_results)}"
                )
                for r in phantom[:3]:
                    log.error(f"      {r.verdict.value}: finding={r.finding_id}")
                if _supervisor:
                    _supervisor.on_agent_rejected(
                        agent_id or label,
                        f"ClaimProvenance: {len(phantom)} phantom claims",
                    )
                return f"[PROVENANCE_FAILED] {len(phantom)} phantom claims"
            elif weak:
                log.warning(
                    f"  📍 ClaimProvenance: {len(weak)}/{len(prov_results)} "
                    f"weak matches (not blocked)"
                )
            else:
                log.info(
                    f"  📍 ClaimProvenance: {len(prov_results)} claims verified"
                )

        # --- BudgetGuard: record cost and check daily cap ---
        if _budget_guard:
            within_budget = _budget_guard.record_cost(
                agent_id=agent_id or label,
                stage=label,
                cost_usd=cost,
                elapsed_sec=elapsed,
            )
            if not within_budget:
                log.error(
                    f"  💰 BudgetGuard: DZIENNY BUDŻET PRZEKROCZONY po '{label}' "
                    f"(${_budget_guard.daily_total:.4f} / ${_budget_guard.max_cost_usd_per_day:.2f}) "
                    f"— pipeline MUSI zostać wstrzymany"
                )
                if _agent_mgr and agent_id:
                    _agent_mgr.mark_completed(agent_id, elapsed=elapsed, cost=cost)
                return f"[BUDGET_EXCEEDED] Daily cost ${_budget_guard.daily_total:.4f} >= cap ${_budget_guard.max_cost_usd_per_day:.2f}"

        # --- Dashboard Cost Hook: send cost to dashboard for live monitoring ---
        _report_cost_to_dashboard(
            agent_id=agent_id or label,
            stage=label,
            cost_usd=cost,
            elapsed_ms=elapsed * 1000,
            model_name=getattr(agent, 'model', '') or '',
            tokens_in=getattr(conv.conversation_stats.get_combined_metrics(), 'accumulated_input_tokens', 0) if conv else 0,
            tokens_out=getattr(conv.conversation_stats.get_combined_metrics(), 'accumulated_output_tokens', 0) if conv else 0,
            success=True,
        )

        if _agent_mgr and agent_id:
            _agent_mgr.mark_completed(agent_id, elapsed=elapsed, cost=cost)

        # --- Supervisor: record completion ---
        if _supervisor:
            _supervisor.on_agent_complete(
                agent_id or label,
                status="completed",
                elapsed=elapsed,
                cost=cost,
            )

        # --- Context Persistence: record completion ---
        if ctx_persistence:
            ctx_persistence.record_event(
                event_type=EventType.ITERATION_END,
                agent_id=agent_id or label,
                description=f"Agent '{agent_id or label}' completed in {elapsed:.0f}s",
                details={"elapsed": elapsed, "cost": cost},
            )

        # Extract last response
        from openhands.sdk.llm import content_to_str
        for event in reversed(conv.state.events):
            if hasattr(event, "llm_message"):
                return "".join(content_to_str(event.llm_message.content))
        return ""

    except Exception as e:
        elapsed = time.monotonic() - t0
        if _agent_mgr and agent_id:
            _agent_mgr.mark_failed(agent_id, str(e))

        # --- Supervisor: record failure ---
        if _supervisor:
            _supervisor.on_agent_complete(
                agent_id or label,
                status="failed",
                elapsed=elapsed,
                error=str(e),
            )
            # Supervisor decides: retry or escalate?
            decision = _supervisor.on_failure_decision(
                agent_id or label, str(e), elapsed
            )
            if decision == "escalate":
                log.error(f"  ⚠️ Supervisor ESKALUJE błąd agenta '{label}' do administratora")
                if _human_gate:
                    escalation_req = GateRequest(
                        id=f"gate-escalation-{uuid.uuid4().hex[:6]}",
                        agent_name=agent_id or label,
                        stage=label,
                        level=GateLevel.CRITICAL,
                        title=f"ESKALACJA: Agent '{label}' zgłosił błąd",
                        description=f"Agent '{label}' zgłosił błąd: {e}",
                        action_plan=[{"description": "Eskalacja błędu do administratora", "status": "pending"}],
                        risk_assessment="Agent krytycznie zawiódł — wymaga interwencji",
                        proposed_commands=[],
                        metadata={"agent": agent_id or label, "error": str(e), "elapsed": elapsed},
                    )
                    if _gate_ux:
                        esc_consequences = _consequence_desc.describe_consequences(
                            "error_escalation",
                            {"agent_name": agent_id or label, "error": str(e)},
                        ) if _consequence_desc else {}
                        if esc_consequences:
                            _gate_ux.display_decision_menu(
                                esc_consequences,
                                gate_level="critical",
                                header={"agent": agent_id or label, "stage": label,
                                        "title": f"ESKALACJA: {label}"},
                            )
                    _human_gate.request_approval(escalation_req)

        # --- Context Persistence: record failure ---
        if ctx_persistence:
            ctx_persistence.record_event(
                event_type=EventType.ESCALATED,
                agent_id=agent_id or label,
                description=f"Agent '{agent_id or label}' failed: {e}",
                details={"error": str(e), "elapsed": elapsed},
            )
        raise


# PIPELINE-012 v6.2.0: global registry of active async agent runs so cancel()
# can propagate through to the HTTP layer (httpx inside litellm).
_ACTIVE_RUNS: dict[str, asyncio.Task] = {}
_ACTIVE_RUNS_LOCK = asyncio.Lock() if False else None  # only for doc — dict ops are atomic


async def _cancel_active_run(run_key: str) -> bool:
    """PIPELINE-012: cancel a running agent by key. Returns True if cancelled."""
    task = _ACTIVE_RUNS.get(run_key)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        return True
    return False


async def run_agent_async(agent, workspace: Path, task: str, label: str,
                          agent_id: str | None = None,
                          timeout_s: int | None = None) -> str:
    """Async wrapper for agent runner.

    FIX PIPELINE-010: Hard per-agent timeout prevents whole pipeline hang
    when one LLM call stalls (no response, network issue, overload).
    Default 300s, overridable via SYLION_AGENT_TIMEOUT env var.

    FIX PIPELINE-012 (v6.2.0): When SYLION_LLM_ASYNC=1 (default for new
    deployments), the agent runs natively in the event loop via
    ``run_single_agent_async`` so that cancellation actually aborts the HTTP
    call through ``litellm.acompletion``. Otherwise falls back to the legacy
    run_in_executor path (sync completion, cancel only stops awaiting).
    """
    # P1-D fix: get_running_loop() instead of deprecated get_event_loop()
    loop = asyncio.get_running_loop()
    if timeout_s is None:
        try:
            timeout_s = int(os.environ.get("SYLION_AGENT_TIMEOUT", "300"))
        except Exception:
            timeout_s = 300

    use_async = os.environ.get("SYLION_LLM_ASYNC", "1") == "1"
    run_key = f"{agent_id or label}-{uuid.uuid4().hex[:6]}"

    try:
        if use_async:
            coro = run_single_agent_async(agent, workspace, task, label, agent_id)
            task_obj = asyncio.create_task(coro, name=run_key)
            _ACTIVE_RUNS[run_key] = task_obj
            try:
                return await asyncio.wait_for(task_obj, timeout=timeout_s)
            finally:
                _ACTIVE_RUNS.pop(run_key, None)
        else:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None, run_single_agent, agent, workspace, task, label, agent_id
                ),
                timeout=timeout_s,
            )
    except asyncio.CancelledError:
        log.warning(f"  ⚠ Agent '{label}' cancelled — HTTP aborted (PIPELINE-012)")
        raise
    except asyncio.TimeoutError:
        log.error(f"  ✗ Agent '{label}' TIMEOUT after {timeout_s}s (PIPELINE-010 safeguard)")
        raise RuntimeError(f"Agent '{label}' timeout after {timeout_s}s")


async def run_single_agent_async(agent, workspace: Path, task: str, label: str,
                                  agent_id: str | None = None) -> str:
    """PIPELINE-012 v6.2.0: Native async agent runner.

    Unlike run_single_agent (which runs in an executor thread), this runs
    directly in the event loop and uses ``Conversation.run_async`` so that
    ``asyncio.CancelledError`` propagates to httpx and closes the connection.

    For feature-parity with the sync path, Human Gate / File Verification /
    Supervisor hooks are delegated back to the sync runner via a thread for
    non-LLM work; ONLY the LLM call itself is async. This keeps cancel
    responsive on the part that matters (the long-running HTTP call).
    """
    # For simplicity + safety, delegate heavy pre/post logic to sync runner
    # in a thread, but make that thread cancellable at await boundary.
    # The key insight: conversation.run_async() uses litellm.acompletion which
    # IS cancellable. We replicate only the minimal flow needed.
    loop = asyncio.get_running_loop()

    # Snapshot globals (same as sync path)
    with _globals_lock:
        _supervisor = supervisor
        _human_gate = human_gate
        _agent_mgr = agent_mgr

    log.info(f"  ▶ {label} [async]")
    if _agent_mgr and agent_id:
        _agent_mgr.mark_running(agent_id)
    if _supervisor:
        _supervisor.on_agent_start(agent_id or label, label, task)

    t0 = time.monotonic()
    try:
        from openhands.sdk import Conversation, DelegationVisualizer
        conv = Conversation(
            agent=agent,
            workspace=str(workspace),
            visualizer=DelegationVisualizer(name=label),
        )
        conv.send_message(task)
        # The actual cancellable HTTP call:
        await conv.run_async()

        elapsed = time.monotonic() - t0
        try:
            cost = conv.conversation_stats.get_combined_metrics().accumulated_cost
        except Exception:
            cost = 0.0
        log.info(f"  ✓ {label} — {elapsed:.0f}s, ${cost:.4f} [async]")

        # Extract last assistant message
        result = ""
        for ev in reversed(conv.state.events):
            if getattr(ev, "role", None) == "assistant":
                result = getattr(ev.llm_message, "content", "") or ""
                break

        if _supervisor:
            try:
                _supervisor.on_agent_complete(agent_id or label, result, cost=cost, elapsed=elapsed)
            except Exception:
                pass
        if _agent_mgr and agent_id:
            try:
                _agent_mgr.mark_completed(agent_id)
            except Exception:
                pass
        return result

    except asyncio.CancelledError:
        elapsed = time.monotonic() - t0
        log.warning(f"  ⚠ {label} CANCELLED after {elapsed:.1f}s [async] (HTTP aborted)")
        # PIPELINE-012: notify supervisor; legacy cost_log persistence was removed in R3.13.
        log.debug("Cancelled run not persisted to legacy DB: %s", agent_id or label)
        if _supervisor:
            try:
                _supervisor.on_agent_rejected(agent_id or label, "Cancelled by user/pipeline")
            except Exception:
                pass
        raise
    except Exception as e:
        elapsed = time.monotonic() - t0
        log.error(f"  ✗ {label} failed [async]: {e}")
        if _supervisor:
            try:
                _supervisor.on_agent_failed(agent_id or label, str(e), elapsed=elapsed)
            except Exception:
                pass
        raise


# ---------------------------------------------------------------------------
# STAGE 1: PREPARE (Księga + Build)
# ---------------------------------------------------------------------------

async def stage_1_prepare(cfg: PipelineConfig, results_dir: Path):
    """Etap 1: Analiza Księgi + budowanie binarek (równolegle)."""
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 1: PREPARE (Księga + Build)     ║")
    log.info("╚═══════════════════════════════════════╝")

    # --- v5.10 LLM Tier Routing (FinOps) ---
    try:
        from tier_routing import select_tier
        _task_description = str(cfg.ksiega_path or cfg.workspace)
        _files = [str(f) for f in cfg.workspace.rglob("*.py")][:50] if cfg.workspace.exists() else []
        tier = select_tier(_task_description, _files)
        cfg.__dict__["model_tier"] = tier.tier.value
        log.info("  LLM Tier Routing: tier=%s models=%s", tier.tier.name, tier.models[:2])
    except Exception as _tier_exc:
        log.warning("  LLM Tier Routing unavailable: %s", _tier_exc)

    (results_dir / "stage1").mkdir(parents=True, exist_ok=True)

    llm_claude = make_llm_by_name("claude")
    ksiega_agent = create_ksiega_analyst(llm_claude)
    build_agent = create_build_agent(llm_claude)

    ksiega_task = f"""Przeanalizuj Księgę i wyekstrahuj wymagania.
{'Księga: ' + str(cfg.ksiega_path) if cfg.ksiega_path else 'Użyj wbudowanych wymagań domyślnych.'}
Zapisz wynik w: {results_dir}/stage1/requirements.json

UWAGA: requirements.json jest DERIVED ARTIFACT — generowany automatycznie
przez ten agent. NIE jest źródłem prawdy. Źródło: Księga SYLION 3.4 FIXED."""

    build_task = f"""Zbuduj binaria SYLION.
Workspace: {cfg.workspace}
Zapisz binaria w: {cfg.workspace}/build/
Zapisz status w: {results_dir}/stage1/build_status.json"""

    # Generuj manifest plików synchronicznie (szybkie)
    go_files = []
    if cfg.packages:
        for pkg in cfg.packages:
            pkg_path = cfg.workspace / pkg
            if pkg_path.exists():
                go_files.extend(str(f.relative_to(cfg.workspace))
                                for f in pkg_path.rglob("*.go")
                                if "vendor" not in str(f) and "_test.go" not in f.name)
    else:
        go_files = [str(f.relative_to(cfg.workspace))
                     for f in cfg.workspace.rglob("*.go")
                     if "vendor" not in str(f) and "_test.go" not in f.name]
    go_files.sort()

    manifest = {"total_files": len(go_files), "files": go_files,
                "packages": sorted(set(str(Path(f).parent) for f in go_files))}
    manifest_path = results_dir / "stage1" / "file_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info(f"  File manifest: {len(go_files)} plików Go")

    # Księga + Build równolegle
    results = await asyncio.gather(
        run_agent_async(ksiega_agent, cfg.workspace, ksiega_task, "Księga Analyst"),
        run_agent_async(build_agent, cfg.workspace, build_task, "Build Agent"),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd Stage 1: {r}")

    save_signal(results_dir, "stage1_done", {"files": len(go_files)})


# ---------------------------------------------------------------------------
# STAGE 2: AUDIT (4 modele równolegle)
# ---------------------------------------------------------------------------

async def stage_2_audit(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 2: AUDIT (4 modele)             ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage2_audit").mkdir(parents=True, exist_ok=True)

    tasks = []
    for model in cfg.get_active_models():
        llm = make_llm(model)
        agent = create_auditor(llm, model.name, model.strengths)
        task_msg = f"""Przeprowadź audyt bezpieczeństwa kodu SYLION.
Przeczytaj wymagania z: {results_dir}/stage1/requirements.json
Przeczytaj listę plików z: {results_dir}/stage1/file_manifest.json
Zapisz findings w: {results_dir}/stage2_audit/audit_{model.name}.json
Po zakończeniu utwórz: {results_dir}/signals/audit_{model.name}_done.json"""

        tasks.append(run_agent_async(agent, cfg.workspace, task_msg, f"Auditor [{model.name}]"))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd audytu: {r}")

    save_signal(results_dir, "stage2_done")


# ---------------------------------------------------------------------------
# STAGE 3: CROSS-VERIFY (4 modele równolegle)
# ---------------------------------------------------------------------------

async def stage_3_cross_verify(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 3: CROSS-VERIFY (4 modele)      ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage3_verify").mkdir(parents=True, exist_ok=True)

    tasks = []
    for model in cfg.get_active_models():
        llm = make_llm(model)
        agent = create_cross_verifier(llm, model.name)
        task_msg = f"""Zweryfikuj findings z audytów INNYCH modeli.
Przeczytaj audyty z: {results_dir}/stage2_audit/ (OPRÓCZ audit_{model.name}.json)
Zapisz weryfikację w: {results_dir}/stage3_verify/verify_{model.name}.json
Po zakończeniu utwórz: {results_dir}/signals/verify_{model.name}_done.json"""

        tasks.append(run_agent_async(agent, cfg.workspace, task_msg, f"Verifier [{model.name}]"))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd weryfikacji: {r}")

    save_signal(results_dir, "stage3_done")


# ---------------------------------------------------------------------------
# STAGE 4: MERGE
# ---------------------------------------------------------------------------

async def stage_4_merge(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 4: MERGE (decyzje)              ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage4_merge").mkdir(parents=True, exist_ok=True)

    # --- Layer 4: SemanticDedup (before merge consensus) ---
    # Load all findings from stage 2 (audit) + stage 3 (cross-verify)
    all_findings = []
    for json_dir in ["stage2_audit", "stage3_verify"]:
        src_dir = results_dir / json_dir
        if src_dir.exists():
            for jf in sorted(src_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text())
                    if isinstance(data, list):
                        all_findings.extend(data)
                    elif isinstance(data, dict) and "findings" in data:
                        all_findings.extend(data["findings"])
                except Exception as e:
                    log.warning(f"  Layer 4: cannot parse {jf.name}: {e}")

    dedup_summary = ""
    if semantic_deduper and all_findings:
        log.info(f"  🔍 SemanticDedup: deduplicating {len(all_findings)} findings")
        dedup_result = semantic_deduper.deduplicate(all_findings)
        canonical = semantic_deduper.get_canonical_findings(all_findings, dedup_result)

        log.info(
            f"  🔍 SemanticDedup: {dedup_result.total_findings} → "
            f"{dedup_result.unique_clusters} unique clusters "
            f"({dedup_result.duplicates_removed} duplicates removed, "
            f"backend={dedup_result.backend})"
        )
        dedup_summary = (
            f"\n\n--- SemanticDedup Report ---\n"
            f"Deduplicated: {dedup_result.total_findings} → {dedup_result.unique_clusters} unique\n"
            f"Removed: {dedup_result.duplicates_removed} duplicates\n"
            f"Backend: {dedup_result.backend}\n"
        )

        # Save dedup results for audit trail
        dedup_out = results_dir / "stage4_merge" / "semantic_dedup_report.json"
        try:
            dedup_out.write_text(json.dumps({
                "total_findings": dedup_result.total_findings,
                "unique_clusters": dedup_result.unique_clusters,
                "duplicates_removed": dedup_result.duplicates_removed,
                "backend": dedup_result.backend,
                "similarity_threshold": dedup_result.similarity_threshold,
                "canonical_count": len(canonical),
            }, indent=2))
        except Exception:
            pass  # Non-blocking: dedup report is informational

        # Save canonical (deduplicated) findings for the merger
        canonical_path = results_dir / "stage4_merge" / "deduped_findings.json"
        try:
            canonical_path.write_text(json.dumps(canonical, indent=2, default=str))
        except Exception:
            pass
    elif not all_findings:
        log.info("  🔍 SemanticDedup: no findings to deduplicate")
    else:
        log.info("  🔍 SemanticDedup: disabled")

    llm = make_llm_by_name("claude")
    agent = create_merger(llm)
    task_msg = f"""Scal findings z audytów i podejmij decyzje.
Audyty: {results_dir}/stage2_audit/
Weryfikacje: {results_dir}/stage3_verify/
Próg konsensusu: {cfg.consensus_threshold}/{len(cfg.get_active_models())}
Zapisz w: {results_dir}/stage4_merge/merged_findings.json{dedup_summary}"""

    await run_agent_async(agent, cfg.workspace, task_msg, "Merger")
    save_signal(results_dir, "stage4_done")


# ---------------------------------------------------------------------------
# STAGE 5: PATCH (4 agenty równolegle)
# ---------------------------------------------------------------------------

async def stage_5_patch(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 5: PATCH (4 agenty + LoopGuard) ║")
    log.info("╚═══════════════════════════════════════╝")

    if cfg.dry_run:
        log.info("  (dry-run) Pomijam patchowanie")
        save_signal(results_dir, "stage5_done", {"dry_run": True})
        return

    (results_dir / "stage5_patch").mkdir(parents=True, exist_ok=True)

    # --- LoopGuard: log patch stage start ---
    if loop_guard:
        log.info("  🛡️ LoopGuard: monitorowanie stage5_patch (max 5 iteracji/plik)")

    llm = make_llm_by_name("claude")
    tasks = []
    merged_findings = f"{results_dir}/stage4_merge/merged_findings.json"
    for partition in range(1, 5):
        # --- LoopGuard: check before each patcher ---
        patcher_id = f"patcher_{partition}"
        file_key = f"stage5_patch/partition_{partition}"
        if loop_guard:
            status = loop_guard.check_loop(patcher_id, file_key)
            if status == LoopStatus.HARD_LIMIT:
                log.warning(f"  🚫 LoopGuard: patcher {partition} ZABLOKOWANY "
                            f"(przekroczono limit iteracji)")
                # Human Gate: show loop menu with consequences
                if human_gate:
                    loop_ux = LoopConsequences()
                    loop_ux.show_loop_menu({
                        "agent_name": patcher_id,
                        "file_path": file_key,
                        "iteration": iteration_tracker.get_iteration_count(file_key) if iteration_tracker else 0,
                        "max_iterations": 5,
                        "current_model": "claude",
                        "alternative_model": "gpt-5",
                        "loop_description": "Patch → Audyt → Nowy bug → Patch → …",
                    })
                continue
            elif status == LoopStatus.WARNING:
                log.warning(f"  ⚠️ LoopGuard: patcher {partition} — zbliża się do limitu")
            elif status == LoopStatus.LOOP_DETECTED:
                log.warning(f"  🔄 LoopGuard: patcher {partition} — wykryto pętlę semantyczną")

        agent = create_patch_agent(llm, partition)
        task_msg = f"""Wygeneruj patche dla findings z partycji {partition}/4.
Merged findings: {results_dir}/stage4_merge/merged_findings.json
Zapisz patche w: {results_dir}/stage5_patch/patches_{partition}.json"""

        tasks.append(run_agent_async(agent, cfg.workspace, task_msg,
                                     f"Patcher [{partition}]", agent_id=patcher_id))

    if not tasks:
        log.error("  🚫 Wszystkie patchery zablokowane przez LoopGuard!")
        save_signal(results_dir, "stage5_blocked", {"reason": "all_patchers_loop_blocked"})
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd patchowania: {r}")
        else:
            # --- LoopGuard: record successful iteration ---
            if loop_guard:
                file_key = f"stage5_patch/partition_{i+1}"
                loop_guard.record_iteration(
                    agent_id=f"patcher_{i+1}",
                    file_path=file_key,
                    action="patch_applied",
                )

    # --- Context Persistence: record stage completion ---
    if ctx_persistence:
        from loop_guard import StageSummary
        num_ok = sum(1 for r in results if not isinstance(r, Exception))
        num_err = sum(1 for r in results if isinstance(r, Exception))
        ctx_persistence.save_stage_summary(StageSummary(
            stage_name="PATCH",
            agents_involved=[f"patcher_{i+1}" for i in range(len(results))],
            findings_found=len(tasks),
            findings_resolved=num_ok,
            findings_remaining=num_err,
            duration_sec=0.0,
            cost_usd=0.0,
            human_decisions=[],
        ))

    # Re-build z patchami
    build_agent = create_build_agent(llm)
    await run_agent_async(build_agent, cfg.workspace,
                          f"Przebuduj binaria po patchach. Status: {results_dir}/stage5_patch/rebuild_status.json",
                          "Re-Build")
    save_signal(results_dir, "stage5_done")


# ---------------------------------------------------------------------------
# STAGE 5.5: RUNTIME (Signaling, Device Harness, Metrics, ABR initialization)
# ---------------------------------------------------------------------------

async def stage_5_5_runtime(cfg: PipelineConfig, results_dir: Path):
    """Initialize Pion D runtime subsystems: signaling, device harness, metrics, ABR.

    This stage ensures all runtime components are alive and ready before
    the deploy stage pushes binaries to devices.
    """
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 5.5: RUNTIME (Pion D init)      ║")
    log.info("╚═══════════════════════════════════════╝")

    runtime_results = {
        "signaling": {"status": "SKIP"},
        "device_harness": {"status": "SKIP"},
        "metrics": {"status": "SKIP"},
        "abr": {"status": "SKIP"},
        "input_protocol": {"status": "SKIP"},
        "audio_pipeline": {"status": "SKIP"},
        "stream_security": {"status": "SKIP"},
        "benchmark_harness": {"status": "SKIP"},
    }

    # --- Signaling: verify readiness ---
    if signaling_srv:
        try:
            stats = signaling_srv.get_stats()
            runtime_results["signaling"] = {
                "status": "OK",
                "max_rooms": signaling_srv.max_rooms,
                "active_rooms": stats.get("total_rooms", 0),
            }
            log.info("  ✓ Signaling: gotowy (max_rooms=%d)", signaling_srv.max_rooms)
        except Exception as e:
            runtime_results["signaling"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ Signaling: %s", e)
    else:
        log.warning("  ⚠ SignalingServer nie zainicjalizowany")

    # --- Device Harness: health check ---
    if device_harness:
        try:
            health = device_harness.health_check_all()
            runtime_results["device_harness"] = {
                "status": "OK",
                "devices": {k: v.state.value if hasattr(v, 'state') else str(v) for k, v in health.items()},
            }
            for dev_name, dev_status in health.items():
                state_str = dev_status.state.value if hasattr(dev_status, 'state') else str(dev_status)
                log.info("  ✓ Device %s: %s", dev_name, state_str)
        except Exception as e:
            runtime_results["device_harness"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ DeviceHarness: %s", e)
    else:
        log.warning("  ⚠ DeviceHarness nie zainicjalizowany")

    # --- Metrics: verify collector ---
    if metrics_collector:
        try:
            dashboard = metrics_collector.get_dashboard()
            runtime_results["metrics"] = {
                "status": "OK",
                "store_stats": dashboard.get("store_stats", {}),
                "thresholds_configured": len(dashboard.get("alert_stats", {}).get("threshold_count", [])) if isinstance(dashboard.get("alert_stats"), dict) else 0,
            }
            log.info("  ✓ Metrics: gotowy (thresholds=%d)",
                     runtime_results["metrics"].get("thresholds_configured", 0))
        except Exception as e:
            runtime_results["metrics"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ MetricsCollector: %s", e)
    else:
        log.warning("  ⚠ MetricsCollector nie zainicjalizowany")

    # --- ABR: verify controller ---
    if abr_controller:
        try:
            abr_stats = abr_controller.get_stats()
            current = abr_controller.get_current_settings()
            runtime_results["abr"] = {
                "status": "OK",
                "current_rung": abr_stats.get("current_rung", -1),
                "state": abr_stats.get("state", "unknown"),
                "resolution": current.resolution,
                "bitrate_kbps": current.bitrate_kbps,
            }
            log.info("  ✓ ABR: rung=%d, %s @ %d kbps, state=%s",
                     abr_stats.get("current_rung", -1),
                     current.resolution,
                     current.bitrate_kbps,
                     abr_stats.get("state", "unknown"))
        except Exception as e:
            runtime_results["abr"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ ABRController: %s", e)
    else:
        log.warning("  ⚠ ABRController nie zainicjalizowany")

    # --- Input Protocol: health check ---
    if input_protocol:
        try:
            ip_stats = input_protocol.get_stats()
            runtime_results["input_protocol"] = {
                "status": "OK",
                "protocol_version": ip_stats.get("protocol_version", 0),
                "hmac_enabled": ip_stats.get("hmac_enabled", False),
            }
            log.info("  ✓ InputProtocol: gotowy (v%d, hmac=%s)",
                     ip_stats.get("protocol_version", 0),
                     ip_stats.get("hmac_enabled", False))
        except Exception as e:
            runtime_results["input_protocol"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ InputProtocol: %s", e)
    else:
        log.warning("  ⚠ InputProtocol nie zainicjalizowany")

    # --- Audio Pipeline: health check ---
    if audio_pipeline:
        try:
            ap_stats = audio_pipeline.get_stats()
            runtime_results["audio_pipeline"] = {
                "status": "OK",
                "codec": ap_stats.get("codec", "unknown"),
                "sample_rate": ap_stats.get("sample_rate", 0),
                "echo_cancel": ap_stats.get("echo_cancel_state", "unknown"),
            }
            log.info("  ✓ AudioPipeline: gotowy (codec=%s, rate=%d)",
                     ap_stats.get("codec", "unknown"),
                     ap_stats.get("sample_rate", 0))
        except Exception as e:
            runtime_results["audio_pipeline"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ AudioPipeline: %s", e)
    else:
        log.warning("  ⚠ AudioPipeline nie zainicjalizowany")

    # --- Stream Security: health check ---
    if stream_security:
        try:
            sec_health = stream_security.health_check()
            sec_stats = stream_security.get_stats()
            runtime_results["stream_security"] = {
                "status": "OK" if sec_health == SecCheckResult.PASS else "WARN",
                "production_mode": sec_stats.get("production_mode", False),
                "active_sessions": sec_stats.get("active_sessions", 0),
                "pinned_certs": sec_stats.get("pinned_certs", 0),
            }
            log.info("  ✓ StreamSecurity: gotowy (prod=%s, sessions=%d)",
                     sec_stats.get("production_mode", False),
                     sec_stats.get("active_sessions", 0))
        except Exception as e:
            runtime_results["stream_security"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ StreamSecurity: %s", e)
    else:
        log.warning("  ⚠ StreamSecurityVerifier nie zainicjalizowany")

    # --- Benchmark Harness: health check ---
    if benchmark_harness:
        try:
            bh_health = benchmark_harness.health_check()
            bh_stats = benchmark_harness.get_stats()
            runtime_results["benchmark_harness"] = {
                "status": "OK" if bh_health == "OK" else "WARN",
                "benchmarks": bh_stats.get("benchmarks", []),
                "total_runs": bh_stats.get("total_runs", 0),
            }
            log.info("  ✓ BenchmarkHarness: gotowy (%d benchmarków, %d runów)",
                     len(bh_stats.get("benchmarks", [])),
                     bh_stats.get("total_runs", 0))
        except Exception as e:
            runtime_results["benchmark_harness"] = {"status": "ERROR", "error": str(e)}
            log.error("  ✗ BenchmarkHarness: %s", e)
    else:
        log.warning("  ⚠ BenchmarkHarness nie zainicjalizowany")

    # --- Save results ---
    ok_count = sum(1 for v in runtime_results.values() if v.get("status") == "OK")
    total = len(runtime_results)
    log.info("  Stage 5.5 RUNTIME: %d/%d subsystems OK", ok_count, total)

    save_signal(results_dir, "stage5_5_done", {
        "runtime_results": runtime_results,
        "ok_count": ok_count,
        "total": total,
    })

    # --- Supervisor checkpoint ---
    if supervisor:
        supervisor.on_stage_complete(5.5, "RUNTIME", {
            "ok_count": ok_count,
            "total": total,
            "results": runtime_results,
        })


# ---------------------------------------------------------------------------
# STAGE 5.6: FACT-CHECK (Layer 5 — independent LLM verification)
# ---------------------------------------------------------------------------

async def stage_5_6_fact_check(cfg: PipelineConfig, results_dir: Path):
    """Layer 5: Independent LLM fact-check of merged findings before deploy.

    Reads merged_findings.json from stage 4, converts each finding to
    FactCheckItem, runs FactCheckerAgent.check_all(), blocks pipeline on
    hallucinations.
    """
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 5.6: FACT-CHECK (Layer 5)        ║")
    log.info("╚═══════════════════════════════════════╝")

    if not fact_checker:
        log.info("  FactCheckerAgent WYŁĄCZONY — pomijam")
        save_signal(results_dir, "stage5_6_done", {"skipped": True, "reason": "fact_checker disabled"})
        return

    # Load merged findings from stage 4
    merged_path = results_dir / "stage4_merge" / "merged_findings.json"
    if not merged_path.exists():
        log.warning("  Brak merged_findings.json — pomijam fact-check")
        save_signal(results_dir, "stage5_6_done", {"skipped": True, "reason": "no merged findings"})
        return

    try:
        merged_data = json.loads(merged_path.read_text())
        if isinstance(merged_data, dict) and "findings" in merged_data:
            findings_list = merged_data["findings"]
        elif isinstance(merged_data, list):
            findings_list = merged_data
        else:
            findings_list = []
    except Exception as e:
        log.error(f"  Cannot parse merged_findings.json: {e}")
        save_signal(results_dir, "stage5_6_done", {"skipped": True, "reason": str(e)})
        return

    if not findings_list:
        log.info("  No findings to fact-check")
        save_signal(results_dir, "stage5_6_done", {"skipped": True, "reason": "empty findings"})
        return

    # Convert findings to FactCheckItems
    fc_items = []
    for f in findings_list[:cfg.fact_checker_max_items]:
        fc_items.append(FactCheckItem(
            finding_id=f.get("id", f.get("finding_id", "")),
            file_path=f.get("file", f.get("file_path", "")),
            line_number=f.get("line", f.get("line_number", 0)),
            title=f.get("title", ""),
            description=f.get("description", ""),
            severity=f.get("severity", "MEDIUM"),
            evidence=f.get("evidence", ""),
            fix_suggestion=f.get("fix_suggestion", ""),
            patch_diff=f.get("patch", f.get("patch_diff", "")),
            agent_name=f.get("agent_name", f.get("model", "unknown")),
        ))

    log.info(f"  🧐 FactChecker: checking {len(fc_items)} findings")
    fc_report: FactCheckReport = fact_checker.check_all(fc_items)

    # T-03: sanity guard — too many errors indicates broken LLM caller
    if fc_items and fc_report.errors > len(fc_items) * 0.5:
        raise RuntimeError(
            f"FactChecker broken: too many errors "
            f"({fc_report.errors}/{len(fc_items)} findings returned ERROR verdict)"
        )

    log.info(
        f"  🧐 FactChecker: confirmed={fc_report.confirmed} "
        f"disputed={fc_report.disputed} "
        f"hallucinations={fc_report.hallucinations} "
        f"inconclusive={fc_report.inconclusive} "
        f"errors={fc_report.errors} "
        f"({fc_report.total_elapsed_seconds:.1f}s)"
    )

    # Save report
    fc_out = results_dir / "stage4_merge" / "fact_check_report.json"
    try:
        from dataclasses import asdict
        fc_out.write_text(json.dumps(asdict(fc_report), indent=2, default=str))
    except Exception:
        pass  # Non-blocking

    # Block on hallucinations
    if fc_report.hallucinations > 0:
        msg = (
            f"FactChecker: {fc_report.hallucinations} hallucination(s) detected "
            f"out of {fc_report.total_items} findings"
        )
        log.error(f"  ❌ {msg}")

        # Human Gate: require approval to proceed despite hallucinations
        if human_gate:
            consequences = {}
            if consequence_desc:
                consequences = consequence_desc.describe_consequences(
                    "fact_check_hallucination",
                    {"hallucinations": fc_report.hallucinations,
                     "total_items": fc_report.total_items,
                     "disputed": fc_report.disputed},
                )
            gate_req = GateRequest(
                id=f"gate-factcheck-{uuid.uuid4().hex[:6]}",
                agent_name="fact_checker",
                stage="5.6_fact_check",
                level=GateLevel.CRITICAL,
                title=f"FactChecker: {fc_report.hallucinations} hallucination(s)",
                description=msg,
                action_plan=[{"description": "Review hallucinated findings", "status": "pending"}],
                risk_assessment="Hallucinated findings may lead to incorrect patches",
                proposed_commands=[],
                metadata={"consequences": consequences} if consequences else {},
            )
            if gate_ux and consequences:
                gate_ux.display_decision_menu(
                    consequences,
                    gate_level="critical",
                    header={"agent": "fact_checker", "stage": "5.6_fact_check",
                            "title": f"Hallucination detected"},
                )
            approval = human_gate.request_approval(gate_req)
            if approval.decision != GateDecision.APPROVED:
                log.error("  Human Gate: FACT-CHECK ODRZUCONY — pipeline wstrzymany")
                save_signal(results_dir, "stage5_6_blocked", {
                    "hallucinations": fc_report.hallucinations,
                    "reason": "human_gate_rejected",
                })
                return
            log.warning("  Human Gate: ZATWIERDZONO kontynuację mimo hallucination(s)")
    elif fc_report.disputed > 0:
        log.warning(
            f"  ⚠️ FactChecker: {fc_report.disputed} disputed finding(s) — "
            f"kontynuacja (nie blokujące)"
        )

    # Supervisor checkpoint
    if supervisor:
        supervisor.on_stage_complete(5.6, "FACT-CHECK", {
            "confirmed": fc_report.confirmed,
            "disputed": fc_report.disputed,
            "hallucinations": fc_report.hallucinations,
            "inconclusive": fc_report.inconclusive,
            "errors": fc_report.errors,
            "total_items": fc_report.total_items,
        })

    save_signal(results_dir, "stage5_6_done", {
        "confirmed": fc_report.confirmed,
        "disputed": fc_report.disputed,
        "hallucinations": fc_report.hallucinations,
    })


# ---------------------------------------------------------------------------
# STAGE 6: DEPLOY (Pixel + Router równolegle)
# ---------------------------------------------------------------------------

async def stage_6_deploy(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 6: DEPLOY (Pixel + Router)      ║")
    log.info("╚═══════════════════════════════════════╝")

    if cfg.dry_run:
        log.info("  (dry-run) Pomijam deployment")
        save_signal(results_dir, "stage6_done", {"dry_run": True})
        return

    (results_dir / "stage6_deploy").mkdir(parents=True, exist_ok=True)
    llm = make_llm_by_name("claude")

    pixel_agent = create_pixel_deployer(llm)
    router_agent = create_router_deployer(llm)

    results = await asyncio.gather(
        run_agent_async(pixel_agent, cfg.workspace,
                        f"Wdróż SYLION na Pixel. Binaria: {cfg.workspace}/build/arm64/. Status: {results_dir}/stage6_deploy/pixel_status.json",
                        "Pixel Deployer"),
        run_agent_async(router_agent, cfg.workspace,
                        f"Wdróż SYLION relay na router. Binaria: {cfg.workspace}/build/amd64/. Status: {results_dir}/stage6_deploy/router_status.json",
                        "Router Deployer"),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd deploymentu: {r}")

    save_signal(results_dir, "stage6_done")


# ---------------------------------------------------------------------------
# STAGE 7: TEST (4 typy równolegle)
# ---------------------------------------------------------------------------

async def stage_7_test(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 7: TEST (unit/integ/e2e/regr)   ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage7_test").mkdir(parents=True, exist_ok=True)

    test_types = ["unit", "integration", "e2e", "regression"]
    model_assignments = {
        "unit": "gpt", "integration": "gpt",
        "e2e": "claude", "regression": "gemini",
    }

    tasks = []
    for tt in test_types:
        model_name = model_assignments.get(tt, "claude")
        try:
            llm = make_llm_by_name(model_name)
        except (ValueError, StopIteration):
            llm = make_llm_by_name("claude")

        agent = create_test_agent(llm, tt)
        task_msg = f"""Uruchom testy {tt} dla SYLION.
Workspace: {cfg.workspace}
Deploy status: {results_dir}/stage6_deploy/
Zapisz wyniki: {results_dir}/stage7_test/{tt}_results.json"""

        tasks.append(run_agent_async(agent, cfg.workspace, task_msg, f"Tester [{tt}]"))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd testu: {r}")

    save_signal(results_dir, "stage7_done")


# ---------------------------------------------------------------------------
# STAGE 8: RED/BLUE TEAM (4 agenty równolegle)
# ---------------------------------------------------------------------------

async def stage_8_security(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 8: SECURITY (Red + Blue Team)   ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage8_security").mkdir(parents=True, exist_ok=True)
    llm_claude = make_llm_by_name("claude")

    try:
        llm_gpt = make_llm_by_name("gpt")
    except (ValueError, StopIteration):
        llm_gpt = llm_claude

    try:
        llm_gemini = make_llm_by_name("gemini")
    except (ValueError, StopIteration):
        llm_gemini = llm_claude

    red_net = create_red_team_agent(llm_claude, "network")
    red_app = create_red_team_agent(llm_gpt, "app")
    blue_mon = create_blue_team_agent(llm_gemini, "monitor")
    blue_hard = create_blue_team_agent(llm_claude, "hardener")

    # Red Team i Blue Team Monitor startują jednocześnie
    # Blue Team Monitor musi obserwować co robi Red Team
    results = await asyncio.gather(
        run_agent_async(red_net, cfg.workspace,
                        f"Przeprowadź testy penetracyjne sieciowe. Zapisz: {results_dir}/stage8_security/red_network.json",
                        "Red Team [network]"),
        run_agent_async(red_app, cfg.workspace,
                        f"Przeprowadź testy penetracyjne aplikacji. Zapisz: {results_dir}/stage8_security/red_app.json",
                        "Red Team [app]"),
        run_agent_async(blue_mon, cfg.workspace,
                        f"Monitoruj urządzenia podczas ataków Red Team. Zapisz: {results_dir}/stage8_security/blue_monitor.json",
                        "Blue Team [monitor]"),
        run_agent_async(blue_hard, cfg.workspace,
                        f"Przygotuj rekomendacje hardeningu. Audyty: {results_dir}/stage4_merge/. Zapisz: {results_dir}/stage8_security/blue_hardening.json",
                        "Blue Team [hardener]"),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd security: {r}")

    save_signal(results_dir, "stage8_done")


# ---------------------------------------------------------------------------
# STAGE 8.5: SDR TESTING (HackRF + LimeSDR — 3 agenty)
# ---------------------------------------------------------------------------

async def stage_8_5_sdr(cfg: PipelineConfig, results_dir: Path):
    """Etap 8.5: Testy RF — pasywny monitoring IMSI + aktywny rogue BTS pentest."""
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 8.5: SDR (HackRF + LimeSDR)    ║")
    log.info("╚═══════════════════════════════════════╝")

    if cfg.dry_run:
        log.info("  (dry-run) Pomijam testy SDR")
        save_signal(results_dir, "stage8_5_done", {"dry_run": True})
        return

    (results_dir / "stage8_5_sdr").mkdir(parents=True, exist_ok=True)
    llm_claude = make_llm_by_name("claude")

    try:
        llm_gpt = make_llm_by_name("gpt")
    except (ValueError, StopIteration):
        llm_gpt = llm_claude

    try:
        llm_gemini = make_llm_by_name("gemini")
    except (ValueError, StopIteration):
        llm_gemini = llm_claude

    sdr_monitor = create_sdr_monitor_agent(llm_claude)
    rf_red = create_rf_red_team_agent(llm_gpt)
    rf_blue = create_rf_blue_team_agent(llm_gemini)

    # Phase A: Pasywny monitoring IMSI/IMEI (baseline PRZED aktualizacją)
    log.info("  Phase A: Pasywny monitoring — baseline IMSI/IMEI")
    await run_agent_async(
        sdr_monitor, cfg.workspace,
        f"""Przeprowadź pasywny monitoring IMSI/IMEI routera mobilnego.

Workflow:
1. Sprawdź sprzęt HackRF: `bash sdr/passive_monitor.sh check`
2. Skanuj stacje bazowe: `bash sdr/passive_monitor.sh scan`
3. Przechwyć identyfikatory baseline: `bash sdr/passive_monitor.sh full baseline`
4. Po zakończeniu Stage 6 (deploy) — przechwyć ponownie: `bash sdr/passive_monitor.sh full compare`
5. Porównaj IMSI/IMEI przed i po aktualizacji firmware.

Deploy status: {results_dir}/stage6_deploy/
Zapisz wyniki w: {results_dir}/stage8_5_sdr/passive_monitor.json
Zapisz pliki PCAP w: {results_dir}/stage8_5_sdr/pcap/""",
        "SDR Monitor [passive]",
    )

    # Phase B: Aktywny pentest (Red Team RF) + monitoring (Blue Team RF) — równolegle
    log.info("  Phase B: Rogue BTS pentest + RF Blue Team monitoring")
    results = await asyncio.gather(
        run_agent_async(
            rf_red, cfg.workspace,
            f"""Przeprowadź aktywny pentest RF z użyciem LimeSDR i srsRAN.

DOMYŚLNY TRYB: ZeroMQ (symulacja bez RF — bezpieczne).
Do trybu RF: ustaw SYLION_BTS_MODE=rf (WYMAGA klatki Faradaya).

Scenariusze:
1. Aktywne przechwycenie IMSI: `SYLION_BTS_MODE=zmq bash sdr/rogue_bts.sh attack`
2. Downgrade attack (4G→2G)
3. Traffic injection przez fałszywą BTS
4. Denial of Service (tylko symulacja)

Wyniki pasywnego monitoringu: {results_dir}/stage8_5_sdr/passive_monitor.json
Wyniki Red Team sieciowy/app: {results_dir}/stage8_security/
Zapisz w: {results_dir}/stage8_5_sdr/rf_red_team.json""",
            "RF Red Team [rogue BTS]",
        ),
        run_agent_async(
            rf_blue, cfg.workspace,
            f"""Monitoruj urządzenia podczas ataków RF Red Team.

1. Obserwuj logi routera podczas ataku rogue BTS
2. Sprawdź czy SYLION relay wykrywa zmianę Cell ID
3. Mierz czas detekcji (TTD) każdego ataku
4. Weryfikuj zabezpieczenia: cell ID pinning, fallback, LTE-only mode
5. Przygotuj rekomendacje hardeningu RF

Wyniki pasywnego monitoringu: {results_dir}/stage8_5_sdr/passive_monitor.json
Wyniki Blue Team network: {results_dir}/stage8_security/blue_monitor.json
Zapisz w: {results_dir}/stage8_5_sdr/rf_blue_team.json""",
            "RF Blue Team [detection]",
        ),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd SDR: {r}")

    save_signal(results_dir, "stage8_5_done")


# ---------------------------------------------------------------------------
# STAGE 6.5: STREAMING (Pion D — pixel streaming stack)
# ---------------------------------------------------------------------------

async def stage_6_5_streaming(cfg: PipelineConfig, results_dir: Path):
    """Etap 6.5: Pion D — architektura i konfiguracja pixel streamingu."""
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 6.5: STREAMING (Pion D)          ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage6_5_streaming").mkdir(parents=True, exist_ok=True)
    llm_claude = make_llm_by_name("claude")

    try:
        llm_gpt = make_llm_by_name("gpt")
    except (ValueError, StopIteration):
        llm_gpt = llm_claude

    # FIX PIPELINE-006: run_agent_async expects an Agent (conv.agent.llm),
    # not a raw LLM. Previously streaming code passed llm_claude/llm_gpt
    # directly — Conversation.run() failed with
    # `'LLM' object has no attribute 'llm'` and zero artifacts were produced,
    # tripping the Stage 6.5 HARD GATE. Wrap each LLM in a bare Agent here.
    from openhands.sdk import Agent as _SDKAgent
    claude_agent = _SDKAgent(llm=llm_claude, tools=[])
    gpt_agent = _SDKAgent(llm=llm_gpt, tools=[])

    # stream_architect, stream_encoder, stream_transport run in parallel
    # They produce architecture docs + config needed before stream_tester
    tasks = []

    streaming_dir = results_dir / "stage6_5_streaming"

    if is_agent_enabled("stream_architect"):
        architect_task = f"""Jesteś stream_architect — główny architekt pixel streamingu SYLION.

HARDWARE:
  Pixel 8 (GrapheneOS, Tensor G3, hw MediaCodec H.264, no root, /data/local/tmp/sylion/)
  Laptop (WSL, sw x264 fallback, Pipewire audio)
  Router: Mudi 750v2 (OpenWrt, isolated LAN)

STACK: Video H.264, Audio Opus, Transport WebRTC + RTCDataChannel.
Cel: interaktywny remote desktop (nie VOD). Latency < 80ms P50.

WYMAGANE ARTEFAKTY (każdy musi być pełny, nie placeholder):

1. {streaming_dir}/STREAMING-ARCHITECTURE.md:
   ## Component Diagram — mermaid/ascii diagram: Capture → Encode → Packetize → Transport → Decode → Render
   ## Hardware Acceleration Policy — które etapy hw, które sw, decyzje per device
   ## Latency Budget Breakdown — tabela: każdy etap (capture: Xms, encode: Xms, network: Xms, decode: Xms, render: Xms), suma < 80ms P50
   ## Signaling Protocol — jak sesja jest nawiązywana (SDP offer/answer, ICE candidates, session ID)
   ## Codec Selection Rationale — dlaczego H.264 Baseline (not High), dlaczego Opus, upgrade path do AV1/H.265
   ## TURN Strategy — kiedy relay, serwer TURN, fallback, cost/latency trade-off
   ## Failure Modes & Recovery — tabela: awaria → detekcja → recovery → czas

2. {streaming_dir}/SESSION-FLOW.md:
   ## Session Lifecycle — state machine: IDLE → CONNECTING → NEGOTIATING → STREAMING → RECONNECTING → ENDED
   ## SDP Offer/Answer Flow — sequence diagram kto wysyła co, kiedy
   ## ICE Gathering — parallel gathering, candidate trickling, prflx/srflx/relay priority
   ## Renegotiation — kiedy mid-session (resolution change, codec switch, add/remove audio)
   ## Graceful Shutdown — BYE signal, cleanup, resource release

3. {streaming_dir}/TRUST-BOUNDARIES.md:
   ## Trust Zones — diagram: Pixel (untrusted network) | Router (DMZ) | Laptop (trusted)
   ## Per-Zone Security — co chroni każdy odcinek (DTLS, SRTP, mTLS, none)
   ## Key Material Flow — skąd klucze, rotation, co jeśli compromised
   ## Attack Surface — per component (signaling, media, data channel, capture)

4. {streaming_dir}/ADR-STREAM-001-codec-baseline.md:
   ## Context — dlaczego teraz, jakie opcje
   ## Decision — H.264 Baseline + Opus
   ## Consequences — co zyskujemy, co tracimy, migration path
   ## Alternatives Considered — VP8, VP9, AV1, H.265 — dlaczego odrzucone

Deploy status: {results_dir}/stage6_deploy/

Każdy dokument musi być KOMPLETNY. Nie placeholder — gotowy do review."""
        tasks.append(run_agent_async(
            claude_agent, cfg.workspace, architect_task,
            "Stream Architect", agent_id="stream_architect",
        ))

    if is_agent_enabled("stream_encoder"):
        encoder_task = f"""Jesteś stream_encoder — projektujesz encoder pipeline H.264+Opus dla SYLION.

HARDWARE:
  Pixel 8: Tensor G3, hw MediaCodec (H.264 Baseline, max 1080p@30)
  Laptop: sw x264 (Baseline profile), opcjonalnie VA-API
  Bitrate: {cfg.streaming_min_bitrate_kbps}-{cfg.streaming_max_bitrate_kbps} kbps

Cel: interactive remote desktop. Latency < 80ms P50. Każda ms w encoderze się liczy.

WYMAGANE ARTEFAKTY:

1. {streaming_dir}/ENCODER-PROFILE.md:
   ## 1. Pixel 8 HW Encoder (MediaCodec)
   - Profile: Baseline (nie High — kompatybilność + niższe latency)
   - Level: 3.1 (1080p@30)
   - Rate control: CBR (nie VBR — przewidywalny bitrate dla transport)
   - Keyframe interval: 2s (co 60 frameów) — trade-off: szybki seek vs bandwidth spike
   - Entropy coding: CAVLC (nie CABAC — mniej CPU, mniej latency)
   - Slices: 1 (nie multi-slice — Pixel MediaCodec nie wspiera dobrze)
   - Low-latency mode: FEATURE_LowLatency flag, output buffers natychmiast
   - B-frames: 0 (ZERO — każdy B-frame dodaje 1 frame latency)
   - Lookahead: 0 (zero-latency encoding)
   - Color format: NV12 (OMX_COLOR_FormatYUV420SemiPlanar)

   ## 2. Laptop SW Encoder (x264)
   - Preset: ultrafast (najniższe latency)
   - Tune: zerolatency (disables B-frames, reduces lookahead)
   - Profile: Baseline
   - Rate control: CBR z --vbv-bufsize = 1 frame
   - Threads: 4 (balance CPU vs latency)
   - Scene change detection: disabled (avoid keyframe bursts)

   ## 3. Bitrate Ladder
   | Tier     | Resolution | FPS | Bitrate | Keyframe | Use case |
   |----------|-----------|-----|---------|----------|----------|
   | Max      | 1920x1080 | 30  | {cfg.streaming_max_bitrate_kbps}kbps  | 2s | LAN, good WiFi |
   | High     | 1280x720  | 30  | 4000kbps  | 2s | Normal WiFi |
   | Medium   | 960x540   | 24  | 2000kbps  | 3s | Moderate network |
   | Low      | 640x360   | 15  | 1000kbps  | 4s | Poor network |
   | Survival | 640x360   | 10  | {cfg.streaming_min_bitrate_kbps}kbps   | 5s | Near-zero bandwidth |

   ## 4. ABR (Adaptive Bitrate) Logic
   - Signal: TWCC feedback (transport-wide congestion control)
   - Decision: if packet_loss > 5% OR rtt > 150ms → step down
   - Ramp-up: if no loss for 5s AND rtt < 80ms → step up
   - Hysteresis: min 3s between tier changes
   - Emergency: if packet_loss > 20% → jump to Survival immediately

   ## 5. Error Recovery
   - Encoder crash: restart within 100ms, request keyframe
   - Bitrate overshoot: VBV buffer enforces, skip frames if needed
   - Resolution change: seamless via MediaCodec reconfigure (Pixel) / x264 param change (laptop)

2. {streaming_dir}/bitrate_ladder.json — machine-readable:
   {{
     "tiers": [
       {{"name": "max", "width": 1920, "height": 1080, "fps": 30, "bitrate_kbps": {cfg.streaming_max_bitrate_kbps}, "keyframe_s": 2}},
       {{"name": "high", "width": 1280, "height": 720, "fps": 30, "bitrate_kbps": 4000, "keyframe_s": 2}},
       {{"name": "medium", "width": 960, "height": 540, "fps": 24, "bitrate_kbps": 2000, "keyframe_s": 3}},
       {{"name": "low", "width": 640, "height": 360, "fps": 15, "bitrate_kbps": 1000, "keyframe_s": 4}},
       {{"name": "survival", "width": 640, "height": 360, "fps": 10, "bitrate_kbps": {cfg.streaming_min_bitrate_kbps}, "keyframe_s": 5}}
     ],
     "hw_encoder": {{"profile": "Baseline", "level": "3.1", "rc": "CBR", "b_frames": 0, "low_latency": true}},
     "sw_encoder": {{"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline", "threads": 4}}
   }}

To jest ENCODER SPEC, nie marketing. Każdy parametr musi być uzasadniony."""
        tasks.append(run_agent_async(
            claude_agent, cfg.workspace, encoder_task,
            "Stream Encoder", agent_id="stream_encoder",
        ))

    if is_agent_enabled("stream_transport"):
        transport_task = f"""Jesteś stream_transport — projektujesz WebRTC transport layer dla SYLION.

HARDWARE:
  Pixel 8 (GrapheneOS) ↔ Laptop (WSL) via Router (OpenWrt, isolated LAN).
  Sieć: WiFi (Pixel) → Router → Ethernet (Laptop). Możliwy internet via VPN.

Cel: transport video H.264 + audio Opus + input events z latency < 80ms P50.

WYMAGANE ARTEFAKTY:

1. {streaming_dir}/TRANSPORT-CONFIG.md:
   ## 1. ICE Configuration
   - STUN servers: stun.l.google.com:19302 (primary), stun.cloudflare.com:3478 (backup)
   - TURN server: self-hosted coturn na routerze lub VPS (config template)
   - ICE candidate priority: host > srflx > prflx > relay
   - Trickle ICE: enabled, parallel gathering
   - ICE restart: on network change (WiFi → LTE, IP change)

   ## 2. DTLS-SRTP
   - DTLS version: 1.2 (not 1.0)
   - Cipher: TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
   - Certificate: self-signed per session, fingerprint in SDP
   - SRTP profile: SRTP_AES128_CM_HMAC_SHA1_80
   - Key rotation: every 2^31 packets OR 24h (whichever first)
   - Master key derivation: from DTLS handshake

   ## 3. RTCDataChannel (Control + Input)
   - Channel "sylion-input": ordered, maxRetransmits=3 (input events)
   - Channel "sylion-control": ordered, reliable (session control, metrics)
   - Channel "sylion-telemetry": unordered, maxRetransmits=0 (stats, non-critical)
   - SCTP configuration: max message size 16KB, congestion control enabled

   ## 4. Jitter Buffer
   - Video: adaptive 0-200ms, target 40ms, min for interactive
   - Audio: adaptive 20-200ms, target 50ms (see audio_agent)
   - Algorithm: estimate network jitter from RTCP RR, adjust smoothly

   ## 5. Congestion Control
   - Algorithm: Google GCC (transport-wide congestion control, TWCC)
   - Feedback: RTCP TWCC reports every 100ms
   - Response: signal encoder to reduce bitrate on congestion
   - NACK/FEC: NACK for lost packets, no FEC (latency cost too high)

   ## 6. NAT Traversal Scenarios
   - LAN only (router): direct host candidate, no STUN/TURN needed
   - Same WiFi: host candidates should work
   - Remote (VPN/internet): STUN + TURN fallback required
   - Symmetric NAT: TURN relay only
   - Timeout: ICE gathering max 5s, connectivity check max 10s

2. {streaming_dir}/ice_config.json:
   {{
     "stun_servers": ["stun:stun.l.google.com:19302", "stun:stun.cloudflare.com:3478"],
     "turn_servers": [{{"urls": "turn:router.local:3478", "username": "sylion", "credential_type": "password"}}],
     "ice_transport_policy": "all",
     "bundle_policy": "max-bundle",
     "rtcp_mux": true,
     "dtls": {{"version": "1.2", "srtp_profile": "SRTP_AES128_CM_HMAC_SHA1_80"}},
     "data_channels": [
       {{"label": "sylion-input", "ordered": true, "maxRetransmits": 3}},
       {{"label": "sylion-control", "ordered": true, "reliable": true}},
       {{"label": "sylion-telemetry", "ordered": false, "maxRetransmits": 0}}
     ]
   }}

Każda decyzja musi mieć uzasadnienie. Nie pisz ogólników."""
        tasks.append(run_agent_async(
            gpt_agent, cfg.workspace, transport_task,
            "Stream Transport", agent_id="stream_transport",
        ))

    # --- Latency budget injected from config ---
    lb = cfg.streaming_latency_budget
    latency_budget_block = (
        f"LATENCY BUDGET (TWARDE LIMITY — nie sugestie):\n"
        f"  Video P50 < {lb['video_p50_ms']}ms, P95 < {lb['video_p95_ms']}ms, P99 < {lb['video_p99_ms']}ms\n"
        f"  Input event < {lb['input_max_ms']}ms end-to-end\n"
        f"  A/V sync drift < {lb['av_sync_drift_ms']}ms\n"
        f"  Frame drop rate < {lb['frame_drop_max_pct']}%\n"
        f"  Reconnect < {lb['reconnect_timeout_s']}s, TURN fallback < {lb['turn_fallback_s']}s"
    )
    hw_context = (
        f"HARDWARE CONTEXT:\n"
        f"  Pixel 8 (GrapheneOS): Tensor G3, hw MediaCodec H.264, no root (/data/local/tmp/sylion/)\n"
        f"  Laptop (WSL): sw x264 fallback, Pipewire audio\n"
        f"  Router: Mudi 750v2 (OpenWrt), isolated LAN\n"
        f"  Resolution: max {cfg.streaming_max_resolution}, target {cfg.streaming_target_fps}fps\n"
        f"  Bitrate: {cfg.streaming_min_bitrate_kbps}-{cfg.streaming_max_bitrate_kbps} kbps"
    )
    cross_refs = (
        f"CROSS-REFERENCES (read these artifacts if they already exist):\n"
        f"  {streaming_dir}/STREAMING-ARCHITECTURE.md (stream_architect)\n"
        f"  {streaming_dir}/ENCODER-PROFILE.md (stream_encoder)\n"
        f"  {streaming_dir}/TRANSPORT-CONFIG.md (stream_transport)\n"
        f"  Deploy status: {results_dir}/stage6_deploy/"
    )

    if is_agent_enabled("capture_agent"):
        capture_task = f"""Jesteś capture_agent — projektujesz capture pipeline dla pixel streamingu SYLION.

{hw_context}

{latency_budget_block}

TWOJE ZADANIE:
Zaprojektuj pełną architekturę capture backendów: jak przechwytywany jest obraz ekranu
na każdym urządzeniu i podawany do encodera H.264.

{cross_refs}

WYMAGANE ARTEFAKTY:

1. {streaming_dir}/CAPTURE-BACKENDS.md — MUSI zawierać następujące sekcje:
   ## 1. Pixel 8 Capture Backend
   - API: SurfaceFlinger VirtualDisplay vs MediaProjection (decyzja + uzasadnienie)
   - Permissje GrapheneOS: jak uzyskać CAPTURE_VIDEO bez root (foreground service? system dialog?)
   - Format wyjściowy: NV12/I420, rozdzielczość, stride alignment
   - Frame pacing: VSync lock, target {cfg.streaming_target_fps}fps, co gdy GPU throttle
   - Power budget: jak capture wpływa na batterię, kiedy degradować

   ## 2. Laptop Capture Backend
   - API: Pipewire screencast portal vs GStreamer ximagesrc (decyzja + uzasadnienie)
   - Format: co podajemy do x264/vaapi, color space conversion
   - Multi-monitor: który ekran, region selection

   ## 3. Resolution Negotiation Protocol
   - Klient i serwer negocjują rozdzielczość przy connect i na bieżąco
   - Downscale waterfall: {cfg.streaming_max_resolution} → 1280x720 → 960x540 → 640x360
   - Trigger: kiedy downscale (bitrate starvation? thermal? battery?)

   ## 4. Frame Pacing & Timing
   - VSync alignment strategy
   - Timestamp injection (PTS) — niezbędne do A/V sync
   - Dropped frame handling: co gdy encoder nie nadąża

   ## 5. Error Handling & Fallback
   - Capture lost (app minimized, screen off)
   - Permission revoked mid-stream
   - Graceful degradation vs stream kill

2. {streaming_dir}/capture_config.json — strukturalny config:
   {{
     "pixel": {{"api": "...", "format": "...", "max_fps": ..., "hw_accel": true}},
     "laptop": {{"api": "...", "format": "...", "max_fps": ..., "hw_accel": false}},
     "resolution_waterfall": ["1920x1080", "1280x720", "960x540", "640x360"],
     "frame_pacing": {{"vsync_lock": true, "pts_injection": true}}
   }}

NIE pisz ogólników. Każda sekcja musi mieć konkretne API calls, formaty, decyzje."""
        tasks.append(run_agent_async(
            claude_agent, cfg.workspace, capture_task,
            "Capture Agent", agent_id="capture_agent",
        ))

    if is_agent_enabled("input_protocol_agent"):
        input_task = f"""Jesteś input_protocol_agent — projektujesz binary protocol do przesyłania
input events przez RTCDataChannel w pixel streamingu SYLION.

{hw_context}

{latency_budget_block}

KRYTYCZNE: Input latency < {cfg.streaming_input_latency_ms}ms end-to-end.
To znaczy: od momentu dotknięcia ekranu Pixel do momentu gdy serwer przetworzy event.

{cross_refs}

WYMAGANE ARTEFAKTY:

1. {streaming_dir}/DATACHANNEL-PROTOCOL.md — MUSI zawierać:

   ## 1. Wire Format (Binary Protocol)
   - Header: magic(2B) + version(1B) + type(1B) + timestamp(8B) + seq(4B) + length(2B)
   - Event types: TOUCH_DOWN, TOUCH_MOVE, TOUCH_UP, KEY_DOWN, KEY_UP, MOUSE_MOVE, MOUSE_CLICK, SCROLL
   - Touch payload: x(f32) + y(f32) + pressure(f32) + finger_id(u8)
   - Key payload: keycode(u16) + modifiers(u8)
   - Mouse payload: x(i16) + y(i16) + buttons(u8)
   - Endianness: little-endian (natywne na ARM + x86)
   - Max packet size: fit in single DataChannel message (< 16KB)

   ## 2. RTCDataChannel Configuration
   - Label: "sylion-input"
   - Ordered: true (touch events muszą być w kolejności)
   - MaxRetransmits: 3 (nie więcej — stary input jest gorszy niż dropped)
   - Protocol: "sylion-input-v1"

   ## 3. Security
   - Replay protection: sequence number + timestamp window (max 2s staleness)
   - Event signing: HMAC-SHA256 z session key (derived z DTLS handshake)
   - Rate limiting: max 120 events/sec (touch) / 60 events/sec (key)
   - Validation: bounds check (x/y in resolution range), keycode whitelist

   ## 4. Mobile-First Design
   - Multi-touch: up to 10 simultaneous fingers
   - Gesture recognition: pinch-zoom, swipe, long-press (client-side)
   - Virtual keyboard: special event type VIRTUAL_KB_SHOW/HIDE
   - Haptic feedback trigger: server → client HAPTIC event

   ## 5. Latency Optimization
   - Zero-copy path from touch driver to DataChannel
   - Batching: aggregate events within 5ms window
   - Priority: input events > control messages > telemetry

   ## 6. Error Handling
   - Sequence gap detection: request resend or skip
   - Channel close/reopen: re-negotiate without killing video
   - Server overload: backpressure signal (slow down events)

2. {streaming_dir}/input_event_schema.json — formal schema:
   {{
     "header_format": "<2sB B Q I H",
     "event_types": {{
       "TOUCH_DOWN": 1, "TOUCH_MOVE": 2, "TOUCH_UP": 3,
       "KEY_DOWN": 10, "KEY_UP": 11,
       "MOUSE_MOVE": 20, "MOUSE_CLICK": 21, "SCROLL": 22,
       "VIRTUAL_KB_SHOW": 30, "VIRTUAL_KB_HIDE": 31,
       "HAPTIC": 40
     }},
     "max_events_per_sec": {{"touch": 120, "key": 60, "mouse": 60}},
     "security": {{"hmac": "SHA256", "max_staleness_ms": 2000, "seq_window": 256}}
   }}

Bądź KONKRETNY. Podaj dokładne offsety bajtów, rozmiary, struct pack formaty."""
        tasks.append(run_agent_async(
            gpt_agent, cfg.workspace, input_task,
            "Input Protocol Agent", agent_id="input_protocol_agent",
        ))

    if is_agent_enabled("mobile_ux_agent"):
        ux_task = f"""Jesteś mobile_ux_agent — projektujesz UX streamingu na Pixel 8 (GrapheneOS).

{hw_context}

{latency_budget_block}

{cross_refs}

KONTEKST: Użytkownik ogląda streaming z laptopa na Pixel 8 i steruje zdalnie.
To NIE jest YouTube. To INTERAKTYWNY remote desktop. Latency = krytyczne.

WYMAGANE ARTEFAKTY:

1. {streaming_dir}/PIXEL-UX-SPEC.md — MUSI zawierać:

   ## 1. Adaptive Bitrate Policy
   - ABR algorithm: jak mierzyć bandwidth (TWCC feedback, packet loss, RTT)
   - Decision table:
     | Bandwidth | RTT  | Action |
     |-----------|------|--------|
     | > 5Mbps   | < 50ms | Max quality: {cfg.streaming_max_resolution}@{cfg.streaming_target_fps}fps, {cfg.streaming_max_bitrate_kbps}kbps |
     | 2-5Mbps   | 50-100ms | Mid: 1280x720@30fps, 3000kbps |
     | 1-2Mbps   | 100-200ms | Low: 960x540@24fps, 1500kbps |
     | < 1Mbps   | > 200ms | Survival: 640x360@15fps, {cfg.streaming_min_bitrate_kbps}kbps |
   - Hysteresis: nie skaczemy między poziomami częściej niż co 3s
   - Ramp-up: po polepszeniu sieci, podnosimy jakość stopniowo (5s ramp)

   ## 2. Reconnection UX
   - Timeout: max {cfg.streaming_reconnect_timeout_s}s na reconnect
   - UI overlay: "Reconnecting..." z progress ring po 500ms
   - ICE restart: first, then full re-offer/answer
   - Fallback: jeśli P2P umiera → TURN relay (< {cfg.streaming_turn_fallback_s}s)
   - Final fallback: po 3 failed reconnects → "Connection lost" + manual retry button

   ## 3. Quality Indicator Overlay
   - Semi-transparent pill w górnym prawym rogu
   - Kolor: zielony (< {lb['video_p50_ms']}ms), żółty ({lb['video_p50_ms']}-{lb['video_p95_ms']}ms), czerwony (> {lb['video_p95_ms']}ms)
   - Tekst: "42ms | 1080p | 6.2Mbps" (latency | resolution | bitrate)
   - Tap to expand: szczegóły (packet loss, jitter, codec, fps)
   - Auto-hide after 5s, show on tap

   ## 4. Battery-Aware Encoding
   - Threshold: {cfg.streaming_battery_threshold_pct}% battery
   - Below threshold: force low-quality tier, reduce fps to 24, disable hw overlay effects
   - Waking charging: restore previous quality after 30s stabilization
   - Thermal throttle: jeśli CPU temp > 42°C → reduce to 720p, if > 48°C → 540p

   ## 5. Touch Input UX
   - Cursor visualization: small dot where touch lands on remote screen
   - Gesture mapping: pinch → zoom, two-finger scroll → scroll
   - Virtual keyboard: auto-show on text field focus (server-side hint)
   - Edge swipe: reserved for system gestures (don’t capture)

   ## 6. First-Run & Error States
   - Permission dialog: screen capture + microphone (if audio enabled)
   - Network warning: show if on metered connection
   - Incompatible server version: clear error + update link

2. {streaming_dir}/adaptive_bitrate_policy.json — machine-readable:
   {{
     "tiers": [
       {{"name": "max", "min_bw_kbps": 5000, "max_rtt_ms": 50, "resolution": "{cfg.streaming_max_resolution}", "fps": {cfg.streaming_target_fps}, "bitrate_kbps": {cfg.streaming_max_bitrate_kbps}}},
       {{"name": "mid", "min_bw_kbps": 2000, "max_rtt_ms": 100, "resolution": "1280x720", "fps": 30, "bitrate_kbps": 3000}},
       {{"name": "low", "min_bw_kbps": 1000, "max_rtt_ms": 200, "resolution": "960x540", "fps": 24, "bitrate_kbps": 1500}},
       {{"name": "survival", "min_bw_kbps": 0, "max_rtt_ms": 9999, "resolution": "640x360", "fps": 15, "bitrate_kbps": {cfg.streaming_min_bitrate_kbps}}}
     ],
     "hysteresis_s": 3,
     "ramp_up_s": 5,
     "battery_threshold_pct": {cfg.streaming_battery_threshold_pct},
     "thermal_thresholds_c": {{"medium": 42, "critical": 48}}
   }}

To NIE jest mockup. To spec dla implementacji. Bądź precyzyjny."""
        tasks.append(run_agent_async(
            claude_agent, cfg.workspace, ux_task,
            "Mobile UX Agent", agent_id="mobile_ux_agent",
        ))

    if is_agent_enabled("audio_agent"):
        audio_task = f"""Jesteś audio_agent — projektujesz Opus audio pipeline dla pixel streamingu SYLION.

{hw_context}

{latency_budget_block}

KRYTYCZNE: A/V sync drift < {cfg.streaming_av_sync_drift_ms}ms.
Audio musi być zsynchronizowane z video frame timestamps (PTS).

{cross_refs}

WYMAGANE ARTEFAKTY:

1. {streaming_dir}/AUDIO-PIPELINE.md — MUSI zawierać:

   ## 1. Opus Codec Configuration
   - Sample rate: {cfg.streaming_opus_sample_rate}Hz
   - Channels: 1 (mono — remote desktop, nie muzyka)
   - Bitrate: 32kbps (voice) / 64kbps (high quality, on demand)
   - Frame size: 20ms (960 samples @ 48kHz) — balance latency vs efficiency
   - Application mode: OPUS_APPLICATION_RESTRICTED_LOWDELAY
   - Complexity: 5 (balance CPU vs quality on Pixel)

   ## 2. Echo Cancellation
   - Problem: speaker plays audio → mic picks it up → feedback loop
   - Solution: WebRTC AEC3 (built into libwebrtc)
   - Config: tail length 128ms, NLP aggressiveness medium
   - Fallback na Pixel: Android AudioEffect.AcousticEchoCanceler

   ## 3. Noise Suppression
   - WebRTC NS: level 2 (moderate)
   - Comfort noise generation (CNG): enabled during DTX silence
   - VAD: voice activity detection → trigger DTX

   ## 4. DTX (Discontinuous Transmission)
   - Enabled: true
   - Behavior: when no voice detected, send silence indicator (1 packet/400ms)
   - Savings: ~90% bandwidth during silence
   - Resume latency: < 20ms (first voiced frame)

   ## 5. Audio/Video Synchronization
   - Timestamp source: monotonic clock (shared with video capture)
   - PTS injection: audio frame gets timestamp at capture, not at encode
   - Jitter buffer: adaptive 20-200ms, target 50ms
   - Sync algorithm: 
     1. Video frame arrives with PTS_v
     2. Audio frame arrives with PTS_a
     3. If |PTS_v - PTS_a| > {cfg.streaming_av_sync_drift_ms}ms: adjust jitter buffer
     4. If drift > 200ms: hard reset (drop frames to re-sync)
   - Lip sync test: frequency-based (generate beep + flash, measure offset)

   ## 6. Capture Pipeline
   - Pixel: AudioRecord API (VOICE_COMMUNICATION source, AEC pre-applied)
   - Laptop: Pipewire monitor source (captures system audio output)
   - Buffer: ring buffer 4 frames (80ms) to absorb scheduling jitter

   ## 7. Error Handling
   - Mic permission revoked: mute indicator, continue video-only
   - Audio device change (BT connect/disconnect): seamless switch, max 100ms gap
   - Encode failure: skip frame, don't accumulate

2. {streaming_dir}/audio_config.json — machine-readable:
   {{
     "codec": "opus",
     "sample_rate": {cfg.streaming_opus_sample_rate},
     "channels": 1,
     "bitrate_voice_kbps": 32,
     "bitrate_hq_kbps": 64,
     "frame_size_ms": 20,
     "application": "RESTRICTED_LOWDELAY",
     "complexity": 5,
     "dtx": true,
     "dtx_silence_interval_ms": 400,
     "aec": {{"enabled": true, "tail_ms": 128}},
     "ns": {{"enabled": true, "level": 2}},
     "vad": true,
     "jitter_buffer": {{"min_ms": 20, "max_ms": 200, "target_ms": 50}},
     "av_sync_max_drift_ms": {cfg.streaming_av_sync_drift_ms}
   }}

To jest IMPLEMENTACYJNY spec. Podaj konkretne wartości, API, algorytmy."""
        tasks.append(run_agent_async(
            claude_agent, cfg.workspace, audio_task,
            "Audio Agent", agent_id="audio_agent",
        ))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.error(f"  ✗ Błąd streaming stage: {r}")

    # --- HARD GATE: Verify required Pion D artifacts exist + content validation ---
    streaming_dir = results_dir / "stage6_5_streaming"

    # Each tuple: (filename, agent, min_bytes, required_sections)
    # required_sections: list of strings that MUST appear in the file (case-insensitive)
    required_artifacts_6_5 = [
        ("STREAMING-ARCHITECTURE.md", "stream_architect", 2000, [
            "component diagram", "latency budget", "signaling", "failure mode",
        ]),
        ("ENCODER-PROFILE.md", "stream_encoder", 1500, [
            "mediacodec", "x264", "bitrate ladder", "abr",
        ]),
        ("TRANSPORT-CONFIG.md", "stream_transport", 1500, [
            "ice", "dtls", "datachannel", "jitter buffer",
        ]),
        ("CAPTURE-BACKENDS.md", "capture_agent", 1500, [
            "surfaceflinger", "pipewire", "resolution negotiation", "frame pacing",
        ]),
        ("DATACHANNEL-PROTOCOL.md", "input_protocol_agent", 1500, [
            "wire format", "touch", "security", "replay protection",
        ]),
        ("PIXEL-UX-SPEC.md", "mobile_ux_agent", 1500, [
            "adaptive bitrate", "reconnect", "battery", "quality indicator",
        ]),
        ("AUDIO-PIPELINE.md", "audio_agent", 1500, [
            "opus", "echo cancellation", "dtx", "audio/video sync",
        ]),
    ]
    missing = []
    shallow = []
    for artifact_name, agent_name, min_bytes, sections in required_artifacts_6_5:
        if not is_agent_enabled(agent_name):
            continue
        path = streaming_dir / artifact_name
        if not path.exists() or path.stat().st_size == 0:
            missing.append(artifact_name)
            log.error("  ✗ HARD GATE: Missing artifact %s (agent: %s)", artifact_name, agent_name)
            continue
        # Content validation: size + required sections
        content = path.read_text(encoding="utf-8", errors="replace").lower()
        size = len(content)
        if size < min_bytes:
            shallow.append(f"{artifact_name} ({size}B < {min_bytes}B min)")
            log.warning("  ⚠ CONTENT CHECK: %s is too small (%d bytes, min %d)",
                        artifact_name, size, min_bytes)
        missing_sections = [s for s in sections if s.lower() not in content]
        if missing_sections:
            shallow.append(f"{artifact_name} missing sections: {missing_sections}")
            log.warning("  ⚠ CONTENT CHECK: %s missing required sections: %s",
                        artifact_name, missing_sections)

    if missing:
        log.critical(
            "STAGE 6.5 HARD GATE FAILED — %d missing artifacts: %s",
            len(missing), ", ".join(missing),
        )
        if human_gate:
            gate_req = GateRequest(
                id=f"gate-streaming-artifacts-{uuid.uuid4().hex[:6]}",
                agent_name="orchestrator",
                stage="6.5",
                level=GateLevel.CRITICAL,
                title="STREAMING HARD GATE: BRAKUJĄCE ARTEFAKTY",
                description=(
                    f"Stage 6.5 zakończony, ale {len(missing)} wymaganych artefaktów "
                    f"nie istnieje lub jest pusty:\n"
                    + "\n".join(f"  - {m}" for m in missing)
                    + "\n\nPipeline NIE MOŻE przejść do Stage 7 bez tych dokumentów."
                ),
                action_plan=[
                    {"step": "1. Sprawdź logi agentów streaming"},
                    {"step": "2. Re-run brakujących agentów lub utwórz artefakty ręcznie"},
                    {"step": "3. Po uzupełnieniu: wznów pipeline"},
                ],
                risk_assessment=(
                    "Brak dokumentacji streaming uniemożliwia poprawne testy "
                    "w Stage 7.5 i security review. Pipeline musi zostać wstrzymany."
                ),
                proposed_commands=[],
                metadata={"missing_artifacts": missing},
            )
            human_gate.request_approval(gate_req)
        save_signal(results_dir, "stage6_5_failed", {"missing_artifacts": missing})
        raise RuntimeError(f"Stage 6.5 HARD GATE: {len(missing)} missing artifacts")

    log.info("  ✅ Stage 6.5 HARD GATE: All required streaming artifacts present")
    save_signal(results_dir, "stage6_5_done")


# ---------------------------------------------------------------------------
# STAGE 7.5: STREAM TEST (Pion D specific tests)
# ---------------------------------------------------------------------------

async def stage_7_5_stream_test(cfg: PipelineConfig, results_dir: Path):
    """Etap 7.5: Testy Pionu D — latency, frame drops, A/V sync."""
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 7.5: STREAM TEST (Pion D)        ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage7_5_stream_test").mkdir(parents=True, exist_ok=True)

    # ===================================================================
    # Phase A: E2E Session — wire all 8 runtime modules into live session
    # ===================================================================
    if e2e_controller:
        log.info("  Phase A: E2E Session lifecycle")
        e2e_report = e2e_controller.run_e2e(
            initiator_id="pixel",
            peer_id="laptop",
            run_benchmark=bool(benchmark_harness),
        )
        # Save E2E session report
        e2e_path = results_dir / "stage7_5_stream_test" / "e2e_session_report.json"
        e2e_report.save(e2e_path)
        log.info("  E2E session: state=%s, errors=%d, saved to %s",
                 e2e_report.final_state, len(e2e_report.errors), e2e_path)

        # If benchmark was run, also save as standalone artifact for hard gate
        if e2e_report.benchmark:
            bench_path = results_dir / "stage7_5_stream_test" / "benchmark_results.json"
            bench_path.write_text(json.dumps(e2e_report.benchmark, indent=2, default=str))
            log.info("  Benchmark results saved to %s", bench_path)

        # Cleanup session resources
        e2e_controller.cleanup()
    else:
        log.warning("  E2ESessionController nie zainicjalizowany — pomijam Phase A")

    # ===================================================================
    # Phase A.1: Stream Security — active verification (not just health-check)
    # ===================================================================
    if stream_security:
        log.info("  Phase A.1: Stream Security active verification")
        try:
            sec_session_id = f"verify-stage7.5-{uuid.uuid4().hex[:6]}"
            stream_security.register_session(sec_session_id)
            audit = stream_security.run_full_audit(session_id=sec_session_id)
            sec_report_path = results_dir / "stage7_5_stream_test" / "security_active_audit.json"
            sec_report_path.write_text(json.dumps(
                audit.to_dict() if hasattr(audit, 'to_dict') else {},
                indent=2, default=str,
            ))
            overall = audit.overall_level if hasattr(audit, 'overall_level') else 'UNKNOWN'
            log.info("  Security active audit: level=%s, saved to %s", overall, sec_report_path)

            # Block on CRITICAL security
            if hasattr(audit, 'overall_level') and audit.overall_level == SecurityLevel.INSECURE:
                log.error("  ✗ Security CRITICAL — blocking Stage 7.5")
                if human_gate:
                    gate_req = GateRequest(
                        id=f"gate-sec-audit-{uuid.uuid4().hex[:6]}",
                        agent_name="stream_security",
                        stage="7.5_security_audit",
                        level=GateLevel.CRITICAL,
                        title="Stream Security: CRITICAL audit findings",
                        description=(
                            f"Stream security audit found CRITICAL issues. "
                            f"Pipeline should not proceed without resolution."
                        ),
                        action_plan=[{"description": "Review security audit", "status": "pending"}],
                        risk_assessment="CRITICAL security issues in streaming stack",
                        proposed_commands=[],
                        metadata={"audit_path": str(sec_report_path)},
                    )
                    approval = human_gate.request_approval(gate_req)
                    if approval.decision != GateDecision.APPROVED:
                        save_signal(results_dir, "stage7_5_security_blocked", {"reason": "critical_audit"})
                        raise RuntimeError("Stage 7.5 blocked by CRITICAL security audit")

            stream_security.unregister_session(sec_session_id)
        except RuntimeError:
            raise  # Re-raise pipeline blocking errors
        except Exception as e:
            log.warning("  Security active verification error: %s", e)

    # ===================================================================
    # Phase A.2: Stream Monitor — collect real metrics snapshot
    # ===================================================================
    if stream_monitor_inst:
        log.info("  Phase A.2: Stream Monitor snapshot")
        try:
            snap = stream_monitor_inst.collect_snapshot(
                session_id=e2e_controller.session_id if e2e_controller else "stage7.5"
            )
            stream_monitor_inst.save_snapshot(
                snap, results_dir / "stage7_5_stream_test"
            )
            dashboard_path = stream_monitor_inst.save_dashboard(
                results_dir / "stage7_5_stream_test"
            )
            alert_counts = stream_monitor_inst.get_alert_count()
            log.info("  Monitor: latency_p95=%.1fms, fps=%.1f, alerts=%s",
                     snap.latency_p95_ms, snap.fps, alert_counts)
        except Exception as e:
            log.warning("  Stream Monitor error: %s", e)

    # ===================================================================
    # Phase B: Agent-based testing (existing stream_tester + security_verifier)
    # ===================================================================
    if not is_agent_enabled("stream_tester"):
        log.info("  ⏭ stream_tester wyłączony — pomijam Phase B")
        save_signal(results_dir, "stage7_5_done", {"skipped_phase_b": True})
        return

    try:
        llm_gpt = make_llm_by_name("gpt")
    except (ValueError, StopIteration):
        llm_gpt = make_llm_by_name("claude")

    # FIX PIPELINE-006 (stage 7.5 branch): wrap raw LLMs in Agent objects
    # — run_agent_async accesses conv.agent.llm, passing a raw LLM crashes
    # with `'LLM' object has no attribute 'llm'`.
    from openhands.sdk import Agent as _SDKAgent
    gpt_agent = _SDKAgent(llm=llm_gpt, tools=[])

    # Build latency budget block from config (NOT hardcoded)
    lb = cfg.streaming_latency_budget
    latency_budget_str = (
        f"LATENCY BUDGET (from config.py — AUTHORITATIVE, do not hardcode):\n"
        f"  Video P50: {lb['video_p50_ms']}ms\n"
        f"  Video P95: {lb['video_p95_ms']}ms\n"
        f"  Video P99: {lb['video_p99_ms']}ms\n"
        f"  Input max: {lb['input_max_ms']}ms\n"
        f"  A/V sync drift: {lb['av_sync_drift_ms']}ms\n"
        f"  Frame drop max: {lb['frame_drop_max_pct']}%\n"
        f"  Reconnect timeout: {lb['reconnect_timeout_s']}s\n"
        f"  TURN fallback: {lb['turn_fallback_s']}s\n"
        f"  Bitrate range: {cfg.streaming_min_bitrate_kbps}-{cfg.streaming_max_bitrate_kbps} kbps\n"
        f"  Target FPS: {cfg.streaming_target_fps}\n"
        f"  Max resolution: {cfg.streaming_max_resolution}\n"
        f"  Codec: {cfg.streaming_codec_video} + {cfg.streaming_codec_audio}"
    )

    test_task = f"""Jesteś stream_tester — testujesz Pion D pixel streaming SYLION.

HARDWARE:
  Pixel 8 (GrapheneOS, Tensor G3, /data/local/tmp/sylion/)
  Laptop (WSL, x264)
  Router: Mudi 750v2 (OpenWrt, isolated LAN)

{latency_budget_str}

SPECIFICATION DOCS (read BEFORE testing):
  {results_dir}/stage6_5_streaming/STREAMING-ARCHITECTURE.md
  {results_dir}/stage6_5_streaming/ENCODER-PROFILE.md
  {results_dir}/stage6_5_streaming/TRANSPORT-CONFIG.md
  {results_dir}/stage6_5_streaming/CAPTURE-BACKENDS.md
  {results_dir}/stage6_5_streaming/DATACHANNEL-PROTOCOL.md
  {results_dir}/stage6_5_streaming/PIXEL-UX-SPEC.md
  {results_dir}/stage6_5_streaming/AUDIO-PIPELINE.md

Deploy status: {results_dir}/stage6_deploy/

WYMAGANE ARTEFAKTY:

1. {results_dir}/stage7_5_stream_test/streaming_test_results.json:
   - Structure: {{"test_suite": "pion_d_streaming", "timestamp": "...", "results": [...]}}
   - Each result: {{"test": "name", "status": "PASS|FAIL", "measured": value, "threshold": value, "unit": "ms|%|s"}}
   - REQUIRED test categories:
     a. Latency tests (P50, P95, P99 vs budget)
     b. Frame drop rate test (vs {lb['frame_drop_max_pct']}% max)
     c. A/V sync drift test (vs {lb['av_sync_drift_ms']}ms max)
     d. Reconnection time test (vs {lb['reconnect_timeout_s']}s max)
     e. TURN fallback time test (vs {lb['turn_fallback_s']}s max)
     f. Input latency test (vs {lb['input_max_ms']}ms max)
     g. ABR tier switching test (escalation + de-escalation)
     h. Battery impact test (threshold: {cfg.streaming_battery_threshold_pct}%)
   - PASS/FAIL CRITERIA: test passes if measured <= threshold

2. {results_dir}/stage7_5_stream_test/latency_report.md:
   ## Test Environment — hardware, network conditions, test duration
   ## Latency Distribution — histogram or table: P50, P75, P90, P95, P99
   ## Frame Drop Analysis — rate, burst patterns, correlation with bitrate changes
   ## A/V Sync — drift measurement methodology, max observed drift
   ## Reconnection — time-to-first-frame after disconnect
   ## ABR Behavior — tier transitions observed, hysteresis adherence
   ## Recommendations — what needs improvement, what passed

Każdy test musi mieć KONKRETNĄ wartość measured vs threshold. Nie "looks good" — liczby."""


    # Run stream_tester and stream_security_verifier in parallel
    test_tasks = []
    test_tasks.append(run_agent_async(
        gpt_agent, cfg.workspace, test_task,
        "Stream Tester", agent_id="stream_tester",
    ))

    if is_agent_enabled("stream_security_verifier"):
        security_task = f"""Jesteś stream_security_verifier — robisz security review Pionu D streaming SYLION.

HARDWARE:
  Pixel 8 (GrapheneOS, Tensor G3, /data/local/tmp/sylion/)
  Laptop (WSL, x264)
  Router: Mudi 750v2 (OpenWrt, isolated LAN)

{latency_budget_str}

SPECIFICATION DOCS (read ALL before review):
  {results_dir}/stage6_5_streaming/STREAMING-ARCHITECTURE.md
  {results_dir}/stage6_5_streaming/SESSION-FLOW.md
  {results_dir}/stage6_5_streaming/TRUST-BOUNDARIES.md
  {results_dir}/stage6_5_streaming/ENCODER-PROFILE.md
  {results_dir}/stage6_5_streaming/TRANSPORT-CONFIG.md
  {results_dir}/stage6_5_streaming/CAPTURE-BACKENDS.md
  {results_dir}/stage6_5_streaming/DATACHANNEL-PROTOCOL.md
  {results_dir}/stage6_5_streaming/PIXEL-UX-SPEC.md
  {results_dir}/stage6_5_streaming/AUDIO-PIPELINE.md

WYMAGANY ARTEFAKT:

{results_dir}/stage7_5_stream_test/STREAMING-SECURITY-REVIEW.md:

## 1. SRTP Key Management
   - Key derivation: DTLS-SRTP vs SDES (which is used, is SDES disabled?)
   - Key rotation policy: how often, what triggers re-key
   - Forward secrecy: ECDHE vs static keys
   - Vulnerability: key extraction from /data/local/tmp/ (no root, but adb access)

## 2. DTLS Certificate Validation
   - Self-signed vs CA-signed: which approach, fingerprint pinning?
   - Certificate lifetime: rotation, revocation
   - MITM resistance: fingerprint verification in signaling channel
   - Downgrade attacks: TLS 1.2 vs 1.3, cipher suite restrictions

## 3. DataChannel Authentication
   - Input event signing: HMAC verification (from DATACHANNEL-PROTOCOL.md)
   - Replay protection: sequence numbers, nonce handling
   - Authorization: can unauthenticated party send input events?
   - Rate limiting: max events/sec to prevent input flooding

## 4. Capture Permissions
   - Android MediaProjection: user consent flow, permission persistence
   - Can a malicious app intercept the capture stream?
   - Foreground service notification: is it always visible?
   - PipeWire (laptop): portal permissions, sandboxing

## 5. DoS Resistance (USE LATENCY BUDGETS)
   - Signaling flood: max SDP offers/sec, rate limiting
   - Media flood: what happens if attacker sends > {cfg.streaming_max_bitrate_kbps}kbps?
   - ICE candidate flood: max candidates, trickling limits
   - Reconnection abuse: max reconnects within {lb['reconnect_timeout_s']}s window
   - Battery drain attack: force high-resolution encoding to exhaust battery below {cfg.streaming_battery_threshold_pct}%
   - Latency manipulation: force TURN relay to push latency above {lb['video_p99_ms']}ms

## 6. Trust Boundary Violations
   - Per-zone analysis: Pixel (untrusted) | Router (DMZ) | Laptop (trusted)
   - What if router is compromised? Can it decrypt media?
   - What if Pixel is physically seized? Data at rest in /data/local/tmp/
   - Egress: can streaming components leak data to non-whitelisted endpoints?

## 7. Severity Matrix
   Table: Finding | Severity | Likelihood | Impact | Mitigation

Każdy finding musi mieć KONKRETNY atak. Nie "może być podatne" — opisz jak zaatakować."""
        try:
            llm_opus = make_llm_by_name("opus")
        except (ValueError, StopIteration):
            llm_opus = llm_gpt
        # FIX PIPELINE-006: wrap LLM in Agent
        opus_agent = _SDKAgent(llm=llm_opus, tools=[])
        test_tasks.append(run_agent_async(
            opus_agent, cfg.workspace, security_task,
            "Stream Security Verifier", agent_id="stream_security_verifier",
        ))

    results = await asyncio.gather(*test_tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.error(f"  ✗ Błąd stream test stage: {r}")

    # --- HARD GATE: Verify required Stage 7.5 artifacts + content validation ---
    test_dir = results_dir / "stage7_5_stream_test"

    # Each tuple: (filename, agent, min_bytes, required_sections)
    # required_sections: list of strings that MUST appear in the file (case-insensitive)
    required_artifacts_7_5 = [
        ("streaming_test_results.json", "stream_tester", 500, [
            "test_suite", "results", "status", "measured", "threshold",
        ]),
        ("latency_report.md", "stream_tester", 1000, [
            "test environment", "latency", "frame drop", "reconnect",
        ]),
        ("STREAMING-SECURITY-REVIEW.md", "stream_security_verifier", 1500, [
            "srtp", "dtls", "datachannel", "capture", "dos", "trust",
        ]),
        # E2E Session + Benchmark (generated by e2e_controller, not LLM agent)
        ("e2e_session_report.json", "_e2e_controller", 200, [
            "session_id", "final_state", "events",
        ]),
        ("benchmark_results.json", "_e2e_controller", 100, [
            "run_id", "results",
        ]),
        # Security active audit (generated by stream_security verifier)
        ("security_active_audit.json", "_stream_security", 100, [
            "checks",
        ]),
        # Stream Monitor metrics snapshot
        ("streaming_metrics.json", "_stream_monitor", 100, [
            "timestamp", "session_id",
        ]),
    ]
    missing = []
    shallow = []
    for artifact_name, agent_name, min_bytes, sections in required_artifacts_7_5:
        # Internal modules (prefix _) are always "enabled" — they run if their
        # global instance exists; LLM agents check agents.yaml
        if agent_name.startswith("_"):
            # Check if the corresponding global instance is initialized
            _instance_map = {
                "_e2e_controller": e2e_controller,
                "_stream_security": stream_security,
                "_stream_monitor": stream_monitor_inst,
            }
            if _instance_map.get(agent_name) is None:
                continue  # Module not initialized — skip artifact check
        elif not is_agent_enabled(agent_name):
            continue
        path = test_dir / artifact_name
        if not path.exists() or path.stat().st_size == 0:
            missing.append(artifact_name)
            log.error("  ✗ HARD GATE: Missing artifact %s (agent: %s)", artifact_name, agent_name)
            continue
        # Content validation: size + required sections
        content = path.read_text(encoding="utf-8", errors="replace").lower()
        size = len(content)
        if size < min_bytes:
            shallow.append(f"{artifact_name} ({size}B < {min_bytes}B min)")
            log.warning("  ⚠ CONTENT CHECK: %s is too small (%d bytes, min %d)",
                        artifact_name, size, min_bytes)
        missing_sections = [s for s in sections if s.lower() not in content]
        if missing_sections:
            shallow.append(f"{artifact_name} missing sections: {missing_sections}")
            log.warning("  ⚠ CONTENT CHECK: %s missing required sections: %s",
                        artifact_name, missing_sections)

    if missing:
        log.critical(
            "STAGE 7.5 HARD GATE FAILED — %d missing test artifacts: %s",
            len(missing), ", ".join(missing),
        )
        if human_gate:
            gate_req = GateRequest(
                id=f"gate-stream-test-{uuid.uuid4().hex[:6]}",
                agent_name="orchestrator",
                stage="7.5",
                level=GateLevel.CRITICAL,
                title="STREAM TEST HARD GATE: BRAKUJĄCE WYNIKI",
                description=(
                    f"Stage 7.5 zakończony, ale {len(missing)} wymaganych artefaktów "
                    f"testowych nie istnieje:\n"
                    + "\n".join(f"  - {m}" for m in missing)
                    + "\n\nBez raportów latency i security review pipeline "
                    "NIE MOŻE przejść do Stage 8 (Security)."
                ),
                action_plan=[
                    {"step": "1. Sprawdź logi stream_tester i stream_security_verifier"},
                    {"step": "2. Re-run testów lub utwórz raporty ręcznie"},
                    {"step": "3. Po uzupełnieniu: wznów pipeline"},
                ],
                risk_assessment=(
                    "Brak wyników testów streaming i security review oznacza, że "
                    "Stage 8 (Security) nie będzie miał danych o podatnościach Pionu D."
                ),
                proposed_commands=[],
                metadata={"missing_artifacts": missing},
            )
            human_gate.request_approval(gate_req)
        save_signal(results_dir, "stage7_5_failed", {"missing_artifacts": missing})
        raise RuntimeError(f"Stage 7.5 HARD GATE: {len(missing)} missing artifacts")

    log.info("  ✅ Stage 7.5 HARD GATE: All stream test artifacts present")
    save_signal(results_dir, "stage7_5_done")


# ---------------------------------------------------------------------------
# STAGE 9: REPORT
# ---------------------------------------------------------------------------

async def stage_9_report(cfg: PipelineConfig, results_dir: Path):
    log.info("╔═══════════════════════════════════════╗")
    log.info("║  STAGE 9: REPORT (raport końcowy)      ║")
    log.info("╚═══════════════════════════════════════╝")

    (results_dir / "stage9_report").mkdir(parents=True, exist_ok=True)
    llm = make_llm_by_name("claude")
    agent = create_reporter(llm)

    task_msg = f"""Wygeneruj kompletny raport audytu.
Przeczytaj WSZYSTKIE wyniki z: {results_dir}/
Zapisz raport: {results_dir}/stage9_report/audit_report.md
Zapisz CHANGELOG: {results_dir}/stage9_report/changelog_fragment.md
Zapisz traceability: {results_dir}/stage9_report/traceability_update.json"""

    await run_agent_async(agent, cfg.workspace, task_msg, "Reporter")
    save_signal(results_dir, "stage9_done")


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

async def run_pipeline(cfg: PipelineConfig):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_dir = cfg.results_dir / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(cfg.log_level, results_dir / "pipeline.log")

    # Initialize agent manager (reads agents.yaml)
    mgr = init_agent_manager()
    enabled_count = mgr.get_stats()["enabled"]
    active_stages = mgr.get_active_stages()

    # Initialize Supervisor + Human Gate + Safe Runner
    init_supervisor(results_dir, cfg=cfg)

    sup_status = "AKTYWNY" if supervisor else "WYŁĄCZONY"
    log.info("╔══════════════════════════════════════════════════════════════════╗")
    log.info(f"║  SYLION MULTI-AGENT PIPELINE — {enabled_count}/34 AGENTÓW         ║")
    log.info(f"║  Supervisor: {sup_status:<14}  Human Gate: {'TAK' if human_gate else 'NIE':<6}       ║")
    log.info("╚══════════════════════════════════════════════════════════════════╝")
    log.info(f"Workspace:    {cfg.workspace}")
    log.info(f"Księga:       {cfg.ksiega_path or 'domyślne wymagania'}")
    log.info(f"Modele:       {', '.join(cfg.models)}")
    log.info(f"Konsensus:    {cfg.consensus_threshold}/{len(cfg.models)}")
    log.info(f"Dry-run:      {cfg.dry_run}")
    log.info(f"Weryfikacja:  {'TAK (SHA-256 anti-hallucination)' if halluc_guard else 'NIE'}")
    log.info(f"BookGuardian: {'TAK (SHA=' + book_guardian.baseline_sha[:16] + ')' if book_guardian else 'NIE'}")
    log.info(f"BudgetGuard:  {'TAK (cap=$' + f'{budget_guard.max_cost_usd_per_day:.2f}' + ')' if budget_guard else 'NIE'}")
    log.info(f"Anti-Hallu L2: {'TAK (BuildVerification)' if build_verifier else 'NIE'}")
    log.info(f"Anti-Hallu L3: {'TAK (ClaimProvenance)' if claim_prover else 'NIE'}")
    log.info(f"Anti-Hallu L4: {'TAK (SemanticDedup ' + semantic_deduper.backend.value + ')' if semantic_deduper else 'NIE'}")
    log.info(f"Anti-Hallu L5: {'TAK (FactChecker ' + fact_checker.model_id + ')' if fact_checker else 'NIE'}")
    log.info(f"Runtime Sig:  {'TAK (rooms=' + str(signaling_srv.max_rooms) + ')' if signaling_srv else 'NIE'}")
    log.info(f"Runtime Dev:  {'TAK (dry=' + str(device_harness.runner.dry_run) + ')' if device_harness else 'NIE'}")
    log.info(f"Runtime Met:  {'TAK (samples=' + str(metrics_collector.store.max_samples) + ')' if metrics_collector else 'NIE'}")
    log.info(f"Runtime ABR:  {'TAK (rung=' + str(abr_controller.get_stats().get('current_rung', '?')) + ')' if abr_controller else 'NIE'}")
    log.info(f"Runtime Inp:  {'TAK (InputProtocol)' if input_protocol else 'NIE'}")
    log.info(f"Runtime Aud:  {'TAK (AudioPipeline)' if audio_pipeline else 'NIE'}")
    log.info(f"Runtime Sec:  {'TAK (StreamSecurity prod=' + str(stream_security._production_mode) + ')' if stream_security else 'NIE'}")
    log.info(f"Runtime Bench:{'TAK (' + str(len(benchmark_harness._benchmarks)) + ' benchmarks)' if benchmark_harness else 'NIE'}")
    log.info(f"StreamMonitor:{'TAK (real-time metrics)' if stream_monitor_inst else 'NIE'}")
    log.info(f"E2E Session:  {'TAK (8-module E2E controller)' if e2e_controller else 'NIE'}")

    # --- Dashboard Server: start embedded web UI ---
    global dashboard_srv
    try:
        if os.getenv("SYLION_EXTERNAL_DASHBOARD") == "1":
            dashboard_srv = None
            log.info(f"Dashboard:    external app managed by launcher on port {cfg.dashboard_port}")
        else:
            dashboard_srv = DashboardServer(port=cfg.dashboard_port)
            dashboard_srv.update_runtime_refs(
                stream_monitor=stream_monitor_inst,
                stream_security=stream_security,
                device_harness=device_harness,
                metrics_collector=metrics_collector,
                abr_controller=abr_controller,
                agent_manager=mgr,
            )
            dashboard_srv.start()
            log.info(f"Dashboard:    http://127.0.0.1:{dashboard_srv.port}")
    except Exception as e:
        log.warning(f"Dashboard:    NIE (failed to start: {e})")
        dashboard_srv = None

    log.info(f"Wyniki:       {results_dir}")
    log.info(f"Aktywne etapy: {[f'{s}({len(mgr.get_stage_agents(s))})' for s in active_stages]}")

    t0 = time.monotonic()
    total_cost = 0.0

    # --- Supervisor: Human Gate before entire pipeline ---
    if human_gate:
        # Consequence descriptions for pipeline start
        consequences = {}
        if consequence_desc:
            consequences = consequence_desc.describe_consequences(
                "pipeline_start",
                {"agents": [a.name for a in mgr.get_enabled_agents()],
                 "agents_count": enabled_count,
                 "stages": list(active_stages),
                 "dry_run": cfg.dry_run, "models": cfg.models},
            )

        pipeline_gate_req = GateRequest(
            id=f"gate-pipeline-start-{uuid.uuid4().hex[:6]}",
            agent_name="orchestrator",
            stage="pipeline_start",
            level=GateLevel.CRITICAL,
            title="Uruchomienie pełnego SYLION pipeline",
            description=(
                f"Uruchomienie pipeline z {enabled_count} agentami, "
                f"{len(active_stages)} etapami.\n"
                f"Modele: {', '.join(cfg.models)}\n"
                f"Dry-run: {cfg.dry_run}\n"
                f"Workspace: {cfg.workspace}"
            ),
            action_plan=[{"description": f"Run full pipeline ({enabled_count} agents)", "status": "pending"}],
            risk_assessment="Pełne uruchomienie pipeline — wymaga zatwierdzenia",
            proposed_commands=[],
            metadata={"consequences": consequences} if consequences else {},
        )

        if gate_ux and consequences:
            gate_ux.display_decision_menu(
                consequences,
                gate_level="critical",
                header={"agent": "orchestrator", "stage": "pipeline_start",
                        "title": "Uruchomienie pełnego SYLION pipeline"},
            )

        pipeline_approval = human_gate.request_approval(pipeline_gate_req)
        if pipeline_approval.decision != GateDecision.APPROVED:
            reason = pipeline_approval.human_notes or "odrzucono"
            log.error(f"Human Gate: PIPELINE ODRZUCONY — {reason}")
            save_signal(results_dir, "pipeline_rejected", {
                "reason": reason,
            })
            return
        log.info("  ✅ Human Gate: Pipeline ZATWIERDZONY")

    # --- Supervisor: generate initial checklist ---
    if supervisor:
        supervisor.generate_checklist(active_stages, mgr)

    try:
        stages = [
            (1,   "PREPARE",      stage_1_prepare),
            (2,   "AUDIT",        stage_2_audit),
            (3,   "CROSS-VERIFY", stage_3_cross_verify),
            (4,   "MERGE",        stage_4_merge),
            (5,   "PATCH",        stage_5_patch),
            (5.5, "RUNTIME",      stage_5_5_runtime),
            (5.6, "FACT-CHECK",   stage_5_6_fact_check),
            (6,   "DEPLOY",       stage_6_deploy),
            (6.5, "STREAMING",    stage_6_5_streaming),
            (7,   "TEST",         stage_7_test),
            (7.5, "STREAM-TEST",  stage_7_5_stream_test),
            (8,   "SECURITY",     stage_8_security),
            (8.5, "SDR",          stage_8_5_sdr),
            (9,   "REPORT",       stage_9_report),
        ]

        for stage_num, stage_name, stage_fn in stages:
            if not is_stage_enabled(stage_num):
                log.info(f"  ⏭ Stage {stage_num} ({stage_name}) pominięty — agenty wyłączone")
                if supervisor:
                    supervisor.on_stage_skipped(stage_num, stage_name)
                if dashboard_srv:
                    dashboard_srv.set_stage_skipped(stage_num, stage_name)
                continue

            # --- BookGuardian: check Księga integrity BEFORE each stage ---
            if book_guardian:
                if not book_guardian.check():
                    log.critical(
                        "KSIAźGA DRIFT WYKRYTY przed Stage %s (%s) — PIPELINE ZATRZYMANY",
                        stage_num, stage_name,
                    )
                    save_signal(results_dir, "pipeline_halted_ksiega_drift", {
                        "stage": stage_num, "stage_name": stage_name,
                        "drift_report": book_guardian.export_report(),
                    })
                    return
                log.debug("BookGuardian: Księga OK before Stage %s", stage_num)

            # --- BudgetGuard: check if budget already exceeded ---
            if budget_guard and budget_guard.is_exceeded:
                log.critical(
                    "BudgetGuard: DZIENNY BUDŻET JUŻ PRZEKROCZONY ($%.4f / $%.2f) "
                    "— pomijam Stage %s (%s)",
                    budget_guard.daily_total, budget_guard.max_cost_usd_per_day,
                    stage_num, stage_name,
                )
                save_signal(results_dir, "pipeline_halted_budget", {
                    "stage": stage_num, "stage_name": stage_name,
                    "budget_report": budget_guard.export_report(),
                })
                return

            # Supervisor: notify stage start
            if supervisor:
                supervisor.on_stage_start(stage_num, stage_name)
            if dashboard_srv:
                dashboard_srv.set_pipeline_status("running")
                dashboard_srv.set_stage_running(stage_num, stage_name)

            await stage_fn(cfg, results_dir)

            # Supervisor: notify stage end + update checklist
            if supervisor:
                supervisor.on_stage_complete(stage_num, stage_name)
            if dashboard_srv:
                dashboard_srv.set_stage_completed(stage_num, stage_name)
                # After each stage: generate summary + checklist update
                remaining = supervisor.get_remaining_tasks()
                if remaining:
                    log.info(f"  📝 Supervisor checklist: {len(remaining)} zadań pozostało")

    except Exception as e:
        log.error(f"Pipeline przerwany: {e}", exc_info=True)
        save_signal(results_dir, "pipeline_error", {"error": str(e)})
        if dashboard_srv:
            dashboard_srv.set_pipeline_status("error")

        # Supervisor: escalate pipeline failure
        if supervisor:
            supervisor.on_pipeline_error(str(e))
            if human_gate:
                error_gate_req = GateRequest(
                    id=f"gate-pipeline-error-{uuid.uuid4().hex[:6]}",
                    agent_name="orchestrator",
                    stage="pipeline_error",
                    level=GateLevel.CRITICAL,
                    title="PIPELINE PRZERWANY",
                    description=f"Pipeline przerwany z błędem: {e}",
                    action_plan=[{"description": "Eskalacja błędu pipeline", "status": "pending"}],
                    risk_assessment="Pipeline krytycznie zawiodł — wymaga interwencji",
                    proposed_commands=[],
                    metadata={"error": str(e), "stage": "unknown"},
                )
                if gate_ux and consequence_desc:
                    err_consequences = consequence_desc.describe_consequences(
                        "pipeline_error",
                        {"error": str(e)},
                    )
                    if err_consequences:
                        gate_ux.display_decision_menu(
                            err_consequences,
                            gate_level="critical",
                            header={"agent": "orchestrator", "stage": "pipeline_error",
                                    "title": "PIPELINE PRZERWANY"},
                        )
                human_gate.request_approval(error_gate_req)
        raise

    elapsed = time.monotonic() - t0
    stats = mgr.get_stats() if mgr else {}

    # --- Supervisor: final summary + checklist ---
    if supervisor:
        supervisor.on_pipeline_complete(
            elapsed=elapsed,
            stats=stats,
            results_dir=results_dir,
        )
        # Save final checklist
        supervisor.save_checklist()
        # Human Gate: request final approval of results
        if human_gate:
            final_gate_req = GateRequest(
                id=f"gate-pipeline-results-{uuid.uuid4().hex[:6]}",
                agent_name="orchestrator",
                stage="pipeline_results",
                level=GateLevel.REVIEW,
                title="Pipeline zakończony — sprawdź wyniki",
                description=(
                    f"Pipeline ukończony w {elapsed:.0f}s.\n"
                    f"Ukończonych: {stats.get('completed', 0)}, "
                    f"Błędów: {stats.get('failed', 0)}, "
                    f"Koszt: ${stats.get('total_cost', 0):.4f}"
                ),
                action_plan=[{"description": "Przejrzyj wyniki końcowe pipeline", "status": "completed"}],
                risk_assessment="Wyniki końcowe — tylko przegląd",
                proposed_commands=[],
                metadata={
                    "report": f"{results_dir}/stage9_report/audit_report.md",
                    "checklist": str(supervisor.checklist_path),
                },
            )
            if gate_ux and consequence_desc:
                final_consequences = consequence_desc.describe_consequences(
                    "pipeline_results",
                    {"elapsed": elapsed, "completed": stats.get("completed", 0),
                     "failed": stats.get("failed", 0),
                     "cost": stats.get("total_cost", 0)},
                )
                if final_consequences:
                    gate_ux.display_decision_menu(
                        final_consequences,
                        gate_level="review",
                        header={"agent": "orchestrator", "stage": "pipeline_results",
                                "title": "Pipeline zakończony"},
                    )
            human_gate.request_approval(final_gate_req)

    log.info("╔══════════════════════════════════════════════════════════════════╗")
    log.info("║     PIPELINE ZAKOŃCZONY                                          ║")
    log.info("╚══════════════════════════════════════════════════════════════════╝")
    log.info(f"Czas:         {elapsed:.0f}s ({elapsed / 60:.1f} min)")
    log.info(f"Agenty:       {stats.get('completed', 0)} ukończonych, {stats.get('failed', 0)} błędów")
    log.info(f"Koszt:        ${stats.get('total_cost', 0):.4f}")
    if budget_guard:
        log.info(f"Budżet:       ${budget_guard.daily_total:.4f} / ${budget_guard.max_cost_usd_per_day:.2f} "
                 f"({budget_guard.utilization_pct:.1f}%) {'PRZEKROCZONY' if budget_guard.is_exceeded else 'OK'}")
    if book_guardian:
        log.info(f"Księga:       {'OK (✓ SHA integralny)' if book_guardian.is_healthy else 'DRIFT WYKRYTY!'} "
                 f"(sprawdzeń: {book_guardian.check_count}, dryfty: {book_guardian.drift_count})")
    log.info(f"Supervisor:   {sup_status}")
    log.info(f"Raport:       {results_dir}/stage9_report/audit_report.md")
    if supervisor:
        log.info(f"Checklist:    {supervisor.checklist_path}")
        log.info(f"Human Gate:   {results_dir}/human_gate.jsonl")
    save_signal(results_dir, "pipeline_done", {"elapsed_seconds": elapsed})

    # Stop dashboard server (graceful)
    if dashboard_srv:
        dashboard_srv.set_pipeline_status("completed")
        log.info(f"Dashboard:    http://localhost:{dashboard_srv.port} (still running for review)")
        # Note: dashboard keeps running so user can review results.  
        # It will stop when the process exits (daemon thread).


# ---------------------------------------------------------------------------
# Patch A: v5.9.1 N-fix — run_codebase_audit hook for dashboard
# ---------------------------------------------------------------------------

def run_codebase_audit(
    extracted_path: str, *, ksiega_path: str | None = None,
    dry_run: bool = False, models: list[str] | None = None,
    results_dir: str | None = None, humangate_mode: str = "db",
) -> str:
    """Uruchom SYLION pipeline na uploadowanej bazie kodu (hook dla dashboard).

    Działa w wątku BackgroundTasks; asyncio.run() tworzy nową pętlę eventów.
    Returns: run_id. Raises: ValueError gdy katalog nie istnieje lub pusty.
    """
    import asyncio, uuid, os
    from pathlib import Path as _P
    workspace = _P(extracted_path)
    if not workspace.exists():
        raise ValueError(f"run_codebase_audit: nie istnieje: {extracted_path}")
    if not any(workspace.iterdir()):
        raise ValueError(f"run_codebase_audit: pusty: {extracted_path}")
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    _res = _P(results_dir) / run_id if results_dir else _P("./results") / run_id
    _res.mkdir(parents=True, exist_ok=True)
    # FIX PIPELINE-009: use assignment, not setdefault. setdefault leaks state
    # across runs in the same process (FastAPI BackgroundTasks share env) —
    # first run pins the mode, subsequent runs silently ignore humangate_mode
    # arg, causing TTY fallback → instant 'PIPELINE ODRZUCONY — Keyboard
    # interrupt' while API still reports status=completed (false success).
    os.environ["SYLION_HUMANGATE_MODE"] = humangate_mode
    os.environ["SYLION_RUN_ID"] = run_id
    cfg = PipelineConfig(
        workspace=workspace,
        ksiega_path=_P(ksiega_path) if ksiega_path else None,
        dry_run=dry_run,
        models=models or ["claude", "gpt", "gemini", "deepseek"],
        results_dir=_res, log_level="INFO",
    )
    log.info("run_codebase_audit START run_id=%s", run_id)
    try:
        asyncio.run(run_pipeline(cfg))
    except Exception:
        log.exception("run_codebase_audit FAILED run_id=%s", run_id)
        raise
    log.info("run_codebase_audit DONE run_id=%s", run_id)
    return run_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SYLION 34-Agent Supervised Audit Pipeline",
        epilog="Supervisor działa automatycznie gdy jest włączony w agents.yaml. "
               "Użyj --no-supervisor żeby wyłączyć nadzorca.",
    )
    parser.add_argument("--workspace", "-w", type=Path, required=True)
    parser.add_argument("--ksiega", "-k", type=Path, default=None)
    parser.add_argument("--packages", "-p", type=str, default="")
    parser.add_argument("--models", "-m", type=str, default="claude,gpt,gemini,deepseek")
    parser.add_argument("--consensus", "-c", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--results-dir", "-r", type=Path, default=Path("./results"))
    parser.add_argument("--log-level", "-l", type=str, default="INFO")
    # Skip flags — defined for forward compatibility but not yet wired into stage loop
    parser.add_argument("--skip-deploy", action="store_true", help="[NOT IMPLEMENTED] Skip device deployment")
    parser.add_argument("--skip-security", action="store_true", help="[NOT IMPLEMENTED] Skip Red/Blue Team")
    parser.add_argument("--skip-sdr", action="store_true", help="[NOT IMPLEMENTED] Skip SDR tests")
    parser.add_argument("--start-from", type=int, default=1, help="[NOT IMPLEMENTED] Start from stage N")
    parser.add_argument("--profile", type=str, default=None,
                        help="Profil z agents.yaml (quick_audit, full_no_sdr, security_only, sdr_only, minimal, supervised, unsupervised)")
    # Supervisor options
    parser.add_argument("--no-supervisor", action="store_true",
                        help="Wyłącz Supervisora (Human Gate + Safe Runner) na tę sesję")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Auto-approve bezpiecznych akcji w Human Gate (szybciej, mniej bezpiecznie)")
    parser.add_argument("--dashboard-port", type=int, default=8421,
                        help="Port for dashboard integration (default: 8421)")

    args = parser.parse_args()

    # Warn about unimplemented skip flags
    for flag_name, attr_name in [("--skip-deploy", "skip_deploy"), ("--skip-security", "skip_security"),
                                  ("--skip-sdr", "skip_sdr")]:
        if getattr(args, attr_name, False):
            print(f"  \u26a0\ufe0f  {flag_name} is defined but NOT YET IMPLEMENTED \u2014 ignored")
    if getattr(args, "start_from", 1) != 1:
        print(f"  \u26a0\ufe0f  --start-from is defined but NOT YET IMPLEMENTED \u2014 ignored")

    # Apply profile if specified (modifies agents.yaml before pipeline starts)
    if args.profile:
        try:
            mgr = AgentManager()
            if mgr.apply_profile(args.profile):
                print(f"  ✓ Profil '{args.profile}' zastosowany")
                from agent_manager import print_status
                print_status(mgr)
            else:
                print(f"  ✗ Profil '{args.profile}' nie istnieje")
                print(f"  Dostępne: {', '.join(mgr.profiles.keys())}")
                sys.exit(1)
        except Exception as e:
            print(f"  ✗ Błąd ładowania profilu: {e}")
            sys.exit(1)

    # Handle --no-supervisor: in-memory only, do NOT save to agents.yaml
    if args.no_supervisor:
        try:
            mgr = AgentManager()
            if "supervisor" in mgr.agents:
                mgr.agents["supervisor"].enabled = False
                # mgr.save()  # REMOVED: session-only change, do not persist to disk
                print("  ⚠️  Supervisor WYŁĄCZONY na tę sesję (--no-supervisor, nie zapisano do agents.yaml)")
        except Exception as e:
            print(f"  ⚠️  Nie udało się wyłączyć supervisora: {e}")

    # Handle --auto-approve: in-memory only, do NOT save to agents.yaml
    if args.auto_approve and not args.no_supervisor:
        try:
            mgr = AgentManager()
            sup = mgr.agents.get("supervisor")
            if sup and sup.params.get("human_gate"):
                sup.params["human_gate"]["auto_approve_safe"] = True
                # mgr.save()  # REMOVED: session-only change, do not persist to disk
                print("  ⚠️  Human Gate: auto-approve dla bezpiecznych akcji (--auto-approve, nie zapisano do agents.yaml)")
        except Exception as e:
            print(f"  ⚠️  Nie udało się ustawić auto-approve: {e}")

    # --- Resolve workspace and uploaded inputs ---
    workspace_dir = args.workspace.resolve()
    ksiega_path = args.ksiega.resolve() if args.ksiega else None

    # If no CLI ksiega/workspace override, check dashboard uploads
    uploads_dir = workspace_dir / "workspace_uploads"
    if not uploads_dir.exists():
        # Also check relative to pipeline dir
        uploads_dir = Path(__file__).parent / "workspace_uploads"

    if uploads_dir.exists():
        # Auto-detect Księga from upload slot
        ksiega_slot = uploads_dir / "ksiega"
        if not ksiega_path and ksiega_slot.exists():
            for f in ksiega_slot.iterdir():
                if f.suffix.lower() in (".docx", ".pdf", ".md", ".txt"):
                    ksiega_path = f
                    print(f"  \u2713 Ksi\u0119ga auto-detected from upload: {f.name}")
                    break

        # Auto-detect codebase workspace from extracted ZIP
        extracted_dir = uploads_dir / "codebase_extracted"
        if extracted_dir.exists() and any(extracted_dir.iterdir()):
            # Use extracted codebase as workspace if not explicitly set
            workspace_dir = extracted_dir
            print(f"  \u2713 Workspace auto-set to uploaded codebase: {extracted_dir}")

        # Detect Phantom spec
        phantom_slot = uploads_dir / "phantom"
        phantom_path = None
        if phantom_slot.exists():
            for f in phantom_slot.iterdir():
                if f.suffix.lower() in (".docx", ".pdf", ".md", ".txt"):
                    phantom_path = f
                    print(f"  \u2713 Phantom spec auto-detected from upload: {f.name}")
                    break
        # Store phantom_path in environment for agents to access
        if phantom_path:
            os.environ["SYLION_PHANTOM_PATH"] = str(phantom_path)

    cfg = PipelineConfig(
        workspace=workspace_dir,
        ksiega_path=ksiega_path,
        packages=[p.strip() for p in args.packages.split(",") if p.strip()],
        models=[m.strip() for m in args.models.split(",")],
        consensus_threshold=args.consensus,
        dry_run=args.dry_run,
        results_dir=args.results_dir,
        log_level=args.log_level,
    )

    asyncio.run(run_pipeline(cfg))


if __name__ == "__main__":
    main()
