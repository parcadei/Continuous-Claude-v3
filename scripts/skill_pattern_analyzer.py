"""Skill Pattern Analyzer (Phase 3 Tasks 3.1-3.6).

USAGE:
    from scripts.skill_pattern_analyzer import (
        analyze_corrections,
        identify_weak_patterns,
        suggest_improved_pattern,
        compute_pattern_suggestion,
        apply_pattern_suggestion,
        validate_applied_pattern
    )

    # Analyze corrections for a skill
    corrections = load_corrections("deploy-api")
    suggestions = analyze_corrections(corrections)

    # Identify weak patterns
    weak = identify_weak_patterns(corrections)

    # Get improved pattern for a param
    suggestion = suggest_improved_pattern("hosting", corrections)

    # Apply suggestion to SKILL.md
    apply_pattern_suggestion(skill_path, suggestion)

Pattern analysis:
- Counts correction frequency per parameter
- Identifies parameters with >20% correction rate as "weak"
- Generates improved infer_from patterns from context keywords
- Applies patterns atomically with validation
"""

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.skill_feedback import CorrectionRecord
from scripts.skill_validator import verify_yaml_structure


# Correction rate threshold for weak pattern detection
WEAK_PATTERN_THRESHOLD = 0.2  # 20%
MIN_CORRECTIONS_FOR_SUGGESTION = 2  # Require at least 2 corrections


@dataclass
class PatternSuggestion:
    """Suggested pattern improvement."""
    param: str
    pattern: str
    priority_values: dict[str, list[str]]  # value -> context keywords
    confidence: float = 0.5


def analyze_corrections(corrections: list[CorrectionRecord]) -> list[dict[str, Any]]:
    """Analyze corrections and return pattern suggestions.

    Task 3.1: Main entry point for pattern analysis.

    Args:
        corrections: List of correction records to analyze

    Returns:
        List of suggestion dicts with 'param', 'pattern', etc.
    """
    if not corrections:
        return []

    suggestions = []

    # Group by parameter
    params = set(c.param for c in corrections)

    for param in params:
        param_corrections = [c for c in corrections if c.param == param]

        if len(param_corrections) >= MIN_CORRECTIONS_FOR_SUGGESTION:
            suggestion = suggest_improved_pattern(param, param_corrections)
            if suggestion:
                suggestions.append(suggestion)

    return suggestions


def identify_weak_patterns(corrections: list[CorrectionRecord]) -> list[str]:
    """Identify parameters with high correction rates.

    Task 3.2: Flags parameters with >20% correction rate as weak.

    Args:
        corrections: List of correction records

    Returns:
        List of parameter names that are "weak" (need refinement)
    """
    if not corrections:
        return []

    # Count corrections per parameter
    param_counts = Counter(c.param for c in corrections)

    # For simplicity, flag parameters with >= MIN_CORRECTIONS_FOR_SUGGESTION
    # In production, would compare against total invocations
    weak = []
    for param, count in param_counts.items():
        if count >= MIN_CORRECTIONS_FOR_SUGGESTION:
            weak.append(param)

    return weak


def _extract_keywords(context: str) -> list[str]:
    """Extract meaningful keywords from context string."""
    # Remove common words
    stop_words = {
        'a', 'an', 'the', 'to', 'for', 'of', 'in', 'on', 'at', 'by',
        'with', 'from', 'please', 'using', 'use', 'my', 'our', 'this'
    }

    # Tokenize and filter
    words = re.findall(r'\b[a-zA-Z]{3,}\b', context.lower())
    keywords = [w for w in words if w not in stop_words]

    return keywords


def suggest_improved_pattern(
    param: str,
    corrections: list[CorrectionRecord]
) -> dict[str, Any] | None:
    """Generate improved pattern suggestion from corrections.

    Task 3.3: Analyzes correction contexts to suggest better regex.

    Args:
        param: Parameter name
        corrections: Corrections for this parameter

    Returns:
        Suggestion dict or None if insufficient data
    """
    if len(corrections) < MIN_CORRECTIONS_FOR_SUGGESTION:
        return None

    return compute_pattern_suggestion(param, corrections)


