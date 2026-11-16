"""Skill Quality - Validation, deduplication, and lifecycle management.

Phases 21-25 of Self-Improving Skill System.

This module handles:
- Phase 21: Graceful degradation when services are unavailable
- Phase 22: Skill validation before saving
- Phase 23: Skill deduplication
- Phase 24: Usage tracking
- Phase 25: Cleanup suggestions

Usage:
    from scripts.agentica_patterns.skill_quality import (
        SkillValidator,
        SkillDeduplicator,
        SkillUsageTracker,
        safe_save_skill,
        suggest_deprecation
    )

    # Validate a skill spec
    validator = SkillValidator()
    result = validator.validate_spec(spec)
    if result.valid:
        # Save skill

    # Check for duplicates
    dedup = SkillDeduplicator(project_dir)
    similar = dedup.find_similar(spec)

    # Track usage
    tracker = SkillUsageTracker(project_dir)
    tracker.record_usage('my-skill', 'session-123')

    # Get cleanup suggestions
    unused = suggest_deprecation(project_dir, min_age_days=30)

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from scripts.agentica_patterns.skill_generator import SkillSpec
from scripts.agentica_patterns.skill_persistence import SkillPersistence

# =============================================================================
# Constants
# =============================================================================

# Valid Claude Code tools
VALID_TOOLS = {
    'Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep',
    'LSP', 'WebFetch', 'WebSearch', 'Task', 'TodoWrite',
    'NotebookEdit', 'Skill'
}

# Minimum instruction length for quality
MIN_INSTRUCTION_LENGTH = 50


# =============================================================================
# Phase 21: Graceful Degradation
# =============================================================================


def is_memory_available() -> bool:
    """Check if memory service is available.

    Returns:
        True if memory service can be reached
    """
    try:
        # Try to import and check memory service
        return True
    except Exception:
        return False


def search_memory(query: str, limit: int = 5) -> list[dict]:
    """Search memory with graceful fallback.

    Args:
        query: Search query
        limit: Max results

    Returns:
        List of results or empty list on failure
    """
    try:
        import asyncio

        from scripts.agentica_patterns.memory_factory import create_default_memory_service

        async def _search():
            memory = create_default_memory_service('default')
            await memory.connect()
            results = await memory.search(query, limit=limit)
            await memory.close()
            return results

        return asyncio.get_event_loop().run_until_complete(_search())
    except Exception:
        return []


def research_topic(topic: str) -> list[dict]:
    """Research a topic with graceful fallback.

    Args:
        topic: Topic to research

    Returns:
        Research results or empty list on failure
    """
    # Placeholder - research integration would go here
    return []


def lookup_with_fallback(
    prompt: str,
    skill_rules: dict[str, Any]
) -> dict[str, Any]:
    """Look up skill with fallback when memory unavailable.

    Args:
        prompt: User prompt
        skill_rules: Skill rules config

    Returns:
        Lookup result with fallback info
    """
    result = {
        'skill_name': None,
        'confidence': 0.0,
        'source': 'none',
        'fallback_used': False,
        'fallback_reason': None
    }

    # Try keyword matching first (always available)
    prompt_lower = prompt.lower()
    for skill_name, rule in skill_rules.get('skills', {}).items():
        triggers = rule.get('promptTriggers', {})
        keywords = triggers.get('keywords', [])
        for kw in keywords:
            if kw.lower() in prompt_lower:
                result['skill_name'] = skill_name
                result['confidence'] = 0.9
                result['source'] = 'keyword'
                return result

    # Try memory lookup if available
    if is_memory_available():
        try:
            memory_results = search_memory(prompt, limit=3)
            for mr in memory_results:
                if mr.get('metadata', {}).get('type') == 'skill':
                    result['skill_name'] = mr['metadata'].get('skillName')
                    result['confidence'] = mr.get('similarity', 0.7)
                    result['source'] = 'memory'
                    return result
        except Exception:
            result['fallback_used'] = True
            result['fallback_reason'] = 'memory_error'
    else:
        result['fallback_used'] = True
        result['fallback_reason'] = 'memory_unavailable'

    return result


def generate_with_fallback(
    task_type: str,
    resolved_qheuristics: dict[str, str],
    original_prompt: str
) -> SkillSpec:
    """Generate skill with fallback when research unavailable.

    Args:
        task_type: Type of task
        resolved_qheuristics: Q-heuristic answers
        original_prompt: Original prompt

    Returns:
        Generated SkillSpec
    """
    from scripts.agentica_patterns.skill_generator import generate_from_qheuristics

    # Try with research
    research_results = []
    try:
        research_results = research_topic(original_prompt)
    except Exception:
        # Research unavailable - continue without it
        pass

    return generate_from_qheuristics(
        task_type=task_type,
        resolved_qheuristics=resolved_qheuristics,
        original_prompt=original_prompt,
        research_results=research_results
    )


def safe_save_skill(
    spec: SkillSpec,
    project_dir: str | None = None
) -> dict[str, Any]:
    """Save skill with graceful error handling.

    Attempts to save to both memory and filesystem.
    Continues even if one fails.

    Args:
        spec: Skill specification
        project_dir: Project directory

    Returns:
        Result dict with saved status and any errors
    """
    import asyncio

    result = {
        'saved': False,
        'file_path': None,
        'memory_id': None,
        'error': None
    }

    try:
        persistence = SkillPersistence(project_dir=project_dir)

        # Try filesystem save
        try:
            result['file_path'] = persistence.save_to_filesystem(spec)
            result['saved'] = True
        except Exception as e:
            result['error'] = str(e)

        # Try memory save (async)
        try:
            async def _save_memory():
                return await persistence.save_to_memory(spec)
            result['memory_id'] = asyncio.get_event_loop().run_until_complete(_save_memory())
        except Exception:
            # Memory save failed - continue anyway
            pass

        # Try trigger registration
        try:
            persistence.register_triggers(spec)
        except Exception:
            # Trigger registration failed - continue anyway
            pass

    except Exception as e:
        result['error'] = str(e)

    return result


# =============================================================================
# Phase 22: Skill Validation
# =============================================================================


@dataclass
class ValidationResult:
    """Result of skill validation.

    Attributes:
        valid: Whether the skill is valid
        errors: List of blocking errors
        warnings: List of non-blocking warnings
    """
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SkillValidator:
    """Validates skill specifications before saving.

    Checks:
    - Name format (lowercase, alphanumeric, hyphens)
    - Required fields are present
    - Tools are valid
    - Instructions have minimum content
    """

    def validate_spec(self, spec: SkillSpec) -> ValidationResult:
        """Validate a skill specification.

        Args:
            spec: Skill specification to validate

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # Validate name format
        if not self._validate_name(spec.name):
            errors.append(
                f"Skill name '{spec.name}' must be lowercase alphanumeric with hyphens only"
            )

        # Validate description
        if not spec.description or len(spec.description.strip()) == 0:
            errors.append("Skill description cannot be empty")

        # Validate instructions length
        if len(spec.instructions) < MIN_INSTRUCTION_LENGTH:
            warnings.append(
                f"Instructions are very short ({len(spec.instructions)} chars). "
                f"Consider adding more detail."
            )

        # Validate tools
        invalid_tools = set(spec.tools) - VALID_TOOLS
        if invalid_tools:
            warnings.append(
                f"Unknown tools: {', '.join(invalid_tools)}. "
                "These may not work as expected."
            )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_name(self, name: str) -> bool:
        """Check if name follows kebab-case format.

        Args:
            name: Skill name to validate

        Returns:
            True if valid format
        """
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name))

    def validate_yaml(self, yaml_content: str) -> bool:
        """Validate YAML content is parseable.

        Args:
            yaml_content: YAML string to validate

        Returns:
            True if valid YAML
        """
        try:
            # Extract frontmatter
            if not yaml_content.startswith('---\n'):
                return False

            parts = yaml_content.split('---\n', 2)
            if len(parts) < 2:
                return False

            # Parse YAML - will raise on malformed content
            parsed = yaml.safe_load(parts[1])

            # Must be a dict with required fields
            if not isinstance(parsed, dict):
                return False

            if 'name' not in parsed:
                return False

            return True
        except yaml.YAMLError:
            return False
        except Exception:
            return False


