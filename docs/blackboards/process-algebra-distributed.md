# Blackboard: Process Algebra for Parallel and Distributed Processing

## Context
Extracting composition patterns for multi-agent workflows.
Focus: Distribution, parallelism, real-world applications.

---

## Composition Operators

### 1. Parallel Composition with Synchronization

**Operator:** `P || Q` (interleaved parallel) or `P |[A]| Q` (synchronized on A)

In distributed systems, parallel composition extends beyond simple interleaving:
- **Interleaving semantics**: Actions of P and Q are arbitrarily interleaved
- **Synchronized parallel**: Components synchronize on shared actions (from set A)
- **Full synchronization**: `P ||| Q` - no shared actions, full independence

**Distributed variant (D-pi calculus):**
```
P@l1 || Q@l2   -- P runs at location l1, Q runs at location l2
```

### 2. Location-Aware Composition

**Operator:** `P@l` (located process)

From Distributed Pi-calculus (Dpi) and Ambient Calculus:
- **Located processes**: `P@l` means process P executes at location l
- **Migration**: `go l.P` - process migrates to location l, then becomes P
- **Spawn**: `l!P` - spawn process P at remote location l

**Key operators:**
- `(new l)P` - create new location l, scope restriction
- `l[P]` - ambient named l containing process P
- `in l.P` - enter ambient l
- `out l.P` - exit ambient l

### 3. Distributed Choice

**Operator:** `P + Q` (non-deterministic choice) extended for distribution

In distributed settings, choice is problematic (no global state):
- **Local choice**: `a.P + b.Q` at single location
- **Distributed choice**: Requires consensus or coordination
- **Guarded choice**: Only allow input/output guards to resolve choice

### 4. Locality and Restriction

**Operator:** `(new a)P` or `(nu a)P`

Creates private channel/name scoped to P:
- **Scope extrusion**: Private name can escape via communication
- **Distributed restriction**: `(new a@l)P` - name a is local to location l
- **Failure locality**: Faults at location l don't affect location l'

### 5. Asynchronous Message Passing

**Operator:** `a<v>` (async send) vs `a(x).P` (receive)

Critical for distribution (no rendez-vous):
- **Asynchronous output**: `a<v>` - fire and forget, non-blocking
- **Buffered channels**: Messages queue until consumed
- **Join patterns**: `a(x) & b(y) -> P` - synchronize on multiple inputs

### 6. Failure and Recovery Operators

**Operators for fault tolerance:**
- **Try-catch**: `try P catch Q` - if P fails, execute Q
- **Timeout**: `P timeout(t) Q` - if P takes longer than t, switch to Q
- **Persistent process**: `!P` (replication) - always available copy of P
- **Recovery point**: `checkpoint(P) ; Q` - save state, continue with Q

### 7. Distributed Transaction Operators

**From compensating CSP and Sagas:**
- **Compensating pair**: `P % Q` - if P succeeds but later needs rollback, run Q
- **Saga composition**: `P1/C1 ; P2/C2 ; P3/C3` - forward actions with compensations
- **Two-phase commit**: Coordination primitive built from synchronization

### 8. Broadcasting and Multicast

**Operator:** `a!!v` (broadcast) or `{l1,l2,l3}!v` (multicast)

- **Broadcast**: Send to all processes listening on channel a
- **Multicast group**: Send to specific set of locations
- **Publish-subscribe**: `subscribe(a) ; a?(x).P` - register for topic a

---

## Distribution & Locality

### 1. Location Primitives (Process Algebra Locality)

**Located Processes (D-Pi Calculus)**
```
P@l        -- Process P running at location l
l[P]       -- Alternative notation: P contained in location l
```

Location is a first-class construct that:
- Binds a process to a specific execution site
- Enables reasoning about where computation happens
- Provides isolation boundaries between distributed components

**Location Types:**
- **Physical**: Maps to network addresses, machines, data centers
- **Logical**: Abstract execution contexts (agent instances)
- **Hierarchical**: Nested locations `l1.l2.l3` form containment trees

**Locality Invariant (Key Theorem):**
> If process P at location l only uses channels local to l, then P cannot affect processes at other locations.

