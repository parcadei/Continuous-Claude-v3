"""Tests for the Native REPL Research Coordinator.

Comprehensive unit tests for:
1. ResearchSection dataclass (to_dict)
2. ResearchFindings dataclass (to_markdown)
3. ResearchDocument dataclass (to_markdown)
4. ResearchCoordinator.decompose() (JSON parsing, fallback)
5. ResearchCoordinator.research_sections() (parallel execution)
6. ResearchCoordinator tracking with CoordinationDB
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.agentica_patterns.native_repl.models import (
    ResearchDocument,
    ResearchFindings,
    ResearchSection,
)


# =============================================================================
# ResearchSection Tests
# =============================================================================


class TestResearchSection:
    """Test ResearchSection dataclass."""

    def test_to_dict_basic(self):
        """Should serialize all fields to dict."""
        section = ResearchSection(
            name="async_patterns",
            title="Async Patterns in Python",
            research_focus="Explore async/await patterns and best practices",
            tool_hint="web",
        )
        result = section.to_dict()

        assert result == {
            "name": "async_patterns",
            "title": "Async Patterns in Python",
            "research_focus": "Explore async/await patterns and best practices",
            "tool_hint": "web",
        }

    def test_to_dict_default_tool_hint(self):
        """Should use 'all' as default tool_hint."""
        section = ResearchSection(
            name="general",
            title="General Research",
            research_focus="Research everything",
        )
        result = section.to_dict()

        assert result["tool_hint"] == "all"

    def test_to_dict_codebase_hint(self):
        """Should serialize codebase tool_hint."""
        section = ResearchSection(
            name="code_review",
            title="Code Review",
            research_focus="Review the codebase",
            tool_hint="codebase",
        )
        result = section.to_dict()

        assert result["tool_hint"] == "codebase"

    def test_to_dict_docs_hint(self):
        """Should serialize docs tool_hint."""
        section = ResearchSection(
            name="documentation",
            title="Documentation Research",
            research_focus="Research library documentation",
            tool_hint="docs",
        )
        result = section.to_dict()

        assert result["tool_hint"] == "docs"


# =============================================================================
# ResearchFindings Tests
# =============================================================================


class TestResearchFindings:
    """Test ResearchFindings dataclass."""

    def test_to_dict_all_fields(self):
        """Should serialize all fields to dict."""
        findings = ResearchFindings(
            section_name="Async Patterns",
            key_findings=["asyncio is powerful", "Use async context managers"],
            sources=["https://docs.python.org/3/library/asyncio.html"],
            recommendations=["Use async for I/O bound tasks"],
            code_examples=["async def main(): ..."],
            open_questions=["How to handle cancellation?"],
        )
        result = findings.to_dict()

        assert result["section_name"] == "Async Patterns"
        assert len(result["key_findings"]) == 2
        assert len(result["sources"]) == 1
        assert "raw_response" not in result  # Should not include raw_response

    def test_to_dict_empty_fields(self):
        """Should handle empty fields with defaults."""
        findings = ResearchFindings(section_name="Empty Section")
        result = findings.to_dict()

        assert result["section_name"] == "Empty Section"
        assert result["key_findings"] == []
        assert result["sources"] == []
        assert result["recommendations"] == []
        assert result["code_examples"] == []
        assert result["open_questions"] == []

    def test_to_markdown_full_findings(self):
        """Should render complete findings as markdown."""
        findings = ResearchFindings(
            section_name="Async Patterns",
            key_findings=["asyncio is powerful", "Use async context managers"],
            sources=["https://docs.python.org", "https://pep.python.org"],
            recommendations=["Use async for I/O bound tasks"],
            code_examples=["```python\nasync def main(): ...\n```"],
            open_questions=["How to handle cancellation?"],
        )
        result = findings.to_markdown()

        # Check header
        assert "## Async Patterns" in result

        # Check key findings section
        assert "### Key Findings" in result
        assert "- asyncio is powerful" in result
        assert "- Use async context managers" in result

        # Check sources section
        assert "### Sources" in result
        assert "- https://docs.python.org" in result
        assert "- https://pep.python.org" in result

        # Check recommendations section
        assert "### Recommendations" in result
        assert "- Use async for I/O bound tasks" in result

        # Check code examples section
        assert "### Code Examples" in result
        assert "async def main()" in result

        # Check open questions section
        assert "### Open Questions" in result
        assert "- How to handle cancellation?" in result

    def test_to_markdown_partial_findings(self):
        """Should only render non-empty sections."""
        findings = ResearchFindings(
            section_name="Partial Section",
            key_findings=["One finding"],
        )
        result = findings.to_markdown()

        # Check header and key findings
        assert "## Partial Section" in result
        assert "### Key Findings" in result
        assert "- One finding" in result

        # Should not include empty sections
        assert "### Sources" not in result
        assert "### Recommendations" not in result
        assert "### Code Examples" not in result
        assert "### Open Questions" not in result

    def test_to_markdown_empty_findings(self):
        """Should render minimal markdown for empty findings."""
        findings = ResearchFindings(section_name="Empty Section")
        result = findings.to_markdown()

        assert "## Empty Section" in result
        # Should only have header, no subsections
        assert "### Key Findings" not in result
        assert "### Sources" not in result


# =============================================================================
# ResearchDocument Tests
# =============================================================================


class TestResearchDocument:
    """Test ResearchDocument dataclass."""

    @pytest.fixture
    def sample_findings(self):
        """Create sample findings for testing."""
        return [
            ResearchFindings(
                section_name="Section A",
                key_findings=["Finding A1", "Finding A2"],
                sources=["https://source-a.com"],
            ),
            ResearchFindings(
                section_name="Section B",
                key_findings=["Finding B1"],
                recommendations=["Rec B1"],
            ),
        ]

    def test_to_dict_full_document(self, sample_findings):
        """Should serialize full document to dict."""
        doc = ResearchDocument(
            topic="Python Async Patterns",
            executive_summary="A comprehensive analysis of async patterns.",
            sections=sample_findings,
            overall_recommendations=["Use async/await", "Handle errors"],
            next_steps=["Profile performance", "Write tests"],
            total_sources=5,
            research_depth="deep",
        )
        result = doc.to_dict()

        assert result["topic"] == "Python Async Patterns"
        assert result["executive_summary"] == "A comprehensive analysis of async patterns."
        assert len(result["sections"]) == 2
        assert result["overall_recommendations"] == ["Use async/await", "Handle errors"]
        assert result["next_steps"] == ["Profile performance", "Write tests"]
        assert result["total_sources"] == 5
        assert result["research_depth"] == "deep"
        assert "generated_at" in result  # ISO format

    def test_to_dict_minimal_document(self):
        """Should serialize minimal document with defaults."""
        doc = ResearchDocument(topic="Minimal Topic")
        result = doc.to_dict()

        assert result["topic"] == "Minimal Topic"
        assert result["executive_summary"] == ""
        assert result["sections"] == []
        assert result["overall_recommendations"] == []
        assert result["next_steps"] == []
        assert result["total_sources"] == 0
        assert result["research_depth"] == "standard"

    def test_to_markdown_full_document(self, sample_findings):
        """Should render complete document as markdown."""
        fixed_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        doc = ResearchDocument(
            topic="Python Async Patterns",
            executive_summary="A comprehensive analysis of async patterns in Python.",
            sections=sample_findings,
            overall_recommendations=["Use async/await consistently"],
            next_steps=["Profile performance"],
            generated_at=fixed_time,
            total_sources=3,
            research_depth="deep",
        )
        result = doc.to_markdown()

        # Check title
        assert "# Python Async Patterns" in result

        # Check metadata
        assert "Generated: 2024-01-15 10:30 UTC" in result
        assert "Depth: deep" in result
        assert "Sources: 3" in result

        # Check executive summary
        assert "## Executive Summary" in result
        assert "A comprehensive analysis of async patterns in Python." in result

        # Check sections are included
        assert "## Section A" in result
        assert "## Section B" in result
        assert "Finding A1" in result
        assert "Finding B1" in result

        # Check overall recommendations
        assert "## Overall Recommendations" in result
        assert "- Use async/await consistently" in result

        # Check next steps
        assert "## Next Steps" in result
        assert "- Profile performance" in result

    def test_to_markdown_no_summary(self, sample_findings):
        """Should skip executive summary if empty."""
        doc = ResearchDocument(
            topic="No Summary Topic",
            sections=sample_findings,
        )
        result = doc.to_markdown()

        assert "# No Summary Topic" in result
        assert "## Executive Summary" not in result

    def test_to_markdown_no_recommendations(self):
        """Should skip recommendations if empty."""
        doc = ResearchDocument(topic="No Recommendations")
        result = doc.to_markdown()

        assert "## Overall Recommendations" not in result
        assert "## Next Steps" not in result


# =============================================================================
# ResearchCoordinator Tests
# =============================================================================


class TestResearchCoordinatorDecompose:
    """Test ResearchCoordinator.decompose() method."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = AsyncMock()
        agent.close = AsyncMock()
        return agent

    @pytest.fixture
    def coordinator(self):
        """Create a ResearchCoordinator."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
        return ResearchCoordinator(
            topic="Python async patterns",
            depth="standard",
            max_sections=3,
        )

    @pytest.mark.asyncio
    async def test_decompose_parses_json_response(self, coordinator, mock_agent):
        """Should parse JSON response into ResearchSections."""
        mock_agent.call.return_value = '''[
            {"name": "basics", "title": "Async Basics", "research_focus": "Learn basics", "tool_hint": "web"},
            {"name": "advanced", "title": "Advanced Patterns", "research_focus": "Deep dive", "tool_hint": "docs"}
        ]'''

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 2
        assert sections[0].name == "basics"
        assert sections[0].title == "Async Basics"
        assert sections[0].tool_hint == "web"
        assert sections[1].name == "advanced"
        assert sections[1].tool_hint == "docs"

    @pytest.mark.asyncio
    async def test_decompose_handles_markdown_json(self, coordinator, mock_agent):
        """Should extract JSON from markdown code blocks."""
        mock_agent.call.return_value = '''Here are the sections:
```json
[
    {"name": "basics", "title": "Basics", "research_focus": "Learn", "tool_hint": "all"}
]
```'''

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 1
        assert sections[0].name == "basics"

    @pytest.mark.asyncio
    async def test_decompose_respects_max_sections(self, coordinator, mock_agent):
        """Should limit sections to max_sections."""
        # Return 5 sections but max is 3
        mock_agent.call.return_value = '''[
            {"name": "s1", "title": "S1", "research_focus": "F1", "tool_hint": "web"},
            {"name": "s2", "title": "S2", "research_focus": "F2", "tool_hint": "web"},
            {"name": "s3", "title": "S3", "research_focus": "F3", "tool_hint": "web"},
            {"name": "s4", "title": "S4", "research_focus": "F4", "tool_hint": "web"},
            {"name": "s5", "title": "S5", "research_focus": "F5", "tool_hint": "web"}
        ]'''

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 3  # Limited by max_sections

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_invalid_json(self, coordinator, mock_agent):
        """Should return fallback section on invalid JSON."""
        mock_agent.call.return_value = "This is not valid JSON at all"

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 1
        assert sections[0].name == "general_research"
        assert sections[0].title == "General Research"
        assert "Python async patterns" in sections[0].research_focus

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_empty_response(self, coordinator, mock_agent):
        """Should return fallback section on empty JSON array."""
        mock_agent.call.return_value = "[]"

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 1
        assert sections[0].name == "general_research"

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_exception(self, coordinator, mock_agent):
        """Should return fallback section on exception."""
        mock_agent.call.side_effect = Exception("Network error")

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 1
        assert sections[0].name == "general_research"

    @pytest.mark.asyncio
    async def test_decompose_handles_missing_fields(self, coordinator, mock_agent):
        """Should use defaults for missing fields."""
        mock_agent.call.return_value = '''[
            {"name": "partial"}
        ]'''

        with patch.object(coordinator, "_spawn_agent", return_value=mock_agent):
            sections = await coordinator.decompose()

        assert len(sections) == 1
        assert sections[0].name == "partial"
        assert sections[0].title == "Unknown Section"  # Default
        assert sections[0].research_focus == ""  # Default
        assert sections[0].tool_hint == "all"  # Default


class TestResearchCoordinatorSections:
    """Test ResearchCoordinator.research_sections() method."""

    @pytest.fixture
    def mock_specialist(self):
        """Create a mock specialist agent."""
        agent = AsyncMock()
        agent.close = AsyncMock()
        return agent

    @pytest.fixture
    def coordinator(self):
        """Create a ResearchCoordinator."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
        return ResearchCoordinator(topic="Python async patterns")

    @pytest.fixture
    def sample_sections(self):
        """Create sample sections for testing."""
        return [
            ResearchSection(
                name="basics",
                title="Async Basics",
                research_focus="Learn async basics",
                tool_hint="web",
            ),
            ResearchSection(
                name="advanced",
                title="Advanced Patterns",
                research_focus="Advanced async patterns",
                tool_hint="docs",
            ),
        ]

    @pytest.mark.asyncio
    async def test_research_sections_parallel_execution(
        self, coordinator, mock_specialist, sample_sections
    ):
        """Should execute research for all sections in parallel."""
        call_order = []

        async def mock_call(return_type, prompt):
            section_name = "basics" if "basics" in prompt.lower() else "advanced"
            call_order.append(section_name)
            await asyncio.sleep(0.01)  # Small delay to test parallelism
            return '{"key_findings": ["finding"], "sources": ["source"]}'

        mock_specialist.call = mock_call

        with patch.object(coordinator, "_spawn_agent", return_value=mock_specialist):
            results = await coordinator.research_sections(sample_sections)

        assert len(results) == 2
        # Both sections should have been processed
        assert results[0].section_name == "Async Basics"
        assert results[1].section_name == "Advanced Patterns"

    @pytest.mark.asyncio
    async def test_research_sections_parses_findings(
        self, coordinator, mock_specialist, sample_sections
    ):
        """Should parse JSON findings from specialist response."""
        mock_specialist.call.return_value = '''{
            "key_findings": ["Finding 1", "Finding 2"],
            "sources": ["https://example.com"],
            "recommendations": ["Rec 1"],
            "code_examples": ["code"],
            "open_questions": ["Question?"]
        }'''

        with patch.object(coordinator, "_spawn_agent", return_value=mock_specialist):
            results = await coordinator.research_sections(sample_sections[:1])

        assert len(results) == 1
        findings = results[0]
        assert findings.key_findings == ["Finding 1", "Finding 2"]
        assert findings.sources == ["https://example.com"]
        assert findings.recommendations == ["Rec 1"]
        assert findings.code_examples == ["code"]
        assert findings.open_questions == ["Question?"]

    @pytest.mark.asyncio
    async def test_research_sections_handles_errors(
        self, coordinator, mock_specialist, sample_sections
    ):
        """Should return error finding on exception."""
        mock_specialist.call.side_effect = Exception("Research failed")

        with patch.object(coordinator, "_spawn_agent", return_value=mock_specialist):
            results = await coordinator.research_sections(sample_sections[:1])

        assert len(results) == 1
        assert results[0].section_name == "Async Basics"
        assert "Error" in results[0].raw_response

    @pytest.mark.asyncio
    async def test_research_sections_handles_invalid_json(
        self, coordinator, mock_specialist, sample_sections
    ):
        """Should handle invalid JSON response gracefully."""
        mock_specialist.call.return_value = "Not valid JSON"

        with patch.object(coordinator, "_spawn_agent", return_value=mock_specialist):
            results = await coordinator.research_sections(sample_sections[:1])

        assert len(results) == 1
        assert results[0].section_name == "Async Basics"
        assert results[0].key_findings == []  # Default empty list

    @pytest.mark.asyncio
    async def test_research_sections_mixed_success_failure(
        self, coordinator, sample_sections
    ):
        """Should handle mix of successful and failed sections."""
        call_count = 0

        # Create mock agents that will succeed or fail based on call order
        async def mixed_response(premise, scope=None, pattern=None):
            nonlocal call_count
            call_count += 1
            mock = AsyncMock()
            mock.close = AsyncMock()
            # First call succeeds, second fails
            if call_count == 1:
                mock.call.return_value = '{"key_findings": ["Success!"]}'
            else:
                mock.call.side_effect = Exception("Failed!")
            return mock

        with patch.object(coordinator, "_spawn_agent", side_effect=mixed_response):
            results = await coordinator.research_sections(sample_sections)

        assert len(results) == 2
        # One result should have findings, one should have error
        success_results = [r for r in results if r.key_findings]
        error_results = [r for r in results if "Error" in r.raw_response]

        assert len(success_results) == 1
        assert success_results[0].key_findings == ["Success!"]
        assert len(error_results) == 1


