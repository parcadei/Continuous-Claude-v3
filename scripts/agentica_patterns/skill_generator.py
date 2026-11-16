"""Skill Generator - YAML template generation for JIT skills.

Phase 12 of Self-Improving Skill System.

This module generates SKILL.md content from:
- Task type (implementation, debug, research, planning)
- Resolved Q-heuristic answers
- Research findings (NIA docs, codebase patterns)

Usage:
    from scripts.agentica_patterns.skill_generator import (
        generate_from_qheuristics,
        generate_skill_yaml
    )

    spec = generate_from_qheuristics(
        task_type='implementation',
        resolved_qheuristics={'auth_method': 'JWT'},
        original_prompt='implement JWT authentication'
    )
    yaml_content = generate_skill_yaml(spec)

Plan reference: thoughts/shared/plans/self-improving-skill-system.md (Phase 12)
"""

import re
from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class SkillSpec:
    """Specification for a generated skill.

    Attributes:
        name: Skill name in kebab-case
        description: Brief description
        goal: What the skill accomplishes
        tools: List of allowed tools
        instructions: Step-by-step instructions
        triggers: Keywords and patterns for activation
    """
    name: str
    description: str
    goal: str
    tools: list[str]
    instructions: str
    triggers: dict[str, list[str]] = field(
        default_factory=lambda: {'keywords': [], 'intentPatterns': []}
    )


# =============================================================================
# YAML Generation
# =============================================================================


def generate_skill_yaml(spec: SkillSpec) -> str:
    """Generate SKILL.md content from a SkillSpec.

    Creates valid YAML frontmatter followed by markdown content.

    Args:
        spec: The skill specification

    Returns:
        Complete SKILL.md file content
    """
    # Escape special YAML characters in strings
    name = _yaml_escape(spec.name)
    description = _yaml_escape(spec.description)

    # Format tools list
    if spec.tools:
        tools_str = ', '.join(spec.tools)
    else:
        tools_str = ''

    # Build YAML frontmatter
    frontmatter_lines = [
        '---',
        f'name: {name}',
        f'description: {description}',
    ]

    if tools_str:
        frontmatter_lines.append(f'allowed-tools: [{tools_str}]')

    frontmatter_lines.append('---')

    # Build markdown content
    content_lines = [
        '',
        f'# {spec.name}',
        '',
        '## When to Use',
        '',
        spec.goal,
        '',
        '## Instructions',
        '',
        spec.instructions,
        '',
    ]

    return '\n'.join(frontmatter_lines + content_lines)


def _yaml_escape(value: str) -> str:
    """Escape special characters for YAML.

    Args:
        value: String to escape

    Returns:
        Escaped string (quoted if necessary)

    Note: Handles newlines, tabs, and other control characters by quoting
    and escaping them properly for valid YAML output.
    """
    # Characters that require quoting
    special_chars = [':', '#', '[', ']', '{', '}', '&', '*', '!', '|', '>', "'", '"', '%', '@', '`']

    # Control characters that need escaping (newlines, tabs, carriage returns)
    control_chars = ['\n', '\t', '\r']

    needs_quoting = (
        any(char in value for char in special_chars) or
        any(char in value for char in control_chars)
    )

    if needs_quoting:
        # Double-quote and escape internal quotes and control characters
        escaped = value.replace('\\', '\\\\')  # Escape backslashes first
        escaped = escaped.replace('"', '\\"')  # Escape double quotes
        escaped = escaped.replace('\n', '\\n')  # Escape newlines
        escaped = escaped.replace('\t', '\\t')  # Escape tabs
        escaped = escaped.replace('\r', '\\r')  # Escape carriage returns
        return f'"{escaped}"'

    return value


# =============================================================================
# Skill Name Generation
# =============================================================================


# Common words to remove from skill names
COMMON_WORDS = {
    'implement', 'create', 'build', 'make', 'add', 'write',
    'the', 'a', 'an', 'for', 'to', 'with', 'and', 'or',
    'this', 'that', 'my', 'our', 'your', 'their'
}


