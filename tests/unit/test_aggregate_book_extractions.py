"""
Tests for aggregate_book_extractions.py

Test suite for aggregating book extraction JSON files into a unified searchable index.
These tests are written TDD-style - they should FAIL until the implementation exists.

Book JSON structure:
{
    "book_id": "uuid",
    "book_name": "Book Title",
    "topics": {
        "category/topic": [
            {"score": 0.85, "text": "extracted text..."}
        ]
    }
}
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

# This import should fail until implementation exists
# TDD: Tests should FAIL, not skip, when module doesn't exist
from scripts.aggregate_book_extractions import (
    load_book_json,
    aggregate_multiple_books,
    build_topic_index,
    cross_reference_topics,
    export_unified_index,
    main,
)


# Sample test data matching actual book JSON structure
SAMPLE_BOOK_1 = {
    "book_id": "06bf70b1-c44d-4bbc-a553-37031f70f36f",
    "book_name": "Linear Algebra (Hoffman-Kunze)",
    "topics": {
        "linear-algebra/matrices and determinants": [
            {"score": 0.1588, "text": "The study of matrices and determinants..."},
            {"score": 0.1435, "text": "Determinant properties..."},
        ],
        "linear-algebra/eigenvalues and eigenvectors": [
            {"score": 0.1833, "text": "Eigenvalue decomposition..."},
        ],
        "linear-algebra/vector spaces and subspaces": [
            {"score": 0.1497, "text": "Vector space axioms..."},
        ],
    },
}

SAMPLE_BOOK_2 = {
    "book_id": "3905d541-abcd-1234-5678-123456789abc",
    "book_name": "Abstract Algebra (Dummit-Foote)",
    "topics": {
        "algebra/group theory": [
            {"score": 0.2100, "text": "Group axioms and properties..."},
        ],
        "algebra/ring theory": [
            {"score": 0.1900, "text": "Ring homomorphisms..."},
        ],
        "linear-algebra/vector spaces and subspaces": [
            {"score": 0.1200, "text": "Module theory extends vector spaces..."},
        ],
    },
}

SAMPLE_BOOK_3 = {
    "book_id": "44cc81de-efgh-5678-9012-abcdef012345",
    "book_name": "Real Analysis (Rudin)",
    "topics": {
        "analysis/sequences and series": [
            {"score": 0.1750, "text": "Convergence of sequences..."},
        ],
        "linear-algebra/eigenvalues and eigenvectors": [
            {"score": 0.0900, "text": "Spectral theory in Hilbert spaces..."},
        ],
    },
}


@pytest.fixture
def temp_books_dir():
    """Create temporary directory with sample book JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        books_dir = Path(tmpdir) / "books"
        books_dir.mkdir()

        # Write sample books
        for i, book in enumerate([SAMPLE_BOOK_1, SAMPLE_BOOK_2, SAMPLE_BOOK_3]):
            book_file = books_dir / f"{book['book_id'][:8]}.json"
            book_file.write_text(json.dumps(book, indent=2))

        yield books_dir


@pytest.fixture
def single_book_file(temp_books_dir):
    """Return path to first book file."""
    return temp_books_dir / "06bf70b1.json"


class TestLoadBookJson:
    """Tests for loading a single book JSON file."""

    def test_load_book_json_returns_dict(self, single_book_file):
        """load_book_json should return a dictionary."""
        result = load_book_json(single_book_file)
        assert isinstance(result, dict)

    def test_load_book_json_has_required_keys(self, single_book_file):
        """Loaded book should have book_id, book_name, and topics."""
        result = load_book_json(single_book_file)
        assert "book_id" in result
        assert "book_name" in result
        assert "topics" in result

    def test_load_book_json_topics_structure(self, single_book_file):
        """Topics should be dict mapping topic names to lists of extractions."""
        result = load_book_json(single_book_file)
        topics = result["topics"]

        assert isinstance(topics, dict)
        for topic_name, extractions in topics.items():
            assert isinstance(topic_name, str)
            assert isinstance(extractions, list)
            for extraction in extractions:
                assert "score" in extraction
                assert "text" in extraction

    def test_load_book_json_nonexistent_file_raises(self, temp_books_dir):
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            load_book_json(temp_books_dir / "nonexistent.json")

    def test_load_book_json_invalid_json_raises(self, temp_books_dir):
        """Should raise JSONDecodeError for invalid JSON."""
        bad_file = temp_books_dir / "bad.json"
        bad_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            load_book_json(bad_file)


