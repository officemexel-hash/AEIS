"""Tests for SYLION Governance -- Roles Manager.

Covers: CRUD, permissions, assignments, permission checking, user roles,
EventBus integration, thread safety, and singleton management.
"""
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.roles import (
    RolesManager,
    get_roles_manager,
    reset_roles_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    """Fresh RolesManager with :memory: SQLite."""
    return RolesManager(db_path=":memory:")


@pytest.fixture
def mgr_with_bus():
    """RolesManager connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return RolesManager(db_path=":memory:", event_bus=bus), bus


# ---------------------------------------------------------------------------
# Test: create_role
# ---------------------------------------------------------------------------

class TestCreateRole:
    def test_creates_basic_role(self, mgr):
        result = mgr.create_role("admin", "Administrator")
        assert "role_id" in result
        assert result["name"] == "admin"
        assert result["description"] == "Administrator"
        assert result["permissions"] == []

    def test_creates_with_permissions(self, mgr):
        perms = ["read", "write", "execute"]
        result = mgr.create_role("editor", "Editor", permissions_list=perms)
        assert result["permissions"] == perms

    def test_creates_without_description(self, mgr):
        result = mgr.create_role("minimal")
        assert result["description"] == ""

    def test_rejects_empty_name(self, mgr):
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.create_role("")

    def test_rejects_whitespace_name(self, mgr):
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.create_role("   ")

    def test_rejects_duplicate_name(self, mgr):
        mgr.create_role("unique-name")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_role("unique-name")

    def test_role_id_is_unique(self, mgr):
        r1 = mgr.create_role("role-1")
        r2 = mgr.create_role("role-2")
        assert r1["role_id"] != r2["role_id"]

    def test_timestamps_set(self, mgr):
        before = time.time()
        result = mgr.create_role("ts-role")
        after = time.time()
        assert before <= result["created_at"] <= after
        assert result["created_at"] == result["updated_at"]


# ---------------------------------------------------------------------------
# Test: update_role
# ---------------------------------------------------------------------------

class TestUpdateRole:
    def test_updates_name(self, mgr):
        r = mgr.create_role("old-name", "desc")
        updated = mgr.update_role(r["role_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_updates_description(self, mgr):
        r = mgr.create_role("desc-test", "old desc")
        updated = mgr.update_role(r["role_id"], description="new desc")
        assert updated["description"] == "new desc"

    def test_returns_none_for_missing(self, mgr):
        result = mgr.update_role("nonexistent", name="x")
        assert result is None

    def test_rejects_duplicate_name_on_update(self, mgr):
        mgr.create_role("name-a")
        r2 = mgr.create_role("name-b")
        with pytest.raises(ValueError, match="already exists"):
            mgr.update_role(r2["role_id"], name="name-a")

    def test_preserves_permissions_on_update(self, mgr):
        r = mgr.create_role("perms", permissions_list=["read"])
        updated = mgr.update_role(r["role_id"], description="updated")
        assert updated["permissions"] == ["read"]

    def test_updated_at_changes(self, mgr):
        r = mgr.create_role("ts-up")
        time.sleep(0.01)
        updated = mgr.update_role(r["role_id"], name="changed")
        assert updated["updated_at"] > r["created_at"]


# ---------------------------------------------------------------------------
# Test: delete_role
# ---------------------------------------------------------------------------

class TestDeleteRole:
    def test_deletes_existing(self, mgr):
        r = mgr.create_role("del-me")
        assert mgr.delete_role(r["role_id"]) is True

    def test_returns_false_for_missing(self, mgr):
        assert mgr.delete_role("nonexistent") is False

    def test_get_returns_none_after_delete(self, mgr):
        r = mgr.create_role("del-get")
        mgr.delete_role(r["role_id"])
        assert mgr.get_role(r["role_id"]) is None

    def test_cascades_permissions(self, mgr):
        r = mgr.create_role("cascade-perm", permissions_list=["read", "write"])
        mgr.delete_role(r["role_id"])
        assert mgr._get_role_permissions(r["role_id"]) == []

    def test_cascades_assignments(self, mgr):
        r = mgr.create_role("cascade-assign", permissions_list=["read"])
        mgr.assign_role(r["role_id"], "user-1")
        mgr.delete_role(r["role_id"])
        assert mgr.get_user_roles("user-1") == []


# ---------------------------------------------------------------------------
# Test: get_role
# ---------------------------------------------------------------------------

class TestGetRole:
    def test_returns_created_role(self, mgr):
        r = mgr.create_role("get-test", "desc", permissions_list=["read"])
        fetched = mgr.get_role(r["role_id"])
        assert fetched is not None
        assert fetched["name"] == "get-test"
        assert "read" in fetched["permissions"]

    def test_returns_none_for_missing(self, mgr):
        assert mgr.get_role("nonexistent") is None


# ---------------------------------------------------------------------------
# Test: list_roles
# ---------------------------------------------------------------------------

class TestListRoles:
    def test_lists_all(self, mgr):
        mgr.create_role("r1")
        mgr.create_role("r2")
        assert len(mgr.list_roles()) == 2

    def test_empty_list(self, mgr):
        assert mgr.list_roles() == []

    def test_includes_permissions(self, mgr):
        mgr.create_role("with-perms", permissions_list=["read", "write"])
        roles = mgr.list_roles()
        assert "read" in roles[0]["permissions"]
        assert "write" in roles[0]["permissions"]

    def test_ordered_by_created_at(self, mgr):
        mgr.create_role("first")
        time.sleep(0.01)
        mgr.create_role("second")
        roles = mgr.list_roles()
        assert roles[0]["name"] == "first"
        assert roles[1]["name"] == "second"


# ---------------------------------------------------------------------------
# Test: add_permission / remove_permission
# ---------------------------------------------------------------------------

class TestPermissionManagement:
    def test_add_permission(self, mgr):
        r = mgr.create_role("add-perm")
        result = mgr.add_permission(r["role_id"], "execute")
        assert result is True

    def test_add_duplicate_returns_false(self, mgr):
        r = mgr.create_role("dup-perm", permissions_list=["read"])
        result = mgr.add_permission(r["role_id"], "read")
        assert result is False

    def test_add_permission_to_missing_role(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.add_permission("nonexistent", "read")

    def test_remove_permission(self, mgr):
        r = mgr.create_role("rem-perm", permissions_list=["read", "write"])
        result = mgr.remove_permission(r["role_id"], "write")
        assert result is True
        assert mgr._get_role_permissions(r["role_id"]) == ["read"]

    def test_remove_nonexistent_permission(self, mgr):
        r = mgr.create_role("rem-none")
        result = mgr.remove_permission(r["role_id"], "nonexistent")
        assert result is False

    def test_permissions_visible_in_get_role(self, mgr):
        r = mgr.create_role("vis-perm")
        mgr.add_permission(r["role_id"], "deploy")
        role = mgr.get_role(r["role_id"])
        assert "deploy" in role["permissions"]


# ---------------------------------------------------------------------------
# Test: assign_role
# ---------------------------------------------------------------------------

class TestAssignRole:
    def test_assigns_role_to_user(self, mgr):
        r = mgr.create_role("assign-test", permissions_list=["read"])
        result = mgr.assign_role(r["role_id"], "user-1")
        assert "assignment_id" in result
        assert result["user_id"] == "user-1"
        assert result["already_assigned"] is False

    def test_assigns_with_assigned_by(self, mgr):
        r = mgr.create_role("assigned-by")
        result = mgr.assign_role(r["role_id"], "user-2", assigned_by="admin-1")
        assert result["assigned_by"] == "admin-1"

    def test_duplicate_assignment_idempotent(self, mgr):
        r = mgr.create_role("dup-assign")
        r1 = mgr.assign_role(r["role_id"], "user-3")
        r2 = mgr.assign_role(r["role_id"], "user-3")
        assert r2["already_assigned"] is True
        assert r1["assignment_id"] == r2["assignment_id"]

    def test_raises_for_missing_role(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.assign_role("nonexistent", "user-1")

    def test_user_can_have_multiple_roles(self, mgr):
        r1 = mgr.create_role("multi-1")
        r2 = mgr.create_role("multi-2")
        mgr.assign_role(r1["role_id"], "user-multi")
        mgr.assign_role(r2["role_id"], "user-multi")
        roles = mgr.get_user_roles("user-multi")
        assert len(roles) == 2


# ---------------------------------------------------------------------------
# Test: revoke_assignment
# ---------------------------------------------------------------------------

class TestRevokeAssignment:
    def test_revokes_existing(self, mgr):
        r = mgr.create_role("revoke-test")
        assignment = mgr.assign_role(r["role_id"], "user-rev")
        assert mgr.revoke_assignment(assignment["assignment_id"]) is True

    def test_returns_false_for_missing(self, mgr):
        assert mgr.revoke_assignment("nonexistent") is False

    def test_user_loses_role_after_revoke(self, mgr):
        r = mgr.create_role("revoke-check")
        assignment = mgr.assign_role(r["role_id"], "user-check")
        mgr.revoke_assignment(assignment["assignment_id"])
        assert mgr.get_user_roles("user-check") == []


# ---------------------------------------------------------------------------
# Test: get_user_roles
# ---------------------------------------------------------------------------

class TestGetUserRoles:
    def test_returns_assigned_roles(self, mgr):
        r1 = mgr.create_role("ur-1", permissions_list=["read"])
        r2 = mgr.create_role("ur-2", permissions_list=["write"])
        mgr.assign_role(r1["role_id"], "user-ur")
        mgr.assign_role(r2["role_id"], "user-ur")
        roles = mgr.get_user_roles("user-ur")
        assert len(roles) == 2

    def test_empty_for_no_roles(self, mgr):
        assert mgr.get_user_roles("user-none") == []

    def test_includes_permissions(self, mgr):
        r = mgr.create_role("ur-perm", permissions_list=["read", "execute"])
        mgr.assign_role(r["role_id"], "user-perm")
        roles = mgr.get_user_roles("user-perm")
        assert "read" in roles[0]["permissions"]
        assert "execute" in roles[0]["permissions"]


# ---------------------------------------------------------------------------
# Test: check_permission
# ---------------------------------------------------------------------------

class TestCheckPermission:
    def test_returns_true_when_has_permission(self, mgr):
        r = mgr.create_role("check-yes", permissions_list=["read", "write"])
        mgr.assign_role(r["role_id"], "user-check")
        assert mgr.check_permission("user-check", "read") is True

    def test_returns_false_when_no_permission(self, mgr):
        r = mgr.create_role("check-no", permissions_list=["read"])
        mgr.assign_role(r["role_id"], "user-no")
        assert mgr.check_permission("user-no", "admin") is False

    def test_returns_false_for_no_roles(self, mgr):
        assert mgr.check_permission("user-none", "read") is False

    def test_checks_across_multiple_roles(self, mgr):
        r1 = mgr.create_role("cross-1", permissions_list=["read"])
        r2 = mgr.create_role("cross-2", permissions_list=["write"])
        mgr.assign_role(r1["role_id"], "user-cross")
        mgr.assign_role(r2["role_id"], "user-cross")
        assert mgr.check_permission("user-cross", "read") is True
        assert mgr.check_permission("user-cross", "write") is True


# ---------------------------------------------------------------------------
# Test: get_user_permissions
# ---------------------------------------------------------------------------

class TestGetUserPermissions:
    def test_returns_all_permissions(self, mgr):
        r1 = mgr.create_role("gp-1", permissions_list=["read"])
        r2 = mgr.create_role("gp-2", permissions_list=["write", "execute"])
        mgr.assign_role(r1["role_id"], "user-gp")
        mgr.assign_role(r2["role_id"], "user-gp")
        perms = mgr.get_user_permissions("user-gp")
        assert "read" in perms
        assert "write" in perms
        assert "execute" in perms

    def test_deduplicates(self, mgr):
        r1 = mgr.create_role("dedup-1", permissions_list=["read"])
        r2 = mgr.create_role("dedup-2", permissions_list=["read"])
        mgr.assign_role(r1["role_id"], "user-dedup")
        mgr.assign_role(r2["role_id"], "user-dedup")
        perms = mgr.get_user_permissions("user-dedup")
        assert perms.count("read") == 1

    def test_empty_for_no_roles(self, mgr):
        assert mgr.get_user_permissions("user-none") == []


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_role_created_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("role_created", lambda e: events.append(e))
        mgr.create_role("ev-create", permissions_list=["read"])
        assert len(events) == 1
        assert events[0].payload["name"] == "ev-create"
        assert "read" in events[0].payload["permissions"]

    def test_role_updated_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("role_updated", lambda e: events.append(e))
        r = mgr.create_role("ev-update")
        mgr.update_role(r["role_id"], name="renamed")
        assert len(events) == 1

    def test_role_assigned_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("role_assigned", lambda e: events.append(e))
        r = mgr.create_role("ev-assign")
        mgr.assign_role(r["role_id"], "user-ev", assigned_by="admin")
        assert len(events) == 1
        assert events[0].payload["user_id"] == "user-ev"

    def test_permission_checked_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("permission_checked", lambda e: events.append(e))
        r = mgr.create_role("ev-check", permissions_list=["read"])
        mgr.assign_role(r["role_id"], "user-pc")
        mgr.check_permission("user-pc", "read")
        assert len(events) == 1
        assert events[0].payload["granted"] is True

    def test_permission_checked_event_denied(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("permission_checked", lambda e: events.append(e))
        mgr.check_permission("user-no-perms", "admin")
        assert len(events) == 1
        assert events[0].payload["granted"] is False

    def test_no_event_without_bus(self, mgr):
        mgr.create_role("no-bus")
        r = mgr.create_role("no-bus2", permissions_list=["read"])
        mgr.assign_role(r["role_id"], "user-no-bus")
        mgr.check_permission("user-no-bus", "read")


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_role_creates(self, mgr):
        errors = []

        def create(i):
            try:
                mgr.create_role(f"role-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mgr.list_roles()) == 20

    def test_concurrent_assignments(self, mgr):
        roles = [mgr.create_role(f"ca-{i}", permissions_list=["read"]) for i in range(5)]
        errors = []

        def assign(user_idx):
            try:
                role = roles[user_idx % len(roles)]
                mgr.assign_role(role["role_id"], f"user-{user_idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=assign, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_read_write(self, mgr):
        r = mgr.create_role("rw-role", permissions_list=["read"])
        mgr.assign_role(r["role_id"], "user-rw")
        errors = []

        def reader():
            try:
                for _ in range(50):
                    mgr.get_role(r["role_id"])
                    mgr.list_roles()
                    mgr.check_permission("user-rw", "read")
                    mgr.get_user_roles("user-rw")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                mgr.add_permission(r["role_id"], "write")
                mgr.assign_role(r["role_id"], "user-rw-2")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Test: singleton management
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        reset_roles_manager()
        s1 = get_roles_manager(db_path=":memory:")
        s2 = get_roles_manager()
        assert s1 is s2
        reset_roles_manager()

    def test_reset_clears_singleton(self):
        s1 = get_roles_manager(db_path=":memory:")
        reset_roles_manager()
        s2 = get_roles_manager(db_path=":memory:")
        assert s1 is not s2
        reset_roles_manager()
