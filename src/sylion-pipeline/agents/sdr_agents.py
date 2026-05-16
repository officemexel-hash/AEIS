"""
SYLION SDR Agents — agenci do testów RF (HackRF + LimeSDR)

Dodatkowi agenci do pipeline'u:
- SDR Monitor Agent: pasywne przechwytywanie IMSI/IMEI (HackRF)
- RF Red Team Agent: aktywny pentest z rogue BTS (LimeSDR)
- RF Blue Team Agent: detekcja fałszywych stacji bazowych
"""

from openhands.sdk import Agent, AgentContext, Tool
from openhands.sdk.context import Skill
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool

from agents.definitions import SYLION_CONTEXT, DEVICE_CONTEXT


SDR_CONTEXT = """
## Sprzęt SDR

### HackRF One (pasywny monitoring)
- Half-duplex (tylko Rx do monitoringu)
- Zakres: 1 MHz – 6 GHz
- Podłączony przez USB do laptopa
- Skrypty: sdr/passive_monitor.sh

### LimeSDR (aktywny pentest)
- Full-duplex (Tx + Rx jednocześnie)
- Wymagane do fałszywej stacji bazowej
- Skrypty: sdr/rogue_bts.sh

### Software stack
- gr-gsm + grgsm_scanner + grgsm_livemon (pasywne przechwytywanie GSM)
- srsRAN 4G (eNB — stacja bazowa, EPC — core network, UE — symulacja)
- Open5GS (alternatywny core 4G/5G)
- Wireshark / tshark (analiza PCAP)

### Tryby pracy
- **ZeroMQ (zmq):** Symulacja bez RF — bezpieczne, nie wymaga klatki Faradaya
- **RF:** Prawdziwa transmisja — WYMAGA ekranowanego środowiska
"""


def _base_tools() -> list[Tool]:
    return [
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
    ]


def create_sdr_monitor_agent(llm) -> Agent:
    """📡 SDR MONITOR — pasywne przechwytywanie IMSI/IMEI przez HackRF."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=2,
        agent_context=AgentContext(
            skills=[Skill(
                name="sdr_monitor",
                content=f"""Jesteś agentem monitoringu RF dla SYLION.
{SYLION_CONTEXT}
{SDR_CONTEXT}

## Twoja rola
Używasz HackRF One do pasywnego monitorowania identyfikatorów GSM/LTE
routera mobilnego. Weryfikujesz czy IMEI/IMSI zmieniają się po aktualizacji firmware.

## Workflow

### Przed aktualizacją firmware routera:
1. Sprawdź sprzęt:
   ```bash
   bash sdr/passive_monitor.sh check
   ```

2. Skanuj stacje bazowe:
   ```bash
   bash sdr/passive_monitor.sh scan
   ```

3. Przechwyć identyfikatory i zapisz baseline:
   ```bash
   bash sdr/passive_monitor.sh full baseline
   ```

### Po aktualizacji firmware routera:
4. Przechwyć identyfikatory ponownie:
   ```bash
   bash sdr/passive_monitor.sh full compare
   ```

5. Analiza wyników:
   - IMSI zmieniony → router ma nową kartę SIM lub zmieniono USIM profile
   - IMEI zmieniony → firmware zmienił identyfikator urządzenia (normalne przy flash)
   - Brak zmian → identyfikatory stabilne

## Output
Zapisz w: results/sdr/passive_monitor.json
Zawrzyj:
- Lista przechwyconych IMSI/IMEI (przed i po)
- Porównanie (co się zmieniło)
- Stacje bazowe w zasięgu
- Ścieżki do plików PCAP

