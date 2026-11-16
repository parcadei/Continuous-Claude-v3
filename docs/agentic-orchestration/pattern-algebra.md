# Pattern Algebra for Multi-Agent Composition

> **Document Status: Design Specification**
>
> This document is a *prescriptive* design spec, not a *descriptive* implementation guide.
> Some sections describe existing behavior; others describe intended behavior not yet implemented.
>
> **Why this distinction matters (for future LLMs reading this):**
> Pattern-algebra.md was synthesized from 5 process algebra textbooks (CSP, Pi-calculus, ACP,
> distributed PA, algebra of programming) by 15 research agents in December 2025. The mathematical
> foundations are verified against source literature. However, the implementation in
> `scripts/agentica/` was built pragmatically before this formalization existed.
>
> The gap between spec and implementation is *intentional* - this document serves as the
> north star for making the codebase more rigorous. When you see `[ASPIRATIONAL]`, it means
> "correct by the math, not yet in the code."

A formal algebra for composing multi-agent patterns with scope annotations.

**Synthesized from:** CSP (Hoare), Pi-calculus (Milner), Algebra of Programming (Bird & de Moor), ACP/CCS foundations, and Distributed Process Algebra.

---

## 1. Operators

**[IMPLEMENTED]** - All operators are mathematically grounded and the algebraic laws are verified against source literature.

The pattern composition algebra unifies operators from process algebra into a coherent system for multi-agent workflows.

### 1.1 Sequential Composition

**Syntax:** `A ; B`

**Semantics:** Execute pattern A to completion, then execute pattern B. The output of A becomes available to B.

**Source:** CSP prefix (`a -> P`), ACP (`.`), Pi-calculus derived (`(nu done)(A{done/exit} | done().B)`)

**Laws:**
```
(A ; B) ; C = A ; (B ; C)     -- Associativity
SKIP ; A = A                   -- Left identity
A ; SKIP = A                   -- Right identity (when A terminates)
STOP ; A = STOP                -- Zero element (deadlock propagates)
```

**Pattern Usage:**
- Pipeline stages: `Stage1 ; Stage2 ; Stage3`
- Generator-Critic loop termination: `Generate ; Critique ; [accept -> SKIP [] reject -> loop]`

---

### 1.2 Parallel Composition

**Syntax:** `A | B`

**Semantics:** Execute patterns A and B concurrently. Events in the intersection of their alphabets synchronize; others interleave.

**Variants:**
```
A || B      -- Synchronized parallel (sync on shared alphabet)
A ||| B     -- Interleaving (no synchronization)
A |[S]| B   -- Sync on explicit set S only
```

**Source:** CSP (`||`, `|||`), CCS (`|`), Pi-calculus (`|`)

**Laws:**
```
A | B = B | A                   -- Commutativity
(A | B) | C = A | (B | C)       -- Associativity
A | 0 = A                       -- Identity (0 = nil process)
A || STOP = STOP                -- Zero for sync parallel (if alphabets overlap)
```

**Pattern Usage:**
- Swarm: `Agent1 ||| Agent2 ||| Agent3`
- Map phase: `Mapper1 ||| Mapper2 ||| Mapper3`
- Jury (independent voting): `Juror1 ||| Juror2 ||| Juror3`

---

### 1.3 Choice

**Syntax:** `A + B`

**External Choice (Deterministic):**
```
A [] B      -- Environment determines by first event
```

**Internal Choice (Nondeterministic):**
```
A |~| B     -- Process decides nondeterministically
```

**Conditional Choice:**
```
A <| b |> B -- If b then A else B
```

**Source:** CSP (`[]`, `|~|`), CCS/ACP (`+`), Pi-calculus (`+`)

**Laws:**
```
A + B = B + A                   -- Commutativity
(A + B) + C = A + (B + C)       -- Associativity
A + A = A                       -- Idempotence
A + STOP = A                    -- Identity (STOP offers nothing)
```

**Pattern Usage:**
- Router: `[TextAgent, ImageAgent, AudioAgent]`
- Circuit Breaker: `Primary [] Fallback`
- Chain of Responsibility: `Handler1 [] Handler2 [] Handler3`

---

### 1.4 Nesting

**Syntax:** `A(B)`

**Semantics:** Pattern A uses pattern B as an internal component. B operates within A's scope.

