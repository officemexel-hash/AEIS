# PATCH FAZA 32 — Tmux Sessions + Docker Sandboxing + Git Worktrees

> **Source**: cherry-pick z Agent of Empires (A1, A2, A3)
> **Target**: `32_33_execution_part1.md` sekcja 32 (Build Initialization)
> **Severity**: HIGH (fundamental zmiana w worker spawning)
> **Apply**: zastąpić sekcję "Worker spawning" + dodać nowe sekcje

---

## Problem

Faza 32 spawning workerów dziś:
- **Workers as Python processes** bound do AEIS backend
- **Single working tree** — workers must coordinate branch switches
- **No isolation** — workers mają full operator filesystem access
- **Lost on disconnect** — laptop close = state loss

## Replace section "Worker Spawning"

### OLD (incorrect)

```
Worker spawning:
  For each planned worker:
    Spawn Python process z anthropic SDK
    Workdir: workspace/worker_<id>/
    Status: bound do AEIS backend
    Lifecycle: dies if AEIS dies
```

### NEW (correct, z A1+A2+A3)

```
## 32.X. Modern Worker Spawning (A1+A2+A3)

### Architecture
Każdy worker = **3 isolated layers**:
  1. Tmux session (persistent, A1)
  2. Git worktree (isolated branch, A2)
  3. Docker container (sandboxed, A3)

### Setup workflow

For każdy planned worker:

  Step 1 — Create git worktree (A2):
    git worktree add ${PROJECT_ROOT}/code/worktrees/worker_${id}_${layer} \
                     build/${layer_name}
    
    Result: isolated working tree dla worker
    No conflicts z innymi workers

  Step 2 — Create tmux session (A1):
    tmux new-session -d \
         -s aeis_worker_${id}_${project_id} \
         -c ${WORKTREE_PATH}
    
    Result: persistent tmux session
    Survives laptop close, network drops, crashes

  Step 3 — Spawn Docker container (A3):
    docker run -d \
      --name aeis_worker_${id}_${project_id} \
      --memory=4g --cpus=2 \
      --read-only \
      --tmpfs /tmp \
      --cap-drop=ALL \
      --cap-add=DAC_OVERRIDE \
      --network=aeis_bridge_${project_id} \
      -v ${WORKTREE_PATH}:/workspace \
      -v ${SHARED_AUTH}:/secrets:ro \
      -v ${COORDINATION}:/coordination \
      aeis/worker:latest \
      python -m aeis.worker --id=${id}
    
    Result: isolated container z worker process

  Step 4 — Connect tmux do Docker (orchestration):
    tmux send-keys -t aeis_worker_${id}_${project_id} \
                   "docker exec -it aeis_worker_${id}_${project_id} bash" Enter
    
    Result: tmux session can monitor/control Docker container

### Audit chain entries

  worktree_lifecycle.jsonl:
    worktree_created: timestamp, worker_id, branch, path
  
  session_lifecycle.jsonl:
    session_created: timestamp, worker_id, tmux_session_name
  
  docker_isolation.jsonl:
    container_created: timestamp, worker_id, image, resource_limits

### State tracking

State machine per worker:
  SPAWNED → tmux session created
  CONTAINER_STARTING → Docker container starting
  RUNNING → worker process active
  WAITING → idle, awaiting tasks
  DETACHED → operator closed AEIS, all 3 layers persist
  ATTACHED → operator interactively viewing
  KILLED → explicit termination, all 3 layers cleanup
  CRASHED → unexpected death, auto-recover

### Pre-flight checks (NEW)

Przed spawning workers, walidacja:
  ✓ tmux >= 3.3 installed
  ✓ Docker available + running
  ✓ Disk space > 2× project_size (worktrees overhead)
  ✓ Memory > workers × 4GB (Docker limit)
  ✓ Anthropic API key configured
  ✓ Network whitelist policy active (z W19)
  ✓ Coordination directory exists w writable

If any fails:
  AdvisorCard emitted z specific issue
  Operator decision: install missing, retry, or fallback

### Reconnection workflow (NEW)

Operator reopens AEIS po long absence:
  
  Step 1 — Discover persistent state:
    tmux ls | grep aeis_worker_     # List active sessions
    docker ps --filter name=aeis_worker_  # List containers
    git worktree list                # List worktrees
  
  Step 2 — Reconnect:
    For każda found session:
      AEIS backend re-attach via tmux capture-pane
      Restore worker state from tmux history
      Reconnect to Docker container
      Resume coordination
  
  Step 3 — Display do operator:
    "Found 4 active sessions z poprzedniej pracy"
    Per session: status, last activity, current task
    Operator decision: continue / inspect / kill

### Mobile reconnect (NEW)

Operator switches z laptop do phone:
  Phone connects via Tailscale (lokalne) lub PWA (W12+A5)
  Backend continues running na operator's machine
  Operator sees same active sessions z phone
  State 100% preserved
  No lost work
```

