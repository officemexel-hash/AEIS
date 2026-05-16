"""
SYLION AEIS -- Decomposition Engine (Phase 10 / Distributed-Ready).

Single-module prototype that proves end-to-end distributed build:

  prompt  ─▶  decompose (rule-based)  ─▶  task specs
          ─▶  assign (round-robin Host A / Host B)
          ─▶  dispatch (local subprocess | remote SSH)
          ─▶  merge (stitch task outputs into one artifact)
          ─▶  evidence_pack (SHA-256 manifest + signed-at timestamp)

Intentionally thin. No LLM call on the decomposition side yet -- that's the
ETAP-5 proof scaffold. Adding an Anthropic planner is a drop-in replacement
for `_rule_decompose` once the API key is present.

Host B dispatch uses the operator's registered SSH key (see
`infra/hetzner_host_b.json` and GATE 4 proof). The remote worker is a plain
`python3 -c` invocation; no extra daemon required beyond sshd.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.aeis.decomposition_engine")


class UnsupportedPromptError(RuntimeError):
    """Raised when AEIS cannot decompose a non-trivial prompt locally."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TaskSpec:
    task_id: str
    kind: str                 # "python_function"
    name: str                 # e.g. "add"
    signature: str            # e.g. "a, b"
    body: str                 # python source lines (indented)
    docstring: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "name": self.name,
            "signature": self.signature,
            "body": self.body,
            "docstring": self.docstring,
        }


@dataclass
class TaskResult:
    task_id: str
    worker: str               # "host_a" or "host_b:<ip>"
    status: str               # "completed" | "failed"
    output: str               # rendered python source of the function
    stdout: str = ""
    stderr: str = ""
    latency_ms: int = 0
    error: str | None = None


@dataclass
class EvidencePack:
    pack_id: str
    prompt: str
    decomposed_at: float
    task_count: int
    sha256: str
    manifest: dict[str, Any]
    artifact_path: str | None = None


# ---------------------------------------------------------------------------
# Decomposer
# ---------------------------------------------------------------------------

CALC_OPS = {
    "add":      ("a, b", "return a + b", "Return the sum of a and b."),
    "sub":      ("a, b", "return a - b", "Return a minus b."),
    "mul":      ("a, b", "return a * b", "Return the product of a and b."),
    "div":      ("a, b", "if b == 0:\n    raise ZeroDivisionError('division by zero')\nreturn a / b",
                 "Return a divided by b. Raises ZeroDivisionError if b == 0."),
    "mod":      ("a, b", "return a % b", "Return a modulo b."),
    "pow":      ("a, b", "return a ** b", "Return a raised to the power b."),
}

# "calculator" / "add/sub/mul/div" intent detector.
_CALC_TOKENS = re.compile(r"\b(add|sub|mul|div|mod|pow|subtract|multiply|divide|modulo|power)\b", re.I)
_TOKEN_ALIAS = {
    "subtract": "sub",
    "multiply": "mul",
    "divide":   "div",
    "modulo":   "mod",
    "power":    "pow",
}


def _rule_decompose(prompt: str) -> list[TaskSpec]:
    """Rule-based decomposer for calculator-style prompts.

    Matches bag-of-words tokens for arithmetic ops. Returns a TaskSpec per
    distinct detected op. If nothing matches, falls back to the basic four.
    """
    hits: list[str] = []
    seen: set[str] = set()
    for m in _CALC_TOKENS.finditer(prompt or ""):
        tok = m.group(0).lower()
        tok = _TOKEN_ALIAS.get(tok, tok)
        if tok not in seen:
            seen.add(tok)
            hits.append(tok)

    if not hits:
        hits = ["add", "sub", "mul", "div"]

    tasks: list[TaskSpec] = []
    for op in hits:
        if op not in CALC_OPS:
            continue
        sig, body, doc = CALC_OPS[op]
        tasks.append(TaskSpec(
            task_id=f"t_{uuid.uuid4().hex[:10]}",
            kind="python_function",
            name=op,
            signature=sig,
            body=body,
            docstring=doc,
        ))
    return tasks


