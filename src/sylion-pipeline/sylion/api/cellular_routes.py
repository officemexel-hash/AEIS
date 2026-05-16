"""
SYLION API -- Cellular routes.

Endpoints for: ran_lab, core_network, ue_emulator, rf_isolation,
attack_vectors, control_plane, evidence_writer.
"""

from fastapi import APIRouter, HTTPException

from sylion.cellular.ran_lab import get_ran_lab
from sylion.cellular.core_network import get_core_network_emulator
from sylion.cellular.ue_emulator import get_ue_emulator
from sylion.cellular.rf_isolation import get_rf_isolation_validator
from sylion.cellular.attack_vectors import get_attack_vector_library
from sylion.cellular.control_plane import get_control_plane_analyzer
from sylion.cellular.evidence_writer import get_cellular_evidence_writer

router = APIRouter(prefix="/api/v1/cellular", tags=["cellular"])


# ---------------------------------------------------------------------------
# RAN Lab Orchestrator (O1)
# ---------------------------------------------------------------------------

@router.post("/ran", status_code=201)
def create_ran_stack(technology: str, stack_name: str = '',
                     frequency: float = 0, power_dbm: float = -30,
                     plmn_mcc: str = '001', plmn_mnc: str = '01',
                     isolation_mode: str = 'conducted'):
    """Create a new RAN stack."""
    lab = get_ran_lab()
    return lab.create_stack(technology=technology, stack_name=stack_name,
                            frequency=frequency, power_dbm=power_dbm,
                            plmn_mcc=plmn_mcc, plmn_mnc=plmn_mnc,
                            isolation_mode=isolation_mode)


@router.get("/ran")
def list_ran_stacks(status: str | None = None, limit: int = 100):
    """List RAN stacks with optional status filter."""
    lab = get_ran_lab()
    return {"stacks": lab.list_stacks(status=status, limit=limit)}


@router.get("/ran/{stack_id}")
def get_ran_stack(stack_id: str):
    """Get a RAN stack by ID."""
    lab = get_ran_lab()
    stack = lab.get(stack_id)
    if not stack:
        raise HTTPException(status_code=404, detail=f"RAN stack {stack_id} not found")
    return stack


@router.post("/ran/{stack_id}/start")
def start_ran_stack(stack_id: str):
    """Start a RAN stack."""
    lab = get_ran_lab()
    return lab.start(stack_id)


@router.post("/ran/{stack_id}/stop")
def stop_ran_stack(stack_id: str):
    """Stop a RAN stack."""
    lab = get_ran_lab()
    return lab.stop(stack_id)


# ---------------------------------------------------------------------------
# Core Network Emulator (O2)
# ---------------------------------------------------------------------------

@router.post("/cores", status_code=201)
def create_core(technology: str, stack_name: str = '',
                has_internet: bool = False):
    """Create a new core network emulator."""
    cn = get_core_network_emulator()
    return cn.create(technology=technology, stack_name=stack_name,
                     has_internet=has_internet)


@router.get("/cores")
def list_cores(status: str | None = None, limit: int = 100):
    """List core network emulators."""
    cn = get_core_network_emulator()
    return {"cores": cn.list_cores(status=status, limit=limit)}


@router.get("/cores/{core_id}")
def get_core(core_id: str):
    """Get a core network by ID."""
    cn = get_core_network_emulator()
    core = cn.get(core_id)
    if not core:
        raise HTTPException(status_code=404, detail=f"Core {core_id} not found")
    return core


@router.post("/cores/{core_id}/start")
def start_core(core_id: str):
    """Start a core network emulator."""
    cn = get_core_network_emulator()
    return cn.start(core_id)


@router.post("/cores/{core_id}/stop")
def stop_core(core_id: str):
    """Stop a core network emulator."""
    cn = get_core_network_emulator()
    return cn.stop(core_id)


# ---------------------------------------------------------------------------
# UE Emulator (O3)
# ---------------------------------------------------------------------------

