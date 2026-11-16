# Rigg Agent Orchestration

**Module:** Agent Orchestration
**Status:** Specification
**Depends On:** v3 Refactor (05-agent-orchestration.md, 06-concurrency-coordination.md)

---

## Overview

Rigg agent orchestration provides process-isolated multi-agent coordination. Built on top of the completed v3 refactor, it uses `claude -p` spawning with PostgreSQL + Redis blackboard communication, deterministic routing to 15+ specialized agents, and multi-file atomicity guarantees.

---

## Orchestration Patterns

Rigg supports 11 coordination patterns, inherited from the v3 architecture. Pattern selection is handled by Claude (the main conversation) based on task characteristics.

### Pattern Reference

| Pattern | Use Case | Coordination | Scope |
|---------|----------|--------------|-------|
| **Swarm** | Research, exploration | Parallel independent | Isolated |
| **Jury** | Validation, high-stakes | Voting consensus | Isolated |
| **Pipeline** | Linear workflow | Sequential handoff | Shared (via HandoffState) |
| **Hierarchical** | Implementation, "build" | Coordinator + specialists | Federated |
| **Generator/Critic** | Review, refinement | Iterative loop | Shared |
| **MapReduce** | Batch processing | Fan-out + aggregate | Isolated mappers, Shared reducer |
| **Blackboard** | Collaborative solving | Shared state | Shared |
| **CircuitBreaker** | Resilience, fallback | Primary + fallback | Isolated |
| **Adversarial** | Stress-test, debate | Advocate vs adversary | Isolated |
| **ChainOfResponsibility** | Escalation, tiering | First-match routing | Isolated |
| **EventDriven** | Reactive, monitoring | Pub/sub | Isolated |

### Pattern Selection Heuristics

Claude selects patterns based on:

1. **Keywords:** "research" -> Swarm, "implement" -> Hierarchical, "validate" -> Jury
2. **Complexity:** Unknown -> Hierarchical (adapt), clear steps -> Pipeline
3. **Risk:** High-stakes -> Jury, production -> Adversarial
4. **Independence:** Independent subtasks -> Swarm/MapReduce

---

## Spawning Mechanism

### Process Isolation via Subprocess

All agent spawning uses `claude -p` via subprocess for true process isolation:

```bash
# Basic spawn
claude -p "Your task description" --output-format json > /tmp/agent-$ID.json &

# With allowed tools restriction
claude -p "Research task" --allowedTools "Read,Grep,Glob" --output-format json &

# Capture PID for tracking
PID=$!
echo "$PID" >> /tmp/agent-pids.txt
```

### Spawn Wrapper (Python)

```python
# scripts/claude_spawn.py
import subprocess
import os
from dataclasses import dataclass

@dataclass
class SpawnedAgent:
    pid: int
    agent_id: str
    output_file: str
    depth_level: int

def spawn_agent(
    prompt: str,
    perspective: str = "",
    depth_level: int = 1,
    allowed_tools: list[str] | None = None,
) -> SpawnedAgent:
    """Spawn a headless Claude agent with process isolation."""

    # Enforce depth limit
    if depth_level >= 3:
        raise DepthLimitExceeded("Max nesting depth (3) reached")

    agent_id = generate_uuid()
    output_file = f"/tmp/claude-agents/{agent_id}.json"

    cmd = [
        "claude", "-p", f"{perspective}: {prompt}" if perspective else prompt,
        "--output-format", "json",
    ]

    if allowed_tools:
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])

    env = os.environ.copy()
    env.update({
        "DEPTH_LEVEL": str(depth_level + 1),
        "PARENT_AGENT_ID": os.environ.get("AGENT_ID", "orchestrator"),
        "AGENT_ID": agent_id,
        "SESSION_ID": os.environ.get("SESSION_ID"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
    })

    with open(output_file, 'w') as f:
        proc = subprocess.Popen(cmd, stdout=f, env=env)

    # Register in CoordinationDB (PostgreSQL)
    register_agent(agent_id, pid=proc.pid, parent=env["PARENT_AGENT_ID"])

    return SpawnedAgent(
        pid=proc.pid,
        agent_id=agent_id,
        output_file=output_file,
        depth_level=depth_level + 1,
    )
```

---

## Depth Limits

### Nesting Hierarchy

