# Multi-Agent Patterns

11 orchestration patterns for Claude Code agents using the Agentica SDK.

## Pattern Selection Guide

| Use Case                             | Pattern                     | When to Use                                      |
| ------------------------------------ | --------------------------- | ------------------------------------------------ |
| Research, exploration, brainstorming | **Swarm**                   | Need diverse perspectives, parallel analysis     |
| High-stakes decisions, validation    | **Jury**                    | Reduce hallucination, multiple independent votes |
| Linear workflow, clear steps         | **Pipeline**                | Each step transforms output of previous          |
| Code review, iterative refinement    | **Generator-Critic**        | Propose-critique-refine loop                     |
| Complex tasks with subtasks          | **Hierarchical**            | Coordinator decomposes, specialists execute      |
| Parallel independent work            | **Map-Reduce**              | Fan out N workers, aggregate results             |
| Collaborative problem solving        | **Blackboard**              | Multiple experts contribute to shared state      |
| Resilient pipelines                  | **Circuit Breaker**         | Graceful degradation, fallback on failure        |
| Capability matching, routing         | **Chain of Responsibility** | First matching handler processes request         |
| Security review, stress-testing      | **Adversarial**             | Red vs blue team debate                          |
| Monitoring, reactive systems         | **Event-Driven**            | Pub/sub, agents react to events                  |

## Quick Decision Tree

```
Task type?
├── Need multiple perspectives → Swarm
├── High-stakes decision → Jury
├── Sequential steps → Pipeline
├── Iterative refinement → Generator-Critic
├── Complex decomposition → Hierarchical
├── Parallel independent chunks → Map-Reduce
├── Collaborative shared state → Blackboard
├── Need fallback on failure → Circuit Breaker
├── Route to specialized handler → Chain of Responsibility
├── Debate/stress-test ideas → Adversarial
└── React to events → Event-Driven
```

---

## Patterns

### 1. Swarm

**Purpose:** Parallel exploration with diverse perspectives

**Use when:** Research, brainstorming, multi-angle analysis, time-sensitive exploration

#### Structure

```
         Query
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
 Agent A  Agent B  Agent C  (parallel)
    │      │      │
    └──────┼──────┘
           ▼
       Aggregator
           │
           ▼
        Result
```

#### API

```python
from scripts.agentica.patterns import Swarm, AggregateMode

swarm = Swarm(
    perspectives=[
        "You are a security expert.",
        "You are a performance expert.",
        "You are a UX expert."
    ],
    aggregate_mode=AggregateMode.MERGE
)
result = await swarm.execute("Analyze OAuth implementation")
```

#### Parameters

| Param                   | Type                     | Default      | Description                                          |
| ----------------------- | ------------------------ | ------------ | ---------------------------------------------------- |
| `perspectives`          | `list[str]`              | **required** | Premises for each agent (one per agent)              |
| `aggregate_mode`        | `AggregateMode`          | `MERGE`      | How to combine results: `MERGE`, `CONCAT`, `BEST`    |
| `aggregation_separator` | `str`                    | `" "`        | Separator for `CONCAT` mode                          |
| `fail_fast`             | `bool`                   | `False`      | Stop on first error vs continue with partial results |
| `model`                 | `str \| None`            | `None`       | Model for all agents                                 |
| `scope`                 | `dict[str, Any] \| None` | `None`       | Tools available to all agents                        |
| `mcp`                   | `str \| None`            | `None`       | MCP config path for all agents                       |
| `db`                    | `CoordinationDB \| None` | `None`       | Coordination database for tracking                   |

#### Example

```python
from scripts.agentica.patterns import Swarm, AggregateMode

# Research a topic from multiple angles
swarm = Swarm(
    perspectives=[
        "You are a historian focusing on economic factors.",
        "You are a sociologist analyzing cultural impacts.",
        "You are a political scientist examining governance."
    ],
    aggregate_mode=AggregateMode.CONCAT,
    aggregation_separator="\n\n---\n\n"
)

result = await swarm.execute(
    "Analyze the causes of the Industrial Revolution",
    return_type=str
)
print(result)  # Combined analysis from all perspectives
```

#### Environment Variables

| Var            | Purpose                              |
| -------------- | ------------------------------------ |
| `PATTERN_TYPE` | Set to `swarm` during execution      |
| `PATTERN_ID`   | Unique swarm instance ID             |
| `SWARM_ID`     | Same as `PATTERN_ID`                 |
| `AGENT_ROLE`   | Set to `worker` for all swarm agents |

---

### 2. Jury

**Purpose:** Voting/consensus for high-stakes decisions

**Use when:** Validation, reducing hallucination, need multiple independent evaluations

#### Structure

```
         Question
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
  Juror1  Juror2  Juror3  (parallel votes)
    │      │      │
    └──────┼──────┘
           ▼
       Consensus
           │
           ▼
        Verdict
```

#### API

```python
from scripts.agentica.patterns import Jury, ConsensusMode

jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.MAJORITY
)
verdict = await jury.decide(bool, "Is this code safe to deploy?")
```

#### Parameters

| Param            | Type                           | Default      | Description                                  |
| ---------------- | ------------------------------ | ------------ | -------------------------------------------- |
| `num_jurors`     | `int`                          | **required** | Number of juror agents to spawn              |
| `consensus_mode` | `ConsensusMode`                | **required** | `MAJORITY`, `UNANIMOUS`, or `THRESHOLD`      |
| `threshold`      | `float \| None`                | `None`       | Required for `THRESHOLD` mode (0.0-1.0)      |
| `weights`        | `list[float] \| None`          | `None`       | Optional weights for each juror              |
| `premise`        | `str \| None`                  | `None`       | Single premise for all jurors                |
| `premises`       | `list[str] \| None`            | `None`       | Different premise per juror                  |
| `model`          | `str \| None`                  | `None`       | Model for all jurors                         |
| `scope`          | `dict[str, Any] \| None`       | `None`       | Tools available to jurors                    |
| `key`            | `Callable[[Any], Any] \| None` | `None`       | Extract decision from structured votes       |
| `allow_partial`  | `bool`                         | `False`      | Continue with partial votes on failure       |
| `min_jurors`     | `int \| None`                  | `num_jurors` | Minimum jurors needed (with `allow_partial`) |
| `debug`          | `bool`                         | `False`      | Track individual votes for debugging         |
| `db`             | `CoordinationDB \| None`       | `None`       | Coordination database                        |

