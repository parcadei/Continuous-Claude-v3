"""Tests for Native REPL Research Coordinator (Approach 3).

Tests the research coordinator that uses run_claude() for tool execution.

The coordinator now uses a mutable scope pattern for reliable result capture:
- Agents write to scope["results"] instead of local variables
- Local variables are lost between REPL turns
- Mutable scope dicts persist by reference
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Data Model Tests
# =============================================================================


class TestResearchSection:
    """Test ResearchSection dataclass."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        from scripts.agentica_patterns.native_repl.models import ResearchSection

        section = ResearchSection(
            name="auth_patterns",
            title="Authentication Patterns",
            research_focus="Research OAuth 2.0 and JWT best practices",
            tool_hint="web",
        )

        d = section.to_dict()
        assert d["name"] == "auth_patterns"
        assert d["title"] == "Authentication Patterns"
        assert d["research_focus"] == "Research OAuth 2.0 and JWT best practices"
        assert d["tool_hint"] == "web"

    def test_default_tool_hint(self):
        """Test default tool_hint is 'all'."""
        from scripts.agentica_patterns.native_repl.models import ResearchSection

        section = ResearchSection(
            name="test",
            title="Test",
            research_focus="Test focus",
        )

        assert section.tool_hint == "all"


class TestResearchFindings:
    """Test ResearchFindings dataclass."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        from scripts.agentica_patterns.native_repl.models import ResearchFindings

        findings = ResearchFindings(
            section_name="authentication",
            key_findings=["OAuth 2.0 is recommended", "Use PKCE for SPAs"],
            sources=["https://oauth.net/2/"],
            recommendations=["Implement token refresh"],
        )

        d = findings.to_dict()
        assert d["section_name"] == "authentication"
        assert len(d["key_findings"]) == 2
        assert len(d["sources"]) == 1
        assert len(d["recommendations"]) == 1

    def test_to_markdown(self):
        """Test markdown conversion."""
        from scripts.agentica_patterns.native_repl.models import ResearchFindings

        findings = ResearchFindings(
            section_name="authentication",
            key_findings=["OAuth 2.0 is recommended"],
            recommendations=["Use PKCE"],
        )

        md = findings.to_markdown()
        assert "## authentication" in md
        assert "### Key Findings" in md
        assert "OAuth 2.0 is recommended" in md
        assert "### Recommendations" in md
        assert "Use PKCE" in md

    def test_to_markdown_empty_sections(self):
        """Test markdown with empty sections."""
        from scripts.agentica_patterns.native_repl.models import ResearchFindings

        findings = ResearchFindings(section_name="empty_test")

        md = findings.to_markdown()
        assert "## empty_test" in md
        # Should not have subsections for empty lists
        assert "### Key Findings" not in md


class TestResearchDocument:
    """Test ResearchDocument dataclass."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        from scripts.agentica_patterns.native_repl.models import (
            ResearchDocument,
            ResearchFindings,
        )

        doc = ResearchDocument(
            topic="Test Research",
            executive_summary="This is a test summary.",
            sections=[
                ResearchFindings(
                    section_name="section1",
                    key_findings=["Finding 1"],
                )
            ],
            overall_recommendations=["Rec 1"],
            next_steps=["Step 1"],
            total_sources=5,
            research_depth="deep",
        )

        d = doc.to_dict()
        assert d["topic"] == "Test Research"
        assert d["executive_summary"] == "This is a test summary."
        assert len(d["sections"]) == 1
        assert d["total_sources"] == 5
        assert d["research_depth"] == "deep"
        assert "generated_at" in d

    def test_to_markdown(self):
        """Test markdown conversion."""
        from scripts.agentica_patterns.native_repl.models import (
            ResearchDocument,
            ResearchFindings,
        )

        doc = ResearchDocument(
            topic="Test Research",
            executive_summary="This is a test summary.",
            sections=[
                ResearchFindings(
                    section_name="section1",
                    key_findings=["Finding 1"],
                )
            ],
            overall_recommendations=["Rec 1", "Rec 2"],
            next_steps=["Step 1"],
        )

        md = doc.to_markdown()
        assert "# Test Research" in md
        assert "## Executive Summary" in md
        assert "This is a test summary." in md
        assert "## Overall Recommendations" in md
        assert "- Rec 1" in md
        assert "## Next Steps" in md
        assert "- Step 1" in md


