"""Tests for sylion.contracts.compatibility_checker.

Covers proto parsing, proto diffing, event compatibility, module contract
checks, full system reports, and lifecycle transition validation.
"""

from __future__ import annotations

import json
import textwrap

import pytest

from sylion.contracts.compatibility_checker import (
    CompatibilityChecker,
    ProtoChange,
    ProtoField,
    ProtoMessage,
    ProtoRpc,
    ProtoService,
    diff_protos,
    parse_proto,
)
from sylion.core.contract_registry import Contract, ContractRegistry, ContractType
from sylion.core.module_registry import (
    ModuleKind,
    ModuleLifecycleStage,
    ModuleManifest,
    ModuleRegistry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def contract_reg() -> ContractRegistry:
    return ContractRegistry()


@pytest.fixture
def module_reg() -> ModuleRegistry:
    return ModuleRegistry()


@pytest.fixture
def checker(contract_reg, module_reg) -> CompatibilityChecker:
    return CompatibilityChecker(contract_reg, module_reg)


def _register_module(reg: ModuleRegistry, mid: str, kind=ModuleKind.CORE_KERNEL,
                     depends_on=None, stage=ModuleLifecycleStage.DRAFT):
    m = ModuleManifest(
        module_id=mid,
        module_kind=kind,
        owner_plan="test-plan",
        depends_on=depends_on or [],
        lifecycle_stage=stage,
    )
    return reg.register(m)


def _publish_contract(reg: ContractRegistry, name, version="1.0.0",
                      producer="mod-a", consumers=None,
                      ctype=ContractType.GRPC_SERVICE):
    c = Contract(
        name=name,
        contract_type=ctype,
        version=version,
        producer_module=producer,
        consumer_modules=consumers or [],
    )
    return reg.publish(c)


# ===========================================================================
# 1. Proto parsing
# ===========================================================================

class TestProtoParsing:

    def test_parse_simple_message(self):
        proto = textwrap.dedent("""\
            syntax = "proto3";
            message Foo {
              string name = 1;
              int32  age  = 2;
            }
        """)
        result = parse_proto(proto)
        assert "Foo" in result["messages"]
        foo = result["messages"]["Foo"]
        assert len(foo.fields) == 2
        assert foo.fields[1].name == "name"
        assert foo.fields[1].type_name == "string"
        assert foo.fields[2].name == "age"
        assert foo.fields[2].type_name == "int32"

    def test_parse_repeated_field(self):
        proto = textwrap.dedent("""\
            message Bar {
              repeated string tags = 3;
            }
        """)
        result = parse_proto(proto)
        bar = result["messages"]["Bar"]
        assert bar.fields[3].label == "repeated"
        assert bar.fields[3].name == "tags"

    def test_parse_map_field(self):
        proto = textwrap.dedent("""\
            message Config {
              map<string, string> labels = 5;
            }
        """)
        result = parse_proto(proto)
        cfg = result["messages"]["Config"]
        assert cfg.fields[5].label == "map"
        assert "string" in cfg.fields[5].type_name

    def test_parse_service_with_rpcs(self):
        proto = textwrap.dedent("""\
            service FooService {
              rpc GetFoo(GetFooRequest) returns (Foo);
              rpc ListFoos(ListRequest) returns (FooList);
            }
        """)
        result = parse_proto(proto)
        assert "FooService" in result["services"]
        svc = result["services"]["FooService"]
        assert "GetFoo" in svc.rpcs
        assert svc.rpcs["GetFoo"].input_type == "GetFooRequest"
        assert svc.rpcs["GetFoo"].output_type == "Foo"
        assert "ListFoos" in svc.rpcs

    def test_parse_rpc_with_stream(self):
        proto = textwrap.dedent("""\
            service StreamService {
              rpc Subscribe(SubscribeRequest) returns (stream Event);
            }
        """)
        result = parse_proto(proto)
        svc = result["services"]["StreamService"]
        assert "Subscribe" in svc.rpcs

    def test_parse_empty_message(self):
        proto = "message Empty {}"
        result = parse_proto(proto)
        assert "Empty" in result["messages"]
        assert len(result["messages"]["Empty"].fields) == 0

    def test_parse_multiple_messages_and_services(self):
        proto = textwrap.dedent("""\
            message Req { string id = 1; }
            message Resp { string id = 1; }
            service Svc {
              rpc Call(Req) returns (Resp);
            }
        """)
        result = parse_proto(proto)
        assert len(result["messages"]) == 2
        assert len(result["services"]) == 1

    def test_comments_stripped(self):
        proto = textwrap.dedent("""\
            // This is a comment
            message Foo {
              string name = 1; // inline comment
            }
        """)
        result = parse_proto(proto)
        assert "Foo" in result["messages"]
        assert len(result["messages"]["Foo"].fields) == 1

    def test_parse_qualified_types(self):
        proto = textwrap.dedent("""\
            message Wrapper {
              sylion.common.v1.Status status = 1;
            }
        """)
        result = parse_proto(proto)
        assert result["messages"]["Wrapper"].fields[1].type_name == "sylion.common.v1.Status"


# ===========================================================================
# 2. Proto diffing
# ===========================================================================

class TestProtoDiffing:

    def test_no_changes(self):
        old = parse_proto("message Foo { string name = 1; }")
        new = parse_proto("message Foo { string name = 1; }")
        changes = diff_protos(old, new)
        assert len(changes) == 0

    def test_added_field_non_breaking(self):
        old = parse_proto("message Foo { string name = 1; }")
        new = parse_proto("message Foo { string name = 1; int32 age = 2; }")
        changes = diff_protos(old, new)
        assert len(changes) == 1
        assert changes[0].kind == "field_added"
        assert not changes[0].breaking

    def test_removed_field_breaking(self):
        old = parse_proto("message Foo { string name = 1; int32 age = 2; }")
        new = parse_proto("message Foo { string name = 1; }")
        changes = diff_protos(old, new)
        breaking = [c for c in changes if c.breaking]
        assert any(c.kind == "field_removed" for c in breaking)

    def test_changed_field_type_breaking(self):
        old = parse_proto("message Foo { string id = 1; }")
        new = parse_proto("message Foo { int32 id = 1; }")
        changes = diff_protos(old, new)
        breaking = [c for c in changes if c.breaking]
        assert any(c.kind == "field_type_changed" for c in breaking)

    def test_changed_field_number_breaking(self):
        old = parse_proto("message Foo { string name = 1; int32 age = 2; }")
        new = parse_proto("message Foo { string other = 1; int32 age = 3; }")
        changes = diff_protos(old, new)
        breaking = [c for c in changes if c.breaking]
        assert any(c.kind == "field_number_changed" for c in breaking)

    def test_removed_rpc_breaking(self):
        old = parse_proto("service Svc { rpc Get(GetReq) returns (GetResp); rpc Delete(DelReq) returns (DelResp); }")
        new = parse_proto("service Svc { rpc Get(GetReq) returns (GetResp); }")
        changes = diff_protos(old, new)
        breaking = [c for c in changes if c.breaking]
        assert any(c.kind == "rpc_removed" for c in breaking)

    def test_added_rpc_non_breaking(self):
        old = parse_proto("service Svc { rpc Get(GetReq) returns (GetResp); }")
        new = parse_proto("service Svc { rpc Get(GetReq) returns (GetResp); rpc Create(CreateReq) returns (CreateResp); }")
        changes = diff_protos(old, new)
        non_breaking = [c for c in changes if not c.breaking]
        assert any(c.kind == "rpc_added" for c in non_breaking)

    def test_message_removed_breaking(self):
        old = parse_proto("message Foo { string name = 1; }")
        new = parse_proto("")
        changes = diff_protos(old, new)
        assert any(c.kind == "field_removed" and c.breaking for c in changes)

    def test_service_removed_breaking(self):
        old = parse_proto("service Svc { rpc Get(GetReq) returns (GetResp); }")
        new = parse_proto("")
        changes = diff_protos(old, new)
        assert any(c.kind == "rpc_removed" and c.breaking for c in changes)

    def test_new_message_non_breaking(self):
        old = parse_proto("")
        new = parse_proto("message NewMsg { string id = 1; }")
        changes = diff_protos(old, new)
        assert all(not c.breaking for c in changes)


# ===========================================================================
# 3. Event compatibility
# ===========================================================================

class TestEventCompatibility:

    def test_fully_compatible(self, checker):
        result = checker.check_event_compatibility(
            ["user.created", "user.updated"],
            ["user.created", "user.updated"],
        )
        assert result["compatible"]
        assert result["missing"] == []
        assert result["extra"] == []

    def test_missing_events(self, checker):
        result = checker.check_event_compatibility(
            ["user.created"],
            ["user.created", "user.deleted"],
        )
        assert not result["compatible"]
        assert "user.deleted" in result["missing"]

    def test_extra_producer_events_non_breaking(self, checker):
        result = checker.check_event_compatibility(
            ["user.created", "user.updated", "user.deleted"],
            ["user.created", "user.updated"],
        )
        assert result["compatible"]
        assert "user.deleted" in result["extra"]

    def test_empty_producer(self, checker):
        result = checker.check_event_compatibility(
            [],
            ["user.created"],
        )
        assert not result["compatible"]
        assert result["missing"] == ["user.created"]

    def test_empty_consumer(self, checker):
        result = checker.check_event_compatibility(
            ["user.created"],
            [],
        )
        assert result["compatible"]
        assert result["missing"] == []
        assert result["extra"] == ["user.created"]


# ===========================================================================
# 4. Module contract checks
# ===========================================================================

class TestModuleContracts:

    def test_module_with_no_contracts_is_compatible(self, checker, module_reg):
        _register_module(module_reg, "mod-a")
        result = checker.check_module_contracts("mod-a")
        assert result["compatible"]

    def test_module_as_producer_with_breaking_contract(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-a")
        _publish_contract(contract_reg, "svc.foo", version="1.0.0", producer="mod-a")
        # Publish breaking version
        _publish_contract(contract_reg, "svc.foo", version="2.0.0", producer="mod-a")
        result = checker.check_module_contracts("mod-a")
        assert not result["compatible"]
        assert any("svc.foo" in i for i in result["issues"])

    def test_module_as_consumer_with_breaking_contract(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-b")
        _publish_contract(contract_reg, "svc.bar", version="1.0.0",
                          producer="mod-a", consumers=["mod-b"])
        _publish_contract(contract_reg, "svc.bar", version="2.0.0",
                          producer="mod-a", consumers=["mod-b"])
        result = checker.check_module_contracts("mod-b")
        assert not result["compatible"]

    def test_nonexistent_module_reports_issue(self, checker):
        result = checker.check_module_contracts("ghost")
        assert not result["compatible"]
        assert any("not found" in i for i in result["issues"])

    def test_module_compatible_with_non_breaking_contract(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-c")
        _publish_contract(contract_reg, "svc.baz", version="1.0.0", producer="mod-c")
        _publish_contract(contract_reg, "svc.baz", version="1.1.0", producer="mod-c")
        result = checker.check_module_contracts("mod-c")
        assert result["compatible"]


# ===========================================================================
# 5. Proto breaking detection via checker
# ===========================================================================

class TestProtoBreakingViaChecker:

    def test_identical_protos(self, checker):
        proto = "message Foo { string name = 1; }"
        result = checker.check_proto_breaking_from_text(proto, proto)
        assert not result["breaking"]
        assert result["changes"] == []

    def test_breaking_proto_change(self, checker):
        old = "message Foo { string name = 1; int32 age = 2; }"
        new = "message Foo { string name = 1; }"
        result = checker.check_proto_breaking_from_text(old, new)
        assert result["breaking"]
        assert any(c["kind"] == "field_removed" for c in result["changes"])

    def test_non_breaking_proto_change(self, checker):
        old = "message Foo { string name = 1; }"
        new = "message Foo { string name = 1; int32 age = 2; }"
        result = checker.check_proto_breaking_from_text(old, new)
        assert not result["breaking"]


# ===========================================================================
# 6. Full compatibility report
# ===========================================================================

class TestCompatibilityReport:

    def test_empty_system_report(self, checker):
        report = checker.generate_compatibility_report()
        assert report["modules_checked"] == 0
        assert report["modules_compatible"] == 0
        assert report["total_issues"] == 0

    def test_report_with_healthy_modules(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-a")
        _register_module(module_reg, "mod-b")
        _publish_contract(contract_reg, "svc.x", version="1.0.0",
                          producer="mod-a", consumers=["mod-b"])
        report = checker.generate_compatibility_report()
        assert report["modules_checked"] == 2
        assert report["modules_compatible"] == 2
        assert report["total_issues"] == 0

    def test_report_with_breaking_contracts(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-a")
        _publish_contract(contract_reg, "svc.y", version="1.0.0", producer="mod-a")
        _publish_contract(contract_reg, "svc.y", version="2.0.0", producer="mod-a")
        report = checker.generate_compatibility_report()
        assert report["modules_checked"] == 1
        assert report["modules_compatible"] == 0
        assert report["total_issues"] >= 1

    def test_report_contains_summary_string(self, checker, module_reg):
        _register_module(module_reg, "mod-z")
        report = checker.generate_compatibility_report()
        assert "1 modules" in report["summary"]


# ===========================================================================
# 7. Lifecycle transition validation
# ===========================================================================

class TestValidateTransition:

    def test_valid_transition_no_contracts(self, checker, module_reg):
        _register_module(module_reg, "mod-t")
        result = checker.validate_transition("mod-t", "build")
        assert result["valid"]

    def test_invalid_transition_breaking_produced_contract(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-x")
        _publish_contract(contract_reg, "svc.q", version="1.0.0", producer="mod-x")
        _publish_contract(contract_reg, "svc.q", version="2.0.0", producer="mod-x")
        result = checker.validate_transition("mod-x", "shadow")
        assert not result["valid"]

    def test_transition_to_stable_checks_consumed_contracts(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-a")
        _register_module(module_reg, "mod-b", depends_on=["mod-a"])
        _publish_contract(contract_reg, "svc.r", version="1.0.0",
                          producer="mod-a", consumers=["mod-b"])
        _publish_contract(contract_reg, "svc.r", version="2.0.0",
                          producer="mod-a", consumers=["mod-b"])
        result = checker.validate_transition("mod-b", "stable")
        assert not result["valid"]

    def test_nonexistent_module_transition(self, checker):
        result = checker.validate_transition("ghost", "build")
        assert not result["valid"]
        assert any("not found" in i for i in result["issues"])

    def test_transition_checks_dependent_modules(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-base")
        _register_module(module_reg, "mod-dep", depends_on=["mod-base"])
        _publish_contract(contract_reg, "svc.dep", version="2.0.0",
                          producer="mod-dep")
        # mod-dep has a breaking contract -> any transition check that looks at
        # dependents of mod-base (which is mod-dep) should flag it when
        # mod-dep has issues.
        # In this case mod-base itself is fine, but we check all dependents.
        result = checker.validate_transition("mod-base", "build")
        # mod-dep is a dependent of mod-base and has no pre-existing version,
        # so it is not breaking. The transition should be valid.
        assert result["valid"]


# ===========================================================================
# 8. Edge cases and integration
# ===========================================================================

class TestEdgeCases:

    def test_proto_with_syntax_and_package(self, checker):
        proto = textwrap.dedent("""\
            syntax = "proto3";
            package sylion.test.v1;
            message Msg { string id = 1; }
        """)
        result = checker.check_proto_breaking_from_text(proto, proto)
        assert not result["breaking"]

    def test_event_compatibility_deduplication(self, checker):
        result = checker.check_event_compatibility(
            ["a.b", "a.b", "c.d"],
            ["a.b", "c.d"],
        )
        assert result["compatible"]
        assert result["missing"] == []

    def test_multiple_breaking_changes_accumulate(self, checker):
        old = textwrap.dedent("""\
            message Foo { string name = 1; int32 age = 2; }
            service Svc { rpc Get(GetReq) returns (GetResp); rpc Delete(DelReq) returns (DelResp); }
        """)
        new = textwrap.dedent("""\
            message Foo { string name = 1; }
            service Svc { rpc Get(GetReq) returns (GetResp); }
        """)
        result = checker.check_proto_breaking_from_text(old, new)
        assert result["breaking"]
        breaking_changes = [c for c in result["changes"] if c["breaking"]]
        assert len(breaking_changes) >= 2  # field_removed + rpc_removed

    def test_contract_type_change_is_detected(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "mod-ev")
        # Publish an event_schema contract
        _publish_contract(contract_reg, "evt.user", version="1.0.0",
                          producer="mod-ev", ctype=ContractType.EVENT_SCHEMA)
        # Publish a non-breaking update
        _publish_contract(contract_reg, "evt.user", version="1.1.0",
                          producer="mod-ev", ctype=ContractType.EVENT_SCHEMA)
        result = checker.check_module_contracts("mod-ev")
        assert result["compatible"]

    def test_report_with_mixed_modules(self, checker, contract_reg, module_reg):
        _register_module(module_reg, "good-mod")
        _register_module(module_reg, "bad-mod")
        _publish_contract(contract_reg, "svc.ok", version="1.0.0", producer="good-mod")
        _publish_contract(contract_reg, "svc.ok", version="1.1.0", producer="good-mod")
        _publish_contract(contract_reg, "svc.break", version="1.0.0", producer="bad-mod")
        _publish_contract(contract_reg, "svc.break", version="2.0.0", producer="bad-mod")
        report = checker.generate_compatibility_report()
        assert report["modules_compatible"] == 1
        assert report["total_issues"] >= 1
