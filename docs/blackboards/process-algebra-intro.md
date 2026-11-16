# Blackboard: Introduction to Process Algebra

## Context
Extracting composition patterns for multi-agent workflows.
Focus: Foundational operators and semantics.

---

## Composition Operators

### Source
Research queries to Ragie API for: "process algebra sequential composition", "process algebra parallel operator", "process algebra choice operator", "ACP CCS operators"

**Note:** This section synthesizes canonical process algebra operator definitions from ACP, CCS, CSP, and pi-calculus literature.

### Core Operator Classes

Process algebras (ACP, CCS, CSP, pi-calculus) share a common set of composition operators. These operators form an algebra for building complex concurrent systems from simpler components.

---

### 1. Sequential Composition (Prefixing)

**Operators:**
- **ACP:** `a . P` or `a ; P` (action prefix)
- **CCS:** `a.P` (prefix)
- **CSP:** `a -> P` (prefix)
- **Pi-calculus:** `a(x).P` (input prefix), `a<v>.P` (output prefix)

**Semantics:**
- Perform action `a`, then continue as process `P`
- The most basic form of sequencing
- Creates causal dependency: `a` must complete before `P` begins

**Example:**
```
login.authenticate.access_resource.0
```
Means: login, then authenticate, then access resource, then terminate.

**Agent Application:**
```
receive_task -> plan -> execute -> report -> END
```

---

### 2. Parallel Composition

**Operators:**
- **ACP:** `P || Q` (parallel merge) or `P ||| Q` (left merge)
- **CCS:** `P | Q` (parallel)
- **CSP:** `P || Q` (alphabetized parallel) or `P ||| Q` (interleave)
- **Pi-calculus:** `P | Q` (parallel)

**Semantics:**
- **Interleaving:** Actions of P and Q are arbitrarily interleaved
- **Synchronization:** Shared actions must occur simultaneously
- **Independence:** Each component maintains its own state

**ACP variants:**
```
P || Q    -- merge: interleaving + communication
P ||| Q   -- left merge: P acts first, then merge
P | Q     -- communication merge: only synchronized actions
```

**CSP variants:**
```
P ||| Q       -- interleave: no synchronization
P || Q        -- alphabetized: synchronize on shared alphabet
P |[A]| Q     -- synchronized on set A only
```

**Agent Application:**
```
(research_agent ||| code_agent ||| test_agent)
-- All work independently, interleaved execution

(planner |[handoff]| executor)
-- Synchronize on handoff events only
```

---

### 3. Choice (Nondeterministic/Summation)

**Operators:**
- **ACP:** `P + Q` (alternative composition)
- **CCS:** `P + Q` (summation)
- **CSP:** `P [] Q` (external choice) or `P |~| Q` (internal choice)
- **Pi-calculus:** `P + Q` (summation)

**Semantics:**
- **External choice (CCS/ACP +):** Environment determines which branch via first action
- **Internal choice (CSP |~|):** Process decides nondeterministically
- Once a choice is made, the other branch is discarded

**External vs Internal:**
```
a.P + b.Q     -- External: if environment offers 'a', become P; if 'b', become Q
P |~| Q       -- Internal: process randomly chooses P or Q (unobservable)
```

**Guarded choice:**
```
a.P + b.Q     -- Both branches guarded by observable action
              -- More tractable than unguarded choice
```

**Agent Application:**
```
(user_query -> handle_query) [] (timeout -> abort)
-- External choice: respond to whichever event occurs first

(use_gpt4 |~| use_claude)
-- Internal choice: agent decides which LLM (user doesn't control)
```

---

### 4. Communication (Handshake/Rendezvous)

**Operators:**
- **ACP:** `a | b = c` (communication function, configurable)
- **CCS:** `a.P | ~a.Q --> tau.(P | Q)` (complementary actions synchronize)
- **CSP:** Synchronization on shared events
- **Pi-calculus:** `a<v>.P | a(x).Q --> P | Q[v/x]` (value passing)

**Semantics:**
- Two processes synchronize on complementary actions
- Results in internal (tau/silent) action or value transfer
- **ACP:** Communication is configurable via gamma function
- **CCS:** Uses co-names (`a` and `~a` or `a` and `a-bar`)
- **Pi-calculus:** Channel-based with value passing

**CCS communication:**
```
a.P | ~a.Q  -->  tau.(P | Q)
-- Process sends on 'a', other receives on '~a', both continue
```

**Pi-calculus communication:**
```
a<5>.P | a(x).Q  -->  P | Q[5/x]
-- Send 5 on channel a, receiver binds to x, substitutes 5
```