| Level | Description | Max Agents | Can Spawn? |
|-------|-------------|------------|------------|
| 0 | Main orchestrator (user session) | 1 | Yes |
| 1 | Direct headless agents | Dynamic (resource-based) | Yes (leads only) |
| 2 | Sub-agents spawned by level 1 | Dynamic (resource-based) | No |
| 3 | **HARD LIMIT** - spawn rejected | 0 | No |

### Enforcement

```python
def check_spawn_allowed(requester: str, target: str, depth: int) -> bool:
    """Deterministic spawn control - no LLM involved."""

    # Hard depth limit
    if depth >= 3:
        return False

    # Only leads can spawn at depth 0-1
    LEADS = {'kraken', 'architect', 'phoenix', 'herald', 'maestro'}
    if target in LEADS and depth >= 2:
        return False

    # Dynamic resource check
    if not resources_available():
        return False

    return True
```

---

## Resource Gating

### Thresholds

| Resource | Threshold | Action |
|----------|-----------|--------|
| CPU | < 80% | Allow spawn |
| Memory | < 85% | Allow spawn |
| Open agents | < 50 per session | Allow spawn |

### Implementation

```python
import psutil

def resources_available() -> bool:
    """Check system resources before spawning."""
    cpu_ok = psutil.cpu_percent() < 80
    mem_ok = psutil.virtual_memory().percent < 85

    # Also check agent count in PostgreSQL
    agent_count = db.count_active_agents(session_id=os.environ.get("SESSION_ID"))
    agents_ok = agent_count < 50

    return cpu_ok and mem_ok and agents_ok
```

### Backpressure

Block spawning until PostgreSQL confirms registration:

```python
async def spawn_agent_with_backpressure(prompt: str, timeout: float = 30.0) -> SpawnedAgent:
    """Spawn agent, blocking until DB confirms registration."""
    agent_id = generate_uuid()

    # Register first, block until confirmed
    await asyncio.wait_for(
        register_agent_in_db(agent_id),
        timeout=timeout
    )

    # Only now spawn the process
    return spawn_agent(prompt, agent_id=agent_id)
```

---

## Environment Variables

| Variable | Description | Set By |
|----------|-------------|--------|
| `DEPTH_LEVEL` | Current nesting depth (0-3) | Parent agent |
| `AGENT_ID` | UUID of this agent | Spawn wrapper |
| `PARENT_AGENT_ID` | UUID of parent | Spawn wrapper |
| `SESSION_ID` | Root session identifier | Orchestrator |
| `SWARM_ID` | Current swarm identifier | Pattern executor |
| `PATTERN_TYPE` | Active pattern (swarm, jury, etc.) | Pattern executor |
| `DATABASE_URL` | PostgreSQL connection | Inherited |
| `REDIS_URL` | Redis connection for blackboard | Inherited |

---

## Agent Communication

### Batch System (Not Real-Time)

Rigg uses a **batch** communication model via blackboard, not real-time messaging. Agents:

1. Write findings/status to blackboard
2. Poll blackboard on write operations (PreToolUse hook)
3. Read directives and other agents' findings
4. Mark messages as read

### PostgreSQL + Redis Blackboard

**PostgreSQL (durable, structured):**

```sql
-- Blackboard for inter-agent messaging
CREATE TABLE blackboard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    message_type TEXT NOT NULL CHECK (message_type IN ('finding', 'directive', 'status', 'quorum')),
    target_agent TEXT,  -- NULL = broadcast
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_by JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX idx_blackboard_swarm ON blackboard(swarm_id, created_at);
CREATE INDEX idx_blackboard_target ON blackboard(target_agent) WHERE target_agent IS NOT NULL;
```

**Redis (hot cache, fast polling):**

```python
# Fast blackboard polling via Redis
async def poll_blackboard_redis(swarm_id: str, agent_id: str) -> list[dict]:
    """Poll Redis for recent messages, fall back to PostgreSQL for older."""
    redis_key = f"blackboard:{swarm_id}:recent"

    # Get last 5 minutes of messages from Redis (hot cache)
    messages = await redis.lrange(redis_key, 0, -1)

    # Filter for messages targeting this agent or broadcast
    relevant = [m for m in messages if m['target_agent'] in (None, agent_id)]

    # Filter out already-read messages
    unread = [m for m in relevant if agent_id not in m.get('read_by', [])]

    return unread
```

### Message Types

