"""Regression locks for features merged from audit/w14-production-readiness.

Sprint 1 had a moment when v2 cron-mode work on advisor-etap1 didn't include
the F-016/F-020..F-026 features (file upload, Hetzner, OVH, perplexity). The
user reported this as "usunales..." — actually the branches just diverged.
Merge 656ac871 restored everything. These tests lock those features in.

If any of these tests starts failing, someone reverted a feature: don't
silently accept it — check git log and surface to operator.

Each test is a cheap grep-style presence check (NO HTML/AST parsing). The
goal is an early-warning tripwire on file-level deletions, not deep semantic
validation. Deeper behaviour is covered by route-level smoke tests elsewhere.
"""
from pathlib import Path

import pytest

# Path layout:
#   src/sylion-pipeline/tests/aeis_v2/test_*.py     (this file)
#   src/sylion-pipeline                              (parents[2])
#   src/                                             (parents[3])
#   src/sylion-frontend/src                          (frontend tree)
#   src/sylion-pipeline/sylion/api/*.py              (backend tree)
_HERE = Path(__file__).resolve()
FRONTEND_DIR = _HERE.parents[3] / "sylion-frontend" / "src"
PIPELINE_DIR = _HERE.parents[2]
BACKEND_API_DIR = PIPELINE_DIR / "sylion" / "api"


def _read_frontend(rel: str) -> str:
    p = FRONTEND_DIR / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _read_backend(rel: str) -> str:
    p = BACKEND_API_DIR / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Step2Providers — AI provider catalogue (F-026)
# ---------------------------------------------------------------------------


def test_step2providers_lists_perplexity():
    """F-026: Perplexity provider must be in Step2 wizard catalogue."""
    content = _read_frontend("components/wizard/Step2Providers.tsx")
    assert content, "Step2Providers.tsx must exist"
    lower = content.lower()
    assert "perplexity" in lower, (
        "Step2Providers.tsx must list perplexity (F-026 audit branch addition). "
        "If you removed it: check git log for the merge of audit/w14-production-readiness "
        "and restore the AI_PROVIDERS entry."
    )
    # Tighter: it should be in an AI_PROVIDERS-style entry, not just a comment.
    assert 'id: "perplexity"' in content or "id: 'perplexity'" in content, (
        "perplexity must be an AI_PROVIDERS list entry, not just text in a comment."
    )


def test_step2providers_lists_openrouter():
    """F-026: OpenRouter aggregator provider must remain in Step2 catalogue."""
    content = _read_frontend("components/wizard/Step2Providers.tsx")
    assert content, "Step2Providers.tsx must exist"
    assert "openrouter" in content.lower(), (
        "Step2Providers.tsx must list openrouter (F-026). Restore from "
        "audit/w14-production-readiness if missing."
    )
    assert 'id: "openrouter"' in content or "id: 'openrouter'" in content, (
        "openrouter must be an AI_PROVIDERS list entry."
    )


# ---------------------------------------------------------------------------
# Step2Providers — Hosting providers (F-022)
# ---------------------------------------------------------------------------


def test_step2providers_hosting_includes_hetzner():
    """F-022: Hetzner Cloud provider must remain in HOSTING_PROVIDERS."""
    content = _read_frontend("components/wizard/Step2Providers.tsx")
    assert content, "Step2Providers.tsx must exist"
    assert "hetzner" in content.lower(), (
        "Step2Providers.tsx must list hetzner hosting (F-022). It's one of the "
        "two European VPS providers added in audit/w14-production-readiness."
    )
    assert 'id: "hetzner"' in content or "id: 'hetzner'" in content, (
        "hetzner must be a HOSTING_PROVIDERS list entry, not just a comment."
    )


