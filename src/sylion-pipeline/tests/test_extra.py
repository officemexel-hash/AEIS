"""Tests for SYLION AEIS efficiency, quality, security, aeis, skills, rebuild, surface modules."""
import pytest


# --- Efficiency ---
def test_code_bloat(bus):
    from sylion.efficiency.code_bloat import CodeBloatTracker
    cbt = CodeBloatTracker(event_bus=bus)
    cbt.measure("test.mod", loc=500, complexity=12, deps=3)
    assert cbt.is_within_budget("test.mod")


def test_cost_envelope(bus):
    from sylion.efficiency.cost_envelope import CostEnvelopeTracker
    cet = CostEnvelopeTracker(event_bus=bus)
    cet.set_budget("openai", daily_limit=10.0)
    cet.record("openai", "model1", 1000, 500, 0.05)
    assert cet.is_within_budget("openai")


def test_runtime_perf(bus):
    from sylion.efficiency.runtime_perf import RuntimePerfTracker
    rp = RuntimePerfTracker(event_bus=bus)
    rp.record("api_call", latency_ms=120)
    stats = rp.get_stats("api_call")
    assert stats is not None


def test_memory_footprint(bus):
    from sylion.efficiency.memory_footprint import MemoryFootprintTracker
    mf = MemoryFootprintTracker(event_bus=bus)
    mf.set_budget("module_a", max_rss=512)
    mf.snapshot("module_a", rss=256, heap=128)
    result = mf.check_budget("module_a")
    assert result["status"] == "within"


# --- Quality ---
def test_golden_set(bus):
    from sylion.quality.golden_set_registry import GoldenSetRegistry
    gsr = GoldenSetRegistry(event_bus=bus)
    gsr.register("gs1", "Test baseline", module_id="test.mod", input="in", expected_output="out")
    r = gsr.run_test("gs1", actual_output="out")
    assert r is not None


def test_regression_detector(bus):
    from sylion.quality.regression_detector import RegressionDetector
    rd = RegressionDetector(event_bus=bus)
    rd.set_baseline("test.mod", "gs1", "r1", pass_rate=0.95)
    result = rd.check_regression("test.mod", "gs1", current_pass_rate=0.95)
    assert result is not None


# --- Security ---
def test_auth_provider(bus):
    from sylion.security.auth_provider import AuthProvider
    ap = AuthProvider(event_bus=bus)
    ap.create_user("u1", "admin", "hash123", role="admin")
    u = ap.authenticate("admin", "hash123")
    assert u is not None


def test_session_broker(bus):
    from sylion.security.session_broker import SessionBroker
    sb = SessionBroker(event_bus=bus)
    sb.create("s1", "u1", "token1", timeout=3600)
    assert sb.validate("s1") is not None


def test_audit_sink(bus):
    from sylion.security.audit_sink import AuditSink
    a_s = AuditSink(event_bus=bus)
    a_s.log("login", actor="admin", action="login", result="success")


def test_execution_guard(bus):
    from sylion.security.execution_guard import ExecutionGuard
    eg = ExecutionGuard(event_bus=bus)
    eg.add_rule("r1", "Allow API", action="allow", resource_pattern="/api/*")
    c = eg.check("/api/modules", "GET")
    assert c is not None


def test_secret_provider(bus):
    from sylion.security.secret_provider import SecretProvider
    sp = SecretProvider(event_bus=bus)
    sp.store("api_key", "API Key", "sk-test-123")
    val = sp.retrieve("api_key")
    assert val == "sk-test-123"


def test_policy_engine(bus):
    from sylion.security.policy_engine import PolicyEngine
    pe = PolicyEngine(event_bus=bus)
    pe.create_policy("allow_api", "Allow API", policy_type="access")
    r = pe.evaluate("allow_api", "/api/modules")
    assert r is not None


def test_bootstrap_init(bus):
    from sylion.security.bootstrap_init import BootstrapInit
    bi = BootstrapInit(event_bus=bus)
    profile = bi.bootstrap()
    assert profile is not None


def test_phantom_wrapper(bus):
    from sylion.security.phantom_wrapper import PhantomWrapper
    pw = PhantomWrapper(event_bus=bus)
    r = pw.check("test input", "test output")
    assert r is not None


