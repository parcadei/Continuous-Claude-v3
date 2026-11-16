"""Pytest configuration for integration tests."""

import json
from pathlib import Path

import pytest

try:
    from runtime.mcp_client import get_mcp_client_manager
except ImportError:
    # Allow tests to be collected without runtime module
    get_mcp_client_manager = None


@pytest.fixture(scope="session", autouse=True)
def mcp_config_for_tests(tmp_path_factory):
    """Verify MCP config exists for integration tests.

    The runtime checks for config in this order:
    1. .mcp.json (Claude Code convention)
    2. mcp_config.json (tracked in repo)

    Since mcp_config.json is now tracked, tests can use it directly.
    """
    project_root = Path(__file__).parent.parent.parent
    mcp_json = project_root / ".mcp.json"
    mcp_config_json = project_root / "mcp_config.json"

    if mcp_json.exists():
        yield mcp_json
    elif mcp_config_json.exists():
        yield mcp_config_json
    else:
        pytest.skip("No MCP config found (.mcp.json or mcp_config.json)")


@pytest.fixture(autouse=True)
async def cleanup_mcp_manager():
    """Cleanup MCP client manager after each test.

    This fixture ensures that:
    1. Each test gets a fresh manager instance
    2. The singleton cache is cleared between tests
    3. All connections are properly closed

    This is critical because get_mcp_client_manager() uses @lru_cache
    which would otherwise share state across all tests.
    """
    # Yield to run the test
    yield

    # Cleanup after test
    try:
        manager = get_mcp_client_manager()
        # Only cleanup if manager was initialized
        if manager._state.value != "uninitialized":
            await manager.cleanup()
    except Exception as e:
        # Log but don't fail if cleanup has issues
        print(f"Warning: Manager cleanup failed: {e}")
    finally:
        # Clear the lru_cache to ensure next test gets fresh instance
        get_mcp_client_manager.cache_clear()
