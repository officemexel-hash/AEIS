#!/usr/bin/env python3
"""
SYLION AEIS -- gRPC Stub Generator

Generates Python gRPC stubs from .proto contract files using grpcio-tools.
Run from the sylion-pipeline project root:

    python -m sylion.contracts.generate_stubs

Requires: grpcio-tools >= 1.60.0
Install:  pip install grpcio-tools
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Project root detection
CONTRACTS_DIR = Path(__file__).resolve().parent
PROTO_DIR = CONTRACTS_DIR / "proto"
OUTPUT_DIR = CONTRACTS_DIR / "generated"

# All proto files in dependency order (common first)
PROTO_FILES = [
    "common.proto",
    "core_v1.proto",
    "cognitive_v1.proto",
    "execution_v1.proto",
    "memory_v1.proto",
    "governance_v1.proto",
    "security_v1.proto",
    "efficiency_v1.proto",
    "aeis_v1.proto",
    "skills_v1.proto",
    "surface_v1.proto",
    "rebuild_v1.proto",
    "quality_v1.proto",
    "devices_v1.proto",
    "sdr_v1.proto",
    "cellular_v1.proto",
]


def check_grpcio_tools() -> bool:
    """Check if grpcio-tools is installed."""
    try:
        import grpc_tools.protoc  # noqa: F401
        return True
    except ImportError:
        return False


def generate_stubs(proto_dir: Path, output_dir: Path) -> list[str]:
    """Generate Python gRPC stubs from .proto files.

    Returns list of generated file paths.
    """
    if not check_grpcio_tools():
        print("ERROR: grpcio-tools is not installed.")
        print("Install with: pip install grpcio-tools")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []

    for proto_file in PROTO_FILES:
        proto_path = proto_dir / proto_file
        if not proto_path.exists():
            print(f"WARNING: {proto_file} not found, skipping")
            continue

        cmd = [
            sys.executable, "-m", "grpc_tools.protoc",
            f"--proto_path={proto_dir}",
            f"--python_out={output_dir}",
            f"--grpc_python_out={output_dir}",
            str(proto_path),
        ]

        print(f"Generating stubs for {proto_file}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            continue

        # Track generated files
        stem = proto_file.replace(".proto", "")
        py_file = output_dir / f"{stem}_pb2.py"
        grpc_file = output_dir / f"{stem}_pb2_grpc.py"

        for f in [py_file, grpc_file]:
            if f.exists():
                generated.append(str(f))
                print(f"  -> {f.name}")

    return generated


def generate_init(output_dir: Path, generated: list[str]) -> None:
    """Generate __init__.py in the output directory."""
    init_path = output_dir / "__init__.py"
    init_path.write_text(
        '"""SYLION AEIS gRPC generated stubs. Auto-generated -- do not edit."""\n'
    )
    print(f"\nCreated {init_path}")


def main():
    print("SYLION AEIS gRPC Stub Generator")
    print("=" * 40)
    print(f"Proto dir:  {PROTO_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")
    print()

    generated = generate_stubs(PROTO_DIR, OUTPUT_DIR)

    if generated:
        generate_init(OUTPUT_DIR, generated)
        print(f"\nGenerated {len(generated)} files successfully.")
    else:
        print("\nNo files generated.")
        sys.exit(1)


if __name__ == "__main__":
    main()
