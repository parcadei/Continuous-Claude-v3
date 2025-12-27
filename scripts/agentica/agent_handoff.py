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
    from scripts.agentica.agent_handoff import AgentHandoff

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
from datetime import datetime
from pathlib import Path
from typing import Any


class AgentHandoff:
    """Directory-based handoff mechanism for agent orchestration."""

    BASE_DIR = Path(".claude/cache/agents")

    def __init__(self, session_id: str, base_dir: Path | None = None):
        """Initialize handoff for a session.

        Args:
            session_id: Unique identifier for this orchestration session
            base_dir: Override base directory (for testing)
        """
        self.session_id = session_id
        self.base_dir = base_dir or self.BASE_DIR
        self.session_dir = self.base_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def get_output_dir(self, phase: str) -> Path:
        """Get output directory for a phase.

        Args:
            phase: Phase name (e.g., "research", "plan", "implement")

        Returns:
            Path to output directory (created if needed)
        """
        output_dir = self.session_dir / phase
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "artifacts").mkdir(exist_ok=True)
        return output_dir

    def chain_from(self, upstream_phase: str) -> Path:
        """Get input directory from upstream phase.

        Args:
            upstream_phase: Name of upstream phase to read from

        Returns:
            Path to upstream's output directory
        """
        return self.session_dir / upstream_phase

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
        """
        summary_path = self.session_dir / phase / "summary.md"
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
        """
        output_dir = self.get_output_dir(phase)
        artifact_path = output_dir / "artifacts" / name
        artifact_path.write_text(content)
        return artifact_path

    def read_artifact(self, phase: str, name: str) -> str | None:
        """Read an artifact from a phase.

        Args:
            phase: Phase name
            name: Artifact filename

        Returns:
            Artifact content or None if not found
        """
        artifact_path = self.session_dir / phase / "artifacts" / name
        if artifact_path.exists():
            return artifact_path.read_text()
        return None

    def list_artifacts(self, phase: str) -> list[str]:
        """List all artifacts in a phase.

        Args:
            phase: Phase name

        Returns:
            List of artifact filenames
        """
        artifacts_dir = self.session_dir / phase / "artifacts"
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
        """Remove all handoff data for this session."""
        import shutil

        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)


# Convenience functions for simple usage


def create_handoff(session_id: str) -> AgentHandoff:
    """Create a new handoff instance."""
    return AgentHandoff(session_id)


def get_phase_summary(session_id: str, phase: str) -> str | None:
    """Quick read of a phase summary."""
    handoff = AgentHandoff(session_id)
    return handoff.read_summary(phase)