| Type | Purpose | Example |
|------|---------|---------|
| `finding` | Share discovered information | `{"summary": "Found auth bug in file X"}` |
| `directive` | Control flow instruction | `{"action": "stop", "reason": "Sentinel blocked"}` |
| `status` | Agent state update | `{"state": "completed", "result_file": "/tmp/..."}` |
| `quorum` | Voting/consensus signal | `{"vote": "approve", "confidence": 0.9}` |

### PreToolUse Polling Hook

Agents poll blackboard before write operations:

```typescript
// .claude/hooks/src/blackboard-poll.ts
const WRITE_TOOLS = ['Bash', 'Write', 'Edit', 'MultiEdit'];

async function main() {
    const input = JSON.parse(await readStdin());

    // Only poll for write operations
    if (!WRITE_TOOLS.includes(input.tool_name)) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    const agentId = process.env.AGENT_ID;
    const swarmId = process.env.SWARM_ID;

    if (!agentId || !swarmId) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Poll blackboard for directives
    const messages = await pollBlackboard(swarmId, agentId);

    // Check for blocking directives
    const blockingDirective = messages.find(m =>
        m.message_type === 'directive' &&
        (m.target_agent === agentId || m.target_agent === null)
    );

    if (blockingDirective) {
        console.log(JSON.stringify({
            result: 'block',
            reason: `Directive from sentinel: ${blockingDirective.payload.message}`
        }));
        return;
    }

    // Inject findings as context
    const findings = messages
        .filter(m => m.message_type === 'finding')
        .map(m => m.payload.summary)
        .join('\n');

    if (findings) {
        console.log(JSON.stringify({
            result: 'continue',
            message: `[Blackboard Update]\n${findings}`
        }));
        return;
    }

    console.log(JSON.stringify({ result: 'continue' }));
}
```

---

## Deterministic Routing

### Keyword-Based Agent Selection

Rigg uses deterministic trigger-to-agent mappings (no LLM routing overhead):

```python
AGENT_ROUTING = {
    ('implement', 'large'): 'kraken',
    ('implement', 'small'): 'spark',
    ('fix', '*'): 'spark',
    ('document', '*'): 'scribe',
    ('debug', '*'): 'sleuth',
    ('security', '*'): 'aegis',
    ('performance', '*'): 'profiler',
    ('test', 'unit'): 'arbiter',
    ('test', 'e2e'): 'atlas',
    ('research', 'external'): 'oracle',
    ('research', 'internal'): 'scout',
    ('research', 'repo'): 'pathfinder',
    ('plan', 'feature'): 'architect',
    ('plan', 'refactor'): 'phoenix',
    ('plan', 'integration'): 'architect',
    ('review', 'architect'): 'sentinel',
    ('review', 'phoenix'): 'warden',
    ('session', '*'): 'chronicler',
    ('deploy', '*'): 'herald',
    ('orchestrate', '*'): 'maestro',
}
```

### Agent Roster (18 Specialized Agents)

| Domain | Agent | Role | Can Spawn? |
|--------|-------|------|------------|
| **Implement** | Kraken | Large TDD implementation | Yes |
| | Spark | Small fixes | No |
| **Document** | Scribe | Docs, handoffs, ledgers | No |
| **Debug** | Sleuth | General investigation | No |
| | Aegis | Security analysis | No |
| | Profiler | Performance issues | No |
| **Validate** | Arbiter | Unit/integration tests | No |
| | Atlas | E2E tests | No |
| **Research** | Oracle | External (wraps NIA API) | No |
| | Scout | Internal codebase | No |
| | Pathfinder | External repo analysis | No |
| **Plan** | Architect | Build: new features + integrations | Yes |
| | Phoenix | Change: refactors + migrations | Yes |
| **Review** | Sentinel | Reviews Architect's plans | No |
| | Warden | Reviews Phoenix's plans | No |
| **Session** | Chronicler | Session analysis + precedent lookup | No |
| **Deploy** | Herald | Release prep | Yes |
| **Orchestrate** | Maestro | Pure coordinator (no direct work) | Yes |

### Routing Function

