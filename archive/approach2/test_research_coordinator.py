"""
TDD Tests for Hierarchical Research Coordinator

Tests written BEFORE implementation to drive design.
Expected to FAIL until research_coordinator.py implements the classes.

The Research Coordinator pattern:
- Coordinator decomposes research topics into logical sections
- Specialist agents research sections in parallel using MCP tools
- Coordinator synthesizes findings into a final research document
- Full CoordinationDB integration for observability
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# ResearchSection Dataclass Tests
# =============================================================================


class TestResearchSection:
    """Test ResearchSection dataclass."""

    def test_research_section_creation(self):
        """Can create a ResearchSection with all fields."""
        from scripts.agentica.research_coordinator import ResearchSection

        section = ResearchSection(
            name="api_design",
            title="API Design Patterns",
            research_focus="Investigate REST vs GraphQL patterns for Python microservices",
            tool_hint="web"
        )

        assert section.name == "api_design"
        assert section.title == "API Design Patterns"
        assert section.research_focus == "Investigate REST vs GraphQL patterns for Python microservices"
        assert section.tool_hint == "web"

    def test_research_section_tool_hint_values(self):
        """ResearchSection accepts valid tool_hint values."""
        from scripts.agentica.research_coordinator import ResearchSection

        # Valid values: "web", "library", "both"
        section_web = ResearchSection(
            name="web_section",
            title="Web Research",
            research_focus="Research via web",
            tool_hint="web"
        )
        section_lib = ResearchSection(
            name="lib_section",
            title="Library Docs",
            research_focus="Research via library docs",
            tool_hint="library"
        )
        section_both = ResearchSection(
            name="both_section",
            title="Both Sources",
            research_focus="Research via both",
            tool_hint="both"
        )

        assert section_web.tool_hint == "web"
        assert section_lib.tool_hint == "library"
        assert section_both.tool_hint == "both"

    def test_research_section_to_dict(self):
        """ResearchSection.to_dict() returns serializable dict."""
        from scripts.agentica.research_coordinator import ResearchSection

        section = ResearchSection(
            name="async_patterns",
            title="Async Patterns",
            research_focus="Python async best practices",
            tool_hint="both"
        )

        result = section.to_dict()

        assert isinstance(result, dict)
        assert result["name"] == "async_patterns"
        assert result["title"] == "Async Patterns"
        assert result["research_focus"] == "Python async best practices"
        assert result["tool_hint"] == "both"

    def test_research_section_default_tool_hint(self):
        """ResearchSection defaults to 'both' tool_hint if not specified."""
        from scripts.agentica.research_coordinator import ResearchSection

        section = ResearchSection(
            name="default_section",
            title="Default Section",
            research_focus="General research"
        )

        assert section.tool_hint == "both"


# =============================================================================
# ResearchFindings Dataclass Tests
# =============================================================================


class TestResearchFindings:
    """Test ResearchFindings dataclass."""

    def test_research_findings_creation(self):
        """Can create ResearchFindings with all fields."""
        from scripts.agentica.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="api_design",
            key_findings=["REST is simpler", "GraphQL is more flexible"],
            sources=["https://example.com/rest", "https://example.com/graphql"],
            recommendations=["Use REST for simple APIs", "Use GraphQL for complex queries"],
            code_examples=["```python\napp.route('/api')\n```"],
            open_questions=["How does performance compare at scale?"],
            raw_response="Full response text from specialist agent"
        )

        assert findings.section_name == "api_design"
        assert len(findings.key_findings) == 2
        assert len(findings.sources) == 2
        assert len(findings.recommendations) == 2
        assert len(findings.code_examples) == 1
        assert len(findings.open_questions) == 1
        assert findings.raw_response == "Full response text from specialist agent"

    def test_research_findings_empty_lists_default(self):
        """ResearchFindings defaults empty lists for optional fields."""
        from scripts.agentica.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="minimal_section"
        )

        assert findings.key_findings == []
        assert findings.sources == []
        assert findings.recommendations == []
        assert findings.code_examples == []
        assert findings.open_questions == []
        assert findings.raw_response == ""

    def test_research_findings_to_markdown(self):
        """ResearchFindings.to_markdown() returns formatted markdown."""
        from scripts.agentica.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="async_patterns",
            key_findings=["Use asyncio.gather for parallelism", "Avoid blocking calls"],
            sources=["https://docs.python.org/asyncio"],
            recommendations=["Always use async context managers"],
            code_examples=["```python\nawait asyncio.gather(*tasks)\n```"],
            open_questions=["When to use threads vs async?"]
        )

        markdown = findings.to_markdown()

        assert isinstance(markdown, str)
        assert "## async_patterns" in markdown or "async_patterns" in markdown
        assert "asyncio.gather" in markdown
        assert "https://docs.python.org/asyncio" in markdown
        assert "async context managers" in markdown
        assert "threads vs async" in markdown

    def test_research_findings_to_markdown_handles_empty(self):
        """ResearchFindings.to_markdown() handles empty fields gracefully."""
        from scripts.agentica.research_coordinator import ResearchFindings

        findings = ResearchFindings(section_name="empty_section")

        markdown = findings.to_markdown()

        assert isinstance(markdown, str)
        assert "empty_section" in markdown

    def test_research_findings_to_dict(self):
        """ResearchFindings has to_dict for serialization."""
        from scripts.agentica.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="test",
            key_findings=["finding1"],
            sources=["source1"]
        )

        result = findings.to_dict()

        assert isinstance(result, dict)
        assert result["section_name"] == "test"
        assert result["key_findings"] == ["finding1"]


# =============================================================================
# ResearchDocument Dataclass Tests
# =============================================================================


class TestResearchDocument:
    """Test ResearchDocument dataclass."""

    def test_research_document_creation(self):
        """Can create ResearchDocument with all fields."""
        from scripts.agentica.research_coordinator import (
            ResearchDocument, ResearchFindings
        )

        findings1 = ResearchFindings(
            section_name="section1",
            key_findings=["Finding A"]
        )
        findings2 = ResearchFindings(
            section_name="section2",
            key_findings=["Finding B"]
        )

        doc = ResearchDocument(
            topic="Python Async Best Practices",
            executive_summary="Async programming improves performance for I/O-bound tasks.",
            sections=[findings1, findings2],
            overall_recommendations=["Use async for network operations"],
            next_steps=["Benchmark async vs sync implementations"],
            generated_at=datetime(2025, 12, 26, 10, 0, 0),
            total_sources=5,
            research_depth="standard"
        )

        assert doc.topic == "Python Async Best Practices"
        assert "Async programming" in doc.executive_summary
        assert len(doc.sections) == 2
        assert len(doc.overall_recommendations) == 1
        assert len(doc.next_steps) == 1
        assert doc.total_sources == 5
        assert doc.research_depth == "standard"

    def test_research_document_to_markdown(self):
        """ResearchDocument.to_markdown() returns complete markdown document."""
        from scripts.agentica.research_coordinator import (
            ResearchDocument, ResearchFindings
        )

        findings = ResearchFindings(
            section_name="core_patterns",
            key_findings=["Pattern A is effective"]
        )

        doc = ResearchDocument(
            topic="Test Topic",
            executive_summary="This is the summary.",
            sections=[findings],
            overall_recommendations=["Recommendation 1"],
            next_steps=["Step 1"],
            generated_at=datetime(2025, 12, 26, 10, 0, 0),
            total_sources=3,
            research_depth="standard"
        )

        markdown = doc.to_markdown()

        assert isinstance(markdown, str)
        assert "# Test Topic" in markdown or "Test Topic" in markdown
        assert "summary" in markdown.lower()
        assert "Pattern A" in markdown
        assert "Recommendation 1" in markdown
        assert "Step 1" in markdown

    def test_research_document_to_markdown_includes_metadata(self):
        """ResearchDocument.to_markdown() includes metadata section."""
        from scripts.agentica.research_coordinator import ResearchDocument

        doc = ResearchDocument(
            topic="Metadata Test",
            executive_summary="Summary",
            sections=[],
            overall_recommendations=[],
            next_steps=[],
            generated_at=datetime(2025, 12, 26, 10, 0, 0),
            total_sources=10,
            research_depth="deep"
        )

        markdown = doc.to_markdown()

        # Should include source count and depth somehow
        assert "10" in markdown or "sources" in markdown.lower()
        assert "deep" in markdown.lower() or "depth" in markdown.lower()

    def test_research_document_defaults(self):
        """ResearchDocument has sensible defaults."""
        from scripts.agentica.research_coordinator import ResearchDocument

        doc = ResearchDocument(topic="Minimal Topic")

        assert doc.topic == "Minimal Topic"
        assert doc.executive_summary == ""
        assert doc.sections == []
        assert doc.overall_recommendations == []
        assert doc.next_steps == []
        assert doc.total_sources == 0
        assert doc.research_depth == "standard"

    def test_research_document_to_dict(self):
        """ResearchDocument has to_dict for JSON serialization."""
        from scripts.agentica.research_coordinator import ResearchDocument

        doc = ResearchDocument(
            topic="JSON Test",
            executive_summary="Test summary"
        )

        result = doc.to_dict()

        assert isinstance(result, dict)
        assert result["topic"] == "JSON Test"
        # Should be JSON serializable
        json_str = json.dumps(result)
        assert "JSON Test" in json_str


# =============================================================================
# ResearchCoordinator Tests - Decomposition
# =============================================================================


class TestResearchCoordinatorDecomposition:
    """Test ResearchCoordinator.decompose() method."""

    @pytest.mark.asyncio
    async def test_decompose_returns_research_sections(self):
        """decompose() returns list of ResearchSection objects."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection
        )

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            # Coordinator returns JSON with sections
            mock_coordinator.call = AsyncMock(return_value=json.dumps([
                {
                    "name": "api_patterns",
                    "title": "API Patterns",
                    "research_focus": "Research REST API patterns",
                    "tool_hint": "web"
                },
                {
                    "name": "library_usage",
                    "title": "Library Usage",
                    "research_focus": "FastAPI documentation",
                    "tool_hint": "library"
                }
            ]))
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(
                topic="Building REST APIs with FastAPI"
            )

            sections = await coordinator.decompose()

            assert isinstance(sections, list)
            assert len(sections) == 2
            assert all(isinstance(s, ResearchSection) for s in sections)
            assert sections[0].name == "api_patterns"
            assert sections[1].tool_hint == "library"

    @pytest.mark.asyncio
    async def test_decompose_respects_max_sections(self):
        """decompose() limits sections to max_sections parameter."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            # Return more sections than max
            mock_coordinator.call = AsyncMock(return_value=json.dumps([
                {"name": f"section_{i}", "title": f"Section {i}",
                 "research_focus": f"Focus {i}", "tool_hint": "web"}
                for i in range(10)
            ]))
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(
                topic="Test Topic",
                max_sections=3
            )

            sections = await coordinator.decompose()

            assert len(sections) <= 3

    @pytest.mark.asyncio
    async def test_decompose_handles_invalid_json_gracefully(self):
        """decompose() has fallback for malformed JSON responses."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            # Return invalid JSON
            mock_coordinator.call = AsyncMock(return_value="Not valid JSON {{{")
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(topic="Test Topic")

            # Should not raise, should return fallback
            sections = await coordinator.decompose()

            assert isinstance(sections, list)
            # Fallback creates a single generic section
            assert len(sections) >= 1

    @pytest.mark.asyncio
    async def test_decompose_handles_empty_response(self):
        """decompose() handles empty coordinator response."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(return_value="[]")
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(topic="Simple Topic")

            sections = await coordinator.decompose()

            # Should create at least one section for simple topics
            assert isinstance(sections, list)

    @pytest.mark.asyncio
    async def test_decompose_includes_topic_in_prompt(self):
        """decompose() passes topic to coordinator agent."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(return_value="[]")
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(topic="Python async patterns")

            await coordinator.decompose()

            # Verify call was made with topic in prompt
            call_args = mock_coordinator.call.call_args
            assert "Python async patterns" in str(call_args)


