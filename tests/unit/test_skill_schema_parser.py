"""
Tests for skill schema parser.
TDD: These tests are written BEFORE implementation.
"""
import pytest


def test_parse_enum_parameter():
    """Enum parameter with values and infer_from pattern."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = '''---
name: deploy-api
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp]
    required: true
    infer_from: "vercel|aws|gcp"
---
# Deploy API
'''
    schema = parse_skill_schema(skill_md)
    assert schema.name == "deploy-api"
    assert len(schema.parameters) == 1
    assert schema.parameters["hosting"].type == "enum"
    assert schema.parameters["hosting"].values == ["vercel", "aws", "gcp"]
    assert schema.parameters["hosting"].infer_from == "vercel|aws|gcp"


def test_parse_bool_parameter():
    """Boolean parameter with default."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = '''---
name: test-runner
parameters:
  verbose:
    type: bool
    default: false
---
'''
    schema = parse_skill_schema(skill_md)
    assert schema.parameters["verbose"].type == "bool"
    assert schema.parameters["verbose"].default == False


def test_parse_duration_parameter():
    """Duration with min/max constraints."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = '''---
name: rate-limiter
parameters:
  timeout:
    type: duration
    default: 30s
    min: 1s
    max: 5m
---
'''
    schema = parse_skill_schema(skill_md)
    assert schema.parameters["timeout"].type == "duration"
    assert schema.parameters["timeout"].default == "30s"


def test_skill_without_parameters():
    """Skills without parameters return empty schema."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = '''---
name: simple-skill
description: No params
---
'''
    schema = parse_skill_schema(skill_md)
    assert schema.parameters == {}


def test_malformed_yaml_returns_none():
    """Invalid YAML returns None, not crash."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = "not yaml at all"
    schema = parse_skill_schema(skill_md)
    assert schema is None


def test_parse_required_parameter():
    """Required parameter is parsed correctly."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = '''---
name: deploy
parameters:
  target:
    type: enum
    values: [prod, staging]
    required: true
---
'''
    schema = parse_skill_schema(skill_md)
    assert schema.parameters["target"].required == True


def test_parse_multiple_parameters():
    """Multiple parameters are parsed correctly."""
    from scripts.skill_schema_parser import parse_skill_schema

    skill_md = '''---
name: full-skill
parameters:
  env:
    type: enum
    values: [dev, staging, prod]
  verbose:
    type: bool
    default: false
  timeout:
    type: duration
    default: 30s
---
'''
    schema = parse_skill_schema(skill_md)
    assert len(schema.parameters) == 3
    assert "env" in schema.parameters
    assert "verbose" in schema.parameters
    assert "timeout" in schema.parameters