```python
def route_to_agent(task: str) -> str:
    """Deterministic routing based on keywords."""
    task_lower = task.lower()

    # Priority-ordered keyword matching
    if any(kw in task_lower for kw in ['implement', 'build', 'create']):
        return 'kraken' if len(task) > 200 else 'spark'

    if any(kw in task_lower for kw in ['fix', 'tweak', 'update', 'small']):
        return 'spark'

    if any(kw in task_lower for kw in ['document', 'handoff', 'summarize', 'ledger']):
        return 'scribe'

    if any(kw in task_lower for kw in ['debug', 'investigate', 'error', 'bug']):
        return 'sleuth'

    if any(kw in task_lower for kw in ['security', 'vulnerability', 'cve', 'audit']):
        return 'aegis'

    if any(kw in task_lower for kw in ['slow', 'performance', 'memory', 'race', 'profile']):
        return 'profiler'

    if any(kw in task_lower for kw in ['test', 'validate', 'verify', 'unit', 'integration']):
        return 'arbiter'

    if any(kw in task_lower for kw in ['e2e', 'end-to-end', 'acceptance']):
        return 'atlas'

    if any(kw in task_lower for kw in ['research', 'learn', 'best practices']):
        return 'oracle'

    if any(kw in task_lower for kw in ['find', 'locate', 'where', 'codebase']):
        return 'scout'

    if any(kw in task_lower for kw in ['analyze repo', 'external repo', 'github']):
        return 'pathfinder'

    if any(kw in task_lower for kw in ['plan feature', 'design', 'new', 'integration']):
        return 'architect'

    if any(kw in task_lower for kw in ['plan refactor', 'cleanup', 'migration']):
        return 'phoenix'

    if any(kw in task_lower for kw in ['review plan', 'review feature']):
        return 'sentinel'

    if any(kw in task_lower for kw in ['review refactor', 'review migration']):
        return 'warden'

    if any(kw in task_lower for kw in ['session', 'precedent', 'history', 'context']):
        return 'chronicler'

    if any(kw in task_lower for kw in ['deploy', 'release', 'version']):
        return 'herald'

    if any(kw in task_lower for kw in ['coordinate', 'orchestrate', 'multi-agent']):
        return 'maestro'

    # Default: hierarchical decomposition
    return 'kraken'
```

---

## Multi-File Atomicity

### Tiered Approach

Rigg provides multi-file atomicity through a tiered backup/restore mechanism:

| Tier | Mechanism | Survives | Use Case |
|------|-----------|----------|----------|
| 1 | Git stash | Process crash | Git repos |
| 2 | Custom snapshots | Process crash | Non-git dirs |
| 3 | Shadow copies (PostgreSQL) | Machine crash | Critical edits |

### Tier 1: Git Stash

```python
async def atomic_edit_git(files: list[str], edits: list[Edit]) -> None:
    """Atomic multi-file edit using git stash."""
    # Check if in git repo
    if not is_git_repo():
        return await atomic_edit_snapshot(files, edits)

    # Create stash point
    stash_id = subprocess.run(['git', 'stash', 'push', '-m', 'rigg-atomic-backup'])

    try:
        # Apply all edits
        for edit in edits:
            apply_edit(edit)

        # Verify all edits succeeded
        verify_edits(files)

    except Exception as e:
        # Rollback on failure
        subprocess.run(['git', 'stash', 'pop'])
        raise AtomicEditFailed(str(e))
```

### Tier 2: Custom Snapshots

```python
import tempfile
import shutil

async def atomic_edit_snapshot(files: list[str], edits: list[Edit]) -> None:
    """Atomic multi-file edit using temp directory snapshots."""

    # Create snapshot in temp dir
    snapshot_dir = tempfile.mkdtemp(prefix='rigg-snapshot-')

    try:
        # Copy original files
        for f in files:
            shutil.copy2(f, snapshot_dir)

        # Apply all edits
        for edit in edits:
            apply_edit(edit)

        # Verify all edits succeeded
        verify_edits(files)

    except Exception as e:
        # Rollback: restore from snapshot
        for f in files:
            original = os.path.join(snapshot_dir, os.path.basename(f))
            shutil.copy2(original, f)
        raise AtomicEditFailed(str(e))

    finally:
        shutil.rmtree(snapshot_dir)
```

### Tier 3: Shadow Copies (PostgreSQL)

```sql
-- Shadow copies table for crash-safe recovery
CREATE TABLE shadow_copies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    original_content TEXT NOT NULL,
    edit_content TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'applied', 'rolled_back')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMPTZ,
    UNIQUE(session_id, file_path, status) WHERE status = 'pending'
);
```

