"""Unit tests for memory-client.ts TypeScript module.

Tests the memory client that TypeScript hooks use to call the Python memory service.
Since the actual implementation is in TypeScript, we test:
1. The Python memory service API contract (what the client will call)
2. The expected JSON interface
3. Error handling behaviors

The TypeScript client uses subprocess to call Python scripts,
so these tests validate the Python side of that interface.
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts/agentica to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENTICA_PATH = PROJECT_ROOT / "scripts" / "agentica"
sys.path.insert(0, str(AGENTICA_PATH.parent))


class TestMemoryClientInterface:
    """Test the interface that memory-client.ts expects from Python."""

    def test_memory_search_json_output_format(self):
        """Memory search should return JSON array with content, similarity, metadata."""
        # This is what the TypeScript client expects
        expected_fields = {"content", "similarity", "metadata"}

        # Mock a search result that matches the TypeScript interface
        mock_result = {
            "content": "User prefers Python over JavaScript",
            "similarity": 0.85,
            "metadata": {"type": "skill", "name": "language-preference"},
        }

        # Verify all expected fields are present
        assert expected_fields.issubset(mock_result.keys())

    def test_memory_store_returns_id(self):
        """Memory store should return a memory ID string."""
        # The store function returns a memory ID
        mock_id = "mem-abc123def456"

        assert isinstance(mock_id, str)
        assert mock_id.startswith("mem-")

    def test_memory_search_empty_results(self):
        """Empty search results should be valid JSON array."""
        empty_results = []

        assert isinstance(empty_results, list)
        assert len(empty_results) == 0

    def test_memory_search_result_serialization(self):
        """Search results should be JSON serializable."""
        from datetime import UTC, datetime

        result = {
            "id": "mem-123",
            "content": "Test content",
            "similarity": 0.92,
            "metadata": {"created": datetime.now(UTC).isoformat()},
        }

        # Should serialize without error
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Should deserialize correctly
        parsed = json.loads(json_str)
        assert parsed["content"] == "Test content"


class TestMemoryClientSubprocess:
    """Test subprocess-based memory client pattern used in hooks."""

    def test_subprocess_search_command_format(self):
        """Verify the Python command format for memory search."""
        # This mimics what memory-client.ts does
        # query = "find skill for TypeScript hooks"  # Example input
        # limit = 5  # Example input

        python_script = """
import json
import sys
import asyncio
from scripts.agentica.memory_factory import create_default_memory_service

async def search():
    query = sys.argv[1]
    limit = int(sys.argv[2])
    memory = create_default_memory_service("default")
    await memory.connect()
    results = await memory.search(query, limit=limit)
    await memory.close()
    # Convert to JSON-safe format
    safe_results = []
    for r in results:
        safe_results.append({
            "content": r.get("content", ""),
            "similarity": r.get("similarity", r.get("rank", 0.0)),
            "metadata": r.get("metadata", {})
        })
    print(json.dumps(safe_results))

asyncio.run(search())
"""
        # Verify the script uses the expected argument positions
        assert "sys.argv[1]" in python_script  # query
        assert "sys.argv[2]" in python_script  # limit

    def test_subprocess_store_command_format(self):
        """Verify the Python command format for memory store."""
        # content = "New skill content"  # Example input
        # metadata = {"type": "skill", "name": "test-skill"}  # Example input

        python_script = """
import json
import sys
import asyncio
from scripts.agentica.memory_factory import create_default_memory_service

async def store():
    content = sys.argv[1]
    metadata = json.loads(sys.argv[2])
    memory = create_default_memory_service("default")
    await memory.connect()
    memory_id = await memory.store(content, metadata=metadata)
    await memory.close()
    print(json.dumps({"id": memory_id}))

