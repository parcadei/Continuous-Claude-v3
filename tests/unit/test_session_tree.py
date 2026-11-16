"""Tests for SessionTree - tree-based session branching."""

import pytest
from pathlib import Path


class TestSessionTreeBasics:
    """Basic SessionTree operations."""

    @pytest.fixture
    def tree(self, tmp_path):
        from scripts.agentica_patterns.session_tree import SessionTree
        return SessionTree(session_id="test", db_path=tmp_path / "session.db")

    def test_main_branch_created_automatically(self, tree):
        """Main branch should be created on init."""
        branches = tree.list_branches()
        assert len(branches) == 1
        assert branches[0].name == "main"
        assert branches[0].is_active

    def test_current_branch_name(self, tree):
        """Should return current branch name."""
        assert tree.current_branch_name == "main"

    def test_current_branch_id_format(self, tree):
        """Branch ID should have correct format."""
        assert tree.current_branch_id.startswith("se-")


class TestMessageOperations:
    """Message add/retrieve operations."""

    @pytest.fixture
    def tree(self, tmp_path):
        from scripts.agentica_patterns.session_tree import SessionTree
        return SessionTree(session_id="test", db_path=tmp_path / "session.db")

    def test_add_message_returns_id(self, tree):
        """Adding message should return entry ID."""
        msg_id = tree.add_message("user", "Hello")
        assert msg_id.startswith("se-")

    def test_add_and_get_messages(self, tree):
        """Should add and retrieve messages."""
        tree.add_message("user", "Hello")
        tree.add_message("assistant", "Hi there!")

        messages = tree.get_branch_messages()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Hi there!"

    def test_message_count(self, tree):
        """Should count messages in branch."""
        tree.add_message("user", "One")
        tree.add_message("assistant", "Two")
        tree.add_message("user", "Three")

        assert tree.get_message_count() == 3


class TestBranchOperations:
    """Fork, switch, and branch management."""

    @pytest.fixture
    def tree(self, tmp_path):
        from scripts.agentica_patterns.session_tree import SessionTree
        return SessionTree(session_id="test", db_path=tmp_path / "session.db")

    def test_fork_creates_new_branch(self, tree):
        """Fork should create a new branch."""
        tree.add_message("user", "Original message")
        branch_id = tree.fork("experiment", "Testing something")

        branches = tree.list_branches()
        assert len(branches) == 2
        assert any(b.name == "experiment" for b in branches)

    def test_fork_switches_to_new_branch(self, tree):
        """Fork should switch to the new branch."""
        tree.add_message("user", "Before fork")
        tree.fork("experiment", "Testing")

        assert tree.current_branch_name == "experiment"

    def test_switch_by_name(self, tree):
        """Should switch branch by name."""
        tree.fork("experiment", "Testing")
        tree.switch("main")
        assert tree.current_branch_name == "main"

        tree.switch("experiment")
        assert tree.current_branch_name == "experiment"

    def test_switch_by_id(self, tree):
        """Should switch branch by ID."""
        branch_id = tree.fork("experiment", "Testing")
        tree.switch("main")
        tree.switch(branch_id)
        assert tree.current_branch_name == "experiment"

    def test_switch_invalid_raises(self, tree):
        """Switching to invalid branch should raise."""
        with pytest.raises(ValueError, match="not found"):
            tree.switch("nonexistent")


class TestBranchIsolation:
    """Branch message isolation."""

    @pytest.fixture
    def tree(self, tmp_path):
        from scripts.agentica_patterns.session_tree import SessionTree
        return SessionTree(session_id="test", db_path=tmp_path / "session.db")

    def test_branch_includes_parent_messages(self, tree):
        """Branch messages should include parent messages."""
        tree.add_message("user", "Message 1")
        tree.add_message("assistant", "Message 2")

        tree.fork("experiment", "Testing")
        tree.add_message("user", "Message 3 (on branch)")

        messages = tree.get_branch_messages()
        assert len(messages) == 3
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Message 2"
        assert messages[2].content == "Message 3 (on branch)"

    def test_main_unaffected_by_fork(self, tree):
        """Main branch should not see fork messages."""
        tree.add_message("user", "On main")
        tree.fork("experiment", "Testing")
        tree.add_message("user", "On experiment only")

        tree.switch("main")
        messages = tree.get_branch_messages()
        assert len(messages) == 1
        assert messages[0].content == "On main"

    def test_parallel_branches_isolated(self, tree):
        """Parallel branches should be isolated."""
        tree.add_message("user", "Common base")

        # Create branch A
        tree.fork("branch-a", "First approach")
        tree.add_message("user", "Only in A")

        # Go back to main and create branch B
        tree.switch("main")
        tree.fork("branch-b", "Second approach")
        tree.add_message("user", "Only in B")

        # Check branch A
        tree.switch("branch-a")
        messages_a = tree.get_branch_messages()
        contents_a = [m.content for m in messages_a]
        assert "Common base" in contents_a
        assert "Only in A" in contents_a
        assert "Only in B" not in contents_a

        # Check branch B
        tree.switch("branch-b")
        messages_b = tree.get_branch_messages()
        contents_b = [m.content for m in messages_b]
        assert "Common base" in contents_b
        assert "Only in B" in contents_b
        assert "Only in A" not in contents_b


class TestContextGeneration:
    """Context string generation."""

    @pytest.fixture
    def tree(self, tmp_path):
        from scripts.agentica_patterns.session_tree import SessionTree
        return SessionTree(session_id="test", db_path=tmp_path / "session.db")

    def test_to_context_includes_branch_info(self, tree):
        """Context should include branch information."""
        tree.add_message("user", "Hello")
        tree.fork("experiment", "Testing")

        context = tree.to_context()
        assert "experiment" in context
        assert "Branch ID:" in context
        assert "Total Branches: 2" in context

    def test_to_context_lists_available_branches(self, tree):
        """Context should list available branches."""
        tree.fork("branch-a", "First")
        tree.switch("main")
        tree.fork("branch-b", "Second")

        context = tree.to_context()
        assert "branch-a" in context
        assert "branch-b" in context
        assert "main" in context
