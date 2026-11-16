"""Integration tests for Agentica Broadcast Flow (Phase 17).

Tests end-to-end broadcast flow between simulated agents in a swarm.

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md

Test scenarios covered:
1. Basic broadcast flow between two agents
2. Full swarm lifecycle: multiple agents broadcasting findings -> done -> synthesis
3. Filter combinations work end-to-end
4. Swarm isolation verified across multiple swarms
5. Performance test: 10 agents, 100 broadcasts, verify query performance
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.agentica_patterns.coordination import (
    BroadcastRecord,
    BroadcastType,
    CoordinationDB,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def isolated_db(tmp_path: Path) -> CoordinationDB:
    """Create an isolated test database for each test."""
    db_path = tmp_path / "test_broadcast_flow.db"
    return CoordinationDB(db_path=db_path, session_id=f"test-{uuid4().hex[:8]}")


@pytest.fixture
def swarm_id() -> str:
    """Generate a unique swarm ID for each test."""
    return uuid4().hex[:12]


# ============================================================================
# Test Scenario 1: Basic Broadcast Flow Between Two Agents
# ============================================================================


class TestBasicBroadcastFlow:
    """Test basic broadcast flow as specified in Phase 17 plan.

    Scenario:
    1. Create coordination DB with swarm_id
    2. Create two "agents" (simulated)
    3. Agent 1 broadcasts finding
    4. Agent 2 queries and receives finding
    5. Agent 2 broadcasts blocker
    6. Agent 1 receives blocker
    """

    def test_broadcast_flow_between_agents(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test that broadcasts flow between agents (Phase 17 spec)."""
        db = isolated_db

        # Step 3: Agent 1 broadcasts finding
        b1 = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Found important pattern in auth module"},
        )

        # Step 4: Agent 2 queries and should see agent 1's broadcast
        broadcasts_for_agent2 = db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-2"  # Agent 2 doesn't see its own broadcasts
        )

        assert len(broadcasts_for_agent2) == 1
        assert broadcasts_for_agent2[0].sender_agent == "agent-1"
        assert broadcasts_for_agent2[0].broadcast_type == BroadcastType.FINDING
        assert broadcasts_for_agent2[0].payload["finding"] == "Found important pattern in auth module"

        # Step 5: Agent 2 broadcasts blocker
        b2 = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.BLOCKER,
            payload={
                "blocker": "Cannot access database credentials",
                "severity": "high",
            },
        )

        # Step 6: Agent 1 receives blocker (query excluding self)
        broadcasts_for_agent1 = db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-1"
        )

        assert len(broadcasts_for_agent1) == 1
        assert broadcasts_for_agent1[0].sender_agent == "agent-2"
        assert broadcasts_for_agent1[0].broadcast_type == BroadcastType.BLOCKER
        assert broadcasts_for_agent1[0].payload["blocker"] == "Cannot access database credentials"

    def test_bidirectional_communication(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test that agents can send and receive broadcasts bidirectionally."""
        db = isolated_db

        # Agent 1 sends multiple messages
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "First finding from agent-1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.QUESTION,
            payload={"question": "Has anyone checked the config files?"},
        )

        # Agent 2 sends response
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Config checked - all good"},
        )

        # Verify agent 1 sees agent 2's response
        agent1_inbox = db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-1"
        )
        assert len(agent1_inbox) == 1
        assert agent1_inbox[0].sender_agent == "agent-2"

        # Verify agent 2 sees agent 1's messages
        agent2_inbox = db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-2"
        )
        assert len(agent2_inbox) == 2
        assert all(b.sender_agent == "agent-1" for b in agent2_inbox)


# ============================================================================
# Test Scenario 2: Full Swarm Lifecycle
# ============================================================================


class TestFullSwarmLifecycle:
    """Test full swarm lifecycle with multiple agents.

    Scenario:
    - Multiple agents broadcast findings
    - Agents broadcast done when complete
    - Coordinator can synthesize all findings
    """

    def test_swarm_lifecycle_findings_to_done(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test complete swarm lifecycle: findings -> done -> synthesis ready."""
        db = isolated_db
        num_agents = 4

        # Phase 1: All agents broadcast their findings
        for i in range(1, num_agents + 1):
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"researcher-{i}",
                broadcast_type=BroadcastType.FINDING,
                payload={
                    "finding": f"Research finding #{i}",
                    "confidence": 0.8 + (i * 0.05),
                    "source_file": f"module_{i}.py",
                },
            )

        # Verify all findings are visible
        all_findings = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING]
        )
        assert len(all_findings) == num_agents

        # Phase 2: All agents mark themselves as done
        for i in range(1, num_agents + 1):
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"researcher-{i}",
                broadcast_type=BroadcastType.DONE,
                payload={
                    "summary": f"Completed analysis of module_{i}",
                    "artifacts": {"report": f"report_{i}.md"},
                },
            )

        # Phase 3: Coordinator checks if all agents are done
        done_broadcasts = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.DONE]
        )
        assert len(done_broadcasts) == num_agents

        # Verify we can get unique done agents
        done_agents = {b.sender_agent for b in done_broadcasts}
        expected_agents = {f"researcher-{i}" for i in range(1, num_agents + 1)}
        assert done_agents == expected_agents

        # Phase 4: Coordinator synthesizes all findings
        all_broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        findings = [b for b in all_broadcasts if b.broadcast_type == BroadcastType.FINDING]
        summaries = [b.payload.get("summary") for b in done_broadcasts]

        assert len(findings) == num_agents
        assert all(s is not None for s in summaries)

    def test_swarm_with_blockers_and_resolution(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test swarm where some agents encounter blockers."""
        db = isolated_db

        # Agent 1 makes progress
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Database schema analyzed"},
        )

        # Agent 2 hits a blocker
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.BLOCKER,
            payload={
                "blocker": "Missing API documentation",
                "severity": "medium",
                "help_needed": "Can someone share API docs?",
            },
        )

        # Agent 1 sees the blocker and responds
        blockers = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.BLOCKER]
        )
        assert len(blockers) == 1

        # Agent 1 provides help via finding
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={
                "finding": "API docs found at /docs/api.md",
                "in_response_to": blockers[0].id,
            },
        )

        # Both agents complete
        for agent in ["agent-1", "agent-2"]:
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=agent,
                broadcast_type=BroadcastType.DONE,
                payload={"summary": f"{agent} completed"},
            )

        # Verify complete history
        all_broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert len(all_broadcasts) == 5  # 2 findings + 1 blocker + 2 done

    def test_swarm_abort_scenario(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test swarm abort when critical error occurs."""
        db = isolated_db

        # Agents start working
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Initial analysis started"},
        )

        # Critical error triggers abort
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="coordinator",
            broadcast_type=BroadcastType.ABORT,
            payload={
                "reason": "Critical security vulnerability detected",
                "error_code": "SEC_001",
                "action": "Stop all work immediately",
            },
        )

        # All agents should see abort broadcast
        aborts = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.ABORT]
        )
        assert len(aborts) == 1
        assert aborts[0].payload["error_code"] == "SEC_001"

        # Agent 1 checks and sees abort
        agent1_view = db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-1"
        )
        abort_received = any(
            b.broadcast_type == BroadcastType.ABORT for b in agent1_view
        )
        assert abort_received


