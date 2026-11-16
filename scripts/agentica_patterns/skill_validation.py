"""
Skill name validation to prevent path traversal attacks.

Security: Validates skillName from memory metadata before use in path construction.
This module provides defense-in-depth against path traversal attacks when skill names
are used to construct filesystem paths.

Usage:
    from scripts.agentica_patterns.skill_validation import (
        is_valid_skill_name,
        sanitize_skill_name,
        validate_skill_path
    )

    # Primary validation
    if is_valid_skill_name(skill_name):
        path = Path(skills_dir) / skill_name / "SKILL.md"

    # Fallback sanitization (defense in depth)
    safe_name = sanitize_skill_name(untrusted_name)

    # Full path validation (final check)
    if validate_skill_path(skill_name, skills_dir, constructed_path):
        # Safe to use
"""

import re
from pathlib import Path

# Maximum allowed skill name length
MAX_SKILL_NAME_LENGTH = 100

# Valid skill name pattern: alphanumeric start, can contain hyphens and underscores
# NO forward slashes allowed (flat skill structure for security)
VALID_SKILL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$|^[a-zA-Z0-9]$")

# Dangerous patterns to reject
DANGEROUS_PATTERNS = [
    r"\.\.",  # Parent directory traversal
    r"^/",  # Absolute path
    r"/",  # Any path separator (no nested skills)
    r"\\",  # Backslash (Windows traversal)
    r"%[0-9a-fA-F]{2}",  # URL encoding
    r"\x00",  # Null byte
    r"^~",  # Home directory expansion
    r"^\.",  # Leading dot (hidden files)
    r";",  # Shell semicolon
    r"\$\(",  # Subshell syntax $(
    r"`",  # Backtick command substitution
    r"\s",  # Whitespace
]


def is_valid_skill_name(name: str | None) -> bool:
    """
    Validate skill name for safe use in path construction.

    Returns True only if name is safe to use in path.join().

    Security requirements:
    - Only alphanumeric, hyphens, and underscores allowed
    - Must start with alphanumeric
    - No path separators (/ or \\)
    - No traversal sequences (..)
    - No URL encoding
    - No null bytes
    - No shell metacharacters
    - Max 100 characters

    Args:
        name: The skill name to validate

    Returns:
        True if the name is safe to use in path construction, False otherwise
    """
    if name is None or not isinstance(name, str):
        return False

    if not name or len(name) > MAX_SKILL_NAME_LENGTH:
        return False

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, name):
            return False

    # Must match valid pattern (alphanumeric with hyphens/underscores only)
    if not VALID_SKILL_NAME_PATTERN.match(name):
        return False

    return True


def sanitize_skill_name(name: str | None) -> str:
    """
    Sanitize skill name by removing dangerous characters.

    This is a fallback defense - prefer validation and rejection over sanitization.
    Returns empty string if the input is completely invalid or cannot be made safe.

    Sanitization steps:
    1. Remove path traversal sequences (..)
    2. Remove path separators (/ and \\)
    3. Remove URL encoding patterns
    4. Remove null bytes
    5. Remove shell metacharacters
    6. Remove whitespace
    7. Remove leading dots
    8. Truncate to max length

    Args:
        name: The skill name to sanitize

    Returns:
        Sanitized name or empty string if completely invalid
    """
    if name is None or not isinstance(name, str):
        return ""

    result = name

    # Remove path traversal sequences
    result = re.sub(r"\.\.+", "", result)

    # Remove all path separators
    result = re.sub(r"[/\\]+", "", result)

    # Remove URL encoding patterns
    result = re.sub(r"%[0-9a-fA-F]{2}", "", result)

    # Remove null bytes
    result = result.replace("\x00", "")

    # Remove shell metacharacters
    result = re.sub(r'[;`$()|\'"<>]', "", result)

    # Remove whitespace
    result = re.sub(r"\s+", "", result)

    # Remove leading dots
    result = re.sub(r"^\.+", "", result)

    # Remove home directory expansion
    result = re.sub(r"^~", "", result)

    # Truncate to max length
    result = result[:MAX_SKILL_NAME_LENGTH]

    # Final validation - must have valid characters remaining
    if not result:
        return ""

    # Check that remaining characters are valid
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", result):
        # Try to extract valid parts
        result = re.sub(r"[^a-zA-Z0-9_-]", "", result)

        # If still doesn't start with alphanumeric, try to fix
        if result and not result[0].isalnum():
            # Remove leading non-alphanumeric
            result = re.sub(r"^[^a-zA-Z0-9]+", "", result)

    # Final check - if nothing valid remains, return empty
    if not result or not result[0].isalnum():
        return ""

    return result


def validate_skill_path(skill_name: str, skills_dir: str, constructed_path: str) -> bool:
    """
    Validate that constructed path is safely within skills_dir.

    This is a defense-in-depth check that should be performed AFTER path construction
    to catch any bypass attempts that made it through name validation.

    Uses realpath() to resolve symlinks, ensuring the actual filesystem path
    is within the skills directory.

    Args:
        skill_name: The skill name that was used
        skills_dir: The base skills directory (e.g., /home/user/.claude/skills)
        constructed_path: The full path that was constructed

    Returns:
        True if the path is safely within skills_dir, False otherwise
    """
    # First validate the skill name itself
    if not is_valid_skill_name(skill_name):
        return False

    try:
        # Convert to Path objects and resolve to absolute paths
        skills_resolved = Path(skills_dir).resolve()
        path_resolved = Path(constructed_path).resolve()

        # Check containment - constructed path must be under skills directory
        # Use string comparison with trailing slash to prevent prefix attacks
        # e.g., /home/user/.claude/skills-evil would match /home/user/.claude/skills
        skills_str = str(skills_resolved)
        path_str = str(path_resolved)

        # Path must start with skills_dir + / (not just skills_dir prefix)
        if not path_str.startswith(skills_str + "/") and path_str != skills_str:
            return False

        return True

    except (OSError, ValueError, RuntimeError):
        # Any path resolution error means the path is suspicious
        return False