def test_step2providers_hosting_includes_ovh():
    """F-022: OVHcloud provider must remain in HOSTING_PROVIDERS with all 4 fields."""
    content = _read_frontend("components/wizard/Step2Providers.tsx")
    assert content, "Step2Providers.tsx must exist"
    lower = content.lower()
    assert "ovh" in lower, (
        "Step2Providers.tsx must list OVH hosting (F-022). Restore from "
        "audit/w14-production-readiness if missing."
    )
    assert 'id: "ovh"' in content or "id: 'ovh'" in content, (
        "ovh must be a HOSTING_PROVIDERS list entry."
    )
    # OVH requires the OAuth-style 3-key setup (application_key/secret/consumer).
    # If any of those is missing, the OAuth flow is broken.
    for required_field in ("application_key", "application_secret", "consumer_key"):
        assert required_field in content, (
            f"OVH HOSTING_PROVIDERS entry must define '{required_field}' field "
            f"(part of OVH's OAuth-style 3-key auth)."
        )


# ---------------------------------------------------------------------------
# File upload UI (F-016) — three modal entry points
# ---------------------------------------------------------------------------


def test_step10firstidea_has_file_upload_dropzone():
    """F-016: Step10FirstIdea wizard must have file upload (dropzone + handler)."""
    content = _read_frontend("components/wizard/Step10FirstIdea.tsx")
    assert content, "Step10FirstIdea.tsx must exist"
    lower = content.lower()
    assert "dropzone" in lower or 'type="file"' in content, (
        "Step10FirstIdea.tsx must contain a file dropzone or file input "
        "(F-016 attachments). Test-id 'step10-attachment-dropzone' was the marker."
    )
    assert "handlefileupload" in lower, (
        "Step10FirstIdea.tsx must define handleFileUpload (F-016 upload handler)."
    )
    assert "/workspace/ideas/upload" in content, (
        "Step10FirstIdea.tsx must POST to /api/v1/workspace/ideas/upload (F-016)."
    )


def test_create_idea_modal_has_file_upload():
    """F-016: create-idea-modal must support file attachments."""
    content = _read_frontend("components/idea-vault/create-idea-modal.tsx")
    assert content, "create-idea-modal.tsx must exist"
    lower = content.lower()
    assert "handlefileupload" in lower, (
        "create-idea-modal.tsx must define handleFileUpload (F-016 file upload)."
    )
    assert 'type="file"' in content, (
        'create-idea-modal.tsx must contain an <input type="file"> for attachments.'
    )
    assert "/workspace/ideas/upload" in content, (
        "create-idea-modal.tsx must POST to /api/v1/workspace/ideas/upload."
    )


def test_new_project_modal_has_file_upload():
    """F-016: NewProjectModal (advisor) must support file attachments on draft."""
    content = _read_frontend("components/advisor/NewProjectModal.tsx")
    assert content, "NewProjectModal.tsx must exist"
    lower = content.lower()
    assert "handlefileupload" in lower, (
        "NewProjectModal.tsx must define handleFileUpload (F-016 file upload)."
    )
    assert 'type="file"' in content, (
        'NewProjectModal.tsx must contain an <input type="file"> for attachments.'
    )
    # NewProjectModal uses the projectsApi wrapper rather than direct fetch.
    assert "uploadIdeaFile" in content or "/workspace/ideas/upload" in content, (
        "NewProjectModal.tsx must call uploadIdeaFile (or hit /workspace/ideas/upload directly)."
    )


# ---------------------------------------------------------------------------
# Local LLM runtimes — backend dispatch (advisor-etap1 specific addition)
# ---------------------------------------------------------------------------


def test_ai_providers_dispatch_includes_lmstudio_vllm_llamacpp():
    """advisor-etap1: lmstudio/vllm/llamacpp must remain in DISPATCH dict.

    Cross-file regression check — these three local-runtime providers were
    added on advisor-etap1 and would silently disappear if the dispatch
    table got reverted.
    """
    content = _read_backend("ai_providers_routes.py")
    assert content, "ai_providers_routes.py must exist"
    # Look for the DISPATCH dict body.
    assert "DISPATCH = {" in content, (
        "ai_providers_routes.py must declare a DISPATCH dispatch dict."
    )
    for runtime in ("lmstudio", "vllm", "llamacpp"):
        # Must appear as a string key plus a callable.
        marker = f'"{runtime}": _call_{runtime}'
        assert marker in content, (
            f"DISPATCH must include '{marker}' — the {runtime} local-runtime "
            f"backend was added on advisor-etap1 and must not regress."
        )


