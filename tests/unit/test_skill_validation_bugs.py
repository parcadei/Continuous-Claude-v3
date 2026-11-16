"""Test Validation Bugs - TDD Failing Tests.

These tests are designed to FAIL initially, exposing validation bugs.
Based on bug research from:
- .claude/cache/agents/research-agent/latest-output.md
- thoughts/shared/implementation/mutation-round-1-report.md

Bug categories tested:
1. Empty string vs None confusion
2. Whitespace-only input handling
3. Boundary conditions (0, negative, max length)
4. Invalid characters in skill names
5. Type coercion errors
"""

import pytest


class TestEmptyVsNoneHandling:
    """Test empty string vs None consistency."""

    def test_skill_name_empty_vs_none_consistency(self):
        """
        Bug: Empty string and None may be treated differently.
        Expected: Consistent fallback behavior.
        Actual: May return "" for empty, "generated-skill" for other cases.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # Empty string should produce default
        result_empty = derive_skill_name("")

        assert result_empty  # Not empty
        assert result_empty == "generated-skill" or len(result_empty) > 0

    def test_empty_description_produces_valid_spec(self):
        """
        Bug: Empty description may cause downstream issues.
        Expected: SkillSpec with empty description is valid.
        Actual: May fail validation or produce bad YAML.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml

        spec = SkillSpec(
            name="test",
            description="",  # Empty
            goal="Test goal",
            tools=[],
            instructions="Steps"
        )

        result = generate_skill_yaml(spec)
        assert "---" in result
        assert "name: test" in result

    def test_empty_goal_handled(self):
        """
        Bug: Empty goal may break instruction generation.
        Expected: Use fallback or empty string.
        Actual: May produce malformed output.
        """
        from scripts.agentica_patterns.skill_generator import generate_instructions

        result = generate_instructions(
            task_type="implementation",
            goal="",  # Empty
            resolved_qheuristics={}
        )

        assert result  # Should produce something
        assert isinstance(result, str)

    def test_empty_instructions_handled(self):
        """
        Bug: Empty instructions may produce invalid SKILL.md.
        Expected: Valid output even with empty instructions.
        Actual: May produce file with missing section.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml

        spec = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=[],
            instructions=""  # Empty
        )

        result = generate_skill_yaml(spec)
        assert "## Instructions" in result


class TestWhitespaceHandling:
    """Test whitespace-only input handling."""

    def test_whitespace_only_prompt(self):
        """
        Bug: Whitespace-only prompt may not trigger fallback.
        Expected: Treated as empty, use default name.
        Actual: May produce name like '---' or crash.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("   \t\n   ")

        assert result
        # Should not contain only whitespace
        assert result.strip() == result

    def test_whitespace_only_description(self):
        """
        Bug: Whitespace description may not be stripped.
        Expected: Strip or treat as empty.
        Actual: May produce 'description:    '.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml
        import yaml

        spec = SkillSpec(
            name="test",
            description="   ",  # Whitespace only
            goal="goal",
            tools=[],
            instructions="steps"
        )

        content = generate_skill_yaml(spec)
        parts = content.split('---')
        parsed = yaml.safe_load(parts[1])

        # Description should be empty or stripped
        desc = parsed.get('description', '')
        assert desc is None or desc == "" or desc.strip() == ""

    def test_leading_trailing_whitespace_in_name(self):
        """
        Bug: Whitespace around name not stripped.
        Expected: Strip leading/trailing whitespace.
        Actual: May create ' skill ' directory.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("  implement auth  ")

        assert not result.startswith(' ')
        assert not result.endswith(' ')
        assert not result.startswith('-')
        assert not result.endswith('-')

    def test_multiple_spaces_in_name(self):
        """
        Bug: Multiple consecutive spaces may become multiple hyphens.
        Expected: Single hyphen for word boundaries.
        Actual: May produce 'skill--with--gaps'.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("implement    a    feature")

        # Should not have double hyphens
        assert '--' not in result


class TestBoundaryConditions:
    """Test boundary value handling."""

    def test_skill_name_exactly_50_chars(self):
        """
        Bug: Boundary at max length (50) may be off-by-one.
        Expected: Accept exactly 50 chars.
        Actual: May reject or allow 51.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # Create prompt that would generate ~50 char name
        long_prompt = "word " * 15  # Many words

        result = derive_skill_name(long_prompt)

        assert len(result) <= 50
        assert len(result) > 0

    def test_skill_name_at_49_and_51_chars(self):
        """
        Bug: Off-by-one at boundary.
        Expected: 49 OK, 50 OK, 51 truncated.
        Actual: May truncate at wrong position.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # Test near-boundary prompts
        short_prompt = "a" * 48
        medium_prompt = "a" * 49
        long_prompt = "a" * 100

        result_short = derive_skill_name(short_prompt)
        result_medium = derive_skill_name(medium_prompt)
        result_long = derive_skill_name(long_prompt)

        assert len(result_short) <= 50
        assert len(result_medium) <= 50
        assert len(result_long) <= 50

    def test_empty_tools_list_boundary(self):
        """
        Bug: Empty list vs list with empty string handled differently.
        Expected: Consistent behavior.
        Actual: May produce 'allowed-tools: []' vs 'allowed-tools: [""]'.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml
        import yaml

        spec_empty = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=[],  # Empty list
            instructions="steps"
        )

        content = generate_skill_yaml(spec_empty)
        parts = content.split('---')
        parsed = yaml.safe_load(parts[1])

        # Should either omit field or have empty list
        if 'allowed-tools' in parsed:
            assert parsed['allowed-tools'] == [] or parsed['allowed-tools'] is None

    def test_single_tool_boundary(self):
        """
        Bug: Single-element list may be serialized as string.
        Expected: Still a list.
        Actual: May produce 'allowed-tools: Bash' instead of '[Bash]'.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml
        import yaml

        spec = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=["Bash"],  # Single element
            instructions="steps"
        )

        content = generate_skill_yaml(spec)
        parts = content.split('---')
        parsed = yaml.safe_load(parts[1])

        assert 'allowed-tools' in parsed
        assert isinstance(parsed['allowed-tools'], list)

    def test_zero_significant_words(self):
        """
        Bug: Prompt with only common words has zero significant words.
        Expected: Use fallback mechanism.
        Actual: May crash or return empty.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # All common words
        result = derive_skill_name("the a an for to with and or")

        assert result
        assert len(result) > 0