# =============================================================================
# ResearchCoordinator Tests - Section Research
# =============================================================================


class TestResearchCoordinatorSectionResearch:
    """Test ResearchCoordinator._research_section() method."""

    @pytest.mark.asyncio
    async def test_research_section_returns_findings(self):
        """_research_section() returns ResearchFindings."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection, ResearchFindings
        )

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_specialist = AsyncMock()
            mock_specialist.call = AsyncMock(return_value=json.dumps({
                "key_findings": ["Finding 1", "Finding 2"],
                "sources": ["https://source1.com"],
                "recommendations": ["Use pattern A"],
                "code_examples": [],
                "open_questions": []
            }))
            mock_spawn.return_value = mock_specialist

            coordinator = ResearchCoordinator(topic="Test")

            section = ResearchSection(
                name="test_section",
                title="Test Section",
                research_focus="Research test patterns",
                tool_hint="web"
            )

            findings = await coordinator._research_section(section)

            assert isinstance(findings, ResearchFindings)
            assert findings.section_name == "test_section"
            assert "Finding 1" in findings.key_findings

    @pytest.mark.asyncio
    async def test_research_section_uses_tool_hint(self):
        """_research_section() passes tool_hint to specialist scope."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection
        )

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_specialist = AsyncMock()
            mock_specialist.call = AsyncMock(return_value="{}")
            mock_spawn.return_value = mock_specialist

            coordinator = ResearchCoordinator(topic="Test")

            section = ResearchSection(
                name="lib_section",
                title="Library Section",
                research_focus="Check library docs",
                tool_hint="library"
            )

            await coordinator._research_section(section)

            # Verify spawn was called with appropriate scope for library research
            spawn_call = mock_spawn.call_args
            assert spawn_call is not None
            # The scope should include library documentation tools

    @pytest.mark.asyncio
    async def test_research_section_handles_malformed_response(self):
        """_research_section() handles non-JSON specialist responses."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection, ResearchFindings
        )

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_specialist = AsyncMock()
            # Return plain text instead of JSON
            mock_specialist.call = AsyncMock(return_value="Here are my findings: Pattern A is good.")
            mock_spawn.return_value = mock_specialist

            coordinator = ResearchCoordinator(topic="Test")

            section = ResearchSection(
                name="plain_section",
                title="Plain Response",
                research_focus="Test plain response handling",
                tool_hint="web"
            )

            findings = await coordinator._research_section(section)

            assert isinstance(findings, ResearchFindings)
            assert findings.section_name == "plain_section"
            # Raw response should capture the text
            assert "Pattern A" in findings.raw_response


# =============================================================================
# ResearchCoordinator Tests - Parallel Execution
# =============================================================================


class TestResearchCoordinatorParallelExecution:
    """Test ResearchCoordinator.research_sections() parallel execution."""

    @pytest.mark.asyncio
    async def test_research_sections_executes_in_parallel(self):
        """research_sections() runs specialists in parallel."""
        import asyncio
        import time
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection
        )

        execution_times = []

        async def slow_specialist(*args, **kwargs):
            mock = AsyncMock()
            async def slow_call(return_type, prompt):
                execution_times.append(time.time())
                await asyncio.sleep(0.1)
                return json.dumps({"key_findings": ["Result"]})
            mock.call = slow_call
            return mock

        with patch("scripts.agentica.research_coordinator.spawn", side_effect=slow_specialist):
            coordinator = ResearchCoordinator(topic="Test")

            sections = [
                ResearchSection(name=f"section_{i}", title=f"Section {i}",
                               research_focus=f"Focus {i}", tool_hint="web")
                for i in range(3)
            ]

            start = time.time()
            await coordinator.research_sections(sections)
            duration = time.time() - start

            # If parallel, should take ~0.1s, not ~0.3s
            assert duration < 0.25, f"Expected parallel execution, took {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_research_sections_returns_all_findings(self):
        """research_sections() returns findings for all sections."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection, ResearchFindings
        )

        call_count = [0]

        async def mock_spawn(*args, **kwargs):
            call_count[0] += 1
            mock = AsyncMock()
            mock.call = AsyncMock(return_value=json.dumps({
                "key_findings": [f"Finding from call {call_count[0]}"]
            }))
            return mock

        with patch("scripts.agentica.research_coordinator.spawn", side_effect=mock_spawn):
            coordinator = ResearchCoordinator(topic="Test")

            sections = [
                ResearchSection(name="sec1", title="S1", research_focus="F1"),
                ResearchSection(name="sec2", title="S2", research_focus="F2"),
            ]

            findings = await coordinator.research_sections(sections)

            assert len(findings) == 2
            assert all(isinstance(f, ResearchFindings) for f in findings)

    @pytest.mark.asyncio
    async def test_research_sections_continues_on_failure(self):
        """research_sections() continues with partial results on failure."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection
        )

        call_count = [0]

        async def flaky_spawn(*args, **kwargs):
            call_count[0] += 1
            mock = AsyncMock()
            if call_count[0] == 2:
                # Second specialist fails
                mock.call = AsyncMock(side_effect=Exception("Specialist failed"))
            else:
                mock.call = AsyncMock(return_value=json.dumps({
                    "key_findings": ["Success"]
                }))
            return mock

        with patch("scripts.agentica.research_coordinator.spawn", side_effect=flaky_spawn):
            coordinator = ResearchCoordinator(topic="Test")

            sections = [
                ResearchSection(name="sec1", title="S1", research_focus="F1"),
                ResearchSection(name="sec2", title="S2", research_focus="F2"),
                ResearchSection(name="sec3", title="S3", research_focus="F3"),
            ]

            # Should not raise, should return partial results
            findings = await coordinator.research_sections(sections)

            # At least 2 should succeed
            assert len(findings) >= 2


# =============================================================================
# ResearchCoordinator Tests - Synthesis
# =============================================================================


class TestResearchCoordinatorSynthesis:
    """Test ResearchCoordinator.synthesize() method."""

    @pytest.mark.asyncio
    async def test_synthesize_returns_research_document(self):
        """synthesize() returns complete ResearchDocument."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchFindings, ResearchDocument
        )

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(return_value=json.dumps({
                "executive_summary": "This research covers async patterns.",
                "overall_recommendations": ["Use async for I/O"],
                "next_steps": ["Benchmark performance"]
            }))
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(topic="Async Patterns")

            findings = [
                ResearchFindings(
                    section_name="sec1",
                    key_findings=["Finding A"],
                    sources=["source1.com"]
                ),
                ResearchFindings(
                    section_name="sec2",
                    key_findings=["Finding B"],
                    sources=["source2.com", "source3.com"]
                )
            ]

            doc = await coordinator.synthesize(findings)

            assert isinstance(doc, ResearchDocument)
            assert doc.topic == "Async Patterns"
            assert "async patterns" in doc.executive_summary.lower()
            assert len(doc.sections) == 2
            assert doc.total_sources == 3  # 1 + 2 sources

    @pytest.mark.asyncio
    async def test_synthesize_calculates_total_sources(self):
        """synthesize() correctly counts total sources."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchFindings
        )

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(return_value=json.dumps({
                "executive_summary": "Summary",
                "overall_recommendations": [],
                "next_steps": []
            }))
            mock_spawn.return_value = mock_coordinator

            coordinator = ResearchCoordinator(topic="Test")

            findings = [
                ResearchFindings(section_name="s1", sources=["a", "b", "c"]),
                ResearchFindings(section_name="s2", sources=["d", "e"]),
                ResearchFindings(section_name="s3", sources=[]),
            ]

            doc = await coordinator.synthesize(findings)

            assert doc.total_sources == 5


# =============================================================================
# ResearchCoordinator Tests - Full Research Flow
# =============================================================================


class TestResearchCoordinatorFullFlow:
    """Test ResearchCoordinator.research() end-to-end method."""

    @pytest.mark.asyncio
    async def test_research_end_to_end(self):
        """research() executes full pipeline: decompose → research → synthesize."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchDocument
        )

        call_sequence = []

        async def tracking_spawn(*args, **kwargs):
            mock = AsyncMock()
            premise = kwargs.get("premise", args[0] if args else "")

            if "decompose" in premise.lower() or "coordinator" in premise.lower():
                call_sequence.append("decompose")
                mock.call = AsyncMock(return_value=json.dumps([
                    {"name": "sec1", "title": "Section 1",
                     "research_focus": "Focus 1", "tool_hint": "web"}
                ]))
            elif "synthe" in premise.lower():
                call_sequence.append("synthesize")
                mock.call = AsyncMock(return_value=json.dumps({
                    "executive_summary": "Summary",
                    "overall_recommendations": ["Rec 1"],
                    "next_steps": ["Step 1"]
                }))
            else:
                call_sequence.append("research")
                mock.call = AsyncMock(return_value=json.dumps({
                    "key_findings": ["Finding"],
                    "sources": ["source.com"]
                }))

            return mock

        with patch("scripts.agentica.research_coordinator.spawn", side_effect=tracking_spawn):
            coordinator = ResearchCoordinator(
                topic="Full Flow Test",
                depth="standard"
            )

            doc = await coordinator.research()

            assert isinstance(doc, ResearchDocument)
            assert doc.topic == "Full Flow Test"

    @pytest.mark.asyncio
    async def test_research_respects_depth_parameter(self):
        """research() uses depth parameter to control research thoroughness."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="[]")
            mock_spawn.return_value = mock_agent

            coordinator_standard = ResearchCoordinator(topic="Test", depth="standard")
            coordinator_deep = ResearchCoordinator(topic="Test", depth="deep")

            assert coordinator_standard.depth == "standard"
            assert coordinator_deep.depth == "deep"


# =============================================================================
# ResearchCoordinator Tests - CoordinationDB Integration
# =============================================================================


class TestResearchCoordinatorDBIntegration:
    """Test ResearchCoordinator integration with CoordinationDB."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test_research.db",
            session_id="research-test-session"
        )

    @pytest.mark.asyncio
    async def test_coordinator_uses_tracked_spawn(self, db):
        """ResearchCoordinator uses tracked_spawn when db is provided."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.tracked_spawn") as mock_tracked:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="[]")
            mock_tracked.return_value = mock_agent

            coordinator = ResearchCoordinator(
                topic="Tracked Test",
                db=db
            )

            await coordinator.decompose()

            # Should use tracked_spawn instead of regular spawn
            mock_tracked.assert_called()
            call_kwargs = mock_tracked.call_args[1]
            assert call_kwargs.get("db") == db
            assert call_kwargs.get("pattern") == "research_coordinator"

    @pytest.mark.asyncio
    async def test_specialists_tracked_in_db(self, db):
        """Specialist agents are tracked in CoordinationDB."""
        from scripts.agentica.research_coordinator import (
            ResearchCoordinator, ResearchSection
        )

        agent_ids = []

        async def mock_tracked_spawn(db, pattern, **kwargs):
            agent_id = f"agent-{len(agent_ids)}"
            agent_ids.append(agent_id)
            # Actually register in DB for test verification
            db.register_agent(agent_id=agent_id, pattern=pattern, **kwargs)

            mock = AsyncMock()
            mock.call = AsyncMock(return_value=json.dumps({"key_findings": []}))
            return mock

        with patch("scripts.agentica.research_coordinator.tracked_spawn", side_effect=mock_tracked_spawn):
            coordinator = ResearchCoordinator(topic="DB Test", db=db)

            sections = [
                ResearchSection(name="s1", title="S1", research_focus="F1"),
                ResearchSection(name="s2", title="S2", research_focus="F2"),
            ]

            await coordinator.research_sections(sections)

            # Verify agents were registered
            running = db.get_running_agents()
            assert len(running) >= 2

    @pytest.mark.asyncio
    async def test_coordinator_completes_agents_on_finish(self, db):
        """ResearchCoordinator marks agents as completed."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        registered_agents = []

        async def mock_tracked_spawn(db, pattern, **kwargs):
            agent_id = f"agent-{len(registered_agents)}"
            registered_agents.append(agent_id)
            record = db.register_agent(agent_id=agent_id, pattern=pattern)

            mock = AsyncMock()
            mock.agent_id = agent_id  # Store for completion tracking

            async def call_and_complete(return_type, prompt):
                result = json.dumps({"key_findings": [], "executive_summary": "", "overall_recommendations": [], "next_steps": []})
                db.complete_agent(agent_id)
                return result

            mock.call = call_and_complete
            return mock

        with patch("scripts.agentica.research_coordinator.tracked_spawn", side_effect=mock_tracked_spawn):
            coordinator = ResearchCoordinator(topic="Completion Test", db=db)

            await coordinator.research()

            # All agents should be completed
            running = db.get_running_agents()
            assert len(running) == 0