def test_ai_providers_local_runtime_constants():
    """advisor-etap1: DEFAULT_MODELS + ENV_KEYS must declare lmstudio/vllm/llamacpp."""
    content = _read_backend("ai_providers_routes.py")
    assert content, "ai_providers_routes.py must exist"
    # Both tables must mention all three runtimes.
    for runtime in ("lmstudio", "vllm", "llamacpp"):
        assert f'"{runtime}":' in content, (
            f"ai_providers_routes.py must define '{runtime}' in DEFAULT_MODELS and ENV_KEYS."
        )
    # ENV_KEYS specifically names the env-var override per runtime.
    for env_var in ("LMSTUDIO_BASE_URL", "VLLM_BASE_URL", "LLAMACPP_BASE_URL"):
        assert env_var in content, (
            f"ai_providers_routes.py must reference {env_var} (local-runtime base URL override)."
        )
    # And the LOCAL_PROVIDERS frozenset must enumerate all three.
    assert "LOCAL_PROVIDERS" in content, (
        "ai_providers_routes.py must define LOCAL_PROVIDERS frozenset."
    )


def test_ai_providers_local_runtime_readiness_is_not_key_only():
    """Local runtimes need a reachable daemon, not only a no-key marker."""
    backend = _read_backend("ai_providers_routes.py")
    frontend = _read_frontend("app/(app)/ai-models/page.tsx")
    assert "_local_runtime_reachable" in backend, (
        "Local LM Studio/vLLM/llama.cpp rows must probe daemon reachability; "
        "otherwise the UI can mark offline runtimes as GOTOWY."
    )
    assert '"runtime_reachable": runtime_reachable' in backend
    assert 'RUNTIME OFFLINE' in frontend, (
        "AI Models dashboard must show RUNTIME OFFLINE for local runtimes "
        "that do not answer on their base URL."
    )


def test_vault_routes_use_keyvault_return_contract():
    """Vault activation routes must follow KeyVault's activated/deactivated fields."""
    content = _read_backend("vault_routes.py")
    assert 'result.get("activated")' in content
    assert 'result.get("deactivated")' in content
    assert 'result.get("success")' not in content, (
        "KeyVault.activate_key/deactivate_key do not return success; using it "
        "breaks the dashboard's Aktywuj flow."
    )


# ---------------------------------------------------------------------------
# v2 router wiring — guards against test_federation_cost_cap_runtime regression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "router_module,router_alias",
    [
        ("role_catalog_routes", "role_catalog_router"),
        ("ontology_routes", "ontology_v2_router"),
        ("terminal_routes", "terminal_v2_router"),
        ("federation_routes", "federation_v2_router"),
        ("apps_routes", "apps_v2_router"),
        ("policy_routes", "policy_v2_router"),
    ],
)
def test_app_includes_v2_routers(router_module: str, router_alias: str):
    """Verify app.py imports + mounts all 6 v2 routers.

    Earlier today a regression in test_federation_cost_cap_runtime was traced
    to a missing router include — this test now guards every v2 router import
    AND the corresponding include_router() call.
    """
    content = _read_backend("app.py")
    assert content, "app.py must exist"
    # Import line.
    import_line = f"from sylion.api.{router_module} import router as {router_alias}"
    assert import_line in content, (
        f"app.py must import the v2 router via:\n  {import_line}\n"
        f"If missing, this will silently break {router_alias} routes."
    )
    # Include line.
    include_line = f"app.include_router({router_alias})"
    assert include_line in content, (
        f"app.py must mount the router via:\n  {include_line}\n"
        f"Without include_router(), the router is loaded but unreachable via REST."
    )
