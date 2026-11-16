# Blackboard: Communication and Mobile Systems (Milner) - Pi-calculus

## Context
Extracting composition patterns for multi-agent workflows.
Focus: Mobile processes, scope extrusion, name passing.

---

## Composition Operators

### 1. Parallel Composition (`P | Q`)

**Syntax:**
```
P | Q
```

**Semantics:**
- Processes P and Q execute concurrently
- Can communicate via shared channels
- Independent actions interleave non-deterministically
- Communication happens when one process sends on a channel another is receiving on

**Inference Rules:**
```
      P --a--> P'
    ---------------  (PAR-L)
    P|Q --a--> P'|Q

      Q --a--> Q'
    ---------------  (PAR-R)
    P|Q --a--> P|Q'

    P --x(y)--> P'   Q --x<z>--> Q'
    --------------------------------  (COM)
         P|Q --tau--> P'{z/y}|Q'
```

**Laws:**
- Commutativity: `P | Q = Q | P`
- Associativity: `(P | Q) | R = P | (Q | R)`
- Identity: `P | 0 = P` (where 0 is the nil process)

**Relevance to Agents:**
- Maps to **Swarm pattern**: agents running in parallel, coordinating via channels
- Maps to **Map-Reduce**: fan-out workers with parallel composition

---

### 2. Restriction / New (`(nu x)P` or `(new x)P`)

**Syntax:**
```
(nu x)P    or    (new x)P    or    (vx)P
```

**Semantics:**
- Creates a fresh, private channel name `x`
- Name `x` is only visible within scope of P
- Enables private communication between sub-processes
- Critical for **scope extrusion** (mobility of names)

**Inference Rules:**
```
        P --a--> P'        (x not in a)
      -----------------------  (RES)
      (nu x)P --a--> (nu x)P'

        P --x(y)--> P'
      ---------------------  (OPEN)
      (nu y)P --x<y>--> P'
```

**Laws:**
- Scope narrowing: `(nu x)0 = 0`
- Scope extrusion: `(nu x)(P|Q) = P|(nu x)Q` if `x` not free in P
- Alpha equivalence: bound names can be renamed

**Relevance to Agents:**
- Maps to **private channels** between agent pairs
- Maps to **session isolation**: each agent session has private state
- Critical for **handoff patterns**: scope extrusion = passing private refs

---

### 3. Replication (`!P`)

**Syntax:**
```
!P
```

**Semantics:**
- Infinite parallel copies of P
- `!P = P | !P` (structural congruence)
- Models servers that can handle unlimited concurrent requests
- Always available to spawn new instances

**Inference Rule:**
```
     !P|P --a--> Q
    ---------------  (REP)
      !P --a--> Q
```

**Laws:**
- Unfolding: `!P = P | !P`
- `!(P|Q) = !P | !Q` (distributivity over parallel)

**Relevance to Agents:**
- Maps to **server patterns**: always-available responders
- Maps to **agent pools**: infinite worker availability
- Maps to **Circuit Breaker recovery**: respawn failed agents

---

### 4. Input Prefix (`x(y).P`)

**Syntax:**
```
x(y).P
```

**Semantics:**
- Receive a name on channel x, bind it to y, then continue as P
- The received name substitutes for y in P
- Blocking: waits until message available
- The `y` is a **bound name** (binding occurrence)

**Inference Rule:**
```
--------------------------  (INPUT)
x(y).P --x(y)--> P
```

**Relevance to Agents:**
- Maps to **message receive**: agent blocks waiting for input
- Maps to **request handling**: receive task, process it
- The `y` binding = dynamic task/data routing

---

### 5. Output Prefix (`x<z>.P`)

**Syntax:**
```
x<z>.P    or    x_bar<z>.P    or    x!z.P
```

**Semantics:**
- Send name z on channel x, then continue as P
- Synchronous: blocks until receiver ready
- Name `z` can be a channel itself (name passing = mobility)
- Both `x` and `z` are **free names**

**Inference Rule:**
```
--------------------------  (OUTPUT)
x<z>.P --x<z>--> P
```

**Relevance to Agents:**
- Maps to **message send**: dispatch work to other agents
- Maps to **handoff**: pass reference to another agent
- Passing channels = **delegation** (give agent access to resource)

---

### 6. Choice / Summation (`P + Q`)

