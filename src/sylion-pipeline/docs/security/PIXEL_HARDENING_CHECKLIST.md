# SYLION Pixel 9 — Provisioning Hardening Checklist

**Wersja:** 1.0.0  
**Data:** 2025-01-19  
**Scope:** pixel_provision.py + pixel_manager.sh  
**Odniesienie:** THREAT_MODEL.md (CM-01 … CM-28)

Każdy checkbox jest obowiązkowy przed uznaniem provisioning za kompletne. Podpis operatora wymagany na końcu.

---

## FAZA 0 — Przygotowanie stacji roboczej (pre-provisioning)

- [ ] **H-01** Zweryfikuj wersję `adb`: `adb --version` → wymagane `>= 35.0.2`
- [ ] **H-02** Zweryfikuj hash `usbipd.exe`: `Get-FileHash usbipd.exe -Algorithm SHA256` → porównaj z oficjalnym releasem
- [ ] **H-03** Maszyna provisionera jest odizolowana od sieci (air-gap lub dedykowana VLAN bez internet access podczas provisioning)
- [ ] **H-04** Katalog `~/.android/` zawiera TYLKO `adbkey` stacji roboczej provisionera (usuń obce klucze: `ls -la ~/.android/`)
- [ ] **H-05** Weryfikacja integralności `pixel_provision.py`: `sha256sum pixel_provision.py` → porównaj z release manifest
- [ ] **H-06** Weryfikacja integralności `device/pixel_manager.sh`: `sha256sum device/pixel_manager.sh` → porównaj z release manifest
- [ ] **H-07** Weryfikacja integralności `device_harness.py`: `sha256sum device_harness.py` → porównaj z release manifest

---

## FAZA 1 — GrapheneOS Image (Supply Chain)

- [ ] **H-08** Pobierz obraz WYŁĄCZNIE z `https://releases.grapheneos.org/` (HTTPS, nie HTTP, nie mirror)
- [ ] **H-09** Weryfikuj SHA-256 obrazu:
  ```bash
  sha256sum tokay-ota_update-XXXXXXXXXX.zip
  # porównaj z wartością z: https://releases.grapheneos.org/tokay-ota_update-XXXXXXXXXX.zip.sha256sum
  ```
  SHA-256 [zanotuj]: `____________________________________________________`
- [ ] **H-10** Weryfikuj podpis GPG obrazu:
  ```bash
  gpg --verify tokay-ota_update-XXXXXXXXXX.zip.sig tokay-ota_update-XXXXXXXXXX.zip
  # Klucz GrapheneOS: 65EEFE022108E2B708CBFCF7F9E712E59AF5F22A
  ```
  Wynik GPG verify: `[ OK / FAIL ]`
- [ ] **H-11** Obraz przechowywany na zaszyfrowanym nośniku (LUKS/BitLocker) z hash-em kontrolnym pliku

---

## FAZA 2 — USB / Fizyczne podłączenie urządzenia (S1)

- [ ] **H-12** Używaj TYLKO zaufanego kabla USB-C z ochroną przed injekcją danych (np. PortaPow Data Blocker lub equivalent w trybie data-enabled)
- [ ] **H-13** Przed podłączeniem: wizualnie zweryfikuj urządzenie — seryjny na pudełku vs. `adb get-serialno`
- [ ] **H-14** Zweryfikuj VID:PID w systemie: `lsusb | grep 18d1` powinno pokazać Google Inc. (VID `18d1`)
- [ ] **H-15** Tylko jedno urządzenie USB podłączone do maszyny podczas provisioning
- [ ] **H-16** `usbipd list` nie pokazuje innych urządzeń oprócz Pixela i klucza FIDO2

---

## FAZA 3 — ADB Authentication (S2)

