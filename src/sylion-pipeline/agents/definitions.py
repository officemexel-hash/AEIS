"""
SYLION Multi-Agent Pipeline — Definicje agentów

Każdy agent ma: model LLM, zestaw narzędzi, system prompt, skill.
Agenci komunikują się przez pliki JSON w workspace (shared filesystem).

CANONICAL SOURCE OF TRUTH: agents.yaml (47 agents)
Ten plik definiuje factory functions dla agentów OpenHands SDK.
Liczba agentów i ich konfiguracja jest zarządzana wyłącznie przez agents.yaml.
"""

from openhands.sdk import Agent, AgentContext, Tool
from openhands.sdk.context import Skill
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task import TaskToolSet
from openhands.tools.terminal import TerminalTool


# ===========================================================================
# SYSTEM PROMPTS — wspólne fragmenty
# ===========================================================================

SYLION_CONTEXT = """
## SYLION — Kontekst projektu
Platforma bezpiecznej komunikacji (~130k+ LOC, Go). Architektura:
- Binaria: sylion-server, sylion-verify, sylionctl (statycznie linkowane, linux/amd64)
- Strefy: G1/G2 (session broker), VPS/Workload zones
- Stack: gRPC, REST, GraphQL, PostgreSQL, OpenBao, Firecracker, SEV-SNP/TDX
- Comms: Matrix, Dark-Matrix (.onion), Signal/Briar (fallback)
- Infrastruktura docelowa: Pixel (GrapheneOS) + router mobilny (OpenWrt)

## Zasady bezpieczeństwa (ZAWSZE przestrzegaj)
1. Brak zaufania do XFF
2. HSM-backed keys z PINami
3. Sanityzacja błędów HTTP
4. Authenticated /metrics
5. Restrykcyjny CORS
6. Certyfikowane transport layers (nie WireGuard)
7. PQC-ready
8. Egress whitelisting
9. Dual-admin + panic controls
10. Route guards per rola/tier

## Konwencje Go
- CGO_ENABLED=0, GOOS=linux
- go:embed VERSION
- fmt.Errorf("context: %w", err)
- slog structured logging
- Table-driven tests
"""

DEVICE_CONTEXT = """
## Urządzenia fizyczne

### Pixel (GrapheneOS)
- Połączony przez USB (ADB)
- GrapheneOS z SYLION binary/app
- OTA sideload: recovery → "Apply update from ADB" → `adb sideload ota.zip`
- Deploy: `adb push`, `adb install`, `adb shell`
- Skrypty: /device/pixel_manager.sh

### Router mobilny (OpenWrt)
- Połączony przez USB (RNDIS/ethernet gadget)
- OpenWrt z SYLION relay binary
- Deploy: SSH + SCP (`scp binary root@router:/usr/local/bin/`)
- Config: `/etc/config/sylion`
- Skrypty: /device/router_manager.sh
"""


# ===========================================================================
# AGENT FACTORY — tworzenie instancji agentów
# ===========================================================================

def _base_tools() -> list[Tool]:
    """Podstawowy zestaw narzędzi dla każdego agenta."""
    return [
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
    ]


def _orchestrator_tools() -> list[Tool]:
    """Narzędzia orkiestratora (może delegować)."""
    return [
        Tool(name=TaskToolSet.name),
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
    ]


