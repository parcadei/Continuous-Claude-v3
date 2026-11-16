# Runtime Architecture Deep Dive

This document provides a comprehensive view of the Agentica runtime architecture, covering the full stack from Claude Code orchestration down to the 3-layer memory system.

## Full Runtime Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FULL RUNTIME ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │   Claude Code    │  <- You (CLI)                                         │
│  │   (Orchestrator) │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                  │
│           │ HTTP request: "spawn agent with scope=shared"                   │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │                    AGENTICA SERVER                            │           │
│  │                    (Python FastAPI)                           │           │
│  │                                                               │           │
│  │  - Receives spawn requests                                    │           │
│  │  - Manages agent lifecycle                                    │           │
│  │  - Routes to Claude API (Anthropic SDK)                       │           │
│  │  - Provides scope + memory to each agent                      │           │
│  └──────────────────────────┬───────────────────────────────────┘           │
│                             │                                                │
│           ┌─────────────────┼─────────────────┐                             │
│           ▼                 ▼                 ▼                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐               │
│  │   Agent 1       │ │   Agent 2       │ │   Agent 3       │               │
│  │   (Python)      │ │   (Python)      │ │   (Python)      │               │
│  │                 │ │                 │ │                 │               │
│  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │               │
│  │ │ Claude API  │ │ │ │ Claude API  │ │ │ │ Claude API  │ │               │
│  │ │ (thinking)  │ │ │ │ (thinking)  │ │ │ │ (thinking)  │ │               │
│  │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │               │
│  │                 │ │                 │ │                 │               │
│  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │               │
│  │ │   SCOPE     │ │ │ │   SCOPE     │ │ │ │   SCOPE     │ │               │
│  │ │ [isolated]  │ │ │ │ [shared]    │ │ │ │ [shared]    │ │               │
│  │ └─────────────┘ │ │ └──────┬──────┘ │ │ └──────┬──────┘ │               │
│  │                 │ │        │        │ │        │        │               │
│  │ ┌─────────────┐ │ │        └────────┼─┼────────┘        │               │
│  │ │ LOCAL MEM   │ │ │                 │ │                 │               │
│  │ │ (isolated)  │ │ │                 ▼ ▼                 │               │
│  │ └─────────────┘ │ │ ┌─────────────────────────────────┐ │               │
│  └─────────────────┘ │ │       SHARED CONTEXT            │ │               │
│                      │ │       (in-memory dict)          │ │               │
│                      │ └─────────────────────────────────┘ │               │
│                      └─────────────────┬───────────────────┘               │
│                                        │                                    │
│                                        ▼                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     3-LAYER MEMORY SYSTEM                             │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │                                                                       │  │
│  │   Layer 1: LOCAL CACHE     │ Per-agent, fast, ephemeral              │  │
│  │   (SQLite/dict)            │                                         │  │
│  │                            │                                         │  │
│  │   Layer 2: SHARED CONTEXT  │ Per-pattern, in-memory, scoped          │  │
│  │   (SharedContext obj)      │                                         │  │
│  │                            │                                         │  │
│  │   Layer 3: FEDERATED STORE │ Cross-pattern, PostgreSQL, queryable    │  │
│  │   (PostgreSQL + embeddings)│                                         │  │
│  │                            │                                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## What Each Agent Gets

When an agent is spawned via the Agentica server, it receives access to several components:

| Component | What It Provides |
|-----------|-----------------|
| **Claude API** | Thinking/reasoning capabilities via Anthropic SDK |
| **Scope** | Access permissions: `isolated`, `shared`, or `federated` |
| **Memory Layers** | Local cache, shared context, federated queries |
| **Agentic Functions** | Can call `spawn()`, `query_memory()`, `handoff()` |

### Scope Levels Explained

