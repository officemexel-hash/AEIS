#!/usr/bin/env python3
"""Extract an AEIS frontend/API coverage map.

The script is intentionally static-first and runtime-aware:
- discovers Next.js app routes under src/sylion-frontend/src/app/(app)
- extracts literal API paths from frontend REST clients
- optionally fetches FastAPI /openapi.json and marks client paths as live
- writes JSON and/or Markdown evidence for the audit
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
APP_ROOT = REPO / "src" / "sylion-frontend" / "src" / "app" / "(app)"
FRONTEND_SRC = REPO / "src" / "sylion-frontend" / "src"
API_LIB = REPO / "src" / "sylion-frontend" / "src" / "lib" / "api"
HOOKS_FILE = API_LIB / "hooks.ts"
CLIENT_FILES = sorted(path for path in API_LIB.glob("*.ts") if path.name != "hooks.ts")


@dataclass
class RouteRow:
    route: str
    file: str
    static_api_refs: list[str]
    runtime_api_refs: list[str]
    api_ref_sources: dict[str, list[str]]
    risk_markers: list[str]
    classification: str


@dataclass
class ApiRow:
    path: str
    source_file: str
    methods: list[str]
    runtime_present: bool


def next_route_from_page(page: Path) -> str:
    rel = page.relative_to(APP_ROOT)
    parts = list(rel.parts[:-1])
    route_parts: list[str] = []
    for part in parts:
        if part.startswith("(") and part.endswith(")"):
            continue
        route_parts.append(part)
    return "/" + "/".join(route_parts) if route_parts else "/"


def discover_routes() -> list[Path]:
    return sorted(APP_ROOT.rglob("page.tsx"))


def strip_template_expr(value: str) -> str:
    # Convert `/api/x/${id}/y` to `/api/x/{var}/y` for matching.
    return re.sub(r"\$\{[^}]+\}", "{var}", value)


def normalize_api_ref(value: str) -> str:
    value = strip_template_expr(value)
    if "/api/v1/" in value:
        value = value[value.index("/api/v1/") :]
    match = re.match(r"^(/api/v1/[A-Za-z0-9_./{}:-]+)(?:\?[^`'\"\s,)}\]]*)?", value)
    if not match:
        return value.strip()
    normalized = match.group(1)
    if "{" in value and "}" in value and "{var}" not in normalized:
        normalized = re.sub(r"\{[^}]+\}", "{var}", normalized)
    normalized = re.sub(r"(?<!/)\{var\}$", "", normalized)
    normalized = normalized.rstrip(".,;:{")
    return normalized.rstrip("/")


def extract_api_refs(text: str) -> list[str]:
    refs: set[str] = set()
    patterns = [
        r"`([^`]*?/api/v1/[^`]*)`",
        r'"([^"]*?/api/v1/[^"]*)"',
        r"'([^']*?/api/v1/[^']*)'",
        r"`(\$\{[^}]+\}[^`]*?/[^`]*)`",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = normalize_api_ref(match.group(1))
            if value.startswith("/api/v1/"):
                refs.add(value)
    return sorted(refs)


def extract_api_constants(text: str) -> dict[str, list[str]]:
    constants: dict[str, list[str]] = {}
    for match in re.finditer(r"\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?);", text, flags=re.S):
        refs = extract_api_refs(match.group(2))
        if refs:
            constants[match.group(1)] = refs
    return constants


def merge_refs(*groups: Iterable[str]) -> list[str]:
    refs: set[str] = set()
    for group in groups:
        refs.update(group)
    return sorted(refs)


def object_method_segments(text: str) -> Iterable[tuple[str | None, str, str]]:
    """Yield object literal method segments from API client files.

    The API clients mostly use `export const apiName = { method: (...) => ... }`.
    A lightweight segmenter is enough here and keeps the audit script dependency-free.
    """
    method_re = re.compile(
        r"(?m)^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)\s*=>"
    )
    object_re = re.compile(r"(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{")
    matches = list(method_re.finditer(text))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        object_name = None
        for object_match in object_re.finditer(text, 0, start):
            object_name = object_match.group(1)
        yield object_name, match.group(1), text[start:end]


def extract_api_method_refs() -> dict[str, list[str]]:
    method_refs: dict[str, set[str]] = {}
    for file in CLIENT_FILES:
        if not file.exists():
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        constant_refs = extract_api_constants(text)
        for object_name, method_name, segment in object_method_segments(text):
            refs = set(extract_api_refs(segment))
            for constant_name in re.findall(r"\b[A-Z][A-Z0-9_]*\b", segment):
                refs.update(constant_refs.get(constant_name, []))
            if not refs:
                continue
            method_refs.setdefault(method_name, set()).update(sorted(refs))
            if object_name:
                method_refs.setdefault(f"{object_name}.{method_name}", set()).update(sorted(refs))
    return {key: sorted(value) for key, value in method_refs.items()}


def method_call_refs(text: str, method_refs: dict[str, list[str]]) -> list[str]:
    refs: set[str] = set()
    for object_name, method_name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        specific_refs = method_refs.get(f"{object_name}.{method_name}", [])
        if specific_refs:
            refs.update(specific_refs)
        else:
            refs.update(method_refs.get(method_name, []))
    return sorted(refs)


def export_segments(text: str) -> Iterable[tuple[str, str]]:
    export_re = re.compile(r"(?m)^export\s+(?:const\s+|function\s+)(use[A-Za-z0-9_]+)")
    matches = list(export_re.finditer(text))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        yield match.group(1), text[start:end]


def named_export_segments(text: str) -> Iterable[tuple[str, str]]:
    export_re = re.compile(r"(?m)^export\s+(?:const\s+|function\s+)([A-Za-z_][A-Za-z0-9_]*)")
    matches = list(export_re.finditer(text))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        yield match.group(1), text[start:end]


def extract_hook_api_refs(method_refs: dict[str, list[str]]) -> dict[str, list[str]]:
    if not HOOKS_FILE.exists():
        return {}
    text = HOOKS_FILE.read_text(encoding="utf-8", errors="replace")
    hooks: dict[str, list[str]] = {}
    for hook_name, segment in export_segments(text):
        refs = merge_refs(extract_api_refs(segment), method_call_refs(segment, method_refs))
        if refs:
            hooks[hook_name] = refs
    return hooks


def strip_imports(text: str) -> str:
    return re.sub(r"import\s+(?:.|\n)*?from\s+[\"'][^\"']+[\"'];?", "", text)


def imported_hooks(text: str) -> list[str]:
    hooks: list[str] = []
    for match in re.finditer(r"import\s*\{(?P<names>[^}]+)\}\s*from\s*[\"']@/lib/api/hooks[\"']", text, flags=re.S):
        for raw_name in match.group("names").split(","):
            name = raw_name.strip().split(" as ")[0].strip()
            if name.startswith("use"):
                hooks.append(name)
    body = strip_imports(text)
    return sorted({name for name in hooks if re.search(rf"\b{re.escape(name)}\b", body)})


def resolve_local_module(page: Path, source: str) -> Path | None:
    if source.startswith("@/"):
        target = (FRONTEND_SRC / source[2:]).resolve()
    elif source.startswith("."):
        target = (page.parent / source).resolve()
    else:
        return None
    candidates = [
        target,
        target.with_suffix(".ts"),
        target.with_suffix(".tsx"),
        target / "index.ts",
        target / "index.tsx",
    ]
    for candidate in candidates:
        try:
            candidate.relative_to(REPO)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def local_import_api_refs(page: Path, text: str, method_refs: dict[str, list[str]]) -> list[str]:
    refs: set[str] = set()
    body = strip_imports(text)
    import_re = re.compile(
        r"import\s*\{(?P<names>[^}]+)\}\s*from\s*[\"'](?P<source>(?:\.[^\"']+|@/[^\"']+))[\"']",
        flags=re.S,
    )
    for match in import_re.finditer(text):
        module = resolve_local_module(page, match.group("source"))
        if not module:
            continue
        module_text = module.read_text(encoding="utf-8", errors="replace")
        exported_refs = {
            name: merge_refs(extract_api_refs(segment), method_call_refs(segment, method_refs))
            for name, segment in named_export_segments(module_text)
        }
        for raw_name in match.group("names").split(","):
            name = raw_name.strip().split(" as ")[0].strip()
            if not name or not re.search(rf"\b{re.escape(name)}\b", body):
                continue
            refs.update(exported_refs.get(name, []))
    return sorted(refs)


def extract_client_api_rows(openapi_paths: set[str]) -> list[ApiRow]:
    rows: list[ApiRow] = []
    seen: set[tuple[str, str]] = set()
    for file in CLIENT_FILES:
        if not file.exists():
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        for path in extract_api_refs(text):
            key = (path, str(file.relative_to(REPO)))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                ApiRow(
                    path=path,
                    source_file=str(file.relative_to(REPO)),
                    methods=infer_methods_near_path(text, path),
                    runtime_present=path_matches_openapi(path, openapi_paths),
                )
            )
    return sorted(rows, key=lambda row: (row.source_file, row.path))


def infer_methods_near_path(text: str, path: str) -> list[str]:
    literal = normalize_api_ref(path).replace("{var}", "")
    idx = text.find(literal)
    if idx < 0:
        return ["GET"]
    window = text[max(0, idx - 250) : idx + 500]
    methods = sorted(set(re.findall(r'method:\s*"([A-Z]+)"', window)))
    return methods or ["GET"]


def path_matches_openapi(client_path: str, openapi_paths: set[str]) -> bool:
    if not openapi_paths:
        return False
    client_path = normalize_api_ref(client_path)
    if client_path in openapi_paths:
        return True
    if any(path.startswith(client_path.rstrip("/") + "/") for path in openapi_paths):
        return True
    client_regex = re.escape(client_path)
    client_regex = client_regex.replace(r"\{var\}", r"[^/]+")
    client_regex = client_regex.replace(r"\?", r"\?")
    for path in openapi_paths:
        if re.fullmatch(client_regex, path):
            return True
    normalized = re.sub(r"\{[^}]+\}", "{var}", client_path)
    for path in openapi_paths:
        runtime_normalized = re.sub(r"\{[^}]+\}", "{var}", path)
        if normalized == runtime_normalized:
            return True
    return False


def fetch_openapi(api_base: str, timeout: float) -> set[str]:
    url = api_base.rstrip("/") + "/openapi.json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"WARN: openapi unavailable at {url}: {exc}", file=sys.stderr)
        return set()
    return set(data.get("paths", {}).keys())


def classify_route(api_refs: list[str], runtime_api_refs: list[str], risk_markers: list[str], text: str) -> str:
    if api_refs:
        if len(runtime_api_refs) < len(api_refs):
            return "PARTIAL_API_LINKED"
        return "STATIC_API_LINKED"
    if any(marker in {"stub", "mock", "demo"} for marker in risk_markers):
        return "NEEDS_REVIEW"
    if "redirect(" in text and "next/navigation" in text:
        return "REDIRECT"
    if "CanonicalSurface" in text or "@/data/" in text or "FAQ_ENTRIES" in text:
        return "STATIC_CONTENT"
    return "UI_ONLY_OR_STATIC"


def route_risk_markers(text: str) -> list[str]:
    markers = []
    lower = text.lower()
    token_markers = ["mock", "stub", "demo"]
    for marker in token_markers:
        if re.search(rf"(?<![\w/-]){re.escape(marker)}(?![\w/-])", lower):
            markers.append(marker)
    fallback_risk_phrases = [
        "fallback data",
        "mock fallback",
        "empty fallback",
        "empty fallbacks",
        "offline fallback",
        "defensive fallback",
        "fallback handles",
        "fallback when be",
        "not yet wired",
        "endpoint may not exist",
    ]
    for marker in fallback_risk_phrases:
        if marker in lower:
            markers.append(marker)
    return markers


def route_text_sources(page: Path) -> list[tuple[Path, str]]:
    text = page.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"export\s+\{\s*default\s*\}\s+from\s+[\"'](?P<target>[^\"']+)[\"']", text)
    if not match:
        return [(page, text)]
    target = (page.parent / match.group("target")).resolve()
    candidates = [target, target.with_suffix(".tsx"), target / "page.tsx"]
    for candidate in candidates:
        try:
            candidate.relative_to(REPO)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return [(page, text), (candidate, candidate.read_text(encoding="utf-8", errors="replace"))]
    return [(page, text)]


def extract_routes(openapi_paths: set[str], method_refs: dict[str, list[str]], hook_refs: dict[str, list[str]]) -> list[RouteRow]:
    rows: list[RouteRow] = []
    for page in discover_routes():
        text_sources = route_text_sources(page)
        text = "\n".join(source_text for _, source_text in text_sources)
        direct_refs = extract_api_refs(text)
        client_method_refs = method_call_refs(text, method_refs)
        local_import_refs = merge_refs(
            *(local_import_api_refs(source_page, source_text, method_refs) for source_page, source_text in text_sources)
        )
        route_hook_refs = merge_refs(*(hook_refs.get(name, []) for name in imported_hooks(text)))
        refs = merge_refs(direct_refs, client_method_refs, local_import_refs, route_hook_refs)
        runtime_refs = sorted(ref for ref in refs if path_matches_openapi(ref, openapi_paths))
        markers = route_risk_markers(text)
        sources = {
            "direct_literals": direct_refs,
            "client_methods": client_method_refs,
            "local_imports": local_import_refs,
            "imported_hooks": route_hook_refs,
        }
        rows.append(
            RouteRow(
                route=next_route_from_page(page),
                file=str(page.relative_to(REPO)),
                static_api_refs=refs,
                runtime_api_refs=runtime_refs,
                api_ref_sources={key: value for key, value in sources.items() if value},
                risk_markers=markers,
                classification=classify_route(refs, runtime_refs, markers, text),
            )
        )
    return rows


def write_markdown(path: Path, routes: Iterable[RouteRow], apis: Iterable[ApiRow], openapi_count: int) -> None:
    route_rows = list(routes)
    api_rows = list(apis)
    lines = [
        "# AEIS API/UI Coverage Map",
        "",
        f"- Frontend routes: {len(route_rows)}",
        f"- Client API refs: {len(api_rows)}",
        f"- Runtime OpenAPI paths: {openapi_count}",
        "",
        "## Routes",
        "",
        "| Route | Classification | Risk Markers | API refs | Runtime refs | Sources | File |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in route_rows:
        source_summary = ", ".join(f"{key}:{len(value)}" for key, value in row.api_ref_sources.items()) or "-"
        lines.append(
            f"| `{row.route}` | `{row.classification}` | {', '.join(row.risk_markers) or '-'} | {len(row.static_api_refs)} | {len(row.runtime_api_refs)} | {source_summary} | `{row.file}` |"
        )
    lines.extend(["", "## Client API Refs", "", "| Runtime | Methods | Path | Source |", "|---|---|---|---|"])
    for row in api_rows:
        runtime = "yes" if row.runtime_present else "no"
        lines.append(f"| {runtime} | {','.join(row.methods)} | `{row.path}` | `{row.source_file}` |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.environ.get("AEIS_API_BASE", "http://127.0.0.1:8010"))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    args = parser.parse_args()

    openapi_paths = fetch_openapi(args.api_base, args.timeout)
    method_refs = extract_api_method_refs()
    hook_refs = extract_hook_api_refs(method_refs)
    routes = extract_routes(openapi_paths, method_refs, hook_refs)
    apis = extract_client_api_rows(openapi_paths)
    payload = {
        "repo": str(REPO),
        "frontend_routes": [asdict(row) for row in routes],
        "client_api_refs": [asdict(row) for row in apis],
        "api_method_ref_count": len(method_refs),
        "hook_api_ref_count": len(hook_refs),
        "runtime_openapi_path_count": len(openapi_paths),
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        write_markdown(args.md_out, routes, apis, len(openapi_paths))
    if not args.json_out and not args.md_out:
        sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