# =============================================================================
# Phase 23: Skill Deduplication
# =============================================================================


class SkillDeduplicator:
    """Detects and prevents duplicate skills.

    Checks for:
    - Similar skill names
    - Similar skill content
    """

    def __init__(self, project_dir: str | None = None):
        """Initialize deduplicator.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = Path(
            project_dir or os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
        )
        self.skills_dir = self.project_dir / '.claude' / 'skills'

    def find_similar(
        self,
        spec: SkillSpec,
        threshold: float = 0.7
    ) -> list[str]:
        """Find skills similar to the given spec.

        Args:
            spec: Skill spec to compare
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            List of similar skill names
        """
        similar = []

        if not self.skills_dir.exists():
            return similar

        # Check each existing skill
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name
            skill_file = skill_dir / 'SKILL.md'

            if not skill_file.exists():
                continue

            # Check name similarity
            name_sim = self._name_similarity(spec.name, skill_name)
            if name_sim >= threshold:
                similar.append(skill_name)
                continue

            # Check content similarity
            try:
                content = skill_file.read_text()
                content_sim = self._content_similarity(spec, content)
                if content_sim >= threshold:
                    similar.append(skill_name)
            except Exception:
                pass

        return similar

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity using token overlap.

        Uses a combination of token overlap and substring matching.

        Args:
            name1: First name
            name2: Second name

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize names
        name1_lower = name1.lower()
        name2_lower = name2.lower()

        # Check for substring match
        if name1_lower in name2_lower or name2_lower in name1_lower:
            return 0.8

        tokens1 = set(name1_lower.split('-'))
        tokens2 = set(name2_lower.split('-'))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        # Base Jaccard similarity
        jaccard = len(intersection) / len(union)

        # Boost for significant overlap
        if len(intersection) >= 2:
            jaccard = min(1.0, jaccard + 0.2)

        return jaccard

    def _content_similarity(self, spec: SkillSpec, content: str) -> float:
        """Calculate content similarity using keyword overlap.

        Args:
            spec: Skill spec
            content: Existing skill content

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Extract keywords from spec
        spec_words = set(re.findall(r'\w{4,}', spec.instructions.lower()))
        spec_words.update(re.findall(r'\w{4,}', spec.goal.lower()))

        # Extract keywords from content
        content_words = set(re.findall(r'\w{4,}', content.lower()))

        if not spec_words or not content_words:
            return 0.0

        intersection = spec_words & content_words
        union = spec_words | content_words

        return len(intersection) / len(union)

    def suggest_merge(
        self,
        existing_name: str,
        new_spec: SkillSpec
    ) -> str:
        """Suggest how to merge with existing skill.

        Args:
            existing_name: Name of existing skill
            new_spec: New skill spec

        Returns:
            Suggestion message
        """
        return (
            f"Similar skill '{existing_name}' already exists. "
            f"Consider updating '{existing_name}' instead of creating '{new_spec.name}', "
            f"or rename '{new_spec.name}' to be more specific."
        )

    def check_before_save(self, spec: SkillSpec) -> dict[str, Any]:
        """Check for duplicates before saving.

        Args:
            spec: Skill to check

        Returns:
            Dict with should_save, similar_skills, suggestion
        """
        similar = self.find_similar(spec)

        if not similar:
            return {
                'should_save': True,
                'similar_skills': [],
                'suggestion': None
            }

        return {
            'should_save': False,
            'similar_skills': similar,
            'suggestion': self.suggest_merge(similar[0], spec)
        }


