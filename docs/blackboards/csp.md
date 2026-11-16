# Blackboard: Communicating Sequential Processes (Hoare)

## Context
Extracting composition patterns for multi-agent workflows.
Focus: How CSP handles sequential/parallel composition and scope.

---

## Composition Operators

### Operator: Prefix (Action Guard)
- **Syntax:** `a -> P` (event `a` then process `P`)
- **Semantics:** Process waits for event `a` to occur, then behaves as `P`. This is the fundamental building block - all processes are constructed from prefixed events.
- **Laws:**
  - `a -> STOP` is the simplest non-trivial process (do `a`, then deadlock)
  - `a -> (b -> P) = (a -> b -> P)` (prefix is right-associative)
  - Prefix is deterministic - only one initial event

### Operator: Sequential Composition
- **Syntax:** `P ; Q` (P then Q)
- **Semantics:** Process `P` executes to successful termination (signal `tick`/`checkmark`), then `Q` begins. The termination of `P` is invisible externally; only `Q`'s behavior follows.
- **Laws:**
  - `(P ; Q) ; R = P ; (Q ; R)` (associativity)
  - `SKIP ; P = P` (SKIP is left identity)
  - `P ; SKIP = P` (SKIP is right identity)
  - `STOP ; Q = STOP` (deadlock propagates - zero element)
  - NOT commutative: `P ; Q != Q ; P` in general

### Operator: Parallel Composition (Synchronous/Alphabetized)
- **Syntax:** `P || Q` (P and Q synchronized on common alphabet)
- **Semantics:** Both processes execute concurrently. Events in the intersection of their alphabets require synchronization (both must participate). Events outside the intersection can proceed independently.
- **Laws:**
  - `P || Q = Q || P` (commutativity)
  - `(P || Q) || R = P || (Q || R)` (associativity)
  - `P || STOP = STOP` (if alphabets overlap - deadlock propagates)
  - `SKIP || SKIP = SKIP` (both terminate successfully)

### Operator: Generalized Parallel (Interface Parallel)
- **Syntax:** `P [| A |] Q` (synchronize on set A only)
- **Semantics:** Explicit synchronization set. Processes must synchronize on events in A; events outside A are interleaved independently.
- **Laws:**
  - `P [| {} |] Q = P ||| Q` (empty sync = interleaving)
  - `P [| Events |] Q = P || Q` (full sync = alphabetized parallel)
  - Commutativity: `P [| A |] Q = Q [| A |] P`

### Operator: Alphabetized Parallel
- **Syntax:** `P [A || B] Q` (P with alphabet A, Q with alphabet B)
- **Semantics:** Explicit alphabet declaration. P can only perform events in A, Q can only perform events in B. They synchronize on A intersect B.
- **Laws:**
  - Generalizes `||` with explicit alphabet control
  - `alpha(P [A || B] Q) = A union B`

### Operator: Interleaving (Independent Parallel)
- **Syntax:** `P ||| Q` (P interleaved with Q)
- **Semantics:** Both processes execute concurrently with NO synchronization. Events from each are arbitrarily interleaved. This is "pure parallelism" without communication.
- **Laws:**
  - `P ||| Q = Q ||| P` (commutativity)
  - `(P ||| Q) ||| R = P ||| (Q ||| R)` (associativity)
  - `STOP ||| P = P` (STOP contributes nothing - identity for interleave)
  - `SKIP ||| P = P` (for termination)

### Operator: External Choice (Deterministic)
- **Syntax:** `P [] Q` (external/deterministic choice)
- **Semantics:** Environment chooses between P and Q by offering the first event. If environment offers event in alphabet(P) but not alphabet(Q), P is chosen. Resolution happens on first observable event.
- **Laws:**
  - `P [] Q = Q [] P` (commutativity)
  - `(P [] Q) [] R = P [] (Q [] R)` (associativity)
  - `P [] P = P` (idempotence)
  - `P [] STOP = P` (STOP offers nothing - identity)
  - `(a -> P) [] (b -> Q)` - environment chooses by offering `a` or `b`
  - `(a -> P) [] (a -> Q) = a -> (P |~| Q)` (same guard: becomes internal choice)

### Operator: Internal Choice (Nondeterministic)
- **Syntax:** `P |~| Q` (internal/nondeterministic choice)
- **Semantics:** Process makes the choice internally, nondeterministically. Environment cannot influence which branch is taken. Models implementation freedom.
- **Laws:**
  - `P |~| Q = Q |~| P` (commutativity)
  - `(P |~| Q) |~| R = P |~| (Q |~| R)` (associativity)
  - `P |~| P = P` (idempotence)
  - `(P |~| Q) [] R = (P [] R) |~| (Q [] R)` (distributes into external choice)