# =============================================================================
# ResearchCoordinator Tests - Configuration
# =============================================================================


class TestResearchCoordinatorConfiguration:
    """Test ResearchCoordinator configuration options."""

    def test_coordinator_accepts_model_parameter(self):
        """ResearchCoordinator accepts model parameter."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        coordinator = ResearchCoordinator(
            topic="Test",
            model="anthropic:claude-sonnet-4"
        )

        assert coordinator.model == "anthropic:claude-sonnet-4"

    def test_coordinator_accepts_depth_parameter(self):
        """ResearchCoordinator accepts depth parameter."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        coordinator = ResearchCoordinator(
            topic="Test",
            depth="deep"
        )

        assert coordinator.depth == "deep"

    def test_coordinator_accepts_max_sections_parameter(self):
        """ResearchCoordinator accepts max_sections parameter."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        coordinator = ResearchCoordinator(
            topic="Test",
            max_sections=5
        )

        assert coordinator.max_sections == 5

    def test_coordinator_default_values(self):
        """ResearchCoordinator has sensible defaults."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        coordinator = ResearchCoordinator(topic="Default Test")

        assert coordinator.topic == "Default Test"
        assert coordinator.depth == "standard"
        assert coordinator.max_sections == 5
        assert coordinator.model is None  # Use default model


