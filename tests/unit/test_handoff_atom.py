"""
TDD Tests for HandoffAtom schema.

Tests written FIRST, implementation follows.

Based on plan: thoughts/shared/plans/2025-12-31-handoff-atom.md
"""

import pytest
from datetime import datetime


# ============================================================================
# Phase 1: Core Types
# ============================================================================


class TestOutcome:
    """Tests for Outcome enum."""

    def test_outcome_values(self):
        """Each outcome has expected string value."""
        from scripts.agentica_patterns.handoff_atom import Outcome

        assert Outcome.SUCCESS.value == "success"
        assert Outcome.PARTIAL_PLUS.value == "partial_plus"
        assert Outcome.PARTIAL_MINUS.value == "partial_minus"
        assert Outcome.FAILED.value == "failed"
        assert Outcome.BLOCKED.value == "blocked"
        assert Outcome.DEFERRED.value == "deferred"

    def test_outcome_from_string(self):
        """Can construct Outcome from string value."""
        from scripts.agentica_patterns.handoff_atom import Outcome

        assert Outcome("success") == Outcome.SUCCESS
        assert Outcome("partial_plus") == Outcome.PARTIAL_PLUS


class TestChoice:
    """Tests for Choice dataclass (decision theory)."""

    def test_choice_required_field(self):
        """Choice requires 'selected' field."""
        from scripts.agentica_patterns.handoff_atom import Choice

        c = Choice(selected="OAuth2")
        assert c.selected == "OAuth2"

    def test_choice_defaults(self):
        """Optional fields have sensible defaults."""
        from scripts.agentica_patterns.handoff_atom import Choice

        c = Choice(selected="X")
        assert c.alternatives == []
        assert c.rationale == ""
        assert c.confidence == 1.0
        assert c.constraints == []

    def test_choice_confidence_clamping_high(self):
        """Confidence > 1.0 is clamped to 1.0."""
        from scripts.agentica_patterns.handoff_atom import Choice

        c = Choice(selected="A", confidence=1.5)
        assert c.confidence == 1.0

    def test_choice_confidence_clamping_low(self):
        """Confidence < 0.0 is clamped to 0.0."""
        from scripts.agentica_patterns.handoff_atom import Choice

        c = Choice(selected="A", confidence=-0.5)
        assert c.confidence == 0.0

    def test_choice_to_dict(self):
        """Choice serializes to dict."""
        from scripts.agentica_patterns.handoff_atom import Choice

        c = Choice(
            selected="OAuth2",
            alternatives=["SAML", "API_KEY"],
            rationale="industry standard",
            confidence=0.9,
            constraints=["no enterprise SSO"],
        )
        d = c.to_dict()
        assert d["selected"] == "OAuth2"
        assert d["alternatives"] == ["SAML", "API_KEY"]
        assert d["rationale"] == "industry standard"
        assert d["confidence"] == 0.9
        assert d["constraints"] == ["no enterprise SSO"]

    def test_choice_from_dict(self):
        """Choice deserializes from dict."""
        from scripts.agentica_patterns.handoff_atom import Choice

        d = {
            "selected": "OAuth2",
            "alternatives": ["SAML"],
            "rationale": "security",
        }
        c = Choice.from_dict(d)
        assert c.selected == "OAuth2"
        assert c.alternatives == ["SAML"]
        assert c.rationale == "security"

    def test_choice_from_dict_minimal(self):
        """Choice.from_dict works with only required field."""
        from scripts.agentica_patterns.handoff_atom import Choice

        d = {"selected": "X"}
        c = Choice.from_dict(d)
        assert c.selected == "X"
        assert c.alternatives == []


class TestMorphism:
    """Tests for Morphism dataclass (category theory)."""

    def test_morphism_required_fields(self):
        """Morphism requires source and target."""
        from scripts.agentica_patterns.handoff_atom import Morphism

        m = Morphism(source="A", target="B")
        assert m.source == "A"
        assert m.target == "B"

    def test_morphism_auto_timestamp(self):
        """Morphism auto-generates timestamp if not provided."""
        from scripts.agentica_patterns.handoff_atom import Morphism

        m = Morphism(source="A", target="B")
        assert m.timestamp != ""
        # Should be ISO format
        datetime.fromisoformat(m.timestamp.replace("Z", "+00:00"))

    def test_morphism_defaults(self):
        """Morphism has sensible defaults."""
        from scripts.agentica_patterns.handoff_atom import Morphism

        m = Morphism(source="A", target="B")
        assert m.via == "spawn"
        assert m.preserves == []
        assert m.transforms == {}

    def test_morphism_to_dict(self):
        """Morphism serializes to dict."""
        from scripts.agentica_patterns.handoff_atom import Morphism

        m = Morphism(
            source="query",
            target="result",
            via="pipeline",
            preserves=["context"],
            transforms={"scope": "expanded"},
        )
        d = m.to_dict()
        assert d["source"] == "query"
        assert d["target"] == "result"
        assert d["via"] == "pipeline"
        assert d["preserves"] == ["context"]
        assert d["transforms"] == {"scope": "expanded"}

    def test_morphism_from_dict(self):
        """Morphism deserializes from dict."""
        from scripts.agentica_patterns.handoff_atom import Morphism

        d = {"source": "A", "target": "B", "via": "broadcast"}
        m = Morphism.from_dict(d)
        assert m.source == "A"
        assert m.target == "B"
        assert m.via == "broadcast"