```
┌─────────────────────────────────────────────────────────────────┐
│                        SCOPE HIERARCHY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ISOLATED (default)                                            │
│   ├── Local cache only                                          │
│   ├── Cannot see other agents                                   │
│   └── Best for: Independent tasks, security-sensitive work      │
│                                                                 │
│   SHARED                                                        │
│   ├── Local cache + shared context                              │
│   ├── Can read/write pattern-scoped data                        │
│   └── Best for: Swarms, collaborative patterns                  │
│                                                                 │
│   FEDERATED                                                     │
│   ├── All above + cross-pattern queries                         │
│   ├── Can discover learnings from other sessions                │
│   └── Best for: Knowledge synthesis, long-term learning         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-Orchestrator Support

Multiple Claude Code instances can manage separate swarms while sharing federated memory:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-ORCHESTRATOR ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                    ┌──────────────────┐               │
│  │  Claude Code #1  │                    │  Claude Code #2  │               │
│  │  (Terminal A)    │                    │  (Terminal B)    │               │
│  └────────┬─────────┘                    └────────┬─────────┘               │
│           │                                       │                          │
│           ▼                                       ▼                          │
│  ┌────────────────────┐               ┌────────────────────┐                │
│  │  Swarm Alpha       │               │  Swarm Beta        │                │
│  │  ┌────┬────┬────┐  │               │  ┌────┬────┐       │                │
│  │  │ A1 │ A2 │ A3 │  │               │  │ B1 │ B2 │       │                │
│  │  └────┴────┴────┘  │               │  └────┴────┘       │                │
│  │  scope=shared      │               │  scope=shared      │                │
│  └─────────┬──────────┘               └─────────┬──────────┘                │
│            │                                    │                            │
│            │         ┌──────────────────┐      │                            │
│            └────────>│  FEDERATED STORE │<─────┘                            │
│                      │  (PostgreSQL)    │                                   │
│                      │                  │                                   │
│                      │  - Cross-session │                                   │
│                      │  - Cross-pattern │                                   │
│                      │  - Queryable     │                                   │
│                      └──────────────────┘                                   │
│                                                                              │
│  KEY INSIGHT: Each swarm has isolated shared context, but                   │
│  both can query the federated store for historical learnings                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Use Cases for Multi-Orchestrator

1. **Parallel Development**: One swarm handles backend, another handles frontend
2. **Research + Implementation**: Research swarm discovers patterns, implementation swarm uses them
3. **Continuous Integration**: CI pipeline spawns swarms for different test suites

## Hierarchical Spawning

Agents can spawn sub-agents, creating hierarchical structures:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HIERARCHICAL SPAWNING                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Claude Code CLI                                                            │
│        │                                                                     │
│        │ "spawn Coordinator with scope=shared"                              │
│        ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                      Agentica Server                             │        │
│  └──────────────────────────┬──────────────────────────────────────┘        │
│                             │                                                │
│                             ▼                                                │
│                    ┌─────────────────┐                                      │
│                    │   Coordinator   │  <- Can spawn more agents            │
│                    │   (Manager)     │                                      │
│                    └────────┬────────┘                                      │
│                             │                                                │
│             ┌───────────────┼───────────────┐                               │
│             │               │               │                               │
│             ▼               ▼               ▼                               │
│     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                        │
│     │ Specialist 1│ │ Specialist 2│ │ Specialist 3│                        │
│     │ (Research)  │ │ (Implement) │ │ (Review)    │                        │
│     └──────┬──────┘ └──────┬──────┘ └─────────────┘                        │
│            │               │                                                │
│            ▼               ▼                                                │
│     ┌─────────────┐ ┌─────────────┐                                        │
│     │   Grunt 1   │ │   Grunt 2   │  <- Leaf agents (cannot spawn)         │
│     │ (File Read) │ │ (File Write)│                                        │
│     └─────────────┘ └─────────────┘                                        │
│                                                                              │
│  DEPTH LIMITS:                                                              │
│  - Default max_depth: 3 (Coordinator -> Specialist -> Grunt)                │
│  - Configurable per spawn call                                              │
│  - Prevents infinite recursion                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Hierarchical Pattern Implementation

```python
# Coordinator spawns specialists
async def coordinator_task():
    # Spawn research phase
    research_agent = await spawn(
        task="Research authentication patterns",
        scope="shared",
        can_spawn=True,  # Allow spawning sub-agents
        max_depth=2      # One more level allowed
    )

    # Research agent can spawn grunts
    # Grunts inherit scope but cannot spawn (max_depth exhausted)