**Agent Application:**
```
(coordinator!task.wait_result) | (worker?task.process.coordinator!result)
-- Coordinator sends task, worker receives, processes, sends result back
```

---

### 5. Restriction (Hiding/Scoping)

**Operators:**
- **ACP:** `tau_I(P)` (abstraction) or `del_H(P)` (encapsulation)
- **CCS:** `P \ a` or `P \ {a,b,c}` (restriction)
- **CSP:** `P \ A` (hiding)
- **Pi-calculus:** `(nu a)P` or `(new a)P` (new name/restriction)

**Semantics:**
- Makes certain actions/names private to a process
- External observers cannot see or interact with restricted names
- Enables modularity and encapsulation

**CCS restriction:**
```
(a.P | ~a.Q) \ a  -- 'a' is now internal, only tau visible
```

**Pi-calculus scope:**
```
(nu session)(client<session> | server(session))
-- Fresh private channel 'session' created
```

**Scope extrusion:**
```
(nu a)(b<a>.P)  -- Private name 'a' can escape via channel 'b'
```

**Agent Application:**
```
(new private_context)(
  agent_a<private_context>.continue |
  agent_b(ctx).use_context
)
-- Private shared context between agents
```

---

### 6. Recursion and Replication

**Operators:**
- **ACP:** `X = a.X` (recursive equation)
- **CCS:** `rec X.P` or `fix X.P` (recursion)
- **CSP:** `P = a -> P` (recursive definition)
- **Pi-calculus:** `!P` (replication) or `rec X.P`

**Semantics:**
- **Recursion:** Process can refer to itself, enabling loops
- **Replication (!P):** Infinite parallel copies of P available
- Essential for modeling servers, persistent services

**Recursive process:**
```
Server = receive_request.process.respond.Server
-- Handles one request, then becomes Server again
```

**Replication:**
```
!Worker  ~  Worker | !Worker
-- Always another Worker available
```

**Agent Application:**
```
!request_handler
-- Unlimited concurrent request handling capacity

rec Loop.(receive_task -> process -> Loop)
-- Agent that continuously processes tasks
```

---

### 7. Renaming and Relabeling

**Operators:**
- **ACP:** Renaming function application
- **CCS:** `P[f]` where f is a relabeling function
- **CSP:** `P[[a <- b]]` (renaming)
- **Pi-calculus:** Substitution

**Semantics:**
- Systematically rename actions/channels
- Enables reuse of process definitions with different interfaces
- Preserves structure while changing names

**CCS relabeling:**
```
P[request/a, response/b]
-- Rename action 'a' to 'request', 'b' to 'response'
```

**Agent Application:**
```
GenericWorker[task/input, result/output]
-- Adapt generic worker to specific interface
```

---

### 8. Conditional/Matching

**Operators:**
- **ACP:** Conditional composition (various extensions)
- **CCS:** Not standard, added in extensions
- **Pi-calculus:** `[x=y]P` (match) or `if x=y then P else Q`

**Semantics:**
- Guard a process with a condition
- Process only proceeds if condition holds
- Enables data-dependent behavior

**Pi-calculus match:**
```
[token=valid]proceed.P + [token!=valid]reject.Q
-- Branch based on token validity
```

**Agent Application:**
```
[confidence > 0.8]respond.END + [confidence <= 0.8]escalate.END
-- Route based on confidence score
```

---

### 9. Timeout and Priority

**Operators (extensions):**
- **CSP:** `P timeout[t] Q` (timeout)
- **Priority extensions:** `P >t Q` (P has priority over Q)

**Semantics:**
- **Timeout:** If P doesn't act within time t, switch to Q
- **Priority:** When multiple actions possible, higher priority chosen

**Agent Application:**
```
(wait_for_response timeout[30s] fallback_handler)
-- If no response in 30s, use fallback
```

---

### Operator Summary Table

| Operator | Symbol(s) | Meaning | Agent Pattern |
|----------|-----------|---------|---------------|
| **Prefix** | `a.P`, `a->P` | Sequential | Pipeline stage |
| **Parallel** | `P\|Q`, `P\|\|\|Q` | Concurrent execution | Swarm, Map |
| **Choice** | `P+Q`, `P[]Q` | Alternative branches | Router |
| **Communication** | `a\|~a`, `a<v>\|a(x)` | Synchronization | Handoff |
| **Restriction** | `P\a`, `(nu a)P` | Private scope | Internal channels |
| **Recursion** | `rec X.P`, `!P` | Repetition/replication | Persistent agents |
| **Renaming** | `P[f]` | Interface adaptation | Agent wrapping |
| **Match** | `[x=y]P` | Conditional | Routing logic |
| **Timeout** | `P timeout Q` | Time-bounded | Circuit breaker |