def compute_pattern_suggestion(
    param: str,
    corrections: list[CorrectionRecord]
) -> dict[str, Any]:
    """Pure function to compute pattern suggestion.

    Task 3.4: No side effects, returns suggestion dict.

    Args:
        param: Parameter name
        corrections: Corrections for this parameter

    Returns:
        Suggestion dict with 'param', 'pattern', 'keywords', 'priority_values'
    """
    # Collect all values and their contexts
    value_contexts: dict[str, list[str]] = {}
    all_values = set()

    for c in corrections:
        all_values.add(c.old_value)
        all_values.add(c.new_value)

        # Associate context keywords with corrected value
        if c.new_value not in value_contexts:
            value_contexts[c.new_value] = []
        value_contexts[c.new_value].extend(_extract_keywords(c.context))

    # Build priority keywords per value
    priority_values: dict[str, list[str]] = {}
    for value, keywords in value_contexts.items():
        # Get most common keywords for this value
        keyword_counts = Counter(keywords)
        top_keywords = [kw for kw, _ in keyword_counts.most_common(5)]
        if top_keywords:
            priority_values[value] = top_keywords

    # Generate base pattern from all values
    pattern_parts = sorted(all_values, key=len, reverse=True)
    base_pattern = "|".join(re.escape(v) for v in pattern_parts)

    # Add context keywords to pattern
    all_keywords = set()
    for kws in priority_values.values():
        all_keywords.update(kws)

    return {
        "param": param,
        "pattern": base_pattern,
        "keywords": list(all_keywords)[:10],  # Top 10 keywords
        "priority_values": priority_values
    }


def apply_pattern_suggestion(
    skill_path: str | Path,
    suggestion: dict[str, Any]
) -> bool:
    """Apply pattern suggestion to SKILL.md.

    Task 3.5: Modifies SKILL.md with new infer_from pattern.

    Args:
        skill_path: Path to skill directory
        suggestion: Suggestion dict from compute_pattern_suggestion

    Returns:
        True if applied successfully
    """
    path = Path(skill_path)

    if path.is_dir():
        skill_file = path / "SKILL.md"
    else:
        skill_file = path

    if not skill_file.exists():
        return False

    content = skill_file.read_text()

    # Extract frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if not match:
        return False

    frontmatter_str = match.group(1)
    body = match.group(2)

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError:
        return False

    if not isinstance(frontmatter, dict):
        return False

    # Update or add the parameter pattern
    param = suggestion["param"]
    pattern = suggestion["pattern"]

    if "parameters" not in frontmatter:
        frontmatter["parameters"] = {}

    if param not in frontmatter["parameters"]:
        frontmatter["parameters"][param] = {}

    frontmatter["parameters"][param]["infer_from"] = pattern

    # Add priority_values if present
    if suggestion.get("priority_values"):
        frontmatter["parameters"][param]["priority_values"] = suggestion["priority_values"]

    # Reconstruct content
    new_frontmatter = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    new_content = f"---\n{new_frontmatter}---\n{body}"

    # Write atomically
    skill_file.write_text(new_content)

    return True


def validate_applied_pattern(skill_path: str | Path) -> bool:
    """Validate that SKILL.md is still valid after pattern application.

    Task 3.6: Post-application validation.

    Args:
        skill_path: Path to skill directory

    Returns:
        True if SKILL.md is valid YAML
    """
    path = Path(skill_path)

    if path.is_dir():
        skill_file = path / "SKILL.md"
    else:
        skill_file = path

    if not skill_file.exists():
        return False

    content = skill_file.read_text()

    # Use existing validator
    result = verify_yaml_structure(content)

    return result.is_valid
