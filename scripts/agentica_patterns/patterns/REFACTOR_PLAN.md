# Patterns Module Refactor Plan

## Overview

Refactor `scripts/agentica/patterns.py` (single file, ~800 lines) into a package with one module per pattern for better maintainability and import flexibility.

## Current Structure

```
scripts/agentica/
├── patterns.py          # All 11 patterns in one file
├── primitives.py        # Consensus, Aggregator, HandoffState
├── coordination.py      # CoordinationDB
└── tracked_agent.py     # tracked_spawn
```

## Target Structure

```
scripts/agentica/
├── patterns/
│   ├── __init__.py      # Re-exports all patterns + supporting types
│   ├── primitives.py    # Move from ../primitives.py OR re-export
│   ├── _base.py         # Shared utilities (if needed)
│   ├── swarm.py
│   ├── pipeline.py
│   ├── hierarchical.py
│   ├── jury.py
│   ├── generator_critic.py
│   ├── circuit_breaker.py
│   ├── adversarial.py
│   ├── chain_of_responsibility.py
│   ├── map_reduce.py
│   ├── blackboard.py
│   └── event_driven.py
├── coordination.py      # Unchanged
└── tracked_agent.py     # Unchanged
```

## Pattern Classes Found (11)

| Pattern | Class | Supporting Types |
|---------|-------|------------------|
| Swarm | `Swarm` | - |
| Pipeline | `Pipeline` | - |
| Hierarchical | `Hierarchical` | - |
| Jury | `Jury` | - |
| Generator/Critic | `GeneratorCritic` | - |
| Circuit Breaker | `CircuitBreaker` | `CircuitState` (Enum) |
| Adversarial | `Adversarial` | - |
| Chain of Responsibility | `ChainOfResponsibility` | `Handler` (dataclass) |
| Map/Reduce | `MapReduce` | - |
| Blackboard | `Blackboard` | `Specialist`, `BlackboardState`, `BlackboardResult` |
| Event-Driven | `EventDriven` | `Event`, `Subscriber` |

## Current Imports in patterns.py

```python
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from agentica import spawn
from scripts.agentica.primitives import (
    AggregateMode,
    Aggregator,
    Consensus,
    ConsensusMode,
    HandoffState,
)
from scripts.agentica.coordination import CoordinationDB
from scripts.agentica.tracked_agent import tracked_spawn
```

## Primitives Module Contents

From `scripts/agentica/primitives.py`:
- `ConsensusMode` (Enum)
- `ConsensusNotReachedError` (Exception)
- `Consensus` (Class)
- `AggregateMode` (Enum)
- `Aggregator` (Class)
- `HandoffState` (dataclass)

## Circular Dependency Analysis

**Potential Issue:** None detected.

The dependency graph is linear:
```
patterns.py → primitives.py → (no deps on patterns)
patterns.py → coordination.py → (no deps on patterns)
patterns.py → tracked_agent.py → (no deps on patterns)
```

Each pattern module will import from:
- Standard library (asyncio, dataclasses, etc.)
- `agentica` (spawn)
- `scripts.agentica.primitives` (Consensus, Aggregator, etc.)
- `scripts.agentica.coordination` (CoordinationDB)
- `scripts.agentica.tracked_agent` (tracked_spawn)

No cross-pattern imports needed.

## Shared Utilities

Currently embedded in patterns.py:
1. The `patterns` class with `spawn` override (stub for static type checking)

Recommendation: Move to `patterns/_base.py` if needed, or keep in `__init__.py`.

## Implementation Steps

### Phase 1: Create Package Structure
1. Create `scripts/agentica/patterns/` directory
2. Create `__init__.py` that imports from current patterns.py
3. Verify existing tests still pass

### Phase 2: Extract Patterns One by One
For each pattern:
1. Create `patterns/{pattern_name}.py`
2. Move class + supporting types
3. Add appropriate imports
4. Update `__init__.py` to re-export from new module
5. Run tests to verify no breakage

Order (simplest to most complex):
1. Pipeline (no supporting types, simple)
2. Swarm (no supporting types)
3. Adversarial (no supporting types)
4. GeneratorCritic (no supporting types)
5. Jury (no supporting types)
6. Hierarchical (no supporting types)
7. CircuitBreaker (has CircuitState enum)
8. ChainOfResponsibility (has Handler dataclass)
9. MapReduce (no supporting types)
10. EventDriven (has Event, Subscriber dataclasses)
11. Blackboard (has Specialist, BlackboardState, BlackboardResult)

### Phase 3: Handle Primitives
Decision needed:
- **Option A:** Move primitives.py into patterns/ package
- **Option B:** Re-export primitives from patterns/ (keep original location)

Recommendation: Option B - keep primitives.py in place, add re-exports to patterns/__init__.py. This avoids breaking existing imports.

### Phase 4: Cleanup
1. Delete original patterns.py
2. Update any external imports
3. Run full test suite

## Success Criteria

All 34 tests in `tests/unit/test_patterns_refactor.py` must pass:
- 11 package root imports (TestPackageRootImports)
- 11 direct module imports (TestDirectModuleImports)
- 5 primitives imports (TestPrimitivesImports)
- 7 supporting types imports (TestSupportingTypesImports)

## Current Test Status

```
PASSED: 18 (package root + supporting types)
FAILED: 16 (direct module + primitives imports)
```

The failing tests are the ones that will guide the refactor.
