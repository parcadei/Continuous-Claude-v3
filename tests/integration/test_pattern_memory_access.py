"""Integration tests for memory access in multi-agent patterns.

Phase 3.2 of Memory Auto-Wiring Implementation.

Tests verify that memory functions (remember, recall, search_memory, store_fact)
are properly wired into agent scopes when using tracked_spawn() within patterns
like Swarm, Hierarchical, and Pipeline.
"""

import asyncio
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def tmp_memory_db(tmp_path):
    """Provide temp path for memory database."""
    return tmp_path / "memory.db"


@pytest.fixture
def mock_coordination_db(tmp_path):
    """Create mock coordination DB for pattern tracking."""
    from scripts.agentica_patterns.coordination import CoordinationDB
    return CoordinationDB(db_path=tmp_path / "coord.db", session_id="test-pattern")


@pytest.fixture
def mock_env():
    """Set CLAUDE_SESSION_ID for memory isolation."""
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "pattern-test-session"}):
        yield


class TestSwarmAgentsHaveMemory:
    """Test that Swarm pattern agents receive memory functions in scope."""

    @pytest.mark.asyncio
    async def test_swarm_agents_have_memory(self, mock_coordination_db, tmp_memory_db, mock_env):
        """Swarm agents should receive memory functions in scope via tracked_spawn."""
        from scripts.agentica_patterns import tracked_agent

        captured_scopes = []

        # Capture the scope that gets passed to agentica spawn
        async def capture_spawn(**kwargs):
            agent = AsyncMock()
            agent.call = AsyncMock(return_value={"insight": "test"})
            captured_scopes.append(dict(kwargs.get("scope", {})))
            return agent

        # Patch spawn at the tracked_agent module level
        # tracked_spawn calls spawn internally after memory wiring
        with patch.object(tracked_agent, "spawn", side_effect=capture_spawn):
            # tracked_spawn gets called by patterns, will wire memory then call patched spawn
            from scripts.agentica_patterns.patterns import Swarm

            swarm = Swarm(
                perspectives=["Expert A", "Expert B", "Expert C"],
                db=mock_coordination_db,
            )

            # Need to also patch memory db path
            orig_tracked_spawn = tracked_agent.tracked_spawn

            async def patched_tracked_spawn(*args, **kwargs):
                kwargs["memory_db_path"] = tmp_memory_db
                return await orig_tracked_spawn(*args, **kwargs)

            # Patch the module-level function that the patterns import
            with patch.object(tracked_agent, "tracked_spawn", patched_tracked_spawn):
                result = await swarm.execute("Analyze this topic")

        # Verify at least 3 agents were spawned (one per perspective)
        assert len(captured_scopes) >= 3, f"Expected 3 agents, got {len(captured_scopes)}"

        # Each agent's scope should have memory functions
        for i, scope in enumerate(captured_scopes):
            assert "remember" in scope, f"Agent {i} missing 'remember'"
            assert "recall" in scope, f"Agent {i} missing 'recall'"
            assert "search_memory" in scope, f"Agent {i} missing 'search_memory'"
            assert "store_fact" in scope, f"Agent {i} missing 'store_fact'"
            assert callable(scope["remember"]), f"Agent {i} 'remember' not callable"

    @pytest.mark.asyncio
    async def test_swarm_without_db_no_tracked_spawn(self, mock_env):
        """Swarm without db should use regular spawn (no memory auto-wiring)."""
        from scripts.agentica_patterns.patterns import Swarm

        captured_scopes = []

        async def capture_spawn(**kwargs):
            agent = AsyncMock()
            agent.call = AsyncMock(return_value={"insight": "test"})
            captured_scopes.append(kwargs.get("scope", {}))
            return agent

        with patch("scripts.agentica_patterns.patterns.swarm.spawn", side_effect=capture_spawn):
            swarm = Swarm(
                perspectives=["Expert A", "Expert B"],
                db=None,  # No coordination DB = no tracked_spawn
            )

            result = await swarm.execute("Analyze this")

        # Without db, Swarm uses regular spawn, not tracked_spawn
        # So memory is NOT auto-wired (unless user provides scope)
        assert len(captured_scopes) == 2
        for scope in captured_scopes:
            # Empty scope when no db and no user-provided scope
            assert "remember" not in scope


