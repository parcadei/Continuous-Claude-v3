"""Integration tests for PageIndex with real PostgreSQL.

These tests require a running PostgreSQL instance.
Run with: pytest -m integration
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.pageindex.pageindex_service import (
    PageIndexService,
    AsyncPageIndexService,
    DocType,
    compute_project_id,
    compute_doc_hash,
)


@pytest.mark.integration
class TestPageIndexServicePostgres:
    """Integration tests using real PostgreSQL connection."""

    @pytest.fixture
    def service(self, require_postgres):
        """Create service instance for each test."""
        svc = PageIndexService()
        yield svc
        svc.close()

    @pytest.fixture
    def test_project_path(self):
        """Use a unique project path for test isolation."""
        return f"/test/project/{datetime.now().timestamp()}"

    def test_store_and_retrieve_tree(self, service, test_project_path, sample_tree):
        """Test storing and retrieving a tree index."""
        result = service.store_tree(
            project_path=test_project_path,
            doc_path="ROADMAP.md",
            tree_structure=sample_tree,
            doc_content="# Test\nContent"
        )

        assert result.id is not None
        assert result.doc_path == "ROADMAP.md"
        assert result.doc_type == DocType.ROADMAP
        assert result.tree_structure["doc_name"] == sample_tree["doc_name"]

        # Retrieve and verify
        retrieved = service.get_tree(test_project_path, "ROADMAP.md")
        assert retrieved is not None
        assert retrieved.doc_path == result.doc_path
        assert retrieved.tree_structure == result.tree_structure

        # Cleanup
        service.delete_tree(test_project_path, "ROADMAP.md")

    def test_store_tree_upsert(self, service, test_project_path, sample_tree):
        """Test that storing twice updates the existing record."""
        # Store first version
        result1 = service.store_tree(
            project_path=test_project_path,
            doc_path="test.md",
            tree_structure={"doc_name": "v1", "structure": []},
            doc_content="Version 1"
        )

        # Store second version
        result2 = service.store_tree(
            project_path=test_project_path,
            doc_path="test.md",
            tree_structure={"doc_name": "v2", "structure": []},
            doc_content="Version 2"
        )

        # Should be same ID (upsert)
        assert result1.id == result2.id
        assert result2.tree_structure["doc_name"] == "v2"

        # Cleanup
        service.delete_tree(test_project_path, "test.md")

    def test_get_nonexistent_tree(self, service, test_project_path):
        """Test getting a tree that doesn't exist."""
        result = service.get_tree(test_project_path, "nonexistent.md")
        assert result is None

    def test_delete_tree(self, service, test_project_path, sample_tree):
        """Test deleting a tree index."""
        # Create
        service.store_tree(
            project_path=test_project_path,
            doc_path="to_delete.md",
            tree_structure=sample_tree
        )

        # Verify exists
        assert service.get_tree(test_project_path, "to_delete.md") is not None

        # Delete
        deleted = service.delete_tree(test_project_path, "to_delete.md")
        assert deleted is True

        # Verify gone
        assert service.get_tree(test_project_path, "to_delete.md") is None

    def test_delete_nonexistent_tree(self, service, test_project_path):
        """Test deleting a tree that doesn't exist."""
        deleted = service.delete_tree(test_project_path, "ghost.md")
        assert deleted is False

    def test_list_trees_by_project(self, service, test_project_path, sample_tree):
        """Test listing trees filtered by project."""
        # Create multiple trees
        service.store_tree(test_project_path, "doc1.md", {"doc_name": "d1", "structure": []})
        service.store_tree(test_project_path, "doc2.md", {"doc_name": "d2", "structure": []})

        trees = service.list_trees(project_path=test_project_path)
        assert len(trees) >= 2

        doc_paths = [t.doc_path for t in trees]
        assert "doc1.md" in doc_paths
        assert "doc2.md" in doc_paths

        # Cleanup
        service.delete_tree(test_project_path, "doc1.md")
        service.delete_tree(test_project_path, "doc2.md")

    def test_list_trees_by_doc_type(self, service, test_project_path):
        """Test listing trees filtered by document type."""
        service.store_tree(test_project_path, "ROADMAP.md", {"structure": []})
        service.store_tree(test_project_path, "ARCHITECTURE.md", {"structure": []})

        roadmaps = service.list_trees(project_path=test_project_path, doc_type=DocType.ROADMAP)
        assert any(t.doc_path == "ROADMAP.md" for t in roadmaps)
        assert not any(t.doc_path == "ARCHITECTURE.md" for t in roadmaps)

        # Cleanup
        service.delete_tree(test_project_path, "ROADMAP.md")
        service.delete_tree(test_project_path, "ARCHITECTURE.md")

    def test_needs_reindex_logic(self, service, test_project_path):
        """Test the needs_reindex detection."""
        content_v1 = "# Test\nVersion 1"
        content_v2 = "# Test\nVersion 2"

        # No existing - needs reindex
        assert service.needs_reindex(test_project_path, "doc.md", content_v1) is True

        # Create
        service.store_tree(
            project_path=test_project_path,
            doc_path="doc.md",
            tree_structure={"structure": []},
            doc_content=content_v1
        )

        # Same content - no reindex needed
        assert service.needs_reindex(test_project_path, "doc.md", content_v1) is False

        # Different content - needs reindex
        assert service.needs_reindex(test_project_path, "doc.md", content_v2) is True

        # Cleanup
        service.delete_tree(test_project_path, "doc.md")

    def test_doc_hash_stored_correctly(self, service, test_project_path):
        """Test that document hash is computed and stored."""
        content = "# Test Document\nWith some content."
        expected_hash = compute_doc_hash(content)

        service.store_tree(
            project_path=test_project_path,
            doc_path="hash_test.md",
            tree_structure={"structure": []},
            doc_content=content
        )

        tree = service.get_tree(test_project_path, "hash_test.md")
        assert tree.doc_hash == expected_hash

        # Cleanup
        service.delete_tree(test_project_path, "hash_test.md")

    def test_get_all_project_trees(self, service, test_project_path):
        """Test getting all trees for a project as a dict."""
        service.store_tree(test_project_path, "a.md", {"structure": []})
        service.store_tree(test_project_path, "b.md", {"structure": []})

        trees_dict = service.get_all_project_trees(test_project_path)

        assert "a.md" in trees_dict
        assert "b.md" in trees_dict
        assert isinstance(trees_dict["a.md"].doc_path, str)

        # Cleanup
        service.delete_tree(test_project_path, "a.md")
        service.delete_tree(test_project_path, "b.md")