class TestAggregateMultipleBooks:
    """Tests for aggregating multiple book files."""

    def test_aggregate_returns_list(self, temp_books_dir):
        """aggregate_multiple_books should return list of book dicts."""
        result = aggregate_multiple_books(temp_books_dir)
        assert isinstance(result, list)

    def test_aggregate_loads_all_books(self, temp_books_dir):
        """Should load all JSON files in directory."""
        result = aggregate_multiple_books(temp_books_dir)
        assert len(result) == 3

    def test_aggregate_each_book_has_metadata(self, temp_books_dir):
        """Each aggregated book should have id and name."""
        result = aggregate_multiple_books(temp_books_dir)
        for book in result:
            assert "book_id" in book
            assert "book_name" in book

    def test_aggregate_preserves_all_topics(self, temp_books_dir):
        """Aggregation should preserve all topics from all books."""
        result = aggregate_multiple_books(temp_books_dir)
        all_topic_counts = sum(len(book["topics"]) for book in result)
        # Book 1: 3 topics, Book 2: 3 topics, Book 3: 2 topics = 8 total
        assert all_topic_counts == 8

    def test_aggregate_empty_directory(self, temp_books_dir):
        """Should return empty list for directory with no JSON files."""
        empty_dir = temp_books_dir.parent / "empty"
        empty_dir.mkdir()
        result = aggregate_multiple_books(empty_dir)
        assert result == []

    def test_aggregate_skips_non_json_files(self, temp_books_dir):
        """Should only process .json files."""
        # Add a non-JSON file
        (temp_books_dir / "readme.txt").write_text("ignore me")
        result = aggregate_multiple_books(temp_books_dir)
        assert len(result) == 3  # Still only 3 books


class TestTopicIndexStructure:
    """Tests for building unified topic index."""

    def test_build_topic_index_returns_dict(self, temp_books_dir):
        """build_topic_index should return a dictionary."""
        books = aggregate_multiple_books(temp_books_dir)
        result = build_topic_index(books)
        assert isinstance(result, dict)

    def test_topic_index_keys_are_topics(self, temp_books_dir):
        """Index keys should be topic names (category/topic format)."""
        books = aggregate_multiple_books(temp_books_dir)
        result = build_topic_index(books)

        for key in result.keys():
            assert "/" in key  # category/topic format
            assert isinstance(key, str)

    def test_topic_index_values_contain_book_refs(self, temp_books_dir):
        """Each topic should map to list of book references."""
        books = aggregate_multiple_books(temp_books_dir)
        result = build_topic_index(books)

        for topic, book_refs in result.items():
            assert isinstance(book_refs, list)
            for ref in book_refs:
                assert "book_id" in ref
                assert "book_name" in ref
                assert "extractions" in ref

    def test_topic_index_includes_extractions(self, temp_books_dir):
        """Book references should include the actual extractions."""
        books = aggregate_multiple_books(temp_books_dir)
        result = build_topic_index(books)

        # Check a topic that exists in sample data
        topic = "linear-algebra/matrices and determinants"
        if topic in result:
            for ref in result[topic]:
                assert isinstance(ref["extractions"], list)
                for ext in ref["extractions"]:
                    assert "score" in ext
                    assert "text" in ext

    def test_topic_index_merges_same_topics(self, temp_books_dir):
        """Same topic from different books should be merged."""
        books = aggregate_multiple_books(temp_books_dir)
        result = build_topic_index(books)

        # "linear-algebra/vector spaces and subspaces" appears in books 1 and 2
        topic = "linear-algebra/vector spaces and subspaces"
        assert topic in result
        assert len(result[topic]) >= 2  # At least 2 books cover this topic


