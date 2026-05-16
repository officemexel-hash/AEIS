# AEIS Operator — Aplikacja mobilna (Etap 2)

Kotlin Multiplatform (KMP) + Jetpack Compose. Android first.

## Wymagania

| Narzędzie | Wersja minimalna |
|---|---|
| Java (JDK) | 17+ |
| Android SDK | 35 (compileSdk) |
| Android Studio | Hedgehog+ / Koala+ |
| Gradle | 8.11.1 (pobierany przez wrapper) |

### Konfiguracja Android SDK

1. Zainstaluj Android Studio lub Android command-line tools
2. Zaakceptuj licencje: `sdkmanager --licenses`
3. Ustaw zmienną środowiskową:
   ```bash
   export ANDROID_HOME=/path/to/android/sdk
   ```
   lub utwórz `operator-mobile/local.properties`:
   ```
   sdk.dir=/path/to/android/sdk
   ```

## Budowanie

```bash
cd operator-mobile

# Debug APK
./gradlew assembleDebug

# Release APK
./gradlew assembleRelease

# Testy jednostkowe
./gradlew testDebugUnitTest

# Testy instrumentowane (wymaga podłączonego urządzenia)
./gradlew connectedAndroidTest
```

## Instalacja na urządzeniu

```bash
adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
adb shell am start -n com.sylion.aeis.operator/.MainActivity
```

## Struktura projektu

```
operator-mobile/
├── shared/                          # KMP — współdzielona logika biznesowa
│   └── src/commonMain/kotlin/sylion/aeis/operator/
│       ├── model/                   # AdvisorCard, Project, enums
│       └── repo/                    # CardRepository, ProjectRepository (interfejsy + stuby)
└── androidApp/                      # Android Compose UI
    └── src/main/kotlin/sylion/aeis/operator/android/
        ├── MainActivity.kt          # Entry point (Hello AEIS Mobile — stub)
        └── ui/theme/                # Material 3 dark — modern modernist
            ├── Color.kt             # Paleta + kolory semantyczne (risk: low/medium/high/critical)
            ├── Typography.kt        # Skala typograficzna
            └── Theme.kt             # AEISOperatorTheme (dark mode enforced)
```

## Design system

- **Tryb**: zawsze dark mode (operator preference)
- **Material 3**: darkColorScheme z paletą deep-blue/indigo
- **Kolory ryzyka**:
  - LOW → `#4CAF50` (zielony)
  - MEDIUM → `#FFC107` (bursztynowy)
  - HIGH → `#FF9800` (pomarańczowy)
  - CRITICAL → `#F44336` (czerwony)
- **Typografia**: system font, SemiBold dla headings, Medium dla labels
- **Brak emoji w UI**

## Etapy implementacji

| Etap | Zakres | Status |
|---|---|---|
| Bootstrap (ten PR) | Skeleton KMP + theme + Hello screen | DONE |
| Stage A (M1) | FeedScreen, CardDetailScreen, LifecycleScreen | pending |
| Stage A (M2) | WizardScreen, FundingScreen, HumanGateScreen, PairingScreen, SettingsScreen | pending |
| Stage B (M3) | Auth, BiometricPrompt, FCM push, JWT Keystore | pending |
| Stage C | E2E Appium testy, personas integration | pending |

## Uwagi deweloperskie

- `CardRepositoryStub` / `ProjectRepositoryStub` — placeholdery do zastąpienia przez
  implementację REST przeciwko `mobile_gateway` (CodexM1)
- `minSdk = 26` — wymagane dla `BiometricPrompt` (Stage B)
- Gradle configuration cache włączony (`org.gradle.configuration-cache=true`)