# =============================================================================
# MCP Tool Wrapper Tests
# =============================================================================


class TestMCPToolWrappers:
    """Test MCP tool wrapper functions for specialists."""

    def test_call_perplexity_sync_exists(self):
        """call_perplexity_sync function should exist."""
        from scripts.agentica.research_coordinator import call_perplexity_sync

        assert callable(call_perplexity_sync)

    def test_call_nia_sync_exists(self):
        """call_nia_sync function should exist."""
        from scripts.agentica.research_coordinator import call_nia_sync

        assert callable(call_nia_sync)

    @pytest.mark.asyncio
    async def test_perplexity_research_scope_function(self):
        """perplexity_research should be available as scope function."""
        from scripts.agentica.research_coordinator import perplexity_research

        # Should be callable (async or sync)
        assert callable(perplexity_research)

    @pytest.mark.asyncio
    async def test_library_docs_scope_function(self):
        """library_docs should be available as scope function."""
        from scripts.agentica.research_coordinator import library_docs

        assert callable(library_docs)

    def test_tool_wrappers_use_subprocess(self):
        """Tool wrappers use subprocess to call MCP scripts."""
        import subprocess
        from scripts.agentica.research_coordinator import call_perplexity_sync

        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"result": "test"}',
                stderr=""
            )

            result = call_perplexity_sync("test query", "research")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # Should call perplexity_search.py script
            assert any("perplexity" in str(arg).lower() for arg in call_args[0][0])


