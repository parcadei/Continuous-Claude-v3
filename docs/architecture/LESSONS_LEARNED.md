# Lessons Learned: Building the Claude Continuity Kit

This document captures key insights from building the Agentica integration, multi-agent orchestration patterns, and context management system.

## Agent Design

### Instructions Beat Personas (4x More Effective)

**Pattern:** Structured DO/DON'T instructions outperform personality-based prompts.

**Example:**
```python
# WEAK (personality-driven)
premise = "You are a world-renowned security expert with decades of experience..."

# STRONG (instruction-driven)
premise = """Security Agent: Analyze code for vulnerabilities.

DO:
- Check for SQL injection patterns
- Verify input validation
- Flag hardcoded credentials

DON'T:
- Suggest architectural rewrites
- Recommend libraries without version checks
- Ignore false positive patterns
"""
```

**Why it works:**
- Reduces hallucination (specific guardrails)
- Faster inference (less token overhead)
- Easier to test (clear success criteria)
- Better failure modes (agent knows when to escalate)

**Source:** Testing across swarm, hierarchical, and jury patterns showed 4x better task completion with instruction-based premises.

---

### The build_premise() Pattern

**Pattern:** Separate premise construction from agent spawning for composability.

```python
def build_security_premise(rules: list[str], context: dict) -> str:
    """Build premise from rules and runtime context."""
    base = "Security Agent: Analyze code.\n\n"
    dos = "\n".join(f"- {rule}" for rule in rules)
    context_str = "\n".join(f"Context: {k}={v}" for k, v in context.items())
    return f"{base}DO:\n{dos}\n\n{context_str}"

# Reusable across agents
agent1 = await spawn(premise=build_security_premise(sql_rules, db_context))
agent2 = await spawn(premise=build_security_premise(xss_rules, web_context))
```

**Benefits:**
- Test premise generation separately from agent execution
- Version control for premise templates
- Runtime adaptation (add rules based on context)
- A/B testing different instruction sets

**Source:** `scripts/agentica/patterns.py` - all pattern classes use this approach.

---

## Testing Patterns

### TDD with Existing Tests = Implementation Target

**Pattern:** Write tests BEFORE implementing patterns to drive API design.

```python
# tests/unit/test_agentica_hierarchical.py
# Written BEFORE patterns.py implementation

async def test_hierarchical_creation():
    """Can create a Hierarchical coordinator."""
    hierarchical = Hierarchical(
        coordinator_premise="Break tasks into subtasks.",
        specialist_premises={
            "researcher": "Research topics.",
            "analyst": "Analyze data."
        }
    )
    assert hierarchical is not None
    assert len(hierarchical.specialist_premises) == 2
```

**Why it works:**
- Tests document expected API before any code exists
- Forces thinking about ergonomics upfront
- Creates immediate feedback loop (watch tests turn green)
- Prevents over-engineering (implement minimum to pass tests)

**Example workflow:**
1. Write 10-15 test cases describing desired behavior
2. Run tests (all fail - expected)
3. Implement pattern class
4. Watch tests pass one by one
5. Refactor with safety net

**Source:** All pattern implementations (`test_agentica_*.py` files) follow this approach.

---

### Mutation Testing Catches Gaps Unit Tests Miss

**Pattern:** After unit tests pass, introduce bugs to verify tests actually catch them.

```python
# Original implementation
def _decide_unanimous(self, votes, vote_counts):
    if len(vote_counts) == 1:
        return votes[0]
    raise ConsensusNotReached("Votes not unanimous")

# Mutation: Remove uniqueness check
def _decide_unanimous(self, votes, vote_counts):
    # BUG: Always returns first vote, doesn't check consensus
    return votes[0]
```

**Test coverage gaps revealed:**
- 100% line coverage but logic bugs slip through
- Edge cases not tested (empty lists, single votes, ties)
- Error paths not verified (does it raise the right exception?)

**Fix:** Add mutation-specific tests
```python
def test_unanimous_rejects_split_vote():
    """Unanimous fails when votes differ."""
    consensus = Consensus(ConsensusMode.UNANIMOUS)
    with pytest.raises(ConsensusNotReached):
        consensus.decide([True, False])  # This MUST fail
```

**Source:** Consensus voting implementation revealed this during code review.

---

### Triple-Check Assumptions with NIA

**Pattern:** Before implementing, verify assumptions about libraries with NIA documentation search.

```bash
# Before assuming Agentica spawn() is lazy
uv run python -m runtime.harness scripts/nia_docs.py \
    --package agentica \
    --query "spawn lazy initialization when is agent created"
```

**Catches:**
- API changes between versions
- Misunderstanding from blog posts
- Deprecated patterns
- Subtle behavior differences (lazy vs eager, sync vs async)