**Source:** Category theory functor composition, hierarchical process structures

**Laws:**
```
A(B(C)) = (A . B)(C)            -- Functor composition
A(SKIP) = A                     -- Identity pattern (when A expects result)
```

**Pattern Usage:**
- Hierarchical: `Coordinator(Swarm(Workers))`
- Pipeline with internal parallelism: `Pipeline(MapReduce(Mappers), Aggregator)`

---

### 1.5 Iteration

**Syntax:** `A*`

**Semantics:** Repeat pattern A zero or more times until termination condition.

**Source:** Kleene star, fixed points (mu F, nu F from Bird)

**Variants:**
```
A*          -- Zero or more repetitions
A+          -- One or more repetitions (= A ; A*)
mu X.F(X)   -- Least fixed point (finite iteration)
nu X.F(X)   -- Greatest fixed point (potentially infinite)
```

**Laws:**
```
A* = SKIP + (A ; A*)            -- Unfolding
(A*)* = A*                      -- Idempotence
SKIP* = SKIP                    -- Empty iteration
STOP* = SKIP                    -- Stop iterates zero times
```

**Pattern Usage:**
- Generator-Critic: `mu X.(Generate ; Critique ; [accept -> Result [] reject -> X])`
- Event-Driven: `nu X.(Event ; Handle ; X)`

---

### 1.6 Restriction

**Syntax:** `(nu x)A` or `A \ {x}`

**Semantics:** Create a private channel/scope visible only within A.

**Source:** Pi-calculus (`(nu x)P`), CCS restriction, CSP hiding

**Laws:**
```
(nu x)(nu y)A = (nu y)(nu x)A   -- Scope commutes
(nu x)0 = 0                      -- Empty restriction
(nu x)(A | B) = A | (nu x)B      -- Scope extrusion (if x not free in A)
```

**Pattern Usage:**
- Private coordinator-worker channel: `(nu task_ch)(Coordinator | Workers)`
- Session isolation: `(nu session)(Agent1 | Agent2)`

---

### 1.7 Hiding

**Syntax:** `A \ S`

**Semantics:** Events in set S become internal (tau). They still occur but cannot be observed externally.

**Source:** CSP hiding, ACP abstraction (`tau_I`)

**Laws:**
```
A \ {} = A                       -- Empty hiding is identity
A \ S \ T = A \ (S union T)      -- Hiding composition
(A [] B) \ S = (A \ S) [] (B \ S) -- Distributes over choice
```

**Note:** Hiding does NOT distribute over parallel:
```
(A || B) \ S =/= (A \ S) || (B \ S)
```
Hiding shared synchronization events changes behavior fundamentally.

**Pattern Usage:**
- Pipeline encapsulation: `(Stage1 \ internal) ; (Stage2 \ internal)`
- Jury deliberation hidden: `(Juror1 ||| Juror2 ||| Juror3) \ {deliberation}`

---

### 1.8 Renaming

**Syntax:** `A[[f]]` or `A[[a <- b]]`

**Semantics:** Apply function f to all event names in A. Enables interface adaptation.

**Source:** CSP renaming, CCS relabeling, ACP

**Laws:**
```
A[[id]] = A                      -- Identity renaming
(A[[f]])[[g]] = A[[g . f]]       -- Composition
A[[a <- a]] = A                  -- No-op rename
```

**Pattern Usage:**
- Worker template instantiation: `GenericWorker[[task <- task_1, result <- result_1]]`
- Interface adaptation: `ExternalAPI[[send <- dispatch, recv <- collect]]`

---

### 1.9 Replication

**Syntax:** `!A`

**Semantics:** Infinite parallel copies of A available. Models always-available services.

**Source:** Pi-calculus replication

**Laws:**
```
!A = A | !A                      -- Unfolding
!(A | B) = !A | !B               -- Distributes over parallel
!0 = 0                           -- Replicated nil
!!A = !A                         -- Idempotence
```

**Pattern Usage:**
- Worker pool: `!Worker`
- Server pattern: `!RequestHandler`

---

## 2. Scope Annotations

**[ASPIRATIONAL]** - The scope types (`[iso]`, `[shared]`, `[fed]`, `[handoff]`) are not yet exposed as explicit API parameters in `scripts/agentica/`. The `ScopeType` enum does not exist yet. Currently, scope behavior is implicit based on pattern choice rather than explicit annotation.

