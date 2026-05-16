# SYLION Secure — Pixel 9 Provisioning STRIDE Threat Model

**Wersja:** 1.0.0  
**Data:** 2025-01-19  
**Scope:** `pixel_provision.py` + `device/pixel_manager.sh`  
**Produkt:** SYLION Secure = Google Pixel 9 + GrapheneOS + Mudi  
**Klasyfikacja:** INTERNAL — CONFIDENTIAL

---

## 1. Architektura przepływu provisioning

```
[Operator] ──USB──► [Pixel 9 (stock Android)]
                        │
  Windows Host          │  WSL2 (Linux)
  ┌────────────┐        │  ┌──────────────────────────────────┐
  │ usbipd.exe │◄───────┤  │ pixel_provision.py               │
  └────────────┘        │  │                                  │
                        │  │  Phase A:                        │
                        └──┤  S1: USB passthrough (usbipd)    │
                           │  S2: ADB auth                    │
                           │  S3: Device info + model check   │
                           │  S4: OEM unlock check            │
                           │  S5: GrapheneOS flash readiness  │
                           │  S6: Root check (Magisk)         │
                           │  S7: Deploy SYLION agent         │
                           │  S7.5: FIDO2 HumanGate ◄──────── [Operator physical]
                           │                                  │
                           │  Phase B (post-FIDO2):           │
                           │  S8: Final verification          │
                           └──────────────────────────────────┘
```

**Trust boundaries:**
- `TB1`: Windows Host ↔ WSL2 (usbipd passthrough)
- `TB2`: WSL2 ↔ Pixel 9 (USB/ADB)
- `TB3`: Pipeline ↔ Dashboard API (`/api/devices/provision-pixel`)
- `TB4`: FIDO2 hardware key ↔ Pixel 9 USB-C port
- `TB5`: Operator ↔ Dashboard (HumanGate confirmation)

---

## 2. Aktywa (Assets) podlegające ochronie

| ID  | Asset                            | Wartość    | Lokalizacja                  |
|-----|----------------------------------|------------|------------------------------|
| A1  | GrapheneOS image (OTA .zip)      | KRYTYCZNA  | Lokalny dysk operatora       |
| A2  | ADB authorization key            | WYSOKA     | `~/.android/adbkey`          |
| A3  | SYLION agent + config            | WYSOKA     | `/data/local/tmp/sylion/`    |
| A4  | FIDO2 seed / enrollment          | KRYTYCZNA  | Klucz sprzętowy (YubiKey)    |
| A5  | Device serial number             | ŚREDNIA    | DB `devices.serial`          |
| A6  | Bootloader unlock state          | KRYTYCZNA  | Pixel TEE / fuse             |
| A7  | provisioning audit log           | WYSOKA     | `pixel_manager_YYYYMMDD.log` |
| A8  | DB `devices.model`               | ŚREDNIA    | SQLite dashboard             |

---

## 3. Aktorzy (Threat Actors)

| ID  | Aktor                             | Motywacja           | Poziom          |
|-----|-----------------------------------|---------------------|-----------------|
| TA1 | Złośliwy insider (operator)       | Sabotaż / kradzież  | Wysoki          |
| TA2 | Zewnętrzny atakujący (fizyczny)   | Przejęcie urządzenia| Średni          |
| TA3 | Supply chain (vendor)             | Backdoor w OS/HW    | Wysoki          |
| TA4 | Atakujący sieciowy (pivot WSL2)   | Lateral movement    | Średni          |
| TA5 | Złośliwe USB / BadUSB             | HID/ADB injection   | Wysoki          |

---

## 4. STRIDE Threat Model — 8 etapów

