# V2 to V3 Upgrade Guide

This document details the major changes between V2 and V3 of the Claude Continuity Kit, providing a comprehensive guide for users upgrading their setups.

---

## Overview

V3 introduces a complete multi-agent orchestration system built on the Agentica SDK. The key enhancements include:

| Category | V2 | V3 |
|----------|----|----|
| **Agent Patterns** | Single agent execution | 11 multi-agent orchestration patterns |
| **Skills** | Basic skill discovery | Intelligent trigger system with `skill-rules.json` |
| **Hooks** | Simple lifecycle hooks | Pattern-aware routing with environment variables |
| **Agents** | Ad-hoc agent definitions | 16+ predefined agent types in `.claude/agents/` |
| **Tracing** | Basic logging | Full Braintrust integration with span hierarchy |
| **Coordination** | File-based handoffs | SQLite-backed CoordinationDB with tracked agents |

---

## 1. Pattern System (11 Orchestration Patterns)

V3 implements a comprehensive multi-agent pattern library in `scripts/agentica/patterns/`. Each pattern is designed for specific task types and includes hook integration for observability.

### 1.1 Core Patterns

#### Swarm Pattern (`patterns/swarm.py`)
Spawn multiple agents with different perspectives in parallel, then aggregate results.

```python
from scripts.agentica.patterns.swarm import Swarm
from scripts.agentica.patterns.primitives import AggregateMode

swarm = Swarm(
    perspectives=[
        "You are a security expert.",
        "You are a performance expert.",
        "You are a UX expert."
    ],
    aggregate_mode=AggregateMode.MERGE,
    fail_fast=False
)
result = await swarm.execute("Analyze OAuth implementation")
```

**Environment Variables Set:**
- `PATTERN_TYPE=swarm`
- `SWARM_ID=<unique_id>`
- `AGENT_ROLE=worker`

**Use When:** Research, exploration, needing diverse perspectives, time-sensitive parallel work.

---

#### Hierarchical Pattern (`patterns/hierarchical.py`)
Coordinator decomposes tasks for specialist agents in a tree structure.

```python
from scripts.agentica.patterns.hierarchical import Hierarchical

hierarchical = Hierarchical(
    coordinator_premise="You break tasks into subtasks.",
    specialist_premises={
        "researcher": "You research topics.",
        "analyst": "You analyze data."
    }
)
result = await hierarchical.execute("Research and analyze topic X")
```

**Flow:**
1. Coordinator decomposes task into subtasks
2. Specialists execute subtasks (parallel when independent)
3. Results are aggregated
4. Coordinator synthesizes final answer

**Environment Variables Set:**
- `PATTERN_TYPE=hierarchical`
- `HIERARCHY_ID=<unique_id>`
- `AGENT_ROLE=coordinator|specialist`
- `HIERARCHY_LEVEL=<n>` (0 = coordinator)

---

#### Jury Pattern (`patterns/jury.py`)
N independent agents vote on a question via Consensus mechanism.

```python
from scripts.agentica.patterns.jury import Jury
from scripts.agentica.patterns.primitives import ConsensusMode

jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.MAJORITY
)
verdict = await jury.decide(bool, "Is this code safe?")
```

**Consensus Modes:**
- `MAJORITY`: Most common vote wins
- `UNANIMOUS`: All votes must agree
- `THRESHOLD`: Percentage of votes must agree

**Use When:** High-stakes decisions, reducing hallucination, validation tasks.

---

#### Generator/Critic Pattern (`patterns/generator_critic.py`)
Iterative refinement loop between generator and critic agents.

```python
from scripts.agentica.patterns.generator_critic import GeneratorCritic

gc = GeneratorCritic(
    generator_premise="You generate Python code.",
    critic_premise="You review Python code for correctness.",
    max_rounds=3
)
result = await gc.run("Create a function to parse JSON")
```

**Flow:**
1. Generator creates initial solution
2. Critic evaluates and provides feedback
3. Generator refines based on feedback
4. Repeat until critic approves or max_rounds reached

---

#### Pipeline Pattern (`patterns/pipeline.py`)
Sequential stage execution with HandoffState between stages.