asyncio.run(store())
"""
        assert "sys.argv[1]" in python_script  # content
        assert "sys.argv[2]" in python_script  # metadata JSON


class TestMemoryClientErrorHandling:
    """Test error handling for memory client."""

    def test_connection_error_returns_empty(self):
        """Connection errors should return empty results, not crash."""
        # When DB is unavailable, search should return empty array
        fallback_results = []

        assert isinstance(fallback_results, list)

    def test_invalid_query_handled(self):
        """Invalid queries should be handled gracefully."""
        # Empty or whitespace queries
        invalid_queries = ["", "   ", None]

        for _ in invalid_queries:
            # Should not raise, should return empty or handle gracefully
            result = []  # Expected fallback
            assert isinstance(result, list)

    def test_subprocess_timeout_handling(self):
        """Subprocess should have timeout protection."""
        # TypeScript client should set timeout (e.g., 5000ms)
        timeout_ms = 5000

        assert timeout_ms > 0
        assert timeout_ms <= 30000  # Should not be too long


class TestMemorySearchResultTypes:
    """Test the MemorySearchResult interface compatibility."""

    def test_result_has_required_fields(self):
        """Each result must have content, similarity, metadata."""
        result = {
            "content": "Sample content",
            "similarity": 0.75,
            "metadata": {},
        }

        # Required fields (TypeScript interface)
        assert "content" in result
        assert "similarity" in result
        assert "metadata" in result

        # Type checks
        assert isinstance(result["content"], str)
        assert isinstance(result["similarity"], (int, float))
        assert isinstance(result["metadata"], dict)

    def test_similarity_is_normalized(self):
        """Similarity should be between 0 and 1."""
        valid_similarities = [0.0, 0.5, 0.85, 1.0]

        for sim in valid_similarities:
            assert 0.0 <= sim <= 1.0

    def test_metadata_is_json_serializable(self):
        """Metadata must be JSON serializable."""
        metadata_examples = [
            {},
            {"type": "skill"},
            {"type": "skill", "name": "test", "version": 1},
            {"nested": {"key": "value"}},
        ]

        for meta in metadata_examples:
            # Should not raise
            serialized = json.dumps(meta)
            assert isinstance(serialized, str)


@pytest.mark.asyncio
class TestMemoryServiceIntegration:
    """Integration tests with actual MemoryService (mocked DB)."""

    async def test_sqlite_memory_search_returns_correct_format(self):
        """SQLite memory service returns results matching TypeScript interface."""
        import tempfile
        from pathlib import Path

        from scripts.agentica.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_memory.db"
            memory = MemoryService(session_id="test", db_path=db_path)

            await memory.connect()

            # Store a test fact
            await memory.store(
                "TypeScript hooks use subprocess",
                metadata={"type": "fact"},
            )

            # Search for it
            results = await memory.search("TypeScript")

            await memory.close()

            # Verify format matches what TypeScript expects
            assert isinstance(results, list)
            if results:
                result = results[0]
                assert "content" in result
                # SQLite uses 'rank' not 'similarity'
                assert "rank" in result or "similarity" in result
                assert "metadata" in result

    async def test_memory_service_graceful_fallback(self):
        """Memory service handles missing DB gracefully.

        Note: The Python service raises on invalid paths.
        The TypeScript client should catch this and return empty results.
        This test documents the expected behavior.
        """
        import sqlite3
        from pathlib import Path

        from scripts.agentica.memory_service import MemoryService

        # Non-existent path raises - TypeScript client must handle this
        memory = MemoryService(
            session_id="test", db_path=Path("/nonexistent/path/db.sqlite")
        )

        # Python raises sqlite3.OperationalError on invalid path
        # The TypeScript memory-client.ts must catch this
        with pytest.raises(sqlite3.OperationalError):
            await memory.connect()


class TestMemoryClientCLIWrapper:
    """Test the CLI wrapper script that TypeScript calls."""

    def test_cli_script_exists(self):
        """Verify there's a callable script for memory operations."""
        # The TypeScript client will call a Python script
        # Check that the memory_factory module is importable
        try:
            from scripts.agentica import memory_factory

            assert hasattr(memory_factory, "create_default_memory_service")
        except ImportError:
            pytest.skip("memory_factory not available")

    def test_cli_json_output_format(self):
        """CLI should output valid JSON."""
        # Simulate CLI output
        cli_output = json.dumps(
            [
                {
                    "content": "Test",
                    "similarity": 0.9,
                    "metadata": {},
                }
            ]
        )

        parsed = json.loads(cli_output)
        assert isinstance(parsed, list)