#### Consensus Modes

| Mode        | Description                                    | Raises on Failure          |
| ----------- | ---------------------------------------------- | -------------------------- |
| `MAJORITY`  | Most common vote wins (ties: first occurrence) | Never                      |
| `UNANIMOUS` | All votes must agree                           | `ConsensusNotReachedError` |
| `THRESHOLD` | Percentage must agree                          | `ConsensusNotReachedError` |

#### Example

```python
from scripts.agentica.patterns import Jury, ConsensusMode

# High-stakes security validation
jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.THRESHOLD,
    threshold=0.8,  # 80% must agree
    premises=[
        "You are an application security expert.",
        "You are a network security expert.",
        "You are a cryptography expert.",
        "You are a secure coding expert.",
        "You are a compliance auditor."
    ],
    debug=True  # Track individual votes
)

# Returns bool based on majority vote
is_safe = await jury.decide(bool, "Is this authentication flow secure?")

if jury.debug:
    print(f"Votes: {jury.last_votes}")  # See individual votes
```

#### Environment Variables

| Var            | Purpose                  |
| -------------- | ------------------------ |
| `PATTERN_TYPE` | Set to `jury`            |
| `PATTERN_ID`   | Unique jury instance ID  |
| `JURY_ID`      | Same as `PATTERN_ID`     |
| `AGENT_ROLE`   | Set to `juror`           |
| `JUROR_INDEX`  | 0-indexed juror position |
| `TOTAL_JURORS` | Total number of jurors   |

---

### 3. Pipeline

**Purpose:** Sequential stage execution

**Use when:** Clear linear workflow, each step transforms output of previous

#### Structure

```
  Initial State
       │
       ▼
    Stage A
       │
       ▼
    Stage B
       │
       ▼
    Stage C
       │
       ▼
   Final State
```

#### API

```python
from scripts.agentica.patterns import Pipeline, HandoffState

async def fetch(state: HandoffState) -> HandoffState:
    state.add_artifact("data", await fetch_data())
    return state

async def transform(state: HandoffState) -> HandoffState:
    data = state.artifacts["data"]
    state.add_artifact("transformed", process(data))
    return state

pipeline = Pipeline(stages=[fetch, transform])
result = await pipeline.run(HandoffState(context="", next_instruction="Start"))
```

#### Parameters

| Param    | Type                                           | Default      | Description                                   |
| -------- | ---------------------------------------------- | ------------ | --------------------------------------------- |
| `stages` | `list[Callable[[HandoffState], HandoffState]]` | **required** | Async functions taking/returning HandoffState |

#### HandoffState

```python
@dataclass
class HandoffState:
    context: str              # Current situation/task context
    next_instruction: str     # What the next stage should do
    artifacts: dict[str, Any] # Data/files produced so far
    metadata: dict[str, Any]  # Arbitrary metadata (priority, tags, etc.)
    _handoff_chain: list[dict[str, str]]  # History of handoffs
```

**Key Methods:**
- `add_artifact(key, value)` - Add artifact to state
- `merge(other)` - Merge another state (later wins on conflicts)
- `record_handoff(from_agent, to_agent)` - Track handoff history
- `to_dict()` / `from_dict()` - Serialization

#### Example

```python
from scripts.agentica.patterns import Pipeline, HandoffState

async def extract(state: HandoffState) -> HandoffState:
    # Extract data from source
    raw = await fetch_url(state.artifacts.get("url"))
    state.add_artifact("raw_data", raw)
    state.update_instruction("Transform the raw data")
    return state

async def transform(state: HandoffState) -> HandoffState:
    # Transform extracted data
    data = state.artifacts["raw_data"]
    state.add_artifact("cleaned", clean_data(data))
    state.update_instruction("Load into database")
    return state

async def load(state: HandoffState) -> HandoffState:
    # Load into destination
    cleaned = state.artifacts["cleaned"]
    await db.insert(cleaned)
    state.update_instruction("Complete")
    return state

# ETL Pipeline
pipeline = Pipeline(stages=[extract, transform, load])
initial = HandoffState(
    context="ETL job for user data",
    next_instruction="Extract from API",
    artifacts={"url": "https://api.example.com/users"}
)
result = await pipeline.run(initial)
```

#### Environment Variables

| Var                     | Purpose                     |
| ----------------------- | --------------------------- |
| `PATTERN_TYPE`          | Set to `pipeline`           |
| `PATTERN_ID`            | Unique pipeline instance ID |
| `PIPELINE_ID`           | Same as `PATTERN_ID`        |
| `AGENT_ROLE`            | Set to `stage`              |
| `PIPELINE_STAGE_INDEX`  | 0-indexed stage position    |
| `PIPELINE_TOTAL_STAGES` | Total number of stages      |

---

### 4. Generator-Critic

**Purpose:** Iterative refinement through propose-critique cycles

**Use when:** Code review, writing, any iterative improvement task

#### Structure

```
       Task
         │
         ▼
    ┌─────────┐
    │Generator│──────┐
    └────┬────┘      │
         │           │
         ▼           │
    ┌─────────┐      │
    │  Critic │      │
    └────┬────┘      │
         │           │
    ┌────┴────┐      │
    │Approved?│──No──┘
    └────┬────┘
         │Yes
         ▼
       Result
```

#### API

```python
from scripts.agentica.patterns import GeneratorCritic

gc = GeneratorCritic(
    generator_premise="You generate Python code.",
    critic_premise="You review Python code for correctness.",
    max_rounds=3
)
result = await gc.run("Create a function to parse JSON safely")
```

#### Parameters

| Param               | Type                                     | Default      | Description                                                |
| ------------------- | ---------------------------------------- | ------------ | ---------------------------------------------------------- |
| `generator_premise` | `str`                                    | **required** | Premise for generator agent                                |
| `critic_premise`    | `str`                                    | **required** | Premise for critic agent                                   |
| `max_rounds`        | `int`                                    | `3`          | Maximum iteration rounds                                   |
| `generator_scope`   | `dict[str, Any] \| None`                 | `None`       | Tools for generator                                        |
| `critic_scope`      | `dict[str, Any] \| None`                 | `None`       | Tools for critic                                           |
| `generator_model`   | `str \| None`                            | `None`       | Model for generator                                        |
| `critic_model`      | `str \| None`                            | `None`       | Model for critic                                           |
| `is_approved`       | `Callable[[HandoffState], bool] \| None` | `None`       | Custom approval check (default: "APPROVED" in instruction) |
| `db`                | `CoordinationDB \| None`                 | `None`       | Coordination database                                      |

