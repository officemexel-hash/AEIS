# 45. Operator Mobile App — KMP (Kotlin Multiplatform) Etap 2
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja aplikacji mobilnej SYLION Operator dla Android i iOS.
> Etap 2: autentykacja, biometria, encrypted token store, push notifications stub, iOS skeleton.
> Lokalizacja: `operator-mobile/` (poza `src/`).

## Spis tresci

1. [Cel modulu](#1-cel-modulu)
2. [Architektura KMP](#2-architektura-kmp)
3. [Konfiguracja](#3-konfiguracja)
4. [Autentykacja i bezpieczenstwo (Etap 2)](#4-autentykacja-i-bezpieczenstwo-etap-2)
5. [Push notifications](#5-push-notifications)
6. [Ekrany — Android](#6-ekrany--android)
7. [iOS — stan Etap 2](#7-ios--stan-etap-2)
8. [Weryfikacja](#8-weryfikacja)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modulu

Aplikacja mobilna `operator-mobile` umozliwia operatorowi SYLION AEIS dostep do kluczowych
funkcji systemu z urzadzen mobilnych (Android i iOS). Uzywaja wspolnego kodu biznesowego
(KMP — Kotlin Multiplatform) z natywnym UI per platforma.

Etap 2 dodal:
- kompletna autentykacja email+password (KMP shared `AuthRepository`)
- biometrie Android (`BiometricAuth`, `BiometricPrompt`)
- zaszyfrowany magazyn tokenow Android (`EncryptedTokenStore`, AES256-GCM)
- stub Firebase Cloud Messaging (`FcmTokenProvider`)
- skeleton iOS z podlinkowanym frameworkiem `shared` przez CocoaPods
- konfiguracje buildow Android i iOS (wersje bibliotek, Podfile)

---

## 2. Architektura KMP

```
operator-mobile/
├── shared/                        — wspolny kod KMP (Android + iOS)
│   ├── build.gradle.kts
│   └── src/commonMain/kotlin/sylion/aeis/operator/
│       ├── auth/
│       │   ├── AuthService.kt     — interfejs (login/logout/getToken)
│       │   ├── AuthRepository.kt  — implementacja (Ktor HTTP)
│       │   └── AuthState.kt       — sealed class (Anonymous / Authenticated)
│       └── push/
│           ├── PushService.kt     — interfejs
│           └── PushRepository.kt  — implementacja (stub, Ktor)
│
├── androidApp/
│   ├── build.gradle.kts
│   └── src/main/kotlin/sylion/aeis/operator/android/
│       ├── MainActivity.kt
│       ├── auth/
│       │   ├── BiometricAuth.kt        — BiometricPrompt wrapper
│       │   └── EncryptedTokenStore.kt  — AES256-GCM SharedPreferences
│       ├── push/
│       │   └── FcmTokenProvider.kt     — FCM stub
│       └── ui/
│           ├── login/
│           │   ├── LoginScreen.kt      — ekran logowania (Compose)
│           │   └── LoginViewModel.kt   — ViewModel z AuthRepository
│           └── home/
│               └── HomeScreen.kt       — ekran glowny po zalogowaniu
│
├── iosApp/
│   ├── Podfile                    — CocoaPods: shared KMP framework
│   ├── iosApp.xcodeproj/
│   └── iosApp/
│       ├── iOSApp.swift           — entry point
│       └── ContentView.swift      — Etap 2 skeleton (Etap 3: pelne UI)
│
└── gradle/libs.versions.toml      — katalog wersji zaleznosci
```

---

## 3. Konfiguracja

### 3.1. Android

| Parametr | Wartosc (Etap 2) |
|----------|-----------------|
| Kotlin | zgodnie z `libs.versions.toml` |
| Compose | Material3 |
| BiometricManager | `androidx.biometric` |
| EncryptedPrefs | `androidx.security.crypto` (AES256-SIV key, AES256-GCM value) |
| FCM | stub (wymaga `google-services.json` w produkcji) |

### 3.2. Shared (KMP)

| Parametr | Wartosc |
|----------|---------|
| Backend URL domyslny | `http://localhost:8421` |
| Login endpoint | `POST /api/v1/mobile/auth/login` |
| Push register endpoint | `POST /api/v1/mobile/push/register` |
| HTTP klient | Ktor z ContentNegotiation (kotlinx.serialization) |

### 3.3. iOS

| Parametr | Wartosc |
|----------|---------|
| Framework | `shared` (CocoaPods) |
| Stan Etap 2 | Skeleton `ContentView` ("SYLION Operator / iOS - Etap 3") |
| Biometria iOS | Zaplanowana na Etap 3 (`LocalAuthentication.framework`) |
| Push iOS | Zaplanowane na Etap 3 (`UserNotifications / APNs`) |

---

## 4. Autentykacja i bezpieczenstwo (Etap 2)

### 4.1. `AuthService` (interfejs KMP shared)

```kotlin
interface AuthService {
    suspend fun login(email: String, password: String): Result<AuthState.Authenticated>
    suspend fun logout()
    fun getToken(): String?
    fun isAuthenticated(): Boolean
    fun getState(): AuthState
}
```

### 4.2. `AuthRepository` (implementacja)

- Wywolyje `POST /api/v1/mobile/auth/login` z `{email, password}`.
- Backend zwraca `{token, expiresAt}`.
- Stan trzymany w pamieci jako `_state: AuthState`.
- Brak persystencji w `shared` — persystencja na Android przez `EncryptedTokenStore`.

### 4.3. `AuthState` (sealed class)

```kotlin
sealed class AuthState {
    object Anonymous : AuthState()
    data class Authenticated(val token: String, val expiresAt: Long) : AuthState()
}
```

### 4.4. `EncryptedTokenStore` (Android)

- Uzytkownik AES256-GCM (`MasterKey.KeyScheme.AES256_GCM`).
- Klucze: `auth_token` (String), `auth_expires_at` (Long).
- Metody: `saveToken(token, expiresAt)`, `getToken()`, `getExpiresAt()`, `clear()`, `hasValidToken()`.
- `hasValidToken()`: sprawdza czy token istnieje i `expiresAt > System.currentTimeMillis()`.

### 4.5. `BiometricAuth` (Android)

- Klasa `BiometricAuth(activity: FragmentActivity)`.
- `checkAvailability(context): Availability` — sprawdza dostepnosc (`AVAILABLE`, `NOT_ENROLLED`, `NOT_AVAILABLE`).
- `authenticate(title, subtitle, onSuccess, onError, onFallback)` — uruchamia `BiometricPrompt.AuthenticationCallback`.
- Uzywana jako warstwa dodatkowa po logowaniu email+password (unlock sesji).

### 4.6. `LoginViewModel` (Android Compose)

- Trzyma `_uiState: LoginUiState` (`Idle / Loading / Error(msg) / Success`).
- `login(email, password)` — woła `authRepository.login(...)`, na sukces: `encryptedTokenStore.saveToken(...)`.
- `loginWithBiometric()` — woła `biometricAuth.authenticate(...)` jesli `encryptedTokenStore.hasValidToken()`.

---

## 5. Push notifications

### 5.1. `PushRepository` (shared KMP)

- `registerToken(deviceToken, platform)` → `POST /api/v1/mobile/push/register`.
- `unregisterToken(deviceToken)` → `DELETE /api/v1/mobile/push/unregister`.

### 5.2. `FcmTokenProvider` (Android, stub)

- Oczekuje wezwania z `FirebaseMessagingService.onNewToken(token)`.
- Na nowy token: `pushRepository.registerToken(token, "android")` w `Dispatchers.IO`.
- Wymaga w produkcji: `google-services.json` + plugin `com.google.gms:google-services`.

### 5.3. Wymagania produkcyjne (Etap 3)

- Android: `google-services.json` z projektu Firebase.
- iOS: certyfikat APNs (`.p8`) + konfiguracja `UserNotifications`.
- Backend: endpointy `push/register` i `push/unregister` musza byc zaimplementowane.

---

## 6. Ekrany — Android

### 6.1. `LoginScreen`

- Pola: email, password.
- Przyciski: "Zaloguj" (email+password), "Zaloguj biometria" (jesli `hasValidToken`).
- UiState: `Loading` → spinner, `Error` → komunikat, `Success` → nawigacja do `HomeScreen`.

### 6.2. `HomeScreen`

- Wyswietla tekst powitalny + informacje o zalogowanym uzytkowniku.
- Przycisk "Wyloguj" → `viewModel.logout()`.
- Etap 3 doda: lista kart AEIS, quick actions, notifications feed.

---

## 7. iOS — stan Etap 2

Framework `shared` jest podlinkowany przez CocoaPods (Podfile: `pod 'shared', ...`).
`ContentView.swift` jest skeletonem pokazujacym "iOS - Etap 3" — pelne UI implementowane w Etapie 3.

Plik `iosApp.xcodeproj` zawiera `.gitkeep` — projekt Xcode zostanie wygenerowany przez `pod install`.

---

## 8. Weryfikacja

```bash
# Android (z katalogu operator-mobile/)
./gradlew :androidApp:assembleDebug
./gradlew :androidApp:connectedAndroidTest

# iOS — wymaga macOS
cd iosApp && pod install
open iosApp.xcworkspace   # build w Xcode

# Backend endpoint
curl -X POST http://localhost:8421/api/v1/mobile/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"operator@sylion.ai","password":"test123"}'
```

---

## 9. Troubleshooting

| Problem | Mozliwa przyczyna | Rozwiazanie |
|---------|-------------------|-------------|
| Login zwraca 404 | Backend nie ma endpointu mobile/auth | Sprawdz `mobile_routes.py` w sylion-pipeline |
| Biometria niedostepna | Brak enrolled fingerprint/face | `BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED` → pokazuj fallback haslo |
| Token nie persystuje | `EncryptedTokenStore` nie wywolany | Sprawdz `LoginViewModel.login()` → `encryptedTokenStore.saveToken(...)` |
| iOS build fail | `pod install` nie wywolany | `cd iosApp && pod install` |
| FCM token nie rejestruje | stub FcmTokenProvider (brak `FirebaseMessagingService`) | Etap 3: podlacz `FirebaseMessagingService.onNewToken` |

---

## 10. Cross-references

- [`12_mobile_gateway.md`](12_mobile_gateway.md) — backend gateway dla mobile (JWT, refresh, mobile endpoints)
- [`01_preferences.md`](01_preferences.md) — preferencje operatora dostepne przez API mobile
- [`41_environment_variables.md`](41_environment_variables.md) — URL backendu (`localhost:8421`)
- `docs/claude_parallel/aeis_advisor/_handoff/sprint3/claude_mobile_etap2_report.md` — raport z implementacji Etap 2
