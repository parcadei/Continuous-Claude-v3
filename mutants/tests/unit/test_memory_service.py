"""Tests for MemoryService - Core, Archival, Recall memory."""

import pytest
from pathlib import Path


class TestCoreMemory:
    """Phase 1: Core Memory - in-context persistent blocks."""

    @pytest.fixture
    def memory(self, tmp_path):
        from scripts.agentica.memory_service import MemoryService
        return MemoryService(db_path=tmp_path / "memory.db")

    def test_set_and_get_core_block(self, memory):
        """Should store and retrieve core memory blocks."""
        memory.set_core("persona", "You are a helpful assistant")
        assert memory.get_core("persona") == "You are a helpful assistant"

    def test_update_core_block(self, memory):
        """Should update existing core block."""
        memory.set_core("task", "Research Python")
        memory.set_core("task", "Research Rust")
        assert memory.get_core("task") == "Research Rust"

    def test_list_core_blocks(self, memory):
        """Should list all core block keys."""
        memory.set_core("persona", "Assistant")
        memory.set_core("task", "Research")
        keys = memory.list_core_keys()
        assert "persona" in keys
        assert "task" in keys

    def test_delete_core_block(self, memory):
        """Should delete core block."""
        memory.set_core("temp", "value")
        memory.delete_core("temp")
        assert memory.get_core("temp") is None


class TestArchivalMemory:
    """Phase 2: Archival Memory - FTS5 searchable storage."""

    @pytest.fixture
    def memory(self, tmp_path):
        from scripts.agentica.memory_service import MemoryService
        return MemoryService(db_path=tmp_path / "memory.db")

    def test_store_archival_fact(self, memory):
        """Should store fact in archival memory."""
        fact_id = memory.store("Python was created by Guido van Rossum in 1991")
        assert fact_id is not None
        assert fact_id.startswith("mem-")

    def test_search_archival_memory(self, memory):
        """Should search archival memory with FTS5."""
        memory.store("Python was created by Guido van Rossum")
        memory.store("JavaScript was created by Brendan Eich")
        memory.store("Rust was created by Graydon Hoare")

        results = memory.search("Python creator")
        assert len(results) >= 1
        assert "Guido" in results[0]["content"]

    def test_search_returns_ranked_results(self, memory):
        """Should return results ranked by relevance."""
        memory.store("Python is a programming language")
        memory.store("Python snake is a reptile")
        memory.store("Python programming is popular for AI")

        results = memory.search("Python programming AI", limit=2)
        assert len(results) == 2
        # Most relevant should mention AI
        assert "AI" in results[0]["content"]

    def test_delete_archival_fact(self, memory):
        """Should delete fact from archival memory."""
        fact_id = memory.store("Temporary fact")
        memory.delete_archival(fact_id)
        results = memory.search("Temporary fact")
        assert len(results) == 0


class TestRecallMemory:
    """Phase 3: Recall Memory - cross-source query."""

    @pytest.fixture
    def memory(self, tmp_path):
        from scripts.agentica.memory_service import MemoryService
        return MemoryService(db_path=tmp_path / "memory.db")

    def test_recall_from_core(self, memory):
        """Should recall from core memory."""
        memory.set_core("current_task", "Build a web app")
        result = memory.recall("current_task")
        assert "Build a web app" in result

    def test_recall_from_archival(self, memory):
        """Should recall from archival memory."""
        memory.store("The project uses FastAPI for the backend")
        result = memory.recall("What framework is used for backend?")
        assert "FastAPI" in result

    def test_recall_combines_sources(self, memory):
        """Should combine core and archival in recall."""
        memory.set_core("project", "E-commerce platform")
        memory.store("Using PostgreSQL for database")
        memory.store("Using Redis for caching")

        result = memory.recall("project database")
        assert "PostgreSQL" in result or "E-commerce" in result

    def test_to_context_generates_prompt(self, memory):
        """Should generate context string for prompt injection."""
        memory.set_core("persona", "Expert developer")
        memory.store("User prefers TypeScript over JavaScript")

        context = memory.to_context()
        assert "## Core Memory" in context
        assert "Expert developer" in context