Derived from Pi-calculus scope extrusion and distributed process algebra locality.

### 2.1 Scope Types

| Annotation | Notation | Semantics | State Sharing |
|------------|----------|-----------|---------------|
| **Isolated** | `[iso]` | No shared state; private channels only | None |
| **Shared** | `[shared]` | SharedContext enabled; file cache shared | Read/write cache |
| **Federated** | `[fed]` | Cross-agent memory queries; archival search | Read-only query |
| **Handoff** | `[handoff]` | Sequential state transfer at boundaries | At transition |

### 2.2 Formal Scope Semantics

**Isolated Scope:**
```
[iso] A | B  =  (nu c)(A' | B')
    where A' uses c1, B' uses c2, c1 cap c2 = {}
```
No shared alphabet between agents. Complete independence.

**Shared Scope:**
```
[shared] A | B  =  A |[cache]| B
    where cache = {read, write, invalidate}
```
Agents synchronize on cache operations. SharedContext provides thread-safe access.

**Federated Scope:**
```
[fed] A | B  =  (nu query_ch)(A' | !Oracle | B')
    where Oracle = query_ch(q).answer(q).Oracle
```
Read-only access to shared memory via query channel.

**Handoff Scope:**
```
[handoff] A ; B  =  (nu done)(A' ; done<state>.0 | done(s).B'(s))
```
State explicitly passed at sequential boundary.

### 2.3 Scope Extrusion Rules

From Pi-calculus, scope can expand when private names are communicated:

```
Initial:     (nu x)(A)           -- x private to A
After send:  (nu x)(A' | B')     -- x now shared with B
```

**Extrusion Constraints:**
1. Names can only extrude outward (monotonic)
2. Once extruded, cannot be "un-extruded"
3. Extrusion preserves behavioral equivalence

**Agent Implications:**
- Private task IDs can be shared with sub-agents
- Capability delegation is one-way (cannot revoke)
- Context propagation is monotonic

### 2.4 Scope Compatibility Matrix

| From \ To | Isolated | Shared | Federated | Handoff |
|-----------|----------|--------|-----------|---------|
| **Isolated** | Yes | Widen | Widen | Yes |
| **Shared** | Narrow | Yes | Subset | Via snapshot |
| **Federated** | Subset | Widen | Yes | Query result |
| **Handoff** | Yes | Widen | Widen | Chain |

**Widen:** Scope expands to include new agents
**Narrow:** Must create copy (breaks sharing)
**Subset:** Read-only view of shared state

---

## 3. Algebraic Laws

**[IMPLEMENTED]** - These algebraic laws are mathematically grounded and verified against the source literature (CSP, Pi-calculus, ACP, Bird & de Moor).

### 3.1 Foundational Laws

**Sequential Monoid:**
```
(A ; B) ; C = A ; (B ; C)         -- Associativity
SKIP ; A = A = A ; SKIP           -- Identity
STOP ; A = STOP                   -- Zero (left)
```
Sequential composition forms a monoid with SKIP as identity. Non-commutative.

**Parallel Monoid:**
```
(A | B) | C = A | (B | C)         -- Associativity
A | B = B | A                     -- Commutativity
A | 0 = A                         -- Identity
```
Parallel composition forms a commutative monoid with nil as identity.

**Choice Semilattice:**
```
A + B = B + A                     -- Commutativity
(A + B) + C = A + (B + C)         -- Associativity
A + A = A                         -- Idempotence
A + STOP = A                      -- Identity
```
Choice forms an idempotent commutative monoid (join-semilattice).

### 3.2 Distributivity Laws

**Right Distribution of Sequential over Choice:**
```
(A + B) ; C = (A ; C) + (B ; C)
```
This is the ACP axiom A5.

**Sequential does NOT left-distribute over Choice:**
```
A ; (B + C) =/= (A ; B) + (A ; C)
```
Choice is resolved AFTER A completes.

**Parallel Distribution (conditional):**
```
A || (B + C) = (A || B) + (A || C)
    when B and C offer same initial events in A's sync set
```

**Hiding Distributes over Choice:**
```
(A + B) \ S = (A \ S) + (B \ S)
```

