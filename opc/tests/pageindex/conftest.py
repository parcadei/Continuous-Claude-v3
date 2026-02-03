"""Shared test fixtures for PageIndex test suite.

Provides:
- pytest markers (unit, integration, e2e, slow)
- Sample tree structures and documents
- Mock services and fixtures
- Database fixtures for integration tests
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

opc_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(opc_root))
sys.path.insert(0, str(opc_root / "scripts" / "pageindex"))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external deps)")
    config.addinivalue_line("markers", "integration: Integration tests (require PostgreSQL)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (require PostgreSQL + Claude CLI)")
    config.addinivalue_line("markers", "slow: Slow tests (real LLM calls, >10s)")


SAMPLE_ROADMAP_MD = """# Project Roadmap

## Overview
This is the project roadmap document.

## Current Focus
Working on the memory system integration.

### Phase 1: Foundation
- Set up database schema
- Create basic CRUD operations

### Phase 2: Integration
- Connect to Claude Code hooks
- Add semantic search

## Goals

### Short-term Goals
- Complete memory recall
- Add batch indexing

### Long-term Goals
- Full semantic search
- Cross-project knowledge sharing

## Architecture

### Database Design
Using PostgreSQL with pgvector for embeddings.

### API Design
RESTful endpoints for CRUD operations.

## Timeline
- Q1: Foundation
- Q2: Integration
- Q3: Polish
"""

SAMPLE_ARCHITECTURE_MD = """# Architecture

## Overview
System architecture document.

## Components

### Memory System
Handles persistent storage of learnings.

#### PostgreSQL Backend
Primary data store with pgvector.

#### Embedding Service
Generates embeddings for semantic search.

### Hook System
Intercepts Claude Code events.

#### PreToolUse Hooks
Run before tool execution.

#### PostToolUse Hooks
Run after tool execution.

## Data Flow
1. User input
2. Hook processing
3. Memory query
4. Response generation
"""

SAMPLE_TREE_STRUCTURE = {
    "doc_name": "ROADMAP.md",
    "structure": [
        {
            "node_id": "0001",
            "title": "Project Roadmap",
            "level": 1,
            "text": "This is the project roadmap document.",
            "line_num": 1,
            "nodes": [
                {
                    "node_id": "0002",
                    "title": "Overview",
                    "level": 2,
                    "text": "This is the project roadmap document.",
                    "line_num": 3,
                    "nodes": []
                },
                {
                    "node_id": "0003",
                    "title": "Current Focus",
                    "level": 2,
                    "text": "Working on the memory system integration.",
                    "line_num": 6,
                    "nodes": [
                        {
                            "node_id": "0004",
                            "title": "Phase 1: Foundation",
                            "level": 3,
                            "text": "- Set up database schema\n- Create basic CRUD operations",
                            "line_num": 9,
                            "nodes": []
                        },
                        {
                            "node_id": "0005",
                            "title": "Phase 2: Integration",
                            "level": 3,
                            "text": "- Connect to Claude Code hooks\n- Add semantic search",
                            "line_num": 13,
                            "nodes": []
                        }
                    ]
                },
                {
                    "node_id": "0006",
                    "title": "Goals",
                    "level": 2,
                    "text": "",
                    "line_num": 17,
                    "nodes": [
                        {
                            "node_id": "0007",
                            "title": "Short-term Goals",
                            "level": 3,
                            "text": "- Complete memory recall\n- Add batch indexing",
                            "line_num": 19,
                            "nodes": []
                        },
                        {
                            "node_id": "0008",
                            "title": "Long-term Goals",
                            "level": 3,
                            "text": "- Full semantic search\n- Cross-project knowledge sharing",
                            "line_num": 23,
                            "nodes": []
                        }
                    ]
                },
                {
                    "node_id": "0009",
                    "title": "Architecture",
                    "level": 2,
                    "text": "",
                    "line_num": 27,
                    "nodes": [
                        {
                            "node_id": "0010",
                            "title": "Database Design",
                            "level": 3,
                            "text": "Using PostgreSQL with pgvector for embeddings.",
                            "line_num": 29,
                            "nodes": []
                        },
                        {
                            "node_id": "0011",
                            "title": "API Design",
                            "level": 3,
                            "text": "RESTful endpoints for CRUD operations.",
                            "line_num": 32,
                            "nodes": []
                        }
                    ]
                },
                {
                    "node_id": "0012",
                    "title": "Timeline",
                    "level": 2,
                    "text": "- Q1: Foundation\n- Q2: Integration\n- Q3: Polish",
                    "line_num": 35,
                    "nodes": []
                }
            ]
        }
    ]
}

SAMPLE_ARCHITECTURE_TREE = {
    "doc_name": "ARCHITECTURE.md",
    "structure": [
        {
            "node_id": "0001",
            "title": "Architecture",
            "level": 1,
            "text": "System architecture document.",
            "line_num": 1,
            "nodes": [
                {
                    "node_id": "0002",
                    "title": "Overview",
                    "level": 2,
                    "text": "System architecture document.",
                    "line_num": 3,
                    "nodes": []
                },
                {
                    "node_id": "0003",
                    "title": "Components",
                    "level": 2,
                    "text": "",
                    "line_num": 6,
                    "nodes": [
                        {
                            "node_id": "0004",
                            "title": "Memory System",
                            "level": 3,
                            "text": "Handles persistent storage of learnings.",
                            "line_num": 8,
                            "nodes": [
                                {
                                    "node_id": "0005",
                                    "title": "PostgreSQL Backend",
                                    "level": 4,
                                    "text": "Primary data store with pgvector.",
                                    "line_num": 11,
                                    "nodes": []
                                },
                                {
                                    "node_id": "0006",
                                    "title": "Embedding Service",
                                    "level": 4,
                                    "text": "Generates embeddings for semantic search.",
                                    "line_num": 14,
                                    "nodes": []
                                }
                            ]
                        },
                        {
                            "node_id": "0007",
                            "title": "Hook System",
                            "level": 3,
                            "text": "Intercepts Claude Code events.",
                            "line_num": 17,
                            "nodes": [
                                {
                                    "node_id": "0008",
                                    "title": "PreToolUse Hooks",
                                    "level": 4,
                                    "text": "Run before tool execution.",
                                    "line_num": 20,
                                    "nodes": []
                                },
                                {
                                    "node_id": "0009",
                                    "title": "PostToolUse Hooks",
                                    "level": 4,
                                    "text": "Run after tool execution.",
                                    "line_num": 23,
                                    "nodes": []
                                }
                            ]
                        }
                    ]
                },
                {
                    "node_id": "0010",
                    "title": "Data Flow",
                    "level": 2,
                    "text": "1. User input\n2. Hook processing\n3. Memory query\n4. Response generation",
                    "line_num": 26,
                    "nodes": []
                }
            ]
        }
    ]
}


@pytest.fixture
def sample_tree() -> dict[str, Any]:
    """Provide sample tree structure for testing."""
    return SAMPLE_TREE_STRUCTURE.copy()


@pytest.fixture
def sample_architecture_tree() -> dict[str, Any]:
    """Provide sample architecture tree structure."""
    return SAMPLE_ARCHITECTURE_TREE.copy()


@pytest.fixture
def sample_roadmap_content() -> str:
    """Provide sample roadmap markdown content."""
    return SAMPLE_ROADMAP_MD


@pytest.fixture
def sample_architecture_content() -> str:
    """Provide sample architecture markdown content."""
    return SAMPLE_ARCHITECTURE_MD


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with sample files."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    (project_dir / "ROADMAP.md").write_text(SAMPLE_ROADMAP_MD, encoding="utf-8")
    (project_dir / "docs").mkdir()
    (project_dir / "docs" / "ARCHITECTURE.md").write_text(SAMPLE_ARCHITECTURE_MD, encoding="utf-8")
    (project_dir / "README.md").write_text("# Test Project\n\nA test project.", encoding="utf-8")

    return project_dir


@pytest.fixture
def mock_psycopg2_conn():
    """Provide a mock psycopg2 connection."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=None)
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def mock_claude_cli():
    """Mock Claude CLI for unit tests."""
    def _mock_response(response_text: str):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": response_text})
        mock_result.stderr = ""
        return mock_result

    return _mock_response


