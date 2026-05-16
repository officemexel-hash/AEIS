# SYLION Multi-Agent Architecture — 47 Agentów

> **Canonical Source of Truth**: `agents.yaml` (47 agents, full §9.5 metadata).
> Nie edytuj liczb agentów ręcznie — uruchom `scripts/validate_agents_manifest.py --fix-counts`.

## Architektura nadzoru (Supervisor Layer)

```
                    ┌─────────────────────────────────────────┐
                    │  🛡️  SUPERVISOR (Claude Opus)           │
                    │  Nadzorca wszystkich agentów            │
                    │  • Checklist po każdym etapie           │
                    │  • Human Gate (zatwierdzenia admin.)    │
                    │  • Safe Runner (whitelist komend)       │
                    │  • Loop Guard (anti-loop protection)    │
                    └───────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────┴─────────────────────┐
                    │       📖 BOOK GUARDIAN (SHA-256)         │
                    │  Read-only watchdog Księgi SYLION 3.4    │
                    │  Pipeline HALT on drift                  │
                    ├─────────────────────────────────────────┤
                    │       💰 BUDGET GUARD (cost cap)         │
                    │  Daily API cost limit ($50/day)          │
                    │  Pipeline HALT on budget exceeded        │
                    ├─────────────────────────────────────────┤
                    │       🔍 FILE VERIFIER (anti-hallucin.)  │
                    │  SHA-256 per-agent iteration check       │
                    │  Detects 6 hallucination types           │
                    └───────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────┴─────────────────────┐
                    │          🎯 COORDINATOR                  │
                    │     (Orchestrator — Claude Opus)          │
                    │  Zarządza pipeline'em, podejmuje          │
                    │  decyzje GO/NO-GO, rozwiązuje konflikty  │
                    └──────────┬────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────────┐
         ▼                     ▼                         ▼
  STAGE 1: PREPARE     STAGE 2-4: AUDIT        STAGE 5: PATCH
  STAGE 6: DEPLOY      STAGE 6.5: STREAMING    STAGE 7: TEST
  STAGE 7.5: STREAM    STAGE 8: SECURITY       STAGE 8.5: SDR
  TEST                  STAGE 9: REPORT
```

## 47 Agentów — pełna tabela

### Stage 0 — Meta-agenty (8 agentów)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 1 | supervisor | claude-opus | Nadzorca — Human Gate + Safe Runner + checklist |
| 2 | coordinator | claude-opus | Orkiestrator pipeline, GO/NO-GO |
| 3 | book_guardian | — (pure SHA) | Strażnik Księgi — read-only SHA-256 watchdog |
| 4 | budget_guard | — (pure logic) | Strażnik budżetu — daily cost cap |
| 5 | file_verifier | claude-sonnet | Anti-hallucination SHA-256 guard |
| 6 | stream_monitor | claude-haiku | Ciągły monitoring Pionu D streaming |
| 7 | search_agent | perplexity-sonar-pro | Wyszukiwarka online (CVE, advisories) |
| 8 | reasoning_agent | o3 | Głęboki reasoning (złożone problemy) |

### Stage 1 — Prepare (2 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 9 | ksiega_analyst | claude-sonnet | Analiza Księgi 3.4 → requirements.json (DERIVED ARTIFACT) |
| 10 | build_agent | claude-sonnet | go build × 4 architektury |

### Stage 2 — Audit (5 audytorów)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 11 | auditor_claude | claude-sonnet | Audyt: auth, crypto, session |
| 12 | auditor_gpt | gpt-5 | Audyt: API, input validation, injection |
| 13 | auditor_gemini | gemini-pro | Audyt: concurrency, race conditions |
| 14 | auditor_deepseek | deepseek-v3 | Audyt: memory, errors, edge cases |
| 15 | auditor_grok | grok-3 | Audyt: CVE matching, supply chain |

### Stage 3 — Cross-Verify (4 weryfikatory)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 16 | verifier_claude | claude | Weryfikuje findings GPT/Gemini/DeepSeek |
| 17 | verifier_gpt | gpt | Weryfikuje findings Claude/Gemini/DeepSeek |
| 18 | verifier_gemini | gemini | Weryfikuje findings Claude/GPT/DeepSeek |
| 19 | verifier_deepseek | deepseek | Weryfikuje findings Claude/GPT/Gemini |

### Stage 4 — Merge (1 agent)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 20 | merger | claude | Konsensus ≥3/4 = ACCEPT, deduplikacja findings |

### Stage 5 — Patch (4 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 21-24 | patcher_1..4 | claude | Generator patchy, partycja 1-4/4 |

### Stage 6 — Deploy (2 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 25 | pixel_deployer | claude | ADB push na Pixel 8 (GrapheneOS) |
| 26 | router_deployer | claude | SSH/SCP deploy na router OpenWrt |

### Stage 6.5 — Pion D: Streaming (7 agentów)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 27 | stream_architect | claude-opus | Architekt: H.264+Opus+WebRTC, latency budget, TURN |
| 28 | stream_encoder | claude-sonnet | Encoder profiling: hw (Pixel) / sw fallback |
| 29 | stream_transport | gpt-5 | WebRTC: ICE, STUN/TURN, DTLS-SRTP, jitter buffer |
| 30 | capture_agent | claude-sonnet | Capture backends: SurfaceFlinger (Pixel) / Pipewire (laptop) |
| 31 | input_protocol_agent | gpt-5 | RTCDataChannel input protocol: touch/keyboard/mouse |
| 32 | mobile_ux_agent | claude-sonnet | Mobile UX: adaptive bitrate, reconnect, battery-aware |
| 33 | audio_agent | claude-sonnet | Opus audio pipeline: echo cancel, DTX, A/V sync |