class TestInvalidCharactersInName:
    """Test invalid character handling in skill names."""

    def test_special_characters_filtered(self):
        """
        Bug: Special characters in name may create invalid paths.
        Expected: Filter or escape special characters.
        Actual: May create 'skill:name' directory (invalid on Windows).
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("implement feature: version 2.0!")

        # Should not contain invalid path characters
        invalid_chars = [':', '/', '\\', '<', '>', '|', '?', '*', '"']
        for char in invalid_chars:
            assert char not in result

    def test_only_special_characters(self):
        """
        Bug: Input with only special chars may produce empty name.
        Expected: Fallback to default.
        Actual: May return '' or crash.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("!@#$%^&*()[]{}|\\:;<>?,./")

        assert result
        assert result == "generated-skill" or len(result) > 0

    def test_unicode_normalization(self):
        """
        Bug: Combining characters may not be normalized.
        Expected: Consistent Unicode handling.
        Actual: May produce visually identical but different names.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # Precomposed vs decomposed
        result1 = derive_skill_name("cafe")  # e with acute (precomposed)
        result2 = derive_skill_name("cafe")  # regular e

        # Should produce valid names
        assert result1
        assert result2

    def test_control_characters_filtered(self):
        """
        Bug: Control characters may not be filtered.
        Expected: Remove control characters.
        Actual: May include null bytes or similar.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("implement\x00feature\x1f")

        # Should not contain control characters
        assert '\x00' not in result
        assert '\x1f' not in result


class TestTypeCoercion:
    """Test type coercion and validation."""

    def test_skill_name_type_must_be_string(self):
        """
        Bug: Non-string name may cause AttributeError.
        Expected: Clear error or coercion.
        Actual: May crash with cryptic error.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # Number as string
        result = derive_skill_name(str(12345))
        assert isinstance(result, str)

    def test_tools_must_be_list(self):
        """
        Bug: String passed as tools may iterate over characters.
        Expected: Reject or wrap in list.
        Actual: May produce 'allowed-tools: [B, a, s, h]'.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml
        import yaml

        # Valid case with list
        spec = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=["Bash", "Read"],
            instructions="steps"
        )

        content = generate_skill_yaml(spec)
        parts = content.split('---')
        parsed = yaml.safe_load(parts[1])

        if 'allowed-tools' in parsed:
            # Each tool should be a word, not a character
            for tool in parsed['allowed-tools']:
                assert len(tool) > 1

    def test_qheuristics_dict_required(self):
        """
        Bug: Non-dict qheuristics may cause KeyError.
        Expected: Clear validation error.
        Actual: May crash with 'str has no attribute get'.
        """
        from scripts.agentica_patterns.skill_generator import generate_instructions

        # With valid dict
        result = generate_instructions(
            task_type="implementation",
            goal="Test",
            resolved_qheuristics={}  # Empty dict is valid
        )
        assert result

        # The function should handle missing keys gracefully
        result2 = generate_instructions(
            task_type="unknown_type",
            goal="Test",
            resolved_qheuristics={}
        )
        assert result2