**Multi-Agent Mapping:**
- Each agent runs at a logical "location"
- Location = isolation boundary for context/memory
- Hierarchical pattern: `coordinator@root`, `workers@{l1, l2, l3}`

### 2. Process Migration

**Migration Operators (Mobile Ambients, D-Pi)**
```
go l.P         -- Migrate to location l, then continue as P
move l in P    -- Move P into location l
in n.P         -- Enter ambient n (Ambient Calculus)
out n.P        -- Exit ambient n
open n.P       -- Dissolve ambient boundary, expose contents
```

**Migration Semantics:**
- Process identity preserved across migration
- Local state travels with the process
- Channel endpoints may or may not migrate (design choice)

**Migration Laws:**
```
go l.(go l'.P) ~> go l'.P    -- Last destination wins
(go l.P)@l' ~> P@l           -- Migration completes
```

**Migration Preservation Theorem:**
> Process equivalence is preserved under migration: `P ~ Q implies go l.P ~ go l.Q`

**Multi-Agent Mapping:**
- Agent handoff = `go coordinator.report_result`
- Hierarchical spawn = `move worker_pool in new_agent`
- Circuit breaker = migrate to fallback location on failure
- Load balancing = `go least_loaded.continue_work`

### 3. Distributed Process Location

**Location as First-Class Value (Higher-Order Distributed Pi)**
```
(new l)P           -- Create fresh location l
l?P                -- Receive location, bind to P
a!(l)              -- Send location l on channel a
a?(x:loc).P@x      -- Receive location, execute P there
```

**Location Topology:**
```
parent(l)          -- Parent location in hierarchy
children(l)        -- Set of child locations
sibling(l1, l2)    -- l1 and l2 share same parent
adjacent(l1, l2)   -- Direct communication path exists
path(l1, l2)       -- Any communication path exists
```

**Location Failure Semantics:**
```
fail(l)            -- Location l has crashed
l down: P          -- P executes when l fails (failure handler)
recover(l).P       -- Block until l recovers, then continue as P
alive(l)?P:Q       -- If l is alive do P, else do Q
```

**Location Equivalence:**
```
P@l ~ P@l'         -- Location irrelevance (if P is location-transparent)
```

**Multi-Agent Mapping:**
- `(new worker)spawn(task)` = create new agent location
- `coordinator?(l).dispatch(l, subtask)` = receive agent reference, delegate
- `fail(worker3) => redistribute_work` = handle agent failures
- Topology = swarm (flat), hierarchy (tree), pipeline (chain)

### 4. Distributed Hiding (Location-Scoped Restriction)

**Basic Restriction (Local Hiding):**
```
(new a)P           -- Channel a is private to P
(nu a)P            -- Alternative notation (nu-binder)
```

**Location-Scoped Restriction:**
```
(new l:c)P         -- Channel c is local to location l in process P
l :: (nu c)P       -- Restriction of c to location l
local(c, l).P      -- c is visible only at location l
global(c).P        -- c is visible globally (all locations)
```

**Cross-Location Hiding:**
```
{l1, l2} \ c       -- Hide channel c from locations l1 and l2
hide c in {L}      -- c invisible to all locations in set L
expose c to {L}    -- c visible only to locations in set L
```

**Distributed Scope Extrusion:**
When a private channel escapes via communication across locations:
```
(new c)(c!m@l1 || c?x.P@l2)
~> P[m/x]@l2      -- c extruded from l1 to l2
```

Key property: The scope of c expands to include l2 after communication.

**Hiding Laws:**
```
(new c)(P@l1 || Q@l2) ~ (new c)P@l1 || Q@l2   -- if c not free in Q
P \ {} ~ P                                     -- hiding nothing is identity
P \ {c} ~ P                                    -- if c not used in P
```

**Multi-Agent Mapping:**
- `local(scratchpad, worker)` = worker-private reasoning space
- `global(result_channel)` = all agents can publish results
- `hide deliberation in {jury1, jury2, jury3}` = Jury pattern: internal discussion hidden
- `expose blackboard to {*}` = Blackboard pattern: shared knowledge space
- Scope extrusion = credential/secret passing between agents

### 5. Location Failure and Recovery Mechanisms

