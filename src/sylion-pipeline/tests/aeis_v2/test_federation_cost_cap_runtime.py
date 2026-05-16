"""W17 cost_cap runtime control surface — unit + REST coverage.

Background
----------
Bg agent ``af45`` (commit 2ddd0407) wired the W19 cost_cap_per_decision
policy into ``federation.route()`` with three modes (warn / deny / off)
sourced from ``SYLION_COST_CAP_MODE``. To flip modes the operator had to
restart the process. The W17 cron task closes that gap with:

  - ``set_runtime_cost_cap_mode`` / ``get_runtime_cost_cap_mode`` —
    in-memory override (beats env, survives until process restart).
  - ``reset_cost_cap_warnings_total`` — atomic clear+return for the
    warn-mode counter so the operator can acknowledge a pressure spike.
  - ``_evaluate_cost_cap`` refactored to a pure-function with primitive
    inputs so the simulator REST endpoint can probe arbitrary prices
    without registering a node.

REST surface (``/api/v1/federation/cost-cap/...``):

  - ``POST /cost-cap/mode``      — set or clear the runtime override.
  - ``GET  /cost-cap/status``    — diagnostic snapshot (runtime/env/
                                    effective + warnings + limits).
  - ``POST /cost-cap/simulate``  — pure-function dry-run with arbitrary
                                    cost-per-1k + token estimate.
  - ``POST /cost-cap/warnings/reset`` — atomic counter reset.

These tests cover both the helpers and the REST endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sylion.aeis_v2.deployment import federation as federation_mod
from sylion.aeis_v2.deployment.federation import (
    COST_CAP_PER_DECISION_USD,
    CostCapEvaluation,
    _evaluate_cost_cap,
    _resolved_cost_cap_mode,
    get_runtime_cost_cap_mode,
    reset_cost_cap_warnings_total,
    set_runtime_cost_cap_mode,
)


# --------------------------------------------------------------------------
# Fixtures: clean module state on entry + exit so tests do not bleed.
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_cost_cap_state(monkeypatch):
    """Reset runtime override + warn counter + env on every test.

    ``monkeypatch.setenv(..., raising=False)`` keeps env mutations safe
    even when the variable is not pre-defined; the autouse setter +
    teardown means a stale runtime override from a crashed test can
    never poison a sibling.
    """
    monkeypatch.delenv("SYLION_COST_CAP_MODE", raising=False)
    set_runtime_cost_cap_mode(None)
    federation_mod.cost_cap_warnings_total = 0
    yield
    set_runtime_cost_cap_mode(None)
    federation_mod.cost_cap_warnings_total = 0


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient hitting the global app (RBAC disabled by conftest)."""
    from sylion.api.app import app
    return TestClient(app)


# --------------------------------------------------------------------------
# 1) Runtime override beats env-var resolution.
# --------------------------------------------------------------------------


def test_set_runtime_mode_overrides_env(monkeypatch) -> None:
    """When the runtime override is set, ``_resolved_cost_cap_mode`` must
    return that value regardless of what ``SYLION_COST_CAP_MODE`` says."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "warn")
    assert _resolved_cost_cap_mode() == "warn"

    set_runtime_cost_cap_mode("deny")
    assert _resolved_cost_cap_mode() == "deny", (
        "runtime override must beat env"
    )

    set_runtime_cost_cap_mode("off")
    assert _resolved_cost_cap_mode() == "off"


# --------------------------------------------------------------------------
# 2) Clearing the runtime override (mode=None) falls back to env.
# --------------------------------------------------------------------------


def test_runtime_mode_none_falls_back_to_env(monkeypatch) -> None:
    """``set_runtime_cost_cap_mode(None)`` clears the override; resolution
    then proceeds env -> default exactly like before the override."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "deny")
    set_runtime_cost_cap_mode("warn")
    assert _resolved_cost_cap_mode() == "warn"

    set_runtime_cost_cap_mode(None)
    assert _resolved_cost_cap_mode() == "deny", (
        "after clearing runtime, env value must take over"
    )

    monkeypatch.delenv("SYLION_COST_CAP_MODE", raising=False)
    assert _resolved_cost_cap_mode() == "warn", (
        "with no runtime + no env, default ('warn') wins"
    )


# --------------------------------------------------------------------------
# 3) Override persists across multiple resolution calls within the process.
# --------------------------------------------------------------------------


def test_runtime_mode_persists_across_calls_within_process() -> None:
    """A single ``set_runtime_cost_cap_mode`` call survives until cleared.

    This is the operator's primary use case: flip to ``deny`` once and
    have every subsequent decision (across many threads / requests)
    observe the new mode without further intervention.
    """
    set_runtime_cost_cap_mode("deny")
    for _ in range(50):
        assert _resolved_cost_cap_mode() == "deny"

    # Counters in the diagnostic getter must remain consistent too.
    snapshot = get_runtime_cost_cap_mode()
    assert snapshot["runtime"] == "deny"
    assert snapshot["effective"] == "deny"


