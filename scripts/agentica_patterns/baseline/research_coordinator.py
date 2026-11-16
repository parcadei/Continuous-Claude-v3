"""
Hierarchical Research Coordinator - Multi-agent research with MCP tools.

Implements a research pattern where:
1. Coordinator decomposes topic into logical sections
2. Specialist agents research sections in parallel
3. Coordinator synthesizes findings into final document

USAGE:
    uv run python scripts/agentica/research_coordinator.py \
        --topic "best practices for Python async error handling" \
        --output research-output.md

    # With specific research depth
    uv run python scripts/agentica/research_coordinator.py \
        --topic "React hooks patterns 2025" \
        --depth deep \
        --output react-research.md

REQUIRES:
    - PERPLEXITY_API_KEY in environment
    - uv sync --extra agentica
"""

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - run: uv sync --extra agentica")


@dataclass
class ResearchSection:
    """A section of research to be investigated by a specialist."""

    name: str  # Section identifier (e.g., "authentication", "database")
    title: str  # Human-readable title (e.g., "Authentication Best Practices")
    research_focus: str  # What to research (detailed prompt for specialist)
    tool_hint: str = "web"  # "web" for Perplexity, "library" for Nia, "both"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "research_focus": self.research_focus,
            "tool_hint": self.tool_hint,
        }