# =============================================================================
# Tool Wrapper Tests
# =============================================================================


class TestToolWrappers:
    """Test the run_claude tool wrappers."""

    @pytest.mark.asyncio
    async def test_web_research_calls_run_claude(self):
        """web_research should call run_claude with WebSearch tool."""
        with patch(
            "scripts.agentica_patterns.native_repl.tools.run_claude"
        ) as mock_run_claude:
            mock_run_claude.return_value = {"result": "Test research results"}

            from scripts.agentica_patterns.native_repl.tools import web_research

            result = await web_research("Python async patterns")

            mock_run_claude.assert_called_once()
            call_kwargs = mock_run_claude.call_args[1]
            assert "WebSearch" in call_kwargs["tools"]
            assert "Python async patterns" in call_kwargs["task"]

    @pytest.mark.asyncio
    async def test_codebase_research_calls_run_claude(self):
        """codebase_research should call run_claude with Read/Grep/Glob."""
        with patch(
            "scripts.agentica_patterns.native_repl.tools.run_claude"
        ) as mock_run_claude:
            mock_run_claude.return_value = {"result": "Code patterns found"}

            from scripts.agentica_patterns.native_repl.tools import codebase_research

            result = await codebase_research("async patterns", path="scripts/")

            mock_run_claude.assert_called_once()
            call_kwargs = mock_run_claude.call_args[1]
            assert "Read" in call_kwargs["tools"]
            assert "Grep" in call_kwargs["tools"]
            assert "scripts/" in call_kwargs["task"]

    @pytest.mark.asyncio
    async def test_comprehensive_research_depth(self):
        """comprehensive_research should include depth instructions."""
        with patch(
            "scripts.agentica_patterns.native_repl.tools.run_claude"
        ) as mock_run_claude:
            mock_run_claude.return_value = {"result": "Deep research results"}

            from scripts.agentica_patterns.native_repl.tools import comprehensive_research

            result = await comprehensive_research("Topic", depth="deep")

            call_kwargs = mock_run_claude.call_args[1]
            assert "DEEP research" in call_kwargs["task"]


# =============================================================================
# ResearchCoordinator Tests
# =============================================================================


class TestResearchCoordinator:
    """Test ResearchCoordinator class."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Create a mock CoordinationDB."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test-session")

    @pytest.mark.asyncio
    async def test_decompose_parses_json(self, mock_db):
        """Decompose should parse coordinator's JSON response."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="""