### Operator: Conditional Choice (Boolean Guard)
- **Syntax:** `P <| b |> Q` (if b then P else Q)
- **Semantics:** Boolean guard `b` determines which branch executes. Deterministic choice based on state.
- **Laws:**
  - `P <| true |> Q = P`
  - `P <| false |> Q = Q`
  - `P <| b |> P = P` (both branches same)

### Operator: Hiding (Concealment)
- **Syntax:** `P \ A` (P with events in set A hidden)
- **Semantics:** Events in A become invisible (tau/internal). They still occur but cannot be observed or synchronized with. Converts external actions to internal.
- **Laws:**
  - `(P \ A) \ B = P \ (A union B)` (hiding composition)
  - `P \ {} = P` (hiding nothing is identity)
  - `(P [] Q) \ A = (P \ A) [] (Q \ A)` (distributes over external choice)
  - Warning: `P \ alphabet(P) = divergence` if P has infinite internal computation

### Operator: Renaming
- **Syntax:** `P [[a <- b]]` or `P [[f]]` (apply function f to events)
- **Semantics:** All occurrences of event `a` in P are replaced with event `b`. Interface adaptation for composition.
- **Laws:**
  - `P [[a <- a]] = P` (identity renaming)
  - `(P [[f]]) [[g]] = P [[f ; g]]` (renaming composition)
  - Renaming distributes over all operators

### Operator: Interrupt
- **Syntax:** `P /\ Q` (P interrupted by Q)
- **Semantics:** P executes until Q's first event occurs, then Q takes over permanently. Models timeout and exception handling.
- **Laws:**
  - `P /\ STOP = P` (no interrupt possible - STOP offers nothing)
  - `STOP /\ Q = Q` (immediate interrupt since P cannot proceed)
  - NOT symmetric: `P /\ Q != Q /\ P`

### Operator: Timeout
- **Syntax:** `P [> Q` (P with timeout to Q)
- **Semantics:** If P cannot immediately offer an event, control passes to Q. Models default behavior when stuck.
- **Laws:**
  - `STOP [> Q = Q` (immediate timeout - STOP cannot proceed)
  - `(a -> P) [> Q = (a -> P) [] Q` (available action prevents timeout)

### Operator: Exception (Throw-Catch)
- **Syntax:** `P [| A |> Q` (P with exception set A caught by Q)
- **Semantics:** P runs normally. If an event from A occurs, control transfers to Q (exception handler).
- **Laws:**
  - `P [| {} |> Q = P` (empty exception set - no transfer)
  - Similar to interrupt but with explicit exception event set

### Operator: Linked Parallel
- **Syntax:** `P [a <-> b] Q` (link events a and b between P and Q)
- **Semantics:** Events `a` in P and `b` in Q are bound together - when one occurs, the other must too. Creates bidirectional communication channels.
- **Laws:**
  - Used for synchronous message passing between named channels

### Operator: Replicated (Indexed) Operators
- **Syntax:** `||| i : S @ P(i)` (interleave all P(i) for i in set S)
- **Semantics:** Creates multiple copies of a parameterized process and composes them.
- **Variants:**
  - `[] i : S @ P(i)` - replicated external choice
  - `; i : <1..n> @ P(i)` - replicated sequential composition
  - `|| i : S @ [A(i)] P(i)` - replicated parallel with alphabets

---

## Scope & Hiding

### Overview

CSP provides several mechanisms for controlling visibility and scope of events. These are essential for abstraction, information hiding, and modular composition.

### 1. The Hiding Operator (`\ ` or `\`)

**Syntax:**
```
P \ A
```

**Semantics:**
- `P \ A` behaves like process `P`, but all events in set `A` are hidden (internalized)
- Hidden events become **tau (internal)** actions - invisible to the environment
- The environment cannot observe or synchronize on hidden events

**Key Properties:**
- Hiding removes events from the alphabet: `alpha(P \ A) = alpha(P) - A`
- Hidden events still occur but are unobservable
- Creates **abstraction boundaries** - internal implementation details are concealed

**Example:**
```csp
-- A buffer that hides internal transfer events
BUFFER = (in -> mid -> out -> BUFFER) \ {mid}
-- External view: only 'in' and 'out' are visible
```