#### Example

```python
from scripts.agentica.patterns import GeneratorCritic, HandoffState

# Code review loop
gc = GeneratorCritic(
    generator_premise="""
    You are a senior Python developer. Generate clean, efficient code.
    Follow PEP 8, add type hints, and include docstrings.
    """,
    critic_premise="""
    You are a code reviewer. Check for:
    - Correctness and edge cases
    - Performance issues
    - Security vulnerabilities
    - Code style and readability

    If approved, set next_instruction to "APPROVED".
    If not, provide specific feedback in artifacts['feedback'].
    """,
    max_rounds=5,
    is_approved=lambda state: state.metadata.get("approved", False)
)

result = await gc.run("Implement a rate limiter with sliding window")
print(result.artifacts.get("code"))
```

#### Environment Variables

| Var             | Purpose                       |
| --------------- | ----------------------------- |
| `PATTERN_TYPE`  | Set to `generator_critic`     |
| `PATTERN_ID`    | Unique GC instance ID         |
| `GC_ID`         | Same as `PATTERN_ID`          |
| `AGENT_ROLE`    | `generator` or `critic`       |
| `GC_ITERATION`  | Current iteration (1-indexed) |
| `GC_MAX_ROUNDS` | Maximum rounds configured     |

---

### 5. Hierarchical

**Purpose:** Coordinator decomposes tasks for specialists

**Use when:** Complex tasks with clear decomposition, need accountability chain

#### Structure

```
              Coordinator
                  │
          ┌───────┼───────┐
          ▼       ▼       ▼
      Specialist A B C (parallel)
          │       │       │
          └───────┼───────┘
                  ▼
             Aggregator
                  │
                  ▼
        Coordinator Synthesizes
                  │
                  ▼
              Result
```

#### API

```python
from scripts.agentica.patterns import Hierarchical

hierarchical = Hierarchical(
    coordinator_premise="You break tasks into subtasks and synthesize results.",
    specialist_premises={
        "researcher": "You research topics thoroughly.",
        "analyst": "You analyze data and find patterns.",
        "writer": "You write clear, concise summaries."
    }
)
result = await hierarchical.execute("Research and summarize AI trends in 2024")
```

#### Parameters

| Param                   | Type                     | Default      | Description                                  |
| ----------------------- | ------------------------ | ------------ | -------------------------------------------- |
| `coordinator_premise`   | `str`                    | **required** | Premise for coordinator agent                |
| `specialist_premises`   | `dict[str, str]`         | **required** | Map of specialist name to premise            |
| `coordinator_scope`     | `dict[str, Any] \| None` | `None`       | Tools for coordinator                        |
| `specialist_scope`      | `dict[str, Any] \| None` | `None`       | Tools for specialists                        |
| `coordinator_model`     | `str \| None`            | `None`       | Model for coordinator                        |
| `specialist_model`      | `str \| None`            | `None`       | Model for specialists                        |
| `aggregation_mode`      | `AggregateMode`          | `CONCAT`     | How to aggregate specialist results          |
| `aggregation_separator` | `str`                    | `"\n\n"`     | Separator for aggregation                    |
| `aggregator`            | `Aggregator \| None`     | `None`       | Custom aggregator (overrides mode/separator) |
| `fail_fast`             | `bool`                   | `False`      | Stop on first specialist failure             |
| `return_type`           | `type`                   | `str`        | Expected return type                         |
| `db`                    | `CoordinationDB \| None` | `None`       | Coordination database                        |

#### Flow

1. **Decompose**: Coordinator breaks task into subtasks, assigns to specialists
2. **Execute**: Specialists execute their subtasks in parallel
3. **Aggregate**: Results are combined using aggregator
4. **Synthesize**: Coordinator produces final answer from aggregated results

#### Example

```python
from scripts.agentica.patterns import Hierarchical, AggregateMode

# Build a full-stack feature
hierarchical = Hierarchical(
    coordinator_premise="""
    You are a tech lead. Break down features into frontend, backend, and database tasks.
    Assign appropriate specialists and synthesize their work into a cohesive implementation.
    """,
    specialist_premises={
        "frontend": "You build React components with TypeScript.",
        "backend": "You build FastAPI endpoints with proper validation.",
        "database": "You design PostgreSQL schemas and migrations.",
        "tests": "You write comprehensive test suites."
    },
    aggregation_mode=AggregateMode.CONCAT,
    aggregation_separator="\n\n## Next Component\n\n"
)

result = await hierarchical.execute(
    "Build a user authentication system with email verification"
)
```

#### Environment Variables

| Var               | Purpose                               |
| ----------------- | ------------------------------------- |
| `PATTERN_TYPE`    | Set to `hierarchical`                 |
| `PATTERN_ID`      | Unique hierarchy ID                   |
| `HIERARCHY_ID`    | Same as `PATTERN_ID`                  |
| `AGENT_ROLE`      | `coordinator` or `specialist`         |
| `COORDINATOR_ID`  | ID of coordinator (for specialists)   |
| `HIERARCHY_LEVEL` | 0 for coordinator, 1+ for specialists |

---

### 6. Map-Reduce

**Purpose:** Fan out work to parallel mappers, aggregate with reducer

**Use when:** Parallel processing of independent chunks, batch analysis

#### Structure

```
              Query + Chunks
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
       Mapper1  Mapper2  Mapper3  (parallel)
          │        │        │
          └────────┼────────┘
                   ▼
               Reducer
                   │
                   ▼
                Result
```

#### API

```python
from scripts.agentica.patterns import MapReduce

mr = MapReduce(
    mapper_premise="You analyze one section of code.",
    reducer_premise="You synthesize analysis from multiple reviewers.",
    num_mappers=4
)
result = await mr.execute(
    "Review this codebase for security issues",
    chunks=["auth.py", "api.py", "db.py", "utils.py"]
)
```

#### Parameters

