#!/usr/bin/env python3
"""Build remaining 6 Agentica patterns using DependencySwarm.

USAGE:
    S_M_BASE_URL=http://localhost:2345 uv run python scripts/agentica/build_remaining_patterns.py

This dogfoods the DependencySwarm pattern to build the remaining patterns:
- Circuit Breaker
- Map/Reduce
- Adversarial
- Chain of Responsibility
- Blackboard
- Event-Driven

Requires:
- Claude Proxy running on :8080
- Agentica Server running on :2345
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.dependency_swarm import DependencySwarm


# =============================================================================
# Pattern Prompts
# =============================================================================

CIRCUIT_BREAKER_PROMPT = """
Build the Circuit Breaker pattern in scripts/agentica/patterns.py.

## What to Build

A pattern that wraps agent execution with failure detection. After N consecutive
failures, the circuit "opens" and routes to a fallback agent. After a timeout,
the circuit enters "half-open" state and tests the primary agent again.

## Structure (follow existing patterns)

1. Read scripts/agentica/patterns.py to understand the class structure
2. Add CircuitBreaker class after GeneratorCritic (around line 750)
3. Include:
   - __init__ with: primary_agent, fallback_agent, max_failures=3, reset_timeout=60
   - States: CLOSED (normal), OPEN (using fallback), HALF_OPEN (testing)
   - execute() method that routes based on state
   - Integration with CoordinationDB for tracking

## Example Usage (include in docstring)

```python
cb = CircuitBreaker(
    primary_premise="You implement features.",
    fallback_premise="You implement simpler versions.",
    max_failures=3,
    reset_timeout=60
)
result = await cb.execute("Implement OAuth flow")
```

## Tests

Create tests/unit/test_agentica_circuit_breaker.py with:
1. Test circuit stays closed on success
2. Test circuit opens after max_failures
3. Test fallback is called when open
4. Test circuit resets after timeout

Run tests: uv run pytest tests/unit/test_agentica_circuit_breaker.py -v

Return a summary of what was implemented and test results.
"""

MAP_REDUCE_PROMPT = """
Build the Map/Reduce pattern in scripts/agentica/patterns.py.

## What to Build

A pattern that fans out work to N agents (map phase), then combines results
with a reducer agent (reduce phase). Good for parallel processing of independent
subtasks.

## Structure (follow existing patterns)

1. Read scripts/agentica/patterns.py to understand the class structure
2. Add MapReduce class after CircuitBreaker
3. Include:
   - __init__ with: mapper_premise, reducer_premise, num_mappers=3
   - map() phase: spawn N mappers, execute in parallel
   - reduce() phase: spawn reducer, pass all mapper outputs
   - Integration with CoordinationDB for tracking

## Example Usage (include in docstring)

```python
mr = MapReduce(
    mapper_premise="You analyze one section of code.",
    reducer_premise="You synthesize analysis from multiple reviewers.",
    num_mappers=4
)
result = await mr.execute("Review this codebase", chunks=["file1.py", "file2.py", "file3.py", "file4.py"])
```

## Dependency

This pattern depends on Circuit Breaker being implemented first (for fault tolerance).
You can reference it but don't need to integrate it yet.

## Tests

Create tests/unit/test_agentica_map_reduce.py with:
1. Test map phase distributes work correctly
2. Test reduce phase receives all mapper outputs
3. Test handles mapper failures gracefully
4. Test with different numbers of mappers

Run tests: uv run pytest tests/unit/test_agentica_map_reduce.py -v

Return a summary of what was implemented and test results.
"""

ADVERSARIAL_PROMPT = """
Build the Adversarial pattern in scripts/agentica/patterns.py.

## What to Build

A pattern where agents intentionally take opposing positions to stress-test
an idea or solution. One agent advocates, another attacks, and an optional
judge decides.

## Structure (follow existing patterns)

1. Read scripts/agentica/patterns.py to understand the class structure
2. Add Adversarial class after MapReduce
3. Include:
   - __init__ with: advocate_premise, adversary_premise, judge_premise (optional)
   - debate() method: advocate presents, adversary critiques, iterate
   - resolve() method: judge decides (or return both positions if no judge)
   - max_rounds parameter for debate length
   - Integration with CoordinationDB for tracking

## Example Usage (include in docstring)

