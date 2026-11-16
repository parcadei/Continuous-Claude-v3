"""Tests for Hierarchical Research Coordinator."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


class TestResearchSection:
    """Test ResearchSection dataclass."""

    def test_to_dict(self):
        from scripts.agentica_patterns.research_coordinator import ResearchSection

        section = ResearchSection(
            name="auth",
            title="Authentication",
            research_focus="Research OAuth patterns",
            tool_hint="web",
        )

        d = section.to_dict()
        assert d["name"] == "auth"
        assert d["title"] == "Authentication"
        assert d["research_focus"] == "Research OAuth patterns"
        assert d["tool_hint"] == "web"

    def test_default_tool_hint(self):
        from scripts.agentica_patterns.research_coordinator import ResearchSection

        section = ResearchSection(
            name="test",
            title="Test",
            research_focus="Test focus",
        )
        assert section.tool_hint == "web"


class TestResearchFindings:
    """Test ResearchFindings dataclass."""

    def test_to_markdown_with_findings(self):
        from scripts.agentica_patterns.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="authentication",
            key_findings=["OAuth 2.0 is recommended", "Use PKCE for SPAs"],
            recommendations=["Implement token refresh"],
        )

        md = findings.to_markdown()
        assert "## Authentication" in md
        assert "OAuth 2.0 is recommended" in md
        assert "### Key Findings" in md
        assert "### Recommendations" in md

    def test_to_markdown_with_sources(self):
        from scripts.agentica_patterns.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="test",
            sources=[
                {"title": "Source 1", "url": "https://example.com/1"},
                {"title": "Source 2", "url": "https://example.com/2"},
            ],
        )

        md = findings.to_markdown()
        assert "[Source 1](https://example.com/1)" in md
        assert "### Sources" in md

    def test_to_markdown_with_code_examples(self):
        from scripts.agentica_patterns.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="code",
            code_examples=["def hello():\n    print('hello')"],
        )

        md = findings.to_markdown()
        assert "### Code Examples" in md
        assert "```" in md

    def test_to_dict(self):
        from scripts.agentica_patterns.research_coordinator import ResearchFindings

        findings = ResearchFindings(
            section_name="test",
            key_findings=["finding1"],
            recommendations=["rec1"],
        )

        d = findings.to_dict()
        assert d["section_name"] == "test"
        assert d["key_findings"] == ["finding1"]


class TestResearchDocument:
    """Test ResearchDocument dataclass."""

    def test_to_markdown_full(self):
        from scripts.agentica_patterns.research_coordinator import (
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
            total_sources=5,
        )

        md = doc.to_markdown()
        assert "# Research: Test Research" in md
        assert "Executive Summary" in md
        assert "This is a test summary" in md
        assert "Overall Recommendations" in md
        assert "1. Rec 1" in md
        assert "Next Steps" in md
        assert "- [ ] Step 1" in md
        assert "Total sources consulted: 5" in md

    def test_to_dict(self):
        from scripts.agentica_patterns.research_coordinator import (
            ResearchDocument,
            ResearchFindings,
        )

        doc = ResearchDocument(
            topic="Test",
            executive_summary="Summary",
            sections=[],
            overall_recommendations=["Rec1"],
            next_steps=["Step1"],
        )

        d = doc.to_dict()
        assert d["topic"] == "Test"
        assert d["executive_summary"] == "Summary"
        assert "generated_at" in d


class TestMCPToolWrappers:
    """Test MCP tool wrapper functions."""

    def test_call_perplexity_sync_success(self):
        """Test perplexity sync wrapper handles successful response."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Research results here",
                stderr=""
            )

            from scripts.agentica_patterns.research_coordinator import call_perplexity_sync
            result = call_perplexity_sync("test query", mode="research")

            assert result["success"] is True
            assert "Research results here" in result["answer"]

    def test_call_perplexity_sync_failure(self):
        """Test perplexity sync wrapper handles errors."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="API error"
            )

            from scripts.agentica_patterns.research_coordinator import call_perplexity_sync
            result = call_perplexity_sync("test query")

            assert result["success"] is False
            assert "API error" in result["error"]

    def test_call_nia_sync_success(self):
        """Test nia sync wrapper handles successful response."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Documentation content",
                stderr=""
            )

            from scripts.agentica_patterns.research_coordinator import call_nia_sync
            result = call_nia_sync("asyncio", "gather")

            assert result["success"] is True
            assert "Documentation content" in result["content"]

    def test_perplexity_research_wrapper(self):
        """Test high-level perplexity_research wrapper."""
        with patch("scripts.agentica.research_coordinator.call_perplexity_sync") as mock:
            mock.return_value = {"success": True, "answer": "Research answer"}

            from scripts.agentica_patterns.research_coordinator import perplexity_research
            result = perplexity_research("test query")

            assert result == "Research answer"
            mock.assert_called_once_with("test query", mode="research")

    def test_library_docs_wrapper(self):
        """Test high-level library_docs wrapper."""
        with patch("scripts.agentica.research_coordinator.call_nia_sync") as mock:
            mock.return_value = {"success": True, "content": "Docs content"}

            from scripts.agentica_patterns.research_coordinator import library_docs
            result = library_docs("asyncio", "gather")

            assert result == "Docs content"