### S1: USB Passthrough (usbipd attach)

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-01** Fake USB device imitujący Pixel 9 (VID:18D1). Atakujący podłącza złośliwe urządzenie emulujące Google Pixel (np. przez Facedancer/GreatFET). Script w L208-215 wykrywa bus na podstawie stringa "google/pixel/18d1" — trivially spoofable. | TB1, TB2 | **KRYTYCZNY** |
| **Tampering** | **AV-02** Podmiana busid w wywołaniu usbipd powoduje attach innego urządzenia USB. Walidacja regex w L179 (`^\d+-\d+(\.\d+)*$`) sprawdza tylko format, nie tożsamość. | TB1 | WYSOKI |
| **Repudiation** | **AV-03** Brak logu zdarzenia "który device USB został załączony o której godzinie". `result.add_step` nie zapisuje timestampu Unix ani hasha VID/PID. | — | ŚREDNI |
| **Info Disclosure** | **AV-04** stdout usbipd (L197-215) może wyciec pełną listę urządzeń USB do logów systemowych. | TB1 | NISKI |
| **DoS** | **AV-05** Wielokrotne `usbipd bind --force` bez cleanup może zająć slot USB i uniemożliwić ponowne przypisanie. | TB1 | NISKI |
| **Elevation of Privilege** | **AV-06** `usbipd bind --force` jest wywoływany bez weryfikacji, czy operator ma uprawnienia admina Windows. Komenda może eskalować prawa w kontekście WSL interop. | TB1 | WYSOKI |

**Countermeasures (CM):**
- `CM-01` Weryfikuj VID:PID przez `usbipd list --json` + sprawdzenie `idVendor=18d1` przed bind.
- `CM-02` Dodaj audit log z timestampem, busid, VID, PID do każdego zdarzenia usbipd.
- `CM-03` Wymagaj potwierdzenia operatora (HumanGate) przy auto-detekcji urządzenia.

---

### S2: ADB Authentication

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-07** ADB "unauthorized" → operator akceptuje dialog na urządzeniu bez weryfikacji, że klucz hosta (`~/.android/adbkey`) należy do zaufanej stacji roboczej. Skradziony `adbkey` = pełny dostęp ADB do każdego Pixela. | TB2 | **KRYTYCZNY** |
| **Tampering** | **AV-08** Brak pinning'u klucza ADB — żaden istniejący klucz autoryzacyjny nie jest sprawdzany przed sesją. Dowolny klucz akceptuje urządzenie jeśli operator kliknie "Allow". | TB2 | WYSOKI |
| **Repudiation** | **AV-09** `step_check_adb` nie zapisuje fingerprinta klucza RSA użytego do autoryzacji. Brak dowodu który klucz był użyty. | — | WYSOKI |
| **Info Disclosure** | **AV-10** Stan "unauthorized" jest eksponowany przez dashboard (przez `requires_manual` list) → może ujawnić serial device'a w logach publicznych. | TB3 | ŚREDNI |
| **DoS** | — | — | — |
| **EoP** | **AV-11** Po provisioning ADB debugging pozostaje aktywne (brak `adb shell settings put global adb_enabled 0` w step_verify). Pozostawiony root przez ADB = trwały backdoor. | TB2 | **KRYTYCZNY** |

**Countermeasures (CM):**
- `CM-04` Po zakończeniu provisioning: `adb shell settings put global adb_enabled 0` jako obligatoryjny krok S8.
- `CM-05` Zapisuj RSA fingerprint klucza ADB w audit log przy każdym połączeniu.
- `CM-06` Waliduj że `adbkey` pochodzi z dedykowanego certatu provisionera (pinning).

---