def create_coordinator(llm) -> Agent:
    """🎯 COORDINATOR — główny orkiestrator pipeline'u."""
    return Agent(
        llm=llm,
        tools=_orchestrator_tools(),
        tool_concurrency_limit=8,
        agent_context=AgentContext(
            skills=[Skill(
                name="coordinator",
                content=f"""Jesteś koordynatorem pipeline'u audytu SYLION.
{SYLION_CONTEXT}
{DEVICE_CONTEXT}

## Twoja rola
- Zarządzasz agentami w 10+ etapach pipeline'u (patrz agents.yaml)
- Podejmujesz decyzje GO/NO-GO między etapami
- Rozwiązujesz konflikty między agentami
- Monitorujesz postęp przez pliki signals/

## Workflow
Deleguj zadania do sub-agentów. Czekaj na sygnały ukończenia.
Między etapami sprawdzaj wyniki i podejmuj decyzje.
Jeśli etap się nie powiedzie — zdecyduj: retry, skip, abort.

## Komunikacja
- Zlecenia: zapisz JSON w results/stageN/task_*.json
- Sygnały: sprawdzaj results/signals/stageN_done.json
- Błędy: results/signals/error_*.json
""",
                trigger=None,
            )],
            system_message_suffix="Odpowiadaj po polsku. Bądź zwięzły.",
        ),
    )


def create_ksiega_analyst(llm) -> Agent:
    """📖 KSIĘGA ANALYST — parsuje Księgę, ekstrahuje wymagania.

    STAGE1-001 (v6.2.0): wymusza strict JSON output przez system prompt +
    flag `_strict_json` (LLM.completion_async doda response_format automatycznie
    dla providerów które wspierają JSON mode: OpenAI, Anthropic via tools, DeepSeek).
    """
    agent = Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name="ksiega_analyst",
                content=f"""Jesteś analitykiem dokumentu Księga SYLION.
{SYLION_CONTEXT}

## Twoja rola
Przeczytaj Księgę (dokument referencyjny ~900+ stron) i wyekstrahuj:
1. Wymagania bezpieczeństwa weryfikowalne w kodzie
2. Wymagania architektoniczne
3. Standardy implementacyjne

## Output format — STRICT JSON (STAGE1-001 v6.2.0)
Odpowiedź MUSI być poprawnym obiektem JSON. Bez markdown, bez komentarzy,
bez tekstu otaczającego. Struktura:
```
{{
  "requirements": [
    {{"id": "REQ-001", "category": "security|arch|impl",
      "priority": "P0|P1|P2", "description": "...",
      "verification": "..."}}
  ]
}}
```
Jeśli nie ma Księgi, zwróć `{{"requirements": []}}` — także w JSON.
Zapisz także do pliku: results/stage1/requirements.json
""",
                trigger=None,
            )],
        ),
    )
    # STAGE1-001: tag agenta do strict JSON mode (LLM.completion_async używa)
    try:
        object.__setattr__(agent, "_strict_json", True)
    except Exception:
        pass
    return agent


def create_build_agent(llm) -> Agent:
    """🔨 BUILD AGENT — kompiluje binaria SYLION."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name="build",
                content=f"""Jesteś agentem budującym binaria SYLION.
{SYLION_CONTEXT}

## Twoja rola
1. Zbuduj binaria:
   - sylion-server (linux/amd64)
   - sylion-verify (linux/amd64)
   - sylionctl (linux/amd64)
   - sylion-relay (linux/amd64 dla routera, linux/arm64 dla Pixel)

2. Komendy:
   ```bash
   export CGO_ENABLED=0 GOOS=linux
   
   # amd64 (router + server)
   GOARCH=amd64 go build -ldflags="-s -w" -o build/amd64/sylion-server ./cmd/sylion-server
   GOARCH=amd64 go build -ldflags="-s -w" -o build/amd64/sylion-verify ./cmd/sylion-verify
   GOARCH=amd64 go build -ldflags="-s -w" -o build/amd64/sylionctl ./cmd/sylionctl
   
   # arm64 (Pixel)
   GOARCH=arm64 go build -ldflags="-s -w" -o build/arm64/sylion-relay ./cmd/sylion-relay
   ```

3. Weryfikacja:
   - `go vet ./...`
   - `go test ./... -count=1`
   - Sprawdź rozmiar binarek, embed VERSION

4. Output:
   - Binaria w build/amd64/ i build/arm64/
   - Status w results/stage1/build_status.json