**Example:** Assumed `spawn()` was lazy (creates agent on first call), but NIA confirmed it's eager (creates agent immediately). Changed design to use `Agent()` constructor for lazy patterns.

**Source:** Used extensively during Agentica SDK integration research.

---

## Context Management

### Task (Foreground) > TaskOutput (Streams Full Transcript)

**Pattern:** Use foreground tasks to keep agent work in isolated context.

```python
# WRONG: Background agents accumulate full transcripts
Task(
    subagent_type="implementation",
    run_in_background=True  # 70k+ token transcript floods main context
)
result = TaskOutput(task_id)  # Dumps entire transcript

# RIGHT: Foreground task returns summary only
Task(
    subagent_type="implementation",
    run_in_background=False  # Isolated context
)
# Agent completes, returns summary (~200 tokens)
```

**Why background mode fails:**
- Transcripts accumulate every tool call, thought, retry
- TaskOutput() dumps this into main context
- Triggers mid-conversation compaction
- Loses track of user's original request

**Source:** Session a8b5a799 - background agents caused context flush during implementation.

---

### Agent Context Isolation Prevents Pollution

**Pattern:** Never read agent output files directly. Verify with tests instead.

```bash
# WRONG: Dumps 70k tokens into context
Read("/tmp/claude/.../tasks/<id>.output")

# RIGHT: Verify with executable tests
Bash("npm test")
Bash("cargo test")
Bash("uv run pytest tests/unit/test_*.py -v")
```

**Why reading outputs fails:**
- Agent output files contain full execution logs
- Tool calls, errors, retries all present
- Defeats the purpose of context isolation
- Main conversation should only see summary

**Source:** Global rule `agent-context-isolation.md` - accumulated from multiple sessions.

---

### Directory-Based Handoffs Between Pipeline Stages

**Pattern:** Agents communicate via filesystem, not return values.

```python
# Coordinator writes handoff
@dataclass
class HandoffState:
    stage: str
    research_findings: dict[str, Any]
    next_agent: str
    context: dict[str, Any]

def write_handoff(state: HandoffState, path: Path):
    """Write handoff state to filesystem."""
    with open(path, "w") as f:
        json.dump(asdict(state), f, indent=2)

# Next agent reads handoff
def read_handoff(path: Path) -> HandoffState:
    with open(path, "r") as f:
        data = json.load(f)
    return HandoffState(**data)
```

**Benefits:**
- Persistent (survives crashes, allows resume)
- Observable (humans can inspect handoffs)
- Testable (mock handoffs without running full pipeline)
- Debuggable (see exactly what agent A passed to agent B)

**Source:** `scripts/agentica/primitives.py` - HandoffState dataclass used across all pipeline patterns.

---

## Architecture Insights

### REPL + Scope Sharing = The Key Insight

**Pattern:** Agents share a REPL environment where function calls persist across turns.

```python
# Create scope with memory and task functions
scope = create_agent_scope(session_id="research")

# Spawn agent with scope
agent = await spawn(
    premise="Research assistant with memory.",
    scope=scope
)

# First turn: agent stores fact
await agent.call(str, "Remember: Paris is capital of France")
# Agent calls: scope["remember"]("capital_france", "Paris")

# Second turn: agent recalls
await agent.call(str, "What's the capital of France?")
# Agent calls: scope["recall"]("capital of France") -> "Paris"
```

**Why this is powerful:**
- Functions are closures over service instances (MemoryService, BeadsTaskGraph)
- Agent sees function signatures, not implementation
- Same pattern for MCP tools, databases, APIs
- Enables progressive disclosure (add tools as needed)

**Source:** `scripts/agentica/agent_scope.py` - closure pattern for memory/task injection.

---

### Protocol Over ABC for Backends

**Pattern:** Duck typing for storage backends, not abstract base classes.

```python
# NOT THIS (rigid inheritance)
class StorageBackend(ABC):
    @abstractmethod
    def store(self, key: str, value: str) -> None: ...
    @abstractmethod
    def retrieve(self, key: str) -> str: ...

# THIS (protocol - duck typing)
class StorageProtocol:
    """Protocol for storage backends."""
    def store(self, key: str, value: str) -> None: ...
    def retrieve(self, key: str) -> str: ...

# Any class with these methods works
class SQLiteStorage:
    def store(self, key, value): ...
    def retrieve(self, key): ...

class PostgresStorage:
    def store(self, key, value): ...
    def retrieve(self, key): ...
```

**Benefits:**
- Easier to test (mock objects without inheritance)
- Easier to extend (no base class coupling)
- Supports third-party integrations (Redis, S3, etc.)
- Faster prototyping (no boilerplate)

