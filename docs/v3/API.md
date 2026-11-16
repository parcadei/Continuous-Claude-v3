# API Reference

Complete interface documentation for claude-continuity-kit.

---

## Patterns Module

Multi-agent orchestration patterns for coordinating AI agents.

**Import:** `from scripts.agentica.patterns import *`

---

### Swarm

Spawn multiple agents with different perspectives in parallel, aggregate results.

```python
class Swarm:
    def __init__(
        self,
        perspectives: list[str],
        aggregate_mode: AggregateMode = AggregateMode.MERGE,
        aggregation_separator: str = " ",
        fail_fast: bool = False,
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        mcp: str | None = None,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Swarm pattern.'''

    async def execute(
        self,
        query: str,
        return_type: type = None
    ) -> Any:
        '''Execute swarm on a query.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| perspectives | list[str] | Yes | - | List of agent premises (one per agent) |
| aggregate_mode | AggregateMode | No | MERGE | How to combine results (MERGE, CONCAT, BEST) |
| aggregation_separator | str | No | " " | Separator for CONCAT mode |
| fail_fast | bool | No | False | If True, stop on first error |
| model | str | No | None | Model to use for all agents |
| scope | dict[str, Any] | No | None | Tools/functions available to all agents |
| mcp | str | No | None | MCP config path to pass to all agents |
| db | CoordinationDB | No | None | Optional coordination database for tracking |

**Returns:** Aggregated results from all agents (type depends on aggregate_mode)

**Raises:**
- `ValueError` - If perspectives is None or empty

**Environment Variables Set:**
- `PATTERN_TYPE=swarm`
- `PATTERN_ID=<swarm_id>`
- `SWARM_ID=<swarm_id>`
- `AGENT_ROLE=worker`

**Example:**
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

---

### Hierarchical

Coordinator decomposes tasks for specialist agents.

```python
class Hierarchical:
    def __init__(
        self,
        coordinator_premise: str,
        specialist_premises: dict[str, str],
        coordinator_scope: dict[str, Any] | None = None,
        specialist_scope: dict[str, Any] | None = None,
        coordinator_model: str | None = None,
        specialist_model: str | None = None,
        aggregation_mode: AggregateMode = AggregateMode.CONCAT,
        aggregation_separator: str = "\n\n",
        aggregator: Aggregator | None = None,
        fail_fast: bool = False,
        return_type: type = str,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Hierarchical coordinator.'''

    async def execute(self, task: str) -> Any:
        '''Execute hierarchical pattern on a task.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| coordinator_premise | str | Yes | - | Premise for coordinator agent |
| specialist_premises | dict[str, str] | Yes | - | Dict mapping specialist name to premise |
| coordinator_scope | dict[str, Any] | No | None | Tools for coordinator |
| specialist_scope | dict[str, Any] | No | None | Tools for specialists |
| coordinator_model | str | No | None | Model for coordinator |
| specialist_model | str | No | None | Model for specialists |
| aggregation_mode | AggregateMode | No | CONCAT | How to aggregate specialist results |
| aggregation_separator | str | No | "\n\n" | Separator for aggregation |
| aggregator | Aggregator | No | None | Custom Aggregator instance |
| fail_fast | bool | No | False | Stop on first specialist failure |
| return_type | type | No | str | Expected return type for final result |
| db | CoordinationDB | No | None | Optional coordination database |

**Returns:** Synthesized final result from coordinator

**Environment Variables Set:**
- `PATTERN_TYPE=hierarchical`
- `PATTERN_ID=<hierarchy_id>`
- `HIERARCHY_ID=<hierarchy_id>`
- `AGENT_ROLE=coordinator|specialist`
- `COORDINATOR_ID=<coordinator_id>` (for specialists)
- `HIERARCHY_LEVEL=<n>` (0 = coordinator, 1+ = specialist)

**Example:**
```python
from scripts.agentica.patterns import Hierarchical

hierarchical = Hierarchical(
    coordinator_premise="You break tasks into subtasks.",
    specialist_premises={
        "researcher": "You research topics.",
        "analyst": "You analyze data."
    }
)
result = await hierarchical.execute("Research and analyze topic X")
```

---

### Jury

N independent agents vote on a question via Consensus mechanism.

```python
class Jury:
    def __init__(
        self,
        num_jurors: int,
        consensus_mode: ConsensusMode,
        threshold: float | None = None,
        weights: list[float] | None = None,
        premise: str | None = None,
        premises: list[str] | None = None,
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        key: Callable[[Any], Any] | None = None,
        allow_partial: bool = False,
        min_jurors: int | None = None,
        debug: bool = False,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Jury.'''

    async def decide(self, return_type: type, question: str) -> Any:
        '''Jury decides on a question.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| num_jurors | int | Yes | - | Number of jurors to spawn |
| consensus_mode | ConsensusMode | Yes | - | Voting mode (MAJORITY, UNANIMOUS, THRESHOLD) |
| threshold | float | No | None | Required agreement percentage for THRESHOLD mode |
| weights | list[float] | No | None | Optional weights for each juror |
| premise | str | No | None | Single premise for all jurors |
| premises | list[str] | No | None | Different premise per juror |
| model | str | No | None | Model to use for all jurors |
| scope | dict[str, Any] | No | None | Tools available to all jurors |
| key | Callable | No | None | Function to extract decision from structured votes |
| allow_partial | bool | No | False | Continue with partial votes if some jurors fail |
| min_jurors | int | No | num_jurors | Minimum successful jurors required |
| debug | bool | No | False | Track individual votes for debugging |
| db | CoordinationDB | No | None | Optional coordination database |

**Returns:** Consensus verdict from jurors

**Raises:**
- `ValueError` - Invalid configuration
- `ConsensusNotReachedError` - If consensus cannot be reached

**Environment Variables Set:**
- `PATTERN_TYPE=jury`
- `PATTERN_ID=<jury_id>`
- `JURY_ID=<jury_id>`
- `AGENT_ROLE=juror`
- `JUROR_INDEX=<n>` (0-indexed)
- `TOTAL_JURORS=<n>`

**Example:**
```python
from scripts.agentica.patterns import Jury, ConsensusMode

jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.MAJORITY
)
verdict = await jury.decide(bool, "Is this code safe?")
```

---

### Pipeline

Sequential stage execution with HandoffState.

```python
class Pipeline:
    def __init__(
        self,
        stages: list[Callable[[HandoffState], HandoffState]]
    ) -> None:
        '''Initialize Pipeline.'''

    async def run(self, initial_state: HandoffState) -> HandoffState:
        '''Run the pipeline.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| stages | list[Callable] | Yes | - | List of async functions that take and return HandoffState |

**Returns:** `HandoffState` - Final state after all stages

**Raises:**
- `ValueError` - If stages is empty

**Environment Variables Set:**
- `PATTERN_TYPE=pipeline`
- `PATTERN_ID=<pipeline_id>`
- `PIPELINE_ID=<pipeline_id>`
- `AGENT_ROLE=stage`
- `PIPELINE_STAGE_INDEX=<n>` (0-indexed)
- `PIPELINE_TOTAL_STAGES=<n>`

**Example:**
```python
from scripts.agentica.patterns import Pipeline, HandoffState

async def fetch(state: HandoffState) -> HandoffState:
    state.add_artifact("data", fetch_data())
    return state

async def transform(state: HandoffState) -> HandoffState:
    data = state.artifacts["data"]
    state.add_artifact("transformed", transform(data))
    return state

pipeline = Pipeline(stages=[fetch, transform])
result = await pipeline.run(HandoffState(
    context="Initial context",
    next_instruction="Start processing"
))
```

---

### GeneratorCritic

Iterative refinement loop with generator and critic agents.

```python
class GeneratorCritic:
    def __init__(
        self,
        generator_premise: str,
        critic_premise: str,
        max_rounds: int = 3,
        generator_scope: dict[str, Any] | None = None,
        critic_scope: dict[str, Any] | None = None,
        generator_model: str | None = None,
        critic_model: str | None = None,
        is_approved: Callable[[HandoffState], bool] | None = None,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize GeneratorCritic.'''

    async def run(self, task: str) -> HandoffState:
        '''Run generator/critic loop.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| generator_premise | str | Yes | - | Premise for generator agent |
| critic_premise | str | Yes | - | Premise for critic agent |
| max_rounds | int | No | 3 | Maximum iteration rounds |
| generator_scope | dict[str, Any] | No | None | Tools for generator |
| critic_scope | dict[str, Any] | No | None | Tools for critic |
| generator_model | str | No | None | Model for generator |
| critic_model | str | No | None | Model for critic |
| is_approved | Callable | No | None | Custom function to check if state is approved |
| db | CoordinationDB | No | None | Optional coordination database |

**Returns:** `HandoffState` - Final state (approved or max rounds reached)

**Raises:**
- `ValueError` - If max_rounds is not positive

**Environment Variables Set:**
- `PATTERN_TYPE=generator_critic`
- `PATTERN_ID=<gc_id>`
- `GC_ID=<gc_id>`
- `AGENT_ROLE=generator|critic`
- `GC_ITERATION=<n>`
- `GC_MAX_ROUNDS=<n>`

**Example:**
```python
from scripts.agentica.patterns import GeneratorCritic

gc = GeneratorCritic(
    generator_premise="You generate Python code.",
    critic_premise="You review Python code for correctness."
)
result = await gc.run("Create a function to parse JSON")
```

---

### CircuitBreaker

Failure detection with fallback routing.

```python
class CircuitBreaker:
    def __init__(
        self,
        primary_premise: str,
        fallback_premise: str,
        max_failures: int = 3,
        reset_timeout: float = 60,
        primary_model: str | None = None,
        fallback_model: str | None = None,
        primary_scope: dict[str, Any] | None = None,
        fallback_scope: dict[str, Any] | None = None,
        return_type: type = str,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize CircuitBreaker.'''

    async def execute(self, query: str) -> Any:
        '''Execute query with circuit breaker protection.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| primary_premise | str | Yes | - | Premise for primary agent |
| fallback_premise | str | Yes | - | Premise for fallback agent |
| max_failures | int | No | 3 | Consecutive failures before opening circuit |
| reset_timeout | float | No | 60 | Seconds before trying primary again |
| primary_model | str | No | None | Model for primary agent |
| fallback_model | str | No | None | Model for fallback agent |
| primary_scope | dict[str, Any] | No | None | Tools for primary agent |
| fallback_scope | dict[str, Any] | No | None | Tools for fallback agent |
| return_type | type | No | str | Expected return type for agent calls |
| db | CoordinationDB | No | None | Optional coordination database |

**Returns:** Result from primary or fallback agent

**Circuit States:**
- `CLOSED` - Normal operation, primary agent is used
- `OPEN` - Primary has failed too many times, fallback is used
- `HALF_OPEN` - Testing primary after timeout, one failure reopens

**Environment Variables Set:**
- `PATTERN_TYPE=circuit_breaker`
- `PATTERN_ID=<cb_id>`
- `CB_ID=<cb_id>`
- `AGENT_ROLE=primary|fallback`
- `CIRCUIT_STATE=<state>`

**Example:**
```python
from scripts.agentica.patterns import CircuitBreaker

cb = CircuitBreaker(
    primary_premise="You implement features.",
    fallback_premise="You implement simpler versions.",
    max_failures=3,
    reset_timeout=60
)
result = await cb.execute("Implement OAuth flow")
```

---

### MapReduce

Fan out work to N mapper agents in parallel, then combine with reducer.

```python
class MapReduce:
    def __init__(
        self,
        mapper_premise: str,
        reducer_premise: str,
        num_mappers: int = 3,
        mapper_model: str | None = None,
        reducer_model: str | None = None,
        mapper_scope: dict[str, Any] | None = None,
        reducer_scope: dict[str, Any] | None = None,
        fail_fast: bool = True,
        return_type: type = str,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize MapReduce pattern.'''

    async def execute(self, query: str, chunks: list[Any]) -> Any:
        '''Execute MapReduce pattern.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| mapper_premise | str | Yes | - | Premise for mapper agents |
| reducer_premise | str | Yes | - | Premise for reducer agent |
| num_mappers | int | No | 3 | Number of mapper agents to spawn |
| mapper_model | str | No | None | Model for mapper agents |
| reducer_model | str | No | None | Model for reducer agent |
| mapper_scope | dict[str, Any] | No | None | Tools for mapper agents |
| reducer_scope | dict[str, Any] | No | None | Tools for reducer agent |
| fail_fast | bool | No | True | If True, stop on first mapper error |
| return_type | type | No | str | Expected return type for final result |
| db | CoordinationDB | No | None | Optional coordination database |

**Returns:** Final synthesized result from reducer

**Raises:**
- `ValueError` - If num_mappers < 1

**Environment Variables Set:**
- `PATTERN_TYPE=map_reduce`
- `PATTERN_ID=<mr_id>`
- `MR_ID=<mr_id>`
- `AGENT_ROLE=mapper|reducer`
- `MAPPER_INDEX=<n>` (for mappers)
- `TOTAL_MAPPERS=<n>`

**Example:**
```python
from scripts.agentica.patterns import MapReduce

mr = MapReduce(
    mapper_premise="You analyze one section of code.",
    reducer_premise="You synthesize analysis from multiple reviewers.",
    num_mappers=4
)
result = await mr.execute(
    "Review this codebase",
    chunks=["file1.py", "file2.py", "file3.py", "file4.py"]
)
```

---

### ChainOfResponsibility

Route request to first handler that can process it.

```python
@dataclass
class Handler:
    '''Handler for Chain of Responsibility pattern.'''
    premise: str
    can_handle: Callable[[str], bool]
    priority: int = 0

class ChainOfResponsibility:
    def __init__(
        self,
        handlers: list[Handler],
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        return_type: type = str,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Chain of Responsibility.'''

    async def process(self, query: str) -> Any:
        '''Process a query through the chain of handlers.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| handlers | list[Handler] | Yes | - | List of Handler objects (sorted by priority) |
| model | str | No | None | Model to use for handler agents |
| scope | dict[str, Any] | No | None | Tools available to handler agents |
| return_type | type | No | str | Expected return type from handler |
| db | CoordinationDB | No | None | Optional coordination database |

**Handler Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| premise | str | Yes | - | The agent premise for this handler |
| can_handle | Callable[[str], bool] | Yes | - | Returns True if this handler can handle the query |
| priority | int | No | 0 | Lower number = higher priority |

**Returns:** Result from the handler that processed the request

**Raises:**
- `ValueError` - If no handler can handle the query

**Environment Variables Set:**
- `PATTERN_TYPE=chain_of_responsibility`
- `PATTERN_ID=<cor_id>`
- `COR_ID=<cor_id>`
- `AGENT_ROLE=handler`
- `HANDLER_PRIORITY=<n>`
- `CHAIN_LENGTH=<n>`

**Example:**
```python
from scripts.agentica.patterns import ChainOfResponsibility, Handler

chain = ChainOfResponsibility(handlers=[
    Handler(
        premise="You handle Python questions.",
        can_handle=lambda q: "python" in q.lower()
    ),
    Handler(
        premise="You handle JavaScript questions.",
        can_handle=lambda q: "javascript" in q.lower()
    ),
    Handler(
        premise="You handle general programming questions.",
        can_handle=lambda q: True  # fallback
    ),
])
result = await chain.process("How do I use async in Python?")
```

---

### Adversarial

Agents take opposing positions to stress-test ideas through structured debate.

```python
class Adversarial:
    def __init__(
        self,
        advocate_premise: str,
        adversary_premise: str,
        judge_premise: str | None = None,
        max_rounds: int = 3,
        advocate_model: str | None = None,
        adversary_model: str | None = None,
        judge_model: str | None = None,
        advocate_scope: dict[str, Any] | None = None,
        adversary_scope: dict[str, Any] | None = None,
        judge_scope: dict[str, Any] | None = None,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Adversarial pattern.'''

    async def debate(self, question: str) -> dict[str, Any]:
        '''Run adversarial debate on a question.'''

    async def resolve(self, question: str) -> dict[str, Any] | str:
        '''Run debate and resolve with judge (if available).'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| advocate_premise | str | Yes | - | Premise for the advocate agent (argues in favor) |
| adversary_premise | str | Yes | - | Premise for the adversary agent (attacks/critiques) |
| judge_premise | str | No | None | Optional premise for judge agent (decides winner) |
| max_rounds | int | No | 3 | Maximum debate rounds |
| advocate_model | str | No | None | Model for advocate agent |
| adversary_model | str | No | None | Model for adversary agent |
| judge_model | str | No | None | Model for judge agent |
| advocate_scope | dict[str, Any] | No | None | Tools for advocate agent |
| adversary_scope | dict[str, Any] | No | None | Tools for adversary agent |
| judge_scope | dict[str, Any] | No | None | Tools for judge agent |
| db | CoordinationDB | No | None | Optional coordination database |

**Returns:**
- `debate()`: Dict with debate history and final positions
- `resolve()`: Judge's verdict if judge exists, otherwise both final positions

**Raises:**
- `ValueError` - If max_rounds < 1

**Environment Variables Set:**
- `PATTERN_TYPE=adversarial`
- `PATTERN_ID=<adv_id>`
- `ADV_ID=<adv_id>`
- `AGENT_ROLE=advocate|adversary|judge`
- `ADVERSARIAL_ROUND=<n>`
- `ADVERSARIAL_MAX_ROUNDS=<n>`

**Example:**
```python
from scripts.agentica.patterns import Adversarial

adv = Adversarial(
    advocate_premise="You argue in favor of this decision.",
    adversary_premise="You find flaws in decisions.",
    judge_premise="You decide which position is stronger.",
    max_rounds=3
)
result = await adv.resolve("Should we use microservices or monolith?")
```

---

### EventDriven

Agents react to events published on a bus with loose coupling.

```python
@dataclass
class Event:
    '''An event to be published on the event bus.'''
    type: str
    payload: dict[str, Any]
    timestamp: Any = field(default_factory=lambda: datetime.now())

@dataclass
class Subscriber:
    '''A subscriber that reacts to specific event types.'''
    premise: str
    event_types: list[str]  # Use "*" for wildcard (all events)

class EventDriven:
    def __init__(
        self,
        subscribers: list[Subscriber],
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        return_type: type = str,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Event-Driven pattern.'''

    async def publish(self, event: Event) -> list[Any]:
        '''Publish an event to all matching subscribers.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| subscribers | list[Subscriber] | Yes | - | List of Subscriber definitions |
| model | str | No | None | Model to use for subscriber agents |
| scope | dict[str, Any] | No | None | Tools available to subscriber agents |
| return_type | type | No | str | Expected return type from subscriber handlers |
| db | CoordinationDB | No | None | Optional coordination database |

**Event Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| type | str | Yes | - | Event type string (e.g., "user.created") |
| payload | dict[str, Any] | Yes | - | Event data as a dictionary |
| timestamp | Any | No | now() | When the event was created |

**Subscriber Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| premise | str | Yes | - | The agent premise for this subscriber |
| event_types | list[str] | Yes | - | Event types to subscribe to ("*" for all) |

**Returns:** List of results from all matching subscriber handlers

**Environment Variables Set:**
- `PATTERN_TYPE=event_driven`
- `PATTERN_ID=<bus_id>`
- `EVENT_BUS_ID=<bus_id>`
- `AGENT_ROLE=subscriber`
- `SUBSCRIBER_EVENT_TYPES=<json_list>`

**Example:**
```python
from scripts.agentica.patterns import EventDriven, Event, Subscriber

bus = EventDriven(subscribers=[
    Subscriber(
        premise="You handle user created events.",
        event_types=["user.created"]
    ),
    Subscriber(
        premise="You handle order placed events.",
        event_types=["order.placed"]
    ),
    Subscriber(
        premise="You log all events.",
        event_types=["*"]  # wildcard
    ),
])
results = await bus.publish(Event(
    type="user.created",
    payload={"user_id": "123"}
))
```

---

### Blackboard

Multiple specialists contribute to shared state.

```python
@dataclass
class Specialist:
    '''A specialist agent that contributes to the blackboard.'''
    premise: str
    writes_to: list[str] = field(default_factory=list)
    reads_from: list[str] = field(default_factory=list)

class BlackboardState:
    '''Shared state for the Blackboard pattern.'''
    def __init__(self) -> None: ...
    def __getitem__(self, key: str) -> Any: ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def __contains__(self, key: str) -> bool: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def keys(self): ...
    def items(self): ...
    def to_dict(self) -> dict[str, Any]: ...

@dataclass
class BlackboardResult:
    '''Result from Blackboard.solve().'''
    state: BlackboardState
    iterations: int
    completed: bool

class Blackboard:
    def __init__(
        self,
        specialists: list[Specialist],
        controller_premise: str,
        max_iterations: int = 5,
        controller_model: str | None = None,
        specialist_model: str | None = None,
        controller_scope: dict[str, Any] | None = None,
        specialist_scope: dict[str, Any] | None = None,
        db: CoordinationDB | None = None
    ) -> None:
        '''Initialize Blackboard pattern.'''

    async def solve(self, query: str) -> BlackboardResult:
        '''Solve a problem using the blackboard pattern.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| specialists | list[Specialist] | Yes | - | List of Specialist definitions |
