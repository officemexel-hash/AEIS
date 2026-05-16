"""
SYLION Audit Pipeline — Configuration

Konfiguracja modeli, promptów i parametrów pipeline'u.
Reads from environment variables and .env.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Konfiguracja pojedynczego modelu audytorskiego."""
    name: str               # Identyfikator (np. "claude")
    model_id: str           # ID modelu wg LiteLLM (np. "anthropic/claude-sonnet-4-6")
    api_key_env: str        # Nazwa zmiennej środowiskowej z kluczem API
    base_url: str | None = None  # Opcjonalny base URL (np. dla DeepSeek)
    strengths: str = ""     # Mocne strony — używane w cross-verify

    @property
    def api_key(self) -> str:
        # Ollama does not require an API key
        if self.name == "ollama" or self.api_key_env == "OLLAMA_API_KEY":
            return os.getenv(self.api_key_env, "ollama")  # dummy value, Ollama ignores it
        key = os.getenv(self.api_key_env, "")
        if not key:
            raise ValueError(f"Brak klucza API: ustaw {self.api_key_env} w .env albo zmiennych srodowiskowych")
        return key

    @property
    def is_local(self) -> bool:
        """True if this model runs locally (no cloud API call).
        Recognizes localhost, 127.0.0.1, [::1] (Council fix Z4 — Opus+GPT 2/4).
        """
        url = self.base_url or ""
        return self.base_url is not None and any(
            h in url for h in ("localhost", "127.0.0.1", "::1")
        )


# Modele audytorskie (6 including Ollama — see agents.yaml for consensus threshold)
AUDIT_MODELS: list[ModelConfig] = [
    ModelConfig(
        name="claude",
        model_id="anthropic/claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        strengths="Bezpieczeństwo, analiza wzorców Go, przestrzeganie instrukcji, precyzja",
    ),
    ModelConfig(
        name="gpt",
        model_id="openai/gpt-5",
        api_key_env="OPENAI_API_KEY",
        strengths="Rozumowanie logiczne, analiza złożonych zależności, edge cases",
    ),
    ModelConfig(
        name="gemini",
        model_id="google/gemini-2.5-pro",
        api_key_env="GOOGLE_API_KEY",
        strengths="Duży kontekst, analiza całych pakietów, spójność architektoniczna",
    ),
    ModelConfig(
        name="deepseek",
        model_id="deepseek/deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        strengths="Analiza kodu, optymalizacja, wzorce niskopoziomowe",
    ),
    ModelConfig(
        name="ollama",
        model_id="ollama_chat/llama3",
        api_key_env="OLLAMA_API_KEY",  # Not actually required — Ollama has no auth
        base_url=os.getenv("OLLAMA_API_BASE", "http://localhost:11434"),
        strengths="Lokalny model, zero latency sieciowej, prywatność danych, brak kosztów API",
    ),
]