```json
[
    {"name": "auth", "title": "Authentication", "research_focus": "OAuth patterns", "tool_hint": "web"},
    {"name": "db", "title": "Database", "research_focus": "SQL patterns", "tool_hint": "codebase"}
]
```
""")
        mock_agent.close = AsyncMock()

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", return_value=mock_agent):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

                coord = ResearchCoordinator(
                    topic="Test topic",
                    db=mock_db,
                )
                sections = await coord.decompose()

                assert len(sections) == 2
                assert sections[0].name == "auth"
                assert sections[0].title == "Authentication"
                assert sections[1].name == "db"

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_error(self, mock_db):
        """Decompose should create fallback section on parsing error."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="Invalid JSON response")
        mock_agent.close = AsyncMock()

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", return_value=mock_agent):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

                coord = ResearchCoordinator(topic="Test topic", db=mock_db)
                sections = await coord.decompose()

                assert len(sections) == 1
                assert sections[0].name == "general_research"
                assert "Test topic" in sections[0].research_focus

    @pytest.mark.asyncio
    async def test_research_section_uses_mutable_scope(self, mock_db):
        """Research section should spawn specialist with mutable scope containing results dict."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="Done")
        mock_agent.close = AsyncMock()

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn") as mock_tracked:
                mock_tracked.return_value = mock_agent

                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
                from scripts.agentica_patterns.native_repl.models import ResearchSection

                coord = ResearchCoordinator(topic="Test", db=mock_db)
                section = ResearchSection(
                    name="test_section",
                    title="Test Section",
                    research_focus="Test focus",
                    tool_hint="web",
                )

                findings = await coord._research_section(section)

                # Verify tracked_spawn was called with scope containing:
                # 1. run_claude wrappers
                # 2. mutable 'results' dict for persistence
                assert mock_tracked.called
                call_kwargs = mock_tracked.call_args[1]
                assert "scope" in call_kwargs
                scope = call_kwargs["scope"]

                # Should have tools
                assert "run_claude" in scope
                assert "web_research" in scope
                assert "comprehensive_research" in scope

                # CRITICAL: Should have mutable results dict
                assert "results" in scope
                assert isinstance(scope["results"], dict)

    @pytest.mark.asyncio
    async def test_research_section_extracts_from_scope(self, mock_db):
        """Research section should extract findings from mutable scope after agent call."""
        captured_scope = {}

        async def capture_scope_spawn(**kwargs):
            """Capture the scope and simulate agent writing to it."""
            scope = kwargs.get("scope", {})
            captured_scope.update(scope)

            # Simulate agent writing to scope["results"]
            if "results" in scope:
                scope["results"]["findings"] = {
                    "key_findings": ["Finding from scope"],
                    "sources": ["https://example.com"],
                    "recommendations": ["Use scope pattern"],
                }

            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="Done")
            mock_agent.close = AsyncMock()
            return mock_agent

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", side_effect=capture_scope_spawn):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", side_effect=capture_scope_spawn):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
                from scripts.agentica_patterns.native_repl.models import ResearchSection

                coord = ResearchCoordinator(topic="Test", db=mock_db)
                section = ResearchSection(
                    name="test_section",
                    title="Test Section",
                    research_focus="Test focus",
                    tool_hint="web",
                )

                findings = await coord._research_section(section)

                # Findings should be extracted from scope
                assert findings.section_name == "Test Section"
                assert "Finding from scope" in findings.key_findings
                assert "https://example.com" in findings.sources
                assert "Use scope pattern" in findings.recommendations

    @pytest.mark.asyncio
    async def test_create_specialist_scope_includes_results(self):
        """_create_specialist_scope should include mutable results dict."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

        coord = ResearchCoordinator(topic="Test")
        scope = coord._create_specialist_scope()

        # Should have all tools
        assert "run_claude" in scope
        assert "web_research" in scope
        assert "codebase_research" in scope
        assert "docs_research" in scope
        assert "comprehensive_research" in scope

        # Should have mutable results dict
        assert "results" in scope
        assert isinstance(scope["results"], dict)
        assert scope["results"] == {}  # Initially empty

    @pytest.mark.asyncio
    async def test_scope_persists_by_reference(self):
        """Verify that scope["results"] persists changes by reference."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

        coord = ResearchCoordinator(topic="Test")
        scope = coord._create_specialist_scope()

        # Simulate agent writing to scope
        scope["results"]["findings"] = {"key_findings": ["test"]}

        # Changes should persist in original scope
        assert scope["results"]["findings"]["key_findings"] == ["test"]

    @pytest.mark.asyncio
    async def test_research_sections_parallel(self, mock_db):
        """Research should execute sections in parallel."""
        async def scope_spawn(**kwargs):
            scope = kwargs.get("scope", {})
            if "results" in scope:
                scope["results"]["findings"] = {
                    "key_findings": ["finding"],
                    "recommendations": [],
                }
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="Done")
            mock_agent.close = AsyncMock()
            return mock_agent

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", side_effect=scope_spawn):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", side_effect=scope_spawn):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
                from scripts.agentica_patterns.native_repl.models import ResearchSection

                coord = ResearchCoordinator(topic="Test", db=mock_db)
                sections = [
                    ResearchSection("s1", "Section 1", "Focus 1", "web"),
                    ResearchSection("s2", "Section 2", "Focus 2", "codebase"),
                    ResearchSection("s3", "Section 3", "Focus 3", "all"),
                ]

                findings = await coord.research_sections(sections)

                assert len(findings) == 3
                # All sections should have been researched
                section_names = {f.section_name for f in findings}
                assert "Section 1" in section_names
                assert "Section 2" in section_names
                assert "Section 3" in section_names

    @pytest.mark.asyncio
    async def test_synthesize_combines_findings(self, mock_db):
        """Synthesize should combine findings into document."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="""
{
    "executive_summary": "Test summary of all findings.",
    "overall_recommendations": ["Rec 1", "Rec 2"],
    "next_steps": ["Step 1"]
}
""")
        mock_agent.close = AsyncMock()

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", return_value=mock_agent):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
                from scripts.agentica_patterns.native_repl.models import ResearchFindings

                coord = ResearchCoordinator(topic="Test Topic", db=mock_db)
                findings = [
                    ResearchFindings(
                        section_name="Section 1",
                        key_findings=["Finding 1"],
                        sources=["https://example.com"],
                    ),
                    ResearchFindings(
                        section_name="Section 2",
                        key_findings=["Finding 2"],
                        sources=["https://example2.com"],
                    ),
                ]

                document = await coord.synthesize(findings)

                assert document.topic == "Test Topic"
                assert document.executive_summary == "Test summary of all findings."
                assert len(document.sections) == 2
                assert len(document.overall_recommendations) == 2
                assert document.total_sources == 2

    @pytest.mark.asyncio
    async def test_full_research_workflow_with_scope(self, mock_db):
        """Test the complete research workflow using mutable scope."""
        call_count = 0

        async def mock_spawn(**kwargs):
            nonlocal call_count
            call_count += 1

            # Write findings to scope if this is a specialist (has results in scope)
            scope = kwargs.get("scope", {})
            if "results" in scope:
                scope["results"]["findings"] = {
                    "key_findings": ["Finding 1"],
                    "sources": ["https://source.com"],
                    "recommendations": ["Rec 1"],
                }

            mock_agent = AsyncMock()

            if call_count == 1:
                # Decompose response
                mock_agent.call = AsyncMock(return_value="""
