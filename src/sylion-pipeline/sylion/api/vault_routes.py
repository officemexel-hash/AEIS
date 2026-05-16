"""
SYLION API -- Vault routes.

Endpoints for KeyVault:
  list_keys, store_key, decrypt_key, validate_key, activate_key,
  deactivate_key, delete_key.
"""

from fastapi import APIRouter, Depends, HTTPException

from sylion.security.key_vault import get_key_vault
from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/vault", tags=["Vault"])


@router.get("/keys")
def list_keys(provider: str | None = None, active_only: bool = True):
    """List keys in the vault, optionally filtered to active keys only."""
    vault = get_key_vault()
    keys = vault.list_keys(provider=provider)
    if active_only:
        keys = [k for k in keys if k.get("is_active") in (1, True)]
    return {"keys": keys}


@router.post("/keys", status_code=201)
def store_key(provider: str, key_value: str, display_name: str = "",
              _user: str = Depends(requires_role("owner", "security"))):
    """Store a new key in the vault. Owner/security only — secrets injection."""
    vault = get_key_vault()
    try:
        return vault.store_key(provider, key_value, display_name=display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/keys/{key_id}/decrypt")
def decrypt_key(key_id: str,
                _user: str = Depends(requires_role("owner", "security"))):
    """Decrypt a key. Owner/security only — returns plaintext secrets."""
    vault = get_key_vault()
    result = vault.get_decrypted_key(key_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Key {key_id} not found")
    return {"key_id": key_id, "decrypted_key": result}


@router.post("/keys/{key_id}/validate")
def validate_key(key_id: str):
    """Validate a key."""
    vault = get_key_vault()
    return vault.validate_key(key_id)


@router.post("/keys/{key_id}/activate")
def activate_key(key_id: str):
    """Activate a key."""
    vault = get_key_vault()
    result = vault.activate_key(key_id)
    if not result.get("activated"):
        raise HTTPException(status_code=404, detail=result.get("message", f"Key {key_id} not found"))
    return {"activated": True, "key_id": key_id}


@router.post("/keys/{key_id}/deactivate")
def deactivate_key(key_id: str):
    """Deactivate a key."""
    vault = get_key_vault()
    result = vault.deactivate_key(key_id)
    if not result.get("deactivated"):
        raise HTTPException(status_code=404, detail=result.get("message", f"Key {key_id} not found"))
    return {"deactivated": True, "key_id": key_id}


@router.delete("/keys/{key_id}")
def delete_key(key_id: str):
    """Delete a key."""
    vault = get_key_vault()
    ok = vault.delete_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Key {key_id} not found")
    return {"deleted": True, "key_id": key_id}
