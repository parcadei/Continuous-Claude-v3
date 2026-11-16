# Multi-Agent Patterns Reference

**Location:** `scripts/agentica/patterns.py`

Comprehensive guide to the 11 core multi-agent coordination patterns implemented in Agentica. Each pattern encapsulates a different coordination strategy optimized for specific task characteristics.

## Pattern Selection Guide

| Task Characteristics | Recommended Pattern | Rationale |
|---------------------|---------------------|-----------|
| Research, exploration, "investigate" | **Swarm** | Parallel perspectives, diverse angles |
| Implementation, "build", "create" | **Hierarchical** | Decomposition, accountability chain |
| Review, critique, "feedback" | **Generator/Critic** | Iterative refinement loop |
| Validation, "is correct", high-stakes | **Jury** | Independent voting, consensus |
| Linear workflow, clear steps | **Pipeline** | Sequential handoff, transformations |
| Parallel independent work | **Map/Reduce** | Fan out, aggregate results |
| Collaborative problem-solving | **Blackboard** | Shared state, emergent solutions |
| Resilience, fallback needed | **Circuit Breaker** | Graceful degradation |
| Opposing viewpoints, stress-test | **Adversarial** | Red team vs Blue team |
| Capability matching, tiering | **Chain of Responsibility** | Escalation, cost optimization |
| Monitoring, reactive systems | **Event-Driven** | Subscribe/react, loose coupling |

## Selection Heuristics

### Static Rules (Current)
Claude selects patterns based on:
1. **Task keywords:** "research" → Swarm, "implement" → Hierarchical
2. **Complexity assessment:** Unknown → Hierarchical (adapt as needed)
3. **Risk level:** High-stakes → Jury
4. **Parallelizability:** Independent subtasks → Swarm/Map-Reduce

### Memory-Based Selection (Future)
Patterns can be selected dynamically based on:
- Historical success rates per pattern/task type
- Cost/time tradeoffs learned from past executions
- User preferences stored in session memory

---

## Patterns

### 1. Swarm

**When to use:** Research, exploration, "investigate", need diverse perspectives

**How it works:** Spawn multiple agents with different perspectives in parallel. Each agent attacks the problem from a different angle. Results are aggregated using the Aggregator primitive.

**Example use case:** Security audit from multiple angles (security expert, performance expert, UX expert)

**Code snippet:**
```python
from scripts.agentica.patterns import Swarm
from scripts.agentica.primitives import AggregateMode

swarm = Swarm(
    perspectives=[
        "You are a security expert.",
        "You are a performance expert.",
        "You are a UX expert."
    ],
    aggregate_mode=AggregateMode.MERGE,
    model="anthropic:claude-sonnet-4.5"
)

result = await swarm.execute("Analyze OAuth implementation")
# Returns: Merged analysis from all perspectives
```

**Parameters:**
- `perspectives`: List of agent premises (one per agent)
- `aggregate_mode`: MERGE (dict), CONCAT (str), or BEST (dict)
- `fail_fast`: Stop on first error (default: False)
- `model`, `scope`, `mcp`: Agent configuration
- `db`: Optional CoordinationDB for tracking

---

### 2. Pipeline

**When to use:** Clear linear workflow, each step transforms output, sequential stages

**How it works:** Sequential stage execution with HandoffState. Each stage receives the output of the previous stage and passes its result to the next: A → B → C.

**Example use case:** Data processing pipeline (fetch → transform → analyze → report)

**Code snippet:**
```python
from scripts.agentica.patterns import Pipeline
from scripts.agentica.primitives import HandoffState

async def fetch(state: HandoffState) -> HandoffState:
    state.add_artifact("data", await fetch_data())
    return state

async def transform(state: HandoffState) -> HandoffState:
    data = state.artifacts["data"]
    state.add_artifact("transformed", transform(data))
    return state

async def analyze(state: HandoffState) -> HandoffState:
    data = state.artifacts["transformed"]
    state.add_artifact("analysis", analyze(data))
    return state

pipeline = Pipeline(stages=[fetch, transform, analyze])
result = await pipeline.run(HandoffState(context="Process user data"))
# Returns: Final HandoffState with all artifacts
```

**Parameters:**
- `stages`: List of async functions that take and return HandoffState

---

### 3. Hierarchical

**When to use:** Implementation, "build", "create", complex tasks with clear decomposition

**How it works:** Coordinator decomposes task into subtasks → Specialists execute subtasks in parallel → Results aggregated → Coordinator synthesizes final answer