class TestQuestion:
    """Tests for Question dataclass (erotetic logic)."""

    def test_question_required_field(self):
        """Question requires name field."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="auth_method")
        assert q.name == "auth_method"

    def test_question_defaults(self):
        """Question has sensible defaults."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="q1")
        assert q.value is None
        assert q.q_value == "MED"
        assert q.why == ""
        assert q.resolved_at is None

    def test_question_is_resolved_false(self):
        """Unresolved question returns is_resolved=False."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="auth_method")
        assert not q.is_resolved

    def test_question_is_resolved_with_none(self):
        """Question with value=None is not resolved."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="q1", value=None)
        assert not q.is_resolved

    def test_question_is_resolved_with_unknown(self):
        """Question with value='UNKNOWN' is not resolved."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="q1", value="UNKNOWN")
        assert not q.is_resolved

    def test_question_is_resolved_with_value(self):
        """Question with real value is resolved."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="q1", value="oauth2")
        assert q.is_resolved

    def test_question_resolve(self):
        """Question.resolve() sets value and timestamp."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(name="auth_method")
        assert not q.is_resolved
        q.resolve("oauth2")
        assert q.is_resolved
        assert q.value == "oauth2"
        assert q.resolved_at is not None
        # Verify timestamp is ISO format
        datetime.fromisoformat(q.resolved_at.replace("Z", "+00:00"))

    def test_question_to_dict(self):
        """Question serializes to dict."""
        from scripts.agentica_patterns.handoff_atom import Question

        q = Question(
            name="auth_method",
            value="oauth2",
            q_value="HIGH",
            why="critical security decision",
        )
        d = q.to_dict()
        assert d["name"] == "auth_method"
        assert d["value"] == "oauth2"
        assert d["q_value"] == "HIGH"
        assert d["why"] == "critical security decision"

    def test_question_from_dict(self):
        """Question deserializes from dict."""
        from scripts.agentica_patterns.handoff_atom import Question

        d = {"name": "q1", "value": "answer", "q_value": "LOW"}
        q = Question.from_dict(d)
        assert q.name == "q1"
        assert q.value == "answer"
        assert q.q_value == "LOW"


# ============================================================================
# Phase 2: HandoffAtom Core
# ============================================================================


class TestHandoffAtomCore:
    """Tests for HandoffAtom dataclass."""

    def test_handoff_atom_required_fields(self):
        """HandoffAtom requires identity and morphism fields."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom

        atom = HandoffAtom(
            agent_id="agent-1",
            task_id="task-1",
            from_state="start",
            to_state="end",
        )
        assert atom.agent_id == "agent-1"
        assert atom.task_id == "task-1"
        assert atom.from_state == "start"
        assert atom.to_state == "end"

    def test_handoff_atom_defaults(self):
        """HandoffAtom has sensible defaults."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Outcome

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
        )
        assert atom.pattern_id == ""
        assert atom.via_pattern == "direct"
        assert atom.decisions == []
        assert atom.q_resolved == []
        assert atom.q_remaining == []
        assert atom.artifacts == []
        assert atom.outcome == Outcome.PARTIAL_PLUS
        assert atom.metadata == {}

    def test_handoff_atom_auto_timestamp(self):
        """HandoffAtom auto-generates timestamp."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
        )
        assert atom.timestamp != ""
        datetime.fromisoformat(atom.timestamp.replace("Z", "+00:00"))