```python
async def atomic_edit_shadow(files: list[str], edits: list[Edit]) -> None:
    """Atomic multi-file edit with PostgreSQL shadow copies (crash-safe)."""

    session_id = os.environ.get("SESSION_ID")
    agent_id = os.environ.get("AGENT_ID")

    # Store shadow copies in PostgreSQL
    async with db.transaction():
        for f in files:
            content = Path(f).read_text()
            await db.execute("""
                INSERT INTO shadow_copies (session_id, agent_id, file_path, original_content)
                VALUES ($1, $2, $3, $4)
            """, session_id, agent_id, f, content)

    try:
        # Apply all edits
        for edit in edits:
            apply_edit(edit)

        # Mark as applied
        await db.execute("""
            UPDATE shadow_copies
            SET status = 'applied', applied_at = NOW()
            WHERE session_id = $1 AND agent_id = $2 AND status = 'pending'
        """, session_id, agent_id)

    except Exception as e:
        # Rollback from shadow copies
        shadows = await db.fetch("""
            SELECT file_path, original_content
            FROM shadow_copies
            WHERE session_id = $1 AND agent_id = $2 AND status = 'pending'
        """, session_id, agent_id)

        for shadow in shadows:
            Path(shadow['file_path']).write_text(shadow['original_content'])

        await db.execute("""
            UPDATE shadow_copies
            SET status = 'rolled_back'
            WHERE session_id = $1 AND agent_id = $2 AND status = 'pending'
        """, session_id, agent_id)

        raise AtomicEditFailed(str(e))
```

### Parallel Edits + Rebase

When multiple agents edit different files in parallel:

```python
async def parallel_atomic_edits(agent_edits: dict[str, list[Edit]]) -> None:
    """Coordinate parallel edits from multiple agents."""

    # Each agent works in isolation (temp directory)
    temp_dirs = {}
    for agent_id, edits in agent_edits.items():
        temp_dir = tempfile.mkdtemp(prefix=f'rigg-{agent_id}-')
        temp_dirs[agent_id] = temp_dir

        # Copy working files to temp
        for edit in edits:
            shutil.copy2(edit.file_path, temp_dir)

    # Apply edits in parallel (isolated)
    await asyncio.gather(*[
        apply_edits_in_temp(agent_id, edits, temp_dirs[agent_id])
        for agent_id, edits in agent_edits.items()
    ])

    # Rebase: merge temp results back to working directory
    conflicts = await rebase_from_temps(temp_dirs)

    if conflicts:
        # Spawn fixer agent for conflict resolution
        await spawn_fixer_agent(conflicts)
```

### Fixer Agent

When parallel edits conflict, spawn a fixer agent:

```python
async def spawn_fixer_agent(conflicts: list[Conflict]) -> None:
    """Spawn agent to resolve merge conflicts."""

    conflict_summary = "\n".join([
        f"- {c.file_path}: {c.agent_a} vs {c.agent_b}"
        for c in conflicts
    ])

    prompt = f"""
    Resolve these merge conflicts from parallel agent edits:

    {conflict_summary}

    For each conflict:
    1. Read both versions
    2. Understand the intent of each edit
    3. Merge intelligently (not just concatenate)
    4. Write the resolved file
    """

    await spawn_agent(prompt, allowed_tools=["Read", "Write", "Edit"])
```

---

## Integration with v3 Refactor

### Building on Existing Infrastructure

Rigg agent orchestration builds on top of the completed v3 refactor:

| v3 Component | Rigg Usage |
|--------------|------------|
| `scripts/claude_spawn.py` | Base spawning mechanism |
| PostgreSQL coordination | Agent tracking, blackboard |
| Redis cache | Hot blackboard polling |
| Hooks system | PreToolUse blackboard polling |
| `claude -p` CLI | Process isolation |

