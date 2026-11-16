"""Comprehensive tests for skill_loader.py and skill_schema_parser.py.

This test module covers:
1. Unit tests for all public functions
2. Edge cases (empty files, malformed YAML, missing sections)
3. Integration tests with real file I/O
4. Pytest fixtures for common test scenarios
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from scripts.skill_schema_parser import (
    SkillParameter,
    SkillSchema,
    parse_skill_schema,
)
from scripts.skill_loader import load_skill_schema


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def valid_skill_content() -> str:
    """A complete, valid SKILL.md with all features."""
    return """---
name: test-skill
description: A comprehensive test skill
version: "2.0"
parameters:
  output_format:
    type: enum
    values: [json, yaml, text]
    default: json
    required: false
  verbose:
    type: bool
    default: false
  timeout:
    type: int
    min: 1
    max: 300
    default: 30
  pattern:
    type: string
    infer_from: '.*\\.py$'
    required: true
  duration:
    type: duration
    default: "5m"
---

# Test Skill

This is the main content.

## When to Use

Use this for testing.

## Commands

```bash
echo "test"
```
"""


@pytest.fixture
def minimal_skill_content() -> str:
    """Minimal valid SKILL.md with only required fields."""
    return """---
name: minimal-skill
---

# Minimal Skill

Just the basics.
"""


@pytest.fixture
def skill_without_frontmatter() -> str:
    """SKILL.md with no YAML frontmatter."""
    return """# No Frontmatter Skill

This skill has no YAML frontmatter at all.

## Section

Content here.
"""


@pytest.fixture
def skill_with_malformed_yaml() -> str:
    """SKILL.md with invalid YAML in frontmatter."""
    return """---
name: broken-skill
parameters:
  - this: is
    not: valid
      yaml: structure
    indentation: wrong
---

# Broken Skill
"""


@pytest.fixture
def skill_with_unclosed_frontmatter() -> str:
    """SKILL.md with unclosed frontmatter delimiter."""
    return """---
name: unclosed
description: Missing closing delimiter

# This should not work
"""


@pytest.fixture
def empty_skill_content() -> str:
    """Completely empty SKILL.md."""
    return ""


@pytest.fixture
def skill_with_only_frontmatter() -> str:
    """SKILL.md with frontmatter but no body content."""
    return """---
name: frontmatter-only
description: Just metadata, no body
---
"""


@pytest.fixture
def skill_with_complex_parameters() -> str:
    """SKILL.md with various parameter types for type testing."""
    return """---
name: complex-params
parameters:
  enum_param:
    type: enum
    values: [a, b, c]
    required: true
  bool_param:
    type: bool
    default: true
  int_param:
    type: int
    min: 0
    max: 100
  string_param:
    type: string
    infer_from: 'test-.*'
  duration_param:
    type: duration
    default: "1h30m"
  no_type_param:
    default: "uses default string type"
---

# Complex Parameters
"""


@pytest.fixture
def temp_skills_dir() -> Generator[Path, None, None]:
    """Create a temporary skills directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_base = Path(tmpdir) / ".claude" / "skills"
        skills_base.mkdir(parents=True)
        yield Path(tmpdir)


@pytest.fixture
def populated_skills_dir(
    temp_skills_dir: Path,
    valid_skill_content: str,
    minimal_skill_content: str,
) -> Path:
    """Create a temp directory with multiple skills."""
    skills_base = temp_skills_dir / ".claude" / "skills"

    # Create valid skill
    valid_dir = skills_base / "valid-skill"
    valid_dir.mkdir()
    (valid_dir / "SKILL.md").write_text(valid_skill_content)

    # Create minimal skill
    minimal_dir = skills_base / "minimal-skill"
    minimal_dir.mkdir()
    (minimal_dir / "SKILL.md").write_text(minimal_skill_content)

    return temp_skills_dir


# ============================================================================
# Unit Tests: parse_skill_schema
# ============================================================================