| Param             | Type                     | Default      | Description                |
| ----------------- | ------------------------ | ------------ | -------------------------- |
| `mapper_premise`  | `str`                    | **required** | Premise for mapper agents  |
| `reducer_premise` | `str`                    | **required** | Premise for reducer agent  |
| `num_mappers`     | `int`                    | `3`          | Number of mapper agents    |
| `mapper_model`    | `str \| None`            | `None`       | Model for mappers          |
| `reducer_model`   | `str \| None`            | `None`       | Model for reducer          |
| `mapper_scope`    | `dict[str, Any] \| None` | `None`       | Tools for mappers          |
| `reducer_scope`   | `dict[str, Any] \| None` | `None`       | Tools for reducer          |
| `fail_fast`       | `bool`                   | `True`       | Stop on first mapper error |
| `return_type`     | `type`                   | `str`        | Expected return type       |
| `db`              | `CoordinationDB \| None` | `None`       | Coordination database      |

#### Chunk Distribution

Chunks are distributed round-robin across mappers:
- 12 chunks, 4 mappers: each gets 3 chunks
- 10 chunks, 4 mappers: mappers get 3, 3, 2, 2 chunks
- 2 chunks, 4 mappers: 2 mappers get 1 chunk each, 2 get none

#### Example

```python
from scripts.agentica.patterns import MapReduce

# Analyze a large codebase
mr = MapReduce(
    mapper_premise="""
    You analyze code files for:
    - Code quality issues
    - Security vulnerabilities
    - Performance bottlenecks
    Provide a structured report for each file.
    """,
    reducer_premise="""
    You synthesize multiple code reviews into a comprehensive report.
    Prioritize issues by severity and provide actionable recommendations.
    """,
    num_mappers=8,
    fail_fast=False  # Continue even if some files fail
)

files = ["src/main.py", "src/api.py", "src/models.py", ...]  # Many files
result = await mr.execute("Full codebase security audit", chunks=files)
```

#### Environment Variables

| Var             | Purpose                  |
| --------------- | ------------------------ |
| `PATTERN_TYPE`  | Set to `map_reduce`      |
| `PATTERN_ID`    | Unique MapReduce ID      |
| `MR_ID`         | Same as `PATTERN_ID`     |
| `AGENT_ROLE`    | `mapper` or `reducer`    |
| `MAPPER_INDEX`  | Mapper's index (0-based) |
| `TOTAL_MAPPERS` | Total number of mappers  |

---

### 7. Blackboard

**Purpose:** Collaborative problem solving with shared state

**Use when:** Multiple experts contribute to evolving solution

#### Structure

```
                 Query
                   │
                   ▼
              ┌─────────┐
              │Blackboard│◄───────────────┐
              └────┬────┘                 │
                   │                      │
          ┌────────┼────────┐             │
          ▼        ▼        ▼             │
      Specialist  Specialist Specialist   │
          │        │        │             │
          └────────┼────────┘             │
                   │ write                │
                   ▼                      │
              Controller ─────────────────┘
                   │        (check complete)
                   ▼
               Complete?
                   │Yes
                   ▼
                Result
```

#### API

```python
from scripts.agentica.patterns import Blackboard, Specialist

bb = Blackboard(
    specialists=[
        Specialist(premise="You analyze requirements.", writes_to=["requirements"]),
        Specialist(premise="You design architecture.", writes_to=["architecture"], reads_from=["requirements"]),
        Specialist(premise="You write implementation plan.", writes_to=["plan"], reads_from=["architecture"]),
    ],
    controller_premise="You check if the design is complete and coherent.",
    max_iterations=5
)
result = await bb.solve("Build a user authentication system")
```

#### Parameters

| Param                | Type                     | Default      | Description                        |
| -------------------- | ------------------------ | ------------ | ---------------------------------- |
| `specialists`        | `list[Specialist]`       | **required** | List of specialist definitions     |
| `controller_premise` | `str`                    | **required** | Premise for controller agent       |
| `max_iterations`     | `int`                    | `5`          | Maximum iterations before stopping |
| `controller_model`   | `str \| None`            | `None`       | Model for controller               |
| `specialist_model`   | `str \| None`            | `None`       | Model for specialists              |
| `controller_scope`   | `dict[str, Any] \| None` | `None`       | Tools for controller               |
| `specialist_scope`   | `dict[str, Any] \| None` | `None`       | Tools for specialists              |
| `db`                 | `CoordinationDB \| None` | `None`       | Coordination database              |

#### Specialist Dataclass

```python
@dataclass
class Specialist:
    premise: str           # Agent's role/expertise
    writes_to: list[str]   # Blackboard keys this specialist writes
    reads_from: list[str]  # Blackboard keys this specialist reads
```

#### BlackboardState

```python
class BlackboardState:
    # Dict-like access
    state["key"] = value   # Set and record in history
    value = state["key"]   # Get value
    "key" in state         # Check existence
    state.get("key", default)
    state.keys()
    state.items()
    state.to_dict()        # Get copy of all data
    state.history          # List of all changes
```

#### BlackboardResult

```python
@dataclass
class BlackboardResult:
    state: BlackboardState  # Final blackboard state
    iterations: int         # Number of iterations run
    completed: bool         # Whether controller approved
```

#### Example

```python
from scripts.agentica.patterns import Blackboard, Specialist

# System design with multiple experts
bb = Blackboard(
    specialists=[
        Specialist(
            premise="You gather and document requirements.",
            writes_to=["requirements", "constraints"]
        ),
        Specialist(
            premise="You design system architecture.",
            writes_to=["architecture"],
            reads_from=["requirements", "constraints"]
        ),
        Specialist(
            premise="You design database schema.",
            writes_to=["database_schema"],
            reads_from=["requirements", "architecture"]
        ),
        Specialist(
            premise="You define API contracts.",
            writes_to=["api_spec"],
            reads_from=["requirements", "architecture"]
        ),
        Specialist(
            premise="You review security considerations.",
            writes_to=["security_review"],
            reads_from=["architecture", "database_schema", "api_spec"]
        )
    ],
    controller_premise="""
    You check if the system design is complete:
    - Requirements are clear
    - Architecture addresses requirements
    - Database schema supports data needs
    - API spec is consistent with architecture
    - Security has been reviewed

    Return {"complete": true} when satisfied, or {"complete": false, "feedback": "..."}.
    """,
    max_iterations=10
)

result = await bb.solve("Design a real-time chat application")
if result.completed:
    print("Design complete!")
    print(result.state.to_dict())
else:
    print(f"Reached max iterations ({result.iterations})")
```

