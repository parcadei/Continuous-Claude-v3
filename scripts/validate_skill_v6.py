"""
v6.0-hybrid Skill Validator

Validates SKILL.md files against the v6.0-hybrid schema.

Usage:
    uv run python scripts/validate_skill_v6.py .claude/skills/debug/SKILL.md

References:
    - scripts/skill_schema_v6.py
    - thoughts/shared/plans/2025-12-30-decision-theory-skill-formalization.md
"""

import re
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class ValidationResult:
    """Result of skill validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from SKILL.md."""
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}

    body = parts[2].strip()
    return frontmatter, body


def extract_sections(body: str) -> dict[str, str]:
    """Extract named sections from skill body."""
    sections = {}
    current_section = None
    current_content = []

    for line in body.split('\n'):
        # Match ## I (Initiation), ## Y (Observation Space), etc.
        match = re.match(r'^##\s+(\w+)\s*\(([^)]+)\)', line)
        if match:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = match.group(1).lower()
            current_content = []
        elif re.match(r'^##\s+(\w+)', line):
            # Match ## pi (Policy), ## beta (Termination), etc.
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            match2 = re.match(r'^##\s+(\w+)', line)
            current_section = match2.group(1).lower()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_content)

    return sections


def validate_initiation(section: Optional[str]) -> list[str]:
    """Validate I (Initiation) section."""
    if not section:
        return ["Missing I (Initiation) section"]

    errors = []
    if 'activate:' not in section and 'activate' not in section.lower():
        errors.append("Initiation section missing 'activate' field")

    return errors


def validate_observation_space(section: Optional[str]) -> list[str]:
    """Validate Y (Observation Space) section."""
    # Y is optional but if present should have table format
    return []


def validate_action_space(section: Optional[str]) -> list[str]:
    """Validate U (Action Space) section."""
    if not section:
        return ["Missing U (Action Space) section"]

    errors = []
    if 'primary:' not in section:
        errors.append("Action Space missing 'primary' field")

    return errors


def validate_policy(section: Optional[str]) -> list[str]:
    """Validate pi (Policy) section including Q-tables."""
    if not section:
        return ["Missing pi (Policy) section"]

    errors = []

    # Check for Q-tables and validate mitigation for -inf
    # Match table rows with | action | Q | why | mitigation |
    table_rows = re.findall(r'\|\s*(\S+)\s*\|\s*(-inf|HIGH|MED|LOW)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|', section)

    for action, q_value, why, mitigation in table_rows:
        if q_value == '-inf' and not mitigation.strip():
            errors.append(f"Missing mitigation for forbidden action '{action}' (Q=-inf)")

    return errors


def validate_termination(section: Optional[str]) -> list[str]:
    """Validate beta (Termination) section."""
    if not section:
        return ["Missing beta (Termination) section"]
    return []


def validate_skill_v6(skill_path: str) -> ValidationResult:
    """Validate SKILL.md against v6.0-hybrid schema.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        ValidationResult with valid=True if passes, otherwise errors list
    """
    path = Path(skill_path)
    if not path.exists():
        return ValidationResult(valid=False, errors=[f"File not found: {skill_path}"])

    content = path.read_text()
    frontmatter, body = parse_frontmatter(content)
    errors = []

    # Check version
    version = frontmatter.get('version')
    if not version:
        errors.append("Missing 'version' field in frontmatter")
    elif version != '6.0-hybrid':
        errors.append(f"Version must be '6.0-hybrid', got '{version}'")

    # Check required frontmatter fields
    if not frontmatter.get('name'):
        errors.append("Missing 'name' field in frontmatter")

    if not frontmatter.get('description'):
        errors.append("Missing 'description' field in frontmatter")

    # Extract and validate sections
    sections = extract_sections(body)

    errors += validate_initiation(sections.get('i'))
    errors += validate_observation_space(sections.get('y'))
    errors += validate_action_space(sections.get('u'))
    errors += validate_policy(sections.get('pi'))
    errors += validate_termination(sections.get('beta'))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Validate SKILL.md against v6.0-hybrid schema')
    parser.add_argument('skill_path', help='Path to SKILL.md file')
    args = parser.parse_args()

    result = validate_skill_v6(args.skill_path)

    if result.valid:
        print(f"Valid: {args.skill_path}")
    else:
        print(f"Invalid: {args.skill_path}")
        for error in result.errors:
            print(f"  - {error}")

    return 0 if result.valid else 1


if __name__ == '__main__':
    exit(main())
