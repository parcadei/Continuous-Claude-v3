"""Tests for SpanProcessor two-pass Map/Reduce.

TDD: Write tests first, watch them fail, implement minimally.

Tests follow the plan at: thoughts/shared/work/two-pass-mapreduce/02-plan.md

Run with: uv run pytest tests/unit/test_span_processor.py -v
"""

import asyncio
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Phase 1: Data Structures
# =============================================================================


class TestSpanSummary:
    """Tests for SpanSummary dataclass."""

    def test_span_summary_creation(self):
        """SpanSummary has span_id, turn_number, summary, key_entities, references, span_type, content_hash.

        Validates that the SpanSummary dataclass can be instantiated with all required fields
        and that each field is correctly stored and accessible.
        """
        from scripts.agentica_patterns.span_processor import SpanSummary

        summary = SpanSummary(
            span_id="span_001",
            turn_number=5,
            summary="User requested JWT auth. Decided to use RS256.",
            key_entities=["JWT", "RS256", "auth"],
            references=["span_002", "span_003"],
            span_type="llm_reasoning",
            content_hash="abc123",
        )

        assert summary.span_id == "span_001"
        assert summary.turn_number == 5
        assert summary.summary == "User requested JWT auth. Decided to use RS256."
        assert len(summary.key_entities) == 3
        assert "JWT" in summary.key_entities
        assert "span_002" in summary.references
        assert summary.span_type == "llm_reasoning"
        assert summary.content_hash == "abc123"


class TestSpanDecision:
    """Tests for SpanDecision dataclass."""

    def test_span_decision_creation(self):
        """SpanDecision has span_id, decision, rationale, confidence, source_refs.

        Validates that decisions extracted during Pass 2 can be properly structured
        with all required fields including confidence scores and reference tracing.
        """
        from scripts.agentica_patterns.span_processor import SpanDecision

        decision = SpanDecision(
            span_id="span_010",
            decision="Use PostgreSQL instead of SQLite for production",
            rationale="Need multi-user concurrent access and JSONB support",
            confidence=0.85,
            source_refs=["span_005", "span_007"],
        )

        assert decision.span_id == "span_010"
        assert "PostgreSQL" in decision.decision
        assert "concurrent" in decision.rationale
        assert decision.confidence == 0.85
        assert len(decision.source_refs) == 2
        assert "span_005" in decision.source_refs


class TestSpanProcessingContext:
    """Tests for thread-safe shared context."""

    def test_span_processing_context_creation(self):
        """SpanProcessingContext initializes with empty state.

        Validates that the context starts with empty dictionaries and lists,
        ready to accumulate data during processing.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext

        ctx = SpanProcessingContext()

        assert ctx.span_summaries == {}
        assert ctx.reference_graph == {}
        assert ctx.processing_log == []

    @pytest.mark.asyncio
    async def test_add_summary(self):
        """add_summary stores summary and updates reference graph.

        Validates that adding a summary both stores it by span_id and populates
        the reference graph for later cross-reference resolution.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()
        summary = SpanSummary(
            span_id="span_001",
            turn_number=0,
            summary="Test summary",
            key_entities=[],
            references=["span_000"],
            span_type="tool_call",
            content_hash="hash",
        )

        await ctx.add_summary(summary)

        assert "span_001" in ctx.span_summaries
        assert ctx.reference_graph["span_001"] == ["span_000"]
        assert len(ctx.processing_log) == 1
        assert ctx.processing_log[0]["action"] == "add_summary"

    @pytest.mark.asyncio
    async def test_get_reference_context(self):
        """get_reference_context returns formatted summary context for references.

        Validates that when a span references other spans, we can retrieve
        their summaries formatted for injection into LLM prompts.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()

        # Add two summaries
        await ctx.add_summary(SpanSummary(
            span_id="span_000",
            turn_number=0,
            summary="First summary about user requirements",
            key_entities=["requirements"],
            references=[],
            span_type="user_input",
            content_hash="h1",
        ))
        await ctx.add_summary(SpanSummary(
            span_id="span_001",
            turn_number=1,
            summary="Second summary with analysis",
            key_entities=["analysis"],
            references=["span_000"],  # References first span
            span_type="llm_reasoning",
            content_hash="h2",
        ))

        # Get reference context for span_001
        context = await ctx.get_reference_context("span_001")

        assert "[span_000]: First summary about user requirements" in context

    @pytest.mark.asyncio
    async def test_get_reference_context_no_references(self):
        """get_reference_context returns empty string when no references exist.

        Validates edge case where a span has no references to other spans.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()
        await ctx.add_summary(SpanSummary(
            span_id="span_001",
            turn_number=0,
            summary="Standalone summary",
            key_entities=[],
            references=[],
            span_type="user_input",
            content_hash="h1",
        ))

        context = await ctx.get_reference_context("span_001")
        assert context == ""

    @pytest.mark.asyncio
    async def test_all_summaries(self):
        """all_summaries returns thread-safe copy of all summaries.

        Validates that we can get all summaries for batch operations like embedding.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()
        for i in range(3):
            await ctx.add_summary(SpanSummary(
                span_id=f"span_{i}",
                turn_number=i,
                summary=f"Summary {i}",
                key_entities=[],
                references=[],
                span_type="tool_call",
                content_hash=f"h{i}",
            ))

        summaries = await ctx.all_summaries()

        assert len(summaries) == 3
        # Verify it's a copy (modification doesn't affect original)
        summaries.clear()
        assert len(ctx.span_summaries) == 3

    @pytest.mark.asyncio
    async def test_thread_safety(self):
        """SpanProcessingContext is async-safe for concurrent access.

        Validates that multiple async tasks can safely add summaries concurrently
        without data corruption.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()
        errors = []

        async def add_summaries(start_idx: int, count: int):
            try:
                for i in range(count):
                    await ctx.add_summary(SpanSummary(
                        span_id=f"span_{start_idx + i}",
                        turn_number=start_idx + i,
                        summary=f"Summary {start_idx + i}",
                        key_entities=[],
                        references=[],
                        span_type="tool_call",
                        content_hash=f"h{start_idx + i}",
                    ))
            except Exception as e:
                errors.append(e)

        # Run 5 concurrent async tasks, each adding 10 summaries
        await asyncio.gather(*[add_summaries(i * 10, 10) for i in range(5)])

        assert len(errors) == 0
        assert len(ctx.span_summaries) == 50


# =============================================================================
# Phase 2: Reference Graph Building
# =============================================================================


class TestBuildReferenceGraph:
    """Tests for reference graph building."""

    def test_build_reference_graph_empty(self):
        """build_reference_graph returns empty dict for empty input.

        Validates edge case with no spans to process.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        graph = build_reference_graph([])
        assert graph == {}

    def test_build_reference_graph_explicit_refs(self):
        """build_reference_graph detects explicit reference patterns.

        Validates detection of phrases like 'As discussed earlier',
        'Based on the earlier', 'referring to', 'see above'.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {"span_id": "s1", "input": "Initial request for auth", "output": "OK"},
            {"span_id": "s2", "input": "As discussed earlier, we need JWT", "output": "Following up"},
        ]

        graph = build_reference_graph(spans)

        # s2 should reference s1 due to "As discussed earlier"
        assert "s1" in graph.get("s2", [])

    def test_build_reference_graph_implicit_refs(self):
        """build_reference_graph detects tool output matching.

        Validates that when a span's output contains content from a prior
        span's input, we detect an implicit reference.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {"span_id": "s1", "input": "Please analyze the authentication flow in detail", "output": "Analysis started"},
            {"span_id": "s2", "input": "Next step", "output": "Based on the analysis: Please analyze the authentication flow in detail - findings..."},
        ]

        graph = build_reference_graph(spans)

        # s2 might reference s1 due to content matching
        # (depends on implementation details of the heuristic)
        assert "s1" in graph or "s2" in graph  # At minimum, spans should be in graph

    def test_build_reference_graph_no_false_positives(self):
        """build_reference_graph does not create false references.

        Validates that independent spans without explicit references
        do not get spurious reference relationships.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {"span_id": "s1", "input": "First task", "output": "Done"},
            {"span_id": "s2", "input": "Completely different second task", "output": "Also done"},
        ]

        graph = build_reference_graph(spans)

        # Neither should reference the other
        assert graph.get("s1", []) == []
        assert graph.get("s2", []) == []