| controller_premise | str | Yes | - | Premise for the controller agent |
| max_iterations | int | No | 5 | Maximum iterations before stopping |
| controller_model | str | No | None | Model for controller agent |
| specialist_model | str | No | None | Model for specialist agents |
| controller_scope | dict[str, Any] | No | None | Tools for controller agent |
| specialist_scope | dict[str, Any] | No | None | Tools for specialist agents |
| db | CoordinationDB | No | None | Optional coordination database |

**Specialist Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| premise | str | Yes | - | The premise/role for this specialist |
| writes_to | list[str] | No | [] | Blackboard keys this specialist writes to |
| reads_from | list[str] | No | [] | Blackboard keys this specialist reads from |

**Returns:** `BlackboardResult` with final state, iterations, and completion status

**Raises:**
- `ValueError` - If specialists is empty

**Environment Variables Set:**
- `PATTERN_TYPE=blackboard`
- `BLACKBOARD_ID=<blackboard_id>`
- `AGENT_ROLE=controller|specialist`
- `BLACKBOARD_WRITES_TO=<comma_separated_keys>` (for specialists)
- `BLACKBOARD_READS_FROM=<comma_separated_keys>` (for specialists)

**Example:**
```python
from scripts.agentica.patterns import Blackboard, Specialist

bb = Blackboard(
    specialists=[
        Specialist(
            premise="You analyze requirements.",
            writes_to=["requirements"]
        ),
        Specialist(
            premise="You design architecture.",
            writes_to=["architecture"],
            reads_from=["requirements"]
        ),
        Specialist(
            premise="You write implementation plan.",
            writes_to=["plan"],
            reads_from=["architecture"]
        ),
    ],
    controller_premise="You check if the design is complete.",
    max_iterations=5
)
result = await bb.solve("Build a user authentication system")
print(result.state.to_dict())
```

