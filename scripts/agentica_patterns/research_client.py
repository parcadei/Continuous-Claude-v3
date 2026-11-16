"""Research Client - NIA docs and codebase search integration.

Phases 10-11 of Self-Improving Skill System.

Phase 10: NIA Docs Integration
- Calls scripts/nia_docs.py via subprocess
- Parses results into ResearchResult objects
- Graceful fallback on errors

Phase 11: Codebase Search via rp-cli
- Searches for patterns in codebase using grep/rp-cli
- Returns relevant code snippets
- Handles empty results gracefully

Usage:
    from scripts.agentica_patterns.research_client import research_topic

    results = research_topic('TypeScript hook best practices')
    for r in results:
        print(f"[{r.source}] {r.content[:100]}...")

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import json
import os
import subprocess
from dataclasses import dataclass

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_TIMEOUT_SECONDS = 30
MAX_RESULTS = 20
PROJECT_DIR = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ResearchResult:
    """Result from a research operation.

    Attributes:
        source: Origin of the result - 'nia', 'codebase', or 'web'
        content: The actual content/text
        relevance: Relevance score 0-1 (higher = more relevant)
        url: Optional URL for web/doc sources
    """
    source: str  # 'nia', 'codebase', 'web'
    content: str
    relevance: float
    url: str | None = None

    def __post_init__(self):
        # Validate source
        if self.source not in ('nia', 'codebase', 'web'):
            raise ValueError(f"Invalid source: {self.source}")


# =============================================================================
# Phase 10: NIA Docs Integration
# =============================================================================


def _build_nia_command(query: str) -> list[str]:
    """Build command for NIA universal search.

    Args:
        query: Search query

    Returns:
        Command list for subprocess
    """
    return [
        'uv', 'run', 'python', '-m', 'runtime.harness',
        'scripts/nia_docs.py',
        'search', 'universal', query
    ]


def research_via_nia(
    query: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> list[ResearchResult]:
    """Research a topic using NIA docs API.

    Calls the NIA API via scripts/nia_docs.py subprocess.
    Returns empty list on any error (graceful fallback).

    Args:
        query: Natural language research query
        timeout_seconds: Subprocess timeout

    Returns:
        List of ResearchResult objects from NIA
    """
    if not query or not query.strip():
        return []

    try:
        cmd = _build_nia_command(query)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=PROJECT_DIR
        )

        if result.returncode != 0:
            return []

        # Parse output - NIA returns formatted text, try to extract JSON
        output = result.stdout.strip()

        # Try to parse as JSON if it looks like JSON
        if output.startswith('{') or output.startswith('['):
            try:
                data = json.loads(output)
                return _parse_nia_json_response(data)
            except json.JSONDecodeError:
                pass

        # Otherwise, treat as text output and convert to single result
        if output:
            return [
                ResearchResult(
                    source='nia',
                    content=output[:2000],  # Limit content size
                    relevance=0.7,
                    url=None
                )
            ]

        return []

    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def _parse_nia_json_response(data: dict) -> list[ResearchResult]:
    """Parse NIA JSON response into ResearchResults.

    Args:
        data: Parsed JSON from NIA API

    Returns:
        List of ResearchResult objects
    """
    results = []

    # Handle different response formats
    items = data.get('results', [])
    if not items and isinstance(data, list):
        items = data

    for item in items[:MAX_RESULTS]:
        if isinstance(item, dict):
            content = item.get('content', item.get('snippet', item.get('title', '')))
            url = item.get('url', item.get('link'))

            if content:
                results.append(ResearchResult(
                    source='nia',
                    content=content[:2000],
                    relevance=float(item.get('score', item.get('relevance', 0.7))),
                    url=url
                ))
        elif isinstance(item, str):
            results.append(ResearchResult(
                source='nia',
                content=item[:2000],
                relevance=0.6,
                url=None
            ))

    return results


# =============================================================================
# Phase 11: Codebase Search
# =============================================================================


def search_codebase(
    pattern: str,
    file_filter: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> list[ResearchResult]:
    """Search the codebase for a pattern.

    Uses grep or rg to find matching code patterns.
    Returns empty list on any error (graceful fallback).

    Args:
        pattern: Search pattern (regex or text)
        file_filter: Optional glob pattern for files (e.g., '*.ts')
        timeout_seconds: Subprocess timeout

    Returns:
        List of ResearchResult objects from codebase
    """
    if not pattern or not pattern.strip():
        return []

    try:
        # Build command - try rg first, fall back to grep
        cmd = _build_search_command(pattern, file_filter)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=PROJECT_DIR
        )

        # Even if returncode is 1 (no matches), that's ok
        output = result.stdout.strip()
        if not output:
            return []

        return _parse_grep_output(output, pattern)

    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def _build_search_command(
    pattern: str,
    file_filter: str | None = None
) -> list[str]:
    """Build search command (rg or grep).

    Args:
        pattern: Search pattern
        file_filter: Optional file glob

    Returns:
        Command list for subprocess
    """
    # Try ripgrep first (faster, better output)
    cmd = ['rg', '--no-heading', '--line-number', '-m', '50', pattern]

    if file_filter:
        cmd.extend(['--glob', file_filter])

    # Exclude common directories
    cmd.extend(['--glob', '!node_modules', '--glob', '!.venv', '--glob', '!.git'])

    return cmd


def _parse_grep_output(output: str, pattern: str) -> list[ResearchResult]:
    """Parse grep/rg output into ResearchResults.

    Args:
        output: Raw grep output
        pattern: Original search pattern (for scoring)

    Returns:
        List of ResearchResult objects
    """
    results = []
    lines = output.split('\n')

    for line in lines[:MAX_RESULTS]:
        if not line.strip():
            continue

        # Parse line format: file:line:content
        parts = line.split(':', 2)
        if len(parts) >= 2:
            file_path = parts[0]
            content = parts[-1] if len(parts) > 2 else parts[1]

            # Calculate relevance based on exact match
            relevance = 0.8 if pattern.lower() in content.lower() else 0.5

            results.append(ResearchResult(
                source='codebase',
                content=f"{file_path}: {content.strip()}",
                relevance=relevance,
                url=None
            ))
        else:
            # Just content without file info
            results.append(ResearchResult(
                source='codebase',
                content=line.strip(),
                relevance=0.5,
                url=None
            ))

    # Sort by relevance
    results.sort(key=lambda r: r.relevance, reverse=True)

    return results


def find_skill_patterns(query: str) -> list[ResearchResult]:
    """Find existing skill implementations for reference.

    Searches .claude/skills/ for similar patterns.

    Args:
        query: Pattern to search for

    Returns:
        List of ResearchResult objects from skill files
    """
    return search_codebase(query, file_filter='*.md')


def find_similar_tools(tools: list[str]) -> list[ResearchResult]:
    """Find code using similar tools.

    Args:
        tools: List of tool names to search for

    Returns:
        List of ResearchResult objects
    """
    results = []
    for tool in tools[:5]:  # Limit to avoid too many searches
        tool_results = search_codebase(tool, file_filter='*.ts')
        results.extend(tool_results)

    # Sort and deduplicate
    results.sort(key=lambda r: r.relevance, reverse=True)
    return results[:MAX_RESULTS]


# =============================================================================
# Combined Research
# =============================================================================


def research_topic(
    query: str,
    include_nia: bool = True,
    include_codebase: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> list[ResearchResult]:
    """Research a topic using all available sources.

    Combines NIA docs and codebase search, deduplicates, and sorts by relevance.

    Args:
        query: Research query
        include_nia: Whether to search NIA docs
        include_codebase: Whether to search codebase
        timeout_seconds: Timeout for each source

    Returns:
        List of ResearchResult objects sorted by relevance
    """
    all_results = []

    # Search NIA docs
    if include_nia:
        nia_results = research_via_nia(query, timeout_seconds)
        all_results.extend(nia_results)

    # Search codebase
    if include_codebase:
        codebase_results = search_codebase(query, timeout_seconds=timeout_seconds)
        all_results.extend(codebase_results)

    # Deduplicate by content (keep highest relevance)
    seen_content = {}
    deduped = []

    for result in all_results:
        content_key = result.content[:100].lower().strip()
        if content_key not in seen_content:
            seen_content[content_key] = result
            deduped.append(result)
        elif result.relevance > seen_content[content_key].relevance:
            # Replace with higher relevance result
            deduped.remove(seen_content[content_key])
            seen_content[content_key] = result
            deduped.append(result)

    # Sort by relevance
    deduped.sort(key=lambda r: r.relevance, reverse=True)

    return deduped[:MAX_RESULTS]