**Algebraic Laws:**
```
P \ {} = P                           -- Empty hiding is identity
P \ A \ B = P \ (A union B)          -- Hiding is idempotent/compositional
(P [] Q) \ A = (P \ A) [] (Q \ A)    -- Distributes over external choice
```

### 2. The Alphabet (Process Scope)

**Concept:**
Every process `P` has an **alphabet** `alpha(P)` - the set of events it can engage in.

**Role in Scoping:**
- Alphabet defines the "interface" of a process
- Parallel composition synchronizes on shared alphabet events
- Non-alphabet events cannot be performed

**Parallel Composition with Alphabets:**
```
P [| A |] Q
```
- Processes synchronize on events in set `A`
- Events outside `A` are interleaved (asynchronous)

**Interface Parallel:**
```
P [A || B] Q
```
- `P` has alphabet `A`, `Q` has alphabet `B`
- Synchronization occurs on `A intersection B`

### 3. Restriction vs Hiding

**Restriction** (not in original CSP, but in CCS/pi-calculus):
- Prevents events from ever occurring
- More restrictive than hiding

**Hiding** (CSP approach):
- Events still occur but are unobservable
- Process can still make internal progress

**Comparison:**
| Aspect | Hiding (CSP) | Restriction (CCS) |
|--------|--------------|-------------------|
| Event occurrence | Events occur as tau | Events cannot occur |
| Progress | Internal progress possible | Blocked if only restricted events available |
| Abstraction | Implementation hiding | True removal |

### 4. Scope and Parallel Composition

**Synchronization Algebra:**
```
P || Q
```
- In alphabetized parallel, processes synchronize on shared events
- Each process's scope is defined by its alphabet

**Scope Isolation Patterns:**

1. **Isolated Scope** (No shared events):
```csp
P [| {} |] Q
-- Complete interleaving, no synchronization
```

2. **Shared Scope** (Explicit sync events):
```csp
P [| {sync, done} |] Q
-- Only synchronize on 'sync' and 'done'
```

3. **Federated Scope** (Alphabet intersection):
```csp
P [alpha(P) || alpha(Q)] Q
-- Synchronize on alpha(P) intersection alpha(Q)
```

### 5. Abstraction Function

**Definition:**
Given hiding operator and traces model:
```
traces(P \ A) = {t \ A : t in traces(P)}
```
Where `t \ A` removes all events in `A` from trace `t`.

**Abstraction Properties:**
- Creates quotient processes
- Enables refinement checking at different abstraction levels
- Supports compositional verification

### 6. Renaming (Interface Adaptation)

**Syntax:**
```
P [[a <- b]]
```

**Semantics:**
- Renames event `a` to `b` in process `P`
- Changes the interface without changing structure
- Useful for composing processes with incompatible alphabets

**Scope Implications:**
- Renaming can bring events into or out of synchronization scope
- Enables adapter patterns for composing disparate processes

### 7. CSP Scope Patterns for Multi-Agent Workflows

| Agent Pattern | CSP Scope Model | Mechanism |
|---------------|-----------------|-----------|
| **Isolated** | `P [| {} |] Q` | No shared alphabet |
| **Shared** | `P [| A |] Q` | Explicit sync set |
| **Federated** | `(P \ internal) [| A |] (Q \ internal)` | Hide internals, share interface |

**Hiding for Pattern Composition:**
```csp
-- Hierarchical: Coordinator hides worker internals
COORDINATOR = (WORKER1 ||| WORKER2) \ worker_events

-- Pipeline: Each stage hides internal processing
PIPELINE = (STAGE1 \ internal1) >> (STAGE2 \ internal2)

-- Swarm: Hide individual agent actions, expose results
SWARM = (||| i : AGENTS @ AGENT(i)) \ exploration_events
```

### Summary Table

| Operator | Syntax | Effect on Scope |
|----------|--------|-----------------|
| **Hiding** | `P \ A` | Internalizes events in A |
| **Parallel** | `P [| A |] Q` | Synchronizes on A |
| **Interleave** | `P ||| Q` | No synchronization |
| **Rename** | `P [[a <- b]]` | Adapts interface |
| **Alphabet** | `alpha(P)` | Defines process scope |

### Sources

- Hoare, C.A.R. "Communicating Sequential Processes" (1985)
- Roscoe, A.W. "The Theory and Practice of Concurrency" (1998)
- Schneider, S. "Concurrent and Real-time Systems: The CSP Approach" (1999)

