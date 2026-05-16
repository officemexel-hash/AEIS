# AEIS API / UI COVERAGE MAP

**Data audytu:** 2026-04-24
**API:** 1170 unikalnych ścieżek OpenAPI, 250 schematów, 1433 route objects
**UI:** 48 stron Next.js + 30+ komponentów + legacy dashboard

---

## Mapowanie UI → API

| Strona UI | Endpointy API (prefix) | Status Coverage |
|---|---|---|
| /overview | /health, /api/v1/build-state | Pełna |
| /pipeline | /api/v1/pipeline/* | Pełna |
| /workers | /api/v1/workers/* | Pełna |
| /governance | /api/v1/governance/* (94 paths) | Pełna |
| /decisions | /api/v1/decision-snapshots/* | Pełna |
| /contracts | /api/v1/contracts/* | Pełna |
| /events | /api/v1/event-backbone/* | Pełna |
| /evidence | /api/v1/evidence-timeline/* | Pełna |
| /security-scan | /api/v1/security/* (51 paths) | Pełna |
| /secrets | /api/v1/secrets/* | Pełna |
| /skills | /api/v1/skills/* (27 paths) | Pełna |
| /quality | /api/v1/quality/* | Pełna |
| /rebuild | /api/v1/rebuild/* | Pełna |
| /monitoring | /api/v1/monitoring/* (73 paths) | Pełna |
| /observability | /api/v1/observability/* | Pełna |
| /book | /api/v1/memory/* | Pełna |
| /idea-vault | /api/v1/cognitive/ideas/* | Pełna |
| /funding | /api/v1/funding/* (41 paths) | UI podstawowy, API rozbudowane |
| /cellular | /api/v1/cellular/* (28 paths) | API istnieje, UI minimalne |
| /sdr | /api/v1/sdr/* (23 paths) | API istnieje, UI minimalne |
| /devices | /api/v1/devices/* | Pełna |
| /deploy | /api/v1/deployments/* | Pełna |
| /capacity | /api/v1/capacity/* | Pełna |
| /budget | /api/v1/model-budget/* | Pełna |
| /costs | /api/v1/efficiency/* | Pełna |
| /performance | /api/v1/efficiency/* | Pełna |
| /modules | /api/v1/core/*, /api/v1/manifests/* | Pełna |
| /settings | /api/v1/auth/*, /api/v1/roles/* | Pełna |
| /workspace | /api/v1/workspace/* (60 paths) | Pełna |
| /projects | /api/v1/projects/* (28 paths) | Pełna |
| /integrations | /api/v1/integration/* | Pełna |
| /anomalies | /api/v1/monitoring/anomalies/* | Pełna |
| /healing | /api/v1/self-healing/* | Pełna |
| /health | /api/v1/health/* | Pełna |
| /sla | /api/v1/sla/* | Pełna |
| /notifications | /api/v1/notification-engine/* | Pełna |
| /agents | /api/v1/agents/* | Pełna |
| /autonomy | /api/v1/aeis/* (48 paths) | Pełna |
| /autoscaler | /api/v1/workers/autoscaler/* | Pełna |
| /build-state | /api/v1/build-state | Pełna |
| /builds | /api/v1/core/builds/* | Pełna |
| /bundles | /api/v1/bundles/* | Pełna |
| /connectors | /api/v1/connectors/* | Pełna |
| /drift | /api/v1/integration/drift/* | Pełna |
| /environments | /api/v1/core/environments/* | Pełna |
| /evaluator | /api/v1/evaluator/* | Pełna |
| /gates | /api/v1/gates/* | Pełna |
| /golden-tests | /api/v1/golden-sets/* | Pełna |
| /lifecycle | /api/v1/lifecycle/* | Pełna |
| /risk | /api/v1/risk/* | Pełna |
| /roles | /api/v1/roles/* | Pełna |
| /vault | /api/v1/vault/* | Pełna |
| /versions | /api/v1/versions/* | Pełna |
| /vps | /api/v1/vps/* | Pełna |
| /container | /api/v1/container/* | Pełna |
| /brain | /api/v1/brain/* | Pełna |
| /adapters | /api/v1/adapters/* | Pełna |
| /profile-swaps | /api/v1/profile-swaps/* | Pełna |
| /rollback | /api/v1/rollback/* | Pełna |
| /hot-swap | /api/v1/hot-swap/* | Pełna |
| /execution-guard | /api/v1/execution-guard/* | Pełna |
| /audit-query | /api/v1/audit-query/* | Pełna |
| /knowledge | /api/v1/knowledge/* | Pełna |
| /model-registry | /api/v1/model-registry/* | Pełna |
| /regression | /api/v1/regression/* | Pełna |
| /hardened-audit | /api/v1/hardened-audit/* | Pełna |
| /snapshots | /api/v1/snapshots/* | Pełna |
| /self-explanation | /api/v1/self-explanation/* | Pełna |
| /ideas | /api/v1/ideas/* | Pełna |
| /audit | /api/v1/audit/* | Pełna |
| /auth | /api/v1/auth/* | Pełna |
| /phantom | /api/v1/phantom/* | Pełna |
| /healing-engine | /api/v1/healing-engine/* | Pełna |
| /audit-sink | /api/v1/audit-sink/* | Pełna |
| /feedback | /api/v1/feedback/* | Pełna |
| /ai-providers | /api/v1/ai-providers/* | Pełna |
| /evidence-spine | /api/v1/evidence-spine/* | Pełna |

---

## Niepokryte API (brak UI)

| Endpoint | Dlaczego brak UI |
|---|---|
| /api/v1/funding/* (41 paths) | UI /funding jest podstawowy, API ma pełne CRUD grantów |
| /api/v1/cellular/* (28 paths) | UI /cellular jest readonly / podstawowy |
| /api/v1/sdr/* (23 paths) | UI /sdr jest readonly / podstawowy |
| /ws/stats | WebSocket działa, ale brak dedykowanego panelu realtime |
| /api/v1/container/* | UI istnieje, ale brak operacji deploy / logs |
| /api/v1/vps/* | UI /vps jest podstawowy, brak provisioning wizard |
| /api/v1/brain/* | UI /brain jest eksperymentalny |
| /api/v1/model-budget/* | UI /budget pokazuje tylko agregaty |

---

## Niepokryte UI (brak API / stub)

| UI | Problem |
|---|---|
| Legacy dashboard (8421) | 22 pliki Python, duplikuje funkcje nowego frontendu |
| Marketing page | Statyczna, nie wymaga API |
| /workspace — CouncilPanel | UI istnieje, ale council_hybrid jest stub |
| /workspace — PipelineVisualization | UI istnieje, ale brak WebSocket streamu danych |