# --------------------------------------------------------------------------
# 4) Diagnostic getter exposes runtime / env / effective triple.
# --------------------------------------------------------------------------


def test_get_status_returns_runtime_env_effective(monkeypatch) -> None:
    """``get_runtime_cost_cap_mode`` must report all three slots so the
    operator can spot the source of the active mode at a glance."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "off")
    set_runtime_cost_cap_mode("deny")

    status = get_runtime_cost_cap_mode()
    assert status["runtime"] == "deny"
    assert status["env"] == "off"
    assert status["effective"] == "deny", (
        "effective must reflect the runtime override, not env"
    )

    set_runtime_cost_cap_mode(None)
    cleared = get_runtime_cost_cap_mode()
    assert cleared["runtime"] is None
    assert cleared["env"] == "off"
    assert cleared["effective"] == "off", (
        "after clearing runtime, effective falls through to env"
    )


# --------------------------------------------------------------------------
# 5) ``GET /cost-cap/status`` includes the warnings counter.
# --------------------------------------------------------------------------


def test_get_status_includes_warnings_total(client: TestClient) -> None:
    """The status REST payload must surface ``warnings_total`` so the UI
    can render the cost-cap pressure tile without polling extra
    endpoints."""
    federation_mod.cost_cap_warnings_total = 7

    r = client.get("/api/v1/federation/cost-cap/status")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["warnings_total"] == 7
    assert "mode" in body
    assert body["limit_usd"] == COST_CAP_PER_DECISION_USD
    assert body["estimated_tokens"] == federation_mod.COST_CAP_ESTIMATED_TOKENS
    # ``mode`` must be the diagnostic triple, not a flat string.
    assert isinstance(body["mode"], dict)
    assert {"runtime", "env", "effective"}.issubset(body["mode"].keys())


# --------------------------------------------------------------------------
# 6) Simulator returns ``allow`` when the estimated cost is under the cap.
# --------------------------------------------------------------------------


def test_simulate_cost_cap_under_limit_returns_allow(
    client: TestClient,
) -> None:
    """A 0.001 USD/1k * 1000 tokens decision is 0.001 USD — well under
    the 0.50 USD cap — so all three modes must report ``allow``."""
    for mode in ("warn", "deny", "off"):
        r = client.post(
            "/api/v1/federation/cost-cap/simulate",
            json={
                "cost_per_1k_usd": 0.001,
                "estimated_tokens": 1000,
                "mode": mode,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["exceeded"] is False, f"mode={mode}: must not exceed"
        assert body["decision"] == "allow", (
            f"mode={mode}: under-limit decision must be allow; got "
            f"{body['decision']!r}"
        )
        assert body["estimated_usd"] == pytest.approx(0.001, rel=1e-9)
        assert body["limit_usd"] == COST_CAP_PER_DECISION_USD
        assert body["mode"] == mode


# --------------------------------------------------------------------------
# 7) Simulator with ``mode=warn`` over the cap returns ``warn``.
# --------------------------------------------------------------------------


def test_simulate_cost_cap_over_limit_warn_returns_warn(
    client: TestClient,
) -> None:
    """0.60 USD/1k * 1000 tokens = 0.60 USD > 0.50 USD cap. Warn mode
    must report ``decision="warn"`` and ``exceeded=True``."""
    r = client.post(
        "/api/v1/federation/cost-cap/simulate",
        json={
            "cost_per_1k_usd": 0.60,
            "estimated_tokens": 1000,
            "mode": "warn",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["exceeded"] is True
    assert body["decision"] == "warn"
    assert body["estimated_usd"] == pytest.approx(0.60, rel=1e-9)
    # The simulator MUST NOT mutate the warn-counter — pure function.
    assert federation_mod.cost_cap_warnings_total == 0, (
        "simulator must be side-effect free"
    )


# --------------------------------------------------------------------------
# 8) Simulator with ``mode=deny`` over the cap returns ``deny``.
# --------------------------------------------------------------------------


def test_simulate_cost_cap_over_limit_deny_returns_deny(
    client: TestClient,
) -> None:
    """Same expensive decision under ``deny`` mode must report
    ``decision="deny"`` so the operator can pre-validate before flipping
    the runtime knob."""
    r = client.post(
        "/api/v1/federation/cost-cap/simulate",
        json={
            "cost_per_1k_usd": 0.60,
            "estimated_tokens": 1000,
            "mode": "deny",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["exceeded"] is True
    assert body["decision"] == "deny"
    assert body["estimated_usd"] == pytest.approx(0.60, rel=1e-9)


# --------------------------------------------------------------------------
# 9) Reset returns the previous counter value and zeroes the live one.
# --------------------------------------------------------------------------


def test_reset_warnings_total_returns_previous() -> None:
    """``reset_cost_cap_warnings_total`` is the operator's "ack the spike"
    primitive. It must atomically read the current value, zero the
    module attribute, and return the observed-before value so the caller
    can log/persist the delta."""
    federation_mod.cost_cap_warnings_total = 17

    previous = reset_cost_cap_warnings_total()
    assert previous == 17
    assert federation_mod.cost_cap_warnings_total == 0

    # A second reset on a freshly-zeroed counter returns 0.
    again = reset_cost_cap_warnings_total()
    assert again == 0
    assert federation_mod.cost_cap_warnings_total == 0


# --------------------------------------------------------------------------
# 10) Invalid mode payload to ``POST /cost-cap/mode`` returns HTTP 422.
# --------------------------------------------------------------------------


def test_post_cost_cap_mode_invalid_returns_422(
    client: TestClient,
) -> None:
    """Pydantic's ``Literal`` constraint must reject typos before the
    setter runs — a misconfigured runtime mode could silently disable
    the cap, so we lean on schema validation as the first defence."""
    r = client.post(
        "/api/v1/federation/cost-cap/mode",
        json={"mode": "loose"},  # not in {warn, deny, off}
    )
    assert r.status_code == 422, (
        f"expected 422 on invalid mode literal; got {r.status_code}: "
        f"{r.text[:200]}"
    )

    # Sanity: the runtime override must remain unset after the bad call.
    snapshot = get_runtime_cost_cap_mode()
    assert snapshot["runtime"] is None


# --------------------------------------------------------------------------
# Bonus coverage: the happy path for ``POST /cost-cap/mode``.
# --------------------------------------------------------------------------


def test_post_cost_cap_mode_happy_path_sets_runtime(
    client: TestClient,
) -> None:
    """Ensure the route actually wires through to the setter — set deny,
    then read back via /status and confirm the new effective mode."""
    r = client.post(
        "/api/v1/federation/cost-cap/mode",
        json={"mode": "deny"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"]["runtime"] == "deny"
    assert body["mode"]["effective"] == "deny"

    status = client.get("/api/v1/federation/cost-cap/status")
    assert status.status_code == 200
    assert status.json()["mode"]["effective"] == "deny"


def test_post_cost_cap_mode_null_clears_override(
    client: TestClient,
    monkeypatch,
) -> None:
    """Sending ``mode=null`` must clear the override and let env take
    over again. This is the operator's "back to default" hook."""
    monkeypatch.setenv("SYLION_COST_CAP_MODE", "off")
    set_runtime_cost_cap_mode("deny")

    r = client.post(
        "/api/v1/federation/cost-cap/mode",
        json={"mode": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"]["runtime"] is None
    assert body["mode"]["effective"] == "off", (
        "after clearing runtime, env-supplied 'off' must win"
    )


# --------------------------------------------------------------------------
# Pure-helper coverage: ``_evaluate_cost_cap`` returns the correct shape.
# --------------------------------------------------------------------------


def test_evaluate_cost_cap_returns_dataclass_shape() -> None:
    """The pure helper that backs both the router and the simulator must
    return a ``CostCapEvaluation`` with all four fields populated."""
    result = _evaluate_cost_cap(
        cost_per_1k_usd=0.60,
        estimated_tokens=1000,
        mode="warn",
    )
    assert isinstance(result, CostCapEvaluation)
    assert result.mode == "warn"
    assert result.estimated_usd == pytest.approx(0.60, rel=1e-9)
    assert result.exceeded is True
    assert result.action == "warn"


def test_evaluate_cost_cap_off_mode_always_allows() -> None:
    """Mode ``off`` is the kill-switch — even an obviously-over-cap
    estimate must report ``action=allow`` and the caller skips both
    the deny path and the warn-counter increment."""
    result = _evaluate_cost_cap(
        cost_per_1k_usd=10.0,  # 10 USD/1k tokens
        estimated_tokens=1000,
        mode="off",
    )
    assert result.exceeded is True  # 10 USD > 0.50 USD cap
    assert result.action == "allow", (
        "mode=off must short-circuit to allow even when exceeded"
    )


def test_set_runtime_mode_rejects_typo() -> None:
    """The setter is the last line of defence against a typo that would
    silently disable the cap; bad values must raise rather than be
    coerced."""
    with pytest.raises(ValueError, match="cost_cap mode"):
        set_runtime_cost_cap_mode("loose")  # type: ignore[arg-type]
