#!/usr/bin/env python3
"""Hierarchical Research Coordinator.

A multi-agent research system where:
- Coordinator decomposes research topics into logical sections
- Specialist agents research sections in parallel using MCP tools (Perplexity, Nia)
- Coordinator synthesizes findings into a final research document
- Full CoordinationDB integration for observability

Usage:
    # Run research on a topic
    uv run python -m runtime.harness scripts/agentica/research_coordinator.py \\
        --topic "Python async best practices 2025" \\
        --output research_output.md

    # Deep research with more sections
    uv run python -m runtime.harness scripts/agentica/research_coordinator.py \\
        --topic "AI agent observability patterns" \\
        --depth deep \\
        --max-sections 7 \\
        --output deep_research.md

    # Use specific model
    uv run python -m runtime.harness scripts/agentica/research_coordinator.py \\
        --topic "MCP server architecture" \\
        --model "anthropic:claude-sonnet-4" \\
        --output mcp_research.md
"""

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")

# Import tracked_spawn for CoordinationDB integration
try:
    from scripts.agentica.tracked_agent import tracked_spawn
except ImportError:
    async def tracked_spawn(**kwargs):  # type: ignore
        """Stub tracked_spawn for testing."""
        raise NotImplementedError("tracked_agent not available - use mocking in tests")

if TYPE_CHECKING:
    from scripts.agentica.coordination import CoordinationDB

# Type alias for tool hints
ToolHint = Literal["web", "library", "both"]


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ResearchSection:
    """A section of research to investigate.

    Attributes:
        name: snake_case identifier for the section
        title: Human-readable title
        research_focus: Detailed prompt for the specialist agent
        tool_hint: Which tools to prioritize ("web", "library", "both")
    """
    name: str
    title: str
    research_focus: str
    tool_hint: ToolHint = "both"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "title": self.title,
            "research_focus": self.research_focus,
            "tool_hint": self.tool_hint,
        }