**Syntax:**
```
P + Q
```

**Semantics:**
- External choice: environment determines which branch
- Once one branch commits (performs an action), other is discarded
- Guarded choice: typically `a.P + b.Q` (prefixed)
- Non-deterministic if guards overlap

**Inference Rules:**
```
    P --a--> P'
  ---------------  (SUM-L)
  P+Q --a--> P'

    Q --a--> Q'
  ---------------  (SUM-R)
  P+Q --a--> Q'
```

**Laws:**
- Commutativity: `P + Q = Q + P`
- Associativity: `(P + Q) + R = P + (Q + R)`
- Identity: `P + 0 = P`
- Idempotence: `P + P = P`

**Relevance to Agents:**
- Maps to **first-responder patterns**: race between handlers
- Maps to **timeout + fallback**: try one, fallback to other
- Maps to **Circuit Breaker**: try primary, else backup

---

### 7. Match / Conditional (`[x=y]P`)

**Syntax:**
```
[x=y]P
```

**Semantics:**
- If names x and y are equal, behave as P
- Otherwise, behave as 0 (nil/stuck)
- Enables conditional routing based on identity
- Some variants include mismatch: `[x!=y]P`

**Inference Rule:**
```
------------------  (MATCH)
[x=x]P --tau--> P
```

**Relevance to Agents:**
- Maps to **routing logic**: dispatch based on message type
- Maps to **access control**: only proceed if credentials match
- Critical for **pattern matching** in message handlers

---

### 8. Nil Process (`0`)

**Syntax:**
```
0
```

**Semantics:**
- The inactive process
- Cannot perform any action
- Identity element for parallel composition and choice

**Laws:**
- `P | 0 = P`
- `P + 0 = P`
- `(nu x)0 = 0`

**Relevance to Agents:**
- Maps to **terminated agent**: work complete
- Maps to **no-op handler**: do nothing

---

## Scope Extrusion & Restriction

### Core Concept: The Restriction Operator

In the Pi-calculus, **restriction** (also called "new name" or "private channel") is written:

```
(new x) P
```

or in some notations:

```
(vx) P
```

This creates a **fresh, private name `x`** whose scope is limited to process `P`. Initially, `x` is known only within `P` and cannot be observed or used by the external environment.

### Bound Names vs Free Names

**Free names** `fn(P)` - names that appear in `P` and are not bound by any restriction:
- Can be observed by the environment
- Available for synchronization
- Example: In `x<y>.P`, both `x` (channel) and `y` (message) are free if not restricted

**Bound names** `bn(P)` - names introduced by restriction or input binding:
- Private to their scope
- Cannot be directly observed
- Example: In `(new x) P`, the name `x` is bound

### Scope Extrusion: The Key Innovation

**Scope extrusion** is the mechanism by which a private name can escape its original scope through communication. This is THE distinguishing feature of the Pi-calculus versus CCS or CSP.

#### The Extrusion Rule

When a process sends a private name to another process:

```
(new x)(P | Q)  -->  (new x) P' | Q'   [if x communicated from P to Q]
```

More precisely, if:
- `P = a<x>.P'` (P sends x on channel a)
- `Q = a(y).Q'` (Q receives on channel a)
- `x` is restricted by `(new x)`

Then after the communication:
```
(new x)(a<x>.P' | a(y).Q')  -->  (new x)(P' | Q'{x/y})
```

The scope of `(new x)` has **extruded** to now cover both `P'` and `Q'{x/y}`.

#### Example: Private Channel Sharing

```
(new secret)(
    Alice: a<secret>.Alice'
  | Bob: a(ch).ch<msg>.Bob'
  | Carol: a(ch).ch(m).Carol'
)
```

1. Alice sends `secret` to Bob on public channel `a`
2. Scope extrudes: now Bob knows `secret`
3. Alice sends `secret` to Carol on channel `a`
4. Scope extrudes further: now Carol also knows `secret`
5. Bob and Carol can now communicate privately on `secret`

The scope of `(new secret)` has grown from just Alice to encompass Alice, Bob, and Carol.

### Structural Congruence Rules for Scope

The Pi-calculus defines structural congruence (`===`) rules that govern scope:

**Scope Narrowing:**
```
(new x)(P | Q) === P | (new x)Q    [if x not in fn(P)]
```
If P doesn't use x, the restriction can be pushed to only cover Q.

