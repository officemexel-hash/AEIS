# CODEX CHECKLIST - Top 10 runtime patches

Data: 2026-05-02

Zakres analizowanych plikow:

- AEIS_ARCHITECTURE_DIAGRAMS.md
- PATCH_FAZA_28_PROFILE_6.md
- PATCH_FAZA_32_TMUX_DOCKER_WORKTREES.md
- PATCH_FAZA_35_BUILD_CRITIC_PROMPT_SPLITTING.md
- POC_PLAN_TMUX_A1.md

## Checklista wdrozenia

### Faza 28 - Profile 6 Burst Mode

- [x] Dodac profile_6 do backendowego katalogu resource profiles.
- [x] Oznaczyc profile_6 jako per-phase only, nie jako profil calego masterplanu.
- [x] Dodac limity: 60 workerow, 30 minut, 2 bursty dziennie, safety margin.
- [x] Dodac polityke: operator gate + subscription advisor + cost guard.
- [x] Zablokowac przypadkowy wybor profile_6 jako pelnego profilu build.
- [ ] Dodac osobny endpoint aktywacji burst dla faz 22/31/35.

### Faza 32 - Tmux + Worktrees + Docker

- [x] Dodac plan A1/A2/A3 do build initialization.
- [x] Dodac runtime capability check dla git/session backend/docker.
- [x] Dostosowac A1 do Windows: backend `windows_process_group` zamiast twardego wymagania tmux.
- [x] Dodac planned sessions, worktrees, containers per worker.
- [x] Dodac network whitelist policy jako plan i audit target.
- [x] Zablokowac live spawn bez gotowego runtime i decyzji operatora.
- [x] Uruchomic prawdziwe persistent sessions na Windows: `windows_process_group` smoke test 2 workerow z dashboardu, heartbeat logs, stop przez UI, `running: 0` po zatrzymaniu.
- [ ] Uruchomic prawdziwe Docker containers po potwierdzeniu polityki zasobow.

### Faza 35 - Build Critic + Prompt Splitting

- [x] Dodac Build Critic continuous jako runtime policy fazy 35.
- [x] Dodac jego cadence, budzet, domenowe checki i eskalacje do Human Gate.
- [x] Dodac Prompt Splitting z katami poznawczymi i CRITIC/SYNTHESIZER.
- [x] Dodac audit events dla build critic i prompt splitting policy.
- [ ] Podlaczyc Build Critic do realnych diffow commitow workerow.
- [ ] Podlaczyc Prompt Splitting do realnego generatora wariantow.

### Operator Monitor

- [x] Dodac widocznosc checklisty A1/A2/A3/M1/M2/M3 w dashboardzie operatora.
- [x] Pokazac, czy runtime jest gotowy, jaki session backend jest aktywny i czy Docker daemon dziala.
- [x] Przetlumaczyc widoczne statusy runtime na polski.
- [ ] Dodac akcje operatora "przygotuj runtime" po zaakceptowaniu srodowiska.

## Krytyczne decyzje operatora

Te punkty nie zostaly wykonane automatycznie, bo dotykaja realnego runtime lub moga uruchomic koszt:

- prawdziwy live spawn persistent sessions,
- prawdziwe Docker containers,
- prawdziwy Burst Mode 60 workerow,
- quota checks wobec subskrypcji/API,
- jakikolwiek zewnetrzny deployment lub provisioning.

## Decyzje wykonane samodzielnie przez Codex

- Profile 6 zostal dodany jako polityka planowania, ale z blokada przed uzyciem jako pelny profil masterplanu.
- Faza 32 dostala plan A1/A2/A3 i runtime capability check bez uruchamiania kosztow.
- Faza 35 dostala Build Critic i Prompt Splitting jako konfiguracje operacyjna i dowody w artefaktach.
- Operator Monitor dostal karte statusu runtime patches.
