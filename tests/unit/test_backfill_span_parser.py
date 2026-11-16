"""Tests for SpanParser - extract structured facts from Braintrust spans.

TDD: Tests written FIRST, implementation follows.
"""
import pytest
from scripts.backfill.span_parser import SpanParser, SpanFact


class TestSpanParser:
    """Test span parsing for various tool types."""

    def test_parse_tool_span_read(self):
        """Read tool span extracts file path fact."""
        parser = SpanParser()
        span = {
            "span_id": "span-123",
            "span_attributes": {"type": "tool", "name": "Read"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/path/to/file.py"}',
            "output": "file contents here...",
        }

        facts = parser.parse_span(span, turn=1)

        assert len(facts) >= 1
        assert any(
            f.key == "file_read" and "/path/to/file.py" in f.value for f in facts
        )
        # Check span_id is preserved
        assert all(f.span_id == "span-123" for f in facts)

    def test_parse_tool_span_write(self):
        """Write tool span extracts file path and mutation_count facts."""
        parser = SpanParser()
        span = {
            "span_id": "span-456",
            "span_attributes": {"type": "tool", "name": "Write"},
            "metadata": {"tool_name": "Write"},
            "input": '{"file_path": "/new/file.py", "content": "print(1)\\nprint(2)\\nprint(3)"}',
            "output": "File written successfully",
        }

        facts = parser.parse_span(span, turn=2)

        assert any(f.key == "file_written" and "/new/file.py" in f.value for f in facts)
        assert any(f.key == "mutation_count" for f in facts)

    def test_parse_tool_span_bash(self):
        """Bash tool span extracts command and test results."""
        parser = SpanParser()
        span = {
            "span_id": "span-789",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Bash"},
            "input": '{"command": "pytest tests/"}',
            "output": "5 passed, 0 failed",
        }

        facts = parser.parse_span(span, turn=3)

        assert any(f.key == "test_result" and "passed" in f.value for f in facts)

    def test_parse_tool_span_bash_with_failure(self):
        """Bash tool span detects test failures."""
        parser = SpanParser()
        span = {
            "span_id": "span-fail",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Bash"},
            "input": '{"command": "pytest tests/"}',
            "output": "3 passed, 2 failed",
        }

        facts = parser.parse_span(span, turn=3)

        assert any(f.key == "test_result" and "failed" in f.value for f in facts)

    def test_parse_tool_span_task(self):
        """Task tool span extracts agent spawn fact."""
        parser = SpanParser()
        span = {
            "span_id": "span-task",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Task", "agent_type": "research-agent"},
            "input": '{"prompt": "Research the API..."}',
        }

        facts = parser.parse_span(span, turn=1)

        assert any(
            f.key == "agent_spawned" and f.value == "research-agent" for f in facts
        )

    def test_parse_tool_span_task_without_agent_type(self):
        """Task tool span without agent_type still extracts fact."""
        parser = SpanParser()
        span = {
            "span_id": "span-task2",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Task"},
            "input": '{"prompt": "Do something..."}',
        }

        facts = parser.parse_span(span, turn=1)

        # Should still have agent_spawned fact, maybe with "unknown" value
        assert any(f.key == "agent_spawned" for f in facts)

    def test_parse_llm_span(self):
        """LLM span extracts token count fact."""
        parser = SpanParser()
        span = {
            "span_id": "span-llm",
            "span_attributes": {"type": "llm"},
            "metrics": {"tokens": 5000},
            "output": "I'll help you with...",
        }

        facts = parser.parse_span(span, turn=1)

        assert any(f.key == "tokens_used" and f.value == "5000" for f in facts)

    def test_parse_llm_span_with_prompt_tokens(self):
        """LLM span extracts detailed token counts if available."""
        parser = SpanParser()
        span = {
            "span_id": "span-llm2",
            "span_attributes": {"type": "llm"},
            "metrics": {"tokens": 5000, "prompt_tokens": 3000, "completion_tokens": 2000},
            "output": "Response...",
        }

        facts = parser.parse_span(span, turn=1)

        assert any(f.key == "tokens_used" for f in facts)

    def test_parse_skill_activation(self):
        """Skill activation extracted from metadata."""
        parser = SpanParser()
        span = {
            "span_id": "span-skill",
            "span_attributes": {"type": "tool"},
            "metadata": {"skill_name": "create_handoff", "tool_name": "Write"},
            "input": '{"file_path": "handoffs/session/task-01.md"}',
        }

        facts = parser.parse_span(span, turn=5)

        assert any(
            f.key == "skill_activated" and f.value == "create_handoff" for f in facts
        )

    def test_empty_span_no_crash(self):
        """Empty or malformed span doesn't crash."""
        parser = SpanParser()
        span = {}

        facts = parser.parse_span(span, turn=1)
        assert facts == []

    def test_none_span_no_crash(self):
        """None span handled gracefully."""
        parser = SpanParser()

        facts = parser.parse_span(None, turn=1)  # type: ignore
        assert facts == []

    def test_malformed_json_input_no_crash(self):
        """Malformed JSON in input doesn't crash."""
        parser = SpanParser()
        span = {
            "span_id": "span-bad",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": "not valid json {{{",
        }

        facts = parser.parse_span(span, turn=1)
        # Should return empty or handle gracefully
        assert isinstance(facts, list)

    def test_missing_metadata_handled(self):
        """Span without metadata handled."""
        parser = SpanParser()
        span = {
            "span_id": "span-nometadata",
            "span_attributes": {"type": "tool"},
            "input": '{"file_path": "/test.py"}',
        }

        facts = parser.parse_span(span, turn=1)
        # Should not crash
        assert isinstance(facts, list)

    def test_content_hash_for_dedup(self):
        """Same content produces same hash (excludes timestamp)."""
        parser = SpanParser()
        span = {
            "span_id": "span-hash",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/file.py"}',
        }

        facts1 = parser.parse_span(span, turn=1)
        facts2 = parser.parse_span(span, turn=1)

        # Same content = same hash (idempotent)
        assert len(facts1) > 0
        assert facts1[0].content_hash == facts2[0].content_hash

    def test_content_hash_differs_for_different_turns(self):
        """Different turns produce different hashes."""
        parser = SpanParser()
        span = {
            "span_id": "span-hash2",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/file.py"}',
        }

        facts1 = parser.parse_span(span, turn=1)
        facts2 = parser.parse_span(span, turn=2)

        # Different turn = different hash
        assert facts1[0].content_hash != facts2[0].content_hash

    def test_content_hash_differs_for_different_values(self):
        """Different values produce different hashes."""
        parser = SpanParser()
        span1 = {
            "span_id": "span-a",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/a.py"}',
        }
        span2 = {
            "span_id": "span-b",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/b.py"}',
        }

        facts1 = parser.parse_span(span1, turn=1)
        facts2 = parser.parse_span(span2, turn=1)

        assert facts1[0].content_hash != facts2[0].content_hash

    def test_turn_preserved_in_facts(self):
        """Turn number is preserved in extracted facts."""
        parser = SpanParser()
        span = {
            "span_id": "span-turn",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/test.py"}',
        }

        facts = parser.parse_span(span, turn=42)

        assert all(f.turn == 42 for f in facts)

    def test_confidence_defaults_to_one(self):
        """Fact confidence defaults to 1.0."""
        parser = SpanParser()
        span = {
            "span_id": "span-conf",
            "span_attributes": {"type": "tool"},
            "metadata": {"tool_name": "Read"},
            "input": '{"file_path": "/test.py"}',
        }

        facts = parser.parse_span(span, turn=1)

        assert all(f.confidence == 1.0 for f in facts)


class TestSpanFactDataclass:
    """Test SpanFact dataclass."""

    def test_span_fact_creation(self):
        """SpanFact can be created with required fields."""
        fact = SpanFact(key="file_read", value="/path.py", turn=1)

        assert fact.key == "file_read"
        assert fact.value == "/path.py"
        assert fact.turn == 1
        assert fact.span_id is None
        assert fact.content_hash is None
        assert fact.confidence == 1.0
        assert fact.metadata is None

    def test_span_fact_with_all_fields(self):
        """SpanFact can be created with all fields."""
        fact = SpanFact(
            key="file_written",
            value="/out.py",
            turn=5,
            span_id="span-abc",
            content_hash="hash123",
            confidence=0.9,
            metadata={"extra": "data"},
        )

        assert fact.span_id == "span-abc"
        assert fact.content_hash == "hash123"
        assert fact.confidence == 0.9
        assert fact.metadata == {"extra": "data"}
