"""Tests for temporal handoff generation and parsing.

Implements TDD for Phases 5.1-5.3:
- 5.1: TemporalHandoffState dataclass
- 5.2: Handoff parser
- 5.3: File loading
"""
import pytest
from pathlib import Path

from scripts.temporal_memory.handoff import (
    TemporalHandoffState,
    parse_temporal_handoff,
    load_temporal_handoff,
)


class TestTemporalHandoffState:
    """Phase 5.1: TemporalHandoffState dataclass tests."""

    def test_create_empty_handoff(self):
        """Empty handoff should have sensible defaults."""
        handoff = TemporalHandoffState()
        assert handoff.context == ""
        assert handoff.next_instruction == ""
        assert handoff.invariants == {}
        assert handoff.current_state == {}
        assert handoff.eventualities == []
        assert handoff.open_questions == []
        assert handoff.transitions == []
        assert handoff.turn_count == 0

    def test_create_populated_handoff(self):
        """Populated handoff preserves all fields."""
        handoff = TemporalHandoffState(
            context="Implementing temporal memory",
            next_instruction="Complete Phase 3",
            invariants={"db": "sqlite", "framework": "agentica"},
            current_state={"phase": "testing"},
            eventualities=["tests_pass", "docs_complete"],
            open_questions=[("auth_method", "HIGH", "Blocking decision")],
            transitions=["T=3: phase=planning -> phase=testing"],
            turn_count=5,
        )
        assert handoff.context == "Implementing temporal memory"
        assert handoff.turn_count == 5
        assert len(handoff.invariants) == 2
        assert handoff.invariants["db"] == "sqlite"
        assert handoff.current_state["phase"] == "testing"
        assert len(handoff.eventualities) == 2
        assert len(handoff.open_questions) == 1
        assert len(handoff.transitions) == 1

    def test_to_markdown_header(self):
        """Markdown output includes turn count in header."""
        handoff = TemporalHandoffState(turn_count=10)
        md = handoff.to_markdown()
        assert "# Temporal Handoff (Turn 10)" in md

    def test_to_markdown_open_questions_section(self):
        """Open questions are formatted as a table with priority."""
        handoff = TemporalHandoffState(
            open_questions=[
                ("auth_method", "HIGH", "Architectural decision"),
                ("cache_type", "MED", "Performance impact"),
            ]
        )
        md = handoff.to_markdown()
        assert "## Open Questions" in md
        assert "auth_method" in md
        assert "HIGH" in md
        assert "Architectural decision" in md
        assert "cache_type" in md
        assert "MED" in md

    def test_to_markdown_invariants_section(self):
        """Invariants are formatted as a table."""
        handoff = TemporalHandoffState(invariants={"db": "sqlite", "api": "rest"})
        md = handoff.to_markdown()
        assert "## Invariants" in md
        assert "db" in md
        assert "sqlite" in md
        assert "api" in md

    def test_to_markdown_current_state_section(self):
        """Current state is formatted as a table."""
        handoff = TemporalHandoffState(current_state={"phase": "testing"})
        md = handoff.to_markdown()
        assert "## Current State" in md
        assert "phase" in md
        assert "testing" in md

    def test_to_markdown_pending_goals_section(self):
        """Pending goals are formatted as checkbox list."""
        handoff = TemporalHandoffState(eventualities=["goal_tests", "goal_docs"])
        md = handoff.to_markdown()
        assert "## Pending Goals" in md
        assert "- [ ] goal_tests" in md
        assert "- [ ] goal_docs" in md

    def test_to_markdown_transitions_section(self):
        """Transitions are listed in Recent Transitions section."""
        handoff = TemporalHandoffState(
            transitions=["T=1: a=1 -> a=2", "T=2: b=x -> b=y"]
        )
        md = handoff.to_markdown()
        assert "## Recent Transitions" in md
        assert "T=1: a=1 -> a=2" in md
        assert "T=2: b=x -> b=y" in md

    def test_to_markdown_context_section(self):
        """Context section contains the context string."""
        handoff = TemporalHandoffState(
            context="Working on memory system implementation"
        )
        md = handoff.to_markdown()
        assert "## Context" in md
        assert "Working on memory system implementation" in md

    def test_to_markdown_instruction_section(self):
        """Next instruction section contains the instruction."""
        handoff = TemporalHandoffState(
            next_instruction="Complete the summarizer tests"
        )
        md = handoff.to_markdown()
        assert "## Next Instruction" in md
        assert "Complete the summarizer tests" in md

    def test_from_summary(self):
        """Create handoff from TemporalSummary output."""
        summary = {
            "open_questions_ranked": [("db_type", "HIGH", "Critical")],
            "pending_goals": ["goal_tests"],
            "transitions": ["T=1: a -> b"],
            "current_state": {"db": "sqlite"},
            "turn_count": 3,
        }
        handoff = TemporalHandoffState.from_summary(
            summary=summary, context="Test context", instruction="Test instruction"
        )
        assert handoff.turn_count == 3
        assert handoff.context == "Test context"
        assert handoff.next_instruction == "Test instruction"
        assert len(handoff.open_questions) == 1
        assert handoff.open_questions[0][0] == "db_type"
        assert "goal_tests" in handoff.eventualities
        assert handoff.invariants == {}
        assert handoff.current_state["db"] == "sqlite"

    def test_from_summary_empty(self):
        """from_summary handles empty summary gracefully."""
        summary = {}
        handoff = TemporalHandoffState.from_summary(
            summary=summary, context="", instruction=""
        )
        assert handoff.turn_count == 0
        assert handoff.open_questions == []
        assert handoff.invariants == {}
        assert handoff.current_state == {}

    def test_to_markdown_all_sections_present(self):
        """Full handoff produces all expected sections."""
        handoff = TemporalHandoffState(
            context="Full test",
            next_instruction="Do everything",
            invariants={"key": "value"},
            current_state={"phase": "init"},
            eventualities=["goal"],
            open_questions=[("q", "HIGH", "important")],
            transitions=["T=1: x -> y"],
            turn_count=7,
        )
        md = handoff.to_markdown()

        # Verify all sections present
        sections = [
            "# Temporal Handoff",
            "## Open Questions",
            "## Invariants",
            "## Current State",
            "## Pending Goals",
            "## Recent Transitions",
            "## Context",
            "## Next Instruction",
        ]
        for section in sections:
            assert section in md, f"Missing section: {section}"


