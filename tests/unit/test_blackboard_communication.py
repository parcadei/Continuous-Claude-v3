"""
TDD Tests for Blackboard Communication.

Tests the full bi-directional communication loop using HandoffAtom
as the measurable unit for multi-agent coordination.

Test Categories:
1. Downstream Communication (Coordinator → Agent)
2. Upstream Communication (Agent → Coordinator)
3. Bi-directional Round-trip
4. Signal-to-Noise Ratio (SNR)
5. Output Understanding

Based on:
- Plan: thoughts/shared/plans/2025-12-31-blackboard-communication-testing.md
- Research: thoughts/shared/agents/blackboard-research-patterns.md
- Research: thoughts/shared/agents/blackboard-research-snr.md
"""

import json
from pathlib import Path

import pytest

from scripts.agentica_patterns.blackboard import (
    BlackboardCache,
    MessageType,
    ScopeLevel,
    SharedContextEntry,
    create_result,
    create_task,
)
from scripts.agentica_patterns.handoff_atom import (
    Choice,
    HandoffAtom,
    Outcome,
    Question,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_cache(tmp_path: Path) -> BlackboardCache:
    """Create a test blackboard cache."""
    cache_dir = tmp_path / "blackboard"
    cache = BlackboardCache("test-project", cache_dir=cache_dir)
    cache.clear()
    return cache


@pytest.fixture
def coordinator_atom() -> HandoffAtom:
    """Create a HandoffAtom from coordinator to agent."""
    return HandoffAtom(
        agent_id="coordinator",
        task_id="task-001",
        from_state="planning",
        to_state="implementing",
        pattern_id="hierarchical",
        via_pattern="spawn",
        decisions=[
            Choice(
                selected="Use async pattern",
                alternatives=["sync", "threaded"],
                rationale="Better for I/O bound tasks",
                confidence=0.9,
            )
        ],
        q_remaining=[
            Question(name="database_choice", q_value="HIGH", why="Affects persistence layer"),
            Question(name="api_format", q_value="MED", why="REST vs GraphQL"),
        ],
        metadata={"context": "Building user service"},
    )


@pytest.fixture
def agent_atom() -> HandoffAtom:
    """Create a HandoffAtom from agent back to coordinator."""
    return HandoffAtom(
        agent_id="implementer-001",
        task_id="task-001",
        from_state="implementing",
        to_state="completed",
        pattern_id="hierarchical",
        via_pattern="callback",
        decisions=[
            Choice(
                selected="PostgreSQL",
                alternatives=["SQLite", "MongoDB"],
                rationale="ACID compliance needed",
                confidence=0.95,
            )
        ],
        q_resolved=[
            Question(name="database_choice", value="PostgreSQL", q_value="HIGH"),
        ],
        q_remaining=[
            Question(name="api_format", q_value="MED", why="Still undecided"),
        ],
        artifacts=["src/models/user.py", "src/db/connection.py"],
        outcome=Outcome.PARTIAL_PLUS,
    )


# ============================================================================
# Category 1: Downstream Communication (Coordinator → Agent)
# ============================================================================


class TestDownstreamCommunication:
    """Tests for coordinator → agent message flow."""

    def test_task_atom_transmission_preserves_task_id(
        self, test_cache: BlackboardCache, coordinator_atom: HandoffAtom
    ):
        """Agent receives correct task_id from coordinator."""
        # Coordinator writes task
        entry = create_task(
            project_id="test-project",
            from_agent=coordinator_atom.agent_id,
            to_agent="implementer",
            description="Implement user service",
            data={"task_id": coordinator_atom.task_id},
        )
        test_cache.push(entry)

        # Agent polls
        entries = test_cache.poll(agent_id="implementer")
        assert len(entries) == 1
        assert entries[0].data["task_id"] == "task-001"

    def test_task_atom_transmission_preserves_from_state(
        self, test_cache: BlackboardCache, coordinator_atom: HandoffAtom
    ):
        """Agent receives correct from_state for context."""
        entry = create_task(
            project_id="test-project",
            from_agent="coordinator",
            to_agent="implementer",
            description="Continue from planning",
            data={
                "from_state": coordinator_atom.from_state,
                "to_state": coordinator_atom.to_state,
            },
        )
        test_cache.push(entry)

        entries = test_cache.poll(agent_id="implementer")
        assert entries[0].data["from_state"] == "planning"
        assert entries[0].data["to_state"] == "implementing"

    def test_morphism_channel_captures_mechanism(
        self, test_cache: BlackboardCache, coordinator_atom: HandoffAtom
    ):
        """via field captures communication mechanism."""
        # Record morphism in atom
        coordinator_atom.record_morphism(
            source="coordinator",
            target="implementer",
            via="blackboard",
            preserves=["context", "decisions"],
        )

        assert len(coordinator_atom._morphism_chain) == 1
        assert coordinator_atom._morphism_chain[0].via == "blackboard"
        assert "context" in coordinator_atom._morphism_chain[0].preserves

    def test_context_preservation_via_metadata(
        self, coordinator_atom: HandoffAtom
    ):
        """metadata flows downstream intact."""
        assert coordinator_atom.metadata["context"] == "Building user service"

        # Serialize and deserialize
        data = coordinator_atom.to_dict()
        restored = HandoffAtom.from_dict(data)
        assert restored.metadata["context"] == "Building user service"

    def test_question_propagation_to_child(
        self, coordinator_atom: HandoffAtom
    ):
        """q_remaining from parent reaches child agent."""
        assert len(coordinator_atom.q_remaining) == 2
        high_qs = coordinator_atom.q_remaining_high
        assert len(high_qs) == 1
        assert high_qs[0].name == "database_choice"


# ============================================================================
# Category 2: Upstream Communication (Agent → Coordinator)
# ============================================================================


class TestUpstreamCommunication:
    """Tests for agent → coordinator message flow."""

    def test_handoff_atom_return_is_valid(self, agent_atom: HandoffAtom):
        """Agent returns valid HandoffAtom on completion."""
        assert agent_atom.agent_id == "implementer-001"
        assert agent_atom.task_id == "task-001"
        assert agent_atom.from_state == "implementing"
        assert agent_atom.to_state == "completed"

    def test_decision_capture_includes_choices(self, agent_atom: HandoffAtom):
        """decisions[] includes choices made."""
        assert len(agent_atom.decisions) == 1
        decision = agent_atom.decisions[0]
        assert decision.selected == "PostgreSQL"
        assert "SQLite" in decision.alternatives
        assert decision.confidence == 0.95

    def test_question_resolution_populates_q_resolved(
        self, agent_atom: HandoffAtom
    ):
        """q_resolved populated with answers."""
        assert len(agent_atom.q_resolved) == 1
        resolved = agent_atom.q_resolved[0]
        assert resolved.name == "database_choice"
        assert resolved.value == "PostgreSQL"
        assert resolved.is_resolved

    def test_artifact_tracking_lists_files(self, agent_atom: HandoffAtom):
        """artifacts[] lists produced files."""
        assert len(agent_atom.artifacts) == 2
        assert "src/models/user.py" in agent_atom.artifacts
        assert "src/db/connection.py" in agent_atom.artifacts

    def test_outcome_classification_is_correct(self, agent_atom: HandoffAtom):
        """outcome enum correctly set."""
        assert agent_atom.outcome == Outcome.PARTIAL_PLUS

    def test_blackboard_result_entry_valid(
        self, test_cache: BlackboardCache, agent_atom: HandoffAtom
    ):
        """Agent can write result to blackboard."""
        result = create_result(
            project_id="test-project",
            from_agent=agent_atom.agent_id,
            task_id=agent_atom.task_id,
            success=True,
            summary="Implemented user model with PostgreSQL",
            artifacts=agent_atom.artifacts,
        )
        test_cache.push(result)

        entries = test_cache.poll()
        assert len(entries) == 1
        assert entries[0].type == MessageType.RESULT
        assert entries[0].data["success"] is True


# ============================================================================
# Category 3: Bi-directional Round-trip
# ============================================================================


class TestBidirectionalRoundtrip:
    """Tests for coordinator → agent → coordinator cycle."""

    def test_semantic_preservation_state_chain(
        self, coordinator_atom: HandoffAtom, agent_atom: HandoffAtom
    ):
        """State chain: from_state → to_state is valid through composition."""
        # Verify chain: planning → implementing → completed
        assert coordinator_atom.from_state == "planning"
        assert coordinator_atom.to_state == "implementing"
        assert agent_atom.from_state == "implementing"  # Matches coordinator's to_state
        assert agent_atom.to_state == "completed"

    def test_composition_produces_valid_lineage(
        self, coordinator_atom: HandoffAtom, agent_atom: HandoffAtom
    ):
        """atom1.compose(atom2) produces valid lineage."""
        composed = coordinator_atom.compose(agent_atom)

        # From original start to final end
        assert composed.from_state == "planning"
        assert composed.to_state == "completed"
        # Combined pattern
        assert "hierarchical" in composed.pattern_id

    def test_identity_preservation_through_chain(
        self, coordinator_atom: HandoffAtom, agent_atom: HandoffAtom
    ):
        """agent_id, task_id traceable through chain."""
        composed = coordinator_atom.compose(agent_atom)

        # Uses other's (final) agent_id
        assert composed.agent_id == "implementer-001"
        # Combined task_id preserves lineage
        assert "task-001" in composed.task_id

    def test_no_information_loss_in_composition(
        self, coordinator_atom: HandoffAtom, agent_atom: HandoffAtom
    ):
        """All decisions/questions preserved in composition."""
        composed = coordinator_atom.compose(agent_atom)

        # All decisions from both atoms
        assert len(composed.decisions) == 2
        selected_items = [d.selected for d in composed.decisions]
        assert "Use async pattern" in selected_items
        assert "PostgreSQL" in selected_items

        # All resolved questions
        assert len(composed.q_resolved) == 1  # Only agent resolved one

        # Final remaining questions
        assert len(composed.q_remaining) == 1  # From agent's remaining
        assert composed.q_remaining[0].name == "api_format"

    def test_json_roundtrip_lossless(self, coordinator_atom: HandoffAtom):
        """HandoffAtom serializes and deserializes losslessly."""
        data = coordinator_atom.to_dict()
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        restored = HandoffAtom.from_dict(restored_data)

        assert restored.agent_id == coordinator_atom.agent_id
        assert restored.task_id == coordinator_atom.task_id
        assert restored.from_state == coordinator_atom.from_state
        assert restored.to_state == coordinator_atom.to_state
        assert len(restored.decisions) == len(coordinator_atom.decisions)
        assert len(restored.q_remaining) == len(coordinator_atom.q_remaining)


# ============================================================================
# Category 4: Signal-to-Noise Ratio (SNR)
# ============================================================================


class TestSignalToNoiseRatio:
    """Tests for SNR metrics in handoff communication."""

    def test_resolution_ratio_calculation(self, agent_atom: HandoffAtom):
        """Resolution ratio: q_resolved / (q_resolved + q_remaining)."""
        total_questions = len(agent_atom.q_resolved) + len(agent_atom.q_remaining)
        resolution_ratio = len(agent_atom.q_resolved) / total_questions

        # Agent resolved 1, has 1 remaining → 0.5
        assert resolution_ratio == 0.5
        # Per research: 0.7 is "good" threshold, 0.4-0.7 is "acceptable"
        assert resolution_ratio >= 0.4  # At least acceptable

    def test_decision_confidence_mean(self, agent_atom: HandoffAtom):
        """Decision confidence: mean(d.confidence for d in decisions)."""
        if agent_atom.decisions:
            mean_confidence = sum(d.confidence for d in agent_atom.decisions) / len(
                agent_atom.decisions
            )
        else:
            mean_confidence = 0.0

        # Agent has one decision with 0.95 confidence
        assert mean_confidence == 0.95
        # Per research: 0.8 is "good" threshold
        assert mean_confidence >= 0.8

    def test_artifact_yield_calculation(self, agent_atom: HandoffAtom):
        """Artifact yield: len(artifacts) / task_complexity."""
        # Assume task complexity is estimated at 4 (typical implementation)
        task_complexity = 4
        artifact_yield = len(agent_atom.artifacts) / task_complexity

        # Agent produced 2 artifacts → yield = 0.5
        assert artifact_yield == 0.5
        # Per research: 0.5 is "good" threshold
        assert artifact_yield >= 0.5

    def test_high_question_rate_acceptable(self, agent_atom: HandoffAtom):
        """HIGH question rate: len(q_remaining_high) / len(q_remaining)."""
        if agent_atom.q_remaining:
            high_rate = len(agent_atom.q_remaining_high) / len(agent_atom.q_remaining)
        else:
            high_rate = 0.0

        # Agent has 1 remaining question, none HIGH → rate = 0
        assert high_rate == 0.0
        # Per research: < 0.3 is "good" threshold
        assert high_rate < 0.3

    def test_snr_composite_score(self, agent_atom: HandoffAtom):
        """Calculate composite SNR score per research formula."""
        # Resolution ratio
        total_q = len(agent_atom.q_resolved) + len(agent_atom.q_remaining)
        resolution_ratio = len(agent_atom.q_resolved) / total_q if total_q > 0 else 0

        # Decision confidence
        mean_confidence = (
            sum(d.confidence for d in agent_atom.decisions) / len(agent_atom.decisions)
            if agent_atom.decisions
            else 0
        )

        # Artifact yield (assume complexity = 4)
        artifact_yield = len(agent_atom.artifacts) / 4

        # HIGH question rate (inverted: lower is better)
        high_rate = (
            len(agent_atom.q_remaining_high) / len(agent_atom.q_remaining)
            if agent_atom.q_remaining
            else 0
        )

        # Outcome score (SUCCESS=1.0, PARTIAL_PLUS=0.75, etc.)
        outcome_scores = {
            Outcome.SUCCESS: 1.0,
            Outcome.PARTIAL_PLUS: 0.75,
            Outcome.PARTIAL_MINUS: 0.5,
            Outcome.BLOCKED: 0.25,
            Outcome.FAILED: 0.0,
            Outcome.DEFERRED: 0.5,
        }
        outcome_score = outcome_scores.get(agent_atom.outcome, 0.5)

        # Composite per research formula
        snr = (
            resolution_ratio * 0.25
            + mean_confidence * 0.25
            + artifact_yield * 0.20
            + (1 - high_rate) * 0.15
            + outcome_score * 0.15
        )

        # Expected: 0.5*0.25 + 0.95*0.25 + 0.5*0.20 + 1.0*0.15 + 0.75*0.15
        # = 0.125 + 0.2375 + 0.10 + 0.15 + 0.1125 = 0.725
        assert 0.7 <= snr <= 0.8  # Should be in "good" range


# ============================================================================
# Category 5: Output Understanding
# ============================================================================


class TestOutputUnderstanding:
    """Tests for coordinator's ability to parse and decide based on agent output."""

    def test_parse_correctness_from_json(self, agent_atom: HandoffAtom):
        """Coordinator can HandoffAtom.from_json(agent_output)."""
        # Serialize agent output
        json_output = json.dumps(agent_atom.to_dict())

        # Coordinator parses
        parsed = HandoffAtom.from_dict(json.loads(json_output))

        assert parsed.agent_id == "implementer-001"
        assert parsed.outcome == Outcome.PARTIAL_PLUS

    def test_decision_routing_readable(self, agent_atom: HandoffAtom):
        """Coordinator can read decisions[0].selected and branch."""
        if agent_atom.decisions:
            primary_decision = agent_atom.decisions[0].selected
        else:
            primary_decision = None

        assert primary_decision == "PostgreSQL"
        # Coordinator can branch based on this
        if primary_decision == "PostgreSQL":
            next_step = "configure_postgres"
        else:
            next_step = "configure_alternative"

        assert next_step == "configure_postgres"

    def test_blocker_detection_escalates(self):
        """Coordinator detects outcome == BLOCKED and escalates."""
        blocked_atom = HandoffAtom(
            agent_id="implementer-002",
            task_id="task-002",
            from_state="implementing",
            to_state="blocked",
            outcome=Outcome.BLOCKED,
            q_remaining=[
                Question(
                    name="missing_api_key",
                    q_value="HIGH",
                    why="Cannot access external service",
                )
            ],
        )

        assert blocked_atom.outcome == Outcome.BLOCKED
        assert len(blocked_atom.q_remaining_high) == 1

        # Coordinator escalation logic
        if blocked_atom.outcome == Outcome.BLOCKED:
            escalate = True
            blocker_reason = blocked_atom.q_remaining_high[0].why
        else:
            escalate = False
            blocker_reason = ""

        assert escalate is True
        assert "external service" in blocker_reason

    def test_continuation_logic_spawns_followup(self, agent_atom: HandoffAtom):
        """Coordinator uses q_remaining to spawn follow-up agents."""
        remaining = agent_atom.q_remaining
        assert len(remaining) == 1
        assert remaining[0].name == "api_format"

        # Coordinator spawns agent to resolve remaining question
        follow_up_tasks = [
            {"question": q.name, "priority": q.q_value}
            for q in remaining
            if not q.is_resolved
        ]

        assert len(follow_up_tasks) == 1
        assert follow_up_tasks[0]["question"] == "api_format"
        assert follow_up_tasks[0]["priority"] == "MED"


# ============================================================================
# Blackboard-Specific Tests
# ============================================================================


class TestBlackboardSpecific:
    """Tests specific to blackboard pattern implementation."""

    def test_agent_writes_to_blackboard(self, test_cache: BlackboardCache):
        """Agent can write findings to blackboard."""
        entry = SharedContextEntry(
            id="finding-001",
            project_id="test-project",
            type=MessageType.ARTIFACT,
            from_agent="researcher",
            prose="Found relevant documentation",
            data={"key": "finding", "value": "Documentation at /docs/api.md"},
            artifacts=["/docs/api.md"],
        )
        test_cache.push(entry)

        entries = test_cache.poll()
        assert len(entries) == 1
        assert entries[0].data["key"] == "finding"
        assert entries[0].data["value"] == "Documentation at /docs/api.md"

    def test_agent_reads_blackboard(self, test_cache: BlackboardCache):
        """Agent can read context from blackboard."""
        # Write context first
        entry = SharedContextEntry(
            id="context-001",
            project_id="test-project",
            type=MessageType.STATUS,
            from_agent="coordinator",
            prose="Context: Building user service",
            data={"context": "user-service"},
        )
        test_cache.push(entry)

        # Agent polls and reads
        entries = test_cache.poll(agent_id="implementer")
        assert len(entries) == 1
        assert entries[0].data["context"] == "user-service"

    def test_blackboard_convergence(self, test_cache: BlackboardCache):
        """Multiple agents can signal convergence via voting."""
        # Three agents vote
        for i in range(3):
            entry = SharedContextEntry(
                id=f"vote-{i}",
                project_id="test-project",
                type=MessageType.RESPONSE,
                from_agent=f"agent-{i}",
                data={"vote": "42", "confidence": 0.9},
            )
            test_cache.push(entry)

        # Check convergence
        votes = test_cache.poll(types=[MessageType.RESPONSE])
        assert len(votes) == 3

        # Check if all agree
        values = [v.data["vote"] for v in votes]
        converged = len(set(values)) == 1
        assert converged is True

    def test_blackboard_conflict_resolution_last_write_wins(
        self, test_cache: BlackboardCache
    ):
        """Last write wins conflict resolution."""
        # First write
        entry1 = SharedContextEntry(
            id="key-001",
            project_id="test-project",
            type=MessageType.ARTIFACT,
            from_agent="agent-1",
            data={"key": "result", "value": "A"},
        )
        test_cache.push(entry1)

        # Second write (same key semantically)
        entry2 = SharedContextEntry(
            id="key-002",
            project_id="test-project",
            type=MessageType.ARTIFACT,
            from_agent="agent-2",
            data={"key": "result", "value": "B"},
        )
        test_cache.push(entry2)

        # Get latest by timestamp
        entries = test_cache.poll(types=[MessageType.ARTIFACT])
        # Most recent is last in list
        latest = entries[-1] if entries else None

        assert latest is not None
        assert latest.data["value"] == "B"  # Last write wins

    def test_handoff_atom_composition_lineage(self):
        """HandoffAtom composition preserves full lineage."""
        atom1 = HandoffAtom(
            agent_id="agent-1",
            task_id="t1",
            from_state="A",
            to_state="B",
            decisions=[Choice(selected="option1", confidence=0.8)],
        )
        atom2 = HandoffAtom(
            agent_id="agent-2",
            task_id="t2",
            from_state="B",
            to_state="C",
            decisions=[Choice(selected="option2", confidence=0.9)],
        )

        composed = atom1.compose(atom2)

        # Lineage preserved
        assert composed.from_state == "A"
        assert composed.to_state == "C"
        assert len(composed.decisions) == 2
        assert composed.decisions[0].selected == "option1"
        assert composed.decisions[1].selected == "option2"

    def test_scope_filtering_agent_private(self, test_cache: BlackboardCache):
        """AGENT scope entries only visible to specific agent."""
        # Private message to agent-1
        private_entry = SharedContextEntry(
            id="private-001",
            project_id="test-project",
            type=MessageType.TASK,
            from_agent="coordinator",
            to_agent="agent-1",
            scope=ScopeLevel.AGENT,
            prose="Private task for agent-1",
        )
        test_cache.push(private_entry)

        # agent-1 sees it
        entries_1 = test_cache.poll(agent_id="agent-1", scope=ScopeLevel.AGENT)
        assert len(entries_1) == 1

        # agent-2 doesn't see it
        entries_2 = test_cache.poll(agent_id="agent-2", scope=ScopeLevel.AGENT)
        assert len(entries_2) == 0

    def test_system_reminder_format_compact(self):
        """to_system_reminder() produces compact format."""
        entry = SharedContextEntry(
            id="test-001",
            project_id="test-project",
            type=MessageType.TASK,
            from_agent="coordinator",
            to_agent="implementer",
            prose="Build user API",
            data={"file": "api.py"},
        )

        reminder = entry.to_system_reminder()

        assert "[TASK]" in reminder
        assert "from:coordinator" in reminder
        assert "to:implementer" in reminder
        assert "Build user API" in reminder

        # Check it's reasonably compact (under 200 chars for simple entry)
        assert len(reminder) < 200


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_atom_is_valid(self):
        """Minimal HandoffAtom with only required fields."""
        atom = HandoffAtom(
            agent_id="agent",
            task_id="task",
            from_state="start",
            to_state="end",
        )

        assert atom.agent_id == "agent"
        assert atom.decisions == []
        assert atom.q_resolved == []
        assert atom.q_remaining == []
        assert atom.artifacts == []
        assert atom.outcome == Outcome.PARTIAL_PLUS  # default

    def test_compose_with_empty_decisions(self):
        """Composition works when one atom has no decisions."""
        atom1 = HandoffAtom(
            agent_id="a1", task_id="t1", from_state="A", to_state="B"
        )
        atom2 = HandoffAtom(
            agent_id="a2",
            task_id="t2",
            from_state="B",
            to_state="C",
            decisions=[Choice(selected="x")],
        )

        composed = atom1.compose(atom2)
        assert len(composed.decisions) == 1

    def test_snr_with_no_questions(self):
        """SNR calculation handles no questions gracefully."""
        atom = HandoffAtom(
            agent_id="agent",
            task_id="task",
            from_state="start",
            to_state="end",
            # No q_resolved or q_remaining
        )

        total_q = len(atom.q_resolved) + len(atom.q_remaining)
        # Should handle division by zero
        resolution_ratio = len(atom.q_resolved) / total_q if total_q > 0 else 1.0

        assert resolution_ratio == 1.0  # No questions = fully resolved

    def test_confidence_clamping(self):
        """Confidence values clamped to [0, 1]."""
        choice = Choice(selected="test", confidence=1.5)
        assert choice.confidence == 1.0

        choice2 = Choice(selected="test", confidence=-0.5)
        assert choice2.confidence == 0.0

    def test_cache_handles_concurrent_writes(self, tmp_path: Path):
        """Cache handles rapid sequential writes."""
        cache = BlackboardCache("test-project", cache_dir=tmp_path / "bb")
        cache.clear()

        # Write many entries quickly
        for i in range(50):
            entry = SharedContextEntry(
                id=f"entry-{i}",
                project_id="test-project",
                type=MessageType.STATUS,
                from_agent=f"agent-{i}",
                prose=f"Status update {i}",
            )
            cache.push(entry)

        # Should keep only MAX_HOT_ENTRIES (default 20)
        entries = cache.poll()
        assert len(entries) <= 20