```python
adv = Adversarial(
    advocate_premise="You argue in favor of this architectural decision.",
    adversary_premise="You find flaws in architectural decisions.",
    judge_premise="You decide which position is stronger.",
    max_rounds=3
)
result = await adv.debate("Should we use microservices or monolith?")
```

## Tests

Create tests/unit/test_agentica_adversarial.py with:
1. Test advocate and adversary both get called
2. Test multiple rounds of debate
3. Test judge receives both positions
4. Test works without judge (returns both positions)

Run tests: uv run pytest tests/unit/test_agentica_adversarial.py -v

Return a summary of what was implemented and test results.
"""

CHAIN_OF_RESPONSIBILITY_PROMPT = """
Build the Chain of Responsibility pattern in scripts/agentica/patterns.py.

## What to Build

A pattern where a request passes through a chain of handlers. Each handler
either processes the request (and returns) or passes it to the next handler.
Good for routing to specialized agents.

## Structure (follow existing patterns)

1. Read scripts/agentica/patterns.py to understand the class structure
2. Add ChainOfResponsibility class after Adversarial
3. Include:
   - Handler dataclass: premise, can_handle callable, priority
   - __init__ with: list of handlers (sorted by priority)
   - process() method: try each handler until one can_handle returns True
   - Fallback if no handler can handle
   - Integration with CoordinationDB for tracking

## Example Usage (include in docstring)

```python
chain = ChainOfResponsibility(handlers=[
    Handler(premise="You handle Python questions.", can_handle=lambda q: "python" in q.lower()),
    Handler(premise="You handle JavaScript questions.", can_handle=lambda q: "javascript" in q.lower()),
    Handler(premise="You handle general programming questions.", can_handle=lambda q: True),  # fallback
])
result = await chain.process("How do I use async in Python?")
```

## Tests

Create tests/unit/test_agentica_chain_of_responsibility.py with:
1. Test first matching handler is used
2. Test falls through to next handler if can_handle returns False
3. Test fallback handler catches all
4. Test handler priority ordering

Run tests: uv run pytest tests/unit/test_agentica_chain_of_responsibility.py -v

Return a summary of what was implemented and test results.
"""

BLACKBOARD_PROMPT = """
Build the Blackboard pattern in scripts/agentica/patterns.py.

## What to Build

A pattern where multiple specialist agents contribute to a shared "blackboard"
(state). Each agent reads the blackboard, adds their contribution, and updates
it. A controller decides when the solution is complete.

## Structure (follow existing patterns)

1. Read scripts/agentica/patterns.py to understand the class structure
2. Add Blackboard class after ChainOfResponsibility
3. Include:
   - Blackboard dataclass: dict-like state with history
   - Specialist: premise, writes_to (list of keys), reads_from (list of keys)
   - Controller: checks completion condition
   - __init__ with: specialists, controller_premise, max_iterations
   - solve() method: iterate until controller says done or max_iterations
   - Integration with CoordinationDB for tracking

## Example Usage (include in docstring)