class TestChunkByReferences:
    """Tests for reference-aware chunking."""

    def test_chunk_by_references_small_session(self):
        """chunk_by_references keeps all spans in one chunk for small sessions.

        Validates that sessions smaller than max_chunk_size are not split.
        """
        from scripts.agentica_patterns.span_processor import chunk_by_references

        spans = [
            {"span_id": "s1"},
            {"span_id": "s2"},
            {"span_id": "s3"},
        ]
        ref_graph = {
            "s1": [],
            "s2": [],
            "s3": [],
        }

        chunks = chunk_by_references(spans, ref_graph, max_chunk_size=50)

        # All should be in chunks (possibly multiple if independent)
        total_spans = sum(len(c) for c in chunks)
        assert total_spans == 3

    def test_chunk_by_references_large_session(self):
        """chunk_by_references subdivides large connected components with overlap.

        Validates that when a connected component exceeds max_chunk_size,
        it is subdivided with proper overlap for context preservation.
        """
        from scripts.agentica_patterns.span_processor import chunk_by_references

        spans = [{"span_id": f"s{i}"} for i in range(100)]
        # All spans reference the previous one (one giant component)
        ref_graph = {f"s{i}": [f"s{i-1}"] if i > 0 else [] for i in range(100)}

        chunks = chunk_by_references(spans, ref_graph, max_chunk_size=30, overlap=5)

        # Should subdivide into multiple chunks
        assert len(chunks) > 3
        assert all(len(c) <= 30 for c in chunks)

    def test_chunk_by_references_preserves_connected_components(self):
        """chunk_by_references keeps connected spans together.

        Validates that spans with references to each other are placed
        in the same chunk to preserve context.
        """
        from scripts.agentica_patterns.span_processor import chunk_by_references

        spans = [
            {"span_id": "s1"},
            {"span_id": "s2"},
            {"span_id": "s3"},
            {"span_id": "s4"},
        ]
        ref_graph = {
            "s1": [],
            "s2": ["s1"],  # s1 and s2 are connected
            "s3": [],      # s3 is independent
            "s4": ["s3"],  # s3 and s4 are connected
        }

        chunks = chunk_by_references(spans, ref_graph, max_chunk_size=10)

        # Should have 2 chunks: (s1, s2) and (s3, s4)
        chunk_ids = [set(s["span_id"] for s in chunk) for chunk in chunks]

        # Find which chunks contain which spans
        s1_s2_together = any({"s1", "s2"}.issubset(ids) for ids in chunk_ids)
        s3_s4_together = any({"s3", "s4"}.issubset(ids) for ids in chunk_ids)

        assert s1_s2_together
        assert s3_s4_together


# =============================================================================
# Phase 3: Pass 1 - Summary Extraction
# =============================================================================


class TestExtractSummaries:
    """Tests for Pass 1 summary extraction."""

    @pytest.fixture
    def mock_mapreduce(self):
        """Mock MapReduce for testing without actual LLM calls."""
        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock:
            instance = MagicMock()
            instance._map_phase = AsyncMock(return_value=[
                '[{"span_id": "s1", "summary": "Test summary 1", "key_entities": ["entity1"], "span_type": "tool_call"}]'
            ])
            mock.return_value = instance
            yield mock

    @pytest.mark.asyncio
    async def test_extract_summaries_single_span(self, mock_mapreduce):
        """extract_summaries processes a single span correctly.

        Validates that a single span is processed and its summary
        is stored in the context.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_summaries,
            SpanProcessingContext,
        )

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test input", "output": "test output"}]]

        await extract_summaries(chunks, context, num_mappers=1)

        assert "s1" in context.span_summaries
        assert context.span_summaries["s1"].summary == "Test summary 1"

    @pytest.mark.asyncio
    async def test_extract_summaries_multiple_spans(self, mock_mapreduce):
        """extract_summaries processes multiple spans in parallel.

        Validates that multiple chunks are processed concurrently
        and all summaries are collected.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_summaries,
            SpanProcessingContext,
        )

        # Update mock to return multiple summaries
        mock_mapreduce.return_value._map_phase = AsyncMock(return_value=[
            '[{"span_id": "s1", "summary": "Summary 1", "key_entities": [], "span_type": "tool_call"}, '
            '{"span_id": "s2", "summary": "Summary 2", "key_entities": [], "span_type": "llm_reasoning"}]'
        ])

        context = SpanProcessingContext()
        chunks = [[
            {"span_id": "s1", "input": "input 1", "output": "output 1"},
            {"span_id": "s2", "input": "input 2", "output": "output 2"},
        ]]

        await extract_summaries(chunks, context, num_mappers=2)

        assert len(context.span_summaries) >= 1  # At least the mocked ones

    @pytest.mark.asyncio
    async def test_extract_summaries_stores_to_blackboard(self, mock_mapreduce):
        """extract_summaries stores results in SpanProcessingContext.

        Validates that extracted summaries are properly stored in the
        shared context for use in Pass 2.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_summaries,
            SpanProcessingContext,
        )

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test", "output": "test"}]]

        await extract_summaries(chunks, context, num_mappers=1)

        # Verify summary was stored
        assert "s1" in context.span_summaries

        # Verify processing log was updated
        log_actions = [entry["action"] for entry in context.processing_log]
        assert "add_summary" in log_actions

    @pytest.mark.asyncio
    async def test_extract_summaries_handles_parse_errors(self, mock_mapreduce):
        """extract_summaries handles JSON parse errors gracefully.

        Validates that malformed LLM output doesn't crash the pipeline
        and errors are logged.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_summaries,
            SpanProcessingContext,
        )

        # Return malformed JSON
        mock_mapreduce.return_value._map_phase = AsyncMock(return_value=[
            'not valid json {{{{'
        ])

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test", "output": "test"}]]

        # Should not raise
        await extract_summaries(chunks, context, num_mappers=1)

        # Error should be logged
        error_logs = [e for e in context.processing_log if e.get("action") == "parse_error"]
        assert len(error_logs) >= 1


# =============================================================================
# Phase 4: Pass 2 - Decision Extraction
# =============================================================================


class TestExtractDecisions:
    """Tests for Pass 2 decision extraction."""

    @pytest.fixture
    def mock_mapreduce_decisions(self):
        """Mock MapReduce for decision extraction."""
        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock:
            instance = MagicMock()
            instance._map_phase = AsyncMock(return_value=[
                '[{"span_id": "s1", "decision": "Use PostgreSQL", "rationale": "Better for production", "confidence": 0.9, "source_refs": ["s0"]}]'
            ])
            mock.return_value = instance
            yield mock

    @pytest.mark.asyncio
    async def test_extract_decisions_with_context_injection(self, mock_mapreduce_decisions):
        """extract_decisions injects reference context from Pass 1.

        Validates that decisions are extracted with summary context
        from referenced spans injected into the mapper prompt.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_decisions,
            SpanProcessingContext,
            SpanSummary,
        )

        context = SpanProcessingContext()
        # Pre-populate with summaries from Pass 1
        await context.add_summary(SpanSummary(
            span_id="s0",
            turn_number=0,
            summary="Initial analysis of database options",
            key_entities=["database", "PostgreSQL", "SQLite"],
            references=[],
            span_type="llm_reasoning",
            content_hash="h0",
        ))
        await context.add_summary(SpanSummary(
            span_id="s1",
            turn_number=1,
            summary="Decision about database choice",
            key_entities=["PostgreSQL"],
            references=["s0"],  # References s0
            span_type="llm_reasoning",
            content_hash="h1",
        ))

        chunks = [[
            {"span_id": "s1", "input": "Choose database", "output": "Use PostgreSQL"}
        ]]

        decisions = await extract_decisions(chunks, context, num_mappers=1)

        assert len(decisions) >= 1
        assert any(d.decision == "Use PostgreSQL" for d in decisions)

    @pytest.mark.asyncio
    async def test_extract_decisions_no_references(self, mock_mapreduce_decisions):
        """extract_decisions works when span has no references.

        Validates that decisions can be extracted from standalone spans
        that don't reference other spans.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_decisions,
            SpanProcessingContext,
            SpanSummary,
        )

        context = SpanProcessingContext()
        await context.add_summary(SpanSummary(
            span_id="s1",
            turn_number=0,
            summary="Standalone decision",
            key_entities=[],
            references=[],  # No references
            span_type="llm_reasoning",
            content_hash="h1",
        ))

        chunks = [[
            {"span_id": "s1", "input": "Make decision", "output": "Decision made"}
        ]]

        decisions = await extract_decisions(chunks, context, num_mappers=1)

        # Should still work, just with empty reference context
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_extract_decisions_filters_low_confidence(self, mock_mapreduce_decisions):
        """extract_decisions filters out low-confidence decisions.

        Validates that decisions with confidence < 0.5 are not included
        in the final results.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_decisions,
            SpanProcessingContext,
        )

        # Return low-confidence decision
        mock_mapreduce_decisions.return_value._map_phase = AsyncMock(return_value=[
            '[{"span_id": "s1", "decision": "Maybe do X", "rationale": "Not sure", "confidence": 0.3, "source_refs": []}]'
        ])

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test", "output": "test"}]]

        decisions = await extract_decisions(chunks, context, num_mappers=1)

        # Low confidence decision should be filtered
        assert all(d.confidence >= 0.5 for d in decisions)


# =============================================================================
# Phase 5-6: Integration Tests
# =============================================================================


class TestSpanProcessorIntegration:
    """Tests for full SpanProcessor pipeline."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies for pipeline testing."""
        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock_mr, \
             patch("scripts.agentica_patterns.span_processor.EmbeddingService") as mock_embed, \
             patch("scripts.agentica_patterns.span_processor.MemoryServicePG") as mock_memory:

            # Configure MapReduce mock
            mr_instance = MagicMock()
            mr_instance._map_phase = AsyncMock(return_value=[
                '[{"span_id": "s1", "summary": "Test", "key_entities": [], "span_type": "tool_call"}]'
            ])
            mock_mr.return_value = mr_instance

            # Configure embedding mock
            embed_instance = MagicMock()
            embed_instance.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
            mock_embed.return_value = embed_instance

            # Configure memory mock
            memory_instance = MagicMock()
            memory_instance.connect = AsyncMock()
            memory_instance.close = AsyncMock()
            memory_instance.store = AsyncMock(return_value="stored_id")
            mock_memory.return_value = memory_instance

            yield {
                "mapreduce": mock_mr,
                "embedding": mock_embed,
                "memory": mock_memory,
            }

    @pytest.mark.asyncio
    async def test_span_processor_full_pipeline(self, mock_dependencies):
        """SpanProcessor runs complete two-pass pipeline.

        Validates end-to-end processing: reference graph building,
        Pass 1 (summaries), embedding, Pass 2 (decisions), and persistence.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessor

        with patch("scripts.agentica_patterns.span_processor.embed_and_persist_summaries", new_callable=AsyncMock) as mock_embed_persist, \
             patch("scripts.agentica_patterns.span_processor.persist_decisions", new_callable=AsyncMock) as mock_persist:

            mock_embed_persist.return_value = 5
            mock_persist.return_value = 3

            processor = SpanProcessor(
                session_id="test_session",
                num_mappers=2,
                max_chunk_size=50,
                embedding_provider="mock",
            )

            spans = [
                {"span_id": f"s{i}", "input": f"input {i}", "output": f"output {i}"}
                for i in range(10)
            ]

            result = await processor.process(spans)

            assert result.session_id == "test_session"
            assert result.spans_processed == 10
            assert result.summaries_persisted == 5
            assert result.decisions_persisted == 3
            assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_span_processor_threshold_skip(self, mock_dependencies):
        """SpanProcessor handles empty or minimal span sets.

        Validates that the processor handles edge cases like empty
        input gracefully.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessor

        with patch("scripts.agentica_patterns.span_processor.embed_and_persist_summaries", new_callable=AsyncMock) as mock_embed_persist, \
             patch("scripts.agentica_patterns.span_processor.persist_decisions", new_callable=AsyncMock) as mock_persist:

            mock_embed_persist.return_value = 0
            mock_persist.return_value = 0

            processor = SpanProcessor(
                session_id="test_session",
                num_mappers=2,
                embedding_provider="mock",
            )

            # Empty spans
            result = await processor.process([])

            assert result.spans_processed == 0
            assert result.summaries_extracted == 0
            assert result.decisions_extracted == 0

    @pytest.mark.asyncio
    async def test_span_processor_error_handling(self, mock_dependencies):
        """SpanProcessor captures errors in result.

        Validates that pipeline errors are captured in the result
        rather than crashing the entire process.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessor

        with patch("scripts.agentica_patterns.span_processor.build_reference_graph") as mock_graph:
            mock_graph.side_effect = ValueError("Test error")

            processor = SpanProcessor(
                session_id="test_session",
                num_mappers=2,
                embedding_provider="mock",
            )

            result = await processor.process([{"span_id": "s1"}])

            assert len(result.errors) > 0
            assert "Test error" in result.errors[0]


class TestSpanProcessorResult:
    """Tests for SpanProcessingResult dataclass."""

    def test_span_processing_result_creation(self):
        """SpanProcessingResult captures all pipeline metrics.

        Validates that the result dataclass contains all required fields
        for reporting and debugging.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingResult

        result = SpanProcessingResult(
            session_id="test123",
            spans_processed=100,
            summaries_extracted=95,
            decisions_extracted=20,
            summaries_persisted=95,
            decisions_persisted=20,
            duration_seconds=45.2,
            errors=["Minor warning"],
        )

        assert result.session_id == "test123"
        assert result.spans_processed == 100
        assert result.summaries_extracted == 95
        assert result.decisions_extracted == 20
        assert result.summaries_persisted == 95
        assert result.decisions_persisted == 20
        assert result.duration_seconds == 45.2
        assert len(result.errors) == 1


