"""Refactor patterns.py into modular structure using DependencySwarm.

This script orchestrates the refactoring of scripts/agentica/patterns.py (1967 lines)
into individual pattern files within a patterns/ subdirectory.

Target structure:
    scripts/agentica/patterns/
        __init__.py          # Re-exports all patterns
        primitives.py        # Move from current primitives.py
        swarm.py
        pipeline.py
        hierarchical.py
        jury.py
        generator_critic.py
        circuit_breaker.py
        map_reduce.py
        adversarial.py
        chain_of_responsibility.py
        blackboard.py
        event_driven.py

Approach:
    Phase 1: Context analysis + write failing tests
    Phase 2: Create directory + __init__.py skeleton
    Phase 3: Extract patterns (2-3 at a time in parallel)
    Phase 4: Fix imports, verify all tests pass

Usage:
    uv run python -m runtime.harness scripts/agentica/refactor_patterns_modular.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.agentica_patterns.dependency_swarm import DependencySwarm
from scripts.agentica_patterns.coordination import CoordinationDB


# Pattern class names and their file names
PATTERNS = [
    ("Swarm", "swarm.py"),
    ("Pipeline", "pipeline.py"),
    ("Hierarchical", "hierarchical.py"),
    ("Jury", "jury.py"),
    ("GeneratorCritic", "generator_critic.py"),
    ("CircuitBreaker", "circuit_breaker.py"),
    ("MapReduce", "map_reduce.py"),
    ("Adversarial", "adversarial.py"),
    ("ChainOfResponsibility", "chain_of_responsibility.py"),
    ("Blackboard", "blackboard.py"),
    ("EventDriven", "event_driven.py"),
]


async def main():
    """Execute the refactoring using DependencySwarm."""

    # Setup coordination DB
    project_root = Path(__file__).parent.parent.parent
    cache_dir = project_root / ".claude" / "cache" / "agents"
    cache_dir.mkdir(parents=True, exist_ok=True)

    db = CoordinationDB(
        db_path=cache_dir / "refactor_patterns.db",
        session_id="refactor-patterns-modular"
    )

    # Create swarm with implementation bundle
    swarm = DependencySwarm(
        db=db,
        model="anthropic:claude-sonnet-4",
        fail_fast=False,
        max_parallel=3,
        bundle="implementation"
    )

    # Phase 1: Context analysis + write failing tests
    phase1_id = swarm.add_task(
        name="phase1_analysis",
        premise="""Analyze patterns.py structure and write failing tests.

**Your task:**
1. Use rp-cli to understand the structure:
   ```bash
   rp-cli -e 'structure scripts/agentica/patterns.py'
   ```

2. Create failing tests in `tests/unit/test_patterns_refactor.py`:
   - Test imports from new location: `from scripts.agentica_patterns.patterns import Swarm`
   - Test direct imports: `from scripts.agentica_patterns.patterns.swarm import Swarm`
   - Test that primitives still work: `from scripts.agentica_patterns.patterns.primitives import Consensus`
   - All 11 patterns should be importable from both locations