**Source:** Memory backend factory pattern - SQLite and Postgres both implement protocol.

---

### Server is the Runtime, Not Optional

**Pattern:** Agentica server provides shared state across agent sessions.

```
Without server (local only):
- Each script run = isolated memory
- No cross-session learning
- Manual state persistence

With server (runtime):
- Shared memory pool across sessions
- Agent threads can handoff
- Centralized observability
- Persistent REPL environment
```

**Architecture:**
```
┌─────────────────────────────────────┐
│ Agentica Server (localhost:2345)    │
│ - Shared memory pool                │
│ - Task graph coordination           │
│ - Agent REPL environment            │
└─────────────────────────────────────┘
           ▲
           │ S_M_BASE_URL
           │
    ┌──────┴──────────┐
    │                 │
Agent Script 1    Agent Script 2
(Research)        (Synthesis)
```

**Key insight:** Server isn't just an optimization—it's the foundation for multi-agent coordination.

**Source:** `scripts/agentica/claude_proxy.py` - Agentica server proxy pattern.

---

## Development Process

### Research → Plan → Validate → Implement → Review Pipeline

**Pattern:** Five-stage workflow for complex features.

**Stage 1: Research**
```bash
# Use NIA for library docs
uv run python -m runtime.harness scripts/nia_docs.py \
    --package agentica --query "spawn scope premise"

# Use Perplexity for broader context
uv run python -m runtime.harness scripts/perplexity_search.py \
    --query "multi-agent orchestration patterns 2025"
```

**Stage 2: Plan**
```markdown
# thoughts/shared/plans/2025-12-26-feature.md

## Goal
Build hierarchical research coordinator.

## Phases
- [ ] Phase 1: Data models
- [ ] Phase 2: Coordinator logic
- [ ] Phase 3: Specialist spawning
- [ ] Phase 4: Integration tests
```

**Stage 3: Validate**
```python
# Write tests BEFORE implementation
# tests/unit/test_feature.py
async def test_coordinator_creation():
    coord = Coordinator(premise="...")
    assert coord is not None
```

**Stage 4: Implement**
```bash
# Use agents for implementation (preserves context)
Task(
    subagent_type="implementation",
    instruction="Implement Phase 2 per plan"
)
```

**Stage 5: Review**
```bash
# Tests verify behavior
uv run pytest tests/unit/test_feature.py -v

# QLTY checks style
qlty check scripts/feature.py

# Manual review for edge cases
```

**Source:** Used throughout Phase 6-9 implementations.

---

### Use Agents for Implementation, Keep Main Context Clean

**Pattern:** Delegate complex implementations to agents, preserve main context for coordination.

```python
# Main context (coordination only)
plan = Read("thoughts/shared/plans/feature.md")
summary = summarize(plan)  # 100 tokens

# Spawn implementation agent
Task(
    subagent_type="implementation",
    instruction=f"Implement {summary}"
)

# Agent context (implementation details)
# - Reads full plan
# - Reads existing code
# - Makes edits
# - Runs tests
# - Returns summary only

# Main context receives summary (~200 tokens)
```

**Token savings:**
- Main context: 300 tokens (plan summary + task + result)
- Agent context: 10,000 tokens (full implementation)
- Without agents: 10,300 tokens in main (leads to compaction)

**Source:** Global rule `agent-orchestration.md`.

---

### File-Based Checkboxes > TodoWrite for Multi-Phase Work

**Pattern:** Track progress in ledger files, not Claude's todo system.

```markdown
## State
- Done:
  - [x] Phase 1: Setup database schema
  - [x] Phase 2: Create API endpoints
- Now: [→] Phase 3: Add validation logic
- Next: Phase 4: Frontend components
- Remaining:
  - [ ] Phase 5: Wire up API calls
  - [ ] Phase 6: Write tests
```

**Why files beat todos:**
- TodoWrite survives compaction but loses context
- File checkboxes never degrade (full fidelity)
- Human-readable without tools
- Persist across sessions automatically
- Visible in git diffs (shows progress over time)

**Source:** Global rule `continuity.md` - checkbox pattern for ledgers.

---

## Pattern Selection (Meta-Pattern)

### Claude IS the Router

**Pattern:** Don't build explicit routing logic. Claude selects patterns based on task characteristics.

```python
# NOT THIS (rigid router)
def route_task(task: str) -> Pattern:
    if "research" in task.lower():
        return SwarmPattern()
    elif "implement" in task.lower():
        return HierarchicalPattern()
    else:
        return PipelinePattern()

# THIS (Claude decides)
# User: "Research async patterns and create implementation tasks"
# Claude: Sees "research" → selects Swarm for exploration
#         Sees "create tasks" → uses task graph for coordination
#         Automatically adapts based on findings
```

