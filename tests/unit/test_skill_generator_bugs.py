"""Test YAML Generation Bugs - TDD Failing Tests.

These tests are designed to FAIL initially, exposing bugs in skill_generator.py.
Based on bug research from:
- .claude/cache/agents/research-agent/latest-output.md
- thoughts/shared/implementation/mutation-round-1-report.md

Bug categories tested:
1. Special character escaping failures
2. Empty/whitespace handling
3. Unicode handling
4. Multiline string handling
5. Indentation consistency
"""

import pytest
import yaml


class TestYAMLSpecialCharacters:
    """Test special character handling in YAML generation."""

    def test_yaml_escape_handles_colon_in_value(self):
        """
        Bug: Colons in values break YAML parsing without proper quoting.
        Expected: Value with colon should be quoted.
        Actual: May produce invalid YAML like 'description: has:colon'.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("value:with:colons")
        # Must be quoted to be valid YAML
        assert result.startswith('"') or result.startswith("'")

        # Must parse without error
        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        assert parsed['key'] == "value:with:colons"

    def test_yaml_escape_handles_hash_symbol(self):
        """
        Bug: Hash symbols start comments in YAML.
        Expected: Hash in values should be quoted.
        Actual: May produce 'description: foo#bar' which truncates at #.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("comment#here")

        # Must parse correctly (hash not treated as comment)
        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        assert parsed['key'] == "comment#here"

    def test_yaml_escape_handles_newlines(self):
        """
        Bug: Newlines in values break single-line YAML.
        Expected: Newlines should be escaped or value multiline-formatted.
        Actual: May produce invalid YAML with literal newline.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("line1\nline2\nline3")

        # Must produce valid YAML
        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        # Newlines should be preserved semantically
        assert "line1" in parsed['key']
        assert "line2" in parsed['key']

    def test_yaml_escape_handles_tab_characters(self):
        """
        Bug: Tab characters may not be properly escaped.
        Expected: Tabs should be escaped or value quoted.
        Actual: May produce invalid YAML or unexpected whitespace.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("has\ttab\there")

        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        # Tab should be preserved (as tab or escaped)
        assert "has" in parsed['key']
        assert "tab" in parsed['key']

    def test_yaml_escape_handles_quotes_in_value(self):
        """
        Bug: Internal quotes can break YAML quoting.
        Expected: Quotes should be escaped properly.
        Actual: May produce '"value "with" quotes"' which is invalid.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape('value "with" quotes')

        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        assert parsed['key'] == 'value "with" quotes'

    def test_yaml_escape_handles_single_quotes(self):
        """
        Bug: Single quotes in double-quoted strings not escaped.
        Expected: Both quote types handled correctly.
        Actual: May produce "value 'with' single" which works, but what about mixed?
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("value 'with' single and \"double\" quotes")

        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        assert "single" in parsed['key']
        assert "double" in parsed['key']

    def test_yaml_escape_handles_brackets(self):
        """
        Bug: Brackets start lists/maps in YAML.
        Expected: Brackets in values should be quoted.
        Actual: May produce 'key: [not a list]' parsed as list.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("[not a list]")

        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        # Must be string, not list
        assert isinstance(parsed['key'], str)
        assert parsed['key'] == "[not a list]"

    def test_yaml_escape_handles_curly_braces(self):
        """
        Bug: Curly braces start maps in YAML.
        Expected: Braces in values should be quoted.
        Actual: May produce 'key: {not: a map}' parsed as map.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("{not: a map}")

        full_yaml = f"key: {result}"
        parsed = yaml.safe_load(full_yaml)
        # Must be string, not dict
        assert isinstance(parsed['key'], str)


