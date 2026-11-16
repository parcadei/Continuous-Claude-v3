"""Skill Persistence - Auto-save JIT skills to memory and filesystem.

Phases 13-15 of Self-Improving Skill System.

This module handles:
- Phase 13: Saving generated skills to memory (for semantic retrieval)
- Phase 14: Writing SKILL.md files to .claude/skills/ directory
- Phase 15: Registering skill triggers in skill-rules.json

Usage:
    from scripts.agentica_patterns.skill_persistence import SkillPersistence, save_skill
    from scripts.agentica_patterns.skill_generator import SkillSpec

    # Create persistence handler
    persistence = SkillPersistence(project_dir='/path/to/project')

    # Save a generated skill
    spec = SkillSpec(name='my-skill', ...)
    memory_id = await persistence.save_to_memory(spec)
    file_path = persistence.save_to_filesystem(spec)
    persistence.register_triggers(spec)

    # Or use convenience function
    result = await save_skill(spec, project_dir='/path/to/project')

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.agentica_patterns.skill_generator import SkillSpec, generate_skill_yaml
from scripts.agentica_patterns.skill_validation import is_valid_skill_name, validate_skill_path


class SecurityError(ValueError):
    """Raised when a security violation is detected (e.g., symlink attack)."""

    pass


# =============================================================================
# Memory Client Interface
# =============================================================================


@dataclass
class MemoryClient:
    """Simple memory client for skill storage.

    Wraps the memory service to store skill content with metadata.
    Designed for graceful fallback when memory service is unavailable.
    """

    session_id: str = "default"
    project_dir: str | None = None

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str | None:
        """Store content in memory.

        Args:
            content: The content to store
            metadata: Optional metadata to attach

        Returns:
            Memory ID if successful, None on failure
        """
        try:
            # Import memory factory dynamically to avoid circular imports
            import asyncio

            from scripts.agentica_patterns.memory_factory import create_default_memory_service

            async def _store():
                memory = create_default_memory_service(self.session_id)
                await memory.connect()
                memory_id = await memory.store(content, metadata=metadata or {})
                await memory.close()
                return memory_id

            # Run async function
            return asyncio.get_event_loop().run_until_complete(_store())
        except Exception:
            # Graceful fallback - return None on any error
            return None


# =============================================================================
# Skill Persistence Class
# =============================================================================


class SkillPersistence:
    """Handles persisting generated skills to memory and filesystem.

    Provides a unified interface for:
    - Storing skill content in memory for future semantic search
    - Writing SKILL.md files to the skills directory
    - Registering triggers in skill-rules.json

    Attributes:
        project_dir: Root directory of the project
        skills_dir: Path to .claude/skills/ directory
    """

    def __init__(self, project_dir: str | None = None, session_id: str = "default"):
        """Initialize skill persistence handler.

        Args:
            project_dir: Project root directory (defaults to CLAUDE_PROJECT_DIR or cwd)
            session_id: Session ID for memory isolation
        """
        self.project_dir = Path(project_dir or os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        self.skills_dir = self.project_dir / ".claude" / "skills"
        self._memory_client = MemoryClient(session_id=session_id, project_dir=str(self.project_dir))

    # =========================================================================
    # Phase 13: Memory Storage
    # =========================================================================

    async def save_to_memory(self, spec: SkillSpec) -> str | None:
        """Save skill to memory for future retrieval.

        Stores the skill YAML content with metadata for semantic search.

        Args:
            spec: The skill specification to store

        Returns:
            Memory ID if successful, None on failure
        """
        # Generate YAML content
        content = generate_skill_yaml(spec)

        # Build metadata
        metadata = {
            "type": "skill",
            "name": spec.name,
            "description": spec.description,
            "tools": spec.tools,
            "created": datetime.now().isoformat(),
            "triggers": spec.triggers,
        }

        # Store in memory
        memory_id = self._memory_client.store(content, metadata=metadata)

        return memory_id

    # =========================================================================
    # Phase 14: Filesystem Storage
    # =========================================================================

    def _safe_write_file(self, target_path: Path, content: str) -> None:
        """Atomically write file with symlink protection.

        Security: Uses temp file + rename to prevent TOCTOU, checks for symlinks.

        This prevents the race condition where:
        1. Path is validated
        2. Attacker swaps file/directory to symlink
        3. write_text() follows symlink to attacker-controlled location

        Args:
            target_path: The target file path to write
            content: The content to write

        Raises:
            SecurityError: If target or parent is a symlink
        """
        # Reject if target is a symlink (using lstat to not follow symlinks)
        if target_path.exists():
            try:
                os.lstat(target_path)  # Verify we can stat without following
                if os.path.islink(target_path):
                    raise SecurityError(f"Refusing to write to symlink: {target_path}")
            except OSError:
                pass  # File doesn't exist or can't stat

        # Reject if parent is a symlink
        if target_path.parent.is_symlink():
            raise SecurityError(f"Refusing to write in symlinked directory: {target_path.parent}")

        # Create parent directory if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename on same filesystem)
        fd = None
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(
                dir=str(target_path.parent), prefix=".tmp_", suffix=".tmp"
            )

            # Write content
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = None  # Mark as closed

            # Final symlink check before rename (defense in depth against TOCTOU race)
            if target_path.exists() and os.path.islink(target_path):
                os.unlink(temp_path)
                raise SecurityError(f"Target became symlink during write: {target_path}")

            # Atomic rename (POSIX guarantees atomicity on same filesystem)
            os.rename(temp_path, str(target_path))
            temp_path = None  # Mark as renamed (no cleanup needed)

        except Exception:
            # Clean up temp file on any error
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if temp_path is not None and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            raise

    def _safe_read_file(self, target_path: Path) -> str:
        """Read file with symlink protection.

        Args:
            target_path: The file to read

        Returns:
            File contents as string

        Raises:
            SecurityError: If target or parent is a symlink
        """
        if os.path.islink(target_path):
            raise SecurityError(f"Refusing to read symlink: {target_path}")

        if target_path.parent.is_symlink():
            raise SecurityError(f"Refusing to read from symlinked directory: {target_path.parent}")

        return target_path.read_text()

    def _validate_skill_name(self, name: str) -> str:
        """Validate and sanitize skill name to prevent path traversal.

        Security: Uses comprehensive validation from skill_validation module.
        Rejects names with path traversal sequences, shell metacharacters,
        URL encoding, null bytes, and other dangerous patterns.

        Args:
            name: The skill name to validate

        Returns:
            The validated skill name

        Raises:
            ValueError: If name fails validation
        """
        if not is_valid_skill_name(name):
            raise ValueError(f"Invalid skill name (path traversal or dangerous characters): {name}")

        return name

    def save_to_filesystem(self, spec: SkillSpec) -> str:
        """Save skill to filesystem as SKILL.md.

        Creates the skill directory and writes the SKILL.md file.
        Handles name collisions by appending a number suffix.

        Security:
        - Validates skill names to prevent path traversal attacks
        - Rejects symlink directories to prevent TOCTOU attacks
        - Uses atomic write with symlink protection

        Args:
            spec: The skill specification to write

        Returns:
            Absolute path to the created SKILL.md file

        Raises:
            ValueError: If skill name contains path traversal sequences
            SecurityError: If skill directory is a symlink (TOCTOU protection)
        """
        # Security: Validate skill name before any filesystem operations
        skill_name = self._validate_skill_name(spec.name)

        # Ensure skills directory exists
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Find unique skill name
        skill_dir = self.skills_dir / skill_name

        # Security: Reject if skill_dir is a symlink (TOCTOU protection)
        # Check BEFORE exists() to prevent symlink following
        if os.path.islink(skill_dir):
            raise SecurityError(f"Skill directory is a symlink, refusing to write: {skill_name}")

        if skill_dir.exists():
            # Handle name collision
            skill_name = self._find_unique_name(spec.name)
            skill_dir = self.skills_dir / skill_name

            # Security: Check new candidate too
            if os.path.islink(skill_dir):
                raise SecurityError(
                    f"Skill directory is a symlink, refusing to write: {skill_name}"
                )

        # Security: Verify resolved path is within skills directory
        resolved_skill_dir = skill_dir.resolve()
        resolved_skills_dir = self.skills_dir.resolve()
        if not str(resolved_skill_dir).startswith(str(resolved_skills_dir)):
            raise ValueError(f"Skill path escapes skills directory: {skill_name}")

        # Create skill directory (only if not a symlink - already checked above)
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Write SKILL.md using atomic write with symlink protection
        skill_path = skill_dir / "SKILL.md"

        # Security: Defense-in-depth path validation using skill_validation module
        if not validate_skill_path(skill_name, str(self.skills_dir), str(skill_path)):
            raise SecurityError(f"Invalid skill path (path escape detected): {skill_path}")

        content = generate_skill_yaml(spec)

        # Security: Use _safe_write_file instead of write_text to prevent TOCTOU
        self._safe_write_file(skill_path, content)

        return str(skill_path)

    def _find_unique_name(self, base_name: str) -> str:
        """Find a unique skill name by appending numbers.

        Args:
            base_name: The original skill name

        Returns:
            A unique skill name (e.g., 'my-skill-2')
        """
        counter = 2
        while True:
            candidate = f"{base_name}-{counter}"
            if not (self.skills_dir / candidate).exists():
                return candidate
            counter += 1

    # =========================================================================
    # Phase 15: Trigger Registration
    # =========================================================================

    def register_triggers(self, spec: SkillSpec) -> None:
        """Register skill triggers in skill-rules.json.

        Adds the skill to skill-rules.json with its keywords and intent patterns.
        Creates the file if it doesn't exist. Preserves existing entries.

        Args:
            spec: The skill specification with triggers
        """
        rules_path = self.skills_dir / "skill-rules.json"

        # Load existing rules or create new
        if rules_path.exists():
            with open(rules_path) as f:
                rules = json.load(f)
        else:
            rules = self._create_default_rules()

        # Ensure skills dict exists
        if "skills" not in rules:
            rules["skills"] = {}

        # Add skill entry
        rules["skills"][spec.name] = {
            "type": "domain",
            "enforcement": "suggest",
            "priority": "low",  # JIT skills start at low priority
            "description": spec.description,
            "promptTriggers": {
                "keywords": spec.triggers.get("keywords", []),
                "intentPatterns": spec.triggers.get("intentPatterns", []),
            },
        }

        # Write back with formatting
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        with open(rules_path, "w") as f:
            json.dump(rules, f, indent=2)

    def _create_default_rules(self) -> dict[str, Any]:
        """Create a default skill-rules.json structure.

        Returns:
            Default rules dictionary
        """
        return {
            "version": "1.0",
            "description": "Skill activation triggers for Claude Code.",
            "skills": {},
        }

    # =========================================================================
    # Exists Check
    # =========================================================================

    def exists(self, skill_name: str) -> bool:
        """Check if a skill exists in the filesystem.

        A skill exists if its directory contains a SKILL.md file.
        Uses lstat-based checks to avoid following symlinks.

        Security: Does NOT follow symlinks to prevent information disclosure
        attacks where a symlink points to sensitive external files.

        Args:
            skill_name: Name of the skill to check

        Returns:
            True if skill exists (and is not a symlink), False otherwise
        """
        skill_dir = self.skills_dir / skill_name

        # Security: Return False for symlink directories (lstat-based check)
        # This prevents following symlinks to external locations
        if os.path.islink(skill_dir):
            return False

        skill_path = skill_dir / "SKILL.md"

        # Security: Return False for symlink files
        if os.path.islink(skill_path):
            return False

        return skill_path.exists()


# =============================================================================
# Convenience Functions
# =============================================================================


async def save_skill(
    spec: SkillSpec, project_dir: str | None = None, session_id: str = "default"
) -> dict[str, Any]:
    """Save a skill to both memory and filesystem.

    Convenience function that:
    1. Saves to memory for semantic retrieval
    2. Saves to filesystem as SKILL.md
    3. Registers triggers in skill-rules.json

    Args:
        spec: The skill specification to save
        project_dir: Project root directory
        session_id: Session ID for memory isolation

    Returns:
        Dictionary with:
        - memory_id: ID from memory storage (or None)
        - file_path: Path to SKILL.md file
    """
    persistence = SkillPersistence(project_dir=project_dir, session_id=session_id)

    # Save to memory (may fail gracefully)
    memory_id = await persistence.save_to_memory(spec)

    # Save to filesystem
    file_path = persistence.save_to_filesystem(spec)

    # Register triggers
    persistence.register_triggers(spec)

    return {
        "memory_id": memory_id,
        "file_path": file_path,
    }
