from __future__ import annotations

import pytest

from sylion.container.docker_manager import (
    ContainerManager,
    get_container_manager,
    reset_container_manager,
)


class _FakeEventBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)
        return event.event_id


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_container_manager()
    yield
    reset_container_manager()


@pytest.fixture
def event_bus():
    return _FakeEventBus()


@pytest.fixture
def manager(event_bus):
    return ContainerManager(db_path=":memory:", event_bus=event_bus)


def test_register_container_creates_row_with_uid(manager, event_bus):
    result = manager.register_container(
        name="api",
        image="nginx:latest",
        status="running",
        ports=[80, 443],
        env={"MODE": "prod"},
        labels={"tier": "web"},
    )
    stored = manager.get_container(result["container_id"])

    assert result["container_id"]
    assert stored["name"] == "api"
    assert stored["image"] == "nginx:latest"
    assert stored["status"] == "running"
    assert stored["ports"] == [80, 443]
    assert stored["env"] == {"MODE": "prod"}
    assert stored["labels"] == {"tier": "web"}
    assert event_bus.events[-1].topic == "container.registered"


def test_list_containers_returns_registered_rows(manager):
    first = manager.register_container(name="worker", status="created")
    second = manager.register_container(name="api", status="running")
    items = manager.list_containers()

    assert [item["container_id"] for item in items] == [
        second["container_id"],
        first["container_id"],
    ]


def test_get_container_with_invalid_id_returns_none(manager):
    assert manager.get_container("missing-container") is None


def test_update_container_persists_allowed_fields(manager, event_bus):
    created = manager.register_container(name="api", image="nginx:1.0")

    updated = manager.update_container(
        created["container_id"],
        name="api-v2",
        image="nginx:1.1",
        status="running",
        ports=[8080],
        env={"A": "1"},
        labels={"rev": "2"},
    )

    assert updated["name"] == "api-v2"
    assert updated["image"] == "nginx:1.1"
    assert updated["status"] == "running"
    assert updated["ports"] == [8080]
    assert updated["env"] == {"A": "1"}
    assert updated["labels"] == {"rev": "2"}
    assert event_bus.events[-1].topic == "container.updated"


def test_delete_container_removes_row(manager, event_bus):
    created = manager.register_container(name="api")

    deleted = manager.delete_container(created["container_id"])

    assert deleted is True
    assert manager.get_container(created["container_id"]) is None
    assert event_bus.events[-1].topic == "container.deleted"


def test_register_image_creates_row_with_uid(manager, event_bus):
    result = manager.register_image(
        name="python",
        tag="3.12",
        size_mb=150,
        labels={"base": "debian"},
    )
    stored = manager.get_image(result["image_id"])

    assert result["image_id"]
    assert stored["name"] == "python"
    assert stored["tag"] == "3.12"
    assert stored["size_mb"] == 150
    assert stored["labels"] == {"base": "debian"}
    assert event_bus.events[-1].topic == "image.registered"


def test_list_images_returns_registered_rows(manager):
    first = manager.register_image(name="python", tag="3.11")
    second = manager.register_image(name="redis", tag="7")
    items = manager.list_images()

    assert [item["image_id"] for item in items] == [
        second["image_id"],
        first["image_id"],
    ]


def test_get_image_returns_registered_row(manager):
    created = manager.register_image(name="postgres", tag="16")

    stored = manager.get_image(created["image_id"])

    assert stored["name"] == "postgres"
    assert stored["tag"] == "16"


def test_delete_image_removes_row(manager):
    created = manager.register_image(name="redis")

    deleted = manager.delete_image(created["image_id"])

    assert deleted is True
    assert manager.get_image(created["image_id"]) is None


def test_register_pod_creates_row_with_uid(manager, event_bus):
    result = manager.register_pod(
        name="api-pod",
        namespace="prod",
        status="Running",
        node="node-a",
        containers=["api", "sidecar"],
        labels={"app": "api"},
    )
    stored = manager.get_pod(result["pod_id"])

    assert result["pod_id"]
    assert stored["name"] == "api-pod"
    assert stored["namespace"] == "prod"
    assert stored["status"] == "Running"
    assert stored["node"] == "node-a"
    assert stored["containers"] == ["api", "sidecar"]
    assert stored["labels"] == {"app": "api"}
    assert event_bus.events[-1].topic == "pod.registered"


def test_list_pods_returns_registered_rows(manager):
    first = manager.register_pod(name="job-a")
    second = manager.register_pod(name="job-b")
    items = manager.list_pods()

    assert [item["pod_id"] for item in items] == [
        second["pod_id"],
        first["pod_id"],
    ]


def test_get_pod_returns_registered_row(manager):
    created = manager.register_pod(name="api-pod", namespace="prod")

    stored = manager.get_pod(created["pod_id"])

    assert stored["name"] == "api-pod"
    assert stored["namespace"] == "prod"


def test_update_pod_persists_allowed_fields(manager):
    created = manager.register_pod(name="api-pod")

    updated = manager.update_pod(
        created["pod_id"],
        name="api-pod-v2",
        namespace="prod",
        status="Running",
        node="node-b",
        containers=["api"],
        labels={"rev": "2"},
    )

    assert updated["name"] == "api-pod-v2"
    assert updated["namespace"] == "prod"
    assert updated["status"] == "Running"
    assert updated["node"] == "node-b"
    assert updated["containers"] == ["api"]
    assert updated["labels"] == {"rev": "2"}