```

## Evidence-Based Pattern Selection (Erotetic)

The erotetic framework replaces heuristic pattern selection with evidence-based reasoning:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EROTETIC PATTERN SELECTION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  BEFORE (Keyword Heuristics):                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  User says "research"  ──────────────> keyword match ───> Swarm     │    │
│  │  User says "implement" ──────────────> keyword match ───> Pipeline  │    │
│  │  User says "validate"  ──────────────> keyword match ───> Jury      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  PROBLEM: Keywords don't capture task structure                             │
│                                                                              │
│  AFTER (Evidence-Based - E(X,Q)):                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  E(X,Q) = Set of unknowns needed to answer Q given evidence X       │    │
│  │                                                                      │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │ Analyze task structure:                                      │    │    │
│  │  │                                                              │    │    │
│  │  │ E(X,Q) = {independent unknowns}                              │    │    │
│  │  │   -> Can explore in parallel                                 │    │    │
│  │  │   -> SELECT: Swarm / Map-Reduce                              │    │    │
│  │  │                                                              │    │    │
│  │  │ E(X,Q) = {sequential unknowns: u1 -> u2 -> u3}               │    │    │
│  │  │   -> Must resolve in order                                   │    │    │
│  │  │   -> SELECT: Pipeline                                        │    │    │
│  │  │                                                              │    │    │
│  │  │ E(X,Q) = {conflicting unknowns: u1 vs u2}                    │    │    │
│  │  │   -> Need synthesis of opposing views                        │    │    │
│  │  │   -> SELECT: Generator/Critic                                │    │    │
│  │  │                                                              │    │    │
│  │  │ E(X,Q) = {high-stakes unknowns}                              │    │    │
│  │  │   -> Need consensus/validation                               │    │    │
│  │  │   -> SELECT: Jury                                            │    │    │
│  │  │                                                              │    │    │
│  │  │ E(X,Q) = {hierarchical unknowns: broad -> specific}          │    │    │
│  │  │   -> Decompose then delegate                                 │    │    │
│  │  │   -> SELECT: Hierarchical                                    │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pattern Selection Examples

| Task | E(X,Q) Analysis | Selected Pattern |
|------|-----------------|------------------|
| "Research auth libraries" | `{lib1_features, lib2_features, lib3_features}` - independent | **Swarm** |
| "Build user registration" | `{schema -> api -> ui}` - sequential | **Pipeline** |
| "Review this PR" | `{security_issues, style_issues, logic_issues}` - independent | **Swarm** |
| "Is this code correct?" | `{validator1_opinion, validator2_opinion, validator3_opinion}` - voting | **Jury** |
| "Improve this algorithm" | `{proposal, critique}` - dialectic | **Generator/Critic** |

## Communication Protocol

### The 3-Layer Memory IS the Communication Mechanism

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COMMUNICATION VIA MEMORY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Traditional Message Passing:                                               │
│  ┌─────────┐    message    ┌─────────┐                                      │
│  │ Agent A │ ─────────────> │ Agent B │                                      │
│  └─────────┘               └─────────┘                                      │
│                                                                              │
│  Memory-Based Communication:                                                │
│  ┌─────────┐                ┌─────────┐                                      │
│  │ Agent A │                │ Agent B │                                      │
│  └────┬────┘                └────┬────┘                                      │
│       │ write                    │ read                                      │
│       ▼                          ▼                                           │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │              SHARED CONTEXT                          │                    │
│  │                                                      │                    │
│  │  key: "research_findings"                           │                    │
│  │  value: { sources: [...], summary: "..." }          │                    │
│  │                                                      │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                              │
│  ADVANTAGES:                                                                │
│  - Natural persistence (memory outlives agents)                             │
│  - Broadcast by default (all shared-scope agents see it)                    │
│  - Queryable (can search historical communications)                         │
│  - No routing logic needed (scope rules handle it)                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Communication Rules by Scope

| Scope | Write To | Read From |
|-------|----------|-----------|
| `isolated` | Local cache only | Local cache only |
| `shared` | Local + shared context | Local + shared context |
| `federated` | All layers | All layers (including cross-session queries) |

### Pattern Algebra Defines WHEN

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PATTERN-SPECIFIC COMMUNICATION                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SWARM:                                                                     │
│  - Agents write to shared context independently                             │
│  - Aggregator reads all results at pattern completion                       │
│  - No inter-agent reads during execution                                    │
│                                                                              │
│  PIPELINE:                                                                  │
│  - Agent N writes output                                                    │
│  - Agent N+1 reads Agent N's output                                         │
│  - Sequential handoff via shared context keys                               │
│                                                                              │
│  GENERATOR/CRITIC:                                                          │
│  - Generator writes proposal                                                │
│  - Critic reads proposal, writes critique                                   │
│  - Generator reads critique, writes revised proposal                        │
│  - Iterative until convergence                                              │
│                                                                              │
│  BLACKBOARD:                                                                │
│  - All agents can read/write anytime                                        │
│  - Coordinator monitors for convergence                                     │
│  - Most flexible but requires careful design                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Open Question: Message Format Schema

The current implementation uses unstructured shared context (dict with any keys/values). Future work may introduce:

```python
# Potential structured message format
@dataclass
class AgentMessage:
    sender_id: str
    timestamp: datetime
    message_type: Literal["result", "request", "handoff", "error"]
    payload: dict
    metadata: dict  # pattern-specific fields
