"""End-to-end integration test for v3 components.

Tests that Memory Service, BeadsTaskGraph, SessionTree, and Agent Scope
all work together correctly.
"""

import pytest
from pathlib import Path


class TestV3Integration:
    """Integration tests for v3 components."""

    @pytest.fixture
    def db_path(self, tmp_path):
        return tmp_path / "integration.db"

    def test_memory_and_tasks_share_session(self, db_path):
        """Memory and tasks should share session isolation."""
        from scripts.agentica.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="integration", db_path=db_path)

        # Store memory
        scope["remember"]("project", "E-commerce platform")
        scope["store_fact"]("Using PostgreSQL for database")

        # Create tasks
        task1 = scope["create_task"]("Design schema")
        task2 = scope["create_task"]("Implement API", blocks=[task1])

        # Verify state
        assert "E-commerce" in scope["recall"]("project")
        ready = scope["get_ready_tasks"]()
        assert task1 in ready
        assert task2 not in ready

        # Complete task1, task2 becomes ready
        scope["complete_task"](task1)
        ready = scope["get_ready_tasks"]()
        assert task2 in ready

    def test_session_tree_branches_work(self, db_path):
        """Session tree branching should work correctly."""
        from scripts.agentica.session_tree import SessionTree

        tree = SessionTree(session_id="integration", db_path=db_path)

        # Add messages to main
        tree.add_message("user", "Let's try approach A")
        tree.add_message("assistant", "Starting approach A")

        # Fork to experiment
        tree.fork("experiment", "Trying approach B")
        tree.add_message("user", "Actually, let's try approach B")

        # Verify isolation
        exp_messages = tree.get_branch_messages()
        assert len(exp_messages) == 3  # 2 from main + 1 from experiment

        tree.switch("main")
        main_messages = tree.get_branch_messages()
        assert len(main_messages) == 2  # Only main messages

    def test_full_workflow_simulation(self, db_path):
        """Simulate a full agent workflow with all components."""
        from scripts.agentica.agent_scope import create_agent_scope
        from scripts.agentica.session_tree import SessionTree

        session_id = "workflow"

        # Create agent scope
        scope = create_agent_scope(session_id=session_id, db_path=db_path)

        # Create session tree
        tree = SessionTree(session_id=session_id, db_path=db_path)

        # Simulate workflow
        tree.add_message("user", "Build a REST API")

        # Agent stores context
        scope["remember"]("task", "Build REST API")
        scope["store_fact"]("User wants FastAPI framework")

        # Agent creates tasks
        research = scope["create_task"]("Research FastAPI patterns")
        design = scope["create_task"]("Design endpoints", blocks=[research])
        implement = scope["create_task"]("Implement API", blocks=[design])

        # Verify workflow state
        ready = scope["get_ready_tasks"]()
        assert research in ready
        assert design not in ready
        assert implement not in ready

        # Complete research, fork to try different approach
        scope["complete_task"](research)
        tree.fork("flask-approach", "Trying Flask instead")

        # Store Flask-specific memory
        scope["store_fact"]("Switched to Flask framework")

        # Verify state
        assert design in scope["get_ready_tasks"]()
        assert tree.current_branch_name == "flask-approach"