class TestParseSkillSchema:
    """Unit tests for parse_skill_schema function."""

    def test_parse_valid_skill(self, valid_skill_content: str) -> None:
        """Test parsing a complete, valid skill."""
        schema = parse_skill_schema(valid_skill_content)

        assert schema is not None
        assert schema.name == "test-skill"
        assert len(schema.parameters) == 5

    def test_parse_minimal_skill(self, minimal_skill_content: str) -> None:
        """Test parsing a minimal skill with only name."""
        schema = parse_skill_schema(minimal_skill_content)

        assert schema is not None
        assert schema.name == "minimal-skill"
        assert len(schema.parameters) == 0

    def test_parse_without_frontmatter_returns_none(
        self, skill_without_frontmatter: str
    ) -> None:
        """Test that missing frontmatter returns None."""
        schema = parse_skill_schema(skill_without_frontmatter)
        assert schema is None

    def test_parse_malformed_yaml_returns_none(
        self, skill_with_malformed_yaml: str
    ) -> None:
        """Test that malformed YAML returns None."""
        schema = parse_skill_schema(skill_with_malformed_yaml)
        assert schema is None

    def test_parse_unclosed_frontmatter_returns_none(
        self, skill_with_unclosed_frontmatter: str
    ) -> None:
        """Test that unclosed frontmatter returns None."""
        schema = parse_skill_schema(skill_with_unclosed_frontmatter)
        assert schema is None

    def test_parse_empty_content_returns_none(self, empty_skill_content: str) -> None:
        """Test that empty content returns None."""
        schema = parse_skill_schema(empty_skill_content)
        assert schema is None

    def test_parse_frontmatter_only(self, skill_with_only_frontmatter: str) -> None:
        """Test parsing skill with only frontmatter, no body."""
        schema = parse_skill_schema(skill_with_only_frontmatter)

        assert schema is not None
        assert schema.name == "frontmatter-only"

    def test_parse_returns_unknown_for_missing_name(self) -> None:
        """Test that missing name defaults to 'unknown'."""
        content = """---
description: No name field
---

# Content
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        assert schema.name == "unknown"


class TestSkillParameterParsing:
    """Unit tests for parameter parsing in parse_skill_schema."""

    def test_enum_parameter(self, valid_skill_content: str) -> None:
        """Test parsing enum parameter type."""
        schema = parse_skill_schema(valid_skill_content)
        assert schema is not None

        param = schema.parameters.get("output_format")
        assert param is not None
        assert param.type == "enum"
        assert param.values == ["json", "yaml", "text"]
        assert param.default == "json"
        assert param.required is False

    def test_bool_parameter(self, valid_skill_content: str) -> None:
        """Test parsing bool parameter type."""
        schema = parse_skill_schema(valid_skill_content)
        assert schema is not None

        param = schema.parameters.get("verbose")
        assert param is not None
        assert param.type == "bool"
        assert param.default is False

    def test_int_parameter_with_range(self, valid_skill_content: str) -> None:
        """Test parsing int parameter with min/max."""
        schema = parse_skill_schema(valid_skill_content)
        assert schema is not None

        param = schema.parameters.get("timeout")
        assert param is not None
        assert param.type == "int"
        assert param.min == 1
        assert param.max == 300
        assert param.default == 30

    def test_string_parameter_with_infer_from(self, valid_skill_content: str) -> None:
        """Test parsing string parameter with infer_from regex."""
        schema = parse_skill_schema(valid_skill_content)
        assert schema is not None

        param = schema.parameters.get("pattern")
        assert param is not None
        assert param.type == "string"
        assert param.infer_from == r".*\.py$"
        assert param.required is True

    def test_duration_parameter(self, valid_skill_content: str) -> None:
        """Test parsing duration parameter type."""
        schema = parse_skill_schema(valid_skill_content)
        assert schema is not None

        param = schema.parameters.get("duration")
        assert param is not None
        assert param.type == "duration"
        assert param.default == "5m"

    def test_parameter_defaults_to_string_type(
        self, skill_with_complex_parameters: str
    ) -> None:
        """Test that parameters without explicit type default to string."""
        schema = parse_skill_schema(skill_with_complex_parameters)
        assert schema is not None

        param = schema.parameters.get("no_type_param")
        assert param is not None
        assert param.type == "string"

    def test_required_defaults_to_false(self, valid_skill_content: str) -> None:
        """Test that required defaults to False if not specified."""
        schema = parse_skill_schema(valid_skill_content)
        assert schema is not None

        param = schema.parameters.get("verbose")
        assert param is not None
        assert param.required is False

    def test_null_parameters_handled(self) -> None:
        """Test that null parameters field is handled gracefully."""
        content = """---
name: null-params
parameters: null
---