3. Run tests to confirm they fail:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py -v
   ```

4. Document findings:
   - Create `scripts/agentica/patterns/REFACTOR_PLAN.md`
   - List all pattern classes found
   - List all imports that patterns.py uses
   - Note any circular dependencies
   - Document shared utilities/helpers

**Success criteria:**
- Test file exists with 22+ tests (2 per pattern + primitives)
- All tests fail with ImportError
- REFACTOR_PLAN.md exists with complete analysis
""",
        bundle="implementation"
    )

    # Phase 2: Create directory structure
    phase2_id = swarm.add_task(
        name="phase2_scaffold",
        premise="""Create the patterns/ directory and __init__.py skeleton.

**Your task:**
1. Create directory: `scripts/agentica/patterns/`

2. Create `scripts/agentica/patterns/__init__.py` with:
   ```python
   '''Multi-Agent Patterns for Agentica.

   Re-exports all patterns for convenience.
   '''

   # Primitives
   from scripts.agentica_patterns.patterns.primitives import (
       AggregateMode,
       Aggregator,
       Consensus,
       ConsensusMode,
       ConsensusNotReachedError,
       HandoffState,
   )

   # Patterns (placeholders - will be filled in by extraction tasks)
   # from scripts.agentica_patterns.patterns.swarm import Swarm
   # from scripts.agentica_patterns.patterns.pipeline import Pipeline
   # ... etc

   __all__ = [
       "AggregateMode",
       "Aggregator",
       "Consensus",
       "ConsensusMode",
       "ConsensusNotReachedError",
       "HandoffState",
       # Pattern classes will be added here
   ]
   ```

3. Verify structure:
   ```bash
   ls -la scripts/agentica/patterns/
   ```

**Success criteria:**
- Directory exists: `scripts/agentica/patterns/`
- `__init__.py` exists with primitives imports
- File is valid Python (no syntax errors)
""",
        depends_on=[phase1_id],
        bundle="implementation"
    )

    # Phase 3: Move primitives.py
    phase3_id = swarm.add_task(
        name="phase3_move_primitives",
        premise="""Move primitives.py into patterns/ directory.

**Your task:**
1. Copy `scripts/agentica/primitives.py` to `scripts/agentica/patterns/primitives.py`

2. No changes needed to the file content - it's already self-contained

3. Update imports in `scripts/agentica/patterns/__init__.py`:
   - Change from: `from scripts.agentica_patterns.patterns.primitives import ...`
   - To: `from scripts.agentica_patterns.patterns.primitives import ...`
   - (Should already be correct from Phase 2)

4. Run primitives tests to verify:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py::test_primitives_import -v
   ```

**Success criteria:**
- File exists: `scripts/agentica/patterns/primitives.py`
- Test passes for primitives import
""",
        depends_on=[phase2_id],
        bundle="implementation"
    )

    # Phase 4-7: Extract patterns in batches of 3
    # Batch 1: Swarm, Pipeline, Hierarchical
    extract_ids = []

    batch1_patterns = [
        ("Swarm", "swarm.py", 53, 228),
        ("Pipeline", "pipeline.py", 233, 395),
        ("Hierarchical", "hierarchical.py", 400, 650),
    ]

    for class_name, file_name, start_line, end_line in batch1_patterns:
        task_id = swarm.add_task(
            name=f"extract_{class_name.lower()}",
            premise=f"""Extract {class_name} pattern to {file_name}.

**Your task:**
1. Read the pattern class from backup:
   ```bash
   rp-cli -e 'read scripts/agentica/patterns.py.backup --start-line {start_line} --limit {end_line - start_line}'
   ```

2. Create `scripts/agentica/patterns/{file_name}` with:
   - Import statements (copy from patterns.py header)
   - The {class_name} class (lines {start_line}-{end_line} approx)
   - Update imports to use relative imports where needed
   - Example: `from scripts.agentica_patterns.primitives import X` → `from .primitives import X`

3. Update `scripts/agentica/patterns/__init__.py`:
   - Uncomment: `from scripts.agentica_patterns.patterns.{file_name[:-3]} import {class_name}`
   - Add to `__all__`: `"{class_name}",`