# ---------------------------------------------------------------------------
# Pipeline config
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Globalna konfiguracja pipeline'u."""
    workspace: Path = Path(".")
    ksiega_path: Path | None = None
    packages: list[str] = field(default_factory=list)  # Konkretne pakiety do audytu (puste = wszystko)
    results_dir: Path = Path(os.getenv("RESULTS_DIR", "./results"))
    consensus_threshold: int = int(os.getenv("CONSENSUS_THRESHOLD", "3"))
    max_agent_steps: int = int(os.getenv("MAX_AGENT_STEPS", "50"))
    dry_run: bool = False   # True = nie generuj patchy
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    models: list[str] = field(default_factory=lambda: ["claude", "gpt", "gemini", "deepseek"])

    # --- Global Daily Budget Cap ---
    max_cost_usd_per_day: float = float(os.getenv("MAX_COST_USD_PER_DAY", "50.0"))  # Daily API cost limit
    budget_warning_threshold: float = float(os.getenv("BUDGET_WARNING_THRESHOLD", "0.80"))  # Warn at 80%

    # --- Pion D Streaming Latency Budgets ---
    streaming_latency_p50_ms: int = int(os.getenv("STREAM_LATENCY_P50_MS", "80"))
    streaming_latency_p95_ms: int = int(os.getenv("STREAM_LATENCY_P95_MS", "150"))
    streaming_latency_p99_ms: int = int(os.getenv("STREAM_LATENCY_P99_MS", "300"))
    streaming_input_latency_ms: int = int(os.getenv("STREAM_INPUT_LATENCY_MS", "50"))
    streaming_frame_drop_max_pct: float = float(os.getenv("STREAM_FRAME_DROP_MAX_PCT", "1.0"))
    streaming_av_sync_drift_ms: int = int(os.getenv("STREAM_AV_SYNC_DRIFT_MS", "50"))
    streaming_reconnect_timeout_s: int = int(os.getenv("STREAM_RECONNECT_TIMEOUT_S", "3"))
    streaming_turn_fallback_s: int = int(os.getenv("STREAM_TURN_FALLBACK_S", "5"))
    streaming_min_bitrate_kbps: int = int(os.getenv("STREAM_MIN_BITRATE_KBPS", "500"))
    streaming_max_bitrate_kbps: int = int(os.getenv("STREAM_MAX_BITRATE_KBPS", "8000"))
    streaming_target_fps: int = int(os.getenv("STREAM_TARGET_FPS", "30"))
    streaming_max_resolution: str = os.getenv("STREAM_MAX_RESOLUTION", "1920x1080")
    streaming_codec_video: str = os.getenv("STREAM_CODEC_VIDEO", "H.264")
    streaming_codec_audio: str = os.getenv("STREAM_CODEC_AUDIO", "Opus")
    streaming_opus_sample_rate: int = int(os.getenv("STREAM_OPUS_SAMPLE_RATE", "48000"))
    streaming_battery_threshold_pct: int = int(os.getenv("STREAM_BATTERY_THRESHOLD_PCT", "20"))

    # --- Dashboard ---
    dashboard_port: int = int(os.getenv("DASHBOARD_PORT", "8421"))

    @property
    def streaming_latency_budget(self) -> dict:
        """Compiled latency budget for streaming agents."""
        return {
            "video_p50_ms": self.streaming_latency_p50_ms,
            "video_p95_ms": self.streaming_latency_p95_ms,
            "video_p99_ms": self.streaming_latency_p99_ms,
            "input_max_ms": self.streaming_input_latency_ms,
            "av_sync_drift_ms": self.streaming_av_sync_drift_ms,
            "frame_drop_max_pct": self.streaming_frame_drop_max_pct,
            "reconnect_timeout_s": self.streaming_reconnect_timeout_s,
            "turn_fallback_s": self.streaming_turn_fallback_s,
        }

    # --- Anti-Hallucination Layer 1: File Verification (SHA-256 Guard) ---
    file_verification_enabled: bool = True    # Enable SHA-256 file verification
    verify_checksums: bool = True             # Verify SHA-256 checksums before/after each agent
    verify_fail_closed: bool = True           # Block agent on hallucination (True) or warn only (False)
    verify_auto_escalate: bool = True         # Auto-escalate to Human Gate on CRITICAL hallucination
    verify_files: list[str] = field(default_factory=list)  # Restrict verification to these files (empty = all declared)
    verification_results_dir: Path | None = None  # Override results_dir for verification logs

    # --- Pion D Runtime: Signaling Server ---
    signaling_max_rooms: int = int(os.getenv("SIGNALING_MAX_ROOMS", "50"))
    signaling_heartbeat_interval_s: int = int(os.getenv("SIGNALING_HEARTBEAT_S", "10"))
    signaling_stale_timeout_s: int = int(os.getenv("SIGNALING_STALE_TIMEOUT_S", "30"))
    signaling_stun_urls: str = os.getenv("SIGNALING_STUN_URLS", "stun:stun.l.google.com:19302")
    signaling_turn_urls: str = os.getenv("SIGNALING_TURN_URLS", "")
    signaling_turn_username: str = os.getenv("SIGNALING_TURN_USERNAME", "")
    signaling_turn_credential: str = os.getenv("SIGNALING_TURN_CREDENTIAL", "")

    # --- Pion D Runtime: Device Harness ---
    device_harness_dry_run: bool = bool(os.getenv("DEVICE_HARNESS_DRY_RUN", "true").lower() in ("true", "1", "yes"))
    device_pixel_serial: str = os.getenv("DEVICE_PIXEL_SERIAL", "")  # ADB serial for Pixel 8
    device_router_host: str = os.getenv("DEVICE_ROUTER_HOST", "192.168.8.1")
    device_router_user: str = os.getenv("DEVICE_ROUTER_USER", "root")
    device_router_ssh_key: str = os.getenv("DEVICE_ROUTER_SSH_KEY", "")

    # --- Pion D Runtime: Metrics Ingestion ---
    metrics_max_samples_per_metric: int = int(os.getenv("METRICS_MAX_SAMPLES", "10000"))
    metrics_alert_dedup_window_s: int = int(os.getenv("METRICS_ALERT_DEDUP_S", "60"))
    metrics_log_dir: str = os.getenv("METRICS_LOG_DIR", "")

    # --- Pion D Runtime: ABR Controller ---
    abr_initial_rung: int = int(os.getenv("ABR_INITIAL_RUNG", "1"))
    abr_ramp_up_threshold: float = float(os.getenv("ABR_RAMP_UP_THRESHOLD", "1.5"))  # 1.5x rung max
    abr_ramp_down_threshold: float = float(os.getenv("ABR_RAMP_DOWN_THRESHOLD", "0.8"))  # 0.8x rung min
    abr_nack_reduction_pct: float = float(os.getenv("ABR_NACK_REDUCTION_PCT", "0.15"))  # 15% bitrate cut
    abr_thermal_max_rung: int = int(os.getenv("ABR_THERMAL_MAX_RUNG", "1"))  # Max rung under thermal

    # --- Pion D Runtime: Input Protocol ---
    input_protocol_hmac_key: str = os.getenv("INPUT_PROTOCOL_HMAC_KEY", "")  # Empty = default key
    input_protocol_max_replay_window_s: float = float(os.getenv("INPUT_REPLAY_WINDOW_S", "5.0"))
    input_protocol_max_batch_size: int = int(os.getenv("INPUT_MAX_BATCH_SIZE", "32"))

    # --- Pion D Runtime: Audio Pipeline ---
    audio_opus_bitrate_bps: int = int(os.getenv("AUDIO_OPUS_BITRATE_BPS", "32000"))
    audio_opus_dtx_enabled: bool = bool(os.getenv("AUDIO_OPUS_DTX", "true").lower() in ("true", "1", "yes"))
    audio_jitter_buffer_ms: int = int(os.getenv("AUDIO_JITTER_BUFFER_MS", "200"))
    audio_echo_cancel_enabled: bool = bool(os.getenv("AUDIO_ECHO_CANCEL", "true").lower() in ("true", "1", "yes"))

    # --- Pion D Runtime: Stream Security ---
    stream_security_production: bool = bool(os.getenv("STREAM_SECURITY_PROD", "true").lower() in ("true", "1", "yes"))
    stream_security_weak_cipher_block: bool = bool(os.getenv("STREAM_SECURITY_WEAK_BLOCK", "true").lower() in ("true", "1", "yes"))
    stream_security_require_relay: bool = bool(os.getenv("STREAM_SECURITY_RELAY_ONLY", "true").lower() in ("true", "1", "yes"))
    stream_security_signaling_rate: int = int(os.getenv("STREAM_SECURITY_SIG_RATE", "50"))
    stream_security_dc_rate: int = int(os.getenv("STREAM_SECURITY_DC_RATE", "200"))
    stream_security_pinned_certs: str = os.getenv("STREAM_SECURITY_PINNED_CERTS", "")  # Comma-separated

    # --- Pion D Benchmark Harness ---
    benchmark_enabled: bool = bool(os.getenv("BENCHMARK_ENABLED", "true").lower() in ("true", "1", "yes"))
    benchmark_output_dir: str = os.getenv("BENCHMARK_OUTPUT_DIR", "")
    benchmark_setup_p95_ms: float = float(os.getenv("BENCH_SETUP_P95_MS", "2000"))
    benchmark_input_photon_p95_ms: float = float(os.getenv("BENCH_INPUT_PHOTON_P95_MS", "100"))
    benchmark_abr_rampup_ms: float = float(os.getenv("BENCH_ABR_RAMPUP_MS", "5000"))
    benchmark_reconnect_p95_ms: float = float(os.getenv("BENCH_RECONNECT_P95_MS", "4000"))
    benchmark_frame_drop_fail_pct: float = float(os.getenv("BENCH_FRAME_DROP_FAIL_PCT", "0.05"))
    benchmark_av_sync_fail_ms: float = float(os.getenv("BENCH_AV_SYNC_FAIL_MS", "80"))

    # --- Anti-Hallucination Layer 2: BuildVerification (go vet/build/test) ---
    build_verification_enabled: bool = bool(os.getenv("BUILD_VERIFICATION_ENABLED", "true").lower() in ("true", "1", "yes"))
    build_run_tests: bool = bool(os.getenv("BUILD_RUN_TESTS", "true").lower() in ("true", "1", "yes"))
    build_test_timeout_s: int = int(os.getenv("BUILD_TEST_TIMEOUT_S", "120"))
    build_vet_timeout_s: int = int(os.getenv("BUILD_VET_TIMEOUT_S", "30"))
    build_build_timeout_s: int = int(os.getenv("BUILD_BUILD_TIMEOUT_S", "60"))

    # --- Anti-Hallucination Layer 3: ClaimProvenance (keyword matching) ---
    claim_provenance_enabled: bool = bool(os.getenv("CLAIM_PROVENANCE_ENABLED", "true").lower() in ("true", "1", "yes"))
    provenance_context_window: int = int(os.getenv("PROVENANCE_CONTEXT_WINDOW", "10"))
    provenance_min_match_ratio: float = float(os.getenv("PROVENANCE_MIN_MATCH_RATIO", "0.3"))

    # --- Anti-Hallucination Layer 4: SemanticDedup (finding deduplication) ---
    semantic_dedup_enabled: bool = bool(os.getenv("SEMANTIC_DEDUP_ENABLED", "true").lower() in ("true", "1", "yes"))
    dedup_similarity_threshold: float = float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.75"))
    dedup_model_name: str = os.getenv("DEDUP_MODEL_NAME", "all-MiniLM-L6-v2")

    # --- Anti-Hallucination Layer 5: FactCheckerAgent (independent LLM) ---
    fact_checker_enabled: bool = bool(os.getenv("FACT_CHECKER_ENABLED", "true").lower() in ("true", "1", "yes"))
    fact_checker_model: str = os.getenv("FACT_CHECKER_MODEL", "claude")  # Use a different model than auditors
    fact_checker_max_items: int = int(os.getenv("FACT_CHECKER_MAX_ITEMS", "50"))
    fact_checker_context_lines: int = int(os.getenv("FACT_CHECKER_CONTEXT_LINES", "20"))

    def get_active_models(self) -> list[ModelConfig]:
        """Zwróć tylko modele wybrane w konfiguracji."""
        return [m for m in AUDIT_MODELS if m.name in self.models]

    @property
    def verification_output_dir(self) -> Path:
        """Resolved path for file verification outputs."""
        return self.verification_results_dir or (self.results_dir / "verification")


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# Etap 1: Ekstrakcja wymagań z Księgi
PROMPT_KSIEGA_EXTRACT = """Przeanalizuj dokument Księgi SYLION i wyekstrahuj wymagania bezpieczeństwa
oraz architektoniczne, które można zweryfikować przez audyt kodu.

Dla każdego wymagania podaj:
- ID (np. KS-SEC-001)
- Kategoria (SECURITY / ARCHITECTURE / TRANSPORT / CRYPTO / AUTH / DATA)
- Opis wymagania
- Kryteria weryfikacji (co sprawdzić w kodzie)
- Priorytet (P0 = krytyczny, P1 = wysoki, P2 = średni)

Zwróć wynik jako JSON array obiektów. Skoncentruj się na wymaganiach weryfikowalnych
statycznie w kodzie Go. Pomiń wymagania dotyczące infrastruktury/deploymentu.

Znane kluczowe wymagania (ZAWSZE uwzględnij):
1. Brak zaufania do X-Forwarded-For
2. HSM-backed key management z wymaganymi PINami
3. Sanityzacja błędów HTTP (brak wycieku informacji wewnętrznych)
4. Authenticated /metrics endpoints
5. Restrykcyjny CORS
6. Certyfikowane warstwy transportowe (nie WireGuard w baseline)
7. Przygotowanie na PQC (post-quantum cryptography)
8. Egress whitelisting
9. Dual-admin / panic controls
10. Route guards per rola/tier na każdym endpoincie
"""

