# Module: Agent Orchestration

## Overview

Replace Agentica SDK `spawn()` with `claude -p` via Bash for true process isolation.

> **Reference**: See [00-architecture-decisions.md](./00-architecture-decisions.md) for foundational decisions on agent roster, spawn coordination, and routing.

---

## Spawning Mechanism

### Command Pattern

```bash
# Basic spawn
claude -p "Your task description" --output-format json > /tmp/agent-$ID.json &

# With allowed tools restriction
claude -p "Research task" --allowedTools "Read,Grep,Glob" --output-format json &

# Capture PID for tracking
PID=$!
echo "$PID" >> /tmp/agent-pids.txt
```

### Python Wrapper

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
    """Spawn a headless Claude agent."""

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
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "SESSION_ID": os.environ.get("SESSION_ID"),
    })

    with open(output_file, 'w') as f:
        proc = subprocess.Popen(cmd, stdout=f, env=env)

    # Register in CoordinationDB
    register_agent(agent_id, pid=proc.pid, parent=env["PARENT_AGENT_ID"])

    return SpawnedAgent(
        pid=proc.pid,
        agent_id=agent_id,
        output_file=output_file,
        depth_level=depth_level + 1,
    )
```

---

## Session Isolation

```
MAX_AGENTS_PER_SESSION = 4
```

Each session gets an isolated agent pool. No cross-session resource contention. The `SESSION_ID` **MUST** be passed through ALL spawned agents to maintain isolation boundaries.

---

## Nesting Limits

| Level | Description | Max Agents |
|-------|-------------|------------|
| 0 | Main orchestrator (user session) | 1 |
| 1 | Direct headless agents | Dynamic (resource-based) |
| 2 | Sub-agents spawned by level 1 | Dynamic (resource-based) |
| 3 | **HARD LIMIT** - spawn rejected | 0 |

### Enforcement

```python
def check_spawn_allowed() -> bool:
    depth = int(os.environ.get("DEPTH_LEVEL", "0"))
    if depth >= 3:
        return False  # Hard reject

    # Dynamic resource check
    cpu_available = psutil.cpu_percent() < 80
    mem_available = psutil.virtual_memory().percent < 85

    return cpu_available and mem_available
```

---

## Environment Variables

| Variable | Description | Set By |
|----------|-------------|--------|
| `DEPTH_LEVEL` | Current nesting depth (0-3) | Parent agent |
| `AGENT_ID` | UUID of this agent | Spawn wrapper |
| `PARENT_AGENT_ID` | UUID of parent | Spawn wrapper |
| `SESSION_ID` | Root session identifier | Orchestrator |
| `DATABASE_URL` | PostgreSQL connection | Inherited |
| `PATTERN_TYPE` | Current pattern (swarm, jury, etc.) | Orchestrator |

---

## Pattern Implementation

### Swarm (Parallel Research)

```python
async def execute_swarm(query: str, perspectives: list[str]) -> list[str]:
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

### Jury (Voting)

