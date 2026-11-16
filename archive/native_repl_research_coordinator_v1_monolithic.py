#!/usr/bin/env python3
"""Native REPL Research Coordinator (Approach 3).

A hierarchical research coordinator that uses Claude Code CLI via run_claude()
for tool execution. This is the Native REPL approach where:
- Agentica agents handle orchestration
- Claude Code CLI (via run_claude) handles execution
- Specialists delegate research to Claude with appropriate tools

Architecture:
    ResearchCoordinator
        -> decompose() spawns coordinator agent
        -> research_sections() spawns specialist agents in parallel
        -> synthesize() coordinator synthesizes findings

    Each specialist uses run_claude() to invoke Claude Code CLI with:
        - WebSearch for web research
        - Read/Grep for codebase research
        - WebFetch for documentation

Usage:
    uv run python scripts/agentica/native_repl/research_coordinator.py \
        --topic "Python async best practices" \
        --output research.md \
        --track

    # Deep research with more sections
    uv run python scripts/agentica/native_repl/research_coordinator.py \
        --topic "MCP server patterns" \
        --depth deep \
        --max-sections 7 \
        --output mcp-research.md

Comparison with Approach 2:
    - Approach 2: Specialists call perplexity/nia scripts via subprocess
    - Approach 3: Specialists call run_claude() which invokes Claude Code CLI
    - Key difference: Claude Code handles tool selection internally
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional

# Import spawn from agentica
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

# Import run_claude for Claude Code CLI execution
try:
    from scripts.agentica.native_repl.run_claude import run_claude
except ImportError:
    async def run_claude(**kwargs):  # type: ignore
        """Stub run_claude for testing."""
        raise NotImplementedError("run_claude not available")

if TYPE_CHECKING:
    from scripts.agentica.coordination import CoordinationDB


# Type alias for tool hints
ToolHint = Literal["web", "codebase", "docs", "all"]


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
        tool_hint: Which tools to prioritize ("web", "codebase", "docs", "all")
    """
    name: str
    title: str
    research_focus: str
    tool_hint: ToolHint = "all"

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
# run_claude Tool Wrappers for Agent Scope
# =============================================================================
# These are the tools that specialists will use in their REPL code.
# Unlike Approach 2 which calls perplexity/nia scripts directly,
# Approach 3 delegates to Claude Code CLI which handles tool selection.


async def web_research(query: str, max_turns: int = 5) -> str:
    """Search the web for information using Claude Code CLI.

    This invokes Claude Code with WebSearch enabled to research a topic.

    Args:
        query: The research query
        max_turns: Maximum agentic turns for Claude

    Returns:
        Research results as string
    """
    result = await run_claude(
        task=f"""Research this topic thoroughly and provide a comprehensive summary:

{query}

Include:
- Key facts and findings
- Relevant sources/references
- Any important caveats or limitations

Format your response as structured text that can be parsed.""",
        tools=["WebSearch"],
        max_turns=max_turns,
        system_prompt="You are a research assistant. Be thorough and cite sources.",
    )

    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


async def codebase_research(query: str, path: str = ".", max_turns: int = 5) -> str:
    """Search the codebase for patterns and implementations.

    This invokes Claude Code with Read/Grep/Glob to analyze code.

    Args:
        query: What to search for
        path: Directory to search in
        max_turns: Maximum agentic turns

    Returns:
        Code analysis results
    """
    result = await run_claude(
        task=f"""Analyze the codebase for: {query}

Search in: {path}

Find relevant:
- Code patterns
- Implementations
- Examples
- Documentation

Summarize your findings with file paths and code snippets.""",
        tools=["Read", "Grep", "Glob"],
        max_turns=max_turns,
        system_prompt="You are a code analyst. Find relevant patterns and implementations.",
    )

    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


async def docs_research(url: str, query: str, max_turns: int = 3) -> str:
    """Fetch and analyze documentation from a URL.

    This invokes Claude Code with WebFetch to read documentation.

    Args:
        url: Documentation URL to fetch
        query: What to look for in the docs
        max_turns: Maximum agentic turns

    Returns:
        Documentation analysis
    """
    result = await run_claude(
        task=f"""Fetch and analyze the documentation at: {url}

Look for information about: {query}

Summarize:
- Key concepts
- Usage examples
- Best practices
- Common pitfalls""",
        tools=["WebFetch"],
        max_turns=max_turns,
        system_prompt="You are a documentation analyst. Extract key information clearly.",
    )

    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


async def comprehensive_research(
    topic: str,
    max_turns: int = 10,
    depth: str = "standard"
) -> str:
    """Comprehensive research using all available tools.

    This is the main research function for specialists. It invokes Claude Code
    with multiple tools to gather comprehensive information.

    Args:
        topic: Research topic
        max_turns: Maximum agentic turns
        depth: "standard" or "deep"

    Returns:
        Comprehensive research findings
    """
    depth_instruction = ""
    if depth == "deep":
        depth_instruction = """
This is a DEEP research request. Be extremely thorough:
- Search multiple sources
- Cross-reference findings
- Look for edge cases and nuances
- Provide detailed analysis
"""

    result = await run_claude(
        task=f"""Conduct comprehensive research on:

{topic}

{depth_instruction}

Your research should include:
1. Key findings and facts
2. Current best practices
3. Code examples (if applicable)
4. Common pitfalls to avoid
5. Reliable sources

Format your response as structured text with clear sections.""",
        tools=["WebSearch", "Read", "Grep", "Glob", "WebFetch"],
        max_turns=max_turns,
        system_prompt="You are a senior research analyst. Provide thorough, accurate research.",
    )

    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


