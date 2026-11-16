"""Skill injection utilities for Agentica agents.

Load skills and rules from .claude/ directory and inject them into agent premises.
Supports predefined bundles for common scenarios (implementation, research).

Usage:
    from scripts.agentica_patterns.skill_injection import inject_skills

    # Single skill
    premise = inject_skills(
        "Implement feature X",
        skills=["test-driven-development"]
    )

    # Predefined bundle
    premise = inject_skills(
        "Implement feature X",
        bundle="implementation"
    )
"""

from pathlib import Path

# Predefined skill/rule bundles
BUNDLES = {
    "implementation": {
        "skills": ["test-driven-development", "qlty-check"],
        "rules": ["git-commits", "observe-before-editing"],
        "premise": "You are an implementation expert. Write tests first. "
        "Watch them fail. Implement minimally. Check outputs before editing."
    },
    "research": {
        "skills": ["rp-explorer", "repo-research-analyst"],
        "rules": [],
        "premise": "You are a codebase analyst. Explore efficiently. Document patterns."
    }
}


def load_skill(skill_name: str, base_path: Path | None = None) -> str:
    """Load skill content from SKILL.md file.

    Args:
        skill_name: Name of the skill directory
        base_path: Base path for .claude directory (defaults to project root)

    Returns:
        Skill content as string

    Raises:
        FileNotFoundError: If skill file doesn't exist
    """
    if base_path is None:
        # Default to project root (.claude is at project root)
        base_path = Path(__file__).parent.parent.parent

    skill_path = base_path / ".claude" / "skills" / skill_name / "SKILL.md"

    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_name} at {skill_path}")

    return skill_path.read_text()


def load_rule(rule_name: str, base_path: Path | None = None) -> str:
    """Load rule content from .md file.

    Args:
        rule_name: Name of the rule file (without .md extension)
        base_path: Base path for .claude directory (defaults to project root)

    Returns:
        Rule content as string

    Raises:
        FileNotFoundError: If rule file doesn't exist
    """
    if base_path is None:
        # Default to project root (.claude is at project root)
        base_path = Path(__file__).parent.parent.parent

    rule_path = base_path / ".claude" / "rules" / f"{rule_name}.md"

    if not rule_path.exists():
        raise FileNotFoundError(f"Rule not found: {rule_name} at {rule_path}")

    return rule_path.read_text()


def inject_skills(
    premise: str,
    skills: list[str] | None = None,
    rules: list[str] | None = None,
    bundle: str | None = None,
    base_path: Path | None = None
) -> str:
    """Inject skills and rules into premise.

    Args:
        premise: Original task premise
        skills: List of skill names to inject
        rules: List of rule names to inject
        bundle: Predefined bundle name (implementation, research)
        base_path: Base path for .claude directory

    Returns:
        Enhanced premise with skill/rule content prepended
    """
    # Bundle overrides explicit skills/rules
    if bundle:
        if bundle not in BUNDLES:
            raise ValueError(f"Unknown bundle: {bundle}. Available: {list(BUNDLES.keys())}")

        bundle_config = BUNDLES[bundle]
        skills = bundle_config["skills"]
        rules = bundle_config["rules"]
        # Optionally prepend bundle premise to original premise
        bundle_premise = bundle_config.get("premise")
        if bundle_premise:
            premise = f"{bundle_premise}\n\n{premise}"

    # If no skills or rules, return original premise
    if not skills and not rules:
        return premise

    # Build injected content
    injected_parts = []

    # Load skills
    if skills:
        for skill_name in skills:
            skill_content = load_skill(skill_name, base_path)
            injected_parts.append(f"# Skill: {skill_name}\n\n{skill_content}")

    # Load rules
    if rules:
        for rule_name in rules:
            rule_content = load_rule(rule_name, base_path)
            injected_parts.append(f"# Rule: {rule_name}\n\n{rule_content}")

    # Combine: injected content + original premise
    if injected_parts:
        injected_section = "\n\n---\n\n".join(injected_parts)
        return f"{injected_section}\n\n---\n\n{premise}"

    return premise