class TestParseTemporalHandoff:
    """Phase 5.2: Handoff parser tests."""

    def test_parse_open_questions_table(self):
        """Parser extracts open questions from table format."""
        content = """
# Temporal Handoff (Turn 5)

## Open Questions (E(X,Q) - PRIORITY)
| Question | Q-Value | Why Ask First |
|----------|---------|---------------|
| auth_method | HIGH | Blocking decision |
| cache_type | MED | Performance |
"""
        result = parse_temporal_handoff(content)
        assert len(result["open_questions"]) == 2
        assert result["open_questions"][0] == (
            "auth_method",
            "HIGH",
            "Blocking decision",
        )
        assert result["open_questions"][1] == ("cache_type", "MED", "Performance")

    def test_parse_invariants_table(self):
        """Parser extracts invariants from table format."""
        content = """
## Invariants (Always)
| Property | Value |
|----------|-------|
| db | sqlite |
| api | rest |
"""
        result = parse_temporal_handoff(content)
        assert result["invariants"]["db"] == "sqlite"
        assert result["invariants"]["api"] == "rest"

    def test_parse_current_state_table(self):
        """Parser extracts current state from table format."""
        content = """
## Current State (Snapshot)
| Property | Value |
|----------|-------|
| phase | testing |
| db | sqlite |
"""
        result = parse_temporal_handoff(content)
        assert result["current_state"]["phase"] == "testing"
        assert result["current_state"]["db"] == "sqlite"

    def test_parse_pending_goals(self):
        """Parser extracts only unchecked goals."""
        content = """
## Pending Goals
- [ ] goal_tests
- [ ] goal_docs
- [x] goal_setup
"""
        result = parse_temporal_handoff(content)
        assert "goal_tests" in result["pending_goals"]
        assert "goal_docs" in result["pending_goals"]
        # Only unchecked goals
        assert "goal_setup" not in result["pending_goals"]

    def test_parse_transitions(self):
        """Parser extracts transitions from list format."""
        content = """
## Recent Transitions
- T=1: phase=planning -> phase=testing
- T=2: db=none -> db=sqlite
"""
        result = parse_temporal_handoff(content)
        assert len(result["transitions"]) == 2
        assert "phase=planning -> phase=testing" in result["transitions"][0]
        assert "db=none -> db=sqlite" in result["transitions"][1]

    def test_parse_context(self):
        """Parser extracts multi-line context."""
        content = """
## Context
Working on the temporal memory system.
This is multi-line context.

## Next Instruction
Complete the tests.
"""
        result = parse_temporal_handoff(content)
        assert "temporal memory system" in result["context"]
        assert "multi-line context" in result["context"]

    def test_parse_instruction(self):
        """Parser extracts next instruction."""
        content = """
## Next Instruction
Complete the summarizer tests and run validation.
"""
        result = parse_temporal_handoff(content)
        assert "summarizer tests" in result["next_instruction"]
        assert "run validation" in result["next_instruction"]

    def test_parse_empty_sections(self):
        """Parser handles document with no sections."""
        content = "# Temporal Handoff (Turn 0)"
        result = parse_temporal_handoff(content)
        assert result["open_questions"] == []
        assert result["invariants"] == {}
        assert result["current_state"] == {}
        assert result["pending_goals"] == []
        assert result["transitions"] == []
        assert result["context"] == ""
        assert result["next_instruction"] == ""

    def test_parse_turn_count(self):
        """Parser extracts turn count from header."""
        content = "# Temporal Handoff (Turn 42)"
        result = parse_temporal_handoff(content)
        assert result["turn_count"] == 42

    def test_parse_turn_count_default(self):
        """Parser defaults turn count to 0 if not found."""
        content = "# Some Other Header"
        result = parse_temporal_handoff(content)
        assert result["turn_count"] == 0

    def test_round_trip(self):
        """Test that to_markdown -> parse recovers data."""
        original = TemporalHandoffState(
            context="Test context",
            next_instruction="Test instruction",
            invariants={"db": "sqlite"},
            current_state={"phase": "testing"},
            eventualities=["goal_tests"],
            open_questions=[("auth", "HIGH", "Important")],
            transitions=["T=1: a -> b"],
            turn_count=5,
        )
        md = original.to_markdown()
        parsed = parse_temporal_handoff(md)

        assert parsed["context"] == "Test context"
        assert parsed["next_instruction"] == "Test instruction"
        assert parsed["invariants"]["db"] == "sqlite"
        assert parsed["current_state"]["phase"] == "testing"
        assert "goal_tests" in parsed["pending_goals"]
        assert len(parsed["open_questions"]) == 1
        assert parsed["open_questions"][0][0] == "auth"
        assert len(parsed["transitions"]) == 1
        assert parsed["turn_count"] == 5

    def test_parse_handles_extra_whitespace(self):
        """Parser is resilient to extra whitespace."""
        content = """
## Open Questions (E(X,Q) - PRIORITY)
| Question | Q-Value | Why Ask First |
|----------|---------|---------------|
|  auth_method  |  HIGH  |  Important choice  |
"""
        result = parse_temporal_handoff(content)
        assert len(result["open_questions"]) == 1
        q, qv, why = result["open_questions"][0]
        assert q == "auth_method"
        assert qv == "HIGH"
        assert why == "Important choice"

    def test_parse_invariants_with_complex_values(self):
        """Parser handles invariant values with special characters."""
        content = """
## Invariants (Always)
| Property | Value |
|----------|-------|
| config_path | /tmp/config.json |
| pattern | key=value |
"""
        result = parse_temporal_handoff(content)
        assert result["invariants"]["config_path"] == "/tmp/config.json"
        assert result["invariants"]["pattern"] == "key=value"