#### Environment Variables

| Var                     | Purpose                      |
| ----------------------- | ---------------------------- |
| `PATTERN_TYPE`          | Set to `blackboard`          |
| `BLACKBOARD_ID`         | Unique blackboard ID         |
| `AGENT_ROLE`            | `controller` or `specialist` |
| `BLACKBOARD_WRITES_TO`  | Comma-separated write keys   |
| `BLACKBOARD_READS_FROM` | Comma-separated read keys    |

---

### 8. Circuit Breaker

**Purpose:** Fault tolerance with fallback routing

**Use when:** Resilient pipelines, graceful degradation

#### Structure

```
         Query
           │
           ▼
    ┌──────────────┐
    │Circuit State?│
    └──────┬───────┘
           │
    ┌──────┴──────┐
    │             │
  CLOSED        OPEN
    │             │
    ▼             ▼
  Primary     Fallback
    │             │
    ├──Success────┤
    │             │
    ├──Failure────┤
    │      │      │
    │  Count++    │
    │      │      │
    │  Threshold? │
    │      │      │
    │    OPEN     │
    │             │
    └──────┬──────┘
           ▼
         Result
```

#### Circuit States

| State       | Description                                        |
| ----------- | -------------------------------------------------- |
| `CLOSED`    | Normal operation, using primary agent              |
| `OPEN`      | Threshold reached, using fallback agent            |
| `HALF_OPEN` | Testing primary after timeout, one failure reopens |

#### API

```python
from scripts.agentica.patterns import CircuitBreaker

cb = CircuitBreaker(
    primary_premise="You implement complex features.",
    fallback_premise="You implement simpler alternatives.",
    max_failures=3,
    reset_timeout=60
)
result = await cb.execute("Implement OAuth2 with PKCE")
```

#### Parameters

| Param              | Type                     | Default      | Description                         |
| ------------------ | ------------------------ | ------------ | ----------------------------------- |
| `primary_premise`  | `str`                    | **required** | Premise for primary agent           |
| `fallback_premise` | `str`                    | **required** | Premise for fallback agent          |
| `max_failures`     | `int`                    | `3`          | Failures before opening circuit     |
| `reset_timeout`    | `float`                  | `60`         | Seconds before trying primary again |
| `primary_model`    | `str \| None`            | `None`       | Model for primary                   |
| `fallback_model`   | `str \| None`            | `None`       | Model for fallback                  |
| `primary_scope`    | `dict[str, Any] \| None` | `None`       | Tools for primary                   |
| `fallback_scope`   | `dict[str, Any] \| None` | `None`       | Tools for fallback                  |
| `return_type`      | `type`                   | `str`        | Expected return type                |
| `db`               | `CoordinationDB \| None` | `None`       | Coordination database               |

#### State Properties

```python
cb.state           # Current CircuitState (CLOSED, OPEN, HALF_OPEN)
cb.failure_count   # Current consecutive failure count
cb.last_failure_time  # Timestamp of last failure
```

#### Example

```python
from scripts.agentica.patterns import CircuitBreaker, CircuitState

# Resilient code generation
cb = CircuitBreaker(
    primary_premise="""
    You are an expert developer. Generate production-quality code
    with proper error handling, logging, and tests.
    """,
    fallback_premise="""
    You are a pragmatic developer. Generate working code
    that covers the main use case. Keep it simple.
    """,
    max_failures=3,
    reset_timeout=120  # Try primary again after 2 minutes
)

# Execute multiple times
for task in tasks:
    result = await cb.execute(task)
    print(f"Circuit state: {cb.state}")

    if cb.state == CircuitState.OPEN:
        print("Warning: Primary agent failing, using fallback")
```

#### Environment Variables

| Var             | Purpose                                       |
| --------------- | --------------------------------------------- |
| `PATTERN_TYPE`  | Set to `circuit_breaker`                      |
| `PATTERN_ID`    | Unique circuit breaker ID                     |
| `CB_ID`         | Same as `PATTERN_ID`                          |
| `AGENT_ROLE`    | `primary` or `fallback`                       |
| `CIRCUIT_STATE` | Current state (`closed`, `open`, `half_open`) |

---

### 9. Chain of Responsibility

**Purpose:** Route request to first matching handler

**Use when:** Capability matching, tiered support, cost optimization

#### Structure

```
         Query
           │
           ▼
    ┌──────────────┐
    │Handler A     │──Can handle?──No──┐
    │(priority: 0) │                   │
    └──────┬───────┘                   │
           │Yes                        │
           ▼                           ▼
        Process                 ┌──────────────┐
           │                    │Handler B     │──Can handle?──No──┐
           ▼                    │(priority: 1) │                   │
         Result                 └──────┬───────┘                   │
                                       │Yes                        │
                                       ▼                           ▼
                                    Process                 ┌──────────────┐
                                       │                    │Handler C     │
                                       ▼                    │(fallback)    │
                                     Result                 └──────────────┘
```

#### API

```python
from scripts.agentica.patterns import ChainOfResponsibility, Handler

chain = ChainOfResponsibility(handlers=[
    Handler(premise="You handle Python.", can_handle=lambda q: "python" in q.lower()),
    Handler(premise="You handle JavaScript.", can_handle=lambda q: "javascript" in q.lower()),
    Handler(premise="You handle general questions.", can_handle=lambda q: True),  # fallback
])
result = await chain.process("How do I use async in Python?")
```

#### Parameters

| Param         | Type                     | Default      | Description                           |
| ------------- | ------------------------ | ------------ | ------------------------------------- |
| `handlers`    | `list[Handler]`          | **required** | List of handlers (sorted by priority) |
| `model`       | `str \| None`            | `None`       | Model for handler agents              |
| `scope`       | `dict[str, Any] \| None` | `None`       | Tools for handlers                    |
| `return_type` | `type`                   | `str`        | Expected return type                  |
| `db`          | `CoordinationDB \| None` | `None`       | Coordination database                 |

#### Handler Dataclass

```python
@dataclass
class Handler:
    premise: str                      # Agent's role/expertise
    can_handle: Callable[[str], bool]  # Predicate: can this handler process the query?
    priority: int = 0                 # Lower = higher priority
```

#### Example

