#!/usr/bin/env python3
"""
SYLION AEIS -- Canonical Module Manifest Generator

Auto-generates JSON manifests for all 81 modules across 15 classes (A-O).
Each manifest validates against contracts/manifest_schema.json.

Usage:
    python -m sylion.contracts.generate_manifests
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema validation (uses jsonschema if available, falls back to manual)
# ---------------------------------------------------------------------------

SCHEMA_PATH = Path(__file__).parent / "manifest_schema.json"
MANIFESTS_DIR = Path(__file__).parent / "manifests"
SYLION_ROOT = Path(__file__).resolve().parents[2]  # sylion/ package root

# ---------------------------------------------------------------------------
# Package-to-class mapping
# ---------------------------------------------------------------------------

PACKAGE_KIND = {
    "core":       "A",
    "cognitive":  "B",
    "execution":  "C",
    "memory":     "D",
    "governance": "E",
    "security":   "F",
    "efficiency": "G",
    "aeis":       "H",
    "skills":     "I",
    "surface":    "J",
    "rebuild":    "K",
    "quality":    "L",
    "devices":    "M",
    "sdr":        "N",
    "cellular":   "O",
}

# Packages that are infrastructure/surface, not counted as "modules"
SKIP_PACKAGES = {"api", "db", "contracts"}

# ---------------------------------------------------------------------------
# Module metadata: owner_plan, decision_class, security_profile, description
# ---------------------------------------------------------------------------

MODULE_META: dict[str, dict] = {
    # ── A: Core (8 modules) ──────────────────────────────────────────────
    "core.event_bus": {
        "owner_plan": "P01",
        "decision_class_entry": "D0",
        "security_profile": "dev-light",
        "description": "Pub/sub event backbone. SQLite-backed (NATS JetStream later). Event taxonomy: domain.event.action",
    },
    "core.module_registry": {
        "owner_plan": "P01",
        "decision_class_entry": "D0",
        "security_profile": "dev-light",
        "description": "Single source of truth about living modules. Module lifecycle state machine.",
    },
    "core.evidence_spine": {
        "owner_plan": "P02",
        "decision_class_entry": "D0",
        "security_profile": "dev-light",
        "description": "Immutable hash-chain audit log. SHA-256 chain with tamper-evident evidence entries.",
    },
    "core.decision_gate_engine": {
        "owner_plan": "P04",
        "decision_class_entry": "D0",
        "security_profile": "dev-light",
        "description": "Classifies changes D0-D5 and evaluates governance gates. Foundation of governance.",
    },
    "core.contract_registry": {
        "owner_plan": "P06",
        "decision_class_entry": "D0",
        "security_profile": "dev-light",
        "description": "Versioned repository of inter-module contracts. Detects breaking changes.",
    },
    "core.bundle_assembler": {
        "owner_plan": "P01",
        "decision_class_entry": "D1",
        "security_profile": "dev-light",
        "description": "Assemble, validate, and ship module bundles for coordinated deployment.",
    },
    "core.manifest_loader": {
        "owner_plan": "P01",
        "decision_class_entry": "D0",
        "security_profile": "dev-light",
        "description": "Parse and validate module.yaml manifests against canonical schema.",
    },
    "core.environment_orchestrator": {
        "owner_plan": "P09",
        "decision_class_entry": "D1",
        "security_profile": "dev-light",
        "description": "Manage module deployment lifecycle with shadow->dual->cutover transitions.",
    },
    # ── B: Cognitive (7 modules) ─────────────────────────────────────────
    "cognitive.planner": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Multi-agent planning engine. Decomposes goals into executable task trees.",
    },
    "cognitive.evaluator": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Evaluates plan quality, feasibility, and alignment with constraints.",
    },
    "cognitive.reasoner": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Logical reasoning engine with chain-of-thought and formal verification hooks.",
    },
    "cognitive.context_builder": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Builds execution context from memory, evidence, and system state.",
    },
    "cognitive.model_router": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Routes LLM requests to optimal model based on task type and cost envelope.",
    },
    "cognitive.llm_adapter": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Unified adapter for LLM providers (OpenAI, Anthropic, local). Token tracking.",
    },
    "cognitive.code_agent": {
        "owner_plan": "P01",
        "decision_class_entry": "D3",
        "description": "Autonomous code generation and modification agent with sandbox execution.",
    },
    # ── C: Execution (6 modules) ─────────────────────────────────────────
    "execution.tool_runner": {
        "owner_plan": "P08",
        "decision_class_entry": "D2",
        "description": "Executes registered tools with input validation and output capture.",
    },
    "execution.connector_framework": {
        "owner_plan": "P08",
        "decision_class_entry": "D2",
        "description": "Plugin framework for external system connectors (REST, gRPC, DB).",
    },
    "execution.workflow_engine": {
        "owner_plan": "P08",
        "decision_class_entry": "D2",
        "description": "DAG-based workflow orchestration with parallel execution and checkpointing.",
    },
    "execution.job_runner": {
        "owner_plan": "P08",
        "decision_class_entry": "D2",
        "description": "Background job execution with priority queues and resource limits.",
    },
    "execution.adapter_bus": {
        "owner_plan": "P08",
        "decision_class_entry": "D2",
        "description": "Message bus for inter-adapter communication with protocol translation.",
    },
    "execution.retry_orchestrator": {
        "owner_plan": "P08",
        "decision_class_entry": "D2",
        "description": "Exponential backoff retry with circuit breaker and dead-letter queue.",
    },
    # ── D: Memory (7 modules) ────────────────────────────────────────────
    "memory.kanon_access": {
        "owner_plan": "P12",
        "decision_class_entry": "D2",
        "description": "Access layer for Ksiega (Kanon) sections. Versioned knowledge base.",
    },
    "memory.compact_layer": {
        "owner_plan": "P12",
        "decision_class_entry": "D2",
        "description": "Compaction and summarization layer for long-term memory storage.",
    },
    "memory.evidence_store": {
        "owner_plan": "P12",
        "decision_class_entry": "D2",
        "description": "Structured evidence storage with link to EvidenceSpine hash chain.",
    },
    "memory.indexer": {
        "owner_plan": "P12",
        "decision_class_entry": "D2",
        "description": "Full-text and semantic indexing for memory retrieval.",
    },
    "memory.retrieval": {
        "owner_plan": "P12",
        "decision_class_entry": "D2",
        "description": "Unified retrieval interface combining keyword, semantic, and graph search.",
    },
    "memory.self_model_store": {
        "owner_plan": "P12",
        "decision_class_entry": "D3",
        "description": "Persistent store for self-model (capabilities, limits, identity).",
    },
    "memory.kb_adapter": {
        "owner_plan": "P12",
        "decision_class_entry": "D2",
        "description": "Adapter for external knowledge base integrations (vector DB, graph DB).",
    },
    # ── E: Governance (7 modules) ────────────────────────────────────────
    "governance.decision_ladder": {
        "owner_plan": "P05",
        "decision_class_entry": "D3",
        "description": "Implements the D0-D5 decision classification ladder with auto-routing.",
    },
    "governance.council_workflow": {
        "owner_plan": "P05",
        "decision_class_entry": "D3",
        "description": "Council voting workflow: propose, deliberate, vote, ratify.",
    },
    "governance.roles": {
        "owner_plan": "P05",
        "decision_class_entry": "D2",
        "description": "Role-based access control for governance actors (Agent, Board, Council, Human).",
    },
    "governance.gates_registry": {
        "owner_plan": "P05",
        "decision_class_entry": "D2",
        "description": "Registry of governance gates (G-xxx) with enable/disable and evaluation.",
    },
    "governance.evidence_workflow": {
        "owner_plan": "P05",
        "decision_class_entry": "D2",
        "description": "Evidence collection, review, and chain-of-custody workflow.",
    },
    "governance.policy_registry": {
        "owner_plan": "P05",
        "decision_class_entry": "D2",
        "description": "Central policy registry with versioning and enforcement hooks.",
    },
    "governance.self_explanation_validator": {
        "owner_plan": "P05",
        "decision_class_entry": "D3",
        "description": "Validates that system decisions include adequate self-explanations.",
    },
    # ── F: Security (9 modules) ──────────────────────────────────────────
    "security.auth_provider": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Authentication provider supporting bootstrap, session, OIDC modes.",
    },
    "security.bootstrap_init": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Bootstrap initialization for security subsystem. First-run setup.",
    },
    "security.session_broker": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Session management with timeout, rotation, and concurrent limits.",
    },
    "security.policy_engine": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Policy evaluation engine. Enforces security policies at runtime.",
    },
    "security.execution_guard": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Guards code execution with sandboxing and resource limits.",
    },
    "security.secret_provider": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Secret management with rotation, vault integration, and access audit.",
    },
    "security.audit_sink": {
        "owner_plan": "P07",
        "decision_class_entry": "D4",
        "security_profile": "staging-strict",
        "description": "Immutable audit log sink. All security events flow here.",
    },
    "security.phantom_wrapper": {
        "owner_plan": "P07",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Phantom/sandbox execution wrapper for untrusted code paths.",
    },
    "security.profiles": {
        "owner_plan": "P07",
        "decision_class_entry": "D0",
        "security_profile": "staging-strict",
        "description": "Security profile definitions for dev, test, staging, prod environments.",
    },
    # ── G: Efficiency (4 modules) ────────────────────────────────────────
    "efficiency.code_bloat": {
        "owner_plan": "P10",
        "decision_class_entry": "D2",
        "description": "Tracks code size, complexity, and duplication metrics.",
    },
    "efficiency.runtime_perf": {
        "owner_plan": "P10",
        "decision_class_entry": "D2",
        "description": "Runtime performance monitoring with latency histograms and throughput.",
    },
    "efficiency.memory_footprint": {
        "owner_plan": "P10",
        "decision_class_entry": "D2",
        "description": "Memory usage tracking and leak detection across modules.",
    },
    "efficiency.cost_envelope": {
        "owner_plan": "P11",
        "decision_class_entry": "D3",
        "description": "LLM cost tracking with budget envelopes and per-task allocation.",
    },
    # ── H: AEIS Self (4 modules) ─────────────────────────────────────────
    "aeis.self_observation": {
        "owner_plan": "P16",
        "decision_class_entry": "D3",
        "description": "Real-time self-observation of system state, performance, and health.",
    },
    "aeis.improvement_queue": {
        "owner_plan": "P16",
        "decision_class_entry": "D3",
        "description": "Priority queue of self-improvement proposals with evidence requirements.",
    },
    "aeis.self_explanation": {
        "owner_plan": "P16",
        "decision_class_entry": "D3",
        "description": "Generates human-readable explanations of system decisions and behavior.",
    },
    "aeis.self_limitation": {
        "owner_plan": "P16",
        "decision_class_entry": "D5",
        "description": "Enforces hard limits on system capabilities. Cannot be bypassed.",
    },
    "aeis.self_preservation": {
        "owner_plan": "P16",
        "decision_class_entry": "D5",
        "description": "Protects system integrity. Detects and prevents self-modification attacks.",
    },
    # ── I: Skills (3 modules) ────────────────────────────────────────────
    "skills.registry": {
        "owner_plan": "P15",
        "decision_class_entry": "D2",
        "description": "Registry of available skills with metadata and versioning.",
    },
    "skills.executor": {
        "owner_plan": "P15",
        "decision_class_entry": "D2",
        "description": "Executes skill invocations with input validation and output capture.",
    },
    "skills.demand_signal": {
        "owner_plan": "P15",
        "decision_class_entry": "D2",
        "description": "Analyzes skill usage patterns and generates demand signals.",
    },
    # ── J: Surface (3 modules) ───────────────────────────────────────────
    "surface.console_api": {
        "owner_plan": "P13",
        "decision_class_entry": "D2",
        "description": "REST API surface for console/management operations.",
    },
    "surface.console_ui": {
        "owner_plan": "P13",
        "decision_class_entry": "D2",
        "description": "Web UI console for system monitoring and control.",
    },
    "surface.ws_gateway": {
        "owner_plan": "P13",
        "decision_class_entry": "D2",
        "description": "WebSocket gateway for real-time event streaming to clients.",
    },
    # ── K: Rebuild (4 modules) ───────────────────────────────────────────
    "rebuild.orchestrator": {
        "owner_plan": "P14",
        "decision_class_entry": "D3",
        "description": "Orchestrates module rebuild lifecycle: plan, execute, validate.",
    },
    "rebuild.lpw_manager": {
        "owner_plan": "P14",
        "decision_class_entry": "D3",
        "description": "Last-Processed-Window manager for zero-data-loss rebuild transitions.",
    },
    "rebuild.cutover_controller": {
        "owner_plan": "P14",
        "decision_class_entry": "D4",
        "description": "Controls cutover from old to new module implementation.",
    },
    "rebuild.cft_runner": {
        "owner_plan": "P17",
        "decision_class_entry": "D4",
        "description": "Cross-Functional Test runner for rebuild validation.",
    },
    # ── L: Quality (3 modules) ───────────────────────────────────────────
    "quality.golden_set_registry": {
        "owner_plan": "P18",
        "decision_class_entry": "D2",
        "description": "Registry of golden test sets with expected outputs and thresholds.",
    },
    "quality.test_runner": {
        "owner_plan": "P18",
        "decision_class_entry": "D2",
        "description": "Test execution engine with golden set comparison and reporting.",
    },
    "quality.regression_detector": {
        "owner_plan": "P18",
        "decision_class_entry": "D2",
        "description": "Detects regressions by comparing current results against golden sets.",
    },
    # ── M: Devices (4 modules) ───────────────────────────────────────────
    "devices.device_discovery": {
        "owner_plan": "P19",
        "decision_class_entry": "D2",
        "description": "Discovers devices on the network via multiple protocols.",
    },
    "devices.device_registry": {
        "owner_plan": "P19",
        "decision_class_entry": "D2",
        "description": "Registry of known devices with capabilities and status tracking.",
    },
    "devices.artifact_deployer": {
        "owner_plan": "P19",
        "decision_class_entry": "D3",
        "description": "Deploys artifacts to target devices with rollback support.",
    },
    "devices.test_harness": {
        "owner_plan": "P19",
        "decision_class_entry": "D2",
        "description": "On-device test execution harness with result collection.",
    },
    # ── N: SDR (5 modules) ───────────────────────────────────────────────
    "sdr.sdr_gateway": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "SDR hardware gateway. Manages radio interfaces and capture sessions.",
    },
    "sdr.capture_orchestrator": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "Orchestrates multi-channel RF capture with scheduling and coordination.",
    },
    "sdr.signal_analyzer": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "Signal analysis: spectral, temporal, modulation classification.",
    },
    "sdr.protocol_decoder": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "Protocol identification and decoding for known RF protocols.",
    },
    "sdr.rf_safety_governor": {
        "owner_plan": "P20",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "RF safety governor. Enforces transmission limits and compliance.",
    },
    # ── O: Cellular (7 modules) ──────────────────────────────────────────
    "cellular.ran_lab": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "RAN (Radio Access Network) lab emulation with gNB and UE simulation.",
    },
    "cellular.core_network": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "Core network emulation: AMF, SMF, UPF, and subscriber management.",
    },
    "cellular.ue_emulator": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "User Equipment emulator with attach/detach and mobility simulation.",
    },
    "cellular.rf_isolation": {
        "owner_plan": "P20",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "RF isolation validation for lab environment safety compliance.",
    },
    "cellular.attack_vectors": {
        "owner_plan": "P20",
        "decision_class_entry": "D5",
        "security_profile": "staging-strict",
        "description": "Library of known cellular attack vectors for security testing.",
    },
    "cellular.control_plane": {
        "owner_plan": "P20",
        "decision_class_entry": "D4",
        "description": "Control plane message analysis and protocol fuzzing.",
    },
    "cellular.evidence_writer": {
        "owner_plan": "P20",
        "decision_class_entry": "D3",
        "description": "Writes cellular test evidence to EvidenceSpine with structured payloads.",
    },
}

# ---------------------------------------------------------------------------
# Dependency map (from source analysis)
# ---------------------------------------------------------------------------

DEPENDS_ON: dict[str, list[str]] = {
    # Core
    "core.event_bus": [],
    "core.module_registry": [],
    "core.evidence_spine": ["core.event_bus"],
    "core.decision_gate_engine": ["core.event_bus"],
    "core.contract_registry": ["core.event_bus"],
    "core.bundle_assembler": ["core.event_bus", "core.module_registry"],
    "core.manifest_loader": ["core.module_registry", "core.contract_registry"],
    "core.environment_orchestrator": ["core.event_bus", "core.module_registry", "core.bundle_assembler"],
    # Cognitive
    "cognitive.planner": ["core.event_bus"],
    "cognitive.evaluator": ["core.event_bus"],
    "cognitive.reasoner": ["core.event_bus"],
    "cognitive.context_builder": ["core.event_bus"],
    "cognitive.model_router": ["core.event_bus"],
    "cognitive.llm_adapter": ["core.event_bus"],
    "cognitive.code_agent": ["core.event_bus"],
    # Execution
    "execution.tool_runner": ["core.event_bus"],
    "execution.connector_framework": ["core.event_bus"],
    "execution.workflow_engine": ["core.event_bus"],
    "execution.job_runner": ["core.event_bus"],
    "execution.adapter_bus": ["core.event_bus"],
    "execution.retry_orchestrator": ["core.event_bus"],
    # Memory
    "memory.kanon_access": ["core.event_bus"],
    "memory.compact_layer": ["core.event_bus"],
    "memory.evidence_store": ["core.event_bus", "core.evidence_spine"],
    "memory.indexer": ["core.event_bus"],
    "memory.retrieval": ["core.event_bus", "memory.indexer"],
    "memory.self_model_store": ["core.event_bus"],
    "memory.kb_adapter": ["core.event_bus"],
    # Governance
    "governance.decision_ladder": ["core.event_bus", "core.evidence_spine", "core.decision_gate_engine"],
    "governance.council_workflow": ["core.event_bus", "core.evidence_spine", "core.decision_gate_engine"],
    "governance.roles": ["core.event_bus"],
    "governance.gates_registry": ["core.event_bus", "core.decision_gate_engine"],
    "governance.evidence_workflow": ["core.event_bus", "core.evidence_spine"],
    "governance.policy_registry": ["core.event_bus"],
    "governance.self_explanation_validator": ["core.event_bus"],
    # Security
    "security.auth_provider": ["core.event_bus"],
    "security.bootstrap_init": ["core.event_bus"],
    "security.session_broker": ["core.event_bus"],
    "security.policy_engine": ["core.event_bus"],
    "security.execution_guard": ["core.event_bus"],
    "security.secret_provider": ["core.event_bus"],
    "security.audit_sink": ["core.event_bus"],
    "security.phantom_wrapper": ["core.event_bus"],
    "security.profiles": [],
    # Efficiency
    "efficiency.code_bloat": ["core.event_bus"],
    "efficiency.runtime_perf": ["core.event_bus"],
    "efficiency.memory_footprint": ["core.event_bus"],
    "efficiency.cost_envelope": ["core.event_bus"],
    # AEIS
    "aeis.self_observation": ["core.event_bus"],
    "aeis.improvement_queue": ["core.event_bus"],
    "aeis.self_explanation": ["core.event_bus"],
    "aeis.self_limitation": ["core.event_bus"],
    "aeis.self_preservation": ["core.event_bus"],
    # Skills
    "skills.registry": ["core.event_bus"],
    "skills.executor": ["core.event_bus"],
    "skills.demand_signal": ["core.event_bus"],
    # Surface
    "surface.console_api": ["core.event_bus"],
    "surface.console_ui": ["core.event_bus"],
    "surface.ws_gateway": ["core.event_bus"],
    # Rebuild
    "rebuild.orchestrator": ["core.event_bus"],
    "rebuild.lpw_manager": ["core.event_bus"],
    "rebuild.cutover_controller": ["core.event_bus"],
    "rebuild.cft_runner": ["core.event_bus"],
    # Quality
    "quality.golden_set_registry": ["core.event_bus"],
    "quality.test_runner": ["core.event_bus"],
    "quality.regression_detector": ["core.event_bus"],
    # Devices
    "devices.device_discovery": ["core.event_bus"],
    "devices.device_registry": ["core.event_bus"],
    "devices.artifact_deployer": ["core.event_bus"],
    "devices.test_harness": ["core.event_bus"],
    # SDR
    "sdr.sdr_gateway": ["core.event_bus"],
    "sdr.capture_orchestrator": ["core.event_bus", "sdr.rf_safety_governor"],
    "sdr.signal_analyzer": ["core.event_bus"],
    "sdr.protocol_decoder": ["core.event_bus"],
    "sdr.rf_safety_governor": ["core.event_bus"],
    # Cellular
    "cellular.ran_lab": ["core.event_bus"],
    "cellular.core_network": ["core.event_bus"],
    "cellular.ue_emulator": ["core.event_bus"],
    "cellular.rf_isolation": ["core.event_bus"],
    "cellular.attack_vectors": ["core.event_bus"],
    "cellular.control_plane": ["core.event_bus"],
    "cellular.evidence_writer": ["core.event_bus"],
}

# ---------------------------------------------------------------------------
# Event publication map (from source scanning of topic= literals)
# ---------------------------------------------------------------------------

PUBLISHES_EVENTS: dict[str, list[str]] = {
    "core.event_bus": [],
    "core.module_registry": ["module.registered", "module.deregistered", "module.lifecycle.transition"],
    "core.evidence_spine": ["evidence.appended"],
    "core.decision_gate_engine": ["decision.classified"],
    "core.contract_registry": ["contract.published"],
    "core.bundle_assembler": ["bundle.assembled"],
    "core.manifest_loader": [],
    "core.environment_orchestrator": ["environment.deployed"],
    "cognitive.planner": ["cognitive.plan.created", "cognitive.plan.updated", "cognitive.plan.completed"],
    "cognitive.evaluator": ["cognitive.evaluation.completed"],
    "cognitive.reasoner": ["cognitive.reasoning.step", "cognitive.reasoning.completed"],
    "cognitive.context_builder": ["cognitive.context.built"],
    "cognitive.model_router": ["cognitive.model.selected", "cognitive.model.fallback"],
    "cognitive.llm_adapter": ["cognitive.llm.request", "cognitive.llm.response"],
    "cognitive.code_agent": ["cognitive.code.generated", "cognitive.code.executed"],
    "execution.tool_runner": ["execution.tool.started", "execution.tool.completed", "execution.tool.failed"],
    "execution.connector_framework": ["execution.connector.connected", "execution.connector.disconnected"],
    "execution.workflow_engine": ["execution.workflow.started", "execution.workflow.completed", "execution.workflow.failed"],
    "execution.job_runner": ["execution.job.queued", "execution.job.completed", "execution.job.failed"],
    "execution.adapter_bus": ["execution.adapter.message", "execution.adapter.error"],
    "execution.retry_orchestrator": ["execution.retry.attempt", "execution.retry.exhausted", "execution.circuit.state"],
    "memory.kanon_access": ["memory.kanon.read", "memory.kanon.updated"],
    "memory.compact_layer": ["memory.compaction.started", "memory.compaction.completed"],
    "memory.evidence_store": ["memory.evidence.stored", "memory.evidence.linked"],
    "memory.indexer": ["memory.index.updated", "memory.index.rebuilt"],
    "memory.retrieval": ["memory.retrieval.query", "memory.retrieval.result"],
    "memory.self_model_store": ["memory.self_model.updated", "memory.self_model.snapshot"],
    "memory.kb_adapter": ["memory.kb.sync", "memory.kb.query"],
    "governance.decision_ladder": ["governance.decision.proposed", "governance.decision.classified"],
    "governance.council_workflow": ["governance.council.proposed", "governance.council.vote", "governance.council.ratified"],
    "governance.roles": ["governance.role.assigned", "governance.role.revoked"],
    "governance.gates_registry": ["governance.gate.registered", "governance.gate.evaluated"],
    "governance.evidence_workflow": ["governance.evidence.collected", "governance.evidence.reviewed"],
    "governance.policy_registry": ["governance.policy.created", "governance.policy.updated"],
    "governance.self_explanation_validator": ["governance.self_explanation.validated", "governance.self_explanation.rejected"],
    "security.auth_provider": ["security.auth.login", "security.auth.logout", "security.auth.failed"],
    "security.bootstrap_init": ["security.bootstrap.initialized", "security.bootstrap.key_rotated"],
    "security.session_broker": ["security.session.created", "security.session.expired", "security.session.revoked"],
    "security.policy_engine": ["security.policy.evaluated", "security.policy.violation"],
    "security.execution_guard": ["security.guard.blocked", "security.guard.allowed"],
    "security.secret_provider": ["security.secret.accessed", "security.secret.rotated"],
    "security.audit_sink": ["security.audit.event", "security.audit.alert"],
    "security.phantom_wrapper": ["security.phantom.executed", "security.phantom.violation"],
    "security.profiles": [],
    "efficiency.code_bloat": ["efficiency.bloat.measured", "efficiency.bloat.threshold"],
    "efficiency.runtime_perf": ["efficiency.perf.sample", "efficiency.perf.alert"],
    "efficiency.memory_footprint": ["efficiency.memory.sample", "efficiency.memory.leak_detected"],
    "efficiency.cost_envelope": ["efficiency.cost.tracked", "efficiency.cost.over_budget"],
    "aeis.self_observation": ["aeis.observation.snapshot", "aeis.observation.anomaly"],
    "aeis.improvement_queue": ["aeis.improvement.proposed", "aeis.improvement.prioritized"],
    "aeis.self_explanation": ["aeis.explanation.generated", "aeis.explanation.approved"],
    "aeis.self_limitation": ["aeis.limitation.enforced", "aeis.limitation.violation"],
    "aeis.self_preservation": ["aeis.preservation.check", "aeis.preservation.integrity_alert"],
    "skills.registry": ["skills.skill.registered", "skills.skill.deregistered"],
    "skills.executor": ["skills.execution.started", "skills.execution.completed"],
    "skills.demand_signal": ["skills.demand.detected", "skills.demand.trend"],
    "surface.console_api": ["surface.api.request", "surface.api.response"],
    "surface.console_ui": ["surface.ui.render", "surface.ui.interaction"],
    "surface.ws_gateway": ["surface.ws.connected", "surface.ws.disconnected", "surface.ws.message"],
    "rebuild.orchestrator": ["rebuild.plan.created", "rebuild.plan.completed"],
    "rebuild.lpw_manager": ["rebuild.lpw.checkpoint", "rebuild.lpw.replay"],
    "rebuild.cutover_controller": ["rebuild.cutover.started", "rebuild.cutover.completed", "rebuild.cutover.rollback"],
    "rebuild.cft_runner": ["rebuild.cft.started", "rebuild.cft.passed", "rebuild.cft.failed"],
    "quality.golden_set_registry": ["quality.golden_set.registered", "quality.golden_set.updated"],
    "quality.test_runner": ["quality.test.started", "quality.test.completed"],
    "quality.regression_detector": ["quality.regression.detected", "quality.regression.cleared"],
    "devices.device_discovery": ["devices.discovery.found", "devices.discovery.lost"],
    "devices.device_registry": ["devices.device.registered", "devices.device.status"],
    "devices.artifact_deployer": ["devices.deployment.started", "devices.deployment.completed"],
    "devices.test_harness": ["devices.test.started", "devices.test.completed"],
    "sdr.sdr_gateway": ["sdr.gateway.started", "sdr.gateway.capture"],
    "sdr.capture_orchestrator": ["sdr.capture.started", "sdr.capture.completed"],
    "sdr.signal_analyzer": ["sdr.signal.detected", "sdr.signal.classified"],
    "sdr.protocol_decoder": ["sdr.protocol.identified", "sdr.protocol.decoded"],
    "sdr.rf_safety_governor": ["sdr.safety.check", "sdr.safety.violation"],
    "cellular.ran_lab": ["cellular.ran.started", "cellular.ran.measurement"],
    "cellular.core_network": ["cellular.core.attached", "cellular.core.session"],
    "cellular.ue_emulator": ["cellular.ue.attached", "cellular.ue.detached"],
    "cellular.rf_isolation": ["cellular.rf.validation", "cellular.rf.violation"],
    "cellular.attack_vectors": ["cellular.attack.executed", "cellular.attack.result"],
    "cellular.control_plane": ["cellular.cp.message", "cellular.cp.anomaly"],
    "cellular.evidence_writer": ["cellular.evidence.written", "cellular.evidence.chained"],
}

# ---------------------------------------------------------------------------
# Consumed events (inferred from governance/observability patterns)
# ---------------------------------------------------------------------------

CONSUMES_EVENTS: dict[str, list[str]] = {
    "core.event_bus": [],
    "core.module_registry": [],
    "core.evidence_spine": [],
    "core.decision_gate_engine": [],
    "core.contract_registry": [],
    "core.bundle_assembler": [],
    "core.manifest_loader": [],
    "core.environment_orchestrator": [],
    # Cognitive consumes evidence events for reasoning
    "cognitive.planner": ["governance.decision.classified", "aeis.improvement.proposed"],
    "cognitive.evaluator": ["cognitive.plan.created", "execution.workflow.completed"],
    "cognitive.reasoner": ["cognitive.context.built", "memory.retrieval.result"],
    "cognitive.context_builder": ["memory.kanon.read", "memory.retrieval.result"],
    "cognitive.model_router": ["efficiency.cost.tracked"],
    "cognitive.llm_adapter": ["cognitive.model.selected"],
    "cognitive.code_agent": ["cognitive.plan.created", "security.guard.allowed"],
    # Execution
    "execution.tool_runner": ["cognitive.code.generated"],
    "execution.connector_framework": [],
    "execution.workflow_engine": ["execution.tool.completed", "execution.job.completed"],
    "execution.job_runner": ["execution.workflow.started"],
    "execution.adapter_bus": [],
    "execution.retry_orchestrator": ["execution.tool.failed", "execution.job.failed"],
    # Memory
    "memory.kanon_access": [],
    "memory.compact_layer": ["memory.evidence.stored", "memory.index.updated"],
    "memory.evidence_store": ["evidence.appended"],
    "memory.indexer": ["memory.evidence.stored", "memory.kanon.updated"],
    "memory.retrieval": [],
    "memory.self_model_store": ["aeis.observation.snapshot", "aeis.limitation.enforced"],
    "memory.kb_adapter": [],
    # Governance
    "governance.decision_ladder": ["decision.classified"],
    "governance.council_workflow": ["governance.decision.proposed", "governance.evidence.collected"],
    "governance.roles": [],
    "governance.gates_registry": ["governance.gate.registered"],
    "governance.evidence_workflow": ["evidence.appended", "memory.evidence.stored"],
    "governance.policy_registry": [],
    "governance.self_explanation_validator": ["aeis.explanation.generated"],
    # Security
    "security.auth_provider": [],
    "security.bootstrap_init": [],
    "security.session_broker": ["security.auth.login", "security.auth.logout"],
    "security.policy_engine": ["governance.policy.updated"],
    "security.execution_guard": ["security.policy.evaluated"],
    "security.secret_provider": [],
    "security.audit_sink": ["security.auth.login", "security.auth.failed", "security.policy.violation", "security.guard.blocked"],
    "security.phantom_wrapper": ["security.guard.allowed"],
    "security.profiles": [],
    # Efficiency
    "efficiency.code_bloat": [],
    "efficiency.runtime_perf": [],
    "efficiency.memory_footprint": [],
    "efficiency.cost_envelope": ["cognitive.llm.response"],
    # AEIS
    "aeis.self_observation": ["module.registered", "environment.deployed"],
    "aeis.improvement_queue": ["aeis.observation.anomaly", "efficiency.bloat.threshold", "efficiency.perf.alert"],
    "aeis.self_explanation": ["decision.classified", "governance.council.ratified"],
    "aeis.self_limitation": [],
    "aeis.self_preservation": ["aeis.limitation.violation", "security.policy.violation"],
    # Skills
    "skills.registry": [],
    "skills.executor": ["skills.demand.detected"],
    "skills.demand_signal": ["skills.execution.completed"],
    # Surface
    "surface.console_api": [],
    "surface.console_ui": [],
    "surface.ws_gateway": ["module.registered", "decision.classified", "environment.deployed"],
    # Rebuild
    "rebuild.orchestrator": ["governance.council.ratified"],
    "rebuild.lpw_manager": ["rebuild.plan.created"],
    "rebuild.cutover_controller": ["rebuild.cft.passed"],
    "rebuild.cft_runner": ["rebuild.plan.created"],
    # Quality
    "quality.golden_set_registry": [],
    "quality.test_runner": [],
    "quality.regression_detector": ["quality.test.completed"],
    # Devices
    "devices.device_discovery": [],
    "devices.device_registry": ["devices.discovery.found", "devices.discovery.lost"],
    "devices.artifact_deployer": ["devices.device.registered"],
    "devices.test_harness": ["devices.deployment.completed"],
    # SDR
    "sdr.sdr_gateway": [],
    "sdr.capture_orchestrator": ["sdr.gateway.capture", "sdr.safety.check"],
    "sdr.signal_analyzer": ["sdr.capture.completed"],
    "sdr.protocol_decoder": ["sdr.signal.classified"],
    "sdr.rf_safety_governor": [],
    # Cellular
    "cellular.ran_lab": [],
    "cellular.core_network": ["cellular.ue.attached"],
    "cellular.ue_emulator": [],
    "cellular.rf_isolation": ["sdr.capture.completed"],
    "cellular.attack_vectors": [],
    "cellular.control_plane": ["cellular.ran.measurement"],
    "cellular.evidence_writer": ["cellular.attack.result", "cellular.cp.anomaly"],
}


# ---------------------------------------------------------------------------
# Generation logic
# ---------------------------------------------------------------------------

def get_default(key: str, module_id: str) -> str:
    """Get default value for a manifest field."""
    defaults = {
        "implementation_strategy": "greenfield",
        "contract_version": "1.0.0",
        "security_profile": "dev-light",
        "auth_mode": "bootstrap",
        "execution_guard": "off",
        "audit_mode": "basic",
        "milestone": "M0",
        "lifecycle_stage": "draft",
        "version": "1.0.0",
    }
    return defaults.get(key, "")


def build_manifest(module_id: str) -> dict:
    """Build a complete manifest dict for a module."""
    package, name = module_id.split(".", 1)
    kind = PACKAGE_KIND[package]
    meta = MODULE_META.get(module_id, {})

    manifest = {
        "module_id": module_id,
        "module_kind": kind,
        "owner_plan": meta.get("owner_plan", "P01"),
        "implementation_strategy": get_default("implementation_strategy", module_id),
        "contract_version": get_default("contract_version", module_id),
        "decision_class_entry": meta.get("decision_class_entry", "D3"),
        "security_profile": meta.get("security_profile", get_default("security_profile", module_id)),
        "auth_mode": get_default("auth_mode", module_id),
        "execution_guard": get_default("execution_guard", module_id),
        "audit_mode": get_default("audit_mode", module_id),
        "depends_on": DEPENDS_ON.get(module_id, []),
        "publishes_events": PUBLISHES_EVENTS.get(module_id, []),
        "consumes_events": CONSUMES_EVENTS.get(module_id, []),
        "description": meta.get("description", ""),
        "version": get_default("version", module_id),
        "milestone": get_default("milestone", module_id),
        "lifecycle_stage": get_default("lifecycle_stage", module_id),
    }

    # Override auth_mode and execution_guard for security modules
    if package == "security" and name != "profiles":
        manifest["auth_mode"] = "session"
        manifest["execution_guard"] = "strict"
        manifest["audit_mode"] = "extended"

    return manifest


def validate_manifest(manifest: dict, schema: dict) -> list[str]:
    """Validate a manifest against the JSON schema. Returns list of errors."""
    errors: list[str] = []

    # Check required fields
    for field in schema.get("required", []):
        if field not in manifest:
            errors.append(f"missing required field: {field}")

    props = schema.get("properties", {})

    for key, value in manifest.items():
        if key not in props:
            errors.append(f"unknown field: {key}")
            continue

        prop_schema = props[key]

        # Type checks
        if prop_schema.get("type") == "string":
            if not isinstance(value, str):
                errors.append(f"{key}: expected string, got {type(value).__name__}")
            elif "pattern" in prop_schema and not re.match(prop_schema["pattern"], value):
                errors.append(f"{key}: does not match pattern {prop_schema['pattern']}")
            elif "enum" in prop_schema and value not in prop_schema["enum"]:
                errors.append(f"{key}: '{value}' not in {prop_schema['enum']}")

        elif prop_schema.get("type") == "array":
            if not isinstance(value, list):
                errors.append(f"{key}: expected array, got {type(value).__name__}")

    # Check additionalProperties
    if not schema.get("additionalProperties", True):
        for key in manifest:
            if key not in props:
                errors.append(f"additional property not allowed: {key}")

    return errors


def generate_all() -> tuple[int, int, list[str]]:
    """Generate all manifests. Returns (success_count, error_count, errors)."""
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load schema
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    success = 0
    errors: list[str] = []
    module_ids = sorted(MODULE_META.keys())

    for module_id in module_ids:
        manifest = build_manifest(module_id)

        # Validate
        validation_errors = validate_manifest(manifest, schema)
        if validation_errors:
            for err in validation_errors:
                errors.append(f"{module_id}: {err}")
            continue

        # Write
        out_path = MANIFESTS_DIR / f"{module_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")

        success += 1

    return success, len(errors), errors


def main():
    print("=" * 70)
    print("SYLION AEIS -- Canonical Module Manifest Generator")
    print("=" * 70)
    print()

    # Count modules by class
    by_class: dict[str, int] = {}
    for mid in MODULE_META:
        pkg = mid.split(".")[0]
        kind = PACKAGE_KIND[pkg]
        by_class[kind] = by_class.get(kind, 0) + 1

    print(f"Total modules defined: {len(MODULE_META)}")
    print(f"Output directory:      {MANIFESTS_DIR}")
    print()
    print("Modules by class:")
    for kind in sorted(by_class.keys()):
        pkg_name = [k for k, v in PACKAGE_KIND.items() if v == kind][0]
        print(f"  {kind} ({pkg_name:12s}): {by_class[kind]} modules")
    print()

    # Generate
    success, error_count, errors = generate_all()

    print(f"Generated: {success} manifests")
    print(f"Errors:    {error_count}")
    print()

    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
        print()
        sys.exit(1)

    # Summary table
    print("-" * 70)
    print(f"{'module_id':<40s} {'kind':>4s} {'plan':>4s} {'D':>2s} {'deps':>4s} {'pubs':>4s} {'cons':>4s}")
    print("-" * 70)
    for mid in sorted(MODULE_META.keys()):
        pkg = mid.split(".")[0]
        kind = PACKAGE_KIND[pkg]
        meta = MODULE_META[mid]
        deps = len(DEPENDS_ON.get(mid, []))
        pubs = len(PUBLISHES_EVENTS.get(mid, []))
        cons = len(CONSUMES_EVENTS.get(mid, []))
        dc = meta.get("decision_class_entry", "D3")
        plan = meta.get("owner_plan", "P01")
        print(f"{mid:<40s} {kind:>4s} {plan:>4s} {dc:>2s} {deps:>4d} {pubs:>4d} {cons:>4d}")
    print("-" * 70)
    print(f"Total: {success} manifests validated and written")
    print()

    # Try jsonschema validation if available
    try:
        import jsonschema
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
        jsonschema_errors = []
        for mid in sorted(MODULE_META.keys()):
            path = MANIFESTS_DIR / f"{mid}.json"
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            try:
                jsonschema.validate(doc, schema)
            except jsonschema.ValidationError as e:
                jsonschema_errors.append(f"{mid}: {e.message}")
        if jsonschema_errors:
            print(f"jsonschema validation: {len(jsonschema_errors)} errors")
            for e in jsonschema_errors:
                print(f"  - {e}")
        else:
            print(f"jsonschema validation: all {success} manifests PASS")
    except ImportError:
        print("(jsonschema not installed -- schema validation done manually)")

    print()
    print("DONE")


if __name__ == "__main__":
    main()