4. Run tests:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py::test_{class_name.lower()}_import -v
   uv run pytest tests/unit/test_agentica_{class_name.lower()}.py -v
   ```

**Success criteria:**
- File exists: `scripts/agentica/patterns/{file_name}`
- Import tests pass for {class_name}
- Original pattern tests still pass
""",
            depends_on=[phase3_id],
            bundle="implementation"
        )
        extract_ids.append(task_id)

    # Batch 2: Jury, GeneratorCritic, CircuitBreaker
    batch2_patterns = [
        ("Jury", "jury.py", 655, 780),
        ("GeneratorCritic", "generator_critic.py", 785, 950),
        ("CircuitBreaker", "circuit_breaker.py", 955, 1130),
    ]

    for class_name, file_name, start_line, end_line in batch2_patterns:
        task_id = swarm.add_task(
            name=f"extract_{class_name.lower()}",
            premise=f"""Extract {class_name} pattern to {file_name}.

**Your task:**
1. Read the pattern class from backup:
   ```bash
   rp-cli -e 'read scripts/agentica/patterns.py.backup --start-line {start_line} --limit {end_line - start_line}'
   ```

2. Create `scripts/agentica/patterns/{file_name}` with:
   - Import statements (copy from patterns.py header)
   - The {class_name} class (lines {start_line}-{end_line} approx)
   - Update imports to use relative imports where needed
   - Example: `from scripts.agentica_patterns.primitives import X` → `from .primitives import X`

3. Update `scripts/agentica/patterns/__init__.py`:
   - Uncomment: `from scripts.agentica_patterns.patterns.{file_name[:-3]} import {class_name}`
   - Add to `__all__`: `"{class_name}",`

4. Run tests:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py::test_{class_name.lower()}_import -v
   uv run pytest tests/unit/test_agentica_{class_name.lower()}.py -v
   ```

**Success criteria:**
- File exists: `scripts/agentica/patterns/{file_name}`
- Import tests pass for {class_name}
- Original pattern tests still pass
""",
            depends_on=[phase3_id],
            bundle="implementation"
        )
        extract_ids.append(task_id)

    # Batch 3: MapReduce, Adversarial, ChainOfResponsibility
    batch3_patterns = [
        ("MapReduce", "map_reduce.py", 1135, 1300),
        ("Adversarial", "adversarial.py", 1305, 1500),
        ("ChainOfResponsibility", "chain_of_responsibility.py", 1505, 1670),
    ]

    for class_name, file_name, start_line, end_line in batch3_patterns:
        task_id = swarm.add_task(
            name=f"extract_{class_name.lower()}",
            premise=f"""Extract {class_name} pattern to {file_name}.

**Your task:**
1. Read the pattern class from backup:
   ```bash
   rp-cli -e 'read scripts/agentica/patterns.py.backup --start-line {start_line} --limit {end_line - start_line}'
   ```

2. Create `scripts/agentica/patterns/{file_name}` with:
   - Import statements (copy from patterns.py header)
   - The {class_name} class (lines {start_line}-{end_line} approx)
   - Update imports to use relative imports where needed
   - Example: `from scripts.agentica_patterns.primitives import X` → `from .primitives import X`

3. Update `scripts/agentica/patterns/__init__.py`:
   - Uncomment: `from scripts.agentica_patterns.patterns.{file_name[:-3]} import {class_name}`
   - Add to `__all__`: `"{class_name}",`

4. Run tests:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py::test_{class_name.lower()}_import -v
   uv run pytest tests/unit/test_agentica_{class_name.lower()}.py -v
   ```

**Success criteria:**
- File exists: `scripts/agentica/patterns/{file_name}`
- Import tests pass for {class_name}
- Original pattern tests still pass
""",
            depends_on=[phase3_id],
            bundle="implementation"
        )
        extract_ids.append(task_id)

    # Batch 4: Blackboard, EventDriven
    batch4_patterns = [
        ("Blackboard", "blackboard.py", 1675, 1840),
        ("EventDriven", "event_driven.py", 1845, 1967),
    ]

    for class_name, file_name, start_line, end_line in batch4_patterns:
        task_id = swarm.add_task(
            name=f"extract_{class_name.lower()}",
            premise=f"""Extract {class_name} pattern to {file_name}.

**Your task:**
1. Read the pattern class from backup:
   ```bash
   rp-cli -e 'read scripts/agentica/patterns.py.backup --start-line {start_line} --limit {end_line - start_line}'
   ```

2. Create `scripts/agentica/patterns/{file_name}` with:
   - Import statements (copy from patterns.py header)
   - The {class_name} class (lines {start_line}-{end_line} approx)
   - Update imports to use relative imports where needed
   - Example: `from scripts.agentica_patterns.primitives import X` → `from .primitives import X`

3. Update `scripts/agentica/patterns/__init__.py`:
   - Uncomment: `from scripts.agentica_patterns.patterns.{file_name[:-3]} import {class_name}`
   - Add to `__all__`: `"{class_name}",`

4. Run tests:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py::test_{class_name.lower()}_import -v
   uv run pytest tests/unit/test_agentica_{class_name.lower()}.py -v
   ```

