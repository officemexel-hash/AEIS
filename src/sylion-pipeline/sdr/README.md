# SYLION SDR Module — HackRF + LimeSDR

Moduł testów RF dla pipeline'u SYLION. Wykorzystuje HackRF One (pasywny monitoring)
i LimeSDR (aktywny pentest / fałszywa stacja bazowa) do weryfikacji bezpieczeństwa
routera mobilnego w zamkniętym środowisku laboratoryjnym.

## ⚠️ UWAGA PRAWNA

**Wszystkie testy RF MUSZĄ odbywać się w zamkniętym, ekranowanym środowisku.**
Transmisja na częstotliwościach komórkowych bez licencji jest nielegalna.

Wymagania:
- Klatka Faradaya / ekranowane pomieszczenie / RF shielding bag
- LUB: tryb ZeroMQ (symulacja bez RF — `srsRAN` z `device_name = zmq`)
- Moc transmisji: minimum potrzebne (< 1mW w ekranowanym środowisku)

## Architektura

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZAMKNIĘTE ŚRODOWISKO RF                        │
│                  (Klatka Faradaya / RF Shield)                    │
│                                                                   │
│   ┌──────────────┐        ┌───────────────┐                     │
│   │ Router mobilny│◄──RF──►│ LimeSDR       │                     │
│   │ (OpenWrt +    │        │ (Fake BTS /   │                     │
│   │  modem LTE)   │        │  srsRAN eNB)  │                     │
│   └──────┬───────┘        └───────┬───────┘                     │
│          │                        │ USB                           │
│   ┌──────┴───────┐        ┌───────┴───────┐                     │
│   │ Pixel phone   │        │               │                     │
│   │ (GrapheneOS)  │        │               │                     │
│   └──────┬───────┘        │   LAPTOP      │                     │
│          │ USB             │               │                     │
│          └────────────────►│  ┌─────────┐  │                     │
│                            │  │ HackRF  │  │  (pasywny Rx)       │
│                            │  │ One     │◄─┼──RF (tylko odbiór)  │
│                            │  └─────────┘  │                     │
│                            │               │                     │
│                            │  Agenci AI:   │                     │
│                            │  • SDR Monitor│                     │
│                            │  • RF Red Team│                     │
│                            │  • RF Blue Tm │                     │
│                            └───────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

## Dwa tryby pracy

### Tryb 1: Pasywny monitoring (HackRF One)
- **Cel:** Weryfikacja czy IMEI/IMSI routera zmieniają się po aktualizacji firmware
- **Hardware:** HackRF One (Rx only)
- **Software:** gr-gsm + grgsm_livemon + IMSI-catcher script
- **Legalność:** Pasywny odbiór — legalne w większości jurysdykcji
- **Workflow:**
  1. Zeskanuj stacje bazowe: `grgsm_scanner`
  2. Nagraj baseline IMEI/IMSI routera
  3. Wgraj nowy firmware na router
  4. Nagraj nowe IMEI/IMSI
  5. Porównaj — raportuj zmiany

### Tryb 2: Aktywny pentest — Rogue BTS (LimeSDR)
- **Cel:** Red Team test — próba przechwycenia/manipulacji ruchu routera
- **Hardware:** LimeSDR (full duplex — wymagane do TX+RX)
- **Software:** srsRAN 4G (eNB) + Open5GS (EPC) lub YateBTS (2G)
- **Legalność:** TYLKO w klatce Faradaya / z ZeroMQ (bez RF)
- **Workflow:**
  1. Postawienie fałszywej stacji bazowej (2G/4G)
  2. Próba wymuszenia downgrade z 4G→2G
  3. Próba przechwycenia IMSI
  4. Próba wstrzyknięcia ruchu do routera
  5. Weryfikacja czy router odrzuca fałszywą BTS

## Wymagane oprogramowanie

```bash
# GNU Radio + gr-gsm (pasywny monitoring)
sudo apt install gnuradio gr-gsm hackrf libhackrf-dev

# srsRAN 4G (aktywny pentest / symulacja)
sudo apt install srsran cmake build-essential libfftw3-dev \
  libmbedtls-dev libboost-all-dev libconfig++-dev \
  libsctp-dev libzmq3-dev

# Open5GS (core network dla srsRAN)
sudo apt install open5gs

# LimeSDR driver
sudo apt install limesuite soapysdr-module-lms7

# Narzędzia analizy
sudo apt install wireshark tshark tcpdump
```

## Sprzęt

| Urządzenie | Rola | Tryb | Wymagane |
|------------|------|------|----------|
| HackRF One | Pasywny Rx (skanowanie, IMSI capture) | Tylko odbiór | Tak |
| LimeSDR | Aktywny Tx+Rx (fake BTS) | Full duplex | Opcjonalne |
| Antena GSM 900/1800 | Odbiór/nadawanie | — | Tak |
| RF Shield / Klatka Faradaya | Izolacja RF | — | WYMAGANE dla Tx |