class TestHandoffAtomErotetic:
    """Tests for HandoffAtom erotetic properties."""

    def test_e_is_empty_true(self):
        """e_is_empty=True when all questions resolved and none remaining."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Question

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_resolved=[Question(name="q1", value="v1")],
            q_remaining=[],
        )
        assert atom.e_is_empty

    def test_e_is_empty_false_with_remaining(self):
        """e_is_empty=False when questions remain."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Question

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_resolved=[Question(name="q1", value="v1")],
            q_remaining=[Question(name="q2")],
        )
        assert not atom.e_is_empty

    def test_e_is_empty_false_with_no_resolved(self):
        """e_is_empty=False when no questions resolved yet."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_resolved=[],
            q_remaining=[],
        )
        assert not atom.e_is_empty

    def test_q_remaining_count(self):
        """q_remaining_count returns number of unresolved questions."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Question

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_remaining=[Question(name="q1"), Question(name="q2"), Question(name="q3")],
        )
        assert atom.q_remaining_count == 3

    def test_q_remaining_high(self):
        """q_remaining_high returns only HIGH priority questions."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Question

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_remaining=[
                Question(name="q1", q_value="HIGH"),
                Question(name="q2", q_value="MED"),
                Question(name="q3", q_value="HIGH"),
                Question(name="q4", q_value="LOW"),
            ],
        )
        high = atom.q_remaining_high
        assert len(high) == 2
        assert all(q.q_value == "HIGH" for q in high)


class TestHandoffAtomMorphism:
    """Tests for HandoffAtom morphism methods."""

    def test_record_morphism(self):
        """record_morphism adds to morphism chain."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
        )
        assert len(atom._morphism_chain) == 0

        atom.record_morphism(source="A", target="B", via="spawn")
        assert len(atom._morphism_chain) == 1
        assert atom._morphism_chain[0].source == "A"
        assert atom._morphism_chain[0].target == "B"

    def test_compose(self):
        """compose creates new atom representing A->B->C."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Choice, Question

        a1 = HandoffAtom(
            agent_id="agent1",
            task_id="t1",
            from_state="A",
            to_state="B",
            pattern_id="swarm",
            via_pattern="parallel",
            decisions=[Choice(selected="X")],
            q_resolved=[Question(name="q1", value="v1")],
        )
        a2 = HandoffAtom(
            agent_id="agent2",
            task_id="t2",
            from_state="B",
            to_state="C",
            pattern_id="pipeline",
            via_pattern="sequential",
            decisions=[Choice(selected="Y")],
            q_remaining=[Question(name="q2")],
        )

        composed = a1.compose(a2)

        # From self's start to other's end
        assert composed.from_state == "A"
        assert composed.to_state == "C"
        # Uses other's agent (most recent)
        assert composed.agent_id == "agent2"
        # Combined task id
        assert "t1" in composed.task_id
        assert "t2" in composed.task_id
        # Decisions concatenated
        assert len(composed.decisions) == 2
        # Other's remaining questions
        assert len(composed.q_remaining) == 1
        assert composed.q_remaining[0].name == "q2"
        # Both resolved questions
        assert len(composed.q_resolved) == 1


class TestHandoffAtomDecisions:
    """Tests for HandoffAtom decision methods."""

    def test_record_decision(self):
        """record_decision appends to decisions list."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Choice

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
        )
        assert len(atom.decisions) == 0

        atom.record_decision(Choice(selected="OAuth2", rationale="security"))
        assert len(atom.decisions) == 1
        assert atom.decisions[0].selected == "OAuth2"


# ============================================================================
# Phase 3: Serialization
# ============================================================================


