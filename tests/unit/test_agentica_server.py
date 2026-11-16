"""Tests for Agentica Server - FastAPI agent hosting."""

import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

pytest.importorskip("fastapi")

# Mock agentica module if not installed
if "agentica" not in sys.modules:
    mock_agentica = MagicMock()
    mock_agentica.spawn = AsyncMock()
    sys.modules["agentica"] = mock_agentica


class TestServerImports:
    """Test server module imports."""

    def test_server_module_imports(self):
        """Server module should be importable."""
        from scripts.agentica_patterns.server import app
        assert app is not None

    def test_has_fastapi_app(self):
        """Should export FastAPI app instance."""
        from scripts.agentica_patterns.server import app
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        """GET /health should return 200 with status."""
        from fastapi.testclient import TestClient
        from scripts.agentica_patterns.server import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAgentQueryEndpoint:
    """Test agent query endpoint structure."""

    @pytest.mark.asyncio
    async def test_agent_endpoint_exists(self):
        """POST /agent/{type}/query should exist."""
        from fastapi.testclient import TestClient
        from scripts.agentica_patterns.server import app

        client = TestClient(app)

        # Without mocking, should fail gracefully (no API key)
        # But endpoint should exist
        response = client.post(
            "/agent/research/query",
            json={"query": "test"}
        )

        # Should not be 404 (endpoint exists)
        assert response.status_code != 404

    def test_query_requires_body(self):
        """POST /agent/{type}/query should require query body."""
        from fastapi.testclient import TestClient
        from scripts.agentica_patterns.server import app

        client = TestClient(app)
        response = client.post("/agent/research/query")

        # Should be 422 (validation error) not 404
        assert response.status_code == 422


class TestAgentRegistry:
    """Test agent type registry."""

    def test_registry_has_research_agent(self):
        """Registry should include research agent type."""
        from scripts.agentica_patterns.server.registry import AGENT_TYPES

        assert "research" in AGENT_TYPES
        assert callable(AGENT_TYPES["research"])

    def test_unknown_agent_type_rejected(self):
        """Unknown agent types should return 404."""
        from fastapi.testclient import TestClient
        from scripts.agentica_patterns.server import app

        client = TestClient(app)
        response = client.post(
            "/agent/unknown_type/query",
            json={"query": "test"}
        )

        assert response.status_code == 404
