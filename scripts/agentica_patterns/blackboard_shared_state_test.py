#!/usr/bin/env python3
"""Blackboard Shared State Test.

Tests multi-agent coordination via blackboard shared state, where agents can:
- Write state that other agents read mid-execution
- Read state written by other agents
- Coordinate through shared blackboard entries

USAGE:
    # Start servers first (in separate terminals):
    # Terminal 1: uv run python scripts/agentica_patterns/claude_proxy.py --port 8080
    # Terminal 2: cd workspace/agentica-research/agentica-server && \
    #             INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions \
    #             uv run agentica-server --port 2345

    # Then run this script:
    S_M_BASE_URL=http://localhost:2345 uv run python scripts/agentica_patterns/blackboard_shared_state_test.py

Tests:
    1. Same-scope: Two agents share a scope_id, write/read via BlackboardCache
    2. Cross-scope: Two agents with different scope_ids read/write to shared blackboard
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agentica_patterns.blackboard import (
    BlackboardCache,
    SharedContextEntry,
    MessageType,
    EntryPriority,
    ScopeLevel,
)
from scripts.agentica_patterns.tracked_agent import tracked_spawn
from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.claude_scope import create_claude_scope


# Formal environment specification to prevent hallucinated function calls
FORMAL_ENVIRONMENT_SPEC = """
## Initial State Specification (Formal)

### Deontic Logic (Permitted/Forbidden Actions)
- Permitted(write_file(path, content)) -> creates file at path
- Permitted(read_file(path)) -> returns file content
- Permitted(bash(command)) -> executes shell command
- Permitted(write_to_blackboard(key, value)) -> writes to shared blackboard
- Permitted(read_from_blackboard(key)) -> reads from shared blackboard
- Permitted(list_blackboard()) -> lists all blackboard entries
- Forbidden(view_file) AND Forbidden(fs.write) AND Forbidden(os.write)

### Epistemic State
- K(scope_functions) = {write_file, read_file, bash, grep, glob, write_to_blackboard, read_from_blackboard, list_blackboard}
- B(training_data_functions) = {} // Discard training data assumptions
- K(return_format) = {"success": bool, ...}

### API Signatures (CRITICAL - prevents hallucination)
# Scope functions (these are what YOU call):
- write_to_blackboard(key: str, value: Any) -> {"success": bool, "key": str, "value": Any, "entry_id": str}
- read_from_blackboard(key: str) -> {"success": bool, "key": str, "value": Any | None, "from_agent": str, "entry_id": str}
- list_blackboard() -> {"success": bool, "count": int, "entries": list}
# File functions:
- write_file(path: str, content: str) -> bool
- read_file(path: str) -> str

# Internal Infrastructure (NOT for agent use - for documentation only):
# Source: .claude/skills/agentica-infrastructure/API_SPEC.md
#
# BlackboardCache (File: blackboard.py)
# Constructor:
#   BlackboardCache(project_id: str, cache_dir: Path = BLACKBOARD_CACHE_DIR)
#   - BLACKBOARD_CACHE_DIR defaults to /tmp/claude-blackboard
# Methods:
#   .push(entry: SharedContextEntry) -> None  # Add entry (FIFO with max size)
#   .poll(agent_id?: str, pattern_id?: str, since_timestamp?: str, types?: list[MessageType], scope?: ScopeLevel) -> list[SharedContextEntry]
#   .clear() -> None  # Clear all entries
#   .get_summary(max_entries: int = 5) -> str  # Compact summary for injection
#
# SharedContextEntry (dataclass):
#   # Identity (required)
#   id: str
#   project_id: str
#   type: MessageType  # TASK, RESULT, QUERY, RESPONSE, STATUS, ARTIFACT, ERROR
#   from_agent: str    # NOTE: "from_agent" NOT "source_agent"
#   # Optional routing
#   to_agent: str | None = None  # None = broadcast
#   pattern_id: str | None = None
#   scope: ScopeLevel = ScopeLevel.SHARED  # AGENT, SHARED, or TEMPORAL
#   # Content (hybrid format)
#   formal: str | None = None   # Formal logic notation
#   prose: str | None = None    # Natural language (NOT "content")
#   data: dict[str, Any] = {}   # Structured payload (NOT "content")
#   # References
#   artifacts: list[str] = []   # File paths
#   parent_id: str | None = None  # For threading
#   # Metadata
#   priority: EntryPriority = EntryPriority.NORMAL  # CRITICAL, HIGH, NORMAL, LOW
#   timestamp: str  # Auto-set
#   ttl_seconds: int | None = None  # Auto-expire
#
# MessageType (Enum): TASK, RESULT, QUERY, RESPONSE, STATUS, ARTIFACT, ERROR
# EntryPriority (Enum): CRITICAL, HIGH, NORMAL, LOW
# ScopeLevel (Enum): AGENT, SHARED, TEMPORAL