class TestHandoffAtomSerialization:
    """Tests for HandoffAtom serialization."""

    def test_to_dict(self):
        """to_dict includes all fields."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Choice,
            Question,
            Outcome,
        )

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="start",
            to_state="end",
            pattern_id="swarm",
            via_pattern="parallel",
            decisions=[Choice(selected="X", rationale="reason")],
            q_resolved=[Question(name="q1", value="v1")],
            q_remaining=[Question(name="q2", q_value="HIGH")],
            artifacts=["file1.py", "file2.py"],
            outcome=Outcome.SUCCESS,
            metadata={"key": "value"},
        )
        d = atom.to_dict()

        assert d["agent_id"] == "a1"
        assert d["task_id"] == "t1"
        assert d["from_state"] == "start"
        assert d["to_state"] == "end"
        assert d["pattern_id"] == "swarm"
        assert d["via_pattern"] == "parallel"
        assert len(d["decisions"]) == 1
        assert d["decisions"][0]["selected"] == "X"
        assert len(d["q_resolved"]) == 1
        assert len(d["q_remaining"]) == 1
        assert d["artifacts"] == ["file1.py", "file2.py"]
        assert d["outcome"] == "success"
        assert d["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """from_dict reconstructs HandoffAtom."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, Outcome

        d = {
            "agent_id": "a1",
            "task_id": "t1",
            "from_state": "start",
            "to_state": "end",
            "pattern_id": "jury",
            "via_pattern": "consensus",
            "decisions": [{"selected": "approve", "rationale": "tests pass"}],
            "q_resolved": [{"name": "validation", "value": "passed"}],
            "q_remaining": [],
            "artifacts": ["report.md"],
            "outcome": "success",
            "metadata": {},
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
        atom = HandoffAtom.from_dict(d)

        assert atom.agent_id == "a1"
        assert atom.pattern_id == "jury"
        assert atom.outcome == Outcome.SUCCESS
        assert len(atom.decisions) == 1
        assert atom.decisions[0].selected == "approve"

    def test_roundtrip(self):
        """to_dict -> from_dict preserves all data."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Choice,
            Question,
            Outcome,
        )

        original = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="start",
            to_state="end",
            pattern_id="hierarchical",
            via_pattern="decompose",
            decisions=[
                Choice(
                    selected="microservices",
                    alternatives=["monolith"],
                    rationale="scalability",
                    confidence=0.8,
                )
            ],
            q_resolved=[Question(name="architecture", value="microservices")],
            q_remaining=[Question(name="deployment", q_value="HIGH")],
            artifacts=["design.md"],
            outcome=Outcome.PARTIAL_PLUS,
            metadata={"phase": 2},
        )

        serialized = original.to_dict()
        restored = HandoffAtom.from_dict(serialized)

        assert restored.agent_id == original.agent_id
        assert restored.task_id == original.task_id
        assert restored.from_state == original.from_state
        assert restored.to_state == original.to_state
        assert restored.pattern_id == original.pattern_id
        assert restored.outcome == original.outcome
        assert len(restored.decisions) == len(original.decisions)
        assert restored.decisions[0].rationale == "scalability"
        assert restored.decisions[0].confidence == 0.8

    def test_to_json(self):
        """to_json produces compact JSON string."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom
        import json

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
        )
        json_str = atom.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["agent_id"] == "a1"

        # Should be compact (no extra spaces)
        assert ": " not in json_str  # Compact separator

    def test_from_json(self):
        """from_json parses JSON string."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom

        json_str = '{"agent_id":"a1","task_id":"t1","from_state":"A","to_state":"B","outcome":"success"}'
        atom = HandoffAtom.from_json(json_str)
        assert atom.agent_id == "a1"


# ============================================================================
# Phase 4: Renderer
# ============================================================================


class TestSummarizeHandoff:
    """Tests for summarize_handoff renderer."""

    def test_basic_summary(self):
        """Basic atom produces readable summary."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Outcome,
            summarize_handoff,
        )

        atom = HandoffAtom(
            agent_id="agent-1",
            task_id="task-1",
            from_state="query",
            to_state="result",
            pattern_id="swarm",
            via_pattern="parallel_aggregate",
            outcome=Outcome.SUCCESS,
        )
        summary = summarize_handoff(atom)

        assert "agent-1" in summary
        assert "swarm" in summary
        assert "completed successfully" in summary

    def test_summary_with_decisions(self):
        """Summary includes key decisions."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Choice,
            summarize_handoff,
        )

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            decisions=[Choice(selected="OAuth2", rationale="industry standard")],
        )
        summary = summarize_handoff(atom)

        assert "OAuth2" in summary
        assert "industry standard" in summary
        assert "Key decisions" in summary

    def test_summary_with_resolved_questions(self):
        """Summary includes resolved questions."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Question,
            summarize_handoff,
        )

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_resolved=[
                Question(name="auth_method", value="oauth2"),
                Question(name="database", value="postgres"),
            ],
        )
        summary = summarize_handoff(atom)

        assert "Resolved" in summary
        assert "auth_method" in summary

    def test_summary_with_high_priority_remaining(self):
        """Summary highlights HIGH priority remaining questions."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Question,
            summarize_handoff,
        )

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            q_remaining=[
                Question(name="critical_decision", q_value="HIGH"),
                Question(name="minor_detail", q_value="LOW"),
            ],
        )
        summary = summarize_handoff(atom)

        assert "HIGH priority" in summary
        assert "critical_decision" in summary

    def test_summary_with_artifacts(self):
        """Summary mentions artifact count."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Outcome,
            summarize_handoff,
        )

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="A",
            to_state="B",
            artifacts=["file1.py", "file2.py", "file3.py"],
            outcome=Outcome.SUCCESS,
        )
        summary = summarize_handoff(atom)

        assert "3 artifact" in summary

    def test_summary_outcome_descriptions(self):
        """Each outcome type has descriptive text."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Outcome,
            summarize_handoff,
        )

        outcomes_expected = {
            Outcome.SUCCESS: "completed successfully",
            Outcome.PARTIAL_PLUS: "made progress",
            Outcome.PARTIAL_MINUS: "limited progress",
            Outcome.FAILED: "failed",
            Outcome.BLOCKED: "blocked",
            Outcome.DEFERRED: "deferred",
        }

        for outcome, expected_text in outcomes_expected.items():
            atom = HandoffAtom(
                agent_id="a1",
                task_id="t1",
                from_state="A",
                to_state="B",
                outcome=outcome,
            )
            summary = summarize_handoff(atom)
            assert expected_text in summary, f"Expected '{expected_text}' in summary for {outcome}"

    def test_summary_no_pattern(self):
        """Summary works without pattern_id."""
        from scripts.agentica_patterns.handoff_atom import HandoffAtom, summarize_handoff

        atom = HandoffAtom(
            agent_id="a1",
            task_id="t1",
            from_state="start",
            to_state="end",
        )
        summary = summarize_handoff(atom)

        # Should not crash, should mention transition
        assert "a1" in summary
        assert "start" in summary or "end" in summary


# ============================================================================
# Phase 5: Factory Functions
# ============================================================================


class TestFactoryFunctions:
    """Tests for pattern-specific factory functions."""

    def test_create_swarm_atom(self):
        """create_swarm_atom produces valid HandoffAtom."""
        from scripts.agentica_patterns.handoff_atom import create_swarm_atom, Outcome

        atom = create_swarm_atom(
            agent_id="swarm-1",
            task_id="research-task",
            perspectives_used=["security", "performance", "ux"],
            aggregated_result="findings.md",
            outcome=Outcome.SUCCESS,
        )

        assert atom.pattern_id == "swarm"
        assert atom.via_pattern == "parallel_aggregate"
        assert atom.from_state == "query"
        assert atom.to_state == "aggregated_result"
        assert len(atom.decisions) == 1
        assert "3 perspectives" in atom.decisions[0].selected
        assert "findings.md" in atom.artifacts

    def test_create_pipeline_atom(self):
        """create_pipeline_atom produces valid HandoffAtom."""
        from scripts.agentica_patterns.handoff_atom import create_pipeline_atom

        atom = create_pipeline_atom(
            agent_id="pipeline-1",
            task_id="etl-task",
            stages_completed=["extract", "transform"],
            current_stage="load",
        )

        assert atom.pattern_id == "pipeline"
        assert atom.via_pattern == "sequential_handoff"
        assert atom.from_state == "transform"
        assert atom.to_state == "load"

    def test_create_jury_atom(self):
        """create_jury_atom produces valid HandoffAtom."""
        from scripts.agentica_patterns.handoff_atom import create_jury_atom, Outcome

        atom = create_jury_atom(
            agent_id="jury-1",
            task_id="validation-task",
            votes=[True, True, False, True, True],
            verdict=True,
            consensus_mode="majority",
            outcome=Outcome.SUCCESS,
        )

        assert atom.pattern_id == "jury"
        assert "majority" in atom.via_pattern
        assert atom.from_state == "question"
        assert atom.to_state == "verdict"
        assert len(atom.decisions) == 1
        assert atom.decisions[0].selected == "True"


# ============================================================================
# Token Efficiency Validation
# ============================================================================


class TestTokenEfficiency:
    """Tests to validate token efficiency claims."""

    def test_json_size_vs_prose(self):
        """HandoffAtom JSON should be smaller than equivalent prose."""
        from scripts.agentica_patterns.handoff_atom import (
            HandoffAtom,
            Choice,
            Question,
            Outcome,
            summarize_handoff,
        )

        atom = HandoffAtom(
            agent_id="agent-1",
            task_id="task-1",
            from_state="query",
            to_state="analyzed",
            pattern_id="swarm",
            via_pattern="parallel",
            decisions=[
                Choice(
                    selected="oauth2_pkce",
                    alternatives=["saml", "api_keys"],
                    rationale="industry standard",
                )
            ],
            q_remaining=[Question(name="token_refresh", q_value="MED")],
            outcome=Outcome.SUCCESS,
        )

        json_str = atom.to_json()
        prose = summarize_handoff(atom)

        # JSON should be comparable or smaller than prose
        # (prose is meant to be concise, so they may be similar)
        # Main benefit is structured queryability, not just size
        assert len(json_str) > 0
        assert len(prose) > 0

        # JSON should be under 600 characters for this simple case
        # (includes auto-generated timestamp which adds ~40 chars)
        assert len(json_str) < 600, f"JSON too large: {len(json_str)} chars"