""",
                trigger=None,
            )],
        ),
    )


def create_auditor(llm, model_name: str, strengths: str) -> Agent:
    """🔍 AUDITOR — audyt kodu przez jeden model."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name=f"auditor_{model_name}",
                content=f"""Jesteś audytorem bezpieczeństwa kodu Go (model: {model_name}).
{SYLION_CONTEXT}

## Twoje mocne strony
{strengths}

## Twoja rola
1. Przeczytaj wymagania z results/stage1/requirements.json
2. Przeczytaj listę plików z results/stage1/file_manifest.json
3. Przeanalizuj KAŻDY plik pod kątem wymagań
4. Dla każdego problemu zapisz finding z polami:
   id, file, line, severity, category, requirement_id, title,
   description, evidence, fix_suggestion, confidence

## Output
Zapisz w: results/stage2_audit/audit_{model_name}.json
Po zakończeniu: utwórz results/signals/audit_{model_name}_done.json

## Zasady
- Bądź RYGORYSTYCZNY — lepiej false positive niż pominąć prawdziwy problem
- Czytaj pliki przez terminal (cat, grep) — nie zgaduj zawartości
- Podawaj DOKŁADNE numery linii
- confidence: 0.0-1.0 (jak pewny jesteś znaleziska)
""",
                trigger=None,
            )],
        ),
    )


def create_cross_verifier(llm, verifier_name: str) -> Agent:
    """🔄 CROSS-VERIFIER — weryfikuje ustalenia innych modeli."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name=f"verifier_{verifier_name}",
                content=f"""Jesteś niezależnym weryfikatorem audytu (model: {verifier_name}).
{SYLION_CONTEXT}

## Twoja rola
1. Przeczytaj findings INNYCH modeli z results/stage2_audit/
   (wszystkie pliki OPRÓCZ audit_{verifier_name}.json)
2. Dla KAŻDEGO finding'u:
   - Otwórz plik i linię wskazaną w finding'u
   - Zweryfikuj czy problem faktycznie istnieje
   - Oceń severity i sugerowaną naprawę

## Output format
Dla każdego finding'u:
  original_id, verdict (CONFIRMED/DISPUTED/INCONCLUSIVE),
  confidence, reasoning, additional_context, missed_by_original

Zapisz w: results/stage3_verify/verify_{verifier_name}.json
Po zakończeniu: results/signals/verify_{verifier_name}_done.json
""",
                trigger=None,
            )],
        ),
    )


def create_merger(llm) -> Agent:
    """🔀 MERGER — scala findings i podejmuje decyzje."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name="merger",
                content=f"""Jesteś architektem bezpieczeństwa podejmującym decyzje.
{SYLION_CONTEXT}

## Twoja rola
1. Przeczytaj WSZYSTKIE audyty z results/stage2_audit/
2. Przeczytaj WSZYSTKIE weryfikacje z results/stage3_verify/
3. Deduplikuj findings (po file + line ±5 + category)
4. Dla każdego unikalnego finding'u podejmij decyzję:
   - ACCEPT (≥3/4 potwierdza, 0 odrzuca) → do patchowania
   - REVIEW (2/4 lub sprzeczne) → do ręcznego przeglądu
   - SKIP (≤1/4 lub niska pewność) → pomijamy

## Output
Zapisz w: results/stage4_merge/merged_findings.json
Sygnał: results/signals/stage4_done.json z podsumowaniem
""",
                trigger=None,
            )],
        ),
    )


def create_patch_agent(llm, partition: int) -> Agent:
    """🩹 PATCH AGENT — generuje patche dla grupy findings."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name=f"patcher_{partition}",
                content=f"""Jesteś ekspertem Go generującym poprawki bezpieczeństwa.
{SYLION_CONTEXT}

## Twoja rola
1. Przeczytaj merged_findings.json z results/stage4_merge/
2. Weź findings z decyzją ACCEPT, partycja {partition}/4
   (sortuj po file, weź co 4-ty zaczynając od {partition-1})
