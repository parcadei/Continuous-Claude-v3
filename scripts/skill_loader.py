"""
Load skill schemas from SKILL.md files on disk.

USAGE:
    from scripts.skill_loader import load_skill_schema
    schema = load_skill_schema("skill-name")
    # or with explicit base path
    schema = load_skill_schema("skill-name", base_path=Path("/project"))
"""
import os
from pathlib import Path
from scripts.skill_schema_parser import parse_skill_schema, SkillSchema


def load_skill_schema(
    skill_name: str, base_path: Path | None = None
) -> SkillSchema | None:
    """
    Load skill schema from .claude/skills/{skill_name}/SKILL.md.

    Args:
        skill_name: Name of the skill directory
        base_path: Project root (defaults to cwd or CLAUDE_PROJECT_DIR)

    Returns:
        SkillSchema or None if not found/parseable
    """
    if base_path is None:
        base_path = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))

    skill_path = base_path / ".claude" / "skills" / skill_name / "SKILL.md"

    if not skill_path.exists():
        return None

    content = skill_path.read_text()
    return parse_skill_schema(content)