**Hiding does NOT Distribute over Parallel:**
```
(A || B) \ S =/= (A \ S) || (B \ S)
```
Shared synchronization events become internal together.

### 3.3 Fusion Laws (from Bird)

**Catamorphism Fusion:**
```
h . ([f]) = ([g])   <==   h . f = g . F(h)
```
Post-processing can be fused into a fold if the fusion condition holds.

**Banana-Split:**
```
([f]) /\ ([g]) = ([f /\ g . <F(fst), F(snd)>])
```
Two folds over the same structure can be computed in a single pass.

**Pattern Application:**
- Map-Reduce: Combine multiple aggregations into single reduce
- Swarm: Collect multiple metrics in one parallel sweep

### 3.4 Refinement Laws

Refinement (`[=`) means "correctly implements":
```
P [= Q  means Q refines (implements) P
```

**Transitivity:**
```
P [= Q  and  Q [= R  implies  P [= R
```

**Monotonicity:**
```
P [= Q  implies  P | R [= Q | R     -- Parallel
P [= Q  implies  P ; R [= Q ; R     -- Sequential
P [= Q  implies  P + R [= Q + R     -- Choice
P [= Q  implies  P \ S [= Q \ S     -- Hiding
```

### 3.5 Congruence Laws

For any equivalence relation (~), if P ~ Q:
```
a.P ~ a.Q                -- Prefix
P | R ~ Q | R            -- Parallel
(nu x)P ~ (nu x)Q        -- Restriction
P + R ~ Q + R            -- Choice
!P ~ !Q                  -- Replication
```

Equivalence is preserved by all contexts (compositional reasoning).

### 3.6 Recursion Laws

**Fixed Point Unfolding:**
```
mu X.F(X) = F(mu X.F(X))
```

**Unique Fixed Point (Guardedness):**
```
If F is guarded, then X = F(X) has a unique solution.
```
A functor is guarded if every recursive call is prefixed by at least one observable action.

**Replication as Fixed Point:**
```
!P = mu X.(P | X)
```

---

## 4. Pattern Composition Table

**[IMPLEMENTED]** - All 12 patterns exist in `scripts/agentica/patterns.py` and related modules.

| Pattern | Primary Op | Valid Compositions | Scope Requirement | Termination |
|---------|------------|-------------------|-------------------|-------------|
| **Pipeline** | `;` | Any sequential | `[handoff]` between stages | Finite (last stage) |
| **Swarm** | `\|\|\|` | Parallel only | `[iso]` or `[shared]` | Join barrier |
| **Jury** | `\|\|\|` ; Aggregate | Parallel then seq | `[iso]` (independence required) | All votes collected |
| **Hierarchical** | `\|[assign,report]\|` | Nested parallel | `[shared]` or `[fed]` | Coordinator decides |
| **Generator-Critic** | `;` with `mu` | Sequential loop | `[handoff]` per iteration | Acceptance condition |
| **Map-Reduce** | `\|\|\|` ; `;` | Parallel then aggregate | `[iso]` map, `[shared]` reduce | Reduce complete |
| **Adversarial** | `\|\|\|` ; Judge | Parallel debate | `[iso]` debate, `[handoff]` to judge | Judge verdict |
| **Circuit Breaker** | `+` (timeout) | Choice with fallback | `[handoff]` state transfer | Primary or fallback |
| **Chain of Responsibility** | `+` (cascade) | Sequential fallback | `[handoff]` on escalation | First handler succeeds |
| **Blackboard** | `\|[board]\|` | Shared state parallel | `[shared]` (central blackboard) | Convergence criterion |
| **Event-Driven** | `nu X.(event;handle;X)` | Reactive loop | `[fed]` event queries | External stop signal |
| **Broadcast** | `\|[msg]\|` | One-to-many sync | `[shared]` message channel | All receivers ack |

### 4.1 Composition Validity Predicate

**[ASPIRATIONAL]** - `CanCompose()` has no runtime implementation yet. This predicate is specified here but not enforced at runtime.

```
CanCompose(A, B, op, scope) <=>
    ScopeCompatible(A, B, scope)
  & NoDeadlock(A, B, op)
  & TerminationGuarantee(A op B, scope)
  & ResourceBounded(A op B)
```