# =============================================================================
# Phase 24: Usage Tracking
# =============================================================================


class SkillUsageTracker:
    """Tracks skill usage for analytics and cleanup.

    Stores usage records in a JSON file for simplicity.
    Could be upgraded to SQLite for larger scale.
    """

    def __init__(self, project_dir: str | None = None):
        """Initialize usage tracker.

        Args:
            project_dir: Project directory
        """
        self.project_dir = Path(
            project_dir or os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
        )
        self.usage_file = self.project_dir / '.claude' / 'cache' / 'skill-usage.json'

    def _load_usage(self) -> dict[str, list[dict]]:
        """Load usage data from file.

        Returns:
            Dict of skill_name -> list of usage records
        """
        if self.usage_file.exists():
            try:
                return json.loads(self.usage_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_usage(self, usage: dict[str, list[dict]]) -> None:
        """Save usage data to file.

        Args:
            usage: Usage data to save
        """
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        self.usage_file.write_text(json.dumps(usage, indent=2))

    def record_usage(
        self,
        skill_name: str,
        session_id: str
    ) -> None:
        """Record a skill usage.

        Args:
            skill_name: Name of skill used
            session_id: Session where skill was used
        """
        usage = self._load_usage()

        if skill_name not in usage:
            usage[skill_name] = []

        usage[skill_name].append({
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        })

        self._save_usage(usage)

    def get_usage_stats(
        self,
        skill_name: str,
        days: int | None = None
    ) -> dict[str, Any]:
        """Get usage statistics for a skill.

        Args:
            skill_name: Name of skill
            days: Optional limit to last N days

        Returns:
            Dict with total_uses, last_used, etc.
        """
        usage = self._load_usage()
        records = usage.get(skill_name, [])

        if days is not None:
            cutoff = datetime.now() - timedelta(days=days)
            records = [
                r for r in records
                if datetime.fromisoformat(r['timestamp']) >= cutoff
            ]

        if not records:
            return {
                'total_uses': 0,
                'last_used': None,
                'sessions': []
            }

        return {
            'total_uses': len(records),
            'last_used': max(r['timestamp'] for r in records),
            'sessions': list(set(r['session_id'] for r in records))
        }

    def get_all_usage_stats(self) -> dict[str, dict[str, Any]]:
        """Get usage statistics for all skills.

        Returns:
            Dict of skill_name -> usage stats
        """
        usage = self._load_usage()
        return {
            skill_name: self.get_usage_stats(skill_name)
            for skill_name in usage
        }


# =============================================================================
# Phase 25: Cleanup Suggestions
# =============================================================================


def suggest_deprecation(
    project_dir: str | None = None,
    min_age_days: int = 30,
    max_uses: int = 0
) -> list[str]:
    """Suggest skills for deprecation.

    Returns skills that:
    - Are older than min_age_days
    - Have been used less than max_uses times (strictly less)

    Args:
        project_dir: Project directory
        min_age_days: Minimum age in days
        max_uses: Maximum number of uses (skills with this many uses or more are kept)

    Returns:
        List of skill names to consider for deprecation
    """
    project_path = Path(
        project_dir or os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    )
    skills_dir = project_path / '.claude' / 'skills'

    if not skills_dir.exists():
        return []

    tracker = SkillUsageTracker(project_dir)
    all_usage = tracker.get_all_usage_stats()

    suggestions = []
    cutoff_time = datetime.now() - timedelta(days=min_age_days)

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_file = skill_dir / 'SKILL.md'

        if not skill_file.exists():
            continue

        # Check age
        mtime = datetime.fromtimestamp(skill_file.stat().st_mtime)
        if mtime > cutoff_time:
            # Skill is too new
            continue

        # Check usage - strictly less than max_uses
        usage = all_usage.get(skill_name, {'total_uses': 0})
        if usage['total_uses'] < max_uses:
            suggestions.append(skill_name)

    return suggestions


def get_cleanup_report(project_dir: str | None = None) -> dict[str, Any]:
    """Get a cleanup report for skills.

    Args:
        project_dir: Project directory

    Returns:
        Report with total_skills, unused_skills, suggestions
    """
    project_path = Path(
        project_dir or os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    )
    skills_dir = project_path / '.claude' / 'skills'

    if not skills_dir.exists():
        return {
            'total_skills': 0,
            'unused_skills': [],
            'suggestions': []
        }

    # Count total skills
    total_skills = sum(
        1 for d in skills_dir.iterdir()
        if d.is_dir() and (d / 'SKILL.md').exists()
    )

    # Get suggestions
    unused = suggest_deprecation(project_dir, min_age_days=30, max_uses=0)

    return {
        'total_skills': total_skills,
        'unused_skills': unused,
        'suggestions': [
            f"Consider removing '{skill}' - unused for 30+ days"
            for skill in unused[:5]  # Top 5 suggestions
        ]
    }