### Hook Registration

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": ["Bash", "Write", "Edit", "MultiEdit"],
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/blackboard-poll.sh"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/agent-cleanup.sh"
      }]
    }]
  }
}
```

### Agent Cleanup on Stop

```typescript
// .claude/hooks/src/agent-cleanup.ts
async function main() {
    const input = JSON.parse(await readStdin());
    const agentId = process.env.AGENT_ID;
    const sessionId = process.env.SESSION_ID;

    if (!agentId) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Mark agent as completed in PostgreSQL
    await db.execute(`
        UPDATE agents
        SET status = 'completed', completed_at = NOW()
        WHERE agent_id = $1
    `, agentId);

    // Clean up shadow copies
    await db.execute(`
        DELETE FROM shadow_copies
        WHERE agent_id = $1 AND status = 'applied'
    `, agentId);

    console.log(JSON.stringify({ result: 'continue' }));
}
```

---

## Conflict Resolution

### Discovery Conflicts

When an agent discovers information conflicting with global state:

1. Agent reports conflict to orchestrator via blackboard
2. Maestro synthesizes or escalates to user
3. No auto-override - user decides

### Swarm Contradictions

When parallel agents reach different conclusions:

1. All results written to blackboard
2. Maestro synthesizes or asks user
3. Majority vote only for simple binary decisions

---

## Handoff Format

YAML frontmatter + markdown body:

```yaml
---
agent: kraken
timestamp: 2026-01-01T12:00:00Z
resolved:
  - framework: react
  - database: postgres
unknowns:
  - auth_method: null
decision_matrix:
  - action: add_caching
    options:
      redis: {risk: 0.1, value: 0.9}
      memory: {risk: 0.05, value: 0.6}
diff:
  created: [src/api/routes.ts]
  modified: [src/index.ts]
spawn_next: null
---

## Context
One-sentence summary of what was done.

## Decisions Made
- Chose React over Vue because [reason]

## Open Questions
- UNCONFIRMED: Should auth use JWT or sessions?
```

---

## Workflow Examples

### Swarm Pattern (Research)

```python
async def execute_swarm(query: str, perspectives: list[str]) -> list[str]:
    """Spawn parallel research agents with different perspectives."""
    agents = []

    for perspective in perspectives:
        agent = spawn_agent(
            prompt=query,
            perspective=f"As {perspective} expert",
            allowed_tools=["Read", "Grep", "Glob", "WebSearch"],
        )
        agents.append(agent)

    # Wait for all
    results = await wait_for_all(agents, timeout=600)

    # Synthesize
    return synthesize_results(results)
```

### Jury Pattern (Voting)

```python
async def execute_jury(question: str, num_jurors: int = 3) -> dict:
    """Spawn voting agents for consensus decision."""
    agents = []

    for i in range(num_jurors):
        agent = spawn_agent(
            prompt=f"Vote on: {question}. Return JSON: {{vote: 'approve'|'reject', rationale: '...'}}",
            perspective=f"Juror {i+1}",
        )
        agents.append(agent)

    # Quorum-based: proceed if 2/3 complete
    results = await wait_for_quorum(agents, quorum=2, timeout=300)

    # Tally votes
    return tally_votes(results)
```

### Pipeline Pattern (Sequential)

```python
async def execute_pipeline(stages: list[str], initial_input: str) -> str:
    """Sequential stage execution with handoff."""
    result = initial_input

    for stage in stages:
        agent = spawn_agent(
            prompt=f"{stage}\n\nInput: {result}",
        )
        result = await wait_for_agent(agent, timeout=300)

    return result
```

### Onboard Workflow (Scout -> Scribe)

```python
# Onboard = Scout -> Scribe pipeline
pipeline = Pipeline(stages=[
    ("scout", "Explore codebase, detect tech stack"),
    ("scribe", "Create initial continuity ledger")
])
result = await pipeline.execute(initial_prompt)
```

---

## Files Created/Modified

### Files to Create

| File | Purpose |
|------|---------|
| `scripts/claude_spawn.py` | Spawn wrapper with tracking |
| `scripts/wait_agents.py` | Wait utilities (all, quorum, any) |
| `scripts/atomic_edit.py` | Multi-file atomicity |
| `.claude/hooks/src/blackboard-poll.ts` | PreToolUse polling hook |
| `.claude/hooks/src/agent-cleanup.ts` | Stop hook for cleanup |

### Files to Modify

| File | Changes |
|------|---------|
| `scripts/agentica_patterns/patterns.py` | Replace `spawn()` with `spawn_agent()` |
| `scripts/agentica_patterns/task_executor.py` | Use new spawning |
| `.claude/settings.json` | Register new hooks |
| `.claude/rules/agent-orchestration.md` | Reference `claude -p` pattern |

---

## References

- **v3 Refactor:** `docs/refactor/05-agent-orchestration.md`
- **Concurrency:** `docs/refactor/06-concurrency-coordination.md`
- **Patterns Reference:** `docs/architecture/PATTERNS.md`
- **Blackboard Schema:** `docs/refactor/06-concurrency-coordination.md#postgresql-schema`