3. Dla każdego finding'u:
   a. Przeczytaj plik źródłowy
   b. Wygeneruj MINIMALNĄ poprawkę
   c. Dodaj/zaktualizuj testy (table-driven)
   d. Sprawdź: go vet, go test

## Output
Dla każdego patcha:
  finding_id, patch (unified diff), test_patch, verification_commands,
  changelog_entry, verification_result (pass/fail)

Zapisz w: results/stage5_patch/patches_{partition}.json
Sygnał: results/signals/patch_{partition}_done.json
""",
                trigger=None,
            )],
        ),
    )


def create_pixel_deployer(llm) -> Agent:
    """📱 PIXEL DEPLOYER — wgrywa na Pixel przez ADB."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=2,
        agent_context=AgentContext(
            skills=[Skill(
                name="pixel_deployer",
                content=f"""Jesteś agentem wdrożeniowym dla Google Pixel z GrapheneOS.
{SYLION_CONTEXT}
{DEVICE_CONTEXT}

## Twoja rola
1. Sprawdź połączenie ADB: `bash device/pixel_manager.sh check`
2. Pobierz najnowszą wersję GrapheneOS OTA (jeśli wymaga aktualizacji)
3. Sideload OTA: `adb reboot recovery`, czekaj, `adb sideload ota.zip`
4. Po restarcie — deploy SYLION:
   - `adb push build/arm64/sylion-relay /data/local/tmp/`
   - `adb shell chmod +x /data/local/tmp/sylion-relay`
   - `adb push configs/pixel/ /data/local/tmp/sylion-config/`
5. Health check:
   - `adb shell /data/local/tmp/sylion-relay --version`
   - `adb shell /data/local/tmp/sylion-relay health`

## UWAGA na GrapheneOS
- Bootloader MUSI być UNLOCKED do sideload custom images
- OTA sideload: recovery sprawdza podpis (musi być signed by GrapheneOS)
- ADB debugging musi być włączony w Developer Options
- Root NIE jest dostępny w standardowym GrapheneOS

## Output
Zapisz w: results/stage6_deploy/pixel_status.json
Sygnał: results/signals/pixel_deployed.json
""",
                trigger=None,
            )],
        ),
    )


def create_router_deployer(llm) -> Agent:
    """📡 ROUTER DEPLOYER — wgrywa na router przez SSH."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=2,
        agent_context=AgentContext(
            skills=[Skill(
                name="router_deployer",
                content=f"""Jesteś agentem wdrożeniowym dla routera OpenWrt.
{SYLION_CONTEXT}
{DEVICE_CONTEXT}

## Twoja rola
1. Sprawdź połączenie: `bash device/router_manager.sh check 192.168.1.1`
2. Backup aktualnej konfiguracji: `bash device/router_manager.sh backup`
3. Deploy SYLION relay:
   - `scp build/amd64/sylion-relay root@192.168.1.1:/usr/local/bin/`
   - `ssh root@192.168.1.1 'chmod +x /usr/local/bin/sylion-relay'`
4. Deploy konfiguracji:
   - `scp configs/router/sylion.conf root@192.168.1.1:/etc/config/sylion`
5. Restart serwisu:
   - `ssh root@192.168.1.1 '/etc/init.d/sylion restart'`
6. Health check:
   - `ssh root@192.168.1.1 '/usr/local/bin/sylion-relay health'`

## Output
Zapisz w: results/stage6_deploy/router_status.json
Sygnał: results/signals/router_deployed.json
""",
                trigger=None,
            )],
        ),
    )


def create_test_agent(llm, test_type: str) -> Agent:
    """🧪 TEST AGENT — uruchamia testy na urządzeniach."""
    test_instructions = {
        "unit": """