# Etap 3: Audyt kodu — prompt dla każdego modelu
PROMPT_AUDIT = """Jesteś ekspertem audytu bezpieczeństwa kodu Go dla platformy SYLION.

## Kontekst
SYLION to platforma bezpiecznej komunikacji (~130k+ LOC w Go). Architektura:
- Single-binary orchestrator: sylion-server, sylion-verify, sylionctl
- gRPC + REST + GraphQL API
- PostgreSQL (LISTEN/NOTIFY + SSE)
- OpenBao (PKI/sekrety), Firecracker microVMs, AMD SEV-SNP / Intel TDX
- Strefy G1/G2 (session broker), VPS/Workload zones
- Matrix core comms, Dark-Matrix (.onion)

## Wymagania do weryfikacji
{requirements}

## Pliki do audytu
{file_list}

## Instrukcje
Przeanalizuj każdy plik pod kątem wymagań. Dla każdego znalezionego problemu:

```json
{{
  "id": "FIND-XXX",
  "file": "path/to/file.go",
  "line": 42,
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "category": "SECURITY|ARCHITECTURE|...",
  "requirement_id": "KS-SEC-001",
  "title": "Krótki opis",
  "description": "Szczegółowy opis problemu",
  "evidence": "Fragment kodu pokazujący problem",
  "fix_suggestion": "Proponowana naprawa z kodem",
  "confidence": 0.95
}}
```

Zwróć JSON array z wszystkimi znalezionymi problemami.
Bądź rygorystyczny — lepiej zgłosić false positive niż pominąć prawdziwy problem.
Skoncentruj się na swoich mocnych stronach: {model_strengths}
"""