**Example use case:** Building a feature (coordinator breaks into backend/frontend/tests, specialists implement each)

**Code snippet:**
```python
from scripts.agentica.patterns import Hierarchical
from scripts.agentica.primitives import AggregateMode

hierarchical = Hierarchical(
    coordinator_premise="You break tasks into subtasks and synthesize results.",
    specialist_premises={
        "researcher": "You research topics thoroughly.",
        "analyst": "You analyze data and identify patterns.",
        "writer": "You synthesize findings into reports."
    },
    aggregation_mode=AggregateMode.CONCAT,
    coordinator_model="anthropic:claude-opus-4.5",
    specialist_model="anthropic:claude-sonnet-4.5"
)

result = await hierarchical.execute("Research and analyze microservices best practices")
# Returns: Synthesized final answer from coordinator
```

**Parameters:**
- `coordinator_premise`, `specialist_premises`: Role definitions
- `coordinator_scope`, `specialist_scope`: Tools for each
- `coordinator_model`, `specialist_model`: Model selection
- `aggregation_mode`: How to combine specialist results
- `fail_fast`: Stop on first specialist failure (default: False)
- `return_type`: Expected final result type (default: str)

---

### 4. Jury

**When to use:** Validation, "is correct", high-stakes decisions, reducing hallucination

**How it works:** N independent agents evaluate independently and vote. Consensus mechanism determines final verdict (majority, unanimous, threshold).

**Example use case:** Code safety review (5 jurors independently evaluate, majority decides)

**Code snippet:**
```python
from scripts.agentica.patterns import Jury
from scripts.agentica.primitives import ConsensusMode

jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.MAJORITY,
    premise="You are an expert code reviewer. Evaluate for security, correctness, and best practices.",
    model="anthropic:claude-sonnet-4.5"
)

verdict = await jury.decide(bool, "Is this code safe to deploy?")
# Returns: True/False based on majority vote
```

**Parameters:**
- `num_jurors`: Number of jurors to spawn
- `consensus_mode`: MAJORITY, UNANIMOUS, or THRESHOLD
- `threshold`: Required agreement (0-1) for THRESHOLD mode
- `weights`: Optional per-juror weights
- `premise`: Single premise for all jurors
- `premises`: Different premise per juror (mutually exclusive with `premise`)
- `allow_partial`: Continue with partial votes if some fail
- `min_jurors`: Minimum successful votes required
- `debug`: Track individual votes for debugging

---

### 5. GeneratorCritic

**When to use:** Review, critique, "feedback", iterative refinement

**How it works:** Generator creates initial solution → Critic evaluates and provides feedback → Generator refines → Loop until approved or max_rounds reached

**Example use case:** Code generation with review (generate function → critic reviews → refine → repeat)

**Code snippet:**
```python
from scripts.agentica.patterns import GeneratorCritic

gc = GeneratorCritic(
    generator_premise="You generate Python code that is clean, efficient, and well-documented.",
    critic_premise="You review Python code for correctness, style, and best practices.",
    max_rounds=3,
    generator_model="anthropic:claude-sonnet-4.5",
    critic_model="anthropic:claude-opus-4.5"
)

result = await gc.run("Create a function to parse JSON safely")
# Returns: HandoffState with approved solution
```

**Parameters:**
- `generator_premise`, `critic_premise`: Role definitions
- `max_rounds`: Maximum iteration rounds (default: 3)
- `generator_scope`, `critic_scope`: Tools for each
- `generator_model`, `critic_model`: Model selection
- `is_approved`: Custom function to check if state is approved

---

### 6. CircuitBreaker

**When to use:** Resilient pipelines, fallback needed, graceful degradation

**How it works:** Wraps agent execution with failure detection. After N consecutive failures, circuit "opens" and routes to fallback. After timeout, enters "half-open" to test primary recovery.

**States:**
- **CLOSED:** Normal operation (primary agent)
- **OPEN:** Too many failures (fallback agent)
- **HALF_OPEN:** Testing primary after timeout

**Example use case:** API integration with fallback (try primary API → on failure, use cached data)

**Code snippet:**
```python
from scripts.agentica.patterns import CircuitBreaker

cb = CircuitBreaker(
    primary_premise="You implement features using the latest API.",
    fallback_premise="You implement simpler versions using cached data.",
    max_failures=3,
    reset_timeout=60,  # seconds
    return_type=str
)

result = await cb.execute("Implement OAuth flow")
# Returns: Result from primary or fallback based on circuit state
```

