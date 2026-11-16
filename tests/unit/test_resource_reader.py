"""Unit tests for TypeScript resource-reader.ts.

Tests the resource reader utility that reads resources JSON from
/tmp/claude-resources-{sessionId}.json.

Follows TDD: Write tests FIRST, then implement.

Phase 4 of: docs/handoffs/resource-limits-plan.md
"""

import json
import os
import subprocess
from pathlib import Path
import pytest


class TestResourceReaderFileExists:
    """Tests that the resource-reader.ts file exists."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_resource_reader_ts_exists(self, shared_dir: Path):
        """resource-reader.ts should exist in shared directory."""
        resource_reader = shared_dir / "resource-reader.ts"

        assert resource_reader.exists(), (
            f"Expected {resource_reader} to exist. "
            "Create .claude/hooks/src/shared/resource-reader.ts"
        )


class TestResourceStateInterface:
    """Tests for the ResourceState interface."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_exports_resource_state_interface(self, hooks_dir: Path, tmp_path: Path):
        """Module should export ResourceState interface."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_interface.ts"
        test_script.write_text(f'''
import {{ ResourceState }} from '{resource_reader}';
const state: ResourceState = {{
    freeMemMB: 8000,
    activeAgents: 2,
    maxAgents: 12,
    contextPct: 45
}};
console.log(JSON.stringify(state));
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Failed to use ResourceState: {result.stderr}"

        state = json.loads(result.stdout.strip())
        assert state["freeMemMB"] == 8000
        assert state["activeAgents"] == 2
        assert state["maxAgents"] == 12
        assert state["contextPct"] == 45


class TestReadResourceState:
    """Tests for readResourceState() function."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def session_id(self):
        """Generate unique session ID for tests."""
        return f"test-resource-reader-{os.getpid()}"

    @pytest.fixture
    def resource_file(self, session_id):
        """Create and cleanup resource file for tests."""
        path = Path(f"/tmp/claude-resources-{session_id}.json")
        yield path
        # Cleanup
        if path.exists():
            path.unlink()

    def test_exports_read_resource_state_function(self, hooks_dir: Path, tmp_path: Path):
        """Module should export readResourceState function."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_export.ts"
        test_script.write_text(f'''
import {{ readResourceState }} from '{resource_reader}';
console.log(typeof readResourceState);
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Failed to import readResourceState: {result.stderr}"
        assert result.stdout.strip() == "function"

    def test_returns_null_when_file_missing(self, hooks_dir: Path, tmp_path: Path, session_id, resource_file):
        """readResourceState() returns null when file doesn't exist."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        # Ensure file doesn't exist
        if resource_file.exists():
            resource_file.unlink()

        test_script = tmp_path / "test_missing.ts"
        test_script.write_text(f'''
import {{ readResourceState }} from '{resource_reader}';
const state = readResourceState();
console.log(JSON.stringify(state));
''')

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"
        assert result.stdout.strip() == "null"

    def test_returns_resource_state_when_file_exists(self, hooks_dir: Path, tmp_path: Path, session_id, resource_file):
        """readResourceState() parses valid JSON file correctly."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        # Create valid resource file
        resource_data = {
            "freeMemMB": 8000,
            "activeAgents": 2,
            "maxAgents": 12,
            "contextPct": 45
        }
        resource_file.write_text(json.dumps(resource_data))

        test_script = tmp_path / "test_parse.ts"
        test_script.write_text(f'''
import {{ readResourceState }} from '{resource_reader}';
const state = readResourceState();
console.log(JSON.stringify(state));
''')

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"

        state = json.loads(result.stdout.strip())
        assert state is not None
        assert state["freeMemMB"] == 8000
        assert state["activeAgents"] == 2
        assert state["maxAgents"] == 12
        assert state["contextPct"] == 45

    def test_returns_null_on_corrupt_json(self, hooks_dir: Path, tmp_path: Path, session_id, resource_file):
        """readResourceState() returns null on corrupt JSON."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        # Write corrupt JSON
        resource_file.write_text("{ invalid json [")

        test_script = tmp_path / "test_corrupt.ts"
        test_script.write_text(f'''
import {{ readResourceState }} from '{resource_reader}';
const state = readResourceState();
console.log(JSON.stringify(state));
''')

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Should not throw on corrupt JSON: {result.stderr}"
        assert result.stdout.strip() == "null"

    def test_returns_defaults_on_missing_fields(self, hooks_dir: Path, tmp_path: Path, session_id, resource_file):
        """readResourceState() handles partial JSON with defaults."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        # Write partial JSON (missing some fields)
        resource_file.write_text('{"freeMemMB": 5000}')

        test_script = tmp_path / "test_defaults.ts"
        test_script.write_text(f'''
import {{ readResourceState }} from '{resource_reader}';
const state = readResourceState();
console.log(JSON.stringify(state));
''')

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"

        state = json.loads(result.stdout.strip())
        assert state is not None
        assert state["freeMemMB"] == 5000
        # Missing fields should have defaults
        assert state["activeAgents"] == 0
        assert state["maxAgents"] == 10
        assert state["contextPct"] == 0


class TestGetSessionId:
    """Tests for getSessionId() helper function."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_exports_get_session_id_function(self, hooks_dir: Path, tmp_path: Path):
        """Module should export getSessionId function."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_session_id_export.ts"
        test_script.write_text(f'''
import {{ getSessionId }} from '{resource_reader}';
console.log(typeof getSessionId);
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Failed to import getSessionId: {result.stderr}"
        assert result.stdout.strip() == "function"

    def test_returns_claude_session_id_when_set(self, hooks_dir: Path, tmp_path: Path):
        """getSessionId() returns CLAUDE_SESSION_ID when set."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_session_id_env.ts"
        test_script.write_text(f'''
import {{ getSessionId }} from '{resource_reader}';
console.log(getSessionId());
''')

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = "test-session-123"

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"
        assert result.stdout.strip() == "test-session-123"

    def test_returns_string(self, hooks_dir: Path, tmp_path: Path):
        """getSessionId() always returns a string."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_session_id_type.ts"
        test_script.write_text(f'''
import {{ getSessionId }} from '{resource_reader}';
const id = getSessionId();
console.log(typeof id);
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"
        assert result.stdout.strip() == "string"


class TestDefaultResourceState:
    """Tests for DEFAULT_RESOURCE_STATE constant."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_exports_default_resource_state(self, hooks_dir: Path, tmp_path: Path):
        """Module should export DEFAULT_RESOURCE_STATE constant."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_default_export.ts"
        test_script.write_text(f'''
import {{ DEFAULT_RESOURCE_STATE }} from '{resource_reader}';
console.log(JSON.stringify(DEFAULT_RESOURCE_STATE));
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Failed to import DEFAULT_RESOURCE_STATE: {result.stderr}"

        defaults = json.loads(result.stdout.strip())
        assert "freeMemMB" in defaults
        assert "activeAgents" in defaults
        assert "maxAgents" in defaults
        assert "contextPct" in defaults

    def test_default_values_are_sensible(self, hooks_dir: Path, tmp_path: Path):
        """Default values should be sensible fallbacks."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_default_values.ts"
        test_script.write_text(f'''
import {{ DEFAULT_RESOURCE_STATE }} from '{resource_reader}';
console.log(JSON.stringify(DEFAULT_RESOURCE_STATE));
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"

        defaults = json.loads(result.stdout.strip())
        # Sensible defaults
        assert defaults["freeMemMB"] >= 1024  # At least 1GB
        assert defaults["activeAgents"] == 0  # No agents by default
        assert defaults["maxAgents"] >= 1     # At least 1 agent allowed
        assert 0 <= defaults["contextPct"] <= 100


class TestResourceFilePath:
    """Tests for getResourceFilePath() helper function."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_exports_get_resource_file_path(self, hooks_dir: Path, tmp_path: Path):
        """Module should export getResourceFilePath function."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_filepath_export.ts"
        test_script.write_text(f'''
import {{ getResourceFilePath }} from '{resource_reader}';
console.log(typeof getResourceFilePath);
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Failed to import: {result.stderr}"
        assert result.stdout.strip() == "function"

    def test_returns_correct_path_format(self, hooks_dir: Path, tmp_path: Path):
        """getResourceFilePath() returns /tmp/claude-resources-{sessionId}.json."""
        resource_reader = hooks_dir / "src" / "shared" / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        test_script = tmp_path / "test_filepath_format.ts"
        test_script.write_text(f'''
import {{ getResourceFilePath }} from '{resource_reader}';
const path = getResourceFilePath('test-123');
console.log(path);
''')

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Function threw: {result.stderr}"
        assert result.stdout.strip() == "/tmp/claude-resources-test-123.json"


class TestFileContentAnalysis:
    """Tests for the structure of resource-reader.ts file."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_exports_resource_state_interface_in_file(self, shared_dir: Path):
        """File should export ResourceState interface."""
        resource_reader = shared_dir / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        content = resource_reader.read_text()
        assert "export interface ResourceState" in content, (
            "resource-reader.ts should export ResourceState interface"
        )

    def test_uses_fs_module(self, shared_dir: Path):
        """File should import from fs module."""
        resource_reader = shared_dir / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        content = resource_reader.read_text()
        assert "from 'fs'" in content or 'from "fs"' in content, (
            "resource-reader.ts should import from fs module"
        )

    def test_has_freememmb_field(self, shared_dir: Path):
        """ResourceState should have freeMemMB field."""
        resource_reader = shared_dir / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        content = resource_reader.read_text()
        assert "freeMemMB" in content, (
            "ResourceState should have freeMemMB field"
        )

    def test_has_activeagents_field(self, shared_dir: Path):
        """ResourceState should have activeAgents field."""
        resource_reader = shared_dir / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        content = resource_reader.read_text()
        assert "activeAgents" in content, (
            "ResourceState should have activeAgents field"
        )

    def test_has_maxagents_field(self, shared_dir: Path):
        """ResourceState should have maxAgents field."""
        resource_reader = shared_dir / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        content = resource_reader.read_text()
        assert "maxAgents" in content, (
            "ResourceState should have maxAgents field"
        )

    def test_has_contextpct_field(self, shared_dir: Path):
        """ResourceState should have contextPct field."""
        resource_reader = shared_dir / "resource-reader.ts"

        if not resource_reader.exists():
            pytest.skip("resource-reader.ts doesn't exist yet")

        content = resource_reader.read_text()
        assert "contextPct" in content, (
            "ResourceState should have contextPct field"
        )