# Etap 4: Weryfikacja krzyżowa
PROMPT_CROSS_VERIFY = """Jesteś niezależnym weryfikatorem audytu bezpieczeństwa kodu Go (SYLION).

Otrzymujesz ustalenia (findings) z audytu przeprowadzonego przez INNY model AI.
Twoje zadanie to NIEZALEŻNA weryfikacja każdego finding'u.

## Ustalenia do weryfikacji
{findings}

## Pliki źródłowe (odczytaj je aby zweryfikować)
{file_list}

## Instrukcje
Dla KAŻDEGO finding'u oceń:

```json
{{
  "original_id": "FIND-XXX",
  "verdict": "CONFIRMED|DISPUTED|INCONCLUSIVE",
  "confidence": 0.0-1.0,
  "reasoning": "Dlaczego potwierdzasz/odrzucasz",
  "additional_context": "Dodatkowe obserwacje",
  "missed_by_original": [
    {{
      "description": "Problem pominięty przez oryginalny audyt",
      "file": "path/to/file.go",
      "line": 99
    }}
  ]
}}
```

Bądź krytyczny. Sprawdź:
1. Czy finding jest faktyczny (odczytaj plik i linię)?
2. Czy severity jest adekwatne?
3. Czy sugerowana naprawa jest poprawna i bezpieczna?
4. Czy oryginalny audytor nie pominął czegoś w tym samym pliku?
"""