@router.post("/ue", status_code=201)
def create_ue(stack_name: str = '', technology: str = '4G',
              imsi: str = ''):
    """Create a new UE emulator instance."""
    ue = get_ue_emulator()
    return ue.create(stack_name=stack_name, technology=technology,
                     imsi=imsi)


@router.get("/ue")
def list_ues(status: str | None = None, limit: int = 100):
    """List UE emulator instances."""
    ue = get_ue_emulator()
    return {"ues": ue.list_ues(status=status, limit=limit)}


@router.get("/ue/{ue_id}")
def get_ue(ue_id: str):
    """Get a UE by ID."""
    ue = get_ue_emulator()
    device = ue.get(ue_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"UE {ue_id} not found")
    return device


@router.post("/ue/{ue_id}/attach")
def attach_ue(ue_id: str, ran_id: str, core_id: str):
    """Attach a UE to RAN and core."""
    ue = get_ue_emulator()
    return ue.attach(ue_id, ran_id, core_id)


@router.post("/ue/{ue_id}/detach")
def detach_ue(ue_id: str):
    """Detach a UE."""
    ue = get_ue_emulator()
    return ue.detach(ue_id)


# ---------------------------------------------------------------------------
# RF Isolation Validator (O4)
# ---------------------------------------------------------------------------

@router.post("/isolation", status_code=201)
def validate_isolation(frequency: float, measurement_dbm: float,
                       monitor_sdr: str = '', harmonics: str = '[]'):
    """Validate RF isolation for an experiment frequency."""
    import json
    iso = get_rf_isolation_validator()
    harmonics_list = json.loads(harmonics) if isinstance(harmonics, str) else []
    return iso.validate(frequency=frequency, measurement_dbm=measurement_dbm,
                        monitor_sdr=monitor_sdr, harmonics=harmonics_list)


@router.get("/isolation")
def list_isolation_checks(limit: int = 50):
    """List isolation checks."""
    iso = get_rf_isolation_validator()
    return {"checks": iso.list_checks(limit=limit)}


@router.get("/isolation/latest")
def latest_isolation():
    """Get the latest isolation check."""
    iso = get_rf_isolation_validator()
    result = iso.latest()
    if not result:
        raise HTTPException(status_code=404, detail="No isolation checks found")
    return result