### S3: Device Info & Model Check

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-12** Złośliwy device może zwrócić fałszywe `ro.product.model = "Pixel 9"` i `ro.grapheneos.version = "..."` przez zmodyfikowane `getprop`. Model check (L367-385) oparty wyłącznie na getprop — trivially bypassable. | TB2 | **KRYTYCZNY** |
| **Tampering** | **AV-13** SQL injection w `_save_model_to_db` (L424): `model` pochodzi z `adb shell getprop` i jest wstawiane przez parametryzowane zapytanie — bezpieczne. Ale `serial` nie jest validowane przed DB write (L421-424). | TB2, TB3 | ŚREDNI |
| **Repudiation** | **AV-14** `step_get_device_info` nie zapisuje `build_fingerprint` do audit trail provisioning job. Niemożliwe post-facto określenie jakiego ROM-u użyto. | — | WYSOKI |
| **Info Disclosure** | — | — | — |
| **DoS** | **AV-15** `force=True` bypass modelu (CLI `--force`) może sprowokować provisioning na nieznanym urządzeniu, co zakończy się brickiem. | TB3 | WYSOKI |
| **EoP** | — | — | — |

**Countermeasures (CM):**
- `CM-07` Weryfikuj tożsamość urządzenia przez `fastboot getvar all` (certyfikat attestation z TEE) zamiast wyłącznie getprop.
- `CM-08` Zapisuj `build_fingerprint` w `provisioning_jobs` DB jako pole `fingerprint_at_provision`.
- `CM-09` `--force` wymaga explicitnego potwierdzenia HumanGate z uzasadnieniem.

---

### S4: OEM Unlock / Bootloader Unlock (CRITICAL — IRREVERSIBLE)

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-16** Stan `ro.boot.verifiedbootstate=orange` może być fałszywie zgłoszony przez zmodyfikowany ROM. Script traktuje "orange" = unlocked i kontynuuje bez potwierdzenia. | TB2 | WYSOKI |
| **Tampering** | **AV-17** **Brak HumanGate przed `fastboot flashing unlock`**. `step_check_oem_unlock` tylko sprawdza stan — ale faktyczne odblokowanie jest poza kodem i delegowane do operatora. Jeśli ktoś zautomatyzuje `fastboot flashing unlock` (np. przez patch), staje się nieodwracalne. | TB2 | **KRYTYCZNY** |
| **Repudiation** | **AV-18** Brak zapisu timestampu faktycznego unlock w audit DB. `requires_manual` lista zawiera nazwę kroku ale nie czas wykonania. | — | WYSOKI |
| **Info Disclosure** | — | — | — |
| **DoS** | **AV-19** Przerwa zasilania podczas unlock sequence (po `fastboot flashing unlock` przed reflashem) = brick (bootloader unlocked, stock ROM wymazany, GrapheneOS nie zainstalowany). | — | **KRYTYCZNY** |
| **EoP** | **AV-20** Operator z dostępem do pipeline może wywołać `provision_pixel(skip_flash=True)` po unlock — urządzenie zostanie z odblokowanym bootloaderem i stock ROM-em = złoto dla physical attacker. | TB3 | **KRYTYCZNY** |

**Countermeasures (CM):**
- `CM-10` Dodaj obligatoryjny HumanGate PRZED każdym destructive step (unlock, flash, factory reset): `_require_human_gate("BOOTLOADER_UNLOCK")`.
- `CM-11` Implementuj "rollback checkpoint" — jeśli flash nie powiedzie się po unlock, wymuś `fastboot flashing lock` zanim pipeline zakończy się błędem.
- `CM-12` Zapisuj timestamp unlock/lock do `provisioning_audit_events` (osobna tabela od `steps`).

---

### S5: GrapheneOS Flash

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | — | — | — |
| **Tampering** | **AV-21** `pixel_flash_grapheneos()` (shell) nie weryfikuje SHA-256 ani sygnatury GPG przed `adb sideload`. Złośliwy obraz OTA może zostać zaflashowany. Szczególnie groźne przez supply chain (TA3). | TB2 | **KRYTYCZNY** |
| **Repudiation** | **AV-22** Brak zapisu sumy kontrolnej zaflashowanego obrazu w audit logu. Niemożliwe post-facto udowodnienie co zostało wgrane. | — | WYSOKI |
| **Info Disclosure** | **AV-23** `image_path` jest logowany w plaintext w `pixel_manager_YYYYMMDD.log` — może ujawnić lokalizację sekretnych plików OTA. | TB2 | NISKI |
| **DoS** | **AV-24** Przerwanie sideload w trakcie (timeout, USB disconnect) = partial flash = brick. Brak retry logic z checksum verification w `pixel_flash_grapheneos`. | — | WYSOKI |
| **EoP** | **AV-25** Supply chain: GrapheneOS z backdoor firmware = trwały EoP na poziomie TEE/bootloader. | TA3 | **KRYTYCZNY** |