```python
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

## Tests

Create tests/unit/test_agentica_blackboard.py with:
1. Test specialists can read/write to blackboard
2. Test iteration continues until controller approves
3. Test max_iterations stops infinite loops
4. Test state history is preserved

Run tests: uv run pytest tests/unit/test_agentica_blackboard.py -v

Return a summary of what was implemented and test results.
"""

EVENT_DRIVEN_PROMPT = """
Build the Event-Driven pattern in scripts/agentica/patterns.py.

## What to Build

A pattern where agents react to events. Events are published to a bus, and
subscriber agents are notified. Good for loose coupling between agents.

## Structure (follow existing patterns)

1. Read scripts/agentica/patterns.py to understand the class structure
2. Add EventDriven class after Blackboard
3. Include:
   - Event dataclass: type, payload, timestamp
   - Subscriber: premise, event_types (list of types to subscribe to)
   - EventBus: publish(), subscribe(), dispatch()
   - __init__ with: list of subscribers
   - publish() method: sends event to all matching subscribers
   - Async dispatch: subscribers can run concurrently
   - Integration with CoordinationDB for tracking

## Example Usage (include in docstring)

```python
bus = EventDriven(subscribers=[
    Subscriber(premise="You handle user created events.", event_types=["user.created"]),
    Subscriber(premise="You handle order placed events.", event_types=["order.placed"]),
    Subscriber(premise="You log all events.", event_types=["*"]),  # wildcard
])
await bus.publish(Event(type="user.created", payload={"user_id": "123"}))
```

## Tests

Create tests/unit/test_agentica_event_driven.py with:
1. Test subscribers receive matching events
2. Test wildcard subscriber receives all events
3. Test non-matching subscribers don't receive events
4. Test concurrent dispatch to multiple subscribers

Run tests: uv run pytest tests/unit/test_agentica_event_driven.py -v

Return a summary of what was implemented and test results.
"""


async def main():
    """Build all 6 remaining patterns using DependencySwarm."""
    print("=" * 60)
    print("Building 6 Remaining Patterns via DependencySwarm")
    print("=" * 60)
    print()

    # Initialize coordination database
    db = CoordinationDB(session_id="build-patterns")

    # Create DependencySwarm with implementation bundle
    swarm = DependencySwarm(
        db=db,
        model="anthropic:claude-sonnet-4",
        fail_fast=False,  # Continue even if one pattern fails
        max_parallel=2,   # Build 2 patterns at a time
        bundle="implementation",  # Use implementation skill bundle
        rules=["async-repl-protocol"],  # Follow REPL protocol
    )

    # Add tasks with dependencies
    # Phase 1: Circuit Breaker (no deps - foundational)
    circuit_breaker_id = swarm.add_task(
        name="circuit_breaker",
        premise=CIRCUIT_BREAKER_PROMPT,
    )

    # Phase 2: Map/Reduce (depends on Circuit Breaker for fault tolerance concepts)
    map_reduce_id = swarm.add_task(
        name="map_reduce",
        premise=MAP_REDUCE_PROMPT,
        depends_on=[circuit_breaker_id],
    )

    # Phase 2: Adversarial (independent, can run parallel with Map/Reduce)
    adversarial_id = swarm.add_task(
        name="adversarial",
        premise=ADVERSARIAL_PROMPT,
        depends_on=[circuit_breaker_id],  # Waits for phase 1
    )

    # Phase 3: Chain of Responsibility (depends on phase 2)
    chain_id = swarm.add_task(
        name="chain_of_responsibility",
        premise=CHAIN_OF_RESPONSIBILITY_PROMPT,
        depends_on=[map_reduce_id, adversarial_id],
    )

    # Phase 3: Blackboard (can run parallel with Chain of Responsibility)
    blackboard_id = swarm.add_task(
        name="blackboard",
        premise=BLACKBOARD_PROMPT,
        depends_on=[map_reduce_id, adversarial_id],
    )

    # Phase 4: Event-Driven (final, depends on all others)
    event_driven_id = swarm.add_task(
        name="event_driven",
        premise=EVENT_DRIVEN_PROMPT,
        depends_on=[chain_id, blackboard_id],
    )

    print("Task graph created:")
    print(f"  Phase 1: circuit_breaker ({circuit_breaker_id[:8]})")
    print(f"  Phase 2: map_reduce ({map_reduce_id[:8]}), adversarial ({adversarial_id[:8]})")
    print(f"  Phase 3: chain_of_responsibility ({chain_id[:8]}), blackboard ({blackboard_id[:8]})")
    print(f"  Phase 4: event_driven ({event_driven_id[:8]})")
    print()
    print("Executing DependencySwarm...")
    print("(Monitor with: uv run python scripts/agentica/watch_agents.py --watch --monitor)")
    print()

    # Execute the swarm
    try:
        results = await swarm.execute()

        print()
        print("=" * 60)
        print("BUILD RESULTS")
        print("=" * 60)

        for name, result in results.items():
            print(f"\n[{name}]")
            print("-" * 40)
            # Truncate long results
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            print(result_str)

        # Summary
        print()
        print("=" * 60)
        completed = len(results)
        total = 6
        print(f"Completed: {completed}/{total} patterns")

        if completed == total:
            print("All patterns built successfully!")
        else:
            # Check which failed
            failed = []
            for node in swarm.graph.nodes.values():
                if node.status == "failed":
                    failed.append(f"{node.name}: {node.error}")
            if failed:
                print("Failed patterns:")
                for f in failed:
                    print(f"  - {f}")

        return results

    except Exception as e:
        print(f"Error during execution: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