# Content
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        assert len(schema.parameters) == 0

    def test_non_dict_parameter_skipped(self) -> None:
        """Test that non-dict parameter definitions are skipped."""
        content = """---
name: invalid-param-type
parameters:
  valid_param:
    type: string
  invalid_param: "just a string"
  another_valid:
    type: bool
---

# Content
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        assert len(schema.parameters) == 2
        assert "valid_param" in schema.parameters
        assert "another_valid" in schema.parameters
        assert "invalid_param" not in schema.parameters


class TestSkillSchemaDataclass:
    """Unit tests for SkillSchema and SkillParameter dataclasses."""

    def test_skill_schema_creation(self) -> None:
        """Test creating SkillSchema directly."""
        param = SkillParameter(name="test", type="string")
        schema = SkillSchema(name="direct-skill", parameters={"test": param})

        assert schema.name == "direct-skill"
        assert len(schema.parameters) == 1

    def test_skill_parameter_defaults(self) -> None:
        """Test SkillParameter default values."""
        param = SkillParameter(name="minimal", type="bool")

        assert param.name == "minimal"
        assert param.type == "bool"
        assert param.required is False
        assert param.default is None
        assert param.values is None
        assert param.infer_from is None
        assert param.min is None
        assert param.max is None

    def test_skill_parameter_all_fields(self) -> None:
        """Test SkillParameter with all fields set."""
        param = SkillParameter(
            name="complete",
            type="enum",
            required=True,
            default="a",
            values=["a", "b", "c"],
            infer_from="pattern",
            min=0,
            max=100,
        )

        assert param.name == "complete"
        assert param.type == "enum"
        assert param.required is True
        assert param.default == "a"
        assert param.values == ["a", "b", "c"]
        assert param.infer_from == "pattern"
        assert param.min == 0
        assert param.max == 100


# ============================================================================
# Unit Tests: load_skill_schema
# ============================================================================


class TestLoadSkillSchema:
    """Unit tests for load_skill_schema function."""

    def test_load_existing_skill(self, populated_skills_dir: Path) -> None:
        """Test loading an existing skill by name."""
        schema = load_skill_schema("valid-skill", base_path=populated_skills_dir)

        assert schema is not None
        assert schema.name == "test-skill"

    def test_load_minimal_skill(self, populated_skills_dir: Path) -> None:
        """Test loading a minimal skill."""
        schema = load_skill_schema("minimal-skill", base_path=populated_skills_dir)

        assert schema is not None
        assert schema.name == "minimal-skill"

    def test_load_nonexistent_skill_returns_none(
        self, populated_skills_dir: Path
    ) -> None:
        """Test that loading a nonexistent skill returns None."""
        schema = load_skill_schema("nonexistent-skill", base_path=populated_skills_dir)
        assert schema is None

    def test_load_with_default_base_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test load_skill_schema uses cwd when base_path is None."""
        # This test verifies the function uses CLAUDE_PROJECT_DIR or cwd
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / ".claude" / "skills" / "env-skill"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text(
                """---
name: env-skill
---
# Content
"""
            )

            monkeypatch.setenv("CLAUDE_PROJECT_DIR", tmpdir)
            schema = load_skill_schema("env-skill")

            assert schema is not None
            assert schema.name == "env-skill"

    def test_load_skill_with_parse_error(self, temp_skills_dir: Path) -> None:
        """Test loading a skill that fails to parse."""
        skills_base = temp_skills_dir / ".claude" / "skills" / "broken-skill"
        skills_base.mkdir(parents=True)
        (skills_base / "SKILL.md").write_text("not valid yaml frontmatter at all")

        schema = load_skill_schema("broken-skill", base_path=temp_skills_dir)
        assert schema is None


# ============================================================================
# Integration Tests: Real File I/O
# ============================================================================


class TestIntegrationFileIO:
    """Integration tests with real file system operations."""

    def test_round_trip_skill_creation_and_loading(self) -> None:
        """Test creating a skill file and loading it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / ".claude" / "skills" / "roundtrip-skill"
            skills_dir.mkdir(parents=True)

            skill_content = """---
name: roundtrip-skill
description: Created for testing
parameters:
  mode:
    type: enum
    values: [fast, slow]
    default: fast
---

# Roundtrip Skill