def derive_skill_name(prompt: str) -> str:
    """Derive a skill name from the original prompt.

    Converts prompt to kebab-case, removes common words,
    and ensures reasonable length.

    Args:
        prompt: Original user prompt

    Returns:
        Skill name in kebab-case
    """
    # Convert to lowercase and remove special characters
    cleaned = re.sub(r"[^\w\s]", '', prompt.lower())

    # Split into words
    words = cleaned.split()

    # Remove common words (but keep at least some words)
    significant_words = [w for w in words if w not in COMMON_WORDS]
    if len(significant_words) < 2 and words:
        significant_words = words[:4]

    # Take first 4-5 significant words
    name_words = significant_words[:5]

    # Join with hyphens
    name = '-'.join(name_words)

    # Ensure max length
    if len(name) > 50:
        name = name[:50].rsplit('-', 1)[0]

    # Fallback if empty
    if not name:
        name = 'generated-skill'

    return name


# =============================================================================
# Tool Selection
# =============================================================================


# Default tools by task type
DEFAULT_TOOLS = {
    'implementation': ['Bash', 'Read', 'Write', 'Edit', 'Glob'],
    'debug': ['Bash', 'Read', 'Grep', 'Glob', 'LSP'],
    'research': ['Read', 'Glob', 'Grep', 'WebFetch', 'WebSearch'],
    'planning': ['Read', 'Write', 'Glob'],
}


def select_tools_for_task(
    task_type: str,
    resolved_qheuristics: dict[str, str]
) -> list[str]:
    """Select appropriate tools for a task.

    Uses task type defaults, then overrides with Q-heuristic answers.

    Args:
        task_type: Type of task
        resolved_qheuristics: User's answers to Q-heuristics

    Returns:
        List of tool names
    """
    # Check if tools specified in Q-heuristics
    if 'tools' in resolved_qheuristics:
        tools_str = resolved_qheuristics['tools']
        return [t.strip() for t in tools_str.split(',')]

    # Use defaults for task type
    return DEFAULT_TOOLS.get(task_type, ['Bash', 'Read', 'Write'])


# =============================================================================
# Instruction Generation
# =============================================================================


# Instruction templates by task type
INSTRUCTION_TEMPLATES = {
    'implementation': """
1. Understand the requirements: {goal}
2. Search for existing patterns using Glob/Grep
3. Write tests first (TDD approach) if specified: {test_coverage}
4. Implement the solution
5. Verify tests pass
6. Document any significant decisions
""",
    'debug': """
1. Reproduce the issue: {error_type}
2. Gather information (logs, stack traces, state)
3. Narrow down the scope: {scope}
4. Investigation depth: {investigation_depth}
5. Identify root cause
6. Implement fix
7. Verify the fix resolves the issue
""",
    'research': """
1. Define research scope: {depth}
2. Gather information from: {sources}
3. Analyze findings
4. Synthesize insights
5. Format output as: {output_format}
""",
    'planning': """
1. Understand the objective: {goal}
2. Break down into phases
3. Detail level: {detail_level}
4. Include timeline: {include_timeline}
5. Risk analysis: {include_risks}
6. Create actionable plan
"""
}