**Scope Widening (Extrusion Prerequisite):**
```
P | (new x)Q === (new x)(P | Q)    [if x not in fn(P)]
```
Scope can expand to cover more processes (alpha-renaming if needed).

**Restriction Swap:**
```
(new x)(new y)P === (new y)(new x)P
```
Order of restrictions doesn't matter.

**Restriction on Nil:**
```
(new x)0 === 0
```
Restricting nothing is nothing.

### Mobility: The Essence

The key insight is that **channel names can be passed as data**. In:

```
x<y>.P
```

The name `y` is sent as data on channel `x`. If `y` is a restricted (private) name, this constitutes **link passing** - the recipient now has a link (channel) they didn't have before.

This enables:
- **Dynamic topology**: Communication structure changes at runtime
- **Scope mobility**: Private names move between processes
- **Delegation**: One process can delegate its private channels to another

### The Open Transition Rule

Formally, scope extrusion is captured by the OPEN rule:

```
         P --a(x)--> P'    [x bound in output]
   ----------------------------------- [OPEN]
   (new x)P --a<x>--> P'   [x now free in label]
```

When a restricted name is output, the restriction "opens" and the name becomes visible (extruded) in the transition label.

### Agent Scope Application

For multi-agent workflows, scope extrusion maps directly to:

1. **Private Channels as Agent-to-Agent Links**
   - `(new ch)(Agent1 | Agent2)` - private communication
   - When Agent1 shares `ch` with Agent3, scope extends

2. **Dynamic Coordination**
   - Agents can establish new private channels at runtime
   - A coordinator can pass private channels to workers
   - Workers can share channels without coordinator involvement

3. **Capability Passing**
   - Names represent capabilities (access rights)
   - Scope extrusion = capability delegation
   - Once extruded, capability cannot be "taken back"

4. **Task Context Propagation**
   - Private task ID or context can be extruded to sub-agents
   - All agents sharing the context can coordinate
   - Context scope grows as tasks are delegated

### Formal Definition of Free/Bound Names

```
fn(0) = {}                           -- nil process
fn(x<y>.P) = {x,y} U fn(P)           -- output
fn(x(y).P) = {x} U (fn(P) \ {y})     -- input (y becomes bound)
fn(P|Q) = fn(P) U fn(Q)              -- parallel
fn((new x)P) = fn(P) \ {x}           -- restriction (x becomes bound)
fn(!P) = fn(P)                        -- replication
fn(P+Q) = fn(P) U fn(Q)              -- choice (if present)

bn(0) = {}
bn(x<y>.P) = bn(P)
bn(x(y).P) = {y} U bn(P)             -- y is bound by input
bn(P|Q) = bn(P) U bn(Q)
bn((new x)P) = {x} U bn(P)           -- x is bound by restriction
bn(!P) = bn(P)
bn(P+Q) = bn(P) U bn(Q)
```

### Key Property: Scope Extrusion is Monotonic

Once a name escapes its original scope, it cannot be "un-extruded." This is analogous to:
- Information that has been shared cannot be unshared
- Capabilities that have been delegated cannot be revoked (in pure Pi-calculus)
- Agent context, once propagated, persists

---

## Algebraic Laws

### Structural Congruence (`===`)

Structural congruence is the smallest equivalence relation closed under all Pi-calculus operators satisfying:

#### 1. Alpha-Equivalence (Bound Name Renaming)
```
(nu x)P === (nu y)P{y/x}        if y not free in P
x(z).P === x(w).P{w/z}          if w not free in P
```
Bound names can be freely renamed without changing process meaning.

#### 2. Parallel Composition (Abelian Monoid)
```
P | Q === Q | P                  (commutativity)
(P | Q) | R === P | (Q | R)      (associativity)
P | 0 === P                      (identity)
```
Parallel composition forms a commutative monoid with nil as identity.

#### 3. Summation / Choice
```
P + Q === Q + P                  (commutativity)
(P + Q) + R === P + (Q + R)      (associativity)
P + 0 === P                      (identity)
P + P === P                      (idempotence)
```

#### 4. Restriction
```
(nu x)(nu y)P === (nu y)(nu x)P  (scope exchange)
(nu x)0 === 0                     (scope garbage collection)
(nu x)(P | Q) === P | (nu x)Q     if x not in fn(P) (scope extrusion)
```

