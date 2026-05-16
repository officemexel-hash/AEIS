#!/usr/bin/env python3
"""
SYLION Audit Pipeline — Orchestrator

Pipeline: Księga → Kod → Audyt (4 modele) → Weryfikacja krzyżowa → Scalenie → Patch → Podsumowanie

Wymaga: pip install openhands-sdk openhands-tools openhands-workspace python-dotenv
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, AgentContext, Conversation, Tool, register_agent
from openhands.sdk.context import Skill
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task import TaskToolSet
from openhands.tools.terminal import TerminalTool

from config import (
    AUDIT_MODELS,
    PROMPT_AUDIT,
    PROMPT_CROSS_VERIFY,
    PROMPT_KSIEGA_EXTRACT,
    PROMPT_MERGE_DECISION,
    PROMPT_PATCH,
    PROMPT_SUMMARY,
    ModelConfig,
    PipelineConfig,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"


def setup_logging(level: str, log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("sylion-pipeline")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Helper: create LLM from ModelConfig
# ---------------------------------------------------------------------------

def create_llm(model: ModelConfig) -> LLM:
    return LLM(
        model=model.model_id,
        api_key=SecretStr(model.api_key),
        base_url=model.base_url,
        usage_id=f"sylion-audit-{model.name}",
    )


# ---------------------------------------------------------------------------
# Helper: run a single-shot agent and return its output
# ---------------------------------------------------------------------------

def run_agent_task(
    llm: LLM,
    task: str,
    workspace: Path,
    skills: list[Skill] | None = None,
    system_suffix: str = "",
) -> str:
    """Uruchom agenta z pojedynczym zadaniem i zwróć ostatnią odpowiedź."""
    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=skills or [],
            system_message_suffix=system_suffix,
        ),
    )
    conversation = Conversation(agent=agent, workspace=str(workspace))
    conversation.send_message(task)
    conversation.run()

    # Pobierz ostatni event z odpowiedzią
    for event in reversed(conversation.state.events):
        if hasattr(event, "llm_message"):
            from openhands.sdk.llm import content_to_str
            return "".join(content_to_str(event.llm_message.content))
    return ""


# ---------------------------------------------------------------------------
# Helper: save / load JSON
# ---------------------------------------------------------------------------

def save_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json_from_text(text: str) -> list | dict:
    """Wyciągnij JSON z odpowiedzi agenta (może być otoczony markdown)."""
    import re
    # Szukaj bloku ```json ... ```
    match = re.search(r"```json\s*([\s\S]*?)```", text)
    if match:
        return json.loads(match.group(1))
    # Szukaj surowego JSON (array lub object)
    match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"Nie znaleziono JSON w odpowiedzi:\n{text[:500]}")


# ---------------------------------------------------------------------------
# ETAP 1: Ekstrakcja wymagań z Księgi
# ---------------------------------------------------------------------------

def stage_1_extract_requirements(cfg: PipelineConfig, results_dir: Path, log: logging.Logger) -> list[dict]:
    """Parsuj Księgę i wyekstrahuj weryfikowalne wymagania."""
    log.info("═══ ETAP 1: Ekstrakcja wymagań z Księgi ═══")

    if cfg.ksiega_path and cfg.ksiega_path.exists():
        # Użyj Claude (najlepszy do zrozumienia polskiego dokumentu)
        model = next(m for m in AUDIT_MODELS if m.name == "claude")
        llm = create_llm(model)

        task = f"""{PROMPT_KSIEGA_EXTRACT}