class TestLoadTemporalHandoff:
    """Phase 5.3: Load handoff from file."""

    def test_load_nonexistent_session(self, tmp_path):
        """Loading nonexistent session returns None."""
        result = load_temporal_handoff("nonexistent", base_dir=tmp_path)
        assert result is None

    def test_load_temporal_handoff(self, tmp_path):
        """Load and parse temporal handoff from file."""
        # Create handoff directory and file
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "test-session"
        session_dir.mkdir(parents=True)

        handoff_file = session_dir / "2025-01-01_handoff.md"
        handoff_file.write_text(
            """
# Temporal Handoff (Turn 3)

## Open Questions (E(X,Q) - PRIORITY)
| Question | Q-Value | Why Ask First |
|----------|---------|---------------|
| db_type | HIGH | Critical |

## Invariants (Always)
| Property | Value |
|----------|-------|
| framework | agentica |

## Pending Goals
- [ ] tests_pass

## Context
Test session context.

## Next Instruction
Continue implementation.
"""
        )

        result = load_temporal_handoff("test-session", base_dir=tmp_path)
        assert result is not None
        assert "framework" in result.invariants
        assert result.invariants["framework"] == "agentica"
        assert len(result.open_questions) == 1
        assert "tests_pass" in result.eventualities
        assert "Test session context" in result.context

    def test_load_prefers_temporal_over_legacy(self, tmp_path):
        """Loader picks temporal handoff over legacy format."""
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "test-session"
        session_dir.mkdir(parents=True)

        # Create legacy handoff (older)
        legacy = session_dir / "2025-01-01_legacy.md"
        legacy.write_text("# Regular Handoff\nSome content")

        # Create temporal handoff (more recent)
        temporal = session_dir / "2025-01-02_temporal.md"
        temporal.write_text(
            """
# Temporal Handoff (Turn 5)

## Context
Temporal context.
"""
        )

        result = load_temporal_handoff("test-session", base_dir=tmp_path)
        assert result is not None
        assert "Temporal context" in result.context

    def test_load_empty_directory(self, tmp_path):
        """Loading from empty directory returns None."""
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "empty-session"
        session_dir.mkdir(parents=True)

        result = load_temporal_handoff("empty-session", base_dir=tmp_path)
        assert result is None

    def test_load_only_legacy_handoffs(self, tmp_path):
        """Returns None if only legacy (non-temporal) handoffs exist."""
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "legacy-session"
        session_dir.mkdir(parents=True)

        # Create only legacy handoffs
        legacy = session_dir / "2025-01-01_handoff.md"
        legacy.write_text("# Regular Handoff\nSome content without temporal marker")

        result = load_temporal_handoff("legacy-session", base_dir=tmp_path)
        assert result is None

    def test_load_extracts_turn_count(self, tmp_path):
        """Loader extracts turn count from header."""
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "turn-session"
        session_dir.mkdir(parents=True)

        handoff_file = session_dir / "handoff.md"
        handoff_file.write_text(
            """
# Temporal Handoff (Turn 42)

## Context
Turn count test.
"""
        )

        result = load_temporal_handoff("turn-session", base_dir=tmp_path)
        assert result is not None
        assert result.turn_count == 42

    def test_load_with_default_base_dir(self, tmp_path, monkeypatch):
        """Loader uses cwd when base_dir not specified."""
        # Create handoff in tmp_path
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "cwd-session"
        session_dir.mkdir(parents=True)

        handoff_file = session_dir / "handoff.md"
        handoff_file.write_text("# Temporal Handoff (Turn 1)\n\n## Context\nCwd test.")

        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        result = load_temporal_handoff("cwd-session")
        assert result is not None
        assert "Cwd test" in result.context


