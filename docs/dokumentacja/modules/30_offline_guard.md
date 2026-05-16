# 30. Backend Offline Guard — Strażnik dostępności backendu
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja dwóch komponentów offline-awareness: `BackendOfflineGuard` (blokujący
> cały UI) oraz `ApiOfflineBanner` (nieblokujący pasek informacyjny). Oba monitorują
> dostępność backendu, lecz działają w różnych trybach reakcji.

## Spis treści

1. [Cel i lokalizacja](#1-cel-i-lokalizacja)
   - 1.1. BackendOfflineGuard (blokujący)
   - 1.2. ApiOfflineBanner (nieblokujący)
2. [Architektura](#2-architektura)
3. [Stany i zachowanie](#3-stany-i-zachowanie)
4. [Konfiguracja](#4-konfiguracja)
5. [Integracja w layout](#5-integracja-w-layout)
6. [UI offline — szczegóły](#6-ui-offline--szczegóły)
7. [Healthcheck endpoint](#7-healthcheck-endpoint)
8. [Przykłady i operacja](#8-przykłady-i-operacja)
9. [Weryfikacja](#9-weryfikacja)
10. [Cross-references](#10-cross-references)

---

## 1. Cel i lokalizacja

### 1.1. BackendOfflineGuard (blokujący)

| Pole | Wartość |
|------|---------|
| Plik komponentu | `src/sylion-frontend/src/components/system/BackendOfflineGuard.tsx` |
| Integracja | `src/sylion-frontend/src/app/(app)/layout.tsx` (root wrapper) |
| Endpoint monitorowany | `GET /health` (backend FastAPI) |
| Typ | Client component (`"use client"`) |

`BackendOfflineGuard` rozwiązuje problem sytuacji, gdy frontend załaduje się poprawnie,
ale backend SYLION nie jest uruchomiony. Bez guardu operator widzi stronę z niezrozumiałymi
błędami sieciowymi zamiast czytelnego komunikatu. Z guardem cały UI jest zablokowany
(rozmycie + overlay) z wyraźną instrukcją uruchomienia serwera.

### 1.2. ApiOfflineBanner (nieblokujący)

| Pole | Wartość |
|------|---------|
| Plik komponentu | `src/sylion-frontend/src/components/layout/ApiOfflineBanner.tsx` |
| Integracja | dowolny layout lub strona, która może tracić połączenie z API |
| Źródło statusu | `useHealth()` hook (`src/sylion-frontend/src/lib/api/hooks.ts`) |
| Typ | Client component (`"use client"`) |

Dodany w sprint2 (consolidated commit 9c45020) jako uzupełnienie `BackendOfflineGuard`.
Różnica: `ApiOfflineBanner` **nie blokuje** interfejsu — wyświetla drobny amber
"toast" w prawym dolnym rogu ekranu, informując o problemie z połączeniem bez
uniemożliwiania dalszej pracy z danymi zapisanymi lokalnie.

```tsx
export function ApiOfflineBanner() {
  const { error, loading, data } = useHealth();
  const isOffline = !loading && (error !== null || data.status !== "ok");
  if (!isOffline) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 max-w-sm rounded-md border
                 border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm
                 text-amber-200 shadow-lg backdrop-blur"
    >
      <div className="font-medium">Backend offline</div>
      <div className="mt-1 text-xs text-amber-200/80">
        Nie można połączyć się z API (127.0.0.1:8010).
        Dane mogą być nieaktualne lub zastępcze.
      </div>
    </div>
  );
}
```

#### Porównanie: Guard vs Banner

| Cecha | `BackendOfflineGuard` | `ApiOfflineBanner` |
|-------|----------------------|--------------------|
| Blokuje UI | tak (blur + overlay) | nie |
| Pozycja | fullscreen fixed | bottom-right toast |
| Źródło statusu | własny polling `/health` | `useHealth()` hook |
| Retry button | tak (`window.location.reload()`) | nie |
| Poziom ważności | krytyczny — praca niemożliwa | informacyjny — praca możliwa z cache |
| Plik | `system/BackendOfflineGuard.tsx` | `layout/ApiOfflineBanner.tsx` |

---

## 2. Architektura

```typescript
type BackendStatus = "checking" | "online" | "offline";

export function BackendOfflineGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>("checking");
  // polling /health co 5 sekund
  // "checking" → loading screen
  // "offline"  → blur overlay + instrukcje
  // "online"   → renderuje children
}
```

### 2.1. Mechanika pollingu

```
useEffect przy mount:
  1. Natychmiastowe check() po zamontowaniu
  2. setInterval(check, 5000) — co 5 sekund
  3. Cleanup: clearInterval + mounted=false przy odmontowaniu

check():
  fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) })
  → res.ok → "online"
  → !res.ok lub timeout → "offline"
```

Timeout żądania: 3000 ms (3 sekundy) — żeby nie blokować dłużej gdy backend jest powolny
przy starcie.

---

## 3. Stany i zachowanie

| Stan | Warunek | Render |
|------|---------|--------|
| `checking` | Przy starcie, przed pierwszą odpowiedzią | Loading screen: "Łączenie z serwerem..." (wyśrodkowane, `min-h-screen`) |
| `online` | `/health` zwraca HTTP 2xx | `<>{children}</>` — normalne renderowanie aplikacji |
| `offline` | `/health` zwraca błąd, timeout lub non-2xx | Blur overlay + modal z instrukcjami + button "Spróbuj ponownie" |

### 3.1. Przejścia stanów

```
start  →  checking
checking  →  online    (gdy /health ok)
checking  →  offline   (gdy /health fail)
offline   →  online    (gdy następny tick: /health znowu ok)
online    →  offline   (gdy następny tick: /health fail)
```

Stan przywraca się automatycznie — gdy backend wróci, overlay znika bez przeładowania strony.
Przycisk "Spróbuj ponownie" wymusza `window.location.reload()` — przeładowanie strony.

---

## 4. Konfiguracja

### 4.1. Zmienna środowiskowa

| Zmienna | Domyślna | Opis |
|---------|----------|------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8010` | Adres backendu SYLION. Musi być widoczny z przeglądarki klienta. |

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010

# Produkcja (różny host)
NEXT_PUBLIC_API_URL=https://api.sylion.example.com
```

### 4.2. Parametry hardcodowane

| Parametr | Wartość | Opis |
|----------|---------|------|
| Interwał pollingu | `5000 ms` | Co ile sekund sprawdzany jest `/health` |
| Timeout żądania | `3000 ms` | Czas oczekiwania na odpowiedź zanim uznamy backend za offline |
| Endpoint | `/health` | Ścieżka healthchecku |

---

## 5. Integracja w layout

Plik: `src/sylion-frontend/src/app/(app)/layout.tsx`

```tsx
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <BackendOfflineGuard>
      <SidebarProvider>
        <AppShell>{children}</AppShell>
      </SidebarProvider>
    </BackendOfflineGuard>
  );
}
```

`BackendOfflineGuard` jest najwyższym wrapperem w hierarchii komponentów `(app)` route group.
Oznacza to, że każda strona aplikacji (advisor, onboarding, settings, faq, dashboard itd.)
jest chroniona przez guard — żadna strona nie renderuje pełnego UI gdy backend jest offline.

Wyjątek: strony poza route group `(app)` (np. strona logowania `(auth)`) nie są owinięte
guard-em i renderują się niezależnie od statusu backendu.

---

## 6. UI offline — szczegóły

### 6.1. Warstwa rozmyta (children)

```tsx
<div className="pointer-events-none opacity-30 blur-sm select-none">
  {children}
</div>
```

Children aplikacji (AppShell, sidebar, treść strony) są renderowane ale:
- `pointer-events-none` — kliknięcia zablokowane
- `opacity-30` — przyciemnione do 30%
- `blur-sm` — efekt rozmycia
- `select-none` — zaznaczanie tekstu zablokowane

### 6.2. Overlay modal

```
┌─────────────────────────────────────────────────────┐
│  [WifiOff ikona]                                    │
│  Backend niedostępny                                │
│  Nie można połączyć się z serwerem SYLION.          │
│  Sprawdź czy serwer działa na http://127.0.0.1:8010 │
│                                                     │
│  Aplikacja będzie zablokowana... (retry co 5s)      │
│                                                     │
│  Co możesz zrobić:                                  │
│  • Uruchom serwer: scripts/start-server.bat         │
│  • Sprawdź logi backendu w terminalu                │
│  • Jeśli serwer działa, sprawdź czy port nie jest   │
│    zablokowany                                      │
│                                                     │
│  [Spróbuj ponownie]                                 │
└─────────────────────────────────────────────────────┘
```

Overlay jest `fixed inset-0 z-50` — przykrywa całą stronę.
Backdrop: `bg-background/80 backdrop-blur-sm`.

---

## 7. Healthcheck endpoint

Backend FastAPI udostępnia `GET /health` na głównej aplikacji.

```bash
curl http://127.0.0.1:8010/health
# {"status": "ok"}
```

Guard uznaje backend za "online" gdy:
- Odpowiedź `res.ok` (HTTP status 200–299)

Guard uznaje backend za "offline" gdy:
- Błąd sieciowy (backend nie odpowiada)
- Timeout (3s bez odpowiedzi)
- Odpowiedź non-2xx (np. 500, 503)

---

## 8. Przykłady i operacja

### 8.1. Uruchomienie serwera (Windows)

```bat
scripts\start-server.bat
```

Po uruchomieniu: guard przejdzie z `offline` do `online` przy następnym ticku (maks. 5s),
overlay zniknie i aplikacja wróci do normalnego funkcjonowania.

### 8.2. Diagnoza gdy guard ciągle pokazuje offline

1. Sprawdź czy backend jest uruchomiony: `curl http://127.0.0.1:8010/health`
2. Sprawdź zmienną `NEXT_PUBLIC_API_URL` w `.env.local`
3. Sprawdź firewall / proxy — port 8010 musi być dostępny z przeglądarki
4. Sprawdź logi backend w terminalu

### 8.3. Symulacja offline w dev

```javascript
// W DevTools: zablokuj /health przez Network > Block request URL
// lub wyłącz backend
```

Guard natychmiast pokaże overlay po 3s (timeout) lub 5s (następny tick).

---

## 9. Weryfikacja

```bash
# Sprawdź czy guard jest w layoucie
grep -n "BackendOfflineGuard" src/sylion-frontend/src/app/\(app\)/layout.tsx
# Oczekiwane: linia z import i użyciem

# Sprawdź healthcheck
curl -s http://127.0.0.1:8010/health
# Oczekiwane: {"status": "ok"} lub {"status": "ok", ...}

# Sprawdź czy komponent istnieje
ls src/sylion-frontend/src/components/system/BackendOfflineGuard.tsx
```

---

## 10. Cross-references

### 10.1. Komponent nadrzędny

| Element | Plik |
|---------|------|
| Layout `(app)` | `src/sylion-frontend/src/app/(app)/layout.tsx` |
| `SidebarProvider` (wewnątrz guard) | `src/sylion-frontend/src/components/layout/SidebarContext.tsx` |
| `AppShell` (wewnątrz guard) | zdefiniowany w `layout.tsx` |

### 10.2. Powiązane zachowanie

| Komponent | Relacja |
|-----------|---------|
| `MockBanner` | Pokazuje się gdy backend odpowiada ale dane są mockowe — komplementarny do guard |
| `FirstRunBanner` | Polling `/onboarding/has_completed` — uruchamiany tylko gdy guard zezwolił na render (backend online) |
| `ApiOfflineBanner` | Nieblokujący partner Guard — pokazuje amber toast bez blokowania UI; plik: `layout/ApiOfflineBanner.tsx` |

### 10.3. Backend endpoint

- `GET /health` — zdefiniowany w `src/sylion-pipeline/sylion/api/app.py`
- `GET /api/v1/orchestration/health` — osobny health dla modułu orchestration_config

### 10.4. Setup

Instrukcje uruchomienia serwera: [`modules/40_setup_step_by_step.md`](40_setup_step_by_step.md) §3.
Zmienne środowiskowe: [`modules/41_environment_variables.md`](41_environment_variables.md) — `NEXT_PUBLIC_API_URL`.