# Etap 5: Scalenie — prompt dla agenta decyzyjnego
PROMPT_MERGE_DECISION = """Jesteś architektem bezpieczeństwa platformy SYLION.

Otrzymujesz wyniki audytu z 4 modeli AI oraz ich krzyżową weryfikację.
Twoje zadanie to podjęcie decyzji dla każdego finding'u.

## Reguły decyzyjne
- **ACCEPT** (wdrażamy): ≥{threshold}/4 modeli potwierdza finding + żaden nie odrzuca
- **REVIEW** (do ręcznego przeglądu): 2/4 potwierdza LUB są sprzeczne verdicts
- **SKIP** (pomijamy): ≤1/4 potwierdza LUB niska pewność (<0.5 avg)

## Dane wejściowe
{all_findings_with_verdicts}

## Instrukcje
Dla każdego unikalnego finding'u (deduplikacja po file+line+category):

```json
{{
  "finding_id": "MERGED-XXX",
  "original_ids": ["FIND-001", "FIND-042", ...],
  "decision": "ACCEPT|REVIEW|SKIP",
  "file": "path/to/file.go",
  "line": 42,
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "title": "Skonsolidowany opis",
  "description": "Połączona analiza ze wszystkich modeli",
  "consensus_score": "3/4",
  "fix_strategy": "Najlepsza strategia naprawy (synteza sugestii)",
  "risk_if_skipped": "Co się stanie jeśli nie naprawimy"
}}
```

Dodatkowo wygeneruj podsumowanie:
- Liczba ACCEPT / REVIEW / SKIP
- Top 5 najkrytyczniejszych findings
- Rekomendacja ogólna
"""

