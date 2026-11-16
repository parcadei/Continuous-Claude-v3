"""Agent directory handoff mechanism for context-preserving orchestration.

Instead of using TaskOutput (which floods context with full transcripts),
agents communicate via filesystem directories.

Pattern:
    Research → .claude/cache/agents/research/summary.md
                     ↓ (read by)
    Plan     → .claude/cache/agents/plan/summary.md
                     ↓ (read by)
    Implement → .claude/cache/agents/implement/summary.md

Usage:
    from scripts.agentica_patterns.agent_handoff import AgentHandoff

    handoff = AgentHandoff(session_id="task-123")

    # Phase 1: Research
    research_dir = handoff.get_output_dir("research")
    # Agent writes to research_dir/summary.md

    # Phase 2: Plan reads research output
    plan_input = handoff.chain_from("research")
    plan_dir = handoff.get_output_dir("plan")
    # Agent reads plan_input/summary.md, writes to plan_dir/summary.md

    # Generate system prompt with context
    system_prompt = handoff.build_system_prompt(
        agent_role="Planner",
        phase="plan",
        upstream="research",
        downstream="implement",
        task="Create implementation plan",
        code_map=codemap_content,
    )
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# Validation patterns for path components
# Allow alphanumeric, underscore, hyphen only (no dots, slashes, or special chars)
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')
# Filenames can have a single dot for extension
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$')


def _validate_path_component(component: str, component_type: str = "path component") -> str:
    """Validate a path component to prevent traversal attacks.

    Args:
        component: The path component to validate (session_id, phase, etc.)
        component_type: Description for error messages

    Returns:
        The validated component (unchanged if valid)

    Raises:
        ValueError: If component contains traversal patterns or invalid characters
    """
    if not component:
        raise ValueError(f"Empty {component_type} not allowed")

    # Block null bytes
    if '\x00' in component:
        raise ValueError(f"Null byte in {component_type} not allowed")

    # Block obvious traversal patterns before regex check
    if '..' in component:
        raise ValueError(f"Path traversal in {component_type}: {component!r}")

    if component.startswith('/') or component.startswith('~'):
        raise ValueError(f"Absolute path in {component_type} not allowed: {component!r}")

    if '/' in component or '\\' in component:
        raise ValueError(f"Path separator in {component_type} not allowed: {component!r}")

    # Validate against allowlist pattern
    if not SAFE_PATH_COMPONENT.match(component):
        raise ValueError(
            f"Invalid {component_type}: {component!r}. "
            f"Only alphanumeric, underscore, and hyphen allowed."
        )

    return component


def _validate_filename(name: str) -> str:
    """Validate a filename for artifact storage.

    Args:
        name: The filename to validate

    Returns:
        The validated filename

    Raises:
        ValueError: If filename is invalid
    """
    if not name:
        raise ValueError("Empty filename not allowed")

    if '\x00' in name:
        raise ValueError("Null byte in filename not allowed")

    if '..' in name:
        raise ValueError(f"Path traversal in filename: {name!r}")

    if '/' in name or '\\' in name:
        raise ValueError(f"Path separator in filename not allowed: {name!r}")

    if name.startswith('.'):
        raise ValueError(f"Hidden files not allowed: {name!r}")

    if not SAFE_FILENAME.match(name):
        raise ValueError(
            f"Invalid filename: {name!r}. "
            f"Only alphanumeric, underscore, hyphen, and single extension allowed."
        )

    return name


def _validate_path_within_base(path: Path, base: Path) -> Path:
    """Validate that a resolved path stays within the base directory.

    Args:
        path: Path to validate (will be resolved)
        base: Base directory that must contain the path

    Returns:
        The resolved path

    Raises:
        ValueError: If path escapes base directory
    """
    resolved = path.resolve()
    base_resolved = base.resolve()

    # Handle macOS case-insensitive filesystem
    if sys.platform == 'darwin':
        resolved_str = str(resolved).lower()
        base_str = str(base_resolved).lower()
    else:
        resolved_str = str(resolved)
        base_str = str(base_resolved)

    # Check containment
    if not (resolved_str.startswith(base_str + os.sep) or resolved_str == base_str):
        raise ValueError(
            f"Path {path} resolves to {resolved} which escapes base directory {base_resolved}"
        )

    return resolved


class AgentHandoff:
    """Directory-based handoff mechanism for agent orchestration."""

    BASE_DIR = Path(".claude/cache/agents")

    def __init__(self, session_id: str, base_dir: Path | None = None):
        """Initialize handoff for a session.

        Args:
            session_id: Unique identifier for this orchestration session
            base_dir: Override base directory (for testing)

        Raises:
            ValueError: If session_id contains path traversal patterns
        """
        # Validate session_id before use
        self.session_id = _validate_path_component(session_id, "session_id")
        self.base_dir = (base_dir or self.BASE_DIR).resolve()

        # Build session directory path
        self.session_dir = self.base_dir / self.session_id

        # Validate the constructed path stays within base_dir
        _validate_path_within_base(self.session_dir, self.base_dir)

        self.session_dir.mkdir(parents=True, exist_ok=True)

    def get_output_dir(self, phase: str) -> Path:
        """Get output directory for a phase.

        Args:
            phase: Phase name (e.g., "research", "plan", "implement")

        Returns:
            Path to output directory (created if needed)

        Raises:
            ValueError: If phase contains path traversal patterns
        """
        # Validate phase before use
        _validate_path_component(phase, "phase")

        output_dir = self.session_dir / phase

        # Belt-and-suspenders: verify path containment
        _validate_path_within_base(output_dir, self.base_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "artifacts").mkdir(exist_ok=True)
        return output_dir

    def chain_from(self, upstream_phase: str) -> Path:
        """Get input directory from upstream phase.

        Args:
            upstream_phase: Name of upstream phase to read from

        Returns:
            Path to upstream's output directory

        Raises:
            ValueError: If upstream_phase contains path traversal patterns
        """
        # Validate upstream_phase before use
        _validate_path_component(upstream_phase, "upstream_phase")

        path = self.session_dir / upstream_phase

        # Validate containment
        _validate_path_within_base(path, self.base_dir)

        return path

    def write_summary(self, phase: str, summary: str, metadata: dict[str, Any] | None = None) -> Path:
        """Write summary.md for a phase.

        Args:
            phase: Phase name
            summary: Summary content (markdown)
            metadata: Optional metadata dict

        Returns:
            Path to written summary file
        """
        output_dir = self.get_output_dir(phase)
        summary_path = output_dir / "summary.md"

        content = f"""# {phase.title()} Phase Summary