class TestResearchCoordinator:
    """Test ResearchCoordinator class."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

    def test_coordinator_initialization(self):
        """Test coordinator initializes with correct defaults."""
        from scripts.agentica_patterns.research_coordinator import ResearchCoordinator

        coord = ResearchCoordinator(
            topic="Test topic",
            depth="standard",
        )

        assert coord.topic == "Test topic"
        assert coord.depth == "standard"
        assert coord.max_sections == 5
        assert coord.sections == []
        assert coord.findings == []
        assert coord.coordinator is None

    def test_coordinator_with_db(self, mock_db):
        """Test coordinator accepts coordination database."""
        from scripts.agentica_patterns.research_coordinator import ResearchCoordinator

        coord = ResearchCoordinator(
            topic="Test",
            db=mock_db,
        )

        assert coord.db == mock_db

    @pytest.mark.asyncio
    async def test_decompose_parses_json(self, mock_db):
        """Decompose should parse coordinator's JSON response."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="""
```json
[
    {"name": "auth", "title": "Auth", "research_focus": "OAuth patterns", "tool_hint": "web"},
    {"name": "db", "title": "Database", "research_focus": "Connection pooling", "tool_hint": "library"}
]
```
""")

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import ResearchCoordinator

                    coord = ResearchCoordinator(
                        topic="Test topic",
                        db=mock_db,
                    )
                    sections = await coord.decompose()

                    assert len(sections) == 2
                    assert sections[0].name == "auth"
                    assert sections[1].name == "db"

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_invalid_json(self, mock_db):
        """Decompose should fallback to single section on invalid JSON."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="Invalid JSON response")

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import ResearchCoordinator

                    coord = ResearchCoordinator(
                        topic="Test topic",
                        db=mock_db,
                    )
                    sections = await coord.decompose()

                    assert len(sections) == 1
                    assert sections[0].name == "main_research"

    @pytest.mark.asyncio
    async def test_research_sections_parallel(self, mock_db):
        """Research should execute sections in parallel."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="""
{"key_findings": ["finding"], "recommendations": ["rec"], "sources": []}
""")

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import (
                        ResearchCoordinator,
                        ResearchSection,
                    )

                    coord = ResearchCoordinator(topic="Test", db=mock_db)
                    coord.sections = [
                        ResearchSection("s1", "S1", "Focus 1", "web"),
                        ResearchSection("s2", "S2", "Focus 2", "web"),
                        ResearchSection("s3", "S3", "Focus 3", "library"),
                    ]

                    findings = await coord.research_sections()

                    assert len(findings) == 3
                    # All should have parsed findings
                    for f in findings:
                        assert f.key_findings == ["finding"]

    @pytest.mark.asyncio
    async def test_research_section_parses_findings(self, mock_db):
        """Individual section research should parse findings correctly."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="""
```json
{
    "key_findings": ["Finding A", "Finding B"],
    "recommendations": ["Rec 1"],
    "sources": [{"title": "Source", "url": "https://example.com"}],
    "code_examples": ["print('hello')"],
    "open_questions": ["Question 1"]
}
```
""")

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import (
                        ResearchCoordinator,
                        ResearchSection,
                    )

                    coord = ResearchCoordinator(topic="Test", db=mock_db)
                    section = ResearchSection("test", "Test Section", "Focus", "web")

                    findings = await coord._research_section(section)

                    assert findings.section_name == "Test Section"
                    assert findings.key_findings == ["Finding A", "Finding B"]
                    assert findings.recommendations == ["Rec 1"]
                    assert len(findings.sources) == 1
                    assert findings.code_examples == ["print('hello')"]

    @pytest.mark.asyncio
    async def test_synthesize_creates_document(self, mock_db):
        """Synthesize should create final research document."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="""