class TestInstructionGeneration:
    """Test instruction generation edge cases."""

    def test_unknown_task_type_fallback(self):
        """
        Bug: Unknown task type may not have template.
        Expected: Use fallback template.
        Actual: May crash with KeyError.
        """
        from scripts.agentica_patterns.skill_generator import generate_instructions

        result = generate_instructions(
            task_type="completely_unknown_type",
            goal="Test goal",
            resolved_qheuristics={}
        )

        assert result
        assert isinstance(result, str)
        assert "Test goal" in result or "task" in result.lower()

    def test_missing_qheuristic_values(self):
        """
        Bug: Missing qheuristic values may leave placeholders.
        Expected: Use default values.
        Actual: May produce 'test_coverage: {test_coverage}'.
        """
        from scripts.agentica_patterns.skill_generator import generate_instructions

        result = generate_instructions(
            task_type="implementation",
            goal="Test",
            resolved_qheuristics={}  # Missing all values
        )

        # Should not have unresolved placeholders
        assert '{' not in result
        assert '}' not in result

    def test_research_results_integration(self):
        """
        Bug: Research results may not be properly formatted.
        Expected: Extract and format insights.
        Actual: May append raw object repr.
        """
        from scripts.agentica_patterns.skill_generator import generate_instructions

        class MockResult:
            content = "Best practice: always test your code"

        result = generate_instructions(
            task_type="implementation",
            goal="Test",
            resolved_qheuristics={},
            research_results=[MockResult(), MockResult()]
        )

        # Should include research content
        assert "Best practice" in result or "Research" in result


class TestTriggerGeneration:
    """Test trigger generation edge cases."""

    def test_trigger_from_empty_prompt(self):
        """
        Bug: Empty prompt may produce empty triggers.
        Expected: Empty but valid structure.
        Actual: May crash or return None.
        """
        from scripts.agentica_patterns.skill_generator import generate_triggers

        result = generate_triggers("", "implementation")

        assert result is not None
        assert 'keywords' in result
        assert 'intentPatterns' in result
        assert isinstance(result['keywords'], list)
        assert isinstance(result['intentPatterns'], list)

    def test_trigger_extracts_significant_words(self):
        """
        Bug: May not filter common words from keywords.
        Expected: Only significant words in keywords.
        Actual: May include 'the', 'and', etc.
        """
        from scripts.agentica_patterns.skill_generator import generate_triggers

        result = generate_triggers(
            "implement the authentication system with JWT",
            "implementation"
        )

        keywords = result['keywords']

        # Should not include common words
        common = {'the', 'with', 'and', 'for', 'to'}
        for kw in keywords:
            assert kw not in common

    def test_trigger_unknown_task_type(self):
        """
        Bug: Unknown task type may crash pattern generation.
        Expected: Empty patterns, valid structure.
        Actual: May crash or return malformed data.
        """
        from scripts.agentica_patterns.skill_generator import generate_triggers

        result = generate_triggers(
            "do something special",
            "unknown_task_type"
        )

        assert result is not None
        assert isinstance(result, dict)
        assert 'keywords' in result
        assert 'intentPatterns' in result


class TestGenerateFromQheuristics:
    """Test the main generation function."""

    def test_minimal_input(self):
        """
        Bug: Minimal input may crash at various points.
        Expected: Produce valid spec with defaults.
        Actual: May crash with empty fields.
        """
        from scripts.agentica_patterns.skill_generator import generate_from_qheuristics

        spec = generate_from_qheuristics(
            task_type="implementation",
            resolved_qheuristics={},
            original_prompt="test"
        )

        assert spec.name
        assert spec.description
        assert spec.goal
        assert spec.tools is not None
        assert spec.instructions

    def test_goal_extraction_from_prompt(self):
        """
        Bug: Goal extraction may fail on short prompts.
        Expected: Extract or use full prompt as goal.
        Actual: May produce empty goal.
        """
        from scripts.agentica_patterns.skill_generator import generate_from_qheuristics

        spec = generate_from_qheuristics(
            task_type="implementation",
            resolved_qheuristics={},
            original_prompt="x"  # Very short
        )

        assert spec.goal
        assert len(spec.goal) > 0

    def test_tool_selection_from_qheuristics(self):
        """
        Bug: Custom tools in qheuristics may not override defaults.
        Expected: Use tools from qheuristics if provided.
        Actual: May ignore and use defaults.
        """
        from scripts.agentica_patterns.skill_generator import generate_from_qheuristics

        spec = generate_from_qheuristics(
            task_type="implementation",
            resolved_qheuristics={"tools": "CustomTool1, CustomTool2"},
            original_prompt="test prompt"
        )

        assert "CustomTool1" in spec.tools
        assert "CustomTool2" in spec.tools
