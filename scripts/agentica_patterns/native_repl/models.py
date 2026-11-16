"""Data models for the Native REPL Research Coordinator.

This module contains the data classes used throughout the research workflow.
No business logic - only data structures with serialization methods.

Classes:
    ResearchSection: A section of research to be investigated
    ResearchFindings: Results from a specialist researching a section
    ResearchDocument: Final synthesized research document
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

# Type alias for tool hints
ToolHint = Literal["web", "codebase", "docs", "all"]


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
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
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
