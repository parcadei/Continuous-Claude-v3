"""Tests for v6.0-hybrid skill validator.

TDD: These tests are written BEFORE implementation.
Run: uv run pytest tests/unit/test_validate_skill_v6.py -v
"""

import pytest
from pathlib import Path


class TestValidateSkillV6:
    """Tests for validate_skill_v6 function."""

    def test_import_validator_module(self):
        """Validator module should be importable."""
        from scripts.validate_skill_v6 import validate_skill_v6
        assert validate_skill_v6 is not None

    def test_valid_skill_passes_validation(self, tmp_path):
        """A valid v6.0-hybrid skill should pass validation."""
        from scripts.validate_skill_v6 import validate_skill_v6

        skill_content = '''---
name: test-skill
version: 6.0-hybrid
description: A test skill
---

# Option: test-skill

## I (Initiation)
activate: [trigger_condition]
skip: [anti_pattern]

## Y (Observation Space)
| signal | source | interpretation |
|--------|--------|----------------|
| input  | user   | goal           |

## U (Action Space)
primary: [Read, Bash]
forbidden: [Write]

## pi (Policy)

### P0: Start
```
eta |-> read_context if has_files
```

| action | Q | why | mitigation |
|--------|---|-----|------------|
| skip_read | -inf | Missing context | read first |

## beta (Termination)
```
beta(eta) = 1.0 if done
```
success: [goal_achieved]
failure: [abandoned]

## Output Schema
```yaml
sections: [summary]
```

## Invariants
```
inv_1: never skip_read
```
'''
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_content)

        result = validate_skill_v6(str(skill_path))
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_version_fails_validation(self, tmp_path):
        """Skill without version field should fail."""
        from scripts.validate_skill_v6 import validate_skill_v6

        skill_content = '''---
name: test-skill
description: A test skill
---
# No version field
'''
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_content)

        result = validate_skill_v6(str(skill_path))
        assert result.valid is False
        assert any("version" in e.lower() for e in result.errors)

    def test_wrong_version_fails_validation(self, tmp_path):
        """Skill with wrong version should fail."""
        from scripts.validate_skill_v6 import validate_skill_v6

        skill_content = '''---
name: test-skill
version: 5.0-hybrid
description: Wrong version
---
# Content
'''
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_content)

        result = validate_skill_v6(str(skill_path))
        assert result.valid is False
        assert any("6.0-hybrid" in e for e in result.errors)

    def test_forbidden_action_without_mitigation_fails(self, tmp_path):
        """Forbidden action (Q=-inf) without mitigation should fail."""
        from scripts.validate_skill_v6 import validate_skill_v6

        skill_content = '''---
name: test-skill
version: 6.0-hybrid
description: Test
---

# Option: test-skill

## I (Initiation)
activate: [x]
skip: []

## Y (Observation Space)
| signal | source | interpretation |
|--------|--------|----------------|

## U (Action Space)
primary: [Read]
forbidden: []

## pi (Policy)

### P0: Start

| action | Q | why | mitigation |
|--------|---|-----|------------|
| bad_action | -inf | dangerous | |

## beta (Termination)
success: []
failure: []

## Output Schema
```yaml
sections: []
```

## Invariants
```
```
'''
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_content)

        result = validate_skill_v6(str(skill_path))
        assert result.valid is False
        assert any("mitigation" in e.lower() for e in result.errors)

    def test_missing_initiation_section_fails(self, tmp_path):
        """Skill missing I (Initiation) section should fail."""
        from scripts.validate_skill_v6 import validate_skill_v6

        skill_content = '''---
name: test-skill
version: 6.0-hybrid
description: Test
---

# Option: test-skill

## Y (Observation Space)
| signal | source | interpretation |
|--------|--------|----------------|

## U (Action Space)
primary: [Read]
forbidden: []

## pi (Policy)

## beta (Termination)
success: []
failure: []

## Output Schema
```yaml
sections: []
```

## Invariants
```
```
'''
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_content)

        result = validate_skill_v6(str(skill_path))
        assert result.valid is False
        assert any("initiation" in e.lower() for e in result.errors)

    def test_validation_result_contains_all_errors(self, tmp_path):
        """ValidationResult should list all errors, not just first."""
        from scripts.validate_skill_v6 import validate_skill_v6

        skill_content = '''---
name: test-skill
description: Missing version and sections
---
# Minimal content
'''
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_content)

        result = validate_skill_v6(str(skill_path))
        assert result.valid is False
        # Should have multiple errors (version, sections, etc.)
        assert len(result.errors) > 1


class TestValidationResultType:
    """Tests for ValidationResult data structure."""

    def test_validation_result_has_required_fields(self):
        """ValidationResult should have valid and errors fields."""
        from scripts.validate_skill_v6 import ValidationResult

        result = ValidationResult(valid=True, errors=[])
        assert hasattr(result, 'valid')
        assert hasattr(result, 'errors')

    def test_validation_result_errors_is_list(self):
        """ValidationResult.errors should be a list of strings."""
        from scripts.validate_skill_v6 import ValidationResult

        result = ValidationResult(valid=False, errors=["Error 1", "Error 2"])
        assert isinstance(result.errors, list)
        assert all(isinstance(e, str) for e in result.errors)
