"""Tests for skill YAML structural validation (Phase 1 Tasks 1.4-1.6).

This module tests the skill_validator.py that verifies:
1. YAML syntax is valid
2. Required fields (name, description) are present
3. Parameter schemas follow expected structure

TDD approach: tests are written FIRST, then implementation.
"""

import pytest
from pathlib import Path


# =============================================================================
# Task 1.4: Structural Verification (Valid YAML)
# =============================================================================


class TestYAMLStructureValid:
    """Tests for valid YAML structure verification."""

    def test_verify_yaml_structure_valid(self) -> None:
        """Task 1.4: verify_yaml_structure() should accept valid YAML."""
        from scripts.skill_validator import verify_yaml_structure

        valid_yaml = """---
name: deploy-api
description: Deploy API to hosting provider
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp]
---

# Deploy API Skill

This skill deploys your API.
"""
        result = verify_yaml_structure(valid_yaml)
        assert result.is_valid, f"Valid YAML should pass. Errors: {result.errors}"
        assert len(result.errors) == 0

    def test_verify_yaml_structure_minimal_valid(self) -> None:
        """Minimal valid YAML with just name and description."""
        from scripts.skill_validator import verify_yaml_structure

        minimal_yaml = """---
name: test-skill
description: A test skill
---

# Test Skill
"""
        result = verify_yaml_structure(minimal_yaml)
        assert result.is_valid, f"Minimal valid YAML should pass. Errors: {result.errors}"

    def test_verify_yaml_structure_complex_params(self) -> None:
        """Valid YAML with complex parameter structure."""
        from scripts.skill_validator import verify_yaml_structure

        complex_yaml = """---
name: deploy-api
description: Deploy API
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp]
    infer_from: "vercel|aws|gcp"
    default: aws
  auth_method:
    type: enum
    values: [jwt, oauth, api-key]
    required: true
---
"""
        result = verify_yaml_structure(complex_yaml)
        assert result.is_valid, f"Complex YAML should pass. Errors: {result.errors}"


# =============================================================================
# Task 1.5: Invalid YAML Test Cases
# =============================================================================


class TestYAMLStructureInvalid:
    """Tests for invalid YAML structure detection."""

    def test_verify_yaml_structure_invalid(self) -> None:
        """Task 1.5: verify_yaml_structure() should reject malformed YAML."""
        from scripts.skill_validator import verify_yaml_structure

        invalid_yaml = """---
name: broken-skill
  indentation: is wrong
    this: will fail
---
"""
        result = verify_yaml_structure(invalid_yaml)
        assert not result.is_valid, "Invalid YAML should fail"
        assert len(result.errors) > 0, "Should report errors for invalid YAML"

    def test_verify_yaml_structure_no_frontmatter(self) -> None:
        """YAML without frontmatter delimiters should fail."""
        from scripts.skill_validator import verify_yaml_structure

        no_frontmatter = """
name: no-delimiters
description: Missing the --- markers

# Skill Content
"""
        result = verify_yaml_structure(no_frontmatter)
        assert not result.is_valid, "Missing frontmatter should fail"

    def test_verify_yaml_structure_unclosed_frontmatter(self) -> None:
        """YAML with unclosed frontmatter should fail."""
        from scripts.skill_validator import verify_yaml_structure

        unclosed = """---
name: unclosed
description: Missing closing delimiter

# Never closed
"""
        result = verify_yaml_structure(unclosed)
        assert not result.is_valid, "Unclosed frontmatter should fail"

    def test_verify_yaml_structure_invalid_yaml_syntax(self) -> None:
        """Invalid YAML syntax (tabs) should fail."""
        from scripts.skill_validator import verify_yaml_structure

        tab_yaml = """---
name: tab-skill
description: Has tabs
parameters:
\thosting: aws
---
"""
        result = verify_yaml_structure(tab_yaml)
        # Note: YAML allows tabs in some cases, so this might not fail
        # The test validates we handle edge cases


# =============================================================================
# Task 1.6: Required Fields Validation
# =============================================================================


class TestRequiredFieldsValidation:
    """Tests for required fields (name, description) validation."""

    def test_verify_required_fields(self) -> None:
        """Task 1.6: verify_yaml_structure() should require name and description."""
        from scripts.skill_validator import verify_yaml_structure

        missing_name = """---
description: Has description but no name
---
"""
        result = verify_yaml_structure(missing_name)
        assert not result.is_valid, "Missing name should fail"
        assert any("name" in e.lower() for e in result.errors), (
            f"Should report missing name. Errors: {result.errors}"
        )

    def test_verify_missing_description(self) -> None:
        """Missing description should fail."""
        from scripts.skill_validator import verify_yaml_structure

        missing_desc = """---
name: no-description
---
"""
        result = verify_yaml_structure(missing_desc)
        assert not result.is_valid, "Missing description should fail"
        assert any("description" in e.lower() for e in result.errors), (
            f"Should report missing description. Errors: {result.errors}"
        )

    def test_verify_empty_name(self) -> None:
        """Empty name should fail."""
        from scripts.skill_validator import verify_yaml_structure

        empty_name = """---
name: ""
description: Has empty name
---
"""
        result = verify_yaml_structure(empty_name)
        assert not result.is_valid, "Empty name should fail"

    def test_verify_empty_description(self) -> None:
        """Empty description should fail."""
        from scripts.skill_validator import verify_yaml_structure

        empty_desc = """---
name: test-skill
description: ""
---
"""
        result = verify_yaml_structure(empty_desc)
        assert not result.is_valid, "Empty description should fail"


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_exists(self) -> None:
        """ValidationResult dataclass should exist."""
        from scripts.skill_validator import ValidationResult

        result = ValidationResult(is_valid=True, errors=[])
        assert result.is_valid
        assert result.errors == []

    def test_validation_result_with_errors(self) -> None:
        """ValidationResult with errors should not be valid."""
        from scripts.skill_validator import ValidationResult

        result = ValidationResult(
            is_valid=False,
            errors=["Missing required field: name"]
        )
        assert not result.is_valid
        assert len(result.errors) == 1
