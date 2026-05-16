"""
SYLION Worker Runtime Launcher

Usage:
    python scripts/run_worker.py --worker-id wk_xxx --loop --interval 60

Or register a new worker and run:
    python scripts/run_worker.py --register "Worker-A" --host localhost --capacity 3 --loop
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure sylion-pipeline is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "sylion-pipeline"))

from sylion.worker.registry import get_worker_registry
from sylion.worker.runtime import WorkerRuntime, SandboxManager
from sylion.worker.compact import CompactGenerator
from sylion.core.event_bus import get_event_bus


def main():
    parser = argparse.ArgumentParser(description="SYLION Worker Runtime Launcher")
    parser.add_argument("--register", type=str, default=None, help="Register new worker with this name")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--capacity", type=int, default=3)
    parser.add_argument("--tags", type=str, default="", help="Comma-separated tags")
    parser.add_argument("--worker-id", type=str, default=None, help="Existing worker ID to run")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--repo-url", type=str, default=None)
    parser.add_argument("--sandbox-dir", type=str, default=None)
    args = parser.parse_args()

    registry = get_worker_registry(event_bus=get_event_bus())

    worker_id = args.worker_id
    if args.register:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        w = registry.register_worker(
            name=args.register,
            host=args.host,
            capacity=args.capacity,
            tags=tags,
        )
        worker_id = w["worker_id"]
        print(f"Registered worker: {worker_id} ({w['name']})")

    if not worker_id:
        print("ERROR: Provide --worker-id or --register")
        sys.exit(1)

    sandbox = SandboxManager(base_dir=args.sandbox_dir)
    compact_gen = CompactGenerator(
        worker_registry=registry,
        manifest_dir=Path(__file__).parent.parent / "src" / "sylion-pipeline" / "sylion" / "contracts" / "manifests",
    )
    runtime = WorkerRuntime(
        worker_id=worker_id,
        registry=registry,
        sandbox=sandbox,
        compact_generator=compact_gen,
    )

    if args.loop:
        print(f"Starting worker loop: {worker_id}")
        runtime.loop(interval=args.interval, max_cycles=args.max_cycles, repo_url=args.repo_url)
    else:
        result = runtime.execute_cycle(repo_url=args.repo_url)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
