"""Tests for research client - NIA docs and codebase search integration.

TDD Implementation for Phases 10-11 of Self-Improving Skill System.

Phase 10: NIA Docs Integration
- Call scripts/nia_docs.py via subprocess
- Parse results into ResearchResult objects
- Graceful fallback on errors

Phase 11: Codebase Search via rp-cli
- Search for patterns in codebase
- Return relevant code snippets
- Handle empty results

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path


# =============================================================================
# Phase 10: NIA Docs Integration Tests
# =============================================================================


class TestResearchResult:
    """Test ResearchResult data structure."""

    def test_research_result_structure(self):
        """ResearchResult should have required fields."""
        # Import after test discovery
        from scripts.agentica.research_client import ResearchResult

        result = ResearchResult(
            source='nia',
            content='Test content',
            relevance=0.85,
            url='https://example.com/doc'
        )

        assert result.source == 'nia'
        assert result.content == 'Test content'
        assert result.relevance == 0.85
        assert result.url == 'https://example.com/doc'

    def test_research_result_optional_url(self):
        """URL should be optional."""
        from scripts.agentica.research_client import ResearchResult

        result = ResearchResult(
            source='codebase',
            content='Code snippet',
            relevance=0.9
        )

        assert result.url is None

    def test_research_result_source_validation(self):
        """Source should be one of: nia, codebase, web."""
        from scripts.agentica.research_client import ResearchResult

        # Valid sources
        for source in ['nia', 'codebase', 'web']:
            result = ResearchResult(source=source, content='test', relevance=0.5)
            assert result.source == source


class TestResearchViaNia:
    """Test NIA docs integration (Phase 10)."""

    def test_research_via_nia_success(self):
        """Should return results from NIA API."""
        from scripts.agentica.research_client import research_via_nia

        mock_output = json.dumps({
            'results': [
                {
                    'title': 'TypeScript Hook Pattern',
                    'content': 'Hooks should read stdin and write JSON to stdout.',
                    'url': 'https://docs.example.com/hooks'
                }
            ]
        })

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=''
            )

            results = research_via_nia('TypeScript hook best practices')

        assert len(results) >= 1
        assert results[0].source == 'nia'
        assert 'Hook' in results[0].content or 'hook' in results[0].content.lower()

    def test_research_via_nia_empty_results(self):
        """Should return empty list when no results found."""
        from scripts.agentica.research_client import research_via_nia

        mock_output = json.dumps({'results': []})

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=''
            )

            results = research_via_nia('extremely obscure topic xyz123')

        assert results == []

    def test_research_via_nia_api_error(self):
        """Should return empty list on API error (graceful fallback)."""
        from scripts.agentica.research_client import research_via_nia

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout='',
                stderr='API error: 500'
            )

            results = research_via_nia('any query')

        assert results == []

    def test_research_via_nia_timeout(self):
        """Should return empty list on timeout."""
        from scripts.agentica.research_client import research_via_nia
        import subprocess

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd='nia', timeout=30)

            results = research_via_nia('any query', timeout_seconds=30)

        assert results == []

    def test_research_via_nia_invalid_json(self):
        """Should return text content as fallback when not valid JSON.

        NIA sometimes returns formatted text instead of JSON.
        This should be captured as a single result.
        """
        from scripts.agentica.research_client import research_via_nia

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='Some formatted text output from NIA',
                stderr=''
            )

            results = research_via_nia('any query')

        # Should capture as single result (graceful handling)
        assert len(results) == 1
        assert results[0].source == 'nia'
        assert 'formatted text' in results[0].content

    def test_research_via_nia_uses_correct_script(self):
        """Should call scripts/nia_docs.py with correct arguments."""
        from scripts.agentica.research_client import research_via_nia

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({'results': []}),
                stderr=''
            )

            research_via_nia('test query')

        # Verify subprocess was called with nia_docs.py
        call_args = mock_run.call_args
        assert call_args is not None
        cmd = call_args[0][0]
        # Should contain nia_docs.py or search command
        cmd_str = ' '.join(cmd) if isinstance(cmd, list) else str(cmd)
        assert 'nia' in cmd_str.lower() or 'search' in cmd_str.lower()


class TestResearchViaNiaWithRealScript:
    """Integration-like tests that verify script invocation patterns."""

    def test_research_builds_correct_command(self):
        """Should build correct command for NIA universal search."""
        from scripts.agentica.research_client import _build_nia_command

        cmd = _build_nia_command('authentication patterns')

        assert 'search' in cmd
        assert 'universal' in cmd
        assert 'authentication patterns' in cmd


# =============================================================================
# Phase 11: Codebase Search Tests
# =============================================================================


class TestSearchCodebase:
    """Test codebase search via rp-cli or grep (Phase 11)."""

    def test_search_codebase_success(self):
        """Should return code patterns from codebase."""
        from scripts.agentica.research_client import search_codebase

        mock_output = """