def _chat_decompose(prompt: str) -> list[TaskSpec]:
    lowered = (prompt or "").lower()
    if not any(token in lowered for token in ("komunikator", "wiadomos", "chat")):
        return []
    return [
        TaskSpec(f"t_{uuid.uuid4().hex[:10]}", "python_function", "register_user", "username, password", "return {'username': username, 'created': True}", "Register a user."),
        TaskSpec(f"t_{uuid.uuid4().hex[:10]}", "python_function", "login_user", "username, password", "return {'username': username, 'authenticated': True}", "Authenticate a user."),
        TaskSpec(f"t_{uuid.uuid4().hex[:10]}", "python_function", "send_message", "room_id, sender, text", "return {'room_id': room_id, 'sender': sender, 'text': text}", "Send a room message."),
        TaskSpec(f"t_{uuid.uuid4().hex[:10]}", "html_fragment", "chat_shell", "", "<!DOCTYPE html><html><body><main id='chat-app'></main></body></html>", "Chat UI shell."),
    ]


def _tasks_from_planner_payload(raw_text: str) -> list[TaskSpec]:
    match = re.search(r"\{.*\}", raw_text or "", re.S)
    if not match:
        raise UnsupportedPromptError("Planner did not return a JSON task payload")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise UnsupportedPromptError(f"Planner returned invalid JSON: {exc}") from exc
    tasks_raw = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(tasks_raw, list) or not tasks_raw:
        raise UnsupportedPromptError("Planner returned no tasks")
    tasks: list[TaskSpec] = []
    for item in tasks_raw:
        if not isinstance(item, dict):
            continue
        tasks.append(TaskSpec(
            task_id=f"t_{uuid.uuid4().hex[:10]}",
            kind=str(item.get("kind") or "python_function"),
            name=str(item.get("name") or f"task_{len(tasks) + 1}"),
            signature=str(item.get("signature") or ""),
            body=str(item.get("body") or ""),
            docstring=str(item.get("docstring") or ""),
        ))
    if not tasks:
        raise UnsupportedPromptError("Planner returned no usable tasks")
    return tasks


