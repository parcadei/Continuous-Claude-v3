"""Tests for build_premise() function."""

import pytest
from scripts.agentica.primitives import build_premise


class TestBuildPremise:
    """Tests for build_premise utility."""

    def test_build_premise_basic(self):
        """Test basic premise with required fields."""
        result = build_premise(
            role="Test Agent",
            task="Do testing",
            do=["Write tests"],
            dont=["Skip coverage"],
        )
        assert "ROLE: Test Agent" in result
        assert "TASK: Do testing" in result
        assert "DO:" in result
        assert "- Write tests" in result
        assert "DON'T:" in result
        assert "- Skip coverage" in result

    def test_build_premise_with_examples(self):
        """Test premise with optional examples."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Action"],
            dont=["Anti-action"],
            examples=["Example 1", "Example 2"],
        )
        assert "EXAMPLES:" in result
        assert "- Example 1" in result
        assert "- Example 2" in result

    def test_build_premise_empty_do(self):
        """Test that empty DO list omits DO section."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=[],
            dont=["Anti-action"],
        )
        assert "DO:" not in result
        assert "DON'T:" in result

    def test_build_premise_empty_dont(self):
        """Test that empty DON'T list omits DON'T section."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Action"],
            dont=[],
        )
        assert "DO:" in result
        assert "DON'T:" not in result

    def test_build_premise_backward_compatible(self):
        """Test that output is a plain string usable by spawn()."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Do this"],
            dont=["Not that"],
        )
        assert isinstance(result, str)
        # Must work with existing spawn() signature
        # spawn(premise=result) should work unchanged

    def test_build_premise_format_structure(self):
        """Test sections appear in ROLE > TASK > DO > DON'T > EXAMPLES order."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Do"],
            dont=["Dont"],
            examples=["Ex"],
        )
        role_pos = result.find("ROLE:")
        task_pos = result.find("TASK:")
        do_pos = result.find("DO:")
        dont_pos = result.find("DON'T:")
        examples_pos = result.find("EXAMPLES:")

        assert role_pos < task_pos < do_pos < dont_pos < examples_pos

    def test_build_premise_multiple_do_items(self):
        """Test multiple DO items are formatted correctly."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["First", "Second", "Third"],
            dont=["Bad"],
        )
        assert "- First" in result
        assert "- Second" in result
        assert "- Third" in result

    def test_build_premise_none_examples(self):
        """Test that None examples are not included."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Action"],
            dont=["Anti-action"],
            examples=None,
        )
        assert "EXAMPLES" not in result


class TestBuildPremiseHardening:
    """Hardening tests for build_premise() based on mutation analysis and bug research."""

    # ========================================================================
    # Mutation Analysis Tests - Format Verification
    # ========================================================================

    def test_exact_header_format(self):
        """Test exact header format with space after colon."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Action"],
            dont=["Anti"],
        )
        # Verify exact format with space after colon
        assert result.startswith("ROLE: Agent")
        assert "TASK: Task" in result
        assert "DO:\n" in result
        assert "DON'T:\n" in result
        # Ensure no format without space
        assert "ROLE:Agent" not in result
        assert "TASK:Task" not in result

    def test_single_item_do_list(self):
        """Test that single DO item is included."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Single action"],
            dont=[],
        )
        assert "DO:" in result
        assert "- Single action" in result

    def test_single_item_dont_list(self):
        """Test that single DON'T item is included."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=[],
            dont=["Single anti-pattern"],
        )
        assert "DON'T:" in result
        assert "- Single anti-pattern" in result

    def test_section_separation(self):
        """Test that sections are separated by double newlines."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Do"],
            dont=["Dont"],
        )
        # Verify double newline between sections
        assert "\n\n" in result
        # Should have at least 3 double newlines: ROLE-TASK, TASK-DO, DO-DONT
        assert result.count("\n\n") >= 3

    def test_bullet_format_with_space(self):
        """Test that list items use '- ' not '-' or other formats."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["First", "Second"],
            dont=["Bad"],
        )
        # Verify bullets with spaces
        assert "\n- First\n" in result
        assert "\n- Second\n" in result
        assert "\n- Bad" in result
        # Ensure no malformed bullets
        assert "\n-First" not in result
        assert "\n-Second" not in result
        assert "\n* " not in result  # No asterisk bullets

    # ========================================================================
    # Bug Category Tests - P0 Critical
    # ========================================================================

    def test_newline_in_item_sanitized(self):
        """Newlines in items should be replaced with space (P0)."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Line1\nLine2", "Valid"],
            dont=[],
        )
        # Newlines should be replaced, not break list format
        lines = result.split('\n')
        do_items = [l for l in lines if l.startswith('- ')]
        # Should still have 2 items, not 3
        assert len(do_items) == 2
        # Content should be sanitized (expect this to fail initially)
        assert "Line1 Line2" in result or "Line1\nLine2" in result

    # ========================================================================
    # Bug Category Tests - P1 High Priority
    # ========================================================================

    def test_none_in_list_filtered(self):
        """None values in lists should be filtered out (P1)."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Valid", None, "Also valid"],
            dont=[],
        )
        # None should be filtered, not appear as "None" string
        assert "- None" not in result
        assert "Valid" in result
        assert "Also valid" in result

    def test_empty_string_filtered(self):
        """Empty strings in lists should be filtered (P1)."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Valid", "", "Also valid"],
            dont=[],
        )
        # No empty bullets
        assert "- \n" not in result
        lines = result.split('\n')
        do_items = [l for l in lines if l.startswith('- ')]
        # Should only have 2 items, not 3
        assert len(do_items) == 2

    def test_whitespace_only_filtered(self):
        """Whitespace-only items should be filtered (P1)."""
        result = build_premise(
            role="Agent",
            task="Task",
            do=["Valid", "   ", "Also valid"],
            dont=[],
        )
        # No whitespace-only bullets
        assert "-    " not in result
        lines = result.split('\n')
        do_items = [l for l in lines if l.startswith('- ')]
        # Should only have 2 items, not 3
        assert len(do_items) == 2

    def test_empty_role_raises(self):
        """Empty role should raise ValueError (P1)."""
        with pytest.raises(ValueError, match="role"):
            build_premise(
                role="",
                task="Task",
                do=["Action"],
                dont=[],
            )

    def test_empty_task_raises(self):
        """Empty task should raise ValueError (P1)."""
        with pytest.raises(ValueError, match="task"):
            build_premise(
                role="Agent",
                task="",
                do=["Action"],
                dont=[],
            )

    # ========================================================================
    # Bug Category Tests - P2 Important
    # ========================================================================

    def test_unicode_preserved(self):
        """Unicode and emoji should be preserved correctly (P2)."""
        result = build_premise(
            role="Review Agent 🔍",
            task="Check 👍 reactions",
            do=["Find 🎯 patterns", "Flag 🚩 issues"],
            dont=["Ignore 🙈 warnings"],
        )
        # Emoji should be preserved
        assert "🔍" in result
        assert "👍" in result
        assert "🎯" in result
        assert "🚩" in result
        assert "🙈" in result

    def test_very_long_item(self):
        """Very long items should not break (P2)."""
        long_item = "A" * 1000
        result = build_premise(
            role="Agent",
            task="Task",
            do=[long_item, "Short"],
            dont=[],
        )
        # Should handle long items without crashing
        assert long_item in result
        assert "Short" in result
        # Basic structure should still be intact
        assert "DO:" in result

    # ========================================================================
    # Mutation Round 2 Gap Tests - Critical Coverage
    # ========================================================================

    def test_whitespace_only_role_raises(self):
        """Whitespace-only role should raise ValueError."""
        with pytest.raises(ValueError, match="role"):
            build_premise(role="   ", task="Test", do=["a"], dont=["b"])

    def test_whitespace_only_task_raises(self):
        """Whitespace-only task should raise ValueError."""
        with pytest.raises(ValueError, match="task"):
            build_premise(role="Agent", task="   ", do=["a"], dont=["b"])

    def test_newline_replaced_with_space_not_removed(self):
        """Newlines should become spaces, not be removed."""
        result = build_premise(
            role="Agent",
            task="Test",
            do=["Line one\nLine two"],
            dont=[]
        )
        # Should be "Line one Line two" not "Line oneLine two"
        assert "Line one Line two" in result
        # Verify it's NOT concatenated without space
        assert "Line oneLine two" not in result

    def test_examples_sanitized(self):
        """Examples should filter None and empty strings."""
        result = build_premise(
            role="Agent",
            task="Test",
            do=["a"],
            dont=["b"],
            examples=[None, "", "  ", "Valid example"]
        )
        assert "Valid example" in result
        assert "- None" not in result
        # Count example items - should only have 1
        lines = result.split('\n')
        # Find EXAMPLES section first
        if "EXAMPLES:" in result:
            examples_idx = lines.index("EXAMPLES:")
            example_items = [l for l in lines[examples_idx+1:] if l.startswith('- ')]
            assert len(example_items) == 1