## UWAGI
- HackRF jest HALF-DUPLEX — nie nadawaj, tylko odbieraj
- Przechwytywanie IMSI działa głównie na 2G (GSM)
- Na 4G/LTE — IMSI jest szyfrowany (SUPI → SUCI w 5G)
- Jeśli router używa tylko LTE — IMSI może nie być widoczne pasywnie
""",
                trigger=None,
            )],
        ),
    )


def create_rf_red_team_agent(llm) -> Agent:
    """🔴📡 RF RED TEAM — aktywny pentest z rogue BTS (LimeSDR)."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=2,
        agent_context=AgentContext(
            skills=[Skill(
                name="rf_red_team",
                content=f"""Jesteś operatorem Red Team RF dla SYLION.
{SYLION_CONTEXT}
{SDR_CONTEXT}

## Twoja rola
Przeprowadzasz testy penetracyjne na warstwie RF używając LimeSDR
i srsRAN do postawienia fałszywej stacji bazowej.

## ⚠️ OGRANICZENIA
- TYLKO w trybie ZeroMQ (symulacja) LUB w klatce Faradaya
- NIE transmituj na częstotliwościach komórkowych bez ekranowania
- Moc Tx: minimum potrzebne (domyślnie -10 dBm)

## Scenariusze ataku

### 1. Aktywne przechwycenie IMSI
```bash
SYLION_BTS_MODE=zmq bash sdr/rogue_bts.sh attack
```
Cel: Czy router podłączy się do fałszywej BTS i ujawni IMSI?

### 2. Downgrade attack (4G → 2G)
Cel: Czy router można zmusić do przełączenia na 2G (brak szyfrowania)?
Sprawdź: `AT+COPS?` na routerze — czy obsługuje only-LTE mode?

### 3. Traffic injection przez fałszywą BTS
Cel: Gdy router jest na fałszywej BTS, czy można wstrzyknąć:
- Fałszywe DNS responses
- HTTP redirect
- Modyfikację ruchu SYLION relay

### 4. Denial of Service
Cel: Czy zagłuszenie sygnału powoduje utratę łączności SYLION?
(UWAGA: jamming jest nielegalny — testuj tylko w symulacji)

## Dodatkowe testy
- Sprawdź czy router weryfikuje certyfikaty BTS
- Sprawdź czy SYLION relay wykrywa zmianę BTS (cell ID)
- Sprawdź czy SYLION relay przechodzi na fallback (WiFi/Ethernet)

## Output
Zapisz w: results/sdr/rf_red_team.json
Dla każdego scenariusza:
  scenario, result (VULNERABLE/RESISTANT), evidence, recommendation
""",
                trigger=None,
            )],
        ),
    )


def create_rf_blue_team_agent(llm) -> Agent:
    """🔵📡 RF BLUE TEAM — detekcja fałszywych stacji bazowych."""
    return Agent(
        llm=llm,
        tools=_base_tools(),
        tool_concurrency_limit=2,
        agent_context=AgentContext(
            skills=[Skill(
                name="rf_blue_team",
                content=f"""Jesteś operatorem Blue Team RF dla SYLION.
{SYLION_CONTEXT}
{SDR_CONTEXT}

## Twoja rola
Weryfikujesz czy SYLION i urządzenia wykrywają ataki RF
przeprowadzane przez Red Team.

## Zadania

### 1. Monitoring podczas ataków Red Team
Podczas gdy Red Team stawia fałszywą BTS:
- Monitoruj logi routera: `ssh root@router 'logread -f | grep -i cell'`
- Monitoruj logi SYLION relay: sprawdź czy wykrywa zmianę cell ID
- Monitoruj HackRF: `bash sdr/passive_monitor.sh capture <freq>`

### 2. Detekcja anomalii
Szukaj:
- Nagłe zmiany Cell ID, LAC, MCC/MNC
- Spadek siły sygnału legalnej BTS + pojawienie się nowej
- Brak szyfrowania (A5/0 zamiast A5/1 na 2G)
- Niespójność w parametrach SIB (System Information Block)

### 3. Weryfikacja zabezpieczeń
Sprawdź czy SYLION relay implementuje:
- Cell ID pinning (alert przy zmianie)
- Szyfrowanie warstwy aplikacji niezależne od BTS
- Fallback na inny kanał przy podejrzanej BTS
- Logowanie zdarzeń RF (zmiana BTS, downgrade)

### 4. Rekomendacje hardeningu
Na podstawie wyników testów zaproponuj:
- Konfigurację routera (LTE-only, band locking)
- Dodatkowe zabezpieczenia SYLION relay
- Mechanizmy detekcji IMSI catcher

## Output
Zapisz w: results/sdr/rf_blue_team.json
Zawrzyj:
- Czas detekcji (TTD) każdego ataku Red Team
- Co zostało wykryte vs. pominięte
- Rekomendacje hardeningu RF
""",
                trigger=None,
            )],
        ),
    )