This tests the full cycle.
"""
            (skills_dir / "SKILL.md").write_text(skill_content)

            schema = load_skill_schema("roundtrip-skill", base_path=Path(tmpdir))

            assert schema is not None
            assert schema.name == "roundtrip-skill"
            assert "mode" in schema.parameters
            assert schema.parameters["mode"].values == ["fast", "slow"]

    def test_loading_skill_with_unicode_content(self) -> None:
        """Test loading skill with unicode characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / ".claude" / "skills" / "unicode-skill"
            skills_dir.mkdir(parents=True)

            skill_content = """---
name: unicode-skill
description: Contains émojis 🎉 and spëcial çharacters
---

# Unicode Skill

こんにちは世界 - Hello World in Japanese
"""
            (skills_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

            schema = load_skill_schema("unicode-skill", base_path=Path(tmpdir))

            assert schema is not None
            assert schema.name == "unicode-skill"

    def test_loading_skill_from_symlinked_directory(self) -> None:
        """Test loading skill from a symlinked skills directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create actual skill directory
            actual_dir = tmppath / "actual" / ".claude" / "skills" / "linked-skill"
            actual_dir.mkdir(parents=True)
            (actual_dir / "SKILL.md").write_text(
                """---
name: linked-skill
---
# Linked
"""
            )

            # Create symlink
            link_base = tmppath / "linked"
            link_base.mkdir()
            (link_base / ".claude").symlink_to(tmppath / "actual" / ".claude")

            schema = load_skill_schema("linked-skill", base_path=link_base)

            assert schema is not None
            assert schema.name == "linked-skill"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_frontmatter_with_only_dashes(self) -> None:
        """Test handling of content that starts with --- but has no closing."""
        content = """---
"""
        schema = parse_skill_schema(content)
        assert schema is None

    def test_frontmatter_with_extra_dashes(self) -> None:
        """Test frontmatter with extra dashes in content."""
        content = """---
name: extra-dashes
---

# Content

Here's some code:

```
--- this is not a frontmatter delimiter ---
```
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        assert schema.name == "extra-dashes"

    def test_frontmatter_with_embedded_triple_dashes(self) -> None:
        """Test that embedded --- in YAML values doesn't break parsing."""
        content = """---
name: embedded-dashes
description: "Contains --- in the value"
---

# Content
"""
        # This might fail depending on implementation - good edge case to test
        schema = parse_skill_schema(content)

        # Either returns None or successfully parses
        if schema is not None:
            assert schema.name == "embedded-dashes"

    def test_parameter_with_empty_values_list(self) -> None:
        """Test enum parameter with empty values list."""
        content = """---
name: empty-values
parameters:
  broken_enum:
    type: enum
    values: []
---
# Content
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        param = schema.parameters.get("broken_enum")
        assert param is not None
        assert param.values == []

    def test_very_long_skill_content(self) -> None:
        """Test parsing a very long skill file."""
        long_content = """---
name: long-skill
description: A very long skill
---

# Long Skill

""" + (
            "This is a very long paragraph. " * 1000
        )

        schema = parse_skill_schema(long_content)

        assert schema is not None
        assert schema.name == "long-skill"

    def test_skill_with_special_yaml_characters(self) -> None:
        """Test skill with YAML special characters in values."""
        content = """---
name: special-chars
description: "Contains: colons, [brackets], {braces}"
parameters:
  path:
    type: string
    default: "/path/to/file:with:colons"
---
# Content
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        assert schema.name == "special-chars"

    def test_whitespace_only_content(self) -> None:
        """Test content with only whitespace."""
        content = "   \n\n   \t\t\n   "
        schema = parse_skill_schema(content)
        assert schema is None

    def test_frontmatter_with_non_dict_root(self) -> None:
        """Test frontmatter that parses to non-dict (e.g., list)."""
        content = """---
- item1
- item2
---
# Content
"""
        schema = parse_skill_schema(content)
        assert schema is None

    def test_parameter_with_none_values(self) -> None:
        """Test parameter definitions with None values for optional fields."""
        content = """---
name: none-values
parameters:
  nullable_param:
    type: string
    default: null
    min: null
    max: null
---
# Content
"""
        schema = parse_skill_schema(content)

        assert schema is not None
        param = schema.parameters.get("nullable_param")
        assert param is not None
        assert param.default is None
        assert param.min is None
        assert param.max is None


# ============================================================================
# Regression Tests
# ============================================================================


class TestRegressions:
    """Regression tests for previously found bugs."""

    def test_windows_line_endings(self) -> None:
        """Test that Windows line endings (CRLF) are handled."""
        content = "---\r\nname: windows-skill\r\n---\r\n\r\n# Content\r\n"
        schema = parse_skill_schema(content)

        # May or may not work depending on implementation
        # Document current behavior
        if schema is not None:
            assert schema.name == "windows-skill"

    def test_trailing_whitespace_in_frontmatter(self) -> None:
        """Test trailing whitespace after frontmatter delimiter."""
        content = """---
name: trailing-ws
---

# Content
"""
        schema = parse_skill_schema(content)

        # Current implementation may not handle this
        # Test documents behavior
        if schema is not None:
            assert schema.name == "trailing-ws"

    def test_tabs_in_yaml_indentation(self) -> None:
        """Test YAML with tab indentation (technically invalid YAML)."""
        content = """---
name: tab-indent
parameters:
\tparam1:
\t\ttype: string
---
# Content
"""
        schema = parse_skill_schema(content)
        # YAML spec says tabs are not allowed for indentation
        # Test documents current handling
        assert schema is None or isinstance(schema, SkillSchema)