---

## Primitives

Core primitives for multi-agent coordination.

**Import:** `from scripts.agentica.patterns.primitives import *`

---

### ConsensusMode

Voting modes for agent consensus.

```python
class ConsensusMode(Enum):
    MAJORITY = "majority"    # Most common vote wins
    UNANIMOUS = "unanimous"  # All votes must agree
    THRESHOLD = "threshold"  # Percentage of votes must agree
```

---

### Consensus

Consensus voting mechanism for multi-agent decisions.

```python
class Consensus:
    def __init__(
        self,
        mode: ConsensusMode,
        threshold: float | None = None
    ) -> None:
        '''Initialize consensus mechanism.'''

    def decide(
        self,
        votes: list[Any],
        weights: list[float] | None = None,
        key: Callable[[Any], Any] | None = None
    ) -> Any:
        '''Decide consensus from votes.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| mode | ConsensusMode | Yes | - | Voting mode |
| threshold | float | No | None | Required agreement percentage (0.0-1.0) for THRESHOLD mode |

**decide() Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| votes | list[Any] | Yes | - | List of votes from agents |
| weights | list[float] | No | None | Optional weights for each vote |
| key | Callable | No | None | Function to extract comparable value from vote |

**Returns:** The winning vote (original vote object, not extracted key)

**Raises:**
- `ValueError` - Invalid inputs (empty votes, mismatched weights, negative weights)
- `TypeError` - Unhashable vote types without key function
- `ConsensusNotReachedError` - Consensus cannot be achieved under mode

**Example:**
```python
from scripts.agentica.patterns.primitives import Consensus, ConsensusMode

