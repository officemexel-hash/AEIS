"""SYLION API -- Container & Kubernetes routes."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/container", tags=["container"])

_manager = None


def _get_manager():
    global _manager
    if _manager is not None:
        return _manager
    from sylion.container.docker_manager import get_container_manager
    _manager = get_container_manager()
    return _manager


# ---------------------------------------------------------------------------
# Docker Containers
# ---------------------------------------------------------------------------

@router.post("/containers", status_code=201)
def register_container(body: dict):
    mgr = _get_manager()
    return mgr.register_container(
        name=body.get("name", ""),
        image=body.get("image", ""),
        status=body.get("status", "created"),
        ports=body.get("ports"),
        env=body.get("env"),
        labels=body.get("labels"),
    )


@router.get("/containers")
def list_containers(status: str | None = None):
    mgr = _get_manager()
    return {"containers": mgr.list_containers(status=status)}


@router.get("/containers/{container_id}")
def get_container(container_id: str):
    mgr = _get_manager()
    result = mgr.get_container(container_id)
    if not result:
        raise HTTPException(status_code=404, detail="Container not found")
    return result


@router.patch("/containers/{container_id}")
def update_container(container_id: str, body: dict):
    mgr = _get_manager()
    result = mgr.update_container(container_id, **body)
    if not result:
        raise HTTPException(status_code=404, detail="Container not found")
    return result


@router.delete("/containers/{container_id}")
def delete_container(container_id: str):
    mgr = _get_manager()
    if not mgr.delete_container(container_id):
        raise HTTPException(status_code=404, detail="Container not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Docker Images
# ---------------------------------------------------------------------------

@router.post("/images", status_code=201)
def register_image(body: dict):
    mgr = _get_manager()
    return mgr.register_image(
        name=body.get("name", ""),
        tag=body.get("tag", "latest"),
        size_mb=body.get("size_mb", 0),
        labels=body.get("labels"),
    )


@router.get("/images")
def list_images():
    mgr = _get_manager()
    return {"images": mgr.list_images()}


@router.get("/images/{image_id}")
def get_image(image_id: str):
    mgr = _get_manager()
    result = mgr.get_image(image_id)
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    return result


@router.delete("/images/{image_id}")
def delete_image(image_id: str):
    mgr = _get_manager()
    if not mgr.delete_image(image_id):
        raise HTTPException(status_code=404, detail="Image not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# K8s Pods
# ---------------------------------------------------------------------------

@router.post("/pods", status_code=201)
def register_pod(body: dict):
    mgr = _get_manager()
    return mgr.register_pod(
        name=body.get("name", ""),
        namespace=body.get("namespace", "default"),
        status=body.get("status", "Pending"),
        node=body.get("node", ""),
        containers=body.get("containers"),
        labels=body.get("labels"),
    )


@router.get("/pods")
def list_pods(namespace: str | None = None):
    mgr = _get_manager()
    return {"pods": mgr.list_pods(namespace=namespace)}


@router.get("/pods/{pod_id}")
def get_pod(pod_id: str):
    mgr = _get_manager()
    result = mgr.get_pod(pod_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pod not found")
    return result


@router.patch("/pods/{pod_id}")
def update_pod(pod_id: str, body: dict):
    mgr = _get_manager()
    result = mgr.update_pod(pod_id, **body)
    if not result:
        raise HTTPException(status_code=404, detail="Pod not found")
    return result


@router.delete("/pods/{pod_id}")
def delete_pod(pod_id: str):
    mgr = _get_manager()
    if not mgr.delete_pod(pod_id):
        raise HTTPException(status_code=404, detail="Pod not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# K8s Deployments
# ---------------------------------------------------------------------------

@router.post("/deployments", status_code=201)
def register_deployment(body: dict):
    mgr = _get_manager()
    return mgr.register_deployment(
        name=body.get("name", ""),
        namespace=body.get("namespace", "default"),
        replicas=body.get("replicas", 1),
        available=body.get("available", 0),
        strategy=body.get("strategy", "RollingUpdate"),
        labels=body.get("labels"),
    )


@router.get("/deployments")
def list_deployments(namespace: str | None = None):
    mgr = _get_manager()
    return {"deployments": mgr.list_deployments(namespace=namespace)}


@router.get("/deployments/{deployment_id}")
def get_deployment(deployment_id: str):
    mgr = _get_manager()
    result = mgr.get_deployment(deployment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


@router.patch("/deployments/{deployment_id}")
def update_deployment(deployment_id: str, body: dict):
    mgr = _get_manager()
    result = mgr.update_deployment(deployment_id, **body)
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


@router.delete("/deployments/{deployment_id}")
def delete_deployment(deployment_id: str):
    mgr = _get_manager()
    if not mgr.delete_deployment(deployment_id):
        raise HTTPException(status_code=404, detail="Deployment not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def container_stats():
    mgr = _get_manager()
    return mgr.get_stats()
