"""Tests for sylion.devices.artifact_deployer -- ArtifactDeployer."""

import pytest

from sylion.devices.artifact_deployer import ArtifactDeployer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deployer():
    return ArtifactDeployer(db_path=":memory:")


# ---------------------------------------------------------------------------
# deploy()
# ---------------------------------------------------------------------------

class TestDeploy:
    def test_deploy_returns_record(self, deployer):
        result = deployer.deploy("dev-1", "deadbeef12345678")
        assert result["deploy_id"].startswith("dep-")
        assert result["device_id"] == "dev-1"
        assert result["artifact_hash"] == "deadbeef12345678"
        assert result["status"] == "deployed"
        assert result["rollback_hash"] == ""

    def test_deploy_default_type_is_apk(self, deployer):
        result = deployer.deploy("dev-1", "abcdef0123456789")
        assert result["artifact_type"] == "apk"

    def test_deploy_custom_type(self, deployer):
        result = deployer.deploy("dev-1", "abcdef0123456789",
                                 artifact_type="firmware")
        assert result["artifact_type"] == "firmware"

    def test_deploy_has_timestamp(self, deployer):
        result = deployer.deploy("dev-1", "abcdef0123456789")
        assert result["deployed_at"] > 0

    def test_multiple_deploys_same_device(self, deployer):
        deployer.deploy("dev-1", "hash1abcdef1234")
        deployer.deploy("dev-1", "hash2abcdef5678")
        deps = deployer.list_deployments(device_id="dev-1")
        assert len(deps) == 2


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, deployer):
        result = deployer.deploy("dev-1", "abcdef0123456789")
        fetched = deployer.get(result["deploy_id"])
        assert fetched is not None
        assert fetched["device_id"] == "dev-1"

    def test_get_nonexistent_returns_none(self, deployer):
        assert deployer.get("no-such-deploy") is None


# ---------------------------------------------------------------------------
# rollback()
# ---------------------------------------------------------------------------

class TestRollback:
    def test_rollback_success(self, deployer):
        result = deployer.deploy("dev-1", "originalhash1234")
        deploy_id = result["deploy_id"]
        rolled = deployer.rollback(deploy_id)
        assert rolled is not None
        assert rolled["status"] == "rolled_back"
        assert rolled["rollback_hash"] == "originalhash1234"

    def test_rollback_nonexistent_returns_none(self, deployer):
        assert deployer.rollback("no-such-id") is None

    def test_rollback_preserves_original_hash(self, deployer):
        result = deployer.deploy("dev-1", "uniquehash9876")
        rolled = deployer.rollback(result["deploy_id"])
        assert rolled["rollback_hash"] == "uniquehash9876"
        assert rolled["artifact_hash"] == "uniquehash9876"

    def test_rollback_can_be_retrieved(self, deployer):
        result = deployer.deploy("dev-1", "canretrievehash")
        deploy_id = result["deploy_id"]
        deployer.rollback(deploy_id)
        fetched = deployer.get(deploy_id)
        assert fetched["status"] == "rolled_back"


# ---------------------------------------------------------------------------
# list_deployments()
# ---------------------------------------------------------------------------

class TestListDeployments:
    def test_list_all(self, deployer):
        deployer.deploy("dev-1", "hash000000001")
        deployer.deploy("dev-2", "hash000000002")
        deps = deployer.list_deployments()
        assert len(deps) == 2

    def test_filter_by_device(self, deployer):
        deployer.deploy("dev-1", "hash000000001")
        deployer.deploy("dev-2", "hash000000002")
        deployer.deploy("dev-1", "hash000000003")
        deps = deployer.list_deployments(device_id="dev-1")
        assert len(deps) == 2

    def test_limit(self, deployer):
        for i in range(5):
            deployer.deploy("dev-1", f"hash{i:016d}")
        deps = deployer.list_deployments(limit=3)
        assert len(deps) == 3

    def test_empty_list(self, deployer):
        assert deployer.list_deployments() == []

    def test_order_is_newest_first(self, deployer):
        import time
        d1 = deployer.deploy("dev-1", "firsthash00001")
        time.sleep(0.01)
        d2 = deployer.deploy("dev-1", "secondhash0001")
        deps = deployer.list_deployments()
        assert deps[0]["deploy_id"] == d2["deploy_id"]


# ---------------------------------------------------------------------------
# dry_run()
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_valid_hash(self, deployer):
        result = deployer.dry_run("dev-1", "longenoughhash")
        assert result["valid"] is True
        assert result["dry_run"] is True
        assert result["warnings"] == []

    def test_dry_run_short_hash(self, deployer):
        result = deployer.dry_run("dev-1", "short")
        assert result["valid"] is False
        assert len(result["warnings"]) > 0

    def test_dry_run_does_not_create_deployment(self, deployer):
        deployer.dry_run("dev-1", "validhash12345")
        deps = deployer.list_deployments()
        assert len(deps) == 0

    def test_dry_run_returns_device_id(self, deployer):
        result = deployer.dry_run("dev-x", "validhash12345")
        assert result["device_id"] == "dev-x"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_deploy_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        d = ArtifactDeployer(db_path=":memory:", event_bus=MockBus())
        d.deploy("dev-1", "abcdef0123456789")
        topics = [e.topic for e in events]
        assert "device.artifact.deployed" in topics

    def test_rollback_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        d = ArtifactDeployer(db_path=":memory:", event_bus=MockBus())
        result = d.deploy("dev-1", "abcdef0123456789")
        d.rollback(result["deploy_id"])
        topics = [e.topic for e in events]
        assert "device.artifact.rolled_back" in topics
