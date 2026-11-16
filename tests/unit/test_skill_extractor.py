"""
Tests for skill value extractor.
TDD: These tests are written BEFORE implementation.
"""
import pytest
from scripts.skill_schema_parser import SkillSchema, SkillParameter


def test_extract_enum_value():
    """Extract enum value from prompt using infer_from pattern."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(
        name="deploy",
        parameters={
            "hosting": SkillParameter(
                name="hosting",
                type="enum",
                values=["vercel", "aws", "gcp"],
                infer_from=r"vercel|aws|gcp",
            )
        },
    )
    prompt = "Deploy my app to AWS with auto-scaling"
    result = extract_skill_values(prompt, schema)
    assert result["hosting"] == "aws"


def test_extract_bool_value():
    """Extract boolean from prompt."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(
        name="test",
        parameters={
            "verbose": SkillParameter(
                name="verbose",
                type="bool",
                infer_from=r"\b(verbose|quiet)\b",
            )
        },
    )
    prompt = "Run tests in verbose mode"
    result = extract_skill_values(prompt, schema)
    assert result["verbose"] == "verbose"


def test_missing_value_returns_unknown():
    """Parameters not found in prompt return UNKNOWN."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(
        name="deploy",
        parameters={
            "hosting": SkillParameter(
                name="hosting",
                type="enum",
                values=["vercel", "aws"],
                infer_from=r"vercel|aws",
            ),
            "region": SkillParameter(
                name="region",
                type="enum",
                values=["us-east", "eu-west"],
                infer_from=r"us-east|eu-west",
            ),
        },
    )
    prompt = "Deploy to AWS"
    result = extract_skill_values(prompt, schema)
    assert result["hosting"] == "aws"
    assert result["region"] == "UNKNOWN"


def test_default_value_when_not_found():
    """Use default if param has one and not found."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(
        name="test",
        parameters={
            "timeout": SkillParameter(
                name="timeout",
                type="duration",
                default="30s",
                infer_from=r"\d+[smh]",
            )
        },
    )
    prompt = "Run tests"
    result = extract_skill_values(prompt, schema)
    assert result["timeout"] == "30s"


def test_no_infer_from_uses_values_as_pattern():
    """If no infer_from, build pattern from values list."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(
        name="deploy",
        parameters={
            "env": SkillParameter(
                name="env",
                type="enum",
                values=["prod", "staging", "dev"],
            )
        },
    )
    prompt = "Deploy to staging"
    result = extract_skill_values(prompt, schema)
    assert result["env"] == "staging"


def test_case_insensitive_matching():
    """Matching should be case insensitive."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(
        name="deploy",
        parameters={
            "hosting": SkillParameter(
                name="hosting",
                type="enum",
                values=["vercel", "aws", "gcp"],
                infer_from=r"vercel|aws|gcp",
            )
        },
    )
    prompt = "Deploy my app to AWS"
    result = extract_skill_values(prompt, schema)
    assert result["hosting"] == "aws"


def test_empty_schema_returns_empty_dict():
    """Schema with no parameters returns empty dict."""
    from scripts.skill_extractor import extract_skill_values

    schema = SkillSchema(name="simple", parameters={})
    prompt = "Do something"
    result = extract_skill_values(prompt, schema)
    assert result == {}