#### 5. Replication
```
!P === P | !P                    (unfolding - fundamental law)
!0 === 0                          (replicated nil)
!!P === !P                        (idempotence of replication)
```

---

### Behavioral Equivalences

#### Strong Bisimulation (~)

**Definition:** A symmetric relation R on processes is a **strong bisimulation** if whenever P R Q:
- If P --a--> P', then there exists Q' such that Q --a--> Q' and P' R Q'

Two processes are **strongly bisimilar** (P ~ Q) if they are related by some strong bisimulation.

**Properties:**
```
~ is an equivalence relation (reflexive, symmetric, transitive)
~ is a congruence (preserved by all operators)
P ~ Q  implies  fn(P) = fn(Q)
```

**Strong Bisimulation Laws:**
```
P | 0 ~ P                        (parallel identity)
P | Q ~ Q | P                    (parallel commutativity)
(P | Q) | R ~ P | (Q | R)        (parallel associativity)
!P ~ P | !P                      (replication unfolding)
(nu x)0 ~ 0                      (restriction identity)
```

#### Weak Bisimulation / Observational Equivalence (~~)

Abstracts away internal (tau) actions. Let:
- `===>` denote zero or more tau transitions
- `--a==>` denote `===> --a--> ===>`

**Definition:** A symmetric relation R is a **weak bisimulation** if whenever P R Q:
- If P --a--> P' (a visible), then Q --a==> Q' and P' R Q'
- If P --tau--> P', then Q ===> Q' and P' R Q'

**Tau Laws (valid under weak bisimulation):**
```
tau.P ~~ P                       (tau absorption)
a.tau.P ~~ a.P                   (tau after visible action)
P + tau.P ~~ tau.P               (tau dominates choice)
```

**Observational Equivalence Properties:**
- Coarser than strong bisimulation (equates more processes)
- Still a congruence
- More practical for verification (ignores internal steps)

#### Barbed Congruence

**Definition:** Process P **barbs on x** (written P|x) if P can immediately output on channel x.

**Barbed Bisimulation:** R is a barbed bisimulation if whenever P R Q:
- P|x implies Q|x (and vice versa)
- P --tau--> P' implies Q ===> Q' and P' R Q'

**Barbed Congruence:** P and Q are barbed congruent if for all contexts C[], C[P] and C[Q] are barbed bisimilar.

---

### Late vs Early Bisimulation

Pi-calculus has two main semantics for input:

#### Early Semantics
- Input transition commits immediately to received value
- `P --x(y)--> P'` where y is instantiated
- Checking: for all names z, after substitution P'{z/y} must match Q'{z/y}

#### Late Semantics
- Input transition delays commitment (parametric in received value)
- `P --x(y)--> P'` where y remains a placeholder
- Checking: exists Q' such that for all z, P'{z/y} matches Q'{z/y}

**Relationship:**
```
Early bisimilarity implies Late bisimilarity
Late bisimilarity does NOT imply Early bisimilarity
```

Late bisimulation is coarser (equates more processes).

---

### Open Bisimulation (~o)

**Motivation:** Standard bisimulations don't respect all substitutions properly.

**Definition:** P ~o Q if for all substitutions sigma:
```
P.sigma ~ Q.sigma
```

**Properties:**
- Finer than early/late bisimulation
- Better algebraic properties (respects name equalities)
- Closed under substitution by definition
- Used in many verification tools

---

### Expansion Law

The **expansion law** characterizes interleaving of parallel processes with prefixes:

For guarded sums:
```
P = sum_i a_i.P_i
Q = sum_j b_j.Q_j
```

Their parallel composition expands to:
```
P | Q === sum_i a_i.(P_i | Q)           [P acts alone]
        + sum_j b_j.(P | Q_j)           [Q acts alone]
        + sum_{(i,j): a_i, b_j sync}    [P and Q communicate]
            tau.(P_i | Q_j)
```

**Example:**
```
x<v>.P | x(y).Q  ===  x<v>.(P | x(y).Q) + x(y).(x<v>.P | Q) + tau.(P | Q{v/y})
```

The expansion law is fundamental for proving bisimulation between different process representations.

---

### Congruence Properties