@dataclass
class ResearchFindings:
    """Structured output from a specialist's research."""

    section_name: str
    key_findings: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)  # [{"title": ..., "url": ...}]
    recommendations: list[str] = field(default_factory=list)
    code_examples: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_response: str = ""  # Full response for debugging

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_name": self.section_name,
            "key_findings": self.key_findings,
            "sources": self.sources,
            "recommendations": self.recommendations,
            "code_examples": self.code_examples,
            "open_questions": self.open_questions,
        }

    def to_markdown(self) -> str:
        """Format findings as markdown section."""
        lines = [f"## {self.section_name.title()}\n"]

        if self.key_findings:
            lines.append("### Key Findings\n")
            for finding in self.key_findings:
                lines.append(f"- {finding}")
            lines.append("")

        if self.code_examples:
            lines.append("### Code Examples\n")
            for example in self.code_examples:
                lines.append(f"```\n{example}\n```")
            lines.append("")

        if self.recommendations:
            lines.append("### Recommendations\n")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        if self.sources:
            lines.append("### Sources\n")
            for src in self.sources[:5]:  # Top 5 sources
                title = src.get("title", src.get("url", "Unknown"))
                url = src.get("url", "")
                if url:
                    lines.append(f"- [{title}]({url})")
                else:
                    lines.append(f"- {title}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class ResearchDocument:
    """Final synthesized research document."""

    topic: str
    executive_summary: str
    sections: list[ResearchFindings]
    overall_recommendations: list[str]
    next_steps: list[str]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_sources: int = 0
    research_depth: str = "standard"

    def to_dict(self) -> dict[str, Any]:
        """Serialize document to dictionary."""
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
        """Generate full research document as markdown."""
        lines = [
            f"# Research: {self.topic}",
            f"\n*Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*",
            f"*Depth: {self.research_depth}*\n",
            "---\n",
            "## Executive Summary\n",
            self.executive_summary,
            "\n---\n",
        ]

        # Add each section
        for section in self.sections:
            lines.append(section.to_markdown())

        # Overall recommendations
        if self.overall_recommendations:
            lines.append("---\n")
            lines.append("## Overall Recommendations\n")
            for i, rec in enumerate(self.overall_recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Next steps
        if self.next_steps:
            lines.append("## Next Steps\n")
            for step in self.next_steps:
                lines.append(f"- [ ] {step}")
            lines.append("")

        # Metadata
        lines.append("---\n")
        lines.append(f"*Total sources consulted: {self.total_sources}*")

        return "\n".join(lines)


# ============================================================================
# MCP Tool Wrappers
# ============================================================================


def _get_project_dir() -> Path:
    """Get project directory for running scripts."""
    return Path(__file__).parent.parent.parent


def call_perplexity_sync(
    query: str,
    mode: str = "research"
) -> dict[str, Any]:
    """
    Synchronous Perplexity search for use in agent scope.

    Args:
        query: Research query
        mode: "ask" (quick), "research" (thorough), "deep" (comprehensive)

    Returns:
        Dict with "answer" and "success" keys
    """
    project_dir = _get_project_dir()
    script = project_dir / "scripts" / "perplexity_search.py"

    mode_flag = {
        "ask": "--ask",
        "research": "--research",
        "reason": "--reason",
        "deep": "--deep",
    }.get(mode, "--research")

    try:
        result = subprocess.run(
            ["uv", "run", "python", str(script), mode_flag, query],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120,  # 2 minutes for deep research
        )

        if result.returncode != 0:
            return {"error": result.stderr, "success": False}

        # Return output as answer
        return {"answer": result.stdout, "success": True}

    except subprocess.TimeoutExpired:
        return {"error": "Perplexity search timed out after 120s", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def call_nia_sync(
    package: str,
    query: str,
    registry: str = "py_pi"
) -> dict[str, Any]:
    """
    Synchronous Nia documentation search for use in agent scope.

    Args:
        package: Package name (e.g., "aiohttp", "react")
        query: What to search for in the docs
        registry: "npm", "py_pi", "crates", "go_modules"

    Returns:
        Dict with documentation content
    """
    project_dir = _get_project_dir()
    script = project_dir / "scripts" / "nia_docs.py"

    try:
        result = subprocess.run(
            [
                "uv", "run", "python", str(script),
                "--package", package,
                "--query", query,
                "--registry", registry,
            ],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=30,
        )

        if result.returncode != 0:
            return {"error": result.stderr, "success": False}

        return {"content": result.stdout, "success": True}

    except subprocess.TimeoutExpired:
        return {"error": "Nia docs search timed out after 30s", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


# High-level wrapper functions for agent scope
def perplexity_research(query: str) -> str:
    """Search the web for research on a topic. Returns synthesized answer."""
    result = call_perplexity_sync(query, mode="research")
    if result.get("success"):
        return result.get("answer", "No results found")
    return f"Error: {result.get('error', 'Unknown error')}"


def perplexity_deep(query: str) -> str:
    """Deep comprehensive research on a topic. Takes longer but more thorough."""
    result = call_perplexity_sync(query, mode="deep")
    if result.get("success"):
        return result.get("answer", "No results found")
    return f"Error: {result.get('error', 'Unknown error')}"


def library_docs(package: str, query: str) -> str:
    """Search library documentation. Specify the package name and your query."""
    result = call_nia_sync(package, query)
    if result.get("success"):
        return result.get("content", "No documentation found")
    return f"Error: {result.get('error', 'Unknown error')}"


# ============================================================================
# Research Coordinator Class
# ============================================================================


class ResearchCoordinator:
    """
    Hierarchical research coordinator with MCP tool integration.

    Flow:
    1. Coordinator analyzes topic and decomposes into sections
    2. Specialist agents research each section in parallel
    3. Specialists use MCP tools (Perplexity, Nia) for actual research
    4. Coordinator synthesizes findings into final document

    Example:
        coordinator = ResearchCoordinator(
            topic="Python async error handling best practices",
            depth="deep",
            db=CoordinationDB()
        )
        document = await coordinator.research()
        print(document.to_markdown())
    """

    COORDINATOR_PREMISE = """You are a research coordinator. Your job is to:
1. Analyze research topics and break them into logical sections
2. Assign sections to specialist researchers
3. Synthesize findings into comprehensive reports

When decomposing a topic:
- Create 3-5 focused sections that cover the topic comprehensively
- Each section should be researchable independently
- Indicate whether each section needs web research or library documentation

CRITICAL: You must return valid JSON. Do not add any text before or after the JSON.
"""

    SPECIALIST_PREMISE = """You are a research specialist. Your job is to:
1. Research your assigned section thoroughly using the provided tools
2. Extract key findings, code examples, and recommendations
3. Return structured findings for synthesis

You have access to these tools:
- perplexity_research(query) - Search the web for information
- perplexity_deep(query) - Comprehensive web research (use for complex topics)
- library_docs(package, query) - Search library documentation

CRITICAL RULES:
- You MUST call the appropriate tool to gather real information
- Do NOT make up facts or pretend you already know the answer
- Do NOT claim you found information without actually calling a tool
- If a tool call fails, report the error - do not fabricate results
- Return your findings as valid JSON

Return your findings in this exact JSON format:
{
    "key_findings": ["finding 1", "finding 2", ...],
    "code_examples": ["code example 1", ...],
    "recommendations": ["recommendation 1", ...],
    "sources": [{"title": "Source Title", "url": "https://..."}],
    "open_questions": ["question 1", ...]
}
"""

    def __init__(
        self,
        topic: str,
        depth: str = "standard",  # "quick", "standard", "deep"
        max_sections: int = 5,
        model: str = "anthropic:claude-sonnet-4.5",
        db: Optional["CoordinationDB"] = None,
    ):
        """
        Initialize research coordinator.

        Args:
            topic: Research topic/question
            depth: Research depth ("quick", "standard", "deep")
            max_sections: Maximum sections to decompose into
            model: Model for coordinator and specialists
            db: Optional coordination database for tracking
        """
        self.topic = topic
        self.depth = depth
        self.max_sections = max_sections
        self.model = model
        self.db = db

        # Will be populated during research
        self.sections: list[ResearchSection] = []
        self.findings: list[ResearchFindings] = []
        self.coordinator = None

        # Tool scope for specialists
        self.specialist_scope = {
            "perplexity_research": perplexity_research,
            "perplexity_deep": perplexity_deep,
            "library_docs": library_docs,
        }

    async def _spawn_coordinator(self):
        """Lazily spawn the coordinator agent."""
        if self.coordinator is None:
            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.coordinator = await tracked_spawn(
                    db=self.db,
                    premise=self.COORDINATOR_PREMISE,
                    model=self.model,
                    pattern="research_coordinator",
                )
            else:
                self.coordinator = await spawn(
                    premise=self.COORDINATOR_PREMISE,
                    model=self.model,
                )

    async def decompose(self) -> list[ResearchSection]:
        """
        Have coordinator decompose topic into research sections.

        Returns:
            List of ResearchSection objects
        """
        await self._spawn_coordinator()

        decompose_prompt = f"""
Analyze this research topic and decompose it into {self.max_sections} focused sections:

Topic: {self.topic}

For each section, provide:
1. name: Short identifier (snake_case)
2. title: Human-readable title
3. research_focus: Detailed description of what to research
4. tool_hint: "web" for general research, "library" for documentation, "both" for comprehensive

Return ONLY a JSON array with no additional text:
[
    {{
        "name": "example_section",
        "title": "Example Section Title",
        "research_focus": "Research about...",
        "tool_hint": "web"
    }}
]
"""

        response = await self.coordinator.call(str, decompose_prompt)

        # Parse JSON from response
        try:
            # Find JSON in response (may have markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            sections_data = json.loads(json_str.strip())
            self.sections = [
                ResearchSection(**s) for s in sections_data[:self.max_sections]
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fallback: create single section with full topic
            self.sections = [
                ResearchSection(
                    name="main_research",
                    title=self.topic,
                    research_focus=self.topic,
                    tool_hint="both",
                )
            ]

        return self.sections

    async def _research_section(self, section: ResearchSection) -> ResearchFindings:
        """
        Have a specialist research a single section.

        Args:
            section: Section to research

        Returns:
            ResearchFindings from the specialist
        """
        # Spawn specialist with MCP tools
        if self.db:
            from scripts.agentica_patterns.tracked_agent import tracked_spawn
            specialist = await tracked_spawn(
                db=self.db,
                premise=self.SPECIALIST_PREMISE,
                model=self.model,
                scope=self.specialist_scope,
                pattern="research_specialist",
            )
        else:
            specialist = await spawn(
                premise=self.SPECIALIST_PREMISE,
                model=self.model,
                scope=self.specialist_scope,
            )

        # Determine research approach based on tool_hint and depth
        tool_guidance = ""
        if section.tool_hint == "library":
            tool_guidance = "Use library_docs() to search official documentation."
        elif section.tool_hint == "web":
            if self.depth == "deep":
                tool_guidance = "Use perplexity_deep() for comprehensive research."
            else:
                tool_guidance = "Use perplexity_research() for web research."
        else:  # both
            if self.depth == "deep":
                tool_guidance = "Use both perplexity_deep() and library_docs() for comprehensive coverage."
            else:
                tool_guidance = "Use both perplexity_research() and library_docs() as appropriate."

        research_prompt = f"""
Research this section thoroughly:

Section: {section.title}
Focus: {section.research_focus}

{tool_guidance}

IMPORTANT: You MUST call the tool(s) to get real information. Do NOT skip the tool call.
Do NOT claim to have found information without actually calling a tool.

After gathering information from the tool(s), return your findings as JSON:
{{
    "key_findings": ["finding 1", "finding 2", ...],
    "code_examples": ["code example 1", ...],
    "recommendations": ["recommendation 1", ...],
    "sources": [{{"title": "Source Title", "url": "https://..."}}],
    "open_questions": ["question 1", ...]
}}
"""

        response = await specialist.call(str, research_prompt)

        # Parse findings from response
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())
            return ResearchFindings(
                section_name=section.title,
                key_findings=data.get("key_findings", []),
                sources=data.get("sources", []),
                recommendations=data.get("recommendations", []),
                code_examples=data.get("code_examples", []),
                open_questions=data.get("open_questions", []),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            # Return raw response as finding
            return ResearchFindings(
                section_name=section.title,
                key_findings=[response[:500] if response else "No response received"],
                raw_response=response,
            )

    async def research_sections(self) -> list[ResearchFindings]:
        """
        Research all sections in parallel.

        Returns:
            List of ResearchFindings from all specialists
        """
        if not self.sections:
            await self.decompose()

        # Run all specialists in parallel
        tasks = [self._research_section(section) for section in self.sections]
        self.findings = await asyncio.gather(*tasks)

        return self.findings

    async def synthesize(self) -> ResearchDocument:
        """
        Have coordinator synthesize findings into final document.

        Returns:
            Complete ResearchDocument
        """
        if not self.findings:
            await self.research_sections()

        await self._spawn_coordinator()

        # Compile findings for synthesis
        findings_text = ""
        total_sources = 0
        for finding in self.findings:
            findings_text += f"\n\n## {finding.section_name}\n"
            findings_text += f"Key Findings: {finding.key_findings}\n"
            findings_text += f"Recommendations: {finding.recommendations}\n"
            findings_text += f"Open Questions: {finding.open_questions}\n"
            total_sources += len(finding.sources)

        synthesis_prompt = f"""
Synthesize these research findings into a coherent research document.

Original Topic: {self.topic}

Findings from specialists:
{findings_text}

Provide:
1. executive_summary: 2-3 paragraph summary of key insights
2. overall_recommendations: Top 5-7 actionable recommendations
3. next_steps: Suggested follow-up actions

Return ONLY valid JSON with no additional text:
{{
    "executive_summary": "...",
    "overall_recommendations": ["rec 1", ...],
    "next_steps": ["step 1", ...]
}}
"""

        response = await self.coordinator.call(str, synthesis_prompt)

        # Parse synthesis
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())
            return ResearchDocument(
                topic=self.topic,
                executive_summary=data.get("executive_summary", ""),
                sections=self.findings,
                overall_recommendations=data.get("overall_recommendations", []),
                next_steps=data.get("next_steps", []),
                total_sources=total_sources,
                research_depth=self.depth,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fallback with raw findings
            return ResearchDocument(
                topic=self.topic,
                executive_summary=response[:1000] if response else "Unable to synthesize findings.",
                sections=self.findings,
                overall_recommendations=[],
                next_steps=[],
                total_sources=total_sources,
                research_depth=self.depth,
            )

    async def research(self) -> ResearchDocument:
        """
        Execute full research workflow.

        Returns:
            Complete ResearchDocument with all findings synthesized
        """
        await self.decompose()
        await self.research_sections()
        return await self.synthesize()


# ============================================================================
# CLI Entry Point
# ============================================================================


async def main():
    """CLI entry point for research coordinator."""
    parser = argparse.ArgumentParser(
        description="Hierarchical Research Coordinator with MCP tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Quick research
    %(prog)s --topic "Python async patterns" --output research.md

    # Deep comprehensive research
    %(prog)s --topic "React hooks 2025" --depth deep --output react.md

    # With observability tracking
    %(prog)s --topic "API design patterns" --track --output api.md
"""
    )
    parser.add_argument(
        "--topic", "-t",
        type=str,
        required=True,
        help="Research topic or question"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path for markdown document"
    )
    parser.add_argument(
        "--depth", "-d",
        type=str,
        choices=["quick", "standard", "deep"],
        default="standard",
        help="Research depth (default: standard)"
    )
    parser.add_argument(
        "--max-sections", "-m",
        type=int,
        default=5,
        help="Maximum sections to decompose into (default: 5)"
    )
    parser.add_argument(
        "--track",
        action="store_true",
        help="Enable CoordinationDB tracking for observability"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of markdown"
    )
    args = parser.parse_args()

    # Setup coordination DB if tracking enabled
    db = None
    if args.track:
        from scripts.agentica_patterns.coordination import CoordinationDB
        db = CoordinationDB()
        print(f"Tracking enabled. Session: {db.session_id}")

    print(f"Researching: {args.topic}")
    print(f"Depth: {args.depth}")
    print(f"Max sections: {args.max_sections}")
    print("-" * 50)

    # Create coordinator and run research
    coordinator = ResearchCoordinator(
        topic=args.topic,
        depth=args.depth,
        max_sections=args.max_sections,
        db=db,
    )

    try:
        document = await coordinator.research()

        # Format output
        if args.json:
            output = json.dumps(document.to_dict(), indent=2)
        else:
            output = document.to_markdown()

        # Write or print output
        if args.output:
            Path(args.output).write_text(output)
            print(f"\nResearch document written to: {args.output}")
        else:
            print("\n" + output)

        # Print tracking summary
        if db:
            summary = db.get_session_summary()
            print(f"\n--- Tracking Summary ---")
            print(f"Agents: {summary['agents_by_status']}")
            print(f"Patterns: {summary['agents_by_pattern']}")
            print(f"Tasks: {summary['total_tasks']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if db:
            print(f"Check coordination DB for details: {db.db_path}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


# Type hint import for CoordinationDB (avoid circular import)
if False:  # TYPE_CHECKING
    from scripts.agentica_patterns.coordination import CoordinationDB