# ============================================================================
# Test Scenario 3: Filter Combinations
# ============================================================================


class TestFilterCombinations:
    """Test that filter combinations work correctly end-to-end."""

    def test_since_with_exclude_sender(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test combining since and exclude_sender filters."""
        db = isolated_db

        # Create old broadcasts
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Old from agent-1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Old from agent-2"},
        )

        time.sleep(0.02)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        time.sleep(0.02)

        # Create new broadcasts
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New from agent-1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New from agent-2"},
        )

        # Query: since cutoff, exclude agent-1
        result = db.get_broadcasts(
            swarm_id=swarm_id,
            since=cutoff,
            exclude_sender="agent-1"
        )

        assert len(result) == 1
        assert result[0].sender_agent == "agent-2"
        assert result[0].payload["finding"] == "New from agent-2"

    def test_type_filter_with_exclude_sender(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test combining type and exclude_sender filters."""
        db = isolated_db

        # Agent 1 sends finding and blocker
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "F1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "B1"},
        )

        # Agent 2 sends finding
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "F2"},
        )

        # Query: FINDING type, exclude agent-1
        result = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING],
            exclude_sender="agent-1"
        )

        assert len(result) == 1
        assert result[0].sender_agent == "agent-2"
        assert result[0].broadcast_type == BroadcastType.FINDING

    def test_all_filters_combined(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test combining all three filters: since, exclude_sender, types."""
        db = isolated_db

        # Create old broadcasts
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Old finding from 1"},
        )

        time.sleep(0.02)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        time.sleep(0.02)

        # Create new broadcasts from multiple agents with different types
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New finding from 1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New finding from 2"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "New blocker from 2"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-3",
            broadcast_type=BroadcastType.DONE,
            payload={"summary": "Agent 3 done"},
        )

        # Query: since cutoff, exclude agent-1, only FINDING and BLOCKER
        result = db.get_broadcasts(
            swarm_id=swarm_id,
            since=cutoff,
            exclude_sender="agent-1",
            broadcast_types=[BroadcastType.FINDING, BroadcastType.BLOCKER]
        )

        # Should only get: "New finding from 2" and "New blocker from 2"
        assert len(result) == 2
        assert all(b.sender_agent == "agent-2" for b in result)
        types = {b.broadcast_type for b in result}
        assert types == {BroadcastType.FINDING, BroadcastType.BLOCKER}


# ============================================================================
# Test Scenario 4: Swarm Isolation
# ============================================================================


class TestSwarmIsolation:
    """Test that broadcasts are properly isolated between swarms."""

    def test_multiple_swarms_no_leakage(self, isolated_db: CoordinationDB):
        """Verify broadcasts don't leak between different swarms."""
        db = isolated_db
        swarm_alpha = "swarm-alpha-" + uuid4().hex[:6]
        swarm_beta = "swarm-beta-" + uuid4().hex[:6]
        swarm_gamma = "swarm-gamma-" + uuid4().hex[:6]

        # Create broadcasts in each swarm
        for swarm, prefix in [
            (swarm_alpha, "Alpha"),
            (swarm_beta, "Beta"),
            (swarm_gamma, "Gamma"),
        ]:
            for i in range(3):
                db.create_broadcast(
                    swarm_id=swarm,
                    sender_agent=f"agent-{i}",
                    broadcast_type=BroadcastType.FINDING,
                    payload={"finding": f"{prefix} finding {i}"},
                )

        # Verify each swarm only sees its own broadcasts
        alpha_broadcasts = db.get_broadcasts(swarm_id=swarm_alpha)
        beta_broadcasts = db.get_broadcasts(swarm_id=swarm_beta)
        gamma_broadcasts = db.get_broadcasts(swarm_id=swarm_gamma)

        assert len(alpha_broadcasts) == 3
        assert len(beta_broadcasts) == 3
        assert len(gamma_broadcasts) == 3

        # Verify no cross-contamination
        assert all(b.swarm_id == swarm_alpha for b in alpha_broadcasts)
        assert all(b.swarm_id == swarm_beta for b in beta_broadcasts)
        assert all(b.swarm_id == swarm_gamma for b in gamma_broadcasts)

        # Verify content is correct
        assert all("Alpha" in b.payload["finding"] for b in alpha_broadcasts)
        assert all("Beta" in b.payload["finding"] for b in beta_broadcasts)
        assert all("Gamma" in b.payload["finding"] for b in gamma_broadcasts)

    def test_same_agent_id_different_swarms(self, isolated_db: CoordinationDB):
        """Same agent ID in different swarms should be isolated."""
        db = isolated_db
        swarm_1 = "swarm-1-" + uuid4().hex[:6]
        swarm_2 = "swarm-2-" + uuid4().hex[:6]

        # Same agent-1 identifier used in both swarms
        db.create_broadcast(
            swarm_id=swarm_1,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Swarm 1 finding"},
        )
        db.create_broadcast(
            swarm_id=swarm_2,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Swarm 2 finding"},
        )

        # Each swarm should only see its own agent-1's broadcast
        swarm1_broadcasts = db.get_broadcasts(
            swarm_id=swarm_1,
            exclude_sender="agent-1"
        )
        swarm2_broadcasts = db.get_broadcasts(
            swarm_id=swarm_2,
            exclude_sender="agent-1"
        )

        # exclude_sender should work within each swarm
        assert len(swarm1_broadcasts) == 0
        assert len(swarm2_broadcasts) == 0

        # Without exclude_sender, each swarm sees its own broadcast
        assert len(db.get_broadcasts(swarm_id=swarm_1)) == 1
        assert len(db.get_broadcasts(swarm_id=swarm_2)) == 1

    def test_nonexistent_swarm_returns_empty(self, isolated_db: CoordinationDB):
        """Querying a non-existent swarm should return empty list."""
        db = isolated_db

        # Create some broadcasts in a real swarm
        db.create_broadcast(
            swarm_id="real-swarm",
            sender_agent="agent",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "test"},
        )

        # Query non-existent swarm
        result = db.get_broadcasts(swarm_id="nonexistent-swarm-xyz123")
        assert result == []