```python
from scripts.agentica.patterns.pipeline import Pipeline
from scripts.agentica.patterns.primitives import HandoffState

async def fetch(state: HandoffState) -> HandoffState:
    state.add_artifact("data", fetch_data())
    return state

async def transform(state: HandoffState) -> HandoffState:
    data = state.artifacts["data"]
    state.add_artifact("transformed", transform(data))
    return state

pipeline = Pipeline(stages=[fetch, transform])
result = await pipeline.run(initial_state)
```

**Environment Variables Set:**
- `PATTERN_TYPE=pipeline`
- `PIPELINE_STAGE_INDEX=<n>`
- `PIPELINE_TOTAL_STAGES=<n>`

---

### 1.2 Specialized Patterns

#### MapReduce Pattern (`patterns/map_reduce.py`)
Fan out work to N mapper agents in parallel, then combine with reducer.

```python
from scripts.agentica.patterns.map_reduce import MapReduce

mr = MapReduce(
    mapper_premise="You analyze one section of code.",
    reducer_premise="You synthesize analysis from multiple reviewers.",
    num_mappers=4
)
result = await mr.execute("Review codebase", chunks=["file1.py", "file2.py"])
```

**Use When:** Parallel processing of independent subtasks, batch analysis.

---

#### Blackboard Pattern (`patterns/blackboard.py`)
Multiple specialists contribute to shared state monitored by a controller.

```python
from scripts.agentica.patterns.blackboard import Blackboard, Specialist

bb = Blackboard(
    specialists=[
        Specialist(premise="You analyze requirements.", writes_to=["requirements"]),
        Specialist(premise="You design architecture.", writes_to=["architecture"], reads_from=["requirements"]),
    ],
    controller_premise="You check if the design is complete.",
    max_iterations=5
)
result = await bb.solve("Build a user authentication system")
```

**Use When:** Collaborative problem solving, emergent solutions.

---

#### Circuit Breaker Pattern (`patterns/circuit_breaker.py`)
Failure detection with automatic fallback routing.

```python
from scripts.agentica.patterns.circuit_breaker import CircuitBreaker

cb = CircuitBreaker(
    primary_premise="You implement features.",
    fallback_premise="You implement simpler versions.",
    max_failures=3,
    reset_timeout=60
)
result = await cb.execute("Implement OAuth flow")
```

**States:**
- `CLOSED`: Normal operation, primary agent used
- `OPEN`: Primary failed too many times, fallback used
- `HALF_OPEN`: Testing primary after timeout

---

#### Adversarial Pattern (`patterns/adversarial.py`)
Agents take opposing positions to stress-test ideas through debate.

```python
from scripts.agentica.patterns.adversarial import Adversarial

adv = Adversarial(
    advocate_premise="You argue in favor of this decision.",
    adversary_premise="You find flaws in decisions.",
    judge_premise="You decide which position is stronger.",
    max_rounds=3
)
result = await adv.resolve("Microservices or monolith?")
```

**Use When:** Security review, stress testing ideas, finding edge cases.

---

#### Chain of Responsibility Pattern (`patterns/chain_of_responsibility.py`)
Route request to first handler that can process it.

```python
from scripts.agentica.patterns.chain_of_responsibility import ChainOfResponsibility, Handler

chain = ChainOfResponsibility(handlers=[
    Handler(premise="Python expert", can_handle=lambda q: "python" in q.lower()),
    Handler(premise="JavaScript expert", can_handle=lambda q: "javascript" in q.lower()),
    Handler(premise="General programmer", can_handle=lambda q: True),  # fallback
])
result = await chain.process("How do I use async in Python?")
```

**Use When:** Capability matching, tiered support, cost optimization.

---

#### Event-Driven Pattern (`patterns/event_driven.py`)
Agents react to events published on a bus with loose coupling.

```python
from scripts.agentica.patterns.event_driven import EventDriven, Event, Subscriber

bus = EventDriven(subscribers=[
    Subscriber(premise="Handle user events.", event_types=["user.created"]),
    Subscriber(premise="Log all events.", event_types=["*"]),  # wildcard
])
await bus.publish(Event(type="user.created", payload={"user_id": "123"}))
```

**Use When:** Monitoring, reactive systems, async workflows.

---

### 1.3 Primitives

All patterns share common primitives in `patterns/primitives.py`:

#### Consensus
```python
from scripts.agentica.patterns.primitives import Consensus, ConsensusMode

consensus = Consensus(mode=ConsensusMode.MAJORITY)
winner = consensus.decide(votes=[True, True, False])
```

#### Aggregator
```python
from scripts.agentica.patterns.primitives import Aggregator, AggregateMode

aggregator = Aggregator(mode=AggregateMode.MERGE)
merged = aggregator.aggregate([{"a": 1}, {"b": 2}])  # {"a": 1, "b": 2}
```

#### HandoffState
```python
from scripts.agentica.patterns.primitives import HandoffState

state = HandoffState(
    context="Current task context",
    next_instruction="What to do next"
)
state.add_artifact("key", "value")
state.record_handoff("agent1", "agent2")
```

---

## 2. Skills System Upgrades

### 2.1 New Skills (V3)

V3 adds 41+ skills in `.claude/skills/`. Key new additions:

| Skill | Description |
|-------|-------------|
| `agentica-sdk` | Build Python agents with @agentic decorator, spawn(), MCP integration |
| `agentica-spawn` | Spawn multi-agent patterns (Swarm, Hierarchical, Jury, etc.) |
| `agentica-claude-proxy` | SSE streaming, --allowedTools, anti-hallucination prompts |
| `agentica-server` | Server + proxy setup, architecture, startup sequence |
| `agentica-prompts` | Write reliable prompts for Agentica/REPL agents |
| `braintrust-analyze` | Session analysis, agent stats, loop detection |
| `braintrust-tracing` | Trace hierarchy, sub-agent correlation, debugging |
| `research-codebase` | Document codebase as-is with parallel sub-agents |
| `token-burn-debug` | Diagnose and fix token/context burn issues |
| `debug-hooks` | Systematic hook debugging workflow |

### 2.2 Skill Rules System

V3 introduces `skill-rules.json` for intelligent skill activation based on user intent.

**Location:** `.claude/skills/skill-rules.json`

**Structure:**
```json
{
  "version": "1.0",
  "skills": {
    "skill-name": {
      "type": "domain",
      "enforcement": "suggest|block|warn",
      "priority": "critical|high|medium|low",
      "description": "Brief description",
      "promptTriggers": {
        "keywords": ["trigger", "words"],
        "intentPatterns": ["regex patterns"]
      }
    }
  },
  "agents": {
    "agent-name": {
      "type": "exploration|research|planning|debugging",
      "enforcement": "suggest",
      "promptTriggers": {...}
    }
  }
}
```

**Enforcement Types:**
- `suggest`: Skill suggestion appears but doesn't block
- `block`: Requires skill to be used before proceeding (guardrail)
- `warn`: Shows warning but allows proceeding

**Example Trigger:**
```json
"agentica-sdk": {
  "promptTriggers": {
    "keywords": ["agentica", "@agentic", "spawn agent", "python agent"],
    "intentPatterns": [
      "(build|create|make).*?(agent|agentic).*?python",
      "spawn.*?agent"
    ]
  }
}
```

---

## 3. Hook System Upgrades

### 3.1 New Hook Events

V3 adds pattern-aware hooks that route based on `PATTERN_TYPE` environment variable.

**New Hook Files:**

| Hook | Purpose |
|------|---------|
| `stop-coordinator.ts` | Pattern-aware router for Stop events |
| `subagent-start-swarm.ts` | Agent joining swarm notification |
| `subagent-stop-swarm.ts` | Agent leaving swarm, broadcast coordination |
| `session-end-cleanup-swarms.ts` | Cleanup swarm state on session end |
| `post-task-complete.ts` | Handle Task tool completion events |
| `pre-tool-use-broadcast.ts` | Broadcast tool use to swarm members |

### 3.2 Pattern-Aware Routing

The `stop-coordinator.ts` routes Stop events to pattern-specific handlers:

```typescript
// Detection via environment
const pattern = detectPattern(); // reads PATTERN_TYPE

switch (pattern) {
  case 'swarm':
    output = await swarm.onStop(input);
    break;
  case 'jury':
    output = await jury.onStop(input);
    break;
  case 'pipeline':
    output = await handlePipelineStop(input);
    break;
  // ... other patterns
}
```