```python
from scripts.agentica.patterns import ChainOfResponsibility, Handler

# Tiered support system
chain = ChainOfResponsibility(
    handlers=[
        # Tier 1: FAQ bot (cheapest, fastest)
        Handler(
            premise="You answer common questions from the FAQ.",
            can_handle=lambda q: any(kw in q.lower() for kw in ["hours", "location", "pricing"]),
            priority=0
        ),
        # Tier 2: Technical support
        Handler(
            premise="You provide technical troubleshooting.",
            can_handle=lambda q: any(kw in q.lower() for kw in ["error", "bug", "not working"]),
            priority=1
        ),
        # Tier 3: Senior engineer
        Handler(
            premise="You handle complex technical issues requiring deep expertise.",
            can_handle=lambda q: any(kw in q.lower() for kw in ["architecture", "design", "scale"]),
            priority=2
        ),
        # Tier 4: Fallback (catches everything)
        Handler(
            premise="You route unclear questions to the appropriate team.",
            can_handle=lambda q: True,
            priority=99
        )
    ]
)

result = await chain.process("What are your business hours?")  # -> FAQ bot
result = await chain.process("I'm getting an error on login")  # -> Tech support
result = await chain.process("How should we architect for scale?")  # -> Senior engineer
```

#### Environment Variables

| Var                | Purpose                          |
| ------------------ | -------------------------------- |
| `PATTERN_TYPE`     | Set to `chain_of_responsibility` |
| `PATTERN_ID`       | Unique chain ID                  |
| `COR_ID`           | Same as `PATTERN_ID`             |
| `AGENT_ROLE`       | Set to `handler`                 |
| `HANDLER_PRIORITY` | Handler's priority value         |
| `CHAIN_LENGTH`     | Total number of handlers         |

---

### 10. Adversarial

**Purpose:** Stress-test ideas through structured debate

**Use when:** Security review, design decisions, finding edge cases

#### Structure

```
       Question
          │
          ▼
    ┌───────────┐
    │  Advocate │──────┐
    └─────┬─────┘      │
          │            │
          ▼            │
    ┌───────────┐      │
    │ Adversary │      │
    └─────┬─────┘      │
          │            │
     More rounds?──Yes─┘
          │No
          ▼
    ┌───────────┐
    │   Judge   │ (optional)
    └─────┬─────┘
          │
          ▼
        Verdict
```

#### API

```python
from scripts.agentica.patterns import Adversarial

adv = Adversarial(
    advocate_premise="You argue in favor of this architectural decision.",
    adversary_premise="You find flaws in architectural decisions.",
    judge_premise="You decide which position is stronger.",
    max_rounds=3
)
result = await adv.resolve("Should we use microservices or monolith?")
```

#### Parameters

| Param               | Type                     | Default      | Description                               |
| ------------------- | ------------------------ | ------------ | ----------------------------------------- |
| `advocate_premise`  | `str`                    | **required** | Premise for advocate (argues in favor)    |
| `adversary_premise` | `str`                    | **required** | Premise for adversary (attacks/critiques) |
| `judge_premise`     | `str \| None`            | `None`       | Premise for judge (decides winner)        |
| `max_rounds`        | `int`                    | `3`          | Maximum debate rounds                     |
| `advocate_model`    | `str \| None`            | `None`       | Model for advocate                        |
| `adversary_model`   | `str \| None`            | `None`       | Model for adversary                       |
| `judge_model`       | `str \| None`            | `None`       | Model for judge                           |
| `advocate_scope`    | `dict[str, Any] \| None` | `None`       | Tools for advocate                        |
| `adversary_scope`   | `dict[str, Any] \| None` | `None`       | Tools for adversary                       |
| `judge_scope`       | `dict[str, Any] \| None` | `None`       | Tools for judge                           |
| `db`                | `CoordinationDB \| None` | `None`       | Coordination database                     |

#### Methods

| Method              | Returns       | Description                                          |
| ------------------- | ------------- | ---------------------------------------------------- |
| `debate(question)`  | `dict`        | Run debate only, returns history and final positions |
| `resolve(question)` | `dict \| str` | Run debate + judge verdict (if judge configured)     |

#### Example

```python
from scripts.agentica.patterns import Adversarial

# Security review through debate
adv = Adversarial(
    advocate_premise="""
    You are a developer defending your implementation choices.
    Explain why the current approach is secure and appropriate.
    """,
    adversary_premise="""
    You are a penetration tester. Find security vulnerabilities.
    Attack the design, find edge cases, suggest exploits.
    """,
    judge_premise="""
    You are a security architect. Evaluate both positions objectively.
    Decide if the implementation is secure enough for production.
    Provide specific recommendations.
    """,
    max_rounds=3
)

result = await adv.resolve("Is this JWT authentication implementation secure?")

print("Advocate's final position:", result["advocate_final"])
print("Adversary's final position:", result["adversary_final"])
print("Judge's verdict:", result["verdict"])
print("Debate history:", result["history"])
```

#### Environment Variables

| Var                      | Purpose                             |
| ------------------------ | ----------------------------------- |
| `PATTERN_TYPE`           | Set to `adversarial`                |
| `PATTERN_ID`             | Unique adversarial ID               |
| `ADV_ID`                 | Same as `PATTERN_ID`                |
| `AGENT_ROLE`             | `advocate`, `adversary`, or `judge` |
| `ADVERSARIAL_ROUND`      | Current round (1-indexed)           |
| `ADVERSARIAL_MAX_ROUNDS` | Maximum rounds configured           |

---

### 11. Event-Driven

**Purpose:** Pub/sub pattern for reactive agent systems

**Use when:** Monitoring, reactive systems, async workflows, loose coupling

#### Structure

```
              Publisher
                  │
                  ▼
              Event Bus
                  │
          ┌───────┼───────┐
          ▼       ▼       ▼
      Sub A     Sub B   Sub C  (matching subscribers)
          │       │       │
          └───────┼───────┘
                  ▼
            Results List
```

#### API

```python
from scripts.agentica.patterns import EventDriven, Event, Subscriber

bus = EventDriven(subscribers=[
    Subscriber(premise="You handle user events.", event_types=["user.created", "user.deleted"]),
    Subscriber(premise="You log all events.", event_types=["*"]),  # wildcard
])
results = await bus.publish(Event(type="user.created", payload={"user_id": "123"}))
```

#### Parameters