def generate_instructions(
    task_type: str,
    goal: str,
    resolved_qheuristics: dict[str, str],
    research_results: list[Any] | None = None
) -> str:
    """Generate step-by-step instructions for a skill.

    Uses templates based on task type, filled with Q-heuristic values.

    Args:
        task_type: Type of task
        goal: Main goal of the skill
        resolved_qheuristics: User's answers
        research_results: Optional research findings to incorporate

    Returns:
        Formatted instructions string
    """
    template = INSTRUCTION_TEMPLATES.get(
        task_type,
        "1. Understand the task: {goal}\n2. Execute the task\n3. Verify results"
    )

    # Build substitution dict
    subs = {
        'goal': goal,
        'test_coverage': resolved_qheuristics.get('test_coverage', 'Unit Tests'),
        'error_type': resolved_qheuristics.get('error_type', 'Unknown'),
        'scope': resolved_qheuristics.get('scope', 'Auto-detect'),
        'investigation_depth': resolved_qheuristics.get('investigation_depth', 'Root Cause'),
        'depth': resolved_qheuristics.get('depth', 'Standard'),
        'sources': resolved_qheuristics.get('sources', 'All'),
        'output_format': resolved_qheuristics.get('output_format', 'Summary'),
        'detail_level': resolved_qheuristics.get('detail_level', 'Standard'),
        'include_timeline': resolved_qheuristics.get('include_timeline', 'No'),
        'include_risks': resolved_qheuristics.get('include_risks', 'No'),
    }

    # Format template
    instructions = template.format(**subs)

    # Add research insights if available
    if research_results:
        insights = _extract_research_insights(research_results)
        if insights:
            instructions += f"\n\n**Best Practices from Research:**\n{insights}"

    return instructions.strip()


def _extract_research_insights(research_results: list[Any]) -> str:
    """Extract key insights from research results.

    Args:
        research_results: List of ResearchResult objects

    Returns:
        Formatted insights string
    """
    insights = []

    for result in research_results[:3]:  # Top 3 results
        content = getattr(result, 'content', str(result))
        # Take first 200 chars of each result
        snippet = content[:200].strip()
        if snippet:
            insights.append(f"- {snippet}")

    return '\n'.join(insights)


# =============================================================================
# Trigger Generation
# =============================================================================


def generate_triggers(
    original_prompt: str,
    task_type: str
) -> dict[str, list[str]]:
    """Generate skill triggers from the original prompt.

    Extracts keywords and creates intent patterns.

    Args:
        original_prompt: User's original prompt
        task_type: Type of task

    Returns:
        Dict with 'keywords' and 'intentPatterns' lists
    """
    # Extract significant words as keywords
    words = re.findall(r'\b\w{4,}\b', original_prompt.lower())
    keywords = [w for w in words if w not in COMMON_WORDS][:5]

    # Generate intent pattern based on task type
    patterns = []
    if task_type == 'implementation' and keywords:
        patterns.append(f"implement.*{keywords[0]}")
    elif task_type == 'debug' and keywords:
        patterns.append(f"(debug|fix).*{keywords[0]}")
    elif task_type == 'research' and keywords:
        patterns.append(f"research.*{keywords[0]}")

    return {
        'keywords': keywords,
        'intentPatterns': patterns
    }


# =============================================================================
# Main Generation Function
# =============================================================================


def generate_from_qheuristics(
    task_type: str,
    resolved_qheuristics: dict[str, str],
    original_prompt: str,
    research_results: list[Any] | None = None
) -> SkillSpec:
    """Generate a complete SkillSpec from Q-heuristic answers.

    This is the main entry point for skill generation.

    Args:
        task_type: Type of task (implementation, debug, research, planning)
        resolved_qheuristics: Dictionary of Q-heuristic id -> answer
        original_prompt: The user's original prompt
        research_results: Optional research findings to incorporate

    Returns:
        Complete SkillSpec ready for YAML generation
    """
    # Derive skill name from prompt
    name = derive_skill_name(original_prompt)

    # Extract goal from prompt (first sentence or first 100 chars)
    goal = original_prompt.split('.')[0][:100].strip()
    if not goal.endswith('.'):
        goal += '.'

    # Generate description
    description = f"Auto-generated skill for: {goal[:50]}"

    # Select tools
    tools = select_tools_for_task(task_type, resolved_qheuristics)

    # Generate instructions
    instructions = generate_instructions(
        task_type,
        goal,
        resolved_qheuristics,
        research_results
    )

    # Generate triggers
    triggers = generate_triggers(original_prompt, task_type)

    return SkillSpec(
        name=name,
        description=description,
        goal=goal,
        tools=tools,
        instructions=instructions,
        triggers=triggers
    )