@pytest.fixture
def require_postgres():
    """Skip test if PostgreSQL is not available."""
    from dotenv import load_dotenv
    load_dotenv(override=True)

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://claude:claude_dev@localhost:5432/continuous_claude"
    )
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")


@pytest.fixture
def require_claude_cli():
    """Skip test if Claude CLI is not available."""
    import subprocess
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            pytest.skip("Claude CLI not available or not authenticated")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"Claude CLI not available: {e}")


@pytest.fixture
def require_anthropic_api():
    """Skip test if Anthropic API is not available or has no credits.

    Tests can use either:
    1. ANTHROPIC_API_KEY with credits
    2. Claude CLI fallback (if API key not set)
    """
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-haiku-4-5-20251001",  # Claude Haiku 4.5
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                pytest.skip("Anthropic API has no credits - unset ANTHROPIC_API_KEY to use Claude CLI fallback")
            pytest.skip(f"Anthropic API error: {e}")
        except Exception as e:
            pytest.skip(f"Anthropic API not available: {e}")
    else:
        import subprocess
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                pytest.skip("Claude CLI not available and ANTHROPIC_API_KEY not set")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            pytest.skip(f"Neither Anthropic API key nor Claude CLI available: {e}")


@pytest.fixture
def clean_pageindex_tables(require_postgres):
    """Clean pageindex tables before/after test."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from dotenv import load_dotenv
    load_dotenv(override=True)

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://claude:claude_dev@localhost:5432/continuous_claude"
    )

    def cleanup():
        conn = psycopg2.connect(database_url)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pageindex_trees WHERE project_id LIKE 'test_%'")
            conn.commit()
        conn.close()

    cleanup()
    yield
    cleanup()


GOLDEN_SEARCH_TESTS = [
    {
        "query": "What is the current focus?",
        "expected_nodes": ["0003"],
        "expected_titles": ["Current Focus"],
        "min_confidence": 0.7,
    },
    {
        "query": "database design",
        "expected_nodes": ["0010"],
        "expected_titles": ["Database Design"],
        "min_confidence": 0.7,
    },
    {
        "query": "project goals",
        "expected_nodes": ["0006", "0007", "0008"],
        "expected_titles": ["Goals", "Short-term Goals", "Long-term Goals"],
        "min_confidence": 0.6,
    },
    {
        "query": "timeline and schedule",
        "expected_nodes": ["0012"],
        "expected_titles": ["Timeline"],
        "min_confidence": 0.7,
    },
    {
        "query": "integration phase",
        "expected_nodes": ["0005"],
        "expected_titles": ["Phase 2: Integration"],
        "min_confidence": 0.7,
    },
]


@pytest.fixture
def golden_tests() -> list[dict[str, Any]]:
    """Provide golden test cases for search accuracy testing."""
    return GOLDEN_SEARCH_TESTS.copy()