| Param         | Type                     | Default      | Description                        |
| ------------- | ------------------------ | ------------ | ---------------------------------- |
| `subscribers` | `list[Subscriber]`       | **required** | List of subscriber definitions     |
| `model`       | `str \| None`            | `None`       | Model for subscriber agents        |
| `scope`       | `dict[str, Any] \| None` | `None`       | Tools for subscribers              |
| `return_type` | `type`                   | `str`        | Expected return type from handlers |
| `db`          | `CoordinationDB \| None` | `None`       | Coordination database              |

#### Event Dataclass

```python
@dataclass
class Event:
    type: str                  # Event type (e.g., "user.created", "order.placed")
    payload: dict[str, Any]    # Event data
    timestamp: datetime        # When event was created (defaults to now)
```

#### Subscriber Dataclass

```python
@dataclass
class Subscriber:
    premise: str              # Agent's role/expertise
    event_types: list[str]    # Event types to subscribe to. Use "*" for all events
```

#### Example

```python
from scripts.agentica.patterns import EventDriven, Event, Subscriber

# E-commerce event system
bus = EventDriven(
    subscribers=[
        # Order processing
        Subscriber(
            premise="You process new orders and initiate fulfillment.",
            event_types=["order.placed"]
        ),
        # Inventory management
        Subscriber(
            premise="You update inventory when items are sold or restocked.",
            event_types=["order.placed", "inventory.restocked"]
        ),
        # Customer notifications
        Subscriber(
            premise="You send customer notifications for order status changes.",
            event_types=["order.placed", "order.shipped", "order.delivered"]
        ),
        # Analytics
        Subscriber(
            premise="You track all events for analytics and reporting.",
            event_types=["*"]  # Wildcard: receives all events
        )
    ]
)

# Publish event - all matching subscribers are notified concurrently
results = await bus.publish(Event(
    type="order.placed",
    payload={
        "order_id": "ORD-123",
        "customer_id": "CUST-456",
        "items": [{"sku": "ITEM-001", "quantity": 2}],
        "total": 99.99
    }
))

# Results from: order processing, inventory, notifications, analytics
for i, result in enumerate(results):
    print(f"Subscriber {i}: {result}")
```

#### Environment Variables

| Var                      | Purpose                              |
| ------------------------ | ------------------------------------ |
| `PATTERN_TYPE`           | Set to `event_driven`                |
| `PATTERN_ID`             | Unique bus ID                        |
| `EVENT_BUS_ID`           | Same as `PATTERN_ID`                 |
| `AGENT_ROLE`             | Set to `subscriber`                  |
| `SUBSCRIBER_EVENT_TYPES` | JSON array of subscribed event types |

---

## Primitives

### Consensus

Voting mechanism supporting multiple modes.

```python
from scripts.agentica.patterns import Consensus, ConsensusMode

# Majority vote
consensus = Consensus(mode=ConsensusMode.MAJORITY)
winner = consensus.decide(votes=[True, True, False, True])  # -> True

# Unanimous (raises if not all agree)
consensus = Consensus(mode=ConsensusMode.UNANIMOUS)
winner = consensus.decide(votes=[True, True, True])  # -> True

# Threshold (raises if threshold not met)
consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.75)
winner = consensus.decide(votes=[True, True, True, False])  # -> True (75%)

# Weighted votes
consensus = Consensus(mode=ConsensusMode.MAJORITY)
winner = consensus.decide(
    votes=[True, False, True],
    weights=[2.0, 3.0, 1.0]  # False wins with weight 3.0
)

# Structured votes with key extraction
votes = [{"choice": "A", "confidence": 0.9}, {"choice": "A", "confidence": 0.8}]
winner = consensus.decide(votes=votes, key=lambda v: v["choice"])
```

### Aggregator

Combine results from multiple agents.

```python
from scripts.agentica.patterns import Aggregator, AggregateMode

# Merge dicts
agg = Aggregator(mode=AggregateMode.MERGE)
result = agg.aggregate([{"a": 1}, {"b": 2}])  # -> {"a": 1, "b": 2}

# Merge lists
agg = Aggregator(mode=AggregateMode.MERGE, deduplicate=True)
result = agg.aggregate([[1, 2], [2, 3]])  # -> [1, 2, 3]

# Concatenate strings
agg = Aggregator(mode=AggregateMode.CONCAT, separator="\n\n")
result = agg.aggregate(["Part 1", "Part 2"])  # -> "Part 1\n\nPart 2"

# Select best (requires 'score' field)
agg = Aggregator(mode=AggregateMode.BEST)
result = agg.aggregate([
    {"score": 0.8, "result": "Good"},
    {"score": 0.95, "result": "Better"}
])  # -> "Better"
```

### HandoffState

Structured state for agent-to-agent handoffs.

```python
from scripts.agentica.patterns import HandoffState

# Create state
state = HandoffState(
    context="Processing user request",
    next_instruction="Analyze the data"
)

# Add artifacts
state.add_artifact("data", {"users": [...]})
state.add_artifact("config", {"timeout": 30})

# Track handoffs
state.record_handoff(from_agent="extractor", to_agent="transformer")

# Merge states
other = HandoffState(context="Updated", next_instruction="Finalize")
merged = state.merge(other)  # other's context/instruction win

# Serialize
data = state.to_dict()
restored = HandoffState.from_dict(data)
```

---

## Hybrid Patterns

Patterns can compose for complex orchestration.

### Hierarchical + Swarm

Coordinator spawns swarms for research phases.

```python
from scripts.agentica.patterns import Hierarchical, Swarm

# Coordinator decomposes, then spawns swarms for parallel research
async def research_with_swarm(task: str):
    # Phase 1: Coordinator decomposes
    hierarchical = Hierarchical(
        coordinator_premise="Decompose research tasks.",
        specialist_premises={}  # No direct specialists
    )

    # Phase 2: Each subtask gets a swarm
    subtasks = await decompose(task)
    for subtask in subtasks:
        swarm = Swarm(
            perspectives=[
                "Academic perspective",
                "Industry perspective",
                "Historical perspective"
            ]
        )
        await swarm.execute(subtask)
```

### Generator/Critic + Jury

Multiple critics vote on generator output.