# Etap 6: Generowanie patcha
PROMPT_PATCH = """Jesteś ekspertem Go implementującym poprawki bezpieczeństwa w platformie SYLION.

## Finding do naprawienia
{finding}

## Plik źródłowy
{source_code}

## Konwencje SYLION
- Statycznie linkowane binaria (CGO_ENABLED=0)
- Error wrapping: fmt.Errorf("context: %w", err)
- Sanityzacja błędów: nigdy err.Error() do klienta
- Structured logging: slog.Info/Error z kontekstem
- Route guards per rola/tier
- Table-driven tests
- Wersja: go:embed VERSION

## Instrukcje
1. Wygeneruj MINIMALNĄ poprawkę (nie refaktoryzuj niezwiązanego kodu)
2. Dodaj/zaktualizuj testy (table-driven)
3. Upewnij się że `go vet` i `go test` przechodzą
4. Wygeneruj unified diff (patch)

Zwróć:
```json
{{
  "finding_id": "MERGED-XXX",
  "patch": "--- a/path/to/file.go\\n+++ b/path/to/file.go\\n@@ ...unified diff...",
  "test_patch": "--- a/path/to/file_test.go\\n+++ b/path/to/file_test.go\\n@@ ...",
  "verification_commands": ["go vet ./...", "go test ./path/to/package/..."],
  "changelog_entry": "Krótki opis dla CHANGELOG"
}}
```
"""

# Etap 7: Podsumowanie
PROMPT_SUMMARY = """Wygeneruj kompletny raport audytu bezpieczeństwa platformy SYLION w Markdown.

## Dane
{pipeline_results}

## Struktura raportu

# Raport Audytu Bezpieczeństwa — SYLION vX.Y.Z

## Podsumowanie wykonawcze
- Data audytu, modele użyte, zakres
- Kluczowe metryki (findings, patche, consensus rate)

## Wyniki audytu

### Problemy krytyczne (CRITICAL)
Tabela z: ID, Plik, Opis, Status (ACCEPT/REVIEW), Consensus

### Problemy wysokie (HIGH)
...

### Problemy średnie (MEDIUM)
...

## Analiza konsensusu
- Gdzie modele się zgadzały vs. gdzie się różniły
- Które modele były najbardziej/najmniej rygorystyczne

## Wdrożone poprawki
- Lista patchy z opisem
- Wyniki weryfikacji (go vet, go test)

## Do ręcznego przeglądu (REVIEW)
- Findings wymagające ludzkiej decyzji

## Macierz śledzenia
Tabela: Wymaganie Księgi → Finding ID → Patch → Test

## Rekomendacje
- Priorytety na następny sprint
- Sugestie architektoniczne
"""

