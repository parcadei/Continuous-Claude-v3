"""ResearchCoordinator for the Native REPL approach.

This module contains the main coordinator class that orchestrates
multi-agent research using Claude Code CLI via run_claude().

Classes:
    ResearchCoordinator: Main orchestration class

Scope Persistence Pattern:
    Agentica REPL loses local variables between turns. To persist data,
    pass a mutable scope dict that agents write to by reference:

        scope = {"results": {}}
        agent = await spawn(premise="...", scope=scope)
        await agent.call(str, "Store findings in results['key']")
        # scope["results"]["key"] now contains the result
"""

import asyncio
from typing import TYPE_CHECKING, Any

from .json_utils import parse_json_dict, parse_json_list
from .models import ResearchDocument, ResearchFindings, ResearchSection
from .tools import get_tool_scope

# Import spawn from agentica (with fallback for testing)
try:
    from agentica import spawn
except ImportError:

    async def spawn(**kwargs: Any) -> Any:  # type: ignore[misc]
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")


# Import tracked_spawn for CoordinationDB integration
try:
    from scripts.agentica_patterns.tracked_agent import tracked_spawn
except ImportError:

    async def tracked_spawn(**kwargs: Any) -> Any:  # type: ignore[misc]
        """Stub tracked_spawn for testing."""
        raise NotImplementedError("tracked_agent not available")