---

## Scope & Abstraction

### Source
Research queries for: "process algebra abstraction", "process algebra encapsulation", "process algebra hiding", "process algebra renaming"

**Note:** Canonical process algebra scope mechanisms from CCS (Milner), CSP (Hoare), ACP (Bergstra & Klop), and Pi-calculus (Milner).

### Overview

Process algebras provide four primary mechanisms for scope and abstraction:

| Mechanism | Notation | Effect | Use Case |
|-----------|----------|--------|----------|
| Restriction/Hiding | `(nu a)P`, `P \ A` | Make actions internal | Private channels |
| Encapsulation | `delta_H(P)` | Block unsynced actions | Force handshakes |
| Abstraction | `tau_I(P)` | Replace with tau | Observational hiding |
| Renaming | `P[f]`, `rho_f(P)` | Substitute action names | Template instantiation |

### 1. Restriction (CCS) and Hiding (CSP)

**CCS Restriction**: `(nu a)P` or `P \ {a}`
- Makes action `a` private to process `P`
- External observers cannot synchronize on `a`
- Internal communications on `a` become tau (silent) steps

```
(nu a)(a.P | a_bar.Q)
  --> tau.(P | Q)    # sync happens internally, visible as tau
```

**CSP Hiding**: `P \ A` or `P hide A`
- Actions in set `A` become internal events
- Traces containing hidden actions are projected out
- Enables compositional refinement checking

```
(P ||| Q) \ {sync}
  = process where sync-events are invisible to environment
```

**Algebraic Laws**:
```
(nu a)(nu b)P = (nu b)(nu a)P           # Scope commutes
(nu a)(P | Q) = P | (nu a)Q  if a not free in P   # Scope narrowing
(nu a)0 = 0                              # Empty scope
P \ {} = P                               # Hide nothing
P \ A \ B = P \ (A union B)              # Hide composition
```

### 2. Encapsulation (ACP)

**Encapsulation Operator**: `delta_H(P)` where H is a set of actions
- Actions in H are BLOCKED entirely (become deadlock delta)
- Unlike hiding: these actions are NOT converted to tau
- Forces synchronization: standalone actions MUST find communication partners

```
delta_H(a.P) = delta        if a in H     # blocked -> deadlock
delta_H(a.P) = a.delta_H(P) if a not in H # preserved
delta_H(P + Q) = delta_H(P) + delta_H(Q)  # distributes over choice
delta_H(P . Q) = delta_H(P) . delta_H(Q)  # distributes over sequence
```

**Use Case**: In multi-agent patterns, encapsulation ensures protocol correctness:
- `handoff_send` action MUST sync with `handoff_receive`
- Standalone attempts deadlock rather than proceed incorrectly

**Key Difference from Hiding**:
| Operator | Unsync'd Action | Process Continues? |
|----------|-----------------|-------------------|
| Hiding `P \ A` | Becomes tau | Yes |
| Encapsulation `delta_H(P)` | Becomes delta | No (deadlock) |

### 3. Abstraction Operator (ACP with tau)

**Abstraction**: `tau_I(P)` where I is a set of actions
- Actions in I become tau (silent/internal steps)
- Unlike encapsulation: process CONTINUES (no deadlock)
- Creates observational abstraction for external viewers

```
tau_I(a.P) = tau.tau_I(P)   if a in I    # becomes silent step
tau_I(a.P) = a.tau_I(P)     if a not in I # unchanged
tau_I(tau.P) = tau.tau_I(P)               # tau preserved
tau_I(P + Q) = tau_I(P) + tau_I(Q)        # distributes over choice
```

**Use Case**: After agents synchronize internally, abstract away the sync:
- Internal coordination is hidden from orchestrator layer
- Simplifies observable behavior for higher-level reasoning

### 4. Renaming (CCS, CSP, ACP)

**CCS Relabeling**: `P[f]` where f: Act -> Act
- Systematically renames actions according to function f
- Preserves process structure, changes interface

**CSP Renaming**: `P[[a <- b]]` or `P[[f]]`
- Replaces action `a` with action `b` throughout P
- Enables component reuse with different interfaces

**ACP Renaming**: `rho_f(P)`
- Function-based renaming distributing over all operators

```
# CCS
(a.b.0)[c/a, d/b] = c.d.0

# CSP
(a -> b -> STOP)[[a <- start, b <- finish]]
  = start -> finish -> STOP

# ACP
rho_f(a.P) = f(a).rho_f(P)
rho_f(P + Q) = rho_f(P) + rho_f(Q)
rho_f(P | Q) = rho_f(P) | rho_f(Q)
```

