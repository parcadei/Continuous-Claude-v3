"""
Parse typed parameter schemas from SKILL.md frontmatter.

USAGE:
    from scripts.skill_schema_parser import parse_skill_schema
    schema = parse_skill_schema(skill_md_content)
"""
from dataclasses import dataclass
from typing import Any
import re
import yaml


@dataclass
class SkillParameter:
    """A typed parameter in a skill schema."""

    name: str
    type: str  # enum | bool | duration | int | string
    required: bool = False
    default: Any = None
    values: list[str] | None = None  # for enum
    infer_from: str | None = None  # regex pattern
    min: Any = None
    max: Any = None


@dataclass
class SkillSchema:
    """Schema for a skill with typed parameters."""

    name: str
    parameters: dict[str, SkillParameter]


def parse_skill_schema(skill_md: str) -> SkillSchema | None:
    """
    Extract typed parameter schema from SKILL.md content.

    Args:
        skill_md: The raw content of a SKILL.md file

    Returns:
        SkillSchema with parsed parameters, or None if parsing fails
    """
    # Extract YAML frontmatter (between --- markers)
    match = re.match(r"^---\n(.*?)\n---", skill_md, re.DOTALL)
    if not match:
        return None

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None

    if not isinstance(frontmatter, dict):
        return None

    name = frontmatter.get("name", "unknown")
    params_raw = frontmatter.get("parameters", {})

    if params_raw is None:
        params_raw = {}

    parameters: dict[str, SkillParameter] = {}
    for param_name, param_def in params_raw.items():
        if not isinstance(param_def, dict):
            continue

        parameters[param_name] = SkillParameter(
            name=param_name,
            type=param_def.get("type", "string"),
            required=param_def.get("required", False),
            default=param_def.get("default"),
            values=param_def.get("values"),
            infer_from=param_def.get("infer_from"),
            min=param_def.get("min"),
            max=param_def.get("max"),
        )

    return SkillSchema(name=name, parameters=parameters)