class TestTemporalHandoffIntegration:
    """Integration tests for handoff workflow."""

    def test_full_workflow(self, tmp_path):
        """Test complete handoff creation, save, load, parse cycle."""
        # Create handoff state
        handoff = TemporalHandoffState(
            context="Implementing Phase 5 of temporal memory",
            next_instruction="Write tests for handoff parser",
            invariants={"project": "claude-continuity-kit", "language": "python"},
            current_state={"phase": "implementation"},
            eventualities=["goal_tests_pass", "goal_coverage_80"],
            open_questions=[
                ("persistence_format", "HIGH", "SQLite vs JSON for storage"),
                ("api_design", "MED", "Sync vs async interface"),
            ],
            transitions=[
                "T=3: phase=planning -> phase=implementation",
                "T=5: tests=failing -> tests=passing",
            ],
            turn_count=7,
        )

        # Generate markdown
        md = handoff.to_markdown()

        # Save to file
        session_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "integration-test"
        session_dir.mkdir(parents=True)
        handoff_file = session_dir / "current.md"
        handoff_file.write_text(md)

        # Load and verify
        loaded = load_temporal_handoff("integration-test", base_dir=tmp_path)
        assert loaded is not None

        # Verify all fields preserved
        assert loaded.context == handoff.context
        assert loaded.next_instruction == handoff.next_instruction
        assert loaded.invariants == handoff.invariants
        assert loaded.current_state == handoff.current_state
        assert set(loaded.eventualities) == set(handoff.eventualities)
        assert len(loaded.open_questions) == len(handoff.open_questions)
        assert loaded.turn_count == handoff.turn_count

    def test_handoff_with_summarizer_output(self):
        """Test creating handoff from summarizer output format."""
        # Simulated TemporalSummarizer output
        summary = {
            "open_questions_ranked": [
                ("db_type", "HIGH", "Fundamental storage decision"),
                ("api_style", "MED", "Affects all endpoints"),
            ],
            "pending_goals": ["goal_integration_tests", "goal_docs"],
            "transitions": [
                "T=1: phase=init -> phase=design",
                "T=2: phase=design -> phase=impl",
            ],
            "current_state": {
                "db": "sqlite",
                "framework": "agentica",
                "test_status": "passing",
            },
            "turn_count": 5,
            "token_estimate": 150,
        }

        handoff = TemporalHandoffState.from_summary(
            summary=summary,
            context="Building temporal memory system",
            instruction="Complete handoff tests",
        )

        # Verify conversion
        assert handoff.turn_count == 5
        assert len(handoff.open_questions) == 2
        assert handoff.open_questions[0][0] == "db_type"
        assert "goal_integration_tests" in handoff.eventualities
        assert handoff.invariants == {}
        assert handoff.current_state["db"] == "sqlite"

        # Verify markdown generation
        md = handoff.to_markdown()
        assert "Turn 5" in md
        assert "db_type" in md
        assert "HIGH" in md
        assert "goal_integration_tests" in md