**ScopeCompatible(A, B, scope):**
```
scope = [iso]    => alphabet(A) cap alphabet(B) = {}
scope = [shared] => SharedContext(A) = SharedContext(B)
scope = [fed]    => ReadOnly(B, SharedMemory(A))
scope = [handoff] => OutputType(A) compatible_with InputType(B)
```

**NoDeadlock(A, B, op):**
```
op = |   => NOT(MustSync(A, x) AND NOT(CanSync(B, x)))
op = ||  => alphabet(A) cap alphabet(B) != {required_sync} OR both_offer(required_sync)
op = ;   => Terminates(A)
```

**TerminationGuarantee(P, scope):**
```
Guarded(P)                           -- All recursion is guarded
OR Bounded(iterations)               -- Finite iteration count
OR HasExitCondition(P)               -- Explicit termination
```

---

## 5. Specialist Composition Matrix

**[IMPLEMENTED]** - The 6 specialists are defined and their composition constraints are enforced through the pattern implementations.

The 6 specialists have composition constraints based on their capabilities and scope requirements.

### 5.1 Specialist Profiles

| Specialist | Primary Op | Scope Preference | Stateful? | Can Lead? |
|------------|------------|------------------|-----------|-----------|
| **Finder** | Search | `[fed]` | No (query-only) | No |
| **Oracle** | Reason | `[iso]` | Yes (reasoning chain) | Yes |
| **Librarian** | Lookup | `[fed]` | No (cache-only) | No |
| **Kraken** | Refactor | `[shared]` | Yes (file state) | Yes |
| **Sentinel** | Review | `[iso]` | No (read-only) | Yes (for review) |
| **Hydra** | Branch | `[shared]` | Yes (git state) | Yes |

### 5.2 Valid Specialist Compositions

| Composition | Pattern | Valid? | Scope |
|-------------|---------|--------|-------|
| `Finder ; Oracle` | Pipeline | Yes | `[handoff]`: search results to reasoner |
| `Finder \|\|\| Librarian` | Swarm | Yes | `[fed]`: both query-only |
| `Oracle \|\|\| Oracle` | Jury | Yes | `[iso]`: independent reasoning |
| `Kraken ; Sentinel` | Pipeline | Yes | `[handoff]`: refactor then review |
| `Kraken \|\|\| Kraken` | Swarm | **No** | Conflict: both modify files |
| `Hydra(Swarm(Finder, Oracle))` | Hierarchical | Yes | `[shared]`: Hydra coordinates |
| `Sentinel ; Kraken` | Gen-Crit | Yes | `[handoff]`: review suggests, Kraken implements |

### 5.3 Composition Constraints

**Resource Conflicts:**
```
CanParallel(A, B) <=>
    NOT(Writes(A) cap Writes(B) != {})      -- No write-write conflict
  & NOT(Writes(A) cap Reads(B) != {} AND timing = concurrent)  -- No write-read race
```

**Capability Chain:**
```
ValidPipeline(A, B) <=>
    OutputCapability(A) subseteq InputCapability(B)
```

| From \ To | Finder | Oracle | Librarian | Kraken | Sentinel | Hydra |
|-----------|--------|--------|-----------|--------|----------|-------|
| **Finder** | - | Yes | Yes | Yes | Yes | Yes |
| **Oracle** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Librarian** | - | Yes | - | Yes | Yes | Yes |
| **Kraken** | - | Yes | - | No* | Yes | Yes |
| **Sentinel** | - | Yes | - | Yes | - | Yes |
| **Hydra** | Yes | Yes | Yes | Yes | Yes | - |

`*` Kraken cannot pipeline to Kraken (state interference)
`-` Typically not meaningful (no output to consume)

---

## 6. Validity Predicate (Complete)

**[ASPIRATIONAL]** - The complete validity predicate below has no runtime implementation yet. The `ScopeType` enum does not exist, and `CanCompose()` is not enforced at runtime.

```
CanCompose(A, B, scope) <=>
    ScopeCompatible(A, B, scope)
  & NoDeadlock(A, B)
  & TerminationGuarantee(A . B)
  & ResourceSafe(A, B)
  & CausallyConsistent(A, B)
```

### 6.1 ScopeCompatible

