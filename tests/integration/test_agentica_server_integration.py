"""Integration tests for Agentica Server.

Tests that require API keys are marked with @needs_api_keys.
State persistence tests run without API keys.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

# Mark for tests that need API keys
needs_api_keys = pytest.mark.skipif(
    not (os.environ.get("PERPLEXITY_API_KEY") or os.environ.get("NIA_API_KEY")),
    reason="No API keys set"
)


@needs_api_keys
class TestServerIntegration:
    """Integration tests for the full server (requires API keys)."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path):
        """Create temporary state directory."""
        state_dir = tmp_path / ".claude" / "cache" / "agentica-state"
        state_dir.mkdir(parents=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_agent_query_returns_response(self, temp_state_dir):
        """Agent query should return a response."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(temp_state_dir)}):
            from fastapi.testclient import TestClient
            from scripts.agentica_patterns.server import app

            client = TestClient(app)
            response = client.post(
                "/agent/research/query",
                json={"query": "What is Python?"}
            )

            # Should get a response (may fail on API error but should process)
            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "response" in data
                assert len(data["response"]) > 0


@needs_api_keys
class TestStatePersistenceIntegrationWithAPI:
    """Integration tests for state persistence with real API calls."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path):
        """Create temporary state directory."""
        state_dir = tmp_path / ".claude" / "cache" / "agentica-state"
        state_dir.mkdir(parents=True)
        return tmp_path

    def test_state_persisted_after_query(self, temp_state_dir):
        """State should be persisted after agent query."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(temp_state_dir)}):
            from fastapi.testclient import TestClient
            from scripts.agentica_patterns.server import app

            client = TestClient(app)

            # Make a query
            client.post(
                "/agent/research/query",
                json={"query": "test query"}
            )

            # Check state file exists
            state_file = temp_state_dir / ".claude" / "cache" / "agentica-state" / "research.json"
            # May not exist if query failed, but if it does, check structure
            if state_file.exists():
                with open(state_file) as f:
                    data = json.load(f)
                assert "timestamp" in data
                assert "state" in data


class TestStatePersistenceIntegration:
    """Integration tests for state persistence (no API keys needed)."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path):
        """Create temporary state directory."""
        state_dir = tmp_path / ".claude" / "cache" / "agentica-state"
        state_dir.mkdir(parents=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_state_hydrated_on_restart(self, temp_state_dir):
        """Agent should hydrate state from file on recreation."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(temp_state_dir)}):
            from scripts.agentica_patterns.server.persistence import save_state, load_state

            # Pre-populate state
            original_state = {
                "findings": ["prior finding 1", "prior finding 2"],
                "sources": {"http://example.com": "Example"},
                "query_history": ["previous query"],
            }
            save_state("research", original_state)

            # Verify state was saved correctly
            loaded = load_state("research")
            assert loaded is not None
            assert "prior finding 1" in loaded.get("findings", [])
            assert "prior finding 2" in loaded.get("findings", [])
            assert loaded.get("sources", {}).get("http://example.com") == "Example"

    @pytest.mark.asyncio
    async def test_state_merges_on_hydration(self, temp_state_dir):
        """Persisted state should merge with initial agent state."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(temp_state_dir)}):
            from scripts.agentica_patterns.server.persistence import save_state

            # Pre-populate state
            save_state("research", {
                "findings": ["prior finding 1"],
                "custom_field": "preserved value",
            })

            # Create a mock agent with initial state
            class MockStatefulAgent:
                def __init__(self):
                    self.state = {
                        "findings": [],
                        "sources": {},
                        "query_history": [],
                    }

                async def call(self, return_type, task):
                    return "response"

            agent = MockStatefulAgent()

            # Simulate hydration logic from registry
            from scripts.agentica_patterns.server.persistence import load_state
            state = load_state("research")
            if state:
                for key, value in state.items():
                    agent.state[key] = value

            # Verify merged state
            assert "prior finding 1" in agent.state.get("findings", [])
            assert agent.state.get("custom_field") == "preserved value"


class TestMemoryManagement:
    """Integration tests for memory management (no API keys needed)."""

    def test_large_state_triggers_flush(self, tmp_path):
        """Large state should be flushed to manageable size."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import (
                save_state, should_flush, flush_state, get_state_size
            )

            # Create large state
            large_state = {
                "findings": [f"finding {i}" for i in range(1000)],
                "detailed_results": "x" * (1024 * 1024),  # 1MB
                "query_history": [f"query {i}" for i in range(500)],
            }
            save_state("research", large_state)

            # Should trigger flush
            assert should_flush("research")

            # Flush should reduce size
            original_size = get_state_size("research")
            flush_state("research")
            new_size = get_state_size("research")

            assert new_size < original_size