@router.get("/isolation/{check_id}")
def get_isolation_check(check_id: str):
    """Get an isolation check by ID."""
    iso = get_rf_isolation_validator()
    result = iso.get(check_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Check {check_id} not found")
    return result


@router.get("/isolation-valid")
def is_isolation_valid(frequency: float):
    """Check if latest isolation check for frequency is valid."""
    iso = get_rf_isolation_validator()
    return {"frequency": frequency, "valid": iso.is_valid(frequency)}


# ---------------------------------------------------------------------------
# Attack Vector Library (O5)
# ---------------------------------------------------------------------------

@router.post("/attack-vectors", status_code=201)
def register_attack_vector(vector_id: str, name: str,
                           technology: str = '4G',
                           decision_class: str = 'D3',
                           preconditions: str = '[]',
                           steps: str = '[]',
                           legal_basis: str = ''):
    """Register a new attack vector."""
    import json
    lib = get_attack_vector_library()
    pre_list = json.loads(preconditions) if isinstance(preconditions, str) else []
    steps_list = json.loads(steps) if isinstance(steps, str) else []
    return lib.register(vector_id=vector_id, name=name,
                        technology=technology,
                        decision_class=decision_class,
                        preconditions=pre_list,
                        steps=steps_list,
                        legal_basis=legal_basis)


@router.get("/attack-vectors")
def list_attack_vectors(technology: str | None = None,
                        lifecycle: str | None = None):
    """List attack vectors with optional filters."""
    lib = get_attack_vector_library()
    return {"vectors": lib.list_vectors(technology=technology,
                                         lifecycle=lifecycle)}


@router.get("/attack-vectors/{vector_id}")
def get_attack_vector(vector_id: str):
    """Get an attack vector by ID."""
    lib = get_attack_vector_library()
    result = lib.get(vector_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Attack vector {vector_id} not found")
    return result


@router.post("/attack-vectors/{vector_id}/publish")
def publish_attack_vector(vector_id: str):
    """Publish a draft attack vector."""
    lib = get_attack_vector_library()
    return lib.publish(vector_id)


@router.post("/attack-vectors/{vector_id}/deprecate")
def deprecate_attack_vector(vector_id: str):
    """Deprecate a published attack vector."""
    lib = get_attack_vector_library()
    return lib.deprecate(vector_id)


@router.get("/attack-vectors-stats")
def attack_vector_stats():
    """Get attack vector counts by lifecycle."""
    lib = get_attack_vector_library()
    return lib.get_stats()


# ---------------------------------------------------------------------------
# Control Plane Analyzer (O6)
# ---------------------------------------------------------------------------

@router.post("/control-plane/analyze", status_code=201)
def analyze_control_plane(pcap_source: str, technology: str = '4G',
                          protocol: str = ''):
    """Analyze a control plane PCAP."""
    cp = get_control_plane_analyzer()
    return cp.analyze(pcap_source=pcap_source, technology=technology,
                      protocol=protocol)


@router.get("/control-plane")
def list_cp_analyses(technology: str | None = None, limit: int = 100):
    """List control plane analyses."""
    cp = get_control_plane_analyzer()
    return {"analyses": cp.list_analyses(technology=technology, limit=limit)}


@router.get("/control-plane/{analysis_id}")
def get_cp_analysis(analysis_id: str):
    """Get a control plane analysis by ID."""
    cp = get_control_plane_analyzer()
    result = cp.get(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return result


@router.post("/control-plane/{analysis_id}/detect-anomalies")
def detect_cp_anomalies(analysis_id: str):
    """Run anomaly detection on a control plane analysis."""
    cp = get_control_plane_analyzer()
    return cp.detect_anomalies(analysis_id)


# ---------------------------------------------------------------------------
# Cellular Evidence Writer (O7)
# ---------------------------------------------------------------------------

@router.post("/evidence", status_code=201)
def write_evidence(evidence_id: str, experiment_id: str,
                   attack_vector: str = '', isolation: str = '{}',
                   governance: str = '{}', findings: str = '',
                   pcap_cp: str = '', pcap_up: str = '',
                   iq_recording: str = ''):
    """Write cellular experiment evidence."""
    import json
    ew = get_cellular_evidence_writer()
    iso_dict = json.loads(isolation) if isinstance(isolation, str) else {}
    gov_dict = json.loads(governance) if isinstance(governance, str) else {}
    return ew.write(evidence_id=evidence_id,
                    experiment_id=experiment_id,
                    attack_vector=attack_vector,
                    isolation=iso_dict,
                    governance=gov_dict,
                    findings=findings,
                    pcap_cp=pcap_cp, pcap_up=pcap_up,
                    iq_recording=iq_recording)


@router.get("/evidence")
def list_cellular_evidence(experiment_id: str | None = None,
                           limit: int = 100):
    """List cellular evidence records."""
    ew = get_cellular_evidence_writer()
    return {"evidence": ew.list_evidence(experiment_id=experiment_id,
                                          limit=limit)}


@router.get("/evidence/{evidence_id}")
def get_cellular_evidence(evidence_id: str):
    """Get a cellular evidence record by ID."""
    ew = get_cellular_evidence_writer()
    result = ew.get(evidence_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found")
    return result


@router.post("/evidence/{evidence_id}/validate")
def validate_cellular_evidence(evidence_id: str):
    """Validate cellular evidence completeness."""
    ew = get_cellular_evidence_writer()
    return ew.validate(evidence_id)
