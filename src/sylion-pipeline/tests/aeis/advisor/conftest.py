"""Shared pytest fixtures for AEIS advisor module tests."""

from __future__ import annotations

import sqlite3
import sys

import pytest


def _maybe_call(module_name: str, attr_name: str) -> None:
    try:
        module = __import__(module_name, fromlist=[attr_name])
        getattr(module, attr_name)()
    except Exception:
        return


def _maybe_close_sqlite_conn(module_name: str) -> None:
    try:
        module = __import__(module_name, fromlist=["_sqlite_conn"])
        conn = getattr(module, "_sqlite_conn", None)
        if conn is not None:
            conn.close()
        setattr(module, "_sqlite_conn", None)
    except Exception:
        return


def _maybe_close_event_buses() -> None:
    try:
        from sylion.core import event_bus as event_bus_mod

        bus = getattr(event_bus_mod, "_bus", None)
        if bus is not None:
            getattr(bus, "_conn").close()
        event_bus_mod._bus = None
    except Exception:
        pass

    try:
        from sylion.core import event_bus_factory as factory_mod

        for bus in list(getattr(factory_mod, "_instances", {}).values()):
            conn = getattr(bus, "_conn", None)
            if conn is not None:
                conn.close()
        factory_mod._instances.clear()
    except Exception:
        pass


def _maybe_close_singleton_conn(module_name: str, singleton_attr: str) -> None:
    try:
        module = __import__(module_name, fromlist=[singleton_attr])
        instance = getattr(module, singleton_attr, None)
        conn = getattr(instance, "_conn", None)
        if conn is not None:
            conn.close()
        setattr(module, singleton_attr, None)
    except Exception:
        return


def _close_sylion_sqlite_handles() -> None:
    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("sylion.") or module is None:
            continue
        for attr_name, value in list(vars(module).items()):
            if isinstance(value, sqlite3.Connection):
                try:
                    value.close()
                except Exception:
                    pass
                try:
                    setattr(module, attr_name, None)
                except Exception:
                    pass
                continue
            conn = getattr(value, "_conn", None)
            if isinstance(conn, sqlite3.Connection):
                try:
                    conn.close()
                except Exception:
                    pass


def _reset_service_singletons() -> None:
    _maybe_call("sylion.aeis.advisor.engine.service", "reset_engine_service")
    _maybe_call("sylion.aeis.advisor.events.audit_subscriber", "reset_advisor_audit_subscriber")
    _maybe_call("sylion.aeis.advisor.funding.service", "reset_funding_service")
    _maybe_call("sylion.aeis.advisor.history.service", "reset_history_service")
    _maybe_call("sylion.aeis.advisor.mobile_gateway.api", "reset_mobile_router")
    _maybe_call("sylion.aeis.advisor.preferences.service", "reset_preferences_service")
    _maybe_call("sylion.aeis.advisor.pricing", "reset_pricing")
    _maybe_call("sylion.aeis.advisor.role_resolver.service", "reset_role_resolver_service")
    _maybe_call("sylion.aeis.advisor.scaling.service", "reset_scaling_service")
    _maybe_call("sylion.aeis.advisor.subscription.service", "reset_subscription_service")
    _maybe_call("sylion.aeis.advisor.variants.service", "reset_variants_service")


@pytest.fixture(autouse=True)
def reset_advisor_singletons():
    """Reset advisor singletons without assuming every sibling module exists."""
    _reset_service_singletons()
    yield
    _reset_service_singletons()
    _maybe_close_event_buses()
    _maybe_close_singleton_conn("sylion.cognitive.model_registry", "_registry")
    _maybe_close_singleton_conn("sylion.monitoring.model_budget", "_instance")
    _maybe_close_singleton_conn("sylion.security.key_vault", "_vault")
    _maybe_close_sqlite_conn("sylion.aeis.advisor.engine._db")
    _maybe_close_sqlite_conn("sylion.aeis.advisor.preferences._db")


def pytest_sessionfinish(session, exitstatus):
    _reset_service_singletons()
    _maybe_close_event_buses()
    _close_sylion_sqlite_handles()