```
ScopeCompatible(A, B, [iso]) <=>
    fn(A) cap fn(B) = {}                    -- No shared free names

ScopeCompatible(A, B, [shared]) <=>
    CacheManager(A) = CacheManager(B)       -- Same SharedContext
  & LockProtocol(A, B)                      -- Thread-safe access

ScopeCompatible(A, B, [fed]) <=>
    QueryOnly(B, MemoryOf(A))               -- B can only read A's memory
  & NOT(Mutates(B, MemoryOf(A)))            -- No write access

ScopeCompatible(A, B, [handoff]) <=>
    OutputSchema(A) <= InputSchema(B)       -- Type-compatible handoff
  & Serializable(OutputOf(A))               -- Can be marshaled
```

### 6.2 NoDeadlock

```
NoDeadlock(A, B) <=>
    -- No circular wait
    NOT(Waits(A, channel_x) & Waits(B, channel_x) & NOT(Provides(A|B, channel_x)))
    -- No unmatched sync
  & (forall c in SyncSet(A|B). CanSync(A, c) OR CanSync(B, c))
    -- No resource starvation
  & (forall r in Resources(A|B). EventuallyAvailable(r))
```

### 6.3 TerminationGuarantee

```
TerminationGuarantee(P) <=>
    -- All loops have exit conditions
    (forall X in RecursiveVars(P).
       Guarded(X) & (BoundedIterations(X) OR ExitCondition(X)))
    -- No infinite internal computation
  & NOT(DivergentTau(P))
    -- Parallel components all terminate (for sync patterns)
  & (P = A || B  implies  TerminationGuarantee(A) & TerminationGuarantee(B))
```

### 6.4 ResourceSafe

```
ResourceSafe(A, B) <=>
    -- Memory bounded
    PeakMemory(A | B) <= MemoryLimit
    -- No concurrent writes to same resource
  & (forall r. NOT(ConcurrentWrite(A, r) & ConcurrentWrite(B, r)))
    -- File locks respected
  & (forall f. Write(A, f) & Write(B, f)  implies  Sequentialized(A, B, f))
```

### 6.5 CausallyConsistent

```
CausallyConsistent(A, B) <=>
    -- Happens-before respected
    (forall e1, e2. HappensBefore(e1, e2) implies Ordered(e1, e2))
    -- No causal cycles
  & AcyclicDependencies(A, B)
    -- Message ordering preserved (per channel)
  & (forall c. FIFO(MessageOrder(c)) OR Unordered(c))
```

---

## 7. CSP/Process Algebra Models for 12 Patterns

### 7.1 Pipeline

```csp
Pipeline(A, B, C) = A ; B ; C

-- With explicit handoffs
Pipeline_Handoff(A, B, C) =
    (A >> handoff1) ; (handoff1? >> B >> handoff2) ; (handoff2? >> C)
```

### 7.2 Swarm

```csp
Swarm(A, B, C) = A ||| B ||| C

-- With result collection
Swarm_Collect(Agents, Collector) =
    (||| i : Agents @ Agent(i)) [| {result} |] Collector
```

### 7.3 Hierarchical

```csp
Hierarchical(Coord, Workers) =
    Coord [| {assign, report} |] (||| i : Workers @ Worker(i))

-- Coordinator process
Coord = dispatch_tasks ; collect_reports ; synthesize
```

### 7.4 Jury

```csp
Jury(Jurors) =
    (||| i : Jurors @ vote(i) -> Juror(i))
    ; tally_votes
    ; announce_verdict

-- Independent deliberation (isolated)
Juror(i) = deliberate(i) ; cast_vote(i)
```

### 7.5 Generator-Critic

```csp
GenCrit(G, C) =
    mu X . (
        G >> draft
        ; C >> feedback
        ; (accept -> SKIP [] reject -> X)
    )
```

### 7.6 Map-Reduce

```csp
MapReduce(Data, Mapper, Reducer) =
    (||| chunk : partition(Data) @ Mapper(chunk))
    ; Reducer
    ; output_result
```

### 7.7 Adversarial

```csp
Adversarial(Red, Blue, Judge) =
    (Red ||| Blue) [| {argument} |] Debate
    ; Judge
    ; verdict

Debate = collect_arguments ; structure_debate
```

### 7.8 Circuit Breaker