[
    {"name": "part1", "title": "Part 1", "research_focus": "Focus 1", "tool_hint": "web"}
]
""")
            elif call_count == 3:
                # Synthesis response (call 2 is research)
                mock_agent.call = AsyncMock(return_value="""
{
    "executive_summary": "Final summary.",
    "overall_recommendations": ["Final rec"],
    "next_steps": ["Next step"]
}
""")
            else:
                mock_agent.call = AsyncMock(return_value="Done")

            mock_agent.close = AsyncMock()
            return mock_agent

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", side_effect=mock_spawn):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", side_effect=mock_spawn):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

                coord = ResearchCoordinator(
                    topic="Full Test Topic",
                    depth="standard",
                    max_sections=3,
                    db=mock_db,
                )

                document = await coord.research()

                assert document.topic == "Full Test Topic"
                assert len(document.sections) >= 1
                assert document.research_depth == "standard"
                # Findings should come from scope
                assert document.sections[0].key_findings == ["Finding 1"]

    @pytest.mark.asyncio
    async def test_coordinator_tracks_agents(self, mock_db):
        """Coordinator should register agents with CoordinationDB."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value='[{"name": "test", "title": "Test", "research_focus": "Focus", "tool_hint": "all"}]')
        mock_agent.close = AsyncMock()

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn") as mock_tracked:
                mock_tracked.return_value = mock_agent

                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

                coord = ResearchCoordinator(topic="Test", db=mock_db)
                await coord.decompose()

                # Verify tracked_spawn was called with db
                assert mock_tracked.called
                call_kwargs = mock_tracked.call_args[1]
                assert call_kwargs["db"] == mock_db
                assert call_kwargs["pattern"] == "native_repl_coordinator"