class TestHierarchicalAgentsHaveMemory:
    """Test that Hierarchical pattern agents receive memory functions."""

    @pytest.mark.asyncio
    async def test_hierarchical_coordinator_has_memory(self, mock_coordination_db, tmp_memory_db, mock_env):
        """Hierarchical coordinator should receive memory functions."""
        from scripts.agentica_patterns import tracked_agent

        captured_scopes = []
        agent_premises = []

        async def capture_spawn(**kwargs):
            agent = AsyncMock()
            agent.agent_id = f"agent_{len(captured_scopes)}"
            premise = kwargs.get("premise", "")
            agent_premises.append(premise)

            # Return decomposition for coordinator, result for specialists
            if "coordinate" in premise.lower() or "break" in premise.lower():
                # Coordinator - return empty list to skip specialist execution
                agent.call = AsyncMock(side_effect=[
                    [],  # No subtasks (simple task)
                    "Direct coordinator answer"  # Final synthesis
                ])
            else:
                agent.call = AsyncMock(return_value="Specialist result")

            captured_scopes.append(dict(kwargs.get("scope", {})))
            return agent

        with patch.object(tracked_agent, "spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.patterns import Hierarchical

            orig_tracked_spawn = tracked_agent.tracked_spawn

            async def patched_tracked_spawn(*args, **kwargs):
                kwargs["memory_db_path"] = tmp_memory_db
                return await orig_tracked_spawn(*args, **kwargs)

            with patch.object(tracked_agent, "tracked_spawn", patched_tracked_spawn):
                hierarchical = Hierarchical(
                    coordinator_premise="You coordinate and break down tasks.",
                    specialist_premises={"worker": "You do work."},
                    db=mock_coordination_db,
                )
                result = await hierarchical.execute("Simple question")

        # At least coordinator should have been spawned
        assert len(captured_scopes) >= 1, "Coordinator should be spawned"

        # First scope is coordinator
        coordinator_scope = captured_scopes[0]
        assert "remember" in coordinator_scope, "Coordinator missing 'remember'"
        assert "recall" in coordinator_scope, "Coordinator missing 'recall'"
        assert "search_memory" in coordinator_scope, "Coordinator missing 'search_memory'"
        assert "store_fact" in coordinator_scope, "Coordinator missing 'store_fact'"

    @pytest.mark.asyncio
    async def test_hierarchical_specialists_have_memory(self, mock_coordination_db, tmp_memory_db, mock_env):
        """Hierarchical specialists should receive memory functions."""
        from scripts.agentica_patterns import tracked_agent

        captured_scopes = []
        spawn_order = []

        async def capture_spawn(**kwargs):
            agent = AsyncMock()
            agent.agent_id = f"agent_{len(captured_scopes)}"
            premise = kwargs.get("premise", "")
            spawn_order.append(premise[:30])

            if "coordinate" in premise.lower() or "break" in premise.lower():
                # Coordinator returns subtasks on first call, synthesis on second
                agent.call = AsyncMock(side_effect=[
                    [{"specialist": "researcher", "task": "Research topic"}],
                    "Synthesized answer"
                ])
            else:
                agent.call = AsyncMock(return_value="Specialist findings")

            captured_scopes.append(dict(kwargs.get("scope", {})))
            return agent

        with patch.object(tracked_agent, "spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.patterns import Hierarchical

            orig_tracked_spawn = tracked_agent.tracked_spawn

            async def patched_tracked_spawn(*args, **kwargs):
                kwargs["memory_db_path"] = tmp_memory_db
                return await orig_tracked_spawn(*args, **kwargs)

            with patch.object(tracked_agent, "tracked_spawn", patched_tracked_spawn):
                hierarchical = Hierarchical(
                    coordinator_premise="You coordinate and break down tasks.",
                    specialist_premises={
                        "researcher": "You research topics.",
                        "analyst": "You analyze data."
                    },
                    db=mock_coordination_db,
                )
                result = await hierarchical.execute("Research and analyze topic X")

        # Should have coordinator + at least 1 specialist
        assert len(captured_scopes) >= 2, f"Expected coordinator + specialist, got {len(captured_scopes)}"

        # All agents (coordinator and specialists) should have memory
        for i, scope in enumerate(captured_scopes):
            assert "remember" in scope, f"Agent {i} missing 'remember'"
            assert "recall" in scope, f"Agent {i} missing 'recall'"


class TestMemoryPersistsAcrossAgents:
    """Test that memory stored by one agent is recallable by another."""

    @pytest.mark.asyncio
    async def test_memory_persists_across_agents(self, tmp_memory_db, mock_env):
        """Memory stored by one agent should be recallable by another in same session."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        # Create two scopes with same session_id (simulating two agents in same session)
        session_id = "shared-session-123"

        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        # Agent 1 stores a fact
        scope1["remember"]("api_key", "secret-123")
        scope1["store_fact"]("The project uses Python 3.11")

        # Agent 2 should be able to recall it
        recall_result = scope2["recall"]("api_key")
        assert "secret-123" in recall_result, f"Failed to recall across agents: {recall_result}"

        search_results = scope2["search_memory"]("Python")
        assert len(search_results) > 0, "Failed to search memory across agents"
        assert any("Python" in r.get("content", "") for r in search_results)

    @pytest.mark.asyncio
    async def test_memory_isolation_in_swarm(self, mock_coordination_db, tmp_memory_db, mock_env):
        """All swarm agents share the same session, so memory is shared."""
        from scripts.agentica_patterns import tracked_agent

        # We'll capture the _memory_service from each scope to verify session sharing
        memory_services = []

        async def capture_spawn(**kwargs):
            agent = AsyncMock()
            agent.call = AsyncMock(return_value={"insight": "test"})
            scope = kwargs.get("scope", {})
            if "_memory_service" in scope:
                memory_services.append(scope["_memory_service"])
            return agent

        with patch.object(tracked_agent, "spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.patterns import Swarm

            orig_tracked_spawn = tracked_agent.tracked_spawn

            async def patched_tracked_spawn(*args, **kwargs):
                kwargs["memory_db_path"] = tmp_memory_db
                return await orig_tracked_spawn(*args, **kwargs)

            with patch.object(tracked_agent, "tracked_spawn", patched_tracked_spawn):
                swarm = Swarm(
                    perspectives=["Expert A", "Expert B"],
                    db=mock_coordination_db,
                )
                await swarm.execute("Analyze topic")

        # All memory services should use the same session_id (from CLAUDE_SESSION_ID)
        assert len(memory_services) == 2, f"Expected 2 memory services, got {len(memory_services)}"
        for ms in memory_services:
            assert ms.session_id == "pattern-test-session", \
                f"Memory service has wrong session: {ms.session_id}"


class TestSessionIsolationInPatterns:
    """Test that different sessions have isolated memory in patterns."""

    @pytest.mark.asyncio
    async def test_session_isolation_in_patterns(self, mock_coordination_db, tmp_memory_db):
        """Different sessions should have isolated memory in patterns."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        # Session A stores data
        scope_a = create_unified_scope(
            session_id="session-A",
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )
        scope_a["remember"]("secret", "session-a-secret")
        scope_a["store_fact"]("Session A specific fact")

        # Session B should NOT see Session A's data
        scope_b = create_unified_scope(
            session_id="session-B",
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )
        scope_b["remember"]("secret", "session-b-secret")

        # Recall in each session should get their own data
        recall_a = scope_a["recall"]("secret")
        recall_b = scope_b["recall"]("secret")

        assert "session-a-secret" in recall_a, f"Session A got wrong data: {recall_a}"
        assert "session-b-secret" in recall_b, f"Session B got wrong data: {recall_b}"
        assert "session-a-secret" not in recall_b, "Session B leaked Session A data"

    @pytest.mark.asyncio
    async def test_swarm_agents_share_session_memory(self, mock_coordination_db, tmp_memory_db, mock_env):
        """Swarm agents in same CLAUDE_SESSION_ID share memory."""
        # This is the expected behavior - all agents in a pattern share the session
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        # Simulate what tracked_spawn does - uses CLAUDE_SESSION_ID
        session_id = os.environ.get("CLAUDE_SESSION_ID", "default")

        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        # Agent 1 stores
        scope1["remember"]("shared_key", "shared_value")

        # Agent 2 can recall
        result = scope2["recall"]("shared_key")
        assert "shared_value" in result, "Swarm agents should share memory"


class TestPipelineAgentsHaveMemory:
    """Test that Pipeline pattern stages can have memory access."""

    @pytest.mark.asyncio
    async def test_pipeline_stages_can_use_memory(self, tmp_memory_db, mock_env):
        """Pipeline stages should be able to use memory functions in scope."""
        from scripts.agentica_patterns.patterns.pipeline import Pipeline
        from scripts.agentica_patterns.patterns.primitives import HandoffState
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        # Create scope with memory for pipeline stages
        scope = create_unified_scope(
            session_id="pipeline-session",
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        # Track memory operations in stages
        memory_operations = []

        async def stage1(state: HandoffState) -> HandoffState:
            # Store a fact in memory
            scope["remember"]("stage1_key", "stage1_value")
            memory_operations.append(("remember", "stage1_key", "stage1_value"))
            state.add_artifact("stage1_done", True)
            return state

        async def stage2(state: HandoffState) -> HandoffState:
            # Recall from memory
            result = scope["recall"]("stage1_key")
            memory_operations.append(("recall", "stage1_key", result))
            state.add_artifact("recall_result", result)
            return state

        pipeline = Pipeline(stages=[stage1, stage2])
        initial_state = HandoffState(
            context="Testing memory in pipeline stages",
            next_instruction="Run through pipeline stages"
        )

        final_state = await pipeline.run(initial_state)

        # Verify memory operations worked
        assert len(memory_operations) == 2, "Expected 2 memory operations"
        assert memory_operations[0][0] == "remember"
        assert memory_operations[1][0] == "recall"
        assert "stage1_value" in memory_operations[1][2], "Recall should return stored value"

        # Verify pipeline completed
        assert final_state.artifacts.get("stage1_done") is True
        assert "stage1_value" in final_state.artifacts.get("recall_result", "")


class TestMemoryFunctionsWorkEndToEnd:
    """Test that memory functions work correctly within pattern execution."""

    @pytest.mark.asyncio
    async def test_remember_and_recall(self, tmp_memory_db, mock_env):
        """scope['remember'] and scope['recall'] should work end-to-end."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id="e2e-test-session",
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        # Store
        scope["remember"]("key1", "value1")
        scope["remember"]("key2", "value2")

        # Recall
        result1 = scope["recall"]("key1")
        result2 = scope["recall"]("key2")

        assert "value1" in result1, f"recall key1 failed: {result1}"
        assert "value2" in result2, f"recall key2 failed: {result2}"

    @pytest.mark.asyncio
    async def test_search_memory(self, tmp_memory_db, mock_env):
        """scope['search_memory'] should return FTS5 search results."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id="search-test-session",
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        # Store multiple facts
        scope["store_fact"]("Python is a programming language")
        scope["store_fact"]("JavaScript runs in browsers")
        scope["store_fact"]("Python is used for data science")

        # Search
        results = scope["search_memory"]("Python")

        assert len(results) >= 2, f"Expected at least 2 Python results, got {len(results)}"
        assert all("Python" in r.get("content", "") for r in results)

    @pytest.mark.asyncio
    async def test_store_fact_returns_id(self, tmp_memory_db, mock_env):
        """scope['store_fact'] should store and return a memory ID."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id="store-fact-session",
            db_path=tmp_memory_db,
            enable_memory=True,
            enable_tasks=False,
        )

        # Store and get ID
        fact_id = scope["store_fact"]("Important discovery: test passes")

        assert fact_id is not None, "store_fact should return an ID"
        assert isinstance(fact_id, str), f"ID should be string, got {type(fact_id)}"

        # Verify fact is searchable
        results = scope["search_memory"]("Important discovery")
        assert len(results) >= 1, "Stored fact should be searchable"