## Add new section 32.Y — Network Whitelist (W19 integration)

```
## 32.Y. Network Whitelist Policy

Per-project network policy enforced via Docker bridge + iptables:

allowed_destinations:
  api.anthropic.com:443
  api.openai.com:443 (if multi-provider)
  github.com:443
  github.com:22 (SSH)
  registry.npmjs.org:443
  pypi.org:443
  
  # Per-customer specific:
  api.stripe.com:443 (jeśli Stripe in scope)
  ksef.mf.gov.pl:443 (jeśli KSeF in scope)
  api.mailjet.com:443 (jeśli Mailjet in scope)

blocked_default:
  ALL other endpoints

Policy enforcement:
  Docker bridge network: aeis_bridge_${project_id}
  iptables rules dropping non-whitelisted traffic
  Audit chain: network_block.jsonl

Pattern detection:
  Repeat blocked attempts → potential malicious behavior
  AdvisorCard emit z worker review request
```

## Customer Y CRM example

```
Setup w faza 32:
  
  Worker 1 (Backend specialist):
    worktrees/worker_1_layer_2/  ← Layer 2 integrations
    tmux session: aeis_worker_1_customer_y_crm
    Docker container: aeis_worker_1 (4GB RAM, 2 CPU)
    Network: anthropic + github + pypi + stripe + ksef
  
  Worker 2 (Frontend specialist):
    worktrees/worker_2_layer_4/  ← Layer 4 frontend
    tmux session: aeis_worker_2_customer_y_crm
    Docker container: aeis_worker_2 (4GB RAM, 2 CPU)
    Network: anthropic + github + npmjs (NO stripe direct)

Setup time: ~45 sec (parallel spawning)
Disk usage: ~150MB extra (worktrees)
Memory usage: ~8GB (2 containers × 4GB)

Robert zamyka laptop o 23:00:
  Tmux sessions persist
  Docker containers persist
  Workers continue idle (waiting dla resume)
  
Robert wraca rano 8:00:
  AEIS backend startup
  Auto-reconnect do tmux + Docker
  Workers resume z exact state
  No data loss
  No re-execution of completed work
```

## Audit chain

Łączny audit chain dla faza 32:
  worktree_lifecycle.jsonl: 8 entries (per worktree)
  session_lifecycle.jsonl: 2 entries (per worker)  
  docker_isolation.jsonl: 2 entries (per container)
  network_policy.jsonl: 1 entry (whitelist applied)
  workflow_engine.jsonl: 5 entries (orchestration)

## Co operator rozumie po patchu

1. **Workers są persistent** — laptop close nie psuje wszystkiego
2. **Workers są isolated** — Docker chroni przed destructive operations
3. **Workers truly parallel** — git worktrees eliminują merge conflicts
4. **Mobile reconnect możliwy** — true cross-device workflow
5. **Network policy enforced** — data sovereignty + GDPR compliance
6. **Reconnection seamless** — zero data loss on disconnects