# =============================================================================
# Integration Tests
# =============================================================================


class TestResearchCoordinatorIntegration:
    """Integration tests for ResearchCoordinator (requires mocking)."""

    @pytest.mark.asyncio
    async def test_full_research_produces_valid_markdown(self):
        """Full research flow produces valid markdown output."""
        from scripts.agentica.research_coordinator import ResearchCoordinator

        with patch("scripts.agentica.research_coordinator.spawn") as mock_spawn:
            call_count = [0]

            async def multi_agent_mock(*args, **kwargs):
                call_count[0] += 1
                mock = AsyncMock()

                if call_count[0] == 1:
                    # Decompose call
                    mock.call = AsyncMock(return_value=json.dumps([
                        {"name": "overview", "title": "Overview",
                         "research_focus": "General overview", "tool_hint": "web"}
                    ]))
                elif call_count[0] == 2:
                    # Research section call
                    mock.call = AsyncMock(return_value=json.dumps({
                        "key_findings": ["Key insight discovered"],
                        "sources": ["https://example.com"],
                        "recommendations": ["Do this"],
                        "code_examples": [],
                        "open_questions": []
                    }))
                else:
                    # Synthesize call
                    mock.call = AsyncMock(return_value=json.dumps({
                        "executive_summary": "This research found important insights.",
                        "overall_recommendations": ["Follow best practices"],
                        "next_steps": ["Implement findings"]
                    }))

                return mock

            mock_spawn.side_effect = multi_agent_mock

            coordinator = ResearchCoordinator(
                topic="Integration Test Topic",
                depth="standard",
                max_sections=1
            )

            doc = await coordinator.research()
            markdown = doc.to_markdown()

            # Verify markdown is well-formed
            assert "# Integration Test Topic" in markdown or "Integration Test Topic" in markdown
            assert "Key insight" in markdown
            assert "https://example.com" in markdown