# =============================================================================
# ResearchCoordinator with CoordinationDB Tests
# =============================================================================


class TestResearchCoordinatorTracking:
    """Test ResearchCoordinator integration with CoordinationDB."""

    @pytest.fixture
    def tmp_db(self, tmp_path):
        """Create temporary CoordinationDB."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session",
        )

    @pytest.fixture
    def tracked_coordinator(self, tmp_db):
        """Create a ResearchCoordinator with tracking enabled."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
        return ResearchCoordinator(
            topic="Python async patterns",
            db=tmp_db,
        )

    @pytest.mark.asyncio
    async def test_coordinator_with_db_registers_agents(self, tracked_coordinator, tmp_db):
        """Should register agents in CoordinationDB when spawning."""
        mock_agent = AsyncMock()
        mock_agent.call.return_value = '[{"name": "test", "title": "Test", "research_focus": "Test", "tool_hint": "web"}]'
        mock_agent.close = AsyncMock()

        # Mock tracked_spawn to simulate agent registration
        with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn") as mock_tracked_spawn:
            mock_tracked_spawn.return_value = mock_agent

            # Call decompose which uses _spawn_agent
            await tracked_coordinator.decompose()

            # Verify tracked_spawn was called with db
            mock_tracked_spawn.assert_called_once()
            call_kwargs = mock_tracked_spawn.call_args[1]
            assert call_kwargs["db"] == tmp_db
            assert call_kwargs["pattern"] == "native_repl_coordinator"

    @pytest.mark.asyncio
    async def test_coordinator_without_db_uses_regular_spawn(self, tmp_path):
        """Should use regular spawn when no db is provided."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

        coordinator = ResearchCoordinator(topic="Test topic")  # No db

        mock_agent = AsyncMock()
        mock_agent.call.return_value = '[]'
        mock_agent.close = AsyncMock()

        with patch("scripts.agentica_patterns.native_repl.coordinator.spawn") as mock_spawn:
            mock_spawn.return_value = mock_agent

            await coordinator.decompose()

            mock_spawn.assert_called_once()

    @pytest.mark.asyncio
    async def test_specialist_agents_tracked_with_pattern(self, tracked_coordinator, tmp_db):
        """Should track specialist agents with correct pattern."""
        mock_agent = AsyncMock()
        mock_agent.call.return_value = '{"key_findings": ["test"]}'
        mock_agent.close = AsyncMock()

        section = ResearchSection(
            name="test",
            title="Test Section",
            research_focus="Test",
            tool_hint="web",
        )

        with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn") as mock_tracked_spawn:
            mock_tracked_spawn.return_value = mock_agent

            await tracked_coordinator._research_section(section)

            mock_tracked_spawn.assert_called_once()
            call_kwargs = mock_tracked_spawn.call_args[1]
            assert call_kwargs["pattern"] == "native_repl_specialist"

    def test_coordinator_stores_db_reference(self, tracked_coordinator, tmp_db):
        """Should store db reference for tracking."""
        assert tracked_coordinator.db == tmp_db

    def test_coordinator_without_db_has_none(self, tmp_path):
        """Should have None db when not provided."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator
        coordinator = ResearchCoordinator(topic="Test")
        assert coordinator.db is None


