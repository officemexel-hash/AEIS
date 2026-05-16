"""SYLION AEIS security profiles for different environments."""
from dataclasses import dataclass, field

@dataclass
class SecurityProfile:
    name: str
    auth_mode: str = "bootstrap"  # bootstrap, token, mTLS
    audit_level: str = "basic"  # none, basic, full
    exec_guard: str = "off"  # off, warn, enforce
    secret_rotation_days: int = 90
    rate_limit: int = 1000
    allowed_origins: list = field(default_factory=lambda: ["*"])
    encryption_at_rest: bool = False
    signing_enabled: bool = False
    policy_enforcement: str = "advisory"  # advisory, strict
    session_timeout: int = 3600
    max_concurrent_sessions: int = 10

PROFILES = {
    "dev-light": SecurityProfile(
        name="dev-light",
        auth_mode="bootstrap",
        audit_level="basic",
        exec_guard="off",
        rate_limit=10000,
        session_timeout=86400,
    ),
    "test-light": SecurityProfile(
        name="test-light",
        auth_mode="token",
        audit_level="basic",
        exec_guard="warn",
        rate_limit=5000,
        session_timeout=7200,
    ),
    "staging-strict": SecurityProfile(
        name="staging-strict",
        auth_mode="token",
        audit_level="full",
        exec_guard="enforce",
        rate_limit=1000,
        encryption_at_rest=True,
        signing_enabled=True,
        policy_enforcement="strict",
        session_timeout=3600,
    ),
    "prod-strict": SecurityProfile(
        name="prod-strict",
        auth_mode="mTLS",
        audit_level="full",
        exec_guard="enforce",
        secret_rotation_days=30,
        rate_limit=500,
        allowed_origins=["https://sylion.aeis"],
        encryption_at_rest=True,
        signing_enabled=True,
        policy_enforcement="strict",
        session_timeout=1800,
        max_concurrent_sessions=3,
    ),
}

def get_profile(name: str) -> SecurityProfile:
    return PROFILES.get(name, PROFILES["dev-light"])

def list_profiles() -> dict:
    return {name: {"name": p.name, "auth_mode": p.auth_mode, "audit_level": p.audit_level, "exec_guard": p.exec_guard} for name, p in PROFILES.items()}