### 3.3 Shared Hook Utilities

New shared modules in `.claude/hooks/src/shared/`:

```
shared/
  pattern-router.ts    # Pattern detection from env vars
  db-utils.ts          # CoordinationDB query utilities
  types.ts             # Shared TypeScript interfaces
```

### 3.4 Hook Registration (settings.json)

V3 hooks are registered in `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stop-coordinator.sh"
      }]
    }],
    "SubagentStart": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/subagent-start.sh"
      }]
    }],
    "SubagentStop": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/subagent-stop.sh"
      }]
    }]
  }
}
```

---

## 4. Agent Types

V3 defines 16+ agent types in `.claude/agents/`:

### 4.1 Exploration Agents

| Agent | Purpose |
|-------|---------|
| `rp-explorer` | Token-efficient codebase exploration with RepoPrompt |
| `codebase-analyzer` | Deep dive on specific components, trace data flow |
| `codebase-locator` | Find files, directories, and components |
| `codebase-pattern-finder` | Find similar implementations and usage examples |

### 4.2 Research Agents

| Agent | Purpose |
|-------|---------|
| `research-agent` | Comprehensive research using MCP tools |
| `research-codebase` | Document codebase as-is with parallel sub-agents |
| `repo-research-analyst` | Analyze repository structure and conventions |

### 4.3 Planning and Implementation

| Agent | Purpose |
|-------|---------|
| `plan-agent` | Create implementation plans |
| `validate-agent` | Validate plan tech choices against best practices |
| `agentica-agent` | Build Python agents using Agentica SDK |

### 4.4 Debugging and Analysis

| Agent | Purpose |
|-------|---------|
| `debug-agent` | Investigate issues using codebase exploration |
| `braintrust-analyst` | Analyze traced sessions |
| `session-analyst` | Review session patterns and learnings |

### 4.5 Agent Definition Format

Agent definitions in `.claude/agents/*.md`:

```markdown
---
name: agent-name
description: Brief description
model: sonnet
tools: [Bash, Read, Write, Edit, Glob, Grep]
---

# Agent Name

Description and purpose.

## Step 1: Setup
...

## Step 2: Execute
...

## Output Location
Where results are written.

## Rules
Constraints and guidelines.
```

---

## 5. Braintrust Integration

### 5.1 Tracing Architecture

V3 provides full session tracing with span hierarchy:

```
Session (task span) - root_span_id = session_id
|
+-- Turn 1 (task span)
|   |
|   +-- claude-sonnet (llm span)
|   +-- Read (tool span)
|   +-- Edit (tool span)
|
+-- Turn 2 (task span)
|   |
|   +-- Task (tool span) --> [Sub-agent session]
```

### 5.2 Hook Event Flow

| Hook | Creates | Key Fields |
|------|---------|------------|
| SessionStart | Root span | `session_id`, `root_span_id` |
| UserPromptSubmit | Turn span | `prompt`, `turn_number` |
| PostToolUse | Tool span | `tool_name`, `input`, `output` |
| Stop | LLM spans | `model`, `tokens`, `tool_calls` |
| SessionEnd | (finalizes) | `turn_count`, `tool_count` |

### 5.3 Analysis Commands

```bash
# Analyze last session
uv run python -m runtime.harness scripts/braintrust_analyze.py --last-session

# List recent sessions
uv run python -m runtime.harness scripts/braintrust_analyze.py --sessions 5

# Agent usage statistics
uv run python -m runtime.harness scripts/braintrust_analyze.py --agent-stats

# Detect loops (repeated tool patterns)
uv run python -m runtime.harness scripts/braintrust_analyze.py --detect-loops

# Weekly summary
uv run python -m runtime.harness scripts/braintrust_analyze.py --weekly-summary
```

### 5.4 Configuration

Environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `TRACE_TO_BRAINTRUST` | Yes | Set to `"true"` to enable |
| `BRAINTRUST_API_KEY` | Yes | API key for Braintrust |
| `BRAINTRUST_CC_PROJECT` | No | Project name (default: `claude-code`) |
| `BRAINTRUST_CC_DEBUG` | No | Verbose logging |

---

## 6. Migration Guide

### 6.1 Required Steps

1. **Update dependencies**
   ```bash
   uv sync --all-extras
   ```

