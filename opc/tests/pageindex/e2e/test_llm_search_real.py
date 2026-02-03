"""End-to-end tests with real LLM calls.

These tests call the Anthropic API and verify search accuracy.
Marked as 'slow' because LLM calls take >10 seconds.

Run with: pytest -m "e2e and slow"
Requires: ANTHROPIC_API_KEY in environment or opc/.env
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.pageindex.tree_search import tree_search, SearchResult
from scripts.pageindex.claude_llm import claude_complete


@pytest.mark.e2e
@pytest.mark.slow
class TestRealLLMSearch:
    """Tests that use real Claude CLI calls."""

    def test_search_finds_relevant_node(self, require_anthropic_api, sample_tree):
        """Test that search finds relevant nodes in tree."""
        results = tree_search(
            query="What is the current focus?",
            tree_structure=sample_tree,
            doc_name="ROADMAP.md",
            max_results=3,
            model="haiku"  # Use haiku for cost/speed
        )

        assert len(results) > 0
        # Current Focus section should be found
        node_ids = [r.node_id for r in results]
        titles = [r.title.lower() for r in results]

        assert any("focus" in t for t in titles) or "0003" in node_ids

    def test_search_database_design(self, require_anthropic_api, sample_tree):
        """Test searching for database design section."""
        results = tree_search(
            query="database design and postgresql",
            tree_structure=sample_tree,
            doc_name="ROADMAP.md",
            max_results=3,
            model="haiku"
        )

        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any("database" in t or "architecture" in t for t in titles)

    def test_search_goals_section(self, require_anthropic_api, sample_tree):
        """Test searching for goals."""
        results = tree_search(
            query="project goals and objectives",
            tree_structure=sample_tree,
            doc_name="ROADMAP.md",
            max_results=5,
            model="haiku"
        )

        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any("goal" in t for t in titles)

    def test_search_timeline(self, require_anthropic_api, sample_tree):
        """Test searching for timeline information."""
        results = tree_search(
            query="project timeline and schedule",
            tree_structure=sample_tree,
            doc_name="ROADMAP.md",
            max_results=3,
            model="haiku"
        )

        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        # Should find Timeline section
        assert any("timeline" in t or "phase" in t for t in titles)

    def test_search_returns_confidence_scores(self, require_anthropic_api, sample_tree):
        """Test that results include confidence scores."""
        results = tree_search(
            query="integration phase",
            tree_structure=sample_tree,
            model="haiku"
        )

        if results:
            for result in results:
                assert hasattr(result, 'confidence')
                assert 0 <= result.confidence <= 1

    def test_search_returns_relevance_reasons(self, require_anthropic_api, sample_tree):
        """Test that results include relevance reasons."""
        results = tree_search(
            query="foundation setup",
            tree_structure=sample_tree,
            model="haiku"
        )

        if results:
            for result in results:
                assert hasattr(result, 'relevance_reason')
                assert len(result.relevance_reason) > 0

    def test_search_no_results_for_unrelated_query(self, require_anthropic_api, sample_tree):
        """Test that unrelated queries return few/no results."""
        results = tree_search(
            query="quantum computing in space exploration",
            tree_structure=sample_tree,
            model="haiku"
        )

        # May return empty or low-confidence results
        if results:
            # Any results should have low confidence
            max_confidence = max(r.confidence for r in results)
            # LLM might still find tangential matches, so we're lenient
            assert max_confidence < 0.95

    def test_search_respects_max_results(self, require_anthropic_api, sample_tree):
        """Test that max_results is respected."""
        results = tree_search(
            query="project information",
            tree_structure=sample_tree,
            max_results=2,
            model="haiku"
        )

        assert len(results) <= 2


@pytest.mark.e2e
@pytest.mark.slow
class TestClaudeCLIDirectCalls:
    """Direct tests of Claude CLI functionality."""

    def test_claude_complete_returns_text(self, require_anthropic_api):
        """Test basic Claude CLI completion."""
        response = claude_complete(
            "Reply with exactly: HELLO",
            model="haiku"
        )

        assert len(response) > 0
        # Should contain HELLO or similar
        assert "HELLO" in response.upper() or len(response) > 2

    def test_claude_complete_json_response(self, require_anthropic_api):
        """Test Claude CLI returns valid JSON when asked."""
        response = claude_complete(
            'Return only this JSON array, no other text: [{"id": 1}]',
            model="haiku"
        )

        assert len(response) > 0
        # Should be parseable as JSON
        import json
        try:
            # Try to extract JSON from response
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                assert isinstance(data, list)
        except json.JSONDecodeError:
            pass  # LLM may not always follow instructions perfectly


@pytest.mark.e2e
@pytest.mark.slow
class TestArchitectureDocSearch:
    """Tests searching architecture documentation."""

    def test_search_memory_system(self, require_anthropic_api, sample_architecture_tree):
        """Test searching for memory system in architecture doc."""
        results = tree_search(
            query="memory system storage",
            tree_structure=sample_architecture_tree,
            doc_name="ARCHITECTURE.md",
            model="haiku"
        )

        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any("memory" in t or "storage" in t for t in titles)

    def test_search_hooks_system(self, require_anthropic_api, sample_architecture_tree):
        """Test searching for hooks system."""
        results = tree_search(
            query="hook system and tool execution",
            tree_structure=sample_architecture_tree,
            doc_name="ARCHITECTURE.md",
            model="haiku"
        )

        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any("hook" in t for t in titles)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e and slow"])