```

**Trade-offs to consider:**
- Schema enforcement vs. flexibility
- Versioning and backward compatibility
- Performance overhead of validation

## Bird's Eye View Problem

Observability of multi-agent systems remains an open challenge:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OBSERVABILITY CHALLENGES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CURRENT STATE:                                                             │
│  - Braintrust tracing captures individual agent spans                       │
│  - Session tree tracks parent-child relationships                           │
│  - watch_agents.py provides real-time status                                │
│                                                                              │
│  GAPS:                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  1. GLOBAL VIEW                                                     │    │
│  │     - What are ALL agents doing right now?                          │    │
│  │     - Cross-orchestrator visibility                                 │    │
│  │                                                                      │    │
│  │  2. MESSAGE FLOW                                                    │    │
│  │     - Who wrote what to shared context?                             │    │
│  │     - Timeline of memory operations                                 │    │
│  │                                                                      │    │
│  │  3. CAUSAL DEBUGGING                                                │    │
│  │     - Why did Agent B fail?                                         │    │
│  │     - Trace back to Agent A's bad output                            │    │
│  │                                                                      │    │
│  │  4. RESOURCE TRACKING                                               │    │
│  │     - Token usage across swarm                                      │    │
│  │     - Cost attribution per pattern                                  │    │
│  │                                                                      │    │
│  │  5. LIVE VISUALIZATION                                              │    │
│  │     - Real-time graph of agent relationships                        │    │
│  │     - Memory state dashboard                                        │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  POTENTIAL SOLUTIONS:                                                       │
│  - OpenTelemetry integration for distributed tracing                        │
│  - Event sourcing for memory operations                                     │
│  - GraphQL API for querying agent state                                     │
│  - Real-time WebSocket dashboard                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Summary

The Agentica runtime architecture provides:

1. **Layered Memory**: Local cache -> Shared context -> Federated store
2. **Scope-Based Access**: Isolated, shared, or federated visibility
3. **Hierarchical Spawning**: Agents can spawn sub-agents with depth limits
4. **Evidence-Based Selection**: Erotetic framework for pattern selection
5. **Memory-Based Communication**: No explicit message passing needed

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Separation of concerns** | Memory layers handle communication; patterns handle coordination |
| **Scope isolation** | Agents only see what they need to see |
| **Evidence over heuristics** | E(X,Q) analysis determines pattern selection |
| **Federated learning** | Cross-session knowledge synthesis |

### Future Work

- Standardized message format schema
- Enhanced observability tooling
- Cost tracking and optimization
- Live visualization dashboard