# --- AEIS ---
def test_self_observation(bus):
    from sylion.aeis.self_observation import SelfObservation
    so = SelfObservation(event_bus=bus)
    so.record("cpu", 45.0)
    d = so.get_dashboard()
    assert d is not None


def test_improvement_queue(bus):
    from sylion.aeis.improvement_queue import ImprovementQueue
    iq = ImprovementQueue(event_bus=bus)
    iq.submit("Optimize X", priority=5)
    n = iq.get_next()
    assert n is not None


def test_self_limitation(bus):
    from sylion.aeis.self_limitation import SelfLimitationEngine
    sl = SelfLimitationEngine(event_bus=bus)
    sl.register_policy("slp-api", "api", max_calls=10000, window_seconds=3600)
    # Record a few actions below the limit
    for _ in range(5):
        sl.record_action("api", "client1", action="call", result="ok")
    result = sl.check_rate("api", "client1")
    assert result["allowed"] is True


def test_self_preservation(bus):
    from sylion.aeis.self_preservation import SelfPreservationEngine
    spr = SelfPreservationEngine(event_bus=bus)
    spr.check_health("core", score=0.95)
    assert not spr.should_shutdown()


def test_self_explanation(bus):
    from sylion.aeis.self_explanation import SelfExplanationEngine
    se = SelfExplanationEngine(event_bus=bus)
    r = se.generate("dec1", "Why this decision?", explanation="Test explanation")
    assert r is not None


# --- Skills ---
def test_skills_registry(bus):
    from sylion.skills.registry import SkillsRegistry
    sr = SkillsRegistry(event_bus=bus)
    sr.register("s-test", "Test Skill", domain="test")
    sr.publish("s-test")
    skill = sr.get("s-test")
    assert skill["lifecycle"] == "PUBLISHED"


def test_skills_executor(bus):
    from sylion.skills.executor import SkillsExecutor
    se = SkillsExecutor(event_bus=bus)
    r = se.execute("test_skill", input_data={"input": "data"})
    assert r is not None


def test_demand_signal(bus):
    from sylion.skills.demand_signal import DemandSignalAnalyzer
    ds = DemandSignalAnalyzer(event_bus=bus)
    ds.record(signal_type="request", source="agent_1", skill_id="s-test")
    signals = ds.get_signals("s-test")
    assert len(signals) >= 1


# --- Rebuild ---
def test_rebuild_orchestrator(bus):
    from sylion.rebuild.orchestrator import RebuildOrchestrator
    ro = RebuildOrchestrator(event_bus=bus)
    plan = ro.create_plan("test rebuild", modules=["test.mod"])
    assert plan is not None


def test_lpw_manager(bus):
    from sylion.rebuild.lpw_manager import LPWManager
    lpw = LPWManager(event_bus=bus)
    lpw.record("test.mod", version="1.0.0")
    last = lpw.get_lpw("test.mod")
    assert last is not None


def test_cutover_controller(bus):
    from sylion.rebuild.cutover_controller import CutoverController
    cc = CutoverController(event_bus=bus)
    plan = cc.create_plan("test.mod")
    assert plan is not None


def test_cft_runner(bus):
    from sylion.rebuild.cft_runner import CFTRunner
    cft = CFTRunner(event_bus=bus)
    suite = cft.create_suite("Test Suite", module_id="test.mod")
    r = cft.run_test(suite["suite_id"], golden_hash="abc123")
    assert r["passed"]


# --- Surface ---
def test_console_api(bus):
    from sylion.surface.console_api import ConsoleAPI
    api = ConsoleAPI(event_bus=bus)
    ep = api.register("/api/test", "GET", description="Test endpoint")
    assert "endpoint_id" in ep
    api.record_request(ep["endpoint_id"], status_code=200)
    stats = api.get_stats()
    assert stats["total_requests"] >= 1


def test_console_ui(bus):
    from sylion.surface.console_ui import ConsoleUI
    ui = ConsoleUI(event_bus=bus)
    c = ui.register_component("TestPanel", panel="main")
    assert "component_id" in c
    layouts = ui.list_layouts()
    assert isinstance(layouts, list)


def test_ws_gateway(bus):
    from sylion.surface.ws_gateway import WSGateway
    ws = WSGateway(event_bus=bus)
    conn = ws.connect(user_id="user1", channels=["channel1", "channel2"])
    assert "conn_id" in conn