**Parameters:**
- `primary_premise`, `fallback_premise`: Agent roles
- `max_failures`: Consecutive failures before opening circuit (default: 3)
- `reset_timeout`: Seconds before trying primary again (default: 60)
- `primary_model`, `fallback_model`: Model selection
- `primary_scope`, `fallback_scope`: Tools for each
- `return_type`: Expected return type (default: str)

---

### 7. Adversarial

**When to use:** Opposing viewpoints, stress-test ideas, security review, finding edge cases

**How it works:** Advocate argues in favor → Adversary attacks/critiques → Iterate for max_rounds → Optional judge decides winner

**Example use case:** Architectural decision review (advocate defends microservices, adversary attacks, judge decides)

**Code snippet:**
```python
from scripts.agentica.patterns import Adversarial

adv = Adversarial(
    advocate_premise="You argue in favor of architectural decisions with strong reasoning.",
    adversary_premise="You find flaws and weaknesses in architectural decisions.",
    judge_premise="You evaluate both positions and decide which is stronger.",
    max_rounds=3
)

result = await adv.resolve("Should we use microservices or monolith?")
# Returns: Dict with advocate_final, adversary_final, verdict, history
```

**Parameters:**
- `advocate_premise`, `adversary_premise`: Debater roles
- `judge_premise`: Optional judge role (if None, returns both positions)
- `max_rounds`: Maximum debate rounds (default: 3)
- `advocate_model`, `adversary_model`, `judge_model`: Model selection
- `advocate_scope`, `adversary_scope`, `judge_scope`: Tools for each

**Methods:**
- `debate(question)`: Run debate, return both final positions
- `resolve(question)`: Run debate + judge verdict

---

### 8. ChainOfResponsibility

**When to use:** Capability matching, tiered support, escalation, cost optimization

**How it works:** Pass request through chain until one handler can handle it. First handler (by priority) where `can_handle` returns True processes the request.

**Example use case:** Support routing (simple bot → junior agent → senior agent → escalate)

**Code snippet:**
```python
from scripts.agentica.patterns import ChainOfResponsibility, Handler

chain = ChainOfResponsibility(
    handlers=[
        Handler(
            premise="You handle Python questions.",
            can_handle=lambda q: "python" in q.lower(),
            priority=1
        ),
        Handler(
            premise="You handle JavaScript questions.",
            can_handle=lambda q: "javascript" in q.lower(),
            priority=1
        ),
        Handler(
            premise="You handle general programming questions.",
            can_handle=lambda q: True,  # fallback
            priority=2
        )
    ],
    model="anthropic:claude-sonnet-4.5"
)

result = await chain.process("How do I use async in Python?")
# Returns: Result from Python handler
```

**Parameters:**
- `handlers`: List of Handler objects (sorted by priority)
- `model`, `scope`: Agent configuration
- `return_type`: Expected return type (default: str)

**Handler fields:**
- `premise`: Agent role
- `can_handle`: Callable that returns True if handler can process
- `priority`: Lower number = higher priority (default: 0)

---

### 9. MapReduce

**When to use:** Parallel independent work, batch processing, distributable analysis

**How it works:** Distribute independent subtasks across mapper agents in parallel → Reducer aggregates all results → Synthesize final answer

**Example use case:** Codebase review (split by files, map to reviewers, reduce to summary)

**Code snippet:**
```python
from scripts.agentica.patterns import MapReduce

mr = MapReduce(
    mapper_premise="You analyze one section of code for bugs and improvements.",
    reducer_premise="You synthesize analysis from multiple reviewers into a final report.",
    num_mappers=4,
    mapper_model="anthropic:claude-sonnet-4.5",
    reducer_model="anthropic:claude-opus-4.5"
)

result = await mr.execute(
    "Review this codebase",
    chunks=["file1.py", "file2.py", "file3.py", "file4.py"]
)
# Returns: Synthesized final report
```

**Parameters:**
- `mapper_premise`, `reducer_premise`: Role definitions
- `num_mappers`: Number of mapper agents (default: 3)
- `mapper_model`, `reducer_model`: Model selection
- `mapper_scope`, `reducer_scope`: Tools for each
- `fail_fast`: Stop on first mapper error (default: True)
- `return_type`: Expected final result type (default: str)

---

### 10. Blackboard

**When to use:** Collaborative problem-solving, emergent solutions, shared state