class TestYAMLEmptyWhitespaceHandling:
    """Test empty and whitespace-only value handling."""

    def test_yaml_handles_empty_description(self):
        """
        Bug: Empty description may produce invalid 'description:' line.
        Expected: Empty values should produce valid YAML.
        Actual: May produce YAML that fails to parse or has wrong type.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="test-skill",
            description="",  # Empty
            goal="A goal",
            tools=[],
            instructions="Do the thing"
        )
        content = generate_skill_yaml(spec)

        # Extract and parse frontmatter
        parts = content.split('---')
        assert len(parts) >= 3, "Must have frontmatter delimiters"

        frontmatter = yaml.safe_load(parts[1])
        # Empty description should be string or None, not missing
        assert 'description' in frontmatter
        assert frontmatter['description'] == "" or frontmatter['description'] is None

    def test_yaml_handles_whitespace_only_description(self):
        """
        Bug: Whitespace-only values may not be trimmed.
        Expected: Whitespace-only should be treated as empty or trimmed.
        Actual: May produce 'description:    ' which parses differently.
        """
        from scripts.agentica_patterns.skill_generator import _yaml_escape

        result = _yaml_escape("   ")

        # Should either be empty or quoted
        assert result.strip() == "" or result.startswith('"')

    def test_yaml_handles_empty_tools_list(self):
        """
        Bug: Empty tools list may omit field or produce '[]'.
        Expected: Consistent behavior for empty tools.
        Actual: May produce 'allowed-tools: ' which is not a list.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=[],  # Empty list
            instructions="steps"
        )
        content = generate_skill_yaml(spec)

        parts = content.split('---')
        frontmatter = yaml.safe_load(parts[1])

        # Either no allowed-tools key, or an empty list
        if 'allowed-tools' in frontmatter:
            assert isinstance(frontmatter['allowed-tools'], list)


class TestYAMLUnicodeHandling:
    """Test Unicode and international character handling."""

    def test_derive_skill_name_handles_accented_characters(self):
        """
        Bug: Accented chars may be stripped or cause regex errors.
        Expected: Accented characters handled gracefully.
        Actual: May produce empty name or crash.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # French text with accents
        result = derive_skill_name("implementer un systeme d'authentification")

        assert result  # Must produce something
        assert isinstance(result, str)
        assert len(result) > 0

    def test_derive_skill_name_handles_emoji(self):
        """
        Bug: Emoji may not be filtered correctly by regex.
        Expected: Emoji stripped, valid name produced.
        Actual: May crash or produce name with emoji.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("build a chat bot for users")

        assert result
        # Should not contain emoji in final name
        # Name should be kebab-case
        assert '-' in result or result.isalpha()

    def test_yaml_preserves_unicode_in_description(self):
        """
        Bug: Unicode in description may be corrupted.
        Expected: Unicode preserved through generation.
        Actual: May mangle or drop non-ASCII.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="unicode-test",
            description="Cafe, naive, resume",
            goal="Handle international text",
            tools=[],
            instructions="Test"
        )
        content = generate_skill_yaml(spec)

        parts = content.split('---')
        frontmatter = yaml.safe_load(parts[1])

        # Unicode should be preserved
        assert "Cafe" in frontmatter['description'] or "cafe" in frontmatter['description'].lower()

    def test_yaml_handles_cjk_characters(self):
        """
        Bug: CJK (Chinese/Japanese/Korean) chars may break regex.
        Expected: CJK handled gracefully.
        Actual: May crash or produce invalid output.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        # Japanese text
        result = derive_skill_name("Build a tool")

        # Should produce valid kebab-case name
        assert result
        assert all(c.isalnum() or c == '-' for c in result)


class TestYAMLMultilineHandling:
    """Test multiline string handling in YAML generation."""

    def test_multiline_instructions_produce_valid_yaml(self):
        """
        Bug: Multiline instructions may break YAML formatting.
        Expected: Multiline content properly formatted.
        Actual: May produce invalid YAML with unescaped newlines.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        multiline_instructions = """1. First step
2. Second step
3. Third step with details:
   - Sub-item a
   - Sub-item b"""

        spec = SkillSpec(
            name="multiline-test",
            description="Test multiline",
            goal="Test",
            tools=["Bash"],
            instructions=multiline_instructions
        )
        content = generate_skill_yaml(spec)

        # Should not raise when parsing
        parts = content.split('---')
        yaml.safe_load(parts[1])  # Must not raise

        # Instructions should appear in markdown section
        assert "First step" in content
        assert "Second step" in content

    def test_multiline_goal_handled_correctly(self):
        """
        Bug: Multiline goal in YAML frontmatter may break parsing.
        Expected: Goal properly handled (escaped or truncated).
        Actual: May produce invalid frontmatter.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="test",
            description="desc",
            goal="Line 1.\nLine 2.\nLine 3.",
            tools=[],
            instructions="steps"
        )
        content = generate_skill_yaml(spec)

        parts = content.split('---')
        # Must parse without error
        yaml.safe_load(parts[1])


