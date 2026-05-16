"""
SYLION API -- SDR routes.

Endpoints for: sdr_gateway, capture_orchestrator, signal_analyzer,
protocol_decoder, rf_safety_governor.
"""

from fastapi import APIRouter, HTTPException

from sylion.sdr.sdr_gateway import get_sdr_gateway
from sylion.sdr.capture_orchestrator import get_capture_orchestrator
from sylion.sdr.signal_analyzer import get_signal_analyzer
from sylion.sdr.protocol_decoder import get_protocol_decoder
from sylion.sdr.rf_safety_governor import get_rf_safety_governor

router = APIRouter(prefix="/api/v1/sdr", tags=["sdr"])


# ---------------------------------------------------------------------------
# SDR Gateway (N1)
# ---------------------------------------------------------------------------

@router.post("/devices", status_code=201)
def register_sdr(sdr_id: str, device_type: str, driver: str = "soapysdr",
                 freq_min: float = 0, freq_max: float = 6e9,
                 sample_rate_max: float = 2e6, tx_capable: bool = False):
    """Register a new SDR device."""
    gw = get_sdr_gateway()
    return gw.register_sdr(sdr_id=sdr_id, device_type=device_type,
                           driver=driver, freq_min=freq_min,
                           freq_max=freq_max,
                           sample_rate_max=sample_rate_max,
                           tx_capable=tx_capable)


@router.get("/devices")
def list_sdrs(status: str | None = None):
    """List SDR devices with optional status filter."""
    gw = get_sdr_gateway()
    return {"devices": gw.list_sdrs(status=status)}


@router.get("/devices/{sdr_id}")
def get_sdr(sdr_id: str):
    """Get capabilities of a specific SDR device."""
    gw = get_sdr_gateway()
    caps = gw.get_capabilities(sdr_id)
    if not caps:
        raise HTTPException(status_code=404, detail=f"SDR {sdr_id} not found")
    return caps


@router.get("/devices/{sdr_id}/available")
def check_sdr_available(sdr_id: str):
    """Check if an SDR device is available."""
    gw = get_sdr_gateway()
    return {"sdr_id": sdr_id, "available": gw.check_available(sdr_id)}


@router.post("/devices/{sdr_id}/status")
def update_sdr_status(sdr_id: str, status: str):
    """Update SDR device status."""
    gw = get_sdr_gateway()
    result = gw.update_status(sdr_id, status)
    if not result:
        raise HTTPException(status_code=404, detail=f"SDR {sdr_id} not found")
    return result


# ---------------------------------------------------------------------------
# Capture Orchestrator (N2)
# ---------------------------------------------------------------------------

@router.post("/captures", status_code=201)
def create_capture(sdr_id: str, frequency: float,
                   sample_rate: float = 2e6, mode: str = "RX",
                   duration_s: float = 60):
    """Create a new capture session."""
    orch = get_capture_orchestrator()
    return orch.create_capture(sdr_id=sdr_id, frequency=frequency,
                               sample_rate=sample_rate, mode=mode,
                               duration_s=duration_s)


@router.get("/captures")
def list_captures(sdr_id: str | None = None, limit: int = 100):
    """List captures with optional SDR filter."""
    orch = get_capture_orchestrator()
    return {"captures": orch.list_captures(sdr_id=sdr_id, limit=limit)}


