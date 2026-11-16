"""Skill Generator V2 - 3-mode generation with parity verification.

USAGE:
    from scripts.skill_generator_v2 import create_skill, convert_skill, enhance_skill

    # CREATE mode - new skill from scratch
    result = await create_skill(prompt, mode=CreationMode.RESEARCH)

    # CONVERT mode - prose to typed schema
    result = await convert_skill(skill_path)

    # ENHANCE mode - add params to existing
    result = await enhance_skill(skill_path, new_params)

MODES:
    - CREATE/RESEARCH: Generate new skill via NIA research pipeline
    - CREATE/INTERVIEW: Generate new skill via expert Q&A
    - CONVERT: Extract typed params from existing prose skill
    - ENHANCE: Add/refine params on existing skill

THEORY:
    The generator uses E(X,Q) parity verification to ensure converted schemas
    preserve the semantic intent of original prose definitions. Coverage >= 0.8
    is considered valid.
"""
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from scripts.skill_parity_checker import ParityResult, check_parity
from scripts.skill_schema_extractor import extract_eqx_from_schema


class CreationMode(Enum):
    """Mode for CREATE operation."""
    RESEARCH = "research"    # NIA 3x pipeline
    INTERVIEW = "interview"  # Expert Q&A


@dataclass
class SkillGenerationResult:
    """Result of skill generation."""
    schema: dict[str, Any]              # Generated schema
    yaml_content: str                   # Complete SKILL.md content
    research_sources: list[str]         # Research sources used (CREATE mode)
    parity_result: ParityResult | None  # Parity verification (CONVERT/ENHANCE)


# =============================================================================
# CREATE Mode
# =============================================================================


async def create_skill(
    prompt: str,
    mode: CreationMode = CreationMode.RESEARCH,
    interview_answers: dict[str, Any] | None = None
) -> SkillGenerationResult:
    """
    Create new typed skill from scratch.

    Args:
        prompt: Description of skill to create
        mode: RESEARCH (NIA 3x) or INTERVIEW (expert Q&A)
        interview_answers: Answers for INTERVIEW mode

    Returns:
        SkillGenerationResult with schema and YAML
    """
    if mode == CreationMode.RESEARCH:
        return await _create_via_research(prompt)
    else:
        return await _create_via_interview(prompt, interview_answers or {})


async def _create_via_research(prompt: str) -> SkillGenerationResult:
    """Create skill using research pipeline."""
    # Do research
    research_results = await _do_research(prompt)

    # Generate schema from research
    schema = await _generate_schema_from_research(prompt, research_results)

    # Ensure name exists
    if "name" not in schema:
        schema["name"] = _derive_skill_name(prompt)

    # Generate YAML
    yaml_content = _generate_yaml(schema)

    # Extract research sources
    sources = [r.get("source", str(r)) if isinstance(r, dict) else str(r)
               for r in research_results]

    return SkillGenerationResult(
        schema=schema,
        yaml_content=yaml_content,
        research_sources=sources,
        parity_result=None  # No parity for CREATE
    )


async def _create_via_interview(
    prompt: str,
    answers: dict[str, Any]
) -> SkillGenerationResult:
    """Create skill using interview answers."""
    schema = await _generate_schema_from_interview(prompt, answers)

    if "name" not in schema:
        schema["name"] = _derive_skill_name(prompt)

    yaml_content = _generate_yaml(schema)

    return SkillGenerationResult(
        schema=schema,
        yaml_content=yaml_content,
        research_sources=[],
        parity_result=None
    )


async def _do_research(prompt: str) -> list[dict[str, Any]]:
    """
    Perform research for skill creation.

    In production, this calls NIA docs or web search.
    Returns list of research results.
    """
    # Placeholder for actual research integration
    # Would call NIA 3x pattern here
    return []


