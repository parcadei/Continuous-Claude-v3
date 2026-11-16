#!/usr/bin/env python3
"""
Hierarchical Research Coordinator - Multi-agent research with MCP tools.

Implements a research pattern where:
1. Coordinator decomposes topic into logical sections
2. Specialist agents research sections in parallel
3. Coordinator synthesizes findings into final document

USAGE:
    uv run python scripts/agentica/native_repl/research_coordinator.py \
        --topic "best practices for Python async error handling" \
        --output research-output.md

    # With specific research depth
    uv run python scripts/agentica/native_repl/research_coordinator.py \
        --topic "React hooks patterns 2025" \
        --depth deep \
        --output react-research.md

    # JSON output
    uv run python scripts/agentica/native_repl/research_coordinator.py \
        --topic "MCP server architecture" \
        --format json \
        --output research.json

REQUIRES:
    - PERPLEXITY_API_KEY in environment
    - uv sync --extra agentica
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal

# Add project root to path for runtime imports
sys.path.insert(0, str(__file__).rsplit("/scripts", 1)[0])

from runtime.mcp_client import get_mcp_client_manager


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ResearchSection:
    """A section of research to be investigated by a specialist."""

    name: str  # Section identifier (e.g., "authentication", "database")
    title: str  # Human-readable title (e.g., "Authentication Best Practices")
    questions: list[str]  # Specific questions to research
    source_preference: Literal["web", "docs", "both"] = "web"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "questions": self.questions,
            "source_preference": self.source_preference,
        }


@dataclass
class ResearchFindings:
    """Structured output from a specialist's research."""

    section: ResearchSection
    web_results: list[str] = field(default_factory=list)
    doc_results: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    raw_responses: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section.to_dict(),
            "web_results": self.web_results,
            "doc_results": self.doc_results,
            "sources": self.sources,
        }

    def to_markdown(self) -> str:
        """Format findings as markdown section."""
        lines = [f"## {self.section.title}\n"]

        if self.web_results:
            lines.append("### Web Research Findings\n")
            for result in self.web_results:
                # Indent multi-line results
                formatted = result.replace("\n", "\n> ")
                lines.append(f"> {formatted}\n")

        if self.doc_results:
            lines.append("### Documentation Findings\n")
            for result in self.doc_results:
                formatted = result.replace("\n", "\n> ")
                lines.append(f"> {formatted}\n")

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

    title: str
    summary: str
    sections: list[ResearchFindings]
    recommendations: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    total_sources: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "recommendations": self.recommendations,
            "next_steps": self.next_steps,
            "generated_at": self.generated_at.isoformat(),
            "total_sources": self.total_sources,
        }

    def to_markdown(self) -> str:
        """Generate full research document as markdown."""
        lines = [
            f"# {self.title}",
            "",
            f"*Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*",
            "",
            "## Executive Summary",
            "",
            self.summary,
            "",
        ]

        # Add each section
        for finding in self.sections:
            lines.append(finding.to_markdown())

        # Recommendations
        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Next steps
        if self.next_steps:
            lines.append("## Next Steps")
            lines.append("")
            for step in self.next_steps:
                lines.append(f"- {step}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Total sources consulted: {self.total_sources}*")

        return "\n".join(lines)


# ============================================================================
# MCP Tool Wrappers (Synchronous for use in non-async contexts)
# ============================================================================


async def _call_perplexity_async(query: str, mode: str = "research") -> dict[str, Any]:
    """Async wrapper for Perplexity MCP tool."""
    mgr = get_mcp_client_manager()
    await mgr.initialize()
    tool_name = f"perplexity__perplexity_{mode}"
    result = await mgr.call_tool(tool_name, {"query": query})
    return result


async def _call_nia_async(query: str, library: str | None = None) -> dict[str, Any]:
    """Async wrapper for Nia MCP tool."""
    mgr = get_mcp_client_manager()
    await mgr.initialize()
    params = {"query": query}
    if library:
        params["library"] = library
    result = await mgr.call_tool("nia__search", params)
    return result