# ---------------------------------------------------------------------------
# Stream Monitor — Production Prompt (Stage 0 / continuous)
# ---------------------------------------------------------------------------

PROMPT_STREAM_MONITOR = """Jesteś stream_monitor — ciągły agent nadzorujący sesje streamingowe SYLION w czasie rzeczywistym.

## Twoje obowiązki
1. **Health check** — co {heartbeat_interval_s}s odpytaj SignalingServer, DeviceHarness, MetricsCollector, ABRController, InputProtocol, AudioPipeline, StreamSecurityVerifier, BenchmarkHarness.
2. **Alerty progowe** — monitoruj metryki (latency, bitrate, FPS, frame drop, AV sync drift) i eskaluj WARN/CRITICAL.
3. **Security audit** — co {security_audit_interval_s}s uruchom pełny audit bezpieczeństwa sesji (DTLS, SRTP, ICE, token, rate limit, cert pin, anomaly).
4. **Benchmark trigger** — uruchom benchmark suite po deploy lub na żądanie operatora.
5. **Human Gate** — eskaluj do operatora każdą sytuację CRITICAL i czekaj na decyzję.

## Subsystemy do monitorowania
- SignalingServer: rooms, peers, ICE, DTLS
- DeviceHarness: Pixel 8 (GrapheneOS), Mudi 750v2 (OpenWrt)
- MetricsCollector: latency (p50/p95/p99), bitrate, FPS, frame drops
- ABRController: current rung, state, congestion signals
- InputProtocol: DataChannel binary wire, replay protection, HMAC
- AudioPipeline: Opus codec, jitter buffer, echo cancel, AV sync
- StreamSecurityVerifier: DTLS fingerprint, SRTP cipher, ICE filtering, token, rate limits
- BenchmarkHarness: 6 benchmarków (setup, input-to-photon, bitrate adapt, reconnect, frame drop, AV sync)

## Zasady bezpieczeństwa
- LLM NIGDY nie wydaje raw shell. Generuje parametry do pre-approved scenariuszy.
- Wszelkie komendy ADB/SSH przechodzą przez SafeCommandRunner (whitelist + dry_run).
- DTLS fingerprint mismatch = natychmiast CRITICAL + kill session.
- Weak SRTP cipher = BLOCK (nie downgrade).
- Non-relay ICE w prod = REJECT.
- Token expired = force re-auth.
- Rate limit > 10 violations = session terminate.

## Format odpowiedzi (JSON)
```json
{{
  "timestamp": "ISO-8601",
  "status": "OK | WARN | CRITICAL",
  "subsystems": {{
    "signaling": {{"status": "OK", "rooms": 0}},
    "device": {{"status": "OK", "pixel_state": "ready", "router_state": "ready"}},
    "metrics": {{"status": "OK", "latency_p95_ms": 0, "fps": 0, "bitrate_kbps": 0}},
    "abr": {{"status": "OK", "rung": 0, "state": "stable"}},
    "input_protocol": {{"status": "OK", "replay_violations": 0}},
    "audio": {{"status": "OK", "codec": "opus", "av_drift_ms": 0}},
    "security": {{"status": "OK", "level": "secure", "checks_passed": 0}},
    "benchmark": {{"status": "OK", "last_run": null, "passed": 0, "failed": 0}}
  }},
  "alerts": [],
  "actions_taken": [],
  "human_gate_required": false,
  "human_gate_reason": null
}}
```

## Eskalacja
- WARN: loguj + kontynuuj monitoring
- CRITICAL: Human Gate → czekaj na decyzję → wykonaj zatwierdzoną akcję
- Security FAIL: natychmiast Human Gate CRITICAL

## Dane wejściowe
{runtime_status}
"""
