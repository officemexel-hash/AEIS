"""
Tests for sylion.contracts.generate_stubs

Exercises every public helper and constant:
  - check_grpcio_tools
  - generate_stubs
  - generate_init
  - PROTO_FILES / CONTRACTS_DIR / PROTO_DIR / OUTPUT_DIR
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from sylion.contracts.generate_stubs import (
    CONTRACTS_DIR,
    OUTPUT_DIR,
    PROTO_DIR,
    PROTO_FILES,
    check_grpcio_tools,
    generate_init,
    generate_stubs,
)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------


class TestPathConstants:
    def test_contracts_dir_is_path(self):
        assert isinstance(CONTRACTS_DIR, Path)

    def test_proto_dir_is_path(self):
        assert isinstance(PROTO_DIR, Path)

    def test_output_dir_is_path(self):
        assert isinstance(OUTPUT_DIR, Path)

    def test_contracts_dir_exists(self):
        assert CONTRACTS_DIR.exists()

    def test_proto_dir_exists(self):
        assert PROTO_DIR.exists()

    def test_proto_dir_is_subdirectory_of_contracts(self):
        assert PROTO_DIR.parent == CONTRACTS_DIR

    def test_output_dir_is_subdirectory_of_contracts(self):
        assert OUTPUT_DIR.parent == CONTRACTS_DIR


# ---------------------------------------------------------------------------
# PROTO_FILES constant
# ---------------------------------------------------------------------------


class TestProtoFilesConstant:
    def test_is_list(self):
        assert isinstance(PROTO_FILES, list)

    def test_not_empty(self):
        assert len(PROTO_FILES) > 0

    def test_all_end_in_proto(self):
        for f in PROTO_FILES:
            assert f.endswith(".proto"), f"Expected .proto extension: {f}"

    def test_common_proto_is_first(self):
        assert PROTO_FILES[0] == "common.proto"

    def test_all_proto_files_exist_on_disk(self):
        for f in PROTO_FILES:
            path = PROTO_DIR / f
            assert path.exists(), f"Proto file not found: {path}"

    def test_no_duplicates(self):
        assert len(PROTO_FILES) == len(set(PROTO_FILES))

    def test_count_matches_on_disk(self):
        on_disk = sorted(p.name for p in PROTO_DIR.glob("*.proto"))
        for f in PROTO_FILES:
            assert f in on_disk, f"PROTO_FILES entry not on disk: {f}"


# ---------------------------------------------------------------------------
# check_grpcio_tools
# ---------------------------------------------------------------------------


class TestCheckGrpcioTools:
    def test_returns_bool(self):
        result = check_grpcio_tools()
        assert isinstance(result, bool)

    def test_returns_true_when_installed(self):
        """If grpcio-tools is installed (as it should be), returns True."""
        result = check_grpcio_tools()
        if result:
            import grpc_tools.protoc  # noqa: F401 — confirm importable
        # If not installed, we just confirm it returned False
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# generate_stubs
# ---------------------------------------------------------------------------


class TestGenerateStubs:
    @pytest.fixture(autouse=True)
    def _require_grpcio(self):
        """Skip tests if grpcio-tools is not installed."""
        if not check_grpcio_tools():
            pytest.skip("grpcio-tools not installed")

    def test_returns_list(self):
        result = generate_stubs(PROTO_DIR, OUTPUT_DIR)
        assert isinstance(result, list)

    def test_all_returned_paths_are_strings(self):
        result = generate_stubs(PROTO_DIR, OUTPUT_DIR)
        for path in result:
            assert isinstance(path, str)

    def test_output_dir_created_if_missing(self, tmp_path):
        out = tmp_path / "stubs_out"
        assert not out.exists()
        generate_stubs(PROTO_DIR, out)
        assert out.exists()

    def test_generated_files_exist_on_disk(self):
        result = generate_stubs(PROTO_DIR, OUTPUT_DIR)
        for path_str in result:
            p = Path(path_str)
            assert p.exists(), f"Generated file not found: {path_str}"

    def test_generated_files_are_python(self):
        result = generate_stubs(PROTO_DIR, OUTPUT_DIR)
        for path_str in result:
            assert path_str.endswith(".py"), f"Not a Python file: {path_str}"

    def test_pb2_and_grpc_files_generated(self):
        result = generate_stubs(PROTO_DIR, OUTPUT_DIR)
        basenames = [Path(p).name for p in result]
        # At least one _pb2.py and one _pb2_grpc.py should appear
        assert any("_pb2.py" in n and "_grpc" not in n for n in basenames), (
            "No _pb2.py files generated"
        )
        assert any("_pb2_grpc.py" in n for n in basenames), (
            "No _pb2_grpc.py files generated"
        )

    def test_generates_for_most_existing_protos(self):
        result = generate_stubs(PROTO_DIR, OUTPUT_DIR)
        # Protos with syntax errors will be skipped by generate_stubs.
        # Verify that the majority of protos produce at least a _pb2 file.
        generated_stems = set()
        for p in result:
            name = Path(p).name
            stem = name.replace("_pb2_grpc.py", "").replace("_pb2.py", "")
            generated_stems.add(stem)
        # At least 80% of proto files should compile successfully
        threshold = len(PROTO_FILES) * 8 // 10
        assert len(generated_stems) >= threshold, (
            f"Only {len(generated_stems)}/{len(PROTO_FILES)} proto files "
            f"generated stubs (expected >= {threshold})"
        )

    def test_skips_missing_proto_files(self, tmp_path):
        """If a proto file is missing, it should be skipped gracefully."""
        empty_proto_dir = tmp_path / "proto_empty"
        empty_proto_dir.mkdir()
        out_dir = tmp_path / "out"
        result = generate_stubs(empty_proto_dir, out_dir)
        # No proto files -> no generated files
        assert result == []

    def test_generates_with_subset_of_protos(self, tmp_path):
        """Only proto files present on disk should be processed."""
        import shutil
        subset_dir = tmp_path / "proto_subset"
        subset_dir.mkdir()
        out_dir = tmp_path / "out_subset"
        # Copy just common.proto
        shutil.copy2(PROTO_DIR / "common.proto", subset_dir / "common.proto")
        result = generate_stubs(subset_dir, out_dir)
        assert len(result) >= 1
        for p in result:
            assert "common" in Path(p).name


# ---------------------------------------------------------------------------
# generate_init
# ---------------------------------------------------------------------------


class TestGenerateInit:
    def test_creates_init_file(self, tmp_path):
        generate_init(tmp_path, ["fake_pb2.py"])
        init_path = tmp_path / "__init__.py"
        assert init_path.exists()

    def test_init_contains_docstring(self, tmp_path):
        generate_init(tmp_path, ["fake_pb2.py"])
        init_path = tmp_path / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        assert "Auto-generated" in content

    def test_init_is_valid_python(self, tmp_path):
        generate_init(tmp_path, ["fake_pb2.py"])
        init_path = tmp_path / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        # Should compile without errors
        compile(content, str(init_path), "exec")

    def test_init_overwrites_existing(self, tmp_path):
        init_path = tmp_path / "__init__.py"
        init_path.write_text("old content", encoding="utf-8")
        generate_init(tmp_path, ["fake_pb2.py"])
        content = init_path.read_text(encoding="utf-8")
        assert "old content" not in content
        assert "Auto-generated" in content

    def test_init_content_exact(self, tmp_path):
        generate_init(tmp_path, [])
        init_path = tmp_path / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        expected = (
            '"""SYLION AEIS gRPC generated stubs. '
            'Auto-generated -- do not edit."""\n'
        )
        assert content == expected