---

## Algebraic Laws

### Overview

CSP operators satisfy algebraic laws that enable equational reasoning about processes. These laws form the foundation for process refinement and verification.

---

### 1. Parallel Composition Laws

#### Associativity of Parallel
```
(P || Q) || R = P || (Q || R)
```
*Parallel composition groups arbitrarily. Three concurrent processes can be parenthesized either way without changing behavior.*

**Implication for Agents:** Spawning order in swarms is irrelevant - `(A || B) || C` behaves the same as `A || (B || C)`.

#### Commutativity of Parallel
```
P || Q = Q || P
```
*Order of parallel processes is irrelevant. Symmetry in concurrent execution.*

**Implication for Agents:** In Map-Reduce, the order of mappers doesn't affect the parallel composition.

#### Identity for Parallel (Interleaving)
```
P ||| SKIP = P
SKIP ||| P = P
```
*SKIP is identity for interleaving. A process that does nothing and terminates doesn't affect composition.*

#### Zero for Parallel (Synchronizing)
```
P || STOP = STOP    (when STOP's alphabet intersects P's)
```
*STOP (deadlock) propagates through synchronizing parallel - if one process deadlocks on shared events, composition deadlocks.*

#### Interleaving Associativity and Commutativity
```
(P ||| Q) ||| R = P ||| (Q ||| R)
P ||| Q = Q ||| P
```
*True parallelism (no sync) is both associative and commutative.*

---

### 2. Sequential Composition Laws

#### Associativity of Sequential
```
(P ; Q) ; R = P ; (Q ; R)
```
*Sequential composition is associative. Grouping doesn't affect execution order.*

**Implication for Pipelines:** `(Stage1 ; Stage2) ; Stage3 = Stage1 ; (Stage2 ; Stage3)`

#### Left Identity
```
SKIP ; P = P
```
*SKIP followed by P is just P. SKIP terminates immediately, passing control.*

#### Right Identity
```
P ; SKIP = P
```
*P followed by SKIP is just P (assuming P terminates).*

#### Zero Element (Left)
```
STOP ; P = STOP
```
*STOP absorbs everything after it. Deadlock prevents continuation.*

#### Non-Commutativity
```
P ; Q =/= Q ; P    (in general)
```
*Sequential composition is NOT commutative. Order fundamentally matters.*

**Implication for Pipelines:** Cannot swap pipeline stages arbitrarily.

#### Prefix and Sequential
```
(a -> P) ; Q = a -> (P ; Q)    (when P terminates with SKIP)
```
*Prefix distributes into sequential when followed by termination.*

---

### 3. External Choice Laws

#### Associativity
```
(P [] Q) [] R = P [] (Q [] R)
```
*Choice groups arbitrarily.*

#### Commutativity
```
P [] Q = Q [] P
```
*Order of alternatives is irrelevant to external observer.*

#### Idempotence
```
P [] P = P
```
*Choosing between same process yields that process.*

#### Identity (STOP)
```
P [] STOP = P
```
*STOP is identity for external choice. Choosing between P and deadlock gives P.*

#### Zero (Special Case)
```
CHAOS [] P = CHAOS    (in some semantics)
```
*CHAOS (arbitrary behavior) absorbs choice.*

#### Choice-Prefix Interaction
```
(a -> P) [] (b -> Q) = (a -> P) [] (b -> Q)    (a =/= b: resolved by first event)
(a -> P) [] (a -> Q) = a -> (P |~| Q)          (same initial: becomes internal choice)
```
*When same event guards both branches, external choice degrades to internal choice.*

---

### 4. Internal Choice Laws

#### Associativity
```
(P |~| Q) |~| R = P |~| (Q |~| R)
```

#### Commutativity
```
P |~| Q = Q |~| P
```

#### Idempotence
```
P |~| P = P
```

#### Absorption into External Choice
```
P [] (P |~| Q) = P |~| Q
(P |~| Q) [] Q = P |~| Q
```
*External choice does NOT absorb internal choice - nondeterminism persists.*

#### Distributivity (Choice over Prefix)
```
a -> (P |~| Q) = (a -> P) |~| (a -> Q)
```
*Prefix distributes over internal choice.*

---

### 5. Distributivity Laws

#### Parallel over External Choice (Conditional)
```
P || (Q [] R) = (P || Q) [] (P || R)
```
*Holds when Q and R offer the same initial events in P's synchronization set.*

**Caveat:** This law has restrictions based on initial event sets.

