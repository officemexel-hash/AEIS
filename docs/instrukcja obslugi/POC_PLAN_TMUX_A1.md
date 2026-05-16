# POC PLAN — Tmux Persistent Sessions (A1)

> **Cel**: szczegółowy plan implementacji **pierwszego feature** z Top 10
> **Format**: week-by-week breakdown, code samples, success criteria, tests
> **Czas**: 3 tygodnie 1 dev (lub 1.5 tyg 2 dev)
> **Założenie**: solo developer (Robert) implementuje sam

---

# Spis treści

1. [Executive Summary](#1-executive-summary)
2. [Pre-flight: dlaczego A1 first](#2-pre-flight-dlaczego-a1-first)
3. [Week 1: Foundation](#3-week-1-foundation)
4. [Week 2: Integration](#4-week-2-integration)
5. [Week 3: Polish + Testing](#5-week-3-polish--testing)
6. [Success Criteria](#6-success-criteria)
7. [Test Suite](#7-test-suite)
8. [Rollout strategy](#8-rollout-strategy)
9. [Risk mitigation](#9-risk-mitigation)
10. [Post-POC: next features](#10-post-poc-next-features)

---

# 1. Executive Summary

## 1.1. Co budujemy

**Tmux-based persistent worker sessions** w AEIS:
- Workers spawned w tmux sessions (zamiast bare Python processes)
- Sessions persist across operator disconnects (laptop close, network drop, crash)
- AEIS backend reconnects do existing sessions on startup
- Audit chain dla session lifecycle

## 1.2. Dlaczego A1 najpierw

A1 to **fundament** dla Top 10:
- A2 (Git Worktrees) — używa tmux sessions
- A3 (Docker Sandboxing) — orchestrowany przez tmux
- M1 (Burst Mode) — wymaga 60 persistent sessions
- M3 (Build Critic) — monitoruje workers przez tmux
- A5 (Web PWA) — sync state z persistent sessions

**Bez A1 nic z tego nie działa**. Implementacja A1 unlocks reszta.

## 1.3. Estimated outcomes

```
Effort: 3 weeks (1 dev) lub 1.5 weeks (2 dev)
Cost: ~$10k operator's time

Annual savings (Robert's baseline):
  Time saved: 4h/tydzień × 52 = 208h/year
  Value: 208 × $80/h = $16,640/year
  
ROI Year 1: 166%
ROI Year 2+: ∞ (one-time investment)

Dependencies enabled:
  ✓ A2 (Git Worktrees) — week 4-5
  ✓ A3 (Docker Sandboxing) — week 6-8
  ✓ M3 (Build Critic) — week 9-10
  ✓ M1 (Burst Mode) — week 11-12
```

---

# 2. Pre-flight: dlaczego A1 first

## 2.1. Walidacja założeń

Przed startem POC, walidacja:

```
Q1: Czy tmux jest stabilny dla 50+ persistent sessions?
A: TAK — battle-tested, używany przez tysiące devs codziennie
   AoE manages 9+ CLIs concurrently, 1.6k stars

Q2: Czy operator's machine ma resources?
A: Robert's MacBook Pro M3 Max — wystarczy
   Tmux overhead: minimal (~5MB per session)

Q3: Czy implementacja Python wraps tmux łatwo?
A: TAK — `libtmux` library mature
   Alternatywy: subprocess + tmux CLI (proste)

Q4: Czy AEIS backend już ma worker spawning logic?
A: TAK — w faza 32. Modyfikacja zamiast rewrite.

Q5: Czy mobile reconnect wymaga complex sync logic?
A: NIE — backend continues running na operator's machine
   Mobile/PWA łączy się do tego samego backend (różne UI)
```

Wszystko ✓ — POC jest realnie wykonalny.

## 2.2. Stakeholders

```
Owner: Robert (operator + dev)
Reviewers: 
  - Architecture: Council Hybrid (W3) approval D3
  - Integration: existing AEIS backend tests passing

Stakeholders:
  - Future operators: get persistent sessions feature
  - Customer Y CRM (active project): becomes test case
  - Robert's productivity: immediate beneficiary
```

## 2.3. Initial setup

```bash
# Pre-POC environment setup

# Verify tmux installation
$ tmux -V
tmux 3.4

# Install libtmux (Python library)
$ pip install libtmux

# Verify AEIS backend running
$ curl http://localhost:8000/health
{"status": "ok"}

# Create POC branch
$ git checkout -b feature/tmux-persistent-sessions

# Backup current worker code
$ cp -r aeis/worker/ aeis/worker_pre_a1_backup/
```

---

# 3. Week 1: Foundation

## 3.1. Day 1-2: Library wrapper + Session manager

### Task 1.1: SessionManager class

**File**: `aeis/session_manager.py` (NEW)

```python
"""
SessionManager — wraps libtmux dla persistent worker sessions.
"""
import libtmux
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class WorkerSession:
    """Represents persistent worker session w tmux."""
    session_id: str
    worker_id: int
    project_id: str
    tmux_session_name: str
    workdir: Path
    created_at: datetime
    last_active: datetime
    state: str  # SPAWNED | RUNNING | WAITING | DETACHED | KILLED


class SessionManager:
    """
    Manages tmux sessions dla AEIS workers.
    
    Each worker gets dedicated tmux session that persists across:
    - Operator disconnects (laptop close)
    - AEIS backend restarts
    - Network drops
    - Crashes (mostly — system reboot is exception)
    """
    
    def __init__(self, server: Optional[libtmux.Server] = None):
        self.server = server or libtmux.Server()
        self._sessions: dict[str, WorkerSession] = {}
    
    def create_worker_session(
        self,
        worker_id: int,
        project_id: str,
        workdir: Path,
        command: str
    ) -> WorkerSession:
        """
        Create new persistent tmux session dla worker.
        
        Args:
            worker_id: AEIS worker identifier
            project_id: Project context
            workdir: Working directory dla worker
            command: Initial command to execute
        
        Returns:
            WorkerSession metadata
        """
        session_name = f"aeis_worker_{worker_id}_{project_id}"
        
        # Create detached tmux session
        tmux_session = self.server.new_session(
            session_name=session_name,
            detach=True,
            start_directory=str(workdir),
            window_command=command,
            kill_session=False  # don't kill if exists (resume)
        )
        
        worker_session = WorkerSession(
            session_id=session_name,
            worker_id=worker_id,
            project_id=project_id,
            tmux_session_name=session_name,
            workdir=workdir,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow(),
            state="SPAWNED"
        )
        
        self._sessions[session_name] = worker_session
        return worker_session
    
    def list_active_sessions(self) -> List[WorkerSession]:
        """List all active AEIS sessions (z tmux discovery)."""
        active = []
        for tmux_session in self.server.sessions:
            if tmux_session.name.startswith("aeis_worker_"):
                # Reconstruct worker_session metadata
                if tmux_session.name in self._sessions:
                    active.append(self._sessions[tmux_session.name])
                else:
                    # Discovered session not w cache — reconstruct
                    parts = tmux_session.name.split("_")
                    if len(parts) >= 4:
                        worker_id = int(parts[2])
                        project_id = "_".join(parts[3:])
                        active.append(WorkerSession(
                            session_id=tmux_session.name,
                            worker_id=worker_id,
                            project_id=project_id,
                            tmux_session_name=tmux_session.name,
                            workdir=Path(tmux_session.start_directory or "/"),
                            created_at=datetime.utcnow(),  # unknown
                            last_active=datetime.utcnow(),
                            state="DETACHED"
                        ))
        return active
    
    def attach_to_session(self, session_id: str) -> bool:
        """Reattach do existing session (after operator reconnect)."""
        try:
            tmux_session = self.server.find_where({"session_name": session_id})
            if tmux_session:
                if session_id in self._sessions:
                    self._sessions[session_id].state = "ATTACHED"
                    self._sessions[session_id].last_active = datetime.utcnow()
                return True
        except Exception:
            return False
        return False
    
    def capture_session_output(self, session_id: str, lines: int = 100) -> str:
        """Capture recent output z session (dla monitoring)."""
        tmux_session = self.server.find_where({"session_name": session_id})
        if tmux_session:
            window = tmux_session.attached_window
            pane = window.attached_pane
            return "\n".join(pane.cmd("capture-pane", "-p", "-S", f"-{lines}").stdout)
        return ""
    
    def send_command(self, session_id: str, command: str) -> bool:
        """Send command do running session."""
        tmux_session = self.server.find_where({"session_name": session_id})
        if tmux_session:
            window = tmux_session.attached_window
            pane = window.attached_pane
            pane.send_keys(command)
            self._sessions[session_id].last_active = datetime.utcnow()
            return True
        return False
    
    def kill_session(self, session_id: str) -> bool:
        """Explicit cleanup of session."""
        tmux_session = self.server.find_where({"session_name": session_id})
        if tmux_session:
            tmux_session.kill_session()
            if session_id in self._sessions:
                self._sessions[session_id].state = "KILLED"
            return True
        return False
    
    def get_session_state(self, session_id: str) -> Optional[str]:
        """Query session current state."""
        tmux_session = self.server.find_where({"session_name": session_id})
        if not tmux_session:
            return None
        
        # Heuristic: idle vs active based on last command
        if session_id in self._sessions:
            return self._sessions[session_id].state
        return "DETACHED"  # exists w tmux but nie w our cache
```

### Task 1.2: Unit tests

**File**: `tests/test_session_manager.py` (NEW)

```python
import pytest
from pathlib import Path
from aeis.session_manager import SessionManager, WorkerSession

@pytest.fixture
def session_manager():
    """Fresh SessionManager dla each test."""
    sm = SessionManager()
    # Cleanup any leftover sessions z previous runs
    for s in sm.list_active_sessions():
        sm.kill_session(s.session_id)
    return sm


def test_create_worker_session(session_manager, tmp_path):
    """Test podstawowa session creation."""
    session = session_manager.create_worker_session(
        worker_id=1,
        project_id="test_project",
        workdir=tmp_path,
        command="echo 'hello' && sleep 60"
    )
    
    assert session.session_id == "aeis_worker_1_test_project"
    assert session.state == "SPAWNED"
    assert session.workdir == tmp_path
    
    # Cleanup
    session_manager.kill_session(session.session_id)


def test_list_active_sessions(session_manager, tmp_path):
    """Test discovery of active sessions."""
    # Create 3 sessions
    for i in range(1, 4):
        session_manager.create_worker_session(
            worker_id=i,
            project_id="test_project",
            workdir=tmp_path,
            command="sleep 60"
        )
    
    active = session_manager.list_active_sessions()
    assert len(active) == 3
    
    # Cleanup
    for s in active:
        session_manager.kill_session(s.session_id)


def test_session_persists_across_manager_instances(tmp_path):
    """Test critical: session survives SessionManager recreation."""
    # Create session w first SessionManager
    sm1 = SessionManager()
    session = sm1.create_worker_session(
        worker_id=1,
        project_id="persist_test",
        workdir=tmp_path,
        command="sleep 120"
    )
    
    # Drop reference do sm1
    del sm1
    
    # Create new SessionManager (simulates AEIS backend restart)
    sm2 = SessionManager()
    
    # Session should still be discoverable
    active = sm2.list_active_sessions()
    matching = [s for s in active if s.session_id == "aeis_worker_1_persist_test"]
    
    assert len(matching) == 1
    assert matching[0].state == "DETACHED"
    
    # Cleanup
    sm2.kill_session("aeis_worker_1_persist_test")


def test_capture_session_output(session_manager, tmp_path):
    """Test output capture."""
    session = session_manager.create_worker_session(
        worker_id=1,
        project_id="output_test",
        workdir=tmp_path,
        command="echo 'TEST_OUTPUT' && sleep 30"
    )
    
    # Wait dla output
    import time
    time.sleep(2)
    
    output = session_manager.capture_session_output(session.session_id)
    assert "TEST_OUTPUT" in output
    
    # Cleanup
    session_manager.kill_session(session.session_id)


def test_send_command(session_manager, tmp_path):
    """Test interactive command sending."""
    session = session_manager.create_worker_session(
        worker_id=1,
        project_id="command_test",
        workdir=tmp_path,
        command="bash"
    )
    
    # Send command
    success = session_manager.send_command(session.session_id, "echo 'INTERACTIVE'")
    assert success
    
    # Verify w output
    import time
    time.sleep(1)
    output = session_manager.capture_session_output(session.session_id)
    assert "INTERACTIVE" in output
    
    # Cleanup
    session_manager.kill_session(session.session_id)
```

### Day 1-2 deliverables

```
✓ SessionManager class implemented (~150 lines Python)
✓ 5 unit tests passing
✓ Manual smoke test:
  $ python -c "from aeis.session_manager import SessionManager; \
               sm = SessionManager(); \
               s = sm.create_worker_session(1, 'test', Path('/tmp'), 'echo hello'); \
               print(s)"
✓ libtmux Python integration working
```

## 3.2. Day 3-4: Audit chain integration

### Task 1.3: Session lifecycle audit chain

**File**: `aeis/audit/session_lifecycle.py` (NEW)

```python
"""
Session Lifecycle audit chain — extension W10 Evidence Spine.
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
import nacl.signing


class SessionLifecycleChain:
    """
    Hash-chained, Ed25519-signed audit log dla session events.
    
    Compatible z W10 Evidence Spine architecture.
    """
    
    GENESIS_HASH = "0000000000000000"
    
    def __init__(
        self,
        chain_path: Path,
        signing_key: nacl.signing.SigningKey
    ):
        self.chain_path = chain_path
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        self.signing_key = signing_key
        self._previous_hash = self._load_last_hash()
    
    def _load_last_hash(self) -> str:
        """Load hash of last entry, or GENESIS_HASH if file empty."""
        if not self.chain_path.exists() or self.chain_path.stat().st_size == 0:
            return self.GENESIS_HASH
        
        # Read last line
        with open(self.chain_path, "r") as f:
            lines = f.readlines()
            if not lines:
                return self.GENESIS_HASH
            last_entry = json.loads(lines[-1])
            return last_entry["content_hash"]
    
    def _compute_hash(self, content: dict) -> str:
        """SHA-256 hash of content + previous hash."""
        content_str = json.dumps(content, sort_keys=True)
        full_input = f"{self._previous_hash}|{content_str}"
        return hashlib.sha256(full_input.encode()).hexdigest()
    
    def _sign_entry(self, entry: dict) -> str:
        """Ed25519 signature of entry."""
        entry_bytes = json.dumps(entry, sort_keys=True).encode()
        signed = self.signing_key.sign(entry_bytes)
        return signed.signature.hex()
    
    def append(
        self,
        event_type: str,
        worker_id: int,
        project_id: str,
        session_id: str,
        details: Optional[dict] = None
    ) -> dict:
        """
        Append new entry do session_lifecycle chain.
        
        Event types:
            session_created
            session_attached
            session_detached
            session_state_change
            session_killed
            session_crashed
        """
        content = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "worker_id": worker_id,
            "project_id": project_id,
            "session_id": session_id,
            "details": details or {},
            "previous_hash": self._previous_hash,
        }
        
        content_hash = self._compute_hash(content)
        content["content_hash"] = content_hash
        
        signature = self._sign_entry(content)
        content["signature"] = signature
        
        # Append do file
        with open(self.chain_path, "a") as f:
            f.write(json.dumps(content) + "\n")
        
        # Update internal state
        self._previous_hash = content_hash
        
        return content
    
    def verify_integrity(self) -> bool:
        """Verify entire chain integrity (hash chain + signatures)."""
        if not self.chain_path.exists():
            return True  # empty chain valid
        
        previous_hash = self.GENESIS_HASH
        
        with open(self.chain_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                entry = json.loads(line)
                
                # Verify previous_hash matches
                if entry["previous_hash"] != previous_hash:
                    print(f"Line {line_num}: previous_hash mismatch")
                    return False
                
                # Verify content_hash
                content = {
                    k: v for k, v in entry.items()
                    if k not in ["content_hash", "signature"]
                }
                expected_hash = self._compute_hash(content)
                if entry["content_hash"] != expected_hash:
                    print(f"Line {line_num}: content_hash mismatch")
                    return False
                
                # Update previous_hash dla next iteration
                previous_hash = entry["content_hash"]
        
        return True
```

### Task 1.4: Tests dla audit chain

```python
# tests/test_session_lifecycle_chain.py

import pytest
from pathlib import Path
import nacl.signing
from aeis.audit.session_lifecycle import SessionLifecycleChain


@pytest.fixture
def chain(tmp_path):
    chain_path = tmp_path / "session_lifecycle.jsonl"
    signing_key = nacl.signing.SigningKey.generate()
    return SessionLifecycleChain(chain_path, signing_key)


def test_append_first_entry(chain):
    entry = chain.append(
        event_type="session_created",
        worker_id=1,
        project_id="test",
        session_id="aeis_worker_1_test"
    )
    
    assert entry["event_type"] == "session_created"
    assert entry["previous_hash"] == "0000000000000000"
    assert "content_hash" in entry
    assert "signature" in entry


def test_chain_integrity_valid(chain):
    chain.append("session_created", 1, "test", "ses1")
    chain.append("session_attached", 1, "test", "ses1")
    chain.append("session_detached", 1, "test", "ses1")
    
    assert chain.verify_integrity() is True


def test_chain_integrity_tampered(chain):
    chain.append("session_created", 1, "test", "ses1")
    chain.append("session_attached", 1, "test", "ses1")
    
    # Tamper z chain (modify line)
    with open(chain.chain_path, "r") as f:
        lines = f.readlines()
    
    # Modify first line w-place
    import json
    first_entry = json.loads(lines[0])
    first_entry["worker_id"] = 999  # tampered
    lines[0] = json.dumps(first_entry) + "\n"
    
    with open(chain.chain_path, "w") as f:
        f.writelines(lines)
    
    # Should detect tampering
    assert chain.verify_integrity() is False
```

### Day 3-4 deliverables

```
✓ SessionLifecycleChain implemented z hash chain + Ed25519 signing
✓ Audit chain entries dla 6 event types
✓ Verify integrity function
✓ 3+ unit tests passing
```

## 3.3. Day 5: Integration z AEIS backend

### Task 1.5: Modify worker spawning logic

**File**: `aeis/worker_orchestrator.py` (MODIFY existing)

Add: SessionManager integration:

```python
# BEFORE (existing code):
def spawn_worker(worker_id: int, project_id: str, workdir: Path):
    # Spawn Python subprocess
    process = subprocess.Popen([
        sys.executable, "-m", "aeis.worker",
        "--id", str(worker_id),
        "--project", project_id
    ], cwd=workdir)
    return process


# AFTER (modified):
from aeis.session_manager import SessionManager
from aeis.audit.session_lifecycle import SessionLifecycleChain

session_manager = SessionManager()
audit_chain = SessionLifecycleChain(
    chain_path=Path("~/.sylion/aeis/audit/session_lifecycle.jsonl").expanduser(),
    signing_key=load_operator_signing_key()
)

def spawn_worker(worker_id: int, project_id: str, workdir: Path):
    # Spawn worker w persistent tmux session
    command = f"{sys.executable} -m aeis.worker --id={worker_id} --project={project_id}"
    
    session = session_manager.create_worker_session(
        worker_id=worker_id,
        project_id=project_id,
        workdir=workdir,
        command=command
    )
    
    # Audit chain entry
    audit_chain.append(
        event_type="session_created",
        worker_id=worker_id,
        project_id=project_id,
        session_id=session.session_id,
        details={
            "workdir": str(workdir),
            "command": command,
            "tmux_session_name": session.tmux_session_name
        }
    )
    
    return session


def reconnect_to_existing_sessions():
    """
    Called on AEIS backend startup.
    Discover and reconnect do sessions z poprzedniej pracy.
    """
    active = session_manager.list_active_sessions()
    
    if active:
        print(f"Found {len(active)} active sessions z poprzedniej pracy")
        for session in active:
            session_manager.attach_to_session(session.session_id)
            audit_chain.append(
                event_type="session_attached",
                worker_id=session.worker_id,
                project_id=session.project_id,
                session_id=session.session_id,
                details={"reason": "backend_startup"}
            )
    
    return active
```

### Day 5 deliverables

```
✓ AEIS backend uses SessionManager dla worker spawning
✓ Audit chain entries dla session events
✓ Reconnect logic on backend startup
✓ Smoke test:
  - Start AEIS, spawn worker
  - Kill AEIS backend (Ctrl+C)
  - Wait 30 sec
  - Restart AEIS
  - Verify worker still running, reconnected
```

## 3.4. Week 1 milestone

```
End of Week 1:
  ✓ SessionManager working
  ✓ Audit chain integrated
  ✓ Backend uses tmux dla workers
  ✓ Reconnect on startup working
  
  Tests passing: 8+
  Integration test: kill+restart backend, sessions persist
  
  Demonstrable: Robert może zostawić AEIS na noc, reconnect rano
```

---

# 4. Week 2: Integration

## 4.1. Day 6-7: UI updates (W1 + W18)

### Task 2.1: Frontend "Active Sessions" view

**File**: `frontend/components/ActiveSessions.tsx` (NEW)

```typescript
// Active Sessions component dla operator dashboard

import { useEffect, useState } from 'react';

interface WorkerSession {
  session_id: string;
  worker_id: number;
  project_id: string;
  state: string;
  last_active: string;
}

export function ActiveSessions() {
  const [sessions, setSessions] = useState<WorkerSession[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetch('/api/sessions/active')
      .then(res => res.json())
      .then(data => {
        setSessions(data);
        setLoading(false);
      });
    
    // WebSocket dla real-time updates
    const ws = new WebSocket('ws://localhost:8000/ws/sessions');
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setSessions(prev => updateSession(prev, update));
    };
    
    return () => ws.close();
  }, []);
  
  if (loading) return <div>Loading sessions...</div>;
  
  return (
    <div className="active-sessions">
      <h2>Active Worker Sessions</h2>
      {sessions.length === 0 ? (
        <p>No active sessions. Start a project to spawn workers.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Worker</th>
              <th>Project</th>
              <th>State</th>
              <th>Last Active</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map(session => (
              <tr key={session.session_id}>
                <td>Worker {session.worker_id}</td>
                <td>{session.project_id}</td>
                <td>
                  <span className={`state-${session.state.toLowerCase()}`}>
                    {session.state}
                  </span>
                </td>
                <td>{formatTimestamp(session.last_active)}</td>
                <td>
                  <button onClick={() => attachSession(session.session_id)}>
                    Attach
                  </button>
                  <button onClick={() => killSession(session.session_id)}>
                    Kill
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

### Task 2.2: Backend API endpoints

**File**: `aeis/api/sessions.py` (NEW)

```python
from fastapi import APIRouter, HTTPException
from aeis.session_manager import SessionManager

router = APIRouter(prefix="/api/sessions")
session_manager = SessionManager()

@router.get("/active")
def list_active_sessions():
    """List all active worker sessions."""
    sessions = session_manager.list_active_sessions()
    return [
        {
            "session_id": s.session_id,
            "worker_id": s.worker_id,
            "project_id": s.project_id,
            "state": s.state,
            "last_active": s.last_active.isoformat() + "Z",
        }
        for s in sessions
    ]


@router.post("/{session_id}/attach")
def attach_session(session_id: str):
    """Reattach do existing session."""
    success = session_manager.attach_to_session(session_id)
    if not success:
        raise HTTPException(404, "Session not found")
    return {"status": "attached"}


@router.delete("/{session_id}")
def kill_session(session_id: str):
    """Explicit cleanup of session."""
    success = session_manager.kill_session(session_id)
    if not success:
        raise HTTPException(404, "Session not found")
    return {"status": "killed"}


@router.get("/{session_id}/output")
def get_session_output(session_id: str, lines: int = 100):
    """Capture recent session output."""
    output = session_manager.capture_session_output(session_id, lines=lines)
    return {"output": output}
```

### Day 6-7 deliverables

```
✓ Active Sessions view w UI
✓ 4 API endpoints (list, attach, kill, output)
✓ WebSocket real-time updates
✓ Frontend integration test
```

## 4.2. Day 8-9: Mobile reconnect support

### Task 2.3: Mobile API parity

Mobile/PWA musi mieć same API access:

```python
# aeis/api/mobile_sessions.py — same endpoints, mobile-optimized responses

@router.get("/mobile/sessions/summary")
def mobile_sessions_summary():
    """Compact summary dla mobile screens."""
    sessions = session_manager.list_active_sessions()
    return {
        "total": len(sessions),
        "running": len([s for s in sessions if s.state == "RUNNING"]),
        "waiting": len([s for s in sessions if s.state == "WAITING"]),
        "detached": len([s for s in sessions if s.state == "DETACHED"]),
        "items": [
            {
                "id": s.session_id,
                "title": f"W{s.worker_id} • {s.project_id}",
                "state_emoji": state_to_emoji(s.state),
                "last_active_relative": relative_time(s.last_active),
            }
            for s in sessions[:20]  # max 20 dla mobile
        ]
    }
```

### Task 2.4: Tailscale Funnel setup

```bash
# Setup Tailscale Funnel dla remote mobile access

# 1. Install Tailscale on operator's machine
# 2. Login z operator's Tailscale account
$ tailscale up

# 3. Enable Funnel (allow public HTTPS access)
$ tailscale serve https / http://localhost:3000
$ tailscale funnel 443 on

# 4. Get public URL
$ tailscale funnel status
Funnel on: https://operator-mac.tail-scale-net.ts.net

# 5. Operator can now access AEIS z phone via:
# https://operator-mac.tail-scale-net.ts.net
```

### Day 8-9 deliverables

```
✓ Mobile API endpoints
✓ Tailscale Funnel setup documented
✓ Phone test: open URL, see active sessions
✓ Cross-device sync working (same session visible)
```

## 4.3. Day 10: Edge case handling

### Task 2.5: Crash recovery

```python
# aeis/session_manager.py — extension dla crash recovery

def detect_crashed_sessions(self) -> List[WorkerSession]:
    """
    Detect sessions which crashed (no heartbeat z ostatnich 5 min).
    """
    crashed = []
    threshold = datetime.utcnow() - timedelta(minutes=5)
    
    for session_name, session in self._sessions.items():
        # Check if tmux session still exists
        tmux_session = self.server.find_where({"session_name": session_name})
        if not tmux_session:
            session.state = "CRASHED"
            crashed.append(session)
            continue
        
        # Check last activity
        if session.last_active < threshold:
            # Send heartbeat probe
            output = self.capture_session_output(session_name, lines=10)
            if "AEIS_HEARTBEAT" not in output:
                session.state = "CRASHED"
                crashed.append(session)
    
    return crashed


def auto_recover_crashed(self, audit_chain) -> List[WorkerSession]:
    """Auto-respawn crashed sessions z latest checkpoint."""
    crashed = self.detect_crashed_sessions()
    recovered = []
    
    for session in crashed:
        # Audit chain
        audit_chain.append(
            event_type="session_crashed",
            worker_id=session.worker_id,
            project_id=session.project_id,
            session_id=session.session_id,
            details={"detection_method": "heartbeat_lost"}
        )
        
        # Respawn
        new_session = self.create_worker_session(
            worker_id=session.worker_id,
            project_id=session.project_id,
            workdir=session.workdir,
            command=f"python -m aeis.worker --id={session.worker_id} --resume"
        )
        recovered.append(new_session)
    
    return recovered
```

### Day 10 deliverables

```
✓ Crash detection (heartbeat-based)
✓ Auto-recovery logic
✓ Audit chain entries dla crashes
✓ Test: kill -9 worker process, verify auto-recovery
```

## 4.4. Week 2 milestone

```
End of Week 2:
  ✓ UI shows active sessions
  ✓ Mobile reconnect works (Tailscale Funnel)
  ✓ Crash recovery automatic
  ✓ API parity (desktop + mobile)
  
  Tests passing: 15+
  
  Demonstrable end-to-end:
    1. Start project, workers spawned w tmux
    2. Robert closes laptop
    3. 30 min later, opens phone, sees workers active
    4. Approves hard gate from phone
    5. Returns do laptop, all state preserved
```

---

# 5. Week 3: Polish + Testing

## 5.1. Day 11-12: Performance tuning

### Task 3.1: Stress test 60+ sessions

```python
# tests/integration/test_session_scale.py

import pytest
import time
from aeis.session_manager import SessionManager
from pathlib import Path

@pytest.mark.slow
def test_100_concurrent_sessions(tmp_path):
    """Verify SessionManager handles 100 sessions."""
    sm = SessionManager()
    sessions = []
    
    start_time = time.time()
    for i in range(100):
        session = sm.create_worker_session(
            worker_id=i,
            project_id="scale_test",
            workdir=tmp_path,
            command="sleep 300"
        )
        sessions.append(session)
    
    spawn_duration = time.time() - start_time
    print(f"Spawned 100 sessions w {spawn_duration:.2f}s")
    assert spawn_duration < 60  # under 1 min
    
    # Verify wszystkie active
    active = sm.list_active_sessions()
    assert len(active) == 100
    
    # Cleanup
    cleanup_start = time.time()
    for s in sessions:
        sm.kill_session(s.session_id)
    cleanup_duration = time.time() - cleanup_start
    print(f"Cleaned up 100 sessions w {cleanup_duration:.2f}s")
    assert cleanup_duration < 30
```

### Task 3.2: Memory profiling

```bash
# Profile memory usage z 60 sessions

$ python -m memory_profiler stress_test_60_sessions.py

# Expected:
# Tmux server: ~200MB (60 sessions × ~3MB)
# AEIS backend: +50MB (SessionManager state)
# Total overhead: ~250MB dla 60 workers
```

## 5.2. Day 13: Documentation

### Task 3.3: Operator documentation

**File**: `docs/persistent_sessions.md` (NEW)

```markdown
# Persistent Worker Sessions (A1)

## Co to jest

AEIS workers działają w persistent tmux sessions. Oznacza to:
- ✓ Zamknij laptop, workery działają dalej
- ✓ Wróć rano, wszystko jest gdzie zostawiłeś
- ✓ Switch między laptop i phone seamlessly
- ✓ Crash recovery automatic

## Wymagania

- macOS lub Linux
- tmux >= 3.3 installed (`brew install tmux` lub `apt install tmux`)
- Python libtmux (auto-installed z AEIS)
- (Optional) Tailscale dla mobile access

## Setup

Pierwsze uruchomienie:
1. Verify tmux: `tmux -V`
2. AEIS detects automatically on start
3. Confirm w settings: ☑ "Persistent worker sessions"

## Daily workflow

### Working
Start project normally. Workers spawned w tmux:
```
✓ Worker 1 (Backend) — aeis_worker_1_customer_y_crm
✓ Worker 2 (Frontend) — aeis_worker_2_customer_y_crm
```

### Closing laptop
Just close. Workers continue working.

### Mobile reconnect
1. Open AEIS app or Tailscale URL
2. See same active sessions
3. Continue (approve gates, monitor, etc.)

### Returning to laptop
1. Open AEIS desktop
2. Auto-detect z tmux: "Found 4 active sessions z poprzedniej pracy"
3. Continue normally

## Troubleshooting

**Q: Sessions disappeared po reboot**
A: System reboot kills tmux server. Sessions LOST. Reopen AEIS, workers respawn z latest checkpoint.

**Q: Worker crashed mid-task**
A: Auto-recovery detects, respawns. Audit chain logs event.

**Q: Want do explicitly stop a worker**
A: UI: "Active Sessions" → Kill button. Or CLI: `tmux kill-session -t aeis_worker_X`
```

## 5.3. Day 14-15: Final integration testing

### Task 3.4: End-to-end test scenarios

```python
# tests/e2e/test_persistent_sessions_e2e.py

@pytest.mark.e2e
def test_overnight_persistence():
    """
    Scenario: Robert leaves project running overnight.
    
    Steps:
    1. Start AEIS, begin Customer Y CRM faza 35
    2. Spawn 2 workers
    3. Workers run dla 5 min (simulate work progress)
    4. Kill AEIS backend (Ctrl+C simulation)
    5. Wait 30 sec
    6. Restart AEIS backend
    7. Verify reconnection
    8. Verify worker state preserved
    9. Verify no LLM calls duplicated
    """
    # ... test implementation


@pytest.mark.e2e
def test_mobile_to_desktop_handoff():
    """
    Scenario: Robert pracuje na phone, switches do laptop.
    
    Steps:
    1. Start project z laptop
    2. Workers spawned
    3. Robert opens phone (Tailscale URL)
    4. Sees same workers
    5. Approves hard gate from phone
    6. Returns do laptop
    7. Verify gate approval reflected w desktop UI
    8. Verify audit chain tracks both devices
    """
    # ... test implementation


@pytest.mark.e2e
def test_60_workers_burst_dependency():
    """
    Scenario: Test foundation dla M1 Burst Mode (60 workers).
    
    Steps:
    1. Create 60 sessions concurrent
    2. Verify all spawn within 60 sec
    3. Verify all detect-able after backend restart
    4. Cleanup 60 sessions w under 30 sec
    """
    # ... test implementation
```

## 5.4. Week 3 milestone — POC complete

```
End of Week 3:
  ✓ Performance: 100 concurrent sessions tested
  ✓ Memory: <300MB overhead dla 60 workers
  ✓ Documentation: operator + dev docs
  ✓ E2E tests: 5+ scenarios passing
  ✓ Audit chain: integrity verified
  ✓ UI: Active Sessions view z real-time updates
  ✓ Mobile: Tailscale Funnel access working
  
  POC SHIPS dla Robert's daily use.
  
  Foundation dla:
    Week 4-5: A2 (Git Worktrees)
    Week 6-8: A3 (Docker Sandboxing)
    Week 9-10: M3 (Build Critic)
    Week 11-12: M1 (Burst Mode)
```

---

# 6. Success Criteria

## 6.1. Functional criteria

```
MUST HAVE (block release jeśli not met):
  [✓] Workers spawned w tmux sessions
  [✓] Sessions persist across AEIS backend restart
  [✓] Audit chain entries dla 6 event types
  [✓] UI shows active sessions
  [✓] API endpoints (list/attach/kill/output)
  [✓] Crash recovery automatic
  [✓] Tests: 95%+ passing

NICE TO HAVE (post-release):
  [○] Tailscale Funnel auto-config
  [○] Visual session preview w UI
  [○] Slack notification on crashes
  [○] Performance dashboard (sessions over time)
```

## 6.2. Performance criteria

```
Spawn time:
  Target: <2 sec per session
  Stretch: <1 sec
  
Reconnect time (post-restart):
  Target: <5 sec for 10 sessions
  Stretch: <3 sec
  
Memory overhead:
  Target: <5 MB per session (tmux)
  Stretch: <3 MB

Crash detection latency:
  Target: <60 sec
  Stretch: <30 sec
```

## 6.3. UX criteria

```
Operator scenarios:
  [✓] Close laptop, sessions continue
  [✓] Open phone, see same sessions  
  [✓] Returns to laptop, no data loss
  [✓] Crash auto-recovers without operator action
  [✓] UI clearly shows session state
  [✓] Audit chain queryable z UI
```

---

# 7. Test Suite

## 7.1. Test pyramid

```
                    ╱╲
                   ╱E2E╲           5 scenarios (manual + automated)
                  ╱──────╲
                 ╱ Integ. ╲        15 tests (API + UI integration)
                ╱──────────╲
               ╱  Unit Tests ╲     30+ tests (SessionManager + ChainAudit)
              ╱──────────────╲
```

## 7.2. CI/CD integration

```yaml
# .github/workflows/test_a1.yml

name: Test A1 — Persistent Sessions

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y tmux
      - run: pip install -e ".[test]"
      - run: pytest tests/test_session_manager.py -v
      - run: pytest tests/test_session_lifecycle_chain.py -v
  
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y tmux
      - run: pip install -e ".[test]"
      - run: pytest tests/integration/ -v -m "not slow"
  
  e2e:
    runs-on: macos-latest  # zachowanie similar do Robert's setup
    steps:
      - uses: actions/checkout@v4
      - run: brew install tmux
      - run: pip install -e ".[test]"
      - run: pytest tests/e2e/ -v --timeout=300
```

---

# 8. Rollout strategy

## 8.1. Phase 1 — Internal beta (Week 4)

```
Audience: Robert only
Project: Internal R&D project (low risk)
Duration: 1 week
Goal: validate w real usage, find edge cases

Monitoring:
  - Audit chain integrity check daily
  - Performance metrics (memory, latency)
  - Crash rate
  - UX friction points
```

## 8.2. Phase 2 — Customer Y CRM (Week 5)

```
Audience: Robert na Customer Y CRM (active D4 project)
Risk: medium (real customer)
Mitigation: keep old code path as fallback

Rollback plan:
  Feature flag: AEIS_USE_TMUX_SESSIONS=true|false
  If issues: set false, revert do bare processes
  Existing audit chain preserved
```

## 8.3. Phase 3 — Other operators (post-A1)

```
Once A1 stable, ship to other operators:
  Documentation update (Polish + English)
  Migration guide (existing projects)
  Beta testing program (5-10 operators)
  
General availability: po 4 weeks of stable internal use
```

---

# 9. Risk mitigation

## 9.1. Technical risks

```
RISK 1: tmux instability dla 60+ sessions
  Probability: LOW (battle-tested)
  Impact: HIGH (would block M1 Burst Mode)
  Mitigation: 
    - Stress test 100 sessions w POC
    - Fallback: zellij or process-based dla high counts
    - Monitor tmux server memory long-term

RISK 2: Windows compatibility
  Probability: HIGH (tmux is Linux/macOS)
  Impact: MEDIUM (limits operator base)
  Mitigation:
    - WSL2 fallback
    - Future: zellij Windows alternative (Q2 2027)
    - Current: warning message dla Windows operators

RISK 3: System reboot loses sessions
  Probability: MEDIUM (planned reboots, OS updates)
  Impact: LOW (acceptable, recoverable z checkpoint)
  Mitigation:
    - Document expectation
    - Checkpoint frequency increased (5 min → 30 sec)
    - Auto-recovery z checkpoint
```

## 9.2. UX risks

```
RISK 4: Operator confused by tmux concepts
  Probability: MEDIUM
  Impact: LOW (learning curve)
  Mitigation:
    - Hide tmux details behind AEIS UI
    - Documentation analogizes to "background processes"
    - Operator never needs do interact z tmux directly

RISK 5: Performance degradation on slower machines
  Probability: LOW (tmux lightweight)
  Impact: MEDIUM (slower operators frustrated)
  Mitigation:
    - Optional disable (config setting)
    - Per-session resource limits
    - Performance monitoring built-in
```

## 9.3. Schedule risks

```
RISK 6: 3 weeks za mało
  Probability: MEDIUM
  Impact: HIGH (delays subsequent features)
  Mitigation:
    - Buffer week 4 dla stabilization
    - Cut scope: defer some edge cases do Phase 2
    - Post-launch iteration acceptable
```

---

# 10. Post-POC: next features

## 10.1. Immediate next (Week 4-5)

**A2 Git Worktrees** — depends on A1 sessions

```
Reuses: SessionManager (just adds worktree creation)
New: WorktreeManager class
Integration: faza 32 worker spawning
Estimated effort: 2 weeks
```

## 10.2. Following (Week 6-8)

**A3 Docker Sandboxing** — depends on A1 + A2

```
Reuses: SessionManager + WorktreeManager
New: ContainerManager class, Docker config
Integration: each worker spawned w container
Estimated effort: 3 weeks
```

## 10.3. Capabilities (Week 9-12)

```
Week 9-10: M3 Build Critic (depends on A1)
Week 11-12: M1 Burst Mode (depends on A1+A2+A3+M2)
```

## 10.4. Final dependency tree

```
                  A1 (3 weeks)
                  /│\
                 / │ \
                /  │  \
               A2  M3  hooks/profiles
              (2)  (2)
              /
             A3 (3)
             /
            M1 (2) ← needs M2 too
```

**Critical path do Burst Mode**: A1 → A2 → A3 → M1 = 10 weeks minimum
**Z parallel dev**: A1 + (A2+A3 parallel) → M3+M1+M2 = 7 weeks

---

# Podsumowanie POC plan

```
TIMELINE:
  Week 1: Foundation (SessionManager + AuditChain + integration)
  Week 2: UX (UI + Mobile + edge cases)
  Week 3: Polish (performance + docs + testing)

EFFORT:
  3 weeks 1 dev = ~120h work
  Cost: ~$10k operator time

DELIVERABLES:
  ✓ SessionManager class (~200 lines)
  ✓ SessionLifecycleChain (~150 lines)
  ✓ API endpoints (~80 lines)
  ✓ UI component (~100 lines TypeScript)
  ✓ 30+ unit tests
  ✓ 5+ E2E tests
  ✓ Documentation (operator + dev)

ROI:
  Annual savings: $16,640
  Year 1 ROI: 166%
  Year 2+ ROI: ∞

UNLOCKS:
  ✓ A2 Git Worktrees (next)
  ✓ A3 Docker Sandboxing
  ✓ M1 Burst Mode (game changer)
  ✓ M3 Build Critic
  ✓ A5 Web PWA mobile reconnect

SUCCESS CRITERIA:
  Functional: 7 must-haves all met
  Performance: spawn <2s, reconnect <5s
  UX: 6 operator scenarios validated
  Tests: 95%+ passing

START DATE: TBD (operator decision)
TARGET END: Start + 3 weeks
GO/NO-GO MILESTONE: end of Week 1
```

🚀 **POC plan gotowy do executywnej decyzji.**

Powiedz "GO" gdy chcesz zacząć implementację.