**Countermeasures (CM):**
- `CM-13` MANDATORY: przed sideload/flash weryfikuj `sha256sum ${image_path}` przeciwko oficjalnemu hashu z `https://releases.grapheneos.org/` (HTTPS pinning).
- `CM-14` MANDATORY: weryfikuj podpis GPG obrazu (klucz GrapheneOS: `65EEFE022108E2B708CBFCF7F9E712E59AF5F22A`).
- `CM-15` Zapisuj `sha256:${hash}` zaflashowanego obrazu do `provisioning_jobs.grapheneos_sha256`.
- `CM-16` Implementuj retry z full-verification po przerwaniu flash.

---

### S6: Root Check (Magisk)

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-26** Magisk może ukryć swój package name (`com.topjohnwu.magisk`). Sprawdzenie przez `pm list packages` (L521-522) jest podatne na MagiskHide / Shamiko — false negative dla złośliwego roota. | TB2 | WYSOKI |
| **Tampering** | — | — | — |
| **Repudiation** | — | — | — |
| **Info Disclosure** | — | — | — |
| **DoS** | — | — | — |
| **EoP** | **AV-27** Pipeline akceptuje root check jako "ok" (L529-531) gdy `has_su=True` — nie weryfikuje czy to autoryzowany Magisk vs. nieznany rootkit. Root = pełny EoP nad urządzeniem. | TB2 | **KRYTYCZNY** |

**Countermeasures (CM):**
- `CM-17` Po provisioning: wymuś **wyłączenie** root dla aplikacji nieautoryzowanych przez SYLION. Magisk nie powinien być aktywny po finalizacji (jeśli nie jest wymagany przez architekturę).
- `CM-18` Jeśli root jest wymagany: zapisuj `magisk_version` + `sha256(boot.img)` w audit logu.

---

### S7: Deploy SYLION Agent

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | — | — | — |
| **Tampering** | **AV-28** `step_deploy_agent` nie weryfikuje integralności lokalnych plików `device_harness.py` i `pixel_manager.sh` przed wysłaniem na urządzenie. Atakujący z dostępem do systemu plików maszyny provisionera może podłożyć złośliwe pliki. | TB2 | **KRYTYCZNY** |
| **Repudiation** | **AV-29** Brak SHA-256 plików wgranych na urządzenie w logach provisioning. `agent_deploy_ok` w result zawiera tylko nazwy plików, nie sumy kontrolne. | — | WYSOKI |
| **Info Disclosure** | **AV-30** `DEVICE_SYLION_DIR = "/data/local/tmp/sylion"` — `tmp/` jest world-readable w trybie ADB. Pliki konfiguracyjne SYLION z sekretnymi danymi mogą być odczytane przez inne procesy z dostępem shell. | TB2 | WYSOKI |
| **DoS** | — | — | — |
| **EoP** | **AV-31** `chmod 755` na wgrane skrypty (L577) + lokalizacja w `/data/local/tmp/` = wykonywalne przez każdy proces z `adb shell`. Jeśli ADB debugging zostanie pozostawione, atakujący zdalny ma wykonanie kodu. | TB2 | **KRYTYCZNY** |

**Countermeasures (CM):**
- `CM-19` Weryfikuj SHA-256 plików lokalnych przed push: porównaj z release manifest (`.sha256sums`).
- `CM-20` Po deploy: `adb shell chmod 700 ${DEVICE_SYLION_DIR}` (nie 755), owner=shell, no world-read.
- `CM-21` Przenieś SYLION agent do `/data/data/com.sylion.agent/` (app-private) zamiast `/data/local/tmp/`.