Generated: {datetime.now().isoformat()}
Session: {self.session_id}

{summary}
"""
        if metadata:
            content += f"\n## Metadata\n\n```json\n{json.dumps(metadata, indent=2)}\n```\n"

        summary_path.write_text(content)
        return summary_path

    def read_summary(self, phase: str) -> str | None:
        """Read summary.md from a phase.

        Args:
            phase: Phase name

        Returns:
            Summary content or None if not found

        Raises:
            ValueError: If phase contains path traversal patterns
        """
        # Validate phase
        _validate_path_component(phase, "phase")

        summary_path = self.session_dir / phase / "summary.md"

        # Validate path containment
        _validate_path_within_base(summary_path, self.base_dir)

        if summary_path.exists():
            return summary_path.read_text()
        return None

    def write_artifact(self, phase: str, name: str, content: str) -> Path:
        """Write an artifact file.

        Args:
            phase: Phase name
            name: Artifact filename
            content: Artifact content

        Returns:
            Path to written artifact

        Raises:
            ValueError: If phase or name contains path traversal patterns
        """
        # Validate filename
        _validate_filename(name)

        # get_output_dir validates phase
        output_dir = self.get_output_dir(phase)
        artifact_path = output_dir / "artifacts" / name

        # Belt-and-suspenders: verify final path
        _validate_path_within_base(artifact_path, self.base_dir)

        artifact_path.write_text(content)
        return artifact_path

    def read_artifact(self, phase: str, name: str) -> str | None:
        """Read an artifact from a phase.

        Args:
            phase: Phase name
            name: Artifact filename

        Returns:
            Artifact content or None if not found

        Raises:
            ValueError: If phase or name contains path traversal patterns
        """
        # Validate both components
        _validate_path_component(phase, "phase")
        _validate_filename(name)

        artifact_path = self.session_dir / phase / "artifacts" / name

        # Validate containment
        _validate_path_within_base(artifact_path, self.base_dir)

        if artifact_path.exists():
            return artifact_path.read_text()
        return None

    def list_artifacts(self, phase: str) -> list[str]:
        """List all artifacts in a phase.

        Args:
            phase: Phase name

        Returns:
            List of artifact filenames

        Raises:
            ValueError: If phase contains path traversal patterns
        """
        # Validate phase
        _validate_path_component(phase, "phase")

        artifacts_dir = self.session_dir / phase / "artifacts"

        # Validate containment
        _validate_path_within_base(artifacts_dir, self.base_dir)

        if artifacts_dir.exists():
            return [f.name for f in artifacts_dir.iterdir() if f.is_file()]
        return []

    def build_system_prompt(
        self,
        agent_role: str,
        phase: str,
        task: str,
        upstream: str | None = None,
        downstream: str | None = None,
        code_map: str | None = None,
        memory_context: str | None = None,
        extra_context: str | None = None,
    ) -> str:
        """Build rich system prompt for an agent.

        Args:
            agent_role: Role name (e.g., "Researcher", "Planner")
            phase: Current phase name
            task: Task description
            upstream: Upstream phase name (for input)
            downstream: Downstream phase name (for context)
            code_map: RepoPrompt codemap content
            memory_context: Memory system documentation
            extra_context: Additional context to inject

        Returns:
            Complete system prompt
        """
        output_dir = self.get_output_dir(phase)
        input_dir = self.chain_from(upstream) if upstream else None

        # Read upstream summary if available
        upstream_content = ""
        if upstream:
            upstream_summary = self.read_summary(upstream)
            if upstream_summary:
                upstream_content = f"""
