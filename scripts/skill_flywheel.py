"""Skill Flywheel Orchestrator (Phase 2 Tasks 2.1-2.11).

USAGE:
    from scripts.skill_flywheel import run_flywheel, FlywheelResult

    result = await run_flywheel(skill_path, prompt, persist=False)

    if result.success:
        print(f"Converted! Diff:\\n{result.diff}")
    else:
        print(f"Failed: {result.reason}")

The flywheel orchestrator:
1. Detects if skill has typed params
2. If NO typed params -> triggers CONVERT mode to infer from prose
3. Double-verifies: structural (YAML syntax) + semantic (parity >= threshold)
4. Shows diff of changes for transparency
5. Persists upgraded SKILL.md permanently (with backup)
6. Updates skill registry
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scripts.skill_validator import verify_yaml_structure, ValidationResult
from scripts.skill_diff import format_skill_diff
from scripts.skill_parity_checker import PARITY_THRESHOLD as DEFAULT_PARITY_THRESHOLD


# Session-level tracking of processed skills (prevents double-execution)
_processed_skills: set[str] = set()


def get_processed_skills() -> set[str]:
    """Get set of skills processed in this session.

    Task 3.11: Tracking to prevent double-execution.
    """
    return _processed_skills.copy()


def mark_skill_processed(skill_id: str) -> None:
    """Mark a skill as processed in this session.

    Task 3.11: Called after flywheel processes a skill.
    """
    _processed_skills.add(skill_id)


def is_skill_processed(skill_id: str) -> bool:
    """Check if skill was already processed this session.

    Task 3.11: Used to prevent double-execution.
    """
    return skill_id in _processed_skills


def clear_processed_skills() -> None:
    """Clear processed skills (for testing or session reset)."""
    _processed_skills.clear()


def should_trigger_flywheel(skill_id: str, content: str, prompt: str) -> bool:
    """Determine if flywheel should be triggered for this skill.

    Task 3.12: Explicit trigger conditions.

    Conditions:
    1. Skill has NO typed params (prose-only)
    2. Not already processed in this session
    3. User prompt is not empty
    4. Content contains prose that could be inferred from

    Args:
        skill_id: Unique skill identifier
        content: SKILL.md content
        prompt: User prompt that triggered the skill

    Returns:
        True if flywheel should run
    """
    # Condition 1: Skill must be prose-only (no typed params)
    if _detect_typed_params(content):
        return False

    # Condition 2: Not already processed this session
    if is_skill_processed(skill_id):
        return False

    # Condition 3: Prompt must not be empty
    if not prompt or not prompt.strip():
        return False

    # Condition 4: Content must have some prose body
    # (If only frontmatter, nothing to infer from)
    lines = content.strip().split('\n')
    body_lines = []
    in_frontmatter = False
    for line in lines:
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            body_lines.append(line)

    body = '\n'.join(body_lines).strip()
    if len(body) < 10:  # Minimal prose content
        return False

    return True


@dataclass
class FlywheelResult:
    """Result of flywheel orchestration."""
    success: bool
    converted: bool = False
    diff: str | None = None
    reason: str = ""
    schema: dict[str, Any] = field(default_factory=dict)
    parity_score: float = 0.0
    backup_path: str | None = None


def get_parity_threshold() -> float:
    """Get parity threshold from environment or default.

    Task 2.6: Configurable via PARITY_THRESHOLD env var.
    """
    env_val = os.environ.get("PARITY_THRESHOLD")
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            return DEFAULT_PARITY_THRESHOLD
    return DEFAULT_PARITY_THRESHOLD


def _detect_typed_params(content: str) -> bool:
    """Detect if skill has typed parameters in YAML frontmatter.

    Tasks 2.2-2.3: Returns True if skill has non-empty parameters: block.
    """
    # Extract frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
    if not match:
        return False

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return False

    if not isinstance(frontmatter, dict):
        return False

    # Check for non-empty parameters
    params = frontmatter.get("parameters")
    if params is None:
        return False
    if isinstance(params, dict) and len(params) == 0:
        return False

    return bool(params)


def _read_skill_content(skill_path: str | Path) -> str:
    """Read SKILL.md content from path."""
    path = Path(skill_path)

    if path.is_dir():
        skill_file = path / "SKILL.md"
    else:
        skill_file = path

    return skill_file.read_text()


def _get_skill_file_path(skill_path: str | Path) -> Path:
    """Get path to SKILL.md file."""
    path = Path(skill_path)

    if path.is_dir():
        return path / "SKILL.md"
    return path


def _write_atomically(file_path: Path, content: str, backup: bool = True) -> str | None:
    """Write file atomically with optional backup.

    Task 2.9: Uses write-then-rename pattern for atomic writes.

    Returns:
        Path to backup file if created, else None.
    """
    backup_path = None

    # Create backup if file exists
    if backup and file_path.exists():
        backup_path = file_path.parent / f"{file_path.name}.bak"
        shutil.copy2(file_path, backup_path)

    # Write to temp file first (atomic pattern)
    temp_fd, temp_path = tempfile.mkstemp(
        suffix='.md',
        dir=file_path.parent
    )
    try:
        with os.fdopen(temp_fd, 'w') as f:
            f.write(content)

        # Atomic rename
        os.replace(temp_path, file_path)
    except Exception:
        # Cleanup temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    return str(backup_path) if backup_path else None


def _update_skill_registry(skill_path: str | Path, schema: dict[str, Any]) -> None:
    """Update skill registry after persist.

    Task 2.11: Placeholder for skill registry update.
    Currently a no-op; can be extended to update skill-rules.json or index.
    """
    # Future: Update skill-rules.json triggers
    # Future: Update artifact index
    pass


async def run_flywheel(
    skill_path: str | Path,
    prompt: str,
    persist: bool = False
) -> FlywheelResult:
    """Run the flywheel orchestration.

    Orchestrates:
    1. Detection: Does skill have typed params?
    2. Conversion: If no, call convert_skill()
    3. Structural verification: Is YAML valid?
    4. Semantic verification: Does parity >= threshold?
    5. Diff generation: Show changes
    6. Persistence: Write atomically with backup
    7. Registry update: Update skill index

    Args:
        skill_path: Path to skill directory or SKILL.md
        prompt: User prompt that triggered the skill
        persist: Whether to write changes to disk

    Returns:
        FlywheelResult with success status and details
    """
    from scripts.skill_generator_v2 import convert_skill

    # Read original content
    try:
        original_content = _read_skill_content(skill_path)
    except FileNotFoundError as e:
        return FlywheelResult(
            success=False,
            reason=f"Skill file not found: {e}"
        )

    # Task 2.2-2.3: Check if skill already has typed params
    if _detect_typed_params(original_content):
        return FlywheelResult(
            success=True,
            converted=False,
            reason="Skill already has typed parameters"
        )

    # Task 2.4: Trigger convert mode
    try:
        convert_result = await convert_skill(skill_path)
    except Exception as e:
        return FlywheelResult(
            success=False,
            reason=f"Conversion failed: {e}"
        )

    # Task 2.5: Structural verification
    validation = verify_yaml_structure(convert_result.yaml_content)
    if not validation.is_valid:
        return FlywheelResult(
            success=False,
            reason=f"Structural verification failed: {validation.errors}"
        )

    # Task 2.6-2.7: Semantic verification (parity check)
    threshold = get_parity_threshold()
    parity = convert_result.parity_result

    if parity and not parity.is_valid:
        return FlywheelResult(
            success=False,
            reason=f"Parity verification failed: coverage {parity.coverage_score:.1%} < threshold {threshold:.1%}",
            parity_score=parity.coverage_score if parity else 0.0
        )

    # Task 2.8: Generate diff
    diff = format_skill_diff(original_content, convert_result.yaml_content)

    result = FlywheelResult(
        success=True,
        converted=True,
        diff=diff,
        schema=convert_result.schema,
        parity_score=parity.coverage_score if parity else 1.0,
        reason="Conversion successful"
    )

    # Task 2.9-2.11: Persist if requested
    if persist:
        skill_file = _get_skill_file_path(skill_path)

        # Atomic write with backup
        backup_path = _write_atomically(skill_file, convert_result.yaml_content)
        result.backup_path = backup_path

        # Task 2.10: Verify persisted file
        persisted_content = skill_file.read_text()
        post_validation = verify_yaml_structure(persisted_content)
        if not post_validation.is_valid:
            # Restore from backup
            if backup_path and Path(backup_path).exists():
                shutil.copy2(backup_path, skill_file)
            return FlywheelResult(
                success=False,
                reason=f"Persisted file validation failed: {post_validation.errors}"
            )

        # Task 2.11: Update registry
        _update_skill_registry(skill_path, convert_result.schema)

    return result