@router.get("/captures/{capture_id}")
def get_capture(capture_id: str):
    """Get a capture by ID."""
    orch = get_capture_orchestrator()
    cap = orch.get(capture_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")
    return cap


@router.post("/captures/{capture_id}/start")
def start_capture(capture_id: str):
    """Start a capture session."""
    orch = get_capture_orchestrator()
    return orch.start(capture_id)


@router.post("/captures/{capture_id}/stop")
def stop_capture(capture_id: str):
    """Stop a running capture."""
    orch = get_capture_orchestrator()
    return orch.stop(capture_id)


# ---------------------------------------------------------------------------
# Signal Analyzer (N3)
# ---------------------------------------------------------------------------

@router.post("/analysis/spectrum", status_code=201)
def analyze_spectrum(capture_id: str, fft_size: int = 4096):
    """Perform spectrum analysis on capture data."""
    sa = get_signal_analyzer()
    return sa.analyze_spectrum(capture_id=capture_id, fft_size=fft_size)


@router.post("/analysis/modulation", status_code=201)
def classify_modulation(capture_id: str):
    """Classify modulation of captured signal."""
    sa = get_signal_analyzer()
    return sa.classify_modulation(capture_id=capture_id)


@router.post("/analysis/detect", status_code=201)
def detect_signals(capture_id: str, threshold_db: float = -80):
    """Detect signals above threshold."""
    sa = get_signal_analyzer()
    return sa.detect_signals(capture_id=capture_id,
                             threshold_db=threshold_db)


@router.get("/analysis")
def list_analyses(capture_id: str | None = None, limit: int = 100):
    """List analysis results with optional capture filter."""
    sa = get_signal_analyzer()
    return {"analyses": sa.list_analyses(capture_id=capture_id, limit=limit)}


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str):
    """Get a single analysis result by ID."""
    sa = get_signal_analyzer()
    result = sa.get(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return result


# ---------------------------------------------------------------------------
# Protocol Decoder (N4)
# ---------------------------------------------------------------------------

@router.post("/decode", status_code=201)
def decode_protocol(capture_id: str, protocol: str):
    """Decode captured data for a given protocol."""
    dec = get_protocol_decoder()
    return dec.decode(capture_id=capture_id, protocol=protocol)


@router.get("/decodes")
def list_decodes(capture_id: str | None = None, limit: int = 100):
    """List decode results with optional capture filter."""
    dec = get_protocol_decoder()
    return {"decodes": dec.list_decodes(capture_id=capture_id, limit=limit)}


@router.get("/decodes/{decode_id}")
def get_decode(decode_id: str):
    """Get a single decode result by ID."""
    dec = get_protocol_decoder()
    result = dec.get(decode_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Decode {decode_id} not found")
    return result


@router.get("/protocols")
def list_protocols():
    """List supported protocols."""
    dec = get_protocol_decoder()
    return {"protocols": dec.list_protocols()}


# ---------------------------------------------------------------------------
# RF Safety Governor (N5)
# ---------------------------------------------------------------------------

@router.post("/rf/policies", status_code=201)
def add_band_policy(policy_id: str, jurisdiction: str,
                    band_start: float, band_end: float,
                    max_power_dbm: float = -10, tx_allowed: bool = False,
                    requires_council: bool = True):
    """Add or replace an RF band policy."""
    gov = get_rf_safety_governor()
    return gov.add_band_policy(policy_id=policy_id,
                               jurisdiction=jurisdiction,
                               band_start=band_start,
                               band_end=band_end,
                               max_power_dbm=max_power_dbm,
                               tx_allowed=tx_allowed,
                               requires_council=requires_council)


@router.get("/rf/policies")
def get_rf_policies(jurisdiction: str | None = None):
    """Get RF band policies."""
    gov = get_rf_safety_governor()
    return {"policies": gov.get_policies(jurisdiction=jurisdiction)}


@router.post("/rf/check-tx")
def check_tx_allowed(frequency: float, power_dbm: float,
                     jurisdiction: str = "PL"):
    """Check if TX is allowed at given frequency/power."""
    gov = get_rf_safety_governor()
    return gov.check_tx_allowed(frequency=frequency, power_dbm=power_dbm,
                                jurisdiction=jurisdiction)


@router.post("/rf/record-tx", status_code=201)
def record_tx(sdr_id: str, frequency: float, power_dbm: float,
              approved_by: str = ""):
    """Record a TX event."""
    gov = get_rf_safety_governor()
    return gov.record_tx(sdr_id=sdr_id, frequency=frequency,
                         power_dbm=power_dbm, approved_by=approved_by)


@router.post("/rf/enable-tx")
def enable_tx_global(enabled_by: str):
    """Enable global TX (requires Council approval)."""
    gov = get_rf_safety_governor()
    return gov.enable_tx_global(enabled_by=enabled_by)


@router.get("/rf/tx-enabled")
def is_tx_enabled():
    """Check if global TX is enabled."""
    gov = get_rf_safety_governor()
    return {"tx_enabled": gov.is_tx_enabled()}


@router.get("/rf/events")
def get_rf_events(sdr_id: str | None = None, limit: int = 100):
    """Get TX events."""
    gov = get_rf_safety_governor()
    return {"events": gov.get_events(sdr_id=sdr_id, limit=limit)}
