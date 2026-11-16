#!/usr/bin/env python3
"""Nia API Client - Complete API coverage for documentation, research, and search.

API Categories:
- Oracle Research: Autonomous AI research agent (Pro only)
- Search: Query repos, docs, web, universal search
- Repositories: Index and search GitHub repos
- Data Sources: Index and search documentation websites
- Research Papers: Index and search arXiv papers
- Context Sharing: Save and retrieve conversation contexts

Usage Examples:
  # Oracle autonomous research (Pro only)
  uv run python -m runtime.harness scripts/nia_docs.py \
    oracle research "best practices for hybrid BM25 + vector search"

  # Universal search across all indexed sources
  uv run python -m runtime.harness scripts/nia_docs.py \
    search universal "authentication middleware patterns"

  # Search in specific package
  uv run python -m runtime.harness scripts/nia_docs.py \
    search package fastapi --query "dependency injection"

  # Web search
  uv run python -m runtime.harness scripts/nia_docs.py \
    search web "sqlite-vss vector search"

  # Deep research (Pro only)
  uv run python -m runtime.harness scripts/nia_docs.py \
    search deep "implementing hybrid retrieval with reranking"

  # List indexed repositories
  uv run python -m runtime.harness scripts/nia_docs.py repos list

  # Index a new repository
  uv run python -m runtime.harness scripts/nia_docs.py repos index owner/repo

  # Search repository code
  uv run python -m runtime.harness scripts/nia_docs.py repos grep owner/repo "pattern"

  # List data sources
  uv run python -m runtime.harness scripts/nia_docs.py sources list

  # Index documentation website
  uv run python -m runtime.harness scripts/nia_docs.py sources index https://docs.example.com

  # List research papers
  uv run python -m runtime.harness scripts/nia_docs.py papers list

  # Index arXiv paper
  uv run python -m runtime.harness scripts/nia_docs.py papers index 2310.06825

  # Save conversation context
  uv run python -m runtime.harness scripts/nia_docs.py context save --title "My Context" --content "..."

  # Search contexts
  uv run python -m runtime.harness scripts/nia_docs.py context search "embeddings"

Requires: NIA_API_KEY environment variable
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# API base URL
NIA_API_URL = os.environ.get("NIA_API_URL", "https://apigcp.trynia.ai")


def load_api_key() -> str:
    """Load API key from environment or .env file."""
    if os.environ.get("NIA_API_KEY"):
        return os.environ["NIA_API_KEY"]

    for env_path in [Path.home() / ".claude" / ".env", Path.cwd() / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NIA_API_KEY="):
                        key = line.split("=", 1)[1].strip('"\'')
                        os.environ["NIA_API_KEY"] = key
                        return key
    return ""


NIA_API_KEY = load_api_key()


def get_headers() -> dict:
    """Get common headers for API requests."""
    return {
        "Authorization": f"Bearer {NIA_API_KEY}",
        "Content-Type": "application/json"
    }


# =============================================================================
# ORACLE RESEARCH API
# =============================================================================

async def oracle_research(
    query: str,
    repositories: List[str] = None,
    data_sources: List[str] = None,
    output_format: str = None,
    model: str = "claude-opus-4-5-20251101"
) -> dict:
    """Oracle autonomous research agent (Pro only).

    Args:
        query: Research question to investigate
        repositories: Optional list of repository identifiers
        data_sources: Optional list of documentation source IDs
        output_format: Optional format specification
        model: Model to use (claude-opus-4-5-20251101, claude-sonnet-4-5-20250929, claude-sonnet-4-5-1m)

    Returns:
        Research report with citations, tool calls, iterations, duration
    """
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle"
    payload = {"query": query, "model": model}

    if repositories:
        payload["repositories"] = repositories
    if data_sources:
        payload["data_sources"] = data_sources
    if output_format:
        payload["output_format"] = output_format

    async with aiohttp.ClientSession() as session:
        timeout = aiohttp.ClientTimeout(total=300)  # 5 min for deep research
        async with session.post(url, headers=get_headers(), json=payload, timeout=timeout) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_research_stream(
    query: str,
    repositories: List[str] = None,
    data_sources: List[str] = None,
    model: str = "claude-opus-4-5-20251101"
) -> None:
    """Oracle research with real-time streaming (Pro only). Prints events as they arrive."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/stream"
    payload = {"query": query, "model": model}

    if repositories:
        payload["repositories"] = repositories
    if data_sources:
        payload["data_sources"] = data_sources

    async with aiohttp.ClientSession() as session:
        timeout = aiohttp.ClientTimeout(total=300)
        async with session.post(url, headers=get_headers(), json=payload, timeout=timeout) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status} - {await resp.text()}")
                return

            async for line in resp.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data:'):
                    print(line[5:].strip())


