from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from sylion.api.app import app
import sylion.api.monitoring_budget_routes as _routes
from sylion.monitoring.model_budget import reset_model_budget

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_budget_runtime(tmp_path, monkeypatch):
    db_path = tmp_path / "monitoring-budget.sqlite"
    monkeypatch.setenv("SYLION_DB_PATH", str(db_path))

    if _routes._tracker is not None:
        _routes._tracker._conn.close()
    _routes._tracker = None
    reset_model_budget()

    yield

    if _routes._tracker is not None:
        _routes._tracker._conn.close()
    _routes._tracker = None
    reset_model_budget()


def _configure_budget():
    response = client.put(
        "/api/v1/monitoring/budget/qwen3.5:latest",
        json={
            "budget_limit": 300.0,
            "provider": "ollama",
            "fallback_model_id": "gpt-oss:20b",
        },
    )
    assert response.status_code == 200
    return response.json()


def _record_usage():
    response = client.post(
        "/api/v1/monitoring/budget/qwen3.5:latest/usage",
        json={
            "amount": 12.5,
            "tokens_in": 123,
            "tokens_out": 45,
            "task_type": "analysis",
            "session_id": "session_live_001",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_monitoring_budget_summary_and_transactions_routes_return_live_shapes():
    budget = _configure_budget()
    recorded = _record_usage()

    assert budget["budget_limit"] == pytest.approx(300.0)
    assert budget["provider"] == "ollama"
    assert budget["fallback_model_id"] == "gpt-oss:20b"
    assert recorded["recorded"] is True
    assert recorded["transaction"]["task_type"] == "analysis"

    summary = client.get("/api/v1/monitoring/budget/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["total_budget"] == pytest.approx(300.0)
    assert payload["total_spent"] == pytest.approx(12.5)
    assert payload["generated_at"] > 0
    assert len(payload["by_model"]) == 1
    assert payload["by_model"][0]["model_id"] == "qwen3.5:latest"
    assert payload["by_model"][0]["period_spend"]["monthly"] == pytest.approx(12.5)
    assert payload["by_model"][0]["period_budget"]["monthly"] == pytest.approx(300.0)

    transactions = client.get("/api/v1/monitoring/budget/transactions?limit=10")
    assert transactions.status_code == 200
    tx_payload = transactions.json()
    assert "transactions" in tx_payload
    assert len(tx_payload["transactions"]) == 1
    assert tx_payload["transactions"][0]["model_id"] == "qwen3.5:latest"
    assert tx_payload["transactions"][0]["amount"] == pytest.approx(12.5)
    assert tx_payload["transactions"][0]["tokens_in"] == 123
    assert tx_payload["transactions"][0]["tokens_out"] == 45


def test_monitoring_budget_reset_clears_visible_spend_and_preserves_configuration():
    _configure_budget()
    _record_usage()

    reset_response = client.post("/api/v1/monitoring/budget/qwen3.5:latest/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["reset"] is True

    budget = client.get("/api/v1/monitoring/budget/qwen3.5:latest")
    assert budget.status_code == 200
    payload = budget.json()
    assert payload["budget_limit"] == pytest.approx(300.0)
    assert payload["spent"] == pytest.approx(0.0)
    assert payload["remaining"] == pytest.approx(300.0)

    transactions = client.get("/api/v1/monitoring/budget/transactions")
    assert transactions.status_code == 200
    assert transactions.json()["transactions"] == []


def test_monitoring_budget_uses_persistent_db_when_singleton_reloads():
    _configure_budget()
    _record_usage()

    if _routes._tracker is not None:
        _routes._tracker._conn.close()
    _routes._tracker = None
    reset_model_budget()

    summary = client.get("/api/v1/monitoring/budget/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["total_budget"] == pytest.approx(300.0)
    assert payload["total_spent"] == pytest.approx(12.5)
    assert payload["by_model"][0]["provider"] == "ollama"