## Unit Tests
1. `go test ./... -v -count=1 -coverprofile=coverage.out`
2. `go tool cover -func=coverage.out`
3. Sprawdź pokrycie (minimum 60% dla krytycznych pakietów)
4. Zapisz wyniki: results/stage7_test/unit_results.json
""",
        "integration": """
## Integration Tests
1. Sprawdź czy Pixel i Router są dostępne
2. Wyślij request z Pixel → Router relay → Server
3. Sprawdź flow: session establishment, key exchange, message relay
4. Testuj failover: rozłącz router, sprawdź auto-reconnect
5. Zapisz wyniki: results/stage7_test/integration_results.json
""",
        "e2e": """
## End-to-End Tests
1. Zainicjuj pełny flow SYLION:
   - Rejestracja urządzenia (Pixel → Server)
   - Zestawienie sesji (G1/G2 zones)
   - Wymiana wiadomości przez Matrix relay
   - Weryfikacja szyfrowania end-to-end
2. Sprawdź logi na wszystkich komponentach
3. Zapisz wyniki: results/stage7_test/e2e_results.json
""",
        "regression": """
## Regression Tests
1. Porównaj wyniki testów z poprzednią wersją
2. Sprawdź czy nowe patche nie złamały istniejącej funkcjonalności
3. Porównaj benchmarki (go test -bench .)
4. Sprawdź rozmiary binarek vs. poprzednia wersja
5. Zapisz wyniki: results/stage7_test/regression_results.json
""",
    }

    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name=f"tester_{test_type}",
                content=f"""Jesteś testerem SYLION (typ: {test_type}).
{SYLION_CONTEXT}
{DEVICE_CONTEXT}
{test_instructions.get(test_type, '')}

Po zakończeniu: results/signals/test_{test_type}_done.json
""",
                trigger=None,
            )],
        ),
    )


def create_red_team_agent(llm, attack_type: str) -> Agent:
    """🔴 RED TEAM — offensive security testing."""
    attack_instructions = {
        "network": """
## Network Attack Scenarios
Przeprowadź testy penetracyjne na warstwie sieciowej:

1. **Recon:** Skanuj porty na Pixel i Router
   ```bash
   nmap -sV -p- <router_ip>
   adb shell 'netstat -tlnp'
   ```

2. **Man-in-the-Middle:** Spróbuj przechwycić ruch Pixel↔Router
   - Czy TLS jest poprawnie zaimplementowany?
   - Czy certyfikaty są weryfikowane?

3. **Replay Attack:** Przechwycić i powtórzyć pakiety sesji

4. **DNS/ARP Spoofing:** Czy urządzenia weryfikują DNS responses?

5. **DoS:** Flooding na relay endpointy routera

6. **Egress Testing:** Spróbuj nawiązać połączenia do nieautoryzowanych adresów

UWAGA: Wszystkie ataki na LOKALNE urządzenia przez USB. NIE atakuj zewnętrznych serwisów.

Zapisz: results/stage8_security/red_network.json
""",
        "app": """
## Application Attack Scenarios
Przeprowadź testy penetracyjne na warstwie aplikacji:

1. **API Fuzzing:** Wyślij zniekształcone requesty do SYLION API
   ```bash
   # Fuzzing endpoint session
   curl -X POST http://localhost:PORT/api/v1/sessions \\
     -H "Content-Type: application/json" \\
     -d '{"user":"'; DROP TABLE--","session":"<script>alert(1)</script>"}'
   ```

2. **Auth Bypass:** Spróbuj dostać się do chronionych endpointów bez tokena

3. **Privilege Escalation:** Spróbuj eskalować z user → admin

4. **Input Validation:** SQL injection, XSS, command injection

5. **Token/Session attacks:** Przewidywalność tokenów, session fixation

6. **Error Information Leak:** Spróbuj wymusić błędy i zbadaj odpowiedzi