consensus = Consensus(mode=ConsensusMode.MAJORITY)
winner = consensus.decide(["yes", "no", "yes", "yes"])
# winner == "yes"

consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.7)
winner = consensus.decide(["approve", "approve", "reject"])
# Raises ConsensusNotReachedError (66% < 70%)
```

---

### AggregateMode

Modes for aggregating results from multiple agents.

```python
class AggregateMode(Enum):
    MERGE = "merge"    # Combine dicts/lists
    CONCAT = "concat"  # Join strings
    BEST = "best"      # Pick highest score
```

---

### Aggregator

Aggregate results from multiple agents.

```python
class Aggregator:
    def __init__(
        self,
        mode: AggregateMode,
        separator: str = " ",
        deduplicate: bool = False
    ) -> None:
        '''Initialize aggregator.'''

    def aggregate(self, results: list[Any]) -> Any:
        '''Aggregate multiple results into one.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| mode | AggregateMode | Yes | - | Aggregation mode |
| separator | str | No | " " | String separator for CONCAT mode |
| deduplicate | bool | No | False | Remove duplicates in MERGE/CONCAT modes |

**Returns:** Aggregated result (type depends on mode)

**Raises:**
- `ValueError` - Empty results or missing required fields
- `TypeError` - Incompatible types for merging

**Modes:**
- `MERGE`: Combine dicts (last wins on conflicts) or concatenate lists
- `CONCAT`: Join strings with separator
- `BEST`: Select result with highest `score` field

**Example:**
```python
from scripts.agentica.patterns.primitives import Aggregator, AggregateMode

# MERGE dicts
agg = Aggregator(mode=AggregateMode.MERGE)
result = agg.aggregate([{"a": 1}, {"b": 2}])
# result == {"a": 1, "b": 2}

# CONCAT strings
agg = Aggregator(mode=AggregateMode.CONCAT, separator="\n")
result = agg.aggregate(["Line 1", "Line 2"])
# result == "Line 1\nLine 2"

# BEST score
agg = Aggregator(mode=AggregateMode.BEST)
result = agg.aggregate([
    {"score": 0.8, "result": "good"},
    {"score": 0.95, "result": "excellent"}
])
# result == "excellent"
```

---

### HandoffState

Structured state for agent-to-agent handoffs.

```python
@dataclass
class HandoffState:
    context: str
    next_instruction: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    _handoff_chain: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        '''Serialize to dictionary.'''

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffState":
        '''Deserialize from dictionary.'''

    def add_artifact(self, key: str, value: Any) -> None:
        '''Add an artifact to the state.'''

    def merge(self, other: "HandoffState") -> "HandoffState":
        '''Merge another state into this one.'''

    def record_handoff(self, from_agent: str, to_agent: str) -> None:
        '''Record a handoff in the chain.'''

    def get_handoff_chain(self) -> list[dict[str, str]]:
        '''Get the handoff chain history.'''

    def update_instruction(self, instruction: str) -> None:
        '''Update the next instruction.'''

    def clear_artifacts(self) -> None:
        '''Clear all artifacts while preserving other state.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| context | str | Yes | - | Current situation/task context |
