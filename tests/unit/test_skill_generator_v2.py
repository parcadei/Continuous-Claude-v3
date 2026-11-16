"""Tests for Skill Generator V2 - 3-mode generation with parity verification.

TDD: Write failing tests first, then implement to pass.

Modes:
- CREATE: Generate new typed skill from scratch (research or interview)
- CONVERT: Convert existing prose skill to typed schema
- ENHANCE: Add/refine params on existing skill
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from scripts.skill_generator_v2 import (
    create_skill,
    convert_skill,
    enhance_skill,
    CreationMode,
    SkillGenerationResult,
)


class TestCreateSkill:
    """Tests for CREATE mode skill generation."""

    @pytest.mark.asyncio
    async def test_create_via_research_returns_result(self):
        """CREATE mode with research should return SkillGenerationResult."""
        mock_research = [
            {"content": "Use async/await for GraphQL resolvers"},
            {"content": "Schema-first design recommended"},
            {"content": "Consider pagination for list queries"}
        ]

        with patch(
            'scripts.skill_generator_v2._do_research',
            new_callable=AsyncMock,
            return_value=mock_research
        ), patch(
            'scripts.skill_generator_v2._generate_schema_from_research',
            new_callable=AsyncMock,
            return_value={
                "name": "graphql-api-generator",
                "parameters": {
                    "schema_format": {"type": "enum", "values": ["SDL", "code-first"]}
                }
            }
        ):
            result = await create_skill(
                prompt="Build a GraphQL API generator skill",
                mode=CreationMode.RESEARCH
            )

        assert result is not None
        assert result.schema is not None
        assert "parameters" in result.schema
        assert len(result.research_sources) >= 1

    @pytest.mark.asyncio
    async def test_create_via_interview_uses_answers(self):
        """CREATE mode with interview should use provided answers."""
        answers = {
            "schema_format": "SDL",
            "include_resolvers": True
        }

        with patch(
            'scripts.skill_generator_v2._generate_schema_from_interview',
            new_callable=AsyncMock,
            return_value={
                "name": "graphql-skill",
                "parameters": {
                    "schema_format": {"type": "enum", "values": ["SDL"], "default": "SDL"},
                    "include_resolvers": {"type": "bool", "default": True}
                }
            }
        ):
            result = await create_skill(
                prompt="Build a GraphQL skill",
                mode=CreationMode.INTERVIEW,
                interview_answers=answers
            )

        assert result.schema["parameters"]["schema_format"]["default"] == "SDL"
        assert result.schema["parameters"]["include_resolvers"]["default"] is True

    @pytest.mark.asyncio
    async def test_create_generates_valid_yaml(self):
        """CREATE mode should produce parseable YAML."""
        with patch(
            'scripts.skill_generator_v2._do_research',
            new_callable=AsyncMock,
            return_value=[]
        ), patch(
            'scripts.skill_generator_v2._generate_schema_from_research',
            new_callable=AsyncMock,
            return_value={
                "name": "test-skill",
                "parameters": {"x": {"type": "string"}}
            }
        ):
            result = await create_skill(
                prompt="Test skill",
                mode=CreationMode.RESEARCH
            )

        # YAML should be non-empty and contain frontmatter
        assert result.yaml_content
        assert "---" in result.yaml_content
        assert "name:" in result.yaml_content


class TestConvertSkill:
    """Tests for CONVERT mode."""

    @pytest.mark.asyncio
    async def test_convert_extracts_params(self):
        """CONVERT mode should extract params from prose."""
        skill_prose = """---
name: debug
description: Debug issues
---
# Debug