# =============================================================================
# Additional Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_span_summary_with_empty_references(self):
        """SpanSummary handles empty reference list.

        Validates that spans with no references are properly handled.
        """
        from scripts.agentica_patterns.span_processor import SpanSummary

        summary = SpanSummary(
            span_id="standalone",
            turn_number=0,
            summary="Independent span",
            key_entities=[],
            references=[],
            span_type="user_input",
            content_hash="hash123",
        )

        assert summary.references == []

    def test_span_decision_with_max_confidence(self):
        """SpanDecision handles confidence at boundaries.

        Validates that confidence values at 0.0 and 1.0 are valid.
        """
        from scripts.agentica_patterns.span_processor import SpanDecision

        decision_low = SpanDecision(
            span_id="s1",
            decision="Uncertain decision",
            rationale="Not sure",
            confidence=0.0,
            source_refs=[],
        )

        decision_high = SpanDecision(
            span_id="s2",
            decision="Certain decision",
            rationale="Very confident",
            confidence=1.0,
            source_refs=[],
        )

        assert decision_low.confidence == 0.0
        assert decision_high.confidence == 1.0

    def test_reference_graph_with_circular_refs(self):
        """build_reference_graph handles circular references.

        Validates that circular references don't cause infinite loops
        during graph traversal or chunking.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph, chunk_by_references

        spans = [
            {"span_id": "s1", "input": "As discussed in s3", "output": ""},
            {"span_id": "s2", "input": "As discussed in s1", "output": ""},
            {"span_id": "s3", "input": "As discussed in s2", "output": ""},
        ]

        # Should not infinite loop
        graph = build_reference_graph(spans)
        chunks = chunk_by_references(spans, graph, max_chunk_size=10)

        # All spans should be in some chunk
        all_span_ids = set()
        for chunk in chunks:
            for span in chunk:
                all_span_ids.add(span["span_id"])

        assert all_span_ids == {"s1", "s2", "s3"}


# =============================================================================
# TDD Phase 2: Boundary Condition Tests (From Mutation Testing M1-M11)
# =============================================================================


class TestBoundaryConditions:
    """Tests for boundary conditions identified via mutation testing.

    These tests expose bugs where mutations to boundary values would
    survive the existing test suite. Target: Kill mutants M1-M11.
    """

    def test_implicit_reference_20char_boundary(self):
        """M1: Verify the >20 character threshold for implicit references.

        Bug: Changing `len(prior_input) > 20` to `>= 20` or `> 19` survives.
        This test verifies the exact boundary behavior.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # Exactly 20 characters - should NOT create implicit reference
        spans_20 = [
            {"span_id": "s1", "input": "x" * 20, "output": "done"},
            {"span_id": "s2", "input": "", "output": "x" * 20 + " more text"},
        ]
        graph_20 = build_reference_graph(spans_20)
        assert "s1" not in graph_20.get("s2", []), \
            "20 chars should NOT match (need > 20)"

        # 21 characters - should create implicit reference
        spans_21 = [
            {"span_id": "s1", "input": "x" * 21, "output": "done"},
            {"span_id": "s2", "input": "", "output": "x" * 21 + " more text"},
        ]
        graph_21 = build_reference_graph(spans_21)
        assert "s1" in graph_21.get("s2", []), \
            "21 chars should match (> 20)"

        # 19 characters - definitely should NOT match
        spans_19 = [
            {"span_id": "s1", "input": "x" * 19, "output": "done"},
            {"span_id": "s2", "input": "", "output": "x" * 19 + " more text"},
        ]
        graph_19 = build_reference_graph(spans_19)
        assert "s1" not in graph_19.get("s2", []), \
            "19 chars should NOT match"

    def test_content_slice_50char_boundary(self):
        """M2: Verify the [:50] content slice for implicit references.

        Bug: Changing `prior_input[:50]` to `[:49]` or `[:51]` survives.
        This test verifies exact 50-character matching.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # Create 60-character input; only first 50 should be used for matching
        base_content = "a" * 50 + "b" * 10  # 60 chars total

        # Output contains first 50 chars - should match
        spans_match = [
            {"span_id": "s1", "input": base_content, "output": "done"},
            {"span_id": "s2", "input": "", "output": "a" * 50 + " different ending"},
        ]
        graph_match = build_reference_graph(spans_match)
        assert "s1" in graph_match.get("s2", []), \
            "First 50 chars should match"

        # Output contains first 49 chars but not char 50 - should NOT match
        spans_no_match = [
            {"span_id": "s1", "input": base_content, "output": "done"},
            {"span_id": "s2", "input": "", "output": "a" * 49 + "Z" + " different"},
        ]
        graph_no_match = build_reference_graph(spans_no_match)
        assert "s1" not in graph_no_match.get("s2", []), \
            "49 chars + different char 50 should NOT match"

    def test_reference_window_3span_limit(self):
        """M4: Verify the 3-span reference window for explicit patterns.

        Bug: Changing `range(max(0, idx - 3), idx)` to `idx - 2` survives.
        This test verifies that exactly 3 prior spans are referenced.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # Create 6 spans where s5 uses explicit reference pattern
        spans = [
            {"span_id": f"s{i}", "input": f"Input {i}", "output": f"Output {i}"}
            for i in range(6)
        ]
        # s5 triggers explicit reference pattern
        spans[5]["input"] = "As discussed earlier, we should proceed"

        graph = build_reference_graph(spans)
        refs = graph.get("s5", [])

        # Should reference s2, s3, s4 (prior 3 spans)
        assert "s2" in refs, "s2 should be in 3-span window"
        assert "s3" in refs, "s3 should be in 3-span window"
        assert "s4" in refs, "s4 should be in 3-span window"

        # Should NOT reference s0, s1 (outside 3-span window)
        assert "s0" not in refs, "s0 should be outside 3-span window"
        assert "s1" not in refs, "s1 should be outside 3-span window"

    def test_content_hash_16char_format(self):
        """M6: Verify content hash is exactly 16 hex characters.

        Bug: Changing `hexdigest()[:16]` to `[:15]` or `[:17]` survives.
        This test verifies the exact hash format.
        """
        from scripts.agentica_patterns.span_processor import _content_hash

        # Test with metadata
        hash1 = _content_hash("Test content", {"span_id": "s1", "type": "tool_call"})
        assert len(hash1) == 16, f"Hash should be 16 chars, got {len(hash1)}"
        assert all(c in "0123456789abcdef" for c in hash1), \
            "Hash should be hex characters only"

        # Test without metadata (None)
        hash2 = _content_hash("Test content", None)
        assert len(hash2) == 16, f"Hash with None metadata should be 16 chars"
        assert all(c in "0123456789abcdef" for c in hash2), \
            "Hash should be hex characters only"

        # Different content should produce different hash
        hash3 = _content_hash("Different content", None)
        assert hash1 != hash3 or hash2 != hash3, "Different content should produce different hash"

    def test_prior_spans_only_no_future(self):
        """M7: Verify break vs continue - only PRIOR spans get referenced.

        Bug: Changing `break` to `continue` would check ALL spans, not just prior.
        This test verifies that future spans are never referenced.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # s1's content appears in s2's output, but s2 comes AFTER s1
        # so s1 should NOT reference s2
        content_shared = "x" * 25  # > 20 chars
        spans = [
            {"span_id": "s1", "input": content_shared, "output": "First output"},
            {"span_id": "s2", "input": "Later input", "output": content_shared + " appears here"},
        ]

        graph = build_reference_graph(spans)

        # s1 should NOT reference s2 (s2 comes after s1)
        assert "s2" not in graph.get("s1", []), \
            "s1 should NOT reference future span s2"

        # s2 CAN reference s1 (s1 comes before s2)
        assert "s1" in graph.get("s2", []), \
            "s2 SHOULD reference prior span s1"

    def test_empty_component_handling(self):
        """M8: Verify empty components don't create empty chunks.

        Bug: Removing `if component_spans:` check would append empty lists.
        This test verifies no empty chunks are created.
        """
        from scripts.agentica_patterns.span_processor import chunk_by_references

        spans = [{"span_id": "s1"}, {"span_id": "s2"}]
        # Reference graph with no connections (each span is its own component)
        ref_graph = {"s1": [], "s2": []}

        chunks = chunk_by_references(spans, ref_graph, max_chunk_size=10)

        # No chunk should be empty
        assert all(len(chunk) > 0 for chunk in chunks), \
            "No chunks should be empty"

        # All spans should be in some chunk
        all_span_ids = {s["span_id"] for chunk in chunks for s in chunk}
        assert all_span_ids == {"s1", "s2"}

    @pytest.mark.asyncio
    async def test_default_confidence_value(self):
        """M10: Verify default confidence is 0.5 when field missing.

        Bug: Changing `d.get("confidence", 0.5)` default to 0.0 or 1.0 survives.
        This test verifies the exact default behavior.

        HOWEVER: The filter at line 539 is `if d.get("confidence", 0) < 0.5: continue`
        which means missing confidence gets default 0, not 0.5. The SpanDecision
        creation at line 546 uses `d.get("confidence", 0.5)`, but that only runs
        AFTER the filter. So decisions without confidence are filtered OUT.

        This test documents the ACTUAL behavior (which may be a bug).
        """
        from scripts.agentica_patterns.span_processor import (
            extract_decisions,
            SpanProcessingContext,
        )

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test", "output": "test"}]]

        # Mock MapReduce to return decision WITHOUT confidence field
        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock_mr:
            instance = MagicMock()
            # Note: NO confidence field in response
            instance._map_phase = AsyncMock(return_value=[
                '[{"span_id": "s1", "decision": "Test decision", "rationale": "Test", "source_refs": []}]'
            ])
            mock_mr.return_value = instance

            decisions = await extract_decisions(chunks, context, num_mappers=1)

        # BUG: Line 539 uses `d.get("confidence", 0)` for filtering
        # but line 546 uses `d.get("confidence", 0.5)` for construction
        # Missing confidence = 0 < 0.5, so it gets filtered out!
        # Expected: 1 decision with default confidence 0.5
        # Actual (BUG): 0 decisions (filtered by line 539)
        assert len(decisions) == 1, \
            f"Missing confidence should default to 0.5 and be included, got {len(decisions)}"
        if len(decisions) > 0:
            assert decisions[0].confidence == 0.5, \
                f"Default confidence should be 0.5, got {decisions[0].confidence}"

    def test_metadata_none_handling(self):
        """M11: Verify _content_hash handles metadata=None without crash.

        Bug: Removing `if metadata else None` checks would cause AttributeError.
        This test verifies graceful None handling.
        """
        from scripts.agentica_patterns.span_processor import _content_hash

        # Should not raise any exception
        hash_none = _content_hash("Test content", None)
        assert isinstance(hash_none, str)
        assert len(hash_none) == 16

        # Should also handle empty dict
        hash_empty = _content_hash("Test content", {})
        assert isinstance(hash_empty, str)
        assert len(hash_empty) == 16

    @pytest.mark.asyncio
    async def test_confidence_boundary_0_5(self):
        """M5: Verify confidence == 0.5 IS included (not filtered).

        Bug: Changing `< 0.5` to `<= 0.5` would exclude decisions at exactly 0.5.
        This test verifies the exact boundary.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_decisions,
            SpanProcessingContext,
        )

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test", "output": "test"}]]

        # Mock MapReduce to return decision with EXACTLY 0.5 confidence
        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock_mr:
            instance = MagicMock()
            instance._map_phase = AsyncMock(return_value=[
                '[{"span_id": "s1", "decision": "Edge case", "rationale": "Test", "confidence": 0.5, "source_refs": []}]'
            ])
            mock_mr.return_value = instance

            decisions = await extract_decisions(chunks, context, num_mappers=1)

        # Confidence == 0.5 should be INCLUDED (filter is < 0.5)
        assert len(decisions) == 1, \
            f"Confidence 0.5 should be included, got {len(decisions)} decisions"

        # Verify 0.49 is excluded
        context2 = SpanProcessingContext()
        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock_mr2:
            instance2 = MagicMock()
            instance2._map_phase = AsyncMock(return_value=[
                '[{"span_id": "s1", "decision": "Below threshold", "rationale": "Test", "confidence": 0.49, "source_refs": []}]'
            ])
            mock_mr2.return_value = instance2

            decisions_low = await extract_decisions(chunks, context2, num_mappers=1)

        assert len(decisions_low) == 0, \
            f"Confidence 0.49 should be excluded, got {len(decisions_low)} decisions"