**Failure Primitives:**
```
kill(l)            -- Force-terminate location l
crash(l)           -- Simulate crash at l
timeout(l, t)      -- l fails if unresponsive for time t
```

**Recovery Patterns:**
```
supervise l: P     -- Restart P at l if it fails
checkpoint(l)      -- Save state of location l
restore(l)         -- Restore l from last checkpoint
migrate(l, l')     -- Move contents of l to l' (failover)
```

**Failure Propagation:**
```
fail(l) ||  P@l  ~> fail(l)      -- Failure dominates local process
fail(l) || P@l'  ~> P@l'         -- Failure is local (l != l')
fail(parent(l)) ~> fail(l)       -- Hierarchical failure propagation
```

**Multi-Agent Mapping:**
- Circuit breaker = `timeout(primary, 5s) => go fallback.continue`
- Supervisor trees = `supervise worker: task_loop`
- Hierarchical recovery = coordinator detects worker failure, respawns
- Swarm resilience = continue if majority of locations survive

### 6. Location Types for Pattern Classification

| Pattern | Location Structure | Migration | Hiding Scope | Failure Domain |
|---------|-------------------|-----------|--------------|----------------|
| **Hierarchical** | Tree (coordinator at root) | Down only | Per-level | Propagates up |
| **Swarm** | Flat peers | Any-to-any | Global channel | Isolated |
| **Pipeline** | Linear chain | Forward only | Per-stage | Stops pipeline |
| **Map/Reduce** | Star (aggregator center) | To center | Map: local, Reduce: global | Partial ok |
| **Jury** | Isolated peers + verdict | To verdict collector | Deliberation hidden | Majority rules |
| **Blackboard** | Shared central location | Read/write to shared | Public board | Central failure = total |
| **Circuit Breaker** | Primary + fallback | On failure | State shared | Failover |
| **Generator/Critic** | Alternating pair | Bidirectional | Drafts hidden | Restart cycle |

---

## Algebraic Laws

### Core Insight: Laws Specific to Distributed Systems

In distributed process algebras (D-Pi, Ambient Calculus, distributed CSP), the algebraic laws must account for:
1. **Location transparency** - hiding where processes execute
2. **Migration** - processes moving between locations
3. **Failure** - partial failures and recovery
4. **Asynchrony** - message delays and reordering

### Parallel Composition Laws (Distributed Extension)

**Standard Laws (inherited from CCS/CSP):**
```
P | Q = Q | P                           -- Commutativity
(P | Q) | R = P | (Q | R)               -- Associativity
P | 0 = P                               -- Identity (nil process)
```

**Distributed Extension Laws:**
```
l[P] | l[Q] = l[P | Q]                  -- Location Fusion
l[P] | m[Q] = m[Q] | l[P]               -- Location Commutativity (l != m)
l[0] = 0                                -- Empty Location Collapse
```

**Agent Pattern Analog:**
- Location Fusion: Agents at same location can share memory
- Location Commutativity: Independent agents can execute in any order
- Empty Collapse: Terminated agents are garbage-collected

### Distributed Bisimulation Laws

**Strong Bisimulation (~):**
```
P ~ Q  implies  l[P] ~ l[Q]             -- Location Congruence
P ~ Q  implies  P | R ~ Q | R           -- Parallel Context
P ~ Q  implies  (nu a)P ~ (nu a)Q       -- Restriction Context
```

**Weak Bisimulation (approx):**
```
P approx Q  implies  l[P] approx l[Q]   -- Weak Location Congruence
tau.P approx P                          -- Tau Absorption (internal steps invisible)
```

**Location Bisimulation (distributed-specific):**
```
l[m[P]] bisim_loc l[P] iff l = m        -- Location Flattening (same location)
l[a!v.P] bisim_loc l[P] | a!v           -- Output Asynchrony
```

**Agent Pattern Analog:**
- Bisimulation allows replacing agents with behaviorally equivalent ones
- Weak bisimulation hides internal coordination overhead
- Location bisimulation enables location-agnostic reasoning

### Scope Extrusion Laws (Distributed Pi-calculus)