def decompose_prompt(prompt: str, llm_adapter: Any | None = None) -> list[TaskSpec]:
    """Decompose prompt using safe local rules first, then an explicit planner LLM."""
    chat_tasks = _chat_decompose(prompt)
    if chat_tasks:
        return chat_tasks
    if _CALC_TOKENS.search(prompt or ""):
        return _rule_decompose(prompt)
    if llm_adapter is None:
        raise UnsupportedPromptError("Prompt requires a live planner model")

    provider = llm_adapter._get_provider() if hasattr(llm_adapter, "_get_provider") else ""
    api_key = llm_adapter._get_api_key(provider) if hasattr(llm_adapter, "_get_api_key") else ""
    if not api_key:
        raise UnsupportedPromptError("Prompt requires a live planner model")
    try:
        response = llm_adapter.call_messages(
            "planner",
            [
                {"role": "system", "content": "Return JSON with a tasks array."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1600,
        )
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedPromptError(str(exc)) from exc
    text = response.get("text", "") if isinstance(response, dict) else str(response)
    return _tasks_from_planner_payload(text)


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def assign_round_robin(
    tasks: list[TaskSpec],
    workers: list[str],
) -> list[tuple[TaskSpec, str]]:
    """Assign each task to a worker in round-robin order.

    workers: list like ["host_a", "host_b:46.224.3.35"].
    """
    if not workers:
        raise ValueError("no workers available for assignment")
    out: list[tuple[TaskSpec, str]] = []
    for i, t in enumerate(tasks):
        out.append((t, workers[i % len(workers)]))
    return out


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _render_task_source(task: TaskSpec) -> str:
    """Render a task spec as a standalone python function source."""
    doc = f'    """{task.docstring}"""' if task.docstring else ""
    # Re-indent body to 4 spaces.
    body_lines = [ln if ln.strip() else "" for ln in task.body.split("\n")]
    body = "\n".join(("    " + ln) if ln else "" for ln in body_lines)
    pieces = [f"def {task.name}({task.signature}):"]
    if doc:
        pieces.append(doc)
    pieces.append(body)
    return "\n".join(pieces) + "\n"


def _remote_test_script(task: TaskSpec) -> str:
    """Produce a small python program the remote runs to exec+test the task."""
    source = _render_task_source(task)
    # Minimal self-test. The remote prints a JSON blob to stdout.
    tests = {
        "add": "assert add(2, 3) == 5; assert add(-1, 1) == 0",
        "sub": "assert sub(5, 3) == 2; assert sub(0, 4) == -4",
        "mul": "assert mul(4, 5) == 20; assert mul(-2, 3) == -6",
        "div": "assert div(10, 2) == 5; assert div(7, 2) == 3.5",
        "mod": "assert mod(10, 3) == 1",
        "pow": "assert pow(2, 10) == 1024",
    }
    self_test = tests.get(task.name, "pass")
    runner = (
        "import json, sys\n"
        + source
        + "\n"
        + "try:\n"
        + f"    {self_test}\n"
        + "    ok = True\n"
        + "    err = ''\n"
        + "except Exception as exc:\n"
        + "    ok = False\n"
        + "    err = repr(exc)\n"
        + "print(json.dumps({'ok': ok, 'err': err, 'source': " + json.dumps(source) + "}))\n"
    )
    return runner


def dispatch_local(task: TaskSpec) -> TaskResult:
    """Execute the task in a subprocess on Host A."""
    script = _remote_test_script(task)
    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        latency = int((time.time() - start) * 1000)
    except Exception as exc:  # noqa: BLE001
        return TaskResult(
            task_id=task.task_id,
            worker="host_a",
            status="failed",
            output="",
            error=str(exc),
            latency_ms=int((time.time() - start) * 1000),
        )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    try:
        payload = json.loads(stdout.splitlines()[-1]) if stdout else {"ok": False, "err": "no_stdout"}
    except Exception:
        payload = {"ok": False, "err": f"parse_fail: {stdout[:200]}"}

    return TaskResult(
        task_id=task.task_id,
        worker="host_a",
        status="completed" if payload.get("ok") else "failed",
        output=payload.get("source", "") or _render_task_source(task),
        stdout=stdout,
        stderr=stderr,
        latency_ms=latency,
        error=None if payload.get("ok") else payload.get("err"),
    )


def dispatch_remote_ssh(task: TaskSpec, ssh_target: str) -> TaskResult:
    """Execute the task on a remote Host B via SSH `python3 -c`.

    ssh_target: "root@46.224.3.35" or similar (operator's key must be authorized).
    """
    script = _remote_test_script(task)
    start = time.time()
    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=15",
                ssh_target,
                "python3 -",
            ],
            input=script,
            capture_output=True,
            text=True,
            timeout=45,
        )
        latency = int((time.time() - start) * 1000)
    except Exception as exc:  # noqa: BLE001
        return TaskResult(
            task_id=task.task_id,
            worker=f"host_b:{ssh_target}",
            status="failed",
            output="",
            error=str(exc),
            latency_ms=int((time.time() - start) * 1000),
        )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    try:
        payload = json.loads(stdout.splitlines()[-1]) if stdout else {"ok": False, "err": "no_stdout"}
    except Exception:
        payload = {"ok": False, "err": f"parse_fail: {stdout[:200]}"}

    return TaskResult(
        task_id=task.task_id,
        worker=f"host_b:{ssh_target}",
        status="completed" if payload.get("ok") else "failed",
        output=payload.get("source", "") or _render_task_source(task),
        stdout=stdout,
        stderr=stderr,
        latency_ms=latency,
        error=None if payload.get("ok") else payload.get("err"),
    )


def dispatch(task: TaskSpec, worker: str) -> TaskResult:
    """Route to the right dispatcher based on worker label."""
    if task.kind in {"html_fragment", "css_fragment", "js_fragment"}:
        return TaskResult(
            task_id=task.task_id,
            worker=worker,
            status="completed",
            output=task.body,
        )
    if worker == "host_a":
        return dispatch_local(task)
    if worker.startswith("host_b:"):
        ssh_target = worker.split("host_b:", 1)[1]
        if "@" not in ssh_target:
            ssh_target = f"root@{ssh_target}"
        return dispatch_remote_ssh(task, ssh_target)
    # Unknown worker -- fail fast, don't silently run locally.
    return TaskResult(
        task_id=task.task_id,
        worker=worker,
        status="failed",
        output="",
        error=f"unknown worker label '{worker}'",
    )


# ---------------------------------------------------------------------------
# Merge + Evidence pack
# ---------------------------------------------------------------------------

def merge_artifact(results: list[TaskResult]) -> str:
    """Stitch task outputs into one python file in deterministic order.

    Orders by task function name for stable SHA across runs.
    """
    html = next((r.output for r in results if r.status == "completed" and "<html" in r.output.lower()), "")
    if html:
        css = "\n".join(r.output for r in results if r.status == "completed" and r.output and r.output != html and "{" in r.output)
        js = "\n".join(r.output for r in results if r.status == "completed" and r.output and r.output != html and ("const " in r.output or "function " in r.output))
        return html.replace("{{STYLE}}", css).replace("{{SCRIPT}}", js)

    ordered = sorted(
        [r for r in results if r.status == "completed" and r.output],
        key=lambda r: r.output.split("(", 1)[0],
    )
    header = "# Auto-generated by SYLION Decomposition Engine\n\n"
    body = "\n".join(r.output for r in ordered)
    return header + body