| next_instruction | str | Yes | - | What the next agent should do |
| artifacts | dict[str, Any] | No | {} | Data/files produced so far |
| metadata | dict[str, Any] | No | {} | Arbitrary metadata (priority, tags, etc.) |

**Example:**
```python
from scripts.agentica.patterns.primitives import HandoffState

state = HandoffState(
    context="Building a REST API",
    next_instruction="Design the database schema"
)
state.add_artifact("requirements", ["auth", "users", "posts"])
state.record_handoff(from_agent="planner", to_agent="architect")

# Merge states
other = HandoffState(
    context="Updated context",
    next_instruction="Implement the schema"
)
merged = state.merge(other)
```

---

## MCP Runtime

Model Context Protocol client for connecting to MCP servers.

**Import:** `from src.runtime.mcp_client import McpClientManager, get_mcp_client_manager, call_mcp_tool`

---

### ConnectionState

Explicit states for the MCP Client Manager lifecycle.

```python
class ConnectionState(Enum):
    UNINITIALIZED = "uninitialized"  # Manager created but not initialized
    INITIALIZED = "initialized"      # Configuration loaded, no server connections
    CONNECTED = "connected"          # At least one server connection established
```

---

### McpClientManager

Lazy-loading MCP client manager with explicit state machine.

```python
class McpClientManager:
    def __init__(self) -> None:
        '''Initialize an uninitialized MCP Client Manager.'''

    async def initialize(self, config_path: Path | None = None) -> None:
        '''Initialize the manager by loading configuration.'''

    async def call_tool(
        self,
        tool_identifier: str,
        params: dict[str, Any],
        max_retries: int = 1
    ) -> Any:
        '''Call an MCP tool with lazy server connection and automatic retry.'''

    async def list_all_tools(self) -> list[Tool]:
        '''List all available tools from all enabled servers.'''

    async def cleanup(self) -> None:
        '''Close all connections and reset manager to uninitialized state.'''
```