#### Sequential Does NOT Distribute over Choice
```
P ; (Q [] R) =/= (P ; Q) [] (P ; R)
```
*Choice is resolved by environment AFTER P terminates, not before.*

**Implication:** Pipeline cannot distribute over router decisions made downstream.

#### Hiding over External Choice
```
(P [] Q) \ A = (P \ A) [] (Q \ A)
```
*Hiding distributes over external choice.*

#### Hiding Does NOT Distribute over Parallel
```
(P || Q) \ A =/= (P \ A) || (Q \ A)    (in general)
```
*Hiding shared synchronization events changes behavior fundamentally.*

**Why:** If `a` is in `A` and both P and Q sync on `a`, hiding it makes internal progress. Hiding individually breaks the synchronization.

#### Interleaving over Choice
```
(P [] Q) ||| R = (P ||| R) [] (Q ||| R)
```
*Interleaving distributes over external choice.*

---

### 6. Prefix Laws

#### Prefix Determinism
```
a -> P    (deterministic: exactly one initial event)
```

#### Prefix-Parallel Interaction
```
(a -> P) || (a -> Q) = a -> (P || Q)
```
*Synchronized prefix: both must engage, then parallel continues.*

#### Prefix-Interleave Interaction
```
(a -> P) ||| (b -> Q) = (a -> (P ||| (b -> Q))) [] (b -> ((a -> P) ||| Q))
```
*Interleaved prefix: environment chooses which happens first.*

---

### 7. Hiding Laws

#### Empty Set Identity
```
P \ {} = P
```

#### Composition (Union)
```
P \ A \ B = P \ (A union B)
```
*Multiple hidings combine.*

#### Distribution over Choice
```
(P [] Q) \ A = (P \ A) [] (Q \ A)
(P |~| Q) \ A = (P \ A) |~| (Q \ A)
```

#### Hiding and Sequential
```
(P ; Q) \ A = (P \ A) ; (Q \ A)    (when A does not affect termination)
```

---

### 8. Recursion Laws

#### Fixed Point Unfolding
```
mu X . F(X) = F(mu X . F(X))
```
*A recursive definition can be unfolded once.*

#### Unique Fixed Point (Guardedness)
```
If F is guarded, then X = F(X) has a unique solution.
```
*Guardedness: every recursive call is prefixed by at least one event.*

#### Recursion-Parallel
```
mu X . (P(X) || Q) = (mu X . P(X)) || Q    (when Q has no X)
```

---

### 9. Refinement Laws