If P === Q (structural congruence) or P ~ Q (bisimulation), then:

```
a.P === a.Q                      (prefix congruence)
P | R === Q | R                  (parallel congruence)
(nu x)P === (nu x)Q              (restriction congruence)
P + R === Q + R                  (choice congruence)
!P === !Q                        (replication congruence)
[x=y]P === [x=y]Q                (match congruence)
```

**Closure under contexts:** For any context C[] (process with a hole):
```
P === Q  implies  C[P] === C[Q]
P ~ Q    implies  C[P] ~ C[Q]
```

---

### Summary: Law Categories

| Category | Key Laws | Purpose |
|----------|----------|---------|
| **Structural** | Alpha, monoid, scope | Syntactic equivalence |
| **Strong Bisim** | Step-by-step matching | Finest behavioral equiv |
| **Weak Bisim** | Tau abstraction | Practical verification |
| **Open Bisim** | Substitution closure | Name-respecting equiv |
| **Expansion** | Interleaving semantics | Parallel decomposition |
| **Congruence** | Context closure | Compositional reasoning |

---

## Relevance to Pattern Composition

### Mapping to 12 Agent Patterns

| Pi-Calculus | Agent Pattern | Mapping |
|-------------|---------------|---------|
| `P \| Q` | Swarm, Map-Reduce | Parallel agents |
| `(nu x)P` | Session isolation | Private channels |
| `!P` | Worker pool, Server | Infinite responders |
| `x(y).P` | Message receive | Blocking input |
| `x<z>.P` | Message send | Dispatch/handoff |
| `P + Q` | Circuit breaker, Race | First responder wins |
| `[x=y]P` | Router, Dispatcher | Pattern matching |

### Derived Operators for Agent Patterns

**Sequential composition (derived):**
```
P ; Q  =  (nu done)(P{done/exit} | done().Q)
```
Maps to Pipeline pattern: finish P, signal done, start Q.

**Conditional routing (derived):**
```
if b then P else Q  =  [b=true]P + [b=false]Q
```
Maps to Router pattern with boolean dispatch.

**Timeout (derived):**
```
P timeout t  =  P + delay(t).fallback
```
Maps to Circuit Breaker with timeout.

**Request-response (derived):**
```
RPC(req, resp) = req<data, resp>.(resp(result).P)
```
Maps to synchronous agent call with response channel.

### Composition Algebra Summary

| Operation | Pi-calculus | Agent Semantics |
|-----------|-------------|-----------------|
| Run together | `P \| Q` | Both agents active |
| Private channel | `(nu x)(P \| Q)` | Isolated communication |
| Replicated server | `!x(req).Handler` | Handle any number of requests |
| Race/first wins | `P + Q` | First to respond wins |
| Sequential | `P ; Q` (derived) | Q waits for P |
| Conditional | `[x=y]P` | Route based on match |

### Key Insights for Agent Algebra

1. **Scope = Isolation**: `(nu x)` creates isolated subsystems
2. **Mobility = Handoff**: Name passing enables dynamic delegation
3. **Replication = Resilience**: `!P` ensures service availability
4. **Choice = Fallback**: `P + Q` models fault tolerance
5. **Composition = Concurrent execution**: `P | Q` runs agents together
6. **Structural congruence = Refactoring freedom**: Can reorganize without changing behavior

### Bisimulation for Pattern Equivalence

Two pattern implementations are **equivalent** if bisimilar:
```
Pattern1 ~ Pattern2  implies  interchangeable in any context
```

This enables:
- Verifying refactored patterns preserve behavior
- Substituting one implementation for another
- Optimizing compositions without breaking correctness

### Open Questions

- How do bisimulation equivalences map to agent behavioral testing?
- Can scope extrusion model capability-based security?
- What's the equivalent of "deadlock freedom" for agent patterns?
- How to model agent failure/crash (not in pure pi-calculus)?

---

## Sources

- Milner, R. (1999). *Communicating and Mobile Systems: the Pi-Calculus*. Cambridge University Press.
- Sangiorgi, D. & Walker, D. (2001). *The Pi-Calculus: A Theory of Mobile Processes*. Cambridge University Press.
- Milner, R., Parrow, J., & Walker, D. (1992). "A Calculus of Mobile Processes, I and II". *Information and Computation*, 100(1):1-77.