**Use Case**: Agent templates instantiated with unique identifiers:
- "worker" template becomes "worker_1", "worker_2"
- Channel `task` becomes `task_1`, `task_2` per instance

### 5. Scope Extrusion (Pi-calculus)

**Unique to Pi-calculus**: Bound names can escape their lexical scope
- Names are first-class values that can be communicated
- Enables dynamic reconfiguration and mobility

```
(nu x)(x_bar<y>.P | x(z).Q)
  --> (nu x)(P | Q{y/z})

# But also: scope can extrude
(nu x)(a_bar<x>.P | a(z).Q)
  --> (nu x)(P | Q{x/z})    # x escapes to Q
```

**Scope Extrusion Laws**:
```
(nu x)(P | Q) ~ P | (nu x)Q   if x not free in P   # narrow scope
(nu x)(P | Q) ~ (nu x)P | Q   if x not free in Q   # narrow scope
# BUT if x sent from P to Q, scope expands to include both
```

**Use Case**: Dynamic channel creation for agent spawning:
- Parent creates private result channel `(nu result)`
- Sends `result` to child agent
- Child reports back on `result` channel
- Channel identity is mobile across agent boundaries

### Summary: Scope Mechanism Comparison

| Mechanism | Algebra | Effect on Action | Visible? | Blocks? |
|-----------|---------|------------------|----------|---------|
| Restriction | CCS | Internal tau | No | No |
| Hiding | CSP | Trace projected out | No | No |
| Encapsulation | ACP | Becomes deadlock | N/A | Yes |
| Abstraction | ACP_tau | Becomes tau | No | No |
| Renaming | All | Name substituted | Yes (new name) | No |
| Extrusion | Pi | Scope expands | Yes (mobile) | No |

### Multi-Agent Pattern Mapping

| Process Algebra Concept | Multi-Agent Pattern Application |
|-------------------------|--------------------------------|
| Restriction `(nu a)P` | Private coordinator-worker channels |
| Hiding `P \ A` | Hide internal workflow from orchestrator |
| Encapsulation `delta_H(P)` | Enforce handoff protocol (must sync) |
| Abstraction `tau_I(P)` | Collapse sync to single observable step |
| Renaming `P[f]` | Template instantiation with unique IDs |
| Scope extrusion | Dynamic result channels for spawned agents |

---

## Algebraic Laws

### Source
Research query to Ragie API for: "process algebra axioms", "process algebra laws", "ACP axioms", "process algebra equational"

**Note:** Below is the canonical process algebra axiom set from ACP (Algebra of Communicating Processes) literature.

### BPA (Basic Process Algebra) Axioms

The foundational axioms for sequential and choice composition:

| Axiom | Name | Law |
|-------|------|-----|
| A1 | Choice commutativity | `x + y = y + x` |
| A2 | Choice associativity | `(x + y) + z = x + (y + z)` |
| A3 | Choice idempotency | `x + x = x` |
| A4 | Sequential associativity | `(x . y) . z = x . (y . z)` |
| A5 | Sequential distributivity (right) | `(x + y) . z = x . z + y . z` |

### ACP (Algebra of Communicating Processes) Axioms

Extends BPA with parallelism and communication:

| Axiom | Name | Law |
|-------|------|-----|
| CM1 | Merge definition | `x \|\| y = x \|\|_ y + y \|\|_ x + x \| y` |
| CM2-CM9 | Left-merge axioms | (define `\|\|_` semantics) |
| C1-C3 | Communication axioms | (define `\|` merge semantics) |
| D1-D2 | Deadlock axioms | `delta + x = x`, `delta . x = delta` |
| E | Encapsulation | `tau_I(a) = a` if `a not in I` |

### Key Operators and Their Laws

**Sequential Composition (`.` or `;`)**
```
Associative: (P . Q) . R = P . (Q . R)
Unit: skip . P = P . skip = P
Zero: stop . P = stop
```

**Choice/Alternative (`+`)**
```
Commutative: P + Q = Q + P
Associative: (P + Q) + R = P + (Q + R)
Idempotent: P + P = P
Unit: stop + P = P
```

**Parallel Composition (`||`)**
```
Commutative: P || Q = Q || P
Associative: (P || Q) || R = P || (Q || R)
Unit: skip || P = P
Interleaving: a . P || b . Q = a . (P || b . Q) + b . (a . P || Q)
```

**Synchronization/Communication (`|`)**
```
Handshake: a! | a? = tau  (internal action)
Mismatch: a! | b? = delta  (deadlock, if a != b)
```

