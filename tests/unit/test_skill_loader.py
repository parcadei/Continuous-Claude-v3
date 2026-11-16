"""
Tests for skill schema loader.
TDD: These tests are written BEFORE implementation.
"""
import pytest
from pathlib import Path


def test_load_existing_skill(tmp_path):
    """Load schema from existing skill directory."""
    from scripts.skill_loader import load_skill_schema

    skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: test-skill
parameters:
  mode:
    type: enum
    values: [fast, slow]
---
# Test
'''
    )

    schema = load_skill_schema("test-skill", base_path=tmp_path)
    assert schema is not None
    assert schema.name == "test-skill"
    assert "mode" in schema.parameters


def test_load_nonexistent_skill(tmp_path):
    """Return None for skill that doesn't exist."""
    from scripts.skill_loader import load_skill_schema

    schema = load_skill_schema("nonexistent-skill-xyz", base_path=tmp_path)
    assert schema is None


def test_load_skill_without_params(tmp_path):
    """Skills without params return empty parameters."""
    from scripts.skill_loader import load_skill_schema

    skill_dir = tmp_path / ".claude" / "skills" / "simple"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: simple
description: No params
---
'''
    )

    schema = load_skill_schema("simple", base_path=tmp_path)
    assert schema is not None
    assert schema.parameters == {}


def test_load_skill_with_complex_params(tmp_path):
    """Load skill with multiple parameter types."""
    from scripts.skill_loader import load_skill_schema

    skill_dir = tmp_path / ".claude" / "skills" / "deploy-api"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: deploy-api
description: Deploy API to hosting provider
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp]
    required: true
    infer_from: "vercel|aws|gcp"
  verbose:
    type: bool
    default: false
  timeout:
    type: duration
    default: 30s
---
'''
    )

    schema = load_skill_schema("deploy-api", base_path=tmp_path)
    assert schema is not None
    assert len(schema.parameters) == 3
    assert schema.parameters["hosting"].required == True
    assert schema.parameters["verbose"].default == False
    assert schema.parameters["timeout"].default == "30s"


def test_load_skill_malformed_yaml(tmp_path):
    """Return None for skill with malformed YAML."""
    from scripts.skill_loader import load_skill_schema

    skill_dir = tmp_path / ".claude" / "skills" / "broken"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("not valid yaml at all")

    schema = load_skill_schema("broken", base_path=tmp_path)
    assert schema is None