def test_delete_pod_removes_row(manager):
    created = manager.register_pod(name="api-pod")

    deleted = manager.delete_pod(created["pod_id"])

    assert deleted is True
    assert manager.get_pod(created["pod_id"]) is None


def test_register_deployment_creates_row_with_uid(manager, event_bus):
    result = manager.register_deployment(
        name="api-deploy",
        namespace="prod",
        replicas=3,
        available=2,
        strategy="Recreate",
        labels={"app": "api"},
    )
    stored = manager.get_deployment(result["deployment_id"])

    assert result["deployment_id"]
    assert stored["name"] == "api-deploy"
    assert stored["namespace"] == "prod"
    assert stored["replicas"] == 3
    assert stored["available"] == 2
    assert stored["strategy"] == "Recreate"
    assert stored["labels"] == {"app": "api"}
    assert event_bus.events[-1].topic == "deployment.registered"


def test_list_deployments_returns_registered_rows(manager):
    first = manager.register_deployment(name="api-a")
    second = manager.register_deployment(name="api-b")
    items = manager.list_deployments()

    assert [item["deployment_id"] for item in items] == [
        second["deployment_id"],
        first["deployment_id"],
    ]


def test_get_deployment_returns_registered_row(manager):
    created = manager.register_deployment(name="api-deploy", namespace="prod")

    stored = manager.get_deployment(created["deployment_id"])

    assert stored["name"] == "api-deploy"
    assert stored["namespace"] == "prod"


def test_update_deployment_persists_allowed_fields(manager):
    created = manager.register_deployment(name="api-deploy")

    updated = manager.update_deployment(
        created["deployment_id"],
        name="api-deploy-v2",
        namespace="prod",
        replicas=5,
        available=4,
        strategy="Recreate",
        labels={"rev": "2"},
    )

    assert updated["name"] == "api-deploy-v2"
    assert updated["namespace"] == "prod"
    assert updated["replicas"] == 5
    assert updated["available"] == 4
    assert updated["strategy"] == "Recreate"
    assert updated["labels"] == {"rev": "2"}


def test_delete_deployment_removes_row(manager):
    created = manager.register_deployment(name="api-deploy")

    deleted = manager.delete_deployment(created["deployment_id"])

    assert deleted is True
    assert manager.get_deployment(created["deployment_id"]) is None


def test_get_stats_returns_counts_for_all_entity_types(manager):
    manager.register_container(name="api")
    manager.register_container(name="worker")
    manager.register_image(name="python")
    manager.register_pod(name="api-pod")
    manager.register_deployment(name="api-deploy")

    stats = manager.get_stats()

    assert stats == {
        "docker_containers": 2,
        "docker_images": 1,
        "k8s_pods": 1,
        "k8s_deployments": 1,
    }


@pytest.mark.parametrize(
    ("register_name", "list_name"),
    [
        ("register_container", "list_containers"),
        ("register_image", "list_images"),
        ("register_pod", "list_pods"),
        ("register_deployment", "list_deployments"),
    ],
)
def test_duplicate_registration_handling_creates_distinct_rows(manager, register_name, list_name):
    register = getattr(manager, register_name)
    items_before = getattr(manager, list_name)()
    assert items_before == []

    first = register(name="duplicate")
    second = register(name="duplicate")
    items_after = getattr(manager, list_name)()

    assert len(items_after) == 2
    assert first != second


@pytest.mark.parametrize(
    ("getter_name", "invalid_id"),
    [
        ("get_container", "missing-container"),
        ("get_image", "missing-image"),
        ("get_pod", "missing-pod"),
        ("get_deployment", "missing-deployment"),
    ],
)
def test_get_with_invalid_id_returns_none_for_each_entity(manager, getter_name, invalid_id):
    getter = getattr(manager, getter_name)
    assert getter(invalid_id) is None


@pytest.mark.parametrize(
    ("updater_name", "invalid_id"),
    [
        ("update_container", "missing-container"),
        ("update_pod", "missing-pod"),
        ("update_deployment", "missing-deployment"),
    ],
)
def test_update_with_invalid_id_returns_none_for_supported_entities(manager, updater_name, invalid_id):
    updater = getattr(manager, updater_name)
    assert updater(invalid_id, name="updated") is None


@pytest.mark.parametrize(
    ("register_name", "delete_name", "id_key"),
    [
        ("register_container", "delete_container", "container_id"),
        ("register_image", "delete_image", "image_id"),
        ("register_pod", "delete_pod", "pod_id"),
        ("register_deployment", "delete_deployment", "deployment_id"),
    ],
)
def test_delete_is_idempotent(register_name, delete_name, id_key, manager):
    register = getattr(manager, register_name)
    delete = getattr(manager, delete_name)
    created = register(name="to-delete")

    assert delete(created[id_key]) is True
    assert delete(created[id_key]) is False


def test_get_container_manager_returns_singleton_instance():
    first = get_container_manager(db_path=":memory:")
    second = get_container_manager()

    assert isinstance(first, ContainerManager)
    assert first is second


def test_reset_container_manager_creates_fresh_singleton():
    first = get_container_manager(db_path=":memory:")

    reset_container_manager()
    second = get_container_manager(db_path=":memory:")

    assert first is not second