**State Transitions:**
- `UNINITIALIZED -> INITIALIZED` (via `initialize()`)
- `INITIALIZED -> CONNECTED` (via `_connect_to_server()`)
- `any state -> UNINITIALIZED` (via `cleanup()`)

**Tool Identifier Format:** `"serverName__toolName"` (double underscore)

**initialize() Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| config_path | Path | No | None | Path to config file. If not provided, merges global config with project config |

**call_tool() Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| tool_identifier | str | Yes | - | Tool identifier in format "serverName__toolName" |
| params | dict[str, Any] | Yes | - | Parameters to pass to the tool |
| max_retries | int | No | 1 | Maximum number of retry attempts on failure |

**Returns:** The tool execution result (unwrapped from response)

**Raises:**
- `ConfigurationError` - If manager not initialized
- `ToolNotFoundError` - If tool doesn't exist on the specified server
- `ToolExecutionError` - If tool execution fails after all retries
- `ServerConnectionError` - If unable to connect to server

**Example:**
```python
from src.runtime.mcp_client import McpClientManager

manager = McpClientManager()
await manager.initialize()

result = await manager.call_tool(
    "morph__warpgrep_codebase_search",
    {"query": "TODO", "path": "."}
)

await manager.cleanup()
```

---

### get_mcp_client_manager

Get or create the singleton MCP Client Manager instance.

```python
def get_mcp_client_manager() -> McpClientManager:
    '''Get or create the singleton MCP Client Manager instance.'''
```

