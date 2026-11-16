"""Skill Execution Feedback Capture (Phase 2 Tasks 2.12-2.14).

USAGE:
    from scripts.skill_feedback import capture_correction, persist_correction

    # Capture a user correction
    correction = capture_correction(
        skill_id="deploy-api",
        param="hosting",
        old_value="aws",
        new_value="gcp",
        context="User said deploy to GCP"
    )

    # Persist to disk
    persist_correction(correction)

    # Load corrections for analysis
    corrections = load_corrections("deploy-api")

Corrections are stored in .jsonl format at:
    .claude/cache/skill-corrections/{skill_id}.jsonl
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CorrectionRecord:
    """Record of a user correction to an inferred parameter.

    Task 2.13: Defines the correction record schema.

    Fields:
        skill_id: Name of the skill being corrected
        param: Parameter name that was corrected
        old_value: Original inferred value
        new_value: User's corrected value
        timestamp: ISO timestamp of correction
        context: Original user prompt or context
    """
    skill_id: str
    param: str
    old_value: str
    new_value: str
    timestamp: str
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CorrectionRecord':
        """Create from dictionary."""
        return cls(**data)


def get_corrections_dir() -> Path:
    """Get the corrections cache directory.

    Default: .claude/cache/skill-corrections/
    Can be overridden for testing.
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    return Path(project_dir) / ".claude" / "cache" / "skill-corrections"


def capture_correction(
    skill_id: str,
    param: str,
    old_value: str,
    new_value: str,
    context: str = ""
) -> CorrectionRecord:
    """Capture a user correction to an inferred parameter.

    Task 2.12: Creates a CorrectionRecord in memory.

    Args:
        skill_id: Name of the skill being corrected
        param: Parameter name that was corrected
        old_value: Original inferred value
        new_value: User's corrected value
        context: Optional context (user prompt)

    Returns:
        CorrectionRecord with auto-generated timestamp
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    return CorrectionRecord(
        skill_id=skill_id,
        param=param,
        old_value=old_value,
        new_value=new_value,
        timestamp=timestamp,
        context=context
    )


def persist_correction(correction: CorrectionRecord) -> Path:
    """Persist a correction record to disk.

    Task 2.14: Stores corrections in .jsonl format.

    File format: One JSON object per line (JSONL)
    Location: .claude/cache/skill-corrections/{skill_id}.jsonl

    Args:
        correction: The correction record to persist

    Returns:
        Path to the corrections file
    """
    corrections_dir = get_corrections_dir()
    corrections_dir.mkdir(parents=True, exist_ok=True)

    file_path = corrections_dir / f"{correction.skill_id}.jsonl"

    # Append to file (JSONL format)
    with open(file_path, 'a') as f:
        f.write(json.dumps(correction.to_dict()) + '\n')

    return file_path


def load_corrections(skill_id: str) -> list[CorrectionRecord]:
    """Load all corrections for a skill.

    Task 2.14c: Loads corrections from .jsonl file.

    Args:
        skill_id: Name of the skill

    Returns:
        List of CorrectionRecord objects (empty if none)
    """
    corrections_dir = get_corrections_dir()
    file_path = corrections_dir / f"{skill_id}.jsonl"

    if not file_path.exists():
        return []

    corrections = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                corrections.append(CorrectionRecord.from_dict(data))

    return corrections


def get_correction_rate(skill_id: str, param: str) -> float:
    """Calculate correction rate for a parameter.

    Useful for identifying weak patterns.

    Args:
        skill_id: Name of the skill
        param: Parameter to analyze

    Returns:
        Correction rate (0.0 - 1.0, or 0.0 if no data)
    """
    corrections = load_corrections(skill_id)

    param_corrections = [c for c in corrections if c.param == param]

    if not param_corrections:
        return 0.0

    # For now, return 1.0 if any corrections exist
    # Future: Compare to total invocations
    return 1.0
