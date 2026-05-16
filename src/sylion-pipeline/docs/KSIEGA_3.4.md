# KSIĘGA SYLION 3.4 FIXED
## Specyfikacja Produktu — SYLION Secure
### Pixel 9 + GrapheneOS + Mudi Router

---

**Dokument:** Księga SYLION 3.4 FIXED  
**Wersja:** 3.4 (FIXED — immutable, normative)  
**Status:** NORMATIVE SOURCE OF TRUTH — CHRONIONY PRZEZ BookGuardian  
**Data zamrożenia:** 2026-04-19  
**Właściciel produktu:** [PRODUCT OWNER — do uzupełnienia]  
**Klasyfikacja:** POUFNE / INTERNAL — SYLION  

> **INVARIANT:** Ten dokument jest jedynym normatywnym źródłem wymagań dla
> pipeline'u SYLION. Plik `requirements.json` jest artefaktem POCHODNYM
> generowanym przez `ksiega_analyst` (Stage 1). W razie konfliktu: **Księga wygrywa**.
> Żaden agent nie może modyfikować tego pliku. BookGuardian monitoruje SHA-256.

---

## Spis treści

1. [Wprowadzenie i cel produktu](#1-wprowadzenie-i-cel-produktu)
2. [Zakres i adresaci](#2-zakres-i-adresaci)
3. [Architektura sprzętowa — Pixel 9 + GrapheneOS](#3-architektura-sprzetowa--pixel-9--grapheneos)
4. [Router Mudi — specyfikacja i integracja](#4-router-mudi--specyfikacja-i-integracja)
5. [Model zagrożeń (Threat Model)](#5-model-zagrozen-threat-model)
6. [Wymagania bezpieczeństwa](#6-wymagania-bezpieczenstwa)
7. [Wymagania prywatności i zgodności (RODO/GDPR)](#7-wymagania-prywatnosci-i-zgodnosci-rodomdgpr)
8. [Architektura sieciowa](#8-architektura-sieciowa)
9. [Zarządzanie tożsamością i dostępem](#9-zarzadzanie-tozsamoscia-i-dostepem)
10. [Wymagania dotyczące aplikacji i ekosystemu](#10-wymagania-dotyczace-aplikacji-i-ekosystemu)
11. [Zarządzanie danymi i retencja](#11-zarzadzanie-danymi-i-retencja)
12. [Procedury operacyjne](#12-procedury-operacyjne)
13. [Testy i walidacja](#13-testy-i-walidacja)
14. [Zgodność regulacyjna](#14-zgodnosc-regulacyjna)
15. [Glosariusz](#15-glosariusz)
16. [Historia zmian](#16-historia-zmian)

---

## 1. Wprowadzenie i cel produktu

### 1.1 Misja SYLION Secure

SYLION Secure to zintegrowane rozwiązanie bezpieczeństwa przeznaczone dla osób
i organizacji potrzebujących najwyższego poziomu ochrony komunikacji mobilnej
w środowiskach o podwyższonym ryzyku.

Produkt łączy trzy komponenty:

| Komponent | Rola | Wariant |
|-----------|------|---------|
| **Google Pixel 9** | Bezpieczny terminal mobilny | Pro / Pro XL / Pro Fold |
| **GrapheneOS** | Hardened Android — system operacyjny | Stable channel |
| **GL.iNet Mudi (GL-E750)** | Prywatny router 4G/LTE z VPN | v2 (MediaTek MT7621A) |

### 1.2 Cel dokumentu

Niniejsza Księga definiuje:

1. **Wymagania sprzętowe i konfiguracyjne** dla każdego z trzech komponentów
2. **Model zagrożeń** obejmujący scenariusze ataków sieciowych, fizycznych i wywiadowczych
3. **Polityki bezpieczeństwa** obowiązujące w całym stosie
4. **Procedury wdrożeniowe i operacyjne** zapewniające powtarzalność konfiguracji
5. **Wymagania zgodności** z przepisami polskimi (RODO, KSC) i unijnymi (NIS2, DORA)

### 1.3 Unikalność rozwiązania

SYLION Secure wyróżnia się wśród rozwiązań bezpieczeństwa mobilnego:

- **Pełna weryfikowalność łańcucha rozruchu** (Verified Boot + GrapheneOS attestation)
- **Izolacja sieciowa na poziomie sprzętowym** (dedykowany router fizyczny, nie VPN app)
- **Zero Google Play Services** w profilach produkcyjnych (GrapheneOS Sandboxed Google Play opcjonalnie)
- **Open-source wszystkich krytycznych komponentów** (GrapheneOS, OpenWRT/GL.iNet, WireGuard)
- **Audytowalny pipeline** — SYLION pipeline weryfikuje spójność specyfikacji przed każdym deployem

---

## 2. Zakres i adresaci

### 2.1 Adresaci

| Rola | Zastosowanie dokumentu |
|------|------------------------|
| Inżynier bezpieczeństwa | Wdrożenie konfiguracji, hardening |
| Administrator systemu | Utrzymanie, aktualizacje, procedury operacyjne |
| Audytor bezpieczeństwa | Weryfikacja zgodności z wymaganiami |
| Właściciel produktu | Zmiany zakresu, autoryzacja odchyleń |
| Pipeline SYLION (agent) | Automatyczna weryfikacja wymagań (Stage 1–7) |

### 2.2 Poza zakresem

Następujące zagadnienia są poza zakresem Księgi 3.4:

- Konfiguracja centralnego zarządzania MDM (opisana w osobnym dokumencie)
- Integracja z systemami SIEM (ADR-0031, planowane v5.10)
- Polityki dla urządzeń iOS/macOS
- Procedury certyfikacji Common Criteria

### 2.3 Zależności

Niniejsza Księga zakłada dostępność:

- GrapheneOS w wersji ≥ 2025-04-01 (kanał stable)
- GL.iNet firmware ≥ 4.5.x (OpenWRT 23.x base)
- WireGuard kernel module (wbudowany w GrapheneOS ≥ Android 14)
- Dostęp do endpointu VPN (WireGuard lub OpenVPN IKEv2)

---

## 3. Architektura sprzętowa — Pixel 9 + GrapheneOS

### 3.1 Wymagania dotyczące sprzętu

#### 3.1.1 Wybór modelu Pixel 9

Obsługiwane są wyłącznie następujące warianty:

| Model | Chipset | RAM | Storage | Status |
|-------|---------|-----|---------|--------|
| Pixel 9 | Tensor G4 | 12 GB | 128/256 GB | ✅ SUPPORTED |
| Pixel 9 Pro | Tensor G4 | 16 GB | 128/256/512 GB | ✅ SUPPORTED |
| Pixel 9 Pro XL | Tensor G4 | 16 GB | 128/256/512 GB | ✅ SUPPORTED |
| Pixel 9 Pro Fold | Tensor G4 | 16 GB | 256/512 GB | ✅ SUPPORTED |

**Wymaganie REQ-HW-01:** Urządzenie musi być zakupione u autoryzowanego sprzedawcy
z nienaruszonym opakowaniem. Numer IMEI musi być zweryfikowany przed instalacją GrapheneOS.

**Wymaganie REQ-HW-02:** Urządzenie nie może być wcześniej aktywowane ani posiadać
aktywnego konta Google. Jeśli było aktywowane, musi przejść pełny factory reset
z weryfikacją Verified Boot przed instalacją.

#### 3.1.2 Weryfikacja sprzętu przed instalacją

```
Procedura PHY-VERIFY-01:
  1. Sprawdź numer seryjny na opakowaniu vs. w urządzeniu (Ustawienia → O telefonie)
  2. Uruchom w trybie fastboot: fastboot oem device-info
  3. Weryfikuj: "Device unlocked: false" (fabrycznie zablokowane)
  4. Sprawdź Titan M2 chip via: fastboot getvar all | grep security
  5. Zrób zdjęcie stanu przed instalacją (audit trail)
```

### 3.2 Instalacja GrapheneOS

#### 3.2.1 Wymagania instalacyjne

**Wymaganie REQ-GROS-01:** GrapheneOS musi być instalowany wyłącznie przez
oficjalną stronę `https://grapheneos.org/install/` lub CLI installer.

**Wymaganie REQ-GROS-02:** Weryfikacja integralności obrazu instalacyjnego:

```bash
# Weryfikacja SHA-256 obrazu
sha256sum factory-<device>-<build>.zip

# Weryfikacja podpisu GPG
gpg --verify factory-<device>-<build>.zip.sig factory-<device>-<build>.zip
```

**Wymaganie REQ-GROS-03:** Po instalacji GrapheneOS musi być ponownie zablokowany
Verified Boot (`fastboot flashing lock`). Próba uruchomienia z odblokowanym bootloaderem
musi generować alert w SYLION pipeline.

#### 3.2.2 Konfiguracja Verified Boot

GrapheneOS Verified Boot zapewnia:
- Kryptograficzna weryfikacja każdej partycji przy starcie
- Rollback Protection (wersja firmware nie może być obniżona)
- Attestation (zdalne potwierdzenie stanu urządzenia)

**Wymaganie REQ-VB-01:** Status Verified Boot musi być zielony (`dm-verity: enabled`).
Jakikolwiek inny stan wymaga natychmiastowej reinicjalizacji urządzenia.

### 3.3 Konfiguracja GrapheneOS

#### 3.3.1 Profile użytkownika (Spaces)

GrapheneOS obsługuje wiele izolowanych profili użytkownika. SYLION Secure
definiuje następującą strukturę:

| Profil | Przeznaczenie | Dostęp do sieci | Aplikacje |
|--------|---------------|-----------------|-----------|
| **Owner** | Administracja, aktualizacje | Pełny (przez Mudi VPN) | Minimalne — tylko systemowe |
| **Work** | Komunikacja biznesowa | Przez VPN (enforced) | Signal, ProtonMail, Nextcloud |
| **Personal** | Użytek prywatny | Przez VPN | Standardowe |
| **Isolated** | Uruchamianie niezaufanych aplikacji | Brak / ograniczony | Sandbox |

**Wymaganie REQ-PROF-01:** Profil Owner nie może mieć zainstalowanych żadnych
zewnętrznych aplikacji. Wszelkie aplikacje instalowane są w dedykowanych profilach.

**Wymaganie REQ-PROF-02:** Przełączanie między profilami musi wymagać uwierzytelnienia
(PIN/hasło/biometria na poziomie każdego profilu).

#### 3.3.2 Konfiguracja hardening GrapheneOS

```
Wymagania hardening (REQ-HARD-01 do REQ-HARD-12):

REQ-HARD-01: Auto-reboot po 18h nieaktywności (Ustawienia → Bezpieczeństwo → Auto-reboot)
REQ-HARD-02: PIN minimum 8 cyfr LUB hasło minimum 12 znaków (tryb strong PIN)
REQ-HARD-03: Szyfrowanie pamięci: domyślnie włączone w GrapheneOS (Android FBE)
REQ-HARD-04: Disallow installation from unknown sources = true (dla wszystkich profili)
REQ-HARD-05: MAC address randomization = per-network (nie per-time)
REQ-HARD-06: Sensors permission = domyślnie DENY dla wszystkich aplikacji
REQ-HARD-07: Camera/Microphone access indicators = enabled
REQ-HARD-08: Network permission firewall: block internet by default dla nowych aplikacji
REQ-HARD-09: USB data port: disabled gdy zablokowany (USB Host Mode = OFF gdy lock screen)
REQ-HARD-10: Secure Lock Screen: wymagane hasło nie PIN dla Owner i Work
REQ-HARD-11: OTA updates: auto-download, manual install (NIE auto-install w tle)
REQ-HARD-12: Exploit protection compatibility mode = disabled (pełna ochrona)
```

#### 3.3.3 Zarządzanie aplikacjami

**Wymaganie REQ-APP-01:** Aplikacje mogą być instalowane wyłącznie z:
- GrapheneOS App Store (Accrescent lub F-Droid — oficjalny repozytorium)
- Ręczna instalacja APK z weryfikowanego źródła (wymagana autoryzacja właściciela produktu)

**Wymaganie REQ-APP-02:** Sandboxed Google Play może być zainstalowane wyłącznie
w profilu Personal lub Isolated. NIGDY w Owner lub Work.

**Wymaganie REQ-APP-03:** Każda aplikacja w profilu Work musi mieć jawnie zdefiniowane
uprawnienia w dokumentacji konfiguracji (osobny dokument AppManifest).

---

## 4. Router Mudi — specyfikacja i integracja

### 4.1 Sprzęt GL.iNet Mudi (GL-E750)

#### 4.1.1 Specyfikacja techniczna

| Parametr | Wartość |
|----------|---------|
| Model | GL.iNet GL-E750 Mudi v2 |
| Chipset | MediaTek MT7621A (MIPS 880 MHz dual-core) |
| RAM | 128 MB DDR3 |
| Flash | 32 MB NOR |
| WiFi | 802.11 a/b/g/n/ac (2.4 GHz + 5 GHz) |
| LTE modem | Quectel EP06-E (Cat.6, 300/50 Mbps) |
| SIM | 1x nano-SIM |
| USB | 1x USB 2.0 (dla dodatkowego modemu) |
| Bateria | 7000 mAh (≈8h pracy jako hotspot) |
| OS base | OpenWRT 23.05 / GL.iNet firmware 4.x |

#### 4.1.2 Wymagania dotyczące zakupu

**Wymaganie REQ-MUDI-01:** Urządzenie musi być zakupione bezpośrednio od GL.iNet
lub autoryzowanego dystrybutora. Zakaz zakupu z rynku wtórnego bez pełnej
weryfikacji oprogramowania.

**Wymaganie REQ-MUDI-02:** Po otrzymaniu — natychmiastowy factory reset przed
podłączeniem do sieci produkcyjnej.

**Wymaganie REQ-MUDI-03:** Weryfikacja sumy kontrolnej firmware:

```bash
# Pobierz firmware z oficjalnej strony GL.iNet
wget https://dl.gl-inet.com/router/e750/release/4.x.x/gl-e750-4.x.x-release1.tar.gz

# Weryfikuj SHA-256 (porównaj z wartością na stronie producenta)
sha256sum gl-e750-4.x.x-release1.tar.gz
```

### 4.2 Konfiguracja sieciowa Mudi

#### 4.2.1 Podstawowa konfiguracja sieci

```
Wymagania sieciowe (REQ-NET-01 do REQ-NET-08):

REQ-NET-01: SSID sieci WiFi musi być ukryte (Broadcast SSID = OFF)
REQ-NET-02: Protokół WiFi: WPA3-SAE (minimum WPA2-AES, WPA/TKIP = zakazane)
REQ-NET-03: Hasło WiFi: minimum 20 losowych znaków
REQ-NET-04: LAN subnet: nie używać 192.168.1.x (domyślne / łatwe do zgadnięcia)
             Zalecane: 10.77.x.x/24 lub inna nieoczywista przestrzeń
REQ-NET-05: DHCP leasing: krótki (4h) z możliwością rezerwacji MAC
REQ-NET-06: Firewall: DROP wszystkie pakiety przychodzące z WAN (domyślnie)
REQ-NET-07: DNS-over-HTTPS lub DNS-over-TLS (np. Cloudflare 1.1.1.1 lub własny resolver)
REQ-NET-08: IPv6: wyłączone (chyba że VPN obsługuje IPv6 — sprawdź leaks)
```

#### 4.2.2 Konfiguracja VPN na Mudi

GL.iNet Mudi obsługuje WireGuard i OpenVPN bezpośrednio na routerze.

**Wymaganie REQ-VPN-01:** Cały ruch z podłączonych urządzeń musi przechodzić
przez VPN (VPN policy-based routing lub globalne przekierowanie).

**Wymaganie REQ-VPN-02:** Kill switch VPN musi być włączony. Gdy VPN niedostępny,
ruch musi być blokowany (nie przechodzić przez ISP bezpośrednio).

```
Konfiguracja WireGuard na Mudi (przykład):
[Interface]
PrivateKey = <KLUCZ_PRYWATNY_ROUTERA>
Address = 10.200.0.2/32
DNS = 10.200.0.1

[Peer]
PublicKey = <KLUCZ_PUBLICZNY_SERWERA>
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = vpn.sylion.example:51820
PersistentKeepalive = 25
```

**Wymaganie REQ-VPN-03:** Klucze WireGuard muszą być generowane lokalnie na Mudi.
Nigdy nie należy używać kluczy wygenerowanych przez dostawcę VPN.

**Wymaganie REQ-VPN-04:** Rotacja kluczy VPN: minimum co 90 dni lub po każdym
podejrzanym zdarzeniu bezpieczeństwa.

#### 4.2.3 Separacja ruchu (VLAN / network policies)

**Wymaganie REQ-VLAN-01:** Urządzenia podłączone do Mudi muszą być podzielone
na co najmniej dwa segmenty:

| Segment | Przeznaczenie | VPN | Dostęp do LAN |
|---------|---------------|-----|---------------|
| secure | Urządzenia SYLION (Pixel 9) | Obligatoryjny | Tak |
| guest | Urządzenia niezaufane | Opcjonalny | Nie |

### 4.3 Aktualizacje firmware Mudi

**Wymaganie REQ-FW-01:** Firmware Mudi musi być aktualizowany w ciągu 30 dni
od wydania nowej wersji przez GL.iNet.

**Wymaganie REQ-FW-02:** Przed aktualizacją firmware — wykonaj backup konfiguracji
(GL.iNet Admin Panel → System → Backup).

**Wymaganie REQ-FW-03:** Po aktualizacji firmware — weryfikacja wszystkich ustawień
VPN i firewall (aktualizacja może zresetować niektóre opcje).

---

## 5. Model zagrożeń (Threat Model)

### 5.1 Aktorzy zagrożeń

| ID | Aktor | Motywacja | Zdolności |
|----|-------|-----------|-----------|
| TA-01 | Państwowy napastnik (APT) | Inwigilacja, kradzież IP | Zasoby nieograniczone, exploity 0-day |
| TA-02 | Cyberprzestępca | Zysk finansowy | Komercyjne narzędzia, phishing |
| TA-03 | Insider threat | Sabotaż, kradzież danych | Dostęp wewnętrzny |
| TA-04 | Fizyczny napastnik | Kradzież urządzenia, wymuszenie | Dostęp fizyczny do urządzenia |
| TA-05 | MITM (sieciowy) | Przechwycenie komunikacji | Kontrola sieci lokalnej lub ISP |

### 5.2 Scenariusze zagrożeń

#### Scenariusz T-01: Przechwycenie komunikacji przez MITM

**Opis:** Napastnik kontroluje sieć (np. fałszywy hotspot WiFi) i próbuje
przechwycić lub zmodyfikować transmisję danych.

**Kontrole bezpieczeństwa:**
- Mudi VPN kill switch zapobiega transmisji poza tunelem
- Certificate pinning w aplikacjach
- DNS-over-HTTPS zapobiega DNS hijacking

**Poziom ryzyka po kontrolach:** NISKI

#### Scenariusz T-02: Fizyczna kradzież urządzenia

**Opis:** Urządzenie Pixel 9 zostaje skradzione lub zagubione.

**Kontrole bezpieczeństwa:**
- Full disk encryption (Android FBE — File-Based Encryption)
- Auto-reboot po 18h (wymaga ponownego podania hasła przed odszyfrowaniem danych)
- Brak biometrii po ponownym uruchomieniu (wymaga PIN/hasło)
- Profile Guest nie zawierają danych produkcyjnych

**Poziom ryzyka po kontrolach:** NISKI

#### Scenariusz T-03: Exploitacja systemu operacyjnego

**Opis:** Napastnik wykorzystuje lukę w Android/kernel do przejęcia urządzenia.

**Kontrole bezpieczeństwa:**
- GrapheneOS hardened allocator (hardened malloc)
- Kernele z dodatkowym hardeningiem (KASLR, SELinux enforcing)
- Regularne aktualizacje (GrapheneOS wydaje patche szybciej niż stock Android)
- Izolacja profili — kompromitacja jednego nie daje dostępu do innych

**Poziom ryzyka po kontrolach:** ŚREDNI (0-day APT jest realne)

#### Scenariusz T-04: Kompromitacja firmware routera

**Opis:** Napastnik modyfikuje firmware Mudi lub wstrzykuje złośliwy kod.

**Kontrole bezpieczeństwa:**
- Weryfikacja SHA-256 przed aktualizacją
- Dostęp admin panel tylko z sieci lokalnej (nie z WAN)
- Zmiana domyślnych danych dostępowych
- Regularne audyty konfiguracji

**Poziom ryzyka po kontrolach:** NISKI

#### Scenariusz T-05: Supply chain attack

**Opis:** Urządzenie lub oprogramowanie jest skompromitowane przed dotarciem do użytkownika.

**Kontrole bezpieczeństwa:**
- Zakup od autoryzowanych dostawców
- Weryfikacja Verified Boot przed instalacją
- GrapheneOS instalowany ze świeżo zweryfikowanego źródła
- Audyt pierwszego uruchomienia (sprawdzenie stanu fabrycznego)

**Poziom ryzyka po kontrolach:** NISKI–ŚREDNI

### 5.3 Macierz ryzyk

| ID | Zagrożenie | Prawdopodobieństwo | Wpływ | Ryzyko wrodzone | Ryzyko resztkowe |
|----|----------|-------------------|-------|----------------|-----------------|
| T-01 | MITM sieciowy | Wysoki | Wysoki | KRYTYCZNY | NISKI |
| T-02 | Kradzież fizyczna | Średni | Wysoki | WYSOKI | NISKI |
| T-03 | Exploitacja OS | Niski | Krytyczny | WYSOKI | ŚREDNI |
| T-04 | Kompromitacja routera | Niski | Wysoki | ŚREDNI | NISKI |
| T-05 | Supply chain | Niski | Krytyczny | WYSOKI | NISKI |

---

## 6. Wymagania bezpieczeństwa

### 6.1 Wymagania kryptograficzne

```
REQ-CRYPTO-01: Wszystkie połączenia sieciowe muszą używać TLS 1.3 (minimum TLS 1.2)
REQ-CRYPTO-02: Zakazane algorytmy: DES, 3DES, RC4, MD5, SHA-1 (dla nowych certyfikatów)
REQ-CRYPTO-03: Minimalne długości kluczy: RSA ≥ 4096 bit, EC ≥ 256 bit (P-256/P-384)
REQ-CRYPTO-04: VPN: WireGuard (ChaCha20Poly1305) preferowany; OpenVPN z AES-256-GCM
REQ-CRYPTO-05: Klucze prywatne: generowane na docelowym urządzeniu, nigdy nie przenoszone
REQ-CRYPTO-06: Certyfikaty: self-signed zakazane dla systemów produkcyjnych
               Wyjątek: CA wewnętrzna z odpowiednim łańcuchem zaufania
```

### 6.2 Wymagania dotyczące uwierzytelniania

```
REQ-AUTH-01: Hasła urządzeń: minimum 12 znaków, losowe, nie dictionary words
REQ-AUTH-02: Biometria: dozwolona jako drugi czynnik, nie jako jedyny
             Po restarcie: wymagany PIN/hasło (nie biometria)
REQ-AUTH-03: MFA: wymagane dla wszystkich dostępów zdalnych / kont produkcyjnych
REQ-AUTH-04: Sesje: timeout 15 minut dla aplikacji wrażliwych
REQ-AUTH-05: Brute force: urządzenie musi enforceować throttling po 10 błędnych próbach
             (GrapheneOS: PIN/hasło throttling wbudowany)
REQ-AUTH-06: Recovery codes: przechowywane offline, zaszyfrowane, w bezpiecznej lokalizacji
```

### 6.3 Wymagania audytu i logowania

```
REQ-LOG-01: Zdarzenia logowane: loginy (sukces/błąd), zmiany konfiguracji, połączenia VPN
REQ-LOG-02: Retencja logów: minimum 90 dni
REQ-LOG-03: Logi muszą być niemodyfikowalne (append-only, WORM storage jeśli możliwe)
REQ-LOG-04: Zdarzenia krytyczne (drift Księgi, błąd VPN, nieudana weryfikacja sprzętu):
             natychmiastowa notyfikacja operatora
REQ-LOG-05: Logi na urządzeniu mobilnym: eksportowane do bezpiecznego, zewnętrznego systemu
             co minimum 24h
```

### 6.4 Wymagania dotyczące aktualizacji

```
REQ-UPD-01: GrapheneOS: aktualizacje instalowane w ciągu 14 dni od wydania
             (patche krytyczne: 72h)
REQ-UPD-02: GL.iNet Mudi: aktualizacje instalowane w ciągu 30 dni
             (patche krytyczne: 7 dni)
REQ-UPD-03: Aplikacje: aktualizowane co minimum 30 dni; krytyczne patche: 7 dni
REQ-UPD-04: Przed każdą aktualizacją: backup konfiguracji + test w środowisku staging
             (jeśli dostępne)
REQ-UPD-05: Proces aktualizacji musi być audytowany (kto, co, kiedy, skąd)
```

---

## 7. Wymagania prywatności i zgodności (RODO/GDPR)

### 7.1 Zasady przetwarzania danych

**Wymaganie REQ-RODO-01 (Minimalizacja danych):**  
SYLION Secure nie zbiera danych użytkownika ponad niezbędne minimum dla
świadczenia funkcjonalności bezpieczeństwa.

**Wymaganie REQ-RODO-02 (Ograniczenie celu):**  
Dane zbierane (logi bezpieczeństwa, dane konfiguracyjne) są używane wyłącznie
do celów bezpieczeństwa i audytu. Nie ma profilowania użytkownika.

**Wymaganie REQ-RODO-03 (Prawo do bycia zapomnianym):**  
Użytkownik może zażądać usunięcia wszystkich danych konfiguracyjnych.
Factory reset urządzenia musi trwale usunąć dane (GrapheneOS secure erase).

**Wymaganie REQ-RODO-04 (Przenoszenie danych):**  
Eksport konfiguracji urządzenia musi być możliwy w formacie maszynowo-czytelnym
(JSON/YAML). Format dokumentacji: patrz AppManifest v1.2.

### 7.2 Przetwarzanie danych osobowych

SYLION Secure przetwarza następujące kategorie danych:

| Kategoria | Podstawa prawna | Retencja | Lokalizacja |
|-----------|-----------------|----------|-------------|
| Logi bezpieczeństwa | Uzasadniony interes (bezpieczeństwo) | 90 dni | Urządzenie lokalne + serwer |
| Dane konfiguracyjne | Umowa | Przez czas używania produktu | Urządzenie lokalne |
| Dane diagnostyczne | Zgoda (opt-in) | 30 dni | Serwer operatora |
| Klucze kryptograficzne | Umowa | Przez czas życia klucza | Tylko urządzenie |

### 7.3 Transfer danych poza EOG

**Wymaganie REQ-TRANSFER-01:**  
Dane użytkownika nie mogą być transferowane poza EOG bez:
- Odpowiedniej podstawy prawnej (SCC, Binding Corporate Rules)
- Jawnej zgody użytkownika dla danych osobowych
- Dokumentacji w Rejestrze Czynności Przetwarzania

**Wymaganie REQ-TRANSFER-02:**  
Serwery VPN muszą być zlokalizowane w EOG (domyślnie) lub w kraju
o odpowiednim poziomie ochrony danych. Lista zaakceptowanych krajów:
patrz SYLION Policy GDPR-03.

### 7.4 DPIA (Ocena skutków dla ochrony danych)

Pełna DPIA dla SYLION Secure jest wymagana jeśli:
- Produkt przetwarza dane wrażliwe (art. 9 RODO)
- Produkt jest wdrażany dla więcej niż 1000 użytkowników
- Produkt jest używany przez organy publiczne

Szablon DPIA: patrz SYLION Legal Template DPIA-01.

---

## 8. Architektura sieciowa

### 8.1 Topologia sieci SYLION Secure

```
Internet (ISP)
      |
      | LTE/4G (SIM karta)
      |
[GL.iNet Mudi GL-E750]
  ├── VPN tunnel (WireGuard) ──→ [SYLION VPN Server]
  ├── WiFi: SSID hidden, WPA3
  │     └── [Pixel 9 / GrapheneOS]
  │           └── Wszystkie aplikacje → przez VPN
  └── [Guest VLAN — opcjonalny, izolowany]
```

### 8.2 Ścieżki ruchu sieciowego

**Ścieżka A (normalna operacja):**
```
Pixel 9 → WiFi → Mudi → WireGuard tunnel → VPN Server → Internet
```

**Ścieżka B (VPN niedostępny — kill switch aktywny):**
```
Pixel 9 → WiFi → Mudi → [BLOKADA] ✗ Internet
```

**Ścieżka C (tryb offline):**
```
Pixel 9 → WiFi → Mudi → [tylko LAN — brak dostępu do WAN]
```

### 8.3 Adresacja sieciowa

**Wymaganie REQ-ADDR-01:**

| Segment | Zakres IP | Uwagi |
|---------|-----------|-------|
| Mudi LAN (secure) | 10.77.1.0/24 | Pixel 9 i urządzenia zaufane |
| Mudi LAN (guest) | 10.77.2.0/24 | Izolowany segment gości |
| VPN tunnel | 10.200.0.0/24 | Adresacja wewnętrzna VPN |
| VPN server | 10.200.0.1 | Gateway VPN |

### 8.4 DNS

**Wymaganie REQ-DNS-01:** DNS na Mudi musi być skonfigurowany przez DoH (DNS-over-HTTPS)
lub DoT (DNS-over-TLS). Zakazane: plaintext UDP/53 do zewnętrznych resolverów.

**Wymaganie REQ-DNS-02:** Preferowane resolvery:
- Własny resolver organizacji (jeśli dostępny)
- Cloudflare 1.1.1.1 (DoH/DoT) — jako fallback
- Quad9 9.9.9.9 (DoH/DoT) — jako fallback

**Wymaganie REQ-DNS-03:** Resolver musi być skonfigurowany wewnątrz tunelu VPN,
nie na ISP DNS (zapobieganie DNS leak).

---

## 9. Zarządzanie tożsamością i dostępem

### 9.1 Konta i role

| Rola | Uprawnienia | Urządzenia | MFA |
|------|-------------|----------|-----|
| Operator urządzenia | Pełny dostęp do swojego urządzenia | Pixel 9 (owner) | Wymagane |
| Administrator sieci | Konfiguracja Mudi | Mudi admin panel | Wymagane |
| Audytor | Dostęp do logów (read-only) | Dashboard SYLION | Wymagane |
| Pipeline agent | Automatyczna weryfikacja konfiguracji | SYLION pipeline | Service account |

### 9.2 Zarządzanie dostępem do Mudi

**Wymaganie REQ-MUDI-ACCESS-01:**
- Panel administracyjny Mudi dostępny TYLKO z sieci LAN (nie z WAN)
- Domyślne hasło admin zmienione przy pierwszej konfiguracji
- Hasło admin: minimum 20 losowych znaków, przechowywane w KeePassXC lub Bitwarden

**Wymaganie REQ-MUDI-ACCESS-02:**
- SSH do Mudi: wyłączone lub dostępne tylko z określonego IP
- Jeśli SSH wymagane: klucze SSH (RSA 4096 lub ED25519), hasło wyłączone
- Sesje SSH: timeout 10 minut

### 9.3 Zarządzanie kluczami

**Wymaganie REQ-KEYS-01:** Klucze WireGuard generowane lokalnie:
```bash
# Na Mudi lub bezpiecznym serwerze
wg genkey | tee privatekey | wg pubkey > publickey
```

**Wymaganie REQ-KEYS-02:** Przechowywanie kluczy prywatnych:
- NIGDY nie wysyłaj klucza prywatnego przez sieć nieszyfrowaną
- Backup kluczy: zaszyfrowany (GPG, age), offline (pendrive zaszyfrowany)
- Rotacja: minimum co 90 dni

**Wymaganie REQ-KEYS-03:** Centralny rejestr kluczy:
- KeePassXC database z silnym hasłem master
- Backup bazy danych KeePassXC: ≥2 niezależne lokalizacje offline
- Dostęp do bazy: tylko osoby o roli Operator lub Administrator

---

## 10. Wymagania dotyczące aplikacji i ekosystemu

### 10.1 Dozwolone aplikacje (allowlist)

Poniższe aplikacje są pre-approved dla profili Work i Personal:

#### Komunikacja

| Aplikacja | Profil | Źródło | Uprawnienia |
|-----------|--------|--------|-------------|
| Signal | Work, Personal | Official APK / Accrescent | Mikrofon, Kamera, Kontakty (opt) |
| Element (Matrix) | Work | F-Droid / Official | Powiadomienia |
| Briar | Personal | F-Droid | Bluetooth (opt), WiFi |
| ProtonMail | Work | Official APK | Powiadomienia |

#### Bezpieczeństwo i narzędzia

| Aplikacja | Profil | Źródło | Uwagi |
|-----------|--------|--------|-------|
| GrapheneOS Auditor | Owner | GrapheneOS App Store | Weryfikacja sprzętu |
| WireGuard | All | F-Droid / Wbudowany | VPN client |
| KeePassDX | All | F-Droid | Menadżer haseł |
| Nextcloud | Work | F-Droid | Przechowywanie plików |
| Shelter | All | F-Droid | Tworzenie profilu pracy |
| OpenKeychain | Work | F-Droid | GPG na urządzeniu |

#### Przeglądarka

| Aplikacja | Profil | Źródło | Uwagi |
|-----------|--------|--------|-------|
| Vanadium | All | Wbudowany w GrapheneOS | Domyślna (Chromium hardened) |
| Firefox + uBlock Origin | Personal | F-Droid | Alternatywa |
| Tor Browser | Isolated | Official APK | Tylko profil Isolated |

### 10.2 Zakazane aplikacje (denylist)

Następujące kategorie aplikacji są ZAKAZANE we wszystkich profilach:

```
DENY-APP-01: Aplikacje wymagające root (modyfikacja systemu)
DENY-APP-02: Aplikacje z known malware (sprawdź VirusTotal / MobSF przed instalacją)
DENY-APP-03: Aplikacje zbierające dane do celów reklamowych (ad-SDKs)
DENY-APP-04: Antywirus/security apps innych niż zintegrowane z GrapheneOS
             (większość jest scamem lub zbiera dane)
DENY-APP-05: TikTok, WeChat, i inne aplikacje z known excessive data collection
DENY-APP-06: Aplikacje wymagające disabling Verified Boot
```

### 10.3 Konfiguracja uprawnień aplikacji

**Wymaganie REQ-PERM-01:** Każda aplikacja powinna działać z minimalnymi uprawnieniami
(principle of least privilege). GrapheneOS pozwala granularnie cofać uprawnienia.

**Wymaganie REQ-PERM-02:** Uprawnienia sieciowe:
- Nowe aplikacje: domyślnie BRAK dostępu do internetu
- Aplikacje wymagające sieci: jawna lista w AppManifest

**Wymaganie REQ-PERM-03:** Uprawnienia lokalizacji:
- Lokalizacja: DENY dla wszystkich aplikacji (domyślnie)
- Wyjątki: tylko aplikacje nawigacyjne (Maps), za jawną zgodą użytkownika

---

## 11. Zarządzanie danymi i retencja

### 11.1 Klasyfikacja danych

| Klasa | Opis | Przykłady | Ochrona |
|-------|------|-----------|---------|
| **POUFNE** | Dane wrażliwe — krytyczne | Klucze prywatne, dane osobowe | Szyfrowanie AES-256, dostęp minimalny |
| **WEWNĘTRZNE** | Dane robocze — nieupubliczniać | Konfiguracje, logi, dokumenty robocze | Szyfrowanie w spoczynku i transporcie |
| **PUBLICZNE** | Dane możliwe do upublicznienia | Dokumentacja techniczna bez danych wrażliwych | Standard TLS |

### 11.2 Polityki retencji

| Typ danych | Retencja | Mechanizm usunięcia |
|----------|----------|---------------------|
| Logi bezpieczeństwa urządzenia | 90 dni | Auto-purge, secure erase |
| Logi VPN | 7 dni | Auto-purge |
| Konfiguracje | Przez czas użytkowania + 30 dni | Secure erase na deprovisioning |
| Backup konfiguracji | 3 ostatnie wersje | Rotacja (FIFO) |
| Klucze kryptograficzne | Przez czas życia klucza | Secure erase + certyfikat zniszczenia |
| Dane diagnostyczne (opt-in) | 30 dni | Auto-purge |

### 11.3 Procedura deprovisioning

Przy wycofaniu urządzenia z użycia:

```
DEPROVISIONING-01: Usuń wszystkie profile użytkownika poza Owner
DEPROVISIONING-02: Factory reset przez GrapheneOS secure erase
    (Ustawienia → System → Reset → Erase all data)
DEPROVISIONING-03: Weryfikacja: wgraj dowolną treść testową, sprawdź czy po
    factory reset jest niedostępna (test odzysku danych)
DEPROVISIONING-04: Usuń klucze VPN z serwera (revoke WireGuard peer)
DEPROVISIONING-05: Usuń MAC urządzenia z DHCP reservations na Mudi
DEPROVISIONING-06: Udokumentuj deprovisioning w rejestrze urządzeń
DEPROVISIONING-07: Fizyczne zniszczenie urządzenia jeśli dane były POUFNE
    i urządzenie nie będzie reużywane
```

---

## 12. Procedury operacyjne

### 12.1 Onboarding nowego urządzenia

```
ONBOARDING-01: Zakup i weryfikacja sprzętu (REQ-HW-01, REQ-HW-02)
ONBOARDING-02: Instalacja GrapheneOS (REQ-GROS-01 do REQ-GROS-03)
ONBOARDING-03: Konfiguracja hardening (REQ-HARD-01 do REQ-HARD-12)
ONBOARDING-04: Konfiguracja profili (REQ-PROF-01, REQ-PROF-02)
ONBOARDING-05: Instalacja aplikacji z allowlist (Sekcja 10.1)
ONBOARDING-06: Konfiguracja VPN WireGuard (klucze generowane na urządzeniu)
ONBOARDING-07: Test VPN: weryfikacja IP, DNS leak test, kill switch test
ONBOARDING-08: Rejestracja urządzenia w rejestrze (IMEI, profil użytkownika, SHA firmware)
ONBOARDING-09: Przegląd bezpieczeństwa przez administratora (sign-off)
ONBOARDING-10: Przekazanie urządzenia użytkownikowi z instrukcją obsługi
```

### 12.2 Procedura reagowania na incydenty

**Poziom 1 — Niski (WARNING):**  
Nieudana próba uwierzytelnienia (≤5), podejrzana sieć WiFi.  
Akcja: Log, monitoring przez 24h.

**Poziom 2 — Średni (ALERT):**  
Wielokrotne nieudane uwierzytelnienia (>10), zmiana konfiguracji bez autoryzacji,
alert VPN (kill switch aktywowany).  
Akcja: Notyfikacja operatora, przegląd logów, tymczasowe wyłączenie dostępu.

**Poziom 3 — Wysoki (CRITICAL):**  
Podejrzana modyfikacja firmware, kradzież urządzenia, kompromitacja kluczy VPN,
drift Księgi SYLION (BookGuardian alert).  
Akcja: Natychmiastowa izolacja, revocation kluczy, reset urządzenia, śledztwo.

### 12.3 Procedury BackUp i recovery

```
BACKUP-01: Konfiguracja Mudi: eksport co 30 dni (GL.iNet Admin → System → Backup)
BACKUP-02: Klucze WireGuard: backup zaszyfrowany po każdej generacji
BACKUP-03: KeePass baza danych: backup na 2 niezależnych, offline nośnikach
BACKUP-04: GrapheneOS konfiguracja: eksport przez Google Backup NIE JEST dozwolony
           Użyj aplikacji backup (np. SeedVault — wbudowany w GrapheneOS)
BACKUP-05: Test recovery: raz na kwartał weryfikacja, że backup jest odtwarzalny
```

---

## 13. Testy i walidacja

### 13.1 Testy przed wdrożeniem

Przed dopuszczeniem urządzenia do produkcji:

| Test | Opis | Narzędzie | Wynik oczekiwany |
|------|------|-----------|-----------------|
| VPN leak test | Weryfikacja brak wycieku IP/DNS | ipleak.net, dnsleaktest.com | IP = VPN server, DNS = resolver VPN |
| WiFi isolation | Urządzenia w secure segment nie docierają do guest | nmap | Brak połączenia między VLAN |
| Kill switch test | Wyłącz VPN → ruch zablokowany | tcpdump na Mudi | Zero pakietów poza LAN |
| Bootloader status | Verified Boot zielony | fastboot oem device-info | Locked = true |
| Application permissions | Wszystkie app z minimalnym dostępem | Manualna inspekcja | Brak nadmiarowych uprawnień |
| GrapheneOS Auditor | Weryfikacja integralności systemu | GrapheneOS Auditor app | PASS |

### 13.2 Regularne audyty

| Częstotliwość | Audyt | Odpowiedzialny |
|---------------|-------|----------------|
| Tygodniowo | Przegląd logów bezpieczeństwa | Operator |
| Miesięcznie | Weryfikacja aktualizacji (OS, apps, firmware) | Administrator |
| Kwartalnie | Pełny przegląd konfiguracji vs. Księga SYLION | Audytor |
| Rocznie | Zewnętrzny pentest (opcjonalny, zalecany) | Zewnętrzna firma |

### 13.3 Zarządzanie lukami bezpieczeństwa

**Wymaganie REQ-VULN-01:**
1. Subskrypcja do security bulletins: Android (Google), GL.iNet
2. Ocena krytyczności każdej luki w ciągu 24h od ogłoszenia
3. Patch critical: 72h; patch high: 7 dni; patch medium: 30 dni; patch low: 90 dni

---

## 14. Zgodność regulacyjna

### 14.1 Polskie przepisy

| Przepis | Wymagania | Status |
|---------|-----------|--------|
| RODO (GDPR) | Minimalizacja danych, DPIA dla high-risk | W zakresie (Sekcja 7) |
| KSC (Ustawa o Krajowym Systemie Cyberbezpieczeństwa) | Zgłaszanie incydentów, min. środki bezp. | W zakresie dla OKI |
| KC (Kodeks Cywilny) | Odpowiedzialność za przetwarzanie danych | Standardowe |

### 14.2 Unijne przepisy

| Dyrektywa/Rozporządzenie | Zakres | Wymagania SYLION |
|--------------------------|--------|-----------------|
| NIS2 (2022/2555) | Operatorzy essentialnych usług | Zarządzanie ryzykiem, incydenty |
| DORA (2022/2554) | Finanse — ICT risk management | Jeśli klient finansowy |
| eIDAS 2 | Tożsamość cyfrowa | Potencjalnie dla future features |
| AI Act | Systemy AI wysokiego ryzyka | SYLION pipeline (Stage 6 — AI) |

### 14.3 Certyfikacje (opcjonalne)

Organizacje mogą dążyć do certyfikacji:
- **ISO 27001** — System Zarządzania Bezpieczeństwem Informacji
- **BSI C5** (Niemcy) — Cloud Security Baseline
- **Common Criteria EAL2+** — dla urządzeń używanych przez instytucje rządowe

---

## 15. Glosariusz

| Termin | Definicja |
|--------|-----------|
| BookGuardian | Moduł SYLION pipeline monitorujący integralność SHA-256 Księgi |
| DoH | DNS-over-HTTPS — szyfrowanie zapytań DNS |
| DoT | DNS-over-TLS — szyfrowanie zapytań DNS (wariant) |
| FBE | File-Based Encryption — szyfrowanie plików w Android (domyślne od Android 10) |
| GrapheneOS | Utwardzone, skoncentrowane na prywatności ROM dla urządzeń Pixel |
| HumanGate | Mechanizm SYLION wymagający akceptacji operatora dla ryzykownych operacji |
| Kill Switch | Mechanizm blokujący ruch gdy VPN jest niedostępny |
| Mudi | GL.iNet GL-E750 — przenośny router 4G z baterią |
| RODO | Rozporządzenie Ogólne o Ochronie Danych (GDPR) |
| Rebase | Autoryzowana aktualizacja baseline SHA BookGuardiana po zmianie Księgi |
| SHA-256 | Secure Hash Algorithm 256-bit — kryptograficzna suma kontrolna |
| SSID | Service Set Identifier — nazwa sieci WiFi |
| VPN | Virtual Private Network — szyfrowany tunel sieciowy |
| Verified Boot | Mechanizm weryfikacji integralności systemu Android przy starcie |
| WireGuard | Nowoczesny protokół VPN — szybszy i prostszy od OpenVPN |

---

## 16. Historia zmian

| Wersja | Data | Autor | Zmiany |
|--------|------|-------|--------|
| 3.0 | 2025-01-01 | [PM] | Wersja inicjalna — Pixel 8 + GrapheneOS + GL.iNet Beryl |
| 3.1 | 2025-06-15 | [PM] | Aktualizacja do Pixel 9, GL.iNet Mudi v2 |
| 3.2 | 2025-09-01 | [SEC] | Rozszerzenie modelu zagrożeń (T-05 supply chain) |
| 3.3 | 2025-12-01 | [LEGAL] | Dodanie sekcji RODO, NIS2, DORA |
| 3.4 | 2026-01-15 | [PM + SEC] | Finalizacja specyfikacji v5.9.x, zamrożenie jako FIXED |
| 3.4 FIXED | 2026-04-19 | BookGuardian | Zamrożony jako normative baseline SYLION pipeline |

---

## Appendix A — Checklisty wdrożeniowe

### A.1 Checklist Pixel 9 + GrapheneOS

```
□ Zakup urządzenia od autoryzowanego sprzedawcy
□ Weryfikacja numeru seryjnego i IMEI
□ Bootloader odblokowany → GrapheneOS zainstalowany → Bootloader zablokowany
□ Verified Boot: zielony
□ REQ-HARD-01 do REQ-HARD-12: wszystkie skonfigurowane
□ Profile: Owner, Work, Personal, Isolated — wszystkie skonfigurowane
□ Aplikacje z allowlist zainstalowane w odpowiednich profilach
□ VPN WireGuard: skonfigurowany, klucze wygenerowane lokalnie
□ Test VPN: leak test PASS, kill switch PASS
□ GrapheneOS Auditor: PASS
□ Rejestracja w rejestrze urządzeń
□ Sign-off administratora
```

### A.2 Checklist GL.iNet Mudi

```
□ Zakup od autoryzowanego dystrybutora
□ Factory reset przy pierwszej konfiguracji
□ Weryfikacja SHA-256 firmware
□ Aktualizacja do najnowszego firmware GL.iNet
□ Zmiana domyślnego hasła admin (min. 20 znaków)
□ WiFi: SSID ukryte, WPA3, hasło min. 20 znaków
□ LAN subnet zmieniony z domyślnego
□ DNS: DoH lub DoT skonfigurowany
□ VPN WireGuard: skonfigurowany z kill switch
□ VLAN: secure + guest skonfigurowane
□ SSH: wyłączone lub klucze SSH, timeout 10 min
□ Admin panel: tylko z LAN, nie z WAN
□ Backup konfiguracji wykonany
□ Test VPN i kill switch PASS
```

---

*Koniec Księgi SYLION 3.4 FIXED*  
*SHA-256 niniejszego pliku jest bazą dla BookGuardian SYLION pipeline.*  
*Wszelkie modyfikacje muszą być autoryzowane przez właściciela produktu za pomocą `book_guardian_rebase.py`.*