**Basic Scope Extrusion:**
```
(nu a)(P | Q) = P | (nu a)Q   if a not in fn(P)   -- Scope Narrowing
(nu a)(nu b)P = (nu b)(nu a)P                      -- Scope Commutativity
(nu a)0 = 0                                        -- Empty Scope Collapse
```

**Location-aware Scope Extrusion:**
```
l[(nu a)P] = (nu a)l[P]   if a != l               -- Scope Through Location
(nu l)l[P] = 0            if P has no migration    -- Location Garbage Collection
```

**Distributed Name Passing:**
```
l[a!<b>.P] | m[a?(x).Q] -> l[P] | m[Q{b/x}]       -- Remote Communication
l[go m.P] -> m[P]                                  -- Migration
```

**Agent Pattern Analog:**
- Scope extrusion models channel/capability passing between agents
- Location GC models agent lifecycle management
- Remote communication models inter-agent message passing

### Distribution-Specific Axioms

**Failure and Recovery:**
```
l[P] | fail(l) -> 0                               -- Location Failure
l[P] | recover(l, Q) -> l[Q]                      -- Location Recovery
(P | fail(l)) | recover(l, Q) = P | l[Q]          -- Recovery Semantics
```

**Asynchronous Message Laws:**
```
a!v | a!w = a!w | a!v                             -- Output Commutativity
a!v.P | a?(x).Q -> P | Q{v/x}                     -- Synchronous Rendezvous
a<<v>> | a?(x).Q -> Q{v/x}                        -- Async Message Consumption
```

**Ordering and Causality:**
```
(a!v ; b!w) != (b!w ; a!v)   in general           -- Sequential Order Matters
(a!v || b!w) = (b!w || a!v)                       -- Parallel Order Irrelevant
a!v --> b!w  implies  causally_before(a, b)       -- Causal Ordering
```

**Agent Pattern Analog:**
- Failure/recovery models circuit breaker patterns
- Async message laws model event-driven patterns
- Causal ordering models dependency tracking in pipelines

### Equivalence Laws for Distribution

**May-Testing Equivalence:**
```
P =_may Q  iff  forall C: (C[P] may pass) <=> (C[Q] may pass)
```

**Must-Testing Equivalence:**
```
P =_must Q  iff  forall C: (C[P] must pass) <=> (C[Q] must pass)
```

**Barbed Congruence (Distributed):**
```
P =_barb Q  iff  forall l, a:
  l[P] has_barb a  <=>  l[Q] has_barb a
```

**Fair Testing (for distributed systems):**
```
P =_fair Q  iff  under fair scheduling:
  P diverges <=> Q diverges
  P deadlocks <=> Q deadlocks
```

**Agent Pattern Analog:**
- May-testing: "agent can produce result"
- Must-testing: "agent will definitely produce result"
- Barbed congruence: external observability
- Fair testing: accounting for scheduler fairness

### Reduction Laws for Optimization

**Fusion Laws:**
```
l[P] | l[Q] -> l[P | Q]                           -- Colocate for efficiency
(nu a)(P | a?(x).Q) -> (nu a)P | Q{v/x}           -- Inline communication
```

**Garbage Collection Laws:**
```
(nu a)P = P   if a not in fn(P) and a not in bn(P)  -- Unused Name GC
l[0] = 0                                             -- Empty Location GC
P | 0 = P                                            -- Nil Process GC
```

**Parallel Reduction:**
```
P -> P'  implies  P | Q -> P' | Q                 -- Independent Progress
l[P] -> l[P']  implies  l[P] | m[Q] -> l[P'] | m[Q]  -- Location Independence
```

**Agent Pattern Analog:**
- Fusion enables agent colocation optimization
- GC laws enable resource cleanup
- Parallel reduction enables true parallelism

### Replication Laws

```
!P ~ P | !P                                        -- Replication Unfolds
!(P | Q) ~ !P | !Q                                 -- Replication Distributes
!0 = 0                                             -- Null Replication
!(nu a)P = (nu a)!P   if a bound in P              -- Scope Through Replication
```

**Agent Pattern Analog:**
- Replication models stateless worker pools
- Unfold rule: always have a spare worker available
- Distribution: parallel replication for scaling

### Summary Table: Laws by Category