def call_perplexity_sync(query: str, mode: str = "research") -> dict[str, Any]:
    """Synchronous wrapper for Perplexity MCP tool.

    Args:
        query: Research query
        mode: One of "ask", "research", "reason", "deep"

    Returns:
        Research results from Perplexity
    """
    return asyncio.run(_call_perplexity_async(query, mode))


def call_nia_sync(query: str, library: str | None = None) -> dict[str, Any]:
    """Synchronous wrapper for Nia MCP tool.

    Args:
        query: Documentation search query
        library: Optional library to search in

    Returns:
        Documentation results from Nia
    """
    return asyncio.run(_call_nia_async(query, library))


# ============================================================================
# Research Coordinator
# ============================================================================


class ResearchCoordinator:
    """Hierarchical research coordinator using decompose → research → synthesize workflow.

    This class orchestrates a multi-agent research pattern where:
    1. decompose(): Break topic into researchable sections
    2. research(): Execute research for each section using MCP tools
    3. synthesize(): Combine findings into a coherent document
    """

    def __init__(self, topic: str, depth: str = "standard"):
        """Initialize the research coordinator.

        Args:
            topic: The research topic to investigate
            depth: Research depth - "quick", "standard", or "deep"
        """
        self.topic = topic
        self.depth = depth
        self.sections: list[ResearchSection] = []
        self.findings: list[ResearchFindings] = []

    def decompose(self) -> list[ResearchSection]:
        """Break topic into researchable sections.

        Uses a simple heuristic to create sections. In a full implementation,
        this would use Claude to dynamically decompose the topic.

        Returns:
            List of ResearchSection objects
        """
        # For now, use a simple decomposition strategy
        # In production, this would call Claude to intelligently decompose

        # Default sections for any research topic
        self.sections = [
            ResearchSection(
                name="overview",
                title=f"Overview of {self.topic}",
                questions=[
                    f"What is {self.topic}?",
                    f"Why is {self.topic} important?",
                ],
                source_preference="web",
            ),
            ResearchSection(
                name="best_practices",
                title=f"Best Practices for {self.topic}",
                questions=[
                    f"What are the best practices for {self.topic}?",
                    f"What are common mistakes to avoid with {self.topic}?",
                ],
                source_preference="both",
            ),
            ResearchSection(
                name="implementation",
                title=f"Implementation Details",
                questions=[
                    f"How to implement {self.topic}?",
                    f"What are the key considerations for {self.topic}?",
                ],
                source_preference="docs",
            ),
        ]

        # Add more sections for deeper research
        if self.depth == "deep":
            self.sections.append(
                ResearchSection(
                    name="advanced",
                    title=f"Advanced Topics in {self.topic}",
                    questions=[
                        f"What are advanced patterns for {self.topic}?",
                        f"What are edge cases to consider with {self.topic}?",
                    ],
                    source_preference="both",
                )
            )
            self.sections.append(
                ResearchSection(
                    name="future",
                    title=f"Future of {self.topic}",
                    questions=[
                        f"What is the future of {self.topic}?",
                        f"What emerging trends relate to {self.topic}?",
                    ],
                    source_preference="web",
                )
            )

        return self.sections

    async def research_async(self) -> list[ResearchFindings]:
        """Execute research for each section asynchronously.

        Returns:
            List of ResearchFindings, one per section
        """
        if not self.sections:
            self.decompose()

        self.findings = []

        for section in self.sections:
            print(f"🔍 Researching: {section.title}")

            findings = ResearchFindings(section=section)

            # Research based on source preference
            if section.source_preference in ("web", "both"):
                for question in section.questions:
                    try:
                        result = await _call_perplexity_async(question, "research")
                        answer = result.get("answer", result.get("content", str(result)))
                        findings.web_results.append(answer)

                        # Extract sources if available
                        if "sources" in result:
                            findings.sources.extend(result["sources"])

                        findings.raw_responses.append(result)
                    except Exception as e:
                        findings.web_results.append(f"Error: {e}")

            if section.source_preference in ("docs", "both"):
                for question in section.questions:
                    try:
                        result = await _call_nia_async(question)
                        content = result.get("content", result.get("answer", str(result)))
                        findings.doc_results.append(content)
                        findings.raw_responses.append(result)
                    except Exception as e:
                        findings.doc_results.append(f"Error: {e}")

            self.findings.append(findings)

        return self.findings

    def research(self) -> list[ResearchFindings]:
        """Execute research for each section synchronously.

        Returns:
            List of ResearchFindings, one per section
        """
        return asyncio.run(self.research_async())

    def synthesize(self) -> ResearchDocument:
        """Synthesize findings into a coherent research document.

        Returns:
            ResearchDocument with all findings combined
        """
        if not self.findings:
            self.research()

        # Count total sources
        total_sources = sum(len(f.sources) for f in self.findings)

        # Generate summary from findings
        summary_parts = []
        for finding in self.findings:
            if finding.web_results:
                # Take first result as representative
                summary_parts.append(finding.web_results[0][:500])
            elif finding.doc_results:
                summary_parts.append(finding.doc_results[0][:500])

        summary = f"This research document covers {len(self.findings)} key areas of {self.topic}. " + \
                  " ".join(summary_parts[:2])  # First two summaries

        # Generate recommendations based on best practices section
        recommendations = []
        for finding in self.findings:
            if finding.section.name == "best_practices" and finding.web_results:
                # Extract bullet points from results
                for result in finding.web_results[:1]:
                    # Simple extraction of recommendations
                    lines = result.split("\n")
                    for line in lines:
                        if line.strip().startswith(("-", "*", "•", "1", "2", "3")):
                            rec = line.strip().lstrip("-*•0123456789. ")
                            if rec and len(rec) > 10:
                                recommendations.append(rec[:200])

        # Default recommendations if none extracted
        if not recommendations:
            recommendations = [
                f"Review the best practices for {self.topic}",
                "Consider the implementation details carefully",
                "Stay updated on emerging trends in this area",
            ]

        # Generate next steps
        next_steps = [
            f"Deep dive into specific aspects of {self.topic}",
            "Create proof-of-concept implementation",
            "Review and validate findings with domain experts",
        ]

        return ResearchDocument(
            title=f"Research: {self.topic}",
            summary=summary[:1000],  # Limit summary length
            sections=self.findings,
            recommendations=recommendations[:5],  # Top 5 recommendations
            next_steps=next_steps,
            total_sources=total_sources,
        )

    async def execute_async(self) -> ResearchDocument:
        """Execute the full research workflow asynchronously.

        Returns:
            Complete ResearchDocument
        """
        print(f"📋 Decomposing topic: {self.topic}")
        self.decompose()
        print(f"   Created {len(self.sections)} research sections")

        print("🔬 Researching sections...")
        await self.research_async()
        print(f"   Gathered findings from {len(self.findings)} sections")

        print("✨ Synthesizing document...")
        document = self.synthesize()
        print(f"   Document ready with {document.total_sources} sources")

        return document

    def execute(self) -> ResearchDocument:
        """Execute the full research workflow synchronously.

        Returns:
            Complete ResearchDocument
        """
        return asyncio.run(self.execute_async())


# ============================================================================
# CLI Entry Point
# ============================================================================


async def main_async():
    """Async main entry point."""
    parser = argparse.ArgumentParser(
        description="Hierarchical Research Coordinator - Multi-agent research with MCP tools"
    )
    parser.add_argument(
        "--topic", "-t",
        required=True,
        help="Research topic"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--depth", "-d",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="Research depth (default: standard)"
    )

    args = parser.parse_args()

    try:
        coordinator = ResearchCoordinator(args.topic, depth=args.depth)
        document = await coordinator.execute_async()

        if args.format == "json":
            output = json.dumps(document.to_dict(), indent=2, default=str)
        else:
            output = document.to_markdown()

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"\n📄 Saved to {args.output}")
        else:
            print("\n" + "=" * 60)
            print(output)

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


def main():
    """Synchronous main entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