---

### S7.5: FIDO2 HumanGate

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-32** Endpoint `POST /provision/{job_id}/fido2-confirm` nie jest wymieniony w kodzie jako chroniony przez CSRF/FIDO2. Złośliwy serwis może wysłać fałszywe potwierdzenie FIDO2 bez fizycznej interakcji operatora. | TB3 | **KRYTYCZNY** |
| **Tampering** | — | — | — |
| **Repudiation** | **AV-33** `step_fido2_enroll` zawsze zwraca `True` (L649) bez cryptographic proof of enrollment. Brak weryfikacji, że klucz FIDO2 faktycznie był użyty. | — | **KRYTYCZNY** |
| **Info Disclosure** | **AV-34** `FIDO2_INSTRUCTIONS` zawarte w `result.fido2_instructions` mogą być zwrócone przez API do nieautoryzowanego klienta jeśli `provision-pixel` endpoint nie ma auth. | TB3 | ŚREDNI |
| **DoS** | **AV-35** Pipeline zatrzymuje się w nieskończoność jeśli operator nigdy nie wyśle `fido2-confirm` — brak timeout na HumanGate phase. | — | WYSOKI |
| **EoP** | — | — | — |

**Countermeasures (CM):**
- `CM-22` `fido2-confirm` endpoint musi wymagać uwierzytelnienia operatora (JWT + FIDO2 challenge-response), nie tylko job_id.
- `CM-23` Dodaj timeout HumanGate: jeśli `fido2-confirm` nie przyjdzie w ciągu N minut, anuluj job i wymuś `adb shell settings put global adb_enabled 0`.
- `CM-24` Zapisz cryptographic attestation w audit logu: challenge UUID + response timestamp.

---

### S8: Final Verification

| STRIDE | Zagrożenie | Wektor ataku | Kod ryzyka |
|--------|-----------|--------------|------------|
| **Spoofing** | **AV-36** `step_verify` sprawdza `echo SYLION_OK` przez ADB (L662) — dowolny fake device może zwrócić ten string. Weryfikacja jest semantic-only, nie kryptograficzna. | TB2 | WYSOKI |
| **Tampering** | — | — | — |
| **Repudiation** | **AV-37** `verify_summary` nie weryfikuje: (a) że ADB debugging jest wyłączone, (b) że bootloader jest re-locked, (c) że nie ma nieznanych pakietów zainstalowanych. Prowizja może zakończyć się "ok" z krytycznymi misconfiguration. | — | **KRYTYCZNY** |
| **Info Disclosure** | **AV-38** ADB debugging pozostawione włączone po provisioning (brak wyłączenia w S8) = permanent Info Disclosure risk. | TB2 | **KRYTYCZNY** |
| **DoS** | — | — | — |
| **EoP** | **AV-39** Brak weryfikacji `ro.boot.verifiedbootstate=green` (bootloader locked) po zakończeniu provisioning. Urządzenie z unlocked bootloaderem może trafić do użytkownika końcowego. | TB2 | **KRYTYCZNY** |

**Countermeasures (CM):**
- `CM-25` Dodaj do `step_verify`: sprawdzenie `ro.boot.verifiedbootstate` == `green` lub `yellow`.
- `CM-26` Dodaj do `step_verify`: potwierdzenie że `adb_enabled == 0`.
- `CM-27` Dodaj do `step_verify`: sprawdzenie `ro.grapheneos.version` != "" (GrapheneOS zainstalowany).
- `CM-28` Dodaj do `step_verify`: uruchomienie Auditor attestation check (GrapheneOS feature).

---

## 5. Supply Chain Threats

