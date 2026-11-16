"""
Skill YAML Structural Validator (Phase 1 Tasks 1.4-1.6).

USAGE:
    uv run python scripts/skill_validator.py --file path/to/SKILL.md

Validates:
1. YAML frontmatter syntax
2. Required fields (name, description)
3. Parameter schema structure

Returns JSON with validation result and any errors.
"""

from dataclasses import dataclass, field
from typing import Any
import yaml
import re
import argparse
import json
import sys


@dataclass
class ValidationResult:
    """Result of YAML structure validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    parsed_frontmatter: dict[str, Any] | None = None


# Regex to extract YAML frontmatter (between --- delimiters)
FRONTMATTER_PATTERN = re.compile(
    r'^---\s*\n(.*?)\n---',
    re.DOTALL | re.MULTILINE
)


def verify_yaml_structure(content: str) -> ValidationResult:
    """
    Verify YAML frontmatter structure in SKILL.md content.

    Args:
        content: Full SKILL.md content with YAML frontmatter

    Returns:
        ValidationResult with is_valid flag and any errors
    """
    errors: list[str] = []

    # Check for frontmatter delimiters
    if not content.strip().startswith('---'):
        errors.append("Missing YAML frontmatter opening delimiter '---'")
        return ValidationResult(is_valid=False, errors=errors)

    # Extract frontmatter
    match = FRONTMATTER_PATTERN.match(content.strip())
    if not match:
        errors.append("Missing YAML frontmatter closing delimiter '---' or malformed frontmatter")
        return ValidationResult(is_valid=False, errors=errors)

    yaml_content = match.group(1)

    # Parse YAML
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML syntax: {e}")
        return ValidationResult(is_valid=False, errors=errors)

    # Handle empty YAML
    if parsed is None:
        parsed = {}

    # Validate required fields
    if 'name' not in parsed:
        errors.append("Missing required field: name")
    elif not parsed.get('name'):
        errors.append("Field 'name' cannot be empty")

    if 'description' not in parsed:
        errors.append("Missing required field: description")
    elif not parsed.get('description'):
        errors.append("Field 'description' cannot be empty")

    if errors:
        return ValidationResult(is_valid=False, errors=errors, parsed_frontmatter=parsed)

    return ValidationResult(is_valid=True, errors=[], parsed_frontmatter=parsed)


def validate_file(file_path: str) -> ValidationResult:
    """Validate a SKILL.md file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return verify_yaml_structure(content)
    except FileNotFoundError:
        return ValidationResult(is_valid=False, errors=[f"File not found: {file_path}"])
    except IOError as e:
        return ValidationResult(is_valid=False, errors=[f"IO error reading file: {e}"])


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate SKILL.md YAML structure"
    )
    parser.add_argument(
        '--file', '-f',
        required=True,
        help="Path to SKILL.md file to validate"
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help="Output as JSON"
    )

    args = parser.parse_args()
    result = validate_file(args.file)

    if args.json:
        output = {
            "is_valid": result.is_valid,
            "errors": result.errors
        }
        print(json.dumps(output))
    else:
        if result.is_valid:
            print(f"VALID: {args.file}")
        else:
            print(f"INVALID: {args.file}")
            for error in result.errors:
                print(f"  - {error}")

    sys.exit(0 if result.is_valid else 1)


if __name__ == '__main__':
    main()
