"""Mobile Field Inspector — D4 demo project.

Domain: field operations.
Operator captures inspections with photo + GPS + signature, queues offline
when no connectivity, syncs when reconnects.

Per docs/w14_workplan/demo_projects/manifests/01-mobile_field_inspector.yaml
Domain-specific human errors validated:
  - lost_connectivity_during_approval (stale_data_action, D3)
  - gps_spoofing_attempt (wrong_context, D4)
  - photo_evidence_corruption_unverified (premature_action, D3)
"""
from sylion.demo.mobile_field_inspector.models import (
    FieldInspection, GpsCoord, InspectionStatus, OfflineQueueEntry,
    PhotoEvidence, SignatureEvidence,
)
from sylion.demo.mobile_field_inspector.service import InspectorService
from sylion.demo.mobile_field_inspector.store import InspectorStore

__all__ = [
    "FieldInspection", "GpsCoord", "InspectionStatus",
    "OfflineQueueEntry", "PhotoEvidence", "SignatureEvidence",
    "InspectorService", "InspectorStore",
]