### Temporal Logic (Action Ordering)
- Always(write_to_blackboard(k,v) -> Eventually(blackboard_contains(k,v)))
- Before(read_from_blackboard(k)) -> After(some_agent_wrote(k))

### First-Order Logic
- ForAll(f in Functions): f in K(scope_functions) -> callable(f)
- ForAll(f not in K(scope_functions)) -> NOT EXISTS implementation(f)
"""


def create_blackboard_scope(
    blackboard: BlackboardCache,
    agent_id: str,
    project_id: str,
) -> dict[str, Any]:
    """Create scope with blackboard read/write functions.

    Args:
        blackboard: Shared BlackboardCache instance
        agent_id: Unique identifier for this agent
        project_id: Project identifier for blackboard entries

    Returns:
        Scope dict with blackboard functions added to file ops
    """
    # Get base file operations
    base_scope = create_claude_scope()

    def write_to_blackboard(key: str, value: Any) -> dict[str, Any]:
        """Write a key-value pair to the blackboard.

        The value is stored as a RESULT entry so other agents can read it.
        """
        entry = SharedContextEntry(
            id=str(uuid.uuid4())[:8],
            project_id=project_id,
            type=MessageType.RESULT,
            from_agent=agent_id,
            to_agent=None,  # Broadcast to all
            scope=ScopeLevel.SHARED,
            prose=f"Set {key}",
            data={"key": key, "value": value},
            priority=EntryPriority.NORMAL,
        )
        blackboard.push(entry)
        return {
            "success": True,
            "key": key,
            "value": value,
            "entry_id": entry.id,
        }

    def read_from_blackboard(key: str) -> dict[str, Any]:
        """Read a value from the blackboard by key.

        Searches through all entries to find the most recent value for the key.
        """
        entries = blackboard.poll()

        # Find most recent entry with this key (search backwards)
        for entry in reversed(entries):
            if entry.data.get("key") == key:
                return {
                    "success": True,
                    "key": key,
                    "value": entry.data.get("value"),
                    "from_agent": entry.from_agent,
                    "entry_id": entry.id,
                }

        return {
            "success": False,
            "key": key,
            "value": None,
            "error": f"Key '{key}' not found on blackboard",
        }

    def list_blackboard() -> dict[str, Any]:
        """List all entries on the blackboard."""
        entries = blackboard.poll()
        return {
            "success": True,
            "count": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "from_agent": e.from_agent,
                    "type": e.type.value,
                    "data": e.data,
                    "timestamp": e.timestamp,
                }
                for e in entries
            ],
        }

    return {
        **base_scope,
        "write_to_blackboard": write_to_blackboard,
        "read_from_blackboard": read_from_blackboard,
        "list_blackboard": list_blackboard,
    }


# Agent 1: Research Topic Writer
AGENT1_PREMISE = FORMAL_ENVIRONMENT_SPEC + """
You are Agent 1: the Research Topic Writer.

## Your Task

1. Write "research_topic" = "formal logic" to the blackboard using write_to_blackboard()
2. Wait a moment, then write your findings about formal logic to the blackboard
3. Write your findings to a file as well

## Steps

1. Call: write_to_blackboard("research_topic", "formal logic")
2. Call: write_to_blackboard("agent1_findings", "Formal logic includes propositional logic, first-order logic, and modal logic. Key concepts: validity, soundness, completeness.")
3. Call: write_file("thoughts/shared/agents/blackboard-test-agent1.md", "<your findings>")
4. Return a brief summary

## Available Tools

You have access to:
- `write_to_blackboard(key, value)` - Write a key-value pair to the shared blackboard
- `read_from_blackboard(key)` - Read a value from the blackboard
- `list_blackboard()` - List all entries on the blackboard
- `write_file(path, content)` - Write to a file
- `read_file(path)` - Read a file
- `bash(command)` - Run shell commands

## IMPORTANT

1. Actually USE the tools - don't just describe what you would do
2. Use write_to_blackboard() FIRST to set the research topic
3. Return a brief summary when done
"""

# Agent 2: Research Topic Reader
AGENT2_PREMISE = FORMAL_ENVIRONMENT_SPEC + """
You are Agent 2: the Research Topic Reader.

## Your Task

1. Read the "research_topic" from the blackboard (that Agent 1 wrote)
2. Based on what you read, write complementary findings to the blackboard
3. Write your findings to a file as well

## Steps

1. Call: read_from_blackboard("research_topic") - should return "formal logic" (written by Agent 1)
2. Call: read_from_blackboard("agent1_findings") - read what Agent 1 discovered
3. Call: write_to_blackboard("agent2_findings", "<your complementary findings based on the topic>")
4. Call: write_file("thoughts/shared/agents/blackboard-test-agent2.md", "<your findings>")
5. Return a summary of what you read and wrote