Księga znajduje się w: {cfg.ksiega_path}
Przeczytaj ją i wyekstrahuj wymagania."""

        response = run_agent_task(llm, task, cfg.workspace)
        requirements = extract_json_from_text(response)
    else:
        log.warning("Brak ścieżki do Księgi — używam wbudowanych wymagań domyślnych")
        requirements = _default_requirements()

    save_json(requirements, results_dir / "requirements.json")
    log.info(f"Wyekstrahowano {len(requirements)} wymagań")
    return requirements


def _default_requirements() -> list[dict]:
    """Domyślne wymagania gdy Księga nie jest dostępna."""
    return [
        {"id": "KS-SEC-001", "category": "SECURITY", "priority": "P0",
         "description": "Brak zaufania do X-Forwarded-For — nigdy nie używaj XFF do identyfikacji klienta",
         "verification": "Sprawdź czy kod nie czyta X-Forwarded-For, X-Real-IP bez walidacji"},
        {"id": "KS-SEC-002", "category": "SECURITY", "priority": "P0",
         "description": "HSM-backed key management z wymaganymi PINami",
         "verification": "Sprawdź czy operacje kryptograficzne wymagają HSM PIN"},
        {"id": "KS-SEC-003", "category": "SECURITY", "priority": "P0",
         "description": "Sanityzacja błędów HTTP — brak wycieku informacji wewnętrznych",
         "verification": "Sprawdź czy http.Error nie używa err.Error(), czy nie zwraca stack traces"},
        {"id": "KS-SEC-004", "category": "SECURITY", "priority": "P1",
         "description": "Authenticated /metrics endpoints",
         "verification": "Sprawdź czy /metrics, /debug, /healthz wymagają uwierzytelniania"},
        {"id": "KS-SEC-005", "category": "SECURITY", "priority": "P1",
         "description": "Restrykcyjny CORS — brak wildcardów",
         "verification": "Sprawdź Access-Control-Allow-Origin, nie może być '*' w produkcji"},
        {"id": "KS-ARCH-001", "category": "ARCHITECTURE", "priority": "P1",
         "description": "Route guards per rola/tier na każdym endpoincie",
         "verification": "Sprawdź czy każdy handler ma guard sprawdzający rolę/uprawnienia"},
        {"id": "KS-ARCH-002", "category": "ARCHITECTURE", "priority": "P1",
         "description": "Spójność wersji — go:embed VERSION we wszystkich binarkach",
         "verification": "Sprawdź czy sylion-server, sylion-verify, sylionctl używają go:embed VERSION"},
        {"id": "KS-CRYPTO-001", "category": "CRYPTO", "priority": "P1",
         "description": "Przygotowanie na PQC (post-quantum cryptography)",
         "verification": "Sprawdź czy są abstrakcje kryptograficzne umożliwiające wymianę algorytmów"},
        {"id": "KS-TRANSPORT-001", "category": "TRANSPORT", "priority": "P0",
         "description": "Certyfikowane warstwy transportowe — nie WireGuard w baseline",
         "verification": "Sprawdź czy transport nie zależy od WireGuard"},
        {"id": "KS-DATA-001", "category": "DATA", "priority": "P1",
         "description": "Walidacja i sanityzacja wszystkich danych wejściowych",
         "verification": "Sprawdź binding/parsing requestów, czy są walidatory"},
        {"id": "KS-AUTH-001", "category": "AUTH", "priority": "P0",
         "description": "Dual-admin i panic controls",
         "verification": "Sprawdź czy krytyczne operacje wymagają podwójnej autoryzacji"},
        {"id": "KS-NET-001", "category": "SECURITY", "priority": "P1",
         "description": "Egress whitelisting — jawne listy dozwolonych połączeń wychodzących",
         "verification": "Sprawdź konfigurację połączeń wychodzących, czy jest whitelist"},
    ]


# ---------------------------------------------------------------------------
# ETAP 2: Identyfikacja plików do audytu
# ---------------------------------------------------------------------------

def stage_2_file_manifest(cfg: PipelineConfig, results_dir: Path, log: logging.Logger) -> list[str]:
    """Znajdź pliki Go do audytu."""
    log.info("═══ ETAP 2: Identyfikacja plików do audytu ═══")

    workspace = cfg.workspace
    go_files = []

    if cfg.packages:
        # Audytuj tylko wskazane pakiety
        for pkg in cfg.packages:
            pkg_path = workspace / pkg
            if pkg_path.exists():
                go_files.extend(str(f.relative_to(workspace)) for f in pkg_path.rglob("*.go")
                                if "vendor" not in str(f) and "_test.go" not in f.name)
    else:
        # Wszystkie pliki Go (bez vendor i testów)
        go_files = [str(f.relative_to(workspace)) for f in workspace.rglob("*.go")
                     if "vendor" not in str(f) and "_test.go" not in f.name]

    # Sortuj po pakiecie
    go_files.sort()

    manifest = {
        "total_files": len(go_files),
        "files": go_files,
        "packages": sorted(set(str(Path(f).parent) for f in go_files)),
    }
    save_json(manifest, results_dir / "file_manifest.json")
    log.info(f"Znaleziono {len(go_files)} plików Go w {len(manifest['packages'])} pakietach")
    return go_files


# ---------------------------------------------------------------------------
# ETAP 3: Audyt równoległy przez 4 modele
# ---------------------------------------------------------------------------

async def stage_3_parallel_audit(
    cfg: PipelineConfig,
    requirements: list[dict],
    file_list: list[str],
    results_dir: Path,
    log: logging.Logger,
) -> dict[str, list[dict]]:
    """Uruchom audyt równolegle przez 4 modele."""
    log.info("═══ ETAP 3: Audyt równoległy (4 modele) ═══")

    active_models = cfg.get_active_models()
    req_text = json.dumps(requirements, ensure_ascii=False, indent=2)
    file_text = "\n".join(file_list)

    async def audit_with_model(model: ModelConfig) -> tuple[str, list[dict]]:
        log.info(f"  → Uruchamiam audyt: {model.name} ({model.model_id})")
        t0 = time.monotonic()

        prompt = PROMPT_AUDIT.format(
            requirements=req_text,
            file_list=file_text,
            model_strengths=model.strengths,
        )

        llm = create_llm(model)
        # Uruchom w thread pool (SDK jest synchroniczny)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, run_agent_task, llm, prompt, cfg.workspace
        )

        try:
            findings = extract_json_from_text(response)
        except ValueError:
            log.error(f"  ✗ {model.name}: nie udało się sparsować odpowiedzi")
            findings = []

        elapsed = time.monotonic() - t0
        log.info(f"  ✓ {model.name}: {len(findings)} findings w {elapsed:.0f}s")

        # Dodaj źródło do każdego finding'u
        for f in findings:
            f["source_model"] = model.name

        save_json(findings, results_dir / "audits" / f"audit_{model.name}.json")
        return model.name, findings

    # Uruchom równolegle
    tasks = [audit_with_model(m) for m in active_models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_audits = {}
    for result in results:
        if isinstance(result, Exception):
            log.error(f"  ✗ Błąd audytu: {result}")
        else:
            name, findings = result
            all_audits[name] = findings

    total = sum(len(f) for f in all_audits.values())
    log.info(f"Łącznie: {total} findings z {len(all_audits)} modeli")
    return all_audits


# ---------------------------------------------------------------------------
# ETAP 4: Weryfikacja krzyżowa
# ---------------------------------------------------------------------------

async def stage_4_cross_verify(
    cfg: PipelineConfig,
    all_audits: dict[str, list[dict]],
    file_list: list[str],
    results_dir: Path,
    log: logging.Logger,
) -> dict[str, list[dict]]:
    """Każdy model weryfikuje ustalenia pozostałych 3 modeli."""
    log.info("═══ ETAP 4: Weryfikacja krzyżowa ═══")

    active_models = cfg.get_active_models()
    file_text = "\n".join(file_list)

    async def verify_with_model(
        verifier: ModelConfig, findings_to_verify: list[dict]
    ) -> tuple[str, list[dict]]:
        log.info(f"  → {verifier.name} weryfikuje {len(findings_to_verify)} findings")
        t0 = time.monotonic()

        prompt = PROMPT_CROSS_VERIFY.format(
            findings=json.dumps(findings_to_verify, ensure_ascii=False, indent=2),
            file_list=file_text,
        )

        llm = create_llm(verifier)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, run_agent_task, llm, prompt, cfg.workspace
        )

        try:
            verdicts = extract_json_from_text(response)
        except ValueError:
            log.error(f"  ✗ {verifier.name}: nie udało się sparsować weryfikacji")
            verdicts = []

        elapsed = time.monotonic() - t0
        confirmed = sum(1 for v in verdicts if isinstance(v, dict) and v.get("verdict") == "CONFIRMED")
        log.info(f"  ✓ {verifier.name}: {confirmed}/{len(verdicts)} confirmed w {elapsed:.0f}s")

        save_json(verdicts, results_dir / "cross_verify" / f"verify_{verifier.name}.json")
        return verifier.name, verdicts

    # Dla każdego modelu — weryfikuj findings INNYCH modeli
    tasks = []
    for verifier in active_models:
        other_findings = []
        for model_name, findings in all_audits.items():
            if model_name != verifier.name:
                other_findings.extend(findings)
        tasks.append(verify_with_model(verifier, other_findings))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_verdicts = {}
    for result in results:
        if isinstance(result, Exception):
            log.error(f"  ✗ Błąd weryfikacji: {result}")
        else:
            name, verdicts = result
            all_verdicts[name] = verdicts

    return all_verdicts


# ---------------------------------------------------------------------------
# ETAP 5: Scalenie i decyzja
# ---------------------------------------------------------------------------

def stage_5_merge(
    cfg: PipelineConfig,
    all_audits: dict[str, list[dict]],
    all_verdicts: dict[str, list[dict]],
    results_dir: Path,
    log: logging.Logger,
) -> list[dict]:
    """Scal findings i podejmij decyzje na podstawie konsensusu."""
    log.info("═══ ETAP 5: Scalenie i decyzja ═══")

    # Deduplikacja: grupuj po (file, line ±5, category)
    groups: dict[str, list[dict]] = {}

    for model_name, findings in all_audits.items():
        for f in findings:
            if not isinstance(f, dict):
                continue
            key = f"{f.get('file', '?')}:{f.get('line', 0) // 5}:{f.get('category', '?')}"
            if key not in groups:
                groups[key] = []
            groups[key].append(f)

    # Zbierz verdicts per finding
    verdict_index: dict[str, list[dict]] = {}
    for model_name, verdicts in all_verdicts.items():
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            orig_id = v.get("original_id", "")
            if orig_id not in verdict_index:
                verdict_index[orig_id] = []
            verdict_index[orig_id].append({**v, "verifier": model_name})

    # Podejmij decyzje
    merged: list[dict] = []
    counts = {"ACCEPT": 0, "REVIEW": 0, "SKIP": 0}

    for idx, (key, group) in enumerate(groups.items(), 1):
        # Zlicz ile modeli znalazło ten problem
        source_models = set(f.get("source_model", "?") for f in group)
        num_sources = len(source_models)

        # Zlicz potwierdzenia cross-verify
        confirmed = 0
        disputed = 0
        for f in group:
            fid = f.get("id", "")
            for v in verdict_index.get(fid, []):
                if v.get("verdict") == "CONFIRMED":
                    confirmed += 1
                elif v.get("verdict") == "DISPUTED":
                    disputed += 1

        # Reguła decyzyjna
        total_support = num_sources + confirmed
        if total_support >= cfg.consensus_threshold and disputed == 0:
            decision = "ACCEPT"
        elif total_support >= 2 or (confirmed > 0 and disputed > 0):
            decision = "REVIEW"
        else:
            decision = "SKIP"

        # Wybierz najwyższy severity
        severities = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        max_sev = max(group, key=lambda f: severities.get(f.get("severity", "LOW"), 0))

        merged_finding = {
            "finding_id": f"MERGED-{idx:03d}",
            "original_ids": [f.get("id", "?") for f in group],
            "decision": decision,
            "file": group[0].get("file", "?"),
            "line": group[0].get("line", 0),
            "severity": max_sev.get("severity", "MEDIUM"),
            "category": group[0].get("category", "?"),
            "title": group[0].get("title", "?"),
            "description": "\n---\n".join(f.get("description", "") for f in group),
            "consensus_score": f"{num_sources}/{len(cfg.get_active_models())} models + {confirmed} cross-confirms",
            "source_models": list(source_models),
            "fix_suggestion": group[0].get("fix_suggestion", ""),
        }
        merged.append(merged_finding)
        counts[decision] += 1

    # Sortuj: CRITICAL ACCEPT first
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    decision_order = {"ACCEPT": 0, "REVIEW": 1, "SKIP": 2}
    merged.sort(key=lambda f: (decision_order.get(f["decision"], 9), severity_order.get(f["severity"], 9)))

    save_json(merged, results_dir / "merged_findings.json")
    log.info(f"Scalono: {len(merged)} unikalnych findings")
    log.info(f"  ACCEPT: {counts['ACCEPT']} | REVIEW: {counts['REVIEW']} | SKIP: {counts['SKIP']}")
    return merged


# ---------------------------------------------------------------------------
# ETAP 6: Generowanie patchy
# ---------------------------------------------------------------------------

async def stage_6_patches(
    cfg: PipelineConfig,
    merged: list[dict],
    results_dir: Path,
    log: logging.Logger,
) -> list[dict]:
    """Generuj patche dla findings z decyzją ACCEPT."""
    log.info("═══ ETAP 6: Generowanie patchy ═══")

    if cfg.dry_run:
        log.info("  (dry-run) Pomijam generowanie patchy")
        return []

    accepted = [f for f in merged if f["decision"] == "ACCEPT"]
    log.info(f"  Generuję patche dla {len(accepted)} findings")

    # Użyj Claude do generowania patchy (najlepszy do Go)
    model = next(m for m in AUDIT_MODELS if m.name == "claude")

    async def generate_patch(finding: dict) -> dict | None:
        log.info(f"  → Patch: {finding['finding_id']} ({finding['file']}:{finding['line']})")

        # Odczytaj plik źródłowy
        source_path = cfg.workspace / finding["file"]
        if not source_path.exists():
            log.warning(f"    ✗ Plik nie istnieje: {finding['file']}")
            return None

        source_code = source_path.read_text(encoding="utf-8")

        prompt = PROMPT_PATCH.format(
            finding=json.dumps(finding, ensure_ascii=False, indent=2),
            source_code=source_code[:15000],  # Limit kontekstu
        )

        llm = create_llm(model)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, run_agent_task, llm, prompt, cfg.workspace
        )

        try:
            patch_data = extract_json_from_text(response)
            if isinstance(patch_data, dict):
                # Zapisz patch
                patch_file = results_dir / "patches" / f"{finding['finding_id'].lower()}.patch"
                patch_file.parent.mkdir(parents=True, exist_ok=True)
                patch_file.write_text(patch_data.get("patch", ""), encoding="utf-8")
                log.info(f"    ✓ Patch zapisany: {patch_file.name}")
                return patch_data
        except ValueError:
            log.error(f"    ✗ Nie udało się sparsować patcha dla {finding['finding_id']}")

        return None

    # Generuj patche sekwencyjnie (modyfikują te same pliki)
    patches = []
    for finding in accepted:
        patch = await generate_patch(finding)
        if patch:
            patches.append(patch)

    log.info(f"Wygenerowano {len(patches)}/{len(accepted)} patchy")
    return patches


# ---------------------------------------------------------------------------
# ETAP 7: Podsumowanie
# ---------------------------------------------------------------------------

def stage_7_summary(
    cfg: PipelineConfig,
    requirements: list[dict],
    merged: list[dict],
    patches: list[dict],
    results_dir: Path,
    log: logging.Logger,
) -> str:
    """Wygeneruj końcowy raport audytu."""
    log.info("═══ ETAP 7: Podsumowanie ═══")

    model = next(m for m in AUDIT_MODELS if m.name == "claude")
    llm = create_llm(model)

    pipeline_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models_used": [m.name for m in cfg.get_active_models()],
        "requirements_count": len(requirements),
        "total_findings": len(merged),
        "accepted": len([f for f in merged if f["decision"] == "ACCEPT"]),
        "review": len([f for f in merged if f["decision"] == "REVIEW"]),
        "skipped": len([f for f in merged if f["decision"] == "SKIP"]),
        "patches_generated": len(patches),
        "findings": merged,
        "patches_summary": [
            {"finding_id": p.get("finding_id"), "changelog": p.get("changelog_entry")}
            for p in patches
        ],
    }

    prompt = PROMPT_SUMMARY.format(
        pipeline_results=json.dumps(pipeline_data, ensure_ascii=False, indent=2)
    )

    response = run_agent_task(llm, prompt, cfg.workspace)

    report_path = results_dir / "audit_report.md"
    report_path.write_text(response, encoding="utf-8")
    log.info(f"Raport zapisany: {report_path}")

    return response


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_pipeline(cfg: PipelineConfig) -> None:
    """Uruchom pełny pipeline audytu."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_dir = cfg.results_dir / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    log = setup_logging(cfg.log_level, results_dir / "pipeline.log")
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║         SYLION AUDIT PIPELINE — START                       ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info(f"Workspace:  {cfg.workspace}")
    log.info(f"Modele:     {', '.join(cfg.models)}")
    log.info(f"Konsensus:  {cfg.consensus_threshold}/{len(cfg.models)}")
    log.info(f"Wyniki:     {results_dir}")
    log.info(f"Dry-run:    {cfg.dry_run}")

    t0 = time.monotonic()

    # ETAP 1: Księga → wymagania
    requirements = stage_1_extract_requirements(cfg, results_dir, log)

    # ETAP 2: Kod → lista plików
    file_list = stage_2_file_manifest(cfg, results_dir, log)

    if not file_list:
        log.error("Brak plików Go do audytu — przerywam")
        return

    # ETAP 3: Audyt równoległy (4 modele)
    all_audits = await stage_3_parallel_audit(cfg, requirements, file_list, results_dir, log)

    if not all_audits:
        log.error("Żaden model nie zwrócił wyników — przerywam")
        return

    # ETAP 4: Weryfikacja krzyżowa
    all_verdicts = await stage_4_cross_verify(cfg, all_audits, file_list, results_dir, log)

    # ETAP 5: Scalenie i decyzja
    merged = stage_5_merge(cfg, all_audits, all_verdicts, results_dir, log)

    # ETAP 6: Patch
    patches = await stage_6_patches(cfg, merged, results_dir, log)

    # ETAP 7: Podsumowanie
    summary = stage_7_summary(cfg, requirements, merged, patches, results_dir, log)

    elapsed = time.monotonic() - t0
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║         SYLION AUDIT PIPELINE — ZAKOŃCZONY                  ║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info(f"Czas:       {elapsed:.0f}s ({elapsed / 60:.1f} min)")
    log.info(f"Findings:   {len(merged)} (ACCEPT: {sum(1 for f in merged if f['decision']=='ACCEPT')})")
    log.info(f"Patche:     {len(patches)}")
    log.info(f"Raport:     {results_dir / 'audit_report.md'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SYLION Audit Pipeline — wielomodelowy audyt bezpieczeństwa"
    )
    parser.add_argument(
        "--workspace", "-w", type=Path, required=True,
        help="Ścieżka do repozytorium SYLION"
    )
    parser.add_argument(
        "--ksiega", "-k", type=Path, default=None,
        help="Ścieżka do dokumentu Księgi (PDF/TXT)"
    )
    parser.add_argument(
        "--packages", "-p", type=str, default="",
        help="Pakiety do audytu (oddzielone przecinkiem, np. internal/api,pkg/broker)"
    )
    parser.add_argument(
        "--models", "-m", type=str, default="claude,gpt,gemini,deepseek",
        help="Modele do użycia (oddzielone przecinkiem)"
    )
    parser.add_argument(
        "--consensus", "-c", type=int, default=3,
        help="Próg konsensusu (domyślnie 3 z 4)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nie generuj patchy (tylko audyt i raport)"
    )
    parser.add_argument(
        "--results-dir", "-r", type=Path, default=Path("./results"),
        help="Katalog wyników"
    )
    parser.add_argument(
        "--log-level", "-l", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    args = parser.parse_args()

    cfg = PipelineConfig(
        workspace=args.workspace.resolve(),
        ksiega_path=args.ksiega.resolve() if args.ksiega else None,
        packages=[p.strip() for p in args.packages.split(",") if p.strip()],
        models=[m.strip() for m in args.models.split(",")],
        consensus_threshold=args.consensus,
        dry_run=args.dry_run,
        results_dir=args.results_dir,
        log_level=args.log_level,
    )

    asyncio.run(run_pipeline(cfg))


if __name__ == "__main__":
    main()