### Stage 7 — Test (4 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 34 | tester_unit | gpt | go test z pokryciem kodu |
| 35 | tester_integration | gpt | Pixel↔Router↔Server flow |
| 36 | tester_e2e | claude | Full: rejestracja→sesja→wiadomość→verify |
| 37 | tester_regression | gemini | Porównanie z poprzednią wersją, benchmarki |

### Stage 7.5 — Stream Test (2 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 38 | stream_tester | gpt-5 | Latency P50/P95/P99, frame drop, A/V sync |
| 39 | stream_security_verifier | claude-opus | Security review: SRTP, DTLS, DataChannel auth |

### Stage 8 — Security (4 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 40 | red_team_network | claude | Ataki sieciowe: nmap, MITM, replay, DNS |
| 41 | red_team_app | gpt | Ataki aplikacyjne: fuzzing, auth bypass |
| 42 | blue_team_monitor | gemini | Monitoring logów, anomalie, TTD |
| 43 | blue_team_hardener | claude | Hardening: firewall, TLS, permissions |

### Stage 8.5 — SDR (3 agenty)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 44 | sdr_monitor | claude | HackRF: pasywne IMSI/IMEI skanowanie |
| 45 | rf_red_team | gpt | LimeSDR: rogue BTS pentest (ZMQ/Faraday) |
| 46 | rf_blue_team | gemini | Detekcja fałszywych BTS, cell ID tracking |

### Stage 9 — Report (1 agent)

| # | Agent | Model | Rola |
|---|-------|-------|------|
| 47 | reporter | claude-sonnet | Raport końcowy, CHANGELOG, traceability matrix |

## Przepływ danych (pipeline stages)

```
STAGE 0: META-AGENTS (always active)
  Supervisor → human_gate.jsonl, checklist.json
  BookGuardian → baseline.json, drift_log.jsonl
  BudgetGuard → budget_YYYY-MM-DD.json
  FileVerifier → file_verification_log.jsonl
  StreamMonitor → streaming_metrics.json

STAGE 1: PREPARE
  Księga Analyst → requirements.json (DERIVED ARTIFACT — source: Księga 3.4)
  Build Agent → sylion-server, sylion-verify, sylionctl (binaries)

STAGE 2: AUDIT (równolegle)
  5× Auditor → audit_*.json

STAGE 3: CROSS-VERIFY (równolegle)
  4× Cross-Verifier → verify_*.json

STAGE 4: MERGE
  Merger → merged_findings.json (ACCEPT/REVIEW/SKIP)

STAGE 5: PATCH (równolegle)
  4× Patch Agent → patches/*.patch
  Build Agent → re-build z patchami

STAGE 6: DEPLOY
  Pixel Deployer → wgrywa na Pixel (ADB)
  Router Deployer → wgrywa na router (SSH)

STAGE 6.5: STREAMING (Pion D) — HARD GATE: all 7 artifacts required
  Stream Architect → STREAMING-ARCHITECTURE.md, SESSION-FLOW.md
  Stream Encoder → ENCODER-PROFILE.md, bitrate_ladder.json
  Stream Transport → TRANSPORT-CONFIG.md, ice_config.json
  Capture Agent → CAPTURE-BACKENDS.md, capture_config.json
  Input Protocol Agent → DATACHANNEL-PROTOCOL.md, input_event_schema.json
  Mobile UX Agent → PIXEL-UX-SPEC.md, adaptive_bitrate_policy.json
  Audio Agent → AUDIO-PIPELINE.md, audio_config.json

STAGE 7: TEST (równolegle)
  Unit Tester → unit_results.json
  Integration Tester → integration_results.json
  E2E Tester → e2e_results.json
  Regression Tester → regression_results.json

STAGE 7.5: STREAM TEST — HARD GATE: test results + security review required
  Stream Tester → streaming_test_results.json, latency_report.md
  Stream Security Verifier → STREAMING-SECURITY-REVIEW.md

STAGE 8: SECURITY (równolegle)
  Red Team: Network → red_network.json
  Red Team: App → red_app.json
  Blue Team: Monitor → blue_monitor.json
  Blue Team: Hardener → blue_hardening.json

STAGE 8.5: SDR (HackRF + LimeSDR)
  Phase A: SDR Monitor → passive_monitor.json
  Phase B (równolegle):
    RF Red Team → rf_red_team.json (rogue BTS, downgrade)
    RF Blue Team → rf_blue_team.json (detekcja, TTD)

STAGE 9: REPORT
  Reporter → audit_report.md, CHANGELOG, traceability matrix
  Coordinator → final_decision.json (GO/NO-GO)
```

## Komunikacja między agentami

Agenci komunikują się przez **pliki w workspace** (shared filesystem):

```
sylion-pipeline/
├── workspace/                # Repozytorium SYLION
├── results/<timestamp>/      # Wyniki bieżącego pipeline'u
│   ├── stage1/              # Prepare
│   ├── stage2_audit/        # Audyt ×5
│   ├── stage3_verify/       # Cross-verify ×4
│   ├── stage4_merge/        # Merge
│   ├── stage5_patch/        # Patche
│   ├── stage6_deploy/       # Deployment status
│   ├── stage6_5_streaming/  # Pion D streaming docs
│   ├── stage7_test/         # Test results ×4
│   ├── stage7_5_stream/     # Streaming test results
│   ├── stage8_security/     # Red/Blue team
│   ├── stage8_5_sdr/        # SDR: HackRF + LimeSDR
│   ├── stage9_report/       # Final report
│   ├── budget/              # BudgetGuard daily snapshots
│   ├── book_guardian/       # BookGuardian baseline + drift
│   ├── file_verification/   # Anti-hallucination log
│   └── signals/             # Sygnały sterujące
└── device/                   # Skrypty zarządzania urządzeniami
```