@pytest.mark.integration
@pytest.mark.asyncio
class TestAsyncPageIndexService:
    """Integration tests for async service."""

    @pytest.fixture
    async def async_service(self, require_postgres):
        """Create async service instance."""
        try:
            svc = AsyncPageIndexService()
            yield svc
            await svc.close()
        except ImportError:
            pytest.skip("asyncpg not installed")

    @pytest.fixture
    def test_project_path(self):
        return f"/test/async/{datetime.now().timestamp()}"

    async def test_async_store_and_retrieve(self, async_service, test_project_path):
        """Test async store and retrieve operations."""
        tree_structure = {"doc_name": "async_test", "structure": []}

        result = await async_service.store_tree(
            project_path=test_project_path,
            doc_path="async.md",
            tree_structure=tree_structure,
            doc_content="# Async Test"
        )

        assert result.id is not None
        assert result.doc_path == "async.md"

        retrieved = await async_service.get_tree(test_project_path, "async.md")
        assert retrieved is not None
        assert retrieved.tree_structure["doc_name"] == "async_test"


@pytest.mark.integration
class TestConcurrentOperations:
    """Test concurrent database operations."""

    @pytest.fixture
    def service(self, require_postgres):
        svc = PageIndexService()
        yield svc
        svc.close()

    def test_multiple_projects_isolation(self, service):
        """Test that different projects are properly isolated."""
        project_a = f"/test/project_a/{datetime.now().timestamp()}"
        project_b = f"/test/project_b/{datetime.now().timestamp()}"

        service.store_tree(project_a, "doc.md", {"name": "A", "structure": []})
        service.store_tree(project_b, "doc.md", {"name": "B", "structure": []})

        tree_a = service.get_tree(project_a, "doc.md")
        tree_b = service.get_tree(project_b, "doc.md")

        assert tree_a.tree_structure["name"] == "A"
        assert tree_b.tree_structure["name"] == "B"

        # Cleanup
        service.delete_tree(project_a, "doc.md")
        service.delete_tree(project_b, "doc.md")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