# =============================================================================
# ResearchCoordinator Class
# =============================================================================


class ResearchCoordinator:
    """Hierarchical coordinator for multi-agent research using Native REPL.

    The coordinator:
    1. Decomposes topics into logical research sections
    2. Spawns specialist agents to research each section in parallel
    3. Specialists use run_claude() to invoke Claude Code CLI
    4. Synthesizes findings into a comprehensive research document

    This is Approach 3 - Native REPL:
    - Intelligence layer: Claude via Agentica agents
    - Execution layer: Claude Code CLI via run_claude()
    - Tool access: Claude Code handles tool selection internally

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
            model: Optional model to use for Agentica agents
            db: Optional CoordinationDB for observability
        """
        self.topic = topic
        self.depth = depth
        self.max_sections = max_sections
        self.model = model
        self.db = db

        # Build scope with run_claude wrappers for specialists
        self.specialist_scope = {
            "run_claude": run_claude,
            "web_research": web_research,
            "codebase_research": codebase_research,
            "docs_research": docs_research,
            "comprehensive_research": comprehensive_research,
        }

    async def _spawn_agent(
        self,
        premise: str,
        scope: Optional[dict[str, Any]] = None,
        pattern: str = "native_repl_coordinator",
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
- tool_hint: "web" for general research, "codebase" for code analysis, "docs" for documentation, "all" for comprehensive

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

        coordinator = await self._spawn_agent(premise, pattern="native_repl_coordinator")

        prompt = f"""Decompose this research topic into focused sections:

Topic: {self.topic}

Research depth: {self.depth}
Maximum sections: {self.max_sections}

Return ONLY a JSON array with the sections. No explanation text.
"""

        try:
            response = await coordinator.call(str, prompt)
            await coordinator.close()

            sections_data = self._parse_json_response(response)

            if not sections_data:
                # Fallback to single generic section
                return [
                    ResearchSection(
                        name="general_research",
                        title="General Research",
                        research_focus=f"Research the topic: {self.topic}",
                        tool_hint="all"
                    )
                ]

            sections = []
            for item in sections_data[:self.max_sections]:
                section = ResearchSection(
                    name=item.get("name", "unknown"),
                    title=item.get("title", "Unknown Section"),
                    research_focus=item.get("research_focus", ""),
                    tool_hint=item.get("tool_hint", "all")
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
                    tool_hint="all"
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

    def _build_specialist_premise(self, section: ResearchSection) -> str:
        """Build premise for specialist based on section and tool hint."""

        # Map tool hints to available functions
        tool_docs = {
            "web": """
You have access to:
- `web_research(query)` - Search the web for information
- `comprehensive_research(topic)` - Thorough multi-source research
""",
            "codebase": """
You have access to:
- `codebase_research(query, path=".")` - Analyze code patterns
- `comprehensive_research(topic)` - Thorough multi-source research
""",
            "docs": """
You have access to:
- `docs_research(url, query)` - Fetch and analyze documentation
- `web_research(query)` - Search the web for information
""",
            "all": """
You have access to:
- `web_research(query)` - Search the web for information
- `codebase_research(query, path)` - Analyze code patterns
- `docs_research(url, query)` - Fetch and analyze documentation
- `comprehensive_research(topic, depth)` - Thorough multi-source research
""",
        }

        tool_guidance = tool_docs.get(section.tool_hint, tool_docs["all"])

        return f"""You are a specialist researcher focused on: {section.title}

Your task is to thoroughly investigate the given focus area.
{tool_guidance}
**Important:** Use `await` when calling these async functions.

Return your findings as JSON with these fields:
- key_findings: List of important discoveries
- sources: List of URLs/references consulted
- recommendations: Actionable suggestions
- code_examples: Relevant code snippets (if applicable)
- open_questions: Questions that remain unanswered

Example REPL code:
```python
results = await comprehensive_research("{section.title}", depth="{self.depth}")
# Parse and structure the findings
return {{"key_findings": [...], "sources": [...]}}
```
"""

    async def _research_section(self, section: ResearchSection) -> ResearchFindings:
        """Have a specialist agent research a section.

        Args:
            section: The section to research

        Returns:
            ResearchFindings from the specialist
        """
        premise = self._build_specialist_premise(section)

        specialist = await self._spawn_agent(
            premise,
            scope=self.specialist_scope,
            pattern="native_repl_specialist"
        )

        prompt = f"""Research this topic in depth:

{section.research_focus}

Use the available research tools to gather comprehensive information.
Return your findings as JSON.
"""

        try:
            response = await specialist.call(str, prompt)
            await specialist.close()

            findings_data = self._parse_findings_response(response)

            return ResearchFindings(
                section_name=section.title,
                key_findings=findings_data.get("key_findings", []),
                sources=findings_data.get("sources", []),
                recommendations=findings_data.get("recommendations", []),
                code_examples=findings_data.get("code_examples", []),
                open_questions=findings_data.get("open_questions", []),
                raw_response=response,
            )

        except Exception as e:
            # Return findings with error in raw_response
            return ResearchFindings(
                section_name=section.title,
                raw_response=f"Error: {e}",
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
        async def safe_research(section: ResearchSection) -> ResearchFindings:
            """Research with error handling."""
            try:
                return await self._research_section(section)
            except Exception as e:
                # Return findings with error in raw_response
                return ResearchFindings(
                    section_name=section.title,
                    raw_response=f"Error: {e}",
                )

        # Execute all research in parallel
        results = await asyncio.gather(
            *[safe_research(section) for section in sections],
            return_exceptions=False
        )

        return list(results)

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

        coordinator = await self._spawn_agent(premise, pattern="native_repl_coordinator")

        # Format findings for synthesis
        findings_text = "\n\n".join([
            f"### {f.section_name}\n"
            f"Key findings: {', '.join(f.key_findings[:5]) if f.key_findings else 'None'}\n"
            f"Recommendations: {', '.join(f.recommendations[:3]) if f.recommendations else 'None'}\n"
            f"Open questions: {', '.join(f.open_questions[:3]) if f.open_questions else 'None'}"
            for f in findings
        ])

        prompt = f"""Synthesize these research findings into a coherent summary:

Topic: {self.topic}

{findings_text}

Return your synthesis as JSON.
"""

        try:
            response = await coordinator.call(str, prompt)
            await coordinator.close()

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
        print(f"[Coordinator] Decomposing topic into sections...", file=sys.stderr)
        sections = await self.decompose()
        print(f"[Coordinator] Created {len(sections)} sections", file=sys.stderr)

        for s in sections:
            print(f"  - {s.title} ({s.tool_hint})", file=sys.stderr)

        print(f"[Coordinator] Researching sections in parallel...", file=sys.stderr)
        findings = await self.research_sections(sections)
        print(f"[Coordinator] Completed {len(findings)} research tasks", file=sys.stderr)

        print(f"[Coordinator] Synthesizing findings...", file=sys.stderr)
        document = await self.synthesize(findings)
        print(f"[Coordinator] Research complete", file=sys.stderr)

        return document


# =============================================================================
# CLI Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Native REPL Research Coordinator (Approach 3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic research
  %(prog)s --topic "Python async patterns" --output research.md

  # Deep research with more sections
  %(prog)s --topic "AI observability" --depth deep --max-sections 7

  # With tracking enabled
  %(prog)s --topic "MCP architecture" --track --output research.md

  # JSON output
  %(prog)s --topic "API design" --format json --output research.json
        """
    )

    parser.add_argument(
        "--topic", "-t",
        required=True,
        help="Research topic to investigate"
    )
    parser.add_argument(
        "--depth", "-d",
        choices=["standard", "deep"],
        default="standard",
        help="Research depth (default: standard)"
    )
    parser.add_argument(
        "--max-sections", "-m",
        type=int,
        default=5,
        help="Maximum sections to create (default: 5)"
    )
    parser.add_argument(
        "--model",
        help="Model to use for Agentica agents (e.g., anthropic:claude-sonnet-4)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--track",
        action="store_true",
        help="Enable CoordinationDB tracking"
    )
    parser.add_argument(
        "--no-track",
        action="store_true",
        help="Disable CoordinationDB tracking (default behavior)"
    )

    return parser.parse_args()


async def main() -> None:
    """Main entry point for CLI."""
    args = parse_args()

    # Setup coordination DB if tracking enabled
    db = None
    if args.track:
        try:
            from scripts.agentica.coordination import CoordinationDB
            db = CoordinationDB()
            print(f"[Tracking] Session: {db.session_id}", file=sys.stderr)
        except ImportError:
            print("[Warning] CoordinationDB not available, tracking disabled", file=sys.stderr)

    # Create coordinator
    coordinator = ResearchCoordinator(
        topic=args.topic,
        depth=args.depth,
        max_sections=args.max_sections,
        model=args.model,
        db=db,
    )

    print(f"=== Native REPL Research Coordinator ===", file=sys.stderr)
    print(f"Topic: {args.topic}", file=sys.stderr)
    print(f"Depth: {args.depth}, Max sections: {args.max_sections}", file=sys.stderr)
    print(f"", file=sys.stderr)

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
        print(f"[Output] Research saved to: {args.output}", file=sys.stderr)
    else:
        print(output)

    # Print tracking summary if enabled
    if db:
        try:
            summary = db.get_session_summary()
            print(f"\n=== Tracking Summary ===", file=sys.stderr)
            print(f"Agents: {summary.get('agents_by_status', {})}", file=sys.stderr)
            print(f"Patterns: {summary.get('agents_by_pattern', {})}", file=sys.stderr)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
