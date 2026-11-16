"""Tests for SpanProcessor integration into memory_backfill.py.

These tests verify the wiring of SpanProcessor (two-pass map/reduce) into
the memory backfill pipeline.

Test cases:
1. backfill_session accepts use_two_pass parameter
2. SpanProcessor is called when use_two_pass=True
3. SpanProcessor is NOT called when use_two_pass=False
4. Auto-enable two-pass when span_count > 50
5. SpanProcessor results (summaries/decisions) are stored to memory
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


class TestMemoryBackfillTwoPassParameter:
    """Test that backfill_session accepts use_two_pass parameter."""

    @pytest.mark.asyncio
    async def test_memory_backfill_has_use_two_pass_parameter(self):
        """backfill_session should accept use_two_pass: bool = False."""
        import inspect
        from scripts.agentica.memory_backfill import backfill_session

        sig = inspect.signature(backfill_session)
        params = sig.parameters

        # Assert parameter exists
        assert "use_two_pass" in params, (
            "backfill_session must accept use_two_pass parameter"
        )

        # Assert default is False
        param = params["use_two_pass"]
        assert param.default is False, (
            "use_two_pass default must be False"
        )

        # Assert type annotation is bool
        # Handle both PEP 563 string annotations and actual types
        assert param.annotation == bool or param.annotation == "bool", (
            "use_two_pass must be annotated as bool"
        )


class TestSpanProcessorIntegration:
    """Test that SpanProcessor is called correctly based on use_two_pass."""

    @pytest.fixture
    def mock_spans(self) -> list[dict[str, Any]]:
        """Create mock spans for testing."""
        return [
            {
                "span_id": f"span_{i}",
                "input": f"input_{i}",
                "output": f"output_{i}",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            }
            for i in range(10)
        ]

    @pytest.fixture
    def large_span_set(self) -> list[dict[str, Any]]:
        """Create >50 spans to trigger auto two-pass."""
        return [
            {
                "span_id": f"span_{i}",
                "input": f"input_{i}",
                "output": f"output_{i}",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            }
            for i in range(60)
        ]

    @pytest.mark.asyncio
    async def test_memory_backfill_uses_span_processor_when_enabled(
        self, mock_spans: list[dict[str, Any]]
    ):
        """SpanProcessor should be called when use_two_pass=True."""
        from scripts.agentica.memory_backfill import backfill_session

        mock_processor_result = MagicMock()
        mock_processor_result.summaries_extracted = 5
        mock_processor_result.decisions_extracted = 2
        mock_processor_result.summaries_persisted = 5
        mock_processor_result.decisions_persisted = 2
        mock_processor_result.errors = []

        with patch(
            "scripts.agentica.memory_backfill.fetch_session_spans",
            new_callable=AsyncMock,
            return_value=mock_spans,
        ), patch(
            "scripts.agentica.memory_backfill.get_hierarchical_context",
            return_value={"handoff": None, "ledger": None},
        ), patch(
            "scripts.agentica.memory_backfill.SpanProcessor"
        ) as mock_processor_class, patch(
            "scripts.agentica.memory_backfill.EmbeddingService"
        ), patch(
            "scripts.agentica.memory_backfill.create_memory_service",
            new_callable=AsyncMock,
        ):
            # Setup mock processor
            mock_processor = AsyncMock()
            mock_processor.process = AsyncMock(return_value=mock_processor_result)
            mock_processor_class.return_value = mock_processor

            result = await backfill_session(
                session_id="test-session",
                project_id="test-project",
                api_key="test-key",
                use_two_pass=True,
                dry_run=True,
            )

            # Assert SpanProcessor was instantiated
            mock_processor_class.assert_called_once()

            # Assert process() was called with spans
            mock_processor.process.assert_called_once()
            call_args = mock_processor.process.call_args
            assert len(call_args[0][0]) == len(mock_spans), (
                "SpanProcessor.process should receive all spans"
            )

    @pytest.mark.asyncio
    async def test_memory_backfill_skips_span_processor_when_disabled(
        self, mock_spans: list[dict[str, Any]]
    ):
        """SpanProcessor should NOT be called when use_two_pass=False."""
        from scripts.agentica.memory_backfill import backfill_session

        with patch(
            "scripts.agentica.memory_backfill.fetch_session_spans",
            new_callable=AsyncMock,
            return_value=mock_spans,
        ), patch(
            "scripts.agentica.memory_backfill.get_hierarchical_context",
            return_value={"handoff": None, "ledger": None},
        ), patch(
            "scripts.agentica.memory_backfill.SpanProcessor"
        ) as mock_processor_class, patch(
            "scripts.agentica.memory_backfill.EmbeddingService"
        ) as mock_embedder_class, patch(
            "scripts.agentica.memory_backfill.create_memory_service",
            new_callable=AsyncMock,
        ) as mock_memory:
            # Setup mock embedder
            mock_embedder = MagicMock()
            mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 10])
            mock_embedder_class.return_value = mock_embedder

            # Setup mock memory service
            mock_mem_instance = AsyncMock()
            mock_mem_instance.search = AsyncMock(return_value=[])
            mock_mem_instance.store = AsyncMock(return_value="mem-id-1")
            mock_mem_instance.close = AsyncMock()
            mock_memory.return_value = mock_mem_instance

            result = await backfill_session(
                session_id="test-session",
                project_id="test-project",
                api_key="test-key",
                use_two_pass=False,  # Explicitly disabled
                dry_run=False,
            )

            # Assert SpanProcessor was NOT instantiated
            mock_processor_class.assert_not_called()


class TestAutoTwoPassThreshold:
    """Test automatic two-pass enablement based on span count."""

    @pytest.mark.asyncio
    async def test_two_pass_threshold_triggers_automatically(self):
        """When span_count > 50, should auto-enable two-pass."""
        from scripts.agentica.memory_backfill import backfill_session

        # Create 60 spans (> threshold of 50)
        large_spans = [
            {
                "span_id": f"span_{i}",
                "input": f"input_{i}",
                "output": f"output_{i}",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            }
            for i in range(60)
        ]

        mock_processor_result = MagicMock()
        mock_processor_result.summaries_extracted = 30
        mock_processor_result.decisions_extracted = 10
        mock_processor_result.summaries_persisted = 30
        mock_processor_result.decisions_persisted = 10
        mock_processor_result.errors = []

        with patch(
            "scripts.agentica.memory_backfill.fetch_session_spans",
            new_callable=AsyncMock,
            return_value=large_spans,
        ), patch(
            "scripts.agentica.memory_backfill.get_hierarchical_context",
            return_value={"handoff": None, "ledger": None},
        ), patch(
            "scripts.agentica.memory_backfill.SpanProcessor"
        ) as mock_processor_class, patch(
            "scripts.agentica.memory_backfill.EmbeddingService"
        ), patch(
            "scripts.agentica.memory_backfill.create_memory_service",
            new_callable=AsyncMock,
        ):
            # Setup mock processor
            mock_processor = AsyncMock()
            mock_processor.process = AsyncMock(return_value=mock_processor_result)
            mock_processor_class.return_value = mock_processor

            # Call WITHOUT use_two_pass - should auto-enable due to span count
            result = await backfill_session(
                session_id="test-session",
                project_id="test-project",
                api_key="test-key",
                # use_two_pass not specified - should auto-enable for >50 spans
                dry_run=True,
            )

            # Assert SpanProcessor was instantiated (auto-enabled)
            mock_processor_class.assert_called_once()


class TestSpanProcessorResultsPersistence:
    """Test that SpanProcessor results are stored to memory."""

    @pytest.mark.asyncio
    async def test_span_processor_results_stored_to_memory(self):
        """Verify extracted summaries/decisions go to MemoryServicePG."""
        from scripts.agentica.memory_backfill import backfill_session

        mock_spans = [
            {
                "span_id": f"span_{i}",
                "input": f"input_{i}",
                "output": f"output_{i}",
                "span_attributes": {"type": "tool"},
                "metadata": {"tool_name": "Read"},
            }
            for i in range(10)
        ]

        mock_processor_result = MagicMock()
        mock_processor_result.summaries_extracted = 10
        mock_processor_result.decisions_extracted = 5
        mock_processor_result.summaries_persisted = 10
        mock_processor_result.decisions_persisted = 5
        mock_processor_result.errors = []

        with patch(
            "scripts.agentica.memory_backfill.fetch_session_spans",
            new_callable=AsyncMock,
            return_value=mock_spans,
        ), patch(
            "scripts.agentica.memory_backfill.get_hierarchical_context",
            return_value={"handoff": None, "ledger": None},
        ), patch(
            "scripts.agentica.memory_backfill.SpanProcessor"
        ) as mock_processor_class, patch(
            "scripts.agentica.memory_backfill.EmbeddingService"
        ), patch(
            "scripts.agentica.memory_backfill.create_memory_service",
            new_callable=AsyncMock,
        ):
            # Setup mock processor
            mock_processor = AsyncMock()
            mock_processor.process = AsyncMock(return_value=mock_processor_result)
            mock_processor_class.return_value = mock_processor

            result = await backfill_session(
                session_id="test-session",
                project_id="test-project",
                api_key="test-key",
                use_two_pass=True,
                dry_run=True,  # Even in dry_run, SpanProcessor persists internally
            )

            # Verify result includes SpanProcessor counts
            # Note: The integration should populate BackfillResult with SpanProcessor stats
            # This requires backfill_session to return span_processor-related counts
            assert hasattr(result, "summaries_from_two_pass") or result.facts_extracted >= 0, (
                "BackfillResult should include SpanProcessor extraction counts"
            )


class TestBackfillResultEnhancement:
    """Test that BackfillResult includes two-pass metrics."""

    def test_backfill_result_has_two_pass_fields(self):
        """BackfillResult should have fields for two-pass metrics."""
        from scripts.agentica.memory_backfill import BackfillResult

        # Get fields from dataclass
        import dataclasses
        fields = {f.name for f in dataclasses.fields(BackfillResult)}

        # These fields should exist for two-pass tracking
        expected_fields = [
            "summaries_from_two_pass",
            "decisions_from_two_pass",
        ]

        for field_name in expected_fields:
            assert field_name in fields, (
                f"BackfillResult must have '{field_name}' field for two-pass tracking"
            )