## UPSTREAM CONTEXT (from {upstream})

{upstream_summary}
"""

        prompt = f"""## AGENT IDENTITY

You are {agent_role} in a multi-agent orchestration system.
Phase: {phase}
Session: {self.session_id}
{f"Your output will be consumed by: {downstream}" if downstream else "You are the final phase."}
{f"Your input comes from: {upstream}" if upstream else "You are the first phase."}

## SYSTEM ARCHITECTURE

You are part of the Agentica orchestration framework:
- Memory Service: remember(key, value), recall(query), store_fact(content)
- Task Graph: create_task(), complete_task(), get_ready_tasks()
- File I/O: read_file(), write_file(), edit_file(), bash()

Session ID: {self.session_id} (all your memory/tasks scoped here)

## DIRECTORY HANDOFF

{f"Read your inputs from: {input_dir}" if input_dir else "No upstream input."}
Write your outputs to: {output_dir}

Output format:
- {output_dir}/summary.md - What you did, key findings, handoff to next phase
- {output_dir}/artifacts/ - Any generated files (code, data, etc.)

{upstream_content}
"""

        if code_map:
            prompt += f"""
## CODE CONTEXT

{code_map}
"""

        if memory_context:
            prompt += f"""
## MEMORY SYSTEM

{memory_context}
"""

        if extra_context:
            prompt += f"""
## ADDITIONAL CONTEXT

{extra_context}
"""

        prompt += f"""
## YOUR TASK

{task}

## CRITICAL RULES

1. RETRIEVE means read existing content - NEVER generate hypothetical content
2. WRITE means create/update file - specify exact content
3. When stuck, output what you found and what's blocking you
4. Your summary.md is your handoff to the next phase - be precise
5. Write artifacts for anything the next phase needs to read
"""

        return prompt

    def get_memory_context(self) -> str:
        """Get standard memory context documentation.

        Returns:
            Memory system documentation string
        """
        return f"""You have access to a 3-tier memory system:

1. **Core Memory** (in-context): remember(key, value), recall(query)
   - Fast key-value store for current session facts

2. **Archival Memory** (searchable): store_fact(content), search_memory(query)
   - FTS5-indexed long-term storage
   - Use for findings that should persist

3. **Recall** (unified): recall(query)
   - Searches both core and archival
   - Returns formatted context string

All memory is scoped to session_id: {self.session_id}
"""

    def cleanup(self) -> None:
        """Remove all handoff data for this session.

        Raises:
            ValueError: If session directory escapes base directory (should never happen
                        if session_id was validated in __init__, but defense-in-depth)
        """
        import shutil

        if self.session_dir.exists():
            # Defense in depth: re-validate before destructive operation
            try:
                _validate_path_within_base(self.session_dir, self.base_dir)
            except ValueError as e:
                # Log this as a security event - should never happen with validated session_id
                raise ValueError(
                    f"SECURITY: Refusing to delete directory outside base: {self.session_dir}. "
                    f"Original error: {e}"
                ) from e

            if not self.session_dir.is_dir():
                raise ValueError(f"Expected directory, got file: {self.session_dir}")

            shutil.rmtree(self.session_dir)


# Convenience functions for simple usage


def create_handoff(session_id: str) -> AgentHandoff:
    """Create a new handoff instance."""
    return AgentHandoff(session_id)


def get_phase_summary(session_id: str, phase: str) -> str | None:
    """Quick read of a phase summary."""
    handoff = AgentHandoff(session_id)
    return handoff.read_summary(phase)