**Selection criteria:**
| Task Involves... | Pattern | Reason |
|------------------|---------|--------|
| Research, exploration, "investigate" | Swarm | Parallel diverse perspectives |
| Implementation, "build", "create" | Hierarchical | Coordinator → specialists → grunts |
| Review, critique, "feedback" | Generator/Critic | Iterative refinement |
| Validation, "is correct", high-stakes | Jury | Multiple independent evaluations |
| Linear workflow, clear steps | Pipeline | Sequential handoff |
| Parallel independent work | Map/Reduce | Fan out → aggregate |
| Unknown complexity | Hierarchical | Start structured, adapt as needed |

**Source:** `scripts/agentica/PATTERNS.md` - pattern selection guide.

---

## Anti-Patterns (Avoid)

### Don't Use LLMs for Retrieval (Hot-Path Oracle)

**WRONG:**
```python
# Asking agent what's been done
oracle = await spawn(premise="Recall session state")
status = await oracle.call(str, "What tasks are complete?")
# 2000ms latency, hallucination risk
```

**RIGHT:**
```python
# Query database directly
completed = db.get_completed_tasks()
# 5ms latency, always accurate
```

**Rule:** Use LLMs for reasoning, databases for facts.

**Source:** Global rule `agent-orchestration.md` - "Avoid Hot-Path LLMs".

---

### Don't Collapse Different ID Types

**WRONG:**
```python
# Using session_id for everything
trace = braintrust.log(session_id=session_id)  # Wrong ID type
```

**RIGHT:**
```python
# Keep IDs separate
session_id = "claude-code-session"     # Human-facing
root_span_id = "braintrust-trace-id"  # Query key
turn_span_id = "braintrust-turn-id"   # Individual turn
```

**Rule:** Different concepts = different IDs. Never conflate.

**Source:** Global rule `explicit-identity.md`.

---

### Don't Assume "Latest" Across Boundaries

**WRONG:**
```python
# Process boundary - race condition
subprocess.run(["analyzer", "--learn"])  # Which session?
```

**RIGHT:**
```python
# Explicit identity
subprocess.run(["analyzer", "--learn", "--session-id", session_id])
```

**Rule:** Pass explicit identifiers through entire pipeline.

**Source:** Global rule `explicit-identity.md`.

---

## Testing Insights

### Async REPL Pitfalls

**Pattern:** Common mistakes when testing agentic functions in REPL harness.

1. **Forgetting `await` on future-returning tools**
   ```python
   # WRONG
   content = view_file(path)  # Returns Future, not string

   # RIGHT
   content = await view_file(path)
   ```

2. **Multiple code blocks (only first executes)**
   ```python
   # WRONG
   content = await view_file(path)
   ---
   return any(c.isdigit() for c in content)  # Never runs

   # RIGHT (single block)
   content = await view_file(path)
   return any(c.isdigit() for c in content)
   ```

3. **Not returning non-str types**
   ```python
   # WRONG
   any(c.isdigit() for c in content)  # Expression, not returned

   # RIGHT
   return any(c.isdigit() for c in content)
   ```

**Source:** Global rule `async-repl-protocol.md` - repeated across 4 sessions.

---

## Environment Management

### Check Actual Interpreter, Not System Python

**Pattern:** `uv` may use different Python than system default.

```bash
# WRONG: System Python is not authoritative
python3 --version  # 3.11

# RIGHT: What uv actually uses
uv run python --version  # 3.13 (from .python-version)

# Verify package installed
uv pip show agentica

# Confirm import works
uv run python -c "import agentica; print(agentica.__version__)"
```

**Common issue:** Optional dependencies require Python 3.12+ but `.python-version` is 3.11.

**Fix:**
```bash
echo "3.13" > .python-version
rm -rf .venv && uv venv && uv sync --all-extras
```

**Source:** Global rule `environment-triage.md` - session 2243c067.

---

## Summary

The most impactful lessons:

1. **Instructions > Personas** - 4x effectiveness gain
2. **TDD drives API design** - tests before implementation
3. **REPL + scope sharing** - the core architectural insight
4. **File checkboxes > todos** - context preservation across compaction
5. **Claude IS the router** - no need for rigid routing logic
6. **Agents for implementation** - preserve main context
7. **Protocol over ABC** - flexibility for backends
8. **Explicit identity** - no "latest" across boundaries
9. **Database for facts, LLM for reasoning** - avoid hot-path oracles
10. **Verify with tests, not output files** - context isolation

These patterns enabled building a production-grade multi-agent orchestration system with minimal token overhead and maximum flexibility.
