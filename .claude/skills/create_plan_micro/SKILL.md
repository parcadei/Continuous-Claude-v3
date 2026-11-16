---
name: create_plan
description: Create detailed implementation plans through interactive research and iteration
model: opus
version: 3.0
---

# Formal Specification

## Multimodal Logic Integration

This specification combines five modal logics via fusion with bridge principles:
- **JL**: Justification Logic (Artemov's LP)
- **IEL**: Inferential Erotetic Logic (Wisniewski)
- **TEL**: Temporal Epistemic Logic (LTL + S5)
- **SDL**: Standard Deontic Logic
- **DEL**: Dynamic Epistemic Logic

## Justification Logic (JL)

Based on Artemov's Logic of Proofs (LP). Justification terms are explicit evidence.

```
# Syntax: t:phi means "t is a justification for phi"
# Terms: t ::= c | x | t+s | t*s | !t (constants, variables, sum, application, checker)

# Justified knowledge (replaces K(why(p)))
t:p                                    # Term t justifies proposition p
[c]:claim(u,p)                        # Constant c is evidence for user claim
[e]:evidence(f,l,r)                   # Evidence term e from file f, line l

# Justification axioms (LP axioms)
t:(p -> q) -> (s:p -> (t*s):q)        # Application axiom
t:p -> !t:(t:p)                        # Proof checker axiom
t:p -> p                               # Factivity (justified implies true)

# Knowledge as justified true belief (JTB replacement)
K(p) := exists t. t:p                  # Know p iff some term justifies p

# Verification creates justification terms
[verify(p)]exists t. t:p               # Verification produces evidence
[read(f,l)]exists e. [e]:content(f,l)  # Reading produces file evidence

# Skeptical stance: require explicit justification
claim(u,p) -> B(p) & not exists t. t:p # Claims create belief without justification
proceed(r) <-> exists t. t:r           # Proceed only with justified requirements
```

## Inferential Erotetic Logic (IEL)

Based on Wisniewski's IEL. Questions as sets of possible answers.

```
# Syntax: ?{a1, a2, ..., an} is a question with direct answers ai
# Im(Q) = implied by asking Q (presuppositions)

# Question types
?{p, not p}                            # Yes/no question about p
?{a1, ..., an}                         # Which-question with options
?x.phi(x)                              # Wh-question: which x satisfies phi

# Erotetic inference (Q evokes Q' relative to X)
X, Q |~ Q'                             # X and asking Q licenses asking Q'

# Requirement clarification questions
vague(r) := exists t. t:r & not exists s. s:why(r)
vague(r) -> ?{why1(r), why2(r), ...}   # Vagueness evokes why-questions

# Questions from incomplete knowledge
not K(p) & not K(not p) -> ?{p, not p} # Ignorance licenses inquiry
exists f. possibly(evidence(f,_,r)) -> ?x.file_location(x,r)

# Question resolution
[answer(Q,a)]K(a)                      # Answering Q with a produces knowledge of a
Im(?{a1,...,an}) = a1 v ... v an       # Presupposition of question
```

## Temporal Epistemic Logic (TEL)

Standard LTL extended with epistemic operators and past modalities.

```
# Future operators (LTL)
X phi        # Next: phi holds at next state
[] phi       # Always: phi holds at all future states (box)
<> phi       # Eventually: phi holds at some future state (diamond)
phi U psi    # Until: phi until psi

# Past operators (PLTL) - replaces informal phi^-1
H phi        # Historically: phi held at all past states
P phi        # Previously: phi held at some past state
S phi        # Since: dual of Until

# File reading constraints
[](mentioned(f) -> <>read_fully(f))           # Mentioned files eventually read
[](mentioned(f) -> not spawn U read_fully(f)) # No spawn until read
[](partial_read(f) -> false)                  # Partial reads impossible

# Research phase ordering
[](spawn_tasks -> <>all_complete)             # Spawned tasks complete
[](not all_complete -> not synthesize)        # No synthesis before completion

# Phase sequencing
[](phase(n) -> P phase(n-1))                  # Phase n requires past phase n-1
[](automated_fail -> not manual_verify)       # Automated gates manual
[](feedback -> O iterate)                     # Feedback triggers next iteration

# Termination
<>(approved | abandoned)                      # Eventually terminates
```

## Standard Deontic Logic (SDL)

Based on von Wright's SDL with standard operators.

```
# Operators
O(phi)       # Obligation: phi is obligatory
P(phi)       # Permission: phi is permitted  (P(phi) <-> not O(not phi))
F(phi)       # Forbidden: phi is forbidden   (F(phi) <-> O(not phi))

# Deontic axioms
O(phi -> psi) -> (O(phi) -> O(psi))          # K axiom for O
O(phi) -> P(phi)                              # Ought implies may
not (O(phi) & O(not phi))                     # Deontic consistency

# Planning obligations (MUST)
O(read_fully(f)) <- mentioned(f)              # Must read mentioned files
O(parallel_spawn) <- research_phase           # Must spawn parallel research
O(wait_all) <- pre_synthesis                  # Must wait before synthesis
O(verify(c)) <- correction(c)                 # Must verify corrections
O(present) <- pre_design                      # Must present findings first
O(approval) <- pre_write                      # Must get approval first

# Prohibitions (MUST NOT)
F(partial_read)                               # Partial reads forbidden
F(assume) <- can_verify                       # Assuming when verifiable forbidden
F(finalize) <- open_question                  # Finalizing with questions forbidden
F(proceed) <- not exists t. t:requirement     # Unjustified proceed forbidden

# Permissions (MAY)
P(web_search) <- planning_phase               # Web search permitted in planning
P(iterate) <- not approved                    # Iteration permitted until done
P(spawn_followup) <- unexpected_result        # Follow-up tasks permitted
```

## Dynamic Epistemic Logic (DEL)

Based on Plaza's public announcement logic with action modalities.

```
# Public announcement operator
[!phi]psi                                     # After announcing phi, psi holds

# Reduction axioms (standard DEL)
[!phi]p <-> (phi -> p)                        # Atomic
[!phi]not psi <-> (phi -> not [!phi]psi)      # Negation
[!phi](psi & chi) <-> [!phi]psi & [!phi]chi   # Conjunction
[!phi]K(psi) <-> (phi -> K(phi -> [!phi]psi)) # Knowledge update

# Action modalities for planning operations
[read(f)]K(content(f))                        # Reading produces knowledge
[spawn(a,q)]<>result(a,q)                     # Spawning produces eventual result
[present]<feedback>iterate                    # Presenting may trigger feedback
[verify(p)](K(p) | K(not p))                  # Verification resolves truth

# Composed actions
[read_all ; spawn_parallel ; wait]ready_to_synthesize
[present ; (feedback ; revise)* ; approve]finalized

# Update operations
[correction(u,p)][verify]K(p) | K(not p)      # Correction triggers verification
[answer(Q,a)][update]K(a)                     # Answer updates knowledge
```

## Interaction Axioms (Bridge Principles)

These connect the separate logics into a coherent multimodal system.

```
# JL-TEL Bridge: Temporal justification
t:p -> [](t:p)                                # Justifications persist (monotonic)
[read(f,l)]exists e. [](e:content(f,l))       # File evidence persists

# JL-SDL Bridge: Deontic justification
O(phi) & exists t. t:not phi -> violation     # Obligation with contrary evidence
O(verify(p)) -> <>[verify]exists t. t:p       # Must verify implies eventually justified

# IEL-DEL Bridge: Questions and announcements
?{a1,...,an} -> [!ai]resolved(Q) for each ai  # Answering resolves question
[answer(Q,a)]not ?{a1,...,an}                 # Answered questions no longer open

# TEL-SDL Bridge: Temporal deontic
O(phi) -> <>phi                               # Obligations eventually fulfilled (ideal)
[](F(phi) -> not phi)                         # Forbidden never happens (ideal)

# Full integration axiom
O(exists t. t:r) <- requirement(r)            # Requirements need justification
vague(r) -> O(resolve(?{why1(r),...}))        # Vagueness demands clarification
```

## Predicates and Definitions

| Symbol | Framework | Type | Meaning |
|--------|-----------|------|---------|
| `t:p` | JL | Term x Prop | t justifies p |
| `K(p)` | JL+TEL | Prop -> Bool | exists t. t:p |
| `B(p)` | JL | Prop -> Bool | Believe p (unjustified) |
| `?{...}` | IEL | Set -> Query | Question with answers |
| `O(p)` | SDL | Prop -> Prop | p is obligatory |
| `P(p)` | SDL | Prop -> Prop | p is permitted |
| `F(p)` | SDL | Prop -> Prop | p is forbidden |
| `[]p` | TEL | Prop -> Prop | Always p |
| `<>p` | TEL | Prop -> Prop | Eventually p |
| `H p` | TEL | Prop -> Prop | Historically p |
| `[a]p` | DEL | Action x Prop | After a, p holds |
| `[!p]q` | DEL | Prop x Prop | After announcing p, q |

## Agents

| Phase | Agent | Tools | Purpose |
|-------|-------|-------|---------|
| research | `codebase-locator` | Read, Grep, Glob | Find relevant files |
| research | `codebase-analyzer` | Read, Grep | Understand implementation |
| research | `codebase-pattern-finder` | Read, Grep, Glob | Find similar patterns |
| research | `thoughts-locator` | Read, Grep, Glob | Find prior research |
| research | `thoughts-analyzer` | Read | Extract insights |
| research | `linear-ticket-reader` | LinearAPI | Get ticket details |
| research | `research-agent` | WebSearch | External documentation |

## State Machine

```
                +--------------------------------------+
                |                                      |
                v                                      |
INIT --> GATHER --> PRESENT --> RESEARCH --> FINDINGS --> STRUCTURE --> WRITE --> REVIEW --> DONE
             |           |           |                        |           |
             v           |           v                        |           |
          CLARIFY -------+        DESIGN ---------------------+           |
             |                       |                                    |
             +-------+-------+-------+------------------------------------+ ITERATE <-----+
```

## Higher-Order Workflow Composition

```
# Main workflow (using ; for sequencing, | for choice, * for iteration)
create_plan : Input -> Plan
create_plan =
  check_params ;
  gather_context ;
  (present_understanding ; clarify)* until aligned ;
  spawn_research ;
  wait_all ;
  (present_findings ; feedback)* until approach_selected ;
  present_structure ;
  (revise_structure)* until structure_approved ;
  write_plan ;
  (present ; feedback ; iterate)* until approved

# Sub-workflows with pattern mapping
gather_context =
  read_all_mentioned |
  spawn_initial_research ;
  read_identified_files ;
  analyze_and_verify

research_phase   ~ Swarm([locator, analyzer, thoughts, linear])
iteration_phase  ~ Generator-Critic(draft, user_feedback)
verification     ~ Pipeline([automated, manual])
```

## Output Schema

```yaml
path: "thoughts/shared/plans/{date}-{ticket}-{description}.md"
date_format: "YYYY-MM-DD"
ticket_format: "ENG-XXXX"  # optional
description_format: kebab-case

schema:
  required:
    - overview
    - current_state_analysis
    - desired_end_state
    - key_discoveries[]
    - not_doing[]
    - implementation_approach
    - phases[]:
        - name
        - overview
        - changes[]:
            - file
            - description
            - code_snippet?
        - success_criteria:
            - automated[]  # executable commands
            - manual[]     # human verification
    - testing_strategy
    - references[]
  optional:
    - performance_considerations
    - migration_notes
```

---

# Prose (Where Logic Insufficient)

## Response Templates

**Initial (no params):**
```
I'll help you create a detailed implementation plan. Let me start by understanding what we're building.

Please provide:
1. The task/ticket description (or reference to a ticket file)
2. Any relevant context, constraints, or specific requirements
3. Links to related research or previous implementations

Tip: Invoke with a file directly: `/create_plan thoughts/tickets/eng_1234.md`
For deeper analysis: `/create_plan think deeply about thoughts/tickets/eng_1234.md`
```

**Understanding presentation:**
```
Based on the ticket and my research of the codebase, I understand we need to [summary].

I've found that:
- [evidence with file:line]
- [pattern discovered]
- [complexity identified]

Questions that my research couldn't answer:
- [question requiring human judgment]
```

**Structure proposal:**
```
Here's my proposed plan structure:

## Overview
[1-2 sentences]

## Implementation Phases:
1. [Phase] - [accomplishment]
2. [Phase] - [accomplishment]

Does this phasing make sense?
```

## Domain Patterns

```yaml
database_changes:
  sequence: [schema, store_methods, business_logic, api, clients]

new_features:
  sequence: [research_patterns, data_model, backend, api, ui]

refactoring:
  sequence: [document_current, plan_incremental, maintain_compat, migrate]
```

## Tool Preferences

```
# Preference ordering (informal but practical)
prefer(uv_run, raw_python)
prefer(make_target, manual_cd)
prefer(npx_direct, global_install)
```

---

# Validity Constraints

```
# Well-formedness (informal metalevel)
forall phase. has_automated_criteria(phase) & has_manual_criteria(phase)
forall file_ref. exists line. specific_reference(file_ref, line)
forall discovery. exists e. [e]:discovery          # Evidence-backed

# Completeness
not exists q. open(q) & finalized(plan)            # No open questions when final
forall r. covered_by_phase(r) | in_not_doing(r)    # All requirements addressed

# Consistency
forall i,j. (i < j) -> not depends(phase_i, phase_j)  # Dependency ordering
forall c. executable(c) | human_verifiable(c)         # Criteria are checkable
```