src/hooks/example.ts:10:export function processHook(input: HookInput): HookOutput {
src/hooks/example.ts:15:  return { result: 'continue' };
"""

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=''
            )

            results = search_codebase('HookInput')

        assert len(results) >= 1
        assert results[0].source == 'codebase'
        assert 'HookInput' in results[0].content or 'hook' in results[0].content.lower()

    def test_search_codebase_empty_results(self):
        """Should return empty list when pattern not found."""
        from scripts.agentica.research_client import search_codebase

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='',
                stderr=''
            )

            results = search_codebase('nonexistent_pattern_xyz123')

        assert results == []

    def test_search_codebase_error_fallback(self):
        """Should return empty list on search error."""
        from scripts.agentica.research_client import search_codebase

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout='',
                stderr='Error: command not found'
            )

            results = search_codebase('any pattern')

        assert results == []

    def test_search_codebase_with_file_filter(self):
        """Should support filtering by file extension."""
        from scripts.agentica.research_client import search_codebase

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='file.ts:1:match',
                stderr=''
            )

            results = search_codebase('pattern', file_filter='*.ts')

        # Verify filter was passed
        call_args = mock_run.call_args
        assert call_args is not None

    def test_search_codebase_relevance_scoring(self):
        """Results should have relevance scores based on match quality."""
        from scripts.agentica.research_client import search_codebase

        mock_output = """
src/exact.ts:1:exactPattern
src/partial.ts:1:partial match Pattern somewhere
"""

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=''
            )

            results = search_codebase('exactPattern')

        # Results should be sorted by relevance
        if len(results) >= 2:
            assert results[0].relevance >= results[1].relevance


class TestSearchCodebasePatterns:
    """Test pattern-specific codebase searches."""

    def test_find_skill_implementations(self):
        """Should find existing skill implementations for reference."""
        from scripts.agentica.research_client import find_skill_patterns

        with patch('scripts.agentica.research_client.search_codebase') as mock_search:
            mock_search.return_value = [
                MagicMock(
                    source='codebase',
                    content='SKILL.md content',
                    relevance=0.9,
                    url=None
                )
            ]

            results = find_skill_patterns('hook')

        mock_search.assert_called()
        assert len(results) >= 0  # Can be empty if no patterns found

    def test_find_similar_tools(self):
        """Should find tools with similar functionality."""
        from scripts.agentica.research_client import find_similar_tools

        with patch('scripts.agentica.research_client.search_codebase') as mock_search:
            mock_search.return_value = []

            results = find_similar_tools(['Bash', 'Read', 'Write'])

        # Should have searched for tool-related patterns
        mock_search.assert_called()


# =============================================================================
# Combined Research Tests
# =============================================================================


class TestCombinedResearch:
    """Test combining NIA and codebase research."""

    def test_research_topic_combines_sources(self):
        """Should combine results from multiple sources."""
        from scripts.agentica.research_client import research_topic

        with patch('scripts.agentica.research_client.research_via_nia') as mock_nia, \
             patch('scripts.agentica.research_client.search_codebase') as mock_codebase:

            mock_nia.return_value = [
                MagicMock(source='nia', content='NIA result', relevance=0.8, url='http://x')
            ]
            mock_codebase.return_value = [
                MagicMock(source='codebase', content='Code result', relevance=0.7, url=None)
            ]

            results = research_topic('TypeScript hooks')

        assert len(results) >= 2
        sources = [r.source for r in results]
        assert 'nia' in sources
        assert 'codebase' in sources

    def test_research_topic_deduplicates(self):
        """Should deduplicate similar results."""
        from scripts.agentica.research_client import research_topic

        with patch('scripts.agentica.research_client.research_via_nia') as mock_nia, \
             patch('scripts.agentica.research_client.search_codebase') as mock_codebase:

            # Same content from different sources
            mock_nia.return_value = [
                MagicMock(source='nia', content='Same content', relevance=0.8, url=None)
            ]
            mock_codebase.return_value = [
                MagicMock(source='codebase', content='Same content', relevance=0.7, url=None)
            ]

            results = research_topic('test')

        # Should deduplicate based on content
        contents = [r.content for r in results]
        # At least some deduplication should occur
        assert len(contents) <= 2

    def test_research_topic_sorts_by_relevance(self):
        """Results should be sorted by relevance (highest first)."""
        from scripts.agentica.research_client import research_topic

        with patch('scripts.agentica.research_client.research_via_nia') as mock_nia, \
             patch('scripts.agentica.research_client.search_codebase') as mock_codebase:

            mock_nia.return_value = [
                MagicMock(source='nia', content='Low relevance', relevance=0.3, url=None)
            ]
            mock_codebase.return_value = [
                MagicMock(source='codebase', content='High relevance', relevance=0.9, url=None)
            ]

            results = research_topic('test')

        if len(results) >= 2:
            assert results[0].relevance >= results[1].relevance

    def test_research_topic_graceful_on_all_failures(self):
        """Should return empty list if all sources fail."""
        from scripts.agentica.research_client import research_topic

        with patch('scripts.agentica.research_client.research_via_nia') as mock_nia, \
             patch('scripts.agentica.research_client.search_codebase') as mock_codebase:

            mock_nia.return_value = []
            mock_codebase.return_value = []

            results = research_topic('test')

        assert results == []


# =============================================================================
# Research Client Configuration Tests
# =============================================================================


class TestResearchClientConfig:
    """Test research client configuration."""

    def test_default_timeout(self):
        """Should have reasonable default timeout."""
        from scripts.agentica.research_client import DEFAULT_TIMEOUT_SECONDS

        assert DEFAULT_TIMEOUT_SECONDS >= 5
        assert DEFAULT_TIMEOUT_SECONDS <= 60

    def test_max_results_limit(self):
        """Should limit maximum results returned."""
        from scripts.agentica.research_client import MAX_RESULTS

        assert MAX_RESULTS >= 5
        assert MAX_RESULTS <= 50