# =============================================================================
# JSON Utils Integration Tests
# =============================================================================


class TestJsonUtilsIntegration:
    """Test JSON parsing utilities used by coordinator."""

    def test_parse_json_list_direct(self):
        """Should parse direct JSON array."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        result = parse_json_list('[{"name": "test"}]')
        assert result == [{"name": "test"}]

    def test_parse_json_list_markdown(self):
        """Should extract JSON from markdown code block."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        result = parse_json_list('Here is the JSON:\n```json\n[{"name": "test"}]\n```')
        assert result == [{"name": "test"}]

    def test_parse_json_list_embedded(self):
        """Should find JSON array in text."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        result = parse_json_list('Some text [{"name": "test"}] more text')
        assert result == [{"name": "test"}]

    def test_parse_json_list_invalid(self):
        """Should return empty list on invalid JSON."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_list

        result = parse_json_list('Not valid JSON')
        assert result == []

    def test_parse_json_dict_direct(self):
        """Should parse direct JSON object."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_dict

        result = parse_json_dict('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_dict_markdown(self):
        """Should extract JSON from markdown code block."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_dict

        result = parse_json_dict('Result:\n```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_dict_invalid(self):
        """Should return empty dict on invalid JSON."""
        from scripts.agentica_patterns.native_repl.json_utils import parse_json_dict

        result = parse_json_dict('Not valid JSON')
        assert result == {}


# =============================================================================
# Full Workflow Integration Tests
# =============================================================================


class TestResearchCoordinatorWorkflow:
    """Test the full research workflow."""

    @pytest.fixture
    def mock_agents(self):
        """Create mock agents for full workflow."""
        decompose_agent = AsyncMock()
        decompose_agent.call.return_value = '''[
            {"name": "overview", "title": "Overview", "research_focus": "Overview", "tool_hint": "web"},
            {"name": "details", "title": "Details", "research_focus": "Details", "tool_hint": "docs"}
        ]'''
        decompose_agent.close = AsyncMock()

        specialist_agent = AsyncMock()
        specialist_agent.call.return_value = '''{
            "key_findings": ["Important finding"],
            "sources": ["https://example.com"],
            "recommendations": ["Do this"]
        }'''
        specialist_agent.close = AsyncMock()

        synthesize_agent = AsyncMock()
        synthesize_agent.call.return_value = '''{
            "executive_summary": "A great summary",
            "overall_recommendations": ["Recommendation 1"],
            "next_steps": ["Step 1"]
        }'''
        synthesize_agent.close = AsyncMock()

        return decompose_agent, specialist_agent, synthesize_agent

    @pytest.mark.asyncio
    async def test_full_research_workflow(self, mock_agents):
        """Should execute full research workflow."""
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

        decompose_agent, specialist_agent, synthesize_agent = mock_agents
        coordinator = ResearchCoordinator(topic="Python async")

        call_count = 0

        async def mock_spawn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call is decompose
            if call_count == 1:
                return decompose_agent
            # Next calls are specialists
            elif call_count <= 3:
                return specialist_agent
            # Last call is synthesize
            else:
                return synthesize_agent

        with patch.object(coordinator, "_spawn_agent", side_effect=mock_spawn):
            document = await coordinator.research()

        assert document.topic == "Python async"
        assert document.executive_summary == "A great summary"
        assert len(document.sections) == 2
        assert document.overall_recommendations == ["Recommendation 1"]
        assert document.next_steps == ["Step 1"]

    @pytest.mark.asyncio
    async def test_research_workflow_with_tracking(self, mock_agents, tmp_path):
        """Should track all agents in full workflow."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        from scripts.agentica_patterns.native_repl.coordinator import ResearchCoordinator

        decompose_agent, specialist_agent, synthesize_agent = mock_agents

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="workflow-test")
        coordinator = ResearchCoordinator(topic="Python async", db=db)

        spawned_patterns = []

        async def mock_tracked_spawn(*args, **kwargs):
            pattern = kwargs.get("pattern", "unknown")
            spawned_patterns.append(pattern)

            if pattern == "native_repl_coordinator":
                if len([p for p in spawned_patterns if p == "native_repl_coordinator"]) == 1:
                    return decompose_agent
                else:
                    return synthesize_agent
            else:
                return specialist_agent

        with patch("scripts.agentica_patterns.native_repl.coordinator.tracked_spawn", side_effect=mock_tracked_spawn):
            document = await coordinator.research()

        assert document.topic == "Python async"
        # Should have: 1 decompose + 2 specialists + 1 synthesize = 4 agents
        # Patterns: 2 coordinator + 2 specialists
        assert spawned_patterns.count("native_repl_coordinator") == 2
        assert spawned_patterns.count("native_repl_specialist") == 2