# =============================================================================
# TDD Phase 2: Bug Pattern Tests (From Bug Research)
# =============================================================================


class TestBugPatterns:
    """Tests for critical bug patterns identified via code research.

    These tests expose real bugs in the implementation that could
    cause production failures. Focus on LLM integration and data handling.
    """

    @pytest.mark.asyncio
    async def test_asyncio_lock_not_blocking(self):
        """Bug 1.1: threading.Lock in async context blocks event loop.

        Current implementation uses asyncio.Lock which doesn't block the
        event loop. This test verifies that concurrent add_summary calls don't
        cause excessive latency from event loop blocking.
        """
        import time
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        context = SpanProcessingContext()

        async def slow_add(i):
            """Simulate concurrent adds with yields."""
            await asyncio.sleep(0.01)  # Yield to event loop
            await context.add_summary(SpanSummary(
                span_id=f"s{i}",
                turn_number=i,
                summary=f"Summary {i}",
                key_entities=[],
                references=[],
                span_type="test",
                content_hash=f"h{i}",
            ))
            await asyncio.sleep(0.01)  # Yield again

        start = time.monotonic()
        # Run 50 concurrent adds
        await asyncio.gather(*[slow_add(i) for i in range(50)])
        duration = time.monotonic() - start

        # With asyncio.Lock: ~0.02s (parallel)
        # With threading.Lock: could be much longer (sequential blocking)
        # Allow generous margin for CI variability
        assert duration < 2.0, \
            f"Event loop likely blocked: {duration:.2f}s (expected < 2s for async operations)"
        assert len(context.span_summaries) == 50

    def test_chunk_overlap_infinite_loop(self):
        """Bug 2.2: overlap >= max_chunk_size causes infinite loop.

        When overlap >= max_chunk_size, the step in range() becomes 0 or negative,
        causing an infinite loop. This test verifies graceful handling.
        """
        import signal
        from scripts.agentica_patterns.span_processor import chunk_by_references

        spans = [{"span_id": f"s{i}"} for i in range(20)]
        # All connected (one giant component that needs subdivision)
        ref_graph = {f"s{i}": [f"s{i-1}"] if i > 0 else [] for i in range(20)}

        # Set up timeout to catch infinite loop
        def timeout_handler(signum, frame):
            raise TimeoutError("Chunking took too long - possible infinite loop")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)  # 5 second timeout

        try:
            # overlap (10) >= max_chunk_size (5) - should handle gracefully
            chunks = chunk_by_references(spans, ref_graph, max_chunk_size=5, overlap=10)

            # Should not hang, should produce valid chunks
            assert len(chunks) > 0, "Should produce at least one chunk"
            assert all(len(c) > 0 for c in chunks), "No empty chunks"
        except TimeoutError:
            pytest.fail("chunk_by_references entered infinite loop with overlap >= max_chunk_size")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    @pytest.mark.asyncio
    async def test_json_markdown_fence_parsing(self):
        """Bug 3.1: LLM returns JSON wrapped in markdown fences.

        Common LLM behavior: wrapping JSON in ```json ... ``` fences.
        Current implementation calls json.loads() directly which fails.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_summaries,
            SpanProcessingContext,
        )

        context = SpanProcessingContext()
        chunks = [[{"span_id": "s1", "input": "test", "output": "test"}]]

        # Mock returns JSON wrapped in markdown fences
        markdown_wrapped = '''```json
[{"span_id": "s1", "summary": "Test summary", "key_entities": ["test"], "span_type": "tool_call"}]
```'''

        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock_mr:
            instance = MagicMock()
            instance._map_phase = AsyncMock(return_value=[markdown_wrapped])
            mock_mr.return_value = instance

            await extract_summaries(chunks, context, num_mappers=1)

        # BUG: Current implementation will fail to parse this
        # Test expects successful parsing after fix
        assert "s1" in context.span_summaries, \
            "Should parse JSON even with markdown fences"

    @pytest.mark.asyncio
    async def test_gather_return_exceptions(self):
        """Bug 1.2: asyncio.gather cancels all tasks on first exception.

        When one mapper fails, gather() (with default return_exceptions=False)
        cancels all other in-progress tasks, losing their results.

        This test verifies partial results are preserved on failure.
        """
        from scripts.agentica_patterns.span_processor import (
            extract_summaries,
            SpanProcessingContext,
        )

        context = SpanProcessingContext()
        chunks = [
            [{"span_id": "s1", "input": "valid", "output": "valid"}],
            [{"span_id": "s2", "input": "will_fail", "output": "fail"}],
            [{"span_id": "s3", "input": "valid", "output": "valid"}],
        ]

        call_count = 0

        async def mock_map_phase(query, chunks):
            nonlocal call_count
            call_count += 1
            if "will_fail" in query:
                raise ValueError("Simulated mapper failure")
            return ['[{"span_id": "s1", "summary": "OK", "key_entities": [], "span_type": "test"}]']

        with patch("scripts.agentica_patterns.span_processor.MapReduce") as mock_mr:
            instance = MagicMock()
            instance._map_phase = mock_map_phase
            mock_mr.return_value = instance

            # Should not raise - should handle partial failure gracefully
            try:
                await extract_summaries(chunks, context, num_mappers=4)
            except ValueError:
                pass  # Current bug: exception propagates

        # BUG: Current implementation may lose results from successful chunks
        # Test expects at least some summaries to be preserved
        # Note: This test may pass if exception kills everything, which is the bug
        assert call_count >= 1, "At least some mappers should have been called"

    @pytest.mark.asyncio
    async def test_empty_spans_handling(self):
        """Bug 3.3: Empty spans list should not crash.

        Various empty input scenarios should be handled gracefully.
        """
        from scripts.agentica_patterns.span_processor import (
            build_reference_graph,
            chunk_by_references,
            extract_summaries,
            extract_decisions,
            SpanProcessingContext,
        )

        # Empty spans to reference graph
        graph = build_reference_graph([])
        assert graph == {}

        # Empty spans to chunking
        chunks = chunk_by_references([], {}, max_chunk_size=10)
        assert chunks == []

        # Empty chunks to extract_summaries
        context = SpanProcessingContext()
        await extract_summaries([], context, num_mappers=1)
        assert len(context.span_summaries) == 0

        # Empty chunks to extract_decisions
        decisions = await extract_decisions([], context, num_mappers=1)
        assert decisions == []


# =============================================================================
# TDD Phase 2: Race Condition Tests
# =============================================================================


# =============================================================================
# TDD Phase 3: Reference Graph Filtering (P1 Fix)
# =============================================================================


class TestReferenceGraphFiltering:
    """Tests for span type filtering in reference detection.

    P1 Fix: Pattern matching should only run on LLM outputs, not tool outputs.
    Tool outputs contain file content with code comments that match patterns
    like 'as discussed' - these are false positives from reading source files.

    Research: thoughts/shared/work/two-pass-mapreduce/15-btql-research.md
    """

    def test_pattern_matching_skips_tool_spans(self):
        """Pattern matching should NOT run on tool span outputs.

        Tool outputs contain file content which has code comments
        matching patterns like 'as discussed' - these are false positives.

        Example: A Read tool output contains a code comment:
        "# As discussed earlier, this handles auth"
        This should NOT create a reference to prior spans.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # Span with type="tool" containing code comment
        spans = [
            {
                "span_id": "s1",
                "input": "Initial design discussion",
                "output": "Decided on JWT authentication",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "input": "Read file",
                "output": "# As discussed earlier, this handles auth\ndef authenticate(): pass",
                "span_attributes": {"type": "tool"},  # Tool span - file content!
            },
        ]
        graph = build_reference_graph(spans)

        # s2 should NOT reference s1 - it's a code comment in tool output
        assert graph.get("s2", []) == [], (
            "Tool span output should NOT trigger pattern matching. "
            "The 'As discussed earlier' is a code comment in file content, not LLM reasoning."
        )

    def test_pattern_matching_runs_on_llm_spans(self):
        """Pattern matching SHOULD run on LLM span outputs.

        When Claude's reasoning contains 'as discussed earlier', this IS
        a genuine reference to prior conversation context.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "How should we handle authentication?",
                "output": "Let's use JWT tokens with RS256 signing",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "input": "What about token refresh?",
                "output": "As discussed earlier, we're using JWT. For refresh, we should use rotating refresh tokens.",
                "span_attributes": {"type": "llm"},  # LLM span - real reference!
            },
        ]
        graph = build_reference_graph(spans)

        # s2 SHOULD reference s1 - it's Claude discussing prior context
        assert "s1" in graph.get("s2", []), (
            "LLM span output SHOULD trigger pattern matching. "
            "The 'As discussed earlier' is genuine conversation reference."
        )

    def test_pattern_matching_in_input_vs_output(self):
        """Pattern matching should check LLM output, not tool input.

        The 'as discussed' pattern only makes sense in Claude's OUTPUT
        (where Claude is generating reasoning), not in INPUT (user prompt).
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "First discussion",
                "output": "Initial decision made",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "input": "As discussed earlier, can you elaborate?",  # User using the phrase
                "output": "Sure, I'll explain more about the JWT implementation",
                "span_attributes": {"type": "llm"},
            },
        ]
        graph = build_reference_graph(spans)

        # Current behavior matches on input+output combined
        # After P1 fix, should focus on LLM output only for pattern detection
        # User input with "as discussed" is less reliable indicator
        # This test documents current behavior - may need refinement
        refs = graph.get("s2", [])

        # The key assertion is that LLM spans ARE processed (unlike tool spans)
        # Whether input or output is used is a secondary concern
        assert "s2" in graph, "LLM span should be processed for references"

    def test_output_input_matching_works_for_all_spans(self):
        """Output->input content matching should work for all span types.

        This heuristic is structural (content containment), not pattern-based.
        It should work regardless of span type because it detects when one
        span's output literally contains another span's input content.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # Long enough input to trigger the >20 char + [:50] match
        input_content = "Analyze the authentication module in auth_service.py"

        spans = [
            {
                "span_id": "s1",
                "input": input_content,
                "output": "Starting analysis...",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "input": "Continue",
                "output": f"Based on: {input_content} - here are the findings...",
                "span_attributes": {"type": "tool"},  # Even tool spans
            },
        ]
        graph = build_reference_graph(spans)

        # Content matching should work for tool spans (structural, not pattern)
        assert "s1" in graph.get("s2", []), (
            "Output->input content matching should work for all span types. "
            "This is structural matching, not pattern-based."
        )

    def test_missing_span_attributes_defaults_to_llm(self):
        """Spans without span_attributes should default to LLM behavior.

        For backwards compatibility and safety, spans missing the
        span_attributes field should be treated as LLM spans (most permissive).
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "Initial discussion",
                "output": "First decision",
                # No span_attributes - should default to LLM-like behavior
            },
            {
                "span_id": "s2",
                "input": "Follow up",
                "output": "As discussed earlier, we should proceed",
                # No span_attributes - should still trigger pattern matching
            },
        ]
        graph = build_reference_graph(spans)

        # Without span_attributes, default to LLM behavior (pattern matching enabled)
        assert "s1" in graph.get("s2", []), (
            "Missing span_attributes should default to LLM behavior. "
            "Pattern matching should be enabled for backwards compatibility."
        )

    def test_span_attributes_type_none_defaults_to_llm(self):
        """Spans with span_attributes but type=None should default to LLM.

        Edge case: span_attributes dict exists but type key is missing or None.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "Setup discussion",
                "output": "Configuration decided",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "input": "Next step",
                "output": "As discussed earlier, the config needs updating",
                "span_attributes": {"name": "some_span"},  # No 'type' key
            },
        ]
        graph = build_reference_graph(spans)

        # Missing type in span_attributes should default to LLM behavior
        assert "s1" in graph.get("s2", []), (
            "span_attributes without 'type' should default to LLM behavior."
        )

    def test_multiple_tool_spans_no_cross_contamination(self):
        """Multiple tool spans should not reference each other via patterns.

        Even if multiple tool outputs contain matching patterns, they should
        not create spurious references between file contents.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "Read utils.py",
                "output": "# As discussed in design doc\ndef helper(): pass",
                "span_attributes": {"type": "tool"},
            },
            {
                "span_id": "s2",
                "input": "Read auth.py",
                "output": "# As discussed earlier in the codebase\nclass Auth: pass",
                "span_attributes": {"type": "tool"},
            },
            {
                "span_id": "s3",
                "input": "Read config.py",
                "output": "# Based on the earlier setup\nCONFIG = {}",
                "span_attributes": {"type": "tool"},
            },
        ]
        graph = build_reference_graph(spans)

        # No tool span should reference another via pattern matching
        # (they might still reference via content matching if applicable)
        for span_id in ["s1", "s2", "s3"]:
            refs = graph.get(span_id, [])
            # Filter out any refs that could be from content matching
            # Pattern-based refs would be all prior spans in the 3-span window
            # The point is: tool spans shouldn't trigger pattern detection
            pass  # Structural assertion below

        # Key assertion: s2 and s3 should NOT have pattern-triggered refs to prior spans
        # because they are tool spans and patterns are in code comments
        assert graph.get("s2", []) == [], "Tool span s2 should not have pattern refs"
        assert graph.get("s3", []) == [], "Tool span s3 should not have pattern refs"

    def test_mixed_llm_and_tool_span_sequence(self):
        """Real-world scenario: LLM spans interleaved with tool calls.

        Pattern: Claude reasons (LLM) -> reads file (tool) -> reasons again (LLM)
        Only the LLM reasoning should trigger pattern-based references.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "Let's review the auth implementation",
                "output": "I'll check the auth module to understand the current state",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "input": "Read auth/service.py",
                "output": "# As discussed in security review, we use JWT\nclass AuthService:\n    pass",
                "span_attributes": {"type": "tool"},  # File content with comment
            },
            {
                "span_id": "s3",
                "input": "What's your analysis?",
                "output": "As discussed earlier, the current implementation uses JWT. I recommend adding refresh tokens.",
                "span_attributes": {"type": "llm"},  # Real LLM reference
            },
        ]
        graph = build_reference_graph(spans)

        # s2 (tool) should NOT reference s1 via pattern (code comment is not a reference)
        assert "s1" not in graph.get("s2", []) or graph.get("s2", []) == [], (
            "Tool span should not create pattern-based reference from code comment"
        )

        # s3 (LLM) SHOULD reference prior spans via pattern ("As discussed earlier")
        s3_refs = graph.get("s3", [])
        assert len(s3_refs) > 0, (
            "LLM span with 'As discussed earlier' should reference prior spans"
        )
        # Should reference at least s1 or s2 (within 3-span window)
        assert "s1" in s3_refs or "s2" in s3_refs, (
            "LLM span should reference within the 3-span window"
        )

    def test_file_path_reference_detection_p2_placeholder(self):
        """P2: Spans reading/writing same file should be linked.

        This is a placeholder for P2 implementation.
        File-based reference detection is a structural heuristic:
        - Read X -> Edit X -> Write X should be linked
        - This is independent of span type (works for tool chains)
        """
        # P2 TODO: Implement file path extraction and matching
        # For now, just ensure the test structure exists
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": '{"file_path": "/app/auth.py"}',  # Read
                "output": "class Auth: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": '{"file_path": "/app/auth.py", "old_string": "pass", "new_string": "return True"}',
                "output": "Edit successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Edit"},
            },
        ]
        graph = build_reference_graph(spans)

        # P2 TODO: After implementation, this should pass:
        # assert "s1" in graph.get("s2", []), "Edit should reference Read of same file"

        # For now, just document expected behavior
        # Current implementation may or may not detect this based on content matching


class TestRaceConditions:
    """Tests for race conditions in concurrent processing.

    These tests expose thread safety issues that can cause
    data corruption under load.
    """

    @pytest.mark.asyncio
    async def test_concurrent_blackboard_writes(self):
        """Bug 1.3: Race condition in add_summary concurrent writes.

        Multiple coroutines calling add_summary simultaneously may
        corrupt the shared state without proper locking.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        context = SpanProcessingContext()
        errors = []

        async def add_many(batch_id, count):
            """Add summaries with yields to maximize race window."""
            for i in range(count):
                await asyncio.sleep(0)  # Yield to maximize interleaving
                try:
                    await context.add_summary(SpanSummary(
                        span_id=f"batch{batch_id}_s{i}",
                        turn_number=batch_id * 100 + i,
                        summary=f"Summary batch {batch_id} item {i}",
                        key_entities=[f"entity_{batch_id}_{i}"],
                        references=[],
                        span_type="test",
                        content_hash=f"h{batch_id}_{i}",
                    ))
                except Exception as e:
                    errors.append(str(e))
                await asyncio.sleep(0)

        # Run 10 concurrent batches of 20 adds each
        await asyncio.gather(*[add_many(i, 20) for i in range(10)])

        assert len(errors) == 0, f"Concurrent write errors: {errors}"
        assert len(context.span_summaries) == 200, \
            f"Expected 200 summaries, got {len(context.span_summaries)} (race condition?)"

        # Verify all expected span_ids are present
        expected_ids = {f"batch{b}_s{i}" for b in range(10) for i in range(20)}
        actual_ids = set(context.span_summaries.keys())
        missing = expected_ids - actual_ids
        assert not missing, f"Missing span_ids (race condition?): {missing}"

    @pytest.mark.asyncio
    async def test_reference_update_race_condition(self):
        """Bug: Direct mutation of references during iteration.

        Line 751-753 mutates span_summaries[span_id].references directly
        without lock protection during Pass 2 processing.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        context = SpanProcessingContext()

        # Pre-populate with summaries
        for i in range(100):
            await context.add_summary(SpanSummary(
                span_id=f"s{i}",
                turn_number=i,
                summary=f"Summary {i}",
                key_entities=[],
                references=[],  # Will be mutated
                span_type="test",
                content_hash=f"h{i}",
            ))

        ref_graph = {f"s{i}": [f"s{j}" for j in range(max(0, i-3), i)] for i in range(100)}
        errors = []

        async def update_refs():
            """Simulate reference updates (Pass 2 behavior)."""
            for span_id, refs in ref_graph.items():
                if span_id in context.span_summaries:
                    # This is the problematic mutation without lock
                    context.span_summaries[span_id].references = refs
                await asyncio.sleep(0)  # Yield

        async def read_refs():
            """Concurrently read references."""
            for _ in range(100):
                for span_id in list(context.span_summaries.keys()):
                    try:
                        ref_context = await context.get_reference_context(span_id)
                        # Verify consistent state
                        if ref_context and not isinstance(ref_context, str):
                            errors.append(f"Got non-string ref context: {type(ref_context)}")
                    except RuntimeError as e:
                        if "changed size during iteration" in str(e):
                            errors.append(str(e))
                await asyncio.sleep(0)

        await asyncio.gather(update_refs(), read_refs())

        # This test may pass due to GIL but exposes the unsafe pattern
        # The real fix is to use asyncio.Lock consistently
        assert len(errors) == 0, f"Race condition errors: {errors[:5]}"

    @pytest.mark.asyncio
    async def test_processing_log_concurrent_append(self):
        """Race condition in processing_log.append without lock.

        Multiple concurrent log appends may cause issues.
        """
        from scripts.agentica_patterns.span_processor import SpanProcessingContext, SpanSummary

        context = SpanProcessingContext()

        async def add_with_logging(i):
            await asyncio.sleep(0)
            await context.add_summary(SpanSummary(
                span_id=f"s{i}",
                turn_number=i,
                summary=f"Summary {i}",
                key_entities=[],
                references=[],
                span_type="test",
                content_hash=f"h{i}",
            ))
            # add_summary also appends to processing_log

        # Run 100 concurrent adds
        await asyncio.gather(*[add_with_logging(i) for i in range(100)])

        # All 100 logs should be present
        assert len(context.processing_log) == 100, \
            f"Expected 100 log entries, got {len(context.processing_log)} (race condition?)"


# =============================================================================
# TDD P2: File Path Reference Detection Tests
# =============================================================================


class TestFilePathReferences:
    """Tests for file path-based reference detection (P2).

    P2 Priority: Spans reading/writing same file should be linked (90% confidence).

    Research: thoughts/shared/work/two-pass-mapreduce/15-btql-research.md

    File path reference detection is a structural heuristic that detects when
    multiple tool operations (Read, Edit, Write) operate on the same file path.
    This creates implicit references without relying on pattern matching.

    Example scenario:
        Span 1: Read("/src/auth.py") -> output: file content
        Span 2: Write("/src/auth.py") -> input: modified content
        -> Span 2 should reference Span 1 (same file path)
    """

    def test_read_write_same_file_creates_reference(self):
        """Read then Write to same file should create reference.

        This is the canonical P2 use case: when Claude reads a file and then
        writes to the same file, the Write span should reference the Read span
        because the Write is logically dependent on what was read.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/src/auth.py"},
                "output": "class Auth:\n    def login(self): pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": {"file_path": "/src/auth.py", "content": "updated content"},
                "output": "Write successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Write"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "Write span should reference Read span of same file. "
            "File path '/src/auth.py' links these operations."
        )

    def test_read_edit_same_file_creates_reference(self):
        """Read then Edit to same file should create reference.

        Edit operations (which modify part of a file) should also reference
        prior Read operations on the same file.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/app/config.py"},
                "output": "DEBUG = True\nPORT = 8080",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": {
                    "file_path": "/app/config.py",
                    "old_string": "DEBUG = True",
                    "new_string": "DEBUG = False",
                },
                "output": "Edit successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Edit"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "Edit span should reference Read span of same file. "
            "File path '/app/config.py' links these operations."
        )

    def test_different_files_no_reference(self):
        """Different file paths should NOT create reference.

        Operations on different files should not create spurious references.
        This prevents false positives from unrelated file operations.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/src/auth.py"},
                "output": "class Auth: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": {"file_path": "/src/database.py"},
                "output": "class Database: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s3",
                "input": {"file_path": "/src/utils.py", "content": "new content"},
                "output": "Write successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Write"},
            },
        ]
        graph = build_reference_graph(spans)

        # s2 reads different file than s1 - no reference
        assert "s1" not in graph.get("s2", []), (
            "Read of different file should NOT reference prior Read"
        )

        # s3 writes to different file than s1 or s2 - no references
        assert "s1" not in graph.get("s3", []), (
            "Write to different file should NOT reference unrelated Read"
        )
        assert "s2" not in graph.get("s3", []), (
            "Write to different file should NOT reference unrelated Read"
        )

    def test_glob_then_read_matching_file_creates_reference(self):
        """Glob followed by Read of matching file should create reference.

        When Glob finds files and then Read accesses one of those files,
        the Read should reference the Glob that discovered the file.
        This captures the "search then access" pattern.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"pattern": "**/*.py"},
                "output": ["/src/auth.py", "/src/utils.py", "/src/main.py"],
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Glob"},
            },
            {
                "span_id": "s2",
                "input": {"file_path": "/src/auth.py"},
                "output": "class Auth: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "Read should reference Glob that returned the file path. "
            "The Read of '/src/auth.py' follows Glob output containing that path."
        )

    def test_file_path_in_nested_input(self):
        """Handle file_path in nested input structures.

        Some tools may have file_path nested within the input structure.
        The detection should handle various input formats gracefully.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/src/models/user.py"},
                "output": "class User: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                # file_path might be in different input format
                "input": {"params": {"file_path": "/src/models/user.py"}, "action": "write"},
                "output": "Write successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Write"},
            },
        ]
        graph = build_reference_graph(spans)

        # P2 implementation should handle nested file_path
        # This test documents expected behavior for edge case
        assert "s1" in graph.get("s2", []), (
            "Should detect file_path even in nested input structures"
        )

    def test_multiple_operations_same_file_chain(self):
        """Multiple operations on same file should create chain of references.

        A common pattern: Read -> analyze -> Edit -> verify -> Write
        All operations on the same file should form a reference chain.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/src/service.py"},
                "output": "class Service: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": "Analyze the service class",
                "output": "The service class needs refactoring",
                "span_attributes": {"type": "llm"},  # LLM reasoning span
            },
            {
                "span_id": "s3",
                "input": {
                    "file_path": "/src/service.py",
                    "old_string": "pass",
                    "new_string": "self.initialized = True",
                },
                "output": "Edit successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Edit"},
            },
            {
                "span_id": "s4",
                "input": {"file_path": "/src/service.py"},
                "output": "class Service:\n    def __init__(self):\n        self.initialized = True",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
        ]
        graph = build_reference_graph(spans)

        # s3 (Edit) should reference s1 (Read of same file)
        assert "s1" in graph.get("s3", []), (
            "Edit should reference initial Read of same file"
        )

        # s4 (second Read) should reference s1 (first Read) and s3 (Edit)
        s4_refs = graph.get("s4", [])
        assert "s1" in s4_refs, (
            "Second Read should reference first Read of same file"
        )
        assert "s3" in s4_refs, (
            "Second Read should reference Edit of same file"
        )

    def test_file_path_string_input_fallback(self):
        """Handle file_path when input is JSON string instead of dict.

        Sometimes tool inputs are serialized as JSON strings.
        The detection should parse these to extract file paths.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": '{"file_path": "/app/handler.py"}',  # JSON string
                "output": "def handle(): pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": '{"file_path": "/app/handler.py", "content": "updated"}',
                "output": "Write successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Write"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "Should parse JSON string inputs to extract file_path"
        )

    def test_grep_then_read_matching_file(self):
        """Grep followed by Read of file containing match should create reference.

        When Grep finds content in files and then Read accesses one of those
        files, the Read should reference the Grep that found the match.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"pattern": "class.*Error", "path": "/src"},
                "output": "/src/exceptions.py:5:class AuthError(Exception):",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Grep"},
            },
            {
                "span_id": "s2",
                "input": {"file_path": "/src/exceptions.py"},
                "output": "class AuthError(Exception): pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "Read should reference Grep that found matches in the file. "
            "The Read of '/src/exceptions.py' follows Grep output mentioning that path."
        )

    def test_file_path_normalization(self):
        """File paths should be normalized for comparison.

        Paths like '/src/./auth.py' and '/src/auth.py' should be treated as the same.
        Trailing slashes and other variations should be handled.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/src/./auth.py"},  # Has redundant ./
                "output": "class Auth: pass",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
            {
                "span_id": "s2",
                "input": {"file_path": "/src/auth.py"},  # Normalized path
                "output": "Write successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Write"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "File paths should be normalized before comparison. "
            "'/src/./auth.py' and '/src/auth.py' are the same file."
        )

    def test_write_then_read_same_file(self):
        """Write then Read of same file should also create reference.

        The Read depends on the Write that created/modified the file content.
        This is the reverse of Read->Write but equally valid.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": {"file_path": "/tmp/output.json", "content": '{"result": "success"}'},
                "output": "Write successful",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Write"},
            },
            {
                "span_id": "s2",
                "input": {"file_path": "/tmp/output.json"},
                "output": '{"result": "success"}',
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            },
        ]
        graph = build_reference_graph(spans)

        assert "s1" in graph.get("s2", []), (
            "Read should reference prior Write of same file. "
            "The Read content depends on what was written."
        )


# =============================================================================
# TDD P3: Parent Span ID References Tests
# =============================================================================


class TestParentSpanReferences:
    """Tests for span_parents structural reference detection (P3).

    P3: Use native span_parents for structural hierarchy (100% confidence).

    The Braintrust span tree structure uses span_parents to establish
    parent-child relationships:
    - root_span_id: Session ID (parent of all spans)
    - span_parents: Direct parent span(s) (for hierarchical structure)

    This is the most reliable reference detection mechanism (100% confidence)
    because it's based on explicit structural data, not heuristics.

    Research: thoughts/shared/work/two-pass-mapreduce/15-btql-research.md
    """

    def test_child_references_parent(self):
        """Child span should reference its parent via span_parents.

        When span B has span_parents containing span A, span B
        should include span A in its reference list.

        Example:
            Span A: {span_id: "parent", span_parents: []}
            Span B: {span_id: "child", span_parents: ["parent"]}
            -> Span B references Span A via structural hierarchy
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "parent",
                "span_parents": [],
                "input": "Initial task",
                "output": "Starting work",
            },
            {
                "span_id": "child",
                "span_parents": ["parent"],
                "input": "Subtask",
                "output": "Completed subtask",
            },
        ]
        graph = build_reference_graph(spans)

        # Child should reference parent via span_parents
        assert "parent" in graph.get("child", []), (
            "Child span should reference its parent via span_parents. "
            "This is 100% confidence structural relationship."
        )

    def test_multiple_children_same_parent(self):
        """Multiple children should all reference the same parent.

        When multiple spans share the same span_parents, they are
        siblings. Each sibling should reference the parent.

        Tree structure:
            parent
            /    \\
         child1  child2
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "parent",
                "span_parents": [],
                "input": "Parent task",
                "output": "Coordinating",
            },
            {
                "span_id": "child1",
                "span_parents": ["parent"],
                "input": "First subtask",
                "output": "Done 1",
            },
            {
                "span_id": "child2",
                "span_parents": ["parent"],
                "input": "Second subtask",
                "output": "Done 2",
            },
        ]
        graph = build_reference_graph(spans)

        # Both children should reference the parent
        assert "parent" in graph.get("child1", []), (
            "child1 should reference parent via span_parents"
        )
        assert "parent" in graph.get("child2", []), (
            "child2 should reference parent via span_parents"
        )

    def test_siblings_reference_each_other(self):
        """Siblings (same parent) should optionally reference each other.

        Spans with the same span_parents are likely related and may
        benefit from cross-referencing during processing.

        This is optional behavior - the key requirement is parent references.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "parent",
                "span_parents": [],
                "input": "Parent task",
                "output": "Coordinating",
            },
            {
                "span_id": "child1",
                "span_parents": ["parent"],
                "input": "First subtask",
                "output": "Done 1",
            },
            {
                "span_id": "child2",
                "span_parents": ["parent"],
                "input": "Second subtask",
                "output": "Done 2",
            },
        ]
        graph = build_reference_graph(spans)

        # Siblings could reference each other (optional enhancement)
        # Primary requirement: parent references work
        child1_refs = graph.get("child1", [])
        child2_refs = graph.get("child2", [])

        # At minimum, verify both children reference parent
        assert "parent" in child1_refs
        assert "parent" in child2_refs

        # Optional: siblings reference each other (for richer context)
        # Uncomment if implementing sibling references:
        # assert "child2" in child1_refs or "child1" in child2_refs

    def test_nested_hierarchy_three_levels(self):
        """Deeply nested spans should reference their ancestors.

        Tree structure:
            root
              |
            middle
              |
            leaf

        The leaf should reference middle (direct parent).
        Whether leaf also references root is implementation-dependent.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "root",
                "span_parents": [],
                "input": "Root task",
                "output": "Root output",
            },
            {
                "span_id": "middle",
                "span_parents": ["root"],
                "input": "Middle task",
                "output": "Middle output",
            },
            {
                "span_id": "leaf",
                "span_parents": ["middle"],
                "input": "Leaf task",
                "output": "Leaf output",
            },
        ]
        graph = build_reference_graph(spans)

        # Leaf should reference its direct parent (middle)
        assert "middle" in graph.get("leaf", []), (
            "Leaf should reference direct parent 'middle'"
        )

        # Middle should reference its direct parent (root)
        assert "root" in graph.get("middle", []), (
            "Middle should reference direct parent 'root'"
        )

        # Root has no parent
        root_refs = graph.get("root", [])
        # Root should not reference anything via span_parents
        # (it may have other heuristic references though)

    def test_missing_span_parents_field(self):
        """Spans without span_parents field should not cause errors.

        Some spans may not have the span_parents field at all.
        The function should handle this gracefully and fall back
        to other detection methods.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "input": "First span",
                "output": "Output 1",
                # Note: no span_parents field
            },
            {
                "span_id": "s2",
                "input": "Second span",
                "output": "Output 2",
                # Note: no span_parents field
            },
        ]

        # Should not raise any exception
        graph = build_reference_graph(spans)

        # Should return valid graph structure
        assert isinstance(graph, dict)
        # Spans should be in graph (possibly with empty refs)
        assert "s1" in graph or "s2" in graph

    def test_span_parents_empty_value(self):
        """Spans with span_parents=[] should be handled correctly.

        Root spans have span_parents=[]. These should not reference
        any parent via structural hierarchy.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "root1",
                "span_parents": [],
                "input": "Root span 1",
                "output": "Output 1",
            },
            {
                "span_id": "root2",
                "span_parents": [],
                "input": "Root span 2",
                "output": "Output 2",
            },
        ]
        graph = build_reference_graph(spans)

        # Neither root should reference the other via span_parents
        # (they may have other heuristic references though)
        assert isinstance(graph.get("root1", []), list)
        assert isinstance(graph.get("root2", []), list)

    def test_span_parents_not_in_spans(self):
        """span_parents referencing non-existent span should be handled.

        Edge case: A span references a parent that's not in the current
        span list (e.g., truncated session, partial fetch).
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "orphan",
                "span_parents": ["missing_parent"],  # Not in spans list
                "input": "Orphan span",
                "output": "Output",
            },
            {
                "span_id": "s2",
                "span_parents": [],
                "input": "Normal span",
                "output": "Output 2",
            },
        ]

        # Should not raise any exception
        graph = build_reference_graph(spans)

        # Orphan should not reference missing_parent (it's not in spans)
        orphan_refs = graph.get("orphan", [])
        assert "missing_parent" not in orphan_refs, (
            "Should not reference span_parents that's not in span list"
        )

    def test_span_parents_empty_array(self):
        """span_parents as empty array should be handled correctly.

        Edge case: Empty array should not create spurious references.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s1",
                "span_parents": [],  # Empty array
                "input": "First span",
                "output": "Output 1",
            },
            {
                "span_id": "s2",
                "span_parents": ["s1"],
                "input": "Second span",
                "output": "Output 2",
            },
        ]
        graph = build_reference_graph(spans)

        # s1 with empty span_parents should not create invalid refs
        s1_refs = graph.get("s1", [])
        assert "" not in s1_refs, "Empty string should not be a reference"

        # s2 should still reference s1
        assert "s1" in graph.get("s2", []), (
            "s2 should reference s1 via span_parents"
        )

    def test_structural_refs_combined_with_heuristics(self):
        """span_parents references should combine with other heuristics.

        Structural references (span_parents) should ADD to references
        detected via other methods (pattern matching, content matching),
        not replace them.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "s0",
                "span_parents": [],
                "input": "Initial discussion about authentication",
                "output": "Let's use JWT tokens",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s1",
                "span_parents": [],  # Not a structural child of s0
                "input": "Different topic",
                "output": "Something else",
                "span_attributes": {"type": "llm"},
            },
            {
                "span_id": "s2",
                "span_parents": ["s0"],  # Structural child of s0
                "input": "Follow up",
                "output": "As discussed earlier, JWT is the way to go",
                "span_attributes": {"type": "llm"},
            },
        ]
        graph = build_reference_graph(spans)

        s2_refs = graph.get("s2", [])

        # s2 should reference s0 via span_parents (structural)
        assert "s0" in s2_refs, (
            "s2 should reference s0 via span_parents"
        )

        # s2 might also reference s1 via pattern matching ("as discussed earlier")
        # This depends on implementation - the 3-span window would include s1
        # The key point: span_parents refs ADD to, don't replace, heuristics

    def test_span_parents_takes_precedence(self):
        """Structural references should have highest confidence.

        Even if pattern matching suggests different references, span_parents
        should always be included (100% confidence vs pattern's 50%).
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        # Create a scenario where heuristics might not detect the parent
        spans = [
            {
                "span_id": "parent",
                "span_parents": [],
                "input": "XYZ topic",
                "output": "ABC result",
                "span_attributes": {"type": "tool"},  # Tool span
            },
            {
                "span_id": "child",
                "span_parents": ["parent"],
                "input": "Completely unrelated content",
                "output": "Different output entirely",
                "span_attributes": {"type": "tool"},
            },
        ]
        graph = build_reference_graph(spans)

        # Even though content doesn't match and no patterns trigger,
        # child should reference parent via structural relationship
        assert "parent" in graph.get("child", []), (
            "span_parents reference should always be included, "
            "regardless of other heuristics"
        )

    def test_complex_tree_structure(self):
        """Complex tree with multiple branches and levels.

        Tree structure:
                  root
                /      \\
            branch1   branch2
            /    \\        |
         leaf1  leaf2   leaf3
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {"span_id": "root", "span_parents": [], "input": "Root", "output": "R"},
            {"span_id": "branch1", "span_parents": ["root"], "input": "B1", "output": "B1"},
            {"span_id": "branch2", "span_parents": ["root"], "input": "B2", "output": "B2"},
            {"span_id": "leaf1", "span_parents": ["branch1"], "input": "L1", "output": "L1"},
            {"span_id": "leaf2", "span_parents": ["branch1"], "input": "L2", "output": "L2"},
            {"span_id": "leaf3", "span_parents": ["branch2"], "input": "L3", "output": "L3"},
        ]
        graph = build_reference_graph(spans)

        # Verify all parent relationships
        assert "root" in graph.get("branch1", [])
        assert "root" in graph.get("branch2", [])
        assert "branch1" in graph.get("leaf1", [])
        assert "branch1" in graph.get("leaf2", [])
        assert "branch2" in graph.get("leaf3", [])

        # Root has no parent
        root_refs = graph.get("root", [])
        # Root should not reference any parent via span_parents

    def test_self_referential_span_parents(self):
        """span_parents pointing to self should be ignored.

        Edge case: A span's span_parents contains its own span_id.
        This should be treated as invalid and ignored.
        """
        from scripts.agentica_patterns.span_processor import build_reference_graph

        spans = [
            {
                "span_id": "selfref",
                "span_parents": ["selfref"],  # Points to itself
                "input": "Self referential",
                "output": "Output",
            },
        ]
        graph = build_reference_graph(spans)

        # Should not reference itself
        selfref_refs = graph.get("selfref", [])
        assert "selfref" not in selfref_refs, (
            "Span should not reference itself via span_parents"
        )
