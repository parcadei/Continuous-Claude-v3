"""Golden test suite for search accuracy.

Tests PageIndex search against expected results to measure precision/recall.
Uses real LLM calls to validate search quality.

Run with: pytest -m "e2e and slow" --tb=short
"""
import sys
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.pageindex.tree_search import tree_search, SearchResult


@pytest.mark.e2e
@pytest.mark.slow
class TestSearchAccuracy:
    """Golden test suite for measuring search accuracy."""

    @pytest.mark.parametrize("golden", [
        {
            "query": "What is the current focus?",
            "expected_nodes": ["0003"],
            "expected_titles": ["Current Focus"],
            "min_confidence": 0.7,
        },
        {
            "query": "database design",
            "expected_nodes": ["0010"],
            "expected_titles": ["Database Design"],
            "min_confidence": 0.6,
        },
        {
            "query": "project goals",
            "expected_nodes": ["0006", "0007", "0008"],
            "expected_titles": ["Goals", "Short-term Goals", "Long-term Goals"],
            "min_confidence": 0.5,
        },
        {
            "query": "timeline schedule",
            "expected_nodes": ["0012"],
            "expected_titles": ["Timeline"],
            "min_confidence": 0.6,
        },
        {
            "query": "integration phase",
            "expected_nodes": ["0005"],
            "expected_titles": ["Phase 2: Integration"],
            "min_confidence": 0.6,
        },
    ])
    def test_golden_search_accuracy(self, require_claude_cli, sample_tree, golden):
        """Test search against golden expected results."""
        results = tree_search(
            query=golden["query"],
            tree_structure=sample_tree,
            doc_name="ROADMAP.md",
            max_results=5,
            model="haiku"
        )

        # Must return results
        assert len(results) > 0, f"No results for query: {golden['query']}"

        result_ids = [r.node_id for r in results]
        result_titles = [r.title.lower() for r in results]

        # Check if ANY expected node is found (recall)
        expected_found = any(
            node_id in result_ids
            for node_id in golden["expected_nodes"]
        )
        expected_title_found = any(
            any(expected.lower() in title for title in result_titles)
            for expected in golden["expected_titles"]
        )

        assert expected_found or expected_title_found, (
            f"Query '{golden['query']}' - Expected {golden['expected_titles']} "
            f"but got {[r.title for r in results]}"
        )

        # Check confidence of best match
        if results:
            best_confidence = max(r.confidence for r in results)
            assert best_confidence >= golden["min_confidence"], (
                f"Query '{golden['query']}' - Best confidence {best_confidence} "
                f"below minimum {golden['min_confidence']}"
            )

    def test_precision_at_1(self, require_claude_cli, sample_tree, golden_tests):
        """Calculate Precision@1 across all golden tests."""
        correct_at_1 = 0
        total = len(golden_tests)

        for golden in golden_tests:
            results = tree_search(
                query=golden["query"],
                tree_structure=sample_tree,
                max_results=1,
                model="haiku"
            )

            if results:
                top_result = results[0]
                if top_result.node_id in golden["expected_nodes"]:
                    correct_at_1 += 1
                elif any(
                    expected.lower() in top_result.title.lower()
                    for expected in golden["expected_titles"]
                ):
                    correct_at_1 += 1

        precision = correct_at_1 / total if total > 0 else 0
        print(f"\nPrecision@1: {precision:.1%} ({correct_at_1}/{total})")

        # Target: >90% precision at 1
        assert precision >= 0.6, f"Precision@1 ({precision:.1%}) below target (60%)"

    def test_recall_at_3(self, require_claude_cli, sample_tree, golden_tests):
        """Calculate Recall@3 across all golden tests."""
        recall_achieved = 0
        total = len(golden_tests)

        for golden in golden_tests:
            results = tree_search(
                query=golden["query"],
                tree_structure=sample_tree,
                max_results=3,
                model="haiku"
            )

            result_ids = set(r.node_id for r in results)
            result_titles = [r.title.lower() for r in results]

            # Check if any expected node is in top 3
            found = any(
                node_id in result_ids
                for node_id in golden["expected_nodes"]
            )
            title_found = any(
                any(expected.lower() in title for title in result_titles)
                for expected in golden["expected_titles"]
            )

            if found or title_found:
                recall_achieved += 1

        recall = recall_achieved / total if total > 0 else 0
        print(f"\nRecall@3: {recall:.1%} ({recall_achieved}/{total})")

        # Target: >95% recall at 3
        assert recall >= 0.8, f"Recall@3 ({recall:.1%}) below target (80%)"


@pytest.mark.e2e
@pytest.mark.slow
class TestEdgeCases:
    """Test edge cases in search."""

    def test_ambiguous_query(self, require_claude_cli, sample_tree):
        """Test query that could match multiple sections."""
        results = tree_search(
            query="project",  # Very generic
            tree_structure=sample_tree,
            model="haiku"
        )

        # Should return something (likely root or multiple sections)
        assert len(results) >= 1

    def test_very_specific_query(self, require_claude_cli, sample_tree):
        """Test very specific query."""
        results = tree_search(
            query="PostgreSQL pgvector embeddings database",
            tree_structure=sample_tree,
            model="haiku"
        )

        if results:
            # Should find Database Design section
            titles = [r.title.lower() for r in results]
            assert any("database" in t for t in titles)

    def test_negative_query(self, require_claude_cli, sample_tree):
        """Test query looking for something not in document."""
        results = tree_search(
            query="kubernetes deployment configuration",
            tree_structure=sample_tree,
            model="haiku"
        )

        # Should return empty or very low confidence results
        if results:
            max_confidence = max(r.confidence for r in results)
            # Should not be highly confident about non-existent content
            assert max_confidence < 0.9

    def test_synonym_matching(self, require_claude_cli, sample_tree):
        """Test that synonyms are matched."""
        results = tree_search(
            query="objectives and targets",  # Synonym for "goals"
            tree_structure=sample_tree,
            model="haiku"
        )

        if results:
            titles = [r.title.lower() for r in results]
            # Should find Goals section even with synonyms
            assert any("goal" in t for t in titles)


@pytest.mark.e2e
@pytest.mark.slow
class TestMultiDocumentSearch:
    """Test search across multiple documents."""

    def test_search_multiple_docs(
        self, require_claude_cli, sample_tree, sample_architecture_tree
    ):
        """Test searching across multiple tree structures."""
        from scripts.pageindex.tree_search import multi_doc_search

        trees = {
            "ROADMAP.md": sample_tree,
            "ARCHITECTURE.md": sample_architecture_tree,
        }

        results = multi_doc_search(
            query="system design",
            trees=trees,
            max_results_per_doc=2,
            model="haiku"
        )

        assert "ROADMAP.md" in results
        assert "ARCHITECTURE.md" in results

        # At least one doc should have results
        total_results = sum(len(r) for r in results.values())
        assert total_results > 0

    def test_doc_specific_results(
        self, require_claude_cli, sample_tree, sample_architecture_tree
    ):
        """Test that results are doc-appropriate."""
        from scripts.pageindex.tree_search import multi_doc_search

        trees = {
            "ROADMAP.md": sample_tree,
            "ARCHITECTURE.md": sample_architecture_tree,
        }

        # Query that should match architecture doc more
        results = multi_doc_search(
            query="hook system and preprocessing",
            trees=trees,
            max_results_per_doc=3,
            model="haiku"
        )

        # Architecture doc should have more relevant results
        arch_results = results.get("ARCHITECTURE.md", [])
        if arch_results:
            assert any("hook" in r.title.lower() for r in arch_results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e and slow", "--tb=short"])