**Returns:** The singleton McpClientManager instance

---

### call_mcp_tool

Convenience function for calling MCP tools using the singleton manager.

```python
async def call_mcp_tool(
    tool_identifier: str,
    params: dict[str, Any],
    max_retries: int = 1
) -> Any:
    '''Convenience function for calling MCP tools.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| tool_identifier | str | Yes | - | Tool identifier in format "serverName__toolName" |
| params | dict[str, Any] | Yes | - | Parameters to pass to the tool |
| max_retries | int | No | 1 | Maximum number of retry attempts on failure |

**Returns:** The tool execution result

**Example:**
```python
from src.runtime.mcp_client import call_mcp_tool

# Manager must be initialized first
result = await call_mcp_tool(
    "perplexity__perplexity_ask",
    {"query": "What is the latest Python version?"}
)
```

---

## Memory Services

Memory storage with Core, Archival, and Recall memory types.

---

### MemoryService

SQLite-based memory service with FTS5 search.

**Import:** `from scripts.agentica.memory_service import MemoryService`

```python
class MemoryService:
    def __init__(
        self,
        session_id: str = "default",
        db_path: Path | None = None
    ) -> None:
        '''Initialize memory service.'''

    async def connect(self) -> None:
        '''Initialize backend connection and schema.'''

    async def close(self) -> None:
        '''Close backend connection.'''

    # Core Memory
    async def set_core(self, key: str, value: str) -> None:
        '''Set a core memory block.'''

    async def get_core(self, key: str) -> str | None:
        '''Get a core memory block.'''

    async def list_core_keys(self) -> list[str]:
        '''List all core memory block keys.'''

    async def delete_core(self, key: str) -> None:
        '''Delete a core memory block.'''

    async def get_all_core(self) -> dict[str, str]:
        '''Get all core memory blocks.'''

    # Archival Memory
    async def store(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None
    ) -> str:
        '''Store a fact in archival memory.'''

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        '''Search archival memory with FTS5.'''

    async def delete_archival(self, memory_id: str) -> None:
        '''Delete a fact from archival memory.'''

    # Recall Memory
    async def recall(
        self,
        query: str,
        include_core: bool = True,
        limit: int = 5
    ) -> str:
        '''Recall information from all memory sources.'''

    async def to_context(self, max_archival: int = 10) -> str:
        '''Generate context string for prompt injection.'''
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| session_id | str | No | "default" | Session identifier for isolation |
| db_path | Path | No | None | Custom database path |

**Example:**
```python
from scripts.agentica.memory_service import MemoryService

memory = MemoryService(session_id="abc123")
await memory.connect()

# Core memory (in-context)
await memory.set_core("persona", "You are a helpful assistant")
await memory.set_core("task", "Build a REST API")

# Archival memory (searchable)
await memory.store("User prefers Python over JavaScript")
await memory.store("Project uses PostgreSQL database")

# Recall (cross-source query)
result = await memory.recall("What database does the project use?")

# Generate context for prompt
context = await memory.to_context()

await memory.close()
```

---

### MemoryServicePG

PostgreSQL + pgvector memory service with vector search.

**Import:** `from scripts.agentica.memory_service_pg import MemoryServicePG`

```python
class MemoryServicePG:
    def __init__(
        self,
        session_id: str = "default",
        agent_id: str | None = None
    ) -> None:
        '''Initialize memory service.'''

    async def connect(self) -> None:
        '''Initialize connection pool.'''

    async def close(self) -> None:
        '''Release connection.'''

    # Core Memory (same as MemoryService)
    async def set_core(self, key: str, value: str) -> None: ...
    async def get_core(self, key: str) -> str | None: ...
    async def list_core_keys(self) -> list[str]: ...
    async def delete_core(self, key: str) -> None: ...
    async def get_all_core(self) -> dict[str, str]: ...

    # Archival Memory
    async def store(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None
    ) -> str:
        '''Store a fact in archival memory.'''

    async def search_text(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        '''Search archival memory with full-text search.'''

    async def search_vector(
        self,
        query_embedding: list[float],
        limit: int = 10
    ) -> list[dict[str, Any]]:
        '''Search archival memory with vector similarity.'''

    async def search_vector_with_threshold(
        self,
        query_embedding: list[float],
        threshold: float = 0.0,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        '''Search with vector similarity and threshold filter.'''

    async def search_vector_with_filter(
        self,
        query_embedding: list[float],
        metadata_filter: dict[str, Any],
        limit: int = 10
    ) -> list[dict[str, Any]]:
        '''Search with vector similarity and metadata filter.'''

    async def search_hybrid(
        self,
        text_query: str,
        query_embedding: list[float],
        limit: int = 10,
        text_weight: float = 0.3,
        vector_weight: float = 0.7
    ) -> list[dict[str, Any]]:
        '''Hybrid search combining full-text search and vector similarity.'''

    async def search_hybrid_rrf(
        self,
        text_query: str,
        query_embedding: list[float],
        limit: int = 10,
        k: int = 60
    ) -> list[dict[str, Any]]:
        '''Hybrid search using Reciprocal Rank Fusion.'''

    async def store_with_embedding(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedder: EmbeddingProvider | None = None
    ) -> str:
        '''Store a fact with auto-generated embedding.'''

    async def delete_archival(self, memory_id: str) -> None: ...

    # Recall Memory (same as MemoryService)
    async def recall(self, query: str, include_core: bool = True, limit: int = 5) -> str: ...
    async def to_context(self, max_archival: int = 10) -> str: ...
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| session_id | str | No | "default" | Session identifier for isolation |
| agent_id | str | No | None | Agent identifier for agent-specific memory |

**Scoping Model (R-Flow):**
- `session_id`: Claude Code session
- `agent_id`: Optional agent identifier within session

**Example:**
```python
from scripts.agentica.memory_service_pg import MemoryServicePG