Zapisz: results/stage8_security/red_app.json
""",
    }

    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name=f"red_team_{attack_type}",
                content=f"""Jesteś operatorem Red Team SYLION (specjalizacja: {attack_type}).
{SYLION_CONTEXT}
{DEVICE_CONTEXT}

## ZASADY RED TEAM
- Atakujesz TYLKO lokalne urządzenia (Pixel, Router, localhost)
- NIE atakujesz zewnętrznych serwisów
- Dokumentuj KAŻDY krok ataku
- Przy znalezieniu podatności — zatrzymaj się, nie exploituj dalej
- Severity: CRITICAL/HIGH/MEDIUM/LOW

{attack_instructions.get(attack_type, '')}

Po zakończeniu: results/signals/red_{attack_type}_done.json
""",
                trigger=None,
            )],
        ),
    )


def create_blue_team_agent(llm, defense_type: str) -> Agent:
    """🔵 BLUE TEAM — monitoring, detection, hardening."""
    defense_instructions = {
        "monitor": """
## Monitoring & Detection
Monitoruj urządzenia podczas ataków Red Team:

1. **Log Analysis:**
   - Router: `ssh root@router 'logread -f'`
   - Pixel: `adb logcat -s SYLION:*`
   - Szukaj anomalii, nieautoryzowanych dostępów

2. **Network Monitoring:**
   - `ssh root@router 'tcpdump -i br-lan -w /tmp/capture.pcap'`
   - Analizuj czy ataki Red Team są wykrywane

3. **Process Monitoring:**
   - Czy SYLION procesy działają poprawnie?
   - Czy nie ma nieautoryzowanych procesów?

4. **Alert Correlation:**
   - Powiąż logi z atakami Red Team
   - Oceń czas detekcji (TTD)
   - Raportuj co zostało wykryte vs. co pominięte

Zapisz: results/stage8_security/blue_monitor.json
""",
        "hardener": """
## Hardening Recommendations
Na podstawie wyników audytu i Red Team:

1. **Firewall Rules:**
   - Przejrzyj i zaostrzaj reguły OpenWrt
   - Zablokuj niepotrzebne porty
   - Egress filtering

2. **TLS Configuration:**
   - Sprawdź cipher suites
   - Minimum TLS 1.3
   - Certificate pinning

3. **OS Hardening:**
   - GrapheneOS: sprawdź exploit protection
   - OpenWrt: disable unnecessary services
   - File permissions

4. **Application Hardening:**
   - Rate limiting
   - Input validation completeness
   - Security headers

Zapisz: results/stage8_security/blue_hardening.json
""",
    }

    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name=f"blue_team_{defense_type}",
                content=f"""Jesteś operatorem Blue Team SYLION (specjalizacja: {defense_type}).
{SYLION_CONTEXT}
{DEVICE_CONTEXT}

{defense_instructions.get(defense_type, '')}

Po zakończeniu: results/signals/blue_{defense_type}_done.json
""",
                trigger=None,
            )],
        ),
    )


def create_reporter(llm) -> Agent:
    """📊 REPORTER — generuje raport końcowy."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=4,
        agent_context=AgentContext(
            skills=[Skill(
                name="reporter",
                content=f"""Jesteś reporterem pipeline'u audytu SYLION.
{SYLION_CONTEXT}

## Twoja rola
Przeczytaj WSZYSTKIE wyniki z results/ i wygeneruj:

1. **audit_report.md** — kompletny raport w Markdown:
   - Podsumowanie wykonawcze
   - Wyniki audytu (CRITICAL → LOW)
   - Analiza konsensusu modeli
   - Wyniki Red Team / Blue Team
   - Status deploymentu i testów
   - Macierz śledzenia (Księga → Finding → Patch → Test)
   - Rekomendacje

2. **CHANGELOG fragment** — opis zmian dla bieżącej wersji

3. **traceability_update.json** — aktualizacja macierzy śledzenia

Zapisz w: results/stage9_report/
""",
                trigger=None,
            )],
        ),
    )
