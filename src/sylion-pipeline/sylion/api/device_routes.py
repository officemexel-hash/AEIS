"""
SYLION API -- Device routes.

Endpoints for: device_discovery, device_registry, artifact_deployer,
test_harness.
"""

from fastapi import APIRouter, HTTPException

from sylion.devices.device_discovery import get_device_discovery
from sylion.devices.device_registry import get_device_registry
from sylion.devices.artifact_deployer import get_artifact_deployer
from sylion.devices.test_harness import get_on_device_test_harness

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


# ---------------------------------------------------------------------------
# Device Discovery (M1)
# ---------------------------------------------------------------------------

@router.post("/discovery/scan", status_code=201)
def scan_devices(transport: str = "all"):
    """Scan for devices on available transports."""
    svc = get_device_discovery()
    discovered = svc.scan(transport=transport)
    return {"discovered": discovered}


@router.get("/discovery")
def list_discovered_devices(transport: str | None = None,
                            status: str | None = None):
    """List discovered devices with optional filters."""
    svc = get_device_discovery()
    return {"devices": svc.list_devices(transport=transport, status=status)}


@router.get("/discovery/{device_id}")
def get_discovered_device(device_id: str):
    """Get a single discovered device by ID."""
    svc = get_device_discovery()
    device = svc.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    return device


@router.post("/discovery/{device_id}/release")
def release_device(device_id: str):
    """Release a discovered device."""
    svc = get_device_discovery()
    result = svc.release(device_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    return result


# ---------------------------------------------------------------------------
# Device Registry (M2)
# ---------------------------------------------------------------------------

@router.post("/registry", status_code=201)
def register_device(device_id: str, transport: str, model: str,
                    firmware: str = "", capabilities: str = "{}"):
    """Register a new device in the registry."""
    import json
    reg = get_device_registry()
    caps = json.loads(capabilities) if isinstance(capabilities, str) else {}
    return reg.register(device_id=device_id, transport=transport,
                        model=model, firmware=firmware,
                        capabilities=caps)


@router.get("/registry")
def list_registered_devices(lifecycle: str | None = None):
    """List registered devices with optional lifecycle filter."""
    reg = get_device_registry()
    return {"devices": reg.list_devices(lifecycle=lifecycle)}


@router.get("/registry/{device_id}")
def get_registered_device(device_id: str):
    """Get a single registered device by ID."""
    reg = get_device_registry()
    device = reg.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    return device


@router.post("/registry/{device_id}/transition")
def transition_device(device_id: str, lifecycle: str):
    """Transition a device to a new lifecycle state."""
    reg = get_device_registry()
    try:
        return reg.transition(device_id, lifecycle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/registry/{device_id}/authorize")
def authorize_device(device_id: str, authorized_by: str):
    """Authorize a quarantined device."""
    reg = get_device_registry()
    try:
        return reg.authorize(device_id, authorized_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/registry-stats")
def device_registry_stats():
    """Get device counts by lifecycle state."""
    reg = get_device_registry()
    return reg.get_stats()


# ---------------------------------------------------------------------------
# Artifact Deployer (M3)
# ---------------------------------------------------------------------------

@router.post("/deployments", status_code=201)
def deploy_artifact(device_id: str, artifact_hash: str,
                    artifact_type: str = "apk"):
    """Deploy an artifact to a device."""
    deployer = get_artifact_deployer()
    return deployer.deploy(device_id=device_id, artifact_hash=artifact_hash,
                           artifact_type=artifact_type)


@router.get("/deployments")
def list_deployments(device_id: str | None = None, limit: int = 100):
    """List deployments with optional device filter."""
    deployer = get_artifact_deployer()
    return {"deployments": deployer.list_deployments(device_id=device_id,
                                                     limit=limit)}


@router.get("/deployments/{deploy_id}")
def get_deployment(deploy_id: str):
    """Get a single deployment by ID."""
    deployer = get_artifact_deployer()
    dep = deployer.get(deploy_id)
    if not dep:
        raise HTTPException(status_code=404, detail=f"Deployment {deploy_id} not found")
    return dep


@router.post("/deployments/{deploy_id}/rollback")
def rollback_deployment(deploy_id: str):
    """Rollback a deployment."""
    deployer = get_artifact_deployer()
    result = deployer.rollback(deploy_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Deployment {deploy_id} not found")
    return result


@router.post("/deployments/dry-run")
def dry_run_deployment(device_id: str, artifact_hash: str):
    """Validate a deployment without actually deploying."""
    deployer = get_artifact_deployer()
    return deployer.dry_run(device_id=device_id, artifact_hash=artifact_hash)


# ---------------------------------------------------------------------------
# On-Device Test Harness (M4)
# ---------------------------------------------------------------------------

@router.post("/tests", status_code=201)
def run_device_test(device_id: str, suite: str = "contract"):
    """Run a test suite on a device."""
    harness = get_on_device_test_harness()
    return harness.run_test(device_id=device_id, suite=suite)


@router.get("/tests")
def list_device_tests(device_id: str | None = None, limit: int = 100):
    """List device tests with optional device filter."""
    harness = get_on_device_test_harness()
    return {"tests": harness.list_tests(device_id=device_id, limit=limit)}


@router.get("/tests/{test_id}")
def get_device_test(test_id: str):
    """Get a single test result by ID."""
    harness = get_on_device_test_harness()
    result = harness.get_results(test_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")
    return result


@router.get("/tests/{device_id}/stats")
def device_test_stats(device_id: str):
    """Get aggregate test statistics for a device."""
    harness = get_on_device_test_harness()
    return harness.get_stats(device_id)