- [ ] **H-17** Na telefonie: przed kliknięciem "Allow USB debugging" — sprawdź fingerprint klucza wyświetlony na ekranie urządzenia vs. `cat ~/.android/adbkey.pub | sha256sum`
- [ ] **H-18** Zaznacz "Always allow from this computer" WYŁĄCZNIE dla dedykowanej stacji provisionera
- [ ] **H-19** Potwierdź pojedyncze urządzenie: `adb devices` zwraca dokładnie 1 device w stanie `device`
- [ ] **H-20** Nie uruchamiaj provisioning gdy `adb devices` zwraca `unauthorized` — wymagaj pełnej autoryzacji

---

## FAZA 4 — CRITICAL: OEM Unlock / Bootloader (S4)

> **UWAGA: Operacje w tej fazie są NIEODWRACALNE. Wymagany podpis supervisora.**

- [ ] **H-21** ⚠️ HUMAN GATE: Supervisor potwierdza słownie tożsamość urządzenia (model + serial) przed unlock
- [ ] **H-22** Urządzenie podłączone do zasilania (kabel ładowania) — minimum 50% baterii
- [ ] **H-23** Zapisz timestamp (UTC) momentu unlock: `date -u` → `____________________`
- [ ] **H-24** Po `fastboot flashing unlock` — urządzenie pokazuje ostrzeżenie na ekranie — operator potwierdza wzrokowo
- [ ] **H-25** NIE przerywaj zasilania po unlock — trzymaj kabel przez cały czas flash
- [ ] **H-26** Supervisor podpis (unlock authorization): `____________________`

---

## FAZA 5 — GrapheneOS Flash (S5)

- [ ] **H-27** Przed flash: powtórz weryfikację SHA-256 obrazu (H-09) — suma kontrolna musi być identyczna
- [ ] **H-28** Użyj wyłącznie `adb sideload` lub `fastboot` z weryfikowanego obrazu — NIE web installer na tym etapie
- [ ] **H-29** Monitoruj postęp sideload — nie odłączaj kabla USB podczas transferu
- [ ] **H-30** Po zakończeniu flash: zweryfikuj `ro.grapheneos.version` przez `adb shell getprop ro.grapheneos.version` → zanotuj wersję: `____________________`
- [ ] **H-31** Zapisz SHA-256 zaflashowanego obrazu w DB / logu provisioning job

---

## FAZA 6 — CRITICAL: Bootloader Lock (po flash) (S4b)

> **UWAGA: Pominięcie tego kroku = urządzenie z unlocked bootloader = ZAGROŻENIE BEZPIECZEŃSTWA**

- [ ] **H-32** ⚠️ HUMAN GATE: Przed wydaniem urządzenia — potwierdź `fastboot flashing lock` lub `ro.boot.verifiedbootstate=green`
- [ ] **H-33** Sprawdź stan: `adb shell getprop ro.boot.verifiedbootstate` → wymagane `green` (lub `yellow` dla user-signed)
- [ ] **H-34** Sprawdź: `adb shell getprop ro.boot.flash.locked` → wymagane `1`
- [ ] **H-35** Zapisz timestamp (UTC) momentu re-lock: `date -u` → `____________________`

---

## FAZA 7 — Deploy SYLION Agent (S7)

- [ ] **H-36** Przed push: `sha256sum device_harness.py` vs. release manifest — identyczne?
- [ ] **H-37** Przed push: `sha256sum device/pixel_manager.sh` vs. release manifest — identyczne?
- [ ] **H-38** Po push: zweryfikuj `adb shell sha256sum /data/local/tmp/sylion/device_harness.py` vs. lokalny SHA-256
- [ ] **H-39** Po push: `adb shell ls -la /data/local/tmp/sylion/` — uprawnienia max `700` (owner shell)
- [ ] **H-40** Brak sekretnych kluczy/tokenów w plikach konfiguracyjnych wgrywanych do `/data/local/tmp/sylion/config/`

---

## FAZA 8 — FIDO2 HumanGate (S7.5)