# ============================================================================
# Test Scenario 5: Performance Tests
# ============================================================================


class TestBroadcastPerformance:
    """Performance tests for broadcast operations."""

    def test_10_agents_100_broadcasts(self, isolated_db: CoordinationDB, swarm_id: str):
        """Test performance with 10 agents and 100 total broadcasts."""
        db = isolated_db
        num_agents = 10
        broadcasts_per_agent = 10
        total_broadcasts = num_agents * broadcasts_per_agent

        # Create 100 broadcasts (10 per agent)
        start_time = time.time()
        for agent_id in range(num_agents):
            for i in range(broadcasts_per_agent):
                db.create_broadcast(
                    swarm_id=swarm_id,
                    sender_agent=f"agent-{agent_id}",
                    broadcast_type=BroadcastType.FINDING,
                    payload={
                        "finding": f"Finding {i} from agent {agent_id}",
                        "data": "x" * 100,  # Some payload data
                    },
                )
        write_time = time.time() - start_time

        # Query all broadcasts
        start_time = time.time()
        all_broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        query_all_time = time.time() - start_time

        assert len(all_broadcasts) == total_broadcasts

        # Query with exclude_sender filter
        start_time = time.time()
        for agent_id in range(num_agents):
            filtered = db.get_broadcasts(
                swarm_id=swarm_id,
                exclude_sender=f"agent-{agent_id}"
            )
            # Each agent should see 90 broadcasts (all except their own 10)
            assert len(filtered) == total_broadcasts - broadcasts_per_agent
        filter_query_time = time.time() - start_time

        # Performance assertions (generous limits for CI environments)
        assert write_time < 5.0, f"Writing 100 broadcasts took {write_time:.2f}s (expected < 5s)"
        assert query_all_time < 0.5, f"Querying all broadcasts took {query_all_time:.2f}s (expected < 0.5s)"
        assert filter_query_time < 2.0, f"10 filtered queries took {filter_query_time:.2f}s (expected < 2s)"

    def test_large_swarm_50_agents(self, isolated_db: CoordinationDB, swarm_id: str):
        """Test with 50 agents, each sending 5 broadcasts."""
        db = isolated_db
        num_agents = 50
        broadcasts_per_agent = 5
        total_broadcasts = num_agents * broadcasts_per_agent

        # Create broadcasts
        for agent_id in range(num_agents):
            for i in range(broadcasts_per_agent):
                db.create_broadcast(
                    swarm_id=swarm_id,
                    sender_agent=f"agent-{agent_id}",
                    broadcast_type=BroadcastType.FINDING if i % 2 == 0 else BroadcastType.QUESTION,
                    payload={"msg": f"Broadcast {i} from agent {agent_id}"},
                )

        # Query by type
        start_time = time.time()
        findings = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING]
        )
        type_query_time = time.time() - start_time

        # Should have roughly half as FINDING (indices 0, 2, 4 = 3 per agent)
        expected_findings = num_agents * 3  # 0, 2, 4 per agent
        assert len(findings) == expected_findings
        assert type_query_time < 0.5

    def test_concurrent_reads_and_writes(self, tmp_path: Path, swarm_id: str):
        """Test concurrent access from multiple connections."""
        db_path = tmp_path / "concurrent_test.db"
        num_agents = 5
        broadcasts_per_agent = 20

        def agent_worker(agent_id: int) -> list[BroadcastRecord]:
            """Simulate an agent that writes and reads broadcasts."""
            db = CoordinationDB(db_path=db_path, session_id=f"session-{agent_id}")

            # Write broadcasts
            for i in range(broadcasts_per_agent):
                db.create_broadcast(
                    swarm_id=swarm_id,
                    sender_agent=f"agent-{agent_id}",
                    broadcast_type=BroadcastType.FINDING,
                    payload={"index": i, "agent": agent_id},
                )

            # Read broadcasts from other agents
            others = db.get_broadcasts(
                swarm_id=swarm_id,
                exclude_sender=f"agent-{agent_id}"
            )
            return others

        # Run agents concurrently
        with ThreadPoolExecutor(max_workers=num_agents) as executor:
            futures = [executor.submit(agent_worker, i) for i in range(num_agents)]
            results = [f.result() for f in futures]

        # Verify final state with fresh connection
        db = CoordinationDB(db_path=db_path, session_id="verifier")
        all_broadcasts = db.get_broadcasts(swarm_id=swarm_id)

        expected_total = num_agents * broadcasts_per_agent
        assert len(all_broadcasts) == expected_total

        # Verify each agent's broadcasts are present
        by_agent = {}
        for b in all_broadcasts:
            agent = b.sender_agent
            by_agent[agent] = by_agent.get(agent, 0) + 1

        for i in range(num_agents):
            assert by_agent[f"agent-{i}"] == broadcasts_per_agent