| ID     | Zagrożenie                                                             | Countermeasure                                                 |
|--------|------------------------------------------------------------------------|----------------------------------------------------------------|
| SC-01  | Złośliwy GrapheneOS OTA (mirror, MITM na HTTP)                        | CM-13 + CM-14: SHA-256 + GPG verify przed flash               |
| SC-02  | Trojanizowany `usbipd.exe` zainstalowany przez operatora              | Weryfikuj hash usbipd.exe po instalacji (winget checksum)     |
| SC-03  | Złośliwy `adb` / `fastboot` w PATH (WSL package manager attack)       | Pinuj wersje: `adb --version` musi być >= 35.0.2               |
| SC-04  | Hardware-level backdoor w Pixel 9 (firmware/TEE)                     | Android Attestation API post-provision                        |
| SC-05  | Złośliwy FIDO2 klucz (klonowany/trojański YubiKey)                   | Weryfikuj `aaguid` klucza FIDO2 w attestation                 |

---

## 6. Rollback — scenariusze przerwania provisioning

| Etap przerwania                    | Stan urządzenia                              | Akcja naprawcza                                                 |
|------------------------------------|----------------------------------------------|-----------------------------------------------------------------|
| Po `usbipd attach`, przed ADB      | Normalny stock Android                       | Żadna — restart provisioning                                    |
| Po ADB auth, przed unlock          | ADB auth aktywna, bootloader locked          | Wyczyść `~/.android/adbkey` jeśli podejrzany klucz            |
| Po OEM unlock, przed flash         | **NIEBEZPIECZNY**: bootloader unlocked, bez ROM | **PRIORYTET**: `fastboot flash --disable-verity` GrapheneOS lub `fastboot flashing lock` |
| Podczas flash (w trakcie sideload) | Partial flash = BRICK możliwy               | Recovery mode → pełny reflash z zweryfikowanym obrazem         |
| Po flash, przed lock bootloader    | GrapheneOS bez locked bootloader            | `fastboot flashing lock` NATYCHMIAST                           |
| Po lock, przed deploy agent        | GrapheneOS z locked bootloader (OK)         | Restart od S7                                                  |
| Podczas FIDO2 HumanGate            | Agent wgrany, FIDO2 incomplete              | Anuluj job, wymuś factory reset przez `fastboot -w`            |
| Po FIDO2, przed verify             | Prawie gotowe                               | Wznów Phase B (`provision_pixel_phase_b`)                      |

**Rollback procedure (automatyczna):**

```python
# Wymagana implementacja w pipeline:
class RollbackCheckpoint:
    STAGES = ["pre_check", "unlocked", "flashed", "locked", "agent_deployed", "fido2_done"]
    # Każdy checkpoint zapisywany do DB z timestampem
    # W razie błędu: rollback do ostatniego bezpiecznego checkpointa
```

---

## 7. Risk Matrix

| Atak  | Prawdopodobieństwo | Wpływ       | Risk Score | Priorytet |
|-------|-------------------|-------------|------------|-----------|
| AV-01 (fake USB device)          | ŚREDNIE | KRYTYCZNY  | 12 | P1 |
| AV-07 (skradziony adbkey)        | NISKIE  | KRYTYCZNY  | 9  | P1 |
| AV-11 (ADB włączone po provison) | WYSOKIE | KRYTYCZNY  | 16 | **P0** |
| AV-17 (brak HumanGate unlock)    | ŚREDNIE | KRYTYCZNY  | 12 | P1 |
| AV-19 (brick po unlock)          | ŚREDNIE | KRYTYCZNY  | 12 | P1 |
| AV-21 (tampered GrapheneOS img)  | NISKIE  | KRYTYCZNY  | 9  | P1 |
| AV-25 (supply chain backdoor)    | NISKIE  | KRYTYCZNY  | 9  | P1 |
| AV-27 (unauthorized root)        | ŚREDNIE | KRYTYCZNY  | 12 | P1 |
| AV-31 (executable agent in tmp/) | WYSOKIE | KRYTYCZNY  | 16 | **P0** |
| AV-32 (fake fido2-confirm)       | NISKIE  | KRYTYCZNY  | 9  | P1 |
| AV-33 (no crypto proof FIDO2)    | WYSOKIE | KRYTYCZNY  | 16 | **P0** |
| AV-37 (verify incomplete)        | WYSOKIE | KRYTYCZNY  | 16 | **P0** |
| AV-39 (bootloader not relocked)  | ŚREDNIE | KRYTYCZNY  | 12 | P1 |