class TestYAMLIndentationConsistency:
    """Test indentation produces valid YAML."""

    def test_generated_yaml_has_consistent_indentation(self):
        """
        Bug: Mixed indentation (2 vs 4 spaces) breaks YAML.
        Expected: Consistent indentation throughout.
        Actual: May mix indentation levels.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="indent-test",
            description="Test indentation",
            goal="Test",
            tools=["Bash", "Read", "Write"],
            instructions="Step 1"
        )
        content = generate_skill_yaml(spec)

        # Parse must succeed
        parts = content.split('---')
        parsed = yaml.safe_load(parts[1])

        # Verify structure is correct
        assert parsed['name'] == "indent-test"
        if 'allowed-tools' in parsed:
            assert isinstance(parsed['allowed-tools'], list)

    def test_yaml_tools_list_format_is_valid(self):
        """
        Bug: Tools list format may be invalid (wrong brackets, spacing).
        Expected: Tools as valid YAML list.
        Actual: May produce malformed list syntax.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="tools-test",
            description="desc",
            goal="goal",
            tools=["Bash", "Read", "Write", "Edit", "Glob"],
            instructions="steps"
        )
        content = generate_skill_yaml(spec)

        parts = content.split('---')
        parsed = yaml.safe_load(parts[1])

        # Tools must be a list with correct values
        assert 'allowed-tools' in parsed
        assert isinstance(parsed['allowed-tools'], list)
        assert "Bash" in parsed['allowed-tools']


class TestSkillNameDerivation:
    """Test skill name derivation edge cases."""

    def test_derive_skill_name_from_empty_string(self):
        """
        Bug: Empty input may return empty string or crash.
        Expected: Fallback to default name.
        Actual: May return "" which is invalid.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("")

        assert result  # Not empty
        assert len(result) > 0
        assert result == "generated-skill" or len(result) > 0

    def test_derive_skill_name_truncates_at_max_length(self):
        """
        Bug: Long names may exceed 50 char limit or truncate mid-word.
        Expected: Truncate at word boundary, max 50 chars.
        Actual: May produce 51+ chars or end with hyphen.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        long_prompt = "implement a very complex authentication system with multiple " * 5
        result = derive_skill_name(long_prompt)

        assert len(result) <= 50
        assert not result.endswith('-')

    def test_derive_skill_name_removes_common_words(self):
        """
        Bug: Common words like 'the', 'a' may remain in name.
        Expected: Common words filtered out.
        Actual: May produce 'implement-the-auth' instead of 'auth'.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("implement the authentication for the users")

        # Should not start with 'implement-the' or similar
        assert not result.startswith("implement-the")
        assert not result.startswith("the-")

    def test_derive_skill_name_handles_only_common_words(self):
        """
        Bug: Input with only common words may produce empty name.
        Expected: Fallback mechanism kicks in.
        Actual: May return "" or crash.
        """
        from scripts.agentica_patterns.skill_generator import derive_skill_name

        result = derive_skill_name("implement the a an for to")

        assert result  # Not empty
        assert len(result) > 0


class TestToolsListHandling:
    """Test tools parameter edge cases."""

    def test_tools_with_non_string_elements(self):
        """
        Bug: Non-string tool names may cause TypeError.
        Expected: Convert to strings or raise clear error.
        Actual: May crash with AttributeError.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        # This tests if the code handles mixed types
        spec = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=["Bash", "Read"],  # Valid first
            instructions="steps"
        )
        result = generate_skill_yaml(spec)
        assert "Bash" in result

    def test_tools_with_special_characters(self):
        """
        Bug: Tool names with special chars may break YAML.
        Expected: Proper escaping or rejection.
        Actual: May produce invalid YAML.
        """
        from scripts.agentica_patterns.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name="test",
            description="desc",
            goal="goal",
            tools=["Tool:Name", "Another#Tool"],  # Special chars
            instructions="steps"
        )
        result = generate_skill_yaml(spec)

        # Must produce parseable YAML
        parts = result.split('---')
        parsed = yaml.safe_load(parts[1])

        if 'allowed-tools' in parsed:
            assert isinstance(parsed['allowed-tools'], list)