```python
from scripts.agentica.patterns import GeneratorCritic, Jury, ConsensusMode

# Generator proposes, jury of critics evaluates
async def reviewed_generation(task: str):
    gc = GeneratorCritic(
        generator_premise="Generate code.",
        critic_premise="Evaluate code quality."
    )

    result = await gc.run(task)

    # Multiple reviewers vote on quality
    jury = Jury(
        num_jurors=3,
        consensus_mode=ConsensusMode.MAJORITY,
        premises=[
            "Security reviewer",
            "Performance reviewer",
            "Style reviewer"
        ]
    )

    approved = await jury.decide(bool, f"Is this code ready? {result}")
    return result if approved else None
```

### Pipeline + Circuit Breaker

Fallback agents on stage failure.

```python
from scripts.agentica.patterns import Pipeline, CircuitBreaker, HandoffState

async def resilient_stage(state: HandoffState) -> HandoffState:
    cb = CircuitBreaker(
        primary_premise="Complex processing",
        fallback_premise="Simple processing",
        max_failures=2
    )
    result = await cb.execute(state.next_instruction)
    state.add_artifact("result", result)
    return state

pipeline = Pipeline(stages=[
    extract_stage,
    resilient_stage,  # Has fallback
    load_stage
])
```

---

## Environment Variables Reference

All patterns set environment variables for hook integration:

| Variable                 | Description                               | Set By                  |
| ------------------------ | ----------------------------------------- | ----------------------- |
| `PATTERN_TYPE`           | Pattern name (lowercase with underscores) | All patterns            |
| `PATTERN_ID`             | Unique instance ID for this execution     | All patterns            |
| `AGENT_ROLE`             | Agent's role in the pattern               | All patterns            |
| `SWARM_ID`               | Swarm instance ID                         | Swarm                   |
| `JURY_ID`                | Jury instance ID                          | Jury                    |
| `JUROR_INDEX`            | Juror's index (0-based)                   | Jury                    |
| `TOTAL_JURORS`           | Total number of jurors                    | Jury                    |
| `PIPELINE_ID`            | Pipeline instance ID                      | Pipeline                |
| `PIPELINE_STAGE_INDEX`   | Stage index (0-based)                     | Pipeline                |
| `PIPELINE_TOTAL_STAGES`  | Total number of stages                    | Pipeline                |
| `GC_ID`                  | Generator/Critic instance ID              | Generator-Critic        |
| `GC_ITERATION`           | Current iteration                         | Generator-Critic        |
| `GC_MAX_ROUNDS`          | Max configured rounds                     | Generator-Critic        |
| `HIERARCHY_ID`           | Hierarchy instance ID                     | Hierarchical            |
| `COORDINATOR_ID`         | Coordinator's ID                          | Hierarchical            |
| `HIERARCHY_LEVEL`        | Nesting level (0=coordinator)             | Hierarchical            |
| `MR_ID`                  | MapReduce instance ID                     | Map-Reduce              |
| `MAPPER_INDEX`           | Mapper's index                            | Map-Reduce              |
| `TOTAL_MAPPERS`          | Total mapper count                        | Map-Reduce              |
| `BLACKBOARD_ID`          | Blackboard instance ID                    | Blackboard              |
| `BLACKBOARD_WRITES_TO`   | Keys specialist writes                    | Blackboard              |
| `BLACKBOARD_READS_FROM`  | Keys specialist reads                     | Blackboard              |
| `CB_ID`                  | Circuit Breaker instance ID               | Circuit Breaker         |
| `CIRCUIT_STATE`          | Current circuit state                     | Circuit Breaker         |
| `COR_ID`                 | Chain of Responsibility ID                | Chain of Responsibility |
| `HANDLER_PRIORITY`       | Handler's priority                        | Chain of Responsibility |
| `CHAIN_LENGTH`           | Total handlers in chain                   | Chain of Responsibility |
| `ADV_ID`                 | Adversarial instance ID                   | Adversarial             |
| `ADVERSARIAL_ROUND`      | Current debate round                      | Adversarial             |
| `ADVERSARIAL_MAX_ROUNDS` | Max debate rounds                         | Adversarial             |
| `EVENT_BUS_ID`           | Event bus instance ID                     | Event-Driven            |
| `SUBSCRIBER_EVENT_TYPES` | JSON array of subscribed types            | Event-Driven            |

---

## Imports

```python
# Core patterns
from scripts.agentica.patterns import (
    Swarm,
    Jury,
    Pipeline,
    GeneratorCritic,
    Hierarchical,
    MapReduce,
    Blackboard,
    CircuitBreaker,
    ChainOfResponsibility,
    Adversarial,
    EventDriven,
)

# Pattern components
from scripts.agentica.patterns import (
    Specialist,           # Blackboard specialist definition
    Handler,              # Chain of Responsibility handler
    Event,                # Event-Driven event
    Subscriber,           # Event-Driven subscriber
    BlackboardState,      # Blackboard shared state
    BlackboardResult,     # Blackboard result
    CircuitState,         # Circuit breaker states enum
)

# Primitives
from scripts.agentica.patterns import (
    Consensus,
    ConsensusMode,
    ConsensusNotReachedError,
    Aggregator,
    AggregateMode,
    HandoffState,
)
```

---

## Testing

Each pattern has comprehensive unit tests in `tests/unit/`:

| Pattern                 | Test File                                  |
| ----------------------- | ------------------------------------------ |
| Swarm                   | `test_agentica_swarm.py`                   |
| Jury                    | `test_agentica_jury.py`                    |
| Pipeline                | `test_agentica_pipeline.py`                |
| Generator-Critic        | `test_agentica_generator_critic.py`        |
| Hierarchical            | `test_agentica_hierarchical.py`            |
| Map-Reduce              | `test_agentica_map_reduce.py`              |
| Blackboard              | `test_agentica_blackboard.py`              |
| Circuit Breaker         | `test_agentica_circuit_breaker.py`         |
| Chain of Responsibility | `test_agentica_chain_of_responsibility.py` |
| Adversarial             | `test_agentica_adversarial.py`             |
| Event-Driven            | `test_agentica_event_driven.py`            |
| Consensus               | `test_agentica_consensus.py`               |
| Aggregator              | `test_agentica_aggregator.py`              |
| Handoff                 | `test_agentica_handoff.py`                 |

Run tests:
```bash
# All pattern tests
uv run pytest tests/unit/test_agentica_*.py -v

# Specific pattern
uv run pytest tests/unit/test_agentica_swarm.py -v
```