- [ ] **H-41** Używaj tylko fabrycznie nowego lub zweryfikowanego klucza FIDO2 (nie pożyczonego/używanego)
- [ ] **H-42** Zweryfikuj `aaguid` klucza FIDO2 po enrollmencie: odpowiada modelu YubiKey/klucza z inwentarza
- [ ] **H-43** Enrollment wykonany fizycznie przez OPERATORA z certyfikacją — nie zdalnie
- [ ] **H-44** `fido2-confirm` wysłany przez zalogowanego operatora (sesja uwierzytelniona JWT), nie przez anonimowe API
- [ ] **H-45** Zapisz UUID enrollmentu i timestamp potwierdzenia w audit logu

---

## FAZA 9 — Final Verification (S8) + Post-Provisioning

- [ ] **H-46** ✅ **KLUCZOWE**: `adb shell settings get global adb_enabled` → wymagane `0` (ADB wyłączone)
  - Jeśli `1`: natychmiast wykonaj `adb shell settings put global adb_enabled 0` + `adb reboot`
- [ ] **H-47** ✅ **KLUCZOWE**: `adb shell getprop ro.boot.verifiedbootstate` → `green`
- [ ] **H-48** ✅ **KLUCZOWE**: `adb shell getprop ro.grapheneos.version` → nie puste
- [ ] **H-49** Sprawdź brak nieautoryzowanych pakietów: `adb shell pm list packages -3` → tylko SYLION agent + GrapheneOS apps
- [ ] **H-50** Sprawdź `adb shell getprop ro.build.version.security_patch` → max 60 dni wstecz od dziś
- [ ] **H-51** Sprawdź brak aktywnego procesu `su` / Magisk: `adb shell pgrep -l su; adb shell pm list packages com.topjohnwu.magisk`
- [ ] **H-52** Wykonaj factory reset jeśli provisioning przerwany przed S5 (flash): `fastboot -w` + restart od zera
- [ ] **H-53** Odłącz urządzenie od maszyny provisionera po zakończeniu verificiation
- [ ] **H-54** Skasuj `adb shell` history: `adb shell rm -f /data/local/tmp/.bash_history`

---

## FAZA 10 — Audit & Documentation

- [ ] **H-55** Provisioning job zapisany w DB z: serial, model, grapheneos_version, sha256_image, timestamp_start, timestamp_end, operator_id
- [ ] **H-56** Log `pixel_manager_YYYYMMDD.log` zarchiwizowany i podpisany: `sha256sum pixel_manager_YYYYMMDD.log >> logs.manifest`
- [ ] **H-57** Wszystkie HumanGate eventy zapisane w `provisioning_audit_events` z operator_id + timestamp
- [ ] **H-58** Incydenty (nieudane kroki, warningi) zgłoszone do SYLION Security Team
- [ ] **H-59** Urządzenie wydane użytkownikowi końcowemu z dokumentacją provisioning (model, GrapheneOS version, FIDO2 key serial)

---

## Podpis i Zatwierdzenie

| Rola              | Imię i Nazwisko       | Podpis | Data (UTC)    |
|-------------------|-----------------------|--------|---------------|
| Operator          |                       |        |               |
| Supervisor        |                       |        |               |
| Security Review   |                       |        |               |

---

## Szybka karta kontrolna (podręczna)

```
PRZED provisioning:
  □ Zweryfikuj SHA-256 + GPG obrazu GrapheneOS
  □ Zweryfikuj integralność adb/fastboot/pixel_provision.py
  □ Tylko 1 USB device podłączony

CRITICAL STEPS (wymagają supervisora):
  □ Unlock bootloader → zapisz timestamp
  □ Flash GrapheneOS → zapisz SHA-256
  □ Lock bootloader → zapisz timestamp
  □ FIDO2 enrollment → zapisz UUID

PO provisioning (OBLIGATORYJNE):
  □ adb_enabled = 0
  □ verifiedbootstate = green
  □ grapheneos_version != ""
  □ Odłącz urządzenie od ADB
```

---

*Checklist wygenerowany na podstawie THREAT_MODEL.md v1.0.0, wymagania SYLION Secure v5.9.1*