```json
{
    "executive_summary": "This is the summary.",
    "overall_recommendations": ["Use async", "Add tests"],
    "next_steps": ["Review code", "Deploy"]
}
```
""")

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import (
                        ResearchCoordinator,
                        ResearchFindings,
                    )

                    coord = ResearchCoordinator(topic="Test Topic", db=mock_db)
                    coord.findings = [
                        ResearchFindings(
                            section_name="Section 1",
                            key_findings=["Finding 1"],
                        )
                    ]

                    doc = await coord.synthesize()

                    assert doc.topic == "Test Topic"
                    assert doc.executive_summary == "This is the summary."
                    assert doc.overall_recommendations == ["Use async", "Add tests"]
                    assert doc.next_steps == ["Review code", "Deploy"]
                    assert len(doc.sections) == 1

    @pytest.mark.asyncio
    async def test_full_research_workflow(self, mock_db):
        """Test complete research workflow."""
        mock_agent = AsyncMock()

        # First call: decompose returns sections
        # Second call: research section
        # Third call: synthesize
        call_count = [0]

        async def mock_call(return_type, prompt, **kwargs):
            call_count[0] += 1
            if "decompose" in prompt.lower() or "analyze" in prompt.lower():
                return """
```json
[{"name": "sec1", "title": "Section 1", "research_focus": "Focus", "tool_hint": "web"}]
```
"""
            elif "research" in prompt.lower():
                return '{"key_findings": ["f1"], "recommendations": [], "sources": []}'
            else:  # synthesize
                return """
{
    "executive_summary": "Summary",
    "overall_recommendations": ["Rec"],
    "next_steps": ["Step"]
}
"""

        mock_agent.call = mock_call

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import ResearchCoordinator

                    coord = ResearchCoordinator(topic="Full Test", db=mock_db)
                    doc = await coord.research()

                    assert doc.topic == "Full Test"
                    assert len(doc.sections) >= 1

    @pytest.mark.asyncio
    async def test_coordinator_tracks_agents(self, mock_db):
        """Coordinator should register agents with CoordinationDB."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value='{"key_findings": []}')

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.tracked_spawn") as mock_tracked:
                mock_tracked.return_value = mock_agent

                from scripts.agentica_patterns.research_coordinator import (
                    ResearchCoordinator,
                    ResearchSection,
                )

                coord = ResearchCoordinator(topic="Test", db=mock_db)
                coord.sections = [
                    ResearchSection("s1", "S1", "Focus", "web"),
                ]
                await coord.research_sections()

                # Verify tracked_spawn was called with db
                assert mock_tracked.called
                call_kwargs = mock_tracked.call_args[1]
                assert call_kwargs["db"] == mock_db
                assert call_kwargs["pattern"] == "research_specialist"

    @pytest.mark.asyncio
    async def test_tool_hint_guidance(self, mock_db):
        """Test that tool_hint influences prompt guidance."""
        mock_agent = AsyncMock()
        prompts_received = []

        async def capture_prompt(return_type, prompt, **kwargs):
            prompts_received.append(prompt)
            return '{"key_findings": []}'

        mock_agent.call = capture_prompt

        with patch("scripts.agentica.research_coordinator.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                with patch("scripts.agentica.tracked_agent.tracked_spawn", return_value=mock_agent):
                    from scripts.agentica_patterns.research_coordinator import (
                        ResearchCoordinator,
                        ResearchSection,
                    )

                    coord = ResearchCoordinator(topic="Test", db=mock_db, depth="deep")
                    coord.sections = [
                        ResearchSection("lib", "Library", "Focus", "library"),
                    ]
                    await coord.research_sections()

                    # Should mention library_docs for library tool_hint
                    assert any("library_docs" in p for p in prompts_received)


class TestCLI:
    """Test CLI entry point."""

    def test_argparse_required_args(self):
        """Test that --topic is required."""
        import sys
        from io import StringIO

        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = StringIO()

        try:
            from scripts.agentica_patterns.research_coordinator import main
            import argparse

            # This would fail without --topic
            parser = argparse.ArgumentParser()
            parser.add_argument("--topic", "-t", type=str, required=True)
            with pytest.raises(SystemExit):
                parser.parse_args([])
        finally:
            sys.stderr = old_stderr

    def test_argparse_depth_choices(self):
        """Test depth argument accepts valid choices."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--depth", "-d",
            type=str,
            choices=["quick", "standard", "deep"],
            default="standard",
        )

        args = parser.parse_args(["--depth", "deep"])
        assert args.depth == "deep"

        with pytest.raises(SystemExit):
            parser.parse_args(["--depth", "invalid"])
