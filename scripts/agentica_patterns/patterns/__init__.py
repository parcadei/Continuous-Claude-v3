'''Multi-Agent Patterns for Agentica.

Re-exports all patterns for convenience.
'''

# Pattern classes
from scripts.agentica_patterns.patterns.adversarial import Adversarial
from scripts.agentica_patterns.patterns.blackboard import (
    Blackboard,
    BlackboardResult,
    BlackboardState,
    Specialist,
)
from scripts.agentica_patterns.patterns.chain_of_responsibility import ChainOfResponsibility, Handler
from scripts.agentica_patterns.patterns.circuit_breaker import CircuitBreaker, CircuitState
from scripts.agentica_patterns.patterns.event_driven import Event, EventDriven, Subscriber
from scripts.agentica_patterns.patterns.generator_critic import GeneratorCritic
from scripts.agentica_patterns.patterns.hierarchical import Hierarchical
from scripts.agentica_patterns.patterns.jury import Jury
from scripts.agentica_patterns.patterns.map_reduce import MapReduce
from scripts.agentica_patterns.patterns.pipeline import Pipeline
from scripts.agentica_patterns.patterns.primitives import (
    AggregateMode,
    Aggregator,
    Consensus,
    ConsensusMode,
    ConsensusNotReachedError,
    HandoffState,
    gather_fail_fast,
)

# Patterns
from scripts.agentica_patterns.patterns.swarm import Swarm

__all__ = [
    "AggregateMode",
    "Aggregator",
    "Consensus",
    "ConsensusMode",
    "ConsensusNotReachedError",
    "HandoffState",
    "gather_fail_fast",
    # Pattern classes
    "Swarm",
    "Pipeline",
    "Hierarchical",
    "CircuitBreaker",
    "CircuitState",
    "Jury",
    "GeneratorCritic",
    "MapReduce",
    "ChainOfResponsibility",
    "Handler",
    "Adversarial",
    "EventDriven",
    "Event",
    "Subscriber",
    "Blackboard",
    "BlackboardResult",
    "BlackboardState",
    "Specialist",
]