async def oracle_list_sessions(limit: int = 20, offset: int = 0) -> dict:
    """List Oracle research sessions."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/sessions"
    params = {"limit": limit, "offset": offset}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_get_session(session_id: str) -> dict:
    """Get Oracle research session details."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/sessions/{session_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_get_messages(session_id: str) -> dict:
    """Get Oracle session chat messages."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/sessions/{session_id}/messages"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_chat_followup(session_id: str, message: str) -> None:
    """Stream a follow-up chat answer for an Oracle session (SSE)."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/sessions/{session_id}/chat"
    payload = {"message": message}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status} - {await resp.text()}")
                return

            async for line in resp.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data:'):
                    print(line[5:].strip())


async def oracle_list_jobs() -> dict:
    """List Oracle research jobs."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/jobs"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_create_job(
    query: str,
    repositories: List[str] = None,
    data_sources: List[str] = None,
    model: str = "claude-opus-4-5-20251101"
) -> dict:
    """Create Oracle research job (Pro only). Returns immediately, runs async."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/jobs"
    payload = {"query": query, "model": model}

    if repositories:
        payload["repositories"] = repositories
    if data_sources:
        payload["data_sources"] = data_sources

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_get_job(job_id: str) -> dict:
    """Get Oracle job status and result."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/jobs/{job_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def oracle_cancel_job(job_id: str) -> dict:
    """Cancel Oracle research job."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/jobs/{job_id}"

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return {"status": "cancelled", "job_id": job_id}


