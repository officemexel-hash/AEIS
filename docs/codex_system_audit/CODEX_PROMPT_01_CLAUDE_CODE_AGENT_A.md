# CODEX PROMPT 01 - CLAUDE CODE - AGENT A

Rola: Lead Architecture + Governance Spine  
Priorytet: najciezszy  
Ownership: tylko obszary przypisane A w `CODEX_PARALLEL_COORDINATION.md`

## Cel

Masz skonsolidowac glowny spine AEIS tak, aby `workspace -> project_mode` stal sie jednym, logicznie spojnym flow z jednym governance truth plane.

Nie buduj nowego systemu obok istniejacego runtime.

Masz naprawiac i konsolidowac:

- `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`
- `src/sylion-pipeline/sylion/project_mode/*`
- `src/sylion-pipeline/sylion/governance/*`
- `src/sylion-pipeline/sylion/api/governance_routes.py`
- `src/sylion-pipeline/sylion/api/aeis_routes.py`
- `src/sylion-pipeline/sylion/api/model_registry_routes.py`
- `src/sylion-pipeline/sylion/cognitive/model_registry.py`

## Najwazniejsze problemy do naprawy

1. Human Gate split brain
   Dzis istnieja:
   - `workspace/humangate/sessions`
   - globalne `gates/human/requests`
   - funding-local approvals

   Masz zrobic z tego jeden dominujacy governance truth plane, bez utraty dzialajacego flow `workspace`.

2. Council semantics drift
   Dzis:
   - `council_plan.enabled = false`
   - `active_size = 1`
   - a hierarchy nadal zaczyna sie od `planner_council`

   Masz uzgodnic council semantics z runtime.

3. Model registry vs workspace council-members split
   Dzis nie ma jednego truth plane dla skladu rady modeli.

4. Worker pool reconciliation bug
   `execution_plan` i utrwalony `worker_pool` potrafia sie rozjechac.

5. Autonomy controller detached state
   Warstwa autonomii istnieje, ale nie steruje realnym spine.

## Zakres wykonawczy

### A1. Unified governance ticket contract

Stworz w ownership scope jeden kanoniczny kontrakt decyzji/governance, z ktorego beda mogly korzystac:

- workspace
- globalne governance routes
- funding bridge od K
- mobile bridge od B

Nie tworz nowego top-level `core/`.
Osadz to w istniejacym namespace governance/project_mode/workspace.

### A2. Workspace -> Human Gate -> Project Mode truth consolidation

Masz doprowadzic do tego, aby:

- workspace approvals mialy wspolny audit trail z governance
- launch i kolejne decyzje mialy jednoznaczny decision trail
- state projektu, approvals i hierarchy byly spójne

### A3. Council truth consolidation

Masz:

- powiazac runtime council z model registry
- uporzadkowac `enabled`, `active_size`, `decision_hierarchy`
- zapewnic, ze runtime semantics nie klamia dokumentacji

### A4. Worker pool reconciliation

Napraw bug, w ktorym stare `worker_pool` przezywa zmiany `execution_plan`.

Warunek sukcesu:

- zatwierdzony execution plan i realny worker_pool musza odpowiadac sobie po launch

### A5. Autonomy integration

Masz doprowadzic do tego, aby autonomy stage nie byl tylko osobnym endpointem, ale mial realny wplyw na spine `workspace -> project_mode`.

### A6. Hook points dla B i K

Masz przygotowac miejsca wpiecia dla:

- skills/memory/mobile od B
- funding/observability bridge od K

Ale bez wchodzenia w ich ownership scope.

Zostaw im:

- stabilna semantyke
- czytelne miejsca integracji

## Twarde ograniczenia

- nie tworz nowego greenfieldowego `core` obchodzacego `workspace`
- nie przenos logiki poza istniejace namespace'y repo
- nie edytuj ownership scope B i K
- shared files reserved-for-D zostaw D

## Handoff do D

Oddajesz:

- naprawiony spine governance/workspace/project_mode
- liste miejsc integracji dla B i K
- liste testow, ktore uruchomiles
- liste ryzyk pozostalych dla D

## Done definition

- workspace i governance nie sa juz dwoma rozlaczonymi plane'ami decyzji
- council semantics sa spojne z runtime
- model registry i council membership maja jednoznaczny truth path
- worker pool reconciliation jest naprawione
- autonomy plane wplywa na realny flow
- nie zbudowales nowego rownoleglego spinu obok istniejacego