# ============================================================================
# Additional E2E Tests
# ============================================================================


class TestRealisticSwarmScenarios:
    """Realistic end-to-end swarm scenarios."""

    def test_research_swarm_with_synthesis(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Simulate a research swarm that gathers findings and synthesizes."""
        db = isolated_db

        # Three researchers with different perspectives
        researchers = [
            ("security-expert", "Security"),
            ("performance-expert", "Performance"),
            ("architecture-expert", "Architecture"),
        ]

        # Phase 1: Each researcher broadcasts their findings
        for agent, specialty in researchers:
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=agent,
                broadcast_type=BroadcastType.FINDING,
                payload={
                    "finding": f"{specialty} analysis complete",
                    "severity": "medium",
                    "recommendations": [f"Improve {specialty.lower()} in module X"],
                },
            )

        # Phase 2: Researchers mark themselves done
        for agent, specialty in researchers:
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=agent,
                broadcast_type=BroadcastType.DONE,
                payload={
                    "summary": f"{specialty} review completed",
                    "artifacts": {
                        "report": f"{specialty.lower()}_report.md"
                    },
                },
            )

        # Phase 3: Coordinator synthesizes
        all_findings = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING]
        )
        all_done = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.DONE]
        )

        # Verify synthesis inputs
        assert len(all_findings) == 3
        assert len(all_done) == 3

        # All recommendations can be aggregated
        all_recommendations = []
        for f in all_findings:
            all_recommendations.extend(f.payload.get("recommendations", []))
        assert len(all_recommendations) == 3

    def test_hierarchical_coordination(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test hierarchical pattern: coordinator -> specialists -> workers."""
        db = isolated_db

        # Coordinator assigns tasks
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="coordinator",
            broadcast_type=BroadcastType.FINDING,
            payload={
                "task_assignment": True,
                "tasks": {
                    "specialist-1": "Review backend code",
                    "specialist-2": "Review frontend code",
                },
            },
        )

        # Specialists report findings
        for i in [1, 2]:
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"specialist-{i}",
                broadcast_type=BroadcastType.FINDING,
                payload={"finding": f"Specialist {i} completed review"},
            )

        # Specialist 1 encounters a blocker
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="specialist-1",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "Need clarification on requirements"},
        )

        # Coordinator sees blocker
        blockers = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.BLOCKER]
        )
        assert len(blockers) == 1

        # Coordinator provides clarification
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="coordinator",
            broadcast_type=BroadcastType.FINDING,
            payload={
                "clarification": True,
                "for_agent": "specialist-1",
                "details": "The requirements are...",
            },
        )

        # All specialists complete
        for i in [1, 2]:
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"specialist-{i}",
                broadcast_type=BroadcastType.DONE,
                payload={"summary": f"Specialist {i} done"},
            )

        # Verify final state
        all_broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        done_count = sum(1 for b in all_broadcasts if b.broadcast_type == BroadcastType.DONE)
        assert done_count == 2  # Both specialists done

    def test_incremental_polling_pattern(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test pattern where agents poll for new broadcasts incrementally."""
        db = isolated_db

        # Initial broadcast
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Initial finding"},
        )

        # Agent 2 polls and notes the timestamp
        initial_broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert len(initial_broadcasts) == 1
        last_seen = initial_broadcasts[-1].created_at

        time.sleep(0.02)

        # More broadcasts come in
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-3",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New finding 1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-4",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New finding 2"},
        )

        # Agent 2 polls again with 'since' filter
        new_broadcasts = db.get_broadcasts(
            swarm_id=swarm_id,
            since=last_seen
        )

        # Should only see the 2 new broadcasts
        assert len(new_broadcasts) == 2
        assert all(b.created_at > last_seen for b in new_broadcasts)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling in broadcast flow."""

    def test_empty_swarm_operations(self, isolated_db: CoordinationDB, swarm_id: str):
        """Test operations on empty swarm."""
        db = isolated_db

        # Query empty swarm
        broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert broadcasts == []

        # Query with filters on empty swarm
        filtered = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING],
            exclude_sender="nonexistent"
        )
        assert filtered == []

    def test_unicode_in_payloads(self, isolated_db: CoordinationDB, swarm_id: str):
        """Test Unicode content in payloads."""
        db = isolated_db

        unicode_payload = {
            "finding": "Found issue in file",
            "japanese": "日本語テスト",
            "emoji": "Test passed! :-)",
            "chinese": "中文测试",
            "arabic": "اختبار",
        }

        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="unicode-agent",
            broadcast_type=BroadcastType.FINDING,
            payload=unicode_payload,
        )

        result = db.get_broadcasts(swarm_id=swarm_id)
        assert len(result) == 1
        assert result[0].payload == unicode_payload

    def test_very_long_agent_ids(self, isolated_db: CoordinationDB, swarm_id: str):
        """Test with very long agent identifiers."""
        db = isolated_db

        long_agent_id = "agent-" + "x" * 500  # 500 character agent ID

        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent=long_agent_id,
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "test"},
        )

        result = db.get_broadcasts(swarm_id=swarm_id)
        assert len(result) == 1
        assert result[0].sender_agent == long_agent_id

    def test_rapid_successive_broadcasts(
        self, isolated_db: CoordinationDB, swarm_id: str
    ):
        """Test rapid-fire broadcasts don't lose data."""
        db = isolated_db
        num_broadcasts = 50

        # Rapid-fire broadcasts
        for i in range(num_broadcasts):
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"rapid-agent-{i % 5}",
                broadcast_type=BroadcastType.FINDING,
                payload={"index": i},
            )

        # All should be persisted
        result = db.get_broadcasts(swarm_id=swarm_id)
        assert len(result) == num_broadcasts

        # Verify ordering (should be in creation order)
        indices = [b.payload["index"] for b in result]
        assert indices == list(range(num_broadcasts))
