# Agentic Orchestration

A formal system for composing multi-agent patterns with resource-aware validation.

## Overview

This system provides:
- **Pattern Algebra** - Mathematical foundations for composing agents (from process algebra)
- **Composition Validator** - Structural validation of pattern chains
- **Resource Validator** - Runtime capacity checking before launch
- **Fallback Suggestions** - Cheaper alternatives when resources are constrained

## Quick Start

```bash
# Validate a composition
uv run python scripts/validate_composition.py "Pipeline ;[handoff] Jury"

# Check if resources allow launch
uv run python scripts/validate_composition.py --check-resources "Swarm(5) |[iso] Jury"

# Get suggestions for two patterns
uv run python scripts/validate_composition.py --suggest Swarm Jury
```

## Documents

| Document | Description |
|----------|-------------|
| [README.md](README.md) | This overview |
| [pattern-algebra.md](pattern-algebra.md) | Formal specification (technical) |
| [pattern-algebra-for-humans.md](pattern-algebra-for-humans.md) | Layman's explanation (pop science) |
| [architecture.md](architecture.md) | System architecture with diagrams |
| [scripts-reference.md](scripts-reference.md) | All scripts and their purposes |
| [validation-report.md](../pattern-algebra-validation.md) | Epistemic validation of the spec |

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│              AGENTIC ORCHESTRATION PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   User/LLM proposes: "Swarm(5) → Jury → Aggregator"            │
│                           │                                     │
│                           ▼                                     │
│   ┌─────────────────────────────────────────────┐              │
│   │         validate_composition.py              │              │
│   │  "Is this algebraically valid?"              │              │
│   │                                              │              │
│   │  Checks:                                     │              │
│   │  • Scope compatibility                       │              │
│   │  • Deadlock potential                        │              │
│   │  • Termination guarantees                   │              │
│   └─────────────────┬───────────────────────────┘              │
│                     │                                           │
│            ✓ Valid  │  ✗ Invalid → Show errors                 │
│                     ▼                                           │
│   ┌─────────────────────────────────────────────┐              │
│   │            status.sh + resources             │              │
│   │  "Do we have capacity to run this?"          │              │
│   │                                              │              │
│   │  Checks:                                     │              │
│   │  • Available RAM                             │              │
│   │  • Active agent count                        │              │
│   │  • Max concurrent agents                     │              │
│   └─────────────────┬───────────────────────────┘              │
│                     │                                           │
│            ✓ Enough │  ✗ Insufficient → Suggest fallback       │
│                     ▼                                           │
│   ┌─────────────────────────────────────────────┐              │
│   │              Launch composition              │              │
│   └─────────────────────────────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Why This Exists

Before this system, multi-agent orchestration was ad-hoc:
- No formal rules for which patterns could combine
- No resource checking before spawning agents
- LLMs would propose compositions that deadlocked or exhausted memory

Now we have:
1. **Mathematical foundations** from process algebra (CSP, Pi-calculus)
2. **Automated validation** via scripts
3. **Resource awareness** integrated with the status line
4. **Graceful degradation** via fallback suggestions

## Source Material

The pattern algebra was synthesized from 5 process algebra textbooks:
- Hoare - Communicating Sequential Processes (CSP)
- Milner - Communication and Mobile Systems (Pi-calculus)
- Bird & de Moor - The Algebra of Programming
- Introduction to Process Algebra (ACP/CCS)
- Process Algebra for Parallel and Distributed Processing

See [pattern-algebra.md](pattern-algebra.md) for the full formal specification.