class TestCrossReferenceTopics:
    """Tests for finding books covering the same topic."""

    def test_cross_reference_returns_dict(self, temp_books_dir):
        """cross_reference_topics should return a dictionary."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)
        result = cross_reference_topics(topic_index)
        assert isinstance(result, dict)

    def test_cross_reference_finds_shared_topics(self, temp_books_dir):
        """Should identify topics covered by multiple books."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)
        result = cross_reference_topics(topic_index)

        # At least one topic should be shared
        shared_topics = [t for t, refs in result.items() if len(refs) > 1]
        assert len(shared_topics) > 0

    def test_cross_reference_includes_book_names(self, temp_books_dir):
        """Cross-reference should include human-readable book names."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)
        result = cross_reference_topics(topic_index)

        for topic, refs in result.items():
            for ref in refs:
                assert "book_name" in ref

    def test_cross_reference_eigenvalues_topic(self, temp_books_dir):
        """Eigenvalues topic should appear in multiple books."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)
        result = cross_reference_topics(topic_index)

        eigenvalues_topic = "linear-algebra/eigenvalues and eigenvectors"
        assert eigenvalues_topic in result
        # Books 1 and 3 both cover eigenvalues
        book_names = [ref["book_name"] for ref in result[eigenvalues_topic]]
        assert len(book_names) >= 2

    def test_cross_reference_includes_scores(self, temp_books_dir):
        """Cross-reference should include best score per book for ranking."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)
        result = cross_reference_topics(topic_index)

        for topic, refs in result.items():
            for ref in refs:
                # Should have max_score or similar for ranking
                assert "max_score" in ref or "best_score" in ref or "score" in ref


class TestExportUnifiedIndex:
    """Tests for exporting the aggregated index."""

    def test_export_creates_file(self, temp_books_dir):
        """export_unified_index should create output file."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)

        output_path = temp_books_dir.parent / "unified_index.json"
        export_unified_index(topic_index, output_path)

        assert output_path.exists()

    def test_export_creates_valid_json(self, temp_books_dir):
        """Exported file should be valid JSON."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)

        output_path = temp_books_dir.parent / "unified_index.json"
        export_unified_index(topic_index, output_path)

        # Should not raise
        data = json.loads(output_path.read_text())
        assert isinstance(data, dict)

    def test_export_includes_metadata(self, temp_books_dir):
        """Exported index should include metadata."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)

        output_path = temp_books_dir.parent / "unified_index.json"
        export_unified_index(topic_index, output_path)

        data = json.loads(output_path.read_text())
        assert "metadata" in data or "topics" in data

    def test_export_includes_all_topics(self, temp_books_dir):
        """Exported index should include all topics."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)

        output_path = temp_books_dir.parent / "unified_index.json"
        export_unified_index(topic_index, output_path)

        data = json.loads(output_path.read_text())
        # Topics should be preserved
        topics_key = "topics" if "topics" in data else "index"
        assert len(data.get(topics_key, data)) > 0

    def test_export_dry_run_does_not_write(self, temp_books_dir):
        """Dry run should not create file."""
        books = aggregate_multiple_books(temp_books_dir)
        topic_index = build_topic_index(books)

        output_path = temp_books_dir.parent / "dry_run_index.json"
        export_unified_index(topic_index, output_path, dry_run=True)

        assert not output_path.exists()


class TestCLIDryRun:
    """Tests for CLI with --dry-run flag."""

    def test_cli_dry_run_no_output_file(self, temp_books_dir):
        """CLI --dry-run should not create output file."""
        import sys

        output_path = temp_books_dir.parent / "cli_output.json"

        # Simulate CLI args
        test_args = [
            "aggregate_book_extractions.py",
            "--input-dir", str(temp_books_dir),
            "--output", str(output_path),
            "--dry-run",
        ]

        with patch.object(sys, 'argv', test_args):
            main()

        assert not output_path.exists()

    def test_cli_dry_run_prints_summary(self, temp_books_dir, capsys):
        """CLI --dry-run should print summary of what would be done."""
        import sys

        output_path = temp_books_dir.parent / "cli_output.json"

        test_args = [
            "aggregate_book_extractions.py",
            "--input-dir", str(temp_books_dir),
            "--output", str(output_path),
            "--dry-run",
        ]

        with patch.object(sys, 'argv', test_args):
            main()

        captured = capsys.readouterr()
        # Should print some summary info
        assert "books" in captured.out.lower() or "topics" in captured.out.lower()

    def test_cli_without_dry_run_creates_file(self, temp_books_dir):
        """CLI without --dry-run should create output file."""
        import sys

        output_path = temp_books_dir.parent / "cli_output.json"

        test_args = [
            "aggregate_book_extractions.py",
            "--input-dir", str(temp_books_dir),
            "--output", str(output_path),
        ]

        with patch.object(sys, 'argv', test_args):
            main()

        assert output_path.exists()

    def test_cli_default_input_dir(self, temp_books_dir, monkeypatch):
        """CLI should use default input dir if not specified."""
        import sys

        # Change to temp directory
        monkeypatch.chdir(temp_books_dir.parent)

        output_path = temp_books_dir.parent / "default_output.json"

        test_args = [
            "aggregate_book_extractions.py",
            "--output", str(output_path),
            "--dry-run",
        ]

        with patch.object(sys, 'argv', test_args):
            # Should not raise even without --input-dir
            try:
                main()
            except SystemExit as e:
                # Acceptable if it exits cleanly
                pass

    def test_cli_help_flag(self, capsys):
        """CLI --help should show usage."""
        import sys

        test_args = ["aggregate_book_extractions.py", "--help"]

        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Help exits with code 0
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "--dry-run" in captured.out or "--help" in captured.out


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_pipeline(self, temp_books_dir):
        """Test complete aggregation pipeline."""
        # Load books
        books = aggregate_multiple_books(temp_books_dir)
        assert len(books) == 3

        # Build index
        topic_index = build_topic_index(books)
        assert len(topic_index) > 0

        # Cross-reference
        cross_refs = cross_reference_topics(topic_index)
        assert len(cross_refs) > 0

        # Export
        output_path = temp_books_dir.parent / "full_pipeline.json"
        export_unified_index(topic_index, output_path)
        assert output_path.exists()

        # Verify output
        data = json.loads(output_path.read_text())
        assert isinstance(data, dict)

    def test_real_books_directory(self):
        """Test with actual books directory if it exists."""
        real_books_dir = Path("thoughts/shared/books")

        if not real_books_dir.exists():
            pytest.skip("Real books directory not found")

        books = aggregate_multiple_books(real_books_dir)

        # Should load at least some books
        assert len(books) > 0

        # Each book should have valid structure
        for book in books:
            assert "book_id" in book
            assert "book_name" in book
            assert "topics" in book