@dataclass
class ResearchFindings:
    """Findings from a specialist agent researching a section.

    Attributes:
        section_name: The section this finding belongs to
        key_findings: List of key discoveries
        sources: List of source URLs/references
        recommendations: Actionable recommendations
        code_examples: Relevant code snippets
        open_questions: Questions that remain unanswered
        raw_response: The full raw response from the specialist
    """
    section_name: str
    key_findings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    code_examples: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "section_name": self.section_name,
            "key_findings": self.key_findings,
            "sources": self.sources,
            "recommendations": self.recommendations,
            "code_examples": self.code_examples,
            "open_questions": self.open_questions,
            "raw_response": self.raw_response,
        }

    def to_markdown(self) -> str:
        """Convert findings to markdown format."""
        lines = [f"## {self.section_name}", ""]

        if self.key_findings:
            lines.append("### Key Findings")
            for finding in self.key_findings:
                lines.append(f"- {finding}")
            lines.append("")

        if self.sources:
            lines.append("### Sources")
            for source in self.sources:
                lines.append(f"- {source}")
            lines.append("")

        if self.recommendations:
            lines.append("### Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        if self.code_examples:
            lines.append("### Code Examples")
            for example in self.code_examples:
                lines.append(example)
                lines.append("")

        if self.open_questions:
            lines.append("### Open Questions")
            for question in self.open_questions:
                lines.append(f"- {question}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class ResearchDocument:
    """The final research document synthesized from all findings.

    Attributes:
        topic: The main research topic
        executive_summary: High-level summary of findings
        sections: List of ResearchFindings from specialists
        overall_recommendations: Cross-cutting recommendations
        next_steps: Suggested follow-up actions
        generated_at: Timestamp of document generation
        total_sources: Total number of sources consulted
        research_depth: Depth level used ("standard" or "deep")
    """
    topic: str
    executive_summary: str = ""
    sections: list[ResearchFindings] = field(default_factory=list)
    overall_recommendations: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_sources: int = 0
    research_depth: str = "standard"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "topic": self.topic,
            "executive_summary": self.executive_summary,
            "sections": [s.to_dict() for s in self.sections],
            "overall_recommendations": self.overall_recommendations,
            "next_steps": self.next_steps,
            "generated_at": self.generated_at.isoformat(),
            "total_sources": self.total_sources,
            "research_depth": self.research_depth,
        }

    def to_markdown(self) -> str:
        """Convert document to markdown format."""
        lines = [
            f"# {self.topic}",
            "",
            f"*Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*",
            f"*Depth: {self.research_depth} | Sources: {self.total_sources}*",
            "",
        ]

        if self.executive_summary:
            lines.extend([
                "## Executive Summary",
                "",
                self.executive_summary,
                "",
            ])

        # Add each section's findings
        for section in self.sections:
            lines.append(section.to_markdown())

        if self.overall_recommendations:
            lines.append("## Overall Recommendations")
            lines.append("")
            for rec in self.overall_recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        if self.next_steps:
            lines.append("## Next Steps")
            lines.append("")
            for step in self.next_steps:
                lines.append(f"- {step}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# MCP Tool Wrappers
# =============================================================================


def call_perplexity_sync(query: str, mode: str = "research") -> dict[str, Any]:
    """Call Perplexity search via subprocess.

    Args:
        query: The search query
        mode: Search mode - "ask", "research", "reason", or "deep"

    Returns:
        Dictionary with search results
    """
    script_path = Path(__file__).parent.parent / "perplexity_search.py"

    mode_flag = f"--{mode}"
    cmd = [
        "uv", "run", "python", "-m", "runtime.harness",
        str(script_path), mode_flag, query
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=Path(__file__).parent.parent.parent
        )
        return {
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else "",
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Perplexity search timed out", "output": "", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "output": "", "returncode": -1}


def call_nia_sync(
    package: str,
    query: str,
    registry: str = "py_pi"
) -> dict[str, Any]:
    """Call Nia documentation search via subprocess.

    Args:
        package: Package name to search
        query: Search query
        registry: Package registry (py_pi, npm, crates, go_modules)

    Returns:
        Dictionary with search results
    """
    script_path = Path(__file__).parent.parent / "nia_docs.py"

    cmd = [
        "uv", "run", "python", "-m", "runtime.harness",
        str(script_path),
        "search", "package", package,
        "--query", query,
        "--registry", registry
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path(__file__).parent.parent.parent
        )
        return {
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else "",
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Nia search timed out", "output": "", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "output": "", "returncode": -1}


def perplexity_research(query: str) -> str:
    """Scope function for standard web research.

    This is an agent scope function that wraps call_perplexity_sync.
    """
    result = call_perplexity_sync(query, mode="research")
    if result.get("error"):
        return f"Error: {result['error']}"
    return str(result.get("output", ""))


def perplexity_deep(query: str) -> str:
    """Scope function for deep comprehensive research.

    This is an agent scope function for in-depth research tasks.
    """
    result = call_perplexity_sync(query, mode="deep")
    if result.get("error"):
        return f"Error: {result['error']}"
    return str(result.get("output", ""))


def library_docs(package: str, query: str) -> str:
    """Scope function for library documentation search.

    This is an agent scope function that wraps call_nia_sync.
    """
    result = call_nia_sync(package, query)
    if result.get("error"):
        return f"Error: {result['error']}"
    return str(result.get("output", ""))


# =============================================================================
# ResearchCoordinator Class
# =============================================================================


class ResearchCoordinator:
    """Hierarchical coordinator for multi-agent research.

    The coordinator:
    1. Decomposes topics into logical research sections
    2. Spawns specialist agents to research each section in parallel
    3. Synthesizes findings into a comprehensive research document

    Attributes:
        topic: The research topic
        depth: Research depth ("standard" or "deep")
        max_sections: Maximum number of sections to create
        model: Optional model override
        db: Optional CoordinationDB for tracking
    """

    def __init__(
        self,
        topic: str,
        depth: str = "standard",
        max_sections: int = 5,
        model: Optional[str] = None,
        db: Optional["CoordinationDB"] = None,
    ):
        """Initialize the research coordinator.

        Args:
            topic: The research topic to investigate
            depth: Research depth - "standard" or "deep"
            max_sections: Maximum sections to decompose into
            model: Optional model to use for agents
            db: Optional CoordinationDB for observability
        """
        self.topic = topic
        self.depth = depth
        self.max_sections = max_sections
        self.model = model
        self.db = db

    async def _spawn_agent(
        self,
        premise: str,
        scope: Optional[dict[str, Any]] = None,
        pattern: str = "research_coordinator",
    ) -> Any:
        """Spawn an agent with optional tracking.

        Uses tracked_spawn if db is provided, otherwise regular spawn.
        """
        spawn_kwargs: dict[str, Any] = {"premise": premise}
        if self.model:
            spawn_kwargs["model"] = self.model
        if scope:
            spawn_kwargs["scope"] = scope

        if self.db:
            return await tracked_spawn(
                db=self.db,
                pattern=pattern,
                **spawn_kwargs
            )
        else:
            return await spawn(**spawn_kwargs)

    async def decompose(self) -> list[ResearchSection]:
        """Decompose the topic into research sections.

        The coordinator agent analyzes the topic and breaks it down
        into logical sections for specialist research.

        Returns:
            List of ResearchSection objects
        """
        premise = """You are a research coordinator who breaks down complex topics
into logical research sections. Your job is to:
1. Analyze the research topic
2. Identify 3-7 distinct aspects that need investigation
3. Create focused research prompts for each section

Return a JSON array of sections, each with:
- name: snake_case identifier
- title: Human-readable title
- research_focus: Detailed prompt for the specialist
- tool_hint: "web" for general research, "library" for code docs, "both" for combined

Example output:
[
  {
    "name": "api_patterns",
    "title": "API Design Patterns",
    "research_focus": "Investigate REST vs GraphQL patterns...",
    "tool_hint": "web"
  }
]
"""

        coordinator = await self._spawn_agent(premise, pattern="research_coordinator")

        prompt = f"""Decompose this research topic into focused sections:

Topic: {self.topic}

Research depth: {self.depth}
Maximum sections: {self.max_sections}

Return ONLY a JSON array with the sections. No explanation text.
"""

        try:
            response = await coordinator.call(str, prompt)
            sections_data = self._parse_json_response(response)

            if not sections_data:
                # Fallback to single generic section
                return [
                    ResearchSection(
                        name="general_research",
                        title="General Research",
                        research_focus=f"Research the topic: {self.topic}",
                        tool_hint="both"
                    )
                ]

            sections = []
            for item in sections_data[:self.max_sections]:
                section = ResearchSection(
                    name=item.get("name", "unknown"),
                    title=item.get("title", "Unknown Section"),
                    research_focus=item.get("research_focus", ""),
                    tool_hint=item.get("tool_hint", "both")
                )
                sections.append(section)

            return sections

        except Exception:
            # Fallback on any error
            return [
                ResearchSection(
                    name="general_research",
                    title="General Research",
                    research_focus=f"Research the topic: {self.topic}",
                    tool_hint="both"
                )
            ]

    def _parse_json_response(self, response: str) -> list[dict[str, Any]]:
        """Parse JSON from agent response, handling markdown code blocks."""
        # Try direct parse first
        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                try:
                    parsed = json.loads(response[start:end].strip())
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass

        # Try extracting any JSON array
        if "[" in response:
            start = response.find("[")
            end = response.rfind("]") + 1
            if end > start:
                try:
                    parsed = json.loads(response[start:end])
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass

        return []

    def _build_specialist_scope(self, tool_hint: ToolHint) -> dict[str, Any]:
        """Build scope for specialist based on tool hint."""
        scope: dict[str, Any] = {}

        if tool_hint in ("web", "both"):
            scope["perplexity_research"] = perplexity_research
            if self.depth == "deep":
                scope["perplexity_deep"] = perplexity_deep

        if tool_hint in ("library", "both"):
            scope["library_docs"] = library_docs

        return scope

    async def _research_section(self, section: ResearchSection) -> ResearchFindings:
        """Have a specialist agent research a section.

        Args:
            section: The section to research

        Returns:
            ResearchFindings from the specialist
        """
        premise = f"""You are a specialist researcher focused on: {section.title}

Your task is to thoroughly investigate the given focus area.
Use the available tools to gather information.

Return your findings as JSON with these fields:
- key_findings: List of important discoveries
- sources: List of URLs/references consulted
- recommendations: Actionable suggestions
- code_examples: Relevant code snippets (if applicable)
- open_questions: Questions that remain unanswered
"""

        scope = self._build_specialist_scope(section.tool_hint)
        specialist = await self._spawn_agent(premise, scope=scope, pattern="research_coordinator")

        prompt = f"""Research this topic in depth:

{section.research_focus}

Use available tools to gather comprehensive information.
Return your findings as JSON.
"""

        try:
            response = await specialist.call(str, prompt)
            findings_data = self._parse_findings_response(response)

            return ResearchFindings(
                section_name=section.name,
                key_findings=findings_data.get("key_findings", []),
                sources=findings_data.get("sources", []),
                recommendations=findings_data.get("recommendations", []),
                code_examples=findings_data.get("code_examples", []),
                open_questions=findings_data.get("open_questions", []),
                raw_response=response,
            )

        except Exception as e:
            # Return findings with raw response on error
            return ResearchFindings(
                section_name=section.name,
                raw_response=str(e),
            )

    def _parse_findings_response(self, response: str) -> dict[str, Any]:
        """Parse findings JSON from specialist response."""
        # Try direct parse
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                try:
                    data = json.loads(response[start:end].strip())
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    pass

        # Try extracting any JSON object
        if "{" in response:
            start = response.find("{")
            end = response.rfind("}") + 1
            if end > start:
                try:
                    data = json.loads(response[start:end])
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    pass

        # Return empty dict, caller will use raw_response
        return {}

    async def research_sections(
        self,
        sections: list[ResearchSection]
    ) -> list[ResearchFindings]:
        """Research all sections in parallel.

        Args:
            sections: List of sections to research

        Returns:
            List of ResearchFindings (may be partial if some failed)
        """
        async def safe_research(section: ResearchSection) -> Optional[ResearchFindings]:
            """Research with error handling."""
            try:
                return await self._research_section(section)
            except Exception as e:
                # Return findings with error in raw_response
                return ResearchFindings(
                    section_name=section.name,
                    raw_response=f"Error: {e}",
                )

        # Execute all research in parallel
        results = await asyncio.gather(
            *[safe_research(section) for section in sections],
            return_exceptions=False
        )

        # Filter out None results (shouldn't happen with our error handling)
        return [r for r in results if r is not None]

    async def synthesize(self, findings: list[ResearchFindings]) -> ResearchDocument:
        """Synthesize findings into a research document.

        Args:
            findings: List of findings from specialists

        Returns:
            Comprehensive ResearchDocument
        """
        # Calculate total sources
        total_sources = sum(len(f.sources) for f in findings)

        premise = """You are a research synthesizer who creates comprehensive
reports from specialist findings. Your job is to:
1. Identify common themes and patterns
2. Synthesize key insights
3. Provide actionable recommendations
4. Suggest next steps

Return your synthesis as JSON with:
- executive_summary: 2-3 paragraph overview
- overall_recommendations: List of cross-cutting recommendations
- next_steps: List of suggested follow-up actions
"""

        coordinator = await self._spawn_agent(premise, pattern="research_coordinator")

        # Format findings for synthesis
        findings_text = "\n\n".join([
            f"### {f.section_name}\n"
            f"Key findings: {', '.join(f.key_findings[:5])}\n"
            f"Recommendations: {', '.join(f.recommendations[:3])}\n"
            f"Open questions: {', '.join(f.open_questions[:3])}"
            for f in findings
        ])

        prompt = f"""Synthesize these research findings into a coherent summary:

Topic: {self.topic}

{findings_text}

Return your synthesis as JSON.
"""

        try:
            response = await coordinator.call(str, prompt)
            synthesis_data = self._parse_findings_response(response)

            return ResearchDocument(
                topic=self.topic,
                executive_summary=synthesis_data.get("executive_summary", ""),
                sections=findings,
                overall_recommendations=synthesis_data.get("overall_recommendations", []),
                next_steps=synthesis_data.get("next_steps", []),
                total_sources=total_sources,
                research_depth=self.depth,
            )

        except Exception:
            # Return document with what we have
            return ResearchDocument(
                topic=self.topic,
                sections=findings,
                total_sources=total_sources,
                research_depth=self.depth,
            )

    async def research(self) -> ResearchDocument:
        """Execute the full research workflow.

        This is the main entry point that:
        1. Decomposes the topic into sections
        2. Researches each section in parallel
        3. Synthesizes findings into a final document

        Returns:
            Complete ResearchDocument
        """
        # 1. Decompose topic into sections
        sections = await self.decompose()

        # 2. Research all sections in parallel
        findings = await self.research_sections(sections)

        # 3. Synthesize into final document
        document = await self.synthesize(findings)

        return document


# =============================================================================
# CLI Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Hierarchical Research Coordinator - Multi-agent research system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic research
  %(prog)s --topic "Python async patterns" --output research.md

  # Deep research with more sections
  %(prog)s --topic "AI observability" --depth deep --max-sections 7

  # JSON output
  %(prog)s --topic "MCP architecture" --format json --output research.json
        """
    )

    parser.add_argument(
        "--topic",
        required=True,
        help="Research topic to investigate"
    )
    parser.add_argument(
        "--depth",
        choices=["standard", "deep"],
        default="standard",
        help="Research depth (default: standard)"
    )
    parser.add_argument(
        "--max-sections",
        type=int,
        default=5,
        help="Maximum sections to create (default: 5)"
    )
    parser.add_argument(
        "--model",
        help="Model to use (e.g., anthropic:claude-sonnet-4)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable CoordinationDB tracking"
    )

    return parser.parse_args()


async def main() -> None:
    """Main entry point for CLI."""
    args = parse_args()

    # Setup coordination DB if tracking enabled
    db = None
    if not args.no_tracking:
        try:
            from scripts.agentica.coordination import CoordinationDB
            db = CoordinationDB()
        except ImportError:
            pass  # CoordinationDB not available

    # Create coordinator
    coordinator = ResearchCoordinator(
        topic=args.topic,
        depth=args.depth,
        max_sections=args.max_sections,
        model=args.model,
        db=db,
    )

    print(f"Starting research on: {args.topic}", file=sys.stderr)
    print(f"Depth: {args.depth}, Max sections: {args.max_sections}", file=sys.stderr)

    # Execute research
    document = await coordinator.research()

    # Format output
    if args.format == "json":
        output = json.dumps(document.to_dict(), indent=2, default=str)
    else:
        output = document.to_markdown()

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        print(f"Research saved to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
