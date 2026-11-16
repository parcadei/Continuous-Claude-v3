"""Tests for agent cards responsive wrapping in Agent Monitor TUI.

Verifies that:
1. GenericVisualizer uses Grid container for responsive wrapping
2. SwarmVisualizer uses Grid container for responsive wrapping
3. All agents render (no artificial limit)
"""

import inspect

import pytest

from scripts.agent_monitor_tui.widgets.agent_view import (
    GenericVisualizer,
    SwarmVisualizer,
)


class TestGenericVisualizerGrid:
    """Test GenericVisualizer uses Grid for responsive wrapping."""

    def test_uses_grid_container(self) -> None:
        """GenericVisualizer should use Grid container, not Horizontal."""
        # Get the source code of the compose method
        source = inspect.getsource(GenericVisualizer.compose)

        # Check for 'with Grid' pattern using string matching
        assert "with Grid(" in source, "GenericVisualizer.compose should use 'with Grid(...)'"
        # Old code used 'with Horizontal():' for cards - should not be present
        assert "with Horizontal():" not in source, (
            "GenericVisualizer.compose should not use 'with Horizontal():'"
        )

    def test_no_artificial_limit_in_source(self) -> None:
        """GenericVisualizer should not have artificial slicing limit."""
        source = inspect.getsource(GenericVisualizer.compose)

        # Check that there's no slice like [:8] which was the old limit
        assert "[:8]" not in source, "GenericVisualizer should not limit agents to 8"
        assert "[:" not in source or "self.agents[:" not in source, (
            "GenericVisualizer should not slice self.agents"
        )

    def test_stores_all_agents(self) -> None:
        """GenericVisualizer should store all agents passed to it."""
        from datetime import datetime, UTC
        from scripts.agentica_patterns.coordination import AgentRecord

        agents = [
            AgentRecord(
                id=f"agent-{i}",
                session_id="sess-123",
                premise="Test",
                model="test",
                scope_keys=[],
                pattern="generic",
                parent_agent_id=None,
                pid=12345,
                ppid=1000,
                spawned_at=datetime.now(UTC),
                completed_at=None,
                status="running",
                error_message=None,
            )
            for i in range(15)
        ]

        viz = GenericVisualizer(agents, [])

        # Check all agents are stored
        assert len(viz.agents) == 15

    def test_orphan_ids_extracted(self) -> None:
        """GenericVisualizer should extract orphan IDs correctly."""
        from datetime import datetime, UTC
        from scripts.agentica_patterns.coordination import AgentRecord, OrphanCandidate

        agents = [
            AgentRecord(
                id=f"agent-{i}",
                session_id="sess-123",
                premise="Test",
                model="test",
                scope_keys=[],
                pattern="generic",
                parent_agent_id=None,
                pid=12345,
                ppid=1000,
                spawned_at=datetime.now(UTC),
                completed_at=None,
                status="running",
                error_message=None,
            )
            for i in range(3)
        ]
        orphans = [
            OrphanCandidate(
                agent_id="agent-1",
                ppid=1,
                parent_agent_id=None,
                spawned_at=datetime.now(UTC),
                tier=1,
                reason="test",
            )
        ]

        viz = GenericVisualizer(agents, orphans)

        assert "agent-1" in viz.orphan_ids
        assert "agent-0" not in viz.orphan_ids
        assert "agent-2" not in viz.orphan_ids


class TestSwarmVisualizerGrid:
    """Test SwarmVisualizer uses Grid for responsive wrapping."""

    def test_uses_grid_container(self) -> None:
        """SwarmVisualizer should use Grid container, not Horizontal with row limit."""
        source = inspect.getsource(SwarmVisualizer.compose)

        # Check for 'with Grid' pattern using string matching
        assert "with Grid(" in source, "SwarmVisualizer.compose should use 'with Grid(...)'"

    def test_no_row_chunking(self) -> None:
        """SwarmVisualizer should not chunk agents into rows of 4."""
        source = inspect.getsource(SwarmVisualizer.compose)

        # Old code had row_agents and len(row_agents) == 4
        assert "row_agents" not in source, "SwarmVisualizer should not use row chunking"
        assert "== 4" not in source, "SwarmVisualizer should not limit to 4 per row"


class TestGridCSSConfiguration:
    """Test that CSS is configured for grid layout."""

    def test_generic_visualizer_has_grid_css(self) -> None:
        """GenericVisualizer should define grid CSS."""
        css = GenericVisualizer.DEFAULT_CSS
        assert "grid-size" in css, "GenericVisualizer CSS should include grid-size"
        assert "#agent-grid" in css, "GenericVisualizer CSS should target #agent-grid"

    def test_swarm_visualizer_has_grid_css(self) -> None:
        """SwarmVisualizer should define grid CSS."""
        css = SwarmVisualizer.DEFAULT_CSS
        assert "grid-size" in css, "SwarmVisualizer CSS should include grid-size"
        assert ".swarm-grid" in css, "SwarmVisualizer CSS should target .swarm-grid"

    def test_grid_size_value(self) -> None:
        """Grid should use appropriate grid-size for responsive layout."""
        generic_css = GenericVisualizer.DEFAULT_CSS
        swarm_css = SwarmVisualizer.DEFAULT_CSS

        # Both should have grid-size: 5 (or similar reasonable value)
        assert "grid-size: 5" in generic_css or "grid-size:5" in generic_css
        assert "grid-size: 5" in swarm_css or "grid-size:5" in swarm_css

    def test_grid_gutter_configured(self) -> None:
        """Grid should have gutter spacing configured."""
        generic_css = GenericVisualizer.DEFAULT_CSS
        swarm_css = SwarmVisualizer.DEFAULT_CSS

        assert "grid-gutter" in generic_css, "GenericVisualizer should have grid-gutter"
        assert "grid-gutter" in swarm_css, "SwarmVisualizer should have grid-gutter"
