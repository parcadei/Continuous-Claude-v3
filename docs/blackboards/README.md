# Blackboards

Shared knowledge extraction from process algebra books.

## Context

We're building **pattern composition algebra** for multi-agent workflows:
- 12 patterns (Pipeline, Swarm, Jury, etc.)
- Each pattern has scope requirements (Isolated, Shared, Federated)
- Need formal basis for composition rules

## Books Being Analyzed

| Book | Blackboard | Agents |
|------|------------|--------|
| Hoare - CSP | `csp.md` | 3 |
| Milner - Pi-calculus | `pi-calculus.md` | 3 |
| Intro to Process Algebra | `process-algebra-intro.md` | 3 |
| Process Algebra for Distributed | `process-algebra-distributed.md` | 3 |
| Bird - Algebra of Programming | `algebra-of-programming.md` | 3 |

## Agent Focus Areas

Each book gets 3 agents exploring:
1. **Composition operators** - What operations exist? (sequential, parallel, choice)
2. **Scope/binding** - How is scope handled? (restriction, hiding, extrusion)
3. **Equivalences/laws** - What algebraic laws hold? (associativity, commutativity, distributivity)

## Synthesis

After extraction, all blackboards will be synthesized into:
- `docs/moments/moment-2.md` - Narrative of what was learned
- `docs/pattern-algebra.md` - Formal specification for our patterns
