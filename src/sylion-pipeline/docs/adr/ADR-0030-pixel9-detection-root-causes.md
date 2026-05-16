# ADR-0030: Pixel 9 detection root causes fix

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/pixel_deep  

---

## Kontekst

ADR-0015 (pixel-9-default-device) wprowadził Pixel 9 jako domyślne urządzenie w `device/` module. Audyt mega_audit/pixel_deep i mega_audit/pixel_9_detection_root_causes ujawnił trzy niezależne przyczyny nieprawidłowego wykrywania Pixel 9 w pipeline analizy urządzeń:

**Root Cause 1 — String matching case sensitivity:**  
`device/detector.py` używał `if "pixel 9" in device_str.lower()` ale dane z ADB (`adb shell getprop ro.product.model`) zwracają `"Pixel 9 Pro"`, `"Pixel 9a"`, `"Pixel 9 Pro XL"` — regex `"pixel 9"` nie pokrywał wariantów Pro/XL/a, generując `False` dla 3 z 4 wariantów.

**Root Cause 2 — udev rules gap:**  
`mega_audit/udev_rules_gap` wykazał brak reguł udev dla Pixel 9 (USB Vendor ID: `0x18d0`, Product ID: `0x4ee7`). Urządzenie podłączone przez USB nie było rozpoznawane przez `adb devices` bez ręcznej reguły `/etc/udev/rules.d/51-android.rules`.

**Root Cause 3 — ADB path detection:**  
`mega_audit/adb_not_in_path` ujawnił, że `device/adb_runner.py` używał `subprocess.run(["adb", ...])` zakładając `adb` w `$PATH`. Na instalacjach bez Android SDK (np. VPS) — `FileNotFoundError`. Brak graceful fallback do `platform-tools/adb`.

Rozważane podejścia:
- **P1** — Naprawienie regex dla wszystkich wariantów Pixel 9 (tylko RC1)
- **P2** — P1 + dodanie reguł udev + graceful ADB path resolution (wybrana)
- **P3** — Zastąpienie string-matching bazą danych urządzeń (device fingerprint DB)
- **P4** — Rezygnacja z auto-detection; konfiguracja ręczna w `config.yaml`

## Decyzja

Wdrożenie **P2** naprawiające wszystkie trzy root causes:

1. **Regex fix**: zamiana `"pixel 9"` na `re.search(r"pixel\s+9(\s+(pro(\s+xl)?|a))?", s, re.IGNORECASE)` pokrywający: Pixel 9, Pixel 9 Pro, Pixel 9 Pro XL, Pixel 9a.
2. **udev rules**: dodanie do `device/udev/51-android.rules` wpisu dla Pixel 9 (`ATTR{idVendor}=="18d0", ATTR{idProduct}=="4ee7"`). Skrypt `install.sh` kopiuje reguły i wywołuje `udevadm control --reload-rules`.
3. **ADB path resolution**: `adb_runner.py` szuka `adb` w kolejności: `$ADB_PATH` env → `$PATH` → `./platform-tools/adb` → `~/Android/Sdk/platform-tools/adb`. Przy braku wszystkich: `SYL-3003` (adb not found) zamiast traceback.

## Konsekwencje

### Pozytywne
- Wszystkie 4 warianty Pixel 9 (Standard, Pro, Pro XL, 9a) wykrywane poprawnie
- Instalacja na VPS/CI bez Android SDK nie generuje `FileNotFoundError` — graceful degradation
- udev rules instalowane automatycznie przez `install.sh` — zero ręcznej konfiguracji

### Negatywne
- Regex musi być aktualizowany przy nowych wariantach Pixel (np. Pixel 9 Pro Fold) — tech debt
- udev rules wymagają uprawnień root podczas `install.sh` — może blokować instalację bez sudo

### Neutralne
- `device/udev/` staje się katalogiem zarządzanym przez `install.sh` — nowy artifact w repo

## Alternatywy odrzucone

- **Device fingerprint DB (P3)**: baza danych ~5000 urządzeń — nadmierne dla projektu skupionego na Pixel 9
- **Konfiguracja ręczna (P4)**: pogarsza UX (dodatkowy krok instalacji) — odrzucone

## Referencje

- `mega_audit/pixel_deep/` — głęboki audyt modułu device/
- `mega_audit/pixel_9_detection_root_causes/` — analiza 3 root causes
- `mega_audit/udev_rules_gap/` — brakujące reguły udev
- `mega_audit/adb_not_in_path/` — brak ADB w PATH
- ADR-0015 (pixel-9-default-device) — pierwotna decyzja o Pixel 9
- `device/detector.py` — zaktualizowany regex Pixel 9
- `device/adb_runner.py` — graceful ADB path resolution
- `device/udev/51-android.rules` — reguły udev dla Pixel 9