**How it works:** Multiple specialists contribute to shared state (blackboard). Controller monitors state and decides when solution is complete. Specialists read relevant keys, process, and write contributions.

**Example use case:** System design (requirements analyst → architect → implementation planner, all contributing to shared design)

**Code snippet:**
```python
from scripts.agentica.patterns import Blackboard, Specialist

bb = Blackboard(
    specialists=[
        Specialist(
            premise="You analyze requirements.",
            writes_to=["requirements"]
        ),
        Specialist(
            premise="You design architecture based on requirements.",
            writes_to=["architecture"],
            reads_from=["requirements"]
        ),
        Specialist(
            premise="You create implementation plan based on architecture.",
            writes_to=["plan"],
            reads_from=["architecture"]
        )
    ],
    controller_premise="You check if the design is complete and coherent.",
    max_iterations=5
)

result = await bb.solve("Build a user authentication system")
# Returns: BlackboardResult with state, iterations, completed flag
```

**Parameters:**
- `specialists`: List of Specialist objects
- `controller_premise`: Controller role
- `max_iterations`: Maximum iterations before stopping (default: 5)
- `controller_model`, `specialist_model`: Model selection
- `controller_scope`, `specialist_scope`: Tools for each

**Specialist fields:**
- `premise`: Agent role
- `writes_to`: List of blackboard keys to write
- `reads_from`: List of blackboard keys to read

**BlackboardResult:**
- `state`: Final BlackboardState
- `iterations`: Number of iterations run
- `completed`: True if controller approved, False if max iterations reached

---

### 11. EventDriven

**When to use:** Monitoring, reactive systems, async workflows, loose coupling

**How it works:** Events are published to a bus. Subscriber agents are notified based on subscribed event types. Subscribers can use wildcard "*" to receive all events.

**Example use case:** Monitoring system (log agent subscribes to all events, alert agent subscribes to errors)

**Code snippet:**
```python
from scripts.agentica.patterns import EventDriven, Event, Subscriber

bus = EventDriven(
    subscribers=[
        Subscriber(
            premise="You handle user created events by sending welcome emails.",
            event_types=["user.created"]
        ),
        Subscriber(
            premise="You handle order placed events by triggering fulfillment.",
            event_types=["order.placed"]
        ),
        Subscriber(
            premise="You log all events for audit trail.",
            event_types=["*"]  # wildcard
        )
    ],
    model="anthropic:claude-sonnet-4.5"
)

results = await bus.publish(Event(
    type="user.created",
    payload={"user_id": "123", "email": "user@example.com"}
))
# Returns: List of results from all matching subscribers
```

**Parameters:**
- `subscribers`: List of Subscriber objects
- `model`, `scope`: Agent configuration
- `return_type`: Expected return type from handlers (default: str)

**Subscriber fields:**
- `premise`: Agent role
- `event_types`: List of event types to subscribe to (use "*" for all)

**Event fields:**
- `type`: Event type string (e.g., "user.created")
- `payload`: Event data as dict
- `timestamp`: When event was created (auto-generated)

---

## Hybrid Patterns

Patterns can compose to create more sophisticated coordination strategies:

### Hierarchical + Swarm
```python
# Coordinator spawns swarms for research phases
hierarchical = Hierarchical(
    coordinator_premise="You coordinate research and implementation.",
    specialist_premises={
        "research_lead": "You spawn swarms to research from multiple angles."
    }
)

# Inside research_lead agent:
swarm = Swarm(perspectives=["security", "performance", "scalability"])
research_results = await swarm.execute("Analyze microservices")
```

### Generator/Critic + Jury
```python
# Multiple critics vote on generator output
gc = GeneratorCritic(
    generator_premise="You generate solutions.",
    critic_premise="You evaluate solutions."
)

# After generation, jury votes
jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)
approved = await jury.decide(bool, "Is this solution acceptable?")
```

### Pipeline + Circuit Breaker
```python
# Pipeline with fallback agents on step failure
async def stage_a(state: HandoffState) -> HandoffState:
    cb = CircuitBreaker(
        primary_premise="Use latest API",
        fallback_premise="Use cached data"
    )
    result = await cb.execute(state.context)
    state.add_artifact("a_result", result)
    return state

pipeline = Pipeline(stages=[stage_a, stage_b, stage_c])
```

---

## Meta-Pattern: Claude IS the Router

**Key insight:** Don't build a separate router agent. Claude (the main conversation) selects patterns based on:

1. **Task keywords:** Detects trigger words in user request
   - "research", "investigate" → Swarm
   - "implement", "build" → Hierarchical
   - "review", "critique" → Generator/Critic
   - "validate", "is correct" → Jury

2. **Complexity assessment:** Analyzes task structure
   - Unknown complexity → Start Hierarchical (adapt as needed)
   - Clear decomposition → Hierarchical
   - Linear workflow → Pipeline

3. **Risk level:** Evaluates stakes
   - High-stakes decision → Jury
   - Production deployment → Adversarial (stress-test)
   - Experimental feature → Generator/Critic

4. **Parallelizability:** Identifies independence
   - Independent subtasks → Swarm or Map/Reduce
   - Sequential dependencies → Pipeline

**Benefit:** No additional LLM call for routing. Claude's understanding of the user's intent directly informs pattern selection.

---

## Pattern Composition Rules

### When to Compose
1. **Nested decomposition:** Hierarchical spawns Swarms for research
2. **Quality gates:** Pipeline stages use Generator/Critic for refinement
3. **Fallback strategies:** Circuit Breaker wraps any pattern
4. **Consensus on output:** Any pattern + Jury for validation

### How to Compose
- **Sequential:** Pattern A output feeds Pattern B input
- **Nested:** Pattern A spawns Pattern B internally
- **Wrapper:** Pattern A wraps Pattern B (e.g., Circuit Breaker)
- **Parallel:** Multiple patterns run concurrently, results merged

---

## CoordinationDB Integration

All patterns support optional `db` parameter for tracking:

```python
from scripts.agentica.coordination import CoordinationDB

db = CoordinationDB("coordination.db")

swarm = Swarm(
    perspectives=["security", "performance"],
    db=db  # Enables agent tracking
)

# Query agents later
agents = db.query_agents(pattern="swarm")
```

**Tracked data:**
- Agent spawns (pattern, premise, model)
- Execution times
- Parent-child relationships
- Task assignments

---

## Performance Considerations

### Token Usage
- **Swarm/Map-Reduce:** N parallel agents = N * tokens
- **Hierarchical:** Coordinator + specialists = (1 + N) * tokens
- **Generator/Critic:** Iterative, tokens accumulate per round

### Latency
- **Parallel patterns (Swarm, Map-Reduce):** Latency = max(agent times)
- **Sequential patterns (Pipeline):** Latency = sum(stage times)
- **Iterative patterns (Generator/Critic):** Latency = rounds * avg(agent time)

### Cost Optimization
- Use cheaper models for mappers/specialists: `specialist_model="anthropic:claude-haiku-4.5"`
- Use expensive models for coordinators/reducers: `coordinator_model="anthropic:claude-opus-4.5"`
- Set `fail_fast=False` for graceful degradation instead of full failure

---

## Common Pitfalls

1. **Over-parallelization:** Too many agents causes coordination overhead
   - Swarm: 3-5 perspectives optimal
   - Map-Reduce: Match num_mappers to chunk count (avoid empty mappers)

2. **Infinite loops:** Generator/Critic or Adversarial without termination
   - Always set `max_rounds` appropriately
   - Implement clear `is_approved` logic

3. **State pollution:** Blackboard specialists writing to wrong keys
   - Explicitly define `reads_from` and `writes_to`
   - Controller validates state coherence

4. **Missing fallbacks:** Circuit Breaker without proper fallback agent
   - Ensure fallback can actually complete the task (simpler version)

---

## Future: Memory-Based Pattern Selection

Current selection is static (rule-based). Future enhancement:

```python
# Store pattern success in memory
memory.store_pattern_outcome(
    pattern="swarm",
    task_type="research",
    success=True,
    cost_tokens=15000,
    latency_seconds=8.3
)

# Query best pattern for task type
best_pattern = memory.query_best_pattern(
    task_type="research",
    optimize_for="latency"  # or "cost" or "success_rate"
)
```

**Benefits:**
- Learn from historical performance
- Adapt to user preferences
- Optimize cost/latency tradeoffs dynamically

---

## References

- **Implementation:** `scripts/agentica/patterns.py`
- **Primitives:** `scripts/agentica/primitives.py` (Aggregator, Consensus, HandoffState)
- **Coordination DB:** `scripts/agentica/coordination.py`
- **Tracked Agents:** `scripts/agentica/tracked_agent.py`
- **Tests:** `tests/unit/test_agentica_*.py`
