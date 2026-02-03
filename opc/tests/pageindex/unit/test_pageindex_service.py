"""Unit tests for PageIndex service (enhanced from original)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.pageindex.pageindex_service import (
    PageIndexService,
    DocType,
    TreeIndex,
    compute_project_id,
    compute_doc_hash,
    detect_doc_type,
)


@pytest.mark.unit
class TestHelperFunctions:
    def test_compute_project_id_consistent(self):
        path = "/home/user/project"
        id1 = compute_project_id(path)
        id2 = compute_project_id(path)
        assert id1 == id2
        assert len(id1) == 16

    def test_compute_project_id_different_paths(self):
        id1 = compute_project_id("/path/a")
        id2 = compute_project_id("/path/b")
        assert id1 != id2

    def test_compute_project_id_windows_paths(self):
        id1 = compute_project_id("C:\\Users\\test\\project")
        id2 = compute_project_id("C:\\Users\\test\\project")
        assert id1 == id2

    def test_compute_doc_hash(self):
        content = "# Test Document\n\nSome content here."
        hash1 = compute_doc_hash(content)
        hash2 = compute_doc_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_compute_doc_hash_different_content(self):
        hash1 = compute_doc_hash("content a")
        hash2 = compute_doc_hash("content b")
        assert hash1 != hash2

    def test_compute_doc_hash_whitespace_sensitive(self):
        hash1 = compute_doc_hash("content")
        hash2 = compute_doc_hash("content ")
        assert hash1 != hash2

    def test_detect_doc_type_roadmap(self):
        assert detect_doc_type("ROADMAP.md") == DocType.ROADMAP
        assert detect_doc_type("docs/ROADMAP.md") == DocType.ROADMAP
        assert detect_doc_type("project-roadmap.md") == DocType.ROADMAP

    def test_detect_doc_type_architecture(self):
        assert detect_doc_type("ARCHITECTURE.md") == DocType.ARCHITECTURE
        assert detect_doc_type("docs/architecture.md") == DocType.ARCHITECTURE
        assert detect_doc_type("system-architecture.md") == DocType.ARCHITECTURE

    def test_detect_doc_type_readme(self):
        assert detect_doc_type("README.md") == DocType.README
        assert detect_doc_type("readme.md") == DocType.README
        assert detect_doc_type("Readme.md") == DocType.README

    def test_detect_doc_type_documentation(self):
        assert detect_doc_type("docs/guide.md") == DocType.DOCUMENTATION
        assert detect_doc_type("USER_GUIDE.md") == DocType.DOCUMENTATION
        assert detect_doc_type("API_REFERENCE.md") == DocType.DOCUMENTATION
        assert detect_doc_type("docs/MANUAL.md") == DocType.DOCUMENTATION

    def test_detect_doc_type_other(self):
        assert detect_doc_type("random.md") == DocType.OTHER
        assert detect_doc_type("notes.md") == DocType.OTHER
        assert detect_doc_type("changelog.md") == DocType.OTHER


@pytest.mark.unit
class TestTreeIndex:
    def test_tree_index_default_values(self):
        index = TreeIndex()
        assert index.id is None
        assert index.project_id == ""
        assert index.doc_path == ""
        assert index.doc_type == DocType.OTHER
        assert index.tree_structure == {}

    def test_tree_index_with_values(self):
        index = TreeIndex(
            id="test-id",
            project_id="proj123",
            doc_path="ROADMAP.md",
            doc_type=DocType.ROADMAP,
            tree_structure={"doc_name": "test", "structure": []},
        )
        assert index.id == "test-id"
        assert index.project_id == "proj123"
        assert index.doc_type == DocType.ROADMAP
        assert index.tree_structure["doc_name"] == "test"

    def test_tree_index_timestamps(self):
        from datetime import datetime
        now = datetime.now()
        index = TreeIndex(
            created_at=now,
            updated_at=now
        )
        assert index.created_at == now
        assert index.updated_at == now


@pytest.mark.unit
class TestPageIndexService:
    @pytest.fixture
    def mock_conn(self):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=None)
        cursor.fetchone.return_value = {
            "id": "test-uuid",
            "project_id": "proj123",
            "doc_path": "ROADMAP.md",
            "doc_type": "ROADMAP",
            "tree_structure": {"doc_name": "test"},
            "doc_hash": "abc123",
            "created_at": None,
            "updated_at": None,
        }
        conn.cursor.return_value = cursor
        return conn

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_store_tree(self, mock_psycopg2, mock_conn):
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.store_tree(
            project_path="/home/user/project",
            doc_path="ROADMAP.md",
            tree_structure={"doc_name": "test", "structure": []},
            doc_content="# Roadmap\n\nContent",
        )

        assert result.doc_path == "ROADMAP.md"
        assert result.doc_type == DocType.ROADMAP

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_store_tree_auto_detects_type(self, mock_psycopg2, mock_conn):
        mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = {
            "id": "test-uuid",
            "project_id": "proj123",
            "doc_path": "docs/ARCHITECTURE.md",
            "doc_type": "ARCHITECTURE",
            "tree_structure": {},
            "doc_hash": "abc",
            "created_at": None,
            "updated_at": None,
        }
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.store_tree(
            project_path="/project",
            doc_path="docs/ARCHITECTURE.md",
            tree_structure={},
        )

        assert result.doc_type == DocType.ARCHITECTURE

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_get_tree_found(self, mock_psycopg2, mock_conn):
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.get_tree("/home/user/project", "ROADMAP.md")

        assert result is not None
        assert result.doc_path == "ROADMAP.md"

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_get_tree_not_found(self, mock_psycopg2, mock_conn):
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.get_tree("/home/user/project", "nonexistent.md")

        assert result is None

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_needs_reindex_no_existing(self, mock_psycopg2, mock_conn):
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.needs_reindex("/project", "doc.md", "content")

        assert result is True

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_needs_reindex_unchanged(self, mock_psycopg2, mock_conn):
        content = "# Test"
        expected_hash = compute_doc_hash(content)
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            "id": "test-uuid",
            "project_id": "proj123",
            "doc_path": "doc.md",
            "doc_type": "OTHER",
            "tree_structure": {},
            "doc_hash": expected_hash,
            "created_at": None,
            "updated_at": None,
        }
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.needs_reindex("/project", "doc.md", content)

        assert result is False

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_needs_reindex_changed(self, mock_psycopg2, mock_conn):
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            "id": "test-uuid",
            "project_id": "proj123",
            "doc_path": "doc.md",
            "doc_type": "OTHER",
            "tree_structure": {},
            "doc_hash": "old_hash",
            "created_at": None,
            "updated_at": None,
        }
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.needs_reindex("/project", "doc.md", "new content")

        assert result is True

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_list_trees_all(self, mock_psycopg2, mock_conn):
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            {
                "id": "1",
                "project_id": "proj1",
                "doc_path": "ROADMAP.md",
                "doc_type": "ROADMAP",
                "doc_hash": "abc",
                "created_at": None,
                "updated_at": None,
                "node_count": 5
            },
            {
                "id": "2",
                "project_id": "proj1",
                "doc_path": "README.md",
                "doc_type": "README",
                "doc_hash": "def",
                "created_at": None,
                "updated_at": None,
                "node_count": 3
            }
        ]
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.list_trees(project_path="/project")

        assert len(result) == 2
        assert result[0].doc_path == "ROADMAP.md"
        assert result[1].doc_path == "README.md"

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_delete_tree_success(self, mock_psycopg2, mock_conn):
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("deleted-id",)
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.delete_tree("/project", "doc.md")

        assert result is True

    @patch("scripts.pageindex.pageindex_service.psycopg2")
    def test_delete_tree_not_found(self, mock_psycopg2, mock_conn):
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        mock_psycopg2.connect.return_value = mock_conn

        service = PageIndexService()
        result = service.delete_tree("/project", "nonexistent.md")

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