You debug by checking logs and database state.
Use JWT or OAuth for authentication.
"""
        mock_prose_eqx = {
            "parameters": {
                "log_location": {"type": "string"},
                "auth_method": {"type": "enum", "values": ["JWT", "OAuth"]}
            },
            "unknowns": {"log_location": "UNKNOWN"},
            "z3_checkable": ["auth_method"]
        }

        with patch(
            'scripts.skill_generator_v2._read_skill_file',
            return_value=skill_prose
        ), patch(
            'scripts.skill_prose_extractor.extract_eqx_from_prose',
            new_callable=AsyncMock,
            return_value=mock_prose_eqx
        ):
            result = await convert_skill(".claude/skills/debug")

        assert "log_location" in result.schema["parameters"]
        assert "auth_method" in result.schema["parameters"]

    @pytest.mark.asyncio
    async def test_convert_includes_parity_result(self):
        """CONVERT mode should include parity verification."""
        skill_prose = """---
name: test
---
# Test
Simple skill.
"""
        mock_prose_eqx = {
            "parameters": {"x": {"type": "string"}},
            "unknowns": {},
            "z3_checkable": []
        }

        with patch(
            'scripts.skill_generator_v2._read_skill_file',
            return_value=skill_prose
        ), patch(
            'scripts.skill_prose_extractor.extract_eqx_from_prose',
            new_callable=AsyncMock,
            return_value=mock_prose_eqx
        ):
            result = await convert_skill(".claude/skills/test")

        assert result.parity_result is not None
        # Perfect parity expected when schema matches prose extraction
        assert result.parity_result.coverage_score == 1.0

    @pytest.mark.asyncio
    async def test_convert_preserves_name(self):
        """CONVERT should keep original skill name."""
        skill_prose = """---
name: my-original-skill
description: Original description
---
# My Skill
Content here.
"""
        mock_prose_eqx = {
            "parameters": {},
            "unknowns": {},
            "z3_checkable": []
        }

        with patch(
            'scripts.skill_generator_v2._read_skill_file',
            return_value=skill_prose
        ), patch(
            'scripts.skill_prose_extractor.extract_eqx_from_prose',
            new_callable=AsyncMock,
            return_value=mock_prose_eqx
        ):
            result = await convert_skill(".claude/skills/my-skill")

        assert result.schema["name"] == "my-original-skill"


class TestEnhanceSkill:
    """Tests for ENHANCE mode."""

    @pytest.mark.asyncio
    async def test_enhance_adds_param(self):
        """ENHANCE mode should add new parameters."""
        skill_prose = """---
name: debug
---
# Debug
Debug skill.
"""
        mock_prose_eqx = {
            "parameters": {"existing_param": {"type": "string"}},
            "unknowns": {},
            "z3_checkable": []
        }

        new_params = {
            "verbose": {"type": "bool", "default": False, "description": "Verbose output"}
        }

        with patch(
            'scripts.skill_generator_v2._read_skill_file',
            return_value=skill_prose
        ), patch(
            'scripts.skill_prose_extractor.extract_eqx_from_prose',
            new_callable=AsyncMock,
            return_value=mock_prose_eqx
        ):
            result = await enhance_skill(".claude/skills/debug", new_params)

        assert "verbose" in result.schema["parameters"]
        assert "existing_param" in result.schema["parameters"]

    @pytest.mark.asyncio
    async def test_enhance_preserves_existing(self):
        """ENHANCE mode should preserve existing parameters."""
        skill_prose = """---
name: debug
---
# Debug
"""
        mock_prose_eqx = {
            "parameters": {
                "log_level": {"type": "enum", "values": ["debug", "info", "warn"]},
                "timeout": {"type": "int", "default": 30}
            },
            "unknowns": {},
            "z3_checkable": ["log_level"]
        }

        new_params = {
            "new_param": {"type": "string"}
        }

        with patch(
            'scripts.skill_generator_v2._read_skill_file',
            return_value=skill_prose
        ), patch(
            'scripts.skill_prose_extractor.extract_eqx_from_prose',
            new_callable=AsyncMock,
            return_value=mock_prose_eqx
        ):
            result = await enhance_skill(".claude/skills/debug", new_params)

        # Should have original + new
        assert "log_level" in result.schema["parameters"]
        assert "timeout" in result.schema["parameters"]
        assert "new_param" in result.schema["parameters"]
        assert len(result.schema["parameters"]) == 3

    @pytest.mark.asyncio
    async def test_enhance_can_override_param(self):
        """ENHANCE mode should allow overriding existing param definitions."""
        skill_prose = """---