async def _generate_schema_from_research(
    prompt: str,
    research_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Generate schema from prompt and research.

    In production, this calls LLM with research context.
    """
    # Placeholder - actual implementation would use LLM
    return {
        "name": _derive_skill_name(prompt),
        "description": f"Generated skill for: {prompt[:50]}",
        "parameters": {}
    }


async def _generate_schema_from_interview(
    prompt: str,
    answers: dict[str, Any]
) -> dict[str, Any]:
    """
    Generate schema from interview answers.

    Converts Q&A answers to typed parameter definitions.
    """
    parameters = {}

    for key, value in answers.items():
        if isinstance(value, bool):
            parameters[key] = {"type": "bool", "default": value}
        elif isinstance(value, int):
            parameters[key] = {"type": "int", "default": value}
        elif isinstance(value, list):
            parameters[key] = {"type": "enum", "values": value, "default": value[0] if value else None}
        else:
            parameters[key] = {"type": "string", "default": str(value)}

    return {
        "name": _derive_skill_name(prompt),
        "description": f"Generated skill for: {prompt[:50]}",
        "parameters": parameters
    }


# =============================================================================
# CONVERT Mode
# =============================================================================


async def convert_skill(skill_path: str | Path) -> SkillGenerationResult:
    """
    Convert prose skill to typed schema.

    Extracts implicit parameters from prose using LLM analysis,
    then generates typed schema with parity verification.

    Args:
        skill_path: Path to skill directory or SKILL.md file

    Returns:
        SkillGenerationResult with schema, YAML, and parity result
    """
    from scripts.skill_prose_extractor import extract_eqx_from_prose

    # Read skill file
    skill_md = _read_skill_file(skill_path)

    # Extract E(X,Q) from prose
    prose_eqx = await extract_eqx_from_prose(skill_md)

    # Generate schema from extracted params (pass path for name derivation)
    schema = _prose_eqx_to_schema(prose_eqx, skill_md, skill_path)

    # Extract E(X,Q) from generated schema
    schema_eqx = extract_eqx_from_schema({"parameters": schema.get("parameters", {})})

    # Verify parity
    parity = check_parity(prose_eqx, schema_eqx)

    # Extract original body to preserve instructions
    original_body = _extract_body(skill_md)

    # Generate YAML with preserved body
    yaml_content = _generate_yaml(schema, original_body)

    return SkillGenerationResult(
        schema=schema,
        yaml_content=yaml_content,
        research_sources=[],
        parity_result=parity
    )


def _read_skill_file(skill_path: str | Path) -> str:
    """Read SKILL.md content from path."""
    path = Path(skill_path)

    if path.is_dir():
        skill_file = path / "SKILL.md"
    else:
        skill_file = path

    if skill_file.exists():
        return skill_file.read_text()

    raise FileNotFoundError(f"SKILL.md not found at {skill_path}")


def _extract_body(md_content: str) -> str:
    """Extract body content after YAML frontmatter.

    Returns everything after the closing --- of frontmatter.
    If no frontmatter, returns the entire content.
    """
    # Match YAML frontmatter: ---\n...\n---
    match = re.match(r"^---\n.*?\n---\n?", md_content, re.DOTALL)
    if match:
        return md_content[match.end():].strip()
    return md_content.strip()


def _prose_eqx_to_schema(
    prose_eqx: dict[str, Any],
    original_md: str,
    skill_path: str | Path | None = None
) -> dict[str, Any]:
    """
    Convert prose E(X,Q) extraction to schema.

    Args:
        prose_eqx: E(X,Q) extraction from prose
        original_md: Original SKILL.md content (for name extraction)
        skill_path: Path to skill (for name derivation from directory)

    Returns:
        Schema dict with name, description, parameters
    """
    # Extract name from original frontmatter or derive from path
    name = _extract_name_from_yaml(original_md, skill_path)

    # Build parameters from extraction
    parameters = prose_eqx.get("parameters", {})

    return {
        "name": name,
        "description": f"Converted skill: {name}",
        "parameters": parameters
    }


def _extract_name_from_yaml(md_content: str, skill_path: str | Path | None = None) -> str:
    """Extract skill name from YAML frontmatter or derive from path.

    Priority:
    1. Explicit 'name' field in frontmatter
    2. Directory name from skill_path (e.g., .claude/skills/research -> research)
    3. Fallback to 'converted-skill'
    """
    # Try frontmatter first
    match = re.match(r"^---\n(.*?)\n---", md_content, re.DOTALL)
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1))
            if isinstance(frontmatter, dict) and "name" in frontmatter:
                return frontmatter["name"]
        except yaml.YAMLError:
            pass

    # Derive from skill path (directory name)
    if skill_path:
        path = Path(skill_path)
        if path.is_dir():
            return path.name
        elif path.name == "SKILL.md":
            return path.parent.name

    return "converted-skill"


# =============================================================================
# ENHANCE Mode
# =============================================================================


async def enhance_skill(
    skill_path: str | Path,
    new_params: dict[str, dict[str, Any]]
) -> SkillGenerationResult:
    """
    Enhance existing skill with additional parameters.

    Merges new params into existing skill definition.
    New params override existing if same name.

    Args:
        skill_path: Path to skill directory or SKILL.md file
        new_params: New parameters to add {name: {type, default, ...}}

    Returns:
        SkillGenerationResult with merged schema
    """
    # First convert to get baseline
    converted = await convert_skill(skill_path)

    # Merge parameters (new overrides existing)
    merged_params = {**converted.schema.get("parameters", {}), **new_params}

    # Update schema
    enhanced_schema = {
        **converted.schema,
        "parameters": merged_params
    }

    # Read original skill to preserve body
    skill_md = _read_skill_file(skill_path)
    original_body = _extract_body(skill_md)

    # Regenerate YAML with preserved body
    yaml_content = _generate_yaml(enhanced_schema, original_body)

    # Recalculate parity with enhanced schema
    from scripts.skill_prose_extractor import extract_eqx_from_prose
    prose_eqx = await extract_eqx_from_prose(skill_md)
    schema_eqx = extract_eqx_from_schema({"parameters": merged_params})
    parity = check_parity(prose_eqx, schema_eqx)

    return SkillGenerationResult(
        schema=enhanced_schema,
        yaml_content=yaml_content,
        research_sources=[],
        parity_result=parity
    )


# =============================================================================
# YAML Generation
# =============================================================================


def _generate_yaml(schema: dict[str, Any], original_body: str | None = None) -> str:
    """
    Generate SKILL.md content from schema.

    Creates YAML frontmatter with typed parameters.
    If original_body is provided, preserves the original instructions.

    Args:
        schema: Schema dict with name, description, parameters
        original_body: Original skill body to preserve (optional)

    Returns:
        Complete SKILL.md content
    """
    name = schema.get("name", "generated-skill")
    description = schema.get("description", "")
    parameters = schema.get("parameters", {})

    # Build frontmatter dict
    frontmatter: dict[str, Any] = {
        "name": name,
        "description": description
    }

    if parameters:
        frontmatter["parameters"] = parameters

    # Generate YAML
    yaml_content = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    # Build complete content
    if original_body:
        # Preserve original instructions - just add new frontmatter
        content_lines = [
            "---",
            yaml_content.rstrip(),
            "---",
            "",
            original_body,
        ]
    else:
        # Generate placeholder for new skills
        content_lines = [
            "---",
            yaml_content.rstrip(),
            "---",
            "",
            f"# {name}",
            "",
            "## When to Use",
            "",
            description or "Use this skill when...",
            "",
            "## Instructions",
            "",
            "1. Analyze the task",
            "2. Execute steps",
            "3. Verify results",
            "",
        ]

    return "\n".join(content_lines)


def _derive_skill_name(prompt: str) -> str:
    """
    Derive skill name from prompt.

    Converts to kebab-case, removes common words.
    """
    # Common words to remove
    common = {
        'implement', 'create', 'build', 'make', 'add', 'write',
        'the', 'a', 'an', 'for', 'to', 'with', 'and', 'or',
        'this', 'that', 'my', 'our', 'your', 'their', 'skill'
    }

    # Clean and split
    cleaned = re.sub(r"[^\w\s]", '', prompt.lower())
    words = cleaned.split()

    # Remove common words
    significant = [w for w in words if w not in common]
    if len(significant) < 2 and words:
        significant = words[:4]

    # Join with hyphens
    name = '-'.join(significant[:5])

    # Ensure max length
    if len(name) > 50:
        name = name[:50].rsplit('-', 1)[0]

    return name or 'generated-skill'