| Category | Law | Formula | Agent Use |
|----------|-----|---------|-----------|
| Parallel | Commutativity | `P \| Q = Q \| P` | Order independence |
| Parallel | Associativity | `(P\|Q)\|R = P\|(Q\|R)` | Grouping flexibility |
| Location | Fusion | `l[P]\|l[Q] = l[P\|Q]` | Colocation |
| Scope | Extrusion | `(nu a)(P\|Q) = P\|(nu a)Q` | Capability passing |
| Failure | Recovery | `fail(l) \| recover(l,Q) -> l[Q]` | Circuit breaker |
| Bisim | Congruence | `P~Q => C[P]~C[Q]` | Agent substitution |
| Async | Output Comm | `a!v \| a!w = a!w \| a!v` | Event buffering |
| Replication | Unfold | `!P ~ P \| !P` | Worker pool |
| GC | Nil Process | `P \| 0 = P` | Resource cleanup |
| Causality | Independence | `(a\|\|b) = (b\|\|a)` | Parallel execution |

---

## Relevance to Pattern Composition

### Mapping to Multi-Agent Patterns

| Distributed Operator | Agent Pattern | Application |
|---------------------|---------------|-------------|
| `P@l1 \|\| Q@l2` | **Swarm** | Agents at different "locations" (contexts) |
| `P \|[sync]\| Q` | **Pipeline** | Handoff synchronization between stages |
| `go l.P` | **Delegation** | Agent migrates work to specialist |
| `l!P` | **Spawn** | Create new agent at location |
| `a!!v` | **Broadcast** | Coordinator broadcasts to all workers |
| `P % Q` | **Circuit Breaker** | Compensation when P fails |
| `!P` | **Replication** | Stateless workers (scale out) |
| `a(x) & b(y)` | **Aggregator** | Collect from multiple sources |
| `checkpoint ; P` | **State persistence** | Save agent state for recovery |
| `P + Q` (guarded) | **Router** | Choose handler based on first input |

### Composition Algebra for Patterns

Define pattern composition:
```
Pattern1 >> Pattern2   -- sequential (pipeline)
Pattern1 || Pattern2   -- parallel (swarm/map)
Pattern1 + Pattern2    -- choice (router)
Pattern1 % Pattern2    -- with fallback (circuit breaker)
```

### Key Insights for Implementation

1. **Location = Agent Context**: Each agent is a "location" with private state
2. **Channels = Message Queues**: Communication is asynchronous
3. **Scope = Visibility**: Restricted channels are private conversations
4. **Failure Domains**: Agent failures are local (don't crash the swarm)
5. **Replication = Scaling**: `!Worker` gives infinite supply of workers
6. **Migration = Handoff**: Agent work can move between contexts
7. **Hiding = Encapsulation**: Internal deliberation hidden from outside

---

## Sources

- Milner, R. "Communicating and Mobile Systems: The Pi-Calculus" (1999)
- Hennessy, M. & Riely, J. "Resource Access Control in Systems of Mobile Agents" (HLCL 1998)
- Cardelli, L. & Gordon, A. "Mobile Ambients" (FoSSaCS 1998)
- Fournet, C. & Gonthier, G. "The Join Calculus" (POPL 1996)
- Process Algebra for Parallel and Distributed Processing (Bergstra et al., 2010)
- Francalanza, A. et al. "A Theory of Monitors" (2017)
- Sangiorgi, D. & Walker, D. "The Pi-Calculus: A Theory of Mobile Processes" (2003)
- ISO/IEC LOTOS/E-LOTOS specifications

---

## Research Methodology

**Ragie queries used:**
1. `distributed process algebra laws`
2. `distributed equivalence process algebra`
3. `distributed bisimulation`
4. `parallel distributed axioms process algebra`

**To execute Ragie queries manually:**
```bash
cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit

uv run python scripts/ragie_query.py --query "distributed process algebra laws" --top-k 10 --rerank
uv run python scripts/ragie_query.py --query "distributed equivalence process algebra" --top-k 10 --rerank
uv run python scripts/ragie_query.py --query "distributed bisimulation" --top-k 10 --rerank
uv run python scripts/ragie_query.py --query "parallel distributed axioms process algebra" --top-k 10 --rerank
```