---

## 8. Podsumowanie countermeasures (28 łącznie)

| CM   | Etap  | Opis                                                           | Status     |
|------|-------|----------------------------------------------------------------|------------|
| CM-01| S1    | Weryfikacja VID:PID urządzenia USB przed bind                  | DO IMPL.   |
| CM-02| S1    | Audit log z timestampem + VID/PID przy każdym usbipd event    | DO IMPL.   |
| CM-03| S1    | HumanGate przy auto-detekcji USB device                        | DO IMPL.   |
| CM-04| S2    | Wyłącz ADB debugging na końcu provisioning (S8)               | **KRYT.**  |
| CM-05| S2    | Zapisuj RSA fingerprint klucza ADB w audit log                | DO IMPL.   |
| CM-06| S2    | ADB key pinning (dedykowany certyfikat)                        | DO IMPL.   |
| CM-07| S3    | Weryfikacja przez fastboot attestation, nie tylko getprop      | DO IMPL.   |
| CM-08| S3    | Zapisz `build_fingerprint` w DB przy provisioning             | DO IMPL.   |
| CM-09| S3    | `--force` wymaga HumanGate z uzasadnieniem                    | DO IMPL.   |
| CM-10| S4    | HumanGate PRZED unlock bootloader (CRITICAL step)             | **KRYT.**  |
| CM-11| S4    | Rollback checkpoint: `fastboot flashing lock` po failed flash | **KRYT.**  |
| CM-12| S4    | Timestamp unlock/lock w `provisioning_audit_events`           | DO IMPL.   |
| CM-13| S5    | SHA-256 verify obrazu GrapheneOS przed flash                  | **KRYT.**  |
| CM-14| S5    | GPG verify obrazu GrapheneOS (klucz GrapheneOS oficjalny)     | **KRYT.**  |
| CM-15| S5    | Zapisz `sha256` zaflashowanego obrazu w DB                    | DO IMPL.   |
| CM-16| S5    | Retry z full-verification po przerwaniu flash                 | DO IMPL.   |
| CM-17| S6    | Wymuś dezaktywację root po provisioning                       | DO IMPL.   |
| CM-18| S6    | Zapisz `magisk_version` + `sha256(boot.img)` w audit          | DO IMPL.   |
| CM-19| S7    | SHA-256 plików agenta przed push                              | **KRYT.**  |
| CM-20| S7    | `chmod 700` na katalog agenta (nie 755)                       | DO IMPL.   |
| CM-21| S7    | Przenieś agenta do app-private storage                        | DO IMPL.   |
| CM-22| S7.5  | fido2-confirm endpoint: JWT + FIDO2 challenge-response        | **KRYT.**  |
| CM-23| S7.5  | Timeout HumanGate z auto-cleanup (disable ADB)                | DO IMPL.   |
| CM-24| S7.5  | Cryptographic attestation FIDO2 w audit logu                  | DO IMPL.   |
| CM-25| S8    | Sprawdź `ro.boot.verifiedbootstate == green` w verify         | **KRYT.**  |
| CM-26| S8    | Sprawdź `adb_enabled == 0` w verify                           | **KRYT.**  |
| CM-27| S8    | Sprawdź `ro.grapheneos.version != ""` w verify                | DO IMPL.   |
| CM-28| S8    | Dodaj GrapheneOS Auditor attestation check do verify          | DO IMPL.   |

---

*Threat model wygenerowany w oparciu o analizę `pixel_provision.py` (872 linii) i `device/pixel_manager.sh` (809 linii), v5.9.1.*