```python
async def execute_jury(question: str, num_jurors: int = 3) -> dict:
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

### Pipeline (Sequential)

```python
async def execute_pipeline(stages: list[str], initial_input: str) -> str:
    result = initial_input

    for stage in stages:
        agent = spawn_agent(
            prompt=f"{stage}\n\nInput: {result}",
        )
        result = await wait_for_agent(agent, timeout=300)

    return result
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/agentica_patterns/patterns.py` | Replace `spawn()` with `spawn_agent()` |
| `scripts/agentica_patterns/patterns/*.py` | Update all pattern modules |
| `scripts/agentica_patterns/task_executor.py` | Use new spawning |
| `.claude/rules/agent-orchestration.md` | Update to reference `claude -p` |

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/claude_spawn.py` | Spawn wrapper with tracking |
| `scripts/wait_agents.py` | Wait utilities (all, quorum, any) |

---

## Agent Routing (Deterministic)

Instead of probabilistic meta-learning, use deterministic trigger->agent mappings.

### Routing Philosophy

1. **Keyword matching FIRST** - Instant, covers 80% of cases
2. **LLM classification FALLBACK** - Handles edge cases (~500ms)
3. **NOT erotetic** - Erotetic is for parameter extraction, not routing

### Routing Table

| Activity | Trigger Words | Agent |
|----------|--------------|-------|
| Implement (complex) | implement, build, create | Kraken |
| Implement (simple) | fix, tweak, update, small | Spark |
| Document | document, handoff, summarize, ledger | Scribe |
| Debug | debug, investigate, error, bug | Sleuth |
| Security | security, vulnerability, CVE, audit | Aegis |
| Performance | slow, performance, memory, race, profile | Profiler |
| Validate | test, validate, verify, unit, integration | Arbiter |
| E2E Test | e2e, end-to-end, acceptance | Atlas |
| Research (external) | research, learn, best practices, NIA | Oracle |
| Research (internal) | find, locate, where, codebase | Scout |
| Research (repo) | analyze repo, external repo, github | Pathfinder |
| Plan Feature | plan feature, design, new, integration | Architect |
| Plan Refactor | plan refactor, cleanup, migration | Phoenix |
| Review Architect | review plan, review feature | Sentinel |
| Review Phoenix | review refactor, review migration | Warden |
| Session Analysis | session, precedent, history, context | Chronicler |
| Deploy | deploy, release, version | Herald |
| Orchestrate | coordinate, orchestrate, multi-agent | Maestro |

### Implementation

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

---

## Agent Roster (V3)

### Final Roster: 18 Agents

| Domain | Agent | Role |
|--------|-------|------|
| **Implement** | Kraken | Large TDD implementation |
| | Spark | Small fixes |
| **Document** | Scribe | Docs, handoffs, ledgers |
| **Debug** | Sleuth | General investigation |
| | Aegis | Security analysis |
| | Profiler | Performance issues (renamed from Turbo) |
| **Validate** | Arbiter | Unit/integration tests |
| | Atlas | E2E tests |
| **Research** | Oracle | External (wraps NIA API) |
| | Scout | Internal codebase |
| | Pathfinder | External repo analysis |
| **Plan** | Architect | Build: new features + integrations |
| | Phoenix | Change: refactors + migrations |
| **Review** | Sentinel | Reviews Architect's plans |
| | Warden | Reviews Phoenix's plans |
| **Session** | Chronicler | Session analysis + precedent lookup |
| **Deploy** | Herald | Release prep |
| **Orchestrate** | Maestro | Pure coordinator (no direct work) |

### Agent Categories

| Category | Agents | Can Spawn? |
|----------|--------|------------|
| **Leads (5)** | Kraken, Architect, Phoenix, Herald, Maestro | Yes (depth check) |
| **Workers (13)** | Spark, Scribe, Sleuth, Aegis, Profiler, Arbiter, Atlas, Oracle, Scout, Pathfinder, Sentinel, Warden, Chronicler | No (leaf nodes) |

> **Note**: Only the 5 Leads can spawn other agents. Workers are leaf nodes that execute tasks without spawning.

---

## Spawn Control

### SpawnQueue Architecture

**Redis (hot)** + **PostgreSQL (durable)**:
- Redis: Hot polling at 100ms intervals for low-latency spawn requests
- PostgreSQL: Durability and audit trail for all spawn decisions

### Deterministic Coordinator (Not LLM)

```python
# coordinator.py
class SpawnCoordinator:
    def request_spawn(self, requester: str, target: str, depth: int) -> bool:
        # Hard depth limit
        if depth >= 3:
            return False

        # Leads only at depth 0-1
        if is_lead(target) and depth >= 2:
            return False

        # Resource check
        if not resources_available():
            return False

        return True
```

### SpawnQueue Polling

Agents request spawns via SpawnQueue (Redis + PostgreSQL):
1. Agent writes `{need_spawn: {type: "scout", reason: "research needed"}}` to Redis
2. Coordinator polls Redis every 100ms
3. Coordinator applies rules, writes approval/rejection
4. Decision persisted to PostgreSQL for audit
5. Agent polls for response, proceeds or escalates

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

## Workflow Patterns

### Pipeline (used for Onboard)

Onboard = Scout -> Scribe pipeline:
```python
pipeline = Pipeline(stages=[
    ("scout", "Explore codebase, detect tech stack"),
    ("scribe", "Create initial continuity ledger")
])
result = await pipeline.execute(initial_prompt)
```

---

## Conflict Resolution

### Discovery Conflicts
When agent discovers info conflicting with global state:
1. Agent reports conflict to orchestrator via blackboard
2. Maestro synthesizes or escalates to user
3. No auto-override - user decides

### Swarm Contradictions
When parallel agents reach different conclusions:
1. All results written to blackboard
2. Maestro synthesizes or asks user
3. Majority vote only for simple binary decisions

---

## Deleted Agents (Replaced)

| Deleted | Absorbed By |
|---------|-------------|
| codebase-analyzer, codebase-locator, codebase-pattern-finder | Scout (as scripts) |
| repo-research-analyst | Pathfinder |
| session-analyst, braintrust-analyst, context-query-agent | Chronicler |
| validate-agent, review-agent | Arbiter, Sentinel/Warden |
| nexus, pioneer, critic, judge, surveyor, liaison | Merged into Architect, Phoenix, Sentinel, Warden |
| onboard | Workflow: Scout -> Scribe |
| turbo | Renamed to Profiler |