Refinement (`[=`) means "implements correctly" - P [= Q means Q refines P.

#### Transitivity
```
P [= Q  and  Q [= R  implies  P [= R
```

#### Monotonicity for Parallel
```
P [= Q  implies  P || R [= Q || R
```

#### Monotonicity for Sequential
```
P [= Q  implies  P ; R [= Q ; R
R ; P [= R ; Q  (when R terminates)
```

#### Monotonicity for Choice
```
P [= Q  implies  P [] R [= Q [] R
```

#### Monotonicity for Hiding
```
P [= Q  implies  P \ A [= Q \ A
```

---

### Summary: Algebraic Structure

| Operator | Associative | Commutative | Idempotent | Identity | Zero |
|----------|-------------|-------------|------------|----------|------|
| `\|\|` (sync) | Yes | Yes | No | - | STOP |
| `\|\|\|` (interleave) | Yes | Yes | No | SKIP | - |
| `;` (seq) | Yes | **No** | No | SKIP | STOP |
| `[]` (ext choice) | Yes | Yes | Yes | STOP | - |
| `\|~\|` (int choice) | Yes | Yes | Yes | - | - |

---

### Key Laws for Pattern Composition

**For Swarm/Map-Reduce (Parallel):**
- Associativity: nest arbitrarily
- Commutativity: order irrelevant

**For Pipeline (Sequential):**
- Associativity: refactor stages freely
- Non-commutativity: order matters

**For Router (Choice):**
- Idempotence: duplicate branches collapse
- STOP as identity: dead branches eliminated

**For Encapsulation (Hiding):**
- Distributes over choice: hide after routing
- Does NOT distribute over parallel: hide at composition boundary

---

## Relevance to Pattern Composition

### Mapping CSP Laws to Multi-Agent Patterns

Based on the algebraic laws above, here's how they apply to our pattern composition:

| CSP Operator | Agent Pattern | Key Algebraic Properties |
|--------------|---------------|--------------------------|
| `P \|\| Q` | Swarm, Map-Reduce | Associative, Commutative |
| `P ; Q` | Pipeline, Hierarchical | Associative, NOT Commutative |
| `P [] Q` | Router (external) | Commutative, Idempotent |
| `P \|~\| Q` | Load Balancer (internal) | Commutative, Idempotent |
| `P \|\|\| Q` | Independent Workers | Associative, Commutative |
| `P \ A` | Encapsulation | Distributes over choice |

### Composition Algebra for Patterns

```csp
-- Swarm is commutative monoid under |||
Swarm(A, B) = Swarm(B, A)                           -- commutativity
Swarm(Swarm(A, B), C) = Swarm(A, Swarm(B, C))       -- associativity

-- Pipeline is non-commutative monoid under ;
Pipeline(A, Pipeline(B, C)) = Pipeline(Pipeline(A, B), C)  -- associativity
Pipeline(A, NoOp) = A                                       -- right identity
Pipeline(NoOp, A) = A                                       -- left identity
Pipeline(A, B) =/= Pipeline(B, A)                           -- NOT commutative

-- Router is idempotent commutative under []
Route(A, B) = Route(B, A)                           -- commutativity
Route(A, A) = A                                     -- idempotence
Route(A, DeadEnd) = A                               -- STOP as identity
```

### Key Insights for Pattern Algebra

1. **Parallel patterns (Swarm, Map-Reduce) form a commutative monoid**
   - Order of spawning doesn't matter
   - Can nest arbitrarily: `(A || B) || C = A || (B || C)`
   - SKIP is identity for interleaving

2. **Sequential patterns (Pipeline) form a non-commutative monoid**
   - Can refactor grouping: `(A ; B) ; C = A ; (B ; C)`
   - Cannot swap order: `A ; B =/= B ; A`
   - SKIP is identity, STOP is zero

3. **Choice patterns are idempotent**
   - Duplicate alternatives collapse: `A [] A = A`
   - STOP is identity for external choice

4. **Hiding provides encapsulation but doesn't distribute over parallel**
   - Internal communications hidden from parent
   - Must hide at composition boundary, not component level

5. **Refinement is monotonic**
   - Improving a component improves the whole system
   - Enables compositional verification

### CSP Models for 12 Agent Patterns

```csp
-- 1. Pipeline: Sequential composition
Pipeline(A, B, C) = A ; B ; C

-- 2. Swarm: Interleaved independent agents
Swarm(A, B, C) = A ||| B ||| C

-- 3. Hierarchical: Coordinator parallel with workers
Hierarchical(Coord, Workers) =
  Coord [| {assign, report} |] (||| i : Workers @ Worker(i))

-- 4. Jury: Parallel then aggregate
Jury(A, B, C) = (A ||| B ||| C) ; Aggregate

-- 5. Generator-Critic: Sequential loop
GenCrit(G, C) =
  mu X . (G ; C ; (accept -> SKIP [] reject -> X))

-- 6. Map-Reduce: Fan-out then aggregate
MapReduce(Mapper, Reducer) =
  (||| i : Items @ Mapper(i)) ; Reducer

-- 7. Circuit Breaker: Interrupt on failure
CircuitBreaker(P, Fallback) = P /\ (fail -> Fallback)

-- 8. Consensus: All must agree
Consensus(Agents) =
  (||| i : Agents @ vote(i) -> SKIP) ; verify

-- 9. Broadcast: One to many
Broadcast(Sender, Receivers) =
  Sender [| {msg} |] (||| i : Receivers @ Recv(i))

-- 10. Aggregator: Many to one
Aggregator(Senders, Collector) =
  (||| i : Senders @ Send(i)) [| {result} |] Collector

-- 11. Event-Driven: React to external events
EventDriven(Handler) =
  mu X . ((event -> Handler ; X) [] (stop -> SKIP))

-- 12. Chain of Responsibility: Try handlers in order
Chain(H1, H2, H3) =
  H1 ; ((handled -> SKIP) [] (pass -> H2 ; ((handled -> SKIP) [] (pass -> H3))))
```

---

## References

- Hoare, C.A.R. (1985). *Communicating Sequential Processes*. Prentice Hall.
- Roscoe, A.W. (1998). *The Theory and Practice of Concurrency*. Prentice Hall.
- Schneider, S. (2000). *Concurrent and Real-Time Systems: The CSP Approach*. Wiley.
- FDR4 Manual: https://www.cs.ox.ac.uk/projects/fdr/