# =============================================================================
# JSON Parsing Tests
# =============================================================================


class TestJsonParsing:
    """Test JSON parsing helper functions."""

    def test_parse_json_list_direct(self):
        """Test parsing direct JSON array."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        result = parse_json_list('[{"name": "test"}]')
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_parse_json_list_markdown_block(self):
        """Test parsing JSON from markdown code block."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        response = """Here's the breakdown:

```json
[
    {"name": "section1", "title": "Section 1"}
]
```

That's the sections.
"""
        result = parse_json_list(response)
        assert len(result) == 1
        assert result[0]["name"] == "section1"

    def test_parse_json_list_embedded_array(self):
        """Test parsing embedded JSON array."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        response = """The sections are: [{"name": "embedded"}] and that's it."""
        result = parse_json_list(response)
        assert len(result) == 1
        assert result[0]["name"] == "embedded"

    def test_parse_json_dict_direct(self):
        """Test parsing findings as dict."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_dict

        result = parse_json_dict('{"key_findings": ["f1", "f2"]}')
        assert "key_findings" in result
        assert len(result["key_findings"]) == 2

    def test_parse_json_dict_invalid(self):
        """Test parsing returns empty dict for invalid input."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_dict

        result = parse_json_dict("Not valid JSON at all")
        assert result == {}


# =============================================================================
# Scope Persistence Pattern Tests
# =============================================================================


class TestScopePersistence:
    """Test the mutable scope pattern for REPL variable persistence.

    These tests verify the fix for the bug where local variables were
    lost between REPL turns. The fix uses mutable scope dicts that
    persist by reference.
    """

    def test_scope_dict_persists_by_reference(self):
        """Verify basic Python reference semantics for scope persistence."""
        # This is the pattern that works:
        resources = {"findings": None}

        # Simulate agent writing to scope
        def simulate_agent_write(scope):
            scope["findings"] = {"key_findings": ["test"]}

        simulate_agent_write(resources)

        # Original dict is updated
        assert resources["findings"] == {"key_findings": ["test"]}

    def test_local_variable_would_be_lost(self):
        """Demonstrate why local variables fail (for documentation)."""
        # This is the pattern that FAILS in real REPL:
        # findings = None
        # await agent.call(str, "findings = {...}")  # local var in REPL
        # # findings is None here - lost between turns

        # We can't actually test the REPL behavior, but this documents
        # why the mutable scope pattern is necessary.
        pass

    @pytest.mark.asyncio
    async def test_specialist_scope_has_results_container(self):
        """Specialist scope should include mutable results container."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

        coord = ResearchCoordinator(topic="Test")
        scope = coord._create_specialist_scope()

        # Must have results container
        assert "results" in scope
        assert isinstance(scope["results"], dict)

        # Simulate agent writing
        scope["results"]["findings"] = {"key_findings": ["persisted"]}

        # Verify persistence
        assert scope["results"]["findings"]["key_findings"] == ["persisted"]

    @pytest.mark.asyncio
    async def test_prompt_instructs_scope_usage(self, tmp_path):
        """Prompts should instruct agents to use scope for persistence."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="Done")
        mock_agent.close = AsyncMock()

        captured_prompt = None

        async def capture_call(return_type, prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "Done"

        mock_agent.call = capture_call

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", return_value=mock_agent):
                from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
                from scripts.agentica_patterns.native_repl.models import ResearchSection

                coord = ResearchCoordinator(topic="Test")
                section = ResearchSection(
                    name="test",
                    title="Test",
                    research_focus="Test focus",
                    tool_hint="all",
                )

                await coord._research_section(section)

                # Prompt should mention scope persistence
                assert captured_prompt is not None
                assert "results['findings']" in captured_prompt
                assert "local variables" in captured_prompt.lower() or "lost" in captured_prompt.lower()
