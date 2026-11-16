"""
Tests for erotetic skill integration (typed skill parameters with Z3 checking).
TDD: These tests are written BEFORE implementation.
"""
import pytest
import subprocess
import json
from pathlib import Path


def test_erotetic_with_typed_skill(tmp_path):
    """Hook uses skill-specific parameters when skill has typed params."""
    # Create a skill with typed params
    skill_dir = tmp_path / ".claude" / "skills" / "deploy-api"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: deploy-api
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp]
    infer_from: "vercel|aws|gcp"
  database:
    type: enum
    values: [postgres, mysql, sqlite]
    infer_from: "postgres|mysql|sqlite"
---
# Deploy API
'''
    )

    # Call the integrated erotetic flow using Python direct import
    # This tests the integration of skill_loader + extractor + z3_erotetic
    from scripts.skill_loader import load_skill_schema
    from scripts.skill_extractor import extract_skill_values
    from scripts.z3_erotetic import check_evocation

    schema = load_skill_schema("deploy-api", base_path=tmp_path)
    assert schema is not None

    prompt = "Deploy my FastAPI app to AWS"
    propositions = extract_skill_values(prompt, schema)
    result = check_evocation(propositions)

    assert result["isEmpty"] == False
    assert "database" in result["unknowns"]
    assert "hosting" not in result["unknowns"]  # "aws" was extracted


def test_erotetic_fallback_no_typed_params(tmp_path):
    """Falls back to empty extraction when skill has no typed params."""
    skill_dir = tmp_path / ".claude" / "skills" / "simple"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: simple
description: No params
---
'''
    )

    from scripts.skill_loader import load_skill_schema
    from scripts.skill_extractor import extract_skill_values
    from scripts.z3_erotetic import check_evocation

    schema = load_skill_schema("simple", base_path=tmp_path)
    assert schema is not None
    assert schema.parameters == {}

    prompt = "Build an API with JWT auth"
    propositions = extract_skill_values(prompt, schema)
    result = check_evocation(propositions)

    # No typed params means no unknowns from this skill
    assert result["isEmpty"] == True
    assert result["unknowns"] == []


def test_full_params_means_empty_evocation(tmp_path):
    """E(X,Q) is empty when all parameters are known."""
    skill_dir = tmp_path / ".claude" / "skills" / "deploy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: deploy
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp]
    infer_from: "vercel|aws|gcp"
  database:
    type: enum
    values: [postgres, mysql, sqlite]
    infer_from: "postgres|mysql|sqlite"
---
'''
    )

    from scripts.skill_loader import load_skill_schema
    from scripts.skill_extractor import extract_skill_values
    from scripts.z3_erotetic import check_evocation

    schema = load_skill_schema("deploy", base_path=tmp_path)
    prompt = "Deploy to AWS with postgres database"
    propositions = extract_skill_values(prompt, schema)
    result = check_evocation(propositions)

    # Both params extracted - E(X,Q) should be empty
    assert result["isEmpty"] == True
    assert result["unknowns"] == []


def test_partial_params_lists_unknowns(tmp_path):
    """E(X,Q) lists unknowns when some parameters are missing."""
    skill_dir = tmp_path / ".claude" / "skills" / "multi"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: multi
parameters:
  hosting:
    type: enum
    values: [vercel, aws]
    infer_from: "vercel|aws"
  database:
    type: enum
    values: [postgres, mysql]
    infer_from: "postgres|mysql"
  framework:
    type: enum
    values: [fastapi, django]
    infer_from: "fastapi|django"
---
'''
    )

    from scripts.skill_loader import load_skill_schema
    from scripts.skill_extractor import extract_skill_values
    from scripts.z3_erotetic import check_evocation

    schema = load_skill_schema("multi", base_path=tmp_path)
    prompt = "Deploy my fastapi app to aws"
    propositions = extract_skill_values(prompt, schema)
    result = check_evocation(propositions)

    # Only database is unknown
    assert result["isEmpty"] == False
    assert result["count"] == 1
    assert "database" in result["unknowns"]
    assert "hosting" not in result["unknowns"]
    assert "framework" not in result["unknowns"]


def test_default_values_reduce_unknowns(tmp_path):
    """Parameters with defaults don't count as unknowns."""
    skill_dir = tmp_path / ".claude" / "skills" / "defaults"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: defaults
parameters:
  required_param:
    type: enum
    values: [a, b]
    infer_from: "\\ba\\b|\\bb\\b"
  optional_param:
    type: bool
    default: false
---
'''
    )

    from scripts.skill_loader import load_skill_schema
    from scripts.skill_extractor import extract_skill_values
    from scripts.z3_erotetic import check_evocation

    schema = load_skill_schema("defaults", base_path=tmp_path)
    prompt = "Do something"  # Neither param mentioned
    propositions = extract_skill_values(prompt, schema)
    result = check_evocation(propositions)

    # Only required_param is unknown (optional_param has default)
    assert result["count"] == 1
    assert "required_param" in result["unknowns"]
    assert "optional_param" not in result["unknowns"]