2. **Regenerate hooks**
   ```bash
   cd .claude/hooks && npm run build
   ```

3. **Update settings.json**
   Add new hooks to your `.claude/settings.json`:
   ```json
   {
     "hooks": {
       "SubagentStart": [...],
       "SubagentStop": [...],
       "Stop": [...]
     }
   }
   ```

4. **Set environment variables**
   Add to `.env`:
   ```bash
   TRACE_TO_BRAINTRUST=true
   BRAINTRUST_API_KEY=your-key
   ```

### 6.2 Optional Upgrades

1. **Enable pattern-aware hooks**
   - Add pattern environment variables to your custom hooks
   - Use `detectPattern()` from shared utilities

2. **Use CoordinationDB**
   ```python
   from scripts.agentica.coordination import CoordinationDB

   db = CoordinationDB()
   swarm = Swarm(perspectives=[...], db=db)
   ```

3. **Migrate to new skill triggers**
   - Update custom skills to use `skill-rules.json` format
   - Add `promptTriggers` for automatic activation

### 6.3 Code Changes

**V2 pattern (single agent):**
```python
result = await agent.call(str, "Analyze this code")
```

**V3 pattern (multi-agent):**
```python
from scripts.agentica.patterns.swarm import Swarm

swarm = Swarm(perspectives=[
    "Security analysis perspective",
    "Performance analysis perspective"
])
result = await swarm.execute("Analyze this code")
```

---

## 7. Breaking Changes

### 7.1 Environment Variable Requirements

V3 patterns require specific environment variables for hook routing:

| Pattern | Required Env Vars |
|---------|------------------|
| Swarm | `PATTERN_TYPE=swarm`, `SWARM_ID` |
| Jury | `PATTERN_TYPE=jury`, `JURY_ID`, `TOTAL_JURORS` |
| Pipeline | `PATTERN_TYPE=pipeline`, `PIPELINE_STAGE_INDEX` |
| All patterns | `PATTERN_ID`, `AGENT_ROLE` |

### 7.2 Hook Input Schema Changes

New hooks expect additional fields:

```typescript
interface StopInput {
  session_id: string;
  stop_hook_active?: boolean;  // New: prevents infinite loops
  // ...
}

interface SubagentStartInput {
  session_id: string;
  agent_id?: string | null;  // New: may be missing in older versions
  agent_type?: string;
}
```

### 7.3 Skill Rules Format

V2 skills without triggers in `skill-rules.json` will not auto-activate. Add entries for all custom skills.

### 7.4 CoordinationDB Schema

If using CoordinationDB from V2, tables may need migration:

```sql
-- New tables in V3
CREATE TABLE IF NOT EXISTS jury_votes (...);
CREATE TABLE IF NOT EXISTS pipeline_stages (...);
CREATE TABLE IF NOT EXISTS blackboard_state (...);
```

---

## 8. File Reference

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `scripts/agentica/patterns/` | 11 multi-agent patterns |
| `.claude/skills/` | 41+ skill definitions |
| `.claude/agents/` | 16+ agent definitions |
| `.claude/hooks/src/` | TypeScript hook implementations |
| `.claude/hooks/src/shared/` | Shared hook utilities |
| `.claude/hooks/src/patterns/` | Pattern-specific hook handlers |

### Key Files

| File | Purpose |
|------|---------|
| `scripts/agentica/PATTERNS.md` | Pattern reference documentation |
| `.claude/skills/skill-rules.json` | Skill activation triggers |
| `.claude/settings.json` | Hook registration |
| `scripts/braintrust_analyze.py` | Session analysis CLI |

---

## Summary

V3 transforms the Claude Continuity Kit from a single-agent system into a comprehensive multi-agent orchestration platform. Key benefits:

1. **11 orchestration patterns** for any task type
2. **Intelligent skill activation** via trigger rules
3. **Pattern-aware hooks** for observability
4. **Full Braintrust tracing** with span hierarchy
5. **Predefined agents** for common workflows

Users upgrading from V2 should:
1. Review the pattern library to identify applicable patterns
2. Update `skill-rules.json` for custom skills
3. Add new hook registrations to `settings.json`
4. Configure Braintrust environment variables for tracing