name: test
---
"""
        mock_prose_eqx = {
            "parameters": {
                "timeout": {"type": "int", "default": 30}
            },
            "unknowns": {},
            "z3_checkable": []
        }

        # Override timeout with new definition
        new_params = {
            "timeout": {"type": "int", "default": 60, "min": 1, "max": 300}
        }

        with patch(
            'scripts.skill_generator_v2._read_skill_file',
            return_value=skill_prose
        ), patch(
            'scripts.skill_prose_extractor.extract_eqx_from_prose',
            new_callable=AsyncMock,
            return_value=mock_prose_eqx
        ):
            result = await enhance_skill(".claude/skills/test", new_params)

        # New definition should take precedence
        assert result.schema["parameters"]["timeout"]["default"] == 60
        assert result.schema["parameters"]["timeout"]["max"] == 300


class TestSkillGenerationResult:
    """Tests for SkillGenerationResult dataclass."""

    def test_result_has_required_fields(self):
        """Result should have all required fields."""
        from scripts.skill_parity_checker import ParityResult

        parity = ParityResult(
            prose_only=[],
            schema_only=[],
            coverage_score=1.0,
            gaps=[],
            resolved_unknowns=[]
        )

        result = SkillGenerationResult(
            schema={"name": "test", "parameters": {}},
            yaml_content="---\nname: test\n---",
            research_sources=[],
            parity_result=parity
        )

        assert result.schema is not None
        assert result.yaml_content is not None
        assert result.research_sources is not None
        assert result.parity_result is not None


class TestCreationMode:
    """Tests for CreationMode enum."""

    def test_research_mode(self):
        """RESEARCH mode value."""
        assert CreationMode.RESEARCH.value == "research"

    def test_interview_mode(self):
        """INTERVIEW mode value."""
        assert CreationMode.INTERVIEW.value == "interview"


class TestYAMLGeneration:
    """Tests for YAML output generation."""

    @pytest.mark.asyncio
    async def test_yaml_includes_parameters(self):
        """Generated YAML should include typed parameters."""
        with patch(
            'scripts.skill_generator_v2._do_research',
            new_callable=AsyncMock,
            return_value=[]
        ), patch(
            'scripts.skill_generator_v2._generate_schema_from_research',
            new_callable=AsyncMock,
            return_value={
                "name": "test",
                "parameters": {
                    "auth": {"type": "enum", "values": ["JWT", "OAuth"], "required": True}
                }
            }
        ):
            result = await create_skill("test", mode=CreationMode.RESEARCH)

        # YAML should contain parameters section
        assert "parameters:" in result.yaml_content
        assert "auth:" in result.yaml_content
        assert "type: enum" in result.yaml_content

    @pytest.mark.asyncio
    async def test_yaml_is_parseable(self):
        """Generated YAML should be parseable."""
        import yaml

        with patch(
            'scripts.skill_generator_v2._do_research',
            new_callable=AsyncMock,
            return_value=[]
        ), patch(
            'scripts.skill_generator_v2._generate_schema_from_research',
            new_callable=AsyncMock,
            return_value={
                "name": "parseable-skill",
                "description": "A skill",
                "parameters": {"x": {"type": "string"}}
            }
        ):
            result = await create_skill("test", mode=CreationMode.RESEARCH)

        # Extract frontmatter and parse
        yaml_content = result.yaml_content
        if yaml_content.startswith("---"):
            parts = yaml_content.split("---", 2)
            if len(parts) >= 2:
                frontmatter = parts[1]
                parsed = yaml.safe_load(frontmatter)
                assert parsed["name"] == "parseable-skill"