**Hiding/Abstraction (`tau_I`)**
```
tau_I(a) = tau  if a in I
tau_I(a) = a    if a not in I
tau_I(P + Q) = tau_I(P) + tau_I(Q)
tau_I(P . Q) = tau_I(P) . tau_I(Q)
```

**Restriction/Encapsulation (`\L`)**
```
(P \ L) removes actions in L from P's interface
Distributive over choice and sequence
```

### Tau Laws (Silent/Internal Actions)

| Law | Name | Equation |
|-----|------|----------|
| T1 | Tau prefix | `tau . P = P` (weak bisimulation) |
| T2 | Tau loop | `P + tau . P = tau . P` |
| T3 | Tau absorption | `a . (P + tau . Q) = a . (P + tau . Q) + a . Q` |
| B1 | Branching | `a . (tau . (P + Q) + Q) = a . (P + Q)` |
| B2 | Branching | `tau . (tau . P + Q) = tau . P + Q` |

### Expansion Law

The fundamental theorem that reduces parallel to sequential+choice:

```
P || Q = sum_{a in A(P)} a . (P' || Q)
       + sum_{b in A(Q)} b . (P || Q')
       + sum_{gamma(a,b)=c} c . (P' || Q')
```

Where `gamma` is the communication function.

### Recursion Axioms (RSP - Recursive Specification Principle)

```
If X = f(X) has a unique solution, then X = mu X . f(X)
RDP: X = t_X => X = <X | E>  (Recursive Definition Principle)
RSP: If Y = t_X[Y/X] then Y = <X | E>
```

### Congruence Laws

For any law to be useful, operators must be congruent with respect to the equivalence relation (bisimulation):

```
P ~ Q implies:
  - a . P ~ a . Q
  - P + R ~ Q + R
  - P || R ~ Q || R
  - P \ L ~ Q \ L
```

### Equational Theory Summary

| Algebra | Operators | Key Property |
|---------|-----------|--------------|
| BPA | `.`, `+` | Sequential processes |
| PA | `.`, `+`, `\|\|` | Interleaving parallelism |
| ACP | `.`, `+`, `\|\|`, `\|`, `delta` | Communication + deadlock |
| ACP_tau | + `tau`, `tau_I` | Silent actions |
| TCP | + timing | Real-time extensions |

---

## Relevance to Pattern Composition

### Mapping to Multi-Agent Patterns

| Process Algebra Operator | Agent Pattern | How It Maps |
|--------------------------|---------------|-------------|
| `a.P` (prefix) | **Pipeline** | Sequential stage execution |
| `P \| Q` (parallel) | **Swarm/Map** | Concurrent agents |
| `P + Q` (choice) | **Router** | Select handler based on input |
| `a\|~a` (communication) | **Handoff** | Agent-to-agent message passing |
| `(nu a)P` (restriction) | **Private channel** | Internal coordination |
| `!P` (replication) | **Scaling** | Stateless worker pool |
| `P timeout Q` | **Circuit breaker** | Fallback on timeout |
| `P [] Q` (external choice) | **Event router** | First event determines path |
| `delta_H(P)` (encapsulation) | **Protocol enforcement** | Ensure handoffs complete |
| `tau_I(P)` (abstraction) | **Observational hiding** | Collapse internal steps |

### Composition Algebra for Patterns

Based on process algebra, define pattern composition:

```
Pattern1 ; Pattern2     -- sequential (prefix composition)
Pattern1 || Pattern2    -- parallel (swarm)
Pattern1 + Pattern2     -- choice (router)
Pattern1 |[sync]| P2    -- synchronized parallel (pipeline with handoffs)
(new ch)(Pattern)       -- with private channel (internal coordination)
!Pattern                -- replicated (elastic scaling)
```

---

## Sources

### Primary References
- Milner, R. "Communication and Concurrency" (1989) - CCS reference
- Milner, R. "Communicating and Mobile Systems: The Pi-Calculus" (1999)
- Hoare, C.A.R. "Communicating Sequential Processes" (1985) - CSP reference
- Bergstra, J.A. & Klop, J.W. "Algebra of Communicating Processes" (ACP series, 1984-)
- Baeten, J.C.M. "A Brief History of Process Algebra" (2005) - survey paper

### Supplementary Research
- Category theory agents research (`.claude/cache/agents/research-agent/category-theory-agents.md`)
- Temporal logic agents research (`.claude/cache/agents/research-agent/temporal-logic-agents.md`)
- Distributed process algebra (`docs/blackboards/process-algebra-distributed.md`)