async def oracle_stream_job_events(job_id: str) -> None:
    """Stream Oracle job events (SSE)."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/oracle/jobs/{job_id}/events"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status} - {await resp.text()}")
                return

            async for line in resp.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data:'):
                    print(line[5:].strip())


# =============================================================================
# SEARCH API
# =============================================================================

async def search_query(
    messages: List[dict],
    repositories: List[str] = None,
    data_sources: List[str] = None,
    search_mode: str = "repositories",
    include_sources: bool = True
) -> dict:
    """Query indexed repositories and documentation."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/search/query"
    payload = {
        "messages": messages,
        "search_mode": search_mode,
        "include_sources": include_sources
    }

    if repositories:
        payload["repositories"] = repositories
    if data_sources:
        payload["data_sources"] = data_sources

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def search_web(query: str, category: str = None, time_range: str = None) -> dict:
    """Web search."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/search/web"
    payload = {"query": query}

    if category:
        payload["category"] = category
    if time_range:
        payload["time_range"] = time_range

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def search_deep(query: str) -> dict:
    """Deep research agent (Pro only)."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/search/deep"
    payload = {"query": query}

    async with aiohttp.ClientSession() as session:
        timeout = aiohttp.ClientTimeout(total=300)
        async with session.post(url, headers=get_headers(), json=payload, timeout=timeout) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def search_universal(query: str, limit: int = 10) -> dict:
    """Universal search across all public indexed sources."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/search/universal"
    payload = {"query": query, "search_mode": "unified", "limit": limit}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def search_package_hybrid(
    package: str,
    query: str,
    registry: str = "py_pi",
    limit: int = 10
) -> dict:
    """Semantic search within a package."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/package-search/hybrid"
    payload = {
        "registry": registry,
        "package_name": package,
        "semantic_queries": [query],
        "limit": limit
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def search_package_grep(
    package: str,
    pattern: str,
    registry: str = "py_pi",
    limit: int = 10
) -> dict:
    """Regex search within a package."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/package-search/grep"
    payload = {
        "registry": registry,
        "package_name": package,
        "pattern": pattern,
        "limit": limit
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


# =============================================================================
# REPOSITORIES API
# =============================================================================

async def repos_list(
    q: str = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """List all indexed repositories."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories"
    params = {"limit": limit, "offset": offset}
    if q:
        params["q"] = q
    if status:
        params["status"] = status

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def repos_index(repo: str, github_token: str = None) -> dict:
    """Index a new GitHub repository."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories"
    payload = {"repository": repo}
    if github_token:
        payload["github_token"] = github_token

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def repos_status(repository_id: str) -> dict:
    """Get repository indexing status."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories/{repository_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def repos_delete(repository_id: str) -> dict:
    """Delete a repository."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories/{repository_id}"

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return {"status": "deleted", "repository_id": repository_id}


async def repos_rename(repository_id: str, display_name: str) -> dict:
    """Rename a repository."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories/{repository_id}/rename"
    payload = {"display_name": display_name}

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def repos_tree(repository_id: str) -> dict:
    """Get repository tree structure."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories/{repository_id}/tree"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def repos_content(repository_id: str, path: str) -> dict:
    """Get repository file content."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories/{repository_id}/content"
    payload = {"path": path}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def repos_grep(
    repository_id: str,
    pattern: str,
    context_lines: int = 3,
    exhaustive: bool = False
) -> dict:
    """Search repository code with regex."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/repositories/{repository_id}/grep"
    payload = {
        "pattern": pattern,
        "context_lines": context_lines,
        "exhaustive": exhaustive
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


# =============================================================================
# DATA SOURCES API
# =============================================================================

async def sources_list(
    q: str = None,
    status: str = None,
    source_type: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """List all data sources."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources"
    params = {"limit": limit, "offset": offset}
    if q:
        params["q"] = q
    if status:
        params["status"] = status
    if source_type:
        params["source_type"] = source_type

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_index(url_to_index: str, display_name: str = None) -> dict:
    """Index a new data source (documentation website)."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources"
    payload = {"url": url_to_index}
    if display_name:
        payload["display_name"] = display_name

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_get(source_id: str) -> dict:
    """Get data source details."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_delete(source_id: str) -> dict:
    """Delete a data source."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}"

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return {"status": "deleted", "source_id": source_id}


async def sources_content(source_id: str, path: str) -> dict:
    """Get data source page content."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}/content"
    payload = {"path": path}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_tree(source_id: str) -> dict:
    """Get documentation tree structure."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}/tree"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_ls(source_id: str, path: str = "/") -> dict:
    """List documentation directory contents."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}/ls"
    params = {"path": path}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_read(source_id: str, path: str) -> dict:
    """Read documentation page content."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}/read"
    params = {"path": path}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_grep(source_id: str, pattern: str, context_lines: int = 3) -> dict:
    """Search documentation with regex."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/{source_id}/grep"
    payload = {"pattern": pattern, "context_lines": context_lines}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def sources_rename(source_id: str, display_name: str) -> dict:
    """Rename a data source."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/data-sources/rename"
    payload = {"source_id": source_id, "display_name": display_name}

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


# =============================================================================
# RESEARCH PAPERS API
# =============================================================================

async def papers_list(
    limit: int = 50,
    offset: int = 0,
    status: str = None
) -> dict:
    """List indexed research papers."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/research-papers"
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def papers_index(arxiv_id: str) -> dict:
    """Index an arXiv research paper."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/research-papers"
    payload = {"arxiv_id": arxiv_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


# =============================================================================
# CONTEXT SHARING API
# =============================================================================

async def context_list(
    limit: int = 20,
    offset: int = 0,
    tags: str = None,
    agent_source: str = None
) -> dict:
    """List conversation contexts."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts"
    params = {"limit": limit, "offset": offset}
    if tags:
        params["tags"] = tags
    if agent_source:
        params["agent_source"] = agent_source

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def context_save(
    title: str,
    content: str,
    summary: str = None,
    tags: List[str] = None,
    metadata: dict = None
) -> dict:
    """Save conversation context."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts"
    payload = {"title": title, "content": content}
    if summary:
        payload["summary"] = summary
    if tags:
        payload["tags"] = tags
    if metadata:
        payload["metadata"] = metadata

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=get_headers(), json=payload) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def context_search_text(query: str) -> dict:
    """Text search contexts."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts/search"
    params = {"query": query}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def context_search_semantic(query: str) -> dict:
    """Semantic search contexts using embeddings."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts/semantic-search"
    params = {"query": query}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(), params=params) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def context_get(context_id: str) -> dict:
    """Get conversation context details."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts/{context_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def context_update(context_id: str, updates: dict) -> dict:
    """Update conversation context."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts/{context_id}"

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=get_headers(), json=updates) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return await resp.json()


async def context_delete(context_id: str) -> dict:
    """Delete conversation context."""
    import aiohttp

    url = f"{NIA_API_URL}/v2/contexts/{context_id}"

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=get_headers()) as resp:
            if resp.status != 200:
                return {"error": f"API error {resp.status}: {await resp.text()}"}
            return {"status": "deleted", "context_id": context_id}


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_oracle_result(result: dict) -> str:
    """Format Oracle research result."""
    if "error" in result:
        return f"Error: {result['error']}"

    output = ["# Oracle Research Result\n"]

    if result.get("final_report"):
        output.append(result["final_report"])

    if result.get("citations"):
        output.append("\n## Citations")
        for i, cite in enumerate(result["citations"], 1):
            output.append(f"{i}. [{cite.get('tool', 'unknown')}] {cite.get('summary', '')[:200]}")

    if result.get("duration_ms"):
        output.append(f"\n---\nDuration: {result['duration_ms']}ms | Iterations: {result.get('iterations', 'N/A')}")

    return "\n".join(output)


def format_search_result(result: dict, search_type: str) -> str:
    """Format search results."""
    if "error" in result:
        return f"Error: {result['error']}"

    output = [f"# {search_type} Results\n"]

    if "content" in result:
        output.append(result["content"][:2000])
        if result.get("sources"):
            output.append("\n## Sources")
            for src in result["sources"][:5]:
                if isinstance(src, dict):
                    output.append(f"- {src.get('title', src.get('path', 'unknown'))}")
                else:
                    output.append(f"- {src}")

    elif "results" in result:
        for i, item in enumerate(result["results"][:10], 1):
            if isinstance(item, dict):
                title = item.get("title", item.get("path", item.get("name", f"Result {i}")))
                snippet = item.get("snippet", item.get("content", item.get("description", "")))[:300]
                output.append(f"\n{i}. **{title}**")
                if snippet:
                    output.append(f"   {snippet}")
            else:
                output.append(f"\n{i}. {str(item)[:300]}")

    elif "matches" in result:
        for i, match in enumerate(result["matches"][:10], 1):
            path = match.get("path", match.get("file", "unknown"))
            line = match.get("line", match.get("content", ""))
            output.append(f"\n{i}. `{path}`")
            if line:
                output.append(f"   {line[:200]}")

    else:
        output.append(json.dumps(result, indent=2, default=str)[:2000])

    return "\n".join(output)


def format_list_result(result: dict, item_type: str) -> str:
    """Format list results."""
    if "error" in result:
        return f"Error: {result['error']}"

    output = [f"# {item_type}\n"]

    items = result.get("repositories") or result.get("data_sources") or result.get("papers") or result.get("contexts") or result.get("sessions") or result.get("jobs") or []

    if not items:
        output.append("No items found.")
    else:
        for i, item in enumerate(items[:20], 1):
            if isinstance(item, dict):
                name = item.get("display_name", item.get("title", item.get("repository_id", item.get("id", f"Item {i}"))))
                status = item.get("status", "")
                output.append(f"{i}. {name} {f'({status})' if status else ''}")
            else:
                output.append(f"{i}. {item}")

    total = result.get("total", len(items))
    output.append(f"\n---\nTotal: {total}")

    return "\n".join(output)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Nia API Client - Complete API coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command category")

    # Oracle commands
    oracle_parser = subparsers.add_parser("oracle", help="Oracle research (Pro only)")
    oracle_sub = oracle_parser.add_subparsers(dest="action")

    oracle_research_p = oracle_sub.add_parser("research", help="Run autonomous research")
    oracle_research_p.add_argument("query", help="Research question")
    oracle_research_p.add_argument("--repos", nargs="*", help="Repository IDs")
    oracle_research_p.add_argument("--sources", nargs="*", help="Data source IDs")
    oracle_research_p.add_argument("--model", default="claude-opus-4-5-20251101",
                                   choices=["claude-opus-4-5-20251101", "claude-sonnet-4-5-20250929", "claude-sonnet-4-5-1m"])
    oracle_research_p.add_argument("--stream", action="store_true", help="Stream results")

    oracle_sessions_p = oracle_sub.add_parser("sessions", help="List research sessions")
    oracle_sessions_p.add_argument("--limit", type=int, default=20)

    oracle_session_p = oracle_sub.add_parser("session", help="Get session details")
    oracle_session_p.add_argument("session_id", help="Session ID")
    oracle_session_p.add_argument("--messages", action="store_true", help="Get chat messages")

    oracle_chat_p = oracle_sub.add_parser("chat", help="Follow-up chat in session")
    oracle_chat_p.add_argument("session_id", help="Session ID")
    oracle_chat_p.add_argument("message", help="Follow-up message")

    oracle_jobs_p = oracle_sub.add_parser("jobs", help="List research jobs")

    oracle_job_p = oracle_sub.add_parser("job", help="Get/manage job")
    oracle_job_p.add_argument("job_id", help="Job ID")
    oracle_job_p.add_argument("--cancel", action="store_true", help="Cancel job")
    oracle_job_p.add_argument("--stream", action="store_true", help="Stream events")

    oracle_create_job_p = oracle_sub.add_parser("create-job", help="Create async job")
    oracle_create_job_p.add_argument("query", help="Research question")
    oracle_create_job_p.add_argument("--repos", nargs="*", help="Repository IDs")
    oracle_create_job_p.add_argument("--model", default="claude-opus-4-5-20251101")

    # Search commands
    search_parser = subparsers.add_parser("search", help="Search operations")
    search_sub = search_parser.add_subparsers(dest="action")

    search_universal_p = search_sub.add_parser("universal", help="Universal search")
    search_universal_p.add_argument("query", help="Search query")
    search_universal_p.add_argument("--limit", type=int, default=10)

    search_web_p = search_sub.add_parser("web", help="Web search")
    search_web_p.add_argument("query", help="Search query")
    search_web_p.add_argument("--category", help="Category filter")
    search_web_p.add_argument("--time", help="Time range")

    search_deep_p = search_sub.add_parser("deep", help="Deep research (Pro)")
    search_deep_p.add_argument("query", help="Research query")

    search_package_p = search_sub.add_parser("package", help="Search in package")
    search_package_p.add_argument("package", help="Package name")
    search_package_p.add_argument("--query", help="Semantic search query")
    search_package_p.add_argument("--grep", help="Regex pattern")
    search_package_p.add_argument("--registry", default="py_pi",
                                  choices=["npm", "py_pi", "crates", "go_modules"])
    search_package_p.add_argument("--limit", type=int, default=10)

    search_query_p = search_sub.add_parser("query", help="Query repos/docs")
    search_query_p.add_argument("query", help="Query text")
    search_query_p.add_argument("--repos", nargs="*", help="Repository IDs")
    search_query_p.add_argument("--sources", nargs="*", help="Data source IDs")

    # Repository commands
    repos_parser = subparsers.add_parser("repos", help="Repository operations")
    repos_sub = repos_parser.add_subparsers(dest="action")

    repos_list_p = repos_sub.add_parser("list", help="List repositories")
    repos_list_p.add_argument("--filter", help="Filter substring")
    repos_list_p.add_argument("--status", help="Status filter")
    repos_list_p.add_argument("--limit", type=int, default=100)

    repos_index_p = repos_sub.add_parser("index", help="Index repository")
    repos_index_p.add_argument("repo", help="owner/repo")
    repos_index_p.add_argument("--token", help="GitHub token for private repos")

    repos_status_p = repos_sub.add_parser("status", help="Get status")
    repos_status_p.add_argument("repo_id", help="Repository ID")

    repos_tree_p = repos_sub.add_parser("tree", help="Get tree structure")
    repos_tree_p.add_argument("repo_id", help="Repository ID")

    repos_content_p = repos_sub.add_parser("content", help="Get file content")
    repos_content_p.add_argument("repo_id", help="Repository ID")
    repos_content_p.add_argument("path", help="File path")

    repos_grep_p = repos_sub.add_parser("grep", help="Search with regex")
    repos_grep_p.add_argument("repo_id", help="Repository ID")
    repos_grep_p.add_argument("pattern", help="Regex pattern")
    repos_grep_p.add_argument("--context", type=int, default=3)

    repos_delete_p = repos_sub.add_parser("delete", help="Delete repository")
    repos_delete_p.add_argument("repo_id", help="Repository ID")

    # Data sources commands
    sources_parser = subparsers.add_parser("sources", help="Data source operations")
    sources_sub = sources_parser.add_subparsers(dest="action")

    sources_list_p = sources_sub.add_parser("list", help="List sources")
    sources_list_p.add_argument("--filter", help="Filter substring")
    sources_list_p.add_argument("--status", help="Status filter")
    sources_list_p.add_argument("--limit", type=int, default=100)

    sources_index_p = sources_sub.add_parser("index", help="Index documentation")
    sources_index_p.add_argument("url", help="Documentation URL")
    sources_index_p.add_argument("--name", help="Display name")

    sources_get_p = sources_sub.add_parser("get", help="Get source details")
    sources_get_p.add_argument("source_id", help="Source ID")

    sources_tree_p = sources_sub.add_parser("tree", help="Get tree structure")
    sources_tree_p.add_argument("source_id", help="Source ID")

    sources_content_p = sources_sub.add_parser("content", help="Get page content")
    sources_content_p.add_argument("source_id", help="Source ID")
    sources_content_p.add_argument("path", help="Page path")

    sources_grep_p = sources_sub.add_parser("grep", help="Search with regex")
    sources_grep_p.add_argument("source_id", help="Source ID")
    sources_grep_p.add_argument("pattern", help="Regex pattern")

    sources_delete_p = sources_sub.add_parser("delete", help="Delete source")
    sources_delete_p.add_argument("source_id", help="Source ID")

    # Papers commands
    papers_parser = subparsers.add_parser("papers", help="Research papers")
    papers_sub = papers_parser.add_subparsers(dest="action")

    papers_list_p = papers_sub.add_parser("list", help="List papers")
    papers_list_p.add_argument("--status", help="Status filter")
    papers_list_p.add_argument("--limit", type=int, default=50)

    papers_index_p = papers_sub.add_parser("index", help="Index arXiv paper")
    papers_index_p.add_argument("arxiv_id", help="arXiv ID (e.g., 2310.06825)")

    # Context commands
    context_parser = subparsers.add_parser("context", help="Context sharing")
    context_sub = context_parser.add_subparsers(dest="action")

    context_list_p = context_sub.add_parser("list", help="List contexts")
    context_list_p.add_argument("--tags", help="Filter by tags")
    context_list_p.add_argument("--limit", type=int, default=20)

    context_save_p = context_sub.add_parser("save", help="Save context")
    context_save_p.add_argument("--title", required=True, help="Context title")
    context_save_p.add_argument("--content", required=True, help="Context content")
    context_save_p.add_argument("--summary", help="Optional summary")
    context_save_p.add_argument("--tags", nargs="*", help="Tags")

    context_search_p = context_sub.add_parser("search", help="Search contexts")
    context_search_p.add_argument("query", help="Search query")
    context_search_p.add_argument("--semantic", action="store_true", help="Use semantic search")

    context_get_p = context_sub.add_parser("get", help="Get context")
    context_get_p.add_argument("context_id", help="Context ID")

    context_delete_p = context_sub.add_parser("delete", help="Delete context")
    context_delete_p.add_argument("context_id", help="Context ID")

    return parser


async def main():
    parser = build_parser()

    # Handle args that might come from runtime harness
    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    if not args_to_parse:
        parser.print_help()
        return

    args = parser.parse_args(args_to_parse)

    if not NIA_API_KEY:
        print("Error: NIA_API_KEY not found. Set in environment or ~/.claude/.env")
        return

    try:
        # Oracle commands
        if args.command == "oracle":
            if args.action == "research":
                print(f"Running Oracle research: {args.query}")
                if args.stream:
                    await oracle_research_stream(args.query, args.repos, args.sources, args.model)
                else:
                    result = await oracle_research(args.query, args.repos, args.sources, model=args.model)
                    print(format_oracle_result(result))

            elif args.action == "sessions":
                result = await oracle_list_sessions(args.limit)
                print(format_list_result(result, "Oracle Sessions"))

            elif args.action == "session":
                if args.messages:
                    result = await oracle_get_messages(args.session_id)
                else:
                    result = await oracle_get_session(args.session_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "chat":
                await oracle_chat_followup(args.session_id, args.message)

            elif args.action == "jobs":
                result = await oracle_list_jobs()
                print(format_list_result(result, "Oracle Jobs"))

            elif args.action == "job":
                if args.cancel:
                    result = await oracle_cancel_job(args.job_id)
                elif args.stream:
                    await oracle_stream_job_events(args.job_id)
                    return
                else:
                    result = await oracle_get_job(args.job_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "create-job":
                result = await oracle_create_job(args.query, args.repos, model=args.model)
                print(json.dumps(result, indent=2, default=str))

        # Search commands
        elif args.command == "search":
            if args.action == "universal":
                print(f"Universal search: {args.query}")
                result = await search_universal(args.query, args.limit)
                print(format_search_result(result, "Universal Search"))

            elif args.action == "web":
                print(f"Web search: {args.query}")
                result = await search_web(args.query, args.category, args.time)
                print(format_search_result(result, "Web Search"))

            elif args.action == "deep":
                print(f"Deep research: {args.query}")
                result = await search_deep(args.query)
                print(format_search_result(result, "Deep Research"))

            elif args.action == "package":
                if args.grep:
                    print(f"Package grep: {args.package} / {args.grep}")
                    result = await search_package_grep(args.package, args.grep, args.registry, args.limit)
                else:
                    print(f"Package search: {args.package} / {args.query}")
                    result = await search_package_hybrid(args.package, args.query or "", args.registry, args.limit)
                print(format_search_result(result, "Package Search"))

            elif args.action == "query":
                messages = [{"role": "user", "content": args.query}]
                result = await search_query(messages, args.repos, args.sources)
                print(format_search_result(result, "Query"))

        # Repository commands
        elif args.command == "repos":
            if args.action == "list":
                result = await repos_list(args.filter, args.status, args.limit)
                print(format_list_result(result, "Repositories"))

            elif args.action == "index":
                print(f"Indexing repository: {args.repo}")
                result = await repos_index(args.repo, args.token)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "status":
                result = await repos_status(args.repo_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "tree":
                result = await repos_tree(args.repo_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "content":
                result = await repos_content(args.repo_id, args.path)
                print(result.get("content", json.dumps(result, indent=2)))

            elif args.action == "grep":
                result = await repos_grep(args.repo_id, args.pattern, args.context)
                print(format_search_result(result, "Repository Grep"))

            elif args.action == "delete":
                result = await repos_delete(args.repo_id)
                print(json.dumps(result, indent=2))

        # Data sources commands
        elif args.command == "sources":
            if args.action == "list":
                result = await sources_list(args.filter, args.status, limit=args.limit)
                print(format_list_result(result, "Data Sources"))

            elif args.action == "index":
                print(f"Indexing: {args.url}")
                result = await sources_index(args.url, args.name)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "get":
                result = await sources_get(args.source_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "tree":
                result = await sources_tree(args.source_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "content":
                result = await sources_content(args.source_id, args.path)
                print(result.get("content", json.dumps(result, indent=2)))

            elif args.action == "grep":
                result = await sources_grep(args.source_id, args.pattern)
                print(format_search_result(result, "Source Grep"))

            elif args.action == "delete":
                result = await sources_delete(args.source_id)
                print(json.dumps(result, indent=2))

        # Papers commands
        elif args.command == "papers":
            if args.action == "list":
                result = await papers_list(args.limit, status=args.status)
                print(format_list_result(result, "Research Papers"))

            elif args.action == "index":
                print(f"Indexing arXiv paper: {args.arxiv_id}")
                result = await papers_index(args.arxiv_id)
                print(json.dumps(result, indent=2, default=str))

        # Context commands
        elif args.command == "context":
            if args.action == "list":
                result = await context_list(args.limit, tags=args.tags)
                print(format_list_result(result, "Contexts"))

            elif args.action == "save":
                result = await context_save(args.title, args.content, args.summary, args.tags)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "search":
                if args.semantic:
                    result = await context_search_semantic(args.query)
                else:
                    result = await context_search_text(args.query)
                print(format_search_result(result, "Context Search"))

            elif args.action == "get":
                result = await context_get(args.context_id)
                print(json.dumps(result, indent=2, default=str))

            elif args.action == "delete":
                result = await context_delete(args.context_id)
                print(json.dumps(result, indent=2))

        else:
            parser.print_help()

    except ImportError:
        print("Error: aiohttp not installed. Run: pip install aiohttp")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