memory = MemoryServicePG(session_id="abc123", agent_id="agent-1")
await memory.connect()

# Store with embedding
await memory.store(
    "User prefers Python",
    embedding=[0.1, 0.2, 0.3, ...]  # Padded to 4096 dimensions
)

# Vector search
results = await memory.search_vector(query_embedding, limit=5)

# Hybrid search with RRF
results = await memory.search_hybrid_rrf(
    text_query="Python preferences",
    query_embedding=query_embedding,
    limit=10,
    k=60
)

await memory.close()
```

---

### ArchivalFact

A fact stored in archival memory.

```python
@dataclass
class ArchivalFact:
    id: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime
    similarity: float | None = None  # For vector search results (PostgreSQL only)
```

---

## Type Definitions

### CircuitState

Circuit breaker states.

```python
class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation, using primary
    OPEN = "open"            # Failure threshold reached, using fallback
    HALF_OPEN = "half_open"  # Testing if primary has recovered
```

---

### ConsensusNotReachedError

Exception raised when consensus cannot be reached.

```python
class ConsensusNotReachedError(Exception):
    '''Raised when consensus cannot be reached under the specified mode.'''
    pass

# Alias for backwards compatibility
ConsensusNotReached = ConsensusNotReachedError
```

---

## CLI Commands

Commands available via `pyproject.toml` scripts.

| Command | Module | Description |
|---------|--------|-------------|
| `mcp-exec` | `runtime.harness:main` | Execute MCP-enabled scripts |
| `mcp-generate` | `runtime.generate_wrappers:main` | Generate Python wrappers from MCP config |
| `mcp-generate-discovery` | `runtime.generate_test_params:main` | Generate test parameters for tools |
| `mcp-discover` | `runtime.discover_schemas:main` | Discover API schemas from actual responses |

**Usage:**
```bash
# Execute a script
uv run python -m runtime.harness scripts/my_script.py

# Generate wrappers
uv run mcp-generate

# Discover schemas
uv run mcp-discover
```

---

## Environment Variables

Environment variables set by patterns for hook detection:

| Variable | Set By | Description |
|----------|--------|-------------|
| `PATTERN_TYPE` | All patterns | Pattern type identifier |
| `PATTERN_ID` | All patterns | Unique pattern execution ID |
| `AGENT_ROLE` | All patterns | Role of the current agent |
| `SWARM_ID` | Swarm | Swarm execution ID |
| `HIERARCHY_ID` | Hierarchical | Hierarchy execution ID |
| `HIERARCHY_LEVEL` | Hierarchical | 0 = coordinator, 1+ = specialist |
| `COORDINATOR_ID` | Hierarchical | ID of coordinator (for specialists) |
| `JURY_ID` | Jury | Jury execution ID |
| `JUROR_INDEX` | Jury | 0-indexed juror number |
| `TOTAL_JURORS` | Jury | Total number of jurors |
| `PIPELINE_ID` | Pipeline | Pipeline execution ID |
| `PIPELINE_STAGE_INDEX` | Pipeline | 0-indexed stage number |
| `PIPELINE_TOTAL_STAGES` | Pipeline | Total number of stages |
| `GC_ID` | GeneratorCritic | Generator/Critic execution ID |
| `GC_ITERATION` | GeneratorCritic | Current iteration number |
| `GC_MAX_ROUNDS` | GeneratorCritic | Maximum iterations |
| `CB_ID` | CircuitBreaker | Circuit breaker execution ID |
| `CIRCUIT_STATE` | CircuitBreaker | Current circuit state |
| `MR_ID` | MapReduce | MapReduce execution ID |
| `MAPPER_INDEX` | MapReduce | Mapper index (for mappers) |
| `TOTAL_MAPPERS` | MapReduce | Total number of mappers |
| `COR_ID` | ChainOfResponsibility | Chain execution ID |
| `HANDLER_PRIORITY` | ChainOfResponsibility | Handler priority value |
| `CHAIN_LENGTH` | ChainOfResponsibility | Total handlers in chain |
| `ADV_ID` | Adversarial | Adversarial execution ID |
| `ADVERSARIAL_ROUND` | Adversarial | Current debate round |
| `ADVERSARIAL_MAX_ROUNDS` | Adversarial | Maximum debate rounds |
| `EVENT_BUS_ID` | EventDriven | Event bus ID |
| `SUBSCRIBER_EVENT_TYPES` | EventDriven | JSON list of subscribed event types |
| `BLACKBOARD_ID` | Blackboard | Blackboard execution ID |
| `BLACKBOARD_WRITES_TO` | Blackboard | Comma-separated keys specialist writes |
| `BLACKBOARD_READS_FROM` | Blackboard | Comma-separated keys specialist reads |
