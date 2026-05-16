"""W14 local-model task dispatcher.

Thin CLI wrapper around ``ollama run`` for the three W14 local models:

    qwen3.5:latest         — boilerplate scaffolding (dataclasses, REST stubs)
    qwen2.5:7b-instruct    — focused single-purpose validators / assertions
    gpt-oss:20b            — pre-commit review / lightweight reasoning

Usage
-----
::

    python scripts/w14_local_task.py \\
        --model qwen3.5 \\
        --task dataclass_scaffold \\
        --input docs/w14_workplan/ontology_spec.yaml \\
        --output build/w14_scaffold.json

Tasks (matching W14_PROMPT_LOCAL_*.md briefs):

    dataclass_scaffold     — stub a single dataclass from a yaml object spec
    action_handler_stub    — stub a CommandBus action handler skeleton
    validator              — write a single atomic validator function
    batch_validators       — write a batch of validators from a list
    batch_i18n_pl          — translate operator-facing strings to PL
    scenario_fixture       — create a HumanScenario fixture for a domain
    pre_review             — gpt-oss reviews a diff, returns ready_for_claude_review
    drift_detection        — detect SoT/Masterplan drift in a code diff
    refactor               — propose a refactor for one file (no apply)

The script never writes to source paths — it only emits artefacts under
``--output`` so the human-in-the-loop reviewer can inspect/diff before
copying snippets in.
"""
from __future__ import annotations

import argparse
import json
import logging
import shlex
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("w14_local_task")

MODEL_ALIASES: dict[str, str] = {
    "qwen2.5": "qwen2.5:7b-instruct",
    "qwen3.5": "qwen3.5:latest",
    "gpt-oss": "gpt-oss:20b",
    # Pass-through if user already gave the full tag.
    "qwen2.5:7b-instruct": "qwen2.5:7b-instruct",
    "qwen3.5:latest": "qwen3.5:latest",
    "gpt-oss:20b": "gpt-oss:20b",
}

VALID_TASKS = (
    "dataclass_scaffold",
    "action_handler_stub",
    "validator",
    "batch_validators",
    "batch_i18n_pl",
    "scenario_fixture",
    "pre_review",
    "drift_detection",
    "refactor",
)


def _read_input(arg: str) -> str:
    """Resolve --input as either a file path or an inline string."""
    p = Path(arg)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return arg


def _build_prompt(task: str, payload: str) -> str:
    """Assemble a deterministic prompt for the chosen task."""
    if task == "dataclass_scaffold":
        return (
            "You are a Python dataclass scaffolder. Given a single YAML object "
            "spec (fields with type/required/enum hints), output ONLY a Python "
            "@dataclass declaration. No prose, no markdown fences. Use "
            "`field(default_factory=...)` for collections and `time.time` for "
            "timestamps. Spec:\n\n" + payload
        )
    if task == "action_handler_stub":
        return (
            "Write a Python class skeleton implementing a SYLION CommandBus "
            "action handler with .validate(payload) and .execute(payload, "
            "intent_id). Skip docstrings beyond one-liners. Spec:\n\n" + payload
        )
    if task == "validator":
        return (
            "Write a single Python function named `validate_X` that raises "
            "ValueError on bad input. No tests, no imports beyond `re`. "
            "Spec:\n\n" + payload
        )
    if task == "batch_validators":
        return (
            "Write Python validator functions, one per line of input. Each "
            "function raises ValueError; output ONLY function definitions. "
            "Input list:\n\n" + payload
        )
    if task == "batch_i18n_pl":
        return (
            "Translate the following operator-facing English strings to "
            "concise Polish. Output JSON: {\"en\": \"pl\", ...}. ASCII only.\n\n"
            + payload
        )
    if task == "scenario_fixture":
        return (
            "Generate a Python HumanScenario(...) literal for the given domain. "
            "Output only the constructor call. Domain:\n\n" + payload
        )
    if task == "pre_review":
        return (
            "You are a code reviewer. Read the unified diff and answer with "
            "JSON: {\"ready_for_claude_review\": bool, \"blockers\": [str], "
            "\"suggestions\": [str]}. ASCII only.\n\nDiff:\n\n" + payload
        )
    if task == "drift_detection":
        return (
            "Detect SoT/Masterplan drift in this diff. Output JSON: "
            "{\"drift_detected\": bool, \"reasons\": [str]}.\n\n" + payload
        )
    if task == "refactor":
        return (
            "Suggest a refactor (no apply). Output JSON: {\"summary\": str, "
            "\"changes\": [{\"file\": str, \"before\": str, \"after\": str}]}."
            "\n\nFile contents:\n\n" + payload
        )
    raise ValueError(f"Unknown task: {task}")


def call_ollama(model: str, prompt: str, timeout: int) -> tuple[str, int]:
    """Invoke ollama run; return (stdout, returncode)."""
    cmd = ["ollama", "run", model]
    log.debug("dispatching: %s", shlex.join(cmd))
    started = time.time()
    proc = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    elapsed = time.time() - started
    log.info(
        "ollama %s exited rc=%d in %.1fs (out=%dB err=%dB)",
        model, proc.returncode, elapsed,
        len(proc.stdout or ""), len(proc.stderr or ""),
    )
    return proc.stdout, proc.returncode


def write_output(path: Path, content: str, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        # Best-effort: validate JSON, but persist raw on failure for debugging.
        try:
            parsed = json.loads(content)
            path.write_text(
                json.dumps(parsed, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            return
        except json.JSONDecodeError:
            log.warning("output was not valid JSON; writing raw text")
    path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="W14 local-model task dispatcher")
    parser.add_argument("--model", required=True, help="qwen2.5 | qwen3.5 | gpt-oss")
    parser.add_argument("--task", required=True, choices=VALID_TASKS)
    parser.add_argument("--input", required=True, help="File path OR inline string")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--format", default="text", choices=("text", "json"))
    parser.add_argument("--timeout", type=int, default=180,
                        help="Seconds before ollama is killed (default: 180)")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
    )

    if args.model not in MODEL_ALIASES:
        log.error("unknown model alias: %s (valid: %s)",
                  args.model, sorted(MODEL_ALIASES))
        return 2
    full_model = MODEL_ALIASES[args.model]

    payload = _read_input(args.input)
    prompt = _build_prompt(args.task, payload)
    log.info("task=%s model=%s prompt_chars=%d output=%s",
             args.task, full_model, len(prompt), args.output)

    try:
        stdout, rc = call_ollama(full_model, prompt, args.timeout)
    except subprocess.TimeoutExpired:
        log.error("ollama timed out after %ds", args.timeout)
        return 3
    except FileNotFoundError:
        log.error("'ollama' binary not found in PATH")
        return 4

    if rc != 0:
        log.error("ollama returned rc=%d", rc)
        return rc

    write_output(Path(args.output), stdout, args.format)
    log.info("wrote %d chars -> %s", len(stdout), args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
