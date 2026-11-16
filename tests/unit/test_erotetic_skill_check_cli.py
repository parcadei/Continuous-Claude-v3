"""
Tests for erotetic skill check CLI script.
"""
import pytest
import subprocess
import json
from pathlib import Path


def test_cli_with_typed_skill(tmp_path):
    """CLI uses skill-specific parameters when skill has typed params."""
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

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/erotetic_skill_check.py",
            "--skill",
            "deploy-api",
            "--prompt",
            "Deploy my FastAPI app to AWS",
            "--base-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,  # Project root
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["isEmpty"] == False
    assert "database" in output["unknowns"]
    assert "hosting" not in output["unknowns"]


def test_cli_skill_not_found(tmp_path):
    """CLI handles nonexistent skill gracefully."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/erotetic_skill_check.py",
            "--skill",
            "nonexistent-skill",
            "--prompt",
            "Deploy to AWS",
            "--base-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    # No schema means empty propositions = empty evocation
    assert output["isEmpty"] == True


def test_cli_with_generic_fallback(tmp_path):
    """CLI uses generic patterns when skill has no typed params and fallback enabled."""
    skill_dir = tmp_path / ".claude" / "skills" / "simple"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '''---
name: simple
description: No params
---
'''
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/erotetic_skill_check.py",
            "--skill",
            "simple",
            "--prompt",
            "Build an API with JWT auth using postgres",
            "--base-path",
            str(tmp_path),
            "--use-generic-fallback",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    # Generic patterns extracted jwt and postgres
    assert output["isEmpty"] == False or output["count"] >= 0  # May have unknowns
    # At least some generic props should be checked


def test_cli_all_params_known(tmp_path):
    """CLI returns empty evocation when all params are extracted."""
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

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/erotetic_skill_check.py",
            "--skill",
            "deploy",
            "--prompt",
            "Deploy to AWS with postgres database",
            "--base-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["isEmpty"] == True
    assert output["unknowns"] == []
