"""
SYLION API -- Evidence Signing routes.

Endpoints for the EvidenceSigner module:
  generate_key, revoke_key, sign_evidence, verify_signature,
  list_signed_evidence, get_signing_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/security/evidence", tags=["Evidence Signing"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_evidence_signer = None


def _get_evidence_signer():
    global _evidence_signer
    if _evidence_signer is not None:
        return _evidence_signer
    from sylion.security.evidence_signer import get_evidence_signer
    _evidence_signer = get_evidence_signer()
    return _evidence_signer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateKeyRequest(BaseModel):
    alias: str
    key_type: str = "hmac_sha256"


class RevokeKeyRequest(BaseModel):
    key_id: str


class SignEvidenceRequest(BaseModel):
    key_id: str
    evidence_id: str
    data_json: str


class VerifySignatureRequest(BaseModel):
    signed_id: str


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

@router.post("/keys/generate", status_code=201)
def generate_key(body: GenerateKeyRequest):
    """Generate a new signing key with the given alias."""
    signer = _get_evidence_signer()
    try:
        return signer.generate_key(alias=body.alias, key_type=body.key_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/keys/revoke")
def revoke_key(body: RevokeKeyRequest):
    """Revoke a signing key by key_id."""
    signer = _get_evidence_signer()
    revoked = signer.revoke_key(body.key_id)
    if not revoked:
        raise HTTPException(status_code=404,
                            detail=f"Key {body.key_id} not found or already revoked")
    return {"revoked": True, "key_id": body.key_id}


# ---------------------------------------------------------------------------
# Signing and verification
# ---------------------------------------------------------------------------

@router.post("/sign", status_code=201)
def sign_evidence(body: SignEvidenceRequest):
    """Sign evidence data with the specified key."""
    signer = _get_evidence_signer()
    try:
        return signer.sign_evidence(
            key_id=body.key_id,
            evidence_id=body.evidence_id,
            data_json=body.data_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify")
def verify_signature(body: VerifySignatureRequest):
    """Verify a signature by signed_id."""
    signer = _get_evidence_signer()
    return signer.verify_signature(body.signed_id)


# ---------------------------------------------------------------------------
# Querying -- static paths before dynamic /{...} paths
# ---------------------------------------------------------------------------

@router.get("/signed")
def list_signed_evidence(
    evidence_id: str | None = None,
    limit: int = 100,
):
    """List signed evidence, optionally filtered by evidence_id."""
    signer = _get_evidence_signer()
    results = signer.list_signed_evidence(evidence_id=evidence_id, limit=limit)
    return {"signed": results, "count": len(results)}


@router.get("/stats")
def get_signing_stats():
    """Return summary statistics for signing keys and signed evidence."""
    signer = _get_evidence_signer()
    return signer.get_signing_stats()
