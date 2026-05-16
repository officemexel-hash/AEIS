"""Tests for SYLION KeyVault + PromptTemplateManager — security keys and prompt templates."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sylion.security.key_vault import KeyVault, get_key_vault, reset_key_vault
from sylion.cognitive.prompt_templates import (
    PromptTemplateManager,
    get_prompt_template_manager,
    reset_prompt_template_manager,
)
from sylion.core.event_bus import SylionEvent


# =====================================================================
# Fixtures
# =====================================================================

class _FakeEventBus:
    """Minimal event bus stub that absorbs any emit() or publish() call."""
    def emit(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        return ""


@pytest.fixture(autouse=True)
def _reset_singletons():
    reset_key_vault()
    reset_prompt_template_manager()
    yield
    reset_key_vault()
    reset_prompt_template_manager()


@pytest.fixture
def vault(tmp_path):
    db_file = str(tmp_path / "key_vault_test.db")
    return KeyVault(db_path=db_file, event_bus=_FakeEventBus(), vault_secret="test")


@pytest.fixture
def ptm(tmp_path):
    db_file = str(tmp_path / "prompt_templates_test.db")
    return PromptTemplateManager(event_bus=_FakeEventBus(), db_path=db_file)


# =====================================================================
# KeyVault — TestStoreKey
# =====================================================================

class TestStoreKey:

    def test_store_returns_key_id(self, vault):
        result = vault.store_key("openai", "sk-test-123", display_name="main-key")
        assert "key_id" in result
        assert result["key_id"] != ""
        assert result["provider"] == "openai"
        assert result["display_name"] == "main-key"

    def test_store_encrypts_key(self, vault):
        result = vault.store_key("openai", "sk-secret-key", display_name="enc-test")
        decrypted = vault.get_decrypted_key(result["key_id"])
        assert decrypted == "sk-secret-key"

    def test_store_anthropic(self, vault):
        result = vault.store_key("anthropic", "sk-ant-api-key-xyz")
        assert result["provider"] == "anthropic"

    def test_store_openai(self, vault):
        result = vault.store_key("openai", "sk-oai-abc123")
        assert result["provider"] == "openai"


# =====================================================================
# KeyVault — TestDecryptKey
# =====================================================================

class TestDecryptKey:

    def test_decrypt_roundtrip(self, vault):
        stored = vault.store_key("test", "my-secret-value")
        decrypted = vault.get_decrypted_key(stored["key_id"])
        assert decrypted == "my-secret-value"

    def test_decrypt_nonexistent(self, vault):
        result = vault.get_decrypted_key("nonexistent-id")
        assert result is None


# =====================================================================
# KeyVault — TestListKeys
# =====================================================================

class TestListKeys:

    def test_list_empty(self, vault):
        keys = vault.list_keys()
        assert keys == []

    def test_list_after_store(self, vault):
        vault.store_key("openai", "sk-1")
        vault.store_key("anthropic", "sk-ant-2")
        keys = vault.list_keys()
        assert len(keys) == 2

    def test_list_filter_by_provider(self, vault):
        vault.store_key("openai", "sk-o1")
        vault.store_key("openai", "sk-o2")
        vault.store_key("anthropic", "sk-a1")
        openai_keys = vault.list_keys(provider="openai")
        assert len(openai_keys) == 2
        anthropic_keys = vault.list_keys(provider="anthropic")
        assert len(anthropic_keys) == 1


# =====================================================================
# KeyVault — TestActivateDeactivate
# =====================================================================

class TestActivateDeactivate:

    def test_activate(self, vault):
        stored = vault.store_key("test", "sk-abc")
        result = vault.activate_key(stored["key_id"])
        assert result is not None

    def test_deactivate(self, vault):
        stored = vault.store_key("test", "sk-xyz")
        result = vault.deactivate_key(stored["key_id"])
        assert result is not None


# =====================================================================
# KeyVault — TestValidateKey
# =====================================================================

class TestValidateKey:

    def test_validate_active_key(self, vault):
        stored = vault.store_key("openai", "sk-real-key")
        result = vault.validate_key(stored["key_id"])
        assert "valid" in result

    def test_validate_invalid_format(self, vault):
        stored = vault.store_key("openai", "wrong-prefix")
        result = vault.validate_key(stored["key_id"])
        assert "valid" in result


# =====================================================================
# KeyVault — TestHierarchy
# =====================================================================

class TestHierarchy:

    def test_save_hierarchy(self, vault):
        result = vault.save_hierarchy(
            name="Standard",
            levels=[
                {"level": 1, "model_id": "gpt-3.5", "task_types": ["chat"]},
                {"level": 2, "model_id": "gpt-4", "task_types": ["reasoning"]},
                {"level": 3, "model_id": "gpt-4-turbo", "task_types": ["premium"]},
            ],
        )
        assert "hierarchy_id" in result
        assert result["name"] == "Standard"

    def test_get_hierarchy(self, vault):
        saved = vault.save_hierarchy("H1", [
            {"level": 1, "model_id": "gpt-4", "task_types": ["reasoning"]},
        ])
        fetched = vault.get_hierarchy(saved["hierarchy_id"])
        assert fetched is not None
        assert fetched["name"] == "H1"

    def test_list_hierarchies(self, vault):
        vault.save_hierarchy("H1", [])
        vault.save_hierarchy("H2", [])
        hierarchies = vault.list_hierarchies()
        assert len(hierarchies) == 2


# =====================================================================
# KeyVault — TestCouncilMembers
# =====================================================================

class TestCouncilMembers:

    def test_configure_member(self, vault):
        result = vault.configure_council_member(
            member_id="analyst-1",
            model_id="gpt-4",
            role="analyst",
            priority=5,
        )
        assert result["model_id"] == "gpt-4"
        assert result["role"] == "analyst"

    def test_list_members(self, vault):
        vault.configure_council_member("m1", "gpt-4", "analyst", 1)
        vault.configure_council_member("m2", "gpt-3.5", "reviewer", 2)
        members = vault.list_council_members()
        assert len(members) == 2

    def test_remove_member(self, vault):
        result = vault.configure_council_member("m1", "gpt-4", "analyst", 1)
        assert vault.remove_council_member("m1") is True


# =====================================================================
# KeyVault — TestSingleton
# =====================================================================

class TestKeyVaultSingleton:

    def test_get_returns_instance(self, tmp_path):
        v = get_key_vault(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_kv.db"))
        assert isinstance(v, KeyVault)

    def test_idempotent(self, tmp_path):
        v1 = get_key_vault(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_kv.db"))
        v2 = get_key_vault(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_kv.db"))
        assert v1 is v2

    def test_reset_clears(self, tmp_path):
        v1 = get_key_vault(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_kv.db"))
        reset_key_vault()
        v2 = get_key_vault(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_kv2.db"))
        assert v1 is not v2


# =====================================================================
# PromptTemplateManager — TestCreateTemplate
# =====================================================================

class TestCreateTemplate:

    def test_create_basic(self, ptm):
        result = ptm.create_template(
            name="Summarize",
            content="Summarize the following: {text}",
            category="utility",
        )
        assert "template_id" in result
        assert result["name"] == "Summarize"
        assert result["category"] == "utility"
        assert result["version"] == 1

    def test_create_extracts_variables(self, ptm):
        result = ptm.create_template(
            name="MultiVar",
            content="Hello {name}, your role is {role} in {team}.",
            category="test",
        )
        assert "variables" in result
        assert sorted(result["variables"]) == ["name", "role", "team"]

    def test_create_with_team_project(self, ptm):
        result = ptm.create_template(
            name="Scoped",
            content="Hello {user}",
            category="test",
            team_id="team-a",
            project_id="proj-1",
        )
        assert result["team_id"] == "team-a"
        assert result["project_id"] == "proj-1"


# =====================================================================
# PromptTemplateManager — TestUpdateTemplate
# =====================================================================

class TestUpdateTemplate:

    def test_update_bumps_version(self, ptm):
        created = ptm.create_template(
            name="V1",
            content="Original {x}",
            category="test",
        )
        assert created["version"] == 1
        updated = ptm.update_template(created["template_id"], content="Updated {x} and {y}")
        assert updated["version"] == 2

    def test_update_re_extracts_variables(self, ptm):
        created = ptm.create_template(
            name="Vars",
            content="Hello {name}",
            category="test",
        )
        updated = ptm.update_template(
            created["template_id"],
            content="Hello {name}, welcome to {project}!",
        )
        assert sorted(updated["variables"]) == ["name", "project"]


# =====================================================================
# PromptTemplateManager — TestGetTemplate
# =====================================================================

class TestGetTemplate:

    def test_get_existing(self, ptm):
        created = ptm.create_template(
            name="Fetch",
            content="Content here {x}",
            category="test",
        )
        fetched = ptm.get_template(created["template_id"])
        assert fetched is not None
        assert fetched["name"] == "Fetch"
        assert fetched["content"] == "Content here {x}"

    def test_get_nonexistent(self, ptm):
        result = ptm.get_template("no-such-template")
        assert result is None


# =====================================================================
# PromptTemplateManager — TestListTemplates
# =====================================================================

class TestListTemplates:

    def test_list_empty(self, ptm):
        result = ptm.list_templates()
        assert result == []

    def test_list_after_create(self, ptm):
        ptm.create_template("T1", "Hello", category="cat-a")
        ptm.create_template("T2", "World", category="cat-b")
        templates = ptm.list_templates()
        assert len(templates) == 2

    def test_list_filter_by_category(self, ptm):
        ptm.create_template("T1", "Think {topic}", category="reasoning")
        ptm.create_template("T2", "Summarize {text}", category="utility")
        ptm.create_template("T3", "Analyze {data}", category="reasoning")
        reasoning = ptm.list_templates(category="reasoning")
        assert len(reasoning) == 2
        utility = ptm.list_templates(category="utility")
        assert len(utility) == 1


# =====================================================================
# PromptTemplateManager — TestResolveTemplate
# =====================================================================

class TestResolveTemplate:

    def test_resolve_substitutes_variables(self, ptm):
        created = ptm.create_template(
            name="Greet",
            content="Hello {name}, welcome to {project}!",
            category="test",
        )
        resolved = ptm.resolve_template(
            created["template_id"],
            {"name": "Alice", "project": "SYLION"},
        )
        assert resolved == "Hello Alice, welcome to SYLION!"

    def test_resolve_missing_key_raises(self, ptm):
        created = ptm.create_template(
            name="Partial",
            content="Hello {name} from {city}!",
            category="test",
        )
        with pytest.raises(ValueError, match="Missing required"):
            ptm.resolve_template(created["template_id"], {"name": "Bob"})


# =====================================================================
# PromptTemplateManager — TestDeleteTemplate
# =====================================================================

class TestDeleteTemplate:

    def test_delete_soft(self, ptm):
        created = ptm.create_template(
            name="ToDelete",
            content="Bye {name}",
            category="test",
        )
        result = ptm.delete_template(created["template_id"])
        assert result is True

    def test_deleted_not_in_list(self, ptm):
        created = ptm.create_template(
            name="Gone",
            content="Vanish {x}",
            category="test",
        )
        ptm.delete_template(created["template_id"])
        templates = ptm.list_templates(is_active=1)
        assert len(templates) == 0

    def test_deleted_still_in_get_but_inactive(self, ptm):
        created = ptm.create_template(
            name="Ghost",
            content="Boo",
            category="test",
        )
        ptm.delete_template(created["template_id"])
        fetched = ptm.get_template(created["template_id"])
        assert fetched is not None
        assert fetched["is_active"] == 0


# =====================================================================
# PromptTemplateManager — TestImportExport
# =====================================================================

class TestImportExport:

    def test_export_and_import(self, ptm):
        created = ptm.create_template(
            name="Export",
            content="Test {x}",
            category="test",
        )
        exported = ptm.export_template(created["template_id"])
        data = json.loads(exported)
        assert data["name"] == "Export"

    def test_import_creates_new(self, ptm):
        json_str = json.dumps({"name": "Imported", "content": "Hello {x}"})
        result = ptm.import_template(json_str)
        assert result["name"] == "Imported"

    def test_import_empty_raises(self, ptm):
        with pytest.raises(ValueError):
            ptm.import_template("{}")


# =====================================================================
# PromptTemplateManager — TestSingleton
# =====================================================================

class TestPromptTemplateManagerSingleton:

    def test_get_returns_instance(self, tmp_path):
        m = get_prompt_template_manager(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_ptm.db"))
        assert isinstance(m, PromptTemplateManager)

    def test_idempotent(self, tmp_path):
        m1 = get_prompt_template_manager(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_ptm.db"))
        m2 = get_prompt_template_manager(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_ptm.db"))
        assert m1 is m2

    def test_reset_clears(self, tmp_path):
        m1 = get_prompt_template_manager(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_ptm.db"))
        reset_prompt_template_manager()
        m2 = get_prompt_template_manager(event_bus=_FakeEventBus(), db_path=str(tmp_path / "singleton_ptm2.db"))
        assert m1 is not m2