```csp
CircuitBreaker(Primary, Fallback, timeout) =
    (Primary timeout[t] Fallback)
    ; output_result

-- With state tracking
CircuitBreaker_Stateful(P, F, state) =
    [state = closed] Primary
    + [state = open] Fallback
    + [state = half_open] (Primary timeout[probe_t] (set_open ; Fallback))
```

### 7.9 Chain of Responsibility

```csp
Chain(H1, H2, H3) =
    H1 ; ((handled -> SKIP) [] (pass ->
    H2 ; ((handled -> SKIP) [] (pass ->
    H3 ; ((handled -> SKIP) [] (pass -> escalate))))))
```

### 7.10 Blackboard

```csp
Blackboard(Agents, Board) =
    (||| i : Agents @
        mu X . (
            read_board(i)
            ; contribute(i)
            ; write_board(i)
            ; [converged -> SKIP [] continue -> X]
        )
    ) [| {read_board, write_board} |] Board
```

### 7.11 Event-Driven

```csp
EventDriven(Handlers) =
    nu X . (
        ([] e : Events @ event(e) -> Handler(e))
        ; X
    )
    [] (stop -> SKIP)
```

### 7.12 Broadcast

```csp
Broadcast(Sender, Receivers) =
    Sender ; msg_out
    ; (||| r : Receivers @ msg_in(r) ; ack(r))
    ; collect_acks
```

---

## 8. Summary

### 8.1 Operator Quick Reference

| Symbol | Name | Type | Commutative | Associative | Identity | Zero |
|--------|------|------|-------------|-------------|----------|------|
| `;` | Sequential | A;B | No | Yes | SKIP | STOP |
| `\|` | Parallel | A\|B | Yes | Yes | 0 | - |
| `\|\|\|` | Interleave | A\|\|\|B | Yes | Yes | SKIP | - |
| `\|\|` | Sync Parallel | A\|\|B | Yes | Yes | - | STOP |
| `+` / `[]` | Choice | A+B | Yes | Yes | STOP | - |
| `(nu x)` | Restriction | (nu x)A | N/A | N/A | N/A | N/A |
| `\ S` | Hiding | A \ S | N/A | N/A | {} | N/A |
| `*` | Iteration | A* | N/A | N/A | - | - |
| `!` | Replication | !A | N/A | N/A | - | 0 |

### 8.2 Scope Quick Reference

| Scope | Symbol | Sharing | Thread-Safe | Use Case |
|-------|--------|---------|-------------|----------|
| Isolated | `[iso]` | None | N/A | Jury, independent workers |
| Shared | `[shared]` | Full | Yes | Hierarchical, Blackboard |
| Federated | `[fed]` | Read-only | Yes | Cross-agent queries |
| Handoff | `[handoff]` | At boundary | Transfer | Pipeline stages |

### 8.3 Law Quick Reference

| Category | Key Laws |
|----------|----------|
| **Monoid** | Associativity, Identity |
| **Semilattice** | + Idempotence |
| **Distribution** | (A+B);C = A;C + B;C |
| **Scope** | Extrusion, Narrowing, Commutation |
| **Fusion** | Catamorphism fusion, Banana-split |
| **Refinement** | Transitivity, Monotonicity |

---

## Implementation Roadmap

To close the gap between this spec and the codebase:

1. **Phase 1: Scope Type Enum** - Add `ScopeType` to `unified_scope.py`
2. **Phase 2: Annotation Syntax** - Enable `pattern ;[shared] pattern` in orchestration
3. **Phase 3: Validity Predicate** - Implement `CanCompose()` as runtime check
4. **Phase 4: Composition Optimizer** - Use fusion laws to optimize pattern chains

---

## References

- Hoare, C.A.R. (1985). *Communicating Sequential Processes*. Prentice Hall.
- Milner, R. (1999). *Communicating and Mobile Systems: the Pi-Calculus*. Cambridge.
- Bird, R. & de Moor, O. (1997). *The Algebra of Programming*. Prentice Hall.
- Bergstra, J.A. & Klop, J.W. (1984-). Algebra of Communicating Processes (ACP series).
- Roscoe, A.W. (1998). *The Theory and Practice of Concurrency*. Prentice Hall.
- Sangiorgi, D. & Walker, D. (2001). *The Pi-Calculus: A Theory of Mobile Processes*. Cambridge.
- Cardelli, L. & Gordon, A. (1998). "Mobile Ambients". FoSSaCS.
