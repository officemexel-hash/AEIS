# Scaling — Operator Guide

## Co robi ten moduł

Doradza, jaką infrastrukturę uruchomić pod projekt AEIS: tylko lokalnie, lokalnie + jeden VPS, tylko VPS, czy wiele VPS-ów. Na podstawie profilu obciążenia (szacowane tokeny/dzień, równoległość, wymagane opóźnienie) dobiera topologię, poziom decyzyjny (D-level) i buduje plan wdrożenia etapami (staging). Wszystko powyżej `local_only` to D3+ — wymaga Evidence Pack i Human Gate.

## Kiedy operator wchodzi w interakcję

- **Przy tworzeniu deploymentu** — AEIS wyświetla kartę *Topologia rekomendowana* z opcjami lokal/VPS/multi.
- **Panel Operator → Infrastruktura → Środowiska** — przeglądasz zarejestrowane środowiska (VPS-y, capacity).
- **Karta *Plan staging*** — gdy zmieniasz topologię (np. scale-up z local na VPS), AEIS pokazuje kolejne kroki: deploy, test, switchover.
- **Panel Operator → Infrastruktura → Rejestruj środowisko** — ręcznie dodajesz nowy VPS do inventory.

## Konfiguracja

| Ustawienie | Gdzie w UI | Efekt |
|---|---|---|
| **Strategia runtime** | Preferencje → Infrastruktura → Strategia (future) | Wymusza konkretną topologię (`local_only`, `hybrid`, `vps_only`). Obecnie nieaktywne — czeka na Codex Phase 2. |
| **Autonomy level** | Operator → Ustawienia → Poziom autonomii | `manual` wymusza D3+ na wszystkich kartach infrastruktury (U5 rule). |
| **Trusted providers** | Preferencje → Bezpieczeństwo (future) | Ogranicza, które firmy hostingowe mogą być użyte w rekomendacji VPS. |

> Obecnie rekomendacja jest w pełni automatyczna na podstawie profilu obciążenia. W przyszłości operator będzie mógł wymusić topologię przez preferencję.

## Rozwiązywanie problemów

### 1. AEIS zawsze rekomenduje `local_only`, choć projekt jest duży

**Symptom**: Nawet dla 10M tokenów/dzień rekomendacja to lokalny model, brak VPS.

**Przyczyna**: Pole `estimated_tokens_per_day` w profilu obciążenia jest `None`, ujemne lub nie zostało przekazane do modułu.

**Rozwiązanie**:
1. W panelu **Projekt → Profil obciążenia** upewnij się, że pole *Szacowane tokeny/dzień* jest wypełnione liczbą dodatnią.
2. Sprawdź, czy parallelism > 0 (jeśli = 0 lub brak, moduł przyjmuje 1).
3. Wyczyść pamięć podręczną i wygeneruj rekomendację na nowo.

### 2. Przy staging planie pojawia się `ValueError: ... is not in list`

**Symptom**: Czerwony błąd przy próbie wygenerowania planu zmiany topologii.

**Przyczyna**: Podano nieznany ciąg topologii (literówka lub przestarzała nazwa).

**Rozwiązanie**:
1. Upewnij się, że używasz dokładnie jednej z nazw: `local_only`, `local_plus_vps`, `vps_only`, `multi_vps`.
2. Sprawdź wielkość liter — nazwy są case-sensitive.
3. Jeśli używasz API bezpośrednio — sprawdź, czy `current_topology` i `target_topology` nie są puste.

### 3. Karta VPS ma D-level D2 zamiast D3

**Symptom**: AEIS pokazuje rekomendację VPS bez żądania Human Gate / Evidence Pack.

**Przyczyna**: Engine niepoprawnie zaklasyfikował typ rekomendacji lub override autonomii nie działa.

**Rozwiązanie**:
1. Sprawdź w panelu **Operator → Ustawienia → Poziom autonomii** — ustaw na `manual` (wymusza D3+).
2. Sprawdź log eventu `aeis.advisor.scaling.topology_recommended` — zobacz, jaki `d_level` został wyemitowany.
3. Jeśli `d_level=D2` dla `vps_only` lub `multi_vps` — to błąd wewnętrzny engine; zgłoś do zespołu (Claude territory).

### 4. Rejestracja środowiska nie pojawia się w inventory

**Symptom**: Dodałeś VPS w panelu, ale lista **Operator → Infrastruktura → Środowiska** jest pusta.

**Przyczyna**: Baza SQLite nie jest zainicjalizowana lub `operator_id` w rejestracji nie zgadza się z aktualnym operatorem.

**Rozwiązanie**:
1. Sprawdź w logu event `aeis.advisor.scaling.env_registered` — zobacz, pod jakim `operator_id` zostało zapisane.
2. Upewnij się, że masz uprawnienia do przeglądania inventory (sprawdź RBAC).
3. Jeśli baza jest pusta — zrestartuj AEIS; `ensure_tables()` tworzy tabele leniwie przy pierwszym dostępie.

### 5. Scale-up i scale-down dają ten sam plan (brak zmian)

**Symptom**: Plan staging pokazuje tylko 1 fazę "no_change".

**Przyczyna**: Aktualna topologia i docelowa są identyczne.

**Rozwiązanie**:
1. Sprawdź w karcie, jaka jest *Aktualna topologia* (może już jesteś na `multi_vps`).
2. Jeśli celowo nie zmieniasz niczego — to prawidłowe zachowanie.
3. Jeśli chcesz zmienić — wybierz inną topologię docelową w panelu **Infrastruktura → Zmień topologię**.

## Eventy emitowane (audit / debug)

| Event | Kiedy | Payload (kluczowe pola) |
|---|---|---|
| `aeis.advisor.scaling.topology_recommended` | Po rekomendacji topologii | `card_id`, `operator_id`, `project_id`, `recommended`, `d_level`, `evidence_pack_id` |
| `aeis.advisor.scaling.staging_proposed` | Po wygenerowaniu planu staging | `plan_id`, `current`, `target`, `phases_count` |
| `aeis.advisor.scaling.env_registered` | Po rejestracji środowiska | `env_id`, `operator_id`, `kind`, `capacity_tokens_per_day` |

> Eventy można podejrzeć w panelu **Operator → Audit Trail** lub w konsoli przez `EventBus.subscribe(...)`.

## Cross-references

- **Role Resolver** — wybiera modele, które będą uruchamiane na zarekomendowanej infrastrukturze; lokalne modele = lokal_only, zewnętrzne = VPS-okienko.
- **Variants** — wariant *aggressive* może wymagać `multi_vps`; scaling sprawdza, czy topologia jest możliwa do realizacji.
- **Subscription** — każda zmiana VPS (D3+) może wpłynąć na koszt; subscription weryfikuje ROI przed akceptacją.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md) — D3+ dla VPS i zmian infrastruktury.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md) — wymagana zawartość Evidence Pack przy scale-up.
- **Architecture**: [`docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md`](../../../../../../docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md) — pełna taksonomia eventów advisor.