## Available Tools

You have access to:
- `write_to_blackboard(key, value)` - Write a key-value pair to the shared blackboard
- `read_from_blackboard(key)` - Read a value from the blackboard
- `list_blackboard()` - List all entries on the blackboard
- `write_file(path, content)` - Write to a file
- `read_file(path)` - Read a file
- `bash(command)` - Run shell commands

## IMPORTANT

1. Actually USE the tools - don't just describe what you would do
2. Use read_from_blackboard() to get the topic Agent 1 set
3. Your findings should complement what Agent 1 found
4. Return a brief summary including what you read from the blackboard
"""


async def test_same_scope():
    """Test two agents sharing the same blackboard scope."""
    print("\n" + "=" * 60)
    print("TEST 1: Same Scope Blackboard Communication")
    print("=" * 60)

    # Setup
    project_id = f"test-same-scope-{uuid.uuid4().hex[:6]}"
    blackboard = BlackboardCache(project_id)
    blackboard.clear()  # Start fresh

    db = CoordinationDB()
    output_dir = Path("thoughts/shared/agents")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] Project ID: {project_id}")
    print(f"[*] Blackboard cache file: {blackboard.cache_file}")

    # Create scope with shared blackboard
    agent1_id = f"agent1-{uuid.uuid4().hex[:6]}"
    agent2_id = f"agent2-{uuid.uuid4().hex[:6]}"

    scope1 = create_blackboard_scope(blackboard, agent1_id, project_id)
    scope2 = create_blackboard_scope(blackboard, agent2_id, project_id)

    print(f"\n[1] Spawning Agent 1 (Writer): {agent1_id}")
    agent1 = await tracked_spawn(
        db=db,
        premise=AGENT1_PREMISE,
        model="anthropic:claude-sonnet-4",
        scope=scope1,
        pattern="blackboard_test",
    )

    # Execute Agent 1 first
    print("[*] Executing Agent 1...")
    try:
        result1 = await agent1.call(
            str,
            "Execute your task: write the research topic and findings to the blackboard."
        )
        print(f"\n[Agent 1] Result:\n{result1[:500]}...")
    except Exception as e:
        print(f"\n[Agent 1] ERROR: {e}")
        result1 = None

    # Check blackboard state after Agent 1
    print("\n[*] Blackboard state after Agent 1:")
    entries = blackboard.poll()
    for e in entries:
        print(f"    - [{e.type.value}] {e.from_agent}: {e.data}")

    # Now spawn and execute Agent 2
    print(f"\n[2] Spawning Agent 2 (Reader): {agent2_id}")
    agent2 = await tracked_spawn(
        db=db,
        premise=AGENT2_PREMISE,
        model="anthropic:claude-sonnet-4",
        scope=scope2,
        pattern="blackboard_test",
    )

    print("[*] Executing Agent 2...")
    try:
        result2 = await agent2.call(
            str,
            "Execute your task: read the research topic from the blackboard and write complementary findings."
        )
        print(f"\n[Agent 2] Result:\n{result2[:500]}...")
    except Exception as e:
        print(f"\n[Agent 2] ERROR: {e}")
        result2 = None

    # Final blackboard state
    print("\n[*] Final blackboard state:")
    entries = blackboard.poll()
    for e in entries:
        print(f"    - [{e.type.value}] {e.from_agent}: {e.data}")

    # Cleanup
    await agent1.close()
    await agent2.close()

    # Verify results
    print("\n" + "-" * 60)
    print("VERIFICATION")
    print("-" * 60)

    # Check if expected keys exist on blackboard
    final_entries = blackboard.poll()
    keys_found = {e.data.get("key") for e in final_entries if e.data.get("key")}

    expected_keys = {"research_topic", "agent1_findings", "agent2_findings"}
    missing_keys = expected_keys - keys_found

    if not missing_keys:
        print("[PASS] All expected keys found on blackboard")
    else:
        print(f"[FAIL] Missing keys: {missing_keys}")

    # Check if Agent 2 read Agent 1's topic
    agent2_read_topic = any(
        e.from_agent.startswith("agent2") and e.data.get("key") == "agent2_findings"
        for e in final_entries
    )
    if agent2_read_topic:
        print("[PASS] Agent 2 wrote findings (implies it read the topic)")
    else:
        print("[WARN] Agent 2 may not have read/processed the topic")

    return {
        "project_id": project_id,
        "entries": [e.to_dict() for e in final_entries],
        "keys_found": list(keys_found),
        "result1": result1,
        "result2": result2,
    }


async def test_cross_scope():
    """Test two agents with different scope_ids reading from shared blackboard."""
    print("\n" + "=" * 60)
    print("TEST 2: Cross-Scope Blackboard Communication")
    print("=" * 60)

    # In cross-scope, agents have different pattern_ids but same project_id
    # This simulates agents from different swarms sharing a global blackboard

    project_id = f"test-cross-scope-{uuid.uuid4().hex[:6]}"
    blackboard = BlackboardCache(project_id)
    blackboard.clear()

    db = CoordinationDB()

    print(f"\n[*] Project ID (shared): {project_id}")
    print("[*] Agents will have different pattern_ids but share the project blackboard")

    # Agent 1 with pattern "swarm_alpha"
    agent1_id = f"alpha-{uuid.uuid4().hex[:6]}"
    scope1 = create_blackboard_scope(blackboard, agent1_id, project_id)

    print(f"\n[1] Spawning Agent 1 (Swarm Alpha): {agent1_id}")
    agent1 = await tracked_spawn(
        db=db,
        premise=AGENT1_PREMISE,
        model="anthropic:claude-sonnet-4",
        scope=scope1,
        pattern="swarm_alpha",  # Different pattern
    )

    print("[*] Executing Agent 1 (Alpha)...")
    try:
        result1 = await agent1.call(
            str,
            "Execute your task: write the research topic and findings to the blackboard."
        )
        print(f"\n[Agent 1 (Alpha)] Result:\n{result1[:300]}...")
    except Exception as e:
        print(f"\n[Agent 1 (Alpha)] ERROR: {e}")
        result1 = None

    # Agent 2 with pattern "swarm_beta" - different swarm but reads from same blackboard
    agent2_id = f"beta-{uuid.uuid4().hex[:6]}"
    scope2 = create_blackboard_scope(blackboard, agent2_id, project_id)

    print(f"\n[2] Spawning Agent 2 (Swarm Beta): {agent2_id}")
    agent2 = await tracked_spawn(
        db=db,
        premise=AGENT2_PREMISE,
        model="anthropic:claude-sonnet-4",
        scope=scope2,
        pattern="swarm_beta",  # Different pattern
    )

    print("[*] Executing Agent 2 (Beta)...")
    try:
        result2 = await agent2.call(
            str,
            "Execute your task: read the research topic from the blackboard (written by another swarm) and write complementary findings."
        )
        print(f"\n[Agent 2 (Beta)] Result:\n{result2[:300]}...")
    except Exception as e:
        print(f"\n[Agent 2 (Beta)] ERROR: {e}")
        result2 = None

    # Final state
    print("\n[*] Final blackboard state (cross-scope):")
    entries = blackboard.poll()
    for e in entries:
        print(f"    - [{e.from_agent}] {e.data.get('key')}: {str(e.data.get('value'))[:50]}...")

    await agent1.close()
    await agent2.close()

    # Verification
    print("\n" + "-" * 60)
    print("VERIFICATION")
    print("-" * 60)

    # Check cross-scope communication worked
    alpha_wrote = any(e.from_agent.startswith("alpha") for e in entries)
    beta_wrote = any(e.from_agent.startswith("beta") for e in entries)

    if alpha_wrote and beta_wrote:
        print("[PASS] Both swarms (alpha and beta) wrote to shared blackboard")
    else:
        print(f"[FAIL] alpha_wrote={alpha_wrote}, beta_wrote={beta_wrote}")

    return {
        "project_id": project_id,
        "entries": [e.to_dict() for e in entries],
        "alpha_wrote": alpha_wrote,
        "beta_wrote": beta_wrote,
    }


async def main():
    """Run all blackboard shared state tests."""
    print("=" * 60)
    print("BLACKBOARD SHARED STATE TEST")
    print("=" * 60)
    print(f"Started: {datetime.now(UTC).isoformat()}")

    results = {}

    # Test 1: Same scope
    try:
        results["same_scope"] = await test_same_scope()
    except Exception as e:
        print(f"\n[ERROR] Same scope test failed: {e}")
        import traceback
        traceback.print_exc()
        results["same_scope"] = {"error": str(e)}

    # Test 2: Cross scope
    try:
        results["cross_scope"] = await test_cross_scope()
    except Exception as e:
        print(f"\n[ERROR] Cross scope test failed: {e}")
        import traceback
        traceback.print_exc()
        results["cross_scope"] = {"error": str(e)}

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    same_scope_ok = "error" not in results.get("same_scope", {})
    cross_scope_ok = "error" not in results.get("cross_scope", {})

    print(f"Same-scope test:  {'PASS' if same_scope_ok else 'FAIL'}")
    print(f"Cross-scope test: {'PASS' if cross_scope_ok else 'FAIL'}")

    # Write results to file
    output_path = Path("thoughts/shared/agents/blackboard-shared-state-results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults written to: {output_path}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
