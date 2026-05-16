# W14 Demo Projects — 6 projektów demonstracyjnych
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Moduł: `sylion.aeis.testing.demo_projects` + `sylion.demo.*`
> Commits: `3fd53a06` (E11 manifesty) + `df31e83b` (E11 execute_demo) +
>          `c5e509f0` (E11-full mobile) + `3e6c9dbd` (E11-full 5 demos) +
>          `4fcc42ee` (E11-rest 40 endpoints) + `26cb526c` (E11-fe 5 stron)

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [6 manifestów projektów demo](#4-6-manifestów-projektów-demo)
5. [DemoProjectOrchestrator + execute_demo](#5-demoprojectorchestratorexecute_demo)
6. [Backend demo — implementacje domenowe](#6-backend-demo--implementacje-domenowe)
7. [REST endpoints — 51 endpointów łącznie](#7-rest-endpoints--51-endpointów-łącznie)
8. [Frontend — 6 stron demo](#8-frontend--6-stron-demo)
9. [Testy — 151 testów łącznie](#9-testy--151-testów-łącznie)
10. [Weryfikacja](#10-weryfikacja)
11. [Rozwiązywanie problemów](#11-rozwiązywanie-problemów)
12. [Cross-references](#12-cross-references)

---

## 1. Cel modułu

Demo Projects to 6 pełnych projektów demonstracyjnych pokrywających różne domeny
i poziomy D-ladder (D3 do D5). Każdy projekt:

- Posiada manifest YAML deklarujący wymagania (persony, klasy testów, blokery release)
- Ma pełną implementację backendową z prawdziwymi zabezpieczeniami W14 w warstwie serwisowej
- Eksponuje REST API zgodne z wzorcem mobile-inspector
- Ma stronę frontend z prezentacją zabezpieczeń governance
- Przechodzi przez pełny cykl W14 via `execute_demo()`

Cel operatorski: "jeden klik — pełne demo działania W14 od chartera do release".

---

## 2. Architektura

```
testing/demo_projects/
  manifests/
    01-mobile_field_inspector.yaml
    02-public_project_showcase.yaml
    03-factory_automation_panel.yaml
    04-operator_crm.yaml
    05-funding_pipeline_tracker.yaml
    06-skills_marketplace.yaml
  orchestrator.py         DemoProjectOrchestrator + execute_demo
  __init__.py             eksport: DemoProjectOrchestrator, execute_demo

sylion/demo/
  mobile_field_inspector/    models.py + store.py + service.py
  public_project_showcase/   models.py + store.py + service.py
  factory_automation_panel/  models.py + store.py + service.py
  operator_crm/              models.py + store.py + service.py
  funding_pipeline_tracker/  models.py + store.py + service.py
  skills_marketplace/        models.py + store.py + service.py

sylion/api/
  demo_mobile_inspector_routes.py   11 endpoints
  demo_portal_routes.py              8 endpoints
  demo_factory_routes.py             9 endpoints
  demo_crm_routes.py                 8 endpoints
  demo_funding_routes.py             6 endpoints
  demo_marketplace_routes.py         9 endpoints

sylion-frontend/.../demo/
  mobile-inspector/page.tsx
  portal/page.tsx
  factory/page.tsx
  crm/page.tsx
  funding/page.tsx
  marketplace/page.tsx
```

---

## 3. Konfiguracja

| Zmienna | Default | Opis |
|---------|---------|------|
| `SYLION_W14_DB` | `sylion_aeis.db` | Baza OntologyStore używana przez execute_demo |
| `SYLION_DEMO_DB` | `:memory:` per demo | Baza SQLite per demo serwis (można wskazać plik) |

Prefixes routerów REST:

| Demo | Prefix | Tag |
|------|--------|-----|
| Mobile Field Inspector | `/api/v1/demo/mobile-inspector` | `demo-mobile-inspector` |
| Public Portal | `/api/v1/demo/portal` | `demo-portal` |
| Factory Automation | `/api/v1/demo/factory` | `demo-factory` |
| Operator CRM | `/api/v1/demo/crm` | `demo-crm` |
| Funding Tracker | `/api/v1/demo/funding` | `demo-funding` |
| Skills Marketplace | `/api/v1/demo/marketplace` | `demo-marketplace` |

---

## 4. 6 manifestów projektów demo

### Przegląd

| # | Projekt | Typ | D-level | Domeny | Wymagane persony |
|---|---------|-----|---------|--------|-----------------|
| 01 | Mobile Field Inspector | mobile-app | D4 | field_operations | beginner, mobile_first, incident_responder |
| 02 | Public Project Showcase | web-portal | D3 | public_facing | viewer_curious, auditor |
| 03 | Factory Automation HMI | industrial-iot | D5 | industrial_safety | production_engineer\*, overloaded, incident_responder |
| 04 | Operator CRM | crm | D4 | data_management | power_user, auditor, legal_compliance_officer\* |
| 05 | Funding Pipeline Tracker | fintech-grants | D4 | external_action | funding_hunter\*, governance_officer\*, auditor |
| 06 | AEIS Skills Marketplace | marketplace | D5 | supply_chain | admin_overconfident, viewer_curious, incident_responder |

\* persona spoza 8 startowych — wymaga rozszerzenia katalogu person w pełnej implementacji.

### Manifest 01 — Mobile Field Inspector (D4)

```yaml
project_id: demo_01_mobile_field_inspector
target_d_level: D4
domain_specific_human_errors:
  - stale_data_action: submit_after_lost_connectivity_during_approval (D3)
  - wrong_context: gps_spoofing_attempt (D4)
  - premature_action: photo_evidence_corruption_unverified (D3)
required_test_classes: [T0, T2, T3, T4, T5, T6, T7, T9, T15]
release_blockers:
  - GPS coordinates outside expected range
  - Photo upload without signature
  - Offline action without conflict resolution
expected_modules: 8 / api_endpoints: 12 / ui_pages: 5
```

### Manifest 02 — Public Project Showcase (D3)

```yaml
project_id: demo_02_public_project_showcase
target_d_level: D3
domain_specific_human_errors:
  - permission_overreach: viewer_attempts_edit_project_data (D3)
  - bypass_attempt: scrape_internal_endpoints_via_seo_bot (D3)
  - permission_overreach: idor_attempt_with_other_project_id (D4)
required_test_classes: [T0, T2, T3, T5, T6, T8, T10, T15]
release_blockers:
  - Any IDOR vulnerability
  - Missing rate limiting on contact form
  - PII exposure in public endpoints
```

### Manifest 03 — Factory Automation HMI (D5)

```yaml
project_id: demo_03_factory_automation_panel
target_d_level: D5
domain_specific_human_errors:
  - premature_action: wrong_cabinet_upload_no_id_verification (D5)
  - gate_skip: missing_emergency_stop_verification (D5)
  - authority_abuse: unsafe_override_safety_interlock (D5)
required_test_classes: [T0, T2, T4, T5, T6, T7, T8, T9, T10, T11, T13, T15]
release_blockers:
  - Backup not verified before upload
  - Emergency stop not tested
  - Safety interlock override without D5 approval
  - Any P0/P1 finding
success_criteria:
  - Council session D5 completed (full Council + multi-sig)
  - All 3 sentinels (cost+security+safety) pass
  - Minimum 7 lessons_learned (D5 wymaga więcej)
```

### Manifest 04 — Operator CRM (D4)

```yaml
project_id: demo_04_operator_crm
target_d_level: D4
domain_specific_human_errors:
  - permission_overreach: gdpr_delete_request_vs_audit_retention_policy (D4)
  - wrong_context: contact_merge_creating_data_loss (D3)
  - authority_abuse: operator_self_grants_admin_role (D4)
release_blockers:
  - PII exposure in any endpoint
  - GDPR right-to-be-forgotten not enforceable
  - Audit log write failure (must be append-only)
  - Role escalation without approval workflow
```

### Manifest 05 — Funding Pipeline Tracker (D4)

```yaml
project_id: demo_05_funding_pipeline_tracker
target_d_level: D4
domain: external_action
domain_specific_human_errors:
  - premature_action: submit_after_grant_deadline_due_to_clock_drift (D4)
  - stale_data_action: expired_signature_used_in_external_submit (D4)
  - premature_action: oversized_attachment_silent_truncation (D3)
release_blockers:
  - Submit after deadline (no clock validation)
  - External submit without external_action gate
  - Signature validation bypass
```

### Manifest 06 — AEIS Skills Marketplace (D5)

```yaml
project_id: demo_06_skills_marketplace
target_d_level: D5
domain: supply_chain
domain_specific_human_errors:
  - bypass_attempt: malicious_skill_upload_without_static_scan (D5)
  - premature_action: approve_runaway_cost_skill_without_budget_check (D5)
  - permission_overreach: dependency_confusion_attack_via_typo_squat (D5)
release_blockers:
  - Skill upload without static security scan
  - Skill execution without sandbox isolation
  - Council session not D5-complete
success_criteria:
  - Council session D5 completed (full Council + multi-sig + sentinels)
  - Cost Sentinel + Security Sentinel both zero open alerts
  - Minimum 8 lessons_learned
```

---

## 5. DemoProjectOrchestrator + execute_demo

### DemoProjectOrchestrator

```python
from sylion.aeis.testing.demo_projects import DemoProjectOrchestrator

orc = DemoProjectOrchestrator()
orc.load_all()  # ładuje 6 manifestów z katalogu manifests/

print(orc.list())           # list[DemoProjectManifest]
print(orc.coverage())       # dict: d_level distribution, type distribution
errors = orc.validate_all() # list[str] — błędy walidacji manifest
```

### execute_demo — 6-krokowy lifecycle W14

```python
from sylion.aeis.testing.demo_projects import execute_demo
from sylion.aeis.testing.ontology import OntologyStore
from sylion.core.event_bus import SylionEventBus

ontology = OntologyStore(db_path="sylion_aeis.db")
event_bus = SylionEventBus()

result = execute_demo("demo_01_mobile_field_inspector", ontology, event_bus)
```

Funkcja przechodzi przez pełny lifecycle W14 dla projektu:

| Krok | Akcja | Szczegóły |
|------|-------|-----------|
| 1 | Charter | Utwórz → propose → approve (z HG ticket ref + Council session ref) |
| 2 | Findings injection | 3 domainowe findingi z manifestu, severity per D-level |
| 3 | Repair lifecycle | Per finding: REPRODUCED → CLASSIFIED → ... → CLOSED + RepairAttempt |
| 4 | ReleaseCandidate | Promote do gate_status=RELEASE_CANDIDATE |
| 5 | ReleaseReadinessReport | Generuj z 12+6 checklistą (wszystkie punkty satisfied) |
| 6 | Memory | Zapisz lesson + anti-pattern do TestingMemoryStore |

Format zwracanego dict:

```python
{
    "status": "READY_FOR_PRODUCTION",
    "project_id": "demo_01_mobile_field_inspector",
    "manifest_name": "Mobile Field Inspector",
    "steps": ["charter_created", "findings_injected", "repairs_completed",
              "release_candidate_promoted", "report_generated", "lesson_recorded"],
    "total_steps": 6
}
```

### Pokrycie D-level i typów

```python
coverage = orc.coverage()
# {
#   "d_level": {"D3": 1, "D4": 3, "D5": 2},
#   "type": {
#     "mobile-app": 1, "web-portal": 1, "industrial-iot": 1,
#     "crm": 1, "fintech-grants": 1, "marketplace": 1
#   }
# }
```

---

## 6. Backend demo — implementacje domenowe

Każda implementacja backendowa ma wzorzec `models.py + store.py + service.py` z prawdziwymi
zabezpieczeniami W14 w warstwie serwisowej.

### Demo 01 — Mobile Field Inspector

**Lokalizacja**: `sylion/demo/mobile_field_inspector/`

Modele (5 dataclasses z walidatorami):

| Model | Kluczowe walidacje |
|-------|-------------------|
| `GpsCoord` | lat/lon range, accuracy 0–1000m |
| `PhotoEvidence` | sha256 64-char, rozmiar 1KB–25MB |
| `SignatureEvidence` | signer wymagany, data ≥ 32 znaków |
| `FieldInspection` | revision counter (multi-tab guard) |
| `OfflineQueueEntry` | attempt count + last_error |

Zabezpieczenia W14 w `InspectorService`:

- Walidacja statusów przejść (TRANSITIONS dict)
- Blokada: nie można oznaczyć `ready_to_sync` bez photo+sig+gps
- GPS spoofing: drift > 5km flagowany (Finding auto-created)
- GPS accuracy > 200m flagowany
- Optimistic concurrency: `update_inspection` rzuca `RuntimeError` przy revision mismatch (409 Conflict)

### Demo 02 — Public Project Showcase (D3)

**Lokalizacja**: `sylion/demo/public_project_showcase/`

Zabezpieczenia:
- RBAC enforcement: 4 role (public/authenticated/owner/admin)
- IDOR guard: `PortalStore.update_project` wymaga `expected_owner` match
- Rate-limit: max 3 kontakty per IP per 60s (anti-spam)

### Demo 03 — Factory Automation HMI (D5)

**Lokalizacja**: `sylion/demo/factory_automation_panel/`

D5 safety chain przed uploadem programu (5-krokowa):

| Krok | Walidacja |
|------|-----------|
| 1 | Serial szafy PLC musi pasować do IO mapping (anti wrong-cabinet) |
| 2 | Backup < 24h |
| 3 | Test e-stop < 7 dni, response time < 500ms |
| 4 | Dry-run musi przejść |
| 5 | (override safety interlock) WYMAGA Council session (D5 hard rule) |

### Demo 04 — Operator CRM (D4)

**Lokalizacja**: `sylion/demo/operator_crm/`

Zabezpieczenia:
- GDPR delete: PII redacted in-place, rekord zachowany (audit retention)
- GDPR delete WYMAGA `hg_ticket_id` (D4 governance gate)
- Contact merge: detekcja konfliktów (email/phone/role mismatches)
- Role escalation do VIP wymaga admin actor + HG ticket
- Audit log: PII redacted przy zapisie, append-only, nigdy nie usuwany przez GDPR

### Demo 05 — Funding Pipeline Tracker (D4)

**Lokalizacja**: `sylion/demo/funding_pipeline_tracker/`

Zabezpieczenia:
- Per-attachment hard cap: 20 MB (brak cichego truncation, HTTP 413)
- Per-application total cap: 100 MB
- External submit WYMAGA `hg_ticket_id` (D4 external_action gate)
- Hard guards przed submitem:
  - Deadline nie minął (clock check, nie można submit po expiry)
  - Minimum jeden podpis z ważnym (nie przeterminowanym) certyfikatem
  - Podpis podpisany w ciągu 30 dni
- Nieudane submity zapisywane jako `SubmissionAttempt` do audytu

### Demo 06 — AEIS Skills Marketplace (D5)

**Lokalizacja**: `sylion/demo/skills_marketplace/`

Zabezpieczenia:
- Anti-typosquat: unikalność name+version, exact-match search
- Dependency declarations WYMAGAJĄ dokładnego pin wersji (bez ranges)
- Static security scan OBOWIĄZKOWY przed review
  - high/critical findings → auto status=`scan_failed` (nie można approve)
- Approval WYMAGA `council_session_id` (D5 hard rule)
- Per-skill cost budget hard cap (anti runaway-cost)

---

## 7. REST endpoints — 51 endpointów łącznie

### Demo 01 — Mobile Inspector (11 endpoints)

| Metoda | URL | Opis |
|--------|-----|------|
| GET | `/health` | Liveness check |
| GET | `/inspections` | Lista inspekcji |
| POST | `/inspections` | Utwórz inspekcję |
| GET | `/inspections/{id}` | Pobierz inspekcję |
| POST | `/inspections/{id}/transition` | Zmień status |
| POST | `/inspections/{id}/photo` | Dodaj zdjęcie |
| POST | `/inspections/{id}/signature` | Dodaj podpis |
| PATCH | `/inspections/{id}/gps` | Aktualizuj GPS |
| GET | `/queue` | Lista kolejki offline |
| POST | `/queue` | Dodaj do kolejki |
| POST | `/queue/sync-all` | Synchronizuj całą kolejkę |

### Demo 02 — Portal (8 endpoints, prefix `/api/v1/demo/portal`)

| Metoda | URL | Opis |
|--------|-----|------|
| GET | `/health` | Liveness |
| GET | `/projects` | Lista projektów (paginacja) |
| POST | `/projects` | Utwórz projekt (authenticated) |
| GET | `/projects/{id}` | Pobierz projekt |
| PATCH | `/projects/{id}` | Aktualizuj (IDOR guard: expected_owner) |
| POST | `/contact` | Wyślij wiadomość (rate-limit 3/60s) |
| GET | `/public/stats` | Publiczne statystyki |
| GET | `/rbac-roles` | Lista ról (demo) |

### Demo 03 — Factory (9 endpoints, prefix `/api/v1/demo/factory`)

| Metoda | URL | Opis |
|--------|-----|------|
| GET | `/health` | Liveness + safety chain status |
| GET | `/cabinets` | Lista szaf PLC |
| POST | `/upload` | Upload programu (5-krokowa safety chain, HTTP 422 przy awarii) |
| POST | `/backup` | Wykonaj backup |
| POST | `/estop-test` | Przeprowadź test e-stop |
| POST | `/dry-run` | Suchy przebieg |
| POST | `/interlock-override` | Override (WYMAGA council_session_id, HTTP 403 bez) |
| GET | `/audit` | Audit trail akcji |
| GET | `/safety-chain-status` | Status wszystkich 5 kroków chain |

### Demo 04 — CRM (8 endpoints, prefix `/api/v1/demo/crm`)

| Metoda | URL | Opis |
|--------|-----|------|
| GET | `/health` | Liveness |
| GET | `/contacts` | Lista kontaktów |
| POST | `/contacts` | Utwórz kontakt |
| DELETE | `/contacts/{id}` | GDPR delete (WYMAGA hg_ticket_id, HTTP 403 bez) |
| POST | `/contacts/merge` | Scal kontakty (detekcja konfliktów) |
| PATCH | `/contacts/{id}/role` | Zmień rolę (VIP wymaga admin + HG) |
| GET | `/audit` | Audit trail (PII redacted) |
| GET | `/anti-patterns` | Demo aktywnych anty-wzorców |

### Demo 05 — Funding (6 endpoints, prefix `/api/v1/demo/funding`)

| Metoda | URL | Opis |
|--------|-----|------|
| GET | `/health` | Liveness |
| POST | `/applications` | Utwórz aplikację grantową |
| POST | `/applications/{id}/attachments` | Dodaj załącznik (20MB limit per plik, 413) |
| POST | `/applications/{id}/sign` | Podpisz aplikację |
| POST | `/applications/{id}/submit` | Submit (WYMAGA hg_ticket_id + deadline + sig freshness) |
| GET | `/applications/{id}/audit` | Historia prób i podpisów |

### Demo 06 — Marketplace (9 endpoints, prefix `/api/v1/demo/marketplace`)

| Metoda | URL | Opis |
|--------|-----|------|
| GET | `/health` | Liveness |
| GET | `/skills` | Lista skilli |
| POST | `/skills` | Upload (anti-typosquat, exact version pin) |
| GET | `/skills/{id}` | Pobierz skill |
| POST | `/skills/{id}/scan` | Uruchom static scan |
| POST | `/skills/{id}/approve` | Zatwierdź (WYMAGA council_session_id, D5) |
| POST | `/skills/{id}/can-execute` | Pre-flight cost guard |
| GET | `/skills/{id}/dependencies` | Lista dependencies |
| GET | `/anti-patterns` | Demo wykrytych anty-wzorców |

### Mapowanie kodów HTTP

Wszystkie routery stosują spójny mapping:

| Kod | Znaczenie |
|-----|-----------|
| 400 | Błąd walidacji (`ValueError`) |
| 403 | Brak uprawnień (`PermissionError`) |
| 404 | Nie znaleziono |
| 409 | Konflikt (race condition, rate-limit, merge conflict) |
| 413 | Payload za duży (attachment cap) |
| 422 | Unprocessable — nieudana safety chain guard |

---

## 8. Frontend — 6 stron demo

Wszystkie strony w `src/sylion-frontend/src/app/(app)/demo/`.
Wzorzec: `useHealth()` → `backendLive` → blokada przycisków destruktywnych gdy `!backendLive`.

### `/demo/mobile-inspector`

- Status indicator + badge live/mock
- Przycisk "Create demo inspection" (pełny lifecycle: gps + photo + sig + queue)
- Przycisk "Sync all" (kolejka offline)
- Lista inspekcji z badges statusów + revision counter + znacznik GPS
- Panel kolejki z retry count + last_error
- Karta podsumowania zabezpieczeń W14

### `/demo/portal`

- Ikona Globe, lista projektów z view counts
- Demo rate-limit (HTTP 429 oczekiwane po 3 kontaktach)
- Przycisk adversarial: "IDOR attempt" (oczekiwane 403)

### `/demo/factory`

- Ikona Factory + badge D5 SAFETY
- 5-krokowy happy path (każdy krok osobny przycisk)
- Adversarial: "skip backup" (oczekiwane HTTP 422)
- Timestamped activity log

### `/demo/crm`

- Ikona Users, lista kontaktów z badges roli + statusu
- GDPR delete z potwierdzeniem (confirm flow)
- Przyciski adversarial:
  - "GDPR bez HG" (oczekiwane 403)
  - "VIP bez admin" (oczekiwane 403)

### `/demo/funding`

- Ikona DollarSign, pełny flow (create + attach + sign + submit)
- Adversarial:
  - "no HG" przy submit (oczekiwane 403)
  - "oversized 25MB" (oczekiwane 413)
- Activity log z timestampami

### `/demo/marketplace`

- Ikona Package + badge D5
- Happy path: clean upload → scan clean → approve
- Demo malicious: critical finding → auto scan_failed → approve rzuca 422
- Adversarial: "approve bez council" (oczekiwane 403)
- Karta wyjaśniająca ochrony W14

Wyświetlanie błędów: kod HTTP widoczny w UI jako `BLOCKED 403/422/429 (correct)` —
operator widzi, że system zachowuje się zgodnie z oczekiwaniami.

---

## 9. Testy — 151 testów łącznie

### Rozkład

| Commit | Zakres | Testy | Skumulowane |
|--------|--------|-------|-------------|
| `3fd53a06` | Manifesty + orchestrator | 17 | 431 (E0-E11 manifesty) |
| `df31e83b` | execute_demo lifecycle | 4 | 435 |
| `c5e509f0` | Mobile Field Inspector full | 38 | 473 |
| `3e6c9dbd` | 5 remaining demos | 92 | 565 |

### Mobile Field Inspector — 38 testów (c5e509f0)

17 testów modeli: walidatory GpsCoord (range, accuracy), PhotoEvidence (sha256, size),
SignatureEvidence (signer, length), FieldInspection (revision), OfflineQueueEntry.

13 testów serwisowych: status transitions valid/invalid, multi-tab revision conflict,
offline queue retry, sync_all batch.

8 testów adversarialnych pokrywających 3 domenowe błędy z manifestu:
- `gps_spoofing_attempt` — drift detection + range validation
- `photo_evidence_corruption_unverified` — sha256+size enforcement
- `lost_connectivity_during_approval` — revision conflict + inspection vanish handling

### 5 pozostałych demo — 92 testy (3e6c9dbd)

| Demo | Testy | Kluczowe przypadki |
|------|-------|-------------------|
| portal | 22 | RBAC roles, IDOR guard, rate-limit 3/60s, SEO scrape |
| factory | 14 | D5 safety chain full, estop validation, interlock override blokada |
| crm | 20 | GDPR PII redaction, audit append-only, VIP escalation |
| funding | 16 | 20MB cap, deadline enforcement, signature freshness 30d |
| marketplace | 22 | Anti-typosquat, static scan block, council D5 requirement |

### Manifest + orchestrator — 17 + 4 testy

17 testów manifestów: ładowanie 6 projektów, walidacja, rozkład D-level (D3×1 + D4×3 + D5×2),
pokrycie typów (6 różnych), per-projekt security/governance/chaos test classes.

4 testy execute_demo: single mobile project, unknown project error, all 6 reach
READY_FOR_PRODUCTION, D5 strict checks pass.

---

## 10. Weryfikacja

```bash
cd src/sylion-pipeline

# Testy manifestów i orchestratora
python -m pytest tests/aeis/testing/test_demo_projects.py -v

# Testy Mobile Field Inspector
python -m pytest tests/demo/mobile_field_inspector/ -v

# Testy wszystkich 6 demos
python -m pytest tests/demo/ -v

# Pełne demo lifecycle (wszystkie 6 projektów)
python -c "
from sylion.aeis.testing.demo_projects import DemoProjectOrchestrator, execute_demo
from sylion.aeis.testing.ontology import OntologyStore

orc = DemoProjectOrchestrator()
orc.load_all()
ontology = OntologyStore(db_path=':memory:')

for manifest in orc.list():
    r = execute_demo(manifest.project_id, ontology, event_bus=None)
    print(manifest.project_id, r['status'])
"
# Oczekiwany wynik: wszystkie 6 → READY_FOR_PRODUCTION

# Sprawdź endpoints REST po restarcie backendu
curl http://127.0.0.1:8010/api/v1/demo/mobile-inspector/health
curl http://127.0.0.1:8010/api/v1/demo/portal/health
curl http://127.0.0.1:8010/api/v1/demo/factory/health
curl http://127.0.0.1:8010/api/v1/demo/crm/health
curl http://127.0.0.1:8010/api/v1/demo/funding/health
curl http://127.0.0.1:8010/api/v1/demo/marketplace/health

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/demo/mobile-inspector
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/demo/portal
# Oczekiwane: 200
```

---

## 11. Rozwiązywanie problemów

### `execute_demo` rzuca `ValueError: unknown project`

Sprawdź, że `DemoProjectOrchestrator.load_all()` zostało wywołane przed `execute_demo`.
`project_id` musi dokładnie pasować do wartości z manifestu YAML (np.
`demo_01_mobile_field_inspector`).

### HTTP 409 Conflict przy update inspekcji

Revision mismatch — dwa requesty próbują zaktualizować ten sam rekord. Backend broni przed
wyścigiem. W teście: odśwież inspekcję (`GET /{id}`) i użyj aktualnego `revision`.

### HTTP 422 przy factory upload mimo poprawnych danych

Sprawdź wszystkie 5 kroków safety chain. `/safety-chain-status` zwraca stan każdego kroku.
Najczęstsza przyczyna: brak backupu (wymaga `/backup` wywołanego < 24h temu)
lub niezdany test e-stop (wymaga `/estop-test` < 7 dni temu).

### Marketplace approval 403

Approval D5 wymaga `council_session_id` w body requestu. Przejdź przez `/scan` (clean)
i przekaż `council_session_id` z aktywnej sesji Rady do `/approve`.

### Demo strony nie łączą się z backendem

Sprawdź `backendLive` — gdy false, destruktywne przyciski są wyłączone. Backend wymaga
restartu po dodaniu nowych routerów (`4fcc42ee`). Po restarcie `/api/v1/demo/*/health`
powinny zwracać 200.

---

## 12. Cross-references

- [`46_w14_ontology.md`](./46_w14_ontology.md) — OntologyStore, TestCharter, Finding,
  ReleaseCandidate, ReleaseReadinessReport (używane przez execute_demo)
- [`47_w14_charter_finding.md`](./47_w14_charter_finding.md) — CharterStore i FindingStore
  używane przez execute_demo (krok 1 i 2)
- [`48_w14_human_lab.md`](./48_w14_human_lab.md) — persony deklarowane w manifestach
- [`49_w14_test_center.md`](./49_w14_test_center.md) — TestingMemoryStore.record_lesson()
  wywoływane w kroku 6 execute_demo
- [`modules/31_d_ladder_complete.md`](./31_d_ladder_complete.md) — D-level per projekt
  determinuje blokery release i wymagania Council
- [`modules/33_council_hybrid.md`](./33_council_hybrid.md) — D5 wymaga pełnej sesji Rady
  (factory + marketplace); council_session_id wymagany w approve endpoints