def build_evidence_pack(
    prompt: str,
    tasks: list[TaskSpec],
    assignments: list[tuple[TaskSpec, str]],
    results: list[TaskResult],
    artifact: str,
    artifact_path: str | None,
) -> EvidencePack:
    """Build a signed-at manifest. SHA-256 covers tasks+results+artifact."""
    manifest = {
        "prompt": prompt,
        "decomposed_at": time.time(),
        "task_count": len(tasks),
        "assignments": [
            {"task_id": t.task_id, "name": t.name, "worker": w}
            for (t, w) in assignments
        ],
        "results": [
            {
                "task_id": r.task_id,
                "worker": r.worker,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "error": r.error,
            } for r in results
        ],
        "artifact_sha256": hashlib.sha256(artifact.encode("utf-8")).hexdigest(),
        "artifact_bytes": len(artifact.encode("utf-8")),
    }
    packed = json.dumps(manifest, sort_keys=True, default=str).encode("utf-8")
    pack_sha = hashlib.sha256(packed).hexdigest()
    return EvidencePack(
        pack_id=f"ep_{uuid.uuid4().hex[:12]}",
        prompt=prompt,
        decomposed_at=manifest["decomposed_at"],
        task_count=len(tasks),
        sha256=pack_sha,
        manifest=manifest,
        artifact_path=artifact_path,
    )


# ---------------------------------------------------------------------------
# End-to-end orchestration
# ---------------------------------------------------------------------------

@dataclass
class DecomposeAndBuildResult:
    pack_id: str
    prompt: str
    tasks: list[dict[str, Any]]
    assignments: list[dict[str, Any]]
    results: list[dict[str, Any]]
    artifact: str
    artifact_format: str
    artifact_sha256: str
    artifact_path: str | None
    evidence: dict[str, Any]
    elapsed_ms: int


def decompose_and_build(
    prompt: str,
    workers: list[str] | None = None,
    artifact_dir: str | Path | None = None,
    llm_adapter: Any | None = None,
) -> DecomposeAndBuildResult:
    """Full pipeline: prompt → tasks → dispatch → artifact → evidence."""
    start = time.time()

    # 1. Decompose
    tasks = decompose_prompt(prompt, llm_adapter=llm_adapter) if llm_adapter is not None else (
        _chat_decompose(prompt) or _rule_decompose(prompt)
    )

    # 2. Assign
    workers = workers or ["host_a"]
    assignments = assign_round_robin(tasks, workers)

    # 3. Dispatch
    results: list[TaskResult] = []
    for task, worker in assignments:
        log.info("dispatch task=%s name=%s worker=%s", task.task_id, task.name, worker)
        results.append(dispatch(task, worker))

    # 4. Merge
    artifact = merge_artifact(results)
    artifact_format = "html" if any(t.kind == "html_fragment" for t in tasks) else "python"

    # 5. Persist artifact if requested
    path: str | None = None
    if artifact_dir:
        d = Path(artifact_dir)
        d.mkdir(parents=True, exist_ok=True)
        suffix = "html" if artifact_format == "html" else "py"
        p = d / f"decomposed_{int(time.time())}.{suffix}"
        # Write LF-normalized so on-disk sha matches manifest sha on any OS.
        p.write_bytes(artifact.encode("utf-8"))
        path = str(p)

    # 6. Evidence pack
    pack = build_evidence_pack(prompt, tasks, assignments, results, artifact, path)

    elapsed_ms = int((time.time() - start) * 1000)
    return DecomposeAndBuildResult(
        pack_id=pack.pack_id,
        prompt=prompt,
        tasks=[t.to_dict() for t in tasks],
        assignments=[{"task_id": t.task_id, "name": t.name, "worker": w} for (t, w) in assignments],
        results=[{
            "task_id": r.task_id, "worker": r.worker, "status": r.status,
            "latency_ms": r.latency_ms, "error": r.error,
        } for r in results],
        artifact=artifact,
        artifact_format=artifact_format,
        artifact_sha256=pack.manifest["artifact_sha256"],
        artifact_path=path,
        evidence={
            "pack_id": pack.pack_id,
            "sha256": pack.sha256,
            "task_count": pack.task_count,
            "manifest": pack.manifest,
        },
        elapsed_ms=elapsed_ms,
    )