**Success criteria:**
- File exists: `scripts/agentica/patterns/{file_name}`
- Import tests pass for {class_name}
- Original pattern tests still pass
""",
            depends_on=[phase3_id],
            bundle="implementation"
        )
        extract_ids.append(task_id)

    # Phase Final: Verify and cleanup
    final_id = swarm.add_task(
        name="phase_final_verify",
        premise="""Verify refactoring and cleanup.

**Your task:**
1. Run all pattern tests:
   ```bash
   uv run pytest tests/unit/test_patterns_refactor.py -v
   uv run pytest tests/unit/test_agentica_*.py -v
   ```

2. Verify all imports work:
   ```bash
   python -c "from scripts.agentica_patterns.patterns import Swarm, Pipeline, Hierarchical, Jury, GeneratorCritic, CircuitBreaker, MapReduce, Adversarial, ChainOfResponsibility, Blackboard, EventDriven"
   python -c "from scripts.agentica_patterns.patterns.primitives import Consensus, Aggregator, HandoffState"
   ```

3. Update existing files to use new import paths:
   - Search for: `from scripts.agentica_patterns.patterns import`
   - Verify they still work with new structure
   - Update if needed

4. Create final report:
   ```bash
   cat > scripts/agentica/patterns/REFACTOR_COMPLETE.md << 'EOF'
# Refactoring Complete

## Structure
- 12 pattern files created
- All tests passing
- Imports verified

## Files Created
- primitives.py
- swarm.py
- pipeline.py
- hierarchical.py
- jury.py
- generator_critic.py
- circuit_breaker.py
- map_reduce.py
- adversarial.py
- chain_of_responsibility.py
- blackboard.py
- event_driven.py

## Test Results
[Insert test output]

## Next Steps
- Can archive scripts/agentica/patterns.py.backup
- Can update documentation references
EOF
   ```

5. Run linting:
   ```bash
   uv run qlty check scripts/agentica/patterns/
   ```

**Success criteria:**
- All tests pass
- All imports work
- Linting passes
- REFACTOR_COMPLETE.md created
""",
        depends_on=extract_ids,
        bundle="implementation"
    )

    # Execute the swarm
    print("Starting refactoring with DependencySwarm...")
    print(f"Total tasks: {len(swarm.graph.nodes)}")
    print(f"Max parallel: {swarm.max_parallel}")
    print(f"Fail fast: {swarm.fail_fast}")
    print()

    results = await swarm.execute()

    # Report results
    print("\n" + "="*80)
    print("REFACTORING COMPLETE")
    print("="*80)

    for task_name, result in results.items():
        status = "✓" if task_name in results else "✗"
        print(f"{status} {task_name}")

    # Check for failures
    failed_tasks = [
        (tid, node) for tid, node in swarm.graph.nodes.items()
        if node.status == "failed"
    ]

    if failed_tasks:
        print("\n" + "="*80)
        print("FAILURES")
        print("="*80)
        for tid, node in failed_tasks:
            print(f"\n✗ {node.name}")
            print(f"  Error: {node.error}")

    print("\n" + "="*80)
    print(f"Completed: {len(results)}/{len(swarm.graph.nodes)}")
    print("="*80)

    # Close DB
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