if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class ResearchCoordinator:
    """Hierarchical coordinator for multi-agent research using Native REPL.

    This is Approach 3 - Native REPL:
    - Intelligence layer: Claude via Agentica agents
    - Execution layer: Claude Code CLI via run_claude()
    - Tool access: Claude Code handles tool selection internally

    Scope Persistence:
        The coordinator uses mutable scope dicts to persist data between
        REPL turns. Agents write to scope["results"] rather than using
        local variables, which are lost between turns.

    Example:
        >>> coordinator = ResearchCoordinator("Python async patterns")
        >>> document = await coordinator.research()
        >>> print(document.to_markdown())
    """

    def __init__(
        self,
        topic: str,
        depth: str = "standard",
        max_sections: int = 5,
        model: str | None = None,
        db: "CoordinationDB | None" = None,
    ):
        """Initialize the research coordinator."""
        self.topic = topic
        self.depth = depth
        self.max_sections = max_sections
        self.model = model
        self.db = db
        # Base tool scope from tools.py
        self._base_tool_scope = get_tool_scope()

    def _create_specialist_scope(self) -> dict[str, Any]:
        """Create a mutable scope for specialist agents.

        Returns a scope dict that includes:
        - All tools from get_tool_scope()
        - A mutable 'results' dict for persisting data between turns

        The 'results' dict persists by reference, so agents can store
        findings there and the coordinator can retrieve them after.

        Returns:
            Scope dict with tools and results container
        """
        scope = dict(self._base_tool_scope)  # Copy base tools
        scope["results"] = {}  # Mutable container for findings
        return scope

    async def _spawn_agent(
        self,
        premise: str,
        scope: dict[str, Any] | None = None,
        pattern: str = "native_repl_coordinator",
    ) -> Any:
        """Spawn an agent with optional tracking."""
        spawn_kwargs: dict[str, Any] = {"premise": premise}
        if self.model:
            spawn_kwargs["model"] = self.model
        if scope:
            spawn_kwargs["scope"] = scope

        if self.db:
            return await tracked_spawn(db=self.db, pattern=pattern, **spawn_kwargs)
        return await spawn(**spawn_kwargs)

    async def decompose(self) -> list[ResearchSection]:
        """Decompose the topic into research sections."""
        premise = """You are a research coordinator who breaks down topics.
Return a JSON array with: name, title, research_focus, tool_hint.
tool_hint is one of: "web", "codebase", "docs", or "all"
"""
        coordinator = await self._spawn_agent(
            premise, pattern="native_repl_coordinator"
        )

        prompt = f"""Decompose this research topic into focused sections:

Topic: {self.topic}
Depth: {self.depth}
Max sections: {self.max_sections}

Return ONLY a JSON array with the sections.
"""
        try:
            response = await coordinator.call(str, prompt)
            await coordinator.close()
            sections_data = parse_json_list(response)

            if not sections_data:
                return [self._fallback_section()]

            return [
                ResearchSection(
                    name=item.get("name", "unknown"),
                    title=item.get("title", "Unknown Section"),
                    research_focus=item.get("research_focus", ""),
                    tool_hint=item.get("tool_hint", "all"),
                )
                for item in sections_data[: self.max_sections]
            ]
        except Exception:
            return [self._fallback_section()]

    def _fallback_section(self) -> ResearchSection:
        """Create a fallback section when decomposition fails."""
        return ResearchSection(
            name="general_research",
            title="General Research",
            research_focus=f"Research the topic: {self.topic}",
            tool_hint="all",
        )

    async def _research_section(
        self, section: ResearchSection
    ) -> ResearchFindings:
        """Have a specialist agent research a section.

        Uses mutable scope pattern for reliable result capture:
        - Creates scope with 'results' dict
        - Agent writes findings to results['findings']
        - Coordinator extracts from scope after call
        """
        # Create mutable scope for this specialist
        scope = self._create_specialist_scope()

        premise = self._build_specialist_premise(section)
        specialist = await self._spawn_agent(
            premise, scope=scope, pattern="native_repl_specialist"
        )

        prompt = f"""Research this topic in depth:

{section.research_focus}

Use the available research tools (await them).

IMPORTANT: Store your findings in results['findings'] as a dict with:
- key_findings: list of key facts discovered
- sources: list of URLs/references
- recommendations: list of recommendations

Example:
```python
findings_data = await comprehensive_research("{section.research_focus}")
results['findings'] = {{
    "key_findings": [...],
    "sources": [...],
    "recommendations": [...]
}}
```

Do NOT use local variables to store results - they are lost between turns.
Write directly to results['findings'] to persist the data.
"""
        try:
            await specialist.call(str, prompt)
            await specialist.close()

            # Extract findings from mutable scope
            findings_data = scope.get("results", {}).get("findings", {})

            # Handle case where agent returned JSON string instead of dict
            if isinstance(findings_data, str):
                findings_data = parse_json_dict(findings_data)

            return ResearchFindings(
                section_name=section.title,
                key_findings=findings_data.get("key_findings", []),
                sources=findings_data.get("sources", []),
                recommendations=findings_data.get("recommendations", []),
                code_examples=findings_data.get("code_examples", []),
                open_questions=findings_data.get("open_questions", []),
                raw_response=str(findings_data),
            )
        except Exception as e:
            return ResearchFindings(
                section_name=section.title, raw_response=f"Error: {e}"
            )

    def _build_specialist_premise(self, section: ResearchSection) -> str:
        """Build premise for specialist based on section and tool hint."""
        tool_docs = {
            "web": "- web_research(query)\n- comprehensive_research(topic)",
            "codebase": "- codebase_research(query, path)\n- comprehensive_research(topic)",
            "docs": "- docs_research(url, query)\n- web_research(query)",
            "all": (
                "- web_research(query)\n- codebase_research(query, path)\n"
                "- docs_research(url, query)\n- comprehensive_research(topic)"
            ),
        }
        tools = tool_docs.get(section.tool_hint, tool_docs["all"])

        return f"""You are a specialist researcher for: {section.title}

Available tools (use await):
{tools}

CRITICAL: Store all results in the 'results' dict provided in your scope.
Local variables are LOST between REPL turns. Use results['findings'] to persist data.

Return findings as dict with: key_findings, sources, recommendations
"""

    async def research_sections(
        self, sections: list[ResearchSection]
    ) -> list[ResearchFindings]:
        """Research all sections in parallel."""

        async def safe_research(section: ResearchSection) -> ResearchFindings:
            try:
                return await self._research_section(section)
            except Exception as e:
                return ResearchFindings(
                    section_name=section.title, raw_response=f"Error: {e}"
                )

        results = await asyncio.gather(
            *[safe_research(section) for section in sections],
            return_exceptions=False
        )
        return list(results)

    def _format_finding_summary(self, finding: ResearchFindings) -> str:
        """Format a finding as a summary for synthesis."""
        key = ", ".join(finding.key_findings[:5]) if finding.key_findings else "None"
        recs = ", ".join(finding.recommendations[:3]) if finding.recommendations else "None"
        return f"### {finding.section_name}\nFindings: {key}\nRecommendations: {recs}"

    async def synthesize(
        self, findings: list[ResearchFindings]
    ) -> ResearchDocument:
        """Synthesize findings into a research document."""
        total_sources = sum(len(f.sources) for f in findings)

        premise = """You are a research synthesizer. Return synthesis as JSON:
- executive_summary: 2-3 paragraph overview
- overall_recommendations: List of recommendations
- next_steps: List of follow-up actions
"""
        coordinator = await self._spawn_agent(
            premise, pattern="native_repl_coordinator"
        )

        findings_text = "\n\n".join(
            self._format_finding_summary(f) for f in findings
        )

        prompt = f"""Synthesize these research findings:

Topic: {self.topic}

{findings_text}

Return your synthesis as JSON.
"""
        try:
            response = await coordinator.call(str, prompt)
            await coordinator.close()
            synthesis = parse_json_dict(response)

            return ResearchDocument(
                topic=self.topic,
                executive_summary=synthesis.get("executive_summary", ""),
                sections=findings,
                overall_recommendations=synthesis.get("overall_recommendations", []),
                next_steps=synthesis.get("next_steps", []),
                total_sources=total_sources,
                research_depth=self.depth,
            )
        except Exception as e:
            import sys
            print(f"[Coordinator] Synthesis error: {type(e).__name__}: {e}", file=sys.stderr)
            return ResearchDocument(
                topic=self.topic,
                sections=findings,
                total_sources=total_sources,
                research_depth=self.depth,
            )

    async def research(self) -> ResearchDocument:
        """Execute the full research workflow."""
        sections = await self.decompose()
        findings = await self.research_sections(sections)
        return await self.synthesize(findings)
